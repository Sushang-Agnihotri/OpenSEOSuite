import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, Layers, Plus, Save, Search, Trash2 } from "lucide-react";
import { type FormEvent, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  Badge, Button, Card, Checkbox, type Column, DataBadge, DataTable, EmptyState, ErrorBox, ExportMenu, Field, FileButton, Input,
  NeedsCrawl, Notice, PageHeader, Pagination, SearchInput, Select, Spinner, Stat, Tabs, Textarea, Url,
} from "../components/ui";
import { api } from "../lib/api";
import { useSite } from "../lib/context";
import { fmtInt, fmtNum, shortUrl } from "../lib/format";

type Tab = "research" | "saved" | "mapping" | "cluster";

const INTENT_TONE: Record<string, string> = { transactional: "green", commercial: "purple", navigational: "blue", local: "orange", informational: "gray" };
const INTENTS = ["informational", "commercial", "transactional", "navigational", "local"];
const TYPES = ["question", "comparison", "preposition", "long-tail", "suggestion"];
const PER_PAGE = 100;

function IntentBadge({ intent, confidence }: { intent: string | null | undefined; confidence?: number | null }) {
  if (!intent) return <span className="text-slate-400">–</span>;
  return (
    <span className="inline-flex items-center gap-1.5">
      <Badge tone={INTENT_TONE[intent] ?? "gray"} title="Rule-based estimate">{intent}</Badge>
      {confidence !== undefined && confidence !== null && (
        <span className="text-xs tabular-nums text-slate-500 dark:text-slate-400" title="Rough confidence of the rule-based estimate">{Math.round(confidence * 100)}%</span>
      )}
    </span>
  );
}

function Chip({ children }: { children: React.ReactNode }) {
  return <span className="inline-flex items-center rounded-md border border-slate-200 bg-slate-50 px-1.5 py-0.5 text-xs text-slate-700 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300">{children}</span>;
}

function RowCheck({ checked, onChange, label }: { checked: boolean; onChange: (v: boolean) => void; label: string }) {
  return (
    <input type="checkbox" aria-label={label} checked={checked} onChange={(e) => onChange(e.target.checked)}
      className="h-4 w-4 rounded border-slate-300 text-brand-600 focus:ring-brand-500 dark:border-slate-600 dark:bg-slate-900" />
  );
}

function csvCell(v: unknown): string {
  let s = v === null || v === undefined ? "" : String(v);
  if (/^[=+\-@]/.test(s)) s = `'${s}`; // neutralise spreadsheet formula injection
  return /[",\n\r]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

function downloadCsv(filename: string, header: string[], rows: unknown[][]) {
  const text = [header, ...rows].map((r) => r.map(csvCell).join(",")).join("\r\n");
  const url = URL.createObjectURL(new Blob(["﻿", text], { type: "text/csv;charset=utf-8" }));
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

function parseLines(text: string): string[] {
  return Array.from(new Set(text.split(/\r?\n/).map((l) => l.trim()).filter(Boolean)));
}

function ClusterGrid({ clusters }: { clusters: any[] }) {
  const [showAll, setShowAll] = useState<Record<string, boolean>>({});
  if (!clusters.length) return <EmptyState title="No clusters" description="There were not enough keywords to group." />;
  return (
    <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
      {clusters.map((c, i) => {
        const key = `${c.label}-${i}`;
        const kws: string[] = c.keywords ?? [];
        const shown = showAll[key] ? kws : kws.slice(0, 12);
        return (
          <div key={key} className="rounded-xl border border-slate-200 bg-white p-3 shadow-sm dark:border-slate-800 dark:bg-slate-900">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h3 className="min-w-0 break-words text-sm font-semibold text-slate-900 dark:text-slate-100">{c.label}</h3>
              <div className="flex items-center gap-1.5">
                <Badge>{c.size} keyword{c.size === 1 ? "" : "s"}</Badge>
                <IntentBadge intent={c.dominant_intent} />
              </div>
            </div>
            <div className="mt-2 flex flex-wrap gap-1">
              {shown.map((k) => <Chip key={k}>{k}</Chip>)}
              {kws.length > 12 && (
                <button className="text-xs font-medium text-brand-700 hover:underline dark:text-brand-300" onClick={() => setShowAll((s) => ({ ...s, [key]: !s[key] }))}>
                  {showAll[key] ? "Show fewer" : `+${kws.length - 12} more`}
                </button>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

/* ------------------------------------------------------------------ research */
function ResearchTab() {
  const { site } = useSite();
  const qc = useQueryClient();
  const [seed, setSeed] = useState("");
  const [lang, setLang] = useState("en");
  const [country, setCountry] = useState("us");
  const [sources, setSources] = useState<Record<string, boolean>>({ google: true, bing: true, duckduckgo: true });
  const [depth, setDepth] = useState("basic");
  const [view, setView] = useState<"keywords" | "clusters">("keywords");
  const [q, setQ] = useState("");
  const [type, setType] = useState("");
  const [intent, setIntent] = useState("");
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<Set<string>>(new Set());

  const activeSources = Object.keys(sources).filter((s) => sources[s]);
  const suggest = useMutation({
    mutationFn: () => api.post("/keywords/suggest", { seed: seed.trim(), lang: lang.trim().toLowerCase(), country: country.trim().toLowerCase(), sources: activeSources, depth }),
    onSuccess: () => { setSelected(new Set()); setPage(1); save.reset(); },
  });
  const save = useMutation({
    mutationFn: async (keywords: string[]) => {
      let added = 0;
      let total = 0;
      for (let i = 0; i < keywords.length; i += 2000) {
        const r = await api.post(`/sites/${site!.id}/keywords`, { keywords: keywords.slice(i, i + 2000), source: "suggest" });
        added += r.added;
        total = r.total;
      }
      return { added, total };
    },
    onSuccess: () => {
      setSelected(new Set());
      void qc.invalidateQueries({ queryKey: ["keywords", site?.id] });
      void qc.invalidateQueries({ queryKey: ["keyword-mapping", site?.id] });
    },
  });

  const result = suggest.data;
  const all: any[] = result?.keywords ?? [];
  const visible = useMemo(() => {
    const needle = q.trim().toLowerCase();
    return all.filter((k) => (!needle || k.keyword.includes(needle)) && (!type || k.type === type) && (!intent || k.intent === intent));
  }, [all, q, type, intent]);
  const pageRows = visible.slice((page - 1) * PER_PAGE, page * PER_PAGE);
  const allVisibleSelected = visible.length > 0 && visible.every((k) => selected.has(k.keyword));
  const errors = Object.entries((result?.errors ?? {}) as Record<string, string>);

  const toggle = (kw: string, on: boolean) => setSelected((s) => { const n = new Set(s); if (on) n.add(kw); else n.delete(kw); return n; });
  const toggleAll = (on: boolean) => setSelected((s) => { const n = new Set(s); visible.forEach((k) => (on ? n.add(k.keyword) : n.delete(k.keyword))); return n; });

  const submit = (e: FormEvent) => { e.preventDefault(); if (seed.trim() && activeSources.length) suggest.mutate(); };

  const columns: Column<any>[] = [
    { key: "sel", width: "32px", header: <RowCheck label="Select all visible keywords" checked={allVisibleSelected} onChange={toggleAll} />,
      render: (k) => <RowCheck label={`Select ${k.keyword}`} checked={selected.has(k.keyword)} onChange={(v) => toggle(k.keyword, v)} /> },
    { key: "keyword", header: "Keyword", render: (k) => <span className="font-medium text-slate-900 dark:text-slate-100">{k.keyword}</span> },
    { key: "type", header: "Type", render: (k) => <Badge tone={k.type === "question" ? "blue" : "gray"}>{k.type}</Badge> },
    { key: "intent", header: <span className="inline-flex items-center gap-1.5">Intent <DataBadge kind="estimated" /></span>,
      render: (k) => <IntentBadge intent={k.intent} confidence={k.intent_confidence} /> },
    { key: "sources", header: "Sources", tooltip: "Which autocomplete endpoints returned this suggestion",
      render: (k) => <span className="flex flex-wrap gap-1">{(k.sources ?? []).map((s: string) => <Chip key={s}>{s}</Chip>)}</span> },
    { key: "words", header: "Words", align: "right", render: (k) => k.words },
    { key: "volume", header: "Search volume", tooltip: "Autocomplete endpoints do not provide search volume. Import a Keyword Planner CSV under Saved keywords to add it.",
      render: (k) => (k.search_volume !== null && k.search_volume !== undefined ? fmtInt(k.search_volume) : <DataBadge kind="unavailable" />) },
  ];

  return (
    <div className="space-y-4">
      <Card title="Find keyword ideas" description="Real completions from public autocomplete endpoints, fetched at request time.">
        <form onSubmit={submit} className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-12">
            <Field label="Seed keyword" className="sm:col-span-2 lg:col-span-5">
              <Input required maxLength={120} value={seed} onChange={(e) => setSeed(e.target.value)} placeholder="e.g. standing desk" />
            </Field>
            <Field label="Language" hint="2-letter code" className="lg:col-span-2">
              <Input required pattern="[A-Za-z]{2}" maxLength={2} value={lang} onChange={(e) => setLang(e.target.value)} placeholder="en" />
            </Field>
            <Field label="Country" hint="2-letter code" className="lg:col-span-2">
              <Input required pattern="[A-Za-z]{2}" maxLength={2} value={country} onChange={(e) => setCountry(e.target.value)} placeholder="us" />
            </Field>
            <Field label="Depth" className="lg:col-span-3">
              <Select value={depth} onChange={(e) => setDepth(e.target.value)}>
                <option value="basic">Basic (questions + prepositions)</option>
                <option value="deep">Deep (adds A–Z expansion, slower)</option>
              </Select>
            </Field>
          </div>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex flex-wrap items-center gap-x-5 gap-y-2">
              <span className="text-xs font-medium text-slate-600 dark:text-slate-300">Sources</span>
              <Checkbox label="Google" checked={sources.google} onChange={(v) => setSources((s) => ({ ...s, google: v }))} />
              <Checkbox label="Bing" checked={sources.bing} onChange={(v) => setSources((s) => ({ ...s, bing: v }))} />
              <Checkbox label="DuckDuckGo" checked={sources.duckduckgo} onChange={(v) => setSources((s) => ({ ...s, duckduckgo: v }))} />
            </div>
            <Button type="submit" variant="primary" loading={suggest.isPending} disabled={!seed.trim() || !activeSources.length} icon={<Search className="h-4 w-4" />}>Get suggestions</Button>
          </div>
          {!activeSources.length && <p className="text-xs text-amber-700 dark:text-amber-300">Select at least one source.</p>}
        </form>
      </Card>

      {suggest.isPending && <Card><Spinner label={depth === "deep" ? "Collecting suggestions (deep mode can take a minute)…" : "Collecting suggestions…"} /></Card>}
      {suggest.error && <ErrorBox error={suggest.error} onRetry={() => suggest.mutate()} />}

      {result && !suggest.isPending && (
        <>
          {errors.length > 0 && (
            <Notice tone="warn">
              <p className="font-medium">Some sources failed and are missing from the results:</p>
              <ul className="mt-1 list-disc pl-5">{errors.map(([s, m]) => <li key={s}><span className="font-medium">{s}</span>: {m}</li>)}</ul>
            </Notice>
          )}
          {(result.data_notes ?? []).length > 0 && (
            <Notice>
              <ul className="list-disc space-y-0.5 pl-5">{result.data_notes.map((n: string) => <li key={n}>{n}</li>)}</ul>
            </Notice>
          )}
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <Stat label="Suggestions" value={fmtInt(all.length)} hint={`for "${result.seed}"`} />
            <Stat label="Questions" value={fmtInt(all.filter((k) => k.type === "question").length)} />
            <Stat label="Clusters" value={fmtInt((result.clusters ?? []).length)} tooltip="Lexical grouping by shared stemmed terms. At most 60 clusters are returned." />
            <Stat label="Autocomplete requests" value={fmtInt(result.queries)} hint={Object.keys(result.sources ?? {}).join(", ")} />
          </div>

          <Card padded={false}
            title={<span className="inline-flex gap-1">
              {(["keywords", "clusters"] as const).map((v) => (
                <button key={v} onClick={() => setView(v)} aria-pressed={view === v}
                  className={`rounded-md px-2 py-1 text-xs font-medium ${view === v ? "bg-brand-600 text-white" : "text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800"}`}>
                  {v === "keywords" ? `Keywords (${all.length})` : `Clusters (${(result.clusters ?? []).length})`}
                </button>
              ))}
            </span>}
            actions={view === "keywords" ? (
              <>
                <Button size="sm" icon={<Download className="h-3.5 w-3.5" />} disabled={!visible.length}
                  onClick={() => downloadCsv(`keywords-${result.seed.replace(/[^a-z0-9]+/gi, "-")}.csv`,
                    ["keyword", "type", "intent (estimate)", "intent confidence", "sources", "words", "search volume"],
                    visible.map((k) => [k.keyword, k.type, k.intent, k.intent_confidence, (k.sources ?? []).join(" "), k.words, k.search_volume ?? "unavailable"]))}>
                  CSV ({visible.length})
                </Button>
                <Button size="sm" variant="primary" icon={<Save className="h-3.5 w-3.5" />} loading={save.isPending} disabled={!site || !selected.size}
                  title={site ? undefined : "Add a website first to save keywords"} onClick={() => save.mutate(Array.from(selected))}>
                  Save selected to site{selected.size ? ` (${selected.size})` : ""}
                </Button>
              </>
            ) : undefined}>
            {view === "keywords" ? (
              <>
                <div className="flex flex-wrap items-center gap-2 border-b border-slate-100 p-3 dark:border-slate-800">
                  <SearchInput value={q} onChange={(v) => { setQ(v); setPage(1); }} placeholder="Filter keywords…" />
                  <Select className="w-auto" value={type} onChange={(e) => { setType(e.target.value); setPage(1); }} aria-label="Filter by type">
                    <option value="">All types</option>
                    {TYPES.map((t) => <option key={t} value={t}>{t === "question" ? "Questions" : t}</option>)}
                  </Select>
                  <Select className="w-auto" value={intent} onChange={(e) => { setIntent(e.target.value); setPage(1); }} aria-label="Filter by intent">
                    <option value="">All intents</option>
                    {INTENTS.map((t) => <option key={t} value={t}>{t}</option>)}
                  </Select>
                  {!site && <span className="text-xs text-slate-500 dark:text-slate-400">Add a website to save keywords.</span>}
                </div>
                {save.error && <div className="p-3"><ErrorBox error={save.error} /></div>}
                {save.data && <div className="p-3"><Notice tone="success">{save.data.added} new keyword{save.data.added === 1 ? "" : "s"} saved to {site?.name}. The site now has {save.data.total} saved keywords.</Notice></div>}
                <DataTable dense columns={columns} rows={pageRows} rowKey={(k) => k.keyword}
                  empty={<EmptyState title={all.length ? "No keywords match the filters" : "No suggestions returned"}
                    description={all.length ? "Clear or change the filters above." : "The selected sources returned nothing for this seed. Try a broader seed or another language/country."} />} />
                {visible.length > 0 && <Pagination page={page} perPage={PER_PAGE} total={visible.length} onPage={setPage} />}
              </>
            ) : (
              <div className="p-4"><ClusterGrid clusters={result.clusters ?? []} /></div>
            )}
          </Card>
        </>
      )}

      {!result && !suggest.isPending && !suggest.error && (
        <Card><EmptyState icon={<Search className="h-6 w-6" />} title="Enter a seed keyword"
          description="Suggestions come live from autocomplete endpoints. Search volume is never invented: it is only shown when you import it." /></Card>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ saved */
function SavedTab() {
  const { site } = useSite();
  const qc = useQueryClient();
  const siteId = site?.id;
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [adding, setAdding] = useState(false);
  const [manual, setManual] = useState("");

  const list = useQuery({ queryKey: ["keywords", siteId], queryFn: () => api.get(`/sites/${siteId}/keywords`), enabled: !!siteId });
  const invalidate = () => {
    void qc.invalidateQueries({ queryKey: ["keywords", siteId] });
    void qc.invalidateQueries({ queryKey: ["keyword-mapping", siteId] });
  };
  const add = useMutation({
    mutationFn: (keywords: string[]) => api.post(`/sites/${siteId}/keywords`, { keywords, source: "manual" }),
    onSuccess: () => { setManual(""); invalidate(); },
  });
  const importCsv = useMutation({ mutationFn: (file: File) => api.upload(`/sites/${siteId}/keywords/import`, file), onSuccess: invalidate });
  const remove = useMutation({
    mutationFn: (ids: number[]) => api.del(`/sites/${siteId}/keywords`, ids),
    onSuccess: () => { setSelected(new Set()); invalidate(); },
  });

  const items: any[] = list.data?.items ?? [];
  const visible = useMemo(() => {
    const needle = q.trim().toLowerCase();
    return needle ? items.filter((k) => k.keyword.includes(needle) || (k.cluster ?? "").includes(needle)) : items;
  }, [items, q]);

  if (!site) return <NeedsCrawl hasSite={false} />;

  const pageRows = visible.slice((page - 1) * PER_PAGE, page * PER_PAGE);
  const allSelected = visible.length > 0 && visible.every((k) => selected.has(k.id));
  const toggle = (id: number, on: boolean) => setSelected((s) => { const n = new Set(s); if (on) n.add(id); else n.delete(id); return n; });
  const manualList = parseLines(manual);
  const legend = (list.data?.legend ?? {}) as Record<string, string>;
  const dash = <span className="text-slate-400">–</span>;

  const columns: Column<any>[] = [
    { key: "sel", width: "32px", header: <RowCheck label="Select all" checked={allSelected} onChange={(on) => setSelected(on ? new Set(visible.map((k) => k.id)) : new Set())} />,
      render: (k) => <RowCheck label={`Select ${k.keyword}`} checked={selected.has(k.id)} onChange={(v) => toggle(k.id, v)} /> },
    { key: "keyword", header: "Keyword", render: (k) => <span className="font-medium text-slate-900 dark:text-slate-100">{k.keyword}</span> },
    { key: "cluster", header: "Cluster", tooltip: "Lexical cluster label, recomputed whenever keywords are added", render: (k) => (k.cluster ? <Chip>{k.cluster}</Chip> : dash) },
    { key: "intent", header: <span className="inline-flex items-center gap-1.5">Intent <DataBadge kind="estimated" /></span>, render: (k) => <IntentBadge intent={k.intent} /> },
    { key: "clicks", header: <span className="inline-flex items-center gap-1.5">Clicks <DataBadge kind="measured" /></span>, align: "right", render: (k) => (k.gsc ? fmtInt(k.gsc.clicks) : dash) },
    { key: "impressions", header: "Impressions", align: "right", tooltip: "Google Search Console, measured", render: (k) => (k.gsc ? fmtInt(k.gsc.impressions) : dash) },
    { key: "position", header: "Avg position", align: "right", tooltip: "Google Search Console, impression-weighted average", render: (k) => (k.gsc && k.gsc.position !== null ? fmtNum(k.gsc.position) : dash) },
    { key: "volume", header: <span className="inline-flex items-center gap-1.5">Volume <DataBadge kind="imported" /></span>, align: "right",
      render: (k) => (k.volume_status === "imported" ? fmtInt(k.search_volume) : <DataBadge kind="unavailable" />) },
    { key: "competition", header: "Competition", tooltip: "From your imported file, shown as provided", render: (k) => k.imported?.competition ?? dash },
    { key: "source", header: "Source", render: (k) => <Badge>{k.source}</Badge> },
  ];

  return (
    <div className="space-y-4">
      {Object.keys(legend).length > 0 && (
        <Notice>
          <div className="flex flex-wrap gap-x-6 gap-y-1.5">
            {legend.gsc && <span className="inline-flex items-center gap-1.5"><DataBadge kind="measured" /> {legend.gsc}</span>}
            {legend.imported && <span className="inline-flex items-center gap-1.5"><DataBadge kind="imported" /> {legend.imported}</span>}
            {legend.unavailable && <span className="inline-flex items-center gap-1.5"><DataBadge kind="unavailable" /> {legend.unavailable}</span>}
            <span className="inline-flex items-center gap-1.5"><DataBadge kind="estimated" /> Intent labels are rule-based estimates</span>
          </div>
        </Notice>
      )}
      {list.data && !list.data.has_gsc_data && (
        <Notice tone="warn">No Search Console data for this site yet, so clicks, impressions and position are empty. <Link to="/search-console" className="font-medium underline">Connect or import Search Console data</Link>.</Notice>
      )}

      <Card padded={false} title={`Saved keywords for ${site.name}`}
        actions={<>
          <Button size="sm" icon={<Plus className="h-3.5 w-3.5" />} onClick={() => setAdding((a) => !a)}>Add keywords</Button>
          <FileButton label="Import Keyword Planner CSV" loading={importCsv.isPending} onFile={(f) => importCsv.mutate(f)} />
          <ExportMenu formats={[
            { label: "CSV", path: `/sites/${site.id}/keywords/export`, query: { format: "csv" } },
            { label: "Excel (XLSX, with page mapping)", path: `/sites/${site.id}/keywords/export`, query: { format: "xlsx" } },
          ]} />
        </>}>
        {adding && (
          <div className="space-y-2 border-b border-slate-100 p-3 dark:border-slate-800">
            <Field label="Keywords, one per line" hint={`${manualList.length} keyword${manualList.length === 1 ? "" : "s"} (max 2,000 per batch). Duplicates are skipped.`}>
              <Textarea rows={5} value={manual} onChange={(e) => setManual(e.target.value)} placeholder={"ergonomic office chair\nbest standing desk for small spaces"} />
            </Field>
            <div className="flex gap-2">
              <Button variant="primary" size="sm" loading={add.isPending} disabled={!manualList.length || manualList.length > 2000} onClick={() => add.mutate(manualList)}>Save keywords</Button>
              <Button variant="ghost" size="sm" onClick={() => setAdding(false)}>Close</Button>
            </div>
          </div>
        )}
        {(add.error || importCsv.error || remove.error || add.data || importCsv.data) && (
          <div className="space-y-2 p-3">
            {add.error && <ErrorBox error={add.error} />}
            {importCsv.error && <ErrorBox error={importCsv.error} />}
            {remove.error && <ErrorBox error={remove.error} />}
            {add.data && <Notice tone="success">{add.data.added} keyword{add.data.added === 1 ? "" : "s"} added ({add.data.total} saved in total).</Notice>}
            {importCsv.data && <Notice tone="success">Import finished: {importCsv.data.added} added, {importCsv.data.updated} updated with imported metrics.</Notice>}
          </div>
        )}
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 p-3 dark:border-slate-800">
          <SearchInput value={q} onChange={(v) => { setQ(v); setPage(1); }} placeholder="Filter by keyword or cluster…" />
          <Button size="sm" variant="danger" icon={<Trash2 className="h-3.5 w-3.5" />} disabled={!selected.size} loading={remove.isPending}
            onClick={() => remove.mutate(Array.from(selected))}>Delete selected{selected.size ? ` (${selected.size})` : ""}</Button>
        </div>
        {list.isLoading ? <Spinner /> : list.error ? <div className="p-3"><ErrorBox error={list.error} onRetry={() => list.refetch()} /></div> : (
          <>
            <DataTable dense columns={columns} rows={pageRows} rowKey={(k) => k.id}
              empty={<EmptyState title={items.length ? "No keywords match the filter" : "No saved keywords yet"}
                description={items.length ? "Clear the filter to see all keywords." : "Save suggestions from the Research tab, add keywords manually, or import a Google Ads Keyword Planner CSV (Keyword, Avg. monthly searches, Competition)."} />} />
            {visible.length > 0 && <Pagination page={page} perPage={PER_PAGE} total={visible.length} onPage={setPage} />}
          </>
        )}
      </Card>
    </div>
  );
}

/* ------------------------------------------------------------------ mapping */
function MappingTab() {
  const { site } = useSite();
  const siteId = site?.id;
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);
  const mapping = useQuery({ queryKey: ["keyword-mapping", siteId], queryFn: () => api.get(`/sites/${siteId}/keywords/mapping`), enabled: !!siteId });

  if (!site) return <NeedsCrawl hasSite={false} />;
  if (mapping.isLoading) return <Card><Spinner label="Scoring keywords against crawled pages…" /></Card>;
  if (mapping.error) return <ErrorBox error={mapping.error} onRetry={() => mapping.refetch()} />;

  const data = mapping.data ?? {};
  const items: any[] = data.items ?? [];
  const summary = (data.summary ?? {}) as Record<string, number>;
  const visible = status ? items.filter((i) => i.status === status) : items;
  const pageRows = visible.slice((page - 1) * PER_PAGE, page * PER_PAGE);
  const tone: Record<string, string> = { mapped: "green", "cannibalisation risk": "orange", "no matching page": "gray" };

  if (!data.crawl_id) {
    return <Card><EmptyState title="No completed crawl yet" description={data.message ?? "Run a crawl first so keywords can be mapped to pages."}
      action={<Link to="/crawler" className="text-sm font-medium text-brand-700 hover:underline dark:text-brand-300">Go to Crawler</Link>} /></Card>;
  }

  const columns: Column<any>[] = [
    { key: "keyword", header: "Keyword", render: (i) => <span className="font-medium text-slate-900 dark:text-slate-100">{i.keyword}</span> },
    { key: "status", header: "Status", render: (i) => <Badge tone={tone[i.status] ?? "gray"}>{i.status}</Badge> },
    { key: "best", header: "Best matching page", render: (i) => i.best_page ? (
      <div className="max-w-md">
        <Url href={i.best_page.url} label={shortUrl(i.best_page.url, site.url)} />
        <div className="text-xs text-slate-500 dark:text-slate-400">{i.best_page.title || "No title"} · relevance {fmtNum(i.best_page.score, 2)}</div>
      </div>
    ) : <span className="text-slate-400">No page reaches the relevance threshold</span> },
    { key: "competing", header: "Competing pages", tooltip: "Other pages whose relevance is within 85% of the best page", render: (i) => (i.competing_pages ?? []).length ? (
      <ul className="max-w-md space-y-1">
        {i.competing_pages.map((c: any) => (
          <li key={c.url}><Url href={c.url} label={shortUrl(c.url, site.url)} /> <span className="text-xs text-slate-500 dark:text-slate-400">({fmtNum(c.score, 2)})</span></li>
        ))}
      </ul>
    ) : <span className="text-slate-400">–</span> },
  ];

  return (
    <div className="space-y-4">
      <Notice>
        <span className="mr-1.5"><DataBadge kind="estimated" /></span>
        This is an on-page relevance estimate: each saved keyword is scored against the title, H1, URL, meta description and body text of the indexable pages in your latest crawl. It shows which page targets a keyword most strongly, not which page ranks for it. For measured cannibalisation, see <Link to="/search-console" className="font-medium underline">Search Console insights</Link>.
      </Notice>
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label="Mapped" value={fmtInt(summary.mapped ?? 0)} tone="good" hint="One clear best page" />
        <Stat label="Cannibalisation risk" value={fmtInt(summary["cannibalisation risk"] ?? 0)} tone={summary["cannibalisation risk"] ? "warn" : undefined} hint="Several pages compete" />
        <Stat label="No matching page" value={fmtInt(summary["no matching page"] ?? 0)} hint="Content gap candidates" />
        <Stat label="Pages considered" value={fmtInt(data.pages_considered)} hint="Indexable pages in the latest crawl" />
      </div>
      <Card padded={false} title="Keyword to page mapping" description="Up to 500 saved keywords are mapped."
        actions={<Select className="w-auto" value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }} aria-label="Filter by status">
          <option value="">All statuses</option>
          <option value="mapped">Mapped</option>
          <option value="cannibalisation risk">Cannibalisation risk</option>
          <option value="no matching page">No matching page</option>
        </Select>}>
        <DataTable columns={columns} rows={pageRows} rowKey={(i) => i.keyword}
          empty={<EmptyState title={items.length ? "No keywords with this status" : "No saved keywords to map"}
            description={items.length ? "Choose another status." : "Save keywords from the Research tab or add them under Saved keywords first."} />} />
        {visible.length > 0 && <Pagination page={page} perPage={PER_PAGE} total={visible.length} onPage={setPage} />}
      </Card>
    </div>
  );
}

/* ------------------------------------------------------------------ cluster tool */
function ClusterTab() {
  const [text, setText] = useState("");
  const [seed, setSeed] = useState("");
  const [threshold, setThreshold] = useState(0.5);
  const keywords = parseLines(text);
  const cluster = useMutation({ mutationFn: () => api.post("/keywords/cluster", { keywords, seed: seed.trim() || null, threshold }) });
  const clusters: any[] = cluster.data?.clusters ?? [];

  return (
    <div className="space-y-4">
      <Card title="Cluster a keyword list" description="Group any list of keywords by shared terms. Nothing is fetched from the web.">
        <div className="grid gap-4 lg:grid-cols-3">
          <Field label="Keywords, one per line" className="lg:col-span-2" hint={`${keywords.length} unique keyword${keywords.length === 1 ? "" : "s"} (max 3,000)`}>
            <Textarea rows={9} value={text} onChange={(e) => setText(e.target.value)} placeholder={"best running shoes\nrunning shoes for flat feet\ntrail running shoes women"} />
          </Field>
          <div className="space-y-4">
            <Field label="Seed to ignore (optional)" hint="Words from the seed are ignored so clusters reflect the modifiers.">
              <Input maxLength={120} value={seed} onChange={(e) => setSeed(e.target.value)} placeholder="running shoes" />
            </Field>
            <Field label={`Similarity threshold: ${threshold.toFixed(2)}`} hint="Lower merges more keywords into fewer, broader clusters. Higher keeps clusters tight.">
              <input type="range" min={0.1} max={1} step={0.05} value={threshold} onChange={(e) => setThreshold(Number(e.target.value))}
                className="w-full accent-brand-600" aria-label="Similarity threshold" />
            </Field>
            <Button variant="primary" icon={<Layers className="h-4 w-4" />} loading={cluster.isPending} disabled={!keywords.length || keywords.length > 3000} onClick={() => cluster.mutate()}>Cluster keywords</Button>
          </div>
        </div>
      </Card>
      {cluster.error && <ErrorBox error={cluster.error} onRetry={() => cluster.mutate()} />}
      {cluster.isPending && <Card><Spinner label="Clustering…" /></Card>}
      {cluster.data && !cluster.isPending && (
        <Card title={`${clusters.length} cluster${clusters.length === 1 ? "" : "s"}`}
          description={<span className="inline-flex flex-wrap items-center gap-1.5">Method: {cluster.data.method}. Dominant intent is a rule-based estimate. <DataBadge kind="estimated" /></span>}
          actions={<Button size="sm" icon={<Download className="h-3.5 w-3.5" />} disabled={!clusters.length}
            onClick={() => downloadCsv("keyword-clusters.csv", ["cluster", "cluster size", "dominant intent (estimate)", "keyword"],
              clusters.flatMap((c) => (c.keywords as string[]).map((k) => [c.label, c.size, c.dominant_intent, k])))}>CSV</Button>}>
          <ClusterGrid clusters={clusters} />
        </Card>
      )}
    </div>
  );
}

export default function Keywords() {
  const [tab, setTab] = useState<Tab>("research");
  return (
    <div>
      <PageHeader title="Keyword research"
        description="Discover keyword ideas from live autocomplete data, group them into clusters, and map them to your pages. Demand figures appear only when measured by Search Console or imported by you." />
      <Tabs<Tab> value={tab} onChange={setTab} tabs={[
        { id: "research", label: "Research" },
        { id: "saved", label: "Saved keywords" },
        { id: "mapping", label: "Page mapping & cannibalisation" },
        { id: "cluster", label: "Cluster tool" },
      ]} />
      {tab === "research" && <ResearchTab />}
      {tab === "saved" && <SavedTab />}
      {tab === "mapping" && <MappingTab />}
      {tab === "cluster" && <ClusterTab />}
    </div>
  );
}
