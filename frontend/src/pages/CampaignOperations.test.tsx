import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import { AppContext } from "../context";
import type { Campaign } from "../types";

vi.mock("../hooks", async (original) => ({
  ...(await original<typeof import("../hooks")>()),
  useResource: () => ({
    data: {
      items: [{ id: "email", label: "Email outreach", implemented: true, uses_email_columns: true }],
      campaign_id: "c1", kind: "email", contacts: 20, contacted: 10,
      messages_sent: 15, replied: 5, replied_contacted: 4,
      completed: 1, stopped: 0, awaiting_first_contact: 10, reply_rate: 40,
      reply_rate_denominator: "unique_contacts_sent",
      draft_status: { approved: 7, pending: 3 }
    },
    loading: false, error: "", reload: () => undefined,
  }),
}));

import Campaigns from "./Campaigns";
import { CampaignPerformancePanel, CampaignSettingsModal, CloneCampaignModal } from "./CampaignOperations";

const campaign: Campaign = {
  id: "c1", name: "Climate Outreach", kind: "email", status: "active",
  daily_send_limit: 25, timezone: "Asia/Kolkata", approval_mode: "each_message",
  followup1_working_days: 4, followup2_working_days: 6,
  variants: ["A", "B"], updated_at: "2026-10-13T10:00:00Z",
  send_window_start: "09:00", send_window_end: "17:00",
  send_weekdays: [0, 1, 2, 3, 4],
  experiment_hypothesis: "Human evidence performs",
  experiment_metric: "reply_rate", experiment_min_sample: 40, control_variant: "A",
  contact_count: 20, replied_count: 5, sent_count: 15,
};

const context = {
  campaigns: [campaign], campaignId: "c1", activeCampaign: campaign,
  selectCampaign: () => undefined,
  createCampaign: async () => campaign,
  refreshCampaigns: () => undefined,
  notify: () => undefined,
};

describe("Campaign Management product capabilities", () => {
  it("offers editing, reuse, performance and explicit archiving", () => {
    const html = renderToStaticMarkup(
      <AppContext.Provider value={context}>
        <Campaigns />
      </AppContext.Provider>,
    );
    expect(html).toContain("Edit settings");
    expect(html).toContain("Duplicate settings");
    expect(html).toContain("Performance");
    expect(html).toContain("Archive");
    expect(html).toContain("Pause");
  });

  it("shows complete existing settings without a new campaign type", () => {
    const html = renderToStaticMarkup(
      <CampaignSettingsModal campaign={campaign} changed={() => undefined}
        close={() => undefined} notify={() => undefined} />
    );
    expect(html).toContain("Send window starts");
    expect(html).toContain("First follow-up");
    expect(html).toContain("Sending weekdays");
    expect(html).toContain("Experiment hypothesis");
    expect(html).toContain("Control variant");
    expect(html).toContain("Save settings");
    expect(html).not.toContain("Change campaign type");
  });

  it("explains configuration-only paused copies before creation", () => {
    const html = renderToStaticMarkup(
      <CloneCampaignModal campaign={campaign} created={() => undefined}
        close={() => undefined} notify={() => undefined} />
    );
    expect(html).toContain("Create paused copy");
    expect(html).toContain("no recipients");
    expect(html).toContain("Duplicate campaign configuration");
  });

  it("labels reply rate by actually contacted recipients, not imports", () => {
    const html = renderToStaticMarkup(<CampaignPerformancePanel campaign={campaign} />);
    expect(html).toContain("Reply rate");
    expect(html).toContain("40%");
    expect(html).toContain("unique contacts sent");
    expect(html).toContain("Outbound messages");
    expect(html).toContain("pending");
  });
});
