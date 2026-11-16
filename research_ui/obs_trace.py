"""Trace a report's obs-* references back to what the tool actually returned (B, 11/15).

Agent v2 drafts cite tool observations (obs-1, obs-2, …: the n-th tool call of that job) instead of snapshot
fragment ids. This module maps each cited obs to its sources using only the job's own record — the checkpoint the
worker saved (tool name, arguments, full result; decision 29). It never re-runs a tool and never uses what the model
wrote about the observation.

Per tool (B, 11/15):
- read_evidence           → the one ev- fragment it read
- search_evidence         → the ev- fragments it returned, marked "只看到摘要"
- get_financial_snapshot  → the quarters the snapshot actually returned
- get_price_window        → the trading days returned
- get_macro_snapshot      → the macro rows returned
- calculate_metrics       → traced through its inputs: each input value must appear in an earlier tool result of the
                            same job; then it follows those observations. Otherwise "計算結果，輸入未驗證".

The ev- fragments found this way are then checked with the existing rule (in the snapshot, hash matches). The
result is frozen into the report version (data["obs_map"]), so the source drawer shows the actual mapping and it
can be re-checked later.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any, Callable

from agents.tools import args_hash

UNAVAILABLE = "這個 job 的工具紀錄（checkpoint）拿不到，無法對應 obs 到來源"
SUMMARY_ONLY = "只看到摘要"
FULL_TEXT = "讀過全文"
NUMBER = re.compile(r"-?\d[\d,]*\.?\d*")


def _calls_by_role(checkpoint: dict[str, Any]) -> dict[str, list[tuple[str, dict[str, Any]]]]:
    """Every function call the model made, per role, in order: (tool name, args)."""
    out: dict[str, list[tuple[str, dict[str, Any]]]] = {}
    for role, key in (("researcher", "researcher_contents"), ("reviewer", "reviewer_contents")):
        calls = []
        for content in checkpoint.get(key) or []:
            for part in (content or {}).get("parts") or []:
                fc = (part or {}).get("function_call")
                if fc and fc.get("name"):
                    calls.append((fc["name"], fc.get("args") or {}))
        out[role] = calls
    return out


def _attach_args(observations: list[dict[str, Any]], checkpoint: dict[str, Any]) -> dict[str, dict[str, Any] | None]:
    """obs_id → the call's arguments, matched by role, tool name and args_hash (the hash the worker recorded)."""
    pool = _calls_by_role(checkpoint)
    used: set[tuple[str, int]] = set()
    found: dict[str, dict[str, Any] | None] = {}
    for o in observations:
        args = None
        for i, (name, a) in enumerate(pool.get(o.get("role") or "", [])):
            if (o.get("role"), i) in used or name != o.get("tool_name"):
                continue
            if args_hash(a) == o.get("args_hash"):
                used.add((o.get("role"), i))
                args = a
                break
        found[o["obs_id"]] = args
    return found


def _numbers(value: Any) -> list[float]:
    if isinstance(value, bool):
        return []
    if isinstance(value, (int, float)):
        return [float(value)]
    if isinstance(value, str):
        out = []
        for m in NUMBER.findall(value):
            try:
                out.append(float(m.replace(",", "")))
            except ValueError:
                pass
        return out
    if isinstance(value, dict):
        return [n for v in value.values() for n in _numbers(v)]
    if isinstance(value, list):
        return [n for v in value for n in _numbers(v)]
    return []


def _input_numbers(value: Any) -> list[float]:
    """Numeric inputs of a calculation (numbers only: labels such as price_basis or dates are not inputs)."""
    if isinstance(value, bool):
        return []
    if isinstance(value, (int, float)):
        return [float(value)]
    if isinstance(value, dict):
        return [n for v in value.values() for n in _input_numbers(v)]
    if isinstance(value, list):
        return [n for v in value for n in _input_numbers(v)]
    return []


def _same(a: float, b: float) -> bool:
    return abs(a - b) <= 1e-9 * max(1.0, abs(a), abs(b))


def _targets(o: dict[str, Any]) -> tuple[list[dict[str, Any]], str]:
    """What a non-calculation observation points at, read from its recorded result."""
    data = o.get("data")
    name = o.get("tool_name")
    if name == "read_evidence" and isinstance(data, dict) and data.get("evidence_version_id"):
        return [{"kind": "evidence", "id": data["evidence_version_id"], "seen": FULL_TEXT}], ""
    if name == "search_evidence" and isinstance(data, list):
        ids = [r["evidence_version_id"] for r in data if isinstance(r, dict) and r.get("evidence_version_id")]
        return [{"kind": "evidence", "id": i, "seen": SUMMARY_ONLY} for i in dict.fromkeys(ids)], \
            ("" if ids else "搜尋沒有回傳任何片段")
    if name == "get_financial_snapshot" and isinstance(data, dict):
        return [{"kind": "financial_snapshot", "source_id": data.get("source_id"), "snapshot_id": data.get("snapshot_id"),
                 "latest_period": data.get("latest_period"), "periods": data.get("ttm_periods") or [],
                 "period_basis": data.get("period_basis"), "content_hash": data.get("content_hash"),
                 "available_at": data.get("available_at")}], ""
    if name == "get_price_window" and isinstance(data, dict):
        return [{"kind": "price", "source_id": data.get("source_id"), "content_hash": data.get("content_hash"),
                 "trade_dates": [c.get("trade_date") for c in data.get("closes") or []],
                 "price_basis": data.get("price_basis"), "available_at": data.get("available_at")}], ""
    if name == "get_macro_snapshot" and isinstance(data, list):
        rows = [{k: r.get(k) for k in ("series_id", "observation_date", "source_id", "content_hash", "available_at")}
                for r in data if isinstance(r, dict)]
        return ([{"kind": "macro", "rows": rows}] if rows else []), ("" if rows else "總經工具沒有回傳資料")
    if data is None:
        return [], "紀錄沒有保存這次工具的完整結果"
    return [], f"{name} 的結果無法對應到來源"


def map_observations(job: dict[str, Any]) -> dict[str, Any]:
    """All observations of the job, each with what it maps to. status 'unavailable' when there is no checkpoint."""
    cp = job.get("checkpoint")
    observations = (cp or {}).get("observations")
    if not isinstance(observations, list):
        return {"status": "unavailable", "note": UNAVAILABLE, "items": {}}
    args = _attach_args(observations, cp)
    items: dict[str, dict[str, Any]] = {}
    for idx, o in enumerate(observations):
        oid = o["obs_id"]
        entry = {"obs_id": oid, "role": o.get("role"), "tool": o.get("tool_name"), "tool_status": o.get("status"),
                 "args": args.get(oid), "output_hash": o.get("output_hash"), "via": [], "targets": [], "note": ""}
        if o.get("status") != "ok":
            entry["note"] = f"工具沒有成功（{o.get('status')}{'：' + o['reason'] if o.get('reason') else ''}），沒有來源"
        elif o.get("tool_name") == "calculate_metrics":
            values = (args.get(oid) or {}).get("values")
            inputs = _input_numbers(values) if isinstance(values, dict) else []
            earlier = [p for p in observations[:idx] if p.get("status") == "ok" and p.get("tool_name") != "calculate_metrics"]
            via: list[str] = []
            missing = []
            for v in inputs:
                hit = next((p["obs_id"] for p in earlier if any(_same(v, n) for n in _numbers(p.get("data")))), None)
                if hit is None:
                    missing.append(v)
                elif hit not in via:
                    via.append(hit)
            if args.get(oid) is None:
                entry["note"] = "計算結果，輸入未驗證（紀錄找不到這次計算的輸入）"
            elif not inputs or missing:
                entry["note"] = "計算結果，輸入未驗證" + (
                    f"（{'、'.join(f'{m:g}' for m in missing)} 不在先前的工具結果中）" if missing else "（沒有數值輸入）")
            else:
                entry["via"] = via
        else:
            entry["targets"], entry["note"] = _targets(o)
        items[oid] = entry
    # calculate_metrics follows its inputs' targets (one level: inputs are never calculations, see `earlier`)
    for entry in items.values():
        if entry["via"]:
            entry["targets"] = [t for v in entry["via"] for t in items[v]["targets"]]
            if not entry["targets"]:
                entry["note"] = "計算結果，輸入未驗證（輸入來源無法對應）"
                entry["via"] = []
    return {"status": "ok", "note": "", "items": items}


def check_evidence(read: Callable[[str], dict[str, Any]], ev_id: str) -> dict[str, Any]:
    """The existing fragment rule: the ev- id is in the snapshot and its paragraph hash matches."""
    out = read(ev_id)
    if out.get("status") != "ok":
        return {"exists": False, "hash_match": None, "data": None}
    d = out["data"]
    para = d.get("paragraph") or ""
    return {"exists": True, "hash_match": hashlib.sha256(para.encode("utf-8")).hexdigest() == d.get("content_hash"),
            "data": d}


def obs_traced(entry: dict[str, Any] | None, ev_ok: Callable[[str], bool]) -> bool:
    """An obs counts as traced when it maps to at least one fragment that passes the rule, or to snapshot data."""
    if not entry:
        return False
    return any((t["kind"] != "evidence") or ev_ok(t["id"]) for t in entry["targets"])


def claim_trace(claims: list[dict[str, Any]], obs_map: dict[str, Any],
                read: Callable[[str], dict[str, Any]]) -> tuple[str, str]:
    """Evidence half of source_traceable for one report (B, 11/09 and 11/15).

    - a cited ev- fragment not in the snapshot → missing; hash mismatch → conflict (unchanged rule)
    - a cited obs that maps to nothing that passes the rule → missing ("缺來源"); fragments it maps to are
      checked with the same rule
    - a fact claim with no reference at all → missing; inference / unknown claims may cite nothing
    - obs cited but the job record is unavailable → not_run ("無法判定"), the only such case
    """
    checked: dict[str, dict[str, Any]] = {}

    def ev(ev_id: str) -> dict[str, Any]:
        if ev_id not in checked:
            checked[ev_id] = check_evidence(read, ev_id)
        return checked[ev_id]

    def ev_ok(ev_id: str) -> bool:
        r = ev(ev_id)
        return r["exists"] and r["hash_match"] is not False

    conflict, ev_missing, missing, unrun = [], [], [], []
    items = obs_map.get("items") or {}
    for c in claims:
        cid = c.get("claim_id") or c.get("id") or "?"
        refs = c.get("evidence_refs") or []
        if not refs and c.get("kind") == "fact":
            missing.append(f"事實主張 {cid} 沒有引用來源")
        for ref in refs:
            ref = str(ref)
            if ref.startswith("ev-"):
                r = ev(ref)
                if r["exists"] and r["hash_match"] is False:
                    conflict.append(ref)
                elif not r["exists"]:
                    ev_missing.append(ref)
            elif ref.startswith("obs-"):
                if obs_map.get("status") != "ok":
                    unrun.append(ref)
                    continue
                entry = items.get(ref)
                for t in (entry or {}).get("targets", []):
                    if t["kind"] == "evidence":
                        r = ev(t["id"])
                        if r["exists"] and r["hash_match"] is False:
                            conflict.append(f"{ref}→{t['id']}")
                if not obs_traced(entry, ev_ok):
                    why = "這個 job 沒有這個工具觀察" if entry is None else (entry["note"] or "對不到片段或快照")
                    missing.append(f"{ref} 對不到來源（{why}）")
    # wording of the two pre-existing outcomes kept as before (reports that cite ev- directly read the same)
    if conflict:
        via_obs = [x for x in dict.fromkeys(conflict) if "→" in x]
        return "conflict", "引用的片段 hash 不符" + ("：" + "、".join(via_obs) if via_obs else "")
    if ev_missing or missing:
        parts = (["引用的片段不在快照中：" + "、".join(dict.fromkeys(ev_missing))] if ev_missing else []) + \
            list(dict.fromkeys(missing))
        return "missing", "；".join(parts)
    if unrun:
        return "not_run", f"{UNAVAILABLE}：" + "、".join(dict.fromkeys(unrun))
    return "pass", ""
