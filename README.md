# Ultimate Open-Source SEO Toolkit

A self-hosted SEO platform you can run for free: site crawler, technical audit, internal-link analysis, keyword research, SERP and
content analysis, Search Console reporting, page speed, monitoring and exportable reports — in one application, on your own machine.

> **Status: 0.1.0 (first development release).** The crawler, audit engine, exports, monitoring and API are covered by automated tests.
> Some integrations could not be verified against live third-party services yet. `PROJECT_STATUS.md` lists precisely what is verified
> and `KNOWN_LIMITATIONS.md` what the tool cannot do.

## Why another SEO tool?

Research across 460+ GitHub repositories (see `RESEARCH/`) showed that most "open-source Ahrefs/Semrush alternatives" are front-ends
for a paid data API, while the genuinely free tools are single-purpose crawlers. This project aims at the gap in between:

- **Everything in the core works without paid APIs or accounts.** Optional integrations use free tiers or your own keys.
- **No invented numbers.** Every figure is labelled *measured*, *estimated*, *imported* or *unavailable*. Search volumes and backlink
  totals are never guessed.
- **Honest scope.** It does not contain Ahrefs' backlink index or Semrush's keyword database, and says so.

## Features

| Module | What it does |
|---|---|
| **Crawler** | Async crawler with robots.txt (RFC 9309), sitemap discovery, depth/URL limits, per-host rate limiting, retries, include/exclude patterns, subdomain option, external-link and image checks, optional JavaScript rendering (Playwright) |
| **Site audit** | 95 rules in 4 severities with explanations and fixes: status codes, redirect chains/loops, broken links and images, indexability, canonicals, titles/descriptions/headings, duplicate and near-duplicate content, thin content, URL structure, HTTPS/mixed content, hreflang, structured data, Open Graph/Twitter, viewport, sitemap consistency; transparent 0-100 score; crawl-to-crawl comparison |
| **Internal linking** | Internal PageRank, click depth, orphan pages, anchor-text analysis, topic-based link opportunities, interactive link graph |
| **Sitemaps & indexing** | Sitemap validation, non-indexable URLs in sitemaps, missing pages, canonical mismatches, sitemap generation |
| **Schema markup** | JSON-LD validation for 25 types, site-wide report, validator for any URL or snippet, template generator for 12 types |
| **Page speed** | PageSpeed Insights API (Lighthouse + real-user Core Web Vitals) and optional local Lighthouse; recommendations grouped by topic; history |
| **International / Local SEO** | hreflang validation and reciprocity, language targeting; LocalBusiness markup, NAP consistency, citation imports |
| **Keyword research** | Suggestions from Google/Bing/DuckDuckGo autocomplete, question and long-tail discovery, intent classification, clustering, keyword-to-page mapping, cannibalisation detection, Keyword Planner import |
| **SERP analysis** | Via SearXNG, Google Programmable Search API, Brave Search API or pasted URLs: ranking-page structure, common topics, questions, content gaps, difficulty estimate |
| **Content optimizer** | Editor with on-page checks, readability, term and topic coverage against competing pages, FAQ/schema/internal-link suggestions |
| **Competitors** | Crawl competitor sites and compare measured on-site metrics, topical overlap and gaps |
| **Backlinks** | Import link datasets (Search Console exports, any CSV), verify links live, referring domains, anchors, broken link targets |
| **Search Console** | OAuth integration or CSV import: clicks, impressions, CTR, position by query/page/country/device, declining queries, opportunities, cannibalisation |
| **Monitoring** | Scheduled uptime checks, recurring audits, sitemap/metadata/competitor change detection, keyword position alerts, alert feed |
| **Reports** | PDF audit report, PDF competitor report, Excel workbooks, CSV, JSON |
| **AI (optional)** | Explain issues, prioritise fixes, titles/descriptions, briefs, action plans — through a local Ollama model or your own OpenAI-compatible API; always fed real data from your crawl |

## Screenshots

Screenshots live in `docs/screenshots/`. They are captured from a real instance auditing the bundled test website
(`backend/tests/fixture_site.py`), never from mock data. See that folder's README for how to regenerate them.

## Architecture

```mermaid
flowchart LR
  subgraph Browser
    UI[React + TypeScript SPA]
  end
  subgraph "API process (FastAPI, one worker)"
    API[REST API /api]
    JOBS[Job runner + scheduler]
    CRAWL[Crawler\nhttpx + lxml\noptional Playwright]
    AUDIT[Audit engine\n95 rules]
    MODS[Keywords · SERP · Content\nBacklinks · Competitors · Reports]
  end
  DB[(SQLite or PostgreSQL)]
  WEB((Websites))
  EXT[[Optional services:\nPageSpeed Insights · Search Console\nSearXNG / Google CSE / Brave · Ollama]]
  UI -- JWT --> API
  API --> JOBS --> CRAWL --> AUDIT --> DB
  API --> MODS --> DB
  CRAWL -- SSRF-guarded fetches --> WEB
  MODS -.-> EXT
```

More detail: `docs/ARCHITECTURE.md` and `ARCHITECTURE_DECISIONS.md`.

## Installation

### Option A: Docker

```bash
git clone <your fork or this repository> ultimate-open-source-seo-toolkit
cd ultimate-open-source-seo-toolkit
docker compose up -d
```

Open http://localhost:8000 and create the first account (it becomes the administrator). Data is kept in the `seo-data` volume.

### Option B: Manual (Windows, macOS, Linux)

Requirements: Python 3.11+ and Node.js 20+.

```bash
# 1. Backend
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate      macOS/Linux: source .venv/bin/activate
pip install -e .

# 2. Frontend (build once; the backend serves it)
cd ../frontend
npm install
npm run build

# 3. Run
cd ../backend
uvicorn app.main:app --port 8000
```

Open http://localhost:8000. The database is created and migrated automatically in `backend/data/`.

Optional extras:

```bash
pip install -e ".[render]" && playwright install chromium   # JavaScript rendering
pip install -e ".[postgres]"                                # PostgreSQL driver
npm install -g lighthouse                                   # local Lighthouse audits
```

### Development mode

```bash
cd backend && uvicorn app.main:app --reload --port 8000    # API
cd frontend && npm run dev                                  # UI on http://localhost:5173 (proxies /api)
```

## Usage

1. **Websites → Add website.** Enter a name and URL.
2. **Crawler → Start crawl.** Defaults: 500 URLs, 5 concurrent requests, 200 ms delay, robots.txt respected.
3. **Site Audit** shows the score and prioritised issues; click an issue for affected URLs and the fix. Download the PDF or Excel report.
4. Explore **Internal Linking**, **Sitemaps**, **Schema**, **International**, **Local**.
5. **Keyword Research** → collect suggestions, save them to the site, then check **Page mapping & cannibalisation**.
6. **Search Console** → connect with OAuth or import a CSV export to see measured clicks, impressions and positions.
7. **Monitoring** → schedule uptime checks and recurring audits; alerts appear under the bell icon.

To try the tool on a site full of known problems, run the bundled test website and audit it:

```bash
cd backend
python -m tests.fixture_site 8765                                   # terminal 1
SEO_ALLOW_PRIVATE_NETWORKS=true uvicorn app.main:app --port 8000    # terminal 2 (PowerShell: $env:SEO_ALLOW_PRIVATE_NETWORKS="true")
# then add http://127.0.0.1:8765/ as a website
```

## Configuration

All settings are optional environment variables (prefix `SEO_`), documented in `.env.example`. The important ones:

| Variable | Default | Purpose |
|---|---|---|
| `SEO_DATA_DIR` | `./data` | SQLite database and generated secret key |
| `SEO_DATABASE_URL` | SQLite | Set to a PostgreSQL URL to switch database |
| `SEO_SECRET_KEY` | generated | Token signing key |
| `SEO_ALLOW_REGISTRATION` | `true` | Close sign-ups after creating your accounts |
| `SEO_ALLOW_PRIVATE_NETWORKS` | `false` | Allow crawling localhost/LAN (disables that part of SSRF protection) |
| `SEO_PUBLIC_BASE_URL` | `http://localhost:8000` | Used for the Google OAuth redirect URI |

Integration keys (PageSpeed, SERP provider, AI provider, Google OAuth client) are entered under **Settings** in the app.

### Outbound connections

The application contacts only:

| When | Host |
|---|---|
| Crawling, link checks, monitors, SERP page analysis | The sites you ask it to fetch |
| Keyword suggestions | `suggestqueries.google.com`, `api.bing.com`, `duckduckgo.com` |
| Page speed (if used) | `www.googleapis.com` (PageSpeed Insights) |
| Search Console (if connected) | `accounts.google.com`, `oauth2.googleapis.com`, `www.googleapis.com` |
| SERP provider (if configured) | Your SearXNG instance, `www.googleapis.com`, or `api.search.brave.com` |
| AI (if configured) | Your Ollama instance or the API base URL you set |

There is no telemetry.

## API documentation

Interactive OpenAPI docs are served at `/api/docs` (Swagger UI) and `/api/redoc`; the schema is at `/api/openapi.json`.
`docs/API.md` gives an overview and a scripted example. Authenticate with `POST /api/auth/login` and send
`Authorization: Bearer <token>`.

## Testing

```bash
cd backend && pip install -e ".[dev]" && pytest -q     # 167 tests: units, security, end-to-end crawl of a flawed test site
cd frontend && npm test && npm run typecheck
```

The backend suite starts a local website containing ~50 planted SEO problems and asserts that each is detected (and that healthy pages
are not flagged).

## Roadmap

See `docs/ROADMAP.md`. Near-term: notifications (e-mail/webhook), log-file analysis, Bing
Webmaster Tools, batch page-speed testing, encrypted secrets.

## Contributing

Contributions are welcome — see `CONTRIBUTING.md`. Adding an audit rule is a good first change (one catalogue entry, one check, one test).

## Limitations

Summarised in `KNOWN_LIMITATIONS.md`. The short version: no web-scale backlink index, no search-volume database, no competitor
traffic data, rank tracking only through Search Console. These require proprietary datasets no free tool can honestly provide.

## License

MIT — see `LICENSE`. Third-party licences: `docs/THIRD_PARTY_LICENSES.md`.
