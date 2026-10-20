"""Records the oracle chamber (dev tool): Georgian UI, 390x844, demo build, FULL tier unless a scene says LITE.

    python -m scripts.build_frontend
    python -m scripts.chamber_videos                 # every scene -> dist/motion/chamber/*.webm
    python -m scripts.chamber_videos tour tarot      # only some scenes
    python -m scripts.chamber_videos --shots         # screenshots of every station -> dist/screens/chamber/

Swipes are real pointer drags, so inertia and the settle are what a finger produces.
"""
import shutil
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

from scripts.chamber_check import ARGS
from scripts.perf_probe import DIST, serve

OUT = DIST / "motion" / "chamber"
SHOTS = DIST / "screens" / "chamber"
VP = {"width": 390, "height": 844}


def swipe(page, dx, dy=0, steps=14, y=520):
    x0 = 195 - dx / 2
    page.mouse.move(x0, y)
    page.mouse.down()
    for i in range(1, steps + 1):
        page.mouse.move(x0 + dx * i / steps, y + dy * i / steps)
        page.wait_for_timeout(16)
    page.mouse.up()


def tap(page, x, y):
    page.mouse.move(x, y)
    page.mouse.down()
    page.wait_for_timeout(60)
    page.mouse.up()


def back(page):
    page.evaluate("window.__astro.back()")


def scene_tour(page):
    """First visit: the guided intro, then a walk round the room, the dome, the compass, one panel."""
    page.wait_for_timeout(2600)
    for _ in range(3):
        page.click("#chIntroNext")
        page.wait_for_timeout(2400)
    page.wait_for_timeout(1200)
    for _ in range(4):
        swipe(page, -170)
        page.wait_for_timeout(1500)
    swipe(page, 330, steps=10)
    page.wait_for_timeout(1800)
    swipe(page, 0, -220)
    page.wait_for_timeout(2600)
    swipe(page, 0, 220)
    page.wait_for_timeout(1800)
    page.click("#chCompassBtn")
    page.wait_for_timeout(2000)
    page.click("#chList .ch-item[data-id='moon']")
    page.wait_for_timeout(3600)
    page.evaluate("document.getElementById('scroller').scrollTo({ top: 400, behavior: 'smooth' })")
    page.wait_for_timeout(1800)
    back(page)
    page.wait_for_timeout(2600)


def dbg(page):
    return page.evaluate("window.__chamber.state.stage && window.__chamber.state.stage.debug()")


def drag(page, a, b, steps=16):
    page.mouse.move(a[0], a[1])
    page.mouse.down()
    for i in range(1, steps + 1):
        page.mouse.move(a[0] + (b[0] - a[0]) * i / steps, a[1] + (b[1] - a[1]) * i / steps)
        page.wait_for_timeout(18)
    page.mouse.up()


def tarot_flow(page, three):
    page.evaluate("window.__chamber.open('tarot')")
    page.wait_for_timeout(2600)
    if three:
        page.click(".ch-hud .seg button[data-v='three']")
        page.wait_for_timeout(900)
        page.fill(".ch-q", "რა მელის ამ თვეში?")
        page.wait_for_timeout(600)
    d = dbg(page)["deck"]
    drag(page, (d["x"] - 90, d["y"]), (d["x"] + 90, d["y"]))      # a swipe across the deck: the riffle
    page.wait_for_timeout(2600)
    for _ in range(3 if three else 1):
        fan = dbg(page)["fan"]
        c = fan[len(fan) // 2]
        drag(page, (c["x"], c["y"]), (c["x"], c["y"] - 150), steps=18)
        page.wait_for_timeout(1300)
    page.wait_for_timeout(2600)                                   # the server draws, the cards shimmer
    for s in dbg(page)["slots"]:
        drag(page, (s["x"], s["y"] + 30), (s["x"], s["y"] - 60), steps=14)   # turned over by hand
        page.wait_for_timeout(1500)
    page.wait_for_timeout(4200)
    page.evaluate("document.getElementById('scroller').scrollTo({ top: 520, behavior: 'smooth' })")
    page.wait_for_timeout(2600)


def scene_tarot(page):
    tarot_flow(page, three=True)


def scene_tarot_reversed(page):
    tarot_flow(page, three=False)


def scene_sphere(page):
    page.evaluate("window.__chamber.open('sphere')")
    page.wait_for_function("window.__chamber.state.stage && window.__chamber.state.stage.debug")
    page.wait_for_timeout(1400)
    page.fill(".ch-q", "გამიმართლებს ხვალ?")
    page.wait_for_timeout(900)
    b = dbg(page)["ball"]
    page.mouse.move(b["x"] - 50, b["y"] - 30)
    page.mouse.down()
    import math
    for i in range(70):                                            # a finger wiping round and round
        a = i / 6
        page.mouse.move(b["x"] + math.cos(a) * 55, b["y"] + math.sin(a) * 40)
        page.wait_for_timeout(22)
    page.mouse.up()
    page.wait_for_timeout(6500)


def scene_gift(page):
    page.evaluate("window.__chamber.open('gift')")
    page.wait_for_function("window.__chamber.state.stage && window.__chamber.state.stage.debug")
    page.wait_for_timeout(1600)
    c = dbg(page)["chest"]
    page.mouse.click(c["x"], c["y"])
    page.wait_for_timeout(5200)


def scene_horoscope(page):
    page.wait_for_timeout(1200)
    swipe(page, 0, -220)                                           # look up at the dome: today's real sky
    page.wait_for_timeout(2600)
    page.evaluate("window.__chamber.open('horo')")
    page.wait_for_function("window.__chamber.state.stage && window.__chamber.state.stage.debug && window.__chamber.state.stage.debug().n > 0", timeout=15000)
    page.wait_for_timeout(4200)                                    # the wheel opens, the transits glide in, the beams light
    for i in (1, 0):
        b = dbg(page)["beams"][i]
        page.mouse.click(b["x"], b["y"])
        page.wait_for_timeout(3600)
        page.evaluate("document.getElementById('scroller').scrollTo({ top: 360, behavior: 'smooth' })")
        page.wait_for_timeout(2200)
        page.click("#chPClose")                                     # back to the wheel
        page.wait_for_timeout(1800)
    page.click(".ch-hud .seg button[data-v='week']")
    page.wait_for_timeout(4200)
    page.click(".ch-hud-foot .btn")
    page.wait_for_timeout(4500)
    page.evaluate("document.getElementById('scroller').scrollTo({ top: 700, behavior: 'smooth' })")
    page.wait_for_timeout(2500)


SCENES = {"chamber-tour": (scene_tour, {"intro": True}), "chamber-horoscope": (scene_horoscope, {}), "chamber-tarot": (scene_tarot, {}),
          "chamber-tarot-reversed": (scene_tarot_reversed, {"query": "&rev=tower"}), "chamber-sphere": (scene_sphere, {}),
          "chamber-gift": (scene_gift, {})}


def make_context(browser, opts, tmp=None):
    kw = {"viewport": VP, "is_mobile": True, "has_touch": True}
    if tmp:
        kw.update(record_video_dir=str(tmp), record_video_size=VP)
    ctx = browser.new_context(**kw)
    init = "try { localStorage.setItem('astro.lang', 'ka');" + ("" if opts.get("intro") else " localStorage.setItem('astro.chIntro', '1');") + " } catch (e) {}"
    ctx.add_init_script(init)
    return ctx


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    want = [a for a in sys.argv[1:] if not a.startswith("--")]
    httpd = serve()
    base = f"http://127.0.0.1:{httpd.server_address[1]}/preview.html?ui=chamber"
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="chrome", headless=True, args=ARGS)
        if "--shots" in sys.argv:
            shots(browser, base)
        else:
            OUT.mkdir(parents=True, exist_ok=True)
            tmp = OUT / "_raw"
            for name, (scene, opts) in SCENES.items():
                if want and not any(w in name for w in want):
                    continue
                ctx = make_context(browser, opts, tmp)
                page = ctx.new_page()
                page.goto(f"{base}&tier={opts.get('tier', 'full')}{opts.get('query', '')}")
                page.wait_for_function("window.__chamber && document.getElementById('splash').hidden", timeout=30000)
                scene(page)
                video = page.video.path()
                ctx.close()
                dest = OUT / f"{name}.webm"
                shutil.move(video, dest)
                print(f"{dest.relative_to(DIST.parent)}: {dest.stat().st_size // 1024} KB")
            shutil.rmtree(tmp, ignore_errors=True)
        browser.close()
    httpd.shutdown()


def shots(browser, base):
    """A screenshot of the room facing each object, of each open panel, of the dome and the compass, both tiers."""
    SHOTS.mkdir(parents=True, exist_ok=True)
    for tier in ("full", "lite"):
        ctx = make_context(browser, {})
        page = ctx.new_page()
        page.goto(f"{base}&tier={tier}")
        page.wait_for_function("window.__chamber && document.getElementById('splash').hidden", timeout=30000)
        page.wait_for_timeout(1500)
        ids = page.evaluate("window.__chamber.STATIONS.map((s) => s.id)")
        for i, sid in enumerate(ids):
            page.evaluate(f"window.__chamber.turn({i})")
            page.wait_for_timeout(1400)
            page.screenshot(path=str(SHOTS / f"{tier}-{i:02d}-{sid}-room.png"))
            page.evaluate(f"window.__chamber.open('{sid}')")
            page.wait_for_timeout(2600)
            page.screenshot(path=str(SHOTS / f"{tier}-{i:02d}-{sid}-open.png"))
            back(page)
            page.wait_for_timeout(1500)
        page.evaluate("window.__chamber.up(true)")
        page.wait_for_timeout(1800)
        page.screenshot(path=str(SHOTS / f"{tier}-10-dome.png"))
        page.evaluate("window.__chamber.open('horo')")
        page.wait_for_timeout(2600)
        page.screenshot(path=str(SHOTS / f"{tier}-10-dome-open.png"))
        back(page)
        page.wait_for_timeout(1500)
        page.evaluate("window.__chamber.compass()")
        page.wait_for_timeout(800)
        page.screenshot(path=str(SHOTS / f"{tier}-11-compass.png"))
        ctx.close()
        print(f"{tier}: screenshots in {SHOTS.relative_to(DIST.parent)}")


if __name__ == "__main__":
    main()
