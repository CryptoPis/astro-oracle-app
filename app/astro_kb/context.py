"""Knowledge-base lines for AI prompts: the KB decides what a symbol means, the AI only phrases it.

Every function returns short plain text in the reader's language (so the Georgian or Russian wording the model
sees is already natural), and never long extracts from the source books.
"""
from datetime import date

from app.astro_kb import load

WEEKDAY_PLANET = {0: "moon", 1: "mars", 2: "mercury", 3: "jupiter", 4: "venus", 5: "saturn", 6: "sun"}


def _l(entry: dict, lang: str) -> dict:
    return entry.get(lang) or entry["en"]


def tarot_card(slug: str, reversed_: bool, lang: str) -> str:
    """Waite's upright or reversed meaning of one Major Arcana card, in our words."""
    side = load("tarot").get(slug, {}).get("reversed" if reversed_ else "upright")
    if not side:
        return ""
    t = _l(side, lang)
    return (f"meaning: {t['meaning']} | supportive: {t['supportive']} | challenging: {t['challenging']} | "
            f"advice: {t['advice']}")


def coffee_dictionary(lang: str) -> str:
    kb = load("coffee")
    rules = "\n".join(f"- {r}" for r in kb["rules"].get(lang, kb["rules"]["en"]))
    symbols = "\n".join(f"- {_l(s, lang)[0]} ({s['tone']}): {_l(s, lang)[1]}" for s in kb["symbols"].values())
    return f"Reading rules (Tea-Cup Reading, 1920s):\n{rules}\nSymbol dictionary:\n{symbols}"


def aura_palette(lang: str) -> str:
    rows = []
    for c in load("aura").values():
        t = _l(c, lang)
        rows.append(f"- {t['name']} {c['hex']}: {t['meaning']} (+ {t['supportive']} / - {t['challenging']})")
    return "Aura colours (after W. W. Atkinson, The Human Aura, 1910):\n" + "\n".join(rows)


def moon_phase(code: str, lang: str) -> str:
    entry = load("moon").get(code)
    if not entry:
        return ""
    t = _l(entry, lang)
    return (f"Folk lore (Harley, Moon Lore): {t['lore']} | supportive: {t['supportive']} | "
            f"challenging: {t['challenging']} | advice: {t['advice']}")


def number(n: int, lang: str) -> str:
    entry = load("numbers").get(str(n))
    if not entry:
        return ""
    t = _l(entry, lang)
    return (f"ruling planet: {entry['planet']} ({entry['source']}) | meaning: {t['meaning']} | supportive: "
            f"{t['supportive']} | challenging: {t['challenging']} | advice: {t['advice']}")


def dream_symbols(text: str, lang: str, limit: int = 5) -> list[tuple[str, dict]]:
    """Symbols whose word stems appear in the dream text (any of the three languages)."""
    low = text.lower()
    found = []
    for sid, s in load("dreams")["symbols"].items():
        stems = [st for lg in ("en", "ka", "ru") for st in s["stems"][lg]]
        if any(st.lower() in low for st in stems):
            found.append((sid, _l(s, lang)))
    return found[:limit]


def dream_context(text: str, lang: str) -> str:
    kb = load("dreams")
    method = "\n".join(f"- {m}" for m in kb["method"].get(lang, kb["method"]["en"]))
    found = dream_symbols(text, lang)
    sym = "\n".join(f"- {sid}: {t['meaning']} Reflective question: {t['question']}" for sid, t in found)
    return (f"Method (after Freud, The Interpretation of Dreams: one perspective among several):\n{method}"
            + (f"\nKnown symbols in this dream:\n{sym}" if sym else ""))


def day_correspondence(day: date, lang: str) -> dict:
    """The planet of the weekday and its colour, metal, stone, plant and keyword (Agrippa), for UI chips."""
    pid = WEEKDAY_PLANET[day.weekday()]
    c = load("correspondences")[pid]
    t = _l(c, lang)
    planet = load("planets")[pid]
    return {"planet": pid, "planet_name": _l(planet, lang)["name"], "color": c["color"], "color_name": t["color_name"],
            "metal": _l(c["metal"], lang) if isinstance(c["metal"], dict) else c["metal"],
            "stone": c["stones"].get(lang, c["stones"]["en"])[0], "plant": c["plants"].get(lang, c["plants"]["en"])[0],
            "keyword": t["keyword"], "tip": t["tip"]}


def day_line(day: date, lang: str) -> str:
    d = day_correspondence(day, lang)
    return (f"Day of {d['planet']} (Agrippa's correspondences): colour {d['color_name']}, stone {d['stone']}, "
            f"keyword {d['keyword']}; {d['tip']}")


def sphere_lore(tone: str, lang: str) -> dict:
    kb = load("sphere")
    t = _l(kb[tone], lang)
    return {"cloud": t["cloud"], "lore": t["lore"], "how_to": kb["how_to"].get(lang, kb["how_to"]["en"])}
