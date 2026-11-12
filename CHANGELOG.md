# Changelog

All notable changes are recorded here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project
uses [Semantic Versioning](https://semver.org/).

## [0.1.0] - Unreleased

First development release.

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
- **Tooling**: 167 backend tests including an end-to-end audit of a deliberately flawed test website, frontend tests, CI workflow,
  Dockerfile and Compose file.
