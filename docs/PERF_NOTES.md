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

---

# Visual fix 2 (2026-10-15, branch `visual-fix-2`)

Reported from a real Android phone in Telegram (the phone ran the `main` build, without visual pass 3).
Each cause was confirmed in Playwright on the `main` build before fixing, with `scripts/ui_audit.py`
(390×844 phone, overflow measured against the device width; idle restyles with the CPU 4x).

| bug | confirmed on `main` | cause | after |
|---|---|---|---|
| fields overflow on the right (dream text, profile fields, sphere, advisor) | dream textarea and all 4 profile fields end at **398 px** on a 390 px screen; mobile Chrome then widens the layout viewport to 398 | `.field { width: 100% }` + padding + border with the default `content-box`, plus the default 8 px body margin | global `box-sizing: border-box`, `body { margin: 0 }` (visual pass 3); audit: no element past 390 px on any screen, ka/en/ru, phone + desktop |
| rail cards lose frame/title/chip, only the icon floats | idle home restyles **653 ms/s** (33 full recalcs/s) from `--tx/--ty` on `:root`; every `.pcard` had `perspective() rotateX/Y` from those variables | 3D-transformed items inside an `overflow-x: auto` scroll-snap container: Android WebView drops their paint (could not reproduce the drop itself in desktop Chrome; the restyle storm and the 3D transforms are confirmed) | rail cards are flat (no tilt, no perspective) with `contain: paint`; tilt only on the hero card, written on it only when the value changes; idle restyles **0**; audit: all 12 cards in all 3 rails show frame + title + chip in every language |
| reward chips too small, coin pill cramped | `.74rem`, 10% gold on dark | | chips `.82rem` bold, brighter, with a gold coin, `nowrap`; coin pill `nowrap`, never shrinks; the brand text gives way; audit with 12,500 and 1,250,000 |
| tab bar hides the end of the content | | 28 px of space under content for a ~74 px bar | fade above the bar + 44 px extra, safe-area aware |
| Telegram Desktop flicker/jank | see the first part of this file | | performance tier, one scroller, loops paused, cold-start splash (visual pass 3) |

Performance with the new live-sky section (CPU 4x): phone 59.8 FPS idle and scrolling, 0 long tasks, busy
189 ms/s idle; desktop 59.9 FPS, 0 long tasks; phone with the full tier forced 60 FPS, 0 long tasks.
The sky wheel is a static SVG drawn once per data refresh; only the planet-of-the-day halo animates
(opacity/transform, paused in the lite tier).

# Oracle chamber (2026-10-20, branch `oracle-chamber`)

Measured with `python -m scripts.chamber_check --perf` on the demo build (`dist/preview.html?ui=chamber`),
390×844, device pixel ratio 2 (the chamber caps it at 1.75), Chrome with **CPU throttled 4×**. The FULL tier ran on a
real GPU through ANGLE/Direct3D 11 (an old NVIDIA GeForce GT 630, roughly a mid phone GPU), not on software GL.

| | FULL (three.js) | LITE (2.5D) |
|---|---|---|
| Interactive (page start → room usable) | 3.33 s | 2.33 s |
| of which: parsing the 2.3 MB demo page | 0.96 s | 0.97 s |
| of which: the chamber's own boot | 1.19 s | 0.21 s |
| FPS, room idle (candles, dust, smoke) | 60.3 (worst frame 17 ms) | 60.0 (worst 50 ms, one frame) |
| FPS, turning between objects | 60.2 (worst 17 ms) | 60.2 (worst 17 ms) |
| JS heap before → after 10 more station visits | 12.9 → 12.9 MB (+0.4 %) | 7.27 → 7.27 MB (+0.1 %) |
| GPU geometries / textures after 10 visits and 3 full tarot draws | 109 / 30 → 109 / 30 | none |
| Download when the chamber starts (gzip) | 207 KB (three.js 166 KB + modules 41 KB) | 22 KB |

Notes
- The real app page (`static/index.html`, ~330 KB) parses much faster than the 2.3 MB demo page with inlined images,
  so on a phone the FULL room should be interactive in under 3 s once the server is awake.
- Stage modules (6-7 KB each), sound (2 KB) and the tarot card faces load only when needed; card faces are released
  when the tarot stage ends.
- What was cut to get here: per-pixel procedural textures halved (256 px, they repeat), the classic star sky is not
  painted in chamber mode, shaders compile with `renderer.compileAsync` (parallel where the driver allows).
- Rendering stops while a panel covers the room (except for a reaction that is playing), while the app is hidden,
  and when leaving; the LITE tier only animates transforms and opacity. A FULL room that draws its first frames
  slowly (average > 45 ms) switches itself to LITE and remembers it.
- GPU uploads are lazy (an object is uploaded the first time it is drawn), so the memory check warms up every
  station and stage first, then compares.

# Chamber graphics, stage A (2026-10-21, branch `chamber-graphics`)

The FULL room now has a real PBR shell (stone walls and pillars, an oak floor and wainscot, a rug and a velvet cloth:
albedo + normal map, roughness derived from the albedo in the shader), shadows rendered once, a window plate with
parallax and the real moon (NASA CGI Moon Kit, lit for the day's phase), a dome plate under a live shimmer (the
planets and the ecliptic ring stay real meshes), a raised black point (#0b0710) and a haze (#352f35). Lights use the
palette measured from the references (`scripts/chamber_assets.py`): candle amber #f2a958, moonlight #afb8d1. The
references' own black point measures #000000 and their haze #14080b, crushed blacks that the raised values lift.

Two graphics levels inside FULL (`static/chamber/full.js`, `GFX`):

| | High | Medium |
|---|---|---|
| pixel ratio cap | 1.75 | 1.4 |
| shadow casters (rendered once) | 2: moon (1024²) + central candle (512² cube) | 1: moon |
| glow | half-res bloom (2× MSAA scene target, bright pass, 2 blur passes) + glow sprites | glow sprites only |
| textures | 1024 px set, 2,431,590 bytes | 512 px set, 715,130 bytes |

Choice: frames 10-50 are drawn at High. If their average frame time is over 45 ms the room switches to LITE (as
before); over 20 ms it goes to Medium; otherwise it stays High. The WebP set for the chosen level is fetched only
then, after the first paint, and swapped in one texture per frame; procedural textures stand in until it arrives.
`?gfx=high|medium` forces a level and loads the textures from frame 2.

## Measured

`python -m scripts.chamber_check --perf` on the demo build: 390×844, device pixel ratio 2, **CPU throttled 4×**, real
GPU (GeForce GT 630 through ANGLE/D3D11, the same machine as the "Oracle chamber" numbers above). "Before" =
`main` at 1836db5, measured again in the same session.

| | before: FULL | after: FULL High | after: FULL Medium | LITE (unchanged) |
|---|---|---|---|---|
| Interactive (page start → room usable) | 3.16 s | 3.54 s | 3.81 s | 2.18 s |
| of which: the chamber's own boot | 1.11 s | 1.19 s | 1.47 s | 0.18 s |
| Photographic textures applied, after interactive | none | 0.51 s (1.10 s cold) | 0.01 s (0.26 s cold) | none |
| FPS, room idle | 60.3 (worst frame 17 ms) | 59.5 (worst 34 ms) | 60.3 (worst 17 ms) | 60.3 (worst 17 ms) |
| FPS, turning between objects | 60.2 (worst 17 ms) | 56.8 (worst 117 ms) | 60.0 (worst 33 ms) | 60.2 (worst 17 ms) |
| JS heap before → after 10 more station visits | 12.58 → 12.64 MB (+0.5 %) | 13.11 → 13.16 MB (+0.4 %) | (same engine as High) | 6.93 → 6.94 MB |
| GPU geometries / textures after 10 visits and 3 tarot draws | 109 / 30 → 109 / 30 | 110 / 39 → 110 / 39 | | none |
| Draw calls per frame (idle view) | | 1 to the screen (scene into the bloom target) | 34 | |
| Auto level on this machine | | High (frames 10-50 averaged 16.7 ms) | | |

What the High budget costs, one suspect off at a time (High, textures loaded, same probe):

| experiment | idle FPS | turning FPS |
|---|---|---|
| High as first built (4× MSAA scene target) | 48.5 | 47.4 |
| no bloom at all (direct render, both shadows kept) | 60.3 | 59.2 |
| no candle shadow | 51.8 | 49.6 |
| no normal maps | 51.0 | 50.4 |
| pixel ratio 1.4 | 60.3 | 59.2 |
| **bloom target 2× MSAA (shipped)** | **60.3** | **56.8** |
| bloom target without MSAA | 60.3 | 59.2 |

The 4× multisampled full-resolution target was the whole cost. 2× keeps smooth edges at a pixel ratio of 1.75 and
holds 60 FPS idle. The worst frame while turning (117 ms in High, one frame) is the first time an object's 1024 px
maps are drawn (GPU uploads are lazy). It also appears with the bloom off.

Notes
- High grows the download by up to 2.43 MB on capable phones, Medium by 0.72 MB, LITE by nothing. It is fetched after
  the room is already interactive, so it never delays the first paint.
- Shadows: `shadowMap.autoUpdate = false`. They are drawn once at boot and again only when the level changes. A
  level change holds the last frame while the new light set's shaders compile (`compileAsync`).
- Colour: one patched three.js chunk (`colorspace_fragment`) makes every built-in material write display-ready sRGB
  with the raised black point. The bloom target therefore holds exactly what the screen shows, so High and Medium
  match, and the hand-written shaders (flames, the sphere, the stages) needed no change.
- Screenshots (phone 390×844 @3x): `dist/screens/chamber-graphics/` (`before-*`, `after-high-*`, `after-medium-*`:
  room, window, astrolabe, dome), made with `python -m scripts.chamber_shots`.
