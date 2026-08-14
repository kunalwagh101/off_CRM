/**
 * Regenerate the WebM container fixture.
 *
 * `frontend/src/video/webm.ts` writes WebM and
 * `offsetx_apollo_builder/video/gates.py` reads it. They are two halves of one
 * format written on two sides of the wire, and the only way to know they agree
 * is for one to read what the other wrote.
 *
 * This runs the real muxer under Node and writes
 * `tests/fixtures/muxed_sample.webm`, which `tests/test_video_gates.py` then
 * parses. The frame payloads are synthetic — the muxer never looks inside a
 * chunk, and neither does the parser, so what is under test here is the
 * container, which is exactly the part both files implement.
 *
 *     cd frontend && npm run fixtures
 *
 * It lives inside `frontend/` because it imports Vite to bundle the
 * TypeScript, and Node resolves a script's imports from where the script is.
 */

import { build } from "vite";
import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const fixture = resolve(root, "..", "tests", "fixtures", "muxed_sample.webm");
const outDir = mkdtempSync(join(tmpdir(), "offcrm-webm-"));

await build({
  configFile: false,
  logLevel: "error",
  root,
  build: {
    outDir,
    emptyOutDir: true,
    minify: false,
    lib: { entry: "src/video/webm.ts", formats: ["es"], fileName: "webm" }
  }
});

const { WebMWriter } = await import(join(outDir, "webm.js"));

const FPS = 30;
const SECONDS = 3;
const WIDTH = 1080;
const HEIGHT = 1920;

const writer = new WebMWriter({
  width: WIDTH,
  height: HEIGHT,
  videoCodec: "vp09.00.10.08",
  durationMs: SECONDS * 1000
});

for (let index = 0; index < FPS * SECONDS; index += 1) {
  // Varying lengths so the size fields are not all identical, which is how a
  // length bug hides.
  const data = new Uint8Array(300 + (index % 17));
  data.fill(index & 0xff);
  writer.addVideo({
    timestamp: Math.round((index * 1_000_000) / FPS),
    type: index % (FPS * 2) === 0 ? "key" : "delta",
    byteLength: data.length,
    copyTo: (target) => target.set(data)
  });
}

const bytes = writer.finish();
writeFileSync(fixture, bytes);
console.log(
  `wrote ${fixture} — ${bytes.length} bytes, ${writer.frameCount} frames, ` +
    `${WIDTH}x${HEIGHT}, ${SECONDS}s`
);
