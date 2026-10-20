/* Oracle chamber (FULL): the gift chest. Touch it: the lid opens with a starburst, coins rise and fly to the
   counter (POST /api/user/daily-reward through the app's own claimGift, so the economy is unchanged). The streak,
   its seven pips and the weekly streak freeze are shown above the chest. */

const TX = {
  ka: { open: "ზარდახშის გახსნა", touch: "შეეხე ზარდახშას და გახსენი", empty: "ზარდახშა დღეს უკვე გაიხსნა. ხვალ ახალი საჩუქარი დაგხვდება." },
  en: { open: "Open the chest", touch: "Touch the chest to open it", empty: "The chest has been opened today. A new gift waits tomorrow." },
  ru: { open: "Открыть сундук", touch: "Коснись сундука, чтобы открыть его", empty: "Сундук сегодня уже открыт. Завтра тебя ждёт новый подарок." },
};

export function createStage({ THREE, engine, station, B, ui, F }) {
  const tx = (k) => (TX[B.S.lang] || TX.en)[k], el = B.el, lid = station.lid, inner = station.inner;
  let lidT = 0, lidA = 0, glowT = 0, opening = false;
  const fx = new Set();

  const card = el("div", "ch-gift"), streak = el("b"), pips = el("div", "pips"), frz = el("p", "frz"), hint = el("p", "ch-stage-hint");
  const openBtn = el("button", "btn ch-act", tx("open")); openBtn.type = "button"; openBtn.addEventListener("click", () => open());
  hint.setAttribute("aria-live", "polite"); card.append(streak, pips, frz); ui.hud.append(card, hint, openBtn);
  function render() {
    const u = B.S.user || {}, n = u.streak || 0, avail = u.daily_reward_available !== false;
    streak.textContent = B.t("streak", { n });
    pips.replaceChildren(...Array.from({ length: 7 }, (_, i) => el("i", i < n % 7 || (n && n % 7 === 0) ? "on" : "")));
    const f = u.streak_freeze; frz.hidden = !f; if (f) frz.textContent = B.t(f.saving && avail ? "frzSaving" : f.ready ? "frzReady" : "frzUsed");
    hint.textContent = avail ? tx("touch") : tx("empty"); openBtn.hidden = !avail;
    if (!avail && !opening) lidT = .35;
  }
  render();

  function flyCoins(n) {
    const from = engine.project(station.center.clone().add(new THREE.Vector3(0, .15, 0))), target = ui.coinsTarget(), tr = target.getBoundingClientRect();
    const svg = '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="11" fill="#e2bd6a"/><circle cx="12" cy="12" r="8.2" fill="none" stroke="#7d5c24" stroke-width=".8"/></svg>';
    for (let i = 0; i < n; i++) {
      const c = el("i", "ch-coin"); c.innerHTML = svg; document.body.append(c);
      const sx = from.x + (Math.random() - .5) * 60, sy = from.y, ux = sx + (Math.random() - .5) * 80, uy = sy - 90 - Math.random() * 90;
      const anim = c.animate([{ transform: `translate(${sx}px, ${sy}px) scale(.4)`, opacity: 0 }, { transform: `translate(${ux}px, ${uy}px) scale(1)`, opacity: 1, offset: .35 },
        { transform: `translate(${tr.left + tr.width * .25}px, ${tr.top + tr.height / 2}px) scale(.55)`, opacity: .9 }],
        { duration: B.reduced ? 1 : 1150 + i * 60, delay: B.reduced ? 0 : i * 70, easing: "cubic-bezier(.2,.7,.1,1)", fill: "forwards" });
      anim.onfinish = () => { c.remove(); if (i === n - 1) { target.classList.remove("bump"); void target.offsetWidth; target.classList.add("bump"); } };
    }
  }
  async function open() {
    if (opening) return; const u = B.S.user || {};
    if (u.daily_reward_available === false) { B.haptic.soft(); lidT = .35; B.toast(tx("empty")); return; }
    opening = true; B.haptic.tap();
    let reward = null; try { reward = await B.claimGift(); } catch { opening = false; return; }
    lidT = 1; glowT = 1; B.haptic.ok(); ui.sound("chest");
    const at = station.center.clone().add(new THREE.Vector3(0, .12, 0));
    fx.add(F.burst(engine.scene, at, { count: 70, speed: .7, size: 12 }));
    const star = F.glow(engine.X.T.glow, 0xffe2a8, .1, 1); star.position.copy(at); engine.scene.add(star);
    const t0 = performance.now(); fx.add({ update() { const k = (performance.now() - t0) / 900; star.scale.setScalar(.1 + k * 1.6); star.material.opacity = Math.max(0, 1 - k);
      if (k >= 1) { this.dispose(); return false; } return true; }, dispose() { engine.scene.remove(star); star.material.dispose(); } });
    if (reward) { setTimeout(() => flyCoins(Math.min(12, 6 + Math.round((reward.coins_earned || 50) / 25))), 350); }
    render(); opening = false;
  }

  return {
    debug: () => ({ chest: engine.project(station.center.clone()) }),
    async start() {},
    down(e) { if (engine.raycast(e.clientX, e.clientY, [station.hit, station.body, lid]).length) { open(); } return true; },
    move() { return true; }, up() { return true; },
    update(t, dt) {
      lidA += (lidT - lidA) * Math.min(1, dt * 3.2); lid.rotation.x = -lidA * 1.9;
      inner.material.opacity += (glowT * (.75 + .15 * Math.sin(t * 2)) - inner.material.opacity) * Math.min(1, dt * 2);
      for (const f of fx) if (!f.update(dt)) fx.delete(f);
    },
    end() { for (const f of fx) f.dispose && f.dispose(); fx.clear(); lid.rotation.x = 0; inner.material.opacity = 0; ui.hud.replaceChildren(); },
  };
}
