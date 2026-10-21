/* Oracle chamber: entry point, loaded by frontend/app.html only when the chamber UI is on.
   The room (FULL: three.js, LITE: 2.5D) is the home screen; every practice is an object. Touching one glides the
   camera in and opens the practice in a glass-and-gold panel: the panel shows the app's own views (same API, auth,
   i18n, economy and readings as the classic UI), which this module never duplicates. */

const V = new URL(import.meta.url).searchParams.get("v") || "dev";
const load = (name) => import(new URL(`./${name}.js?v=${V}`, import.meta.url).href);
const THREE_URL = new URL("../vendor/three-0.160.0.module.min.js", import.meta.url).href;

function css() {
  return new Promise((resolve) => {
    const l = document.createElement("link"); l.rel = "stylesheet"; l.href = new URL(`./chamber.css?v=${V}`, import.meta.url).href;
    l.onload = l.onerror = resolve; document.head.append(l); setTimeout(resolve, 3000);
  });
}

function webglOK() {
  try { const c = document.createElement("canvas"); return !!(c.getContext("webgl2", { failIfMajorPerformanceCaveat: true }) || c.getContext("webgl", { failIfMajorPerformanceCaveat: true })); }
  catch { return false; }
}
/* FULL on capable phones; LITE on Telegram Desktop and the web, on weak phones, without fast WebGL and with reduced
   motion. ?tier=full|lite or the Profile choice override it. */
export function chooseTier(B) {
  let forced = null; try { forced = new URLSearchParams(location.search).get("tier") || B.store.get("astro.chTier"); } catch {}
  if (forced === "full" || forced === "lite") return { tier: forced, forced: true };
  if (B.reduced) return { tier: "lite", why: "reduced-motion" };
  if (["tdesktop", "macos", "weba", "webk", "web", "unigram"].includes(B.PERF.plat)) return { tier: "lite", why: "desktop" };
  if (!(B.tg && B.tg.initData) && matchMedia("(pointer: fine)").matches) return { tier: "lite", why: "desktop" };
  if ((navigator.hardwareConcurrency || 8) <= 4 || (navigator.deviceMemory || 8) <= 3) return { tier: "lite", why: "weak" };
  if (B.store.get("astro.chSlow") === "1") return { tier: "lite", why: "slow-before" };
  if (!webglOK()) return { tier: "lite", why: "no-webgl" };
  return { tier: "full" };
}

const ICON = {
  compass: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="9.5"/><circle cx="12" cy="12" r="7" stroke-opacity=".4"/><path d="M12 4.5l2.2 7.5L12 19.5 9.8 12z" fill="currentColor" fill-opacity=".25"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2"/></svg>',
  coin: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="11" fill="#e2bd6a"/><circle cx="12" cy="12" r="8.2" fill="none" stroke="#7d5c24" stroke-width=".8"/><path d="M12 6.5l1.4 4.1 4.1 1.4-4.1 1.4L12 17.5l-1.4-4.1L6.5 12l4.1-1.4z" fill="#5b3f12"/></svg>',
  prev: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" aria-hidden="true"><path d="M15 5l-7 7 7 7"/></svg>',
  next: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" aria-hidden="true"><path d="M9 5l7 7-7 7"/></svg>',
  x: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18"/></svg>',
};

export async function start(B) {
  performance.mark("chamber-start");
  const [st] = await Promise.all([load("stations"), css()]);
  const { STATIONS, EXTRA, STEP, byId, stationOfView, makeT } = st;
  const T = makeT(B), $ = B.$, el = B.el, html = document.documentElement;
  try { $("#splashText").textContent = T("loading"); } catch {}
  const choice = chooseTier(B);
  html.dataset.ctier = choice.tier;

  /* ── Telegram: full screen where supported, our colours, no swipe-to-close ── */
  const tg = B.tg;
  try { if (tg && tg.initData) { tg.setHeaderColor("#0d0a24"); tg.setBackgroundColor("#0d0a24"); tg.disableVerticalSwipes && tg.disableVerticalSwipes();
    if (tg.requestFullscreen && tg.isVersionAtLeast && tg.isVersionAtLeast("8.0") && ["android", "ios"].includes(tg.platform)) tg.requestFullscreen(); } } catch {}

  /* ── re-home the Home blocks the room replaces: energy + sky -> the dome's panel; numbers -> astrolabe; gift -> chest ── */
  const horo = $("#v-horo"), energies = document.querySelectorAll("#v-home .energy");
  if (energies[0]) horo.prepend(energies[0]);
  for (const id of ["#skySec", "#report"]) { const n = $(id); if (n) horo.append(n); }
  if (energies[1]) $("#v-num").prepend(energies[1]);
  const giftBox = $("#gift");

  /* ── shell ── */
  const root = el("div", "ch"); root.id = "ch";
  root.innerHTML = `
    <div class="ch-stage" id="chStage"></div>
    <header class="ch-top">
      <button class="ch-btn" id="chCompassBtn" type="button">${ICON.compass}</button>
      <span class="ch-title" id="chTitle" aria-live="polite"></span>
      <span class="ch-coins" id="chCoins">${ICON.coin}<b id="chCoinVal"></b></span>
      <button class="ch-btn ch-me" id="chMe" type="button"></button>
    </header>
    <button class="ch-arrow prev" id="chPrev" type="button">${ICON.prev}</button>
    <button class="ch-arrow next" id="chNext" type="button">${ICON.next}</button>
    <button class="ch-plaque" id="chPlaque" type="button"><b id="chName"></b><span id="chSub"></span></button>
    <p class="ch-hint" id="chHint"></p>
    <div class="ch-hud" id="chHud" hidden></div>
    <button class="ch-catch" id="chCatch" type="button" hidden></button>
    <div class="ch-compass" id="chCompass" role="dialog" aria-modal="true" hidden>
      <div class="ch-compass-in"><div class="ch-compass-head"><h2 id="chCompassTitle"></h2><button class="ch-btn" id="chCompassX" type="button">${ICON.x}</button></div>
      <div class="ch-list" id="chList"></div></div>
    </div>
    <div class="ch-intro" id="chIntro" hidden><div class="ch-intro-card"><p id="chIntroText"></p><div class="ch-intro-dots" id="chIntroDots"></div>
      <div class="ch-intro-row"><button class="btn ghost" id="chIntroSkip" type="button"></button><button class="btn" id="chIntroNext" type="button"></button></div></div></div>`;
  document.body.prepend(root);
  const scroller = $("#scroller");
  const phead = el("div", "ch-phead"); phead.innerHTML = `<i class="ch-grip" aria-hidden="true"></i><h2 id="chPTitle"></h2><div class="ch-tabs" id="chTabs" hidden></div><button class="ch-btn" id="chPClose" type="button">${ICON.x}</button>`;
  scroller.prepend(phead);

  /* coins: the classic counter stays the source of truth (setCoins); the top bar mirrors it */
  const coinSrc = $("#coinVal"), coinDst = $("#chCoinVal"), mirror = () => { coinDst.textContent = coinSrc.textContent; };
  mirror(); new MutationObserver(mirror).observe(coinSrc, { childList: true, characterData: true, subtree: true });
  const me = $("#chMe"), u0 = B.S.user || {};
  if (u0.photo_url) { const i = el("img"); i.src = u0.photo_url; i.alt = ""; me.append(i); } else me.textContent = (u0.first_name || "✦").slice(0, 1);

  /* ── engine ── */
  const state = { station: null, panel: false, compass: false, intro: false, busy: 0, opening: false };
  let engine = null;
  const ctx = {
    STATIONS, STEP, host: $("#chStage"), forced: !!choice.forced,
    onPick: (id) => open(id),
    onTurning: () => { if (!B.store.get("astro.chTurned")) B.store.set("astro.chTurned", "1"); },
    onTurned: (i) => { plaque(i); },
    onLook: (on) => { plaque(); syncBack(); },
    onTapFocused: () => {},
    onSlow: () => swapToLite("slow"), onLost: () => swapToLite("lost"),
  };
  async function makeEngine(tier) {
    if (tier === "full") {
      const [THREE, tex, fx, room, full, post] = await Promise.all([import(THREE_URL), load("tex"), load("fx"), load("room"), load("full"), load("post")]);
      return full.createFull(THREE, B, ctx, { tex, fx, room, post });
    }
    const lite = await load("lite"); return lite.createLite(B, ctx);
  }
  try { engine = await makeEngine(choice.tier); }
  catch (e) { console.warn("chamber full tier failed, using lite", e); html.dataset.ctier = "lite"; engine = await makeEngine("lite"); }
  async function swapToLite(why) {
    if (engine.tier !== "full") return; console.warn("chamber: switching to the light version", why);
    if (why === "slow") B.store.set("astro.chSlow", "1");
    const old = engine; html.dataset.ctier = "lite"; engine = await makeEngine("lite"); old.dispose(); refreshNew(); plaque();
  }

  /* ── labels ── */
  const stationName = (s) => T("st_" + s.id);
  function plaque(i) {
    const up = engine.up, s = up ? byId("horo") : STATIONS[i != null ? i : engine.index()];
    $("#chName").textContent = stationName(s); $("#chSub").textContent = up ? T("domeTap") : T("sub_" + s.id);
    $("#chPlaque").setAttribute("aria-label", `${stationName(s)}: ${up ? T("domeTap") : T("sub_" + s.id)}`);
    $("#chHint").textContent = up ? T("down") : B.store.get("astro.chTurned") ? T("up") : T("swipe");
    $("#chTitle").textContent = "";
  }
  function texts() {
    $("#chCompassBtn").setAttribute("aria-label", T("compass")); $("#chCompassTitle").textContent = T("compass");
    $("#chCompassX").setAttribute("aria-label", T("close")); $("#chPClose").setAttribute("aria-label", T("toRoom"));
    $("#chMe").setAttribute("aria-label", T("profile")); $("#chPrev").setAttribute("aria-label", "‹"); $("#chNext").setAttribute("aria-label", "›");
    $("#chCatch").setAttribute("aria-label", T("toRoom"));
    $("#chList").replaceChildren(...[...STATIONS, ...EXTRA].map((s) => {
      const b = el("button", "ch-item"); b.type = "button"; b.dataset.id = s.id;
      const art = el("span", "ch-item-art"); art.innerHTML = B.practiceArt(s.art, { draw: false, glow: "#e2bd6a" });
      const txt = el("span", "ch-item-txt"); txt.append(el("b", null, stationName(s)), el("small", null, T("sub_" + s.id)));
      const dot = el("i", "ch-item-new"); dot.setAttribute("aria-label", T("newToday"));
      b.append(art, txt, dot); b.addEventListener("click", () => { closeCompass(); open(s.id); }); return b; }));
    plaque(); refreshNew();
  }

  /* ── "something new today" glow ── */
  function newMap() {
    const u = B.S.user || {}, day = B.todayKey(), seen = (k) => B.store.get("astro.chSeen." + k) === day;
    return { gift: u.daily_reward_available !== false, tarot: !seen("tarot"), horo: !!u.birth_date && !seen("horo"), moon: !seen("moon") };
  }
  function refreshNew() {
    const m = newMap(); engine.setNew(m);
    document.querySelectorAll("#chList .ch-item").forEach((b) => b.classList.toggle("is-new", !!m[b.dataset.id]));
  }

  /* ── panel ── */
  function setPanelHead(name, s) {
    $("#chPTitle").textContent = s ? stationName(s) : "";
    const tabs = $("#chTabs"); tabs.hidden = !(s && s.id === "chart");
    if (!tabs.hidden) tabs.replaceChildren(...[["kundli", "tabKundli"], ["compat", "tabCompat"]].map(([v, k]) => {
      const b = el("button", null, T(k)); b.type = "button"; b.setAttribute("aria-pressed", String(name === v)); b.addEventListener("click", () => B.go(v)); return b; }));
  }
  let pauseTimer;
  function openPanel(name, s) {
    setPanelHead(name, s);
    if (!state.panel) { state.panel = true; scroller.scrollTop = 0; requestAnimationFrame(() => scroller.classList.add("ch-open")); $("#chCatch").hidden = false; root.classList.add("panel-on"); }
    clearTimeout(pauseTimer); pauseTimer = setTimeout(() => { if (state.panel) engine.pause(true); }, 1000);
    syncBack();
  }
  /* end whatever is open (a stage, the panel) without moving the camera: the next glide starts from here */
  function leaveCurrent() {
    clearTimeout(pauseTimer);
    if (state.panel) { state.panel = false; scroller.classList.remove("ch-open"); $("#chCatch").hidden = true; root.classList.remove("panel-on"); }
    engine.pause(false);
    if (state.stage) { try { state.stage.end(); } catch (e) { console.warn("stage end", e); } state.stage = null; engine.setStage(null); $("#chHud").hidden = true; root.classList.remove("stage-on"); }
  }
  async function closeAll() {
    if (state.closing) return; state.closing = true;
    leaveCurrent();
    await engine.unfocus(); state.station = null; state.closing = false;
    refreshNew(); plaque(); syncBack();
  }
  async function hidePanel() {   // inside a stage, closing the panel returns to the object (the cards, the wheel)
    if (!state.panel) return; state.panel = false; clearTimeout(pauseTimer); scroller.classList.remove("ch-open"); $("#chCatch").hidden = true;
    root.classList.remove("panel-on"); engine.pause(false); await engine.refocus("stage"); syncBack();
  }
  B.S.onGo = (name) => {
    if (name === "home") { if (state.stage && state.panel) hidePanel(); else closeAll(); return; }
    const s = name === "chamber" ? byId(state.station) : stationOfView(name);
    if (s && s.id !== "profile" && engine.focused !== s.id && !state.opening) { state.station = s.id; engine.focus(s.id, "panel"); }
    openPanel(name, s);
  };
  B.S.onBack = () => {
    if (state.compass) { closeCompass(); return true; }
    if (state.intro) { endIntro(); return true; }
    if (!state.panel && !engine.focused && engine.up) { engine.lookUp(false); return true; }
    return false;   // the app then calls go("home"), which closes everything
  };
  function syncBack() {
    const show = state.panel || !!engine.focused || state.compass || engine.up;
    try { if (show) tg.BackButton.show(); else tg.BackButton.hide(); } catch {}
  }

  /* ── interactive stages (FULL): the object itself is the interface; the panel comes for the reading ── */
  const STAGES = { tarot: "stage-tarot", sphere: "stage-sphere", gift: "stage-gift", horo: "stage-horo", moon: "stage-moon", coffee: "stage-coffee" };
  /* sound: off by default; the module loads on the first gesture after it is switched on (Profile) */
  let soundMod = null;
  const sound = { play(n) { if (soundMod) soundMod.play(n); } };
  async function soundOn() { if (!soundMod) soundMod = (await load("sound")).createSound(); await soundMod.enable(); }
  addEventListener("pointerdown", () => { if (B.store.get("astro.sound") === "on") soundOn(); }, { once: true, capture: true });
  document.addEventListener("astro:sound", (e) => { if (e.detail) soundOn(); else if (soundMod) soundMod.disable(); });
  async function openStage(id) {
    if (engine.tier !== "full" || !STAGES[id]) return false;
    const [mod] = await Promise.all([load(STAGES[id]), engine.focus(id, "stage")]);
    const hud = $("#chHud"); hud.replaceChildren(); hud.hidden = false; root.classList.add("stage-on");
    const ui = {
      hud, T,
      panel(nodes, title) { $("#chPanel").replaceChildren(...[].concat(nodes)); engine.refocus("panel"); B.go("chamber"); if (title) $("#chPTitle").textContent = title; },
      hidePanel,
      sound: (name) => sound.play(name),
      coinsTarget: () => $("#chCoins"),
    };
    const stage = mod.createStage({ THREE: engine.THREE, engine, room: engine.room, station: engine.room.stations.get(id), B, T, ui, F: engine.F, X: engine.X });
    state.stage = stage; engine.setStage(stage); await stage.start(); syncBack();
    return true;
  }

  /* ── opening a station ── */
  async function open(id) {
    if (state.opening) return; const s = byId(id); if (!s) return;
    state.opening = true; B.haptic.tap(); sound.play("pick");
    if (state.stage || (state.panel && state.station !== id)) leaveCurrent();   // e.g. another object chosen from the compass
    state.station = id;
    if (["tarot", "horo", "moon"].includes(id)) B.store.set("astro.chSeen." + id, B.todayKey());
    try {
      if (id === "profile") { B.go("profile"); return; }
      if (await openStage(id)) return;
      const glide = engine.focus(id, "panel");
      await new Promise((r) => setTimeout(r, B.reduced ? 0 : 380));   // the panel rises while the camera arrives
      if (id === "gift") { B.renderGift(); $("#chPanel").replaceChildren(giftBox); B.go("chamber"); }
      else B.go(s.view);
      if (id === "num") { const n = numbers(); if (n) { engine.react("num", n); awake(3500); } }
      await glide;
    } finally { state.opening = false; }
  }

  /* ── compass (direct access, also for screen readers) ── */
  function openCompass() { state.compass = true; const c = $("#chCompass"); c.hidden = false; requestAnimationFrame(() => c.classList.add("on")); refreshNew(); syncBack();
    setTimeout(() => { const f = c.querySelector(".ch-item"); f && f.focus({ preventScroll: true }); }, 60); }
  function closeCompass() { if (!state.compass) return; state.compass = false; const c = $("#chCompass"); c.classList.remove("on"); setTimeout(() => { if (!state.compass) c.hidden = true; }, 300); syncBack(); $("#chCompassBtn").focus({ preventScroll: true }); }

  /* ── first visit: a short guided intro; a floating light visits the main objects ── */
  let introStep = 0;
  function showIntro() { state.intro = true; introStep = 0; root.classList.add("intro-on"); $("#chIntro").hidden = false; requestAnimationFrame(() => $("#chIntro").classList.add("on")); introRender(); syncBack(); }
  function introRender() {
    $("#chIntroText").textContent = T("intro" + (introStep + 1));
    $("#chIntroDots").replaceChildren(...[0, 1, 2].map((i) => el("i", i === introStep ? "on" : "")));
    $("#chIntroSkip").textContent = T("skip"); $("#chIntroNext").textContent = introStep === 2 ? T("begin") : T("next");
    engine.guide(introStep);
  }
  function endIntro() { state.intro = false; root.classList.remove("intro-on"); B.store.set("astro.chIntro", "1"); $("#chIntro").classList.remove("on"); setTimeout(() => { $("#chIntro").hidden = true; }, 300); engine.endGuide(); syncBack(); plaque(); }
  $("#chIntroNext").addEventListener("click", () => { B.haptic.tap(); if (introStep < 2) { introStep++; introRender(); } else endIntro(); });
  $("#chIntroSkip").addEventListener("click", () => { B.haptic.tap(); endIntro(); });

  /* ── wiring ── */
  $("#chCompassBtn").addEventListener("click", () => (state.compass ? closeCompass() : openCompass()));
  $("#chCompassX").addEventListener("click", closeCompass);
  $("#chCompass").addEventListener("click", (e) => { if (e.target.id === "chCompass") closeCompass(); });
  $("#chMe").addEventListener("click", () => open("profile"));
  $("#chPlaque").addEventListener("click", () => open(engine.up ? "horo" : STATIONS[engine.index()].id));
  $("#chPrev").addEventListener("click", () => { B.haptic.tap(); engine.step(-1); });
  $("#chNext").addEventListener("click", () => { B.haptic.tap(); engine.step(1); });
  $("#chCatch").addEventListener("click", () => B.go("home"));
  $("#chPClose").addEventListener("click", () => B.go("home"));
  { let y0 = null; phead.addEventListener("pointerdown", (e) => { if (e.target.closest("button")) return; y0 = e.clientY; scroller.classList.add("ch-drag"); try { phead.setPointerCapture(e.pointerId); } catch {} });
    phead.addEventListener("pointermove", (e) => { if (y0 == null) return; const d = Math.max(0, e.clientY - y0); scroller.style.transform = `translateY(${d}px)`; });
    const end = (e) => { if (y0 == null) return; const d = e.clientY - y0; y0 = null; scroller.classList.remove("ch-drag"); scroller.style.transform = ""; if (d > 90) B.go("home"); };
    phead.addEventListener("pointerup", end); phead.addEventListener("pointercancel", end); }
  addEventListener("keydown", (e) => {
    if (state.panel || state.compass || state.intro || /input|textarea/i.test((e.target.tagName || ""))) return;
    if (e.key === "ArrowLeft") engine.step(-1); else if (e.key === "ArrowRight") engine.step(1);
    else if (e.key === "ArrowUp") engine.lookUp(true); else if (e.key === "ArrowDown") engine.lookUp(false);
    else if (e.key === "Enter" && e.target === document.body) open(engine.up ? "horo" : STATIONS[engine.index()].id);
  });
  /* the room keeps rendering for a moment when something reacts behind the panel (the oracle thinking, a reading) */
  function awake(ms) { engine.pause(false); clearTimeout(pauseTimer); pauseTimer = setTimeout(() => { if (state.panel && !state.busy) engine.pause(true); }, ms); }
  document.addEventListener("astro:busy", (e) => { state.busy = Math.max(0, state.busy + (e.detail.on ? 1 : -1)); engine.setBusy(state.busy > 0, e.detail.path);
    if (state.panel) awake(state.busy ? 60000 : 1500); });
  document.addEventListener("astro:vision", (e) => { if (e.detail.kind === "aura") { engine.react("aura", e.detail.reading.colors); if (state.panel) awake(5000); } });
  document.addEventListener("astro:compat", () => { engine.react("compat"); if (state.panel) awake(9000); });
  { const d = $("#dreamText"); if (d) d.addEventListener("input", () => { engine.react("quill"); if (state.panel) awake(1200); }); }
  function numbers() {   // life path, personal year (birth day + month + this year, reduced) and the first number of the day
    const u = B.S.user || {}; if (!u.birth_date) return null;
    const [, m, d] = u.birth_date.split("-").map(Number); let py = [...`${d}${m}${new Date().getFullYear()}`].reduce((a, c) => a + +c, 0);
    while (py > 9) py = [...String(py)].reduce((a, c) => a + +c, 0);
    return { lp: u.life_path, py, lucky: B.S.energy && B.S.energy.lucky_numbers ? B.S.energy.lucky_numbers[0] : null };
  }
  document.addEventListener("astro:energy", refreshNew);
  const skyNow = () => { if (B.S.sky) engine.setSky(B.S.sky); }; skyNow(); document.addEventListener("astro:sky", skyNow);
  // the language can change in the Profile panel: re-label the chamber
  new MutationObserver(texts).observe(document.documentElement, { attributes: true, attributeFilter: ["lang"] });

  texts(); syncBack();
  if (!B.store.get("astro.chIntro")) setTimeout(showIntro, 700);
  const day = B.todayKey();
  if (engine.room && engine.room.birthday && B.store.get("astro.chBday") !== day) { B.store.set("astro.chBday", day); setTimeout(() => B.toast(T("birthday")), 1600); }

  // scripts (demo only) can drive the chamber
  if (B.S.demo) window.__chamber = { open, close: () => B.go("home"), turn: (i) => engine.turnTo(i), up: (on) => engine.lookUp(on), get engine() { return engine; },
    compass: () => openCompass(), state, tier: () => engine.tier, STATIONS };
  performance.mark("chamber-ready");
  return { tier: engine.tier };
}
