"""scripts/build_w02_fixtures.py — W02-B 由真實快照產生兩份 fixture。

輸出
----
- data/v12-financial-fixtures.json ：季度／TTM／時點分層驗算 fixture（真實）＋合成驗算例
- fixtures/tool-responses.json     ：六工具正常／缺值／錯誤之「預期回傳」規格

原則
----
- 所有真實數字一律從 data/financial-snapshots.json 讀取，不手打。
- 預期計算值以本檔獨立公式計算，不呼叫 agents/calculator.py（避免測試自己驗自己）。
- 回傳頂層固定為 status / tool / reason / data（沿用 agents/tools.py 框架）。
- 可得時間：財報＝MOPS 發言時間（official）；股價＝交易日 17:30（rule_close_1730）；
  未知官方時間＝captured_at（captured_at_fallback）。
- 合成樣本一律 synthetic_fixture=true。

執行
----
    python scripts/build_w02_fixtures.py          # 產生兩個檔案
    python scripts/check_sources.py               # 再跑檢查器
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "data" / "financial-snapshots.json"
MACRO_CSV = ROOT / "data" / "manual" / "macro.csv"
OUT_FIN = ROOT / "data" / "v12-financial-fixtures.json"
OUT_TOOL = ROOT / "fixtures" / "tool-responses.json"

TW = timezone(timedelta(hours=8))
FIXTURE_VERSION = "v1.4-w02"
CONTRACT_VERSION = "v1.1-w02"
CUTOFF = "2026-09-30T17:30:00+08:00"   # 統一比較基準：2026-09-30 收盤後
PRICE_DATE = "2026-09-30"
STATUS_ENUM = ["ok", "no_data", "invalid_input", "unreadable", "tool_error"]
ROLES = {"2454": "subject", "2379": "peer", "3034": "peer", "2330": "industry_reference", "2317": "research_only"}
TTM_PERIODS = ["2025Q3", "2025Q4", "2026Q1", "2026Q2"]
DCF_PARAM_NOTE = "WACC 10%、g 3% 為 valuation_agent/dcf_model.py 程式預設值；5 年持平 FCF；均待組長核定"


# ---------------------------------------------------------------------------
# 讀取來源
# ---------------------------------------------------------------------------
def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


SNAP = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
DEV_CASES = {c["case_id"]: c for c in json.loads((ROOT / "evaluation" / "dev-cases.json")
                                                  .read_text(encoding="utf-8"))["cases"]}
SNAP_HASH = sha256_file(SNAPSHOT)
MACRO_HASH = sha256_file(MACRO_CSV)
RAW = SNAP["source_manifest"]["raw_files"]


def raw_file(dataset: str, ticker: str | None) -> dict[str, Any]:
    for r in RAW:
        if r["dataset"] == dataset and r["data_id"] == ticker:
            return r
    raise KeyError(f"source_manifest 缺 {dataset} {ticker}")


def quarters(ticker: str) -> dict[str, dict[str, Any]]:
    return {q["period"]: q for q in SNAP["financials"][ticker]["quarters"]}


def close_on(ticker: str, trade_date: str) -> float:
    for p in SNAP["prices"][ticker]:
        if p["trade_date"] == trade_date:
            return p["close"]
    raise KeyError(f"{ticker} 無 {trade_date} 收盤價")


def evidence(eid: str) -> dict[str, Any]:
    return next(e for e in SNAP["evidences"] if e["evidence_version_id"] == eid)


def price_available_at(trade_date: str) -> str:
    return f"{trade_date}T17:30:00+08:00"


def parse(t: str) -> datetime:
    return datetime.fromisoformat(t.replace("Z", "+00:00"))


# ---------------------------------------------------------------------------
# 獨立計算（不呼叫 calculator.py）
# ---------------------------------------------------------------------------
def ttm(ticker: str, periods: list[str], field: str) -> float | None:
    q = quarters(ticker)
    rows = [q.get(p) for p in periods]
    if len(rows) != 4 or any(r is None or r.get(field) is None for r in rows):
        return None
    if field == "eps" and any(r["eps_source"] == "unverified" for r in rows):
        return None
    return round(sum(r[field] for r in rows), 2)


def dcf(fcfs: list[float], wacc: float, g: float, net_debt: float, shares_m: float) -> dict[str, Any]:
    pv = sum(f / (1 + wacc) ** i for i, f in enumerate(fcfs, start=1))
    tv = fcfs[-1] * (1 + g) / (wacc - g)
    pv_tv = tv / (1 + wacc) ** len(fcfs)
    ev = pv + pv_tv
    eq = ev - net_debt
    per_share = round(eq / shares_m * 100, 2)   # 億元 ÷ 百萬股 × 100 = 元／股
    return {"pv_fcf_total": round(pv, 2), "terminal_value": round(tv, 2), "pv_terminal": round(pv_tv, 2),
            "enterprise_value": round(ev, 2), "equity_value": round(eq, 2), "intrinsic_value_per_share": per_share}


def sensitivity(fcfs, wacc, g, nd, sh) -> dict[str, dict[str, float | None]]:
    out: dict[str, dict[str, float | None]] = {}
    for w in (round(wacc - 0.01, 4), round(wacc, 4), round(wacc + 0.01, 4)):
        row: dict[str, float | None] = {}
        for gg in (round(g - 0.005, 4), round(g, 4), round(g + 0.005, 4)):
            row[f"{round(gg * 100, 2)}%"] = None if w <= gg else dcf(fcfs, w, gg, nd, sh)["intrinsic_value_per_share"]
        out[f"{round(w * 100, 2)}%"] = row
    return out


# ---------------------------------------------------------------------------
# 1) v12-financial-fixtures.json
# ---------------------------------------------------------------------------
QUARTER_FIELDS = ["revenue", "operating_income", "net_income", "operating_cash_flow", "capital_expenditure",
                  "free_cash_flow", "eps", "eps_source", "shares_issued", "treasury_shares",
                  "shares_outstanding", "bvps", "net_debt"]


def company_fixture(ticker: str) -> dict[str, Any]:
    fs_raw = raw_file("TaiwanStockFinancialStatements", ticker)
    price_raw = raw_file("TaiwanStockPrice", ticker)
    q = quarters(ticker)
    rows = []
    for period, src in q.items():
        row = {"period": period, "period_basis": src["period_basis"], "statement_basis": "consolidated",
               "currency": "TWD", "unit_money": "100m", "unit_shares": "1m", "unit_per_share": "TWD"}
        row.update({k: src.get(k) for k in QUARTER_FIELDS})
        row.update({"available_at": src["available_at"], "available_at_basis": "official",
                    "captured_at": fs_raw["captured_at"], "source_id": src["source_id"],
                    "snapshot_id": src["snapshot_id"], "content_hash": src["content_hash"],
                    "synthetic_fixture": False})
        rows.append(row)

    close = close_on(ticker, PRICE_DATE)
    eps_ttm = ttm(ticker, TTM_PERIODS, "eps")
    fcf_ttm = ttm(ticker, TTM_PERIODS, "free_cash_flow")
    bvps = q["2026Q2"]["bvps"]
    yoy = None
    if q.get("2025Q2", {}).get("revenue"):
        yoy = round(q["2026Q2"]["revenue"] / q["2025Q2"]["revenue"] - 1, 4)

    return {
        "company_name": SNAP["financials"][ticker].get("company_name"),
        "role": ROLES[ticker],
        "statement_basis": "consolidated",
        "currency": "TWD",
        "unit_money": "100m",
        "unit_shares": "1m",
        "quarters": rows,
        "ttm_summary": {
            "as_of_period": "2026Q2",
            "periods": TTM_PERIODS,
            "eps_ttm": eps_ttm,
            "eps_ttm_unit": "TWD/share",
            "fcf_ttm": fcf_ttm,
            "fcf_ttm_unit": "100m TWD",
            "eps_sources": [q[p]["eps_source"] for p in TTM_PERIODS],
            "is_complete_4_quarters": eps_ttm is not None,
            "rounding_note": "各季值取自快照（由原始值計算後四捨五入至 0.01），TTM 為四季快照值相加",
        },
        "market_snapshot": {
            "trade_date": PRICE_DATE,
            "close_price": close,
            "currency": "TWD",
            "unit": "TWD/share",
            "price_basis": "raw_close",
            "available_at": price_available_at(PRICE_DATE),
            "available_at_basis": "rule_close_1730",
            "captured_at": price_raw["captured_at"],
            "source_id": "finmind_price",
            "content_hash": price_raw["sha256"],
            "verification": "與 TWSE STOCK_DAY 2026-09 原始檔逐日比對一致（data-contract.md 待決事項 9）",
            "pe_ttm": round(close / eps_ttm, 2) if eps_ttm and eps_ttm > 0 else None,
            "pe_missing_reason": None if eps_ttm and eps_ttm > 0 else "EPS TTM 缺失或非正",
            "bvps": bvps,
            "pb_ratio": round(close / bvps, 2) if bvps and bvps > 0 else None,
            "revenue_yoy_quarter": yoy,
            "revenue_yoy_basis": "2026Q2 單季 ÷ 2025Q2 單季 − 1",
        },
    }


SYNTHETIC_EXAMPLES: list[dict[str, Any]] = [
    {"example_id": "SX-01", "topic": "YTD 還原單季（含 Q4 = 全年 − Q3 累計）",
     "input": {"statement_basis": "consolidated", "currency": "TWD", "unit": "100m", "fiscal_year": 2099,
               "ytd": {"Q1": 100.0, "Q2": 250.0, "Q3": 420.0}, "annual": 600.0},
     "expected": {"single_quarter": {"Q1": 100.0, "Q2": 150.0, "Q3": 170.0, "Q4": 180.0}}},
    {"example_id": "SX-02", "topic": "前期缺值不得差分",
     "input": {"statement_basis": "consolidated", "currency": "TWD", "unit": "100m",
               "ytd": {"Q1": None, "Q2": 250.0}},
     "expected": {"single_quarter": {"Q2": {"value": None, "missing_reason": "Q1 累計值缺失，無法差分"}}}},
    {"example_id": "SX-03", "topic": "口徑不同不得差分",
     "input": {"currency": "TWD", "unit": "100m",
               "ytd": {"Q1": {"value": 100.0, "statement_basis": "consolidated"},
                       "Q2": {"value": 260.0, "statement_basis": "standalone"}}},
     "expected": {"single_quarter": {"Q2": {"value": None, "missing_reason": "Q1 與 Q2 口徑不同（合併 vs 個體）"}}}},
    {"example_id": "SX-04", "topic": "時點存量不可跨期相加",
     "input": {"unit": "1m shares", "shares_outstanding": {"Q1": 1000.0, "Q2": 1010.0}},
     "expected": {"shares_outstanding_for_valuation": 1010.0,
                  "forbidden": "1000 + 1010 = 2010 不是有效數字；存量取最近一期"}},
    {"example_id": "SX-05", "topic": "不足 4 季不得算 TTM",
     "input": {"currency": "TWD", "eps": {"Q2": 5.0, "Q3": 6.0, "Q4": 7.0}},
     "expected": {"eps_ttm": {"value": None, "missing_reason": "僅 3 季，不得年化推估"}}},
    {"example_id": "SX-06", "topic": "TTM 含 unverified EPS 不得作正式數字",
     "input": {"currency": "TWD", "eps": [{"q": "Q1", "v": 5.0, "eps_source": "mops_direct"},
                                         {"q": "Q2", "v": 6.0, "eps_source": "unverified"},
                                         {"q": "Q3", "v": 7.0, "eps_source": "mops_direct"},
                                         {"q": "Q4", "v": 8.0, "eps_source": "finmind_quarterly"}]},
     "expected": {"eps_ttm": {"value": None, "missing_reason": "Q2 EPS 為 unverified"}}},
    {"example_id": "SX-07", "topic": "四連續季 TTM",
     "input": {"currency": "TWD", "eps": {"Q1": 5.0, "Q2": 6.0, "Q3": 7.0, "Q4": 8.0},
               "eps_source": "mops_direct"},
     "expected": {"eps_ttm": 26.0}},
    {"example_id": "SX-08", "topic": "null 與 0 分開",
     "input": {"currency": "TWD", "unit": "100m",
               "BondsPayable": {"finmind": None, "mops_note": "合併資產負債表無應付公司債科目（附 MOPS 網址）"},
               "ShorttermBorrowings": {"finmind": None, "mops_note": None}},
     "expected": {"BondsPayable": {"value": 0.0, "reason": "科目確實不存在，有原文證明"},
                  "ShorttermBorrowings": {"value": None, "missing_reason": "FinMind 缺值且無人工覆寫"},
                  "net_debt": {"value": None, "missing_reason": "計息負債有缺值，淨負債不得計算"}}},
    {"example_id": "SX-09", "topic": "未知公告時間不視為較早可得",
     "input": {"cutoff": "2099-08-01T00:00:00+08:00",
               "doc_a": {"available_at": None, "captured_at": "2099-08-05T10:00:00+08:00", "period": "2099Q2"},
               "doc_b": {"available_at": None, "captured_at": None, "period": "2099Q2"}},
     "expected": {"doc_a": {"effective_available_at": "2099-08-05T10:00:00+08:00",
                            "available_at_basis": "captured_at_fallback", "usable_at_cutoff": False},
                  "doc_b": {"effective_available_at": None, "usable_at_cutoff": False,
                            "reason": "兩個時間皆未知，視為不可得；不得倒填為 2099-06-30"}}},
    {"example_id": "SX-10", "topic": "年度相容：四單季加總等於年度值",
     "input": {"currency": "TWD", "unit": "100m", "single_quarter": [100.0, 150.0, 170.0, 180.0],
               "annual_reported": 600.0},
     "expected": {"annual_from_quarters": 600.0, "matches_annual": True,
                  "annual_dcf_input": "沿用年度值 600.0，不改年度 DCF 路徑"}},
    {"example_id": "SX-11", "topic": "CapEx 符號與 FCF",
     "input": {"currency": "TWD", "unit": "100m",
               "case_a": {"CashFlowsFromOperatingActivities": 50.0, "PropertyAndPlantAndEquipment": -20.0},
               "case_b": {"CashFlowsFromOperatingActivities": 50.0, "PropertyAndPlantAndEquipment": 5.0}},
     "expected": {"case_a": {"capital_expenditure": 20.0, "free_cash_flow": 30.0},
                  "case_b": {"free_cash_flow": None, "missing_reason": "CapEx 為正值，與來源慣例不符，中止並人工確認"}}},
    {"example_id": "SX-12", "topic": "EPS 或 BVPS 非正不計算比率",
     "input": {"currency": "TWD", "price": 100.0, "eps_ttm": -2.0, "bvps": 0.0},
     "expected": {"pe_ttm": {"value": None, "missing_reason": "EPS TTM ≤ 0"},
                  "pb_ratio": {"value": None, "missing_reason": "BVPS ≤ 0"}}},
]
for ex in SYNTHETIC_EXAMPLES:
    ex["synthetic_fixture"] = True


def build_financial_fixtures() -> dict[str, Any]:
    return {
        "fixture_version": FIXTURE_VERSION,
        "generated_by": "scripts/build_w02_fixtures.py",
        "generated_at": datetime.now(TW).isoformat(timespec="seconds"),
        "cutoff": CUTOFF,
        "source_snapshot": {"file": "data/financial-snapshots.json", "sha256": SNAP_HASH,
                            "manifest_version": SNAP["manifest_version"]},
        "note": ("真實季度資料取自快照（synthetic_fixture=false）；synthetic_examples 為人工驗算例"
                 "（synthetic_fixture=true，年度用 2099 以免與真實資料混淆），不得作為財務數字來源。"),
        "companies": {t: company_fixture(t) for t in ("2454", "2379", "3034", "2330")},
        "peer_summary": None,   # 由下方填入
        "synthetic_examples": SYNTHETIC_EXAMPLES,
    }


# ---------------------------------------------------------------------------
# 2) tool-responses.json
# ---------------------------------------------------------------------------
def resp(tool: str, status: str, data: Any = None, reason: str | None = None) -> dict[str, Any]:
    return {"status": status, "tool": tool, "reason": reason, "data": data if status == "ok" else None}


def case(cid: str, tool: str, args: dict[str, Any], expected: dict[str, Any], *, role: str = "researcher",
         job_cutoff: str | None = None, job_snapshot: str | None = None, synthetic: bool = False,
         check: str = "exact", note: str | None = None) -> dict[str, Any]:
    out = {"fixture_id": cid, "tool": tool, "role": role, "job_cutoff": job_cutoff, "job_snapshot_id": job_snapshot,
           "input": args, "synthetic_fixture": synthetic, "check_mode": check, "expected_response": expected}
    if note:
        out["note"] = note
    return out


def evidence_row(e: dict[str, Any]) -> dict[str, Any]:
    return {"source_id": e["source_id"], "evidence_version_id": e["evidence_version_id"], "ticker": e["ticker"],
            "title": e["title"], "published_at": e["published_at"], "captured_at": e["captured_at"],
            "available_at": e["available_at"], "available_at_basis": "official",
            "content_hash": e["content_hash"], "abstract": e.get("abstract")}


def financial_data(ticker: str, cutoff: str) -> dict[str, Any]:
    q = [x for x in SNAP["financials"][ticker]["quarters"] if parse(x["available_at"]) <= parse(cutoff)]
    latest = q[-1]
    periods = [x["period"] for x in q[-4:]]
    eps_ttm = ttm(ticker, periods, "eps") if len(q) >= 4 else None
    fcf_ttm = ttm(ticker, periods, "free_cash_flow") if len(q) >= 4 else None
    missing = None if len(q) >= 4 else f"可得單季季數不足 4 季（僅 {len(q)} 季），禁止年化推估"
    fs_raw = raw_file("TaiwanStockFinancialStatements", ticker)
    return {
        "ticker": ticker, "company_name": SNAP["financials"][ticker].get("company_name"),
        "statement_basis": "consolidated", "currency": "TWD", "unit": "100m",
        "latest_period": latest["period"], "period_basis": "single_quarter",
        "ttm_periods": periods if len(q) >= 4 else None,
        "source_id": latest["source_id"], "snapshot_id": latest["snapshot_id"],
        "content_hash": latest["content_hash"], "missing_reason": missing,
        "metrics": {
            "revenue_single_q": latest["revenue"], "operating_income_single_q": latest["operating_income"],
            "net_income_single_q": latest["net_income"],
            "operating_cash_flow_single_q": latest["operating_cash_flow"],
            "capital_expenditure_single_q": latest["capital_expenditure"],
            "free_cash_flow_single_q": latest["free_cash_flow"], "eps_single_q": latest["eps"],
            "eps_source": latest["eps_source"], "bvps": latest["bvps"],
            "eps_ttm": eps_ttm, "fcf_ttm": fcf_ttm,
            "shares_outstanding_m": latest["shares_outstanding"], "net_debt": latest["net_debt"],
        },
        "available_at": latest["available_at"], "available_at_basis": "official",
        "captured_at": fs_raw["captured_at"],
    }


def price_data(ticker: str, end_at: str, sessions: int) -> dict[str, Any] | None:
    raw = raw_file("TaiwanStockPrice", ticker)
    rows = [p for p in SNAP["prices"][ticker] if parse(price_available_at(p["trade_date"])) <= parse(end_at)]
    if len(rows) < sessions:
        return None
    last = rows[-1]["trade_date"]
    return {"ticker": ticker, "currency": "TWD", "unit": "TWD/share", "price_basis": "raw_close",
            "sessions": sessions, "source_id": "finmind_price", "content_hash": raw["sha256"],
            "available_at": price_available_at(last), "available_at_basis": "rule_close_1730",
            "captured_at": raw["captured_at"],
            "closes": [{"trade_date": p["trade_date"], "close_price": p["close"],
                        "available_at": price_available_at(p["trade_date"]),
                        "available_at_basis": "rule_close_1730"} for p in rows[-sessions:]]}


def macro_row(series_id: str) -> dict[str, Any]:
    m = next(x for x in SNAP["macro"] if x["series_id"] == series_id)
    return {"series_id": m["series_id"], "indicator": m["indicator"], "observation_date": m["observation_date"],
            "value": m["value"], "unit": m["unit"], "available_at": m["available_at"],
            "available_at_basis": "official", "source_id": "fred_macro", "content_hash": MACRO_HASH,
            "vintage": None, "vintage_missing_reason": "只有現行下載值，無歷史 vintage"}


def build_tool_responses(fin: dict[str, Any]) -> dict[str, Any]:
    C: list[dict[str, Any]] = []
    e2330 = evidence("ev-2330-2026q2-01")

    # --- search_evidence ---------------------------------------------------
    a = {"ticker": "2330", "query": "營收", "cutoff": "2026-07-20T17:00:00+08:00", "limit": 5}
    C.append(case("TR-01", "search_evidence", a, resp("search_evidence", "ok", [evidence_row(e2330)])))
    a = {"ticker": "2330", "query": "營收", "cutoff": "2026-06-01T00:00:00+08:00", "limit": 5}
    C.append(case("TR-02", "search_evidence", a, resp("search_evidence", "no_data",
                  reason="指定 cutoff 前查無相符索引快照"), check="status_only"))
    a = {"ticker": "2379", "query": "營收", "cutoff": "2026-09-30T17:30:00+08:00", "limit": 5}
    C.append(case("TR-03", "search_evidence", a, resp("search_evidence", "invalid_input",
                  reason="search_evidence.ticker='2379' 不在允許值 ['2330', '2317', '2454']"), check="status_only",
                  note="2379/3034 只透過財務與行情工具作同業比較輸入"))
    a = {"ticker": "2330", "query": "https://example.com 營收", "cutoff": "2026-09-30T17:30:00+08:00", "limit": 5}
    C.append(case("TR-04", "search_evidence", a, resp("search_evidence", "invalid_input",
                  reason="search_evidence 參數含 URL/路徑/SQL/指令字樣，拒絕執行"), check="status_only"))

    # --- read_evidence -----------------------------------------------------
    C.append(case("TR-05", "read_evidence", {"evidence_version_id": "ev-2330-2026q2-01"},
                  resp("read_evidence", "ok", {"evidence_version_id": e2330["evidence_version_id"],
                                               "source_id": e2330["source_id"],
                                               "paragraph": e2330["paragraph"][:1200],
                                               "source_url": e2330["source_url"],
                                               "content_hash": e2330["content_hash"],
                                               "available_at": e2330["available_at"],
                                               "available_at_basis": "official"})))
    C.append(case("TR-06", "read_evidence", {"evidence_version_id": "ev-dev-15-unreadable"},
                  resp("read_evidence", "unreadable", reason="來源正文不可讀（paragraph 為 null），不得補造內容"),
                  job_cutoff=DEV_CASES["CASE-15"]["cutoff_at"], job_snapshot="snap-dev-case-15",
                  synthetic=True, check="status_only", note="CASE-15；不得崩潰"))
    C.append(case("TR-07", "read_evidence", {"evidence_version_id": "ev-non-existent-999"},
                  resp("read_evidence", "no_data", reason="查無指定片段: ev-non-existent-999"), check="status_only"))

    # --- get_financial_snapshot ---------------------------------------------
    for cid, cutoff, note in [
        ("TR-08", CUTOFF, "最新 2026Q2；TTM = 2025Q3–2026Q2"),
        ("TR-09", "2026-04-01T00:00:00+08:00", "只有 2025Q2–Q4 三季可得 → TTM 為 null（不是 0）"),
        ("TR-10", "2026-07-31T18:00:00+08:00", "2026Q2 於 18:41:57 才公告，cutoff 18:00 時最新仍為 2026Q1（財報期 ≠ 公告日）"),
    ]:
        C.append(case(cid, "get_financial_snapshot", {"ticker": "2454", "cutoff": cutoff},
                      resp("get_financial_snapshot", "ok", financial_data("2454", cutoff)), note=note))
    C.append(case("TR-11", "get_financial_snapshot", {"ticker": "9999", "cutoff": CUTOFF},
                  resp("get_financial_snapshot", "invalid_input",
                       reason="get_financial_snapshot.ticker='9999' 不在允許值"), check="status_only"))
    C.append(case("TR-12", "get_financial_snapshot",
                  {"ticker": "2454", "cutoff": CUTOFF, "period_basis": "single_quarter"},
                  resp("get_financial_snapshot", "invalid_input",
                       reason="get_financial_snapshot 不接受欄位 ['period_basis']"), check="status_only",
                  note="契約只有 ticker、cutoff 兩個參數"))
    C.append(case("TR-13", "get_financial_snapshot", {"ticker": "2454", "cutoff": "2025-01-01T00:00:00+08:00"},
                  resp("get_financial_snapshot", "no_data", reason="截至 cutoff 無可得財務資料"), check="status_only"))

    # --- get_macro_snapshot -------------------------------------------------
    C.append(case("TR-14", "get_macro_snapshot", {"cutoff": CUTOFF, "series_ids": ["CPIAUCSL", "FEDFUNDS"]},
                  resp("get_macro_snapshot", "ok", [macro_row("CPIAUCSL"), macro_row("FEDFUNDS")])))
    C.append(case("TR-15", "get_macro_snapshot", {"cutoff": CUTOFF, "series_ids": ["UNRATE"]},
                  resp("get_macro_snapshot", "invalid_input", reason="series ['UNRATE'] 不在已核准白名單"),
                  check="status_only"))
    C.append(case("TR-16", "get_macro_snapshot", {"cutoff": "2026-07-10T00:00:00+08:00", "series_ids": ["CPIAUCSL"]},
                  resp("get_macro_snapshot", "no_data", reason="指定指標於 cutoff 前無數據"), check="status_only",
                  note="2026-06 CPI 於 2026-07-14 才發布"))

    # --- get_price_window ---------------------------------------------------
    C.append(case("TR-17", "get_price_window", {"ticker": "2454", "end_at": CUTOFF, "sessions": 5},
                  resp("get_price_window", "ok", price_data("2454", CUTOFF, 5))))
    end = "2026-09-30T17:00:00+08:00"
    C.append(case("TR-18", "get_price_window", {"ticker": "2454", "end_at": end, "sessions": 1},
                  resp("get_price_window", "ok", price_data("2454", end, 1)),
                  note="09-30 收盤價 17:30 才可得，end_at 17:00 時最新為 09-29"))
    C.append(case("TR-19", "get_price_window", {"ticker": "2454", "end_at": CUTOFF, "sessions": 10},
                  resp("get_price_window", "invalid_input", reason="get_price_window.sessions=10 不在允許值 [1, 5, 20]"),
                  check="status_only"))
    C.append(case("TR-20", "get_price_window", {"ticker": "2454", "end_at": CUTOFF, "sessions": 5},
                  resp("get_price_window", "invalid_input", reason="reviewer 無權使用 get_price_window"),
                  role="reviewer", check="status_only", note="Reviewer 需查價時以 claim_id 退回 Researcher"))

    # --- calculate_metrics --------------------------------------------------
    c54 = fin["companies"]["2454"]
    p, e_ttm = c54["market_snapshot"]["close_price"], c54["ttm_summary"]["eps_ttm"]
    refs = ["snap-2454-2026Q2", "finmind_price"]
    C.append(case("TR-21", "calculate_metrics",
                  {"operation": "pe_ttm", "values": {"price": p, "eps_ttm": e_ttm}, "evidence_refs": refs},
                  resp("calculate_metrics", "ok", {"result_value": round(p / e_ttm, 2), "is_applicable": True,
                                                   "reason": None, "evidence_refs": refs, "operation": "pe_ttm"})))
    C.append(case("TR-22", "calculate_metrics",
                  {"operation": "pe_ttm", "values": {"price": p, "eps_ttm": -5.2}, "evidence_refs": refs},
                  resp("calculate_metrics", "invalid_input", reason="EPS TTM <= 0，不適用本益比 (NA)"),
                  synthetic=True, check="status_only"))
    C.append(case("TR-23", "calculate_metrics",
                  {"operation": "pe_ttm", "values": {"price": p, "eps_ttm": e_ttm}, "evidence_refs": []},
                  resp("calculate_metrics", "invalid_input", reason="運算必須引用具體 evidence_refs 依據"),
                  check="status_only"))

    fcf, nd = c54["ttm_summary"]["fcf_ttm"], c54["quarters"][-1]["net_debt"]
    sh = c54["quarters"][-1]["shares_outstanding"]
    fcfs = [fcf] * 5
    dv = {"free_cash_flows": fcfs, "wacc": 0.10, "terminal_growth": 0.03, "net_debt": nd, "shares_outstanding": sh}
    d = dcf(fcfs, 0.10, 0.03, nd, sh)
    d.update({"sensitivity_matrix": sensitivity(fcfs, 0.10, 0.03, nd, sh), "is_applicable": True, "reason": None,
              "evidence_refs": ["snap-2454-2026Q2"], "operation": "dcf_scenario"})
    C.append(case("TR-24", "calculate_metrics",
                  {"operation": "dcf_scenario", "values": dv, "evidence_refs": ["snap-2454-2026Q2"]},
                  resp("calculate_metrics", "ok", d), note=DCF_PARAM_NOTE + "；內在價值非保證成交價"))
    for cid, patch, reason in [
        ("TR-25", {"wacc": 0.03}, "WACC (0.03) 必須嚴格大於終端成長率 g (0.03)"),
        ("TR-26", {"net_debt": None}, "DCF 關鍵參數缺失，嚴禁假補 0"),
        ("TR-27", {"free_cash_flows": fcfs[:3]}, "DCF 預測期必須為 5 年，目前為 3 年"),
    ]:
        C.append(case(cid, "calculate_metrics",
                      {"operation": "dcf_scenario", "values": {**dv, **patch}, "evidence_refs": ["snap-2454-2026Q2"]},
                      resp("calculate_metrics", "invalid_input", reason=reason), synthetic=True, check="status_only"))

    metrics, table, peers = {}, {}, {"pe": [], "pb": [], "yoy": []}
    for t in ("2454", "2379", "3034", "2330"):
        ms, tt = fin["companies"][t]["market_snapshot"], fin["companies"][t]["ttm_summary"]
        metrics[t] = {"price": ms["close_price"], "eps_ttm": tt["eps_ttm"], "bvps": ms["bvps"],
                      "revenue_yoy": ms["revenue_yoy_quarter"], "fcf": tt["fcf_ttm"]}
        table[t] = {"role": ROLES[t], "price": ms["close_price"], "pe_ttm": ms["pe_ttm"], "pe_na_reason": None,
                    "pb_ratio": ms["pb_ratio"], "pb_na_reason": None, "revenue_yoy": ms["revenue_yoy_quarter"],
                    "revenue_yoy_na_reason": None, "fcf": tt["fcf_ttm"], "fcf_na_reason": None,
                    "dcf_intrinsic_value": None, "dcf_gap_pct": None}
        if ROLES[t] == "peer":
            peers["pe"].append(ms["pe_ttm"]); peers["pb"].append(ms["pb_ratio"])
            peers["yoy"].append(ms["revenue_yoy_quarter"])
    summary = {"peer_avg_pe": round(sum(peers["pe"]) / 2, 2), "peer_avg_pb": round(sum(peers["pb"]) / 2, 2),
               "peer_avg_revenue_yoy": round(sum(peers["yoy"]) / 2, 4), "excluded_references": ["2330"]}
    fin["peer_summary"] = {**summary, "calculation_basis": "只用 peer 角色（2379、3034）平均，排除 2330"}
    pv = {"subject": "2454", "comparators": ["2379", "3034", "2330"], "metrics": metrics,
          "price_as_of": PRICE_DATE, "cutoff": CUTOFF, "method_version": "peer-v1.2",
          "snapshot_ids": {t: f"snap-{t}-2026Q2" for t in ("2454", "2379", "3034", "2330")}}
    C.append(case("TR-28", "calculate_metrics",
                  {"operation": "peer_comparison", "values": pv, "evidence_refs": ["snap-2454-2026Q2", "finmind_price"]},
                  resp("calculate_metrics", "ok", {"subject": "2454", "comparison_table": table,
                                                   "peer_average_stats": summary, "is_applicable": True,
                                                   "reason": None, "operation": "peer_comparison",
                                                   "evidence_refs": ["snap-2454-2026Q2", "finmind_price"]}),
                  note="2330 為 industry_reference，不入同業平均"))
    bad = {**pv, "comparators": ["2379", "2317"],
           "snapshot_ids": {"2454": "snap-2454-2026Q2", "2379": "snap-2379-2026Q2", "2317": "snap-2317-2026Q2"},
           "metrics": {k: metrics[k] for k in ("2454", "2379")}}
    C.append(case("TR-29", "calculate_metrics",
                  {"operation": "peer_comparison", "values": bad, "evidence_refs": ["snap-2454-2026Q2"]},
                  resp("calculate_metrics", "invalid_input", reason="比較標的只限 ('2379', '3034', '2330')，收到 ['2317']"),
                  check="status_only"))
    C.append(case("TR-30", "calculate_metrics",
                  {"operation": "pb_ratio", "values": {"price": p, "bvps": c54["market_snapshot"]["bvps"]},
                   "evidence_refs": ["snap-2454-2026Q2"]},
                  resp("calculate_metrics", "invalid_input", reason="calculate_metrics.operation='pb_ratio' 不在允許值"),
                  check="status_only", note="P/B 只在 peer_comparison 內計算，不新增 operation"))

    # --- 工具異常 ------------------------------------------------------------
    C.append(case("TR-31", "read_evidence", {"evidence_version_id": "ev-2317-2026q2-consolidated"},
                  resp("read_evidence", "tool_error", reason="TimeoutError: read_evidence 逾時"),
                  job_cutoff=DEV_CASES["CASE-26"]["cutoff_at"], job_snapshot="snap-dev-case-26", synthetic=True,
                  check="status_only", note="CASE-26；由 dispatch 包成 tool_error，job 不得崩潰、不得發布未核實結果"))

    return {
        "fixture_version": FIXTURE_VERSION,
        "contract_version": CONTRACT_VERSION,
        "generated_by": "scripts/build_w02_fixtures.py",
        "source_snapshot": {"file": "data/financial-snapshots.json", "sha256": SNAP_HASH},
        "status_enum": STATUS_ENUM,
        "response_shape": ["status", "tool", "reason", "data"],
        "check_modes": {"exact": "整個 expected_response 必須相同",
                        "status_only": "只比 status；reason 為參考文字",
                        "fields": "比 status 與 data 中列出的數值欄位"},
        "scope": ("TR-xx 是六工具的契約 fixture，不是研究評估案例，不計入固定 30 案（10 開發 + 20 保留）。"
                  "只引用開發集 CASE-15、CASE-26 的快照；不引用任何保留案例。"),
        "note": ("預期回傳為 W02 契約規格。真實數字取自快照；synthetic_fixture=true 為人工構造之錯誤輸入或擾動，"
                 "不作為財務數字來源。"),
        "responses": C,
    }


def main() -> None:
    fin = build_financial_fixtures()
    tools = build_tool_responses(fin)
    OUT_FIN.write_text(json.dumps(fin, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    OUT_TOOL.write_text(json.dumps(tools, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"寫入 {OUT_FIN.relative_to(ROOT)}（{len(fin['companies'])} 家公司、{len(SYNTHETIC_EXAMPLES)} 個合成例）")
    print(f"寫入 {OUT_TOOL.relative_to(ROOT)}（{len(tools['responses'])} 個工具 fixture，不計入 30 案）")


if __name__ == "__main__":
    main()