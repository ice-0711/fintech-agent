"""Report data section frozen into the approved report JSON (W07-A, handbook ch.04 F05).

The website and the PDF both render *only* the approved report JSON. This module builds the
deterministic part of it — quarterly table, valuation status with DCF assumptions and
sensitivity, data-quality risk, 2454 peer comparison, price window and resolved sources —
from the job's own snapshot with B's tools. No LLM, no network, no new formula.

* Global snapshot jobs (forward / normal research) use B's tools on data/financial-snapshots.json.
* Case snapshots (snap-dev-*, snap-test-*) only expose what the case snapshot contains; tables the
  case cannot support are left out with a stated reason instead of being filled from other data.
"""

from __future__ import annotations

import hashlib
from typing import Any

from agents import tools_impl
from agents.snapshot import SnapshotToolbox, load_case_snapshot

from .comparison import DCF_ASSUMPTIONS, build_comparison, company_row_at, quarters_table
from .risk import METHOD_VERSION as RISK_METHOD
from .risk import RISK_FOOTNOTE, VALUATION_FOOTNOTE

DATA_VERSION = "report-data-v1.1"  # v1.1: snapshot_id citations resolve to the financial-snapshot tool result
EXCERPT_CHARS = 200
METHOD_LIMITATIONS = [
    "所有數字由工具從資料快照計算，沒有 LLM 改寫；缺值以 NA 加原因呈現，不以 0 代替。",
    "DCF 基準情境假設 FCF 5 年持平於 TTM FCF、不成長；WACC 9%、g 3% 是組長核定的程式預設，不是個股風險估計。"
    "因此模型值普遍低於市價，這是假設造成的，不代表股價高估。",
    "價格為未還原收盤價；收盤價自交易日 17:30（台北）起才視為可得。",
    "季度數字為單季，不是年度數字；TTM 為最近四季加總；FCF = 營業現金流 − 正值資本支出。",
    "同業比較只適用 2454，且只在報告資料截止與同業快照相同時呈現，不混用不同時點。",
]


def _fmt(v: Any) -> str:
    return "NA" if v is None else f"{v:,.2f}".rstrip("0").rstrip(".") if isinstance(v, float) else str(v)


def _snapshot_source(toolbox: SnapshotToolbox, ref: str, ticker: str, cutoff: str) -> dict[str, Any] | None:
    """A claim may cite the financial-snapshot tool result by its snapshot_id (B, W07 audit). The 'excerpt'
    is the tool's own values for that snapshot, so a reader can check every number the claim uses."""
    r = toolbox("get_financial_snapshot", {"ticker": ticker, "cutoff": cutoff})
    d = r.get("data") if r.get("status") == "ok" else None
    if not d or d.get("snapshot_id") != ref:
        return None
    m = d.get("metrics") or {}
    periods = d.get("ttm_periods") or []
    span = f"{periods[0]}–{periods[-1]}" if periods else "NA"
    basis = {"single_quarter": "單季", "cumulative": "累計"}.get(d.get("period_basis"), d.get("period_basis") or "NA")
    excerpt = (f"財報快照 {ref}（{d.get('latest_period')}，{basis}；金額單位億元）：單季 EPS {_fmt(m.get('eps_single_q'))} 元；"
               f"近四季 EPS 合計（TTM）{_fmt(m.get('eps_ttm'))} 元（{span}）；單季營收 {_fmt(m.get('revenue_single_q'))}；"
               f"TTM FCF {_fmt(m.get('fcf_ttm'))}。")
    return {"id": ref, "resolved": True, "kind": "financial_snapshot", "source_id": d.get("source_id"),
            "source_url": None, "available_at": d.get("available_at"), "content_hash": d.get("content_hash"),
            "hash_match": None, "hash_note": "原始財報檔的 sha256（工具結果，不是公告片段）", "excerpt": excerpt}


def _sources(toolbox: SnapshotToolbox, refs: list[str], ticker: str, cutoff: str) -> list[dict[str, Any]]:
    out = []
    for ref in dict.fromkeys(refs):
        snap = _snapshot_source(toolbox, ref, ticker, cutoff) if ref.startswith("snap-") else None
        if snap is not None:
            out.append(snap)
            continue
        r = toolbox("read_evidence", {"evidence_version_id": ref})
        if r.get("status") != "ok":
            out.append({"id": ref, "resolved": False,
                        "reason": "不是本快照的來源片段（例如工具觀察編號 obs-*），或 cutoff 前不可得"
                        if r.get("status") == "no_data" else (r.get("reason") or r.get("status"))})
            continue
        d = r["data"]
        para = d.get("paragraph") or ""
        out.append({"id": ref, "resolved": True, "kind": "evidence", "source_url": d.get("source_url"),
                    "available_at": d.get("available_at"), "content_hash": d.get("content_hash"),
                    "hash_match": hashlib.sha256(para.encode("utf-8")).hexdigest() == d.get("content_hash"),
                    "excerpt": para[:EXCERPT_CHARS] + ("…" if len(para) > EXCERPT_CHARS else "")})
    return out


def _claim_refs(job: dict[str, Any]) -> list[str]:
    return [ref for c in ((job.get("draft") or {}).get("claims") or []) for ref in (c.get("evidence_refs") or [])]


def build_report_data(job: dict[str, Any]) -> dict[str, Any]:
    ticker, cutoff, snap_id = job["ticker"], job["cutoff_at"], job["source_snapshot_id"]
    toolbox = SnapshotToolbox(ticker, snap_id, cutoff)
    refs = _claim_refs(job)
    method = {"data_version": DATA_VERSION, "risk_method": RISK_METHOD, "tools_version": "tools-v12",
              "dcf_assumptions": DCF_ASSUMPTIONS, "valuation_footnote": VALUATION_FOOTNOTE,
              "risk_footnote": RISK_FOOTNOTE, "limitations": METHOD_LIMITATIONS}

    if load_case_snapshot(snap_id) is not None:
        fin = toolbox("get_financial_snapshot", {"ticker": ticker, "cutoff": cutoff})
        price = toolbox("get_price_window", {"ticker": ticker, "end_at": cutoff, "sessions": 1})
        return {
            "scope": "case_snapshot",
            "scope_note": f"本報告使用案例快照 {snap_id}：只呈現快照內有的數字；季度序列、DCF 與同業比較不適用。",
            "financial": fin.get("data") if fin.get("status") == "ok" else None,
            "price": (price.get("data") or {}).get("closes") if price.get("status") == "ok" else None,
            "price_window": None, "price_window_na_reason": "案例快照只有單日收盤價",
            "quarters": None, "quarters_na_reason": "案例快照不含季度序列",
            "valuation": {"status": "undeterminable", "label": "無法判定", "gap": None,
                          "reason": "案例快照不提供 DCF 所需的連續四季 FCF、淨負債與流通股數",
                          "dcf_per_share": None, "sensitivity": None, "dcf_detail": None},
            "data_quality": {"level": "unassessed", "label": "資料品質風險：未評估",
                             "reasons": ["案例快照不跑資料品質檢查"], "checks": []},
            "peer_comparison": None, "peer_na_reason": "案例快照不含同業資料",
            "sources": _sources(toolbox, refs, ticker, cutoff),
            "method": method,
        }

    row = company_row_at(ticker, cutoff)
    window = tools_impl.get_price_window(ticker, cutoff, 5)
    peer, peer_reason = None, "同業比較只適用 2454"
    if ticker == "2454":
        cmp_ = build_comparison()
        if tools_impl._parse_iso(cmp_["cutoff_at"]) == tools_impl._parse_iso(cutoff):
            peer = {k: cmp_[k] for k in ("price_as_of", "cutoff_at", "snapshot_version", "method_version",
                                         "periods_consistent", "peer_stats", "data_status")}
            peer["rows"] = [{k: r[k] for k in ("ticker", "name", "role", "financial_period", "price", "metrics",
                                               "include_in_peer_stats")}
                            | {"valuation": {k: r["valuation"][k] for k in ("status", "label", "gap", "reason")},
                               "data_quality": {k: r["data_quality"][k] for k in ("level", "label")}}
                            for r in cmp_["rows"]]
            peer_reason = None
        else:
            peer_reason = "同業快照的資料截止與本報告不同，不混用不同時點的比較"
    return {
        "scope": "global_snapshot",
        "scope_note": None,
        "company": row.get("name"),
        "financial_period": row["financial_period"],
        "available_at": row["available_at"],
        "price": row["price"],
        "price_window": (window.get("data") or {}).get("closes") if window.get("status") == "ok" else None,
        "price_window_na_reason": None if window.get("status") == "ok"
        else f"近 5 個交易日收盤價不可得：{window.get('reason') or window.get('status')}",
        "ttm": {"periods": row.get("ttm_periods"), "eps_ttm": row["metrics"]["pe_ttm"].get("eps_ttm"),
                "fcf_ttm": row["metrics"]["fcf_ttm"]["value"]},
        "quarters": quarters_table(ticker, cutoff), "quarters_na_reason": None,
        "metrics": row["metrics"],
        "valuation": row["valuation"],
        "data_quality": {k: row["data_quality"][k] for k in ("level", "label", "reasons", "checks")},
        "peer_comparison": peer, "peer_na_reason": peer_reason,
        "sources": _sources(toolbox, refs + [e["id"] for e in row["evidence"]], ticker, cutoff),
        "method": method,
    }
