# $Astro Oracle: Telegram Mini App backend (v2)

FastAPI + aiogram 3 (webhook) + async SQLAlchemy. The bot is now a thin entry point; all features live in the Mini App (`static/index.html`).

```
astro-oracle/
├── app/
│   ├── main.py            FastAPI app, lifespan, webhook route, static hosting
│   ├── config.py          .env settings
│   ├── db.py / models.py  async SQLAlchemy (SQLite now, PostgreSQL-ready)
│   ├── security.py        Telegram initData HMAC-SHA256 validation + auth dependency
│   ├── ai/                provider.py (AsyncGroq JSON mode / mock), prompts.py (schemas)
│   ├── core/              astro.py (zodiac, numerology, moon), tarot.py (deck, draw)
│   ├── services/          economy.py ($AST ledger), users.py, content.py (shared AI cache)
│   ├── api/               user.py, horoscope.py, tarot.py, dreams.py, common.py
│   └── bot/               handlers.py (/start, /stats, /send), scheduler.py (morning push)
├── static/
│   ├── index.html         built Mini App page (do not edit; edit frontend/app.html)
│   └── img/               logo + zodiac art (webp)
├── frontend/app.html      Mini App source: design, screens, API client, demo mode
├── scripts/               migrate_legacy_db.py, build_frontend.py
└── tests/test_api.py
```

## Frontend
`frontend/app.html` is the whole Mini App: night-sky design, rotating astrolabe with the live moon phase, smoke and fog effects, 3D tarot cards, horoscope, dream journal, profile, ka/en/ru.
- Inside Telegram it talks to the API with `Authorization: tma <initData>`.
- Opened in a normal browser (no initData) it runs in **demo mode** with sample data, so the design can be reviewed without a server.
- After editing, run `python -m scripts.build_frontend` → `static/index.html` (served at `/`) and `dist/preview.html` (standalone preview).

## Quick start (local, no Telegram, no AI costs)
```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env    # set ENV=development DEV_AUTH_BYPASS=true AI_PROVIDER=mock BOT_ENABLED=false
uvicorn app.main:app --reload
# open http://localhost:8000  (API docs: /docs, dev only)
pytest -q
```

## Production
1. BotFather: `/newapp` → choose @astrogm2026bot → Web App URL = `https://<your-domain>/` → short name (put it in `MINI_APP_SHORT_NAME`).
2. Fill `.env` (`ENV=production`, real `BOT_TOKEN`, `GROQ_API_KEY`, `PUBLIC_BASE_URL=https://…`, long random `WEBHOOK_SECRET`, `ADMIN_IDS`).
3. Run behind HTTPS (Caddy/nginx/Cloudflare): `docker build -t astro . && docker run -d --env-file .env -v $PWD/data:/srv/data -p 8000:8000 astro`
   On startup the app sets the webhook and the chat menu button automatically.
4. One-time (if you have the old bot database): `python -m scripts.migrate_legacy_db /path/to/astro_bot.db`.

Run a **single** process/worker (bot dispatcher + scheduler + SQLite). Scaling out later means PostgreSQL plus moving the scheduler to its own worker.

## API (all require `Authorization: tma <initData>`)
| Method | Path | Notes |
|---|---|---|
| POST | /api/auth/verify | upsert user, referral via `startapp=ref_<id>`, returns profile + moon + economy table |
| GET / PATCH | /api/user/profile | PATCH: `lang`, `birth_date` (YYYY-MM-DD), `birth_time`, `birth_city` |
| POST | /api/user/daily-reward | 409 `already_claimed` if taken today; streak bonuses at 3/7/30 |
| GET | /api/horoscope?period=day\|week\|month&sign=Leo | shared cache per sign/period/lang; coins only for own sign |
| GET | /api/daily/energy | quote, affirmation, lucky numbers, moon |
| GET | /api/zodiac | localized 12-sign selector data |
| POST | /api/tarot/draw | `{spread: daily\|single\|three, question?}`; daily = same card all day |
| GET | /api/tarot/history | |
| POST | /api/dreams/analyze | `{text, save}` → structured analysis, saved to journal |
| GET / DELETE | /api/dreams, /api/dreams/{id} | dream journal |

Errors: `{"detail": {"code": "...", "message": "..."}}`. Codes: `daily_quota` (429), `ai_unavailable` (503), `needs_birth_date`, `bad_sign` (400), `already_claimed` (409).

## Assets still needed
- `static/img/zodiac/`: Aries, Taurus, Gemini, Cancer are in place. Leo → Pisces are missing; the app shows a gold glyph medallion for them until art is added (`<sign>.webp`, then add it to `ART` in `frontend/app.html`).
- Tarot: 21 illustrated cards + card back in `static/img/tarot/`. The Hierophant painting is missing; the app draws a gold-line face for it until `hierophant.webp` is added (then add it to `TAROT_IMG` in `frontend/app.html`).
- Practice icons (12) in `static/img/icons/`.

## Not yet ported from the legacy bot
Advisor chat, aura & coffee (vision → needs an upload endpoint), compatibility, kundli (needs a real ephemeris), moon ritual, numerology reading, magic sphere, leaderboard, tasks, admin cashout review. The economy constants for all of them already exist in `services/economy.py`.
