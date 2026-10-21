"""Phone-size screenshots of the oracle chamber's FULL room (dev tool, uses the demo build).

    python -m scripts.build_frontend
    python -m scripts.chamber_shots --label after --gfx high medium            # -> dist/screens/chamber-graphics/
    python -m scripts.chamber_shots --label before --dist path/to/other/dist   # e.g. a build of main, no levels

Views: the room between two objects, toward the window, the tarot table, the star dome, a wall with candelabras, the window up close. 390x844 at
device pixel ratio 3 (the chamber caps it per graphics level). Waits for the photographic textures when the build
has them (engine.texReady), so the shots show the final room, not the stand-ins.
"""
import argparse
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

from scripts.chamber_check import ARGS
from scripts.perf_probe import serve

ROOT = Path(__file__).resolve().parent.parent
STEP = 0.6283185
VIEWS = {   # name: (set-up, tear-down); the old builds (no look()) fall back to turning to an object
    "room": (f"(e => e.look ? e.look({-0.5 * STEP}, -0.04) : window.__chamber.turn(0))(window.__chamber.engine)", None),
    "window": ("window.__chamber.turn(2)", None),
    "tarot": ("window.__chamber.turn(0)", None),
    "dome": ("window.__chamber.up(true)", "window.__chamber.up(false)"),
    "candelabras": (f"(e => e.look ? e.look({4.5 * STEP}, 0.06) : window.__chamber.turn(5))(window.__chamber.engine)", None),
    "windowclose": ("window.__chamber.engine.focus('moon', 'stage')", "window.__chamber.engine.unfocus()"),
}


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", required=True)
    ap.add_argument("--gfx", nargs="*", default=[None])
    ap.add_argument("--views", nargs="*", default=None)
    ap.add_argument("--dist", type=Path, default=ROOT / "dist")
    ap.add_argument("--out", type=Path, default=ROOT / "dist" / "screens" / "chamber-graphics")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    httpd = serve(args.dist)
    base = f"http://127.0.0.1:{httpd.server_address[1]}/preview.html?ui=chamber&tier=full"
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="chrome", headless=True, args=ARGS)
        for gfx in args.gfx:
            ctx = browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True, device_scale_factor=3)
            ctx.add_init_script("try { localStorage.setItem('astro.lang', 'en'); localStorage.setItem('astro.chIntro', '1') } catch (e) {}")
            page = ctx.new_page()
            errors = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.on("console", lambda m: errors.append(m.text) if m.type == "error" and "favicon" not in m.text and "404" not in m.text else None)
            page.goto(base + (f"&gfx={gfx}" if gfx else ""))
            page.wait_for_function("window.__chamber && document.getElementById('splash').hidden", timeout=30000)
            info = page.evaluate("""async () => { const e = window.__chamber.engine;
              const tex = e.texReady ? await Promise.race([e.texReady, new Promise((r) => setTimeout(() => r('timeout'), 20000))]) : null;
              return { tier: e.tier, gfx: e.gfx || null, tex, dpr: e.renderer ? e.renderer.getPixelRatio() : null }; }""")
            page.wait_for_timeout(1500)   # the plates fade in
            name = f"{args.label}-{gfx}" if gfx else args.label
            print(name, info)
            for view, (js, undo) in VIEWS.items():
                if args.views and view not in args.views:
                    continue
                page.evaluate(js)
                page.wait_for_timeout(2400)
                page.screenshot(path=str(args.out / f"{name}-{view}.png"))
                if undo:
                    page.evaluate(undo)
                    page.wait_for_timeout(1200)
            if errors:
                print("  console errors:", errors)
            ctx.close()
        browser.close()
    httpd.shutdown()
    print("saved to", args.out)


if __name__ == "__main__":
    main()
