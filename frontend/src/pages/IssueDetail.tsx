import { keepPreviousData, useMutation, useQuery } from "@tanstack/react-query";
import { ArrowLeft, ArrowRight, Sparkles } from "lucide-react";
import { type ReactNode, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { Badge, Button, Card, type Column, DataTable, EmptyState, ErrorBox, NeedsCrawl, PageHeader, Pagination, SeverityBadge, Spinner, StatusCode, Url } from "../components/ui";
import { api } from "../lib/api";
import { useSite } from "../lib/context";
import { fmtBytes, fmtInt, fmtMs, shortUrl, titleCase } from "../lib/format";

/* ------------------------------------------------------------------ issue details renderer (shared with the page detail view) */
const isUrl = (v: unknown): v is string => typeof v === "string" && /^https?:\/\//i.test(v);
const LABELS: Record<string, string> = { ttfb_ms: "Time to first byte", other_urls: "Also on", points_to: "Which points to", x_robots_tag: "X-Robots-Tag", html_lang: "HTML lang", h1: "H1 headings", ids: "Duplicate ids" };
const label = (k: string) => LABELS[k] ?? titleCase(k);

function scalar(key: string, v: unknown, base?: string): ReactNode {
  if (typeof v === "boolean") return v ? "yes" : "no";
  if (typeof v === "number") return key.endsWith("_ms") ? fmtMs(v) : key === "bytes" ? fmtBytes(v) : fmtInt(v);
  if (isUrl(v)) return <Url href={v} label={shortUrl(v, base)} />;
  return String(v);
}

/** One object inside a list (a broken link, an image, an hreflang alternate…): URL first, then compact facts. */
function ObjectLine({ item, base }: { item: Record<string, any>; base?: string }) {
  const url = item.url ?? item.href ?? item.src;
  const rest = Object.entries(item).filter(([k, v]) => !["url", "href", "src", "status", "error"].includes(k) && v !== null && v !== undefined && v !== "" && !(Array.isArray(v) && !v.length));
  return (
    <span className="inline-flex flex-wrap items-center gap-x-1.5 gap-y-0.5">
      {isUrl(url) ? <Url href={url} label={shortUrl(url, base)} /> : url ? <span className="break-all">{String(url)}</span> : null}
      {(item.status != null || !!item.error) && <StatusCode code={item.status ?? null} error={item.error} />}
      {item.status == null && item.error && <span className="text-xs text-slate-500 dark:text-slate-400">{String(item.error)}</span>}
      {rest.map(([k, v]) => (
        <span key={k} className="text-xs text-slate-500 dark:text-slate-400">
          {label(k).toLowerCase()}: <span className="text-slate-700 dark:text-slate-300">{Array.isArray(v) ? v.map(String).join("; ") : typeof v === "object" ? Object.values(v).map(String).join(", ") : scalar(k, v, base)}</span>
        </span>
      ))}
    </span>
  );
}

function ListValue({ k, items, base }: { k: string; items: any[]; base?: string }) {
  const [all, setAll] = useState(false);
  if (k === "chain") {
    return (
      <span className="inline-flex flex-wrap items-center gap-x-1 gap-y-0.5">
        {items.map((c, i) => (
          <span key={i} className="inline-flex items-center gap-1">
            {i > 0 && <ArrowRight className="h-3 w-3 shrink-0 text-slate-400" />}
            {isUrl(c) ? <Url href={c} label={shortUrl(c, base)} /> : String(c)}
          </span>
        ))}
      </span>
    );
  }
  if (items.every((i) => typeof i !== "object" && !isUrl(i)) && items.join(", ").length < 90) return <>{items.map(String).join(", ")}</>;
  const shown = all ? items : items.slice(0, 4);
  return (
    <span className="block">
      <span className="block space-y-0.5">
        {shown.map((it, i) => (
          <span key={i} className="block">
            {it !== null && typeof it === "object" && !Array.isArray(it) ? <ObjectLine item={it} base={base} /> : isUrl(it) ? <Url href={it} label={shortUrl(it, base)} /> : <span className="break-words">{String(it)}</span>}
          </span>
        ))}
      </span>
      {items.length > 4 && (
        <button type="button" onClick={(e) => { e.stopPropagation(); setAll(!all); }} className="mt-0.5 text-xs font-medium text-brand-700 hover:underline dark:text-brand-300">
          {all ? "Show fewer" : `+${items.length - 4} more`}
        </button>
      )}
    </span>
  );
}

/** Readable rendering of an issue's `details` object. Never prints raw JSON. */
export function IssueDetails({ details, base }: { details: Record<string, any> | null | undefined; base?: string }) {
  const entries = Object.entries(details ?? {}).filter(([, v]) => v !== null && v !== undefined && v !== "" && !(Array.isArray(v) && !v.length));
  if (!entries.length) return <span className="text-slate-400">–</span>;
  // a `count` next to the list it counts is noise
  const hasList = entries.some(([, v]) => Array.isArray(v));
  return (
    <div className="max-w-[36rem] space-y-1 whitespace-normal break-words text-sm">
      {entries.filter(([k]) => !(k === "count" && hasList)).map(([k, v]) => (
        <div key={k}>
          <span className="text-xs font-medium text-slate-500 dark:text-slate-400">{label(k)}{Array.isArray(v) && v.length > 1 ? ` (${v.length})` : ""}: </span>
          {Array.isArray(v) ? <ListValue k={k} items={v} base={base} />
            : typeof v === "object" ? <ObjectLine item={v} base={base} />
            : <span className="text-slate-800 dark:text-slate-200">{scalar(k, v, base)}</span>}
        </div>
      ))}
    </div>
  );
}

/* ------------------------------------------------------------------ AI helper (shared with the page detail view) */
export function AiResult({ run, title = "AI suggestion" }: { run: { data?: any; error: unknown; isPending: boolean }; title?: string }) {
  if (run.isPending) return <Card title={title}><Spinner label="Asking the AI provider…" /></Card>;
  if (run.error) return <ErrorBox error={run.error} />;
  if (!run.data) return null;
  return (
    <Card title={title} description={[run.data.provider, run.data.model].filter(Boolean).join(" · ") || undefined}>
      <div className="prose-ai whitespace-pre-wrap break-words text-sm text-slate-700 dark:text-slate-300">{run.data.output}</div>
      {run.data.grounding && <p className="mt-3 border-t border-slate-100 pt-2 text-xs text-slate-500 dark:border-slate-800 dark:text-slate-400">{run.data.grounding}</p>}
    </Card>
  );
}

/* ------------------------------------------------------------------ page */
const backLink = (
  <Link to="/audit" className="mb-3 inline-flex items-center gap-1 text-sm font-medium text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-200">
    <ArrowLeft className="h-4 w-4" /> Back to Site Audit
  </Link>
);

export default function IssueDetail() {
  const { ruleId = "" } = useParams();
  const { site, crawlId, loading } = useSite();
  const navigate = useNavigate();
  const [page, setPage] = useState(1);
  const q = useQuery({
    queryKey: ["issue", crawlId, ruleId, page],
    queryFn: () => api.get(`/crawls/${crawlId}/issues/${encodeURIComponent(ruleId)}`, { page, per_page: 50 }),
    enabled: crawlId !== null,
    placeholderData: keepPreviousData,
  });
  const ai = useMutation({ mutationFn: () => api.post("/ai/run", { task: "explain_issue", crawl_id: crawlId, rule_id: ruleId }) });

  if (loading) return <Spinner />;
  if (crawlId === null) return <>{backLink}<PageHeader title="Issue" /><NeedsCrawl hasSite={!!site} running={!!site?.active_crawl} /></>;
  if (q.isLoading) return <>{backLink}<Spinner /></>;
  if (q.error) return <>{backLink}<ErrorBox error={q.error} onRetry={() => q.refetch()} /></>;

  const rule = q.data.rule;
  const columns: Column<any>[] = [
    { key: "url", header: "Affected URL", render: (i) => (
      <div className="max-w-[26rem] break-all">
        {i.page_id !== null ? <span className="font-medium text-brand-700 dark:text-brand-300">{shortUrl(i.url, site?.url)}</span>
          : <span className="inline-flex flex-wrap items-center gap-1.5"><Url href={i.url} label={shortUrl(i.url)} /><Badge>site-wide</Badge></span>}
      </div>
    ) },
    { key: "details", header: "Details", render: (i) => <IssueDetails details={i.details} base={site?.url} /> },
  ];

  return (
    <>
      {backLink}
      <PageHeader title={rule.title}
        description={<span className="inline-flex flex-wrap items-center gap-2"><SeverityBadge severity={rule.severity} /><Badge>{titleCase(rule.category)}</Badge>{rule.scope === "site" && <Badge tone="purple">site-wide check</Badge>}<span>{fmtInt(q.data.total)} affected</span></span>}
        actions={<Button icon={<Sparkles className="h-4 w-4" />} loading={ai.isPending} onClick={() => ai.mutate()} title="Optional. Needs an AI provider configured in Settings.">Explain with AI</Button>} />
      <div className="space-y-4">
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <Card title="Why it matters"><p className="text-sm leading-relaxed text-slate-700 dark:text-slate-300">{rule.description}</p></Card>
          <Card title="How to fix"><p className="text-sm leading-relaxed text-slate-700 dark:text-slate-300">{rule.fix}</p></Card>
        </div>
        <AiResult run={ai} title="AI explanation" />
        <Card title="Affected URLs" description={rule.scope === "site" ? "This check applies to the website as a whole." : "Select a row to open the page's full report."} padded={false}>
          <div className={q.isPlaceholderData ? "opacity-60 transition-opacity" : ""}>
            <DataTable columns={columns} rows={q.data.items} rowKey={(_, i) => i}
              onRowClick={(i) => { if (i.page_id !== null) navigate(`/pages/${crawlId}/${i.page_id}`); }}
              empty={<EmptyState title="No affected URLs" description="This issue does not occur in the latest crawl. It may have been fixed since you opened the audit." />} />
            <Pagination page={page} perPage={q.data.per_page} total={q.data.total} onPage={setPage} />
          </div>
        </Card>
      </div>
    </>
  );
}
