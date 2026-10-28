"""W07-L rehearsal: the whole publication path against the Supabase TEST project (Postgres + private Storage).

    .venv/bin/python scripts/rehearse_publication.py

Uses a MOCK job (never a model call), the SUPABASE_TEST_* variables from .env (values never printed),
and removes its rows and PDF at the end so nothing fake stays published. Prints one line per check.
"""

from __future__ import annotations

import hashlib
import os
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import agents  # noqa: E402,F401  (loads .env)
from agents.publication import PublicationError, ReportStore  # noqa: E402

CHECKS: list[tuple[str, bool]] = []


def check(name: str, ok: bool) -> None:
    CHECKS.append((name, ok))
    print(("PASS " if ok else "FAIL ") + name, flush=True)


def store() -> ReportStore:
    from research_ui.storage_supabase import SupabaseStorage  # noqa: PLC0415
    from supabase import create_client  # noqa: PLC0415

    storage = SupabaseStorage(create_client(os.environ["SUPABASE_TEST_URL"], os.environ["SUPABASE_TEST_KEY"]), "reports")
    return ReportStore(os.environ["SUPABASE_TEST_DB_URL"], storage)


def main() -> None:
    job_id = f"rehearsal-{uuid.uuid4().hex[:8]}"
    job = {"job_id": job_id, "ticker": "2330", "cutoff_at": "2026-08-12T09:00:00+00:00",
           "source_snapshot_id": "snap-dev-case-01", "question_version": "q-v1", "mode": "dual",
           "model_id": "MOCK", "status": "succeeded", "calls_used": 0, "tool_calls_used": 0, "tokens_observed": 0,
           "supplement_rounds": 0,
           "draft": {"claims": [{"claim_id": "c1", "kind": "fact", "text": "MOCK 演練主張（非研究結果）",
                                 "evidence_refs": ["ev-dev-01-official"], "limitations": []}],
                     "limitations": ["W07 發布流程演練，非真實研究"], "unknowns": []},
           "review": {"decision": "pass", "checked_refs": ["ev-dev-01-official"], "decision_summary": "MOCK 演練"}}
    events = [{"event_type": "mock_scenario", "detail": {"mock": True}}]
    reports = store()
    rv = reports.create_version(job, events)
    rv_id = rv["report_version_id"]
    try:
        check("建立版本：status=draft，存進 Supabase Postgres", rv["status"] == "draft")
        check("同內容再建立 → 回傳同一版本（不重複）", reports.create_version(job, events)["report_version_id"] == rv_id)
        check("未核准不在公開清單", all(p["report_version_id"] != rv_id for p in reports.published()))
        try:
            reports.approve(rv_id, "0" * 64, "lead"); check("hash 不符拒絕核准", False)
        except PublicationError:
            check("hash 不符拒絕核准", True)
        try:
            reports.publish(rv_id); check("未核准拒絕發布", False)
        except PublicationError:
            check("未核准拒絕發布", True)
        check("核准（帶正確 hash）→ approved", reports.approve(rv_id, rv["report_hash"], "lead")["status"] == "approved")
        pub = reports.publish(rv_id)
        check("發布：PDF 上傳私有 bucket、hash 讀回一致 → published", pub["status"] == "published" and bool(pub["pdf_hash"]))
        check("已發布出現在公開清單", any(p["report_version_id"] == rv_id for p in reports.published()))
        restarted = store()  # a fresh process after a redeploy: nothing kept in memory or on local disk
        pdf = restarted.read_published_pdf(rv_id)
        check("模擬重新部署後仍可下載、PDF hash 與紀錄一致",
              hashlib.sha256(pdf).hexdigest() == pub["pdf_hash"] and pdf[:4] == b"%PDF")
        try:
            restarted.publish(rv_id); check("已發布版本不可重新發布／覆寫", False)
        except PublicationError:
            check("已發布版本不可重新發布／覆寫", True)
        print(f"PDF 大小：{len(pdf)} bytes；storage_key：{pub['storage_key']}")
    finally:
        v = reports.get(rv_id)
        if v.get("storage_key"):
            reports.storage.bucket.remove([v["storage_key"]])
        reports._db.run("delete from report_versions where job_id = ?", (job_id,))
        left = reports._db.rows("select count(*) as n from report_versions where job_id = ?", (job_id,))[0]["n"]
        print(f"清除演練資料：版本列剩 {left}，PDF {'已刪除' if v.get('storage_key') else '未產生'}")
    passed = sum(ok for _, ok in CHECKS)
    print(f"{passed}/{len(CHECKS)} 通過")
    sys.exit(0 if passed == len(CHECKS) else 1)


if __name__ == "__main__":
    main()
