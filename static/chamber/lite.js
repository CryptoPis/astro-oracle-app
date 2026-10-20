/* Oracle chamber (LITE tier): the same room in 2.5D. Layers (stone wall, arched niches with the objects as gold
   engravings, candle glows, the floor) move at different depths while swiping. No WebGL; only transforms and
   opacity animate. Same interface as the FULL engine (full.js). */

export async function createLite(B, ctx) {
  const { STATIONS } = ctx, host = ctx.host, n = STATIONS.length;
  const root = document.createElement("div"); root.className = "lt"; root.setAttribute("aria-hidden", "true");
  root.innerHTML = `<div class="lt-wall"></div><div class="lt-track"></div><div class="lt-floor"></div><div class="lt-dome"><div class="lt-dome-in"></div></div><i class="lt-orb"></i><div class="lt-vig"></div>`;
  host.append(root);
  const wall = root.querySelector(".lt-wall"), track = root.querySelector(".lt-track"), floor = root.querySelector(".lt-floor"), domeIn = root.querySelector(".lt-dome-in"), orb = root.querySelector(".lt-orb");
  wall.style.backgroundImage = `url(${stoneUrl()})`;

  const bays = STATIONS.map((st) => {
    const bay = document.createElement("div"); bay.className = "lt-bay"; bay.dataset.id = st.id;
    bay.innerHTML = `<div class="lt-niche"></div><div class="lt-medal">${B.practiceArt(st.art, { draw: false, glow: "#e2bd6a" })}</div>
      <div class="lt-obj"><div class="lt-art">${objectArt(st)}</div><i class="lt-ped"></i></div><i class="lt-candle l"></i><i class="lt-candle r"></i><i class="lt-new"></i>`;
    track.append(bay); return bay;
  });
  // the moon window shows the real phase
  { const bay = bays[STATIONS.findIndex((s) => s.id === "moon")], c = document.createElement("canvas"); c.className = "lt-moon"; c.width = c.height = 160;
    const m = B.moonNow(); try { B.drawMoon(c.getContext("2d"), 80, 80, 46, (m.age_days || 0) / 29.53); } catch {}
    bay.querySelector(".lt-art").prepend(c); }
  // the dome: the same live zodiac wheel as the classic Home (it is rendered there from /api/sky)
  const fillDome = () => { const w = document.getElementById("wheel"); if (w && w.innerHTML) domeIn.innerHTML = `<svg viewBox="0 0 320 320" class="lt-wheel">${w.innerHTML}</svg>`; };
  const onSky = () => requestAnimationFrame(fillDome);   // the classic wheel is drawn right after the event
  fillDome(); document.addEventListener("astro:sky", onSky);

  /* ── layout: each bay sits at its offset from the current one; only neighbours are shown ── */
  let cur = 0, dragX = 0, up = false, focused = null, anim = false;
  const W = () => innerWidth;
  const rel = (i) => { let r = (i - cur) % n; if (r > n / 2) r -= n; if (r < -n / 2) r += n; return r; };
  function layout(withAnim) {
    const w = W(); root.classList.toggle("lt-anim", !!withAnim);
    bays.forEach((b, i) => { const r = rel(i), x = r * w + dragX; b.hidden = Math.abs(r) > 1; b.style.transform = `translate3d(${x}px,0,0)`; });
    const off = ((((-cur * w * .55 + dragX * .55) % 256) + 256) % 256) - 256;   // the stone tile is 256 px: seamless
    wall.style.transform = `translate3d(${off}px,0,0)`;
    floor.style.transform = `translate3d(${dragX * 1.25}px,0,0)`;
  }
  function settle(dir) {
    anim = true; dragX = -dir * W(); layout(true);
    setTimeout(() => { cur = (cur + dir + n) % n; dragX = 0; layout(false); anim = false; ctx.onTurned(cur); }, B.reduced ? 0 : 480);
  }
  layout(false);

  /* ── input ── */
  let ptr = null;
  root.addEventListener("pointerdown", (e) => { if (anim) return; ptr = { x: e.clientX, y: e.clientY, t: performance.now(), axis: null }; try { root.setPointerCapture(e.pointerId); } catch {} });
  root.addEventListener("pointermove", (e) => { if (!ptr || focused) return; const dx = e.clientX - ptr.x, dy = e.clientY - ptr.y;
    if (!ptr.axis && Math.hypot(dx, dy) > 8) ptr.axis = Math.abs(dx) > Math.abs(dy) ? "x" : "y";
    if (ptr.axis === "x" && !up) { dragX = dx; layout(false); ctx.onTurning(); }
    if (ptr.axis === "y" && Math.abs(dy) > 50 && !ptr.done) { ptr.done = true; if (dy < 0 && !up) api.lookUp(true); else if (dy > 0 && up) api.lookUp(false); } });
  const end = (e) => { if (!ptr) return; const p = ptr; ptr = null;
    if (!p.axis && performance.now() - p.t < 450) { if (focused) return ctx.onTapFocused && ctx.onTapFocused(e);
      if (up) { ctx.onPick("horo"); return; }
      const hit = e.target.closest && e.target.closest(".lt-obj, .lt-niche, .lt-medal"); if (hit) ctx.onPick(hit.closest(".lt-bay").dataset.id); return; }
    if (p.axis === "x") { const dx = e.clientX - p.x, v = dx / Math.max(1, performance.now() - p.t);
      if (dx < -W() * .18 || v < -.45) settle(1); else if (dx > W() * .18 || v > .45) settle(-1); else { dragX = 0; layout(true); } } };
  root.addEventListener("pointerup", end); root.addEventListener("pointercancel", end);

  const api = {
    tier: "lite", root,
    index: () => cur, get up() { return up; },
    turnTo(i) { if (focused) return; i = ((i % n) + n) % n; if (i === cur) return; const r = rel(i);
      if (Math.abs(r) === 1) { settle(r); return; } cur = i; dragX = 0; layout(false); ctx.onTurned(cur); },
    step(d) { if (!anim) settle(d > 0 ? 1 : -1); },
    lookUp(on) { if (focused) return; up = on; root.classList.toggle("lt-up", on); ctx.onLook(on); B.haptic.soft(); },
    async focus(id, mode = "panel") {
      const i = STATIONS.findIndex((s) => s.id === id);
      if (i >= 0) { if (up) api.lookUp(false); if (i !== cur) { cur = i; dragX = 0; layout(false); } }
      focused = id; root.classList.add("lt-focus"); root.dataset.mode = mode;
      const bay = bays[i]; bays.forEach((b) => b.classList.toggle("lt-on", b === bay));
      await wait(B.reduced ? 0 : 900);
    },
    async refocus(mode) { root.dataset.mode = mode; await wait(480); },
    async unfocus() { if (!focused) return; root.classList.remove("lt-focus"); bays.forEach((b) => b.classList.remove("lt-on")); await wait(B.reduced ? 0 : 900); focused = null; },
    get focused() { return focused; },
    pause(on) { root.classList.toggle("lt-paused", on); },
    setNew(map) { for (const [id, v] of Object.entries(map)) { const i = STATIONS.findIndex((s) => s.id === id); if (i >= 0) bays[i].classList.toggle("is-new", !!v); }
      root.classList.toggle("dome-new", !!map.horo); },
    setBusy(on) { root.classList.toggle("lt-busy", on); },
    guide(step) { const ids = ["tarot", "sphere", "horo"], id = ids[step]; orb.classList.add("on");
      if (id === "horo") { api.lookUp(true); orb.style.transform = "translate3d(50vw, 22vh, 0)"; return; }
      if (up) api.lookUp(false); api.turnTo(STATIONS.findIndex((s) => s.id === id)); orb.style.transform = "translate3d(50vw, 40vh, 0)"; },
    endGuide() { orb.classList.remove("on"); if (up) api.lookUp(false); },
    setStage() {}, kick() {},
    dispose() { document.removeEventListener("astro:sky", onSky); root.remove(); },
  };
  return api;
}
const wait = (ms) => new Promise((r) => setTimeout(r, ms));

/* each object, drawn as large gold line art in its niche (the app's engraving style) */
function objectArt(st) {
  const G = "#e2bd6a", s = (body) => `<svg viewBox="0 0 200 240" fill="none" stroke="${G}" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">${body}</svg>`;
  const A = {
    tarot: `<ellipse cx="100" cy="170" rx="86" ry="18"/><path d="M14 170v8q86 30 172 0v-8"/><path d="M92 196v34M108 196v34M70 232h60"/>
      <rect x="62" y="132" width="34" height="22" rx="2" transform="rotate(-12 79 143)"/><rect x="104" y="134" width="34" height="22" rx="2" transform="rotate(10 121 145)"/>
      <path d="M150 150v-24" /><path d="M150 118q4 6 0 10q-4-4 0-10z" fill="${G}" fill-opacity=".5"/>`,
    sphere: `<circle cx="100" cy="92" r="52"/><path d="M68 70q32-26 62 4" stroke-opacity=".5"/><path d="M76 108q24 14 50-4" stroke-opacity=".35"/>
      <path d="M70 142q30 12 60 0M80 146l-8 40M120 146l8 40M60 190h80M70 190l-10 34h80l-10-34"/>`,
    moon: `<path d="M50 220V90a50 50 0 0 1 100 0v130z"/><path d="M100 40v180M50 140h100" stroke-opacity=".7"/><path d="M36 224h128"/>
      <path d="M70 224v-12M100 224v-16M130 224v-10" stroke-opacity=".6"/>`,
    advisor: `<path d="M100 60q16 22 0 40q-16-18 0-40z" fill="${G}" fill-opacity=".35"/><rect x="86" y="104" width="28" height="64" rx="3"/>
      <path d="M70 170h60l-10 14h-40zM96 184v30M70 220h60l-6-6h-48z"/>`,
    dream: `<path d="M40 120q30-12 60 4q30-16 60-4v54q-30-12-60 4q-30-16-60-4z"/><path d="M100 124v54"/><path d="M52 136q20-6 40 2M52 150q20-6 40 2M108 138q20-8 40-2M108 152q20-8 40-2" stroke-opacity=".45"/>
      <path d="M150 112l26-50" /><path d="M176 62q-14 6-18 24q14-4 18-24z" fill="${G}" fill-opacity=".3"/><path d="M96 182l-8 48M104 182l8 48M76 232h48"/>`,
    num: `<circle cx="100" cy="110" r="70"/><circle cx="100" cy="110" r="56" stroke-opacity=".7"/><circle cx="100" cy="110" r="38" stroke-opacity=".6"/>
      <path d="M100 40v-14M92 26h16M100 110l40-30M100 110l-30 38" /><circle cx="100" cy="110" r="4" fill="${G}"/>`,
    chart: `<rect x="40" y="110" width="120" height="70" rx="4"/><path d="M34 106v78M166 106v78" stroke-width="5" stroke-opacity=".7"/>
      <path d="M62 160l22-26 26 12 24-22" stroke-opacity=".7"/><circle cx="62" cy="160" r="3" fill="${G}"/><circle cx="84" cy="134" r="3" fill="${G}"/><circle cx="110" cy="146" r="3" fill="${G}"/><circle cx="134" cy="124" r="3" fill="${G}"/>
      <path d="M60 182l-6 48M140 182l6 48M50 230h100"/>`,
    aura: `<ellipse cx="100" cy="104" rx="58" ry="84"/><ellipse cx="100" cy="104" rx="48" ry="74" stroke-opacity=".5"/><path d="M70 196l-12 36M130 196l12 36"/>
      <path d="M78 80q22-20 44 0" stroke-opacity=".4"/>`,
    coffee: `<ellipse cx="100" cy="190" rx="70" ry="14"/><path d="M62 132h76l-8 46q-30 12-60 0z"/><ellipse cx="100" cy="132" rx="38" ry="8" fill="${G}" fill-opacity=".15"/>
      <path d="M138 142q22 2 14 22q-6 8-18 6"/><path d="M84 116q4-10 0-18M104 114q4-12 0-22M120 116q4-10 0-18" stroke-opacity=".45"/>`,
    gift: `<rect x="40" y="140" width="120" height="70" rx="4"/><path d="M40 140q0-50 60-50t60 50"/><path d="M70 90v120M130 90v120" stroke-opacity=".7"/>
      <rect x="92" y="132" width="16" height="22" rx="2" fill="${G}" fill-opacity=".35"/><path d="M60 82l6-10M100 70v-14M140 82l-6-10" stroke-opacity=".6"/>`,
  };
  return s(A[st.id] || A.sphere);
}

/* a small stone texture for the LITE wall (painted once) */
function stoneUrl() {
  const c = document.createElement("canvas"); c.width = 256; c.height = 256; const x = c.getContext("2d");
  x.fillStyle = "#211c3a"; x.fillRect(0, 0, 256, 256);
  let seed = 7; const r = () => { seed = (seed * 16807) % 2147483647; return seed / 2147483647; };
  for (let row = 0; row < 8; row++) { let px = row % 2 ? -20 : 0; while (px < 256) { const w = 40 + r() * 46, l = 24 + r() * 14;
    x.fillStyle = `hsl(250, 18%, ${l * .55}%)`; x.fillRect(px + 1.5, row * 32 + 1.5, w - 3, 29); px += w; } }
  x.globalAlpha = .12; for (let i = 0; i < 1500; i++) { x.fillStyle = r() < .5 ? "#000" : "#6a5f9a"; x.fillRect(r() * 256, r() * 256, 1.5, 1.5); }
  return c.toDataURL("image/png");
}
