/* Oracle chamber (FULL tier): the room's shell. Ten flat stone faces (the moon face has a real opening), an oak floor
   and wainscot, beveled gold moldings, pillars, ten candle sconces (instanced), velvet drapes (instanced) and the
   gothic moon window (a deep stone reveal, a carved frame with tracery, glass, a stone sill and three candles).
   Light: the sconces are not three.js lights. Their pools are computed in the shell's own shader (inverse-square
   falloff, a finite range, one loop over ten points), so the room has candle pools and dark corners for the cost of
   one shader loop; only the central candle and the moon cast shadows. Every surface material also breaks its
   texture's repetition with a low-frequency variation (patches, soot over the candles, dark corners, wear). */

const TAU = Math.PI * 2;
export const FW = 2 * 6 * Math.sin(Math.PI / 10);   // the width of one wall face (corner radius 6 m)
const TILE = { stone: 1.7, oak: 1.3, velvet: .55 };   // metres per texture tile
const N = 10;                                          // sconces

/* uniforms shared by every shell material: the sconce flames (xyz world, w intensity) and their colour */
export function makeSconceUniforms(THREE) {
  return { uSc: { value: Array.from({ length: N }, () => new THREE.Vector4()) }, uScCol: { value: new THREE.Color(0xf2a958) } };
}

const MACRO = {
  none: "vec3 chMacro(vec3 p, inout float r) { return vec3(1.0); }",
  /* stone: large patches, soot above every flame, grime at the foot, smoke under the dome, darker corners */
  wall: `vec3 chMacro(vec3 p, inout float r) {
    float n = chF(vec2(p.x * 0.7 + p.z * 0.7, p.y) * 0.55), k = mix(0.68, 1.14, n);
    float a = atan(p.x, -p.z) / ${(TAU / N).toFixed(6)}, dc = abs(fract(a) - 0.5) * ${FW.toFixed(4)};   // metres to the nearest corner (its sconce)
    float soot = exp(-dc * dc / 0.12 - (p.y - 2.96) * (p.y - 2.96) / 0.45) * step(2.2, p.y);            // smoke above the flame
    k *= 1.0 - 0.55 * soot;
    k *= mix(0.7, 1.0, smoothstep(0.0, 1.0, p.y)) * mix(1.0, 0.72, smoothstep(3.1, 4.2, p.y));
    k *= mix(0.62, 1.0, smoothstep(0.0, 0.2 * ${FW.toFixed(4)}, dc));
    r *= mix(0.92, 1.08, n); return vec3(k); }`,
  /* oak: patches and plank-scale tone, a worn walk round the objects (lighter, smoother), dust against the walls */
  floor: `vec3 chMacro(vec3 p, inout float r) {
    float n = chF(p.xz * 0.45), n2 = chN(p.xz * 1.7 + 5.0), rr = length(p.xz);
    float k = mix(0.7, 1.1, n) * mix(0.9, 1.05, n2);
    float wear = exp(-pow((rr - 2.5) / 0.32, 2.0)) * (0.55 + 0.45 * n2);
    k *= 1.0 + wear * 0.25; r *= 1.0 - wear * 0.3;
    k *= mix(1.0, 0.6, smoothstep(4.4, 5.7, rr)); return vec3(k); }`,
  /* velvet: slow light/dark patches across the folds, so the tile never repeats visibly */
  cloth: `vec3 chMacro(vec3 p, inout float r) { float n = chF(vec2(p.x + p.z, p.y) * 0.9); return vec3(mix(0.7, 1.15, n)); }`,
};

/* a MeshStandardMaterial for the shell: roughness from the albedo (lo..hi), the macro variation, the sconce pools,
   and (vary) a per-instance texture offset and rotation from the attribute aVar */
export function surface(THREE, SC, { macro = "none", rough = [.6, .9], vary = false, ...opts }) {
  const m = new THREE.MeshStandardMaterial({ metalness: 0, roughness: rough[1], ...opts });
  const uRough = { value: new THREE.Vector2(rough[0], rough[1]) };
  m.onBeforeCompile = (sh) => {
    Object.assign(sh.uniforms, SC, { uRough });
    sh.vertexShader = sh.vertexShader.replace("#include <common>", `#include <common>
      varying vec3 vWPos;${vary ? "\n      attribute vec3 aVar;" : ""}`)
      .replace("#include <project_vertex>", `#include <project_vertex>
      { vec4 w = vec4(transformed, 1.0);
        #ifdef USE_INSTANCING
        w = instanceMatrix * w;
        #endif
        vWPos = (modelMatrix * w).xyz; }`);
    if (vary) sh.vertexShader = sh.vertexShader.replace("#include <uv_vertex>", `#include <uv_vertex>
      { mat2 rot = mat2(cos(aVar.z), sin(aVar.z), -sin(aVar.z), cos(aVar.z));
        #ifdef USE_MAP
        vMapUv = rot * vMapUv + aVar.xy;
        #endif
        #ifdef USE_BUMPMAP
        vBumpMapUv = rot * vBumpMapUv + aVar.xy;
        #endif
      }`);
    sh.fragmentShader = sh.fragmentShader.replace("#include <common>", `#include <common>
      varying vec3 vWPos; uniform vec4 uSc[${N}]; uniform vec3 uScCol; uniform vec2 uRough;
      float chH(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
      float chN(vec2 p) { vec2 i = floor(p), f = fract(p); f = f * f * (3.0 - 2.0 * f);
        return mix(mix(chH(i), chH(i + vec2(1.0, 0.0)), f.x), mix(chH(i + vec2(0.0, 1.0)), chH(i + vec2(1.0, 1.0)), f.x), f.y); }
      float chF(vec2 p) { return chN(p) * 0.5 + chN(p * 2.07 + 13.1) * 0.3 + chN(p * 4.3 + 7.7) * 0.2; }
      ${MACRO[macro]}`)
      .replace("#include <map_fragment>", "#include <map_fragment>\n      float chRough = 1.0; diffuseColor.rgb *= chMacro(vWPos, chRough);")
      .replace("#include <roughnessmap_fragment>", `#include <roughnessmap_fragment>
      roughnessFactor = clamp(mix(uRough.y, uRough.x, smoothstep(0.015, 0.25, dot(diffuseColor.rgb, vec3(0.2126, 0.7152, 0.0722)))) * chRough, 0.05, 1.0);`)
      .replace("#include <lights_fragment_end>", `#include <lights_fragment_end>
      { vec3 nW = inverseTransformDirection(geometryNormal, viewMatrix), acc = vec3(0.0);
        for (int i = 0; i < ${N}; i++) { vec3 L = uSc[i].xyz - vWPos; float d = max(length(L), 0.05);
          float fall = pow(clamp(1.0 - pow(d / 3.6, 4.0), 0.0, 1.0), 2.0) / (d * d);   // inverse square, gone by 3.6 m
          acc += uSc[i].w * fall * max(dot(nW, L / d), 0.0); }
        reflectedLight.directDiffuse += acc * uScCol * BRDF_Lambert(material.diffuseColor); }`);
  };
  m.customProgramCacheKey = () => `ch-${macro}-${vary}`;   // few programs: each one costs compile time at boot
  return m;
}

/* a small warm room environment for the metals (reflections of candle pools and the window), made once */
function roomEnv(THREE, renderer) {
  const c = document.createElement("canvas"); c.width = 256; c.height = 128; const x = c.getContext("2d");
  const g = x.createLinearGradient(0, 0, 0, 128);
  g.addColorStop(0, "#0e0a16"); g.addColorStop(.42, "#24160f"); g.addColorStop(.52, "#3a2414"); g.addColorStop(.62, "#1c120c"); g.addColorStop(1, "#0a0708");
  x.fillStyle = g; x.fillRect(0, 0, 256, 128);
  const spot = (cx, cy, r, col) => { const s = x.createRadialGradient(cx, cy, 0, cx, cy, r); s.addColorStop(0, col); s.addColorStop(1, "rgba(0,0,0,0)"); x.fillStyle = s; x.fillRect(cx - r, cy - r, r * 2, r * 2); };
  for (let i = 0; i < 10; i++) spot((i + .5) * 25.6, 54, 9, "rgba(255,196,120,.95)");
  spot(64, 50, 20, "rgba(170,190,255,.45)");
  spot(128, 20, 40, "rgba(60,50,110,.35)");
  const t = new THREE.CanvasTexture(c); t.mapping = THREE.EquirectangularReflectionMapping; t.colorSpace = THREE.SRGBColorSpace;
  const pm = new THREE.PMREMGenerator(renderer), rt = pm.fromEquirectangular(t); pm.dispose(); t.dispose();
  return rt;
}

/* concatenate non-indexed position/normal/uv of several geometries (already in place) */
function merge(THREE, geos) {
  const parts = geos.map((g) => (g.index ? g.toNonIndexed() : g)), out = new THREE.BufferGeometry();
  for (const [name, size] of [["position", 3], ["normal", 3], ["uv", 2]]) {
    const len = parts.reduce((a, g) => a + g.attributes[name].array.length, 0), buf = new Float32Array(len); let o = 0;
    for (const g of parts) { buf.set(g.attributes[name].array, o); o += g.attributes[name].array.length; }
    out.setAttribute(name, new THREE.BufferAttribute(buf, size));
  }
  geos.forEach((g) => g.dispose()); parts.forEach((g) => g.dispose());
  return out;
}
const scaleUV = (g, sx, sy) => { const uv = g.attributes.uv; for (let i = 0; i < uv.count; i++) uv.setXY(i, uv.getX(i) * sx, uv.getY(i) * sy); return g; };

/* a pointed (gothic) arch outline from the bottom left, up, over the apex and down: half width hw, springing at hs,
   arcs of radius R centred on the opposite springers' side */
function pointed(THREE, hw, hs, R, n = 18) {
  const pts = [new THREE.Vector2(-hw, 0), new THREE.Vector2(-hw, hs)], top = Math.acos((hw - R) / R);
  for (let i = 1; i <= n; i++) { const t = Math.PI + (top - Math.PI) * i / n; pts.push(new THREE.Vector2(-hw + R + Math.cos(t) * R, hs + Math.sin(t) * R)); }
  for (let i = n - 1; i >= 0; i--) { const t = Math.PI + (top - Math.PI) * i / n; pts.push(new THREE.Vector2(hw - R - Math.cos(t) * R, hs + Math.sin(t) * R)); }
  pts.push(new THREE.Vector2(hw, 0));   // the right arc already ends on the springer (hw, hs)
  return pts;
}
const archHeight = (hw, hs, R) => hs + Math.sqrt(R * R - (R - hw) * (R - hw));

/* a wax candle: a lathe with a soft, melted top and a few drips down the side */
export function waxGeometry(THREE, h, r, seed = 1) {
  const prof = [[0, 0], [r * 1.05, 0], [r * 1.03, h * .1], [r, h * .55], [r * .99, h * .9], [r * .93, h * .985], [r * .55, h], [r * .2, h * .975], [0, h * .97]];
  const g = new THREE.LatheGeometry(prof.map(([x, y]) => new THREE.Vector2(x, y)), 20), p = g.attributes.position;
  const ss = (a, b, v) => { const t = Math.min(1, Math.max(0, (v - a) / (b - a))); return t * t * (3 - 2 * t); };
  for (let i = 0; i < p.count; i++) { const x = p.getX(i), y = p.getY(i), z = p.getZ(i), a = Math.atan2(x, z);
    const k = 1 + .16 * Math.max(0, Math.sin(a * 3 + seed * 2.1)) ** 12 * ss(.35, .97, y / h) + .1 * Math.max(0, Math.sin(a * 5 + seed)) ** 16 * ss(.7, .99, y / h);
    p.setX(i, x * k); p.setZ(i, z * k); }
  g.computeVertexNormals(); return g;
}

/* velvet drape: a sheet with vertical folds (deeper at the hem), gathered at the top; bottom at y = 0 */
function drapeGeometry(THREE, w, h) {
  const g = new THREE.PlaneGeometry(w, h, 30, 18); g.translate(0, h / 2, 0);
  const p = g.attributes.position, uv = g.attributes.uv;
  for (let i = 0; i < p.count; i++) { const x = p.getX(i), y = p.getY(i), t = y / h;
    const fold = Math.sin(x * 30 + 1.3) * .045 + Math.sin(x * 63 + 4) * .014 + Math.sin(x * 11 + .4) * .03;
    uv.setXY(i, (x + w / 2) / TILE.velvet, y / TILE.velvet);
    p.setXYZ(i, x * (1 - .3 * t), y, .09 + fold * (.45 + .55 * (1 - t)) + .05 * (1 - t)); }
  g.computeVertexNormals(); return g;
}

export function buildShell(THREE, { scene, X, F, SC, renderer, STEP, WALL, moonSlot }) {
  const T = X.T, env = roomEnv(THREE, renderer);
  for (const t of [T.stone, T.floor, T.velvet]) { t.wrapS = t.wrapT = THREE.RepeatWrapping; t.repeat.set(1, 1); }
  const flatN = T.flatN;
  const mats = {
    stone: surface(THREE, SC, { map: T.stone, normalMap: flatN, color: 0xd2c8c8, macro: "wall", rough: [.72, .96] }),
    reveal: surface(THREE, SC, { map: T.stone, normalMap: flatN, normalScale: new THREE.Vector2(.35, .35), color: 0x7a7074, macro: "wall", rough: [.72, .96] }),
    pillar: surface(THREE, SC, { map: T.stone, normalMap: flatN, color: 0xb4aaae, macro: "wall", rough: [.72, .96] }),
    floor: surface(THREE, SC, { map: T.floor, normalMap: flatN, macro: "floor", rough: [.4, .8] }),
    wains: surface(THREE, SC, { map: T.floor, normalMap: flatN, color: 0xb8a698, macro: "wall", rough: [.5, .82] }),
    frame: surface(THREE, SC, { map: T.floor, normalMap: flatN, color: 0x6e5a4c, macro: "none", rough: [.45, .75] }),
    rug: surface(THREE, SC, { map: T.rug, bumpMap: T.rug, bumpScale: 2, macro: "none", rough: [.86, .98] }),
    velvet: surface(THREE, SC, { map: T.velvet, bumpMap: T.velvet, bumpScale: 1.5, macro: "none", rough: [.62, .95] }),
    drape: surface(THREE, SC, { map: T.velvet, bumpMap: T.velvet, bumpScale: 1.5, color: 0xd8d0ff, macro: "cloth", rough: [.55, .95], vary: true }),
    wax: surface(THREE, SC, { color: 0xeadcc0, emissive: 0x2a1406, macro: "none", rough: [.45, .6] }),
    gold: new THREE.MeshStandardMaterial({ color: 0xd4a84f, metalness: .8, roughness: .35, envMap: env.texture, envMapIntensity: 1.2 }),
    iron: new THREE.MeshStandardMaterial({ color: 0x2a2420, metalness: .7, roughness: .5, envMap: env.texture, envMapIntensity: .6 }),
  };
  /* which materials show which photographic set (upgrade swaps a set's texture into all of them at once) */
  const sets = { stone: [mats.stone, mats.reveal, mats.pillar], floor: [mats.floor, mats.wains, mats.frame], rug: [mats.rug], velvet: [mats.velvet, mats.drape] };
  const casters = [], receivers = [];
  const add = (m, { cast = false, receive = true } = {}) => { scene.add(m); if (cast) casters.push(m); if (receive) receivers.push(m); return m; };
  const faceM = (a, y = 0) => new THREE.Matrix4().compose(new THREE.Vector3(Math.sin(a) * WALL, y, -Math.cos(a) * WALL),
    new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0, 1, 0), -a), new THREE.Vector3(1, 1, 1));

  /* ── the moon window's measures (local: x across, y up from the sill, z towards the room) ── */
  const W = { hw: .75, hs: 1.39, R: 1.125, D: .42, sill: 1.0, t: .075, m: .06 };
  W.H = archHeight(W.hw, W.hs, W.R);

  /* ── walls: ten faces, uv in stone tiles (continuous round the room); the moon face has the opening ── */
  const faces = [];
  for (let k = 0; k < 10; k++) {
    const sh = new THREE.Shape([new THREE.Vector2(-FW / 2, 0), new THREE.Vector2(FW / 2, 0), new THREE.Vector2(FW / 2, 4.2), new THREE.Vector2(-FW / 2, 4.2)]);
    if (k === moonSlot) sh.holes.push(new THREE.Path(pointed(THREE, W.hw, W.hs, W.R).map((p) => new THREE.Vector2(p.x, p.y + W.sill))));
    const g = new THREE.ShapeGeometry(sh, 16), p = g.attributes.position, uv = g.attributes.uv;
    for (let i = 0; i < p.count; i++) uv.setXY(i, (k * FW + p.getX(i) + FW / 2) / TILE.stone, p.getY(i) / TILE.stone);
    faces.push(g.applyMatrix4(faceM(k * STEP)));
  }
  const wallsOnly = { receive: false };   // both shadow lights look down: shadows fall on the floor, so the walls skip the lookups
  add(new THREE.Mesh(merge(THREE, faces), mats.stone), wallsOnly);
  // wainscot: oak planks to 0.9 m, a little proud of the stone
  const wains = [];
  for (let k = 0; k < 10; k++) { const g = new THREE.PlaneGeometry(FW - .02, .9); g.translate(0, .45, .025);
    const uv = g.attributes.uv; for (let i = 0; i < uv.count; i++) uv.setXY(i, (k * FW + uv.getX(i) * FW) / TILE.oak, uv.getY(i) * .9 / TILE.oak);
    wains.push(g.applyMatrix4(faceM(k * STEP))); }
  add(new THREE.Mesh(merge(THREE, wains), mats.wains), wallsOnly);
  // floor: uv in oak tiles from the world position
  { const g = new THREE.CircleGeometry(6.2, 10, Math.PI / 10); g.rotateX(-Math.PI / 2);
    const p = g.attributes.position, uv = g.attributes.uv; for (let i = 0; i < p.count; i++) uv.setXY(i, p.getX(i) / TILE.oak, p.getZ(i) / TILE.oak);
    add(new THREE.Mesh(g, mats.floor)); }
  { const rug = new THREE.Mesh(new THREE.CircleGeometry(2.3, 72), mats.rug); rug.rotation.x = -Math.PI / 2; rug.position.y = .006; add(rug); }

  /* ── moldings: real profiles turned round the decagon (lathe, 10 sides), metal lit by the scene ── */
  const molding = (prof, y) => { const g = new THREE.LatheGeometry(prof.map(([d, h]) => new THREE.Vector2(6 - d, y + h)).reverse(), 10, Math.PI / 10);   // reversed: faces look inwards
    return add(new THREE.Mesh(g, mats.gold), { receive: false }); };
  molding([[0, -.06], [.012, -.056], [.018, -.042], [.016, -.03], [.028, -.022], [.036, -.008], [.038, .004], [.032, .016], [.02, .022], [.025, .032], [.012, .042], [0, .046]], .9);   // dado: bead and cove
  molding([[0, 0], [.015, .01], [.02, .03], [.035, .05], [.05, .08], [.06, .11], [.058, .13], [.07, .15], [.09, .18], [.105, .2], [.11, .23], [0, .25]], 3.95);   // crown under the dome
  molding([[0, 0], [.03, 0], [.034, .012], [.03, .028], [.02, .036], [.02, .07], [0, .075]], 0);   // skirting
  // pillars at the corners: stone shafts, a gold capital, a stone base
  const capG = new THREE.LatheGeometry([[.2, 0], [.2, .03], [.16, .05], [.17, .08], [.21, .11], [.24, .15], [.24, .18], [0, .18]].map(([r, y]) => new THREE.Vector2(r, y)), 20);
  const baseG = new THREE.LatheGeometry([[0, 0], [.25, 0], [.25, .06], [.21, .08], [.22, .11], [.18, .14], [.17, .2]].map(([r, y]) => new THREE.Vector2(r, y)), 20);
  const shaftG = scaleUV(new THREE.CylinderGeometry(.13, .15, 4.2, 14), .9 / TILE.stone, 4.2 / TILE.stone);
  const pillarAt = (k) => { const a = (k + .5) * STEP; return [Math.sin(a) * 5.8, -Math.cos(a) * 5.8]; };
  { const shaft = new THREE.InstancedMesh(shaftG, mats.pillar, 10), cap = new THREE.InstancedMesh(capG, mats.gold, 10), base = new THREE.InstancedMesh(baseG, mats.pillar, 10), o = new THREE.Object3D();
    for (let k = 0; k < 10; k++) { const [x, z] = pillarAt(k);
      o.position.set(x, 2.1, z); o.updateMatrix(); shaft.setMatrixAt(k, o.matrix);
      o.position.set(x, 3.77, z); o.updateMatrix(); cap.setMatrixAt(k, o.matrix);
      o.position.set(x, 0, z); o.updateMatrix(); base.setMatrixAt(k, o.matrix); }
    add(shaft, { cast: true, receive: false }); add(cap, { receive: false }); add(base); }

  /* ── sconces on the pillars (instanced): a gold back plate, an iron arm, a gold dish, a wax candle and its flame ── */
  const sconceFrame = (k) => { const a = (k + .5) * STEP; return new THREE.Matrix4().compose(new THREE.Vector3(Math.sin(a) * 5.66, 0, -Math.cos(a) * 5.66),
    new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0, 1, 0), -a), new THREE.Vector3(1, 1, 1)); };
  const plateG = new THREE.CylinderGeometry(.07, .08, .018, 24).rotateX(Math.PI / 2).scale(1, 1.9, 1).translate(0, 2.2, .01);   // a tall back plate behind the flame
  const armG = new THREE.CylinderGeometry(.011, .013, .27, 8).rotateX(Math.PI / 2 + .45).translate(0, 2.06, .13);
  const dishG = new THREE.LatheGeometry([[0, 0], [.03, 0], [.07, .02], [.075, .03], [.07, .032]].map(([r, y]) => new THREE.Vector2(r, y)), 18).translate(0, 2.11, .25);
  const sconceWax = waxGeometry(THREE, .17, .021, 3).translate(0, 2.13, .25);
  const sconceParts = [[plateG, mats.gold], [armG, mats.iron], [dishG, mats.gold], [sconceWax, mats.wax]].map(([g, m]) => { const im = new THREE.InstancedMesh(g, m, N);
    for (let k = 0; k < N; k++) im.setMatrixAt(k, sconceFrame(k)); add(im, { receive: false }); return im; });
  const flames = [];
  for (let k = 0; k < N; k++) { const at = new THREE.Vector3(0, 2.3, .25).applyMatrix4(sconceFrame(k));
    const fl = F.flame(.05, k * .37); fl.position.copy(at).setY(2.298); scene.add(fl);
    const gl = F.glow(T.glow, 0xffc27a, .62, .5); gl.position.copy(at).setY(2.34); scene.add(gl);
    SC.uSc.value[k].set(at.x * .985, 2.36, at.z * .985, 0); flames.push({ fl, gl, k }); }

  /* ── velvet drapes (instanced): beside every corner and both sides of the window; each with its own texture
     offset and rotation (aVar), so the tile never lines up ── */
  const drapeAt = [];
  for (let k = 0; k < 10; k++) { if (k === moonSlot) continue; for (const s of [-1, 1]) drapeAt.push([k, s * (FW / 2 - .42), .62]); }
  drapeAt.push([moonSlot, -1.13, .72], [moonSlot, 1.13, .72]);
  { const g = drapeGeometry(THREE, 1, 3.86), aVar = new Float32Array(drapeAt.length * 3), rnd = X.rng(17);
    const im = new THREE.InstancedMesh(g, mats.drape, drapeAt.length);
    drapeAt.forEach(([k, x, w], i) => { im.setMatrixAt(i, faceM(k * STEP).multiply(new THREE.Matrix4().makeTranslation(x, 0, 0)).multiply(new THREE.Matrix4().makeScale(w, 1, 1)));
      aVar.set([rnd() * 7, rnd() * 7, (rnd() - .5) * 1.2], i * 3); });
    g.setAttribute("aVar", new THREE.InstancedBufferAttribute(aVar, 3));
    add(im, { cast: true, receive: false }); }   // receiving the soft point shadow over this much cloth cost High 7 fps; against the wall it barely shows

  /* ── the moon window ── */
  const win = new THREE.Group(); win.applyMatrix4(faceM(moonSlot * STEP, W.sill));
  const outline = pointed(THREE, W.hw, W.hs, W.R);
  // the reveal: the opening's sides, from the wall face back to the glass; stone, uv in tiles
  { const pos = [], uv = []; let s = 0;
    for (let i = 0; i < outline.length - 1; i++) {   // both jambs and the arch; the bottom is the sill
      const a = outline[i], b = outline[i + 1], l = a.distanceTo(b);
      const q = [[a.x, a.y, 0, s, 0], [b.x, b.y, 0, s + l, 0], [b.x, b.y, -W.D, s + l, W.D], [a.x, a.y, -W.D, s, W.D]];
      for (const j of [0, 2, 1, 0, 3, 2]) {   // wound to face the opening
        pos.push(q[j][0], q[j][1], q[j][2]); uv.push(q[j][3] / TILE.stone, q[j][4] / TILE.stone); }
      s += l; }
    const g = new THREE.BufferGeometry(); g.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3)); g.setAttribute("uv", new THREE.Float32BufferAttribute(uv, 2)); g.computeVertexNormals();
    win.add(new THREE.Mesh(g, mats.reveal)); }
  // the frame: one carved piece of dark oak, the opening minus two lights (each split by a transom) and an oculus
  const yT = 1.0, ys = 1.45, hwl = (W.hw - W.t - W.m / 2) / 2, xl = W.m / 2 + hwl, Rl = hwl * 1.5;
  { const sh = new THREE.Shape(outline);
    for (const side of [-1, 1]) { const cx = side * xl;
      sh.holes.push(new THREE.Path([[cx - hwl, W.t], [cx + hwl, W.t], [cx + hwl, yT - .025], [cx - hwl, yT - .025]].map(([x, y]) => new THREE.Vector2(x, y))));
      sh.holes.push(new THREE.Path(pointed(THREE, hwl, ys - yT - .025, Rl, 12).map((p) => new THREE.Vector2(p.x + cx, p.y + yT + .025)))); }
    const oc = new THREE.Path(); oc.absarc(0, 2.12, .17, 0, TAU, true); sh.holes.push(oc);
    const g = new THREE.ExtrudeGeometry(sh, { depth: .07, bevelEnabled: true, bevelThickness: .014, bevelSize: .012, bevelSegments: 2, curveSegments: 28 });
    g.translate(0, 0, -W.D + .04); scaleUV(g, 1 / TILE.oak, 1 / TILE.oak);
    const m = new THREE.Mesh(g, mats.frame); win.add(m); casters.push(m); }
  // gold fittings: the oculus ring, bosses where the bars meet, plates at the springers
  { const ring = new THREE.Mesh(new THREE.TorusGeometry(.17, .013, 8, 48), mats.gold); ring.position.set(0, 2.12, -W.D + .14); win.add(ring);
    const bossG = new THREE.SphereGeometry(.022, 12, 8), plateG2 = new THREE.BoxGeometry(.05, .09, .012);
    for (const [x, y] of [[0, yT], [-xl, yT], [xl, yT], [0, ys + .2]]) { const b = new THREE.Mesh(bossG, mats.gold); b.position.set(x, y, -W.D + .135); b.scale.z = .6; win.add(b); }
    for (const x of [-W.hw + .04, W.hw - .04]) for (const y of [W.hs, .4]) { const p = new THREE.Mesh(plateG2, mats.gold); p.position.set(x, y, -W.D + .13); win.add(p); } }
  // the glass, just behind the frame: the landscape and the moon (room.js gives it the window shader)
  const paneShape = new THREE.Shape(pointed(THREE, W.hw - W.t / 2, W.hs, W.R - W.t / 2));
  const paneGeo = new THREE.ShapeGeometry(paneShape, 24); { const p = paneGeo.attributes.position, uv = paneGeo.attributes.uv, hw = W.hw - W.t / 2, H = archHeight(hw, W.hs, W.R - W.t / 2);
    for (let i = 0; i < p.count; i++) uv.setXY(i, (p.getX(i) + hw) / (2 * hw), p.getY(i) / H); paneGeo.userData.size = [2 * hw, H]; }
  paneGeo.translate(0, 0, -W.D + .03);
  // a thick stone sill, out into the room
  { const g = scaleUV(new THREE.BoxGeometry(W.hw * 2 + .5, .12, W.D + .3), 2 / TILE.stone, .6 / TILE.stone);
    const m = new THREE.Mesh(g, mats.stone); m.position.set(0, -.06, -W.D / 2 + .15); win.add(m); casters.push(m); receivers.push(m); }
  // three candles on the sill: wax, a wick, a living flame; the moon ritual makes them flare
  const sill = [[-.5, .2], [.02, .27], [.46, .16]], waxI = new THREE.InstancedMesh(waxGeometry(THREE, 1, .032, 2), mats.wax, 3);
  sill.forEach(([x, h], i) => waxI.setMatrixAt(i, new THREE.Matrix4().compose(new THREE.Vector3(x, 0, .08), new THREE.Quaternion(), new THREE.Vector3(1, h, 1))));
  win.add(waxI); casters.push(waxI);
  const ritual = sill.map(([x, h], seed) => {
    const c = new THREE.Group(); c.position.set(x, 0, .08);
    const wick = new THREE.Mesh(new THREE.CylinderGeometry(.002, .002, .02, 4), mats.iron); wick.position.y = h + .005; c.add(wick);
    const fl = F.flame(.075, seed * .21); fl.position.y = h + .002; c.add(fl);
    const gl = F.glow(T.glow, 0xffc27a, .7, .55); gl.position.y = h + .06; c.add(gl);
    c.userData = { flame: fl, glow: gl, flare: 0, f: 0 }; win.add(c); return c; });
  scene.add(win);

  /* every frame: the sconces flicker (their pools follow), the sill candles flare during the ritual */
  const flick = (t, s) => .84 + Math.sin(t * 7.1 + s) * .05 + Math.sin(t * 13.3 + s * 3) * .04 + Math.sin(t * 2.3 + s * 5) * .07;
  function update(t, dt) {
    for (const { gl, k } of flames) { const f = flick(t, k * 1.7); SC.uSc.value[k].w = 3.2 * f; gl.material.opacity = .5 * f; }
    for (const c of ritual) { const u = c.userData; u.f += (u.flare - u.f) * Math.min(1, dt * 2); const s = 1 + u.f * .55;
      u.flame.scale.setScalar(s); u.glow.scale.setScalar(.7 * s); u.glow.material.opacity = .55 + u.f * .3; }
  }
  return { mats, sets, casters, receivers, win, W, paneGeo, ritual, env, update };
}
