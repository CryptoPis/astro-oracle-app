/* Oracle chamber (FULL): the coffee cup. Swirl the grounds (circle round the cup with a finger, or tilt the phone),
   turn the cup over onto the saucer with a swipe down, then the app's own photo flow reads it (POST /api/vision/coffee).
   When the reading comes, its symbols (named from the knowledge base) float round the cup. */

const TX = {
  ka: { swirl: "მოატრიალე ნალექი: თითით წრეები შემოხაზე ფინჯანს (ან ტელეფონი დახარე)", flip: "ახლა ფინჯანი თეფშზე დაამხე: ქვემოთ გადაუსვი",
    photo: "ნალექი ჩამოიწრიტა. ახლა ფინჯნის ფოტო გადაიღე", take: "ფოტოს გადაღება", skip: "პირდაპირ ფოტოზე" },
  en: { swirl: "Swirl the grounds: circle round the cup with a finger (or tilt the phone)", flip: "Now turn the cup over onto the saucer: swipe down",
    photo: "The grounds have settled. Now take a photo of the cup", take: "Take the photo", skip: "Straight to the photo" },
  ru: { swirl: "Покрути гущу: обведи чашку пальцем по кругу (или наклони телефон)", flip: "Теперь переверни чашку на блюдце: проведи вниз",
    photo: "Гуща осела. Теперь сфотографируй чашку", take: "Сделать фото", skip: "Сразу к фото" },
};

export function createStage({ THREE, engine, station, B, ui }) {
  const tx = (k) => (TX[B.S.lang] || TX.en)[k], el = B.el, cup = station.cup, coffee = station.coffee;
  /* a swirl texture on the coffee: dark brown with a lighter crema spiral */
  const c = document.createElement("canvas"); c.width = c.height = 128; const x = c.getContext("2d");
  x.fillStyle = "#2a160c"; x.fillRect(0, 0, 128, 128); x.strokeStyle = "rgba(196,150,96,.55)"; x.lineWidth = 3;
  x.beginPath(); for (let a = 0; a < 18; a += .1) { const r = a * 3.4; x.lineTo(64 + Math.cos(a) * r, 64 + Math.sin(a) * r); } x.stroke();
  const swirlTex = new THREE.CanvasTexture(c); swirlTex.center.set(.5, .5); swirlTex.colorSpace = THREE.SRGBColorSpace;
  const oldMat = coffee.material, mat = new THREE.MeshLambertMaterial({ map: swirlTex }); coffee.material = mat;
  const home = { y: cup.position.y, rx: cup.rotation.x };

  const hint = el("p", "ch-stage-hint", tx("swirl")), take = el("button", "btn", tx("take")), skip = el("button", "btn ghost", tx("skip"));
  take.type = skip.type = "button"; take.hidden = true;
  hint.setAttribute("aria-live", "polite"); ui.hud.append(hint); const foot = el("div", "ch-hud-foot"), row = el("div", "ch-row"); row.append(take, skip); foot.append(row); document.body.append(foot);
  const labels = el("div", "ch-symbols"); document.body.append(labels);

  let phase = "swirl", turned = 0, spin = 0, flipT = 0, flipA = 0, last = null, drag = null, symbols = [];
  const photo = () => { B.haptic.tap(); B.go("coffee"); };
  take.addEventListener("click", photo); skip.addEventListener("click", photo);

  const center = () => engine.project(station.center.clone());
  function down(e) { drag = { x: e.clientX, y: e.clientY }; const p = center(); last = Math.atan2(e.clientY - p.y, e.clientX - p.x); return true; }
  function move(e) {
    if (!drag) return true;
    if (phase === "swirl") { const p = center(), a = Math.atan2(e.clientY - p.y, e.clientX - p.x); let d = a - last; if (d > Math.PI) d -= Math.PI * 2; if (d < -Math.PI) d += Math.PI * 2;
      last = a; spin += d * 6; turned += Math.abs(d); if (turned > Math.PI * 4.5) ready(); }
    return true;
  }
  function up(e) { const d = drag; drag = null; if (!d) return true;
    if (phase === "flip" && e.clientY - d.y > 70) { phase = "flipping"; flipT = 1; B.haptic.flip(); ui.sound("flip"); setTimeout(settled, B.reduced ? 0 : 1300); }
    return true; }
  function ready() { if (phase !== "swirl") return; phase = "flip"; hint.textContent = tx("flip"); B.haptic.soft(); }
  function settled() { phase = "photo"; hint.textContent = tx("photo"); take.hidden = false; skip.hidden = true; }
  /* tilting the phone swirls too */
  let tiltLast = null; const onTilt = (e) => { if (phase !== "swirl" || e.gamma == null) return; if (tiltLast != null) { const d = (e.gamma - tiltLast) * Math.PI / 180; spin += d * 4; turned += Math.abs(d) * .6; if (turned > Math.PI * 4.5) ready(); } tiltLast = e.gamma; };
  addEventListener("deviceorientation", onTilt);

  /* the reading's symbols, floating round the cup */
  const onVision = (e) => { if (e.detail.kind !== "coffee") return; symbols = (e.detail.reading.symbols || []).slice(0, 5).map((s) => s.symbol);
    labels.replaceChildren(...symbols.map((s, i) => { const l = el("span", null, s); l.style.setProperty("--i", i); return l; })); };
  document.addEventListener("astro:vision", onVision);

  return {
    debug: () => ({ phase, cup: center() }),
    async start() {},
    down, move, up,
    update(t, dt) {
      swirlTex.rotation += spin * dt; spin *= Math.exp(-dt * 1.6); cup.rotation.z = Math.sin(t * 7) * Math.min(.05, Math.abs(spin) * .01);
      flipA += (flipT - flipA) * Math.min(1, dt * 3.2); cup.rotation.x = home.rx + flipA * Math.PI; cup.position.y = home.y + Math.sin(flipA * Math.PI) * .07 + flipA * .09;
      if (symbols.length) { const p = center(), R = Math.min(innerWidth * .36, 150);
        [...labels.children].forEach((l, i) => { const a = -Math.PI / 2 + (i - (symbols.length - 1) / 2) * .62 + Math.sin(t * .4 + i) * .04;
          l.style.transform = `translate(${p.x + Math.cos(a) * R}px, ${p.y + Math.sin(a) * R * .75 - 20}px) translate(-50%, -50%)`; }); }
    },
    end() { removeEventListener("deviceorientation", onTilt); document.removeEventListener("astro:vision", onVision);
      coffee.material = oldMat; mat.dispose(); swirlTex.dispose(); cup.rotation.set(0, 0, 0); cup.position.y = home.y;
      foot.remove(); labels.remove(); ui.hud.replaceChildren(); },
  };
}
