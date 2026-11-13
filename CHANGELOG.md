# Changelog

All notable changes are recorded here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project
uses [Semantic Versioning](https://semver.org/).

## [0.1.0] - Unreleased

First development release.

### Security
Result of the pre-release security review (details: `docs/SECURITY_REVIEW.md`).
- JavaScript rendering: every browser request is vetted and performed with redirects disabled; WebSockets blocked; frame URLs re-checked;
  Chromium sandbox on by default (`SEO_RENDER_SANDBOX`).
- Local Lighthouse: administrator-only, one run at a time, final URL re-checked, errors no longer echoed.
- `robots.txt` rules and crawl filters use a linear-time matcher instead of regular expressions (a hostile `robots.txt` or pattern could
  freeze the server).
- Request-body size limit enforced before bodies are read; overall deadline and minimum transfer rate per fetch; per-account job cap;
  links-per-page cap; hostile HTML parsed off the event loop.
- Search Console OAuth: `state` is single-use and bound to the signed-in account; the code is exchanged by the app with the user's token.
- Accounts: registration closed after the first account by default; atomic first-admin creation; per-account login lockout; password
  change invalidates older sessions; trusted-proxy aware rate limiting (`SEO_TRUSTED_PROXIES`); secret key file created owner-only.
- Web: Permissions-Policy, COOP/CORP, HSTS over HTTPS, `Cache-Control: no-store` on the API, narrow CSP for the API docs, only `http(s)`
  links are clickable; static-file requests are vetted before touching the filesystem (UNC path leak on Windows).
- SSRF guard: deprecated IPv6 ranges refused; startup failure instead of a silently inactive guard.
- Dependencies: Vite 6, Vitest 4, React Router 7 (8 npm advisories, 2 critical, resolved); GitHub Actions pinned by SHA; Dependabot and a
  scheduled security workflow added; Docker Compose binds to `127.0.0.1`, drops capabilities and sets `no-new-privileges`.

### Fixed
- Crawls could lose up to 40 pages from their totals when the last database batch was still being written as the crawl finished
  (found by CI as an occasional 460-of-500 failure on slower disks).
- `docker compose up -d` failed on a fresh checkout because the optional PostgreSQL service required a password even when it was not
  started. PostgreSQL is now an optional override file, `docker-compose.postgres.yml`, and CI smoke-tests both variants.

### Changed
- The product is named **OpenSEOSuite** (README, UI, licence holder, API title).
- **Crawl include/exclude patterns are no longer regular expressions.** They are plain text with `*` wildcards and optional `^` / `$`
  anchors (for example `/blog/*`, `?sort=`, `.pdf$`).
- `SEO_ALLOW_REGISTRATION` now defaults to `false` (the first account can always be created).
- Docker Compose publishes the port on `127.0.0.1` by default (`SEO_BIND=0.0.0.0` to expose it).
- `/api/auth/password` returns a fresh token; older tokens stop working.
- `/api/gsc/callback` now redirects into the app; the exchange happens at `POST /api/gsc/exchange`.

### Added (documentation)
- README banner, badges, 23 screenshots from a real instance (`scripts/capture_screenshots.py`), comparison table and security section.

### Added
- **Crawler**: asyncio crawler with RFC 9309 robots.txt handling, sitemap discovery (index, gzip, text), depth/URL limits, per-host
  throttling with crawl-delay, retries honouring Retry-After, include/exclude patterns, optional subdomains, external-link and image
  checks, optional Playwright rendering, cancellation.
- **Audit**: 95 rules across availability, redirects, links, indexability, content, URL, security, images, mobile, HTML, social,
  structured data, international and sitemap categories; page and site scores; crawl comparison.
- **Site analysis**: internal PageRank, click depth, orphan detection, exact and near-duplicate content (SimHash), canonical and
  hreflang cross-checks, sitemap consistency.
- **Modules**: internal linking (with link graph and link opportunities), sitemap manager and generator, schema validator and
  generator, PageSpeed Insights + local Lighthouse, international SEO, local SEO, keyword research (suggestions, intent, clustering,
  page mapping, cannibalisation, Keyword Planner import), SERP analysis (SearXNG, Google CSE, Brave, manual), content optimizer,
  competitor comparison, backlink import and verification, Search Console (OAuth and CSV), monitoring with alerts, optional AI layer
  (Ollama or OpenAI-compatible).
- **Reports**: PDF audit report, PDF competitor report, XLSX workbooks, CSV, JSON, generated XML sitemap.
- **Platform**: FastAPI REST API with OpenAPI docs, SQLite/PostgreSQL via SQLAlchemy and Alembic migrations, in-process job runner and
  scheduler, React/TypeScript dashboard with light and dark themes.
- **Security**: connection-level SSRF guard, Argon2id passwords, JWT auth, per-user data isolation, rate limiting, security headers,
  upload restrictions, formula-injection-safe exports.
- **Tooling**: 221 backend tests including an end-to-end audit of a deliberately flawed test website, frontend tests, CI workflow,
  Dockerfile and Compose file.
