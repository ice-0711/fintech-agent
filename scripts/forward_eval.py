"""scripts/forward_eval.py — W07-D 前瞻評估 runner（離線、決定性、不連網、不呼叫模型）

依手冊第 06 章與 research/forward-batch-1-sources.json 的 price_basis 規約：
  entry   = 訊號截止時間（cutoff）之後下一個台股交易日的「開盤價」，該日是第 1 個持有交易日
  exit    = 第 1／5／20 個持有交易日的「收盤價」（D1 = entry 當日收盤）
  報酬    = (price_exit - price_entry) / price_entry；開盤、收盤都用未還原（raw）價格，不混調整價
  NA      = 觀察窗未滿、窗口超出交易日曆、缺開盤或缺收盤、停牌（成交量 0）、cutoff 尚未到；一律記原因，不補值
  方向    = 只有 direction 為 up／down 的訊號才計方向命中；none／空值只展示路徑，不計命中
  除權息  = 觀察窗內有除息日時只標記 corporate_action_in_window，raw 報酬照算，不自行還原

「前瞻價格不回流 Agent」的做法：
  1. 本程式不 import agents／research_ui 任何模組（tests 以 ast 檢查）
  2. 輸出路徑若在 data/forward、fixtures、agents 之下一律拒絕寫入（Agent 工具只讀這些位置）
  3. --as-of 必須明確指定（不讀系統時間），同樣輸入一定得到同樣輸出
價格檔請放在 evaluation/ 底下，不要放進 data/forward。

輸入格式
  --signals   JSON：{"batch_id": "...", "signals": [{"signal_id","ticker","signal_cutoff_at","direction"}]}
              direction 為 "up"、"down"、"none" 或 null
  --prices    CSV：ticker,trade_date,open,close,volume（FinMind TaiwanStockPrice 的 Trading_Volume 也可）
  --calendar  CSV：一欄 date（FinMind TaiwanStockTradingDate 的實際交易日；颱風假等以實際為準）
  --actions   JSON（選填）：[{"ticker","ex_date"}]，來源見 forward-batch-1-sources.json corporate_actions
  --as-of     ISO 時間（含 +08:00），代表「截取結果的時刻」；收盤價在交易日 17:30 之後才算可得
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

TPE = timezone(timedelta(hours=8))
HORIZONS = (1, 5, 20)
MARKET_OPEN = time(9, 0)
CLOSE_AVAILABLE = time(17, 30)  # rule_close_1730：組長 2026-10-22 核定全專案統一
FORBIDDEN_OUT_PARTS = (("data", "forward"), ("fixtures",), ("agents",))
VALID_DIRECTIONS = {"up", "down", "none", None}

NA_REASONS = {
    "cutoff_not_reached": "訊號截止時間尚未到（as_of 早於 cutoff）",
    "calendar_missing_entry": "交易日曆沒有 cutoff 之後的交易日，無法決定 entry",
    "window_beyond_calendar": "第 k 個持有交易日超出交易日曆（觀察窗未滿或日曆未涵蓋）",
    "immature": "exit 日收盤價在 as_of 時尚未可得（觀察窗未成熟）",
    "missing_entry_open": "entry 日缺開盤價",
    "missing_exit_close": "exit 日缺收盤價",
    "suspended_entry": "entry 日停牌（成交量為 0）",
    "suspended_exit": "exit 日停牌（成交量為 0）",
}


# ───────────────────────── 讀檔 ─────────────────────────

def parse_dt(text: str) -> datetime:
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        raise ValueError(f"時間必須含時區（+08:00）：{text}")
    return dt.astimezone(TPE)


def load_calendar(path: Path) -> list[date]:
    days: set[date] = set()
    with open(path, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            raw = (row.get("date") or row.get("trade_date") or "").strip()
            if raw:
                days.add(date.fromisoformat(raw))
    return sorted(days)


def _num(value: str | None) -> float | None:
    if value is None:
        return None
    value = value.strip().replace(",", "")
    if value in ("", "NA", "null", "None", "-"):
        return None
    return float(value)


def load_prices(path: Path) -> dict[tuple[str, date], dict]:
    prices: dict[tuple[str, date], dict] = {}
    with open(path, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            ticker = (row.get("ticker") or row.get("stock_id") or "").strip()
            raw_date = (row.get("trade_date") or row.get("date") or "").strip()
            if not ticker or not raw_date:
                continue
            vol = _num(row.get("volume") if "volume" in row else row.get("Trading_Volume"))
            prices[(ticker, date.fromisoformat(raw_date))] = {
                "open": _num(row.get("open")),
                "close": _num(row.get("close")),
                "volume": vol,
            }
    return prices


def load_signals(path: Path) -> tuple[str, list[dict]]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    signals = data["signals"]
    for s in signals:
        if s.get("direction") not in VALID_DIRECTIONS:
            raise ValueError(f"{s.get('signal_id')}: direction 只能是 up／down／none／null")
    return data.get("batch_id", ""), signals


def load_actions(path: Path | None) -> list[dict]:
    if path is None:
        return []
    return json.loads(Path(path).read_text(encoding="utf-8"))


# ───────────────────────── 計算 ─────────────────────────

def find_entry_index(calendar: list[date], cutoff: datetime) -> int | None:
    """cutoff 之後第一個「開盤時間晚於 cutoff」的交易日；cutoff 21:00 時就是下一個交易日。"""
    for i, d in enumerate(calendar):
        if datetime.combine(d, MARKET_OPEN, tzinfo=TPE) > cutoff:
            return i
    return None


def _price_problem(row: dict | None, field: str, side: str) -> str | None:
    if row is None or row.get(field) in (None, 0):
        if row is not None and row.get("volume") == 0:
            return f"suspended_{side}"
        return f"missing_{side}_{'open' if field == 'open' else 'close'}"
    if row.get("volume") == 0:
        return f"suspended_{side}"
    return None


def evaluate_signal(signal: dict, calendar: list[date], prices: dict, as_of: datetime,
                    actions: list[dict]) -> dict:
    ticker = str(signal["ticker"])
    cutoff = parse_dt(signal["signal_cutoff_at"])
    direction = signal.get("direction")
    row: dict = {
        "signal_id": signal["signal_id"], "ticker": ticker,
        "signal_cutoff_at": signal["signal_cutoff_at"], "direction": direction or "none",
        "entry_date": "", "entry_open": "",
    }
    ex_dates = sorted({date.fromisoformat(a["ex_date"]) for a in actions if str(a["ticker"]) == ticker})

    def na_all(reason: str) -> dict:
        for k in HORIZONS:
            row.update({f"d{k}_exit_date": "", f"d{k}_exit_close": "", f"d{k}_return": "",
                        f"d{k}_status": "NA", f"d{k}_na_reason": reason,
                        f"d{k}_corporate_action_in_window": "", f"d{k}_direction_hit": ""})
        return row

    if as_of < cutoff:
        return na_all("cutoff_not_reached")
    entry_idx = find_entry_index(calendar, cutoff)
    if entry_idx is None:
        return na_all("calendar_missing_entry")

    entry_date = calendar[entry_idx]
    entry_row = prices.get((ticker, entry_date))
    entry_problem = _price_problem(entry_row, "open", "entry")
    row["entry_date"] = entry_date.isoformat()
    if entry_problem is None:
        row["entry_open"] = entry_row["open"]

    for k in HORIZONS:
        out = {f"d{k}_exit_date": "", f"d{k}_exit_close": "", f"d{k}_return": "",
               f"d{k}_status": "NA", f"d{k}_na_reason": "",
               f"d{k}_corporate_action_in_window": "", f"d{k}_direction_hit": ""}
        exit_idx = entry_idx + k - 1  # entry 當日是第 1 個持有交易日
        if exit_idx >= len(calendar):
            out[f"d{k}_na_reason"] = "window_beyond_calendar"
            row.update(out)
            continue
        exit_date = calendar[exit_idx]
        out[f"d{k}_exit_date"] = exit_date.isoformat()
        if as_of < datetime.combine(exit_date, CLOSE_AVAILABLE, tzinfo=TPE):
            out[f"d{k}_na_reason"] = "immature"
            row.update(out)
            continue
        if entry_problem is not None:
            out[f"d{k}_na_reason"] = entry_problem
            row.update(out)
            continue
        exit_row = prices.get((ticker, exit_date))
        exit_problem = _price_problem(exit_row, "close", "exit")
        if exit_problem is not None:
            out[f"d{k}_na_reason"] = exit_problem
            row.update(out)
            continue
        ret = (exit_row["close"] - entry_row["open"]) / entry_row["open"]
        in_window = [d.isoformat() for d in ex_dates if entry_date <= d <= exit_date]
        out[f"d{k}_exit_close"] = exit_row["close"]
        out[f"d{k}_return"] = round(ret, 6)
        out[f"d{k}_status"] = "ok"
        out[f"d{k}_corporate_action_in_window"] = ";".join(in_window)
        if direction in ("up", "down"):
            if ret == 0:
                out[f"d{k}_direction_hit"] = "zero_return"  # 組長 2026-10-29 核定：不計入方向命中率的分子與分母，另列筆數
            elif (direction == "up") == (ret > 0):
                out[f"d{k}_direction_hit"] = "hit"
            else:
                out[f"d{k}_direction_hit"] = "miss"
        row.update(out)
    return row


def summarize(rows: list[dict]) -> dict:
    summary: dict = {"n_signals": len(rows), "horizons": {}}
    for k in HORIZONS:
        statuses = [r[f"d{k}_status"] for r in rows]
        reasons = Counter(r[f"d{k}_na_reason"] for r in rows if r[f"d{k}_status"] == "NA")
        hits = [r[f"d{k}_direction_hit"] for r in rows if r[f"d{k}_status"] == "ok"]
        counted = [h for h in hits if h in ("hit", "miss")]
        summary["horizons"][f"D{k}"] = {
            "n_ok": statuses.count("ok"),
            "n_na": statuses.count("NA"),
            "na_by_reason": dict(sorted(reasons.items())),
            "direction_hit_numerator": counted.count("hit"),
            "direction_hit_denominator": len(counted),
            "note": "小樣本觀察；不證明預測能力，不做獲利承諾",
        }
    return summary


CSV_FIELDS = (["signal_id", "ticker", "signal_cutoff_at", "direction", "entry_date", "entry_open"]
              + [f"d{k}_{suffix}" for k in HORIZONS for suffix in
                 ("exit_date", "exit_close", "return", "status", "na_reason",
                  "corporate_action_in_window", "direction_hit")])


def check_output_path(path: Path) -> None:
    parts = Path(path).resolve().parts
    for forbidden in FORBIDDEN_OUT_PARTS:
        n = len(forbidden)
        for i in range(len(parts) - n + 1):
            if tuple(parts[i:i + n]) == forbidden:
                raise PermissionError(
                    f"拒絕寫入 {'/'.join(forbidden)}：前瞻價格結果不可放在 Agent 讀得到的位置")


def run(signals_path, prices_path, calendar_path, as_of_text, out_csv, out_summary=None,
        actions_path=None) -> tuple[list[dict], dict]:
    out_csv = Path(out_csv)
    check_output_path(out_csv)
    if out_summary:
        check_output_path(Path(out_summary))
    as_of = parse_dt(as_of_text)
    batch_id, signals = load_signals(signals_path)
    calendar = load_calendar(Path(calendar_path))
    prices = load_prices(Path(prices_path)) if prices_path and Path(prices_path).exists() else {}
    actions = load_actions(Path(actions_path) if actions_path else None)
    rows = [evaluate_signal(s, calendar, prices, as_of, actions) for s in signals]
    summary = summarize(rows)
    summary.update({"batch_id": batch_id, "as_of": as_of.isoformat(),
                    "price_basis": "raw_unadjusted；entry=cutoff 後下一交易日開盤，exit=第 1／5／20 個持有交易日收盤",
                    "calendar_days": len(calendar)})
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with open(out_csv, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    if out_summary:
        Path(out_summary).write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
                                     encoding="utf-8")
    return rows, summary


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="W07-D 前瞻 1/5/20 日評估（離線、決定性）")
    ap.add_argument("--signals", required=True)
    ap.add_argument("--prices", required=True)
    ap.add_argument("--calendar", required=True)
    ap.add_argument("--actions")
    ap.add_argument("--as-of", required=True, help="例如 2026-11-09T09:00:00+08:00")
    ap.add_argument("--out", required=True)
    ap.add_argument("--summary-out")
    args = ap.parse_args(argv)
    _, summary = run(args.signals, args.prices, args.calendar, args.as_of, args.out,
                     args.summary_out, args.actions)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
