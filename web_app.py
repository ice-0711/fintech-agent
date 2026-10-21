"""Local web dashboard for interactive stock analysis.

Run:
    python web_app.py

Then open http://127.0.0.1:5000. The browser never receives Supabase keys;
all FinMind, Supabase, DCF, chart, and PDF work stays in this Python backend.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from flask import Flask, jsonify, render_template, request, send_from_directory, url_for

from agents.api import bp as research_jobs_bp
from research_ui import bp as research_ui_bp
from financial_analyzer import analyze_financials
from fundamental_uploader import upload_to_supabase
from main import (
    ensure_complete_fundamentals,
    get_supabase_client,
    load_fundamental_data,
    run_analysis,
)
from report_downloader import download_financial_report, fetch_stock_name

ROOT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT_DIR / "output"

app = Flask(__name__)
app.register_blueprint(research_jobs_bp)  # V1.2 research jobs; deny-by-default without RESEARCH_API_TOKEN
app.register_blueprint(research_ui_bp)  # V1.2 research workspace UI (A); job entry is MOCK-only unless RESEARCH_UI_MOCK=1


def output_url(path: str | None) -> str | None:
    """Convert an output file path into a dashboard URL."""

    if not path:
        return None
    file_path = Path(path).resolve()
    try:
        relative = file_path.relative_to(OUTPUT_DIR)
    except ValueError:
        return None
    return url_for("serve_output", filename=relative.as_posix())


def stock_payload(stock_code: str) -> dict[str, Any]:
    """Run the full analysis pipeline and return a JSON-ready payload."""

    stock_code = stock_code.strip()
    if not stock_code:
        raise ValueError("請輸入股票代號。")
    if not stock_code.isdigit():
        raise ValueError("目前網站版先支援台股數字代號，例如 2330、2317、2454。")

    records = download_financial_report(stock_code, years=5)
    if not records:
        raise ValueError(f"FinMind 沒有回傳 {stock_code} 可用財務資料。")

    company = records[-1].get("company") or fetch_stock_name(stock_code)
    analysis = analyze_financials(records, stock_code, company)
    upload_to_supabase(records, analysis)

    run_result = run_analysis(stock_code)
    client = get_supabase_client()
    fundamental = ensure_complete_fundamentals(load_fundamental_data(client, stock_code))
    latest = fundamental["records"][-1]

    return {
        "stock_code": stock_code,
        "company": fundamental.get("company") or company,
        "data_source": fundamental.get("data_source"),
        "latest_year": latest.get("year"),
        "summary": fundamental.get("summary"),
        "strengths": fundamental.get("strengths") or [],
        "risks": fundamental.get("risks") or [],
        "fcf_forecast": run_result["dcf"].get("free_cash_flows") or [],
        "intrinsic_value": run_result["dcf"]["intrinsic_value_per_share"],
        "intrinsic_value_note": run_result["dcf"].get("unavailable_reason"),
        "wacc": run_result["dcf"].get("wacc"),
        "terminal_growth": run_result["dcf"].get("terminal_growth"),
        "charts": [output_url(path) for path in run_result["charts"]],
        "pdf": output_url(run_result.get("pdf")),
    }


@app.get("/")
def index():
    return render_template("dashboard.html")


@app.get("/api/stocks")
def known_stocks():
    client = get_supabase_client()
    rows = client.table("fundamental_data").select("stock_code, company").execute().data or []
    seen: dict[str, str] = {}
    for row in rows:
        code = str(row.get("stock_code") or "").strip()
        if code and code not in seen:
            seen[code] = row.get("company") or code
    return jsonify([
        {"stock_code": code, "company": company}
        for code, company in sorted(seen.items())
    ])


@app.post("/api/analyze")
def analyze_stock():
    payload = request.get_json(silent=True) or {}
    stock_code = str(payload.get("stock_code") or "").strip()
    try:
        return jsonify({"ok": True, "result": stock_payload(stock_code)})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400


@app.get("/output/<path:filename>")
def serve_output(filename: str):
    return send_from_directory(OUTPUT_DIR, filename)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False, use_reloader=False)
