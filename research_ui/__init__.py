"""V1.2 research workspace UI (A: W02–W04).

Routes
------
GET  /research                    workspace page (no job is created by opening it)
GET  /api/ui/published            published report metadata (read-only, 0 LLM)
POST /api/ui/mock/jobs            MOCK job create — only when RESEARCH_UI_MOCK=1
GET  /api/ui/jobs/<job_id>        MOCK job status + trace, read from the job DB
POST /api/ui/mock/jobs/<id>/cancel  cancel a running MOCK job
GET  /api/ui/reports/<rv_id>       published report detail (claims + sources), 0 LLM
GET  /api/ui/evidence/<ev_id>      exact evidence version for the source drawer, 0 LLM
GET  /api/ui/comparison/2454       peer-comparison panel (tool-reproduced values), 0 LLM
GET  /api/ui/replays               recorded live runs (REPLAY), 0 LLM
GET  /api/ui/replays/<id>          one recorded run with trace and review rounds
POST /api/ui/jobs/<id>/approve     always refused here: approval needs login (W07)

Rules from the handbook kept here:
* No API key or token is ever sent to the browser; the page cannot reach the
  real research API (authorisation is MOCK-only until 組長 decides).
* Public reads never start analysis: nothing here calls /api/analyze, FinMind,
  Supabase writes or Gemini.
* Only `publication_status == "published"` rows leave the server.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

from flask import Blueprint, current_app, jsonify, render_template, request

from agents.contract import COMPARISON_ONLY_TICKERS, RESEARCH_TICKERS, ContractError

from agents import tools_impl

from .comparison import build_comparison, company_row, referenced_evidence_ids
from .mock_jobs import SCENARIOS, MockJobs
from .replays import get_replay, list_replays

ROOT = Path(__file__).resolve().parent.parent
FIXTURE_PATH = ROOT / "ui" / "v12-dashboard-fixture.json"

bp = Blueprint("research_ui", __name__)

PUBLISHED_FIELDS = (
    "report_version_id", "ticker", "company", "publication_status", "research_outcome", "cutoff_at",
    "published_at", "pdf_status", "synthetic_fixture",
)


def enrich(row: dict[str, Any], cache: dict[str, Any]) -> dict[str, Any]:
    """Add tool-derived period, update time, valuation status and data-quality risk (0 LLM)."""
    code = row["ticker"]
    if code not in cache:
        try:
            cache[code] = company_row(code)
        except Exception as exc:  # noqa: BLE001 - show as unassessed, never as low risk
            cache[code] = {"error": str(exc)[:200]}
    c = cache[code]
    if "error" in c:
        return {**row, "financial_period": None, "data_updated_at": None, "snapshot_stale": None,
                "valuation": {"status": "undeterminable", "label": "無法判定", "gap": None, "reason": "比較資料讀取失敗"},
                "data_quality": {"level": "unassessed", "label": "資料品質風險：未評估", "reasons": [c["error"]]}}
    stale = any(ch["check_id"] == "freshness" and ch["result"] == "stale" for ch in c["data_quality"]["checks"])
    return {
        **row,
        "financial_period": c["financial_period"],
        "data_updated_at": c["available_at"],
        "snapshot_stale": stale,
        "valuation": {k: c["valuation"][k] for k in ("status", "label", "gap", "reason")} | {"dcf_per_share": c["valuation"]["dcf_per_share"]},
        "data_quality": {k: c["data_quality"][k] for k in ("level", "label", "reasons", "footnote")},
    }


def mock_enabled() -> bool:
    flag = current_app.config.get("RESEARCH_UI_MOCK")
    if flag is None:
        flag = os.getenv("RESEARCH_UI_MOCK") == "1"
    return bool(flag)


def get_mock() -> MockJobs:
    mock = current_app.extensions.get("research_ui_mock")
    if mock is None:
        path = current_app.config.get("RESEARCH_UI_MOCK_DB") or os.getenv("RESEARCH_UI_MOCK_DB") \
            or str(ROOT / "tmp" / "research_ui_mock.sqlite3")
        mock = MockJobs(path, ROOT, clock=current_app.config.get("RESEARCH_UI_CLOCK"))
        current_app.extensions["research_ui_mock"] = mock
    return mock


def load_fixture() -> dict[str, Any]:
    path = Path(current_app.config.get("RESEARCH_UI_FIXTURE") or FIXTURE_PATH)
    return json.loads(path.read_text(encoding="utf-8"))


def disabled():
    return jsonify({"ok": False, "error": "research_entry_disabled",
                    "message": "研究入口未啟用：目前只開放 MOCK 測試環境，正式授權由組長決定。"}), 403


@bp.get("/research")
def research_page():
    return render_template(
        "research.html",
        mock_enabled=mock_enabled(),
        research_tickers=RESEARCH_TICKERS,
        comparison_only=COMPARISON_ONLY_TICKERS,
        scenarios=SCENARIOS,
    )


@bp.get("/api/ui/published")
def published_reports():
    try:
        fixture = load_fixture()
    except (OSError, ValueError):
        return jsonify({"ok": False, "error": "published_metadata_unavailable"}), 503
    cache: dict[str, Any] = {}
    rows = [
        enrich({key: row.get(key) for key in PUBLISHED_FIELDS}, cache)
        for row in fixture.get("published_reports", [])
        if row.get("publication_status") == "published"
    ]
    return jsonify({
        "ok": True,
        "source": "fixture",
        "synthetic_fixture": bool(fixture.get("synthetic_fixture")),
        "fixture_note": fixture.get("fixture_note"),
        "timezone": "Asia/Taipei",
        "reports": rows,
    })


@bp.post("/api/ui/mock/jobs")
def create_mock_job():
    if not mock_enabled():
        return disabled()
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"ok": False, "error": "請求內容需為 JSON 物件"}), 400
    try:
        job, created = get_mock().create(payload)
    except ContractError as exc:
        status = 409 if "idempotency_key" in str(exc) else 400
        return jsonify({"ok": False, "error": str(exc)}), status
    return jsonify({"ok": True, "created": created, "job": job}), 202 if created else 200


@bp.get("/api/ui/jobs/<job_id>")
def mock_job_status(job_id: str):
    if not mock_enabled():
        return disabled()
    found = get_mock().get(job_id)
    if found is None:
        return jsonify({"ok": False, "error": "not_found"}), 404
    job, events = found
    return jsonify({"ok": True, "job": job, "events": events})


@bp.post("/api/ui/mock/jobs/<job_id>/cancel")
def cancel_mock_job(job_id: str):
    if not mock_enabled():
        return disabled()
    try:
        job = get_mock().cancel(job_id)
    except KeyError:
        return jsonify({"ok": False, "error": "not_found"}), 404
    except ContractError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 409
    return jsonify({"ok": True, "job": job})


# ----- W04: report detail, source drawer, comparison ------------------------------------
REPORT_FIELDS = ("question", "source_snapshot_id", "model_id", "prompt_version", "job_id",
                 "counter_evidence", "next_signals", "limitations")


def _published_row(fixture: dict[str, Any], rv_id: str) -> dict[str, Any] | None:
    return next((r for r in fixture.get("published_reports", [])
                 if r.get("report_version_id") == rv_id and r.get("publication_status") == "published"), None)


@bp.get("/api/ui/reports/<rv_id>")
def report_detail(rv_id: str):
    fixture = load_fixture()
    meta = _published_row(fixture, rv_id)
    detail = (fixture.get("reports") or {}).get(rv_id)
    if meta is None or detail is None:  # drafts and unknown versions look the same: not found
        return jsonify({"ok": False, "error": "not_found"}), 404
    claims = []
    for claim in detail.get("claims", []):
        refs = [{"id": r, "exists": tools_impl.read_evidence(r).get("status") == "ok"}
                for r in claim.get("evidence_refs", [])]
        claims.append({**claim, "evidence": refs, "unsourced": not any(r["exists"] for r in refs)})
    return jsonify({
        "ok": True,
        "report": {**enrich({k: meta.get(k) for k in PUBLISHED_FIELDS}, {}), **{k: detail.get(k) for k in REPORT_FIELDS},
                   "claims": claims},
        "synthetic_fixture": bool(fixture.get("synthetic_fixture")),
        "timezone": "Asia/Taipei",
    })


def _allowed_evidence(fixture: dict[str, Any]) -> set[str]:
    allowed = set(referenced_evidence_ids())
    for row in fixture.get("published_reports", []):
        if row.get("publication_status") != "published":
            continue
        for claim in ((fixture.get("reports") or {}).get(row["report_version_id"]) or {}).get("claims", []):
            allowed.update(claim.get("evidence_refs", []))
    return allowed


@bp.get("/api/ui/evidence/<ev_id>")
def evidence_detail(ev_id: str):
    fixture = load_fixture()
    if ev_id not in _allowed_evidence(fixture):
        return jsonify({"ok": False, "error": "not_referenced", "message": "只開放已發布報告或比較面板引用的來源"}), 404
    out = tools_impl.read_evidence(ev_id)
    if out.get("status") != "ok":
        return jsonify({"ok": False, "error": "no_data", "evidence_version_id": ev_id,
                        "message": "快照中沒有這個來源片段（無來源）"}), 404
    data = out["data"]
    computed = hashlib.sha256(data["paragraph"].encode("utf-8")).hexdigest()
    cutoff_note = None
    rv_id = request.args.get("report")
    meta = _published_row(fixture, rv_id) if rv_id else None
    if meta and meta.get("cutoff_at"):
        after = tools_impl._parse_iso(data["available_at"]) > tools_impl._parse_iso(meta["cutoff_at"])
        cutoff_note = "cutoff 後才可得，不可引用" if after else "cutoff 前可得"
    return jsonify({
        "ok": True,
        "evidence": {
            **data,
            "hash_algorithm": "sha256(paragraph, utf-8)",
            "computed_hash": computed,
            "hash_match": computed == data["content_hash"],
            "cutoff_check": cutoff_note,
            "synthetic_fixture": True,
        },
    })


@bp.get("/api/ui/comparison/2454")
def comparison_2454():
    try:
        return jsonify(build_comparison())
    except (OSError, ValueError, KeyError) as exc:
        return jsonify({"ok": False, "error": "comparison_unavailable", "message": str(exc)}), 503


# ----- W05: replays and the (refused) approval action ------------------------------------
@bp.get("/api/ui/replays")
def replays():
    try:
        return jsonify({"ok": True, "label": "REPLAY", "replays": list_replays()})
    except (OSError, ValueError, KeyError) as exc:
        return jsonify({"ok": False, "error": "replays_unavailable", "message": str(exc)[:200]}), 503


@bp.get("/api/ui/replays/<path:replay_id>")
def replay_detail(replay_id: str):
    try:
        found = get_replay(replay_id)
    except (OSError, ValueError, KeyError) as exc:
        return jsonify({"ok": False, "error": "replays_unavailable", "message": str(exc)[:200]}), 503
    if found is None:
        return jsonify({"ok": False, "error": "not_found"}), 404
    return jsonify({"ok": True, **found})


@bp.post("/api/ui/jobs/<job_id>/approve")
def approve_job(job_id: str):
    """Human approval is W07 work and needs login; this UI never publishes."""
    return jsonify({"ok": False, "error": "approval_requires_login",
                    "message": "核准發布需要登入的核准人（W07 開放）。研究工作台目前不能發布任何版本。"}), 403
