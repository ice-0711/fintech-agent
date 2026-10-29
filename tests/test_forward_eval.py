"""tests/test_forward_eval.py — W07-D 前瞻評估 runner（不連網、不耗 LLM）

所有價格與日曆都是「測試用的合成資料」，只驗證計算規則，不代表任何真實股價或真實交易日曆。
合成日曆刻意拿掉 2026-11-04（假裝休市），確認程式用日曆而不是用「週一到週五」推算。
"""
from __future__ import annotations

import ast
import csv
import importlib.util
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("forward_eval", ROOT / "scripts" / "forward_eval.py")
fe = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fe)

TPE = timezone(timedelta(hours=8))
CUTOFF = "2026-10-30T21:00:00+08:00"


def make_calendar():
    days, d = [], date(2026, 10, 26)
    while d <= date(2026, 12, 11):
        if d.weekday() < 5 and d != date(2026, 11, 4):  # 合成：11/04 休市
            days.append(d)
        d += timedelta(days=1)
    return days


CAL = make_calendar()
ENTRY = date(2026, 11, 2)
IDX = CAL.index(ENTRY)
D1, D5, D20 = CAL[IDX], CAL[IDX + 4], CAL[IDX + 19]


def make_prices(ticker="2330", entry_open=100.0, closes=None, volume=1000):
    closes = closes or {D1: 102.0, D5: 110.0, D20: 90.0}
    prices = {(ticker, ENTRY): {"open": entry_open, "close": 101.0, "volume": volume}}
    for d, c in closes.items():
        prices.setdefault((ticker, d), {"open": c, "close": c, "volume": volume})
        prices[(ticker, d)]["close"] = c
        prices[(ticker, d)]["volume"] = volume
    return prices


def sig(direction="up", ticker="2330", cutoff=CUTOFF, sid="fwd1-2330"):
    return {"signal_id": sid, "ticker": ticker, "signal_cutoff_at": cutoff, "direction": direction}


def as_of(d, hh=18, mm=0):
    return datetime(d.year, d.month, d.day, hh, mm, tzinfo=TPE)


def ev(signal=None, prices=None, when=None, actions=None, calendar=None):
    return fe.evaluate_signal(signal or sig(), calendar or CAL, prices if prices is not None else make_prices(),
                              when or as_of(D20), actions or [])


def test_entry_is_next_trading_day_open_not_cutoff_day():
    row = ev()
    assert row["entry_date"] == "2026-11-02"  # 10/30 21:00 之後，下一個交易日，不是 10/30
    assert row["entry_open"] == 100.0


def test_cutoff_before_market_open_uses_same_day():
    row = ev(sig(cutoff="2026-11-02T08:00:00+08:00"))
    assert row["entry_date"] == "2026-11-02"


def test_entry_day_close_is_first_holding_day_and_d5_d20_counts():
    assert D1 == ENTRY
    assert CAL.index(D5) - CAL.index(D1) == 4      # D5 = 第 5 個持有交易日（含 entry 當日）
    assert CAL.index(D20) - CAL.index(D1) == 19
    row = ev()
    assert row["d1_exit_date"] == D1.isoformat() and row["d5_exit_date"] == D5.isoformat()
    assert row["d20_exit_date"] == D20.isoformat()


def test_return_formula_and_raw_prices():
    row = ev()
    assert row["d1_return"] == pytest.approx((102.0 - 100.0) / 100.0)
    assert row["d5_return"] == pytest.approx(0.10)
    assert row["d20_return"] == pytest.approx(-0.10)
    assert [row[f"d{k}_status"] for k in (1, 5, 20)] == ["ok"] * 3


def test_calendar_skips_holiday_instead_of_weekdays():
    # 11/04 不在日曆：D5 應該是 11/09，而不是週一到週五推算的 11/06
    assert D5 == date(2026, 11, 9)


def test_as_of_before_cutoff_is_all_na():
    row = ev(when=as_of(date(2026, 10, 29)))
    assert {row[f"d{k}_na_reason"] for k in (1, 5, 20)} == {"cutoff_not_reached"}


def test_immature_until_close_is_available_at_1730():
    early = ev(when=as_of(D5, 17, 29))
    assert early["d5_status"] == "NA" and early["d5_na_reason"] == "immature"
    assert early["d1_status"] == "ok"             # D1 早就成熟，不受 D5 影響
    on_time = ev(when=as_of(D5, 17, 30))
    assert on_time["d5_status"] == "ok"
    assert on_time["d20_na_reason"] == "immature"


def test_window_beyond_calendar_is_na():
    short_cal = [d for d in CAL if d <= D5]
    row = ev(calendar=short_cal)
    assert row["d20_na_reason"] == "window_beyond_calendar" and row["d5_status"] == "ok"


def test_calendar_without_entry_day_is_na():
    row = ev(calendar=[d for d in CAL if d <= date(2026, 10, 30)])
    assert {row[f"d{k}_na_reason"] for k in (1, 5, 20)} == {"calendar_missing_entry"}


def test_missing_entry_open_makes_all_horizons_na():
    prices = make_prices()
    prices[("2330", ENTRY)]["open"] = None
    row = ev(prices=prices)
    assert {row[f"d{k}_na_reason"] for k in (1, 5, 20)} == {"missing_entry_open"}
    assert row["entry_open"] == ""


def test_missing_exit_close_only_hits_that_horizon():
    prices = make_prices()
    del prices[("2330", D5)]
    row = ev(prices=prices)
    assert row["d5_na_reason"] == "missing_exit_close"
    assert row["d1_status"] == "ok" and row["d20_status"] == "ok"


def test_suspended_exit_is_na_and_not_filled():
    prices = make_prices()
    prices[("2330", D20)]["volume"] = 0
    row = ev(prices=prices)
    assert row["d20_na_reason"] == "suspended_exit" and row["d20_return"] == ""


def test_suspended_entry_is_na():
    row = ev(prices=make_prices(volume=0))
    assert row["d1_na_reason"] == "suspended_entry"


def test_corporate_action_flagged_but_raw_return_kept():
    row = ev(actions=[{"ticker": "2330", "ex_date": D5.isoformat()},
                      {"ticker": "2317", "ex_date": D5.isoformat()}])
    assert row["d1_corporate_action_in_window"] == ""
    assert row["d5_corporate_action_in_window"] == D5.isoformat()
    assert row["d20_corporate_action_in_window"] == D5.isoformat()
    assert row["d5_return"] == pytest.approx(0.10)   # 不還原


@pytest.mark.parametrize("direction,hits", [
    ("up", ["hit", "hit", "miss"]),       # D1 +2%、D5 +10%、D20 -10%
    ("down", ["miss", "miss", "hit"]),
    ("none", ["", "", ""]),
    (None, ["", "", ""]),
])
def test_direction_hit_rules(direction, hits):
    row = ev(sig(direction=direction))
    assert [row[f"d{k}_direction_hit"] for k in (1, 5, 20)] == hits


def test_zero_return_is_neither_hit_nor_miss():
    row = ev(prices=make_prices(closes={D1: 100.0, D5: 100.0, D20: 100.0}))
    assert row["d1_direction_hit"] == "zero_return"


def test_summary_counts_na_and_hit_denominator():
    rows = [ev(sig("up", sid="a")), ev(sig("none", sid="b")), ev(sig("up", sid="c"), when=as_of(D1, 12, 0))]
    s = fe.summarize(rows)
    d1 = s["horizons"]["D1"]
    assert (d1["n_ok"], d1["n_na"]) == (2, 1)
    assert d1["na_by_reason"] == {"immature": 1}
    assert (d1["direction_hit_numerator"], d1["direction_hit_denominator"]) == (1, 1)  # 只有 a 計方向


def test_invalid_direction_rejected(tmp_path):
    p = tmp_path / "s.json"
    p.write_text(json.dumps({"signals": [sig(direction="buy")]}), encoding="utf-8")
    with pytest.raises(ValueError):
        fe.load_signals(p)


def test_naive_time_rejected():
    with pytest.raises(ValueError):
        fe.parse_dt("2026-10-30T21:00:00")


@pytest.mark.parametrize("bad", ["data/forward/out.csv", "fixtures/dev/out.csv", "agents/out.csv"])
def test_output_path_guard_refuses_agent_readable_locations(tmp_path, bad):
    with pytest.raises(PermissionError):
        fe.check_output_path(tmp_path / bad)


def test_output_path_guard_allows_evaluation_dir(tmp_path):
    fe.check_output_path(tmp_path / "evaluation" / "out.csv")


def test_runner_does_not_import_agent_modules():
    tree = ast.parse((ROOT / "scripts" / "forward_eval.py").read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert not imported & {"agents", "research_ui", "agent", "tools_impl"}


def _write_inputs(tmp_path, with_prices=True):
    (tmp_path / "evaluation").mkdir()
    signals = tmp_path / "signals.json"
    signals.write_text(json.dumps({"batch_id": "forward-batch-1", "signals": [
        sig("up", "2330", sid="fwd1-2330"), sig("none", "2317", sid="fwd1-2317")]}), encoding="utf-8")
    cal = tmp_path / "cal.csv"
    cal.write_text("date\n" + "\n".join(d.isoformat() for d in CAL) + "\n", encoding="utf-8")
    prices = tmp_path / "prices.csv"
    if with_prices:
        lines = ["ticker,trade_date,open,close,volume", f"2330,{ENTRY},100,101,1000",
                 f"2330,{D1},100,102,1000", f"2330,{D5},110,110,1000", f"2330,{D20},90,90,1000"]
        prices.write_text("\n".join(lines) + "\n", encoding="utf-8")
    else:
        prices.write_text("ticker,trade_date,open,close,volume\n", encoding="utf-8")
    return signals, prices, cal


def test_cli_end_to_end_and_deterministic(tmp_path):
    signals, prices, cal = _write_inputs(tmp_path)
    out1, out2 = tmp_path / "evaluation" / "o1.csv", tmp_path / "evaluation" / "o2.csv"
    args = ["--signals", str(signals), "--prices", str(prices), "--calendar", str(cal),
            "--as-of", as_of(D20).isoformat()]
    assert fe.main(args + ["--out", str(out1), "--summary-out", str(tmp_path / "evaluation" / "s.json")]) == 0
    assert fe.main(args + ["--out", str(out2)]) == 0
    assert out1.read_bytes() == out2.read_bytes()   # 同輸入同輸出
    rows = list(csv.DictReader(open(out1, encoding="utf-8-sig")))
    by_id = {r["signal_id"]: r for r in rows}
    assert by_id["fwd1-2330"]["d20_status"] == "ok" and by_id["fwd1-2330"]["d20_direction_hit"] == "miss"
    assert by_id["fwd1-2317"]["d1_na_reason"] == "missing_entry_open"   # 2317 沒價格 → NA 照列，不消失
    summary = json.loads((tmp_path / "evaluation" / "s.json").read_text(encoding="utf-8"))
    assert summary["n_signals"] == 2 and summary["horizons"]["D1"]["n_na"] == 1


def test_dry_run_before_cutoff_lists_every_signal_as_na(tmp_path):
    signals, prices, cal = _write_inputs(tmp_path, with_prices=False)
    out = tmp_path / "evaluation" / "dry.csv"
    _, summary = fe.run(signals, prices, cal, "2026-10-29T09:30:00+08:00", out)
    assert summary["horizons"]["D20"]["n_ok"] == 0
    assert summary["horizons"]["D20"]["na_by_reason"] == {"cutoff_not_reached": 2}
