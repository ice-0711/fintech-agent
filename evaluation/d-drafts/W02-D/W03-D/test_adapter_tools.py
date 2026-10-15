"""W03-D 草稿：六工具驗證測試（對應 B 的 data/v12-adapter-tests.md TEST-01 到 TEST-09，另加整合與 DCF 回歸）。

三組：
  A. 工具函式本身（直接呼叫 agents/tools_impl.py、agents/calculator.py）：TEST-01 到 TEST-09。
  B. 經由 dispatch 的整合測試：六個工具各測 正常 / 缺失 / 無權限。
     這是 provider.py 實際使用的路徑（agents/provider.py 呼叫 dispatch）。
  C. DCF 回歸：新的 calculate_dcf_scenario 對照既有年度 valuation_agent/dcf_model.py 與手算值。

全部離線，不呼叫任何模型，不連網。預期值是依手冊與 B 的規約先寫好，不是拿程式輸出反推。
測試失敗代表「依規約應該通過卻沒通過」，要交給 B 修正；失敗不要刪，要留在結果紀錄裡。

執行（在 repo 根目錄，用專案 venv）：
  REPO_ROOT=. python -m pytest -q <本檔>
"""

import copy
import inspect
import os
import sys

import pytest

REPO_ROOT = os.path.abspath(os.environ.get("REPO_ROOT", "."))
sys.path.insert(0, REPO_ROOT)

import agents.register_tools  # noqa: E402,F401  (載入時會把六個真實工具註冊進 dispatch)
from agents import calculator as calc  # noqa: E402
from agents import tools, tools_impl as ti  # noqa: E402

CUT_SEP = "2026-09-30T17:00:00+08:00"   # 資料檔裡價格最晚到 2026-09-30
CUT_MAY = "2026-05-31T17:00:00+08:00"   # 此時 2454 只有 3 季已公告
CUT_EARLY = "2026-06-01T00:00:00+08:00"  # 早於所有證據的公告時間


def _status(r):
    return r["status"]


# =====================================================================
# A. 工具函式本身：TEST-01 到 TEST-09
# =====================================================================
def test_TEST01_search_evidence_no_lookahead():
    out = ti.search_evidence("2330", "", CUT_EARLY, 3)
    assert _status(out) == "no_data"


def test_search_evidence_normal_returns_source_ids():
    out = ti.search_evidence("2330", "", CUT_SEP, 3)
    assert _status(out) == "ok"
    assert out["data"][0]["source_id"] and out["data"][0]["content_hash"]


def test_search_evidence_unauthorized_ticker():
    assert _status(ti.search_evidence("2379", "", CUT_SEP, 3)) == "invalid_input"


def test_TEST02_read_evidence_unknown_id_is_no_data():
    assert _status(ti.read_evidence("ev-does-not-exist")) == "no_data"


def test_read_evidence_normal():
    out = ti.read_evidence("ev-2330-2026q2-01")
    assert _status(out) == "ok" and out["data"]["content_hash"]


def test_TEST03_ttm_needs_four_quarters():
    out = ti.get_financial_snapshot("2454", CUT_MAY)  # 只有 2025Q3、2025Q4、2026Q1 三季
    assert _status(out) == "ok"
    m = out["data"]["metrics"]
    assert m["eps_ttm"] is None and m["fcf_ttm"] is None


def test_financial_snapshot_ttm_four_quarters_matches_hand_sum():
    snap = ti._load_snapshots()["financials"]["2454"]["quarters"]
    expected_eps = round(sum(q["eps"] for q in snap[-4:]), 2)  # 手算：最後四季單季 EPS 相加
    out = ti.get_financial_snapshot("2454", CUT_SEP)
    assert out["data"]["metrics"]["eps_ttm"] == expected_eps


def test_ttm_requires_consecutive_quarters(monkeypatch):
    """手冊 F01：TTM 需要四個『連續』季度。這裡挖掉 2025Q4，四季不連續，預期 TTM 為 null。"""
    data = copy.deepcopy(ti._load_snapshots())
    base = data["financials"]["2454"]["quarters"]
    q = lambda period, day: dict(base[0], period=period, available_at=f"{day}T15:00:00+08:00", eps=1.0, free_cash_flow=1.0)
    data["financials"]["2454"]["quarters"] = [
        q("2025Q1", "2025-05-10"), q("2025Q3", "2025-11-10"), q("2026Q1", "2026-05-10"), q("2026Q2", "2026-08-10"),
    ]
    monkeypatch.setattr(ti, "_load_snapshots", lambda: data)
    out = ti.get_financial_snapshot("2454", CUT_SEP)
    assert out["data"]["metrics"]["eps_ttm"] is None


def test_financial_snapshot_missing_ticker_is_no_data():
    assert _status(ti.get_financial_snapshot("2317", CUT_SEP)) == "no_data"


def test_TEST04_price_window_rejects_bad_sessions():
    assert _status(ti.get_price_window("2330", CUT_SEP, 10)) == "invalid_input"


def test_price_window_normal():
    out = ti.get_price_window("2454", CUT_SEP, 5)
    assert _status(out) == "ok" and len(out["data"]["closes"]) == 5


def test_price_window_insufficient_sessions_is_no_data():
    assert _status(ti.get_price_window("2454", CUT_SEP, 20)) == "no_data"


def test_TEST05_pe_nonpositive_eps_not_applicable():
    out = ti.calculate_metrics("pe_ttm", {"price": 120, "eps_ttm": 0}, ["e1"])
    assert _status(out) == "invalid_input"
    out = ti.calculate_metrics("pe_ttm", {"price": 120, "eps_ttm": -2}, ["e1"])
    assert _status(out) == "invalid_input"


def test_pe_normal_hand_value():
    out = ti.calculate_metrics("pe_ttm", {"price": 120, "eps_ttm": 6}, ["e1"])
    assert _status(out) == "ok" and out["data"]["result_value"] == 20.0  # 120 / 6 = 20


def test_calculate_metrics_requires_evidence_refs():
    assert _status(ti.calculate_metrics("pe_ttm", {"price": 120, "eps_ttm": 6}, [])) == "invalid_input"


DCF_OK = dict(free_cash_flows=[100.0, 110.0], wacc=0.10, terminal_growth=0.02, net_debt=50.0, shares_outstanding=100.0)


def test_TEST06_dcf_wacc_not_above_g():
    v = dict(DCF_OK, wacc=0.03, terminal_growth=0.03)
    assert _status(ti.calculate_metrics("dcf_scenario", v, ["e1"])) == "invalid_input"


def test_TEST07_dcf_missing_net_debt_is_not_zero():
    v = dict(DCF_OK, net_debt=None)
    assert _status(ti.calculate_metrics("dcf_scenario", v, ["e1"])) == "invalid_input"


PEER_BASE = {
    "2454": {"price": 100, "eps_ttm": 10, "pb": 2.0},
    "2379": {"price": 100, "eps_ttm": 5, "pb": 4.0},   # PE 20
    "3034": {"price": 50, "eps_ttm": 5, "pb": 2.0},    # PE 10
    "2330": {"price": 500, "eps_ttm": 10, "pb": 6.0},  # PE 50，產業參照
}


def test_TEST08_peer_subject_must_be_2454():
    out = ti.calculate_metrics("peer_comparison",
                               {"subject": "2330", "comparators": ["2379"], "metrics": PEER_BASE}, ["e1"])
    assert _status(out) == "invalid_input"


def test_TEST08_peer_more_than_four_companies():
    out = ti.calculate_metrics("peer_comparison",
                               {"subject": "2454", "comparators": ["2379", "3034", "2330", "9999"], "metrics": PEER_BASE}, ["e1"])
    assert _status(out) == "invalid_input"


def test_TEST09_peer_average_excludes_2330():
    out = ti.calculate_metrics("peer_comparison",
                               {"subject": "2454", "comparators": ["2379", "3034", "2330"], "metrics": PEER_BASE}, ["e1"])
    assert _status(out) == "ok"
    d = out["data"]
    assert d["comparison_table"]["2330"]["role"] == "industry_reference"
    # 手算：同業只有 2379(PE 20) 與 3034(PE 10)，平均 15.0；若誤把 2330(PE 50) 算進去會是 26.67
    assert d["peer_average_stats"]["peer_avg_pe"] == 15.0
    # PB 手算：(4.0 + 2.0) / 2 = 3.0
    assert d["peer_average_stats"]["peer_avg_pb"] == 3.0


def test_macro_snapshot_direct_normal_and_no_lookahead():
    ok = ti.get_macro_snapshot(CUT_SEP, ["FEDFUNDS"])
    assert _status(ok) == "ok" and ok["data"][0]["series_id"] == "FEDFUNDS"
    early = ti.get_macro_snapshot(CUT_EARLY, ["FEDFUNDS"])   # FEDFUNDS 於 2026-07-01 才可得
    assert _status(early) == "no_data"


def test_macro_snapshot_direct_unknown_series_is_no_data():
    assert _status(ti.get_macro_snapshot(CUT_SEP, ["NOT_A_SERIES"])) == "no_data"


def test_tools_can_read_dev_case_snapshots():
    """B 的 dev 案例證據放在 fixtures/dev/case_fixtures.json（例如 ev-dev-01-official），
    但六工具讀的是 data/financial-snapshots.json。依手冊，工具應能讀到本 job 快照裡的證據。"""
    assert _status(ti.read_evidence("ev-dev-01-official")) == "ok"


# =====================================================================
# B. 經由 dispatch 的整合測試（provider.py 實際走的路徑）
# =====================================================================
NORMAL_CALLS = {
    "search_evidence": ("researcher", {"ticker": "2330", "query": "", "cutoff": CUT_SEP, "limit": 3}),
    "read_evidence": ("researcher", {"evidence_version_id": "ev-2330-2026q2-01"}),
    "get_financial_snapshot": ("researcher", {"ticker": "2454", "cutoff": CUT_SEP}),
    "get_price_window": ("researcher", {"ticker": "2454", "end_at": CUT_SEP, "sessions": 5}),
    "calculate_metrics": ("researcher", {"operation": "pe_ttm", "values": {"price": 120, "eps_ttm": 6}, "evidence_refs": ["e1"]}),
}


@pytest.mark.parametrize("name", list(NORMAL_CALLS))
def test_dispatch_normal_call_returns_ok(name):
    role, args = NORMAL_CALLS[name]
    out = tools.dispatch(role, name, args, CUT_SEP)
    assert out["status"] == "ok", f"{name} 經 dispatch 回 {out['status']}：{out.get('reason')}"


def test_dispatch_macro_normal_call_returns_ok():
    """已知待辦：MACRO_SERIES_WHITELIST 目前是空的（agents/tools.py 註解：待 W02 與 B 鎖定），
    所以任何序列都會被擋。資料檔裡有 CPIAUCSL、FEDFUNDS。白名單鎖定後這項應通過。"""
    out = tools.dispatch("researcher", "get_macro_snapshot", {"cutoff": CUT_SEP, "series_ids": ["CPIAUCSL"]}, CUT_SEP)
    assert out["status"] == "ok", out.get("reason")


def test_registered_impls_follow_dict_contract():
    """dispatch 呼叫 impl(args)：把整包參數當成『一個字典』傳入（agents/tools.py ToolImpl = Callable[[dict], dict]，
    既有測試也是 register_tool(..., lambda args: ...)）。真實工具必須能用一個位置參數呼叫。"""
    bad = []
    for name, impl in tools._REGISTRY.items():
        required = [p for p in inspect.signature(impl).parameters.values()
                    if p.default is inspect.Parameter.empty and p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)]
        if len(required) > 1:
            bad.append((name, [p.name for p in required]))
    assert not bad, f"這些工具需要多個必填參數，和 dispatch 的 impl(args) 不相容：{bad}"


@pytest.mark.parametrize("name,role,args", [
    ("search_evidence", "researcher", {"ticker": "2330", "cutoff": CUT_SEP, "limit": 3}),             # 缺 query
    ("read_evidence", "researcher", {}),                                                              # 缺 id
    ("get_financial_snapshot", "researcher", {"ticker": "2454"}),                                      # 缺 cutoff
    ("get_price_window", "researcher", {"ticker": "2454", "end_at": CUT_SEP}),                         # 缺 sessions
    ("calculate_metrics", "researcher", {"operation": "pe_ttm", "values": {}}),                        # 缺 evidence_refs
    ("get_macro_snapshot", "researcher", {"cutoff": CUT_SEP}),                                         # 缺 series_ids
])
def test_dispatch_missing_required_field_is_invalid_input(name, role, args):
    out = tools.dispatch(role, name, args, CUT_SEP)
    assert out["status"] == "invalid_input" and out["data"] is None


@pytest.mark.parametrize("name,args", [
    ("search_evidence", {"ticker": "2330", "query": "x", "cutoff": CUT_SEP, "limit": 3}),
    ("get_price_window", {"ticker": "2330", "end_at": CUT_SEP, "sessions": 5}),
])
def test_dispatch_reviewer_cannot_use_researcher_only_tools(name, args):
    out = tools.dispatch("reviewer", name, args, CUT_SEP)
    assert out["status"] == "invalid_input" and "無權" in out["reason"]


def test_dispatch_unknown_tool_and_unknown_role():
    assert tools.dispatch("researcher", "web_search", {}, CUT_SEP)["status"] == "invalid_input"
    assert tools.dispatch("intern", "read_evidence", {"evidence_version_id": "x"}, CUT_SEP)["status"] == "invalid_input"


def test_dispatch_refuses_data_after_job_cutoff():
    out = tools.dispatch("researcher", "get_price_window",
                         {"ticker": "2454", "end_at": "2026-10-05T17:00:00+08:00", "sessions": 5}, CUT_SEP)
    assert out["status"] == "invalid_input"


def test_dispatch_refuses_url_or_sql_in_query():
    out = tools.dispatch("researcher", "search_evidence",
                         {"ticker": "2454", "query": "http://evil.example; DROP TABLE jobs", "cutoff": CUT_SEP, "limit": 3}, CUT_SEP)
    assert out["status"] == "invalid_input"


# =====================================================================
# C. DCF 回歸：新 calculate_dcf_scenario 對照既有年度 DCF 與手算值
# =====================================================================
def _legacy_dcf():
    import importlib.util
    path = os.path.join(REPO_ROOT, "valuation_agent", "dcf_model.py")
    spec = importlib.util.spec_from_file_location("legacy_dcf_model", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# 既有 dcf_model.py 自己的範例：台積電、五年 FCF、WACC 9%、g 3%、淨負債 -3000（淨現金）、股數 25945（百萬股）
LEGACY_EXAMPLE = dict(free_cash_flows=[2000, 2200, 2400, 2600, 2800], wacc=0.09, terminal_growth=0.03,
                      net_debt=-3000, shares_outstanding=25945)


def test_dcf_new_calculator_matches_legacy_annual_dcf():
    legacy = _legacy_dcf().calculate_dcf(**LEGACY_EXAMPLE)
    new = calc.calculate_dcf_scenario(LEGACY_EXAMPLE["free_cash_flows"], LEGACY_EXAMPLE["wacc"],
                                      LEGACY_EXAMPLE["terminal_growth"], LEGACY_EXAMPLE["net_debt"],
                                      LEGACY_EXAMPLE["shares_outstanding"])
    assert new["is_applicable"] is True
    assert abs(new["intrinsic_value_per_share"] - legacy) <= 0.01  # 兩者四捨五入順序不同，容許 0.01 元


def test_dcf_hand_computed_two_year_example():
    """手算（億元、百萬股）：FCF=[100,110], WACC=10%, g=2%, 淨負債=50, 股數=100
       PV1=100/1.1=90.909091；PV2=110/1.21=90.909091；合計=181.818182
       TV=110*1.02/(0.10-0.02)=1402.5；PV(TV)=1402.5/1.21=1159.090909
       EV=1340.909091；股權=1290.909091；每股=1290.909091/100*100=1290.91"""
    out = calc.calculate_dcf_scenario(**DCF_OK)
    assert out["enterprise_value"] == 1340.91
    assert out["equity_value"] == 1290.91
    assert out["intrinsic_value_per_share"] == 1290.91


def test_dcf_zero_or_negative_shares_rejected():
    assert calc.calculate_dcf_scenario(**dict(DCF_OK, shares_outstanding=0))["is_applicable"] is False
    assert calc.calculate_dcf_scenario(**dict(DCF_OK, shares_outstanding=-5))["is_applicable"] is False


def test_dcf_empty_cash_flows_rejected_not_zero():
    out = calc.calculate_dcf_scenario(**dict(DCF_OK, free_cash_flows=[]))
    assert out["is_applicable"] is False and out["intrinsic_value_per_share"] is None
