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
import AgentTeam, { ToolGrantChoices } from "./AgentTeam";

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

describe('saved tool access', () => {
  it('keeps unavailable saved grants visible and checked so the owner can clear them', () => {
    const html = renderToStaticMarkup(<ToolGrantChoices tools={[]} savedGrants={['removed-123']}
      grants={['removed-123']} catalogueReady onToggle={vi.fn()} />);
    expect(html).toContain('Unavailable saved tool removed-');
    expect(html).toContain('checked=""');
    expect(html).toContain('Clear its saved access');
    expect(html).not.toContain('No tool access is added by default');
  });
  it('keeps a cleared saved grant visible until saving so the pending choice can be undone', () => {
    const html = renderToStaticMarkup(<ToolGrantChoices tools={[]} savedGrants={['removed-123']}
      grants={[]} catalogueReady onToggle={vi.fn()} />);
    expect(html).toContain('Unavailable saved tool removed-');
    expect(html).not.toContain('checked=""');
  });
  it('preserves available choices and waits for a successful catalogue before declaring saved grants unavailable', () => {
    const pending = renderToStaticMarkup(<ToolGrantChoices tools={[]} savedGrants={['saved-id']}
      grants={['saved-id']} catalogueReady={false} onToggle={vi.fn()} />);
    expect(pending).not.toContain('Unavailable saved tool');
    const known = renderToStaticMarkup(<ToolGrantChoices tools={[{id:'saved-id', name:'known-tool', description:''}]}
      savedGrants={['saved-id']} grants={['saved-id']} catalogueReady onToggle={vi.fn()} />);
    expect(known).toContain('known-tool');
    expect(known).not.toContain('Unavailable saved tool');
    expect(known).toContain('checked=""');
  });
});
