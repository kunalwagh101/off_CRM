/**
 * Running an effect chain on the GPU.
 *
 * A clip's pixels go in, a canvas comes out, and in between each primitive is
 * one full-screen draw into a framebuffer that becomes the next one's input.
 * Two textures, swapped — the classic ping-pong — so a chain of any length uses
 * the same memory as a chain of one.
 *
 * **The preview and the export share this.** That is not a convenience; it is
 * the same rule the rest of this feature runs on. A preview drawn by different
 * code than the export is a preview that lies, and the lie is only discovered
 * once the file is finished.
 *
 * **Nothing here decides what an effect is.** The chain arrives already
 * resolved by the server — names and numbers, no lookups — so a look nobody
 * declared cannot reach a shader, and this file has no opinion about what any
 * of them mean.
 *
 * **A machine without WebGL2 still exports.** `EffectPipeline.create` returns
 * null rather than throwing, and the painter draws unfiltered and says so. A
 * missing filter is worth reporting; it is not worth refusing to render.
 */

import { NEEDS_BLURRED_COPY, PROGRAMS, SEPARABLE, VERTEX_SOURCE } from "./glsl";

/** One resolved pass, exactly as the manifest carries it. */
export interface ResolvedStep {
  primitive: string;
  passes: number;
  numbers: Record<string, number>;
  colours: Record<string, string>;
}

/** `#rrggbb` to the three floats a `vec3` uniform wants. */
export function hexToRgb(hex: string): [number, number, number] {
  const body = (hex || "#000000").replace("#", "");
  const full = body.length === 3 ? body.split("").map((c) => c + c).join("") : body;
  const value = Number.parseInt(full.slice(0, 6) || "000000", 16);
  return [((value >> 16) & 255) / 255, ((value >> 8) & 255) / 255, (value & 255) / 255];
}

interface Compiled {
  program: WebGLProgram;
  uniforms: Map<string, WebGLUniformLocation | null>;
}

interface Target {
  framebuffer: WebGLFramebuffer;
  texture: WebGLTexture;
}

/** Why a chain did not run, when it did not. */
export interface EffectProblem {
  primitive: string;
  reason: string;
}

export class EffectPipeline {
  private constructor(
    private readonly gl: WebGL2RenderingContext,
    private readonly canvas: HTMLCanvasElement | OffscreenCanvas
  ) {}

  private programs = new Map<string, Compiled | null>();
  private targets: Target[] = [];
  private aux: Target | null = null;
  private sourceTexture: WebGLTexture | null = null;
  private width = 0;
  private height = 0;
  /** Primitives whose shader would not compile here. Reported, then skipped. */
  readonly problems: EffectProblem[] = [];

  /**
   * A pipeline, or null on a machine that cannot run one.
   *
   * `premultipliedAlpha: false` matters: the shaders work in straight alpha
   * because a key that multiplied its colour by its own matte would darken
   * every soft edge it produced.
   */
  static create(): EffectPipeline | null {
    if (typeof document === "undefined" && typeof OffscreenCanvas === "undefined") return null;
    const canvas: HTMLCanvasElement | OffscreenCanvas =
      typeof OffscreenCanvas !== "undefined"
        ? new OffscreenCanvas(2, 2)
        : document.createElement("canvas");
    const gl = canvas.getContext("webgl2", {
      premultipliedAlpha: false,
      preserveDrawingBuffer: true,
      antialias: false,
      alpha: true
    }) as WebGL2RenderingContext | null;
    if (!gl) return null;
    const pipeline = new EffectPipeline(gl, canvas);
    return pipeline.setUp() ? pipeline : null;
  }

  private quad: WebGLBuffer | null = null;
  private vertex: WebGLShader | null = null;

  private setUp(): boolean {
    const { gl } = this;
    const vertex = gl.createShader(gl.VERTEX_SHADER);
    if (!vertex) return false;
    gl.shaderSource(vertex, VERTEX_SOURCE);
    gl.compileShader(vertex);
    if (!gl.getShaderParameter(vertex, gl.COMPILE_STATUS)) return false;
    this.vertex = vertex;

    const quad = gl.createBuffer();
    if (!quad) return false;
    gl.bindBuffer(gl.ARRAY_BUFFER, quad);
    gl.bufferData(
      gl.ARRAY_BUFFER,
      new Float32Array([-1, -1, 3, -1, -1, 3]),
      gl.STATIC_DRAW
    );
    this.quad = quad;
    return true;
  }

  private compile(primitive: string): Compiled | null {
    const cached = this.programs.get(primitive);
    if (cached !== undefined) return cached;

    const { gl } = this;
    const source = PROGRAMS[primitive];
    if (!source || !this.vertex) {
      this.programs.set(primitive, null);
      this.problems.push({ primitive, reason: "no shader for this operation" });
      return null;
    }
    const fragment = gl.createShader(gl.FRAGMENT_SHADER);
    const program = fragment ? gl.createProgram() : null;
    if (!fragment || !program) {
      this.programs.set(primitive, null);
      return null;
    }
    gl.shaderSource(fragment, source.fragment);
    gl.compileShader(fragment);
    if (!gl.getShaderParameter(fragment, gl.COMPILE_STATUS)) {
      const log = gl.getShaderInfoLog(fragment) || "would not compile";
      gl.deleteShader(fragment);
      this.programs.set(primitive, null);
      this.problems.push({ primitive, reason: log.trim().split("\n")[0] });
      return null;
    }
    gl.attachShader(program, this.vertex);
    gl.attachShader(program, fragment);
    gl.bindAttribLocation(program, 0, "aPos");
    gl.linkProgram(program);
    gl.deleteShader(fragment);
    if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
      const log = gl.getProgramInfoLog(program) || "would not link";
      this.programs.set(primitive, null);
      this.problems.push({ primitive, reason: log.trim().split("\n")[0] });
      return null;
    }

    // Every uniform the program actually kept. A parameter a shader does not
    // read is optimised out and its location is null, which is not an error —
    // `bloom` declares a radius it never samples, because the *runner* uses it.
    const uniforms = new Map<string, WebGLUniformLocation | null>();
    for (const name of ["uSource", "uSize", "uSeed", "uAxis", "uAux",
                        ...source.numbers, ...source.colours]) {
      uniforms.set(name, gl.getUniformLocation(program, name));
    }
    const compiled = { program, uniforms };
    this.programs.set(primitive, compiled);
    return compiled;
  }

  private resize(width: number, height: number): void {
    if (this.width === width && this.height === height) return;
    const { gl } = this;
    for (const target of [...this.targets, this.aux]) {
      if (!target) continue;
      gl.deleteFramebuffer(target.framebuffer);
      gl.deleteTexture(target.texture);
    }
    this.targets = [];
    this.aux = null;
    this.canvas.width = width;
    this.canvas.height = height;
    this.width = width;
    this.height = height;
    for (let index = 0; index < 2; index++) {
      const target = this.makeTarget(width, height);
      if (target) this.targets.push(target);
    }
    this.aux = this.makeTarget(width, height);
  }

  private makeTarget(width: number, height: number): Target | null {
    const { gl } = this;
    const texture = gl.createTexture();
    const framebuffer = gl.createFramebuffer();
    if (!texture || !framebuffer) return null;
    gl.bindTexture(gl.TEXTURE_2D, texture);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, width, height, 0, gl.RGBA, gl.UNSIGNED_BYTE, null);
    // CLAMP_TO_EDGE, not REPEAT: a blur that wrapped would pull the right edge
    // of the picture into the left of it.
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
    gl.bindFramebuffer(gl.FRAMEBUFFER, framebuffer);
    gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT0, gl.TEXTURE_2D, texture, 0);
    gl.bindFramebuffer(gl.FRAMEBUFFER, null);
    return { framebuffer, texture };
  }

  private upload(source: CanvasImageSource): WebGLTexture | null {
    const { gl } = this;
    if (!this.sourceTexture) {
      this.sourceTexture = gl.createTexture();
      if (!this.sourceTexture) return null;
      gl.bindTexture(gl.TEXTURE_2D, this.sourceTexture);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
    }
    gl.bindTexture(gl.TEXTURE_2D, this.sourceTexture);
    // The Y flip is here rather than in the vertex stage so that every later
    // pass, which reads a framebuffer and not an image, needs no flag at all.
    gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, true);
    gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL, false);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, source as TexImageSource);
    gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, false);
    return this.sourceTexture;
  }

  private draw(
    compiled: Compiled,
    input: WebGLTexture,
    into: Target | null,
    step: ResolvedStep,
    seed: number,
    axis: number,
    aux: WebGLTexture | null
  ): void {
    const { gl } = this;
    gl.bindFramebuffer(gl.FRAMEBUFFER, into ? into.framebuffer : null);
    gl.viewport(0, 0, this.width, this.height);
    gl.useProgram(compiled.program);
    gl.bindBuffer(gl.ARRAY_BUFFER, this.quad);
    gl.enableVertexAttribArray(0);
    gl.vertexAttribPointer(0, 2, gl.FLOAT, false, 0, 0);

    gl.activeTexture(gl.TEXTURE0);
    gl.bindTexture(gl.TEXTURE_2D, input);
    gl.uniform1i(compiled.uniforms.get("uSource") ?? null, 0);
    if (aux) {
      gl.activeTexture(gl.TEXTURE1);
      gl.bindTexture(gl.TEXTURE_2D, aux);
      gl.uniform1i(compiled.uniforms.get("uAux") ?? null, 1);
      gl.activeTexture(gl.TEXTURE0);
    }
    gl.uniform2f(compiled.uniforms.get("uSize") ?? null, this.width, this.height);
    gl.uniform1f(compiled.uniforms.get("uSeed") ?? null, seed);
    gl.uniform1f(compiled.uniforms.get("uAxis") ?? null, axis);
    for (const [name, value] of Object.entries(step.numbers)) {
      const location = compiled.uniforms.get(name);
      if (location) gl.uniform1f(location, value);
    }
    for (const [name, value] of Object.entries(step.colours)) {
      const location = compiled.uniforms.get(name);
      if (location) gl.uniform3fv(location, hexToRgb(value));
    }
    gl.drawArrays(gl.TRIANGLES, 0, 3);
  }

  /** A blurred copy of `input` into `this.aux`, for the primitives that want one. */
  private blurInto(input: WebGLTexture, radius: number, seed: number): WebGLTexture | null {
    const blur = this.compile("blur");
    if (!blur || !this.aux || this.targets.length < 2) return null;
    const step: ResolvedStep = { primitive: "blur", passes: 2, numbers: { radius }, colours: {} };
    // Horizontal into the spare target, vertical into aux, so neither pass
    // reads the surface it is writing.
    this.draw(blur, input, this.targets[1], step, seed, 0, null);
    this.draw(blur, this.targets[1].texture, this.aux, step, seed, 1, null);
    return this.aux.texture;
  }

  /**
   * Run a chain over one image and return the canvas holding the result.
   *
   * `seed` should move with the frame, not with the wall clock: grain that
   * changed between a preview and an export would be two different videos, and
   * a re-export has to produce the file it produced yesterday.
   *
   * Returns null when there is nothing to do, so the caller draws its original
   * source and pays nothing.
   */
  apply(
    source: CanvasImageSource,
    width: number,
    height: number,
    chain: ResolvedStep[],
    seed: number
  ): HTMLCanvasElement | OffscreenCanvas | null {
    if (!chain.length || width < 1 || height < 1) return null;
    const { gl } = this;
    this.resize(Math.round(width), Math.round(height));
    if (this.targets.length < 2) return null;
    const uploaded = this.upload(source);
    if (!uploaded) return null;

    gl.disable(gl.BLEND);
    let input = uploaded;
    let index = 0;
    let ran = 0;

    for (const step of chain) {
      const compiled = this.compile(step.primitive);
      if (!compiled) continue;
      const into = this.targets[index % 2];

      if (SEPARABLE.has(step.primitive)) {
        const spare = this.targets[(index + 1) % 2];
        this.draw(compiled, input, spare, step, seed, 0, null);
        this.draw(compiled, spare.texture, into, step, seed, 1, null);
      } else if (NEEDS_BLURRED_COPY.has(step.primitive)) {
        // The aux blur reads `input`, so it has to happen before the pass that
        // writes over one of the ping-pong targets.
        const blurred = this.blurInto(input, step.numbers.radius ?? 16, seed);
        this.draw(compiled, input, into, step, seed, 0, blurred);
      } else {
        this.draw(compiled, input, into, step, seed, 0, null);
      }

      input = into.texture;
      index += 1;
      ran += 1;
    }

    if (!ran) return null;

    // One last pass to the drawing buffer, so the caller gets a canvas it can
    // hand straight to `drawImage` instead of a texture it would have to read.
    const copy = this.compile("exposure");
    if (!copy) return null;
    this.draw(copy, input, null, { primitive: "exposure", passes: 1, numbers: { stops: 0 }, colours: {} },
              seed, 0, null);
    return this.canvas;
  }

  /** Whether a primitive has a shader here at all. Used by the tests. */
  static knows(primitive: string): boolean {
    return primitive in PROGRAMS;
  }

  dispose(): void {
    const { gl } = this;
    for (const target of [...this.targets, this.aux]) {
      if (!target) continue;
      gl.deleteFramebuffer(target.framebuffer);
      gl.deleteTexture(target.texture);
    }
    for (const compiled of this.programs.values()) {
      if (compiled) gl.deleteProgram(compiled.program);
    }
    if (this.sourceTexture) gl.deleteTexture(this.sourceTexture);
    if (this.quad) gl.deleteBuffer(this.quad);
    this.targets = [];
    this.aux = null;
    this.programs.clear();
    this.sourceTexture = null;
  }
}
