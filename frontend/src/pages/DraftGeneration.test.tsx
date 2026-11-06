import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { DraftGenerationMode, generationOutcome } from "./DraftGeneration";

describe("draft generation routing and outcomes", () => {
  it("explains how to connect AI while keeping local templates available", () => {
    const html = renderToStaticMarkup(<DraftGenerationMode mode="local" onChange={() => {}} connected={0} />);
    expect(html).toContain("Local templates only");
    expect(html).toContain('href="#connectors"');
    expect(html).not.toContain("fallback chain");
  });
  it("shows policy boundaries for connected providers", () => {
    const html = renderToStaticMarkup(<DraftGenerationMode mode="connectors" onChange={() => {}} connected={2} />);
    expect(html).toContain("Connectors (2 connected)");
    expect(html).toContain("data policy");
    expect(html).not.toContain("Parallel first-success");
  });
  it("never presents a failed batch as success", () => {
    expect(generationOutcome({ generated: 0, blocked: 0, failures: [{ error: "Reference: E-123" }] })).toEqual({
      tone: "error", message: "0 drafts generated, 0 blocked by audit, 1 failed. Reference: E-123"
    });
    expect(generationOutcome({ generated: 2, blocked: 0, failures: [{}] }).tone).toBe("error");
    expect(generationOutcome({ generated: 2, blocked: 1, failures: [] }).tone).toBe("info");
    expect(generationOutcome({ generated: 2, blocked: 0, failures: [] }).tone).toBe("success");
  });
});
