export const fmtInt = (n: number | null | undefined) => (n === null || n === undefined ? "–" : Math.round(n).toLocaleString("en-US"));

export const fmtNum = (n: number | null | undefined, digits = 1) =>
  n === null || n === undefined ? "–" : n.toLocaleString("en-US", { maximumFractionDigits: digits });

export const fmtPct = (ratio: number | null | undefined, digits = 1) =>
  ratio === null || ratio === undefined ? "–" : `${(ratio * 100).toFixed(digits)}%`;

export function fmtBytes(bytes: number | null | undefined): string {
  if (bytes === null || bytes === undefined) return "–";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(2)} MB`;
}

export function fmtMs(ms: number | null | undefined): string {
  if (ms === null || ms === undefined) return "–";
  return ms >= 1000 ? `${(ms / 1000).toFixed(2)} s` : `${Math.round(ms)} ms`;
}

/** The API returns naive UTC timestamps; append Z so the browser converts them to local time. */
function parseDate(iso: string): Date {
  return new Date(/[zZ]|[+-]\d\d:\d\d$/.test(iso) || iso.length <= 10 ? iso : `${iso}Z`);
}

export function fmtDate(iso: string | null | undefined): string {
  if (!iso) return "–";
  return parseDate(iso).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}

export function fmtDateTime(iso: string | null | undefined): string {
  if (!iso) return "–";
  return parseDate(iso).toLocaleString(undefined, { year: "numeric", month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

export function timeAgo(iso: string | null | undefined): string {
  if (!iso) return "never";
  const s = Math.max(0, (Date.now() - parseDate(iso).getTime()) / 1000);
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)} min ago`;
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`;
  return `${Math.floor(s / 86400)} d ago`;
}

export function shortUrl(url: string, base?: string): string {
  try {
    const u = new URL(url);
    if (base && new URL(base).host === u.host) return u.pathname + u.search || "/";
    return u.host + (u.pathname === "/" ? "" : u.pathname) + u.search;
  } catch {
    return url;
  }
}

export const SEVERITIES = ["critical", "high", "medium", "low"] as const;
export type Severity = (typeof SEVERITIES)[number];

export const SEVERITY_COLOR: Record<Severity, string> = { critical: "#dc2626", high: "#ea580c", medium: "#ca8a04", low: "#64748b" };

export function scoreColor(score: number | null | undefined): string {
  if (score === null || score === undefined) return "#94a3b8";
  return score >= 85 ? "#16a34a" : score >= 65 ? "#ca8a04" : "#dc2626";
}

export const titleCase = (s: string) => s.replace(/[_-]/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
