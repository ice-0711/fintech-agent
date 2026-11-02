"""Forward batch freeze (W08-L): A falls back to B when FinMind lacks the new quarter, the record keeps
the sha256 and reason, and nothing is overwritten. The builder is faked; no network."""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import freeze_forward_batch as fz  # noqa: E402

REAL = Path(__file__).resolve().parents[1]
SNAP = REAL / "data" / "forward" / "financial-snapshots-2026-10-30.json"


@pytest.fixture
def repo(tmp_path, monkeypatch):
    (tmp_path / "research").mkdir()
    manual = tmp_path / "data" / "manual" / "forward"
    manual.mkdir(parents=True)
    for k in ("evidence", "macro", "announce", "mops-control"):
        (manual / f"{k}-2026-10-30.csv").write_text("x\n", encoding="utf-8")
    src = {"signal_cutoff_at": "2026-10-30T21:00:00+08:00", "research_tickers": ["2330", "2317", "2454"],
           "comparison_only": {"subject": "2454"}, "snapshot": {"file": "data/forward/snap-9.json"}}
    (tmp_path / "research" / "forward-batch-9-sources.json").write_text(json.dumps(src), encoding="utf-8")
    calls = []

    def fake_build(args):
        calls.append(args)
        if "--announce-extra" in args:
            return subprocess.CompletedProcess(args, 1, "", "[中止] FinMind 無 2454 2026Q3 科目")
        out = tmp_path / args[args.index("--out") + 1]
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(SNAP, out)
        return subprocess.CompletedProcess(args, 0, "ok", "")

    monkeypatch.setattr(fz, "ROOT", tmp_path)
    monkeypatch.setattr(fz, "build", fake_build)
    monkeypatch.setattr(sys, "argv", ["freeze", "--batch", "9"])
    return tmp_path, calls


def test_a_falls_back_to_b_and_records_why(repo):
    root, calls = repo
    fz.main()
    rec = json.loads((root / "research" / "forward-batch-9.json").read_text(encoding="utf-8"))
    assert len(calls) == 2 and "--announce-extra" not in calls[1]
    assert rec["q3_decision"].startswith("B：A 中止") and "2026Q3" in rec["q3_decision"]
    assert rec["snapshot_sha256"] == "3ec3d8a09028d6f8d58bab6e71b613902572a23cee888f25d6b4b731552e5cca"
    assert rec["periods_used"]["2454"] == "2026Q2" and rec["generated_late"]  # batch 1 was ~22 h late
    assert not any(rec["no_backfill_check"].values())


def test_never_overwrites(repo):
    root, _ = repo
    fz.main()
    with pytest.raises(SystemExit, match="已存在"):
        fz.main()


def test_missing_manual_files_stop(repo):
    root, _ = repo
    (root / "data" / "manual" / "forward" / "macro-2026-10-30.csv").unlink()
    with pytest.raises(SystemExit, match="未備妥"):
        fz.main()
