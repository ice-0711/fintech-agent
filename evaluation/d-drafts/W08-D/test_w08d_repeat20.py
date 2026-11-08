"""W08-D: 20 identical requests (offline, local SQLite, no network, no live Supabase)."""
import sqlite3
import pytest
from flask import Flask

from agents.api import bp
from conftest import job_request

AUTH = {"Authorization": "Bearer test-token"}


@pytest.fixture
def client(tmp_path, monkeypatch):
    db = tmp_path / "api.sqlite3"
    monkeypatch.setenv("RESEARCH_DB_PATH", str(db))
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    app = Flask(__name__)
    app.config["RESEARCH_API_TOKEN"] = "test-token"
    app.register_blueprint(bp)
    c = app.test_client()
    c.db_path = db
    return c


def _count_jobs(db):
    con = sqlite3.connect(db)
    try:
        tables = [r[0] for r in con.execute("select name from sqlite_master where type='table'")]
        t = next(n for n in tables if "job" in n.lower() and "lease" not in n.lower() and "event" not in n.lower())
        return con.execute(f"select count(*) from {t}").fetchone()[0], t
    finally:
        con.close()


def test_20_identical_authorized_requests_create_one_job(client):
    codes, ids = [], set()
    for _ in range(20):
        r = client.post("/api/research/jobs", json=job_request(), headers=AUTH)
        codes.append(r.status_code)
        ids.add(r.get_json()["job"]["job_id"])
    assert codes[0] == 202 and all(c == 200 for c in codes[1:])
    assert len(ids) == 1
    n, table = _count_jobs(client.db_path)
    assert n == 1, f"{table} has {n} rows"


def test_20_unauthorized_requests_all_401_and_create_nothing(client):
    codes = [client.post("/api/research/jobs", json=job_request()).status_code for _ in range(20)]
    assert codes == [401] * 20
    try:
        n, _ = _count_jobs(client.db_path)
    except (StopIteration, sqlite3.OperationalError):
        n = 0
    assert n == 0
