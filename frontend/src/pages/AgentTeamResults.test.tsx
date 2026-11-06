import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import { DelegationResultView, RoleResultView } from "./AgentTeamResults";

describe("agent-team results", () => {
  it("shows zero drafts as zero and preserves the human approval boundary", () => {
    const html = renderToStaticMarkup(<RoleResultView open={vi.fn()} value={{ role: "Poster", status: "drafts_only", drafts: { posts_created: 0, assets_considered: 0, skipped: [], warnings: [] } }} />);
    expect(html).toContain("0 posts created from 0 approved assets");
    expect(html).toContain("None were approved or published");
    expect(html).toContain("Review draft posts");
  });
  it("labels an offline strategy as rules-based rather than model-written", () => {
    const html = renderToStaticMarkup(<RoleResultView open={vi.fn()} value={{ role: "Director", status: "draft_only", plan: { source: "rules" } }} />);
    expect(html).toContain("not written by a model");
    expect(html).toContain("No campaigns were applied or activated");
  });
  it("escapes untrusted child output and labels it as findings to verify", () => {
    const html = renderToStaticMarkup(<DelegationResultView value={{ result: "Review first", children: [{ companion_id: "one", name: "Scout", result: '<img src=x alt="" onerror="alert(1)">' }] }} />);
    expect(html).not.toContain("<img");
    expect(html).toContain("&lt;img");
    expect(html).toContain("not confirmed facts");
  });
});
