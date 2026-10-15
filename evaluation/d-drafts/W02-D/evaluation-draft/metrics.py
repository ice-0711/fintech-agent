"""W02-D 草稿：七項指標的計算函式。

規則（來自手冊 V1.2 第06章與 rubric-v1）：
1. 每個指標都回傳 numerator（分子）、denominator（分母）、na_count（無法評分而排除的數量）。
2. 分母為 0 時 value 是 None 並標 status="NA"，不能當成 0。
3. unknown 不能當成 supported，也不能直接當成 unsupported；它留在分母裡，並另外回報數量。
4. 失敗、逾時、429 的 job 都留在作業成功率的分母裡，不能刪。
5. 沒有帳單時，成本是 None，不是 0。
這是 D 的初稿，尚未經 B 與組長驗收。全部都是離線計算，不呼叫任何模型。
"""

from __future__ import annotations

from typing import Iterable

LABELS = ("supported", "unsupported", "unknown")


def _result(numerator: int, denominator: int, na_count: int = 0, **extra) -> dict:
    out = {
        "numerator": numerator,
        "denominator": denominator,
        "na_count": na_count,
        "value": None if denominator == 0 else numerator / denominator,
        "status": "NA" if denominator == 0 else "ok",
    }
    out.update(extra)
    return out


# 指標1：證據支持率
def evidence_support_rate(labels: Iterable[str | None]) -> dict:
    """labels：每個關鍵可驗證主張的標註。None 代表評分者還沒標，算 NA、不進分母。"""
    labels = list(labels)
    for lab in labels:
        if lab is not None and lab not in LABELS:
            raise ValueError(f"unknown label: {lab!r}")
    scored = [x for x in labels if x is not None]
    return _result(
        numerator=scored.count("supported"),
        denominator=len(scored),
        na_count=len(labels) - len(scored),
        unsupported_count=scored.count("unsupported"),
        unknown_count=scored.count("unknown"),
    )


# 指標2：引用可解析率（和「引用有沒有支持主張」分開算）
def citation_resolvable_rate(resolvable: Iterable[bool | None]) -> dict:
    items = list(resolvable)
    scored = [x for x in items if x is not None]
    return _result(sum(1 for x in scored if x), len(scored), len(items) - len(scored))


# 指標3：植入錯誤檢出率；沒有植入錯誤的案例另外報誤報率
def planted_error_detection(cases: list[dict]) -> dict:
    """cases：每筆 {case_id, planted: [error_id...], flagged: [error_id...]}。
    planted 為空的案例不進檢出率分母，改進誤報率。"""
    planted_total = detected = 0
    clean_cases = false_alarm_cases = 0
    for c in cases:
        planted, flagged = set(c.get("planted", [])), set(c.get("flagged", []))
        if planted:
            planted_total += len(planted)
            detected += len(planted & flagged)
        else:
            clean_cases += 1
            if flagged:
                false_alarm_cases += 1
    rate = _result(detected, planted_total)
    rate["false_alarm"] = _result(false_alarm_cases, clean_cases)
    return rate


# 指標4：修正率（只改寫措辭不算修正，所以輸入是「同一個 critical 錯誤是否還在」）
def fix_rate(needed_fix: Iterable[str], still_present_after_revision: Iterable[str]) -> dict:
    needed = set(needed_fix)
    still = set(still_present_after_revision) & needed
    return _result(len(needed - still), len(needed))


# 指標5：合理拒答率（資料不足的案例中，選擇 insufficient 並說明缺口）
def reasonable_refusal_rate(runs: list[dict]) -> dict:
    """runs：每筆 {case_id, data_sufficient: bool, decision, states_gap: bool}。
    資料完整卻拒答的情況另外列在 refused_when_sufficient，不混進分子。"""
    insufficient = [r for r in runs if not r["data_sufficient"]]
    ok = [r for r in insufficient if r["decision"] == "insufficient" and r.get("states_gap")]
    wrong = [r["case_id"] for r in runs if r["data_sufficient"] and r["decision"] == "insufficient"]
    return _result(len(ok), len(insufficient), refused_when_sufficient=wrong)


# 指標6：作業成功率（429、timeout、failed 都留在分母）
def job_success_rate(statuses: Iterable[str]) -> dict:
    statuses = list(statuses)
    counts: dict[str, int] = {}
    for s in statuses:
        counts[s] = counts.get(s, 0) + 1
    return _result(counts.get("succeeded", 0), len(statuses), status_counts=counts)


# 指標7：成本與效能（每列附樣本數 N；沒有資料就是 None，不是 0）
def cost_perf(values: Iterable[float | int | None]) -> dict:
    items = list(values)
    known = [v for v in items if v is not None]
    return {
        "n": len(known),
        "na_count": len(items) - len(known),
        "mean": (sum(known) / len(known)) if known else None,
        "max": max(known) if known else None,
        "status": "NA" if not known else "ok",
    }
