"""Authorised research-job API (W02-L).

POST /api/research/jobs      create (idempotent) → 202 with job_id
GET  /api/research/jobs/<id> status + event trace (no secrets, no hidden reasoning)

Auth is deny-by-default: a logged-in admin session (agents/admin.py) or
`Authorization: Bearer <RESEARCH_API_TOKEN>`.
If RESEARCH_API_TOKEN is not set on the server, every request is rejected.
Existing /api/analyze is not changed here; bringing it under the same
authorisation/quota policy is a separate decision for the team lead with A.
"""

from __future__ import annotations

import hmac
import os
from functools import wraps
from pathlib import Path

from flask import Blueprint, current_app, jsonify, request

from .admin import is_admin
from .contract import ContractError, validate_job_request
from .store import JobStore

bp = Blueprint("research_jobs", __name__, url_prefix="/api/research")

PUBLIC_JOB_FIELDS = (
    "job_id", "ticker", "mode", "status", "stage", "cutoff_at", "source_snapshot_id", "question_version",
    "model_id", "prompt_version", "calls_used", "tokens_observed", "tool_calls_used", "supplement_rounds",
    "stop_reason", "checkpoint_version", "created_at", "updated_at",
)


def get_store() -> JobStore:
    store = current_app.extensions.get("research_job_store")
    if store is None:
        path = os.getenv("RESEARCH_DB_PATH") or str(Path(current_app.root_path) / "tmp" / "research_jobs.sqlite3")
        store = JobStore(path)
        current_app.extensions["research_job_store"] = store
    return store


def require_token(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if is_admin():  # logged-in lead (browser session)
            return view(*args, **kwargs)
        expected = current_app.config.get("RESEARCH_API_TOKEN") or os.getenv("RESEARCH_API_TOKEN")
        supplied = request.headers.get("Authorization", "").encode("utf-8", "surrogateescape")
        if not expected or not hmac.compare_digest(supplied, f"Bearer {expected}".encode()):
            return jsonify({"ok": False, "error": "unauthorized"}), 401
        return view(*args, **kwargs)

    return wrapper


def public_job(job: dict) -> dict:
    return {key: job.get(key) for key in PUBLIC_JOB_FIELDS}


@bp.post("/jobs")
@require_token
def create_job():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"ok": False, "error": "請求內容需為 JSON 物件"}), 400
    payload.setdefault("idempotency_key", request.headers.get("Idempotency-Key"))
    try:
        req = validate_job_request(payload)
    except ContractError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    try:
        job, created = get_store().create_job(req, os.getenv("GEMINI_MODEL") or None)
    except ContractError as exc:  # idempotency_key reused with different content
        return jsonify({"ok": False, "error": str(exc)}), 409
    return jsonify({"ok": True, "created": created, "job": public_job(job)}), 202 if created else 200


@bp.get("/jobs/<job_id>")
@require_token
def job_status(job_id: str):
    store = get_store()
    job = store.get_job(job_id)
    if job is None:
        return jsonify({"ok": False, "error": "not_found"}), 404
    return jsonify({"ok": True, "job": public_job(job), "events": store.list_events(job_id)})


@bp.post("/jobs/<job_id>/cancel")
@require_token
def cancel_job(job_id: str):
    try:
        job = get_store().request_cancel(job_id)
    except KeyError:
        return jsonify({"ok": False, "error": "not_found"}), 404
    return jsonify({"ok": True, "job": public_job(job)})


# ----- W07-L: report versions, human approval, publication ---------------------
from flask import Response  # noqa: E402

from .publication import PublicationError, ReportStore  # noqa: E402


def get_reports() -> ReportStore:
    reports = current_app.extensions.get("report_store")
    if reports is None:
        root = Path(current_app.root_path) / "tmp"
        from research_ui.storage_supabase import storage_from_env  # noqa: PLC0415  (W07-A: Supabase when configured)

        # REPORT_DB_URL (postgresql://, Supabase) keeps versions across redeploys; else a local SQLite file.
        reports = ReportStore(os.getenv("REPORT_DB_URL") or os.getenv("REPORT_DB_PATH") or str(root / "reports.sqlite3"),
                              storage_from_env(os.getenv("REPORT_STORAGE_DIR") or str(root / "storage")))
        current_app.extensions["report_store"] = reports
    return reports


def require_admin(view):
    """Approval and publication need the logged-in lead; an API token is not enough."""
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not is_admin():
            return jsonify({"ok": False, "error": "請先以組長身分登入 /admin/login"}), 401
        return view(*args, **kwargs)

    return wrapper


def public_version(v: dict) -> dict:
    return {k: v.get(k) for k in ("report_version_id", "job_id", "version_no", "status", "report_hash", "pdf_hash",
                                  "storage_key", "approved_by", "approved_at", "published_at", "failure")}


@bp.post("/jobs/<job_id>/report")
@require_token
def create_report(job_id: str):
    store = get_store()
    job = store.get_job(job_id)
    if job is None:
        return jsonify({"ok": False, "error": "not_found"}), 404
    try:
        v = get_reports().create_version(job, store.list_events(job_id))
    except PublicationError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 409
    return jsonify({"ok": True, "version": public_version(v), "report": v["report"]})


@bp.get("/reports/<rv_id>")
@require_token
def get_report(rv_id: str):
    try:
        v = get_reports().get(rv_id)
    except KeyError:
        return jsonify({"ok": False, "error": "not_found"}), 404
    return jsonify({"ok": True, "version": public_version(v), "report": v["report"]})


@bp.post("/reports/<rv_id>/approve")
@require_admin
def approve_report(rv_id: str):
    seen = (request.get_json(silent=True) or {}).get("report_hash", "")
    try:
        v = get_reports().approve(rv_id, str(seen), approver="lead")
    except KeyError:
        return jsonify({"ok": False, "error": "not_found"}), 404
    except PublicationError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 409
    return jsonify({"ok": True, "version": public_version(v)})


@bp.post("/reports/<rv_id>/publish")
@require_admin
def publish_report(rv_id: str):
    try:
        v = get_reports().publish(rv_id)
    except KeyError:
        return jsonify({"ok": False, "error": "not_found"}), 404
    except PublicationError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 409
    return jsonify({"ok": True, "version": public_version(v)})


public_bp = Blueprint("public_reports", __name__, url_prefix="/reports")


@public_bp.get("")
def published_reports():
    """Read-only list for visitors and A's dashboard (0 LLM calls)."""
    return jsonify({"ok": True, "reports": get_reports().published()})


@public_bp.get("/<rv_id>.pdf")
def published_pdf(rv_id: str):
    try:
        data = get_reports().read_published_pdf(rv_id)
    except KeyError:
        return jsonify({"ok": False, "error": "not_found"}), 404
    except PublicationError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 404
    return Response(data, mimetype="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="{rv_id}.pdf"'})
