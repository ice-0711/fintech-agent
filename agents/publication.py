"""Human approval and versioned publication (W07-L), local storage first.

Rules (handbook ch.02 / W07-L):
- A report version is built once from a finished job (review pass) and never edited;
  changes mean a new version. Its hash locks the content.
- Approval needs the logged-in lead and the hash the lead saw; only the newest
  version of a job can be approved, so an old approval cannot overwrite a newer one.
- Publication renders the PDF from the approved JSON only (no LLM call), writes it
  under a versioned storage key, reads it back and checks the hash. Only then is the
  version published; any failure leaves it pdf_failed for an admin retry. A published
  version is never overwritten.
- LocalStorage stands in for Supabase Storage until the test project exists.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Protocol

from zoneinfo import ZoneInfo

from .contract import utc_now_iso

TW = ZoneInfo("Asia/Taipei")

MAX_PDF_BYTES = 5 * 1024 * 1024
MAX_PDF_PAGES = 10

SCHEMA = """
create table if not exists report_versions (
    report_version_id text primary key,
    job_id text not null,
    version_no integer not null,
    status text not null check (status in ('draft', 'approved', 'pdf_failed', 'published')),
    report_json text not null,
    report_hash text not null,
    pdf_hash text,
    storage_key text,
    approved_by text,
    approved_at text,
    published_at text,
    failure text,
    created_at text not null,
    unique (job_id, version_no)
);
"""


class PublicationError(ValueError):
    """Refused publication step; message is safe to show to the lead."""


def canonical_hash(data: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


class Storage(Protocol):
    def put(self, key: str, data: bytes) -> None: ...
    def get(self, key: str) -> bytes: ...
    def exists(self, key: str) -> bool: ...


class LocalStorage:
    """Write-once local object store (stand-in for Supabase Storage)."""

    def __init__(self, root: str | Path):
        self.root = Path(root)

    def _path(self, key: str) -> Path:
        path = (self.root / key).resolve()
        if self.root.resolve() not in path.parents:
            raise PublicationError("storage key 不可跳出儲存根目錄")
        return path

    def put(self, key: str, data: bytes) -> None:
        path = self._path(key)
        if path.exists():
            raise PublicationError(f"{key} 已存在，已發布物件不可覆寫")
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_bytes(data)
        tmp.replace(path)

    def get(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def exists(self, key: str) -> bool:
        return self._path(key).exists()


def build_report_json(job: dict[str, Any], events: list[dict[str, Any]]) -> dict[str, Any]:
    """Freeze what the website and PDF show: the reviewed draft plus provenance."""
    draft, review = job.get("draft") or {}, job.get("review") or {}
    versions = sorted({e["detail"].get("prompt_version") for e in events
                       if e["event_type"] == "model_call" and e["detail"].get("prompt_version")})
    return {
        "job_id": job["job_id"], "ticker": job["ticker"], "cutoff_at": job["cutoff_at"],
        "source_snapshot_id": job["source_snapshot_id"], "question_version": job["question_version"],
        "mode": job["mode"], "model_id": job.get("model_id"), "prompt_versions": versions,
        "claims": draft.get("claims", []),
        "macro_observations": draft.get("macro_observations", []),
        "fundamental_observations": draft.get("fundamental_observations", []),
        "valuation_scenarios": draft.get("valuation_scenarios", []),
        "positive_channels": draft.get("positive_channels", []),
        "negative_channels": draft.get("negative_channels", []),
        "conflicts": draft.get("conflicts", []), "unknowns": draft.get("unknowns", []),
        "next_signals": draft.get("next_signals", []), "limitations": draft.get("limitations", []),
        "review": {k: review.get(k) for k in ("decision", "checked_refs", "checked_metric_ids", "decision_summary")},
        "budget": {k: job.get(k) for k in ("calls_used", "tool_calls_used", "tokens_observed", "supplement_rounds")},
        "disclaimer": "本報告為研究觀察，非投資建議；不含買賣評級、目標價或漲跌機率。",
    }


def render_pdf(report: dict[str, Any], version: dict[str, Any]) -> bytes:
    """PDF from the approved JSON only (reuses report_builder's fpdf2 class and CJK font)."""
    from report_builder import PDF_FONT_FAMILY, ReportPDF, clean_text, register_pdf_fonts  # noqa: PLC0415

    pdf = ReportPDF()
    register_pdf_fonts(pdf)
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    def heading(text: str) -> None:
        pdf.set_font(PDF_FONT_FAMILY, "B", 13)
        pdf.ln(2)
        pdf.multi_cell(0, 8, text, new_x="LMARGIN", new_y="NEXT")

    def line(text: Any, size: int = 10) -> None:
        pdf.set_font(PDF_FONT_FAMILY, "", size)
        pdf.multi_cell(0, 6, clean_text(text), new_x="LMARGIN", new_y="NEXT")

    pdf.set_font(PDF_FONT_FAMILY, "B", 16)
    pdf.multi_cell(0, 10, f"{report['ticker']} 研究報告", new_x="LMARGIN", new_y="NEXT")
    cutoff_tw = datetime.fromisoformat(report["cutoff_at"].replace("Z", "+00:00")).astimezone(TW)
    line(f"資料截止：{cutoff_tw:%Y-%m-%d %H:%M}（台北時間）　快照：{report['source_snapshot_id']}")
    line(f"報告版本：{version['report_version_id']}（第 {version['version_no']} 版）　hash：{version['report_hash'][:16]}…", 8)
    line(f"模型：{report.get('model_id')}　prompt：{', '.join(report.get('prompt_versions') or [])}", 8)

    heading("主張")
    for c in report["claims"]:
        refs = ", ".join(c.get("evidence_refs") or []) or "無"
        line(f"[{c.get('claim_id')}｜{c.get('kind')}] {c.get('text')}")
        line(f"　來源：{refs}", 8)
        for lim in c.get("limitations") or []:
            line(f"　限制：{lim}", 8)
    for title, key in (("總經觀察", "macro_observations"), ("基本面觀察", "fundamental_observations"),
                       ("估值情境", "valuation_scenarios"), ("反向證據與矛盾", "conflicts"),
                       ("未知事項", "unknowns"), ("下一個確認訊號", "next_signals"), ("限制", "limitations")):
        items = report.get(key) or []
        if items:
            heading(title)
            for item in items:
                line(f"・{item if isinstance(item, str) else json.dumps(item, ensure_ascii=False)}")
    heading("覆核")
    review = report.get("review") or {}
    line(f"決定：{review.get('decision')}　{review.get('decision_summary') or ''}")
    line(f"已核對來源：{', '.join(review.get('checked_refs') or []) or '無'}", 8)
    heading("聲明")
    line(report["disclaimer"])
    if pdf.page_no() > MAX_PDF_PAGES:
        raise PublicationError(f"PDF {pdf.page_no()} 頁，超過 {MAX_PDF_PAGES} 頁上限")
    data = bytes(pdf.output())
    if len(data) > MAX_PDF_BYTES:
        raise PublicationError("PDF 超過 5MB 上限")
    return data


class ReportStore:
    def __init__(self, path: str | Path, storage: Storage,
                 renderer: Callable[[dict[str, Any], dict[str, Any]], bytes] = render_pdf):
        self.storage, self.renderer = storage, renderer
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(path), check_same_thread=False, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA)

    def _row(self, rv_id: str) -> dict[str, Any]:
        row = self._conn.execute("select * from report_versions where report_version_id = ?", (rv_id,)).fetchone()
        if row is None:
            raise KeyError(rv_id)
        out = dict(row)
        out["report"] = json.loads(out.pop("report_json"))
        return out

    def get(self, rv_id: str) -> dict[str, Any]:
        return self._row(rv_id)

    def create_version(self, job: dict[str, Any], events: list[dict[str, Any]]) -> dict[str, Any]:
        if job.get("status") != "succeeded" or (job.get("review") or {}).get("decision") != "pass":
            raise PublicationError("只有覆核 pass 且 job 成功的研究才能建立報告版本")
        report = build_report_json(job, events)
        digest = canonical_hash(report)
        with self._lock:
            latest = self._conn.execute(
                "select report_version_id, report_hash, version_no from report_versions where job_id = ? "
                "order by version_no desc limit 1", (job["job_id"],)).fetchone()
            if latest and latest["report_hash"] == digest:
                return self._row(latest["report_version_id"])  # same content → same version (idempotent)
            rv_id = f"rv-{uuid.uuid4()}"
            self._conn.execute(
                "insert into report_versions (report_version_id, job_id, version_no, status, report_json, report_hash,"
                " created_at) values (?, ?, ?, 'draft', ?, ?, ?)",
                (rv_id, job["job_id"], (latest["version_no"] if latest else 0) + 1,
                 json.dumps(report, ensure_ascii=False), digest, utc_now_iso()))
        return self._row(rv_id)

    def approve(self, rv_id: str, seen_hash: str, approver: str) -> dict[str, Any]:
        with self._lock:
            v = self._row(rv_id)
            if v["status"] != "draft":
                raise PublicationError(f"版本狀態為 {v['status']}，只有 draft 可以核准")
            if seen_hash != v["report_hash"]:
                raise PublicationError("hash 與目前版本不符：請重新檢視最新內容再核准")
            newest = self._conn.execute("select max(version_no) from report_versions where job_id = ?",
                                        (v["job_id"],)).fetchone()[0]
            if v["version_no"] != newest:
                raise PublicationError("已有更新的版本，舊版本不能核准")
            self._conn.execute("update report_versions set status = 'approved', approved_by = ?, approved_at = ? "
                               "where report_version_id = ? and status = 'draft'", (approver, utc_now_iso(), rv_id))
        return self._row(rv_id)

    def publish(self, rv_id: str) -> dict[str, Any]:
        v = self._row(rv_id)
        if v["status"] == "published":
            raise PublicationError("已發布的版本不可重新發布或覆寫")
        if v["status"] not in ("approved", "pdf_failed"):
            raise PublicationError("只有已核准（或產檔失敗待重試）的版本可以發布")
        if canonical_hash(v["report"]) != v["report_hash"]:
            raise PublicationError("報告內容與 hash 不符，拒絕發布")
        key = f"reports/{v['report']['ticker']}/{rv_id}.pdf"
        try:
            pdf = self.renderer(v["report"], v)
            pdf_hash = hashlib.sha256(pdf).hexdigest()
            if not self.storage.exists(key):
                self.storage.put(key, pdf)
            if hashlib.sha256(self.storage.get(key)).hexdigest() != pdf_hash:
                raise PublicationError("Storage 讀回的 PDF hash 不符")
        except Exception as exc:  # noqa: BLE001 - record and leave for an admin retry
            with self._lock:
                self._conn.execute("update report_versions set status = 'pdf_failed', failure = ? "
                                   "where report_version_id = ? and status != 'published'", (str(exc)[:300], rv_id))
            raise PublicationError(f"PDF 產生或儲存失敗，狀態 pdf_failed：{exc}") from exc
        with self._lock:
            self._conn.execute(
                "update report_versions set status = 'published', pdf_hash = ?, storage_key = ?, published_at = ?, "
                "failure = null where report_version_id = ? and status in ('approved', 'pdf_failed')",
                (pdf_hash, key, utc_now_iso(), rv_id))
        return self._row(rv_id)

    def published(self) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "select report_version_id from report_versions where status = 'published' order by published_at desc").fetchall()
        out = []
        for r in rows:
            v = self._row(r[0])
            out.append({"report_version_id": v["report_version_id"], "ticker": v["report"]["ticker"],
                        "cutoff_at": v["report"]["cutoff_at"], "published_at": v["published_at"],
                        "publication_status": v["status"], "review_decision": v["report"]["review"]["decision"],
                        "pdf_status": "ready" if v["storage_key"] else "missing"})
        return out

    def read_published_pdf(self, rv_id: str) -> bytes:
        v = self._row(rv_id)
        if v["status"] != "published":
            raise PublicationError("未發布的版本不可下載")
        data = self.storage.get(v["storage_key"])
        if hashlib.sha256(data).hexdigest() != v["pdf_hash"]:
            raise PublicationError("PDF 與發布紀錄的 hash 不符")
        return data
