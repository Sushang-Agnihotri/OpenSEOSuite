# Architecture Decisions

Short records of the decisions that shape the codebase. Add a new record when you change one.

## ADR-001: Python/FastAPI backend, React/TypeScript frontend
**Decision.** FastAPI + SQLAlchemy 2 + Alembic on the server; React 18 + TypeScript + Vite + Tailwind + Recharts in the browser. In
production the API process also serves the built frontend, so there is one process and one port.
**Why.** The SEO/data ecosystem (lxml, trafilatura, Playwright, openpyxl, reportlab) is strongest in Python; asyncio suits I/O-bound
crawling; FastAPI gives validation and OpenAPI docs for free.

## ADR-002: SQLite by default, PostgreSQL optional
**Decision.** The default database is a SQLite file in `SEO_DATA_DIR` (WAL mode). Setting `SEO_DATABASE_URL` to a PostgreSQL URL switches
engines; models avoid engine-specific SQL (one bound-parameter `text()` update is portable).
**Why.** Research showed installation friction is the main reason open-source SEO tools are abandoned. SQLite handles crawls of tens of
thousands of URLs on a laptop. PostgreSQL remains available for bigger or multi-user installations.
**Trade-off.** SQLite allows one writer at a time; concurrent crawls queue their writes (30 s busy timeout).

## ADR-003: In-process background jobs instead of Celery + Redis
**Decision.** Long work (crawls, link verification, monitors, Search Console sync) runs as asyncio tasks inside the API process, with state
in the `jobs` table. A semaphore limits concurrent jobs (`SEO_MAX_CONCURRENT_JOBS`).
**Why.** Celery is not supported on Windows, and a mandatory Redis broker contradicts "easy installation, runs locally". Crawling is
I/O-bound, so one event loop is enough; CPU-heavy steps (HTML parsing, post-crawl analysis) run in worker threads.
**Trade-off.** Jobs do not survive a restart (they are marked failed on startup and can be re-run) and the API must run as a single
process. A queue backend can be added behind `app/jobs.py` without touching callers.

## ADR-004: Own crawler on httpx rather than embedding Scrapy
**Decision.** A purpose-built asyncio crawler (`app/crawler`) using httpx, lxml and an optional Playwright renderer.
**Why.** Scrapy's Twisted reactor does not share a process cleanly with FastAPI/asyncio. An SEO crawler also needs things a scraping
framework does not model: every URL as a row (including redirects, blocked and failed URLs), link graph capture, and SSRF controls on
every connection.

## ADR-005: SSRF protection at connection time
**Decision.** Besides syntactic URL validation, the HTTP connection pool uses a custom network backend that resolves the hostname,
rejects the connection if any address is non-public, and connects to the vetted IP. Redirects are followed manually so every hop passes
the same gate. Environment proxies are ignored. `SEO_ALLOW_PRIVATE_NETWORKS=true` relaxes this for auditing localhost/LAN sites.
**Why.** Validate-then-fetch is vulnerable to DNS rebinding; checking the address actually connected to is not.
**Trade-off.** Relies on httpx/httpcore internals (`transport._pool._network_backend`), so the httpx version is pinned to a tested range.

## ADR-006: Redirects are rows, not transparently followed
**Decision.** During a crawl a 3xx response is stored as its own page with `redirect_to`; the target is queued separately. Chains and
loops are derived afterwards by walking those pointers.
**Why.** It mirrors how SEO crawlers present data, makes "links pointing to redirects" trivial to compute and avoids re-fetching chains.

## ADR-007: Two-phase audit
**Decision.** Page-local checks run while crawling (`audit/page_checks.py`); checks that need the whole site (duplicates, link graph,
canonical targets, hreflang reciprocity, sitemap consistency) run once at the end (`audit/analysis.py`).
**Why.** Keeps memory flat during the crawl and lets the analysis be re-run without re-crawling.

## ADR-008: Rules as data
**Decision.** Every audit rule is one entry in `audit/rules.py` with id, severity, category, explanation and fix. Checks only emit
`(rule_id, details)`.
**Why.** Severity changes, documentation, reports, the UI and the AI explanations all read the same catalogue.

## ADR-009: Transparent scoring
**Decision.** Page score = 100 minus 25/10/4/1 per critical/high/medium/low rule firing on the page (floor 0). Site score = mean page
score minus 10/5/2/0.5 per site-wide rule. The formula is shown in the UI and the PDF.
**Why.** A score nobody can reproduce is not actionable. This one can be verified by hand.

## ADR-010: Never fabricate metrics
**Decision.** Each figure is tagged measured, estimated, imported or unavailable in the API and UI. Search volume, CPC and backlink totals
are never synthesised. Estimates (intent, difficulty, opportunity) carry their method.
**Why.** The brief requires it, and invented numbers are the main trust problem of free SEO tools.

## ADR-011: SERP data only through permitted providers
**Decision.** SERP analysis uses a provider interface: self-hosted SearXNG, Google Programmable Search JSON API, Brave Search API, or
URLs pasted by the user. No direct scraping of Google/Bing result pages.
**Why.** Scraping result pages violates the engines' terms and breaks constantly (captcha, markup changes).

## ADR-012: JWT bearer tokens in the Authorization header
**Decision.** Stateless HS256 JWTs sent as `Authorization: Bearer`, stored by the SPA in localStorage; passwords hashed with Argon2id.
**Why.** No cookies means no CSRF surface. The trade-off (token readable by injected script) is mitigated with a strict
Content-Security-Policy, no third-party scripts and React's output escaping.

## ADR-013: Secrets entered in the UI live in the database
**Decision.** Integration credentials (PSI key, SERP keys, OAuth client secret, tokens) are stored in the `settings` table, write-only
through the API (reads return a mask).
**Why.** Non-technical users can configure integrations without editing files. They are not encrypted at rest; protecting the database
file is documented in SECURITY.md. Encryption with a master key is on the roadmap.

## ADR-014: Dependency-light text analysis
**Decision.** Readability, stemming, TF-IDF-style term ranking, SimHash and clustering are implemented in plain Python (`app/text.py`,
`crawler/parser.py`, `keywords/research.py`) instead of pulling in scikit-learn/NLTK/spaCy.
**Why.** Hundreds of megabytes of ML wheels for a few formulas would slow installation; the algorithms are small and testable.
**Trade-off.** Lexical methods only (no embeddings); readability formulas are calibrated for English.

## ADR-015: MIT licence
**Decision.** MIT. All code is original; dependencies are MIT/BSD/Apache-2.0/ISC. GPL/AGPL projects were studied for ideas only, and
SearXNG (AGPL) is only ever contacted over HTTP as a separate service.
