import { useMutation } from "@tanstack/react-query";
import { CheckCircle2, CircleAlert, CircleX, FileText, Gauge } from "lucide-react";
import { type ReactNode, useMemo, useState } from "react";
import {
  Badge, Button, Card, Checkbox, type Column, DataBadge, DataTable, EmptyState, ErrorBox, Field, Input, KeyValue, Notice, PageHeader, ScoreRing, Spinner, Textarea, Url,
} from "../components/ui";
import { api } from "../lib/api";
import { useSite } from "../lib/context";
import { fmtInt, fmtPct, shortUrl } from "../lib/format";

const INTENT_TONE: Record<string, string> = { transactional: "green", commercial: "purple", navigational: "blue", local: "orange", informational: "gray" };

function parseLines(text: string): string[] {
  return Array.from(new Set(text.split(/\r?\n/).map((l) => l.trim()).filter(Boolean)));
}

function countWords(text: string): number {
  const plain = text.replace(/<[^>]*>/g, " ");
  return (plain.match(/[\p{L}\p{N}][\p{L}\p{N}'’-]*/gu) ?? []).length;
}

function Chip({ children, tone, title }: { children: ReactNode; tone?: "good" | "bad"; title?: string }) {
  return (
    <span title={title} className={`inline-flex items-center gap-1 rounded-md border px-1.5 py-0.5 text-xs ${
      tone === "good" ? "border-emerald-200 bg-emerald-50 text-emerald-800 dark:border-emerald-900 dark:bg-emerald-950/40 dark:text-emerald-300"
      : tone === "bad" ? "border-amber-200 bg-amber-50 text-amber-900 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-200"
      : "border-slate-200 bg-slate-50 text-slate-700 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300"}`}>{children}</span>
  );
}

const STATUS_META: Record<string, { label: string; icon: ReactNode }> = {
  fail: { label: "Failing", icon: <CircleX className="h-4 w-4 text-red-600 dark:text-red-400" /> },
  warn: { label: "Needs attention", icon: <CircleAlert className="h-4 w-4 text-amber-600 dark:text-amber-400" /> },
  pass: { label: "Passing", icon: <CheckCircle2 className="h-4 w-4 text-emerald-600 dark:text-emerald-400" /> },
};

function CheckGroup({ status, checks }: { status: string; checks: any[] }) {
  const [open, setOpen] = useState(status !== "pass");
  if (!checks.length) return null;
  const meta = STATUS_META[status];
  return (
    <div>
      <button className="flex w-full items-center justify-between gap-2 py-1.5 text-left" onClick={() => setOpen((o) => !o)} aria-expanded={open}>
        <span className="flex items-center gap-2 text-sm font-semibold text-slate-900 dark:text-slate-100">{meta.icon}{meta.label}
          <span className="rounded-full bg-slate-100 px-1.5 text-xs font-medium text-slate-600 dark:bg-slate-800 dark:text-slate-300">{checks.length}</span></span>
        <span className="text-xs text-slate-500 dark:text-slate-400">{open ? "Hide" : "Show"}</span>
      </button>
      {open && (
        <ul className="divide-y divide-slate-100 dark:divide-slate-800">
          {checks.map((c) => (
            <li key={c.id} className="py-2 pl-6">
              <div className="flex flex-wrap items-baseline justify-between gap-x-3">
                <span className="text-sm font-medium text-slate-800 dark:text-slate-200">{c.label}</span>
                <span className="text-xs text-slate-400" title="Weight of this check in the score">weight {c.weight}</span>
              </div>
              <div className="break-words text-xs text-slate-500 dark:text-slate-400">{c.detail}</div>
              {c.recommendation && <div className="mt-1 text-xs text-slate-700 dark:text-slate-300"><span className="font-medium">Fix:</span> {c.recommendation}</div>}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default function Content() {
  const { site } = useSite();
  const [keyword, setKeyword] = useState("");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [url, setUrl] = useState("");
  const [secondary, setSecondary] = useState("");
  const [content, setContent] = useState("");
  const [loadUrl, setLoadUrl] = useState("");
  const [competitorText, setCompetitorText] = useState("");
  const [useSerp, setUseSerp] = useState(false);
  const [suggestQuestions, setSuggestQuestions] = useState(false);
  const [useSitePages, setUseSitePages] = useState(true);
  const [termFilter, setTermFilter] = useState<"all" | "missing">("missing");

  const words = useMemo(() => countWords(content), [content]);
  const competitorUrls = parseLines(competitorText);
  const secondaryList = secondary.split(",").map((s) => s.trim()).filter(Boolean);

  const fetchPage = useMutation({
    mutationFn: () => api.post("/content/fetch", { url: loadUrl.trim() }),
    onSuccess: (d) => {
      setTitle(d.title ?? "");
      setDescription(d.meta_description ?? "");
      setContent(d.content ?? "");
      setUrl(d.url ?? loadUrl.trim());
    },
  });
  const analyze = useMutation({
    mutationFn: () => api.post("/content/analyze", {
      content, keyword: keyword.trim(), title: title.trim() || null, meta_description: description.trim() || null, url: url.trim() || null,
      secondary_keywords: secondaryList, competitor_urls: competitorUrls, use_serp: useSerp, suggest_questions: suggestQuestions,
      site_id: site && useSitePages ? site.id : null,
    }),
  });

  const r = analyze.data;
  const checks: any[] = r?.checks ?? [];
  const read = r?.readability;
  const terms: any[] = r?.semantic_terms ?? [];
  const shownTerms = termFilter === "missing" ? terms.filter((t) => t.status === "missing") : terms;
  const topics: any[] = r?.topic_coverage?.topics ?? [];
  const tooMany = secondaryList.length > 30 || competitorUrls.length > 10;
  const canAnalyze = !!keyword.trim() && !!content.trim() && !tooMany;

  const termColumns: Column<any>[] = [
    { key: "term", header: "Term", render: (t) => <span className="font-medium text-slate-900 dark:text-slate-100">{t.term}</span> },
    { key: "share", header: "Competitors using it", align: "right", render: (t) => `${fmtPct(t.share, 0)} (${t.documents})` },
    { key: "avg", header: "Avg uses", align: "right", render: (t) => t.avg_count },
    { key: "used", header: "In your draft", align: "right", render: (t) => (t.used ? <Badge tone="green">used {t.used}×</Badge> : <Badge tone="amber">missing</Badge>) },
  ];

  return (
    <div>
      <PageHeader title="Content optimiser"
        description="Score a draft against on-page best practice and, optionally, against the pages that already rank. Scores are heuristics; they do not predict rankings." />

      <div className="grid gap-4 lg:grid-cols-2">
        {/* ------------------------------------------------------ editor */}
        <div className="min-w-0 space-y-4">
          <Card title="Draft">
            <div className="space-y-3">
              <div className="flex flex-col gap-2 sm:flex-row sm:items-end">
                <Field label="Load an existing page (optional)" className="flex-1">
                  <Input type="url" value={loadUrl} onChange={(e) => setLoadUrl(e.target.value)} placeholder="https://example.com/page-to-improve" />
                </Field>
                <Button loading={fetchPage.isPending} disabled={!loadUrl.trim()} onClick={() => fetchPage.mutate()}>Load from URL</Button>
              </div>
              {fetchPage.error && <ErrorBox error={fetchPage.error} />}
              {fetchPage.data && !fetchPage.isPending && <Notice tone="success">Loaded {fmtInt(fetchPage.data.word_count)} words from <span className="break-all">{fetchPage.data.url}</span>. Title, description and content were filled in.</Notice>}

              <Field label="Target keyword">
                <Input required maxLength={200} value={keyword} onChange={(e) => setKeyword(e.target.value)} placeholder="e.g. cold brew coffee ratio" />
              </Field>
              <Field label="Title" hint={`${title.length} characters (aim for 30-60)`}>
                <Input maxLength={500} value={title} onChange={(e) => setTitle(e.target.value)} />
              </Field>
              <Field label="Meta description" hint={`${description.length} characters (aim for 70-160)`}>
                <Textarea rows={2} maxLength={1000} value={description} onChange={(e) => setDescription(e.target.value)} />
              </Field>
              <div className="grid gap-3 sm:grid-cols-2">
                <Field label="URL (optional)">
                  <Input maxLength={2048} value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://example.com/cold-brew-ratio" />
                </Field>
                <Field label="Secondary keywords" hint={`Comma separated${secondaryList.length ? ` · ${secondaryList.length} / 30` : ""}`}>
                  <Input value={secondary} onChange={(e) => setSecondary(e.target.value)} placeholder="cold brew concentrate, steep time" />
                </Field>
              </div>
              <Field label="Content (Markdown, HTML or plain text)">
                <Textarea rows={18} maxLength={400000} value={content} onChange={(e) => setContent(e.target.value)} className="font-mono text-xs"
                  placeholder={"# Heading\n\nWrite or paste your draft here…"} />
              </Field>
              <div className="flex items-center justify-between text-xs text-slate-500 dark:text-slate-400">
                <span><span className="font-semibold tabular-nums text-slate-700 dark:text-slate-200">{fmtInt(words)}</span> words · {fmtInt(content.length)} characters</span>
                {r?.target_word_count ? <span>Competitor median: {fmtInt(r.target_word_count)} words</span> : null}
              </div>
            </div>
          </Card>

          <Card title="Compare against ranking pages" description="Optional. Enables related-term, topic-coverage and FAQ suggestions.">
            <div className="space-y-3">
              <Field label="Competitor URLs, one per line" hint={`${competitorUrls.length} / 10 URLs. Pages are fetched and measured by this toolkit.`}>
                <Textarea rows={4} value={competitorText} onChange={(e) => setCompetitorText(e.target.value)} className="font-mono text-xs" placeholder="https://competitor.example/their-article" />
              </Field>
              <Checkbox label="Use SERP provider for competitors" checked={useSerp} onChange={setUseSerp} hint="Used only when no competitor URLs are pasted. Needs a SERP provider in Settings." />
              <Checkbox label="Suggest questions from autocomplete" checked={suggestQuestions} onChange={setSuggestQuestions} hint="Adds real question completions for the keyword as FAQ ideas." />
              <Checkbox label="Use my site's pages for internal link ideas" checked={!!site && useSitePages} onChange={setUseSitePages}
                hint={site ? `Uses the latest crawl of ${site.name}.` : "Add a website and crawl it to enable this."} />
            </div>
          </Card>

          <div className="flex flex-wrap items-center gap-3">
            <Button variant="primary" icon={<Gauge className="h-4 w-4" />} loading={analyze.isPending} disabled={!canAnalyze} onClick={() => analyze.mutate()}>Analyse content</Button>
            {!canAnalyze && !tooMany && <span className="text-xs text-slate-500 dark:text-slate-400">Enter a target keyword and some content.</span>}
            {tooMany && <span className="text-xs text-red-600 dark:text-red-400">At most 30 secondary keywords and 10 competitor URLs.</span>}
          </div>
        </div>

        {/* ------------------------------------------------------ results */}
        <div className="min-w-0 space-y-4">
          {analyze.isPending ? <Card><Spinner label={competitorUrls.length || useSerp ? "Fetching competitor pages and analysing…" : "Analysing…"} /></Card>
            : analyze.error ? <ErrorBox error={analyze.error} onRetry={() => analyze.mutate()} />
            : !r ? <Card><EmptyState icon={<FileText className="h-6 w-6" />} title="No analysis yet" description="Fill in the keyword and content, then press Analyse content. Run it again after each edit." /></Card>
            : (
              <>
                <Card>
                  <div className="flex flex-col items-center gap-4 sm:flex-row sm:items-start">
                    <ScoreRing score={r.score} size={112} />
                    <div className="min-w-0 flex-1 space-y-2 text-sm">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-semibold text-slate-900 dark:text-slate-100">Content score</span>
                        <DataBadge kind="estimated" />
                        <Badge>{r.format}</Badge>
                      </div>
                      <div className="flex flex-wrap items-center gap-2 text-slate-600 dark:text-slate-300">
                        Intent: <Badge tone={INTENT_TONE[r.intent?.intent] ?? "gray"}>{r.intent?.intent}</Badge>
                        <span className="text-xs text-slate-500 dark:text-slate-400">estimate, confidence {fmtPct(r.intent?.confidence, 0)}</span>
                      </div>
                      <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs text-slate-600 sm:grid-cols-3 dark:text-slate-300">
                        <span>Words: <b className="tabular-nums">{fmtInt(r.word_count)}</b></span>
                        <span>Target: <b className="tabular-nums">{r.target_word_count ? fmtInt(r.target_word_count) : "n/a"}</b></span>
                        <span>Exact phrase: <b className="tabular-nums">{r.keyword_occurrences}×</b></span>
                        <span>Density: <b className="tabular-nums">{r.keyword_density}%</b></span>
                        <span>Competitors used: <b className="tabular-nums">{r.competitors_used}</b></span>
                        <span>Checks: <b className="tabular-nums">{checks.filter((c) => c.status === "pass").length}/{checks.length}</b> passing</span>
                      </div>
                    </div>
                  </div>
                </Card>

                {(r.notes ?? []).length > 0 && (
                  <Notice><ul className="list-disc space-y-0.5 pl-5">{r.notes.map((n: string) => <li key={n}>{n}</li>)}</ul></Notice>
                )}

                <Card title="Checks">
                  <div className="space-y-2">
                    {["fail", "warn", "pass"].map((s) => <CheckGroup key={`${s}-${analyze.submittedAt}`} status={s} checks={checks.filter((c) => c.status === s)} />)}
                  </div>
                </Card>

                <Card title="Readability" description="Flesch formulas, calibrated for English text">
                  {read?.flesch_reading_ease === null || read?.flesch_reading_ease === undefined ? (
                    <p className="text-sm text-slate-500 dark:text-slate-400">Not enough text to measure readability.</p>
                  ) : (
                    <KeyValue items={[
                      ["Reading ease", <span key="e">{read.flesch_reading_ease} <Badge tone={read.flesch_reading_ease >= 50 ? "green" : read.flesch_reading_ease >= 30 ? "amber" : "red"}>{read.label}</Badge></span>],
                      ["Grade level", read.flesch_kincaid_grade],
                      ["Sentences", fmtInt(read.sentences)],
                      ["Avg sentence length", `${read.avg_sentence_length} words`],
                      ["Sentences over 25 words", fmtPct(read.long_sentence_share, 0)],
                    ]} />
                  )}
                </Card>

                <Card padded={false} title="Related terms from ranking pages"
                  actions={terms.length ? (
                    <span className="inline-flex gap-1">
                      {(["missing", "all"] as const).map((f) => (
                        <button key={f} onClick={() => setTermFilter(f)} aria-pressed={termFilter === f}
                          className={`rounded-md px-2 py-1 text-xs font-medium ${termFilter === f ? "bg-brand-600 text-white" : "text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800"}`}>
                          {f === "missing" ? `Missing (${terms.filter((t) => t.status === "missing").length})` : `All (${terms.length})`}
                        </button>
                      ))}
                    </span>
                  ) : undefined}>
                  {terms.length ? (
                    <div className="max-h-96 overflow-y-auto">
                      <DataTable dense columns={termColumns} rows={shownTerms} rowKey={(t) => t.term}
                        empty={<EmptyState title="Nothing missing" description="Your draft uses every recurring term found on the competitor pages." />} />
                    </div>
                  ) : <EmptyState title="No competitor data" description="Paste competitor URLs or enable the SERP provider option to see which terms ranking pages use." />}
                </Card>

                <Card title="Topic coverage" description={r.topic_coverage?.covered_share !== null && r.topic_coverage?.covered_share !== undefined
                  ? `Covers ${fmtPct(r.topic_coverage.covered_share, 0)} of the subheading topics competitors use` : "Subheading topics used by competitor pages"}>
                  {topics.length ? (
                    <div className="flex flex-wrap gap-1.5">
                      {topics.map((t) => <Chip key={t.term} tone={t.covered ? "good" : "bad"} title={`${t.documents} competitor page(s), ${t.covered ? "covered" : "not covered"}`}>{t.term} <span className="opacity-70">{fmtPct(t.share, 0)}</span></Chip>)}
                    </div>
                  ) : <p className="text-sm text-slate-500 dark:text-slate-400">{r.competitors_used ? "No recurring subheading topics were found on the competitor pages." : "Needs competitor pages."}</p>}
                  {topics.length > 0 && <p className="mt-2 text-xs text-slate-500 dark:text-slate-400">Green: covered in your draft. Amber: not covered.</p>}
                </Card>

                <Card title="FAQ suggestions" description="Questions from autocomplete and competitor headings that your draft does not answer yet">
                  {(r.faq_suggestions ?? []).length ? (
                    <ul className="list-disc space-y-1 pl-5 text-sm text-slate-700 dark:text-slate-300">{r.faq_suggestions.map((q: string) => <li key={q}>{q}</li>)}</ul>
                  ) : <p className="text-sm text-slate-500 dark:text-slate-400">No suggestions. Enable autocomplete questions or add competitor URLs to get ideas.</p>}
                </Card>

                <div className="grid gap-4 xl:grid-cols-2">
                  <Card title="Schema recommendations">
                    {(r.schema_recommendations ?? []).length ? (
                      <ul className="space-y-2 text-sm">
                        {r.schema_recommendations.map((s: any) => (
                          <li key={s.type}><Badge tone="purple">{s.type}</Badge> <span className="text-slate-600 dark:text-slate-300">{s.reason}</span></li>
                        ))}
                      </ul>
                    ) : <p className="text-sm text-slate-500 dark:text-slate-400">No schema type stands out for this draft.</p>}
                  </Card>
                  <Card title="Internal link suggestions">
                    {(r.internal_link_suggestions ?? []).length ? (
                      <ul className="space-y-2 text-sm">
                        {r.internal_link_suggestions.map((l: any) => (
                          <li key={l.url}>
                            <Url href={l.url} label={shortUrl(l.url, site?.url)} />
                            <div className="text-xs text-slate-500 dark:text-slate-400">{l.title ? `${l.title} · ` : ""}{l.reason}</div>
                          </li>
                        ))}
                      </ul>
                    ) : <p className="text-sm text-slate-500 dark:text-slate-400">{site && useSitePages ? "No crawled page of your site matches topics mentioned in the draft (or no crawl has completed yet)." : "Select a site and enable the internal-link option to get ideas from your crawled pages."}</p>}
                  </Card>
                </div>

                <Card title={`Competitors used (${(r.competitors ?? []).length})`}>
                  {(r.competitors ?? []).length ? (
                    <ul className="divide-y divide-slate-100 text-sm dark:divide-slate-800">
                      {r.competitors.map((c: any) => (
                        <li key={c.url} className="flex flex-wrap items-baseline justify-between gap-x-3 py-1.5">
                          <span className="min-w-0"><span className="text-slate-800 dark:text-slate-200">{c.title || "Untitled"}</span><br /><Url href={c.url} className="text-xs" /></span>
                          <span className="text-xs tabular-nums text-slate-500 dark:text-slate-400">{fmtInt(c.word_count)} words</span>
                        </li>
                      ))}
                    </ul>
                  ) : <p className="text-sm text-slate-500 dark:text-slate-400">No competitor pages were analysed.</p>}
                </Card>
              </>
            )}
        </div>
      </div>
    </div>
  );
}
