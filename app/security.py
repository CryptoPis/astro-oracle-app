"""Telegram Mini App authentication.

The frontend sends the raw `Telegram.WebApp.initData` string on every request:

    Authorization: tma <initData>

Validation follows https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app

    secret_key       = HMAC_SHA256(key="WebAppData", msg=BOT_TOKEN)
    data_check_string = "\\n".join(sorted(f"{k}={v}" for every field except "hash"))
    valid            = HMAC_SHA256(key=secret_key, msg=data_check_string).hex() == hash

The check is stateless and runs on every request (it costs microseconds), so
there are no session tokens to store, leak or expire. Never trust
`initDataUnsafe` on the client.
"""
import hashlib
import hmac
import json
import time
from dataclasses import dataclass, field
from urllib.parse import parse_qsl, urlencode

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session
from app.models import User

_FUTURE_SKEW = 60  # seconds of clock skew tolerated for auth_date in the future


@dataclass
class InitData:
    user: dict
    auth_date: int
    start_param: str | None = None
    query_id: str | None = None
    raw: dict = field(default_factory=dict)

    @property
    def user_id(self) -> int:
        return int(self.user["id"])


class InitDataError(ValueError):
    pass


def _secret_key(bot_token: str) -> bytes:
    return hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()


def _check_string(pairs: dict[str, str]) -> str:
    return "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()) if k != "hash")


def validate_init_data(init_data: str, bot_token: str, max_age: int) -> InitData:
    if not init_data:
        raise InitDataError("empty initData")
    try:
        pairs = dict(parse_qsl(init_data, keep_blank_values=True, strict_parsing=True))
    except ValueError as e:
        raise InitDataError("malformed initData") from e

    received = pairs.get("hash")
    if not received:
        raise InitDataError("hash missing")

    expected = hmac.new(_secret_key(bot_token), _check_string(pairs).encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, received):
        raise InitDataError("bad signature")

    try:
        auth_date = int(pairs["auth_date"])
    except (KeyError, ValueError) as e:
        raise InitDataError("auth_date missing") from e
    now = int(time.time())
    if auth_date > now + _FUTURE_SKEW:
        raise InitDataError("auth_date in the future")
    if max_age and now - auth_date > max_age:
        raise InitDataError("initData expired")

    try:
        user = json.loads(pairs["user"])
        int(user["id"])
    except (KeyError, ValueError, TypeError) as e:
        raise InitDataError("user missing") from e

    return InitData(user=user, auth_date=auth_date, start_param=pairs.get("start_param"),
                    query_id=pairs.get("query_id"), raw=pairs)


def sign_init_data(fields: dict, bot_token: str) -> str:
    """Builds a valid initData string. For tests and local tooling only."""
    pairs = {k: (json.dumps(v, separators=(",", ":")) if isinstance(v, dict) else str(v))
             for k, v in fields.items()}
    pairs["hash"] = hmac.new(_secret_key(bot_token), _check_string(pairs).encode(),
                             hashlib.sha256).hexdigest()
    return urlencode(pairs)


# ───────────────────────── FastAPI dependencies ─────────────────────────

async def require_init_data(request: Request) -> InitData:
    s = get_settings()
    header = request.headers.get("Authorization", "")
    scheme, _, raw = header.partition(" ")

    if s.is_dev and s.dev_auth_bypass and not raw:
        return InitData(user={"id": s.dev_user_id, "first_name": "Dev", "language_code": "en"},
                        auth_date=int(time.time()))

    if scheme.lower() != "tma" or not raw:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing Telegram initData",
                            headers={"WWW-Authenticate": "tma"})
    try:
        return validate_init_data(raw, s.bot_token, s.init_data_max_age)
    except InitDataError as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"invalid initData: {e}") from e


async def current_user(init: InitData = Depends(require_init_data),
                       session: AsyncSession = Depends(get_session)) -> User:
    from app.services.users import upsert_user  # avoid import cycle
    user = await session.get(User, init.user_id)
    if user is None:  # first call wasn't /auth/verify; create the user without a referral
        user, _ = await upsert_user(session, init, with_referral=False)
        await session.commit()
    if user.is_blocked:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "account blocked")
    return user
