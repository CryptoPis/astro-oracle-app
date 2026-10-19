"""Reproduces "Home still shows the old data after a profile change" against the REAL backend (dev tool).

    pip install playwright
    python -m scripts.build_frontend
    python -m scripts.ui_profile_refresh

Starts uvicorn locally (throwaway SQLite, mock AI, bot off, a dummy bot token that only signs local test
initData; it runs in a temp directory so no .env file is read), opens the Mini App in Chrome with a stub
window.Telegram.WebApp carrying signed initData (telegram.org is blocked), and runs these scenarios:

  basic       onboard, then change birth date + time + city in Profile, go Home
  race        the Home energy request for the OLD sign is slow (mobile network / cold server) and
              arrives after the new one: Home must still show the new sign's energy
  background  the profile changes elsewhere (bot, another device) while the app sits in the
              background 10 minutes (fake clock); on return Home must update
  retry       Save fails once with a network error (a clear error must be visible), then succeeds
  double      Save tapped twice quickly: one request, no error, correct data

Instrumentation (test only): a fetch wrapper tags every /api/daily/energy quote with the sign the server
answered for ("… [Pisces]"), so the DOM shows which response is on screen.
Exit code 1 if any check fails.
"""
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
TOKEN = "123456:LOCAL-TEST-ONLY"   # not a real bot token: only signs initData for this local server
os.environ.setdefault("BOT_TOKEN", TOKEN)
from app.security import sign_init_data  # noqa: E402

FETCH_TAG = """
(() => {
  const orig = window.fetch.bind(window); window.__api = [];
  window.fetch = async (input, init) => {
    const url = typeof input === 'string' ? input : input.url, slow = url.includes('/api/daily/energy') && window.__slowNextEnergy;
    if (slow) window.__slowNextEnergy = false;
    const res = await orig(input, init);
    if (url.includes('/api/')) window.__api.push({ url, method: (init && init.method) || 'GET', status: res.status });
    if (!url.includes('/api/daily/energy') || !res.ok) return res;
    const data = await res.json();
    data.quote = `${data.quote} [${data.sign ? data.sign.id : 'none'}]`;
    if (slow) await new Promise((r) => setTimeout(r, 4000));
    return new Response(JSON.stringify(data), { status: res.status, headers: { 'Content-Type': 'application/json' } });
  };
})();
"""


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def start_server():
    tmp = tempfile.mkdtemp()
    port = free_port()
    env = {**os.environ, "BOT_TOKEN": TOKEN, "BOT_ENABLED": "false", "AI_PROVIDER": "mock", "ENV": "development",
           "DATABASE_URL": f"sqlite+aiosqlite:///{tmp}/refresh.db", "PUBLIC_BASE_URL": f"http://127.0.0.1:{port}",
           "MORNING_PUSH_MODE": "off", "CRON_SECRET": "local", "GROQ_API_KEY": "", "DEV_AUTH_BYPASS": "false"}
    proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--app-dir", str(ROOT), "--port", str(port),
                             "--log-level", "warning"], cwd=tmp, env=env)
    base = f"http://127.0.0.1:{port}"
    for _ in range(60):
        try:
            urllib.request.urlopen(base + "/healthz", timeout=1)
            return proc, base
        except Exception:
            time.sleep(.5)
    proc.kill()
    raise SystemExit("server did not start")


def init_data(uid):
    return sign_init_data({"user": {"id": uid, "first_name": "Tester", "language_code": "en"},
                           "auth_date": int(time.time()), "query_id": "AAH"}, TOKEN)


def stub(uid):
    user = {"id": uid, "first_name": "Tester", "language_code": "en"}
    return f"""
(() => {{ const ev = {{}}; window.__tgEvents = ev;
  window.Telegram = {{ WebApp: {{ initData: {json.dumps(init_data(uid))}, initDataUnsafe: {{ user: {json.dumps(user)} }},
    platform: 'android', version: '8.0', isVersionAtLeast: (v) => parseFloat(v) <= 8.0,
    ready() {{}}, expand() {{}}, setHeaderColor() {{}}, setBackgroundColor() {{}}, setBottomBarColor() {{}}, disableVerticalSwipes() {{}},
    BackButton: {{ show() {{}}, hide() {{}}, onClick() {{}} }}, HapticFeedback: {{ impactOccurred() {{}}, notificationOccurred() {{}} }},
    onEvent(n, f) {{ (ev[n] = ev[n] || []).push(f); }}, offEvent() {{}}, openTelegramLink() {{}} }} }};
  try {{ localStorage.setItem('astro.lang', 'en'); }} catch (e) {{}}
}})();
"""


def api(base, uid, method, path, body=None):
    req = urllib.request.Request(base + path, method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Authorization": f"tma {init_data(uid)}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())


class Run:
    def __init__(self):
        self.fails, self.passes = [], 0

    def check(self, scenario, what, ok, detail=""):
        if ok:
            self.passes += 1
        else:
            self.fails.append(f"[{scenario}] {what}" + (f": {detail}" if detail else ""))
        print(f"  {'ok  ' if ok else 'FAIL'} {what}" + ("" if ok else f"  ({detail})"))


def home_state(page):
    return page.evaluate("""() => ({ sign: document.querySelector('#heroSign').textContent.trim(),
      sub: document.querySelector('#heroSub').textContent, quote: document.querySelector('#quote').textContent,
      potd: (document.querySelector('#potd') || {}).textContent || '', report: document.querySelector('#report').hidden ? null : document.querySelector('#report').textContent,
      sky: !document.querySelector('#skySec').hidden })""")


def assert_home(run, sc, page, sign, element):
    page.wait_for_timeout(1500)
    h = home_state(page)
    run.check(sc, f"hero sign is {sign}", h["sign"] == sign, h["sign"])
    run.check(sc, f"hero subtitle shows {element}", element in h["sub"], h["sub"])
    run.check(sc, f"energy block is for {sign}", f"[{sign}]" in h["quote"], h["quote"][-40:])
    run.check(sc, "sky section and planet of the day render", h["sky"] and len(h["potd"]) > 10, h["potd"][:60])
    return h


def open_app(browser, base, uid, slow_energy=False, clock=False):
    ctx = browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
    ctx.route("**/telegram.org/**", lambda r: r.abort())
    ctx.add_init_script(stub(uid))
    ctx.add_init_script(FETCH_TAG)
    if slow_energy:
        ctx.add_init_script("window.__slowNextEnergy = true;")
    page = ctx.new_page()
    errs = []
    page.on("pageerror", lambda e: errs.append(str(e)))
    if clock:
        page.clock.install()
    page.goto(base + "/")
    page.wait_for_selector("#splash", state="hidden", timeout=20000)
    return ctx, page, errs


def save_profile(page, date, time_=None, city=None):
    page.click("[data-tab=profile]")
    page.wait_for_timeout(400)
    page.fill("#birthInput", date)
    if time_ is not None:
        page.fill("#birthTime", time_)
    if city is not None:
        page.fill("#birthCity", city)
    page.click("#dateForm button")


def scenario_basic(run, browser, base):
    print("basic: onboard, change date + time + city, go Home")
    ctx, page, errs = open_app(browser, base, 7001)
    run.check("basic", "onboarding shown for a new user", page.is_visible("#onboard"))
    page.fill("#obDate", "1990-08-15")
    page.click("#obForm button")
    page.wait_for_timeout(1500)
    assert_home(run, "basic", page, "Leo", "Fire")
    save_profile(page, "1995-03-14", "08:15", "Tbilisi")
    page.wait_for_timeout(1200)
    p = api(base, 7001, "GET", "/api/user/profile")["user"]
    run.check("basic", "server saved date, time and city", (p["birth_date"], p["birth_time"], p["birth_city"]) == ("1995-03-14", "08:15", "Tbilisi"), str(p))
    page.click("[data-tab=home]")
    assert_home(run, "basic", page, "Pisces", "Water")
    run.check("basic", "no page errors", not errs, str(errs))
    ctx.close()


def scenario_race(run, browser, base):
    print("race: the old sign's energy arrives late")
    api(base, 7002, "POST", "/api/auth/verify")
    api(base, 7002, "PATCH", "/api/user/profile", {"birth_date": "1990-08-15"})
    ctx, page, errs = open_app(browser, base, 7002, slow_energy=True)
    save_profile(page, "1995-03-14")
    page.wait_for_timeout(1000)
    page.click("[data-tab=home]")
    page.wait_for_timeout(5000)    # the slow Leo response lands now
    assert_home(run, "race", page, "Pisces", "Water")
    ctx.close()


def scenario_background(run, browser, base):
    print("background: changed elsewhere while the app sleeps 10 minutes")
    api(base, 7003, "POST", "/api/auth/verify")
    api(base, 7003, "PATCH", "/api/user/profile", {"birth_date": "1990-08-15"})
    ctx, page, errs = open_app(browser, base, 7003, clock=True)
    assert_home(run, "background", page, "Leo", "Fire")
    page.evaluate("""() => { Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => 'hidden' });
      Object.defineProperty(document, 'hidden', { configurable: true, get: () => true }); document.dispatchEvent(new Event('visibilitychange')); }""")
    api(base, 7003, "PATCH", "/api/user/profile", {"birth_date": "1995-03-14"})   # e.g. from another device
    page.clock.fast_forward("10:00")
    page.evaluate("""() => { Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => 'visible' });
      Object.defineProperty(document, 'hidden', { configurable: true, get: () => false }); document.dispatchEvent(new Event('visibilitychange'));
      (window.__tgEvents.activated || []).forEach((f) => f()); }""")
    page.wait_for_timeout(500)
    page.clock.fast_forward("00:05")
    assert_home(run, "background", page, "Pisces", "Water")
    ctx.close()


def scenario_retry(run, browser, base):
    print("retry: Save fails once, then succeeds")
    api(base, 7004, "POST", "/api/auth/verify")
    api(base, 7004, "PATCH", "/api/user/profile", {"birth_date": "1990-08-15"})
    ctx, page, errs = open_app(browser, base, 7004)
    state = {"n": 0}

    def flaky(route):
        if route.request.method == "PATCH" and state["n"] == 0:
            state["n"] += 1
            return route.abort("internetdisconnected")
        return route.continue_()
    page.route("**/api/user/profile", flaky)
    save_profile(page, "1995-03-14")
    page.wait_for_timeout(800)
    err = page.evaluate("""() => { const e = document.querySelector('#saveMsg'); const t = document.querySelector('#toast');
      return (e && !e.hidden && e.textContent.trim()) || (t.classList.contains('show') && t.classList.contains('err') && t.textContent.trim()) || ''; }""")
    run.check("retry", "a visible error after the failed save", bool(err), "nothing visible")
    still = api(base, 7004, "GET", "/api/user/profile")["user"]["birth_date"]
    run.check("retry", "server still has the old date after the failure", still == "1990-08-15", still)
    page.click("#dateForm button")
    page.wait_for_timeout(1200)
    now = api(base, 7004, "GET", "/api/user/profile")["user"]["birth_date"]
    run.check("retry", "second Save stores the new date", now == "1995-03-14", now)
    page.click("[data-tab=home]")
    assert_home(run, "retry", page, "Pisces", "Water")
    ctx.close()


def scenario_double(run, browser, base):
    print("double: Save tapped twice quickly")
    api(base, 7005, "POST", "/api/auth/verify")
    api(base, 7005, "PATCH", "/api/user/profile", {"birth_date": "1990-08-15"})
    ctx, page, errs = open_app(browser, base, 7005)
    page.click("[data-tab=profile]")
    page.wait_for_timeout(400)
    page.fill("#birthInput", "1995-03-14")
    page.evaluate("() => { const b = document.querySelector('#dateForm button'); b.click(); b.click(); }")
    page.wait_for_timeout(1500)
    n = page.evaluate("() => window.__api.filter((c) => c.method === 'PATCH').length")
    run.check("double", "only one PATCH request", n == 1, f"{n} requests")
    page.click("[data-tab=home]")
    assert_home(run, "double", page, "Pisces", "Water")
    run.check("double", "no page errors", not errs, str(errs))
    ctx.close()


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    proc, base = start_server()
    run = Run()
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(channel="chrome", headless=True)
            for sc in (scenario_basic, scenario_race, scenario_background, scenario_retry, scenario_double):
                try:
                    sc(run, browser, base)
                except Exception as e:   # a crashed scenario is a failure, the others still run
                    run.fails.append(f"[{sc.__name__}] crashed: {str(e).splitlines()[0][:160]}")
                    print(f"  FAIL crashed: {str(e).splitlines()[0][:160]}")
            browser.close()
    finally:
        proc.terminate()
    print(f"\n{run.passes} checks passed, {len(run.fails)} failed")
    if run.fails:
        print("FAILED:\n  " + "\n  ".join(run.fails))
        sys.exit(1)


if __name__ == "__main__":
    main()
