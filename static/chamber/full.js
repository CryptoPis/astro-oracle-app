/* Oracle chamber (FULL tier): the WebGL engine. Renderer, camera navigation, picking, glides and the loop.
   Navigation: swipe left/right turns between the ten objects (inertia, then a calm settle, no overshoot); swipe up
   looks at the dome; tilt adds a very small parallax. Rendering stops while a panel covers the room, while the app is
   hidden, and when nothing moves. */

const TAU = Math.PI * 2;
/* the app's one easing curve, cubic-bezier(.2,.7,.1,1), as a function of time 0..1 */
export function ease(x) {
  const ax = .2, ay = .7, bx = .1, by = 1;
  let t = x; for (let i = 0; i < 6; i++) { const cx = 3 * ax * t * (1 - t) ** 2 + 3 * bx * t * t * (1 - t) + t ** 3 - x;
    const d = 3 * ax * (1 - t) ** 2 + 6 * (bx - ax) * t * (1 - t) + 3 * (1 - bx) * t * t; if (Math.abs(d) < 1e-6) break; t -= cx / d; t = Math.min(1, Math.max(0, t)); }
  return 3 * ay * t * (1 - t) ** 2 + 3 * by * t * t * (1 - t) + t ** 3;
}

/* Graphics levels inside FULL. High: pixel ratio up to 1.75, shadows from the moon and the central candle, half-res
   bloom, 1024 px textures. Medium: up to 1.4, the moon's shadow only, glow sprites instead of bloom, 512 px textures.
   The level is chosen from the frame times of frames 10-50 (drawn at High); a room too slow even for that switches to
   LITE (ctx.onSlow). ?gfx=high|medium forces a level. */
export const GFX = { high: { dpr: 1.75, tex: 1024, bloom: true }, medium: { dpr: 1.4, tex: 512, bloom: false } };
const HIGH_MAX_MS = 20, LITE_MS = 45;   // average frame time over frames 10-50 (drawn before the 1024 px set: keep headroom)

/* the colour finish, one line for every built-in material: write display-ready sRGB (also into the bloom's target,
   so High and Medium look alike) and raise the black point to the palette's night (#0b0710) */
function colourFinish(THREE) {
  if (THREE.ShaderChunk.colorspace_fragment.includes("CH_FINISH")) return;
  THREE.ShaderChunk.colorspace_fragment = "/* CH_FINISH */ gl_FragColor = sRGBTransferOETF( gl_FragColor );"
    + " gl_FragColor.rgb = vec3(0.0431, 0.0275, 0.0627) + gl_FragColor.rgb * vec3(0.9569, 0.9725, 0.9373);";
}

export async function createFull(THREE, B, ctx, mods) {
  const { STATIONS, STEP } = ctx;
  let forcedGfx = null; try { forcedGfx = new URLSearchParams(location.search).get("gfx"); } catch {}
  if (!GFX[forcedGfx]) forcedGfx = null;
  let gfx = forcedGfx || "high";
  const host = ctx.host, dprOf = (level) => Math.min(devicePixelRatio || 1, GFX[level].dpr);
  colourFinish(THREE);
  const renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: "high-performance", stencil: false });
  renderer.outputColorSpace = THREE.LinearSRGBColorSpace;   // the encoding happens in the colour finish
  renderer.setPixelRatio(dprOf(gfx)); renderer.setSize(innerWidth, innerHeight);
  renderer.shadowMap.enabled = true; renderer.shadowMap.type = THREE.PCFShadowMap; renderer.shadowMap.autoUpdate = false;
  const cv = renderer.domElement; cv.className = "ch-gl"; cv.setAttribute("aria-hidden", "true"); host.append(cv);

  const X = mods.tex.makeTextures(THREE, B), F = mods.fx.makeFx(THREE, X);
  const room = mods.room.buildRoom(THREE, B, X, F, { STEP, STATIONS });
  const scene = room.scene;
  room.setShadows(gfx); renderer.shadowMap.needsUpdate = true;
  let post = GFX[gfx].bloom && renderer.capabilities.isWebGL2 ? mods.post.makePost(THREE, renderer) : null;
  let texSize = 0, texDone = null, compiling = false;
  const texReady = new Promise((r) => { texDone = r; });
  function loadTextures() {   // once, at the level's size, after the first frames
    if (texSize) return; texSize = GFX[gfx].tex;
    room.upgrade(texSize).then((failed) => { if (failed.length) console.warn("chamber textures", failed); texDone({ size: texSize, failed }); kick(); });
  }
  async function setGfx(level) {
    if (level === gfx || !GFX[level]) return; gfx = level;
    compiling = true;   // hold the last frame while the shaders for the new light set compile
    renderer.setPixelRatio(dprOf(level)); renderer.setSize(innerWidth, innerHeight);
    if (post && !GFX[level].bloom) { post.dispose(); post = null; }
    else if (!post && GFX[level].bloom && renderer.capabilities.isWebGL2) post = mods.post.makePost(THREE, renderer);
    if (post) post.setSize(...renderer.getDrawingBufferSize(new THREE.Vector2()).toArray());
    room.setShadows(level); renderer.shadowMap.needsUpdate = true;
    try { await Promise.race([renderer.compileAsync(scene, camera), new Promise((r) => setTimeout(r, 2500))]); } catch {}
    compiling = false; kick();
  }
  const camera = new THREE.PerspectiveCamera(66, innerWidth / innerHeight, .05, 40);
  const EYE = 1.45;

  /* ── pose: yaw/pitch in the room, or a focus on one object ── */
  const nav = { yaw: 0, yawT: 0, pitch: -.1, pitchT: -.1, tiltY: 0, tiltP: 0, tY: 0, tP: 0, up: false };
  const pose = { pos: new THREE.Vector3(0, EYE, 0), look: new THREE.Vector3(), off: 0 };
  let focus = null;   // { id, from: {pos, look, off}, to: {...}, t0, dur, resolve }
  let focused = null; // station id while focused
  const roomLook = (out) => out.set(Math.sin(nav.yaw + nav.tiltY) * Math.cos(nav.pitch + nav.tiltP), Math.sin(nav.pitch + nav.tiltP), -Math.cos(nav.yaw + nav.tiltY) * Math.cos(nav.pitch + nav.tiltP)).add(pose.pos);
  const index = () => ((Math.round(nav.yaw / STEP) % 10) + 10) % 10;

  function focusPose(id, mode) {
    const st = room.stations.get(id);
    if (id === "horo" || !st) {   // the dome: look up from the middle of the room (also when opened from the compass)
      nav.up = true; nav.pitch = nav.pitchT = 1.02;
      const look = roomLook(new THREE.Vector3()); return { pos: new THREE.Vector3(0, EYE, 0), look, off: mode === "panel" ? .3 : 0 }; }
    const c = st.center, flat = new THREE.Vector3(-c.x, 0, -c.z).normalize();
    const dist = st.dist * (mode === "stage" ? (st.stageDist || 1) : 1);
    const pos = c.clone().addScaledVector(flat, dist); pos.y = Math.max(.95, c.y + dist * (st.stageRise != null && mode === "stage" ? st.stageRise : .42));
    return { pos, look: c.clone(), off: mode === "panel" ? .36 : (st.stageOff || 0) };
  }
  function glide(to, dur = 900) {
    return new Promise((resolve) => { const from = { pos: camera.position.clone(), look: currentLook.clone(), off: pose.off };
      if (focus && focus.resolve) focus.resolve(); focus = { from, to, t0: performance.now(), dur: B.reduced ? 1 : dur, resolve }; kick(); });
  }
  const currentLook = new THREE.Vector3();

  /* ── input ── */
  let ptr = null, stage = null, paused = false;
  const pick = (x, y, list) => { const ray = new THREE.Raycaster(), v = new THREE.Vector2((x / innerWidth) * 2 - 1, -(y / innerHeight) * 2 + 1);
    ray.setFromCamera(v, camera); const hits = ray.intersectObjects(list, false); return hits.length ? hits[0].object.userData.station : null; };
  const ringHits = () => [...room.stations.values()].filter((s) => s.id !== "horo").map((s) => s.hit);
  function down(e) {
    if (stage && stage.down && stage.down(e)) return;
    ptr = { x: e.clientX, y: e.clientY, t: performance.now(), yaw: nav.yaw, axis: null, hist: [[performance.now(), e.clientX]] };
    try { cv.setPointerCapture(e.pointerId); } catch {}
  }
  function move(e) {
    if (stage && stage.move && stage.move(e)) return;
    if (!ptr || focused) return; const dx = e.clientX - ptr.x, dy = e.clientY - ptr.y;
    if (!ptr.axis && Math.hypot(dx, dy) > 8) ptr.axis = Math.abs(dx) > Math.abs(dy) ? "x" : "y";
    if (ptr.axis === "x" && !nav.up) { nav.yaw = nav.yawT = ptr.yaw - dx * (TAU / innerWidth) * .42; ptr.hist.push([performance.now(), e.clientX]); if (ptr.hist.length > 6) ptr.hist.shift(); ctx.onTurning(); kick(); }
    if (ptr.axis === "y" && Math.abs(dy) > 50 && !ptr.done) { ptr.done = true; if (dy < 0 && !nav.up) lookUp(true); else if (dy > 0 && nav.up) lookUp(false); }
  }
  function up(e) {
    if (stage && stage.up && stage.up(e)) return;
    if (!ptr) return; const p = ptr; ptr = null;
    if (!p.axis && performance.now() - p.t < 450) { if (focused) return ctx.onTapFocused && ctx.onTapFocused(e);
      const id = pick(e.clientX, e.clientY, nav.up ? [room.stations.get("horo").hit] : ringHits()); if (id) ctx.onPick(id); return; }
    if (p.axis === "x") { const h = p.hist, a = h[0], b = h[h.length - 1], dt = Math.max(16, b[0] - a[0]);
      const v = -(b[1] - a[1]) / dt * (TAU / innerWidth) * .42 * 1000;   // rad/s
      nav.yawT = Math.round((nav.yaw + Math.max(-1.2, Math.min(1.2, v * .28))) / STEP) * STEP; kick();
      ctx.onTurned(((Math.round(nav.yawT / STEP) % 10) + 10) % 10); }
  }
  cv.addEventListener("pointerdown", down); addEventListener("pointermove", move, { passive: true }); addEventListener("pointerup", up); addEventListener("pointercancel", up);

  function lookUp(on) { if (focused) return; nav.up = on; nav.pitchT = on ? 1.02 : -.1; ctx.onLook(on); B.haptic.soft(); kick(); }

  /* tilt parallax: Telegram's DeviceOrientation, or the browser's; tiny and smoothed */
  let tiltBase = null;
  const onTilt = (beta, gamma) => { if (beta == null || gamma == null) return; if (!tiltBase) tiltBase = { beta };
    nav.tY = Math.max(-1, Math.min(1, gamma / 40)) * .03; nav.tP = Math.max(-1, Math.min(1, (beta - tiltBase.beta) / 40)) * -.02; kick(); };
  const tgo = B.tg && B.tg.DeviceOrientation;
  const tgTilt = () => onTilt(tgo.beta * 57.3, tgo.gamma * 57.3), winTilt = (e) => onTilt(e.beta, e.gamma);
  if (!B.reduced) { try { if (tgo && tgo.start && B.tg.isVersionAtLeast && B.tg.isVersionAtLeast("8.0")) { tgo.start({ refresh_rate: 50 }); B.tg.onEvent("deviceOrientationChanged", tgTilt); }
    else addEventListener("deviceorientation", winTilt); } catch { addEventListener("deviceorientation", winTilt); } }

  /* ── guide light for the first visit ── */
  const orb = F.glow(X.T.glow, 0xffe2a8, .35, 0); scene.add(orb); const orbCore = F.glow(X.T.glow, 0xffffff, .12, 0); orb.add(orbCore); orbCore.scale.set(.35, .35, 1);
  let orbTo = null;

  /* ── loop ── */
  let raf = 0, last = 0, t0 = performance.now(), frames = 0, slowSum = 0, settled = 0;
  const ready = new Promise((r) => { ctx._ready = r; });
  function kick() { if (!raf && !paused && !document.hidden) { last = performance.now(); raf = requestAnimationFrame(frame); } }
  function frame(now) {
    raf = 0; const dt = Math.min(.05, (now - last) / 1000); last = now;
    if (paused || document.hidden) return;
    const k = 1 - Math.exp(-dt * 7.5);
    nav.yaw += (nav.yawT - nav.yaw) * (ptr && ptr.axis === "x" ? 1 : k);
    nav.pitch += (nav.pitchT - nav.pitch) * (1 - Math.exp(-dt * 5));
    nav.tiltY += (nav.tY - nav.tiltY) * k; nav.tiltP += (nav.tP - nav.tiltP) * k;
    if (focus) { const p = Math.min(1, (now - focus.t0) / focus.dur), e = ease(p);
      camera.position.lerpVectors(focus.from.pos, focus.to.pos, e); currentLook.lerpVectors(focus.from.look, focus.to.look, e); pose.off = focus.from.off + (focus.to.off - focus.from.off) * e;
      if (p >= 1) { const r = focus.resolve; focus = null; r && r(); } }
    else if (!focused) { camera.position.copy(pose.pos); roomLook(currentLook); }
    camera.lookAt(currentLook);
    applyOffset();
    if (orbTo) { orb.position.lerp(orbTo, 1 - Math.exp(-dt * 2.4)); orb.material.opacity += (.9 - orb.material.opacity) * k; orbCore.material.opacity = orb.material.opacity; }
    else if (orb.material.opacity > .001) { orb.material.opacity *= 1 - k; orbCore.material.opacity = orb.material.opacity; }
    const t = (now - t0) / 1000; room.update(t, dt, camera); if (stage && stage.update) stage.update(t, dt);
    if (compiling) { raf = requestAnimationFrame(frame); return; }
    if (post) post.render(scene, camera); else renderer.render(scene, camera);
    frames++; if (frames === 2) { ctx._ready(); if (forcedGfx) loadTextures(); }   // a forced level needs no measuring
    if (frames > 10 && frames <= 50) { slowSum += dt; if (frames === 50) decide(slowSum / 40 * 1000); }
    const moving = Math.abs(nav.yawT - nav.yaw) > 1e-4 || Math.abs(nav.pitchT - nav.pitch) > 1e-4 || focus || ptr;
    settled = moving ? 0 : settled + 1;
    raf = requestAnimationFrame(frame);   // the room is alive (candles, dust): keep drawing while visible and uncovered
  }
  let measured = null;
  function decide(avgMs) {   // after frames 10-50: keep High, step down to Medium, or leave for LITE
    measured = Math.round(avgMs * 10) / 10;
    if (avgMs > LITE_MS && !ctx.forced) { ctx.onSlow(); return; }
    if (!forcedGfx && gfx === "high" && avgMs > HIGH_MAX_MS) setGfx("medium").then(loadTextures);
    else loadTextures();
  }
  let offW = 0;
  function applyOffset() { const w = innerWidth, h = innerHeight;
    if (Math.abs(pose.off) < .001) { if (camera.view && camera.view.enabled) camera.clearViewOffset(); }
    else camera.setViewOffset(w, h, 0, pose.off * h, w, h);
    if (offW !== w) { offW = w; } }
  function resize() { renderer.setSize(innerWidth, innerHeight); camera.aspect = innerWidth / innerHeight; camera.updateProjectionMatrix();
    if (post) post.setSize(...renderer.getDrawingBufferSize(new THREE.Vector2()).toArray()); kick(); }
  addEventListener("resize", resize);
  const vis = () => { if (!document.hidden) kick(); }; document.addEventListener("visibilitychange", vis);
  cv.addEventListener("webglcontextlost", (e) => { e.preventDefault(); ctx.onLost && ctx.onLost(); });

  // start facing the tarot table; shaders compile in parallel first where the driver allows (KHR_parallel_shader_compile)
  nav.yaw = nav.yawT = 0; camera.position.copy(pose.pos); roomLook(currentLook); camera.lookAt(currentLook);
  try { await Promise.race([renderer.compileAsync(scene, camera), new Promise((r) => setTimeout(r, 2500))]); } catch {}
  kick();
  await Promise.race([ready, new Promise((r) => setTimeout(r, 4000))]);

  const api = {
    tier: "full", canvas: cv, room, THREE, F, X, camera, scene, renderer,
    get gfx() { return gfx; }, get gfxMeasuredMs() { return measured; }, texReady, setGfx,
    index, get up() { return nav.up; },
    turnTo(i) { if (focused) return; nav.up = false; nav.pitchT = -.1; const cur = nav.yawT; let target = i * STEP; while (target - cur > Math.PI) target -= TAU; while (cur - target > Math.PI) target += TAU; nav.yawT = target; kick(); ctx.onTurned(((i % 10) + 10) % 10); },
    step(d) { api.turnTo(index() + d); },
    lookUp,
    async focus(id, mode = "panel") {
      api.pause(false);   // a glide only finishes in a rendered frame
      if (id !== "horo" && nav.up) { nav.up = false; nav.pitchT = -.1; }
      if (id !== "horo") { const st = room.stations.get(id); if (st) { const slot = STATIONS.find((s) => s.id === id).slot; api.turnTo(slot); nav.yaw = nav.yawT; } }
      if (!focused) { camera.position.copy(pose.pos); roomLook(currentLook); }
      focused = id; await glide(focusPose(id, mode), 900);
    },
    async refocus(mode) { api.pause(false); if (focused) await glide(focusPose(focused, mode), 480); },
    async unfocus() { if (!focused) return; api.pause(false);
      if (focused === "horo") { nav.up = false; nav.pitch = nav.pitchT = -.1; ctx.onLook(false); }
      const to = { pos: pose.pos.clone(), look: roomLook(new THREE.Vector3()), off: 0 }; await glide(to, 900); focused = null; },
    get focused() { return focused; },
    pause(on) { paused = on; if (!on) kick(); else if (raf) { cancelAnimationFrame(raf); raf = 0; } },
    setNew(map) { for (const [id, v] of Object.entries(map)) { const s = room.stations.get(id); if (s) s.isNew = !!v; } kick(); },
    setBusy(on, path) { room.setBusy(on, path); kick(); },
    react(kind, data) { room.react(kind, data); kick(); },
    setSky(sky) { room.setSky(sky); kick(); },
    guide(step) { const ids = ["tarot", "sphere", "horo"], st = room.stations.get(ids[step]);
      if (!st) { orbTo = null; return; }
      if (ids[step] === "horo") { orbTo = new THREE.Vector3(0, 4.8, -2.4).applyAxisAngle(new THREE.Vector3(0, 1, 0), -nav.yaw); lookUp(true); }
      else { if (nav.up) lookUp(false); api.turnTo(STATIONS.find((s) => s.id === ids[step]).slot); orbTo = st.center.clone().add(new THREE.Vector3(0, .35, 0)); }
      if (step === 0) orb.position.set(0, 2.4, 0);
      kick(); },
    endGuide() { orbTo = null; if (nav.up) lookUp(false); kick(); },
    setStage(s) { stage = s; kick(); },
    ease,
    raycast(x, y, list) { const ray = new THREE.Raycaster(); ray.setFromCamera(new THREE.Vector2((x / innerWidth) * 2 - 1, -(y / innerHeight) * 2 + 1), camera); return ray.intersectObjects(list, true); },
    rayPlane(x, y, plane) { const ray = new THREE.Raycaster(); ray.setFromCamera(new THREE.Vector2((x / innerWidth) * 2 - 1, -(y / innerHeight) * 2 + 1), camera); return ray.ray.intersectPlane(plane, new THREE.Vector3()); },
    project(v) { const p = v.clone().project(camera); return { x: (p.x + 1) / 2 * innerWidth, y: (1 - p.y) / 2 * innerHeight }; },
    stationCenter(id) { const s = room.stations.get(id); return s && s.center.clone(); },
    kick,
    dispose() {
      paused = true; if (raf) cancelAnimationFrame(raf); raf = 0;
      cv.removeEventListener("pointerdown", down); removeEventListener("pointermove", move); removeEventListener("pointerup", up); removeEventListener("pointercancel", up);
      removeEventListener("resize", resize); document.removeEventListener("visibilitychange", vis); removeEventListener("deviceorientation", winTilt);
      try { if (tgo && tgo.stop) { tgo.stop(); B.tg.offEvent("deviceOrientationChanged", tgTilt); } } catch {}
      scene.traverse((o) => { if (o.geometry) o.geometry.dispose(); const m = o.material; if (m) (Array.isArray(m) ? m : [m]).forEach((x) => { for (const v of Object.values(x)) if (v && v.isTexture) v.dispose(); x.dispose(); }); });
      if (post) post.dispose(); post = null;
      X.dispose(); renderer.dispose(); try { renderer.forceContextLoss(); } catch {} cv.remove();
    },
  };
  return api;
}
