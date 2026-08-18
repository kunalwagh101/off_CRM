/**
 * Turning a clip into a list of pixel passes.
 *
 * Two sources feed one chain.
 *
 * **The stack** — the looks a person chose. Those arrive already resolved in
 * the manifest, because the catalogue is far too large to ship in order to draw
 * one clip and because a look nobody declared must never reach a shader.
 *
 * **The properties** — the sliders. `brightness`, `contrast`, `vignette`,
 * `grain` and the rest are animatable numbers on the clip itself, so they are
 * resolved per frame here rather than by the server.
 *
 * The second half of this file is a bug fix as much as a feature. `PROPERTY_SPEC`
 * has declared `vignette`, `sharpen`, `grain`, `tint`, `corner_radius`,
 * `border_width` and `shadow` since the timeline was written; the document
 * stored them, clamped them and animated them — and the painter drew none of
 * them, because a 2D canvas cannot. Every one of those is a primitive now.
 *
 * **Order is the look.** Grade, then focus, then texture, then the chosen
 * stack, then framing. Framing goes last because a rounded corner or a drop
 * shadow is about where the clip *is*, not about what it looks like, and a
 * grain applied over a rounded corner would grain the transparent part too.
 */

import type { ResolvedStep } from "./shaders/pipeline";

/** The manifest's `effects.clips`: a resolved chain per clip id. */
export type EffectTable = Record<string, ResolvedStep[]>;

function step(primitive: string, numbers: Record<string, number>,
              colours: Record<string, string> = {}, passes = 1): ResolvedStep {
  return { primitive, passes, numbers, colours };
}

/** Everything before the chosen looks: exposure, colour, focus and texture. */
export function propertyGrade(properties: Record<string, number>): ResolvedStep[] {
  const chain: ResolvedStep[] = [];
  const brightness = properties.brightness ?? 0;
  const exposure = properties.exposure ?? 0;
  // One stop is a doubling and `brightness` is a multiplier, so the two compose
  // as a single exposure rather than as two separate operations — which is what
  // the CSS-filter painter did too, and the one thing about it worth keeping.
  const stops = exposure + Math.log2(Math.max(0.001, 1 + brightness));
  if (stops !== 0) chain.push(step("exposure", { stops }));
  if (properties.contrast) chain.push(step("contrast", { amount: properties.contrast, pivot: 0.5 }));
  if (properties.saturation) chain.push(step("saturation", { amount: properties.saturation }));
  // Temperature was previously a sepia wash plus a hue rotation, because that
  // is what a CSS filter can express. It is a red/blue rebalance now, which is
  // what the control has always claimed to be.
  if (properties.temperature) chain.push(step("temperature", { amount: properties.temperature }));
  if (properties.tint) chain.push(step("tint", { amount: properties.tint }));
  if (properties.blur > 0) chain.push(step("blur", { radius: properties.blur }, {}, 2));
  if (properties.sharpen > 0) {
    chain.push(step("sharpen", { amount: properties.sharpen, radius: 1.5 }));
  }
  if (properties.grain > 0) chain.push(step("grain", { amount: properties.grain, size: 1 }));
  return chain;
}

/** Everything after them: the matte, the corner and the shadow. */
export function propertyFrame(
  properties: Record<string, number>,
  style: Record<string, unknown>
): ResolvedStep[] {
  const chain: ResolvedStep[] = [];
  if (properties.vignette > 0) {
    chain.push(step("vignette", { amount: properties.vignette, radius: 0.75, softness: 0.45 },
                    { colour: "#000000" }));
  }
  const radius = properties.corner_radius ?? 0;
  const border = properties.border_width ?? 0;
  if (radius > 0 || border > 0) {
    chain.push(step("rounded_frame", { radius, border },
                    { border_colour: String(style.border_colour ?? "#ffffff") }));
  }
  if (properties.shadow > 0) {
    chain.push(step("drop_shadow",
                    { radius: properties.shadow, offset_x: 0,
                      offset_y: Math.round(properties.shadow * 0.6), opacity: 0.5 },
                    { colour: String(style.shadow_colour ?? "#000000") }, 3));
  }
  return chain;
}

/**
 * The whole chain for one clip at one instant.
 *
 * `extraBlur` is the transition painter's contribution — a blur transition
 * blurs both sides of a cut, and it has always done that through the same
 * number the `blur` property uses.
 */
export function chainFor(
  clipId: string,
  properties: Record<string, number>,
  style: Record<string, unknown>,
  table: EffectTable | undefined,
  extraBlur = 0
): ResolvedStep[] {
  const withBlur = extraBlur > 0
    ? { ...properties, blur: (properties.blur ?? 0) + extraBlur }
    : properties;
  return [
    ...propertyGrade(withBlur),
    ...(table?.[clipId] ?? []),
    ...propertyFrame(properties, style)
  ];
}

/** What one chain costs, in full-screen draws. For saying "this will be slow". */
export function passCost(chain: ResolvedStep[]): number {
  return chain.reduce((total, item) => total + (item.passes || 1), 0);
}

/**
 * The CSS-filter approximation, for a machine with no WebGL2.
 *
 * Deliberately a subset: a canvas filter can do light, contrast, saturation and
 * blur, and cannot do a vignette, a grain, a key or a mask. The painter reports
 * which clips lost something rather than pretending the picture is right.
 */
export function cssFallback(properties: Record<string, number>, extraBlur = 0): string {
  const parts: string[] = [];
  const light = (1 + (properties.brightness ?? 0)) * 2 ** (properties.exposure ?? 0);
  const blur = (properties.blur ?? 0) + extraBlur;
  if (light !== 1) parts.push(`brightness(${light.toFixed(4)})`);
  if (properties.contrast) parts.push(`contrast(${(1 + properties.contrast).toFixed(4)})`);
  if (properties.saturation) parts.push(`saturate(${(1 + properties.saturation).toFixed(4)})`);
  if (properties.temperature) {
    const amount = Math.min(1, Math.abs(properties.temperature));
    parts.push(`sepia(${amount.toFixed(3)})`);
    parts.push(`hue-rotate(${(properties.temperature < 0 ? 170 : -10) * amount}deg)`);
  }
  if (blur > 0) parts.push(`blur(${blur.toFixed(2)}px)`);
  return parts.length ? parts.join(" ") : "none";
}

/** Which properties the CSS fallback silently cannot draw. */
export const CSS_CANNOT_DRAW = ["tint", "sharpen", "grain", "vignette",
                                "corner_radius", "border_width", "shadow"] as const;

/** Names the fallback would drop on this clip, for an honest warning. */
export function fallbackLosses(
  properties: Record<string, number>,
  chain: ResolvedStep[]
): string[] {
  const lost = CSS_CANNOT_DRAW.filter((name) => (properties[name] ?? 0) > 0);
  return chain.length ? [...lost, "effects"] : lost;
}
