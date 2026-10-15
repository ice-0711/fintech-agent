"""W02-D 草稿：mock runner 與人工評分輸入格式。

這個檔案完全離線，不呼叫任何模型，所以不會新增 LLM 樣本。
每筆 run 都標 run_kind="mock"，不能和 live 實測混在一起。
模式沿用 agents/state.py 的寫法：workflow（基線）、single、dual。
"""

from __future__ import annotations

import csv
import io
import json
import random

MODES = ("workflow", "single", "dual")
RUN_KIND = "mock"


def make_runs(cases: list[dict], modes=MODES) -> list[dict]:
    """每個案例 x 每個模式一筆 run。內容是固定的模擬值，不代表任何模型結果。"""
    runs = []
    for c in cases:
        for m in modes:
            if m not in MODES:
                raise ValueError(f"unknown mode: {m!r}")
            runs.append(
                {
                    "run_id": f"{c['case_id']}-{m}",
                    "case_id": c["case_id"],
                    "mode": m,
                    "run_kind": RUN_KIND,
                    "llm_calls": 0,
                    "status": "succeeded",
                    "decision": "insufficient" if c.get("allow_insufficient") else "pass",
                    "claims": [],
                    "note": "MOCK：未呼叫模型",
                }
            )
    return runs


def anonymize(runs: list[dict], seed: int = 0) -> tuple[list[dict], dict[str, str]]:
    """評分者看到的版本：拿掉 mode 與原始 run_id，順序打亂。
    回傳 (給評分者的紀錄, 對照表 blind_id -> run_id)。對照表由組長保管，評分前不給 B 與 D。"""
    rng = random.Random(seed)
    order = list(range(len(runs)))
    rng.shuffle(order)
    blind, key = [], {}
    for n, i in enumerate(order, start=1):
        r = runs[i]
        bid = f"R{n:03d}"
        key[bid] = r["run_id"]
        blind.append({"blind_id": bid, "case_id": r["case_id"], "decision": r["decision"], "claims": r["claims"]})
    return blind, key


# 人工評分輸入格式：一列 = 一位評分者對一個主張的標註。
SCORE_COLUMNS = ["blind_id", "scorer", "claim_id", "label", "severity", "reason", "required_evidence"]
VALID_LABELS = ("supported", "unsupported", "unknown")
VALID_SEVERITY = ("", "critical", "minor")


def blank_score_sheet(blind_runs: list[dict], scorer: str) -> str:
    """產生空白評分表（CSV 文字）。label 留空代表還沒標，計算時算 NA，不是 0。"""
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(SCORE_COLUMNS)
    for r in blind_runs:
        for c in r["claims"]:
            w.writerow([r["blind_id"], scorer, c["claim_id"], "", "", "", ""])
    return buf.getvalue()


def validate_score_rows(rows: list[dict]) -> list[str]:
    """回傳錯誤訊息清單，空清單代表格式沒問題。critical 一定要有 reason 與 required_evidence。"""
    errors = []
    for i, r in enumerate(rows, start=1):
        missing = [c for c in SCORE_COLUMNS if c not in r]
        if missing:
            errors.append(f"row {i}: 缺欄位 {missing}")
            continue
        if r["label"] not in ("",) + VALID_LABELS:
            errors.append(f"row {i}: label 不合法 {r['label']!r}")
        if r["severity"] not in VALID_SEVERITY:
            errors.append(f"row {i}: severity 不合法 {r['severity']!r}")
        if r["severity"] == "critical" and not (r["reason"] and r["required_evidence"] and r["claim_id"]):
            errors.append(f"row {i}: critical 必須有 claim_id、reason、required_evidence")
    return errors


def dump_runs(runs: list[dict]) -> str:
    return json.dumps(runs, ensure_ascii=False, indent=2)
