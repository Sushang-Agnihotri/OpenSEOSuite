import { useQuery } from "@tanstack/react-query";
import { Bell, Globe, Loader2, Plus } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";
import {
  Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart, Pie, PieChart, ResponsiveContainer, Tooltip as ChartTooltip, XAxis, YAxis,
} from "recharts";
import { Badge, Button, Card, chartColors, EmptyState, ErrorBox, PageHeader, ProgressBar, ScoreRing, SeverityBadge, Spinner, Stat } from "../components/ui";
import { api } from "../lib/api";
import { type Site, useSite } from "../lib/context";
import { fmtDate, fmtInt, fmtNum, SEVERITIES, SEVERITY_COLOR, timeAgo, titleCase } from "../lib/format";

const tooltipStyle = { background: "#0f172a", border: "none", borderRadius: 8, color: "#f1f5f9", fontSize: 12 };
const axisTick = { fontSize: 11, fill: "#94a3b8" };
const STATUS_CLASS_COLOR: Record<string, string> = { "2xx": "#16a34a", "3xx": "#3866f5", "4xx": "#ea580c", "5xx": "#dc2626", error: "#991b1b", blocked: "#64748b" };
const JOB_TONE: Record<string, string> = { completed: "green", running: "blue", queued: "gray", failed: "red", cancelled: "amber" };
const linkClass = "text-sm font-medium text-brand-700 hover:underline dark:text-brand-300";

function SiteCard({ s, selected, onSelect }: { s: Site; selected: boolean; onSelect: () => void }) {
  const sev = s.last_crawl?.issues_by_severity;
  return (
    <div className={`rounded-xl border bg-white p-4 shadow-sm transition dark:bg-slate-900 ${selected ? "border-brand-500 ring-1 ring-brand-500/30 dark:border-brand-400" : "border-slate-200 dark:border-slate-800"}`}>
      <div className="flex items-start gap-4">
        <ScoreRing score={s.last_crawl?.score} size={76} />
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <h3 className="truncate text-sm font-semibold text-slate-900 dark:text-slate-100">{s.name}</h3>
            {selected && <Badge tone="blue">selected</Badge>}
          </div>
          <div className="truncate text-xs text-slate-500 dark:text-slate-400">{s.domain}</div>
          <div className="mt-2 flex flex-wrap gap-1">
            {sev ? SEVERITIES.map((k) => (
              <span key={k} title={`${k} issues`} className="inline-flex items-center gap-1 rounded-md bg-slate-100 px-1.5 py-0.5 text-xs tabular-nums text-slate-700 dark:bg-slate-800 dark:text-slate-300">
                <span className="h-1.5 w-1.5 rounded-full" style={{ background: SEVERITY_COLOR[k] }} />{fmtInt(sev[k] ?? 0)}
              </span>
            )) : <span className="text-xs text-slate-500 dark:text-slate-400">No completed crawl yet</span>}
          </div>
        </div>
      </div>
      <div className="mt-3 flex items-center justify-between gap-2 border-t border-slate-100 pt-3 text-xs text-slate-500 dark:border-slate-800 dark:text-slate-400">
        {s.active_crawl ? (
          <Link to="/crawler" onClick={onSelect} className="inline-flex items-center gap-1.5 font-medium text-brand-700 hover:underline dark:text-brand-300">
            <Loader2 className="h-3.5 w-3.5 animate-spin" /> crawling…
          </Link>
        ) : <span>Last crawl: {s.last_crawl ? timeAgo(s.last_crawl.finished_at) : "never"}</span>}
        {selected ? <Link to={s.last_crawl ? "/audit" : "/crawler"} className="font-medium text-brand-700 hover:underline dark:text-brand-300">{s.last_crawl ? "Open audit" : "Start a crawl"}</Link>
          : <button onClick={onSelect} className="font-medium text-brand-700 hover:underline dark:text-brand-300">Select</button>}
      </div>
    </div>
  );
}

function Overview({ site }: { site: Site }) {
  const q = useQuery({ queryKey: ["overview", site.id], queryFn: () => api.get(`/sites/${site.id}/overview`), refetchInterval: site.active_crawl ? 5000 : false });
  if (q.isLoading) return <Card><Spinner /></Card>;
  if (q.error) return <ErrorBox error={q.error} onRetry={() => q.refetch()} />;
  const latest = q.data.latest;
  const stats: Record<string, any> = latest?.stats ?? {};
  const sev = stats.issues_by_severity ?? {};
  const history: any[] = (q.data.history ?? []).map((h: any) => ({ ...h, label: h.date ? fmtDate(h.date) : `#${h.id}` }));
  const statusData = Object.entries(stats.status_classes ?? {}).map(([name, value]) => ({ name, value: Number(value) })).sort((a, b) => a.name.localeCompare(b.name));
  const score: number | null = latest?.score ?? null;

  if (!latest) {
    return (
      <Card title={site.name}>
        <EmptyState title={site.active_crawl ? "First crawl in progress" : "No completed crawl yet"}
          description={site.active_crawl ? "Scores, issues and charts appear here as soon as the crawl finishes." : "Run a crawl to see the score, issues and trends for this website."}
          action={<Link to="/crawler" className={linkClass}>{site.active_crawl ? "View progress" : "Go to Crawler"}</Link>} />
      </Card>
    );
  }
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
        <Stat label="SEO score" value={score === null ? "–" : fmtNum(score, 0)} tone={score === null ? undefined : score >= 85 ? "good" : score >= 65 ? "warn" : "bad"}
          hint={`Crawl #${latest.id} · ${timeAgo(latest.finished_at)}`} tooltip="Average page score minus penalties for site-wide problems. See Site Audit for the formula." />
        <Stat label="URLs crawled" value={fmtInt(stats.total_urls ?? latest.pages_crawled)} hint={stats.limit_reached ? "URL limit reached" : undefined} />
        <Stat label="Indexable pages" value={fmtInt(stats.indexable_pages)} hint={`${fmtInt(stats.non_indexable_pages)} not indexable`} />
        <Stat label="Critical / high" value={`${fmtInt(sev.critical ?? 0)} / ${fmtInt(sev.high ?? 0)}`} tone={sev.critical ? "bad" : sev.high ? "warn" : "good"} hint={<Link to="/audit" className="hover:underline">View issues</Link>} />
        <Stat label="Unread alerts" value={fmtInt(q.data.counts?.unread_alerts)} tone={q.data.counts?.unread_alerts ? "warn" : undefined} hint={<Link to="/monitoring" className="hover:underline">Open monitoring</Link>} />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card title="Score history" description="Site score for each completed crawl" className="lg:col-span-2">
          {history.length < 2 ? <EmptyState title="Not enough history" description="The trend appears after the second completed crawl." /> : (
            <ResponsiveContainer width="100%" height={240}>
              <LineChart data={history} margin={{ top: 8, right: 12, bottom: 4, left: -16 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#94a3b833" vertical={false} />
                <XAxis dataKey="label" tick={axisTick} minTickGap={24} />
                <YAxis domain={[0, 100]} tick={axisTick} />
                <ChartTooltip contentStyle={tooltipStyle} />
                <Line type="monotone" dataKey="score" name="Score" stroke={chartColors[0]} strokeWidth={2} dot={{ r: 3 }} connectNulls />
              </LineChart>
            </ResponsiveContainer>
          )}
        </Card>
        <Card title="HTTP status" description="URLs in the latest crawl by response class">
          {!statusData.length ? <EmptyState title="No data" /> : (
            <ResponsiveContainer width="100%" height={240}>
              <PieChart>
                <Pie data={statusData} dataKey="value" nameKey="name" innerRadius={52} outerRadius={80} paddingAngle={2} stroke="none">
                  {statusData.map((d) => <Cell key={d.name} fill={STATUS_CLASS_COLOR[d.name] ?? "#64748b"} />)}
                </Pie>
                <ChartTooltip contentStyle={tooltipStyle} itemStyle={{ color: "#f1f5f9" }} />
                <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 12 }} />
              </PieChart>
            </ResponsiveContainer>
          )}
        </Card>
      </div>

      <Card title="Issues by severity over time" description="Issue counts for each completed crawl">
        {!history.length ? <EmptyState title="No data" /> : (
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={history} margin={{ top: 8, right: 12, bottom: 4, left: -8 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#94a3b833" vertical={false} />
              <XAxis dataKey="label" tick={axisTick} minTickGap={24} />
              <YAxis allowDecimals={false} tick={axisTick} />
              <ChartTooltip contentStyle={tooltipStyle} cursor={{ fill: "#94a3b81a" }} />
              <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 12 }} />
              {SEVERITIES.map((s) => <Bar key={s} dataKey={s} name={titleCase(s)} stackId="sev" fill={SEVERITY_COLOR[s]} maxBarSize={48} />)}
            </BarChart>
          </ResponsiveContainer>
        )}
      </Card>
    </div>
  );
}

export default function Dashboard() {
  const { site, setSiteId } = useSite();
  const navigate = useNavigate();
  const q = useQuery({
    queryKey: ["dashboard"],
    queryFn: () => api.get("/dashboard"),
    refetchInterval: (query) => {
      const d = query.state.data;
      return d && (d.sites.some((s: Site) => s.active_crawl) || d.jobs.some((j: any) => j.status === "running" || j.status === "queued")) ? 4000 : false;
    },
  });

  if (q.isLoading) return <Spinner />;
  if (q.error) return <><PageHeader title="Dashboard" /><ErrorBox error={q.error} onRetry={() => q.refetch()} /></>;
  const sites: Site[] = q.data.sites;
  const alerts: any[] = q.data.alerts;
  const jobs: any[] = q.data.jobs;

  if (!sites.length) {
    return (
      <>
        <PageHeader title="Dashboard" description="An overview of every website you track." />
        <Card>
          <EmptyState icon={<Globe className="h-6 w-6" />} title="Add your first website" description="Add a website and run a crawl to see its SEO score, issues and trends here."
            action={<Button variant="primary" icon={<Plus className="h-4 w-4" />} onClick={() => navigate("/sites")}>Add website</Button>} />
        </Card>
      </>
    );
  }

  return (
    <>
      <PageHeader title="Dashboard" description="An overview of every website you track."
        actions={<Button icon={<Plus className="h-4 w-4" />} onClick={() => navigate("/sites")}>Manage websites</Button>} />
      <div className="space-y-6">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {sites.map((s) => <SiteCard key={s.id} s={s} selected={site?.id === s.id} onSelect={() => setSiteId(s.id)} />)}
        </div>

        {site && (
          <section>
            <h2 className="mb-3 text-sm font-semibold text-slate-900 dark:text-slate-100">{site.name} <span className="font-normal text-slate-500 dark:text-slate-400">· {site.domain}</span></h2>
            <Overview site={site} />
          </section>
        )}

        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <Card title="Recent alerts" padded={false} actions={<Link to="/monitoring" className={linkClass}>All alerts</Link>}>
            {!alerts.length ? <EmptyState icon={<Bell className="h-6 w-6" />} title="No alerts" description="Alerts from monitors show up here when something changes on your websites." /> : (
              <ul className="divide-y divide-slate-100 dark:divide-slate-800">
                {alerts.map((a) => (
                  <li key={a.id} className="flex items-start gap-3 px-4 py-2.5">
                    <SeverityBadge severity={a.severity} />
                    <div className="min-w-0 flex-1">
                      <div className={`break-words text-sm ${a.read ? "text-slate-600 dark:text-slate-400" : "font-medium text-slate-900 dark:text-slate-100"}`}>{a.title}</div>
                      <div className="text-xs text-slate-500 dark:text-slate-400">{a.site ?? "Unknown site"} · {timeAgo(a.created_at)}</div>
                    </div>
                    {!a.read && <span className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-brand-500" title="Unread" />}
                  </li>
                ))}
              </ul>
            )}
          </Card>
          <Card title="Recent jobs" description="Background work such as crawls and imports" padded={false}>
            {!jobs.length ? <EmptyState title="No jobs yet" description="Crawls and other background tasks are listed here." /> : (
              <ul className="divide-y divide-slate-100 dark:divide-slate-800">
                {jobs.map((j) => (
                  <li key={j.id} className="px-4 py-2.5">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-slate-900 dark:text-slate-100">{titleCase(j.kind)}</span>
                      <Badge tone={JOB_TONE[j.status] ?? "gray"}>{j.status}</Badge>
                      <span className="ml-auto whitespace-nowrap text-xs text-slate-500 dark:text-slate-400">{timeAgo(j.finished_at ?? j.created_at)}</span>
                    </div>
                    {j.status === "running" ? <div className="mt-1.5"><ProgressBar value={j.progress ?? 0} label={j.message ?? "Working…"} /></div>
                      : (j.error || j.message) && <div className={`mt-0.5 break-words text-xs ${j.error ? "text-red-600 dark:text-red-400" : "text-slate-500 dark:text-slate-400"}`}>{j.error ?? j.message}</div>}
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </div>
      </div>
    </>
  );
}
