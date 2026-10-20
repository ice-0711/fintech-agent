"""scripts/build_source_manifest.py — W03-B 由實際檔案產生 data/source-manifest.json

取代舊版手寫 manifest（舊版 hash 為假值，例如 c3ab8ff1… 為字串 "foobar" 的 SHA-256）。

來源
----
1. data/financial-snapshots.json → source_manifest.raw_files：FinMind 原始檔
   - 本機檔案存在時重算 sha256，與紀錄不符即中止。
   - 檔案不存在（例如授權不可轉散布而未附）時標 file_present=false，不猜 hash。
2. data/manual/*.csv：人工整理檔，以整檔 sha256 記錄。
3. evidences：content_hash 必須等於 sha256(paragraph)，不符即中止。
4. financial-snapshots.json 本身的 sha256（下游 fixture 引用此值）。

執行
----
    python scripts/build_source_manifest.py
"""

from __future__ import annotations

import csv
import hashlib
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "data" / "financial-snapshots.json"
MANUAL_DIR = ROOT / "data" / "manual"
REGISTER = ROOT / "source-register.csv"
OUT = ROOT / "data" / "source-manifest.json"
TW = timezone(timedelta(hours=8))

DATASET_SOURCE_ID = {
    "TaiwanStockFinancialStatements": "finmind_fs_income",
    "TaiwanStockBalanceSheet": "finmind_bs",
    "TaiwanStockCashFlowsStatement": "finmind_cf",
    "TaiwanStockPrice": "finmind_price",
    "TaiwanStockTradingDate": "finmind_trading_date",
}
MANUAL_SOURCE_ID = {
    "announce_times.csv": "mops_announce",
    "balance_overrides.csv": "mops_balance_overrides",
    "macro.csv": "fred_macro",
    "evidence.csv": "mops_announce",
}


def die(msg: str) -> None:
    print(f"[中止] {msg}")
    sys.exit(1)


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def main() -> None:
    if not SNAPSHOT.exists():
        die("找不到 data/financial-snapshots.json")
    snap_bytes = SNAPSHOT.read_bytes()
    snap = json.loads(snap_bytes)
    registered = set()
    if REGISTER.exists():
        with REGISTER.open(encoding="utf-8") as f:
            registered = {r["source_id"] for r in csv.DictReader(f)}

    # 1) FinMind 原始檔
    raw_rows = []
    for raw in snap.get("source_manifest", {}).get("raw_files", []):
        sid = ("finmind_tw_market" if raw["dataset"] == "TaiwanStockPrice" and raw["data_id"] == "TAIEX"
               else DATASET_SOURCE_ID.get(raw["dataset"]))
        if sid is None:
            die(f"未登記的資料集：{raw['dataset']}")
        if registered and sid not in registered:
            die(f"{sid} 不在 source-register.csv")
        path = ROOT / raw["file"]
        present = path.exists()
        if present and sha256_bytes(path.read_bytes()) != raw["sha256"]:
            die(f"{raw['file']} 重算 sha256 與快照紀錄不符")
        raw_rows.append({
            "source_id": sid,
            "dataset": raw["dataset"],
            "entity": raw["data_id"] or "ALL",
            "request_range": [raw["start"], raw["end"]],
            "captured_at": raw["captured_at"],
            "content_hash": raw["sha256"],
            "file": raw["file"],
            "file_present": present,
            "hash_verified": present,
            "license_note": "FinMind 原始回應不可轉散布；僅保存於本機與 repo（.gitignore 視授權）",
        })

    # 2) 人工整理檔
    manual_rows = []
    for path in sorted(MANUAL_DIR.glob("*.csv")):
        sid = MANUAL_SOURCE_ID.get(path.name)
        if sid is None:
            die(f"未登記的人工檔：{path.name}")
        manual_rows.append({
            "source_id": sid,
            "file": f"data/manual/{path.name}",
            "content_hash": sha256_bytes(path.read_bytes()),
            "modified_at": datetime.fromtimestamp(path.stat().st_mtime, TW).isoformat(timespec="seconds"),
            "note": "檔案修改時間，不代表原始資料取得時間",
        })

    # 3) 證據片段
    evidence_rows = []
    for ev in snap.get("evidences", []):
        para = ev.get("paragraph")
        if para is not None and sha256_bytes(para.encode("utf-8")) != ev.get("content_hash"):
            die(f"{ev['evidence_version_id']} content_hash 與 paragraph 不符")
        evidence_rows.append({
            "evidence_version_id": ev["evidence_version_id"],
            "source_id": ev["source_id"],
            "ticker": ev["ticker"],
            "published_at": ev.get("published_at"),
            "available_at": ev.get("available_at"),
            "captured_at": ev.get("captured_at"),
            "source_url": ev.get("source_url"),
            "content_hash": ev.get("content_hash"),
            "time_verified": False,
            "note": "published_at 尚未逐筆對照 MOPS 發言紀錄核實",
        })

    out = {
        "manifest_version": "v1.3-w03",
        "generated_by": "scripts/build_source_manifest.py",
        "generated_at": datetime.now(TW).isoformat(timespec="seconds"),
        "hash_algorithm": "sha256",
        "lock_status": "draft_w03（W06 凍結時鎖定）",
        "statement_basis": "consolidated",
        "snapshot": {
            "file": "data/financial-snapshots.json",
            "content_hash": sha256_bytes(snap_bytes),
            "manifest_version": snap.get("manifest_version"),
            "cutoff": snap.get("cutoff"),
            "generated_at": snap.get("generated_at"),
        },
        "raw_files": raw_rows,
        "manual_files": manual_rows,
        "evidences": evidence_rows,
        "summary": {
            "raw_files": len(raw_rows),
            "raw_files_present": sum(r["file_present"] for r in raw_rows),
            "manual_files": len(manual_rows),
            "evidences": len(evidence_rows),
            "null_hashes": sum(1 for r in raw_rows + manual_rows + evidence_rows if not r["content_hash"]),
        },
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    s = out["summary"]
    print(f"寫入 {OUT.relative_to(ROOT)}：原始檔 {s['raw_files']}（本機 {s['raw_files_present']}）、"
          f"人工檔 {s['manual_files']}、證據 {s['evidences']}、null hash {s['null_hashes']}")


if __name__ == "__main__":
    main()