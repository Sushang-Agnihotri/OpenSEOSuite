# Contributing

Thanks for considering a contribution. This project values accuracy and maintainability over feature count.

## Ground rules

1. **No fabricated data.** A feature must show measured data, a clearly labelled estimate with its method, imported data, or nothing.
2. **No placeholders.** Do not merge buttons that do nothing, endpoints that return canned responses, or empty modules. If something
   cannot be finished, leave it out and add it to `docs/ROADMAP.md`.
3. **Respect third-party terms.** No scraping of search-result pages; prefer official APIs; keep robots.txt compliance on by default.
4. **Licences.** Only add dependencies under MIT/BSD/Apache-2.0/ISC (or similar permissive) licences. Never copy code from GPL/AGPL or
   unlicensed projects. Record new dependencies in `docs/THIRD_PARTY_LICENSES.md`.
5. **Security.** Any code that fetches a user-supplied URL must go through `app.crawler.fetcher.Fetcher` (or `checked_url` +
   `Fetcher`) so SSRF protections apply.

## Development setup

```bash
cd backend
python -m venv .venv && source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pytest -q
ruff check app tests

cd ../frontend
npm install
npm run typecheck && npm test
npm run dev
```

## Project layout

```
backend/app/
  api/            REST routers (auth, sites, crawls, tools, integrations)
  audit/          rule catalogue, page checks, site-wide analysis, schema + hreflang validation
  crawler/        fetcher (SSRF-safe), robots, sitemaps, HTML parser, crawl engine, optional renderer
  keywords/ serp/ content/   research modules
  integrations/   PageSpeed, Search Console, AI providers
  services/       backlinks, competitors, monitoring, settings store
  reports/        CSV/XLSX/PDF builders
  security/       auth, SSRF guard, rate limiting
backend/tests/    unit, security and end-to-end tests + the flawed fixture website
frontend/src/     components/ (UI kit, layout), lib/ (API client, context), pages/
```

## Adding an audit rule

1. Add an entry to `backend/app/audit/rules.py` (id, title, severity, category, description, fix).
2. Emit it from `audit/page_checks.py` (needs one page) or `audit/analysis.py` (needs the whole crawl).
3. Add a page that triggers it to `backend/tests/fixture_site.py` and list it in `EXPECTED` in `tests/test_api.py`; add a healthy page
   to `NOT_EXPECTED` if false positives are plausible.

## Database changes

Change the models, then generate a migration and review it:

```bash
cd backend
alembic revision --autogenerate -m "describe the change"
pytest tests/test_api.py::test_migrations_are_current
```

## Pull requests

- Keep PRs focused; include tests for new behaviour and update docs (`README.md`, `KNOWN_LIMITATIONS.md`, `CHANGELOG.md`).
- CI must pass: ruff, pytest, TypeScript type-check, frontend tests and build.
- Describe how you verified the change. "It renders" is not verification.

## Reporting bugs

Open an issue with the version, steps to reproduce, expected and actual behaviour. For crawler issues include the crawl settings and,
if possible, a public URL that reproduces the problem. For security issues follow `SECURITY.md`.
