/** Render a private image without putting bearer credentials in its URL. */
import { useEffect, useState, type ImgHTMLAttributes } from "react";
import { fetchMedia, getToken } from "./api";

type ProtectedImageProps = Omit<ImgHTMLAttributes<HTMLImageElement>, "src"> & { src: string };
type Loaded = { src: string; token: string; url: string; error: string };
const MAX_IMAGE_BYTES = 32 * 1024 * 1024;

async function imageBlob(response: Response): Promise<Blob> {
  const contentLength = Number(response.headers?.get("content-length") || "0");
  if (contentLength > MAX_IMAGE_BYTES) throw new Error("Image too large to preview.");
  const declared = response.headers?.get("content-type") ?? "";
  if (declared && !/^image\/(?:png|jpeg|webp|gif)(?:\s*;|$)/i.test(declared)) {
    throw new Error("The server did not return a supported image.");
  }
  if (!response.body) {
    const blob = await response.blob();
    if (blob.size > MAX_IMAGE_BYTES) throw new Error("Image too large to preview.");
    return blob;
  }
  const reader = response.body.getReader();
  const chunks: Uint8Array<ArrayBuffer>[] = [];
  let size = 0;
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      size += value.byteLength;
      if (size > MAX_IMAGE_BYTES) throw new Error("Image too large to preview.");
      // Copy to a stable owned buffer for Blob's typed-array contract.
      chunks.push(new Uint8Array(value));
    }
  } catch (error) {
    await reader.cancel().catch(() => undefined);
    throw error;
  } finally {
    reader.releaseLock();
  }
  return new Blob(chunks, { type: declared || "application/octet-stream" });
}

export function ProtectedImage({ src, alt = "", ...props }: ProtectedImageProps) {
  const token = getToken();
  const [loaded, setLoaded] = useState<Loaded | null>(null);
  // The selected src AND token must match. Never show a previous user's image
  // even for one render after a session token changes.
  const current = loaded?.src === src && loaded.token === token ? loaded : null;

  useEffect(() => {
    if (!src || !token) return;
    const controller = new AbortController();
    let objectUrl = "";
    void (async () => {
      try {
        const response = await fetchMedia(src, { signal: controller.signal });
        if (!response.ok) {
          throw new Error(response.status === 404
            ? "This image is missing. Refresh to check it."
            : "This image could not be loaded. Refresh to retry.");
        }
        const blob = await imageBlob(response);
        if (controller.signal.aborted) return;
        objectUrl = URL.createObjectURL(blob);
        setLoaded({ src, token, url: objectUrl, error: "" });
      } catch (error) {
        if (controller.signal.aborted) return;
        setLoaded({
          src,
          token,
          url: "",
          error: error instanceof Error ? error.message : "Image preview failed."
        });
      }
    })();
    return () => {
      controller.abort();
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [src, token]);

  if (!src) return <span role="status">Image unavailable.</span>;
  // Native images cannot carry headers; cookie-only mode needs none.
  if (!token) return <img {...props} src={src} alt={alt} />;
  if (current?.error) return <span role="alert">{current.error}</span>;
  if (!current?.url) return <span role="status">Loading image…</span>;
  return <img {...props} src={current.url} alt={alt} />;
}
