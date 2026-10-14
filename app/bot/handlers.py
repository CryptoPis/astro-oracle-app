"""Slim Telegram bot. All features now live in the Mini App; the bot is the
entry point (/start plus menu button), handles legacy referral links, sends
notifications, and keeps the admin commands."""
import asyncio
import html

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message, WebAppInfo
from sqlalchemy import func, select

from app.config import get_settings
from app.db import SessionLocal
from app.models import User
from app.services.users import apply_referral, get_or_create, parse_ref

settings = get_settings()
router = Router()

WELCOME = {
    "ka": "✨ <b>მოგესალმები $Astro ✧ Oracle-ში!</b>\n\nჰოროსკოპი, ტარო, სიზმრების ახსნა და 🪐 $AST ჯილდოები. ყველაფერი ერთ აპლიკაციაში.",
    "ru": "✨ <b>Добро пожаловать в $Astro ✧ Oracle!</b>\n\nГороскопы, таро, толкование снов и награды 🪐 $AST в одном приложении.",
    "en": "✨ <b>Welcome to $Astro ✧ Oracle!</b>\n\nHoroscopes, tarot, dream interpretation and 🪐 $AST rewards, all in one app.",
}
OPEN_BTN = {"ka": "🔮 აპლიკაციის გახსნა", "ru": "🔮 Открыть приложение", "en": "🔮 Open the app"}


def open_app_kb(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=OPEN_BTN.get(lang, OPEN_BTN["en"]), web_app=WebAppInfo(url=settings.webapp_url))]])


def is_admin(m: Message) -> bool:
    return m.from_user is not None and m.from_user.id in settings.admin_ids


@router.message(CommandStart())
async def cmd_start(message: Message, command: CommandObject):
    async with SessionLocal() as session:
        user, is_new = await get_or_create(session, message.from_user.model_dump())
        if is_new:  # legacy links: t.me/astrogm2026bot?start=<inviter_id>
            await apply_referral(session, user, parse_ref(command.args))
        await session.commit()
        lang = user.lang
    await message.answer(WELCOME.get(lang, WELCOME["en"]), reply_markup=open_app_kb(lang))


@router.message(Command("stats"), F.func(is_admin))
async def cmd_stats(message: Message):
    async with SessionLocal() as s:
        total = await s.scalar(select(func.count()).select_from(User))
        coins = await s.scalar(select(func.coalesce(func.sum(User.astro_coins), 0)))
        langs = (await s.execute(select(User.lang, func.count()).group_by(User.lang))).all()
    lines = "\n".join(f"• {(l or '?').upper()}: {c}" for l, c in langs)
    await message.answer(f"📊 <b>Stats</b>\n👥 Users: <b>{total}</b>\n🪐 $AST in circulation: <b>{coins:,}</b>\n{lines}")


@router.message(Command("send"), F.func(is_admin))
async def cmd_broadcast(message: Message, command: CommandObject, bot: Bot):
    text = (command.args or "").strip()
    if not text:
        return await message.answer("Usage: /send your text")
    async with SessionLocal() as s:
        ids = (await s.scalars(select(User.telegram_id).where(User.is_blocked.is_(False)))).all()
    ok = fail = 0
    status = await message.answer(f"⏳ Sending to {len(ids)}…")
    for uid in ids:
        try:
            await bot.send_message(uid, html.escape(text))
            ok += 1
        except Exception:
            fail += 1
        await asyncio.sleep(0.05)  # stay under Telegram's ~30 msg/s limit
    await status.edit_text(f"✅ Sent: <b>{ok}</b>\n❌ Failed/blocked: <b>{fail}</b>")


@router.message(Command("diag"), F.func(is_admin))
async def cmd_diag(message: Message, bot: Bot):
    from app.services.diag import format_report, run_checks
    status = await message.answer("🔎 Checking keys and services…")
    await status.edit_text(format_report(await run_checks(bot), html=True))


def build_bot() -> tuple[Bot, Dispatcher]:
    bot = Bot(token=settings.bot_token, default=DefaultBotProperties(parse_mode="HTML"))
    dp = Dispatcher()
    dp.include_router(router)
    return bot, dp
