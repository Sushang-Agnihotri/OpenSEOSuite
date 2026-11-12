import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, ChevronDown, ChevronUp, Play, Square, Trash2 } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip as ChartTooltip, XAxis, YAxis } from "recharts";
import {
  Badge, Button, Card, Checkbox, chartColors, type Column, DataTable, EmptyState, ErrorBox, ExportMenu, Field, Input, Modal, Notice,
  PageHeader, Pagination, ProgressBar, SearchInput, Select, Spinner, Stat, StatusCode, Tabs, Textarea, Url,
} from "../components/ui";
import { api } from "../lib/api";
import { type CrawlSummary, useSite } from "../lib/context";
import { fmtBytes, fmtDateTime, fmtInt, fmtMs, fmtNum, scoreColor, shortUrl, timeAgo, titleCase } from "../lib/format";

/* ------------------------------------------------------------------ crawl configuration form (shared with the Websites page) */
export type CrawlCfg = Record<string, any>;

/** Drop empty values so the backend applies its defaults, and tidy pattern lists. */
export function cleanConfig(cfg: CrawlCfg): CrawlCfg {
  const out: CrawlCfg = {};
  for (const [k, v] of Object.entries(cfg)) {
    if (v === "" || v === null || v === undefined || (typeof v === "number" && Number.isNaN(v))) continue;
    if (Array.isArray(v)) out[k] = v.map((s) => String(s).trim()).filter(Boolean);
    else if (typeof v === "string") {
      if (v.trim()) out[k] = v.trim();
    } else out[k] = v;
  }
  return out;
}

export function CrawlConfigForm({ value, onChange, advanced = false }: { value: CrawlCfg; onChange: (v: CrawlCfg) => void; advanced?: boolean }) {
  const set = (k: string, v: any) => onChange({ ...value, [k]: v });
  const num = (k: string, label: string, hint: string, min: number, max?: number, step = 1) => (
    <Field label={label} hint={hint}>
      <Input type="number" inputMode="numeric" min={min} max={max} step={step} value={value[k] ?? ""}
        onChange={(e) => set(k, e.target.value === "" ? "" : Number(e.target.value))} />
    </Field>
  );
  const flag = (k: string, label: string, hint: string) => <Checkbox label={label} hint={hint} checked={!!value[k]} onChange={(v) => set(k, v)} />;
  const patterns = (k: string, label: string, hint: string, placeholder: string) => (
    <Field label={label} hint={hint}>
      <Textarea rows={3} spellCheck={false} placeholder={placeholder} className="font-mono text-xs"
        value={(value[k] ?? []).join("\n")} onChange={(e) => set(k, e.target.value.split("\n"))} />
    </Field>
  );
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {num("max_urls", "Max URLs", "Stop after this many URLs. The server may apply a lower hard limit.", 1)}
        {num("max_depth", "Max depth", "Clicks from the start URL (0–100).", 0, 100)}
        {num("concurrency", "Concurrency", "Parallel requests (1–32). Keep low for small servers.", 1, 32)}
        {num("delay_ms", "Delay (ms)", "Pause between requests, to stay polite (0–60000).", 0, 60000, 50)}
        {advanced && num("timeout_s", "Timeout (s)", "Per-request timeout (2–120).", 2, 120)}
        {advanced && num("retries", "Retries", "Retries for failed requests (0–5).", 0, 5)}
        {advanced && num("max_external_links", "Max external links", "External links to status-check (0–20000).", 0, 20000)}
        {advanced && num("max_images", "Max images", "Images to status-check (0–5000).", 0, 5000)}
      </div>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {flag("respect_robots", "Respect robots.txt", "Skip URLs disallowed for crawlers.")}
        {flag("use_sitemaps", "Use XML sitemaps", "Discover URLs from sitemaps and audit them.")}
        {flag("include_subdomains", "Include subdomains", "Treat subdomains as part of the site.")}
        {flag("follow_nofollow", "Follow nofollow links", "Also crawl links marked rel=nofollow.")}
        {flag("check_external_links", "Check external links", "Request outbound links to find broken ones.")}
        {flag("check_images", "Check images", "Request images to find broken or oversized files.")}
        {flag("render_js", "Render JavaScript", "Needs Playwright installed on the server. Much slower.")}
      </div>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        {patterns("include_patterns", "Include patterns", "Regex, one per line. If set, only matching URLs are crawled (max 20).", "^https://example\\.com/blog/")}
        {patterns("exclude_patterns", "Exclude patterns", "Regex, one per line. Matching URLs are skipped (max 20).", "\\?sort=\n/cart")}
      </div>
      {advanced && (
        <Field label="User agent" hint="Leave empty to use the toolkit's default crawler user agent.">
          <Input value={value.user_agent ?? ""} maxLength={300} onChange={(e) => set("user_agent", e.target.value)} placeholder="Default" />
        </Field>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ small helpers */
const ACTIVE = ["queued", "running"];
const STATUS_TONE: Record<string, string> = { completed: "green", running: "blue", queued: "gray", failed: "red", cancelled: "amber" };
const STATUS_CLASS_COLOR: Record<string, string> = { "2xx": "#16a34a", "3xx": "#3866f5", "4xx": "#ea580c", "5xx": "#dc2626", error: "#991b1b", blocked: "#64748b", "1xx": "#0891b2" };
const tooltipStyle = { background: "#0f172a", border: "none", borderRadius: 8, color: "#f1f5f9", fontSize: 12 };
const axisTick = { fontSize: 11, fill: "#94a3b8" };

export function CrawlStatusBadge({ status }: { status: string }) {
  return <Badge tone={STATUS_TONE[status] ?? "gray"}>{status}</Badge>;
}

function Score({ value }: { value: number | null | undefined }) {
  if (value === null || value === undefined) return <span className="text-slate-400">–</span>;
  return <span className="font-semibold tabular-nums" style={{ color: scoreColor(value) }}>{fmtNum(value, 0)}</span>;
}

function DistChart({ data, color, vertical }: { data: { name: string; value: number }[]; color?: (name: string, i: number) => string; vertical?: boolean }) {
  if (!data.length) return <EmptyState title="No data" description="This crawl recorded nothing for this breakdown." />;
  const fill = (name: string, i: number) => (color ? color(name, i) : chartColors[0]);
  if (vertical) {
    return (
      <ResponsiveContainer width="100%" height={Math.max(160, data.length * 30 + 30)}>
        <BarChart data={data} layout="vertical" margin={{ top: 4, right: 16, bottom: 4, left: 8 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#94a3b833" horizontal={false} />
          <XAxis type="number" allowDecimals={false} tick={axisTick} />
          <YAxis type="category" dataKey="name" width={130} tick={axisTick} />
          <ChartTooltip contentStyle={tooltipStyle} cursor={{ fill: "#94a3b81a" }} />
          <Bar dataKey="value" name="URLs" radius={[0, 4, 4, 0]}>{data.map((d, i) => <Cell key={d.name} fill={fill(d.name, i)} />)}</Bar>
        </BarChart>
      </ResponsiveContainer>
    );
  }
  return (
    <ResponsiveContainer width="100%" height={240}>
      <BarChart data={data} margin={{ top: 4, right: 8, bottom: 4, left: -16 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#94a3b833" vertical={false} />
        <XAxis dataKey="name" tick={axisTick} />
        <YAxis allowDecimals={false} tick={axisTick} />
        <ChartTooltip contentStyle={tooltipStyle} cursor={{ fill: "#94a3b81a" }} />
        <Bar dataKey="value" name="URLs" radius={[4, 4, 0, 0]}>{data.map((d, i) => <Cell key={d.name} fill={fill(d.name, i)} />)}</Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

const toSeries = (obj: Record<string, number> | undefined | null) => Object.entries(obj ?? {}).map(([name, value]) => ({ name, value: Number(value) || 0 }));

/* ------------------------------------------------------------------ tabs */
function PagesTab({ crawlId, base }: { crawlId: number; base: string }) {
  const navigate = useNavigate();
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const [indexable, setIndexable] = useState("");
  const [kind, setKind] = useState("");
  const [sort, setSort] = useState("url");
  const [order, setOrder] = useState<"asc" | "desc">("asc");
  const [page, setPage] = useState(1);
  useEffect(() => setPage(1), [crawlId, q, status, indexable, kind, sort, order]);
  const query = useQuery({
    queryKey: ["crawl-pages", crawlId, q, status, indexable, kind, sort, order, page],
    queryFn: () => api.get(`/crawls/${crawlId}/pages`, { q, status, indexable, kind, sort, order, page, per_page: 50 }),
    placeholderData: keepPreviousData,
  });
  const onSort = (key: string) => {
    if (key === sort) setOrder(order === "asc" ? "desc" : "asc");
    else {
      setSort(key);
      setOrder(key === "url" ? "asc" : "desc");
    }
  };
  const columns: Column<any>[] = [
    { key: "url", header: "URL", sortKey: "url", render: (p) => (
      <div className="max-w-[26rem]">
        <div className="truncate font-medium text-slate-900 dark:text-slate-100" title={p.url}>{shortUrl(p.url, base)}</div>
        {p.title && <div className="truncate text-xs text-slate-500 dark:text-slate-400" title={p.title}>{p.title}</div>}
        {p.redirect_to && <div className="truncate text-xs text-slate-500 dark:text-slate-400" title={p.redirect_to}>→ {shortUrl(p.redirect_to, base)}</div>}
      </div>
    ) },
    { key: "status", header: "Status", sortKey: "status", render: (p) => (p.blocked_by_robots ? <Badge tone="gray" title="Blocked by robots.txt">blocked</Badge> : <StatusCode code={p.status_code} error={p.error} />) },
    { key: "indexable", header: "Indexable", render: (p) => (!p.is_html ? <span className="text-slate-400">–</span>
      : p.indexable ? <Badge tone="green">yes</Badge>
      : <span className="inline-flex items-center gap-1.5"><Badge tone="amber">no</Badge><span className="text-xs text-slate-500 dark:text-slate-400">{p.indexability_reason}</span></span>) },
    { key: "depth", header: "Depth", sortKey: "depth", align: "right", tooltip: "Clicks from the start URL", render: (p) => p.depth ?? "–" },
    { key: "inlinks", header: "Inlinks", sortKey: "inlinks", align: "right", render: (p) => fmtInt(p.inlinks) },
    { key: "words", header: "Words", sortKey: "words", align: "right", render: (p) => (p.is_html ? fmtInt(p.word_count) : "–") },
    { key: "response", header: "Response", sortKey: "response", align: "right", render: (p) => fmtMs(p.response_ms) },
    { key: "size", header: "Size", sortKey: "size", align: "right", render: (p) => fmtBytes(p.size_bytes) },
    { key: "issues", header: "Issues", sortKey: "issues", align: "right", render: (p) => (p.issue_count ? <Badge tone="amber">{p.issue_count}</Badge> : <span className="text-slate-400">0</span>) },
    { key: "score", header: "Score", sortKey: "score", align: "right", render: (p) => <Score value={p.score} /> },
  ];
  return (
    <Card padded={false}>
      <div className="flex flex-wrap items-center gap-2 border-b border-slate-100 p-3 dark:border-slate-800">
        <SearchInput value={q} onChange={setQ} placeholder="Search URL or title…" />
        <Select value={status} onChange={(e) => setStatus(e.target.value)} className="w-auto" aria-label="Status filter">
          <option value="">All statuses</option>
          {["2xx", "3xx", "4xx", "5xx", "error", "blocked"].map((s) => <option key={s} value={s}>{s}</option>)}
        </Select>
        <Select value={indexable} onChange={(e) => setIndexable(e.target.value)} className="w-auto" aria-label="Indexability filter">
          <option value="">Any indexability</option>
          <option value="true">Indexable</option>
          <option value="false">Not indexable</option>
        </Select>
        <Select value={kind} onChange={(e) => setKind(e.target.value)} className="w-auto" aria-label="Type filter">
          <option value="">All types</option>
          <option value="html">HTML pages</option>
          <option value="other">Other resources</option>
        </Select>
      </div>
      {query.isLoading ? <Spinner /> : query.error ? <div className="p-3"><ErrorBox error={query.error} onRetry={() => query.refetch()} /></div> : (
        <div className={query.isPlaceholderData ? "opacity-60 transition-opacity" : ""}>
          <DataTable columns={columns} rows={query.data.items} rowKey={(p) => p.id} dense sort={sort} order={order} onSort={onSort}
            onRowClick={(p) => navigate(`/pages/${crawlId}/${p.id}`)}
            empty={<EmptyState title="No URLs match" description="Change the search or filters to see more of this crawl." />} />
          <Pagination page={page} perPage={query.data.per_page} total={query.data.total} onPage={setPage} />
        </div>
      )}
    </Card>
  );
}

function LinksTab({ crawlId, base }: { crawlId: number; base: string }) {
  const [kind, setKind] = useState("broken");
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  useEffect(() => setPage(1), [crawlId, kind, q]);
  const query = useQuery({
    queryKey: ["crawl-links", crawlId, kind, q, page],
    queryFn: () => api.get(`/crawls/${crawlId}/links`, { kind, q, page, per_page: 50 }),
    placeholderData: keepPreviousData,
  });
  const columns: Column<any>[] = [
    { key: "source", header: "Source page", render: (l) => (
      <div className="max-w-[22rem] truncate">
        {l.source_page_id ? <Link to={`/pages/${crawlId}/${l.source_page_id}`} title={l.source_url} className="text-brand-700 hover:underline dark:text-brand-300">{shortUrl(l.source_url, base)}</Link>
          : <span title={l.source_url}>{shortUrl(l.source_url, base)}</span>}
      </div>
    ) },
    { key: "target", header: "Target", render: (l) => <div className="max-w-[22rem] truncate"><Url href={l.target_url} label={shortUrl(l.target_url, base)} className="!break-normal" /></div> },
    { key: "anchor", header: "Anchor text", render: (l) => <div className="max-w-[14rem] truncate" title={l.anchor ?? undefined}>{l.anchor || <span className="text-slate-400">(empty)</span>}</div> },
    { key: "type", header: "Type", render: (l) => <span className="inline-flex gap-1"><Badge tone={l.internal ? "blue" : "purple"}>{l.internal ? "internal" : "external"}</Badge>{l.nofollow && <Badge>nofollow</Badge>}</span> },
    { key: "status", header: "Status", tooltip: "Status of the link target. A dash means the target was not checked.", render: (l) => (l.status === null && !l.error ? <span className="text-slate-400">–</span>
      : <span className="inline-flex items-center gap-1.5"><StatusCode code={l.status} error={l.error} />{l.status === null && l.error && <span className="max-w-[10rem] truncate text-xs text-slate-500" title={l.error}>{l.error}</span>}</span>) },
  ];
  return (
    <Card padded={false}>
      <div className="flex flex-wrap items-center gap-2 border-b border-slate-100 p-3 dark:border-slate-800">
        <Select value={kind} onChange={(e) => setKind(e.target.value)} className="w-auto" aria-label="Link type">
          <option value="broken">Broken links</option>
          <option value="internal">Internal links</option>
          <option value="external">External links</option>
          <option value="redirect">Links to redirects</option>
          <option value="nofollow">Nofollow links</option>
        </Select>
        <SearchInput value={q} onChange={setQ} placeholder="Search URL or anchor…" />
      </div>
      {query.isLoading ? <Spinner /> : query.error ? <div className="p-3"><ErrorBox error={query.error} onRetry={() => query.refetch()} /></div> : (
        <div className={query.isPlaceholderData ? "opacity-60 transition-opacity" : ""}>
          <DataTable columns={columns} rows={query.data.items} rowKey={(_, i) => i} dense
            empty={<EmptyState title={kind === "broken" && !q ? "No broken links found" : "No links match"} description={kind === "broken" && !q ? "Every checked link target answered successfully in this crawl." : "Change the link type or search."} />} />
          <Pagination page={page} perPage={query.data.per_page} total={query.data.total} onPage={setPage} />
        </div>
      )}
    </Card>
  );
}

function RedirectsTab({ crawlId, base }: { crawlId: number; base: string }) {
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const query = useQuery({ queryKey: ["crawl-redirects", crawlId], queryFn: () => api.get(`/crawls/${crawlId}/redirects`) });
  useEffect(() => setPage(1), [crawlId, q]);
  const rows: any[] = useMemo(() => {
    const items: any[] = query.data?.items ?? [];
    const needle = q.trim().toLowerCase();
    return needle ? items.filter((r) => r.url.toLowerCase().includes(needle) || r.chain.some((c: string) => c.toLowerCase().includes(needle))) : items;
  }, [query.data, q]);
  if (query.isLoading) return <Card><Spinner /></Card>;
  if (query.error) return <ErrorBox error={query.error} onRetry={() => query.refetch()} />;
  const columns: Column<any>[] = [
    { key: "chain", header: "Redirect chain", render: (r) => (
      <div className="flex max-w-[44rem] flex-wrap items-center gap-x-1.5 gap-y-1 text-xs">
        <Link to={`/pages/${crawlId}/${r.page_id}`} title={r.url} className="max-w-[18rem] truncate font-medium text-brand-700 hover:underline dark:text-brand-300">{shortUrl(r.url, base)}</Link>
        {r.chain.map((c: string, i: number) => (
          <span key={i} className="inline-flex min-w-0 items-center gap-1.5">
            <ArrowRight className="h-3 w-3 shrink-0 text-slate-400" />
            <span className="max-w-[18rem] truncate" title={c}>{shortUrl(c, base)}</span>
          </span>
        ))}
      </div>
    ) },
    { key: "status", header: "Status", render: (r) => <StatusCode code={r.status_code} /> },
    { key: "hops", header: "Hops", align: "right", render: (r) => (r.hops > 1 ? <Badge tone="amber">{r.hops}</Badge> : r.hops) },
    { key: "loop", header: "Loop", render: (r) => (r.loop ? <Badge tone="red">loop</Badge> : <span className="text-slate-400">–</span>) },
    { key: "final", header: "Final status", tooltip: "Status of the last URL in the chain, when it was crawled", render: (r) => (r.final_status === null || r.final_status === undefined ? <span className="text-slate-400" title="Final URL was not crawled">–</span> : <StatusCode code={r.final_status} />) },
    { key: "inlinks", header: "Inlinks", align: "right", tooltip: "Internal links still pointing at the redirecting URL", render: (r) => fmtInt(r.inlinks) },
  ];
  return (
    <Card padded={false}>
      <div className="flex flex-wrap items-center gap-2 border-b border-slate-100 p-3 dark:border-slate-800">
        <SearchInput value={q} onChange={setQ} placeholder="Search redirects…" />
      </div>
      <DataTable columns={columns} rows={rows.slice((page - 1) * 50, page * 50)} rowKey={(r) => r.page_id} dense
        empty={<EmptyState title={q ? "No redirects match" : "No redirects found"} description={q ? "Try a different search." : "No crawled URL answered with a redirect."} />} />
      {rows.length > 0 && <Pagination page={page} perPage={50} total={rows.length} onPage={setPage} />}
    </Card>
  );
}

const DUP_LABEL: Record<string, string> = {
  duplicate_content: "Exact duplicate content", near_duplicate_content: "Near-duplicate content", title_duplicate: "Duplicate titles",
  description_duplicate: "Duplicate meta descriptions", h1_duplicate: "Duplicate H1",
};

function DuplicatesTab({ crawlId, base }: { crawlId: number; base: string }) {
  const query = useQuery({ queryKey: ["crawl-duplicates", crawlId], queryFn: () => api.get<Record<string, any[]>>(`/crawls/${crawlId}/duplicates`) });
  const [type, setType] = useState<string | null>(null);
  const [shown, setShown] = useState(20);
  const [open, setOpen] = useState<Record<string, boolean>>({});
  if (query.isLoading) return <Card><Spinner /></Card>;
  if (query.error) return <ErrorBox error={query.error} onRetry={() => query.refetch()} />;
  const data = query.data ?? {};
  const types = Object.keys(data);
  if (!types.some((t) => data[t].length)) return <Card><EmptyState title="No duplicates found" description="No indexable pages share a title, description, H1 or body content in this crawl." /></Card>;
  const current = type && data[type] ? type : types.find((t) => data[t].length) ?? types[0];
  const groups = data[current] ?? [];
  return (
    <Card padded={false}>
      <div className="flex flex-wrap gap-1.5 border-b border-slate-100 p-3 dark:border-slate-800">
        {types.map((t) => (
          <Button key={t} size="sm" variant={t === current ? "primary" : "secondary"} onClick={() => { setType(t); setShown(20); }}>
            {DUP_LABEL[t] ?? titleCase(t)} · {data[t].length}
          </Button>
        ))}
      </div>
      {!groups.length ? <EmptyState title="Nothing in this group" description="No pages were flagged for this duplicate type." /> : (
        <ul className="divide-y divide-slate-100 dark:divide-slate-800">
          {groups.slice(0, shown).map((g, i) => {
            const key = `${current}-${i}`;
            const expanded = !!open[key];
            const urls: string[] = expanded ? g.urls : g.urls.slice(0, 4);
            return (
              <li key={key} className="p-3">
                <div className="mb-1.5 flex flex-wrap items-center gap-2">
                  <Badge tone="amber">{g.count} pages</Badge>
                  <span className="min-w-0 break-words text-sm font-medium text-slate-800 dark:text-slate-200">
                    {g.value ? `“${g.value}”` : current === "near_duplicate_content" ? "Very similar body text" : "Identical body text"}
                  </span>
                </div>
                <ul className="space-y-0.5 text-sm">
                  {urls.map((u) => <li key={u} className="truncate"><Url href={u} label={shortUrl(u, base)} /></li>)}
                </ul>
                {g.urls.length > 4 && (
                  <button className="mt-1 text-xs font-medium text-brand-700 hover:underline dark:text-brand-300" onClick={() => setOpen({ ...open, [key]: !expanded })}>
                    {expanded ? "Show fewer" : `Show all ${g.urls.length}`}
                  </button>
                )}
              </li>
            );
          })}
        </ul>
      )}
      {groups.length > shown && (
        <div className="border-t border-slate-100 p-3 text-center dark:border-slate-800">
          <Button size="sm" onClick={() => setShown(shown + 20)}>Show more ({groups.length - shown} remaining)</Button>
        </div>
      )}
    </Card>
  );
}

function StructureTab({ stats }: { stats: Record<string, any> }) {
  if (!stats || !Object.keys(stats).length) return <Card><EmptyState title="No statistics" description="Statistics are computed when a crawl completes." /></Card>;
  const depth = toSeries(stats.depth_distribution).sort((a, b) => (a.name === "unreachable" ? 1 : b.name === "unreachable" ? -1 : Number(a.name) - Number(b.name)));
  const byValue = (o: any) => toSeries(o).sort((a, b) => b.value - a.value);
  const links = stats.links ?? {};
  const redirects = stats.redirects ?? {};
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
        <Stat label="URLs" value={fmtInt(stats.total_urls)} />
        <Stat label="HTML pages" value={fmtInt(stats.html_pages)} tooltip="HTML pages that answered 200" />
        <Stat label="Indexable" value={fmtInt(stats.indexable_pages)} tone="good" />
        <Stat label="Non-indexable" value={fmtInt(stats.non_indexable_pages)} tone={stats.non_indexable_pages ? "warn" : undefined} />
        <Stat label="Avg words" value={fmtInt(stats.avg_word_count)} tooltip="Average word count of indexable pages" />
        <Stat label="Avg response" value={fmtMs(stats.avg_response_ms)} />
        <Stat label="Internal links" value={fmtInt(links.internal)} />
        <Stat label="External links" value={fmtInt(links.external)} hint={`${fmtInt(links.external_checked)} checked`} />
        <Stat label="Broken links" value={fmtInt((links.broken_internal ?? 0) + (links.broken_external ?? 0))} tone={(links.broken_internal ?? 0) + (links.broken_external ?? 0) ? "bad" : "good"}
          hint={`${fmtInt(links.broken_internal)} internal · ${fmtInt(links.broken_external)} external`} />
        <Stat label="Redirects" value={fmtInt(redirects.total)} hint={`${fmtInt(redirects.chains)} chains · ${fmtInt(redirects.loops)} loops`} />
        <Stat label="With schema" value={fmtInt(stats.schema?.pages_with_schema)} tooltip="Pages carrying JSON-LD or microdata" />
        <Stat label="With hreflang" value={fmtInt(stats.hreflang_pages)} />
      </div>
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card title="Click depth" description="HTML pages by number of clicks from the start URL">
          <DistChart data={depth} color={(name) => (name === "unreachable" ? "#dc2626" : Number(name) > 4 ? "#ca8a04" : chartColors[0])} />
        </Card>
        <Card title="Status classes" description="All crawled URLs by HTTP response class">
          <DistChart data={toSeries(stats.status_classes).sort((a, b) => a.name.localeCompare(b.name))} color={(name) => STATUS_CLASS_COLOR[name] ?? "#64748b"} />
        </Card>
        <Card title="Content types" description="What the crawler received">
          <DistChart vertical data={byValue(stats.content_types)} color={(_, i) => chartColors[i % chartColors.length]} />
        </Card>
        <Card title="Why pages are not indexable" description="HTML pages excluded from indexing, by reason">
          {Object.keys(stats.non_indexable_reasons ?? {}).length
            ? <DistChart vertical data={byValue(stats.non_indexable_reasons)} color={() => "#ca8a04"} />
            : <EmptyState title="Everything is indexable" description="No HTML page was excluded from indexing." />}
        </Card>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ page */
type TabId = "pages" | "links" | "redirects" | "duplicates" | "structure";

export default function Crawler() {
  const { site, loading, refresh } = useSite();
  const qc = useQueryClient();
  const [cfg, setCfg] = useState<CrawlCfg>({});
  const [showOptions, setShowOptions] = useState(false);
  const [inspectId, setInspectId] = useState<number | null>(null);
  const [tab, setTab] = useState<TabId>("pages");
  const [toDelete, setToDelete] = useState<CrawlSummary | null>(null);
  const siteId = site?.id ?? null;
  const activeId = site?.active_crawl?.id ?? null;

  useEffect(() => {
    setCfg({ ...(site?.crawl_config ?? {}) });
    setInspectId(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [siteId]);

  const invalidateAll = () => {
    refresh();
    for (const key of ["crawls", "crawl", "dashboard", "overview"]) void qc.invalidateQueries({ queryKey: [key] });
  };

  const start = useMutation({
    mutationFn: () => api.post(`/sites/${siteId}/crawls`, cleanConfig(cfg)),
    onSuccess: invalidateAll,
  });
  const cancel = useMutation({ mutationFn: (id: number) => api.post(`/crawls/${id}/cancel`), onSuccess: invalidateAll });
  const remove = useMutation({
    mutationFn: (id: number) => api.del(`/crawls/${id}`),
    onSuccess: () => {
      setToDelete(null);
      invalidateAll();
    },
  });

  // live progress of the running crawl
  const live = useQuery({
    queryKey: ["crawl", activeId, "live"],
    queryFn: () => api.get(`/crawls/${activeId}`),
    enabled: activeId !== null,
    refetchInterval: (q) => (ACTIVE.includes(q.state.data?.status ?? "queued") ? 1500 : false),
  });
  const liveStatus: string | undefined = live.data?.status;
  useEffect(() => {
    if (liveStatus && !ACTIVE.includes(liveStatus)) invalidateAll();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [liveStatus, activeId]);
  const prevActive = useRef<number | null>(null);
  useEffect(() => {
    if (prevActive.current !== null && activeId === null) invalidateAll();
    prevActive.current = activeId;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeId]);

  const history = useQuery<CrawlSummary[]>({ queryKey: ["crawls", siteId], queryFn: () => api.get(`/sites/${siteId}/crawls`), enabled: siteId !== null });
  const crawls = history.data ?? [];
  const inspected = crawls.find((c) => c.id === inspectId && !ACTIVE.includes(c.status)) ?? crawls.find((c) => c.status === "completed") ?? null;
  const inspectedId = inspected?.id ?? null;
  const detail = useQuery({ queryKey: ["crawl", inspectedId], queryFn: () => api.get(`/crawls/${inspectedId}`), enabled: inspectedId !== null });

  if (loading) return <Spinner />;
  if (!site) {
    return (
      <>
        <PageHeader title="Crawler" description="Crawl a website to collect every URL, link, redirect and on-page element." />
        <Card><EmptyState title="Add a website first" description="The crawler works on the selected website. Add one to get started."
          action={<Link to="/sites" className="text-sm font-medium text-brand-700 hover:underline dark:text-brand-300">Go to Websites</Link>} /></Card>
      </>
    );
  }

  const job = live.data?.job;
  const stats: Record<string, any> = detail.data?.stats ?? {};
  const exportPath = `/crawls/${inspectedId}/export`;

  const historyColumns: Column<CrawlSummary>[] = [
    { key: "id", header: "Crawl", render: (c) => <span className="font-medium text-slate-900 dark:text-slate-100">#{c.id}</span> },
    { key: "status", header: "Status", render: (c) => (
      <span className="inline-flex items-center gap-1.5">
        <CrawlStatusBadge status={c.status} />
        {c.error && <span className="max-w-[16rem] truncate text-xs text-red-600 dark:text-red-400" title={c.error}>{c.error}</span>}
      </span>
    ) },
    { key: "score", header: "Score", align: "right", render: (c) => <Score value={c.score} /> },
    { key: "pages", header: "URLs", align: "right", render: (c) => fmtInt(c.pages_crawled) },
    { key: "issues", header: "Critical / high", align: "right", render: (c) => (c.issues_by_severity ? `${fmtInt(c.issues_by_severity.critical)} / ${fmtInt(c.issues_by_severity.high)}` : "–") },
    { key: "date", header: "Date", render: (c) => <span title={timeAgo(c.finished_at ?? c.created_at)}>{fmtDateTime(c.finished_at ?? c.started_at ?? c.created_at)}</span> },
    { key: "actions", header: "", align: "right", render: (c) => (
      <span className="inline-flex items-center gap-1">
        {ACTIVE.includes(c.status) ? <Button size="sm" variant="ghost" loading={cancel.isPending && cancel.variables === c.id} onClick={() => cancel.mutate(c.id)}>Cancel</Button> : (
          <>
            {c.id === inspectedId ? <Badge tone="blue">inspecting</Badge>
              : <Button size="sm" disabled={c.pages_crawled === 0} title={c.pages_crawled === 0 ? "This crawl stored no URLs" : undefined} onClick={() => setInspectId(c.id)}>Inspect</Button>}
            <Button size="sm" variant="ghost" aria-label={`Delete crawl ${c.id}`} onClick={() => { remove.reset(); setToDelete(c); }}><Trash2 className="h-4 w-4" /></Button>
          </>
        )}
      </span>
    ) },
  ];

  return (
    <>
      <PageHeader title="Crawler" description={<>Crawl <span className="font-medium text-slate-700 dark:text-slate-200">{site.url}</span> and inspect every URL, link, redirect and duplicate.</>}
        actions={inspectedId !== null && (
          <ExportMenu formats={[
            { label: "Pages (CSV)", path: exportPath, query: { dataset: "pages", format: "csv" } },
            { label: "Issues (CSV)", path: exportPath, query: { dataset: "issues", format: "csv" } },
            { label: "Links (CSV)", path: exportPath, query: { dataset: "links", format: "csv" } },
            { label: "Full workbook (Excel)", path: exportPath, query: { dataset: "all", format: "xlsx" } },
            { label: "Pages + stats (JSON)", path: exportPath, query: { dataset: "pages", format: "json" } },
          ]} />
        )} />

      <div className="space-y-4">
        {activeId !== null ? (
          <Card title={`Crawl #${activeId} in progress`} description="You can leave this page. The crawl keeps running on the server."
            actions={<Button size="sm" variant="danger" icon={<Square className="h-3.5 w-3.5" />} loading={cancel.isPending} onClick={() => cancel.mutate(activeId)}>Cancel crawl</Button>}>
            <ProgressBar value={job?.progress ?? 0} label={job?.message ?? (live.data?.status === "queued" || !live.data ? "Waiting to start…" : "Crawling…")} />
            {live.error && <div className="mt-3"><ErrorBox error={live.error} onRetry={() => live.refetch()} /></div>}
            {cancel.error && <div className="mt-3"><ErrorBox error={cancel.error} /></div>}
          </Card>
        ) : (
          <Card title="Start a crawl" description="Uses this website's saved defaults unless you change the options below."
            actions={<>
              <Button size="sm" variant="ghost" icon={showOptions ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />} onClick={() => setShowOptions(!showOptions)}>Options</Button>
              <Button size="sm" variant="primary" icon={<Play className="h-3.5 w-3.5" />} loading={start.isPending} onClick={() => start.mutate()}>Start crawl</Button>
            </>}>
            {showOptions ? <CrawlConfigForm value={cfg} onChange={setCfg} /> : (
              <div className="flex flex-wrap gap-x-5 gap-y-1 text-sm text-slate-600 dark:text-slate-300">
                <span>Up to <b className="font-semibold">{fmtInt(Number(cfg.max_urls) || 0)}</b> URLs</span>
                <span>Depth ≤ <b className="font-semibold">{cfg.max_depth ?? "–"}</b></span>
                <span><b className="font-semibold">{cfg.concurrency ?? "–"}</b> parallel requests</span>
                <span>{cfg.respect_robots ? "Respects robots.txt" : "Ignores robots.txt"}</span>
                <span>{cfg.render_js ? "JavaScript rendering on" : "No JavaScript rendering"}</span>
              </div>
            )}
            {start.error && <div className="mt-3"><ErrorBox error={start.error} /></div>}
          </Card>
        )}

        <Card title="Crawl history" description="The crawl marked “inspecting” feeds the tabs below." padded={false}>
          {history.isLoading ? <Spinner /> : history.error ? <div className="p-3"><ErrorBox error={history.error} onRetry={() => history.refetch()} /></div> : (
            <DataTable columns={historyColumns} rows={crawls} rowKey={(c) => c.id} dense
              empty={<EmptyState title="No crawls yet" description="Start the first crawl to audit this website." />} />
          )}
        </Card>

        {inspectedId !== null && (
          <section>
            <div className="mb-3 flex flex-wrap items-center gap-2">
              <h2 className="text-sm font-semibold text-slate-900 dark:text-slate-100">Crawl #{inspectedId}</h2>
              {inspected && <CrawlStatusBadge status={inspected.status} />}
              <span className="text-xs text-slate-500 dark:text-slate-400">{fmtInt(inspected?.pages_crawled)} URLs · {fmtDateTime(inspected?.finished_at ?? inspected?.created_at)}</span>
            </div>
            {stats.limit_reached && (
              <div className="mb-3"><Notice tone="warn">This crawl stopped at its URL limit, so parts of the site were not crawled. Raise “Max URLs” in the crawl options for full coverage.</Notice></div>
            )}
            {inspected && inspected.status !== "completed" && (
              <div className="mb-3"><Notice tone="warn">This crawl did not complete ({inspected.status}). The data below is partial and site-wide analysis may be missing.</Notice></div>
            )}
            <Tabs<TabId> value={tab} onChange={setTab} tabs={[
              { id: "pages", label: "Pages", count: stats.total_urls ?? null },
              { id: "links", label: "Links" },
              { id: "redirects", label: "Redirects", count: stats.redirects?.total ?? null },
              { id: "duplicates", label: "Duplicates" },
              { id: "structure", label: "Structure" },
            ]} />
            {tab === "pages" && <PagesTab crawlId={inspectedId} base={site.url} />}
            {tab === "links" && <LinksTab crawlId={inspectedId} base={site.url} />}
            {tab === "redirects" && <RedirectsTab crawlId={inspectedId} base={site.url} />}
            {tab === "duplicates" && <DuplicatesTab crawlId={inspectedId} base={site.url} />}
            {tab === "structure" && (detail.isLoading ? <Card><Spinner /></Card> : detail.error ? <ErrorBox error={detail.error} onRetry={() => detail.refetch()} /> : <StructureTab stats={stats} />)}
          </section>
        )}
      </div>

      <Modal open={toDelete !== null} onClose={() => setToDelete(null)} title={`Delete crawl #${toDelete?.id ?? ""}?`}
        footer={<>
          <Button onClick={() => setToDelete(null)}>Keep crawl</Button>
          <Button variant="danger" loading={remove.isPending} onClick={() => toDelete && remove.mutate(toDelete.id)}>Delete crawl</Button>
        </>}>
        <p className="text-sm text-slate-600 dark:text-slate-300">
          This permanently removes the crawl's {fmtInt(toDelete?.pages_crawled)} URLs, links and issues. Score history for this crawl is lost. This cannot be undone.
        </p>
        {remove.error && <div className="mt-3"><ErrorBox error={remove.error} /></div>}
      </Modal>
    </>
  );
}
