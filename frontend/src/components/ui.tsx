/** Shared UI kit. Every page composes these so the product looks and behaves consistently. */
import clsx from "clsx";
import { AlertTriangle, ChevronLeft, ChevronRight, Download, HelpCircle, Inbox, Loader2, Search, X } from "lucide-react";
import { type ButtonHTMLAttributes, type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes, useEffect, useRef, useState } from "react";
import { api, errorMessage } from "../lib/api";
import { scoreColor, type Severity } from "../lib/format";

/* ------------------------------------------------------------------ layout primitives */
export function PageHeader({ title, description, actions }: { title: string; description?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-start justify-between gap-3">
      <div className="min-w-0">
        <h1 className="text-xl font-semibold tracking-tight text-slate-900 dark:text-slate-50">{title}</h1>
        {description && <p className="mt-1 max-w-3xl text-sm text-slate-500 dark:text-slate-400">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}

export function Card({ title, description, actions, children, className, padded = true }: {
  title?: ReactNode; description?: ReactNode; actions?: ReactNode; children?: ReactNode; className?: string; padded?: boolean;
}) {
  return (
    <section className={clsx("rounded-xl border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-900", className)}>
      {(title || actions) && (
        <header className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 px-4 py-3 dark:border-slate-800">
          <div className="min-w-0">
            {title && <h2 className="text-sm font-semibold text-slate-900 dark:text-slate-100">{title}</h2>}
            {description && <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">{description}</p>}
          </div>
          {actions && <div className="flex items-center gap-2">{actions}</div>}
        </header>
      )}
      <div className={padded ? "p-4" : ""}>{children}</div>
    </section>
  );
}

export function Stat({ label, value, hint, tone, tooltip }: { label: string; value: ReactNode; hint?: ReactNode; tone?: "good" | "warn" | "bad"; tooltip?: string }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-900">
      <div className="flex items-center gap-1 text-xs font-medium uppercase tracking-wide text-slate-500 dark:text-slate-400">
        {label}
        {tooltip && <Tooltip text={tooltip} />}
      </div>
      <div className={clsx("mt-1.5 text-2xl font-semibold tabular-nums",
        tone === "good" ? "text-emerald-600 dark:text-emerald-400" : tone === "warn" ? "text-amber-600 dark:text-amber-400"
        : tone === "bad" ? "text-red-600 dark:text-red-400" : "text-slate-900 dark:text-slate-50")}>{value}</div>
      {hint && <div className="mt-1 text-xs text-slate-500 dark:text-slate-400">{hint}</div>}
    </div>
  );
}

/* ------------------------------------------------------------------ buttons & inputs */
type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "secondary" | "ghost" | "danger"; size?: "sm" | "md"; loading?: boolean; icon?: ReactNode };

export function Button({ variant = "secondary", size = "md", loading, icon, children, className, disabled, ...rest }: ButtonProps) {
  return (
    <button
      {...rest}
      disabled={disabled || loading}
      className={clsx(
        "inline-flex items-center justify-center gap-1.5 rounded-lg font-medium transition focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-1 disabled:cursor-not-allowed disabled:opacity-50 dark:focus-visible:ring-offset-slate-900",
        size === "sm" ? "h-8 px-2.5 text-xs" : "h-9 px-3.5 text-sm",
        variant === "primary" && "bg-brand-600 text-white hover:bg-brand-700",
        variant === "secondary" && "border border-slate-300 bg-white text-slate-700 hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:hover:bg-slate-800",
        variant === "ghost" && "text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800",
        variant === "danger" && "bg-red-600 text-white hover:bg-red-700",
        className,
      )}
    >
      {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : icon}
      {children}
    </button>
  );
}

const fieldClass =
  "h-9 w-full rounded-lg border border-slate-300 bg-white px-3 text-sm text-slate-900 placeholder:text-slate-400 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20 disabled:opacity-60 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100";

export function Input({ className, ...rest }: InputHTMLAttributes<HTMLInputElement>) {
  return <input {...rest} className={clsx(fieldClass, className)} />;
}

export function Select({ className, children, ...rest }: SelectHTMLAttributes<HTMLSelectElement>) {
  return <select {...rest} className={clsx(fieldClass, "pr-8", className)}>{children}</select>;
}

export function Textarea({ className, ...rest }: React.TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea {...rest} className={clsx(fieldClass, "h-auto py-2 leading-relaxed", className)} />;
}

export function Field({ label, hint, children, className }: { label: string; hint?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <label className={clsx("block", className)}>
      <span className="mb-1 block text-xs font-medium text-slate-600 dark:text-slate-300">{label}</span>
      {children}
      {hint && <span className="mt-1 block text-xs text-slate-500 dark:text-slate-400">{hint}</span>}
    </label>
  );
}

export function Checkbox({ label, checked, onChange, hint }: { label: string; checked: boolean; onChange: (v: boolean) => void; hint?: string }) {
  return (
    <label className="flex cursor-pointer items-start gap-2 text-sm text-slate-700 dark:text-slate-200">
      <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)}
        className="mt-0.5 h-4 w-4 rounded border-slate-300 text-brand-600 focus:ring-brand-500 dark:border-slate-600 dark:bg-slate-900" />
      <span>{label}{hint && <span className="block text-xs text-slate-500 dark:text-slate-400">{hint}</span>}</span>
    </label>
  );
}

export function SearchInput({ value, onChange, placeholder = "Search…" }: { value: string; onChange: (v: string) => void; placeholder?: string }) {
  const [local, setLocal] = useState(value);
  useEffect(() => setLocal(value), [value]);
  useEffect(() => {
    const t = setTimeout(() => local !== value && onChange(local), 300);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [local]);
  return (
    <div className="relative w-full max-w-xs">
      <Search className="pointer-events-none absolute left-2.5 top-2.5 h-4 w-4 text-slate-400" />
      <Input value={local} onChange={(e) => setLocal(e.target.value)} placeholder={placeholder} className="pl-8" aria-label={placeholder} />
    </div>
  );
}

/* ------------------------------------------------------------------ badges */
const toneClass: Record<string, string> = {
  gray: "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300",
  red: "bg-red-50 text-red-700 ring-1 ring-inset ring-red-600/20 dark:bg-red-950/50 dark:text-red-300",
  orange: "bg-orange-50 text-orange-700 ring-1 ring-inset ring-orange-600/20 dark:bg-orange-950/50 dark:text-orange-300",
  amber: "bg-amber-50 text-amber-800 ring-1 ring-inset ring-amber-600/20 dark:bg-amber-950/50 dark:text-amber-300",
  green: "bg-emerald-50 text-emerald-700 ring-1 ring-inset ring-emerald-600/20 dark:bg-emerald-950/50 dark:text-emerald-300",
  blue: "bg-brand-50 text-brand-700 ring-1 ring-inset ring-brand-600/20 dark:bg-brand-900/30 dark:text-brand-200",
  purple: "bg-violet-50 text-violet-700 ring-1 ring-inset ring-violet-600/20 dark:bg-violet-950/50 dark:text-violet-300",
};

export function Badge({ tone = "gray", children, title }: { tone?: keyof typeof toneClass | string; children: ReactNode; title?: string }) {
  return <span title={title} className={clsx("inline-flex items-center whitespace-nowrap rounded-md px-1.5 py-0.5 text-xs font-medium", toneClass[tone] ?? toneClass.gray)}>{children}</span>;
}

export function SeverityBadge({ severity }: { severity: Severity | string }) {
  const tone = { critical: "red", high: "orange", medium: "amber", low: "gray" }[severity] ?? "gray";
  return <Badge tone={tone}>{severity}</Badge>;
}

export function StatusCode({ code, error }: { code: number | null | undefined; error?: string | null }) {
  if (code === null || code === undefined) return <Badge tone="red" title={error ?? undefined}>{error ? "error" : "–"}</Badge>;
  const tone = code < 300 ? "green" : code < 400 ? "blue" : code < 500 ? "orange" : "red";
  return <Badge tone={tone}>{code}</Badge>;
}

/** Makes the provenance of a number explicit: measured data, an estimate, imported by the user, or unavailable. */
export function DataBadge({ kind }: { kind: "measured" | "estimated" | "imported" | "unavailable" }) {
  const map = {
    measured: ["green", "Measured directly by this toolkit or by Google Search Console"],
    estimated: ["amber", "An estimate derived from heuristics. Treat as directional, not exact"],
    imported: ["blue", "Taken from a file you imported"],
    unavailable: ["gray", "No legitimate free data source exists, so no value is shown"],
  } as const;
  return <Badge tone={map[kind][0]} title={map[kind][1]}>{kind}</Badge>;
}

export function Tooltip({ text }: { text: string }) {
  return (
    <span className="group relative inline-flex">
      <HelpCircle className="h-3.5 w-3.5 cursor-help text-slate-400" aria-label={text} />
      <span role="tooltip" className="pointer-events-none absolute bottom-full left-1/2 z-50 mb-1.5 hidden w-56 -translate-x-1/2 rounded-md bg-slate-900 px-2 py-1.5 text-xs font-normal normal-case leading-snug tracking-normal text-white shadow-lg group-hover:block dark:bg-slate-700">
        {text}
      </span>
    </span>
  );
}

/* ------------------------------------------------------------------ states */
export function Spinner({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="flex items-center justify-center gap-2 py-12 text-sm text-slate-500 dark:text-slate-400" role="status">
      <Loader2 className="h-4 w-4 animate-spin" /> {label}
    </div>
  );
}

export function ErrorBox({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  return (
    <div role="alert" className="flex items-start gap-3 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800 dark:border-red-900 dark:bg-red-950/40 dark:text-red-200">
      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
      <div className="min-w-0 flex-1 break-words">{typeof error === "string" ? error : errorMessage(error)}</div>
      {onRetry && <Button size="sm" onClick={onRetry}>Retry</Button>}
    </div>
  );
}

export function Notice({ tone = "info", children }: { tone?: "info" | "warn" | "success"; children: ReactNode }) {
  return (
    <div className={clsx("rounded-lg border p-3 text-sm",
      tone === "info" && "border-brand-200 bg-brand-50 text-brand-900 dark:border-brand-900 dark:bg-brand-900/20 dark:text-brand-100",
      tone === "warn" && "border-amber-200 bg-amber-50 text-amber-900 dark:border-amber-900 dark:bg-amber-950/30 dark:text-amber-100",
      tone === "success" && "border-emerald-200 bg-emerald-50 text-emerald-900 dark:border-emerald-900 dark:bg-emerald-950/30 dark:text-emerald-100")}>
      {children}
    </div>
  );
}

export function EmptyState({ title, description, action, icon }: { title: string; description?: ReactNode; action?: ReactNode; icon?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center px-6 py-14 text-center">
      <div className="mb-3 rounded-full bg-slate-100 p-3 text-slate-400 dark:bg-slate-800">{icon ?? <Inbox className="h-6 w-6" />}</div>
      <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">{title}</h3>
      {description && <p className="mt-1 max-w-md text-sm text-slate-500 dark:text-slate-400">{description}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

export function ProgressBar({ value, label }: { value: number; label?: string }) {
  const pct = Math.max(0, Math.min(100, Math.round(value * 100)));
  return (
    <div>
      <div className="h-2 w-full overflow-hidden rounded-full bg-slate-200 dark:bg-slate-800" role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100}>
        <div className="h-full rounded-full bg-brand-600 transition-all duration-500" style={{ width: `${pct}%` }} />
      </div>
      {label && <div className="mt-1 flex justify-between text-xs text-slate-500 dark:text-slate-400"><span>{label}</span><span>{pct}%</span></div>}
    </div>
  );
}

export function ScoreRing({ score, size = 96, label = "score" }: { score: number | null | undefined; size?: number; label?: string }) {
  const r = (size - 10) / 2;
  const c = 2 * Math.PI * r;
  const pct = score === null || score === undefined ? 0 : Math.max(0, Math.min(100, score)) / 100;
  return (
    <div className="relative inline-flex items-center justify-center" style={{ width: size, height: size }} title={`${label}: ${score ?? "n/a"}`}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" strokeWidth="8" className="stroke-slate-200 dark:stroke-slate-800" />
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" strokeWidth="8" strokeLinecap="round" stroke={scoreColor(score)} strokeDasharray={c} strokeDashoffset={c * (1 - pct)} />
      </svg>
      <div className="absolute text-center">
        <div className="text-xl font-semibold tabular-nums text-slate-900 dark:text-slate-50">{score === null || score === undefined ? "–" : Math.round(score)}</div>
        <div className="text-[10px] uppercase tracking-wide text-slate-500">{label}</div>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ tabs / modal */
export function Tabs<T extends string>({ tabs, value, onChange }: { tabs: { id: T; label: string; count?: number | null }[]; value: T; onChange: (id: T) => void }) {
  return (
    <div className="mb-4 flex gap-1 overflow-x-auto border-b border-slate-200 dark:border-slate-800" role="tablist">
      {tabs.map((t) => (
        <button key={t.id} role="tab" aria-selected={value === t.id} onClick={() => onChange(t.id)}
          className={clsx("-mb-px flex items-center gap-1.5 whitespace-nowrap border-b-2 px-3 py-2 text-sm font-medium transition",
            value === t.id ? "border-brand-600 text-brand-700 dark:border-brand-400 dark:text-brand-300"
              : "border-transparent text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-200")}>
          {t.label}
          {t.count !== undefined && t.count !== null && <span className="rounded-full bg-slate-100 px-1.5 text-xs text-slate-600 dark:bg-slate-800 dark:text-slate-300">{t.count}</span>}
        </button>
      ))}
    </div>
  );
}

export function Modal({ open, onClose, title, children, wide, footer }: { open: boolean; onClose: () => void; title: string; children: ReactNode; wide?: boolean; footer?: ReactNode }) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-slate-900/50 p-4 backdrop-blur-sm sm:p-8" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div role="dialog" aria-modal="true" aria-label={title} className={clsx("w-full rounded-xl border border-slate-200 bg-white shadow-xl dark:border-slate-700 dark:bg-slate-900", wide ? "max-w-4xl" : "max-w-lg")}>
        <header className="flex items-center justify-between border-b border-slate-100 px-4 py-3 dark:border-slate-800">
          <h2 className="text-sm font-semibold text-slate-900 dark:text-slate-100">{title}</h2>
          <button onClick={onClose} aria-label="Close" className="rounded p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-700 dark:hover:bg-slate-800"><X className="h-4 w-4" /></button>
        </header>
        <div className="max-h-[75vh] overflow-y-auto p-4">{children}</div>
        {footer && <footer className="flex justify-end gap-2 border-t border-slate-100 px-4 py-3 dark:border-slate-800">{footer}</footer>}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ table */
export interface Column<T> {
  key: string;
  header: ReactNode;
  render: (row: T) => ReactNode;
  align?: "left" | "right" | "center";
  sortKey?: string; // server-side sort key; makes the header clickable
  width?: string;
  tooltip?: string;
}

export function DataTable<T>({ columns, rows, rowKey, onRowClick, sort, order, onSort, empty, dense }: {
  columns: Column<T>[]; rows: T[]; rowKey: (row: T, index: number) => string | number; onRowClick?: (row: T) => void;
  sort?: string; order?: "asc" | "desc"; onSort?: (key: string) => void; empty?: ReactNode; dense?: boolean;
}) {
  if (!rows.length) return <>{empty ?? <EmptyState title="Nothing to show" description="No rows match the current filters." />}</>;
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-max border-collapse text-left text-sm">
        <thead>
          <tr className="border-b border-slate-200 bg-slate-50 text-xs uppercase tracking-wide text-slate-500 dark:border-slate-800 dark:bg-slate-900/60 dark:text-slate-400">
            {columns.map((c) => (
              <th key={c.key} style={{ width: c.width }} className={clsx("px-3 py-2 font-medium", c.align === "right" && "text-right", c.align === "center" && "text-center")}>
                <span className="inline-flex items-center gap-1">
                  {c.sortKey && onSort ? (
                    <button className="inline-flex items-center gap-1 uppercase hover:text-slate-800 dark:hover:text-slate-200" onClick={() => onSort(c.sortKey!)}>
                      {c.header}{sort === c.sortKey && <span aria-hidden>{order === "desc" ? "↓" : "↑"}</span>}
                    </button>
                  ) : c.header}
                  {c.tooltip && <Tooltip text={c.tooltip} />}
                </span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={rowKey(row, i)} onClick={onRowClick ? () => onRowClick(row) : undefined}
              className={clsx("border-b border-slate-100 last:border-0 dark:border-slate-800/70", onRowClick && "cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-800/50")}>
              {columns.map((c) => (
                <td key={c.key} className={clsx("px-3 align-top text-slate-700 dark:text-slate-300", dense ? "py-1.5" : "py-2.5", c.align === "right" && "text-right tabular-nums", c.align === "center" && "text-center")}>
                  {c.render(row)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function Pagination({ page, perPage, total, onPage }: { page: number; perPage: number; total: number; onPage: (p: number) => void }) {
  const pages = Math.max(1, Math.ceil(total / perPage));
  if (total <= perPage) return <div className="px-3 py-2 text-xs text-slate-500 dark:text-slate-400">{total.toLocaleString()} row{total === 1 ? "" : "s"}</div>;
  return (
    <div className="flex items-center justify-between gap-3 px-3 py-2 text-xs text-slate-500 dark:text-slate-400">
      <span>{((page - 1) * perPage + 1).toLocaleString()}–{Math.min(page * perPage, total).toLocaleString()} of {total.toLocaleString()}</span>
      <div className="flex items-center gap-1">
        <Button size="sm" variant="ghost" disabled={page <= 1} onClick={() => onPage(page - 1)} aria-label="Previous page"><ChevronLeft className="h-4 w-4" /></Button>
        <span className="tabular-nums">Page {page} / {pages}</span>
        <Button size="sm" variant="ghost" disabled={page >= pages} onClick={() => onPage(page + 1)} aria-label="Next page"><ChevronRight className="h-4 w-4" /></Button>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ misc */
export function Url({ href, label, className }: { href: string; label?: string; className?: string }) {
  return (
    <a href={href} target="_blank" rel="noopener noreferrer nofollow" onClick={(e) => e.stopPropagation()} title={href}
      className={clsx("break-all text-brand-700 hover:underline dark:text-brand-300", className)}>{label ?? href}</a>
  );
}

/** Export button with a format menu. `formats` maps a label to the download request. */
export function ExportMenu({ formats, label = "Export" }: { formats: { label: string; path: string; query?: Record<string, any> }[]; label?: string }) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const close = (e: MouseEvent) => ref.current && !ref.current.contains(e.target as Node) && setOpen(false);
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, []);
  const run = async (f: { path: string; query?: Record<string, any> }) => {
    setOpen(false);
    setBusy(true);
    setError(null);
    try {
      await api.download(f.path, f.query);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="relative" ref={ref}>
      <Button icon={<Download className="h-4 w-4" />} loading={busy} onClick={() => (formats.length === 1 ? run(formats[0]) : setOpen((o) => !o))} aria-haspopup="menu" aria-expanded={open}>{label}</Button>
      {open && (
        <div role="menu" className="absolute right-0 z-40 mt-1 w-52 overflow-hidden rounded-lg border border-slate-200 bg-white py-1 shadow-lg dark:border-slate-700 dark:bg-slate-900">
          {formats.map((f) => (
            <button key={f.label} role="menuitem" onClick={() => run(f)} className="block w-full px-3 py-2 text-left text-sm text-slate-700 hover:bg-slate-50 dark:text-slate-200 dark:hover:bg-slate-800">{f.label}</button>
          ))}
        </div>
      )}
      {error && <div className="absolute right-0 z-40 mt-1 w-64 rounded-md bg-red-600 px-2 py-1.5 text-xs text-white shadow">{error}</div>}
    </div>
  );
}

export function KeyValue({ items }: { items: [ReactNode, ReactNode][] }) {
  return (
    <dl className="divide-y divide-slate-100 text-sm dark:divide-slate-800">
      {items.map(([k, v], i) => (
        <div key={i} className="grid grid-cols-3 gap-3 py-2">
          <dt className="text-slate-500 dark:text-slate-400">{k}</dt>
          <dd className="col-span-2 break-words text-slate-800 dark:text-slate-200">{v ?? "–"}</dd>
        </div>
      ))}
    </dl>
  );
}

export function FileButton({ onFile, label = "Import CSV", accept = ".csv,.tsv,.txt", loading }: { onFile: (f: File) => void; label?: string; accept?: string; loading?: boolean }) {
  const ref = useRef<HTMLInputElement>(null);
  return (
    <>
      <input ref={ref} type="file" accept={accept} hidden onChange={(e) => { const f = e.target.files?.[0]; if (f) onFile(f); e.target.value = ""; }} />
      <Button loading={loading} onClick={() => ref.current?.click()}>{label}</Button>
    </>
  );
}

/** Shown by site-scoped pages when no site exists or no crawl has completed yet. */
export function NeedsCrawl({ hasSite, running }: { hasSite: boolean; running?: boolean }) {
  return (
    <Card>
      <EmptyState
        title={!hasSite ? "Add a website first" : running ? "Crawl in progress" : "No completed crawl yet"}
        description={!hasSite ? "Add a site under Websites, then run a crawl to populate this view."
          : running ? "This view fills in automatically when the running crawl finishes." : "Start a crawl from the Crawler page to populate this view."}
        action={<a href={hasSite ? "/crawler" : "/sites"} className="text-sm font-medium text-brand-700 hover:underline dark:text-brand-300">{hasSite ? "Go to Crawler" : "Go to Websites"}</a>}
      />
    </Card>
  );
}

export const chartColors = ["#3866f5", "#16a34a", "#ea580c", "#9333ea", "#0891b2", "#ca8a04", "#dc2626", "#64748b"];
