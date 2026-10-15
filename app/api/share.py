"""Share-to-story images. Telegram's shareToStory needs a public HTTPS URL, so the Mini App uploads the card it
rendered on a canvas and gets a short-lived link back. Images live in memory only (one process on Render):
at most MAX_ITEMS, each deleted after TTL seconds. Uploads need a logged-in user and are capped per day.
"""
import secrets
import time
from collections import OrderedDict

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session
from app.models import User
from app.security import current_user
from app.services import economy

router = APIRouter(tags=["share"])

MAX_BYTES = 3 * 1024 * 1024
MAX_ITEMS = 200
TTL = 3600
DAILY_UPLOADS = 20
_images: "OrderedDict[str, tuple[bytes, str, float]]" = OrderedDict()
_MAGIC = {b"\x89PNG\r\n\x1a\n": ("png", "image/png"), b"\xff\xd8\xff": ("jpg", "image/jpeg")}


def _sweep(now: float) -> None:
    for key in [k for k, (_, _, exp) in _images.items() if exp < now]:
        del _images[key]
    while len(_images) > MAX_ITEMS:
        _images.popitem(last=False)


@router.post("/api/share/image")
async def upload(file: UploadFile = File(...), user: User = Depends(current_user),
                 session: AsyncSession = Depends(get_session)):
    raw = await file.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, {"code": "too_large"})
    kind = next((v for magic, v in _MAGIC.items() if raw.startswith(magic)), None)
    if kind is None:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, {"code": "bad_image"})
    if not await economy.bump_counter(session, user.telegram_id, "share", DAILY_UPLOADS):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, {"code": "daily_quota"})
    await session.commit()
    now = time.time()
    _sweep(now)
    name = f"{secrets.token_urlsafe(12)}.{kind[0]}"
    _images[name] = (raw, kind[1], now + TTL)
    return {"url": f"{get_settings().public_base_url}/share/{name}", "expires_in": TTL}


@router.get("/share/{name}", include_in_schema=False)
async def serve(name: str):
    item = _images.get(name)
    if item is None or item[2] < time.time():
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    return Response(item[0], media_type=item[1], headers={"Cache-Control": f"public, max-age={TTL}"})
