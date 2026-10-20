"""tests/test_adapter_tools.py
V1.6 資料適配層與計算工具單元測試套件（供組員 D 執行）
舊值已全部更新：價格、TTM EPS、P/E、P/B、股數、淨負債皆來自已驗證來源。
"""
import pytest
from agents.tools_impl import (
    search_evidence,
    read_evidence,
    get_financial_snapshot,
    get_price_window,
    calculate_metrics,
)
from agents.calculator import (
    calculate_pe_ttm,
    calculate_dcf_scenario,
    calculate_peer_comparison,
)


def test_test_01_search_evidence_no_look_ahead():
    """TEST-01: cutoff 早於入庫可得時間，嚴禁前視洩漏，回傳 no_data"""
    res = search_evidence(ticker="2330", query="營收", cutoff="2026-06-01T00:00:00+08:00")
    assert res["status"] == "no_data"
    assert res["data"] is None


def test_test_02_read_evidence_invalid_id():
    """TEST-02: 輸入不存在之 ID，回傳 no_data，不拋出未捕獲例外"""
    res = read_evidence(evidence_version_id="ev-non-existent-999")
    assert res["status"] == "no_data"
    assert res["data"] is None


def test_test_03_get_financial_snapshot_incomplete_ttm():
    """TEST-03: cutoff 設在 2025 年底（僅 2 季資料），TTM 必須回傳 None 並記錄 missing_reason"""
    res = get_financial_snapshot(ticker="2454", cutoff="2025-12-31T00:00:00+08:00")
    assert res["status"] == "ok"
    assert res["data"]["metrics"]["eps_ttm"] is None
    assert res["data"]["missing_reason"] is not None


def test_test_04_get_price_window_invalid_sessions():
    """TEST-04: 請求非 1, 5, 20 之天數，回傳 invalid_input"""
    res = get_price_window(ticker="2330", end_at="2026-09-30T17:30:00+08:00", sessions=10)
    assert res["status"] == "invalid_input"


def test_test_05_calculate_pe_ttm_non_positive_eps():
    """TEST-05: EPS TTM <= 0 時標註 NA，不產出負本益比"""
    res_zero = calculate_pe_ttm(price=4920.0, eps_ttm=0.0)
    assert not res_zero["is_applicable"]
    res_neg = calculate_pe_ttm(price=4920.0, eps_ttm=-5.2)
    assert not res_neg["is_applicable"]


def test_test_06_calculate_dcf_wacc_le_g():
    """TEST-06: WACC <= g 拒絕折現計算。
    輸入為 2454 真實值：淨負債 −1717.81 億（淨現金）、流通股數 1596.10 百萬股。
    free_cash_flows 以 2454 TTM FCF 920.63 平送 5 年，僅用於驗證邏輯，不代表預測值。
    """
    res = calculate_dcf_scenario(
        free_cash_flows=[920.63] * 5,
        wacc=0.03,
        terminal_growth=0.03,
        net_debt=-1717.81,
        shares_outstanding=1596.10,
    )
    assert not res["is_applicable"]
def test_test_06b_calculate_dcf_requires_five_years():
    """TEST-06b: 預測期非 5 年須拒絕計算"""
    res = calculate_dcf_scenario(
        free_cash_flows=[920.63] * 3,
        wacc=0.10,
        terminal_growth=0.03,
        net_debt=-1717.81,
        shares_outstanding=1596.10,
    )
    assert not res["is_applicable"]
    assert "5 年" in res["reason"]


def test_test_07_calculate_dcf_missing_params():
    """TEST-07: 缺少關鍵參數禁止擅自以 0 補缺值"""
    res = calculate_dcf_scenario(
        free_cash_flows=[920.63] * 5,
        wacc=0.08,
        terminal_growth=0.025,
        net_debt=None,
        shares_outstanding=1596.10,
    )
    assert not res["is_applicable"]
    assert "關鍵參數缺失" in res["reason"]


def test_test_08_calculate_peer_comparison_subject_limit():
    """TEST-08: 主體只限 2454"""
    res = calculate_peer_comparison(subject="2330", comparators=["2454"], metrics_map={})
    assert not res["is_applicable"]


def test_test_09_calculate_peer_comparison_exclude_2330():
    """TEST-09: 2330 作為產業參照，嚴格排除在同業平均計算之外。

    數值來源（均已確認）：
    - 價格：TWSE STOCK_DAY 2026-09-30 收盤價，與 FinMind 比對一致
        2454 = 4920、2379 = 760、3034 = 546、2330 = 2480
    - TTM EPS ：（2025Q3 至 2026Q2 四季，依 data-contract 第二節第 2-1 條）
        2454 = 15.84 + 14.40 + 15.17 + 15.28 = 60.69
        2379 = 6.69 + 5.18 + 8.44 + 7.42 = 27.73
        3034 = 6.01 + 6.07 + 6.19 + 10.40 = 28.67
        2330 = 17.44 + 19.51 + 22.08 + 27.25 = 86.28
    - BVPS（2026Q2，流通股數口徑）
        2454 = 265.77、2379 = 97.83、3034 = 113.33、2330 = 248.05
    - revenue_yoy（2026Q2 營收 ÷ 2025Q2 營收 − 1，快照 JSON）
        2454 = 1521.83 ÷ 1503.69 − 1 ≈ 0.0121
        2379 = 375.53 ÷ 319.14 − 1 ≈ 0.1767
        3034 = 286.60 ÷ 261.52 − 1 ≈ 0.0959
        2330 = 12703.80 ÷ 9337.92 − 1 ≈ 0.3605

    同業平均 P/E（僅 2379 與 3034）：
        2379 P/E = 760 ÷ 27.73 ≈ 27.41
        3034 P/E = 546 ÷ 28.67 ≈ 19.04
        平均 ≈ 23.23
    """
    metrics = {
        "2454": {"price": 4920.0, "eps_ttm": 60.69, "pb": 18.51, "revenue_yoy": 0.0121},
        "2379": {"price": 760.0, "eps_ttm": 27.73, "pb": 7.77, "revenue_yoy": 0.1767},
        "3034": {"price": 546.0, "eps_ttm": 28.67, "pb": 4.82, "revenue_yoy": 0.0959},
        "2330": {"price": 2480.0, "eps_ttm": 86.28, "pb": 10.00, "revenue_yoy": 0.3605},
    }
    res = calculate_peer_comparison(subject="2454", comparators=["2379", "3034", "2330"], metrics_map=metrics)
    assert res["is_applicable"]
    stats = res["peer_average_stats"]
    assert stats["excluded_references"] == ["2330"]
    # 僅計算 2379 (27.41) 與 3034 (19.04) 之平均 ≈ 23.23，容許四捨五入誤差 0.01
    assert stats["peer_avg_pe"] == pytest.approx(23.23, abs=0.01)
