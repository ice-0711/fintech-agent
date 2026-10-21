"""tests/test_tool_fixtures.py — W03-B 以 W02 契約 fixture 驗證六工具實作

每個 fixtures/tool-responses.json 的 TR-xx 都經 agents.tools.dispatch 執行
（含 tools.py 的參數驗證與角色權限），再依 check_mode 比對：
- exact       ：整個回傳必須相同
- status_only ：只比 status（reason 為參考文字）

需要 job 快照的 TR（job_snapshot_id 不為 null）走 agents/snapshot.py 的 SnapshotToolbox；
TR-06（CASE-15 正文不可讀）與 TR-31（CASE-26 逾時）由組長 2026-10-21 修正 snapshot.py 後
改為正式檢查（不再 xfail）。
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = json.loads((ROOT / "fixtures" / "tool-responses.json").read_text(encoding="utf-8"))
def _ids(case):
    return case["fixture_id"]


@pytest.fixture
def registered():
    """conftest 會在每個測試前清空註冊表；這裡重新掛上 B 的實作。"""
    from agents import register_tools

    register_tools.init_tools()
    from agents import tools
    return tools


@pytest.mark.parametrize("case", FIXTURES["responses"], ids=_ids)
def test_tool_fixture(case, registered):
    executor = None
    if case["job_snapshot_id"]:
        from agents.snapshot import SnapshotToolbox

        executor = SnapshotToolbox(case["input"].get("ticker", "2330"), case["job_snapshot_id"], case["job_cutoff"])

    actual = registered.dispatch(case["role"], case["tool"], case["input"], case["job_cutoff"], executor=executor)
    expected = case["expected_response"]

    assert set(actual) == {"status", "tool", "reason", "data"}, f"回傳頂層欄位不固定：{sorted(actual)}"
    assert actual["status"] == expected["status"], actual.get("reason")
    if actual["status"] != "ok":
        assert actual["data"] is None and actual["reason"]
    if case["check_mode"] == "exact":
        assert actual == expected


def test_status_enum_closed(registered):
    """所有 fixture 的 status 必須在契約列舉內。"""
    allowed = set(FIXTURES["status_enum"])
    assert {c["expected_response"]["status"] for c in FIXTURES["responses"]} <= allowed


def test_timeout_becomes_tool_error(registered):
    """register_tools 的逾時保護：慢工具 → TimeoutError → dispatch 回 tool_error。"""
    import time

    from agents import register_tools

    def slow(**_):
        time.sleep(1)
        return {"status": "ok", "tool": "read_evidence", "reason": None, "data": {}}

    registered.register_tool("read_evidence", register_tools.with_timeout("read_evidence", slow, seconds=0.1))
    out = registered.dispatch("researcher", "read_evidence", {"evidence_version_id": "ev-x"})
    assert out["status"] == "tool_error" and "逾時" in out["reason"] and out["data"] is None


def test_growth_rate_nonpositive_base_is_na():
    """基期 ≤ 0 時成長率為 NA（不除以 abs 硬算）；正基期照常計算。"""
    from agents.calculator import calculate_growth_rate

    for prev in (-100.0, 0.0):
        r = calculate_growth_rate(-50.0, prev)
        assert r["result_value"] is None and r["is_applicable"] is False and "NA" in r["reason"]
    ok = calculate_growth_rate(1521.83, 1503.69)          # 2454 2026Q2 vs 2025Q2 單季營收
    assert ok["is_applicable"] and ok["result_value"] == 0.0121


def test_money_100m_keeps_null():
    """financial_analyzer.money_100m 缺值回 None，不補 0。"""
    from financial_analyzer import fmt_100m, money_100m

    assert money_100m(None) is None
    assert money_100m("abc") is None
    assert money_100m(0) == 0.0
    assert fmt_100m(None) == "無資料"


def test_read_evidence_does_not_invent_url(tmp_path, monkeypatch):
    """快照沒有 source_url 時回傳 None，不自動填通用 MOPS 網址。"""
    from agents import tools_impl

    snap = {"evidences": [{"evidence_version_id": "ev-t", "source_id": "s", "ticker": "2330",
                           "paragraph": "x", "available_at": "2026-01-01T00:00:00+08:00", "content_hash": "h"}]}
    path = tmp_path / "snap.json"
    path.write_text(json.dumps(snap), encoding="utf-8")
    monkeypatch.setattr(tools_impl, "SNAPSHOT_PATH", path)
    out = tools_impl.read_evidence(evidence_version_id="ev-t")
    assert out["status"] == "ok" and out["data"]["source_url"] is None


def test_unknown_time_not_available(tmp_path, monkeypatch):
    """available_at 與 captured_at 皆無 → 不可得；只有 captured_at → 以它判定。"""
    from agents import tools_impl

    snap = {"evidences": [
        {"evidence_version_id": "ev-a", "source_id": "s", "ticker": "2330", "paragraph": "營收",
         "available_at": None, "captured_at": "2026-08-05T10:00:00+08:00", "content_hash": "h"},
        {"evidence_version_id": "ev-b", "source_id": "s", "ticker": "2330", "paragraph": "營收",
         "available_at": None, "captured_at": None, "content_hash": "h"}]}
    path = tmp_path / "snap.json"
    path.write_text(json.dumps(snap), encoding="utf-8")
    monkeypatch.setattr(tools_impl, "SNAPSHOT_PATH", path)

    early = tools_impl.search_evidence(ticker="2330", query="營收", cutoff="2026-08-01T00:00:00+08:00", limit=5)
    assert early["status"] == "no_data"
    late = tools_impl.search_evidence(ticker="2330", query="營收", cutoff="2026-08-06T00:00:00+08:00", limit=5)
    assert [r["evidence_version_id"] for r in late["data"]] == ["ev-a"]
    assert late["data"][0]["available_at_basis"] == "captured_at_fallback"


def test_ttm_rejects_unverified_and_gaps(tmp_path, monkeypatch):
    """TTM：含 unverified EPS 或季度不連續 → null 並附原因。"""
    from agents import tools_impl

    def q(period, eps_source="mops_direct"):
        return {"period": period, "period_basis": "single_quarter", "available_at": "2026-01-01T00:00:00+08:00",
                "eps": 1.0, "eps_source": eps_source, "free_cash_flow": 1.0}

    for quarters, needle in [
        ([q("2025Q1"), q("2025Q2", "unverified"), q("2025Q3"), q("2025Q4")], "unverified"),
        ([q("2024Q4"), q("2025Q2"), q("2025Q3"), q("2025Q4")], "不連續"),
    ]:
        path = tmp_path / "snap.json"
        path.write_text(json.dumps({"financials": {"2454": {"quarters": quarters}}}), encoding="utf-8")
        monkeypatch.setattr(tools_impl, "SNAPSHOT_PATH", path)
        out = tools_impl.get_financial_snapshot(ticker="2454", cutoff="2026-09-30T00:00:00+08:00")
        assert out["data"]["metrics"]["eps_ttm"] is None
        assert needle in out["data"]["missing_reason"]