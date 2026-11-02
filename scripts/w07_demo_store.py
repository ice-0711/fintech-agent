"""Load the frozen W07 acceptance versions (reports/v12-online-pdf) into a local report store, unchanged.

For screenshots of the website showing exactly the versions B audited: same report_version_id, approved JSON,
report hash, PDF bytes, PDF hash and storage key as manifest.json. Nothing is re-rendered or recomputed; the
report hash and PDF hash are checked before anything is written. Offline, 0 LLM.

    python scripts/w07_demo_store.py DIR
    REPORT_DB_PATH=DIR/reports.sqlite3 REPORT_STORAGE_DIR=DIR/storage python web_app.py   # then open /research
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agents.publication import LocalStorage, canonical_hash, open_report_db  # noqa: E402

SRC = ROOT / "reports" / "v12-online-pdf"


def main(target: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)
    db = open_report_db(target / "reports.sqlite3")
    storage = LocalStorage(target / "storage")
    manifest = json.loads((SRC / "manifest.json").read_text(encoding="utf-8"))
    for v in manifest["versions"]:
        report = json.loads((SRC / v["json_file"]).read_text(encoding="utf-8"))
        pdf = (SRC / v["pdf_file"]).read_bytes()
        assert canonical_hash(report) == v["report_hash"], f"{v['ticker']} report hash mismatch"
        assert hashlib.sha256(pdf).hexdigest() == v["pdf_hash"], f"{v['ticker']} PDF hash mismatch"
        if not storage.exists(v["storage_key"]):
            storage.put(v["storage_key"], pdf)
        db.run("insert or replace into report_versions (report_version_id, job_id, version_no, status, report_json,"
               " report_hash, pdf_hash, storage_key, approved_by, approved_at, published_at, created_at)"
               " values (?, ?, ?, 'published', ?, ?, ?, ?, ?, ?, ?, ?)",
               (v["report_version_id"], v["job_id"], v["version_no"], json.dumps(report, ensure_ascii=False),
                v["report_hash"], v["pdf_hash"], v["storage_key"], v["approved_by"], v["approved_at"],
                v["published_at"], v["approved_at"]))
        print(v["ticker"], v["report_version_id"])


if __name__ == "__main__":
    main(Path(sys.argv[1]))
