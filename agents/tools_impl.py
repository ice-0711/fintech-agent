"""agents/tools_impl.py
W03-B: 6 大工具標準實作模組。
嚴格對齊 V1.2 工具契約與資料手冊：
- 不做任意網路爬蟲或外部未授權請求
- cutoff 後數據嚴格不可見 (No Look-Ahead)
- 缺值一律保持 None / no_data，嚴禁以 0 補缺值
- 2330 僅作為產業參照，絕不納入 2454 同業平均計算
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

# 相容不同執行路徑的匯入方式
try:
    from agents.calculator import execute_calculation
except ImportError:
    from calculator import execute_calculation  # type: ignore

CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent

# 尋找 financial-snapshots.json 候選路徑
CANDIDATE_PATHS = [
    PROJECT_ROOT / "data" / "financial-snapshots.json",
    PROJECT_ROOT / "financial-snapshots.json",
    CURRENT_DIR / "data" / "financial-snapshots.json",
    CURRENT_DIR / "financial-snapshots.json",
    Path("data/financial-snapshots.json"),
    Path("financial-snapshots.json"),
]


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


def _consecutive_quarters(periods: list[str]) -> bool:
    """['2025Q3','2025Q4','2026Q1','2026Q2'] → True；跳季或格式不明 → False。"""
    try:
        idx = [int(p[:4]) * 4 + int(p[-1]) - 1 for p in periods]
    except (ValueError, TypeError, IndexError):
        return False
    return all(b - a == 1 for a, b in zip(idx, idx[1:]))


def _parse_iso(dt_str: str) -> datetime:
    return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))


# -------------------------------------------------------------------------
# 工具 1: search_evidence
# -------------------------------------------------------------------------
def search_evidence(ticker: str, query: str, cutoff: str, limit: int = 5) -> dict[str, Any]:
    """查詢已入庫快照之公開文件索引 (Researcher 專用)"""
    if ticker not in ("2330", "2317", "2454"):
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
            # 防前視：可得時間必須早於或等於 cutoff
            if avail_dt <= cutoff_dt:
                query_words = [w for w in query.strip().split() if w]
                title = ev.get("title", "")
                abstract = ev.get("abstract", "")
                if not query_words or any(word in title or word in abstract for word in query_words):
                    matches.append({
                        "source_id": ev["source_id"],
                        "title": title,
                        "published_at": ev.get("published_at"),
                        "captured_at": ev["captured_at"],
                        "available_at": ev["available_at"],
                        "content_hash": ev["content_hash"],
                        "abstract": abstract
                    })

    if not matches:
        return {"status": "no_data", "tool": "search_evidence", "reason": "指定 cutoff 前查無相符索引快照", "data": None}

    return {"status": "ok", "tool": "search_evidence", "data": matches[:limit]}


# -------------------------------------------------------------------------
# 工具 2: read_evidence
# -------------------------------------------------------------------------
def read_evidence(evidence_version_id: str) -> dict[str, Any]:
    """讀取不可變文本片段 (<=1,200 字，Researcher/Reviewer 共用)"""
    snapshots = _load_snapshots()
    # 開發案例證據在 fixtures/dev/case_fixtures.json（W04-B）；一併可讀。（組長修正 2026-10-15）
    dev_path = PROJECT_ROOT / "fixtures" / "dev" / "case_fixtures.json"
    dev_evidences = []
    if dev_path.exists():
        with open(dev_path, "r", encoding="utf-8") as f:
            for snap in json.load(f).get("snapshots", {}).values():
                dev_evidences.extend(snap.get("evidences", []))
    for ev in snapshots.get("evidences", []) + dev_evidences:
        if ev.get("evidence_version_id") == evidence_version_id:
            return {
                "status": "ok",
                "tool": "read_evidence",
                "data": {
                    "evidence_version_id": ev["evidence_version_id"],
                    "paragraph": ev["paragraph"],
                    "source_url": ev.get("source_url"),
                    "content_hash": ev["content_hash"],
                    "available_at": ev["available_at"]
                }
            }
    return {"status": "no_data", "tool": "read_evidence", "reason": f"查無指定片段: {evidence_version_id}", "data": None}


# -------------------------------------------------------------------------
# 工具 3: get_financial_snapshot
# -------------------------------------------------------------------------
def get_financial_snapshot(ticker: str, cutoff: str) -> dict[str, Any]:
    """取得單季、TTM 與存量財務指標 (含 YTD 差分還原與連續 4 季 TTM 檢查)"""
    try:
        cutoff_dt = _parse_iso(cutoff)
    except Exception as exc:
        return {"status": "invalid_input", "tool": "get_financial_snapshot", "reason": f"cutoff 格式錯誤: {exc}", "data": None}

    snapshots = _load_snapshots()
    company_data = snapshots.get("financials", {}).get(ticker)

    if not company_data:
        return {"status": "no_data", "tool": "get_financial_snapshot", "reason": f"查無 {ticker} 財務資料", "data": None}

    # 依 cutoff 篩選已可得之單季資料
    available_quarters = []
    for q in company_data.get("quarters", []):
        if _parse_iso(q["available_at"]) <= cutoff_dt:
            available_quarters.append(q)

    if not available_quarters:
        return {"status": "no_data", "tool": "get_financial_snapshot", "reason": f"截至 {cutoff} 無可得財務資料", "data": None}

    latest_q = available_quarters[-1]

    # 檢查是否足夠連續 4 季以計算 TTM，不足則嚴格保持 None
    eps_ttm = None
    fcf_ttm = None
    if len(available_quarters) >= 4:
        last_4 = available_quarters[-4:]
        # 手冊 F01：TTM 需「連續」四季，且任一季缺值即為 null（不補 0）。（組長修正 2026-10-15）
        if _consecutive_quarters([q["period"] for q in last_4]):
            if all(q.get("eps") is not None for q in last_4):
                eps_ttm = round(sum(q["eps"] for q in last_4), 2)
            if all(q.get("free_cash_flow") is not None for q in last_4):
                fcf_ttm = round(sum(q["free_cash_flow"] for q in last_4), 2)

    return {
        "status": "ok",
        "tool": "get_financial_snapshot",
        "data": {
            "ticker": ticker,
            "company_name": company_data.get("company_name", ticker),
            "statement_basis": company_data.get("statement_basis", "consolidated"),
            "currency": company_data.get("currency", "TWD"),
            "unit": "100m",
            "latest_period": latest_q["period"],
            "metrics": {
                "revenue_single_q": latest_q.get("revenue"),
                "net_income_single_q": latest_q.get("net_income"),
                "operating_cash_flow_single_q": latest_q.get("operating_cash_flow"),
                "capital_expenditure_single_q": latest_q.get("capital_expenditure"),
                "free_cash_flow_single_q": latest_q.get("free_cash_flow"),
                "eps_single_q": latest_q.get("eps"),
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
def get_macro_snapshot(cutoff: str, series_ids: list[str]) -> dict[str, Any]:
    """取得白名單總經快照 (FRED / TWII)"""
    try:
        cutoff_dt = _parse_iso(cutoff)
    except Exception as exc:
        return {"status": "invalid_input", "tool": "get_macro_snapshot", "reason": f"cutoff 格式錯誤: {exc}", "data": None}

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
def get_price_window(ticker: str, end_at: str, sessions: int) -> dict[str, Any]:
    """取得指定交易日收盤價視窗 (Researcher 專用)"""
    if sessions not in (1, 5, 20):
        return {"status": "invalid_input", "tool": "get_price_window", "reason": "sessions 只限 1, 5, 20", "data": None}

    try:
        end_dt = _parse_iso(end_at)
    except Exception as exc:
        return {"status": "invalid_input", "tool": "get_price_window", "reason": f"end_at 格式錯誤: {exc}", "data": None}

    snapshots = _load_snapshots()
    price_series = snapshots.get("prices", {}).get(ticker, [])

    valid_prices = [p for p in price_series if _parse_iso(p["trade_date"] + "T13:30:00+08:00") <= end_dt]

    if not valid_prices or len(valid_prices) < sessions:
        return {"status": "no_data", "tool": "get_price_window", "reason": "交易數據不足或停牌", "data": None}

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
# 工具 6: calculate_metrics (委派 calculator 模組)
# -------------------------------------------------------------------------
def calculate_metrics(operation: str, values: dict[str, Any], evidence_refs: list[str]) -> dict[str, Any]:
    """確定性純數學運算入口，委派給 agents.calculator.execute_calculation"""
    return execute_calculation(operation=operation, values=values, evidence_refs=evidence_refs)