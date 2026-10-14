"""Tarot deck: Major Arcana (matches the current index.html UI).

Images are served from /static/img/tarot/<slug>.jpg. Run
scripts/fetch_tarot_images.py once to download the public-domain
Rider–Waite (1909) scans from Wikimedia Commons, so the app no longer
hotlinks Wikimedia.

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
                "image_url": f"{base_url}/static/img/tarot/{self.slug}.jpg"}


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
