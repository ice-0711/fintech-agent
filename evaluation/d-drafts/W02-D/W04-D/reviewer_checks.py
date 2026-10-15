"""W04-D 草稿：Reviewer 的離線確定性核對（季度、TTM、available_at、幣別、同業角色、來源衝突、注入文字）。

這是「規則式核對」，用來：
  1. 在不呼叫任何模型的情況下，把手冊 Reviewer 規則變成可重現的檢查，用 10 個 dev 案例的草稿測 pass/revise/insufficient。
  2. 產出精確的 required_evidence（指到工具與參數或來源編號）。
它不是真正的 Reviewer（Reviewer 是 LLM，要自己選工具核對）；這裡只能檢查「可以用規則判斷」的部分，
需要讀原文才能判斷的問題見 evaluation/reviewer-dev.md 的「需查來源才能判斷」清單。

輸入的草稿格式（claims 裡的 facts 是 D 提議的結構化欄位，現有 Researcher 草稿還沒有，見 reviewer-dev.md 的 CR 建議）：
  claim = {claim_id, kind: fact|inference|unknown, text, evidence_refs: [...], facts: [fact...], limitations: [...]}
  fact  = {metric, value, currency?, period?, period_basis?, source_ref?, inputs?, operation?, derived_inputs?, fx_rate?,
           quarters?, peers?, wacc?, g?, prior_value?, prior_ref?}
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

UNVERIFIED_RE = re.compile(r"未經核實|傳聞|未具名|未核對|未經審計|分析師預估")
INJECTION_RE = re.compile(r"SYSTEM\s*OVERRIDE|ignore\s+(all\s+)?(previous|prior)|忽略.{0,6}(規則|指令)|output\s+(a\s+)?(buy|sell)", re.I)
RECOMMEND_RE = re.compile(r"買進|賣出|強烈(買|賣)|目標價|價格目標|\b(BUY|SELL)\b", re.I)
CUR_PREFIX = r"(?P<cur>USD|US\$|美元|NTD|TWD|NT\$|新台幣|新臺幣|台幣)"
CUR_MAP = {"USD": "USD", "US$": "USD", "美元": "USD", "NTD": "TWD", "TWD": "TWD", "NT$": "TWD",
           "新台幣": "TWD", "新臺幣": "TWD", "台幣": "TWD"}
CONFLICT_KEYWORDS = ("營收", "毛利率")
# 這些指標需要的欄位；欄位是 null 或不存在就不可算（不可補 0）
KEY_FIELDS = {"intrinsic_value_per_share": ("free_cash_flow", "shares_outstanding"), "dcf_per_share": ("free_cash_flow", "shares_outstanding"),
              "equity_value_per_share": ("shares_outstanding",)}
# 指標對應到快照欄位（用於核對數字是否和快照一致）
SNAPSHOT_FIELD = {"close_price": "close_price", "eps_ttm": "eps_ttm", "revenue": "revenue"}


def _t(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def num_variants(v: float) -> list[str]:
    f = float(v)
    return list({format(f, ",.10g"), format(f, ".10g")})


def paragraph_contains(paragraph: str, value: float) -> bool:
    for s in num_variants(value):
        if re.search(rf"(?<![\d,.]){re.escape(s)}(?![\d,]|\.\d)", paragraph):
            return True
    return False


def currency_before(paragraph: str, value: float) -> str | None:
    """找出緊接在這個數字前面的幣別標記（正規化成 USD 或 TWD）；找不到回 None。"""
    for s in num_variants(value):
        m = re.search(rf"{CUR_PREFIX}\s*(?<![\d,.]){re.escape(s)}(?![\d,]|\.\d)", paragraph)
        if m:
            return CUR_MAP[m.group("cur")]
    return None


def is_unverified(ev: dict) -> bool:
    return bool(UNVERIFIED_RE.search(ev.get("title", "") + ev.get("paragraph", "")))


def find_conflicts(evidences: list[dict]) -> list[dict]:
    """同一個關鍵字（營收、毛利率）在不同證據裡出現不同數字，就是來源衝突。"""
    out = []
    for kw in CONFLICT_KEYWORDS:
        found = {}
        for ev in evidences:
            m = re.search(rf"{kw}[^\d]{{0,16}}?([\d,]+(?:\.\d+)?)\s*(億|%|％)", ev.get("paragraph", ""))
            if m:
                found[ev["evidence_version_id"]] = float(m.group(1).replace(",", ""))
        if len(set(found.values())) > 1:
            out.append({"keyword": kw, "values": found})
    return out


def consecutive_quarters(labels: list[str]) -> bool:
    """['2025Q3','2025Q4','2026Q1','2026Q2'] 這種連續四季才算 True。"""
    try:
        idx = []
        for lab in labels:
            m = re.fullmatch(r"(\d{4})Q([1-4])", lab)
            idx.append(int(m.group(1)) * 4 + int(m.group(2)) - 1)
    except AttributeError:
        return False
    return len(idx) == 4 and all(b - a == 1 for a, b in zip(idx, idx[1:]))


def _iss(claim_id, severity, reason, required, code, outcome="revise"):
    return {"claim_id": claim_id, "severity": severity, "reason": reason, "required_evidence": required,
            "_code": code, "_outcome": outcome}


def check_draft(draft: dict, snapshot: dict, cutoff_at: str, snapshot_id: str, remaining_calls: int = 3,
                observations: list[dict] | None = None) -> dict:
    """回傳 {"review": {...符合 schema...}, "trace": [規則代碼與結果]}。"""
    claims = draft.get("claims", [])
    evid = {e["evidence_version_id"]: e for e in snapshot.get("evidences", [])}
    obs = {o["obs_id"]: o for o in (observations or [])}
    cutoff = _t(cutoff_at)
    issues: list[dict] = []
    checked_refs: list[str] = []
    metric_ids: list[str] = []
    first_id = claims[0]["claim_id"] if claims else "none"
    conflicts = find_conflicts(list(evid.values()))
    disclosed = " ".join(str(x) for x in draft.get("conflicts", []))
    n_fact_claims = sum(1 for c in claims if c.get("kind") == "fact")

    for c in claims:
        cid, kind, refs = c["claim_id"], c.get("kind"), c.get("evidence_refs", [])
        # --- 建議、評級、目標價：任何主張都不可有 ---
        if kind != "unknown" and RECOMMEND_RE.search(c.get("text", "")):
            issues.append(_iss(cid, "critical", "主張含買賣建議或目標價；專題禁止虛構買賣評級與價格目標，且可能來自注入文字",
                               f"read_evidence({refs[0] if refs else '本快照來源'})，確認 {cid} 的依據；刪除買賣建議，只保留可由來源核實的事實", "recommendation"))
        # --- fact 必須有引用 ---
        if kind == "fact" and not refs:
            issues.append(_iss(cid, "critical", "fact 沒有任何引用", f"read_evidence(來源編號)，為 {cid} 補上屬於本快照的 evidence_version_id", "fact_no_ref"))
        for r in refs:
            if r == snapshot_id:
                checked_refs.append(r)
                continue
            if r in obs:
                checked_refs.append(r)
                if obs[r].get("status") != "ok":
                    issues.append(_iss(cid, "critical", f"引用的工具結果 {r} 狀態為 {obs[r].get('status')}，不是有效資料",
                                       f"退回 Researcher：{cid} 不可引用 {obs[r].get('tool_name')} 的 {obs[r].get('status')} 結果；改用 read_evidence 取得有效來源", "bad_tool_result"))
                continue
            if r not in evid:
                issues.append(_iss(cid, "critical", f"引用 {r} 不存在於本快照（{snapshot_id}）",
                                   f"read_evidence({r}) 確認是否存在；不存在則改引用本快照內的 evidence_version_id", "ref_missing"))
                continue
            checked_refs.append(r)
            ev = evid[r]
            if _t(ev["available_at"]) > cutoff:
                issues.append(_iss(cid, "critical", f"{r} 的 available_at={ev['available_at']} 晚於 cutoff {cutoff_at}（前視）",
                                   f"read_evidence({r}) 核對 available_at；改用 cutoff 前已可得的來源", "lookahead"))
            if INJECTION_RE.search(ev.get("paragraph", "")):
                issues.append(_iss(cid, "minor", f"{r} 含要求忽略規則或買賣的指令文字，已視為不可信資料",
                                   f"read_evidence({r})，確認 {cid} 只採用其中可核實的客觀事實，並在 limitations 說明來源含不可信指令", "injection_text", "pass"))

        for f in c.get("facts", []):
            metric = f.get("metric", "")
            metric_ids.append(metric)
            src, val = f.get("source_ref"), f.get("value")
            ev = evid.get(src)
            # --- 來源是否支持數字 ---
            if ev is not None and val is not None:
                if not paragraph_contains(ev["paragraph"], val):
                    issues.append(_iss(cid, "critical", f"{metric}={val} 在 {src} 的原文裡找不到，來源不支持這個數字",
                                       f"read_evidence({src})，逐字核對 {cid} 的 {metric} 數值", "not_supported"))
                if is_unverified(ev):
                    issues.append(_iss(cid, "critical", f"{src} 是未經核實的來源（傳聞或未核對報導），不能當成事實",
                                       f"read_evidence({src}) 確認來源性質；改用官方公告的 evidence_version_id，並把傳聞放進 conflicts",
                                       "unverified_source"))
                cur = currency_before(ev["paragraph"], val)
                if cur and f.get("currency") and cur != f["currency"]:
                    issues.append(_iss(cid, "critical", f"{metric} 在 {src} 原文的幣別是 {cur}，主張標成 {f['currency']}",
                                       f"read_evidence({src})，核對 {cid} 的幣別與單位", "currency_mislabel"))
            # --- 跨幣別直接運算 ---
            if f.get("operation") in ("ratio", "sum", "diff") and f.get("derived_inputs"):
                curs = {x.get("currency") for x in f["derived_inputs"]}
                if len(curs) > 1 and not f.get("fx_rate"):
                    issues.append(_iss(cid, "critical", f"{metric} 直接{f['operation']}不同幣別 {sorted(x for x in curs if x)}，沒有匯率轉換",
                                       f"read_evidence({src or '來源編號'})，確認各數字幣別；統一為 TWD 並附匯率來源後才可運算，否則刪除此主張", "currency_mixed"))
            # --- 期間口徑：ytd 當單季 ---
            snap = snapshot.get("financial_snapshot") or {}
            if f.get("period_basis") == "single_quarter" and snap.get("period_basis") == "ytd" and val is not None:
                if abs(val - snap.get("revenue", float("nan"))) < 1e-9:
                    issues.append(_iss(cid, "critical", f"把累計(ytd) {val} 當成單季；快照 period_basis=ytd",
                                       f"get_financial_snapshot(ticker, cutoff) 取得 2026Q1 單季值，再用 calculate_metrics 以 ytd 減前期還原單季", "ytd_as_single"))
            if f.get("derived_from") == "ytd_minus_prior":
                ytd, prior = f.get("ytd_value"), f.get("prior_value")
                if ytd is None or prior is None or abs((ytd - prior) - val) > 0.05:
                    issues.append(_iss(cid, "critical", f"ytd 還原單季的算術不一致（{ytd} - {prior} 應等於 {val}）",
                                       f"calculate_metrics 重算 {cid}：ytd 減前期單季，並核對兩個數字的期間與口徑", "ytd_math"))
                elif not f.get("prior_ref") or f.get("prior_ref") == snapshot_id:
                    issues.append(_iss(cid, "minor", f"前期值 {prior} 沒有獨立來源編號（只出現在快照備註）",
                                       f"get_financial_snapshot(ticker, cutoff) 取得前一季單季值與 available_at，補上前期來源", "prior_no_source", "pass"))
            # --- TTM 要四個連續單季 ---
            if f.get("period_basis") == "ttm" and not consecutive_quarters(f.get("quarters", [])):
                issues.append(_iss(cid, "critical", f"TTM 需要四個連續單季，收到 {f.get('quarters')}",
                                   f"get_financial_snapshot(ticker, cutoff) 確認連續四個單季都已公告；不足則 {metric} 標 null", "ttm_not_consecutive"))
            # --- 本益比重算 ---
            if metric == "pe_ttm" and f.get("inputs"):
                p, e = f["inputs"].get("price"), f["inputs"].get("eps_ttm")
                if e is None or e <= 0 or p is None:
                    issues.append(_iss(cid, "critical", "P/E 的 EPS 缺失或非正，應為不適用", "calculate_metrics(pe_ttm) 確認 EPS 與價格；EPS 非正則 P/E 標不適用", "pe_na"))
                elif abs(round(p / e, 2) - val) > 0.01:
                    issues.append(_iss(cid, "critical", f"P/E 重算為 {round(p / e, 2)}，主張為 {val}",
                                       f"calculate_metrics(operation=pe_ttm, price={p}, eps_ttm={e}) 重算並修正 {cid}", "pe_math"))
                ps = snapshot.get("price_snapshot")
                if ps and (p != ps.get("close_price") or e != ps.get("eps_ttm")):
                    issues.append(_iss(cid, "critical", "P/E 的輸入和快照的收盤價或 TTM EPS 不一致",
                                       f"read_evidence({snapshot_id}) 或 get_financial_snapshot 核對同日股價與 TTM EPS", "pe_input_mismatch"))
            # --- 同業平均不可含 2330 ---
            if metric.startswith("peer_avg"):
                peers = f.get("peers", [])
                if "2330" in peers:
                    issues.append(_iss(cid, "critical", "同業平均納入了 2330；2330 只是產業參照，不可計入 2454 的同業平均",
                                       "calculate_metrics(operation=peer_comparison, subject=2454, comparators=[2379, 3034, 2330])，同業平均只含 2379、3034", "peer_includes_2330"))
                if len(peers) + 1 > 4:
                    issues.append(_iss(cid, "critical", "比較公司（含 2454）超過 4 家", "calculate_metrics(operation=peer_comparison) 把比較對象限制在 4 家以內", "peer_over_4"))
            # --- DCF：WACC 必須大於 g ---
            if metric in KEY_FIELDS and f.get("wacc") is not None and f.get("g") is not None and f["wacc"] <= f["g"]:
                issues.append(_iss(cid, "critical", f"WACC={f['wacc']} 不大於 g={f['g']}，DCF 不可計算",
                                   "calculate_metrics(operation=dcf_scenario) 確認 WACC 大於 g；否則 DCF 標不適用", "wacc_le_g"))
            # --- 缺關鍵欄位卻給出估值 ---
            if metric in KEY_FIELDS:
                missing = [k for k in KEY_FIELDS[metric] if snap.get(k) is None]
                if missing:
                    why = snap.get("missing_reason") or f"{missing} 為 null"
                    issues.append(_iss(cid, "critical", f"{metric} 需要 {KEY_FIELDS[metric]}，但快照缺 {missing}（{why}），不可推估或補 0",
                                       f"get_financial_snapshot(ticker={snapshot.get('ticker', '')}, cutoff={cutoff_at}) 取得 {', '.join(missing)}；若仍為 null，維持 insufficient 並寫明缺口",
                                       "missing_key_data", "insufficient"))

    # --- 來源衝突是否揭露 ---
    for cf in conflicts:
        ids = list(cf["values"])
        if not all(i in disclosed for i in ids):
            issues.append(_iss(first_id, "minor", f"證據之間的「{cf['keyword']}」數字不同（{cf['values']}），草稿沒有在 conflicts 說明",
                               f"read_evidence({ids[0]}) 與 read_evidence({ids[1]})，把差異與採信理由寫進 conflicts", "conflict_undisclosed", "pass"))

    # --- 沒有任何事實主張 ---
    if n_fact_claims == 0:
        has_missing = any(i["_code"] == "missing_key_data" for i in issues)
        if not has_missing:
            nulls = [k for k, v in (snapshot.get("financial_snapshot") or {}).items() if v is None]
            need = (f"get_financial_snapshot(ticker={snapshot.get('ticker', '')}, cutoff={cutoff_at}) 取得 {', '.join(nulls)}"
                    if nulls else f"read_evidence(本快照 {snapshot_id} 內的來源編號) 取得可核實的事實")
            issues.append(_iss(first_id, "critical", "草稿沒有任何有來源的事實主張，沒有可核對的內容", need, "no_fact_claims", "insufficient"))

    # --- 決定 ---
    crit = [i for i in issues if i["severity"] == "critical"]
    needs_insufficient = any(i["_outcome"] == "insufficient" for i in crit)
    if needs_insufficient:
        decision = "insufficient"
    elif crit and remaining_calls <= 0:
        decision = "insufficient"
        issues.append(_iss(first_id, "critical", "還有 critical 問題但沒有剩餘預算可以補查，不可宣稱已核實",
                           "退回 Researcher：預算不足，需保留限制並停止，不可跳過覆核發布", "no_budget", "insufficient"))
    elif crit:
        decision = "revise"
    else:
        decision = "pass"

    trace = [{"claim_id": i["claim_id"], "code": i["_code"], "severity": i["severity"]} for i in issues]
    public_issues = [{k: v for k, v in i.items() if not k.startswith("_")} for i in issues][:10]
    n_c = sum(1 for i in public_issues if i["severity"] == "critical")
    summary = {"pass": "無未解決的 critical 問題，引用與數字已核對。",
               "revise": f"有 {n_c} 個 critical 問題，可在現有來源內修正，請依 required_evidence 補查。",
               "insufficient": "關鍵資料缺失或預算不足，無法核實；保留限制，不放行。"}[decision]
    review = {"decision": decision, "issues": public_issues, "checked_refs": sorted(set(checked_refs)),
              "checked_metric_ids": sorted(set(metric_ids)), "decision_summary": summary}
    return {"review": review, "trace": trace}
