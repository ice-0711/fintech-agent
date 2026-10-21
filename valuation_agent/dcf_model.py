"""DCF 估值模型。

本模組使用五年自由現金流、WACC、終端成長率、淨負債與流通股數，
估算股票的每股內在價值。
"""

from __future__ import annotations


def calculate_dcf_details(
    free_cash_flows,
    wacc=0.09,
    terminal_growth=0.03,
    net_debt=0,
    shares_outstanding=1,
):
    """回傳 DCF 計算明細。

    參數說明：
    - free_cash_flows: 未來自由現金流列表，建議放 5 年預測值
    - wacc: 加權平均資金成本，預設 9%（與 main.py、手冊第 02 章一致；組長 2026-10-21 核定）
    - terminal_growth: 終端成長率，預設 3%
    - net_debt: 淨負債，若公司是淨現金可輸入負數
    - shares_outstanding: 流通股數，若金額用「億元」，股數建議用「百萬股」

    注意：
    目前專題範例使用「億元」與「百萬股」，所以最後會乘以 100，
    換算成「元/股」。
    """

    if not free_cash_flows:
        raise ValueError("free_cash_flows 不可為空。")
    if wacc <= terminal_growth:
        raise ValueError("wacc 必須大於 terminal_growth，否則終端價值無法合理計算。")
    if shares_outstanding <= 0:
        raise ValueError("shares_outstanding 必須大於 0。")

    discounted_cash_flows = []
    for year_index, fcf in enumerate(free_cash_flows, start=1):
        present_value = fcf / ((1 + wacc) ** year_index)
        discounted_cash_flows.append(round(present_value, 2))

    pv_fcf = sum(discounted_cash_flows)
    terminal_value = free_cash_flows[-1] * (1 + terminal_growth) / (wacc - terminal_growth)
    pv_terminal = terminal_value / ((1 + wacc) ** len(free_cash_flows))
    enterprise_value = pv_fcf + pv_terminal
    equity_value = enterprise_value - net_debt

    # 範例單位是「億元 / 百萬股」，1 億元 / 1 百萬股 = 100 元/股。
    intrinsic_value_per_share = equity_value / shares_outstanding * 100

    return {
        "discounted_cash_flows": discounted_cash_flows,
        "pv_fcf": round(pv_fcf, 2),
        "terminal_value": round(terminal_value, 2),
        "pv_terminal": round(pv_terminal, 2),
        "enterprise_value": round(enterprise_value, 2),
        "equity_value": round(equity_value, 2),
        "intrinsic_value_per_share": round(intrinsic_value_per_share, 2),
    }


def calculate_dcf(
    free_cash_flows,
    wacc=0.09,
    terminal_growth=0.03,
    net_debt=0,
    shares_outstanding=1,
):
    """回傳每股內在價值。"""

    details = calculate_dcf_details(
        free_cash_flows=free_cash_flows,
        wacc=wacc,
        terminal_growth=terminal_growth,
        net_debt=net_debt,
        shares_outstanding=shares_outstanding,
    )
    return details["intrinsic_value_per_share"]


if __name__ == "__main__":
    stock_name = "台積電"
    fcf_list = [2000, 2200, 2400, 2600, 2800]
    wacc = 0.09
    terminal_growth = 0.03
    net_debt = -3000
    shares_outstanding = 25945

    result = calculate_dcf_details(
        free_cash_flows=fcf_list,
        wacc=wacc,
        terminal_growth=terminal_growth,
        net_debt=net_debt,
        shares_outstanding=shares_outstanding,
    )

    print(f"{stock_name} DCF 估值測試")
    print(f"五年預測 FCF（億元）：{fcf_list}")
    print(f"WACC：{wacc:.2%}")
    print(f"終端成長率：{terminal_growth:.2%}")
    print(f"淨負債（億元）：{net_debt:,.0f}")
    print(f"流通股數（百萬股）：{shares_outstanding:,.0f}")
    print(f"各年 FCF 現值（億元）：{result['discounted_cash_flows']}")
    print(f"五年 FCF 現值合計（億元）：{result['pv_fcf']:,.2f}")
    print(f"終端價值（億元）：{result['terminal_value']:,.2f}")
    print(f"終端價值現值（億元）：{result['pv_terminal']:,.2f}")
    print(f"企業價值（億元）：{result['enterprise_value']:,.2f}")
    print(f"股權價值（億元）：{result['equity_value']:,.2f}")
    print(f"每股內在價值：{result['intrinsic_value_per_share']:,.2f} 元/股")
