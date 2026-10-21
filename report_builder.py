"""PDF report builder for fintech-agent.

The output PDF is generated with editable source data from the Python pipeline
and saved under output/. The generated PDF itself is ignored by Git according
to the existing .gitignore.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
import logging

import pandas as pd
from fpdf import FPDF

ROOT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT_DIR / "output"
FONT_CANDIDATES = [
    ROOT_DIR / "assets" / "fonts" / "NotoSansCJKtc-Regular.otf",
    Path(r"C:\Windows\Fonts\msjh.ttc"),
    Path(r"C:\Windows\Fonts\msjhbd.ttc"),
    Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
    Path("/usr/share/fonts/opentype/noto/NotoSansCJKtc-Regular.otf"),
]
PDF_FONT_FAMILY = "report_font"

logging.getLogger("fontTools.subset").setLevel(logging.ERROR)


class ReportPDF(FPDF):
    def header(self) -> None:
        self.set_font(PDF_FONT_FAMILY, "B", 10)
        self.set_text_color(30, 65, 80)
        self.cell(0, 8, "多智能體投資分析系統", align="R", new_x="LMARGIN", new_y="NEXT")
        self.ln(2)

    def footer(self) -> None:
        self.set_y(-15)
        self.set_font(PDF_FONT_FAMILY, "", 8)
        self.set_text_color(120, 120, 120)
        self.cell(0, 10, f"第 {self.page_no()} 頁", align="C")


def clean_text(value: Any, default: str = "尚無資料") -> str:
    if value is None:
        return default
    if isinstance(value, list):
        return "\n".join(str(item) for item in value if item) or default
    if isinstance(value, dict):
        return "\n".join(f"{key}: {item}" for key, item in value.items()) or default
    text = str(value).strip()
    return text or default


def add_section_title(pdf: FPDF, title: str) -> None:
    pdf.set_fill_color(225, 245, 238)
    pdf.set_text_color(8, 80, 65)
    pdf.set_font(PDF_FONT_FAMILY, "B", 15)
    pdf.multi_cell(0, 10, title[:42], fill=True, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)


def add_key_value(pdf: FPDF, label: str, value: Any) -> None:
    pdf.set_font(PDF_FONT_FAMILY, "B", 10)
    pdf.set_text_color(18, 47, 64)
    pdf.cell(0, 7, label, new_x="LMARGIN", new_y="NEXT")
    pdf.set_font(PDF_FONT_FAMILY, "", 10)
    pdf.multi_cell(0, 7, clean_text(value), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(1)


def macro_summary(macro_df: pd.DataFrame, limit: int = 8) -> list[tuple[str, str, str]]:
    if macro_df.empty or not {"indicator", "date", "value"}.issubset(macro_df.columns):
        return []
    rows = []
    latest = macro_df.dropna(subset=["indicator", "date", "value"]).sort_values("date")
    for indicator, subset in latest.groupby("indicator"):
        item = subset.tail(1).iloc[0]
        rows.append((str(indicator), str(item["date"]), f"{float(item['value']):,.2f}"))
    return rows[:limit]


def add_macro_table(pdf: FPDF, macro_df: pd.DataFrame) -> None:
    rows = macro_summary(macro_df)
    if not rows:
        pdf.set_font(PDF_FONT_FAMILY, "", 10)
        pdf.multi_cell(0, 8, "macro_data 目前沒有可整理的資料。")
        return

    pdf.set_font(PDF_FONT_FAMILY, "B", 9)
    pdf.set_fill_color(181, 212, 244)
    pdf.cell(68, 8, "指標", border=1, fill=True)
    pdf.cell(42, 8, "日期", border=1, fill=True)
    pdf.cell(50, 8, "最新值", border=1, fill=True, new_x="LMARGIN", new_y="NEXT")
    pdf.set_font(PDF_FONT_FAMILY, "", 9)
    for indicator, date, value in rows:
        pdf.cell(68, 8, indicator, border=1)
        pdf.cell(42, 8, date, border=1)
        pdf.cell(50, 8, value, border=1, new_x="LMARGIN", new_y="NEXT")


def add_chart_pages(pdf: FPDF, chart_paths: list[str]) -> None:
    titles = ["股價走勢圖", "P/E 與 P/B 財務比率圖", "DCF 估值瀑布圖"]
    for index, path in enumerate(chart_paths):
        chart = Path(path)
        if not chart.exists():
            continue
        pdf.add_page()
        title = titles[index] if index < len(titles) else f"分析圖表 {index + 1}"
        add_section_title(pdf, title)
        pdf.image(str(chart), x=12, y=38, w=185)


def resolve_font_path() -> Path:
    for path in FONT_CANDIDATES:
        if path.exists():
            return path
    raise FileNotFoundError(
        "找不到可用中文字型，請確認 assets/fonts/NotoSansCJKtc-Regular.otf 存在。"
    )


def register_pdf_fonts(pdf: FPDF) -> None:
    font_path = resolve_font_path()
    pdf.add_font(PDF_FONT_FAMILY, "", str(font_path))
    pdf.add_font(PDF_FONT_FAMILY, "B", str(font_path))


def build_pdf_report(
    stock_code: str,
    macro_df: pd.DataFrame,
    fundamental_data: dict[str, Any],
    dcf_details: dict[str, Any],
    chart_paths: list[str],
) -> str:
    """Build a PDF report and return the output path."""

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / f"{stock_code}_analysis_report.pdf"

    pdf = ReportPDF()
    pdf.set_auto_page_break(auto=True, margin=16)
    register_pdf_fonts(pdf)

    pdf.add_page()
    pdf.set_text_color(18, 47, 64)
    pdf.set_font(PDF_FONT_FAMILY, "B", 22)
    pdf.cell(0, 14, f"{fundamental_data.get('company', stock_code)} 投資分析報告", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font(PDF_FONT_FAMILY, "", 11)
    pdf.set_text_color(100, 119, 128)
    pdf.multi_cell(0, 8, f"股票代號：{stock_code}｜資料來源：{fundamental_data.get('data_source', 'unknown')}")
    pdf.ln(5)

    add_section_title(pdf, "一、DCF 估值結論")
    value = dcf_details.get("intrinsic_value_per_share")
    add_key_value(pdf, "每股內在價值", f"{value:,.2f} 元/股" if value is not None
                  else dcf_details.get("unavailable_reason", "無法判定"))
    if value is not None:
        add_key_value(pdf, "五年 FCF 現值", f"{dcf_details['pv_fcf']:,.2f} 億元")
        add_key_value(pdf, "終端價值現值", f"{dcf_details['pv_terminal']:,.2f} 億元")
        add_key_value(pdf, "企業價值", f"{dcf_details['enterprise_value']:,.2f} 億元")
        add_key_value(pdf, "股權價值", f"{dcf_details['equity_value']:,.2f} 億元")
    pdf.ln(4)

    add_section_title(pdf, "二、財報分析摘要")
    add_key_value(pdf, "公司名稱", fundamental_data.get("company"))
    add_key_value(pdf, "分析摘要", fundamental_data.get("summary"))
    add_key_value(pdf, "主要風險", fundamental_data.get("risks"))
    pdf.ln(4)

    add_section_title(pdf, "三、總經資料摘要")
    add_macro_table(pdf, macro_df)

    add_chart_pages(pdf, chart_paths)
    pdf.output(str(output_path))
    return str(output_path)


if __name__ == "__main__":
    print("請由 main.py 呼叫 build_pdf_report() 產生完整報告。")
