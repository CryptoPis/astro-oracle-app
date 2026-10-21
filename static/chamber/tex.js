/* Oracle chamber (FULL tier): textures. Procedural ones are drawn once on canvases at boot (never any text): stone,
   dark wood, the rug, velvet, parchment, a star chart, gold matcaps, glows, smoke and gold engravings made from the
   app's own line art (practiceArt). The room's photographic set (img/*.webp, built by scripts/chamber_assets.py) is
   loaded after the first frames with load(); the shell shows the procedural stand-ins until then. */

const V = new URL(import.meta.url).searchParams.get("v") || "dev";

export function makeTextures(THREE, B) {
  const made = [];
  const canvas = (w, h = w) => { const c = document.createElement("canvas"); c.width = w; c.height = h; return [c, c.getContext("2d")]; };
  const tex = (c, { repeat = null, srgb = true, mips = true } = {}) => {
    const t = new THREE.CanvasTexture(c);
    if (srgb) t.colorSpace = THREE.SRGBColorSpace;
    if (repeat) { t.wrapS = t.wrapT = THREE.RepeatWrapping; t.repeat.set(repeat[0], repeat[1]); }
    t.anisotropy = 4; if (!mips) { t.generateMipmaps = false; t.minFilter = THREE.LinearFilter; }
    made.push(t); return t;
  };

  /* small seeded value noise with octaves (fast enough for 256-512 px, done once) */
  function rng(seed) { let a = seed >>> 0; return () => { a = (a + 0x6D2B79F5) >>> 0; let t = a; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; }; }
  function noise(seed, size = 64) {
    const r = rng(seed), g = new Float32Array(size * size); for (let i = 0; i < g.length; i++) g[i] = r();
    const at = (x, y) => g[((y % size + size) % size) * size + ((x % size + size) % size)];
    const sm = (t) => t * t * (3 - 2 * t);
    const v = (x, y) => { const xi = Math.floor(x), yi = Math.floor(y), xf = sm(x - xi), yf = sm(y - yi);
      const a = at(xi, yi), b = at(xi + 1, yi), c = at(xi, yi + 1), d = at(xi + 1, yi + 1);
      return a + (b - a) * xf + (c - a) * yf + (a - b - c + d) * xf * yf; };
    return (x, y, oct = 4) => { let s = 0, amp = .5, f = 1; for (let o = 0; o < oct; o++) { s += v(x * f, y * f) * amp; amp *= .5; f *= 2; } return s; };
  }
  function pixels(w, h, fn) {
    const [c, x] = canvas(w, h), img = x.createImageData(w, h), d = img.data;
    for (let j = 0; j < h; j++) for (let i = 0; i < w; i++) { const [r, g, b, a = 255] = fn(i, j), k = (j * w + i) * 4; d[k] = r; d[k + 1] = g; d[k + 2] = b; d[k + 3] = a; }
    x.putImageData(img, 0, 0); return [c, x];
  }

  /* dark ashlar stone: blocks in rows, mortar lines, soft noise; deep indigo-grey */
  function stone() {
    const S = 256, n = noise(3), r = rng(5), rows = 4, rh = S / rows, blocks = [];
    for (let row = 0; row < rows; row++) { let x = row % 2 ? -20 : 0; while (x < S) { const w = 40 + r() * 45; blocks.push([x, row * rh, w, rh, .82 + r() * .3]); x += w; } }
    const shade = new Float32Array(S * S).fill(1), edge = new Float32Array(S * S);
    for (const [bx, by, bw, bh, s] of blocks) for (let j = Math.max(0, by | 0); j < Math.min(S, by + bh); j++) for (let i = Math.max(0, bx | 0); i < Math.min(S, bx + bw); i++) {
      const k = j * S + i, dx = Math.min(i - bx, bx + bw - i), dy = Math.min(j - by, by + bh - j);
      shade[k] = s; edge[k] = Math.min(dx, dy); }
    const [c] = pixels(S, S, (i, j) => { const k = j * S + i, nn = n(i / 24, j / 24, 3), fine = n(i / 5 + 50, j / 5, 1), e = edge[k];
      const mortar = e < 1.4 ? .45 : e < 3 ? .74 + e * .08 : 1;
      const v = shade[k] * mortar * (.78 + nn * .35 + fine * .12);
      return [46 * v, 41 * v, 64 * v]; });
    return c;
  }
  /* dark wood planks with grain */
  function wood(tone = [70, 46, 30]) {
    const S = 256, n = noise(9), r = rng(4), pw = 32, offs = Array.from({ length: 9 }, () => r() * 400), shades = offs.map(() => .8 + r() * .35);
    const [c] = pixels(S, S, (i, j) => { const p = Math.floor(i / pw), x = i - p * pw, y = j + offs[p];
      const grain = .5 + .5 * Math.sin((y * .09 + n(x / 15 + p * 7, y / 60, 3) * 9) * 1.4);
      const seam = x < 1 || x > pw - 1 ? .45 : 1, v = shades[p] * seam * (.7 + grain * .25 + n(i / 7, j / 30, 1) * .2);
      return [tone[0] * v, tone[1] * v, tone[2] * v]; });
    return c;
  }
  /* the round rug: deep burgundy and indigo, gold rings, an eight-pointed star; transparent outside the circle */
  function rug() {
    const S = 512, [c, x] = canvas(S), cx = S / 2, R = S / 2 - 4;
    const g = x.createRadialGradient(cx, cx, 0, cx, cx, R); g.addColorStop(0, "#3a1630"); g.addColorStop(.55, "#2a1238"); g.addColorStop(1, "#1a0f33");
    x.fillStyle = g; x.beginPath(); x.arc(cx, cx, R, 0, 7); x.fill();
    x.strokeStyle = "rgba(226,189,106,.75)"; x.lineWidth = 3;
    for (const rr of [R - 10, R - 24, R * .62, R * .6, R * .3]) { x.beginPath(); x.arc(cx, cx, rr, 0, 7); x.stroke(); }
    x.lineWidth = 1.5; x.strokeStyle = "rgba(226,189,106,.55)";
    for (let i = 0; i < 48; i++) { const a = i * Math.PI / 24, r1 = R - 24, r2 = R * .62; x.beginPath(); x.moveTo(cx + Math.cos(a) * r1, cx + Math.sin(a) * r1);
      x.lineTo(cx + Math.cos(a + Math.PI / 48) * (r1 + r2) / 2, cx + Math.sin(a + Math.PI / 48) * (r1 + r2) / 2); x.lineTo(cx + Math.cos(a) * r2, cx + Math.sin(a) * r2); x.stroke(); }
    x.beginPath(); for (let i = 0; i < 16; i++) { const a = i * Math.PI / 8 - Math.PI / 2, rr = i % 2 ? R * .12 : R * .29; x.lineTo(cx + Math.cos(a) * rr, cx + Math.sin(a) * rr); }
    x.closePath(); x.fillStyle = "rgba(226,189,106,.16)"; x.fill(); x.lineWidth = 2.5; x.strokeStyle = "rgba(226,189,106,.8)"; x.stroke();
    const r = rng(2); x.fillStyle = "rgba(0,0,0,.18)"; for (let i = 0; i < 1500; i++) x.fillRect(r() * S, r() * S, 1, 1);   // pile
    return c;
  }
  function velvet() {
    const S = 256, [c, x] = canvas(S), g = x.createRadialGradient(S / 2, S / 2, 0, S / 2, S / 2, S / 2);
    g.addColorStop(0, "#2d2160"); g.addColorStop(.85, "#17113a"); g.addColorStop(1, "#100c2a"); x.fillStyle = g; x.fillRect(0, 0, S, S);
    x.strokeStyle = "rgba(226,189,106,.8)"; x.lineWidth = 3; x.beginPath(); x.arc(S / 2, S / 2, S / 2 - 8, 0, 7); x.stroke();
    x.lineWidth = 1; x.setLineDash([2, 5]); x.beginPath(); x.arc(S / 2, S / 2, S / 2 - 16, 0, 7); x.stroke(); return c;
  }
  function parchment(S = 256, seed = 7) {
    const n = noise(seed);
    const [c] = pixels(S, S, (i, j) => { const u = i / S - .5, v = j / S - .5, vig = 1 - Math.min(1, (u * u + v * v) * 1.6);
      const b = .72 + n(i / 30, j / 30, 3) * .3 + n(i / 4, j / 4, 1) * .06, k = (.55 + vig * .45) * b;
      return [226 * k, 204 * k, 160 * k]; });
    return c;
  }
  const upscale = (src, S) => { const [, x] = canvas(S); x.imageSmoothingQuality = "high"; x.drawImage(src, 0, 0, S, S); return x; };
  /* a star chart on parchment: circles, dots and constellation lines in brown ink; no letters */
  function starChart() {
    const S = 512, x = upscale(parchment(256, 11), S), r = rng(31), cx = S / 2;
    x.strokeStyle = "rgba(70,44,22,.55)"; x.lineWidth = 1.4;
    for (const rr of [220, 170, 110]) { x.beginPath(); x.arc(cx, cx, rr, 0, 7); x.stroke(); }
    for (let i = 0; i < 12; i++) { const a = i * Math.PI / 6; x.beginPath(); x.moveTo(cx + Math.cos(a) * 110, cx + Math.sin(a) * 110); x.lineTo(cx + Math.cos(a) * 220, cx + Math.sin(a) * 220); x.stroke(); }
    x.fillStyle = "rgba(60,36,18,.85)";
    for (let k = 0; k < 7; k++) { const a = r() * 6.28, d = 40 + r() * 160, pts = [];
      for (let i = 0; i < 4 + (r() * 3 | 0); i++) pts.push([cx + Math.cos(a) * d + (r() - .5) * 90, cx + Math.sin(a) * d + (r() - .5) * 90]);
      x.beginPath(); pts.forEach(([px, py], i) => (i ? x.lineTo(px, py) : x.moveTo(px, py))); x.stroke();
      pts.forEach(([px, py]) => { x.beginPath(); x.arc(px, py, 2 + r() * 2.5, 0, 7); x.fill(); }); }
    for (let i = 0; i < 160; i++) { x.globalAlpha = .3 + r() * .5; x.beginPath(); x.arc(r() * S, r() * S, .6 + r(), 0, 7); x.fill(); }
    x.globalAlpha = 1; return x.canvas;
  }
  /* matcaps: the whole "metal" look in one lookup (cheap on phones) */
  function matcap(stops, hi = "rgba(255,246,220,.95)") {
    const S = 256, [c, x] = canvas(S), g = x.createRadialGradient(S * .42, S * .38, S * .04, S / 2, S / 2, S / 2);
    stops.forEach(([o, col]) => g.addColorStop(o, col)); x.fillStyle = g; x.fillRect(0, 0, S, S);
    const h = x.createRadialGradient(S * .34, S * .28, 0, S * .34, S * .28, S * .2); h.addColorStop(0, hi); h.addColorStop(1, "rgba(255,240,200,0)");
    x.fillStyle = h; x.fillRect(0, 0, S, S);
    const rim = x.createRadialGradient(S / 2, S / 2, S * .38, S / 2, S / 2, S / 2); rim.addColorStop(0, "rgba(255,200,120,0)"); rim.addColorStop(1, "rgba(255,200,120,.35)");
    x.fillStyle = rim; x.fillRect(0, 0, S, S); return c;
  }
  function glow(core = "255,248,225", edge = "255,214,150") {
    const S = 128, [c, x] = canvas(S), g = x.createRadialGradient(S / 2, S / 2, 0, S / 2, S / 2, S / 2);
    g.addColorStop(0, `rgba(${core},1)`); g.addColorStop(.18, `rgba(${edge},.55)`); g.addColorStop(.5, `rgba(${edge},.12)`); g.addColorStop(1, `rgba(${edge},0)`);
    x.fillStyle = g; x.fillRect(0, 0, S, S); return c;
  }
  function smoke() {
    const S = 128, n = noise(17);
    const [c] = pixels(S, S, (i, j) => { const u = i / S - .5, v = j / S - .5, d = Math.sqrt(u * u + v * v) * 2, f = Math.max(0, 1 - d);
      const a = Math.max(0, n(i / 20, j / 20, 3) - .35) * f * f * 330; return [205, 195, 230, Math.min(255, a)]; });
    return c;
  }
  /* a gold engraving from the app's line art (SVG -> image -> canvas). Resolves to a texture. */
  function engraving(art, size = 256) {
    const svg = B.practiceArt(art, { draw: false, glow: "#e2bd6a" }).replace(/<svg class="[^"]*"/, `<svg width="${size}" height="${size}"`);
    const [c, x] = canvas(size), t = tex(c);
    const img = new Image(); img.decoding = "async";
    img.onload = () => { x.clearRect(0, 0, size, size); x.drawImage(img, 0, 0, size, size); t.needsUpdate = true; };
    img.src = "data:image/svg+xml;charset=utf-8," + encodeURIComponent(svg);
    return t;
  }
  const T = {
    stone: tex(stone(), { repeat: [12, 3] }), floor: tex(wood(), { repeat: [8, 8] }), table: tex(wood([58, 36, 26]), { repeat: [1, 1] }),
    rug: tex(rug()), velvet: tex(velvet()), parchment: tex(parchment()), chart: tex(starChart()),
    gold: tex(matcap([[0, "#fff1c8"], [.35, "#e2bd6a"], [.75, "#7d5c24"], [1, "#2b1d0a"]])),
    brass: tex(matcap([[0, "#f3dca0"], [.4, "#b48a45"], [.8, "#4a3416"], [1, "#1d1307"]], "rgba(255,240,210,.7)")),
    darkwood: tex(matcap([[0, "#8a6040"], [.5, "#4a2e1c"], [1, "#120a06"]], "rgba(255,220,180,.25)")),
    glass: tex(matcap([[0, "#cfd8ff"], [.5, "#3a3477"], [1, "#0b0920"]], "rgba(255,255,255,.9)")),
    ceramic: tex(matcap([[0, "#fff8ee"], [.55, "#d9cfc0"], [1, "#5a5048"]], "rgba(255,255,255,.95)")),
    glow: tex(glow(), { srgb: false }), glowCool: tex(glow("235,240,255", "170,190,255"), { srgb: false }),
    glowViolet: tex(glow("240,230,255", "139,108,255"), { srgb: false }), smoke: tex(smoke(), { srgb: false }),
    flatN: (() => { const [c, x] = canvas(4); x.fillStyle = "rgb(128,128,255)"; x.fillRect(0, 0, 4, 4); return tex(c, { srgb: false, mips: false }); })(),   // a flat normal map until the real one arrives
  };
  /* a runtime image (img/<name>.webp), decoded off the main thread where the browser can; sRGB for colour maps */
  function load(name, { srgb = true } = {}) {
    const img = new Image(); img.decoding = "async"; img.src = new URL(`./img/${name}.webp?v=${V}`, import.meta.url).href;
    return img.decode().then(() => { const t = new THREE.Texture(img); if (srgb) t.colorSpace = THREE.SRGBColorSpace;
      t.anisotropy = 4; t.needsUpdate = true; made.push(t); return t; });
  }
  const track = (t) => { made.push(t); return t; };
  const release = (t) => { if (!t) return; const i = made.indexOf(t); if (i >= 0) made.splice(i, 1); t.dispose(); };
  return { T, tex, engraving, load, track, release, canvas, rng, dispose() { made.forEach((t) => t.dispose()); made.length = 0; } };
}
