"""W04-L step 3: run development cases through the Researcher/Reviewer graph, live and mock,
and write agent/researcher-v12-traces.json.

    .venv/bin/python scripts/dev_traces.py               # mock only (no API)
    .venv/bin/python scripts/dev_traces.py --live        # mock + live (≤ 8 sends per case)

Live uses GEMINI_MODEL / GEMINI_API_KEY from .env and the verified quota in
handoff/quota-baseline.json; jobs are stored in tmp/dev_runs.sqlite3 (never Supabase).
Mock runs use scripted model replies (labelled MOCK) with the same real tools/snapshots.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from agents.budget import ProjectQuota  # noqa: E402
from agents.contract import validate_job_request  # noqa: E402
from agents.research_graph import RESEARCHER_PROMPT_VERSION, make_research_handler  # noqa: E402
from agents.review_contract import REVIEWER_PROMPT_VERSION  # noqa: E402
from agents.store import JobStore  # noqa: E402
from agents.worker import run_once  # noqa: E402
from test_provider_mock import FakeClient, fc_response, text_response  # noqa: E402

CASES = ["CASE-01", "CASE-04", "CASE-13"]
OUT = ROOT / "agent" / "researcher-v12-traces.json"


def load_cases() -> dict[str, dict]:
    data = json.loads((ROOT / "evaluation" / "dev-cases.json").read_text(encoding="utf-8"))
    return {c["case_id"]: c for c in data["cases"]}


def mock_script(case: dict) -> list:
    """Scripted MOCK replies: a plausible path per case, used only to compare with live."""
    cut, t = case["cutoff_at"], case["ticker"]
    draft = lambda claims, status="draft": json.dumps({"status": status, "decision_summary": "MOCK", "claims": claims,  # noqa: E731
                                                        "conflicts": [], "limitations": []}, ensure_ascii=False)
    passed = json.dumps({"decision": "pass", "issues": [], "checked_refs": [], "checked_metric_ids": [],
                         "decision_summary": "MOCK"}, ensure_ascii=False)
    if case["case_id"] == "CASE-01":
        claims = [{"claim_id": "c1", "kind": "fact", "text": "2026Q2 合併營收約 6,735 億元（新台幣）",
                   "evidence_refs": ["ev-dev-01-official"], "facts": [{"metric": "revenue", "value": 6735, "currency": "TWD",
                   "period": "2026Q2", "period_basis": "single_quarter", "source_ref": "ev-dev-01-official"}], "limitations": []}]
        return [fc_response("search_evidence", {"ticker": t, "query": "營收", "cutoff": cut, "limit": 3}),
                fc_response("read_evidence", {"evidence_version_id": "ev-dev-01-official"}),
                text_response(draft(claims)), text_response(passed)]
    if case["case_id"] == "CASE-04":
        return [fc_response("get_price_window", {"ticker": t, "end_at": cut, "sessions": 1}),
                fc_response("get_financial_snapshot", {"ticker": t, "cutoff": cut}),
                fc_response("calculate_metrics", {"operation": "pe_ttm", "values": {"price": 1005.0, "eps_ttm": 38.2},
                                                  "evidence_refs": ["obs-1", "obs-2"]}),
                text_response(draft([{"claim_id": "c1", "kind": "fact", "text": "以同日收盤價與 TTM EPS 計算 P/E",
                                      "evidence_refs": ["obs-3"], "limitations": []}])), text_response(passed)]
    return [fc_response("get_financial_snapshot", {"ticker": t, "cutoff": cut}),
            text_response(draft([{"claim_id": "c1", "kind": "unknown", "text": "CapEx 缺失，FCF 無法計算",
                                  "evidence_refs": [], "limitations": ["CapEx null"]}], status="insufficient"))]


def run(store: JobStore, case: dict, client, model_id: str, quota: ProjectQuota, tag: str) -> dict:
    req = validate_job_request({"ticker": case["ticker"], "mode": "dual", "cutoff_at": case["cutoff_at"],
                                "source_snapshot_id": case["source_snapshot_id"], "focus": case["title"],
                                "idempotency_key": f"{case['case_id']}-{tag}"})
    job, _ = store.create_job(req, model_id)
    handler = make_research_handler(client, model_id, quota)
    final = run_once(store, f"dev-{tag}", handler)
    for _ in range(3):  # RPM/TPM pause → wait until resume_after, then the same job continues
        if not final or final["status"] != "paused_quota" or not final.get("resume_after"):
            break
        wait = max(0.0, final["resume_after"] - time.time()) + 1
        print(f"  {case['case_id']} paused ({final['stop_reason']}), resuming in {wait:.0f}s", flush=True)
        time.sleep(wait)
        final = run_once(store, f"dev-{tag}", handler)
    if final and final["job_id"] != job["job_id"]:
        raise RuntimeError(f"worker ran another job {final['job_id']} instead of {job['job_id']}")
    events = store.list_events(job["job_id"])
    return {
        "job_id": job["job_id"],
        "status": final["status"] if final else None,
        "stop_reason": final.get("stop_reason") if final else None,
        "path": [f"{e['role']}:{e['tool_name']}→{e['detail'].get('status')}" for e in events if e["event_type"] == "tool_call"],
        "steps": [{"seq": e["event_seq"], "role": e["role"], "event": e["event_type"], "tool": e["tool_name"],
                   **{k: e["detail"].get(k) for k in ("call_number", "prompt_version", "input_estimate",
                                                       "estimate_under_actual", "status", "reason", "final_decision",
                                                       "model_decision", "rules_decision", "critical") if k in e["detail"]},
                   **({"prompt_tokens": e["detail"]["usage"].get("prompt_token_count"),
                       "total_tokens": e["detail"]["usage"].get("total_token_count")} if "usage" in e["detail"] else {})}
                  for e in events if e["event_type"] not in ("job_created", "lease_acquired")],
        "draft": (final or {}).get("draft"),
        "review": (final or {}).get("review"),
        "budget": {k: (final or {}).get(k) for k in ("calls_used", "tool_calls_used", "tokens_observed",
                                                     "supplement_rounds", "active_seconds")},
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--cases", default=",".join(CASES))
    ap.add_argument("--model", help="compare another model listed in quota-baseline.json gemini_alternatives_checked")
    args = ap.parse_args()
    cases = load_cases()
    chosen = [cases[c] for c in args.cases.split(",")]
    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip()
    out = {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "commit": commit,
           "prompt_versions": {"researcher": RESEARCHER_PROMPT_VERSION, "reviewer": REVIEWER_PROMPT_VERSION},
           "note": "mock = scripted model replies (MOCK) on real tools/snapshots; live = gemini chose every step.",
           "cases": []}

    mock_quota = ProjectQuota(model_id="mock-model", rpm=10**4, tpm=10**8, rpd=10**6)
    with tempfile.TemporaryDirectory() as tmp:
        mock_store = JobStore(Path(tmp) / "mock.sqlite3")
        mocks = {c["case_id"]: run(mock_store, c, FakeClient(mock_script(c)), "mock-model", mock_quota, "mock") for c in chosen}
        mock_store.close()

    live = {}
    if args.live:
        from agents.provider import make_client
        baseline = json.loads((ROOT / "handoff" / "quota-baseline.json").read_text(encoding="utf-8"))
        quota = ProjectQuota.from_baseline(baseline)
        model_id = os.getenv("GEMINI_MODEL")
        if args.model:  # comparison run: only with that model's own recorded quota, never a guessed one
            alt = next((a for a in baseline.get("gemini_alternatives_checked", []) if a["model_id"] == args.model), None)
            if alt is None:
                sys.exit(f"{args.model} 沒有記錄在 quota-baseline.json，停止。")
            quota = ProjectQuota(model_id=alt["model_id"], rpm=alt["rpm"], tpm=alt["tpm"], rpd=alt["rpd"])
            model_id = args.model
        if model_id != quota.model_id:
            sys.exit(f"GEMINI_MODEL={model_id} 與 quota-baseline.json 的 {quota.model_id} 不一致，停止。")
        stamp = datetime.now().strftime("%Y%m%d%H%M")
        store = JobStore(ROOT / "tmp" / f"dev_runs-{stamp}.sqlite3")  # fresh DB: no older paused job is resumed here
        client = make_client()
        for i, c in enumerate(chosen):
            if i:
                time.sleep(60)  # stay under 80 % of RPM between cases
            live[c["case_id"]] = run(store, c, client, model_id, quota, f"live-{stamp}")
            print(c["case_id"], live[c["case_id"]]["status"], live[c["case_id"]]["path"], flush=True)
        out["model_id"] = model_id

    for c in chosen:
        entry = {"case_id": c["case_id"], "ticker": c["ticker"], "category": c["category"], "title": c["title"],
                 "expected_behavior": c["expected_behavior"], "mock": mocks[c["case_id"]]}
        if c["case_id"] in live:
            entry["live"] = live[c["case_id"]]
        out["cases"].append(entry)
    out_path = OUT if not args.model else OUT.with_name(f"researcher-v12-traces-{args.model}.json")
    OUT.parent.mkdir(exist_ok=True)
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("wrote", out_path.relative_to(ROOT))


if __name__ == "__main__":
    main()
