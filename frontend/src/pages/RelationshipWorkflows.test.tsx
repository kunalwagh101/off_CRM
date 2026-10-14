import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import { AppContext } from "../context";
import type { Campaign } from "../types";

vi.mock("../hooks", async (original) => ({
  ...(await original<typeof import("../hooks")>()),
  useResource: (_loader: unknown, dependencies: unknown[]) => ({
    data: dependencies.length === 3 ? {
      campaign_contact_id: "row-1",
      contact: { full_name: "Ravi Shah", email: "ravi@example.test", company: "Sample" },
      total: 1,
      items: [{
        id: "message-1", direction: "inbound", stage: "reply",
        subject: "Interested", body_preview: "Can we arrange a call?",
        truncated: 0, created_at: "2026-10-14T10:00:00Z"
      }]
    } : typeof dependencies[3] === "boolean" ? {
      total: 1,
      items: [{
        id: "task-one", campaign_id: "c1", campaign_contact_id: "row-1",
        title: "Call Ravi", description: "Book next meeting", assigned_to: "Owner",
        contact_name: "Ravi Shah", due_at: "2026-10-20T10:00:00Z",
        priority: "high", status: "open", revision: 1
      }]
    } : {
      total: 1,
      items: [{
        campaign_contact_id: "row-1",
        full_name: "Ravi Shah", email: "ravi@example.test", company: "Sample",
        status: "replied", subject: "Interested", reply_preview: "Can we talk?",
        received_at: "2026-10-14T10:00:00Z", review_status: "unreviewed",
        outcome: "", triage_note: "",
      }]
    },
    loading: false, error: "", reload: () => undefined,
  })
}));

import ReplyInbox, { inboxPath } from "./ReplyInbox";
import Followups, { followupsPath, TaskComposer } from "./Followups";
import ContactConversation, { contactMessagePath } from "./ContactConversation";

const campaign = { id: "c1", name: "Climate Outreach", kind: "email" } as Campaign;
const context = {
  campaigns: [campaign], campaignId: "c1", activeCampaign: campaign,
  selectCampaign: () => undefined, createCampaign: async () => campaign,
  refreshCampaigns: () => undefined, notify: () => undefined,
};

describe("Reply workflow features", () => {
  it("uses encoded campaign scoped paths and bounded pages", () => {
    expect(inboxPath("c/1", 2, "unreviewed", "meeting")).toBe(
      "/campaigns/c%2F1/replies/inbox?limit=50&offset=100&review_status=unreviewed&outcome=meeting"
    );
    expect(contactMessagePath("a/b", "member/1", 1)).toBe(
      "/campaigns/a%2Fb/contacts/member%2F1/messages?limit=25&offset=25"
    );
    expect(followupsPath("a/b", 1, "open", true)).toBe(
      "/campaigns/a%2Fb/followups?limit=50&offset=50&status=open&overdue_only=true"
    );
  });

  it("lets an operator review and schedule a follow-up without sending", () => {
    const html = renderToStaticMarkup(
      <AppContext.Provider value={context}><ReplyInbox /></AppContext.Provider>
    );
    expect(html).toContain("Reply inbox");
    expect(html).toContain("Ravi Shah");
    expect(html).toContain("Review outcome");
    expect(html).toContain("Full conversation");
    expect(html).toContain("Create follow-up");
    expect(html).not.toContain("Send now");
  });

  it("shows real conversation content but no raw provider JSON", () => {
    const html = renderToStaticMarkup(
      <ContactConversation campaignId="c1" membershipId="row-1" onClose={() => undefined} />
    );
    expect(html).toContain("Communication history");
    expect(html).toContain("Interested");
    expect(html).toContain("Can we arrange a call?");
    expect(html).not.toContain("raw_json");
  });

  it("shows task assignment and completion controls, with a no-send form", () => {
    const html = renderToStaticMarkup(
      <AppContext.Provider value={context}><Followups /></AppContext.Provider>
    );
    expect(html).toContain("Human follow-up tasks");
    expect(html).toContain("Call Ravi");
    expect(html).toContain("Complete");
    expect(html).toContain("Conversation");

    const form = renderToStaticMarkup(
      <TaskComposer campaignId="c1" onClose={() => undefined} onSaved={() => undefined} />
    );
    expect(form).toContain("Assigned to (label only)");
    expect(form).toContain("Due date and time");
    expect(form).toContain("never sends a message");
  });
});
