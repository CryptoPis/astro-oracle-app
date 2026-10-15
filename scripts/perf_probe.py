"""Measures rendering cost of dist/preview.html in Chrome (dev tool, not used by the server).

    pip install playwright        # uses the installed Google Chrome, no browser download
    python -m scripts.build_frontend
    python -m scripts.perf_probe [--label before] [--tier lite|full]

For each scenario it records, with the CPU throttled 4x:
  fps / p95 frame time / janky frames (> 33 ms)  from requestAnimationFrame deltas
  long tasks (> 50 ms)                            from PerformanceObserver("longtask")
  style recalcs / layouts per second              from CDP Performance.getMetrics
  main-thread ms per second spent in Paint, style (UpdateLayoutTree), Layout, scripts, and
  raster/composite work                           from a Chrome trace
Scrolling: real touch gestures on the phone (CDP Input.synthesizeScrollGesture), the mouse wheel on desktop.
Results go to dist/perf-<label>.json and a summary is printed.
"""
import argparse
import json
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
SECONDS = 5
TRACE_CATS = "devtools.timeline,disabled-by-default-devtools.timeline,cc,gpu,blink"

PROBE = """
window.__perf = { frames: [], longs: [] };
let last = performance.now();
(function f(t) { window.__perf.frames.push(t - last); last = t; requestAnimationFrame(f); })(last);
try { new PerformanceObserver((l) => l.getEntries().forEach((e) => window.__perf.longs.push(e.duration)))
  .observe({ type: "longtask", buffered: true }); } catch (e) {}
"""

# top-level events only (nested ones would be counted twice)
BUCKETS = {"paint": {"Paint"}, "raster": {"RasterTask"}, "composite": {"Commit", "ActivateLayerTree"}}


class Quiet(SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def serve():
    handler = partial(Quiet, directory=str(DIST))
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


def summarize_trace(events, seconds):
    out = {k: 0.0 for k in BUCKETS}
    paints = 0
    for e in events:
        if e.get("ph") != "X" or "dur" not in e:
            continue
        for k, names in BUCKETS.items():
            if e.get("name") in names:
                out[k] += e["dur"] / 1000
        paints += e.get("name") == "Paint"
    res = {f"{k}_ms_per_s": round(v / seconds, 1) for k, v in out.items()}
    res["paints_per_s"] = round(paints / seconds, 1)
    return res


def measure(page, cdp, action):
    page.evaluate("window.__perf.frames = []; window.__perf.longs = []; window.__perf.t0 = performance.now()")
    m0 = {m["name"]: m["value"] for m in cdp.send("Performance.getMetrics")["metrics"]}
    events = []
    cdp.on("Tracing.dataCollected", lambda p: events.extend(p["value"]))
    done = threading.Event()
    cdp.on("Tracing.tracingComplete", lambda p: done.set())
    cdp.send("Tracing.start", {"categories": TRACE_CATS, "transferMode": "ReportEvents"})
    action()
    elapsed = page.evaluate("(performance.now() - window.__perf.t0) / 1000")
    m1 = {m["name"]: m["value"] for m in cdp.send("Performance.getMetrics")["metrics"]}
    p = page.evaluate("window.__perf")
    cdp.send("Tracing.end")
    for _ in range(100):
        if done.is_set():
            break
        page.wait_for_timeout(100)
    frames = sorted(x for x in p["frames"][1:] if x > 0)
    n = len(frames)
    per_s = lambda k, scale=1: round((m1[k] - m0[k]) * scale / elapsed, 1)
    res = {
        "fps": round(n / elapsed, 1),
        "p95_frame_ms": round(frames[int(n * .95)] if n else 0, 1),
        "janky_frames": sum(1 for x in frames if x > 33.4),
        "long_tasks": len(p["longs"]),
        "long_task_ms": round(sum(p["longs"])),
        "style_recalcs_per_s": per_s("RecalcStyleCount"),
        "style_ms_per_s": per_s("RecalcStyleDuration", 1000),
        "layouts_per_s": per_s("LayoutCount"),
        "layout_ms_per_s": per_s("LayoutDuration", 1000),
        "script_ms_per_s": per_s("ScriptDuration", 1000),
        "busy_ms_per_s": per_s("TaskDuration", 1000),
    }
    res.update(summarize_trace(events, elapsed))
    return res


def scroll_for(page, seconds, step=60, cdp=None):
    w, h = page.viewport_size["width"], page.viewport_size["height"]
    if cdp is not None:   # phone: real touch scroll gestures (a wheel on an emulated phone barely fires scroll events)
        for i in range(int(seconds / 1.25)):
            cdp.send("Input.synthesizeScrollGesture", {"x": w / 2, "y": h / 2, "yDistance": -900 if i % 2 == 0 else 900,
                                                         "speed": 900, "gestureSourceType": "touch", "preventFling": True})
        return
    page.mouse.move(w / 2, h / 2)
    ticks = int(seconds * 1000 / 50)
    for i in range(ticks):
        page.mouse.wheel(0, step if (i // 25) % 2 == 0 else -step)  # down then up, like a user reading
        page.wait_for_timeout(50)


def run(label, tier, inject=None, only=None):
    httpd = serve()
    url = f"http://127.0.0.1:{httpd.server_address[1]}/preview.html" + (f"?tier={tier}" if tier else "")
    results = {}
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="chrome", headless=True)
        for name, vp, mobile in [("phone", {"width": 390, "height": 844}, True), ("desktop", {"width": 1280, "height": 800}, False)]:
            if only and name != only:
                continue
            ctx = browser.new_context(viewport=vp, device_scale_factor=3 if mobile else 1, is_mobile=mobile, has_touch=mobile)
            page = ctx.new_page()
            errors = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.on("console", lambda m: m.type == "error" and "favicon" not in m.text and "404" not in m.text and errors.append(m.text))
            page.add_init_script(PROBE)
            if inject:
                page.add_init_script(inject)
            page.add_init_script("try { localStorage.setItem('astro.lang', 'en') } catch (e) {}")
            page.goto(url, wait_until="load")
            page.wait_for_timeout(2500)
            cdp = ctx.new_cdp_session(page)
            cdp.send("Performance.enable")
            cdp.send("Emulation.setCPUThrottlingRate", {"rate": 4})
            r = {}
            r["home_idle"] = measure(page, cdp, lambda: page.wait_for_timeout(SECONDS * 1000))
            touch = cdp if mobile else None
            r["home_scroll"] = measure(page, cdp, lambda: scroll_for(page, SECONDS, cdp=touch))
            page.evaluate("document.querySelector('[data-tab=tarot]').click()")
            page.wait_for_timeout(1500)
            r["tarot_scroll"] = measure(page, cdp, lambda: scroll_for(page, SECONDS, cdp=touch))
            page.evaluate("document.querySelector('[data-tab=home]').click()")
            r["errors"] = errors
            results[name] = r
            ctx.close()
        browser.close()
    httpd.shutdown()
    out = DIST / f"perf-{label}.json"
    out.write_text(json.dumps(results, indent=2), encoding="utf-8")
    keys = ["fps", "p95_frame_ms", "janky_frames", "long_tasks", "busy_ms_per_s", "style_recalcs_per_s", "style_ms_per_s",
            "script_ms_per_s", "paints_per_s", "paint_ms_per_s", "raster_ms_per_s"]
    for dev, r in results.items():
        print(f"\n[{label}] {dev}  errors: {r['errors'] or 'none'}")
        print("scenario      " + " ".join(f"{k[:12]:>12}" for k in keys))
        for sc in ("home_idle", "home_scroll", "tarot_scroll"):
            print(f"{sc:13} " + " ".join(f"{r[sc].get(k, 0):>12}" for k in keys))
    print(f"\nsaved {out}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", default="run")
    ap.add_argument("--tier", default=None, help="force a performance tier via ?tier= (after the fix)")
    ap.add_argument("--inject", default=None, help="JS file run before the page (for isolation experiments)")
    ap.add_argument("--only", default=None, choices=["phone", "desktop"])
    a = ap.parse_args()
    run(a.label, a.tier, Path(a.inject).read_text(encoding="utf-8") if a.inject else None, a.only)
