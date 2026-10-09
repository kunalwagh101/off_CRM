import { useEffect, useState, type ReactNode } from "react";
import { Badge, Button, Panel, StatePanel } from "../components";
import { api, getToken } from "../api";

export type DraftedPost = {
  id: string; caption: string; platform: string; status: string; asset_id: string;
  media_kind?: "image" | "video"; media_url?: string; media_error?: string;
};
export type DraftedPostsProps = {
  posts: DraftedPost[]; busy: boolean; onApprove: (id: string) => void;
  onSkip: (id: string) => void; onSchedule: (id: string) => void; emptyAction: ReactNode;
};

function PostCard({ post, busy, onApprove, onSkip, onSchedule, previewing, onPreview }: Omit<DraftedPostsProps, "posts" | "emptyAction"> & { post: DraftedPost; previewing: boolean; onPreview: () => void }) {
  const [source, setSource] = useState("");
  const [ready, setReady] = useState(!post.asset_id);
  const [error, setError] = useState(post.media_error ?? "");
  useEffect(() => {
    if (!previewing || !post.asset_id || !post.media_url || post.media_error) {
      setReady(!post.asset_id);
      setSource("");
      return;
    }
    const controller = new AbortController();
    let objectUrl = "";
    setReady(false);
    setSource("");
    setError("");
    // Cookies authorize normal logins. Token installs need an authenticated
    // fetch because an img/video element cannot supply a bearer header.
    void (async () => {
      try {
        const token = getToken();
        const response = await fetch(api.url(post.media_url!), { credentials: "include", signal: controller.signal, headers: token ? { Authorization: `Bearer ${token}` } : {} });
        if (!response.ok) {
          const reference = response.headers.get("x-error-id") ?? "";
          throw new Error("The attachment could not be loaded. Review it on Image review or Video editor and refresh." + (/^E-[0-9A-F]{24}$/.test(reference) ? ` Reference: ${reference}` : ""));
        }
        const maxBytes = 32 * 1024 * 1024;
        if (Number(response.headers.get("content-length")) > maxBytes) throw new Error("This attachment is too large for a posting preview. Review it on Image review or Video editor.");
        const reader = response.body?.getReader();
        if (!reader) throw new Error("The attachment could not be read. Refresh to retry.");
        const chunks: Uint8Array<ArrayBuffer>[] = [];
        let total = 0;
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          total += value.byteLength;
          if (total > maxBytes) { await reader.cancel(); throw new Error("This attachment is too large for a posting preview. Review it on Image review or Video editor."); }
          chunks.push(value);
        }
        if (controller.signal.aborted) return;
        objectUrl = URL.createObjectURL(new Blob(chunks, { type: response.headers.get("content-type") ?? "application/octet-stream" }));
        setSource(objectUrl);
      } catch (reason) {
        if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : "Could not load the attachment. Refresh to retry.");
      }
    })();
    return () => { controller.abort(); if (objectUrl) URL.revokeObjectURL(objectUrl); };
  }, [previewing, post.asset_id, post.media_url, post.media_error]);
  return <article className="posting-draft">
    <p><Badge>{post.status}</Badge> · {post.platform === "local_outbox" ? "Local outbox" : post.platform}</p>
    <p style={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>{post.caption}</p>
    {post.asset_id ? <figure>
      {post.media_url && !post.media_error ? <Button tone="ghost" disabled={busy} onClick={onPreview}>{previewing ? "Close preview" : "Preview attachment"}</Button> : null}
      {post.media_kind === "video" ? <video controls preload="metadata" src={source || undefined} aria-label="Video attached to this post" style={{ maxWidth: "100%", maxHeight: 320 }} onLoadedData={() => setReady(true)} onError={() => { setReady(false); setError("Video preview failed. Review it on Video editor and refresh."); }} /> : post.media_kind === "image" ? <img src={source || undefined} alt="Picture attached to this post" style={{ maxWidth: "100%", maxHeight: 320 }} onLoad={() => setReady(true)} onError={() => { setReady(false); setError("Picture preview failed. Review it on Image review and refresh."); }} /> : null}
      <figcaption>{error || (!ready ? "Load and review the attachment before approving this post. Refresh to retry." : "Review the attached media and caption before approving.")}</figcaption>
      {error && !ready && !post.media_error && post.media_url ? <Button tone="ghost" disabled={busy} onClick={() => setReady(true)}>I reviewed this attachment on Image review or Video editor</Button> : null}
    </figure> : null}
    <div className="vinspector-actions">
      {post.status === "draft" ? <>
        <Button disabled={busy || !ready} onClick={() => onApprove(post.id)}>Approve &amp; schedule</Button>
        <Button tone="ghost" disabled={busy} onClick={() => onSkip(post.id)}>Skip</Button>
      </> : post.status === "approved" ? <Button disabled={busy || !ready} onClick={() => onSchedule(post.id)}>Schedule approved post</Button> : null}
    </div>
  </article>;
}

export default function DraftedPosts({ posts, emptyAction, ...actions }: DraftedPostsProps) {
  const [previewId, setPreviewId] = useState("");
  return <Panel title="Drafted posts" subtitle="Nothing goes out until you approve and schedule it.">
    {!posts.length ? <StatePanel title="No posts waiting for review" description="Start a plan above and keep its pictures on Image review. Approved pictures can become drafted posts." action={emptyAction} /> : posts.map(post => <PostCard key={post.id} post={post} {...actions} previewing={previewId === post.id} onPreview={() => setPreviewId(previous => previous === post.id ? "" : post.id)} />)}
  </Panel>;
}
