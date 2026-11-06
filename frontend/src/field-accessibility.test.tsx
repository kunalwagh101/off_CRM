import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { Field } from "./components";

describe("stable field names during editing", () => {
  it("associates a populated textarea with its label independently of the text value", () => {
    const html = renderToStaticMarkup(<Field label="Procedure text" hint="Only selected procedures enter a run."><textarea defaultValue="Saved procedure body" /></Field>);
    const label = html.match(/<span id="([^"]+)">Procedure text<\/span>/)?.[1];
    expect(label).toBeTruthy();
    expect(html).toContain(`aria-labelledby="${label}"`);
    expect(html).toContain("aria-describedby=");
  });
  it("retains an explicit accessible name supplied by a caller", () => {
    const html = renderToStaticMarkup(<Field label="Contact"><input aria-label="Search contacts" defaultValue="Ana" /></Field>);
    expect(html).toContain('aria-label="Search contacts"');
    expect(html).not.toContain('aria-labelledby=');
  });
});
