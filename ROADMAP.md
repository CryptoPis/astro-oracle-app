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

## Next
- Deploy (HTTPS host), register the Mini App in BotFather, test inside Telegram.
- Feedback round on the design and texts.
- Leaderboard and tasks (Telegram channel, X) from the legacy bot.
- Kundli extras: navamsa (D9), current dasha periods.

Missing art: 8 zodiac paintings (Leo → Pisces), the Hierophant tarot card.

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
