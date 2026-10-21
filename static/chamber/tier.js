/* Oracle chamber: the graphics-tier rules, free of the DOM so they can be tested (tests/test_chamber_tier.py).
   FULL starts at High. After a measuring window (40 frames, starting 10 frames after the shaders have finished
   compiling): High that is too slow steps down to Medium and measures again; only Medium that is too slow as well
   leaves for LITE, and only then is the "too slow" flag kept, and only for this build. */

export const HIGH_MAX_MS = 20, LITE_MS = 45, STALL_MS = 100, WINDOW = 40, SETTLE = 10;

/* the stored "too slow" flag counts only for the build that wrote it (its version stamp V); an older value, such as
   the "1" earlier builds wrote, is ignored, so every new release gets a fresh try at FULL */
export const slowBefore = (stored, V) => !!stored && !!V && stored === V;

/* the average frame time of a window. Frames over STALL_MS (a shader still compiling, a texture going to the GPU)
   are stalls, not the device's pace, and are left out; but when they are most of the window, the device really is
   that slow and the window counts as STALL_MS */
export function windowAverage(ms) {
  const ok = ms.filter((x) => x <= STALL_MS);
  return ok.length >= ms.length / 2 ? ok.reduce((a, b) => a + b, 0) / Math.max(1, ok.length) : STALL_MS;
}

/* what to do after a window at `level` ("high" | "medium"): "keep", "medium" (step down and measure again) or
   "lite" (leave FULL and remember it for this build). forced: FULL was chosen by hand (never LITE); fixedLevel: the
   level was forced with ?gfx= (never changes) */
export function nextStep(level, avgMs, { forced = false, fixedLevel = false } = {}) {
  if (fixedLevel) return "keep";
  if (level === "high") return avgMs > HIGH_MAX_MS ? "medium" : "keep";   // however slow, Medium gets its own window first
  return avgMs > LITE_MS && !forced ? "lite" : "keep";
}
