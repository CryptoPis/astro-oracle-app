from datetime import date, time
from typing import Literal

from fastapi import HTTPException, status
from pydantic import BaseModel, Field, field_validator

from app.core import astro
from app.models import User
from app.services.economy import today_utc

Lang = Literal["ka", "ru", "en"]
Period = Literal["day", "week", "month"]
Spread = Literal["daily", "single", "three"]


class ProfileUpdate(BaseModel):
    lang: Lang | None = None
    birth_date: date | None = Field(None, description="ISO YYYY-MM-DD (HTML <input type=date> format)")
    birth_time: time | None = Field(None, description="HH:MM, optional")
    birth_city: str | None = Field(None, max_length=128)

    @field_validator("birth_date")
    @classmethod
    def _sane_date(cls, v: date | None):
        if v and not (date(1900, 1, 1) <= v <= today_utc()):
            raise ValueError("birth_date out of range")
        return v

    @field_validator("birth_city")
    @classmethod
    def _strip(cls, v: str | None):
        return v.strip() or None if v else v


class TarotDrawRequest(BaseModel):
    spread: Spread = "daily"
    question: str | None = Field(None, max_length=300)


class DreamRequest(BaseModel):
    text: str = Field(min_length=10, max_length=2000)
    save: bool = True


def resolve_sign(user: User, sign: str | None) -> str:
    if sign:
        normalized = sign.strip().capitalize()
        if normalized not in astro.SIGNS:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, {"code": "bad_sign", "allowed": astro.SIGNS})
        return normalized
    if user.birth_date:
        return astro.zodiac_sign(user.birth_date)
    raise HTTPException(status.HTTP_400_BAD_REQUEST,
                        {"code": "needs_birth_date", "message": "Set birth_date or pass ?sign="})


def sign_info(sign: str, lang: str) -> dict:
    return {"id": sign, "name": astro.SIGN_NAMES[sign][lang], "emoji": astro.SIGN_EMOJI[sign],
            "element": astro.SIGN_ELEMENT[sign]}


def quota_exceeded(kind: str) -> HTTPException:
    return HTTPException(status.HTTP_429_TOO_MANY_REQUESTS,
                         {"code": "daily_quota", "message": f"Daily limit for {kind} reached. Come back tomorrow."})
