/**
 * The forty-eight pixel operations, as GLSL.
 *
 * One fragment program each, all sharing a vertex stage that draws two
 * triangles over the whole viewport. Every program reads `uSource` at `vUv` and
 * writes one colour, so the pipeline can run any of them into any of the others
 * without knowing what they do.
 *
 * **The parameter names match `effects.py` exactly.** A number called `radius`
 * there arrives here as the uniform `radius`, and a colour called `shadow`
 * arrives as `shadow`. Nothing translates between the two files, so nothing can
 * translate them differently.
 *
 * **Nothing here is random.** Grain and noise take a `uSeed` derived from the
 * frame number, not from `Math.random`, because a preview and an export that
 * disagree about the noise are two different videos, and a re-export has to
 * produce the same file it produced yesterday.
 *
 * **Alpha is preserved unless the operation is about alpha.** A grade must not
 * quietly make a transparent overlay opaque, so tone operations write
 * `vec4(rgb, src.a)` and only the keys and mattes touch the fourth channel.
 */

/** Drawn as two triangles covering the clip space square. */
export const VERTEX_SOURCE = `#version 300 es
in vec2 aPos;
out vec2 vUv;
void main() {
  vUv = aPos * 0.5 + 0.5;
  gl_Position = vec4(aPos, 0.0, 1.0);
}`;

/** Shared by every fragment program: the source, its size, and the clock. */
const PREAMBLE = `#version 300 es
precision highp float;
in vec2 vUv;
out vec4 fragColour;
uniform sampler2D uSource;
uniform vec2 uSize;
uniform float uSeed;

const vec3 LUMA = vec3(0.2126, 0.7152, 0.0722);

float luma(vec3 c) { return dot(c, LUMA); }

// A hash with no trigonometry in it. sin-based hashes differ between GPU
// vendors at the last bit, and "the grain is different on your machine" is a
// bug nobody enjoys finding.
float hash12(vec2 p) {
  vec3 v = fract(vec3(p.xyx) * 0.1031);
  v += dot(v, v.yzx + 33.33);
  return fract((v.x + v.y) * v.z);
}

vec2 hash22(vec2 p) {
  vec3 v = fract(vec3(p.xyx) * vec3(0.1031, 0.1030, 0.0973));
  v += dot(v, v.yzx + 33.33);
  return fract((v.xx + v.yz) * v.zy);
}

// Value noise, bilinear between hashed lattice points.
float valueNoise(vec2 p) {
  vec2 i = floor(p);
  vec2 f = fract(p);
  vec2 u = f * f * (3.0 - 2.0 * f);
  return mix(
    mix(hash12(i), hash12(i + vec2(1.0, 0.0)), u.x),
    mix(hash12(i + vec2(0.0, 1.0)), hash12(i + vec2(1.0, 1.0)), u.x),
    u.y);
}

vec3 rgb2hsv(vec3 c) {
  vec4 K = vec4(0.0, -1.0 / 3.0, 2.0 / 3.0, -1.0);
  vec4 p = mix(vec4(c.bg, K.wz), vec4(c.gb, K.xy), step(c.b, c.g));
  vec4 q = mix(vec4(p.xyw, c.r), vec4(c.r, p.yzx), step(p.x, c.r));
  float d = q.x - min(q.w, q.y);
  return vec3(abs(q.z + (q.w - q.y) / (6.0 * d + 1e-10)), d / (q.x + 1e-10), q.x);
}

vec3 hsv2rgb(vec3 c) {
  vec4 K = vec4(1.0, 2.0 / 3.0, 1.0 / 3.0, 3.0);
  vec3 p = abs(fract(c.xxx + K.xyz) * 6.0 - K.www);
  return c.z * mix(K.xxx, clamp(p - K.xxx, 0.0, 1.0), c.y);
}

vec4 src() { return texture(uSource, vUv); }
vec4 at(vec2 uv) { return texture(uSource, clamp(uv, vec2(0.0005), vec2(0.9995))); }
`;

/** One program, and which uniforms it declares. */
export interface ProgramSource {
  /** The full fragment shader, preamble included. */
  fragment: string;
  /** Extra uniforms beyond the shared ones, so the runner can skip lookups. */
  numbers: string[];
  colours: string[];
}

function shader(body: string, numbers: string[] = [], colours: string[] = []): ProgramSource {
  const declarations = [
    ...numbers.map((name) => `uniform float ${name};`),
    ...colours.map((name) => `uniform vec3 ${name};`)
  ].join("\n");
  return { fragment: `${PREAMBLE}\n${declarations}\n${body}`, numbers, colours };
}

/**
 * Every primitive, keyed by the id `effects.py` declares.
 *
 * The blur family takes an extra `uAxis` and `uPass` the runner supplies — a
 * separable gaussian is the same program run twice with a different direction,
 * which is the whole reason it is cheap.
 */
export const PROGRAMS: Record<string, ProgramSource> = {
  // ── tone ──────────────────────────────────────────────────────────────────
  exposure: shader(
    `void main() {
      vec4 c = src();
      fragColour = vec4(c.rgb * exp2(stops), c.a);
    }`,
    ["stops"]
  ),

  contrast: shader(
    `void main() {
      vec4 c = src();
      fragColour = vec4((c.rgb - pivot) * (1.0 + amount) + pivot, c.a);
    }`,
    ["amount", "pivot"]
  ),

  saturation: shader(
    `void main() {
      vec4 c = src();
      fragColour = vec4(mix(vec3(luma(c.rgb)), c.rgb, 1.0 + amount), c.a);
    }`,
    ["amount"]
  ),

  vibrance: shader(
    // Weighted by how unsaturated the pixel already is, so skin — which sits
    // near the saturated end — is left where it was.
    `void main() {
      vec4 c = src();
      float mx = max(c.r, max(c.g, c.b));
      float mn = min(c.r, min(c.g, c.b));
      float sat = mx - mn;
      float weight = 1.0 - clamp(sat, 0.0, 1.0);
      fragColour = vec4(mix(vec3(luma(c.rgb)), c.rgb, 1.0 + amount * weight), c.a);
    }`,
    ["amount"]
  ),

  temperature: shader(
    `void main() {
      vec4 c = src();
      vec3 shifted = c.rgb + vec3(amount * 0.18, 0.0, -amount * 0.18);
      fragColour = vec4(shifted, c.a);
    }`,
    ["amount"]
  ),

  tint: shader(
    `void main() {
      vec4 c = src();
      vec3 shifted = c.rgb + vec3(-amount * 0.09, amount * 0.18, -amount * 0.09);
      fragColour = vec4(shifted, c.a);
    }`,
    ["amount"]
  ),

  hue_rotate: shader(
    `void main() {
      vec4 c = src();
      vec3 hsv = rgb2hsv(clamp(c.rgb, 0.0, 1.0));
      hsv.x = fract(hsv.x + degrees / 360.0);
      fragColour = vec4(hsv2rgb(hsv), c.a);
    }`,
    ["degrees"]
  ),

  levels: shader(
    `void main() {
      vec4 c = src();
      vec3 v = clamp((c.rgb - black) / max(1e-4, white - black), 0.0, 1.0);
      fragColour = vec4(pow(v, vec3(1.0 / max(0.01, gamma))), c.a);
    }`,
    ["black", "white", "gamma"]
  ),

  curve_s: shader(
    // smoothstep is already an S; mixing toward it by amount gives a curve
    // that is exactly the identity at zero and cannot overshoot at one.
    `void main() {
      vec4 c = src();
      vec3 v = clamp(c.rgb, 0.0, 1.0);
      vec3 s = smoothstep(vec3(0.0), vec3(1.0), v);
      fragColour = vec4(mix(v, s, amount), c.a);
    }`,
    ["amount"]
  ),

  fade: shader(
    `void main() {
      vec4 c = src();
      fragColour = vec4(c.rgb * (1.0 - amount * 0.35) + amount * 0.16, c.a);
    }`,
    ["amount"]
  ),

  bleach_bypass: shader(
    `void main() {
      vec4 c = src();
      float l = luma(c.rgb);
      vec3 hard = mix(2.0 * c.rgb * l, 1.0 - 2.0 * (1.0 - c.rgb) * (1.0 - l), step(0.5, l));
      fragColour = vec4(mix(c.rgb, hard, amount), c.a);
    }`,
    ["amount"]
  ),

  duotone: shader(
    `void main() {
      vec4 c = src();
      fragColour = vec4(mix(c.rgb, mix(dark, light, luma(c.rgb)), amount), c.a);
    }`,
    ["amount"],
    ["dark", "light"]
  ),

  split_tone: shader(
    `void main() {
      vec4 c = src();
      float l = luma(c.rgb);
      // Two ramps meeting at balance, so a shadow tone never reaches the
      // highlights and back again.
      float low = 1.0 - smoothstep(0.0, max(0.01, balance), l);
      float high = smoothstep(balance, 1.0, l);
      vec3 tinted = c.rgb + (shadow - 0.5) * low * amount + (highlight - 0.5) * high * amount;
      fragColour = vec4(tinted, c.a);
    }`,
    ["amount", "balance"],
    ["shadow", "highlight"]
  ),

  posterize: shader(
    `void main() {
      vec4 c = src();
      float n = max(2.0, floor(levels));
      fragColour = vec4(floor(clamp(c.rgb, 0.0, 1.0) * n) / (n - 1.0), c.a);
    }`,
    ["levels"]
  ),

  threshold: shader(
    `void main() {
      vec4 c = src();
      float l = luma(c.rgb);
      float v = smoothstep(level - softness - 1e-4, level + softness + 1e-4, l);
      fragColour = vec4(mix(c.rgb, vec3(v), amount), c.a);
    }`,
    ["level", "softness", "amount"]
  ),

  invert: shader(
    `void main() {
      vec4 c = src();
      fragColour = vec4(mix(c.rgb, 1.0 - c.rgb, amount), c.a);
    }`,
    ["amount"]
  ),

  sepia: shader(
    `void main() {
      vec4 c = src();
      vec3 s = vec3(
        dot(c.rgb, vec3(0.393, 0.769, 0.189)),
        dot(c.rgb, vec3(0.349, 0.686, 0.168)),
        dot(c.rgb, vec3(0.272, 0.534, 0.131)));
      fragColour = vec4(mix(c.rgb, s, amount), c.a);
    }`,
    ["amount"]
  ),

  grayscale: shader(
    // The weights are parameters rather than constants because that is what a
    // darkroom colour filter is: weight red heavily and a blue sky goes black.
    `void main() {
      vec4 c = src();
      float total = max(1e-4, red + green + blue);
      float g = dot(c.rgb, vec3(red, green, blue) / total);
      fragColour = vec4(mix(c.rgb, vec3(g), amount), c.a);
    }`,
    ["amount", "red", "green", "blue"]
  ),

  // ── focus ─────────────────────────────────────────────────────────────────
  blur: shader(
    // One axis per pass. Nine taps at a spacing that grows with the radius: a
    // true gaussian at radius 60 would be 121 taps, and this is visually the
    // same for a fraction of the cost.
    `uniform float uAxis;
    void main() {
      vec4 c = src();
      if (radius <= 0.01) { fragColour = c; return; }
      vec2 stepUv = (uAxis < 0.5 ? vec2(1.0, 0.0) : vec2(0.0, 1.0)) * radius / uSize;
      float weights[5];
      weights[0] = 0.2270270270; weights[1] = 0.1945945946; weights[2] = 0.1216216216;
      weights[3] = 0.0540540541; weights[4] = 0.0162162162;
      vec4 sum = c * weights[0];
      for (int i = 1; i < 5; i++) {
        float o = float(i) * 0.62;
        sum += at(vUv + stepUv * o) * weights[i];
        sum += at(vUv - stepUv * o) * weights[i];
      }
      fragColour = sum;
    }`,
    ["radius"]
  ),

  directional_blur: shader(
    `void main() {
      if (radius <= 0.01) { fragColour = src(); return; }
      float a = radians(angle);
      vec2 stepUv = vec2(cos(a), sin(a)) * radius / uSize;
      vec4 sum = vec4(0.0);
      for (int i = -6; i <= 6; i++) {
        sum += at(vUv + stepUv * (float(i) / 6.0));
      }
      fragColour = sum / 13.0;
    }`,
    ["radius", "angle"]
  ),

  radial_blur: shader(
    `void main() {
      if (amount <= 0.0005) { fragColour = src(); return; }
      vec2 centre = vec2(centre_x, centre_y);
      vec2 delta = vUv - centre;
      vec4 sum = vec4(0.0);
      for (int i = 0; i < 12; i++) {
        float scale = 1.0 - amount * (float(i) / 11.0);
        sum += at(centre + delta * scale);
      }
      fragColour = sum / 12.0;
    }`,
    ["amount", "centre_x", "centre_y"]
  ),

  sharpen: shader(
    // Unsharp mask against a small box, which is close enough to a gaussian at
    // these radii and costs four taps instead of a second pass.
    `void main() {
      vec4 c = src();
      vec2 stepUv = radius / uSize;
      vec4 soft = (at(vUv + vec2(stepUv.x, 0.0)) + at(vUv - vec2(stepUv.x, 0.0))
                 + at(vUv + vec2(0.0, stepUv.y)) + at(vUv - vec2(0.0, stepUv.y))) * 0.25;
      fragColour = vec4(c.rgb + (c.rgb - soft.rgb) * amount, c.a);
    }`,
    ["amount", "radius"]
  ),

  // Bloom, soft focus, tilt shift and drop shadow all need a blurred copy of
  // the source. The runner makes one and binds it as `uAux`, which is what
  // their extra passes are for.
  bloom: shader(
    `uniform sampler2D uAux;
    void main() {
      vec4 c = src();
      vec4 b = texture(uAux, vUv);
      vec3 bright = max(vec3(0.0), b.rgb - threshold) / max(0.01, 1.0 - threshold);
      fragColour = vec4(c.rgb + bright * intensity, c.a);
    }`,
    ["threshold", "radius", "intensity"]
  ),

  soft_focus: shader(
    `uniform sampler2D uAux;
    void main() {
      vec4 c = src();
      vec4 b = texture(uAux, vUv);
      fragColour = vec4(mix(c.rgb, max(c.rgb, b.rgb), amount), c.a);
    }`,
    ["radius", "amount"]
  ),

  tilt_shift: shader(
    `uniform sampler2D uAux;
    void main() {
      vec4 c = src();
      vec4 b = texture(uAux, vUv);
      float d = abs(vUv.y - focus);
      float sharp = 1.0 - smoothstep(width * 0.5, width * 0.5 + width, d);
      fragColour = mix(mix(c, b, amount), c, sharp);
    }`,
    ["radius", "focus", "width", "amount"]
  ),

  // ── distortion ────────────────────────────────────────────────────────────
  pixelate: shader(
    `void main() {
      vec2 cells = max(vec2(1.0), uSize / max(1.0, size));
      fragColour = at((floor(vUv * cells) + 0.5) / cells);
    }`,
    ["size"]
  ),

  chromatic_aberration: shader(
    `void main() {
      vec2 delta = (vUv - 0.5) * amount;
      vec4 c = src();
      fragColour = vec4(at(vUv + delta).r, c.g, at(vUv - delta).b, c.a);
    }`,
    ["amount"]
  ),

  lens_distortion: shader(
    `void main() {
      vec2 p = vUv - 0.5;
      float r2 = dot(p, p);
      fragColour = at(0.5 + p * (1.0 + amount * r2));
    }`,
    ["amount"]
  ),

  rgb_split: shader(
    `void main() {
      float a = radians(angle);
      vec2 delta = vec2(cos(a), sin(a)) * amount;
      vec4 c = src();
      fragColour = vec4(at(vUv + delta).r, c.g, at(vUv - delta).b, c.a);
    }`,
    ["amount", "angle"]
  ),

  displace: shader(
    `void main() {
      vec2 p = vUv * scale + uSeed * speed;
      vec2 push = vec2(valueNoise(p) - 0.5, valueNoise(p + 37.0) - 0.5) * amount;
      fragColour = at(vUv + push);
    }`,
    ["amount", "scale", "speed"]
  ),

  wave: shader(
    `void main() {
      float phase = uSeed * speed;
      vec2 push = axis < 0.5
        ? vec2(sin(vUv.y * frequency + phase) * amplitude, 0.0)
        : vec2(0.0, sin(vUv.x * frequency + phase) * amplitude);
      fragColour = at(vUv + push);
    }`,
    ["amplitude", "frequency", "speed", "axis"]
  ),

  swirl: shader(
    `void main() {
      vec2 centre = vec2(centre_x, centre_y);
      vec2 p = vUv - centre;
      // Aspect-correct, or a swirl on a vertical canvas is an oval.
      p.x *= uSize.x / uSize.y;
      float d = length(p);
      float t = amount * max(0.0, 1.0 - d / max(0.01, radius));
      float s = sin(t), co = cos(t);
      p = vec2(p.x * co - p.y * s, p.x * s + p.y * co);
      p.x /= uSize.x / uSize.y;
      fragColour = at(centre + p);
    }`,
    ["amount", "radius", "centre_x", "centre_y"]
  ),

  kaleidoscope: shader(
    `void main() {
      vec2 p = vUv - 0.5;
      p.x *= uSize.x / uSize.y;
      float wedge = 6.28318530718 / max(2.0, floor(segments));
      float a = atan(p.y, p.x) - radians(angle);
      a = mod(a, wedge);
      a = abs(a - wedge * 0.5);
      float r = length(p);
      vec2 folded = vec2(cos(a), sin(a)) * r;
      folded.x /= uSize.x / uSize.y;
      fragColour = mix(src(), at(folded + 0.5), amount);
    }`,
    ["segments", "angle", "amount"]
  ),

  mirror: shader(
    `void main() {
      vec2 uv = vUv;
      if (axis < 0.5) {
        uv.x = side < 0.5 ? min(uv.x, 1.0 - uv.x) : max(uv.x, 1.0 - uv.x);
      } else {
        uv.y = side < 0.5 ? min(uv.y, 1.0 - uv.y) : max(uv.y, 1.0 - uv.y);
      }
      fragColour = mix(src(), at(uv), amount);
    }`,
    ["axis", "side", "amount"]
  ),

  punch: shader(
    `void main() {
      vec2 centre = vec2(centre_x, centre_y);
      fragColour = at(centre + (vUv - centre) / max(0.01, scale));
    }`,
    ["scale", "centre_x", "centre_y"]
  ),

  // ── texture ───────────────────────────────────────────────────────────────
  grain: shader(
    // uSeed moves with the frame, so this crawls the way film grain does.
    `void main() {
      vec4 c = src();
      float n = hash12(floor(vUv * uSize / max(0.3, size)) + uSeed * 7.13) - 0.5;
      fragColour = vec4(c.rgb + n * amount, c.a);
    }`,
    ["amount", "size"]
  ),

  noise: shader(
    // The same field every frame: texture rather than movement.
    `void main() {
      vec4 c = src();
      float n = hash12(floor(vUv * uSize / max(0.3, size))) - 0.5;
      fragColour = vec4(c.rgb + n * amount, c.a);
    }`,
    ["amount", "size"]
  ),

  scanlines: shader(
    `void main() {
      vec4 c = src();
      float band = sin((vUv.y + uSeed * speed * 0.01) * count * 3.14159265);
      fragColour = vec4(c.rgb * (1.0 - amount * 0.5 * (0.5 + 0.5 * band)), c.a);
    }`,
    ["count", "amount", "speed"]
  ),

  halftone: shader(
    `void main() {
      vec4 c = src();
      float a = radians(angle);
      mat2 rot = mat2(cos(a), -sin(a), sin(a), cos(a));
      vec2 p = rot * (vUv * uSize) / max(2.0, size);
      vec2 cell = fract(p) - 0.5;
      float l = luma(c.rgb);
      // Dot radius from luminance: dark areas get big dots.
      float dotMask = 1.0 - smoothstep(0.0, 0.08, length(cell) - sqrt(1.0 - l) * 0.5);
      fragColour = vec4(mix(c.rgb, vec3(1.0 - dotMask), amount), c.a);
    }`,
    ["size", "angle", "amount"]
  ),

  dither: shader(
    // A 4x4 Bayer matrix, written out rather than computed: an index expression
    // into a const array is not portable across GLSL ES implementations.
    `float bayer(vec2 p) {
      vec2 i = mod(floor(p), 4.0);
      float x = i.x, y = i.y;
      float v = 0.0;
      if (y < 0.5)      { v = x < 0.5 ? 0.0 : (x < 1.5 ? 8.0 : (x < 2.5 ? 2.0 : 10.0)); }
      else if (y < 1.5) { v = x < 0.5 ? 12.0 : (x < 1.5 ? 4.0 : (x < 2.5 ? 14.0 : 6.0)); }
      else if (y < 2.5) { v = x < 0.5 ? 3.0 : (x < 1.5 ? 11.0 : (x < 2.5 ? 1.0 : 9.0)); }
      else              { v = x < 0.5 ? 15.0 : (x < 1.5 ? 7.0 : (x < 2.5 ? 13.0 : 5.0)); }
      return v / 16.0;
    }
    void main() {
      vec4 c = src();
      float n = max(2.0, floor(levels));
      vec3 v = clamp(c.rgb, 0.0, 1.0) + (bayer(vUv * uSize) - 0.5) / n;
      fragColour = vec4(mix(c.rgb, floor(v * n) / (n - 1.0), amount), c.a);
    }`,
    ["levels", "amount"]
  ),

  // ── shape, matte and key ──────────────────────────────────────────────────
  vignette: shader(
    `void main() {
      vec4 c = src();
      float aspect = uSize.x / uSize.y;
      vec2 p = (vUv - 0.5) * 2.0;
      p.x *= aspect;
      float d = length(p) / max(0.01, length(vec2(aspect, 1.0)));
      float v = smoothstep(radius, radius + softness, d);
      fragColour = vec4(mix(c.rgb, colour, v * amount), c.a);
    }`,
    ["amount", "radius", "softness"],
    ["colour"]
  ),

  rounded_frame: shader(
    // A signed distance to a rounded box, in pixels, so the corner is the same
    // size on any canvas.
    `void main() {
      vec4 c = src();
      vec2 halfSize = uSize * 0.5;
      vec2 p = abs(vUv * uSize - halfSize);
      float r = min(radius, min(halfSize.x, halfSize.y));
      vec2 q = p - (halfSize - r);
      float d = length(max(q, 0.0)) + min(max(q.x, q.y), 0.0) - r;
      float inside = 1.0 - smoothstep(-1.0, 1.0, d);
      float edge = border > 0.0
        ? (1.0 - smoothstep(-1.0, 1.0, d + border)) : 1.0;
      vec3 rgb = mix(border_colour, c.rgb, edge);
      fragColour = vec4(rgb, c.a * inside);
    }`,
    ["radius", "border"],
    ["border_colour"]
  ),

  drop_shadow: shader(
    `uniform sampler2D uAux;
    void main() {
      vec4 c = src();
      vec2 offset = vec2(offset_x, -offset_y) / uSize;
      float shade = texture(uAux, clamp(vUv - offset, vec2(0.0), vec2(1.0))).a * opacity;
      // Source-over of the layer onto its own shadow. Doing it the other way
      // round darkens every semi-transparent edge of the layer itself.
      float under = shade * (1.0 - c.a);
      float alpha = c.a + under;
      vec3 rgb = alpha > 0.0001 ? (c.rgb * c.a + colour * under) / alpha : c.rgb;
      fragColour = vec4(rgb, alpha);
    }`,
    ["radius", "offset_x", "offset_y", "opacity"],
    ["colour"]
  ),

  chroma_key: shader(
    // Distance in chroma only, so a green that is merely darker still keys.
    `void main() {
      vec4 c = src();
      vec3 keyHsv = rgb2hsv(colour);
      vec3 hsv = rgb2hsv(clamp(c.rgb, 0.0, 1.0));
      float dh = abs(hsv.x - keyHsv.x);
      dh = min(dh, 1.0 - dh) * 2.0;
      float ds = abs(hsv.y - keyHsv.y) * 0.5;
      float d = sqrt(dh * dh + ds * ds) * (1.0 + (1.0 - hsv.y));
      float keyed = smoothstep(tolerance, tolerance + softness + 1e-4, d);
      // Spill: pull the key colour back out of what survived, or every edge
      // keeps a green rim and the composite looks like a composite.
      float excess = max(0.0, dot(c.rgb, normalize(colour + 1e-4)) - luma(c.rgb));
      vec3 despilled = c.rgb - normalize(colour + 1e-4) * excess * spill;
      fragColour = vec4(mix(c.rgb, despilled, amount), c.a * mix(1.0, keyed, amount));
    }`,
    ["tolerance", "softness", "spill", "amount"],
    ["colour"]
  ),

  luma_key: shader(
    `void main() {
      vec4 c = src();
      float l = luma(clamp(c.rgb, 0.0, 1.0));
      float keep = smoothstep(threshold, threshold + softness + 1e-4, l);
      if (invert > 0.5) keep = 1.0 - smoothstep(threshold - softness - 1e-4, threshold, l);
      fragColour = vec4(c.rgb, c.a * mix(1.0, keep, amount));
    }`,
    ["threshold", "softness", "invert", "amount"]
  ),

  mask_linear: shader(
    `void main() {
      vec4 c = src();
      float a = radians(angle);
      float d = dot(vUv - 0.5, vec2(cos(a), sin(a))) + 0.5;
      float keep = smoothstep(position - softness - 1e-4, position + softness + 1e-4, d);
      if (invert > 0.5) keep = 1.0 - keep;
      fragColour = vec4(c.rgb, c.a * mix(1.0, keep, amount));
    }`,
    ["angle", "position", "softness", "invert", "amount"]
  ),

  mask_radial: shader(
    `void main() {
      vec4 c = src();
      vec2 p = vUv - vec2(centre_x, centre_y);
      p.x *= (uSize.x / uSize.y) / max(0.01, aspect);
      float d = length(p);
      float keep = 1.0 - smoothstep(radius, radius + softness + 1e-4, d);
      if (invert > 0.5) keep = 1.0 - keep;
      fragColour = vec4(c.rgb, c.a * mix(1.0, keep, amount));
    }`,
    ["centre_x", "centre_y", "radius", "softness", "aspect", "invert", "amount"]
  ),

  edge: shader(
    `void main() {
      vec4 c = src();
      vec2 stepUv = thickness / uSize;
      float tl = luma(at(vUv + vec2(-stepUv.x,  stepUv.y)).rgb);
      float t  = luma(at(vUv + vec2(0.0,      stepUv.y)).rgb);
      float tr = luma(at(vUv + vec2( stepUv.x,  stepUv.y)).rgb);
      float l  = luma(at(vUv + vec2(-stepUv.x, 0.0)).rgb);
      float r  = luma(at(vUv + vec2( stepUv.x, 0.0)).rgb);
      float bl = luma(at(vUv + vec2(-stepUv.x, -stepUv.y)).rgb);
      float b  = luma(at(vUv + vec2(0.0,     -stepUv.y)).rgb);
      float br = luma(at(vUv + vec2( stepUv.x, -stepUv.y)).rgb);
      float gx = -tl - 2.0 * l - bl + tr + 2.0 * r + br;
      float gy =  tl + 2.0 * t + tr - bl - 2.0 * b - br;
      float g = clamp(length(vec2(gx, gy)), 0.0, 1.0);
      fragColour = vec4(mix(c.rgb, mix(c.rgb, vec3(g), blend), amount), c.a);
    }`,
    ["amount", "thickness", "blend"]
  )
};

/** Which primitives want a blurred copy of the source bound as `uAux`. */
export const NEEDS_BLURRED_COPY = new Set(["bloom", "soft_focus", "tilt_shift", "drop_shadow"]);

/** Which primitives run the blur program twice rather than their own. */
export const SEPARABLE = new Set(["blur"]);
