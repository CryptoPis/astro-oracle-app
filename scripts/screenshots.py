"""Screenshots of every screen of dist/preview.html (dev tool, not used by the server).

    pip install playwright
    python -m scripts.build_frontend
    python -m scripts.screenshots [--langs ka,en,ru] [--devices phone,desktop] [--full]

Saves PNGs to dist/shots/<device>-<lang>-<screen>.png and prints console errors (exit code 1 if any).
--full also saves the whole scrollable content of each screen (…-full.png).
"""
import argparse
import sys

from playwright.sync_api import sync_playwright

from scripts.perf_probe import serve, DIST

DEVICES = {"phone": ({"width": 390, "height": 844}, 3, True), "desktop": ({"width": 1280, "height": 800}, 1, False)}
SCREENS = ["home", "horo", "tarot", "tarot-drawn", "dream", "dream-read", "profile", "num", "sphere", "moon", "compat",
           "advisor", "aura", "coffee", "kundli"]
UNSCROLL = ("html,body{overflow:visible!important;height:auto!important}"
            "#scroller{position:static!important;overflow:visible!important;contain:none!important}")


def shoot(page, path, full):
    page.screenshot(path=str(path))
    if full:
        tag = page.add_style_tag(content=UNSCROLL)
        page.screenshot(path=str(path).replace(".png", "-full.png"), full_page=True)
        tag.evaluate("n => n.remove()")


def open_screen(page, name):
    go = lambda v: page.evaluate(f"window.__astro.go('{v}')")
    if name == "tarot-drawn":
        go("tarot")
        page.wait_for_timeout(900)
        page.click("#drawBtn")
        page.wait_for_timeout(5200)
    elif name == "dream-read":
        go("dream")
        page.fill("#dreamText", "I was flying over a silver lake at night and a white owl followed me.")
        page.click("#dreamBtn")
        page.wait_for_timeout(2600)
    elif name == "sphere":
        go("sphere")
        page.wait_for_timeout(400)
        page.click("#sphereBtn")
        page.wait_for_timeout(2600)
    elif name == "compat":
        go("compat")
        page.fill("#partnerDate", "1995-03-14")
        page.click("#compatForm button")
        page.wait_for_timeout(2400)
    elif name == "advisor":
        go("advisor")
        page.wait_for_timeout(300)
        page.click("#askChips button")
        page.wait_for_timeout(2600)
    else:
        go(name)
        page.wait_for_timeout(2200)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--langs", default="ka,en,ru")
    ap.add_argument("--devices", default="phone,desktop")
    ap.add_argument("--screens", default=",".join(SCREENS))
    ap.add_argument("--full", action="store_true")
    a = ap.parse_args()
    out = DIST / "shots"
    out.mkdir(parents=True, exist_ok=True)
    httpd = serve()
    base = f"http://127.0.0.1:{httpd.server_address[1]}/preview.html"
    errors = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="chrome", headless=True)
        for dev in a.devices.split(","):
            vp, dpr, mobile = DEVICES[dev]
            for lang in a.langs.split(","):
                ctx = browser.new_context(viewport=vp, device_scale_factor=dpr, is_mobile=mobile, has_touch=mobile)
                ctx.add_init_script(f"try {{ localStorage.setItem('astro.lang', '{lang}') }} catch (e) {{}}")
                page = ctx.new_page()
                tag = f"{dev}-{lang}"
                page.on("pageerror", lambda e, tag=tag: errors.append(f"{tag}: {e}"))
                page.on("console", lambda m, tag=tag: m.type == "error" and "404" not in m.text and errors.append(f"{tag}: {m.text}"))
                # cold start, server down, onboarding
                page.goto(base + "?cold=hold")
                page.wait_for_timeout(4200)
                page.screenshot(path=str(out / f"{tag}-splash.png"))
                page.goto(base + "?cold=down")
                page.wait_for_timeout(11500)
                page.screenshot(path=str(out / f"{tag}-splash-down.png"))
                page.goto(base + "?new=1")
                page.wait_for_timeout(1800)
                page.screenshot(path=str(out / f"{tag}-onboarding.png"))
                page.goto(base)
                page.wait_for_timeout(2200)
                for name in a.screens.split(","):
                    open_screen(page, name)
                    shoot(page, out / f"{tag}-{name}.png", a.full)
                    if name == "home":
                        page.click("#giftBtn")   # reward toast + coin counter
                        page.wait_for_timeout(500)
                        page.screenshot(path=str(out / f"{tag}-toast.png"))
                ctx.close()
        browser.close()
    httpd.shutdown()
    print(f"saved to {out}")
    if errors:
        print("console errors:\n  " + "\n  ".join(errors))
        sys.exit(1)
    print("no console errors")


if __name__ == "__main__":
    main()
