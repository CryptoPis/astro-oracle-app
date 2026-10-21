/* Oracle chamber (FULL tier): the room's shell. Ten flat stone faces (the moon face has a real opening), an oak floor
   and wainscot, beveled gold moldings, pillars with two candelabras each, velvet drapes with gold borders, the gothic
   moon window (a deep stone reveal with an arch molding, a carved frame with lancets and a quatrefoil, gold fittings,
   glass, a stone sill on corbels and three candles) and the gold architecture of the dome (ribs, rings, medallions).
   Light without lights: the candelabras' pools are computed in the shell's own shader (inverse-square falloff, a
   finite range, one loop over eleven points) and drawn again as soft additive decals on the walls and pillars; the
   glossy floor shows a long reflection streak of every candelabra and of the window (view-dependent, in the floor
   shader). Only the central candle and the moon are three.js lights that cast shadows. Every surface breaks its
   texture's repetition with a low-frequency variation (patches, soot over the candles, dark corners, wear). */

const TAU = Math.PI * 2;
export const FW = 2 * 6 * Math.sin(Math.PI / 10);   // the width of one wall face (corner radius 6 m)
const TILE = { stone: 1.7, oak: 1.3, velvet: .55 };   // metres per texture tile
const N = 11;                                          // light points: ten candelabras (one per pillar) + the window sill

/* uniforms shared by every shell material: the light points (xyz world, w intensity), their colour, the window */
export function makeSconceUniforms(THREE) {
  return { uSc: { value: Array.from({ length: N }, () => new THREE.Vector4()) }, uScCol: { value: new THREE.Color(0xf2a958) },
    uWin: { value: new THREE.Vector4() }, uStreak: { value: 1 } };
}

const MACRO = {
  none: "vec3 chMacro(vec3 p, inout float r) { return vec3(1.0); }",
  /* stone: large patches, soot above both candle clusters, grime at the foot, smoke under the dome, darker corners */
  wall: `vec3 chMacro(vec3 p, inout float r) {
    float n = chF(vec2(p.x * 0.7 + p.z * 0.7, p.y) * 0.55), k = mix(0.68, 1.14, n);
    float a = atan(p.x, -p.z) / ${(TAU / 10).toFixed(6)}, dc = abs(fract(a) - 0.5) * ${FW.toFixed(4)};   // metres to the nearest corner (its candelabras)
    float soot = exp(-dc * dc / 0.16) * (exp(-(p.y - 2.75) * (p.y - 2.75) / 0.5) * 0.75 + exp(-(p.y - 1.75) * (p.y - 1.75) / 0.12) * 0.35);
    k *= 1.0 - 0.7 * soot;
    k *= mix(0.7, 1.0, smoothstep(0.0, 1.0, p.y)) * mix(1.0, 0.72, smoothstep(3.1, 4.2, p.y));
    k *= mix(0.62, 1.0, smoothstep(0.0, 0.2 * ${FW.toFixed(4)}, dc));
    r *= mix(0.92, 1.08, n); return vec3(k); }`,
  /* oak: patches and plank-scale tone, a worn walk round the objects (lighter, smoother), dust against the walls */
  floor: `vec3 chMacro(vec3 p, inout float r) {
    float n = chF(p.xz * 0.45), n2 = chN(p.xz * 1.7 + 5.0), rr = length(p.xz);
    float k = mix(0.72, 1.1, n) * mix(0.9, 1.05, n2);
    float wear = exp(-pow((rr - 2.85) / 0.32, 2.0)) * (0.55 + 0.45 * n2);
    k *= 1.0 + wear * 0.25; r *= 1.0 - wear * 0.3;
    k *= mix(1.0, 0.65, smoothstep(4.6, 5.7, rr)); return vec3(k); }`,
  /* velvet drapes: slow light/dark patches, a darker centre and a gold embroidered border down both edges */
  cloth: `vec3 chMacro(vec3 p, inout float r) {
    float n = chF(vec2(p.x + p.z, p.y) * 0.9), u = vRawUv.x / ${(1 / TILE.velvet).toFixed(4)}, e = min(u, 1.0 - u), y = vRawUv.y * ${TILE.velvet.toFixed(3)};
    float band = 1.0 - smoothstep(0.075, 0.085, e);
    vec2 q = vec2(e / 0.08 - 0.5, fract(y * 6.0) - 0.5); float dd = abs(q.x) * 1.4 + abs(q.y);
    float motif = (1.0 - smoothstep(0.3, 0.36, dd)) * smoothstep(0.12, 0.16, dd) + (1.0 - smoothstep(0.05, 0.09, dd));   // a lozenge chain
    float lines = (1.0 - smoothstep(0.003, 0.006, abs(e - 0.012))) + (1.0 - smoothstep(0.003, 0.006, abs(e - 0.07)));
    chGold = band * clamp(motif * 0.9 + lines, 0.0, 1.0);
    r *= mix(1.0, 0.45, chGold);
    return vec3(mix(0.7, 1.15, n) * mix(0.66, 1.0, 1.0 - smoothstep(0.1, 0.42, e))); }`,
};

/* a MeshStandardMaterial for the shell: roughness from the albedo (lo..hi), the macro variation, the light points'
   pools, (vary) a per-instance texture offset and rotation from the attribute aVar, (streaks) the floor's reflections */
export function surface(THREE, SC, { macro = "none", rough = [.6, .9], vary = false, streaks = false, ...opts }) {
  const m = new THREE.MeshStandardMaterial({ metalness: 0, roughness: rough[1], ...opts });
  const uRough = { value: new THREE.Vector2(rough[0], rough[1]) };
  m.onBeforeCompile = (sh) => {
    Object.assign(sh.uniforms, SC, { uRough });
    sh.vertexShader = sh.vertexShader.replace("#include <common>", `#include <common>
      varying vec3 vWPos; varying vec2 vRawUv;${vary ? "\n      attribute vec3 aVar;" : ""}`)
      .replace("#include <project_vertex>", `#include <project_vertex>
      { vec4 w = vec4(transformed, 1.0);
        #ifdef USE_INSTANCING
        w = instanceMatrix * w;
        #endif
        vWPos = (modelMatrix * w).xyz; vRawUv = uv; }`);
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
      varying vec3 vWPos; varying vec2 vRawUv; uniform vec4 uSc[${N}]; uniform vec3 uScCol; uniform vec2 uRough; uniform vec4 uWin; uniform float uStreak;
      float chGold = 0.0;
      float chH(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
      float chN(vec2 p) { vec2 i = floor(p), f = fract(p); f = f * f * (3.0 - 2.0 * f);
        return mix(mix(chH(i), chH(i + vec2(1.0, 0.0)), f.x), mix(chH(i + vec2(0.0, 1.0)), chH(i + vec2(1.0, 1.0)), f.x), f.y); }
      float chF(vec2 p) { return chN(p) * 0.5 + chN(p * 2.07 + 13.1) * 0.3 + chN(p * 4.3 + 7.7) * 0.2; }
      ${MACRO[macro]}`)
      .replace("#include <map_fragment>", `#include <map_fragment>
      float chRough = 1.0; diffuseColor.rgb *= chMacro(vWPos, chRough);
      diffuseColor.rgb = mix(diffuseColor.rgb, vec3(0.83, 0.62, 0.28), chGold);`)
      .replace("#include <roughnessmap_fragment>", `#include <roughnessmap_fragment>
      roughnessFactor = clamp(mix(uRough.y, uRough.x, smoothstep(0.015, 0.25, dot(diffuseColor.rgb, vec3(0.2126, 0.7152, 0.0722)))) * chRough, 0.05, 1.0);`)
      .replace("#include <metalnessmap_fragment>", "#include <metalnessmap_fragment>\n      metalnessFactor = max(metalnessFactor, chGold * 0.75);")
      .replace("#include <lights_fragment_end>", `#include <lights_fragment_end>
      { vec3 nW = inverseTransformDirection(geometryNormal, viewMatrix), acc = vec3(0.0);
        for (int i = 0; i < ${N}; i++) { vec3 L = uSc[i].xyz - vWPos; float d = max(length(L), 0.05);
          float fall = pow(clamp(1.0 - pow(d / 3.8, 4.0), 0.0, 1.0), 2.0) / (d * d);   // inverse square, gone by 3.8 m
          acc += uSc[i].w * fall * max(dot(nW, L / d), 0.0); }
        reflectedLight.directDiffuse += acc * uScCol * BRDF_Lambert(material.diffuseColor);
        ${macro === "cloth" ? "reflectedLight.directDiffuse += uScCol * pow(1.0 - max(dot(geometryNormal, geometryViewDir), 0.0), 3.0) * 0.07;   // candle rim on the folds" : ""}
        ${streaks ? `{ // the glossy floor: each light point leaves a long streak towards the eye (narrow across, long along the view)
          vec3 nG = normalize(mix(inverseTransformDirection(nonPerturbedNormal, viewMatrix), nW, 0.15));   // the boards' plane, a hint of their relief
          vec3 V = normalize(cameraPosition - vWPos), Rv = reflect(-V, nG), S = normalize(cross(vec3(0.0, 1.0, 0.0), V)), U = normalize(cross(S, Rv));
          vec3 sp = vec3(0.0);
          for (int i = 0; i < ${N}; i++) { vec3 L = uSc[i].xyz - vWPos; float d = length(L); vec3 D = L / d - Rv; float a = dot(D, S), b = dot(D, U);
            sp += uScCol * (uSc[i].w * exp(-a * a / 0.0016 - b * b / 0.09) / (1.0 + d * d * 0.06)); }
          { vec3 L = uWin.xyz - vWPos; float d = length(L); vec3 D = L / d - Rv; float a = dot(D, S), b = dot(D, U);
            sp += vec3(0.55, 0.62, 0.9) * (uWin.w * exp(-a * a / 0.006 - b * b / 0.12) / (1.0 + d * d * 0.05)); }
          reflectedLight.directSpecular += sp * uStreak * 1.6 * (1.0 - roughnessFactor * 0.7); }` : ""}
      }`);
  };
  m.customProgramCacheKey = () => `ch-${macro}-${vary}-${streaks}`;   // few programs: each one costs compile time at boot
  return m;
}

/* camera-facing quads for many small lights in one draw: flames (noise flicker, a teardrop) or glows (a soft disc).
   Per instance: position and size in instanceMatrix, a seed in aSeed. Cylindrical billboards round the vertical. */
function billboardMaterial(THREE, clock, cam, kind) {
  const frag = kind === "flame"
    ? `void main() { vec2 p = vUv - vec2(0.5, 0.28); float h = clamp(vUv.y, 0.0, 1.0);
        float t = uTime * 9.0 + vSeed * 31.0, flick = 0.82 + 0.18 * mix(n1(floor(t)), n1(floor(t) + 1.0), smoothstep(0.0, 1.0, fract(t)));
        float w = mix(0.22, 0.02, pow(h, 0.8)) * flick, sx = p.x / max(w, 0.001);
        float body = (1.0 - smoothstep(0.55, 1.0, abs(sx))) * smoothstep(-0.03, 0.06, vUv.y) * (1.0 - smoothstep(0.55, 0.98, h));
        float core = (1.0 - smoothstep(0.0, 0.5, abs(sx))) * (1.0 - smoothstep(0.08, 0.5, h)) * smoothstep(0.0, 0.1, vUv.y);
        vec3 col = mix(mix(vec3(1.0, 0.45, 0.12), vec3(1.0, 0.82, 0.45), smoothstep(0.0, 0.6, body)), vec3(1.0, 0.98, 0.9), core);
        float a = clamp(body * 0.85 + core, 0.0, 1.0) * (0.85 + 0.15 * flick); if (a < 0.01) discard; gl_FragColor = vec4(col * a, a); }`
    : `void main() { float d = length(vUv - 0.5) * 2.0; float t = uTime * 6.0 + vSeed * 17.0;
        float flick = 0.8 + 0.2 * mix(n1(floor(t)), n1(floor(t) + 1.0), smoothstep(0.0, 1.0, fract(t)));
        float a = (exp(-d * d * 7.0) * 0.8 + exp(-d * d * 40.0) * 0.6) * (1.0 - smoothstep(0.85, 1.0, d)) * flick * uGain;
        gl_FragColor = vec4(vec3(1.0, 0.72, 0.4) * a, a); }`;
  return new THREE.ShaderMaterial({
    uniforms: { uTime: clock, uCam: cam, uGain: { value: 1 } }, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
    vertexShader: `attribute float aSeed; uniform float uTime; uniform vec3 uCam; varying vec2 vUv; varying float vSeed;
      void main() { vUv = uv; vSeed = aSeed;
        vec3 c = (modelMatrix * instanceMatrix * vec4(0.0, 0.0, 0.0, 1.0)).xyz, to = uCam - c;
        float s = length(instanceMatrix[1].xyz); vec3 right = normalize(vec3(to.z, 0.0, -to.x) + 1e-5);
        vec3 p = position; ${kind === "flame" ? "p.x += sin(uTime * 7.0 + aSeed * 9.0 + uv.y * 3.0) * 0.08 * uv.y;" : ""}
        gl_Position = projectionMatrix * viewMatrix * vec4(c + right * p.x * s + vec3(0.0, p.y * s, 0.0), 1.0); }`,
    fragmentShader: `uniform float uTime, uGain; varying vec2 vUv; varying float vSeed;
      float n1(float x) { return fract(sin(x * 12.9898 + vSeed * 78.233) * 43758.5453); }
      ${frag}`,
  });
}

/* soft additive light on the walls (the candelabras' pools, the moon's patch): a quad, its gradient centred at
   aD.xy (in the quad's uv), aD.z a seed for the flicker, aD.w the strength; aCol the colour */
function decalMaterial(THREE, clock) {
  return new THREE.ShaderMaterial({
    uniforms: { uTime: clock, uGain: { value: 1 } }, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
    polygonOffset: true, polygonOffsetFactor: -2, polygonOffsetUnits: -2,
    vertexShader: `attribute vec4 aD; attribute vec3 aCol; varying vec2 vUv; varying vec4 vD; varying vec3 vCol;
      void main() { vUv = uv; vD = aD; vCol = aCol; gl_Position = projectionMatrix * modelViewMatrix * instanceMatrix * vec4(position, 1.0); }`,
    fragmentShader: `uniform float uTime, uGain; varying vec2 vUv; varying vec4 vD; varying vec3 vCol;
      void main() { vec2 q = (vUv - vD.xy) * vec2(1.0, 0.8); float d = dot(q, q) * 4.0;
        float flick = 0.88 + 0.07 * sin(uTime * 7.3 + vD.z * 9.0) + 0.05 * sin(uTime * 12.1 + vD.z * 3.0);
        float a = (exp(-d * 2.2) - exp(-2.2)) * flick * vD.w * uGain; if (a <= 0.0) discard;
        gl_FragColor = vec4(vCol * a, a); }`,
  });
}

/* a small warm room environment for the metals (reflections of candle pools and the window), made once */
function roomEnv(THREE, renderer) {
  const c = document.createElement("canvas"); c.width = 256; c.height = 128; const x = c.getContext("2d");
  const g = x.createLinearGradient(0, 0, 0, 128);
  g.addColorStop(0, "#1a1226"); g.addColorStop(.42, "#3a2414"); g.addColorStop(.52, "#5a3618"); g.addColorStop(.62, "#2c1a0e"); g.addColorStop(1, "#140c08");
  x.fillStyle = g; x.fillRect(0, 0, 256, 128);
  const spot = (cx, cy, r, col) => { const s = x.createRadialGradient(cx, cy, 0, cx, cy, r); s.addColorStop(0, col); s.addColorStop(1, "rgba(0,0,0,0)"); x.fillStyle = s; x.fillRect(cx - r, cy - r, r * 2, r * 2); };
  for (let i = 0; i < 10; i++) { spot((i + .5) * 25.6, 52, 11, "rgba(255,196,120,1)"); spot((i + .5) * 25.6, 62, 8, "rgba(255,180,100,.8)"); }
  spot(64, 50, 22, "rgba(170,190,255,.55)");
  spot(128, 16, 46, "rgba(80,60,140,.45)");
  const t = new THREE.CanvasTexture(c); t.mapping = THREE.EquirectangularReflectionMapping; t.colorSpace = THREE.SRGBColorSpace;
  const pm = new THREE.PMREMGenerator(renderer), rt = pm.fromEquirectangular(t); pm.dispose(); t.dispose();
  return rt;
}

/* a carved-relief normal map for the window frame (lozenge lattice cut into the oak), drawn once */
function carvedNormal(THREE) {
  const S = 128, c = document.createElement("canvas"); c.width = c.height = S; const x = c.getContext("2d"), img = x.createImageData(S, S);
  const h = (i, j) => { const u = ((i % S) + S) % S / S * 8, v = ((j % S) + S) % S / S * 8;
    const a = Math.abs(((u + v) % 1) - .5), b = Math.abs(((u - v + 8) % 1) - .5); return Math.min(1, Math.min(a, b) * 9); };   // grooves along both diagonals
  for (let j = 0; j < S; j++) for (let i = 0; i < S; i++) {
    const dx = (h(i + 1, j) - h(i - 1, j)) * 1.2, dy = (h(i, j + 1) - h(i, j - 1)) * 1.2, l = Math.hypot(dx, dy, 1), k = (j * S + i) * 4;
    img.data[k] = (-dx / l * .5 + .5) * 255; img.data[k + 1] = (dy / l * .5 + .5) * 255; img.data[k + 2] = (1 / l * .5 + .5) * 255; img.data[k + 3] = 255; }
  x.putImageData(img, 0, 0);
  const t = new THREE.CanvasTexture(c); t.wrapS = t.wrapT = THREE.RepeatWrapping; return t;
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

/* a quatrefoil outline (the union of four circles) round (cx, cy) */
function quatrefoil(THREE, cx, cy, d, rc, n = 96) {
  const pts = [], lobes = [[d, 0], [0, d], [-d, 0], [0, -d]];
  for (let i = 0; i < n; i++) { const a = i / n * TAU, ux = Math.cos(a), uy = Math.sin(a); let r = 0;
    for (const [lx, ly] of lobes) { const p = ux * lx + uy * ly, q = rc * rc - (lx * lx + ly * ly - p * p); if (q >= 0) r = Math.max(r, p + Math.sqrt(q)); }
    pts.push(new THREE.Vector2(cx + ux * r, cy + uy * r)); }
  return pts;
}

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

/* a wall candelabra in its own frame (x across, y up, z out from the wall): a back plate, a bracket, curved arms and
   drip pans; returns the merged gold geometry and the candle tops (cup positions) */
function candelabra(THREE, n, y0) {
  const geos = [], cups = [], spread = n === 5 ? .11 : .13;
  geos.push(new THREE.CylinderGeometry(.06, .07, .016, 20).rotateX(Math.PI / 2).scale(1, 1.6, 1).translate(0, y0 - .02, .008));   // back plate
  geos.push(new THREE.CylinderGeometry(.012, .016, .2, 10).rotateX(Math.PI / 2).translate(0, y0, .1));                         // bracket
  geos.push(new THREE.SphereGeometry(.026, 14, 10).translate(0, y0, .2));                                                        // hub
  for (let i = 0; i < n; i++) { const o = i - (n - 1) / 2, x = o * spread, z = .2 + (1 - Math.abs(o) / ((n - 1) / 2 || 1)) * .04, y = y0 + .05 + (n - Math.abs(o) * 2) * .012;
    const a = new THREE.Vector3(0, y0, .2), b = new THREE.Vector3(x, y - .03, z);
    if (Math.abs(o) > 0) { const mid = a.clone().lerp(b, .5).add(new THREE.Vector3(0, -.04, 0));
      geos.push(new THREE.TubeGeometry(new THREE.QuadraticBezierCurve3(a, mid, b), 10, .008, 6)); }
    geos.push(new THREE.CylinderGeometry(.007, .009, .035, 8).translate(x, y - .015, z));                                         // socket
    geos.push(new THREE.LatheGeometry([[0, 0], [.018, 0], [.034, .008], [.036, .012]].map(([r, h]) => new THREE.Vector2(r, h)), 16).translate(x, y, z));   // drip pan
    cups.push(new THREE.Vector3(x, y + .004, z)); }
  return { geo: merge(THREE, geos), cups };
}

export function buildShell(THREE, { scene, X, F, SC, renderer, STEP, WALL, moonSlot }) {
  const T = X.T, env = roomEnv(THREE, renderer), cam = { value: new THREE.Vector3() };
  for (const t of [T.stone, T.floor, T.velvet]) { t.wrapS = t.wrapT = THREE.RepeatWrapping; t.repeat.set(1, 1); }
  const flatN = T.flatN, carved = carvedNormal(THREE); X.track(carved);
  const mats = {
    stone: surface(THREE, SC, { map: T.stone, normalMap: flatN, color: 0xd2c8c8, macro: "wall", rough: [.72, .96] }),
    reveal: surface(THREE, SC, { map: T.stone, normalMap: flatN, normalScale: new THREE.Vector2(.35, .35), color: 0xb4aaac, macro: "wall", rough: [.72, .96] }),
    pillar: surface(THREE, SC, { map: T.stone, normalMap: flatN, color: 0xb4aaae, macro: "wall", rough: [.72, .96] }),
    floor: surface(THREE, SC, { map: T.floor, normalMap: flatN, normalScale: new THREE.Vector2(.45, .45), macro: "floor", rough: [.3, .6], streaks: true }),
    wains: surface(THREE, SC, { map: T.floor, normalMap: flatN, color: 0xb8a698, macro: "wall", rough: [.5, .82] }),
    frame: surface(THREE, SC, { map: T.floor, normalMap: carved, normalScale: new THREE.Vector2(.9, .9), color: 0x7a6656, macro: "none", rough: [.4, .7] }),
    rug: surface(THREE, SC, { map: T.rug, bumpMap: T.rug, bumpScale: 2, color: 0xffffff, macro: "none", rough: [.86, .98] }),
    velvet: surface(THREE, SC, { map: T.velvet, bumpMap: T.velvet, bumpScale: 1.5, macro: "none", rough: [.62, .95] }),
    drape: surface(THREE, SC, { map: T.velvet, bumpMap: T.velvet, bumpScale: 1.5, color: 0xd8d0ff, macro: "cloth", rough: [.55, .95], vary: true }),
    wax: surface(THREE, SC, { color: 0xeadcc0, emissive: 0x2a1406, macro: "none", rough: [.45, .6] }),
    gold: new THREE.MeshStandardMaterial({ color: 0xd4a84f, metalness: .8, roughness: .35, envMap: env.texture, envMapIntensity: 1.3 }),
    // the dome's gold: no candle reaches up there, so it carries a faint warm light of its own (the candles from below)
    domeGold: new THREE.MeshStandardMaterial({ color: 0xf0c868, metalness: .8, roughness: .3, envMap: env.texture, envMapIntensity: 2.4, emissive: 0x8a5a1c }),
    iron: new THREE.MeshStandardMaterial({ color: 0x2a2420, metalness: .7, roughness: .5, envMap: env.texture, envMapIntensity: .6 }),
  };
  mats.rug.color.setScalar(1.35);   // the rug must read on a phone: its gold pattern a little brighter than the photo
  /* which materials show which photographic set (upgrade swaps a set's texture into all of them at once); the frame
     keeps its carved relief, not the planks' normal map */
  const sets = { stone: [mats.stone, mats.reveal, mats.pillar], floor: [mats.floor, mats.wains, mats.frame], rug: [mats.rug], velvet: [mats.velvet, mats.drape] };
  mats.frame.userData.keepNormal = true;
  const casters = [], receivers = [];
  const add = (m, { cast = false, receive = true } = {}) => { scene.add(m); if (cast) casters.push(m); if (receive) receivers.push(m); return m; };
  const faceM = (a, y = 0) => new THREE.Matrix4().compose(new THREE.Vector3(Math.sin(a) * WALL, y, -Math.cos(a) * WALL),
    new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0, 1, 0), -a), new THREE.Vector3(1, 1, 1));
  const instAttr = (g, name, data, size) => { g.setAttribute(name, new THREE.InstancedBufferAttribute(new Float32Array(data), size)); };

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
  // floor: uv in oak tiles from the world position; the rug, larger than before so it reads from the room's middle
  { const g = new THREE.CircleGeometry(6.2, 10, Math.PI / 10); g.rotateX(-Math.PI / 2);
    const p = g.attributes.position, uv = g.attributes.uv; for (let i = 0; i < p.count; i++) uv.setXY(i, p.getX(i) / TILE.oak, p.getZ(i) / TILE.oak);
    add(new THREE.Mesh(g, mats.floor)); }
  { const rug = new THREE.Mesh(new THREE.CircleGeometry(2.6, 80), mats.rug); rug.rotation.x = -Math.PI / 2; rug.position.y = .006; add(rug); }

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

  /* ── candelabras on the pillars, as in the reference: five candles at head height, three lower down. Instanced:
     the gold (2 draws), the candles (1), the flames (1), the glows (1) ── */
  const pillarFrame = (k) => { const a = (k + .5) * STEP; return new THREE.Matrix4().compose(new THREE.Vector3(Math.sin(a) * 5.64, 0, -Math.cos(a) * 5.64),
    new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0, 1, 0), -a), new THREE.Vector3(1, 1, 1)); };
  const upper = candelabra(THREE, 5, 1.95), lower = candelabra(THREE, 3, 1.15);
  for (const c of [upper, lower]) { const im = new THREE.InstancedMesh(c.geo, mats.gold, 10); for (let k = 0; k < 10; k++) im.setMatrixAt(k, pillarFrame(k)); add(im, { receive: false }); }
  const candles = [];   // [world position of the candle foot, height, pillar]
  for (let k = 0; k < 10; k++) for (const [c, hs] of [[upper, [.15, .19, .23, .19, .15]], [lower, [.13, .17, .13]]])
    c.cups.forEach((cup, i) => candles.push([cup.clone().applyMatrix4(pillarFrame(k)), hs[i], k]));
  { const waxG = waxGeometry(THREE, 1, .016, 4), im = new THREE.InstancedMesh(waxG, mats.wax, candles.length);
    candles.forEach(([p, h], i) => im.setMatrixAt(i, new THREE.Matrix4().compose(p, new THREE.Quaternion(), new THREE.Vector3(1, h, 1)))); add(im, { receive: false }); }
  const quad = (w, h, y0) => new THREE.PlaneGeometry(w, h).translate(0, y0, 0);
  { const g = quad(.1, .26, .11), im = new THREE.InstancedMesh(g, billboardMaterial(THREE, F.clock, cam, "flame"), candles.length);
    candles.forEach(([p, h], i) => im.setMatrixAt(i, new THREE.Matrix4().compose(p.clone().setY(p.y + h + .002), new THREE.Quaternion(), new THREE.Vector3(.42, .42, .42))));
    instAttr(g, "aSeed", candles.map((_, i) => (i * .618) % 1), 1); im.frustumCulled = false; im.renderOrder = 5; scene.add(im); }
  { const g = quad(1, 1, 0), clusters = [];
    for (let k = 0; k < 10; k++) for (const [c, y, s] of [[upper, 2.2, .95], [lower, 1.35, .7]]) clusters.push([new THREE.Vector3(0, y, .23).applyMatrix4(pillarFrame(k)), s]);
    const im = new THREE.InstancedMesh(g, billboardMaterial(THREE, F.clock, cam, "glow"), clusters.length);
    clusters.forEach(([p, s], i) => im.setMatrixAt(i, new THREE.Matrix4().compose(p, new THREE.Quaternion(), new THREE.Vector3(s, s, s))));
    instAttr(g, "aSeed", clusters.map((_, i) => (i * .37) % 1), 1); im.frustumCulled = false; im.renderOrder = 4; scene.add(im); }
  // the light points for the pools and streaks: between the two clusters of each pillar
  for (let k = 0; k < 10; k++) { const p = new THREE.Vector3(0, 1.75, .3).applyMatrix4(pillarFrame(k)); SC.uSc.value[k].set(p.x, p.y, p.z, 0); }

  /* ── pools of light painted on the walls and pillars round each candelabra, and the moon's patch: soft additive
     decals (one draw), slightly flickering ── */
  { const items = [];   // [matrix, centre u, centre v, seed, strength, colour]
    const warm = [1.0, .66, .34];
    for (let k = 0; k < 10; k++) { const ka = k * STEP;
      // the two faces meeting at pillar k: face k (corner on its right) and face k+1 (corner on its left)
      items.push([faceM(ka).multiply(new THREE.Matrix4().makeTranslation(FW / 2 - .9, 1.65, .012)).multiply(new THREE.Matrix4().makeScale(1.8, 3.0, 1)), 1, .5, k, .5, warm]);
      items.push([faceM(ka + STEP).multiply(new THREE.Matrix4().makeTranslation(-FW / 2 + .9, 1.65, .012)).multiply(new THREE.Matrix4().makeScale(1.8, 3.0, 1)), 0, .5, k, .5, warm]);
      items.push([pillarFrame(k).multiply(new THREE.Matrix4().makeTranslation(0, 1.7, .02)).multiply(new THREE.Matrix4().makeScale(.55, 2.6, 1)), .5, .52, k, .45, warm]); }
    // the moon: a cool glow on the wall round the window
    items.push([faceM(moonSlot * STEP).multiply(new THREE.Matrix4().makeTranslation(0, W.sill + 1.3, .015)).multiply(new THREE.Matrix4().makeScale(3.2, 3.4, 1)), .5, .5, 3, .22, [.55, .62, .95]]);
    const g = new THREE.PlaneGeometry(1, 1), im = new THREE.InstancedMesh(g, decalMaterial(THREE, F.clock), items.length);
    items.forEach(([m], i) => im.setMatrixAt(i, m));
    instAttr(g, "aD", items.flatMap(([, u, v, s, w]) => [u, v, s, w]), 4); instAttr(g, "aCol", items.flatMap((x) => x[5]), 3);
    im.frustumCulled = false; im.renderOrder = 2; scene.add(im); }
  // the window's moonlight on the floor: its lights and bars, stretched out into the room, soft-edged
  { const ma = moonSlot * STEP, len = 2.8, g = new THREE.PlaneGeometry(1.7, len).rotateX(-Math.PI / 2);
    const mat = new THREE.ShaderMaterial({ uniforms: { uS: { value: .3 } }, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
      vertexShader: "varying vec2 vUv; void main() { vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }",
      fragmentShader: `uniform float uS; varying vec2 vUv;
        void main() { float u = abs(vUv.x - 0.5) * 2.0, v = vUv.y;   // v = 1 at the wall, 0 far into the room
          float w = mix(0.95, 0.35, 1.0 - smoothstep(0.0, 0.1, v)), lights = (1.0 - smoothstep(w - 0.12, w, u)) * smoothstep(0.02, 0.09, u);   // the lights, the mullion between
          float transom = 1.0 - (1.0 - smoothstep(0.015, 0.05, abs(v - 0.55))) * 0.85;
          float a = lights * transom * (1.0 - smoothstep(0.82, 1.0, v)) * smoothstep(0.0, 0.25, v) * uS;
          gl_FragColor = vec4(vec3(0.55, 0.62, 0.92) * a, a); }` });
    const m = new THREE.Mesh(g, mat); m.position.set(Math.sin(ma) * (WALL - .3 - len / 2), .012, -Math.cos(ma) * (WALL - .3 - len / 2)); m.rotation.y = -ma; m.renderOrder = 2; scene.add(m); }

  /* ── velvet drapes (instanced): beside every corner and both sides of the window; each with its own texture
     offset and rotation (aVar), so the tile never lines up; gold borders from the shader ── */
  const drapeAt = [];
  for (let k = 0; k < 10; k++) { if (k === moonSlot) continue; for (const s of [-1, 1]) drapeAt.push([k, s * (FW / 2 - .5), .62]); }
  drapeAt.push([moonSlot, -1.2, .72], [moonSlot, 1.2, .72]);
  { const g = drapeGeometry(THREE, 1, 3.86), aVar = [], rnd = X.rng(17);
    const im = new THREE.InstancedMesh(g, mats.drape, drapeAt.length);
    drapeAt.forEach(([k, x, w], i) => { im.setMatrixAt(i, faceM(k * STEP).multiply(new THREE.Matrix4().makeTranslation(x, 0, 0)).multiply(new THREE.Matrix4().makeScale(w, 1, 1)));
      aVar.push(rnd() * 7, rnd() * 7, (rnd() - .5) * 1.2); });
    instAttr(g, "aVar", aVar, 3);
    add(im, { cast: true, receive: false }); }   // receiving the soft shadow over this much cloth cost High 7 fps; against the wall it barely shows

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
  // a stone arch molding round the opening on the wall (a beveled band following the pointed arch)
  { const o = pointed(THREE, W.hw + .17, W.hs, W.R + .17); o[0].y = -.1; o[o.length - 1].y = -.1;
    const sh = new THREE.Shape(o); sh.holes.push(new THREE.Path(outline));
    const g = new THREE.ExtrudeGeometry(sh, { depth: .05, bevelEnabled: true, bevelThickness: .025, bevelSize: .025, bevelSegments: 2, curveSegments: 24 });
    scaleUV(g, 1 / TILE.stone, 1 / TILE.stone); win.add(new THREE.Mesh(g, mats.reveal)); }
  // the frame: one carved piece of dark oak, the opening minus two lights (each split by a transom) and a quatrefoil
  const yT = 1.0, ys = 1.45, hwl = (W.hw - W.t - W.m / 2) / 2, xl = W.m / 2 + hwl, Rl = hwl * 1.5, qc = 2.12;
  { const sh = new THREE.Shape(outline);
    for (const side of [-1, 1]) { const cx = side * xl;
      sh.holes.push(new THREE.Path([[cx - hwl, W.t], [cx + hwl, W.t], [cx + hwl, yT - .025], [cx - hwl, yT - .025]].map(([x, y]) => new THREE.Vector2(x, y))));
      sh.holes.push(new THREE.Path(pointed(THREE, hwl, ys - yT - .025, Rl, 12).map((p) => new THREE.Vector2(p.x + cx, p.y + yT + .025)))); }
    sh.holes.push(new THREE.Path(quatrefoil(THREE, 0, qc, .088, .092)));
    const g = new THREE.ExtrudeGeometry(sh, { depth: .07, bevelEnabled: true, bevelThickness: .014, bevelSize: .012, bevelSegments: 2, curveSegments: 28 });
    g.translate(0, 0, -W.D + .04); scaleUV(g, 1 / TILE.oak, 1 / TILE.oak);
    const m = new THREE.Mesh(g, mats.frame); win.add(m); casters.push(m); }
  // gold fittings: fleur crosses where the bars meet (a boss, four tapered arms with knobs), a ring round the quatrefoil
  { const geos = [new THREE.SphereGeometry(.026, 14, 10)];
    for (let i = 0; i < 4; i++) { const a = i * Math.PI / 2, d = new THREE.Vector3(Math.cos(a), Math.sin(a), 0);
      geos.push(new THREE.ConeGeometry(.016, .07, 8).rotateZ(a - Math.PI / 2).translate(d.x * .05, d.y * .05, 0));
      geos.push(new THREE.SphereGeometry(.012, 10, 8).translate(d.x * .088, d.y * .088, 0)); }
    const at = [[0, yT, 1.2], [0, .5, .9], [0, 1.68, .9], [-W.hw + W.t / 2, yT, .8], [W.hw - W.t / 2, yT, .8], [0, qc - .2, .8]];
    const im = new THREE.InstancedMesh(merge(THREE, geos), mats.gold, at.length);
    at.forEach(([x, y, s], i) => im.setMatrixAt(i, new THREE.Matrix4().compose(new THREE.Vector3(x, y, -W.D + .13), new THREE.Quaternion(), new THREE.Vector3(s, s, s * .6))));
    win.add(im);
    const ring = new THREE.Mesh(new THREE.TorusGeometry(.2, .012, 8, 56), mats.gold); ring.position.set(0, qc, -W.D + .135); win.add(ring); }
  // the glass, just behind the frame: the landscape and the moon (room.js gives it the window shader)
  const paneShape = new THREE.Shape(pointed(THREE, W.hw - W.t / 2, W.hs, W.R - W.t / 2));
  const paneGeo = new THREE.ShapeGeometry(paneShape, 24); { const p = paneGeo.attributes.position, uv = paneGeo.attributes.uv, hw = W.hw - W.t / 2, H = archHeight(hw, W.hs, W.R - W.t / 2);
    for (let i = 0; i < p.count; i++) uv.setXY(i, (p.getX(i) + hw) / (2 * hw), p.getY(i) / H); paneGeo.userData.size = [2 * hw, H]; }
  paneGeo.translate(0, 0, -W.D + .03);
  // a thick stone sill, out into the room, on two stepped corbels
  { const g = scaleUV(new THREE.BoxGeometry(W.hw * 2 + .5, .12, W.D + .3), 2 / TILE.stone, .6 / TILE.stone);
    const m = new THREE.Mesh(g, mats.stone); m.position.set(0, -.06, -W.D / 2 + .15); win.add(m); casters.push(m); receivers.push(m);
    const prof = new THREE.Shape([[0, 0], [.26, 0], [.26, -.05], [.18, -.08], [.15, -.17], [.06, -.22], [0, -.3]].map(([u, v]) => new THREE.Vector2(u, v)));
    const cg = new THREE.ExtrudeGeometry(prof, { depth: .14, bevelEnabled: true, bevelThickness: .01, bevelSize: .01, bevelSegments: 1 }).rotateY(-Math.PI / 2).translate(.07, -.12, 0);
    scaleUV(cg, 1 / TILE.stone, 1 / TILE.stone);
    for (const x of [-W.hw - .1, W.hw + .1]) { const c = new THREE.Mesh(cg, mats.reveal); c.position.x = x; win.add(c); } }
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
  win.updateMatrixWorld(true);
  { const p = new THREE.Vector3(0, .32, .2).applyMatrix4(win.matrixWorld); SC.uSc.value[10].set(p.x, p.y, p.z, 0); }   // the sill candles light the reveal
  { const p = new THREE.Vector3(0, 1.3, -W.D).applyMatrix4(win.matrixWorld); SC.uWin.value.set(p.x, p.y, p.z, 1.1); }    // the window's streak on the floor

  /* ── the dome's gold architecture: ten ribs from the rim to a central boss (over the pillars), rings, medallions
     where they cross. The real planets and the ecliptic ring stay in front (room.js). ── */
  const RD = 5.9, Y0 = 4.2;
  { const pts = []; for (let i = 0; i <= 24; i++) { const e = (.03 + i / 24 * 1.49); pts.push(new THREE.Vector3(0, Y0 + RD * Math.sin(e), -RD * Math.cos(e))); }
    const g = new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pts), 48, .055, 6), im = new THREE.InstancedMesh(g, mats.domeGold, 10);
    for (let k = 0; k < 10; k++) im.setMatrixAt(k, new THREE.Matrix4().makeRotationY(-(k + .5) * STEP)); add(im, { receive: false }); }
  for (const e of [.07, .3, 1.05]) { const r = RD * Math.cos(e), t = new THREE.Mesh(new THREE.TorusGeometry(r, e < .1 ? .07 : .05, 8, 120), mats.domeGold);
    t.rotation.x = Math.PI / 2; t.position.y = Y0 + RD * Math.sin(e); add(t, { receive: false }); }
  { const boss = new THREE.Mesh(new THREE.LatheGeometry([[0, -.16], [.1, -.15], [.18, -.11], [.25, -.07], [.3, -.03], [.33, 0]].map(([r, y]) => new THREE.Vector2(r, y)), 40), mats.domeGold);
    boss.position.y = Y0 + RD * Math.sin(1.515) + .01; add(boss, { receive: false });
    const med = new THREE.LatheGeometry([[0, .045], [.05, .04], [.07, .02], [.1, .028], [.13, .012], [.15, 0]].map(([r, y]) => new THREE.Vector2(r, y)).reverse(), 28).rotateX(Math.PI / 2);
    const spots = []; for (let k = 0; k < 10; k++) for (const e of [.3, 1.05]) spots.push([(k + .5) * STEP, e]);
    const im = new THREE.InstancedMesh(med, mats.domeGold, spots.length), o = new THREE.Object3D();
    spots.forEach(([a, e], i) => { o.position.set(Math.sin(a) * (RD - .06) * Math.cos(e), Y0 + (RD - .06) * Math.sin(e), -Math.cos(a) * (RD - .06) * Math.cos(e)); o.lookAt(0, Y0, 0); o.updateMatrix(); im.setMatrixAt(i, o.matrix); });
    add(im, { receive: false }); }

  /* every frame: the light points flicker (their pools and streaks follow), the sill candles flare during the ritual */
  const flick = (t, s) => .84 + Math.sin(t * 7.1 + s) * .05 + Math.sin(t * 13.3 + s * 3) * .04 + Math.sin(t * 2.3 + s * 5) * .07;
  function update(t, dt, camera) {
    cam.value.copy(camera.position);
    for (let k = 0; k < 10; k++) SC.uSc.value[k].w = 4.2 * flick(t, k * 1.7);
    let flare = 0;
    for (const c of ritual) { const u = c.userData; u.f += (u.flare - u.f) * Math.min(1, dt * 2); const s = 1 + u.f * .55; flare += u.f;
      u.flame.scale.setScalar(s); u.glow.scale.setScalar(.7 * s); u.glow.material.opacity = .55 + u.f * .3; }
    SC.uSc.value[10].w = (1.6 + flare * .5) * flick(t, 11);
  }
  function setLevel(level) {   // High: the floor also mirrors the room's environment; Medium keeps only the streaks
    const want = level === "high" ? env.texture : null;
    if (mats.floor.envMap !== want) { mats.floor.envMap = want; mats.floor.envMapIntensity = .5; mats.floor.needsUpdate = true; }
  }
  return { mats, sets, casters, receivers, win, W, paneGeo, ritual, env, update, setLevel };
}
