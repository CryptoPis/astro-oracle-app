"""Natal chart, transits, aspects, ranking, cache keys and the personal horoscope API."""
import os
from datetime import date, datetime, time, timezone

os.environ.setdefault("BOT_TOKEN", "123456:TEST-TOKEN")

import astronomy as A  # noqa: E402

from app.core import transits as T  # noqa: E402
from app.core.chart import Place  # noqa: E402

TBILISI = Place("Tbilisi", 41.72, 44.78, "Asia/Tbilisi")


def test_natal_positions_match_reference_and_astronomy_engine():
    # J2000 (2000-01-01 12:00 UTC): Sun ~10° Capricorn, Jupiter ~25° Aries, Saturn ~10° Taurus (standard ephemerides)
    n = T.natal_chart(date(2000, 1, 1), time(12, 0), None)
    assert abs(n["points"]["sun"] - 280.4) < 0.5
    assert abs(n["points"]["jupiter"] - 25.2) < 0.7 and abs(n["points"]["saturn"] - 40.4) < 0.7
    assert n["asc"] is None and "asc" not in n["points"]
    # same numbers as asking astronomy-engine directly
    when = datetime(2026, 10, 20, 12, 0, tzinfo=timezone.utc)
    t = A.Time.Make(2026, 10, 20, 12, 0, 0)
    pos = T.positions(when)
    for pid, body in T.BODIES.items():
        assert abs(pos[pid][0] - A.Ecliptic(A.GeoVector(body, t, True)).elon % 360) < 1e-6
    # Mercury was retrograde on 2024-04-08 (1-25 April 2024)
    assert T.positions(datetime(2024, 4, 8, 12, tzinfo=timezone.utc))["mercury"][1] < 0


def test_birth_time_and_city_add_the_ascendant_and_change_the_fingerprint():
    a = T.natal_chart(date(1990, 8, 15), time(8, 0), TBILISI)
    b = T.natal_chart(date(1990, 8, 15), None, None)
    assert a["asc"] is not None and 120 <= a["asc"] < 180          # Leo rising for 08:00 in Tbilisi
    assert a["fingerprint"] != b["fingerprint"]
    assert T.natal_chart(date(1990, 8, 15), time(8, 0), TBILISI)["fingerprint"] == a["fingerprint"]


def test_aspect_detection_and_orbs():
    natal = {"sun": 100.0}
    hit = T.aspects_at({"mars": (190.0, 0.6)}, natal, include_moon=False)
    assert [(h["transit"], h["aspect"], h["orb"]) for h in hit] == [("mars", "square", 0.0)]
    assert T.aspects_at({"mars": (193.5, 0.6)}, natal, False) == []        # 3.5° > Mars square orb 2.5°
    assert T.aspects_at({"saturn": (221.5, 0.05)}, natal, False)[0]["aspect"] == "trine"
    assert T.aspects_at({"moon": (100.5, 13)}, natal, include_moon=False) == []
    assert T.aspects_at({"moon": (100.5, 13)}, natal, include_moon=True)[0]["aspect"] == "conjunction"
    assert T.aspects_at({"jupiter": (281.0, 0.2)}, natal, False)[0]["aspect"] == "opposition"   # wraps around 360


def test_ranking_prefers_slow_planets_tight_orbs_and_hard_aspects():
    def item(tp, np, aid, orb):
        return {"transit": tp, "natal": np, "aspect": aid, "orb": orb, "max_orb": T.load("aspects")[aid]["orb"] * T.ORB_SCALE[tp]}
    saturn_square_sun = item("saturn", "sun", "square", 0.3)
    venus_sextile_mercury = item("venus", "mercury", "sextile", 0.3)
    loose = item("saturn", "sun", "square", 2.0)
    assert T.score(saturn_square_sun) > T.score(loose) > T.score(venus_sextile_mercury)


def test_transits_for_a_real_period():
    n = T.natal_chart(date(1990, 8, 15), time(8, 0), TBILISI)
    day = T.transits_for(n, "day", date(2026, 10, 20))
    week = T.transits_for(n, "week", date(2026, 10, 20))
    assert 1 <= len(day["transits"]) <= 4 and len(week["transits"]) <= 5
    assert [t["id"] for t in day["transits"]] == [f"T{i}" for i in range(1, len(day["transits"]) + 1)]
    assert all(t["transit"] != "moon" for t in week["transits"])          # the Moon only counts for the day
    assert day["transits"][0]["score"] >= day["transits"][-1]["score"]
    assert all(1 <= t["house"] <= 12 for t in day["transits"])            # houses known (time + city given)
    # Jupiter in Leo conjunct the natal Sun (22° Leo) in October 2026; Venus retrograde from 3 October
    assert any(t["transit"] == "jupiter" and t["natal"] == "sun" and t["aspect"] == "conjunction" for t in day["transits"])
    assert "venus" in day["retrograde"]
    t1 = day["transits"][0]
    assert T.label(t1, "ka").count("შენი") == 1 and T.label(t1, "en").count("your") == 1
    assert "T1:" in T.describe_for_ai(t1, "ka")


def test_cache_key_is_per_natal_chart_period_and_language():
    from app.services.content import personal_key
    a = T.natal_chart(date(1990, 8, 15), time(8, 0), TBILISI)
    b = T.natal_chart(date(1990, 8, 15), time(9, 0), TBILISI)
    d = date(2026, 10, 20)
    assert personal_key(a, "day", d, "ka") == personal_key(a, "day", d, "ka")
    assert len({personal_key(a, "day", d, "ka"), personal_key(b, "day", d, "ka"), personal_key(a, "day", d, "en"),
                personal_key(a, "week", d, "ka")}) == 4
    assert personal_key(a, "week", d, "ka") == personal_key(a, "week", date(2026, 10, 22), "ka")   # same ISO week
