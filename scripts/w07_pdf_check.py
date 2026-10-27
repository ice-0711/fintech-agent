"""W07-A layout check for the acceptance PDFs (reports/v12-online-pdf). Offline, 0 LLM.

For each PDF: pages, bytes, embedded fonts, link and image counts, and whether every key item of
its approved JSON appears in the extracted PDF text (nothing truncated). Also renders each page to
PNG (reports/v12-online-pdf/pages/) for the visual check. Prints a Markdown table.

    python scripts/w07_pdf_check.py
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT / "reports" / "v12-online-pdf"
sys.path.insert(0, str(ROOT))

from agents.publication import MAX_PDF_BYTES, MAX_PDF_PAGES  # noqa: E402


def norm(s: str) -> str:
    return "".join(str(s).split())


def required_items(rep: dict) -> dict[str, str]:
    d = rep["data"]
    items = {"免責聲明": rep["disclaimer"], "估值狀態": d["valuation"]["label"],
             "資料品質風險": d["data_quality"]["label"]}
    for c in rep["claims"]:
        items[f"主張 {c['claim_id']}"] = c["text"]
    for i, lim in enumerate((rep.get("limitations") or []) + d["method"]["limitations"]):
        items[f"限制 {i + 1}"] = lim
    for q in d.get("quarters") or []:
        items[f"季度 {q['period']} 營收"] = f"{q['revenue']:,.2f}"
    if d["valuation"].get("dcf_per_share") is not None:
        items["DCF 每股"] = f"{d['valuation']['dcf_per_share']:,.2f}"
    for s in d["sources"]:
        items[f"來源 {s['id']}"] = s["id"]
    if d.get("peer_comparison"):
        for r in d["peer_comparison"]["rows"]:
            items[f"同業 {r['ticker']}"] = r["ticker"]
    return items


def main() -> None:
    manifest = json.loads((DIR / "manifest.json").read_text(encoding="utf-8"))
    pages_dir = DIR / "pages"
    pages_dir.mkdir(exist_ok=True)
    rows, problems = [], []
    for v in manifest["versions"]:
        pdf = (DIR / v["pdf_file"]).read_bytes()
        rep = json.loads((DIR / v["json_file"]).read_text(encoding="utf-8"))
        doc = pymupdf.open(stream=pdf, filetype="pdf")
        text = norm("".join(p.get_text() for p in doc))
        fonts = sorted({f[3] for p in doc for f in p.get_fonts()})
        links = [lk["uri"] for p in doc for lk in p.get_links() if lk.get("uri")]
        images = sum(len(p.get_images()) for p in doc)
        items = required_items(rep)
        missing = [k for k, val in items.items() if norm(val) not in text]
        hash_ok = hashlib.sha256(pdf).hexdigest() == v["pdf_hash"]
        for i, page in enumerate(doc):
            page.get_pixmap(dpi=60).save(pages_dir / f"{v['ticker']}-p{i + 1}.png")
        ok = doc.page_count <= MAX_PDF_PAGES and len(pdf) <= MAX_PDF_BYTES and not missing and hash_ok
        rows.append(f"| {v['ticker']} | `{v['report_version_id']}` | {doc.page_count} | {len(pdf) / 1024:,.0f} KB | "
                    f"{', '.join(fonts)} | {len(links)} | {images} | {len(items) - len(missing)}/{len(items)} | "
                    f"{'相符' if hash_ok else '不符'} | {'通過' if ok else '不通過'} |")
        if missing:
            problems.append(f"{v['ticker']} 缺：{', '.join(missing)}")
    print("| 股票 | 版本 | 頁數 | 大小 | 內嵌字型 | 連結 | 圖 | JSON 關鍵項目在 PDF 內 | PDF hash | 結果 |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    print("\n".join(rows))
    print("\n" + ("\n".join(problems) if problems else "沒有缺漏或截斷的關鍵項目。"))


if __name__ == "__main__":
    main()
