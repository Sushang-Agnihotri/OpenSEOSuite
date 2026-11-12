import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FileDown, Play, Plus, Sparkles, Trash2, Users } from "lucide-react";
import { type FormEvent, type ReactNode, useState } from "react";
import { Link } from "react-router-dom";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip as ChartTooltip, XAxis, YAxis } from "recharts";
import {
  Badge, Button, Card, chartColors, type Column, DataBadge, DataTable, EmptyState, ErrorBox, Field, Input, NeedsCrawl, Notice, PageHeader, ProgressBar, Spinner, Stat, Url,
} from "../components/ui";
import { api, ApiError, errorMessage } from "../lib/api";
import { type Job, useJob, useSite } from "../lib/context";
import { fmtDate, fmtInt, fmtMs, fmtNum, fmtPct, shortUrl } from "../lib/format";

function Chip({ children, title }: { children: ReactNode; title?: string }) {
  return <span title={title} className="inline-flex items-center gap-1 rounded-md border border-slate-200 bg-slate-50 px-1.5 py-0.5 text-xs text-slate-700 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300">{children}</span>;
}

const METRICS: { key: string; label: string; help?: string; get: (p: any) => ReactNode }[] = [
  { key: "score", label: "Technical health score", help: "Audit score of the crawl (0-100)", get: (p) => (p.score === null || p.score === undefined ? "–" : Math.round(p.score)) },
  { key: "urls_crawled", label: "URLs crawled", help: "Limited by each crawl's URL cap", get: (p) => <>{fmtInt(p.urls_crawled)}{p.limit_reached && <span className="ml-1 text-xs text-amber-600 dark:text-amber-400" title="The crawl stopped at its URL limit">cap</span>}</> },
  { key: "indexable_pages", label: "Indexable pages", get: (p) => fmtInt(p.indexable_pages) },
  { key: "sitemap_urls", label: "Sitemap URLs", get: (p) => fmtInt(p.sitemap_urls) },
  { key: "avg_word_count", label: "Avg word count", get: (p) => fmtInt(p.avg_word_count) },
  { key: "avg_title_length", label: "Avg title length", get: (p) => fmtInt(p.avg_title_length) },
  { key: "avg_description_length", label: "Avg description length", get: (p) => fmtInt(p.avg_description_length) },
  { key: "pages_missing_description", label: "Pages missing description", get: (p) => fmtInt(p.pages_missing_description) },
  { key: "avg_internal_links_out", label: "Avg internal links out", get: (p) => fmtNum(p.avg_internal_links_out) },
  { key: "avg_h2_per_page", label: "Avg H2 per page", get: (p) => fmtNum(p.avg_h2_per_page) },
  { key: "avg_response_ms", label: "Avg response time", get: (p) => fmtMs(p.avg_response_ms) },
  { key: "critical", label: "Critical issues", get: (p) => fmtInt(p.issues_by_severity?.critical ?? 0) },
  { key: "high", label: "High issues", get: (p) => fmtInt(p.issues_by_severity?.high ?? 0) },
  { key: "crawled_at", label: "Crawled", get: (p) => fmtDate(p.crawled_at) },
];

const CHART_METRICS: [string, string][] = [
  ["score", "Health score"], ["avg_title_length", "Avg title length"], ["avg_description_length", "Avg description length"],
  ["avg_internal_links_out", "Avg internal links"], ["avg_h2_per_page", "Avg H2 / page"],
];

function AiPanel({ siteId }: { siteId: number }) {
  const run = useMutation({ mutationFn: (task: string) => api.post("/ai/run", { task, site_id: siteId }) });
  return (
    <Card title="AI analysis" description="Generated from the comparison data on this page by the AI provider you configured."
      actions={<>
        <Button size="sm" icon={<Sparkles className="h-3.5 w-3.5" />} loading={run.isPending && run.variables === "content_gaps"} disabled={run.isPending} onClick={() => run.mutate("content_gaps")}>Content gap analysis</Button>
        <Button size="sm" icon={<Sparkles className="h-3.5 w-3.5" />} loading={run.isPending && run.variables === "competitor_analysis"} disabled={run.isPending} onClick={() => run.mutate("competitor_analysis")}>Competitor summary</Button>
      </>}>
      {run.isPending ? <Spinner label="Generating…" /> : run.error ? (
        <div className="space-y-2">
          <ErrorBox error={run.error} />
          {run.error instanceof ApiError && run.error.status === 400 && (
            <p className="text-xs text-slate-500 dark:text-slate-400">AI features are optional and need a provider. <Link to="/settings" className="font-medium text-brand-700 hover:underline dark:text-brand-300">Configure it in Settings</Link>.</p>
          )}
        </div>
      ) : run.data ? (
        <div className="space-y-3">
          <div className="prose-ai whitespace-pre-wrap text-sm text-slate-700 dark:text-slate-300">{run.data.output}</div>
          <p className="border-t border-slate-100 pt-2 text-xs text-slate-500 dark:border-slate-800 dark:text-slate-400">{run.data.provider}{run.data.model ? ` · ${run.data.model}` : ""}. {run.data.grounding}</p>
        </div>
      ) : <p className="text-sm text-slate-500 dark:text-slate-400">Ask for a written summary of topical gaps or of how the crawled competitors compare.</p>}
    </Card>
  );
}

function CompetitorRow({ siteId, comp, onChanged }: { siteId: number; comp: any; onChanged: () => void }) {
  const [maxUrls, setMaxUrls] = useState(150);
  const [jobId, setJobId] = useState<number | null>(null);
  const [failure, setFailure] = useState<string | null>(null);
  const job = useJob(jobId, (j: Job) => {
    setJobId(null);
    setFailure(j.status === "failed" ? j.error ?? "The crawl failed." : j.status === "cancelled" ? "The crawl was cancelled." : null);
    onChanged();
  });
  const crawl = useMutation({
    mutationFn: () => api.post(`/sites/${siteId}/competitors/${comp.id}/crawl`, { max_urls: maxUrls }),
    onSuccess: (c) => { setFailure(null); setJobId(c.job_id ?? null); onChanged(); },
  });
  const remove = useMutation({ mutationFn: () => api.del(`/sites/${siteId}/competitors/${comp.id}`), onSuccess: onChanged });
  const running = comp.crawl_running || !!jobId;
  const validMax = Number.isInteger(maxUrls) && maxUrls >= 1 && maxUrls <= 5000;

  return (
    <li className="space-y-2 px-4 py-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm font-medium text-slate-900 dark:text-slate-100">{comp.name}</span>
            {running ? <Badge tone="blue">crawl running</Badge> : comp.profile ? <Badge tone="green">crawled {fmtDate(comp.profile.crawled_at)}</Badge> : <Badge>not crawled</Badge>}
          </div>
          <Url href={comp.url} className="text-xs" />
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <label className="flex items-center gap-1.5 text-xs text-slate-500 dark:text-slate-400">
            Max URLs
            <Input type="number" min={1} max={5000} value={maxUrls} onChange={(e) => setMaxUrls(Number(e.target.value))} className="h-8 w-20" aria-label={`Max URLs for ${comp.name}`} />
          </label>
          <Button size="sm" icon={<Play className="h-3.5 w-3.5" />} loading={crawl.isPending} disabled={running || !validMax} onClick={() => crawl.mutate()}>{comp.profile ? "Re-crawl" : "Crawl"}</Button>
          <Button size="sm" variant="ghost" aria-label={`Delete ${comp.name}`} loading={remove.isPending}
            onClick={() => { if (window.confirm(`Delete competitor "${comp.name}" and its crawl data?`)) remove.mutate(); }}>
            <Trash2 className="h-4 w-4 text-red-600 dark:text-red-400" />
          </Button>
        </div>
      </div>
      {running && <ProgressBar value={job?.progress ?? 0} label={job?.message ?? "Crawling politely (reduced concurrency)…"} />}
      {(crawl.error || remove.error || failure) && <ErrorBox error={crawl.error ?? remove.error ?? failure} />}
    </li>
  );
}

function OverlapCard({ comp, siteUrl }: { comp: any; siteUrl: string }) {
  const ov = comp.profile?.keyword_overlap;
  const opps: any[] = comp.profile?.content_opportunities ?? [];
  const [allGaps, setAllGaps] = useState(false);
  if (!ov) return null;
  const gaps: any[] = ov.gaps ?? [];
  const oppColumns: Column<any>[] = [
    { key: "page", header: "Competitor page", render: (o) => (
      <div className="max-w-md"><div className="text-slate-900 dark:text-slate-100">{o.title}</div><Url href={o.url} label={shortUrl(o.url, comp.url)} className="text-xs" /></div>
    ) },
    { key: "topics", header: "Topics you lack", render: (o) => <span className="flex max-w-sm flex-wrap gap-1">{(o.topics_you_lack ?? []).map((t: string) => <Chip key={t}>{t}</Chip>)}</span> },
    { key: "pr", header: "Internal PageRank", align: "right", tooltip: "Importance of the page within the competitor's own internal link graph, computed from our crawl",
      render: (o) => (o.internal_pagerank === null || o.internal_pagerank === undefined ? "–" : fmtNum(o.internal_pagerank, 4)) },
  ];
  return (
    <Card padded={false} title={<span className="inline-flex flex-wrap items-center gap-2">Topical overlap with {comp.name} <DataBadge kind="measured" /></span>} description={<Url href={comp.url} />}>
      <div className="space-y-4 p-4">
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <Stat label="Shared terms" value={fmtInt(ov.shared_terms)} />
          <Stat label="Overlap share" value={fmtPct(ov.overlap_share)} tooltip="Shared terms divided by all distinct terms on both sites" />
          <Stat label="Gap terms" value={fmtInt(gaps.length)} hint="They cover, you do not" />
          <Stat label="Your unique terms" value={fmtInt((ov.your_unique_terms ?? []).length)} hint="You cover, they do not" />
        </div>
        <Notice>{ov.method}</Notice>
        <div>
          <div className="mb-1.5 text-xs font-medium uppercase tracking-wide text-slate-500 dark:text-slate-400">Gaps: terms on 2+ of their pages, absent from your titles and H1s</div>
          {gaps.length ? (
            <div className="flex flex-wrap gap-1">
              {(allGaps ? gaps : gaps.slice(0, 30)).map((g) => <Chip key={g.term} title={`${g.competitor_pages} competitor pages`}>{g.term} <span className="font-semibold tabular-nums">{g.competitor_pages}</span></Chip>)}
              {gaps.length > 30 && <button className="text-xs font-medium text-brand-700 hover:underline dark:text-brand-300" onClick={() => setAllGaps((a) => !a)}>{allGaps ? "Show fewer" : `+${gaps.length - 30} more`}</button>}
            </div>
          ) : <span className="text-sm text-slate-500 dark:text-slate-400">No gap terms found.</span>}
        </div>
        <div className="grid gap-4 md:grid-cols-2">
          <div>
            <div className="mb-1.5 text-xs font-medium uppercase tracking-wide text-slate-500 dark:text-slate-400">Your unique terms</div>
            {(ov.your_unique_terms ?? []).length ? <div className="flex flex-wrap gap-1">{ov.your_unique_terms.map((g: any) => <Chip key={g.term} title={`${g.your_pages} of your pages`}>{g.term} <span className="font-semibold tabular-nums">{g.your_pages}</span></Chip>)}</div>
              : <span className="text-sm text-slate-500 dark:text-slate-400">None.</span>}
          </div>
          <div>
            <div className="mb-1.5 text-xs font-medium uppercase tracking-wide text-slate-500 dark:text-slate-400">Top shared terms</div>
            {(ov.top_shared ?? []).length ? <div className="flex flex-wrap gap-1">{ov.top_shared.map((t: string) => <Chip key={t}>{t}</Chip>)}</div>
              : <span className="text-sm text-slate-500 dark:text-slate-400">None.</span>}
          </div>
        </div>
      </div>
      <div className="border-t border-slate-100 dark:border-slate-800">
        <div className="px-4 py-3">
          <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">Content opportunities</h3>
          <p className="text-xs text-slate-500 dark:text-slate-400">Their most internally linked pages covering topics missing from your titles and H1s ({shortUrl(siteUrl)}).</p>
        </div>
        <DataTable dense columns={oppColumns} rows={opps} rowKey={(o) => o.url}
          empty={<EmptyState title="No content opportunities" description="No competitor page covers a two-word topic that is missing from your site." />} />
      </div>
    </Card>
  );
}

export default function Competitors() {
  const { site } = useSite();
  const qc = useQueryClient();
  const siteId = site?.id;
  const [name, setName] = useState("");
  const [url, setUrl] = useState("");
  const [pdfBusy, setPdfBusy] = useState(false);
  const [pdfError, setPdfError] = useState<string | null>(null);

  const q = useQuery({
    queryKey: ["competitors", siteId],
    queryFn: () => api.get(`/sites/${siteId}/competitors`),
    enabled: !!siteId,
    refetchInterval: (query) => ((query.state.data?.competitors ?? []).some((c: any) => c.crawl_running) ? 4000 : false),
  });
  const refresh = () => void qc.invalidateQueries({ queryKey: ["competitors", siteId] });
  const add = useMutation({
    mutationFn: () => api.post(`/sites/${siteId}/competitors`, { name: name.trim() || null, url: url.trim() }),
    onSuccess: () => { setName(""); setUrl(""); refresh(); },
  });

  if (!site) return <NeedsCrawl hasSite={false} />;

  const data = q.data;
  const own = data?.site?.profile ?? null;
  const competitors: any[] = data?.competitors ?? [];
  const profiled = competitors.filter((c) => c.profile);
  const columnsData: { name: string; profile: any; own?: boolean }[] = [
    ...(own ? [{ name: data.site.name, profile: own, own: true }] : []),
    ...profiled.map((c) => ({ name: c.name, profile: c.profile })),
  ];
  const chartData = CHART_METRICS.map(([key, label]) => {
    const row: Record<string, any> = { metric: label };
    columnsData.forEach((c, i) => { row[`s${i}`] = c.profile[key] ?? 0; });
    return row;
  });
  const submit = (e: FormEvent) => { e.preventDefault(); if (url.trim()) add.mutate(); };
  const downloadPdf = async () => {
    setPdfBusy(true);
    setPdfError(null);
    try {
      await api.download(`/sites/${site.id}/competitors/report.pdf`, undefined, "competitors.pdf");
    } catch (e) {
      setPdfError(errorMessage(e));
    } finally {
      setPdfBusy(false);
    }
  };

  return (
    <div>
      <PageHeader title="Competitors"
        description="Crawl competitor sites with the same crawler used for your own site and compare what is measurable: structure, content depth, metadata and topical coverage."
        actions={<Button icon={<FileDown className="h-4 w-4" />} loading={pdfBusy} disabled={!data || (!own && !profiled.length)} onClick={downloadPdf}>Download PDF</Button>} />

      <div className="space-y-4">
        {pdfError && <ErrorBox error={pdfError} />}
        {q.isLoading ? <Card><Spinner /></Card> : q.error ? <ErrorBox error={q.error} onRetry={() => q.refetch()} /> : data && (
          <>
            {(data.notes ?? []).length > 0 && (
              <Notice><ul className="list-disc space-y-0.5 pl-5">{data.notes.map((n: string) => <li key={n}>{n}</li>)}</ul></Notice>
            )}

            {!own && (
              <Card>
                <EmptyState title="Crawl your own site first"
                  description={`Comparisons, topical overlap and content opportunities need a completed crawl of ${site.name}. You can already add competitors and crawl them below.`}
                  action={<Link to="/crawler" className="text-sm font-medium text-brand-700 hover:underline dark:text-brand-300">Go to Crawler</Link>} />
              </Card>
            )}

            <Card padded={false} title={`Competitors (${competitors.length} / 10)`} description="Competitor crawls skip external-link and image checks and run with reduced concurrency.">
              <form onSubmit={submit} className="flex flex-col gap-2 border-b border-slate-100 p-4 sm:flex-row sm:items-end dark:border-slate-800">
                <Field label="Name (optional)" className="sm:w-56">
                  <Input maxLength={255} value={name} onChange={(e) => setName(e.target.value)} placeholder="Defaults to the domain" />
                </Field>
                <Field label="Competitor URL" className="flex-1">
                  <Input required minLength={3} maxLength={2048} value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://competitor.example" />
                </Field>
                <Button type="submit" variant="primary" icon={<Plus className="h-4 w-4" />} loading={add.isPending} disabled={!url.trim() || competitors.length >= 10}>Add competitor</Button>
              </form>
              {add.error && <div className="p-4 pb-0"><ErrorBox error={add.error} /></div>}
              {competitors.length ? (
                <ul className="divide-y divide-slate-100 dark:divide-slate-800">
                  {competitors.map((c) => <CompetitorRow key={c.id} siteId={site.id} comp={c} onChanged={refresh} />)}
                </ul>
              ) : <EmptyState icon={<Users className="h-6 w-6" />} title="No competitors yet" description="Add the URL of a site you compete with, then crawl it to build its profile." />}
            </Card>

            {columnsData.length > 0 && (
              <Card padded={false} title={<span className="inline-flex items-center gap-2">Comparison <DataBadge kind="measured" /></span>}
                description="Every value is measured by this toolkit's crawler on the indexable pages it reached.">
                <div className="overflow-x-auto">
                  <table className="w-full min-w-max border-collapse text-left text-sm">
                    <thead>
                      <tr className="border-b border-slate-200 bg-slate-50 text-xs uppercase tracking-wide text-slate-500 dark:border-slate-800 dark:bg-slate-900/60 dark:text-slate-400">
                        <th className="px-3 py-2 font-medium">Metric</th>
                        {columnsData.map((c, i) => (
                          <th key={i} className="px-3 py-2 text-right font-medium">
                            <span className="inline-flex items-center gap-1.5">
                              <span className="h-2 w-2 rounded-full" style={{ background: chartColors[i % chartColors.length] }} />
                              {c.name}{c.own && <Badge tone="blue">you</Badge>}
                            </span>
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {METRICS.map((m) => (
                        <tr key={m.key} className="border-b border-slate-100 last:border-0 dark:border-slate-800/70">
                          <td className="px-3 py-2 text-slate-600 dark:text-slate-300" title={m.help}>{m.label}</td>
                          {columnsData.map((c, i) => (
                            <td key={i} className={`px-3 py-2 text-right tabular-nums ${c.own ? "font-semibold text-slate-900 dark:text-slate-100" : "text-slate-700 dark:text-slate-300"}`}>{m.get(c.profile)}</td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Card>
            )}

            {columnsData.length > 1 && (
              <Card title="Side by side" description="Health score, metadata lengths (characters) and per-page averages">
                <ResponsiveContainer width="100%" height={300}>
                  <BarChart data={chartData} margin={{ top: 8, right: 8, left: -12, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#94a3b833" vertical={false} />
                    <XAxis dataKey="metric" tick={{ fontSize: 11, fill: "#94a3b8" }} interval={0} tickLine={false} />
                    <YAxis tick={{ fontSize: 11, fill: "#94a3b8" }} tickLine={false} axisLine={false} />
                    <ChartTooltip cursor={{ fill: "#94a3b81a" }} contentStyle={{ background: "#0f172a", border: "none", borderRadius: 8, color: "#f8fafc", fontSize: 12 }} />
                    <Legend wrapperStyle={{ fontSize: 12 }} />
                    {columnsData.map((c, i) => <Bar key={i} dataKey={`s${i}`} name={c.name} fill={chartColors[i % chartColors.length]} radius={[3, 3, 0, 0]} maxBarSize={28} />)}
                  </BarChart>
                </ResponsiveContainer>
              </Card>
            )}

            {own && profiled.map((c) => <OverlapCard key={c.id} comp={c} siteUrl={site.url} />)}
            {own && competitors.length > 0 && !profiled.length && (
              <Card><EmptyState title="No competitor has been crawled yet" description="Press Crawl next to a competitor. Overlap and content opportunities appear when its crawl completes." /></Card>
            )}

            {(own || profiled.length > 0) && <AiPanel siteId={site.id} />}
          </>
        )}
      </div>
    </div>
  );
}
