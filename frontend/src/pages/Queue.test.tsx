import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import { AppContext } from "../context";

vi.mock("../hooks", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../hooks")>()),
  useResource: () => ({
    data: {
      items: [{
        campaign_contact_id: "row-1",
        full_name: "Sample Person",
        email: "person@example.test",
        company: "Example",
        status: "new",
        current_stage: "",
        draft_stage: "initial",
        approval_status: "pending",
        sendable: true,
        quality_score: 85,
        is_due: true,
      }],
      total: 218,
      limit: 100,
      offset: 0,
      counts: { all: 218, ready: 7, approval: 203, replied: 8 },
    },
    loading: false, error: "", reload: () => undefined,
  }),
}));

import Queue, { QUEUE_PAGE_SIZE, queuePagePath } from "./Queue";

describe("send queue visibility", () => {
  it("uses server-backed page URLs including the queue view", () => {
    expect(QUEUE_PAGE_SIZE).toBe(100);
    expect(queuePagePath("c/one", 2, "approval")).toBe(
      "/campaigns/c%2Fone/queue?limit=100&offset=200&view=approval"
    );
    expect(queuePagePath("c", -1, "all")).toContain("offset=0");
  });

  it("shows global totals even when the current page has just one row", () => {
    const html = renderToStaticMarkup(
      <AppContext.Provider value={{
        campaigns: [],
        campaignId: "campaign-one",
        activeCampaign: { id: "campaign-one", name: "Launch", daily_send_limit: 25 } as never,
        selectCampaign: () => undefined,
        createCampaign: async () => { throw new Error("Not called"); },
        refreshCampaigns: () => undefined,
        notify: () => undefined,
      }}>
        <Queue />
      </AppContext.Provider>
    );
    expect(html).toContain("Ready now");
    expect(html).toContain("Needs approval");
    expect(html).toContain("7");
    expect(html).toContain("203");
    expect(html).toContain("8");
    expect(html).toContain("All contacts (218)");
    expect(html).toContain("Approved and due (7)");
    expect(html).toContain("Replied (8)");
    expect(html).toContain('aria-label="Filter queue"');
    expect(html).toContain("Showing 1–100 of 218");
    expect(html).toContain('aria-label="Queue pages"');
    expect(html).toContain("Previous page");
    expect(html).toContain("Next page");
    expect(html).toContain("Send with Gmail");
  });
});
