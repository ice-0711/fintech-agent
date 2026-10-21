"""W3-W5 integration entrypoint for the fintech-agent project.

Usage:
    python main.py 2330

The program reads Supabase first. fundamental_data must contain FinMind numeric
values either as dedicated columns or as the summary JSON payload written by
seed_fundamental_data.py.
"""

from __future__ import annotations

import ast
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

import pandas as pd
from dotenv import load_dotenv
from supabase import Client, create_client

from report_downloader import fetch_price_history as fetch_finmind_price_history
from report_downloader import fetch_stock_name
from valuation_agent.chart_builder import (
    plot_dcf_waterfall,
    plot_financial_ratios,
    plot_stock_price,
)
from valuation_agent.dcf_model import calculate_dcf_details

ROOT_DIR = Path(__file__).resolve().parent
PAGE_SIZE = 1000


def get_supabase_client() -> Client:
    """Create a Supabase client from .env."""

    load_dotenv(ROOT_DIR / ".env")
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if not url or not key:
        raise ValueError("找不到 SUPABASE_URL 或 SUPABASE_KEY，請確認 .env。")
    return create_client(url, key)


def fetch_all_rows(client: Client, table_name: str) -> list[dict[str, Any]]:
    """Read all rows from a Supabase table using simple pagination."""

    rows: list[dict[str, Any]] = []
    start = 0
    while True:
        end = start + PAGE_SIZE - 1
        response = client.table(table_name).select("*").range(start, end).execute()
        batch = response.data or []
        rows.extend(batch)
        if len(batch) < PAGE_SIZE:
            break
        start += PAGE_SIZE
    return rows


def load_macro_data(client: Client) -> pd.DataFrame:
    """Read macro_data and convert it into a pandas DataFrame."""

    rows = fetch_all_rows(client, "macro_data")
    macro_df = pd.DataFrame(rows)
    if macro_df.empty:
        raise ValueError("macro_data 目前沒有資料。")

    if "value" in macro_df.columns:
        macro_df["value"] = pd.to_numeric(macro_df["value"], errors="coerce")
    if "date" in macro_df.columns:
        macro_df = macro_df.sort_values("date").reset_index(drop=True)
    return macro_df


def parse_summary_payload(value: Any) -> dict[str, Any]:
    """Parse FinMind numeric and analysis payloads stored in summary."""

    if not isinstance(value, str) or not value.strip().startswith("{"):
        return {}
    try:
        payload = json.loads(value)
    except json.JSONDecodeError:
        return {}
    if not isinstance(payload, dict):
        return {}

    financials = payload.get("financials")
    result = dict(financials) if isinstance(financials, dict) else {}
    analysis = payload.get("analysis")
    if isinstance(analysis, dict):
        for key in ["strengths", "risks", "fcf_forecast"]:
            if analysis.get(key) is not None:
                result[key] = analysis[key]
    if payload.get("summary_text"):
        result["_summary_text"] = payload["summary_text"]
    if payload.get("data_source"):
        result["data_source"] = payload["data_source"]
    return result


def parse_json_field(value: Any) -> Any:
    """Decode JSON strings from text columns when possible."""

    if not isinstance(value, str):
        return value
    text = value.strip()
    if not text or text[0] not in "[{":
        return value
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return value


def normalize_fundamental_row(row: dict[str, Any]) -> dict[str, Any]:
    """Merge dedicated columns with optional summary JSON payload."""

    normalized = dict(row)
    for key in ["strengths", "risks", "fcf_forecast"]:
        if key in normalized:
            normalized[key] = parse_json_field(normalized.get(key))
    payload = parse_summary_payload(row.get("summary"))
    for key, value in payload.items():
        if key == "_summary_text":
            normalized["summary_text"] = value
        elif normalized.get(key) is None:
            normalized[key] = value
    if normalized.get("summary_text"):
        normalized["summary"] = normalized["summary_text"]
    return normalized


def load_fundamental_data(client: Client, stock_code: str) -> dict[str, Any]:
    """Read one stock's rows from fundamental_data and package them as a dict."""

    response = (
        client.table("fundamental_data")
        .select("*")
        .eq("stock_code", stock_code)
        .execute()
    )
    rows = response.data or []
    if not rows:
        raise ValueError(f"fundamental_data 找不到 stock_code={stock_code} 的資料。")

    rows = [normalize_fundamental_row(row) for row in rows]
    rows = sorted(rows, key=lambda row: str(row.get("year", "")))
    latest = rows[-1]
    return {
        "stock_code": stock_code,
        "company": latest.get("company") or stock_code,
        "latest": latest,
        "records": rows,
        "summary": latest.get("summary"),
        "strengths": latest.get("strengths"),
        "risks": latest.get("risks"),
        "fcf_forecast": latest.get("fcf_forecast"),
        "data_source": latest.get("data_source") or "supabase",
        "shares_outstanding": latest.get("shares_outstanding"),
        "net_debt": latest.get("net_debt"),
    }


def to_float(value: Any) -> float | None:
    """Best effort conversion to float."""

    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).replace(",", "").strip())
    except ValueError:
        return None


def numbers_from_forecast(value: Any) -> list[float]:
    """Parse a list of numeric FCF forecast values from Supabase output."""

    if value is None:
        return []
    if isinstance(value, (int, float)):
        return [float(value)]
    if isinstance(value, dict):
        numbers: list[float] = []
        for item in value.values():
            numbers.extend(numbers_from_forecast(item))
        return numbers
    if isinstance(value, list):
        numbers: list[float] = []
        for item in value:
            numbers.extend(numbers_from_forecast(item))
        return numbers

    text = str(value).strip()
    if not text:
        return []

    try:
        parsed = ast.literal_eval(text)
    except (ValueError, SyntaxError):
        parsed = None
    if parsed is not None and parsed != text:
        parsed_numbers = numbers_from_forecast(parsed)
        if parsed_numbers:
            return parsed_numbers

    numbers: list[float] = []
    for line in text.splitlines() or [text]:
        target = line.split(":", 1)[-1]
        matches = re.findall(r"-?\d+(?:\.\d+)?", target.replace(",", ""))
        if matches:
            numbers.append(float(matches[-1]))
    return numbers


def has_financial_fields(fundamental_data: dict[str, Any]) -> bool:
    """Return True when Supabase rows contain fields needed for DCF/charts."""

    for row in fundamental_data.get("records", []):
        if to_float(row.get("free_cash_flow")) is not None:
            return True
    return bool(numbers_from_forecast(fundamental_data.get("fcf_forecast")))


def ensure_complete_fundamentals(fundamental_data: dict[str, Any]) -> dict[str, Any]:
    """Validate Supabase financial values and enrich charts with FinMind price."""

    stock_code = fundamental_data["stock_code"]
    if not has_financial_fields(fundamental_data):
        raise ValueError(
            "fundamental_data 缺少 DCF 所需的 FinMind 數值。"
            f"請先執行：python seed_fundamental_data.py {stock_code}"
        )

    if not fundamental_data.get("price_history"):
        fundamental_data["price_history"] = fetch_finmind_price_history(stock_code)
    if not fundamental_data.get("company") or fundamental_data["company"] == stock_code:
        fundamental_data["company"] = fetch_stock_name(stock_code)
    return fundamental_data


def normalize_money_to_100m(values: list[float]) -> list[float]:
    """Convert raw TWD-like amounts into NT$100 million units when needed."""

    if not values:
        return values
    if max(abs(value) for value in values) >= 10_000_000:
        return [value / 100_000_000 for value in values]
    return values


def build_fcf_forecast(fundamental_data: dict[str, Any]) -> list[float]:
    """Build five FCF inputs for DCF."""

    forecast = numbers_from_forecast(fundamental_data.get("fcf_forecast"))
    if len(forecast) >= 5:
        return normalize_money_to_100m(forecast[:5])

    historical_fcf = []
    for row in fundamental_data["records"]:
        value = to_float(row.get("free_cash_flow"))
        if value is not None:
            historical_fcf.append(value)

    if not historical_fcf:
        raise ValueError("fundamental_data 沒有可用的 free_cash_flow 或 fcf_forecast。")

    free_cash_flows = historical_fcf[-5:]
    while len(free_cash_flows) < 5:
        free_cash_flows.append(free_cash_flows[-1] * 1.03)
    return normalize_money_to_100m(free_cash_flows[:5])


def env_float(names: list[str], default: float) -> float:
    """Read one of several possible environment variables as float."""

    for name in names:
        value = os.getenv(name)
        if value:
            parsed = to_float(value)
            if parsed is not None:
                return parsed
    return default


def env_float_optional(names: list[str]) -> float | None:
    """Read one of several environment variables as float, or None."""

    for name in names:
        value = os.getenv(name)
        if value:
            parsed = to_float(value)
            if parsed is not None:
                return parsed
    return None


def money_to_100m(value: Any) -> float | None:
    """Convert a single raw TWD value into NT$100 million units when needed."""

    parsed = to_float(value)
    if parsed is None:
        return None
    if abs(parsed) >= 10_000_000:
        return parsed / 100_000_000
    return parsed


def shares_to_million(value: Any) -> float | None:
    shares = to_float(value)
    if shares is None:
        return None
    if shares > 1_000_000:
        return shares / 1_000_000
    return shares


def calculate_intrinsic_value(fundamental_data: dict[str, Any]) -> dict[str, Any]:
    """Call dcf_model.py and return the valuation detail dict."""

    stock_code = fundamental_data["stock_code"]
    free_cash_flows = build_fcf_forecast(fundamental_data)
    wacc = env_float(["DCF_WACC", "DEFAULT_WACC"], 0.09)
    terminal_growth = env_float(["TERMINAL_GROWTH", "DCF_TERMINAL_GROWTH"], 0.03)
    net_debt_override = env_float_optional([f"NET_DEBT_{stock_code}", "DEFAULT_NET_DEBT"])
    net_debt = money_to_100m(net_debt_override)
    if net_debt is None:
        net_debt = money_to_100m(fundamental_data.get("net_debt"))
    if net_debt is None:
        net_debt = money_to_100m(fundamental_data.get("latest", {}).get("net_debt"))

    shares = env_float_optional([f"SHARES_OUTSTANDING_{stock_code}", "DEFAULT_SHARES_OUTSTANDING"])
    shares_outstanding = shares_to_million(shares) or shares_to_million(fundamental_data.get("shares_outstanding"))
    if not shares_outstanding:
        shares_outstanding = shares_to_million(fundamental_data.get("latest", {}).get("shares_outstanding"))
    if not shares_outstanding:
        raise ValueError("fundamental_data 缺少 shares_outstanding，無法計算每股內在價值。")

    if net_debt is None:
        # data-contract §2.7 / §4.2: a missing net debt is never treated as 0. No per-share value.
        return {
            "intrinsic_value_per_share": None,
            "unavailable_reason": "缺淨負債資料，DCF 每股價值無法判定（不以 0 代替）",
            "free_cash_flows": free_cash_flows,
            "net_debt": None,
            "shares_outstanding": shares_outstanding,
            "wacc": wacc,
            "terminal_growth": terminal_growth,
        }

    details = calculate_dcf_details(
        free_cash_flows=free_cash_flows,
        wacc=wacc,
        terminal_growth=terminal_growth,
        net_debt=net_debt,
        shares_outstanding=shares_outstanding,
    )
    details["free_cash_flows"] = free_cash_flows
    details["net_debt"] = net_debt
    details["shares_outstanding"] = shares_outstanding
    details["wacc"] = wacc
    details["terminal_growth"] = terminal_growth
    return details


def stock_price_series(macro_df: pd.DataFrame, fundamental_data: dict[str, Any]) -> tuple[list[str], list[float]]:
    """Prepare price trend data for chart_builder.py."""

    price_history = fundamental_data.get("price_history") or []
    if len(price_history) >= 2:
        return [row["date"] for row in price_history], [float(row["price"]) for row in price_history]

    if {"indicator", "date", "value"}.issubset(macro_df.columns):
        for indicator in [fundamental_data["stock_code"], fundamental_data["company"], "TWII", "S&P500"]:
            subset = macro_df[macro_df["indicator"].astype(str).str.contains(str(indicator), na=False)]
            subset = subset.dropna(subset=["date", "value"]).tail(12)
            if len(subset) >= 2:
                return subset["date"].astype(str).tolist(), subset["value"].astype(float).tolist()

    records = fundamental_data["records"]
    dates = [str(row.get("year")) for row in records if row.get("year") is not None]
    values = [to_float(row.get("revenue")) for row in records]
    values = [value for value in values if value is not None]
    values = normalize_money_to_100m(values)
    if len(dates) >= 2 and len(values) >= 2:
        return dates[-len(values) :], values
    raise ValueError("無法建立股價走勢圖資料。")


def ratio_series(fundamental_data: dict[str, Any]) -> tuple[list[str], list[float], list[float]]:
    """Prepare P/E and P/B-like ratio data for chart_builder.py."""

    years: list[str] = []
    pe_list: list[float] = []
    pb_list: list[float] = []

    for row in fundamental_data["records"]:
        year = row.get("year")
        if year is None:
            continue
        pe = to_float(row.get("pe_ratio") or row.get("pe"))
        pb = to_float(row.get("pb_ratio") or row.get("pb"))
        revenue = to_float(row.get("revenue"))
        net_income = to_float(row.get("net_income"))
        operating_income = to_float(row.get("operating_income"))

        if pe is None and revenue and net_income:
            pe = abs(revenue / net_income)
        if pb is None and revenue and operating_income:
            pb = abs(revenue / operating_income)

        if pe is not None and pb is not None:
            years.append(str(year))
            pe_list.append(round(pe, 2))
            pb_list.append(round(pb, 2))

    if len(years) < 2:
        raise ValueError("無法建立 P/E 與 P/B 圖表資料。")
    return years, pe_list, pb_list


def generate_charts(
    macro_df: pd.DataFrame,
    fundamental_data: dict[str, Any],
    dcf_details: dict[str, Any],
) -> list[str]:
    """Call chart_builder.py and create three PNG charts."""

    stock_name = fundamental_data["company"]
    stock_dates, stock_prices = stock_price_series(macro_df, fundamental_data)
    ratio_years, pe_list, pb_list = ratio_series(fundamental_data)
    charts = [
        plot_stock_price(stock_dates, stock_prices, stock_name),
        plot_financial_ratios(ratio_years, pe_list, pb_list, stock_name),
    ]
    if dcf_details.get("intrinsic_value_per_share") is not None:
        waterfall_components = ["五年 FCF 現值", "終端價值現值", "淨負債調整"]
        waterfall_values = [dcf_details["pv_fcf"], dcf_details["pv_terminal"], -dcf_details["net_debt"]]
        charts.append(plot_dcf_waterfall(waterfall_components, waterfall_values, stock_name))
    return charts


def build_report_if_available(
    macro_df: pd.DataFrame,
    fundamental_data: dict[str, Any],
    dcf_details: dict[str, Any],
    chart_paths: list[str],
) -> str | None:
    """Generate PDF report when report_builder.py is available."""

    if os.getenv("RENDER") and os.getenv("ENABLE_PDF_ON_RENDER") != "1":
        print("略過 PDF 產生：Render 免費環境預設關閉 PDF，以避免記憶體不足。")
        return None

    try:
        from report_builder import build_pdf_report
    except Exception as exc:
        print(f"略過 PDF 產生：report_builder.py 無法匯入（{exc}）")
        return None

    return build_pdf_report(
        stock_code=fundamental_data["stock_code"],
        macro_df=macro_df,
        fundamental_data=fundamental_data,
        dcf_details=dcf_details,
        chart_paths=chart_paths,
    )


def run_analysis(stock_code: str) -> dict[str, Any]:
    """Run the complete data integration, valuation, chart, and PDF flow."""

    client = get_supabase_client()
    print(f"開始分析股票代號：{stock_code}")

    macro_df = load_macro_data(client)
    print(f"已讀取 macro_data：{len(macro_df)} 筆")

    fundamental_data = load_fundamental_data(client, stock_code)
    print(f"已讀取 fundamental_data：{len(fundamental_data['records'])} 筆")

    fundamental_data = ensure_complete_fundamentals(fundamental_data)
    print(f"財務資料來源：{fundamental_data.get('data_source')}")

    dcf_details = calculate_intrinsic_value(fundamental_data)
    value = dcf_details["intrinsic_value_per_share"]
    print(f"每股內在價值：{value:,.2f} 元/股" if value is not None else f"每股內在價值：{dcf_details['unavailable_reason']}")

    chart_paths = generate_charts(macro_df, fundamental_data, dcf_details)
    for path in chart_paths:
        print(f"圖表已輸出：{path}")

    pdf_path = build_report_if_available(macro_df, fundamental_data, dcf_details, chart_paths)
    if pdf_path:
        print(f"PDF 報告已輸出：{pdf_path}")

    print(f"分析完成，共產出 {len(chart_paths)} 張圖表")
    return {"charts": chart_paths, "pdf": pdf_path, "dcf": dcf_details}


def main() -> None:
    stock_code = sys.argv[1] if len(sys.argv) > 1 else input("請輸入股票代號：").strip()
    if not stock_code:
        raise ValueError("stock_code 不可為空。")
    try:
        run_analysis(stock_code)
    except Exception as exc:
        print(f"分析失敗：{exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
