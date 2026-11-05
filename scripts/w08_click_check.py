"""W08-A: browser check of the public read paths (Playwright, Chromium).

    python scripts/w08_click_check.py --base http://127.0.0.1:5093 --counts COUNTS.json \
        --out performance/v12-click-check.json --shots design/w08

1. Open /research (1440×900 and 390×844). Click the three tickers 5 rounds in a row → record every request.
2. Open each published report 5 times in a row → only GET /api/ui/reports/<rv>; no POST, no /api/analyze.
3. Download a PDF twice and open a source drawer; check the PDF buttons and the drawer are not covered
   (document.elementFromPoint at their centre is the element itself).
4. Slow / failing server (requests delayed or aborted by the test): the page says it is waiting, then offers
   retry, instead of looking frozen.
Server counters (model requests, full-statement fetches, outbound connections) must not move.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from playwright.sync_api import sync_playwright


def uncovered(page, selector: str) -> bool:
    return page.eval_on_selector(selector, """el => { const r = el.getBoundingClientRect();
        const hit = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
        return !!hit && (hit === el || el.contains(hit)); }""")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--counts", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--shots", required=True)
    a = ap.parse_args()
    shots = Path(a.shots)
    shots.mkdir(parents=True, exist_ok=True)
    counts = lambda: json.loads(Path(a.counts).read_text(encoding="utf-8"))  # noqa: E731
    before = counts()
    result: dict = {"viewports": {}}
    with sync_playwright() as pw:
        browser = pw.chromium.launch(args=["--no-proxy-server"])
        for name, vp in (("1440", {"width": 1440, "height": 900}), ("390", {"width": 390, "height": 844})):
            ctx = browser.new_context(viewport=vp, accept_downloads=True, locale="zh-TW", timezone_id="Asia/Taipei")
            page = ctx.new_page()
            reqs: list[dict] = []
            errors: list[str] = []
            page.on("request", lambda r: reqs.append({"method": r.method, "url": r.url.replace(a.base, "")}))
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.goto(f"{a.base}/research", wait_until="networkidle")
            page.wait_for_selector(".report-card .btn-link")
            load_reqs = list(reqs)
            reqs.clear()
            for _ in range(5):  # step 1: switch tickers quickly
                for code in ("2330", "2317", "2454"):
                    page.click(f'label[for="t{code}"]')
                    page.wait_for_timeout(80)
            page.wait_for_timeout(800)
            ticker_reqs = list(reqs)
            reqs.clear()
            real = page.eval_on_selector_all(".report-card", "els => els.map(e => e.dataset.report).filter(r => !r.includes('fixture'))")
            for _ in range(5):  # step 2: open each published report 5 times in a row
                for rv in real:
                    page.click(f'.report-card[data-report="{rv}"] [data-open-report]')
                    page.wait_for_timeout(120)
            page.wait_for_timeout(1500)
            page.wait_for_selector("#reportPanel .claim")
            report_reqs = list(reqs)
            reqs.clear()
            pdf_ok = uncovered(page, "#reportPanel a[download]")
            downloads = []
            for _ in range(2):
                with page.expect_download() as d:
                    page.click("#reportPanel a[download]")
                path = d.value.path()
                downloads.append({"file": d.value.suggested_filename, "bytes": Path(path).stat().st_size,
                                  "head": Path(path).read_bytes()[:5].decode("latin-1")})
            page.click("#reportPanel [data-evidence]")
            page.wait_for_selector("#drawerBody .quote")
            drawer_ok = uncovered(page, "#drawerBody .quote")
            page.screenshot(path=str(shots / f"W08-report-drawer-{name}.png"))
            page.click("#drawerClose")
            pdf_reqs = list(reqs)
            result["viewports"][name] = {
                "page_load_requests": load_reqs,
                "ticker_switch_15_clicks_requests": ticker_reqs,
                "open_report_clicks": len(real) * 5,
                "open_report_requests": report_reqs,
                "pdf_and_source_requests": pdf_reqs,
                "downloads": downloads,
                "pdf_button_uncovered": pdf_ok, "source_drawer_uncovered": drawer_ok,
                "posts_or_analyze": [r for r in load_reqs + ticker_reqs + report_reqs + pdf_reqs
                                     if r["method"] != "GET" or "/api/analyze" in r["url"]],
                "page_errors": errors,
            }
            ctx.close()

        # step 4: slow and failing server, as seen by the page
        ctx = browser.new_context(viewport={"width": 1440, "height": 900}, locale="zh-TW", timezone_id="Asia/Taipei")
        page = ctx.new_page()
        fail = {"n": 0}

        held: list = []

        def slow(route):  # hold the request; it is released from the main loop after 6 s
            held.append(route)

        def flaky(route):
            fail["n"] += 1
            if fail["n"] <= 1:
                route.fulfill(status=503, content_type="text/html", body="<html>Service Unavailable</html>")
            else:
                route.continue_()

        page.route("**/api/ui/published", slow)
        page.goto(f"{a.base}/research", wait_until="domcontentloaded")
        page.wait_for_timeout(6500)
        slow_status = page.inner_text("#pageStatus")
        page.screenshot(path=str(shots / "W08-slow-server-1440.png"))
        for route in held:
            route.continue_()
        page.wait_for_selector(".report-card", timeout=30000)
        page.wait_for_timeout(300)
        after_slow = page.inner_text("#pageStatus")
        page.unroute("**/api/ui/published")
        page.route("**/api/ui/comparison/2454", flaky)
        page.reload(wait_until="domcontentloaded")
        page.wait_for_selector("#comparisonPanel .error-box", timeout=15000)
        fail_text = page.inner_text("#comparisonPanel")
        page.locator("#comparisonSection").screenshot(path=str(shots / "W08-retry-after-503-1440.png"))
        page.click('[data-retry="comparison"]')
        page.wait_for_selector("#comparisonPanel .cmp-table", timeout=15000)
        result["slow_server"] = {"status_after_6s": slow_status, "status_after_load": after_slow,
                                 "first_503_text": fail_text, "recovered_after_retry": True}
        ctx.close()
        browser.close()
    after = counts()
    result["server_counters_delta"] = {k: after[k] - before[k] for k in
                                       ("model_generate_content", "model_client_created", "gemini_adapter_created",
                                        "full_statement_fetch", "outbound_connections")}
    Path(a.out).write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    for name, v in result["viewports"].items():
        print(name, "load", len(v["page_load_requests"]), "ticker", len(v["ticker_switch_15_clicks_requests"]),
              "report", len(v["open_report_requests"]), "/", v["open_report_clicks"], "posts", v["posts_or_analyze"],
              "dl", v["downloads"], "uncovered", v["pdf_button_uncovered"], v["source_drawer_uncovered"], v["page_errors"])
    print(result["slow_server"])
    print(result["server_counters_delta"])


if __name__ == "__main__":
    main()
