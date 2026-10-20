"""Moon ritual, compatibility, AI astrologer, aura and coffee photo readings."""
import io
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai import prompts as P
from app.ai.provider import AIError, get_ai
from app.api.common import quota_exceeded, sign_info
from app.core import astro
from app.db import get_session
from app.models import Reading, User
from app.security import current_user
from app.services import economy
from app.services.content import cached_ai

router = APIRouter(prefix="/api", tags=["practices"])


def _need_birth(user: User) -> None:
    if not user.birth_date:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, {"code": "needs_birth_date"})


# ───────────────────────── Moon ritual ─────────────────────────
@router.get("/moon/ritual")
async def moon_ritual(user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    day = economy.today_utc()
    moon_en, moon = astro.moon_phase("en"), astro.moon_phase(user.lang)

    async def gen():
        system, prompt = P.moon_ritual_prompt(user.lang, moon_en["name"], moon_en["illumination"], day.isoformat(), moon_en["code"])
        return (await get_ai().complete_json(system, prompt, P.MoonRitualAI, max_tokens=700)).model_dump()

    ritual, _ = await cached_ai(session, "moon", f"{moon['code']}:{day.isoformat()}:{user.lang}", gen)
    reward = await economy.grant_action_reward(session, user.telegram_id, "moon")
    await session.commit()
    return {"moon": moon, "ritual": ritual, "reward": reward}


# ───────────────────────── Compatibility ─────────────────────────
_ELEMENT_BASE = {frozenset(["fire"]): 84, frozenset(["earth"]): 82, frozenset(["air"]): 83, frozenset(["water"]): 86,
                 frozenset(["fire", "air"]): 80, frozenset(["earth", "water"]): 81,
                 frozenset(["fire", "earth"]): 58, frozenset(["air", "water"]): 60,
                 frozenset(["fire", "water"]): 54, frozenset(["air", "earth"]): 56}
_ASPECT = {0: 2, 1: -4, 2: 6, 3: -8, 4: 9, 5: -5, 6: 3}  # distance in signs -> bonus (trine best, square hardest)


def compat_percent(a: str, b: str) -> int:
    base = _ELEMENT_BASE[frozenset([astro.SIGN_ELEMENT[a], astro.SIGN_ELEMENT[b]])]
    d = abs(astro.SIGNS.index(a) - astro.SIGNS.index(b)) % 12
    return max(35, min(97, base + _ASPECT[min(d, 12 - d)]))


class CompatRequest(BaseModel):
    partner_birth_date: date
    partner_name: str | None = Field(None, max_length=40)

    @field_validator("partner_birth_date")
    @classmethod
    def _sane(cls, v: date):
        if not (date(1900, 1, 1) <= v <= economy.today_utc()):
            raise ValueError("partner_birth_date out of range")
        return v


@router.post("/compatibility")
async def compatibility(body: CompatRequest, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    _need_birth(user)
    me, other = astro.zodiac_sign(user.birth_date), astro.zodiac_sign(body.partner_birth_date)
    a, b = sorted([me, other], key=astro.SIGNS.index)
    percent = compat_percent(a, b)

    async def gen():
        system, prompt = P.compat_prompt(user.lang, a, b, percent)
        return (await get_ai().complete_json(system, prompt, P.CompatAI, max_tokens=900)).model_dump()

    reading, _ = await cached_ai(session, "compat", f"{a}:{b}:{user.lang}", gen)  # 78 pairs x 3 languages at most
    reward = await economy.grant_action_reward(session, user.telegram_id, "compatibility")
    name = (body.partner_name or "").strip() or None
    session.add(Reading(user_id=user.telegram_id, kind="compat", variant=f"{me}-{other}", day=economy.today_utc(),
                        question=name, payload={"percent": percent, **reading}))
    await session.commit()
    return {"you": sign_info(me, user.lang), "partner": {**sign_info(other, user.lang), "name": name},
            "percent": percent, "reading": reading, "reward": reward}


# ───────────────────────── AI astrologer ─────────────────────────
class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    text: str = Field(max_length=1500)


class AdvisorRequest(BaseModel):
    message: str = Field(min_length=2, max_length=600)
    history: list[ChatTurn] = Field(default_factory=list, max_length=8)


@router.post("/advisor")
async def advisor(body: AdvisorRequest, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    uid = user.telegram_id
    if not await economy.consume_ai_quota(session, uid, "advisor"):
        raise quota_exceeded("advisor")
    await session.commit()
    moon = astro.moon_phase("en")
    if user.birth_date:
        sign = astro.zodiac_sign(user.birth_date)
        profile = (f"sun sign {sign} ({astro.SIGN_ELEMENT[sign]}), born {user.birth_date.isoformat()}"
                   f"{', ' + user.birth_city if user.birth_city else ''}, life path {astro.life_path_number(user.birth_date)}")
    else:
        profile = "birth date unknown"
    profile += f"; today {economy.today_utc().isoformat()}, moon: {moon['name']}"
    system, prompt = P.advisor_prompt(user.lang, profile, [t.model_dump() for t in body.history[-8:]], body.message.strip())
    try:
        ai = await get_ai().complete_json(system, prompt, P.AdvisorAI, max_tokens=700)
    except AIError:
        await economy.release_counter(session, uid, "ai:advisor")
        await session.commit()
        raise
    reward = await economy.grant_action_reward(session, uid, "advisor")
    left = economy.AI_DAILY_CAPS["advisor"] - await economy.counter_value(session, uid, "ai:advisor")
    await session.commit()
    return {**ai.model_dump(), "messages_left": left, "reward": reward}


# ───────────────────────── Photo readings ─────────────────────────
MAX_UPLOAD = 8 * 1024 * 1024
VISION = {"aura": (P.aura_prompt, P.AuraAI, "aura"), "coffee": (P.coffee_prompt, P.CoffeeAI, "coffee")}


def prepare_image(raw: bytes) -> bytes:
    """Validates the upload and re-encodes it as a ≤1024px JPEG (strips EXIF/location data)."""
    from PIL import Image, ImageOps, UnidentifiedImageError
    try:
        im = Image.open(io.BytesIO(raw))
        im.verify()
        im = ImageOps.exif_transpose(Image.open(io.BytesIO(raw))).convert("RGB")
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, {"code": "bad_photo", "message": "Not an image."}) from e
    im.thumbnail((1024, 1024))
    out = io.BytesIO()
    im.save(out, "JPEG", quality=85)
    return out.getvalue()


@router.post("/vision/{kind}")
async def vision(kind: Literal["aura", "coffee"], file: UploadFile = File(...), user: User = Depends(current_user),
                 session: AsyncSession = Depends(get_session)):
    raw = await file.read(MAX_UPLOAD + 1)
    if len(raw) > MAX_UPLOAD:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, {"code": "too_large", "message": "Photo is larger than 8 MB."})
    image = prepare_image(raw)
    uid = user.telegram_id
    if not await economy.consume_ai_quota(session, uid, "vision"):
        raise quota_exceeded(kind)
    await session.commit()
    prompt_fn, schema, action = VISION[kind]
    system, prompt = prompt_fn(user.lang)
    try:
        ai = await get_ai().complete_json(system, prompt, schema, max_tokens=900, image=image)
    except AIError:
        await economy.release_counter(session, uid, "ai:vision")
        await session.commit()
        raise
    if not ai.image_ok:
        await economy.release_counter(session, uid, "ai:vision")
        await session.commit()
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, {"code": "bad_photo", "message": "Photo does not fit this reading."})
    payload = ai.model_dump(exclude={"image_ok"})
    session.add(Reading(user_id=uid, kind=kind, variant=None, day=economy.today_utc(), payload=payload))  # the photo itself is not stored
    reward = await economy.grant_action_reward(session, uid, action)
    await session.commit()
    return {"kind": kind, "reading": payload, "reward": reward}
