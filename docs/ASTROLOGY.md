# How the personal horoscope is computed

Code: `app/core/transits.py` (astronomy), `app/astro_kb/*.json` (meanings), `app/services/content.py`
(`get_personal_horoscope`, `get_personal_energy`), `app/ai/prompts.py` (`personal_horoscope_prompt`).

## Steps
1. **Natal chart** (tropical zodiac, astronomy-engine, geocentric apparent positions): Sun, Moon, Mercury, Venus,
   Mars, Jupiter, Saturn at the moment of birth. Without a birth time the chart is cast for local noon; the
   ascendant and the (whole-sign) houses are used only when both birth time and city are known.
2. **Transits**: Sun to Pluto during the period. Day: one moment (12:00 UTC), the Moon included. Week (ISO week)
   and month: one sample per day at 12:00 UTC; each aspect keeps its tightest orb and the date of it; the Moon
   is left out (it aspects everything within a few days).
3. **Aspects** to the natal points: conjunction, sextile, square, trine, opposition. Base orbs 6/3/5/5/6°, scaled
   by the speed of the transiting planet (Moon 0.7, Sun 0.6, Mercury/Venus/Mars 0.5, Jupiter/Saturn 0.45,
   Uranus/Neptune/Pluto 0.35): a Saturn square counts within 2.25°, a Mars conjunction within 3°.
4. **Ranking**: transiting planet weight × natal point weight × aspect weight × closeness (tighter = stronger),
   then Sepharial's rules: the rarer the planet the weightier (Neptune 1.0, Uranus .97, Pluto .95, Saturn .93,
   Jupiter .85, Mars .7), a retrograde pass ×1.15 and a stationary one ×1.25 (|speed| under 15% of the mean),
   two planets on one natal point ×1.1; and the transiting planet's essential dignity after Lilly (domicile ×1.2,
   exaltation ×1.15, detriment ×1.05, fall ×1.0). At most two aspects per transiting planet; top 4 for a day,
   5 for a week or month. Retrograde planets of the period and the Moon's sign (day) are added.
5. **Meanings**: each transit is described to the AI with the knowledge-base entries in the reader's language:
   the pair entry from `transits.json` ("saturn>venus": meaning, supportive or challenging expression, advice,
   after Sepharial), planet and aspect themes, the house if known, the dignity, retrograde/stationary and
   double-transit notes (an afflicted Jupiter "does little good", Sepharial), and the life areas it colours. The AI only phrases; it must cite the transits it used per
   section (`why`), be plain about squares, oppositions and retrogrades, and give practical advice.
6. **Chips**: the `why` ids are replaced on the server by exact labels computed from the chart
   ("მარსი □ შენი მზე"), plus the dignity chip when there is one ("იუპიტერი ამაღლებაში"), so the chips can
   never contain AI inventions.
7. **Cache and quota**: keyed by what the text depends on, not by the person: sign + period key + language +
   accuracy (time/city known) + `transits.signature()` (the top transits with aspect, house, dignity, motion,
   applying, double; the retrogrades; the Moon's sign for a day). Orbs and dates stay out of the AI text, so
   everyone with the same top transits shares one AI call; the exact dates are added per person after the cache.
   Personal texts are generated only when opened (the morning cron makes sign texts only). A new text costs one
   slot of the daily AI cap (`horoscope` 40, `energy` 3 per user); when the cap is reached or the AI fails, the
   shared sign text is shown. The quality guard applies as everywhere.
8. **Daily energy**: written from the single strongest transit of the day (`energy_personal`, shared by
   signature), shown with a chip "today's main transit", plus the planet of the weekday with its colour, stone
   and keyword (Agrippa's correspondences, no AI). The day's numbers are a fixed per-user, per-day draw and are labelled
   "numbers of the day" (no astrological claim).

People without a birth date, or reading another sign, get the shared sign horoscope as before.

## Example (birth 1990-08-15, 08:00, Tbilisi; reading for 2026-10-20)
Natal: Sun 22° Leo, Moon 11° Gemini, Venus 1° Leo, Mars 21° Taurus, ascendant 1° Virgo.
Strongest transits of the day: Jupiter ☌ natal Sun (orb 0.7°, in the 12th house), Pluto ☍ natal Venus (1.6°),
Jupiter □ natal Mars (1.6°), Neptune △ natal Venus (0.9°); retrograde: Venus, Saturn, Uranus, Neptune;
the Moon in Aquarius.

## What is approximate or simplified
- Without a birth time the Moon can be off by up to about 7°, and there are no houses or ascendant.
- Houses are whole-sign houses; no Placidus or other systems. No asteroids, nodes, Chiron or minor aspects.
- Transits are sampled once a day at 12:00 UTC, not at exact aspect times; the day reading uses one moment.
- Orbs are a common-practice choice; the weights follow Sepharial's order of rarity, not exact numbers of his.
- The meanings are a compact knowledge base in our own words; the AI phrases them and can still word things
  imperfectly (the quality guard catches garbled text, not astrological nuance).
- Tarot is intentionally random; only its interpretation rules were made more honest.

## Sources of the knowledge base (`app/astro_kb/`)
All meanings are written in our own modern words, in natural Georgian, English and Russian; the books are not in
the repository and nothing longer than a short phrase is quoted. Each entry has a `source` note.

| Feature | KB file | Source (public domain) | Used for |
|---|---|---|---|
| Transits | `transits.json`, `planets.json` | Sepharial, *Astrology* / "Effects of Transits" (1920) | planet-over-planet meanings, rarity weights, retro/stationary, double transits |
| Dignities | `dignities.json` | Lilly, *Christian Astrology* (1647), I ch. XVIII-XIX | domicile, exaltation, detriment, fall, triplicity, faces; ranking and chips |
| Cross-check | `dignities.json`, `aspects.json`, `signs.json` | Ptolemy, *Tetrabiblos* (Robbins) | terms, natures, aspects as (dis)harmonious |
| Tarot | `tarot.json` | A. E. Waite, *The Pictorial Key to the Tarot* (1910) | 22 cards upright and reversed |
| Coffee | `coffee.json` | *Tea-Cup Reading* ("a Highland Seer", 1920s) | reading rules, 46 symbols with tone |
| Aura | `aura.json` | W. W. Atkinson, *The Human Aura* (1910) | 15 colours with hex |
| Sphere | `sphere.json` | Sepharial, *How to Read the Crystal* (1922) | the cloud line per answer tone |
| Moon ritual | `moon.json` | T. Harley, *Moon Lore* (1885) | 8 phases, presented as folk tradition |
| Numerology | `numbers.json` | Sepharial, *Cosmic Symbolism* (1911), planetary numbers | 1-9; 11/22/33 marked as modern |
| Dreams | `dreams.json` | S. Freud, *The Interpretation of Dreams* (1900, Brill) | method only, one perspective, family-friendly; 24 symbols with a reflective question |
| Day tips | `correspondences.json` | H. C. Agrippa, *Three Books of Occult Philosophy* I.22-29 | weekday planet, colour, metal, stone, plant |

Where the sources disagree (noted in `dignities.json`): Ptolemy gives two sets of terms (Egyptian and his own; we
use his own, as Lilly's table says "according to Ptolemy"); the water triplicity is Mars by day and night in
Ptolemy and Lilly, Venus by day in Dorotheus (we follow Lilly); Pluto, Uranus and Neptune have no traditional
dignities (Sepharial treats Uranus and Neptune by nature and rarity only; Pluto was found in 1930, after him).
