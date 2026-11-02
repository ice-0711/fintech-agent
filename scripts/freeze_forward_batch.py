"""Freeze one forward batch snapshot right after its Friday 21:00 cutoff (W08-L / W09-L).

    .venv/bin/python scripts/freeze_forward_batch.py --batch 2

Reads research/forward-batch-<N>-sources.json (B), runs scripts/build_snapshot_finmind.py once with B's
manual files and writes research/forward-batch-<N>.json with the sha256. Q3 rule (lead 10/31): try with
the new-quarter announce/control files first (A); if the builder stops because FinMind has no such
quarter yet, build without them (B) and record why. Never overwrites a snapshot or a record, and refuses
to run before the cutoff. FINMIND_TOKEN comes from .env (loaded by `import agents`, value never printed).
Research runs afterwards with scripts/forward_research.py --live --batch <N>.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import agents  # noqa: E402,F401  (loads .env for FINMIND_TOKEN)

BUILDER = ROOT / "scripts" / "build_snapshot_finmind.py"
LATE_AFTER = timedelta(hours=3)


def build(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(BUILDER), *args], cwd=ROOT, capture_output=True, text=True)


def tail(proc: subprocess.CompletedProcess, n: int = 3) -> str:
    return " / ".join((proc.stdout + proc.stderr).strip().splitlines()[-n:])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", type=int, required=True)
    n = ap.parse_args().batch
    src = json.loads((ROOT / "research" / f"forward-batch-{n}-sources.json").read_text(encoding="utf-8"))
    cutoff = datetime.fromisoformat(src["signal_cutoff_at"])
    if datetime.now(timezone.utc) < cutoff:
        sys.exit(f"還沒到截止時間 {src['signal_cutoff_at']}，停止。")
    day = cutoff.date().isoformat()
    manual = ROOT / "data" / "manual" / "forward"
    files = {k: manual / f"{k}-{day}.csv" for k in ("evidence", "macro", "announce", "mops-control")}
    missing = [p.name for k, p in files.items() if k in ("evidence", "macro") and not p.exists()]
    if missing:
        sys.exit(f"B 的人工檔未備妥：{', '.join(missing)}，停止。")
    out = Path(src["snapshot"]["file"])
    record = ROOT / "research" / f"forward-batch-{n}.json"
    for p in (ROOT / out, record):
        if p.exists():
            sys.exit(f"{p.relative_to(ROOT)} 已存在，不覆蓋，停止。")

    base = ["--cutoff", cutoff.strftime("%Y-%m-%dT%H:%M"), "--out", str(out),
            "--evidence", str(files["evidence"].relative_to(ROOT)), "--macro", str(files["macro"].relative_to(ROOT))]
    extra = []
    if files["announce"].exists():
        extra += ["--announce-extra", str(files["announce"].relative_to(ROOT))]
    if files["mops-control"].exists():
        extra += ["--control", str(files["mops-control"].relative_to(ROOT))]
    proc, q3 = build(base + extra), "A：新季別公告與對帳檔一併納入" if extra else "B：本批沒有新季別人工檔"
    if proc.returncode and extra:
        reason = tail(proc)
        proc, q3 = build(base), f"B：A 中止（{reason}），改不帶新季別人工檔"
    if proc.returncode:
        sys.exit(f"快照產生失敗：{tail(proc, 6)}")

    snap_path = ROOT / out
    snap = json.loads(snap_path.read_text(encoding="utf-8"))
    generated = datetime.fromisoformat(snap["generated_at"])
    late = generated - cutoff
    quarters_after = sum(1 for f in snap["financials"].values() for q in f["quarters"]
                         if q.get("available_at") and datetime.fromisoformat(q["available_at"]) > cutoff)
    evid_after = sum(1 for e in snap["evidences"]
                     if e.get("available_at") and datetime.fromisoformat(e["available_at"]) > cutoff)
    prices_after = sum(1 for rows in snap["prices"].values() for r in rows if r["trade_date"] > day)
    rec = {
        "batch_id": f"forward-batch-{n}",
        "task": src.get("task") or ("W08-L" if n == 2 else "W09-L"),
        "signal_cutoff_at": src["signal_cutoff_at"],
        "snapshot_file": str(out),
        "snapshot_sha256": hashlib.sha256(snap_path.read_bytes()).hexdigest(),
        "generated_at": snap["generated_at"],
        "generated_late": f"晚於截止 {late.total_seconds() / 3600:.1f} 小時；不重抓覆蓋。" if late > LATE_AFTER else None,
        "sources_file": f"research/forward-batch-{n}-sources.json",
        "builder_args": base + (extra if q3.startswith("A") else []),
        "research_tickers": src["research_tickers"],
        "comparison_only": src["comparison_only"],
        "periods_used": {t: p[-1] for t, p in snap["periods_by_ticker"].items()},
        "q3_decision": q3,
        "direction": "none（照第 1 批；只展示 1／5／20 日報酬，不算命中率）",
        "raw_files": [r["file"] for r in snap["source_manifest"]["raw_files"]],
        "no_backfill_check": {"evidence_available_after_cutoff": evid_after,
                              "quarters_available_after_cutoff": quarters_after,
                              f"prices_after_{day.replace('-', '_')}": prices_after},
        "research_reports": {"status": "未執行", "run": f".venv/bin/python scripts/forward_research.py --live --batch {n}"},
    }
    record.write_text(json.dumps(rec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("wrote", record.relative_to(ROOT), rec["snapshot_sha256"][:12], q3, rec["no_backfill_check"], flush=True)
    if any(rec["no_backfill_check"].values()):
        sys.exit("有截止後才可得的資料，請組長與 B 核對後再跑研究。")


if __name__ == "__main__":
    main()
