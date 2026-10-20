"""scripts/build_peer_snapshot.py — W04-B 由快照重建 data/v12-peer-snapshot.json

- 主體 2454；同業 2379、3034；產業參照 2330（不入同業平均）。
- 所有數字由 data/financial-snapshots.json 計算，不手打；同一基準日 2026-09-30 收盤價。
- 每家附財報快照 ID／hash／可得時間，與股價原始檔 hash／可得時間（交易日 17:30）。
- 缺值為 null 並附原因；DCF 參數待組長核定前不計算差距。

執行：python scripts/build_peer_snapshot.py
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "data" / "financial-snapshots.json"
OUT = ROOT / "data" / "v12-peer-snapshot.json"
TW = timezone(timedelta(hours=8))

PRICE_AS_OF = "2026-09-30"
CUTOFF = "2026-09-30T17:30:00+08:00"
TTM_PERIODS = ["2025Q3", "2025Q4", "2026Q1", "2026Q2"]
COMPANIES = {  # 代號: (簡稱, 角色)
    "2454": ("聯發科", "subject"),
    "2379": ("瑞昱", "peer"),
    "3034": ("聯詠", "peer"),
    "2330": ("台積電", "industry_reference"),
}


def raw_file(snap, dataset, ticker):
    return next((r for r in snap["source_manifest"]["raw_files"]
                 if r["dataset"] == dataset and r["data_id"] == ticker), {})


def build() -> dict:
    snap = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    out_companies = {}
    for code, (name, role) in COMPANIES.items():
        q = {x["period"]: x for x in snap["financials"][code]["quarters"]}
        last4 = [q.get(p) for p in TTM_PERIODS]
        complete = all(r is not None for r in last4)
        eps_ok = complete and all(r["eps"] is not None and r["eps_source"] != "unverified" for r in last4)
        fcf_ok = complete and all(r["free_cash_flow"] is not None for r in last4)
        eps_ttm = round(sum(r["eps"] for r in last4), 2) if eps_ok else None
        fcf_ttm = round(sum(r["free_cash_flow"] for r in last4), 2) if fcf_ok else None
        latest = q["2026Q2"]
        price_row = next((p for p in snap["prices"][code] if p["trade_date"] == PRICE_AS_OF), None)
        price = price_row["close"] if price_row else None
        bvps = latest.get("bvps")
        base = q.get("2025Q2", {}).get("revenue")
        yoy = round(latest["revenue"] / base - 1, 4) if base else None
        praw = raw_file(snap, "TaiwanStockPrice", code)
        fraw = raw_file(snap, "TaiwanStockFinancialStatements", code)

        out_companies[code] = {
            "name": name,
            "role": role,
            "include_in_peer_stats": role == "peer",
            "financial_period": "2026Q2",
            "currency": "TWD",
            "statement_basis": "consolidated",
            "close_price": price,
            "close_price_unit": "TWD/share",
            "price_basis": "raw_close",
            "close_price_source": "FinMind TaiwanStockPrice，與 TWSE STOCK_DAY 2026-09 原始檔逐日比對一致",
            "price_available_at": f"{PRICE_AS_OF}T17:30:00+08:00",
            "price_available_at_basis": "rule_close_1730",
            "price_source_id": "finmind_price",
            "price_content_hash": praw.get("sha256"),
            "eps_ttm": eps_ttm,
            "eps_ttm_periods": TTM_PERIODS,
            "eps_quarters": {p: q[p]["eps_source"] for p in TTM_PERIODS if p in q},
            "pe_ttm": round(price / eps_ttm, 2) if (price and eps_ttm and eps_ttm > 0) else None,
            "pe_na_reason": None if (price and eps_ttm and eps_ttm > 0) else "收盤價或 EPS TTM 缺失／非正",
            "bvps": bvps,
            "pb_ratio": round(price / bvps, 2) if (price and bvps and bvps > 0) else None,
            "pb_na_reason": None if (price and bvps and bvps > 0) else "收盤價或 BVPS 缺失／非正",
            "revenue_yoy_quarter": yoy,
            "revenue_yoy_basis": "2026Q2 單季營收 ÷ 2025Q2 單季營收 − 1",
            "fcf_ttm_100m": fcf_ttm,
            "dcf_intrinsic_value": None,
            "dcf_gap_pct": None,
            "dcf_status": "WACC、g 待組長核定，未計算",
            "financial_snapshot_id": latest["snapshot_id"],
            "financial_source_id": latest["source_id"],
            "financial_content_hash": latest["content_hash"],
            "financial_available_at": latest["available_at"],
            "financial_available_at_basis": "official",
            "financial_captured_at": fraw.get("captured_at"),
            "evidence_refs": [f"ev-{code}-2026q2-01"],
        }

    peers = [c for c in out_companies.values() if c["role"] == "peer"]
    avg = lambda key, nd: (round(sum(v) / len(v), nd) if (v := [c[key] for c in peers if c[key] is not None]) else None)
    return {
        "snapshot_version": "v1.7-w04",
        "generated_by": "scripts/build_peer_snapshot.py",
        "generated_at": datetime.now(TW).isoformat(timespec="seconds"),
        "verified_by": "Team Member B",
        "synthetic_fixture": False,
        "subject": "2454",
        "benchmark_reference": "2330",
        "price_as_of": PRICE_AS_OF,
        "cutoff_at": CUTOFF,
        "source_snapshot": {"file": "data/financial-snapshots.json",
                            "manifest_version": json.loads(SNAPSHOT.read_text(encoding="utf-8"))["manifest_version"]},
        "rule_constraints": [
            "最多 4 家公司（主體 2454 + 同業 2379、3034 + 產業參照 2330）",
            "2330 僅作為產業參照，不計入同業平均",
            "所有公司使用同一基準日 2026-09-30 未還原收盤價；各自財報期與來源明示",
            "同業比較僅跑確定性計算工具，0 次 LLM 呼叫",
        ],
        "companies": out_companies,
        "peer_summary_statistics": {
            "calculation_basis": "僅以 peer 角色（2379、3034）計算平均，完全排除 2330 與主體",
            "peer_avg_pe": avg("pe_ttm", 2),
            "peer_avg_pb": avg("pb_ratio", 2),
            "peer_avg_revenue_yoy": avg("revenue_yoy_quarter", 4),
            "peer_avg_fcf_ttm_100m": avg("fcf_ttm_100m", 2),
            "n_peers": len(peers),
            "excluded_entities": ["2330"],
        },
    }


def main() -> None:
    out = build()
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    s = out["peer_summary_statistics"]
    print(f"寫入 {OUT.relative_to(ROOT)}：peer_avg_pe={s['peer_avg_pe']}、peer_avg_pb={s['peer_avg_pb']}、"
          f"peer_avg_revenue_yoy={s['peer_avg_revenue_yoy']}")


if __name__ == "__main__":
    main()