"""W10/W11 正式評估 runner：保留 20 案 × 3 模式 = 60 run（組長 11/09）。

    .venv/bin/python scripts/formal_runs.py --make-plan            # 產生 evaluation/run-plan.json（固定種子，交 D 確認）
    .venv/bin/python scripts/formal_runs.py --status               # 只印進度：每個 run 的狀態，不印內容
    .venv/bin/python scripts/formal_runs.py --live [--max-runs 6]  # 依計畫跑下一批（每個配額日 ≤ J=6）

規則（evaluation/d-drafts/protocol-v1.md 第四、五節；handoff/decisions-2026-10.md）
- 只在第二段已鎖定、`build_freeze.py --verify --strict` 通過時才跑 live；否則拒絕。
- 只讀封存案例的執行欄位（case_id、ticker、cutoff_at、source_snapshot_id、variant），不讀、不印、不輸出
  expected_* 等答案欄位；終端只印 run_id、案例 ID、模式、狀態與停止代碼。
- 草稿與覆核存在 job 資料庫（tmp/formal_v2.sqlite3），評分用匿名化匯出另外處理；組長與 Claude 不打開。
- 成功與失敗（429、timeout、failed、insufficient）都寫一列進 evaluation/formal/runs-v2.jsonl，可續跑：
  已有紀錄的 run_id 不重跑（要重跑須發新實驗版本，舊紀錄保留）。
"""

from __future__ import annotations

import argparse
import json
import os
import random
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))

from agents.budget import ProjectQuota  # noqa: E402
from agents.research_graph import RESEARCHER_PROMPT_VERSION  # noqa: E402
from agents.review_contract import REVIEWER_PROMPT_VERSION  # noqa: E402
from agents.store import JobStore  # noqa: E402

SEALED = ROOT / "evaluation" / "test-cases-sealed.json"
PLAN = ROOT / "evaluation" / "run-plan.json"
OUT_DIR = ROOT / "evaluation" / "formal"
EXPERIMENT = "formal-v2"            # Agent v2（handoff/agent-version-changes.md）；重跑須改版本
RUNS = OUT_DIR / "runs-v2.jsonl"
DB = ROOT / "tmp" / "formal_v2.sqlite3"
MODES = ("single", "dual", "workflow")
SEED = 20261116                      # 計畫種子：W10 第一天
RUN_FIELDS = ("case_id", "ticker", "cutoff_at", "source_snapshot_id", "variant", "title")  # 只取執行欄位


def load_holdout() -> dict[str, dict]:
    """Execution fields only; answer fields never leave this function."""
    data = json.loads(SEALED.read_text(encoding="utf-8"))
    out = {}
    for c in data["cases"]:
        if c.get("split") not in (None, "test", "holdout"):
            sys.exit(f"{c['case_id']} 不是保留集（split={c.get('split')}），停止")
        out[c["case_id"]] = {k: c[k] for k in RUN_FIELDS if k in c}
    if len(out) != 20:
        sys.exit(f"保留集應為 20 案，實際 {len(out)}，停止")
    return out


def make_plan(case_ids: list[str], seed: int = SEED) -> dict:
    """Shuffle cases with a fixed seed; each case runs its three modes back to back (rotated order),
    so one quota day (J=6) covers two whole cases and every mode sees the same days and conditions."""
    rng = random.Random(seed)
    order = sorted(case_ids)
    rng.shuffle(order)
    runs = []
    for i, cid in enumerate(order):
        modes = MODES[i % 3:] + MODES[:i % 3]
        for m in modes:
            runs.append({"seq": len(runs) + 1, "run_id": f"{EXPERIMENT}-{cid}-{m}", "case_id": cid, "mode": m,
                         "quota_day_index": len(runs) // 6 + 1})
    return {"experiment": EXPERIMENT, "seed": seed, "n_cases": len(order), "modes": list(MODES), "n_runs": len(runs),
            "j_per_quota_day": 6, "quota_days": (len(runs) + 5) // 6,
            "design": "固定種子打亂案例順序；同一案例三模式連續執行、起始模式輪替；每配額日 6 run（2 案 × 3 模式）",
            "status": "組長端草案（11/09），待 D 確認或替換（W09-D run-plan）", "runs": runs}


def done_runs() -> dict[str, dict]:
    if not RUNS.exists():
        return {}
    rows = [json.loads(line) for line in RUNS.read_text(encoding="utf-8").splitlines() if line.strip()]
    return {r["run_id"]: r for r in rows}


def lock_ok() -> bool:
    fm = json.loads((ROOT / "data" / "v12-frozen-manifest.json").read_text(encoding="utf-8"))
    if not fm.get("freeze_stages", {}).get("stage2", {}).get("locked"):
        print("第二段尚未鎖定（build_freeze.py --lock-agent），不可執行正式評估")
        return False
    r = subprocess.run([sys.executable, "scripts/build_freeze.py", "--verify", "--strict"], cwd=ROOT,
                       capture_output=True, text=True)
    if r.returncode != 0:
        print("build_freeze.py --verify --strict 未通過，不可執行正式評估：")
        print(r.stdout[-1500:])
        return False
    return True


def row_for(plan_run: dict, result: dict, model_id: str, commit: str, started: str) -> dict:
    """Metadata only: no draft, review, claims or answer fields."""
    return {"run_id": plan_run["run_id"], "experiment": EXPERIMENT, "case_id": plan_run["case_id"],
            "mode": plan_run["mode"], "seq": plan_run["seq"], "job_id": result.get("job_id"),
            "status": result.get("status"), "stop_reason": result.get("stop_reason"),
            "budget": result.get("budget"), "n_steps": len(result.get("steps") or []),
            "model_id": model_id, "prompt_versions": {"researcher": RESEARCHER_PROMPT_VERSION,
                                                       "reviewer": REVIEWER_PROMPT_VERSION},
            "commit": commit, "started_at": started,
            "finished_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "run_mode": "live"}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--make-plan", action="store_true")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--max-runs", type=int, default=6)
    args = ap.parse_args(argv)

    if args.make_plan:
        if PLAN.exists():
            sys.exit(f"{PLAN.relative_to(ROOT)} 已存在，不覆寫")
        plan = make_plan(list(load_holdout()))
        PLAN.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {PLAN.relative_to(ROOT)}：{plan['n_runs']} run、{plan['quota_days']} 個配額日")
        return 0

    if not PLAN.exists():
        sys.exit("沒有 evaluation/run-plan.json，先 --make-plan 並請 D 確認")
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    done = done_runs()
    if args.status:
        counts: dict[str, int] = {}
        for r in plan["runs"]:
            st = done.get(r["run_id"], {}).get("status") or "pending"
            counts[st] = counts.get(st, 0) + 1
        print(f"{plan['experiment']}：{len(done)}/{plan['n_runs']} 已執行；" + "、".join(f"{k} {v}" for k, v in sorted(counts.items())))
        return 0

    if not args.live:
        ap.print_help()
        return 0
    if not lock_ok():
        return 1
    from dev_traces import run  # same job path as the development runs
    from agents.provider import make_client
    baseline = json.loads((ROOT / "handoff" / "quota-baseline.json").read_text(encoding="utf-8"))
    quota = ProjectQuota.from_baseline(baseline)
    model_id = os.getenv("GEMINI_MODEL")
    if model_id != quota.model_id:
        sys.exit(f"GEMINI_MODEL={model_id} 與 quota-baseline.json 的 {quota.model_id} 不一致，停止")
    cases = load_holdout()
    todo = [r for r in plan["runs"] if r["run_id"] not in done][: args.max_runs]
    if not todo:
        print("全部 run 已執行")
        return 0
    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip()
    DB.parent.mkdir(exist_ok=True)
    OUT_DIR.mkdir(exist_ok=True)
    store, client = JobStore(DB), make_client()
    for i, r in enumerate(todo):
        if i:
            time.sleep(60)  # stay under 80 % of RPM between jobs
        started = datetime.now(timezone.utc).isoformat(timespec="seconds")
        try:
            result = run(store, cases[r["case_id"]], client, model_id, quota, EXPERIMENT, r["mode"])
        except Exception as exc:  # recorded, never retried silently
            result = {"status": "runner_error", "stop_reason": type(exc).__name__}
        if result.get("status") == "paused_quota":  # not run yet: no row, the same run_id goes first next quota day
            print(r["run_id"], "paused_quota", result.get("stop_reason") or "", "→ 配額日已用完，下一個配額日續跑")
            break
        row = row_for(r, result, model_id, commit, started)
        with RUNS.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(r["run_id"], row["status"], row["stop_reason"] or "", flush=True)
    store.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
