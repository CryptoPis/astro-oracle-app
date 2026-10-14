"""$Astro Oracle: FastAPI backend + aiogram bot in one process.

Run:  uvicorn app.main:app --host 0.0.0.0 --port 8000
Render: see render.yaml (single worker; the bot dispatcher and the scheduler live in this process).
"""
import asyncio
import contextlib
import hmac
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.ai.provider import AIError
from app.api import dreams, horoscope, kundli, practices, practices2, tarot, user
from app.config import get_settings
from app.db import init_models, ping

settings = get_settings()
logging.basicConfig(level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("astro")

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
WEBHOOK_PATH = "/telegram/webhook"
_background: set[asyncio.Task] = set()


def run_in_background(coro) -> None:
    task = asyncio.create_task(coro)
    _background.add(task)
    task.add_done_callback(_background.discard)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_models()
    bot = dp = sched = polling = None
    if settings.bot_enabled:
        from aiogram.types import MenuButtonWebApp, WebAppInfo
        from app.bot.handlers import build_bot
        from app.bot.scheduler import start_scheduler

        bot, dp = build_bot()
        app.state.bot, app.state.dp = bot, dp
        if settings.webhook_enabled:
            url = f"{settings.public_base_url}{WEBHOOK_PATH}"
            try:
                await bot.set_webhook(url, secret_token=settings.webhook_secret,
                                      allowed_updates=dp.resolve_used_update_types())
                log.info("Webhook set to %s", url)
            except Exception:
                log.exception("Could not set the Telegram webhook (check BOT_TOKEN)")
        else:  # local dev without HTTPS: fall back to long polling
            await bot.delete_webhook(drop_pending_updates=False)
            polling = asyncio.create_task(dp.start_polling(bot, handle_signals=False))
            log.warning("PUBLIC_BASE_URL is not https:// - using long polling (dev only)")
        if settings.webapp_url.startswith("https://"):
            with contextlib.suppress(Exception):
                await bot.set_chat_menu_button(menu_button=MenuButtonWebApp(
                    text="🔮 Open", web_app=WebAppInfo(url=settings.webapp_url)))
        if settings.morning_push_mode == "internal":
            sched = start_scheduler(bot)
    yield
    if sched:
        sched.shutdown(wait=False)
    if polling:
        await dp.stop_polling()
        polling.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await polling
    if bot:
        await bot.session.close()


app = FastAPI(title="$Astro Oracle API", version="2.0.0", lifespan=lifespan,
              docs_url="/docs" if settings.is_dev else None, redoc_url=None)

app.add_middleware(GZipMiddleware, minimum_size=1024)   # index.html ~100 KB -> ~25 KB

if settings.cors_origins:
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=False,
                       allow_methods=["GET", "POST", "PATCH", "DELETE"], allow_headers=["Authorization", "Content-Type"])


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    path = request.url.path
    if path.startswith("/api/"):
        response.headers.setdefault("Cache-Control", "no-store")
    elif path.startswith("/static/img/"):
        # art never changes under the same name: let phones keep it for a week
        response.headers["Cache-Control"] = "public, max-age=604800, stale-while-revalidate=86400"
    return response


@app.exception_handler(AIError)
async def ai_error_handler(_: Request, exc: AIError):
    return JSONResponse(status_code=503, content={"detail": {
        "code": "ai_unavailable", "message": "The stars are clouded right now. Please try again in a moment."}})


for r in (user.auth_router, user.user_router, horoscope.router, tarot.router, dreams.router, practices.router, practices2.router, kundli.router):
    app.include_router(r)


@app.post(WEBHOOK_PATH, include_in_schema=False)
async def telegram_webhook(request: Request):
    token = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if not settings.webhook_secret or not hmac.compare_digest(token, settings.webhook_secret):
        raise HTTPException(403)
    from aiogram.types import Update
    bot, dp = request.app.state.bot, request.app.state.dp
    update = Update.model_validate(await request.json(), context={"bot": bot})
    # Answer Telegram at once; slow handlers (e.g. /send to all users) must not make Telegram resend the update.
    run_in_background(dp.feed_update(bot, update))
    return {"ok": True}


@app.get("/healthz", include_in_schema=False)
async def health(deep: bool = False):
    """Light check for uptime pings (cron-job.org). ?deep=1 also checks the database."""
    if not deep:
        return {"ok": True}
    try:
        await ping()
        return {"ok": True, "db": "ok"}
    except Exception as e:
        log.exception("database ping failed")
        return JSONResponse(status_code=503, content={"ok": False, "db": type(e).__name__})


def _check_cron(key: str) -> None:
    if not settings.cron_secret or not hmac.compare_digest(key or "", settings.cron_secret):
        raise HTTPException(403)


@app.api_route("/cron/morning", methods=["GET", "POST"], include_in_schema=False)
async def cron_morning(key: str = ""):
    """Called once a day by an outside cron (cron-job.org): sends the morning horoscope and warms the AI cache.
    Returns immediately; the work continues in the background."""
    _check_cron(key)
    from app.bot.scheduler import send_morning_horoscopes
    bot = getattr(app.state, "bot", None)
    if bot is None:
        raise HTTPException(503, "bot disabled")
    run_in_background(send_morning_horoscopes(bot))
    return JSONResponse(status_code=202, content={"ok": True, "started": True})


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
async def index():
    page = STATIC_DIR / "index.html"
    if not page.exists():
        return JSONResponse({"detail": "Put your index.html in /static"}, status_code=404)
    return FileResponse(page, headers={"Cache-Control": "no-cache"})
