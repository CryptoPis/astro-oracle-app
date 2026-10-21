/* Oracle chamber (FULL tier): the room and its ten objects.
   A decagon of rubble stone, an oak floor with a round rug, a star dome above, and one object per practice. The shell
   is PBR (albedo + normal map; roughness derived from the albedo in the shader) from the art references, loaded after
   the first frames (see upgrade); until then small procedural textures stand in. The window and the dome are
   pre-rendered plates under live shaders (the real moon phase; the Milky Way shimmer, planets and the ecliptic).
   Lights: an ambient haze, two flickering candle lights and the moonlight; shadows are rendered once. */

const TAU = Math.PI * 2;
const WALL = 6 * Math.cos(Math.PI / 10);   // the decagon's flat faces sit at the apothem (5.71 m), not at the 6 m radius
/* palette measured from the art references (scripts/chamber_assets.py): candle amber, moonlight; the haze and the
   raised black point (#0b0710, in full.js) lift the references' crushed blacks */
export const PALETTE = { candle: 0xf2a958, moon: 0xafb8d1, haze: 0x352f35, night: 0x0b0710 };

/* MeshStandardMaterial whose roughness follows the albedo: dark crevices rough, lighter worn tops smoother */
function pbr(THREE, opts, [lo, hi]) {
  const m = new THREE.MeshStandardMaterial({ metalness: 0, roughness: hi, ...opts });
  const f = (v) => v.toFixed(3);
  m.onBeforeCompile = (s) => { s.fragmentShader = s.fragmentShader.replace("#include <roughnessmap_fragment>", `#include <roughnessmap_fragment>
    roughnessFactor = mix(${f(hi)}, ${f(lo)}, smoothstep(0.015, 0.25, dot(diffuseColor.rgb, vec3(0.2126, 0.7152, 0.0722))));`); };
  m.customProgramCacheKey = () => `rough${lo}-${hi}`;
  return m;
}

export function buildRoom(THREE, B, X, F, { STEP, STATIONS }) {
  const T = X.T, scene = new THREE.Scene();
  const night = nightInfo();
  scene.background = new THREE.Color(PALETTE.night);
  scene.fog = new THREE.FogExp2(PALETTE.haze, .045);

  const lam = (o) => new THREE.MeshLambertMaterial(o);
  const at = (m, x, y, z) => { m.position.set(x, y, z); return m; };
  /* the shell's tiled textures: [procedural stand-in, repeat]; upgrade() swaps in the photographic set */
  const rep = (t, x, y) => { const c = t.clone(); c.wrapS = c.wrapT = THREE.RepeatWrapping; c.repeat.set(x, y); c.needsUpdate = true; X.track(c); return c; };
  const shell = {
    stone: pbr(THREE, { map: rep(T.stone, 22, 2.6), color: 0xd6cfd8 }, [.72, .95]),
    pillar: pbr(THREE, { map: rep(T.stone, .6, 2.6), color: 0xb8b0bc }, [.72, .95]),
    floor: pbr(THREE, { map: rep(T.floor, 10, 10), color: 0xffffff }, [.42, .78]),
    wains: pbr(THREE, { map: rep(T.floor, 34, .8), color: 0xc8b4a4, side: THREE.BackSide }, [.5, .8]),
    rug: pbr(THREE, { map: T.rug }, [.86, .98]),
    velvet: pbr(THREE, { map: T.velvet }, [.62, .95]),
  };
  shell.stone.side = THREE.BackSide;
  const mat = {
    stone: shell.stone,
    floor: shell.floor,
    wood: lam({ map: T.table, color: 0xe8d0b8 }),
    gold: new THREE.MeshMatcapMaterial({ matcap: T.gold }),
    brass: new THREE.MeshMatcapMaterial({ matcap: T.brass }),
    dark: new THREE.MeshMatcapMaterial({ matcap: T.darkwood }),
    ceramic: new THREE.MeshMatcapMaterial({ matcap: T.ceramic }),
    hidden: new THREE.MeshBasicMaterial({ visible: false }),
  };
  const metal = [mat.gold, mat.brass, mat.dark, mat.ceramic];   // matcaps ignore lights: tinted with the candlelight instead

  /* ── shell ── */
  const receivers = [], casters = [];
  const floor = new THREE.Mesh(new THREE.CircleGeometry(6.2, 10, Math.PI / 10), mat.floor); floor.rotation.x = -Math.PI / 2; scene.add(floor);
  const rug = new THREE.Mesh(new THREE.CircleGeometry(2.3, 72), shell.rug); rug.rotation.x = -Math.PI / 2; rug.position.y = .006; scene.add(rug);
  const wallGeo = new THREE.CylinderGeometry(6, 6, 4.2, 10, 1, true, Math.PI / 10);
  const walls = new THREE.Mesh(wallGeo, mat.stone); walls.position.y = 2.1; scene.add(walls);
  const wains = new THREE.Mesh(new THREE.CylinderGeometry(5.94, 5.94, .9, 10, 1, true, Math.PI / 10), shell.wains);
  wains.position.y = .45; scene.add(wains);
  receivers.push(floor, rug, walls, wains);
  for (const [y, h] of [[.92, .035], [3.9, .025]]) { const b = new THREE.Mesh(new THREE.CylinderGeometry(5.9, 5.9, h, 10, 1, true, Math.PI / 10), Object.assign(mat.gold.clone(), { side: THREE.BackSide })); b.position.y = y; scene.add(b); metal.push(b.material); }
  // pillars at the corners, between the objects
  const pillarGeo = new THREE.CylinderGeometry(.13, .16, 4.2, 10), capGeo = new THREE.TorusGeometry(.17, .025, 6, 20);
  for (let i = 0; i < 10; i++) { const a = (i + .5) * STEP, p = new THREE.Mesh(pillarGeo, shell.pillar);
    p.position.set(Math.sin(a) * 5.8, 2.1, -Math.cos(a) * 5.8); scene.add(p); casters.push(p); receivers.push(p);
    for (const y of [.95, 4.0]) { const c = new THREE.Mesh(capGeo, mat.gold); c.rotation.x = Math.PI / 2; c.position.set(p.position.x, y, p.position.z); scene.add(c); } }
  // the star dome: the night-sky plate seen from below (azimuthal projection, zenith in the middle) under a live shimmer
  const domeMat = domeMaterial(THREE, F.clock);
  const dome = new THREE.Mesh(new THREE.SphereGeometry(6, 64, 20, 0, TAU, 0, Math.PI / 2), domeMat);
  dome.position.y = 4.2; scene.add(dome);
  scene.add(domeStars(THREE, F.clock, X.rng(91)));

  /* ── lights ── */
  const ambient = new THREE.AmbientLight(PALETTE.haze, .85); scene.add(ambient);
  const central = new THREE.PointLight(night.candle, 30, 0, 1.45); central.position.set(0, 3.0, 0); scene.add(central);
  const moonDir = STATIONS.find((s) => s.id === "moon").slot * STEP;
  const moonLight = new THREE.DirectionalLight(PALETTE.moon, .35 + night.moon * 1.1);
  moonLight.position.set(Math.sin(moonDir) * 8, 5, -Math.cos(moonDir) * 8); moonLight.target.position.set(0, 0, 0); scene.add(moonLight, moonLight.target);
  moonLight.userData.base = moonLight.intensity;
  /* shadows: the moon (both graphics levels) and the central candle (High); drawn once, see setShadows */
  { const s = moonLight.shadow; s.mapSize.set(1024, 1024); Object.assign(s.camera, { left: -6.5, right: 6.5, top: 6.5, bottom: -6.5, near: 1, far: 18 }); s.bias = -.0006; s.normalBias = .02; }
  { const s = central.shadow; s.mapSize.set(512, 512); s.camera.near = .2; s.camera.far = 9; s.bias = -.002; s.normalBias = .02; }

  // candle sconces on the pillars: a brass arm, a dish and a candle; their light is baked into glows on the stone
  const armGeo = new THREE.CylinderGeometry(.012, .012, .26, 6), dishGeo = new THREE.CylinderGeometry(.07, .045, .025, 14);
  const wallGlow = (pos, color, size, op) => { const g = F.glow(T.glow, color, size, op); g.position.copy(pos); scene.add(g); return g; };
  const sconces = [];
  for (let i = 0; i < 10; i++) { const a = (i + .5) * STEP, r = 5.62, x = Math.sin(a) * r, z = -Math.cos(a) * r;
    const arm = new THREE.Mesh(armGeo, mat.brass); arm.position.set(x, 2.02, z); arm.rotation.x = Math.PI / 2; arm.rotation.y = -a; arm.rotateX(-.0); scene.add(arm);
    const dish = new THREE.Mesh(dishGeo, mat.brass); dish.position.set(Math.sin(a) * (r - .14), 2.1, -Math.cos(a) * (r - .14)); scene.add(dish);
    const c = F.candle(.12, .02); c.position.set(dish.position.x, 2.11, dish.position.z); scene.add(c);
    sconces.push(wallGlow(new THREE.Vector3(Math.sin(a) * (r + .02), 2.35, -Math.cos(a) * (r + .02)), 0xffb870, 2.2, .22)); }
  // a warm pool of light on the stone behind every object (the moon window gets a cool one)
  for (const st of STATIONS) { const a = st.slot * STEP, cool = st.id === "moon";
    wallGlow(new THREE.Vector3(Math.sin(a) * (WALL - .06), 1.7, -Math.cos(a) * (WALL - .06)), cool ? 0x8fa0ff : 0xffa860, cool ? 3.2 : 3.6, cool ? .16 : .2); }

  /* ── stations ── */
  const stations = new Map();
  const place = (grp, slot, r, y = 0) => { const a = slot * STEP; grp.position.set(Math.sin(a) * r, y, -Math.cos(a) * r); grp.rotation.y = -a; scene.add(grp); return grp; };
  const hitBox = (w, h, d, y) => { const m = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), mat.hidden); m.position.y = y; return m; };
  const engr = new Map();
  function medallion(st) {   // a gold engraving of the practice above each object, on the wall
    const t = X.engraving(st.art, 256); engr.set(st.id, t);
    const m = new THREE.Mesh(new THREE.PlaneGeometry(1.05, 1.05), new THREE.MeshBasicMaterial({ map: t, transparent: true, opacity: .62, depthWrite: false, blending: THREE.AdditiveBlending }));
    const a = st.slot * STEP; m.position.set(Math.sin(a) * (WALL - .04), 3.0, -Math.cos(a) * (WALL - .04)); m.rotation.y = -a; scene.add(m); return m;
  }
  function register(id, grp, center, dist, hit, extra = {}) {
    grp.add(hit); hit.userData.station = id; grp.updateMatrixWorld(true);
    const newGlow = F.glow(T.glow, 0xffd27a, 1.3, 0); newGlow.position.copy(center);
    grp.add(newGlow);
    stations.set(id, { id, grp, center: grp.localToWorld(center.clone()), dist, hit, newGlow, isNew: false, ...extra });
  }
  const S = Object.fromEntries(STATIONS.map((s) => [s.id, s]));
  STATIONS.forEach(medallion);

  // 0 · tarot table: velvet cloth, the deck, a candle, the small box of revealed cards
  { const g = new THREE.Group();
    const top = new THREE.Mesh(new THREE.CylinderGeometry(.62, .62, .05, 40), mat.wood); top.position.y = .8; g.add(top);
    const cloth = new THREE.Mesh(new THREE.CylinderGeometry(.58, .58, .012, 48), shell.velvet); cloth.position.y = .83; g.add(cloth);
    g.add(at(new THREE.Mesh(new THREE.CylinderGeometry(.07, .11, .78, 12), mat.dark), 0, .39, 0));
    g.add(at(new THREE.Mesh(new THREE.CylinderGeometry(.3, .36, .05, 24), mat.dark), 0, .025, 0));
    const side = lam({ color: 0xd8c9a6 }), back = lam({ color: 0x2a2060 });
    const deck = new THREE.Mesh(new THREE.BoxGeometry(.13, .04, .2), [side, side, back, side, side, side]); deck.position.set(0, .856, .02); g.add(deck);
    new THREE.TextureLoader().load(B.BACK_IMG, (tx) => { tx.colorSpace = THREE.SRGBColorSpace; back.map = tx; back.color.set(0xffffff); back.needsUpdate = true; });
    const c = F.candle(.14, .022); c.position.set(.36, .836, -.3); g.add(c);
    const box = new THREE.Mesh(new THREE.BoxGeometry(.2, .07, .14), mat.dark); box.position.set(-.3, .87, -.2); box.rotation.y = .3; g.add(box);
    const lid = new THREE.Mesh(new THREE.BoxGeometry(.21, .012, .15), mat.gold); lid.position.set(-.3, .91, -.2); lid.rotation.y = .3; g.add(lid);
    place(g, S.tarot.slot, 2.7);
    register("tarot", g, new THREE.Vector3(0, .86, 0), 1.25, hitBox(1.3, .5, 1.3, .8), { deck, box, lid, candle: c, stageDist: .34, stageRise: 2.5, stageOff: -.02 });
  }
  // 1 · crystal ball on a brass stand
  { const g = new THREE.Group();
    const prof = [[0, 0], [.2, 0], [.21, .03], [.09, .09], [.05, .35], [.075, .62], [.045, .8], [.05, .9], [.15, .97], [.17, 1.0]].map(([x, y]) => new THREE.Vector2(x, y));
    g.add(new THREE.Mesh(new THREE.LatheGeometry(prof, 28), mat.brass));
    const ball = new THREE.Mesh(new THREE.SphereGeometry(.21, 48, 32), sphereMaterial(THREE, F.clock)); ball.position.y = 1.2; g.add(ball);
    const halo = F.glow(T.glowViolet, 0x8b6cff, .95, .5); halo.position.y = 1.2; g.add(halo);
    place(g, S.sphere.slot, 2.9);
    register("sphere", g, new THREE.Vector3(0, 1.18, 0), .95, hitBox(.6, 1.4, .6, .7), { ball, halo, stageDist: 1.3, stageRise: .1, stageOff: .07 });
  }
  // 2 · the moon window (real phase), its sill with three ritual candles, the moonbeam and dust
  { const g = new THREE.Group(), W = 1.0, Hr = 1.15, r = W / 2;
    const shape = new THREE.Shape(); shape.moveTo(-r, 0); shape.lineTo(r, 0); shape.lineTo(r, Hr); shape.absarc(0, Hr, r, 0, Math.PI, false); shape.lineTo(-r, 0);
    const paneGeo = new THREE.ShapeGeometry(shape, 24), pos = paneGeo.attributes.position, uv = paneGeo.attributes.uv;
    for (let i = 0; i < pos.count; i++) uv.setXY(i, (pos.getX(i) + r) / W, pos.getY(i) / (Hr + r));
    const moon = B.moonNow();
    const pane = new THREE.Mesh(paneGeo, windowMaterial(THREE, (moon.age_days || 0) / 29.53, (moon.illumination || 50) / 100, [W, Hr + r])); g.add(pane);
    const fr = mat.dark;
    for (const [w, h, x, y] of [[.06, Hr, -r, Hr / 2], [.06, Hr, r, Hr / 2], [W + .12, .07, 0, 0], [.03, Hr + r, 0, (Hr + r) / 2], [W, .03, 0, Hr * .55]]) {
      const b = new THREE.Mesh(new THREE.BoxGeometry(w, h, .06), fr); b.position.set(x, y, .02); g.add(b); }
    const arch = new THREE.Mesh(new THREE.TorusGeometry(r, .035, 8, 32, Math.PI), mat.gold); arch.position.set(0, Hr, .03); g.add(arch);
    const sill = new THREE.Mesh(new THREE.BoxGeometry(W + .3, .06, .3), mat.wood); sill.position.set(0, -.03, .13); g.add(sill);
    const ritual = [-.3, 0, .3].map((x, i) => { const c = F.candle(.09 + i * .02, .02); c.position.set(x, 0, .16); c.userData.flame.visible = false; c.userData.glow.visible = false; g.add(c); return c; });
    place(g, S.moon.slot, WALL - .07, 1.35);
    const glowWin = F.glow(T.glowCool, 0x9fb0ff, 2.6, .35 + night.moon * .3); glowWin.position.set(0, .9, .2); g.add(glowWin);
    register("moon", g, new THREE.Vector3(0, .75, 0), 2.0, hitBox(1.3, 2.0, .4, .8), { ritual, pane, stageDist: .9, stageRise: .05, stageOff: .1 });
    const a = S.moon.slot * STEP, from = new THREE.Vector3(Math.sin(a) * 5.6, 2.3, -Math.cos(a) * 5.6), to = new THREE.Vector3(Math.sin(a) * 1.2, 0, -Math.cos(a) * 1.2);
    scene.add(F.beam(from, to, 1.3, 0xb0c0ff, .05 + night.moon * .08));
    const mid = from.clone().lerp(to, .5), box = new THREE.Box3(new THREE.Vector3(mid.x - 1.2, .2, mid.z - 1.2), new THREE.Vector3(mid.x + 1.2, 2.6, mid.z + 1.2));
    scene.add(F.dust(140, box, 0xd8e0ff, 9));
  }
  // 3 · the oracle's candle: a tall brass candlestick, a thick candle and the second candle light
  let flameLight;
  { const g = new THREE.Group();
    const prof = [[0, 0], [.17, 0], [.18, .03], [.06, .1], [.04, .5], [.07, .55], [.035, .62], [.035, .95], [.1, .98], [.11, 1.0]].map(([x, y]) => new THREE.Vector2(x, y));
    g.add(new THREE.Mesh(new THREE.LatheGeometry(prof, 24), mat.brass));
    const c = F.candle(.3, .055, 0xf0e2c6); c.position.y = 1.0; g.add(c);
    c.userData.flame.scale.set(1.5, 1.5, 1.5); c.userData.glow.scale.multiplyScalar(1.6);
    flameLight = new THREE.PointLight(night.candle, 4, 0, 1.6); flameLight.position.set(0, 1.42, .08); g.add(flameLight);
    place(g, S.advisor.slot, 2.9);
    register("advisor", g, new THREE.Vector3(0, 1.3, 0), .95, hitBox(.5, 1.6, .5, .8), { candle: c });
  }
  // 4 · the book of dreams on a lectern, a quill in an inkwell
  { const g = new THREE.Group();
    g.add(at(new THREE.Mesh(new THREE.CylinderGeometry(.05, .07, .95, 10), mat.dark), 0, .47, 0));
    g.add(at(new THREE.Mesh(new THREE.CylinderGeometry(.22, .26, .04, 20), mat.dark), 0, .02, 0));
    const desk = new THREE.Group(); desk.position.set(0, 1.0, 0); desk.rotation.x = .42; g.add(desk);
    desk.add(new THREE.Mesh(new THREE.BoxGeometry(.66, .03, .46), mat.wood));
    const cover = new THREE.Mesh(new THREE.BoxGeometry(.6, .02, .4), lam({ color: 0x4a1a24 })); cover.position.y = .025; desk.add(cover);
    const pageMat = lam({ map: T.parchment, side: THREE.DoubleSide });
    for (const sgn of [-1, 1]) { const pg = new THREE.PlaneGeometry(.27, .37, 10, 1), p = pg.attributes.position;
      for (let i = 0; i < p.count; i++) { const x = p.getX(i), u = (x + .135) / .27, curl = sgn < 0 ? u : 1 - u; p.setZ(i, Math.sin(Math.min(1, curl * 1.2) * Math.PI * .5) * .035); }
      pg.computeVertexNormals(); const page = new THREE.Mesh(pg, pageMat); page.rotation.x = -Math.PI / 2; page.position.set(sgn * .14, .04, 0); desk.add(page); }
    const well = new THREE.Mesh(new THREE.CylinderGeometry(.03, .035, .05, 12), mat.glassDark || mat.dark); well.position.set(.26, .05, -.14); desk.add(well);
    const quill = new THREE.Group(); quill.position.set(.26, .07, -.14); quill.rotation.set(-.5, 0, -.35); desk.add(quill);
    quill.add(at(new THREE.Mesh(new THREE.CylinderGeometry(.003, .004, .26, 5), mat.ceramic), 0, .13, 0));
    const feather = new THREE.Mesh(new THREE.CircleGeometry(.05, 16), lam({ color: 0xece4d4, side: THREE.DoubleSide, emissive: 0x201810 }));
    feather.scale.set(.45, 2.2, 1); feather.position.y = .19; quill.add(feather);
    place(g, S.dream.slot, 2.9);
    register("dream", g, new THREE.Vector3(0, 1.02, 0), .95, hitBox(.8, 1.3, .7, .7), { desk, quill, pageMat });
  }
  // 5 · the brass astrolabe on the wall: three rings and the rete turn to the person's numbers
  { const g = new THREE.Group();
    const disc = new THREE.Mesh(new THREE.CylinderGeometry(.56, .56, .04, 64), mat.brass); disc.rotation.x = Math.PI / 2; g.add(disc);
    const rings = [.5, .41, .31].map((rr, i) => { const pivot = new THREE.Group(); pivot.position.z = .03 + i * .012; g.add(pivot);
      pivot.add(new THREE.Mesh(new THREE.TorusGeometry(rr, .011, 6, 64), mat.gold));
      const tick = new THREE.Mesh(new THREE.BoxGeometry(.018, .07, .012), mat.gold); tick.position.y = rr; pivot.add(tick); return pivot; });
    const rete = new THREE.Mesh(new THREE.PlaneGeometry(.8, .8), new THREE.MeshBasicMaterial({ map: X.engraving("numerology", 256), transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, opacity: .85 }));
    rete.position.z = .07; g.add(rete);
    const hang = new THREE.Mesh(new THREE.TorusGeometry(.07, .012, 6, 16), mat.gold); hang.position.y = .62; g.add(hang);
    place(g, S.num.slot, WALL - .1, 1.85);
    register("num", g, new THREE.Vector3(0, 0, .03), 1.9, hitBox(1.25, 1.25, .2, 0), { rings, rete });
  }
  // 6 · the star-chart scroll on a small table
  { const g = new THREE.Group();
    const top = new THREE.Mesh(new THREE.BoxGeometry(.74, .04, .52), mat.wood); top.position.y = .76; g.add(top);
    for (const [x, z] of [[-.32, -.21], [.32, -.21], [-.32, .21], [.32, .21]]) g.add(at(new THREE.Mesh(new THREE.CylinderGeometry(.022, .026, .74, 8), mat.dark), x, .37, z));
    const chart = new THREE.Mesh(new THREE.PlaneGeometry(.58, .4), lam({ map: T.chart })); chart.rotation.x = -Math.PI / 2 + .12; chart.position.set(0, .8, 0); g.add(chart);
    const rollMat = lam({ map: T.parchment, color: 0xd8c6a0 });
    for (const x of [-.31, .31]) { const roll = new THREE.Mesh(new THREE.CylinderGeometry(.032, .032, .44, 14), rollMat); roll.rotation.x = Math.PI / 2; roll.position.set(x, .81, 0); g.add(roll); }
    place(g, S.chart.slot, 2.85);
    register("chart", g, new THREE.Vector3(0, .82, 0), 1.05, hitBox(.9, .6, .7, .6), { chart });
  }
  // 7 · the aura mirror in an oval gold frame
  { const g = new THREE.Group();
    const oval = new THREE.Group(); oval.position.y = 1.35; oval.scale.set(1, 1.45, 1); g.add(oval);
    oval.add(new THREE.Mesh(new THREE.TorusGeometry(.42, .032, 10, 64), mat.gold));
    oval.add(new THREE.Mesh(new THREE.TorusGeometry(.465, .012, 6, 64), mat.brass));
    const glass = new THREE.Mesh(new THREE.CircleGeometry(.415, 64), mirrorMaterial(THREE, F.clock)); glass.position.z = -.005; oval.add(glass);
    for (const x of [-.3, .3]) { const leg = new THREE.Mesh(new THREE.BoxGeometry(.035, .78, .035), mat.dark); leg.position.set(x, .39, -.05); leg.rotation.z = x * .2; g.add(leg); }
    place(g, S.aura.slot, 3.2);
    register("aura", g, new THREE.Vector3(0, 1.35, 0), 1.45, hitBox(1.0, 1.9, .3, 1.0), { glass });
  }
  // 8 · the coffee cup on its saucer, on a small round table
  { const g = new THREE.Group();
    g.add(at(new THREE.Mesh(new THREE.CylinderGeometry(.32, .32, .035, 32), mat.wood), 0, .68, 0));
    g.add(at(new THREE.Mesh(new THREE.CylinderGeometry(.04, .06, .66, 10), mat.dark), 0, .33, 0));
    const ceramic2 = Object.assign(mat.ceramic.clone(), { side: THREE.DoubleSide }); metal.push(ceramic2);   // a lathe surface seen from above: both sides
    const saucer = new THREE.Mesh(new THREE.LatheGeometry([[0, 0], [.1, 0], [.13, .012], [.135, .018]].map(([x, y]) => new THREE.Vector2(x, y)), 32), ceramic2);
    saucer.position.y = .7; g.add(saucer);
    const cup = new THREE.Group(); cup.position.y = .712; g.add(cup);
    cup.add(new THREE.Mesh(new THREE.LatheGeometry([[0, 0], [.035, 0], [.05, .02], [.058, .06], [.06, .09], [.056, .09], [.054, .062], [.0, .062]].map(([x, y]) => new THREE.Vector2(x, y)), 32), ceramic2));
    const coffee = new THREE.Mesh(new THREE.CircleGeometry(.054, 24), lam({ color: 0x2a160c })); coffee.rotation.x = -Math.PI / 2; coffee.position.y = .07; cup.add(coffee);
    const handle = new THREE.Mesh(new THREE.TorusGeometry(.022, .006, 6, 16, Math.PI * 1.2), mat.ceramic); handle.position.set(.065, .05, 0); handle.rotation.z = -Math.PI * .6; cup.add(handle);
    place(g, S.coffee.slot, 2.8);
    register("coffee", g, new THREE.Vector3(0, .76, 0), .75, hitBox(.6, .5, .6, .7), { cup, coffee, stageDist: .7, stageRise: 1.2, stageOff: .02 });
  }
  // 9 · the gift chest: brass bands, a lock, a hinged lid
  { const g = new THREE.Group();
    const body = new THREE.Mesh(new THREE.BoxGeometry(.52, .28, .34), lam({ map: T.table, color: 0xb08868 })); body.position.y = .14; g.add(body);
    const lid = new THREE.Group(); lid.position.set(0, .28, -.17); g.add(lid);
    const lidMesh = new THREE.Mesh(new THREE.CylinderGeometry(.17, .17, .52, 18, 1, false, 0, Math.PI), lam({ map: T.table, color: 0xb08868 }));
    lidMesh.rotation.z = Math.PI / 2; lidMesh.position.z = .17; lid.add(lidMesh);   // a half cylinder along x, curved side up
    for (const x of [-.17, .17]) { const band = new THREE.Mesh(new THREE.BoxGeometry(.035, .29, .35), mat.brass); band.position.set(x, .14, 0); g.add(band);
      const lb = new THREE.Mesh(new THREE.TorusGeometry(.172, .012, 4, 18, Math.PI), mat.brass); lb.rotation.y = Math.PI / 2; lb.position.set(x, 0, .17); lid.add(lb); }
    const lock = new THREE.Mesh(new THREE.BoxGeometry(.07, .08, .02), mat.gold); lock.position.set(0, .26, .175); g.add(lock);
    const inner = F.glow(T.glow, 0xffd27a, .9, 0); inner.position.set(0, .3, 0); g.add(inner);
    place(g, S.gift.slot, 2.8);
    register("gift", g, new THREE.Vector3(0, .3, 0), 1.05, hitBox(.7, .7, .55, .3), { lid, inner, body, stageDist: 1.35, stageRise: .7, stageOff: .02 });
  }

  /* the objects cast and receive the shadows (not the moon window: the moonlight comes through it) */
  for (const s of stations.values()) if (s.id !== "moon") s.grp.traverse((o) => {
    const m = o.material; if (!o.isMesh || o === s.hit || !m) return;
    if (Array.isArray(m) || (m.visible && !m.transparent && m.blending === THREE.NormalBlending)) { o.castShadow = true; casters.push(o); } });
  for (const s of stations.values()) s.grp.traverse((o) => { if (o.isMesh && o !== s.hit) o.receiveShadow = true; });
  receivers.forEach((o) => { o.receiveShadow = true; }); casters.forEach((o) => { o.castShadow = true; });

  /* the dome as a station (look up, then touch it) */
  const domeHit = new THREE.Mesh(new THREE.SphereGeometry(5.6, 16, 6, 0, TAU, 0, Math.PI / 2.4), Object.assign(mat.hidden.clone(), { side: THREE.BackSide }));
  domeHit.position.y = 4.2; domeHit.userData.station = "horo"; scene.add(domeHit);
  stations.set("horo", { id: "horo", grp: dome, center: new THREE.Vector3(0, 7.5, 0), dist: 0, hit: domeHit, newGlow: null, isNew: false });

  const smoke = F.smoke(new THREE.Vector3(Math.sin(S.dream.slot * STEP + .3) * 2.6, 1.0, -Math.cos(S.dream.slot * STEP + .3) * 2.6)); scene.add(smoke);
  scene.add(F.dust(110, new THREE.Box3(new THREE.Vector3(-2.5, .3, -2.5), new THREE.Vector3(2.5, 3.2, 2.5)), 0xffe2a8, 6));

  /* ── birthday: a golden glow all evening ── */
  const u = B.S.user || {}, today = new Date();
  const birthday = !!u.birth_date && u.birth_date.slice(5) === `${String(today.getMonth() + 1).padStart(2, "0")}-${String(today.getDate()).padStart(2, "0")}`;
  if (birthday) { ambient.color.set(0x6a5020); ambient.intensity = 1.5; central.intensity *= 1.25; scene.add(F.dust(160, new THREE.Box3(new THREE.Vector3(-4, .2, -4), new THREE.Vector3(4, 3.8, 4)), 0xffd27a, 10)); }

  /* ── reactions to readings: the mirror blooms, the astrolabe turns, constellations meet, the quill writes ── */
  const R = { bloom: 0, bloomT: 0, quill: 0, book: 0, compat: null };
  function constellation(r, seed) {
    const pts = [], rnd = X.rng(seed); for (let i = 0; i < 6; i++) pts.push(new THREE.Vector3((rnd() - .5) * .2, (rnd() - .5) * .14, (rnd() - .5) * .04));
    const g = new THREE.BufferGeometry().setFromPoints(pts), stars = new THREE.Points(g, new THREE.PointsMaterial({ map: T.glow, color: 0xffe2a8, size: .06, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending }));
    const lg = new THREE.BufferGeometry().setFromPoints(pts.slice(0, -1).flatMap((p, i) => [p, pts[i + 1]]));
    const lines = new THREE.LineSegments(lg, new THREE.LineBasicMaterial({ color: 0xe2bd6a, transparent: true, opacity: .55 }));
    const grp = new THREE.Group(); grp.add(stars, lines); return grp;
  }
  function react(kind, data) {
    if (kind === "aura") { const u = stations.get("aura").glass.material.uniforms, cols = (data || []).map((c) => c.hex).filter(Boolean);
      [u.uA, u.uB, u.uC].forEach((x, i) => x.value.set(cols[i] || cols[0] || "#e2bd6a")); R.bloom = 0; R.bloomT = 1; }
    if (kind === "num") { const rings = stations.get("num").rings, vals = [[data.lp, data.lp > 9 ? 33 : 9], [data.py, 9], [data.lucky, 49]];
      rings.forEach((rg, i) => { const [v, max] = vals[i] || []; if (v) rg.userData.target = Math.round(rg.rotation.z / (Math.PI * 2)) * Math.PI * 2 - v / max * Math.PI * 2; }); }
    if (kind === "quill") R.quill = 1;
    if (kind === "compat") { const st = stations.get("chart");
      if (R.compat) st.grp.remove(R.compat.grp);
      const a = constellation(.1, 5), b = constellation(.1, 9), grp = new THREE.Group(); grp.add(a, b); grp.position.set(0, 1.05, .05); st.grp.add(grp);
      R.compat = { grp, a, b, t0: clockNow() }; }
  }
  let tNow = 0; const clockNow = () => tNow;

  /* ── every frame ── */
  const flick = (t, s) => .82 + Math.sin(t * 7.1 + s) * .06 + Math.sin(t * 13.3 + s * 3) * .05 + Math.sin(t * 2.3 + s * 5) * .07;
  const tint = new THREE.Color();
  let busy = 0, busyBook = false;
  /* ── graphics levels: shadows (rendered once) and the photographic textures, loaded after the first frames ── */
  function setShadows(level) {   // "high": moon + central candle; "medium": the moon only
    moonLight.castShadow = true;
    const want = level === "high";
    if (central.castShadow !== want) { central.castShadow = want; if (!want && central.shadow.map) { central.shadow.map.dispose(); central.shadow.map = null; } }
  }
  const queue = [], fades = [];
  const pane = stations.get("moon").pane.material;
  function upgrade(size) {   // resolves (with the failures, if any) when every image is applied; one swap per frame
    const swap = (p, apply) => p.then((t) => new Promise((done) => queue.push(() => { apply(t); done(); })));
    const fit = (t, like) => { t.wrapS = t.wrapT = THREE.RepeatWrapping; t.repeat.copy(like.repeat); return t; };
    // a tiled set (albedo + normal) shared by several materials, each keeping its own repeat (clones share one upload)
    const tile = (name, scale, ...mats) => [
      swap(X.load(`${name}_${size}`, { srgb: true }), (t) => mats.forEach((m, i) => {
        const c = fit(i ? X.track(t.clone()) : t, m.map); X.release(m.map); m.map = c; m.needsUpdate = true; })),
      swap(X.load(`${name}_n_${size}`, { srgb: false }), (t) => mats.forEach((m, i) => {
        m.normalMap = fit(i ? X.track(t.clone()) : t, m.map); m.normalScale.set(scale, scale); m.needsUpdate = true; })),
    ];
    // a plate under a shader: raw colour (the shaders write display colour), faded in
    const plate = (name, u, fade) => swap(X.load(`${name}_${size}`, { srgb: false }), (t) => {
      if (name === "moon") t.wrapS = THREE.RepeatWrapping; u.value = t; fades.push(fade); });
    const jobs = [
      ...tile("stone", 1, shell.stone, shell.pillar), ...tile("floor", .8, shell.floor, shell.wains),
      ...tile("rug", .8, shell.rug), ...tile("velvet", .6, shell.velvet),
      plate("window", pane.uniforms.tView, pane.uniforms.uMix), plate("moon", pane.uniforms.tMoon, pane.uniforms.uMoonMix),
      plate("dome", domeMat.uniforms.tSky, domeMat.uniforms.uMix),
    ];
    return Promise.allSettled(jobs).then((r) => r.filter((x) => x.status === "rejected").map((x) => String(x.reason)));
  }

  function update(t, dt, camera) {
    F.clock.value = t;
    if (queue.length) queue.shift()();
    for (let i = fades.length - 1; i >= 0; i--) { const u = fades[i]; u.value = Math.min(1, u.value + dt * 1.6); if (u.value >= 1) fades.splice(i, 1); }
    { const st = stations.get("moon"); st.grp.worldToLocal(pane.uniforms.uCam.value.copy(camera.position)); }
    const k = flick(t, 0), kf = flick(t * (1 + busy * .9), 2.1) * (1 + busy * .35);
    central.intensity = 30 * k * (birthday ? 1.25 : 1); flameLight.intensity = 4 * kf;
    tint.setRGB(.75 + k * .3, .7 + k * .28, .68 + k * .25); for (const m of metal) m.color.copy(tint);
    for (let i = 0; i < sconces.length; i++) sconces[i].material.opacity = .22 * flick(t, i * 1.7);
    const st = stations.get("num"); st.rings.forEach((p, i) => { if (!p.userData.target) p.rotation.z += dt * (.02 + i * .015) * (i % 2 ? -1 : 1); });
    smoke.userData.update(t); tNow = t;
    // reactions
    R.bloom += (R.bloomT - R.bloom) * Math.min(1, dt * .7); stations.get("aura").glass.material.uniforms.uBloom.value = R.bloom;
    for (const rg of stations.get("num").rings) if (rg.userData.target != null) rg.rotation.z += (rg.userData.target - rg.rotation.z) * Math.min(1, dt * 1.4);
    { const d = stations.get("dream"); R.quill *= Math.exp(-dt * 2.5); d.quill.rotation.z = -.35 + Math.sin(t * 22) * .12 * R.quill; d.quill.position.x = .26 + Math.sin(t * 9) * .015 * R.quill;
      R.book += ((busyBook ? 1 : 0) - R.book) * Math.min(1, dt * 2); d.pageMat.emissive.setRGB(.25 * R.book * (.8 + .2 * Math.sin(t * 3)), .18 * R.book, .06 * R.book); }
    { const fl = stations.get("advisor").candle.userData.flame, k2 = 1.5 * (1 + busy * .45 * (.85 + .15 * Math.sin(t * 9))); fl.scale.set(k2, k2, k2); }
    if (R.compat) { const c = R.compat, k = Math.min(1, (t - c.t0) / 3.2), e2 = 1 - Math.pow(1 - k, 3), fade = t - c.t0 > 9 ? Math.max(0, 1 - (t - c.t0 - 9) / 2) : 1;
      c.a.position.set(-.3 * (1 - e2), Math.sin(t) * .01, 0); c.b.position.set(.3 * (1 - e2), Math.cos(t) * .01, 0); c.a.rotation.z = (1 - e2) * .6; c.b.rotation.z = -(1 - e2) * .6;
      for (const g of [c.a, c.b]) { g.children[0].material.size = .06 + (k >= 1 ? .03 * (1 + Math.sin(t * 3)) : 0); g.children[0].material.opacity = fade; g.children[1].material.opacity = .55 * fade; }
      if (fade <= 0) { stations.get("chart").grp.remove(c.grp); c.grp.traverse((o) => { if (o.geometry) o.geometry.dispose(); if (o.material) o.material.dispose(); }); R.compat = null; } }
    for (const s of stations.values()) if (s.newGlow) { const want = s.isNew ? .3 + .22 * Math.sin(t * 1.6 + s.grp.position.x) : 0; s.newGlow.material.opacity += (want - s.newGlow.material.opacity) * Math.min(1, dt * 3); }
    F.face(camera);
  }
  /* ── the real sky on the dome (from /api/sky): planets on a gold ecliptic ring, retrogrades with a red halo ── */
  const ALT = .78, ER = 5.7 * Math.cos(ALT), EY = 4.2 + 5.7 * Math.sin(ALT);
  const ecl = new THREE.Mesh(new THREE.TorusGeometry(ER, .014, 6, 160), new THREE.MeshBasicMaterial({ color: 0xe2bd6a, transparent: true, opacity: .55, fog: false }));
  ecl.rotation.x = Math.PI / 2; ecl.position.y = EY; scene.add(ecl);
  const skyGroup = new THREE.Group(); scene.add(skyGroup);
  const TINT = { sun: 0xffe7a0, moon: 0xe6e2ff, mercury: 0xc8d2ea, venus: 0xf6d6a8, mars: 0xff8a6a, jupiter: 0xf0c890, saturn: 0xe8d29a, uranus: 0x9fe6e0, neptune: 0x8fb0ff, pluto: 0xc9a6d8 };
  const skyAt = (lon, lift = 0) => { const a = Math.PI + lon * Math.PI / 180; return new THREE.Vector3(Math.cos(a) * (ER - lift), EY + lift * .3, -Math.sin(a) * (ER - lift)); };
  function setSky(sky) {
    while (skyGroup.children.length) { const c = skyGroup.children.pop(); c.material.dispose(); }
    if (!sky || !sky.planets) return;
    for (const p of sky.planets) { const big = p.id === "sun" || p.id === "moon" ? .5 : .32;
      const g = F.glow(T.glow, TINT[p.id] || 0xffffff, big, .95); g.position.copy(skyAt(p.lon)); skyGroup.add(g);
      if (p.retro) { const r = F.glow(T.glow, 0xff5a6a, big * 1.9, .35); r.position.copy(g.position); skyGroup.add(r); } }
  }

  return { scene, stations, update, central, flameLight, moonLight, ambient, birthday, night, engr, setSky, skyAt, setShadows, upgrade, shell,
    setBusy(on, path) { busy = on ? 1 : 0; busyBook = !!(on && path && path.startsWith("/api/dreams")); }, react, mat };
}

/* the dome's stars: points on the hemisphere, more near the horizon, a few gold, each twinkling on its own */
function domeStars(THREE, clock, r) {
  const n = 900, pos = new Float32Array(n * 3), seed = new Float32Array(n), size = new Float32Array(n);
  for (let i = 0; i < n; i++) { const th = Math.acos(1 - r() * .97) , ph = r() * Math.PI * 2, R = 5.85;
    pos[i * 3] = Math.sin(th) * Math.cos(ph) * R; pos[i * 3 + 1] = 4.2 + Math.cos(th) * R; pos[i * 3 + 2] = Math.sin(th) * Math.sin(ph) * R;
    seed[i] = r(); size[i] = r() < .06 ? 3.2 : 1.1 + r() * 1.3; }
  const g = new THREE.BufferGeometry(); g.setAttribute("position", new THREE.BufferAttribute(pos, 3)); g.setAttribute("aSeed", new THREE.BufferAttribute(seed, 1)); g.setAttribute("aSize", new THREE.BufferAttribute(size, 1));
  const m = new THREE.ShaderMaterial({ uniforms: { uTime: clock, uPx: { value: Math.min(devicePixelRatio || 1, 1.75) } },
    vertexShader: `attribute float aSeed, aSize; uniform float uTime, uPx; varying float vA; varying float vGold;
      void main() { vec4 mv = modelViewMatrix * vec4(position, 1.0); gl_Position = projectionMatrix * mv; gl_PointSize = aSize * uPx * 1.6;
        vA = 0.45 + 0.55 * (0.5 + 0.5 * sin(uTime * (0.4 + aSeed * 1.3) + aSeed * 40.0)); vGold = step(0.86, aSeed); }`,
    fragmentShader: `varying float vA; varying float vGold; void main() { float d = length(gl_PointCoord - 0.5); float a = smoothstep(0.5, 0.05, d) * vA;
      vec3 c = mix(vec3(0.91, 0.89, 1.0), vec3(1.0, 0.86, 0.6), vGold); gl_FragColor = vec4(c * a, a); }`,
    transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, fog: false });
  const pts = new THREE.Points(g, m); pts.frustumCulled = false; pts.renderOrder = 2; return pts;
}

/* candlelight warmer at night, cooler towards dawn (local time); moonlight stronger at night */
function nightInfo() {
  const h = new Date().getHours() + new Date().getMinutes() / 60;
  if (h >= 21 || h < 4.5) return { candle: PALETTE.candle, moon: 1, phase: "night" };
  if (h < 8) return { candle: 0xf8cc98, moon: .6, phase: "dawn" };
  if (h < 18) return { candle: 0xfad8ae, moon: .25, phase: "day" };
  return { candle: 0xf4b066, moon: .7, phase: "evening" };
}

/* the dome: the night-sky plate in an azimuthal projection (the zenith in the middle, the horizon on the inscribed
   circle) under a live shimmer along its Milky Way; its brightest stars twinkle. Before the plate arrives a gradient
   and the shimmer stand alone. The planets and the ecliptic ring are real meshes on top (setSky). */
function domeMaterial(THREE, clock) {
  return new THREE.ShaderMaterial({ side: THREE.BackSide,
    uniforms: { uTime: clock, tSky: { value: null }, uMix: { value: 0 } },
    vertexShader: "varying vec3 vDir; void main() { vDir = position; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }",
    fragmentShader: `uniform sampler2D tSky; uniform float uMix, uTime; varying vec3 vDir;
      float h(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
      float n(vec2 p) { vec2 i = floor(p), f = fract(p); f = f * f * (3.0 - 2.0 * f); return mix(mix(h(i), h(i + vec2(1, 0)), f.x), mix(h(i + vec2(0, 1)), h(i + vec2(1, 1)), f.x), f.y); }
      void main() { vec3 d = normalize(vDir); float th = acos(clamp(d.y, 0.0, 1.0)) / 1.5707963;
        vec2 uv = 0.5 + d.xz / max(1e-4, length(d.xz)) * th * 0.5;
        vec3 sky = texture2D(tSky, uv).rgb;
        vec3 col = mix(mix(vec3(0.043, 0.031, 0.125), vec3(0.11, 0.078, 0.26), th), sky * vec3(0.9, 0.88, 1.0), uMix);
        float b = dot(d, vec3(-0.7071, 0.0, -0.7071)), band = exp(-b * b / 0.035);   // the plate's band runs corner to corner
        float m = n(uv * 7.0 + vec2(uTime * 0.012, -uTime * 0.008)) * 0.6 + n(uv * 19.0 - uTime * 0.02) * 0.4;
        col += vec3(0.62, 0.5, 0.85) * band * m * mix(0.16, 0.07, uMix);
        vec3 star = max(sky - texture2D(tSky, uv, 3.0).rgb, 0.0);   // brighter than its surroundings: a star, not the band
        col += star * 0.6 * sin(uTime * 1.3 + h(floor(uv * 1024.0)) * 40.0) * uMix;
        col *= mix(0.75, 1.0, smoothstep(1.0, 0.72, th));   // deeper towards the rim, where the dome meets the walls
        gl_FragColor = vec4(col, 1.0); }`,
  });
}
/* the moon window: the landscape plate with a gentle parallax (it is far away: it slides a little against the frame)
   and the real moon, NASA's colour map on a sphere lit for today's phase (p = age / 29.53: 0 new, .5 full).
   size = the pane in metres; uCam = the camera in the window's own space (set every frame) */
function windowMaterial(THREE, p, illum, [w, h]) {
  return new THREE.ShaderMaterial({
    uniforms: { tView: { value: null }, tMoon: { value: null }, uMix: { value: 0 }, uMoonMix: { value: 0 }, uCam: { value: new THREE.Vector3(0, 1, 3) },
      uAspect: { value: w / h }, uSun: { value: new THREE.Vector3(Math.sin(p * TAU), 0, -Math.cos(p * TAU)) }, uIllum: { value: illum } },
    vertexShader: "varying vec2 vUv; varying vec3 vP; void main() { vUv = uv; vP = position; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }",
    fragmentShader: `uniform sampler2D tView, tMoon; uniform float uMix, uMoonMix, uIllum, uAspect; uniform vec3 uCam, uSun; varying vec2 vUv; varying vec3 vP;
      void main() { vec3 v = normalize(vP - uCam);
        vec2 par = clamp(v.xy / max(0.3, -v.z), -1.2, 1.2) * vec2(0.05, 0.03);
        vec2 sc = vec2(0.8, 0.8 * 0.7 / uAspect);   // the plate is 0.7 wide per 1 high: fill the pane without stretching
        vec2 uv = 0.5 + (vUv - 0.5) * sc + par;
        vec3 col = mix(mix(vec3(0.1, 0.125, 0.31), vec3(0.04, 0.063, 0.19), vUv.y), texture2D(tView, uv).rgb, uMix);
        vec2 q = (uv - vec2(0.66, 0.84)) * vec2(0.7, 1.0) / 0.05; float d = length(q);
        if (d < 1.0) { vec3 nr = vec3(q, sqrt(1.0 - d * d));
          vec2 mu = vec2(0.5 + atan(nr.x, nr.z) / 6.2831853, 0.5 + asin(nr.y) / 3.1415927);
          vec3 alb = mix(vec3(0.78, 0.78, 0.8), texture2D(tMoon, mu).rgb, uMoonMix);
          vec3 mc = alb * (smoothstep(-0.03, 0.12, dot(nr, uSun)) * 1.25 + 0.035);
          col = mix(col, mc, smoothstep(1.0, 0.95, d)); }
        else col += vec3(0.7, 0.76, 1.0) * uIllum * 0.16 * exp(-(d - 1.0) * 1.6);
        gl_FragColor = vec4(col, 1.0); }`,
  });
}

/* the crystal ball: glass with a gold rim, a slow inner mist; uTint/uFill colour it; uMist hides the depths */
export function sphereMaterial(THREE, clock) {
  return new THREE.ShaderMaterial({
    uniforms: { uTime: clock, uTint: { value: new THREE.Color(0x8b6cff) }, uFill: { value: 0 }, uMist: { value: 1 }, uFog: { value: 0 }, uMask: { value: null }, uUseMask: { value: 0 } },
    vertexShader: `varying vec3 vN; varying vec3 vV; varying vec3 vP; varying vec2 vUv;
      void main() { vUv = uv; vP = position; vN = normalize(normalMatrix * normal); vec4 mv = modelViewMatrix * vec4(position, 1.0); vV = normalize(-mv.xyz); gl_Position = projectionMatrix * mv; }`,
    fragmentShader: `uniform float uTime, uFill, uMist, uFog, uUseMask; uniform vec3 uTint; uniform sampler2D uMask; varying vec3 vN; varying vec3 vV; varying vec3 vP; varying vec2 vUv;
      float h(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
      float n(vec2 p) { vec2 i = floor(p), f = fract(p); f = f * f * (3.0 - 2.0 * f); return mix(mix(h(i), h(i + vec2(1, 0)), f.x), mix(h(i + vec2(0, 1)), h(i + vec2(1, 1)), f.x), f.y); }
      float fbm(vec2 p) { float s = 0.0, a = 0.5; for (int i = 0; i < 4; i++) { s += a * n(p); p *= 2.03; a *= 0.5; } return s; }
      void main() { float fr = pow(1.0 - max(dot(vN, vV), 0.0), 2.4);
        vec2 q = vP.xy * 7.0 + vec2(uTime * 0.07, -uTime * 0.05); float m = fbm(q + fbm(q * 1.7 + uTime * 0.04));
        vec3 deep = vec3(0.07, 0.05, 0.2); vec3 mist = vec3(0.78, 0.74, 0.95) * smoothstep(0.35, 0.85, m);
        float mask = mix(1.0, texture2D(uMask, vUv).a, clamp(uUseMask, 0.0, 1.0));   // alpha: wiped = transparent
        vec3 col = deep + mist * uMist * mask * 0.9 + vec3(0.62, 0.58, 0.78) * uFog * mask * (0.75 + 0.25 * m);   // the stage's milky fog
        col = mix(col, uTint * (0.55 + 0.45 * m), uFill * 0.85);
        col += vec3(1.0, 0.86, 0.55) * fr * 0.9 + uTint * fr * 0.35;
        float spec = pow(max(dot(reflect(-vV, vN), normalize(vec3(-0.4, 0.7, 0.6))), 0.0), 40.0);
        gl_FragColor = vec4(col + spec * 0.8, 0.92); }`,
    transparent: true,
  });
}
/* the aura mirror: dark silvered glass, a slow sheen; uAura (up to 3 colours) blooms inside when a reading comes */
export function mirrorMaterial(THREE, clock) {
  return new THREE.ShaderMaterial({
    uniforms: { uTime: clock, uBloom: { value: 0 }, uA: { value: new THREE.Color(0xe2bd6a) }, uB: { value: new THREE.Color(0x8b6cff) }, uC: { value: new THREE.Color(0x3fb8a8) } },
    vertexShader: `varying vec2 vUv; void main() { vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`,
    fragmentShader: `uniform float uTime, uBloom; uniform vec3 uA, uB, uC; varying vec2 vUv;
      void main() { vec2 p = vUv - 0.5; float d = length(p);
        vec3 base = mix(vec3(0.1, 0.1, 0.18), vec3(0.03, 0.03, 0.08), d * 1.6);
        float sheen = smoothstep(0.08, 0.0, abs(p.x + p.y * 0.6 - mod(uTime * 0.06, 1.6) + 0.8)) * 0.25;
        float a1 = smoothstep(0.5, 0.0, length(p - vec2(sin(uTime * 0.21) * 0.12, cos(uTime * 0.17) * 0.12 + 0.05)));
        float a2 = smoothstep(0.45, 0.0, length(p - vec2(cos(uTime * 0.13) * 0.15, -0.1 + sin(uTime * 0.19) * 0.1)));
        float a3 = smoothstep(0.4, 0.0, length(p - vec2(-0.1 + sin(uTime * 0.11) * 0.1, 0.12)));
        vec3 aura = (uA * a1 + uB * a2 * 0.8 + uC * a3 * 0.7) * uBloom;
        float rim = smoothstep(0.35, 0.5, d) * 0.25;
        gl_FragColor = vec4(base + aura + vec3(0.9, 0.85, 1.0) * sheen + vec3(0.4, 0.35, 0.6) * rim, 1.0); }`,
  });
}
