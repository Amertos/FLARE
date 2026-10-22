/**
 * Is WebGL usable here?
 *
 * Returns null when it is, or a short reason when it is not (headless CI, a
 * projector without a GPU driver, a browser with hardware acceleration off).
 * Both 3D screens call this during their first render so they can show their
 * text fallback without an effect that sets state after paint.
 */
export function webglSupport(): string | null {
  try {
    const canvas = document.createElement("canvas");
    const ctx = canvas.getContext("webgl2") ?? canvas.getContext("webgl");
    if (!ctx) return "no WebGL context available";
    // Release the probe context immediately: browsers cap the number of live
    // contexts, and this one never draws anything.
    const lose = (ctx as WebGLRenderingContext).getExtension("WEBGL_lose_context");
    lose?.loseContext();
    return null;
  } catch (err) {
    return String(err);
  }
}
