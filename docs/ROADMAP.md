# Roadmap

Ordered by expected value to users. Items move to `CHANGELOG.md` when shipped. See `../PROJECT_STATUS.md` for what is verified today.

## Next (0.2)

- Run the JavaScript-rendering test in CI (install Chromium there) and add a test for local Lighthouse.
- Verify the Search Console OAuth flow end to end with a real Google Cloud project; add URL Inspection (index status per URL).
- Notifications for alerts: e-mail (SMTP) and generic webhook (Slack/Discord compatible).
- Batch page-speed testing for the top pages of a crawl, with site-level Core Web Vitals summary.
- Encrypt stored integration secrets with a master key.
- SERP-overlap keyword clustering exposed in the UI (the function exists in `keywords/research.py`).
- Screenshots and a short demo recording in the README.

## Later

- Log-file analysis (crawl budget, bot hits per URL, status codes seen by Googlebot).
- Bing Webmaster Tools and Google Analytics 4 integrations.
- Image audit by downloading headers of all images (dimensions, format, compression potential).
- Soft-404 detection, pagination-sequence checks, `srcset`/CSS-background link extraction, AMP checks.
- Rendering-based mobile checks (tap targets, font sizes) through Playwright.
- Language-aware readability (formulas for German, Spanish, French ...) and multilingual stop words.
- Embedding-based topic clustering through the optional local AI provider.
- Teams/workspaces with shared sites and roles; API tokens for automation; audit log.
- Queue backend option (Redis/RQ or Dramatiq) and multi-process crawling for very large sites.
- White-label PDF reports (logo, colours), scheduled report delivery.
- Plugin interface for custom audit rules.

## Research

- An open backlink dataset derived from Common Crawl's published web-graph files (host-level first). This needs significant storage and
  batch processing and would ship as a separate optional importer rather than inside the app.
- Google Trends without an official API: revisit if a permitted access route appears.

## Out of scope

- Scraping Google/Bing result pages, proxy rotation, captcha solving.
- Estimating search volumes or traffic without a data source.
- Link-building automation.
