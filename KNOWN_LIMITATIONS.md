# Known Limitations

Read this before relying on the platform for decisions. Nothing here is hidden behind a paid tier; these are limits of free data and of
the current implementation.

## Data that does not exist for free

- **No web-scale backlink index.** Backlink features analyse datasets you import (Search Console link exports, exports from other tools,
  any CSV) and verify them live. Links nobody gave the tool are invisible to it. There is no Domain Rating/Authority equivalent.
- **No search-volume database.** Volumes appear only when you import a Google Ads Keyword Planner file. Search Console impressions are
  shown as the measured alternative for queries your site already appears for.
- **No competitor traffic or ranking-keyword data.** Competitor analysis is limited to what crawling their public site reveals.
- **Rank tracking** is limited to Search Console's average position for your own verified site. There is no per-location, per-device
  daily tracking of arbitrary keywords.
- **Indexed-page counts** cannot be verified without Search Console; sitemap size and indexable crawled pages are shown instead.
- **Google Trends** is not integrated (no official API). **Bing Webmaster Tools** and **Google Analytics** integrations are not
  implemented yet. **Google Business Profile** needs API access that Google grants per project and is not implemented.
- **Google Ads Keyword Planner** has no direct API integration; use its CSV export.

## Estimates (always labelled in the UI)

- **Search intent** is a rule-based keyword classifier.
- **Keyword difficulty** is a heuristic from SERP composition. It does not use links and is not comparable with commercial KD scores.
- **Opportunity / extra clicks** multiplies Search Console impressions by a generic CTR-by-position curve.
- **Content score** reflects on-page best practice and comparison with pages you supply; it does not predict rankings.
- **Keyword-to-page mapping** and crawl-based cannibalisation use lexical relevance, not search-engine behaviour.

## Crawler

- **JavaScript rendering** requires installing Playwright and Chromium separately (about 150 MB). It is covered by three automated tests
  (skipped when Chromium is absent) and is much slower than plain fetching. Each browser request is vetted and redirects are refused
  (a rendered page that redirects is not rendered), but DNS is resolved again by the browser stack after our address check, so
  rebinding protection is weaker than for plain HTTP fetching. If the Chromium sandbox cannot start (some containers), set
  `SEO_RENDER_SANDBOX=false`, accepting the added risk.
- **Include/exclude patterns** are plain text with `*`, `^` and `$` (not regular expressions): regular expressions from untrusted input
  can freeze a single-process server.
- **Local Lighthouse** (optional) is administrator-only and runs one audit at a time. Chrome follows redirects itself, so a run can
  *request* an internal address even though the result is then discarded.
- One crawl runs in one process. Around 50 pages/second was measured against a local test site; real sites are bounded by politeness
  delays. Crawls of hundreds of thousands of URLs are possible in principle but untested; memory grows with the link graph.
- Jobs are in-process: a server restart aborts running crawls (they are marked failed and can be restarted).
- Only `<a href>` links and `<img>` sources are followed/checked. Links created by JavaScript events, CSS backgrounds, `srcset`
  candidates and resources inside iframes are not.
- Soft-404 detection, AMP validation and pagination sequence checks (`rel=next/prev` chains) are not implemented.
- External link checks treat 401/403/405/429/999 as "unverifiable", because many sites block automated requests.
- "Mobile friendliness" is assessed from the viewport tag only; there is no rendering-based tap-target or font-size analysis.
  "HTML validation" covers doctype, duplicate `<head>/<body>`, duplicate IDs and charset, not full W3C conformance.
- Response time is time-to-first-byte from the machine running the crawl, not a user-centric metric.

## Structured data

- Validation covers JSON-LD for 25 common types with required/recommended property tables based on Google's public documentation. It is
  not a full schema.org validator, does not validate value formats (dates, URLs, enumerations) and reports Microdata/RDFa types without
  validating them.

## Content and language

- Readability formulas (Flesch) and the stemmer are calibrated for English. Other languages get tokenised correctly but scores are less
  meaningful. Stop-word removal is English-only.
- Term suggestions are lexical (TF-IDF-style over competitor pages); there are no embeddings or entity extraction.

## SERP analysis

- Needs a provider (self-hosted SearXNG, Google Programmable Search API key, Brave Search API key) or pasted URLs. Provider ordering can
  differ from a live Google result page, and SERP features are limited to what the provider's API reports.

## Search Console

- The OAuth flow needs your own Google Cloud OAuth client. The integration is implemented against the documented API and its parsing and
  reporting logic is tested with imported data, but the live OAuth round-trip was **not verified end to end** during development (no
  Google credentials were available). CSV import is fully tested.
- URL Inspection (per-URL index status) is not implemented.

## Page speed

- PageSpeed Insights tests public URLs only. Without an API key the anonymous quota is small. Field data exists only for pages/origins
  with enough Chrome traffic. Local Lighthouse needs Node.js, the `lighthouse` CLI and Chrome, and was not exercised by automated tests.

## Monitoring

- The scheduler runs inside the API process; monitors do not run while the app is stopped. Alerts appear in the app only (no e-mail,
  Slack or webhook delivery yet).

## Security and multi-user use

- Integration secrets are stored unencrypted in the application database.
- Rate limiting is in-memory and per process, intended for a single-instance deployment.
- Access control is per user (each user sees only their own sites). There are no teams, roles beyond admin, or shared workspaces.
- Access tokens cannot be revoked individually before expiry (change `SEO_SECRET_KEY` to invalidate all).

## Not implemented (roadmap)

Log-file analysis · Bing Webmaster Tools · Google Analytics · Google Trends · e-mail/webhook notifications · batch page-speed testing
across a crawl · URL Inspection API · SERP-overlap clustering in the UI (function exists) · encrypted secrets · distributed crawling.
