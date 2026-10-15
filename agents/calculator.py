"""agents/calculator.py
W03-B / W06 重構版: calculate_metrics 純數學確定性運算實作模組。
包含五大 operations:
1. growth_rate: 成長率計算 (同口徑、前期非0)
2. simple_return: 簡單價格報酬率
3. pe_ttm: 本益比 (同日市價 / TTM EPS，EPS<=0 標註 NA)
4. dcf_scenario: 現金流折現估值 (WACC > g，缺值不補0，輸出敏感度矩陣)
5. peer_comparison: 同業比較 (對齊組長驗證器，2330 嚴格排除於平均值計算之外)
"""

from __future__ import annotations
from typing import Any


def calculate_growth_rate(current: float | None, previous: float | None) -> dict[str, Any]:
    if current is None or previous is None:
        return {"result_value": None, "is_applicable": False, "reason": "數值缺失 (null)"}
    if previous == 0:
        return {"result_value": None, "is_applicable": False, "reason": "基期數值為 0，無法計算成長率"}
    val = round((current - previous) / abs(previous), 4)
    return {"result_value": val, "is_applicable": True, "reason": None}


def calculate_simple_return(entry_price: float | None, exit_price: float | None) -> dict[str, Any]:
    if entry_price is None or exit_price is None or entry_price <= 0:
        return {"result_value": None, "is_applicable": False, "reason": "買進價格無效或非正數"}
    ret = round((exit_price - entry_price) / entry_price, 4)
    return {"result_value": ret, "is_applicable": True, "reason": None}


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


def calculate_peer_comparison(
    subject: str,
    comparators: list[str],
    metrics_map: dict[str, Any]
) -> dict[str, Any]:
    """同業比較計算 (支援以指標名稱為清單或以股票為鍵的雙向格式，嚴格排除 2330)"""
    if subject != "2454":
        return {"is_applicable": False, "reason": "同業比較主體只限 2454"}

    total_companies = [subject] + comparators
    if len(total_companies) > 4:
        return {"is_applicable": False, "reason": "比較公司總數不可超過 4 家"}

    # 支援組長驗證器結構：如果 metrics_map 內包含以股票為鍵的字典或 metrics_data
    data_dict = metrics_map.get("metrics_data", metrics_map)

    table = {}
    peer_pes = []
    peer_pbs = []
    peer_yoys = []

    for code in total_companies:
        data = data_dict.get(code, {})
        p = data.get("price")
        eps = data.get("eps_ttm")
        bvps = data.get("bvps")
        pb = data.get("pb")
        yoy = data.get("revenue_yoy")
        dcf_val = data.get("dcf_intrinsic_value")

        pe_val = round(p / eps, 2) if (p and eps and eps > 0) else None
        pe_na_reason = "EPS TTM 缺失或非正數" if (pe_val is None) else None

        if pb is None and p is not None and bvps is not None and bvps > 0:
            pb = round(p / bvps, 2)
        pb_na_reason = "BVPS 缺失或非正數" if (pb is None) else None

        # 計算市價與 DCF 差距百分比
        dcf_gap = round((dcf_val - p) / p, 4) if (dcf_val is not None and p is not None and p > 0) else None

        role = "industry_reference" if code == "2330" else ("subject" if code == subject else "peer")

        table[code] = {
            "role": role,
            "price": p,
            "pe_ttm": pe_val,
            "pe_na_reason": pe_na_reason,
            "pb_ratio": pb,
            "pb_na_reason": pb_na_reason,
            "revenue_yoy": yoy,
            "dcf_intrinsic_value": dcf_val,
            "dcf_gap_pct": dcf_gap
        }

        # 核心防呆：只有 peer 角色才進入同業平均計算，2330 嚴格排除
        if role == "peer":
            if pe_val is not None:
                peer_pes.append(pe_val)
            if pb is not None:
                peer_pbs.append(pb)
            if yoy is not None:
                peer_yoys.append(yoy)

    avg_pe = round(sum(peer_pes) / len(peer_pes), 2) if peer_pes else None
    avg_pb = round(sum(peer_pbs) / len(peer_pbs), 2) if peer_pbs else None
    avg_yoy = round(sum(peer_yoys) / len(peer_yoys), 4) if peer_yoys else None

    return {
        "subject": subject,
        "comparison_table": table,
        "peer_average_stats": {
            "peer_avg_pe": avg_pe,
            "peer_avg_pb": avg_pb,
            "peer_avg_revenue_yoy": avg_yoy,
            "excluded_references": ["2330"]
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
        res = calculate_simple_return(values.get("entry_price"), values.get("exit_price"))
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
        "data": res
    }
