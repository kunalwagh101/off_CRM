import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { Badge, PageHeader, Progress, StatCard } from "./components";
import { AuthenticatedApp, LoginScreen, navigation } from "./App";
import { AppContext } from "./context";
import { stageLabel } from "./hooks";
import SalesTracker, { formatSalesMoney } from "./pages/SalesTracker";
import AIStudio from "./pages/AIStudio";
import Connections from "./pages/Connections";

const appContext = {
  campaigns: [],
  campaignId: "",
  activeCampaign: null,
  selectCampaign: () => undefined,
  refreshCampaigns: () => undefined,
  notify: () => undefined
};

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

  it("places AI first and gives the global left navigation its own close control", () => {
    expect(navigation[0]).toMatchObject({ page: "ai", label: "AI" });
    const html = renderToStaticMarkup(
      <AuthenticatedApp
        auth={{ configured: true, authenticated: true, username: "owner", expires_at: null }}
        onLogout={() => undefined}
      />
    );
    expect(html).toContain("OFF_CRM");
    expect(html).toContain("Close main navigation");
    expect(html).toContain('href="#ai"');
    expect(html).toContain("Connectors");
  });

  it("renders all sales tracker operating views from one lead-card source", () => {
    const html = renderToStaticMarkup(
      <AppContext.Provider value={appContext}>
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

  it("renders the AI workspace with independent history controls and privacy boundaries", () => {
    const html = renderToStaticMarkup(
      <AppContext.Provider value={appContext}>
        <AIStudio />
      </AppContext.Provider>
    );
    expect(html).toContain("OFF_AI");
    expect(html).toContain("Close chat and project history");
    expect(html).toContain("Chats");
    expect(html).toContain("Projects");
    expect(html).toContain("No mailbox access");
    expect(html).toContain("Email addresses stay local");
    expect(html).toContain("Exact egress audit");
  });

  it("keeps Gmail and classified AI providers in Connectors instead of Settings", () => {
    const html = renderToStaticMarkup(
      <AppContext.Provider value={appContext}>
        <Connections />
      </AppContext.Provider>
    );
    expect(html).toContain("Connectors");
    expect(html).toContain("Gmail");
    expect(html).toContain("AI providers");
    expect(html).toContain("No pull tools");
    expect(html).toContain("Same-tier failover");
  });
});

describe("discovery and Notion additions", () => {
  const context = {
    ...appContext,
    campaignId: "c1"
  };

  it("lets the operator choose the crawler and worker count", async () => {
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

  it("offers one-way Notion sync while OFF_CRM stays the source of truth", async () => {
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
