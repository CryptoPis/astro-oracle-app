"""Phone screenshots of every oracle-chamber station (dev tool, uses the demo build).

    python -m scripts.build_frontend
    python -m scripts.chamber_stations --label before                 # FULL High, FULL Medium and LITE, 360x800, Georgian
    python -m scripts.chamber_stations --label after --tiers high --only sphere gift

Each station is opened the way a person opens it (window.__chamber.open), shot once it has settled, and for the
interactive ones a second time in the state that matters (the sphere wiped, the chest opened, the cards drawn).
Output: dist/screens/chamber-stations/<label>-<tier>-<station>.png
"""
import argparse
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

from scripts.chamber_check import ARGS
from scripts.perf_probe import serve

ROOT = Path(__file__).resolve().parent.parent
VP = {"width": 360, "height": 800}
TIERS = {"high": "&tier=full&gfx=high", "medium": "&tier=full&gfx=medium", "lite": "&tier=lite"}
# station: the follow-up action shot as "<station>-2" (None: one shot)
STATIONS = {
    "room": None,
    "tarot": "tarot",
    "sphere": "sphere",
    "moon": None,
    "aura": None,
    "gift": "gift",
    "horo": None,
    "advisor": None,
    "dream": None,
    "num": None,
    "chart": None,
    "coffee": None,
}
FOLLOW = {
    "sphere": """async () => { const b = [...document.querySelectorAll('#chHud .ch-act')].pop(); if (b) b.click(); }""",
    "gift": """async () => { const b = document.querySelector('#chHud .ch-act'); if (b && !b.hidden) b.click(); }""",
    "tarot": """async () => { const act = () => document.querySelector('#chHud .ch-act');
      act().click(); await new Promise((r) => setTimeout(r, 2600));
      act().click(); await new Promise((r) => setTimeout(r, 2600));
      act().click(); await new Promise((r) => setTimeout(r, 1200)); }""",
}


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", required=True)
    ap.add_argument("--tiers", nargs="*", default=list(TIERS))
    ap.add_argument("--only", nargs="*", default=None)
    ap.add_argument("--lang", default="ka")
    ap.add_argument("--out", type=Path, default=ROOT / "dist" / "screens" / "chamber-stations")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    httpd = serve()
    base = f"http://127.0.0.1:{httpd.server_address[1]}/preview.html?ui=chamber"
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="chrome", headless=True, args=ARGS)
        for tier in args.tiers:
            ctx = browser.new_context(viewport=VP, is_mobile=True, has_touch=True, device_scale_factor=2)
            ctx.add_init_script(f"try {{ localStorage.setItem('astro.lang', '{args.lang}'); localStorage.setItem('astro.chIntro', '1') }} catch (e) {{}}")
            page = ctx.new_page()
            errors = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.on("console", lambda m: errors.append(m.text) if m.type == "error" and "favicon" not in m.text and "404" not in m.text else None)
            page.goto(base + TIERS[tier])
            page.wait_for_function("window.__chamber && document.getElementById('splash').hidden", timeout=30000)
            page.evaluate("Promise.race([window.__chamber.engine.texReady || Promise.resolve(), new Promise((r) => setTimeout(r, 20000))])")
            page.wait_for_timeout(1500)
            for sid, follow in STATIONS.items():
                if args.only and sid not in args.only:
                    continue
                name = f"{args.label}-{tier}-{sid}"
                if sid != "room":
                    page.evaluate(f"window.__chamber.open('{sid}')")
                page.wait_for_timeout(2600)
                page.screenshot(path=str(args.out / f"{name}.png"))
                if follow and tier != "lite":
                    page.evaluate(FOLLOW[follow])
                    page.wait_for_timeout(3200)
                    page.screenshot(path=str(args.out / f"{name}-2.png"))
                if sid != "room":
                    for _ in range(2):
                        if page.evaluate("!!window.__chamber.engine.focused || document.getElementById('scroller').classList.contains('ch-open')"):
                            page.evaluate("window.__astro.back()")
                            page.wait_for_timeout(1300)
            print(tier, "errors:", errors or "none")
            ctx.close()
        browser.close()
    httpd.shutdown()
    print("saved to", args.out)


if __name__ == "__main__":
    main()
