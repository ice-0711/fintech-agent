"""Export real development runs to D's dev-runs.jsonl (W06-D format, evaluation/d-drafts/dev-runs-schema.md).

    .venv/bin/python scripts/export_dev_runs.py [--db tmp/dev_v14.sqlite3] [--out evaluation/d-drafts/dev-runs.jsonl]

Every value comes from the job store (jobs, events, usage ledger); nothing is estimated.
Missing values are null with the reason in `note`. Holdout cases are refused.
Scores are not written here (D's rubric, rubric-v1-final.md §6).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def commit_at(iso: str) -> str | None:
    """Repo commit that was HEAD when the run started (last commit before that time)."""
    out = subprocess.run(["git", "log", "-1", f"--before={iso}", "--format=%h", "main"],
                         capture_output=True, text=True, cwd=ROOT).stdout.strip()
    return out or None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="tmp/dev_v14.sqlite3")
    ap.add_argument("--out", default="evaluation/d-drafts/dev-runs.jsonl")
    args = ap.parse_args()
    dev = {c["source_snapshot_id"]: c for c in
           json.loads((ROOT / "evaluation" / "dev-cases.json").read_text(encoding="utf-8"))["cases"]}
    conn = sqlite3.connect(ROOT / args.db)
    conn.row_factory = sqlite3.Row
    rows = []
    for job_row in conn.execute("select job_id, data from research_jobs order by created_at"):
        job = json.loads(job_row["data"])
        case = dev.get(job["source_snapshot_id"])
        if case is None:
            sys.exit(f"{job['source_snapshot_id']} 不在開發集，拒絕匯出（保留集不得出現）")
        events = [dict(e) | {"detail": json.loads(e["detail"])} for e in conn.execute(
            "select event_seq, created_at, role, event_type, tool_name, detail from job_events where job_id = ? "
            "order by event_seq", (job["job_id"],))]
        calls = [e["detail"] for e in events if e["event_type"] == "model_call"]
        usage = [c.get("usage") or {} for c in calls]
        tin = [u.get("prompt_token_count") for u in usage]
        tout = [(u.get("candidates_token_count") or 0) + (u.get("thoughts_token_count") or 0) for u in usage]
        errors = [e["detail"] for e in events if e["event_type"] == "model_error"]
        leased = next((e["created_at"] for e in events if e["event_type"] in ("lease_acquired", "lease_recovered")), None)
        created, updated = datetime.fromisoformat(job["created_at"]), datetime.fromisoformat(job["updated_at"])
        prompts = sorted({c.get("prompt_version") for c in calls if c.get("prompt_version")})
        notes = ["由組長自 job 紀錄匯出（scripts/export_dev_runs.py），待 D 核對",
                 "只跑 dual 模式；single 未跑、workflow 模式尚未實作"]
        if None in tin:
            notes.append("部分發送無 usage 回傳，tokens_in 為已知值合計")
        rows.append({
            "run_id": "r-" + hashlib.sha256(job["job_id"].encode()).hexdigest()[:8],
            "case_id": case["case_id"],
            "mode": job["mode"],
            "run_mode": "live",
            "model_id": job.get("model_id"),
            "repo_commit": commit_at(job["created_at"]),
            "prompt_versions": prompts,  # system prompt files: agents/prompts/ at repo_commit
            "status": job["status"],
            "stop_reason": job.get("stop_reason"),
            "model_sends": job.get("calls_used"),
            "tool_calls": job.get("tool_calls_used"),
            "supplement_rounds": job.get("supplement_rounds"),
            "tokens_in": sum(t for t in tin if t is not None) if calls else None,
            "tokens_out": sum(tout) if calls else None,
            "latency_active_s": job.get("active_seconds"),
            "latency_queue_s": round((datetime.fromisoformat(leased) - created).total_seconds(), 1) if leased else None,
            "latency_total_s": round((updated - created).total_seconds(), 1),
            "error": "; ".join(f"{e.get('code')} {e.get('error') or ''}".strip() for e in errors) or None,
            "started_at": job["created_at"],
            "note": "；".join(notes),
        })
    out = ROOT / args.out
    out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    print(f"wrote {len(rows)} runs to {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
