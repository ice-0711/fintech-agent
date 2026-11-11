"""把 data/financial-snapshots.json 的每日收盤價逐日和證交所 STOCK_DAY 對帳（組長 2026-11-11，決策 25）。

    .venv/bin/python scripts/check_prices_twse.py

原快照的 5 個交易日已由 B 對過 TWSE（data-contract.md 第 228 行）。股價補成完整歷史後，新增的交易日
用這支程式對帳。TWSE 原始回應存 data/raw/twse/（不進 git），結果寫 data/price-history-twse-check.json。
只讀不改快照；有任何一天對不上就以非 0 結束。
"""

from __future__ import annotations

import hashlib
import json
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
SNAP = ROOT / "data" / "financial-snapshots.json"
RAW = ROOT / "data" / "raw" / "twse"
OUT = ROOT / "data" / "price-history-twse-check.json"
URL = "https://www.twse.com.tw/exchangeReport/STOCK_DAY"
TZ = timezone(timedelta(hours=8))


def month(ticker: str, ym: str) -> tuple[dict[str, float], str]:
    for attempt in range(4):
        r = requests.get(URL, params={"response": "json", "date": ym.replace("-", "") + "01", "stockNo": ticker},
                         headers={"User-Agent": "fintech-agent-capstone price check"}, timeout=60)
        if r.status_code == 200 and r.json().get("stat") == "OK":
            break
        time.sleep(10 * (attempt + 1))
    else:
        sys.exit(f"中止：TWSE {ticker} {ym} 取不到資料")
    RAW.mkdir(parents=True, exist_ok=True)
    sha = hashlib.sha256(r.content).hexdigest()
    (RAW / f"STOCK_DAY_{ticker}_{ym}_{sha[:12]}.json").write_bytes(r.content)
    js = r.json()
    i = js["fields"].index("收盤價")
    out = {}
    for row in js["data"]:
        y, m, d = row[0].split("/")
        try:
            out[f"{int(y) + 1911}-{m}-{d}"] = float(row[i].replace(",", ""))
        except ValueError:
            continue  # 當日無成交（"--"）
    return out, sha


def main() -> int:
    prices = json.loads(SNAP.read_text(encoding="utf-8"))["prices"]
    result, bad = {}, []
    for t, rows in prices.items():
        months = sorted({r["trade_date"][:7] for r in rows})
        twse, shas = {}, []
        for ym in months:
            d, sha = month(t, ym)
            twse.update(d)
            shas.append({"month": ym, "sha256": sha})
            time.sleep(3)
        mism = [{"trade_date": r["trade_date"], "snapshot": r["close"], "twse": twse.get(r["trade_date"])}
                for r in rows if twse.get(r["trade_date"]) != r["close"]]
        first, last = rows[0]["trade_date"], rows[-1]["trade_date"]
        extra = sorted(d for d in twse if first <= d <= last and d not in {r["trade_date"] for r in rows})
        result[t] = {"days": len(rows), "matched": len(rows) - len(mism), "mismatches": mism,
                     "twse_days_not_in_snapshot": extra, "twse_raw": shas}
        bad += [(t, m) for m in mism]
        print(f"{t}: {len(rows)} 日，相符 {len(rows) - len(mism)}，不符 {len(mism)}，TWSE 有而快照沒有 {len(extra)} 日")
    OUT.write_text(json.dumps({"checked_at": datetime.now(TZ).isoformat(timespec="seconds"),
                               "source": "TWSE exchangeReport/STOCK_DAY（收盤價，未還原）",
                               "snapshot": "data/financial-snapshots.json", "result": result},
                              ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
