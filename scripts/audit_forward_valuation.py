"""scripts/audit_forward_valuation.py — W08-B 前瞻快照 DCF／P/E 獨立重算（B 稽核用，不是 Agent 工具）

用途：每批前瞻快照產生後，B 不經過 agents/ 的程式，直接從快照 JSON 重算
TTM EPS、P/E、P/B、TTM FCF、DCF 每股與估值差距，再和報告／工具結果比對。
兩邊算法獨立，數字一致才代表工具沒有算錯。

規則（data-contract.md、組長 2026-10-21 核定）：
- TTM：最新 4 個連續單季相加；不足 4 季或 EPS 未經原文驗證（eps_source 不是 mops_direct／
  finmind_quarterly）→ null，不以單季 × 4 推估
- P/E = 快照最後一個收盤價 ÷ TTM EPS；P/B = 收盤價 ÷ 最新一季 BVPS；分母 ≤ 0 → null
- DCF：WACC 9%、終端成長 3%、5 年持平於 TTM FCF；TTM FCF ≤ 0 → null（無法判定）
  每股 = (5 年折現 + 終端值折現 − 淨負債) ÷ 流通股數
- 估值差距 = (DCF 每股 − 收盤價) ÷ 收盤價；±15% 為本專題顯示門檻

用法：
  python scripts/audit_forward_valuation.py data/financial-snapshots.json
  python scripts/audit_forward_valuation.py data/forward/financial-snapshots-2026-11-06.json --csv evaluation/forward/valuation-audit-2026-11-06.csv
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

WACC, G, YEARS, GAP = 0.09, 0.03, 5, 0.15
VERIFIED_EPS = {"mops_direct", "finmind_quarterly"}
PERIOD_ORDER = {"Q1": 1, "Q2": 2, "Q3": 3, "Q4": 4}


def _key(period: str) -> int:
    return int(period[:4]) * 4 + PERIOD_ORDER[period[4:]]


def _consecutive(periods: list[str]) -> bool:
    keys = [_key(p) for p in periods]
    return all(b - a == 1 for a, b in zip(keys, keys[1:]))


def audit_company(ticker: str, quarters: list[dict], closes: list[dict]) -> dict:
    qs = sorted(quarters, key=lambda q: _key(q["period"]))
    last4 = qs[-4:]
    row: dict = {"ticker": ticker, "latest_period": qs[-1]["period"] if qs else None,
                 "ttm_periods": ";".join(q["period"] for q in last4)}
    reasons = []
    ttm_ok = len(last4) == 4 and _consecutive([q["period"] for q in last4])
    if not ttm_ok:
        reasons.append("不足 4 個連續單季")
    eps_ok = ttm_ok and all(q.get("eps_source") in VERIFIED_EPS for q in last4)
    if ttm_ok and not eps_ok:
        reasons.append("TTM 內有未驗證 EPS")
    row["ttm_eps"] = round(sum(q["eps"] for q in last4), 2) if eps_ok else None
    row["ttm_fcf"] = round(sum(q["free_cash_flow"] for q in last4), 2) if ttm_ok else None

    close = closes[-1]["close"] if closes else None
    row["price_as_of"] = closes[-1]["trade_date"] if closes else None
    row["close"] = close
    bvps = qs[-1].get("bvps") if qs else None
    row["pe_ttm"] = round(close / row["ttm_eps"], 2) if close and row["ttm_eps"] and row["ttm_eps"] > 0 else None
    row["pb"] = round(close / bvps, 2) if close and bvps and bvps > 0 else None

    fcf = row["ttm_fcf"]
    if fcf is None or fcf <= 0:
        row["dcf_per_share"] = None
        reasons.append("TTM FCF 為負或缺值，DCF 無法判定" if fcf is not None else "TTM FCF 缺值")
    else:
        pv = sum(fcf / (1 + WACC) ** i for i in range(1, YEARS + 1))
        tv = fcf * (1 + G) / (WACC - G) / (1 + WACC) ** YEARS
        equity = pv + tv - qs[-1]["net_debt"]                       # 億元
        row["dcf_per_share"] = round(equity * 1e8 / (qs[-1]["shares_outstanding"] * 1e6), 2)
    if row["dcf_per_share"] is not None and close:
        gap = (row["dcf_per_share"] - close) / close
        row["dcf_gap"] = round(gap, 4)
        row["valuation_status"] = ("above_model" if gap < -GAP else "below_model" if gap > GAP else "near_model")
    else:
        row["dcf_gap"], row["valuation_status"] = None, "undeterminable"
    row["notes"] = "；".join(reasons)
    return row


def audit(snapshot_path: Path) -> list[dict]:
    snap = json.loads(snapshot_path.read_text(encoding="utf-8"))
    prices = snap.get("prices", {})
    return [audit_company(t, body.get("quarters", []), prices.get(t, []))
            for t, body in snap.get("financials", {}).items()]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="前瞻快照 DCF／P/E 獨立重算")
    ap.add_argument("snapshot")
    ap.add_argument("--csv", help="輸出 CSV（建議放 evaluation/forward/，不要放 data/forward/）")
    args = ap.parse_args(argv)
    rows = audit(Path(args.snapshot))
    cols = ["ticker", "latest_period", "ttm_periods", "ttm_eps", "ttm_fcf", "price_as_of", "close",
            "pe_ttm", "pb", "dcf_per_share", "dcf_gap", "valuation_status", "notes"]
    if args.csv:
        out = Path(args.csv)
        if "data" in out.parts and "forward" in out.parts:
            sys.exit("[中止] 稽核結果不可寫進 data/forward（Agent 讀得到的位置）")
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=cols)
            w.writeheader()
            w.writerows(rows)
    for r in rows:
        print("  ".join(f"{c}={r[c]}" for c in cols if r.get(c) not in (None, "")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())