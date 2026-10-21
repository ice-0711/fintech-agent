"""Persistent job store with idempotency, leases and fencing (W02-L).

The local backend is SQLite on disk so jobs, events, budget counters and the
model-usage ledger survive a process restart (「資料不只保存在 memory」).
The Supabase tables with the same shape are drafted in
supabase_migrations/20260928_v12_research_jobs.sql and have NOT been applied to
any database yet; a Supabase-backed store is added after that migration is
rehearsed on a test database.

Lease rules (ch.02): lease 60 s, heartbeat 20 s, poll 2 s, one active job at a
time. Every claim increments lease_token; writes carrying an old token are
rejected so a stale worker cannot overwrite newer results.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Callable

from .contract import TERMINAL_STATUSES, ContractError, new_job_record, utc_now_iso

# Fields that must match when an idempotency_key is reused.
IDEMPOTENT_FIELDS = ("ticker", "mode", "cutoff_at", "source_snapshot_id", "question_version")

LEASE_SECONDS = 60
HEARTBEAT_SECONDS = 20
POLL_SECONDS = 2

SCHEMA = """
create table if not exists research_jobs (
    job_id text primary key,
    idempotency_key text not null unique,
    status text not null,
    data text not null,
    lease_owner text,
    lease_token integer not null default 0,
    lease_expires_at real,
    created_at text not null,
    updated_at text not null
);
create table if not exists job_events (
    job_id text not null references research_jobs(job_id),
    event_seq integer not null,
    created_at text not null,
    role text,
    event_type text not null,
    tool_name text,
    detail text not null,
    primary key (job_id, event_seq)
);
create table if not exists model_usage (
    usage_id integer primary key autoincrement,
    job_id text,
    sent_at real not null,
    day_key text not null,
    role text,
    model_id text,
    prompt_version text,
    prompt_hash text,
    reserved_tokens integer not null,
    total_tokens integer,
    outcome text not null
);
"""


class StaleLeaseError(RuntimeError):
    """A worker tried to write with an expired or superseded lease."""


class JobStore:
    def __init__(self, path: str | Path, clock: Callable[[], float] = time.time):
        self.path = str(path)
        self.clock = clock
        self._lock = threading.Lock()
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.path, check_same_thread=False, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("pragma foreign_keys = on")
        self._conn.executescript(SCHEMA)

    def close(self) -> None:
        self._conn.close()

    # ----- jobs -----------------------------------------------------------
    def create_job(self, request: dict[str, Any], model_id: str | None) -> tuple[dict[str, Any], bool]:
        """Create a job, or return the existing one for the same idempotency_key."""

        with self._lock:
            existing = self._conn.execute(
                "select data from research_jobs where idempotency_key = ?",
                (request["idempotency_key"],),
            ).fetchone()
            if existing:
                job = json.loads(existing["data"])
                diff = [k for k in IDEMPOTENT_FIELDS if job.get(k) != request.get(k)]
                if diff:
                    raise ContractError(f"idempotency_key 已用於不同內容的 job（{', '.join(diff)} 不同）")
                return job, False
            job = new_job_record(request, model_id)
            self._conn.execute(
                "insert into research_jobs (job_id, idempotency_key, status, data, created_at, updated_at)"
                " values (?, ?, ?, ?, ?, ?)",
                (job["job_id"], job["idempotency_key"], job["status"], json.dumps(job, ensure_ascii=False),
                 job["created_at"], job["updated_at"]),
            )
            self._append_event_locked(job["job_id"], "system", "job_created", None, {"ticker": job["ticker"]})
            return job, True

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        row = self._conn.execute("select data from research_jobs where job_id = ?", (job_id,)).fetchone()
        return json.loads(row["data"]) if row else None

    def claim_next(self, worker_id: str) -> tuple[dict[str, Any], int] | None:
        """Lease the oldest runnable job, respecting the one-active-job rule.

        Runnable: queued; running with an expired lease (worker crashed); or
        paused_quota whose resume_after has passed. Stored checkpoint and
        budget counters are kept, never reset.
        """

        now = self.clock()
        with self._lock:
            self._conn.execute("begin immediate")
            try:
                active = self._conn.execute(
                    "select 1 from research_jobs where status = 'running' and lease_expires_at > ?",
                    (now,),
                ).fetchone()
                if active:
                    self._conn.execute("commit")
                    return None
                row = self._conn.execute(
                    "select job_id, lease_token, data from research_jobs"
                    " where status = 'queued' or (status = 'running' and lease_expires_at <= ?)"
                    " or (status = 'paused_quota' and json_extract(data, '$.resume_after') <= ?)"
                    " order by created_at, rowid limit 1",
                    (now, now),
                ).fetchone()
                if not row:
                    self._conn.execute("commit")
                    return None
                token = row["lease_token"] + 1
                job = json.loads(row["data"])
                recovered = job["status"] in ("running", "paused_quota")
                job["status"] = "running"
                job.pop("resume_after", None)
                job["updated_at"] = utc_now_iso()
                self._conn.execute(
                    "update research_jobs set status = 'running', data = ?, lease_owner = ?, lease_token = ?,"
                    " lease_expires_at = ?, updated_at = ? where job_id = ?",
                    (json.dumps(job, ensure_ascii=False), worker_id, token, now + LEASE_SECONDS,
                     job["updated_at"], job["job_id"]),
                )
                self._append_event_locked(
                    job["job_id"], "system", "lease_recovered" if recovered else "lease_acquired", None,
                    {"worker_id": worker_id, "lease_token": token},
                )
                self._conn.execute("commit")
                return job, token
            except Exception:
                self._conn.execute("rollback")
                raise

    def _check_lease_locked(self, job_id: str, worker_id: str, token: int) -> sqlite3.Row:
        row = self._conn.execute(
            "select data, lease_owner, lease_token, lease_expires_at from research_jobs where job_id = ?",
            (job_id,),
        ).fetchone()
        if row is None:
            raise KeyError(job_id)
        if row["lease_owner"] != worker_id or row["lease_token"] != token or row["lease_expires_at"] <= self.clock():
            raise StaleLeaseError(f"job {job_id}: lease 已失效或被新 worker 取得")
        return row

    def heartbeat(self, job_id: str, worker_id: str, token: int) -> None:
        with self._lock:
            self._check_lease_locked(job_id, worker_id, token)
            self._conn.execute(
                "update research_jobs set lease_expires_at = ? where job_id = ?",
                (self.clock() + LEASE_SECONDS, job_id),
            )

    def update_job(self, job_id: str, worker_id: str, token: int, changes: dict[str, Any]) -> dict[str, Any]:
        """Fenced write: merge changes and bump checkpoint_version."""

        with self._lock:
            row = self._check_lease_locked(job_id, worker_id, token)
            job = json.loads(row["data"])
            cancel = job.get("cancel_requested")
            job.update(changes)
            if cancel:
                job["cancel_requested"] = True
            job["checkpoint_version"] = job.get("checkpoint_version", 1) + 1
            job["updated_at"] = utc_now_iso()
            release = job["status"] in TERMINAL_STATUSES or job["status"] == "paused_quota"
            self._conn.execute(
                "update research_jobs set status = ?, data = ?, updated_at = ?,"
                " lease_owner = case when ? then null else lease_owner end,"
                " lease_expires_at = case when ? then null else lease_expires_at end"
                " where job_id = ?",
                (job["status"], json.dumps(job, ensure_ascii=False), job["updated_at"], release, release, job_id),
            )
            return job

    def request_cancel(self, job_id: str) -> dict[str, Any]:
        """queued/paused jobs are cancelled at once; a running job gets cancel_requested and the
        graph stops before its next step (budget already used stays recorded). Terminal jobs are unchanged."""

        with self._lock:
            row = self._conn.execute("select data from research_jobs where job_id = ?", (job_id,)).fetchone()
            if row is None:
                raise KeyError(job_id)
            job = json.loads(row["data"])
            if job["status"] in TERMINAL_STATUSES:
                return job
            job["cancel_requested"] = True
            if job["status"] in ("queued", "paused_quota"):
                job.update({"status": "cancelled", "stage": "finished", "stop_reason": "cancel_requested"})
                job.pop("resume_after", None)
            job["updated_at"] = utc_now_iso()
            self._conn.execute(
                "update research_jobs set status = ?, data = ?, updated_at = ? where job_id = ?",
                (job["status"], json.dumps(job, ensure_ascii=False), job["updated_at"], job_id),
            )
            self._append_event_locked(job_id, "system", "cancel_requested", None, {"status": job["status"]})
            return job

    def cancel_requested(self, job_id: str) -> bool:
        row = self._conn.execute(
            "select json_extract(data, '$.cancel_requested') from research_jobs where job_id = ?", (job_id,)
        ).fetchone()
        return bool(row and row[0])

    def requeue(self, job_id: str) -> dict[str, Any]:
        """Manually put a paused_quota job back in the queue (e.g. after quota is verified)."""

        with self._lock:
            row = self._conn.execute("select data from research_jobs where job_id = ?", (job_id,)).fetchone()
            if row is None:
                raise KeyError(job_id)
            job = json.loads(row["data"])
            if job["status"] != "paused_quota":
                raise ValueError(f"job {job_id} 狀態為 {job['status']}，只有 paused_quota 能重新排隊")
            job["status"] = "queued"
            job.pop("resume_after", None)
            job["updated_at"] = utc_now_iso()
            self._conn.execute(
                "update research_jobs set status = 'queued', data = ?, updated_at = ? where job_id = ?",
                (json.dumps(job, ensure_ascii=False), job["updated_at"], job_id),
            )
            self._append_event_locked(job_id, "system", "requeued", None, {})
            return job

    # ----- events ---------------------------------------------------------
    def _append_event_locked(self, job_id: str, role: str | None, event_type: str,
                             tool_name: str | None, detail: dict[str, Any]) -> int:
        seq = self._conn.execute(
            "select coalesce(max(event_seq), 0) + 1 from job_events where job_id = ?", (job_id,)
        ).fetchone()[0]
        self._conn.execute(
            "insert into job_events (job_id, event_seq, created_at, role, event_type, tool_name, detail)"
            " values (?, ?, ?, ?, ?, ?, ?)",
            (job_id, seq, utc_now_iso(), role, event_type, tool_name, json.dumps(detail, ensure_ascii=False)),
        )
        return seq

    def append_event(self, job_id: str, role: str | None, event_type: str,
                     tool_name: str | None = None, detail: dict[str, Any] | None = None) -> int:
        with self._lock:
            return self._append_event_locked(job_id, role, event_type, tool_name, detail or {})

    def list_events(self, job_id: str) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "select event_seq, created_at, role, event_type, tool_name, detail from job_events"
            " where job_id = ? order by event_seq",
            (job_id,),
        ).fetchall()
        return [{**dict(r), "detail": json.loads(r["detail"])} for r in rows]

    # ----- model usage ledger (project-wide, used by the budget gate) -----
    def record_send(self, *, job_id: str | None, day_key: str, role: str, model_id: str,
                    prompt_version: str, prompt_hash: str, reserved_tokens: int) -> int:
        """Insert the ledger row BEFORE the HTTP send; outcome is filled later."""

        with self._lock:
            cur = self._conn.execute(
                "insert into model_usage (job_id, sent_at, day_key, role, model_id, prompt_version,"
                " prompt_hash, reserved_tokens, outcome) values (?, ?, ?, ?, ?, ?, ?, ?, 'pending')",
                (job_id, self.clock(), day_key, role, model_id, prompt_version, prompt_hash, reserved_tokens),
            )
            return int(cur.lastrowid)

    def settle_send(self, usage_id: int, outcome: str, total_tokens: int | None) -> None:
        with self._lock:
            self._conn.execute(
                "update model_usage set outcome = ?, total_tokens = ? where usage_id = ?",
                (outcome, total_tokens, usage_id),
            )

    def requests_on_day(self, day_key: str) -> int:
        return self._conn.execute("select count(*) from model_usage where day_key = ?", (day_key,)).fetchone()[0]

    def jobs_on_day(self, day_key: str) -> set[str]:
        rows = self._conn.execute(
            "select distinct job_id from model_usage where day_key = ? and job_id is not null", (day_key,)
        ).fetchall()
        return {r[0] for r in rows}

    def usage_since(self, since: float) -> tuple[int, int]:
        """(requests, tokens) sent since `since`; unknown totals count the reservation."""

        row = self._conn.execute(
            "select count(*), coalesce(sum(coalesce(total_tokens, reserved_tokens)), 0)"
            " from model_usage where sent_at >= ?",
            (since,),
        ).fetchone()
        return int(row[0]), int(row[1])

    def list_usage(self, job_id: str) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "select * from model_usage where job_id = ? order by usage_id", (job_id,)
        ).fetchall()
        return [dict(r) for r in rows]
