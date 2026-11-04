import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, fetchMedia, setToken } from "./api";
import { loadAudioAssets } from "./video/audio";
import { loadAssets } from "./video/export";

const TOKEN = "test-only-sensitive-api-token";

function response(status = 200): Response {
  return {
    status,
    ok: status >= 200 && status < 300,
    statusText: status === 401 ? "Unauthorized" : "OK",
    arrayBuffer: async () => new ArrayBuffer(8),
    blob: async () => new Blob(["image"])
  } as Response;
}

beforeEach(() => {
  const values = new Map<string, string>();
  vi.stubGlobal("sessionStorage", {
    getItem: (key: string) => values.get(key) ?? null,
    setItem: (key: string, value: string) => values.set(key, value),
    removeItem: (key: string) => values.delete(key)
  });
  vi.stubGlobal("window", { dispatchEvent: vi.fn() });
  vi.stubGlobal("Event", class { constructor(readonly type: string) {} });
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("A20 authenticated binary media requests", () => {
  it("carries local token and cookie credentials for protected images", async () => {
    const request = vi.fn(async () => response());
    vi.stubGlobal("fetch", request);
    setToken(TOKEN);
    await fetchMedia("/api/v1/image-assets/img/file");
    expect(request).toHaveBeenCalledTimes(1);
    const [url, options] = request.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("/api/v1/image-assets/img/file");
    expect(options.credentials).toBe("include");
    expect(new Headers(options.headers).get("Authorization")).toBe(`Bearer ${TOKEN}`);
    expect(url).not.toContain(TOKEN);
  });

  it("keeps cookie login working without adding a bearer token", async () => {
    const request = vi.fn(async () => response());
    vi.stubGlobal("fetch", request);
    await fetchMedia("/api/v1/video-media/clip/file");
    const [, options] = request.mock.calls[0] as unknown as [string, RequestInit];
    expect(options.credentials).toBe("include");
    expect(new Headers(options.headers).has("Authorization")).toBe(false);
  });

  it("never sends a token to another origin or outside the private API path", async () => {
    const request = vi.fn(async () => response());
    vi.stubGlobal("fetch", request);
    setToken(TOKEN);
    await expect(fetchMedia("https://attacker.example/collect")).rejects.toThrow();
    await expect(fetchMedia("//attacker.example/collect")).rejects.toThrow();
    await expect(fetchMedia("/external/asset")).rejects.toThrow();
    expect(request).not.toHaveBeenCalled();
  });

  it("does not call a revoked or expired media credential a missing file", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => response(401)));
    setToken(TOKEN);
    await expect(fetchMedia("/api/v1/image-assets/img/file")).rejects.toMatchObject({
      status: 401
    } satisfies Partial<ApiError>);
    expect((window.dispatchEvent as ReturnType<typeof vi.fn>).mock.calls.length).toBe(1);
  });

  it("returns an actionable 403 instead of reporting a missing asset", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => response(403)));
    setToken(TOKEN);
    await expect(fetchMedia("/api/v1/video-media/v/file")).rejects.toMatchObject({
      status: 403
    } satisfies Partial<ApiError>);
  });

  it("sends a bearer token when decoding audio, not just for JSON API calls", async () => {
    const request = vi.fn(async () => response());
    vi.stubGlobal("fetch", request);
    vi.stubGlobal("OfflineAudioContext", class {
      decodeAudioData = async (_bytes: ArrayBuffer) => ({ sampleRate: 48000 });
    });
    setToken(TOKEN);
    const result = await loadAudioAssets(["song"], id => `/api/v1/video-media/${id}/file`, 48000);
    expect(result.missing).toEqual([]);
    expect(result.buffers.has("song")).toBe(true);
    const [, options] = request.mock.calls[0] as unknown as [string, RequestInit];
    expect(new Headers(options.headers).get("Authorization")).toBe(`Bearer ${TOKEN}`);
  });

  it("does not silently hide an expired session while decoding audio", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => response(401)));
    vi.stubGlobal("OfflineAudioContext", class {
      decodeAudioData = async (_bytes: ArrayBuffer) => ({ sampleRate: 48000 });
    });
    setToken(TOKEN);
    await expect(
      loadAudioAssets(["song"], id => `/api/v1/video-media/${id}/file`, 48000)
    ).rejects.toMatchObject({ status: 401 });
  });

  it("sends the token when decoding stills used by video preview and export", async () => {
    const request = vi.fn(async () => response());
    vi.stubGlobal("fetch", request);
    vi.stubGlobal("createImageBitmap", vi.fn(async () => ({ width: 8, height: 8 })));
    setToken(TOKEN);
    const result = await loadAssets(["still"], id => `/api/v1/image-assets/${id}/file`);
    expect(result.has("still")).toBe(true);
    const [, options] = request.mock.calls[0] as unknown as [string, RequestInit];
    expect(new Headers(options.headers).get("Authorization")).toBe(`Bearer ${TOKEN}`);
  });

  it("preserves a true 404 as missing rather than treating it as an auth failure", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => response(404)));
    setToken(TOKEN);
    const result = await loadAssets(["missing"], id => `/api/v1/image-assets/${id}/file`);
    expect(result.size).toBe(0);
  });
});
