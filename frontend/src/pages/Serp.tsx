import { useMutation, useQuery } from "@tanstack/react-query";
import { Search, Sparkles } from "lucide-react";
import { type FormEvent, type ReactNode, useState } from "react";
import { Link } from "react-router-dom";
import {
  Badge, Button, Card, type Column, DataBadge, DataTable, EmptyState, ErrorBox, Field, Input, Notice, PageHeader, ScoreRing, Spinner, Stat, Textarea, Url,
} from "../components/ui";
import { api, ApiError } from "../lib/api";
import { fmtInt, fmtPct, titleCase } from "../lib/format";

const INTENT_TONE: Record<string, string> = { transactional: "green", commercial: "purple", navigational: "blue", local: "orange", informational: "gray" };
const COMPONENT_MAX: Record<string, number> = { authority_domains: 40, homepage_results: 15, optimised_titles: 25, content_depth: 20 };
const COMPONENT_HELP: Record<string, string> = {
  authority_domains: "Share of top results on very large or .gov/.edu domains",
  homepage_results: "Share of top results that are homepages",
  optimised_titles: "Share of result titles containing every keyword term",
  content_depth: "Average word count of the fetched ranking pages (caps at 2,500 words)",
};

function Chip({ children, title }: { children: ReactNode; title?: string }) {
  return <span title={title} className="inline-flex items-center gap-1 rounded-md border border-slate-200 bg-slate-50 px-1.5 py-0.5 text-xs text-slate-700 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300">{children}</span>;
}

function parseLines(text: string): string[] {
  return Array.from(new Set(text.split(/\r?\n/).map((l) => l.trim()).filter(Boolean)));
}

const termColumns: Column<any>[] = [
  { key: "term", header: "Term", render: (t) => <span className="font-medium text-slate-900 dark:text-slate-100">{t.term}</span> },
  { key: "documents", header: "Pages", align: "right", tooltip: "Number of analysed ranking pages using the term", render: (t) => t.documents },
  { key: "share", header: "Share", align: "right", render: (t) => fmtPct(t.share, 0) },
  { key: "avg", header: "Avg uses", align: "right", tooltip: "Average occurrences on the pages that use it", render: (t) => t.avg_count },
];

function AiBrief({ keyword, serp }: { keyword: string; serp: any }) {
  const run = useMutation({ mutationFn: () => api.post("/ai/run", { task: "content_brief", keyword, serp }) });
  return (
    <Card title="AI content brief" description="Generated only from the analysis on this page by the AI provider you configured."
      actions={<Button size="sm" variant="primary" icon={<Sparkles className="h-3.5 w-3.5" />} loading={run.isPending} onClick={() => run.mutate()}>Generate content brief with AI</Button>}>
      {run.isPending ? <Spinner label="Writing the brief…" /> : run.error ? (
        <div className="space-y-2">
          <ErrorBox error={run.error} onRetry={() => run.mutate()} />
          {run.error instanceof ApiError && run.error.status === 400 && (
            <p className="text-xs text-slate-500 dark:text-slate-400">AI features are optional and need a provider (Ollama or an OpenAI-compatible endpoint). <Link to="/settings" className="font-medium text-brand-700 hover:underline dark:text-brand-300">Configure it in Settings</Link>.</p>
          )}
        </div>
      ) : run.data ? (
        <div className="space-y-3">
          <div className="prose-ai whitespace-pre-wrap text-sm text-slate-700 dark:text-slate-300">{run.data.output}</div>
          <p className="border-t border-slate-100 pt-2 text-xs text-slate-500 dark:border-slate-800 dark:text-slate-400">
            {run.data.provider}{run.data.model ? ` · ${run.data.model}` : ""}. {run.data.grounding}
          </p>
        </div>
      ) : (
        <p className="text-sm text-slate-500 dark:text-slate-400">Turns the heading topics, common terms, questions and ranking-page stats above into an outline for a new page.</p>
      )}
    </Card>
  );
}

function Difficulty({ d }: { d: any }) {
  if (!d || d.score === null || d.score === undefined) {
    return (
      <Card title={<span className="inline-flex items-center gap-2">Difficulty <DataBadge kind="unavailable" /></span>}>
        <p className="text-sm text-slate-500 dark:text-slate-400">{d?.reason ?? "No SERP data"}. No difficulty value is shown rather than guessing one.</p>
      </Card>
    );
  }
  const inputs = d.inputs ?? {};
  return (
    <Card title={<span className="inline-flex items-center gap-2">Difficulty estimate <DataBadge kind="estimated" /></span>}>
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center">
        <div className="flex shrink-0 flex-col items-center gap-1.5">
          <ScoreRing score={d.score} label="of 100" />
          <Badge tone={d.label === "hard" ? "red" : d.label === "medium" ? "amber" : "green"}>{d.label}</Badge>
        </div>
        <div className="min-w-0 flex-1 space-y-2.5">
          {Object.entries((d.components ?? {}) as Record<string, number>).map(([k, v]) => {
            const max = COMPONENT_MAX[k] ?? 100;
            return (
              <div key={k} title={COMPONENT_HELP[k]}>
                <div className="mb-1 flex justify-between text-xs text-slate-600 dark:text-slate-300">
                  <span>{titleCase(k)}</span><span className="tabular-nums">{v} / {max}</span>
                </div>
                <div className="h-1.5 overflow-hidden rounded-full bg-slate-200 dark:bg-slate-800">
                  <div className="h-full rounded-full bg-brand-600" style={{ width: `${Math.min(100, (v / max) * 100)}%` }} />
                </div>
              </div>
            );
          })}
        </div>
      </div>
      <p className="mt-3 text-xs text-slate-500 dark:text-slate-400">
        {d.method} Not comparable to link-based difficulty scores from other tools. Inputs: {inputs.results_considered} results considered, {inputs.authority_domains} on authority domains, {inputs.homepage_results} homepages, {inputs.titles_matching_keyword} titles matching the keyword, average word count {inputs.avg_word_count ?? "n/a"}.
      </p>
    </Card>
  );
}

export default function Serp() {
  const providers = useQuery({ queryKey: ["serp-providers"], queryFn: () => api.get("/serp/providers") });
  const [keyword, setKeyword] = useState("");
  const [country, setCountry] = useState("us");
  const [lang, setLang] = useState("en");
  const [myUrl, setMyUrl] = useState("");
  const [urlText, setUrlText] = useState("");

  const urls = parseLines(urlText);
  const configured: string | undefined = providers.data?.configured;
  const hasProvider = !!configured && configured !== "none";
  const analyze = useMutation({
    mutationFn: () => api.post("/serp/analyze", { keyword: keyword.trim(), country: country.trim().toLowerCase(), lang: lang.trim().toLowerCase(), urls, my_url: myUrl.trim() || null }),
  });
  const r = analyze.data;
  const canSubmit = !!keyword.trim() && urls.length <= 20 && (hasProvider || urls.length > 0);
  const submit = (e: FormEvent) => { e.preventDefault(); if (canSubmit) analyze.mutate(); };

  const resultColumns: Column<any>[] = [
    { key: "pos", header: "#", align: "right", width: "40px", render: (x) => x.position },
    { key: "page", header: "Result", render: (x) => (
      <div className="max-w-md">
        <div className="font-medium text-slate-900 dark:text-slate-100">{x.title || <span className="font-normal text-slate-400">No title available</span>}</div>
        <Url href={x.url} className="text-xs" />
        <div className="mt-1 flex flex-wrap gap-1">
          {x.is_homepage && <Badge tone="blue">homepage</Badge>}
          {x.error && <Badge tone="red" title={x.error}>fetch failed: {x.error}</Badge>}
        </div>
      </div>
    ) },
    { key: "words", header: "Words", align: "right", render: (x) => fmtInt(x.word_count) },
    { key: "tl", header: "Title length", align: "right", render: (x) => (x.title ? x.title_length : "–") },
    { key: "h2", header: "H2s", align: "right", render: (x) => (x.fetched ? x.h2_count : "–") },
    { key: "schema", header: "Schema types", render: (x) => (x.schema_types ?? []).length
      ? <span className="flex max-w-xs flex-wrap gap-1">{x.schema_types.map((t: string) => <Chip key={t}>{t}</Chip>)}</span> : <span className="text-slate-400">–</span> },
  ];

  const summary = r?.summary ?? {};
  const gaps = r?.content_gaps;
  const schemaCounts = Object.entries((summary.schema_types ?? {}) as Record<string, number>);
  const resultTypes = Object.entries((r?.result_types ?? {}) as Record<string, number>);

  return (
    <div>
      <PageHeader title="SERP analysis"
        description="See what the pages ranking for a keyword have in common: length, headings, terms, questions and structured data. Result pages are fetched and measured by this toolkit; search engines are never scraped." />

      <div className="space-y-4">
        {providers.isLoading ? <Card><Spinner label="Checking SERP provider…" /></Card> : providers.error ? <ErrorBox error={providers.error} onRetry={() => providers.refetch()} /> : hasProvider ? (
          <Notice tone="success">SERP provider: <span className="font-medium">{providers.data.providers?.[configured!] ?? configured}</span>. Leave the manual URL box empty to query it, or paste URLs to override.</Notice>
        ) : (
          <Notice tone="warn">
            No SERP provider is configured, so paste the ranking URLs manually below. To fetch results automatically, add SearXNG, Google Programmable Search or Brave Search in <Link to="/settings" className="font-medium underline">Settings</Link>.
          </Notice>
        )}

        <Card title="Analyse a keyword">
          <form onSubmit={submit} className="space-y-4">
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-12">
              <Field label="Keyword" className="sm:col-span-2 lg:col-span-5">
                <Input required maxLength={200} value={keyword} onChange={(e) => setKeyword(e.target.value)} placeholder="e.g. how to descale a kettle" />
              </Field>
              <Field label="Country" hint="2-letter code" className="lg:col-span-2">
                <Input required pattern="[A-Za-z]{2}" maxLength={2} value={country} onChange={(e) => setCountry(e.target.value)} />
              </Field>
              <Field label="Language" hint="2-letter code" className="lg:col-span-2">
                <Input required pattern="[A-Za-z]{2}" maxLength={2} value={lang} onChange={(e) => setLang(e.target.value)} />
              </Field>
              <Field label="My URL (optional)" hint="Adds a content-gap comparison" className="sm:col-span-2 lg:col-span-3">
                <Input type="url" maxLength={2048} value={myUrl} onChange={(e) => setMyUrl(e.target.value)} placeholder="https://example.com/page" />
              </Field>
            </div>
            <Field label={hasProvider ? "Result URLs (optional, overrides the provider)" : "Result URLs, one per line, in ranking order"}
              hint={`${urls.length} / 20 URLs. Positions follow the order you enter.`}>
              <Textarea rows={5} value={urlText} onChange={(e) => setUrlText(e.target.value)} placeholder={"https://first-result.example/page\nhttps://second-result.example/guide"} className="font-mono text-xs" />
            </Field>
            <div className="flex flex-wrap items-center gap-3">
              <Button type="submit" variant="primary" icon={<Search className="h-4 w-4" />} loading={analyze.isPending} disabled={!canSubmit}>Analyse SERP</Button>
              {urls.length > 20 && <span className="text-xs text-red-600 dark:text-red-400">At most 20 URLs.</span>}
              {!hasProvider && !urls.length && !providers.isLoading && <span className="text-xs text-slate-500 dark:text-slate-400">Paste at least one result URL.</span>}
            </div>
          </form>
        </Card>

        {analyze.isPending && <Card><Spinner label="Fetching and analysing the ranking pages…" /></Card>}
        {analyze.error && <ErrorBox error={analyze.error} onRetry={() => analyze.mutate()} />}
        {!r && !analyze.isPending && !analyze.error && (
          <Card><EmptyState icon={<Search className="h-6 w-6" />} title="No analysis yet" description="Enter a keyword to analyse the pages that rank for it." /></Card>
        )}

        {r && !analyze.isPending && (
          <>
            {r.source && <Notice><span className="font-medium">Source: {r.source.provider}.</span> {r.source.note}</Notice>}

            <div className="grid gap-4 lg:grid-cols-2">
              <Card title="Search intent & SERP features">
                <div className="space-y-4 text-sm">
                  <div>
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge tone={INTENT_TONE[r.intent?.intent] ?? "gray"}>{r.intent?.intent}</Badge>
                      <DataBadge kind="estimated" />
                      <span className="text-xs text-slate-500 dark:text-slate-400">confidence {fmtPct(r.intent?.confidence, 0)} · {r.intent?.method}</span>
                    </div>
                    {(r.intent?.signals ?? []).length > 0 && (
                      <div className="mt-2 flex flex-wrap items-center gap-1 text-xs text-slate-500 dark:text-slate-400">Signals: {r.intent.signals.map((s: string) => <Chip key={s}>{s}</Chip>)}</div>
                    )}
                  </div>
                  <div>
                    <div className="mb-1.5 text-xs font-medium uppercase tracking-wide text-slate-500 dark:text-slate-400">SERP features reported</div>
                    {(r.features ?? []).length ? <div className="flex flex-wrap gap-1">{r.features.map((f: string) => <Badge key={f} tone="purple">{f}</Badge>)}</div>
                      : <span className="text-slate-500 dark:text-slate-400">None reported</span>}
                    <p className="mt-1.5 text-xs text-slate-500 dark:text-slate-400">{r.feature_note}</p>
                  </div>
                  <div>
                    <div className="mb-1.5 text-xs font-medium uppercase tracking-wide text-slate-500 dark:text-slate-400">Result types</div>
                    {resultTypes.length ? <div className="flex flex-wrap gap-1">{resultTypes.map(([k, v]) => <Chip key={k} title="Classified from URL paths">{k} <span className="font-semibold tabular-nums">{v}</span></Chip>)}</div>
                      : <span className="text-slate-500 dark:text-slate-400">No results</span>}
                  </div>
                </div>
              </Card>
              <Difficulty d={r.difficulty} />
            </div>

            <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
              <Stat label="Pages analysed" value={fmtInt(summary.pages_analysed)} hint={<span className="inline-flex items-center gap-1">fetched by this toolkit <DataBadge kind="measured" /></span>} />
              <Stat label="Avg word count" value={fmtInt(summary.avg_word_count)} />
              <Stat label="Median word count" value={fmtInt(summary.median_word_count)} />
              <Stat label="Avg title length" value={summary.avg_title_length ? `${summary.avg_title_length} chars` : "–"} />
            </div>

            {gaps ? (
              <Card title="Content gaps for your page" description={<Url href={myUrl.trim()} />}>
                <div className="grid gap-5 md:grid-cols-2">
                  <div>
                    <div className="mb-1 text-xs font-medium uppercase tracking-wide text-slate-500 dark:text-slate-400">Word count vs competitors</div>
                    <div className="text-sm text-slate-700 dark:text-slate-300">
                      Your page: <span className="font-semibold tabular-nums">{fmtInt(gaps.word_count)}</span> words · competitor median: <span className="font-semibold tabular-nums">{fmtInt(gaps.median_competitor_words)}</span>
                      {gaps.word_count !== null && gaps.median_competitor_words ? (
                        <Badge tone={gaps.word_count >= gaps.median_competitor_words * 0.8 ? "green" : "amber"}>
                          {Math.round((gaps.word_count / gaps.median_competitor_words) * 100)}% of median
                        </Badge>
                      ) : null}
                    </div>
                    <div className="mb-1 mt-4 text-xs font-medium uppercase tracking-wide text-slate-500 dark:text-slate-400">Schema types used by 2+ competitors that you lack</div>
                    {(gaps.missing_schema_types ?? []).length ? <div className="flex flex-wrap gap-1">{gaps.missing_schema_types.map((t: string) => <Badge key={t} tone="amber">{t}</Badge>)}</div>
                      : <span className="text-sm text-slate-500 dark:text-slate-400">None</span>}
                  </div>
                  <div>
                    <div className="mb-1 text-xs font-medium uppercase tracking-wide text-slate-500 dark:text-slate-400">Terms used by 40%+ of competitors, missing on your page</div>
                    {(gaps.missing_terms ?? []).length ? <div className="flex flex-wrap gap-1">{gaps.missing_terms.map((t: any) => <Chip key={t.term} title={`${t.documents} pages`}>{t.term} <span className="text-slate-400">{fmtPct(t.share, 0)}</span></Chip>)}</div>
                      : <span className="text-sm text-slate-500 dark:text-slate-400">None</span>}
                    <div className="mb-1 mt-4 text-xs font-medium uppercase tracking-wide text-slate-500 dark:text-slate-400">Heading topics missing from your headings</div>
                    {(gaps.missing_heading_topics ?? []).length ? <div className="flex flex-wrap gap-1">{gaps.missing_heading_topics.map((t: any) => <Chip key={t.term} title={`${t.documents} pages`}>{t.term} <span className="text-slate-400">{fmtPct(t.share, 0)}</span></Chip>)}</div>
                      : <span className="text-sm text-slate-500 dark:text-slate-400">None</span>}
                  </div>
                </div>
              </Card>
            ) : myUrl.trim() ? (
              <Notice tone="warn">Your URL could not be fetched as an HTML page, so no content-gap comparison is available.</Notice>
            ) : null}

            <Card padded={false} title={`Results (${(r.results ?? []).length})`} description="Word count, headings and schema are measured from each fetched page.">
              <DataTable columns={resultColumns} rows={r.results ?? []} rowKey={(x) => `${x.position}-${x.url}`}
                empty={<EmptyState title="No results" description="The provider returned no results for this keyword." />} />
            </Card>

            <div className="grid gap-4 lg:grid-cols-2">
              <Card padded={false} title="Heading topics" description="Terms that recur in the H2/H3 headings of ranking pages">
                <DataTable dense columns={termColumns} rows={r.heading_topics ?? []} rowKey={(t) => t.term}
                  empty={<EmptyState title="No recurring heading topics" description="Not enough pages could be fetched to find shared topics." />} />
              </Card>
              <Card padded={false} title="Common terms" description="Terms that recur in the body text of ranking pages">
                <div className="max-h-[28rem] overflow-y-auto">
                  <DataTable dense columns={termColumns} rows={r.common_terms ?? []} rowKey={(t) => t.term}
                    empty={<EmptyState title="No recurring terms" description="Not enough pages could be fetched to find shared terms." />} />
                </div>
              </Card>
            </div>

            <div className="grid gap-4 lg:grid-cols-2">
              <Card title="Questions answered by ranking pages" description="Headings phrased as questions">
                {(r.questions ?? []).length ? (
                  <ul className="list-disc space-y-1 pl-5 text-sm text-slate-700 dark:text-slate-300">{r.questions.map((q: string) => <li key={q}>{q}</li>)}</ul>
                ) : <p className="text-sm text-slate-500 dark:text-slate-400">No question headings found on the analysed pages.</p>}
              </Card>
              <Card title="Titles & structured data">
                <div className="space-y-4">
                  <div>
                    <div className="mb-1.5 text-xs font-medium uppercase tracking-wide text-slate-500 dark:text-slate-400">Terms shared by result titles</div>
                    {(summary.common_title_terms ?? []).length ? <div className="flex flex-wrap gap-1">{summary.common_title_terms.map((t: any) => <Chip key={t.term}>{t.term} <span className="font-semibold tabular-nums">{t.results}</span></Chip>)}</div>
                      : <span className="text-sm text-slate-500 dark:text-slate-400">No shared title terms</span>}
                  </div>
                  <div>
                    <div className="mb-1.5 text-xs font-medium uppercase tracking-wide text-slate-500 dark:text-slate-400">Schema types on ranking pages</div>
                    {schemaCounts.length ? <div className="flex flex-wrap gap-1">{schemaCounts.map(([t, c]) => <Chip key={t}>{t} <span className="font-semibold tabular-nums">{c}</span></Chip>)}</div>
                      : <span className="text-sm text-slate-500 dark:text-slate-400">No structured data found</span>}
                  </div>
                </div>
              </Card>
            </div>

            <AiBrief key={r.keyword} keyword={r.keyword} serp={r} />
          </>
        )}
      </div>
    </div>
  );
}
