"""W08-A: report-store round trips per public read (database queries and Storage reads).

    python scripts/w08_round_trips.py --base http://127.0.0.1:5090 --counts COUNTS.json --rv RV [--label before]

Run against scripts/w08_counted_wsgi.py. Locally these reads take milliseconds, but on Render every database
query opens a new TLS connection to Supabase (about 1 s) and every Storage read is another request, so the
count per page view is what decides the waiting time there. For each endpoint: the first call after a fresh
start (cold) and 5 repeats within the 60 s list cache (warm). Prints JSON.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import requests


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--counts", required=True)
    ap.add_argument("--rv", required=True)
    ap.add_argument("--ref", required=True)
    ap.add_argument("--label", default="")
    a = ap.parse_args()
    read = lambda: json.loads(Path(a.counts).read_text(encoding="utf-8"))  # noqa: E731
    endpoints = {
        "GET /api/ui/published": "/api/ui/published",
        "GET /reports": "/reports",
        "GET /api/ui/reports/<rv>": f"/api/ui/reports/{a.rv}",
        "GET /api/ui/evidence/<id>": f"/api/ui/evidence/{a.ref}?report={a.rv}",
        "GET /reports/<rv>.pdf (lead's preview)": f"/reports/{a.rv}.pdf",
        "GET /api/ui/reports/<rv>/download": f"/api/ui/reports/{a.rv}/download",
        "GET /api/ui/reports/<rv>.pdf (A's preview)": f"/api/ui/reports/{a.rv}.pdf",
    }
    out = {"label": a.label, "endpoints": {}}
    s = requests.Session()
    for name, path in endpoints.items():
        rows = []
        for _ in range(6):
            before = read()
            r = s.get(a.base + path, timeout=60)
            after = read()
            rows.append({"status": r.status_code,
                         "db": after["report_db_queries"] - before["report_db_queries"],
                         "storage": after["storage_reads"] - before["storage_reads"]})
        out["endpoints"][name] = {"status": rows[0]["status"], "first_db": rows[0]["db"],
                                  "first_storage": rows[0]["storage"],
                                  "repeat_db_each": [x["db"] for x in rows[1:]],
                                  "repeat_storage_each": [x["storage"] for x in rows[1:]]}
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
