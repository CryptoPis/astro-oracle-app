"""Layout audit of the Mini App (dev tool). Exit code 1 if any check fails.

    python -m scripts.build_frontend
    python -m scripts.ui_audit [--langs ka,en,ru] [--devices phone,small,desktop] [--skip-real]

Demo build (dist/preview.html), every screen, every language, phone 390×844, small phone 360×780, desktop:
  - horizontal overflow: nothing wider than the device (an overflowing page widens the layout viewport,
    so the device width is used, not innerWidth);
  - clipped text: an element that hides overflow but whose text is larger than its box;
  - overlapping text: two different text elements whose boxes overlap (e.g. zodiac names running together);
  - tab bar: at the end of the scroll the last item of the screen ends above the floating tab bar;
  - rail cards (.pcard): frame, title and reward chip visible, chip on one line, card inside its rail;
  - zodiac strip: the selected sign is fully inside the strip;
  - sphere: no category chip, an advice line under the answer;
  - idle style recalcs on Home (phone, CPU 4x).
Real backend (stub Telegram + signed initData, mock AI, Georgian), unless --skip-real:
  - tarot card titles come from the dictionary (the mock AI's "card_title" is deliberately "Mock card"),
    no "(…)", and "reversed" appears at most once.
"""
import argparse
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

from scripts.perf_probe import DIST, serve

DEVICES = {"phone": ({"width": 390, "height": 844}, 3, True), "small": ({"width": 360, "height": 780}, 3, True),
           "desktop": ({"width": 1280, "height": 800}, 1, False)}
TABS = ["home", "horo", "tarot", "dream", "profile"]
SUBS = ["num", "sphere", "moon", "compat", "advisor", "aura", "coffee", "kundli"]

LAYOUT_JS = """(W) => {
  const out = { doc: Math.max(document.scrollingElement.scrollWidth, innerWidth), overflow: [], clipped: [], overlap: [] };
  const view = [...document.querySelectorAll('main > .view')].find((v) => !v.hidden);
  const visible = (n) => n.getClientRects().length && !n.closest('[hidden]');
  const clippedBy = (n) => { for (let p = n.parentElement; p && p !== document.body; p = p.parentElement) {
    const ox = getComputedStyle(p).overflowX; if (ox !== 'visible' && p.getBoundingClientRect().right <= W + 1) return true; } return false; };
  const name = (n) => `${n.tagName.toLowerCase()}${n.id ? '#' + n.id : ''}${n.classList.length ? '.' + [...n.classList].join('.') : ''} "${(n.textContent || '').trim().slice(0, 18)}"`;
  const scope = [...document.querySelectorAll('.top *'), ...(view ? view.querySelectorAll('*') : [])];
  for (const n of scope) {
    if (!visible(n) || n.closest('.rail, .strip, .ptable-wrap')) continue;
    const r = n.getBoundingClientRect();
    if (r.width && r.right > W + 1 && !clippedBy(n)) out.overflow.push(`${name(n)} right=${Math.round(r.right)}`);
  }
  // text leaves: elements with their own non-empty text
  const leaves = scope.filter((n) => visible(n) && !n.closest('svg') && [...n.childNodes].some((c) => c.nodeType === 3 && c.textContent.trim()));
  for (const n of leaves) {
    const cs = getComputedStyle(n);
    const hides = cs.overflowX !== 'visible' || cs.overflowY !== 'visible' || cs.textOverflow === 'ellipsis';
    if (hides && !['INPUT', 'TEXTAREA', 'SELECT'].includes(n.tagName) && (n.scrollWidth > n.clientWidth + 1 || n.scrollHeight > n.clientHeight + 2))
      out.clipped.push(name(n));
  }
  const boxes = leaves.filter((n) => !n.closest('.chat')).map((n) => { const range = document.createRange(); range.selectNodeContents(n); return [n, range.getBoundingClientRect()]; })
    .filter(([, r]) => r.width > 0 && r.height > 0);
  for (let i = 0; i < boxes.length; i++) for (let j = i + 1; j < boxes.length; j++) {
    const [a, ra] = boxes[i], [b, rb] = boxes[j];
    if (a.contains(b) || b.contains(a)) continue;
    const w = Math.min(ra.right, rb.right) - Math.max(ra.left, rb.left), h = Math.min(ra.bottom, rb.bottom) - Math.max(ra.top, rb.top);
    // tall Georgian ascenders make neighbouring line boxes touch; real collisions overlap most of the line height
    if (w > 2 && h > 0.35 * Math.min(ra.height, rb.height)) out.overlap.push(`${name(a)} x ${name(b)}`);
  }
  out.overflow = [...new Set(out.overflow)].slice(0, 6); out.clipped = [...new Set(out.clipped)].slice(0, 6); out.overlap = out.overlap.slice(0, 6);
  return out;
}"""

END_JS = """() => {
  const sc = document.querySelector('#scroller'); sc.scrollTop = sc.scrollHeight;
  const view = [...document.querySelectorAll('main > .view')].find((v) => !v.hidden), bar = document.querySelector('.tabs-in').getBoundingClientRect();
  let last = null;
  for (const n of view.querySelectorAll('*')) { if (!n.getClientRects().length || n.closest('[hidden]')) continue;
    const r = n.getBoundingClientRect(); if (r.height && (!last || r.bottom > last.bottom)) last = { bottom: r.bottom, name: n.className || n.tagName }; }
  return last ? { lastBottom: Math.round(last.bottom), barTop: Math.round(bar.top), name: String(last.name).slice(0, 40) } : null;
}"""

RAIL_JS = """() => [...document.querySelectorAll('.rail .pcard')].map((c, i) => {
  const cs = getComputedStyle(c), r = c.getBoundingClientRect(), b = c.querySelector('b'), sm = c.querySelector('small'), rail = c.parentElement.getBoundingClientRect();
  const inside = (n) => { if (!n) return false; const q = n.getBoundingClientRect(); return q.width > 0 && q.height > 0 && q.left >= r.left - 1 && q.right <= r.right + 1 && q.bottom <= r.bottom + 1; };
  const framed = cs.backgroundImage !== 'none' || cs.backgroundColor !== 'rgba(0, 0, 0, 0)';
  const oneLine = sm ? sm.getBoundingClientRect().height < parseFloat(getComputedStyle(sm).fontSize) * 2.2 : false;
  return { i, title: b && b.textContent, framed, titleOk: inside(b) && b.textContent.trim().length > 0, chip: inside(sm) && oneLine,
           inRail: r.bottom <= rail.bottom + 1 && r.top >= rail.top - 1 };
})"""


def nav(page, name):
    page.evaluate(f"window.__astro.go('{name}')")
    page.wait_for_timeout(1700)
    if name == "sphere":
        page.fill("#sphereQ", "ვუყვარვარ?")
        page.click("#sphereBtn")
        page.wait_for_timeout(2400)


def audit_demo(browser, base, devices, langs, failed):
    for dev in devices:
        vp, dpr, mobile = DEVICES[dev]
        for lang in langs:
            ctx = browser.new_context(viewport=vp, device_scale_factor=dpr, is_mobile=mobile, has_touch=mobile)
            ctx.add_init_script(f"try {{ localStorage.setItem('astro.lang', '{lang}') }} catch (e) {{}}")
            page = ctx.new_page()
            errs = []
            page.on("pageerror", lambda e: errs.append(str(e)))
            page.goto(base)
            page.wait_for_timeout(2600)
            tag = f"{dev}-{lang}"
            for name in TABS + SUBS:
                nav(page, name)
                o = page.evaluate(LAYOUT_JS, vp["width"])
                if o["doc"] > vp["width"] or o["overflow"]:
                    failed.append(f"{tag} {name}: horizontal overflow {o['overflow']}")
                if o["clipped"]:
                    failed.append(f"{tag} {name}: clipped text {o['clipped']}")
                if o["overlap"]:
                    failed.append(f"{tag} {name}: overlapping text {o['overlap']}")
                if name == "home":
                    page.evaluate("document.querySelector('#scroller').scrollTop = 0")
                    cards = page.evaluate(RAIL_JS)
                    bad = [c for c in cards if not (c["framed"] and c["titleOk"] and c["chip"] and c["inRail"])]
                    print(f"{tag} rail cards: {len(cards)} checked, {len(bad)} incomplete")
                    failed += [f"{tag} rail card {c}" for c in bad]
                    pill = page.evaluate("(() => { const c = document.querySelector('#coins'), t = document.querySelector('.top'); const r = c.getBoundingClientRect(); return { right: r.right, h: r.height, topW: t.getBoundingClientRect().right }; })()")
                    if pill["right"] > pill["topW"] + 1 or pill["h"] > 44:
                        failed.append(f"{tag} coin pill does not fit: {pill}")
                if name == "horo":
                    sel = page.evaluate("""() => { const s = document.querySelector('.strip'), b = s.querySelector('[aria-pressed="true"]');
                      const a = s.getBoundingClientRect(), r = b.getBoundingClientRect(); return { inside: r.left >= a.left - 1 && r.right <= a.right + 1 }; }""")
                    if not sel["inside"]:
                        failed.append(f"{tag} horo: selected sign is not fully inside the strip")
                if name == "sphere":
                    sph = page.evaluate("() => ({ chip: !!document.querySelector('#tone'), advice: ((document.querySelector('#sphereAdvice') || {}).textContent || '').trim().length })")
                    if sph["chip"] or not sph["advice"]:
                        failed.append(f"{tag} sphere: chip={sph['chip']} advice={sph['advice']}")
                end = page.evaluate(END_JS)
                if end and end["lastBottom"] > end["barTop"]:
                    failed.append(f"{tag} {name}: end of the screen under the tab bar ({end})")
                page.evaluate("document.querySelector('#scroller').scrollTop = 0")
            if errs:
                failed.append(f"{tag} errors: {errs}")
            ctx.close()


def idle_restyles(browser, base):
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
    ctx.close()


def audit_real(browser, failed):
    """Real backend + stub Telegram (see scripts/ui_profile_refresh.py), Georgian, both phone sizes."""
    from scripts import ui_profile_refresh as R
    proc, base = R.start_server()
    try:
        for vp in (DEVICES["phone"][0], DEVICES["small"][0]):
            uid = 9000 + vp["width"]
            R.api(base, uid, "POST", "/api/auth/verify")
            R.api(base, uid, "PATCH", "/api/user/profile", {"birth_date": "1990-08-15", "lang": "ka"})
            ctx = browser.new_context(viewport=vp, is_mobile=True, has_touch=True)
            ctx.route("**/telegram.org/**", lambda r: r.abort())
            ctx.add_init_script(R.stub(uid).replace("localStorage.setItem('astro.lang', 'en')", "localStorage.setItem('astro.lang', 'ka')"))
            page = ctx.new_page()
            page.goto(base + "/")
            page.wait_for_selector("#splash", state="hidden", timeout=20000)
            for spread in ("daily", "three"):
                page.click("[data-tab=tarot]")
                page.wait_for_timeout(600)
                if spread == "three":
                    page.click("#spreadSeg [data-spread=three]")
                    page.wait_for_timeout(400)
                page.click("#drawBtn")
                page.wait_for_timeout(5500)
                titles = page.evaluate("() => [...document.querySelectorAll('#tarotOut .card-read h3')].map((h) => h.textContent)")
                rev = "შებრუნებული"
                for tt in titles:
                    if "Mock" in tt or "(" in tt or tt.count(rev) > 1 or not any("Ⴀ" <= ch <= "ჿ" for ch in tt):
                        failed.append(f"real {vp['width']} tarot {spread}: bad card title {tt!r}")
                print(f"real {vp['width']} tarot {spread}: {titles}")
            ctx.close()
    finally:
        proc.terminate()


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--dist", default=str(DIST))
    ap.add_argument("--langs", default="ka,en,ru")
    ap.add_argument("--devices", default="phone,small,desktop")
    ap.add_argument("--coins", default="12500", help="demo balance to test the top-bar pill")
    ap.add_argument("--skip-real", action="store_true")
    a = ap.parse_args()
    httpd = serve(Path(a.dist))
    base = f"http://127.0.0.1:{httpd.server_address[1]}/preview.html?coins={a.coins}"
    failed: list[str] = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="chrome", headless=True)
        audit_demo(browser, base, a.devices.split(","), a.langs.split(","), failed)
        idle_restyles(browser, base)
        if not a.skip_real:
            audit_real(browser, failed)
        browser.close()
    httpd.shutdown()
    if failed:
        print("FAILED:\n  " + "\n  ".join(failed[:80]) + (f"\n  ... {len(failed) - 80} more" if len(failed) > 80 else ""))
        sys.exit(1)
    print("all checks passed")


if __name__ == "__main__":
    main()
