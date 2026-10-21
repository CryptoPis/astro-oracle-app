/* Oracle chamber (FULL tier): the room and its ten objects.
   The shell (stone faces, oak, moldings, pillars, sconces, drapes, the moon window) is built in shell.js; this module
   adds the dome, the lights and the ten objects. The photographic textures are loaded after the first frames
   (upgrade); until then small procedural textures stand in. The window and the dome are pre-rendered plates under live
   shaders (the real moon phase; procedural stars over the Milky Way; the planets and the ecliptic are meshes).
   Lights: a warm candle-coloured fill, the central candle (a downward spot), the oracle's candle and the moon (a spot through the
   window); the candelabras' pools are computed in the shell's shader. Shadows (centre and moon) are rendered once. */

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

export function buildRoom(THREE, B, X, F, { STEP, STATIONS, renderer, SH }) {
  const T = X.T, scene = new THREE.Scene();
  const night = nightInfo();
  scene.background = new THREE.Color(PALETTE.night);
  scene.fog = new THREE.FogExp2(PALETTE.haze, .045);

  const lam = (o) => new THREE.MeshLambertMaterial(o);
  const at = (m, x, y, z) => { m.position.set(x, y, z); return m; };

  /* ── the shell (shell.js): stone faces, oak, moldings, pillars, sconces, drapes, the moon window ── */
  const SC = SH.makeSconceUniforms(THREE);
  SC.uScCol.value.set(night.candle);
  const moonSlot = STATIONS.find((s) => s.id === "moon").slot;
  const shell = SH.buildShell(THREE, { scene, X, F, SC, renderer, STEP, WALL, moonSlot });
  /* the objects' materials: the metals and the dark wood are lit PBR with the room's environment, like the shell.
     (They were matcaps: a flat face turned to the eye sampled the matcap's hot centre and, after the colour finish's
     exposure, clipped to a white slab.) */
  const env = shell.env.texture;
  const mat = {
    wood: lam({ map: T.table, color: 0xe8d0b8 }),
    gold: shell.mats.gold,
    brass: new THREE.MeshStandardMaterial({ color: 0xb98d4c, metalness: .85, roughness: .42, envMap: env, envMapIntensity: 1.1 }),
    dark: new THREE.MeshStandardMaterial({ map: T.table, color: 0x9a7864, metalness: 0, roughness: .6, envMap: env, envMapIntensity: .35 }),
    ceramic: new THREE.MeshStandardMaterial({ color: 0xf2ece3, metalness: 0, roughness: .28, envMap: env, envMapIntensity: .7 }),   // porcelain
    hidden: new THREE.MeshBasicMaterial({ visible: false }),
  };
  const metal = [];   // (matcaps, tinted with the candlelight each frame: none left)
  const receivers = [...shell.receivers], casters = [...shell.casters];
  // the star dome: the night-sky plate seen from below under live stars (planets and the ecliptic are meshes, setSky)
  const domeMat = domeMaterial(THREE, F.clock);
  const dome = new THREE.Mesh(new THREE.SphereGeometry(6, 64, 20, 0, TAU, 0, Math.PI / 2), domeMat);
  dome.position.y = 4.2; scene.add(dome);

  /* ── lights: a faint haze, the central candle (decay 2, gone by 9 m), the moon as a spot through the window ── */
  // a warm low fill in the candles' own colour (not a neutral ambient): the room's light is candlelight everywhere
  let fill = .55; const ambient = new THREE.AmbientLight(night.candle, fill); scene.add(ambient);
  // the central candle hangs above the rug and lights downwards in a wide, soft cone: one 2D shadow map instead of a
  // point light's cube (the cube's lookups cost High 7 fps on a mid GPU), and the light fades towards the walls
  const central = new THREE.SpotLight(night.candle, 11, 9, 1.18, 1, 2); central.position.set(0, 3.1, 0); central.target.position.set(0, 0, 0); scene.add(central, central.target);
  const ma = moonSlot * STEP, toward = (r, y) => new THREE.Vector3(Math.sin(ma) * r, y, -Math.cos(ma) * r);
  const moonLight = new THREE.SpotLight(PALETTE.moon, 16 + night.moon * 26, 13, .48, .8, 2);
  moonLight.position.copy(toward(WALL + 2.4, 4.1)); moonLight.target.position.copy(toward(2.2, 0)); scene.add(moonLight, moonLight.target);
  moonLight.userData.base = moonLight.intensity;
  /* shadows (drawn once): the moon (both levels) and the central candle (High); soft PCF, see the shadow tint in full.js */
  { const s = moonLight.shadow; s.mapSize.set(1024, 1024); s.camera.near = .5; s.camera.far = 14; s.bias = -.0008; s.normalBias = .02; s.radius = 4; }
  { const s = central.shadow; s.mapSize.set(1024, 1024); s.camera.near = .3; s.camera.far = 9; s.bias = -.0012; s.normalBias = .03; s.radius = 6; }

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
    // the "new today" halo: not depth-tested (as a camera-facing quad it would cut a hard line through the table), and
    // it fades while its object is focused (room.focus)
    const newGlow = F.glow(T.glow, 0xffd27a, 1.3, 0); newGlow.position.copy(center); newGlow.material.depthTest = false;
    grp.add(newGlow);
    stations.set(id, { id, grp, center: grp.localToWorld(center.clone()), dist, hit, newGlow, isNew: false, ...extra });
  }
  const S = Object.fromEntries(STATIONS.map((s) => [s.id, s]));
  STATIONS.filter((s) => s.id !== "moon").forEach(medallion);   // the moon window needs no sign

  // 0 · tarot table: velvet cloth, the deck, a candle, the small box of revealed cards
  { const g = new THREE.Group();
    const top = new THREE.Mesh(new THREE.CylinderGeometry(.62, .62, .05, 40), mat.wood); top.position.y = .8; g.add(top);
    const cloth = new THREE.Mesh(new THREE.CylinderGeometry(.58, .58, .012, 48), shell.mats.velvet); cloth.position.y = .83; g.add(cloth);
    g.add(at(new THREE.Mesh(new THREE.CylinderGeometry(.07, .11, .78, 12), mat.dark), 0, .39, 0));
    g.add(at(new THREE.Mesh(new THREE.CylinderGeometry(.3, .36, .05, 24), mat.dark), 0, .025, 0));
    const side = lam({ color: 0xd8c9a6 }), back = lam({ color: 0x2a2060 });
    const deck = new THREE.Mesh(new THREE.BoxGeometry(.13, .04, .2), [side, side, back, side, side, side]); deck.position.set(0, .856, .02); g.add(deck);
    new THREE.TextureLoader().load(B.BACK_IMG, (tx) => { tx.colorSpace = THREE.SRGBColorSpace; back.map = tx; back.color.set(0xffffff); back.needsUpdate = true; });
    // the candle and the casket sit at the back corners, inside the portrait frame of the stage's view (half width ~.3 m)
    const c = F.candle(.14, .022); c.position.set(.25, .836, -.33); g.add(c);
    const casket = new THREE.Group(); casket.position.set(-.25, .836, -.3); casket.rotation.y = .35; g.add(casket);
    const rounded = (w, d, r) => { const s = new THREE.Shape(), x = w / 2 - r, z = d / 2 - r;
      s.absarc(x, z, r, 0, Math.PI / 2); s.absarc(-x, z, r, Math.PI / 2, Math.PI); s.absarc(-x, -z, r, Math.PI, Math.PI * 1.5); s.absarc(x, -z, r, Math.PI * 1.5, Math.PI * 2); return s; };
    const slab = (w, d, h, r, bevel) => new THREE.ExtrudeGeometry(rounded(w, d, r), { depth: h, bevelEnabled: true, bevelThickness: bevel, bevelSize: bevel, bevelSegments: 2, curveSegments: 6 }).rotateX(-Math.PI / 2);
    const box = new THREE.Mesh(slab(.17, .115, .05, .012, .004), mat.dark); box.position.y = .004; casket.add(box);
    const lid = new THREE.Mesh(slab(.178, .123, .012, .014, .005), mat.dark); lid.position.y = .06; casket.add(lid);
    casket.add(at(new THREE.Mesh(slab(.19, .135, .006, .016, .002), mat.gold), 0, .057, 0));                 // the gold band under the lid
    casket.add(at(new THREE.Mesh(slab(.1, .05, .003, .02, .002), mat.gold), 0, .078, 0));                    // an inlaid plate on the lid
    casket.add(at(new THREE.Mesh(new THREE.SphereGeometry(.009, 12, 8), mat.gold), 0, .084, 0));             // its stud
    casket.add(at(new THREE.Mesh(new THREE.BoxGeometry(.024, .03, .006), mat.gold), 0, .048, .062));         // the clasp
    for (const [x, z] of [[-.075, -.05], [.075, -.05], [-.075, .05], [.075, .05]]) casket.add(at(new THREE.Mesh(new THREE.SphereGeometry(.009, 10, 6), mat.gold), x, .004, z));   // ball feet
    place(g, S.tarot.slot, 2.7);
    register("tarot", g, new THREE.Vector3(0, .86, 0), 1.25, hitBox(1.3, .5, 1.3, .8), { deck, box: casket, lid, candle: c, stageDist: .36, stageRise: 2.4, stageOff: -.075 });
  }
  // 1 · crystal ball on a turned gold stand: a stepped plinth, a bead, a baluster stem with knops, a cup with a lip
  { const g = new THREE.Group();
    const prof = [[0, 0], [.215, 0], [.222, .012], [.222, .034], [.205, .046], [.19, .05], [.188, .066], [.165, .078], [.14, .082],   // plinth: two steps
      [.128, .094], [.132, .106], [.122, .118], [.09, .13], [.072, .16],                                                             // a bead, the foot rises
      [.058, .23], [.05, .32], [.062, .36], [.078, .38], [.062, .4], [.046, .44],                                                    // the lower knop
      [.042, .58], [.05, .62], [.072, .66], [.084, .7], [.072, .74], [.05, .77], [.044, .8],                                          // the baluster
      [.05, .84], [.068, .855], [.05, .87], [.046, .9],                                                                               // a ring under the cup
      [.07, .93], [.1, .96], [.122, .99], [.13, 1.01], [.124, 1.024], [.112, 1.018], [.09, 1.0], [0, .99]]                             // the cup, its rolled lip
      .map(([x, y]) => new THREE.Vector2(x, y));
    const stand = new THREE.Mesh(new THREE.LatheGeometry(prof, 48), shell.mats.gold); g.add(stand);
    for (const [y, r, t] of [[.38, .079, .008], [.7, .085, .007], [1.012, .127, .006]]) {   // bead rings on the knops and the lip
      const ring = new THREE.Mesh(new THREE.TorusGeometry(r, t, 8, 48), shell.mats.gold); ring.rotation.x = Math.PI / 2; ring.position.y = y; g.add(ring); }
    const ball = new THREE.Mesh(new THREE.SphereGeometry(.21, 64, 40), sphereMaterial(THREE, F.clock)); ball.position.y = 1.2; g.add(ball);
    const halo = F.glow(T.glowViolet, 0x8b6cff, .78, .16); halo.position.y = 1.2; g.add(halo);   // restrained: the glass carries the glow
    place(g, S.sphere.slot, 2.9);
    register("sphere", g, new THREE.Vector3(0, 1.18, 0), .95, hitBox(.6, 1.4, .6, .7), { ball, halo, stageDist: 1.3, stageRise: .1, stageOff: .07 });
  }
  // 2 · the moon window (shell.js builds it): the glass shows the landscape and the real moon; three candles on the sill
  { const g = shell.win, moon = B.moonNow();
    const pane = new THREE.Mesh(shell.paneGeo, windowMaterial(THREE, (moon.age_days || 0) / 29.53, (moon.illumination || 50) / 100, shell.paneGeo.userData.size)); g.add(pane);
    register("moon", g, new THREE.Vector3(0, 1.15, 0), 2.9, hitBox(1.8, 2.7, .6, 1.25), { ritual: shell.ritual, pane, stageDist: .85, stageRise: .02, stageOff: .1 });
    const from = toward(WALL - .3, 2.5), to = toward(1.6, 0);
    scene.add(F.beam(from, to, 1.1, 0xb0c0ff, .04 + night.moon * .06));
    const mid = from.clone().lerp(to, .5), box = new THREE.Box3(new THREE.Vector3(mid.x - 1.1, .2, mid.z - 1.1), new THREE.Vector3(mid.x + 1.1, 2.6, mid.z + 1.1));
    scene.add(F.dust(140, box, 0xd8e0ff, 9));
  }
  // 3 · the oracle's candle: a tall brass candlestick, a thick candle and the second candle light
  let flameLight;
  { const g = new THREE.Group();
    const prof = [[0, 0], [.17, 0], [.18, .03], [.06, .1], [.04, .5], [.07, .55], [.035, .62], [.035, .95], [.1, .98], [.11, 1.0]].map(([x, y]) => new THREE.Vector2(x, y));
    g.add(new THREE.Mesh(new THREE.LatheGeometry(prof, 24), mat.brass));
    const c = F.candle(.3, .055, 0xd9c7a6); c.position.y = 1.0; g.add(c);
    c.userData.flame.scale.set(1.5, 1.5, 1.5); c.userData.glow.scale.multiplyScalar(1.15); c.userData.glow.material.opacity = .4;
    flameLight = new THREE.PointLight(night.candle, 2.6, 5, 2); flameLight.position.set(0, 1.62, .32); g.add(flameLight);   // above and in front of the flame: it lights the room, not its own wax
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
    const ceramic2 = Object.assign(mat.ceramic.clone(), { side: THREE.DoubleSide });   // a lathe surface seen from above: both sides
    const saucer = new THREE.Mesh(new THREE.LatheGeometry([[0, 0], [.1, 0], [.13, .012], [.135, .018]].map(([x, y]) => new THREE.Vector2(x, y)), 32), ceramic2);
    saucer.position.y = .7; g.add(saucer);
    const cup = new THREE.Group(); cup.position.y = .712; g.add(cup);
    cup.add(new THREE.Mesh(new THREE.LatheGeometry([[0, 0], [.035, 0], [.05, .02], [.058, .06], [.06, .09], [.056, .09], [.054, .062], [.0, .062]].map(([x, y]) => new THREE.Vector2(x, y)), 32), ceramic2));
    const coffee = new THREE.Mesh(new THREE.CircleGeometry(.054, 24), lam({ color: 0x2a160c })); coffee.rotation.x = -Math.PI / 2; coffee.position.y = .07; cup.add(coffee);
    const handle = new THREE.Mesh(new THREE.TorusGeometry(.022, .006, 6, 16, Math.PI * 1.2), mat.ceramic); handle.position.set(.065, .05, 0); handle.rotation.z = -Math.PI * .6; cup.add(handle);
    place(g, S.coffee.slot, 2.8);
    register("coffee", g, new THREE.Vector3(0, .76, 0), .75, hitBox(.6, .5, .6, .7), { cup, coffee, stageDist: .7, stageRise: 1.2, stageOff: .02 });
  }
  // 9 · the gift chest: a bevelled oak body on a plinth, a domed lid on a hinge, gilded bands with rivets, corner
  // guards, an ornate lock plate with a keyhole; inside, a warm glow and soft god rays that rise when it opens
  { const g = new THREE.Group(), Wc = .52, Dc = .34, Hc = .27, R = .15;   // width, depth, body height, lid rise
    const oak = new THREE.MeshStandardMaterial({ map: T.table, color: 0xb88f6c, roughness: .58, metalness: 0, envMap: env, envMapIntensity: .3 });
    const iron = new THREE.MeshStandardMaterial({ color: 0xa47c3e, metalness: .9, roughness: .38, envMap: env, envMapIntensity: 1.2 });   // gilded iron, darker than the lock
    const rr = (w, h, r) => { const s = new THREE.Shape(), x = w / 2 - r, y = h / 2 - r;
      s.absarc(x, y, r, 0, Math.PI / 2); s.absarc(-x, y, r, Math.PI / 2, Math.PI); s.absarc(-x, -y, r, Math.PI, Math.PI * 1.5); s.absarc(x, -y, r, Math.PI * 1.5, Math.PI * 2); return s; };
    // the body: a rounded-corner block (bevelled), on a slightly wider plinth
    const bodyG = new THREE.ExtrudeGeometry(rr(Wc - .02, Dc - .02, .02), { depth: Hc - .02, bevelEnabled: true, bevelThickness: .01, bevelSize: .01, bevelSegments: 2, curveSegments: 4 }).rotateX(-Math.PI / 2).translate(0, .01, 0);
    const body = new THREE.Mesh(bodyG, oak); g.add(body);
    g.add(new THREE.Mesh(new THREE.ExtrudeGeometry(rr(Wc + .03, Dc + .03, .02), { depth: .03, bevelEnabled: true, bevelThickness: .006, bevelSize: .006, bevelSegments: 1, curveSegments: 4 }).rotateX(-Math.PI / 2).translate(0, .006, 0), oak));
    // the lid: an arch (half an ellipse over the depth) extruded across the width: closed, so it never vanishes when open
    const arch = (d, h, n = 20) => { const s = new THREE.Shape(); s.moveTo(-d / 2, 0); for (let i = 1; i <= n; i++) { const a = Math.PI - i / n * Math.PI; s.lineTo(Math.cos(a) * d / 2, Math.sin(a) * h); } s.lineTo(-d / 2, 0); return s; };
    const archPts = (d, h, n = 24) => Array.from({ length: n + 1 }, (_, i) => { const a = Math.PI - i / n * Math.PI; return [Math.cos(a) * d / 2, Math.sin(a) * h]; });
    const lid = new THREE.Group(); lid.position.set(0, Hc, -Dc / 2); g.add(lid);
    const lidG = new THREE.ExtrudeGeometry(arch(Dc, R), { depth: Wc, bevelEnabled: true, bevelThickness: .008, bevelSize: .008, bevelSegments: 2, curveSegments: 4 })
      .rotateY(Math.PI / 2).translate(-Wc / 2, 0, Dc / 2);   // the arch's x runs along the depth; the hinge is at the back edge (z = 0)
    const lidMesh = new THREE.Mesh(lidG, oak); lid.add(lidMesh);
    const lining = new THREE.Mesh(new THREE.PlaneGeometry(Wc - .04, Dc - .04).rotateX(Math.PI / 2), shell.mats.velvet); lining.position.set(0, -.0095, Dc / 2); lid.add(lining);   // violet velvet under the lid (below the bevel)
    // bands: over the lid (a tube along the arch) and down the body (front, under, back), with rivets
    const rivets = [];
    for (const x of [-.165, .165]) {
      const curve = new THREE.CatmullRomCurve3(archPts(Dc + .022, R + .011).map(([z, y]) => new THREE.Vector3(x, y, z + Dc / 2)));
      lid.add(new THREE.Mesh(new THREE.TubeGeometry(curve, 32, .009, 6), iron));
      for (const z of [Dc / 2 + .007, -Dc / 2 - .007]) { const b = new THREE.Mesh(new THREE.BoxGeometry(.04, Hc + .01, .008), iron); b.position.set(x, Hc / 2 + .006, z); g.add(b); }
      for (let i = 0; i < 4; i++) { rivets.push([x - .012, .04 + i * .065, Dc / 2 + .012], [x + .012, .04 + i * .065, Dc / 2 + .012]); }
      for (let i = 1; i < 6; i++) { const [z, y] = archPts(Dc + .03, R + .016, 6)[i]; rivets.push([x, y + Hc, z, true]); }
    }
    // corner guards: small gilded brackets on the four upright edges
    for (const sx of [-1, 1]) for (const sz of [-1, 1]) { const cg = new THREE.Mesh(new THREE.BoxGeometry(.03, Hc - .04, .03), iron); cg.position.set(sx * (Wc / 2 - .004), Hc / 2 + .01, sz * (Dc / 2 - .004)); g.add(cg); }
    { const rg = new THREE.SphereGeometry(.0065, 8, 6), im = new THREE.InstancedMesh(rg, mat.gold, rivets.length), m4 = new THREE.Matrix4(), body0 = [], lid0 = [];
      rivets.forEach((r) => (r[3] ? lid0 : body0).push(r));
      body0.forEach(([x, y, z], i) => im.setMatrixAt(i, m4.makeTranslation(x, y, z))); im.count = body0.length; g.add(im);
      const il = new THREE.InstancedMesh(rg, mat.gold, lid0.length); lid0.forEach(([x, y, z], i) => il.setMatrixAt(i, m4.makeTranslation(x, y - Hc, z + Dc / 2))); lid.add(il); }
    // the lock: an ornate plate (a shield with a scalloped top) and a keyhole cut through it, the hasp on the lid
    const shield = new THREE.Shape(); { const w = .042, h = .07; shield.moveTo(-w, h * .4);
      shield.quadraticCurveTo(-w * .55, h * .62, 0, h * .5); shield.quadraticCurveTo(w * .55, h * .62, w, h * .4);
      shield.lineTo(w, -h * .05); shield.quadraticCurveTo(w * .9, -h * .45, 0, -h * .62); shield.quadraticCurveTo(-w * .9, -h * .45, -w, -h * .05); shield.lineTo(-w, h * .4); }
    const hole = new THREE.Path(); hole.absarc(0, .012, .0085, -1.08, Math.PI + 1.08, false); hole.lineTo(-.008, -.02); hole.lineTo(.008, -.02); hole.closePath();   // one keyhole outline: the round head, the tapering slot
    shield.holes.push(hole);
    const lock = new THREE.Mesh(new THREE.ExtrudeGeometry(shield, { depth: .008, bevelEnabled: true, bevelThickness: .003, bevelSize: .003, bevelSegments: 2, curveSegments: 10 }), mat.gold);
    lock.position.set(0, Hc - .05, Dc / 2 + .006); g.add(lock);
    const keyhole = new THREE.Mesh(new THREE.PlaneGeometry(.03, .04), new THREE.MeshBasicMaterial({ color: 0x0a0604 })); keyhole.position.set(0, Hc - .05, Dc / 2 + .0055); g.add(keyhole);
    const hasp = new THREE.Mesh(new THREE.BoxGeometry(.03, .045, .008), mat.gold); hasp.position.set(0, .02, Dc + .008); lid.add(hasp);
    // inside: a warm glow over the opening (seen when the lid lifts), and the rays
    const glowMat = new THREE.ShaderMaterial({ uniforms: { uOpen: { value: 0 }, uTime: F.clock }, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
      vertexShader: "varying vec2 vUv; void main() { vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }",
      fragmentShader: `uniform float uOpen, uTime; varying vec2 vUv; void main() { vec2 q = (vUv - 0.5) * vec2(1.0, 1.5); float a = exp(-dot(q, q) * 7.0) * uOpen * (0.9 + 0.1 * sin(uTime * 2.3));
        gl_FragColor = vec4(vec3(1.0, 0.78, 0.42) * a, a); }` });
    // the opening: a dark cavity and the glow over it, just above the body's top (the closed lid covers both)
    const cavity = new THREE.Mesh(new THREE.PlaneGeometry(Wc - .05, Dc - .05).rotateX(-Math.PI / 2), new THREE.MeshBasicMaterial({ color: 0x140b06 })); cavity.position.y = Hc + .0015; g.add(cavity);
    const mouth = new THREE.Mesh(new THREE.PlaneGeometry(Wc - .05, Dc - .05).rotateX(-Math.PI / 2), glowMat); mouth.position.y = Hc + .003; mouth.renderOrder = 3; g.add(mouth);
    /* god rays: twelve soft shafts in a fan rising from the opening, additive, gradient along and across each shaft
       (no hard edges), turning very slowly; one draw */
    const rays = new THREE.Group(); rays.position.y = Hc; g.add(rays);
    { const n = 12, geos = [];
      for (let i = 0; i < n; i++) { const pg = new THREE.PlaneGeometry(.12 + (i % 3) * .035, 1.15, 1, 1).translate(0, .575, 0), a = (i / n) * Math.PI * 2;
        pg.rotateZ((((i * 7) % n) / n - .5) * .7).rotateY(a); const s = new Float32Array(pg.attributes.position.count).fill(i / n); pg.setAttribute("aSeed", new THREE.BufferAttribute(s, 1)); geos.push(pg); }
      const geo = new THREE.BufferGeometry(), parts = geos.map((x) => x.toNonIndexed());
      for (const [name, size] of [["position", 3], ["uv", 2], ["aSeed", 1]]) { const arr = new Float32Array(parts.reduce((s, x) => s + x.attributes[name].array.length, 0)); let o = 0;
        for (const x of parts) { arr.set(x.attributes[name].array, o); o += x.attributes[name].array.length; } geo.setAttribute(name, new THREE.BufferAttribute(arr, size)); }
      geos.forEach((x) => x.dispose()); parts.forEach((x) => x.dispose());
      const rm = new THREE.ShaderMaterial({ uniforms: { uOpen: glowMat.uniforms.uOpen, uTime: F.clock }, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, side: THREE.DoubleSide,
        vertexShader: "attribute float aSeed; varying vec2 vUv; varying float vSeed; void main() { vUv = uv; vSeed = aSeed; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }",
        fragmentShader: `uniform float uOpen, uTime; varying vec2 vUv; varying float vSeed;
          void main() { float across = sin(vUv.x * 3.14159); across *= across;
            float along = smoothstep(0.0, 0.08, vUv.y) * pow(1.0 - vUv.y, 1.6);
            float pulse = 0.6 + 0.4 * sin(uTime * (0.7 + vSeed) + vSeed * 20.0);
            float a = across * along * pulse * uOpen * 0.34; gl_FragColor = vec4(vec3(1.0, 0.82, 0.5) * a, a); }` });
      const mesh = new THREE.Mesh(geo, rm); mesh.renderOrder = 6; mesh.frustumCulled = false; rays.add(mesh); rays.userData.mesh = mesh; }
    const inner = F.glow(T.glow, 0xffd27a, .7, 0); inner.position.set(0, Hc + .06, 0); g.add(inner);
    place(g, S.gift.slot, 2.8);
    register("gift", g, new THREE.Vector3(0, .3, 0), 1.05, hitBox(.7, .7, .55, .3), { lid, inner, body, rays, open: glowMat.uniforms.uOpen, stageDist: 1.0, stageRise: .7, stageOff: -.05 });
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
  if (birthday) { ambient.color.set(0xffc060); fill = .8; central.intensity *= 1.25; scene.add(F.dust(160, new THREE.Box3(new THREE.Vector3(-4, .2, -4), new THREE.Vector3(4, 3.8, 4)), 0xffd27a, 10)); }

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
  let tNow = 0, focusId = null; const clockNow = () => tNow;

  /* ── every frame ── */
  const flick = (t, s) => .82 + Math.sin(t * 7.1 + s) * .06 + Math.sin(t * 13.3 + s * 3) * .05 + Math.sin(t * 2.3 + s * 5) * .07;
  const tint = new THREE.Color();
  let busy = 0, busyBook = false;
  /* ── graphics levels: shadows (rendered once) and the photographic textures, loaded after the first frames ── */
  function setShadows(level) {   // "high": moon + central candle; "medium": the moon only
    moonLight.castShadow = true; shell.setLevel(level);
    const want = level === "high";
    if (central.castShadow !== want) { central.castShadow = want; if (!want && central.shadow.map) { central.shadow.map.dispose(); central.shadow.map = null; } }
  }
  const queue = [], fades = [];
  const pane = stations.get("moon").pane.material;
  /* the photographic set per level (High mixes sizes: near surfaces 1024, the rug and velvet 768; the normal maps,
     the sky and the moon are the same files for both levels) */
  const LEVEL = { high: { stone: 1024, floor: 1024, rug: 768, velvet: 768, normals: 512, window: 1024, sky: 512 },
    medium: { stone: 512, floor: 512, rug: 512, velvet: 512, normals: 512, window: 512, sky: 512 } };
  function upgrade(level, prepare) {   // resolves (with the failures, if any) when every image is applied; one swap per frame
    const L = LEVEL[level];
    const swap = (p, apply) => p.then((t) => new Promise((done) => queue.push(() => { apply(t); if (prepare) prepare(t); done(); })));
    // the materials keep their texture slots from the start (stand-ins), so a swap never recompiles a shader
    const albedo = (set) => swap(X.load(`${set}_${L[set]}`, { srgb: true }), (t) => { t.wrapS = t.wrapT = THREE.RepeatWrapping;
      const old = shell.sets[set][0].map; for (const m of shell.sets[set]) { m.map = t; if (m.bumpMap) m.bumpMap = t; } X.release(old); });
    const normal = (set) => swap(X.load(`${set}_n_${L.normals}`, { srgb: false }), (t) => { t.wrapS = t.wrapT = THREE.RepeatWrapping;
      for (const m of shell.sets[set]) if (!m.userData.keepNormal) m.normalMap = t; });   // the window frame keeps its carving
    // a plate under a shader: raw colour (the shaders write display colour), faded in
    const plate = (file, u, fade) => swap(X.load(file, { srgb: false }), (t) => { if (file.startsWith("moon")) t.wrapS = THREE.RepeatWrapping; u.value = t; fades.push(fade); });
    const jobs = [albedo("stone"), albedo("floor"), normal("stone"), normal("floor"), albedo("rug"), albedo("velvet"),
      plate(`window_${L.window}`, pane.uniforms.tView, pane.uniforms.uMix), plate(`moon_${L.sky}`, pane.uniforms.tMoon, pane.uniforms.uMoonMix),
      plate(`dome_${L.sky}`, domeMat.uniforms.tSky, domeMat.uniforms.uMix)];
    return Promise.allSettled(jobs).then((r) => r.filter((x) => x.status === "rejected").map((x) => String(x.reason)));
  }

  function update(t, dt, camera) {
    F.clock.value = t;
    if (queue.length) queue.shift()();
    for (let i = fades.length - 1; i >= 0; i--) { const u = fades[i]; u.value = Math.min(1, u.value + dt * 1.6); if (u.value >= 1) fades.splice(i, 1); }
    { const st = stations.get("moon"); st.grp.worldToLocal(pane.uniforms.uCam.value.copy(camera.position)); }
    { const b = stations.get("sphere").ball; b.worldToLocal(b.material.uniforms.uCam.value.copy(camera.position)); }
    const k = flick(t, 0), kf = flick(t * (1 + busy * .9), 2.1) * (1 + busy * .35);
    central.intensity = 11 * k * (birthday ? 1.25 : 1); flameLight.intensity = 2.6 * kf;
    tint.setRGB(.75 + k * .3, .7 + k * .28, .68 + k * .25); for (const m of metal) m.color.copy(tint);
    shell.update(t, dt, camera); ambient.intensity = fill * k;
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
    for (const s of stations.values()) if (s.newGlow) { const want = s.isNew && focusId !== s.id ? .3 + .22 * Math.sin(t * 1.6 + s.grp.position.x) : 0; s.newGlow.material.opacity += (want - s.newGlow.material.opacity) * Math.min(1, dt * 3); }
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
    focus(id) { focusId = id; },
    setBusy(on, path) { busy = on ? 1 : 0; busyBook = !!(on && path && path.startsWith("/api/dreams")); }, react, mat };
}

/* candlelight warmer at night, cooler towards dawn (local time); moonlight stronger at night */
function nightInfo() {
  const h = new Date().getHours() + new Date().getMinutes() / 60;
  if (h >= 21 || h < 4.5) return { candle: PALETTE.candle, moon: 1, phase: "night" };
  if (h < 8) return { candle: 0xf8cc98, moon: .6, phase: "dawn" };
  if (h < 18) return { candle: 0xfad8ae, moon: .25, phase: "day" };
  return { candle: 0xf4b066, moon: .7, phase: "evening" };
}

/* the dome: the night-sky plate in an azimuthal projection over a cap of about 50 degrees round the zenith (so a view
   up holds most of it: stars stay small), blurred and desaturated into a subtle Milky Way over the night palette
   (#121423); towards the rim a procedural band continues it. Over everything, crisp procedural stars: three layers of
   cells, one star at most per cell, varied size and colour, anti-aliased to the pixel, a slow twinkle. The planets
   and the ecliptic ring are real meshes on top (setSky). */
function domeMaterial(THREE, clock) {
  return new THREE.ShaderMaterial({ side: THREE.BackSide,
    uniforms: { uTime: clock, tSky: { value: null }, uMix: { value: 0 } }, extensions: { derivatives: true },
    vertexShader: "varying vec3 vDir; void main() { vDir = position; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }",
    fragmentShader: `uniform sampler2D tSky; uniform float uMix, uTime; varying vec3 vDir;
      float h(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
      vec2 h2(vec2 p) { return fract(sin(vec2(dot(p, vec2(127.1, 311.7)), dot(p, vec2(269.5, 183.3)))) * 43758.5453); }
      float n(vec2 p) { vec2 i = floor(p), f = fract(p); f = f * f * (3.0 - 2.0 * f); return mix(mix(h(i), h(i + vec2(1, 0)), f.x), mix(h(i + vec2(0, 1)), h(i + vec2(1, 1)), f.x), f.y); }
      vec3 stars(vec2 p, float dens, float prob, float size, float seed) {
        vec2 c = p * dens, id = floor(c), f = fract(c) - 0.5; float r = h(id + seed);
        if (r > prob) return vec3(0.0);
        vec2 o = (h2(id + seed * 1.7) - 0.5) * 0.7; float rad = size * (0.35 + 0.65 * h(id + seed * 3.1));
        float px = max(fwidth(c.x), fwidth(c.y)), d = length(f - o);
        float a = (1.0 - smoothstep(max(rad - px, 0.0), rad + px, d)) * min(1.0, rad / px);   // a sub-pixel star spreads over one pixel, dimmer
        a *= 1.0 - smoothstep(0.12, 0.35, px);   // a layer whose cells are smaller than a few pixels would alias: fade it
        float tw = 0.78 + 0.22 * sin(uTime * (0.6 + 2.0 * h(id + 9.0)) + r * 60.0);
        float c2 = h(id + seed * 5.3);
        vec3 col = c2 < 0.25 ? vec3(0.55, 0.72, 1.0) : c2 > 0.78 ? vec3(1.0, 0.76, 0.48) : vec3(0.86, 0.9, 1.0);
        return col * a * tw * (0.55 + 0.75 * h(id + 4.0)); }
      void main() { vec3 d = normalize(vDir); float th = acos(clamp(d.y, 0.0, 1.0)) / 1.5707963;
        vec2 p = d.xz / max(1e-4, length(d.xz)) * th;               // 0 at the zenith, 1 at the rim
        vec2 uv = 0.5 + p / 0.56 * 0.5;                              // the plate spans th < 0.56
        vec3 sky = texture2D(tSky, uv, 1.5).rgb;                     // blurred: the plate gives the band, not the stars
        float l = dot(sky, vec3(0.2126, 0.7152, 0.0722));
        sky = mix(vec3(l), sky, 0.85) * vec3(1.04, 0.84, 1.16);       // purple, as in the reference dome
        sky += vec3(1.0, 0.6, 0.42) * smoothstep(0.22, 0.55, l) * 0.35;  // a warm pink-amber in the bright core
        vec3 base = vec3(0.071, 0.078, 0.137);                       // #121423
        float inCap = (1.0 - smoothstep(0.44, 0.56, th)) * uMix;
        float b = dot(d, vec3(-0.7071, 0.0, -0.7071)), band = exp(-b * b / 0.03) * (0.6 + 0.4 * n(p * 6.0 + uTime * 0.01));
        vec3 col = base + vec3(0.14, 0.09, 0.2) * band * (1.0 - inCap) + max(sky - base * 0.6, 0.0) * 0.95 * inCap;
        col += stars(p, 22.0, 0.4, 0.095, 1.0) * 1.7 + stars(p, 48.0, 0.55, 0.1, 7.0) * 1.0 + stars(p, 100.0, 0.65, 0.085, 13.0) * 0.7 + stars(p, 190.0, 0.7, 0.08, 19.0) * 0.45;
        col *= mix(0.62, 1.0, (1.0 - smoothstep(0.72, 1.0, th)));             // deeper towards the rim, where the dome meets the walls
        gl_FragColor = vec4(col, 1.0); }`,
  });
}
/* the moon window: the landscape plate with a gentle parallax (it is far away: it slides a little against the frame)
   and the real moon, NASA's colour map on a sphere lit for today's phase (p = age / 29.53: 0 new, .5 full).
   size = the pane in metres; uCam = the camera in the window's own space (set every frame) */
function windowMaterial(THREE, p, illum, [w, h]) {
  return new THREE.ShaderMaterial({
    uniforms: { tView: { value: null }, tMoon: { value: null }, uMix: { value: 0 }, uMoonMix: { value: 0 }, uCam: { value: new THREE.Vector3(0, 1, 3) },
      uAspect: { value: w / h }, uSun: { value: new THREE.Vector3(Math.sin(p * TAU), 0, -Math.cos(p * TAU)) }, uIllum: { value: illum },
      uMoonUv: { value: new THREE.Vector2(.745, .6) } },   // in the right-hand light, below the tracery
    vertexShader: "varying vec2 vUv; varying vec3 vP; void main() { vUv = uv; vP = position; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }",
    fragmentShader: `uniform sampler2D tView, tMoon; uniform float uMix, uMoonMix, uIllum, uAspect; uniform vec3 uCam, uSun; uniform vec2 uMoonUv; varying vec2 vUv; varying vec3 vP;
      void main() { vec3 v = normalize(vP - uCam);
        vec2 par = clamp(v.xy / max(0.3, -v.z), -1.2, 1.2) * vec2(0.05, 0.03);
        vec2 sc = vec2(0.8, 0.8 * 0.7 / uAspect);   // the plate is 0.7 wide per 1 high: fill the pane without stretching
        vec2 uv = 0.5 + (vUv - 0.5) * sc + par;
        vec3 col = mix(mix(vec3(0.1, 0.125, 0.31), vec3(0.04, 0.063, 0.19), vUv.y), texture2D(tView, uv).rgb, uMix);
        vec2 q = (uv - (0.5 + (uMoonUv - 0.5) * sc)) * vec2(0.7, 1.0) / 0.084; float d = length(q);
        if (d < 1.0) { vec3 nr = vec3(q, sqrt(1.0 - d * d));
          vec2 mu = vec2(0.5 + atan(nr.x, nr.z) / 6.2831853, 0.5 + asin(nr.y) / 3.1415927);
          vec3 alb = mix(vec3(0.78, 0.78, 0.8), texture2D(tMoon, mu).rgb, uMoonMix);
          vec3 mc = alb * (smoothstep(-0.03, 0.12, dot(nr, uSun)) * 1.7 + 0.05);
          col = mix(col, mc, (1.0 - smoothstep(0.95, 1.0, d))); }
        else col += vec3(0.7, 0.76, 1.0) * (0.12 + uIllum * 0.3) * exp(-(d - 1.0) * 1.1);   // a soft halo
        // the glass: a faint warm reflection of the room's candles, stronger at a grazing look, and one soft streak
        float fres = pow(1.0 - clamp(-v.z, 0.0, 1.0), 3.0);
        float streak = (1.0 - smoothstep(0.0, 0.06, abs(vUv.x * 0.9 + vUv.y * 0.45 - 0.62))) * 0.5 + (1.0 - smoothstep(0.0, 0.025, abs(vUv.x * 0.9 + vUv.y * 0.45 - 0.74))) * 0.35;
        col += vec3(1.0, 0.78, 0.5) * (0.035 + 0.22 * fres) + vec3(0.85, 0.85, 1.0) * streak * 0.045;
        gl_FragColor = vec4(col, 1.0); }`,
  });
}

/* the crystal ball: dark violet glass with a swirling nebula inside. The view ray is refracted into the ball and
   the nebula sampled at three depths along it (real parallax: the swirl sits inside, not on the surface), a soft
   fresnel rim, two small window highlights. Everything is mixed (never added past 1) and passed through a soft
   shoulder, so the ball keeps its depth under the bloom: only the highlights cross its threshold.
   uTint/uFill colour the nebula with the answer; uMist/uFog veil it (the stage's mist, wiped through uMask);
   uCam = the camera in the ball's own space (room.update) */
export function sphereMaterial(THREE, clock) {
  return new THREE.ShaderMaterial({
    uniforms: { uTime: clock, uTint: { value: new THREE.Color(0x8b6cff) }, uFill: { value: 0 }, uMist: { value: 1 }, uFog: { value: 0 }, uMask: { value: null }, uUseMask: { value: 0 },
      uCam: { value: new THREE.Vector3(0, 0, 3) }, uR: { value: .21 } },
    vertexShader: `varying vec3 vP; varying vec2 vUv; void main() { vUv = uv; vP = position; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`,
    fragmentShader: `uniform float uTime, uFill, uMist, uFog, uUseMask, uR; uniform vec3 uTint, uCam; uniform sampler2D uMask; varying vec3 vP; varying vec2 vUv;
      float h(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
      float n(vec2 p) { vec2 i = floor(p), f = fract(p); f = f * f * (3.0 - 2.0 * f); return mix(mix(h(i), h(i + vec2(1, 0)), f.x), mix(h(i + vec2(0, 1)), h(i + vec2(1, 1)), f.x), f.y); }
      float fbm(vec2 p) { return n(p) * 0.55 + n(p * 2.07 + 5.3) * 0.28 + n(p * 4.3 + 1.7) * 0.17; }
      /* the nebula at a point inside (q in units of the radius): arms wound round the vertical axis, turning slowly */
      vec2 nebula(vec3 q) {
        float r = length(q.xz), a = uTime * 0.12 + (1.0 - r) * 2.4 + q.y * 0.8, c = cos(a), s = sin(a);   // a whirl: the centre turns most
        vec2 p = mat2(c, s, -s, c) * q.xz * 1.7 + vec2(q.y * 0.9, q.y * 0.5);
        float d = fbm(p + fbm(p * 1.9 + uTime * 0.05) * 0.9);
        float body = 1.0 - smoothstep(0.45, 1.05, length(q * vec3(1.0, 1.25, 1.0)));   // a flattened cloud, clear near the glass
        return vec2(smoothstep(0.32, 0.72, d) * body, d); }
      void main() {
        vec3 N = normalize(vP), V = normalize(vP - uCam);   // V: the view ray, from the eye into the ball
        float ndv = clamp(dot(N, -V), 0.0, 1.0), fr = pow(1.0 - ndv, 3.0);
        vec3 R = refract(V, N, 0.68); float chord = max(-2.0 * dot(vP, R), 0.0);
        vec3 deep = mix(vec3(0.028, 0.018, 0.075), vec3(0.075, 0.045, 0.16), ndv);   // darker towards the rim: a thick glass
        vec3 tint = mix(vec3(0.5, 0.34, 1.0), uTint, uFill), rose = mix(vec3(0.92, 0.42, 0.86), uTint, uFill * 0.6), warm = vec3(1.0, 0.74, 0.42);
        vec3 col = deep; float m = 0.0;
        for (int i = 0; i < 3; i++) { vec3 q = (vP + R * chord * (0.2 + 0.3 * float(i))) / uR; vec2 s = nebula(q); m += s.y;
          vec3 c = mix(mix(tint, rose, smoothstep(0.45, 0.7, s.y)) * 0.8, warm * 1.05, smoothstep(0.55, 1.0, s.x));   // violet, rose, a gold heart
          col = mix(col, c, s.x * (0.78 - 0.14 * float(i))); }
        m /= 3.0;
        float mask = mix(1.0, texture2D(uMask, vUv).a, clamp(uUseMask, 0.0, 1.0));   // alpha: wiped = clear
        vec3 milk = mix(vec3(0.42, 0.36, 0.62), vec3(0.74, 0.7, 0.88), smoothstep(0.3, 0.75, m));   // the mist keeps the swirl's shape
        col = mix(col, milk, clamp(uFog * mask * (0.42 + 0.3 * smoothstep(0.35, 0.7, m)) + uMist * mask * 0.08 * smoothstep(0.4, 0.8, m), 0.0, 0.75));   // the veil, mixed in
        col = mix(col, vec3(0.62, 0.5, 1.0) * 0.5 + warm * 0.3, fr * 0.55);   // the rim: violet-gold, soft
        col = col / (1.0 + col * 0.55);   // a soft shoulder: the ball never flattens to white
        vec3 L1 = normalize(vec3(-0.45, 0.62, 0.64)), L2 = normalize(vec3(0.5, 0.3, 0.8)), Rf = reflect(V, N);
        col += warm * pow(max(dot(Rf, L1), 0.0), 90.0) * 0.9 + vec3(0.8, 0.85, 1.0) * pow(max(dot(Rf, L2), 0.0), 220.0) * 0.45;
        gl_FragColor = vec4(col, 0.96); }`,
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
