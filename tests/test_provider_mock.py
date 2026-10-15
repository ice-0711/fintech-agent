"""W03-L: Gemini adapter against a scripted fake client (MOCK — no network, no key).

Responses are built with the official SDK types so parsing matches real replies.
"""

import pytest
from google.genai import errors, types

from agents.budget import BudgetExceeded, BudgetGate, ProjectQuota
from agents.contract import validate_job_request
from agents.provider import GeminiAdapter
from agents.tools import register_tool, _REGISTRY
from conftest import job_request

MODEL = "gemini-3.5-flash-lite"  # locked by the lead in handoff/quota-baseline.json


def fc_response(name, args, total=120, signature=b"sig-fixture"):
    return types.GenerateContentResponse(
        candidates=[types.Candidate(
            content=types.Content(role="model", parts=[types.Part(
                function_call=types.FunctionCall(name=name, args=args), thought_signature=signature)]),
            finish_reason=types.FinishReason.STOP,
        )],
        usage_metadata=types.GenerateContentResponseUsageMetadata(
            prompt_token_count=total - 20, candidates_token_count=20, total_token_count=total),
        model_version=MODEL + "-001",
    )


def text_response(text, total=200):
    return types.GenerateContentResponse(
        candidates=[types.Candidate(content=types.Content(role="model", parts=[types.Part(text=text)]),
                                    finish_reason=types.FinishReason.STOP)],
        usage_metadata=types.GenerateContentResponseUsageMetadata(
            prompt_token_count=total - 50, candidates_token_count=50, total_token_count=total),
        model_version=MODEL + "-001",
    )


def api_error(code):
    return errors.APIError(code, {"error": {"code": code, "message": "scripted", "status": "X"}})


class FakeClient:
    def __init__(self, script):
        self.script = list(script)
        self.calls = []
        self.models = self

    def generate_content(self, *, model, contents, config):
        self.calls.append({"model": model, "config": config, "n_contents": len(contents), "contents": list(contents)})
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


@pytest.fixture
def adapter_factory(store):
    def make(script, stage="research", quota=None):
        job, _ = store.create_job(validate_job_request(job_request()), MODEL)
        _, token = store.claim_next("w1")
        if stage != "research":
            store.update_job(job["job_id"], "w1", token, {"stage": stage})
        gate = BudgetGate(store=store, job=store.get_job(job["job_id"]),
                          persist=lambda ch: store.update_job(job["job_id"], "w1", token, ch),
                          quota=quota or ProjectQuota(model_id=MODEL, rpm=100, tpm=10**6, rpd=1000))
        client = FakeClient(script)
        sleeps = []
        return GeminiAdapter(client, MODEL, gate, prompt_version="v1.2", sleep=sleeps.append), client, sleeps
    return make


@pytest.fixture
def price_tool():
    register_tool("get_price_window", lambda args: {"status": "ok", "tool": "get_price_window",
                                                    "data": {"synthetic_fixture": True, "closes": [100, 101]}})
    yield
    _REGISTRY.pop("get_price_window", None)


def test_tool_call_roundtrip(adapter_factory, store, price_tool):
    adapter, client, _ = adapter_factory([
        fc_response("get_price_window", {"ticker": "2330", "end_at": "2026-09-30T13:30:00+08:00", "sessions": 5}),
        text_response("MOCK 草稿：依工具觀察撰寫"),
    ])
    out = adapter.run_tool_roundtrip("researcher", "研究 2330", "system v1.2")
    assert out["text"].startswith("MOCK")
    assert len(client.calls) == 2 and client.calls[1]["n_contents"] == 3  # user, model fc, function response
    job_id = adapter.job_id
    events = store.list_events(job_id)
    tool_ev = [e for e in events if e["event_type"] == "tool_call"][0]
    assert tool_ev["tool_name"] == "get_price_window" and tool_ev["detail"]["status"] == "ok"
    job = store.get_job(job_id)
    assert job["calls_used"] == 2 and job["tool_calls_used"] == 1 and job["tokens_observed"] == 320


def test_sdk_config_disables_hidden_retries_and_afc(adapter_factory):
    adapter, client, _ = adapter_factory([text_response("ok")])
    adapter.send("reviewer", [types.Content(role="user", parts=[types.Part.from_text(text="x")])], "sys")
    cfg = client.calls[0]["config"]
    assert cfg.automatic_function_calling.disable is True
    assert cfg.max_output_tokens == 1500
    names = {d.name for d in cfg.tools[0].function_declarations}
    assert names == {"read_evidence", "get_financial_snapshot", "get_macro_snapshot", "calculate_metrics"}
    assert client.calls[0]["model"] == MODEL


def test_usage_records_model_and_prompt_version(adapter_factory, store):
    adapter, _, _ = adapter_factory([text_response("ok", total=321)])
    adapter.send("researcher", [types.Content(role="user", parts=[types.Part.from_text(text="x")])], "sys")
    ev = [e for e in store.list_events(adapter.job_id) if e["event_type"] == "model_call"][0]["detail"]
    assert ev["model_id"] == MODEL and ev["model_version"] == MODEL + "-001"
    assert ev["prompt_version"] == "v1.2" and len(ev["prompt_hash"]) == 64
    assert ev["usage"]["total_token_count"] == 321
    usage = store.list_usage(adapter.job_id)[0]
    assert usage["model_id"] == MODEL and usage["prompt_version"] == "v1.2" and usage["total_tokens"] == 321


def test_429_retry_once_then_pause_and_both_sends_counted(adapter_factory, store):
    adapter, client, sleeps = adapter_factory([api_error(429), api_error(429)])
    with pytest.raises(BudgetExceeded) as err:
        adapter.send("researcher", [types.Content(role="user", parts=[types.Part.from_text(text="x")])], "sys")
    assert err.value.job_status == "paused_quota"
    assert len(client.calls) == 2 and len(sleeps) == 1
    assert store.get_job(adapter.job_id)["calls_used"] == 2


def test_retries_share_the_eight_call_cap(adapter_factory, store):
    script = [api_error(503), text_response("ok")] * 4 + [text_response("never")]
    adapter, client, _ = adapter_factory(script, stage="revision")
    content = [types.Content(role="user", parts=[types.Part.from_text(text="x")])]
    for _ in range(4):
        adapter.send("reviewer", content, "sys")
    with pytest.raises(BudgetExceeded) as err:
        adapter.send("reviewer", content, "sys")
    assert err.value.reason == "call_limit"
    assert len(client.calls) == 8 and store.get_job(adapter.job_id)["calls_used"] == 8


def test_non_retryable_error_counts_and_raises(adapter_factory, store):
    adapter, client, sleeps = adapter_factory([api_error(400)])
    with pytest.raises(errors.APIError):
        adapter.send("researcher", [types.Content(role="user", parts=[types.Part.from_text(text="x")])], "sys")
    assert len(client.calls) == 1 and sleeps == [] and store.get_job(adapter.job_id)["calls_used"] == 1


def test_no_fallback_model(store):
    job, _ = store.create_job(validate_job_request(job_request()), MODEL)
    gate = BudgetGate(store=store, job=job, persist=lambda ch: job,
                      quota=ProjectQuota(model_id="verified-model", rpm=1, tpm=1, rpd=1))
    with pytest.raises(ValueError, match="fallback"):
        GeminiAdapter(FakeClient([]), "other-model", gate, prompt_version="v1.2")
    with pytest.raises(ValueError):
        GeminiAdapter(FakeClient([]), "", gate, prompt_version="v1.2")


def test_unknown_quota_sends_nothing(adapter_factory):
    adapter, client, _ = adapter_factory([text_response("never")], quota=ProjectQuota(model_id=MODEL))
    with pytest.raises(BudgetExceeded) as err:
        adapter.send("researcher", [types.Content(role="user", parts=[types.Part.from_text(text="x")])], "sys")
    assert err.value.reason == "quota_unknown" and client.calls == []


def test_reviewer_tool_escalation_is_refused_by_dispatch(adapter_factory, store):
    adapter, _, _ = adapter_factory([
        fc_response("search_evidence", {"ticker": "2330", "query": "q", "cutoff": "2026-09-30T00:00:00+08:00", "limit": 1}),
        text_response("退回 Researcher"),
    ], stage="review")
    adapter.run_tool_roundtrip("reviewer", "覆核", "sys")
    ev = [e for e in store.list_events(adapter.job_id) if e["event_type"] == "tool_call"][0]
    assert ev["detail"]["status"] == "invalid_input" and "無權" in ev["detail"]["reason"]


def test_thinking_level_defaults_to_minimal(adapter_factory):
    adapter, client, _ = adapter_factory([text_response("ok")])
    adapter.send("researcher", [types.Content(role="user", parts=[types.Part.from_text(text="x")])], "sys")
    cfg = client.calls[0]["config"]
    assert cfg.thinking_config.thinking_level == types.ThinkingLevel.MINIMAL
    assert cfg.thinking_config.thinking_budget is None  # Gemini 3 uses levels, not budgets


def test_thinking_level_must_match_model(store):
    job, _ = store.create_job(validate_job_request(job_request()), "gemini-3.8-flash")
    gate = BudgetGate(store=store, job=job, persist=lambda ch: job,
                      quota=ProjectQuota(model_id="gemini-3.8-flash", rpm=1, tpm=1, rpd=1))
    with pytest.raises(ValueError, match="thinking_level"):
        GeminiAdapter(FakeClient([]), "gemini-3.8-flash", gate, prompt_version="v1.2")  # minimal unsupported
    GeminiAdapter(FakeClient([]), "gemini-3.8-flash", gate, prompt_version="v1.2", thinking_level="low")


def test_thought_signature_is_sent_back(adapter_factory, price_tool):
    adapter, client, _ = adapter_factory([
        fc_response("get_price_window", {"ticker": "2330", "end_at": "2026-09-30T13:30:00+08:00", "sessions": 5},
                    signature=b"sig-abc"),
        text_response("done"),
    ])
    adapter.run_tool_roundtrip("researcher", "q", "sys")
    echoed = client.calls[1]["contents"][1]
    assert echoed.role == "model" and echoed.parts[0].thought_signature == b"sig-abc"


def test_reservation_includes_thinking_inside_output_cap(adapter_factory, store):
    adapter, _, _ = adapter_factory([text_response("ok", total=100)])
    adapter.send("researcher", [types.Content(role="user", parts=[types.Part.from_text(text="x")])], "sys")
    usage = store.list_usage(adapter.job_id)[0]
    assert usage["reserved_tokens"] < 3000 + 1500 + 1  # no separate thinking reservation


def test_estimate_counts_tool_declarations(adapter_factory, store):
    # Live check 2026-09-28: send 1 used 597 prompt tokens though the text was ~70 tokens,
    # because declarations are billed as input. The reservation must cover them.
    adapter, _, _ = adapter_factory([text_response("ok")])
    adapter.send("reviewer", [types.Content(role="user", parts=[types.Part.from_text(text="連線測試")])], "sys")
    reserved = store.list_usage(adapter.job_id)[0]["reserved_tokens"]
    import json as _json
    from agents.budget import estimate_tokens
    from agents.tools import ROLE_TOOLS, TOOL_DECLARATIONS
    decl = _json.dumps([t for t in TOOL_DECLARATIONS if t["name"] in ROLE_TOOLS["reviewer"]], ensure_ascii=False)
    assert reserved - 1500 > estimate_tokens(decl)


def test_ledger_uses_adapter_prompt_version(store):
    job, _ = store.create_job(validate_job_request(job_request()), MODEL)
    _, token = store.claim_next("w1")
    gate = BudgetGate(store=store, job=store.get_job(job["job_id"]),
                      persist=lambda ch: store.update_job(job["job_id"], "w1", token, ch),
                      quota=ProjectQuota(model_id=MODEL, rpm=100, tpm=10**6, rpd=1000))
    adapter = GeminiAdapter(FakeClient([text_response("ok")]), MODEL, gate, prompt_version="researcher-v1.2.1")
    adapter.send("researcher", [types.Content(role="user", parts=[types.Part.from_text(text="x")])], "sys")
    assert store.list_usage(job["job_id"])[0]["prompt_version"] == "researcher-v1.2.1"
