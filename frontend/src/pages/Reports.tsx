import { Download } from "lucide-react";
import { type ReactNode, useState } from "react";
import { Link } from "react-router-dom";
import { Button, Card, EmptyState, Notice, PageHeader, Spinner } from "../components/ui";
import { api, errorMessage } from "../lib/api";
import { useSite } from "../lib/context";
import { fmtDateTime, fmtInt } from "../lib/format";

interface Format {
  label: string;
  path: string;
  query?: Record<string, string>;
  fallback: string;
}
interface Report {
  title: string;
  description: string;
  formats: Format[];
  needsCrawl?: boolean;
}

function ReportRow({ report, disabled }: { report: Report; disabled: boolean }) {
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const run = async (f: Format) => {
    setBusy(f.label);
    setError(null);
    try {
      await api.download(f.path, f.query, f.fallback);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(null);
    }
  };
  return (
    <li className="px-4 py-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0 flex-1 basis-64">
          <div className="text-sm font-medium text-slate-900 dark:text-slate-100">{report.title}</div>
          <div className="text-xs text-slate-500 dark:text-slate-400">{report.description}</div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {report.formats.map((f) => (
            <Button key={f.label} size="sm" icon={<Download className="h-3.5 w-3.5" />} loading={busy === f.label} disabled={disabled || busy !== null}
              title={disabled ? "Needs a completed crawl" : undefined} onClick={() => run(f)}>{f.label}</Button>
          ))}
        </div>
      </div>
      {error && <p role="alert" className="mt-1.5 break-words text-xs text-red-600 dark:text-red-400">Download failed: {error}</p>}
    </li>
  );
}

function Group({ title, description, reports, disabled, notice }: { title: string; description: string; reports: Report[]; disabled?: boolean; notice?: ReactNode }) {
  return (
    <Card title={title} description={description} padded={false}>
      {notice && <div className="p-3 pb-0">{notice}</div>}
      <ul className="divide-y divide-slate-100 dark:divide-slate-800">
        {reports.map((r) => <ReportRow key={r.title} report={r} disabled={!!disabled} />)}
      </ul>
    </Card>
  );
}

export default function Reports() {
  const { site, crawlId, loading } = useSite();
  if (loading) return <Spinner />;
  const linkClass = "font-medium text-brand-700 hover:underline dark:text-brand-300";
  if (!site) {
    return (
      <>
        <PageHeader title="Reports" description="Every downloadable report and export in one place." />
        <Card><EmptyState title="Add a website first" description="Reports are generated for the selected website." action={<Link to="/sites" className={`text-sm ${linkClass}`}>Go to Websites</Link>} /></Card>
      </>
    );
  }

  const crawlPath = `/crawls/${crawlId}`;
  const exp = (dataset: string, format: string, label: string): Format => ({ label, path: `${crawlPath}/export`, query: { dataset, format }, fallback: `${site.domain}-${dataset}.${format}` });
  const crawlReports: Report[] = [
    { title: "Technical audit report", description: "Shareable summary of the score, issues by severity and example URLs for each issue.",
      formats: [{ label: "PDF", path: `${crawlPath}/report.pdf`, fallback: `seo-audit-${site.domain}.pdf` }] },
    { title: "Full crawl workbook", description: "One Excel file with summary, issues, pages, broken links and redirects on separate sheets.", formats: [exp("all", "xlsx", "Excel")] },
    { title: "Pages", description: "Every crawled URL with status, indexability, title, word count, depth, inlinks and score.", formats: [exp("pages", "csv", "CSV")] },
    { title: "Issues", description: "Every issue occurrence with severity, affected URL, details and the recommended fix.", formats: [exp("issues", "csv", "CSV")] },
    { title: "Links", description: "Every link found: source, target, anchor text, internal/external, nofollow and target status.", formats: [exp("links", "csv", "CSV")] },
    { title: "Redirects", description: "Redirecting URLs with their full chain, hop count, loops and final status.", formats: [exp("redirects", "csv", "CSV")] },
    { title: "Crawl data", description: "Crawl statistics and all pages in a machine-readable file for your own tooling.", formats: [exp("pages", "json", "JSON")] },
    { title: "Generated XML sitemap", description: "A ready-to-upload sitemap built from the indexable pages found by the crawl (first file if the site needs several).",
      formats: [{ label: "XML", path: `${crawlPath}/sitemap.xml`, fallback: "sitemap.xml" }] },
  ];
  const siteReports: Report[] = [
    { title: "Keyword report", description: "Tracked keywords with cluster, intent, Search Console metrics and imported volumes. Excel adds the page mapping.",
      formats: [
        { label: "Excel", path: `/sites/${site.id}/keywords/export`, query: { format: "xlsx" }, fallback: `keywords-${site.domain}.xlsx` },
        { label: "CSV", path: `/sites/${site.id}/keywords/export`, query: { format: "csv" }, fallback: `keywords-${site.domain}.csv` },
      ] },
    { title: "Competitor comparison", description: "Side-by-side comparison of this website with the competitors you added.",
      formats: [{ label: "PDF", path: `/sites/${site.id}/competitors/report.pdf`, fallback: `competitors-${site.domain}.pdf` }] },
    { title: "Backlinks", description: "Imported backlinks. Excel adds referring-domain and anchor-text summaries.",
      formats: [
        { label: "Excel", path: `/sites/${site.id}/backlinks/export`, query: { format: "xlsx" }, fallback: `backlinks-${site.domain}.xlsx` },
        { label: "CSV", path: `/sites/${site.id}/backlinks/export`, query: { format: "csv" }, fallback: `backlinks-${site.domain}.csv` },
      ] },
  ];
  const accountReports: Report[] = [
    { title: "Alerts", description: "The 500 most recent monitoring alerts across all of your websites.", formats: [{ label: "CSV", path: "/alerts/export", fallback: "alerts.csv" }] },
  ];

  return (
    <>
      <PageHeader title="Reports" description={<>Every downloadable report and export for <span className="font-medium text-slate-700 dark:text-slate-200">{site.name}</span>.</>} />
      <div className="space-y-4">
        <Group title="Crawl reports" disabled={crawlId === null} reports={crawlReports}
          description={crawlId !== null && site.last_crawl ? `From crawl #${crawlId} · ${fmtInt(site.last_crawl.pages_crawled)} URLs · ${fmtDateTime(site.last_crawl.finished_at)}` : "Built from the latest completed crawl"}
          notice={crawlId === null ? (
            <Notice tone="warn">
              {site.active_crawl ? "These reports unlock when the running crawl finishes. " : "These reports need a completed crawl. "}
              <Link to="/crawler" className={linkClass}>{site.active_crawl ? "View progress" : "Start a crawl"}</Link>
            </Notice>
          ) : undefined} />
        <Group title="Website reports" description="Built from data you track or import for this website. Files can be empty if nothing has been added yet." reports={siteReports} />
        <Group title="Account" description="Not tied to the selected website" reports={accountReports} />
        <p className="text-xs text-slate-500 dark:text-slate-400">Need an older crawl? Individual crawls can be exported from the <Link to="/crawler" className={linkClass}>Crawler</Link> page.</p>
      </div>
    </>
  );
}
