import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import { AppContext } from "../context";
import type { Campaign } from "../types";

vi.mock("../hooks", async (original) => ({
  ...(await original<typeof import("../hooks")>()),
  useResource: (_load: unknown, dependencies: unknown[]) => ({
    data: dependencies.length === 2 ? {
      campaign_id: "campaign-one",
      contact: {
        id: "member-one", full_name: "Ravi Shah", email: "ravi@example.com",
        company: "Sample", title: "Director", category: "CBAM / Trade Compliance",
        status: "replied", current_stage: "initial", variant_id: "A",
        recipient_timezone: "Asia/Kolkata"
      },
      messages: { sent: 1, received: 1 },
      latest_reply: {
        id: "reply-one", subject: "Interested",
        received_at: "2026-10-15T10:00:00Z"
      },
      triage: { review_status: "triaged", outcome: "positive" },
      tasks: {
        total: 1, open: 1,
        next: {
          id: "task-one", title: "Schedule a call",
          due_at: "2026-10-16T10:00:00Z", priority: "high",
          assigned_to: "Founder"
        }
      },
      sales_lead: null
    } : {
      total: 3,
      counts: { overdue_task: 1, reply_review: 1, sales_attention: 1 },
      evaluated_at: "2026-10-15T10:00:00Z",
      sales_attention_rule: "No touch recorded, or last touch more than seven days ago",
      items: [
        { action_type: "overdue_task", item_id: "t1",
          campaign_contact_id: "member-one", sales_lead_id: null,
          headline: "Call Ravi", occurred_at: "2026-10-14T10:00:00Z",
          due_at: "2026-10-14T10:00:00Z", priority: "high",
          reason: "Overdue human follow-up" },
        { action_type: "reply_review", item_id: "reply2",
          campaign_contact_id: "member-two", sales_lead_id: null,
          headline: "Anita Rao", occurred_at: "2026-10-15T10:00:00Z",
          due_at: null, priority: "normal", reason: "Incoming reply needs review" },
        { action_type: "sales_attention", item_id: "lead3",
          campaign_contact_id: "member-one", sales_lead_id: "lead3",
          headline: "Ravi Shah", occurred_at: "2026-10-15T10:00:00Z",
          due_at: null, priority: "normal", reason: "No recorded sales touch" }
      ]
    },
    loading: false, error: "", reload: () => undefined
  })
}));

import Contact360, { overviewPath } from "./Contact360";
import ActionCenter, { actionCenterPath } from "./ActionCenter";

const campaign = { id: "campaign-one", name: "Climate Outreach", kind: "email" } as Campaign;
const context = {
  campaigns: [campaign], campaignId: campaign.id, activeCampaign: campaign,
  selectCampaign: () => undefined, createCampaign: async () => campaign,
  refreshCampaigns: () => undefined, notify: () => undefined
};

describe("Relationship intelligence product features", () => {
  it("scopes Contact 360 and priorities to encoded campaign URLs", () => {
    expect(overviewPath("campaign/1", "member/2")).toBe(
      "/campaigns/campaign%2F1/contacts/member%2F2/overview"
    );
    expect(actionCenterPath("campaign/1", "sales_attention", 2)).toBe(
      "/campaigns/campaign%2F1/actions?action_type=sales_attention&limit=50&offset=100"
    );
  });

  it("shows a qualified-reply conversion only after manual triage", () => {
    const html = renderToStaticMarkup(
      <Contact360 campaignId="campaign-one" membershipId="member-one"
        onClose={() => undefined} />
    );
    expect(html).toContain("Contact 360");
    expect(html).toContain("Ravi Shah");
    expect(html).toContain("Schedule a call");
    expect(html).toContain("Replies received");
    expect(html).toContain("Convert qualified reply to sales lead");
    expect(html).toContain("Communication history");
    expect(html).not.toContain("raw_json");
  });

  it("shows prioritised counts, task/reply/sales actions and safe navigation", () => {
    const html = renderToStaticMarkup(
      <AppContext.Provider value={context}><ActionCenter /></AppContext.Provider>
    );
    expect(html).toMatch(/Today(?:&#x27;|')s priorities/);
    expect(html).toContain("Overdue tasks");
    expect(html).toContain("Replies to review");
    expect(html).toContain("Sales needing attention");
    expect(html).toContain("Call Ravi");
    expect(html).toContain("Anita Rao");
    expect(html).toContain("Open Sales Tracker");
    expect(html).toContain("Contact 360");
    expect(html).not.toContain("Send now");
  });
});
