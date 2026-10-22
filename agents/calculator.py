"""agents/calculator.py
W03-B / W06 重構版: calculate_metrics 純數學確定性運算實作模組。
包含五大 operations:
1. growth_rate: 成長率計算 (同口徑、前期非0)
2. simple_return: 簡單價格報酬率
3. pe_ttm: 本益比 (同日市價 / TTM EPS，EPS<=0 標註 NA)
4. dcf_scenario: 現金流折現估值 (WACC > g，缺值不補0，輸出敏感度矩陣)
5. peer_comparison: 同業比較 (對齊組長驗證器，2330 嚴格排除於平均值計算之外)

W06 修正（2026-10-20）：growth_rate 基期 ≤ 0 回傳 NA（原為除以 abs(基期)）。
W03 修正（2026-10-20）：ok 回傳補 reason=None；peer_comparison 接受 tools.py 的
dcf_per_share、fcf 鍵，補各指標 NA 理由，並檢查比較標的白名單。
"""

from __future__ import annotations
from typing import Any


def calculate_growth_rate(current: float | None, previous: float | None) -> dict[str, Any]:
    if current is None or previous is None:
        return {"result_value": None, "is_applicable": False, "reason": "數值缺失 (null)"}
    if previous <= 0:
        # 基期為負或 0 時成長率無意義（例：−100 → −50 不是「成長 50%」），比照「分母非正 NA」
        return {"result_value": None, "is_applicable": False, "reason": "基期為負或 0，成長率無意義（NA）"}
    val = round((current - previous) / previous, 4)
    return {"result_value": val, "is_applicable": True, "reason": None}


PRICE_BASES = ("raw", "adjusted")


def calculate_simple_return(entry_price: float | None, exit_price: float | None,
                            entry_price_basis: str | None = None,
                            exit_price_basis: str | None = None) -> dict[str, Any]:
    """
    簡單報酬 = (出場價 − 進場價) ÷ 進場價。
    W07-B：可選填 entry_price_basis／exit_price_basis（raw 未還原／adjusted 還原）；
    兩者都填且不同 → NA（原始與調整價格不可混算，手冊第 06 章、CASE-24）。未填時行為與 W06 相同。
    """
    if entry_price is None or exit_price is None or entry_price <= 0:
        return {"result_value": None, "is_applicable": False, "reason": "買進價格無效或非正數"}
    for name, basis in (("entry_price_basis", entry_price_basis), ("exit_price_basis", exit_price_basis)):
        if basis is not None and basis not in PRICE_BASES:
            return {"result_value": None, "is_applicable": False,
                    "reason": f"{name} 只能是 {PRICE_BASES}，收到 {basis}"}
    if entry_price_basis and exit_price_basis and entry_price_basis != exit_price_basis:
        return {"result_value": None, "is_applicable": False,
                "reason": f"價格調整口徑不一致（進場 {entry_price_basis}、出場 {exit_price_basis}），原始與調整價格不可混算報酬（NA）"}
    if exit_price <= 0:
        return {"result_value": None, "is_applicable": False, "reason": "出場價格無效或非正數"}
    ret = round((exit_price - entry_price) / entry_price, 4)
    out = {"result_value": ret, "is_applicable": True, "reason": None}
    if entry_price_basis and exit_price_basis:
        out["price_basis"] = entry_price_basis
    return out


def calculate_pe_ttm(price: float | None, eps_ttm: float | None) -> dict[str, Any]:
    if price is None or eps_ttm is None:
        return {"result_value": None, "is_applicable": False, "reason": "市價或 EPS TTM 缺失"}
    if eps_ttm <= 0:
        return {"result_value": None, "is_applicable": False, "reason": "EPS TTM <= 0，不適用本益比 (NA)"}
    pe = round(price / eps_ttm, 2)
    return {"result_value": pe, "is_applicable": True, "reason": None}


def _run_single_dcf(fcfs: list[float], w: float, gr: float, nd: float, sh: float) -> tuple[float, float, float, float, float, float]:
    pv_fcfs = sum(fcf / ((1 + w) ** idx) for idx, fcf in enumerate(fcfs, start=1))
    tv = fcfs[-1] * (1 + gr) / (w - gr)
    pv_tv = tv / ((1 + w) ** len(fcfs))
    ev = pv_fcfs + pv_tv
    eq = ev - nd
    per_share = round((eq / sh) * 100, 2)
    return round(pv_fcfs, 2), round(tv, 2), round(pv_tv, 2), round(ev, 2), round(eq, 2), per_share


def calculate_dcf_scenario(
    free_cash_flows: list[float] | None,
    wacc: float | None,
    terminal_growth: float | None,
    net_debt: float | None,
    shares_outstanding: float | None
) -> dict[str, Any]:
    if (
        free_cash_flows is None
        or not free_cash_flows
        or wacc is None
        or terminal_growth is None
        or net_debt is None
        or shares_outstanding is None
    ):
        return {
            "enterprise_value": None,
            "equity_value": None,
            "intrinsic_value_per_share": None,
            "sensitivity_matrix": None,
            "is_applicable": False,
            "reason": "DCF 關鍵參數缺失，嚴禁假補 0"
        }
    if len(free_cash_flows) != 5:
        return {
            "enterprise_value": None,
            "equity_value": None,
            "intrinsic_value_per_share": None,
            "sensitivity_matrix": None,
            "is_applicable": False,
            "reason": f"DCF 預測期必須為 5 年，目前為 {len(free_cash_flows)} 年"
        }

    if wacc <= terminal_growth:
        return {
            "enterprise_value": None,
            "equity_value": None,
            "intrinsic_value_per_share": None,
            "sensitivity_matrix": None,
            "is_applicable": False,
            "reason": f"WACC ({wacc}) 必須嚴格大於終端成長率 g ({terminal_growth})"
        }

    if shares_outstanding <= 0:
        return {
            "enterprise_value": None,
            "equity_value": None,
            "intrinsic_value_per_share": None,
            "sensitivity_matrix": None,
            "is_applicable": False,
            "reason": "流通股數必須大於 0"
        }

    # 基準計算
    pv_fcfs, tv, pv_tv, ev, eq, per_share = _run_single_dcf(
        free_cash_flows, wacc, terminal_growth, net_debt, shares_outstanding
    )

    # 產出手冊要求的 WACC ±1% 與 g ±0.5% 敏感度矩陣
    wacc_steps = [round(wacc - 0.01, 4), round(wacc, 4), round(wacc + 0.01, 4)]
    g_steps = [round(terminal_growth - 0.005, 4), round(terminal_growth, 4), round(terminal_growth + 0.005, 4)]

    sensitivity_matrix: dict[str, dict[str, float | None]] = {}
    for w in wacc_steps:
        w_label = f"{round(w * 100, 2)}%"
        sensitivity_matrix[w_label] = {}
        for gr in g_steps:
            g_label = f"{round(gr * 100, 2)}%"
            if w <= gr:
                sensitivity_matrix[w_label][g_label] = None
            else:
                _, _, _, _, _, ps = _run_single_dcf(free_cash_flows, w, gr, net_debt, shares_outstanding)
                sensitivity_matrix[w_label][g_label] = ps

    return {
        "pv_fcf_total": pv_fcfs,
        "terminal_value": tv,
        "pv_terminal": pv_tv,
        "enterprise_value": ev,
        "equity_value": eq,
        "intrinsic_value_per_share": per_share,
        "sensitivity_matrix": sensitivity_matrix,
        "is_applicable": True,
        "reason": None
    }


PEER_SUBJECT = "2454"
PEER_ALLOWED = ("2379", "3034", "2330")
INDUSTRY_REFERENCE = ("2330",)
MAX_PEER_COMPANIES = 4


def _positive(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and x > 0


def calculate_peer_comparison(
    subject: str,
    comparators: list[str],
    metrics_map: dict[str, Any]
) -> dict[str, Any]:
    """同業比較：PE、PB、季營收 YoY、FCF、DCF 差距；2330 為產業參照，不入同業平均。

    metrics_map 每家可含：price, eps_ttm, bvps, pb, revenue_yoy, fcf, dcf_per_share
    （dcf_intrinsic_value 為舊鍵名，仍相容）。缺值一律 null 並附 NA 理由，不補 0。
    """
    if subject != PEER_SUBJECT:
        return {"is_applicable": False, "reason": f"同業比較主體只限 {PEER_SUBJECT}"}
    comparators = list(comparators or [])
    bad = [c for c in comparators if c not in PEER_ALLOWED]
    if bad:
        return {"is_applicable": False, "reason": f"比較標的只限 {PEER_ALLOWED}，收到 {bad}"}
    if len(set(comparators)) != len(comparators):
        return {"is_applicable": False, "reason": "比較標的不可重複"}
    total_companies = [subject] + comparators
    if len(total_companies) > MAX_PEER_COMPANIES:
        return {"is_applicable": False, "reason": f"比較公司總數不可超過 {MAX_PEER_COMPANIES} 家"}

    data_dict = metrics_map.get("metrics_data", metrics_map) if isinstance(metrics_map, dict) else {}

    table: dict[str, Any] = {}
    peer_pes: list[float] = []
    peer_pbs: list[float] = []
    peer_yoys: list[float] = []

    for code in total_companies:
        data = data_dict.get(code) or {}
        price = data.get("price")
        eps = data.get("eps_ttm")
        bvps = data.get("bvps")
        pb = data.get("pb")
        yoy = data.get("revenue_yoy")
        fcf = data.get("fcf")
        dcf_val = data.get("dcf_per_share", data.get("dcf_intrinsic_value"))

        if not _positive(price):
            pe_val, pe_reason = None, "基準日收盤價缺失"
        elif not _positive(eps):
            pe_val, pe_reason = None, "EPS TTM 缺失或非正數"
        else:
            pe_val, pe_reason = round(price / eps, 2), None

        if pb is None and _positive(price) and _positive(bvps):
            pb = round(price / bvps, 2)
        if pb is None:
            pb_reason = "BVPS 缺失或非正數" if _positive(price) else "基準日收盤價缺失"
        else:
            pb_reason = None

        dcf_gap = round((dcf_val - price) / price, 4) if (dcf_val is not None and _positive(price)) else None

        role = "industry_reference" if code in INDUSTRY_REFERENCE else ("subject" if code == subject else "peer")
        table[code] = {
            "role": role,
            "price": price,
            "pe_ttm": pe_val,
            "pe_na_reason": pe_reason,
            "pb_ratio": pb,
            "pb_na_reason": pb_reason,
            "revenue_yoy": yoy,
            "revenue_yoy_na_reason": None if yoy is not None else "季營收或去年同季基期缺失",
            "fcf": fcf,
            "fcf_na_reason": None if fcf is not None else "FCF TTM 缺失",
            "dcf_intrinsic_value": dcf_val,
            "dcf_gap_pct": dcf_gap,
        }

        # 只有 peer 角色進入同業平均；2330 與主體都不計入
        if role == "peer":
            if pe_val is not None:
                peer_pes.append(pe_val)
            if pb is not None:
                peer_pbs.append(pb)
            if yoy is not None:
                peer_yoys.append(yoy)

    return {
        "subject": subject,
        "comparison_table": table,
        "peer_average_stats": {
            "peer_avg_pe": round(sum(peer_pes) / len(peer_pes), 2) if peer_pes else None,
            "peer_avg_pb": round(sum(peer_pbs) / len(peer_pbs), 2) if peer_pbs else None,
            "peer_avg_revenue_yoy": round(sum(peer_yoys) / len(peer_yoys), 4) if peer_yoys else None,
            "excluded_references": list(INDUSTRY_REFERENCE),
        },
        "is_applicable": True,
        "reason": None
    }


def execute_calculation(operation: str, values: dict[str, Any], evidence_refs: list[str]) -> dict[str, Any]:
    if not evidence_refs:
        return {
            "status": "invalid_input",
            "tool": "calculate_metrics",
            "reason": "運算必須引用具體 evidence_refs 依據",
            "data": None
        }

    if operation == "growth_rate":
        res = calculate_growth_rate(values.get("current"), values.get("previous"))
    elif operation == "simple_return":
        res = calculate_simple_return(values.get("entry_price"), values.get("exit_price"),
                                      values.get("entry_price_basis"), values.get("exit_price_basis"))
    elif operation == "pe_ttm":
        res = calculate_pe_ttm(values.get("price"), values.get("eps_ttm"))
    elif operation == "dcf_scenario":
        res = calculate_dcf_scenario(
            values.get("free_cash_flows"),
            values.get("wacc"),
            values.get("terminal_growth"),
            values.get("net_debt"),
            values.get("shares_outstanding")
        )
    elif operation == "peer_comparison":
        res = calculate_peer_comparison(
            values.get("subject", ""),
            values.get("comparators", []),
            values.get("metrics_data", values.get("metrics", {}))
        )
    else:
        return {
            "status": "invalid_input",
            "tool": "calculate_metrics",
            "reason": f"未知的運算操作: {operation}",
            "data": None
        }

    if not res.get("is_applicable", False):
        return {
            "status": "invalid_input",
            "tool": "calculate_metrics",
            "reason": res.get("reason", "運算條件不滿足"),
            "data": None
        }

    res["evidence_refs"] = evidence_refs
    res["operation"] = operation
    return {
        "status": "ok",
        "tool": "calculate_metrics",
        "reason": None,
        "data": res
    }
