"""REPLAY of recorded live research runs (W05-A).

Reads the lead's recorded traces in agent/*.json (Gemini actually chose every
step in the `live` runs). Read-only, 0 LLM. Only `live` runs are listed: the
`mock` runs in those files are scripted model replies for the lead's own tests.

The trace files keep the final draft and final review of each run plus the
decision of every review round; earlier draft versions and the issues of
earlier rounds are not recorded there, which the panel states plainly.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .review_view import ISSUE_FIELDS, review_view

ROOT = Path(__file__).resolve().parent.parent
TRACE_FILES = ("agent/dev-v14-batch1.json", "agent/researcher-v12-traces.json",
               "agent/researcher-v12-traces-gemini-3.6-flash.json")


def _load() -> list[dict[str, Any]]:
    runs = []
    for rel in TRACE_FILES:
        path = ROOT / rel
        if not path.exists():
            continue
        doc = json.loads(path.read_text(encoding="utf-8"))
        for case in doc.get("cases", []):
            live = case.get("live")
            if not live:
                continue
            runs.append({
                "replay_id": f"{path.stem}:{case['case_id']}",
                "file": rel,
                "generated_at": doc.get("generated_at"),
                "commit": doc.get("commit"),
                "model_id": doc.get("model_id"),
                "prompt_versions": doc.get("prompt_versions"),
                "case_id": case["case_id"],
                "ticker": case.get("ticker"),
                "category": case.get("category"),
                "title": case.get("title"),
                "expected_behavior": case.get("expected_behavior"),
                "run": live,
            })
    return runs


def list_replays() -> list[dict[str, Any]]:
    return [{k: r[k] for k in ("replay_id", "file", "generated_at", "commit", "model_id", "case_id", "ticker",
                               "category", "title")}
            | {"status": r["run"].get("status"), "stop_reason": r["run"].get("stop_reason"),
               "review_rounds": sum(1 for s in r["run"].get("steps", []) if s.get("event") == "review")}
            for r in _load()]


def _events(run: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for s in run.get("steps", []):
        detail: dict[str, Any] = {}
        if s.get("event") == "tool_call":
            detail = {"tool_status": s.get("status"), "summary": s.get("reason") or s.get("status")}
        elif s.get("event") == "model_call":
            detail = {"summary": f"第 {s.get('call_number')} 次模型請求・{s.get('prompt_version')}"
                                 + (f"・{s.get('total_tokens')} tokens" if s.get("total_tokens") else "")}
        elif s.get("event") == "review":
            detail = {"summary": f"模型 {s.get('model_decision')}・規則 {s.get('rules_decision')}・最終 {s.get('final_decision')}"
                                 + (f"・critical {', '.join(dict.fromkeys(s.get('critical') or []))}" if s.get("critical") else "")}
        elif s.get("event") == "rules_check":
            detail = {"summary": f"規則檢查 {s.get('rules_decision')}"}
        elif s.get("event") == "draft":
            detail = {"summary": f"草稿狀態 {s.get('status')}"}
        else:
            detail = {"summary": s.get("status") or s.get("reason") or ""}
        out.append({"event_seq": s.get("seq"), "created_at": None, "role": s.get("role"),
                    "event_type": s.get("event"), "tool_name": s.get("tool"), "detail": detail})
    return out


def get_replay(replay_id: str) -> dict[str, Any] | None:
    found = next((r for r in _load() if r["replay_id"] == replay_id), None)
    if found is None:
        return None
    run = found["run"]
    review_steps = [s for s in run.get("steps", []) if s.get("event") == "review"]
    final_review = run.get("review") or {}
    # Rebuild review rounds: decisions for every round; issues only for the last (that is all the file keeps).
    reviews = []
    for i, s in enumerate(review_steps, start=1):
        last = i == len(review_steps)
        reviews.append({"round": i,
                        "model": {"decision": s.get("model_decision"), "issues": final_review.get("issues", []) if last else []},
                        "rules": {"decision": s.get("rules_decision"), "issues": []},
                        "final": ({**final_review, "decision": s.get("final_decision")} if last
                                  else {"decision": s.get("final_decision"), "issues": [
                                      {"claim_id": c, "severity": "critical", "reason": "（此輪細節未保存在紀錄檔）",
                                       "required_evidence": ""} for c in dict.fromkeys(s.get("critical") or [])]})})
    budget = run.get("budget") or {}
    job_like = {"mode": "dual", "status": run.get("status"), "stop_reason": run.get("stop_reason"),
                "draft": run.get("draft"), "checkpoint": {"reviews": reviews},
                "supplement_rounds": budget.get("supplement_rounds", 0), "publication_status": "draft"}
    view = review_view(job_like)
    for rnd in view["rounds"]:
        for issue in rnd["issues"]:
            issue["source"] = "recorded"
    return {
        "replay_id": found["replay_id"],
        "label": "REPLAY",
        "source": {k: found[k] for k in ("file", "generated_at", "commit", "model_id", "prompt_versions")},
        "case": {k: found[k] for k in ("case_id", "ticker", "category", "title", "expected_behavior")},
        "job": {"status": run.get("status"), "stage": "finished", "stop_reason": run.get("stop_reason"),
                "ticker": found["ticker"], "mode": "dual", "model_id": found["model_id"],
                "prompt_version": (found.get("prompt_versions") or {}).get("researcher"),
                "calls_used": budget.get("calls_used"), "tool_calls_used": budget.get("tool_calls_used"),
                "supplement_rounds": budget.get("supplement_rounds"), "active_seconds": budget.get("active_seconds"),
                "tokens_observed": budget.get("tokens_observed"), "job_id": run.get("job_id")},
        "path": run.get("path") or [],
        "events": _events(run),
        "review_view": view,
        "limits_of_record": "紀錄檔只保存最後一版草稿與最後一輪覆核的完整問題；較早輪次只有決定與 critical 主張編號。",
    }


__all__ = ["ISSUE_FIELDS", "get_replay", "list_replays"]
