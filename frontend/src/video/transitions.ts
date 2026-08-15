/**
 * Drawing the nine transition families.
 *
 * `presets.py` declares ~46 transitions. This file implements **nine**, and the
 * other thirty-seven are those nine with different numbers — a direction, a
 * softness, a blur radius. That is the whole architecture argument in
 * `CAPCUT_TOOL_INVENTORY.md` in its smallest form: families are code, presets
 * are rows, and only rows can be searched by something choosing a look.
 *
 * Every family gets the same two things: which side it is drawing (`from` or
 * `to`) and one `progress` from 0 to 1 shared between them. One number rather
 * than two clocks, because two clocks are how the outgoing and incoming halves
 * end up disagreeing about where the middle is.
 */

import type { DrawItem } from "./document";

export interface TransitionPaint {
  /** Multiplied into the clip's own opacity. */
  alpha: number;
  /** Extra scale, multiplied into the clip's own. */
  scale: number;
  /** Extra rotation in degrees. */
  rotation: number;
  /** Extra offset in canvas pixels. */
  x: number;
  y: number;
  /** Extra blur in pixels, added to the clip's own. */
  blur: number;
  /** A clip region, in canvas pixels, or null for the whole frame. */
  clip: { x: number; y: number; width: number; height: number } | null;
  /** A flat colour drawn over everything, for the flash family. */
  flash: { colour: string; alpha: number } | null;
}

const NONE: TransitionPaint = {
  alpha: 1,
  scale: 1,
  rotation: 0,
  x: 0,
  y: 0,
  blur: 0,
  clip: null,
  flash: null
};

/** Smoothstep. A linear wipe reads as mechanical; every editor eases them. */
function ease(t: number): number {
  return t * t * (3 - 2 * t);
}

function directionVector(direction: string): [number, number] {
  switch (direction) {
    case "left":
      return [-1, 0];
    case "right":
      return [1, 0];
    case "up":
      return [0, -1];
    case "down":
      return [0, 1];
    case "diagonal":
      return [-1, -1];
    default:
      return [-1, 0];
  }
}

/**
 * How this side of a transition should be drawn at this instant.
 *
 * `params` comes straight from the preset row, so a new preset needs no change
 * here at all — which is the point.
 */
export function paintFor(
  item: DrawItem,
  family: string,
  params: Record<string, unknown>,
  canvas: { width: number; height: number }
): TransitionPaint {
  const progress = Math.min(1, Math.max(0, Number(item.transition?.progress ?? 0)));
  const incoming = item.transition?.role === "to";
  const paint: TransitionPaint = { ...NONE };
  const eased = ease(progress);

  switch (family) {
    case "dissolve": {
      paint.alpha = incoming ? eased : 1 - eased;
      break;
    }

    case "wipe": {
      // The incoming clip is revealed through a growing region; the outgoing
      // one is drawn whole underneath it. Clipping rather than fading is what
      // makes a wipe a wipe.
      if (!incoming) break;
      const direction = String(params.direction ?? "left");
      const { width, height } = canvas;
      if (direction === "iris") {
        const radius = Math.hypot(width, height) * 0.5 * eased;
        paint.clip = {
          x: width / 2 - radius,
          y: height / 2 - radius,
          width: radius * 2,
          height: radius * 2
        };
      } else if (direction === "barn") {
        const half = (height * eased) / 2;
        paint.clip = { x: 0, y: height / 2 - half, width, height: half * 2 };
      } else if (direction === "up" || direction === "down") {
        const span = height * eased;
        paint.clip = {
          x: 0,
          y: direction === "up" ? height - span : 0,
          width,
          height: span
        };
      } else if (direction === "clock") {
        // Approximated by a growing box: a real sweep needs a path, and a
        // wrong-looking clock is worse than an honest wipe.
        paint.clip = { x: 0, y: 0, width: width * eased, height };
      } else {
        const span = width * eased;
        paint.clip = {
          x: direction === "right" ? 0 : width - span,
          y: 0,
          width: span,
          height
        };
      }
      break;
    }

    case "slide": {
      // Only the incoming clip moves; the outgoing one stays put underneath.
      if (!incoming) break;
      const [dx, dy] = directionVector(String(params.direction ?? "left"));
      paint.x = -dx * canvas.width * (1 - eased);
      paint.y = -dy * canvas.height * (1 - eased);
      break;
    }

    case "push": {
      // Both move together, as if on one strip.
      const [dx, dy] = directionVector(String(params.direction ?? "left"));
      if (incoming) {
        paint.x = -dx * canvas.width * (1 - eased);
        paint.y = -dy * canvas.height * (1 - eased);
      } else {
        paint.x = dx * canvas.width * eased;
        paint.y = dy * canvas.height * eased;
      }
      break;
    }

    case "zoom": {
      const inward = String(params.direction ?? "in") === "in";
      const strength = Number(params.blur ?? 0);
      const shift = String(params.shift ?? "");
      if (incoming) {
        paint.alpha = eased;
        paint.scale = inward ? 1 + (1 - eased) * 0.6 : 1 - (1 - eased) * 0.4;
      } else {
        paint.alpha = 1 - eased;
        paint.scale = inward ? 1 - eased * 0.4 : 1 + eased * 0.6;
      }
      // Peaks in the middle: a blur that is strongest at the cut hides it,
      // which is exactly what a whip is for.
      paint.blur = strength * Math.sin(Math.PI * progress);
      if (shift) {
        const [dx] = directionVector(shift);
        paint.x = dx * canvas.width * 0.25 * Math.sin(Math.PI * progress) * (incoming ? -1 : 1);
      }
      break;
    }

    case "spin": {
      const turns = Number(params.turns ?? 1);
      const scale = Number(params.scale ?? 1);
      paint.alpha = incoming ? eased : 1 - eased;
      paint.rotation = incoming ? -360 * turns * (1 - eased) : 360 * turns * eased;
      paint.scale = incoming ? 1 + (scale - 1) * (1 - eased) : 1 + (scale - 1) * eased;
      paint.blur = Number(params.blur ?? 0) * Math.sin(Math.PI * progress);
      break;
    }

    case "blur": {
      paint.alpha = incoming ? eased : 1 - eased;
      paint.blur = Number(params.radius ?? 20) * Math.sin(Math.PI * progress);
      break;
    }

    case "flash": {
      // A colour peaks at the midpoint and covers the cut entirely, which is
      // why the clips underneath simply hard-cut.
      paint.alpha = incoming ? (progress >= 0.5 ? 1 : 0) : progress < 0.5 ? 1 : 0;
      const softness = Number(params.softness ?? 0);
      const peak = Math.sin(Math.PI * progress) ** (softness > 0 ? 1 : 1.5);
      paint.flash = { colour: String(params.colour ?? "#ffffff"), alpha: peak };
      break;
    }

    case "glitch": {
      const amount = Number(params.amount ?? 1);
      const slices = Number(params.slices ?? 0);
      paint.alpha = incoming ? (progress >= 0.5 ? 1 : 0) : progress < 0.5 ? 1 : 0;
      // Deterministic jitter: the same tick must produce the same offset, or
      // the preview and the export disagree frame by frame.
      const wobble = Math.sin(progress * Math.PI * 14) * Math.sin(progress * Math.PI * 3);
      paint.x = wobble * 40 * amount;
      if (slices > 0) paint.y = Math.sin(progress * Math.PI * slices) * 12 * amount;
      if (params.flash) {
        paint.flash = {
          colour: String(params.flash),
          alpha: Math.max(0, Math.sin(Math.PI * progress) - 0.5) * 2
        };
      }
      break;
    }

    default:
      break;
  }

  return paint;
}

export const NO_TRANSITION = NONE;
