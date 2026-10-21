# Graphics credits: the oracle chamber

The FULL room (`static/chamber/`) uses these images. Only optimized runtime copies are in the repository (WebP,
at most 1024 px). They are built by `python -m scripts.chamber_assets` from the sources below and loaded after the
room's first frames. The originals are not committed.

## The Moon: NASA SVS CGI Moon Kit

- **Source:** "CGI Moon Kit", NASA Scientific Visualization Studio, ID 4720 (released 2019-09-06, page last updated
  2026-01-09). <https://svs.gsfc.nasa.gov/4720/>
- **File used:** `lroc_color_poles_1k.jpg` (1024×512, 135.8 KB), the LROC WAC colour mosaic as an equirectangular
  map. Download: <https://svs.gsfc.nasa.gov/vis/a000000/a004700/a004720/lroc_color_poles_1k.jpg>
- **Credit line (as the SVS page asks):** NASA's Scientific Visualization Studio. Visualizer: Ernie Wright (USRA).
  Scientist: Noah Petro (NASA/GSFC). Data: LRO LROC WAC colour mosaic; LRO LOLA.
- **License:** the SVS page links NASA's media usage guidelines
  (<https://www.nasa.gov/nasa-brand-center/images-and-media/>, reached from
  <https://www.nasa.gov/multimedia/guidelines/index.html>). Checked 2026-10-21, they say:
  > NASA content – images, audio, video, and media files used in the rendition of 3-dimensional models, such as
  > texture maps and polygon data in any format – generally are not subject to copyright in the United States. You
  > may use this material for educational or informational purposes, including photo collections, textbooks, public
  > exhibits, computer graphical simulations and Internet Web pages.

  > NASA content used in a factual manner that does not imply endorsement may be used without needing explicit
  > permission. NASA should be acknowledged as the source of the material.

  > If the NASA material is to be used for commercial purposes, including advertisements, it must not explicitly or
  > implicitly convey NASA's endorsement of commercial goods or services.

  How we comply: the map is a texture map (named explicitly above), it carries no NASA logo, insignia or person,
  NASA is acknowledged here as the source, and the app does not suggest any NASA endorsement.
- **Use:** `moon_1024.webp` / `moon_512.webp`, sampled in the moon window's shader on a sphere lit for the real
  phase of the day.

## The room: the project's own art references

Generated images in the project's art-reference folder (made for this app, kept outside the repository with their
original generated names). Each was identified by its content, and none contains text, letters, digits or drawn symbols:

| original file (`ChatGPT Image Oct 21, 2026, …`) | content | runtime files |
|---|---|---|
| `03_40_46 PM.png` | dark rubble stone wall tile | `stone_*`, `stone_n_*` (walls, pillars) |
| `03_58_40 PM.png` | aged oak planks | `floor_*`, `floor_n_*` (floor, wainscot) |
| `04_05_18 PM.png` | crushed indigo velvet | `velvet_*`, `velvet_n_*` (tarot cloth) |
| `04_06_48 PM.png` (rug A; `04_07_08 PM-1` and `04_07_28 PM-1` are byte-identical copies) | navy/violet rug, gold medallion | `rug_*`, `rug_n_*` (round rug, with a woven border ring added) |
| `04_02_26 PM.png` | night landscape (mountains, lake, village lights), no frame, no moon | `window_*` (a portrait crop) |
| `04_03_16 PM.png` | night sky with the Milky Way, no lines | `dome_*` |
| `03_31_55 PM`, `03_33_18 PM`, `03_59_46 PM` | full-room scenes | none: palette measurement only |

Seam test (wrap-around edge step ÷ average pixel step; 1.00 = seamless), before → after the repair: stone L/R
1.37 → 1.07, T/B 0.99 → 0.99; oak T/B 1.29 → 1.03, L/R 1.04 → 1.03; velvet L/R 1.43 → 0.81, T/B 1.44 → 0.97.
Rug A is not tiled (1.03 / 1.10). Normal maps are derived from the albedo. Roughness is derived from the albedo in the
shader, so it needs no file.

## Runtime files (exact sizes)

Stage A2 (2026-10-21). Each surface gets the size it needs. High loads 1024 px for the near stone and oak, 768 px for
the rug and velvet, and 512 px for the rest. Both levels share the 512 px normal maps, the dome sky and the moon. The
dome is blurred under procedural stars, and the moon is small on screen. The rug and velvet have no normal map: their
bump is derived from the albedo in the shader. Roughness, soot, wear and large-scale variation are derived in the
shader too.

| file | pixels | bytes | High | Medium |
|---|---|---|---|---|
| `stone_1024.webp` | 1024×1024 | 330,850 | ✓ | |
| `stone_512.webp` | 512×512 | 81,200 | | ✓ |
| `stone_n_512.webp` | 512×512 | 121,270 | ✓ | ✓ |
| `floor_1024.webp` | 1024×1024 | 265,526 | ✓ | |
| `floor_512.webp` | 512×512 | 54,266 | | ✓ |
| `floor_n_512.webp` | 512×512 | 87,552 | ✓ | ✓ |
| `rug_768.webp` | 768×768 | 239,714 | ✓ | |
| `rug_512.webp` | 512×512 | 108,628 | | ✓ |
| `velvet_768.webp` | 768×768 | 60,340 | ✓ | |
| `velvet_512.webp` | 512×512 | 25,938 | | ✓ |
| `window_1024.webp` | 658×941 | 63,658 | ✓ | |
| `window_512.webp` | 358×512 | 24,478 | | ✓ |
| `dome_512.webp` | 512×512 | 74,066 | ✓ | ✓ |
| `moon_512.webp` | 512×256 | 19,574 | ✓ | ✓ |

A phone downloads one set: **High 1,262,550 bytes** (9 files; Stage A: 2,431,590) or **Medium 596,972 bytes**
(9 files; Stage A: 715,130). WebP is already compressed, so gzip saves nothing. LITE downloads none.

Removed since Stage A (bytes as they were): `stone_n_1024` 341,448 · `floor_n_1024` 245,238 · `rug_1024` 395,960 ·
`rug_n_1024` 234,066 · `rug_n_512` 91,238 · `velvet_1024` 109,798 · `velvet_n_1024` 74,208 · `velvet_n_512` 26,920 ·
`dome_1024` 278,336 · `moon_1024` 92,502. Unchanged: `stone_1024`, `stone_512`, `stone_n_512`, `floor_1024`,
`floor_512`, `floor_n_512`, `rug_512`, `velvet_512`, `window_1024`, `window_512`, `dome_512`, `moon_512`. New:
`rug_768` 239,714 · `velvet_768` 60,340.

The velvet also dresses the new drapes. Each drape shows the tile with its own offset and rotation, under a slow
light/dark variation, so the repeat never lines up.

## Stage A3: no new files

Everything new in A3 is generated in code: the candelabras, the decals of light, the floor's reflection streaks, the
window's quatrefoil, fittings, arch molding, corbels and carved relief (a 128 px canvas normal map), the drapes' gold
borders, the dome's gold architecture and the procedural stars. The runtime files and their exact bytes are the
table above, unchanged: **High 1,262,550 bytes, Medium 596,972 bytes**.

The reference dome (`03_39_51 PM.png`, gold frame) was evaluated as a cut-out ring for the dome and rejected. The image is
1536×1024 landscape, so its gold ring is cut off at the top and bottom and cannot form a full annulus, and its medallions
are drawn sunburst emblems. The architecture is built from geometry instead (10 ribs, 3 rings, 20 medallions, a boss).

## Stage A3.1: no new files

The dome's thinner gold, the bosses, the crown's new profile and its soft shadow, the frame's gold strips and the
longer floor streaks are all made in code. The runtime files are unchanged: **High 1,262,550 bytes, Medium 596,972 bytes**.

## Code

three.js r160 (MIT), vendored in `static/vendor/` with its license (`three-LICENSE.txt`).
