import { useQuery } from "@tanstack/react-query";
import clsx from "clsx";
import {
  Activity, Bell, FileSearch, FileText, Gauge, Globe2, Languages, LayoutDashboard, Link2, LogOut, MapPin, Menu, Moon, Network,
  PenLine, Search, Settings, Share2, ListTree, Sun, Swords, Braces, Bug, KeyRound, LineChart, X,
} from "lucide-react";
import { type ReactNode, useEffect, useState } from "react";
import { Link, NavLink, useLocation } from "react-router-dom";
import { api } from "../lib/api";
import { useAuth, useSite, useTheme } from "../lib/context";
import { scoreColor } from "../lib/format";
import { Select } from "./ui";

export const NAV: { section: string; items: { to: string; label: string; icon: ReactNode }[] }[] = [
  { section: "Overview", items: [
    { to: "/", label: "Dashboard", icon: <LayoutDashboard className="h-4 w-4" /> },
    { to: "/sites", label: "Websites", icon: <Globe2 className="h-4 w-4" /> },
  ] },
  { section: "Technical SEO", items: [
    { to: "/audit", label: "Site Audit", icon: <Bug className="h-4 w-4" /> },
    { to: "/crawler", label: "Crawler", icon: <FileSearch className="h-4 w-4" /> },
    { to: "/internal-links", label: "Internal Linking", icon: <Network className="h-4 w-4" /> },
    { to: "/sitemaps", label: "Sitemaps & Indexing", icon: <ListTree className="h-4 w-4" /> },
    { to: "/schema", label: "Schema Markup", icon: <Braces className="h-4 w-4" /> },
    { to: "/pagespeed", label: "Page Speed", icon: <Gauge className="h-4 w-4" /> },
    { to: "/international", label: "International SEO", icon: <Languages className="h-4 w-4" /> },
    { to: "/local", label: "Local SEO", icon: <MapPin className="h-4 w-4" /> },
  ] },
  { section: "Research & Content", items: [
    { to: "/keywords", label: "Keyword Research", icon: <KeyRound className="h-4 w-4" /> },
    { to: "/serp", label: "SERP Analysis", icon: <Search className="h-4 w-4" /> },
    { to: "/content", label: "Content Optimizer", icon: <PenLine className="h-4 w-4" /> },
    { to: "/competitors", label: "Competitors", icon: <Swords className="h-4 w-4" /> },
    { to: "/backlinks", label: "Backlinks", icon: <Link2 className="h-4 w-4" /> },
    { to: "/search-console", label: "Search Console", icon: <LineChart className="h-4 w-4" /> },
  ] },
  { section: "Operations", items: [
    { to: "/monitoring", label: "Monitoring", icon: <Activity className="h-4 w-4" /> },
    { to: "/reports", label: "Reports", icon: <FileText className="h-4 w-4" /> },
    { to: "/settings", label: "Settings", icon: <Settings className="h-4 w-4" /> },
  ] },
];

function Brand() {
  return (
    <Link to="/" className="flex items-center gap-2 px-1">
      <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-600 text-white"><Share2 className="h-4 w-4" /></span>
      <span className="leading-tight">
        <span className="block text-sm font-semibold text-slate-900 dark:text-slate-50">OpenSEOSuite</span>
        <span className="block text-[11px] text-slate-500 dark:text-slate-400">open source · self-hosted</span>
      </span>
    </Link>
  );
}

export default function Layout({ children }: { children: ReactNode }) {
  const { user, logout } = useAuth();
  const { sites, site, setSiteId } = useSite();
  const [dark, toggleTheme] = useTheme();
  const [open, setOpen] = useState(false);
  const location = useLocation();
  useEffect(() => setOpen(false), [location.pathname]);
  const { data: alerts } = useQuery({ queryKey: ["alerts", "unread"], queryFn: () => api.get("/alerts", { unread: true, per_page: 1 }), refetchInterval: 60_000 });
  const unread = alerts?.unread ?? 0;

  const sidebar = (
    <nav className="flex h-full flex-col gap-5 overflow-y-auto px-3 py-4" aria-label="Main">
      <Brand />
      {NAV.map((group) => (
        <div key={group.section}>
          <div className="mb-1 px-2 text-[11px] font-semibold uppercase tracking-wider text-slate-400 dark:text-slate-500">{group.section}</div>
          <ul className="space-y-0.5">
            {group.items.map((item) => (
              <li key={item.to}>
                <NavLink to={item.to} end={item.to === "/"}
                  className={({ isActive }) => clsx("flex items-center gap-2.5 rounded-lg px-2 py-1.5 text-sm transition",
                    isActive ? "bg-brand-50 font-medium text-brand-700 dark:bg-brand-900/30 dark:text-brand-200"
                      : "text-slate-600 hover:bg-slate-100 hover:text-slate-900 dark:text-slate-300 dark:hover:bg-slate-800 dark:hover:text-slate-50")}>
                  {item.icon}{item.label}
                </NavLink>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </nav>
  );

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 dark:bg-slate-950 dark:text-slate-100">
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-60 border-r border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900 lg:block">{sidebar}</aside>
      {open && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div className="absolute inset-0 bg-slate-900/50" onClick={() => setOpen(false)} />
          <aside className="absolute inset-y-0 left-0 w-64 border-r border-slate-200 bg-white shadow-xl dark:border-slate-800 dark:bg-slate-900">
            <button className="absolute right-2 top-3 rounded p-1 text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800" onClick={() => setOpen(false)} aria-label="Close menu"><X className="h-5 w-5" /></button>
            {sidebar}
          </aside>
        </div>
      )}
      <div className="lg:pl-60">
        <header className="sticky top-0 z-20 flex h-14 items-center gap-3 border-b border-slate-200 bg-white/90 px-4 backdrop-blur dark:border-slate-800 dark:bg-slate-900/90">
          <button className="rounded p-1.5 text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800 lg:hidden" onClick={() => setOpen(true)} aria-label="Open menu"><Menu className="h-5 w-5" /></button>
          {sites.length > 0 ? (
            <div className="flex min-w-0 items-center gap-2">
              <Select aria-label="Selected website" value={site?.id ?? ""} onChange={(e) => setSiteId(Number(e.target.value))} className="max-w-[16rem]">
                {sites.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
              </Select>
              {site?.last_crawl?.score !== null && site?.last_crawl?.score !== undefined && (
                <span className="hidden items-center gap-1.5 text-xs text-slate-500 dark:text-slate-400 sm:flex" title="SEO score of the latest completed crawl">
                  <span className="h-2 w-2 rounded-full" style={{ background: scoreColor(site.last_crawl.score) }} />
                  score {Math.round(site.last_crawl.score)}
                </span>
              )}
              {site?.active_crawl && <span className="hidden rounded-md bg-brand-50 px-1.5 py-0.5 text-xs font-medium text-brand-700 dark:bg-brand-900/30 dark:text-brand-200 sm:inline">crawling…</span>}
            </div>
          ) : (
            <Link to="/sites" className="text-sm font-medium text-brand-700 hover:underline dark:text-brand-300">Add your first website</Link>
          )}
          <div className="ml-auto flex items-center gap-1">
            <Link to="/monitoring?tab=alerts" className="relative rounded-lg p-2 text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800" aria-label={`Alerts (${unread} unread)`}>
              <Bell className="h-4 w-4" />
              {unread > 0 && <span className="absolute right-1 top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-red-600 px-1 text-[10px] font-semibold text-white">{unread > 99 ? "99+" : unread}</span>}
            </Link>
            <button onClick={toggleTheme} className="rounded-lg p-2 text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800" aria-label={dark ? "Switch to light mode" : "Switch to dark mode"}>
              {dark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
            </button>
            <span className="mx-1 hidden text-xs text-slate-500 dark:text-slate-400 md:inline">{user?.email}</span>
            <button onClick={logout} className="rounded-lg p-2 text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800" aria-label="Sign out"><LogOut className="h-4 w-4" /></button>
          </div>
        </header>
        <main className="mx-auto max-w-[1400px] p-4 sm:p-6">{children}</main>
      </div>
    </div>
  );
}
