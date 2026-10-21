"""Turn a job's drafts and review rounds into what the review panel shows (W05-A).

Input shape follows the lead's research graph (agents/research_graph.py):
  job["checkpoint"]["reviews"] = [{"round", "model", "rules", "final"}, ...]
  job["draft"]                  = latest draft
  job["checkpoint"]["drafts"]   = every draft version, oldest first (CR-A04: the
                                  graph keeps only the latest draft today)

Nothing here calls a model. Only whitelisted fields leave the server.
"""

from __future__ import annotations

from typing import Any

CLAIM_FIELDS = ("claim_id", "kind", "text", "evidence_refs", "limitations")
ISSUE_FIELDS = ("claim_id", "severity", "reason", "required_evidence")


def _claims(draft: dict[str, Any] | None) -> list[dict[str, Any]]:
    out = []
    for c in (draft or {}).get("claims") or []:
        out.append({k: c.get(k) for k in CLAIM_FIELDS})
    return out


def _issue_source(issue: dict[str, Any], model: dict[str, Any] | None, rules: dict[str, Any] | None) -> str:
    key = (issue.get("claim_id"), (issue.get("reason") or "")[:40])
    in_rules = any((i.get("claim_id"), (i.get("reason") or "")[:40]) == key for i in (rules or {}).get("issues", []))
    in_model = any((i.get("claim_id"), (i.get("reason") or "")[:40]) == key for i in (model or {}).get("issues", []))
    if in_rules and in_model:
        return "both"
    return "rules" if in_rules else "model" if in_model else "unknown"


def diff_drafts(old: list[dict[str, Any]], new: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Per-claim change between two draft versions: added / removed / changed / unchanged."""

    old_by, new_by = {c["claim_id"]: c for c in old}, {c["claim_id"]: c for c in new}
    out = []
    for cid, c in new_by.items():
        if cid not in old_by:
            out.append({"claim_id": cid, "change": "added", "fields": []})
            continue
        fields = [f for f in ("kind", "text", "evidence_refs", "limitations") if (old_by[cid].get(f) or None) != (c.get(f) or None)]
        out.append({"claim_id": cid, "change": "changed" if fields else "unchanged", "fields": fields,
                    "before": {f: old_by[cid].get(f) for f in fields}})
    for cid in old_by:
        if cid not in new_by:
            out.append({"claim_id": cid, "change": "removed", "fields": [], "before": {"text": old_by[cid].get("text")}})
    return out


def review_view(job: dict[str, Any]) -> dict[str, Any]:
    cp = job.get("checkpoint") or {}
    drafts_raw = cp.get("drafts")
    drafts_complete = bool(drafts_raw)
    if not drafts_raw:
        drafts_raw = [job["draft"]] if job.get("draft") else []
    drafts = []
    for i, d in enumerate(drafts_raw, start=1):
        claims = _claims(d)
        entry = {"version": i, "status": d.get("status"), "claims": claims,
                 "decision_summary": str(d.get("decision_summary") or "")[:120],
                 "unknowns": list(d.get("unknowns") or [])[:5], "limitations": list(d.get("limitations") or [])[:5]}
        if i > 1:
            entry["diff"] = diff_drafts(drafts[-1]["claims"], claims)
        drafts.append(entry)

    rounds = []
    for r in cp.get("reviews") or []:
        final = r.get("final") or {}
        model, rules = r.get("model"), r.get("rules")
        rounds.append({
            "round": r.get("round"),
            "model_decision": (model or {}).get("decision"),
            "rules_decision": (rules or {}).get("decision"),
            "final_decision": final.get("decision"),
            "decision_summary": str(final.get("decision_summary") or "")[:120],
            "checked_refs": list(final.get("checked_refs") or [])[:20],
            "issues": [{**{k: i.get(k) for k in ISSUE_FIELDS}, "source": _issue_source(i, model, rules)}
                       for i in final.get("issues") or []],
        })

    empty_reason = None
    if not rounds:
        if job.get("mode") == "single":
            empty_reason = "single 模式沒有 Reviewer，本 job 不會有覆核紀錄。"
        elif job.get("status") in ("queued", "running") and job.get("stage") in ("research", "tools", None):
            empty_reason = "Researcher 還在研究，草稿完成後才會進入覆核。"
        elif (job.get("draft") or {}).get("status") == "insufficient" or job.get("stop_reason") == "researcher_insufficient":
            empty_reason = "Researcher 判定資料不足並停止，沒有送出可覆核的草稿，所以沒有模型覆核。"
        elif job.get("status") in ("paused_quota", "timed_out", "failed", "cancelled"):
            empty_reason = f"job 在覆核前停止（{job.get('stop_reason') or job.get('status')}），沒有覆核紀錄。"
        else:
            empty_reason = "這個 job 沒有覆核紀錄。"

    return {
        "drafts": drafts,
        "drafts_complete": drafts_complete,
        "rounds": rounds,
        "empty_reason": empty_reason,
        "supplement_rounds": job.get("supplement_rounds", 0),
        "publication_status": job.get("publication_status") or "draft",
    }
