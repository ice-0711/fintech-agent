"""obs-* traced to their sources through the job's own tool record (B, 11/15).

The jobs here are synthetic: the test runs the tools once on the frozen batch-3 snapshot to build a checkpoint in the
same shape the worker saves (agents/research_graph.py), then checks the mapping and the source_traceable rule. The
real batch-3 mapping comes from the lead's job database (scripts/obs_trace_check.py).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agents.snapshot import SnapshotToolbox
from agents.tools import args_hash
from research_ui.obs_trace import SUMMARY_ONLY, UNAVAILABLE, claim_trace, map_observations
from research_ui.report_data import build_report_data, snapshot_context

ROOT = Path(__file__).resolve().parents[1]
BATCH3 = json.loads((ROOT / "research" / "forward-batch-3.json").read_text(encoding="utf-8"))
SNAP = f"snap-fwd3-{BATCH3['snapshot_sha256'][:12]}"
CUT = BATCH3["signal_cutoff_at"]
EV = "ev-fwd3-2317-rev-202610"


def make_job(calls, claims, ticker="2317", checkpoint=True, mutate=None):
    """calls: [(role, tool, args)] run on the batch-3 snapshot → checkpoint observations + model function calls."""
    obs, contents = [], {"researcher": [], "reviewer": []}
    with snapshot_context(SNAP):
        tb = SnapshotToolbox(ticker, SNAP, CUT)
        for i, (role, name, args) in enumerate(calls, 1):
            r = tb(name, args)
            obs.append({"obs_id": f"obs-{i}", "role": role, "tool_name": name, "args_hash": args_hash(args),
                        "status": r.get("status"), "reason": r.get("reason"), "output_hash": f"h{i}",
                        "digest": "", "brief": "", "data": r.get("data")})
            contents[role].append({"role": "model", "parts": [{"function_call": {"name": name, "args": args}}]})
    if mutate:
        mutate(obs)
    job = {"job_id": "job-test", "ticker": ticker, "cutoff_at": CUT, "source_snapshot_id": SNAP,
           "draft": {"claims": claims}}
    if checkpoint:
        job["checkpoint"] = {"observations": obs, "researcher_contents": contents["researcher"],
                             "reviewer_contents": contents["reviewer"]}
    return job


SEARCH = ("researcher", "search_evidence", {"ticker": "2317", "query": "營收", "cutoff": CUT})
READ = ("researcher", "read_evidence", {"evidence_version_id": EV})
FIN = ("researcher", "get_financial_snapshot", {"ticker": "2317", "cutoff": CUT})
PRICE = ("researcher", "get_price_window", {"ticker": "2317", "end_at": CUT, "sessions": 5})


def fact(cid, refs):
    return {"claim_id": cid, "kind": "fact", "text": "…", "evidence_refs": refs}


def traced(job):
    data = build_report_data(job)
    check = next(c for c in data["data_quality"]["checks"] if c["check_id"] == "source_traceable")
    return data, check


def test_each_tool_maps_to_what_it_returned():
    job = make_job([SEARCH, READ, FIN, PRICE], [fact("c1", ["obs-1", "obs-2", "obs-3", "obs-4"])])
    items = map_observations(job)["items"]
    assert items["obs-1"]["targets"] and all(t["seen"] == SUMMARY_ONLY for t in items["obs-1"]["targets"])
    assert items["obs-2"]["targets"] == [{"kind": "evidence", "id": EV, "seen": "讀過全文"}]
    fin = items["obs-3"]["targets"][0]
    assert fin["kind"] == "financial_snapshot" and fin["periods"] == ["2025Q3", "2025Q4", "2026Q1", "2026Q2"]
    assert items["obs-4"]["targets"][0]["kind"] == "price" and len(items["obs-4"]["targets"][0]["trade_dates"]) == 5
    assert items["obs-2"]["args"] == READ[2]  # arguments recovered from the checkpoint by args_hash


def test_report_with_traced_obs_passes_and_freezes_the_mapping():
    job = make_job([SEARCH, READ, FIN], [fact("c1", ["obs-2"]), fact("c2", ["obs-3"]),
                                         {"claim_id": "c3", "kind": "unknown", "evidence_refs": []}])
    data, check = traced(job)
    assert check["result"] == "pass", check
    src = {s["id"]: s for s in data["sources"]}
    assert src["obs-2"]["resolved"] and src["obs-2"]["targets"][0]["id"] == EV
    assert src["obs-2"]["targets"][0]["hash_match"] is True and src["obs-2"]["targets"][0]["cutoff_ok"] is True
    assert data["obs_map"]["status"] == "ok" and set(data["obs_map"]["items"]) == {"obs-1", "obs-2", "obs-3"}


def test_calculation_follows_inputs_found_in_earlier_results_else_unverified():
    def pe(price, eps):
        return ("researcher", "calculate_metrics",
                {"operation": "pe_ttm", "values": {"price": price, "eps_ttm": eps}, "evidence_refs": ["obs-1", "obs-2"]})

    with snapshot_context(SNAP):
        tb = SnapshotToolbox("2317", SNAP, CUT)
        eps = tb(*FIN[1:])["data"]["metrics"]["eps_ttm"]
        close = tb(*PRICE[1:])["data"]["closes"][-1]["close_price"]
    job = make_job([FIN, PRICE, pe(close, eps), pe(close, 99.99)], [fact("c1", ["obs-3"])])
    items = map_observations(job)["items"]
    assert items["obs-3"]["tool_status"] == "ok" and items["obs-3"]["via"] == ["obs-2", "obs-1"]
    assert [i["name"] for i in items["obs-3"]["inputs"]] == ["price", "eps_ttm"]
    assert [t["kind"] for t in items["obs-3"]["targets"]] == ["price", "financial_snapshot"]
    assert items["obs-4"]["tool_status"] == "ok" and items["obs-4"]["targets"] == []
    assert "輸入未驗證" in items["obs-4"]["note"] and "99.99" in items["obs-4"]["note"]
    _, check = traced(job)
    assert check["result"] == "pass", check
    # 99.99 is in no earlier result: a claim citing that calculation is not traced
    job["draft"]["claims"] = [fact("c1", ["obs-4"])]
    _, check = traced(job)
    assert check["result"] == "missing" and "obs-4" in check["detail"]


def test_obs_that_maps_to_nothing_is_missing_not_undeterminable():
    def fake_hit(obs):
        obs[0]["data"] = [{"evidence_version_id": "ev-not-in-this-snapshot"}]

    job = make_job([SEARCH], [fact("c1", ["obs-1"])], mutate=fake_hit)
    _, check = traced(job)
    assert check["result"] == "missing" and "obs-1 對不到來源" in check["detail"]
    job2 = make_job([SEARCH], [fact("c1", ["obs-9"])])
    _, check2 = traced(job2)
    assert check2["result"] == "missing" and "這個 job 沒有這個工具觀察" in check2["detail"]


def test_failed_tool_call_is_not_a_source():
    job = make_job([("researcher", "read_evidence", {"evidence_version_id": "ev-nope"})], [fact("c1", ["obs-1"])])
    _, check = traced(job)
    assert check["result"] == "missing" and "工具沒有成功" in check["detail"]


def test_only_a_lost_job_record_is_undeterminable():
    job = make_job([READ], [fact("c1", ["obs-1"])], checkpoint=False)
    data, check = traced(job)
    assert check["result"] == "not_run" and UNAVAILABLE in check["detail"]
    assert data["sources"][0]["resolved"] is False and data["sources"][0]["reason"] == UNAVAILABLE


def test_fact_claim_without_any_reference_is_missing_inference_and_unknown_are_not():
    claims = [fact("c1", [EV]), {"claim_id": "c2", "kind": "inference", "evidence_refs": []},
              {"claim_id": "c3", "kind": "unknown", "evidence_refs": []}]
    assert claim_trace(claims, {"status": "ok", "items": {}}, lambda i: _read(i)) == ("pass", "")
    claims.append(fact("c4", []))
    result, detail = claim_trace(claims, {"status": "ok", "items": {}}, lambda i: _read(i))
    assert result == "missing" and "事實主張 c4 沒有引用來源" in detail


def _read(ev_id):
    with snapshot_context(SNAP):
        from agents import tools_impl
        return tools_impl.read_evidence(ev_id)


def test_direct_ev_citations_keep_the_old_wording():
    result, detail = claim_trace([fact("c1", ["ev-missing-x"])], {"status": "ok", "items": {}}, _read)
    assert (result, detail) == ("missing", "引用的片段不在快照中：ev-missing-x")


@pytest.mark.parametrize("batch,ticker", [(1, "2317"), (2, "2330")])
def test_published_agent_v1_reports_keep_their_result(batch, ticker):
    """The two published reports cite ev- directly: same sources and same data-quality result as published."""
    d = json.loads((ROOT / "research" / f"forward-batch-{batch}-reports.json").read_text(encoding="utf-8"))
    r = next(x for x in d["reports"] if x["ticker"] == ticker)
    data = build_report_data({"ticker": ticker, "cutoff_at": d["signal_cutoff_at"],
                              "source_snapshot_id": f"snap-fwd{batch}-{d['snapshot_sha256'][:12]}", "draft": r["draft"]})
    assert data["data_quality"]["level"] == "low"
    assert all(c["result"] == "pass" for c in data["data_quality"]["checks"])
    assert all(s["resolved"] and s["hash_match"] for s in data["sources"])
    assert "obs_map" not in data  # nothing cited obs-*: the frozen JSON gets no new key


def test_drawer_shows_the_frozen_mapping_and_opens_the_fragments_it_found(tmp_path, clock):
    from test_research_ui import make_app

    app = make_app(tmp_path, clock)
    store = app.extensions["report_store"]
    job = make_job([SEARCH, READ, FIN], [fact("c1", ["obs-2"]), fact("c2", ["obs-1"])])
    job.update(job_id="job-obs-drawer", status="succeeded", review={"decision": "pass"}, mode="dual",
               question_version="q", model_id="m")
    v = store.create_version(job, [])
    store.approve(v["report_version_id"], v["report_hash"], "test")
    store.publish(v["report_version_id"])
    client = app.test_client()
    rv = v["report_version_id"]
    report = client.get(f"/api/ui/reports/{rv}").get_json()["report"]
    assert [e["exists"] for c in report["claims"] for e in c["evidence"]] == [True, True]
    obs = client.get(f"/api/ui/evidence/obs-2?report={rv}").get_json()["evidence"]
    assert obs["kind"] == "observation" and obs["tool"] == "read_evidence" and obs["targets"][0]["id"] == EV
    found = client.get(f"/api/ui/evidence/obs-1?report={rv}").get_json()["evidence"]["targets"]
    assert found and all(t["seen"] == SUMMARY_ONLY for t in found)
    # a fragment the search returned opens in the drawer too (it is part of the approved JSON)
    nested = client.get(f"/api/ui/evidence/{found[0]['id']}?report={rv}").get_json()
    assert nested["ok"] and nested["evidence"]["hash_match"] is True



def test_each_calculation_input_records_the_field_and_the_row_date():
    """B, 11/16: batch-3 2317's P/E used 242, the 11/11 close, not the latest trading day's (11/13, 241)."""
    with snapshot_context(SNAP):
        tb = SnapshotToolbox("2317", SNAP, CUT)
        closes = {c["trade_date"][:10]: c["close_price"] for c in tb(*PRICE[1:])["data"]["closes"]}
        eps = tb(*FIN[1:])["data"]["metrics"]["eps_ttm"]
    assert closes["2026-11-11"] == 242.0 and closes["2026-11-13"] == 241.0
    calc = ("researcher", "calculate_metrics",
            {"operation": "pe_ttm", "values": {"price": 242.0, "eps_ttm": eps}, "evidence_refs": ["obs-1", "obs-2"]})
    job = make_job([PRICE, FIN, calc], [fact("c1", ["obs-3"])])
    entry = map_observations(job)["items"]["obs-3"]
    price = next(i for i in entry["inputs"] if i["name"] == "price")
    assert price["match"]["obs_id"] == "obs-1" and price["match"]["tool"] == "get_price_window"
    assert price["match"]["field"].startswith("closes[") and price["match"]["field"].endswith(".close_price")
    assert price["match"]["date"].startswith("2026-11-11") and price["match"]["date_key"] == "trade_date"
    assert price["match"]["in_text"] is False
    assert price["weak"] is False
    eps_in = next(i for i in entry["inputs"] if i["name"] == "eps_ttm")
    assert eps_in["match"]["obs_id"] == "obs-2" and eps_in["match"]["field"] == "metrics.eps_ttm"
    assert (eps_in["match"]["date_key"], eps_in["match"]["date"]) == ("latest_period", "2026Q2")
    # the mapping is frozen into the report: the drawer and PDF can show the date
    data = build_report_data(job)
    src = next(s for s in data["sources"] if s["id"] == "obs-3")
    assert src["inputs"][0]["match"]["date"].startswith("2026-11-11")


def test_small_integers_and_years_are_flagged_and_number_fields_win_over_text():
    def plant(obs):  # one result with the number only inside text, a later one with it as a number field
        obs[0]["data"] = {"paragraph": "2026 年第 4 季", "available_at": "2026-11-01T00:00:00+08:00"}
        obs[1]["data"] = {"rows": [{"period": "2026Q4", "count": 4}]}

    calc = ("researcher", "calculate_metrics",
            {"operation": "growth_rate", "values": {"current": 2026, "previous": 4}, "evidence_refs": ["obs-1"]})
    job = make_job([READ, FIN, calc], [fact("c1", ["obs-3"])], mutate=plant)
    inputs = {i["name"]: i for i in map_observations(job)["items"]["obs-3"]["inputs"]}
    assert inputs["current"]["weak"] and inputs["previous"]["weak"]
    assert inputs["current"]["match"] == {"obs_id": "obs-1", "tool": "read_evidence", "field": "paragraph",
                                          "date": "2026-11-01T00:00:00+08:00", "date_key": "available_at",
                                          "in_text": True}
    prev = inputs["previous"]
    assert prev["match"]["obs_id"] == "obs-2" and prev["match"]["field"] == "rows[0].count"
    # also inside "第 4 季" and inside the period label "2026Q4": shown as 2 other places
    assert prev["match"]["date"] == "2026Q4" and prev["match"]["in_text"] is False and prev["other_matches"] == 2
