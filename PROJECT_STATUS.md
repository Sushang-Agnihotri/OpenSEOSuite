# Project Status

Last updated: 2026-11-13 · Version 0.1.0 (pre-release, not yet published)

This file separates what has been **verified** from what is **implemented but unverified** and what is **not done**. Keep it honest.

## Development phases

| Phase | Scope | State |
|---|---|---|
| A | GitHub research and competitor analysis | Done: `RESEARCH/` (463 repositories surveyed, 68 analysed) |
| B | Architecture and technical design | Done: `ARCHITECTURE_DECISIONS.md`, `docs/ARCHITECTURE.md` |
| C | Backend foundation and database | Done, tested |
| D | Frontend foundation and dashboard | Done; verified in a browser, limited automated tests |
| E | Technical SEO auditing | Done, tested (95 rules) |
| F | Website crawler | Done, tested |
| G | Keyword research and SERP analysis | Done; SERP providers unverified against live services |
| H | Competitor and backlink analysis | Done, tested |
| I | Content optimisation and AI | Done; AI providers unverified against a live model |
| J | Search Console and PageSpeed integrations | Implemented; live calls unverified (see below) |
| K | Monitoring and reporting | Done, tested |
| L | Security, testing, optimisation, release | Security review done and findings fixed (`docs/SECURITY_REVIEW.md`); Docker image and both Compose variants verified in CI; public on GitHub |

## Verification record

### Verified by automated tests (221 backend tests, 18 frontend tests, all passing on Windows 11 / Python 3.11 / Node 20)

- Crawl of a local website with ~50 planted problems: each expected rule fires on the expected URL, and healthy pages are not flagged.
- Redirect chains/loops, broken internal/external links, broken and oversized images, duplicates and near-duplicates, canonicals,
  hreflang, structured data, sitemap and robots.txt checks, orphan/deep pages, URL hygiene, viewport/doctype/lang.
- Crawl limits (URL cap, depth), cancellation, deletion, one-crawl-per-site rule, crawl comparison.
- Performance: 500 pages crawled and analysed in about 10 s (~49 pages/s) against a local server.
- JavaScript rendering with Playwright/Chromium (content and links created by scripts are found).
- Exports: CSV, XLSX (multi-sheet), JSON, PDF audit report, PDF competitor report, generated sitemap; formula-injection escaping.
- Keywords (save, cluster, Keyword Planner import incl. UTF-16, page mapping, cannibalisation), content optimizer, schema validator and
  generator, SERP analysis in manual-URL mode, backlink import + live verification, competitor crawl + comparison.
- Search Console **CSV import**, performance report and insights (declines, new queries, opportunities, cannibalisation).
- Monitors (uptime, metadata change, sitemap change, scheduled audit) and alerts.
- Security (pre-release review, `docs/SECURITY_REVIEW.md`): linear-time matching under hostile `robots.txt`/patterns, body-size and deadline
  limits, OAuth state binding, password-change session invalidation, job caps, safe links, headers, browser-renderer redirect refusal.
- Security: SSRF policy (24 hostile URL forms), connect-time address checks incl. simulated DNS rebinding, redirect following,
  response-size limits, Argon2id hashing, every endpoint rejects unauthenticated calls, cross-user isolation, admin-only settings,
  secret masking, injection payloads, upload type/size limits, login rate limiting, security headers.
- Database migrations match the models; lint clean (ruff, incl. security rules); TypeScript strict type-check; production build.

### Verified by CI (GitHub Actions run #1, commit 1f6e9fa, all jobs green)

- Backend lint + test suite on Ubuntu (Python 3.11 and 3.12), Windows (3.11) and macOS (3.12). The JavaScript-rendering test is
  skipped there because Chromium is not installed in CI.
- Frontend type-check, tests and production build on Ubuntu.
- `docker build` of the image, then a container started from it answers `/api/health`.
- `docker compose up -d` from a fresh checkout with no `.env` file (the README quick start), and the PostgreSQL variant (`docker-compose.postgres.yml`) including a registration written through the API into PostgreSQL 16 — this is the only PostgreSQL verification so far.

### Verified manually

- Application started from a clean data directory; first account created; site added; crawl run; all 21 screens opened in a browser
  against real crawl data with no runtime or console errors.
- Keyword suggestions against the live Google, Bing and DuckDuckGo autocomplete endpoints (103 suggestions for one seed, no errors).

### Implemented but NOT verified against the live third-party service

| Feature | Why unverified | Risk |
|---|---|---|
| PageSpeed Insights API call | The anonymous shared quota was exhausted (HTTP 429, handled with a clear message). Result parsing is unit-tested with a synthetic Lighthouse report. | Field names in real responses may differ in details |
| Local Lighthouse run | Lighthouse CLI not installed on the development machine | Subprocess invocation untested |
| Search Console OAuth, property list, API sync | No Google Cloud OAuth client available | Token exchange / API response handling untested |
| SERP providers (SearXNG, Google Programmable Search, Brave) | No instance or API keys available | Response mapping untested; manual-URL mode is tested |
| AI providers (Ollama, OpenAI-compatible) | No model server available | Prompt construction is tested; HTTP calls are not |
| PostgreSQL beyond a smoke test | CI proves the migrations apply and a user can be written through the API on PostgreSQL 16 in a container. The full test suite and crawls were only run on SQLite | Dialect differences in less common queries |
| Docker on Windows/macOS and long-running use | CI runs on Linux only. A crawl, the data volume across restarts and the UI inside the container were not exercised | Volume permissions or crawl behaviour inside the container could still surprise |
| Frontend interactions | Screens were loaded and checked for errors; forms/buttons on most screens were not clicked through one by one. The Search Console return flow was checked in the browser only with an invalid state | UI bugs in less common flows are likely |
| Dropped capabilities and `no-new-privileges` | Applied in `docker-compose.yml` and covered by the Compose smoke test (the app starts and answers health and registration) | Anything that needs a capability at runtime would only show up in less common flows |
| External penetration test | Not done; the review was code reading, scanners and regression tests | Unknown issues may remain |

### Not implemented

See `KNOWN_LIMITATIONS.md` ("Not implemented") and `docs/ROADMAP.md`: log-file analysis, Bing Webmaster Tools, Google Analytics,
Google Trends, Google Business Profile, notifications by e-mail/webhook, URL Inspection, batch page-speed runs.

## Release acceptance criteria

| # | Criterion | Status |
|---|---|---|
| 1 | Application installs successfully | **Verified** on Windows (venv + npm); test suite also passes on Linux and macOS in CI |
| 2 | Backend runs | **Verified** |
| 3 | Frontend runs | **Verified** (production build served by the backend) |
| 4 | Database migrations work | **Verified** (SQLite) |
| 5 | Users can add websites | **Verified** |
| 6 | Website crawling works | **Verified** (local test sites; not yet run against large public sites) |
| 7 | Technical audits produce real results | **Verified** |
| 8 | Issues are correctly categorised | **Verified** by tests |
| 9 | Reports can be exported | **Verified** |
| 10 | Core modules have automated tests | **Verified** |
| 11 | Security checks completed | **Verified** by review, scanners and tests (`docs/SECURITY_REVIEW.md`); no external penetration test |
| 12 | Documentation complete | **Yes**: README with 23 real screenshots, security review, architecture, API and limitations documents |
| 13 | Docker deployment works | **Verified in CI (Linux)**: image build, `docker compose up` with SQLite and with PostgreSQL; not run on Docker Desktop |
| 14 | No critical errors remain | None known; UI flows only partly exercised |
| 15 | Works without paid API subscriptions | **Verified** |

**Conclusion: not ready for a public release yet.** Criterion 13 is only partly verified, and the unverified integrations above should be
exercised (or clearly marked experimental in the UI) first.

## Next steps

1. Try the image on Docker Desktop (Windows/macOS) and run a crawl inside the container.
2. Click through every form in the UI; add frontend tests for the main flows.
3. Verify PageSpeed (with a free API key), Search Console OAuth, one SERP provider and Ollama.
4. Crawl a few real public sites of different sizes; tune defaults.
5. Add repository topics, a description and the social preview image on GitHub, then announce it.
