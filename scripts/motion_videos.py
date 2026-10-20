"""Records short screen videos of the motion design (dev tool), Georgian UI, 390×844, full tier.

    python -m scripts.build_frontend
    python -m scripts.motion_videos            # -> dist/motion/*.webm

Scenes: home, tab switch, tarot ritual, tarot with a reversed card (?rev=tower), sphere, horoscope, reward.
Uses the demo build (dist/preview.html), whose readings come from the knowledge base (app/astro_kb).
"""
import shutil
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

from scripts.perf_probe import DIST, serve

OUT = DIST / "motion"
VP = {"width": 390, "height": 844}


def scroll(page, to, steps=12, pause=90):
    start = page.evaluate("document.querySelector('#scroller').scrollTop")
    for i in range(1, steps + 1):
        page.evaluate(f"document.querySelector('#scroller').scrollTop = {start + (to - start) * i / steps}")
        page.wait_for_timeout(pause)


def scene_home(page):
    page.wait_for_timeout(5500)
    scroll(page, 900, 18, 120)
    page.wait_for_timeout(2500)
    scroll(page, 0, 12, 90)
    page.wait_for_timeout(1500)


def scene_tabs(page):
    page.wait_for_timeout(2500)
    for tab in ("horo", "tarot", "dream", "profile", "home"):
        page.click(f"[data-tab={tab}]")
        page.wait_for_timeout(1900)


def scene_tarot(page):
    page.evaluate("window.__astro.go('tarot')")
    page.wait_for_timeout(1800)
    page.click("#spreadSeg [data-spread=three]")
    page.wait_for_timeout(1500)
    for i in (1, 3, 5):
        page.evaluate(f"document.querySelector('#deck .fc:nth-child({i})').click()")   # cards float: never 'stable'
        page.wait_for_timeout(500)
    page.wait_for_timeout(8500)
    scroll(page, 700, 14, 120)
    page.wait_for_timeout(3000)


def scene_tarot_reversed(page):
    """Card of the day, forced to The Tower reversed: the honest, Waite-based reading of a hard card."""
    page.evaluate("window.__astro.go('tarot')")
    page.wait_for_timeout(1800)
    page.evaluate("document.querySelector('#deck .fc:nth-child(3)').click()")
    page.wait_for_timeout(9000)
    scroll(page, 520, 14, 130)
    page.wait_for_timeout(3500)


def scene_sphere(page):
    page.evaluate("window.__astro.go('sphere')")
    page.wait_for_timeout(2500)
    page.fill("#sphereQ", "ვუყვარვარ?")
    page.click("#sphereBtn")
    page.wait_for_timeout(5000)
    page.click("#sphereBtn")
    page.wait_for_timeout(4500)


def scene_horoscope(page):
    page.evaluate("window.__astro.go('horo')")
    page.wait_for_timeout(5000)
    scroll(page, 560, 14, 120)
    page.wait_for_timeout(2500)
    scroll(page, 1300, 14, 120)
    page.wait_for_timeout(2500)


def scene_reward(page):
    page.wait_for_timeout(2500)
    page.evaluate("document.querySelector('#gift').scrollIntoView({block: 'center'})")
    page.wait_for_timeout(1200)
    page.click("#giftBtn")
    page.wait_for_timeout(4000)


SCENES = {"home": scene_home, "tab-switch": scene_tabs, "tarot-ritual": scene_tarot, "tarot-reversed": scene_tarot_reversed,
          "sphere": scene_sphere, "horoscope": scene_horoscope, "reward": scene_reward}
QUERY = {"tarot-reversed": "&rev=tower"}


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    OUT.mkdir(parents=True, exist_ok=True)
    tmp = OUT / "_raw"
    httpd = serve()
    base = f"http://127.0.0.1:{httpd.server_address[1]}/preview.html?tier=full"
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="chrome", headless=True)
        for name, scene in SCENES.items():
            ctx = browser.new_context(viewport=VP, is_mobile=True, has_touch=True, record_video_dir=str(tmp), record_video_size=VP)
            ctx.add_init_script("try { localStorage.setItem('astro.lang', 'ka') } catch (e) {}")
            page = ctx.new_page()
            page.goto(base + QUERY.get(name, ""))
            scene(page)
            video = page.video.path()
            ctx.close()
            dest = OUT / f"{name}.webm"
            shutil.move(video, dest)
            print(f"{dest.name}: {dest.stat().st_size // 1024} KB")
        browser.close()
    httpd.shutdown()
    shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
