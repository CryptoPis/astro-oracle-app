/* Oracle chamber (FULL): the crystal ball. Type a question (optional), then wipe the mist away with a finger:
   the ball's shader reads a mask painted where the finger touches. The answer comes from the server
   (POST /api/sphere, as in the classic UI) and rises out of the fog with Sepharial's cloud line; the ball fills
   with the answer's colour (gold yes, violet unclear, silver not now); the topic advice appears below. */

const TX = {
  ka: { wipe: "დასვი კითხვა, მერე თითით გადაწმინდე ნისლი სფეროზე", wiping: "კიდევ… ნისლი იფანტება", auto: "ნისლის გადაწმენდა", again: "ახალი კითხვა" },
  en: { wipe: "Ask your question, then wipe the mist from the ball with a finger", wiping: "More… the mist is clearing", auto: "Clear the mist", again: "A new question" },
  ru: { wipe: "Задай вопрос, затем сотри пальцем туман с шара", wiping: "Ещё… туман рассеивается", auto: "Стереть туман", again: "Новый вопрос" },
};
const TONE = { yes: 0xe2bd6a, wait: 0x8b6cff, no: 0xc9d0e6 };

export function createStage({ THREE, engine, station, B, ui }) {
  const tx = (k) => (TX[B.S.lang] || TX.en)[k], el = B.el;
  const ball = station.ball, mat = ball.material, halo = station.halo;

  /* the mist mask: white = mist, wiped areas turn black */
  const S = 128, cv = document.createElement("canvas"); cv.width = cv.height = S; const cx = cv.getContext("2d");
  const mask = new THREE.CanvasTexture(cv); mask.wrapS = THREE.RepeatWrapping;
  const fillMask = () => { cx.globalCompositeOperation = "source-over"; cx.fillStyle = "#fff"; cx.fillRect(0, 0, S, S); mask.needsUpdate = true; };
  fillMask(); mat.uniforms.uMask.value = mask; mat.uniforms.uUseMask.value = 1;
  let fog = 0, fogT = 1, wiped = 0;
  const cells = new Set();

  /* HUD */
  const q = el("input", "field ch-q"), hint = el("p", "ch-stage-hint", tx("wipe")), auto = el("button", "btn ghost ch-act", tx("auto"));
  q.maxLength = 200; q.placeholder = B.t("spherePh"); auto.type = "button";
  const ans = el("div", "ch-answer"), word = el("p", "ch-answer-word"), cloud = el("p", "ch-answer-cloud"), adv = el("p", "ch-answer-adv"), again = el("button", "btn ch-again", tx("again"));
  again.type = "button"; ans.append(word, cloud, adv, again); ans.hidden = true; ans.setAttribute("aria-live", "polite");
  ui.hud.append(q, hint, auto); document.body.append(ans);

  let phase = "ask", result = null, pending = null, wipeT = 0, fill = 0, fillT = 0, mist = 1, mistT = 1, tint = new THREE.Color(0x8b6cff), drag = null, autoT = 0;
  const ask = () => { if (pending) return pending; const question = q.value.trim() || null;
    pending = B.api("POST", "/api/sphere", { question }).then((r) => { result = r; return r; }).catch((e) => { B.showError(e); reset(); return null; }); return pending; };

  function paint(e) {
    const hit = engine.raycast(e.clientX, e.clientY, [ball])[0]; if (!hit || !hit.uv) return;
    const x = hit.uv.x * S, y = (1 - hit.uv.y) * S; cx.globalCompositeOperation = "destination-out";
    const g = cx.createRadialGradient(x, y, 0, x, y, 16); g.addColorStop(0, "rgba(0,0,0,1)"); g.addColorStop(1, "rgba(0,0,0,0)");
    cx.fillStyle = g; cx.fillRect(x - 16, y - 16, 32, 32); cx.fillRect(x - 16 + S, y - 16, 32, 32); cx.fillRect(x - 16 - S, y - 16, 32, 32);   // wraps round the ball
    mask.needsUpdate = true; cells.add(`${(hit.uv.x * 12) | 0}:${(hit.uv.y * 8) | 0}`); ui.sound("wipe");
    if (phase === "ask") { phase = "wipe"; ask(); hint.textContent = tx("wiping"); q.blur(); q.disabled = true; }
    wiped += 1 / 60; if (cells.size >= 5 || wiped > .75) reveal();   // about one calm circle of the finger
  }
  async function reveal() {
    if (phase !== "wipe") return; phase = "wait";
    const r = await ask(); if (!r) return;
    phase = "done"; B.haptic.ok(); ui.sound("reveal");
    tint.set(TONE[r.tone] || TONE.wait); mat.uniforms.uTint.value.copy(tint); halo.material.color.copy(tint); fillT = 1; mistT = .12; fogT = 0;
    word.textContent = r.answer; cloud.textContent = r.cloud || ""; cloud.title = r.lore || ""; adv.textContent = r.advice || "";
    ans.hidden = false; ui.hud.hidden = true; requestAnimationFrame(() => ans.classList.add("on"));
  }
  function reset() {
    phase = "ask"; result = null; pending = null; cells.clear(); fillMask(); fillT = 0; mistT = 1; fogT = 1; wiped = 0; q.disabled = false; q.value = "";
    hint.textContent = tx("wipe"); ans.classList.remove("on"); ans.hidden = true; ui.hud.hidden = false; halo.material.color.set(0x8b6cff);
  }
  again.addEventListener("click", () => { B.haptic.tap(); reset(); });
  auto.addEventListener("click", () => { if (phase === "ask" || phase === "wipe") { B.haptic.tap(); autoT = 1.6; if (phase === "ask") { phase = "wipe"; ask(); q.disabled = true; } } });

  return {
    debug: () => ({ phase, ball: engine.project(ball.getWorldPosition(new THREE.Vector3())), r: 0.21 }),
    async start() {},
    down(e) { if (phase === "ask" || phase === "wipe") { drag = true; paint(e); } return true; },
    move(e) { if (drag) paint(e); return true; },
    up() { drag = false; return true; },
    update(t, dt) {
      if (autoT > 0) { autoT -= dt; const a = t * 6, r = 48 + Math.sin(t * 2) * 20, x = S / 2 + Math.cos(a) * r, y = S / 2 + Math.sin(a) * r * .6;   // a calm spiral wipes for those who cannot
        cx.globalCompositeOperation = "destination-out"; cx.fillStyle = "rgba(0,0,0,.6)"; cx.beginPath(); cx.arc(x, y, 18, 0, 7); cx.fill(); mask.needsUpdate = true;
        cells.add(`${(x / S * 12) | 0}:${(y / S * 8) | 0}`); if (autoT <= 0 || cells.size >= 6) { autoT = 0; reveal(); } }
      fill += (fillT - fill) * Math.min(1, dt * 1.6); mist += (mistT - mist) * Math.min(1, dt * 1.2); fog += (fogT - fog) * Math.min(1, dt * 1.5); mat.uniforms.uFog.value = fog;
      mat.uniforms.uFill.value = fill; mat.uniforms.uMist.value = mist; halo.material.opacity = .5 + fill * .4 + Math.sin(t * 1.3) * .05;
      if (phase === "done") mat.uniforms.uUseMask.value = Math.max(0, mat.uniforms.uUseMask.value - dt);
    },
    end() {
      mat.uniforms.uUseMask.value = 0; mat.uniforms.uMask.value = null; mat.uniforms.uFog.value = 0; mat.uniforms.uFill.value = 0; mat.uniforms.uMist.value = 1;
      mat.uniforms.uTint.value.set(0x8b6cff); halo.material.color.set(0x8b6cff); halo.material.opacity = .5;
      mask.dispose(); ans.remove(); ui.hud.replaceChildren(); ui.hud.hidden = true;
    },
  };
}
