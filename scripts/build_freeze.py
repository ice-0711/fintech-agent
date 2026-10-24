"""scripts/build_freeze.py — W06-B 凍結 30 案、來源 hash、工具版本與 2D 關係資料

兩段凍結（組長 2026-10-23 核定，handoff/decisions-2026-10.md 第六節）
-------------------------------------------------------------------
- 第一段（10/23，本腳本嚴格核對）：案例、分組、資料、人工檔、FinMind 原始檔、B 的工具與計算程式、評分規則。
  --verify 只要有一個檔案被改就失敗。
- 第二段（10/26 live 再驗、W09 前鎖定）：Researcher/Reviewer prompt 與 Agent 程式（組長負責）。
  本腳本照樣記錄 hash 作為參照；--verify 只列出變動、不判失敗。組長宣布鎖定後執行
  `python scripts/build_freeze.py --lock-agent` 重新記錄，之後改用 `--verify --strict` 全部嚴格核對。

輸出（四個 W06 必交產物）
------------------------
- evaluation/cases_manifest_v1.json ：30 案（10 開發 + 20 保留）之 ID、股票、用途、快照與 hash；不含答案
- data/v12-frozen-manifest.json     ：資料、原始檔、人工檔、同業快照、工具程式與 prompt 之 hash 與版本
- graph-approved.json               ：F06 2D 圖核准資料（只收有原句、文件日期、來源者；獨立於正式案例）
- data-freeze.md                    ：凍結說明、30 案清單、禁止改寫清單、簽核欄

執行
----
    python scripts/build_freeze.py            # 先跑全部檢查，通過才產生四個檔
    python scripts/build_freeze.py --verify   # 凍結後核對：第一段須一致；第二段只列出變動
    python scripts/build_freeze.py --verify --strict   # W09 鎖定後：第二段也須一致
    python scripts/build_freeze.py --lock-agent        # 組長鎖定 prompt/Agent 程式後，B 執行以記錄第二段

hash 規則
---------
- 文字檔（.py .md .csv .json .txt）以「LF 換行」計算 sha256（sha256_lf），
  避免 Windows CRLF 或 git autocrlf 造成同內容不同 hash。
- data/raw/ 下 FinMind 原始回應以原始位元組計算（與快照 source_manifest 紀錄一致）。
- 案例與快照以標準化 JSON（sort_keys）計算，與檔案排版無關。
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TW = timezone(timedelta(hours=8))
FREEZE_VERSION = "cases-v1"
PLANNED_SIGN_DATE = "2026-10-23"
AGENT_LOCK_DEADLINE = "W09 前（10/26 開發集 live 再驗後）"

OUT_CASES = ROOT / "evaluation" / "cases_manifest_v1.json"
OUT_FROZEN = ROOT / "data" / "v12-frozen-manifest.json"
OUT_GRAPH = ROOT / "graph-approved.json"
OUT_MD = ROOT / "data-freeze.md"

DATA_FILES = [
    "data/financial-snapshots.json", "data/source-manifest.json", "data/v12-peer-snapshot.json",
    "data/v12-finance-fact-sheet.md", "data/v12-financial-fixtures.json", "data/tool-contracts.json",
    "data/tool-field-map.md", "data/v12-field-map.csv", "data-contract.md", "source-register.csv",
    "graph-source-register.csv", "graph-reviewed.csv", "fixtures/tool-responses.json",
]
CASE_FILES = [
    "evaluation/dev-cases.json", "fixtures/dev/case_fixtures.json",
    "evaluation/test-cases-sealed.json", "fixtures/test/test-cases-sealed.json",
    "fixtures/test/case_fixtures.json",
]
# 第一段：B 的工具與計算程式（決定數字，與資料一起凍結）
TOOL_FILES = [
    "agents/tools_impl.py", "agents/calculator.py", "agents/register_tools.py", "valuation_agent/dcf_model.py",
]
# 第一段：評分規則（D）
RUBRIC_FILES = ["evaluation/d-drafts/rubric-v1-final.md", "evaluation/d-drafts/protocol-v1.md"]
# 第二段：Agent 程式（組長，W09 前鎖定）
AGENT_FILES = [
    "agents/tools.py", "agents/snapshot.py", "agents/contract.py", "agents/review_checks.py",
    "agents/review_contract.py", "agents/research_graph.py", "agents/provider.py",
]
PROMPT_FILES = ["agents/prompts/researcher-v1.2.txt", "agents/prompts/reviewer-v1.2.txt"]
STAGE1_GROUPS = ("data_files", "tool_files", "rubric_files", "manual_files")
STAGE2_GROUPS = ("agent_files", "prompt_files")
# 開發用、會進入模型上下文的檔案：不得含保留案例答案
DEV_CONTEXT_FILES = PROMPT_FILES + ["fixtures/dev/case_fixtures.json", "evaluation/dev-cases.json",
                                    "fixtures/tool-responses.json"]
MAX_NODES, MAX_EDGES = 20, 30


# ---------------------------------------------------------------------------
def sha256_lf(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def sha256_raw(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sha256_obj(obj) -> str:
    return hashlib.sha256(json.dumps(obj, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def load(rel: str):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def file_entry(rel: str) -> dict:
    p = ROOT / rel
    if not p.exists():
        return {"path": rel, "present": False, "sha256_lf": None}
    return {"path": rel, "present": True, "sha256_lf": sha256_lf(p), "bytes": p.stat().st_size}


def run_module_main(rel: str) -> int:
    spec = importlib.util.spec_from_file_location(Path(rel).stem, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.main([]) if "argv" in mod.main.__code__.co_varnames else mod.main()


def die(msg: str) -> None:
    print(f"[中止] {msg}")
    sys.exit(1)


# ---------------------------------------------------------------------------
# 檢查
# ---------------------------------------------------------------------------
def preflight() -> list[str]:
    print("== 1/3 案例與關係檢查（check_cases.py）")
    if run_module_main("scripts/check_cases.py") != 0:
        die("check_cases.py 未通過，不可凍結")
    print("== 2/3 來源與 cutoff 檢查（check_sources.py）")
    if run_module_main("scripts/check_sources.py") != 0:
        die("check_sources.py 未通過，不可凍結")
    print("== 3/3 保留答案隔離檢查")
    sealed = load("evaluation/test-cases-sealed.json")
    test_fx = load("fixtures/test/case_fixtures.json")
    needles = set()
    for c in sealed["cases"]:
        needles.add(c["case_id"])
        needles.add(c["source_snapshot_id"])
        needles.update(x for x in c.get("expected_supported_claims", []) + c.get("expected_rejected_claims", []) if x)
    for s in test_fx["snapshots"].values():
        needles.update(e["evidence_version_id"] for e in s.get("evidences", []))
    problems = []
    for rel in DEV_CONTEXT_FILES:
        p = ROOT / rel
        if p.exists():
            text = p.read_text(encoding="utf-8")
            hits = sorted(n for n in needles if n in text)
            if hits:
                problems.append(f"{rel} 含保留案例內容：{hits[:5]}")
    if problems:
        die("；".join(problems))
    missing = [r for r in DATA_FILES + CASE_FILES + TOOL_FILES + RUBRIC_FILES + AGENT_FILES + PROMPT_FILES
               if not (ROOT / r).exists()]
    if missing:
        die(f"缺檔：{missing}")
    print("   保留答案未出現在 prompt、開發快照、開發案例與工具 fixture 中")
    return []


# ---------------------------------------------------------------------------
# 1) cases_manifest_v1.json
# ---------------------------------------------------------------------------
def build_cases_manifest(now: str) -> dict:
    dev, dev_fx = load("evaluation/dev-cases.json"), load("fixtures/dev/case_fixtures.json")
    test, test_fx = load("evaluation/test-cases-sealed.json"), load("fixtures/test/case_fixtures.json")
    rows = []
    for split, data, fx in (("dev", dev, dev_fx), ("test", test, test_fx)):
        for c in data["cases"]:
            snap = fx["snapshots"][c["source_snapshot_id"]]
            rows.append({
                "case_id": c["case_id"], "split": split, "ticker": c["ticker"],
                "category": c["category"], "variant": c["variant"],
                "cutoff_at": c["cutoff_at"], "source_snapshot_id": c["source_snapshot_id"],
                "synthetic_fixture": bool(snap.get("synthetic_fixture")),
                "has_perturbation": bool(c.get("perturbation_location")),
                "evidence": [{"evidence_version_id": e["evidence_version_id"], "content_hash": e.get("content_hash"),
                              "synthetic_fixture": e.get("synthetic_fixture")} for e in snap.get("evidences", [])],
                "case_hash": sha256_obj(c),
                "snapshot_hash": sha256_obj(snap),
            })
    rows.sort(key=lambda r: r["case_id"])
    n_dev = sum(r["split"] == "dev" for r in rows)
    n_test = sum(r["split"] == "test" for r in rows)
    if (n_dev, n_test, len(rows)) != (10, 20, 30):
        die(f"案例數不符：dev {n_dev}、test {n_test}、合計 {len(rows)}")
    return {
        "manifest_version": FREEZE_VERSION, "frozen_at": now, "planned_sign_date": PLANNED_SIGN_DATE,
        "generated_by": "scripts/build_freeze.py",
        "split_rule": "手冊第 06 章 30 案固定分配表；30 = 10 開發 + 20 保留",
        "counts": {"dev": n_dev, "test": n_test, "total": len(rows)},
        "answer_policy": "本檔不含任何標準答案；保留答案只存在 evaluation/test-cases-sealed.json，僅供 D 評分",
        "source_files": [file_entry(r) for r in CASE_FILES],
        "cases": rows,
        "cases_digest": sha256_obj([[r["case_id"], r["case_hash"], r["snapshot_hash"]] for r in rows]),
    }


# ---------------------------------------------------------------------------
# 2) v12-frozen-manifest.json
# ---------------------------------------------------------------------------
def build_frozen_manifest(now: str, cases_manifest: dict) -> dict:
    snap = load("data/financial-snapshots.json")
    raw_rows = []
    for raw in snap["source_manifest"]["raw_files"]:
        p = ROOT / raw["file"]
        present = p.exists()
        actual = sha256_raw(p) if present else None
        if present and actual != raw["sha256"]:
            die(f"{raw['file']} 原始檔 hash 與快照紀錄不符")
        raw_rows.append({"file": raw["file"], "dataset": raw["dataset"], "entity": raw["data_id"] or "ALL",
                         "captured_at": raw["captured_at"], "sha256": raw["sha256"], "present": present,
                         "verified": present})
    if any(not r["sha256"] for r in raw_rows):
        die("原始檔 hash 有 null")
    manual = [file_entry(f"data/manual/{p.name}") for p in sorted((ROOT / "data" / "manual").glob("*.csv"))]

    sys.path.insert(0, str(ROOT))
    from agents import contract, tools  # noqa: E402
    peer = load("data/v12-peer-snapshot.json")
    return {
        "manifest_version": FREEZE_VERSION, "frozen_at": now, "planned_sign_date": PLANNED_SIGN_DATE,
        "generated_by": "scripts/build_freeze.py",
        "hash_rule": "文字檔 sha256_lf（CRLF→LF 後計算）；data/raw 原始檔為原始位元組 sha256",
        "versions": {
            "tools_version": tools.TOOLS_VERSION, "contract_version": contract.CONTRACT_VERSION,
            "question_version": contract.QUESTION_VERSION, "prompt_version": contract.PROMPT_VERSION,
            "tool_contract": load("data/tool-contracts.json").get("contract_version"),
            "snapshot_manifest": snap.get("manifest_version"), "snapshot_cutoff": snap.get("cutoff"),
            "peer_snapshot": peer.get("snapshot_version"),
            "macro_whitelist": list(tools.MACRO_SERIES_WHITELIST),
        },
        "cases": {"file": "evaluation/cases_manifest_v1.json", "cases_digest": cases_manifest["cases_digest"],
                  "counts": cases_manifest["counts"]},
        "peer_lock": {
            "subject": peer["subject"], "price_as_of": peer["price_as_of"], "cutoff_at": peer["cutoff_at"],
            "roles": {t: c["role"] for t, c in peer["companies"].items()},
            "peer_summary_statistics": peer["peer_summary_statistics"],
            "file_sha256_lf": sha256_lf(ROOT / "data" / "v12-peer-snapshot.json"),
        },
        "data_files": [file_entry(r) for r in DATA_FILES],
        "raw_files": raw_rows,
        "manual_files": manual,
        "freeze_stages": {
            "stage1": {"frozen_at": now, "groups": list(STAGE1_GROUPS) + ["raw_files", "cases"],
                       "rule": "案例、分組、資料、B 工具、評分規則；--verify 嚴格核對"},
            "stage2": {"groups": list(STAGE2_GROUPS), "locked": False, "locked_at": None,
                       "deadline": AGENT_LOCK_DEADLINE,
                       "rule": "prompt 與 Agent 程式；鎖定前 hash 僅供參照，--verify 只列變動"},
        },
        "tool_files": [file_entry(r) for r in TOOL_FILES],
        "rubric_files": [file_entry(r) for r in RUBRIC_FILES],
        "agent_files": [file_entry(r) for r in AGENT_FILES],
        "prompt_files": [file_entry(r) for r in PROMPT_FILES],
        "summary": {
            "raw_files": len(raw_rows), "raw_files_present": sum(r["present"] for r in raw_rows),
            "null_hashes": sum(1 for r in raw_rows if not r["sha256"]),
        },
        "approved": ["DCF：WACC 9%、g 3%、5 年持平 FCF（組長 2026-10-21）",
                     "淨負債口徑：應付短期票券年度路徑不計入、租賃負債不計入（組長 2026-10-21）",
                     "股價可得時間全專案 17:30；開發案例 v1.5；F06 延後；2317 不做 FCF 正常化（組長 2026-10-22）",
                     "model 維持 gemini-3.5-flash-lite；兩段凍結（組長 2026-10-23）"],
        "pending_approvals": ["CR-W06：agents/snapshot.py 保留集防護（無發布時間片段以 captured_at 判定、tool_simulation no_data、CASE-23／28 輸入），W10 保留集執行前需完成；屬第二段",
                              "審查規則 basis_unspecified（CASE-11-flawed 目前可通過審查，docs/B-review-W06-D-redo.md）；屬第二段",
                              "CASE-26 live 測不到逾時：snap-dev-case-26 無可搜尋證據，模型不會讀取目標來源；修正需開發快照改版（cases-v2）"],
    }


# ---------------------------------------------------------------------------
# 3) graph-approved.json
# ---------------------------------------------------------------------------
def build_graph(now: str) -> dict:
    with (ROOT / "graph-reviewed.csv").open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    edges, excluded = [], []
    for i, r in enumerate(rows, start=1):
        reasons = [k for k in ("quote_original", "doc_date") if not r.get(k)]
        if not (r.get("evidence_url") or r.get("evidence_file")):
            reasons.append("source")
        if r.get("review_status") != "source_text_verified":
            reasons.append("review_status")
        if reasons:
            excluded.append({"row": i + 1, "missing": reasons})
            continue
        edges.append({
            "relation_id": f"REL-{len(edges) + 1:02d}",
            "source": r["source_ticker"], "target": r["target_ticker"], "relation_type": r["relation_type"],
            "quote_original": r["quote_original"], "quote_pdf_page": r.get("quote_pdf_page"),
            "doc_date": r["doc_date"], "doc_date_basis": r.get("doc_date_basis"),
            "evidence_title": r.get("evidence_title"), "evidence_url": r.get("evidence_url"),
            "evidence_file": r.get("evidence_file"), "register_id": r.get("register_id"),
            "verified_date": r.get("verified_date"), "verified_by": r.get("verified_by"),
        })
    names = {}
    for r in rows:
        names[r["source_ticker"]] = r["source_name"]
        names[r["target_ticker"]] = r["target_name"]
    used = sorted({e["source"] for e in edges} | {e["target"] for e in edges})
    nodes = [{"id": t, "label": names.get(t, t), "role": "industry_reference" if t == "2330" else "company"}
             for t in used]
    if len(nodes) > MAX_NODES or len(edges) > MAX_EDGES:
        die(f"關係圖超過上限：{len(nodes)} 點、{len(edges)} 線")
    peer = load("data/v12-peer-snapshot.json")
    return {
        "graph_version": "graph-v1", "approved_at": now, "generated_by": "scripts/build_freeze.py",
        "conditional_feature": "F06（條件式）；本檔獨立保存，不屬於 30 案正式實驗輸入，不得改寫任何案例",
        "llm_usage": 0,
        "limits": {"max_nodes": MAX_NODES, "max_edges": MAX_EDGES},
        "rules": ["只收 review_status = source_text_verified 且有原句、文件日期、來源者",
                  "verified_date 為審核日，不代替 doc_date", "不以 LLM 推測供應關係"],
        "supply_graph": {"nodes": nodes, "edges": edges, "excluded_rows": excluded,
                         "source_file": "graph-reviewed.csv",
                         "source_sha256_lf": sha256_lf(ROOT / "graph-reviewed.csv")},
        "peer_panel": {
            "source_file": "data/v12-peer-snapshot.json",
            "source_sha256_lf": sha256_lf(ROOT / "data" / "v12-peer-snapshot.json"),
            "price_as_of": peer["price_as_of"],
            "nodes": [{"id": t, "label": c["name"], "role": c["role"], "include_in_peer_stats": c["role"] == "peer"}
                      for t, c in peer["companies"].items()],
        },
    }


# ---------------------------------------------------------------------------
# 4) data-freeze.md
# ---------------------------------------------------------------------------
def build_md(now: str, cm: dict, fm: dict, gr: dict) -> str:
    L = ["# 資料與案例凍結紀錄（W06-B，cases-v1）", "",
         f"- 產生時間：{now}（`python scripts/build_freeze.py`）",
         f"- 預定簽出：{PLANNED_SIGN_DATE}",
         f"- 案例摘要 hash（cases_digest）：`{cm['cases_digest']}`",
         f"- 工具版本：{fm['versions']['tools_version']}；契約 {fm['versions']['tool_contract']}；"
         f"prompt {fm['versions']['prompt_version']}；快照 {fm['versions']['snapshot_manifest']}",
         "- 核對：`python scripts/build_freeze.py --verify`", "",
         "## 一、30 案（10 開發 + 20 保留）", "",
         "| 案例 | 用途 | 股票 | 類別 | 變體 | cutoff | 合成 | case_hash（前 12 碼） |", "|---|---|---|---|---|---|---|---|"]
    for r in cm["cases"]:
        L.append(f"| {r['case_id']} | {'開發' if r['split'] == 'dev' else '保留'} | {r['ticker']} | {r['category']} | "
                 f"{r['variant']} | {r['cutoff_at'][:16]} | {'是' if r['synthetic_fixture'] else '否'} | `{r['case_hash'][:12]}` |")
    L += ["", "保留案例的標準答案只在 `evaluation/test-cases-sealed.json`，只供 D 評分；本檔與 `cases_manifest_v1.json` 不含答案。", "",
          "## 二、來源 hash", "",
          f"- FinMind 原始檔 {fm['summary']['raw_files']} 個（本機 {fm['summary']['raw_files_present']} 個已重算核對），null hash {fm['summary']['null_hashes']} 個",
          f"- 人工檔 {len(fm['manual_files'])} 個；資料檔 {len(fm['data_files'])} 個；B 工具程式 {len(fm['tool_files'])} 個；"
          f"評分規則 {len(fm['rubric_files'])} 個（以上第一段）",
          f"- Agent 程式 {len(fm['agent_files'])} 個；prompt {len(fm['prompt_files'])} 個（第二段，"
          f"{'已鎖定 ' + fm['freeze_stages']['stage2']['locked_at'] if fm['freeze_stages']['stage2']['locked'] else '未鎖定，' + AGENT_LOCK_DEADLINE + '鎖定'}）",
          "- 完整清單見 `data/v12-frozen-manifest.json`", "",
          "## 三、同業資料鎖定", "",
          f"- 主體 {fm['peer_lock']['subject']}；股價日 {fm['peer_lock']['price_as_of']}；cutoff {fm['peer_lock']['cutoff_at']}",
          f"- 角色：{', '.join(f'{t}={r}' for t, r in fm['peer_lock']['roles'].items())}",
          f"- 同業平均：P/E {fm['peer_lock']['peer_summary_statistics']['peer_avg_pe']}、"
          f"P/B {fm['peer_lock']['peer_summary_statistics']['peer_avg_pb']}（2330 排除）", "",
          "## 四、F06 關係圖（條件式，獨立保存）", "",
          f"- `graph-approved.json`：{len(gr['supply_graph']['nodes'])} 點、{len(gr['supply_graph']['edges'])} 線；"
          f"剔除 {len(gr['supply_graph']['excluded_rows'])} 列（缺原句、文件日期或來源）",
          "- 不屬於正式實驗輸入，修改關係圖不得改動任何案例或快照", "",
          "## 五、禁止改寫清單（凍結後）", "",
          "兩段凍結（組長 2026-10-23）：第一段 10/23 凍結，`--verify` 嚴格核對；"
          "第二段 prompt 與 Agent 程式於 10/26 開發集 live 再驗後、W09 前鎖定，鎖定前 `--verify` 只列出變動。", "",
          "**第一段（10/23 起不得改寫）**", ""]
    for r in CASE_FILES + ["data/financial-snapshots.json", "data/raw/finmind/*", "data/manual/*.csv",
                           "data/v12-peer-snapshot.json"] + TOOL_FILES + RUBRIC_FILES:
        L.append(f"- `{r}`")
    L += ["", "**第二段（W09 前鎖定；只用開發集調整，保留集不動）**", ""]
    for r in AGENT_FILES + PROMPT_FILES:
        L.append(f"- `{r}`")
    L += ["", "凍結後若必須修改：重跑對應產生腳本 → `python scripts/check_cases.py` → `python scripts/build_freeze.py`，"
          "新版本另立 cases-v2，並依手冊第 06 章重跑受影響模式；不得覆寫 v1 紀錄。", "",
          "## 六、待核定（不影響凍結，但影響結果解讀）", ""]
    L += [f"- {x}" for x in fm["pending_approvals"]]
    L += ["", "## 七、簽核", "", "| 角色 | 姓名 | 日期 | 簽核 |", "|---|---|---|---|",
          "| B（產出） |  |  |  |", "| D（核對標準主張與擾動） |  |  |  |", "| 組長（核准凍結） |  |  |  |", ""]
    return "\n".join(L)


# ---------------------------------------------------------------------------
def _changed(entries: list[dict]) -> list[str]:
    out = []
    for e in entries:
        p = ROOT / e["path"]
        if not p.exists() or sha256_lf(p) != e["sha256_lf"]:
            out.append(e["path"])
    return out


def verify(strict: bool = False) -> int:
    if not OUT_FROZEN.exists() or not OUT_CASES.exists():
        die("尚未凍結（缺 v12-frozen-manifest.json 或 cases_manifest_v1.json）")
    fm, cm = load("data/v12-frozen-manifest.json"), load("evaluation/cases_manifest_v1.json")
    two_stage = "freeze_stages" in fm
    stage2_locked = two_stage and fm["freeze_stages"]["stage2"].get("locked")
    groups1 = STAGE1_GROUPS if two_stage else ("data_files", "tool_files", "prompt_files", "manual_files")
    bad = []
    for group in groups1:
        bad += _changed(fm.get(group, []))
    bad += _changed(cm["source_files"])
    for r in fm["raw_files"]:
        p = ROOT / r["file"]
        if p.exists() and sha256_raw(p) != r["sha256"]:
            bad.append(r["file"])
    drift = []
    if two_stage:
        for group in STAGE2_GROUPS:
            drift += _changed(fm.get(group, []))
    if strict or stage2_locked:
        bad, drift = bad + drift, []
    if bad:
        print(f"凍結後被修改：{len(bad)} 個")
        for b in bad:
            print("  ✗", b)
        return 1
    print(f"凍結紀錄一致（{FREEZE_VERSION}，cases_digest {cm['cases_digest'][:12]}）")
    if drift:
        print(f"第二段（prompt／Agent 程式，{AGENT_LOCK_DEADLINE}鎖定）有 {len(drift)} 個檔案與參照 hash 不同，屬開發調整，不判失敗：")
        for d in drift:
            print("  ~", d)
    return 0


def lock_agent() -> int:
    """組長宣布 prompt 與 Agent 程式鎖定後執行：重新記錄第二段 hash，之後 --verify 全部嚴格核對。"""
    if not OUT_FROZEN.exists():
        die("尚未凍結，請先執行 python scripts/build_freeze.py")
    if verify() != 0:
        die("第一段已被修改，不可鎖定第二段；請先處理（必要時另立 cases-v2）")
    fm = load("data/v12-frozen-manifest.json")
    if "freeze_stages" not in fm:
        die("舊版凍結紀錄沒有兩段資訊，請先重跑 python scripts/build_freeze.py")
    now = datetime.now(TW).isoformat(timespec="seconds")
    sys.path.insert(0, str(ROOT))
    from agents import contract  # noqa: E402
    fm["agent_files"] = [file_entry(r) for r in AGENT_FILES]
    fm["prompt_files"] = [file_entry(r) for r in PROMPT_FILES]
    fm["versions"]["prompt_version"] = contract.PROMPT_VERSION
    fm["freeze_stages"]["stage2"].update({"locked": True, "locked_at": now})
    OUT_FROZEN.write_text(json.dumps(fm, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md = OUT_MD.read_text(encoding="utf-8")
    note = f"\n- 第二段鎖定：{now}（prompt {contract.PROMPT_VERSION}；`python scripts/build_freeze.py --lock-agent`）"
    if "第二段鎖定：" not in md:
        md = md.replace("- 核對：`python scripts/build_freeze.py --verify`",
                        "- 核對：`python scripts/build_freeze.py --verify`" + note, 1)
        OUT_MD.write_text(md, encoding="utf-8")
    print(f"第二段已鎖定（{now}）：Agent 程式 {len(AGENT_FILES)} 個、prompt {len(PROMPT_FILES)} 個；之後 --verify 全部嚴格核對")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="W06-B 凍結 30 案與來源 hash")
    ap.add_argument("--verify", action="store_true", help="只核對現有檔案是否與凍結紀錄一致")
    ap.add_argument("--strict", action="store_true", help="與 --verify 併用：第二段變動也判失敗")
    ap.add_argument("--lock-agent", action="store_true", help="組長鎖定 prompt/Agent 程式後，記錄第二段 hash")
    args = ap.parse_args(argv)
    if args.lock_agent:
        return lock_agent()
    if args.verify:
        return verify(strict=args.strict)

    preflight()
    now = datetime.now(TW).isoformat(timespec="seconds")
    cm = build_cases_manifest(now)
    fm = build_frozen_manifest(now, cm)
    gr = build_graph(now)
    md = build_md(now, cm, fm, gr)
    for path, obj in ((OUT_CASES, cm), (OUT_FROZEN, fm), (OUT_GRAPH, gr)):
        path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    OUT_MD.write_text(md, encoding="utf-8")
    print(f"\n凍結完成（第一段）：30 案（10 開發 + 20 保留）、原始檔 {fm['summary']['raw_files']} 個、"
          f"關係圖 {len(gr['supply_graph']['edges'])} 線；第二段 prompt／Agent 程式{AGENT_LOCK_DEADLINE}鎖定")
    for p in (OUT_CASES, OUT_FROZEN, OUT_GRAPH, OUT_MD):
        print("  寫入", p.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())