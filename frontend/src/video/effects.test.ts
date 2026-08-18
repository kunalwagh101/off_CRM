/**
 * The chain a clip turns into, before any of it reaches a GPU.
 *
 * The half that can be tested without one: which passes get built, in what
 * order, and whether the sliders that the document has always declared now
 * produce an operation instead of nothing.
 */

import { describe, expect, it } from "vitest";
import { chainFor, cssFallback, fallbackLosses, passCost,
         propertyFrame, propertyGrade } from "./effects";
import { PROPERTY_SPEC } from "./document";
import { hexToRgb } from "./shaders/pipeline";
import { PROGRAMS } from "./shaders/glsl";

const NONE: Record<string, number> = {};

describe("the property chain", () => {
  it("builds nothing at all when every slider is where it started", () => {
    expect(propertyGrade(NONE)).toEqual([]);
    expect(propertyFrame(NONE, {})).toEqual([]);
  });

  it("folds brightness and exposure into one pass, because both are light", () => {
    const chain = propertyGrade({ brightness: 1, exposure: 1 });
    expect(chain).toHaveLength(1);
    expect(chain[0].primitive).toBe("exposure");
    // A doubling and a stop is four times the light: 2^(1 + log2(2)).
    expect(2 ** chain[0].numbers.stops).toBeCloseTo(4, 6);
  });

  it("matches what the CSS painter did for the light it could express", () => {
    for (const [brightness, exposure] of [[0.5, 0], [0, 1], [-0.4, -0.5], [0.2, 0.3]]) {
      const chain = propertyGrade({ brightness, exposure });
      const css = (1 + brightness) * 2 ** exposure;
      expect(2 ** chain[0].numbers.stops).toBeCloseTo(css, 6);
    }
  });

  it("draws the seven properties the document declared and nothing ever drew", () => {
    // The bug this build fixes. `PROPERTY_SPEC` has had these since the
    // timeline was written; the 2D painter could express none of them.
    const names = ["tint", "sharpen", "grain", "vignette", "corner_radius",
                   "border_width", "shadow"];
    for (const name of names) {
      expect(PROPERTY_SPEC[name], `${name} is declared`).toBeTruthy();
    }
    const properties = { tint: 0.5, sharpen: 1, grain: 0.3, vignette: 0.4,
                         corner_radius: 20, border_width: 4, shadow: 12 };
    const built = [
      ...propertyGrade(properties).map((step) => step.primitive),
      ...propertyFrame(properties, {}).map((step) => step.primitive)
    ];
    expect(built).toEqual([
      "tint", "sharpen", "grain", "vignette", "rounded_frame", "drop_shadow"
    ]);
  });

  it("puts framing after the grade, because a grain over a rounded corner grains the hole", () => {
    const chain = chainFor("clip-1", { grain: 0.2, corner_radius: 30 }, {}, undefined);
    expect(chain.map((step) => step.primitive)).toEqual(["grain", "rounded_frame"]);
  });

  it("puts the chosen looks between the sliders and the framing", () => {
    const table = { "clip-1": [{ primitive: "sepia", passes: 1,
                                 numbers: { amount: 1 }, colours: {} }] };
    const chain = chainFor("clip-1", { contrast: 0.2, vignette: 0.3 }, {}, table);
    expect(chain.map((step) => step.primitive)).toEqual(["contrast", "sepia", "vignette"]);
  });

  it("adds a transition's blur to the clip's own rather than replacing it", () => {
    const chain = chainFor("clip-1", { blur: 4 }, {}, undefined, 12);
    const blur = chain.find((step) => step.primitive === "blur");
    expect(blur?.numbers.radius).toBe(16);
  });

  it("counts a separable blur as two draws and a bloom as three", () => {
    expect(passCost(propertyGrade({ blur: 10 }))).toBe(2);
    expect(passCost(propertyFrame({ shadow: 10 }, {}))).toBe(3);
  });

  it("only builds a chain for a clip the table actually names", () => {
    const table = { "clip-2": [{ primitive: "invert", passes: 1,
                                 numbers: { amount: 1 }, colours: {} }] };
    expect(chainFor("clip-1", NONE, {}, table)).toEqual([]);
  });
});

describe("the fallback for a machine with no WebGL2", () => {
  it("still expresses the four things a canvas filter can express", () => {
    const css = cssFallback({ brightness: 0.5, contrast: 0.2, saturation: -0.3, blur: 4 });
    expect(css).toContain("brightness(1.5000)");
    expect(css).toContain("contrast(1.2000)");
    expect(css).toContain("saturate(0.7000)");
    expect(css).toContain("blur(4.00px)");
  });

  it("is `none` rather than an empty string when there is nothing to say", () => {
    expect(cssFallback(NONE)).toBe("none");
  });

  it("says what it dropped instead of pretending the picture is right", () => {
    const lost = fallbackLosses({ vignette: 0.4, grain: 0.2, contrast: 0.3 }, []);
    expect(lost).toEqual(["grain", "vignette"]);
  });

  it("counts a chosen look as a loss too", () => {
    const chain = [{ primitive: "sepia", passes: 1, numbers: {}, colours: {} }];
    expect(fallbackLosses(NONE, chain)).toEqual(["effects"]);
  });
});

describe("colours on the way to a uniform", () => {
  it("reads a full hex", () => {
    expect(hexToRgb("#ff8000")).toEqual([1, 128 / 255, 0]);
  });

  it("reads a short one, because a document may carry either", () => {
    expect(hexToRgb("#0af")).toEqual([0, 170 / 255, 1]);
  });

  it("does not throw on nonsense — the server already refused it", () => {
    expect(() => hexToRgb("")).not.toThrow();
  });
});

describe("the shader table", () => {
  it("declares every program with a version directive and one output", () => {
    for (const [name, program] of Object.entries(PROGRAMS)) {
      expect(program.fragment.startsWith("#version 300 es"), name).toBe(true);
      expect(program.fragment, name).toContain("out vec4 fragColour;");
      expect(program.fragment, name).toContain("void main()");
    }
  });

  it("declares a uniform for every parameter it says it takes", () => {
    for (const [name, program] of Object.entries(PROGRAMS)) {
      for (const number of program.numbers) {
        expect(program.fragment, `${name}.${number}`).toContain(`uniform float ${number};`);
      }
      for (const colour of program.colours) {
        expect(program.fragment, `${name}.${colour}`).toContain(`uniform vec3 ${colour};`);
      }
    }
  });

  it("writes fragColour on every path out of main", () => {
    for (const [name, program] of Object.entries(PROGRAMS)) {
      const body = program.fragment.split("void main()")[1] ?? "";
      const returns = (body.match(/\breturn;/g) ?? []).length;
      const writes = (body.match(/fragColour\s*=/g) ?? []).length;
      expect(writes, `${name} writes an output`).toBeGreaterThan(returns);
    }
  });
});
