# $Astro Oracle: project brief (read this first in every new chat)

**What it is.** A Telegram Mini App for astrology and divination, bot @astrogm2026bot. Languages: Georgian (main),
English, Russian. Owner: CryptoPis. Code: github.com/CryptoPis/astro-oracle-app (branch `main`).

**Stack.** Python FastAPI + aiogram 3 (webhook) in one process; async SQLAlchemy (Neon PostgreSQL in production,
SQLite locally); Groq for AI with automatic model fallback (`openai/gpt-oss-120b`, fast `openai/gpt-oss-20b`, vision
`qwen/qwen3.8-27b`; Groq retired the Llama models in 2026); astronomy-engine for real planetary positions (no AstroAPI).
Hosting: Render (render.yaml blueprint) + Neon + cron-job.org (keep-alive and /cron/morning). Guide: `docs/DEPLOY.md`.
Admin self-check: `/diag` in the bot. Dev checks: `scripts/perf_probe.py` (FPS, long tasks), `scripts/ui_audit.py`
(overflow, rail cards), `scripts/screenshots.py` (every screen in ka/en/ru). Frontend: one file `frontend/app.html` (no framework) → `python -m scripts.build_frontend` builds
`static/index.html` (served at `/`) and `dist/preview.html` (browser preview with demo data).

**Astrology.** Horoscopes for your own sign are personal: natal chart + real transits of the day/week/month
(astronomy-engine, tropical), ranked and explained from a knowledge base (`app/astro_kb/`) built from public-
domain books in our own words (Sepharial for transits, Lilly for dignities, Ptolemy as cross-check; Waite for
tarot, Atkinson for aura, Harley for the moon, a 1920s tea-cup book for coffee, Agrippa for day correspondences,
Freud's method for dreams as one perspective). Every AI prompt gets its KB lines: the KB decides, the AI only
phrases, and difficult meanings are said honestly. Each horoscope section shows the transits behind it.
Details, sources and limits: `docs/ASTROLOGY.md`. Kundli stays sidereal (Lahiri). Tarot is random by design.

**AI quota (Groq free tier).** Shared texts per sign; personal texts only on open, shared by transit signature;
per-user daily caps with fallback to the sign text; daily call counters in `/diag` (no user data).

**Motion.** "Slow celestial ritual": one curve `cubic-bezier(.2,.7,.1,1)`, 240/480/900 ms, ambient loops of
20-60 s, transform/opacity/canvas only, paused off screen and while scrolling, reduced in the lite tier.

**AI.** Groq (free) with a quality guard for Georgian and Russian: garbled answers are retried, then another
model, then a hand-written text (never cached). Names of cards, signs, planets and moon phases never come from
the AI. Per-language model `GROQ_MODEL_KA/RU`; a paid provider can take one language via `AI_PROVIDER_KA`
(adapter stub). Details and the benchmark: `docs/AI_QUALITY.md`. The magic sphere is hand-written, no AI.

**Security rules.** Every API call is authenticated with Telegram `initData` (HMAC-SHA256), never trust the client.
Secrets only in `.env` (the old bot token and Groq key were leaked and rotated). $AST coins are off-chain reward
points; every change goes through the `coin_transactions` ledger; rewards are paid only after a successful AI answer.

**Practices built.** Daily energy + lucky numbers, daily gift with streaks, horoscope (12 signs, day/week/month),
tarot (card of the day, three-card spread, collection), dreams + journal, numerology, magic sphere, moon ritual,
compatibility, AI astrologer chat, aura and coffee photo readings, kundli (sidereal chart, navamsa, dasha),
live sky (real planet positions now, planet of the day, retrogrades; meanings are static text, no AI), weekly
sky report, streak freeze (one missed day per week), share-to-story cards.

**Design.** Night sky indigo `#0d0a24`, violet `#8b6cff`, gold `#e2bd6a`. Identity "celestial engraving" (visual
pass 3): translucent night surfaces with a 1px gold hairline that fades around the shape, engraved corners and an
engraved rule with a four-point star under titles, gold ingot buttons. Motion language: one easing curve
`cubic-bezier(.22,.8,.24,1)`, a spring only for arrival/reward, durations 180/320/600 ms; views arrive with a
staggered fade-up, a gold lens slides along the tab bar, the oracle's words surface like ink. Living art cards (tilt
with the phone, change daily), swipeable rails, floating tab bar. Art (2026-10-19): practice icons, zodiac signs, planets and the hero living art are code-drawn
SVG in one style (fine gold line art, thin rings, star dots, violet glow; antique astrolabe + celestial atlas),
lines draw themselves on first appearance; only the tarot deck uses paintings. Nothing moves under the finger
(gyroscope tilt only on the home hero, full tier). Fonts: Jost/Manrope (UI), Noto Sans Georgian,
Cormorant for the oracle's voice (upright in Georgian: Georgian has no true italic). Performance tier `full`/`lite`
(desktop clients and weak phones get `lite`: no blur, still pictures); measure with `scripts/perf_probe.py`, see
`docs/PERF_NOTES.md`. Zodiac art: all 12 signs in one black & gold engraved style, no text in any image (the app
is multilingual); Aries, Taurus, Cancer also keep earlier purple paintings as daily variants. Tarot: full 22-card deck. Art style and prompts: `docs/ART_PROMPTS.md`.

**Oracle chamber (opt-in UI, branch `oracle-chamber`).** A second interface on the same app: a candle-lit
astrologer's room in which every practice is an object you touch (tarot table, crystal ball, moon window, the
oracle's candle, book of dreams, astrolabe, star-chart scroll, aura mirror, coffee cup, gift chest; the star dome
above). Switch: `?ui=chamber` (also `?startapp=ui_chamber`) or Profile → Interface; the classic UI stays the
default. Code: `static/chamber/*.js` (ES modules, loaded only when the chamber is on) + three.js 0.160.0 vendored in
`static/vendor/`; the classic `frontend/app.html` only gained a switch, a small bridge (`bridge()`) and a few events
(`astro:sky`, `astro:energy`, `astro:busy`, `astro:vision`, `astro:compat`). The glass-and-gold panel shows the
app's own views, so API, auth, i18n, economy and AI are shared. FULL tier: procedural WebGL room (no image files,
no text in the art), interactive stages for tarot (shuffle, fan, draw by hand, flip; reversed lands upside down),
the sphere (wipe the mist), the chest (coins fly to the counter), the 3D horoscope under the dome (natal wheel,
transit beams; data from the read-only `GET /api/horoscope/chart`), the moon ritual (candles light step by step)
and the coffee cup (swirl, turn over, photo). LITE tier (Telegram Desktop, weak phones, no fast WebGL, reduced
motion): the same room in 2.5D layers, all features through the panel. Sound: Web Audio only, off by default.
Checks: `scripts/chamber_check.py` (smoke, memory, FPS), videos `scripts/chamber_videos.py`.

**Status / next.** See `ROADMAP.md` (done, next, parked mining, ideas inbox: voice, monetization with Telegram Stars,
engagement strategy). Deployment-ready; follow `docs/DEPLOY.md`.
