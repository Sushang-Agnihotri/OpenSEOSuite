import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, PlugZap, XCircle } from "lucide-react";
import { type FormEvent, type ReactNode, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Badge, Button, Card, ErrorBox, Field, Input, KeyValue, Notice, PageHeader, Select, Spinner } from "../components/ui";
import { api, tokenStore } from "../lib/api";
import { useAuth } from "../lib/context";

const MASK = "********";
type Section = "serp" | "pagespeed" | "ai" | "gsc";
type Values = Record<string, string>;

/** Local form state for one settings section; resets whenever the server copy changes. */
function useSection(section: Section, server: Values | undefined) {
  const qc = useQueryClient();
  const [values, setValues] = useState<Values>(server ?? {});
  const [saved, setSaved] = useState(false);
  const serverKey = JSON.stringify(server ?? {});
  useEffect(() => {
    setValues(JSON.parse(serverKey));
  }, [serverKey]);
  const save = useMutation({
    mutationFn: (v: Values) => api.put("/settings", { [section]: v }),
    onSuccess: (data) => {
      qc.setQueryData(["settings"], data);
      setSaved(true);
      // other pages cache provider/status information derived from these settings
      void qc.invalidateQueries({ predicate: (q) => q.queryKey[0] !== "settings" });
    },
  });
  const set = (key: string, value: string) => {
    setSaved(false);
    setValues((v) => ({ ...v, [key]: value }));
  };
  const dirty = JSON.stringify(values) !== serverKey;
  return { values, set, save, dirty, saved: saved && !dirty };
}

function SecretInput({ value, onChange, placeholder }: { value: string; onChange: (v: string) => void; placeholder?: string }) {
  return (
    <Input type="password" autoComplete="off" value={value} placeholder={placeholder} onChange={(e) => onChange(e.target.value)}
      onFocus={(e) => value === MASK && e.target.select()} />
  );
}
const secretHint = (value: string | undefined) => (value === MASK ? "A value is stored. Leave it as is to keep it, or type a new one to replace it." : "Stored in the application database; never shown again after saving.");

function SaveBar({ s, children }: { s: ReturnType<typeof useSection>; children?: ReactNode }) {
  return (
    <div className="space-y-3">
      {s.save.error ? <ErrorBox error={s.save.error} /> : null}
      <div className="flex flex-wrap items-center gap-2">
        <Button type="submit" variant="primary" loading={s.save.isPending} disabled={!s.dirty}>Save</Button>
        {children}
        {s.saved && <span className="inline-flex items-center gap-1 text-xs text-emerald-700 dark:text-emerald-400"><CheckCircle2 className="h-3.5 w-3.5" /> Saved</span>}
        {s.dirty && <span className="text-xs text-slate-500 dark:text-slate-400">Unsaved changes</span>}
      </div>
    </div>
  );
}

const ext = (href: string, label: string) => <a href={href} target="_blank" rel="noopener noreferrer" className="font-medium text-brand-700 hover:underline dark:text-brand-300">{label}</a>;

/* ------------------------------------------------------------------ account */
function Account() {
  const { user } = useAuth();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [mismatch, setMismatch] = useState(false);
  const change = useMutation({
    mutationFn: () => api.post("/auth/password", { current_password: current, new_password: next }),
    onSuccess: (r: { access_token?: string }) => {
      if (r?.access_token) tokenStore.set(r.access_token); // tokens issued before the change no longer work
      setCurrent(""); setNext(""); setConfirm("");
    },
  });
  const submit = (e: FormEvent) => {
    e.preventDefault();
    change.reset();
    if (next !== confirm) return setMismatch(true);
    setMismatch(false);
    change.mutate();
  };
  return (
    <Card title="Account">
      <div className="grid gap-6 lg:grid-cols-2">
        <KeyValue items={[
          ["Email", user?.email],
          ["Role", user?.is_admin ? <Badge tone="blue">administrator</Badge> : <Badge>member</Badge>],
        ]} />
        <form onSubmit={submit} className="space-y-3">
          <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">Change password</h3>
          {change.error ? <ErrorBox error={change.error} /> : null}
          {mismatch && <ErrorBox error="The new password and its confirmation do not match." />}
          {change.isSuccess && <Notice tone="success">Password changed.</Notice>}
          <Field label="Current password">
            <Input type="password" autoComplete="current-password" required value={current} onChange={(e) => setCurrent(e.target.value)} />
          </Field>
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label="New password" hint="At least 8 characters.">
              <Input type="password" autoComplete="new-password" required minLength={8} maxLength={200} value={next} onChange={(e) => setNext(e.target.value)} />
            </Field>
            <Field label="Confirm new password">
              <Input type="password" autoComplete="new-password" required minLength={8} maxLength={200} value={confirm} onChange={(e) => setConfirm(e.target.value)} />
            </Field>
          </div>
          <Button type="submit" variant="primary" loading={change.isPending}>Change password</Button>
        </form>
      </div>
    </Card>
  );
}

/* ------------------------------------------------------------------ integrations */
const SERP_NOTES: Record<string, ReactNode> = {
  none: "SERP analysis is switched off. Every other feature works without a provider.",
  searxng: <>Self-hosted metasearch, free and without a quota of its own. Enable the JSON output format in your instance's settings.yml (<code>search.formats: [html, json]</code>). Upstream engines may rate-limit a busy instance.</>,
  google_cse: <>Google Programmable Search JSON API: 100 queries per day free, then paid, up to 10 results per request. Needs an API key and a search engine ID (cx) set to search the entire web. Results can differ from google.com.</>,
  brave: <>Brave Search API: its own independent index, not Google's. The free plan is limited to about one request per second and a monthly query quota; check your plan in the Brave dashboard.</>,
};

function SerpSettings({ server }: { server: Values }) {
  const s = useSection("serp", server);
  const p = s.values.provider ?? "none";
  return (
    <Card title="SERP provider" description="Used by SERP analysis and content briefs to fetch live search results">
      <form onSubmit={(e) => { e.preventDefault(); s.save.mutate(s.values); }} className="space-y-4">
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Provider">
            <Select value={p} onChange={(e) => s.set("provider", e.target.value)}>
              <option value="none">None</option>
              <option value="searxng">SearXNG (self-hosted)</option>
              <option value="google_cse">Google Programmable Search</option>
              <option value="brave">Brave Search API</option>
            </Select>
          </Field>
          {p === "searxng" && (
            <Field label="SearXNG URL" hint="Base URL of your instance, including http:// or https://">
              <Input type="url" required value={s.values.searxng_url ?? ""} onChange={(e) => s.set("searxng_url", e.target.value)} placeholder="http://localhost:8080" />
            </Field>
          )}
          {p === "google_cse" && (
            <>
              <Field label="API key" hint={secretHint(s.values.google_cse_key)}>
                <SecretInput value={s.values.google_cse_key ?? ""} onChange={(v) => s.set("google_cse_key", v)} />
              </Field>
              <Field label="Search engine ID (cx)">
                <Input required value={s.values.google_cse_cx ?? ""} onChange={(e) => s.set("google_cse_cx", e.target.value)} />
              </Field>
            </>
          )}
          {p === "brave" && (
            <Field label="Subscription token" hint={secretHint(s.values.brave_key)}>
              <SecretInput value={s.values.brave_key ?? ""} onChange={(v) => s.set("brave_key", v)} />
            </Field>
          )}
        </div>
        <Notice>{SERP_NOTES[p] ?? SERP_NOTES.none}</Notice>
        <SaveBar s={s} />
      </form>
    </Card>
  );
}

function PageSpeedSettings({ server }: { server: Values }) {
  const s = useSection("pagespeed", server);
  return (
    <Card title="PageSpeed Insights" description="Lighthouse and Core Web Vitals data from Google's public API">
      <form onSubmit={(e) => { e.preventDefault(); s.save.mutate(s.values); }} className="space-y-4">
        <Field label="API key" className="max-w-md" hint={secretHint(s.values.api_key)}>
          <SecretInput value={s.values.api_key ?? ""} onChange={(v) => s.set("api_key", v)} placeholder="Optional" />
        </Field>
        <p className="text-xs text-slate-500 dark:text-slate-400">
          The API is free. Without a key, requests share a small anonymous quota and may be rejected with HTTP 429. Create a key in the{" "}
          {ext("https://developers.google.com/speed/docs/insights/v5/get-started", "Google Cloud console")} (enable “PageSpeed Insights API”). Clear the field and save to remove a stored key.
        </p>
        <SaveBar s={s} />
      </form>
    </Card>
  );
}

function AiSettings({ server }: { server: Values }) {
  const s = useSection("ai", server);
  const p = s.values.provider ?? "none";
  const test = useMutation({
    mutationFn: async () => {
      if (s.dirty) await s.save.mutateAsync(s.values);
      return api.get("/ai/status");
    },
  });
  const st = test.data;
  return (
    <Card title="AI provider" description="Optional. Powers AI summaries, briefs and rewrite suggestions; nothing else depends on it.">
      <form onSubmit={(e) => { e.preventDefault(); test.reset(); s.save.mutate(s.values); }} className="space-y-4">
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Provider">
            <Select value={p} onChange={(e) => s.set("provider", e.target.value)}>
              <option value="none">None</option>
              <option value="ollama">Ollama (local models)</option>
              <option value="openai_compatible">OpenAI-compatible API</option>
            </Select>
          </Field>
          {p !== "none" && (
            <>
              <Field label="Base URL" hint={p === "ollama" ? "Default: http://localhost:11434" : "The API root that serves /models and /chat/completions, e.g. https://api.openai.com/v1"}>
                <Input type="url" required value={s.values.base_url ?? ""} onChange={(e) => s.set("base_url", e.target.value)} />
              </Field>
              <Field label="Model" hint={p === "ollama" ? "A model you have pulled, e.g. llama3.1" : "Model identifier as the API expects it"}>
                <Input required value={s.values.model ?? ""} onChange={(e) => s.set("model", e.target.value)} />
              </Field>
              {p === "openai_compatible" && (
                <Field label="API key" hint={secretHint(s.values.api_key)}>
                  <SecretInput value={s.values.api_key ?? ""} onChange={(v) => s.set("api_key", v)} />
                </Field>
              )}
            </>
          )}
        </div>
        <Notice>
          {p === "none" ? "No AI provider is configured. All crawling, auditing and reporting features work without one."
            : p === "ollama" ? "Ollama runs models on your own hardware: free, private, and limited by your machine's memory and speed. Page content stays on this machine."
            : "Prompts, including excerpts of page content, are sent to the configured API. Usage is billed by that provider under your key."}
        </Notice>
        <SaveBar s={s}>
          <Button type="button" icon={<PlugZap className="h-4 w-4" />} loading={test.isPending} onClick={() => test.mutate()}>{s.dirty ? "Save & test connection" : "Test connection"}</Button>
        </SaveBar>
        {test.error ? <ErrorBox error={test.error} /> : null}
        {st && !test.isPending && (
          <div className="rounded-lg border border-slate-200 p-3 text-sm dark:border-slate-800">
            <div className={`flex items-center gap-2 font-medium ${st.available ? "text-emerald-700 dark:text-emerald-400" : st.provider === "none" ? "text-slate-600 dark:text-slate-300" : "text-red-700 dark:text-red-400"}`}>
              {st.available ? <CheckCircle2 className="h-4 w-4" /> : <XCircle className="h-4 w-4" />} {st.message}
            </div>
            {Array.isArray(st.models) && (
              <div className="mt-2">
                <div className="mb-1 text-xs text-slate-500 dark:text-slate-400">{st.models.length ? "Models available in Ollama (click one to use it):" : "Ollama has no models yet. Pull one with: ollama pull llama3.1"}</div>
                <div className="flex flex-wrap gap-1">
                  {st.models.map((m: string) => (
                    <button key={m} type="button" onClick={() => s.set("model", m)} aria-pressed={s.values.model === m}
                      className={`rounded-md px-1.5 py-0.5 text-xs font-medium ring-1 ring-inset ${s.values.model === m
                        ? "bg-brand-600 text-white ring-brand-600" : "bg-slate-100 text-slate-700 ring-slate-200 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:ring-slate-700 dark:hover:bg-slate-700"}`}>
                      {m}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </form>
    </Card>
  );
}

function GscSettings({ server }: { server: Values }) {
  const s = useSection("gsc", server);
  const status = useQuery({ queryKey: ["gsc", "status"], queryFn: () => api.get("/gsc/status") });
  return (
    <Card title="Google Search Console" description="OAuth client used to read your own Search Console data"
      actions={status.data ? (
        <>
          {status.data.client_configured ? <Badge tone="green">client configured</Badge> : <Badge tone="amber">client not configured</Badge>}
          {status.data.connected ? <Badge tone="green">account connected</Badge> : <Badge>not connected</Badge>}
        </>
      ) : undefined}>
      <form onSubmit={(e) => { e.preventDefault(); s.save.mutate(s.values); }} className="space-y-4">
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="OAuth client ID">
            <Input value={s.values.client_id ?? ""} onChange={(e) => s.set("client_id", e.target.value)} placeholder="….apps.googleusercontent.com" autoComplete="off" />
          </Field>
          <Field label="OAuth client secret" hint={secretHint(s.values.client_secret)}>
            <SecretInput value={s.values.client_secret ?? ""} onChange={(v) => s.set("client_secret", v)} />
          </Field>
        </div>
        <div className="rounded-lg border border-slate-200 p-3 text-sm dark:border-slate-800">
          <div className="mb-1 text-xs font-medium uppercase tracking-wide text-slate-500 dark:text-slate-400">Authorised redirect URI</div>
          {status.isLoading ? <span className="text-slate-500 dark:text-slate-400">Loading…</span> : status.error ? <ErrorBox error={status.error} onRetry={() => status.refetch()} />
            : <code className="break-all text-slate-800 dark:text-slate-200">{status.data.redirect_uri}</code>}
          <ol className="mt-3 list-decimal space-y-1 pl-5 text-xs text-slate-600 dark:text-slate-400">
            <li>In the {ext("https://console.cloud.google.com/apis/library/searchconsole.googleapis.com", "Google Cloud console")}, create a project and enable the “Google Search Console API”.</li>
            <li>Configure the OAuth consent screen and add your Google account as a test user.</li>
            <li>Create an OAuth client ID of type “Web application” and add the redirect URI above exactly as shown.</li>
            <li>Paste the client ID and secret here and save.</li>
            <li>Open <Link to="/search-console" className="font-medium text-brand-700 hover:underline dark:text-brand-300">Search Console</Link> and choose Connect.</li>
          </ol>
        </div>
        <SaveBar s={s} />
      </form>
    </Card>
  );
}

function Integrations() {
  const { user } = useAuth();
  const isAdmin = !!user?.is_admin;
  const q = useQuery({ queryKey: ["settings"], queryFn: () => api.get("/settings"), enabled: isAdmin });
  if (!isAdmin) {
    return (
      <Card title="Integrations">
        <Notice tone="warn">Integration settings (SERP provider, PageSpeed key, AI provider, Search Console client) apply to the whole installation and can only be changed by an administrator.</Notice>
      </Card>
    );
  }
  if (q.isLoading) return <Card title="Integrations"><Spinner /></Card>;
  if (q.error) return <Card title="Integrations"><ErrorBox error={q.error} onRetry={() => q.refetch()} /></Card>;
  const d = q.data ?? {};
  return (
    <>
      <SerpSettings server={d.serp ?? {}} />
      <PageSpeedSettings server={d.pagespeed ?? {}} />
      <AiSettings server={d.ai ?? {}} />
      <GscSettings server={d.gsc ?? {}} />
    </>
  );
}

/* ------------------------------------------------------------------ about */
function About() {
  const status = useQuery({ queryKey: ["auth-status"], queryFn: () => api.get("/auth/status") });
  const health = useQuery({ queryKey: ["health"], queryFn: () => api.get("/health"), retry: false });
  return (
    <Card title="About">
      <div className="grid gap-6 lg:grid-cols-2">
        <div>
          {status.isLoading ? <Spinner /> : status.error ? <ErrorBox error={status.error} onRetry={() => status.refetch()} /> : (
            <KeyValue items={[
              ["Application", status.data.app],
              ["Version", status.data.version],
              ["Backend health", health.isLoading ? "Checking…" : health.error ? <Badge tone="red" title={health.error instanceof Error ? health.error.message : undefined}>unreachable</Badge>
                : <Badge tone={health.data?.status === "ok" ? "green" : "amber"}>{health.data?.status ?? "unknown"}</Badge>],
              ["Private networks", status.data.private_networks_allowed
                ? <><Badge tone="amber">allowed</Badge><span className="ml-2 text-xs text-slate-500 dark:text-slate-400">Crawls and fetches may reach localhost and private IP ranges.</span></>
                : <><Badge tone="green">blocked</Badge><span className="ml-2 text-xs text-slate-500 dark:text-slate-400">Requests to localhost and private IP ranges are refused (SSRF protection).</span></>],
              ["Registration", status.data.registration_open ? <Badge tone="amber">open</Badge> : <Badge tone="green">closed</Badge>],
            ]} />
          )}
        </div>
        <div className="space-y-2 text-sm text-slate-600 dark:text-slate-300">
          <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">Data sources and limitations</h3>
          <p>Everything shown comes from one of three places: this toolkit's own crawler and analysis, Google's free APIs (PageSpeed Insights, your own Search Console property), or files you import.</p>
          <ul className="list-disc space-y-1 pl-5">
            <li><strong>No search volume.</strong> Keyword volumes and difficulty scores need third-party data; they are only shown when you import them.</li>
            <li><strong>No web-scale backlink index.</strong> Backlinks are limited to what you import (for example a Search Console links export) and can be re-verified by fetching the linking pages.</li>
            <li><strong>Rankings</strong> come from Search Console (your site only) or from the SERP provider you configure, with that provider's limits.</li>
            <li><strong>Indexing status</strong> can only be confirmed in Search Console; the crawler reports whether a page is <em>indexable</em>.</li>
          </ul>
        </div>
      </div>
    </Card>
  );
}

export default function Settings() {
  return (
    <>
      <PageHeader title="Settings" description="Your account, the integrations this installation uses, and information about the instance." />
      <div className="space-y-4">
        <Account />
        <Integrations />
        <About />
      </div>
    </>
  );
}
