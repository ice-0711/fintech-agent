"""W08-A: memory of rendering the same report PDF several times in one process (as one gunicorn worker does).

    python scripts/w08_pdf_memory.py [--renders 4] [--no-release] [--report reports/v12-online-pdf/2454-*.json]

Imports web_app first (same baseline as the server worker), then renders the approved 2454 report N times,
sampling RSS every 10 ms. --no-release turns off research_ui.report_pdf.release_memory to show the behaviour
before the W08-A fix. Prints one JSON line per render. Offline, 0 LLM.
"""

from __future__ import annotations

import argparse
import glob
import json
import sys
import threading
import time
from pathlib import Path

import psutil

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--renders", type=int, default=4)
    ap.add_argument("--no-release", action="store_true")
    ap.add_argument("--report", default=str(ROOT / "reports" / "v12-online-pdf" / "2454-*.json"))
    a = ap.parse_args()
    proc = psutil.Process()
    rss = lambda: proc.memory_info().rss / 2**20  # noqa: E731
    import web_app  # noqa: F401  (same imports as the server worker)
    from research_ui import report_pdf

    if a.no_release:
        report_pdf.release_memory = lambda: None
    report = json.loads(Path(glob.glob(a.report)[0]).read_text(encoding="utf-8"))
    version = {"report_version_id": "rv-memory-test", "version_no": 1, "report_hash": "h", "approved_by": "lead"}
    peak, stop = [0.0], threading.Event()

    def sample() -> None:
        while not stop.is_set():
            peak[0] = max(peak[0], rss())
            time.sleep(0.01)

    base = rss()
    t = threading.Thread(target=sample)
    t.start()
    for i in range(a.renders):
        peak[0] = rss()
        start = time.perf_counter()
        pdf = report_pdf.render_report_pdf(report, version)
        print(json.dumps({"render": i + 1, "release_memory": not a.no_release, "pdf_bytes": len(pdf),
                          "seconds": round(time.perf_counter() - start, 2), "rss_before_first_mb": round(base, 1),
                          "peak_mb": round(peak[0], 1), "after_mb": round(rss(), 1)}))
    stop.set()
    t.join()


if __name__ == "__main__":
    main()
