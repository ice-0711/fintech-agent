"""A's research workspace UI (W02-A, W03-A, W04-A). Offline, no network, no LLM."""

from __future__ import annotations

import json

import pytest
from flask import Flask

from conftest import ROOT
from research_ui import bp

STATIC_JS = (ROOT / "static" / "research.js").read_text(encoding="utf-8")


def make_app(tmp_path, clock=None, mock=True):
    app = Flask(__name__, root_path=str(ROOT), template_folder="templates", static_folder="static")
    app.add_url_rule("/", "index", lambda: "home")
    app.config.update(RESEARCH_UI_MOCK=mock, RESEARCH_UI_MOCK_DB=str(tmp_path / "ui.sqlite3"), RESEARCH_UI_CLOCK=clock)
    from agents.publication import LocalStorage, ReportStore

    app.extensions["report_store"] = ReportStore(tmp_path / "reports.sqlite3", LocalStorage(tmp_path / "storage"))
    app.register_blueprint(bp)
    return app


@pytest.fixture
def ui(tmp_path, clock):
    return make_app(tmp_path, clock).test_client()


def create(client, **overrides):
    payload = {"ticker": "2454", "cutoff_at": "2026-09-30T17:00:00+08:00", "mode": "dual",
               "scenario": "succeeded", "idempotency_key": "ui-test-1"}
    payload.update(overrides)
    return client.post("/api/ui/mock/jobs", json=payload)


# ----- W02: page, safety, favourites/published -------------------------------------
def test_page_renders_without_secrets_or_sync_analysis(ui, monkeypatch):
    monkeypatch.setenv("RESEARCH_API_TOKEN", "super-secret-token")
    monkeypatch.setenv("SUPABASE_KEY", "supabase-secret")
    html = ui.get("/research").get_data(as_text=True)
    assert "研究工作台" in html
    for text in (html, STATIC_JS):
        assert "super-secret-token" not in text and "supabase-secret" not in text
        assert "/api/analyze" not in text and "Authorization" not in text


def test_web_app_registers_workspace():
    import web_app

    rules = {r.rule for r in web_app.app.url_map.iter_rules()}
    assert {"/research", "/api/ui/published", "/api/ui/mock/jobs", "/api/ui/jobs/<job_id>"} <= rules


def test_published_list_hides_drafts_and_marks_fixture(ui):
    body = ui.get("/api/ui/published").get_json()
    ids = [r["report_version_id"] for r in body["reports"]]
    assert ids and all(r["publication_status"] == "published" for r in body["reports"])
    assert "rv-fixture-2454-0002-draft" not in ids
    assert body["synthetic_fixture"] is True and all(r["synthetic_fixture"] for r in body["reports"])


def test_reading_pages_never_starts_analysis(ui, monkeypatch):
    import web_app

    def boom(*_a, **_k):
        raise AssertionError("public read started a synchronous analysis")

    monkeypatch.setattr(web_app, "stock_payload", boom)
    for url in ("/research", "/api/ui/published", "/research?job=x"):
        assert ui.get(url).status_code == 200


def test_favourites_are_codes_only_and_capped():
    assert 'const FAV_MAX = 5;' in STATIC_JS
    assert '["2330", "2317", "2454", "2379", "3034"]' in STATIC_JS
    assert "localStorage.setItem(FAV_KEY, JSON.stringify(list.slice(0, FAV_MAX)))" in STATIC_JS


# ----- W02: MOCK entry ----------------------------------------------------------------
def test_entry_closed_when_mock_disabled(tmp_path):
    client = make_app(tmp_path, mock=False).test_client()
    assert create(client).status_code == 403
    assert client.get("/api/ui/jobs/x").status_code == 403
    assert "研究入口未啟用" in client.get("/research").get_data(as_text=True)


def test_repeated_click_returns_same_job(ui):
    first = create(ui)
    again = create(ui)
    assert first.status_code == 202 and again.status_code == 200
    assert first.get_json()["job"]["job_id"] == again.get_json()["job"]["job_id"]


def test_comparison_tickers_never_create_jobs(ui):
    for code in ("2379", "3034"):
        resp = create(ui, ticker=code, idempotency_key=f"ui-{code}")
        assert resp.status_code == 400 and "比較參照" in resp.get_json()["error"]


def test_bad_requests_rejected(ui):
    assert create(ui, cutoff_at="", idempotency_key="k2").status_code == 400
    assert create(ui, scenario="hack", idempotency_key="k3").status_code == 400
    assert create(ui).status_code == 202
    assert create(ui, ticker="2330").status_code == 409  # same key, different content


def test_job_survives_restart(tmp_path, clock):
    job_id = create(make_app(tmp_path, clock).test_client()).get_json()["job"]["job_id"]
    reopened = make_app(tmp_path, clock).test_client()  # new app, same DB file
    assert reopened.get(f"/api/ui/jobs/{job_id}").get_json()["job"]["job_id"] == job_id


def test_succeeded_path_progresses_from_db(ui, clock):
    job_id = create(ui).get_json()["job"]["job_id"]
    statuses = []
    for _ in range(12):
        statuses.append(ui.get(f"/api/ui/jobs/{job_id}").get_json()["job"]["status"])
        clock.advance(2)
    assert statuses[0] == "running" and statuses[-1] == "succeeded"
    assert "succeeded" not in statuses[:2]  # pending does not pose as complete


def test_insufficient_path(ui, clock):
    job_id = create(ui, ticker="2317", scenario="insufficient_evidence", idempotency_key="k-ins").get_json()["job"]["job_id"]
    for _ in range(8):
        body = ui.get(f"/api/ui/jobs/{job_id}").get_json()
        clock.advance(2)
    assert body["job"]["status"] == "insufficient_evidence"
    assert body["job"]["stop_reason"]


def test_events_expose_only_whitelisted_fields(ui, clock):
    job_id = create(ui).get_json()["job"]["job_id"]
    for _ in range(10):
        body = ui.get(f"/api/ui/jobs/{job_id}").get_json()
        clock.advance(2)
    allowed = {"mock", "summary", "decision_summary", "evidence_refs", "latency_ms", "tool_status", "args_redacted",
               "output_hash", "claim_id", "severity", "required_evidence", "budget"}
    assert body["events"]
    for event in body["events"]:
        assert set(event["detail"]) <= allowed
        assert event["detail"].get("mock") is True or event["event_type"] in ("job_created", "lease_acquired", "lease_recovered")
    assert "idempotency_key" not in json.dumps(body["job"])


# ----- W03: real job states, trace, cancel ------------------------------------------
def run_until_done(client, clock, job_id, polls=20):
    body = None
    for _ in range(polls):
        body = client.get(f"/api/ui/jobs/{job_id}").get_json()
        if body["job"]["status"] not in ("queued", "running"):
            break
        clock.advance(2)
    return body


@pytest.mark.parametrize("scenario,ticker,final", [
    ("succeeded", "2454", "succeeded"),
    ("insufficient_evidence", "2317", "insufficient_evidence"),
    ("paused_quota", "2330", "paused_quota"),
    ("failed", "2454", "failed"),
    ("timed_out", "2454", "timed_out"),
])
def test_each_status_screen_reaches_its_state(ui, clock, scenario, ticker, final):
    job_id = create(ui, ticker=ticker, scenario=scenario, idempotency_key=f"k-{scenario}").get_json()["job"]["job_id"]
    body = run_until_done(ui, clock, job_id)
    assert body["job"]["status"] == final
    assert body["job"]["stop_reason"]
    if final == "paused_quota":
        assert body["job"]["calls_used"] == 2  # accumulated budget kept, not reset
        clock.advance(600)
        assert ui.get(f"/api/ui/jobs/{job_id}").get_json()["job"]["status"] == "paused_quota"  # no silent retry


def test_trace_shows_real_tool_results_and_source_ids(ui, clock):
    job_id = create(ui).get_json()["job"]["job_id"]
    events = run_until_done(ui, clock, job_id)["events"]
    tools = [e for e in events if e["tool_name"]]
    assert {e["tool_name"] for e in tools} == {"search_evidence", "read_evidence", "get_financial_snapshot"}
    read = next(e for e in tools if e["tool_name"] == "read_evidence")
    assert read["detail"]["tool_status"] == "ok" and read["detail"]["evidence_refs"] == ["ev-2454-2026q2-01"]
    assert {e["role"] for e in tools} == {"researcher", "reviewer"}
    for e in tools:
        assert e["created_at"] and e["detail"]["output_hash"] and "latency_ms" in e["detail"]
        assert e["detail"]["args_redacted"].get("cutoff", "<job.cutoff_at>") == "<job.cutoff_at>"


def test_missing_data_is_no_data_not_zero(ui, clock):
    # A cutoff before any snapshot data: every tool must answer no_data, never a 0.
    job_id = create(ui, ticker="2317", scenario="insufficient_evidence", cutoff_at="2025-01-01T09:00:00+08:00",
                    idempotency_key="k-2317-early").get_json()["job"]["job_id"]
    events = run_until_done(ui, clock, job_id)["events"]
    fin = next(e for e in events if e["tool_name"] == "get_financial_snapshot")
    assert fin["detail"]["tool_status"] == "no_data"
    assert "0" != fin["detail"]["summary"]


def test_second_job_waits_in_queue(ui, clock):
    first = create(ui).get_json()["job"]["job_id"]
    second = create(ui, ticker="2330", idempotency_key="k-second").get_json()["job"]["job_id"]
    ui.get(f"/api/ui/jobs/{first}")
    queued = ui.get(f"/api/ui/jobs/{second}").get_json()["job"]
    assert queued["status"] == "queued" and queued["queue_ahead"] == 1


def test_cancel_running_job_only(ui, clock):
    job_id = create(ui).get_json()["job"]["job_id"]
    ui.get(f"/api/ui/jobs/{job_id}")
    resp = ui.post(f"/api/ui/mock/jobs/{job_id}/cancel")
    assert resp.status_code == 200 and resp.get_json()["job"]["status"] == "cancelled"
    assert ui.post(f"/api/ui/mock/jobs/{job_id}/cancel").status_code == 409
    clock.advance(30)
    assert ui.get(f"/api/ui/jobs/{job_id}").get_json()["job"]["status"] == "cancelled"  # stays cancelled
    assert ui.post("/api/ui/mock/jobs/nope/cancel").status_code == 404


def test_status_is_read_from_db_by_another_process(tmp_path, clock):
    writer = make_app(tmp_path, clock).test_client()
    job_id = create(writer).get_json()["job"]["job_id"]
    run_until_done(writer, clock, job_id)
    reader = make_app(tmp_path, clock).test_client()  # separate app, same DB file
    assert reader.get(f"/api/ui/jobs/{job_id}").get_json()["job"]["status"] == "succeeded"


# ----- W04: report detail, source drawer, comparison -----------------------------------
def test_report_detail_marks_claim_kinds_and_unsourced(ui):
    body = ui.get("/api/ui/reports/rv-fixture-2454-0002").get_json()
    claims = {c["claim_id"]: c for c in body["report"]["claims"]}
    assert {c["kind"] for c in claims.values()} == {"fact", "inference", "unknown"}
    assert claims["c1"]["unsourced"] is False and claims["c1"]["evidence"] == [{"id": "ev-2454-2026q2-01", "exists": True}]
    assert claims["c3"]["unsourced"] is True and claims["c4"]["unsourced"] is True
    assert body["report"]["synthetic_fixture"] is True


def test_unpublished_report_never_leaves_server(ui):
    assert ui.get("/api/ui/reports/rv-fixture-2454-0003-draft").status_code == 404
    assert ui.get("/api/ui/reports/does-not-exist").status_code == 404
    for url in ("/api/ui/published", "/research", "/api/ui/reports/rv-fixture-2454-0002"):
        assert "DRAFT-SECRET" not in ui.get(url).get_data(as_text=True)


def test_evidence_drawer_reports_hash_and_cutoff_honestly(ui):
    import hashlib

    e = ui.get("/api/ui/evidence/ev-2454-2026q2-01?report=rv-fixture-2454-0002").get_json()["evidence"]
    assert e["computed_hash"] == hashlib.sha256(e["paragraph"].encode()).hexdigest()
    assert e["hash_match"] is (e["computed_hash"] == e["content_hash"])  # a mismatch would be shown, not hidden
    assert e["cutoff_check"] == "cutoff 前可得"


def test_fixture_claims_quote_their_source_text(ui):
    """Every fact claim in the FIXTURE reports must quote numbers that appear in its cited paragraph."""
    import re

    fixture = json.loads((ROOT / "ui" / "v12-dashboard-fixture.json").read_text(encoding="utf-8"))
    for rv, report in fixture["reports"].items():
        if rv.endswith("-draft"):
            continue
        for claim in report["claims"]:
            if claim["kind"] != "fact":
                continue
            text = "".join(ui.get(f"/api/ui/evidence/{ref}").get_json()["evidence"]["paragraph"] for ref in claim["evidence_refs"])
            for number in re.findall(r"\d[\d,]*\.?\d*", claim["text"].replace("2026Q2", "")):
                assert number in text, f"{rv} {claim['claim_id']}: {number} not in source"


def test_evidence_missing_or_unreferenced(ui):
    missing = ui.get("/api/ui/evidence/ev-price-20260930-2454")
    assert missing.status_code == 404
    other = ui.get("/api/ui/evidence/src-2454-2026q2-announce")
    assert other.status_code == 404 and other.get_json()["error"] == "not_referenced"


def test_comparison_rules(ui):
    d = ui.get("/api/ui/comparison/2454").get_json()
    rows = {r["ticker"]: r for r in d["rows"]}
    assert list(rows) == ["2454", "2379", "3034", "2330"] and len(rows) <= 4
    assert rows["2330"]["role"] == "industry_reference" and rows["2330"]["include_in_peer_stats"] is False
    assert set(d["peer_stats"]["excluded"]) == {"2454", "2330"}
    for r in d["rows"]:
        assert r["financial_period"] and r["price"]["trade_date"] == d["price_as_of"]
        pe = r["metrics"]["pe_ttm"]
        assert pe["source"] == "tool" and pe["value"] == round(r["price"]["value"] / pe["eps_ttm"], 2)
        assert pe["consistent"] is True  # tool value equals B's peer snapshot
        for name, m in r["metrics"].items():
            assert m["value"] != 0, f"{r['ticker']} {name} shows 0"
            if m["value"] is None:
                assert m["na_reason"]
    peers = [rows["2379"], rows["3034"]]
    expected = round(sum(r["metrics"]["pe_ttm"]["value"] for r in peers) / 2, 2)
    assert d["peer_stats"]["pe_ttm"]["value"] == expected == d["peer_stats"]["snapshot_values"]["pe_ttm"]


def test_comparison_dcf_uses_lead_assumptions(ui):
    d = ui.get("/api/ui/comparison/2454").get_json()
    assert d["dcf_assumptions"]["wacc"] == 0.09 and d["dcf_assumptions"]["terminal_growth"] == 0.03
    s = next(r for r in d["rows"] if r["ticker"] == "2454")
    from agents.calculator import calculate_dcf_scenario
    from agents import tools_impl

    m = tools_impl.get_financial_snapshot("2454", d["cutoff_at"])["data"]["metrics"]
    expect = calculate_dcf_scenario([m["fcf_ttm"]] * 5, 0.09, 0.03, m["net_debt"], m["shares_outstanding_m"])
    assert s["valuation"]["dcf_per_share"] == expect["intrinsic_value_per_share"]
    gap = (expect["intrinsic_value_per_share"] - s["price"]["value"]) / s["price"]["value"]
    assert s["valuation"]["gap"] == round(gap, 4)
    assert s["valuation"]["sensitivity"]["9.0%"]["3.0%"] == expect["intrinsic_value_per_share"]


def test_read_only_ui_has_no_model_code():
    for path in (ROOT / "research_ui").glob("*.py"):
        imports = [line for line in path.read_text(encoding="utf-8").splitlines()
                   if line.startswith(("import ", "from "))]
        assert not [line for line in imports if "provider" in line or "genai" in line or "budget" in line]
