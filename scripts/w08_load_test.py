"""W08-A: 10 read-only visitors + 1 running job for 5 minutes against the research workspace.

    python scripts/w08_load_test.py --base http://127.0.0.1:5090 --server-pid PID --counts COUNTS.json \
        --out performance/v12-read-only.json --raw performance/v12-read-only-requests.csv \
        [--duration 300] [--readers 10] [--publish-at 100 200 --admin-password-env W08_ADMIN_PASSWORD]

Visitors behave like the page: load /research (HTML, CSS, JS) and its three startup reads, then open
published reports, source drawers, the public list, PDF previews and downloads, with 0.5–2 s pauses and
bursts that click the three reports 4–5 times in a row. The job is a MOCK revise_then_pass research job
(scripted model decisions, real snapshot tools) created and polled every 2 s like the page does; when one
finishes the next starts. Optionally the lead logs in once and approves + publishes a report version in the
middle of the run, once per --publish-at time (the PDF is rendered inside that request, as on Render with one
sync worker), so the RSS series shows what each publish leaves behind.

Every request is logged raw (time, endpoint, status, latency, bytes); the summary has p50/p95/p99/max and
4xx/5xx per endpoint, server RSS sampled every second (gunicorn master + worker), and the server's model /
full-statement / outbound-connection counters before and after. No LLM, no external network.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import random
import statistics
import threading
import time
from pathlib import Path

import psutil
import requests

TERMINAL = {"succeeded", "insufficient_evidence", "timed_out", "failed", "cancelled"}


class Log:
    def __init__(self, t0: float):
        self.t0, self.rows, self.lock = t0, [], threading.Lock()

    def call(self, session: requests.Session, who: str, label: str, method: str, url: str, **kw):
        start = time.perf_counter()
        status, size, err = None, 0, None
        try:
            r = session.request(method, url, timeout=180, **kw)
            status, size = r.status_code, len(r.content)
        except requests.RequestException as exc:  # recorded, counted as an error
            err, r = type(exc).__name__, None
        ms = (time.perf_counter() - start) * 1000
        with self.lock:
            self.rows.append({"t_s": round(start - self.t0, 3), "who": who, "endpoint": label, "method": method,
                              "status": status, "ms": round(ms, 1), "bytes": size, "error": err})
        return r


def pct(values: list[float], q: float) -> float | None:
    if not values:
        return None
    s = sorted(values)
    k = (len(s) - 1) * q
    lo, hi = int(k), min(int(k) + 1, len(s) - 1)
    return round(s[lo] + (s[hi] - s[lo]) * (k - lo), 1)


def summarize(rows: list[dict]) -> dict:
    out = {}
    for label in sorted({r["endpoint"] for r in rows}):
        rs = [r for r in rows if r["endpoint"] == label]
        ms = [r["ms"] for r in rs if r["status"] is not None]
        out[label] = {"n": len(rs), "p50_ms": pct(ms, .5), "p95_ms": pct(ms, .95), "p99_ms": pct(ms, .99),
                      "max_ms": max(ms) if ms else None,
                      "status_2xx": sum(1 for r in rs if r["status"] and 200 <= r["status"] < 300),
                      "status_3xx": sum(1 for r in rs if r["status"] and 300 <= r["status"] < 400),
                      "status_4xx": sum(1 for r in rs if r["status"] and 400 <= r["status"] < 500),
                      "status_5xx": sum(1 for r in rs if r["status"] and r["status"] >= 500),
                      "errors": sum(1 for r in rs if r["error"])}
    return out


def reader(i: int, base: str, log: Log, stop: float, reports: list[dict], rng: random.Random) -> None:
    s = requests.Session()
    who = f"reader-{i:02d}"
    while time.perf_counter() < stop:
        # page load, like a browser opening /research
        log.call(s, who, "GET /research", "GET", f"{base}/research")
        log.call(s, who, "GET /static/research.css", "GET", f"{base}/static/research.css")
        log.call(s, who, "GET /static/research.js", "GET", f"{base}/static/research.js")
        log.call(s, who, "GET /api/ui/published", "GET", f"{base}/api/ui/published")
        log.call(s, who, "GET /api/ui/comparison/2454", "GET", f"{base}/api/ui/comparison/2454")
        log.call(s, who, "GET /api/ui/replays", "GET", f"{base}/api/ui/replays")
        for _ in range(rng.randint(3, 6)):
            if time.perf_counter() >= stop:
                return
            time.sleep(rng.uniform(0.5, 2.0))
            act = rng.random()
            rep = rng.choice(reports)
            rv = rep["rv"]
            if act < 0.20:  # burst: click the three tickers' reports 4–5 times in a row
                for _ in range(rng.randint(4, 5)):
                    for r in reports:
                        log.call(s, who, "GET /api/ui/reports/<rv>", "GET", f"{base}/api/ui/reports/{r['rv']}")
                        time.sleep(0.1)
            elif act < 0.45:
                log.call(s, who, "GET /api/ui/reports/<rv>", "GET", f"{base}/api/ui/reports/{rv}")
            elif act < 0.60 and rep["refs"]:
                ref = rng.choice(rep["refs"])
                log.call(s, who, "GET /api/ui/evidence/<id>", "GET", f"{base}/api/ui/evidence/{ref}?report={rv}")
            elif act < 0.72:
                log.call(s, who, "GET /reports", "GET", f"{base}/reports")
            elif act < 0.86:
                log.call(s, who, "GET /api/ui/reports/<rv>.pdf (preview)", "GET", f"{base}/api/ui/reports/{rv}.pdf")
            else:
                log.call(s, who, "GET /api/ui/reports/<rv>/download", "GET", f"{base}/api/ui/reports/{rv}/download")


def job_runner(base: str, log: Log, stop: float, done: list[dict]) -> None:
    s = requests.Session()
    n = 0
    while time.perf_counter() < stop:
        n += 1
        ticker = ("2330", "2317", "2454")[n % 3]
        r = log.call(s, "job", "POST /api/ui/mock/jobs", "POST", f"{base}/api/ui/mock/jobs",
                     json={"ticker": ticker, "cutoff_at": "2026-09-30T17:30:00+08:00", "mode": "dual",
                           "scenario": "revise_then_pass", "idempotency_key": f"w08-load-{int(time.time())}-{n}"})
        if r is None or r.status_code >= 400:
            time.sleep(2)
            continue
        job_id = r.json()["job"]["job_id"]
        started = time.perf_counter()
        status = "queued"
        while time.perf_counter() < stop + 60 and status not in TERMINAL:  # let the last job finish
            time.sleep(2)
            p = log.call(s, "job", "GET /api/ui/jobs/<id> (poll)", "GET", f"{base}/api/ui/jobs/{job_id}")
            if p is not None and p.status_code == 200:
                status = p.json()["job"]["status"]
        done.append({"job_id": job_id, "ticker": ticker, "final_status": status,
                     "wall_s": round(time.perf_counter() - started, 1)})


def publisher(base: str, log: Log, at: float, t0: float, password: str, jobs: list[dict], result: dict,
              used: set) -> None:
    time.sleep(max(0.0, t0 + at - time.perf_counter()))
    s = requests.Session()
    while not any(j["final_status"] == "succeeded" and j["job_id"] not in used for j in jobs):
        time.sleep(1)
    job = next(j for j in jobs if j["final_status"] == "succeeded" and j["job_id"] not in used)
    used.add(job["job_id"])
    log.call(s, "lead", "POST /admin/login", "POST", f"{base}/admin/login", data={"password": password},
             allow_redirects=False)
    r = log.call(s, "lead", "POST /api/ui/jobs/<id>/report", "POST", f"{base}/api/ui/jobs/{job['job_id']}/report")
    v = r.json()["version"]
    t_start = time.perf_counter() - t0
    r = log.call(s, "lead", "POST /api/ui/jobs/<id>/approve (render PDF)", "POST",
                 f"{base}/api/ui/jobs/{job['job_id']}/approve",
                 json={"report_version_id": v["report_version_id"], "report_hash": v["report_hash"]})
    result.update({"job_id": job["job_id"], "report_version_id": v["report_version_id"],
                   "window_s": [round(t_start, 1), round(time.perf_counter() - t0, 1)],
                   "status": r.status_code if r is not None else None,
                   "published": bool(r is not None and r.ok and r.json().get("ok"))})


def rss_sampler(pid: int, stop_event: threading.Event, t0: float, samples: list[dict]) -> None:
    master = psutil.Process(pid)
    while not stop_event.is_set():
        try:
            procs = [master] + master.children(recursive=True)
            per = {p.pid: p.memory_info().rss for p in procs}
            samples.append({"t_s": round(time.perf_counter() - t0, 1), "total_mb": round(sum(per.values()) / 2**20, 1),
                            "worker_mb": round(max(v for k, v in per.items() if k != pid) / 2**20, 1)
                            if len(per) > 1 else None})
        except psutil.Error:
            pass
        stop_event.wait(1.0)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--server-pid", type=int, required=True)
    ap.add_argument("--counts", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--raw", required=True)
    ap.add_argument("--duration", type=float, default=300)
    ap.add_argument("--readers", type=int, default=10)
    ap.add_argument("--seed", type=int, default=8)
    ap.add_argument("--publish-at", type=float, nargs="*", default=[])
    ap.add_argument("--admin-password-env", default="W08_ADMIN_PASSWORD")
    ap.add_argument("--label", default="")
    args = ap.parse_args()

    base = args.base.rstrip("/")
    pub = requests.get(f"{base}/api/ui/published", timeout=60).json()
    reports = []
    for row in pub["reports"]:
        if row["synthetic_fixture"]:
            continue
        det = requests.get(f"{base}/api/ui/reports/{row['report_version_id']}", timeout=60).json()["report"]
        refs = sorted({e["id"] for c in det["claims"] for e in c["evidence"] if e["exists"]})
        reports.append({"rv": row["report_version_id"], "ticker": row["ticker"], "refs": refs})
    assert reports, "no published report to read"
    counts_before = json.loads(Path(args.counts).read_text(encoding="utf-8"))

    t0 = time.perf_counter()
    stop = t0 + args.duration
    log = Log(t0)
    rss: list[dict] = []
    rss_stop = threading.Event()
    jobs: list[dict] = []
    publishes: list[dict] = []
    used: set = set()
    threads = [threading.Thread(target=rss_sampler, args=(args.server_pid, rss_stop, t0, rss), daemon=True)]
    threads += [threading.Thread(target=reader, args=(i, base, log, stop, reports, random.Random(args.seed * 100 + i)))
                for i in range(args.readers)]
    threads.append(threading.Thread(target=job_runner, args=(base, log, stop, jobs)))
    for at in args.publish_at:
        publishes.append({})
        threads.append(threading.Thread(target=publisher, args=(base, log, at, t0, os.environ[args.admin_password_env],
                                                                jobs, publishes[-1], used)))
    for th in threads:
        th.start()
    for th in threads[1:]:
        th.join()
    rss_stop.set()
    threads[0].join()
    counts_after = json.loads(Path(args.counts).read_text(encoding="utf-8"))

    rows = sorted(log.rows, key=lambda r: r["t_s"])
    reads = [r for r in rows if r["who"].startswith("reader")]
    windows = [p["window_s"] for p in publishes if p.get("window_s")]
    in_window = [r for r in reads if any(w[0] <= r["t_s"] <= w[1] for w in windows)]
    outside = [r for r in reads if r not in in_window]
    total = [r["total_mb"] for r in rss]
    result = {
        "label": args.label,
        "measured_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "config": {"base": base, "duration_s": args.duration, "readers": args.readers, "seed": args.seed,
                   "job": "1 MOCK revise_then_pass at a time, polled every 2 s",
                   "publish_at_s": args.publish_at, "reports_read": reports},
        "overall_readers": {"n": len(reads), "p50_ms": pct([r["ms"] for r in reads], .5),
                            "p95_ms": pct([r["ms"] for r in reads], .95), "max_ms": max(r["ms"] for r in reads),
                            "status_5xx": sum(1 for r in reads if r["status"] and r["status"] >= 500),
                            "errors": sum(1 for r in reads if r["error"]),
                            "rps": round(len(reads) / args.duration, 2)},
        "readers_outside_publish": {"n": len(outside), "p95_ms": pct([r["ms"] for r in outside], .95)},
        "readers_during_publish": {"n": len(in_window), "p95_ms": pct([r["ms"] for r in in_window], .95),
                                   "max_ms": max((r["ms"] for r in in_window), default=None)},
        "by_endpoint": summarize(rows),
        "rss_mb": {"samples": len(total), "min": min(total), "median": statistics.median(total), "max": max(total),
                   "worker_max": max((s["worker_mb"] for s in rss if s["worker_mb"]), default=None),
                   "series": rss},
        "jobs": jobs,
        "publishes": publishes,
        "server_counters": {"before": counts_before, "after": counts_after,
                            "model_requests_delta": (counts_after["model_generate_content"]
                                                     - counts_before["model_generate_content"]),
                            "full_statement_fetch_delta": (counts_after["full_statement_fetch"]
                                                           - counts_before["full_statement_fetch"]),
                            "outbound_connections_delta": (counts_after["outbound_connections"]
                                                           - counts_before["outbound_connections"])},
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    with open(args.raw, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(json.dumps({k: result[k] for k in ("overall_readers", "readers_during_publish", "publishes")}, ensure_ascii=False))
    print("rss", {k: result["rss_mb"][k] for k in ("min", "median", "max", "worker_max")})
    print("counters", result["server_counters"]["model_requests_delta"], result["server_counters"]["full_statement_fetch_delta"],
          result["server_counters"]["outbound_connections_delta"])


if __name__ == "__main__":
    main()
