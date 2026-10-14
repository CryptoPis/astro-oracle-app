# $Astro Oracle: project brief (read this first in every new chat)

**What it is.** A Telegram Mini App for astrology and divination, bot @astrogm2026bot. Languages: Georgian (main),
English, Russian. Owner: CryptoPis. Code: github.com/CryptoPis/astro-oracle-app (branch `main`).

**Stack.** Python FastAPI + aiogram 3 (webhook) in one process; async SQLAlchemy (SQLite now, PostgreSQL-ready);
Groq for AI (JSON outputs, `llama-3.3-70b-versatile`, vision `llama-4-scout`); astronomy-engine for real planetary
positions. Frontend: one file `frontend/app.html` (no framework) → `python -m scripts.build_frontend` builds
`static/index.html` (served at `/`) and `dist/preview.html` (browser preview with demo data).

**Security rules.** Every API call is authenticated with Telegram `initData` (HMAC-SHA256), never trust the client.
Secrets only in `.env` (the old bot token and Groq key were leaked and rotated). $AST coins are off-chain reward
points; every change goes through the `coin_transactions` ledger; rewards are paid only after a successful AI answer.

**Practices built.** Daily energy + lucky numbers, daily gift with streaks, horoscope (12 signs, day/week/month),
tarot (card of the day, three-card spread, collection), dreams + journal, numerology, magic sphere, moon ritual,
compatibility, AI astrologer chat, aura and coffee photo readings, kundli (sidereal chart).

**Design.** Night sky indigo `#0d0a24`, violet `#8b6cff`, gold `#e2bd6a`. Living art cards (tilt with the phone,
change daily), swipeable rails, floating tab bar. Fonts: Jost/Manrope (UI), Noto Sans Georgian, Cormorant for the
oracle's voice. Art style and prompts: `docs/ART_PROMPTS.md`.

**Status / next.** See `ROADMAP.md` (done, next, parked mining, ideas inbox: voice, monetization with Telegram Stars,
engagement strategy). Not deployed yet; next technical step is hosting + BotFather Mini App registration.
