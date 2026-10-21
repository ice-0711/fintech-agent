"""W02-L: job contract, persistent queue, leases and API auth (offline)."""

import pytest
from flask import Flask

from agents.api import bp
from agents.contract import ContractError, validate_job_request
from agents.store import LEASE_SECONDS, JobStore, StaleLeaseError
from agents.worker import mock_handler, run_once
from conftest import job_request


def test_duplicate_create_returns_same_job(store):
    req = validate_job_request(job_request())
    first, created1 = store.create_job(req, None)
    second, created2 = store.create_job(req, None)
    assert created1 and not created2
    assert first["job_id"] == second["job_id"]


def test_job_survives_process_restart(db_path, clock):
    s1 = JobStore(db_path, clock=clock)
    job, _ = s1.create_job(validate_job_request(job_request()), None)
    s1.close()
    s2 = JobStore(db_path, clock=clock)
    assert s2.get_job(job["job_id"])["status"] == "queued"
    assert [e["event_type"] for e in s2.list_events(job["job_id"])] == ["job_created"]
    s2.close()


@pytest.mark.parametrize("ticker", ["2379", "3034"])
def test_comparison_only_tickers_do_not_create_llm_jobs(ticker):
    with pytest.raises(ContractError):
        validate_job_request(job_request(ticker=ticker))


@pytest.mark.parametrize("field,value", [("cutoff_at", "2026-09-30T13:30:00"), ("source_snapshot_id", ""),
                                         ("idempotency_key", ""), ("mode", "turbo"), ("ticker", "9999")])
def test_invalid_requests_rejected(field, value):
    with pytest.raises(ContractError):
        validate_job_request(job_request(**{field: value}))


def test_only_one_active_job(store):
    store.create_job(validate_job_request(job_request(idempotency_key="a")), None)
    store.create_job(validate_job_request(job_request(idempotency_key="b", ticker="2317")), None)
    assert store.claim_next("w1") is not None
    assert store.claim_next("w2") is None


def test_expired_lease_is_recovered_and_stale_worker_is_fenced(store, clock):
    job, _ = store.create_job(validate_job_request(job_request()), None)
    _, old_token = store.claim_next("crashed-worker")
    store.update_job(job["job_id"], "crashed-worker", old_token, {"calls_used": 3})

    clock.advance(LEASE_SECONDS + 1)  # worker died, no heartbeat
    recovered, new_token = store.claim_next("new-worker")
    assert recovered["job_id"] == job["job_id"]
    assert recovered["calls_used"] == 3, "budget counters must not reset on recovery"
    assert new_token == old_token + 1

    with pytest.raises(StaleLeaseError):
        store.update_job(job["job_id"], "crashed-worker", old_token, {"status": "succeeded"})
    assert "lease_recovered" in [e["event_type"] for e in store.list_events(job["job_id"])]


def test_heartbeat_keeps_lease(store, clock):
    job, _ = store.create_job(validate_job_request(job_request()), None)
    _, token = store.claim_next("w1")
    clock.advance(LEASE_SECONDS - 5)
    store.heartbeat(job["job_id"], "w1", token)
    clock.advance(LEASE_SECONDS - 5)
    assert store.claim_next("w2") is None


def test_mock_worker_completes_job(store):
    job, _ = store.create_job(validate_job_request(job_request()), None)
    final = run_once(store, "w1", mock_handler)
    assert final["status"] == "succeeded" and final["stop_reason"] == "mock_completed"
    assert final["checkpoint_version"] > 1
    assert run_once(store, "w1", mock_handler) is None


def test_worker_error_is_persisted_not_lost(store):
    store.create_job(validate_job_request(job_request()), None)

    def boom(lease):
        raise RuntimeError("tool crashed")

    final = run_once(store, "w1", boom)
    assert final["status"] == "failed" and "tool crashed" in final["stop_reason"]


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("RESEARCH_DB_PATH", str(tmp_path / "api.sqlite3"))
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    app = Flask(__name__)
    app.config["RESEARCH_API_TOKEN"] = "test-token"
    app.register_blueprint(bp)
    return app.test_client()


AUTH = {"Authorization": "Bearer test-token"}


def test_unauthorized_requests_rejected(client):
    assert client.post("/api/research/jobs", json=job_request()).status_code == 401
    assert client.post("/api/research/jobs", json=job_request(),
                       headers={"Authorization": "Bearer wrong"}).status_code == 401
    assert client.get("/api/research/jobs/x").status_code == 401


def test_api_is_closed_when_no_token_configured(tmp_path, monkeypatch):
    monkeypatch.setenv("RESEARCH_DB_PATH", str(tmp_path / "api.sqlite3"))
    monkeypatch.delenv("RESEARCH_API_TOKEN", raising=False)
    app = Flask(__name__)
    app.register_blueprint(bp)
    resp = app.test_client().post("/api/research/jobs", json=job_request(), headers={"Authorization": "Bearer "})
    assert resp.status_code == 401


def test_api_create_is_idempotent_and_status_readable(client):
    r1 = client.post("/api/research/jobs", json=job_request(), headers=AUTH)
    r2 = client.post("/api/research/jobs", json=job_request(), headers=AUTH)
    assert r1.status_code == 202 and r2.status_code == 200
    job_id = r1.get_json()["job"]["job_id"]
    assert r2.get_json()["job"]["job_id"] == job_id
    status = client.get(f"/api/research/jobs/{job_id}", headers=AUTH).get_json()
    assert status["job"]["status"] == "queued"
    assert status["job"]["model_id"] is None  # not configured → not invented
    assert "idempotency_key" not in status["job"]


def test_api_rejects_reference_ticker(client):
    resp = client.post("/api/research/jobs", json=job_request(ticker="3034"), headers=AUTH)
    assert resp.status_code == 400


def test_admin_login_session_authorises_research_api(tmp_path, monkeypatch):
    from agents.admin import bp as admin_bp, configure
    monkeypatch.setenv("RESEARCH_DB_PATH", str(tmp_path / "api.sqlite3"))
    monkeypatch.delenv("RESEARCH_API_TOKEN", raising=False)
    app = Flask(__name__)
    app.config.update(ADMIN_PASSWORD="right-pass", SECRET_KEY="test")
    configure(app)
    app.register_blueprint(admin_bp)
    app.register_blueprint(bp)
    c = app.test_client()
    assert c.post("/api/research/jobs", json=job_request()).status_code == 401
    assert "密碼錯誤" in c.post("/admin/login", data={"password": "wrong"}).get_data(as_text=True)
    assert c.post("/api/research/jobs", json=job_request()).status_code == 401
    assert c.post("/admin/login", data={"password": "right-pass"}).status_code == 302
    assert c.post("/api/research/jobs", json=job_request()).status_code == 202
    c.get("/admin/logout")
    assert c.get("/api/research/jobs/x").status_code == 401


def test_admin_login_closed_without_password(monkeypatch):
    from agents.admin import bp as admin_bp, configure
    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "test"
    configure(app)
    app.register_blueprint(admin_bp)
    c = app.test_client()
    assert "尚未設定 ADMIN_PASSWORD" in c.get("/admin/login").get_data(as_text=True)
    assert "密碼錯誤" in c.post("/admin/login", data={"password": ""}).get_data(as_text=True)
