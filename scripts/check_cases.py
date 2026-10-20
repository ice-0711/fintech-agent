"""scripts/check_cases.py — W04/W05/W06-B 案例與關係資料檢查器

固定依手冊第 06 章「30 案固定分配表」：30 案 = 10 開發 + 20 保留。

檢查項目
--------
開發集（evaluation/dev-cases.json + fixtures/dev/case_fixtures.json）
  1. 案例 ID、股票、用途與固定分配表一致，共 10 案
  2. 每案的 source_snapshot_id 存在，快照股票與案例股票一致
  3. 每個片段有 synthetic_fixture；content_hash = sha256(paragraph)
  4. 有擾動（synthetic 或 perturbation）者必須有 perturbation_location
  5. 合成擾動不得含指控性字詞（擾動非真實公司指控）
  6. 真實片段 available_at 不早於 MOPS 公告時間（announce_times.csv）
  7. 期望支持的主張所依片段須在 cutoff 前可得（CASE-18 類型除外）
  8. 開發快照不得包含保留案例 ID
保留集（evaluation/test-cases-sealed.json + fixtures/test/case_fixtures.json）
  9. 20 案，ID 與股票與固定分配表一致；與開發集不重疊；30 = 10 + 20
     保留快照套用第 2–7 項；不得引用開發案例；片段 ID 與內容 hash 不與開發集共用
     fixtures/test/SEAL.json 的檔案 hash 與現檔一致（封存後未被修改）
比較快照（data/v12-peer-snapshot.json）
 10. 2330 為 industry_reference 且不入同業平均；平均值可由 peer 重算
關係（graph-reviewed.csv）
 11. 每條關係有原句、文件日期 doc_date（不得以 verified_date 代替）、來源網址或檔案

執行：python scripts/check_cases.py        結束碼 0 = 通過
"""

from __future__ import annotations

import csv
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# 手冊第 06 章 30 案固定分配表：case_id -> (股票, 用途)
FIXED_SPLIT: dict[str, tuple[str, str]] = {
    "CASE-01": ("2330", "dev"), "CASE-02": ("2317", "test"), "CASE-03": ("2454", "test"),
    "CASE-04": ("2330", "dev"), "CASE-05": ("2317", "test"), "CASE-06": ("2454", "test"),
    "CASE-07": ("2330", "test"), "CASE-08": ("2317", "dev"), "CASE-09": ("2454", "test"),
    "CASE-10": ("2330", "test"), "CASE-11": ("2317", "dev"), "CASE-12": ("2454", "test"),
    "CASE-13": ("2330", "test"), "CASE-14": ("2317", "test"), "CASE-15": ("2454", "dev"),
    "CASE-16": ("2330", "test"), "CASE-17": ("2317", "test"), "CASE-18": ("2454", "dev"),
    "CASE-19": ("2330", "dev"), "CASE-20": ("2317", "test"), "CASE-21": ("2454", "test"),
    "CASE-22": ("2330", "dev"), "CASE-23": ("2317", "test"), "CASE-24": ("2454", "test"),
    "CASE-25": ("2330", "test"), "CASE-26": ("2317", "dev"), "CASE-27": ("2454", "test"),
    "CASE-28": ("2330", "test"), "CASE-29": ("2317", "dev"), "CASE-30": ("2454", "test"),
}
# 案例預期「證據在 cutoff 之後」，不檢查第 7 項
AFTER_CUTOFF_CASES = {"CASE-18"}
ACCUSATION_WORDS = ("跌破", "崩", "暴跌", "造假", "掏空", "違法", "醜聞", "虧損擴大", "下修", "危機", "詐")


def h(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def t(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def load_json(rel: str):
    p = ROOT / rel
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


class Report:
    def __init__(self):
        self.errors: list[str] = []
        self.notes: list[str] = []

    def err(self, where, msg):
        self.errors.append(f"[{where}] {msg}")


def announce_times() -> dict[tuple[str, str], datetime]:
    path = ROOT / "data" / "manual" / "announce_times.csv"
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as f:
        return {(r["ticker"], r["period"]): t(r["available_at"]) for r in csv.DictReader(f)}


def check_snapshots(r: Report, label: str, cases: list[dict], snaps: dict, forbidden_ids: set[str]) -> None:
    """開發集與保留集共用：股票、快照、synthetic、hash、擾動位置、指控字詞、可得時間。"""
    ann = announce_times()
    for c in cases:
        cid = c["case_id"]
        want_ticker = FIXED_SPLIT.get(cid, (None,))[0]
        if c["ticker"] != want_ticker:
            r.err(cid, f"股票 {c['ticker']} 與固定分配表 {want_ticker} 不符")
        snap = snaps.get(c["source_snapshot_id"])
        if snap is None:
            r.err(cid, f"找不到快照 {c['source_snapshot_id']}")
            continue
        if snap.get("ticker") != c["ticker"]:
            r.err(cid, f"快照股票 {snap.get('ticker')} 與案例股票 {c['ticker']} 不符")
        text = json.dumps(snap, ensure_ascii=False)
        leaked = sorted(x for x in forbidden_ids if x in text)
        if leaked:
            r.err(cid, f"{label}快照引用另一集合的案例：{leaked}")

        perturbed = bool(snap.get("synthetic_fixture")) or bool(snap.get("perturbation"))
        if perturbed and not c.get("perturbation_location"):
            r.err(cid, "有擾動但缺 perturbation_location")

        cutoff = t(c["cutoff_at"])
        for e in snap.get("evidences", []):
            where = f"{cid}:{e['evidence_version_id']}"
            if "synthetic_fixture" not in e:
                r.err(where, "片段缺 synthetic_fixture")
            if e.get("paragraph") is not None and e.get("content_hash") != h(e["paragraph"]):
                r.err(where, "content_hash 與 paragraph 不符")
            if e.get("synthetic_fixture") and e.get("paragraph"):
                bad = [w for w in ACCUSATION_WORDS if w in e["paragraph"]]
                if bad:
                    r.err(where, f"合成擾動含指控性字詞 {bad}（擾動非真實公司指控）")
            if not e.get("synthetic_fixture") and e.get("available_at"):
                period = e.get("period") or ("2026Q2" if "115 年第 2 季" in (e.get("paragraph") or "") else None)
                official = ann.get((snap["ticker"], period)) if period else None
                if official and t(e["available_at"]) < official:
                    r.err(where, f"available_at {e['available_at']} 早於 MOPS 公告 {official.isoformat()}")
                if (cid not in AFTER_CUTOFF_CASES and c.get("expected_supported_claims")
                        and t(e["available_at"]) > cutoff):
                    r.err(where, f"支持主張所依片段於 cutoff {c['cutoff_at']} 後才可得")
        price = snap.get("price_snapshot") or {}
        rows = price.get("closes") or ([price] if price.get("available_at") else [])
        for row in rows:
            if t(row["available_at"]) > cutoff:
                r.err(cid, f"價格 {row.get('trade_date')} 晚於 cutoff")


def evidence_keys(snaps: dict) -> tuple[set[str], set[str]]:
    ids, hashes = set(), set()
    for s in snaps.values():
        for e in s.get("evidences", []):
            ids.add(e["evidence_version_id"])
            if e.get("content_hash"):
                hashes.add(e["content_hash"])
    return ids, hashes


def check_dev(r: Report) -> tuple[set[str], dict]:
    dev = load_json("evaluation/dev-cases.json")
    fx = load_json("fixtures/dev/case_fixtures.json")
    if dev is None or fx is None:
        r.err("dev", "缺 dev-cases.json 或 case_fixtures.json")
        return set(), {}
    ids = {c["case_id"] for c in dev["cases"]}
    expected = {k for k, (_, s) in FIXED_SPLIT.items() if s == "dev"}
    if ids != expected:
        r.err("dev", f"開發案例與固定分配表不符：多 {sorted(ids - expected)}，缺 {sorted(expected - ids)}")
    holdout = {k for k, (_, s) in FIXED_SPLIT.items() if s == "test"}
    holdout |= {k.lower().replace("case-", "snap-test-case-") for k in holdout}
    check_snapshots(r, "開發", dev["cases"], fx.get("snapshots", {}), holdout)
    r.notes.append(f"開發集 {len(ids)} 案")
    return ids, fx.get("snapshots", {})


def check_holdout(r: Report, dev_ids: set[str], dev_snaps: dict) -> None:
    sealed = load_json("evaluation/test-cases-sealed.json")
    if sealed is None:
        r.notes.append("保留集檔案不存在，略過")
        return
    ids = {c["case_id"] for c in sealed["cases"]}
    expected = {k for k, (_, s) in FIXED_SPLIT.items() if s == "test"}
    if ids != expected:
        r.err("test", f"保留案例與固定分配表不符：多 {sorted(ids - expected)}，缺 {sorted(expected - ids)}")
    if ids & dev_ids:
        r.err("split", f"開發與保留重疊：{sorted(ids & dev_ids)}")
    if len(ids | dev_ids) != 30:
        r.err("split", f"開發 + 保留 = {len(ids | dev_ids)}，應為 30")

    fx = load_json("fixtures/test/case_fixtures.json")
    if fx is None:
        r.err("test", "缺 fixtures/test/case_fixtures.json")
        r.notes.append(f"保留集 {len(ids)} 案")
        return
    dev_forbidden = set(dev_ids) | {k.lower().replace("case-", "snap-dev-case-") for k in dev_ids}
    test_snaps = fx.get("snapshots", {})
    check_snapshots(r, "保留", sealed["cases"], test_snaps, dev_forbidden)
    for c in sealed["cases"]:
        for key in ("variant", "category", "expected_behavior"):
            if not c.get(key):
                r.err(c["case_id"], f"缺 {key}")

    dev_e, dev_h = evidence_keys(dev_snaps)
    test_e, test_h = evidence_keys(test_snaps)
    if dev_e & test_e:
        r.err("isolation", f"開發與保留共用片段 ID：{sorted(dev_e & test_e)}")
    if dev_h & test_h:
        r.err("isolation", f"開發與保留共用相同片段內容（hash）：{len(dev_h & test_h)} 筆")

    copy = ROOT / "fixtures" / "test" / "test-cases-sealed.json"
    if not copy.exists():
        r.err("test", "缺 fixtures/test/test-cases-sealed.json")
    elif copy.read_bytes() != (ROOT / "evaluation" / "test-cases-sealed.json").read_bytes():
        r.err("test", "fixtures/test/test-cases-sealed.json 與 evaluation/ 版本不同（請重跑 build_holdout_cases.py）")

    seal = load_json("fixtures/test/SEAL.json")
    if seal is None:
        r.err("seal", "缺 fixtures/test/SEAL.json（尚未封存）")
    else:
        for rel, digest in seal["files"].items():
            p = ROOT / rel
            if not p.exists() or hashlib.sha256(p.read_bytes()).hexdigest() != digest:
                r.err("seal", f"{rel} 與封存 hash 不符（封存後被修改）")
    r.notes.append(f"保留集 {len(ids)} 案")


def check_peer(r: Report) -> None:
    p = load_json("data/v12-peer-snapshot.json")
    if p is None:
        r.err("peer", "缺 data/v12-peer-snapshot.json")
        return
    comps = p["companies"]
    if comps.get("2330", {}).get("role") != "industry_reference":
        r.err("peer", "2330 必須為 industry_reference")
    peers = [v for v in comps.values() if v.get("role") == "peer"]
    stats = p.get("peer_summary_statistics", {})
    pes = [v["pe_ttm"] for v in peers if v.get("pe_ttm") is not None]
    if pes and stats.get("peer_avg_pe") != round(sum(pes) / len(pes), 2):
        r.err("peer", "peer_avg_pe 無法由 peer 角色重算（是否混入 2330？）")
    if "2330" not in stats.get("excluded_entities", []):
        r.err("peer", "excluded_entities 未列 2330")


def check_graph(r: Report) -> None:
    path = ROOT / "graph-reviewed.csv"
    if not path.exists():
        r.err("graph", "缺 graph-reviewed.csv")
        return
    with path.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if len(rows) > 30:
        r.err("graph", f"關係 {len(rows)} 條，超過 30 邊上限")
    for i, row in enumerate(rows, start=2):
        where = f"graph-reviewed.csv 第 {i} 列"
        if not row.get("quote_original"):
            r.err(where, "缺原句")
        if not row.get("doc_date"):
            r.err(where, "缺 doc_date（文件日期；verified_date 不能代替）")
        if not (row.get("evidence_url") or row.get("evidence_file")):
            r.err(where, "缺來源網址或檔案")
        if row.get("review_status") != "source_text_verified":
            r.err(where, "review_status 不是 source_text_verified")
    r.notes.append(f"關係 {len(rows)} 條")


def main() -> int:
    r = Report()
    dev_ids, dev_snaps = check_dev(r)
    check_holdout(r, dev_ids, dev_snaps)
    check_peer(r)
    check_graph(r)
    print("；".join(r.notes))
    print(f"錯誤：{len(r.errors)}")
    for e in r.errors:
        print("  ✗", e)
    return 1 if r.errors else 0


if __name__ == "__main__":
    sys.exit(main())