"""Forward (LIVE) reports read the snapshot their job ran on (A, 11/08).

Found on Render 11/08: the two published LIVE versions (forward batches 1–2) had their frozen data section built
from the frozen 30-case snapshot, so every claim's source showed as unresolved ("無來源") and the valuation used the
2026-09-30 close instead of the forward snapshot's close at the report cutoff. Offline, 0 LLM.
"""

from __future__ import annotations

import json
from pathlib import Path

from agents import tools_impl
from agents.publication import LocalStorage, ReportStore
from research_ui.report_data import build_report_data, forward_snapshot_file

ROOT = Path(__file__).resolve().parents[1]


def forward_job(batch: int, ticker: str) -> dict:
    rec = json.loads((ROOT / "research" / f"forward-batch-{batch}.json").read_text(encoding="utf-8"))
    reports = json.loads((ROOT / "research" / f"forward-batch-{batch}-reports.json").read_text(encoding="utf-8"))
    r = next(x for x in reports["reports"] if x["ticker"] == ticker)
    return {"job_id": r["job_id"], "ticker": ticker, "cutoff_at": rec["signal_cutoff_at"], "mode": "dual",
            "question_version": "q-v1", "status": r["status"], "draft": r["draft"], "review": r["review"],
            "source_snapshot_id": f"snap-fwd{batch}-{rec['snapshot_sha256'][:12]}", "model_id": reports["model_id"]}


def test_forward_snapshot_id_maps_to_its_file_only_when_the_hash_matches():
    assert forward_snapshot_file("snap-fwd2-f8bedf9f5c7e").name == "financial-snapshots-2026-11-06.json"
    assert forward_snapshot_file("snap-fwd2-000000000000") is None
    assert forward_snapshot_file("fin-snap:v1.6-tw-market") is None


def test_forward_2330_report_uses_the_forward_close_and_resolves_its_sources():
    data = build_report_data(forward_job(2, "2330"))
    assert data["snapshot_file"] == "data/forward/financial-snapshots-2026-11-06.json"
    assert data["price"]["trade_date"] == "2026-11-06" and data["price"]["value"] == 2135.0
    cited = {ref for c in forward_job(2, "2330")["draft"]["claims"] for ref in c["evidence_refs"]}
    resolved = {s["id"] for s in data["sources"] if s["resolved"]}
    assert cited and cited <= resolved
    # the override is only for the build: afterwards the tools read the frozen snapshot again
    assert tools_impl._snapshot_path() == tools_impl.SNAPSHOT_PATH


def test_unknown_forward_snapshot_shows_no_tables_instead_of_other_data():
    job = dict(forward_job(2, "2330"), source_snapshot_id="snap-fwd2-000000000000")
    data = build_report_data(job)
    assert data["scope"] == "unavailable" and data["quarters"] is None and data["sources"] == []


def test_evidence_drawer_reads_the_forward_snapshot(tmp_path, clock):
    from test_research_ui import make_app

    app = make_app(tmp_path, clock)
    store = app.extensions["report_store"] = ReportStore(tmp_path / "r.sqlite3", LocalStorage(tmp_path / "s"))
    job = forward_job(2, "2330")
    v = store.create_version(job, [])
    store.approve(v["report_version_id"], v["report_hash"], approver="lead")
    store.publish(v["report_version_id"])
    client = app.test_client()
    report = client.get(f"/api/ui/reports/{v['report_version_id']}").get_json()["report"]
    assert all(e["exists"] for c in report["claims"] for e in c["evidence"])
    ref = report["claims"][0]["evidence"][0]["id"]
    ev = client.get(f"/api/ui/evidence/{ref}?report={v['report_version_id']}").get_json()["evidence"]
    assert ev["hash_match"] and ev["cutoff_check"] == "cutoff 前可得"


# ----- source_traceable (B 11/09): statement hashes + cited ev- fragments, no default fragment ID ------------
import copy  # noqa: E402
import glob  # noqa: E402

import pytest  # noqa: E402

from research_ui import comparison  # noqa: E402


@pytest.mark.parametrize("path", ["data/financial-snapshots.json", *sorted(glob.glob(str(ROOT / "data/forward/*.json")))])
def test_every_quarter_hash_is_the_three_statement_files(path):
    snap = json.loads((ROOT / path).read_text(encoding="utf-8"))
    n = 0
    for code, company in snap["financials"].items():
        for q in company["quarters"]:
            assert q["content_hash"] == comparison._statement_hash(snap, code), (code, q["period"])
            n += 1
    assert n == 25


def test_forward_live_reports_are_low_risk_once_quarters_are_traced():
    for batch, ticker in ((2, "2330"), (1, "2317")):
        dq = build_report_data(forward_job(batch, ticker))["data_quality"]
        trace = next(c for c in dq["checks"] if c["check_id"] == "source_traceable")
        assert trace["result"] == "pass" and dq["level"] == "low", (ticker, dq)


def _patched(monkeypatch, mutate):
    snap = copy.deepcopy(tools_impl._load_snapshots())
    mutate(snap)
    monkeypatch.setattr(tools_impl, "_load_snapshots", lambda: snap)


CUT = "2026-09-30T17:30:00+08:00"
TTM = ["2025Q3", "2025Q4", "2026Q1", "2026Q2", "2025Q2"]


def test_tampered_quarter_hash_is_a_conflict(monkeypatch):
    _patched(monkeypatch, lambda s: s["financials"]["2330"]["quarters"][-1].update(content_hash="0" * 64))
    assert comparison.financial_traceability("2330", CUT, TTM)[0] == "conflict"


def test_quarter_without_source_id_is_missing(monkeypatch):
    _patched(monkeypatch, lambda s: s["financials"]["2330"]["quarters"][0].pop("source_id"))
    result, detail = comparison.financial_traceability("2330", CUT, TTM)
    assert result == "missing" and "2025Q2" in detail


def test_quarter_published_after_cutoff_is_a_conflict():
    result, detail = comparison.financial_traceability("2330", "2026-08-01T00:00:00+08:00", TTM)
    assert result == "conflict" and "2026Q2" in detail


def test_only_cited_fragments_are_checked_and_no_default_id_is_added():
    row = comparison.company_row_at("2317", CUT, cited_refs=[])
    assert row["evidence"] == []
    assert next(c for c in row["data_quality"]["checks"] if c["check_id"] == "source_traceable")["result"] == "pass"
    bad = comparison.company_row_at("2317", CUT, cited_refs=["ev-does-not-exist"])
    trace = next(c for c in bad["data_quality"]["checks"] if c["check_id"] == "source_traceable")
    assert trace["result"] == "missing" and "ev-does-not-exist" in trace["detail"]
