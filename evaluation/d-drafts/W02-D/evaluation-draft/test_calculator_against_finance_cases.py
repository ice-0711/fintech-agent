"""W02-D 草稿：把 v12-finance-cases.json 裡「calculator.py 目前有實作」的測例接上去驗證。

目前只能接 5 個：FIN-09、FIN-10、FIN-11（P/E）、FIN-14、FIN-15（成長率）。
其餘測例（累計轉單季、TTM、P/B、FCF、同日價格、公告時間等）在 agents/calculator.py 裡沒有對應函式，
所以這裡不測，也不假裝通過；要等 B 說明這些規則放在哪個模組、介面是什麼。

執行方式（在 repo 根目錄，用專案的 venv）：
  CALCULATOR_PATH=agents/calculator.py CASES_PATH=<W02-D>/v12-finance-cases.json python -m pytest -q <本檔>
全部離線，不呼叫任何模型。
"""

import importlib.util
import json
import os

import pytest

CALC = os.environ.get("CALCULATOR_PATH", "")
CASES = os.environ.get("CASES_PATH", os.path.join(os.path.dirname(__file__), "..", "v12-finance-cases.json"))

pytestmark = pytest.mark.skipif(not (CALC and os.path.exists(CALC)), reason="沒有設定 CALCULATOR_PATH")


def _load_calc():
    spec = importlib.util.spec_from_file_location("calculator_under_test", CALC)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _case(cid):
    with open(CASES, encoding="utf-8") as f:
        for c in json.load(f)["cases"]:
            if c["case_id"] == cid:
                return c
    raise KeyError(cid)


@pytest.mark.parametrize("cid", ["FIN-09", "FIN-10"])
def test_pe_ok(cid):
    c, calc = _case(cid), _load_calc()
    out = calc.calculate_pe_ttm(c["inputs"]["price"], c["inputs"]["ttm_eps"])
    assert out["is_applicable"] is True
    assert out["result_value"] == c["expected"]["pe"]


def test_pe_nonpositive_eps_is_NA():
    c, calc = _case("FIN-11"), _load_calc()
    out = calc.calculate_pe_ttm(c["inputs"]["price"], c["inputs"]["ttm_eps"])
    assert out["is_applicable"] is False and out["result_value"] is None


def test_growth_rate_ok():
    c, calc = _case("FIN-14"), _load_calc()
    out = calc.calculate_growth_rate(c["inputs"]["revenue"], c["inputs"]["revenue_prior_year_quarter"])
    # calculator 回傳的是比例（0.2），測例用的是百分比（20.0）；這裡換算後比較
    assert out["is_applicable"] is True
    assert round(out["result_value"] * 100, 2) == c["expected"]["yoy_pct"]


def test_growth_rate_missing_base_is_NA():
    c, calc = _case("FIN-15"), _load_calc()
    out = calc.calculate_growth_rate(c["inputs"]["revenue"], c["inputs"]["revenue_prior_year_quarter"])
    assert out["is_applicable"] is False and out["result_value"] is None
