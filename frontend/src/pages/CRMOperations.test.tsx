import { renderToStaticMarkup } from "react-dom/server";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";
import { AppContext } from "../context";
import type { Campaign } from "../types";

vi.mock("../hooks", async (original) => ({
  ...(await original<typeof import("../hooks")>()),
  useResource: () => ({
    loading: false, error: "", reload: () => undefined,
    data: {
      items: [], total: 0, identity_note: "A matching email is not proof.",
      rate_note: "Recorded outreach only.", sales_note: "Associations only.",
      owner_note: "Labels are not verified identities.",
      overall: { tasks: 0, open: 0, done: 0, overdue: 0, on_time: 0 }
    }
  })
}));

import {
  CRMDataQuality, CampaignComparison, FollowupPerformance,
  qualityPath, comparePath, workloadPath
} from "./CRMOperations";

const campaign = { id: "campaign-one", name: "Campaign one" } as Campaign;
const context = {
  campaigns: [campaign], campaignId: "campaign-one", activeCampaign: campaign,
  selectCampaign: () => undefined, createCampaign: async () => campaign,
  refreshCampaigns: () => undefined, notify: () => undefined
};

function html(view: ReactNode) {
  return renderToStaticMarkup(<AppContext.Provider value={context}>{view}</AppContext.Provider>);
}

describe("CRM operations product features", () => {
  it("generates encoded, bounded request paths", () => {
    expect(qualityPath("sales_overlap", "a+b@example.com", 1)).toContain("search=a%2Bb%40example.com");
    expect(qualityPath("missing_title", "", 1)).toContain("offset=25");
    expect(comparePath("A&B", 2)).toContain("search=A%26B");
    expect(comparePath("a", 0)).toContain("limit=25");
    expect(workloadPath("company/campaign", 3)).toContain("campaign_id=company%2Fcampaign");
    expect(workloadPath("", -1)).toContain("offset=0");
  });

  it("offers non-destructive CRM data review", () => {
    const markup = html(<CRMDataQuality />);
    expect(markup).toContain("CRM data quality");
    expect(markup).toContain("Sales Tracker");
    expect(markup).toContain("Nothing is merged or changed automatically");
    expect(markup).not.toContain("Send now");
  });

  it("shows real denominator and zero-campaign state", () => {
    const markup = html(<CampaignComparison />);
    expect(markup).toContain("Compare campaigns");
    expect(markup).toContain("members with both saved outbound and inbound messages");
    expect(markup).toContain("No campaigns found");
  });

  it("reports human tasks separately from user permissions", () => {
    const markup = html(<FollowupPerformance />);
    expect(markup).toContain("Follow-up performance");
    expect(markup).toContain("All campaigns");
    expect(markup).toContain("Completed on time");
    expect(markup).toContain("do not grant permissions");
  });
});
