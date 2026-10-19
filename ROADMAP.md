# $Astro Oracle: roadmap

## Done
- Backend: FastAPI + aiogram 3 webhook, Telegram initData auth, async SQLAlchemy, Groq JSON-mode AI, $AST ledger.
- Mini App: sky (astrolabe, moon phase, energy, lucky numbers, daily gift), horoscope (12 signs, day/week/month),
  illustrated tarot (card of the day, three-card spread), dream interpreter + journal, profile (birth date, language, invite).
- Numerology (life path + personal year, AI reading cached per number) and the magic sphere (server-side answer).
- Moon ritual (cached per phase/day/language), compatibility (element + aspect score, AI reading per sign pair),
  AI astrologer chat (8-turn context, 15 questions/day), aura and coffee photo readings (vision model, photo not stored),
  kundli (sidereal Lahiri chart from real planetary positions via astronomy-engine, whole-sign houses, moon nakshatra,
  birth city geocoded with Open-Meteo).
- Assets from the old React app: 21 tarot paintings, card back, 12 practice icons.
- Art complete (2026-10-14): all 12 zodiac signs in the black & gold style, text-free (the app is multilingual);
  Aries, Taurus, Cancer keep the earlier purple paintings as second variants; the Hierophant completes the 22-card deck.

- Visual pass 2 (2026-10-14): "living art" cards that tilt with the phone (Telegram gyroscope) and change daily:
  paintings with slow camera drift, light sweep and gold dust, or a 3D constellation of the sign (real star pattern,
  nebula tinted by element) for every sign; tap to switch. New home: hero card, swipeable practice rails, floating
  tab bar, modern type. Tarot: pick cards from a fan, card collection (x / 22). Georgian dates without locale data.

- Production readiness (2026-10-14): Neon PostgreSQL (asyncpg, pooler-safe, tested on real PostgreSQL), Render
  blueprint, external cron endpoint with cache warm-up, gzip + image caching, webhook answered instantly, Groq models
  moved to gpt-oss/qwen with automatic fallback, `/diag` self-check and `scripts/check_env.py`.

- Kundli extras (2026-10-14): navamsa (D9) chart with a D1/D9 switch, Vimshottari dasha timeline (mahadashas,
  sub-periods of the current one); the AI reading covers both and refreshes when the antardasha changes.

- Visual pass 3 (2026-10-15, branch `visual-pass-3`): found the cause of flicker and stutter in Telegram Desktop
  with a Chrome profile (`scripts/perf_probe.py`, `docs/PERF_NOTES.md`): the tilt effect restyled the whole page
  every frame. Now 60 FPS and no long tasks on a 4x slowed CPU (was ~20 FPS). Performance tier (full/lite), one
  scroll container, loops pause while scrolling/hidden/off screen, cold-start splash with retries. New look
  "celestial engraving": gold hairline surfaces, engraved corners and rules, sliding tab lens, staggered view
  arrival, constellation veil, coin count-up with sparks, ink reveal of the oracle's words, tarot glow/flare/gold
  dust, collection cards light up, skeleton shimmer. Screenshots: `scripts/screenshots.py`.

- Visual fix 2 (2026-10-15, branch `visual-fix-2`, on top of visual pass 3): fixes from the first real-phone test
  (fields overflowing, rail cards losing their frame on Android, small reward chips, content hidden by the tab bar).
  New: **live sky** (`GET /api/sky`, real planet positions, zodiac wheel, planet sheet with meanings in ka/en/ru,
  planet of the day, retrograde banner), **weekly sky report** (Sunday/Monday), **streak freeze** (one missed day
  per week forgiven, stored in `action_counters`), **share to story** (canvas card, `POST /api/share/image`,
  Telegram `shareToStory`). Planet art prompts in `docs/ART_PROMPTS.md` §8. Audit: `scripts/ui_audit.py`.
- Deployed 2026-10-15: `visual-fix-2` (with visual pass 3 and kundli D9/dasha) merged into `main` and live on Render;
  rollback tag `backup-before-visual-fix-2` = the previous production version (7548bf2).
- Profile refresh fix (2026-10-19, branch `fix-profile-refresh`): Home could keep the old sign's data after a
  profile change. Reproduced with `scripts/ui_profile_refresh.py` (real backend + stub Telegram): a late response
  for the old sign overwrote the new one, nothing refreshed after the app came back from the background, and a
  double tap sent two saves. Now: stale responses are ignored, every cache is reset and Home rebuilt after a
  change, the profile is re-read after > 60 s in the background, Save shows progress/success/error, and verify,
  GET and PATCH profile return one user shape.
- Deployed 2026-10-19: `fix-profile-refresh` merged into `main` (bced9fa) and live on Render;
  rollback tag `backup-before-profile-refresh` = the previous production version (9a2084c).
- Georgian quality + unified art (2026-10-19, branch `polish-ka-visual`, not deployed): tarot card names from a
  ka/en/ru dictionary (no more "მზის (რევერსი) შებრუნებული"); quality guard for ka/ru answers with retry →
  next model → hand-written text (never cached); Georgian prompt rules in Georgian with examples; per-language
  models `GROQ_MODEL_KA/RU` and a paid-provider slot; `scripts/ai_benchmark.py` (needs the Groq key, not run yet)
  and `scripts/purge_bad_ai_cache.py`. Magic sphere: 24 native answers per language, colored glow instead of
  the chip, topic advice. Layout: zodiac strip fits Georgian names and centres the selection, horoscope art
  without text over it, rail cards without paint containment, no touch-driven tilt. All practice icons, zodiac
  art and the hero art are now one code-drawn gold engraved style. `scripts/ui_audit.py` checks clipped and
  overlapping text, the tab bar, 360×780, and card names against the real backend.

## Next
- Run `scripts/ai_benchmark.py` with the Groq key and set `GROQ_MODEL_KA` on Render (`docs/AI_QUALITY.md`).
- Test the live version on a real phone and in Telegram Desktop (see the checklist in the last report).
- BotFather: rename the Mini App title to "Astro Oracle" (see `docs/DEPLOY.md` §3.4).
- Art (optional): the 8 planet images from `docs/ART_PROMPTS.md` §8.
- Art (optional): a second gold variant per sign for daily rotation (`<sign>-2`), Minor Arcana if the deck grows to 78.
- Deploy following `docs/DEPLOY.md` (Neon + Render + cron-job.org), register the Mini App in BotFather, run `/diag`.
- Feedback round on the design and texts.
- Leaderboard and tasks (Telegram channel, X) from the legacy bot.

## Parked: mining (tap-to-earn)
Decision 2026-10-14: paused. The app launches as an astrology product; mining may return later.

What the old React app had (`src/screens/MiningScreen.jsx`, `hooks.js`): tapping a Merkaba orb for
5 + level/2 $AST per tap, an energy bar (1000 max, −10 per tap, +3 every 3 s), XP and 10 levels with
ranks (Novice → $AST Legend), five daily quests and a level-up modal.

Why it can't come back as it was: balance, energy and level lived only in the phone's localStorage,
so anyone could edit them. If it returns, it must be server-side:
- Taps are batched on the client (e.g. every 2 s) and sent as a count; the server clamps the count by
  elapsed time and current energy, then credits the ledger (`coin_transactions`, reason `mine_tap`).
- Energy is computed on the server from `last_tap_at` + regen rate, never trusted from the client.
- New columns on `users`: `energy`, `last_tap_at`, `xp`, `level`. Daily cap on mined $AST.
- Quests reuse `action_counters` (already tracks per-day actions).
- UI: a fourth tab, or a section on the sky screen; the Merkaba look fits the current palette.

## Ideas inbox (parked 2026-10-14, to plan in their own chats)
**Voice.** Talk to the AI astrologer and tell dreams by voice. Speech-to-text: Groq `whisper-large-v3` (same API key;
Georgian supported, quality to test). Spoken replies: a TTS voice with Georgian (candidates: Azure `ka-GE` neural voices;
verify quality and price). Mini App side: hold-to-record button with `MediaRecorder`, upload to a new `/api/voice` endpoint.

**Monetization.** In Telegram Mini Apps, digital goods must be sold for Telegram Stars (XTR) via `sendInvoice`/`openInvoice`.
Candidate offers: Premium month (unlimited astrologer, deeper spreads like the 10-card Celtic Cross, full kundli with
dasha periods, weekly personal forecast), single deep readings, extra daily questions. Keep $AST as reward points that
unlock extras; avoid selling $AST for money with a cash-out path (it would turn points into a currency).

**Engagement strategy.** What keeps people coming back: daily-changing content (done), streak gift (done), card
collection (done); next candidates: morning push with a personal teaser, weekly "sky report", achievements,
share-to-story cards for readings, referral rewards visible in-app, seasonal events (eclipses, retrogrades).

**Working in separate chats.** This chat stays the ideas/planning chat. Suggested chats in the AstroBot project:
Graphics (art, prompts, animation), Code (backend + Mini App), Marketing (ads, channel, launch), Monetization.
Each new chat should start by reading `claude/PROJECT_BRIEF.md` and `claude/ROADMAP.md` in the project.
