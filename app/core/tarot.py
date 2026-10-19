"""Tarot deck: Major Arcana (matches the current index.html UI).

Images are the project's own illustrated deck, served from
/static/img/tarot/<slug>.webp. The Hierophant has no painting yet; the
frontend draws a gold-line face for it.

To add the Minor Arcana later, append 56 entries to DECK. No other code
needs to change.
"""
import secrets
from dataclasses import dataclass


@dataclass(frozen=True)
class Card:
    number: int
    slug: str
    name: str
    commons_file: str  # Wikimedia Commons file name, used by the fetch script

    def to_dict(self, base_url: str, reversed_: bool) -> dict:
        return {"id": self.slug, "number": self.number, "name": self.name, "reversed": reversed_,
                "image_url": f"{base_url}/static/img/tarot/{self.slug}.webp"}


_MAJOR = [
    ("fool", "The Fool", "RWS_Tarot_00_Fool.jpg"),
    ("magician", "The Magician", "RWS_Tarot_01_Magician.jpg"),
    ("high_priestess", "The High Priestess", "RWS_Tarot_02_High_Priestess.jpg"),
    ("empress", "The Empress", "RWS_Tarot_03_Empress.jpg"),
    ("emperor", "The Emperor", "RWS_Tarot_04_Emperor.jpg"),
    ("hierophant", "The Hierophant", "RWS_Tarot_05_Hierophant.jpg"),
    ("lovers", "The Lovers", "RWS_Tarot_06_Lovers.jpg"),
    ("chariot", "The Chariot", "RWS_Tarot_07_Chariot.jpg"),
    ("strength", "Strength", "RWS_Tarot_08_Strength.jpg"),
    ("hermit", "The Hermit", "RWS_Tarot_09_Hermit.jpg"),
    ("wheel_of_fortune", "Wheel of Fortune", "RWS_Tarot_10_Wheel_of_Fortune.jpg"),
    ("justice", "Justice", "RWS_Tarot_11_Justice.jpg"),
    ("hanged_man", "The Hanged Man", "RWS_Tarot_12_Hanged_Man.jpg"),
    ("death", "Death", "RWS_Tarot_13_Death.jpg"),
    ("temperance", "Temperance", "RWS_Tarot_14_Temperance.jpg"),
    ("devil", "The Devil", "RWS_Tarot_15_Devil.jpg"),
    ("tower", "The Tower", "RWS_Tarot_16_Tower.jpg"),
    ("star", "The Star", "RWS_Tarot_17_Star.jpg"),
    ("moon", "The Moon", "RWS_Tarot_18_Moon.jpg"),
    ("sun", "The Sun", "RWS_Tarot_19_Sun.jpg"),
    ("judgement", "Judgement", "RWS_Tarot_20_Judgement.jpg"),
    ("world", "The World", "RWS_Tarot_21_World.jpg"),
]

DECK: list[Card] = [Card(i, slug, name, f) for i, (slug, name, f) in enumerate(_MAJOR)]

# Card names are never taken from the AI (it invented cases and doubled "reversed"). Nominative case, hand-written.
CARD_NAMES: dict[str, dict[str, str]] = {
    "fool": {"ka": "სულელი", "ru": "Шут", "en": "The Fool"},
    "magician": {"ka": "მაგი", "ru": "Маг", "en": "The Magician"},
    "high_priestess": {"ka": "ქურუმი ქალი", "ru": "Верховная Жрица", "en": "The High Priestess"},
    "empress": {"ka": "იმპერატრიცა", "ru": "Императрица", "en": "The Empress"},
    "emperor": {"ka": "იმპერატორი", "ru": "Император", "en": "The Emperor"},
    "hierophant": {"ka": "იეროფანტი", "ru": "Иерофант", "en": "The Hierophant"},
    "lovers": {"ka": "შეყვარებულები", "ru": "Влюблённые", "en": "The Lovers"},
    "chariot": {"ka": "ეტლი", "ru": "Колесница", "en": "The Chariot"},
    "strength": {"ka": "ძალა", "ru": "Сила", "en": "Strength"},
    "hermit": {"ka": "განდეგილი", "ru": "Отшельник", "en": "The Hermit"},
    "wheel_of_fortune": {"ka": "ბედის ბორბალი", "ru": "Колесо Фортуны", "en": "Wheel of Fortune"},
    "justice": {"ka": "სამართლიანობა", "ru": "Справедливость", "en": "Justice"},
    "hanged_man": {"ka": "ჩამოკიდებული", "ru": "Повешенный", "en": "The Hanged Man"},
    "death": {"ka": "სიკვდილი", "ru": "Смерть", "en": "Death"},
    "temperance": {"ka": "ზომიერება", "ru": "Умеренность", "en": "Temperance"},
    "devil": {"ka": "ეშმაკი", "ru": "Дьявол", "en": "The Devil"},
    "tower": {"ka": "კოშკი", "ru": "Башня", "en": "The Tower"},
    "star": {"ka": "ვარსკვლავი", "ru": "Звезда", "en": "The Star"},
    "moon": {"ka": "მთვარე", "ru": "Луна", "en": "The Moon"},
    "sun": {"ka": "მზე", "ru": "Солнце", "en": "The Sun"},
    "judgement": {"ka": "განკითხვა", "ru": "Суд", "en": "Judgement"},
    "world": {"ka": "სამყარო", "ru": "Мир", "en": "The World"},
}
REVERSED_LABEL = {"ka": "შებრუნებული", "ru": "перевёрнутая", "en": "reversed"}


def card_name(slug: str, lang: str) -> str:
    names = CARD_NAMES.get(slug, {})
    return names.get(lang) or names.get("en") or slug

SPREADS = {
    "daily": ["today"],                    # card of the day: one per user per day
    "single": ["answer"],                  # one card for a question
    "three": ["past", "present", "future"],
}

REVERSED_PROBABILITY = 0.25  # set to 0 to disable reversed cards

_rng = secrets.SystemRandom()  # server-side draw, so the client can't pick its card


def draw(n: int) -> list[tuple[Card, bool]]:
    cards = _rng.sample(DECK, n)
    return [(c, _rng.random() < REVERSED_PROBABILITY) for c in cards]
