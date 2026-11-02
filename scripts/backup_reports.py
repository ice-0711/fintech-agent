"""W08-L backup and restore rehearsal. Supabase Free has no scheduled backups, so we export ourselves.

    .venv/bin/python scripts/backup_reports.py export            # Supabase → tmp/backups/<stamp>/
    .venv/bin/python scripts/backup_reports.py restore <dir>     # <dir> → fresh local SQLite + folder, then verify

export reads report_versions (REPORT_DB_URL) and every published PDF (REPORT_SUPABASE_*, bucket REPORT_STORAGE_BUCKET);
it only reads from Supabase. It also copies every research job database tmp/*.sqlite3 with SQLite's online backup API,
because jobs live only on the lead's Mac. restore never touches Supabase: it rebuilds a ReportStore from the export
and checks that each report hash, each PDF hash and the published list match the export. Values in .env are never printed.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import agents  # noqa: E402,F401  (loads .env)
from agents.publication import LocalStorage, ReportStore, canonical_hash  # noqa: E402

COLUMNS = ("report_version_id", "job_id", "version_no", "status", "report_json", "report_hash", "pdf_hash",
           "storage_key", "approved_by", "approved_at", "published_at", "failure", "created_at")


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def export() -> Path:
    from research_ui.storage_supabase import storage_from_env  # noqa: PLC0415

    if not os.getenv("REPORT_DB_URL"):
        sys.exit("REPORT_DB_URL 未設定，停止。")
    out = ROOT / "tmp" / "backups" / datetime.now().strftime("%Y%m%d-%H%M%S")
    (out / "pdf").mkdir(parents=True)
    store = ReportStore(os.environ["REPORT_DB_URL"], storage_from_env(ROOT / "tmp" / "storage"))
    rows = store._db.rows(f"select {', '.join(COLUMNS)} from report_versions order by created_at")
    rows = [{k: (v if v is None or isinstance(v, (str, int)) else str(v)) for k, v in r.items()} for r in rows]
    pdfs = {}
    for r in rows:
        if r["status"] == "published":
            data = store.storage.get(r["storage_key"])
            if sha(data) != r["pdf_hash"]:
                sys.exit(f"{r['report_version_id']} 的 PDF 與紀錄 hash 不符，停止。")
            name = f"{r['report_version_id']}.pdf"
            (out / "pdf" / name).write_bytes(data)
            pdfs[r["storage_key"]] = {"file": f"pdf/{name}", "sha256": r["pdf_hash"], "bytes": len(data)}
    rows_bytes = json.dumps(rows, ensure_ascii=False, indent=1).encode("utf-8")
    (out / "report_versions.json").write_bytes(rows_bytes)

    jobs = {}
    (out / "jobs").mkdir()
    for db in sorted((ROOT / "tmp").glob("*.sqlite3")):
        dst = out / "jobs" / db.name
        with sqlite3.connect(db) as src, sqlite3.connect(dst) as copy:
            src.backup(copy)
            ok = copy.execute("pragma integrity_check").fetchone()[0]
        jobs[db.name] = {"integrity": ok, "sha256": sha(dst.read_bytes()), "tables": table_counts(dst)}
        if table_counts(db) != jobs[db.name]["tables"]:
            sys.exit(f"{db.name} 備份後筆數不同，停止。")

    manifest = {"exported_at": datetime.now().astimezone().isoformat(timespec="seconds"),
                "source": "Supabase report_versions（REPORT_DB_URL）＋私有 Storage；tmp/*.sqlite3",
                "report_versions": {"rows": len(rows), "sha256": sha(rows_bytes),
                                    "by_status": {s: sum(r["status"] == s for r in rows) for s in {r["status"] for r in rows}}},
                "pdfs": pdfs, "job_databases": jobs}
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("export", out.relative_to(ROOT), "rows", len(rows), "pdfs", len(pdfs), "job dbs", len(jobs))
    return out


def table_counts(db: Path) -> dict[str, int]:
    with sqlite3.connect(db) as conn:
        names = [r[0] for r in conn.execute("select name from sqlite_master where type='table' and name not like 'sqlite_%'")]
        return {n: conn.execute(f'select count(*) from "{n}"').fetchone()[0] for n in sorted(names)}


def restore(src: Path) -> None:
    manifest = json.loads((src / "manifest.json").read_text(encoding="utf-8"))
    rows_bytes = (src / "report_versions.json").read_bytes()
    checks: list[tuple[str, bool]] = [("report_versions.json sha256 與 manifest 一致",
                                       sha(rows_bytes) == manifest["report_versions"]["sha256"])]
    target = src / "restored"
    if target.exists():
        sys.exit(f"{target.relative_to(ROOT)} 已存在，換一個匯出資料夾或先移走，停止。")
    target.mkdir()
    storage = LocalStorage(target / "storage")
    store = ReportStore(target / "reports.sqlite3", storage)
    rows = json.loads(rows_bytes)
    for r in rows:
        store._db.run(f"insert into report_versions ({', '.join(COLUMNS)}) values ({', '.join('?' * len(COLUMNS))})",
                      tuple(r[c] for c in COLUMNS))
        if r["status"] == "published":
            storage.put(r["storage_key"], (src / manifest["pdfs"][r["storage_key"]]["file"]).read_bytes())

    checks.append(("還原筆數相同", len(store._db.rows("select report_version_id from report_versions")) == len(rows)))
    checks.append(("每份報告內容 hash 相符",
                   all(canonical_hash(store.get(r["report_version_id"])["report"]) == r["report_hash"] for r in rows)))
    published = [r for r in rows if r["status"] == "published"]
    checks.append(("已發布清單相同", {p["report_version_id"] for p in store.published()}
                   == {r["report_version_id"] for r in published}))
    checks.append(("已發布 PDF 讀回 hash 相符",
                   all(sha(store.read_published_pdf(r["report_version_id"])) == r["pdf_hash"] for r in published)))
    for name, info in manifest["job_databases"].items():
        db = src / "jobs" / name
        checks.append((f"job 資料庫 {name} 完整且筆數相同",
                       sha(db.read_bytes()) == info["sha256"] and table_counts(db) == info["tables"]))
    for name, ok in checks:
        print(("PASS " if ok else "FAIL ") + name)
    if not all(ok for _, ok in checks):
        sys.exit(1)


if __name__ == "__main__":
    if sys.argv[1:2] == ["export"]:
        export()
    elif sys.argv[1:2] == ["restore"] and len(sys.argv) == 3:
        restore(Path(sys.argv[2]).resolve())
    else:
        sys.exit(__doc__)
