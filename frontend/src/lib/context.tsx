import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createContext, type ReactNode, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { api, setUnauthorizedHandler, tokenStore } from "./api";

/* ------------------------------------------------------------------ types */
export interface User {
  id: number;
  email: string;
  is_admin: boolean;
}
export interface CrawlSummary {
  id: number;
  site_id: number;
  status: "queued" | "running" | "completed" | "failed" | "cancelled";
  start_url: string;
  score: number | null;
  pages_crawled: number;
  error: string | null;
  job_id: number | null;
  config: Record<string, any>;
  created_at: string | null;
  started_at: string | null;
  finished_at: string | null;
  issues_by_severity: Record<string, number> | null;
  stats?: Record<string, any>;
}
export interface Site {
  id: number;
  name: string;
  url: string;
  domain: string;
  gsc_property: string | null;
  crawl_config: Record<string, any>;
  created_at: string;
  last_crawl: CrawlSummary | null;
  active_crawl: CrawlSummary | null;
}

/* ------------------------------------------------------------------ auth */
interface AuthState {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  logout: () => void;
}
const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const qc = useQueryClient();

  const logout = useCallback(() => {
    tokenStore.clear();
    setUser(null);
    qc.clear();
  }, [qc]);

  useEffect(() => {
    setUnauthorizedHandler(() => setUser(null));
    if (!tokenStore.get()) {
      setLoading(false);
      return;
    }
    api
      .get<User>("/auth/me")
      .then(setUser)
      .catch(() => tokenStore.clear())
      .finally(() => setLoading(false));
  }, []);

  const value = useMemo<AuthState>(
    () => ({
      user,
      loading,
      logout,
      login: async (email, password) => {
        const r = await api.post("/auth/login", { email, password });
        tokenStore.set(r.access_token);
        setUser(r.user);
      },
      register: async (email, password) => {
        const r = await api.post("/auth/register", { email, password });
        tokenStore.set(r.access_token);
        setUser(r.user);
      },
    }),
    [user, loading, logout],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}

/* ------------------------------------------------------------------ selected site */
interface SiteState {
  sites: Site[];
  site: Site | null;
  /** id of the latest *completed* crawl of the selected site, if any */
  crawlId: number | null;
  loading: boolean;
  setSiteId: (id: number) => void;
  refresh: () => void;
}
const SiteContext = createContext<SiteState | null>(null);
const SITE_KEY = "seotk.site";

export function SiteProvider({ children }: { children: ReactNode }) {
  const qc = useQueryClient();
  const [siteId, setSiteIdState] = useState<number | null>(() => {
    const v = Number(localStorage.getItem(SITE_KEY));
    return Number.isFinite(v) && v > 0 ? v : null;
  });
  const { data: sites = [], isLoading } = useQuery<Site[]>({
    queryKey: ["sites"],
    queryFn: () => api.get("/sites"),
    // poll while any crawl is running so scores and statuses stay current
    refetchInterval: (q) => ((q.state.data ?? []).some((s) => s.active_crawl) ? 3000 : false),
  });
  const site = sites.find((s) => s.id === siteId) ?? sites[0] ?? null;
  const setSiteId = useCallback((id: number) => {
    localStorage.setItem(SITE_KEY, String(id));
    setSiteIdState(id);
  }, []);
  const refresh = useCallback(() => void qc.invalidateQueries({ queryKey: ["sites"] }), [qc]);
  const value = useMemo<SiteState>(
    () => ({ sites, site, crawlId: site?.last_crawl?.id ?? null, loading: isLoading, setSiteId, refresh }),
    [sites, site, isLoading, setSiteId, refresh],
  );
  return <SiteContext.Provider value={value}>{children}</SiteContext.Provider>;
}

export function useSite(): SiteState {
  const ctx = useContext(SiteContext);
  if (!ctx) throw new Error("useSite must be used inside SiteProvider");
  return ctx;
}

/* ------------------------------------------------------------------ theme */
const THEME_KEY = "seotk.theme";
export function useTheme(): [boolean, () => void] {
  const [dark, setDark] = useState(() => {
    const saved = localStorage.getItem(THEME_KEY);
    return saved ? saved === "dark" : window.matchMedia?.("(prefers-color-scheme: dark)").matches ?? false;
  });
  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
    localStorage.setItem(THEME_KEY, dark ? "dark" : "light");
  }, [dark]);
  return [dark, () => setDark((d) => !d)];
}

/* ------------------------------------------------------------------ jobs */
export interface Job {
  id: number;
  kind: string;
  status: "queued" | "running" | "completed" | "failed" | "cancelled";
  progress: number;
  message: string | null;
  error: string | null;
  result: Record<string, any>;
}

/** Poll a background job until it finishes. Pass null to disable. */
export function useJob(jobId: number | null | undefined, onDone?: (job: Job) => void) {
  const q = useQuery<Job>({
    queryKey: ["job", jobId],
    queryFn: () => api.get(`/jobs/${jobId}`),
    enabled: !!jobId,
    refetchInterval: (query) => (["completed", "failed", "cancelled"].includes(query.state.data?.status ?? "") ? false : 1200),
  });
  const status = q.data?.status;
  useEffect(() => {
    if (q.data && status && ["completed", "failed", "cancelled"].includes(status)) onDone?.(q.data);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status]);
  return q.data ?? null;
}
