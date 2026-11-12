# Architecture

The rationale for each choice is in `../ARCHITECTURE_DECISIONS.md`. This document describes how the pieces fit together.

## Runtime view

```mermaid
flowchart TB
  subgraph Client
    SPA["React SPA (Vite build)\nTanStack Query · React Router · Recharts"]
  end
  subgraph Server["Single API process (uvicorn, 1 worker)"]
    MW["Middleware\nrate limit · security headers · access log"]
    R["Routers /api\nauth · sites · crawls · tools · integrations"]
    JM["JobManager (asyncio tasks)\n+ scheduler loop (monitors)"]
    subgraph Domain
      CR["crawler/\nFetcher → robots → sitemaps → parser → engine"]
      AU["audit/\npage_checks (during crawl)\nanalysis (after crawl)\nrules · schema · hreflang"]
      KW["keywords/ · serp/ · content/"]
      SV["services/\nbacklinks · competitors · monitoring · settings"]
      IN["integrations/\npagespeed · gsc · ai"]
      RP["reports/ (CSV · XLSX · PDF)"]
    end
    SEC["security/\nauth (Argon2id, JWT) · ssrf guard"]
  end
  DB[("SQLite (default) / PostgreSQL\nSQLAlchemy + Alembic")]
  SPA -->|"Bearer JWT"| MW --> R
  R --> JM
  JM --> CR --> AU
  R --> KW & SV & IN & RP
  CR & KW & SV --> SEC
  AU & R & SV & IN --> DB
```

## Crawl sequence

```mermaid
sequenceDiagram
  participant UI
  participant API
  participant Job as Job runner
  participant C as Crawler
  participant A as Analysis
  participant DB
  UI->>API: POST /sites/{id}/crawls (config)
  API->>DB: insert crawl (queued) + job
  API-->>UI: 202 {crawl, job_id}
  Job->>C: run_crawl(crawl_id)
  C->>C: robots.txt, sitemap discovery
  loop workers (concurrency N, per-host delay)
    C->>C: fetch (SSRF-guarded) → parse → page checks
    C->>DB: pages, links, page-level issues (batched)
  end
  C->>C: site checks (HTTPS, host variant), external links, images
  C->>A: analyse_crawl()
  A->>DB: link statuses, depth, PageRank, duplicates, canonical/hreflang/sitemap issues, scores, stats
  UI->>API: GET /crawls/{id} (polls job progress)
  API-->>UI: completed + stats
```

## Data model

```mermaid
erDiagram
  USER ||--o{ SITE : owns
  SITE ||--o{ CRAWL : has
  SITE ||--o{ COMPETITOR : tracks
  COMPETITOR ||--o{ CRAWL : "crawled as"
  CRAWL ||--o{ PAGE : contains
  CRAWL ||--o{ LINK : contains
  CRAWL ||--o{ ISSUE : produces
  PAGE ||--o{ ISSUE : "affected by"
  SITE ||--o{ KEYWORD : saves
  SITE ||--o{ GSC_ROW : "search data"
  SITE ||--o{ BACKLINK : imports
  SITE ||--o{ MONITOR : schedules
  SITE ||--o{ ALERT : receives
  SITE ||--o{ CITATION : imports
  SITE ||--o{ PAGESPEED_RESULT : stores
  USER ||--o{ JOB : starts
```

| Table | Notes |
|---|---|
| `pages` | One row per crawled URL, including redirects, errors and robots-blocked URLs. Scalar SEO fields are columns; variable data (headings, images, Open Graph, JSON-LD, hreflang) is JSON in `data`; extracted body text is a deferred column. |
| `links` | Every `<a>` link with anchor, rel, internal flag and the resolved target status. |
| `issues` | `(crawl, page?, rule_id, severity, category, details)`. `page_id` is null for site-wide rules. |
| `crawls.stats` | JSON summary written by the analysis (status classes, depth distribution, issue counts, sitemap report, site checks ...). |
| `settings` | Instance-wide integration settings and per-user OAuth tokens. |

## Request security path

Every user-supplied URL goes through `api.deps.checked_url` (syntactic policy) and is fetched only via `crawler.fetcher.Fetcher`, whose
connection pool uses `security.ssrf.SafeNetworkBackend` (address policy at connect time). See `../SECURITY.md`.

## Frontend structure

- `lib/api.ts` — fetch wrapper (token, errors, downloads, uploads)
- `lib/context.tsx` — auth, selected site, theme, job polling
- `components/ui.tsx` — the UI kit all pages use (tables, pagination, cards, badges, modals, states)
- `components/Layout.tsx` — navigation shell
- `pages/*` — one file per screen, lazy-loaded

## Extending

| To add | Touch |
|---|---|
| An audit rule | `audit/rules.py` + `audit/page_checks.py` or `audit/analysis.py` + fixture/test |
| A SERP provider | `serp/analyzer.py::search` + `services/settings_store.py` defaults + Settings page |
| An AI task | `integrations/ai.py::TASKS` + context builder in `api/integrations.py::ai_run` |
| A monitor kind | `services/monitoring.py` (`KINDS`, `run_monitor`) + Monitoring page form |
| A queue backend | implement the `JobManager` interface in `jobs.py` |
