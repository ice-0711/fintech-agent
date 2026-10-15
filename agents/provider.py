"""Gemini provider adapter (W03-L) on the official `google-genai` SDK.

- SDK hidden retries are disabled (HttpRetryOptions attempts=1) and automatic
  function calling is off, so every HTTP send goes through the budget gate.
- One explicit retry at most for 429/5xx/timeout, honouring Retry-After plus
  jitter, and it shares the job's 8-send cap.
- A single configured model id; there is no fallback model and no paid tier
  switch. If the configured model has no verified quota, nothing is sent.
- Every send records model id, returned model version, prompt version,
  prompt hash and usageMetadata in the job events and the usage ledger.
"""

from __future__ import annotations

import hashlib
import json
import os
import random
import time
from typing import Any, Callable

from .budget import BudgetExceeded, BudgetGate, estimate_tokens
from .store import JobStore
from .tools import TOOL_DECLARATIONS, ROLE_TOOLS, args_hash, dispatch

RETRYABLE_CODES = {408, 429, 500, 502, 503, 504}
HTTP_TIMEOUT_MS = 45_000        # below the 60 s lease, so a heartbeat before each send keeps the lease alive
MAX_RETRY_SLEEP = 20.0          # longer Retry-After → pause the job instead of holding the lease

# Gemini 3 thinking is set by thinking_level and cannot be turned off.
# Allowed levels per model, from ai.google.dev/gemini-api/docs/thinking (checked 2026-09-28).
THINKING_LEVELS = {
    "gemini-3.8-flash": ("low", "medium", "high"),
    "gemini-3.7-flash": ("low", "medium", "high"),
    "gemini-3.6-flash": ("minimal", "low", "medium", "high"),
    "gemini-3.5-flash": ("minimal", "low", "medium", "high"),
    "gemini-3.5-flash-lite": ("minimal", "low", "medium", "high"),
}
DEFAULT_THINKING_LEVEL = "minimal"  # keeps most of the 1,500 output tokens for the answer


def make_client(api_key: str | None = None):  # pragma: no cover - needs a real key
    """Official SDK client with SDK-level retries disabled."""

    from google import genai
    from google.genai import types

    key = api_key or os.getenv("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY 未設定；只能執行 mock 測試。")
    return genai.Client(
        api_key=key,
        http_options=types.HttpOptions(timeout=HTTP_TIMEOUT_MS, retry_options=types.HttpRetryOptions(attempts=1)),
    )


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _usage_dict(resp: Any) -> dict[str, Any]:
    usage = getattr(resp, "usage_metadata", None)
    if usage is None:
        return {}
    fields = ("prompt_token_count", "candidates_token_count", "thoughts_token_count",
              "tool_use_prompt_token_count", "cached_content_token_count", "total_token_count")
    return {f: getattr(usage, f, None) for f in fields}


def _retry_after_seconds(exc: Exception) -> float | None:
    response = getattr(exc, "response", None)
    headers = getattr(response, "headers", None) or {}
    value = headers.get("retry-after") if hasattr(headers, "get") else None
    try:
        return float(value) if value is not None else None
    except ValueError:
        return None


class GeminiAdapter:
    def __init__(self, client: Any, model_id: str, gate: BudgetGate, *, prompt_version: str,
                 thinking_level: str = DEFAULT_THINKING_LEVEL, sleep: Callable[[float], None] = time.sleep,
                 monotonic: Callable[[], float] = time.monotonic, heartbeat: Callable[[], None] = lambda: None):
        if not model_id:
            raise ValueError("GEMINI_MODEL 未設定；model id 由組長於 handoff/model-config.md 鎖定。")
        if gate.quota.model_id and gate.quota.model_id != model_id:
            raise ValueError(f"quota 核實的是 {gate.quota.model_id}，不能改用 {model_id}（不做 fallback）。")
        allowed = THINKING_LEVELS.get(model_id)
        if allowed is not None and thinking_level not in allowed:
            raise ValueError(f"{model_id} 的 thinking_level 只能是 {allowed}，收到 {thinking_level}")
        self.client, self.model_id, self.gate = client, model_id, gate
        self.prompt_version, self.thinking_level = prompt_version, thinking_level
        self.sleep, self.monotonic, self.heartbeat = sleep, monotonic, heartbeat

    @property
    def store(self) -> JobStore:
        return self.gate.store

    @property
    def job_id(self) -> str:
        return self.gate.job["job_id"]

    def build_config(self, role: str, system_instruction: str, allow_tools: bool = True):
        """allow_tools=False keeps the declarations (same prompt) but forces a text answer,
        e.g. the last research call must return a draft so call 5 stays free for review."""
        from google.genai import types

        allowed = set(ROLE_TOOLS[role])
        declarations = [
            types.FunctionDeclaration(name=t["name"], description=t["description"],
                                      parameters_json_schema=t["parameters"])
            for t in TOOL_DECLARATIONS if t["name"] in allowed
        ]
        return types.GenerateContentConfig(
            system_instruction=system_instruction,
            tools=[types.Tool(function_declarations=declarations)],
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            tool_config=None if allow_tools else types.ToolConfig(
                function_calling_config=types.FunctionCallingConfig(mode=types.FunctionCallingConfigMode.NONE)),
            max_output_tokens=self.gate.limits.max_output_tokens,
            temperature=0,
            thinking_config=types.ThinkingConfig(thinking_level=types.ThinkingLevel(self.thinking_level.upper())),
        )

    @staticmethod
    def prompt_text(role: str, contents: list[Any], system_instruction: str) -> str:
        """Text we estimate and hash. Tool declarations are billed as input too
        (live check 2026-09-28: ~500 tokens), so they are included."""
        tools_json = json.dumps([t for t in TOOL_DECLARATIONS if t["name"] in ROLE_TOOLS[role]], ensure_ascii=False)
        return system_instruction + "\n" + tools_json + "\n" + json.dumps(
            [c.model_dump(mode="json", exclude_none=True) if hasattr(c, "model_dump") else c for c in contents],
            ensure_ascii=False,
        )

    def estimate_input(self, role: str, contents: list[Any], system_instruction: str) -> int:
        return estimate_tokens(self.prompt_text(role, contents, system_instruction))

    def send(self, role: str, contents: list[Any], system_instruction: str, allow_tools: bool = True) -> Any:
        """One logical request = up to 1 + max_retries HTTP sends, all counted."""

        import httpx
        from google.genai import errors

        config = self.build_config(role, system_instruction, allow_tools)
        prompt_text = self.prompt_text(role, contents, system_instruction)
        prompt_hash = _hash(prompt_text)
        for attempt in range(self.gate.limits.max_retries + 1):
            self.heartbeat()  # renew the 60 s lease before a send that may take up to 45 s
            res = self.gate.reserve_call(role, prompt_text, prompt_hash, prompt_version=self.prompt_version)
            started = self.monotonic()
            try:
                resp = self.client.models.generate_content(model=self.model_id, contents=contents, config=config)
            except (errors.APIError, httpx.TimeoutException, httpx.TransportError) as exc:
                code = exc.code if isinstance(exc, errors.APIError) else 408
                self.gate.settle(res, f"error_{code}", None)
                self.store.append_event(self.job_id, role, "model_error", detail={
                    "call_number": res.call_number, "code": code, "error": type(exc).__name__,
                    "model_id": self.model_id, "prompt_version": self.prompt_version, "prompt_hash": prompt_hash,
                })
                self.gate.add_active_time(self.monotonic() - started)
                self.heartbeat()
                retryable = code in RETRYABLE_CODES and attempt < self.gate.limits.max_retries
                wait = (_retry_after_seconds(exc) or 2.0) if retryable else 0.0
                if retryable and wait <= MAX_RETRY_SLEEP and self.gate.can_send_again():
                    self.sleep(wait + random.uniform(0, 1))
                    continue
                if code == 429 or (retryable and wait > MAX_RETRY_SLEEP):
                    raise BudgetExceeded("provider_429", "供應商限流，重試後仍失敗；保存 paused_quota",
                                         wait_seconds=max(wait, 60.0)) from exc
                raise
            except Exception:
                # Unknown failure after the send: keep the reservation as observed, never refund.
                self.gate.settle(res, "error_unknown", None)
                raise
            usage = _usage_dict(resp)
            self.gate.settle(res, "ok", usage.get("total_token_count"))
            candidate = (getattr(resp, "candidates", None) or [None])[0]
            self.store.append_event(self.job_id, role, "model_call", detail={
                "call_number": res.call_number,
                "model_id": self.model_id,
                "model_version": getattr(resp, "model_version", None),
                "prompt_version": self.prompt_version,
                "prompt_hash": prompt_hash,
                "thinking_level": self.thinking_level,
                "input_estimate": res.input_estimate,
                "estimate_under_actual": (usage.get("prompt_token_count") or 0) > res.input_estimate,
                "usage": usage,
                "finish_reason": str(getattr(candidate, "finish_reason", None)),
                "function_calls": [fc.name for fc in (resp.function_calls or [])],
            })
            self.heartbeat()
            # Record time last: going over 180 s stops the job, but this send is already accounted for.
            self.gate.add_active_time(self.monotonic() - started)
            return resp
        raise AssertionError("unreachable")

    def run_tool_roundtrip(self, role: str, user_prompt: str, system_instruction: str) -> dict[str, Any]:
        """Model → tool call(s) → function response → model, until text or a budget stop."""

        from google.genai import types

        contents: list[Any] = [types.Content(role="user", parts=[types.Part.from_text(text=user_prompt)])]
        while True:
            resp = self.send(role, contents, system_instruction)
            calls = resp.function_calls or []
            if not calls:
                return {"text": resp.text, "contents": contents, "response": resp}
            contents.append(resp.candidates[0].content)
            parts = []
            for call in calls:
                args = dict(call.args or {})
                h = args_hash(args)
                self.gate.register_tool_call(call.name, h)
                result = dispatch(role, call.name, args, job_cutoff=self.gate.job.get("cutoff_at"))
                self.store.append_event(self.job_id, role, "tool_call", call.name, {
                    "args_hash": h,
                    "output_hash": _hash(json.dumps(result, sort_keys=True, ensure_ascii=False))[:16],
                    "status": result.get("status"),
                    "reason": result.get("reason"),
                })
                parts.append(types.Part.from_function_response(name=call.name, response=result))
            contents.append(types.Content(role="user", parts=parts))
