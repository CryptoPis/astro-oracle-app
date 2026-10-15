"""Layout audit of dist/preview.html (dev tool): horizontal overflow, rail cards, idle restyles.

    python -m scripts.build_frontend
    python -m scripts.ui_audit [--dist DIR] [--langs ka,en,ru] [--devices phone,desktop]

For every screen it reports
  - horizontal overflow: document/scroller scrollWidth > innerWidth, and every element (outside the
    horizontal rails) whose right edge sticks out of the viewport;
  - rail cards (.pcard): each one must show its frame (background), title and reward chip, with the
    title and the chip fully inside the card;
  - idle style recalcs per second on the home screen (phone, CPU 4x).
Exit code 1 if any check fails.
"""
import argparse
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

from scripts.perf_probe import DIST, serve

DEVICES = {"phone": ({"width": 390, "height": 844}, 3, True), "desktop": ({"width": 1280, "height": 800}, 1, False)}
TABS = ["home", "horo", "tarot", "dream", "profile"]
SUBS = ["num", "sphere", "moon", "compat", "advisor", "aura", "coffee", "kundli"]

# W is the device width passed in: on a phone an overflowing page widens the layout viewport, so innerWidth lies
OVERFLOW_JS = """(W) => {
  const sc = document.querySelector('#scroller');
  const clipped = (n) => { for (let p = n.parentElement; p && p !== document.body; p = p.parentElement) {
    const ox = getComputedStyle(p).overflowX; if (ox !== 'visible' && p.getBoundingClientRect().right <= W + 1) return true; } return false; };
  const out = { doc: Math.max(document.scrollingElement.scrollWidth, innerWidth), scroller: sc ? sc.scrollWidth : null, W, offenders: [] };
  for (const n of document.querySelectorAll('#app *, .tabs *')) {
    if (n.closest('.rail, .strip, .ptable-wrap, [hidden]') || !n.getClientRects().length) continue;
    const r = n.getBoundingClientRect();
    if (r.width && r.right > W + 1 && !clipped(n)) out.offenders.push(`${n.tagName.toLowerCase()}${n.id ? '#' + n.id : ''}.${[...n.classList].join('.')} right=${Math.round(r.right)}`);
  }
  out.offenders = [...new Set(out.offenders)].slice(0, 8);
  return out;
}"""

RAIL_JS = """() => [...document.querySelectorAll('.rail .pcard')].map((c, i) => {
  const cs = getComputedStyle(c), r = c.getBoundingClientRect(), b = c.querySelector('b'), sm = c.querySelector('small');
  const inside = (n) => { if (!n) return false; const q = n.getBoundingClientRect(); return q.width > 0 && q.height > 0 && q.left >= r.left - 1 && q.right <= r.right + 1 && q.bottom <= r.bottom + 1; };
  const framed = cs.backgroundImage !== 'none' || cs.backgroundColor !== 'rgba(0, 0, 0, 0)';
  const oneLine = sm ? sm.getBoundingClientRect().height < parseFloat(getComputedStyle(sm).fontSize) * 2.2 : false;
  return { i, framed, title: inside(b) && b.textContent.trim().length > 0, chip: inside(sm) && oneLine, transform: cs.transform };
})"""


def nav(page, name, has_hook):
    if has_hook:
        page.evaluate(f"window.__astro.go('{name}')")
    elif name in TABS:
        page.click(f"[data-tab={name}]")
    else:
        return False
    page.wait_for_timeout(1500)
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dist", default=str(DIST))
    ap.add_argument("--langs", default="ka,en,ru")
    ap.add_argument("--devices", default="phone,desktop")
    ap.add_argument("--coins", default="12500", help="demo balance to test the top-bar pill")
    a = ap.parse_args()
    httpd = serve(Path(a.dist))
    base = f"http://127.0.0.1:{httpd.server_address[1]}/preview.html?coins={a.coins}"
    failed = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="chrome", headless=True)
        for dev in a.devices.split(","):
            vp, dpr, mobile = DEVICES[dev]
            for lang in a.langs.split(","):
                ctx = browser.new_context(viewport=vp, device_scale_factor=dpr, is_mobile=mobile, has_touch=mobile)
                ctx.add_init_script(f"try {{ localStorage.setItem('astro.lang', '{lang}') }} catch (e) {{}}")
                page = ctx.new_page()
                errs = []
                page.on("pageerror", lambda e: errs.append(str(e)))
                page.goto(base)
                page.wait_for_timeout(2500)
                hook = page.evaluate("!!window.__astro")
                tag = f"{dev}-{lang}"
                for name in TABS + SUBS:
                    if not nav(page, name, hook):
                        continue
                    o = page.evaluate(OVERFLOW_JS, vp["width"])
                    widest = max(o["doc"], o["scroller"] or 0)
                    if widest > o["W"] or o["offenders"]:
                        failed.append(f"{tag} {name}: overflow scrollWidth={widest} > {o['W']}; {o['offenders']}")
                    if name == "home":
                        cards = page.evaluate(RAIL_JS)
                        bad = [c for c in cards if not (c["framed"] and c["title"] and c["chip"])]
                        print(f"{tag} rail cards: {len(cards)} checked, {len(bad)} incomplete")
                        failed += [f"{tag} rail card {c}" for c in bad]
                        pill = page.evaluate("(() => { const c = document.querySelector('#coins'), t = document.querySelector('.top'); const r = c.getBoundingClientRect(); return { right: r.right, h: r.height, topW: t.getBoundingClientRect().right, text: c.textContent.trim() }; })()")
                        if pill["right"] > pill["topW"] + 1 or pill["h"] > 44:
                            failed.append(f"{tag} coin pill does not fit: {pill}")
                if errs:
                    failed.append(f"{tag} errors: {errs}")
                ctx.close()
        # idle restyles on the home screen (phone, CPU 4x)
        ctx = browser.new_context(viewport=DEVICES["phone"][0], is_mobile=True, has_touch=True)
        page = ctx.new_page()
        page.goto(base)
        page.wait_for_timeout(2500)
        cdp = ctx.new_cdp_session(page)
        cdp.send("Performance.enable")
        cdp.send("Emulation.setCPUThrottlingRate", {"rate": 4})
        m0 = {m["name"]: m["value"] for m in cdp.send("Performance.getMetrics")["metrics"]}
        page.wait_for_timeout(4000)
        m1 = {m["name"]: m["value"] for m in cdp.send("Performance.getMetrics")["metrics"]}
        print(f"idle home (phone, 4x): {(m1['RecalcStyleCount'] - m0['RecalcStyleCount']) / 4:.1f} style recalcs/s, "
              f"{(m1['RecalcStyleDuration'] - m0['RecalcStyleDuration']) * 250:.0f} ms/s")
        browser.close()
    httpd.shutdown()
    if failed:
        print("FAILED:\n  " + "\n  ".join(failed[:60]) + (f"\n  ... {len(failed) - 60} more" if len(failed) > 60 else ""))
        sys.exit(1)
    print("all checks passed")


if __name__ == "__main__":
    main()
