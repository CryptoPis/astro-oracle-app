"""Morning horoscope push (legacy send_daily_horoscopes, ported).

Changes: it reuses the shared horoscope cache (36 AI calls at most, not one
per user), sends a short teaser with an "open app" button instead of a wall
of Markdown, and no longer gives free coins to every user just for receiving
a message.
"""
import asyncio
import html
import logging

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select

from app.bot.handlers import open_app_kb
from app.config import get_settings
from app.core import astro
from app.db import SessionLocal
from app.models import User
from app.services import content, economy

log = logging.getLogger(__name__)
HEADER = {"ka": "🌅 შენი დილის ჰოროსკოპი", "ru": "🌅 Твой утренний гороскоп", "en": "🌅 Your morning horoscope"}


async def send_morning_horoscopes(bot: Bot) -> None:
    day = economy.today_utc()
    async with SessionLocal() as session:
        users = (await session.execute(select(User.telegram_id, User.lang, User.birth_date)
                                       .where(User.birth_date.is_not(None), User.is_blocked.is_(False)))).all()
        sent = 0
        for uid, lang, bdate in users:
            sign = astro.zodiac_sign(bdate)
            try:
                h, _ = await content.get_horoscope(session, sign, "day", lang, day)
            except Exception:
                log.exception("horoscope generation failed for %s/%s", sign, lang)
                continue
            text = (f"<b>{HEADER.get(lang, HEADER['en'])}</b>\n"
                    f"{astro.SIGN_EMOJI[sign]} <b>{html.escape(astro.SIGN_NAMES[sign][lang])}</b>\n\n"
                    f"<i>{html.escape(h['title'])}</i>\n{html.escape(h['summary'])}")
            try:
                await bot.send_message(uid, text, reply_markup=open_app_kb(lang))
                sent += 1
            except Exception:
                pass  # user blocked the bot, etc.
            await asyncio.sleep(0.05)
    log.info("morning push sent to %s users", sent)


def start_scheduler(bot: Bot) -> AsyncIOScheduler | None:
    s = get_settings()
    if not s.morning_push_enabled:
        return None
    sched = AsyncIOScheduler(timezone=s.scheduler_timezone)
    sched.add_job(send_morning_horoscopes, "cron", hour=s.morning_push_hour, minute=0, args=[bot],
                  id="morning_push", coalesce=True, misfire_grace_time=3600)
    sched.start()
    return sched
