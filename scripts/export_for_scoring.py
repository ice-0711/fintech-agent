"""W11 盲評匯出：把正式評估的 60 份答卷去掉模式資訊、打亂順序，交給 B、D 獨立評分（protocol-v1 第五節第 4 點）。

    .venv/bin/python scripts/export_for_scoring.py            # 產生盲評檔（預設要求 60 run 都已執行）
    .venv/bin/python scripts/export_for_scoring.py --reveal   # B、D 評分都交了以後，公開對照表

輸出（evaluation/formal/scoring-v2/）
- answers.jsonl：一行一份答卷。answer_id（隨機）、case_id、status（succeeded／insufficient_evidence／failed…）、
  最終草稿（主張、引用、限制、衝突、未知、下一確認訊號、摘要）、主張引用到的工具結果摘要與來源原文。
- answers.md：同內容的可讀版，逐份列出，方便評分。
- score-template-B.txt、score-template-D.txt：照 rubric 格式預留每份答卷的評分欄。
- key-commitment.json：對照表的 sha256。對照表本身（answer_id → run_id、mode）存在組長 Mac 的
  tmp/formal_v2-scoring-key.json，不進 git；--reveal 時才複製進來，並核對 sha256 與事先公開的一致。

去掉的資訊（會洩漏模式）：mode、stop_reason、覆核紀錄、預算與發送次數、工具呼叫順序、Reviewer 的工具結果、
執行時間。草稿是最後一版（dual 經覆核修正後的版本）。

這支程式讀封存案例與保留集草稿，只寫檔、不在終端印任何內容；組長與 Claude 不打開輸出檔。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import secrets
import shutil
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import formal_runs as fr  # noqa: E402
from agents.snapshot import SnapshotToolbox  # noqa: E402

OUT = ROOT / "evaluation" / "formal" / "scoring-v2"
KEY = ROOT / "tmp" / "formal_v2-scoring-key.json"
DRAFT_FIELDS = ("status", "decision_summary", "claims", "conflicts", "unknowns", "next_signals", "limitations",
                "macro_observations", "fundamental_observations", "valuation_scenarios", "positive_channels",
                "negative_channels")


def _refs(draft: dict) -> list[str]:
    out: list[str] = []
    for c in draft.get("claims") or []:
        for r in c.get("evidence_refs") or []:
            if r and r not in out:
                out.append(r)
    return out


def answer_for(run: dict, job: dict | None, case: dict) -> dict:
    """One blinded answer. Only the Researcher's observations that the final draft cites are kept."""
    draft = (job or {}).get("draft") or {}
    cp = (job or {}).get("checkpoint") or {}
    obs = {o["obs_id"]: o for o in cp.get("observations") or [] if o.get("role") == "researcher"}
    cited_obs, cited_ev = [], []
    for ref in _refs(draft):
        if ref.startswith("obs-"):
            o = obs.get(ref)
            cited_obs.append({"obs_id": ref, "found": o is not None,
                              **({"tool": o["tool_name"], "status": o["status"], "result_brief": o.get("brief")} if o else {})})
        elif ref.startswith("ev-"):
            ev = SnapshotToolbox(case["ticker"], case["source_snapshot_id"], case["cutoff_at"]).read_evidence(ref)
            cited_ev.append({"evidence_version_id": ref, "status": ev.get("status"),
                             "paragraph": (ev.get("data") or {}).get("paragraph")})
        else:
            cited_ev.append({"evidence_version_id": ref, "status": "unknown_ref", "paragraph": None})
    return {"case_id": run["case_id"], "status": run.get("status") or (job or {}).get("status"),
            "draft": {k: draft[k] for k in DRAFT_FIELDS if k in draft} if draft else None,
            "cited_observations": cited_obs, "cited_evidence": cited_ev,
            "note": None if draft else "此 run 沒有產出草稿（失敗或中止），依 rubric 記為作業失敗"}


def export(partial: bool = False, db: Path = fr.DB) -> dict:
    plan = json.loads(fr.PLAN.read_text(encoding="utf-8"))
    done = fr.done_runs()
    missing = [r["run_id"] for r in plan["runs"] if r["run_id"] not in done]
    if missing and not partial:
        sys.exit(f"還有 {len(missing)} 個 run 未執行，不匯出（試做請加 --partial）")
    if OUT.exists() and any(OUT.iterdir()):
        sys.exit(f"{OUT} 已有檔案，不覆寫（盲評檔只產生一次）")
    cases = fr.load_holdout()
    con = sqlite3.connect(db)
    jobs = {r[0]: json.loads(r[1]) for r in con.execute("select job_id, data from research_jobs")}
    con.close()
    runs = [done[r["run_id"]] for r in plan["runs"] if r["run_id"] in done]
    order = list(range(len(runs)))
    rng = secrets.SystemRandom()
    rng.shuffle(order)
    used: set[str] = set()
    answers, key = [], []
    for i in order:
        run = runs[i]
        while (aid := f"A-{secrets.token_hex(3)}") in used:
            pass
        used.add(aid)
        answers.append({"answer_id": aid, **answer_for(run, jobs.get(run.get("job_id")), cases[run["case_id"]])})
        key.append({"answer_id": aid, "run_id": run["run_id"], "mode": run["mode"], "job_id": run.get("job_id")})
    key_doc = {"experiment": fr.EXPERIMENT, "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "n": len(key), "partial": bool(missing), "key": key}
    key_bytes = json.dumps(key_doc, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
    KEY.parent.mkdir(exist_ok=True)
    KEY.write_bytes(key_bytes)
    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / "answers.jsonl").open("w", encoding="utf-8") as f:
        for a in answers:
            f.write(json.dumps(a, ensure_ascii=False) + "\n")
    (OUT / "answers.md").write_text(render_md(answers), encoding="utf-8")
    for who in ("B", "D"):
        (OUT / f"score-template-{who}.txt").write_text(template(answers, who), encoding="utf-8")
    commit = {"experiment": fr.EXPERIMENT, "n_answers": len(answers), "partial": bool(missing),
              "key_sha256": hashlib.sha256(key_bytes).hexdigest(), "key_location": "組長 Mac tmp/formal_v2-scoring-key.json（不進 git）",
              "created_at": key_doc["created_at"],
              "rule": "B、D 都交出評分後才執行 --reveal；公開的對照表 sha256 必須與此相同"}
    (OUT / "key-commitment.json").write_text(json.dumps(commit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return commit


def render_md(answers: list[dict]) -> str:
    out = ["# 正式評估 v2 盲評答卷", "",
           "每份答卷只有案例與最終草稿；模式、停止原因、覆核紀錄、預算都已移除。評分請照 rubric-v1-final.md，",
           "兩人獨立評分、先不看對方分數。obs-* 只附摘要（最多 500 字），需要完整數字請用同一快照重算工具結果。", ""]
    for a in answers:
        out += [f"## {a['answer_id']}｜{a['case_id']}｜{a['status']}", ""]
        d = a["draft"]
        if not d:
            out += [a["note"], ""]
            continue
        out += [f"摘要：{d.get('decision_summary') or ''}", ""]
        for c in d.get("claims") or []:
            out.append(f"- {c.get('claim_id')}（{c.get('kind')}）{c.get('text')}　引用：{', '.join(c.get('evidence_refs') or []) or '無'}")
        for k, label in (("conflicts", "衝突"), ("unknowns", "未知"), ("next_signals", "下一確認訊號"), ("limitations", "限制")):
            if d.get(k):
                out.append(f"- {label}：{json.dumps(d[k], ensure_ascii=False)}")
        out.append("")
        for o in a["cited_observations"]:
            out.append(f"  - {o['obs_id']}：" + (f"{o['tool']}／{o['status']}：{o.get('result_brief')}" if o["found"] else "找不到這個工具結果"))
        for e in a["cited_evidence"]:
            out.append(f"  - {e['evidence_version_id']}（{e['status']}）：{e.get('paragraph') or ''}")
        out.append("")
    return "\n".join(out) + "\n"


def template(answers: list[dict], who: str) -> str:
    out = [f"正式評估 v2 盲評紀錄（{who}）。標籤只用 supported / unsupported / unknown；inference 與 unknown 類不計分。",
           "每份答卷照 rubric-v1-final.md 第六節填寫；兩人獨立，先不看對方分數。", ""]
    for a in sorted(answers, key=lambda x: x["answer_id"]):
        out.append(f"{a['answer_id']} | 案例: {a['case_id']}")
        for c in ((a["draft"] or {}).get("claims") or []):
            out.append(f"  {c.get('claim_id')}({c.get('kind')}): 標註:   理由: ")
        out += ["  引用可解析數/總數: ", "  整體結果: 符合預期 / 不符合預期   理由: ", "  備註: ", ""]
    return "\n".join(out) + "\n"


def reveal() -> None:
    commit = json.loads((OUT / "key-commitment.json").read_text(encoding="utf-8"))
    for who in ("B", "D"):
        if not any(OUT.glob(f"scores-{who}*")):
            sys.exit(f"還沒有 {who} 的評分檔（evaluation/formal/scoring-v2/scores-{who}*），不公開對照表")
    data = KEY.read_bytes()
    if hashlib.sha256(data).hexdigest() != commit["key_sha256"]:
        sys.exit("對照表 sha256 與事先公開的不一致，停止")
    shutil.copyfile(KEY, OUT / "key.json")
    print("已公開對照表 evaluation/formal/scoring-v2/key.json（sha256 與 key-commitment.json 一致）")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--partial", action="store_true", help="試做：未跑完也匯出（正式交付請勿使用）")
    ap.add_argument("--reveal", action="store_true")
    args = ap.parse_args(argv)
    if args.reveal:
        reveal()
        return 0
    c = export(partial=args.partial)
    print(f"已匯出 {c['n_answers']} 份盲評答卷到 evaluation/formal/scoring-v2/（對照表 sha256 {c['key_sha256'][:12]}，存在 tmp/）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
