"""Vedic (sidereal, Lahiri) birth chart from real astronomical positions.

Planet positions come from astronomy-engine (pure Python, VSOP87/ELP based, ~1 arcminute).
Sidereal longitude = tropical longitude of date minus the Lahiri ayanamsa.
Houses use the whole-sign system from the ascendant (lagna), as is usual in Jyotish.
"""
import math
from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import astronomy as A

from app.core.astro import SIGNS

PLANETS = [("sun", A.Body.Sun), ("moon", A.Body.Moon), ("mars", A.Body.Mars), ("mercury", A.Body.Mercury),
           ("jupiter", A.Body.Jupiter), ("venus", A.Body.Venus), ("saturn", A.Body.Saturn)]
NAKSHATRAS = ["Ashwini", "Bharani", "Krittika", "Rohini", "Mrigashira", "Ardra", "Punarvasu", "Pushya", "Ashlesha",
              "Magha", "Purva Phalguni", "Uttara Phalguni", "Hasta", "Chitra", "Swati", "Vishakha", "Anuradha",
              "Jyeshtha", "Mula", "Purva Ashadha", "Uttara Ashadha", "Shravana", "Dhanishta", "Shatabhisha",
              "Purva Bhadrapada", "Uttara Bhadrapada", "Revati"]
J2000 = 2451545.0


@dataclass
class Place:
    name: str
    lat: float
    lon: float
    tz: str


def lahiri_ayanamsa(jd: float) -> float:
    """Lahiri (Chitrapaksha) ayanamsa, linear approximation (error < 1′ for 1900–2100)."""
    return 23.85306 + (jd - J2000) / 365.25 * (50.2788 / 3600)


def _tropical(body, t: A.Time) -> float:
    return A.Ecliptic(A.GeoVector(body, t, True)).elon % 360


def _mean_node(t: A.Time) -> float:
    T = t.tt / 36525.0
    return (125.04452 - 1934.136261 * T + 0.0020708 * T * T + T ** 3 / 450000) % 360


def _ascendant(t: A.Time, lat: float, lon: float) -> float:
    ramc = math.radians((A.SiderealTime(t) * 15 + lon) % 360)
    eps = math.radians(23.4392911 - 0.0130042 * t.tt / 36525.0)
    phi = math.radians(lat)
    return math.degrees(math.atan2(math.cos(ramc), -(math.sin(ramc) * math.cos(eps) + math.tan(phi) * math.sin(eps)))) % 360


def _point(pid: str, sid: float, retro: bool, lagna_sign: int | None) -> dict:
    s = int(sid // 30)
    return {"id": pid, "lon": round(sid, 3), "sign": SIGNS[s], "degree": round(sid % 30, 2), "retro": retro,
            "house": ((s - lagna_sign) % 12 + 1) if lagna_sign is not None else None}


def compute_chart(birth_date: date, birth_time: time | None, place: Place | None) -> dict:
    local = datetime.combine(birth_date, birth_time or time(12, 0))
    if place:
        try:
            local = local.replace(tzinfo=ZoneInfo(place.tz))
        except ZoneInfoNotFoundError:
            local = local.replace(tzinfo=timezone.utc)
    else:
        local = local.replace(tzinfo=timezone.utc)
    utc = local.astimezone(timezone.utc)
    t = A.Time.Make(utc.year, utc.month, utc.day, utc.hour, utc.minute, utc.second)
    t_next = t.AddDays(1)
    ayan = lahiri_ayanamsa(t.ut + J2000)

    asc = None
    lagna_sign = None
    if birth_time is not None and place is not None:
        asc_sid = (_ascendant(t, place.lat, place.lon) - ayan) % 360
        lagna_sign = int(asc_sid // 30)
        asc = {"sign": SIGNS[lagna_sign], "degree": round(asc_sid % 30, 2), "lon": round(asc_sid, 3)}

    planets = []
    for pid, body in PLANETS:
        sid = (_tropical(body, t) - ayan) % 360
        retro = False
        if pid not in ("sun", "moon"):
            delta = ((_tropical(body, t_next) - _tropical(body, t)) + 540) % 360 - 180
            retro = delta < 0
        planets.append(_point(pid, sid, retro, lagna_sign))
    rahu = (_mean_node(t) - ayan) % 360
    planets.append(_point("rahu", rahu, True, lagna_sign))
    planets.append(_point("ketu", (rahu + 180) % 360, True, lagna_sign))

    moon = next(p for p in planets if p["id"] == "moon")["lon"]
    span = 360 / 27
    nak = {"name": NAKSHATRAS[int(moon // span)], "pada": int((moon % span) // (span / 4)) + 1}
    return {"planets": planets, "ascendant": asc, "moon_nakshatra": nak, "ayanamsa": round(ayan, 4),
            "has_time": birth_time is not None, "has_place": place is not None,
            "place": place and {"name": place.name, "lat": round(place.lat, 3), "lon": round(place.lon, 3), "tz": place.tz},
            "utc": utc.isoformat()}


def chart_summary(chart: dict) -> str:
    """Compact text for the AI prompt and for the cache key."""
    parts = [f"{p['id']}={p['sign']} {p['degree']:.0f}°{' R' if p['retro'] and p['id'] not in ('rahu', 'ketu') else ''}"
             + (f" H{p['house']}" if p["house"] else "") for p in chart["planets"]]
    asc = chart["ascendant"]
    return (f"Lagna: {asc['sign'] + ' ' + format(asc['degree'], '.0f') + '°' if asc else 'unknown (no birth time/place)'}; "
            f"Moon nakshatra: {chart['moon_nakshatra']['name']} pada {chart['moon_nakshatra']['pada']}; " + ", ".join(parts))
