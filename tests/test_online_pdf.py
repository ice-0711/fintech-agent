"""W07-A: online research PDF from the approved report JSON; preview / download / history. Offline, 0 LLM."""

from __future__ import annotations

import json

import pymupdf
import pytest

from agents.publication import MAX_PDF_BYTES, MAX_PDF_PAGES, PublicationError
from research_ui.storage_supabase import SupabaseStorage, storage_from_env
from test_research_ui import create, make_app, run_until_done

CUTOFF = "2026-09-30T17:30:00+08:00"  # = 2454 peer snapshot cutoff


@pytest.fixture
def lead(tmp_path, clock):
    app = make_app(tmp_path, clock)
    app.secret_key = "test"
    client = app.test_client()
    with client.session_transaction() as sess:
        sess["admin"] = True
    return app, client


def publish(client, clock, ticker, key="w07"):
    job_id = create(client, ticker=ticker, cutoff_at=CUTOFF, scenario="revise_then_pass",
                    idempotency_key=f"{key}-{ticker}").get_json()["job"]["job_id"]
    assert run_until_done(client, clock, job_id)["job"]["status"] == "succeeded"
    v = client.post(f"/api/ui/jobs/{job_id}/report").get_json()["version"]
    assert v["status"] == "draft"
    body = client.post(f"/api/ui/jobs/{job_id}/approve",
                       json={"report_version_id": v["report_version_id"], "report_hash": v["report_hash"]}).get_json()
    assert body["ok"], body
    return job_id, body["version"]


def pdf_text(data: bytes) -> tuple[pymupdf.Document, str]:
    doc = pymupdf.open(stream=data, filetype="pdf")
    return doc, "".join(p.get_text() for p in doc)


def test_draft_is_not_public_until_the_lead_approves_the_seen_hash(lead, clock):
    app, client = lead
    job_id = create(client, ticker="2330", cutoff_at=CUTOFF, scenario="revise_then_pass",
                    idempotency_key="w07-draft").get_json()["job"]["job_id"]
    run_until_done(client, clock, job_id)
    v = client.post(f"/api/ui/jobs/{job_id}/report").get_json()["version"]
    visitor = app.test_client()
    assert v["report_version_id"] not in json.dumps(visitor.get("/api/ui/published").get_json())
    assert visitor.get(f"/api/ui/reports/{v['report_version_id']}").status_code == 404
    assert visitor.get(f"/api/ui/reports/{v['report_version_id']}/download").status_code == 404
    assert visitor.get(f"/reports/{v['report_version_id']}.pdf").status_code in (404, 405)  # lead's bp not mounted here
    assert visitor.post(f"/api/ui/jobs/{job_id}/approve", json={}).status_code == 403
    wrong = client.post(f"/api/ui/jobs/{job_id}/approve", json={"report_version_id": v["report_version_id"],
                                                               "report_hash": "0" * 64})
    assert wrong.status_code == 409 and "hash" in wrong.get_json()["message"]


def test_2454_pdf_has_every_f05_section_and_matches_the_web_json(lead, clock):
    app, client = lead
    job_id, v = publish(client, clock, "2454")
    rv = v["report_version_id"]
    data = client.get(f"/api/ui/reports/{rv}/download")
    assert data.status_code == 200 and "attachment" in data.headers["Content-Disposition"]
    pdf = data.data
    assert len(pdf) <= MAX_PDF_BYTES
    doc, text = pdf_text(pdf)
    assert doc.page_count <= MAX_PDF_PAGES
    report = client.get(f"/api/ui/reports/{rv}").get_json()["report"]
    stored = app.extensions["report_store"].get(rv)["report"]
    # F05 sections
    for heading in ("研究問題", "資料截止", "主張", "季度資料", "DCF 假設與敏感度", "同業比較", "資料品質", "來源",
                    "方法與限制", "報告版本", "MOCK 測試報告"):
        assert heading in text, heading
    # same approved JSON → same numbers on the page and in the PDF
    assert v["report_hash"] in text and rv in text
    for q in report["tables"]["quarters"]:
        assert q["period"] in text and f"{q['revenue']:,.2f}" in text
    assert f"{stored['data']['valuation']['dcf_per_share']:,.2f}" in text
    for row in report["tables"]["peer_comparison"]["rows"]:
        assert row["ticker"] in text
    assert "產業參照（不入平均）" in text
    for c in stored["claims"]:
        assert c["text"][:12] in text
    assert stored["disclaimer"] in text
    links = [lk.get("uri") for page in doc for lk in page.get_links() if lk.get("uri")]
    assert any(s["source_url"] in links for s in report["tables"]["sources"] if s.get("resolved"))
    assert len(doc[1].get_images()) + len(doc[2].get_images()) >= 1  # existing chart types embedded
    assert report["history"][0]["report_version_id"] == rv and report["run_label"] == "MOCK"


def test_2317_negative_fcf_is_undeterminable_in_pdf_without_negative_dcf(lead, clock):
    _, client = lead
    _, v = publish(client, clock, "2317")
    _, text = pdf_text(client.get(f"/api/ui/reports/{v['report_version_id']}/download").data)
    assert "無法判定：TTM FCF ≤ 0，5 年持平情境不適用" in text and "-64.43" not in text
    assert "同業比較只適用 2454" in text


def test_published_list_has_real_versions_with_pdf_links_and_keeps_fixture_labelled(lead, clock):
    app, client = lead
    _, v = publish(client, clock, "2330")
    rows = app.test_client().get("/api/ui/published").get_json()["reports"]
    real = [r for r in rows if not r["synthetic_fixture"]]
    assert [r["report_version_id"] for r in real] == [v["report_version_id"]]
    assert real[0]["run_label"] == "MOCK" and real[0]["pdf_url"].endswith(".pdf") and real[0]["download_url"]
    assert any(r["synthetic_fixture"] for r in rows)


def test_new_version_of_same_job_keeps_history_and_old_pdf(lead, clock):
    app, client = lead
    job_id, v1 = publish(client, clock, "2454", key="hist")
    store = app.extensions["report_store"]
    job = app.extensions["research_ui_mock"].store.get_job(job_id)
    job["draft"] = dict(job["draft"], limitations=["新增限制：示範第二版"])
    v2 = store.create_version(job, [])
    store.approve(v2["report_version_id"], v2["report_hash"], approver="lead")
    store.publish(v2["report_version_id"])
    hist = client.get(f"/api/ui/reports/{v2['report_version_id']}").get_json()["report"]["history"]
    assert [h["version_no"] for h in hist] == [2, 1]
    old = client.get(f"/api/ui/reports/{v1['report_version_id']}/download")
    assert old.status_code == 200 and "新增限制" not in pdf_text(old.data)[1]


def test_evidence_drawer_opens_sources_of_real_published_reports(lead, clock):
    _, client = lead
    _, v = publish(client, clock, "2454", key="ev")
    report = client.get(f"/api/ui/reports/{v['report_version_id']}").get_json()["report"]
    refs = [e["id"] for e in report["claims"][0]["evidence"]]
    assert refs == ["snap-2454-2026Q2", "ev-2454-2026q2-01"]  # tool result + the announcement that also states 15.28
    get = lambda ref: client.get(f"/api/ui/evidence/{ref}?report={v['report_version_id']}").get_json()["evidence"]  # noqa: E731
    snap, ev = get(refs[0]), get(refs[1])
    assert snap["kind"] == "financial_snapshot" and "15.28" in snap["paragraph"] and snap["cutoff_check"] == "cutoff 前可得"
    assert ev["hash_match"] and ev["cutoff_check"] == "cutoff 前可得" and ev["synthetic_fixture"] is False


def test_pdf_over_page_limit_is_refused(monkeypatch):
    from research_ui import report_pdf

    report = {"ticker": "2330", "cutoff_at": CUTOFF, "source_snapshot_id": "s", "question_version": "q",
              "claims": [{"claim_id": f"c{i}", "kind": "fact", "text": "很長的主張" * 40, "evidence_refs": []}
                         for i in range(200)], "data": {}, "disclaimer": "d", "run_label": "MOCK"}
    version = {"report_version_id": "rv-x", "version_no": 1, "report_hash": "h"}
    with pytest.raises(PublicationError, match="頁"):
        report_pdf.render_report_pdf(report, version)


class FakeBucket:
    def __init__(self):
        self.files = {}

    def list(self, folder, opts):
        return [{"name": k.rpartition("/")[2]} for k in self.files if k.rpartition("/")[0] == folder
                and opts["search"] in k]

    def upload(self, key, data, opts):
        assert opts["upsert"] == "false"
        self.files[key] = bytes(data)

    def download(self, key):
        return self.files[key]


class FakeClient:
    def __init__(self):
        self.bucket = FakeBucket()
        self.storage = self

    def from_(self, name):
        assert name == "reports"
        return self.bucket


def test_supabase_storage_is_write_once_and_env_switched(monkeypatch, tmp_path):
    s = SupabaseStorage(FakeClient(), "reports")
    s.put("reports/2330/rv-1.pdf", b"%PDF-1")
    assert s.exists("reports/2330/rv-1.pdf") and s.get("reports/2330/rv-1.pdf") == b"%PDF-1"
    with pytest.raises(PublicationError):
        s.put("reports/2330/rv-1.pdf", b"other")
    for k in ("SUPABASE_URL", "SUPABASE_SERVICE_KEY", "REPORT_STORAGE_BUCKET"):
        monkeypatch.delenv(k, raising=False)
    assert type(storage_from_env(tmp_path)).__name__ == "LocalStorage"


def test_public_reads_make_no_llm_calls(lead, clock, monkeypatch):
    app, client = lead
    _, v = publish(client, clock, "2330", key="nollm")
    import agents.provider as provider  # noqa: F401  (any model call would go through here)

    calls = []
    monkeypatch.setattr("google.genai.Client", lambda *a, **k: calls.append(1), raising=False)
    visitor = app.test_client()
    visitor.get("/api/ui/published")
    visitor.get(f"/api/ui/reports/{v['report_version_id']}")
    visitor.get(f"/api/ui/reports/{v['report_version_id']}/download")
    assert calls == []


@pytest.mark.parametrize("ticker", ["2330", "2317", "2454"])
def test_every_fact_number_is_in_what_the_claim_cites(lead, clock, ticker):
    """B's W07 audit (10/26): a fact's numbers must appear in its cited source — the announcement fragment
    or the financial-snapshot tool result (snapshot_id) — never only in an uncited tool output."""
    import re

    _, client = lead
    _, v = publish(client, clock, ticker, key=f"cite-{ticker}")
    rv = v["report_version_id"]
    report = client.get(f"/api/ui/reports/{rv}").get_json()["report"]
    for claim in report["claims"]:
        if claim["kind"] != "fact":
            continue
        assert claim["evidence"] and all(e["exists"] for e in claim["evidence"]), claim
        text = "".join(client.get(f"/api/ui/evidence/{e['id']}?report={rv}").get_json()["evidence"]["paragraph"]
                       for e in claim["evidence"])
        for number in re.findall(r"\d[\d,]*\.?\d*", claim["text"]):
            assert number.rstrip(".") in text, f"{ticker} {claim['claim_id']}: {number} not in cited source"
    if ticker == "2317":  # the Jan–Jun cumulative announcement (EPS 7.84) must not back the single-quarter 4.27
        c1 = next(c for c in report["claims"] if c["claim_id"] == "c1")
        assert [e["id"] for e in c1["evidence"]] == ["snap-2317-2026Q2"]


def test_pdf_prints_the_close_used_for_the_gap(lead, clock):
    _, client = lead
    _, v = publish(client, clock, "2330", key="price")
    _, text = pdf_text(client.get(f"/api/ui/reports/{v['report_version_id']}/download").data)
    assert "基準收盤價：2026-09-30 收盤 2,480.00 元" in text and "財報快照（工具結果）" in text


def test_peer_snapshot_version_is_named_apart_from_the_main_snapshot(lead, clock):
    """B (10/31): v1.8-w06 is data/v12-peer-snapshot.json, not the main snapshot fin-snap:v1.6-…"""
    app, client = lead
    _, v = publish(client, clock, "2454", key="peer-ver")
    rep = app.extensions["report_store"].get(v["report_version_id"])["report"]
    peer = rep["data"]["peer_comparison"]
    assert "snapshot_version" not in peer and peer["peer_snapshot_version"] == "v1.8-w06"
    assert peer["peer_snapshot_file"] == "data/v12-peer-snapshot.json"
    _, text = pdf_text(client.get(f"/api/ui/reports/{v['report_version_id']}/download").data)
    assert "同業快照 v1.8-w06" in text and rep["source_snapshot_id"] in text


# ----- W08-A: read path without repeated database / Storage round trips ------------------------------------
def test_pdf_preview_and_download_come_from_the_published_list_and_support_etag(lead, clock, monkeypatch):
    import research_ui

    app, client = lead
    _, v = publish(client, clock, "2454", key="w08-etag")
    rv = v["report_version_id"]
    store = app.extensions["report_store"]
    research_ui._pdf_cache.clear()
    first = client.get(f"/api/ui/reports/{rv}.pdf")
    assert first.status_code == 200 and first.headers["Content-Disposition"].startswith("inline")
    assert first.headers["ETag"] == f'"{v["pdf_hash"]}"'
    # no more database reads by id, and no Storage read either: both are served from memory now
    monkeypatch.setattr(store, "get", lambda *_: (_ for _ in ()).throw(AssertionError("db read")))
    monkeypatch.setattr(store.storage, "get", lambda *_: (_ for _ in ()).throw(AssertionError("storage read")))
    again = client.get(f"/api/ui/reports/{rv}/download")
    assert again.status_code == 200 and again.data == first.data and "attachment" in again.headers["Content-Disposition"]
    assert client.get(f"/api/ui/reports/{rv}/download", headers={"If-None-Match": first.headers["ETag"]}).status_code == 304
    assert client.get(f"/api/ui/reports/{rv}").status_code == 200  # report detail also without a db read


def test_pdf_cache_is_bounded_and_rejects_tampered_bytes(lead, clock):
    import research_ui

    app, client = lead
    _, v = publish(client, clock, "2330", key="w08-tamper")
    rv = v["report_version_id"]
    research_ui._pdf_cache.clear()
    store = app.extensions["report_store"]
    path = store.storage._path(app.extensions["report_store"].get(rv)["storage_key"])
    path.chmod(0o644)
    path.write_bytes(b"%PDF-tampered")
    r = client.get(f"/api/ui/reports/{rv}/download")
    assert r.status_code == 404 and r.get_json()["error"] == "pdf_unavailable"
    assert rv not in research_ui._pdf_cache  # a failed hash check is never cached


def test_pdf_cache_keeps_at_most_eight_files(monkeypatch):
    import hashlib
    from types import SimpleNamespace

    import research_ui

    blob = b"%PDF-" + b"x" * 1000
    fake = SimpleNamespace(storage=SimpleNamespace(get=lambda key: blob))
    monkeypatch.setattr(research_ui, "_reports", lambda: fake)
    research_ui._pdf_cache.clear()
    for i in range(research_ui.PDF_CACHE_MAX_FILES + 3):
        research_ui._published_pdf({"report_version_id": f"rv-{i}", "storage_key": f"k{i}",
                                    "pdf_hash": hashlib.sha256(blob).hexdigest()})
    assert list(research_ui._pdf_cache) == [f"rv-{i}" for i in range(3, research_ui.PDF_CACHE_MAX_FILES + 3)]
    research_ui._pdf_cache.clear()


def test_unpublished_versions_have_no_pdf_route(lead, clock):
    app, client = lead
    job_id = create(client, ticker="2317", cutoff_at=CUTOFF, scenario="revise_then_pass",
                    idempotency_key="w08-draft").get_json()["job"]["job_id"]
    run_until_done(client, clock, job_id)
    v = client.post(f"/api/ui/jobs/{job_id}/report").get_json()["version"]
    visitor = app.test_client()
    assert visitor.get(f"/api/ui/reports/{v['report_version_id']}.pdf").status_code == 404


def test_pdf_render_releases_memory_even_when_refused(monkeypatch):
    """W08-A: without this, each render left ~70–230 MB behind (467 → 538 MB after two), over Render's 512 MB."""
    from research_ui import report_pdf

    calls = []
    monkeypatch.setattr(report_pdf, "release_memory", lambda: calls.append(1))
    report = {"ticker": "2330", "cutoff_at": CUTOFF, "source_snapshot_id": "s", "question_version": "q",
              "claims": [{"claim_id": f"c{i}", "kind": "fact", "text": "很長的主張" * 40, "evidence_refs": []}
                         for i in range(200)], "data": {}, "disclaimer": "d", "run_label": "MOCK"}
    with pytest.raises(PublicationError):
        report_pdf.render_report_pdf(report, {"report_version_id": "rv-x", "version_no": 1, "report_hash": "h"})
    report["claims"] = report["claims"][:2]
    assert report_pdf.render_report_pdf(report, {"report_version_id": "rv-x", "version_no": 1, "report_hash": "h"})
    assert calls == [1, 1]
