"""tests/test_snapshot_holdout_guard.py — CR-W06：保留集執行前 snapshot.py 的防護（合成快照，不讀保留集內容）"""
from __future__ import annotations

import pytest

from agents import snapshot as S

CUT = "2026-08-15T17:00:00+08:00"


def _box(monkeypatch, case):
    monkeypatch.setattr(S, "load_case_snapshot", lambda sid: case)
    return S.SnapshotToolbox("2317", "snap-test-synthetic", CUT)


def test_undated_evidence_uses_captured_at_not_crash(monkeypatch):
    case = {"ticker": "2317", "evidences": [
        {"evidence_version_id": "ev-syn-undated", "title": "無發布時間", "available_at": None,
         "captured_at": "2026-08-10T10:00:00+08:00", "paragraph": "合成段落", "content_hash": "h"},
        {"evidence_version_id": "ev-syn-late-capture", "title": "截止後才擷取", "available_at": None,
         "captured_at": "2026-08-20T10:00:00+08:00", "paragraph": "合成段落", "content_hash": "h2"},
        {"evidence_version_id": "ev-syn-no-time", "title": "兩者皆無", "available_at": None,
         "captured_at": None, "paragraph": "合成段落", "content_hash": "h3"}]}
    box = _box(monkeypatch, case)
    s = box.search_evidence("2317", "合成", CUT, 5)
    assert [r["evidence_version_id"] for r in s["data"]] == ["ev-syn-undated"]
    assert s["data"][0]["available_at_basis"] == "captured_at_fallback"
    assert box.read_evidence("ev-syn-late-capture")["status"] == "no_data"
    assert box.read_evidence("ev-syn-no-time")["status"] == "no_data"


def test_simulated_no_data(monkeypatch):
    case = {"ticker": "2317", "evidences": [],
            "tool_simulation": {"tool_name": "get_financial_snapshot", "behavior": "no_data", "reason": "合成：查無"}}
    box = _box(monkeypatch, case)
    out = box("get_financial_snapshot", {"ticker": "2317", "cutoff": CUT})
    assert out == {"status": "no_data", "tool": "get_financial_snapshot", "data": None, "reason": "合成：查無"}
