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
4. **Ranking**: transiting planet weight × natal point weight × aspect weight × closeness (tighter = stronger);
   at most two aspects per transiting planet; top 4 for a day, 5 for a week or month. Retrograde planets of
   the period and the Moon's sign (day) are added.
5. **Meanings**: each transit is described to the AI with the knowledge-base entries in the reader's language
   (planet themes, the supportive or challenging expression that fits the aspect, the aspect's meaning, the
   house if known, the life areas it colours). The AI only phrases; it must cite the transits it used per
   section (`why`), be plain about squares, oppositions and retrogrades, and give practical advice.
6. **Chips**: the `why` ids are replaced on the server by exact labels computed from the chart
   ("მარსი □ შენი მზე"), so the chips can never contain AI inventions.
7. **Cache**: per natal chart fingerprint (birth date + time or noon + rounded coordinates) + period key +
   language (`ai_cache` kind `horoscope_personal`). A new reading uses the daily AI cap for horoscopes; when the
   cap is reached the shared sign text is shown instead. The quality guard applies as everywhere.
8. **Daily energy**: written from the single strongest transit of the day (`energy_personal`), shown with a
   chip "today's main transit". The day's numbers are a fixed per-user, per-day draw and are labelled
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
- Orbs and weights are a reasonable, common-practice choice, not a single school's canon.
- The meanings are a compact knowledge base in our own words; the AI phrases them and can still word things
  imperfectly (the quality guard catches garbled text, not astrological nuance).
- Tarot is intentionally random; only its interpretation rules were made more honest.
