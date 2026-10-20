/* Oracle chamber (FULL tier): living details. A candle flame shader, dust motes drifting in the moonbeam,
   faint incense smoke, additive glow sprites (the cheap "bloom") and the light beam. One shared clock uniform. */

export function makeFx(THREE, X) {
  const clock = { value: 0 };
  const flames = [], _v = new THREE.Vector3();

  /* teardrop flame on a camera-facing plane: white core -> gold -> orange, wobbling with the time */
  const flameMat = new THREE.ShaderMaterial({
    uniforms: { uTime: clock, uBoost: { value: 1 } },
    vertexShader: `varying vec2 vUv; uniform float uTime; attribute float aSeed; varying float vSeed;
      void main() { vUv = uv; vSeed = aSeed; vec3 p = position;
        p.x += sin(uTime * 7.0 + aSeed * 9.0 + uv.y * 3.0) * 0.012 * uv.y;
        gl_Position = projectionMatrix * modelViewMatrix * vec4(p, 1.0); }`,
    fragmentShader: `varying vec2 vUv; varying float vSeed; uniform float uTime; uniform float uBoost;
      void main() { vec2 p = vUv - vec2(0.5, 0.28); float h = clamp(vUv.y, 0.0, 1.0);
        float flick = 0.9 + 0.1 * sin(uTime * 13.0 + vSeed * 7.0) * sin(uTime * 7.3 + vSeed);
        float w = mix(0.22, 0.02, pow(h, 0.8)) * flick; float sx = p.x / max(w, 0.001);
        float body = 1.0 - smoothstep(0.55, 1.0, abs(sx)); body *= smoothstep(-0.03, 0.06, vUv.y) * (1.0 - smoothstep(0.55, 0.98, h));
        float core = (1.0 - smoothstep(0.0, 0.5, abs(sx))) * (1.0 - smoothstep(0.08, 0.5, h)) * smoothstep(0.0, 0.1, vUv.y);
        vec3 col = mix(vec3(1.0, 0.45, 0.12), vec3(1.0, 0.82, 0.45), smoothstep(0.0, 0.6, body));
        col = mix(col, vec3(1.0, 0.98, 0.9), core);
        float a = clamp(body * 0.85 + core, 0.0, 1.0) * uBoost; if (a < 0.01) discard;
        gl_FragColor = vec4(col * a, a); }`,
    transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
  });

  function flame(size = .08, seed = Math.random()) {
    const g = new THREE.PlaneGeometry(size, size * 2.6); g.translate(0, size * 1.1, 0);
    g.setAttribute("aSeed", new THREE.Float32BufferAttribute([seed, seed, seed, seed], 1));
    const m = new THREE.Mesh(g, flameMat); m.renderOrder = 5; flames.push(m); return m;
  }
  function glow(tex, color = 0xffd9a0, size = .5, opacity = .8) {
    const s = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, color, transparent: true, opacity, depthWrite: false, blending: THREE.AdditiveBlending, fog: false }));
    s.scale.set(size, size, 1); s.renderOrder = 4; return s;
  }
  /* a candle: wax cylinder, wick, flame and its glow. Returns the group and its flame position */
  function candle(h = .16, r = .025, waxColor = 0xe9dcc0) {
    const grp = new THREE.Group();
    const wax = new THREE.Mesh(new THREE.CylinderGeometry(r, r * 1.04, h, 14), new THREE.MeshLambertMaterial({ color: waxColor, emissive: 0x3a2410 }));
    wax.position.y = h / 2; grp.add(wax);
    const f = flame(r * 2.4); f.position.y = h + .004; grp.add(f);
    const gl = glow(X.T.glow, 0xffc27a, r * 22, .55); gl.position.y = h + r * 2.2; grp.add(gl);
    grp.userData.flameY = h + r * 2.2; grp.userData.glow = gl; grp.userData.flame = f;
    return grp;
  }
  /* dust: points drifting slowly inside a box, brighter in the beam; positions animated in the vertex shader */
  function dust(count, box, color = 0xffe6b0, size = 7) {
    const pos = new Float32Array(count * 3), seed = new Float32Array(count), r = X.rng(11);
    for (let i = 0; i < count; i++) { pos[i * 3] = box.min.x + r() * (box.max.x - box.min.x); pos[i * 3 + 1] = box.min.y + r() * (box.max.y - box.min.y);
      pos[i * 3 + 2] = box.min.z + r() * (box.max.z - box.min.z); seed[i] = r(); }
    const g = new THREE.BufferGeometry(); g.setAttribute("position", new THREE.BufferAttribute(pos, 3)); g.setAttribute("aSeed", new THREE.BufferAttribute(seed, 1));
    const m = new THREE.ShaderMaterial({
      uniforms: { uTime: clock, uColor: { value: new THREE.Color(color) }, uSize: { value: size }, uH: { value: box.max.y - box.min.y }, uY0: { value: box.min.y }, uPx: { value: 1 } },
      vertexShader: `attribute float aSeed; uniform float uTime, uSize, uH, uY0, uPx; varying float vA;
        void main() { vec3 p = position; float t = uTime * (0.02 + aSeed * 0.03);
          p.y = uY0 + mod(p.y - uY0 + t * uH * 0.35, uH); p.x += sin(uTime * 0.21 + aSeed * 40.0) * 0.18; p.z += cos(uTime * 0.17 + aSeed * 31.0) * 0.18;
          vec4 mv = modelViewMatrix * vec4(p, 1.0); gl_Position = projectionMatrix * mv;
          gl_PointSize = uSize * uPx * (0.4 + aSeed) / -mv.z;
          float edge = smoothstep(0.0, 0.15, (p.y - uY0) / uH) * (1.0 - smoothstep(0.85, 1.0, (p.y - uY0) / uH));
          vA = edge * (0.35 + 0.65 * abs(sin(uTime * (0.6 + aSeed) + aSeed * 20.0))); }`,
      fragmentShader: `uniform vec3 uColor; varying float vA;
        void main() { float d = length(gl_PointCoord - 0.5); float a = smoothstep(0.5, 0.0, d) * vA; if (a < 0.01) discard; gl_FragColor = vec4(uColor * a, a); }`,
      transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
    });
    const pts = new THREE.Points(g, m); pts.frustumCulled = false; pts.renderOrder = 6; return pts;
  }
  /* incense smoke: a few soft sprites rising, turning and fading */
  function smoke(origin, n = 5) {
    const grp = new THREE.Group(), items = [];
    for (let i = 0; i < n; i++) { const s = glow(X.T.smoke, 0xcfc6ea, .5, 0); s.material.blending = THREE.NormalBlending; s.material.opacity = 0; grp.add(s); items.push({ s, off: i / n }); }
    grp.position.copy(origin);
    grp.userData.update = (t) => { for (const it of items) { const k = (t * .05 + it.off) % 1; it.s.position.set(Math.sin(k * 6 + it.off * 9) * .08 * k, k * 1.3, Math.cos(k * 5) * .05 * k);
      const sc = .25 + k * .9; it.s.scale.set(sc, sc, 1); it.s.material.rotation = k * 2 + it.off * 6; it.s.material.opacity = Math.sin(k * Math.PI) * .13; } };
    return grp;
  }
  /* a soft beam of moonlight: an open cone with a vertical fade, additive */
  function beam(from, to, radius, color = 0xa9b8ff, strength = .12) {
    const len = from.distanceTo(to), g = new THREE.CylinderGeometry(radius * .25, radius, len, 24, 1, true); g.translate(0, -len / 2, 0);
    const m = new THREE.ShaderMaterial({ uniforms: { uColor: { value: new THREE.Color(color) }, uS: { value: strength }, uTime: clock },
      vertexShader: `varying float vY; varying vec3 vN; varying vec3 vV; void main() { vY = uv.y; vN = normalize(normalMatrix * normal);
        vec4 mv = modelViewMatrix * vec4(position, 1.0); vV = normalize(-mv.xyz); gl_Position = projectionMatrix * mv; }`,
      fragmentShader: `uniform vec3 uColor; uniform float uS, uTime; varying float vY; varying vec3 vN; varying vec3 vV;
        void main() { float facing = pow(abs(dot(vN, vV)), 1.6); float a = facing * smoothstep(0.0, 0.6, vY) * uS * (0.85 + 0.15 * sin(uTime * 0.3));
          gl_FragColor = vec4(uColor * a, a); }`,
      transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, side: THREE.DoubleSide });
    const mesh = new THREE.Mesh(g, m); mesh.position.copy(from); mesh.lookAt(to); mesh.rotateX(-Math.PI / 2); mesh.renderOrder = 3;
    mesh.userData.mat = m; return mesh;
  }

  /* a burst of gold dust (reward, a turned card): points thrown up, slowed and fading; update(dt) -> still alive */
  function burst(parent, at, { count = 46, color = 0xffd27a, speed = .55, size = 9, life = 1.4 } = {}) {
    const pos = new Float32Array(count * 3), vel = [], r = X.rng((Math.random() * 1e9) | 0);
    for (let i = 0; i < count; i++) { pos.set([at.x, at.y, at.z], i * 3); const a = r() * Math.PI * 2, up = .4 + r() * .8, s = speed * (.4 + r() * .8);
      vel.push([Math.cos(a) * s * .6, up * s, Math.sin(a) * s * .6]); }
    const g = new THREE.BufferGeometry(); g.setAttribute("position", new THREE.BufferAttribute(pos, 3));
    const m = new THREE.PointsMaterial({ color, size: size / 1000, map: X.T.glow, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, sizeAttenuation: true });
    const pts = new THREE.Points(g, m); pts.renderOrder = 7; pts.frustumCulled = false; parent.add(pts);
    let age = 0;
    return { update(dt) { age += dt; const k = Math.max(0, 1 - age / life);
        for (let i = 0; i < count; i++) { const v = vel[i]; v[1] -= dt * .5; v[0] *= .985; v[2] *= .985; pos[i * 3] += v[0] * dt; pos[i * 3 + 1] += v[1] * dt; pos[i * 3 + 2] += v[2] * dt; }
        g.attributes.position.needsUpdate = true; m.opacity = k; if (k <= 0) { this.dispose(); return false; } return true; },
      dispose() { if (pts.parent) pts.parent.remove(pts); g.dispose(); m.dispose(); } };
  }

  return { clock, flameMat, flame, glow, candle, dust, smoke, beam, flames, burst,
    face(camera) { for (const f of flames) { const p = f.parent; if (!p) continue; f.lookAt(camera.position.x, f.getWorldPosition(_v).y, camera.position.z); } } };
}
