"""agents/tools_impl.py
W03-B / W06 重構版: 6 大工具標準實作模組。
嚴格對齊 V1.2 工具契約、真實 2026 公開財務與行情快照：
- 嚴格 No Look-Ahead 防前視
- 缺值保持 null，嚴禁補 0
- 2330 僅作為產業參照，絕不計入同業平均
- 支援解包調用與字典調用雙重相容
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    from agents.calculator import execute_calculation
except ImportError:
    from calculator import execute_calculation  # type: ignore

CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent

CANDIDATE_PATHS = [
    PROJECT_ROOT / "data" / "financial-snapshots.json",
    PROJECT_ROOT / "financial-snapshots.json",
    CURRENT_DIR / "data" / "financial-snapshots.json",
    CURRENT_DIR / "financial-snapshots.json",
    Path("data/financial-snapshots.json"),
    Path("financial-snapshots.json"),
]

MACRO_SERIES_WHITELIST = ["CPIAUCSL", "FEDFUNDS", "UNRATE", "GDP", "DGS10", "TWII"]


def _resolve_snapshot_path() -> Path | None:
    for p in CANDIDATE_PATHS:
        if p.exists():
            return p
    return None


def _load_snapshots() -> dict[str, Any]:
    snap_path = _resolve_snapshot_path()
    if snap_path is None:
        return {"evidences": [], "financials": {}, "macro": [], "prices": {}}
    with open(snap_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _parse_iso(dt_str: str) -> datetime:
    return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))


# -------------------------------------------------------------------------
# 工具 1: search_evidence
# -------------------------------------------------------------------------
def search_evidence(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """查詢已入庫快照之公開文件索引 (Researcher 專用)"""
    params = args[0] if args and isinstance(args[0], dict) else kwargs
    ticker = params.get("ticker", "")
    query = params.get("query", "")
    cutoff = params.get("cutoff", "")
    limit = int(params.get("limit", 5))

    if ticker not in ("2330", "2317", "2454", "2379", "3034"):
        return {"status": "invalid_input", "tool": "search_evidence", "reason": f"未授權研究標的: {ticker}", "data": None}

    try:
        cutoff_dt = _parse_iso(cutoff)
    except Exception as exc:
        return {"status": "invalid_input", "tool": "search_evidence", "reason": f"cutoff 格式錯誤: {exc}", "data": None}

    snapshots = _load_snapshots()
    matches = []

    for ev in snapshots.get("evidences", []):
        if ev.get("ticker") == ticker:
            avail_dt = _parse_iso(ev["available_at"])
            if avail_dt <= cutoff_dt:
                query_words = [w for w in query.strip().split() if w]
                title = ev.get("title", "")
                abstract = ev.get("abstract", "")
                paragraph = ev.get("paragraph", "")
                if not query_words or any(word in title or word in abstract or word in paragraph for word in query_words):
                    matches.append({
                        "source_id": ev.get("source_id"),
                        "evidence_version_id": ev.get("evidence_version_id"),
                        "ticker": ticker,
                        "title": title,
                        "published_at": ev.get("published_at"),
                        "captured_at": ev.get("captured_at"),
                        "available_at": ev.get("available_at"),
                        "content_hash": ev.get("content_hash"),
                        "abstract": abstract
                    })

    if not matches:
        return {"status": "no_data", "tool": "search_evidence", "reason": "指定 cutoff 前查無相符索引快照", "data": None}

    return {"status": "ok", "tool": "search_evidence", "data": matches[:limit]}


# -------------------------------------------------------------------------
# 工具 2: read_evidence
# -------------------------------------------------------------------------
def read_evidence(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """讀取不可變文本片段 (<=1,200 字，Researcher/Reviewer 共用)"""
    params = args[0] if args and isinstance(args[0], dict) else kwargs
    evidence_version_id = params.get("evidence_version_id", "")

    snapshots = _load_snapshots()
    for ev in snapshots.get("evidences", []):
        if ev.get("evidence_version_id") == evidence_version_id:
            paragraph = ev.get("paragraph", "")
            if len(paragraph) > 1200:
                paragraph = paragraph[:1200]
            return {
                "status": "ok",
                "tool": "read_evidence",
                "data": {
                    "evidence_version_id": ev.get("evidence_version_id"),
                    "paragraph": paragraph,
                    "source_url": ev.get("source_url", "https://mops.twse.com.tw/mops/web/t05st01"),
                    "content_hash": ev.get("content_hash"),
                    "available_at": ev.get("available_at")
                }
            }
    return {"status": "no_data", "tool": "read_evidence", "reason": f"查無指定片段: {evidence_version_id}", "data": None}


# -------------------------------------------------------------------------
# 工具 3: get_financial_snapshot
# -------------------------------------------------------------------------
def get_financial_snapshot(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """取得單季、TTM 與存量財務指標 (含連續 4 季單季檢查與補齊契約欄位)"""
    params = args[0] if args and isinstance(args[0], dict) else kwargs
    ticker = params.get("ticker", "")
    cutoff = params.get("cutoff", "")

    try:
        cutoff_dt = _parse_iso(cutoff)
    except Exception as exc:
        return {"status": "invalid_input", "tool": "get_financial_snapshot", "reason": f"cutoff 格式錯誤: {exc}", "data": None}

    snapshots = _load_snapshots()
    company_data = snapshots.get("financials", {}).get(ticker)

    if not company_data:
        return {"status": "no_data", "tool": "get_financial_snapshot", "reason": f"查無 {ticker} 財務資料", "data": None}

    available_quarters = []
    for q in company_data.get("quarters", []):
        if _parse_iso(q["available_at"]) <= cutoff_dt:
            available_quarters.append(q)

    if not available_quarters:
        return {"status": "no_data", "tool": "get_financial_snapshot", "reason": f"截至 {cutoff} 無可得財務資料", "data": None}

    latest_q = available_quarters[-1]

    # 嚴格校驗：必須為連續 4 個 single_quarter 且無缺失值方可加總 TTM
    eps_ttm = None
    fcf_ttm = None
    ttm_missing_reason = None

    if len(available_quarters) >= 4:
        last_4 = available_quarters[-4:]
        is_all_single_q = all(q.get("period_basis") == "single_quarter" for q in last_4)
        has_no_null_eps = all(q.get("eps") is not None for q in last_4)
        has_no_null_fcf = all(q.get("free_cash_flow") is not None for q in last_4)

        if is_all_single_q and has_no_null_eps and has_no_null_fcf:
            eps_ttm = round(sum(q["eps"] for q in last_4), 2)
            fcf_ttm = round(sum(q["free_cash_flow"] for q in last_4), 2)
        else:
            ttm_missing_reason = "單季資料存在缺失或期間口徑不一致，拒絕推估 TTM"
    else:
        ttm_missing_reason = f"可得單季季數不足 4 季 (僅 {len(available_quarters)} 季)，禁止年化推估"

    return {
        "status": "ok",
        "tool": "get_financial_snapshot",
        "data": {
            "ticker": ticker,
            "company_name": company_data.get("company_name", ticker),
            "statement_basis": company_data.get("statement_basis", "consolidated"),
            "currency": company_data.get("currency", "TWD"),
            "unit": "100m",
            "latest_period": latest_q.get("period"),
            "period_basis": latest_q.get("period_basis", "single_quarter"),
            "source_id": latest_q.get("source_id", f"src-finmind-{ticker}-fs"),
            "snapshot_id": latest_q.get("snapshot_id", f"snap-{ticker}-{latest_q.get('period')}"),
            "content_hash": latest_q.get("content_hash", ""),
            "missing_reason": ttm_missing_reason,
            "metrics": {
                "revenue_single_q": latest_q.get("revenue"),
                "operating_income_single_q": latest_q.get("operating_income"),
                "net_income_single_q": latest_q.get("net_income"),
                "operating_cash_flow_single_q": latest_q.get("operating_cash_flow"),
                "capital_expenditure_single_q": latest_q.get("capital_expenditure"),
                "free_cash_flow_single_q": latest_q.get("free_cash_flow"),
                "eps_single_q": latest_q.get("eps"),
                "bvps": latest_q.get("bvps"),
                "eps_ttm": eps_ttm,
                "fcf_ttm": fcf_ttm,
                "shares_outstanding_m": latest_q.get("shares_outstanding"),
                "net_debt": latest_q.get("net_debt")
            },
            "available_at": latest_q["available_at"]
        }
    }


# -------------------------------------------------------------------------
# 工具 4: get_macro_snapshot
# -------------------------------------------------------------------------
def get_macro_snapshot(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """取得白名單總經快照 (FRED / TWII)"""
    params = args[0] if args and isinstance(args[0], dict) else kwargs
    cutoff = params.get("cutoff", "")
    series_ids = params.get("series_ids", [])

    try:
        cutoff_dt = _parse_iso(cutoff)
    except Exception as exc:
        return {"status": "invalid_input", "tool": "get_macro_snapshot", "reason": f"cutoff 格式錯誤: {exc}", "data": None}

    # 檢查是否全為白名單序列
    unauthorized = [sid for sid in series_ids if sid not in MACRO_SERIES_WHITELIST]
    if unauthorized:
        return {"status": "invalid_input", "tool": "get_macro_snapshot", "reason": f"未授權總經序列: {unauthorized}", "data": None}

    snapshots = _load_snapshots()
    macro_list = snapshots.get("macro", [])

    matched = []
    for item in macro_list:
        if item.get("series_id") in series_ids:
            if _parse_iso(item["available_at"]) <= cutoff_dt:
                matched.append(item)

    if not matched:
        return {"status": "no_data", "tool": "get_macro_snapshot", "reason": "指定指標於 cutoff 前無數據", "data": None}

    return {"status": "ok", "tool": "get_macro_snapshot", "data": matched}


# -------------------------------------------------------------------------
# 工具 5: get_price_window
# -------------------------------------------------------------------------
def get_price_window(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """取得指定交易日收盤價視窗 (Researcher 專用，依 FinMind 17:30 官方可得時間判定)"""
    params = args[0] if args and isinstance(args[0], dict) else kwargs
    ticker = params.get("ticker", "")
    end_at = params.get("end_at", "")
    sessions = int(params.get("sessions", 1))

    if sessions not in (1, 5, 20):
        return {"status": "invalid_input", "tool": "get_price_window", "reason": "sessions 只限 1, 5, 20", "data": None}

    try:
        end_dt = _parse_iso(end_at)
    except Exception as exc:
        return {"status": "invalid_input", "tool": "get_price_window", "reason": f"end_at 格式錯誤: {exc}", "data": None}

    snapshots = _load_snapshots()
    price_series = snapshots.get("prices", {}).get(ticker, [])

    # 以平日 17:30:00+08:00 作為 FinMind 當日行情入庫可得時點
    valid_prices = []
    for p in price_series:
        avail_dt = _parse_iso(p["trade_date"] + "T17:30:00+08:00")
        if avail_dt <= end_dt:
            valid_prices.append(p)

    if not valid_prices or len(valid_prices) < sessions:
        return {"status": "no_data", "tool": "get_price_window", "reason": "交易數據不足或指定區間停牌/休市", "data": None}

    target_window = valid_prices[-sessions:]
    return {
        "status": "ok",
        "tool": "get_price_window",
        "data": {
            "ticker": ticker,
            "currency": "TWD",
            "price_basis": "raw_close",
            "sessions": sessions,
            "closes": target_window
        }
    }


# -------------------------------------------------------------------------
# 工具 6: calculate_metrics
# -------------------------------------------------------------------------
def calculate_metrics(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """確定性純數學運算入口，委派給 agents.calculator.execute_calculation"""
    params = args[0] if args and isinstance(args[0], dict) else kwargs
    operation = params.get("operation", "")
    values = params.get("values", {})
    evidence_refs = params.get("evidence_refs", [])
    return execute_calculation(operation=operation, values=values, evidence_refs=evidence_refs)
