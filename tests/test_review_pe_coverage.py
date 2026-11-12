"""11/12（決策 28）：P/E 的期間是股價日期，季度改看所用的 TTM EPS；查到了卻沒寫進草稿只列 minor、不擋。合成資料。"""
import pytest

from agents.review_checks import check_draft

CUTOFF = "2026-09-30T09:30:00+00:00"


def pe_draft(eps_period="2025Q3,2025Q4,2026Q1,2026Q2", pe_period="2026-09-30", with_eps=True):
    facts = [{"metric": "pe_ttm", "value": 28.74, "currency": "TWD", "period": pe_period, "period_basis": "ttm", "source_ref": "snap"}]
    claims = [{"claim_id": "c2", "kind": "fact", "text": "P/E 28.74", "evidence_refs": ["snap"], "facts": facts}]
    if with_eps:
        claims.insert(0, {"claim_id": "c1", "kind": "fact", "text": "TTM EPS 86.28", "evidence_refs": ["snap"],
                          "facts": [{"metric": "eps_ttm", "value": 86.28, "currency": "TWD", "period": eps_period,
                                     "period_basis": "ttm", "source_ref": "snap"}]})
    return {"status": "draft", "claims": claims, "valuation_scenarios": ["x"], "macro_observations": ["y"]}


def snap(ttm_periods=None):
    fin = {"ttm_periods": ttm_periods} if ttm_periods else {}
    return {"ticker": "2330", "evidences": [], "tool_numbers": [86.28, 28.74], "financial_snapshot": fin}


def ttm_flags(d, s):
    return [i["claim_id"] for i in check_draft(d, s, CUTOFF, "snap")["review"]["issues"] if "TTM 需要四個連續單季" in i["reason"]]


def test_pe_dated_by_price_uses_draft_eps_quarters():
    assert ttm_flags(pe_draft(), snap()) == []


def test_pe_uses_snapshot_quarters_when_draft_has_no_eps_ttm():
    assert ttm_flags(pe_draft(with_eps=False), snap(["2025Q3", "2025Q4", "2026Q1", "2026Q2"])) == []


def test_pe_still_blocked_when_eps_quarters_not_consecutive():
    assert ttm_flags(pe_draft(eps_period="2025Q2,2025Q4,2026Q1,2026Q2"), snap()) == ["c1", "c2"]


def test_pe_blocked_when_no_quarters_anywhere():
    assert ttm_flags(pe_draft(with_eps=False), snap()) == ["c2"]


def test_pe_with_its_own_wrong_quarters_still_blocked():
    assert "c2" in ttm_flags(pe_draft(pe_period="2025Q4-2026Q2"), snap())


def obs(*tools):
    return [{"obs_id": f"obs-{i}", "tool_name": t, "status": "ok", "brief": "", "digest": ""} for i, t in enumerate(tools, 1)]


def base_draft(**kw):
    d = {"status": "draft", "claims": [{"claim_id": "c1", "kind": "unknown", "text": "x", "evidence_refs": [], "facts": []}],
         "valuation_scenarios": [], "macro_observations": []}
    d.update(kw)
    return d


def coverage(d, o):
    r = check_draft(d, {"ticker": "2330", "evidences": []}, CUTOFF, "snap", observations=o, system_events=set())["review"]
    return [i for i in r["issues"] if i["reason"].startswith(("已取得", "草稿沒有總經"))]


@pytest.mark.parametrize("tools,draft_kw,n", [
    (("get_price_window",), {}, 2),                                            # 有股價沒估值、沒查總經
    (("get_price_window", "get_macro_snapshot"), {}, 2),                       # 有股價沒估值、有總經沒寫
    (("get_price_window", "get_macro_snapshot"), {"valuation_scenarios": ["v"], "macro_observations": ["m"]}, 0),
    (("get_macro_snapshot",), {"macro_observations": ["m"]}, 0),                # 沒拿到股價就不要求估值
])
def test_coverage_notes(tools, draft_kw, n):
    issues = coverage(base_draft(**draft_kw), obs(*tools))
    assert len(issues) == n and all(i["severity"] == "minor" for i in issues)


def test_coverage_notes_never_block_and_skip_insufficient():
    d = pe_draft()
    d["valuation_scenarios"], d["macro_observations"] = [], []
    r = check_draft(d, snap(), CUTOFF, "snap", observations=obs("get_price_window"), system_events=set())["review"]
    assert r["decision"] == "pass"
    assert coverage(base_draft(status="insufficient"), obs("get_price_window")) == []
