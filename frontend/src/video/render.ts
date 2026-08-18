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
import { chainFor, cssFallback, fallbackLosses, type EffectTable } from "./effects";
import type { EffectPipeline, ResolvedStep } from "./shaders/pipeline";

/** Whatever a clip draws from: a decoded picture, or a video frame. */
export type AssetSource = CanvasImageSource & { width?: number; height?: number };

export interface LoadedAsset {
  source: AssetSource;
  width: number;
  height: number;
}

export type AssetTable = Map<string, LoadedAsset>;

/**
 * Everything the pixel stage needs, or does not have.
 *
 * `pipeline` is null on a machine with no WebGL2, and that is a supported
 * state rather than an error: the painter falls back to the CSS filters it
 * used to use and reports which clips lost something. A missing vignette is
 * worth saying out loud; it is not worth refusing to draw.
 */
export interface PixelStage {
  pipeline: EffectPipeline | null;
  effects?: EffectTable;
  /** Moves with the frame, never with the clock — see `pipeline.ts`. */
  seed?: number;
  /** Filled in as clips are drawn: `[clipId, whatWasLost]`. */
  losses?: Array<[string, string[]]>;
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

/** The shape a clip's own pixels occupy, before any transform is applied. */
function layerSize(
  item: DrawItem,
  project: ProjectDoc,
  assets: AssetTable
): { width: number; height: number } {
  if (item.kind === "solid" || item.kind === "text") {
    return { width: project.width, height: project.height };
  }
  const asset = assets.get(item.clip_id) ?? assets.get(item.asset_id);
  if (!asset) return { width: project.width, height: project.height };
  const properties = item.properties;
  const cropWidth = Math.max(0.01, 1 - properties.crop_left - properties.crop_right);
  const cropHeight = Math.max(0.01, 1 - properties.crop_top - properties.crop_bottom);
  const box = fitBox(
    asset.width * cropWidth, asset.height * cropHeight,
    project.width, project.height,
    String((item.style as Record<string, unknown>).fit ?? "cover")
  );
  // Capped at the canvas's own longest side. A 6000px source filtered at 6000px
  // costs forty times what it costs at 1920 and cannot show more than 1920 of
  // it, and every pass pays that bill again.
  const cap = Math.max(project.width, project.height);
  const scale = Math.min(1, cap / Math.max(1, Math.max(box.width, box.height)));
  return {
    width: Math.max(1, Math.round(box.width * scale)),
    height: Math.max(1, Math.round(box.height * scale))
  };
}

/** The clip's own pixels, into whatever context is current, centred on origin. */
function drawLayerInPlace(
  context: CanvasRenderingContext2D,
  item: DrawItem,
  project: ProjectDoc,
  assets: AssetTable
): void {
  const { width, height } = project;
  const properties = item.properties;
  const style = item.style as Record<string, unknown>;
  if (item.kind === "solid") {
    context.fillStyle = String(style.colour ?? "#000000");
    context.fillRect(-width / 2, -height / 2, width, height);
    return;
  }
  if (item.kind === "text") {
    drawTextItem(context, item, width);
    return;
  }
  // A clip's own entry wins over its asset's. A still is shared by every clip
  // that places it; a piece of footage is at a different moment of itself in
  // every clip that uses it, so `footage.ts` keys those by clip.
  const asset = assets.get(item.clip_id) ?? assets.get(item.asset_id);
  if (!asset) {
    // A clip whose asset is missing draws as an explicit hole rather than as
    // nothing. Nothing looks like a deliberate gap; this does not.
    context.fillStyle = "rgba(255,64,96,0.18)";
    context.fillRect(-width / 2, -height / 2, width, height);
    return;
  }
  const cropLeft = properties.crop_left;
  const cropTop = properties.crop_top;
  const cropWidth = Math.max(0.01, 1 - cropLeft - properties.crop_right);
  const cropHeight = Math.max(0.01, 1 - cropTop - properties.crop_bottom);
  const box = fitBox(
    asset.width * cropWidth, asset.height * cropHeight,
    width, height, String(style.fit ?? "cover")
  );
  context.drawImage(
    asset.source,
    asset.width * cropLeft, asset.height * cropTop,
    asset.width * cropWidth, asset.height * cropHeight,
    -box.width / 2, -box.height / 2, box.width, box.height
  );
}

/** Reused across frames. Allocating one of these per clip per frame is how a
 *  preview turns into a garbage-collection pause. */
let scratch: { canvas: HTMLCanvasElement | OffscreenCanvas;
               context: CanvasRenderingContext2D } | null = null;

function scratchFor(width: number, height: number) {
  if (!scratch) {
    const canvas: HTMLCanvasElement | OffscreenCanvas =
      typeof OffscreenCanvas !== "undefined"
        ? new OffscreenCanvas(width, height)
        : document.createElement("canvas");
    const context = canvas.getContext("2d", { willReadFrequently: false });
    if (!context) return null;
    scratch = { canvas, context: context as unknown as CanvasRenderingContext2D };
  }
  if (scratch.canvas.width !== width || scratch.canvas.height !== height) {
    scratch.canvas.width = width;
    scratch.canvas.height = height;
  }
  scratch.context.setTransform(1, 0, 0, 1, 0, 0);
  scratch.context.clearRect(0, 0, width, height);
  return scratch;
}

/**
 * One clip, through its effect chain.
 *
 * The clip's own pixels go onto a scratch canvas first, at its own size and
 * with its crop already taken — so a vignette is a vignette of *the clip*, and
 * a rounded corner rounds the clip rather than the frame. Nothing about the
 * transform happens here: rotation, scale and position stay in the 2D context
 * above, which is what stops a filter from being able to move anything.
 */
function renderThroughPipeline(
  item: DrawItem,
  project: ProjectDoc,
  assets: AssetTable,
  chain: ResolvedStep[],
  stage: PixelStage
): { canvas: HTMLCanvasElement | OffscreenCanvas; width: number; height: number } | null {
  const size = layerSize(item, project, assets);
  const board = scratchFor(size.width, size.height);
  if (!board || !stage.pipeline) return null;
  board.context.save();
  board.context.translate(size.width / 2, size.height / 2);
  // The layer helper draws image clips at the size `fitBox` gives for the whole
  // canvas; the scratch may be smaller because of the cap, so scale to match.
  if (item.kind !== "solid" && item.kind !== "text") {
    const asset = assets.get(item.clip_id) ?? assets.get(item.asset_id);
    if (asset) {
      const properties = item.properties;
      const cropWidth = Math.max(0.01, 1 - properties.crop_left - properties.crop_right);
      const cropHeight = Math.max(0.01, 1 - properties.crop_top - properties.crop_bottom);
      const box = fitBox(
        asset.width * cropWidth, asset.height * cropHeight,
        project.width, project.height,
        String((item.style as Record<string, unknown>).fit ?? "cover")
      );
      if (box.width > 0) board.context.scale(size.width / box.width, size.height / box.height);
    }
  }
  drawLayerInPlace(board.context, item, project, assets);
  board.context.restore();

  const output = stage.pipeline.apply(
    board.canvas as CanvasImageSource, size.width, size.height, chain, stage.seed ?? 0
  );
  if (!output) return null;
  return { canvas: output, width: size.width, height: size.height };
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
  transitions?: TransitionLookup,
  stage?: PixelStage
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

    const chain = chainFor(item.clip_id, properties, style, stage?.effects, paint.blur);
    const filtered = chain.length && stage?.pipeline
      ? renderThroughPipeline(item, project, assets, chain, stage)
      : null;
    if (chain.length && !filtered) {
      const lost = fallbackLosses(properties, stage?.effects?.[item.clip_id] ?? []);
      if (lost.length) stage?.losses?.push([item.clip_id, lost]);
    }

    context.save();
    context.globalAlpha = alpha;
    // The GPU already applied everything when it ran; applying the CSS
    // approximation on top would grade the picture twice.
    context.filter = filtered ? "none" : cssFallback(properties, paint.blur);
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

    if (filtered) {
      // The pipeline drew this clip's own pixels at its own size, so all that
      // is left is to place it. Everything about *where* a clip sits stays in
      // the 2D context, which is why a filter cannot break a transform.
      context.drawImage(
        filtered.canvas as CanvasImageSource,
        -filtered.width / 2, -filtered.height / 2, filtered.width, filtered.height
      );
    } else {
      drawLayerInPlace(context, item, project, assets);
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
