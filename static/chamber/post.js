/* Oracle chamber (FULL, High graphics): half-resolution bloom. The scene renders once into a 2x multisampled target (4x cost 20% of the frame rate on a mid GPU),
   its bright parts are thresholded and blurred at half size (two separable passes), and one full-screen pass adds
   them back. Every material writes display-ready colour (see the colour finish in full.js), so the target holds
   exactly what the screen would show and the composite adds light without any colour conversion.
   Medium graphics skip it: the glow sprites stand in for the bloom. */

export function makePost(THREE, renderer, { strength = .55, threshold = .6 } = {}) {
  const webgl2 = renderer.capabilities.isWebGL2;
  const scene = new THREE.WebGLRenderTarget(1, 1, { samples: webgl2 ? 2 : 0, depthBuffer: true, stencilBuffer: false });
  const half = [0, 1].map(() => new THREE.WebGLRenderTarget(1, 1, { depthBuffer: false, stencilBuffer: false }));
  const cam = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1);
  const quad = new THREE.Mesh(new THREE.PlaneGeometry(2, 2)); quad.frustumCulled = false;
  const fsScene = new THREE.Scene(); fsScene.add(quad);
  const vertexShader = "varying vec2 vUv; void main() { vUv = uv; gl_Position = vec4(position.xy, 0.0, 1.0); }";
  const texel = new THREE.Vector2();
  const shader = (uniforms, fragmentShader) => new THREE.ShaderMaterial({ uniforms, vertexShader, fragmentShader, depthTest: false, depthWrite: false });

  /* bright pass + 2x downsample in one: four bilinear taps cover the 4x4 source block */
  const bright = shader({ tSrc: { value: scene.texture }, uTexel: { value: texel }, uThr: { value: threshold } },
    `uniform sampler2D tSrc; uniform vec2 uTexel; uniform float uThr; varying vec2 vUv;
    vec3 tap(vec2 o) { vec3 c = texture2D(tSrc, vUv + o * uTexel).rgb; return c * smoothstep(uThr, uThr + 0.3, max(c.r, max(c.g, c.b))); }
    void main() { gl_FragColor = vec4((tap(vec2(-1.0, -1.0)) + tap(vec2(1.0, -1.0)) + tap(vec2(-1.0, 1.0)) + tap(vec2(1.0, 1.0))) * 0.25, 1.0); }`);
  /* 9-tap Gaussian in 5 fetches (linear sampling between texels) */
  const blur = shader({ tSrc: { value: null }, uDir: { value: new THREE.Vector2() } },
    `uniform sampler2D tSrc; uniform vec2 uDir; varying vec2 vUv;
    void main() { vec3 c = texture2D(tSrc, vUv).rgb * 0.227027;
      c += (texture2D(tSrc, vUv + uDir * 1.384615).rgb + texture2D(tSrc, vUv - uDir * 1.384615).rgb) * 0.316216;
      c += (texture2D(tSrc, vUv + uDir * 3.230769).rgb + texture2D(tSrc, vUv - uDir * 3.230769).rgb) * 0.070270;
      gl_FragColor = vec4(c, 1.0); }`);
  const comp = shader({ tScene: { value: scene.texture }, tBloom: { value: half[0].texture }, uStrength: { value: strength } },
    `uniform sampler2D tScene, tBloom; uniform float uStrength; varying vec2 vUv;
    void main() { vec3 c = texture2D(tScene, vUv).rgb, b = texture2D(tBloom, vUv).rgb * uStrength;
      gl_FragColor = vec4(c + b * (1.0 - c * 0.5), 1.0); }`);   // a soft add: highlights do not clip into flat white

  const pass = (mat, target) => { quad.material = mat; renderer.setRenderTarget(target); renderer.render(fsScene, cam); };
  function setSize(w, h) {   // drawing-buffer pixels
    scene.setSize(w, h);
    const hw = Math.max(1, w >> 1), hh = Math.max(1, h >> 1);
    half.forEach((t) => t.setSize(hw, hh));
    texel.set(1 / w, 1 / h);
  }
  const db = new THREE.Vector2();
  setSize(...renderer.getDrawingBufferSize(db).toArray());

  return {
    setSize,
    render(world, camera) {
      renderer.setRenderTarget(scene); renderer.render(world, camera);
      pass(bright, half[0]);
      const hw = half[0].width, hh = half[0].height;
      blur.uniforms.tSrc.value = half[0].texture; blur.uniforms.uDir.value.set(1 / hw, 0); pass(blur, half[1]);
      blur.uniforms.tSrc.value = half[1].texture; blur.uniforms.uDir.value.set(0, 1 / hh); pass(blur, half[0]);
      pass(comp, null);
    },
    dispose() { scene.dispose(); half.forEach((t) => t.dispose()); quad.geometry.dispose(); [bright, blur, comp].forEach((m) => m.dispose()); },
  };
}
