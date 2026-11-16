"""Trace the obs-* references of a forward batch's drafts to their sources, from the lead's job database.

    python scripts/obs_trace_check.py --batch 3
    python scripts/obs_trace_check.py --batch 3 --db tmp/forward_batch3.sqlite3 --out tmp/forward-batch-3-obs-trace.json

For B's check (11/15) before batch 3 is published: for every report of the batch that has a draft, prints each cited
obs → what the job's own tool record says it returned (research_ui.obs_trace), and the source_traceable result the
report version would get. Same code path as publishing (research_ui.report_data.build_report_data).

Read-only: opens the job database with mode=ro, writes only --out. No model call, no network, no tool re-run for
the mapping (the existing fragment rule reads the frozen snapshot, as it does when publishing).
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from research_ui.report_data import build_report_data  # noqa: E402


def load_job(db: Path, job_id: str) -> dict | None:
    con = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
    try:
        row = con.execute("select data from research_jobs where job_id = ?", (job_id,)).fetchone()
    finally:
        con.close()
    return json.loads(row[0]) if row else None


def trace_job(job: dict) -> dict:
    data = build_report_data(job)
    check = next((c for c in (data.get("data_quality") or {}).get("checks", []) if c["check_id"] == "source_traceable"),
                 None)
    obs = [s for s in data.get("sources") or [] if s.get("kind") == "observation"]
    claims = [{"claim_id": c.get("claim_id"), "kind": c.get("kind"), "evidence_refs": c.get("evidence_refs") or []}
              for c in (job.get("draft") or {}).get("claims") or []]
    return {"job_id": job["job_id"], "ticker": job["ticker"], "status": job.get("status"),
            "source_snapshot_id": job.get("source_snapshot_id"), "claims": claims,
            "obs_map_status": (data.get("obs_map") or {}).get("status"),
            "observations": [{k: s.get(k) for k in ("id", "resolved", "tool", "tool_status", "via", "inputs", "targets", "note",
                                                     "reason")} for s in obs],
            "source_traceable": {"result": check["result"], "detail": check["detail"]} if check else None,
            "data_quality": (data.get("data_quality") or {}).get("label")}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", type=int, default=3)
    ap.add_argument("--db", help="job database (default tmp/forward_batch{n}.sqlite3, as scripts/forward_research.py)")
    ap.add_argument("--out", help="JSON output (default tmp/forward-batch-{n}-obs-trace.json)")
    a = ap.parse_args()
    db = Path(a.db) if a.db else ROOT / "tmp" / f"forward_batch{a.batch}.sqlite3"
    out = Path(a.out) if a.out else ROOT / "tmp" / f"forward-batch-{a.batch}-obs-trace.json"
    reports = json.loads((ROOT / "research" / f"forward-batch-{a.batch}-reports.json").read_text(encoding="utf-8"))
    if not db.exists():
        sys.exit(f"找不到 job 資料庫 {db}（前瞻批次在組長 Mac 上執行，資料庫只在那台電腦）")
    results = []
    for r in reports["reports"]:
        if not r.get("draft"):
            print(f"{r['ticker']}：沒有草稿（{r.get('status')}），略過")
            continue
        job = load_job(db, r["job_id"])
        if job is None:
            print(f"{r['ticker']}：資料庫裡找不到 job {r['job_id']}")
            continue
        res = trace_job(job)
        results.append(res)
        print(f"\n== {res['ticker']}  job {res['job_id']}  obs 對應：{res['obs_map_status']}")
        for c in res["claims"]:
            print(f"  {c['claim_id']}（{c['kind']}）引用 {', '.join(c['evidence_refs']) or '—'}")
        for o in res["observations"]:
            print(f"  {o['id']}  {o['tool']}（{o['tool_status']}）{'→' if o['resolved'] else '×'}")
            for t in o.get("targets") or []:
                if t["kind"] == "evidence":
                    print(f"      → {t['id']}  {t['seen']}  在快照中={t['exists']}  hash 相符={t['hash_match']}")
                elif t["kind"] == "financial_snapshot":
                    print(f"      → 財報快照 {t['source_id']} {t['latest_period']} {t['periods']}")
                elif t["kind"] == "price":
                    print(f"      → 股價 {t['source_id']} {t['trade_dates']}")
                elif t["kind"] == "macro":
                    print(f"      → 總經 {[(x['series_id'], x['observation_date']) for x in t['rows']]}")
            for i in o.get("inputs") or []:
                m = i.get("match")
                where = (f"{m['obs_id']} {m['field']} {m.get('date') or ''}" + (" (文字)" if m["in_text"] else "")) if m else "找不到"
                extra = (f"，另有 {i['other_matches']} 處相同" if i.get("other_matches") else "") + \
                    ("，小整數或年份" if i.get("weak") else "")
                print(f"      輸入 {i['name']} = {i['value']:g} → {where}{extra}")
            if o.get("via"):
                print(f"      計算輸入來自 {', '.join(o['via'])}")
            if o.get("note") or o.get("reason"):
                print(f"      {o.get('note') or o.get('reason')}")
        st = res["source_traceable"] or {}
        print(f"  來源可追溯：{st.get('result')}  {st.get('detail') or ''}")
        print(f"  {res['data_quality']}")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"batch": a.batch, "snapshot_sha256": reports.get("snapshot_sha256"), "results": results},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n已寫入 {out}")


if __name__ == "__main__":
    main()
