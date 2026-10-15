"""Budget gate V1 (handbook ch.02 「預算 V1」, W03-L).

Rules enforced here, all before anything is sent to the model:
- ≤ 8 model HTTP sends per job; Researcher, Reviewer, format retries and
  network retries all share it. The counter is incremented and persisted
  BEFORE the send and is never refunded on timeout/429/failure.
- Calls 1–4 are for initial research; call 5 is kept for review, so the
  Researcher cannot use it in the initial research stage. Calls 6–8 are for
  revision or review only.
- ≤ 3,000 input tokens per send (conservative estimate, reconciled against the
  provider's usage afterwards); ≤ 1,500 output tokens per send, thinking
  tokens included (Gemini counts them inside max_output_tokens);
  ≤ 40,000 reserved/observed tokens per job.
- ≤ 10 tool calls per job, ≤ 2 identical tool calls, ≤ 2 supplement rounds,
  ≤ 180 s active time.
- Project-wide RPM/TPM/RPD with 20 % headroom, shared by every Gemini user in
  the project. Unknown quota values mean no live sends (J = 0).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable
from zoneinfo import ZoneInfo

from .store import JobStore

QUOTA_DAY_TZ = ZoneInfo("America/Los_Angeles")  # Gemini daily quota resets at midnight Pacific
HEADROOM = 0.8


@dataclass(frozen=True)
class BudgetLimits:
    max_calls: int = 8
    initial_research_calls: int = 4
    max_input_tokens: int = 3000
    max_output_tokens: int = 1500  # includes thinking tokens
    job_token_budget: int = 40000
    max_tool_calls: int = 10
    max_same_tool_call: int = 2
    max_supplement_rounds: int = 2
    max_active_seconds: float = 180.0
    max_retries: int = 1


class BudgetExceeded(RuntimeError):
    """Raised instead of sending. `reason` becomes the job stop_reason."""

    # reasons that should park the job as paused_quota instead of failing it
    PAUSE_REASONS = {"daily_quota", "quota_unknown", "provider_429", "rate_limited"}

    def __init__(self, reason: str, message: str, wait_seconds: float | None = None):
        super().__init__(f"{reason}: {message}")
        self.reason = reason
        self.wait_seconds = wait_seconds

    @property
    def job_status(self) -> str:
        if self.reason in self.PAUSE_REASONS:
            return "paused_quota"
        if self.reason == "active_time":
            return "timed_out"
        return "insufficient_evidence"


ASCII_CHARS_PER_TOKEN = 3


def estimate_tokens(text: str) -> int:
    """Upper-bound estimate: 1 token per non-ASCII char, 1 per 3 ASCII chars.

    Calibrated 2026-10-15 (W04-L) on the W03 live check: estimates were 725 and 1,136 for
    actual prompt counts of 597 and 1,007 (+21 %, +13 %). The previous 1-per-2 rule
    over-counted by ~1.7x and left no room under the 3,000-token input cap once the
    six tool declarations were included. Every send logs estimate vs actual
    (event detail `input_estimate`), so an under-count is visible.
    """

    non_ascii = sum(1 for ch in text if ord(ch) > 127)
    return non_ascii + math.ceil((len(text) - non_ascii) / ASCII_CHARS_PER_TOKEN)


def seconds_until_quota_reset(now: float) -> float:
    """Seconds until the next midnight Pacific time, when Gemini RPD resets."""

    local = datetime.fromtimestamp(now, QUOTA_DAY_TZ)
    reset = (local + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return max(1.0, reset.timestamp() - now)


def daily_job_limit(rpd: int | None, other_reserved: int = 0, calls_per_job: int = 8) -> int:
    """J = min(6, floor(max(0, floor(0.8 * RPD) - other) / 8)); unknown RPD → 0."""

    if rpd is None:
        return 0
    return min(6, math.floor(max(0, math.floor(HEADROOM * rpd) - other_reserved) / calls_per_job))


@dataclass
class ProjectQuota:
    """Verified per-project limits for ONE model id. None = not verified yet."""

    model_id: str | None = None
    rpm: int | None = None
    tpm: int | None = None
    rpd: int | None = None
    other_daily_reserved: int = 0

    def verified(self) -> bool:
        return None not in (self.model_id, self.rpm, self.tpm, self.rpd)

    @classmethod
    def from_baseline(cls, data: dict[str, Any]) -> "ProjectQuota":
        limits = data.get("gemini", {})
        return cls(
            model_id=limits.get("model_id"),
            rpm=limits.get("rpm"),
            tpm=limits.get("tpm"),
            rpd=limits.get("rpd"),
            other_daily_reserved=int(limits.get("other_daily_reserved") or 0),
        )


@dataclass
class Reservation:
    usage_id: int
    call_number: int
    reserved_tokens: int
    role: str
    input_estimate: int = 0


@dataclass
class BudgetGate:
    """Per-job gate. `persist` writes counter changes through the fenced lease."""

    store: JobStore
    job: dict[str, Any]
    persist: Callable[[dict[str, Any]], dict[str, Any]]
    quota: ProjectQuota
    limits: BudgetLimits = field(default_factory=BudgetLimits)
    clock: Callable[[], float] | None = None

    def _now(self) -> float:
        return (self.clock or self.store.clock)()

    def _save(self, changes: dict[str, Any]) -> None:
        self.job = self.persist(changes)

    # ----- model sends ----------------------------------------------------
    def check_project_quota(self, reserve_tokens: int) -> None:
        q = self.quota
        if not q.verified():
            raise BudgetExceeded("quota_unknown", "RPM/TPM/RPD 尚未由組長核實，只能跑 mock（J=0）")
        now = self._now()
        day_key = datetime.fromtimestamp(now, QUOTA_DAY_TZ).date().isoformat()
        day_cap = math.floor(HEADROOM * q.rpd) - q.other_daily_reserved
        if self.store.requests_on_day(day_key) >= day_cap:
            raise BudgetExceeded("daily_quota", f"今日（太平洋時間 {day_key}）已達 80% RPD 上限 {day_cap}",
                                 wait_seconds=seconds_until_quota_reset(now))
        # J: a job that has not sent anything today may only start if fewer than J jobs have.
        jobs_today = self.store.jobs_on_day(day_key)
        j_limit = daily_job_limit(q.rpd, q.other_daily_reserved)  # handbook formula divides by 8
        if self.job["job_id"] not in jobs_today and len(jobs_today) >= j_limit:
            raise BudgetExceeded("daily_quota", f"今日已有 {len(jobs_today)} 個研究 job，達每日上限 J={j_limit}",
                                 wait_seconds=seconds_until_quota_reset(now))
        req, tok = self.store.usage_since(now - 60)
        if req >= math.floor(HEADROOM * q.rpm) or tok + reserve_tokens > math.floor(HEADROOM * q.tpm):
            raise BudgetExceeded("rate_limited", "近 60 秒 RPM/TPM 已達 80%", wait_seconds=60)

    def reserve_call(self, role: str, prompt_text: str, prompt_hash: str,
                     prompt_version: str | None = None) -> Reservation:
        lim, job = self.limits, self.job
        used = job.get("calls_used", 0)
        if job.get("active_seconds", 0.0) >= lim.max_active_seconds:
            raise BudgetExceeded("active_time", f"主動執行已達 {lim.max_active_seconds:.0f}s，不再發送")
        if used >= lim.max_calls:
            raise BudgetExceeded("call_limit", f"已用 {used}/{lim.max_calls} 次模型發送（含失敗與重試）")
        if role == "researcher" and job.get("stage") in ("research", "tools") and used >= lim.initial_research_calls:
            raise BudgetExceeded("reserved_for_review", f"第 {used + 1} 次保留給覆核，初次研究最多 {lim.initial_research_calls} 次")
        est_in = estimate_tokens(prompt_text)
        if est_in > lim.max_input_tokens:
            raise BudgetExceeded("input_too_large", f"輸入估計 {est_in} token > {lim.max_input_tokens}")
        reserve = est_in + lim.max_output_tokens
        committed = job.get("tokens_observed", 0) + job.get("tokens_reserved", 0)
        if committed + reserve > lim.job_token_budget:
            raise BudgetExceeded("token_limit", f"已用/保留 {committed} + 本次 {reserve} > {lim.job_token_budget}")
        self.check_project_quota(reserve)

        # Commit the reservation before sending: counters first, then ledger row.
        self._save({"calls_used": used + 1, "tokens_reserved": job.get("tokens_reserved", 0) + reserve})
        day_key = datetime.fromtimestamp(self._now(), QUOTA_DAY_TZ).date().isoformat()
        usage_id = self.store.record_send(
            job_id=job["job_id"], day_key=day_key, role=role, model_id=self.quota.model_id or "",
            prompt_version=prompt_version or job.get("prompt_version", ""), prompt_hash=prompt_hash,
            reserved_tokens=reserve,
        )
        return Reservation(usage_id=usage_id, call_number=used + 1, reserved_tokens=reserve, role=role,
                           input_estimate=est_in)

    def can_send_again(self) -> bool:
        """Cheap pre-check so a retry does not sleep when the next send would be refused anyway."""

        return (self.job.get("calls_used", 0) < self.limits.max_calls
                and self.job.get("active_seconds", 0.0) < self.limits.max_active_seconds)

    def settle(self, res: Reservation, outcome: str, total_tokens: int | None) -> None:
        """Replace the reservation with provider usage. Unknown usage keeps the reservation."""

        observed = res.reserved_tokens if total_tokens is None else total_tokens
        self.store.settle_send(res.usage_id, outcome, total_tokens)
        self._save({
            "tokens_reserved": max(0, self.job.get("tokens_reserved", 0) - res.reserved_tokens),
            "tokens_observed": self.job.get("tokens_observed", 0) + observed,
        })

    # ----- tools, rounds, time -------------------------------------------
    def register_tool_call(self, tool_name: str, args_hash: str) -> None:
        lim, job = self.limits, self.job
        used = job.get("tool_calls_used", 0)
        if used >= lim.max_tool_calls:
            raise BudgetExceeded("tool_limit", f"已用 {used}/{lim.max_tool_calls} 次工具")
        counts = dict(job.get("tool_arg_counts") or {})
        key = f"{tool_name}:{args_hash}"
        if counts.get(key, 0) >= lim.max_same_tool_call:
            raise BudgetExceeded("duplicate_tool_call", f"{tool_name} 相同參數已呼叫 {lim.max_same_tool_call} 次")
        counts[key] = counts.get(key, 0) + 1
        self._save({"tool_calls_used": used + 1, "tool_arg_counts": counts})

    def start_supplement_round(self) -> None:
        rounds = self.job.get("supplement_rounds", 0)
        if rounds >= self.limits.max_supplement_rounds:
            raise BudgetExceeded("supplement_limit", f"補查已 {rounds} 輪")
        self._save({"supplement_rounds": rounds + 1})

    def add_active_time(self, seconds: float) -> None:
        total = self.job.get("active_seconds", 0.0) + seconds
        self._save({"active_seconds": round(total, 3)})
        if total > self.limits.max_active_seconds:
            raise BudgetExceeded("active_time", f"主動執行 {total:.0f}s > {self.limits.max_active_seconds:.0f}s")
