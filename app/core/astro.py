"""Deterministic astrology helpers, ported from legacy main.py.

These are pure functions with no AI calls: sun sign, life-path number, moon
phase and daily lucky numbers.
"""
import hashlib
from datetime import date, datetime, timezone

SIGNS = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
         "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]

SIGN_EMOJI = {"Aries": "♈", "Taurus": "♉", "Gemini": "♊", "Cancer": "♋", "Leo": "♌", "Virgo": "♍",
              "Libra": "♎", "Scorpio": "♏", "Sagittarius": "♐", "Capricorn": "♑",
              "Aquarius": "♒", "Pisces": "♓"}

SIGN_NAMES = {
    "Aries": {"ka": "ვერძი", "ru": "Овен", "en": "Aries"},
    "Taurus": {"ka": "კურო", "ru": "Телец", "en": "Taurus"},
    "Gemini": {"ka": "ტყუპები", "ru": "Близнецы", "en": "Gemini"},
    "Cancer": {"ka": "კირჩხიბი", "ru": "Рак", "en": "Cancer"},
    "Leo": {"ka": "ლომი", "ru": "Лев", "en": "Leo"},
    "Virgo": {"ka": "ქალწული", "ru": "Дева", "en": "Virgo"},
    "Libra": {"ka": "სასწორი", "ru": "Весы", "en": "Libra"},
    "Scorpio": {"ka": "მორიელი", "ru": "Скорпион", "en": "Scorpio"},
    "Sagittarius": {"ka": "მშვილდოსანი", "ru": "Стрелец", "en": "Sagittarius"},
    "Capricorn": {"ka": "თხის რქა", "ru": "Козерог", "en": "Capricorn"},
    "Aquarius": {"ka": "მერწყული", "ru": "Водолей", "en": "Aquarius"},
    "Pisces": {"ka": "თევზები", "ru": "Рыбы", "en": "Pisces"},
}

SIGN_ELEMENT = {"Aries": "fire", "Leo": "fire", "Sagittarius": "fire",
                "Taurus": "earth", "Virgo": "earth", "Capricorn": "earth",
                "Gemini": "air", "Libra": "air", "Aquarius": "air",
                "Cancer": "water", "Scorpio": "water", "Pisces": "water"}

# (month, first day of the *next* sign) boundaries, same as legacy calculate_zodiac
_BOUNDS = [(1, 20, "Capricorn", "Aquarius"), (2, 19, "Aquarius", "Pisces"),
           (3, 21, "Pisces", "Aries"), (4, 20, "Aries", "Taurus"),
           (5, 21, "Taurus", "Gemini"), (6, 21, "Gemini", "Cancer"),
           (7, 23, "Cancer", "Leo"), (8, 23, "Leo", "Virgo"),
           (9, 23, "Virgo", "Libra"), (10, 23, "Libra", "Scorpio"),
           (11, 22, "Scorpio", "Sagittarius"), (12, 22, "Sagittarius", "Capricorn")]


def zodiac_sign(d: date) -> str:
    _, cutoff, before, after = _BOUNDS[d.month - 1]
    return before if d.day < cutoff else after


def _reduce(total: int, keep_master: bool) -> int:
    while total > 9 and not (keep_master and total in (11, 22, 33)):
        total = sum(int(c) for c in str(total))
    return total


def personal_year_number(birth: date, year: int) -> int:
    """Birth day + birth month + current year, reduced to 1-9."""
    return _reduce(sum(int(c) for c in f"{birth.day}{birth.month}{year}"), keep_master=False)


def life_path_number(d: date) -> int:
    total = sum(int(c) for c in d.strftime("%d%m%Y"))
    while total > 9 and total not in (11, 22, 33):
        total = sum(int(c) for c in str(total))
    return total


_SYNODIC = 29.53058867
_KNOWN_NEW_MOON = datetime(2024, 1, 11, 11, 57, tzinfo=timezone.utc)

MOON_PHASE_NAMES = {
    "new_moon":        {"ka": "ახალი მთვარე",     "ru": "Новолуние",          "en": "New Moon"},
    "waxing_crescent": {"ka": "მზარდი ნამგალა",   "ru": "Растущий месяц",     "en": "Waxing Crescent"},
    "first_quarter":   {"ka": "პირველი მეოთხედი", "ru": "Первая четверть",    "en": "First Quarter"},
    "waxing_gibbous":  {"ka": "მზარდი მთვარე",    "ru": "Растущая луна",      "en": "Waxing Gibbous"},
    "full_moon":       {"ka": "სავსემთვარეობა",   "ru": "Полнолуние",         "en": "Full Moon"},
    "waning_gibbous":  {"ka": "კლებადი მთვარე",   "ru": "Убывающая луна",     "en": "Waning Gibbous"},
    "last_quarter":    {"ka": "ბოლო მეოთხედი",    "ru": "Последняя четверть", "en": "Last Quarter"},
    "waning_crescent": {"ka": "კლებადი ნამგალა",  "ru": "Убывающий месяц",    "en": "Waning Crescent"},
}


def moon_phase(lang: str = "en", now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    age = ((now - _KNOWN_NEW_MOON).total_seconds() / 86400.0) % _SYNODIC
    p = age / _SYNODIC
    if p < 0.04 or p > 0.96: code, icon = "new_moon", "🌑"
    elif p < 0.21: code, icon = "waxing_crescent", "🌒"
    elif p < 0.29: code, icon = "first_quarter", "🌓"
    elif p < 0.46: code, icon = "waxing_gibbous", "🌔"
    elif p < 0.54: code, icon = "full_moon", "🌕"
    elif p < 0.71: code, icon = "waning_gibbous", "🌖"
    elif p < 0.79: code, icon = "last_quarter", "🌗"
    else: code, icon = "waning_crescent", "🌘"
    return {"code": code, "icon": icon, "name": MOON_PHASE_NAMES[code].get(lang, MOON_PHASE_NAMES[code]["en"]),
            "age_days": round(age, 1), "illumination": round((1 - abs(1 - 2 * p)) * 100)}


def lucky_numbers(user_id: int, day: date, count: int = 3) -> list[int]:
    """Stable for one user on one day: reopening the app shows the same numbers."""
    seed = hashlib.sha256(f"{user_id}:{day.isoformat()}".encode()).digest()
    nums: list[int] = []
    for b in seed:
        n = b % 49 + 1
        if n not in nums:
            nums.append(n)
        if len(nums) == count:
            break
    return sorted(nums)


def period_key(period: str, d: date) -> str:
    if period == "week":
        y, w, _ = d.isocalendar()
        return f"{y}-W{w:02d}"
    if period == "month":
        return d.strftime("%Y-%m")
    return d.isoformat()
