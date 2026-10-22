#!/usr/bin/env python3
"""scripts/audit_report.py — 組員 B 的報告／來源稽核工具（W07 起，W09、W12–W14 沿用）

不呼叫 LLM、不連網、不改任何資料；只讀快照與報告 JSON，輸出稽核表。
本檔不在凍結工具清單內（不是 Agent 工具），可隨報告格式調整，不影響 30 案實驗。

三種用法（repo 根目錄，Windows CMD）：

1) 產生基準表（報告還沒產生時）：以快照算出每檔應有的數字
   python scripts\\audit_report.py --baseline --out data\\v12-report-audit.csv

2) 稽核報告（W07-L 的 report.json；可一次給多份）
   python scripts\\audit_report.py --report output\\reports\\2330.json output\\reports\\2317.json output\\reports\\2454.json ^
       --out data\\v12-report-audit.csv
   前瞻報告加 --snapshot data\\forward\\financial-snapshots-2026-10-30.json

3) 原文定位（W14 答辯：問到數字要能找到原文）
   python scripts\\audit_report.py --find 27.25 --ticker 2330

報告 JSON 結構未定（W07-L 產生），本工具用「掃描鍵名」的方式辨識，不依賴固定結構：
- 引用：evidence_version_id、evidence_refs、source_ref（值為片段 ID 者）
- 報告截止時間：cutoff_at、cutoff、data_cutoff（取第一個找到的）
- 股票：ticker、stock_id、stock_code
- 數字：METRIC_KEYS 列的鍵名（與六工具輸出同名），以報告截止時間由工具重算比對
結果：pass／fail／warn／pending_report；任何 fail 時結束碼為 1。
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from agents import tools_impl as T  # noqa: E402

RESEARCH = ("2330", "2317", "2454")
PEER_SUBJECT, PEERS, INDUSTRY_REF = "2454", ("2379", "3034"), "2330"
FROZEN_CUTOFF = "2026-09-30T17:30:00+08:00"
TOL = 0.011
EVIDENCE_KEYS = {"evidence_version_id", "evidence_refs", "source_ref"}
CUTOFF_KEYS = ("cutoff_at", "cutoff", "data_cutoff")
TICKER_KEYS = ("ticker", "stock_id", "stock_code")
# 報告鍵名 → (工具指標名, 單位, 口徑規則)
METRIC_KEYS = {
    "revenue_single_q": ("revenue_single_q", "億元 TWD", "single_quarter；合併"),
    "operating_income_single_q": ("operating_income_single_q", "億元 TWD", "single_quarter；合併"),
    "net_income_single_q": ("net_income_single_q", "億元 TWD", "single_quarter；母公司業主"),
    "eps_single_q": ("eps_single_q", "元", "single_quarter"),
    "eps_ttm": ("eps_ttm", "元", "四連續單季；不得單季×4"),
    "fcf_ttm": ("fcf_ttm", "億元 TWD", "CFO − 正值 CapEx 四季加總"),
    "bvps": ("bvps", "元", "歸屬母公司權益 ÷ 流通股數"),
    "net_debt": ("net_debt", "億元 TWD", "不含租賃負債"),
    "shares_outstanding_m": ("shares_outstanding_m", "百萬股", "發行 − 庫藏"),
    "close_price": ("close_price", "元", "未還原收盤；同一基準日"),
    "pe_ttm": ("pe_ttm", "倍", "收盤 ÷ TTM EPS；EPS≤0 為 NA"),
    "pb_ratio": ("pb_ratio", "倍", "收盤 ÷ BVPS"),
    "intrinsic_value_per_share": ("dcf_per_share", "元", "WACC 9%、g 3%、5 年持平 TTM FCF；FCF≤0 無法判定"),
    "dcf_per_share": ("dcf_per_share", "元", "同上"),
}
# 已知舊假資料（W05 回歸時查到）：出現在已發布報告即判 fail
KNOWN_FAKE = ["1,598.88", "1598.88", "853.27", "6,735", "53.2%", "1,272.7", "16.19", "19.85"]
COLS = ["audit_id", "ticker", "report_file", "section", "field", "json_path", "report_value",
        "expected_value", "unit", "rule", "result", "note"]


# ---------------------------------------------------------------------------
def walk(node: Any, path: str = "$") -> Iterator[tuple[str, str, Any, dict]]:
    """逐一產生 (json_path, key, value, parent_dict)。"""
    if isinstance(node, dict):
        for k, v in node.items():
            p = f"{path}.{k}"
            yield p, k, v, node
            yield from walk(v, p)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from walk(v, f"{path}[{i}]")


def parse_dt(value: Any) -> datetime | None:
    try:
        return T._parse_iso(str(value))
    except (ValueError, TypeError):
        return None


def num(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.replace(",", ""))
        except ValueError:
            return None
    return None


def expected_metrics(ticker: str, cutoff: str) -> dict[str, Any]:
    """以六工具（同一快照、同一 cutoff）重算報告應有數字；不可算者為 'NA:原因'。"""
    out: dict[str, Any] = {}
    fin = T.get_financial_snapshot(ticker=ticker, cutoff=cutoff)
    if fin["status"] != "ok":
        return {"_error": fin["reason"]}
    d = fin["data"]
    m = d["metrics"]
    out.update({k: m.get(k) for k in ("revenue_single_q", "operating_income_single_q", "eps_ttm",
                                     "fcf_ttm", "bvps", "net_debt", "shares_outstanding_m")})
    out["net_income_single_q"] = m.get("net_income_single_q")
    out["eps_single_q"] = m.get("eps_single_q", m.get("eps"))
    out["_latest_period"] = d.get("latest_period")
    price = T.get_price_window(ticker=ticker, end_at=cutoff, sessions=1)
    close = price["data"]["closes"][-1]["close_price"] if price["status"] == "ok" else None
    out["close_price"] = close
    out["_price_date"] = price["data"]["closes"][-1]["trade_date"] if price["status"] == "ok" else None
    eps, bvps = out["eps_ttm"], out["bvps"]
    out["pe_ttm"] = round(close / eps, 2) if close and eps and eps > 0 else "NA:EPS TTM 缺或非正"
    out["pb_ratio"] = round(close / bvps, 2) if close and bvps and bvps > 0 else "NA:BVPS 缺或非正"
    fcf = out["fcf_ttm"]
    if fcf is None or out["net_debt"] is None or not out["shares_outstanding_m"]:
        out["dcf_per_share"] = "NA:DCF 關鍵參數缺值"
    elif fcf <= 0:
        out["dcf_per_share"] = "NA:無法判定（TTM FCF ≤ 0）"
    else:
        r = T.calculate_metrics(operation="dcf_scenario", values={
            "free_cash_flows": [fcf] * 5, "wacc": 0.09, "terminal_growth": 0.03,
            "net_debt": out["net_debt"], "shares_outstanding": out["shares_outstanding_m"]},
            evidence_refs=[f"snapshot:{ticker}:{out['_latest_period']}"])
        iv = r["data"].get("intrinsic_value_per_share") if r["status"] == "ok" else None
        out["dcf_per_share"] = iv if iv is not None else f"NA:{r.get('reason')}"
    return out


class Audit:
    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []

    def add(self, **kw: Any) -> None:
        row = {c: kw.get(c, "") for c in COLS}
        row["audit_id"] = f"RA-{len(self.rows) + 1:03d}"
        self.rows.append(row)

    @property
    def failed(self) -> int:
        return sum(r["result"] == "fail" for r in self.rows)


# ---------------------------------------------------------------------------
def baseline(audit: Audit, cutoff: str) -> None:
    """報告尚未產生時：列出每檔應有數字與檢查規則（result = pending_report）。"""
    for t in RESEARCH:
        exp = expected_metrics(t, cutoff)
        for key, (metric, unit, rule) in METRIC_KEYS.items():
            if key == "intrinsic_value_per_share":
                continue
            audit.add(ticker=t, section="數字", field=key, expected_value=exp.get(metric), unit=unit,
                      rule=rule, result="pending_report",
                      note=f"財報期 {exp.get('_latest_period')}；股價日 {exp.get('_price_date')}；cutoff {cutoff}")
        for field, rule in (("citations_resolvable", "每個引用的片段 ID 都能在快照解析，hash 相符"),
                            ("no_post_cutoff_source", "引用來源 available_at ≤ 報告 cutoff"),
                            ("no_synthetic_or_known_fake", "無 synthetic_fixture 與已知舊假數字"),
                            ("pdf_equals_web", "PDF 與網頁同一 report.json，數字逐欄一致")):
            audit.add(ticker=t, section="來源", field=field, expected_value="通過", rule=rule, result="pending_report")
    peer = json.loads((ROOT / "data" / "v12-peer-snapshot.json").read_text(encoding="utf-8"))
    for k in ("peer_avg_pe", "peer_avg_pb", "peer_avg_revenue_yoy"):
        audit.add(ticker=PEER_SUBJECT, section="比較", field=k, expected_value=peer["peer_summary_statistics"][k],
                  rule="只 2379、3034；2330 為產業參照不入平均", result="pending_report")
    for t in ("2330", "2317"):
        audit.add(ticker=t, section="比較", field="comparison_panel_absent", expected_value="不應出現",
                  rule="只 2454 套用固定比較組", result="pending_report")


def audit_report(audit: Audit, path: Path) -> None:
    rep = json.loads(path.read_text(encoding="utf-8"))
    name = path.name
    nodes = list(walk(rep))
    ticker = next((str(v) for _, k, v, _ in nodes if k in TICKER_KEYS and str(v) in RESEARCH), None)
    cutoff = next((str(v) for _, k, v, _ in nodes if k in CUTOFF_KEYS and parse_dt(v)), None)
    if not ticker:
        audit.add(report_file=name, section="結構", field="ticker", result="fail", note="報告找不到研究股票代號")
        return
    if not cutoff:
        audit.add(ticker=ticker, report_file=name, section="結構", field="cutoff", result="fail",
                  note="報告沒有 cutoff_at／cutoff，無法判斷可得性")
        return
    cutoff_dt = parse_dt(cutoff)
    snap = T._load_snapshots()
    evidences = {e["evidence_version_id"]: e for e in snap.get("evidences", [])}

    # A. 引用可解析、hash、可得時間
    refs: list[tuple[str, str, dict]] = []
    for p, k, v, parent in nodes:
        if k in EVIDENCE_KEYS:
            for i, ref in enumerate(v if isinstance(v, list) else [v]):
                if isinstance(ref, str) and ref.startswith("ev-"):
                    refs.append((f"{p}[{i}]" if isinstance(v, list) else p, ref, parent))
    for p, ref, parent in refs:
        ev = evidences.get(ref)
        if ev is None:
            audit.add(ticker=ticker, report_file=name, section="來源", field="citation", json_path=p,
                      report_value=ref, result="fail", note="快照中找不到此片段（不可解析）")
            continue
        when, _, _ = T._effective_available(ev)
        problems = []
        if when is None or when > cutoff_dt:
            problems.append(f"可得時間 {ev.get('available_at')} 晚於報告 cutoff {cutoff}")
        if parent.get("content_hash") and parent.get("content_hash") != ev.get("content_hash"):
            problems.append("content_hash 與快照不符")
        audit.add(ticker=ticker, report_file=name, section="來源", field="citation", json_path=p, report_value=ref,
                  expected_value=ev.get("content_hash", "")[:12], result="fail" if problems else "pass",
                  note="；".join(problems))
    if not refs:
        audit.add(ticker=ticker, report_file=name, section="來源", field="citation", result="warn",
                  note="報告沒有任何片段引用（ev-…）；若有主張，需檢查是否漏引用")

    # B. 報告內任何 available_at 晚於 cutoff
    for p, k, v, _ in nodes:
        if k == "available_at" and (dt := parse_dt(v)) and dt > cutoff_dt:
            audit.add(ticker=ticker, report_file=name, section="時間", field="available_at", json_path=p,
                      report_value=v, expected_value=f"≤ {cutoff}", result="fail", note="cutoff 後資料進入報告")

    # C. 假資料
    text = json.dumps(rep, ensure_ascii=False)
    for p, k, v, _ in nodes:
        if k == "synthetic_fixture" and v is True:
            audit.add(ticker=ticker, report_file=name, section="假資料", field=k, json_path=p, report_value=v,
                      result="fail", note="正式報告不得含合成資料")
    for fake in KNOWN_FAKE:
        if fake in text:
            audit.add(ticker=ticker, report_file=name, section="假資料", field="known_fake", report_value=fake,
                      result="fail", note="出現已知舊假數字，請人工確認")

    # D. 數字與口徑
    exp = expected_metrics(ticker, cutoff)
    for p, k, v, _ in nodes:
        if k not in METRIC_KEYS:
            continue
        metric, unit, rule = METRIC_KEYS[k]
        want = exp.get(metric)
        got = num(v)
        if isinstance(want, str) and want.startswith("NA"):
            ok = v is None or (isinstance(v, str) and ("NA" in v or "無法判定" in v or "無資料" in v))
            note = "" if ok else f"應為 NA（{want[3:]}），報告卻給數值"
        elif want is None:
            ok, note = v is None, "快照無此值，報告不應給數值"
        else:
            ok = got is not None and abs(got - float(want)) <= TOL
            note = "" if ok else ("報告為空或非數字" if got is None else f"差 {round(got - float(want), 4)}")
        audit.add(ticker=ticker, report_file=name, section="數字", field=k, json_path=p, report_value=v,
                  expected_value=want, unit=unit, rule=rule, result="pass" if ok else "fail", note=note)

    # E. 比較組
    has_peer = any(k in ("peer_comparison", "peer_summary_statistics", "comparators", "peers") for _, k, _, _ in nodes)
    if ticker != PEER_SUBJECT and has_peer:
        audit.add(ticker=ticker, report_file=name, section="比較", field="comparison_panel_absent",
                  result="fail", note="只 2454 套用固定比較組")
    if ticker == PEER_SUBJECT and has_peer:
        for p, k, v, _ in nodes:
            if k in ("comparators", "peers", "included_in_peer_average") and isinstance(v, list) and INDUSTRY_REF in map(str, v):
                if k != "comparators":
                    audit.add(ticker=ticker, report_file=name, section="比較", field=k, json_path=p, report_value=v,
                              result="fail", note="2330 為產業參照，不得計入同業平均")


def find_value(value: str, ticker: str | None) -> int:
    """W14：數字 → 原文位置（快照片段與財務欄位）。"""
    snap = T._load_snapshots()
    target = num(value)
    hits = 0
    for e in snap.get("evidences", []):
        if ticker and e.get("ticker") != ticker:
            continue
        para = str(e.get("paragraph") or "")
        if value in para or (target is not None and re.search(rf"(?<![\d.]){re.escape(value)}(?![\d])", para)):
            hits += 1
            print(f"[片段] {e['evidence_version_id']}｜{e.get('title')}｜可得 {e.get('available_at')}｜{e.get('source_url') or e.get('source_ref')}")
    for t, comp in snap.get("financials", {}).items():
        if ticker and t != ticker:
            continue
        for q in comp.get("quarters", []):
            for k, v in q.items():
                if target is not None and isinstance(v, (int, float)) and not isinstance(v, bool) and abs(v - target) < 0.005:
                    hits += 1
                    print(f"[財務] {t} {q['period']} {k} = {v}｜{q.get('source_id')}｜可得 {q.get('available_at')}"
                          f"｜EPS 來源 {q.get('eps_source')}")
    if not hits:
        print("查無此數字：請承認未知，不要現場新造分析")
    return hits


def main() -> None:
    ap = argparse.ArgumentParser(description="B 的報告／來源稽核工具（不呼叫 LLM）")
    ap.add_argument("--report", nargs="*", help="report.json 路徑（可多份）")
    ap.add_argument("--baseline", action="store_true", help="報告未產生時輸出基準表")
    ap.add_argument("--snapshot", help="改用指定快照（前瞻批次）；預設為 30 案凍結快照")
    ap.add_argument("--cutoff", default=FROZEN_CUTOFF, help="--baseline 用的 cutoff")
    ap.add_argument("--out", help="輸出 CSV（例如 data\\v12-report-audit.csv）")
    ap.add_argument("--find", help="原文定位：要找的數字或文字")
    ap.add_argument("--ticker", help="--find 限定股票")
    a = ap.parse_args()

    ctx = T.use_snapshot(a.snapshot) if a.snapshot else None
    if ctx:
        ctx.__enter__()
    try:
        if a.find:
            sys.exit(0 if find_value(a.find, a.ticker) else 2)
        audit = Audit()
        if a.baseline:
            baseline(audit, a.cutoff)
        for r in a.report or []:
            audit_report(audit, (ROOT / r).resolve() if not Path(r).is_absolute() else Path(r))
        if not audit.rows:
            ap.error("請指定 --baseline、--report 或 --find")
    finally:
        if ctx:
            ctx.__exit__(None, None, None)

    summary = {k: sum(r["result"] == k for r in audit.rows) for k in ("pass", "fail", "warn", "pending_report")}
    print(f"稽核列數 {len(audit.rows)}：{summary}")
    for r in audit.rows:
        if r["result"] == "fail":
            print(f"  [fail] {r['ticker']} {r['report_file']} {r['field']} {r['json_path']}：{r['note']}")
    if a.out:
        out = (ROOT / a.out) if not Path(a.out).is_absolute() else Path(a.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=COLS)
            w.writeheader()
            w.writerows(audit.rows)
        print(f"寫入 {out.relative_to(ROOT) if out.is_relative_to(ROOT) else out}")
    sys.exit(1 if audit.failed else 0)


if __name__ == "__main__":
    main()
