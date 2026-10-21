"""Builds the oracle chamber's runtime images (static/chamber/img/*.webp) from the art references (dev tool).

    python -m scripts.chamber_assets --art D:/AST/art-reference --moon path/to/lroc_color_poles_1k.jpg

The originals are never committed: this script writes small WebP copies (1024 px for the High tier, 512 px for
Medium) and prints the seam test, the palette measured from the scene references and every output size.
- tiles (stone wall, oak floor, velvet): seam test (wrap-around edge step vs the average pixel step); a tile whose
  edges do not meet is repaired with a minimum-error cut (image quilting) around a half-offset copy; then a normal map
  is derived from the albedo (roughness is derived from the albedo in the shader)
- the round rug: the medallion tile with a woven border ring
- plates: the window landscape (a portrait crop with room for parallax) and the dome's night sky
- the moon: NASA SVS CGI Moon Kit colour map (equirectangular), see docs/CREDITS_GRAPHICS.md
"""
import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "static" / "chamber" / "img"
PREFIX = "ChatGPT Image Oct 21, 2026, "
# identified by content (the files keep their generated names); rug A = three byte-identical copies, one is used
SRC = {
    "stone": "03_40_46 PM.png",    # dark rubble masonry tile
    "floor": "03_58_40 PM.png",    # aged oak planks
    "velvet": "04_05_18 PM.png",   # crushed indigo velvet
    "rug": "04_06_48 PM.png",      # rug A: navy/violet with a gold medallion
    "window": "04_02_26 PM.png",   # night landscape, no frame, no moon
    "dome": "04_03_16 PM.png",     # night sky with the Milky Way, no lines
}
SCENES = ("03_31_55 PM.png", "03_33_18 PM.png", "03_59_46 PM.png")   # full-room references, palette only
# the files each surface needs (pixels). High: near surfaces 1024, the rug and velvet 768; both levels share the
# 512 normal maps, the sky and the moon (blurred or small on screen). Rug and velvet have no normal map: their bump
# comes from the albedo in the shader.
OUTPUTS = {"stone": (1024, 512), "stone_n": (512,), "floor": (1024, 512), "floor_n": (512,), "rug": (768, 512), "velvet": (768, 512),
           "window": (1024, 512), "dome": (512,), "moon": (512,)}
SEAM_MAX = 1.15


def load(path: Path) -> np.ndarray:
    return np.asarray(Image.open(path).convert("RGB")).astype(np.float32) / 255


def seam_ratio(a: np.ndarray) -> tuple[float, float]:
    """Wrap-around edge step / mean neighbouring-pixel step, horizontally and vertically (1.0 = seamless)."""
    gx, gy = np.abs(np.diff(a, axis=1)).mean(), np.abs(np.diff(a, axis=0)).mean()
    return float(np.abs(a[:, 0] - a[:, -1]).mean() / gx), float(np.abs(a[0] - a[-1]).mean() / gy)


def min_cut(err: np.ndarray) -> np.ndarray:
    """Per row, the column of the minimum-error top-to-bottom path through err (h x w), moving at most 1 per row."""
    h, w = err.shape
    cost = err.copy()
    for j in range(1, h):
        prev = cost[j - 1]
        best = np.minimum(prev, np.minimum(np.r_[np.inf, prev[:-1]], np.r_[prev[1:], np.inf]))
        cost[j] += best
    path = np.empty(h, int)
    path[-1] = int(np.argmin(cost[-1]))
    for j in range(h - 2, -1, -1):
        c = path[j + 1]
        lo, hi = max(0, c - 1), min(w, c + 2)
        path[j] = lo + int(np.argmin(cost[j, lo:hi]))
    # the tile wraps: the cut must end where it starts, or the other axis' edges would come from different copies
    fix = np.round((path[0] - path[-1]) * np.arange(h) / (h - 1)).astype(int)
    return np.clip(path + fix, 0, w - 1)


def heal_x(a: np.ndarray) -> np.ndarray:
    """Make the left/right edges meet: a half-offset copy (whose edges are the original's continuous middle) is
    used outside two minimum-error cuts; between them the original covers the copy's own seam."""
    h, w, _ = a.shape
    b = np.roll(a, w // 2, axis=1)
    err = ((a - b) ** 2).sum(axis=2)
    out = b.copy()
    l0, l1, r0, r1 = w // 4, w // 2 - w // 16, w // 2 + w // 16, 3 * w // 4
    left, right = l0 + min_cut(err[:, l0:l1]), r0 + min_cut(err[:, r0:r1])
    xs = np.arange(w)[None, :]
    feather = 3.0
    m = np.clip((xs - left[:, None]) / feather + .5, 0, 1) * np.clip((right[:, None] - xs) / feather + .5, 0, 1)
    return out * (1 - m[..., None]) + a * m[..., None]


def make_tileable(a: np.ndarray) -> np.ndarray:
    sx, sy = seam_ratio(a)
    if sx > SEAM_MAX:
        a = heal_x(a)
    if sy > SEAM_MAX:
        a = heal_x(a.transpose(1, 0, 2)).transpose(1, 0, 2)
    return a


def blur(x: np.ndarray, r: float) -> np.ndarray:
    """Wrap-aware Gaussian blur of a 2-D map (tiles must stay tileable)."""
    fy, fx = np.fft.fftfreq(x.shape[0])[:, None], np.fft.rfftfreq(x.shape[1])[None, :]   # FFT convolution wraps by itself
    return np.fft.irfft2(np.fft.rfft2(x) * np.exp(-2 * (np.pi * r) ** 2 * (fx * fx + fy * fy)), s=x.shape).astype(np.float32)


def normal_map(a: np.ndarray, strength: float) -> np.ndarray:
    """Tangent-space normal map (OpenGL, +Y up) from the albedo's luminance used as a height field. Roughness is
    derived from the same luminance in the shader (room.js), so it costs no download."""
    lum = a @ np.array([.2126, .7152, .0722], np.float32)
    h = blur(lum, 1.6) - blur(lum, 28)   # fine relief only: large light/dark patches are colour, not shape
    h = h / max(1e-6, np.abs(h).max())
    dx = (np.roll(h, -1, axis=1) - np.roll(h, 1, axis=1)) * .5
    dy = (np.roll(h, -1, axis=0) - np.roll(h, 1, axis=0)) * .5
    n = np.dstack([-dx * strength, dy * strength, np.ones_like(h)])   # image y runs down, GL normal maps y up
    n /= np.linalg.norm(n, axis=2, keepdims=True)
    return n * .5 + .5


def rug_round(a: np.ndarray) -> np.ndarray:
    """The square medallion tile as a round rug: a woven border ring in the rug's own gold and navy."""
    s = a.shape[0]
    yy, xx = (np.mgrid[0:s, 0:s] + .5) / s - .5
    d = np.hypot(xx, yy) * 2   # 0 centre .. 1 at the inscribed circle
    lum = a @ np.array([.2126, .7152, .0722], np.float32)
    gold = a[lum > np.percentile(lum, 92)].mean(0)
    navy = a[lum < np.percentile(lum, 20)].mean(0)
    out = a.copy()
    band = (d > .86) & (d < .97)
    out[band] = out[band] * .35 + navy * .65
    for r0, w in ((.865, .012), (.955, .012), (.91, .005)):
        ring = np.clip(1 - np.abs(d - r0) / w, 0, 1)[..., None]
        out = out * (1 - ring) + gold * ring
    out *= np.clip(1.08 - d * .12, 0, 1)[..., None]   # a little worn towards the edge
    return np.clip(out, 0, 1)


def save(arr: np.ndarray, name: str, size: tuple[int, int] | int, q: int = 82) -> int:
    img = Image.fromarray((np.clip(arr, 0, 1) * 255 + .5).astype(np.uint8))
    target = size if isinstance(size, tuple) else (size, size)
    if img.size != target:
        img = img.resize(target, Image.LANCZOS)
    path = OUT / name
    img.save(path, "WEBP", quality=q, method=6)
    return path.stat().st_size


def hexs(c) -> str:
    return "#" + "".join(f"{int(round(min(1, max(0, v)) * 255)):02x}" for v in c)


def palette(art: Path) -> dict:
    px = np.concatenate([load(art / (PREFIX + n)).reshape(-1, 3) for n in SCENES])
    lum = px @ np.array([.2126, .7152, .0722], np.float32)
    o = np.argsort(lum)
    n = len(o)
    top = px[o[int(n * .985):]]
    return {"black": hexs(px[o[int(n * .005):int(n * .02)]].mean(0)), "haze": hexs(px[o[int(n * .25):int(n * .4)]].mean(0)),
            "candle": hexs(top[top[:, 0] > top[:, 2] * 1.25].mean(0)), "moon": hexs(top[top[:, 2] > top[:, 0] * 1.02].mean(0))}


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--art", required=True, type=Path)
    ap.add_argument("--moon", required=True, type=Path)
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    sizes = {}

    print("palette measured from the scene references:", palette(args.art))
    tiles = {"stone": -13, "floor": 10, "velvet": 6, "rug": 8}   # normal-map strength; stone: the mortar is lighter than the stones but sits deeper
    for key, strength in tiles.items():
        a = load(args.art / (PREFIX + SRC[key]))
        before = seam_ratio(a)
        if key == "rug":
            a = rug_round(a)
        else:
            a = make_tileable(a)
        after = seam_ratio(a)
        print(f"{key}: seam ratio L/R {before[0]:.2f} -> {after[0]:.2f}, T/B {before[1]:.2f} -> {after[1]:.2f}")
        for s in OUTPUTS[key]:
            sizes[f"{key}_{s}.webp"] = save(a, f"{key}_{s}.webp", s, q=80)
        if f"{key}_n" in OUTPUTS:
            normal = normal_map(a, strength)
            for s in OUTPUTS[f"{key}_n"]:
                sizes[f"{key}_n_{s}.webp"] = save(normal, f"{key}_n_{s}.webp", s, q=75)

    # the window: a portrait crop over the lake and the village lights, wide enough for a gentle parallax
    w = load(args.art / (PREFIX + SRC["window"]))
    h, ww = w.shape[:2]
    cw = int(h * .7)
    x0 = min(ww - cw, max(0, int(ww * .62) - cw // 2))
    crop = w[:, x0:x0 + cw]
    for s in OUTPUTS["window"]:
        dims = (round(cw * min(1, s / h)), min(h, s))
        sizes[f"window_{s}.webp"] = save(crop, f"window_{s}.webp", dims, q=84)

    d = load(args.art / (PREFIX + SRC["dome"]))
    for s in OUTPUTS["dome"]:
        sizes[f"dome_{s}.webp"] = save(d, f"dome_{s}.webp", s, q=84)

    m = load(args.moon)
    for s in OUTPUTS["moon"]:
        sizes[f"moon_{s}.webp"] = save(m, f"moon_{s}.webp", (s, s // 2), q=84)

    for f in OUT.glob("*.webp"):   # files a former plan made and nothing loads any more
        if f.name not in sizes:
            f.unlink()
            print("removed", f.name)
    for k in sorted(sizes):
        print(f"{k:24s} {sizes[k]:>9,d} B")
    level = {"high": {"stone": 1024, "floor": 1024, "rug": 768, "velvet": 768, "window": 1024},
             "medium": {"stone": 512, "floor": 512, "rug": 512, "velvet": 512, "window": 512}}
    for name, lv in level.items():   # the same per-level lists as room.js (LEVEL)
        files = [f"{k}_{v}.webp" for k, v in lv.items()] + ["stone_n_512.webp", "floor_n_512.webp", "dome_512.webp", "moon_512.webp"]
        print(f"{name}: {len(files)} files, {sum(sizes[f] for f in files):,d} B")


if __name__ == "__main__":
    main()
