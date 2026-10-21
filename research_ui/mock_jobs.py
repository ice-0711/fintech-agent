"""MOCK research jobs for A's UI work (W02-A/W03-A).

Authorisation is still "MOCK only" (decided 2026-10-05): the page never holds
RESEARCH_API_TOKEN and never reaches the real Gemini worker. To still read job
state *from a database* (W03 驗收「狀態從DB取得」) the mock uses 組長's
`agents.store.JobStore` on its own SQLite file, and `agents.contract` for the
same request validation (2379/3034 rejected, cutoff required, idempotent key).

There is no background thread. Each GET calls `pump()`, which applies the
scripted steps whose time has come, through the normal lease/fencing API.
Every event carries `"mock": true`; no model is called anywhere here.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any

from agents.contract import ContractError, validate_job_request
from agents.store import JobStore, StaleLeaseError
from agents import tools_impl

from .review_view import review_view

WORKER_ID = "ui-mock-worker"
STEP_SECONDS = float(os.getenv("RESEARCH_UI_MOCK_STEP_SECONDS", "1.5"))

# Public job fields shown in the UI (same list as agents/api.py, nothing else).
PUBLIC_JOB_FIELDS = (
    "job_id", "ticker", "mode", "status", "stage", "cutoff_at", "source_snapshot_id", "question_version",
    "model_id", "prompt_version", "calls_used", "tokens_observed", "tool_calls_used", "supplement_rounds",
    "active_seconds", "stop_reason", "checkpoint_version", "created_at", "updated_at", "publication_status",
)
# Event detail keys the UI may show. Anything else (raw prompts, args, model text) is dropped.
PUBLIC_DETAIL_KEYS = (
    "mock", "summary", "decision_summary", "evidence_refs", "latency_ms", "tool_status",
    "args_redacted", "output_hash", "claim_id", "severity", "required_evidence", "budget",
)

SCENARIOS = ("revise_then_pass", "succeeded", "insufficient_evidence", "paused_quota", "failed", "timed_out")
CANCELLABLE = ("running",)


def _snapshot_id(root: Path) -> str:
    path = root / "data" / "financial-snapshots.json"
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
        return f"fin-snap:{manifest.get('manifest_version', 'unknown')}"
    except (OSError, ValueError):
        return "fin-snap:unavailable"


def _tool(name: str, **args: Any) -> dict[str, Any]:
    return {"tool": name, "args": args}


def _steps(scenario: str, ticker: str) -> list[dict[str, Any]]:
    """Scripted MOCK steps. Model decisions are scripted (MOCK); tool steps run
    B's real deterministic tools (agents/tools_impl.py) on the fixed snapshot,
    so tool_status, evidence ids and output hashes in the trace are real."""

    plan = {"role": "researcher", "event_type": "plan", "detail": {
        "summary": "MOCK：模型決策為預錄腳本，工具結果為真實快照輸出",
        "decision_summary": "先確認 cutoff 前可得的最新季財報"},
        "changes": {"calls_used": 1, "active_seconds": 4.0}}
    fin = {"role": "researcher", "event_type": "tool_call", "call": _tool("get_financial_snapshot", ticker=ticker),
           "changes": {"stage": "tools", "tool_calls_used": 1, "active_seconds": 6.0}}

    if scenario == "insufficient_evidence":
        ev = f"ev-{ticker}-2026q2-01"
        return [plan, fin,
                {"role": "researcher", "event_type": "tool_call", "call": _tool("read_evidence", evidence_version_id=ev),
                 "changes": {"calls_used": 2, "tool_calls_used": 2, "active_seconds": 10.0}},
                {"role": "researcher", "event_type": "draft", "detail": {
                    "summary": "草稿狀態 insufficient：公告片段只有營收，現金流與 EPS 沒有原文可引用",
                    "decision_summary": "可引用的原文不足以支持估值主張，停止並列出缺口"},
                 "draft": {"status": "insufficient", "decision_summary": "可引用的原文不足以支持估值主張",
                           "claims": [{"claim_id": "c1", "kind": "fact", "text": "2026Q2 合併營收為 2 兆 5,259 億元。",
                                       "evidence_refs": [ev], "limitations": ["片段只有營收"]},
                                      {"claim_id": "c2", "kind": "unknown", "text": "缺 2026Q2 現金流量表原文，無法核實自由現金流與 DCF。",
                                       "evidence_refs": [], "limitations": []}],
                           "unknowns": ["現金流量表原文", "EPS 原文"], "limitations": ["不產生估值結論"]},
                 "changes": {"calls_used": 3, "active_seconds": 12.0}},
                {"role": "researcher", "event_type": "stop", "detail": {
                    "summary": "資料不足，停止並保留限制，不產生評級"},
                 "changes": {"status": "insufficient_evidence", "stage": "finished",
                             "stop_reason": "researcher_insufficient"}}]
    if scenario == "paused_quota":
        return [plan, fin,
                {"role": "system", "event_type": "quota_pause", "detail": {
                    "summary": "MOCK：每日請求額度用盡，保存檢查點；累計預算不歸零",
                    "budget": {"calls_used": 2, "limit": 8}},
                 "changes": {"status": "paused_quota", "calls_used": 2, "active_seconds": 8.0,
                             "stop_reason": "daily_quota_exhausted"}}]
    if scenario == "failed":
        return [plan, fin,
                {"role": "system", "event_type": "error", "detail": {
                    "summary": "MOCK：worker 例外，job 標為失敗並保留已完成的步驟"},
                 "changes": {"status": "failed", "stage": "finished", "active_seconds": 9.0,
                             "stop_reason": "worker_error: MOCK simulated exception"}}]
    if scenario == "timed_out":
        return [plan, fin,
                {"role": "system", "event_type": "timeout", "detail": {
                    "summary": "MOCK：主動執行時間達 180 秒上限，保存檢查點後停止，不冒充成功"},
                 "changes": {"status": "timed_out", "stage": "finished", "active_seconds": 180.0,
                             "stop_reason": "active_time_limit_180s"}}]
    if scenario == "revise_then_pass":
        return _revise_then_pass(ticker, plan, fin)
    # succeeded
    return [plan,
            {"role": "researcher", "event_type": "tool_call", "call": _tool("search_evidence", ticker=ticker, query="第二季", limit=3),
             "changes": {"stage": "tools", "tool_calls_used": 1, "active_seconds": 6.0}},
            {"role": "researcher", "event_type": "tool_call", "call": _tool("read_evidence", evidence_version_id=f"ev-{ticker}-2026q2-01"),
             "changes": {"tool_calls_used": 2, "active_seconds": 8.0}},
            {**fin, "changes": {"tool_calls_used": 3, "active_seconds": 10.0}},
            {"role": "researcher", "event_type": "draft", "detail": {
                "summary": "MOCK：提出草稿主張，每項附來源 ID", "evidence_refs": [f"ev-{ticker}-2026q2-01"]},
             "changes": {"stage": "review", "calls_used": 2, "active_seconds": 15.0}},
            {"role": "reviewer", "event_type": "tool_call", "call": _tool("read_evidence", evidence_version_id=f"ev-{ticker}-2026q2-01"),
             "changes": {"tool_calls_used": 4, "active_seconds": 17.0}},
            {"role": "reviewer", "event_type": "review", "detail": {
                "summary": "MOCK：覆核通過；發布仍需人工核准", "decision_summary": "引用片段與草稿數字一致"},
             "changes": {"calls_used": 3, "active_seconds": 21.0}},
            {"role": "system", "event_type": "finished", "detail": {"summary": "研究完成，等待人工核准（未發布）"},
             "changes": {"status": "succeeded", "stage": "finished", "stop_reason": "mock_completed"}}]


def _revise_then_pass(ticker: str, plan: dict[str, Any], fin: dict[str, Any]) -> list[dict[str, Any]]:
    """MOCK of the core demo: Reviewer rejects one claim, Researcher re-checks with a tool, then pass.

    Numbers come from B's snapshot (fact sheet V1.7); tests assert they equal the tool outputs.
    The deliberate error in draft v1 (single-quarter EPS presented as TTM) is a labelled test case.
    """

    fin_data = (tools_impl.get_financial_snapshot(ticker, "2026-09-30T17:30:00+08:00").get("data") or {})
    m = fin_data.get("metrics") or {}
    ev = f"ev-{ticker}-2026q2-01"
    single_eps, ttm_eps, periods = m.get("eps_single_q"), m.get("eps_ttm"), fin_data.get("ttm_periods") or []
    span = f"{periods[0]}–{periods[-1]}" if periods else "近四季"
    c1 = {"claim_id": "c1", "kind": "fact", "evidence_refs": [ev], "limitations": [],
          "text": f"{fin_data.get('latest_period')} 單季每股盈餘 {single_eps} 元。"}
    v1 = {"status": "draft", "decision_summary": "讀取最新季財報與公告片段後撰稿",
          "claims": [c1,
                     {"claim_id": "c2", "kind": "fact", "evidence_refs": [ev], "limitations": [],
                      "text": f"TTM EPS 為 {single_eps} 元。（測試案例：故意把單季 EPS 當成 TTM）"},
                     {"claim_id": "c3", "kind": "unknown", "evidence_refs": [], "limitations": [],
                      "text": "快照沒有 2026Q3 營收，無法判斷第三季動能。"}],
          "unknowns": ["2026Q3 營收"], "limitations": []}
    v2 = {"status": "draft", "decision_summary": "依覆核意見改用連續四季 EPS",
          "claims": [c1,
                     {"claim_id": "c2", "kind": "fact", "evidence_refs": [ev], "limitations": [f"TTM 期間 {span}"],
                      "text": f"近四季 EPS 合計（TTM）為 {ttm_eps} 元（{span}）。"},
                     v1["claims"][2]],
          "unknowns": ["2026Q3 營收"], "limitations": []}
    issue_c2 = {"claim_id": "c2", "severity": "critical",
                "reason": f"{single_eps} 是 {fin_data.get('latest_period')} 單季 EPS，不是 TTM；期間口徑錯誤",
                "required_evidence": "get_financial_snapshot(ticker, cutoff) 的 eps_ttm，確認連續四個單季"}
    issue_c3 = {"claim_id": "c3", "severity": "minor", "reason": "未知項目可再列出下一個確認訊號",
                "required_evidence": "在 next_signals 寫明 2026Q3 營收公告"}
    round1 = {"round": 1,
              "model": {"decision": "revise", "issues": [issue_c2, issue_c3], "checked_refs": [ev],
                        "decision_summary": "c2 期間口徑錯誤，需補查連續四季 EPS"},
              "rules": {"decision": "revise", "issues": [issue_c2], "checked_refs": [ev]},
              "final": {"decision": "revise", "issues": [issue_c2, issue_c3], "checked_refs": [ev],
                        "decision_summary": "c2 期間口徑錯誤，需補查連續四季 EPS"}}
    round2 = {"round": 2,
              "model": {"decision": "pass", "issues": [], "checked_refs": [ev], "decision_summary": "c2 已改為可由工具重現的 TTM"},
              "rules": {"decision": "pass", "issues": [], "checked_refs": [ev]},
              "final": {"decision": "pass", "issues": [], "checked_refs": [ev], "decision_summary": "c2 已改為可由工具重現的 TTM"}}
    return [
        plan,
        {**fin, "changes": {"stage": "tools", "tool_calls_used": 1, "active_seconds": 6.0}},
        {"role": "researcher", "event_type": "tool_call", "call": _tool("read_evidence", evidence_version_id=ev),
         "changes": {"tool_calls_used": 2, "active_seconds": 8.0}},
        {"role": "researcher", "event_type": "draft", "detail": {"summary": "草稿 v1：3 項主張", "evidence_refs": [ev]},
         "draft": v1, "changes": {"stage": "review", "calls_used": 2, "active_seconds": 14.0}},
        {"role": "reviewer", "event_type": "tool_call", "call": _tool("read_evidence", evidence_version_id=ev),
         "changes": {"tool_calls_used": 3, "active_seconds": 16.0}},
        {"role": "reviewer", "event_type": "review", "detail": {
            "summary": "第 1 輪覆核：revise（c2 critical、c3 minor）", "decision_summary": "c2 期間口徑錯誤，需補查連續四季 EPS",
            "claim_id": "c2", "severity": "critical", "required_evidence": issue_c2["required_evidence"]},
         "review": round1, "changes": {"stage": "revision", "calls_used": 3, "supplement_rounds": 1, "active_seconds": 22.0}},
        {"role": "researcher", "event_type": "tool_call", "call": _tool("get_financial_snapshot", ticker=ticker),
         "detail": {"decision_summary": "依覆核要求補查連續四季 EPS"},
         "changes": {"tool_calls_used": 4, "active_seconds": 25.0}},
        {"role": "researcher", "event_type": "draft", "detail": {"summary": "草稿 v2：只修改 c2，其餘保留"},
         "draft": v2, "changes": {"stage": "review", "calls_used": 4, "active_seconds": 30.0}},
        {"role": "reviewer", "event_type": "review", "detail": {"summary": "第 2 輪覆核：pass", "decision_summary": "c2 已改為可由工具重現的 TTM"},
         "review": round2, "changes": {"calls_used": 5, "active_seconds": 34.0}},
        {"role": "system", "event_type": "finished", "detail": {"summary": "研究完成，等待人工核准（未發布）"},
         "changes": {"status": "succeeded", "stage": "finished", "stop_reason": "review_pass", "publication_status": "draft"}},
    ]


def _run_tool(call: dict[str, Any], cutoff: str) -> dict[str, Any]:
    """Run one of B's deterministic tools and keep only what the trace may show."""

    name, args = call["tool"], dict(call["args"])
    if name in ("search_evidence", "get_financial_snapshot"):
        args["cutoff"] = cutoff
    started = time.perf_counter()
    out = getattr(tools_impl, name)(**args)
    latency_ms = round((time.perf_counter() - started) * 1000, 1)
    data = out.get("data")
    refs: list[str] = []
    if isinstance(data, list):
        refs = [str(d.get("evidence_version_id") or d.get("source_id")) for d in data if isinstance(d, dict)]
    elif isinstance(data, dict) and data.get("evidence_version_id"):
        refs = [str(data["evidence_version_id"])]
    shown_args = {k: ("<job.cutoff_at>" if k == "cutoff" else v) for k, v in args.items()}
    if out.get("reason"):
        summary = out["reason"]
    elif name == "search_evidence":
        summary = f"找到 {len(refs)} 筆來源"
    elif name == "read_evidence":
        summary = "讀取不可變片段"
    elif name == "get_financial_snapshot" and isinstance(data, dict):
        summary = f"最新可得財報期 {data.get('latest_period') or 'NA'}"
    else:
        summary = str(out.get("status"))
    return {
        "tool_status": out.get("status"),
        "summary": summary,
        "evidence_refs": refs,
        "latency_ms": latency_ms,
        "args_redacted": shown_args,
        "output_hash": hashlib.sha256(json.dumps(out, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16],
    }


class MockJobs:
    def __init__(self, db_path: str | Path, root: Path, clock=None):
        self.root = root
        self.store = JobStore(db_path, clock=clock) if clock else JobStore(db_path)
        self.store._conn.execute(  # side table owned by the UI mock only
            "create table if not exists ui_mock_jobs (job_id text primary key, scenario text not null,"
            " started_at real, step integer not null default 0)"
        )

    # ----- create -----------------------------------------------------------
    def create(self, payload: dict[str, Any]) -> tuple[dict[str, Any], bool]:
        scenario = str(payload.get("scenario") or "succeeded")
        if scenario not in SCENARIOS:
            raise ContractError(f"scenario 只限 {', '.join(SCENARIOS)}（MOCK）")
        req = validate_job_request({**payload, "source_snapshot_id": _snapshot_id(self.root)})
        job, created = self.store.create_job(req, model_id=None)
        if created:
            self.store._conn.execute(
                "insert into ui_mock_jobs (job_id, scenario) values (?, ?)", (job["job_id"], scenario))
            self.store.append_event(job["job_id"], "system", "mock_scenario", None,
                                    {"mock": True, "summary": f"MOCK 情境：{scenario}"})
        return self.public_job(job), created

    # ----- read ---------------------------------------------------------------
    def get(self, job_id: str) -> tuple[dict[str, Any], list[dict[str, Any]]] | None:
        self.pump()
        job = self.store.get_job(job_id)
        if job is None or not self._is_mock(job_id):
            return None
        queue_ahead = 0
        if job["status"] == "queued":
            queue_ahead = self.store._conn.execute(
                "select count(*) from research_jobs where status in ('queued','running')"
                " and rowid < (select rowid from research_jobs where job_id = ?)",
                (job_id,),
            ).fetchone()[0]
        public = self.public_job(job)
        public["queue_ahead"] = queue_ahead
        public["review_view"] = review_view(job)
        return public, [self.public_event(e) for e in self.store.list_events(job_id)]

    @staticmethod
    def public_job(job: dict[str, Any]) -> dict[str, Any]:
        out = {key: job.get(key) for key in PUBLIC_JOB_FIELDS}
        out["mock"] = True
        return out

    @staticmethod
    def public_event(event: dict[str, Any]) -> dict[str, Any]:
        detail = event.get("detail") or {}
        return {
            "event_seq": event["event_seq"],
            "created_at": event["created_at"],
            "role": event.get("role"),
            "event_type": event["event_type"],
            "tool_name": event.get("tool_name"),
            "detail": {k: detail[k] for k in PUBLIC_DETAIL_KEYS if k in detail},
        }

    def _is_mock(self, job_id: str) -> bool:
        return self.store._conn.execute("select 1 from ui_mock_jobs where job_id = ?", (job_id,)).fetchone() is not None

    # ----- cancel ---------------------------------------------------------------
    def cancel(self, job_id: str) -> dict[str, Any]:
        """Cancel a running MOCK job through the normal fenced write.

        A queued job cannot be cancelled here: JobStore only lets the lease
        holder change status (CR-A03 for 組長)."""

        self.pump()
        job = self.store.get_job(job_id)
        if job is None or not self._is_mock(job_id):
            raise KeyError(job_id)
        if job["status"] not in CANCELLABLE:
            raise ContractError(f"目前狀態 {job['status']} 不能取消（排隊中取消需組長 JobStore 支援）")
        row = self.store._conn.execute("select lease_token from research_jobs where job_id = ?", (job_id,)).fetchone()
        self.store.append_event(job_id, "system", "cancelled", None,
                                {"mock": True, "summary": "操作者取消；已完成的步驟與預算保留"})
        job = self.store.update_job(job_id, WORKER_ID, row["lease_token"],
                                    {"status": "cancelled", "stage": "finished", "stop_reason": "cancelled_by_operator"})
        return self.public_job(job)

    # ----- time-based progression ---------------------------------------------
    def pump(self) -> None:
        conn = self.store._conn
        running = conn.execute(
            "select r.job_id, r.lease_token, r.lease_owner from research_jobs r join ui_mock_jobs m using (job_id)"
            " where r.status = 'running'"
        ).fetchone()
        if running is None or running["lease_owner"] != WORKER_ID:
            claimed = self.store.claim_next(WORKER_ID)
            if not claimed:
                return
            job, token = claimed
            conn.execute("update ui_mock_jobs set started_at = coalesce(started_at, ?) where job_id = ?",
                         (self.store.clock(), job["job_id"]))
            job_id = job["job_id"]
        else:
            job_id, token = running["job_id"], running["lease_token"]
        self._advance(job_id, token)

    def _advance(self, job_id: str, token: int) -> None:
        conn = self.store._conn
        meta = conn.execute("select scenario, started_at, step from ui_mock_jobs where job_id = ?", (job_id,)).fetchone()
        job = self.store.get_job(job_id)
        steps = _steps(meta["scenario"], job["ticker"])
        due = min(len(steps), int((self.store.clock() - meta["started_at"]) / STEP_SECONDS) + 1)
        try:
            for index in range(meta["step"], due):
                step = steps[index]
                detail = {"mock": True, **step.get("detail", {})}
                tool_name = None
                if step.get("call"):
                    tool_name = step["call"]["tool"]
                    detail.update(_run_tool(step["call"], job["cutoff_at"]))
                self.store.append_event(job_id, step["role"], step["event_type"], tool_name, detail)
                changes = dict(step.get("changes") or {})
                if step.get("draft") or step.get("review"):
                    current = self.store.get_job(job_id)
                    cp = dict(current.get("checkpoint") or {})
                    if step.get("draft"):
                        draft = {**step["draft"], "ticker": current["ticker"], "as_of": current["cutoff_at"]}
                        cp["drafts"] = list(cp.get("drafts") or []) + [draft]
                        changes["draft"] = draft
                    if step.get("review"):
                        cp["reviews"] = list(cp.get("reviews") or []) + [step["review"]]
                        changes["review"] = step["review"]["final"]
                    changes["checkpoint"] = cp
                if changes:
                    self.store.update_job(job_id, WORKER_ID, token, changes)
                else:
                    self.store.heartbeat(job_id, WORKER_ID, token)
                conn.execute("update ui_mock_jobs set step = ? where job_id = ?", (index + 1, job_id))
        except StaleLeaseError:
            return  # lease lapsed (no poll for >60 s); the next pump re-claims and continues
