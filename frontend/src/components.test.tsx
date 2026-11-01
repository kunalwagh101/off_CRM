import { renderToStaticMarkup } from "react-dom/server";
import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { Badge, Button, PageHeader, Progress, StatePanel, StatCard, StorageNote, storageWording } from "./components";
import { LoginScreen, focusMainContent, skipToMainContent } from "./App";
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

  it("shows only explicitly supplied public demo credentials", () => {
    const publicHtml = renderToStaticMarkup(<LoginScreen onLogin={() => undefined} publicDemo={{ username: "visitor", password: "Public-Demo-2026!", read_only: true }} />);
    expect(publicHtml).toContain("Demo login details");
    expect(publicHtml).toContain("Public-Demo-2026!");
    expect(publicHtml).toContain('value="visitor"');
    expect(publicHtml).toContain("AI enabled");
    const privateHtml = renderToStaticMarkup(<LoginScreen onLogin={() => undefined} />);
    expect(privateHtml).not.toContain("Demo login details");
    expect(privateHtml).not.toContain("Public-Demo-2026!");
  });

  it("public visitor connectors expose AI setup without a dead Gmail control", async () => {
    const { default: Connectors } = await import("./pages/Connectors");
    const html = renderToStaticMarkup(
      <AppContext.Provider value={{ publicDemo: true, campaigns: [], campaignId: "", activeCampaign: null, selectCampaign: () => undefined, createCampaign: async () => { throw new Error("Unexpected creation"); }, refreshCampaigns: () => undefined, notify: () => undefined }}>
        <Connectors />
      </AppContext.Provider>
    );
    expect(html).toContain("Use your own provider key");
    expect(html).toContain("AI providers");
    expect(html).not.toContain("Gmail");
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

  it("page navigation focuses main without scrolling, then opens the screen at its top", () => {
    const calls: unknown[] = [];
    const previousWindow = globalThis.window;
    const previousDocument = globalThis.document;
    (globalThis as Record<string, unknown>).window = {
      requestAnimationFrame: (callback: () => void) => {
        callback();
        return 1;
      },
      scrollTo: (options: ScrollToOptions) => calls.push(["scroll", options])
    };
    (globalThis as Record<string, unknown>).document = {
      getElementById: (id: string) =>
        id === "main-content" ? { focus: (options: FocusOptions) => calls.push(["focus", options]) } : null
    };
    try {
      focusMainContent();
      expect(calls).toEqual([
        ["focus", { preventScroll: true }],
        ["scroll", { top: 0, behavior: "instant" }]
      ]);
    } finally {
      (globalThis as Record<string, unknown>).window = previousWindow;
      (globalThis as Record<string, unknown>).document = previousDocument;
    }
  });

  it.each(["#settings", "#contacts"])(
    "skip to content keeps route %s on keyboard/pointer activation",
    (route) => {
      const calls: string[] = [];
      const oldWindow = globalThis.window;
      const oldDocument = globalThis.document;
      (globalThis as Record<string, unknown>).window = {
        location: { hash: route },
        requestAnimationFrame: (callback: () => void) => { callback(); return 1; },
        scrollTo: () => calls.push("scroll")
      };
      (globalThis as Record<string, unknown>).document = {
        getElementById: (id: string) =>
          id === "main-content" ? { focus: () => calls.push("focus") } : null
      };
      try {
        skipToMainContent({ preventDefault: () => calls.push("prevent") });
        expect(calls).toEqual(["prevent", "focus", "scroll"]);
        expect(window.location.hash).toBe(route);
      } finally {
        (globalThis as Record<string, unknown>).window = oldWindow;
        (globalThis as Record<string, unknown>).document = oldDocument;
      }
    }
  );

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

describe("screens before the campaign list has loaded (D-130)", () => {
  // A static render is the first frame: the campaign list has not answered.
  // When it fails, the app stays in exactly this state until a retry works —
  // so what shows here is what an owner has while /campaigns returns 500.
  async function firstFrame(page: string) {
    const memory = new Map<string, string>();
    const storage = {
      getItem: (key: string) => memory.get(key) ?? null,
      setItem: (key: string, value: string) => void memory.set(key, value),
      removeItem: (key: string) => void memory.delete(key)
    };
    const stubs = {
      sessionStorage: storage,
      localStorage: storage,
      window: { location: { hash: `#${page}` }, addEventListener: () => undefined, removeEventListener: () => undefined }
    };
    const globals = globalThis as Record<string, unknown>;
    const saved = Object.fromEntries(Object.keys(stubs).map((key) => [key, globals[key]]));
    Object.assign(globals, stubs);
    try {
      const { AuthenticatedApp } = await import("./App");
      const auth = { configured: true, authenticated: true, username: "owner", expires_at: null };
      return renderToStaticMarkup(<AuthenticatedApp auth={auth} onLogout={() => undefined} />);
    } finally {
      Object.assign(globals, saved);
    }
  }

  it("keeps Settings, where backup and restore live, reachable", async () => {
    const html = await firstFrame("settings");
    expect(html).toContain("Encrypted backup");
    expect(html).not.toContain('aria-label="Loading campaigns"');
  });

  it("holds campaign screens until the list they read has loaded", async () => {
    const html = await firstFrame("contacts");
    expect(html).toContain('aria-label="Loading campaigns"');
    expect(html).not.toContain("<h1>Contacts</h1>");
  });
});

describe("limit presets on the connect form (S-06.02.32)", () => {
  it("offers the provider's own limit or no cap, three sizes, and a typed number", async () => {
    const { CALL_CAP_PRESETS, SPEND_CAP_PRESETS } = await import("./pages/CapPicker");
    expect(CALL_CAP_PRESETS.map((preset) => preset.value)).toEqual([0, 50, 200, 1000]);
    expect(SPEND_CAP_PRESETS.map((preset) => preset.value)).toEqual([0, 1, 5, 20]);
  });

  it("shows a saved cap as its preset, and any other number as custom", async () => {
    const { CALL_CAP_PRESETS, SPEND_CAP_PRESETS, presetChoice } = await import("./pages/CapPicker");
    expect(presetChoice(200, CALL_CAP_PRESETS)).toBe("200");
    expect(presetChoice(0, SPEND_CAP_PRESETS)).toBe("0");
    expect(presetChoice(37, CALL_CAP_PRESETS)).toBe("custom");
  });

  it("posts a preset's number with no number box shown", async () => {
    const { default: CapPicker, CALL_CAP_PRESETS } = await import("./pages/CapPicker");
    const html = renderToStaticMarkup(
      <CapPicker name="requests_per_day" label="Daily call cap" presets={CALL_CAP_PRESETS} defaultValue={200} />
    );
    expect(html).toContain('name="requests_per_day"');
    expect(html).toContain('value="200"');
    expect(html).toContain("Provider&#x27;s own limit");
    expect(html).not.toContain('type="number"');
  });

  it("shows a typed cap in its own labelled number box", async () => {
    const { default: CapPicker, CALL_CAP_PRESETS } = await import("./pages/CapPicker");
    const html = renderToStaticMarkup(
      <CapPicker name="requests_per_day" label="Daily call cap" presets={CALL_CAP_PRESETS} defaultValue={37} />
    );
    expect(html).toContain('type="number"');
    expect(html).toContain('aria-label="Custom daily call cap"');
    expect(html).toContain('value="37"');
  });
});

describe("trust per provider and per model (S-06.02.33)", () => {
  it("offers every tier for a provider and marks its default", async () => {
    const { ProviderTrustSelect } = await import("./pages/TrustSelect");
    const html = renderToStaticMarkup(
      <ProviderTrustSelect name="NVIDIA NIM" value="B" defaultTier="B" onChange={() => undefined} />
    );
    expect(html).toContain('aria-label="Trust for NVIDIA NIM"');
    for (const word of ["Highest trust", "Default trust (default)", "Restricted", "Blocked"]) {
      expect(html).toContain(word);
    }
  });

  it("sends the provider back to its default when its default tier is chosen", async () => {
    const { providerTierToSend } = await import("./pages/TrustSelect");
    expect(providerTierToSend("B", "B")).toBe("");
    expect(providerTierToSend("C", "B")).toBe("C");
    expect(providerTierToSend("A", "B")).toBe("A");
  });

  it("lets a model follow its provider or take its own tier", async () => {
    const { ModelTrustSelect } = await import("./pages/TrustSelect");
    const html = renderToStaticMarkup(
      <ModelTrustSelect modelId="deepseek-ai/deepseek-r1" providerName="NVIDIA NIM" value="" onChange={() => undefined} />
    );
    // The provider is in the name: gpt-4o is offered by two providers.
    expect(html).toContain('aria-label="Trust for deepseek-ai/deepseek-r1 on NVIDIA NIM"');
    expect(html).toContain("Same as provider");
    expect(html).toContain("Highest trust");
  });
});

describe("a custom cap must be a number (review of S-06.02.32)", () => {
  it("reads presets and typed numbers, and refuses a blank or a negative", async () => {
    const { readCap } = await import("./pages/CapPicker");
    expect(readCap("0")).toBe(0);
    expect(readCap("200")).toBe(200);
    expect(readCap("2.5")).toBe(2.5);
    // A blank box was Number("") === 0, which saved "no cap".
    expect(readCap("")).toBeNull();
    expect(readCap("   ")).toBeNull();
    expect(readCap("abc")).toBeNull();
    expect(readCap("-5")).toBeNull();
    expect(readCap(null)).toBeNull();
  });
});

describe("the full-data grant (reviews of S-06.02.33)", () => {
  const base = {
    name: "NVIDIA NIM",
    connected: true,
    grant_offer: true,
    grant_state: "",
    override: null
  };
  const granted = { allow_above_ceiling: true, reason: "Signed a DPA" };

  it("is offered where the server says it would change what is sent, and nowhere else", async () => {
    const { canGrantFullData } = await import("./pages/TrustSelect");
    expect(canGrantFullData(base)).toBe(true);
    expect(canGrantFullData({ ...base, connected: false })).toBe(false);
    // Blocked, lowered, tier A, or no switched-on model at the default (D-179).
    expect(canGrantFullData({ ...base, grant_offer: false })).toBe(false);
    expect(canGrantFullData({ ...base, override: granted })).toBe(false);
  });

  it("says why a grant is or is not in force, and never claims one that is not there", async () => {
    const { grantLine } = await import("./pages/TrustSelect");
    expect(grantLine(base)).toBe("");
    expect(grantLine({ ...base, override: granted, grant_state: "active" })).toBe(
      "Full data granted by you: Signed a DPA. Not for models trusted less than NVIDIA NIM's default."
    );
    expect(grantLine({ ...base, override: granted, grant_state: "provider_lowered" })).toBe(
      "Full data paused while you trust NVIDIA NIM less than its default: Signed a DPA."
    );
    // At its default and blocked: "less than its default" was false (third review).
    expect(grantLine({ ...base, override: granted, grant_state: "provider_blocked" })).toBe(
      "Full data paused: NVIDIA NIM is blocked, so it receives nothing. Signed a DPA."
    );
    expect(grantLine({ ...base, override: granted, grant_state: "no_model" })).toBe(
      "Full data paused: no model you switched on is trusted at NVIDIA NIM's default. Signed a DPA."
    );
    // A grant made for less than full says so; only the screen's grants are full.
    expect(grantLine({ ...base, override: { ...granted, data_policy: "minimal" }, grant_state: "active" })).toBe(
      "Minimal data granted by you: Signed a DPA. Not for models trusted less than NVIDIA NIM's default."
    );
  });
});

describe("what the card says is sent (D-179)", () => {
  it("says Nothing for a blocked provider, and Up to when its models differ", async () => {
    const { sendsWord } = await import("./pages/Connectors");
    expect(sendsWord({ receives_nothing: false, sends: "standard", sends_varies: false, data_policy: "full" })).toBe("Standard");
    expect(sendsWord({ receives_nothing: false, sends: "full", sends_varies: true, data_policy: "standard" })).toBe("Up to Full access");
    expect(sendsWord({ receives_nothing: true, sends: "strict", sends_varies: false, data_policy: "strict" })).toBe("Nothing");
    // Every switched-on model blocked: the router sends it nothing (D-188).
    expect(sendsWord({ receives_nothing: false, sends_nothing: true, sends: "", data_policy: "standard" })).toBe("Nothing");
  });

  it("offers only the levels the provider's standing trust allows, and shows the saved one within them (D-184)", async () => {
    const { levelsUpTo, formLevel } = await import("./pages/Connectors");
    expect([...levelsUpTo("standard")]).toEqual(["strict", "pseudonymous", "minimal", "standard"]);
    expect([...levelsUpTo("full")]).toEqual(["strict", "pseudonymous", "minimal", "standard", "full"]);
    expect(formLevel("full", "standard")).toBe("standard");
    expect(formLevel("minimal", "standard")).toBe("minimal");
  });
});

describe("provider profiles saved before ownership was recorded (D-177)", () => {
  const old = {
    id: "owner-old",
    owner: "default",
    name: "Primary OpenAI",
    provider_type: "openai_compatible" as const,
    model: "gpt-4o-mini",
    base_url: "https://api.openai.com/v1",
    has_stored_secret: true,
    owner_confirmed: false
  };

  it("lists each one with where it sends, and confirms it only with the key it holds", async () => {
    const { default: LegacyProfiles } = await import("./pages/LegacyProfiles");
    const html = renderToStaticMarkup(
      <LegacyProfiles items={[old, { ...old, id: "mine", owner_confirmed: true }]} busy="" onConfirm={() => undefined} onRemove={() => undefined} />
    );
    expect(html).toContain("Primary OpenAI");
    expect(html).toContain("https://api.openai.com/v1");
    expect(html).toContain("Saved for: default");
    // A label proves nothing: anyone's saves were labelled "default" (D-185).
    expect(html).toContain('aria-label="API key of Primary OpenAI"');
    expect(html).toContain('type="password"');
    expect(html).toContain('aria-label="Confirm Primary OpenAI as yours"');
    expect(html).toContain('aria-label="Remove Primary OpenAI"');
    expect(html.match(/Confirm Primary OpenAI/g)?.length).toBe(1);
  });

  it("offers only Remove for a profile with no key stored, and says why truly (D-187, D-191)", async () => {
    const { default: LegacyProfiles } = await import("./pages/LegacyProfiles");
    const html = renderToStaticMarkup(
      <LegacyProfiles items={[{ ...old, has_stored_secret: false }]} busy="" onConfirm={() => undefined} onRemove={() => undefined} />
    );
    expect(html).not.toContain("Confirm Primary OpenAI");
    expect(html).toContain("No key is stored in it, so nothing proves it is yours.");
    expect(html).toContain('aria-label="Remove Primary OpenAI"');
  });

  it("says where Confirm puts each profile before it is pressed (D-190)", async () => {
    const { default: LegacyProfiles } = await import("./pages/LegacyProfiles");
    const html = renderToStaticMarkup(
      <LegacyProfiles
        items={[
          { ...old, confirm_to: "local", confirm_options: ["local"] },
          { ...old, id: "b", name: "Beta profile", owner: "beta", confirm_to: "beta", confirm_options: ["beta", "local"] }
        ]}
        busy=""
        onConfirm={() => undefined}
        onRemove={() => undefined}
      />
    );
    expect(html).toContain("Confirm as yours");
    expect(html).toContain("Confirm for workspace beta");
    // Screen readers hear the destination too: the label overrides the text (D-195).
    expect(html).toContain('aria-label="Confirm Primary OpenAI as yours"');
    expect(html).toContain('aria-label="Confirm Beta profile for workspace beta"');
    // The key proves it yours, so "as yours" is always a choice (D-194).
    expect(html).toContain('aria-label="Confirm Beta profile as yours"');
    expect(html.match(/Confirm Primary OpenAI/g)?.length).toBe(1);
  });

  it("sends where the button pressed says, in any browser, and Enter never chooses between two (D-197)", async () => {
    const { default: LegacyProfiles, enterDestination } = await import("./pages/LegacyProfiles");
    const html = renderToStaticMarkup(
      <LegacyProfiles
        items={[{ ...old, id: "b", name: "Beta profile", owner: "beta", confirm_to: "beta", confirm_options: ["beta", "local"] }]}
        busy=""
        onConfirm={() => undefined}
        onRemove={() => undefined}
      />
    );
    // Each button carries its own destination: not a submit button, so no
    // browser has to report which one was pressed (Safari before 15.4 does not).
    for (const label of ["Confirm Beta profile for workspace beta", "Confirm Beta profile as yours"]) {
      expect(html).toMatch(new RegExp(`<button[^>]*type="button"[^>]*aria-label="${label}"`));
    }
    // Enter in the key box names no button: it confirms only where there is no choice.
    expect(enterDestination(["local"])).toBe("local");
    expect(enterDestination(["beta", "local"])).toBe("");
  });

  it("shows nothing once every profile is settled", async () => {
    const { default: LegacyProfiles } = await import("./pages/LegacyProfiles");
    const html = renderToStaticMarkup(
      <LegacyProfiles items={[{ ...old, owner_confirmed: true }]} busy="" onConfirm={() => undefined} onRemove={() => undefined} />
    );
    expect(html).toBe("");
  });

  it("tells the Drafts screen the truth: waiting profiles, or that no screen adds one yet", async () => {
    const { draftsProfileNote } = await import("./pages/LegacyProfiles");
    expect(draftsProfileNote(2, 0)).toBe("");
    expect(draftsProfileNote(0, 1)).toBe(
      "1 saved provider profile is waiting for you in Settings, under Provider profiles to confirm."
    );
    expect(draftsProfileNote(0, 3)).toBe(
      "3 saved provider profiles are waiting for you in Settings, under Provider profiles to confirm."
    );
    // D-173: it pointed at a Settings form that no longer exists.
    expect(draftsProfileNote(0, 0)).toBe(
      "Personalising with a model needs a provider profile, and no screen adds one yet. Drafts use local templates until then."
    );
  });
});

describe("what a provider is sent (D-174)", () => {
  it("offers every level the server has, in order, so a restricted provider's own level is on the list", async () => {
    const { POLICY_ORDER, policyWord } = await import("./pages/Connectors");
    // offsetx_apollo_builder/ai/tiers.py DataPolicy, lowest first.
    expect([...POLICY_ORDER]).toEqual(["strict", "pseudonymous", "minimal", "standard", "full"]);
    expect(policyWord("pseudonymous")).toBe("Pseudonymous");
    expect(policyWord("full")).toBe("Full access");
  });
});

describe("the Models panel says when a save cut the level (D-193)", () => {
  it("names the level that was saved, and says nothing more when nothing was cut", async () => {
    const { modelsSavedMessage } = await import("./pages/ModelPicker");
    expect(modelsSavedMessage("NVIDIA NIM", 2, { policy_was_clamped: false, policy_ceiling: "standard" })).toBe(
      "NVIDIA NIM: 2 models enabled"
    );
    expect(modelsSavedMessage("NVIDIA NIM", 1, { policy_was_clamped: true, policy_ceiling: "standard" })).toBe(
      "NVIDIA NIM: 1 model enabled. Its level was saved as Standard, the most its trust allows."
    );
  });
});

describe("where a key is kept is said truly, hosted or not (D-202)", () => {
  it("promises nothing about staying on this machine", () => {
    // With OFFSETX_DATABASE_URL the server encrypts a key and keeps it in the
    // hosted database; on Render "this machine" was never the user's own.
    const source = readFileSync(join(process.cwd(), "src", "pages", "Connectors.tsx"), "utf-8");
    expect(source.match(/on this machine/g) ?? []).toEqual([]);
  });
});

describe("where the data is kept (D-226)", () => {
  // The sidebar said "SQLite on this device" whatever was true, on a server
  // whose CRM was in PostgreSQL and whose disk is wiped at every deploy.
  it("says hosted when the CRM is in PostgreSQL", () => {
    const html = renderToStaticMarkup(<StorageNote storage="hosted_postgres" />);
    expect(html).toContain("Hosted database");
    expect(html).toContain("PostgreSQL");
    expect(html).not.toContain("SQLite on this device");
  });

  it("says local when the CRM is a file on this machine", () => {
    const html = renderToStaticMarkup(<StorageNote storage="local_sqlite" />);
    expect(html).toContain("Local workspace");
    expect(html).toContain("SQLite on this device");
  });

  it("claims nothing until it knows", () => {
    for (const storage of [undefined, "", "something_new"]) {
      const html = renderToStaticMarkup(<StorageNote storage={storage} />);
      expect(html).not.toContain("SQLite on this device");
      expect(html).not.toContain("Hosted database");
    }
    expect(storageWording(undefined).detail).toBe("Checking where data is kept");
  });
});
