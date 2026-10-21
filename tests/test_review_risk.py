"""W05-A: review panel data, draft versions, valuation-gap status, data-quality risk. Offline, 0 LLM."""

from __future__ import annotations

import pytest

from research_ui.review_view import diff_drafts, review_view
from research_ui.risk import Check, data_quality_risk, valuation_status
from test_research_ui import create, make_app, run_until_done

FULL = {"free_cash_flows": [1] * 5, "wacc": 0.09, "terminal_growth": 0.03, "net_debt": 0, "shares_outstanding": 1}


# ----- valuation gap ±15% ----------------------------------------------------------------
@pytest.mark.parametrize("dcf,price,status", [
    (115.0, 100.0, "below_model"),     # exactly +15 % → 市價低於模型估值
    (114.99, 100.0, "near_model"),
    (85.0, 100.0, "above_model"),      # exactly −15 % → 市價高於模型估值
    (85.01, 100.0, "near_model"),
    (100.0, 100.0, "near_model"),
    (300.0, 100.0, "below_model"),
    (20.0, 100.0, "above_model"),
])
def test_valuation_thresholds(dcf, price, status):
    out = valuation_status(dcf, price, FULL)
    assert out["status"] == status and out["gap"] == round((dcf - price) / price, 4)


@pytest.mark.parametrize("key,name", [("wacc", "WACC"), ("terminal_growth", "g"), ("net_debt", "淨負債"),
                                      ("shares_outstanding", "流通股數"), ("free_cash_flows", "FCF")])
def test_missing_dcf_parameter_is_undeterminable_never_zero(key, name):
    out = valuation_status(120.0, 100.0, {**FULL, key: None})
    assert out["status"] == "undeterminable" and out["gap"] is None and name in out["reason"]


def test_no_price_or_nonpositive_dcf_is_undeterminable():
    assert valuation_status(120.0, None, FULL)["status"] == "undeterminable"
    assert valuation_status(120.0, 0, FULL)["status"] == "undeterminable"
    neg = valuation_status(-64.43, 200.0, FULL)
    assert neg["status"] == "undeterminable" and "非正" in neg["reason"]


# ----- data-quality risk ---------------------------------------------------------------
def ok(i, key=True):
    return Check(f"k{i}", f"項目{i}", key, "pass")


def test_low_only_when_every_check_passed():
    assert data_quality_risk([ok(1), ok(2), ok(3, key=False)]).level == "low"


@pytest.mark.parametrize("bad,level", [
    (Check("p", "同日收盤價", True, "missing"), "high"),
    (Check("c", "工具值與快照", True, "conflict"), "high"),
    (Check("c2", "次要矛盾", False, "conflict"), "high"),     # any unresolved conflict
    (Check("t", "可得時間", True, "time_unknown"), "high"),
    (Check("k", "關鍵未檢查", True, "not_run"), "high"),
    (Check("s", "財報新鮮度", False, "stale"), "medium"),
    (Check("b", "BVPS", False, "missing"), "medium"),
])
def test_risk_levels(bad, level):
    r = data_quality_risk([ok(1), bad])
    assert r.level == level and r.reasons and bad.label in r.reasons[0]


def test_high_beats_medium_and_nothing_run_is_not_low():
    assert data_quality_risk([Check("s", "新鮮度", False, "stale"), Check("p", "價格", True, "missing")]).level == "high"
    assert data_quality_risk([]).level == "unassessed"
    assert data_quality_risk([Check("x", "x", True, "not_run")]).level == "unassessed"  # nothing actually ran
    assert "不代表股價風險低" in data_quality_risk([ok(1)]).as_dict()["footnote"]


def test_unknown_result_rejected():
    with pytest.raises(ValueError):
        data_quality_risk([Check("x", "x", True, "fine")])


def test_published_list_derives_valuation_and_risk(tmp_path, clock):
    ui = make_app(tmp_path, clock).test_client()
    rows = {r["ticker"]: r for r in ui.get("/api/ui/published").get_json()["reports"]}
    assert rows["2317"]["valuation"]["status"] == "undeterminable"  # TTM FCF is negative
    for r in rows.values():
        assert r["data_quality"]["level"] in ("high", "medium", "low", "unassessed")
        assert r["valuation"]["label"]
        assert "不代表股價風險低" in r["data_quality"]["footnote"]


# ----- draft versions and review rounds ------------------------------------------------
def test_diff_drafts_reports_each_claim():
    old = [{"claim_id": "c1", "kind": "fact", "text": "a", "evidence_refs": ["e"], "limitations": []},
           {"claim_id": "c2", "kind": "fact", "text": "b", "evidence_refs": [], "limitations": []}]
    new = [{"claim_id": "c1", "kind": "fact", "text": "a", "evidence_refs": ["e"], "limitations": []},
           {"claim_id": "c2", "kind": "fact", "text": "B", "evidence_refs": [], "limitations": []},
           {"claim_id": "c3", "kind": "unknown", "text": "c", "evidence_refs": [], "limitations": []}]
    by = {d["claim_id"]: d for d in diff_drafts(old, new)}
    assert by["c1"]["change"] == "unchanged" and by["c3"]["change"] == "added"
    assert by["c2"]["change"] == "changed" and by["c2"]["fields"] == ["text"] and by["c2"]["before"]["text"] == "b"
    assert diff_drafts(new, old)[-1]["change"] == "removed"


@pytest.fixture
def ui(tmp_path, clock):
    return make_app(tmp_path, clock).test_client()


def test_revise_then_pass_keeps_every_draft_and_points_at_the_rejected_claim(ui, clock):
    job_id = create(ui, scenario="revise_then_pass", idempotency_key="k-rev").get_json()["job"]["job_id"]
    body = run_until_done(ui, clock, job_id, polls=30)
    job, view = body["job"], body["job"]["review_view"]
    assert job["status"] == "succeeded" and job["supplement_rounds"] == 1 and job["publication_status"] == "draft"
    assert [r["final_decision"] for r in view["rounds"]] == ["revise", "pass"]
    first = view["rounds"][0]
    critical = [i for i in first["issues"] if i["severity"] == "critical"]
    assert [i["claim_id"] for i in critical] == ["c2"] and critical[0]["required_evidence"]
    assert critical[0]["source"] == "both" and any(i["severity"] == "minor" for i in first["issues"])
    assert view["drafts_complete"] is True and [d["version"] for d in view["drafts"]] == [1, 2]
    v1, v2 = view["drafts"]
    assert "測試案例" in next(c for c in v1["claims"] if c["claim_id"] == "c2")["text"]  # old draft kept
    diff = {d["claim_id"]: d["change"] for d in v2["diff"]}
    assert diff == {"c1": "unchanged", "c2": "changed", "c3": "unchanged"}


def test_revised_numbers_come_from_the_tools(ui, clock):
    from agents import tools_impl

    m = tools_impl.get_financial_snapshot("2454", "2026-09-30T17:30:00+08:00")["data"]["metrics"]
    job_id = create(ui, scenario="revise_then_pass", idempotency_key="k-rev2").get_json()["job"]["job_id"]
    view = run_until_done(ui, clock, job_id, polls=30)["job"]["review_view"]
    v1, v2 = view["drafts"]
    c2_v1 = next(c for c in v1["claims"] if c["claim_id"] == "c2")["text"]
    c2_v2 = next(c for c in v2["claims"] if c["claim_id"] == "c2")["text"]
    assert str(m["eps_single_q"]) in c2_v1 and str(m["eps_ttm"]) in c2_v2


@pytest.mark.parametrize("scenario,ticker,phrase", [
    ("insufficient_evidence", "2317", "資料不足"),
    ("paused_quota", "2330", "覆核前停止"),
])
def test_empty_review_states_say_why(ui, clock, scenario, ticker, phrase):
    job_id = create(ui, ticker=ticker, scenario=scenario, idempotency_key=f"k-e-{scenario}").get_json()["job"]["job_id"]
    view = run_until_done(ui, clock, job_id)["job"]["review_view"]
    assert view["rounds"] == [] and phrase in view["empty_reason"]


def test_single_mode_has_no_reviewer():
    view = review_view({"mode": "single", "status": "succeeded", "draft": {"claims": []}})
    assert "single 模式沒有 Reviewer" in view["empty_reason"]


def test_approval_is_refused_without_login(ui):
    resp = ui.post("/api/ui/jobs/anything/approve")
    assert resp.status_code == 403 and resp.get_json()["error"] == "approval_requires_login"
    assert ui.get("/api/ui/session").get_json() == {"ok": True, "admin": False}


def test_logged_in_lead_still_cannot_publish_before_w07(tmp_path, clock):
    app = make_app(tmp_path, clock)
    app.secret_key = "test"
    client = app.test_client()
    with client.session_transaction() as sess:
        sess["admin"] = True
    resp = client.post("/api/ui/jobs/anything/approve")
    assert resp.status_code == 409 and resp.get_json()["error"] == "publication_not_available"
    assert client.get("/api/ui/session").get_json()["admin"] is True


# ----- REPLAY of recorded live runs -----------------------------------------------------
def test_replays_list_only_live_runs_and_label_them(ui):
    body = ui.get("/api/ui/replays").get_json()
    assert body["label"] == "REPLAY" and body["replays"]
    assert all(r["model_id"] and r["commit"] and r["generated_at"] for r in body["replays"])


def test_replay_of_case04_shows_recorded_reviewer_issues(ui):
    r = ui.get("/api/ui/replays/researcher-v12-traces:CASE-04").get_json()
    assert r["label"] == "REPLAY" and r["job"]["status"] == "insufficient_evidence"
    rnd = r["review_view"]["rounds"][-1]
    assert rnd["final_decision"] == "insufficient"
    assert {"c1", "c2", "c3"} <= {i["claim_id"] for i in rnd["issues"]}
    assert all(i["required_evidence"] for i in rnd["issues"])
    assert r["review_view"]["drafts_complete"] is False and "最後一版草稿" in r["limits_of_record"]
    assert [e["tool_name"] for e in r["events"] if e["event_type"] == "tool_call"][:2] == ["get_financial_snapshot", "get_price_window"]


def test_unknown_replay_is_404(ui):
    assert ui.get("/api/ui/replays/nope:CASE-99").status_code == 404


# ----- W06: interruption recovery ---------------------------------------------------------
def test_worker_interruption_resumes_without_resetting_budget(ui, clock):
    job_id = create(ui, scenario="revise_then_pass", idempotency_key="k-crash").get_json()["job"]["job_id"]
    for _ in range(4):  # a few steps, then the page/worker goes quiet for longer than the 60 s lease
        before = ui.get(f"/api/ui/jobs/{job_id}").get_json()["job"]
        clock.advance(1.5)
    clock.advance(61)
    after = run_until_done(ui, clock, job_id, polls=30)
    assert any(e["event_type"] == "lease_recovered" for e in after["events"])
    assert after["job"]["calls_used"] >= before["calls_used"] and after["job"]["status"] == "succeeded"
    assert [d["version"] for d in after["job"]["review_view"]["drafts"]] == [1, 2]  # no step repeated
