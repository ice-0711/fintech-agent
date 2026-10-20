#!/usr/bin/env python3
"""scripts/verify_fact_sheet.py — 重現 v12-finance-fact-sheet.md V1.7 的數字（組員 B）

所有數字由 data/financial-snapshots.json 計算；DCF 由 dcf_model.calculate_dcf_details 計算。
與 fact sheet 不一致時列出差異並以非零結束碼退出。
用法：python scripts\\verify_fact_sheet.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from valuation_agent.dcf_model import calculate_dcf_details  # 若路徑不同，請依實際位置調整

SNAP = ROOT / "data" / "financial-snapshots.json"
SUBJECT, PEERS, REF = "2454", ["2379", "3034"], "2330"
LAST4 = ["2025Q3", "2025Q4", "2026Q1", "2026Q2"]
WACC, G = 0.10, 0.03            # dcf_model 預設值，待組長核定
TOL = 0.01

EXPECT = {                      # 與 fact sheet 第二、四、五節一致
    "2454": {"pe": 81.07, "pb": 18.51, "eps_ttm": 60.69, "fcf_ttm": 920.63},
    "2379": {"pe": 27.41, "pb": 7.77, "eps_ttm": 27.73, "fcf_ttm": 168.21},
    "3034": {"pe": 19.04, "pb": 4.82, "eps_ttm": 28.67, "fcf_ttm": 167.49},
    "2330": {"pe": 28.74, "pb": 10.00, "eps_ttm": 86.28, "fcf_ttm": 11435.56},
    "peer": {"pe": 23.23, "pb": 6.29, "yoy": 0.1363},
    "dcf": {"iv": 853.27},
}


def load():
    return json.loads(SNAP.read_text(encoding="utf-8"))


def company_metrics(d, t):
    qs = {q["period"]: q for q in d["financials"][t]["quarters"]}
    for p in LAST4:
        if p not in qs:
            raise SystemExit(f"[中止] {t} 缺少 {p}")
        if qs[p]["eps_source"] == "unverified":
            raise SystemExit(f"[中止] {t} {p} EPS 為 unverified，不得用於 TTM")
    eps_ttm = sum(qs[p]["eps"] for p in LAST4)
    fcf_ttm = sum(qs[p]["free_cash_flow"] for p in LAST4)
    latest = qs["2026Q2"]
    price = next(p["close"] for p in d["prices"][t] if p["trade_date"] == "2026-09-30")
    yoy = qs["2026Q2"]["revenue"] / qs["2025Q2"]["revenue"] - 1
    pe = price / eps_ttm if eps_ttm > 0 else None
    pb = price / latest["bvps"] if latest["bvps"] > 0 else None
    return {
        "price": price, "eps_ttm": round(eps_ttm, 2), "fcf_ttm": round(fcf_ttm, 2),
        "pe": round(pe, 2) if pe else None, "pb": round(pb, 2) if pb else None,
        "yoy": yoy, "bvps": latest["bvps"], "net_debt": latest["net_debt"],
        "shares": latest["shares_outstanding"],
    }


def main():
    d = load()
    m = {t: company_metrics(d, t) for t in [SUBJECT] + PEERS + [REF]}

    peer_pe = sum(m[t]["pe"] for t in PEERS) / len(PEERS)
    peer_pb = sum(m[t]["pb"] for t in PEERS) / len(PEERS)
    peer_yoy = sum(m[t]["yoy"] for t in PEERS) / len(PEERS)

    s = m[SUBJECT]
    dcf = calculate_dcf_details(
        free_cash_flows=[s["fcf_ttm"]] * 5, wacc=WACC, terminal_growth=G,
        net_debt=s["net_debt"], shares_outstanding=s["shares"],
    )["intrinsic_value_per_share"]

    got = {
        "2454": {"pe": s["pe"], "pb": s["pb"], "eps_ttm": s["eps_ttm"], "fcf_ttm": s["fcf_ttm"]},
        "2379": {"pe": m["2379"]["pe"], "pb": m["2379"]["pb"], "eps_ttm": m["2379"]["eps_ttm"], "fcf_ttm": m["2379"]["fcf_ttm"]},
        "3034": {"pe": m["3034"]["pe"], "pb": m["3034"]["pb"], "eps_ttm": m["3034"]["eps_ttm"], "fcf_ttm": m["3034"]["fcf_ttm"]},
        "2330": {"pe": m["2330"]["pe"], "pb": m["2330"]["pb"], "eps_ttm": m["2330"]["eps_ttm"], "fcf_ttm": m["2330"]["fcf_ttm"]},
        "peer": {"pe": round(peer_pe, 2), "pb": round(peer_pb, 2), "yoy": round(peer_yoy, 4)},
        "dcf": {"iv": dcf},
    }

    bad = []
    for key, exp in EXPECT.items():
        for k, v in exp.items():
            g = got[key][k]
            if g is None or abs(g - v) > TOL:
                bad.append(f"{key}.{k}: 文件 {v} ≠ 計算 {g}")

    for t in [SUBJECT] + PEERS + [REF]:
        print(t, m[t])
    print("peer 平均 PE/PB/YoY：", round(peer_pe, 2), round(peer_pb, 2), round(peer_yoy, 4))
    print("DCF 每股內在價值（WACC 10%、g 3%）：", dcf)

    if bad:
        print("\n不一致：")
        print("\n".join(bad))
        sys.exit(1)
    print("\n全部數字與 fact sheet 一致 ✅")


if __name__ == "__main__":
    main()