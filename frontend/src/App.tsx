import { lazy, Suspense } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import { Spinner } from "./components/ui";
import { SiteProvider, useAuth } from "./lib/context";
import Login from "./pages/Login";

const Dashboard = lazy(() => import("./pages/Dashboard"));
const Sites = lazy(() => import("./pages/Sites"));
const Audit = lazy(() => import("./pages/Audit"));
const IssueDetail = lazy(() => import("./pages/IssueDetail"));
const PageDetail = lazy(() => import("./pages/PageDetail"));
const Crawler = lazy(() => import("./pages/Crawler"));
const InternalLinks = lazy(() => import("./pages/InternalLinks"));
const Sitemaps = lazy(() => import("./pages/Sitemaps"));
const Schema = lazy(() => import("./pages/Schema"));
const PageSpeed = lazy(() => import("./pages/PageSpeed"));
const International = lazy(() => import("./pages/International"));
const Local = lazy(() => import("./pages/Local"));
const Keywords = lazy(() => import("./pages/Keywords"));
const Serp = lazy(() => import("./pages/Serp"));
const Content = lazy(() => import("./pages/Content"));
const Competitors = lazy(() => import("./pages/Competitors"));
const Backlinks = lazy(() => import("./pages/Backlinks"));
const SearchConsole = lazy(() => import("./pages/SearchConsole"));
const Monitoring = lazy(() => import("./pages/Monitoring"));
const Reports = lazy(() => import("./pages/Reports"));
const Settings = lazy(() => import("./pages/Settings"));

export default function App() {
  const { user, loading } = useAuth();
  if (loading) return <Spinner label="Starting…" />;
  if (!user) return <Login />;
  return (
    <SiteProvider>
      <Layout>
        <Suspense fallback={<Spinner />}>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/sites" element={<Sites />} />
            <Route path="/audit" element={<Audit />} />
            <Route path="/audit/issues/:ruleId" element={<IssueDetail />} />
            <Route path="/pages/:crawlId/:pageId" element={<PageDetail />} />
            <Route path="/crawler" element={<Crawler />} />
            <Route path="/internal-links" element={<InternalLinks />} />
            <Route path="/sitemaps" element={<Sitemaps />} />
            <Route path="/schema" element={<Schema />} />
            <Route path="/pagespeed" element={<PageSpeed />} />
            <Route path="/international" element={<International />} />
            <Route path="/local" element={<Local />} />
            <Route path="/keywords" element={<Keywords />} />
            <Route path="/serp" element={<Serp />} />
            <Route path="/content" element={<Content />} />
            <Route path="/competitors" element={<Competitors />} />
            <Route path="/backlinks" element={<Backlinks />} />
            <Route path="/search-console" element={<SearchConsole />} />
            <Route path="/monitoring" element={<Monitoring />} />
            <Route path="/reports" element={<Reports />} />
            <Route path="/settings" element={<Settings />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </Suspense>
      </Layout>
    </SiteProvider>
  );
}
