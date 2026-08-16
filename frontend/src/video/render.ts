/**
 * Painting one frame onto a canvas.
 *
 * The preview and the export call this same function, with the same resolved
 * frame, and differ only in where the canvas came from and what happens to it
 * afterwards. That is the point: a preview drawn by different code than the
 * export is a preview that lies, and the lie is only discovered once the file
 * is finished.
 */

import type { DrawItem, Frame, ProjectDoc } from "./document";
import { NO_TRANSITION, paintFor, type TransitionPaint } from "./transitions";

/** Whatever a clip draws from: a decoded picture, or a video frame. */
export type AssetSource = CanvasImageSource & { width?: number; height?: number };

export interface LoadedAsset {
  source: AssetSource;
  width: number;
  height: number;
}

export type AssetTable = Map<string, LoadedAsset>;

function filterFor(properties: Record<string, number>, extraBlur = 0): string {
  const parts: string[] = [];
  const brightness = properties.brightness ?? 0;
  const exposure = properties.exposure ?? 0;
  const contrast = properties.contrast ?? 0;
  const saturation = properties.saturation ?? 0;
  const temperature = properties.temperature ?? 0;
  const blur = (properties.blur ?? 0) + extraBlur;
  // Exposure is a stop, so it multiplies rather than adds — and it composes
  // with brightness instead of replacing it.
  const light = (1 + brightness) * 2 ** exposure;
  if (light !== 1) parts.push(`brightness(${light.toFixed(4)})`);
  if (contrast) parts.push(`contrast(${(1 + contrast).toFixed(4)})`);
  if (saturation) parts.push(`saturate(${(1 + saturation).toFixed(4)})`);
  // Warm and cool are a hue rotation plus a sepia wash — cheap, and close
  // enough that nobody reaches for a colour matrix at this size.
  if (temperature) {
    parts.push(`sepia(${Math.min(1, Math.abs(temperature)).toFixed(3)})`);
    parts.push(`hue-rotate(${(temperature < 0 ? 170 : -10) * Math.abs(temperature)}deg)`);
  }
  if (blur > 0) parts.push(`blur(${blur.toFixed(2)}px)`);
  return parts.length ? parts.join(" ") : "none";
}

/** The transition paint for this item, or a no-op when it is not in one. */
function transitionPaint(
  item: DrawItem,
  project: ProjectDoc,
  lookup: TransitionLookup | undefined
): TransitionPaint {
  const preset = item.transition?.preset;
  if (!preset || !lookup) return NO_TRANSITION;
  const spec = lookup(preset);
  if (!spec) return NO_TRANSITION;
  return paintFor(item, spec.family, spec.params ?? {}, {
    width: project.width,
    height: project.height
  });
}

/** Resolves a preset id to its family and params — the registry, fetched once. */
export type TransitionLookup = (
  preset: string
) => { family: string; params: Record<string, unknown> } | undefined;

/**
 * How a source of one shape sits inside a canvas of another.
 *
 * `cover` fills the frame and crops the overflow, which is what a vertical
 * canvas needs from a landscape picture and what CapCut does by default.
 */
function fitBox(
  sourceWidth: number,
  sourceHeight: number,
  canvasWidth: number,
  canvasHeight: number,
  fit: string
): { width: number; height: number } {
  if (!sourceWidth || !sourceHeight) return { width: canvasWidth, height: canvasHeight };
  if (fit === "stretch") return { width: canvasWidth, height: canvasHeight };
  if (fit === "none") return { width: sourceWidth, height: sourceHeight };
  const scale =
    fit === "contain"
      ? Math.min(canvasWidth / sourceWidth, canvasHeight / sourceHeight)
      : Math.max(canvasWidth / sourceWidth, canvasHeight / sourceHeight);
  return { width: sourceWidth * scale, height: sourceHeight * scale };
}

function drawTextItem(
  context: CanvasRenderingContext2D,
  item: DrawItem,
  canvasWidth: number
): void {
  const style = item.style as Record<string, unknown>;
  const size = Number(style.size ?? 64);
  const family = String(style.font ?? "Inter, system-ui, sans-serif");
  const weight = String(style.weight ?? "700");
  const align = String(style.align ?? "center") as CanvasTextAlign;
  const lineHeight = size * Number(style.line_height ?? 1.25);
  const maxWidth = canvasWidth * Number(style.max_width ?? 0.86);

  context.font = `${weight} ${size}px ${family}`;
  context.textAlign = align;
  context.textBaseline = "middle";

  // Wrap by measuring, because a caption that runs off the side of a vertical
  // video is the single most common way an overlay is wrong.
  const words = String(item.text ?? "").split(/\s+/).filter(Boolean);
  const lines: string[] = [];
  let current = "";
  for (const word of words) {
    const candidate = current ? `${current} ${word}` : word;
    if (context.measureText(candidate).width > maxWidth && current) {
      lines.push(current);
      current = word;
    } else {
      current = candidate;
    }
  }
  if (current) lines.push(current);
  if (!lines.length) return;

  const top = -((lines.length - 1) * lineHeight) / 2;
  const background = style.background ? String(style.background) : "";
  if (background) {
    const widest = Math.max(...lines.map((line) => context.measureText(line).width));
    const padding = size * 0.3;
    context.fillStyle = background;
    context.fillRect(
      -widest / 2 - padding,
      top - lineHeight / 2 - padding * 0.6,
      widest + padding * 2,
      lines.length * lineHeight + padding * 1.2
    );
  }

  lines.forEach((line, index) => {
    const y = top + index * lineHeight;
    const stroke = Number(style.stroke ?? 0);
    if (stroke > 0) {
      context.lineWidth = stroke;
      context.strokeStyle = String(style.stroke_colour ?? "#000000");
      context.lineJoin = "round";
      context.strokeText(line, 0, y);
    }
    context.fillStyle = String(style.colour ?? "#ffffff");
    context.fillText(line, 0, y);
  });
}

/**
 * Draw one resolved frame.
 *
 * Items arrive bottom layer first and are drawn in that order, so the z-order
 * on screen is the track order in the document with nothing in between to
 * disagree about.
 */
export function paintFrame(
  context: CanvasRenderingContext2D,
  project: ProjectDoc,
  frame: Frame,
  assets: AssetTable,
  transitions?: TransitionLookup
): void {
  const { width, height } = project;
  context.setTransform(1, 0, 0, 1, 0, 0);
  context.globalAlpha = 1;
  context.filter = "none";
  context.fillStyle = project.background || "#000000";
  context.fillRect(0, 0, width, height);

  const flashes: Array<{ colour: string; alpha: number }> = [];

  for (const item of frame.items) {
    if (item.kind === "audio") continue;
    const paint = transitionPaint(item, project, transitions);
    const alpha = Math.max(0, Math.min(1, item.opacity * paint.alpha));
    if (paint.flash) flashes.push(paint.flash);
    if (alpha <= 0) continue;
    const properties = item.properties;
    const style = item.style as Record<string, unknown>;

    context.save();
    context.globalAlpha = alpha;
    context.filter = filterFor(properties, paint.blur);
    context.globalCompositeOperation =
      (style.blend as GlobalCompositeOperation | undefined) ?? "source-over";
    if (paint.clip) {
      context.beginPath();
      context.rect(paint.clip.x, paint.clip.y, paint.clip.width, paint.clip.height);
      context.clip();
    }
    context.translate(
      width * properties.anchor_x + properties.x + paint.x,
      height * properties.anchor_y + properties.y + paint.y
    );
    context.rotate(((properties.rotation + paint.rotation) * Math.PI) / 180);
    context.scale(
      properties.scale * paint.scale * (properties.flip_x >= 0.5 ? -1 : 1),
      properties.scale * paint.scale * (properties.flip_y >= 0.5 ? -1 : 1)
    );

    if (item.kind === "solid") {
      context.fillStyle = String(style.colour ?? "#000000");
      context.fillRect(-width / 2, -height / 2, width, height);
    } else if (item.kind === "text") {
      drawTextItem(context, item, width);
    } else {
      // A clip's own entry wins over its asset's. A still is shared by every
      // clip that places it; a piece of footage is at a different moment of
      // itself in every clip that uses it, so `footage.ts` keys those by clip.
      const asset = assets.get(item.clip_id) ?? assets.get(item.asset_id);
      if (asset) {
        const cropLeft = properties.crop_left;
        const cropTop = properties.crop_top;
        const cropWidth = Math.max(0.01, 1 - cropLeft - properties.crop_right);
        const cropHeight = Math.max(0.01, 1 - cropTop - properties.crop_bottom);
        const box = fitBox(
          asset.width * cropWidth,
          asset.height * cropHeight,
          width,
          height,
          String(style.fit ?? "cover")
        );
        context.drawImage(
          asset.source,
          asset.width * cropLeft,
          asset.height * cropTop,
          asset.width * cropWidth,
          asset.height * cropHeight,
          -box.width / 2,
          -box.height / 2,
          box.width,
          box.height
        );
      } else {
        // A clip whose asset is missing draws as an explicit hole rather than
        // as nothing. Nothing looks like a deliberate gap; this does not.
        context.fillStyle = "rgba(255,64,96,0.18)";
        context.fillRect(-width / 2, -height / 2, width, height);
      }
    }
    context.restore();
  }

  // Flashes go over everything, which is what makes them hide a cut.
  context.setTransform(1, 0, 0, 1, 0, 0);
  context.globalCompositeOperation = "source-over";
  context.filter = "none";
  for (const flash of flashes) {
    context.globalAlpha = Math.max(0, Math.min(1, flash.alpha));
    context.fillStyle = flash.colour;
    context.fillRect(0, 0, width, height);
  }
  context.globalAlpha = 1;
}
