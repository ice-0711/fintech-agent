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
