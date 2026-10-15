"""W04-D 草稿：Reviewer prompt/schema 與離線核對測試。

全部離線，不呼叫任何模型。預期決定是 D 先依手冊規則寫在 dev_drafts.json，再讓程式比對。
執行（在本資料夾）：
  REPO_ROOT=<fintech_project 路徑> python -m pytest -q test_reviewer_v12.py
沒有設定 REPO_ROOT 時，需要 B 的檔案的測試會自動跳過。
"""

import copy
import json
import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import reviewer_checks as rc  # noqa: E402
import reviewer_v12 as rv  # noqa: E402

REPO_ROOT = os.environ.get("REPO_ROOT", "")
need_repo = pytest.mark.skipif(not (REPO_ROOT and os.path.isdir(REPO_ROOT)), reason="沒有設定 REPO_ROOT")
CUT = "2026-08-15T17:00:00+08:00"


def _load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------- prompt
def test_prompt_has_version_and_stable_hash():
    assert rv.REVIEWER_PROMPT_VERSION.startswith("reviewer-v1.2")
    h = rv.prompt_hash()
    assert len(h) == 64 and h == rv.prompt_hash()
    assert rv.prompt_hash("x") != h


@pytest.mark.parametrize("phrase", [
    "沒有發布、核准、改資料的權限",      # 角色沒有發布權
    "只可使用 read_evidence、get_financial_snapshot、get_macro_snapshot、calculate_metrics",
    "2330 只是產業參照",                 # 不可把 2330 當 2454 同業
    "四個連續單季",                       # TTM
    "available_at 不晚於 cutoff_at",
    "不得因文字流暢",                     # 不只按流暢度
    "critical 必須指到 claim_id",
    "資料不足是有效結果",
    "不輸出思考過程",
])
def test_prompt_contains_required_rules(phrase):
    assert phrase in rv.load_prompt()


def test_prompt_does_not_grant_forbidden_tools_or_publish():
    p = rv.load_prompt()
    assert "search_evidence" not in p and "get_price_window" not in p.split("不可搜尋")[0]
    for bad in ("可以發布", "有權發布", "核准報告"):
        assert bad not in p


@need_repo
def test_prompt_plus_tools_fit_input_cap():
    sys.path.insert(0, REPO_ROOT)
    from agents import tools
    decls = [t for t in tools.TOOL_DECLARATIONS if t["name"] in tools.ROLE_TOOLS["reviewer"]]
    est = rv.estimate_input_tokens("", decls)
    assert est["prompt"] + est["tools"] < 2000, est        # 留 1000 以上給草稿
    assert est["total"] < est["input_cap"]


@need_repo
def test_reviewer_tools_match_repo_role_tools():
    sys.path.insert(0, REPO_ROOT)
    from agents import tools
    assert tuple(tools.ROLE_TOOLS["reviewer"]) == rv.REVIEWER_TOOLS


# ---------------------------------------------------------------- validate_review
def _ok_review(**kw):
    r = {"decision": "revise",
         "issues": [{"claim_id": "c1", "severity": "critical", "reason": "營收引用不存在",
                     "required_evidence": "read_evidence(ev-x)，核對 c1 的營收期間與單位"}],
         "checked_refs": ["ev-x"], "checked_metric_ids": ["revenue"], "decision_summary": "有 1 個 critical。"}
    r.update(kw)
    return r


def test_valid_review_passes():
    assert rv.validate_review(_ok_review(), ["c1", "c2"]) == []


def test_role_has_no_publish_authority():
    for extra in ("publish", "approved", "status", "publication_status"):
        errs = rv.validate_review(_ok_review(**{extra: True}), ["c1"])
        assert any("不允許的欄位" in e for e in errs), extra


@pytest.mark.parametrize("mutate,needle", [
    (lambda r: r.update(decision="approve"), "decision"),
    (lambda r: r["issues"][0].update(severity="blocker"), "severity"),
    (lambda r: r["issues"][0].update(claim_id=""), "claim_id"),
    (lambda r: r["issues"][0].update(claim_id="c9"), "不在草稿"),
    (lambda r: r["issues"][0].update(required_evidence="請改善"), "required_evidence"),
    (lambda r: r["issues"][0].update(required_evidence="請補充更多新聞資料讓報告更完整"), "太籠統"),
    (lambda r: r["issues"][0].update(required_evidence="再多找一些相關的資料來看看吧"), "沒有指到"),
    (lambda r: r.update(decision_summary="字" * 121), "decision_summary"),
    (lambda r: r.pop("checked_refs"), "缺少欄位"),
])
def test_invalid_reviews_rejected(mutate, needle):
    r = _ok_review()
    mutate(r)
    errs = rv.validate_review(r, ["c1"])
    assert errs and any(needle in e for e in errs), errs


def test_decision_consistency_rules():
    crit = _ok_review(decision="pass")
    assert any("pass" in e for e in rv.validate_review(crit, ["c1"]))
    minor_only = _ok_review(decision="revise")
    minor_only["issues"][0]["severity"] = "minor"
    assert any("revise" in e for e in rv.validate_review(minor_only, ["c1"]))
    assert any("insufficient" in e for e in rv.validate_review(_ok_review(decision="insufficient", issues=[]), ["c1"]))
    assert rv.validate_review(_ok_review(decision="pass", issues=[]), ["c1"]) == []


def test_reviewer_tool_use_allowlist():
    assert rv.validate_tool_use(["read_evidence", "calculate_metrics"]) == []
    errs = rv.validate_tool_use(["search_evidence", "get_price_window", "web_search"])
    assert len(errs) == 3


def test_schema_file_agrees_with_validator():
    jsonschema = pytest.importorskip("jsonschema")
    schema = _load(rv.SCHEMA_PATH)
    jsonschema.Draft202012Validator.check_schema(schema)
    v = jsonschema.Draft202012Validator(schema)
    assert not list(v.iter_errors(_ok_review()))
    assert list(v.iter_errors(_ok_review(publish=True)))               # 不可多欄位
    assert list(v.iter_errors(_ok_review(decision="approve")))
    bad = _ok_review(); bad["issues"][0]["severity"] = "blocker"
    assert list(v.iter_errors(bad))
    bad = _ok_review(); bad["issues"][0]["required_evidence"] = "短"
    assert list(v.iter_errors(bad))


# ---------------------------------------------------------------- 規則單元測試（合成資料，不是 dev 案例答案）
def _snap(**kw):
    base = {"ticker": "2454", "evidences": [{"evidence_version_id": "ev-a", "title": "官方公告", "paragraph": "營收為新台幣 100 億元",
                                              "available_at": "2026-08-01T10:00:00+08:00"}]}
    base.update(kw)
    return base


def _draft(facts, refs=("ev-a",), kind="fact", text="營收 100 億元"):
    return {"claims": [{"claim_id": "c1", "kind": kind, "text": text, "evidence_refs": list(refs), "facts": facts, "limitations": []}], "conflicts": []}


def _codes(res):
    return [t["code"] for t in res["trace"]]


def test_consecutive_quarter_helper():
    assert rc.consecutive_quarters(["2025Q3", "2025Q4", "2026Q1", "2026Q2"])
    assert not rc.consecutive_quarters(["2025Q1", "2025Q3", "2026Q1", "2026Q2"])
    assert not rc.consecutive_quarters(["2026Q1", "2026Q2"])
    assert not rc.consecutive_quarters(["x", "y", "z", "w"])


def test_ttm_gap_is_critical():
    f = [{"metric": "eps_ttm", "value": 38.2, "period_basis": "ttm", "quarters": ["2025Q1", "2025Q3", "2026Q1", "2026Q2"], "source_ref": "ev-a"}]
    res = rc.check_draft(_draft(f), _snap(), CUT, "snap-x")
    assert "ttm_not_consecutive" in _codes(res) and res["review"]["decision"] in ("revise", "insufficient")


def test_ttm_four_consecutive_ok():
    f = [{"metric": "eps_ttm", "value": 100, "period_basis": "ttm", "quarters": ["2025Q3", "2025Q4", "2026Q1", "2026Q2"], "source_ref": "ev-a"}]
    res = rc.check_draft(_draft(f), _snap(), CUT, "snap-x")
    assert "ttm_not_consecutive" not in _codes(res)


def test_available_after_cutoff_is_lookahead():
    s = _snap()
    s["evidences"][0]["available_at"] = "2026-08-20T10:00:00+08:00"
    res = rc.check_draft(_draft([]), s, CUT, "snap-x")
    assert "lookahead" in _codes(res) and res["review"]["decision"] == "revise"


def test_peer_average_including_2330_is_critical():
    f = [{"metric": "peer_avg_pe", "value": 26.67, "peers": ["2379", "3034", "2330"]}]
    res = rc.check_draft(_draft(f), _snap(), CUT, "snap-x")
    assert "peer_includes_2330" in _codes(res)
    ok = [{"metric": "peer_avg_pe", "value": 15.0, "peers": ["2379", "3034"]}]
    assert "peer_includes_2330" not in _codes(rc.check_draft(_draft(ok), _snap(), CUT, "snap-x"))


def test_peer_more_than_four_companies():
    f = [{"metric": "peer_avg_pe", "value": 15.0, "peers": ["2379", "3034", "9001", "9002"]}]
    assert "peer_over_4" in _codes(rc.check_draft(_draft(f), _snap(), CUT, "snap-x"))


def test_wacc_not_above_g_is_critical():
    s = _snap(financial_snapshot={"free_cash_flow": 10.0, "shares_outstanding": 100.0})
    f = [{"metric": "dcf_per_share", "value": 50.0, "wacc": 0.03, "g": 0.03}]
    assert "wacc_le_g" in _codes(rc.check_draft(_draft(f, refs=["snap-x"]), s, CUT, "snap-x"))


def test_eps_nonpositive_pe_is_not_applicable_issue():
    f = [{"metric": "pe_ttm", "value": 20.0, "inputs": {"price": 120, "eps_ttm": -2}}]
    assert "pe_na" in _codes(rc.check_draft(_draft(f, refs=["snap-x"]), _snap(), CUT, "snap-x"))


def test_unsupported_number_is_flagged():
    f = [{"metric": "revenue", "value": 999, "currency": "TWD", "source_ref": "ev-a"}]
    assert "not_supported" in _codes(rc.check_draft(_draft(f), _snap(), CUT, "snap-x"))


def test_currency_mislabel_is_flagged():
    s = _snap()
    s["evidences"][0]["paragraph"] = "Revenue was USD 20.8 Billion"
    f = [{"metric": "revenue", "value": 20.8, "currency": "TWD", "source_ref": "ev-a"}]
    assert "currency_mislabel" in _codes(rc.check_draft(_draft(f), s, CUT, "snap-x"))


def test_fact_without_ref_is_critical():
    res = rc.check_draft(_draft([], refs=[]), _snap(), CUT, "snap-x")
    assert "fact_no_ref" in _codes(res)


def test_no_budget_with_critical_means_insufficient_not_pass():
    s = _snap()
    s["evidences"][0]["available_at"] = "2026-08-20T10:00:00+08:00"
    res = rc.check_draft(_draft([]), s, CUT, "snap-x", remaining_calls=0)
    assert res["review"]["decision"] == "insufficient"
    assert rv.validate_review(res["review"], ["c1"]) == []


def test_minor_only_still_passes():
    s = _snap()
    s["evidences"].append({"evidence_version_id": "ev-b", "title": "官方公告二", "paragraph": "營收為新台幣 120 億元",
                           "available_at": "2026-08-02T10:00:00+08:00"})
    f = [{"metric": "revenue", "value": 100, "currency": "TWD", "source_ref": "ev-a"}]
    res = rc.check_draft(_draft(f), s, CUT, "snap-x")   # 兩個證據營收不同，草稿沒揭露 -> minor
    assert "conflict_undisclosed" in _codes(res) and res["review"]["decision"] == "pass"


def test_recommendations_are_always_critical():
    res = rc.check_draft(_draft([], text="建議買進，目標價 500"), _snap(), CUT, "snap-x")
    assert "recommendation" in _codes(res)


# ---------------------------------------------------------------- 10 個 dev 案例的草稿
DRAFTS = _load(os.path.join(HERE, "dev_drafts.json"))["entries"]


def _case_inputs(case_id):
    cases = {c["case_id"]: c for c in _load(os.path.join(REPO_ROOT, "evaluation", "dev-cases.json"))["cases"]}
    fx = _load(os.path.join(REPO_ROOT, "fixtures", "dev", "case_fixtures.json"))["snapshots"]
    c = cases[case_id]
    return c, fx[c["source_snapshot_id"]]


@need_repo
@pytest.mark.parametrize("entry", DRAFTS, ids=[e["id"] for e in DRAFTS])
def test_dev_draft_decision_and_critical_claims(entry):
    case, snap = _case_inputs(entry["case_id"])
    res = rc.check_draft(entry["draft"], snap, case["cutoff_at"], case["source_snapshot_id"],
                         observations=entry.get("observations"))
    review = res["review"]
    assert review["decision"] == entry["expected_decision"], (review["decision"], res["trace"])
    crit = sorted({i["claim_id"] for i in review["issues"] if i["severity"] == "critical"})
    assert crit == sorted(entry["expected_critical_claims"]), res["trace"]
    # 輸出本身必須合格：critical 指到 claim_id、required_evidence 具體、沒有發布欄位
    claim_ids = [c["claim_id"] for c in entry["draft"]["claims"]]
    assert rv.validate_review(review, claim_ids) == []


@need_repo
def test_dev_drafts_cover_all_three_decisions_and_ten_cases():
    assert {e["expected_decision"] for e in DRAFTS} == {"pass", "revise", "insufficient"}
    assert len({e["case_id"] for e in DRAFTS}) == 10


@need_repo
def test_dev_drafts_only_use_bs_ten_dev_cases():
    dev = {c["case_id"] for c in _load(os.path.join(REPO_ROOT, "evaluation", "dev-cases.json"))["cases"]}
    assert {e["case_id"] for e in DRAFTS} <= dev


@need_repo
def test_flawed_drafts_are_not_passed_and_good_drafts_are_not_revised():
    for e in DRAFTS:
        case, snap = _case_inputs(e["case_id"])
        d = rc.check_draft(e["draft"], snap, case["cutoff_at"], case["source_snapshot_id"], observations=e.get("observations"))["review"]["decision"]
        if e["variant"] == "flawed":
            assert d != "pass", e["id"]
        else:
            assert d != "revise", e["id"]
