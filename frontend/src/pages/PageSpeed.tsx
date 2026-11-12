import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Gauge, Loader2, XCircle } from "lucide-react";
import { type FormEvent, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip as ChartTooltip, XAxis, YAxis } from "recharts";
import {
  Badge, Button, Card, chartColors, type Column, DataBadge, DataTable, EmptyState, ErrorBox, Field, Input, Notice, PageHeader,
  ScoreRing, Select, Spinner, Tabs, Url,
} from "../components/ui";
import { api } from "../lib/api";
import { useSite } from "../lib/context";
import { fmtBytes, fmtDateTime, fmtMs, scoreColor, shortUrl, titleCase } from "../lib/format";

const CATEGORIES: [string, string][] = [["performance", "Performance"], ["accessibility", "Accessibility"], ["best-practices", "Best practices"], ["seo", "SEO"]];
const FIELD_ORDER = ["LCP", "INP", "CLS", "FCP", "TTFB"];
const METRIC_NAME: Record<string, string> = {
  LCP: "Largest Contentful Paint", INP: "Interaction to Next Paint", CLS: "Cumulative Layout Shift", FCP: "First Contentful Paint",
  TTFB: "Time to First Byte", TBT: "Total Blocking Time", "Speed Index": "Speed Index", TTI: "Time to Interactive", "TTFB (document)": "Server response time",
};
const TOPIC_ORDER = ["images", "javascript", "css", "render-blocking", "caching", "server", "layout", "other"];
const TOPIC_LABEL: Record<string, string> = {
  images: "Images", javascript: "JavaScript", css: "CSS", "render-blocking": "Render-blocking resources", caching: "Caching & compression",
  server: "Server & network", layout: "Layout stability & page weight", other: "Other",
};
const SOURCE_LABEL: Record<string, string> = { psi_api: "PageSpeed Insights API", local_lighthouse: "Local Lighthouse" };
const tooltipStyle = { background: "#0f172a", border: "none", borderRadius: 8, color: "#f8fafc", fontSize: 12 } as const;
const axisTick = { fontSize: 12, fill: "#94a3b8" } as const;

const ratingTone = (rating: string | null | undefined) => (rating === "good" ? "green" : rating === "needs improvement" ? "amber" : rating === "poor" ? "red" : "gray");
const ratingText = (rating: string | null | undefined) =>
  rating === "good" ? "text-emerald-600 dark:text-emerald-400" : rating === "needs improvement" ? "text-amber-600 dark:text-amber-400" : rating === "poor" ? "text-red-600 dark:text-red-400" : "text-slate-900 dark:text-slate-50";
const metricValue = (label: string, value: number | null | undefined) => (value === null || value === undefined ? "–" : label === "CLS" ? value.toFixed(2) : fmtMs(value));
/** Lighthouse descriptions contain Markdown links and code ticks; show them as plain text. */
const plain = (s: string | null | undefined) => (s ?? "").replace(/\[([^\]]+)\]\([^)]+\)/g, "$1").replace(/`/g, "");

function MetricTile({ label, value, rating, sub }: { label: string; value: string; rating?: string | null; sub?: string }) {
  return (
    <div className="rounded-lg border border-slate-200 p-3 dark:border-slate-800">
      <div className="flex items-center justify-between gap-2">
        <span className="text-xs font-semibold text-slate-700 dark:text-slate-200" title={METRIC_NAME[label]}>{label}</span>
        {rating && <Badge tone={ratingTone(rating)}>{rating}</Badge>}
      </div>
      <div className={`mt-1 text-xl font-semibold tabular-nums ${ratingText(rating)}`}>{value}</div>
      <div className="mt-0.5 truncate text-xs text-slate-500 dark:text-slate-400">{sub ?? METRIC_NAME[label] ?? ""}</div>
    </div>
  );
}

function FieldData({ result }: { result: any }) {
  const page: Record<string, any> = result.field ?? {};
  const origin: Record<string, any> = result.origin_field ?? {};
  const hasPage = Object.keys(page).length > 0;
  const hasOrigin = Object.keys(origin).length > 0;
  const data = hasPage ? page : origin;
  const labels = FIELD_ORDER.filter((l) => data[l]);
  const cwvPass = ["LCP", "INP", "CLS"].every((l) => data[l]?.rating === "good");
  return (
    <Card title="Core Web Vitals: field data" description="75th percentile of real Chrome users over the last 28 days (Chrome UX Report)"
      actions={hasPage || hasOrigin ? <DataBadge kind="measured" /> : <DataBadge kind="unavailable" />}>
      {!hasPage && !hasOrigin ? (
        <EmptyState icon={<Gauge className="h-6 w-6" />} title="No field data for this page"
          description={result.source === "local_lighthouse"
            ? "Local Lighthouse runs produce lab data only. Run the test through the PageSpeed Insights API to see real-user Core Web Vitals."
            : "The Chrome UX Report only covers pages and origins with enough real-user traffic. This URL has not reached that threshold, so only lab data is shown below. Lab data is a simulation, not what your visitors experienced."} />
      ) : (
        <div className="space-y-3">
          {!hasPage && <Notice tone="warn">This URL has too little traffic for page-level field data. The values below are for the whole origin (all pages of the site).</Notice>}
          <div className="flex flex-wrap items-center gap-2 text-sm text-slate-700 dark:text-slate-300">
            {["LCP", "INP", "CLS"].every((l) => data[l]) ? (
              cwvPass ? <><CheckCircle2 className="h-4 w-4 text-emerald-600" /> Core Web Vitals assessment: <strong>passed</strong></>
                : <><XCircle className="h-4 w-4 text-red-600" /> Core Web Vitals assessment: <strong>failed</strong></>
            ) : <span className="text-slate-500 dark:text-slate-400">Not all three Core Web Vitals (LCP, INP, CLS) are available, so no pass/fail assessment is shown.</span>}
            {hasPage && result.field_overall && <Badge tone={result.field_overall === "fast" ? "green" : result.field_overall === "average" ? "amber" : "red"}>overall: {result.field_overall}</Badge>}
          </div>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-5">
            {labels.map((l) => <MetricTile key={l} label={l} value={metricValue(l, data[l].p75)} rating={data[l].rating} />)}
          </div>
        </div>
      )}
    </Card>
  );
}

function Recommendations({ recs }: { recs: any[] }) {
  const topics = TOPIC_ORDER.filter((t) => recs.some((r) => (TOPIC_ORDER.includes(r.topic) ? r.topic : "other") === t));
  const [open, setOpen] = useState<string | null>(null);
  if (!recs.length) return <EmptyState title="No performance recommendations" description="Lighthouse found no audits scoring below 90 for this page." />;
  return (
    <div className="space-y-5">
      {topics.map((topic) => {
        const group = recs.filter((r) => (TOPIC_ORDER.includes(r.topic) ? r.topic : "other") === topic);
        return (
          <section key={topic}>
            <h3 className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
              {TOPIC_LABEL[topic]} <span className="rounded-full bg-slate-100 px-1.5 text-slate-600 dark:bg-slate-800 dark:text-slate-300">{group.length}</span>
            </h3>
            <ul className="divide-y divide-slate-100 rounded-lg border border-slate-200 dark:divide-slate-800 dark:border-slate-800">
              {group.map((r) => {
                const expanded = open === r.id;
                const savings = Object.entries((r.metric_savings ?? {}) as Record<string, number>);
                return (
                  <li key={r.id} className="p-3">
                    <div className="flex flex-wrap items-start justify-between gap-2">
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2">
                          <span className="h-2 w-2 shrink-0 rounded-full" style={{ background: scoreColor(r.score === null || r.score === undefined ? null : r.score * 100) }} aria-hidden />
                          <span className="text-sm font-medium text-slate-900 dark:text-slate-100">{plain(r.title)}</span>
                        </div>
                        <p className="mt-1 text-xs leading-relaxed text-slate-600 dark:text-slate-400">{plain(r.description)}</p>
                      </div>
                      <div className="flex flex-wrap items-center gap-1">
                        {r.savings_ms ? <Badge tone="orange" title="Estimated load-time saving">save ~{fmtMs(r.savings_ms)}</Badge> : null}
                        {r.savings_bytes ? <Badge tone="orange" title="Estimated transfer-size saving">save ~{fmtBytes(r.savings_bytes)}</Badge> : null}
                        {!r.savings_ms && !r.savings_bytes && r.display ? <Badge>{r.display}</Badge> : null}
                      </div>
                    </div>
                    <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-slate-500 dark:text-slate-400">
                      {(r.expected_impact ?? []).length > 0 && (
                        <span className="flex flex-wrap items-center gap-1">Expected to improve:
                          {savings.length ? savings.map(([m, v]) => <Badge key={m} tone="blue" title={METRIC_NAME[m] ?? m}>{m}{typeof v === "number" ? ` −${m === "CLS" ? v.toFixed(2) : fmtMs(v)}` : ""}</Badge>)
                            : r.expected_impact.map((m: string) => <Badge key={m} tone="blue">{m}</Badge>)}
                        </span>
                      )}
                      {(r.items ?? []).length > 0 && (
                        <button className="font-medium text-brand-700 hover:underline dark:text-brand-300" aria-expanded={expanded} onClick={() => setOpen(expanded ? null : r.id)}>
                          {expanded ? "Hide" : "Show"} {r.items.length} affected item{r.items.length === 1 ? "" : "s"}
                        </button>
                      )}
                    </div>
                    {expanded && (
                      <ul className="mt-2 space-y-1 rounded-md bg-slate-50 p-2 text-xs dark:bg-slate-950">
                        {r.items.map((it: any, i: number) => (
                          <li key={i} className="flex flex-wrap items-start justify-between gap-2">
                            <code className="min-w-0 flex-1 break-all text-slate-700 dark:text-slate-300">{it.item}</code>
                            <span className="shrink-0 tabular-nums text-slate-500 dark:text-slate-400">
                              {[it.wasted_ms ? `−${fmtMs(it.wasted_ms)}` : null, it.wasted_bytes ? `−${fmtBytes(it.wasted_bytes)}` : null, it.total_bytes ? `${fmtBytes(it.total_bytes)} total` : null].filter(Boolean).join(" · ")}
                            </span>
                          </li>
                        ))}
                      </ul>
                    )}
                  </li>
                );
              })}
            </ul>
          </section>
        );
      })}
    </div>
  );
}

function CategoryIssues({ issues }: { issues: Record<string, any[]> }) {
  const cats = CATEGORIES.filter(([id]) => id !== "performance" && issues[id]);
  const [tab, setTab] = useState(cats[0]?.[0] ?? "accessibility");
  if (!cats.length) return null;
  const active = cats.some(([id]) => id === tab) ? tab : cats[0][0];
  const list = issues[active] ?? [];
  return (
    <Card title="Failed audits by category" description="Pass/fail checks outside the performance category">
      <Tabs value={active} onChange={setTab} tabs={cats.map(([id, label]) => ({ id, label, count: issues[id].length }))} />
      {list.length === 0 ? <Notice tone="success">No failed {titleCase(active).toLowerCase()} audits.</Notice> : (
        <ul className="divide-y divide-slate-100 dark:divide-slate-800">
          {list.map((a) => (
            <li key={a.id} className="py-2.5">
              <div className="flex items-start gap-2 text-sm font-medium text-slate-900 dark:text-slate-100"><XCircle className="mt-0.5 h-4 w-4 shrink-0 text-red-500" />{plain(a.title)}</div>
              {a.description && <p className="ml-6 mt-0.5 text-xs leading-relaxed text-slate-600 dark:text-slate-400">{plain(a.description)}</p>}
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

function Result({ result }: { result: any }) {
  const lab: Record<string, any> = result.lab ?? {};
  return (
    <div className="space-y-4">
      <Card title="Lighthouse scores"
        description={<><Url href={result.final_url ?? result.url} /> · {titleCase(result.strategy ?? "")} · {SOURCE_LABEL[result.source] ?? result.source} · {fmtDateTime(result.created_at)}{result.lighthouse_version ? ` · Lighthouse ${result.lighthouse_version}` : ""}</>}>
        {result.runtime_error && <div className="mb-4"><Notice tone="warn">Lighthouse reported a problem while loading the page: {result.runtime_error}</Notice></div>}
        <div className="grid grid-cols-2 justify-items-center gap-4 sm:grid-cols-4">
          {CATEGORIES.map(([id, label]) => (
            <div key={id} className="flex flex-col items-center gap-2 text-center">
              <ScoreRing score={result.scores?.[id]} size={104} label="/ 100" />
              <span className="text-sm font-medium text-slate-700 dark:text-slate-200">{label}</span>
            </div>
          ))}
        </div>
      </Card>
      <FieldData result={result} />
      <Card title="Lab metrics" description="Measured in one simulated page load. Useful for debugging, not a substitute for field data." actions={<DataBadge kind="measured" />}>
        {Object.keys(lab).length === 0 ? <EmptyState title="No lab metrics" description="The Lighthouse run returned no metric values." /> : (
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-7">
            {Object.entries(lab).map(([label, m]) => <MetricTile key={label} label={label} value={m.display ?? metricValue(label, m.value)} rating={m.rating} />)}
          </div>
        )}
      </Card>
      <Card title="Recommendations" description="Performance audits scoring below 90, largest estimated savings first" actions={<DataBadge kind="estimated" />}>
        <Recommendations recs={result.recommendations ?? []} />
      </Card>
      <CategoryIssues issues={result.category_issues ?? {}} />
    </div>
  );
}

export default function PageSpeed() {
  const { site } = useSite();
  const qc = useQueryClient();
  const status = useQuery({ queryKey: ["pagespeed-status"], queryFn: () => api.get("/pagespeed/status") });
  const [url, setUrl] = useState<string | null>(null);
  const [strategy, setStrategy] = useState<"mobile" | "desktop">("mobile");
  const [source, setSource] = useState<"psi" | "local">("psi");
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const resultRef = useRef<HTMLDivElement>(null);
  const effectiveUrl = url ?? site?.url ?? "";
  const siteId = site?.id;

  useEffect(() => { setUrl(null); setSelectedId(null); }, [siteId]);

  const history = useQuery({ queryKey: ["pagespeed-history", siteId ?? null], queryFn: () => api.get<any[]>("/pagespeed/history", { site_id: siteId, limit: 100 }) });
  const detail = useQuery({ queryKey: ["pagespeed-result", selectedId], queryFn: () => api.get(`/pagespeed/${selectedId}`), enabled: selectedId !== null, staleTime: Infinity });
  const run = useMutation({
    mutationFn: () => api.post("/pagespeed/run", { url: effectiveUrl.trim(), strategy, source, site_id: siteId ?? null }),
    onSuccess: (data) => {
      qc.setQueryData(["pagespeed-result", data.id], data);
      setSelectedId(data.id);
      void qc.invalidateQueries({ queryKey: ["pagespeed-history"] });
    },
  });
  useEffect(() => {
    if (!run.isPending) return;
    setElapsed(0);
    const t = setInterval(() => setElapsed((s) => s + 1), 1000);
    return () => clearInterval(t);
  }, [run.isPending]);

  const localAvailable = !!status.data?.local_lighthouse;
  useEffect(() => { if (status.data && !localAvailable && source === "local") setSource("psi"); }, [status.data, localAvailable, source]);

  const submit = (e: FormEvent) => {
    e.preventDefault();
    run.mutate();
  };

  const rows: any[] = history.data ?? [];
  const chart = [...rows].reverse().filter((r) => typeof r.scores?.performance === "number")
    .map((r) => ({ t: fmtDateTime(r.created_at), [r.strategy]: r.scores.performance, url: r.url }));
  const strategies = Array.from(new Set(rows.map((r) => r.strategy as string)));
  const scoreCell = (v: number | null | undefined) => (v === null || v === undefined ? <span className="text-slate-400">–</span> : <span className="font-medium tabular-nums" style={{ color: scoreColor(v) }}>{v}</span>);
  const columns: Column<any>[] = [
    { key: "when", header: "Tested", render: (r) => <span className={r.id === selectedId ? "font-semibold text-brand-700 dark:text-brand-300" : ""}>{fmtDateTime(r.created_at)}</span> },
    { key: "url", header: "URL", render: (r) => <span className="block max-w-xs truncate" title={r.url}>{shortUrl(r.url, site?.url)}</span> },
    { key: "strategy", header: "Device", render: (r) => <Badge>{r.strategy}</Badge> },
    { key: "source", header: "Source", render: (r) => SOURCE_LABEL[r.source] ?? r.source },
    { key: "perf", header: "Perf.", align: "right", render: (r) => scoreCell(r.scores?.performance) },
    { key: "a11y", header: "A11y", align: "right", render: (r) => scoreCell(r.scores?.accessibility) },
    { key: "bp", header: "Best pr.", align: "right", render: (r) => scoreCell(r.scores?.["best-practices"]) },
    { key: "seo", header: "SEO", align: "right", render: (r) => scoreCell(r.scores?.seo) },
    { key: "lcp", header: "LCP (lab)", align: "right", render: (r) => metricValue("LCP", r.lab?.LCP?.value) },
    { key: "cls", header: "CLS (lab)", align: "right", render: (r) => metricValue("CLS", r.lab?.CLS?.value) },
  ];

  return (
    <>
      <PageHeader title="PageSpeed" description="Lighthouse scores, real-user Core Web Vitals and prioritised performance recommendations for any URL." />

      <div className="mb-4 grid gap-4 lg:grid-cols-3">
        <Card title="Run a test" className="lg:col-span-2">
          <form onSubmit={submit} className="space-y-4">
            <div className="grid gap-3 sm:grid-cols-4">
              <Field label="URL" className="sm:col-span-4">
                <Input type="url" required value={effectiveUrl} onChange={(e) => setUrl(e.target.value)} placeholder="https://example.com/" disabled={run.isPending} />
              </Field>
              <Field label="Device" className="sm:col-span-1">
                <Select value={strategy} onChange={(e) => setStrategy(e.target.value as "mobile" | "desktop")} disabled={run.isPending}>
                  <option value="mobile">Mobile</option>
                  <option value="desktop">Desktop</option>
                </Select>
              </Field>
              <Field label="Source" className="sm:col-span-3" hint={!localAvailable && status.data ? "Local Lighthouse is not installed on the server." : undefined}>
                <Select value={source} onChange={(e) => setSource(e.target.value as "psi" | "local")} disabled={run.isPending}>
                  <option value="psi">PageSpeed Insights API (lab + field data, public URLs only)</option>
                  <option value="local" disabled={!localAvailable}>Local Lighthouse (lab data only){localAvailable ? "" : " (unavailable)"}</option>
                </Select>
              </Field>
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <Button type="submit" variant="primary" loading={run.isPending} icon={<Gauge className="h-4 w-4" />}>{run.isPending ? "Testing…" : "Run test"}</Button>
              {run.isPending && (
                <span className="inline-flex items-center gap-2 text-sm text-slate-600 dark:text-slate-300" role="status">
                  <Loader2 className="h-4 w-4 animate-spin" /> Lighthouse is loading and measuring the page. This usually takes 15 to 60 seconds ({elapsed} s).
                </span>
              )}
            </div>
            {run.error ? <ErrorBox error={run.error} onRetry={() => run.mutate()} /> : null}
          </form>
        </Card>
        <Card title="Data sources">
          {status.isLoading ? <Spinner /> : status.error ? <ErrorBox error={status.error} onRetry={() => status.refetch()} /> : (
            <div className="space-y-3 text-sm">
              <div className="flex items-center justify-between gap-2">
                <span className="text-slate-700 dark:text-slate-300">PageSpeed Insights API key</span>
                {status.data.psi_key_configured ? <Badge tone="green">configured</Badge> : <Badge tone="amber">not set</Badge>}
              </div>
              <div className="flex items-center justify-between gap-2">
                <span className="text-slate-700 dark:text-slate-300">Local Lighthouse CLI</span>
                {localAvailable ? <Badge tone="green">available</Badge> : <Badge>not installed</Badge>}
              </div>
              <ul className="list-disc space-y-1 pl-4 text-xs text-slate-500 dark:text-slate-400">
                {(status.data.notes ?? []).map((n: string, i: number) => <li key={i}>{n}</li>)}
              </ul>
              {!status.data.psi_key_configured && <Link to="/settings" className="text-xs font-medium text-brand-700 hover:underline dark:text-brand-300">Add an API key in Settings</Link>}
            </div>
          )}
        </Card>
      </div>

      <div className="mb-4 scroll-mt-4" ref={resultRef}>
        {run.isPending ? (
          <Card><Spinner label={`Running Lighthouse on ${shortUrl(effectiveUrl)}… ${elapsed} s`} /></Card>
        ) : selectedId === null ? (
          <Card><EmptyState icon={<Gauge className="h-6 w-6" />} title="No result selected" description="Run a test above, or pick an earlier run from the history below." /></Card>
        ) : detail.isLoading ? <Card><Spinner label="Loading result…" /></Card>
          : detail.error ? <ErrorBox error={detail.error} onRetry={() => detail.refetch()} />
          : detail.data ? <Result result={detail.data} /> : null}
      </div>

      <Card padded={false} title="History" description={site ? `Earlier runs for ${site.name}. Click a row to open it.` : "Your earlier runs. Click a row to open it."}>
        {history.isLoading ? <Spinner /> : history.error ? <div className="p-4"><ErrorBox error={history.error} onRetry={() => history.refetch()} /></div> : (
          <>
            {chart.length > 1 && (
              <div className="border-b border-slate-100 p-4 dark:border-slate-800">
                <div className="mb-2 text-xs font-medium uppercase tracking-wide text-slate-500 dark:text-slate-400">Performance score over time</div>
                <div className="h-56" role="img" aria-label="Performance score over time">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={chart} margin={{ top: 8, right: 16, bottom: 0, left: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#94a3b833" vertical={false} />
                      <XAxis dataKey="t" tick={axisTick} tickLine={false} axisLine={{ stroke: "#94a3b855" }} minTickGap={40} />
                      <YAxis domain={[0, 100]} tick={axisTick} tickLine={false} axisLine={false} width={36} />
                      <ChartTooltip contentStyle={tooltipStyle} labelStyle={{ color: "#f8fafc" }} itemStyle={{ color: "#f8fafc" }} />
                      {strategies.length > 1 && <Legend wrapperStyle={{ fontSize: 12 }} />}
                      {strategies.map((s, i) => (
                        <Line key={s} type="monotone" dataKey={s} name={`${titleCase(s)} performance`} stroke={chartColors[i % chartColors.length]} strokeWidth={2}
                          dot={{ r: 3 }} activeDot={{ r: 5 }} connectNulls isAnimationActive={false} />
                      ))}
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </div>
            )}
            <DataTable columns={columns} rows={rows} rowKey={(r) => r.id} dense onRowClick={(r) => { setSelectedId(r.id); resultRef.current?.scrollIntoView?.({ behavior: "smooth", block: "start" }); }}
              empty={<EmptyState title="No runs yet" description="Results of every test you run are kept here so you can track changes over time." />} />
          </>
        )}
      </Card>
    </>
  );
}
