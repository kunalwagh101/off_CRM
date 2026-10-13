import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import { AppContext } from "../context";

vi.mock("../hooks", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../hooks")>()),
  useResource: () => ({
    data: {
      total: 127,
      items: [{ id: "one", full_name: "Asha Rao", email: "asha@example.test",
        company: "Example", title: "Lead", category: "Trade", route: "direct",
        variant_id: "A", sent_count: 0, status: "new" }],
    },
    loading: false, error: "", reload: () => undefined,
  }),
}));

import Contacts, { CONTACTS_PAGE_SIZE, contactPageBounds, contactsPagePath } from "./Contacts";

describe("A23: contacts pagination", () => {
  it("computes the correct range and never advertises a non-existent page", () => {
    expect(CONTACTS_PAGE_SIZE).toBe(100);
    expect(contactPageBounds(0, 0)).toEqual({ pages: 1, first: 0, last: 0 });
    expect(contactPageBounds(0, 527)).toEqual({ pages: 6, first: 1, last: 100 });
    expect(contactPageBounds(5, 527)).toEqual({ pages: 6, first: 501, last: 527 });
    expect(contactPageBounds(9, 101)).toEqual({ pages: 2, first: 101, last: 101 });
  });

  it("sends an offset to the existing paginated API and encodes filters", () => {
    const path = contactsPagePath("campaign-1", 5, "A & B", "waiting_followup");
    expect(path).toBe("/campaigns/campaign-1/contacts?limit=100&offset=500&search=A%20%26%20B&status=waiting_followup");
    expect(contactsPagePath("c1", -2, "", "")).toContain("offset=0");
  });

  it("shows the total, accessible page controls and the current visible range", () => {
    const html = renderToStaticMarkup(
      <AppContext.Provider value={{
        campaignId: "c1", campaigns: [], activeCampaign: { id: "c1", name: "Pilot" } as never,
        selectCampaign: () => undefined,
        createCampaign: async () => { throw new Error("not called"); },
        refreshCampaigns: () => undefined, notify: () => undefined,
      }}>
        <Contacts />
      </AppContext.Provider>,
    );
    expect(html).toContain("Showing 1–100 of 127");
    expect(html).toContain("Page 1 of 2");
    expect(html).toContain('aria-label="Contacts pages"');
    expect(html).toContain("Previous page");
    expect(html).toContain("Next page");
    expect(html).toContain("127 contacts");
  });
});
