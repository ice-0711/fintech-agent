"""Researcher loop (W04-L) and Researcher → Reviewer orchestration (W05-L) on LangGraph.

One graph node = one model send. The model decides every step: which tool to call next,
when to stop and write the draft, and (as Reviewer) what to re-check. Code only enforces
the boundaries from ch.02: role tool sets, the shared budget gate, cutoff/snapshot
binding, forced text on the last affordable call, at most 2 supplement rounds, and that
a review "pass" never publishes anything (publication stays "draft" until human approval, W07).

Every step is checkpointed to the job row through the fenced lease, so a restarted
worker continues from the saved conversation, observations, draft and review with the
budget counters it already used.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Callable, TypedDict

from google.genai import types
from langgraph.graph import END, START, StateGraph

from .budget import BudgetExceeded, BudgetGate, BudgetLimits, ProjectQuota
from .provider import GeminiAdapter, _hash
from .review_checks import check_draft
from .review_contract import REVIEWER_PROMPT_VERSION, validate_review
from .snapshot import SimulatedTimeout, SnapshotToolbox
from .tools import args_hash, dispatch

PROMPTS = Path(__file__).resolve().parent / "prompts"
RESEARCHER_PROMPT = (PROMPTS / "researcher-v1.2.txt").read_text(encoding="utf-8")
REVIEWER_PROMPT = (PROMPTS / "reviewer-v1.2.txt").read_text(encoding="utf-8")
RESEARCHER_PROMPT_VERSION = "researcher-v1.2.0"
QUESTION = "截至 cutoff_at，總經、基本面與估值證據支持哪些觀察？有哪些反向證據、假設與待確認訊號？"
DECISION_RANK = {"pass": 0, "revise": 1, "insufficient": 2}
MAX_STR, MAX_LIST, MAX_RESULT_CHARS = 200, 5, 900
DROP_KEYS = {"content_hash", "output_hash", "source_id"}  # useless to the model, costly in tokens
SOFT_INPUT_MARGIN = 300  # start digesting older tool results this far below the input cap
TOOL_HEADROOM = 350      # compacted tool results are ~100–300 tokens; fit_context digests if one overshoots
MAX_CALLS_PER_TURN = 2   # parallel calls beyond this are answered "skipped" (keeps the context small)
MAX_FORMAT_RETRIES = 1


class GraphState(TypedDict, total=False):
    next: str


# ----- helpers --------------------------------------------------------------
def compact(value: Any, depth: int = 0) -> Any:
    """Shrink a tool result before it goes back into the model context (3,000-token input cap)."""
    if isinstance(value, str):
        return value if len(value) <= MAX_STR else value[:MAX_STR] + "…(截斷)"
    if isinstance(value, list):
        items = [compact(v, depth + 1) for v in value[:MAX_LIST]]
        return items + ([f"…另有 {len(value) - MAX_LIST} 筆"] if len(value) > MAX_LIST else [])
    if isinstance(value, dict):
        return {k: compact(v, depth + 1) for k, v in value.items() if k not in DROP_KEYS}
    return value


def digest(result: dict[str, Any], limit: int = 240) -> str:
    text = json.dumps(compact(result.get("data")), ensure_ascii=False)
    return text if len(text) <= limit else text[:limit] + "…"


def shrink_history(contents: list[Any], observations: list[dict[str, Any]], include_last: bool = False) -> int:
    """Replace older tool results (all but the newest turn, unless include_last) by short digests."""
    by_id = {o["obs_id"]: o for o in observations}
    shrunk = 0
    for content in (contents if include_last else contents[:-1]):
        for part in content.parts or []:
            fr = part.function_response
            if fr is None or not isinstance(fr.response, dict) or fr.response.get("digested"):
                continue
            obs = by_id.get(fr.response.get("obs_id"), {})
            fr.response = {"obs_id": fr.response.get("obs_id"), "status": fr.response.get("status"),
                           "digested": True, "digest": obs.get("digest", "")[:160]}
            shrunk += 1
    return shrunk


def parse_json_object(text: str | None) -> dict[str, Any] | None:
    if not text:
        return None
    body = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    start, end = body.find("{"), body.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        parsed = json.loads(body[start:end + 1])
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def draft_problems(draft: dict[str, Any] | None) -> list[str]:
    if draft is None:
        return ["不是 JSON 物件"]
    problems = []
    if draft.get("status") not in ("draft", "insufficient"):
        problems.append("status 需為 draft 或 insufficient")
    claims = draft.get("claims")
    if not isinstance(claims, list):
        return problems + ["claims 需為陣列"]
    for c in claims:
        if not isinstance(c, dict) or not c.get("claim_id") or c.get("kind") not in ("fact", "inference", "unknown"):
            problems.append("每個 claim 需有 claim_id 與 kind=fact/inference/unknown")
            break
        if not isinstance(c.get("evidence_refs", []), list):
            problems.append("evidence_refs 需為陣列")
            break
    if draft.get("status") == "draft" and not 1 <= len(claims) <= 5:
        problems.append("draft 需 1 至 5 項 claims（建議 3 至 5）")
    return problems


def merge_reviews(model: dict[str, Any], rules: dict[str, Any]) -> dict[str, Any]:
    """The stricter decision wins; deterministic critical issues cannot be overridden by the model."""
    decision = max(model["decision"], rules["decision"], key=DECISION_RANK.__getitem__)
    seen, issues = set(), []
    for issue in model.get("issues", []) + rules.get("issues", []):
        key = (issue["claim_id"], issue["reason"][:40])
        if key not in seen:
            seen.add(key)
            issues.append(issue)
    if decision == "pass" and any(i["severity"] == "critical" for i in issues):
        decision = "revise"
    return {
        "decision": decision,
        "issues": issues[:10],
        "checked_refs": sorted(set(model.get("checked_refs", [])) | set(rules.get("checked_refs", []))),
        "checked_metric_ids": sorted(set(model.get("checked_metric_ids", [])) | set(rules.get("checked_metric_ids", []))),
        "decision_summary": model.get("decision_summary") or rules.get("decision_summary", ""),
    }


# ----- the run ----------------------------------------------------------------
class ResearchRun:
    def __init__(self, lease: Any, gate: BudgetGate, researcher: GeminiAdapter, reviewer: GeminiAdapter | None,
                 toolbox: SnapshotToolbox):
        self.lease, self.gate, self.toolbox = lease, gate, toolbox
        self.adapters = {"researcher": researcher, "reviewer": reviewer}
        job = lease.job
        self.mode = job["mode"]
        cp = job.get("checkpoint") or {}
        load = lambda key: [types.Content.model_validate(c) for c in cp.get(key, [])]  # noqa: E731
        self.r_contents, self.v_contents = load("researcher_contents"), load("reviewer_contents")
        self.observations: list[dict[str, Any]] = cp.get("observations", [])
        self.draft: dict[str, Any] | None = cp.get("draft")
        self.reviews: list[dict[str, Any]] = cp.get("reviews", [])
        self.format_retries: dict[str, int] = cp.get("format_retries", {"researcher": 0, "reviewer": 0})
        self.resume_next: str = cp.get("next", "researcher")
        self.final: dict[str, Any] | None = None

    # -- persistence ---------------------------------------------------------
    @property
    def job(self) -> dict[str, Any]:
        return self.gate.job

    def save(self, changes: dict[str, Any], next_node: str) -> None:
        dump = lambda cs: [c.model_dump(mode="json", exclude_none=True) for c in cs]  # noqa: E731
        changes = dict(changes)
        changes["checkpoint"] = {
            "next": next_node,
            "researcher_contents": dump(self.r_contents),
            "reviewer_contents": dump(self.v_contents),
            "observations": self.observations,
            "draft": self.draft,
            "reviews": self.reviews,
            "format_retries": self.format_retries,
        }
        self.gate.job = self.lease.save(changes)
        self.lease.heartbeat()

    def event(self, role: str, event_type: str, detail: dict[str, Any], tool_name: str | None = None) -> None:
        self.lease.event(role, event_type, tool_name, detail)

    def remaining(self) -> dict[str, int]:
        lim = self.gate.limits
        return {"model_calls": lim.max_calls - self.job.get("calls_used", 0),
                "tool_calls": lim.max_tool_calls - self.job.get("tool_calls_used", 0)}

    # -- tools ---------------------------------------------------------------
    def run_calls(self, role: str, calls: list[Any]) -> list[Any]:
        parts = [self.run_tool(role, c) for c in calls[:MAX_CALLS_PER_TURN]]
        for c in calls[MAX_CALLS_PER_TURN:]:
            parts.append(types.Part.from_function_response(name=c.name, response={
                "status": "skipped", "reason": f"每輪最多執行 {MAX_CALLS_PER_TURN} 個工具；需要時下一輪再呼叫"}))
        if len(calls) > MAX_CALLS_PER_TURN:
            self.event(role, "calls_skipped", {"requested": len(calls), "executed": MAX_CALLS_PER_TURN})
        return parts

    def run_tool(self, role: str, call: Any) -> Any:
        name, args = call.name, dict(call.args or {})
        h = args_hash(args)
        started, simulated = time.monotonic(), 0.0

        def execute(tool: str, a: dict[str, Any]) -> dict[str, Any]:
            nonlocal simulated
            try:
                return self.toolbox(tool, a)
            except SimulatedTimeout as exc:
                simulated = exc.seconds
                raise

        try:
            self.gate.register_tool_call(name, h)
            result = dispatch(role, name, args, job_cutoff=self.job["cutoff_at"], executor=execute)
        except BudgetExceeded as exc:
            if exc.reason not in ("tool_limit", "duplicate_tool_call"):
                raise
            result = {"status": "refused", "tool": name, "reason": str(exc), "data": None}
        # Tool time counts toward the 180 s active-time cap (ch.02), including a simulated timeout.
        self.gate.add_active_time(time.monotonic() - started + simulated)
        obs_id = f"obs-{len(self.observations) + 1}"
        body = {"obs_id": obs_id, **compact(result)}
        text = json.dumps(body, ensure_ascii=False)
        if len(text) > MAX_RESULT_CHARS:
            body = {"obs_id": obs_id, "status": result.get("status"), "tool": name,
                    "reason": result.get("reason"), "data": text[:MAX_RESULT_CHARS] + "…(截斷)"}
        obs = {"obs_id": obs_id, "role": role, "tool_name": name, "args_hash": h, "status": result.get("status"),
               "reason": result.get("reason"), "output_hash": _hash(json.dumps(result, sort_keys=True, ensure_ascii=False))[:16],
               "digest": digest(result)}
        self.observations.append(obs)
        self.event(role, "tool_call", {k: v for k, v in obs.items() if k not in ("role", "tool_name", "digest")}, tool_name=name)
        return types.Part.from_function_response(name=name, response=body)

    def fit_context(self, role: str, contents: list[Any], system: str) -> None:
        """Keep the next send under the 3,000-token input cap by digesting older tool results."""
        cap = self.gate.limits.max_input_tokens
        adapter = self.adapters[role]
        before = adapter.estimate_input(role, contents, system)
        if before > cap - SOFT_INPUT_MARGIN:
            n = shrink_history(contents, self.observations)
            if adapter.estimate_input(role, contents, system) > cap - 100:
                n += shrink_history(contents, self.observations, include_last=True)
            if n:
                self.event(role, "context_digested", {"results": n, "estimate_before": before,
                                                      "estimate_after": adapter.estimate_input(role, contents, system)})

    def tools_allowed(self, role: str, contents: list[Any] | None = None, system: str = "") -> bool:
        rem = self.remaining()
        if rem["tool_calls"] <= 0:
            return False
        if contents is not None:
            limit = self.gate.limits.max_input_tokens - TOOL_HEADROOM
            est = self.adapters[role].estimate_input(role, contents, system)
            if est > limit and shrink_history(contents, self.observations):
                est = self.adapters[role].estimate_input(role, contents, system)  # older results digested
            if est > limit:
                return False  # still no room for another tool result: answer now instead of overflowing
        if role == "researcher":
            if self.mode == "single":
                return rem["model_calls"] > 1
            if self.job["stage"] in ("research", "tools"):
                return self.job.get("calls_used", 0) < self.gate.limits.initial_research_calls - 1
            return rem["model_calls"] > 2  # revision: keep one call for the draft and one for review
        return rem["model_calls"] > 1  # reviewer: keep one call for the decision

    # -- nodes ---------------------------------------------------------------
    def cancelled(self) -> bool:
        return self.lease.store.cancel_requested(self.job["job_id"])

    def researcher_node(self, state: GraphState) -> GraphState:
        if self.cancelled():
            return self.finish("cancelled", "cancel_requested")
        job = self.job
        if not self.r_contents:
            trusted = {"job_id": job["job_id"], "ticker": job["ticker"], "cutoff_at": job["cutoff_at"],
                       "source_snapshot_id": job["source_snapshot_id"], "question_version": job["question_version"],
                       "question": QUESTION, "focus": job.get("focus"), "remaining": self.remaining()}
            self.r_contents.append(types.Content(role="user", parts=[types.Part.from_text(
                text="可信輸入：" + json.dumps(trusted, ensure_ascii=False))]))
        self.fit_context("researcher", self.r_contents, RESEARCHER_PROMPT)
        allow = self.tools_allowed("researcher", self.r_contents, RESEARCHER_PROMPT)
        if not allow:
            self.r_contents.append(types.Content(role="user", parts=[types.Part.from_text(
                text="現在不能再呼叫工具：請依已取得的結果直接輸出規定的 JSON 草稿（不足就 status=insufficient）。")]))
        resp = self.adapters["researcher"].send("researcher", self.r_contents, RESEARCHER_PROMPT, allow_tools=allow)
        model_turn = resp.candidates[0].content if resp.candidates else None
        calls = resp.function_calls or []
        if calls and not allow:
            # The model asked for tools on a text-only turn: do not run them (that would eat the review call).
            self.event("researcher", "tools_refused", {"requested": [c.name for c in calls]})
            draft = {"status": "insufficient", "claims": [],
                     "limitations": ["Researcher 在必須寫草稿的回合仍要求呼叫工具，未產出草稿"]}
            draft.update({"ticker": job["ticker"], "snapshot_id": job["source_snapshot_id"], "as_of": job["cutoff_at"]})
            self.draft = draft
            return self.finish("insufficient_evidence", "no_draft_on_final_turn")
        if calls:
            self.r_contents.append(model_turn)
            parts = self.run_calls("researcher", calls)
            self.r_contents.append(types.Content(role="user", parts=parts))
            self.save({}, "researcher")
            return {"next": "researcher"}

        draft = parse_json_object(resp.text)
        problems = draft_problems(draft)
        if model_turn is not None:
            self.r_contents.append(model_turn)
        if problems:
            self.event("researcher", "draft_invalid", {"problems": problems})
            if self.format_retries["researcher"] < MAX_FORMAT_RETRIES and self.remaining()["model_calls"] > 1:
                self.format_retries["researcher"] += 1
                self.r_contents.append(types.Content(role="user", parts=[types.Part.from_text(
                    text="上一則不是合格草稿（" + "；".join(problems) + "）。只輸出規定的 JSON 物件。")]))
                self.save({}, "researcher")
                return {"next": "researcher"}
            draft = {"status": "insufficient", "claims": [], "limitations": ["Researcher 未產出合格草稿：" + "；".join(problems)]}
        draft.update({"ticker": job["ticker"], "snapshot_id": job["source_snapshot_id"], "as_of": job["cutoff_at"]})
        self.draft = draft
        self.event("researcher", "draft", {"status": draft["status"], "claims": len(draft.get("claims", [])),
                                           "decision_summary": str(draft.get("decision_summary", ""))[:120]})
        if draft["status"] == "insufficient":
            # No model review is spent on an insufficient draft, but its fact claims still get the
            # deterministic checks so a wrong number in it is recorded (never published either way).
            rules = None
            if self.mode == "dual" and draft.get("claims"):
                rules = check_draft(draft, self.toolbox.snapshot_view(), job["cutoff_at"], job["source_snapshot_id"],
                                    remaining_calls=0, observations=self.observations)["review"]
                self.reviews.append({"round": len(self.reviews) + 1, "model": None, "rules": rules, "final": rules})
                self.event("reviewer", "rules_check", {"rules_decision": rules["decision"],
                           "critical": [i["claim_id"] for i in rules["issues"] if i["severity"] == "critical"]})
            return self.finish("insufficient_evidence", "researcher_insufficient", review=rules)
        if self.mode == "single":
            return self.finish("succeeded", "draft_without_review")
        self.v_contents = []
        self.save({"stage": "review", "draft": draft}, "reviewer")
        return {"next": "reviewer"}

    def reviewer_node(self, state: GraphState) -> GraphState:
        if self.cancelled():
            return self.finish("cancelled", "cancel_requested")
        job, draft = self.job, self.draft or {}
        claim_ids = [c["claim_id"] for c in draft.get("claims", [])]
        if not self.v_contents:
            cited = {r for c in draft.get("claims", []) for r in c.get("evidence_refs", [])}
            cited |= {f.get("source_ref") for c in draft.get("claims", []) for f in c.get("facts", []) or []}
            trusted = {"job_id": job["job_id"], "source_snapshot_id": job["source_snapshot_id"],
                       "cutoff_at": job["cutoff_at"], "remaining_budget": self.remaining(),
                       "draft_claims": draft.get("claims", []), "conflicts": draft.get("conflicts", []),
                       "limitations": draft.get("limitations", []),
                       "researcher_observations_note": "obs-* 是 Researcher 在本 job 依其權限（六工具，含 get_price_window、"
                                                       "search_evidence）取得的工具結果，可作為引用；你不能重查股價或搜尋，"
                                                       "需要新資料時以 required_evidence 退回 Researcher。",
                       "researcher_observations": [
                           {"obs_id": o["obs_id"], "tool_name": o["tool_name"], "status": o["status"],
                            **({"data": o.get("digest")} if o["obs_id"] in cited else {})}
                           for o in self.observations if o["role"] == "researcher"]}
            self.v_contents.append(types.Content(role="user", parts=[types.Part.from_text(
                text="可信輸入：" + json.dumps(trusted, ensure_ascii=False))]))
        self.fit_context("reviewer", self.v_contents, REVIEWER_PROMPT)
        resp = self.adapters["reviewer"].send("reviewer", self.v_contents, REVIEWER_PROMPT,
                                              allow_tools=self.tools_allowed("reviewer", self.v_contents, REVIEWER_PROMPT))
        model_turn = resp.candidates[0].content if resp.candidates else None
        calls = resp.function_calls or []
        if calls and not self.tools_allowed("reviewer", self.v_contents, REVIEWER_PROMPT):
            self.event("reviewer", "tools_refused", {"requested": [c.name for c in calls]})
            review = {"decision": "insufficient", "issues": [], "checked_refs": [], "checked_metric_ids": [],
                      "decision_summary": "Reviewer 在必須下結論的回合仍要求工具，不能視為已核實"}
            return self.finish("insufficient_evidence", "no_review_on_final_turn", review=review)
        if calls:
            self.v_contents.append(model_turn)
            parts = self.run_calls("reviewer", calls)
            self.v_contents.append(types.Content(role="user", parts=parts))
            self.save({}, "reviewer")
            return {"next": "reviewer"}

        review = parse_json_object(resp.text)
        errors = validate_review(review, claim_ids) if review is not None else ["不是 JSON 物件"]
        if model_turn is not None:
            self.v_contents.append(model_turn)
        if errors:
            self.event("reviewer", "review_invalid", {"errors": errors[:5]})
            if self.format_retries["reviewer"] < MAX_FORMAT_RETRIES and self.remaining()["model_calls"] > 0:
                self.format_retries["reviewer"] += 1
                self.v_contents.append(types.Content(role="user", parts=[types.Part.from_text(
                    text="上一則不符合覆核輸出規格（" + "；".join(errors[:3]) + "）。只輸出規定的 JSON。")]))
                self.save({}, "reviewer")
                return {"next": "reviewer"}
            review = {"decision": "insufficient", "issues": [], "checked_refs": [], "checked_metric_ids": [],
                      "decision_summary": "Reviewer 輸出不合格，不能視為已核實"}
        rules = check_draft(draft, self.toolbox.snapshot_view(), job["cutoff_at"], job["source_snapshot_id"],
                            remaining_calls=self.remaining()["model_calls"], observations=self.observations)["review"]
        final = merge_reviews(review, rules)
        self.reviews.append({"round": len(self.reviews) + 1, "model": review, "rules": rules, "final": final})
        self.event("reviewer", "review", {"round": len(self.reviews), "model_decision": review["decision"],
                                          "rules_decision": rules["decision"], "final_decision": final["decision"],
                                          "critical": [i["claim_id"] for i in final["issues"] if i["severity"] == "critical"]})
        if final["decision"] == "pass":
            return self.finish("succeeded", "review_pass", review=final)
        if final["decision"] == "insufficient":
            return self.finish("insufficient_evidence", "review_insufficient", review=final)
        # revise: bounded supplement round back to the Researcher (≤2 rounds, needs ≥2 calls)
        if self.job.get("supplement_rounds", 0) >= self.gate.limits.max_supplement_rounds or self.remaining()["model_calls"] < 2:
            return self.finish("insufficient_evidence", "unresolved_critical", review=final)
        self.gate.start_supplement_round()
        # Fresh, compact conversation for the revision round (the full history would not fit the
        # 3,000-token input cap): previous draft + concrete feedback + digests of earlier tool results.
        revision = {
            "job_id": job["job_id"], "ticker": job["ticker"], "cutoff_at": job["cutoff_at"],
            "source_snapshot_id": job["source_snapshot_id"], "remaining": self.remaining(),
            "previous_draft": {k: draft.get(k) for k in ("claims", "conflicts", "unknowns", "limitations")},
            "review_feedback": [{k: i[k] for k in ("claim_id", "severity", "reason", "required_evidence")}
                                for i in final["issues"]],
            "earlier_observations": [{"obs_id": o["obs_id"], "tool_name": o["tool_name"], "status": o["status"],
                                      "digest": o.get("digest", "")[:160]} for o in self.observations],
        }
        self.r_contents = [types.Content(role="user", parts=[types.Part.from_text(
            text="修正輪可信輸入：" + json.dumps(revision, ensure_ascii=False))])]
        self.save({"stage": "revision", "review": final}, "researcher")
        return {"next": "researcher"}

    def finish(self, status: str, reason: str, review: dict[str, Any] | None = None) -> GraphState:
        self.final = {"status": status, "stage": "finished", "stop_reason": reason, "draft": self.draft,
                      "review": review, "publication_status": "draft"}  # never published here (W07 human approval)
        self.save({"draft": self.draft, "review": review}, "end")
        return {"next": "end"}

    # -- graph -----------------------------------------------------------------
    def execute(self) -> dict[str, Any]:
        graph = StateGraph(GraphState)
        graph.add_node("researcher", self.researcher_node)
        graph.add_node("reviewer", self.reviewer_node)
        route = {"researcher": "researcher", "reviewer": "reviewer", "end": END}
        graph.add_conditional_edges(START, lambda s: s["next"], route)
        graph.add_conditional_edges("researcher", lambda s: s["next"], route)
        graph.add_conditional_edges("reviewer", lambda s: s["next"], route)
        start = self.resume_next if self.resume_next in ("researcher", "reviewer") else "researcher"
        graph.compile().invoke({"next": start}, {"recursion_limit": 40})
        if self.final is None:
            raise RuntimeError("graph ended without a final state")
        return self.final


def make_research_handler(client: Any, model_id: str, quota: ProjectQuota, *, thinking_level: str = "minimal",
                          sleep: Callable[[float], None] = time.sleep) -> Callable[[Any], dict[str, Any]]:
    """Worker handler: builds the shared budget gate, both role adapters and the snapshot toolbox."""

    def handler(lease: Any) -> dict[str, Any]:
        job = lease.job
        if job["mode"] == "workflow":
            raise ValueError("workflow 模式（固定流程基線）尚未實作，排在實驗前（W09）")
        gate = BudgetGate(store=lease.store, job=job, persist=lease.save, quota=quota,
                          limits=BudgetLimits(initial_research_calls=8 if job["mode"] == "single" else 4))

        def adapter(version: str) -> GeminiAdapter:
            return GeminiAdapter(client, model_id, gate, prompt_version=version, thinking_level=thinking_level,
                                 sleep=sleep, heartbeat=lease.heartbeat)

        toolbox = SnapshotToolbox(job["ticker"], job["source_snapshot_id"], job["cutoff_at"])
        reviewer = adapter(REVIEWER_PROMPT_VERSION) if job["mode"] == "dual" else None
        return ResearchRun(lease, gate, adapter(RESEARCHER_PROMPT_VERSION), reviewer, toolbox).execute()

    return handler
