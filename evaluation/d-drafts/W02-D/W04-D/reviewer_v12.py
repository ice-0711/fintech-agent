"""W04-D 草稿：Reviewer 的 runtime prompt、版本、輸出驗證。

不呼叫任何模型，不連網，不依賴 jsonschema（用純 Python 檢查，並在測試裡和 jsonschema 對照）。
這是 D 的初稿，尚未經 B 與組長驗收，也尚未放進 repo 的 agents/。

用途：
  1. REVIEWER_SYSTEM_PROMPT / prompt_hash()：可版本化的 runtime prompt，對應 provider 每次發送記錄的 prompt_version、prompt_hash。
  2. estimate_input_tokens()：用 handoff/model-config.md 的保守估法（非 ASCII 1 字 1 token、ASCII 2 字元 1 token）。
  3. validate_review()：檢查 Reviewer 輸出（schema 加語意規則，包含「角色沒有發布權」與「只用允許工具」）。
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from typing import Any

HERE = os.path.dirname(os.path.abspath(__file__))
REVIEWER_PROMPT_VERSION = "reviewer-v1.2.0-draft"
PROMPT_PATH = os.path.join(HERE, "reviewer-v12-prompt.txt")
SCHEMA_PATH = os.path.join(HERE, "reviewer_output.schema.json")

# 與 agents/tools.py 的 ROLE_TOOLS["reviewer"] 相同（測試會和 repo 對照）
REVIEWER_TOOLS = ("read_evidence", "get_financial_snapshot", "get_macro_snapshot", "calculate_metrics")
DECISIONS = ("pass", "revise", "insufficient")
SEVERITIES = ("critical", "minor")
OUTPUT_KEYS = ("decision", "issues", "checked_refs", "checked_metric_ids", "decision_summary")
ISSUE_KEYS = ("claim_id", "severity", "reason", "required_evidence")

# 不具體的 required_evidence 寫法（手冊：不能只寫「請改善」）
GENERIC_PHRASES = ("請改善", "補充更多", "補更多", "更多資料", "更多新聞", "請再確認", "請修正", "再查證")
# 具體 = 提到允許的工具名稱，或來源/快照編號
SPECIFIC_RE = re.compile(r"(read_evidence|get_financial_snapshot|get_macro_snapshot|calculate_metrics|退回 Researcher|\bev-[\w.-]+|\bsnap-[\w.-]+)")


def load_prompt() -> str:
    with open(PROMPT_PATH, encoding="utf-8") as f:
        return f.read()


def prompt_hash(text: str | None = None) -> str:
    """sha256，和 provider 記錄 prompt_hash 的做法一致（對 prompt 文字取雜湊）。"""
    return hashlib.sha256((text if text is not None else load_prompt()).encode("utf-8")).hexdigest()


def estimate_tokens(text: str) -> int:
    """保守估法：非 ASCII 字元 1 字 1 token，ASCII 2 字元 1 token（無條件進位）。"""
    non_ascii = sum(1 for ch in text if ord(ch) > 127)
    ascii_chars = len(text) - non_ascii
    return non_ascii + (ascii_chars + 1) // 2


def estimate_input_tokens(user_payload: Any = "", tool_declarations: list[dict] | None = None) -> dict:
    prompt = estimate_tokens(load_prompt())
    tools = estimate_tokens(json.dumps(tool_declarations, ensure_ascii=False)) if tool_declarations else 0
    user = estimate_tokens(user_payload if isinstance(user_payload, str) else json.dumps(user_payload, ensure_ascii=False))
    return {"prompt": prompt, "tools": tools, "user": user, "total": prompt + tools + user, "input_cap": 3000}


def _is_str(x: Any) -> bool:
    return isinstance(x, str)


def validate_review(review: Any, draft_claim_ids: list[str] | None = None) -> list[str]:
    """回傳錯誤清單；空清單代表合格。draft_claim_ids 給了才檢查 claim_id 是否真的存在於草稿。"""
    errors: list[str] = []
    if not isinstance(review, dict):
        return ["輸出必須是 JSON 物件"]

    # ---- schema：欄位齊全、不可多欄位（沒有 publish/approved 之類欄位）----
    extra = sorted(set(review) - set(OUTPUT_KEYS))
    if extra:
        errors.append(f"不允許的欄位 {extra}：Reviewer 沒有發布、核准或改資料的權限")
    missing = [k for k in OUTPUT_KEYS if k not in review]
    if missing:
        errors.append(f"缺少欄位 {missing}")
        return errors
    decision = review["decision"]
    if decision not in DECISIONS:
        errors.append(f"decision 只能是 {DECISIONS}")
    issues = review["issues"]
    if not isinstance(issues, list):
        return errors + ["issues 必須是陣列"]
    if len(issues) > 10:
        errors.append("issues 最多 10 筆")
    for k in ("checked_refs", "checked_metric_ids"):
        if not isinstance(review[k], list) or not all(_is_str(x) for x in review[k]):
            errors.append(f"{k} 必須是字串陣列")
    summ = review["decision_summary"]
    if not _is_str(summ) or len(summ) > 120:
        errors.append("decision_summary 必須是 120 字以內的字串")

    # ---- 每個 issue ----
    ids = set(draft_claim_ids) if draft_claim_ids is not None else None
    n_critical = 0
    for i, it in enumerate(issues, start=1):
        tag = f"issues[{i}]"
        if not isinstance(it, dict):
            errors.append(f"{tag} 必須是物件")
            continue
        extra_i = sorted(set(it) - set(ISSUE_KEYS))
        if extra_i:
            errors.append(f"{tag} 不允許的欄位 {extra_i}")
        miss_i = [k for k in ISSUE_KEYS if k not in it]
        if miss_i:
            errors.append(f"{tag} 缺少欄位 {miss_i}")
            continue
        if it["severity"] not in SEVERITIES:
            errors.append(f"{tag}.severity 只能是 {SEVERITIES}")
        if it["severity"] == "critical":
            n_critical += 1
        if not _is_str(it["claim_id"]) or not it["claim_id"].strip():
            errors.append(f"{tag}.claim_id 不可空白（critical 必須指到 claim_id）")
        elif ids is not None and it["claim_id"] not in ids:
            errors.append(f"{tag}.claim_id={it['claim_id']!r} 不在草稿的 claim 中")
        if not _is_str(it["reason"]) or not it["reason"].strip():
            errors.append(f"{tag}.reason 不可空白")
        re_ = it["required_evidence"]
        if not _is_str(re_) or len(re_.strip()) < 12:
            errors.append(f"{tag}.required_evidence 太短，必須具體")
        else:
            if any(p in re_ for p in GENERIC_PHRASES):
                errors.append(f"{tag}.required_evidence 太籠統：{re_!r}")
            if not SPECIFIC_RE.search(re_):
                errors.append(f"{tag}.required_evidence 沒有指到允許的工具或來源編號：{re_!r}")

    # ---- decision 與 issues 的一致性 ----
    if decision == "pass" and n_critical:
        errors.append("decision=pass 但還有 critical issue")
    if decision == "revise" and not n_critical:
        errors.append("decision=revise 必須至少有一個 critical issue")
    if decision == "insufficient" and not issues:
        errors.append("decision=insufficient 必須用 issue 說明缺什麼")
    return errors


def validate_tool_use(tool_names: list[str]) -> list[str]:
    """Reviewer 呼叫的工具必須在允許清單內；需要別的工具要退回 Researcher。"""
    return [f"Reviewer 不可使用 {n}；需要時以 required_evidence 退回 Researcher" for n in tool_names if n not in REVIEWER_TOOLS]
