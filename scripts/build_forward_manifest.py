"""scripts/build_forward_manifest.py — W09-B 前瞻 9 份總表（組員 B）

把三批前瞻的紀錄整理成一張 9 列的總表（3 批 × 2330／2317／2454），不論成功、失敗或還沒凍結都列出：
    research/forward-manifest-9.json
    evaluation/v12-forward-manifest.csv

讀的檔（只讀、不改）：
    research/forward-batch-<N>.json          組長的凍結紀錄（快照 sha256、Q3 決定、研究結果）
    research/forward-batch-<N>-reports.json  研究草稿（model、prompt、path）
    research/forward-batch-<N>-sources.json  B 的來源清單
    data/forward/financial-snapshots-<日期>.json  若存在就重算 sha256 核對

規則（手冊第 06 章、W09-B 驗收）：
    - 9 筆全入清單，不得只挑成功樣本；某批還沒凍結就標 pending，不刪列
    - 本程式不填任何報酬或績效：1／5／20 日報酬由 D 的 scripts/forward_eval.py 依實際價格計算
    - 快照 sha256 與紀錄不符就中止（不產出總表）
    - 輸出不得寫進 data/forward、fixtures、agents（Agent 工具只讀這些位置）

用法：python scripts/build_forward_manifest.py
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TICKERS = ("2330", "2317", "2454")
BATCHES = {1: "2026-10-30", 2: "2026-11-06", 3: "2026-11-13"}
HORIZONS = (1, 5, 20)
TPE = timezone(timedelta(hours=8))
CLOSE_AVAILABLE = time(17, 30)  # rule_close_1730（組長 10/22）
FORBIDDEN_OUT = (("data", "forward"), ("fixtures",), ("agents",))
# 已知公休日（11–12 月無）；實際以 FinMind TaiwanStockTradingDate 核對
HOLIDAYS: set[date] = set()
# 每批用的 Agent 版本（handoff/agent-version-changes.md）；紀錄檔有 agent_version 時以紀錄檔為準
AGENT_VERSION = {1: "v1", 2: "v1", 3: "v2"}
# 發布紀錄不在研究紀錄檔裡，來源寫明（手動登錄，只登已在 repo 文件中的事實）
PUBLICATIONS = {
    "fwd1-2317": {"published": True, "report_version": "rv-6556af9c…（第 1 版）；rv-2ed6652e…（第 2 版，11/09 發布）",
                  "published_on": "2026-11-02",
                  "source": "第 1 版：handoff/deployment-v1.md 第三節第 6 步；第 2 版：handoff/decisions-2026-10.md 第 20 節"},
    "fwd2-2330": {"published": True, "report_version": "rv-db6b0e1b…", "published_on": "2026-11-09",
                  "source": "handoff/decisions-2026-10.md 第 20 節（11/09 14:54:16 核准發布）"},
}
CSV_FIELDS = ("signal_id", "batch_id", "ticker", "signal_cutoff_at", "batch_status", "snapshot_sha256",
              "snapshot_verified", "snapshot_generated_at", "generated_late", "period_used", "q3_decision",
              "direction", "agent_version", "job_id", "job_status", "stop_reason", "model_id", "researcher_prompt",
              "reviewer_prompt", "commit", "published", "report_version", "entry_date_expected",
              "d1_date_expected", "d5_date_expected", "d20_date_expected", "corporate_action_in_window",
              "sources_file", "evidence_ids", "inputs_checked", "latest_input_available_at",
              "signal_price_date", "signal_close", "signal_price_available_at", "price_basis",
              "returns", "audit_file", "note")
PRICE_BASIS = "raw_unadjusted（FinMind TaiwanStockPrice 未還原；進場開盤與 D1／D5／D20 收盤用同一口徑）"


def die(msg: str) -> None:
    print(f"[中止] {msg}")
    sys.exit(1)


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def trading_days_after(d: date, n: int) -> list[date]:
    out, cur = [], d
    while len(out) < n:
        cur += timedelta(days=1)
        if cur.weekday() < 5 and cur not in HOLIDAYS:
            out.append(cur)
    return out


def verify_snapshot(root: Path, rec: dict) -> str:
    """回傳 'ok'／'file_absent'；不符就中止。Windows CRLF 也接受（換行統一為 LF 後再比一次）。"""
    p = root / rec["snapshot_file"]
    if not p.exists():
        return "file_absent"
    raw = p.read_bytes()
    want = rec["snapshot_sha256"]
    if hashlib.sha256(raw).hexdigest() == want:
        return "ok"
    if hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest() == want:
        return "ok_after_lf"
    die(f"{rec['snapshot_file']} 重算 sha256 與 {rec['batch_id']} 紀錄不符")
    return ""


def _dt(text: str | None) -> datetime | None:
    if not text:
        return None
    d = datetime.fromisoformat(text)
    if d.tzinfo is None:
        die(f"可得時間缺時區：{text}")
    return d


def snapshot_inputs(root: Path, rec: dict, ticker: str, cutoff: datetime) -> dict:
    """手冊 W09-B 第 4 步：三日期三股票與 available_at、交易價格同口徑。任何輸入晚於 cutoff 就中止。"""
    p = root / rec["snapshot_file"]
    if not p.exists():
        return {}
    snap = json.loads(p.read_text(encoding="utf-8"))
    if snap.get("cutoff_at") and _dt(snap["cutoff_at"]) != cutoff:
        die(f"{rec['snapshot_file']} 的 cutoff_at {snap['cutoff_at']} 與批次截止 {cutoff.isoformat()} 不同")
    if ticker not in snap.get("financials", {}) or ticker not in snap.get("prices", {}):
        die(f"{rec['snapshot_file']} 缺研究股票 {ticker}")
    times: list[tuple[datetime, str]] = []
    for q in snap["financials"][ticker]["quarters"]:
        times.append((_dt(q["available_at"]), f"財報 {q['period']}"))
    evs = [e for e in snap.get("evidences", []) if e.get("ticker") == ticker]
    for e in evs:
        t = _dt(e.get("available_at") or e.get("captured_at"))
        if t is None:
            die(f"{e['evidence_version_id']} 沒有 available_at 也沒有 captured_at")
        times.append((t, e["evidence_version_id"]))
    for m in snap.get("macro", []):
        times.append((_dt(m["available_at"]), f"總經 {m['series_id']} {m['observation_date']}"))
    prices = [x for x in snap["prices"][ticker] if x.get("close") is not None]
    last = max(prices, key=lambda x: x["trade_date"])
    close_at = datetime.combine(date.fromisoformat(last["trade_date"]), CLOSE_AVAILABLE, cutoff.tzinfo)
    times.append((close_at, f"收盤 {last['trade_date']}"))
    late = [label for t, label in times if t > cutoff]
    if late:
        die(f"{rec['snapshot_file']} {ticker} 有晚於 cutoff 的輸入：{late[:5]}")
    latest = max(times)
    return {
        "evidence_ids": ";".join(e["evidence_version_id"] for e in evs),
        "inputs_checked": len(times),
        "latest_input_available_at": f"{latest[0].isoformat()}（{latest[1]}）",
        "signal_price_date": last["trade_date"],
        "signal_close": last["close"],
        "signal_price_available_at": close_at.isoformat(),
        "price_basis": PRICE_BASIS,
    }


def ex_dates(sources: dict | None) -> dict[str, list[date]]:
    out: dict[str, list[date]] = {}
    for a in (sources or {}).get("corporate_actions") or []:
        d = a.get("ex_dividend_trading_date")
        if d:
            out.setdefault(a["ticker"], []).append(date.fromisoformat(d))
    return out


def build(root: Path) -> dict:
    rows = []
    for n, day in BATCHES.items():
        rec = load(root / "research" / f"forward-batch-{n}.json")
        rep = load(root / "research" / f"forward-batch-{n}-reports.json")
        src = load(root / "research" / f"forward-batch-{n}-sources.json")
        cutoff = f"{day}T21:00:00+08:00"
        cutoff_dt = datetime.fromisoformat(cutoff)
        if rec and rec.get("signal_cutoff_at") and rec["signal_cutoff_at"] != cutoff:
            die(f"forward-batch-{n}.json 的 cutoff {rec['signal_cutoff_at']} 不是手冊規定的 {cutoff}")
        verified = verify_snapshot(root, rec) if rec else None
        days = trading_days_after(date.fromisoformat(day), 20)
        entry, exits = days[0], {k: days[k - 1] for k in HORIZONS}
        exd = ex_dates(src)
        reports = {r["ticker"]: r for r in (rep or {}).get("reports", [])}
        results = ((rec or {}).get("research_reports") or {}).get("results") or {}
        for t in TICKERS:
            sid = f"fwd{n}-{t}"
            r, res = reports.get(t, {}), results.get(t, {})
            pub = PUBLICATIONS.get(sid, {})
            if not rec:
                status = "pending_not_frozen"
            elif not res and not r:
                status = "frozen_research_not_run"
            else:
                status = "researched"
            inp = snapshot_inputs(root, rec, t, cutoff_dt) if rec else {}
            in_window = any(entry <= x <= exits[20] for x in exd.get(t, []))
            notes = []
            if rec and rec.get("generated_late"):
                notes.append(rec["generated_late"])
            if status == "pending_not_frozen":
                notes.append(f"{day} 21:00 截止後由組長凍結；本列保留，不刪")
            if exits[20] >= date(2026, 12, 11):
                notes.append("D20 落在 12/11 定稿日：收盤 17:30 才可得，截取早於 17:30 記 NA")
            rows.append({
                "signal_id": sid, "batch_id": f"forward-batch-{n}", "ticker": t,
                "signal_cutoff_at": cutoff, "batch_status": status,
                "snapshot_sha256": (rec or {}).get("snapshot_sha256"),
                "snapshot_verified": verified,
                "snapshot_generated_at": (rec or {}).get("generated_at"),
                "generated_late": bool((rec or {}).get("generated_late")),
                "period_used": ((rec or {}).get("periods_used") or {}).get(t),
                "q3_decision": (rec or {}).get("q3_decision"),
                "direction": r.get("direction") or ("none" if rec else None),
                "agent_version": (((rec or {}).get("agent_version") or "").split("（")[0].strip()
                                  or AGENT_VERSION[n]),
                "job_id": res.get("job_id") or r.get("job_id"),
                "job_status": res.get("status") or r.get("status"),
                "stop_reason": res.get("stop_reason") or r.get("stop_reason"),
                "model_id": (rep or {}).get("model_id"),
                "researcher_prompt": ((rep or {}).get("prompt_versions") or {}).get("researcher"),
                "reviewer_prompt": ((rep or {}).get("prompt_versions") or {}).get("reviewer"),
                "commit": (rep or {}).get("commit"),
                "published": pub.get("published", False if rep else None),
                "report_version": pub.get("report_version"),
                "entry_date_expected": entry.isoformat(),
                "d1_date_expected": exits[1].isoformat(),
                "d5_date_expected": exits[5].isoformat(),
                "d20_date_expected": exits[20].isoformat(),
                "corporate_action_in_window": in_window,
                "sources_file": (f"research/forward-batch-{n}-sources.json" if src else None),
                "evidence_ids": inp.get("evidence_ids"),
                "inputs_checked": inp.get("inputs_checked"),
                "latest_input_available_at": inp.get("latest_input_available_at"),
                "signal_price_date": inp.get("signal_price_date"),
                "signal_close": inp.get("signal_close"),
                "signal_price_available_at": inp.get("signal_price_available_at"),
                "price_basis": PRICE_BASIS,
                "returns": "由 D 的 scripts/forward_eval.py 依實際價格計算；本表不填",
                "audit_file": (f"research/forward-batch-{n}-audit.md"
                               if (root / "research" / f"forward-batch-{n}-audit.md").exists() else None),
                "note": "；".join(notes) or None,
            })
    return {
        "manifest_id": "forward-manifest-9",
        "generated_by": "scripts/build_forward_manifest.py（組員 B）",
        "rule": "9 筆全入清單（3 批 × 2330／2317／2454），失敗、資料不足、未凍結都保留；不填報酬；交易日為平日推算的預期值，以 TaiwanStockTradingDate 核對",
        "summary": {
            "signals": len(rows),
            "researched": sum(r["batch_status"] == "researched" for r in rows),
            "pending_not_frozen": sum(r["batch_status"] == "pending_not_frozen" for r in rows),
            "succeeded": sum(r["job_status"] == "succeeded" for r in rows),
            "insufficient_evidence": sum(r["job_status"] == "insufficient_evidence" for r in rows),
            "published": sum(bool(r["published"]) for r in rows),
            "direction_up_down": sum(r["direction"] in ("up", "down") for r in rows),
        },
        "signals": rows,
    }


def check_out(path: Path, root: Path) -> None:
    rel = path.resolve().relative_to(root.resolve()).parts
    for bad in FORBIDDEN_OUT:
        if rel[:len(bad)] == bad:
            die(f"輸出不可寫進 {'/'.join(bad)}（Agent 工具讀這裡）")


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=str(ROOT))
    ap.add_argument("--json-out", default="research/forward-manifest-9.json")
    ap.add_argument("--csv-out", default="evaluation/v12-forward-manifest.csv")
    a = ap.parse_args(argv)
    root = Path(a.root)
    jo, co = root / a.json_out, root / a.csv_out
    check_out(jo, root)
    check_out(co, root)
    m = build(root)
    jo.write_text(json.dumps(m, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with co.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS, lineterminator="\n")
        w.writeheader()
        w.writerows(m["signals"])
    s = m["summary"]
    print(f"寫入 {a.json_out}、{a.csv_out}：{s['signals']} 列；已研究 {s['researched']}、未凍結 {s['pending_not_frozen']}、"
          f"通過覆核 {s['succeeded']}、證據不足 {s['insufficient_evidence']}、已發布 {s['published']}")


if __name__ == "__main__":
    main()