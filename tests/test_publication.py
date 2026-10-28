"""W07-L: immutable report versions, human approval, publication (local storage)."""

import hashlib
import json

import pytest
from flask import Flask

from agents.publication import LocalStorage, PublicationError, ReportStore, canonical_hash

JOB = {"job_id": "job-1", "ticker": "2330", "cutoff_at": "2026-08-12T09:00:00+00:00",
       "source_snapshot_id": "snap-dev-case-01", "question_version": "q-v1", "mode": "dual",
       "model_id": "gemini-3.5-flash-lite", "status": "succeeded", "calls_used": 5, "tool_calls_used": 3,
       "tokens_observed": 9000, "supplement_rounds": 0,
       "draft": {"claims": [{"claim_id": "c1", "kind": "fact", "text": "2026Q2 營收 1,270,380,250 千元",
                             "evidence_refs": ["ev-dev-01-official-1"], "limitations": []}],
                 "limitations": ["估值缺同日股價"], "unknowns": ["股價"]},
       "review": {"decision": "pass", "checked_refs": ["ev-dev-01-official-1"], "decision_summary": "已核對"}}
EVENTS = [{"event_type": "model_call", "detail": {"prompt_version": "researcher-v1.2.2"}},
          {"event_type": "model_call", "detail": {"prompt_version": "reviewer-v1.2.0"}}]


@pytest.fixture
def reports(tmp_path):
    return ReportStore(tmp_path / "r.sqlite3", LocalStorage(tmp_path / "storage"))


def test_only_reviewed_successful_jobs_get_a_version(reports):
    with pytest.raises(PublicationError):
        reports.create_version(dict(JOB, status="insufficient_evidence"), EVENTS)
    with pytest.raises(PublicationError):
        reports.create_version(dict(JOB, review={"decision": "revise"}), EVENTS)
    v = reports.create_version(JOB, EVENTS)
    assert v["status"] == "draft" and v["version_no"] == 1
    assert v["report_hash"] == canonical_hash(v["report"])
    assert v["report"]["prompt_versions"] == ["researcher-v1.2.2", "reviewer-v1.2.0"]
    assert reports.create_version(JOB, EVENTS)["report_version_id"] == v["report_version_id"]  # idempotent


def test_approval_needs_matching_hash_and_newest_version(reports):
    v1 = reports.create_version(JOB, EVENTS)
    with pytest.raises(PublicationError, match="hash"):
        reports.approve(v1["report_version_id"], "stale-hash", "lead")
    changed = dict(JOB, draft=dict(JOB["draft"], limitations=["估值缺同日股價", "新增限制"]))
    v2 = reports.create_version(changed, EVENTS)
    assert v2["version_no"] == 2
    with pytest.raises(PublicationError, match="更新的版本"):
        reports.approve(v1["report_version_id"], v1["report_hash"], "lead")
    assert reports.approve(v2["report_version_id"], v2["report_hash"], "lead")["status"] == "approved"
    with pytest.raises(PublicationError):
        reports.approve(v2["report_version_id"], v2["report_hash"], "lead")  # not twice


def test_publish_renders_real_pdf_and_never_overwrites(reports):
    v = reports.create_version(JOB, EVENTS)
    with pytest.raises(PublicationError, match="核准"):
        reports.publish(v["report_version_id"])  # draft cannot be published
    reports.approve(v["report_version_id"], v["report_hash"], "lead")
    pub = reports.publish(v["report_version_id"])
    assert pub["status"] == "published" and pub["storage_key"].startswith("reports/2330/")
    pdf = reports.read_published_pdf(v["report_version_id"])
    assert pdf.startswith(b"%PDF") and hashlib.sha256(pdf).hexdigest() == pub["pdf_hash"]
    with pytest.raises(PublicationError, match="已發布"):
        reports.publish(v["report_version_id"])
    with pytest.raises(PublicationError, match="覆寫"):
        reports.storage.put(pub["storage_key"], b"other")
    assert [r["report_version_id"] for r in reports.published()] == [v["report_version_id"]]


def test_pdf_failure_is_recorded_and_retry_works(tmp_path):
    calls = {"n": 0}

    def flaky(report, version):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("font missing")
        return b"%PDF-1.4 ok"

    reports = ReportStore(tmp_path / "r.sqlite3", LocalStorage(tmp_path / "s"), renderer=flaky)
    v = reports.create_version(JOB, EVENTS)
    reports.approve(v["report_version_id"], v["report_hash"], "lead")
    with pytest.raises(PublicationError, match="pdf_failed"):
        reports.publish(v["report_version_id"])
    assert reports.get(v["report_version_id"])["status"] == "pdf_failed"
    with pytest.raises(PublicationError):
        reports.read_published_pdf(v["report_version_id"])  # not downloadable
    assert reports.publish(v["report_version_id"])["status"] == "published"


def test_tampered_content_is_not_published(reports):
    v = reports.create_version(JOB, EVENTS)
    reports.approve(v["report_version_id"], v["report_hash"], "lead")
    bad = dict(v["report"], claims=[{"claim_id": "c1", "text": "竄改"}])
    reports._db.run("update report_versions set report_json = ? where report_version_id = ?",
                    (json.dumps(bad, ensure_ascii=False), v["report_version_id"]))
    with pytest.raises(PublicationError, match="hash"):
        reports.publish(v["report_version_id"])


def test_api_approval_needs_the_logged_in_lead_not_a_token(tmp_path, monkeypatch):
    from agents.admin import bp as admin_bp, configure
    from agents.api import bp, get_store, public_bp
    monkeypatch.setenv("RESEARCH_DB_PATH", str(tmp_path / "jobs.sqlite3"))
    monkeypatch.setenv("REPORT_DB_PATH", str(tmp_path / "reports.sqlite3"))
    monkeypatch.setenv("REPORT_STORAGE_DIR", str(tmp_path / "storage"))
    app = Flask(__name__)
    app.config.update(ADMIN_PASSWORD="pw", SECRET_KEY="k", RESEARCH_API_TOKEN="tok")
    configure(app)
    for b in (admin_bp, bp, public_bp):
        app.register_blueprint(b)
    c = app.test_client()
    with app.app_context():
        reports = __import__("agents.api", fromlist=["get_reports"]).get_reports()
        v = reports.create_version(JOB, EVENTS)
    rv, token = v["report_version_id"], {"Authorization": "Bearer tok"}
    assert c.post(f"/api/research/reports/{rv}/approve", json={"report_hash": v["report_hash"]},
                  headers=token).status_code == 401  # token is not a human approval
    assert c.get(f"/reports/{rv}.pdf").status_code == 404  # unpublished is not public
    c.post("/admin/login", data={"password": "pw"})
    assert c.post(f"/api/research/reports/{rv}/approve", json={"report_hash": v["report_hash"]}).status_code == 200
    assert c.post(f"/api/research/reports/{rv}/publish").status_code == 200
    c.get("/admin/logout")
    listing = c.get("/reports").get_json()["reports"]
    assert listing[0]["report_version_id"] == rv
    pdf = c.get(f"/reports/{rv}.pdf")
    assert pdf.status_code == 200 and pdf.data.startswith(b"%PDF")
