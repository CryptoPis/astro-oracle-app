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

## After

(filled in below once the fixes landed)
