import type { Clip } from "./document";

export type ClipKeyboardCommand =
  | { operation: "move_clip"; payload: { clip_id: string; start: number } }
  | { operation: "trim_clip"; payload: { clip_id: string; head?: number; tail?: number } };

export function clipKeyboardCommand(
  clip: Pick<Clip, "id" | "start">,
  key: string,
  frameTicks: number,
  modifiers: { shift?: boolean; alt?: boolean; tail?: boolean } = {}
): ClipKeyboardCommand | null {
  if (key !== "ArrowLeft" && key !== "ArrowRight") return null;
  const direction = key === "ArrowLeft" ? -1 : 1;
  const step = Math.max(1, frameTicks) * (modifiers.shift ? 10 : 1);

  if (modifiers.alt) {
    return {
      operation: "trim_clip",
      payload: { clip_id: clip.id, head: direction * step }
    };
  }

  if (modifiers.tail) {
    return {
      operation: "trim_clip",
      payload: { clip_id: clip.id, tail: -direction * step }
    };
  }

  return {
    operation: "move_clip",
    payload: { clip_id: clip.id, start: Math.max(0, clip.start + direction * step) }
  };
}
