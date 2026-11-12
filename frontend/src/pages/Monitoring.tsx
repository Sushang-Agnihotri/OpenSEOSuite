import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bell, CheckCheck, Play, Plus, Trash2 } from "lucide-react";
import { type FormEvent, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import {
  Badge, Button, Card, Checkbox, type Column, DataTable, EmptyState, ErrorBox, ExportMenu, Field, Input, Modal, Notice, PageHeader,
  Pagination, Select, SeverityBadge, Spinner, Tabs, Textarea,
} from "../components/ui";
import { api } from "../lib/api";
import { type Job, useJob, useSite } from "../lib/context";
import { fmtDateTime, fmtInt, fmtMs, shortUrl, timeAgo } from "../lib/format";

type TabId = "monitors" | "alerts";
const KIND_ORDER = ["uptime", "audit", "sitemap", "metadata", "competitor", "gsc"];
const KIND_SHORT: Record<string, string> = { uptime: "Uptime", audit: "Audit", sitemap: "Sitemap", metadata: "Metadata", competitor: "Competitors", gsc: "Keywords (GSC)" };

function fmtInterval(hours: number): string {
  if (hours < 1) return `${Math.round(hours * 60)} min`;
  if (hours % 168 === 0) return hours === 168 ? "weekly" : `${hours / 168} weeks`;
  if (hours % 24 === 0) return hours === 24 ? "daily" : `${hours / 24} days`;
  return hours === 1 ? "hourly" : `${hours} h`;
}

function statusBadge(status: string | null) {
  if (!status) return <Badge>never run</Badge>;
  const tone = status === "ok" ? "green" : status === "problem" ? "red" : status === "error" ? "red" : "amber";
  return <Badge tone={tone}>{status}</Badge>;
}

function Summary({ m }: { m: any }) {
  const s = m.summary;
  const none = <span className="text-slate-400">–</span>;
  if (!s) return none;
  if (m.kind === "uptime") {
    const entries = Object.entries(s as Record<string, any>);
    if (!entries.length) return none;
    const down = entries.filter(([, v]) => !v.ok);
    return (
      <div className="max-w-xs text-xs">
        <div>{entries.length - down.length} of {entries.length} URL{entries.length === 1 ? "" : "s"} up</div>
        {down.slice(0, 3).map(([u, v]) => <div key={u} className="truncate text-red-600 dark:text-red-400" title={u}>{shortUrl(u)}: {v.status ?? "no response"}</div>)}
        {down.length === 0 && entries.length === 1 && entries[0][1].response_ms != null && <div className="text-slate-500 dark:text-slate-400">{fmtMs(entries[0][1].response_ms)}</div>}
      </div>
    );
  }
  if (m.kind === "sitemap") return s.urls === null || s.urls === undefined ? none : <span className="text-xs">{fmtInt(s.urls)} URLs in sitemap</span>;
  if (m.kind === "audit") return s.score === null || s.score === undefined ? none : <span className="text-xs">Score {Math.round(s.score)}{s.last_crawl_id ? ` (crawl #${s.last_crawl_id})` : ""}</span>;
  if (m.kind === "gsc") {
    return (
      <div className="max-w-xs text-xs">
        <div>{fmtInt(s.tracked)} keyword{s.tracked === 1 ? "" : "s"} tracked{s.as_of ? ` as of ${s.as_of}` : ""}</div>
        {s.note && <div className="text-amber-700 dark:text-amber-300">{s.note}</div>}
      </div>
    );
  }
  return none;
}

/** Owns the job of one manual run so several monitors can run at the same time. */
function RunNow({ monitor, onDone }: { monitor: any; onDone: (monitor: any, job: Job | null, error?: unknown) => void }) {
  const [jobId, setJobId] = useState<number | null>(null);
  const start = useMutation({
    mutationFn: () => api.post(`/monitors/${monitor.id}/run`),
    onSuccess: (r) => setJobId(r.job_id),
    onError: (e) => onDone(monitor, null, e),
  });
  const job = useJob(jobId, (j) => {
    setJobId(null);
    onDone(monitor, j);
  });
  const busy = start.isPending || jobId !== null;
  return (
    <Button size="sm" loading={busy} icon={<Play className="h-3.5 w-3.5" />} onClick={(e) => { e.stopPropagation(); start.mutate(); }}
      title={busy && job?.message ? job.message : "Run this monitor now"}>
      {busy ? "Running" : "Run now"}
    </Button>
  );
}

function CreateMonitorModal({ siteId, kinds, onClose }: { siteId: number; kinds: any; onClose: () => void }) {
  const qc = useQueryClient();
  const available = KIND_ORDER.filter((k) => kinds.kinds?.[k]).concat(Object.keys(kinds.kinds ?? {}).filter((k) => !KIND_ORDER.includes(k)));
  const defaults: Record<string, number> = kinds.default_interval_hours ?? {};
  const [kind, setKind] = useState(available[0] ?? "uptime");
  const [name, setName] = useState("");
  const [interval, setIntervalHours] = useState(String(defaults[available[0]] ?? 24));
  const [urls, setUrls] = useState("");
  const [maxUrls, setMaxUrls] = useState("");
  const [positionChange, setPositionChange] = useState("3");
  const [enabled, setEnabled] = useState(true);

  const create = useMutation({
    mutationFn: () => {
      const config: Record<string, any> = {};
      if (kind === "uptime" || kind === "metadata") {
        const list = urls.split(/\r?\n/).map((u) => u.trim()).filter(Boolean);
        if (list.length) config.urls = list;
      }
      if (kind === "audit" && maxUrls.trim()) config.crawl = { max_urls: Number(maxUrls) };
      if (kind === "gsc" && positionChange.trim()) config.position_change = Number(positionChange);
      return api.post(`/sites/${siteId}/monitors`, { kind, name: name.trim() || null, interval_hours: Number(interval), config, enabled });
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["monitors", siteId] });
      onClose();
    },
  });
  const submit = (e: FormEvent) => {
    e.preventDefault();
    create.mutate();
  };
  const changeKind = (k: string) => {
    setKind(k);
    setIntervalHours(String(defaults[k] ?? 24));
  };

  return (
    <Modal open onClose={onClose} title="New monitor"
      footer={<><Button onClick={onClose}>Cancel</Button><Button variant="primary" type="submit" form="monitor-form" loading={create.isPending}>Create monitor</Button></>}>
      <form id="monitor-form" onSubmit={submit} className="space-y-4">
        {create.error ? <ErrorBox error={create.error} /> : null}
        <Field label="What to monitor" hint={kinds.kinds?.[kind]}>
          <Select value={kind} onChange={(e) => changeKind(e.target.value)}>
            {available.map((k) => <option key={k} value={k}>{KIND_SHORT[k] ?? k}: {String(kinds.kinds[k]).split(" (")[0]}</option>)}
          </Select>
        </Field>
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Name" hint="Optional. Defaults to the monitor type.">
            <Input value={name} maxLength={255} onChange={(e) => setName(e.target.value)} placeholder={String(kinds.kinds?.[kind] ?? "").split(" (")[0]} />
          </Field>
          <Field label="Check every (hours)" hint={kind === "audit" ? "Audits run at most every 6 hours." : "0.25 = every 15 minutes."}>
            <Input type="number" required min={kind === "audit" ? 6 : 0.25} max={1440} step="any" value={interval} onChange={(e) => setIntervalHours(e.target.value)} />
          </Field>
        </div>
        {(kind === "uptime" || kind === "metadata") && (
          <Field label="URLs" hint={kind === "uptime" ? "Optional, one per line (max 50). Leave empty to check the site's start URL." : "Optional, one per line (max 50). Leave empty to watch the home page and the 20 strongest pages of the latest crawl."}>
            <Textarea rows={4} value={urls} onChange={(e) => setUrls(e.target.value)} placeholder={"https://example.com/\nhttps://example.com/pricing"} spellCheck={false} />
          </Field>
        )}
        {kind === "audit" && (
          <Field label="Max URLs per crawl" hint="Optional. Leave empty to use the site's crawl settings.">
            <Input type="number" min={1} step={1} value={maxUrls} onChange={(e) => setMaxUrls(e.target.value)} placeholder="Site default" />
          </Field>
        )}
        {kind === "gsc" && (
          <Field label="Position change threshold" hint="Alert when a saved keyword's average position moves by at least this many places (1 to 50). Requires a connected Search Console property.">
            <Input type="number" min={1} max={50} step="any" required value={positionChange} onChange={(e) => setPositionChange(e.target.value)} />
          </Field>
        )}
        {kind === "sitemap" && <Notice>Compares the URLs listed in the site's sitemaps with the previous run and reports additions and removals.</Notice>}
        {kind === "competitor" && <Notice>Watches the competitors saved for this site. Add them on the Competitors page first.</Notice>}
        <Checkbox label="Enabled" hint="Disabled monitors keep their history but are not scheduled." checked={enabled} onChange={setEnabled} />
      </form>
    </Modal>
  );
}

function Monitors({ siteId }: { siteId: number }) {
  const qc = useQueryClient();
  const kinds = useQuery({ queryKey: ["monitoring-kinds"], queryFn: () => api.get("/monitoring/kinds"), staleTime: Infinity });
  const monitors = useQuery({ queryKey: ["monitors", siteId], queryFn: () => api.get<any[]>(`/sites/${siteId}/monitors`) });
  const [creating, setCreating] = useState(false);
  const [deleting, setDeleting] = useState<any | null>(null);
  const [runNote, setRunNote] = useState<{ tone: "success" | "warn"; text: string } | null>(null);

  const toggle = useMutation({
    mutationFn: (m: any) => api.patch(`/monitors/${m.id}`, { enabled: !m.enabled }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["monitors", siteId] }),
  });
  const remove = useMutation({
    mutationFn: (m: any) => api.del(`/monitors/${m.id}`),
    onSuccess: () => {
      setDeleting(null);
      void qc.invalidateQueries({ queryKey: ["monitors", siteId] });
    },
  });
  const onRunDone = (m: any, job: Job | null, error?: unknown) => {
    void qc.invalidateQueries({ queryKey: ["monitors", siteId] });
    void qc.invalidateQueries({ queryKey: ["alerts"] });
    if (error || !job) setRunNote({ tone: "warn", text: `Could not start “${m.name}”: ${error instanceof Error ? error.message : "unknown error"}` });
    else if (job.status === "completed") setRunNote({ tone: "success", text: `“${m.name}” finished. New findings, if any, are listed under Alerts.` });
    else setRunNote({ tone: "warn", text: `“${m.name}” ${job.status}${job.error ? `: ${job.error}` : "."}` });
  };

  const columns: Column<any>[] = [
    { key: "name", header: "Name", render: (m) => <div className="max-w-xs"><div className="font-medium text-slate-900 dark:text-slate-100">{m.name}</div><div className="text-xs text-slate-500 dark:text-slate-400">{String(m.kind_label ?? "").split(" (")[0]}</div></div> },
    { key: "kind", header: "Kind", render: (m) => <Badge tone="blue">{KIND_SHORT[m.kind] ?? m.kind}</Badge> },
    { key: "interval", header: "Interval", render: (m) => fmtInterval(m.interval_hours) },
    {
      key: "enabled", header: "Enabled", render: (m) => (
        <button role="switch" aria-checked={m.enabled} aria-label={`${m.enabled ? "Disable" : "Enable"} ${m.name}`} disabled={toggle.isPending && toggle.variables?.id === m.id}
          onClick={() => toggle.mutate(m)}
          className={`relative inline-flex h-5 w-9 shrink-0 items-center rounded-full transition focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 disabled:opacity-50 ${m.enabled ? "bg-brand-600" : "bg-slate-300 dark:bg-slate-700"}`}>
          <span className={`inline-block h-4 w-4 rounded-full bg-white shadow transition ${m.enabled ? "translate-x-[18px]" : "translate-x-0.5"}`} />
        </button>
      ),
    },
    { key: "last_run", header: "Last run", render: (m) => <span title={m.last_run ? fmtDateTime(m.last_run) : undefined}>{timeAgo(m.last_run)}</span> },
    { key: "status", header: "Last status", render: (m) => statusBadge(m.last_status) },
    { key: "next_run", header: "Next run", render: (m) => (!m.enabled ? <span className="text-slate-400">paused</span> : m.next_run ? fmtDateTime(m.next_run) : "–") },
    { key: "summary", header: "Summary", render: (m) => <Summary m={m} /> },
    {
      key: "actions", header: "", align: "right", render: (m) => (
        <div className="flex items-center justify-end gap-1">
          <RunNow monitor={m} onDone={onRunDone} />
          <Button size="sm" variant="ghost" aria-label={`Delete ${m.name}`} onClick={() => { remove.reset(); setDeleting(m); }}><Trash2 className="h-4 w-4 text-red-600 dark:text-red-400" /></Button>
        </div>
      ),
    },
  ];

  if (monitors.isLoading || kinds.isLoading) return <Spinner />;
  if (monitors.error) return <ErrorBox error={monitors.error} onRetry={() => monitors.refetch()} />;
  if (kinds.error) return <ErrorBox error={kinds.error} onRetry={() => kinds.refetch()} />;
  const rows = monitors.data ?? [];
  const newButton = <Button variant="primary" icon={<Plus className="h-4 w-4" />} onClick={() => setCreating(true)}>New monitor</Button>;

  return (
    <div className="space-y-4">
      {runNote && <Notice tone={runNote.tone}>{runNote.text}</Notice>}
      {toggle.error ? <ErrorBox error={toggle.error} /> : null}
      <Card padded={false} title="Monitors" description="Scheduled checks run in the background while the server is running" actions={newButton}>
        <DataTable columns={columns} rows={rows} rowKey={(m) => m.id}
          empty={<EmptyState icon={<Bell className="h-6 w-6" />} title="No monitors yet"
            description="Monitors re-check the site on a schedule and raise an alert when something changes: a page goes down, the audit score drops, URLs leave the sitemap, titles change or keyword positions move."
            action={newButton} />} />
      </Card>
      {creating && kinds.data && <CreateMonitorModal siteId={siteId} kinds={kinds.data} onClose={() => setCreating(false)} />}
      <Modal open={!!deleting} onClose={() => setDeleting(null)} title="Delete monitor"
        footer={<><Button onClick={() => setDeleting(null)}>Cancel</Button><Button variant="danger" loading={remove.isPending} onClick={() => deleting && remove.mutate(deleting)}>Delete</Button></>}>
        <p className="text-sm text-slate-700 dark:text-slate-300">Delete “{deleting?.name}”? Its schedule and stored state are removed. Alerts it already raised are kept.</p>
        {remove.error ? <div className="mt-3"><ErrorBox error={remove.error} /></div> : null}
      </Modal>
    </div>
  );
}

function Alerts({ siteId }: { siteId: number }) {
  const qc = useQueryClient();
  const [unreadOnly, setUnreadOnly] = useState(false);
  const [page, setPage] = useState(1);
  const perPage = 25;
  useEffect(() => setPage(1), [unreadOnly, siteId]);
  const q = useQuery({
    queryKey: ["alerts", siteId, unreadOnly, page],
    queryFn: () => api.get("/alerts", { site_id: siteId, unread: unreadOnly, page, per_page: perPage }),
    placeholderData: (prev) => prev,
  });
  const markRead = useMutation({
    mutationFn: (ids: number[] | null) => api.post("/alerts/read", ids ? { ids } : {}),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["alerts"] });
      void qc.invalidateQueries({ queryKey: ["alerts", "unread"] });
    },
  });

  const items: any[] = q.data?.items ?? [];
  const columns: Column<any>[] = [
    { key: "severity", header: "Severity", render: (a) => <SeverityBadge severity={a.severity} /> },
    {
      key: "alert", header: "Alert", render: (a) => (
        <div className="max-w-2xl">
          <div className={`flex items-center gap-2 ${a.read ? "text-slate-600 dark:text-slate-400" : "font-semibold text-slate-900 dark:text-slate-100"}`}>
            {!a.read && <span className="h-2 w-2 shrink-0 rounded-full bg-brand-600" aria-label="Unread" />}
            {a.title}
          </div>
          {a.message && <p className="mt-0.5 whitespace-pre-line break-words text-xs text-slate-600 dark:text-slate-400">{a.message}</p>}
        </div>
      ),
    },
    { key: "time", header: "Time", render: (a) => <span className="whitespace-nowrap" title={fmtDateTime(a.created_at)}>{timeAgo(a.created_at)}</span> },
    {
      key: "state", header: "State", align: "right", render: (a) => a.read ? <Badge>read</Badge> : (
        <Button size="sm" variant="ghost" loading={markRead.isPending && markRead.variables?.length === 1 && markRead.variables[0] === a.id} onClick={() => markRead.mutate([a.id])}>Mark read</Button>
      ),
    },
  ];

  return (
    <Card padded={false} title="Alerts" description="Raised by this site's monitors, newest first"
      actions={
        <>
          <Checkbox label="Unread only" checked={unreadOnly} onChange={setUnreadOnly} />
          <span title="Marks every unread alert of all your sites as read">
            <Button icon={<CheckCheck className="h-4 w-4" />} loading={markRead.isPending && markRead.variables === null} disabled={!q.data?.unread} onClick={() => markRead.mutate(null)}>Mark all read</Button>
          </span>
          <ExportMenu label="Export CSV" formats={[{ label: "CSV", path: "/alerts/export" }]} />
        </>
      }>
      {markRead.error ? <div className="p-4"><ErrorBox error={markRead.error} /></div> : null}
      {q.isLoading ? <Spinner /> : q.error ? <div className="p-4"><ErrorBox error={q.error} onRetry={() => q.refetch()} /></div> : (
        <>
          <DataTable columns={columns} rows={items} rowKey={(a) => a.id}
            empty={<EmptyState icon={<Bell className="h-6 w-6" />} title={unreadOnly ? "No unread alerts" : "No alerts yet"}
              description={unreadOnly ? "You are all caught up for this site." : "Alerts appear here when a monitor detects a change or a problem. Create a monitor on the Monitors tab to get started."} />} />
          {items.length > 0 && <Pagination page={page} perPage={perPage} total={q.data.total} onPage={setPage} />}
        </>
      )}
    </Card>
  );
}

export default function Monitoring() {
  const { site, loading } = useSite();
  const [params, setParams] = useSearchParams();
  const tab: TabId = params.get("tab") === "alerts" ? "alerts" : "monitors";
  const setTab = (id: TabId) => setParams(id === "alerts" ? { tab: "alerts" } : {}, { replace: true });

  const header = <PageHeader title="Monitoring" description="Scheduled uptime checks, recurring audits and change detection, with alerts when something needs attention." />;
  if (loading) return <>{header}<Spinner /></>;
  if (!site) {
    return (
      <>
        {header}
        <Card><EmptyState title="Add a website first" description="Monitors belong to a site. Add one under Websites to start monitoring it."
          action={<a href="/sites" className="text-sm font-medium text-brand-700 hover:underline dark:text-brand-300">Go to Websites</a>} /></Card>
      </>
    );
  }
  return (
    <>
      {header}
      <Tabs<TabId> value={tab} onChange={setTab} tabs={[{ id: "monitors", label: "Monitors" }, { id: "alerts", label: "Alerts" }]} />
      {tab === "monitors" ? <Monitors key={site.id} siteId={site.id} /> : <Alerts siteId={site.id} />}
    </>
  );
}
