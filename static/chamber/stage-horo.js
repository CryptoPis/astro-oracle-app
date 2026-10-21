/* Oracle chamber (FULL): the horoscope in 3D under the star dome. The natal wheel floats as a gold ring with the
   person's planets as glowing orbs; the period's transiting planets glide round the outer ring to their real places;
   the transits the reading is built on are beams of light between a transiting and a natal planet (gold conjunction,
   calm teal harmony, crimson tension that visibly crackles). Touch a beam: its meaning from the knowledge base and
   why it matters (the sections of the reading that rest on it). Data: GET /api/horoscope/chart (read-only, no AI)
   and the reading itself (GET /api/horoscope). Without a birth date: today's sky and the sign horoscope. */

const TX = {
  ka: { hint: "შეეხე სინათლის სხივს: გაიგე, რას ნიშნავს და რატომ", read: "მთლიანი ჰოროსკოპი", noDate: "მიუთითე დაბადების თარიღი და გუმბათი შენს ნატალურ რუკას აჩვენებს.",
    toProfile: "დაბადების მონაცემები", whyIn: "ამ ტრანზიტს ეყრდნობა შენი ჰოროსკოპის ნაწილები:", calm: "ამ პერიოდში ძლიერი ასპექტი არ არის: მშვიდი, თანაბარი დროა.",
    sky: "ცა ახლა", loading: "ვარსკვლავები ლაგდებიან…" },
  en: { hint: "Touch a beam of light: what it means, and why", read: "The whole horoscope", noDate: "Add your birth date and the dome will show your own natal chart.",
    toProfile: "Birth data", whyIn: "These parts of your horoscope rest on this transit:", calm: "No strong aspects this period: a calm, steady time.",
    sky: "The sky now", loading: "The stars are taking their places…" },
  ru: { hint: "Коснись луча света: что он значит и почему", read: "Весь гороскоп", noDate: "Укажи дату рождения, и купол покажет твою натальную карту.",
    toProfile: "Данные рождения", whyIn: "На этот транзит опираются части твоего гороскопа:", calm: "В этот период нет сильных аспектов: спокойное, ровное время.",
    sky: "Небо сейчас", loading: "Звёзды занимают свои места…" },
};
const TINT = { sun: 0xffe7a0, moon: 0xe6e2ff, mercury: 0xc8d2ea, venus: 0xf6d6a8, mars: 0xff8a6a, jupiter: 0xf0c890, saturn: 0xe8d29a, uranus: 0x9fe6e0, neptune: 0x8fb0ff, pluto: 0xc9a6d8, asc: 0xe2bd6a };
const ASPECT = { conjunction: 0xf0d28e, trine: 0x7fd6c4, sextile: 0x9fd8ff, square: 0xe0607a, opposition: 0xd8507a };
const GLYPHS = ["♈", "♉", "♊", "♋", "♌", "♍", "♎", "♏", "♐", "♑", "♒", "♓"];
const R_OUT = .95, R_MID = .78, R_IN = .56, R_NATAL = .44, R_TRANSIT = 1.1;

export function createStage({ THREE, engine, B, ui, F, X }) {
  const tx = (k) => (TX[B.S.lang] || TX.en)[k], el = B.el, cam = engine.camera;
  const root = new THREE.Group(), wheel = new THREE.Group(); root.add(wheel); engine.scene.add(root);
  const disposables = [], glowMat = (color, op = 1) => { const m = new THREE.SpriteMaterial({ map: X.T.glow, color, transparent: true, opacity: op, depthWrite: false, blending: THREE.AdditiveBlending, fog: false }); disposables.push(m); return m; };
  const gold = new THREE.MeshBasicMaterial({ color: 0xe2bd6a, transparent: true, opacity: .85, fog: false }), goldDim = gold.clone(); goldDim.opacity = .35;
  disposables.push(gold, goldDim);
  const at = (lon, r) => { const a = lon * Math.PI / 180; return new THREE.Vector3(-Math.cos(a) * r, -Math.sin(a) * r, 0); };   // Aries at nine o'clock, as in the app's wheel

  /* place the wheel in front of the dome, facing the eye, in the free band between the HUD above and the foot below
     (measured: the chips and buttons never cover the ring), as large as that band and the screen width allow */
  let fit = 1;
  const D = 3.25, R_ALL = R_TRANSIT + .1;   // the outermost orbs and their halos
  function placeWheel() {
    const hb = ui.hud.getBoundingClientRect(), fb = foot.getBoundingClientRect(), W = innerWidth, H = innerHeight;
    const top = (ui.hud.hidden || !hb.height ? 70 : hb.bottom) + 10, bot = (fb.height ? fb.top : H - 90) - 10;
    const pxPerM = H / (2 * D * Math.tan(cam.fov * Math.PI / 360));
    fit = Math.max(.45, Math.min(1, (bot - top) / 2 / (R_ALL * pxPerM), (W / 2 - 6) / (R_ALL * pxPerM)));
    const cy = (top + bot) / 2, ndc = new THREE.Vector3(0, 1 - 2 * cy / H, .5).unproject(cam).sub(cam.position).normalize();
    root.position.copy(cam.position).addScaledVector(ndc, D); root.lookAt(cam.position); }
  const relayout = () => requestAnimationFrame(placeWheel);

  /* ── the fixed wheel: rings, sign divisions, glyph sprites ── */
  const geos = [];
  const ring = (r, mat, tube = .01) => { const g = new THREE.TorusGeometry(r, tube, 6, 128); geos.push(g); const m = new THREE.Mesh(g, mat); wheel.add(m); return m; };
  ring(R_OUT, gold, .012); ring(R_MID, gold, .007); ring(R_IN, goldDim, .005);
  const tickGeo = new THREE.BoxGeometry(.006, R_OUT - R_MID, .006); geos.push(tickGeo);
  for (let i = 0; i < 12; i++) { const t = new THREE.Mesh(tickGeo, gold), p = at(i * 30, (R_OUT + R_MID) / 2); t.position.copy(p); t.rotation.z = Math.atan2(p.y, p.x) + Math.PI / 2; wheel.add(t);
    const g = glyph(GLYPHS[i]); g.position.copy(at(i * 30 + 15, (R_OUT + R_MID) / 2)); wheel.add(g); }
  for (let d = 0; d < 360; d += 5) if (d % 30) { const m = new THREE.Mesh(tickGeo, goldDim), p = at(d, R_OUT - .025); m.scale.y = .2; m.position.copy(p); m.rotation.z = Math.atan2(p.y, p.x) + Math.PI / 2; wheel.add(m); }
  function glyph(ch) {   // zodiac signs are symbols (as in the app's own wheel), drawn small in gold
    const c = document.createElement("canvas"); c.width = c.height = 64; const x = c.getContext("2d");
    x.font = '40px "Noto Sans Symbols", "Segoe UI Symbol", "DejaVu Sans", serif'; x.textAlign = "center"; x.textBaseline = "middle"; x.fillStyle = "#f0d28e"; x.fillText(ch + "︎", 32, 34);
    const t = new THREE.CanvasTexture(c); disposables.push(t); const m = new THREE.SpriteMaterial({ map: t, transparent: true, depthWrite: false, fog: false }); disposables.push(m);
    const s = new THREE.Sprite(m); s.scale.set(.09, .09, 1); return s;
  }
  const core = new THREE.Sprite(glowMat(0xffe2a8, .9)); core.scale.set(.12, .12, 1); wheel.add(core);

  /* ── planets and beams (rebuilt per period) ── */
  const dyn = new THREE.Group(); wheel.add(dyn);
  let chart = null, reading = null, beams = [], orbs = [], arrivals = [], selected = null, period = B.S.period || "day";
  const potd = B.DAY_RULER[new Date().getDay()];
  function orb(id, pos, size) {
    const g = new THREE.Group(); g.position.copy(pos);
    const halo = new THREE.Sprite(glowMat(TINT[id] || 0xffffff, .8)); halo.scale.set(size * 2.8, size * 2.8, 1); g.add(halo);
    const c = new THREE.Sprite(glowMat(0xffffff, .95)); c.scale.set(size * .7, size * .7, 1); g.add(c);
    dyn.add(g); return g;
  }
  function clear() { for (const b of beams) { b.mesh.geometry.dispose(); b.mesh.material.dispose(); b.pick.geometry.dispose(); } beams = []; orbs = []; arrivals = [];
    while (dyn.children.length) dyn.remove(dyn.children[0]); }
  const beamVS = "varying vec2 vUv; void main() { vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }";
  const beamFS = `uniform vec3 uColor; uniform float uT, uHard, uOn, uSel; varying vec2 vUv;
    void main() { float flow = 0.55 + 0.45 * sin((vUv.y * 10.0 - uT * 2.2) * 3.1416);
      float dash = mix(1.0, step(0.45, fract(vUv.y * 14.0 - uT * 1.6)), uHard);
      float crackle = mix(1.0, 0.65 + 0.35 * sin(uT * 37.0 + vUv.y * 60.0), uHard);
      float a = uOn * flow * dash * crackle * (0.55 + 0.45 * uSel); gl_FragColor = vec4(uColor * a * (1.0 + uSel), a); }`;
  function beam(item, from, to) {
    const len = from.distanceTo(to), g = new THREE.CylinderGeometry(.006, .006, len, 6, 1, true);
    const m = new THREE.ShaderMaterial({ uniforms: { uColor: { value: new THREE.Color(ASPECT[item.aspect] || 0xffffff) }, uT: { value: 0 },
      uHard: { value: item.nature === "challenging" ? 1 : 0 }, uOn: { value: 0 }, uSel: { value: 0 } }, vertexShader: beamVS, fragmentShader: beamFS,
      transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, side: THREE.DoubleSide });
    const mesh = new THREE.Mesh(g, m), mid = from.clone().lerp(to, .5); mesh.position.copy(mid);
    mesh.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), to.clone().sub(from).normalize()); dyn.add(mesh);
    const pick = new THREE.Mesh(new THREE.CylinderGeometry(.05, .05, len, 6), new THREE.MeshBasicMaterial({ visible: false })); pick.position.copy(mid); pick.quaternion.copy(mesh.quaternion);
    pick.userData.item = item; dyn.add(pick); disposables.push(pick.material);
    return { item, mesh, pick };
  }
  function build() {
    clear(); const now = performance.now();
    const natal = chart && chart.natal.points, sky = chart ? chart.sky : Object.fromEntries((B.S.sky && B.S.sky.planets || []).map((p) => [p.id, { lon: p.lon, retro: p.retro }]));
    if (natal) for (const [id, lon] of Object.entries(natal)) { const o = orb(id, at(lon, id === "asc" ? R_IN : R_NATAL), id === "sun" || id === "moon" ? .075 : .06); orbs.push(o);
      if (id === "asc") { const m = new THREE.Mesh(tickGeo, gold); const p = at(lon, R_IN + .11); m.position.copy(p); m.rotation.z = Math.atan2(p.y, p.x) + Math.PI / 2; dyn.add(m); } }
    for (const [id, p] of Object.entries(sky || {})) {
      const size = id === potd ? .085 : id === "sun" || id === "moon" ? .07 : .058, o = orb(id, at(p.lon - 40, R_TRANSIT), size); orbs.push(o);
      if (id === potd) { const h = new THREE.Sprite(glowMat(0xffd27a, .4)); h.scale.set(.42, .42, 1); o.add(h); o.userData.potd = h; }
      if (p.retro) { const rr = new THREE.Sprite(glowMat(0xff5a6a, .5)); rr.scale.set(size * 4.4, size * 4.4, 1); o.add(rr); }
      arrivals.push({ o, from: p.lon - 40, to: p.lon, t0: now + orbs.length * 70, dur: 2200 });
    }
    if (chart && natal) for (const it of chart.transits) { if (natal[it.natal] == null) continue;
      beams.push(beam(it, at(it.lon, R_TRANSIT), at(natal[it.natal], it.natal === "asc" ? R_IN : R_NATAL))); }
    hint.textContent = !chart ? tx("noDate") : chart.transits.length ? tx("hint") : tx("calm");
    relayout();
    list.replaceChildren(...(chart ? chart.transits : []).map((it) => { const b = el("button", `ch-trb ${it.nature}`, it.label); b.type = "button"; b.addEventListener("click", () => explain(it)); return b; }));
    btnProfile.hidden = !!chart;
  }

  /* ── data ── */
  async function load() {
    hint.textContent = tx("loading");
    const u = B.S.user || {};
    try { chart = u.birth_date ? await B.api("GET", `/api/horoscope/chart?period=${period}`) : null; } catch (e) { chart = null; if (e.code !== "needs_birth_date") B.showError(e); }
    build();
    B.api("GET", `/api/horoscope?period=${period}`).then((r) => { reading = r; }).catch(() => { reading = null; });
    B.store.set("astro.chSeen.horo", B.todayKey());
  }

  /* ── HUD: period, planet of the day, the whole reading ── */
  const seg = el("div", "seg ch-seg"), hint = el("p", "ch-stage-hint"), row = el("div", "ch-row"), btnRead = el("button", "btn", tx("read")), btnProfile = el("button", "btn ghost", tx("toProfile"));
  [["day", "pDay"], ["week", "pWeek"], ["month", "pMonth"]].forEach(([v, k]) => { const b = el("button", null, B.t(k)); b.type = "button"; b.dataset.v = v; b.setAttribute("aria-pressed", String(v === period));
    b.addEventListener("click", () => { if (period === v) return; period = v; B.S.period = v; B.haptic.tap(); seg.querySelectorAll("button").forEach((x) => x.setAttribute("aria-pressed", String(x === b))); load(); }); seg.append(b); });
  const day = el("p", "ch-potd"); const e = B.S.energy && B.S.energy.day;
  if (e) { const dot = el("i"); dot.style.setProperty("--dc", e.color); day.append(dot, `${B.t("dayOf")}: `, el("b", null, e.planet_name), ` · ${e.color_name} · ${e.stone} · ${e.keyword}`); } else day.hidden = true;
  btnRead.type = btnProfile.type = "button"; btnProfile.hidden = true;
  btnRead.addEventListener("click", () => { B.haptic.tap(); B.openHoro(period); });
  btnProfile.addEventListener("click", () => B.go("profile"));
  const list = el("div", "ch-tr"); hint.setAttribute("aria-live", "polite");   // the beams as buttons too (screen readers, small hands)
  row.append(btnRead, btnProfile); ui.hud.append(seg, day, hint); ui.hud.classList.add("ch-hud-dome");
  const foot = el("div", "ch-hud-foot ch-foot-col"); foot.append(list, row); document.body.append(foot);   // the transit chips sit above the button, under the wheel
  addEventListener("resize", relayout);

  /* ── a touched beam: its meaning and why ── */
  function explain(item) {
    selected = item; B.haptic.soft(); ui.sound("pick");
    const card = el("div", "ch-beam"), m = item.meaning || {};
    const head = el("h3", null, item.label); if (item.dignity) head.append(el("small", null, ` · ${item.dignity}`));
    card.append(head, el("span", `ch-nat ${item.nature}`, B.t("nat_" + item.nature)));
    if (m.meaning) card.append(el("p", "ch-beam-m", m.meaning));
    if (item.nature !== "challenging" && m.supportive) card.append(el("p", null, "＋ " + m.supportive));
    if (item.nature !== "harmonious" && m.challenging) card.append(el("p", null, "－ " + m.challenging));
    if (m.advice) card.append(el("p", "advice", m.advice));
    const secs = reading && reading.horoscope && reading.horoscope.sections ? reading.horoscope.sections.filter((s) => (s.why || []).includes(item.label)) : [];
    if (secs.length) { const w = el("div", "ch-why"); w.append(el("span", "label", tx("whyIn")));
      for (const s of secs) { const d = el("div", "area"); d.append(el("b", null, B.t(s.area)), el("p", null, s.text)); w.append(d); } card.append(w); }
    ui.panel([card]);
  }

  /* ── input: touch a beam (or a planet: the nearest beam to it) ── */
  function down(e) {
    const picks = beams.map((b) => b.pick), hit = engine.raycast(e.clientX, e.clientY, picks)[0];
    if (hit) { explain(hit.object.userData.item); return true; }
    return true;
  }

  return {
    debug: () => ({ beams: beams.map((b) => engine.project(b.pick.getWorldPosition(new THREE.Vector3()))), n: beams.length, chart: !!chart }),
    async start() { placeWheel(); root.scale.setScalar(.01); this._t0 = performance.now(); await load(); relayout(); },
    down, move() { return true; }, up() { return true; },
    update(t) {
      const now = performance.now(), k = Math.min(1, (now - this._t0) / 1400), e = engine.ease(k);
      root.scale.setScalar((.01 + .99 * e) * fit); wheel.position.y = Math.sin(t * .6) * .015;
      for (const a of arrivals) { const p = Math.min(1, Math.max(0, (now - a.t0) / a.dur)); a.o.position.copy(at(a.from + (a.to - a.from) * engine.ease(p), R_TRANSIT));
        if (a.o.userData.potd) a.o.userData.potd.material.opacity = .3 + .2 * Math.sin(t * 2); }
      const arrived = arrivals.length ? Math.min(1, Math.max(0, (now - arrivals[arrivals.length - 1].t0 - 1600) / 900)) : 1;
      for (const b of beams) { const u = b.mesh.material.uniforms; u.uT.value = t; u.uOn.value = arrived; u.uSel.value += ((selected === b.item ? 1 : 0) - u.uSel.value) * .1; }
      core.material.opacity = .7 + .2 * Math.sin(t * 1.4);
    },
    end() { removeEventListener("resize", relayout); clear(); engine.scene.remove(root); for (const g of geos) g.dispose(); for (const d of disposables) d.dispose(); foot.remove(); ui.hud.classList.remove("ch-hud-dome"); ui.hud.replaceChildren(); },
  };
}
