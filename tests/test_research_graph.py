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

@pytest.fixture(autouse=True)
def frozen_case_fixtures(monkeypatch):
    """Agent tests use their own frozen snapshots, independent of B's evolving fixtures/dev."""
    from pathlib import Path
    import agents.snapshot as snapshot
    monkeypatch.setattr(snapshot, "DEV_FIXTURES", Path(__file__).parent / "fixtures" / "agent_case_fixtures.json")


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
    assert all(c["config"].tools for c in client.calls[:3])
    last = client.calls[3]
    assert last["config"].tools is None  # no tools declared: the model can only answer in text
    assert len(last["contents"]) == 1 and "不能再呼叫工具" in last["contents"][0].parts[0].text
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
    assert "calls_skipped" in [e["event_type"] for e in events]


CASE15 = {"ticker": "2454", "cutoff_at": "2026-08-05T17:00:00+08:00", "source_snapshot_id": "snap-dev-case-15"}
CASE26 = {"ticker": "2317", "cutoff_at": "2026-08-12T17:00:00+08:00", "source_snapshot_id": "snap-dev-case-26"}


def test_unreadable_source_is_reported_not_crashing(store):
    final, client, events = run_case(store, CASE15, [
        fc_response("search_evidence", {"ticker": "2454", "query": "法說", "cutoff": CASE15["cutoff_at"], "limit": 3}),
        fc_response("read_evidence", {"evidence_version_id": "ev-dev-15-unreadable"}),
        text_response(draft([{"claim_id": "c1", "kind": "unknown", "text": "法說會簡報正文不可讀", "evidence_refs": [],
                              "limitations": ["來源不可讀"]}], status="insufficient"))])
    assert [e["detail"]["status"] for e in events if e["event_type"] == "tool_call"] == ["ok", "unreadable"]
    assert final["status"] == "insufficient_evidence"


def test_simulated_tool_timeout_counts_active_time_and_job_continues(store):
    final, client, events = run_case(store, CASE26, [
        fc_response("read_evidence", {"evidence_version_id": "ev-2317-2026q2-consolidated"}),
        text_response(draft([{"claim_id": "c1", "kind": "unknown", "text": "read_evidence 逾時，未取得來源",
                              "evidence_refs": [], "limitations": ["工具逾時"]}], status="insufficient"))])
    tool = [e["detail"] for e in events if e["event_type"] == "tool_call"][0]
    assert tool["status"] == "tool_error" and "逾時" in tool["reason"]
    assert final["active_seconds"] >= 15 and final["status"] == "insufficient_evidence"


# ----- W06-L: cancel, no re-run of finished jobs ---------------------------------
def test_cancel_queued_job_is_never_run(store):
    job, _ = store.create_job(validate_job_request(job_request(**CASE01)), MODEL)
    assert store.request_cancel(job["job_id"])["status"] == "cancelled"
    assert run_once(store, "w1", make_research_handler(FakeClient([]), MODEL, QUOTA)) is None


def test_cancel_running_job_stops_before_next_step_and_keeps_budget(store):
    job, _ = store.create_job(validate_job_request(job_request(**CASE01)), MODEL)
    client = FakeClient([fc_response("read_evidence", {"evidence_version_id": "ev-dev-01-official"}),
                         text_response(draft(GOOD_CLAIMS))])
    orig = client.generate_content

    def cancel_after_first(**kw):
        resp = orig(**kw)
        store.request_cancel(job["job_id"])  # user cancels while the first call is in flight
        return resp

    client.generate_content = cancel_after_first
    final = run_once(store, "w1", make_research_handler(client, MODEL, QUOTA))
    assert final["status"] == "cancelled" and final["stop_reason"] == "cancel_requested"
    assert final["calls_used"] == 1 and final["tool_calls_used"] == 1 and len(client.calls) == 1


def test_finished_job_is_not_rerun_or_republished(store):
    final, _, _ = run_case(store, CASE01, [
        fc_response("read_evidence", {"evidence_version_id": "ev-dev-01-official"}),
        text_response(draft(GOOD_CLAIMS)), text_response(PASS)])
    assert final["status"] == "succeeded" and final["publication_status"] == "draft"
    again, created = store.create_job(validate_job_request(job_request(
        idempotency_key=CASE01["source_snapshot_id"] + "dual", **CASE01)), MODEL)
    assert not created and again["status"] == "succeeded"
    assert run_once(store, "w2", make_research_handler(FakeClient([]), MODEL, QUOTA)) is None
    assert store.request_cancel(final["job_id"])["status"] == "succeeded"  # terminal stays terminal


def test_cancel_api_requires_token(tmp_path, monkeypatch):
    from flask import Flask
    from agents.api import bp
    monkeypatch.setenv("RESEARCH_DB_PATH", str(tmp_path / "api.sqlite3"))
    app = Flask(__name__)
    app.config["RESEARCH_API_TOKEN"] = "t"
    app.register_blueprint(bp)
    c = app.test_client()
    job_id = c.post("/api/research/jobs", json=job_request(), headers={"Authorization": "Bearer t"}).get_json()["job"]["job_id"]
    assert c.post(f"/api/research/jobs/{job_id}/cancel").status_code == 401
    r = c.post(f"/api/research/jobs/{job_id}/cancel", headers={"Authorization": "Bearer t"})
    assert r.status_code == 200 and r.get_json()["job"]["status"] == "cancelled"


def test_format_retry_never_takes_the_review_call(store):
    q = {"ticker": "2330", "query": "q", "cutoff": CASE01["cutoff_at"], "limit": 1}
    final, client, events = run_case(store, CASE01, [
        fc_response("search_evidence", q), fc_response("read_evidence", {"evidence_version_id": "ev-dev-01-official"}),
        fc_response("search_evidence", dict(q, query="毛利")), text_response("not json")])
    assert final["calls_used"] == 4 and final["stop_reason"] == "researcher_insufficient"
    assert "draft_invalid" in [e["event_type"] for e in events]



def test_reviewer_final_turn_has_no_tools_so_a_good_draft_gets_a_decision(store):
    """10/23 live CASE-01: flash-lite asked for tools on the reviewer's text-only turn; now no tools are declared."""
    rd = {"evidence_version_id": "ev-dev-01-official"}
    final, client, events = run_case(store, CASE01, [
        fc_response("read_evidence", rd), text_response(draft(GOOD_CLAIMS)),
        fc_response("read_evidence", rd), fc_response("get_financial_snapshot", {"ticker": "2330", "cutoff": CASE01["cutoff_at"]}),
        text_response(PASS)])  # the reviewer's forced last turn: no tools declared, it answers
    reviewer_calls = [c for c in client.calls if c["config"].system_instruction.startswith("你是多智能體投資分析系統的 Reviewer")]
    assert reviewer_calls[-1]["config"].tools is None
    assert final["status"] == "succeeded" and final["calls_used"] <= 8


# ----- W07-L: workflow (fixed-pipeline) baseline ---------------------------------
def test_workflow_runs_fixed_tools_then_one_send_without_review(store):
    final, client, events = run_case(store, CASE01, [text_response(draft(GOOD_CLAIMS))], mode="workflow")
    assert final["status"] == "succeeded" and final["stop_reason"] == "workflow_draft_without_review"
    assert final["calls_used"] == 1 and final["review"] is None and final["publication_status"] == "draft"
    tools = tools_used(events)
    assert tools[0] == "search_evidence" and tools[-3:] == ["get_financial_snapshot", "get_macro_snapshot", "get_price_window"]
    assert set(tools[1:-3]) <= {"read_evidence"} and 1 <= len(tools[1:-3]) <= 5  # the snapshot's first five sources
    assert final["tool_calls_used"] == len(tools) <= 10
    assert not any(e["role"] == "reviewer" for e in events)


def test_workflow_same_tool_path_for_every_job(store):
    paths = []
    for i in range(2):
        case = dict(CASE01, focus=f"不同焦點 {i}")
        job, _ = store.create_job(validate_job_request(job_request(idempotency_key=f"wf-{i}", mode="workflow", **case)), MODEL)
        run_once(store, "w1", make_research_handler(FakeClient([text_response(draft([], status="insufficient"))]),
                                                    MODEL, QUOTA, sleep=lambda s: None))
        paths.append(tools_used(store.list_events(job["job_id"])))
    assert paths[0] == paths[1]  # code, not the model, chooses the tools


def test_workflow_tool_request_is_not_executed(store):
    final, client, events = run_case(store, CASE01, [
        fc_response("search_evidence", {"ticker": "2330", "query": "x", "cutoff": CASE01["cutoff_at"], "limit": 1})],
        mode="workflow")
    assert final["status"] == "insufficient_evidence" and final["stop_reason"] == "workflow_invalid_draft"
    assert final["calls_used"] == 1


def test_overlong_review_summary_is_trimmed_not_discarded(store):
    long_pass = json.dumps({"decision": "pass", "issues": [], "checked_refs": ["ev-dev-01-official"],
                            "checked_metric_ids": [], "decision_summary": "引用與數字已逐項核對。" * 20}, ensure_ascii=False)
    final, client, events = run_case(store, CASE01, [
        fc_response("search_evidence", {"ticker": "2330", "query": "營收", "cutoff": CASE01["cutoff_at"], "limit": 3}),
        fc_response("read_evidence", {"evidence_version_id": "ev-dev-01-official"}),
        text_response(draft(GOOD_CLAIMS)),
        text_response(long_pass),
    ])
    assert final["stop_reason"] == "review_pass" and final["calls_used"] == 4  # no retry spent on the summary
    assert len(final["review"]["decision_summary"]) <= 120
    assert any(e["event_type"] == "review_normalized" for e in events)
