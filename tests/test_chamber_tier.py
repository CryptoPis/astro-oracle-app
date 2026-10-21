"""Oracle chamber: the graphics-tier rules (static/chamber/tier.js), run in Node, and how main.js / full.js use them.

- an old permanent "too slow" flag ("1", or another build's stamp) is ignored; only this build's stamp counts
- slow High steps down to Medium first, never straight to LITE
- LITE (and the flag) only when Medium is slow as well; never when FULL was chosen by hand or ?gfx= fixes the level
- stalls (shader compiles, uploads) over 100 ms are left out of a window unless they are most of it
"""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CH = ROOT / "static" / "chamber"
NODE = shutil.which("node")


def run_tier(js: str):
    if not NODE:
        pytest.skip("node is not installed")
    src = f"import * as T from {json.dumps((CH / 'tier.js').as_uri())};\n{js}"
    out = subprocess.run([NODE, "--input-type=module", "-e", src], capture_output=True, text=True, timeout=30)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


def test_old_slow_flag_is_ignored_only_this_builds_counts():
    r = run_tier("""console.log(JSON.stringify([T.slowBefore("1", "faa27ae1f1"), T.slowBefore("0886ae8b44", "faa27ae1f1"),
      T.slowBefore(null, "faa27ae1f1"), T.slowBefore("faa27ae1f1", "faa27ae1f1"), T.slowBefore("dev", "")]));""")
    assert r == [False, False, False, True, False]


def test_slow_high_goes_to_medium_first_never_straight_to_lite():
    r = run_tier("""console.log(JSON.stringify([T.nextStep("high", 15), T.nextStep("high", 30), T.nextStep("high", 80), T.nextStep("high", 100)]));""")
    assert r == ["keep", "medium", "medium", "medium"]


def test_lite_only_when_medium_is_slow_too_and_never_when_forced():
    r = run_tier("""console.log(JSON.stringify([T.nextStep("medium", 30), T.nextStep("medium", 46), T.nextStep("medium", 80, { forced: true }),
      T.nextStep("high", 80, { fixedLevel: true }), T.nextStep("medium", 80, { fixedLevel: true })]));""")
    assert r == ["keep", "lite", "keep", "keep", "keep"]


def test_compile_stalls_are_not_slowness_but_a_slow_device_is():
    r = run_tier("""const quick = Array(36).fill(16.7).concat([420, 380, 260, 150]), slow = Array(40).fill(130), half = Array(20).fill(16).concat(Array(20).fill(140));
      console.log(JSON.stringify([T.windowAverage(quick), T.windowAverage(slow), T.windowAverage(half), T.WINDOW, T.SETTLE]));""")
    assert abs(r[0] - 16.7) < .01 and r[1] == 100 and abs(r[2] - 16) < .01 and r[3] == 40 and r[4] == 10


def test_engine_uses_the_rules():
    main = (CH / "main.js").read_text(encoding="utf-8")
    full = (CH / "full.js").read_text(encoding="utf-8")
    # the flag: written with this build's stamp, only when switching for slowness, and read through slowBefore
    assert 'B.store.set("astro.chSlow", V)' in main and 'B.store.set("astro.chSlow", "1")' not in main
    assert re.search(r'if \(why === "slow"\) B\.store\.set\("astro\.chSlow", V\)', main)
    assert 'TR.slowBefore(B.store.get("astro.chSlow"), V)' in main
    # full.js: LITE only through nextStep's verdict; a slow High re-measures at Medium; the window opens after the compile
    assert 'if (step === "lite") { ctx.onSlow(); return; }' in full and full.count("ctx.onSlow()") == 1
    assert 'setGfx("medium").then(() => { samples = []; mStart = frames + TR.SETTLE; })' in full
    assert "compiled.then(() => { mStart = frames + TR.SETTLE; })" in full
    # the Profile label: the element exists (hidden until the chamber fills it) and the texts exist in ka/en/ru
    assert 'id="tierNow" hidden' in (ROOT / "frontend" / "app.html").read_text(encoding="utf-8")
    st = (CH / "stations.js").read_text(encoding="utf-8")
    for key in ("tierNow", "gfxHigh", "gfxMedium", "gfxLite", "why_forced", "why_reduced", "why_desktop", "why_weak", "why_slowBefore", "why_noWebgl", "why_slow", "why_lost", "why_error"):
        assert st.count(f"{key}:") == 3, key
