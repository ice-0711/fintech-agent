"""Rule-based financial analyzer.

This module generates a deterministic financial summary from FinMind records.
It does not require Gemini, OpenAI, or any external model API, so the project
can produce analysis text even when API keys or quotas are unavailable.
"""

from __future__ import annotations

from datetime import datetime
from math import isfinite
from typing import Any


def to_float(value: Any) -> float | None:
    """Convert values to float when possible."""

    if value is None:
        return None
    try:
        return float(str(value).replace(",", "").strip())
    except ValueError:
        return None


def money_100m(value: Any) -> float | None:
    """Convert raw TWD values to NT$100 million units.

    缺值回傳 None（W03 修正：null 與 0 必須分開，不再補 0.0）。
    """

    parsed = to_float(value)
    if parsed is None:
        return None
    if abs(parsed) >= 10_000_000:
        return parsed / 100_000_000
    return parsed


def fmt_100m(value: float | None) -> str:
    """億元金額轉文字；缺值顯示「無資料」而不是 0。"""

    if value is None or not isfinite(value):
        return "無資料"
    return f"{value:,.0f}"


def percent(value: float | None) -> str:
    if value is None or not isfinite(value):
        return "無法判斷"
    return f"{value * 100:.1f}%"


def growth_rate(start: Any, end: Any) -> float | None:
    start_value = to_float(start)
    end_value = to_float(end)
    if start_value in (None, 0) or end_value is None:
        return None
    return end_value / start_value - 1


def safe_margin(numerator: Any, denominator: Any) -> float | None:
    num = to_float(numerator)
    den = to_float(denominator)
    if den in (None, 0) or num is None:
        return None
    return num / den


def build_fcf_forecast(records: list[dict[str, Any]]) -> list[float]:
    """Forecast five years of FCF using a capped recent growth rate."""

    fcfs = [to_float(row.get("free_cash_flow")) for row in records]
    fcfs = [value for value in fcfs if value is not None]
    positive_fcfs = [value for value in fcfs if value > 0]
    if not positive_fcfs:
        return []

    latest = positive_fcfs[-1]
    if len(positive_fcfs) >= 2 and positive_fcfs[-2] > 0:
        growth = positive_fcfs[-1] / positive_fcfs[-2] - 1
    else:
        growth = 0.05
    growth = max(min(growth, 0.12), 0.03)

    forecast = []
    value = latest
    for _ in range(5):
        value *= 1 + growth
        forecast.append(round(value, 2))
    return forecast


def analyze_financials(financial_data: list[dict[str, Any]], stock_code: str, company_name: str) -> dict[str, Any]:
    """Generate summary, strengths, risks, and FCF forecast from financial data."""

    records = [
        row for row in financial_data
        if row.get("revenue") is not None and row.get("free_cash_flow") is not None
    ]
    records = sorted(records, key=lambda row: str(row.get("year", "")))
    if not records:
        return {}

    first = records[0]
    latest = records[-1]
    revenue_growth = growth_rate(first.get("revenue"), latest.get("revenue"))
    net_income_growth = growth_rate(first.get("net_income"), latest.get("net_income"))
    fcf_growth = growth_rate(first.get("free_cash_flow"), latest.get("free_cash_flow"))
    operating_margin = safe_margin(latest.get("operating_income"), latest.get("revenue"))
    net_margin = safe_margin(latest.get("net_income"), latest.get("revenue"))
    fcf_margin = safe_margin(latest.get("free_cash_flow"), latest.get("revenue"))
    pe_ratio = to_float(latest.get("pe_ratio"))
    pb_ratio = to_float(latest.get("pb_ratio"))
    net_debt_100m = money_100m(latest.get("net_debt"))

    fcf_forecast = build_fcf_forecast(records)
    latest_year = latest.get("year", "最新年度")
    latest_revenue_100m = money_100m(latest.get("revenue"))
    latest_fcf_100m = money_100m(latest.get("free_cash_flow"))

    summary = (
        f"{company_name}（{stock_code}）近 {len(records)} 年財務資料顯示，"
        f"{latest_year} 年營收約 {fmt_100m(latest_revenue_100m)} 億元，"
        f"自由現金流約 {fmt_100m(latest_fcf_100m)} 億元。"
        f"營收相較期初成長 {percent(revenue_growth)}，淨利成長 {percent(net_income_growth)}，"
        f"最新營業利益率約 {percent(operating_margin)}、淨利率約 {percent(net_margin)}。"
        "整體判斷以實際 FinMind 財務數據為基礎，適合作為 DCF 估值與投資分析報告的文字摘要。"
    )

    strengths = [
        f"營收規模持續具備代表性，近年營收成長率約 {percent(revenue_growth)}。",
        f"最新年度營業利益率約 {percent(operating_margin)}，顯示本業獲利能力仍可支撐估值分析。",
        f"最新年度自由現金流約 {fmt_100m(latest_fcf_100m)} 億元，提供 DCF 模型可用的現金流基礎。",
    ]
    if net_debt_100m is not None and net_debt_100m < 0:
        strengths.append(f"最新年度呈現淨現金狀態，淨負債約 {fmt_100m(net_debt_100m)} 億元，財務彈性較佳。")

    risks = []
    negative_fcf_years = [
        str(row.get("year")) for row in records
        if (fcf := to_float(row.get("free_cash_flow"))) is not None and fcf < 0
    ]
    if negative_fcf_years:
        risks.append(f"{'、'.join(negative_fcf_years)} 年自由現金流為負，顯示資本支出或營運資金波動需留意。")
    if fcf_growth is not None and fcf_growth < 0:
        risks.append(f"自由現金流相較期初下降 {abs(fcf_growth) * 100:.1f}%，估值假設需保守。")
    if revenue_growth is not None and revenue_growth < 0:
        risks.append(f"營收相較期初下降 {abs(revenue_growth) * 100:.1f}%，成長動能需重新檢視。")
    if pe_ratio and pe_ratio > 25:
        risks.append(f"最新本益比約 {pe_ratio:.2f} 倍，若成長不如預期，評價修正壓力較高。")
    if pb_ratio and pb_ratio > 5:
        risks.append(f"最新股價淨值比約 {pb_ratio:.2f} 倍，市場已反映較高成長期待。")
    if fcf_margin is not None and fcf_margin < 0.03:
        risks.append(f"最新自由現金流率約 {percent(fcf_margin)}，現金流轉換效率偏低。")

    while len(risks) < 3:
        risks.append("未來營收、毛利率與資本支出變化仍會影響 DCF 估值結果，需持續追蹤。")

    print(f"[OK] 自動化財務分析完成：{company_name}")
    return {
        "company": company_name,
        "stock_code": stock_code,
        "summary": summary,
        "strengths": strengths[:4],
        "risks": risks[:3],
        "fcf_forecast": fcf_forecast,
        "analysis_method": "rule_based_finmind",
        "created_at": datetime.now().isoformat(),
    }


if __name__ == "__main__":
    from report_downloader import download_financial_report

    data = download_financial_report("2330", years=5)
    result = analyze_financials(data, "2330", "台積電")
    print("\n===== 分析結果 =====")
    print("摘要：", result.get("summary"))
    print("優勢：", result.get("strengths"))
    print("風險：", result.get("risks"))
    print("FCF預測：", result.get("fcf_forecast"))
