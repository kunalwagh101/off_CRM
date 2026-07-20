import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { Badge, PageHeader, Progress, StatCard } from "./components";
import { LoginScreen } from "./App";
import { AppContext } from "./context";
import { stageLabel } from "./hooks";
import SalesTracker, { formatSalesMoney } from "./pages/SalesTracker";

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
      <AppContext.Provider value={{ campaigns: [], campaignId: "", activeCampaign: null, selectCampaign: () => undefined, refreshCampaigns: () => undefined, notify: () => undefined }}>
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
    selectCampaign: () => undefined,
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
});
