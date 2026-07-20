const API_ROOT = "/api/v1";
const TOKEN_KEY = "offsetx-api-token";
export const AUTH_REQUIRED_EVENT = "offsetx-auth-required";

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export function getToken(): string {
  return sessionStorage.getItem(TOKEN_KEY) ?? "";
}

export function setToken(value: string): void {
  if (value.trim()) sessionStorage.setItem(TOKEN_KEY, value.trim());
  else sessionStorage.removeItem(TOKEN_KEY);
}

function headers(extra?: HeadersInit): Headers {
  const result = new Headers(extra);
  const token = getToken();
  if (token) result.set("Authorization", `Bearer ${token}`);
  return result;
}

async function parseResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    if (response.status === 401) window.dispatchEvent(new Event(AUTH_REQUIRED_EVENT));
    let message = `${response.status} ${response.statusText}`;
    try {
      const payload = (await response.json()) as { detail?: string | Array<{ msg: string }> };
      if (typeof payload.detail === "string") message = payload.detail;
      else if (Array.isArray(payload.detail)) message = payload.detail.map((item) => item.msg).join(", ");
    } catch {
      // Preserve the HTTP fallback.
    }
    throw new ApiError(message, response.status);
  }
  return (await response.json()) as T;
}

export const api = {
  async get<T>(path: string): Promise<T> {
    return parseResponse<T>(await fetch(`${API_ROOT}${path}`, { headers: headers(), credentials: "include" }));
  },
  async post<T>(path: string, body: unknown, idempotencyKey?: string): Promise<T> {
    const requestHeaders = headers({ "Content-Type": "application/json" });
    if (idempotencyKey) requestHeaders.set("Idempotency-Key", idempotencyKey);
    return parseResponse<T>(
      await fetch(`${API_ROOT}${path}`, {
        method: "POST",
        headers: requestHeaders,
        credentials: "include",
        body: JSON.stringify(body)
      })
    );
  },
  async patch<T>(path: string, body: unknown): Promise<T> {
    return parseResponse<T>(
      await fetch(`${API_ROOT}${path}`, {
        method: "PATCH",
        headers: headers({ "Content-Type": "application/json" }),
        credentials: "include",
        body: JSON.stringify(body)
      })
    );
  },
  async upload<T>(path: string, form: FormData): Promise<T> {
    return parseResponse<T>(
      await fetch(`${API_ROOT}${path}`, { method: "POST", headers: headers(), credentials: "include", body: form })
    );
  },
  async download(path: string, fallbackName: string): Promise<void> {
    const response = await fetch(`${API_ROOT}${path}`, { headers: headers(), credentials: "include" });
    if (!response.ok) {
      await parseResponse<never>(response);
      return;
    }
    const blob = await response.blob();
    const disposition = response.headers.get("Content-Disposition") ?? "";
    const match = disposition.match(/filename="?([^";]+)"?/i);
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = match?.[1] ?? fallbackName;
    link.click();
    URL.revokeObjectURL(link.href);
  },
  async postDownload(path: string, body: unknown, fallbackName: string): Promise<void> {
    const response = await fetch(`${API_ROOT}${path}`, {
      method: "POST",
      headers: headers({ "Content-Type": "application/json" }),
      credentials: "include",
      body: JSON.stringify(body)
    });
    if (!response.ok) {
      await parseResponse<never>(response);
      return;
    }
    const blob = await response.blob();
    const disposition = response.headers.get("Content-Disposition") ?? "";
    const match = disposition.match(/filename="?([^";]+)"?/i);
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = match?.[1] ?? fallbackName;
    link.click();
    URL.revokeObjectURL(link.href);
  }
};

export function idempotencyKey(prefix: string): string {
  return `${prefix}-${crypto.randomUUID()}`;
}
