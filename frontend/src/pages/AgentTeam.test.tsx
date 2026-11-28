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
import AgentTeam, { procedurePatch, companionProfilePatch, ToolGrantChoices, roleRequestAttempt, roleIntentDigest, saveRoleRequestAttempt, loadRoleRequestAttempt, clearRoleRequestAttempt, roleExecutionIntent, recoverLegacyRoleRequestAttempt } from "./AgentTeam";

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


describe("role actions keep the same receipt across uncertain retries", () => {
  it("uses one key for the same pending effect, and changes key for new action context", () => {
    let generated = 0;
    const next = () => `agent-attempt-${++generated}`;
    const payload = { workspace: "local", companion: "maker", role: "Poster", account_ids: ["a"] };
    const first = roleRequestAttempt(null, payload, next);
    expect(first.key).toBe("agent-attempt-1");
    const retry = roleRequestAttempt(first, { ...payload, account_ids: ["a"] }, next);
    expect(retry).toEqual(first);
    expect(generated).toBe(1);
    const changed = roleRequestAttempt(first, { ...payload, account_ids: ["b"] }, next);
    expect(changed.key).toBe("agent-attempt-2");
    const changedCompanion = roleRequestAttempt(first, { ...payload, companion: "director" }, next);
    expect(changedCompanion.key).toBe("agent-attempt-3");
  });
});


describe("uncertain Agent Team receipts survive reload without storing private content", () => {
  it("restores the same receipt only for an identical hashed intent", async () => {
    const records = new Map<string, string>();
    const storage = {
      getItem: (key: string) => records.get(key) ?? null,
      setItem: (key: string, value: string) => { records.set(key, value); },
      removeItem: (key: string) => { records.delete(key); },
    };
    const intent = {
      workspace: "local", companion: "Maker", role: "Maker",
      topic: "PRIVATE PRODUCT RESEARCH CONTENT",
    };
    const hashed = await roleIntentDigest(intent);
    expect(hashed).toMatch(/^[0-9a-f]{64}$/);
    const attempt = roleRequestAttempt(null, hashed, () => "role-once");
    saveRoleRequestAttempt(storage, hashed, attempt);
    expect([...records.values()].join("")).not.toContain("PRIVATE PRODUCT");
    expect(loadRoleRequestAttempt(storage, hashed)).toEqual(attempt);
    const changed = await roleIntentDigest({ ...intent, topic: "Different action" });
    expect(loadRoleRequestAttempt(storage, changed)).toBeNull();
    const restored = roleRequestAttempt(loadRoleRequestAttempt(storage, hashed), hashed, () => "unwanted-key");
    expect(restored.key).toBe("role-once");
    clearRoleRequestAttempt(storage, hashed);
    expect(loadRoleRequestAttempt(storage, hashed)).toBeNull();
  });
});

describe("role execution receipts ignore the unrelated companion selection", () => {
  it("roleExecutionIntent keeps Maker retries stable when the selected companion changes", async () => {
    const payload = { role: "Maker", campaign_id: "image-1", topic: "Private topic" };
    const before = roleExecutionIntent("local", "owner", payload);
    const afterSelectingDifferentCompanion = roleExecutionIntent("local", "owner", { ...payload });
    expect(await roleIntentDigest(before)).toBe(await roleIntentDigest(afterSelectingDifferentCompanion));
    expect(await roleIntentDigest(roleExecutionIntent("other", "owner", payload))).not.toBe(await roleIntentDigest(before));
    expect(await roleIntentDigest(roleExecutionIntent("local", "colleague", payload))).not.toBe(await roleIntentDigest(before));
    expect(await roleIntentDigest(roleExecutionIntent("local", "owner", { ...payload, topic: "changed" }))).not.toBe(await roleIntentDigest(before));
    expect(JSON.stringify(before)).not.toContain("companion");
  });

  it("recovers a pre-fix pending receipt after selecting another companion and a reload", async () => {
    const entries = new Map<string, string>();
    const storage = {
      getItem: (key: string) => entries.get(key) ?? null,
      setItem: (key: string, value: string) => { entries.set(key, value); },
      removeItem: (key: string) => { entries.delete(key); },
    };
    const payload = { role: "Poster", campaign_id: "distribution-1", account_ids: ["a"] };
    const legacy = { workspace: "local", actor: "owner", companion: "old-companion", payload };
    const oldDigest = await roleIntentDigest(legacy);
    saveRoleRequestAttempt(storage, oldDigest, roleRequestAttempt(null, oldDigest, () => "existing-receipt"));

    const intent = roleExecutionIntent("local", "owner", payload);
    const recovered = await recoverLegacyRoleRequestAttempt(storage, intent, ["new-companion", "old-companion"]);
    expect(recovered?.key).toBe("existing-receipt");
    expect(recovered?.digests).toContain(oldDigest);
    expect(await recoverLegacyRoleRequestAttempt(storage, roleExecutionIntent("other", "owner", payload), ["old-companion"])).toBeNull();
    expect(await recoverLegacyRoleRequestAttempt(storage, roleExecutionIntent("local", "owner", { ...payload, account_ids: ["b"] }), ["old-companion"])).toBeNull();

    const newDigest = await roleIntentDigest(intent);
    const next = roleRequestAttempt(null, newDigest, () => recovered?.key ?? "unexpected");
    saveRoleRequestAttempt(storage, newDigest, next);
    expect(loadRoleRequestAttempt(storage, newDigest)?.key).toBe("existing-receipt");
    clearRoleRequestAttempt(storage, newDigest);
    for (const digest of recovered?.digests ?? []) clearRoleRequestAttempt(storage, digest);
    expect(entries.size).toBe(0);
  });

  it("refuses to choose between two distinct legacy keys for the same actual role request", async () => {
    const entries = new Map<string, string>();
    const storage = {
      getItem: (key: string) => entries.get(key) ?? null,
      setItem: (key: string, value: string) => { entries.set(key, value); },
      removeItem: (key: string) => { entries.delete(key); },
    };
    const payload = { role: "Director", gtm_request: { product_id: "p1" } };
    for (const [companion, key] of [["a", "first-key"], ["b", "second-key"]] as const) {
      const digest = await roleIntentDigest({ workspace: "local", actor: "owner", companion, payload });
      saveRoleRequestAttempt(storage, digest, roleRequestAttempt(null, digest, () => key));
    }
    await expect(recoverLegacyRoleRequestAttempt(
      storage, roleExecutionIntent("local", "owner", payload), ["a", "b"],
    )).rejects.toThrow(/multiple pending/i);
  });
});


describe("companion profile saves preserve concurrent security changes", () => {
  const saved = {
    id: "c1", name: "Original", instructions: "Review carefully",
    memory_scope: "original-scope", granted_tool_ids: ["a", "b"], enabled: true,
  };
  const draft = {
    name: saved.name, instructions: saved.instructions,
    memory_scope: saved.memory_scope, granted_tool_ids: [...saved.granted_tool_ids],
  };

  it("sends only a rename, not unchanged permissions or memory scope", () => {
    expect(companionProfilePatch(saved, { ...draft, name: " Renamed " }))
      .toEqual({ name: "Renamed" });
  });
  it("omits unchanged fields and grant ordering", () => {
    expect(companionProfilePatch(saved, { ...draft, granted_tool_ids: ["b", "a"] }))
      .toEqual({});
  });
  it("retains explicit revocation and explicit scope changes", () => {
    expect(companionProfilePatch(saved, { ...draft, granted_tool_ids: [], memory_scope: "new-scope" }))
      .toEqual({ granted_tool_ids: [], memory_scope: "new-scope" });
  });
  it("includes changed instructions without resetting other fields", () => {
    expect(companionProfilePatch(saved, { ...draft, instructions: "Check the source." }))
      .toEqual({ instructions: "Check the source." });
  });
});


describe("procedure editor preserves concurrent content edits", () => {
  const saved = { name: "Original", content: "Original procedure." };
  it("renames without sending stale instructions", () => {
    expect(procedurePatch(saved, { ...saved, name: " Renamed " })).toEqual({ name: "Renamed" });
  });
  it("edits content without sending a stale name", () => {
    expect(procedurePatch(saved, { ...saved, content: "Revised procedure." })).toEqual({ content: "Revised procedure." });
  });
  it("does not send a stale unchanged draft", () => {
    expect(procedurePatch(saved, saved)).toEqual({});
  });
});
