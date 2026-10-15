"""Six-tool contract V1.2 (handbook ch.02 「六工具契約」, ch.04 F02).

This module owns the declarations, role permissions and input validation.
The tool bodies are W03-B's work: until B registers an implementation, every
tool returns a fixed `no_data` result instead of inventing values.

There are exactly six tools. peer_comparison is an operation of
calculate_metrics, not a seventh tool.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from typing import Any, Callable
from zoneinfo import ZoneInfo

from .contract import COMPARISON_ONLY_TICKERS, RESEARCH_TICKERS

TOOLS_VERSION = "tools-v12.0"

CALC_OPERATIONS = ("growth_rate", "simple_return", "pe_ttm", "dcf_scenario", "peer_comparison")
PEER_METRICS = ("pe_ttm", "pb", "revenue_yoy_quarter", "fcf", "dcf_gap")
PEER_SUBJECT = "2454"
PEER_COMPARATORS = ("2379", "3034", "2330")  # 2330 = industry reference, excluded from peer stats
INDUSTRY_REFERENCE = ("2330",)
MAX_PEER_COMPANIES = 4
PRICE_SESSIONS = (1, 5, 20)
# Locked 2026-10-15 from B's approved snapshot (data/financial-snapshots.json → macro, FRED).
# ch.02 also lists a Taiwan market indicator; add it here once B provides an approved series.
MACRO_SERIES_WHITELIST: tuple[str, ...] = ("CPIAUCSL", "FEDFUNDS")
ALL_TICKERS = RESEARCH_TICKERS + COMPARISON_ONLY_TICKERS

_TICKER = {"type": "string", "enum": list(RESEARCH_TICKERS)}
_ANY_TICKER = {"type": "string", "enum": list(ALL_TICKERS)}
_CUTOFF = {"type": "string", "description": "ISO-8601 with timezone; only data available at or before it"}

TOOL_DECLARATIONS: list[dict[str, Any]] = [
    {
        "name": "search_evidence",
        "description": "Search the approved, already-ingested source index (filings, announcements, macro). "
                       "Returns source ids, titles, published/available time and a short abstract. No web crawling.",
        "parameters": {
            "type": "object",
            "properties": {
                "ticker": _TICKER,
                "query": {"type": "string", "maxLength": 200},
                "cutoff": _CUTOFF,
                "limit": {"type": "integer", "minimum": 1, "maximum": 5},
            },
            "required": ["ticker", "query", "cutoff", "limit"],
        },
    },
    {
        "name": "read_evidence",
        "description": "Read one immutable evidence fragment from this job's snapshot (≤1,200 Chinese chars) "
                       "with paragraph, hash and exact source link. Unknown id returns no_data.",
        "parameters": {
            "type": "object",
            "properties": {"evidence_version_id": {"type": "string", "maxLength": 128}},
            "required": ["evidence_version_id"],
        },
    },
    {
        "name": "get_financial_snapshot",
        "description": "FinMind-based financial values available at cutoff: revenue, net income, TTM EPS, FCF, "
                       "shares, net debt. Each value carries period, basis, currency, unit, source and available_at; "
                       "missing values are null with a reason.",
        "parameters": {
            "type": "object",
            "properties": {"ticker": _ANY_TICKER, "cutoff": _CUTOFF},
            "required": ["ticker", "cutoff"],
        },
    },
    {
        "name": "get_macro_snapshot",
        "description": "Approved macro snapshot (whitelisted series only) with observation period and "
                       "release/revision time.",
        "parameters": {
            "type": "object",
            "properties": {
                "cutoff": _CUTOFF,
                "series_ids": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 5},
            },
            "required": ["cutoff", "series_ids"],
        },
    },
    {
        "name": "get_price_window",
        "description": "Taiwan-stock closing prices for the last 1, 5 or 20 trading sessions ending at end_at, "
                       "with raw/adjusted basis. Missing or suspended = no_data.",
        "parameters": {
            "type": "object",
            "properties": {
                "ticker": _ANY_TICKER,
                "end_at": _CUTOFF,
                "sessions": {"type": "integer", "enum": list(PRICE_SESSIONS)},
            },
            "required": ["ticker", "end_at", "sessions"],
        },
    },
    {
        "name": "calculate_metrics",
        "description": "Deterministic calculations only: growth_rate, simple_return, pe_ttm, dcf_scenario, "
                       "peer_comparison (2454 vs 2379/3034, 2330 as industry reference, max 4 companies). "
                       "Values must cite evidence_refs; invalid inputs return null with a reason.",
        "parameters": {
            "type": "object",
            "properties": {
                "operation": {"type": "string", "enum": list(CALC_OPERATIONS)},
                "values": {"type": "object"},
                "evidence_refs": {"type": "array", "items": {"type": "string"}, "maxItems": 20},
            },
            "required": ["operation", "values", "evidence_refs"],
        },
    },
]

TOOL_NAMES = tuple(t["name"] for t in TOOL_DECLARATIONS)
ROLE_TOOLS = {
    "researcher": TOOL_NAMES,
    "reviewer": ("read_evidence", "get_financial_snapshot", "get_macro_snapshot", "calculate_metrics"),
}

# Free text (query, labels) must not look like a URL, file path, SQL or shell fragment.
_FORBIDDEN = re.compile(
    r"([a-z][a-z0-9+.-]*://|\bwww\.|\bfile:|\.\.[/\\]|(^|\s)(/[\w.-]|~/)|[a-z]:\\|\\\\"
    r"|[`;|]|\$\(|&&|--|/\*|\bunion\s+select\b|\bdrop\s+table\b|\bselect\s+\*|\bdelete\s+from\b|\binsert\s+into\b)",
    re.IGNORECASE,
)
# Identifiers (evidence ids, snapshot ids, series ids, method versions) must be plain tokens.
_ID = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
TW = ZoneInfo("Asia/Taipei")


class ToolInputError(ValueError):
    pass


def _parse_time(label: str, value: Any) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise ToolInputError(f"{label} 需為 ISO-8601 時間") from exc
    if parsed.tzinfo is None:
        raise ToolInputError(f"{label} 需含時區")
    return parsed


def _check_not_after_cutoff(label: str, value: Any, job_cutoff: str | None) -> None:
    """No look-ahead: tool times may never be later than the job's cutoff_at."""

    when = _parse_time(label, value)
    if job_cutoff and when > _parse_time("job.cutoff_at", job_cutoff):
        raise ToolInputError(f"{label}={value} 晚於本 job 的 cutoff {job_cutoff}，不可使用之後的資料")


def args_hash(args: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(args, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]


def _walk_strings(value: Any):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for k, v in value.items():
            yield str(k)
            yield from _walk_strings(v)
    elif isinstance(value, list):
        for v in value:
            yield from _walk_strings(v)


def _check_type(name: str, key: str, value: Any, spec: dict[str, Any]) -> None:
    t = spec.get("type")
    ok = {
        "string": isinstance(value, str),
        "integer": isinstance(value, int) and not isinstance(value, bool),
        "array": isinstance(value, list),
        "object": isinstance(value, dict),
    }.get(t, True)
    if not ok:
        raise ToolInputError(f"{name}.{key} 型別應為 {t}")
    if "enum" in spec and value not in spec["enum"]:
        raise ToolInputError(f"{name}.{key}={value!r} 不在允許值 {spec['enum']}")
    if t == "string" and "maxLength" in spec and len(value) > spec["maxLength"]:
        raise ToolInputError(f"{name}.{key} 超過 {spec['maxLength']} 字元")
    if t == "integer":
        if "minimum" in spec and value < spec["minimum"] or "maximum" in spec and value > spec["maximum"]:
            raise ToolInputError(f"{name}.{key}={value} 超出範圍")
    if t == "array":
        if "maxItems" in spec and len(value) > spec["maxItems"]:
            raise ToolInputError(f"{name}.{key} 最多 {spec['maxItems']} 項")
        if "minItems" in spec and len(value) < spec["minItems"]:
            raise ToolInputError(f"{name}.{key} 至少 {spec['minItems']} 項")


def _validate_peer_comparison(values: dict[str, Any], job_cutoff: str | None) -> None:
    subject = values.get("subject")
    comparators = values.get("comparators") or []
    if subject != PEER_SUBJECT:
        raise ToolInputError(f"peer_comparison 主體只限 {PEER_SUBJECT}")
    if not isinstance(comparators, list) or not comparators or not all(isinstance(c, str) for c in comparators):
        raise ToolInputError("peer_comparison.comparators 必填，且為股票代號字串陣列")
    if len(set(comparators)) != len(comparators):
        raise ToolInputError("peer_comparison.comparators 不可重複")
    if 1 + len(comparators) > MAX_PEER_COMPANIES:
        raise ToolInputError(f"peer_comparison 最多 {MAX_PEER_COMPANIES} 家公司（含主體）")
    bad = [c for c in comparators if c not in PEER_COMPARATORS]
    if bad:
        raise ToolInputError(f"比較標的只限 {PEER_COMPARATORS}，收到 {bad}")
    for key in ("price_as_of", "cutoff", "method_version"):
        if not values.get(key):
            raise ToolInputError(f"peer_comparison.{key} 必填（同一報價基準日）")
    if not isinstance(values["method_version"], str) or not _ID.match(values["method_version"]):
        raise ToolInputError("peer_comparison.method_version 格式錯誤")
    _check_not_after_cutoff("peer_comparison.cutoff", values["cutoff"], job_cutoff)
    price_as_of = str(values["price_as_of"])
    if not _DATE.match(price_as_of):
        raise ToolInputError("peer_comparison.price_as_of 需為 YYYY-MM-DD")
    limit = _parse_time("cutoff", job_cutoff or values["cutoff"]).astimezone(TW).date()
    if datetime.fromisoformat(price_as_of).date() > limit:
        raise ToolInputError(f"peer_comparison.price_as_of={price_as_of} 晚於 cutoff 當日")
    metrics = values.get("metrics") or []
    bad_metrics = [m for m in metrics if m not in PEER_METRICS]
    if not metrics or bad_metrics:
        raise ToolInputError(f"peer_comparison.metrics 只限 {PEER_METRICS}")
    snaps = values.get("snapshot_ids")
    if not isinstance(snaps, dict) or set(snaps) != {subject, *comparators}:
        raise ToolInputError("peer_comparison.snapshot_ids 需為每家公司各一個快照 id")
    if not all(isinstance(v, str) and _ID.match(v) for v in snaps.values()):
        raise ToolInputError("peer_comparison.snapshot_ids 的值格式錯誤")


def validate_tool_call(role: str, name: str, args: dict[str, Any], job_cutoff: str | None = None) -> dict[str, Any]:
    """Validate a model-proposed call. Raises ToolInputError; returns the args unchanged.

    `job_cutoff` is the job's cutoff_at; any tool time after it is refused (no look-ahead).
    """

    if name not in TOOL_NAMES:
        raise ToolInputError(f"未知工具 {name}；本系統只有六個工具")
    if name not in ROLE_TOOLS.get(role, ()):
        raise ToolInputError(f"{role} 無權使用 {name}；需要時以 claim_id/required_evidence 退回 Researcher")
    if not isinstance(args, dict):
        raise ToolInputError("工具參數必須是物件")
    decl = next(t for t in TOOL_DECLARATIONS if t["name"] == name)
    props, required = decl["parameters"]["properties"], decl["parameters"]["required"]
    extra = set(args) - set(props)
    if extra:
        raise ToolInputError(f"{name} 不接受欄位 {sorted(extra)}")
    missing = [k for k in required if k not in args or args[k] is None]
    if missing:
        raise ToolInputError(f"{name} 缺少欄位 {missing}")
    for key, value in args.items():
        _check_type(name, key, value, props[key])
    for s in _walk_strings(args):
        if _FORBIDDEN.search(s):
            raise ToolInputError(f"{name} 參數含 URL/路徑/SQL/指令字樣，拒絕執行")
    for key in ("cutoff", "end_at"):
        if key in args:
            _check_not_after_cutoff(f"{name}.{key}", args[key], job_cutoff)
    if name == "read_evidence" and not _ID.match(args["evidence_version_id"]):
        raise ToolInputError("evidence_version_id 格式錯誤")
    if name == "get_macro_snapshot":
        bad = [s for s in args["series_ids"] if not isinstance(s, str) or s not in MACRO_SERIES_WHITELIST]
        if bad:
            raise ToolInputError(f"series {bad} 不在已核准白名單（白名單待 W02 與 B 鎖定）")
    if name == "calculate_metrics" and args["operation"] == "peer_comparison":
        _validate_peer_comparison(args["values"], job_cutoff)
    return args


ToolImpl = Callable[[dict[str, Any]], dict[str, Any]]
_REGISTRY: dict[str, ToolImpl] = {}


def register_tool(name: str, impl: ToolImpl) -> None:
    """B registers the real implementations here (W03-B)."""

    if name not in TOOL_NAMES:
        raise ValueError(f"只能註冊六工具之一：{TOOL_NAMES}")
    _REGISTRY[name] = impl


def dispatch(role: str, name: str, args: dict[str, Any], job_cutoff: str | None = None) -> dict[str, Any]:
    """Validate then run. Validation failures and tool crashes come back as fixed results
    the model can react to (retry another tool or stop), never as an exception."""

    try:
        validate_tool_call(role, name, args, job_cutoff)
    except ToolInputError as exc:
        return {"status": "invalid_input", "tool": name, "reason": str(exc), "data": None}
    impl = _REGISTRY.get(name)
    if impl is None:
        return {"status": "no_data", "tool": name, "reason": "工具實作待 W03-B 註冊", "data": None}
    try:
        result = impl(args)
    except Exception as exc:  # noqa: BLE001 - a broken tool must not crash the job
        return {"status": "tool_error", "tool": name, "reason": f"{type(exc).__name__}: {exc}"[:300], "data": None}
    if not isinstance(result, dict) or "status" not in result:
        return {"status": "tool_error", "tool": name, "reason": "工具回傳格式錯誤", "data": None}
    return result


def contract_document() -> dict[str, Any]:
    """Machine-readable contract written to contracts/tools-v12.json."""

    return {
        "tools_version": TOOLS_VERSION,
        "tool_count": len(TOOL_NAMES),
        "role_tools": {k: list(v) for k, v in ROLE_TOOLS.items()},
        "calculate_metrics_operations": list(CALC_OPERATIONS),
        "peer_comparison": {
            "subject": PEER_SUBJECT,
            "allowed_comparators": list(PEER_COMPARATORS),
            "industry_reference_excluded_from_peer_stats": list(INDUSTRY_REFERENCE),
            "max_companies_including_subject": MAX_PEER_COMPANIES,
            "metrics": list(PEER_METRICS),
            "required_values": ["subject", "comparators", "price_as_of", "cutoff", "snapshot_ids",
                                "metrics", "method_version"],
            "llm_jobs_for_comparators": 0,
        },
        "fixed_result_shapes": {
            "invalid_input": {"status": "invalid_input", "tool": "str", "reason": "str", "data": None},
            "no_data": {"status": "no_data", "tool": "str", "reason": "str", "data": None},
            "tool_error": {"status": "tool_error", "tool": "str", "reason": "str", "data": None},
        },
        "declarations": TOOL_DECLARATIONS,
        "implementation_status": {name: ("registered" if name in _REGISTRY else "pending_W03-B") for name in TOOL_NAMES},
    }
