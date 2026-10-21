"""Oracle chamber smoke test + performance probe (dev tool, uses the demo build).

    python -m scripts.build_frontend
    python -m scripts.chamber_check            # FULL and LITE, 390x844, Georgian
    python -m scripts.chamber_check --perf     # also FPS / first-interactive / memory on a 4x throttled CPU,
                                               # FULL at both graphics levels (High, Medium) and LITE

Checks per tier: every station opens from the compass and closes with the back action (the same handler as
Telegram's BackButton), no console errors, no WebGL context loss, no memory growth after 10 station visits; FULL:
the photographic textures load without a failure (the memory baseline is taken after they are on the GPU).
Exit code 1 if anything fails.
"""
import json
import sys

from playwright.sync_api import sync_playwright

from scripts.perf_probe import serve

VP = {"width": 390, "height": 844}
ARGS = ["--enable-gpu", "--ignore-gpu-blocklist", "--use-angle=d3d11", "--enable-unsafe-swiftshader"]


def open_page(browser, base, tier, throttle=None, gfx=None):
    ctx = browser.new_context(viewport=VP, is_mobile=True, has_touch=True, device_scale_factor=2)
    ctx.add_init_script("try { localStorage.setItem('astro.lang', 'ka'); localStorage.setItem('astro.chIntro', '1') } catch (e) {}")
    page = ctx.new_page()
    errors = []
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" and "favicon" not in m.text and "404" not in m.text else None)
    page.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
    cdp = ctx.new_cdp_session(page)
    if throttle:
        cdp.send("Emulation.setCPUThrottlingRate", {"rate": throttle})
    page.add_init_script("""window.__lost = 0; document.addEventListener('webglcontextlost', () => window.__lost++, true);
      window.__t0 = performance.now();""")
    page.goto(f"{base}&tier={tier}" + (f"&gfx={gfx}" if gfx else ""))
    page.wait_for_function("window.__chamber && document.getElementById('splash').hidden", timeout=30000)
    first = page.evaluate("""() => { const s = performance.getEntriesByName('chamber-start')[0], r = performance.getEntriesByName('chamber-ready')[0],
      nav = performance.getEntriesByType('navigation')[0];
      return { total: Math.round(performance.now()), dom: Math.round(nav.domInteractive), chamber: s && r ? Math.round(r.startTime - s.startTime) : null }; }""")
    return ctx, page, cdp, errors, first


def heap(page, cdp):
    cdp.send("HeapProfiler.collectGarbage")
    page.wait_for_timeout(300)
    cdp.send("HeapProfiler.collectGarbage")
    return page.evaluate("""() => { const e = window.__chamber.engine, r = e.renderer;
      return { heap: performance.memory ? performance.memory.usedJSHeapSize : 0,
        geometries: r ? r.info.memory.geometries : 0, textures: r ? r.info.memory.textures : 0, nodes: document.getElementsByTagName('*').length }; }""")


def smoke(page, cdp, tier, errors):
    fails = []
    ids = page.evaluate("[...document.querySelectorAll('#chList .ch-item')].map((b) => b.dataset.id)")
    if len(ids) < 12:
        fails.append(f"compass lists {len(ids)} items")
    before = None
    for rnd in range(2):          # first round: every station; second: 10 more visits for the memory check
        for i, sid in enumerate(ids if rnd == 0 else ids[:10]):
            page.evaluate("window.__chamber.compass()")
            page.wait_for_timeout(350)
            page.click(f"#chList .ch-item[data-id='{sid}']")
            page.wait_for_timeout(1700)
            opened = page.evaluate("document.getElementById('scroller').classList.contains('ch-open') || !!window.__chamber.state.stage")
            if not opened:
                fails.append(f"{tier}: {sid} did not open")
            page.evaluate("window.__astro.back()")
            page.wait_for_timeout(1300)
            if page.evaluate("!!window.__chamber.state.stage"):     # a stage: the first back closed its panel only
                page.evaluate("window.__astro.back()")
                page.wait_for_timeout(1300)
            closed = page.evaluate("!document.getElementById('scroller').classList.contains('ch-open') && !window.__chamber.engine.focused")
            if not closed:
                fails.append(f"{tier}: {sid} did not close with back")
        if rnd == 0:
            if tier == "full":   # jumping from one stage straight to another must end the first one
                page.evaluate("window.__chamber.open('tarot')")
                page.wait_for_timeout(2500)
                page.evaluate("window.__chamber.compass()")
                page.wait_for_timeout(400)
                page.click("#chList .ch-item[data-id='sphere']")
                page.wait_for_timeout(2600)
                hud = page.evaluate("[...document.querySelectorAll('#chHud > *')].map((n) => n.className).join(' ')")
                if "ch-seg" in hud or "ch-q" not in hud or page.evaluate("document.querySelectorAll('.ch-answer').length") != 1:
                    fails.append(f"{tier}: the tarot stage survived a jump to the sphere ({hud})")
                page.evaluate("window.__astro.back()")
                page.wait_for_timeout(1500)
            before = heap(page, cdp)   # after a warm-up: every object has been drawn once (GPU uploads are lazy)
    after = heap(page, cdp)
    grow = (after["heap"] - before["heap"]) / max(1, before["heap"])
    mem = {"before": before, "after": after, "heap_growth": round(grow, 3)}
    if grow > .15:
        fails.append(f"{tier}: heap grew {grow:.0%} after 10 visits")
    if after["geometries"] > before["geometries"] or after["textures"] > before["textures"]:
        fails.append(f"{tier}: GPU objects grew {before['geometries']}/{before['textures']} -> {after['geometries']}/{after['textures']}")
    if page.evaluate("window.__lost"):
        fails.append(f"{tier}: WebGL context lost")
    fails += [f"{tier}: console: {e}" for e in errors]
    return fails, mem


def deep_tarot(page, cdp):
    """Three full tarot draws (shuffle, pull, server draw, flips, reading) then back: card faces must be released."""
    from scripts.chamber_videos import tarot_flow
    base = heap(page, cdp)
    for k in range(3):
        tarot_flow(page, three=k % 2 == 0)
        for _ in range(2):                                          # the reading panel, then the table
            page.evaluate("window.__astro.back()")
            page.wait_for_timeout(1400)
    after = heap(page, cdp)
    ok = after["textures"] <= base["textures"] and after["geometries"] <= base["geometries"]
    return ok, base, after


def fps(page, seconds=5, turning=True):
    return page.evaluate("""async ([ms, turning]) => { let n = 0, worst = 0, last = performance.now(); const t0 = last;
      let i = 0; const turn = turning ? setInterval(() => window.__chamber.turn(++i % 10), 900) : 0;
      await new Promise((res) => { const f = (now) => { n++; worst = Math.max(worst, now - last); last = now; if (now - t0 < ms) requestAnimationFrame(f); else res(); }; requestAnimationFrame(f); });
      clearInterval(turn); window.__chamber.turn(0); return { fps: Math.round(n / (ms / 1000) * 10) / 10, worst_ms: Math.round(worst) }; }""", [seconds * 1000, turning])


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    perf = "--perf" in sys.argv
    httpd = serve()
    base = f"http://127.0.0.1:{httpd.server_address[1]}/preview.html?ui=chamber"
    all_fails, report = [], {}
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="chrome", headless=True, args=ARGS)
        for tier in ("full", "lite"):
            ctx, page, cdp, errors, first = open_page(browser, base, tier)
            got = page.evaluate("window.__chamber.tier()")
            if got != tier:
                all_fails.append(f"asked for {tier}, got {got}")
            if tier == "full":   # the level chosen from frames 10-50, and the lazy texture set
                tex = page.evaluate("Promise.race([window.__chamber.engine.texReady, new Promise((r) => setTimeout(() => r(null), 30000))])")
                lvl = page.evaluate("({ gfx: window.__chamber.engine.gfx, ms: window.__chamber.engine.gfxMeasuredMs, windows: window.__chamber.engine.gfxMeasures })")
                print(f"full: auto level {lvl['gfx']} (measured windows {lvl['windows']}) · textures {tex}")
                if not tex or tex["failed"]:
                    all_fails.append(f"full: textures did not load: {tex}")
                report["full_auto"] = {**lvl, "textures": tex}
            fails, mem = smoke(page, cdp, tier, errors)
            if tier == "full":
                ok, b0, b1 = deep_tarot(page, cdp)
                print(f"full: 3 tarot draws · GPU geometries/textures {b0['geometries']}/{b0['textures']} -> {b1['geometries']}/{b1['textures']}")
                if not ok:
                    fails.append("full: tarot draws leaked GPU objects")
                if page.evaluate("document.getElementById('chCoinVal').textContent") == "1,250":
                    fails.append("full: tarot draws paid no reward")
            all_fails += fails
            report[tier] = {"smoke": "ok" if not fails else fails, "memory": mem}
            print(f"{tier}: {'ok' if not fails else fails} · heap {mem['before']['heap'] // 1024} -> {mem['after']['heap'] // 1024} KB"
                  f" · GPU geometries/textures {mem['after']['geometries']}/{mem['after']['textures']}")
            ctx.close()
            for gfx in (("high", "medium") if tier == "full" else (None,)) if perf else ():
                name = f"{tier}-{gfx}" if gfx else tier
                ctx, page, cdp, errors, first = open_page(browser, base, tier, throttle=4, gfx=gfx)
                if gfx:   # measure the finished room: the textures are on the GPU
                    page.evaluate("Promise.race([window.__chamber.engine.texReady, new Promise((r) => setTimeout(r, 30000))])")
                page.wait_for_timeout(1500)
                idle = fps(page, 4, turning=False)
                moving = fps(page, 6, turning=True)
                gpu = page.evaluate("(() => { const r = window.__chamber.engine.renderer; return r ? { dpr: r.getPixelRatio(), calls: r.info.render.calls, triangles: r.info.render.triangles, textures: r.info.memory.textures } : null; })()")
                report[name] = {**report.get(name, {}), "perf_4x_cpu": {"first_interactive_ms": first, "idle": idle, "turning": moving, "gpu": gpu}}
                print(f"{name} @4x CPU: interactive at {first['total']} ms (page parsed {first['dom']} ms, chamber boot {first['chamber']} ms)"
                      f" · idle {idle} · turning {moving} · {gpu}")
                ctx.close()
        browser.close()
    httpd.shutdown()
    print(json.dumps(report, ensure_ascii=False, indent=1) if perf else "")
    if all_fails:
        print("FAILED:\n- " + "\n- ".join(all_fails))
        sys.exit(1)
    print("all chamber checks passed")


if __name__ == "__main__":
    main()
