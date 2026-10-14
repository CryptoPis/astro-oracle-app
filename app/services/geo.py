"""Birth-place lookup via the free Open-Meteo geocoding API (no key needed). Results are cached."""
import logging

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.chart import Place
from app.services.content import cached_ai

log = logging.getLogger(__name__)
URL = "https://geocoding-api.open-meteo.com/v1/search"


async def _lookup(city: str) -> dict:
    async with httpx.AsyncClient(timeout=8) as client:
        r = await client.get(URL, params={"name": city, "count": 1, "format": "json"})
        r.raise_for_status()
        res = (r.json().get("results") or [None])[0]
    if not res:
        return {"found": False}
    return {"found": True, "name": f"{res['name']}, {res.get('country', '')}".strip(", "),
            "lat": res["latitude"], "lon": res["longitude"], "tz": res.get("timezone") or "UTC"}


async def geocode(session: AsyncSession, city: str) -> Place | None:
    key = city.strip().lower()[:120]
    try:
        data, _ = await cached_ai(session, "geo", key, lambda: _lookup(city.strip()))
    except Exception:
        log.warning("geocoding failed for %r", city, exc_info=True)
        return None
    return Place(data["name"], data["lat"], data["lon"], data["tz"]) if data.get("found") else None
