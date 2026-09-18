import { readdirSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { describe, expect, it } from "vitest";

const SRC = dirname(fileURLToPath(import.meta.url));

function reactSources(dir: string): string[] {
  const found: string[] = [];
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) {
      found.push(...reactSources(path));
      continue;
    }
    if (entry.isFile() && entry.name.endsWith(".tsx") && !entry.name.endsWith(".test.tsx")) {
      found.push(path);
    }
  }
  return found.sort();
}

function relative(path: string): string {
  return path.slice(SRC.length + 1).replaceAll("\\", "/");
}

describe("repository-wide accessibility source gate", () => {
  const files = reactSources(SRC);

  it("audits every shipped React source file rather than a hand-picked screen list", () => {
    expect(files.length).toBeGreaterThan(20);
    expect(files.some((path) => path.endsWith("App.tsx"))).toBe(true);
    expect(files.some((path) => path.endsWith("pages/AI.tsx"))).toBe(true);
    expect(files.some((path) => path.endsWith("pages/SalesTracker.tsx"))).toBe(true);
    expect(files.some((path) => path.endsWith("pages/VideoEditor.tsx"))).toBe(true);
  });

  it("does not make non-native elements the only click target", () => {
    const violations: string[] = [];
    const pattern = /<(div|span|li|tr|td|section|article)\b[^>]*\bonClick\s*=.*?>/gs;

    for (const path of files) {
      const source = readFileSync(path, "utf8");
      for (const match of source.matchAll(pattern)) {
        const openingTag = match[0];
        // A backdrop may be pointer-dismissable only when it is explicitly
        // hidden from assistive technology and the real dialog/drawer exposes
        // a keyboard close path of its own.
        if (/aria-hidden\s*=\s*["']true["']/.test(openingTag)) continue;
        violations.push(`${relative(path)}: ${openingTag.replace(/\s+/g, " ").slice(0, 180)}`);
      }
    }

    expect(violations).toEqual([]);
  });

  it("requires custom tab stops to expose a semantic role and keyboard handler", () => {
    const violations: string[] = [];
    const pattern = /<(div|span|li|tr|td|section|article)\b[^>]*\btabIndex=\{?0\}?[^>]*>/gs;

    for (const path of files) {
      const source = readFileSync(path, "utf8");
      for (const match of source.matchAll(pattern)) {
        const openingTag = match[0];
        if (!/\brole=/.test(openingTag) || !/\bonKeyDown=/.test(openingTag)) {
          violations.push(`${relative(path)}: ${openingTag.replace(/\s+/g, " ").slice(0, 180)}`);
        }
      }
    }

    expect(violations).toEqual([]);
  });

  it("requires every image to declare alternative-text intent", () => {
    const violations: string[] = [];
    const pattern = /<img\b[^>]*>/gs;

    for (const path of files) {
      const source = readFileSync(path, "utf8");
      for (const match of source.matchAll(pattern)) {
        if (!/\balt\s*=/.test(match[0])) {
          violations.push(`${relative(path)}: ${match[0].replace(/\s+/g, " ").slice(0, 180)}`);
        }
      }
    }

    expect(violations).toEqual([]);
  });

  it("requires literal icon-only buttons to have an accessible name", () => {
    const violations: string[] = [];
    const pattern = /<button\b([^>]*)>([\s\S]*?)<\/button>/g;

    for (const path of files) {
      const source = readFileSync(path, "utf8");
      for (const match of source.matchAll(pattern)) {
        const attrs = match[1] ?? "";
        const body = match[2] ?? "";
        if (/aria-label\s*=/.test(attrs) || body.includes("{")) continue;

        const text = body.replace(/<[^>]+>/g, "").replace(/\s+/g, " ").trim();
        if (text && !/[A-Za-z0-9]/.test(text) && text.length <= 8) {
          violations.push(`${relative(path)}: ${match[0].replace(/\s+/g, " ").slice(0, 180)}`);
        }
      }
    }

    expect(violations).toEqual([]);
  });

  it("never marks a natively focusable control aria-hidden", () => {
    const violations: string[] = [];
    const pattern = /<(a|button|input|select|textarea)\b[^>]*aria-hidden\s*=\s*["']true["'][^>]*>/gs;

    for (const path of files) {
      const source = readFileSync(path, "utf8");
      for (const match of source.matchAll(pattern)) {
        violations.push(`${relative(path)}: ${match[0].replace(/\s+/g, " ").slice(0, 180)}`);
      }
    }

    expect(violations).toEqual([]);
  });
});
