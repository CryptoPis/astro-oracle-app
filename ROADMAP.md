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

- Visual pass 2 (2026-10-14): "living art" cards that tilt with the phone (Telegram gyroscope) and change daily:
  paintings with slow camera drift, light sweep and gold dust, or a 3D constellation of the sign (real star pattern,
  nebula tinted by element) for every sign; tap to switch. New home: hero card, swipeable practice rails, floating
  tab bar, modern type. Tarot: pick cards from a fan, card collection (x / 22). Georgian dates without locale data.

## Next
- Missing art (audit 2026-10-14, rule: no text in any image, the app is multilingual): required 7 — Virgo, Scorpio,
  Sagittarius, Capricorn, Aquarius, Gemini (old one has English text, removed from the app) and the Hierophant;
  recommended 3 — Aries, Taurus, Cancer redone in the black & gold style. Ready prompts: `docs/ART_PROMPTS.md`.
- Deploy (HTTPS host), register the Mini App in BotFather, test inside Telegram.
- Feedback round on the design and texts.
- Leaderboard and tasks (Telegram channel, X) from the legacy bot.
- Kundli extras: navamsa (D9), current dasha periods.

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
