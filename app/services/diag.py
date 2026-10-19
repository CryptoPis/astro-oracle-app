"""System self-check, used by the /diag bot command (admins) and `python -m scripts.check_env`.

Every check returns (status, title, detail) where status is "ok", "warn" or "fail".
Secrets are never printed: only whether they are set and whether the service accepted them.
"""
import time

from sqlalchemy import func, select

from app.config import get_settings

ICON = {"ok": "✅", "warn": "⚠️", "fail": "❌"}


async def run_checks(bot=None) -> list[tuple[str, str, str]]:
    s = get_settings()
    out: list[tuple[str, str, str]] = []
    add = lambda st, title, detail="": out.append((st, title, detail))

    # ── configuration ──
    add("ok" if s.bot_token else "fail", "BOT_TOKEN", "set" if s.bot_token else "missing")
    add("ok" if s.groq_api_key or s.ai_provider == "mock" else "fail", "GROQ_API_KEY",
        "set" if s.groq_api_key else ("mock AI (no key needed)" if s.ai_provider == "mock" else "missing"))
    add("ok" if s.public_base_url.startswith("https://") else "warn", "PUBLIC_BASE_URL", s.public_base_url)
    add("ok" if s.webhook_secret else "warn", "WEBHOOK_SECRET", "set" if s.webhook_secret else "missing: bot falls back to polling")
    add("ok" if s.cron_secret or s.morning_push_mode != "external" else "warn", "CRON_SECRET",
        "set" if s.cron_secret else "missing: /cron/morning is disabled")
    add("ok" if s.admin_ids else "warn", "ADMIN_IDS", f"{len(s.admin_ids)} admin(s)" if s.admin_ids else "none: /stats, /send, /diag unavailable")
    sqlite = s.database_url.startswith("sqlite")
    add("warn" if sqlite and not s.is_dev else "ok", "DATABASE_URL",
        "SQLite: on Render the data is erased on every deploy; use Neon PostgreSQL" if sqlite else "PostgreSQL")

    # ── database ──
    try:
        from app.db import SessionLocal, ping
        from app.models import User
        t = time.perf_counter(); await ping(); ms = (time.perf_counter() - t) * 1000
        async with SessionLocal() as session:
            users = await session.scalar(select(func.count()).select_from(User))
        add("ok", "Database", f"connected in {ms:.0f} ms, {users} users")
    except Exception as e:
        add("fail", "Database", f"{type(e).__name__}: {str(e)[:160]}")

    # ── Telegram ──
    own_bot = None
    try:
        if bot is None:
            from aiogram import Bot
            bot = own_bot = Bot(token=s.bot_token)
        me = await bot.get_me()
        add("ok" if me.username.lower() == s.bot_username.lower() else "warn", "Telegram bot",
            f"@{me.username}" + ("" if me.username.lower() == s.bot_username.lower() else f" (BOT_USERNAME says @{s.bot_username})"))
        info = await bot.get_webhook_info()
        expected = f"{s.public_base_url}/telegram/webhook"
        if info.url == expected:
            err = f", last error: {info.last_error_message}" if info.last_error_message else ""
            add("warn" if info.last_error_message else "ok", "Webhook", f"{info.pending_update_count} pending{err}")
        else:
            add("warn", "Webhook", f"points to {info.url or '(none)'}; expected {expected}")
    except Exception as e:
        add("fail", "Telegram bot", f"{type(e).__name__}: {str(e)[:160]}")
    finally:
        if own_bot:
            await own_bot.session.close()

    # ── AI ──
    if s.ai_provider == "mock":
        add("warn", "AI", "AI_PROVIDER=mock: sample answers only")
    elif s.groq_api_key:
        try:
            from app.ai import prompts as P
            from app.ai.provider import get_ai
            ai = get_ai()
            available = set(await ai.list_models())
            rows = [("text", s.groq_text_model), ("fast", s.groq_fast_model), ("vision", s.groq_vision_model)]
            rows += [(f"{lang} language", m) for lang, m in (("ka", s.groq_model_ka), ("ru", s.groq_model_ru)) if m]
            for label, model in rows:
                add("ok" if model in available else "fail", f"Groq {label} model", model + ("" if model in available else " is NOT available"))
            t = time.perf_counter()
            res = await ai.complete_json(*P.energy_prompt("en", "Leo", "Full Moon", "2026-01-01"), P.EnergyAI, fast=True, max_tokens=200)
            add("ok", "Groq test answer", f"{(time.perf_counter() - t):.1f} s: “{res.focus}”")
        except Exception as e:
            add("fail", "Groq", f"{type(e).__name__}: {str(e)[:160]}")
    return out


def format_report(checks: list[tuple[str, str, str]], html: bool = False) -> str:
    import html as h
    esc = h.escape if html else (lambda x: x)
    lines = [f"{ICON[st]} {'<b>' if html else ''}{esc(title)}{'</b>' if html else ''}: {esc(detail)}" for st, title, detail in checks]
    bad = sum(st == "fail" for st, _, _ in checks)
    lines += ["", "🟢 All systems go" if not bad else f"🔴 {bad} problem(s) to fix"]
    return "\n".join(lines)
