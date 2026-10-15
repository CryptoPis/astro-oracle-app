# Performance notes (visual pass 3, 2026-10-15)

How measured: `python -m scripts.perf_probe` serves `dist/preview.html` (demo data) to the installed Google Chrome
through Playwright, throttles the CPU 4x (CDP `Emulation.setCPUThrottlingRate`) and records for 5 s per scenario:
FPS and p95 frame time (from `requestAnimationFrame` deltas), janky frames (> 33 ms), long tasks (> 50 ms,
`PerformanceObserver`), main-thread busy time, style recalcs and style time (CDP `Performance.getMetrics`), and
Paint/Raster time from a Chrome trace. Phone = 390×844 @3x touch, desktop = 1280×800 @1x mouse.
Headless Chrome uses a software GPU, so GPU-side costs (backdrop blur, compositing) are under-reported; main-thread
numbers are reliable.

## Before (commit 7a1724b)

| device | scenario | FPS | p95 ms | janky | long tasks | busy ms/s | style recalcs/s | style ms/s | script ms/s | paints/s |
|---|---|---|---|---|---|---|---|---|---|---|
| phone | home idle | 20.5 | 66.7 | 80 | 63 | 980 | 20.3 | 561 | 128 | 53 |
| phone | home scroll | 14.6 | 100 | 220 | 201 | 965 | 14.6 | 522 | 102 | 39 |
| phone | tarot scroll | 52.0 | 33.4 | 19 | 0 | 762 | 52.0 | 339 | 142 | 70 |
| desktop | home idle | 17.8 | 66.7 | 90 | 73 | 994 | 17.8 | 584 | 116 | 51 |
| desktop | home scroll | 15.0 | 83.4 | 253 | 100 | 768 | 15.0 | 423 | 72 | 43 |
| desktop | tarot scroll | 35.8 | 33.4 | 40 | 0 | 625 | 36.0 | 322 | 62 | 61 |

The main thread is ~98% busy on the home screen even when nobody touches it, and more than half of that is style
recalculation: one full-document recalc per frame (~28 ms each at 4x).

## Finding the cause: switch one suspect off at a time (phone, home idle)

| experiment (injected before the page runs) | FPS | style ms/s | long tasks | busy ms/s |
|---|---|---|---|---|
| baseline | 20.5 | 561 | 63 | 980 |
| **block `--tx/--ty` writes on `<html>`** | **58.2** | **72** | **0** | 778 |
| `backdrop-filter: none` everywhere | 17.4 | 549 | 62 | 927 |
| hide `#sky` canvas and `.fog` | 19.9 | 579 | 54 | 973 |
| no canvas `shadowBlur` | 15.4 | 447 | 48 | 775 |

**Root cause.** `Tilt.tick()` ran every animation frame (also when idle, because of an "idle sway") and wrote the
custom properties `--tx` / `--ty` on `document.documentElement`. Custom properties are inherited, so every write
invalidated the computed style of the whole document: ~1 000 elements restyled 60 times a second. That alone made
every frame miss its budget on a slow CPU, produced long tasks, and forced the hero card, rails, pills and the
fixed tab bar to be repainted and re-composited every frame. On Telegram Desktop (Chromium/Qt webview) the repaint
of content under the blurred tab bar and pills (`backdrop-filter`) on every frame is what shows up as flicker,
and the starved main thread is what makes scrolling stutter.

Contributing costs (smaller, but real):
- The tarot and sphere smoke loops called `clearRect` every frame even with no particles: a canvas repaint per
  frame for nothing (tarot: 70 paints/s while idle).
- `.la-shine` animated `background-position` (a paint every frame over the hero painting).
- The full-screen `#sky` canvas redrew hundreds of `arc()` stars per frame; the astrolabe redrew 72 ticks and 12
  glyphs (with `shadowBlur`) per frame only to rotate them; living-art stars and motes created radial gradients
  per star per frame.
- Five `backdrop-filter` surfaces over constantly changing content (GPU cost, flicker in desktop webviews).
- Not a problem, contrary to the first suspicion: `drawMoon()` runs once per screen, not per frame.

## Before vs after (same probe, CPU 4x)

"Before" re-measured with the final probe (touch scroll gestures on the phone) so the rows compare like with like.
This machine has 4 CPU cores, so the phone emulation lands in the **lite** tier; the full tier is measured separately.

| device | scenario | FPS before → after | p95 ms | janky frames | long tasks | busy ms/s | style ms/s | paints/s |
|---|---|---|---|---|---|---|---|---|
| phone | home idle | 21.5 → **60.0** | 66.7 → 16.8 | 77 → 0 | 55 → **0** | 994 → **181** | 582 → 0 | 58 → 0 |
| phone | home scroll | 18.4 → **59.8** | 83.5 → 16.8 | 51 → 0 | 31 → **0** | 927 → **223** | 507 → 0 | 53 → 0 |
| phone | tarot scroll | 46.2 → **59.8** | 33.4 → 16.8 | 17 → 0 | 1 → 0 | 903 → **336** | 444 → 92 | 86 → 0 |
| desktop | home idle | 19.3 → **59.9** | 66.8 → 16.8 | 83 → 0 | 62 → **0** | 990 → **206** | 586 → 0 | 55 → 0 |
| desktop | home scroll | 17.9 → **59.9** | 83.4 → 16.8 | 253 → 0 | 33 → **0** | 655 → **148** | 365 → 9 | 45 → 0 |
| desktop | tarot scroll | 40.6 → **58.3** | 33.4 → 16.8 | 39 → 2 | 0 → 0 | 614 → **125** | 307 → 13 | 55 → 11 |

Phone with the **full** tier forced (`--tier full`: idle sway, 3D tilt, twinkling sky layers, 60 fps canvases):
home idle 59.9 FPS, 0 long tasks, busy 489 ms/s; home scroll 59.8 FPS, 0 long tasks; tarot scroll 59.9 FPS.
The full tier is only chosen for phones with more than 4 cores and more than 3 GB of memory, which have that headroom.

## What changed

| problem | fix |
|---|---|
| `--tx/--ty` written on `<html>` every frame | written only on the visible tilt hosts (hero card, rails, sign card), only when the value moved by > 0.004; lite tier: no idle sway, so nothing is written while idle |
| tilted practice cards had `transition: transform` (restarted on every tilt frame) | no transition on the tilt transform; press feedback uses the separate `scale` property |
| page (body) scrolling under fixed layers | one dedicated `#scroller` (`overscroll-behavior: contain`, `contain: layout paint`); `html, body` never scroll |
| loops ran while scrolling / hidden / off screen | one rAF scheduler: per-loop frame rate, nothing runs while scrolling or hidden, loops unregister when idle; CSS animations of off-screen elements paused via IntersectionObserver (`data-off`) and during scroll (`.scrolling`) |
| full-screen sky redrawn every frame | stars painted once per size into 3 canvases (1 on lite); only their opacity animates |
| astrolabe redrawn every frame with `shadowBlur` | drawn once (glow included), rotated by a CSS animation; static on lite |
| per-frame radial gradients and `shadowBlur` in living art | pre-rendered glow sprites, halo stroke instead of `shadowBlur` |
| smoke canvases cleared every frame while empty | canvas layers animate only while particles live, clear once, stop |
| light sweep animated `background-position` + `mix-blend-mode` | sweep moves by `transform`; blend modes removed |
| 5 `backdrop-filter` surfaces | only the tab bar keeps a blur, and only on the full tier; everything else is a solid translucent surface with a gold hairline |
| cold start: up to 45 s of an empty screen | splash "the sky is waking" from the first paint, explanation after 3.5 s, retries with backoff (15/25/30/30 s timeouts), retry button |
| splash SVG kept animating after fade-out | `display: none` after the fade |

## Performance tier

Chosen once at boot (`PERF` in `frontend/app.html`), visible as `<html data-tier="…">`:
- **lite**: Telegram Desktop / macOS / Web clients, any device with ≤ 4 cores or ≤ 3 GB memory, or
  `prefers-reduced-motion`. No backdrop blur, half the stars, still fog, still paintings (no Ken Burns, no sweep),
  static astrolabe, canvases at 24–30 fps, no idle sway, no constellation veil, opacity-only reveals.
- **full**: everything else (capable phones): all effects at 60 fps.
- Override for testing: `?tier=lite` / `?tier=full`, or `localStorage["astro.tier"]`.

## Reproduce

    pip install playwright
    python -m scripts.build_frontend
    python -m scripts.perf_probe --label after            # both devices
    python -m scripts.perf_probe --only phone --tier full  # force a tier
    python -m scripts.screenshots                         # every screen, ka/en/ru, phone + desktop
