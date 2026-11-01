"""tests/test_audit_forward_valuation.py — W08-B 前瞻 DCF／P/E 獨立重算工具"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("afv", ROOT / "scripts" / "audit_forward_valuation.py")
afv = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(afv)

# B 事實表（data/v12-finance-fact-sheet.md）與 A 報告的 2026Q2 基準值
EXPECTED = {
    "2454": dict(ttm_eps=60.69, pe_ttm=81.07, pb=18.51, ttm_fcf=920.63, dcf_per_share=975.52, valuation_status="above_model"),
    "2379": dict(ttm_eps=27.73, pe_ttm=27.41, pb=7.77, ttm_fcf=168.21, dcf_per_share=497.48, valuation_status="above_model"),
    "3034": dict(ttm_eps=28.67, pe_ttm=19.04, pb=4.82, ttm_fcf=167.49, dcf_per_share=502.88, valuation_status="near_model"),
    "2330": dict(ttm_eps=86.28, pe_ttm=28.74, pb=10.0, ttm_fcf=11435.56, dcf_per_share=751.06, valuation_status="above_model"),
    "2317": dict(ttm_eps=15.21, pe_ttm=16.54, pb=1.85, ttm_fcf=-416.44, dcf_per_share=None, valuation_status="undeterminable"),
}


def test_reproduces_frozen_snapshot_values():
    rows = {r["ticker"]: r for r in afv.audit(ROOT / "data" / "financial-snapshots.json")}
    for ticker, exp in EXPECTED.items():
        for key, value in exp.items():
            assert rows[ticker][key] == value, (ticker, key, rows[ticker][key])


def _q(period, eps=1.0, fcf=10.0, src="mops_direct"):
    return {"period": period, "eps": eps, "free_cash_flow": fcf, "eps_source": src,
            "bvps": 10.0, "net_debt": 0.0, "shares_outstanding": 100.0}


def test_fewer_than_four_or_gap_quarters_gives_null_ttm():
    r = afv.audit_company("x", [_q("2026Q1"), _q("2026Q2"), _q("2026Q3")], [{"trade_date": "d", "close": 10.0}])
    assert r["ttm_eps"] is None and r["pe_ttm"] is None and "不足" in r["notes"]
    r = afv.audit_company("x", [_q("2025Q2"), _q("2025Q4"), _q("2026Q1"), _q("2026Q2")], [{"trade_date": "d", "close": 10.0}])
    assert r["ttm_eps"] is None


def test_unverified_eps_gives_null_ttm_eps():
    qs = [_q("2025Q4"), _q("2026Q1"), _q("2026Q2"), _q("2026Q3", src="unverified")]
    assert afv.audit_company("x", qs, [{"trade_date": "d", "close": 10.0}])["ttm_eps"] is None


def test_negative_eps_or_fcf_is_not_valued():
    qs = [_q(p, eps=-1.0, fcf=-5.0) for p in ("2025Q4", "2026Q1", "2026Q2", "2026Q3")]
    r = afv.audit_company("x", qs, [{"trade_date": "d", "close": 10.0}])
    assert r["pe_ttm"] is None and r["dcf_per_share"] is None and r["valuation_status"] == "undeterminable"


def test_refuses_output_into_data_forward(tmp_path):
    with pytest.raises(SystemExit):
        afv.main([str(ROOT / "data" / "financial-snapshots.json"), "--csv", "data/forward/x.csv"])