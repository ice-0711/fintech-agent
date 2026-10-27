"""W07-A: produce the three acceptance PDFs through the real publication path.

MOCK revise_then_pass jobs (scripted model decisions, real snapshot tool results) for 2330, 2317
and 2454 are run to completion, then each goes through the lead's ReportStore exactly like the
website: create_version → approve(seen hash) → publish (render PDF → Storage → read-back hash).
Nothing here calls an LLM or the network.

    python scripts/w07_acceptance_pdfs.py [--out reports/v12-online-pdf] [--workdir DIR]

Writes <out>/<ticker>-<rv>.pdf (acceptance copies, read back from Storage, not the permanent copy),
<out>/<ticker>-<rv>.json (the approved report JSON) and <out>/manifest.json.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agents.publication import LocalStorage, ReportStore  # noqa: E402
from research_ui.mock_jobs import MockJobs  # noqa: E402

CUTOFF = "2026-09-30T17:30:00+08:00"  # = peer snapshot cutoff; 9/30 close is available from 17:30
TICKERS = ("2330", "2317", "2454")


class Clock:
    def __init__(self) -> None:
        self.now = 1_790_000_000.0

    def __call__(self) -> float:
        return self.now


def run_mock(mock: MockJobs, clock: Clock, ticker: str) -> dict:
    job, _ = mock.create({"ticker": ticker, "cutoff_at": CUTOFF, "mode": "dual", "scenario": "revise_then_pass",
                          "idempotency_key": f"w07-acceptance-{ticker}"})
    for _ in range(60):
        public, _events = mock.get(job["job_id"])
        if public["status"] not in ("queued", "running"):
            break
        clock.now += 2
    full = mock.store.get_job(job["job_id"])
    assert full["status"] == "succeeded" and full["review"]["decision"] == "pass", full["status"]
    return full


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "reports" / "v12-online-pdf"))
    ap.add_argument("--workdir", default=None,
                    help="keep jobs.sqlite3, reports.sqlite3 and storage/ here (for a local website demo)")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    work = Path(args.workdir) if args.workdir else Path(tempfile.mkdtemp(prefix="w07-"))
    work.mkdir(parents=True, exist_ok=True)
    clock = Clock()
    mock = MockJobs(work / "jobs.sqlite3", ROOT, clock=clock)
    store = ReportStore(work / "reports.sqlite3", LocalStorage(work / "storage"))
    manifest = []
    for ticker in TICKERS:
        job = run_mock(mock, clock, ticker)
        v = store.create_version(job, mock.store.list_events(job["job_id"]))
        store.approve(v["report_version_id"], v["report_hash"], approver="lead (W07-A acceptance script)")
        v = store.publish(v["report_version_id"])
        pdf = store.read_published_pdf(v["report_version_id"])  # read back from Storage, hash-checked
        stem = f"{ticker}-{v['report_version_id']}"
        (out / f"{stem}.pdf").write_bytes(pdf)
        (out / f"{stem}.json").write_text(json.dumps(v["report"], ensure_ascii=False, indent=1), encoding="utf-8")
        manifest.append({k: v[k] for k in ("report_version_id", "job_id", "version_no", "status", "report_hash",
                                           "pdf_hash", "storage_key", "approved_by", "approved_at", "published_at")}
                        | {"ticker": ticker, "pdf_file": f"{stem}.pdf", "json_file": f"{stem}.json",
                           "pdf_bytes": len(pdf), "run_label": v["report"]["run_label"]})
        print(ticker, v["report_version_id"], len(pdf), "bytes")
    (out / "manifest.json").write_text(json.dumps({"cutoff_at": CUTOFF, "versions": manifest}, ensure_ascii=False,
                                                  indent=1), encoding="utf-8")
    if args.workdir is None:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
