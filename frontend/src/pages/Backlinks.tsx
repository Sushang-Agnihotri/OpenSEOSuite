import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link2, ShieldCheck, Trash2 } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip as ChartTooltip } from "recharts";
import {
  Badge, Button, Card, chartColors, type Column, DataBadge, DataTable, EmptyState, ErrorBox, ExportMenu, FileButton, Modal, NeedsCrawl, Notice,
  PageHeader, Pagination, ProgressBar, SearchInput, Select, Spinner, Stat, StatusCode, Tabs, Url,
} from "../components/ui";
import { api } from "../lib/api";
import { type Job, useJob, useSite } from "../lib/context";
import { fmtDate, fmtInt, shortUrl, timeAgo } from "../lib/format";

type Tab = "links" | "domains" | "anchors" | "targets" | "opportunities";
const PER_PAGE = 50;
const STATUS_TONE: Record<string, string> = { live: "green", lost: "red", unverified: "gray", source_error: "orange" };
const FALLBACK_COVERAGE = "Only links present in imported datasets are shown. This is not a complete picture of the web's links to your site.";

function RelBadge({ nofollow }: { nofollow: boolean | null }) {
  return nofollow === null || nofollow === undefined ? <Badge title="The imported file had no rel information and the link has not been verified">unknown</Badge>
    : nofollow ? <Badge tone="amber">nofollow</Badge> : <Badge tone="green">follow</Badge>;
}

function LinksTab({ siteId, siteUrl }: { siteId: number; siteUrl: string }) {
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const [rel, setRel] = useState("");
  const [page, setPage] = useState(1);
  const list = useQuery({
    queryKey: ["backlinks", siteId, "list", q, status, rel, page],
    queryFn: () => api.get(`/sites/${siteId}/backlinks`, { q, status, rel, page, per_page: PER_PAGE }),
    placeholderData: keepPreviousData,
  });
  const columns: Column<any>[] = [
    { key: "source", header: "Linking page", render: (b) => (
      <div className="max-w-sm">
        <Url href={b.source_url} label={shortUrl(b.source_url)} />
        <div className="text-xs text-slate-500 dark:text-slate-400">{b.source_domain}{String(b.origin).endsWith("domain-level") && " · domain-level row (no page URL in the import)"}</div>
      </div>
    ) },
    { key: "target", header: "Target", render: (b) => (b.target_url ? <Url href={b.target_url} label={shortUrl(b.target_url, siteUrl)} className="block max-w-xs" /> : <span className="text-slate-400">–</span>) },
    { key: "anchor", header: "Anchor", render: (b) => (b.anchor ? <span className="block max-w-xs break-words">{b.anchor}</span> : <span className="text-slate-400">–</span>) },
    { key: "rel", header: "Rel", render: (b) => <RelBadge nofollow={b.nofollow} /> },
    { key: "status", header: "Status", tooltip: "Set by Verify links: live = link found on the page, lost = page loads but no link, source_error = page could not be loaded",
      render: (b) => <span className="inline-flex items-center gap-1"><Badge tone={STATUS_TONE[b.status] ?? "gray"}>{String(b.status).replace("_", " ")}</Badge>{b.http_status ? <StatusCode code={b.http_status} /> : null}</span> },
    { key: "origin", header: "Origin", render: (b) => <Badge tone="blue" title="Dataset that supplied this row">{String(b.origin).split(":")[0]}</Badge> },
    { key: "first", header: "First seen", tooltip: "When the row was first imported into this toolkit", render: (b) => fmtDate(b.first_seen) },
    { key: "checked", header: "Last checked", render: (b) => (b.last_checked ? timeAgo(b.last_checked) : <span className="text-slate-400">never</span>) },
  ];
  return (
    <Card padded={false}>
      <div className="flex flex-wrap items-center gap-2 border-b border-slate-100 p-3 dark:border-slate-800">
        <SearchInput value={q} onChange={(v) => { setQ(v); setPage(1); }} placeholder="Search URL or anchor…" />
        <Select className="w-auto" value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }} aria-label="Filter by status">
          <option value="">All statuses</option>
          <option value="live">Live</option>
          <option value="lost">Lost</option>
          <option value="unverified">Unverified</option>
          <option value="source_error">Source error</option>
        </Select>
        <Select className="w-auto" value={rel} onChange={(e) => { setRel(e.target.value); setPage(1); }} aria-label="Filter by rel">
          <option value="">Follow + nofollow</option>
          <option value="follow">Follow</option>
          <option value="nofollow">Nofollow</option>
        </Select>
      </div>
      {list.isLoading ? <Spinner /> : list.error ? <div className="p-3"><ErrorBox error={list.error} onRetry={() => list.refetch()} /></div> : (
        <>
          <DataTable dense columns={columns} rows={list.data?.items ?? []} rowKey={(b) => b.id}
            empty={<EmptyState title="No links match" description="Change the search or filters." />} />
          <Pagination page={page} perPage={PER_PAGE} total={list.data?.total ?? 0} onPage={setPage} />
        </>
      )}
    </Card>
  );
}

export default function Backlinks() {
  const { site } = useSite();
  const qc = useQueryClient();
  const siteId = site?.id;
  const [tab, setTab] = useState<Tab>("links");
  const [origin, setOrigin] = useState("import");
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [jobId, setJobId] = useState<number | null>(null);
  const [verifyResult, setVerifyResult] = useState<Job | null>(null);

  const summary = useQuery({ queryKey: ["backlinks", siteId, "summary"], queryFn: () => api.get(`/sites/${siteId}/backlinks/summary`), enabled: !!siteId });
  const refresh = () => void qc.invalidateQueries({ queryKey: ["backlinks", siteId] });
  const importCsv = useMutation({ mutationFn: (file: File) => api.upload(`/sites/${siteId}/backlinks/import`, file, { origin }), onSuccess: refresh });
  const verify = useMutation({
    mutationFn: () => api.post(`/sites/${siteId}/backlinks/verify`),
    onSuccess: (r) => { setVerifyResult(null); setJobId(r.job_id); },
  });
  const clear = useMutation({
    mutationFn: () => api.del(`/sites/${siteId}/backlinks`),
    onSuccess: () => { setConfirmDelete(false); importCsv.reset(); setVerifyResult(null); refresh(); },
  });
  const job = useJob(jobId, (j) => { setJobId(null); setVerifyResult(j); refresh(); });

  if (!site) return <NeedsCrawl hasSite={false} />;

  const s = summary.data;
  const total: number = s?.total ?? 0;
  const statuses = (s?.statuses ?? {}) as Record<string, number>;
  const anchorTypes = Object.entries((s?.anchor_types ?? {}) as Record<string, number>).map(([name, value]) => ({ name, value }));
  const verifying = verify.isPending || !!jobId;

  const domainColumns: Column<any>[] = [
    { key: "domain", header: "Referring domain", render: (d) => <Url href={`https://${d.domain}`} label={d.domain} /> },
    { key: "n", header: "Backlinks", align: "right", render: (d) => fmtInt(d.backlinks) },
    { key: "first", header: "First seen", tooltip: "Earliest import date for this domain", render: (d) => fmtDate(d.first_seen) },
  ];
  const anchorColumns: Column<any>[] = [
    { key: "anchor", header: "Anchor text", render: (a) => <span className="block max-w-md break-words">{a.anchor}</span> },
    { key: "n", header: "Links", align: "right", render: (a) => fmtInt(a.count) },
    { key: "share", header: "Share", align: "right", render: (a) => (total ? `${((a.count / total) * 100).toFixed(1)}%` : "–") },
  ];
  const targetColumns: Column<any>[] = [
    { key: "url", header: "Linked page on your site", render: (t) => <Url href={t.url} label={shortUrl(t.url, site.url)} className="block max-w-lg" /> },
    { key: "n", header: "Backlinks", align: "right", render: (t) => fmtInt(t.backlinks) },
    { key: "status", header: "Status in latest crawl", render: (t) => !t.in_crawl ? <Badge title="This URL was not reached by the latest crawl">not in crawl</Badge>
      : <span className="inline-flex items-center gap-1.5"><StatusCode code={t.status} error="no response" />{(t.status === null || t.status >= 400) && <Badge tone="red">broken</Badge>}</span> },
  ];
  const oppColumns: Column<any>[] = [
    { key: "type", header: "Type", render: (o) => <Badge tone="orange">{o.type}</Badge> },
    { key: "url", header: "Page", render: (o) => <Url href={o.url} label={shortUrl(o.url, site.url)} className="block max-w-sm" /> },
    { key: "n", header: "Backlinks", align: "right", render: (o) => fmtInt(o.backlinks) },
    { key: "action", header: "Recommended action", render: (o) => <span className="block max-w-md whitespace-normal">{o.action}</span> },
  ];

  return (
    <div>
      <PageHeader title="Backlinks"
        description="Analyse and verify the backlink data you already have. This toolkit has no web-scale link index, so nothing here is guessed."
        actions={<>
          <Select className="w-auto" value={origin} onChange={(e) => setOrigin(e.target.value)} aria-label="Origin of the file to import" title="Label stored with the imported rows">
            <option value="import">Origin: generic import</option>
            <option value="gsc">Origin: Search Console</option>
            <option value="other">Origin: other tool</option>
          </Select>
          <FileButton label="Import CSV" loading={importCsv.isPending} onFile={(f) => importCsv.mutate(f)} />
          <Button icon={<ShieldCheck className="h-4 w-4" />} loading={verifying} disabled={!total} onClick={() => verify.mutate()}>Verify links</Button>
          <ExportMenu formats={[
            { label: "CSV", path: `/sites/${site.id}/backlinks/export`, query: { format: "csv" } },
            { label: "Excel (XLSX)", path: `/sites/${site.id}/backlinks/export`, query: { format: "xlsx" } },
          ]} />
          <Button variant="ghost" icon={<Trash2 className="h-4 w-4" />} disabled={!total} onClick={() => setConfirmDelete(true)}>Delete all</Button>
        </>} />

      <div className="space-y-4">
        <Notice tone="warn">
          <p className="font-medium">{s?.coverage_note ?? FALLBACK_COVERAGE}</p>
          <p className="mt-1">Data comes only from datasets you import: the Search Console links export, exports from other backlink tools, or any CSV with source, target and anchor columns. Imported rows are labelled <DataBadge kind="imported" />; link status, anchor and rel become <DataBadge kind="measured" /> once you run Verify links.</p>
        </Notice>

        {importCsv.error && <ErrorBox error={importCsv.error} />}
        {importCsv.data && <Notice tone="success">Import finished: {fmtInt(importCsv.data.added)} links added, {fmtInt(importCsv.data.skipped)} skipped (duplicates or invalid URLs). Columns detected: {(importCsv.data.columns_detected ?? []).join(", ") || "none"}.</Notice>}
        {verify.error && <ErrorBox error={verify.error} onRetry={() => verify.mutate()} />}
        {jobId && <Card><ProgressBar value={job?.progress ?? 0} label={job?.message ?? "Starting verification…"} /></Card>}
        {verifyResult && (verifyResult.status === "completed" ? (
          <Notice tone="success">Verification finished: {fmtInt(verifyResult.result?.checked ?? 0)} linking pages checked, {fmtInt(verifyResult.result?.live ?? 0)} live, {fmtInt(verifyResult.result?.lost ?? 0)} lost, {fmtInt(verifyResult.result?.source_error ?? 0)} could not be loaded. Each run checks up to 300 links, least recently checked first.</Notice>
        ) : <ErrorBox error={verifyResult.error ?? `Verification ${verifyResult.status}.`} />)}

        {summary.isLoading ? <Card><Spinner /></Card> : summary.error ? <ErrorBox error={summary.error} onRetry={() => summary.refetch()} /> : !total ? (
          <Card>
            <EmptyState icon={<Link2 className="h-6 w-6" />} title="No backlink data imported yet"
              description="Import a links file to analyse referring domains, anchors and link targets, and to verify which links are still live."
              action={<FileButton label="Import CSV" loading={importCsv.isPending} onFile={(f) => importCsv.mutate(f)} />} />
            <div className="mx-auto max-w-2xl border-t border-slate-100 px-2 pb-4 pt-4 text-sm text-slate-600 dark:border-slate-800 dark:text-slate-300">
              <h3 className="font-semibold text-slate-900 dark:text-slate-100">How to get a links export from Google Search Console</h3>
              <ol className="mt-2 list-decimal space-y-1 pl-5">
                <li>Open Search Console and select your property.</li>
                <li>Go to <span className="font-medium">Links</span> in the left menu.</li>
                <li>Press <span className="font-medium">Export external links</span> (top right) and choose <span className="font-medium">More sample links</span> or <span className="font-medium">Latest links</span>, then download as CSV.</li>
                <li>Choose "Origin: Search Console" above and import the file here.</li>
              </ol>
              <p className="mt-3 text-xs text-slate-500 dark:text-slate-400">
                Any CSV works if it has a source column (e.g. "Source URL", "Linking page", "Referring page URL") or a "Site" column. Optional columns: target ("Target URL", "Target page"), anchor ("Anchor text") and rel ("Nofollow", "Link type"). Files listing only linking sites are stored as domain-level rows and cannot be verified.
              </p>
            </div>
          </Card>
        ) : (
          <>
            <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
              <Stat label="Backlinks" value={fmtInt(total)} hint={<span className="inline-flex flex-wrap items-center gap-1"><DataBadge kind="imported" />{Object.entries((s.origins ?? {}) as Record<string, number>).map(([o, c]) => `${o}: ${fmtInt(c)}`).join(" · ")}</span>} />
              <Stat label="Referring domains" value={fmtInt(s.referring_domains)} />
              <Stat label="Follow / nofollow" value={<>{fmtInt(s.follow)} <span className="text-slate-400">/</span> {fmtInt(s.nofollow)}</>} hint={`${fmtInt(s.rel_unknown)} with unknown rel`} />
              <Stat label="New, last 30 days" value={fmtInt(s.new_last_30_days)} tooltip="Rows first imported into this toolkit in the last 30 days. This is the import date, not the date the link was created." />
              <Stat label="Live / lost" value={<><span className="text-emerald-600 dark:text-emerald-400">{fmtInt(statuses.live ?? 0)}</span> <span className="text-slate-400">/</span> <span className={statuses.lost ? "text-red-600 dark:text-red-400" : ""}>{fmtInt(statuses.lost ?? 0)}</span></>}
                hint={<span className="inline-flex items-center gap-1"><DataBadge kind="measured" />{statuses.source_error ? `${fmtInt(statuses.source_error)} source errors` : "by Verify links"}</span>} />
              <Stat label="Unverified" value={fmtInt(statuses.unverified ?? 0)} hint="Not checked yet" />
            </div>

            <Tabs<Tab> value={tab} onChange={setTab} tabs={[
              { id: "links", label: "Links", count: total },
              { id: "domains", label: "Referring domains", count: s.referring_domains },
              { id: "anchors", label: "Anchors" },
              { id: "targets", label: "Link targets", count: (s.broken_targets ?? []).length ? (s.top_targets ?? []).length : undefined },
              { id: "opportunities", label: "Opportunities", count: (s.opportunities ?? []).length },
            ]} />

            {tab === "links" && <LinksTab siteId={site.id} siteUrl={site.url} />}

            {tab === "domains" && (
              <Card padded={false} title="Referring domains" description="Top 100 domains by number of imported links">
                <DataTable dense columns={domainColumns} rows={s.top_domains ?? []} rowKey={(d) => d.domain} />
              </Card>
            )}

            {tab === "anchors" && (
              <div className="grid gap-4 lg:grid-cols-3">
                <Card title={<span className="inline-flex items-center gap-2">Anchor types <DataBadge kind="estimated" /></span>} description="Classified by simple rules from the anchor text and your domain name">
                  {anchorTypes.length ? (
                    <ResponsiveContainer width="100%" height={260}>
                      <PieChart>
                        <Pie data={anchorTypes} dataKey="value" nameKey="name" innerRadius={55} outerRadius={85} paddingAngle={2} stroke="none">
                          {anchorTypes.map((_, i) => <Cell key={i} fill={chartColors[i % chartColors.length]} />)}
                        </Pie>
                        <ChartTooltip contentStyle={{ background: "#0f172a", border: "none", borderRadius: 8, fontSize: 12 }} itemStyle={{ color: "#f8fafc" }} />
                        <Legend wrapperStyle={{ fontSize: 12 }} />
                      </PieChart>
                    </ResponsiveContainer>
                  ) : <EmptyState title="No anchor text" description="The imported files contain no anchors. Run Verify links to read anchors from the linking pages." />}
                </Card>
                <Card padded={false} className="lg:col-span-2" title="Anchor texts" description="Top 100 anchors">
                  <div className="max-h-[32rem] overflow-y-auto">
                    <DataTable dense columns={anchorColumns} rows={s.top_anchors ?? []} rowKey={(a) => a.anchor}
                      empty={<EmptyState title="No anchor text" description="The imported files contain no anchors. Run Verify links to read anchors from the linking pages." />} />
                  </div>
                </Card>
              </div>
            )}

            {tab === "targets" && (
              <div className="space-y-3">
                {s.crawl_used_for_targets ? (
                  (s.broken_targets ?? []).length > 0 && <Notice tone="warn">{s.broken_targets.length} linked page{s.broken_targets.length === 1 ? " is" : "s are"} broken in your latest crawl. Links pointing to them pass no value until the pages are restored or redirected.</Notice>
                ) : <Notice>No completed crawl of this site yet, so the status of linked pages is unknown. <Link to="/crawler" className="font-medium underline">Run a crawl</Link> to find broken link targets.</Notice>}
                <Card padded={false} title="Link targets" description="Pages on your site that receive imported backlinks (top 100)">
                  <DataTable dense columns={targetColumns} rows={s.top_targets ?? []} rowKey={(t) => t.url}
                    empty={<EmptyState title="No target URLs" description="The imported files do not say which of your pages each link points to. Run Verify links to detect targets." />} />
                </Card>
              </div>
            )}

            {tab === "opportunities" && (
              <Card padded={false} title="Opportunities" description="Link reclamation: backlinks pointing at pages that are broken in your latest crawl">
                <DataTable columns={oppColumns} rows={s.opportunities ?? []} rowKey={(o) => o.url}
                  empty={<EmptyState title="No opportunities found" description={s.crawl_used_for_targets ? "None of the linked pages is broken in your latest crawl." : "Run a crawl of your site so broken link targets can be detected."} />} />
              </Card>
            )}
          </>
        )}
      </div>

      <Modal open={confirmDelete} onClose={() => setConfirmDelete(false)} title="Delete all backlinks?"
        footer={<>
          <Button onClick={() => setConfirmDelete(false)}>Cancel</Button>
          <Button variant="danger" loading={clear.isPending} onClick={() => clear.mutate()}>Delete {fmtInt(total)} backlinks</Button>
        </>}>
        <p className="text-sm text-slate-600 dark:text-slate-300">This permanently removes every imported backlink and all verification results for {site.name}. You can import the files again afterwards.</p>
        {clear.error && <div className="mt-3"><ErrorBox error={clear.error} /></div>}
      </Modal>
    </div>
  );
}
