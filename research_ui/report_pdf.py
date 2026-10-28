"""Research PDF from the approved report JSON (W07-A, handbook ch.04 F05).

Renders only what is in the approved JSON — no LLM, no new numbers. Reuses report_builder's
fpdf2 class and embedded CJK font, and valuation_agent.chart_builder for the two existing chart
types (price line, DCF waterfall). Charts are drawn into a temporary folder that is deleted
right after embedding; nothing is kept under output/ (local files are never the permanent copy).
Limits: ≤ 10 pages, ≤ 5 MB. Sources are clickable links.
"""

from __future__ import annotations

import json
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

TW = ZoneInfo("Asia/Taipei")
MAX_PDF_BYTES = 5 * 1024 * 1024
MAX_PDF_PAGES = 10

INK = (29, 42, 44)
MUTED = (92, 109, 111)
TEAL = (14, 122, 106)
RED = (178, 58, 44)
GOLD = (138, 90, 16)
SOFT = (236, 244, 241)
LINE = (214, 225, 222)

EPS_SOURCE = {"mops_direct": "MOPS", "finmind_quarterly": "FinMind", "unverified": "未驗證"}
KIND_TEXT = {"fact": "事實", "inference": "推論", "unknown": "未知"}
LABEL_TEXT = {"MOCK": "MOCK 測試報告：模型決策為預錄腳本，工具結果為真實快照輸出；不是研究結論",
              "LIVE": None}


def _tw(iso: str | None, seconds: bool = False) -> str:
    if not iso:
        return "—"
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(TW)
    except ValueError:
        return str(iso)
    return dt.strftime("%Y-%m-%d %H:%M:%S" if seconds else "%Y-%m-%d %H:%M")


def _num(v: Any, nd: int = 2, unit: str = "") -> str:
    if v is None:
        return "NA"
    if isinstance(v, (int, float)):
        return f"{v:,.{nd}f}{unit}"
    return str(v)


def _pct(v: Any) -> str:
    return "NA" if v is None else f"{v * 100:.1f}%"


def _price_text(price: Any) -> str:
    """The close the valuation gap uses (B's W07 audit: it was only visible in the chart)."""
    if isinstance(price, list):
        price = price[-1] if price else None
    if not isinstance(price, dict):
        return "NA（沒有同日收盤價）"
    value = price.get("value", price.get("close_price"))
    return f"{price.get('trade_date')} 收盤 {_num(value)} 元（未還原；交易日 17:30 起可得）"


class _Doc:
    def __init__(self) -> None:
        from report_builder import PDF_FONT_FAMILY, ReportPDF, register_pdf_fonts  # noqa: PLC0415

        self.F = PDF_FONT_FAMILY
        self.pdf = ReportPDF()
        register_pdf_fonts(self.pdf)
        self.pdf.set_auto_page_break(auto=True, margin=16)
        self.pdf.set_margins(15, 12, 15)
        self.pdf.add_page()

    # -- primitives --------------------------------------------------------
    def font(self, size: float, bold: bool = False, color: tuple[int, int, int] = INK) -> None:
        self.pdf.set_font(self.F, "B" if bold else "", size)
        self.pdf.set_text_color(*color)

    def text(self, value: Any, size: float = 10, bold: bool = False, color=INK, h: float = 5.6) -> None:
        self.font(size, bold, color)
        self.pdf.multi_cell(0, h, "" if value is None else str(value), align="L", new_x="LMARGIN", new_y="NEXT")

    def heading(self, title: str) -> None:
        if self.pdf.get_y() > 255:
            self.pdf.add_page()
        self.pdf.ln(3)
        self.pdf.set_fill_color(*SOFT)
        self.font(12.5, True, TEAL)
        self.pdf.cell(0, 8, f"  {title}", fill=True, new_x="LMARGIN", new_y="NEXT")
        self.pdf.ln(1.5)

    def banner(self, value: str, color=GOLD) -> None:
        self.pdf.set_draw_color(*color)
        self.font(9.5, True, color)
        self.pdf.multi_cell(0, 5.6, value, border=1, align="L", new_x="LMARGIN", new_y="NEXT", padding=1.5)
        self.pdf.ln(1)

    def kv(self, rows: list[tuple[str, Any]]) -> None:
        for k, v in rows:
            self.font(9, True, MUTED)
            self.pdf.cell(32, 5.6, k)
            self.font(9.5)
            self.pdf.multi_cell(0, 5.6, "—" if v is None else str(v), align="L", new_x="LMARGIN", new_y="NEXT")

    def table(self, header: list[str], rows: list[list[Any]], widths: list[int], size: float = 8.5,
              shade_rows: set[int] | None = None) -> None:
        from fpdf.fonts import FontFace  # noqa: PLC0415

        self.font(size)
        self.pdf.set_draw_color(*LINE)
        head = FontFace(emphasis="BOLD", color=MUTED, fill_color=SOFT)
        with self.pdf.table(col_widths=widths, text_align="LEFT", line_height=size * 0.62,
                            headings_style=head, padding=1.2, first_row_as_headings=True) as t:
            t.row([str(h) for h in header])
            for i, r in enumerate(rows):
                style = FontFace(fill_color=(246, 246, 242)) if shade_rows and i in shade_rows else None
                t.row(["" if c is None else str(c) for c in r], style=style)
        self.pdf.ln(1.5)

    def link_line(self, label: str, url: str | None, size: float = 8.5) -> None:
        self.font(size, False, MUTED)
        self.pdf.write(5, label)
        if url:
            self.font(size, False, (16, 68, 94))
            self.pdf.write(5, url, link=url)
        self.pdf.ln(5)


def _charts(data: dict[str, Any], ticker: str, tmp: Path) -> list[tuple[str, str]]:
    """Existing chart types from chart_builder, drawn into tmp (never output/)."""
    from valuation_agent import chart_builder  # noqa: PLC0415

    old_dir = chart_builder.CHART_DIR
    chart_builder.CHART_DIR = tmp
    out: list[tuple[str, str]] = []
    try:
        window = data.get("price_window") or []
        if len(window) >= 2:
            dates = [c["trade_date"] for c in window]
            prices = [c.get("close_price", c.get("close")) for c in window]
            out.append(("近 5 個交易日收盤價（未還原）", chart_builder.plot_stock_price(dates, prices, ticker)))
        detail = (data.get("valuation") or {}).get("dcf_detail")
        if detail and all(detail.get(k) is not None for k in ("pv_fcf_total", "pv_terminal", "net_debt")):
            out.append(("DCF 拆解（億元；基準情境；最後一欄為股東權益價值）", chart_builder.plot_dcf_waterfall(
                ["5 年 FCF 現值", "終端價值現值", "減：淨負債" if detail["net_debt"] >= 0 else "加：淨現金"],
                [detail["pv_fcf_total"], detail["pv_terminal"], -detail["net_debt"]], ticker)))
    finally:
        chart_builder.CHART_DIR = old_dir
    return out


def render_report_pdf(report: dict[str, Any], version: dict[str, Any]) -> bytes:
    from agents.publication import PublicationError  # noqa: PLC0415

    d = _Doc()
    data = report.get("data") or {}
    label = report.get("run_label") or "LIVE"
    company = data.get("company") or ""

    # ---- title block
    d.text(f"{report['ticker']} {company} 研究報告", 17, True, INK, h=9)
    if LABEL_TEXT.get(label):
        d.banner(LABEL_TEXT[label])
    d.kv([
        ("資料截止", f"{_tw(report['cutoff_at'])}（台北時間）"),
        ("報告版本", f"{version['report_version_id']}（第 {version['version_no']} 版）"),
        ("報告 hash", version["report_hash"]),
        ("核准", f"{version.get('approved_by') or '—'}・{_tw(version.get('approved_at'))}"),
        ("快照", report.get("source_snapshot_id")),
        ("模型／prompt", f"{report.get('model_id') or '無（MOCK 不呼叫模型）'}・{', '.join(report.get('prompt_versions') or []) or '—'}"),
        ("研究問題", f"截至資料截止，總經、基本面與估值證據支持哪些觀察？有哪些反向證據、假設與待確認訊號？（{report.get('question_version')}）"),
    ])
    if data.get("scope_note"):
        d.banner(data["scope_note"], MUTED)

    # ---- status: valuation + data quality
    v, dq = data.get("valuation") or {}, data.get("data_quality") or {}
    d.heading("估值狀態與資料品質")
    gap = f"（DCF 每股 {_num(v.get('dcf_per_share'))} 元，與同日收盤價差距 {_pct(v.get('gap'))}）" if v.get("gap") is not None \
        else f"：{v.get('reason') or ''}"
    d.text(f"估值狀態：{v.get('label') or '無法判定'}{gap}", 10.5, True)
    d.text(f"基準收盤價：{_price_text(data.get('price'))}", 9.5)
    d.text(f"{dq.get('label') or '資料品質風險：未評估'}　{'；'.join(dq.get('reasons') or [])}", 10.5, True,
           RED if dq.get("level") == "high" else INK)
    d.text((data.get("method") or {}).get("valuation_footnote", ""), 8.5, color=MUTED)
    d.text((data.get("method") or {}).get("risk_footnote", ""), 8.5, color=MUTED)

    # ---- claims
    d.heading("主張（事實／推論／未知）")
    for c in report.get("claims") or []:
        d.text(f"{c.get('claim_id')}｜{KIND_TEXT.get(c.get('kind'), c.get('kind'))}　{c.get('text')}", 10, h=5.8)
        d.text(f"　來源：{', '.join(c.get('evidence_refs') or []) or '無（不能當作事實）'}", 8.5, color=MUTED)
        for lim in c.get("limitations") or []:
            d.text(f"　限制：{lim}", 8.5, color=MUTED)
    for title, key in (("總經觀察", "macro_observations"), ("基本面觀察", "fundamental_observations"),
                       ("估值情境", "valuation_scenarios"), ("反向證據與矛盾", "conflicts"), ("負面因素", "negative_channels"), ("正面因素", "positive_channels"),
                       ("未知事項", "unknowns"), ("下一個確認訊號", "next_signals")):
        items = report.get(key) or []
        if items:
            d.text(title, 10, True, TEAL)
            for it in items:
                d.text(f"・{it if isinstance(it, str) else json.dumps(it, ensure_ascii=False)}", 9.5)

    # ---- quarterly data
    d.heading("季度資料（億元；EPS 元）")
    quarters = data.get("quarters")
    if quarters:
        d.table(["財報期", "營收", "營業利益", "淨利", "EPS（來源）", "FCF", "可得時間"],
                [[q["period"], _num(q["revenue"]), _num(q["operating_income"]), _num(q["net_income"]),
                  f"{_num(q['eps'])}（{EPS_SOURCE.get(q.get('eps_source'), q.get('eps_source') or '—')}）",
                  _num(q["free_cash_flow"]), _tw(q["available_at"])]
                 for q in quarters], [16, 22, 21, 20, 32, 20, 33])
        ttm = data.get("ttm") or {}
        d.text(f"TTM（{'、'.join(ttm.get('periods') or []) or 'NA'}）：EPS {_num(ttm.get('eps_ttm'))} 元；FCF {_num(ttm.get('fcf_ttm'))} 億元。"
               "FCF = 營業現金流 − 正值資本支出。單季數字不是年度數字。", 8.5, color=MUTED)
    else:
        d.text(f"NA：{data.get('quarters_na_reason') or '無季度資料'}", 9.5, color=MUTED)

    # ---- DCF + sensitivity
    d.heading("DCF 假設與敏感度")
    a = (data.get("method") or {}).get("dcf_assumptions") or {}
    det = v.get("dcf_detail")
    d.text(f"WACC {_pct(a.get('wacc'))}、g {_pct(a.get('terminal_growth'))}、{a.get('fcf_basis', '')}。{a.get('source', '')}", 9)
    if det:
        d.text(f"5 年 FCF 現值 {_num(det['pv_fcf_total'])}；終端價值現值 {_num(det['pv_terminal'])}；企業價值 {_num(det['enterprise_value'])}；"
               f"淨負債 {_num(det['net_debt'])}；股東權益 {_num(det['equity_value'])}（億元）；流通股數 {_num(det['shares_outstanding_m'])} 百萬股。", 9)
    sens = v.get("sensitivity")
    if sens:
        gs = list(next(iter(sens.values())).keys())
        d.table(["WACC＼g", *gs], [[w, *[_num(sens[w][g]) for g in gs]] for w in sens], [40, 40, 40, 40], 9)
    elif v.get("reason"):
        d.text(f"不計算 DCF：{v['reason']}", 9.5, color=MUTED)

    # ---- peer comparison (2454 only)
    d.heading("同業比較")
    peer = data.get("peer_comparison")
    if peer:
        role = {"subject": "主體", "peer": "同業", "industry_reference": "產業參照（不入平均）"}
        rows, shade = [], set()
        for i, r in enumerate(peer["rows"]):
            m = r["metrics"]
            if r["role"] == "industry_reference":
                shade.add(i)
            rows.append([f"{r['ticker']} {r.get('name') or ''}\n{role.get(r['role'], r['role'])}",
                         f"{r['financial_period']}\n{_num((r.get('price') or {}).get('value'))}",
                         _num(m["pe_ttm"]["value"]), _num(m["pb"]["value"]), _pct(m["revenue_yoy_quarter"]["value"]),
                         _num(m["fcf_ttm"]["value"], 1), _pct(m["dcf_gap"]["value"]), r["valuation"]["label"]])
        d.table(["公司（角色）", "財報期／收盤", "P/E", "P/B", "單季營收 YoY", "FCF TTM", "DCF 差距", "估值狀態"],
                rows, [36, 24, 15, 15, 21, 21, 20, 28], 8, shade)
        ps = peer["peer_stats"]
        d.text(f"同業平均（只用 2379、3034）：P/E {_num(ps['pe_ttm']['value'])}、P/B {_num(ps['pb']['value'])}、"
               f"單季營收 YoY {_pct(ps['revenue_yoy_quarter']['value'])}；排除 {'、'.join(ps['excluded'])}。報價基準日 {peer['price_as_of']}。", 8.5, color=MUTED)
    else:
        d.text(f"不適用：{data.get('peer_na_reason') or '—'}", 9.5, color=MUTED)

    # ---- charts (existing chart types)
    if data.get("price_window_na_reason"):
        d.text(f"價格圖：NA，{data['price_window_na_reason']}", 9, color=MUTED)
    with tempfile.TemporaryDirectory() as tmp:
        for title, path in _charts(data, report["ticker"], Path(tmp)):
            if d.pdf.get_y() > 175:
                d.pdf.add_page()
            d.text(title, 10, True, TEAL)
            d.pdf.image(path, w=128, x=(210 - 128) / 2)
            d.pdf.ln(2)

    # ---- review
    d.heading("覆核")
    review = report.get("review") or {}
    d.text(f"決定：{review.get('decision')}　{review.get('decision_summary') or ''}", 9.5)
    d.text(f"已核對來源：{', '.join(review.get('checked_refs') or []) or '無'}　已核對指標：{', '.join(review.get('checked_metric_ids') or []) or '無'}", 8.5, color=MUTED)
    b = report.get("budget") or {}
    d.text(f"預算使用：模型請求 {b.get('calls_used')}/8、工具 {b.get('tool_calls_used')}/10、補查 {b.get('supplement_rounds')}/2", 8.5, color=MUTED)

    # ---- sources
    d.heading("來源")
    for s in data.get("sources") or []:
        if s.get("resolved") and s.get("kind") == "financial_snapshot":
            d.text(f"{s['id']}　財報快照（工具結果）　可得 {_tw(s.get('available_at'))}　原始檔 {s.get('source_id')}　"
                   f"sha256 {str(s.get('content_hash'))[:16]}…", 8.5, True)
            d.text(s.get("excerpt"), 8.5, color=MUTED)
        elif s.get("resolved"):
            d.text(f"{s['id']}　可得 {_tw(s.get('available_at'))}　sha256 {str(s.get('content_hash'))[:16]}…"
                   f"{'（相符）' if s.get('hash_match') else '（不符，待 B 核對）'}", 8.5, True)
            d.text(s.get("excerpt"), 8.5, color=MUTED)
            d.link_line("原始來源：", s.get("source_url"))
        else:
            d.text(f"{s['id']}　無法解析：{s.get('reason')}", 8.5, color=RED)

    # ---- limitations + disclaimer (never cut: always last, always present)
    d.heading("方法與限制")
    m = data.get("method") or {}
    for lim in (report.get("limitations") or []) + (m.get("limitations") or []):
        d.text(f"・{lim}", 9.5)
    d.text(f"方法版本：{m.get('data_version')}；{m.get('risk_method')}；{m.get('tools_version')}。網站與本 PDF 由同一份核准 JSON 產生。", 8.5, color=MUTED)
    d.text(report.get("disclaimer") or "", 10, True)

    pages = d.pdf.page_no()
    if pages > MAX_PDF_PAGES:
        raise PublicationError(f"PDF {pages} 頁，超過 {MAX_PDF_PAGES} 頁上限")
    out = bytes(d.pdf.output())
    if len(out) > MAX_PDF_BYTES:
        raise PublicationError("PDF 超過 5MB 上限")
    return out
