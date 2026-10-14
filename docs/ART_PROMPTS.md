# Art prompts for $Astro Oracle

## როგორ გამოვიყენოთ (ქართულად)
1. გახსენი ChatGPT (ან OpenArt), სადაც წინა სურათები შექმენი.
2. ჩასვი **სტილის ბლოკი** და შემდეგ კონკრეტული სურათის აღწერა. პრომპტები ინგლისურადაა, რადგან სურათის მოდელები ინგლისურს უკეთ იგებენ.
3. სტილის შესანარჩუნებლად შეგიძლია მიამაგრო ერთ-ერთი არსებული სურათი (მაგ. `კურო.png` ან ტაროს კარტი) და დაწერო: "match the style of the attached image".
4. სურათები ატვირთე პროექტის საქაღალდეში, დაარქვი ქვემოთ მითითებული სახელები და მომწერე. აპლიკაციაში თავად ჩავსვამ.
5. თითო ნიშანზე 2-3 ვარიანტი შეგიძლია გააკეთო (`leo.png`, `leo-2.png`, `leo-3.png`). აპლიკაცია მათ ყოველდღე შეცვლის.

Aspect ratios: zodiac **3:2 landscape** (1536×1024), tarot **2:3 portrait** (1024×1536).

---

## Style block (paste first, every time)
```
Ornate celestial fantasy illustration. Deep indigo and violet night sky with soft purple nebula clouds,
scattered stars and tiny galaxies. The subject is formed from luminous golden light and cosmic dust, with
glowing gold filigree details and subtle amethyst highlights. Rich, cinematic lighting, high detail,
painterly but crisp, centered composition with breathing room around the subject. Palette: midnight
indigo #0d0a24, violet #8b6cff, gold #e2bd6a, ivory highlights. No text, no letters, no watermark, no frame.
```

## Zodiac (missing 8) — file names `leo.png` … `pisces.png`
| File | Subject line (add after the style block) |
|---|---|
| leo.png | A majestic lion with a mane of swirling golden starlight and solar flares, standing proud on a glowing crescent of rock, a radiant sun disc behind its head. |
| virgo.png | A serene maiden in a flowing violet robe woven from stars, holding a sheaf of golden wheat that glows like constellations, soft moonlight on her face. |
| libra.png | Elegant golden scales of balance floating in space, each pan holding a tiny glowing planet, delicate filigree chains, a calm violet nebula behind. |
| scorpio.png | A powerful scorpion made of dark crystal and molten gold, its curved tail glowing with a single crimson star (Antares), mist swirling around it. |
| sagittarius.png | A centaur archer drawing a bow of light, the arrow a streaking comet aimed at the stars, mane and tail made of golden stardust. |
| capricorn.png | A mythical sea-goat: front half a noble mountain goat with spiralling golden horns, back half a shimmering fish tail of cosmic water. |
| aquarius.png | A water-bearer pouring a stream of liquid starlight from a golden urn; the stream turns into a river of tiny stars flowing across the sky. |
| pisces.png | Two luminous koi-like fish circling each other in a yin-yang spiral, linked by a glowing golden cord, trailing star bubbles. |

Variants for existing signs (optional, for daily rotation): `aries-2.png`, `taurus-2.png`, `gemini-2.png`, `cancer-2.png` — same subject, different pose or angle.

## Tarot — missing Major Arcana card
Use the tarot frame style of the existing deck (attach `00_fool.jpg` as reference):
```
Tarot card in portrait 2:3, ornate gold Art Nouveau frame with small sacred-geometry medallions in the corners,
deep cosmic purple background. Same style as the attached card. No text, no title, no numbers.
```
| File | Subject |
|---|---|
| 05_hierophant.jpg | A wise high priest on a stone throne between two pillars, raising a hand in blessing, golden triple crown, two crossed golden keys at his feet, stained-glass light behind. |

## Tarot — Minor Arcana (56 cards, optional next step)
Same tarot frame prompt, then:
- **Wands** (fire, passion): golden-red flames, wooden staffs with sprouting leaves of light. Files `wands_01.jpg` … `wands_14.jpg`.
- **Cups** (water, feelings): golden chalices overflowing with starlit water, moonlit seas. Files `cups_01.jpg` … `cups_14.jpg`.
- **Swords** (air, mind): silver-gold blades, wind and clouds, crisp starlight. Files `swords_01.jpg` … `swords_14.jpg`.
- **Pentacles** (earth, wealth): golden coins engraved with pentagrams, gardens and mountains. Files `pentacles_01.jpg` … `pentacles_14.jpg`.

Numbers 1–10 show that many symbols in a scene that matches the classic Rider–Waite meaning; 11–14 are Page, Knight, Queen, King.
Example: *"Three of Cups: three women raising golden chalices of starlight in a joyful toast, celebration under a violet sky."*

## Moving versions (later)
Each painting can become a 4–6 second seamless loop (gentle mane movement, drifting stars) with an image-to-video
tool. The app is ready to play short `.webm/.mp4` loops in the same "living" card.
