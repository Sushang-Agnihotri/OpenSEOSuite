/** Minimal typed client for the backend API. The JWT lives in localStorage and is sent as a Bearer header
 *  (no cookies are used, so cross-site request forgery does not apply). */

const TOKEN_KEY = "seotk.token";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export const tokenStore = {
  get: () => localStorage.getItem(TOKEN_KEY),
  set: (t: string) => localStorage.setItem(TOKEN_KEY, t),
  clear: () => localStorage.removeItem(TOKEN_KEY),
};

let onUnauthorized: () => void = () => {};
export function setUnauthorizedHandler(fn: () => void) {
  onUnauthorized = fn;
}

function detailToMessage(detail: unknown): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((d: any) => `${(d.loc ?? []).filter((x: any) => x !== "body").join(".")}: ${d.msg}`.replace(/^: /, ""))
      .join("; ");
  }
  return "Request failed";
}

type Query = Record<string, string | number | boolean | null | undefined>;

function withQuery(path: string, query?: Query): string {
  if (!query) return path;
  const params = new URLSearchParams();
  for (const [k, v] of Object.entries(query)) {
    if (v !== undefined && v !== null && v !== "") params.set(k, String(v));
  }
  const qs = params.toString();
  return qs ? `${path}?${qs}` : path;
}

async function request<T>(method: string, path: string, body?: unknown, query?: Query): Promise<T> {
  const headers: Record<string, string> = {};
  const token = tokenStore.get();
  if (token) headers.Authorization = `Bearer ${token}`;
  let payload: BodyInit | undefined;
  if (body instanceof FormData) {
    payload = body;
  } else if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }
  let res: Response;
  try {
    res = await fetch(withQuery(`/api${path}`, query), { method, headers, body: payload });
  } catch {
    throw new ApiError(0, "Cannot reach the server. Is the backend running?");
  }
  if (res.status === 401 && token && !path.startsWith("/auth/login")) {
    tokenStore.clear();
    onUnauthorized();
  }
  if (!res.ok) {
    let message = `${res.status} ${res.statusText}`;
    try {
      const data = await res.json();
      message = detailToMessage(data.detail) || message;
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(res.status, message);
  }
  if (res.status === 204) return undefined as T;
  const type = res.headers.get("content-type") ?? "";
  return (type.includes("application/json") ? res.json() : res.text()) as Promise<T>;
}

export const api = {
  get: <T = any>(path: string, query?: Query) => request<T>("GET", path, undefined, query),
  post: <T = any>(path: string, body?: unknown, query?: Query) => request<T>("POST", path, body ?? {}, query),
  put: <T = any>(path: string, body?: unknown) => request<T>("PUT", path, body ?? {}),
  patch: <T = any>(path: string, body?: unknown) => request<T>("PATCH", path, body ?? {}),
  del: <T = any>(path: string, body?: unknown) => request<T>("DELETE", path, body),
  upload: <T = any>(path: string, file: File, query?: Query) => {
    const form = new FormData();
    form.append("file", file);
    return request<T>("POST", path, form, query);
  },
  /** Download an authenticated export and hand it to the browser as a file. */
  async download(path: string, query?: Query, fallbackName = "export"): Promise<void> {
    const token = tokenStore.get();
    const res = await fetch(withQuery(`/api${path}`, query), { headers: token ? { Authorization: `Bearer ${token}` } : {} });
    if (!res.ok) {
      let message = `${res.status} ${res.statusText}`;
      try {
        message = detailToMessage((await res.json()).detail) || message;
      } catch {
        /* ignore */
      }
      throw new ApiError(res.status, message);
    }
    const disposition = res.headers.get("content-disposition") ?? "";
    const name = /filename="?([^";]+)"?/.exec(disposition)?.[1] ?? fallbackName;
    const url = URL.createObjectURL(await res.blob());
    const a = document.createElement("a");
    a.href = url;
    a.download = name;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  },
};

export function errorMessage(e: unknown): string {
  return e instanceof Error ? e.message : "Something went wrong";
}
