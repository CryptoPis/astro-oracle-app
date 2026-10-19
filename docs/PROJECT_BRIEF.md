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
(astronomy-engine, tropical), ranked and explained from a hand-written knowledge base (`app/astro_kb/`); the AI
only phrases them and each section shows the transits behind it. Details and limits: `docs/ASTROLOGY.md`.
Kundli stays sidereal (Lahiri). Tarot is random by design, interpreted honestly.

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

**Status / next.** See `ROADMAP.md` (done, next, parked mining, ideas inbox: voice, monetization with Telegram Stars,
engagement strategy). Deployment-ready; follow `docs/DEPLOY.md`.
