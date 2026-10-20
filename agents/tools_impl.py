"""agents/tools_impl.py — W03-B 六工具實作（V1.4，對齊 data/tool-contracts.json v1.1-w02）

規則
----
- 回傳頂層固定為 status / tool / reason / data（與 agents/tools.py dispatch 一致）。
- 嚴格防前視：只回傳 cutoff / end_at 之前可得的資料。
- 可得時間依據 available_at_basis：
    official             財報＝MOPS 發言時間；總經＝官方發布時間
    rule_close_1730      股價＝交易日 17:30 +08:00
    captured_at_fallback 官方時間未知，以 captured_at 判定；兩者皆無視為不可得
- 缺值保持 null 並附 missing_reason，不補 0。
- 不產生任何來源網址或 hash：快照沒有就回傳 null。
- 參數格式檢查由 agents/tools.py validate_tool_call 負責；本檔再做最低限度防呆，
  讓直接呼叫（測試、snapshot.py）也不會崩潰。
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

try:
    from agents.calculator import execute_calculation
except ImportError:  # 以 agents/ 為工作目錄執行時
    from calculator import execute_calculation  # type: ignore

CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
SNAPSHOT_PATH = PROJECT_ROOT / "data" / "financial-snapshots.json"
MACRO_CSV = PROJECT_ROOT / "data" / "manual" / "macro.csv"

RESEARCH_TICKERS = ("2330", "2317", "2454")
ALL_TICKERS = RESEARCH_TICKERS + ("2379", "3034")
# 白名單只在 agents/tools.py 維護一處（組長核定）；此處直接引用，避免兩份不一致
try:
    from agents.tools import MACRO_SERIES_WHITELIST
except ImportError:  # 以 agents/ 為工作目錄執行時
    try:
        from tools import MACRO_SERIES_WHITELIST  # type: ignore
    except ImportError:
        MACRO_SERIES_WHITELIST = ("CPIAUCSL", "FEDFUNDS")
PRICE_SESSIONS = (1, 5, 20)
PRICE_AVAILABLE_TIME = "T17:30:00+08:00"
EVIDENCE_MAX_CHARS = 1200
QUERY_MAX_CHARS = 200


# -------------------------------------------------------------------------
# 共用
# -------------------------------------------------------------------------
def _resp(tool: str, status: str, data: Any = None, reason: str | None = None) -> dict[str, Any]:
    """固定回傳結構；非 ok 時 data 一律為 None。"""
    return {"status": status, "tool": tool, "reason": reason, "data": data if status == "ok" else None}


def _params(args: tuple[Any, ...], kwargs: dict[str, Any], names: tuple[str, ...]) -> dict[str, Any]:
    """相容三種呼叫：fn({...})、fn(**kwargs)、fn(位置參數...)（research_ui/comparison.py 使用位置參數）。"""
    if args and isinstance(args[0], dict) and len(args) == 1:
        return args[0]
    params = dict(zip(names, args))
    params.update(kwargs)
    return params


def _parse_iso(value: str) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError(f"時間缺少時區：{value}")
    return parsed


def _load_snapshots() -> dict[str, Any]:
    if not SNAPSHOT_PATH.exists():
        return {"evidences": [], "financials": {}, "macro": [], "prices": {}, "source_manifest": {}}
    with open(SNAPSHOT_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _raw_file(snap: dict[str, Any], dataset: str, ticker: str | None) -> dict[str, Any]:
    """原始 FinMind 檔紀錄（sha256、captured_at）；找不到回傳空 dict。"""
    for raw in snap.get("source_manifest", {}).get("raw_files", []):
        if raw.get("dataset") == dataset and raw.get("data_id") == ticker:
            return raw
    return {}


@lru_cache(maxsize=1)
def _macro_csv_hash() -> str | None:
    return hashlib.sha256(MACRO_CSV.read_bytes()).hexdigest() if MACRO_CSV.exists() else None


def _effective_available(row: dict[str, Any]) -> tuple[datetime | None, str | None, str | None]:
    """回傳 (可得時間, available_at 字串, basis)。兩個時間皆無 → (None, None, None)。"""
    if row.get("available_at"):
        return _parse_iso(row["available_at"]), row["available_at"], "official"
    if row.get("captured_at"):
        return _parse_iso(row["captured_at"]), row["captured_at"], "captured_at_fallback"
    return None, None, None


def _next_period(period: str) -> str:
    year, q = int(period[:4]), int(period[-1])
    return f"{year + 1}Q1" if q == 4 else f"{year}Q{q + 1}"


def _consecutive(periods: list[str]) -> bool:
    return all(_next_period(a) == b for a, b in zip(periods, periods[1:]))


# -------------------------------------------------------------------------
# 工具 1：search_evidence（Researcher）
# -------------------------------------------------------------------------
def search_evidence(*args: Any, **kwargs: Any) -> dict[str, Any]:
    tool = "search_evidence"
    p = _params(args, kwargs, ("ticker", "query", "cutoff", "limit"))
    ticker, query, cutoff = p.get("ticker", ""), p.get("query", "") or "", p.get("cutoff", "")

    if ticker not in RESEARCH_TICKERS:
        return _resp(tool, "invalid_input", reason=f"search_evidence 只限研究主體 {RESEARCH_TICKERS}，收到 {ticker}")
    if len(query) > QUERY_MAX_CHARS:
        return _resp(tool, "invalid_input", reason=f"query 超過 {QUERY_MAX_CHARS} 字")
    try:
        limit = int(p.get("limit", 5))
        cutoff_dt = _parse_iso(cutoff)
    except (TypeError, ValueError) as exc:
        return _resp(tool, "invalid_input", reason=f"參數格式錯誤：{exc}")
    if not 1 <= limit <= 5:
        return _resp(tool, "invalid_input", reason="limit 只限 1 至 5")

    words = [w for w in query.split() if w]
    rows = []
    for ev in _load_snapshots().get("evidences", []):
        if ev.get("ticker") != ticker:
            continue
        when, available_at, basis = _effective_available(ev)
        if when is None or when > cutoff_dt:
            continue
        haystack = " ".join(str(ev.get(k) or "") for k in ("title", "abstract", "paragraph"))
        if words and not any(w in haystack for w in words):
            continue
        rows.append({
            "source_id": ev.get("source_id"),
            "evidence_version_id": ev.get("evidence_version_id"),
            "ticker": ticker,
            "title": ev.get("title"),
            "published_at": ev.get("published_at"),
            "captured_at": ev.get("captured_at"),
            "available_at": available_at,
            "available_at_basis": basis,
            "content_hash": ev.get("content_hash"),
            "abstract": ev.get("abstract"),
        })

    if not rows:
        return _resp(tool, "no_data", reason="指定 cutoff 前查無相符索引快照")
    return _resp(tool, "ok", rows[:limit])


# -------------------------------------------------------------------------
# 工具 2：read_evidence（Researcher / Reviewer）
# -------------------------------------------------------------------------
def read_evidence(*args: Any, **kwargs: Any) -> dict[str, Any]:
    tool = "read_evidence"
    evidence_version_id = _params(args, kwargs, ("evidence_version_id",)).get("evidence_version_id", "")

    for ev in _load_snapshots().get("evidences", []):
        if ev.get("evidence_version_id") != evidence_version_id:
            continue
        paragraph = ev.get("paragraph")
        if paragraph is None:
            return _resp(tool, "unreadable", reason="來源正文不可讀（paragraph 為 null），不得補造內容")
        _, available_at, basis = _effective_available(ev)
        return _resp(tool, "ok", {
            "evidence_version_id": ev.get("evidence_version_id"),
            "source_id": ev.get("source_id"),
            "paragraph": str(paragraph)[:EVIDENCE_MAX_CHARS],
            "source_url": ev.get("source_url"),          # 快照沒有就是 None，不填通用網址
            "content_hash": ev.get("content_hash"),
            "available_at": available_at,
            "available_at_basis": basis,
        })
    return _resp(tool, "no_data", reason=f"查無指定片段: {evidence_version_id}")


# -------------------------------------------------------------------------
# 工具 3：get_financial_snapshot（Researcher / Reviewer）
# -------------------------------------------------------------------------
def _ttm(rows: list[dict[str, Any]], field: str) -> tuple[float | None, str | None]:
    """四連續單季加總；任何條件不符回傳 (None, 原因)。"""
    if len(rows) < 4:
        return None, f"可得單季季數不足 4 季（僅 {len(rows)} 季），禁止年化推估"
    last4 = rows[-4:]
    periods = [r.get("period") for r in last4]
    if not _consecutive(periods):
        return None, f"最近四季不連續：{periods}"
    if any(r.get("period_basis") != "single_quarter" for r in last4):
        return None, "最近四季並非皆為 single_quarter"
    missing = [r["period"] for r in last4 if r.get(field) is None]
    if missing:
        return None, f"{field} 於 {missing} 為 null"
    if field == "eps":
        unverified = [r["period"] for r in last4 if r.get("eps_source") == "unverified"]
        if unverified:
            return None, f"EPS 於 {unverified} 為 unverified，不得作為正式 TTM"
    return round(sum(r[field] for r in last4), 2), None


def get_financial_snapshot(*args: Any, **kwargs: Any) -> dict[str, Any]:
    tool = "get_financial_snapshot"
    p = _params(args, kwargs, ("ticker", "cutoff"))
    ticker, cutoff = p.get("ticker", ""), p.get("cutoff", "")

    if ticker not in ALL_TICKERS:
        return _resp(tool, "invalid_input", reason=f"ticker 只限 {ALL_TICKERS}，收到 {ticker}")
    try:
        cutoff_dt = _parse_iso(cutoff)
    except ValueError as exc:
        return _resp(tool, "invalid_input", reason=f"cutoff 格式錯誤：{exc}")

    snap = _load_snapshots()
    company = snap.get("financials", {}).get(ticker)
    if not company:
        return _resp(tool, "no_data", reason=f"查無 {ticker} 財務資料")

    rows = []
    for q in company.get("quarters", []):
        when, _, _ = _effective_available(q)
        if when is not None and when <= cutoff_dt:
            rows.append(q)
    rows.sort(key=lambda r: r["period"])
    if not rows:
        return _resp(tool, "no_data", reason="截至 cutoff 無可得財務資料")

    latest = rows[-1]
    eps_ttm, eps_reason = _ttm(rows, "eps")
    fcf_ttm, fcf_reason = _ttm(rows, "free_cash_flow")
    reasons = [r for r in dict.fromkeys([eps_reason, fcf_reason]) if r]
    _, available_at, basis = _effective_available(latest)
    raw = _raw_file(snap, "TaiwanStockFinancialStatements", ticker)

    return _resp(tool, "ok", {
        "ticker": ticker,
        "company_name": company.get("company_name", ticker),
        "statement_basis": company.get("statement_basis", "consolidated"),
        "currency": company.get("currency", "TWD"),
        "unit": "100m",
        "latest_period": latest.get("period"),
        "period_basis": latest.get("period_basis"),
        "ttm_periods": [r["period"] for r in rows[-4:]] if eps_ttm is not None or fcf_ttm is not None else None,
        "source_id": latest.get("source_id"),
        "snapshot_id": latest.get("snapshot_id"),
        "content_hash": latest.get("content_hash"),
        "missing_reason": "；".join(reasons) if reasons else None,
        "metrics": {
            "revenue_single_q": latest.get("revenue"),
            "operating_income_single_q": latest.get("operating_income"),
            "net_income_single_q": latest.get("net_income"),
            "operating_cash_flow_single_q": latest.get("operating_cash_flow"),
            "capital_expenditure_single_q": latest.get("capital_expenditure"),
            "free_cash_flow_single_q": latest.get("free_cash_flow"),
            "eps_single_q": latest.get("eps"),
            "eps_source": latest.get("eps_source"),
            "bvps": latest.get("bvps"),
            "eps_ttm": eps_ttm,
            "fcf_ttm": fcf_ttm,
            "shares_outstanding_m": latest.get("shares_outstanding"),
            "net_debt": latest.get("net_debt"),
        },
        "available_at": available_at,
        "available_at_basis": basis,
        "captured_at": raw.get("captured_at"),
    })


# -------------------------------------------------------------------------
# 工具 4：get_macro_snapshot（Researcher / Reviewer）
# -------------------------------------------------------------------------
def get_macro_snapshot(*args: Any, **kwargs: Any) -> dict[str, Any]:
    tool = "get_macro_snapshot"
    p = _params(args, kwargs, ("cutoff", "series_ids"))
    cutoff, series_ids = p.get("cutoff", ""), p.get("series_ids") or []

    if not isinstance(series_ids, list) or not 1 <= len(series_ids) <= 5:
        return _resp(tool, "invalid_input", reason="series_ids 需為 1 至 5 項的陣列")
    unauthorized = [s for s in series_ids if s not in MACRO_SERIES_WHITELIST]
    if unauthorized:
        return _resp(tool, "invalid_input", reason=f"series {unauthorized} 不在已核准白名單 {MACRO_SERIES_WHITELIST}")
    try:
        cutoff_dt = _parse_iso(cutoff)
    except ValueError as exc:
        return _resp(tool, "invalid_input", reason=f"cutoff 格式錯誤：{exc}")

    rows = []
    for m in _load_snapshots().get("macro", []):
        if m.get("series_id") not in series_ids:
            continue
        when, available_at, basis = _effective_available(m)
        if when is None or when > cutoff_dt:
            continue
        rows.append({
            "series_id": m["series_id"],
            "indicator": m.get("indicator"),
            "observation_date": m.get("observation_date"),
            "value": m.get("value"),
            "unit": m.get("unit"),
            "available_at": available_at,
            "available_at_basis": basis,
            "source_id": m.get("source_id", "fred_macro"),
            "content_hash": m.get("content_hash") or _macro_csv_hash(),
            "vintage": m.get("vintage"),
            "vintage_missing_reason": None if m.get("vintage") else "只有現行下載值，無歷史 vintage",
        })

    if not rows:
        return _resp(tool, "no_data", reason="指定指標於 cutoff 前無數據")
    return _resp(tool, "ok", rows)


# -------------------------------------------------------------------------
# 工具 5：get_price_window（Researcher）
# -------------------------------------------------------------------------
def get_price_window(*args: Any, **kwargs: Any) -> dict[str, Any]:
    tool = "get_price_window"
    p = _params(args, kwargs, ("ticker", "end_at", "sessions"))
    ticker, end_at = p.get("ticker", ""), p.get("end_at", "")

    if ticker not in ALL_TICKERS:
        return _resp(tool, "invalid_input", reason=f"ticker 只限 {ALL_TICKERS}，收到 {ticker}")
    try:
        sessions = int(p.get("sessions", 1))
        end_dt = _parse_iso(end_at)
    except (TypeError, ValueError) as exc:
        return _resp(tool, "invalid_input", reason=f"參數格式錯誤：{exc}")
    if sessions not in PRICE_SESSIONS:
        return _resp(tool, "invalid_input", reason="sessions 只限 1, 5, 20")

    snap = _load_snapshots()
    rows = []
    for row in snap.get("prices", {}).get(ticker, []):
        available_at = row["trade_date"] + PRICE_AVAILABLE_TIME
        if _parse_iso(available_at) <= end_dt and row.get("close") is not None:
            rows.append({"trade_date": row["trade_date"], "close_price": row["close"],
                         "available_at": available_at, "available_at_basis": "rule_close_1730"})
    rows.sort(key=lambda r: r["trade_date"])
    if len(rows) < sessions:
        return _resp(tool, "no_data", reason="可得交易日不足，或指定區間停牌／休市")

    window = rows[-sessions:]
    raw = _raw_file(snap, "TaiwanStockPrice", ticker)
    return _resp(tool, "ok", {
        "ticker": ticker,
        "currency": "TWD",
        "unit": "TWD/share",
        "price_basis": "raw_close",
        "sessions": sessions,
        "source_id": "finmind_price",
        "content_hash": raw.get("sha256"),
        "available_at": window[-1]["available_at"],
        "available_at_basis": "rule_close_1730",
        "captured_at": raw.get("captured_at"),
        "closes": window,
    })


# -------------------------------------------------------------------------
# 工具 6：calculate_metrics（Researcher / Reviewer）
# -------------------------------------------------------------------------
def calculate_metrics(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """確定性運算入口，委派給 agents.calculator.execute_calculation。"""
    p = _params(args, kwargs, ("operation", "values", "evidence_refs"))
    return execute_calculation(operation=p.get("operation", ""), values=p.get("values") or {},
                               evidence_refs=p.get("evidence_refs") or [])
