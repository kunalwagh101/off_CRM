import { renderToStaticMarkup } from "react-dom/server";
import { expect, it } from "vitest";
import DraftedPosts from "./pages/DraftedPosts";

const actions = { busy: false, onApprove: () => {}, onSkip: () => {}, onSchedule: () => {}, emptyAction: <button>Choose a plan above</button> };
it("offers approval and skip for drafts, and a schedule retry for approved posts", () => {
  const html = renderToStaticMarkup(<DraftedPosts {...actions} posts={[
    { id: "a", caption: "First caption <safe>", platform: "local_outbox", status: "draft", asset_id: "" },
    { id: "b", caption: "Approved caption", platform: "local_outbox", status: "approved", asset_id: "" }
  ]} />);
  expect(html).toContain("First caption &lt;safe&gt;");
  expect(html).toContain("Approve &amp; schedule");
  expect(html).toContain("Skip");
  expect(html).toContain("Schedule approved post");
});
it("gives the empty review queue an actionable next step", () => {
  const html = renderToStaticMarkup(<DraftedPosts {...actions} posts={[]} />);
  expect(html).toContain("No posts waiting for review");
  expect(html).toContain("Choose a plan above");
});
it("disables consequential actions while saving", () => {
  const html = renderToStaticMarkup(<DraftedPosts {...actions} busy posts={[
    { id: "a", caption: "Caption", platform: "local_outbox", status: "draft", asset_id: "" }
  ]} />);
  expect(html.match(/disabled=""/g)).toHaveLength(2);
});
it("renders a supported video attachment as a video rather than claiming it is a kept picture", () => {
  const post = { id: "v", caption: "Video caption", platform: "local_outbox", status: "draft", asset_id: "render", media_kind: "video" as const, media_url: "/posts/v/media" };
  const html = renderToStaticMarkup(<DraftedPosts {...actions} posts={[post]} />);
  expect(html).toContain("<video");
  expect(html).not.toContain("Picture kept");
  expect(html).not.toContain("image-assets/render");
});
it("keeps missing attachments blocked without an external-review override", () => {
  const html = renderToStaticMarkup(<DraftedPosts {...actions} posts={[
    { id: "missing", caption: "Needs media", platform: "local_outbox", status: "draft", asset_id: "gone", media_error: "Attachment unavailable" }
  ]} />);
  expect(html).toContain("Attachment unavailable");
  expect(html).not.toContain("I reviewed this attachment");
  expect(html).toContain('disabled=""');
});
it("offers an explicit preview without starting media transfers for the whole queue", () => {
  const html = renderToStaticMarkup(<DraftedPosts {...actions} posts={[
    { id: "a", caption: "Picture", platform: "local_outbox", status: "draft", asset_id: "image", media_kind: "image", media_url: "/posts/a/media" },
    { id: "b", caption: "Video", platform: "local_outbox", status: "draft", asset_id: "video", media_kind: "video", media_url: "/posts/b/media" }
  ]} />);
  expect(html.match(/Preview attachment/g)).toHaveLength(2);
  expect(html).not.toContain('src="');
});
