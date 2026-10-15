"""W05-D 草稿測試（離線、mock）。REPO_ROOT 指向 fintech_project；沒設則需 repo 的測試跳過。"""
import json, os, sys
import pytest
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import reviewer_runner as rr, reviewer_v12 as rv

REPO = os.environ.get("REPO_ROOT", "")
need_repo = pytest.mark.skipif(not (REPO and os.path.isdir(REPO)), reason="沒有 REPO_ROOT")
CUT = "2026-10-01T00:00:00+08:00"
SNAP = {"ticker": "2454", "evidences": [{"evidence_version_id": "ev-a", "title": "公告", "paragraph": "營收 100 億元", "available_at": "2026-08-01T10:00:00+08:00"}],
        "financial_snapshot": {"free_cash_flow": 100.0, "shares_outstanding": 10.0}}


class Stub:
    def __init__(self, table=None): self.calls = []; self.table = table or {}
    def __call__(self, name, args):
        self.calls.append((name, args))
        return self.table.get(name, {"status": "ok", "tool": name, "data": {"result_value": 0}})


def draft(facts, refs=("snap-x",)):
    return {"claims": [{"claim_id": "c1", "kind": "fact", "text": "x", "evidence_refs": list(refs), "facts": facts, "limitations": []}], "conflicts": []}


def run(d, ex, **kw):
    return rr.run_review(d, SNAP, CUT, "snap-x", ex, **kw)


def ids(r): return [(i["claim_id"], i["severity"]) for i in r["review"]["issues"]]


def test_only_allowed_tools_and_review_valid():
    ex = Stub({"calculate_metrics": {"status": "ok", "tool": "calculate_metrics", "data": {"result_value": 26.31}}})
    r = run(draft([{"metric": "pe_ttm", "value": 26.31, "inputs": {"price": 1005, "eps_ttm": 38.2}}]), ex)
    assert rv.validate_tool_use([c[0] for c in ex.calls]) == []
    assert rv.validate_review(r["review"], ["c1"]) == []
    assert r["review"]["decision"] == "pass" and r["risk"] == "low"


def test_reviewer_chooses_tool_from_draft_problem():            # 至少一案自主（規則式）選工具
    ex = Stub()
    run(draft([{"metric": "pe_ttm", "value": 28.5, "inputs": {"price": 1005, "eps_ttm": 38.2}}]), ex)
    assert [c[0] for c in ex.calls] == ["calculate_metrics"] and ex.calls[0][1]["operation"] == "pe_ttm"
    ex2 = Stub()
    run(draft([{"metric": "eps_ttm", "value": 68.0}]), ex2)
    assert [c[0] for c in ex2.calls] == ["get_financial_snapshot"]


def test_recalc_mismatch_is_critical_with_concrete_request():
    ex = Stub({"calculate_metrics": {"status": "ok", "tool": "calculate_metrics", "data": {"result_value": 26.31}}})
    r = run(draft([{"metric": "pe_ttm", "value": 28.5, "inputs": {"price": 1005, "eps_ttm": 38.2}}]), ex)
    assert r["review"]["decision"] == "revise" and ("c1", "critical") in ids(r) and r["risk"] == "high"
    assert any("26.31" in i["required_evidence"] for i in r["review"]["issues"])


def test_missing_eps_snapshot_is_insufficient_not_low_risk():
    ex = Stub({"get_financial_snapshot": {"status": "no_data", "tool": "get_financial_snapshot", "reason": "查無", "data": None}})
    r = run(draft([{"metric": "eps_ttm", "value": 68.0}]), ex)
    assert r["review"]["decision"] == "insufficient" and r["risk"] == "unverified"
    assert rv.validate_review(r["review"], ["c1"]) == []


def test_eps_mismatch_vs_snapshot():
    ex = Stub({"get_financial_snapshot": {"status": "ok", "tool": "get_financial_snapshot", "data": {"metrics": {"eps_ttm": 68.0}}}})
    r = run(draft([{"metric": "eps_ttm", "value": 80.0}]), ex)
    assert r["review"]["decision"] == "revise"


def test_capex_sign_error():
    r = run(draft([{"metric": "fcf", "value": 346.3, "inputs": {"operating_cash_flow": 305.1, "capex": -41.2}}]), Stub())
    assert r["review"]["decision"] == "revise" and "263.9" in r["review"]["issues"][0]["required_evidence"]
    ok = run(draft([{"metric": "fcf", "value": 263.9, "inputs": {"operating_cash_flow": 305.1, "capex": -41.2}}]), Stub())
    assert ok["review"]["decision"] == "pass"


def test_no_budget_means_insufficient_and_keeps_original_values():
    d = draft([{"metric": "pe_ttm", "value": 28.5, "inputs": {"price": 1005, "eps_ttm": 38.2}}])
    ex = Stub(); before = json.dumps(d, sort_keys=True)
    r = run(d, ex, remaining_calls=0)
    assert r["review"]["decision"] == "insufficient" and ex.calls == [] and r["risk"] != "low"
    assert json.dumps(d, sort_keys=True) == before          # 不改原草稿、不補值
    assert r["budget"]["unchecked"]


def test_tool_budget_cap_of_10():
    facts = [{"metric": "pe_ttm", "value": 1, "inputs": {"price": 1, "eps_ttm": 1}} for _ in range(12)]
    ex = Stub({"calculate_metrics": {"status": "ok", "tool": "calculate_metrics", "data": {"result_value": 1}}}); r = run(draft(facts), ex)
    assert len(ex.calls) == 10 and r["budget"]["tools_used"] == 10 and r["review"]["decision"] == "insufficient"


def test_invalid_tool_result_is_reported_not_trusted():
    ex = Stub({"calculate_metrics": {"status": "invalid_input", "tool": "calculate_metrics", "reason": "WACC<=g", "data": None}})
    r = run(draft([{"metric": "dcf_per_share", "value": 100, "inputs": {"free_cash_flows": [1], "wacc": .03, "terminal_growth": .03, "net_debt": 0, "shares_outstanding": 1}}]), ex)
    assert r["review"]["decision"] == "revise"


@need_repo
def test_real_calculator_dcf_wacc_le_g_and_missing_param():
    ex = rr.repo_executor(REPO, CUT)
    bad = run(draft([{"metric": "dcf_per_share", "value": 100, "inputs": {"free_cash_flows": [100, 110], "wacc": .03, "terminal_growth": .03, "net_debt": 0, "shares_outstanding": 10}}]), ex)
    assert bad["review"]["decision"] == "revise" and "WACC" in json.dumps(bad["tool_trace"], ensure_ascii=False)
    miss = run(draft([{"metric": "dcf_per_share", "value": 100, "inputs": {"free_cash_flows": [100, 110], "wacc": .09, "terminal_growth": .02, "net_debt": None, "shares_outstanding": 10}}]), ex)
    assert miss["review"]["decision"] == "revise"            # 缺值不可補 0
    good = run(draft([{"metric": "pe_ttm", "value": 26.31, "inputs": {"price": 1005, "eps_ttm": 38.2}}]), ex)
    assert good["review"]["decision"] == "pass"


@need_repo
def test_real_snapshot_tool_for_2454():
    ex = rr.repo_executor(REPO, CUT)
    r = run(draft([{"metric": "eps_ttm", "value": 68.0}]), ex)
    assert r["tool_trace"][0]["snapshot_value"] == 68.0 and r["review"]["decision"] == "pass"
    r2 = run(draft([{"metric": "eps_ttm", "value": 50.0}]), ex)
    assert r2["review"]["decision"] == "revise"


@need_repo
def test_dev_drafts_through_runner_match_expected():
    entries = json.load(open(os.path.join(HERE, "..", "W04-D", "dev_drafts.json")))["entries"]
    cases = {c["case_id"]: c for c in json.load(open(os.path.join(REPO, "evaluation", "dev-cases.json")))["cases"]}
    fx = json.load(open(os.path.join(REPO, "fixtures", "dev", "case_fixtures.json")))["snapshots"]
    rows = []
    for e in entries:
        c = cases[e["case_id"]]; snap = fx[c["source_snapshot_id"]]
        ex = rr.repo_executor(REPO, c["cutoff_at"], snap)
        r = rr.run_review(e["draft"], snap, c["cutoff_at"], c["source_snapshot_id"], ex, ticker=snap.get("ticker"), observations=e.get("observations"))
        assert rv.validate_review(r["review"], [x["claim_id"] for x in e["draft"]["claims"]]) == [], e["id"]
        rows.append({"id": e["id"], "expected": e["expected_decision"], "got": r["review"]["decision"], "risk": r["risk"], "tools": [t["tool"] for t in r["tool_trace"]]})
        if e["variant"] == "flawed":
            assert r["review"]["decision"] != "pass", e["id"]
    json.dump(rows, open(os.path.join(HERE, "reviewer-run-results.json"), "w"), ensure_ascii=False, indent=1)
