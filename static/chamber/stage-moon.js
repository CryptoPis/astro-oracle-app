/* Oracle chamber (FULL): the moon window. The moonlight in the room already follows the real phase; here the
   phase's folklore (after T. Harley, Moon Lore, 1885; shown as tradition, never as fact) introduces tonight's ritual
   (GET /api/moon/ritual, as in the classic UI). Its steps appear one by one while the candles on the sill light. */

const TX = {
  ka: { tradition: "ხალხური ტრადიცია · ტ. ჰარლი, „მთვარის თქმულებები“ (1885)", begin: "რიტუალის დაწყება", next: "შემდეგი ნაბიჯი", finish: "რიტუალის დასრულება",
    step: "ნაბიჯი {i} / {n}", whole: "მთელი რიტუალი" },
  en: { tradition: "Folk tradition · T. Harley, Moon Lore (1885)", begin: "Begin the ritual", next: "Next step", finish: "Complete the ritual",
    step: "Step {i} of {n}", whole: "The whole ritual" },
  ru: { tradition: "Народная традиция · Т. Харли, «Лунные предания» (1885)", begin: "Начать ритуал", next: "Следующий шаг", finish: "Завершить ритуал",
    step: "Шаг {i} из {n}", whole: "Весь ритуал" },
};

export function createStage({ engine, station, B, ui, THREE }) {
  const tx = (k, v = {}) => { let s = (TX[B.S.lang] || TX.en)[k]; for (const [a, b] of Object.entries(v)) s = s.replace(`{${a}}`, b); return s; };
  const el = B.el, candles = station.ritual;
  const card = el("div", "ch-moon"), title = el("b"), lore = el("p", "ch-lore"), src = el("small", null, tx("tradition")), begin = el("button", "btn", tx("begin"));
  begin.type = "button"; card.append(title, lore, src); ui.hud.append(card);
  const stepBox = el("div", "ch-step"), stepN = el("span", "label"), stepT = el("p"), next = el("button", "btn", tx("next"));
  next.type = "button"; stepBox.append(stepN, stepT, next); stepBox.hidden = true;
  const foot = el("div", "ch-hud-foot"); foot.append(begin, stepBox); document.body.append(foot);
  let ritual = null, i = -1, glow = 0, glowT = 0;
  const moon = B.moonNow();
  title.textContent = `${B.MOON_NAMES[moon.code] ? B.MOON_NAMES[moon.code][B.S.lang] || moon.name : moon.name} · ${moon.illumination}%`;
  fetch(new URL("./kb.json" + new URL(import.meta.url).search, import.meta.url)).then((r) => r.json())
    .then((kb) => { const m = kb.moon[moon.code]; if (m) lore.textContent = (m[B.S.lang] || m.en).lore; }).catch(() => { lore.hidden = true; });

  function light(k) { const c = candles[k]; if (!c || c.userData.flame.visible) return; c.userData.flame.visible = true; c.userData.glow.visible = true; B.haptic.soft(); ui.sound("candle"); }
  function show() {
    const n = ritual.steps.length; stepN.textContent = tx("step", { i: i + 1, n }); stepT.textContent = ritual.steps[i];
    stepBox.classList.remove("on"); void stepBox.offsetWidth; stepBox.classList.add("on");
    light(Math.min(candles.length - 1, Math.floor(i * candles.length / n)));
    next.textContent = i === n - 1 ? tx("finish") : tx("next");
  }
  begin.addEventListener("click", async () => {
    begin.disabled = true; B.haptic.tap();
    try { const r = await B.api("GET", "/api/moon/ritual"); ritual = r.ritual; B.store.set("astro.chSeen.moon", B.todayKey()); }
    catch (e) { B.showError(e); begin.disabled = false; return; }
    begin.hidden = true; stepBox.hidden = false; i = 0; show();
  });
  next.addEventListener("click", () => {
    B.haptic.tap(); if (i < ritual.steps.length - 1) { i++; show(); return; }
    candles.forEach((_, k) => light(k)); glowT = 1; whole();
  });
  function whole() {
    const box = el("div", "reading"), ol = el("ol", "ch-steps");
    ritual.steps.forEach((s) => ol.append(el("li", null, s)));
    box.append(el("h2", null, ritual.title), el("p", null, ritual.intention), ol, el("p", "advice", ritual.affirmation), el("p", "note", ritual.avoid));
    ui.panel([box], tx("whole"));
  }

  return {
    debug: () => ({ i, n: ritual ? ritual.steps.length : 0 }),
    async start() {},
    down() { return true; }, move() { return true; }, up() { return true; },
    update(t, dt) { glow += (glowT - glow) * Math.min(1, dt * 1.5); engine.room.moonLight.intensity = engine.room.moonLight.userData.base * (1 + glow * .6); },
    end() { candles.forEach((c) => { c.userData.flame.visible = false; c.userData.glow.visible = false; }); engine.room.moonLight.intensity = engine.room.moonLight.userData.base;
      foot.remove(); ui.hud.replaceChildren(); },
  };
}
