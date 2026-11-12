import { useMutation, useQuery } from "@tanstack/react-query";
import { ArrowLeft, Sparkles } from "lucide-react";
import { type ReactNode, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  Badge, Button, Card, type Column, DataTable, EmptyState, ErrorBox, KeyValue, PageHeader, ScoreRing, SearchInput, SeverityBadge, Spinner, Stat, StatusCode,
  Tabs, Url,
} from "../components/ui";
import { api } from "../lib/api";
import { useSite } from "../lib/context";
import { fmtBytes, fmtInt, fmtMs, fmtNum, shortUrl, titleCase } from "../lib/format";
import { AiResult, IssueDetails } from "./IssueDetail";

type TabId = "overview" | "issues" | "content" | "meta" | "schema" | "links";
const AI_TASKS = [
  { task: "titles", label: "Suggest titles" },
  { task: "meta_descriptions", label: "Suggest meta descriptions" },
  { task: "schema", label: "Suggest schema" },
  { task: "internal_links", label: "Internal link ideas" },
] as const;

const missing = (what = "missing") => <Badge tone="amber">{what}</Badge>;

function WithLength({ text, unit = "characters" }: { text: string | null | undefined; unit?: string }) {
  if (!text) return missing();
  return <span>{text} <span className="whitespace-nowrap text-xs text-slate-500 dark:text-slate-400">({text.length} {unit})</span></span>;
}

function TagTable({ title, tags, emptyText }: { title: string; tags: Record<string, string> | undefined; emptyText: string }) {
  const entries = Object.entries(tags ?? {});
  return (
    <Card title={title}>
      {entries.length ? <KeyValue items={entries.map(([k, v]) => [<code key={k} className="text-xs">{k}</code>, /^https?:\/\//.test(v) ? <Url key={k} href={v} /> : v] as [ReactNode, ReactNode])} />
        : <EmptyState title={`No ${title} tags`} description={emptyText} />}
    </Card>
  );
}

function LinkTable({ rows, base, kind }: { rows: any[]; base: string | undefined; kind: "in" | "out" }) {
  const [q, setQ] = useState("");
  const [shown, setShown] = useState(50);
  const needle = q.trim().toLowerCase();
  const filtered = needle ? rows.filter((r) => r.url.toLowerCase().includes(needle) || (r.anchor ?? "").toLowerCase().includes(needle)) : rows;
  const columns: Column<any>[] = [
    { key: "url", header: kind === "in" ? "Linking page" : "Target", render: (r) => <div className="max-w-[26rem] truncate"><Url href={r.url} label={shortUrl(r.url, base)} className="!break-normal" /></div> },
    { key: "anchor", header: "Anchor text", render: (r) => <div className="max-w-[16rem] truncate" title={r.anchor ?? undefined}>{r.anchor || <span className="text-slate-400">(empty)</span>}</div> },
    { key: "flags", header: "Type", render: (r) => (
      <span className="inline-flex gap-1">
        {kind === "out" && <Badge tone={r.internal ? "blue" : "purple"}>{r.internal ? "internal" : "external"}</Badge>}
        {r.nofollow ? <Badge>nofollow</Badge> : kind === "in" ? <Badge tone="green">follow</Badge> : null}
      </span>
    ) },
    ...(kind === "out" ? [{ key: "status", header: "Status", tooltip: "A dash means the target was not checked.",
      render: (r: any) => (r.status === null && !r.error ? <span className="text-slate-400">–</span> : <StatusCode code={r.status} error={r.error} />) } as Column<any>] : []),
  ];
  return (
    <Card padded={false} title={kind === "in" ? `Inlinks (${rows.length})` : `Outlinks (${rows.length})`}
      description={kind === "in" ? "Internal pages linking here (first 200)" : "Links found on this page (first 500)"}
      actions={rows.length > 8 ? <SearchInput value={q} onChange={(v) => { setQ(v); setShown(50); }} placeholder="Filter links…" /> : undefined}>
      <DataTable columns={columns} rows={filtered.slice(0, shown)} rowKey={(_, i) => i} dense
        empty={<EmptyState title={rows.length ? "No links match" : kind === "in" ? "No inlinks" : "No outlinks"}
          description={rows.length ? "Try a different filter." : kind === "in" ? "No crawled page links to this URL." : "No links were extracted from this URL."} />} />
      {filtered.length > shown && <div className="border-t border-slate-100 p-2 text-center dark:border-slate-800"><Button size="sm" onClick={() => setShown(shown + 100)}>Show more ({filtered.length - shown} remaining)</Button></div>}
    </Card>
  );
}

export default function PageDetail() {
  const { crawlId = "", pageId = "" } = useParams();
  const { site } = useSite();
  const navigate = useNavigate();
  const [tab, setTab] = useState<TabId>("overview");
  const [aiTitle, setAiTitle] = useState("AI suggestion");
  const q = useQuery({ queryKey: ["page", crawlId, pageId], queryFn: () => api.get(`/crawls/${crawlId}/pages/${pageId}`) });
  const ai = useMutation({ mutationFn: (task: string) => api.post("/ai/run", { task, crawl_id: Number(crawlId), page_id: Number(pageId) }) });

  const back = (
    <button onClick={() => navigate(-1)} className="mb-3 inline-flex items-center gap-1 text-sm font-medium text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-200">
      <ArrowLeft className="h-4 w-4" /> Back
    </button>
  );
  if (q.isLoading) return <>{back}<Spinner /></>;
  if (q.error) {
    return <>{back}<PageHeader title="Page report" /><ErrorBox error={q.error} onRetry={() => q.refetch()} />
      <p className="mt-3 text-sm text-slate-500 dark:text-slate-400">The crawl may have been deleted. <Link to="/crawler" className="font-medium text-brand-700 hover:underline dark:text-brand-300">Open the Crawler</Link> to pick another one.</p></>;
  }

  const p = q.data;
  const d: Record<string, any> = p.data ?? {};
  const base = site?.url;
  const headings: any[] = d.headings ?? [];
  const images: any[] = d.images ?? [];
  const hreflang: any[] = d.hreflang ?? [];
  const schema = p.schema ?? { types: [], findings: [], errors: 0, warnings: 0, recommendations: [] };
  const jsonldErrors: string[] = d.jsonld_errors ?? [];
  // The API's link lists replace the numeric inlinks/outlinks counters of the page row (lists are capped at 200 / 500).
  const inlinks: any[] = Array.isArray(p.inlinks) ? p.inlinks : [];
  const outlinks: any[] = Array.isArray(p.outlinks) ? p.outlinks : [];
  const capped = (n: number, cap: number) => (n >= cap ? `${cap}+` : fmtInt(n));
  const internalOut = outlinks.filter((l) => l.internal).length;
  const noAlt = images.filter((i) => i.alt === null || i.alt === "").length;

  const imageColumns: Column<any>[] = [
    { key: "src", header: "Image", render: (i) => <div className="max-w-[30rem] truncate"><Url href={i.src} label={shortUrl(i.src, base)} className="!break-normal" /></div> },
    { key: "alt", header: "Alt text", render: (i) => (i.alt === null ? missing() : i.alt === "" ? <Badge title="Empty alt marks an image as decorative">empty</Badge> : <div className="max-w-[20rem] whitespace-normal break-words">{i.alt}</div>) },
    { key: "dims", header: "Dimensions", tooltip: "Width and height attributes prevent layout shift", render: (i) => (i.has_dimensions ? <Badge tone="green">set</Badge> : <Badge tone="amber">not set</Badge>) },
    { key: "loading", header: "Loading", render: (i) => i.loading ?? <span className="text-slate-400">default</span> },
  ];

  return (
    <>
      {back}
      <PageHeader title={p.title || shortUrl(p.url, base)}
        description={<span className="inline-flex flex-wrap items-center gap-2"><Url href={p.url} />{p.blocked_by_robots ? <Badge>blocked by robots.txt</Badge> : <StatusCode code={p.status_code} error={p.error} />}
          {p.is_html && (p.indexable ? <Badge tone="green">indexable</Badge> : <Badge tone="amber">not indexable{p.indexability_reason ? `: ${p.indexability_reason}` : ""}</Badge>)}</span>} />

      <div className="mb-4 grid grid-cols-1 gap-4 lg:grid-cols-5">
        <Card className="lg:col-span-1"><div className="flex h-full items-center justify-center"><ScoreRing score={p.score} size={104} label="page score" /></div></Card>
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:col-span-4 lg:grid-cols-4">
          <Stat label="Depth" value={p.depth ?? "–"} tooltip="Clicks from the start URL. A dash means the page is not reachable through links." />
          <Stat label="Inlinks" value={capped(inlinks.length, 200)} tooltip="Internal links pointing at this URL" hint={`${capped(internalOut, 500)} internal · ${fmtInt(p.external_outlinks)} external outlinks`} />
          <Stat label="PageRank" value={fmtNum(p.pagerank, 2)} tooltip="Internal PageRank: how link equity flows inside this site (average page = 1.0). Computed from crawled internal links only; unrelated to any search engine's metric." />
          <Stat label="Words" value={p.is_html ? fmtInt(p.word_count) : "–"} />
          <Stat label="Size" value={fmtBytes(p.size_bytes)} />
          <Stat label="Response time" value={fmtMs(p.response_ms)} tone={p.response_ms > 1500 ? "warn" : undefined} />
          <Stat label="Issues" value={fmtInt(p.issue_count)} tone={p.issue_count ? "warn" : "good"} />
          <Stat label="In sitemap" value={p.in_sitemap ? "Yes" : "No"} hint={p.found_via ? `Found via ${p.found_via}` : undefined} />
        </div>
      </div>

      {p.is_html && (
        <Card className="mb-4" title="AI assistance" description="Optional. Needs an AI provider configured in Settings. Suggestions are generated from this page's crawled content.">
          <div className="flex flex-wrap gap-2">
            {AI_TASKS.map((t) => (
              <Button key={t.task} size="sm" icon={<Sparkles className="h-3.5 w-3.5" />} loading={ai.isPending && ai.variables === t.task} disabled={ai.isPending}
                onClick={() => { setAiTitle(t.label); ai.mutate(t.task); }}>{t.label}</Button>
            ))}
          </div>
          {(ai.isPending || ai.error || ai.data) && <div className="mt-3"><AiResult run={ai} title={aiTitle} /></div>}
        </Card>
      )}

      <Tabs<TabId> value={tab} onChange={setTab} tabs={[
        { id: "overview", label: "On-page" },
        { id: "issues", label: "Issues", count: p.issues.length },
        { id: "content", label: "Headings & images", count: headings.length + images.length },
        { id: "meta", label: "Social & hreflang" },
        { id: "schema", label: "Structured data", count: schema.types.length },
        { id: "links", label: "Links", count: inlinks.length + outlinks.length },
      ]} />

      {tab === "overview" && (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <Card title="On-page elements">
            {p.is_html ? (
              <KeyValue items={[
                ["Title", <span key="t"><WithLength text={p.title} />{d.title_count > 1 && <> <Badge tone="amber">{d.title_count} title tags</Badge></>}</span>],
                ["Meta description", <WithLength key="d" text={p.meta_description} />],
                ["H1", p.h1 || missing()],
                ["Canonical", p.canonical ? <span key="c" className="inline-flex flex-wrap items-center gap-1.5"><Url href={p.canonical} />{p.canonical === p.url ? <Badge tone="green">self</Badge> : <Badge tone="amber">points elsewhere</Badge>}</span> : missing("none")],
                ["Meta robots", p.meta_robots || <span key="r" className="text-slate-400">not set (index, follow)</span>],
                ["X-Robots-Tag", d.x_robots_tag || <span key="x" className="text-slate-400">not set</span>],
                ["Language", p.lang || missing()],
                ["Viewport", d.viewport || missing()],
              ]} />
            ) : <EmptyState title="Not an HTML page" description="On-page elements are only extracted from HTML documents." />}
          </Card>
          <Card title="Technical">
            <KeyValue items={[
              ["Content type", p.content_type],
              ["Redirects to", p.redirect_to ? <Url key="r" href={p.redirect_to} /> : <span key="r" className="text-slate-400">no redirect</span>],
              ["Fetch error", p.error || <span key="e" className="text-slate-400">none</span>],
              ["Charset", d.charset],
              ["Rendered with JavaScript", d.rendered === undefined ? undefined : d.rendered ? "yes" : "no"],
              ["Scripts", d.scripts === undefined ? undefined : `${fmtInt(d.scripts)} (${fmtInt(d.blocking_scripts)} render-blocking)`],
              ["Stylesheets", d.stylesheets === undefined ? undefined : fmtInt(d.stylesheets)],
              ["Pagination", d.rel_next || d.rel_prev ? [d.rel_prev && `prev: ${d.rel_prev}`, d.rel_next && `next: ${d.rel_next}`].filter(Boolean).join(" · ") : undefined],
            ]} />
          </Card>
        </div>
      )}

      {tab === "issues" && (
        <Card padded={false}>
          {!p.issues.length ? <EmptyState title="No issues on this page" description="No audit rule fired for this URL in this crawl." /> : (
            <ul className="divide-y divide-slate-100 dark:divide-slate-800">
              {p.issues.map((i: any, idx: number) => (
                <li key={`${i.id}-${idx}`} className="p-4">
                  <div className="flex flex-wrap items-center gap-2">
                    <SeverityBadge severity={i.severity} />
                    <Link to={`/audit/issues/${i.id}`} className="text-sm font-semibold text-slate-900 hover:underline dark:text-slate-100">{i.title}</Link>
                    <Badge>{titleCase(i.category)}</Badge>
                  </div>
                  <p className="mt-1.5 text-sm text-slate-600 dark:text-slate-300">{i.description}</p>
                  <p className="mt-1 text-sm text-slate-600 dark:text-slate-300"><span className="font-medium text-slate-800 dark:text-slate-200">Fix: </span>{i.fix}</p>
                  {i.details && Object.keys(i.details).length > 0 && <div className="mt-2 rounded-lg bg-slate-50 p-2.5 dark:bg-slate-800/50"><IssueDetails details={i.details} base={base} /></div>}
                </li>
              ))}
            </ul>
          )}
        </Card>
      )}

      {tab === "content" && (
        <div className="space-y-4">
          <Card title={`Heading outline (${headings.length})`}>
            {!headings.length ? <EmptyState title="No headings" description="No H1–H6 elements were found on this page." /> : (
              <ul className="space-y-1 text-sm">
                {headings.map((h, i) => (
                  <li key={i} className="flex items-start gap-2" style={{ paddingLeft: `${(Math.max(1, Math.min(6, h.level)) - 1) * 18}px` }}>
                    <span className="mt-0.5 w-7 shrink-0 rounded bg-slate-100 text-center text-[10px] font-semibold uppercase leading-5 text-slate-600 dark:bg-slate-800 dark:text-slate-300">H{h.level}</span>
                    <span className={`min-w-0 break-words ${h.level === 1 ? "font-semibold text-slate-900 dark:text-slate-100" : "text-slate-700 dark:text-slate-300"}`}>{h.text || <span className="italic text-slate-400">(empty heading)</span>}</span>
                  </li>
                ))}
              </ul>
            )}
          </Card>
          <Card title={`Images (${images.length})`} description={images.length ? `${noAlt} without alt text` : undefined} padded={false}>
            <DataTable columns={imageColumns} rows={images} rowKey={(_, i) => i} dense empty={<EmptyState title="No images" description="No <img> elements were found on this page." />} />
          </Card>
        </div>
      )}

      {tab === "meta" && (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <TagTable title="Open Graph" tags={d.og} emptyText="Without Open Graph tags, shared links get a generic preview on social platforms." />
          <TagTable title="Twitter" tags={d.twitter} emptyText="Twitter/X falls back to Open Graph tags when these are absent." />
          <Card title={`Hreflang (${hreflang.length})`} className="lg:col-span-2" padded={false}>
            <DataTable dense rows={hreflang} rowKey={(_, i) => i} empty={<EmptyState title="No hreflang annotations" description="Only needed when the page has versions in other languages or regions." />}
              columns={[
                { key: "lang", header: "Language", render: (h: any) => <Badge tone="blue">{h.lang}</Badge> },
                { key: "href", header: "Alternate URL", render: (h: any) => <span className="inline-flex flex-wrap items-center gap-1.5"><Url href={h.href} />{h.href === p.url && <Badge tone="green">self</Badge>}</span> },
              ]} />
          </Card>
        </div>
      )}

      {tab === "schema" && (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <Card title="Detected types" description={`${schema.errors} errors · ${schema.warnings} warnings`}>
            {schema.types.length || (d.microdata_types ?? []).length ? (
              <div className="flex flex-wrap gap-1.5">
                {schema.types.map((t: string) => <Badge key={t} tone="blue" title="JSON-LD">{t}</Badge>)}
                {(d.microdata_types ?? []).map((t: string) => <Badge key={`m-${t}`} tone="purple" title="Microdata">{t}</Badge>)}
              </div>
            ) : <EmptyState title="No structured data" description="No JSON-LD or microdata was found on this page." />}
          </Card>
          <Card title="Recommended types" description="Suggested from the URL and page structure">
            {schema.recommendations.length ? (
              <ul className="space-y-2 text-sm">
                {schema.recommendations.map((r: any) => <li key={r.type} className="flex flex-wrap items-center gap-2"><Badge tone="green">{r.type}</Badge><span className="text-slate-600 dark:text-slate-300">{r.reason}</span></li>)}
              </ul>
            ) : <EmptyState title="No recommendations" description="Nothing obvious is missing for this kind of page." />}
          </Card>
          <Card title="Validation findings" className="lg:col-span-2" description="Covers required and recommended properties for common rich-result types; not a full schema.org validator.">
            {schema.findings.length || jsonldErrors.length ? (
              <ul className="space-y-2 text-sm">
                {jsonldErrors.map((e, i) => <li key={`e-${i}`} className="flex items-start gap-2"><Badge tone="red">invalid JSON</Badge><span className="min-w-0 break-words text-slate-700 dark:text-slate-300">{e}</span></li>)}
                {schema.findings.map((f: any, i: number) => (
                  <li key={i} className="flex items-start gap-2">
                    <Badge tone={f.level === "warning" ? "amber" : "red"}>{f.level}</Badge>
                    <span className="min-w-0 break-words text-slate-700 dark:text-slate-300">{f.message}{f.path && f.path !== "$" && <code className="ml-1.5 text-xs text-slate-500">{f.path}</code>}</span>
                  </li>
                ))}
              </ul>
            ) : <EmptyState title="No findings" description={schema.types.length ? "The structured data on this page passed every check." : "There is no structured data to validate."} />}
          </Card>
        </div>
      )}

      {tab === "links" && (
        <div className="space-y-4">
          <LinkTable rows={inlinks} base={base} kind="in" />
          <LinkTable rows={outlinks} base={base} kind="out" />
        </div>
      )}
    </>
  );
}
