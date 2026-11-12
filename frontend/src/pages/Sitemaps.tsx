import { useMutation, useQuery } from "@tanstack/react-query";
import { Download } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip as ChartTooltip, XAxis, YAxis } from "recharts";
import {
  Badge, Button, Card, chartColors, type Column, DataTable, EmptyState, ErrorBox, KeyValue, NeedsCrawl, Notice, PageHeader,
  Pagination, Spinner, Stat, StatusCode, Tabs, Url,
} from "../components/ui";
import { api } from "../lib/api";
import { useSite } from "../lib/context";
import { fmtInt, fmtPct, shortUrl, titleCase } from "../lib/format";

type TabId = "nonindexable" | "missing" | "canonical" | "notcrawled";
const PER_PAGE = 25;
const tooltipStyle = { background: "#0f172a", border: "none", borderRadius: 8, color: "#f8fafc", fontSize: 12 } as const;
const axisTick = { fontSize: 12, fill: "#94a3b8" } as const;

function Paged<T>({ rows, columns, rowKey, onRowClick, empty }: {
  rows: T[]; columns: Column<T>[]; rowKey: (r: T, i: number) => string | number; onRowClick?: (r: T) => void; empty: { title: string; description: string };
}) {
  const [page, setPage] = useState(1);
  return (
    <>
      <DataTable columns={columns} rows={rows.slice((page - 1) * PER_PAGE, page * PER_PAGE)} rowKey={rowKey} onRowClick={onRowClick}
        empty={<EmptyState title={empty.title} description={empty.description} />} />
      {rows.length > 0 && <Pagination page={page} perPage={PER_PAGE} total={rows.length} onPage={setPage} />}
    </>
  );
}

function MessageList({ items, tone }: { items: string[]; tone: "red" | "amber" }) {
  if (!items?.length) return <span className="text-slate-400">–</span>;
  return (
    <ul className="max-w-md space-y-1">
      {items.map((m, i) => (
        <li key={i} className="flex items-start gap-1.5 text-xs"><Badge tone={tone}>{tone === "red" ? "error" : "warning"}</Badge><span className="break-words">{m}</span></li>
      ))}
    </ul>
  );
}

export default function Sitemaps() {
  const { site, crawlId } = useSite();
  const navigate = useNavigate();
  const [tab, setTab] = useState<TabId>("nonindexable");
  const q = useQuery({ queryKey: ["sitemaps", crawlId], queryFn: () => api.get(`/crawls/${crawlId}/sitemaps`), enabled: !!crawlId });
  const generate = useMutation({ mutationFn: () => api.download(`/crawls/${crawlId}/sitemap.xml`, undefined, "sitemap.xml") });

  const header = (
    <PageHeader title="Sitemaps & robots.txt" description="Checks that XML sitemaps list exactly the pages you want indexed, and that robots.txt points search engines to them."
      actions={crawlId ? <Button variant="primary" icon={<Download className="h-4 w-4" />} loading={generate.isPending} onClick={() => generate.mutate()}>Generate sitemap.xml</Button> : undefined} />
  );
  if (!crawlId) return <>{header}<NeedsCrawl hasSite={!!site} running={!!site?.active_crawl} /></>;
  if (q.isLoading) return <>{header}<Spinner /></>;
  if (q.error) return <>{header}<ErrorBox error={q.error} onRetry={() => q.refetch()} /></>;

  const d = q.data ?? {};
  const files: any[] = d.files ?? [];
  const nonIndexable: any[] = d.non_indexable_in_sitemap ?? [];
  const missing: any[] = d.indexable_missing_from_sitemap ?? [];
  const mismatch: any[] = d.canonical_mismatch ?? [];
  const notCrawled: string[] = d.not_crawled ?? [];
  const robots = d.robots as any | null | undefined;
  const years = Object.entries((d.lastmod_by_year ?? {}) as Record<string, number>).sort(([a], [b]) => a.localeCompare(b)).map(([year, urls]) => ({ year, urls }));
  const base = site?.url;
  const open = (r: any) => navigate(`/pages/${crawlId}/${r.page_id}`);
  const urlCell = (r: any) => <div className="max-w-xl"><Url href={r.url} label={shortUrl(r.url, base)} /></div>;

  const fileColumns: Column<any>[] = [
    { key: "url", header: "Sitemap", render: (f) => <div className="max-w-md"><Url href={f.url} /></div> },
    { key: "status", header: "Status", render: (f) => <StatusCode code={f.status} error="not fetched" /> },
    { key: "kind", header: "Type", render: (f) => <Badge tone={f.kind === "unknown" ? "amber" : "gray"}>{f.kind === "index" ? "sitemap index" : f.kind}</Badge> },
    { key: "urls", header: "URLs", align: "right", render: (f) => fmtInt(f.url_count) },
    { key: "source", header: "Found via", render: (f) => f.source ?? "–" },
    { key: "errors", header: "Errors", render: (f) => <MessageList items={f.errors ?? []} tone="red" /> },
    { key: "warnings", header: "Warnings", render: (f) => <MessageList items={f.warnings ?? []} tone="amber" /> },
  ];

  return (
    <>
      {header}
      {generate.error ? <div className="mb-4"><ErrorBox error={generate.error} /></div> : null}

      <div className="mb-6 grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        <Stat label="Sitemap files" value={fmtInt(files.length)} tone={files.length ? undefined : "warn"} />
        <Stat label="URLs listed" value={fmtInt(d.url_count)} hint={`${fmtInt(d.urls_crawled)} of them crawled`} />
        <Stat label="With lastmod" value={fmtInt(d.with_lastmod)} hint={d.url_count ? fmtPct(d.with_lastmod / d.url_count, 0) + " of listed URLs" : undefined} />
        <Stat label="Indexable pages" value={fmtInt(d.indexable_pages)} tooltip="Indexable pages found by the crawl" />
        <Stat label="Non-indexable in sitemap" value={fmtInt(nonIndexable.length)} tone={nonIndexable.length ? "bad" : "good"} tooltip="Redirects, errors, noindex or canonicalised URLs that should not be listed" />
        <Stat label="Indexable missing" value={fmtInt(missing.length)} tone={missing.length ? "warn" : "good"} tooltip="Indexable pages not listed in any sitemap" />
      </div>

      <div className="mb-4 grid gap-4 lg:grid-cols-2">
        <Card title="robots.txt">
          {!robots ? (
            <EmptyState title="robots.txt was not checked" description="The crawl did not record a robots.txt result for this site." />
          ) : (
            <KeyValue items={[
              ["Status", <span className="flex flex-wrap items-center gap-2"><StatusCode code={robots.status} />{robots.present ? <Badge tone="green">present</Badge> : <Badge tone="amber">missing</Badge>}
                {robots.blocks_start && <Badge tone="red" title="The start URL is disallowed for the crawler's user agent">blocks start URL</Badge>}</span>],
              ["Sitemap lines", robots.sitemaps?.length ? (
                <ul className="space-y-1">{robots.sitemaps.map((s: string) => <li key={s}><Url href={s} /></li>)}</ul>
              ) : <span className="text-amber-700 dark:text-amber-300">None. Add a “Sitemap: https://…” line so crawlers can find your sitemap.</span>],
              ["Syntax errors", robots.errors?.length ? (
                <ul className="list-disc space-y-1 pl-4 text-red-700 dark:text-red-300">{robots.errors.map((e: string, i: number) => <li key={i}>{e}</li>)}</ul>
              ) : <Badge tone="green">none</Badge>],
              ["Crawl delay", robots.crawl_delay === null || robots.crawl_delay === undefined ? "Not set" : `${robots.crawl_delay} s`],
            ]} />
          )}
        </Card>
        <Card title="lastmod by year" description="How recently the listed URLs claim to have been modified">
          {years.length === 0 ? (
            <EmptyState title="No lastmod values" description="None of the listed URLs carry a <lastmod> date. Accurate lastmod values help search engines prioritise recrawling." />
          ) : (
            <div className="h-56" role="img" aria-label="Sitemap URLs by lastmod year">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={years} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#94a3b833" vertical={false} />
                  <XAxis dataKey="year" tick={axisTick} tickLine={false} axisLine={{ stroke: "#94a3b855" }} />
                  <YAxis allowDecimals={false} tick={axisTick} tickLine={false} axisLine={false} width={44} />
                  <ChartTooltip cursor={{ fill: "#94a3b822" }} contentStyle={tooltipStyle} labelStyle={{ color: "#f8fafc" }} itemStyle={{ color: "#f8fafc" }} />
                  <Bar dataKey="urls" name="URLs" fill={chartColors[0]} radius={[4, 4, 0, 0]} maxBarSize={56} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </Card>
      </div>

      <Card padded={false} title="Sitemap files" className="mb-4">
        <DataTable columns={fileColumns} rows={files} rowKey={(f, i) => `${f.url}-${i}`}
          empty={<EmptyState title="No sitemap found" description="No sitemap was discovered through robots.txt or the common /sitemap.xml locations. Use “Generate sitemap.xml” to create one from this crawl." />} />
      </Card>

      <Tabs<TabId> value={tab} onChange={setTab} tabs={[
        { id: "nonindexable", label: "Non-indexable URLs in sitemap", count: nonIndexable.length },
        { id: "missing", label: "Indexable pages missing from sitemap", count: missing.length },
        { id: "canonical", label: "Canonical mismatches", count: mismatch.length },
        { id: "notcrawled", label: "Listed but not crawled", count: notCrawled.length },
      ]} />
      <Card padded={false} className="mb-4">
        {tab === "nonindexable" && (
          <Paged rows={nonIndexable} rowKey={(r) => r.page_id} onRowClick={open}
            empty={{ title: "Sitemap is clean", description: "Every crawled URL listed in the sitemap is indexable." }}
            columns={[
              { key: "url", header: "URL", render: urlCell },
              { key: "status", header: "Status", render: (r) => <StatusCode code={r.status_code} /> },
              { key: "reason", header: "Why it is not indexable", render: (r) => (r.reason ? titleCase(String(r.reason)) : "–") },
            ]} />
        )}
        {tab === "missing" && (
          <Paged rows={missing} rowKey={(r) => r.page_id} onRowClick={open}
            empty={{ title: "Nothing missing", description: "Every indexable page found by the crawl is listed in a sitemap." }}
            columns={[
              { key: "url", header: "URL", render: urlCell },
              { key: "inlinks", header: "Inlinks", align: "right", render: (r) => fmtInt(r.inlinks) },
            ]} />
        )}
        {tab === "canonical" && (
          <Paged rows={mismatch} rowKey={(r) => r.page_id} onRowClick={open}
            empty={{ title: "No canonical mismatches", description: "Every listed URL is its own canonical." }}
            columns={[
              { key: "url", header: "URL in sitemap", render: urlCell },
              { key: "canonical", header: "Declared canonical", render: (r) => <div className="max-w-xl"><Url href={r.canonical} label={shortUrl(r.canonical, base)} /></div> },
            ]} />
        )}
        {tab === "notcrawled" && (
          <Paged rows={notCrawled.map((url) => ({ url }))} rowKey={(r, i) => `${r.url}-${i}`}
            empty={{ title: "All listed URLs were crawled", description: "The crawl visited every URL found in the sitemaps." }}
            columns={[{ key: "url", header: "URL (up to 200 shown)", render: urlCell }]} />
        )}
      </Card>
      {tab === "notcrawled" && notCrawled.length > 0 && (
        <div className="mb-4"><Notice tone="warn">These URLs were not visited, usually because the crawl's URL limit was reached or robots.txt disallows them. Raise the limit on the Crawler page to cover them.</Notice></div>
      )}

      <div className="space-y-3">
        <Notice>
          <strong>Generate sitemap.xml</strong> downloads a sitemap built from this crawl. It contains only indexable, canonical pages that answered 200. Redirects, errors, noindex pages and
          canonicalised duplicates are left out. Sites with more than 50,000 URLs are split into parts; the download is the first part.
        </Notice>
        {d.indexing_note && <Notice>{d.indexing_note}</Notice>}
      </div>
    </>
  );
}
