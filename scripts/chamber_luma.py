"""Mean luminance of chamber screenshots against a reference image (dev tool).

    python -m scripts.chamber_luma REF.png SHOT.png [SHOT.png ...]

Rec. 709 luma of the sRGB values (0..255), over the band from 12 % to 80 % of the height: the app's header and the
name plaque at the bottom are left out of the screenshots, and the reference is measured over the same band.
"""
import sys

import numpy as np
from PIL import Image


def luma(path: str) -> float:
    a = np.asarray(Image.open(path).convert("RGB")).astype(np.float32)
    h = a.shape[0]
    a = a[int(h * .12):int(h * .80)]
    return float((a @ np.array([.2126, .7152, .0722], np.float32)).mean())


def main() -> None:
    ref = luma(sys.argv[1])
    print(f"reference {ref:6.1f}  {sys.argv[1]}")
    for p in sys.argv[2:]:
        v = luma(p)
        print(f"shot      {v:6.1f}  ({v / ref * 100:5.1f} % of the reference)  {p}")


if __name__ == "__main__":
    main()
