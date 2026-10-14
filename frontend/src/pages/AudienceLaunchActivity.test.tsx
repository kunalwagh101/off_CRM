import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import { AppContext } from "../context";
import type { Campaign } from "../types";

vi.mock("../hooks", async (original) => ({
  ...(await original<typeof import("../hooks")>()),
  useResource: (_load: unknown, dependencies: unknown[]) => ({
    data: dependencies.length === 3 ? {
      items: [{
        id: "event-one", event_type: "contacts_bulk_updated",
        created_at: "2026-10-13T10:00:00+00:00",
        payload: { action: "stop", requested: 3, changed: 2, secret: "NEVER_RENDER" }
      }],
      total: 55
    } : {
      campaign_id: "c1", kind: "email", eligible_for_local_review: false,
      candidate_count: 0, remaining_today: 25, needs_approval: 2,
      external_delivery_verified: false,
      checks: [
        { id: "active", passed: true, message: "Campaign is active", screen: "campaigns" },
        { id: "approved_due", passed: false, message: "Approve drafts first", screen: "drafts" },
      ],
      limitations: "Not a live-provider guarantee",
      items: [{ event_type: "contacts_bulk_updated", count: 1 }],
    },
    loading: false, error: "", reload: () => undefined,
  })
}));

import LaunchReadiness from "./LaunchReadiness";
import CampaignActivity, { activityPath, safeEventDetails } from "./CampaignActivity";
import { ManualContactModal, StopContactsModal } from "./AudienceOperations";

const campaign = { id: "c1", name: "Campaign One", kind: "email" } as Campaign;
const context = {
  campaigns: [campaign], campaignId: "c1", activeCampaign: campaign,
  selectCampaign: () => undefined, createCampaign: async () => campaign,
  refreshCampaigns: () => undefined, notify: () => undefined,
};

describe("Audience, launch readiness and timeline", () => {
  it("creates a contact by explicit form, never says it will send", () => {
    const html = renderToStaticMarkup(
      <ManualContactModal campaignId="c1" open={true} onClose={() => undefined}
        onSaved={() => undefined} notify={() => undefined} categories={["CBAM"]} />
    );
    expect(html).toContain("Full name");
    expect(html).toContain("Work email");
    expect(html).toContain("Verified public research hook");
    expect(html).toContain("Nothing is generated, approved or sent automatically");
    expect(html).toContain("Add contact");
  });

  it("requires a typed STOP and describes what will happen", () => {
    const html = renderToStaticMarkup(
      <StopContactsModal open={true} total={3} busy={false}
        onClose={() => undefined} onConfirm={async () => undefined} />
    );
    expect(html).toContain("Type STOP to confirm");
    expect(html).toContain("3 selected");
    expect(html).toContain("Stop selected outreach");
  });

  it("shows readiness blockers and never offers a send action", () => {
    const html = renderToStaticMarkup(
      <AppContext.Provider value={context}><LaunchReadiness /></AppContext.Provider>
    );
    expect(html).toContain("Preparation needed");
    expect(html).toContain("Approve drafts first");
    expect(html).toContain("Open drafts");
    expect(html).toContain("Not a live-provider guarantee");
    expect(html).not.toContain("Send now");
  });

  it("filters events at the server and never renders raw secret payload values", () => {
    expect(activityPath("c/1", 1, "contact / reply")).toBe(
      "/campaigns/c%2F1/events?limit=50&offset=50&event_type=contact%20%2F%20reply"
    );
    expect(safeEventDetails({
      id: "a", event_type: "send", created_at: "",
      payload: { action: "stop", changed: 2, secret: "DO NOT SHOW", body: "PRIVATE" }
    })).toBe("action: stop · changed: 2");
    const html = renderToStaticMarkup(
      <AppContext.Provider value={context}><CampaignActivity /></AppContext.Provider>
    );
    expect(html).toContain("Campaign activity timeline");
    expect(html).toContain("contacts bulk updated");
    expect(html).toContain("Showing 1–50 of 55");
    expect(html).not.toContain("NEVER_RENDER");
  });
});
