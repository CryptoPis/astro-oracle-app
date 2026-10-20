/* Oracle chamber (FULL): the tarot table. Swipe across the deck to shuffle (a real riffle in 3D), the cards fan
   out in an arc, drag a card up to draw it (one, or three for past/present/future), then turn each card over by
   hand. The cards themselves are drawn by the server (POST /api/tarot/draw, the same call as the classic UI);
   reversed cards land upside down. The reading appears as ink on parchment; the small box holds the collection. */

const TX = {
  ka: { shuffle: "გადაუსვი თითი დასტას და აურიე კარტები", fanOne: "კარტები გაიშალა: ერთი კარტი ზემოთ ამოწიე",
    fanThree: "ამოწიე სამი კარტი: წარსული, აწმყო, მომავალი", speaking: "კარტები ლაპარაკობენ…", flip: "შეეხე კარტს და გადმოაბრუნე",
    box: "გამოვლენილი კარტების ყუთი", boxHint: "აქ ინახება ყველა კარტი, რომელიც უკვე გაგიშლია.", shuffleBtn: "არევა", readAgain: "ამოკითხვის ნახვა",
    choose: "ამირჩიე შენ", turn: "კარტის გადმობრუნება" },
  en: { shuffle: "Swipe across the deck to shuffle the cards", fanOne: "The cards are fanned: drag one card up",
    fanThree: "Drag three cards up: past, present, future", speaking: "The cards are speaking…", flip: "Touch a card to turn it over",
    box: "The box of revealed cards", boxHint: "Every card you have drawn is kept here.", shuffleBtn: "Shuffle", readAgain: "Show the reading",
    choose: "Choose for me", turn: "Turn a card over" },
  ru: { shuffle: "Проведи по колоде, чтобы перетасовать карты", fanOne: "Карты разложены веером: вытяни одну карту вверх",
    fanThree: "Вытяни три карты: прошлое, настоящее, будущее", speaking: "Карты говорят…", flip: "Коснись карты, чтобы перевернуть её",
    box: "Шкатулка открытых карт", boxHint: "Здесь хранятся все карты, которые ты уже открыл.", shuffleBtn: "Перетасовать", readAgain: "Показать толкование",
    choose: "Выбери за меня", turn: "Перевернуть карту" },
};

export function createStage({ THREE, engine, station, B, ui, F }) {
  const tx = (k) => (TX[B.S.lang] || TX.en)[k];
  const { el, $ } = B, grp = station.grp;
  const TOP = .838, W = .118, H = .178, N = 22, FAN = 9;
  const root = new THREE.Group(); grp.add(root);
  const deckPos = new THREE.Vector3(0, TOP, -.2);
  station.deck.visible = false;

  /* materials and the card: a back plane facing up and a face plane facing down (flip = half turn round x) */
  const loader = new THREE.TextureLoader(), textures = [];
  const backTex = loader.load(B.BACK_IMG, (t) => { t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 4; }); textures.push(backTex);
  const backMat = new THREE.MeshLambertMaterial({ map: backTex, emissive: 0x000000 });
  const edgeMat = new THREE.MeshLambertMaterial({ color: 0xd8c9a6 });
  const planeGeo = new THREE.PlaneGeometry(W, H), edgeGeo = new THREE.BoxGeometry(W, .0014, H);
  const sweepMat = new THREE.ShaderMaterial({ uniforms: { uT: { value: -1 } }, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
    vertexShader: "varying vec2 vUv; void main() { vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }",
    fragmentShader: "uniform float uT; varying vec2 vUv; void main() { float d = vUv.x + vUv.y * .6 - uT * 1.9 + .3; float a = smoothstep(.16, 0., abs(d)) * .75; gl_FragColor = vec4(vec3(1., .9, .65) * a, a); }" });
  function makeCard(i) {
    const c = new THREE.Group();
    const edge = new THREE.Mesh(edgeGeo, edgeMat); c.add(edge);
    const back = new THREE.Mesh(planeGeo, backMat); back.rotation.x = -Math.PI / 2; back.position.y = .0008; c.add(back);
    const face = new THREE.Mesh(planeGeo, new THREE.MeshBasicMaterial({ color: 0x1a1440 })); face.rotation.x = Math.PI / 2; face.position.y = -.0008; c.add(face);
    c.userData = { i, face, back, flipped: false, reversed: false };
    c.position.copy(deckPos).setY(TOP + i * .0016); root.add(c); return c;
  }
  const cards = Array.from({ length: N }, (_, i) => makeCard(i));

  /* ── tiny tween system (the app's easing curve) ── */
  const tweens = new Set();
  function tween(obj, to, dur = 480, delay = 0) {
    return new Promise((resolve) => { const from = { px: obj.position.x, py: obj.position.y, pz: obj.position.z, rx: obj.rotation.x, ry: obj.rotation.y, rz: obj.rotation.z };
      tweens.add({ obj, from, to, t0: performance.now() + delay, dur: B.reduced ? 1 : dur, resolve }); engine.kick(); });
  }
  const fx = new Set();

  /* ── state ── */
  let mode = "deck", spread = B.S.spread === "three" ? "three" : "daily", fan = [], slots = [], picked = [], reading = null, busy = false;
  const need = () => (spread === "three" ? 3 : 1);
  const slotPos = (k) => spread === "three" ? new THREE.Vector3((k - 1) * .15, TOP + .002, .02) : new THREE.Vector3(0, TOP + .002, .02);

  /* ── HUD: spread switch, question, hint ── */
  const seg = el("div", "seg ch-seg"), qIn = el("input", "field ch-q"), hint = el("p", "ch-stage-hint"), act = el("button", "btn ghost ch-act");
  [["daily", "sDaily"], ["three", "sThree"]].forEach(([v, k]) => { const b = el("button", null, B.t(k)); b.type = "button"; b.dataset.v = v;
    b.addEventListener("click", () => { if (busy || spread === v) return; spread = v; B.S.spread = v; B.haptic.tap(); syncHud(); reset(); }); seg.append(b); });
  qIn.maxLength = 300; qIn.placeholder = B.t("questionPh"); act.type = "button";
  act.addEventListener("click", () => {   // every gesture has a button too (keyboard, screen readers, a tired hand)
    if (mode === "deck") shuffle();
    else if (mode === "fan" && !busy) { const free = fan.slice(); while (picked.length < need() && free.length) take(free.splice((Math.random() * free.length) | 0, 1)[0]); }
    else if (mode === "flip") { const c = slots.find((x) => !x.userData.flipped); if (c) flip(c); }
    else if (mode === "read" && reading) showReading(); });
  hint.setAttribute("aria-live", "polite");
  ui.hud.append(seg, qIn, hint, act);
  function syncHud() {
    seg.querySelectorAll("button").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.v === spread)));
    qIn.hidden = !(spread === "three" && (mode === "deck" || mode === "fan"));
    hint.textContent = mode === "deck" ? tx("shuffle") : mode === "fan" ? tx(spread === "three" ? "fanThree" : "fanOne") : mode === "wait" ? tx("speaking") : mode === "flip" ? tx("flip") : "";
    act.hidden = mode === "wait" || (mode === "read" && !reading); hint.hidden = !hint.textContent;
    act.textContent = mode === "deck" ? tx("shuffleBtn") : mode === "fan" ? tx("choose") : mode === "flip" ? tx("turn") : tx("readAgain");
    seg.hidden = mode === "wait" || mode === "flip";
  }

  /* ── shuffle: split the deck, riffle the halves back together ── */
  async function shuffle() {
    if (busy || (mode !== "deck" && mode !== "fan")) return; busy = true; B.haptic.soft(); ui.sound("shuffle");
    if (mode === "fan") { await gather(); }
    const order = cards.slice().sort((a, b) => a.position.y - b.position.y), half = order.length >> 1;
    await Promise.all(order.map((c, i) => { const left = i < half, k = left ? i : i - half;
      return tween(c, { px: deckPos.x + (left ? -.075 : .075), py: TOP + k * .0016, pz: deckPos.z + (left ? .01 : -.01), ry: left ? .12 : -.12, rx: 0, rz: left ? .05 : -.05 }, 300, i * 6); }));
    const mixed = []; for (let i = 0; i < half; i++) { mixed.push(order[i]); if (order[half + i]) mixed.push(order[half + i]); }
    await Promise.all(mixed.map((c, i) => tween(c, { px: deckPos.x, py: TOP + i * .0016, pz: deckPos.z, rx: 0, ry: (Math.random() - .5) * .04, rz: 0 }, 260, i * 14)));
    busy = false; B.haptic.tap();
    await fanOut();
  }
  async function fanOut() {
    const order = cards.slice().sort((a, b) => b.position.y - a.position.y); fan = order.slice(0, FAN); mode = "fan"; syncHud();
    await Promise.all(fan.map((c, i) => { const a = (i - (FAN - 1) / 2) * .085, R = .5; c.userData.fanRy = -a;
      return tween(c, { px: Math.sin(a) * R, py: TOP + .001 + i * .0018, pz: .7 - Math.cos(a) * R, rx: 0, ry: -a, rz: 0 }, 480, i * 45); }));
  }
  async function gather() {
    await Promise.all(cards.map((c, i) => tween(c, { px: deckPos.x, py: TOP + i * .0016, pz: deckPos.z, rx: 0, ry: 0, rz: 0 }, 420, i * 8)));
    fan = []; mode = "deck";
  }

  /* ── drawing: drag a fanned card up (or touch it) and it goes to the next slot ── */
  let drag = null;
  const plane = () => new THREE.Plane(new THREE.Vector3(0, 1, 0), 0).applyMatrix4(grp.matrixWorld);
  const toLocal = (v) => grp.worldToLocal(v.clone());
  const hitCard = (e, list) => { const hits = engine.raycast(e.clientX, e.clientY, list.map((c) => c)); if (!hits.length) return null; let o = hits[0].object; while (o && !list.includes(o)) o = o.parent; return o; };
  function down(e) {
    if (busy) return true;
    if (hitCard(e, [station.box, station.lid].filter(Boolean).map((m) => m))) { openBox(); return true; }
    if (mode === "deck") { drag = { x: e.clientX, y: e.clientY, kind: "shuffle" }; return true; }
    if (mode === "fan") { const c = hitCard(e, fan); if (c) { drag = { x: e.clientX, y: e.clientY, kind: "pull", c, start: c.position.clone(), moved: false }; B.haptic.tap(); }
      else drag = { x: e.clientX, y: e.clientY, kind: "shuffle" }; return true; }
    if (mode === "flip") { const c = hitCard(e, slots.filter((s) => !s.userData.flipped)); if (c) drag = { x: e.clientX, y: e.clientY, kind: "flip", c, ang: 0 }; return true; }
    return true;
  }
  function move(e) {
    if (!drag) return true;
    if (drag.kind === "pull") { const p = engine.rayPlane(e.clientX, e.clientY, plane()); if (!p) return true; const l = toLocal(p);
      drag.moved = drag.moved || Math.hypot(e.clientX - drag.x, e.clientY - drag.y) > 8;
      drag.c.position.set(l.x, TOP + .03, l.z); drag.c.rotation.y *= .9; engine.kick(); }
    if (drag.kind === "flip") { drag.ang = Math.max(0, Math.min(Math.PI, Math.abs(e.clientY - drag.y + (e.clientX - drag.x) * .4) / 140 * Math.PI));
      drag.c.rotation.x = drag.ang; drag.c.position.y = TOP + .002 + Math.sin(drag.ang) * .05; engine.kick(); }
    return true;
  }
  function up(e) {
    const d = drag; drag = null; if (!d) return true;
    const dx = e.clientX - d.x, dy = e.clientY - d.y;
    if (d.kind === "shuffle") { if (Math.abs(dx) > 40 || Math.abs(dy) > 60) shuffle(); else if (mode === "deck") shuffle(); return true; }
    if (d.kind === "pull") { const l = d.c.position, pulled = !d.moved || l.z < d.start.z - .05;
      if (pulled && picked.length < need()) take(d.c); else tween(d.c, { px: d.start.x, py: d.start.y, pz: d.start.z, rx: 0, ry: d.c.userData.fanRy ?? d.c.rotation.y, rz: 0 }, 300); return true; }
    if (d.kind === "flip") { if (d.ang > Math.PI / 2 || Math.hypot(dx, dy) < 8) flip(d.c); else tween(d.c, { rx: 0, py: TOP + .002 }, 300); return true; }
    return true;
  }
  async function take(c) {
    const k = picked.length; picked.push(c); fan = fan.filter((x) => x !== c); B.haptic.soft(); ui.sound("pick");
    const p = slotPos(k); await tween(c, { px: p.x, py: p.y + .02, pz: p.z, rx: 0, ry: 0, rz: 0 }, 480); await tween(c, { py: p.y }, 240);
    if (picked.length === need()) draw();
  }

  /* ── the server draws the cards; the slotted cards shimmer while it does ── */
  async function draw() {
    if (mode !== "fan") return;   // several cards may land at once: draw exactly one time
    busy = true; mode = "wait"; syncHud(); slots = picked.slice();
    await Promise.all(fan.map((c, i) => tween(c, { px: deckPos.x, py: TOP + (N + i) * .0016, pz: deckPos.z, rx: 0, ry: 0, rz: 0 }, 420, i * 20)));
    try {
      const q = qIn.value.trim();
      const r = await B.api("POST", "/api/tarot/draw", { spread, question: spread === "three" && q ? q : null });
      reading = r; B.store.set("astro.chSeen.tarot", B.todayKey());
      if (r.repeated) B.toast(B.t("dailyDone"));
      await Promise.all(r.cards.map((c, i) => new Promise((res) => { const s = slots[i]; if (!s) return res();
        s.userData.card = c; s.userData.reversed = !!c.reversed;
        if (c.reversed) s.rotation.y = Math.PI;   // lands upside down, still face down
        const src = B.TAROT_IMG[c.id];
        if (!src) return res();
        loader.load(src, (t) => { t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 4; textures.push(t); s.userData.face.material.map = t; s.userData.face.material.color.set(0xffffff); s.userData.face.material.needsUpdate = true; res(); }, undefined, () => res()); })));
      mode = "flip"; busy = false; syncHud();
    } catch (e) { busy = false; B.showError(e); reset(); }
  }
  async function flip(c) {
    if (c.userData.flipped) return; c.userData.flipped = true; B.haptic.flip(); ui.sound("flip");
    await tween(c, { rx: Math.PI, py: TOP + .002 }, 480);
    const sweep = new THREE.Mesh(planeGeo, sweepMat.clone()); sweep.rotation.x = -Math.PI / 2; sweep.position.y = .002; c.add(sweep);
    const wp = c.getWorldPosition(new THREE.Vector3()); fx.add(F.burst(engine.scene, wp, { count: 40, speed: .45 }));
    const t0 = performance.now(); fx.add({ update() { const k = (performance.now() - t0) / 900; sweep.material.uniforms.uT.value = k * 1.3 - .3; if (k >= 1) { c.remove(sweep); sweep.material.dispose(); return false; } return true; } });
    if (slots.every((s) => s.userData.flipped)) { mode = "read"; syncHud(); setTimeout(showReading, B.reduced ? 0 : 1100); }
  }

  /* ── the reading: ink on parchment, in the glass panel ── */
  async function showReading() {
    if (!reading) return;
    const box = el("div", "ch-parch ch-ink"), out = el("div", "cards-text"); B.renderTarotText(out, reading);
    const again = el("button", "btn wide", B.t("drawAgain")); again.type = "button";
    again.addEventListener("click", async () => { await ui.hidePanel(); reset(); });
    box.append(out); ui.panel([box, again]);
    requestAnimationFrame(() => box.classList.add("on"));
  }
  async function openBox() {
    B.haptic.tap(); ui.sound("pick"); const wrap = el("div", "ch-coll"), grid = el("div", "coll"), head = el("div", "sec-head");
    head.append(el("h2", null, tx("box")), el("span", null, "…")); wrap.append(head, el("p", "muted", tx("boxHint")), grid);
    ui.panel([wrap]);
    try { const r = await B.api("GET", "/api/tarot/collection"), owned = r.owned || {};
      head.lastChild.textContent = `${Object.keys(owned).length} / ${B.ARCANA.length}`;
      grid.replaceChildren(...B.ARCANA.map(([id]) => { const f = el("figure", owned[id] ? "" : "off"), img = el("img"); img.alt = ""; img.decoding = "async"; img.loading = "lazy";
        img.src = owned[id] && B.TAROT_IMG[id] ? B.TAROT_IMG[id] : B.BACK_IMG; f.append(img, el("figcaption", null, owned[id] ? B.cardName(id) : B.t("locked")));
        if (owned[id] > 1) f.append(el("b", null, `×${owned[id]}`)); return f; }));
    } catch (e) { B.showError(e); }
  }

  /* back to a fresh deck: the drawn faces are released */
  function reset() {
    reading = null; picked = []; fan = [];
    for (const c of slots) { const m = c.userData.face.material; if (m.map) { textures.splice(textures.indexOf(m.map), 1); m.map.dispose(); m.map = null; m.color.set(0x1a1440); m.needsUpdate = true; }
      c.userData.flipped = false; c.userData.reversed = false; c.userData.card = null; }
    slots = []; mode = "deck"; busy = false; syncHud(); gather();
  }

  const scr = (o) => engine.project(o.getWorldPosition(new THREE.Vector3()));
  return {
    debug: () => ({ mode, busy, deck: engine.project(grp.localToWorld(deckPos.clone())), fan: fan.map(scr), slots: slots.map(scr), box: scr(station.box) }),
    async start() { syncHud(); },
    down, move, up,
    update(t, dt) {
      const now = performance.now();
      for (const tw of tweens) { const p = Math.min(1, Math.max(0, (now - tw.t0) / tw.dur)); if (p <= 0) continue; const e = engine.ease(p), o = tw.obj, f = tw.from, to = tw.to;
        if (to.px != null) o.position.x = f.px + (to.px - f.px) * e; if (to.py != null) o.position.y = f.py + (to.py - f.py) * e; if (to.pz != null) o.position.z = f.pz + (to.pz - f.pz) * e;
        if (to.rx != null) o.rotation.x = f.rx + (to.rx - f.rx) * e; if (to.ry != null) o.rotation.y = f.ry + (to.ry - f.ry) * e; if (to.rz != null) o.rotation.z = f.rz + (to.rz - f.rz) * e;
        if (p >= 1) { tweens.delete(tw); tw.resolve(); } }
      for (const f of fx) if (!f.update(dt)) fx.delete(f);
      if (mode === "wait") backMat.emissive.setRGB(.18 + .14 * Math.sin(t * 5), .13 + .1 * Math.sin(t * 5), .05);
      else backMat.emissive.setRGB(0, 0, 0);
    },
    end() {
      for (const f of fx) f.dispose && f.dispose(); fx.clear(); tweens.clear();
      grp.remove(root); planeGeo.dispose(); edgeGeo.dispose(); backMat.dispose(); edgeMat.dispose(); sweepMat.dispose();
      for (const c of cards) c.userData.face.material.dispose();
      for (const t of textures) t.dispose(); textures.length = 0;
      station.deck.visible = true; ui.hud.replaceChildren();
    },
  };
}
