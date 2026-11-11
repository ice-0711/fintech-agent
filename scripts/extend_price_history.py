"""把 data/financial-snapshots.json 的股價從 5 個交易日補成完整歷史（組長 2026-11-11 決定，決策 25）。

    .venv/bin/python scripts/extend_price_history.py            # 抓資料、核對、寫入
    .venv/bin/python scripts/extend_price_history.py --check    # 只抓資料與核對，不寫入

為什麼：原快照只留 cutoff（2026-09-30）前 5 個交易日的收盤價，但多數案例的 cutoff 在 7、8 月，
get_price_window 依「不看未來」規則只能回 no_data，估值段落幾乎都寫未知。資料本來就公開可得，
缺的是快照沒收，不是 Agent 查不到。

只動股價：財報、總經、證據、公告時間都不重抓、不改。快照 cutoff 仍是 2026-09-30。
- 來源與口徑不變：FinMind TaiwanStockPrice，未還原收盤價（raw_close）。
- 原始回應存 data/raw/finmind/ 並記 sha256，附加到 source_manifest.raw_files；原 5 日的原始檔紀錄保留。
- 新資料必須包含原本 5 個交易日且收盤價完全相同，最後交易日必須是 2026-09-30；不符即中止、不寫入。
- 可得時間仍由工具依規則計算（交易日 17:30），案例 cutoff 之後的價格工具不會給。

這是第一段凍結檔的變更，寫入後要重新凍結（scripts/build_freeze.py）。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
SNAP = ROOT / "data" / "financial-snapshots.json"
RAW_DIR = ROOT / "data" / "raw" / "finmind"
API = "https://api.finmindtrade.com/api/v4/data"
TZ = timezone(timedelta(hours=8))
START, END = "2025-01-01", "2026-09-30"   # START 與財報起點（FS_START）相同
MANIFEST_VERSION = "v1.7-price-history"


def die(msg: str) -> None:
    sys.exit(f"中止：{msg}")


def fetch(ticker: str) -> tuple[list[dict], dict, bytes]:
    token = os.environ.get("FINMIND_TOKEN")  # 沒有也可以抓（額度較低），不讀 .env
    r = requests.get(API, headers={"Authorization": f"Bearer {token}"} if token else {},
                     params={"dataset": "TaiwanStockPrice", "data_id": ticker, "start_date": START, "end_date": END},
                     timeout=60)
    if r.status_code != 200:
        die(f"HTTP {r.status_code}：TaiwanStockPrice {ticker}")
    js = r.json()
    if js.get("status") != 200:
        die(f"FinMind 回應異常：{ticker} -> {js.get('msg')}")
    sha = hashlib.sha256(r.content).hexdigest()
    entry = {"dataset": "TaiwanStockPrice", "data_id": ticker, "start": START, "end": END,
             "captured_at": datetime.now(TZ).isoformat(timespec="seconds"), "sha256": sha,
             "file": f"data/raw/finmind/TaiwanStockPrice_{ticker}_{sha[:12]}.json"}
    return js.get("data", []), entry, r.content


def rows_for(ticker: str, data: list[dict], old: list[dict]) -> list[dict]:
    rows = sorted(({"trade_date": d["date"], "close": float(d["close"])} for d in data
                   if d.get("close") and float(d["close"]) > 0 and START <= d["date"] <= END),
                  key=lambda x: x["trade_date"])
    if len({x["trade_date"] for x in rows}) != len(rows):
        die(f"[{ticker}] 交易日重複")
    if not rows or rows[-1]["trade_date"] != END:
        die(f"[{ticker}] 最後交易日應為 {END}")
    by_date = {x["trade_date"]: x["close"] for x in rows}
    for o in old:
        if by_date.get(o["trade_date"]) != o["close"]:
            die(f"[{ticker}] {o['trade_date']} 新舊收盤價不一致（舊 {o['close']}，新 {by_date.get(o['trade_date'])}）")
    return rows


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="只抓資料與核對，不寫入")
    args = ap.parse_args(argv)
    snap = json.loads(SNAP.read_text(encoding="utf-8"))
    if snap.get("manifest_version") == MANIFEST_VERSION:
        die("快照已是補過股價的版本，不重做")
    prices, entries, blobs = {}, [], []
    for t in snap["prices"]:
        data, entry, content = fetch(t)
        prices[t] = rows_for(t, data, snap["prices"][t])
        entries.append(entry)
        blobs.append((ROOT / entry["file"], content))
        print(f"{t}: {len(prices[t])} 個交易日（{prices[t][0]['trade_date']} 至 {prices[t][-1]['trade_date']}），"
              f"原 {len(snap['prices'][t])} 日收盤價相同")
    if args.check:
        print("只核對，未寫入")
        return 0
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    for path, content in blobs:
        path.write_bytes(content)
    # 原 5 日的原始檔紀錄保留在前（那 5 日已與 TWSE 對帳，同業快照與工具 fixture 引用其 hash）；新檔附加在後。
    # get_price_window 依視窗日期選涵蓋該區間的原始檔（agents/tools_impl.py _raw_file_covering）。
    snap["source_manifest"]["raw_files"] += entries
    snap["prices"] = prices
    snap["manifest_version"] = MANIFEST_VERSION
    snap["price_history_added_at"] = datetime.now(TZ).isoformat(timespec="seconds")
    snap["price_history_note"] = (f"財報、總經、證據沿用原快照；只把 5 檔股價由 cutoff 前 5 個交易日補為 {START} 至 {END} "
                                  "的全部交易日（未還原收盤價，原 5 日數值相同）。組長 2026-11-11 決定，scripts/extend_price_history.py")
    tmp = SNAP.with_suffix(".json.tmp")
    nl = "\r\n" if b"\r\n" in SNAP.read_bytes() else "\n"   # 沿用原檔換行（B 在 Windows 產生，CRLF），diff 只留真正的變更
    tmp.write_text(json.dumps(snap, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline=nl)
    tmp.replace(SNAP)
    print(f"已寫入 {SNAP.relative_to(ROOT)}（{MANIFEST_VERSION}）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
