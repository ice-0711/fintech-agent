"""tests/test_forward_guard.py — W07-B 前瞻快照與工具防護（不耗 LLM）

驗證 agents/tools_impl.py W07 版新增的三件事，且未設定時與 W06 凍結行為相同：
1. use_snapshot()／FINTECH_SNAPSHOT_PATH 切換快照（前瞻批次 1–3）
2. 快照 cutoff_at 防護：請求的 cutoff 晚於快照截止時間時一律截斷，cutoff 後資料不回流 Agent
3. evidence_version_id 格式白名單（W08-B「未授權 ID 不通過工具」）
"""
from __future__ import annotations

import json

import pytest

from agents import tools_impl as t

FWD_CUTOFF = "2026-10-30T21:00:00+08:00"
LATE = "2026-12-31T21:00:00+08:00"


def _q(period, available_at, eps):
    return {"period": period, "period_basis": "single_quarter", "available_at": available_at,
            "revenue": 100.0, "operating_income": 10.0, "net_income": 8.0, "operating_cash_flow": 9.0,
            "capital_expenditure": 1.0, "free_cash_flow": 8.0, "eps": eps, "eps_source": "mops_direct",
            "shares_outstanding": 100.0, "bvps": 50.0, "net_debt": -5.0, "source_id": "src-x",
            "snapshot_id": f"snap-x-{period}", "content_hash": "h"}


@pytest.fixture
def fwd(tmp_path):
    snap = {
        "cutoff": "2026-10-30",
        "cutoff_at": FWD_CUTOFF,
        "snapshot_mode": "forward",
        "evidences": [
            {"evidence_version_id": "ev-fwd-ok", "source_id": "s1", "ticker": "2454", "title": "九月營收",
             "available_at": "2026-10-09T17:00:00+08:00", "paragraph": "營收 1 億", "abstract": "營收",
             "content_hash": "a"},
            {"evidence_version_id": "ev-fwd-late", "source_id": "s2", "ticker": "2454", "title": "十月營收",
             "available_at": "2026-11-10T17:00:00+08:00", "paragraph": "營收 2 億", "abstract": "營收",
             "content_hash": "b"},
        ],
        "financials": {"2454": {"company_name": "聯發科", "quarters": [
            _q("2025Q4", "2026-02-26T17:08:56+08:00", 14.4),
            _q("2026Q1", "2026-04-30T17:58:34+08:00", 15.17),
            _q("2026Q2", "2026-07-31T18:41:57+08:00", 15.28),
            _q("2026Q3", "2026-10-31T17:10:00+08:00", 16.0),   # 晚於快照 cutoff
        ]}},
        "macro": [{"series_id": "FEDFUNDS", "observation_date": "2026-10", "value": 3.5, "unit": "%",
                   "available_at": "2026-11-02T00:00:00-05:00"}],
        "prices": {"2454": [{"trade_date": "2026-10-30", "close": 1000.0},
                            {"trade_date": "2026-11-02", "close": 1100.0}]},
        "source_manifest": {"raw_files": []},
    }
    path = tmp_path / "fwd.json"
    path.write_text(json.dumps(snap, ensure_ascii=False), encoding="utf-8")
    return path


def test_use_snapshot_switches_and_restores(fwd):
    before = t._snapshot_path()
    with t.use_snapshot(fwd) as p:
        assert p == fwd and t._snapshot_path() == fwd
    assert t._snapshot_path() == before


def test_use_snapshot_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        with t.use_snapshot(tmp_path / "nope.json"):
            pass


def test_env_var_selects_snapshot(fwd, monkeypatch):
    monkeypatch.setenv(t.SNAPSHOT_ENV, str(fwd))
    assert t._snapshot_path() == fwd


def test_post_cutoff_evidence_never_returned(fwd):
    with t.use_snapshot(fwd):
        s = t.search_evidence(ticker="2454", query="營收", cutoff=LATE, limit=5)
        assert [r["evidence_version_id"] for r in s["data"]] == ["ev-fwd-ok"]
        r = t.read_evidence(evidence_version_id="ev-fwd-late")
        assert r["status"] == "no_data" and "截止" in r["reason"]
        assert t.read_evidence(evidence_version_id="ev-fwd-ok")["status"] == "ok"


def test_post_cutoff_quarter_price_macro_excluded(fwd):
    with t.use_snapshot(fwd):
        f = t.get_financial_snapshot(ticker="2454", cutoff=LATE)
        assert f["data"]["latest_period"] == "2026Q2"
        p = t.get_price_window(ticker="2454", end_at=LATE, sessions=1)
        assert p["data"]["closes"][-1]["trade_date"] == "2026-10-30"
        m = t.get_macro_snapshot(cutoff=LATE, series_ids=["FEDFUNDS"])
        assert m["status"] == "no_data"


@pytest.mark.parametrize("bad", ["", "https://evil.example/x", "../../data/raw", "ev 1", "ev;drop", "x" * 200, None, 123])
def test_evidence_id_format_rejected(bad):
    out = t.read_evidence(evidence_version_id=bad)
    assert out["status"] == "invalid_input" and out["data"] is None


def test_well_formed_unknown_id_is_no_data():
    assert t.read_evidence(evidence_version_id="ev-non-existent-999")["status"] == "no_data"


def test_frozen_snapshot_has_no_cutoff_guard():
    """30 案凍結快照沒有 cutoff_at：不截斷，行為與 W06 相同。"""
    snap = t._load_snapshots()
    assert "cutoff_at" not in snap or snap["cutoff_at"] is None or t._snapshot_cutoff(snap) is not None
    if "cutoff_at" not in snap:
        assert t._snapshot_cutoff(snap) is None
