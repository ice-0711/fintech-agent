"""Forward batch research: run the three research tickers against a frozen forward snapshot.

    .venv/bin/python scripts/forward_research.py --live [--batch 2]

Reads research/forward-batch-<N>.json (default 1), refuses a snapshot whose sha256 differs from the record,
and writes research/forward-batch-<N>-reports.json. Nothing is published here: reports still need the lead's approval.
Jobs live in their own tmp/ database so D's calibration export stays dev-only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))

from dev_traces import run  # noqa: E402

from agents.budget import ProjectQuota  # noqa: E402
from agents.provider import make_client  # noqa: E402
from agents.research_graph import RESEARCHER_PROMPT_VERSION  # noqa: E402
from agents.review_contract import REVIEWER_PROMPT_VERSION  # noqa: E402
from agents.store import JobStore  # noqa: E402

FOCUS = "前瞻批次 {n}：依截止時間前可得資料整理總經、基本面與估值，資料不足照實說明"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true", required=True)
    ap.add_argument("--batch", type=int, default=1)
    n = ap.parse_args().batch
    out = ROOT / "research" / f"forward-batch-{n}-reports.json"
    if out.exists():
        sys.exit(f"{out.relative_to(ROOT)} 已存在，不重跑（重跑等於挑結果），停止。")
    rec = json.loads((ROOT / "research" / f"forward-batch-{n}.json").read_text(encoding="utf-8"))
    snap = ROOT / rec["snapshot_file"]
    if hashlib.sha256(snap.read_bytes()).hexdigest() != rec["snapshot_sha256"]:
        sys.exit("前瞻快照的 sha256 與紀錄不符，停止。")
    os.environ["FINTECH_SNAPSHOT_PATH"] = rec["snapshot_file"]
    baseline = json.loads((ROOT / "handoff" / "quota-baseline.json").read_text(encoding="utf-8"))
    quota = ProjectQuota.from_baseline(baseline)
    model_id = os.getenv("GEMINI_MODEL")
    if model_id != quota.model_id:
        sys.exit(f"GEMINI_MODEL={model_id} 與 quota-baseline.json 的 {quota.model_id} 不一致，停止。")
    store, client = JobStore(ROOT / "tmp" / f"forward_batch{n}.sqlite3"), make_client()
    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip()
    reports = []
    for i, ticker in enumerate(rec["research_tickers"]):
        if i:
            time.sleep(60)  # stay under 80 % of RPM between jobs
        case = {"case_id": f"fwd{n}-{ticker}", "ticker": ticker, "cutoff_at": rec["signal_cutoff_at"],
                "source_snapshot_id": f"snap-fwd{n}-{rec['snapshot_sha256'][:12]}", "title": FOCUS.format(n=n)}
        result = run(store, case, client, model_id, quota, "live")
        print(ticker, result["status"], result["stop_reason"], result["path"], flush=True)
        reports.append({"signal_id": case["case_id"], "ticker": ticker, "direction": "none", **result})
    out.write_text(json.dumps({"batch_id": rec["batch_id"], "signal_cutoff_at": rec["signal_cutoff_at"],
                               "snapshot_sha256": rec["snapshot_sha256"], "commit": commit, "model_id": model_id,
                               "prompt_versions": {"researcher": RESEARCHER_PROMPT_VERSION, "reviewer": REVIEWER_PROMPT_VERSION},
                               "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                               "published": False, "reports": reports}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("wrote", out.relative_to(ROOT))


if __name__ == "__main__":
    main()
