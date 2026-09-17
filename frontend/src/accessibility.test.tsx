import { readFileSync } from "node:fs";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { Button, Modal, Progress, StatePanel, dialogTabTarget } from "./components";

describe("shared accessibility contract", () => {
  it("exposes progress values to assistive technology", () => {
    const html = renderToStaticMarkup(<Progress value={112} />);
    expect(html).toContain('role="progressbar"');
    expect(html).toContain('aria-valuenow="100"');
    expect(html).toContain('aria-valuemin="0"');
    expect(html).toContain('aria-valuemax="100"');
    expect(html).toContain('aria-valuetext="100 out of 100"');
  });

  it("marks busy buttons and loading states semantically", () => {
    const button = renderToStaticMarkup(<Button busy>Save</Button>);
    const loading = renderToStaticMarkup(
      <StatePanel tone="loading" title="Loading" description="Fetching records" />
    );
    expect(button).toContain('aria-busy="true"');
    expect(button).toContain("disabled");
    expect(loading).toContain('role="status"');
    expect(loading).toContain('aria-live="polite"');
  });

  it("gives dialogs stable accessible names and descriptions", () => {
    const html = renderToStaticMarkup(
      <Modal open title="Edit lead" description="Update the lead" onClose={() => undefined}>
        <button>Save</button>
      </Modal>
    );
    expect(html).toContain('role="dialog"');
    expect(html).toContain('aria-modal="true"');
    expect(html).toMatch(/aria-labelledby="[^"]+"/);
    expect(html).toMatch(/aria-describedby="[^"]+"/);
    expect(html).toContain('aria-label="Close dialog"');
  });

  it("wraps keyboard focus at both ends of a dialog", () => {
    expect(dialogTabTarget(0, 3, true)).toBe(2);
    expect(dialogTabTarget(2, 3, false)).toBe(0);
    expect(dialogTabTarget(1, 3, false)).toBeNull();
    expect(dialogTabTarget(-1, 3, false)).toBe(0);
    expect(dialogTabTarget(-1, 3, true)).toBe(2);
    expect(dialogTabTarget(-1, 0, false)).toBe(0);
  });

  it("keeps the app shell keyboard and screen-reader landmarks explicit", () => {
    const source = readFileSync(new URL("./App.tsx", import.meta.url), "utf8");
    expect(source).toContain('className="skip-link" href="#main-content"');
    expect(source).toContain('id="main-content"');
    expect(source).toContain('aria-current={page === item.page ? "page" : undefined}');
    expect(source).toContain('aria-live={toast.tone === "error" ? "assertive" : "polite"}');
    expect(source).toContain('role={toast.tone === "error" ? "alert" : "status"}');
  });

  it("does not let legacy outline removal hide keyboard focus", () => {
    const css = readFileSync(new URL("./accessibility.css", import.meta.url), "utf8");
    expect(css).toContain(".campaign-switcher select:focus-visible");
    expect(css).toContain(".search-box input:focus-visible");
    expect(css).toContain("outline: 2.5px solid var(--blue)");
    expect(css).toContain("prefers-reduced-motion: reduce");
  });
});
