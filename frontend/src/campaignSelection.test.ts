import { describe, expect, it, vi } from "vitest";
import { ApiError } from "./api";
import { CampaignSelection } from "./campaignSelection";
import type { Campaign } from "./types";

const campaign = (id: string, kind = "email"): Campaign => ({
  id, name: `Campaign ${id}`, kind, status: "active", daily_send_limit: 25,
  timezone: "Asia/Kolkata", approval_mode: "manual", variants: ["A", "B"],
  updated_at: "2026-09-12T00:00:00Z", send_window_start: "09:00", send_window_end: "17:00",
  send_weekdays: [0, 1, 2, 3, 4], experiment_hypothesis: "", experiment_metric: "reply_rate",
  experiment_min_sample: 40, control_variant: "A"
});

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (error: unknown) => void;
  const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}

function setup(saved = "a", initial = [campaign("a"), campaign("b")]) {
  let rows = [...initial];
  let stored = saved;
  const source = {
    list: vi.fn(async () => [...rows]),
    get: vi.fn(async (id: string) => {
      const row = rows.find((item) => item.id === id);
      if (!row) throw new ApiError("Campaign not found", 404);
      return row;
    }),
    create: vi.fn(async (_body: Record<string, unknown>) => {
      const row = campaign("new", "image");
      rows = [row, ...rows];
      return row;
    })
  };
  const storage = { read: () => stored, write: vi.fn((id: string) => { stored = id; }) };
  const selection = new CampaignSelection(source, storage);
  return { selection, source, storage, stored: () => stored, rows: (next: Campaign[]) => { rows = next; } };
}

describe("campaign selection owns the campaign it displays", () => {
  it("keeps a stored ID inactive until the server confirms its campaign", async () => {
    const { selection, storage } = setup();
    expect(selection.getSnapshot()).toMatchObject({ campaignId: "", ready: false });
    expect(storage.write).not.toHaveBeenCalled();
    await selection.refresh();
    expect(selection.getSnapshot()).toMatchObject({ campaignId: "a", ready: true });
  });

  it("publishes the created row and its selection together before refresh completes", async () => {
    const { selection, source, stored } = setup();
    await selection.refresh();
    const refresh = deferred<Campaign[]>();
    source.list.mockReturnValueOnce(refresh.promise);
    const invalid: string[] = [];
    selection.subscribe(() => {
      const state = selection.getSnapshot();
      if (state.campaignId && !state.campaigns.some((row) => row.id === state.campaignId)) invalid.push(state.campaignId);
    });
    await selection.create({ name: "New image campaign", kind: "image" });
    expect(selection.getSnapshot()).toMatchObject({ campaignId: "new", loading: true });
    expect(selection.getSnapshot().campaigns.find((row) => row.id === "new")?.kind).toBe("image");
    expect(stored()).toBe("new");
    expect(invalid).toEqual([]);
    refresh.resolve([campaign("new", "image"), campaign("a")]);
  });

  it("ignores an old list response delivered after creation and a newer refresh", async () => {
    const { selection, source, stored } = setup();
    await selection.refresh();
    const old = deferred<Campaign[]>();
    source.list.mockReturnValueOnce(old.promise);
    const obsolete = selection.refresh();
    await selection.create({ name: "New image campaign" });
    await selection.refresh();
    old.resolve([campaign("a"), campaign("b")]);
    await obsolete;
    expect(selection.getSnapshot().campaignId).toBe("new");
    expect(stored()).toBe("new");
  });

  it("does not let a pending refresh undo a later manual switch", async () => {
    const { selection, source, stored } = setup();
    await selection.refresh();
    const old = deferred<Campaign[]>();
    source.list.mockReturnValueOnce(old.promise);
    const obsolete = selection.refresh();
    selection.select("b");
    old.resolve([campaign("a"), campaign("b")]);
    await obsolete;
    expect(selection.getSnapshot()).toMatchObject({ campaignId: "b", loading: false });
    expect(stored()).toBe("b");
  });

  it("keeps a later manual choice when an earlier creation finally succeeds", async () => {
    const { selection, source, rows, stored } = setup();
    await selection.refresh();
    const save = deferred<Campaign>();
    source.create.mockReturnValueOnce(save.promise);
    const creating = selection.create({ name: "Slow creation" });
    selection.select("b");
    rows([campaign("new"), campaign("a"), campaign("b")]);
    save.resolve(campaign("new"));
    await creating;
    await selection.refresh();
    expect(selection.getSnapshot().campaignId).toBe("b");
    expect(selection.getSnapshot().campaigns.some((row) => row.id === "new")).toBe(true);
    expect(stored()).toBe("b");
  });

  it("looks up a saved campaign outside the first 200 rows instead of replacing it", async () => {
    const { selection, source, stored } = setup("older");
    const firstPage = Array.from({ length: 200 }, (_, index) => campaign(String(index)));
    source.list.mockResolvedValue(firstPage);
    source.get.mockResolvedValue(campaign("older", "image"));
    await selection.refresh();
    expect(source.get).toHaveBeenCalledWith("older");
    expect(selection.getSnapshot().campaigns).toHaveLength(201);
    expect(selection.getSnapshot().campaignId).toBe("older");
    expect(stored()).toBe("older");
  });

  it("keeps a newly created campaign when the refresh list is stale but its detail exists", async () => {
    const { selection, source, stored } = setup();
    await selection.refresh();
    source.list.mockResolvedValue([campaign("a")]);
    await selection.create({ name: "Created after this list snapshot" });
    await selection.refresh();
    expect(source.get).toHaveBeenCalledWith("new");
    expect(selection.getSnapshot().campaignId).toBe("new");
    expect(stored()).toBe("new");
  });

  it("falls back only after a detail 404 and tells the user which campaign replaced it", async () => {
    const { selection, stored } = setup("deleted");
    await selection.refresh();
    expect(selection.getSnapshot()).toMatchObject({ campaignId: "a", ready: true });
    expect(selection.getSnapshot().selectionNotice).toContain("Switched to Campaign a");
    expect(stored()).toBe("a");
  });

  it("clears a deleted final campaign instead of leaving a stale target for imports", async () => {
    const { selection, stored } = setup("deleted", []);
    await selection.refresh();
    expect(selection.getSnapshot()).toMatchObject({ campaignId: "", campaigns: [], ready: true });
    expect(stored()).toBe("");
  });

  it.each([401, 403, 429, 500, 503])("does not treat detail HTTP %i as deletion", async (status) => {
    const { selection, source, stored } = setup("older");
    source.get.mockRejectedValue(new ApiError("Try again later", status));
    await selection.refresh();
    expect(selection.getSnapshot()).toMatchObject({ campaignId: "", ready: false, loading: false, error: "Try again later" });
    expect(stored()).toBe("older");
  });

  it("ignores a delayed detail 404 after the user has selected another known campaign", async () => {
    const { selection, source, stored } = setup();
    await selection.refresh();
    source.list.mockResolvedValue([campaign("b")]);
    const detail = deferred<Campaign>();
    source.get.mockReturnValueOnce(detail.promise);
    const obsolete = selection.refresh();
    await vi.waitFor(() => expect(source.get).toHaveBeenCalledWith("a"));
    selection.select("b");
    detail.reject(new ApiError("Gone", 404));
    await obsolete;
    expect(selection.getSnapshot()).toMatchObject({ campaignId: "b", selectionNotice: "", error: "" });
    expect(stored()).toBe("b");
  });

  it("a refresh failure keeps the verified campaign and a failed save does not change it", async () => {
    const { selection, source, stored } = setup();
    await selection.refresh();
    source.list.mockRejectedValue(new Error("Network unavailable"));
    await selection.refresh();
    expect(selection.getSnapshot()).toMatchObject({ campaignId: "a", ready: true, error: "Network unavailable" });
    source.create.mockRejectedValue(new ApiError("Name is required", 422));
    await expect(selection.create({ name: "" })).rejects.toThrow("Name is required");
    expect(selection.getSnapshot().campaignId).toBe("a");
    expect(stored()).toBe("a");
  });

  it("does not report a saved campaign as a failed creation when the refresh fails", async () => {
    const { selection, source, stored } = setup();
    await selection.refresh();
    source.list.mockRejectedValue(new Error("Refresh unavailable"));
    await expect(selection.create({ name: "New" })).resolves.toMatchObject({ id: "new" });
    await selection.refresh();
    expect(selection.getSnapshot()).toMatchObject({ campaignId: "new", ready: true, error: "Refresh unavailable" });
    expect(stored()).toBe("new");
  });

  it("does not update a signed-out session or its saved selection from pending work", async () => {
    const { selection, source, stored } = setup();
    await selection.refresh();
    const save = deferred<Campaign>();
    source.create.mockReturnValueOnce(save.promise);
    const creating = selection.create({ name: "Pending at logout" });
    const old = deferred<Campaign[]>();
    source.list.mockReturnValueOnce(old.promise);
    const refreshing = selection.refresh();
    selection.disconnect();
    old.resolve([campaign("other")]);
    save.resolve(campaign("new"));
    await Promise.all([creating, refreshing]);
    expect(selection.getSnapshot().campaignId).toBe("a");
    expect(stored()).toBe("a");
  });

  it("survives React effect reconnect without accepting work from the old connection", async () => {
    const { selection, source } = setup();
    await selection.refresh();
    const save = deferred<Campaign>();
    source.create.mockReturnValueOnce(save.promise);
    const creating = selection.create({ name: "Old connection" });
    selection.disconnect();
    selection.connect();
    await selection.refresh();
    save.resolve(campaign("new"));
    await creating;
    expect(selection.getSnapshot().campaignId).toBe("a");
    expect(selection.getSnapshot().campaigns.some((row) => row.id === "new")).toBe(false);
  });

  it("keeps a valid in-tab selection and explains when browser storage cannot save it", async () => {
    const { selection, storage } = setup();
    storage.write.mockImplementation(() => { throw new Error("Storage disabled"); });
    await selection.refresh();
    selection.select("b");
    expect(selection.getSnapshot().campaignId).toBe("b");
    expect(selection.getSnapshot().storageWarning).toContain("select it again after reloading");
  });
});
