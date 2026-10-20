/* Oracle chamber: sound, generated with the Web Audio API (no audio files). Off by default; starts only after a
   user gesture; fades out when the app is hidden; asks iOS for the "ambient" session so the mute switch is respected.
   Ambience: a low drone, distant chimes, a faint candle crackle. Effects: shuffle, flip, pick, wipe, chest, reveal. */

export function createSound() {
  let ctx = null, master = null, verb = null, on = false, timers = [], noise = null, lastWipe = 0;
  const now = () => ctx.currentTime;

  function init() {
    if (ctx) return;
    try { if (navigator.audioSession) navigator.audioSession.type = "ambient"; } catch {}
    ctx = new (window.AudioContext || window.webkitAudioContext)();
    master = ctx.createGain(); master.gain.value = 0; master.connect(ctx.destination);
    // a soft echo for the chimes
    verb = ctx.createDelay(1); verb.delayTime.value = .33; const fb = ctx.createGain(); fb.gain.value = .32; const wet = ctx.createGain(); wet.gain.value = .35;
    verb.connect(fb); fb.connect(verb); verb.connect(wet); wet.connect(master);
    noise = ctx.createBuffer(1, ctx.sampleRate, ctx.sampleRate); const d = noise.getChannelData(0); for (let i = 0; i < d.length; i++) d[i] = Math.random() * 2 - 1;
  }
  function drone() {
    const lp = ctx.createBiquadFilter(); lp.type = "lowpass"; lp.frequency.value = 380; lp.Q.value = .7;
    const g = ctx.createGain(); g.gain.value = .07; lp.connect(g); g.connect(master);
    const oscs = [[55, "sine", 0], [82.6, "triangle", -6], [110.2, "sine", 4]].map(([f, type, det]) => { const o = ctx.createOscillator(); o.type = type; o.frequency.value = f; o.detune.value = det; o.connect(lp); o.start(); return o; });
    const lfo = ctx.createOscillator(), lg = ctx.createGain(); lfo.frequency.value = .05; lg.gain.value = 140; lfo.connect(lg); lg.connect(lp.frequency); lfo.start();
    return () => { oscs.forEach((o) => o.stop()); lfo.stop(); g.disconnect(); };
  }
  function tone(freq, { dur = 2.8, gain = .04, type = "sine", at = 0, echo = true } = {}) {
    const o = ctx.createOscillator(), g = ctx.createGain(), t = now() + at; o.type = type; o.frequency.value = freq;
    g.gain.setValueAtTime(0, t); g.gain.linearRampToValueAtTime(gain, t + .02); g.gain.exponentialRampToValueAtTime(.0001, t + dur);
    o.connect(g); g.connect(master); if (echo) g.connect(verb); o.start(t); o.stop(t + dur + .05);
  }
  function hiss({ dur = .12, freq = 2000, q = 1, gain = .08, type = "bandpass", sweep = null, at = 0 } = {}) {
    const s = ctx.createBufferSource(), f = ctx.createBiquadFilter(), g = ctx.createGain(), t = now() + at;
    s.buffer = noise; f.type = type; f.frequency.setValueAtTime(freq, t); if (sweep) f.frequency.exponentialRampToValueAtTime(sweep, t + dur); f.Q.value = q;
    g.gain.setValueAtTime(gain, t); g.gain.exponentialRampToValueAtTime(.0001, t + dur);
    s.connect(f); f.connect(g); g.connect(master); s.start(t, Math.random() * .5); s.stop(t + dur + .02);
  }
  const PENTA = [880, 987.8, 1174.7, 1318.5, 1568, 1760];
  function loop(fn, min, max) { const go = () => { if (!on) return; fn(); timers.push(setTimeout(go, min + Math.random() * (max - min))); }; timers.push(setTimeout(go, min + Math.random() * (max - min))); }
  let stopDrone = null;

  const FX = {
    shuffle() { for (let i = 0; i < 9; i++) hiss({ dur: .05, freq: 3500, q: .8, gain: .05, at: i * .035 }); },
    pick() { hiss({ dur: .06, freq: 2600, q: 2, gain: .04 }); },
    flip() { hiss({ dur: .22, freq: 900, sweep: 3800, q: 1.2, gain: .07 }); tone(1318.5, { dur: 1.6, gain: .025, at: .12 }); },
    wipe() { const t = performance.now(); if (t - lastWipe < 90) return; lastWipe = t; hiss({ dur: .12, freq: 1400, q: .6, gain: .025, type: "lowpass" }); },
    reveal() { [784, 987.8, 1174.7, 1568].forEach((f, i) => tone(f, { dur: 2.4, gain: .035, at: i * .12 })); },
    chest() { tone(82.4, { dur: .5, gain: .12, type: "triangle", echo: false }); [1046.5, 1318.5, 1568, 2093].forEach((f, i) => tone(f, { dur: 1.8, gain: .03, at: .15 + i * .09 })); },
    candle() { hiss({ dur: .3, freq: 600, sweep: 1600, q: .7, gain: .04 }); tone(659.3, { dur: 1.2, gain: .02, at: .05 }); },
  };

  function fade(to, s = 1.2) { const t = now(); master.gain.cancelScheduledValues(t); master.gain.setValueAtTime(master.gain.value, t); master.gain.linearRampToValueAtTime(to, t + s); }
  const api = {
    get on() { return on; },
    async enable() {   // call from a user gesture
      init(); if (on) return; on = true;
      try { await ctx.resume(); } catch {}
      stopDrone = drone(); fade(.85);
      loop(() => tone(PENTA[(Math.random() * PENTA.length) | 0] / (Math.random() < .5 ? 2 : 1), { dur: 4, gain: .022 }), 7000, 19000);
      loop(() => hiss({ dur: .006 + Math.random() * .02, freq: 2400 + Math.random() * 2000, q: 3, gain: .012 + Math.random() * .02 }), 90, 900);
    },
    disable() { if (!ctx || !on) return; on = false; timers.forEach(clearTimeout); timers = []; fade(0, .6);
      setTimeout(() => { if (!on) { if (stopDrone) stopDrone(); stopDrone = null; ctx.suspend(); } }, 700); },
    play(name) { if (on && FX[name]) try { FX[name](); } catch {} },
  };
  document.addEventListener("visibilitychange", () => { if (!ctx || !on) return; if (document.hidden) { fade(0, .4); setTimeout(() => document.hidden && ctx.suspend(), 450); } else { ctx.resume(); fade(.85, 1); } });
  return api;
}
