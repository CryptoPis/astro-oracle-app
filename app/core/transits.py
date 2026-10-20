"""Natal chart and transits for personal horoscopes (tropical zodiac, astronomy-engine).

How a reading is built:
1. Natal chart: positions of Sun..Saturn at birth (local noon if the birth time is unknown, so the Moon may
   be off by up to ~7°); the ascendant and whole-sign houses only when time AND city are known.
2. Transits: where Sun..Pluto stand during the period. Day = one moment (12:00 UTC) incl. the Moon; week and
   month = one sample per day, keeping each aspect's tightest orb and its date; the Moon is left out.
3. Aspects to natal points: conjunction, sextile, square, trine, opposition. Orbs shrink for fast planets
   (a Moon square counts within ~3.5°, a Saturn square within ~2.3°).
4. Ranking: transiting planet weight × natal point weight × aspect weight × closeness, then Sepharial's
   rules ("Effects of Transits", 1920): the rarer the planet the weightier (the weights in planets.json), a
   retrograde pass ×1.15 and a stationary one ×1.25 (the planet lingers on the point), two planets on one
   natal point ×1.1 each; and the essential dignity of the transiting planet after Lilly (domicile ×1.2,
   exaltation ×1.15: strong and clear; detriment ×1.05: felt, but awkward). At most two aspects per
   transiting planet so one planet does not fill the whole reading.
5. Meanings: app/astro_kb/transits.json ("saturn>venus", fallback "sun>*") plus planets/aspects/houses.
"""
import hashlib
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import astronomy as A

from app.astro_kb import load
from app.core.astro import SIGNS
from app.core.chart import Place, _ascendant, _tropical

BODIES = {"sun": A.Body.Sun, "moon": A.Body.Moon, "mercury": A.Body.Mercury, "venus": A.Body.Venus,
          "mars": A.Body.Mars, "jupiter": A.Body.Jupiter, "saturn": A.Body.Saturn, "uranus": A.Body.Uranus,
          "neptune": A.Body.Neptune, "pluto": A.Body.Pluto}
NATAL_POINTS = ["sun", "moon", "mercury", "venus", "mars", "jupiter", "saturn"]
RETRO_CAN = ["mercury", "venus", "mars", "jupiter", "saturn", "uranus", "neptune", "pluto"]
ORB_SCALE = {"moon": 0.7, "sun": 0.6, "mercury": 0.5, "venus": 0.5, "mars": 0.5, "jupiter": 0.45, "saturn": 0.45,
             "uranus": 0.35, "neptune": 0.35, "pluto": 0.35}
TOP_N = {"day": 4, "week": 5, "month": 5}
MEAN_SPEED = {"mercury": 1.38, "venus": 1.2, "mars": 0.52, "jupiter": 0.083, "saturn": 0.034, "uranus": 0.012,
              "neptune": 0.006, "pluto": 0.004}           # degrees per day
STATION = 0.15                                              # |speed| below 15% of the mean = stationary
DIGNITY_FACTOR = {"domicile": 1.2, "exaltation": 1.15, "detriment": 1.05, "fall": 1.0}
RETRO_FACTOR, STATION_FACTOR, DOUBLE_FACTOR = 1.15, 1.25, 1.1


def dignity(pid: str, lon: float) -> str | None:
    """Major essential dignity of a traditional planet at a longitude (Lilly's table): domicile | exaltation |
    detriment | fall | None (peregrine or only a minor dignity; the outer planets have none)."""
    kb = load("dignities")
    if pid not in kb["fall"]:
        return None
    sign = SIGNS[int(lon % 360 // 30)]
    if sign in kb["domicile"][pid]:
        return "domicile"
    if kb["exaltation"][pid] == sign:
        return "exaltation"
    if sign in kb["detriment"][pid]:
        return "detriment"
    if kb["fall"][pid] == sign:
        return "fall"
    return None


def motion(pid: str, speed: float) -> str:
    """direct | retrograde | stationary (Sepharial: a stationary or retrograde transit weighs more)."""
    if pid not in MEAN_SPEED:
        return "direct"
    if abs(speed) < STATION * MEAN_SPEED[pid]:
        return "stationary"
    return "retrograde" if speed < 0 else "direct"


def _time(dt: datetime) -> A.Time:
    dt = dt.astimezone(timezone.utc)
    return A.Time.Make(dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second + dt.microsecond / 1e6)


def birth_utc(birth_date: date, birth_time: time | None, place: Place | None) -> datetime:
    local = datetime.combine(birth_date, birth_time or time(12, 0))
    tz = timezone.utc
    if place:
        try:
            tz = ZoneInfo(place.tz)
        except ZoneInfoNotFoundError:
            pass
    return local.replace(tzinfo=tz).astimezone(timezone.utc)


def fingerprint(birth_date: date, birth_time: time | None, place: Place | None) -> str:
    """Stable id of a natal chart: same birth data -> same cache key; any change -> new readings."""
    where = f"{place.lat:.2f},{place.lon:.2f},{place.tz}" if place else "-"
    raw = f"{birth_date.isoformat()}|{birth_time.strftime('%H:%M') if birth_time else 'noon'}|{where}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def natal_chart(birth_date: date, birth_time: time | None = None, place: Place | None = None) -> dict:
    utc = birth_utc(birth_date, birth_time, place)
    t = _time(utc)
    points = {pid: round(_tropical(BODIES[pid], t), 3) for pid in NATAL_POINTS}
    asc = None
    if birth_time is not None and place is not None:
        asc = round(_ascendant(t, place.lat, place.lon), 3)
        points["asc"] = asc
    return {"utc": utc.isoformat(), "points": points, "asc": asc, "time_known": birth_time is not None,
            "place_known": place is not None, "fingerprint": fingerprint(birth_date, birth_time, place)}


def positions(when: datetime) -> dict[str, tuple[float, float]]:
    """{planet: (tropical longitude, degrees per day)} for every transiting body."""
    t, t2 = _time(when), _time(when + timedelta(days=1))
    out = {}
    for pid, body in BODIES.items():
        a, b = _tropical(body, t), _tropical(body, t2)
        out[pid] = (a, ((b - a + 540) % 360) - 180)
    return out


def separation(a: float, b: float) -> float:
    d = abs(a - b) % 360
    return min(d, 360 - d)


def aspects_at(pos: dict, natal: dict, include_moon: bool) -> list[dict]:
    kb = load("aspects")
    found = []
    for tp, (lon, speed) in pos.items():
        if tp == "moon" and not include_moon:
            continue
        for np, nlon in natal.items():
            s = separation(lon, nlon)
            for aid, a in kb.items():
                max_orb = a["orb"] * ORB_SCALE[tp]
                orb = abs(s - a["angle"])
                if orb <= max_orb:
                    nxt = separation(lon + speed, nlon)
                    found.append({"transit": tp, "natal": np, "aspect": aid, "orb": round(orb, 2), "max_orb": max_orb,
                                  "applying": abs(nxt - a["angle"]) < orb, "lon": lon, "speed": speed})
    return found


def score(item: dict) -> float:
    planets, aspects = load("planets"), load("aspects")
    closeness = 1 - 0.6 * item["orb"] / item["max_orb"]
    base = planets[item["transit"]]["weight_transit"] * planets[item["natal"]]["weight_natal"] * aspects[item["aspect"]]["weight"] * closeness
    mot = item.get("motion", "direct")
    base *= STATION_FACTOR if mot == "stationary" else RETRO_FACTOR if mot == "retrograde" else 1.0
    base *= DIGNITY_FACTOR.get(item.get("dignity") or "", 1.0)
    return base * (DOUBLE_FACTOR if item.get("double") else 1.0)


def period_days(period: str, day: date) -> list[date]:
    if period == "day":
        return [day]
    if period == "week":
        start = day - timedelta(days=day.weekday())
        return [start + timedelta(days=i) for i in range(7)]
    first = day.replace(day=1)
    nxt = (first + timedelta(days=32)).replace(day=1)
    return [first + timedelta(days=i) for i in range((nxt - first).days)]


def transits_for(natal: dict, period: str, day: date, limit: int | None = None) -> dict:
    """Ranked aspects of the period's sky to the natal chart, plus retrogrades and the Moon."""
    kb_aspects = load("aspects")
    best: dict[tuple, dict] = {}
    retro: set[str] = set()
    for d in period_days(period, day):
        when = datetime.combine(d, time(12, 0), tzinfo=timezone.utc)
        pos = positions(when)
        retro |= {p for p in RETRO_CAN if pos[p][1] < 0}
        for item in aspects_at(pos, natal["points"], include_moon=(period == "day")):
            key = (item["transit"], item["natal"], item["aspect"])
            if key not in best or item["orb"] < best[key]["orb"]:
                best[key] = {**item, "date": d.isoformat()}
    hits: dict[str, set[str]] = {}
    for item in best.values():
        item["dignity"] = dignity(item["transit"], item["lon"])
        item["motion"] = motion(item["transit"], item["speed"])
        hits.setdefault(item["natal"], set()).add(item["transit"])
    for item in best.values():   # Sepharial: two planets on one point act more strongly (the fast Moon does not count)
        item["double"] = item["transit"] != "moon" and len(hits[item["natal"]] - {"moon"}) >= 2
    ranked = sorted(best.values(), key=score, reverse=True)
    top, per_planet = [], {}
    for item in ranked:
        if per_planet.get(item["transit"], 0) >= 2:
            continue
        per_planet[item["transit"]] = per_planet.get(item["transit"], 0) + 1
        item["nature"] = kb_aspects[item["aspect"]]["nature"]
        item["score"] = round(score(item), 3)
        if natal["asc"] is not None:
            item["house"] = (int(item["lon"] // 30) - int(natal["asc"] // 30)) % 12 + 1
        top.append(item)
        if len(top) >= (limit or TOP_N[period]):
            break
    for i, item in enumerate(top, 1):
        item["id"] = f"T{i}"
    noon = positions(datetime.combine(day, time(12, 0), tzinfo=timezone.utc))
    moon_lon = noon["moon"][0]
    return {"transits": top, "retrograde": [p for p in RETRO_CAN if p in retro],
            "moon_sign": SIGNS[int(moon_lon // 30)], "period": period}


def label(item: dict, lang: str) -> str:
    """Short, case-safe chip text: 'მარსი □ შენი მზე', 'Mars □ your Sun', 'Марс □ твоё Солнце'."""
    planets, aspects = load("planets"), load("aspects")
    t = planets[item["transit"]].get(lang, planets[item["transit"]]["en"])["name"]
    n = planets[item["natal"]].get(lang, planets[item["natal"]]["en"])
    sym = aspects[item["aspect"]]["symbol"]
    if lang == "ka":
        return f"{t} {sym} შენი {n['name']}"
    if lang == "ru":
        return f"{t} {sym} {n.get('poss', 'твой')} {n['name']}"
    return f"{t} {sym} your {n['name']}"


def dignity_label(item: dict, lang: str) -> str | None:
    """'იუპიტერი ამაღლებაში' / 'Jupiter exalted' / 'Юпитер в экзальтации', or None."""
    if not item.get("dignity"):
        return None
    name = load("planets")[item["transit"]].get(lang, load("planets")[item["transit"]]["en"])["name"]
    lab = load("dignities")["labels"][item["dignity"]]
    return f"{name} {lab.get(lang, lab['en'])}"


def pair_meaning(item: dict, lang: str) -> dict | None:
    """Sepharial-based meaning of 'transiting X over natal Y' (transits.json) in the reader's language."""
    kb = load("transits")
    entry = kb.get(f"{item['transit']}>{item['natal']}") or kb.get(f"{item['transit']}>*")
    if not entry:
        return None
    return {**(entry.get(lang) or entry["en"]), "source": entry.get("source", "")}


def signature(tr: dict) -> str:
    """What a reading's text depends on, without orbs and dates: people with the same top transits share one text."""
    parts = [f"{i['transit']}.{i['aspect']}.{i['natal']}.{i.get('house') or 0}.{i.get('dignity') or '-'}.{i.get('motion', 'direct')}"
             f".{int(i['applying'])}.{int(bool(i.get('double')))}" for i in tr["transits"]]
    moon = tr["moon_sign"] if tr["period"] == "day" else ""   # week/month texts do not mention the day's Moon sign
    raw = "|".join(parts) + "#" + ",".join(tr["retrograde"]) + "#" + moon
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def retro_label(pid: str, lang: str) -> str:
    name = load("planets")[pid].get(lang, load("planets")[pid]["en"])["name"]
    return {"ka": f"{name} ℞", "ru": f"{name} ℞", "en": f"{name} ℞"}.get(lang, f"{name} ℞")


def areas_of(item: dict) -> list[str]:
    planets, houses = load("planets"), load("houses")
    out = set(planets[item["transit"]]["areas"]) | set(planets[item["natal"]]["areas"])
    if item.get("house"):
        out |= set(houses[str(item["house"])]["areas"])
    return sorted(out)


def describe_for_ai(item: dict, lang: str) -> str:
    """One line per transit with the knowledge-base meanings in the reader's language (the AI phrases, the KB decides)."""
    planets, aspects, houses = load("planets"), load("aspects"), load("houses")
    tp, np = planets[item["transit"]], planets[item["natal"]]
    tl, nl, al = tp.get(lang, tp["en"]), np.get(lang, np["en"]), aspects[item["aspect"]].get(lang, aspects[item["aspect"]]["en"])
    side = "supportive" if item["nature"] == "harmonious" else "challenging" if item["nature"] == "challenging" else "supportive+challenging"
    expr = {"supportive": tl["supportive"], "challenging": tl["challenging"],
            "supportive+challenging": f"{tl['supportive']} / {tl['challenging']}"}[side]
    pair = pair_meaning(item, lang)
    if pair:   # the pair entry is more specific than the planet's general expression
        expr = {"supportive": pair["supportive"], "challenging": pair["challenging"],
                "supportive+challenging": f"{pair['supportive']} / {pair['challenging']}"}[side]
    house = f"; transit house {item['house']} ({houses[str(item['house'])].get(lang, houses[str(item['house'])]['en'])})" if item.get("house") else ""
    extra = []
    if item.get("motion") in ("retrograde", "stationary"):
        extra.append(f"transiting planet {item['motion']}: the theme lingers and weighs more")
    if item.get("dignity"):
        lab = load("dignities")["labels"][item["dignity"]]
        extra.append(f"transiting {item['transit']} {lab['en']}: {lab['meaning_en']}")
        if item["transit"] == "jupiter" and item["dignity"] in ("detriment", "fall"):
            extra.append("Sepharial: an afflicted Jupiter does little good, so keep the promise modest")
    if item.get("double"):
        extra.append(f"another planet also touches natal {item['natal']}: the theme is emphasised")
    # no orb or date here: the text is shared by everyone with the same signature()
    return (f"{item['id']}: transiting {item['transit']} {item['aspect']} natal {item['natal']} "
            f"({'applying' if item['applying'] else 'separating'}, {item['nature']}); "
            f"{tl['name']}: {tl['themes']}; {nl['name']}: {nl['themes']}; aspect: {al['meaning']}; "
            + (f"meaning: {pair['meaning']}; " if pair else "")
            + f"expression: {expr}"
            + (f"; advice: {pair['advice']}" if pair else "")
            + house + "".join(f"; {e}" for e in extra) + f"; areas: {', '.join(areas_of(item))}")
