"""$Astro Oracle: FastAPI backend + aiogram bot in one process.

Run:  uvicorn app.main:app --host 0.0.0.0 --port 8000
"""
import asyncio
import contextlib
import hmac
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.ai.provider import AIError
from app.api import dreams, horoscope, kundli, practices, practices2, tarot, user
from app.config import get_settings
from app.db import init_models

settings = get_settings()
logging.basicConfig(level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("astro")

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
WEBHOOK_PATH = "/telegram/webhook"


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
            await bot.set_webhook(f"{settings.public_base_url.rstrip('/')}{WEBHOOK_PATH}",
                                  secret_token=settings.webhook_secret,
                                  allowed_updates=dp.resolve_used_update_types())
            log.info("Webhook set")
        else:  # local dev without HTTPS: fall back to long polling
            await bot.delete_webhook(drop_pending_updates=False)
            polling = asyncio.create_task(dp.start_polling(bot, handle_signals=False))
            log.warning("PUBLIC_BASE_URL is not https:// - using long polling (dev only)")
        if settings.webapp_url.startswith("https://"):
            await bot.set_chat_menu_button(menu_button=MenuButtonWebApp(
                text="🔮 Open", web_app=WebAppInfo(url=settings.webapp_url)))
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

if settings.cors_origins:
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=False,
                       allow_methods=["GET", "POST", "PATCH", "DELETE"], allow_headers=["Authorization", "Content-Type"])


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    if request.url.path.startswith("/api/"):
        response.headers.setdefault("Cache-Control", "no-store")
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
    await dp.feed_update(bot, update)
    return {"ok": True}


@app.get("/healthz", include_in_schema=False)
async def health():
    return {"ok": True}


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
async def index():
    page = STATIC_DIR / "index.html"
    if not page.exists():
        return JSONResponse({"detail": "Put your index.html in /static"}, status_code=404)
    return FileResponse(page, headers={"Cache-Control": "no-cache"})
