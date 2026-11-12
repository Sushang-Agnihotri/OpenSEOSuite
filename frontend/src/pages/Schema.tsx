import { useMutation, useQuery } from "@tanstack/react-query";
import { Check, CheckCircle2, Copy, XCircle } from "lucide-react";
import { type FormEvent, useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip as ChartTooltip, XAxis, YAxis } from "recharts";
import {
  Badge, Button, Card, chartColors, type Column, DataTable, EmptyState, ErrorBox, Field, Input, NeedsCrawl, Notice, PageHeader,
  Pagination, SearchInput, Select, Spinner, Stat, Tabs, Textarea, Url,
} from "../components/ui";
import { api } from "../lib/api";
import { useSite } from "../lib/context";
import { fmtInt, shortUrl, titleCase } from "../lib/format";

type TabId = "overview" | "validator" | "generator";
const TAB_IDS: TabId[] = ["overview", "validator", "generator"];
const tooltipStyle = { background: "#0f172a", border: "none", borderRadius: 8, color: "#f8fafc", fontSize: 12 } as const;
const axisTick = { fontSize: 12, fill: "#94a3b8" } as const;

/* ------------------------------------------------------------------ shared bits */
function CodeBlock({ code, label }: { code: string; label: string }) {
  const [copied, setCopied] = useState(false);
  const [failed, setFailed] = useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      setFailed(false);
      setTimeout(() => setCopied(false), 1800);
    } catch {
      setFailed(true);
    }
  };
  return (
    <div className="overflow-hidden rounded-lg border border-slate-200 dark:border-slate-800">
      <div className="flex items-center justify-between gap-2 border-b border-slate-200 bg-slate-50 px-3 py-1.5 dark:border-slate-800 dark:bg-slate-900/60">
        <span className="text-xs font-medium text-slate-600 dark:text-slate-300">{label}</span>
        <div className="flex items-center gap-2">
          {failed && <span className="text-xs text-red-600 dark:text-red-400">Copy blocked by the browser; select the text instead</span>}
          <Button size="sm" variant="ghost" onClick={copy} icon={copied ? <Check className="h-3.5 w-3.5 text-emerald-600" /> : <Copy className="h-3.5 w-3.5" />}>{copied ? "Copied" : "Copy"}</Button>
        </div>
      </div>
      <pre className="max-h-96 overflow-auto bg-white p-3 text-xs leading-relaxed text-slate-800 dark:bg-slate-950 dark:text-slate-200"><code>{code}</code></pre>
    </div>
  );
}

const LEVELS: { id: string; label: string; tone: string; help: string }[] = [
  { id: "error", label: "Errors", tone: "red", help: "Missing required properties. The item is not eligible for the rich result." },
  { id: "structure", label: "Structure problems", tone: "orange", help: "Problems with @context, @type or the shape of the item." },
  { id: "warning", label: "Warnings", tone: "amber", help: "Missing recommended properties. Valid, but less complete." },
];

function ValidationResult({ result }: { result: any }) {
  const findings: any[] = result?.findings ?? [];
  const parseErrors: string[] = result?.parse_errors ?? [];
  const valid = result?.valid ?? (result?.errors === 0);
  const types: string[] = result?.all_types ?? result?.types ?? [];
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        {valid ? (
          <span className="inline-flex items-center gap-1.5 text-sm font-semibold text-emerald-700 dark:text-emerald-400"><CheckCircle2 className="h-5 w-5" /> Valid</span>
        ) : (
          <span className="inline-flex items-center gap-1.5 text-sm font-semibold text-red-700 dark:text-red-400"><XCircle className="h-5 w-5" /> Invalid</span>
        )}
        <Badge tone={result?.errors ? "red" : "green"}>{fmtInt(result?.errors ?? 0)} error{result?.errors === 1 ? "" : "s"}</Badge>
        <Badge tone={result?.warnings ? "amber" : "gray"}>{fmtInt(result?.warnings ?? 0)} warning{result?.warnings === 1 ? "" : "s"}</Badge>
        {parseErrors.length > 0 && <Badge tone="red">{parseErrors.length} parse error{parseErrors.length === 1 ? "" : "s"}</Badge>}
      </div>
      <div>
        <div className="mb-1 text-xs font-medium uppercase tracking-wide text-slate-500 dark:text-slate-400">Types found</div>
        {types.length ? <div className="flex flex-wrap gap-1">{types.map((t) => <Badge key={t} tone="blue">{t}</Badge>)}</div>
          : <p className="text-sm text-slate-500 dark:text-slate-400">No JSON-LD items with an @type were found.</p>}
        {result?.microdata_types?.length > 0 && (
          <div className="mt-2 flex flex-wrap items-center gap-1 text-xs text-slate-500 dark:text-slate-400">Microdata (not validated): {result.microdata_types.map((t: string) => <Badge key={t}>{t}</Badge>)}</div>
        )}
      </div>
      {parseErrors.length > 0 && (
        <div>
          <div className="mb-1 text-xs font-medium uppercase tracking-wide text-slate-500 dark:text-slate-400">Parse errors</div>
          <ul className="space-y-1">{parseErrors.map((e, i) => <li key={i}><ErrorBox error={e} /></li>)}</ul>
        </div>
      )}
      {LEVELS.map((level) => {
        const group = findings.filter((f) => f.level === level.id);
        if (!group.length) return null;
        return (
          <div key={level.id}>
            <div className="mb-1 flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-slate-500 dark:text-slate-400">
              {level.label} <span className="rounded-full bg-slate-100 px-1.5 text-slate-600 dark:bg-slate-800 dark:text-slate-300">{group.length}</span>
            </div>
            <p className="mb-2 text-xs text-slate-500 dark:text-slate-400">{level.help}</p>
            <ul className="divide-y divide-slate-100 rounded-lg border border-slate-200 dark:divide-slate-800 dark:border-slate-800">
              {group.map((f, i) => (
                <li key={i} className="flex flex-wrap items-start gap-2 px-3 py-2 text-sm text-slate-700 dark:text-slate-300">
                  <Badge tone={level.tone}>{level.id}</Badge>
                  <span className="min-w-0 flex-1 break-words">{f.message}</span>
                  <code className="text-xs text-slate-400">{f.path}</code>
                </li>
              ))}
            </ul>
          </div>
        );
      })}
      {valid && findings.length === 0 && parseErrors.length === 0 && types.length > 0 && (
        <Notice tone="success">All required and recommended properties are present for the types this validator knows.</Notice>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ site overview */
function Overview({ onGenerate }: { onGenerate: (type: string) => void }) {
  const { site, crawlId } = useSite();
  const navigate = useNavigate();
  const q = useQuery({ queryKey: ["schema-report", crawlId], queryFn: () => api.get(`/crawls/${crawlId}/schema`), enabled: !!crawlId });
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState<"all" | "errors" | "warnings" | "recommended">("all");
  const [page, setPage] = useState(1);
  useEffect(() => setPage(1), [search, filter]);
  const perPage = 25;

  if (!crawlId) return <NeedsCrawl hasSite={!!site} running={!!site?.active_crawl} />;
  if (q.isLoading) return <Spinner label="Validating structured data…" />;
  if (q.error) return <ErrorBox error={q.error} onRetry={() => q.refetch()} />;
  const d = q.data ?? {};
  const types = Object.entries((d.types ?? {}) as Record<string, number>).map(([type, pages]) => ({ type, pages }));
  const pages: any[] = d.pages ?? [];
  const needle = search.trim().toLowerCase();
  const rows = pages.filter((p) =>
    (filter === "all" || (filter === "errors" && p.errors > 0) || (filter === "warnings" && p.warnings > 0) || (filter === "recommended" && p.recommended?.length > 0))
    && (!needle || p.url.toLowerCase().includes(needle) || (p.types ?? []).some((t: string) => t.toLowerCase().includes(needle))));

  const columns: Column<any>[] = [
    { key: "url", header: "URL", render: (p) => <div className="max-w-sm"><Url href={p.url} label={shortUrl(p.url, site?.url)} /></div> },
    {
      key: "types", header: "Types", render: (p) => (
        <div className="flex max-w-xs flex-wrap gap-1">
          {(p.types ?? []).map((t: string) => <Badge key={t} tone="blue">{t}</Badge>)}
          {(p.microdata ?? []).map((t: string) => <Badge key={`m-${t}`} title="Found as microdata">{t}</Badge>)}
          {!p.types?.length && !p.microdata?.length && <span className="text-slate-400">none</span>}
        </div>
      ),
    },
    { key: "errors", header: "Errors", align: "right", render: (p) => (p.errors ? <Badge tone="red">{p.errors}</Badge> : "0") },
    { key: "warnings", header: "Warnings", align: "right", render: (p) => (p.warnings ? <Badge tone="amber">{p.warnings}</Badge> : "0") },
    {
      key: "problems", header: "Problems", render: (p) => p.problems?.length ? (
        <ul className="max-w-sm list-disc space-y-0.5 pl-4 text-xs">{p.problems.map((m: string, i: number) => <li key={i} className="break-words">{m}</li>)}</ul>
      ) : <span className="text-slate-400">–</span>,
    },
    {
      key: "recommended", header: "Recommended types", tooltip: "Suggested from URL patterns, depth and headings. Click a type to open its template.", render: (p) => p.recommended?.length ? (
        <div className="flex max-w-xs flex-wrap gap-1">
          {p.recommended.map((r: any) => (
            <button key={r.type} title={`${r.reason}. Open the generator`} onClick={(e) => { e.stopPropagation(); onGenerate(r.type); }}
              className="rounded-md bg-violet-50 px-1.5 py-0.5 text-xs font-medium text-violet-700 ring-1 ring-inset ring-violet-600/20 hover:bg-violet-100 dark:bg-violet-950/50 dark:text-violet-300 dark:hover:bg-violet-900/50">
              + {r.type}
            </button>
          ))}
        </div>
      ) : <span className="text-slate-400">–</span>,
    },
  ];

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label="Schema types in use" value={fmtInt(types.length)} />
        <Stat label="Pages with errors" value={fmtInt(d.pages_with_errors)} tone={d.pages_with_errors ? "bad" : "good"} />
        <Stat label="Pages without schema" value={fmtInt(d.pages_without_schema)} tone={d.pages_without_schema ? "warn" : "good"} tooltip="HTML pages (200) with no JSON-LD and no microdata" />
        <Stat label="Pages with suggestions" value={fmtInt(pages.filter((p) => p.recommended?.length).length)} tooltip="Indexable pages where another schema type is likely to fit" />
      </div>
      <Card title="Types by number of pages">
        {types.length === 0 ? (
          <EmptyState title="No structured data found" description="None of the crawled pages contain JSON-LD. Use the Generator tab to create markup for your key pages." />
        ) : (
          <div style={{ height: Math.max(160, Math.min(types.length, 20) * 28 + 40) }} role="img" aria-label="Schema types by number of pages">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={types.slice(0, 20)} layout="vertical" margin={{ top: 4, right: 16, bottom: 4, left: 8 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#94a3b833" horizontal={false} />
                <XAxis type="number" allowDecimals={false} tick={axisTick} tickLine={false} axisLine={false} />
                <YAxis type="category" dataKey="type" width={150} tick={axisTick} tickLine={false} axisLine={{ stroke: "#94a3b855" }} />
                <ChartTooltip cursor={{ fill: "#94a3b822" }} contentStyle={tooltipStyle} labelStyle={{ color: "#f8fafc" }} itemStyle={{ color: "#f8fafc" }} />
                <Bar dataKey="pages" name="Pages" fill={chartColors[0]} radius={[0, 4, 4, 0]} maxBarSize={18} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </Card>
      <Card padded={false} title="Pages" description="Pages with structured data, markup problems or a recommended type"
        actions={
          <>
            <Select value={filter} onChange={(e) => setFilter(e.target.value as typeof filter)} aria-label="Filter pages" className="w-44">
              <option value="all">All pages</option>
              <option value="errors">With errors</option>
              <option value="warnings">With warnings</option>
              <option value="recommended">With suggestions</option>
            </Select>
            <SearchInput value={search} onChange={setSearch} placeholder="Filter by URL or type…" />
          </>
        }>
        <DataTable columns={columns} rows={rows.slice((page - 1) * perPage, page * perPage)} rowKey={(p) => p.page_id}
          onRowClick={(p) => navigate(`/pages/${crawlId}/${p.page_id}`)}
          empty={<EmptyState title={pages.length ? "No pages match" : "Nothing to report"} description={pages.length ? "Change the filter or search term." : "No page has structured data, problems or suggestions."} />} />
        {rows.length > 0 && <Pagination page={page} perPage={perPage} total={rows.length} onPage={setPage} />}
      </Card>
      {d.note && <Notice>{d.note}</Notice>}
    </div>
  );
}

/* ------------------------------------------------------------------ validator */
function Validator() {
  const { site } = useSite();
  const [mode, setMode] = useState<"url" | "jsonld">("url");
  const [url, setUrl] = useState<string | null>(null);
  const [jsonld, setJsonld] = useState("");
  const effectiveUrl = url ?? site?.url ?? "";
  const run = useMutation({ mutationFn: () => api.post("/schema/validate", mode === "url" ? { url: effectiveUrl.trim() } : { jsonld }) });
  const submit = (e: FormEvent) => {
    e.preventDefault();
    run.mutate();
  };
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Card title="Validate structured data" description="Check a live page or paste JSON-LD (with or without the <script> tag)">
        <form onSubmit={submit} className="space-y-4">
          <div className="inline-flex rounded-lg border border-slate-300 p-0.5 dark:border-slate-700" role="group" aria-label="Input type">
            {(["url", "jsonld"] as const).map((m) => (
              <button key={m} type="button" aria-pressed={mode === m} onClick={() => { setMode(m); run.reset(); }}
                className={mode === m ? "rounded-md bg-brand-600 px-3 py-1 text-xs font-medium text-white" : "rounded-md px-3 py-1 text-xs font-medium text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800"}>
                {m === "url" ? "By URL" : "Paste JSON-LD"}
              </button>
            ))}
          </div>
          {mode === "url" ? (
            <Field label="Page URL" hint="The page is fetched by the server and its JSON-LD blocks are extracted.">
              <Input type="url" required value={effectiveUrl} onChange={(e) => setUrl(e.target.value)} placeholder="https://example.com/product" />
            </Field>
          ) : (
            <Field label="JSON-LD" hint="A single object, an array, or an @graph document.">
              <Textarea required rows={14} spellCheck={false} value={jsonld} onChange={(e) => setJsonld(e.target.value)} className="font-mono text-xs"
                placeholder={'{\n  "@context": "https://schema.org",\n  "@type": "Organization",\n  "name": "Example"\n}'} />
            </Field>
          )}
          <Button type="submit" variant="primary" loading={run.isPending}>Validate</Button>
        </form>
      </Card>
      <Card title="Result">
        {run.isPending ? <Spinner label={mode === "url" ? "Fetching and validating…" : "Validating…"} />
          : run.error ? <ErrorBox error={run.error} onRetry={() => run.mutate()} />
          : run.data ? <ValidationResult result={run.data} />
          : <EmptyState title="No validation yet" description="Enter a URL or paste markup, then choose Validate. Checks cover required and recommended properties of common rich-result types." />}
      </Card>
    </div>
  );
}

/* ------------------------------------------------------------------ generator */
type Values = Record<string, any>;
const isStringList = (v: unknown): v is string[] => Array.isArray(v) && v.every((x) => typeof x === "string");
const isPlainObject = (v: unknown): v is Record<string, any> => typeof v === "object" && v !== null && !Array.isArray(v);
const simple = (v: unknown) => typeof v === "string" || typeof v === "number";
const labelOf = (key: string) => titleCase(key.replace(/([a-z])([A-Z])/g, "$1 $2"));

/** Turn the edited form state into the `values` payload. Nested objects are sent whole because the API replaces them wholesale. */
function buildValues(template: Record<string, any>, form: Values): Values {
  const out: Values = {};
  for (const [key, tv] of Object.entries(template)) {
    if (key.startsWith("@")) continue;
    const v = form[key];
    if (v === undefined) continue;
    if (simple(tv)) {
      if (String(v).trim() !== "") out[key] = typeof tv === "number" && !Number.isNaN(Number(v)) ? Number(v) : String(v).trim();
    } else if (isStringList(tv)) {
      const list = String(v).split(/[\n,]/).map((s) => s.trim()).filter(Boolean);
      if (list.length) out[key] = list;
    } else if (isPlainObject(tv) && isPlainObject(v)) {
      const edited = Object.entries(v).filter(([, x]) => String(x).trim() !== "");
      if (edited.length) out[key] = { ...tv, ...Object.fromEntries(edited.map(([k, x]) => [k, String(x).trim()])) };
    }
  }
  return out;
}

function Generator({ initialType }: { initialType: string | null }) {
  const typesQ = useQuery({ queryKey: ["schema-types"], queryFn: () => api.get("/schema/types") });
  const templates: string[] = typesQ.data?.templates ?? [];
  const [type, setType] = useState<string | null>(initialType);
  const active = type && templates.includes(type) ? type : templates[0] ?? null;
  const templateQ = useQuery({ queryKey: ["schema-template", active], queryFn: () => api.post("/schema/generate", { type: active, values: {} }), enabled: !!active, staleTime: Infinity });
  const [form, setForm] = useState<Values>({});
  const generate = useMutation({ mutationFn: (values: Values) => api.post("/schema/generate", { type: active, values }) });
  const { reset } = generate;
  useEffect(() => {
    setForm({});
    reset();
  }, [active, reset]);

  if (typesQ.isLoading) return <Spinner />;
  if (typesQ.error) return <ErrorBox error={typesQ.error} onRetry={() => typesQ.refetch()} />;
  if (!active) return <Card><EmptyState title="No templates available" description="The server did not return any schema templates." /></Card>;

  const template: Record<string, any> = templateQ.data?.jsonld ?? {};
  const spec = typesQ.data?.validated_types?.[active];
  const result = generate.data ?? templateQ.data;
  const keys = Object.keys(template).filter((k) => !k.startsWith("@"));
  const complex = keys.filter((k) => !simple(template[k]) && !isStringList(template[k]) && !(isPlainObject(template[k]) && Object.values(template[k]).some((v) => typeof v === "string")));
  const dirty = Object.keys(buildValues(template, form)).length > 0;
  const required = (key: string) => (spec?.required ?? []).includes(key);
  const submit = (e: FormEvent) => {
    e.preventDefault();
    generate.mutate(buildValues(template, form));
  };

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Card title="Template" description="Pick a type, fill in the fields, then generate the markup">
        <form onSubmit={submit} className="space-y-4">
          <Field label="Schema type">
            <Select value={active} onChange={(e) => setType(e.target.value)}>
              {templates.map((t) => <option key={t} value={t}>{t}</option>)}
            </Select>
          </Field>
          {spec && (
            <p className="text-xs text-slate-500 dark:text-slate-400">
              Required: <span className="font-medium text-slate-700 dark:text-slate-200">{spec.required.join(", ") || "none"}</span>
              {spec.recommended.length > 0 && <> · Recommended: {spec.recommended.join(", ")}</>}
            </p>
          )}
          {templateQ.isLoading ? <Spinner label="Loading template…" /> : templateQ.error ? <ErrorBox error={templateQ.error} onRetry={() => templateQ.refetch()} /> : (
            <>
              <div className="grid gap-3 sm:grid-cols-2">
                {keys.filter((k) => simple(template[k]) || isStringList(template[k])).map((key) => {
                  const list = isStringList(template[key]);
                  return (
                    <Field key={key} label={`${labelOf(key)}${required(key) ? " *" : ""}`} hint={list ? "Separate several values with commas" : undefined}>
                      <Input type={typeof template[key] === "number" ? "number" : "text"} value={form[key] ?? ""}
                        placeholder={list ? "" : String(template[key] ?? "")} onChange={(e) => setForm((f) => ({ ...f, [key]: e.target.value }))} />
                    </Field>
                  );
                })}
              </div>
              {keys.filter((k) => isPlainObject(template[k]) && !complex.includes(k)).map((key) => (
                <fieldset key={key} className="rounded-lg border border-slate-200 p-3 dark:border-slate-800">
                  <legend className="px-1 text-xs font-semibold text-slate-700 dark:text-slate-200">
                    {labelOf(key)}{required(key) ? " *" : ""} <span className="font-normal text-slate-400">{template[key]["@type"]}</span>
                  </legend>
                  <div className="grid gap-3 sm:grid-cols-2">
                    {Object.entries(template[key]).filter(([k, v]) => !k.startsWith("@") && typeof v === "string").map(([sub, def]) => (
                      <Field key={sub} label={labelOf(sub)}>
                        <Input value={form[key]?.[sub] ?? ""} placeholder={String(def)}
                          onChange={(e) => setForm((f) => ({ ...f, [key]: { ...(isPlainObject(f[key]) ? f[key] : {}), [sub]: e.target.value } }))} />
                      </Field>
                    ))}
                  </div>
                </fieldset>
              ))}
              {complex.length > 0 && (
                <p className="text-xs text-slate-500 dark:text-slate-400">
                  Nested lists ({complex.map(labelOf).join(", ")}) keep the template's structure. Edit them in the generated JSON-LD after copying.
                </p>
              )}
              <div className="flex flex-wrap items-center gap-2">
                <Button type="submit" variant="primary" loading={generate.isPending}>Generate markup</Button>
                <Button type="button" variant="ghost" disabled={!dirty && !generate.data} onClick={() => { setForm({}); generate.reset(); }}>Reset fields</Button>
                {generate.data && dirty && <span className="text-xs text-slate-500 dark:text-slate-400">Generate again after changing fields.</span>}
              </div>
              {generate.error ? <ErrorBox error={generate.error} /> : null}
            </>
          )}
        </form>
      </Card>
      <div className="space-y-4">
        <Card title="Generated markup" description="Paste the HTML snippet into the page's <head> or <body>">
          {!result ? (templateQ.error ? <EmptyState title="No markup" description="The template could not be loaded." /> : <Spinner />) : (
            <div className="space-y-3">
              <CodeBlock label="HTML snippet" code={result.html} />
              <CodeBlock label="JSON-LD" code={JSON.stringify(result.jsonld, null, 2)} />
            </div>
          )}
        </Card>
        {result?.validation && (
          <Card title="Validation of the generated markup" description="Empty template fields count as missing">
            <ValidationResult result={result.validation} />
          </Card>
        )}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ page */
export default function Schema() {
  const [params, setParams] = useSearchParams();
  const raw = params.get("tab") as TabId | null;
  const tab: TabId = raw && TAB_IDS.includes(raw) ? raw : "overview";
  const go = (id: TabId, type?: string) => {
    const next: Record<string, string> = id === "overview" ? {} : { tab: id };
    if (type) next.type = type;
    setParams(next, { replace: true });
  };
  return (
    <>
      <PageHeader title="Structured data" description="Audit the schema.org markup found by the crawl, validate any page or snippet, and generate JSON-LD from templates." />
      <Tabs<TabId> value={tab} onChange={(id) => go(id)} tabs={[
        { id: "overview", label: "Site overview" },
        { id: "validator", label: "Validator" },
        { id: "generator", label: "Generator" },
      ]} />
      {tab === "overview" && <Overview onGenerate={(type) => go("generator", type)} />}
      {tab === "validator" && <Validator />}
      {tab === "generator" && <Generator key={params.get("type") ?? ""} initialType={params.get("type")} />}
    </>
  );
}
