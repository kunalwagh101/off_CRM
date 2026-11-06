import { renderToStaticMarkup } from "react-dom/server";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AppContext } from "../context";

const state = vi.hoisted(() => ({ workspace: "local", error: "" }));
vi.mock("../api", () => ({
  idempotencyKey: () => "test-id",
  api: { get: (path: string) => path === "/auth/session" ? { workspace_id: state.workspace } : { items: [] } }
}));
vi.mock("../hooks", () => ({
  useResource: (load: () => unknown) => ({ data: load(), loading: false, error: state.error, reload: vi.fn() })
}));
import AgentTeam from "./AgentTeam";

function screen() {
  return renderToStaticMarkup(<AppContext.Provider value={{ campaigns: [], campaignId: "", activeCampaign: null, selectCampaign: vi.fn(), createCampaign: vi.fn(), refreshCampaigns: vi.fn(), notify: vi.fn() }}><AgentTeam /></AppContext.Provider>);
}

describe("agent-team access and prerequisites", () => {
  beforeEach(() => { state.workspace = "local"; state.error = ""; });
  it("lets an owner create companions with no campaign and explains approval boundaries", () => {
    const html = screen();
    expect(html).toContain("Create companion");
    expect(html).toContain("Set up five roles");
    expect(html).toContain("Five role actions");
    expect(html).toContain("Approval and publication stay");
    expect(html).not.toContain("Strategy product");
  });
  it("keeps owner-only procedures and role actions out of a regular workspace", () => {
    state.workspace = "client-a";
    const html = screen();
    expect(html).toContain("Create companion");
    expect(html).not.toContain("Set up five roles");
    expect(html).not.toContain("Create procedure");
    expect(html).not.toContain("Run selected role");
  });
  it("shows backend loading failures and offers an actual retry action", () => {
    state.error = "Sign in again to read this workspace";
    const html = screen();
    expect(html).toContain(state.error);
    expect(html).toContain("Retry loading");
  });
});
