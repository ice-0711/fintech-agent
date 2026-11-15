"""Screenshots and a short clip of the three demo-path REPLAYs (research_ui.replays.DEMO_PATHS), local app.

    python scripts/replay_demo_media.py --base http://127.0.0.1:5109 --shots media/w10 --video tmp/replay-video

Real screen of the local app (Playwright, Chromium), labelled REPLAY / 本機 in the manifest. After recording, add
the caption bar with scripts/w09_record_sample.caption(). Read-only: replays never call a model.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from research_ui.replays import DEMO_PATHS  # noqa: E402

SLUG = {"示範：正常通過": "pass", "示範：覆核要求補查後修正通過": "revise-pass", "示範：資料不足停止": "insufficient"}


def shots(base: str, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        br = p.chromium.launch()
        for w, h in ((1440, 900), (390, 844)):
            mobile = w < 768
            pg = br.new_page(viewport={"width": w, "height": h}, device_scale_factor=2, is_mobile=mobile,
                             has_touch=mobile)
            for i, (rid, label) in enumerate(DEMO_PATHS.items(), 1):
                pg.goto(f"{base}/research?replay={rid}")
                pg.wait_for_timeout(2500)
                stem = f"a-demo{i}-{SLUG[label]}-{rid.split(':')[1].lower()}"
                pg.locator("section.o2").screenshot(path=str(out / f"{stem}-status-{w}.png"))
                pg.locator("#reviewSection").screenshot(path=str(out / f"{stem}-review-{w}.png"))
            pg.close()
        br.close()


def video(base: str, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    marks: list[dict] = []
    with sync_playwright() as p:
        br = p.chromium.launch()
        ctx = br.new_context(viewport={"width": 1280, "height": 720}, record_video_dir=str(out),
                             record_video_size={"width": 1280, "height": 720})
        pg = ctx.new_page()
        t0 = time.monotonic()

        def mark(text: str) -> None:
            marks.append({"t": round(time.monotonic() - t0, 2), "text": text})

        def show(sel: str, ms: int) -> None:
            pg.evaluate("s => { const el = document.querySelector(s); window.scrollTo({ top: el.getBoundingClientRect()"
                        ".top + scrollY - 8, behavior: 'smooth' }); }", sel)
            pg.wait_for_timeout(ms)

        pg.goto(base + "/research")
        pg.wait_for_timeout(2500)
        mark("回放清單：依 Agent 版本與題目條件分組，示範用的三筆標 ★")
        pg.locator("#replaySelect").scroll_into_view_if_needed()
        pg.wait_for_timeout(3500)
        for rid, label in DEMO_PATHS.items():
            case = rid.split(":")[1]
            pg.evaluate("window.scrollTo(0,0)")
            pg.select_option("#replaySelect", rid)
            pg.wait_for_timeout(700)
            pg.click("#replayOpen")
            pg.wait_for_timeout(1500)
            mark(f"REPLAY {case}（{label.replace('示範：', '')}）：版本、條件、資料截止、預算計數")
            show("#jobPanel", 6000)
            mark(f"REPLAY {case}：覆核紀錄與草稿")
            show("#reviewSection", 7000)
        mark("end")
        ctx.close()
        br.close()
    (out / "marks.json").write_text(json.dumps(marks, ensure_ascii=False, indent=1), encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--shots")
    ap.add_argument("--video")
    a = ap.parse_args()
    if a.shots:
        shots(a.base, Path(a.shots))
    if a.video:
        video(a.base, Path(a.video))


if __name__ == "__main__":
    main()
