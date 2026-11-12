"""W09-B 前瞻 9 份總表：9 列都在、快照指紋不符就停、不填報酬、不寫進 Agent 讀的位置。"""
import hashlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_forward_manifest as bfm  # noqa: E402


def _snap(late: bool = False) -> dict:
    q = {"period": "2026Q2", "available_at": "2026-08-12T13:30:00+08:00"}
    price = {"trade_date": "2026-10-30", "open": 10.0, "close": 11.0}
    ev = {"evidence_version_id": "ev-1", "ticker": "2330",
          "available_at": "2026-10-31T09:00:00+08:00" if late else "2026-10-08T13:54:04+08:00"}
    return {"cutoff_at": "2026-10-30T21:00:00+08:00",
            "financials": {t: {"quarters": [q]} for t in ("2330", "2317", "2454")},
            "prices": {t: [price] for t in ("2330", "2317", "2454")},
            "evidences": [ev],
            "macro": [{"series_id": "FEDFUNDS", "observation_date": "2026-09",
                       "available_at": "2026-10-02T00:00:00-04:00"}]}


def _fake_repo(tmp_path: Path, crlf: bool = False, recorded: str | None = None, late: bool = False) -> Path:
    (tmp_path / "research").mkdir()
    (tmp_path / "evaluation").mkdir()
    (tmp_path / "data" / "forward").mkdir(parents=True)
    snap_bytes = (json.dumps(_snap(late), indent=2) + "\n").encode()
    if crlf:
        snap_bytes = snap_bytes.replace(b"\n", b"\r\n")
    snap = tmp_path / "data" / "forward" / "financial-snapshots-2026-10-30.json"
    snap.write_bytes(snap_bytes)
    rec = {
        "batch_id": "forward-batch-1", "signal_cutoff_at": "2026-10-30T21:00:00+08:00",
        "snapshot_file": "data/forward/financial-snapshots-2026-10-30.json",
        "snapshot_sha256": recorded or hashlib.sha256(snap_bytes.replace(b"\r\n", b"\n")).hexdigest(),
        "generated_at": "2026-10-31T19:08:32+08:00", "periods_used": {"2330": "2026Q2"},
        "research_reports": {"results": {"2330": {"job_id": "j1", "status": "insufficient_evidence",
                                                  "stop_reason": "researcher_insufficient"}}},
    }
    (tmp_path / "research" / "forward-batch-1.json").write_text(json.dumps(rec), encoding="utf-8")
    return tmp_path


def test_always_nine_rows_even_before_any_batch(tmp_path):
    (tmp_path / "research").mkdir()
    m = bfm.build(tmp_path)
    assert len(m["signals"]) == 9
    assert {r["batch_status"] for r in m["signals"]} == {"pending_not_frozen"}
    assert [r["signal_id"] for r in m["signals"][:3]] == ["fwd1-2330", "fwd1-2317", "fwd1-2454"]


def test_failed_and_missing_rows_are_kept(tmp_path):
    m = bfm.build(_fake_repo(tmp_path))
    by = {r["signal_id"]: r for r in m["signals"]}
    assert by["fwd1-2330"]["job_status"] == "insufficient_evidence"
    assert by["fwd1-2317"]["batch_status"] == "frozen_research_not_run"
    assert by["fwd2-2330"]["batch_status"] == "pending_not_frozen"
    assert m["summary"]["signals"] == 9


def test_snapshot_hash_mismatch_stops(tmp_path):
    with pytest.raises(SystemExit):
        bfm.build(_fake_repo(tmp_path, recorded="0" * 64))


def test_windows_crlf_copy_still_verifies(tmp_path):
    m = bfm.build(_fake_repo(tmp_path, crlf=True))
    assert m["signals"][0]["snapshot_verified"] == "ok_after_lf"


def test_no_returns_or_direction_are_filled(tmp_path):
    m = bfm.build(_fake_repo(tmp_path))
    assert m["summary"]["direction_up_down"] == 0
    for r in m["signals"]:
        assert r["returns"].startswith("由 D 的")
        assert not any(k.startswith(("ret_", "hit")) for k in r)


def test_expected_trading_days():
    days = bfm.trading_days_after(bfm.date(2026, 11, 13), 20)
    assert days[0].isoformat() == "2026-11-16" and days[4].isoformat() == "2026-11-20"
    assert days[19].isoformat() == "2026-12-11"


def test_output_into_agent_paths_is_refused(tmp_path):
    root = _fake_repo(tmp_path)
    with pytest.raises(SystemExit):
        bfm.main(["--root", str(root), "--json-out", "data/forward/m.json"])
    with pytest.raises(SystemExit):
        bfm.main(["--root", str(root), "--csv-out", "fixtures/m.csv"])


def test_real_repo_batch_1_matches_lead_record():
    if not (ROOT / "research" / "forward-batch-1.json").exists():
        pytest.skip("repo 沒有第 1 批紀錄")
    m = bfm.build(ROOT)
    rec = json.loads((ROOT / "research" / "forward-batch-1.json").read_text(encoding="utf-8"))
    by = {r["signal_id"]: r for r in m["signals"]}
    for t, res in rec["research_reports"]["results"].items():
        assert by[f"fwd1-{t}"]["job_id"] == res["job_id"]
        assert by[f"fwd1-{t}"]["job_status"] == res["status"]
    assert by["fwd1-2317"]["published"] is True
    assert by["fwd1-2330"]["d20_date_expected"] == "2026-11-27"


def test_published_reports_follow_decision_20():
    """決策第 20 節：11/09 發布 2330 第 2 版（第 2 批快照）與 2317 第 2 版（第 1 批快照）。"""
    by = {r["signal_id"]: r for r in bfm.build(ROOT)["signals"]}
    assert by["fwd2-2330"]["published"] is True
    assert by["fwd2-2330"]["report_version"].startswith("rv-db6b0e1b")
    assert "rv-2ed6652e" in by["fwd1-2317"]["report_version"]
    assert sorted(s for s, r in by.items() if r["published"]) == ["fwd1-2317", "fwd2-2330"]


def test_agent_version_per_row(tmp_path):
    m = bfm.build(_fake_repo(tmp_path))
    v = {r["signal_id"][:4]: r["agent_version"] for r in m["signals"]}
    assert v == {"fwd1": "v1", "fwd2": "v1", "fwd3": "v2"}


def test_input_after_cutoff_stops(tmp_path):
    with pytest.raises(SystemExit):
        bfm.build(_fake_repo(tmp_path, late=True))


def test_signal_price_and_basis_recorded(tmp_path):
    r = bfm.build(_fake_repo(tmp_path))["signals"][0]
    assert r["signal_price_date"] == "2026-10-30" and r["signal_close"] == 11.0
    assert r["signal_price_available_at"] == "2026-10-30T17:30:00+08:00"
    assert r["price_basis"].startswith("raw_unadjusted")
    assert r["evidence_ids"] == "ev-1" and r["inputs_checked"] == 4