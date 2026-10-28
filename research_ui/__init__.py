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
POST /api/ui/jobs/<id>/report      (lead only) freeze a MOCK job into an immutable draft report version
POST /api/ui/jobs/<id>/approve     (lead only) approve the hash the lead saw, then publish (PDF → Storage)
GET  /api/ui/reports/<rv>/download published PDF as an attachment (read back from Storage, hash-checked)

W07-A: published versions come from the lead's ReportStore (agents/publication.py). The website
and the PDF both render the same approved report JSON; FIXTURE rows stay labelled FIXTURE.

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

from flask import Blueprint, Response, current_app, jsonify, render_template, request

from agents.admin import is_admin
from agents.contract import COMPARISON_ONLY_TICKERS, RESEARCH_TICKERS, ContractError

from agents import tools_impl
from agents.publication import PublicationError
from agents.snapshot import SnapshotToolbox

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
    real, store_error = _real_published()
    return jsonify({
        "ok": True,
        "source": "storage+fixture",
        "store_error": store_error,
        "synthetic_fixture": bool(fixture.get("synthetic_fixture")),
        "fixture_note": fixture.get("fixture_note"),
        "timezone": "Asia/Taipei",
        "reports": [_real_row(v) for v in real] + rows,
    })


# ----- W07-A: real published versions (ReportStore + Storage) -------------------------------
def _reports():
    from agents.api import get_reports  # noqa: PLC0415  (lead's store; env REPORT_DB_PATH / REPORT_STORAGE_DIR)

    return get_reports()


def _real_published() -> tuple[list[dict[str, Any]], str | None]:
    """Published versions only (the store never lists drafts or approved-but-unpublished ones)."""
    try:
        store = _reports()
        return [store.get(r["report_version_id"]) for r in store.published()], None
    except Exception as exc:  # noqa: BLE001 - the fixture list still renders; the error is shown
        return [], f"報告版本庫讀取失敗：{str(exc)[:160]}"


def _real_version(rv_id: str) -> dict[str, Any] | None:
    try:
        v = _reports().get(rv_id)
    except KeyError:
        return None
    return v if v["status"] == "published" else None


def _version_links(v: dict[str, Any]) -> dict[str, Any]:
    rv = v["report_version_id"]
    return {"report_version_id": rv, "version_no": v["version_no"], "published_at": v["published_at"],
            "report_hash": v["report_hash"], "pdf_hash": v["pdf_hash"],
            "pdf_url": f"/reports/{rv}.pdf", "download_url": f"/api/ui/reports/{rv}/download"}


def _real_row(v: dict[str, Any]) -> dict[str, Any]:
    """Card data read from the frozen report JSON — not recomputed, so web = PDF."""
    rep = v["report"]
    data = rep.get("data") or {}
    dq = data.get("data_quality") or {}
    val = data.get("valuation") or {}
    return {
        "report_version_id": v["report_version_id"], "ticker": rep["ticker"], "company": data.get("company"),
        "publication_status": "published", "research_outcome": "succeeded", "cutoff_at": rep["cutoff_at"],
        "published_at": v["published_at"], "pdf_status": "published" if v.get("storage_key") else "not_available",
        "synthetic_fixture": False, "run_label": rep.get("run_label") or "LIVE",
        "financial_period": data.get("financial_period"), "data_updated_at": data.get("available_at"),
        "snapshot_stale": any(c.get("check_id") == "freshness" and c.get("result") == "stale"
                              for c in dq.get("checks") or []),
        "valuation": {k: val.get(k) for k in ("status", "label", "gap", "reason", "dcf_per_share")},
        "data_quality": {"level": dq.get("level"), "label": dq.get("label"), "reasons": dq.get("reasons") or [],
                         "footnote": (data.get("method") or {}).get("risk_footnote")},
        **{k: x for k, x in _version_links(v).items() if k != "report_version_id"},
    }


def _history(v: dict[str, Any]) -> list[dict[str, Any]]:
    """Published versions of the same research job, newest first (drafts never appear)."""
    real, _ = _real_published()
    same = [x for x in real if x["job_id"] == v["job_id"]]
    return [_version_links(x) for x in sorted(same, key=lambda x: x["version_no"], reverse=True)]


def _real_detail(v: dict[str, Any]) -> dict[str, Any]:
    rep = v["report"]
    data = rep.get("data") or {}
    resolved = {s["id"]: bool(s.get("resolved")) for s in data.get("sources") or []}
    claims = []
    for claim in rep.get("claims", []):
        refs = [{"id": r, "exists": resolved.get(r, False)} for r in claim.get("evidence_refs") or []]
        claims.append({**claim, "evidence": refs, "unsourced": not any(r["exists"] for r in refs)})
    method = data.get("method") or {}
    return {
        **_real_row(v),
        "question": "截至資料截止，總經、基本面與估值證據支持哪些觀察？有哪些反向證據、假設與待確認訊號？",
        "question_version": rep.get("question_version"), "source_snapshot_id": rep["source_snapshot_id"],
        "model_id": rep.get("model_id"), "prompt_version": ", ".join(rep.get("prompt_versions") or []) or "—",
        "job_id": rep["job_id"], "claims": claims,
        "counter_evidence": rep.get("conflicts") or [], "next_signals": rep.get("next_signals") or [],
        "unknowns": rep.get("unknowns") or [],
        "limitations": (rep.get("limitations") or []) + (method.get("limitations") or []),
        "review": rep.get("review"), "disclaimer": rep.get("disclaimer"),
        "tables": {k: data.get(k) for k in ("scope", "scope_note", "quarters", "quarters_na_reason", "ttm", "price",
                                             "price_window", "peer_comparison", "peer_na_reason", "sources")}
        | {"dcf_assumptions": method.get("dcf_assumptions"), "sensitivity": (data.get("valuation") or {}).get("sensitivity"),
           "dcf_detail": (data.get("valuation") or {}).get("dcf_detail")},
        "history": _history(v),
    }


@bp.get("/api/ui/reports/<rv_id>/download")
def download_report(rv_id: str):
    if _real_version(rv_id) is None:
        return jsonify({"ok": False, "error": "not_found"}), 404
    try:
        data = _reports().read_published_pdf(rv_id)
    except (KeyError, PublicationError, OSError) as exc:
        return jsonify({"ok": False, "error": "pdf_unavailable", "message": str(exc)[:200]}), 404
    v = _reports().get(rv_id)
    name = f"{v['report']['ticker']}-v{v['version_no']}-{rv_id}.pdf"
    return Response(data, mimetype="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{name}"', "Cache-Control": "no-store"})


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
    real = _real_version(rv_id) if rv_id.startswith("rv-") and "fixture" not in rv_id else None
    if real is not None:
        return jsonify({"ok": True, "report": _real_detail(real), "synthetic_fixture": False, "timezone": "Asia/Taipei"})
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
    for v in _real_published()[0]:
        allowed.update(s["id"] for s in ((v["report"].get("data") or {}).get("sources") or []))
        for claim in v["report"].get("claims", []):
            allowed.update(claim.get("evidence_refs") or [])
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
    rv_id = request.args.get("report")
    real = _real_version(rv_id) if rv_id else None
    snap = next((x for x in ((real or {}).get("report", {}).get("data") or {}).get("sources") or []
                 if x.get("id") == ev_id and x.get("kind") == "financial_snapshot"), None)
    if snap is not None:  # a cited financial-snapshot tool result, exactly as frozen in the approved JSON
        after = tools_impl._parse_iso(snap["available_at"]) > tools_impl._parse_iso(real["report"]["cutoff_at"])
        return jsonify({"ok": True, "evidence": {
            "evidence_version_id": ev_id, "kind": "financial_snapshot", "paragraph": snap["excerpt"],
            "source_id": snap.get("source_id"), "source_url": None, "available_at": snap["available_at"],
            "content_hash": snap.get("content_hash"), "computed_hash": None, "hash_match": None,
            "hash_algorithm": snap.get("hash_note"),
            "cutoff_check": "cutoff 後才可得，不可引用" if after else "cutoff 前可得", "synthetic_fixture": False}})
    if real is not None:  # the exact snapshot of that report (case snapshots included)
        rep = real["report"]
        out = SnapshotToolbox(rep["ticker"], rep["source_snapshot_id"], rep["cutoff_at"]).read_evidence(ev_id)
    else:
        out = tools_impl.read_evidence(ev_id)
    if out.get("status") != "ok":
        return jsonify({"ok": False, "error": "no_data", "evidence_version_id": ev_id,
                        "message": "快照中沒有這個來源片段（無來源）"}), 404
    data = out["data"]
    computed = hashlib.sha256(data["paragraph"].encode("utf-8")).hexdigest()
    cutoff_note = None
    meta = {"cutoff_at": real["report"]["cutoff_at"]} if real else (_published_row(fixture, rv_id) if rv_id else None)
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
            "synthetic_fixture": real is None,
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


def _lead_only():
    if not is_admin():
        return jsonify({"ok": False, "error": "approval_requires_login",
                        "message": "核准發布只限登入的組長（/admin/login）。訪客只能閱讀已發布版本。"}), 403
    return None


def _mock_job_for_report(job_id: str):
    if not mock_enabled():
        return None, disabled()
    found = get_mock().get(job_id)
    if found is None:
        return None, (jsonify({"ok": False, "error": "not_found",
                               "message": "找不到這個 job（回放紀錄不能發布）"}), 404)
    return get_mock().store.get_job(job_id), None


@bp.post("/api/ui/jobs/<job_id>/report")
def create_report_version(job_id: str):
    """Lead only: freeze the reviewed MOCK job into an immutable draft version (not public)."""
    denied = _lead_only()
    if denied:
        return denied
    job, err = _mock_job_for_report(job_id)
    if err:
        return err
    try:
        v = _reports().create_version(job, get_mock().store.list_events(job_id))
    except PublicationError as exc:
        return jsonify({"ok": False, "error": "not_publishable", "message": str(exc)}), 409
    return jsonify({"ok": True, "version": {k: v[k] for k in ("report_version_id", "version_no", "status", "report_hash")},
                    "run_label": v["report"].get("run_label")})


@bp.post("/api/ui/jobs/<job_id>/approve")
def approve_job(job_id: str):
    """Lead only: approve exactly the hash the lead saw, then publish (PDF → Storage → read-back).

    Visitors get 403. A wrong/old hash or a newer version gets 409 from the store, nothing is published.
    """
    denied = _lead_only()
    if denied:
        return denied
    body = request.get_json(silent=True) or {}
    rv_id, seen = str(body.get("report_version_id") or ""), str(body.get("report_hash") or "")
    if not rv_id or not seen:
        return jsonify({"ok": False, "error": "version_required",
                        "message": "請先建立報告版本，確認內容與 hash 後再核准。"}), 409
    try:
        v = _reports().get(rv_id)
    except KeyError:
        return jsonify({"ok": False, "error": "not_found"}), 404
    if v["job_id"] != job_id:
        return jsonify({"ok": False, "error": "version_job_mismatch", "message": "版本不屬於這個 job"}), 409
    try:
        if v["status"] == "draft":
            _reports().approve(rv_id, seen, approver="lead")
        elif v["status"] in ("approved", "pdf_failed") and seen != v["report_hash"]:  # retry after a failed PDF
            raise PublicationError("hash 與目前版本不符：請重新檢視最新內容再核准")
        v = _reports().publish(rv_id)
    except PublicationError as exc:
        return jsonify({"ok": False, "error": "publication_failed", "message": str(exc)}), 409
    return jsonify({"ok": True, "version": {**_version_links(v), "status": v["status"]}})


@bp.get("/api/ui/session")
def ui_session():
    """Whether the viewer is the logged-in lead. No secret, no token, only a boolean."""
    return jsonify({"ok": True, "admin": is_admin()})
