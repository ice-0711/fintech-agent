"""2454 peer-comparison panel data (W04-A, updated W05-A), per ui/v12-comparison-contract.md.

Main values come only from B's deterministic tools on the fixed snapshot
(get_financial_snapshot, get_price_window, calculate_metrics). B's peer
snapshot values are kept as `snapshot_value` and compared; a mismatch is a
data-quality conflict. Missing → null + reason, never 0. No LLM, no network.

DCF follows the lead's decisions of 2026-10-21 (handoff/decisions-2026-10.md):
WACC 9 %, g 3 %, base case = 5 years flat at the TTM FCF, formula of
valuation_agent/dcf_model.py as implemented in calculate_metrics(dcf_scenario).
"""

from __future__ import annotations

import hashlib
import json
from datetime import timedelta
from pathlib import Path
from typing import Any

from agents import tools_impl

from .risk import METHOD_VERSION as RISK_METHOD
from .risk import VALUATION_FOOTNOTE, Check, data_quality_risk, valuation_status

ROOT = Path(__file__).resolve().parent.parent
PEER_SNAPSHOT = ROOT / "data" / "v12-peer-snapshot.json"
ORDER = ("2454", "2379", "3034", "2330")
DCF_ASSUMPTIONS = {"wacc": 0.09, "terminal_growth": 0.03, "years": 5,
                   "fcf_basis": "5 年持平於 TTM FCF（基準情境）",
                   "source": "組長核定 2026-10-21；WACC 為程式預設，非個股風險估計"}
METHOD_VERSION = f"ui-peer-v2 / calculate_metrics / {RISK_METHOD}"
# B 2026-10-22: legal gap between filings reaches ~137 days (Q3 report 11/14 → annual 3/31), so 150 days.
STALE_AFTER = timedelta(days=150)  # latest quarter older than this at cutoff → marked stale


def _na(reason: str, snapshot_value: Any = None, **extra: Any) -> dict[str, Any]:
    return {"value": None, "na_reason": reason, "source": "snapshot_only" if snapshot_value is not None else "none",
            "snapshot_value": snapshot_value, "consistent": None, **extra}


def _tool_value(value: float, snapshot_value: Any, tol: float = 0.01, **extra: Any) -> dict[str, Any]:
    consistent = None
    if isinstance(snapshot_value, (int, float)):
        consistent = abs(value - snapshot_value) <= max(tol, abs(snapshot_value) * 0.001)
    return {"value": value, "na_reason": None, "source": "tool", "snapshot_value": snapshot_value,
            "consistent": consistent, **extra}


def _calc(op: str, values: dict[str, Any], refs: list[str]) -> dict[str, Any]:
    return tools_impl.calculate_metrics(op, values, refs or ["snapshot"])


def _quarters(ticker: str, cutoff: str) -> list[dict[str, Any]]:
    cutoff_dt = tools_impl._parse_iso(cutoff)
    company = tools_impl._load_snapshots().get("financials", {}).get(ticker) or {}
    return [q for q in company.get("quarters", []) if tools_impl._parse_iso(q["available_at"]) <= cutoff_dt]


def _evidence(ref: str) -> dict[str, Any]:
    out = tools_impl.read_evidence(ref)
    if out.get("status") != "ok":
        return {"id": ref, "exists": False, "hash_match": None}
    data = out["data"]
    match = hashlib.sha256(data["paragraph"].encode("utf-8")).hexdigest() == data["content_hash"]
    return {"id": ref, "exists": True, "hash_match": match}


def _row(code: str, snap: dict[str, Any], price_as_of: str, cutoff: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    issues: list[dict[str, Any]] = []
    snap = dict(snap)
    snap.setdefault("evidence_refs", [f"ev-{code}-2026q2-01"])
    quarters = _quarters(code, cutoff)
    fin = tools_impl.get_financial_snapshot(code, cutoff)
    fin_data = fin.get("data") or {}
    m = fin_data.get("metrics") or {}
    refs = list(snap.get("evidence_refs") or [])

    price = None
    window = tools_impl.get_price_window(code, cutoff, 1)
    if window.get("status") == "ok":
        last = window["data"]["closes"][-1]
        if last["trade_date"] == price_as_of:
            price = {"value": last.get("close_price", last.get("close")), "trade_date": last["trade_date"],
                     "basis": window["data"].get("price_basis"), "available_at": last.get("available_at")}

    out: dict[str, Any] = {}
    eps_ttm, bvps = m.get("eps_ttm"), m.get("bvps")

    # P/E (TTM) = same-day close ÷ TTM EPS
    if price is None:
        out["pe_ttm"] = _na(f"{price_as_of} 無收盤價，不用其他日期補", snap.get("pe_ttm"))
    elif eps_ttm is None:
        out["pe_ttm"] = _na("TTM 需連續 4 季單季 EPS", snap.get("pe_ttm"))
    else:
        r = _calc("pe_ttm", {"price": price["value"], "eps_ttm": eps_ttm}, refs)
        out["pe_ttm"] = (_tool_value(r["data"]["result_value"], snap.get("pe_ttm"), eps_ttm=eps_ttm)
                         if r["status"] == "ok" else _na(r.get("reason") or "不適用", snap.get("pe_ttm")))

    # P/B = same-day close ÷ BVPS (through the calculator's peer_comparison rule)
    if price is None:
        out["pb"] = _na(f"{price_as_of} 無收盤價", snap.get("pb_ratio"))
    elif not isinstance(bvps, (int, float)) or bvps <= 0:
        out["pb"] = _na("BVPS 缺失或非正數", snap.get("pb_ratio"))
    else:
        r = _calc("peer_comparison", {"subject": "2454", "comparators": [],
                                      "metrics": {"2454": {"price": price["value"], "bvps": bvps}}}, refs)
        pb = r["data"]["comparison_table"]["2454"]["pb_ratio"] if r["status"] == "ok" else None
        out["pb"] = _tool_value(pb, snap.get("pb_ratio"), bvps=bvps) if pb is not None else _na("不適用", snap.get("pb_ratio"))

    # single-quarter revenue YoY
    latest = quarters[-1] if quarters else None
    if latest is None:
        out["revenue_yoy_quarter"] = _na("快照沒有可得季度", snap.get("revenue_yoy_quarter"))
    else:
        base_period = f"{int(latest['period'][:4]) - 1}{latest['period'][4:]}"
        base = next((q for q in quarters if q["period"] == base_period), None)
        if base is None:
            out["revenue_yoy_quarter"] = _na(f"缺去年同季基期（{base_period}）", snap.get("revenue_yoy_quarter"))
        else:
            r = _calc("growth_rate", {"current": latest.get("revenue"), "previous": base.get("revenue")}, refs)
            out["revenue_yoy_quarter"] = (_tool_value(r["data"]["result_value"], snap.get("revenue_yoy_quarter"), tol=0.0005,
                                                      base_period=base_period)
                                          if r["status"] == "ok" else _na(r.get("reason") or "不適用", snap.get("revenue_yoy_quarter")))

    # FCF (TTM)
    fcf_ttm = m.get("fcf_ttm")
    out["fcf_ttm"] = (_tool_value(fcf_ttm, snap.get("fcf_ttm_100m"), tol=0.05, unit="億元") if fcf_ttm is not None
                      else _na("TTM 需連續 4 季", snap.get("fcf_ttm_100m"), unit="億元"))

    # DCF per share and gap
    dcf_inputs = {"free_cash_flows": [fcf_ttm] * DCF_ASSUMPTIONS["years"] if fcf_ttm is not None else None,
                  "wacc": DCF_ASSUMPTIONS["wacc"], "terminal_growth": DCF_ASSUMPTIONS["terminal_growth"],
                  "net_debt": m.get("net_debt"), "shares_outstanding": m.get("shares_outstanding_m")}
    dcf_per_share, sensitivity, dcf_detail = None, None, None
    fcf_positive = isinstance(fcf_ttm, (int, float)) and fcf_ttm > 0  # TTM FCF ≤ 0 → do not run DCF at all
    if fcf_positive and all(v is not None for v in dcf_inputs.values()):
        r = _calc("dcf_scenario", dcf_inputs, refs)
        if r["status"] == "ok":
            dcf_per_share = r["data"]["intrinsic_value_per_share"]
            sensitivity = r["data"].get("sensitivity_matrix")
            dcf_detail = {k: r["data"].get(k) for k in ("pv_fcf_total", "terminal_value", "pv_terminal",
                                                         "enterprise_value", "equity_value")}
            dcf_detail.update(net_debt=m.get("net_debt"), shares_outstanding_m=m.get("shares_outstanding_m"),
                              fcf_ttm=fcf_ttm, unit="億元；股數百萬股")
    valuation = valuation_status(dcf_per_share, price["value"] if price else None, dcf_inputs)
    if valuation["gap"] is not None:
        out["dcf_gap"] = _tool_value(valuation["gap"], snap.get("dcf_gap_pct"), tol=0.00005, dcf_per_share=dcf_per_share,
                                     snapshot_dcf_per_share=snap.get("dcf_intrinsic_value"))
        snap_dcf = snap.get("dcf_intrinsic_value")
        if isinstance(snap_dcf, (int, float)) and abs(snap_dcf - dcf_per_share) > 0.01:
            out["dcf_gap"]["consistent"] = False
    else:
        out["dcf_gap"] = _na(valuation["reason"], snap.get("dcf_gap_pct"))

    # data-quality checks (predefined list; see ui/v12-risk-state-cases.md)
    evidence = [_evidence(r) for r in refs]
    ttm_periods = fin_data.get("ttm_periods") or []
    unverified = [q["period"] for q in quarters if q["period"] in ttm_periods and q.get("eps_source") == "unverified"]
    eps_ok = eps_ttm is not None and not unverified
    eps_detail = ("不足 4 季" if eps_ttm is None else f"EPS 來源未驗證：{'、'.join(unverified)}") if not eps_ok else ""
    net_debt, shares = m.get("net_debt"), m.get("shares_outstanding_m")
    checks = [
        Check("price_same_day", "同日收盤價", True, "pass" if price else "missing",
              "" if price else f"{price_as_of} 無收盤價"),
        Check("eps_ttm_4q", "連續 4 季 EPS（TTM）", True, "pass" if eps_ok else "missing", eps_detail),
        Check("fcf_ttm_4q", "連續 4 季 FCF（TTM）", True, "pass" if fcf_ttm is not None else "missing",
              "" if fcf_ttm is not None else "不足 4 季"),
        Check("net_debt", "淨負債", True, "pass" if isinstance(net_debt, (int, float)) else "missing",
              "" if isinstance(net_debt, (int, float)) else "缺值（不以 0 代替）"),
        Check("shares_outstanding", "流通股數", True,
              "pass" if isinstance(shares, (int, float)) and shares > 0 else "missing",
              "" if isinstance(shares, (int, float)) and shares > 0 else "缺值或非正"),
        Check("fin_available_at", "財報可得時間", True,
              "pass" if fin_data.get("available_at") else ("time_unknown" if fin_data else "missing"),
              "" if fin_data.get("available_at") else "沒有可得時間"),
        Check("source_traceable", "來源片段可追溯", True,
              "conflict" if any(e["exists"] and e["hash_match"] is False for e in evidence)
              else ("pass" if evidence and all(e["exists"] for e in evidence) else "missing"),
              "" if evidence and all(e["exists"] and e["hash_match"] for e in evidence) else
              "片段 hash 不符" if any(e["hash_match"] is False for e in evidence) else "引用的片段不在快照中"),
        Check("bvps", "每股淨值 BVPS", False, "pass" if isinstance(bvps, (int, float)) and bvps > 0 else "missing"),
        Check("yoy_base", "去年同季營收", False, "pass" if out["revenue_yoy_quarter"]["value"] is not None else "missing",
              out["revenue_yoy_quarter"]["na_reason"] or ""),
    ]
    conflicts = [n for n, c in out.items() if c.get("consistent") is False]
    checks.append(Check("snapshot_consistent", "工具值與 B 快照一致", True, "conflict" if conflicts else "pass",
                        ("不一致：" + "、".join(conflicts)) if conflicts else ""))
    if fin_data.get("available_at"):
        age = tools_impl._parse_iso(cutoff) - tools_impl._parse_iso(fin_data["available_at"])
        checks.append(Check("freshness", "財報新鮮度", False, "stale" if age > STALE_AFTER else "pass",
                            f"最新可得財報為 {age.days} 天前公告" if age > STALE_AFTER else ""))
    risk = data_quality_risk(checks).as_dict()

    for name, cell in out.items():
        if cell.get("consistent") is False:
            issues.append({"ticker": code, "metric": name,
                           "issue": f"工具值 {cell['value']} 與 B 快照 {cell['snapshot_value']} 不一致"})
        elif cell["source"] == "snapshot_only":
            issues.append({"ticker": code, "metric": name, "issue": cell["na_reason"]})

    role = snap.get("role")
    return {
        "ticker": code,
        "name": snap.get("name") or fin_data.get("company_name"),
        "role": role,
        "financial_period": fin_data.get("latest_period") or snap.get("financial_period"),
        "available_at": fin_data.get("available_at"),
        "available_at_basis": fin_data.get("available_at_basis"),
        "quarters_available": len(quarters),
        "ttm_periods": fin_data.get("ttm_periods"),
        "price": price,
        "metrics": out,
        "valuation": {**valuation, "dcf_per_share": dcf_per_share, "sensitivity": sensitivity, "dcf_detail": dcf_detail},
        "data_quality": risk,
        "evidence": evidence,
        "include_in_peer_stats": role == "peer",
    }, issues


def build_comparison() -> dict[str, Any]:
    peer = json.loads(PEER_SNAPSHOT.read_text(encoding="utf-8"))
    price_as_of, cutoff = peer["price_as_of"], peer["cutoff_at"]
    rows, checks = [], []
    for code in ORDER:
        snap = peer["companies"].get(code)
        if snap is None:
            continue
        row, issues = _row(code, snap, price_as_of, cutoff)
        rows.append(row)
        checks.extend(issues)

    subject_period = next((r["financial_period"] for r in rows if r["role"] == "subject"), None)
    peers = [r for r in rows if r["include_in_peer_stats"] and r["financial_period"] == subject_period]

    def avg(metric: str, nd: int = 2) -> dict[str, Any]:
        vals = [r["metrics"][metric]["value"] for r in peers if r["metrics"][metric]["value"] is not None]
        return {"value": round(sum(vals) / len(vals), nd) if vals else None, "n": len(vals),
                "na_reason": None if vals else "同業沒有可由工具重現的值"}

    stats_snapshot = peer.get("peer_summary_statistics") or {}
    synthetic = peer.get("synthetic_fixture")
    return {
        "ok": True,
        "subject": "2454",
        "price_as_of": price_as_of,
        "cutoff_at": cutoff,
        "snapshot_version": peer.get("snapshot_version"),
        "method_version": METHOD_VERSION,
        "synthetic_fixture": synthetic is not False,
        "data_status": "B 標示為真實資料（synthetic_fixture=false），待 D 覆核" if synthetic is False
                       else "B 未標示真實或合成，一律以 FIXTURE 呈現",
        "periods_consistent": len({r["financial_period"] for r in rows if r["financial_period"]}) <= 1,
        "rows": rows,
        "peer_stats": {
            "basis": "只用 role=peer、與主體同財報期、且可由工具重現者；2330 產業參照與主體一律排除",
            "pe_ttm": avg("pe_ttm"), "pb": avg("pb"), "revenue_yoy_quarter": avg("revenue_yoy_quarter", 4),
            "snapshot_values": {"pe_ttm": stats_snapshot.get("peer_avg_pe"), "pb": stats_snapshot.get("peer_avg_pb"),
                                "revenue_yoy_quarter": stats_snapshot.get("peer_avg_revenue_yoy")},
            "excluded": [r["ticker"] for r in rows if not r["include_in_peer_stats"]],
        },
        "dcf_assumptions": DCF_ASSUMPTIONS,
        "valuation_footnote": VALUATION_FOOTNOTE,
        "checks": checks,
    }


def company_row(code: str) -> dict[str, Any]:
    """Same tool-derived row for any snapshot ticker (used by the published list)."""
    peer = json.loads(PEER_SNAPSHOT.read_text(encoding="utf-8"))
    snap = dict(peer["companies"].get(code) or {"role": "research"})
    row, _ = _row(code, snap, peer["price_as_of"], peer["cutoff_at"])
    return row


def company_row_at(code: str, cutoff: str) -> dict[str, Any]:
    """Tool-derived row at any cutoff (report data). B's peer snapshot values are used for the
    consistency check only when the snapshot has the same cutoff; otherwise there is nothing to compare."""
    peer = json.loads(PEER_SNAPSHOT.read_text(encoding="utf-8"))
    window = tools_impl.get_price_window(code, cutoff, 1)
    closes = (window.get("data") or {}).get("closes") or []
    price_as_of = closes[-1]["trade_date"] if window.get("status") == "ok" and closes else cutoff[:10]
    same = tools_impl._parse_iso(peer["cutoff_at"]) == tools_impl._parse_iso(cutoff)
    base = peer["companies"].get(code) or {}
    snap = dict(base) if same else {"name": base.get("name")}
    snap.setdefault("role", base.get("role") or "research")
    row, _ = _row(code, snap, price_as_of, cutoff)
    row["price_as_of"] = price_as_of
    row["compared_with_peer_snapshot"] = same
    return row


def quarters_table(code: str, cutoff: str, limit: int = 5) -> list[dict[str, Any]]:
    keep = ("period", "period_basis", "revenue", "operating_income", "net_income", "eps", "eps_source",
            "free_cash_flow", "available_at")
    return [{k: q.get(k) for k in keep} for q in _quarters(code, cutoff)[-limit:]]


def referenced_evidence_ids() -> set[str]:
    peer = json.loads(PEER_SNAPSHOT.read_text(encoding="utf-8"))
    refs = {ref for company in peer["companies"].values() for ref in company.get("evidence_refs") or []}
    return refs | {f"ev-{code}-2026q2-01" for code in ("2330", "2317", "2454")}
