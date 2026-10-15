"""Job contract V1.2 (handbook ch.02 「資料契約 V1.2」).

Only the three research tickers may create LLM jobs. 2379/3034 are
comparison-only references for 2454, and 2330 is an industry reference inside
the 2454 comparison panel; none of those add Gemini jobs.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

CONTRACT_VERSION = "v1.2"
QUESTION_VERSION = "macro-fundamental-valuation-v1"
PROMPT_VERSION = "v1.2"

RESEARCH_TICKERS = ("2330", "2317", "2454")
COMPARISON_ONLY_TICKERS = ("2379", "3034")

JOB_STATUSES = (
    "queued",
    "running",
    "paused_quota",
    "succeeded",
    "insufficient_evidence",
    "timed_out",
    "failed",
    "cancelled",
)
TERMINAL_STATUSES = ("succeeded", "insufficient_evidence", "timed_out", "failed", "cancelled")
STAGES = ("research", "tools", "review", "revision", "finished")
MODES = ("workflow", "single", "dual")


class ContractError(ValueError):
    """Request does not satisfy the V1.2 job contract."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def parse_cutoff(value: Any) -> str:
    """Normalise cutoff_at to ISO-8601 UTC. A cutoff is required, never guessed."""

    if not value:
        raise ContractError("cutoff_at 必填（ISO-8601）。")
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise ContractError(f"cutoff_at 格式錯誤：{value}") from exc
    if parsed.tzinfo is None:
        raise ContractError("cutoff_at 需含時區，例如 2026-09-30T13:30:00+08:00。")
    return parsed.astimezone(timezone.utc).isoformat(timespec="seconds")


def validate_job_request(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate a create-job request and return the normalised fields."""

    ticker = str(payload.get("ticker") or "").strip()
    if ticker in COMPARISON_ONLY_TICKERS:
        raise ContractError(f"{ticker} 只作 2454 比較參照，不建立 LLM 研究 job。")
    if ticker not in RESEARCH_TICKERS:
        raise ContractError(f"研究標的只限 {', '.join(RESEARCH_TICKERS)}。")

    mode = str(payload.get("mode") or "dual")
    if mode not in MODES:
        raise ContractError(f"mode 只限 {', '.join(MODES)}。")

    snapshot_id = str(payload.get("source_snapshot_id") or "").strip()
    if not snapshot_id:
        raise ContractError("source_snapshot_id 必填；job 必須綁定不可變快照。")

    idempotency_key = str(payload.get("idempotency_key") or "").strip()
    if not idempotency_key or len(idempotency_key) > 128:
        raise ContractError("idempotency_key 必填，且不超過 128 字元。")

    focus = payload.get("focus")
    if focus is not None and (not isinstance(focus, str) or len(focus) > 200):
        raise ContractError("focus 為選填文字，不超過 200 字（例如開發案例題目）。")

    return {
        "ticker": ticker,
        "mode": mode,
        "focus": focus,
        "cutoff_at": parse_cutoff(payload.get("cutoff_at")),
        "source_snapshot_id": snapshot_id,
        "idempotency_key": idempotency_key,
        "question_version": str(payload.get("question_version") or QUESTION_VERSION),
    }


def new_job_record(request: dict[str, Any], model_id: str | None) -> dict[str, Any]:
    """Build the initial job row. model_id stays null until configured."""

    return {
        "job_id": str(uuid.uuid4()),
        "ticker": request["ticker"],
        "market": "TW",
        "currency": "TWD",
        "question_version": request["question_version"],
        "cutoff_at": request["cutoff_at"],
        "source_snapshot_id": request["source_snapshot_id"],
        "mode": request["mode"],
        "focus": request.get("focus"),
        "status": "queued",
        "stage": "research",
        "model_id": model_id,
        "prompt_version": PROMPT_VERSION,
        "calls_used": 0,
        "tokens_observed": 0,
        "tokens_reserved": 0,
        "tool_calls_used": 0,
        "supplement_rounds": 0,
        "active_seconds": 0.0,
        "stop_reason": None,
        "checkpoint_version": 1,
        "idempotency_key": request["idempotency_key"],
        "created_at": utc_now_iso(),
        "updated_at": utc_now_iso(),
    }
