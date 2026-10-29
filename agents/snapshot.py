"""Bind tool calls to the job's source snapshot (W04-L integration).

ch.02: read_evidence returns immutable fragments *of this job's snapshot*; source ids
must belong to the snapshot. B's tools (agents/tools_impl.py) read one global store
(data/financial-snapshots.json). The 10 development cases have their own snapshots in
fixtures/dev/case_fixtures.json (B, W04-B). This layer serves those snapshot contents
first and falls back to B's tools for everything a case snapshot does not override.
B's tool code is not modified.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from . import tools_impl
from .register_tools import TOOL_TIMEOUT_SECONDS, with_timeout

ROOT = Path(__file__).resolve().parents[1]
DEV_FIXTURES = ROOT / "fixtures" / "dev" / "case_fixtures.json"
TEST_FIXTURES = ROOT / "fixtures" / "test" / "case_fixtures.json"  # sealed holdout (W10/W11 runs only)


def _t(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _avail(e: dict[str, Any]) -> tuple[str | None, str | None]:
    """(可得時間字串, basis)：官方 available_at 優先，否則 captured_at（CASE-16）；兩者皆無 → (None, None)。"""
    if e.get("available_at"):
        return e["available_at"], "official"
    if e.get("captured_at"):
        return e["captured_at"], "captured_at_fallback"
    return None, None


def _available_by(e: dict[str, Any], limit: datetime) -> bool:
    when, _ = _avail(e)
    return when is not None and _t(when) <= limit


def _numbers(value: Any) -> list[float]:
    """Every numeric leaf in a tool result (bools and date-like strings are skipped)."""
    if isinstance(value, bool) or value is None:
        return []
    if isinstance(value, (int, float)):
        return [float(value)]
    if isinstance(value, dict):
        return [n for v in value.values() for n in _numbers(v)]
    if isinstance(value, (list, tuple)):
        return [n for v in value for n in _numbers(v)]
    return []


def load_case_snapshot(snapshot_id: str) -> dict[str, Any] | None:
    """Dev snapshots (snap-dev-*) or sealed holdout snapshots (snap-test-*, CR-W05-holdout).
    Which cases may run is decided by the runner: scripts/dev_traces.py refuses holdout ids."""
    path = TEST_FIXTURES if snapshot_id.startswith("snap-test-") else DEV_FIXTURES
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8")).get("snapshots", {}).get(snapshot_id)


class SnapshotToolbox:
    """executor(name, args) for agents.tools.dispatch, scoped to one job."""

    def __init__(self, ticker: str, snapshot_id: str, cutoff_at: str):
        self.ticker, self.snapshot_id, self.cutoff = ticker, snapshot_id, _t(cutoff_at)
        self.case = load_case_snapshot(snapshot_id)

    # -- evidence ----------------------------------------------------------
    def _evidences(self) -> list[dict[str, Any]]:
        if self.case is not None:
            return [e for e in self.case.get("evidences", []) if _available_by(e, self.cutoff)]
        return [e for e in tools_impl._load_snapshots().get("evidences", [])
                if e.get("ticker") == self.ticker and _available_by(e, self.cutoff)]

    def snapshot_view(self) -> dict[str, Any]:
        """Snapshot dict for the deterministic review checks (agents/review_checks.py).
        Unreadable sources (paragraph null) become "" so no number can be found in them."""
        view = dict(self.case or {"ticker": self.ticker})
        view["evidences"] = [dict(e, paragraph=e.get("paragraph") or "") for e in self._evidences()]
        # Numbers the financial/price tools return for this job (10/29): a fact citing the snapshot_id must match one.
        nums: list[float] = []
        for call in (lambda: self.get_financial_snapshot(self.ticker, self.cutoff.isoformat()),
                     lambda: self.get_price_window(self.ticker, self.cutoff.isoformat(), 1)):
            try:
                result = call()
            except Exception:  # noqa: BLE001 - a tool failure just means no numbers from it
                continue
            if result.get("status") == "ok":
                nums.extend(_numbers(result.get("data")))
        view["tool_numbers"] = nums
        return view

    def search_evidence(self, ticker: str, query: str, cutoff: str, limit: int = 5) -> dict[str, Any]:
        if self.case is None:
            return tools_impl.search_evidence(ticker=ticker, query=query, cutoff=cutoff, limit=limit)
        if ticker != self.ticker:
            return {"status": "no_data", "tool": "search_evidence", "reason": f"本 job 快照只含 {self.ticker}", "data": None}
        limit_dt = min(self.cutoff, _t(cutoff))
        rows = [{
            "source_id": e["evidence_version_id"],
            "evidence_version_id": e["evidence_version_id"],
            "title": e.get("title", ""),
            "available_at": _avail(e)[0],
            "available_at_basis": _avail(e)[1],
            "content_hash": e.get("content_hash"),
            "abstract": (e.get("paragraph") or "")[:80] or None,
            **({"read_status": "unreadable"} if e.get("paragraph") is None else {}),
        } for e in self._evidences() if _available_by(e, limit_dt)]
        if not rows:
            return {"status": "no_data", "tool": "search_evidence", "reason": "本快照於 cutoff 前無可得來源", "data": None}
        return {"status": "ok", "tool": "search_evidence", "data": rows[:limit]}

    def read_evidence(self, evidence_version_id: str) -> dict[str, Any]:
        for e in self._evidences():
            if e["evidence_version_id"] == evidence_version_id:
                if e.get("paragraph") is None:  # CASE-15; same shape as B's tools_impl
                    return {"status": "unreadable", "tool": "read_evidence", "data": None,
                            "reason": "來源正文不可讀（paragraph 為 null），不得補造內容"}
                return {"status": "ok", "tool": "read_evidence", "data": {
                    "evidence_version_id": e["evidence_version_id"],
                    "paragraph": e["paragraph"][:1200],
                    "source_url": e.get("source_url"),
                    "content_hash": e.get("content_hash"),
                    "available_at": _avail(e)[0],
                    "available_at_basis": _avail(e)[1],
                }}
        return {"status": "no_data", "tool": "read_evidence",
                "reason": f"{evidence_version_id} 不屬於本 job 快照 {self.snapshot_id} 或 cutoff 前不可得", "data": None}

    # -- numbers -----------------------------------------------------------
    def get_financial_snapshot(self, ticker: str, cutoff: str) -> dict[str, Any]:
        case = self.case or {}
        fin = case.get("financial_snapshot")
        price = case.get("price_snapshot")
        if ticker == self.ticker and fin and _t(fin["available_at"]) <= min(self.cutoff, _t(cutoff)):
            data = {k: v for k, v in fin.items() if k != "ticker"}
            data.setdefault("period_basis", "single_quarter" if "period" in fin else None)
            data["snapshot_id"] = self.snapshot_id
            return {"status": "ok", "tool": "get_financial_snapshot", "data": data}
        if ticker == self.ticker and price and "eps_ttm" in price and _t(price["available_at"]) <= self.cutoff:
            return {"status": "ok", "tool": "get_financial_snapshot", "data": {
                "eps_ttm": price["eps_ttm"], "currency": "TWD", "as_of": price["trade_date"],
                "available_at": price["available_at"], "snapshot_id": self.snapshot_id}}
        return tools_impl.get_financial_snapshot(ticker=ticker, cutoff=cutoff)

    def get_price_window(self, ticker: str, end_at: str, sessions: int) -> dict[str, Any]:
        price = (self.case or {}).get("price_snapshot")
        if ticker == self.ticker and price:
            if sessions != 1 or _t(price["available_at"]) > min(self.cutoff, _t(end_at)):
                return {"status": "no_data", "tool": "get_price_window",
                        "reason": "本快照只有單日收盤價（sessions=1）", "data": None}
            return {"status": "ok", "tool": "get_price_window", "data": {
                "ticker": ticker, "currency": "TWD", "price_basis": "raw_close", "sessions": 1,
                "closes": [{"trade_date": price["trade_date"], "close_price": price["close_price"]}],
                "snapshot_id": self.snapshot_id}}
        return tools_impl.get_price_window(ticker=ticker, end_at=end_at, sessions=sessions)

    def get_macro_snapshot(self, cutoff: str, series_ids: list[str]) -> dict[str, Any]:
        return tools_impl.get_macro_snapshot(cutoff=cutoff, series_ids=series_ids)

    def calculate_metrics(self, operation: str, values: dict[str, Any], evidence_refs: list[str]) -> dict[str, Any]:
        return tools_impl.calculate_metrics(operation=operation, values=values, evidence_refs=evidence_refs)

    def _simulated_timeout(self, name: str, args: dict[str, Any]) -> bool:
        sim = (self.case or {}).get("tool_simulation") or {}
        if sim.get("behavior") != "timeout" or sim.get("tool_name") != name:
            return False
        target = sim.get("evidence_version_id")
        return target is None or args.get("evidence_version_id") == target

    def _simulated_no_data(self, name: str) -> dict[str, Any] | None:
        """CASE-30：tool_simulation behavior=no_data 時，該工具回結構化 no_data（不拋例外、不補值）。"""
        sim = (self.case or {}).get("tool_simulation") or {}
        if sim.get("behavior") != "no_data" or sim.get("tool_name") != name:
            return None
        return {"status": "no_data", "tool": name, "data": None,
                "reason": sim.get("reason") or "快照模擬：工具回傳結構化 no_data"}

    def __call__(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        """Run with B's per-tool timeout (register_tools.with_timeout). A snapshot's
        tool_simulation=timeout (CASE-26) is answered as that timeout would be, without
        actually waiting; the elapsed limit is reported so it counts toward active time."""
        if self._simulated_timeout(name, args):
            raise SimulatedTimeout(f"{name} 逾時（>{TOOL_TIMEOUT_SECONDS:g} 秒，快照模擬）", TOOL_TIMEOUT_SECONDS)
        simulated = self._simulated_no_data(name)
        if simulated is not None:
            return simulated
        return with_timeout(name, lambda **a: getattr(self, name)(**a))(args)


class SimulatedTimeout(TimeoutError):
    def __init__(self, message: str, seconds: float):
        super().__init__(message)
        self.seconds = seconds
