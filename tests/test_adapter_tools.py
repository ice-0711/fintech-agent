"""tests/test_adapter_tools.py
V1.2 資料適配層與計算工具單元測試套件 (供組員 D 執行)
"""
import pytest
from agents.tools_impl import (
    search_evidence,
    read_evidence,
    get_financial_snapshot,
    get_price_window,
    calculate_metrics
)
from agents.calculator import (
    calculate_pe_ttm,
    calculate_dcf_scenario,
    calculate_peer_comparison
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
    """TEST-03: cutoff 設在 2025 年底 (僅 2 季資料)，TTM 必須回傳 None 並記錄 missing_reason"""
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
    """TEST-06: WACC <= g 拒絕折現計算"""
    res = calculate_dcf_scenario(
        free_cash_flows=[1200.0] * 5,
        wacc=0.03,
        terminal_growth=0.03,
        net_debt=-920.0,
        shares_outstanding=1600.0
    )
    assert not res["is_applicable"]


def test_test_07_calculate_dcf_missing_params():
    """TEST-07: 缺少關鍵參數禁止擅自以 0 補缺值"""
    res = calculate_dcf_scenario(
        free_cash_flows=[1200.0] * 5,
        wacc=0.08,
        terminal_growth=0.025,
        net_debt=None,
        shares_outstanding=1600.0
    )
    assert not res["is_applicable"]
    assert "關鍵參數缺失" in res["reason"]


def test_test_08_calculate_peer_comparison_subject_limit():
    """TEST-08: 主體只限 2454"""
    res = calculate_peer_comparison(subject="2330", comparators=["2454"], metrics_map={})
    assert not res["is_applicable"]


def test_test_09_calculate_peer_comparison_exclude_2330():
    """TEST-09: 2330 作為產業參照，嚴格排除在同業平均計算之外"""
    metrics = {
        "2454": {"price": 4920.0, "eps_ttm": 66.42, "pb": 15.44, "revenue_yoy": 0.1546},
        "2379": {"price": 1150.0, "eps_ttm": 27.87, "pb": 6.97, "revenue_yoy": 0.1250},
        "3034": {"price": 1220.0, "eps_ttm": 38.20, "pb": 6.59, "revenue_yoy": 0.0820},
        "2330": {"price": 2480.0, "eps_ttm": 76.54, "pb": 12.07, "revenue_yoy": 0.3500}
    }
    res = calculate_peer_comparison(subject="2454", comparators=["2379", "3034", "2330"], metrics_map=metrics)
    assert res["is_applicable"]
    stats = res["peer_average_stats"]
    assert stats["excluded_references"] == ["2330"]
    # 僅計算 2379 (41.26) 與 3034 (31.94) 之平均 = 36.60
    assert stats["peer_avg_pe"] == 36.60