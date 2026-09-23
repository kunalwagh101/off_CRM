import { renderToStaticMarkup } from "react-dom/server";
import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { Badge, Button, PageHeader, Progress, StatePanel, StatCard } from "./components";
import { LoginScreen, focusMainContent } from "./App";
import { AppContext } from "./context";
import { stageLabel } from "./hooks";
import SalesTracker, { formatSalesMoney } from "./pages/SalesTracker";
import VideoSection from "./pages/VideoSection";
import { formatTimecode, ticksPerFrame } from "./video/document";

describe("shared production UI", () => {
  it("renders accessible campaign summary components", () => {
    const html = renderToStaticMarkup(
      <main>
        <PageHeader title="Draft review" description="Human approval is required." />
        <StatCard label="Ready" value={4} accent="green" />
        <Badge tone="success">approved</Badge>
        <Progress value={92} />
      </main>
    );
    expect(html).toContain("Draft review");
    expect(html).toContain("Human approval is required.");
    expect(html).toContain("Quality score 92 out of 100");
    expect(html).toContain('role="progressbar"');
    expect(html).toContain('aria-valuenow="92"');
    expect(html).toContain("badge-success");
  });

  it("uses clear labels for every sequence stage", () => {
    expect(stageLabel("initial")).toBe("First touch");
    expect(stageLabel("followup1")).toBe("Follow-up 1");
    expect(stageLabel("followup2")).toBe("Follow-up 2");
    expect(stageLabel()).toBe("Not started");
  });

  it("renders the protected demo login without Gmail requirements", () => {
    const html = renderToStaticMarkup(<LoginScreen onLogin={() => undefined} />);
    expect(html).toContain("Sign in to the CRM");
    expect(html).toContain('autoComplete="username"');
    expect(html).toContain('autoComplete="current-password"');
    expect(html).toContain("Gmail is not required");
  });

  it("renders all sales tracker operating views from one lead-card source", () => {
    const html = renderToStaticMarkup(
      <AppContext.Provider value={{ campaigns: [], campaignId: "", activeCampaign: null, selectCampaign: () => undefined, createCampaign: async () => { throw new Error("Unexpected creation in a rendering test"); }, refreshCampaigns: () => undefined, notify: () => undefined }}>
        <SalesTracker />
      </AppContext.Provider>
    );
    expect(html).toContain("Sales tracker");
    expect(html).toContain("Kanban board");
    expect(html).toContain("Lead log");
    expect(html).toContain("Visibility dashboard");
    expect(html).toContain("Projection");
    expect(formatSalesMoney(1250, "USD")).toContain("1,250");
  });
});

describe("v0.12 additions", () => {
  const context = {
    campaigns: [],
    campaignId: "c1",
    activeCampaign: null,
    selectCampaign: () => undefined, createCampaign: async () => { throw new Error("Unexpected creation in a rendering test"); },
    refreshCampaigns: () => undefined,
    notify: () => undefined
  };

  it("discovery exposes engine choice cards and a worker control the user owns", async () => {
    const { default: Discovery } = await import("./pages/Discovery");
    const html = renderToStaticMarkup(
      <AppContext.Provider value={context}>
        <Discovery />
      </AppContext.Provider>
    );
    expect(html).toContain("Standard crawler");
    expect(html).toContain("Browser rendering");
    expect(html).toContain("Parallel workers");
    expect(html).toContain("never hit one site harder");
  });

  it("settings offers Notion connect with encrypted-token promise", async () => {
    // Settings reads the session token at render; the node test env has no
    // sessionStorage, so provide a minimal stub before importing.
    const memory = new Map<string, string>();
    (globalThis as Record<string, unknown>).sessionStorage = {
      getItem: (key: string) => memory.get(key) ?? null,
      setItem: (key: string, value: string) => void memory.set(key, value),
      removeItem: (key: string) => void memory.delete(key)
    };
    const { default: Settings } = await import("./pages/Settings");
    const html = renderToStaticMarkup(
      <AppContext.Provider value={context}>
        <Settings />
      </AppContext.Provider>
    );
    expect(html).toContain("Notion sync");
    expect(html).toContain("source of truth");
  });

  it("deliverability keeps bulk sending behind visible safety controls", async () => {
    const { default: Deliverability } = await import("./pages/Deliverability");
    const html = renderToStaticMarkup(
      <AppContext.Provider value={{ ...context, activeCampaign: { id: "c1", name: "Launch", kind: "email" } as never }}>
        <Deliverability />
      </AppContext.Provider>
    );
    expect(html).toContain("Email deliverability");
    expect(html).toContain("cannot guarantee inbox placement");
    expect(html).toContain("Global suppression");
    expect(html).toContain("Durable delivery jobs");
  });
});

describe("the video section on the command centre", () => {
  const context = (kind: string) => ({
    campaigns: [],
    campaignId: "c1",
    activeCampaign: { id: "c1", name: "Launch", kind } as never,
    selectCampaign: () => {}, createCampaign: async () => { throw new Error("Unexpected creation in a rendering test"); },
    refreshCampaigns: () => {},
    notify: () => {}
  });

  it("points an email campaign at where video actually lives", () => {
    const html = renderToStaticMarkup(
      <AppContext.Provider value={context("email") as never}>
        <VideoSection />
      </AppContext.Provider>
    );
    expect(html).toContain("Video lives in image campaigns");
    expect(html).toContain("Switch campaign");
    // No figures for a campaign that cannot hold a timeline.
    expect(html).not.toContain("timelines");
  });

  it("offers the editor and says captions are a draft", () => {
    const html = renderToStaticMarkup(
      <AppContext.Provider value={context("image") as never}>
        <VideoSection />
      </AppContext.Provider>
    );
    expect(html).toContain("Open editor");
    expect(html).toContain("timelines");
    expect(html).toContain("A transcript is a guess");
  });
});

describe("timeline units on the dashboard", () => {
  it("reads a length the way a person would", () => {
    expect(formatTimecode(0)).toBe("0:00.00");
    expect(formatTimecode(90_000 * 75)).toBe("1:15.00");
  });

  it("keeps every offered frame rate exact", () => {
    expect(ticksPerFrame("30")).toBe(3000);
    expect(ticksPerFrame("60")).toBe(1500);
  });
});

describe("keyboard and screen-reader contract", () => {
  function tsxFiles(directory: string): string[] {
    return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
      const path = join(directory, entry.name);
      if (entry.isDirectory()) return tsxFiles(path);
      return entry.name.endsWith(".tsx") ? [path] : [];
    });
  }

  // Each JSX opening tag, read to its real end. `[^>]*` stops at the `>` of
  // `onClick={() => ...}`, hiding every attribute after it (D-105).
  function openingTags(source: string, names: string): string[] {
    const tags: string[] = [];
    for (const match of source.matchAll(new RegExp(`<(?:${names})\\b`, "g"))) {
      let depth = 0;
      for (let end = match.index + match[0].length; end < source.length; end++) {
        const char = source[end];
        if (char === "{") depth++;
        else if (char === "}") depth--;
        else if (char === ">" && depth === 0) {
          tags.push(source.slice(match.index, end + 1));
          break;
        }
      }
    }
    return tags;
  }

  it("shared busy/loading states expose assistive semantics", () => {
    const button = renderToStaticMarkup(<Button busy>Save</Button>);
    const loading = renderToStaticMarkup(
      <StatePanel tone="loading" title="Loading" description="Please wait." />
    );
    expect(button).toContain('aria-busy="true"');
    expect(button).toContain("disabled");
    expect(loading).toContain('role="status"');
    expect(loading).toContain('aria-live="polite"');
    expect(loading).toContain('aria-busy="true"');
  });

  it("page navigation moves programmatic focus to main content", () => {
    let focused = false;
    const previousWindow = globalThis.window;
    const previousDocument = globalThis.document;
    (globalThis as Record<string, unknown>).window = {
      requestAnimationFrame: (callback: () => void) => {
        callback();
        return 1;
      }
    };
    (globalThis as Record<string, unknown>).document = {
      getElementById: (id: string) =>
        id === "main-content" ? { focus: () => { focused = true; } } : null
    };
    try {
      focusMainContent();
      expect(focused).toBe(true);
    } finally {
      (globalThis as Record<string, unknown>).window = previousWindow;
      (globalThis as Record<string, unknown>).document = previousDocument;
    }
  });

  it("uses native interactive elements instead of click-only divs/spans", () => {
    const offenders: string[] = [];
    const missingAlt: string[] = [];
    for (const path of tsxFiles(join(process.cwd(), "src"))) {
      if (path.endsWith("components.test.tsx")) continue;
      const source = readFileSync(path, "utf-8");
      for (const tag of openingTags(source, "div|span|li|tr|td|article|section")) {
        // A backdrop may be a mouse convenience only when it is hidden from
        // assistive technology; the drawer it closes has its own Escape and
        // Close button. The Python contract grants the same one exemption.
        if (/\bonClick\s*=/.test(tag) && !tag.includes('aria-hidden="true"')) {
          offenders.push(path);
        }
      }
      if (/\brole\s*=\s*["']button["']/.test(source)) {
        offenders.push(path + " (role=button)");
      }
      for (const tag of openingTags(source, "img")) {
        if (!/\balt\s*=/.test(tag)) missingAlt.push(path);
      }
    }
    expect(offenders).toEqual([]);
    expect(missingAlt).toEqual([]);
  });

  it("keeps a visible global focus indicator and keyboard-visible hover content", () => {
    const css = readFileSync(join(process.cwd(), "src", "styles.css"), "utf-8");
    expect(css).toContain(":focus-visible");
    expect(css).toContain("outline: 3px solid");
    expect(css).toContain(".catalog-card-wrapper:focus-within .catalog-tooltip");
  });
});

describe("the GTM engine", () => {
  const context = {
    campaigns: [],
    campaignId: "",
    activeCampaign: null,
    selectCampaign: () => undefined, createCampaign: async () => { throw new Error("Unexpected creation in a rendering test"); },
    refreshCampaigns: () => undefined,
    notify: () => undefined
  };

  it("the product screen asks for the truth once, and for the claims never to make", async () => {
    const { default: Product } = await import("./pages/Product");
    const html = renderToStaticMarkup(
      <AppContext.Provider value={context}>
        <Product />
      </AppContext.Provider>
    );
    expect(html).toContain("Your product, described once");
    for (const label of ["Name", "One-liner", "Who it is for", "The problem it solves", "The offer", "Never claim"]) {
      expect(html).toContain(label);
    }
    // The address rule is explained where the owner types, not three screens later.
    expect(html).toContain("may be sent to a model");
    // Linking campaigns waits for a saved product rather than offering a dead button.
    expect(html).toContain("Campaigns that speak for this product");
    expect(html).toContain("Save the product first");
  });

  it("the strategy screen shows the goal form and what is connected before any plan", async () => {
    const { default: Strategy } = await import("./pages/Strategy");
    const html = renderToStaticMarkup(
      <AppContext.Provider value={context}>
        <Strategy />
      </AppContext.Provider>
    );
    expect(html).toContain("Plan the go-to-market");
    expect(html).toContain("What is connected");
    for (const label of ["Product", "Goal", "Target", "Days", "New contacts", "Channels"]) {
      expect(html).toContain(label);
    }
    expect(html).toContain("Draft a plan");
    // The honest promise, where the owner decides.
    expect(html).toContain("nothing sends");
  });

  it("next steps after Apply are links to screens that exist", async () => {
    const { NextSteps } = await import("./pages/Strategy");
    const html = renderToStaticMarkup(
      <NextSteps
        steps={[
          { page: "contacts", label: "Add contacts to the email campaign", why: "The email campaign starts empty." },
          { page: "campaigns", label: "Resume each campaign when you are ready", why: "Apply left every campaign paused." }
        ]}
        notes={["The email campaign was set to 500."]}
      />
    );
    expect(html).toContain('href="#contacts"');
    expect(html).toContain('href="#campaigns"');
    expect(html).toContain("Resume each campaign when you are ready");
    expect(html).toContain("set to 500");
  });

  it("a review shows what is wrong first, and never links a remedy to a screen that cannot do it", async () => {
    const { ReviewView } = await import("./pages/Strategy");
    const html = renderToStaticMarkup(
      <ReviewView
        review={{
          id: "r1", plan_id: "p1", summary: "", source: "rules", provider_id: "", model_id: "", policy: "",
          created_at: "2026-09-22T12:00:00+00:00", measurements: [],
          findings: [
            { channel: "email", campaign_id: "c1", code: "delivery_unhealthy", sentence: "6.0% of 300 accepted emails hard-bounced.", permitted: ["fix_list_quality"], numbers: {} },
            { channel: "distribution", campaign_id: "c2", code: "nothing_published", sentence: "Nothing has been published from this campaign yet.", permitted: ["set_up_posting"], numbers: {} }
          ],
          remedies: [
            { channel: "email", campaign_id: "c1", finding: "delivery_unhealthy", action: "fix_list_quality", why: "6.0% bounced.", proposal: "", page: "contacts", label: "Remove the addresses that bounced." },
            { channel: "distribution", campaign_id: "c2", finding: "nothing_published", action: "set_up_posting", why: "Nothing posted.", proposal: "", page: "", label: "Set up posting." }
          ],
          notes: ["No model could review this plan. These are the rules' remedies."]
        }}
      />
    );
    expect(html).toContain("delivery unhealthy");
    expect(html).toContain("6.0% of 300 accepted emails hard-bounced.");
    expect(html).toContain('href="#contacts"');
    // One remedy has a screen and one does not: exactly one "Open" link.
    expect(html.match(/>Open</g)?.length).toBe(1);
    expect(html).toContain("Rules-based remedies");
    expect(html).toContain("rules&#x27; remedies");
  });
});
