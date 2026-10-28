"""tests/test_forward_inputs.py — W07-B 前瞻人工檔與 30 案凍結檔分開（build_snapshot_finmind.py V1.8）

不連網、不需 FINMIND_TOKEN：只測讀人工檔的函式與參數防呆。
1. --macro 指定的前瞻總經檔：cutoff 後發布的列略過，兩個序列都要有
2. --announce-extra：只能放前瞻季別（2026Q3），晚於 cutoff 略過，早於 cutoff 納入
3. --macro／--control 不可指向已凍結的 data/manual/*.csv；前瞻快照未給 --macro 即中止
"""
from __future__ import annotations

import importlib.util
import sys
from datetime import datetime
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("bsf", ROOT / "scripts" / "build_snapshot_finmind.py")


@pytest.fixture
def bsf(monkeypatch):
    mod = importlib.util.module_from_spec(SPEC)
    SPEC.loader.exec_module(mod)
    monkeypatch.setattr(mod, "CUTOFF_DT", datetime.fromisoformat("2026-10-30T21:00:00+08:00"))
    return mod


def _write(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


MACRO = (
    "series_id,observation_date,value,unit,available_at,source\n"
    "CPIAUCSL,2026-08,330.0,Index 1982-1984=100,2026-09-11T08:30:00-04:00,test\n"
    "CPIAUCSL,2026-10,331.0,Index 1982-1984=100,2026-11-12T08:30:00-05:00,test\n"
    "FEDFUNDS,2026-09,3.6,%,2026-10-01T16:15:00-04:00,test\n"
)


def test_forward_macro_skips_post_cutoff_rows(bsf, tmp_path, monkeypatch):
    monkeypatch.setattr(bsf, "MACRO_CSV", _write(tmp_path / "macro-2026-10-30.csv", MACRO))
    rows = bsf.load_macro()
    assert sorted((r["series_id"], r["observation_date"]) for r in rows) == [
        ("CPIAUCSL", "2026-08"), ("FEDFUNDS", "2026-09")]


def test_forward_macro_requires_both_series(bsf, tmp_path, monkeypatch):
    only_cpi = "\n".join(MACRO.splitlines()[:2]) + "\n"
    monkeypatch.setattr(bsf, "MACRO_CSV", _write(tmp_path / "m.csv", only_cpi))
    with pytest.raises(SystemExit, match="FEDFUNDS"):
        bsf.load_macro()


def _announce_base(tmp_path: Path, bsf) -> Path:
    lines = ["ticker,period,available_at,source_url"]
    dates = ["2025-08-15", "2025-11-14", "2026-03-16", "2026-05-14", "2026-08-14"]
    for t in bsf.TICKERS:
        for p, d in zip(bsf.PERIODS, dates):
            lines.append(f"{t},{p},{d}T18:00:00+08:00,https://mops.twse.com.tw/mops/#/web/t05st01")
    return _write(tmp_path / "announce_times.csv", "\n".join(lines) + "\n")


def test_announce_extra_adds_only_pre_cutoff_forward_quarters(bsf, tmp_path, monkeypatch):
    monkeypatch.setattr(bsf, "ANNOUNCE_CSV", _announce_base(tmp_path, bsf))
    extra = _write(tmp_path / "announce-2026-10-30.csv",
                   "ticker,period,available_at,source_url\n"
                   "2379,2026Q3,2026-10-29T18:10:00+08:00,https://mops.twse.com.tw/mops/#/web/t05st01\n"
                   "2454,2026Q3,2026-10-30T21:30:00+08:00,https://mops.twse.com.tw/mops/#/web/t05st01\n")
    monkeypatch.setattr(bsf, "ANNOUNCE_EXTRA_CSV", extra)
    out = bsf.load_announce()
    assert ("2379", "2026Q3") in out            # 10/29 公告，早於 cutoff → 納入
    assert ("2454", "2026Q3") not in out        # 21:30 公告，晚於 21:00 → 略過，不中止
    assert bsf.PERIODS_BY_TICKER["2379"][-1] == "2026Q3"
    assert bsf.PERIODS_BY_TICKER["2454"] == bsf.PERIODS


def test_announce_extra_rejects_base_periods(bsf, tmp_path, monkeypatch):
    monkeypatch.setattr(bsf, "ANNOUNCE_CSV", _announce_base(tmp_path, bsf))
    extra = _write(tmp_path / "x.csv", "ticker,period,available_at,source_url\n"
                   "2330,2026Q2,2026-08-11T18:46:58+08:00,https://mops.twse.com.tw/mops/#/web/t05st01\n")
    monkeypatch.setattr(bsf, "ANNOUNCE_EXTRA_CSV", extra)
    with pytest.raises(SystemExit, match="只能放前瞻季別"):
        bsf.load_announce()


@pytest.mark.parametrize("argv, msg", [
    (["--cutoff", "2026-10-30T21:00", "--out", "data/forward/x.json",
      "--evidence", "data/manual/forward/evidence-2026-10-30.csv",
      "--macro", "data/manual/macro.csv"], "已凍結"),
    (["--cutoff", "2026-10-30T21:00", "--out", "data/forward/x.json",
      "--evidence", "data/manual/forward/evidence-2026-10-30.csv"], "--macro"),
])
def test_cli_guards(bsf, monkeypatch, argv, msg):
    monkeypatch.setattr(sys, "argv", ["build_snapshot_finmind.py", *argv])
    with pytest.raises(SystemExit, match=msg):
        bsf.main()


EVID_HEAD = "evidence_version_id,source_id,ticker,title,published_at,captured_at,available_at,source_url,paragraph,abstract\n"


def test_evidence_without_official_time_uses_captured_at(bsf, tmp_path, monkeypatch):
    """V1.8：MOPS 每月營收頁沒有發言時間 → available_at 留空，以 captured_at（須早於 cutoff）判定。"""
    p = _write(tmp_path / "ev.csv", EVID_HEAD +
               "ev-a,mops_monthly_revenue,2317,月營收,,2026-10-28T21:18:00+08:00,,https://mops.twse.com.tw/x,營收 1 仟元,摘要\n")
    monkeypatch.setattr(bsf, "EVIDENCE_CSV", p)
    out = bsf.load_evidence({})
    assert out[0]["available_at"] == "" and out[0]["captured_at"].startswith("2026-10-28")


def test_evidence_captured_after_cutoff_is_rejected(bsf, tmp_path, monkeypatch):
    p = _write(tmp_path / "ev.csv", EVID_HEAD +
               "ev-b,mops_monthly_revenue,2317,月營收,,2026-10-31T09:00:00+08:00,,https://mops.twse.com.tw/x,營收 1 仟元,摘要\n")
    monkeypatch.setattr(bsf, "EVIDENCE_CSV", p)
    with pytest.raises(SystemExit, match="captured_at 晚於 cutoff"):
        bsf.load_evidence({})