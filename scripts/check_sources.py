"""scripts/check_sources.py — W02-B 來源 ID 與 cutoff 檢查器。

用途
----
1. 來源 ID：fixture / 快照中出現的 source_id 必須登記在 source-register.csv
   或 data/financial-snapshots.json（含其 source_manifest.raw_files）。
2. cutoff：任何回傳資料的 available_at 不得晚於該次查詢的 cutoff / end_at。
3. 未知時間：available_at 缺失時，以 captured_at 判定可得性；
   兩者皆缺則視為「不可得」，絕不視為較早可得。
4. 時間不可倒填：available_at 不得早於財報期結束日。
5. null 與 0：fixture 中標記為缺值的欄位必須是 null，不可為 0。
6. hash：content_hash 必須是 64 位小寫十六進位；若檔案或段落存在，重算比對。
7. 合成樣本：synthetic_fixture 必須明確為 true/false，不可省略。

執行
----
    python scripts/check_sources.py
    python scripts/check_sources.py --file fixtures/tool-responses.json

結束碼：0 = 全部通過；1 = 有錯誤。
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from datetime import datetime, date
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
SOURCE_REGISTER = ROOT / "source-register.csv"
SNAPSHOT = ROOT / "data" / "financial-snapshots.json"
DEV_FIXTURES = ROOT / "fixtures" / "dev" / "case_fixtures.json"
DEFAULT_FILES = [
    ROOT / "fixtures" / "tool-responses.json",
    ROOT / "data" / "v12-financial-fixtures.json",
]

HASH_RE = re.compile(r"^[0-9a-f]{64}$")
QUARTER_END = {"Q1": (3, 31), "Q2": (6, 30), "Q3": (9, 30), "Q4": (12, 31)}


# ---------------------------------------------------------------------------
# 時間判定（核心規則，可被其他模組 import）
# ---------------------------------------------------------------------------
def parse_time(value: str) -> datetime:
    """解析 ISO-8601；沒有時區一律視為錯誤，不猜時區。"""
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError(f"時間缺少時區：{value}")
    return parsed


def effective_available_at(available_at: str | None, captured_at: str | None) -> datetime | None:
    """可得時間：官方時間優先；未知時用擷取時間；兩者皆無回傳 None（不可得）。"""
    if available_at:
        return parse_time(available_at)
    if captured_at:
        return parse_time(captured_at)
    return None


def is_available(available_at: str | None, captured_at: str | None, cutoff: str) -> bool:
    """unknown 時間不視為較早可得：兩個時間都沒有 → False。"""
    eff = effective_available_at(available_at, captured_at)
    if eff is None:
        return False
    return eff <= parse_time(cutoff)


def period_end(period: str) -> date | None:
    """'2026Q2' → 2026-06-30；格式不符回傳 None。"""
    m = re.fullmatch(r"(\d{4})(Q[1-4])", str(period))
    if not m:
        return None
    month, day = QUARTER_END[m.group(2)]
    return date(int(m.group(1)), month, day)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# 已知來源 ID 與 hash
# ---------------------------------------------------------------------------
def load_known_ids() -> tuple[set[str], set[str], set[str]]:
    """回傳 (source_ids, snapshot_or_evidence_ids, known_hashes)。"""
    source_ids: set[str] = set()
    snap_ids: set[str] = set()
    hashes: set[str] = set()

    if SOURCE_REGISTER.exists():
        with SOURCE_REGISTER.open(encoding="utf-8") as f:
            source_ids |= {row["source_id"] for row in csv.DictReader(f)}

    if SNAPSHOT.exists():
        snap = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
        for raw in snap.get("source_manifest", {}).get("raw_files", []):
            hashes.add(raw["sha256"])
        for ev in snap.get("evidences", []):
            source_ids.add(ev["source_id"])
            snap_ids.add(ev["evidence_version_id"])
            if ev.get("content_hash"):
                hashes.add(ev["content_hash"])
        for company in snap.get("financials", {}).values():
            for q in company.get("quarters", []):
                source_ids.add(q["source_id"])
                snap_ids.add(q["snapshot_id"])
                hashes.add(q["content_hash"])

    # 人工整理檔（macro.csv 等）以整檔 sha256 作為來源 hash
    for manual in (ROOT / "data" / "manual").glob("*.csv"):
        hashes.add(hashlib.sha256(manual.read_bytes()).hexdigest())

    if DEV_FIXTURES.exists():
        dev = json.loads(DEV_FIXTURES.read_text(encoding="utf-8"))
        for sid, case in dev.get("snapshots", {}).items():
            snap_ids.add(sid)
            for ev in case.get("evidences", []):
                snap_ids.add(ev["evidence_version_id"])
                if ev.get("content_hash"):
                    hashes.add(ev["content_hash"])

    return source_ids, snap_ids, hashes


# ---------------------------------------------------------------------------
# 檢查器
# ---------------------------------------------------------------------------
class Checker:
    def __init__(self) -> None:
        self.source_ids, self.snap_ids, self.hashes = load_known_ids()
        self.errors: list[str] = []
        self.checked = 0

    def err(self, where: str, msg: str) -> None:
        self.errors.append(f"[{where}] {msg}")

    # -- 單一資料列 ----------------------------------------------------------
    def check_row(self, where: str, row: dict[str, Any], cutoff: str | None) -> None:
        self.checked += 1
        sid = row.get("source_id")
        if sid is not None and sid not in self.source_ids:
            self.err(where, f"source_id 未登記：{sid}")

        for key in ("snapshot_id", "evidence_version_id"):
            val = row.get(key)
            if val is not None and val not in self.snap_ids:
                self.err(where, f"{key} 不存在於快照：{val}")

        h = row.get("content_hash")
        if h is not None:
            if not HASH_RE.match(str(h)):
                self.err(where, f"content_hash 格式錯誤：{h}")
            elif h not in self.hashes:
                self.err(where, f"content_hash 無法追溯到任何快照或原始檔：{h[:12]}…")
            if row.get("paragraph"):
                if sha256_text(row["paragraph"]) != h:
                    self.err(where, "content_hash 與 paragraph 重算結果不符")

        avail, capt = row.get("available_at"), row.get("captured_at")
        try:
            if cutoff and (avail or capt):
                if not is_available(avail, capt, cutoff):
                    self.err(where, f"available_at {avail or capt} 晚於 cutoff {cutoff}（前視洩漏）")
            if avail and row.get("period"):
                end = period_end(row["period"])
                if end and parse_time(avail).date() <= end:
                    self.err(where, f"available_at {avail} 不晚於財報期結束日 {end}（疑似倒填）")
        except ValueError as exc:
            self.err(where, str(exc))

        basis = row.get("available_at_basis")
        if basis is not None and basis not in ("official", "rule_close_1730", "captured_at_fallback"):
            self.err(where, f"available_at_basis 不合法：{basis}")
        if basis == "captured_at_fallback" and avail and capt and avail != capt:
            self.err(where, "captured_at_fallback 時 available_at 必須等於 captured_at")

    # -- null 與 0 -----------------------------------------------------------
    def check_null_vs_zero(self, where: str, obj: Any) -> None:
        """有 missing_reason 的欄位，其值必須是 null，不可為 0。"""
        if isinstance(obj, dict):
            if obj.get("missing_reason") and "value" in obj and obj["value"] == 0:
                self.err(where, "欄位標記缺值卻填 0（null 與 0 必須分開）")
            for k, v in obj.items():
                self.check_null_vs_zero(f"{where}.{k}", v)
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                self.check_null_vs_zero(f"{where}[{i}]", v)

    # -- 檔案 ---------------------------------------------------------------
    def check_tool_responses(self, data: dict[str, Any]) -> None:
        allowed = set(data.get("status_enum", []))
        holdout = load_holdout_ids()
        text = json.dumps(data, ensure_ascii=False)
        leaked = sorted(h for h in holdout if h in text)
        if leaked:
            self.err("tool-responses", f"引用了保留案例，保留答案不得進入開發用 fixture：{leaked}")
        for case in data.get("responses", []):
            cid = case["fixture_id"]
            resp = case["expected_response"]
            if set(resp) != {"status", "tool", "reason", "data"}:
                self.err(cid, f"回傳頂層欄位必須固定為 status/tool/reason/data，收到 {sorted(resp)}")
            if allowed and resp.get("status") not in allowed:
                self.err(cid, f"status 不在 status_enum：{resp.get('status')}")
            if resp.get("status") != "ok":
                if resp.get("data") is not None:
                    self.err(cid, "非 ok 時 data 必須為 null")
                if not resp.get("reason"):
                    self.err(cid, "非 ok 時 reason 必填")
            if "synthetic_fixture" not in case:
                self.err(cid, "缺 synthetic_fixture 標記")
            cutoff = case["input"].get("cutoff") or case["input"].get("end_at")
            for row in iter_rows(resp.get("data")):
                self.check_row(cid, row, cutoff)
            self.check_null_vs_zero(cid, resp.get("data"))

    def check_financial_fixtures(self, data: dict[str, Any]) -> None:
        for code, comp in data.get("companies", {}).items():
            for key in ("statement_basis", "currency", "unit_money"):
                if key not in comp:
                    self.err(code, f"公司層缺欄位 {key}")
            for q in comp.get("quarters", []):
                where = f"{code}:{q.get('period')}"
                if q.get("synthetic_fixture") is not False:
                    self.err(where, "真實季度資料必須標 synthetic_fixture=false")
                self.check_row(where, q, data.get("cutoff"))
            self.check_null_vs_zero(code, comp)
        for ex in data.get("synthetic_examples", []):
            if ex.get("synthetic_fixture") is not True:
                self.err(ex.get("example_id", "?"), "合成驗算例必須標 synthetic_fixture=true")
            self.check_null_vs_zero(ex.get("example_id", "?"), ex)

    def run_file(self, path: Path) -> None:
        data = json.loads(path.read_text(encoding="utf-8"))
        if "responses" in data:
            self.check_tool_responses(data)
        elif "companies" in data:
            self.check_financial_fixtures(data)
        else:
            self.err(path.name, "無法辨識的檔案格式")


def load_holdout_ids() -> set[str]:
    """保留集案例 ID 與快照 ID（CASE-xx、snap-test-case-xx）。"""
    path = ROOT / "evaluation" / "test-cases-sealed.json"
    if not path.exists():
        return set()
    ids: set[str] = set()
    for c in json.loads(path.read_text(encoding="utf-8")).get("cases", []):
        ids.add(c["case_id"])
        if c.get("source_snapshot_id"):
            ids.add(c["source_snapshot_id"])
    return ids


def iter_rows(obj: Any) -> Iterable[dict[str, Any]]:
    """走訪 data，找出帶有來源欄位的資料列。"""
    if isinstance(obj, dict):
        if any(k in obj for k in ("source_id", "content_hash", "available_at")):
            yield obj
        for v in obj.values():
            if isinstance(v, (dict, list)):
                yield from iter_rows(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from iter_rows(v)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="W02-B 來源 ID 與 cutoff 檢查器")
    ap.add_argument("--file", action="append", help="要檢查的 JSON（可重複）；預設檢查兩個 W02 fixture")
    args = ap.parse_args(argv)
    files = [ROOT / f for f in args.file] if args.file else DEFAULT_FILES

    checker = Checker()
    for path in files:
        if not path.exists():
            checker.err(path.name, "檔案不存在")
            continue
        checker.run_file(path)

    print(f"檢查資料列：{checker.checked}；錯誤：{len(checker.errors)}")
    for e in checker.errors:
        print("  ✗", e)
    return 1 if checker.errors else 0


if __name__ == "__main__":
    sys.exit(main())