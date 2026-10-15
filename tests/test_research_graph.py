"""W04-L Researcher loop and W05-L Reviewer orchestration — MOCK model, real tools/snapshots.

The fake client returns scripted Gemini responses (official SDK types); tools run for real
against B's snapshot data and the dev-case fixtures, so paths differ by what the tools return.
"""

import json

import pytest
from google.genai import types

from agents.budget import ProjectQuota
from agents.contract import validate_job_request
from agents.research_graph import make_research_handler
from agents.worker import run_once
from conftest import job_request
from test_provider_mock import MODEL, FakeClient, fc_response, text_response

QUOTA = ProjectQuota(model_id=MODEL, rpm=1000, tpm=10**7, rpd=100000)
CASE01 = {"ticker": "2330", "cutoff_at": "2026-07-20T17:00:00+08:00", "source_snapshot_id": "snap-dev-case-01",
          "focus": "台積電 2026Q2 先進製程與營收相符"}
CASE13 = {"ticker": "2317", "cutoff_at": "2026-08-10T17:00:00+08:00", "source_snapshot_id": "snap-dev-case-13",
          "focus": "鴻海缺少 2026Q2 資本支出數據"}


def draft(claims, status="draft"):
    return json.dumps({"status": status, "decision_summary": "依讀取的來源撰寫", "claims": claims,
                       "conflicts": [], "limitations": [], "unknowns": []}, ensure_ascii=False)


GOOD_CLAIMS = [{"claim_id": "c1", "kind": "fact", "text": "台積電 2026Q2 合併營收約 6,735 億元（新台幣）",
                "evidence_refs": ["ev-dev-01-official"],
                "facts": [{"metric": "revenue", "value": 6735, "currency": "TWD", "period": "2026Q2",
                           "period_basis": "single_quarter", "source_ref": "ev-dev-01-official"}], "limitations": []},
               {"claim_id": "c2", "kind": "fact", "text": "2026Q2 毛利率為 53.2%", "evidence_refs": ["ev-dev-01-official"],
                "facts": [{"metric": "gross_margin_pct", "value": 53.2, "period": "2026Q2",
                           "source_ref": "ev-dev-01-official"}], "limitations": []}]
PASS = json.dumps({"decision": "pass", "issues": [], "checked_refs": ["ev-dev-01-official"],
                   "checked_metric_ids": [], "decision_summary": "引用與數字已核對"}, ensure_ascii=False)


def run_case(store, case, script, mode="dual"):
    job, _ = store.create_job(validate_job_request(job_request(idempotency_key=case["source_snapshot_id"] + mode,
                                                               mode=mode, **case)), MODEL)
    client = FakeClient(script)
    final = run_once(store, "w1", make_research_handler(client, MODEL, QUOTA, sleep=lambda s: None))
    return final, client, store.list_events(job["job_id"])


def tools_used(events, role=None):
    return [e["tool_name"] for e in events if e["event_type"] == "tool_call" and (role is None or e["role"] == role)]


# ----- W04-L: the researcher loop --------------------------------------------
def test_researcher_path_follows_tool_results_and_review_passes(store):
    final, client, events = run_case(store, CASE01, [
        fc_response("search_evidence", {"ticker": "2330", "query": "營收", "cutoff": CASE01["cutoff_at"], "limit": 3}),
        fc_response("read_evidence", {"evidence_version_id": "ev-dev-01-official"}),
        text_response(draft(GOOD_CLAIMS)),
        text_response(PASS),
    ])
    assert final["status"] == "succeeded" and final["stop_reason"] == "review_pass"
    assert final["publication_status"] == "draft"  # pass ≠ publication
    assert tools_used(events) == ["search_evidence", "read_evidence"]  # not every tool, only what the model chose
    statuses = [e["detail"]["status"] for e in events if e["event_type"] == "tool_call"]
    assert statuses == ["ok", "ok"]  # served from this job's snapshot
    assert final["calls_used"] == 4 and final["review"]["decision"] == "pass"
    calls = [e for e in events if e["event_type"] == "model_call"]
    assert all(c["detail"]["prompt_version"] and c["detail"]["model_id"] == MODEL for c in calls)
    assert [c["detail"]["prompt_version"] for c in calls][-1] == "reviewer-v1.2.0"


def test_different_case_takes_a_different_path_and_stops_insufficient(store):
    final, _, events = run_case(store, CASE13, [
        fc_response("get_financial_snapshot", {"ticker": "2317", "cutoff": CASE13["cutoff_at"]}),
        text_response(draft([{"claim_id": "c1", "kind": "unknown", "text": "2026Q2 CapEx 缺失，無法計算 FCF",
                              "evidence_refs": [], "limitations": ["CapEx null"]}], status="insufficient")),
    ])
    assert tools_used(events) == ["get_financial_snapshot"]
    assert final["status"] == "insufficient_evidence" and final["stop_reason"] == "researcher_insufficient"
    snap = [e for e in events if e["event_type"] == "tool_call"][0]["detail"]
    assert snap["status"] == "ok"


def test_tool_error_is_returned_to_the_model_which_can_choose_again(store):
    final, client, events = run_case(store, CASE01, [
        fc_response("read_evidence", {"evidence_version_id": "ev-not-in-snapshot"}),
        fc_response("read_evidence", {"evidence_version_id": "ev-dev-01-official"}),
        text_response(draft(GOOD_CLAIMS)),
        text_response(PASS),
    ])
    statuses = [e["detail"]["status"] for e in events if e["event_type"] == "tool_call"]
    assert statuses == ["no_data", "ok"]
    sent_back = client.calls[1]["contents"][-1].parts[0].function_response.response
    assert sent_back["status"] == "no_data" and sent_back["obs_id"] == "obs-1"
    assert final["status"] == "succeeded"


def test_fourth_research_call_must_return_a_draft(store):
    q = {"ticker": "2330", "query": "q", "cutoff": CASE01["cutoff_at"], "limit": 1}
    final, client, _ = run_case(store, CASE01, [
        fc_response("search_evidence", q), fc_response("read_evidence", {"evidence_version_id": "ev-dev-01-official"}),
        fc_response("search_evidence", dict(q, query="毛利")), text_response(draft(GOOD_CLAIMS)), text_response(PASS),
    ])
    modes = [c["config"].tool_config for c in client.calls]
    assert modes[:3] == [None, None, None]
    assert modes[3].function_calling_config.mode == types.FunctionCallingConfigMode.NONE
    assert final["status"] == "succeeded" and final["calls_used"] == 5


def test_each_step_is_checkpointed_with_budget(store):
    final, _, events = run_case(store, CASE01, [
        fc_response("read_evidence", {"evidence_version_id": "ev-dev-01-official"}),
        text_response(draft(GOOD_CLAIMS)), text_response(PASS)])
    job = store.get_job(final["job_id"])
    cp = job["checkpoint"]
    assert cp["next"] == "end" and cp["observations"][0]["tool_name"] == "read_evidence"
    assert job["checkpoint_version"] > 5 and job["tool_calls_used"] == 1 and job["tokens_observed"] > 0


def test_invalid_draft_gets_one_format_retry(store):
    final, _, events = run_case(store, CASE01, [
        text_response("我覺得台積電很好"), text_response(draft(GOOD_CLAIMS)), text_response(PASS)])
    assert [e["event_type"] for e in events].count("draft_invalid") == 1
    assert final["status"] == "succeeded"


def test_single_mode_has_no_reviewer(store):
    final, client, events = run_case(store, CASE01, [
        fc_response("read_evidence", {"evidence_version_id": "ev-dev-01-official"}), text_response(draft(GOOD_CLAIMS))],
        mode="single")
    assert final["status"] == "succeeded" and final["stop_reason"] == "draft_without_review"
    assert not [e for e in events if e["role"] == "reviewer"]


# ----- W05-L: reviewer and roles ---------------------------------------------
def test_reviewer_cannot_search_or_fetch_prices(store):
    final, _, events = run_case(store, CASE01, [
        fc_response("read_evidence", {"evidence_version_id": "ev-dev-01-official"}),
        text_response(draft(GOOD_CLAIMS)),
        fc_response("search_evidence", {"ticker": "2330", "query": "q", "cutoff": CASE01["cutoff_at"], "limit": 1}),
        fc_response("get_price_window", {"ticker": "2330", "end_at": CASE01["cutoff_at"], "sessions": 1}),
        text_response(PASS),
    ])
    rev = [e for e in events if e["event_type"] == "tool_call" and e["role"] == "reviewer"]
    assert [e["detail"]["status"] for e in rev] == ["invalid_input", "invalid_input"]
    assert all("無權" in e["detail"]["reason"] for e in rev)


def test_reviewer_cannot_publish(store):
    publish = json.dumps({"decision": "pass", "issues": [], "checked_refs": [], "checked_metric_ids": [],
                          "decision_summary": "ok", "publish": True, "status": "published"})
    final, _, events = run_case(store, CASE01, [
        fc_response("read_evidence", {"evidence_version_id": "ev-dev-01-official"}),
        text_response(draft(GOOD_CLAIMS)), text_response(publish), text_response(publish)])
    assert "review_invalid" in [e["event_type"] for e in events]
    assert final["status"] == "insufficient_evidence" and final["publication_status"] == "draft"


def test_rules_override_model_pass_then_bounded_revision(store):
    fake_ref = [dict(GOOD_CLAIMS[0], evidence_refs=["ev-fake"], facts=[dict(GOOD_CLAIMS[0]["facts"][0], source_ref="ev-fake")])]
    final, client, events = run_case(store, CASE01, [
        fc_response("read_evidence", {"evidence_version_id": "ev-dev-01-official"}),
        text_response(draft(fake_ref)),
        text_response(PASS),                      # model says pass, rules find the fake citation
        text_response(draft(GOOD_CLAIMS)),        # revision with the feedback
        text_response(PASS),
    ])
    reviews = [e["detail"] for e in events if e["event_type"] == "review"]
    assert reviews[0]["model_decision"] == "pass" and reviews[0]["final_decision"] == "revise"
    assert reviews[0]["critical"] == ["c1"]
    assert final["supplement_rounds"] == 1 and final["status"] == "succeeded"
    feedback = client.calls[3]["contents"][-1].parts[0].text
    assert "review_feedback" in feedback and "c1" in feedback


def test_budget_exhaustion_never_skips_review(store):
    q = {"ticker": "2330", "query": "q", "cutoff": CASE01["cutoff_at"], "limit": 1}
    script = [fc_response("read_evidence", {"evidence_version_id": "ev-dev-01-official"}),
              text_response(draft([dict(GOOD_CLAIMS[0], evidence_refs=["ev-fake"])]))]
    script += [text_response(PASS), text_response(draft([dict(GOOD_CLAIMS[0], evidence_refs=["ev-fake"])]))] * 2
    script += [text_response(PASS)] * 3
    final, _, _ = run_case(store, CASE01, script)
    assert final["status"] == "insufficient_evidence" and final["review"]["decision"] != "pass"
    assert final["calls_used"] <= 8 and final["supplement_rounds"] <= 2


def test_crash_mid_run_resumes_from_checkpoint_without_resetting_budget(store, clock):
    job, _ = store.create_job(validate_job_request(job_request(idempotency_key="crash", **CASE01)), MODEL)

    class Crash(Exception):
        pass

    first = FakeClient([fc_response("read_evidence", {"evidence_version_id": "ev-dev-01-official"})])
    orig = first.generate_content

    def crash_after_first(**kw):
        if first.calls:
            raise Crash("worker killed")
        return orig(**kw)

    first.generate_content = crash_after_first
    handler = make_research_handler(first, MODEL, QUOTA, sleep=lambda s: None)
    lease_job, token = store.claim_next("w1")
    from agents.worker import _Lease
    with pytest.raises(Crash):
        handler(_Lease(store, "w1", lease_job, token))
    mid = store.get_job(job["job_id"])
    assert mid["calls_used"] == 2 and mid["checkpoint"]["observations"]

    clock.advance(61)  # lease expires; another worker takes over
    second = FakeClient([text_response(draft(GOOD_CLAIMS)), text_response(PASS)])
    final = run_once(store, "w2", make_research_handler(second, MODEL, QUOTA, sleep=lambda s: None))
    assert final["status"] == "succeeded" and final["calls_used"] == 4  # 2 before crash + 2 after
    assert len(second.calls[0]["contents"]) == 3  # resumed conversation, tool result kept


def test_older_tool_results_are_digested_near_the_input_cap():
    from agents.research_graph import shrink_history
    big = {"obs_id": "obs-1", "status": "ok", "data": {"paragraph": "營收" * 400}}
    contents = [types.Content(role="user", parts=[types.Part.from_function_response(name="read_evidence", response=big)]),
                types.Content(role="user", parts=[types.Part.from_function_response(
                    name="search_evidence", response={"obs_id": "obs-2", "status": "ok", "data": []})])]
    obs = [{"obs_id": "obs-1", "digest": "營收…"}, {"obs_id": "obs-2", "digest": "[]"}]
    assert shrink_history(contents, obs) == 1
    first = contents[0].parts[0].function_response.response
    assert first["digested"] and len(json.dumps(first, ensure_ascii=False)) < 120
    assert contents[1].parts[0].function_response.response["data"] == []  # newest turn kept intact


def test_insufficient_draft_with_wrong_fact_is_flagged_by_rules(store):
    wrong = [dict(GOOD_CLAIMS[0], evidence_refs=["ev-dev-01-official"], text="營收 75000 億元",
                  facts=[dict(GOOD_CLAIMS[0]["facts"][0], value=75000)])]
    final, _, events = run_case(store, CASE01, [
        fc_response("read_evidence", {"evidence_version_id": "ev-dev-01-official"}),
        text_response(draft(wrong, status="insufficient"))])
    assert final["status"] == "insufficient_evidence" and final["calls_used"] == 2  # no model review spent
    check = [e["detail"] for e in events if e["event_type"] == "rules_check"][0]
    assert set(check["critical"]) == {"c1"} and final["review"]["decision"] != "pass"


def test_tool_call_on_text_only_turn_is_not_executed(store):
    q = {"ticker": "2330", "query": "q", "cutoff": CASE01["cutoff_at"], "limit": 1}
    final, client, events = run_case(store, CASE01, [
        fc_response("search_evidence", q), fc_response("read_evidence", {"evidence_version_id": "ev-dev-01-official"}),
        fc_response("search_evidence", dict(q, query="毛利")),
        fc_response("get_macro_snapshot", {"cutoff": CASE01["cutoff_at"], "series_ids": ["CPIAUCSL"]})])  # 4th call
    assert final["status"] == "insufficient_evidence" and final["stop_reason"] == "no_draft_on_final_turn"
    assert final["calls_used"] == 4 and final["tool_calls_used"] == 3  # the refused call was not run
    assert "tools_refused" in [e["event_type"] for e in events]


def test_parallel_calls_beyond_two_are_skipped(store):
    cut = CASE01["cutoff_at"]
    many = types.GenerateContentResponse(
        candidates=[types.Candidate(content=types.Content(role="model", parts=[
            types.Part(function_call=types.FunctionCall(name="get_financial_snapshot", args={"ticker": "2330", "cutoff": cut})),
            types.Part(function_call=types.FunctionCall(name="read_evidence", args={"evidence_version_id": "ev-dev-01-official"})),
            types.Part(function_call=types.FunctionCall(name="get_price_window", args={"ticker": "2330", "end_at": cut, "sessions": 5})),
        ]), finish_reason=types.FinishReason.STOP)],
        usage_metadata=types.GenerateContentResponseUsageMetadata(prompt_token_count=100, candidates_token_count=10,
                                                                  total_token_count=110))
    final, client, events = run_case(store, CASE01, [many, text_response(draft(GOOD_CLAIMS)), text_response(PASS)])
    assert final["tool_calls_used"] == 2 and tools_used(events) == ["get_financial_snapshot", "read_evidence"]
    tool_turn = [c for c in client.calls[1]["contents"] if c.parts and c.parts[0].function_response][-1]
    skipped = tool_turn.parts[2].function_response.response
    assert skipped["status"] == "skipped"
