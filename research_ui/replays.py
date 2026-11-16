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
# Which Agent version and which run conditions each recorded file belongs to (handoff/agent-version-changes.md).
# Shown on every replay so a viewer never reads runs of different versions or conditions as one set of results
# (AGENTS.md: v1 and v2 results are not compared in one table). `group` is the dropdown section: from 11/14 the
# question is sent as the case `task` instead of the variant name (decision 31), so those runs form their own
# group and are not listed with the earlier `variant` runs (lead, 11/14). Newest group first.
DEV = "開發期（v1 之前）"
V2 = "Agent v2"
V2_TASK = "Agent v2・題目送 task"
V2_VARIANT = "Agent v2・題目送 variant"
TRACE_FILES: dict[str, dict[str, Any]] = {
    "agent/calib-v2-rules-check-1115-dual.json": {
        "agent_version": V2, "group": V2_TASK, "frozen_cases": True,
        "condition": "補股價後・題目送 task・11/14 覆核規則修正後（第 35、37、38 節）"},
    "agent/calib-v2-task-rehearsal-1114-dual.json": {
        "agent_version": V2, "group": V2_TASK, "frozen_cases": True,
        "condition": "補股價後・題目送 task・11/14 覆核規則修正前（第 35、37、38 節）"},
    "agent/calib-v2-dual-postprice-1112.json": {
        "agent_version": V2, "group": V2_VARIANT, "frozen_cases": True,
        "condition": "補股價後・題目送 variant・覆核規則修正前（第 28 節）"},
    "agent/calib-v2-dual-rerun-1112.json": {
        "agent_version": V2, "group": V2_VARIANT, "frozen_cases": True, "condition": "補股價後・題目送 variant"},
    "agent/calib-v2-dual-day3.json": {
        "agent_version": V2, "group": V2_VARIANT, "frozen_cases": True, "condition": "補股價前・題目送 variant"},
    "agent/calib-v2-dual-day2.json": {
        "agent_version": V2, "group": V2_VARIANT, "frozen_cases": True, "condition": "補股價前・題目送 variant"},
    "agent/calib-v2-dual-day1.json": {
        "agent_version": V2, "group": V2_VARIANT, "frozen_cases": True, "condition": "補股價前・題目送 variant"},
    "agent/dev-v14-batch1.json": {"agent_version": DEV, "group": DEV, "condition": "開發集早期試跑"},
    "agent/researcher-v12-traces.json": {"agent_version": DEV, "group": DEV, "condition": "開發集早期試跑"},
    "agent/researcher-v12-traces-gemini-3.6-flash.json": {
        "agent_version": DEV, "group": DEV, "condition": "開發集早期試跑（另一模型）"},
}

# The recorded runs the demo script uses for its three paths (E01 shown as REPLAY, decision 34). All three come
# from the same condition group, so the demo never mixes `task` and `variant` runs.
DEMO_PATHS = {
    "calib-v2-rules-check-1115-dual:CASE-04": "示範：正常通過",
    "calib-v2-task-rehearsal-1114-dual:CASE-19": "示範：覆核要求補查後修正通過",
    "calib-v2-rules-check-1115-dual:CASE-15": "示範：資料不足停止",
}

# Recorded runs whose result is known to come from a since-fixed program rule. Kept as recorded, with this note.
RECORD_NOTES = {
    "calib-v2-task-rehearsal-1114-dual:CASE-04": {
        "label": "覆核程式誤判，規則已修",
        "note": "這次停在證據不足，是覆核規則誤擋：收盤價、TTM EPS、本益比都與快照一致，只因 TTM EPS 的期間寫成"
                "結尾季（2026Q2）就被列為 critical，模型兩輪覆核都判通過。11/14 已修正規則；11/15 以修正後規則重跑同題通過"
                "（calib-v2-rules-check-1115-dual:CASE-04）。紀錄照實保留。依據：handoff/decisions-2026-10.md 第 35 節。",
    },
    "calib-v2-dual-postprice-1112:CASE-04": {
        "label": "覆核程式誤判，規則已修",
        "note": "這次停在證據不足，是覆核程式把「TTM 要四個連續單季」套到本益比造成的誤判，不是模型錯誤；"
                "11/13 起規則已修正。紀錄照實保留。依據：handoff/decisions-2026-10.md 第 28 節。",
    },
}

# Recorded runs whose case id was later retired. Shown with this note so a viewer does not read them as the
# sealed holdout case of the same number (lead, handoff/decisions-2026-10.md §15, 11/07; B's source audit).
SUPERSEDED = {
    "researcher-v12-traces:CASE-13": {
        "label": "舊開發草稿，已廢除",
        "note": "這是 10/15 以前的舊開發草稿題目（2317 缺 CapEx），已廢除，與保留集 CASE-13 無關；保留集未被污染。"
                "依據：handoff/decisions-2026-10.md 第 15 節、evaluation/source-audit-final.md 第一節第 3 點。",
    },
}


DEV_CASES = "evaluation/dev-cases.json"


def _dev_cases() -> dict[str, dict[str, Any]]:
    """cutoff_at / source_snapshot_id of the frozen development cases (not the sealed holdout)."""
    try:
        doc = json.loads((ROOT / DEV_CASES).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {c["case_id"]: c for c in doc.get("cases", []) if c.get("split", "dev") == "dev"}


def _load() -> list[dict[str, Any]]:
    runs = []
    dev = _dev_cases()
    for rel, meta in TRACE_FILES.items():
        path = ROOT / rel
        if not path.exists():
            continue
        doc = json.loads(path.read_text(encoding="utf-8"))
        for case in doc.get("cases", []):
            live = case.get("live")
            if not live:
                continue
            replay_id = f"{path.stem}:{case['case_id']}"
            runs.append({
                "replay_id": replay_id,
                "superseded": SUPERSEDED.get(replay_id),
                "record_note": RECORD_NOTES.get(replay_id),
                "agent_version": meta["agent_version"],
                "group": meta["group"],
                "demo_path": DEMO_PATHS.get(replay_id),
                # Runs after the 10/25 case freeze used exactly these frozen cases; earlier drafts may differ.
                "cutoff_at": dev.get(case["case_id"], {}).get("cutoff_at") if meta.get("frozen_cases") else None,
                "source_snapshot_id": (dev.get(case["case_id"], {}).get("source_snapshot_id")
                                       if meta.get("frozen_cases") else None),
                "condition": meta["condition"],
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
                               "category", "title", "superseded", "record_note", "agent_version", "group", "demo_path", "condition",
                               "prompt_versions",
                               "cutoff_at")}
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
        "source": {k: found[k] for k in ("file", "generated_at", "commit", "model_id", "prompt_versions",
                                         "agent_version", "group", "condition")},
        "case": {k: found[k] for k in ("case_id", "ticker", "category", "title", "expected_behavior", "superseded",
                                       "record_note", "demo_path")},
        "job": {"status": run.get("status"), "stage": "finished", "stop_reason": run.get("stop_reason"),
                "ticker": found["ticker"], "mode": "dual", "model_id": found["model_id"],
                "cutoff_at": found["cutoff_at"], "source_snapshot_id": found["source_snapshot_id"],
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
