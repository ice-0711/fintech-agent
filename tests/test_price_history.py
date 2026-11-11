"""Price history extension (lead 11/11, decision 25). Offline; reads the global snapshot only, no case content."""

from __future__ import annotations

import json
from pathlib import Path

from agents.tools_impl import get_price_window

ROOT = Path(__file__).resolve().parents[1]
SNAP = json.loads((ROOT / "data" / "financial-snapshots.json").read_text(encoding="utf-8"))


def _raws(ticker: str) -> list[dict]:
    return [r for r in SNAP["source_manifest"]["raw_files"]
            if r["dataset"] == "TaiwanStockPrice" and r["data_id"] == ticker]


def test_every_ticker_has_a_sorted_unique_history_ending_at_the_snapshot_cutoff():
    for ticker, rows in SNAP["prices"].items():
        dates = [r["trade_date"] for r in rows]
        assert dates == sorted(set(dates)) and dates[-1] == SNAP["cutoff"] and len(dates) > 400, ticker
        assert all(r["close"] > 0 for r in rows), ticker


def test_a_midyear_window_is_served_without_looking_ahead():
    res = get_price_window(ticker="2330", end_at="2026-08-12T17:00:00+08:00", sessions=20)
    closes = res["data"]["closes"]
    assert res["status"] == "ok" and len(closes) == 20
    assert closes[-1]["trade_date"] == "2026-08-11"  # 08-12 closes at 17:30, after the 17:00 cutoff
    assert res["data"]["available_at"] == "2026-08-11T17:30:00+08:00"


def test_content_hash_points_at_the_raw_file_that_covers_the_window():
    old, new = _raws("2454")
    assert old["start"] == "2026-09-10" and new["start"] == "2025-01-01"
    late = get_price_window(ticker="2454", end_at="2026-09-30T17:30:00+08:00", sessions=5)
    assert late["data"]["content_hash"] == old["sha256"]  # unchanged: the TWSE-checked five days keep their source
    for kwargs in ({"end_at": "2026-08-03T17:00:00+08:00", "sessions": 5},
                   {"end_at": "2026-09-30T17:30:00+08:00", "sessions": 20}):
        res = get_price_window(ticker="2454", **kwargs)
        assert res["status"] == "ok" and res["data"]["content_hash"] == new["sha256"]


def test_before_the_history_starts_is_still_no_data():
    assert get_price_window(ticker="2330", end_at="2025-01-02T17:00:00+08:00", sessions=1)["status"] == "no_data"
