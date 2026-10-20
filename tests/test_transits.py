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


def test_cache_key_is_shared_by_matching_transits_and_split_by_period_and_language():
    from app.services.content import personal_plan
    a = T.natal_chart(date(1990, 8, 15), time(8, 0), TBILISI)
    d = date(2026, 10, 20)
    key = lambda n, period="day", lang="ka", day=d: personal_plan(n, "Leo", period, day, lang)["key"]
    assert key(a) == key(a)
    assert len({key(a), key(a, lang="en"), key(a, "week"), key(a, "month")}) == 4
    assert key(a, "week") == key(a, "week", day=date(2026, 10, 22))            # same ISO week
    # a chart whose natal points differ by a few arc-minutes has the same top transits: one shared text
    twin = {**a, "points": {k: v + 0.05 for k, v in a["points"]. items()}, "fingerprint": "other"}
    assert key(twin) == key(a)
    # an unknown birth time changes what the text may say (no houses), so it never shares with a timed chart
    assert key(T.natal_chart(date(1990, 8, 15), None, None)) != key(a)


def test_essential_dignities_follow_lilly_and_ptolemy():
    kb = T.load("dignities")
    sign_at = {s: i * 30 + 15 for i, s in enumerate(T.SIGNS)}
    assert T.dignity("mars", sign_at["Aries"]) == "domicile" and T.dignity("mars", sign_at["Scorpio"]) == "domicile"
    assert T.dignity("jupiter", sign_at["Cancer"]) == "exaltation" and T.dignity("jupiter", sign_at["Capricorn"]) == "fall"
    assert T.dignity("venus", sign_at["Scorpio"]) == "detriment" and T.dignity("sun", sign_at["Libra"]) == "fall"
    assert T.dignity("saturn", sign_at["Libra"]) == "exaltation" and T.dignity("moon", sign_at["Taurus"]) == "exaltation"
    assert T.dignity("mercury", sign_at["Leo"]) is None                     # peregrine
    assert T.dignity("uranus", sign_at["Aquarius"]) is None                 # outer planets have no essential dignity
    opposite = lambda s: T.SIGNS[(T.SIGNS.index(s) + 6) % 12]
    for p in ("sun", "moon", "mercury", "venus", "mars", "jupiter", "saturn"):
        assert sorted(kb["detriment"][p]) == sorted(opposite(s) for s in kb["domicile"][p])   # detriment faces home
        assert kb["fall"][p] == opposite(kb["exaltation"][p])                                  # fall faces exaltation
    for sign, terms in kb["terms"].items():
        assert len(terms) == 5 and terms[-1][1] == 30 and [b for _, b in terms] == sorted(b for _, b in terms)
    chaldean = ["saturn", "jupiter", "mars", "sun", "venus", "mercury", "moon"]
    faces = [f for s in T.SIGNS for f in kb["faces"][s]]
    assert faces[0] == "mars" and all(chaldean.index(b) == (chaldean.index(a) + 1) % 7 for a, b in zip(faces, faces[1:]))
    assert kb["triplicity"]["water"] == {"day": "mars", "night": "mars"}    # Lilly / Ptolemy, see the notes
    # dignity changes the ranking and shows up as a 'why' chip
    base = {"transit": "jupiter", "natal": "sun", "aspect": "trine", "orb": 1.0, "max_orb": 2.25}
    assert T.score({**base, "dignity": "exaltation"}) > T.score(base)
    assert T.dignity_label({**base, "dignity": "exaltation"}, "ka") == "იუპიტერი ამაღლებაში"
    assert T.dignity_label({**base, "dignity": "fall"}, "ru") == "Юпитер в падении"


def test_outer_planet_transits_rank_by_sepharial_and_use_the_pair_meaning():
    def item(tp, aid="square", **kw):   # same relative closeness for every planet (orb = 20% of its max orb)
        max_orb = T.load("aspects")[aid]["orb"] * T.ORB_SCALE[tp]
        return {"transit": tp, "natal": "venus", "aspect": aid, "orb": 0.2 * max_orb, "max_orb": max_orb, "applying": True, "nature": "challenging", "id": "T1", **kw}
    # rarer = weightier: Neptune > Uranus > Pluto > Saturn > Jupiter > Mars
    order = [T.score(item(p)) for p in ("neptune", "uranus", "pluto", "saturn", "jupiter", "mars")]
    assert order == sorted(order, reverse=True)
    # stationary > retrograde > direct; two planets on one point weigh more
    assert T.motion("saturn", 0.002) == "stationary" and T.motion("saturn", -0.03) == "retrograde"
    assert T.motion("pluto", 0.01) == "direct" and T.motion("sun", 0.0) == "direct"
    assert T.score(item("saturn", motion="stationary")) > T.score(item("saturn", motion="retrograde")) > T.score(item("saturn"))
    assert T.score(item("uranus", double=True)) > T.score(item("uranus"))
    kb = T.load("transits")
    for tp in ("uranus", "neptune", "pluto", "saturn", "jupiter", "mars"):
        for np in ("sun", "moon", "mercury", "venus", "mars", "jupiter", "saturn", "asc"):
            assert f"{tp}>{np}" in kb, f"{tp}>{np}"
    line = T.describe_for_ai(item("neptune", motion="stationary", double=True), "ka")
    assert kb["neptune>venus"]["ka"]["meaning"] in line and kb["neptune>venus"]["ka"]["challenging"] in line
    assert "stationary" in line and "another planet" in line and "orb" not in line   # orbs stay out of shared text
    # an afflicted Jupiter is told to promise less (Sepharial)
    assert "afflicted Jupiter" in T.describe_for_ai(item("jupiter", dignity="detriment"), "en")
    # a real sky: neptune/uranus/pluto aspects are found for some birth date
    n = T.natal_chart(date(1997, 3, 29), None, None)
    tr = T.transits_for(n, "month", date(2026, 10, 1), limit=20)
    assert {t["motion"] for t in tr["transits"]} <= {"direct", "retrograde", "stationary"}
