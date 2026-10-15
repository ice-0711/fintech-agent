"""W05-D 草稿：Reviewer runner（離線、可注入工具執行器）。

重要限制（誠實說明）：
- 這裡的「選工具」是規則式 planner，依草稿的問題決定要呼叫哪個允許工具，並記錄 tool_trace。
  它模擬 Reviewer 的行為，不是 Gemini 自己選。真模型自主選工具要等 provider 接上後另測。
- 工具只限 REVIEWER_TOOLS 四個；呼叫前一律先過 validate_tool_call(role="reviewer")。
- 預算：每 job 最多 10 次工具、模型發送剩餘次數由呼叫端傳入；沒有預算就 insufficient。
"""
from __future__ import annotations

import copy
from typing import Any, Callable

import reviewer_checks as rc
import reviewer_v12 as rv

MAX_TOOLS = 10
Executor = Callable[[str, dict], dict]


def repo_executor(repo_root: str, cutoff: str, fixture_snapshot: dict | None = None) -> Executor:
    """接 B 的 tools_impl（直接以關鍵字參數呼叫，繞過 F1 的 impl(args) 簽名問題），
    呼叫前仍先做 validate_tool_call。read_evidence 若給 fixture_snapshot 就從 dev fixture 讀（F3：repo 的 read_evidence 讀不到 dev 證據）。"""
    import sys
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    from agents import tools, tools_impl

    def run(name: str, args: dict) -> dict:
        try:
            tools.validate_tool_call("reviewer", name, args, cutoff)
        except tools.ToolInputError as exc:
            return {"status": "invalid_input", "tool": name, "reason": str(exc), "data": None}
        if name == "read_evidence" and fixture_snapshot is not None:
            for ev in fixture_snapshot.get("evidences", []):
                if ev["evidence_version_id"] == args["evidence_version_id"]:
                    return {"status": "ok", "tool": name, "data": {"paragraph": ev["paragraph"], "available_at": ev["available_at"]}}
            return {"status": "no_data", "tool": name, "reason": "fixture 無此片段", "data": None}
        try:
            return getattr(tools_impl, name)(**args)
        except Exception as exc:  # noqa: BLE001
            return {"status": "tool_error", "tool": name, "reason": f"{type(exc).__name__}: {exc}"[:200], "data": None}
    return run


def _plan(draft: dict, snapshot: dict, snapshot_id: str, ticker: str, cutoff: str) -> list[dict]:
    """依草稿內容決定要核對什麼。每項 = {tool,args,claim_id,purpose,kind}。"""
    plan: list[dict] = []
    evid = {e["evidence_version_id"] for e in snapshot.get("evidences", [])}
    seen_ref: set[str] = set()
    for c in draft.get("claims", []):
        cid = c["claim_id"]
        if c.get("kind") != "fact":
            continue
        for r in c.get("evidence_refs", []):
            if r in evid and r not in seen_ref:
                seen_ref.add(r)
                plan.append({"tool": "read_evidence", "args": {"evidence_version_id": r}, "claim_id": cid, "purpose": "核對引用片段存在且在 cutoff 前", "kind": "ref"})
        for f in c.get("facts", []):
            m, inp = f.get("metric"), f.get("inputs") or {}
            if m == "pe_ttm" and "price" in inp and "eps_ttm" in inp:
                plan.append({"tool": "calculate_metrics", "args": {"operation": "pe_ttm", "values": {"price": inp["price"], "eps_ttm": inp["eps_ttm"]}, "evidence_refs": [snapshot_id]},
                             "claim_id": cid, "purpose": "重算 P/E", "kind": "recalc", "claimed": f.get("value")})
            elif m in ("dcf_per_share", "intrinsic_value_per_share") and inp:
                plan.append({"tool": "calculate_metrics", "args": {"operation": "dcf_scenario", "values": {
                    "free_cash_flows": inp.get("free_cash_flows"), "wacc": inp.get("wacc"), "terminal_growth": inp.get("terminal_growth"),
                    "net_debt": inp.get("net_debt"), "shares_outstanding": inp.get("shares_outstanding")}, "evidence_refs": [snapshot_id]},
                             "claim_id": cid, "purpose": "重算 DCF 並檢查 WACC>g、缺值", "kind": "recalc", "claimed": f.get("value")})
            elif m in ("eps_ttm", "pe_ttm_input"):
                plan.append({"tool": "get_financial_snapshot", "args": {"ticker": ticker, "cutoff": cutoff}, "claim_id": cid,
                             "purpose": "核對 EPS TTM（四連續季）", "kind": "snapshot", "field": "eps_ttm", "claimed": f.get("value")})
            elif m == "fcf" and "operating_cash_flow" in inp and "capex" in inp:
                plan.append({"tool": None, "claim_id": cid, "purpose": "CapEx 符號：FCF = 營業現金流 − 正值 CapEx", "kind": "fcf_local", "inp": inp, "claimed": f.get("value")})
    return plan


def _issue(cid, reason, req, code):
    return rc._iss(cid, "critical", reason, req, code)


def run_review(draft: dict, snapshot: dict, cutoff_at: str, snapshot_id: str, executor: Executor,
               remaining_calls: int = 3, tool_budget: int = MAX_TOOLS, ticker: str | None = None, observations=None) -> dict:
    """回傳 {review, tool_trace, risk, budget}。review 一定符合 schema。"""
    ticker = ticker or snapshot.get("ticker", "")
    base = rc.check_draft(draft, snapshot, cutoff_at, snapshot_id, remaining_calls=remaining_calls, observations=observations)
    issues = [dict(i) for i in base["review"]["issues"]]
    extra: list[dict] = []
    trace: list[dict] = []
    unchecked: list[dict] = []
    used = 0
    plan = _plan(draft, snapshot, snapshot_id, ticker, cutoff_at)
    for step in plan:
        if step["kind"] == "fcf_local":                       # 純本地算術，不耗工具預算
            inp = step["inp"]
            exp = round(inp["operating_cash_flow"] - abs(inp["capex"]), 4)
            ok = step["claimed"] is not None and abs(step["claimed"] - exp) < 0.01
            trace.append({"tool": None, "claim_id": step["claim_id"], "purpose": step["purpose"], "expected": exp, "claimed": step["claimed"], "ok": ok})
            if not ok:
                extra.append(_issue(step["claim_id"], f"FCF 與重算不符：應為 營業現金流 − |CapEx| = {exp}，草稿為 {step['claimed']}（疑似 CapEx 符號處理錯誤）",
                                    f"calculate_metrics 或 get_financial_snapshot 核對 {step['claim_id']} 的營業現金流與 CapEx 符號，FCF 應為 {exp}", "fcf_sign"))
            continue
        if used >= tool_budget or remaining_calls <= 0:
            unchecked.append(step)
            continue
        used += 1
        res = executor(step["tool"], step["args"])
        rec = {"tool": step["tool"], "args": step["args"], "claim_id": step["claim_id"], "purpose": step["purpose"], "status": res.get("status"), "reason": res.get("reason")}
        data = res.get("data") or {}
        if step["kind"] == "recalc":
            if res.get("status") != "ok":
                extra.append(_issue(step["claim_id"], f"重算失敗（{res.get('reason')}）；草稿的數字不能視為已核實",
                                    f"calculate_metrics 以正確參數重算 {step['claim_id']}；缺值請退回 Researcher 補來源，不可補 0", "recalc_invalid"))
            else:
                got = data.get("result_value", data.get("value", data.get("intrinsic_value_per_share")))
                rec["recomputed"] = got
                if got is not None and step["claimed"] is not None and abs(got - step["claimed"]) > 0.01 * max(1, abs(got)):
                    extra.append(_issue(step["claim_id"], f"重算結果 {got} 與草稿 {step['claimed']} 不符",
                                        f"calculate_metrics 重算 {step['claim_id']} 得 {got}；請依此修正或附上草稿用的輸入來源", "recalc_mismatch"))
        elif step["kind"] == "snapshot":
            if res.get("status") != "ok":
                unchecked.append(step)
                rec["note"] = "快照無資料，無法核對"
            else:
                val = (data.get("metrics") or {}).get(step["field"])
                rec["snapshot_value"] = val
                if val is None:
                    unchecked.append(step)
                elif step["claimed"] is not None and abs(val - step["claimed"]) > 0.01 * max(1, abs(val)):
                    extra.append(_issue(step["claim_id"], f"EPS TTM 與財務快照不符：快照 {val}，草稿 {step['claimed']}",
                                        f"get_financial_snapshot({ticker}) 核對 {step['claim_id']} 的 eps_ttm 與四連續季", "snapshot_mismatch"))
        elif step["kind"] == "ref" and res.get("status") != "ok":
            extra.append(_issue(step["claim_id"], "引用的來源片段讀不到", f"read_evidence({step['args']['evidence_version_id']}) 確認片段存在", "ref_unreadable"))
        trace.append(rec)

    issues += [{k: v for k, v in i.items()} for i in extra]
    for u in unchecked:
        issues.append(rc._iss(u["claim_id"], "minor", f"未能核對：{u['purpose']}（預算用盡或工具無資料），原資料保留不補值",
                              f"{u['tool']} 取得 {u['claim_id']} 的對應資料後再核對；預算用盡時退回 Researcher", "unchecked", "insufficient"))
    n_crit = sum(1 for i in issues if i["severity"] == "critical")
    base_dec = base["review"]["decision"]
    if remaining_calls <= 0 and plan:
        decision = "insufficient"           # 沒有預算 → 不能下 pass
    elif base_dec == "insufficient":
        decision = "insufficient"
    elif n_crit:
        decision = "revise"
    elif unchecked:
        decision = "insufficient"
    else:
        decision = "pass"
    clean = [{k: i[k] for k in rv.ISSUE_KEYS} for i in issues]
    if decision == "insufficient" and not clean:
        first = (draft.get("claims") or [{"claim_id": "none"}])[0]["claim_id"]
        clean.append({"claim_id": first, "severity": "minor", "reason": "預算用盡，未能執行任何核對",
                      "required_evidence": "read_evidence(來源編號) 與 calculate_metrics 在補查預算恢復後核對；否則退回 Researcher"})
    review = {"decision": decision, "issues": clean, "checked_refs": base["review"]["checked_refs"],
              "checked_metric_ids": base["review"]["checked_metric_ids"],
              "decision_summary": f"{decision}：critical {sum(1 for i in clean if i['severity']=='critical')} 個，未核對 {len(unchecked)} 項。"[:120]}
    # 資料品質風險映射：資料不足絕不標低風險
    if decision == "insufficient":
        risk = "unverified"          # 資料不足 = 未核實，不標低風險也不假裝已知高風險
    elif n_crit:
        risk = "high"
    elif unchecked or any(t["code"] in ("missing_key_data", "no_fact_claims", "pe_na") for t in base["trace"]):
        risk = "unverified"
    else:
        risk = "low"
    return {"review": review, "tool_trace": trace, "risk": risk,
            "budget": {"tools_used": used, "tool_budget": tool_budget, "remaining_calls": remaining_calls, "unchecked": [u["purpose"] for u in unchecked]},
            "rule_trace": base["trace"]}
