# GitHub Repository Analysis

Data collected on 2026-11-12 from the public GitHub REST API (unauthenticated).

## Method

1. 43 search queries (topics such as `seo`, `seo-audit`, `technical-seo` and phrase searches for every module area: crawling, keyword research, SERP, backlinks, sitemaps, robots.txt, structured data, Lighthouse/Core Web Vitals, Search Console, hreflang, local SEO, content optimisation, readability, monitoring, Common Crawl) returned **463 distinct repositories** with more than 40 stars.
2. 17 well-known infrastructure projects that keyword search does not surface (Scrapy, Crawlee, trafilatura, SearXNG, Uptime Kuma, Ollama ...) were added by name.
3. 68 repositories were shortlisted for relevance by reading descriptions and topics; unrelated hits (Next.js boilerplates, Ethereum's 'Lighthouse', prompt/skill packs with no code to learn from, etc.) were discarded regardless of star count.
4. For the closest comparable products the README and docs were read (open-seo, seonaut, LibreCrawl, crawlseo, rankme.fast, bisibility); the remaining notes combine repository documentation with prior knowledge of these projects. Source code was **not** copied from any repository.

### What the numbers mean

- Stars, forks, open issues, licence, language and last push come straight from the API on the collection date and will drift.
- Contributor counts were fetched only for the 25 most relevant repositories (API rate limit); others show `n/c` (not collected).
- GitHub **traffic** (visitors, page views) is visible only to repository administrators. It was not accessible and is therefore not reported.
- 'Maintained' = pushed within the last 12 months and not archived.

## Shortlisted repositories

| # | Repository | Category | Stars | Forks | Open issues | Contributors | Licence | Language | Last push | Maintained |
|---|---|---|---:|---:|---:|---:|---|---|---|---|
| 1 | [every-app/open-seo](https://github.com/every-app/open-seo) | SEO platform | 27,396 | 3,823 | 113 | 21 | MIT | TypeScript | 2026-11-11 | Yes |
| 2 | [crawlseo/crawlseo](https://github.com/crawlseo/crawlseo) | SEO platform | 693 | 102 | 4 | 11 | MIT | TypeScript | 2026-11-02 | Yes |
| 3 | [SelmiAbderrahim/rankme.fast](https://github.com/SelmiAbderrahim/rankme.fast) | SEO platform | 922 | 33 | 13 | 1 | AGPL-3.0 | TypeScript | 2026-10-28 | Yes |
| 4 | [CorgiCorner/bisibility](https://github.com/CorgiCorner/bisibility) | SEO platform | 602 | 36 | 2 | 1 | AGPL-3.0 | TypeScript | 2026-11-10 | Yes |
| 5 | [towfiqi/serpbear](https://github.com/towfiqi/serpbear) | Rank tracking | 2,179 | 317 | 79 | 18 | MIT | TypeScript | 2026-10-30 | Yes |
| 6 | [serphacker/serposcope](https://github.com/serphacker/serposcope) | Rank tracking | 753 | 206 | 67 | n/c | MIT | JavaScript | 2024-01-22 | No (archived) |
| 7 | [AgriciDaniel/keywordpro](https://github.com/AgriciDaniel/keywordpro) | Keyword research | 297 | 81 | 7 | n/c | Apache-2.0 | TypeScript | 2026-11-06 | Yes |
| 8 | [iannuttall/seo](https://github.com/iannuttall/seo) | SEO platform | 622 | 52 | 0 | n/c | Apache-2.0 | TypeScript | 2026-11-11 | Yes |
| 9 | [StJudeWasHere/seonaut](https://github.com/StJudeWasHere/seonaut) | Technical audit | 868 | 146 | 14 | 9 | MIT | Go | 2026-10-08 | Yes |
| 10 | [PhialsBasement/LibreCrawl](https://github.com/PhialsBasement/LibreCrawl) | Crawler | 1,109 | 231 | 37 | 11 | MIT | Python | 2026-11-10 | Yes |
| 11 | [janreges/siteone-crawler](https://github.com/janreges/siteone-crawler) | Crawler | 1,001 | 95 | 17 | 7 | MIT | Rust | 2026-09-27 | Yes |
| 12 | [sethblack/python-seo-analyzer](https://github.com/sethblack/python-seo-analyzer) | Technical audit | 1,494 | 351 | 22 | 29 | NOASSERTION | Python | 2026-11-07 | Yes |
| 13 | [viasite/site-audit-seo](https://github.com/viasite/site-audit-seo) | Technical audit | 307 | 47 | 11 | 5 | NOASSERTION | JavaScript | 2026-10-27 | Yes |
| 14 | [nazuke/SEOMacroscope](https://github.com/nazuke/SEOMacroscope) | Crawler | 267 | 44 | 15 | 2 | GPL-3.0 | C# | 2024-03-31 | No |
| 15 | [squirrelscan/squirrelscan](https://github.com/squirrelscan/squirrelscan) | Technical audit | 311 | 38 | 81 | 10 | MIT | TypeScript | 2026-11-12 | Yes |
| 16 | [seo-skills/seo-audit-skill](https://github.com/seo-skills/seo-audit-skill) | Technical audit | 668 | 84 | 0 | n/c | MIT | TypeScript | 2026-10-15 | Yes |
| 17 | [kemalai/FreeCrawl-SEO-Tool](https://github.com/kemalai/FreeCrawl-SEO-Tool) | Crawler | 157 | 24 | 0 | n/c | MIT | TypeScript | 2026-11-07 | Yes |
| 18 | [beb7/gflare-tk](https://github.com/beb7/gflare-tk) | Crawler | 198 | 21 | 20 | n/c | GPL-3.0 | Python | 2023-07-07 | No |
| 19 | [StanGirard/seo-audits-toolkit](https://github.com/StanGirard/seo-audits-toolkit) | Technical audit | 830 | 156 | 41 | n/c | none | Python | 2023-02-06 | No |
| 20 | [eliasdabbas/advertools](https://github.com/eliasdabbas/advertools) | SEO data toolkit | 1,505 | 268 | 6 | 15 | MIT | Python | 2026-06-30 | Yes |
| 21 | [backstagephp/laravel-seo-scanner](https://github.com/backstagephp/laravel-seo-scanner) | Technical audit | 275 | 31 | 1 | n/c | MIT | PHP | 2026-07-08 | Yes |
| 22 | [scrapy/scrapy](https://github.com/scrapy/scrapy) | Crawl framework | 65,340 | 12,123 | 180 | 761 | BSD-3-Clause | Python | 2026-11-10 | Yes |
| 23 | [apify/crawlee](https://github.com/apify/crawlee) | Crawl framework | 26,425 | 1,758 | 135 | 164 | Apache-2.0 | TypeScript | 2026-11-12 | Yes |
| 24 | [unclecode/crawl4ai](https://github.com/unclecode/crawl4ai) | Crawl framework | 87,250 | 9,095 | 334 | n/c | Apache-2.0 | Python | 2026-11-10 | Yes |
| 25 | [gocolly/colly](https://github.com/gocolly/colly) | Crawl framework | 25,590 | 1,860 | 195 | n/c | Apache-2.0 | Go | 2026-10-16 | Yes |
| 26 | [projectdiscovery/katana](https://github.com/projectdiscovery/katana) | Crawl framework | 17,831 | 1,226 | 27 | n/c | MIT | Go | 2026-11-09 | Yes |
| 27 | [spatie/crawler](https://github.com/spatie/crawler) | Crawl framework | 2,829 | 369 | 0 | n/c | MIT | PHP | 2026-11-05 | Yes |
| 28 | [microsoft/playwright-python](https://github.com/microsoft/playwright-python) | Browser automation | 15,102 | 1,256 | 2 | n/c | Apache-2.0 | Python | 2026-11-11 | Yes |
| 29 | [lycheeverse/lychee](https://github.com/lycheeverse/lychee) | Link checker | 4,123 | 246 | 79 | 127 | Apache-2.0 | Rust | 2026-11-09 | Yes |
| 30 | [JustinBeckwith/linkinator](https://github.com/JustinBeckwith/linkinator) | Link checker | 1,289 | 110 | 19 | 30 | MIT | TypeScript | 2026-11-11 | Yes |
| 31 | [stevenvachon/broken-link-checker](https://github.com/stevenvachon/broken-link-checker) | Link checker | 2,084 | 310 | 81 | n/c | MIT | JavaScript | 2026-09-07 | Yes |
| 32 | [linkchecker/linkchecker](https://github.com/linkchecker/linkchecker) | Link checker | 1,081 | 169 | 96 | n/c | GPL-2.0 | Python | 2026-09-22 | Yes |
| 33 | [google/robotstxt](https://github.com/google/robotstxt) | robots.txt | 3,479 | 258 | 12 | 22 | Apache-2.0 | C++ | 2026-04-01 | Yes |
| 34 | [seomoz/reppy](https://github.com/seomoz/reppy) | robots.txt | 196 | 39 | 25 | n/c | MIT | Python | 2024-01-12 | No |
| 35 | [samclarke/robots-parser](https://github.com/samclarke/robots-parser) | robots.txt | 168 | 19 | 7 | n/c | MIT | JavaScript | 2026-10-08 | Yes |
| 36 | [GateNLP/ultimate-sitemap-parser](https://github.com/GateNLP/ultimate-sitemap-parser) | Sitemaps | 257 | 79 | 5 | 10 | GPL-3.0 | Python | 2026-06-16 | Yes |
| 37 | [lgraubner/sitemap-generator](https://github.com/lgraubner/sitemap-generator) | Sitemaps | 453 | 136 | 32 | n/c | MIT | JavaScript | 2024-06-28 | No |
| 38 | [iamvishnusankar/next-sitemap](https://github.com/iamvishnusankar/next-sitemap) | Sitemaps | 3,751 | 138 | 8 | n/c | MIT | TypeScript | 2026-05-13 | Yes |
| 39 | [GoogleChrome/lighthouse](https://github.com/GoogleChrome/lighthouse) | Performance | 31,049 | 9,787 | 435 | 398 | Apache-2.0 | JavaScript | 2026-11-12 | Yes |
| 40 | [GoogleChrome/lighthouse-ci](https://github.com/GoogleChrome/lighthouse-ci) | Performance | 7,140 | 732 | 153 | n/c | Apache-2.0 | JavaScript | 2026-11-12 | Yes |
| 41 | [GoogleChrome/web-vitals](https://github.com/GoogleChrome/web-vitals) | Performance | 8,674 | 539 | 18 | n/c | Apache-2.0 | JavaScript | 2026-11-12 | Yes |
| 42 | [sitespeedio/sitespeed.io](https://github.com/sitespeedio/sitespeed.io) | Performance | 5,050 | 632 | 57 | n/c | MIT | JavaScript | 2026-11-11 | Yes |
| 43 | [cloudfour/lighthouse-parade](https://github.com/cloudfour/lighthouse-parade) | Performance | 373 | 15 | 27 | n/c | MIT | TypeScript | 2026-11-11 | Yes |
| 44 | [GoogleChromeLabs/psi](https://github.com/GoogleChromeLabs/psi) | Performance | 3,096 | 122 | 15 | n/c | Apache-2.0 | JavaScript | 2021-04-10 | No (archived) |
| 45 | [google/schemarama](https://github.com/google/schemarama) | Structured data | 150 | 25 | 22 | n/c | Apache-2.0 | JavaScript | 2024-08-19 | No (archived) |
| 46 | [microlinkhq/metascraper](https://github.com/microlinkhq/metascraper) | Metadata | 2,753 | 183 | 9 | n/c | MIT | HTML | 2026-11-08 | Yes |
| 47 | [RehanSaeed/Schema.NET](https://github.com/RehanSaeed/Schema.NET) | Structured data | 691 | 87 | 67 | n/c | MIT | C# | 2026-11-11 | Yes |
| 48 | [adbar/trafilatura](https://github.com/adbar/trafilatura) | Content extraction | 7,122 | 505 | 64 | 120 | Apache-2.0 | Python | 2026-11-11 | Yes |
| 49 | [mozilla/readability](https://github.com/mozilla/readability) | Content extraction | 11,538 | 741 | 322 | n/c | Apache-2.0 | JavaScript | 2026-08-04 | Yes |
| 50 | [textstat/textstat](https://github.com/textstat/textstat) | Readability | 1,393 | 193 | 23 | n/c | MIT | Python | 2026-10-26 | Yes |
| 51 | [cdimascio/py-readability-metrics](https://github.com/cdimascio/py-readability-metrics) | Readability | 410 | 65 | 23 | n/c | MIT | Python | 2024-09-15 | No |
| 52 | [hilmanski/contentswift](https://github.com/hilmanski/contentswift) | Content optimisation | 165 | 31 | 14 | n/c | none | TypeScript | 2023-10-31 | No |
| 53 | [karust/openserp](https://github.com/karust/openserp) | SERP | 1,572 | 188 | 28 | 9 | MIT | Go | 2026-11-11 | Yes |
| 54 | [searxng/searxng](https://github.com/searxng/searxng) | SERP | 39,472 | 3,606 | 208 | 366 | AGPL-3.0 | Python | 2026-11-11 | Yes |
| 55 | [GeneralMills/pytrends](https://github.com/GeneralMills/pytrends) | Trends | 3,730 | 893 | 152 | n/c | NOASSERTION | Python | 2024-08-10 | No (archived) |
| 56 | [chukhraiartur/seo-keyword-research-tool](https://github.com/chukhraiartur/seo-keyword-research-tool) | Keyword research | 167 | 22 | 6 | n/c | MIT | Python | 2023-05-10 | No |
| 57 | [searchsolved/search-solved-public-seo](https://github.com/searchsolved/search-solved-public-seo) | SEO scripts | 424 | 179 | 8 | n/c | NOASSERTION | Python | 2026-09-21 | Yes |
| 58 | [joshcarty/google-searchconsole](https://github.com/joshcarty/google-searchconsole) | Search Console | 256 | 75 | 2 | 6 | MIT | Python | 2025-11-15 | Yes |
| 59 | [AminForou/mcp-gsc](https://github.com/AminForou/mcp-gsc) | Search Console | 2,180 | 281 | 8 | n/c | MIT | Python | 2026-11-06 | Yes |
| 60 | [sundios/SEO-Dashboard](https://github.com/sundios/SEO-Dashboard) | Search Console | 144 | 42 | 17 | n/c | none | TypeScript | 2026-08-05 | Yes |
| 61 | [goenning/google-indexing-script](https://github.com/goenning/google-indexing-script) | Indexing | 7,731 | 553 | 18 | n/c | MIT | TypeScript | 2024-10-10 | No |
| 62 | [commoncrawl/cdx_toolkit](https://github.com/commoncrawl/cdx_toolkit) | Web data | 221 | 38 | 10 | n/c | Apache-2.0 | Python | 2026-10-16 | Yes |
| 63 | [commoncrawl/cc-pyspark](https://github.com/commoncrawl/cc-pyspark) | Web data | 460 | 98 | 6 | n/c | MIT | Python | 2026-09-17 | Yes |
| 64 | [lc/gau](https://github.com/lc/gau) | Web data | 5,165 | 529 | 30 | n/c | MIT | Go | 2026-10-12 | Yes |
| 65 | [louislam/uptime-kuma](https://github.com/louislam/uptime-kuma) | Monitoring | 93,536 | 8,698 | 851 | 1159 | MIT | JavaScript | 2026-11-12 | Yes |
| 66 | [msgbyte/tianji](https://github.com/msgbyte/tianji) | Monitoring | 3,119 | 199 | 145 | n/c | Apache-2.0 | TypeScript | 2026-11-10 | Yes |
| 67 | [ollama/ollama](https://github.com/ollama/ollama) | AI | 186,727 | 19,031 | 4,627 | n/c | MIT | Go | 2026-11-12 | Yes |
| 68 | [AgriciDaniel/claude-seo](https://github.com/AgriciDaniel/claude-seo) | AI SEO | 28,341 | 3,653 | 51 | n/c | MIT | Python | 2026-11-11 | Yes |

## Per-repository evaluation

### 1. every-app/open-seo

- **URL:** https://github.com/every-app/open-seo
- **Main functionality:** All-in-one suite: keyword research, rank tracking, competitor insights, backlinks, site audits, AI visibility, MCP server
- **Technical architecture:** TypeScript web app; Docker or Cloudflare deploy; all SEO data bought per request from DataForSEO
- **Most useful features / ideas:** First-visitor-becomes-admin onboarding; MCP/agent access; focused workflows
- **Strengths:** Polished UI, very active, simple self-hosting
- **Weaknesses:** Unusable without a paid DataForSEO key; no own crawler-grade audit
- **Licence:** MIT
- **Used in this platform:** Adopted first-run admin flow. Deliberately the opposite data model: our core works with zero paid keys

### 2. crawlseo/crawlseo

- **URL:** https://github.com/crawlseo/crawlseo
- **Main functionality:** GSC analytics + site crawler + Core Web Vitals + MCP in one dashboard
- **Technical architecture:** Next.js, Prisma, PostgreSQL; RFC 9309 robots handling; DataForSEO optional, Google Autocomplete fallback
- **Most useful features / ideas:** Explicit list of every outbound host; noindex pages crawled but not scored; per-host robots.txt
- **Strengths:** Honest data-flow documentation; MIT
- **Weaknesses:** 16 issue types only; no scheduling; 2,000-page default cap
- **Licence:** MIT
- **Used in this platform:** Adopted: outbound-services table in docs, autocomplete as free keyword source, robots per origin, redirect targets re-checked

### 3. SelmiAbderrahim/rankme.fast

- **URL:** https://github.com/SelmiAbderrahim/rankme.fast
- **Main functionality:** Audits, rank tracking, keywords, backlinks, GSC, AI visibility
- **Technical architecture:** Docker Compose; MongoDB + PostgreSQL; vendor providers behind feature flags with `fake` demo backends
- **Most useful features / ideas:** Plain-language findings (page, why, fix); provider abstraction; encrypted secrets
- **Strengths:** Clear architecture docs
- **Weaknesses:** AGPL-3.0; does not crawl itself; needs vendor keys for real data; single maintainer
- **Licence:** AGPL-3.0
- **Used in this platform:** Idea only (AGPL, no code): every rule has a one-sentence why + fix; provider interface for SERP/AI

### 4. CorgiCorner/bisibility

- **URL:** https://github.com/CorgiCorner/bisibility
- **Main functionality:** Rank tracking, keyword research, backlinks, AI answer tracking, small site audit, GSC/GA4
- **Technical architecture:** TypeScript; hosted or self-hosted; DataForSEO BYO
- **Most useful features / ideas:** Share-of-voice vs competitors; scheduled checks with alerts
- **Strengths:** Good docs and demo
- **Weaknesses:** AGPL-3.0; audit covers a small page sample; metered data
- **Licence:** AGPL-3.0
- **Used in this platform:** Idea only: alert model for scheduled checks

### 5. towfiqi/serpbear

- **URL:** https://github.com/towfiqi/serpbear
- **Main functionality:** Keyword position tracking with GSC integration and email notifications
- **Technical architecture:** Next.js + SQLite; scraping via third-party SERP APIs/proxies
- **Most useful features / ideas:** SQLite-first deployment; GSC to enrich keyword rows with real clicks/impressions
- **Strengths:** Lightweight, popular
- **Weaknesses:** Depends on paid scrapers/proxies for positions
- **Licence:** MIT
- **Used in this platform:** Adopted: SQLite default; keyword table enriched with measured GSC data; position tracking via GSC rather than scraping

### 6. serphacker/serposcope

- **URL:** https://github.com/serphacker/serposcope
- **Main functionality:** Legacy Java rank tracker scraping Google with proxies/captcha solvers
- **Technical architecture:** Java, embedded DB
- **Most useful features / ideas:** Historical rank charts
- **Strengths:** Was the reference OSS rank tracker
- **Weaknesses:** Archived; direct Google scraping breaks ToS and constantly
- **Licence:** MIT
- **Used in this platform:** Counter-example: we do not scrape Google result pages

### 7. AgriciDaniel/keywordpro

- **URL:** https://github.com/AgriciDaniel/keywordpro
- **Main functionality:** Local-first keyword research with guided reports and saved sessions
- **Technical architecture:** TypeScript desktop/web
- **Most useful features / ideas:** Saved research sessions; guided reports
- **Strengths:** Local-first
- **Weaknesses:** Young project
- **Licence:** Apache-2.0
- **Used in this platform:** Idea: saved keyword lists per site

### 8. iannuttall/seo

- **URL:** https://github.com/iannuttall/seo
- **Main functionality:** Agent-oriented SEO: real Search Console data exposed to coding agents
- **Technical architecture:** TypeScript
- **Most useful features / ideas:** GSC as ground truth
- **Strengths:** Active
- **Weaknesses:** Agent-centric, little UI
- **Licence:** Apache-2.0
- **Used in this platform:** Reinforces GSC-as-measured-data principle

### 9. StJudeWasHere/seonaut

- **URL:** https://github.com/StJudeWasHere/seonaut
- **Main functionality:** Site crawler and auditor with issue severities and dashboards
- **Technical architecture:** Go + MySQL; server-rendered UI with ECharts; Docker
- **Most useful features / ideas:** Three-level severity, issue catalogue with explanations, crawl comparison
- **Strengths:** Fast, clean, focused, MIT
- **Weaknesses:** Requires MySQL; no JS rendering; limited beyond audit
- **Licence:** MIT
- **Used in this platform:** Closest model for our audit module: rule catalogue with severity + description, per-issue URL lists, crawl-to-crawl comparison

### 10. PhialsBasement/LibreCrawl

- **URL:** https://github.com/PhialsBasement/LibreCrawl
- **Main functionality:** Screaming-Frog-style web crawler with JS rendering, PSI, exports, n-gram analysis, plugins
- **Technical architecture:** Python Flask; multi-tenant sessions; Playwright Chromium
- **Most useful features / ideas:** One-click start scripts; CSV/XLSX/JSON export; n-gram analysis over body/headings/anchors
- **Strengths:** Actively maintained, genuinely free
- **Weaknesses:** Results largely session/browser-persisted; single maintainer
- **Licence:** MIT
- **Used in this platform:** Adopted: optional Playwright rendering, multi-format export, anchor/term analysis. We persist crawls in a database instead

### 11. janreges/siteone-crawler

- **URL:** https://github.com/janreges/siteone-crawler
- **Main functionality:** Cross-platform crawler/analyser: SEO, security headers, performance, accessibility, offline export
- **Technical architecture:** Rust CLI (earlier PHP/Swoole); HTML report
- **Most useful features / ideas:** Security-header and redirect checks; single self-contained report
- **Strengths:** Very fast; rich single-run report
- **Weaknesses:** CLI/report oriented, no persistent multi-site dashboard
- **Licence:** MIT
- **Used in this platform:** Adopted: HSTS/HTTPS-enforcement/host-variant site checks, standalone downloadable report

### 12. sethblack/python-seo-analyzer

- **URL:** https://github.com/sethblack/python-seo-analyzer
- **Main functionality:** Crawls a site, analyses word counts, titles, descriptions, headings
- **Technical architecture:** Python package + CLI; BeautifulSoup; optional LLM
- **Most useful features / ideas:** Simple page-level checks, keyword n-grams
- **Strengths:** Easy to embed
- **Weaknesses:** Basic rule set; no link graph or persistence
- **Licence:** NOASSERTION
- **Used in this platform:** Baseline of on-page checks we extend (95 rules)

### 13. viasite/site-audit-seo

- **URL:** https://github.com/viasite/site-audit-seo
- **Main functionality:** CLI/web service: crawl + Lighthouse per page, table output
- **Technical architecture:** Node.js, Puppeteer, Lighthouse
- **Most useful features / ideas:** Field presets; Lighthouse-per-URL batch
- **Strengths:** Useful table view
- **Weaknesses:** Heavy (browser per page); niche maintenance
- **Licence:** NOASSERTION
- **Used in this platform:** Idea: column presets in the pages table

### 14. nazuke/SEOMacroscope

- **URL:** https://github.com/nazuke/SEOMacroscope
- **Main functionality:** Windows desktop link/metadata scanner (Screaming Frog alternative)
- **Technical architecture:** C# WinForms
- **Most useful features / ideas:** Desktop-grade crawl tables, hreflang matrix
- **Strengths:** Broad feature list
- **Weaknesses:** GPL-3.0; Windows-only; unmaintained since 2024
- **Licence:** GPL-3.0
- **Used in this platform:** Idea only (GPL): hreflang reciprocity matrix

### 15. squirrelscan/squirrelscan

- **URL:** https://github.com/squirrelscan/squirrelscan
- **Main functionality:** Website QA with 310+ rules across SEO, performance, security for coding agents
- **Technical architecture:** TypeScript CLI
- **Most useful features / ideas:** Large categorised rule set; machine-readable output
- **Strengths:** Active
- **Weaknesses:** Agent/CLI focus
- **Licence:** MIT
- **Used in this platform:** Rule taxonomy cross-checked against ours

### 16. seo-skills/seo-audit-skill

- **URL:** https://github.com/seo-skills/seo-audit-skill
- **Main functionality:** CLI with 332 audit rules across categories
- **Technical architecture:** TypeScript
- **Most useful features / ideas:** Rule categories and weights
- **Strengths:** Broad rules
- **Weaknesses:** CLI only
- **Licence:** MIT
- **Used in this platform:** Rule taxonomy cross-check

### 17. kemalai/FreeCrawl-SEO-Tool

- **URL:** https://github.com/kemalai/FreeCrawl-SEO-Tool
- **Main functionality:** High-performance desktop crawler for SEO audits
- **Technical architecture:** TypeScript
- **Most useful features / ideas:** Large-crawl focus
- **Strengths:** MIT, recent
- **Weaknesses:** Young
- **Licence:** MIT
- **Used in this platform:** Benchmark for crawl throughput goals

### 18. beb7/gflare-tk

- **URL:** https://github.com/beb7/gflare-tk
- **Main functionality:** Greenflare: Python desktop SEO crawler
- **Technical architecture:** Python, Tkinter, SQLite
- **Most useful features / ideas:** SQLite as crawl store; exclusion/inclusion rules
- **Strengths:** Handles large crawls on a laptop
- **Weaknesses:** GPL-3.0; unmaintained since 2023
- **Licence:** GPL-3.0
- **Used in this platform:** Idea only (GPL): include/exclude URL patterns, SQLite crawl store

### 19. StanGirard/seo-audits-toolkit

- **URL:** https://github.com/StanGirard/seo-audits-toolkit
- **Main functionality:** Django app: Lighthouse, security headers, keyword extraction, internal link graphs
- **Technical architecture:** Django + Celery + Redis + Docker
- **Most useful features / ideas:** Internal-link graph visualisation; background jobs
- **Strengths:** Showed the all-in-one idea early
- **Weaknesses:** No licence file; unmaintained since 2023
- **Licence:** no licence file (all rights reserved by default)
- **Used in this platform:** No code used (unlicensed). Lesson: Celery/Redis stack hurt adoption - we default to in-process jobs

### 20. eliasdabbas/advertools

- **URL:** https://github.com/eliasdabbas/advertools
- **Main functionality:** Python library: Scrapy-based SEO crawler, sitemap/robots parsing to DataFrames, log analysis, GSC helpers
- **Technical architecture:** Python + Scrapy + pandas
- **Most useful features / ideas:** robots.txt and sitemap parsing as data; crawl output as analysable table; log-file parsing
- **Strengths:** Battle-tested by SEO analysts; MIT
- **Weaknesses:** Library, not a product; pandas-heavy
- **Licence:** MIT
- **Used in this platform:** Adopted ideas: treat crawl as a queryable dataset, sitemap/robots as structured reports. Log analysis is on our roadmap

### 21. backstagephp/laravel-seo-scanner

- **URL:** https://github.com/backstagephp/laravel-seo-scanner
- **Main functionality:** Scans Laravel routes for SEO issues
- **Technical architecture:** PHP package
- **Most useful features / ideas:** Check classes with weights
- **Strengths:** Neat rule abstraction
- **Weaknesses:** Framework-specific
- **Licence:** MIT
- **Used in this platform:** Rule-as-data pattern

### 22. scrapy/scrapy

- **URL:** https://github.com/scrapy/scrapy
- **Main functionality:** Industry-standard crawling framework
- **Technical architecture:** Python, Twisted reactor, middleware pipeline
- **Most useful features / ideas:** Per-domain throttling, retry middleware, depth limits, dupe filter
- **Strengths:** Mature, 760+ contributors
- **Weaknesses:** Twisted event loop does not compose with FastAPI/asyncio in one process
- **Licence:** BSD-3-Clause
- **Used in this platform:** Design reference (AutoThrottle, retry, depth). Not embedded: an httpx/asyncio crawler lives inside the API process

### 23. apify/crawlee

- **URL:** https://github.com/apify/crawlee
- **Main functionality:** Crawling/browser automation library with queues and session pools
- **Technical architecture:** Node.js/TypeScript (Python port exists)
- **Most useful features / ideas:** Unified HTTP + browser crawling; request queue persistence
- **Strengths:** Excellent abstractions
- **Weaknesses:** Node runtime
- **Licence:** Apache-2.0
- **Used in this platform:** Idea: same parser path for raw and rendered HTML

### 24. unclecode/crawl4ai

- **URL:** https://github.com/unclecode/crawl4ai
- **Main functionality:** LLM-oriented async crawler producing Markdown
- **Technical architecture:** Python asyncio + Playwright
- **Most useful features / ideas:** Rendered-page extraction to clean text
- **Strengths:** Very popular
- **Weaknesses:** Aimed at RAG, not SEO auditing
- **Licence:** Apache-2.0
- **Used in this platform:** Idea: Markdown extraction for the content editor (we use trafilatura)

### 25. gocolly/colly

- **URL:** https://github.com/gocolly/colly
- **Main functionality:** Fast Go scraping framework
- **Technical architecture:** Go
- **Most useful features / ideas:** Limit rules per domain
- **Strengths:** Fast, simple
- **Weaknesses:** Go
- **Licence:** Apache-2.0
- **Used in this platform:** Reference for per-host rate-limit rules

### 26. projectdiscovery/katana

- **URL:** https://github.com/projectdiscovery/katana
- **Main functionality:** Security-oriented crawler with headless mode
- **Technical architecture:** Go
- **Most useful features / ideas:** Scope control; form/JS endpoint discovery
- **Strengths:** Fast
- **Weaknesses:** Security focus
- **Licence:** MIT
- **Used in this platform:** Reference for strict scope rules

### 27. spatie/crawler

- **URL:** https://github.com/spatie/crawler
- **Main functionality:** PHP crawler with concurrency and JS execution option
- **Technical architecture:** PHP, Guzzle
- **Most useful features / ideas:** Crawl profiles (which URLs to crawl) and observers
- **Strengths:** Clean API
- **Weaknesses:** PHP
- **Licence:** MIT
- **Used in this platform:** Idea: scope object deciding crawlability

### 28. microsoft/playwright-python

- **URL:** https://github.com/microsoft/playwright-python
- **Main functionality:** Headless Chromium/Firefox/WebKit control
- **Technical architecture:** Python bindings over Playwright driver
- **Most useful features / ideas:** Request interception (route) lets us vet every browser request
- **Strengths:** First-class async API
- **Weaknesses:** Large browser download
- **Licence:** Apache-2.0
- **Used in this platform:** Used (optional extra) for JavaScript rendering; route interception enforces SSRF policy

### 29. lycheeverse/lychee

- **URL:** https://github.com/lycheeverse/lychee
- **Main functionality:** Fast async link checker
- **Technical architecture:** Rust CLI
- **Most useful features / ideas:** Accept-list of status codes; caching; excludes
- **Strengths:** Extremely fast
- **Weaknesses:** CLI only
- **Licence:** Apache-2.0
- **Used in this platform:** Adopted: treat 401/403/429/999 as 'unverifiable' not broken; HEAD then GET fallback

### 30. JustinBeckwith/linkinator

- **URL:** https://github.com/JustinBeckwith/linkinator
- **Main functionality:** Crawls a site and validates links
- **Technical architecture:** TypeScript
- **Most useful features / ideas:** Retry on 429 with Retry-After
- **Strengths:** Simple, maintained
- **Weaknesses:** Link checking only
- **Licence:** MIT
- **Used in this platform:** Adopted: honour Retry-After

### 31. stevenvachon/broken-link-checker

- **URL:** https://github.com/stevenvachon/broken-link-checker
- **Main functionality:** Finds broken links, missing images
- **Technical architecture:** Node.js
- **Most useful features / ideas:** Distinguishes link kinds (anchor, image, etc.)
- **Strengths:** Widely used
- **Weaknesses:** Slow releases
- **Licence:** MIT
- **Used in this platform:** Adopted: separate broken-image rule

### 32. linkchecker/linkchecker

- **URL:** https://github.com/linkchecker/linkchecker
- **Main functionality:** Recursive link checker with many protocols
- **Technical architecture:** Python
- **Most useful features / ideas:** Warnings vs errors
- **Strengths:** Mature
- **Weaknesses:** GPL-2.0
- **Licence:** GPL-2.0
- **Used in this platform:** Idea only (GPL)

### 33. google/robotstxt

- **URL:** https://github.com/google/robotstxt
- **Main functionality:** Google's production robots.txt parser/matcher
- **Technical architecture:** C++
- **Most useful features / ideas:** Reference semantics: longest match, Allow wins ties, * and $
- **Strengths:** Authoritative
- **Weaknesses:** C++ (bindings needed)
- **Licence:** Apache-2.0
- **Used in this platform:** Our pure-Python matcher follows these semantics/RFC 9309 and is tested against them

### 34. seomoz/reppy

- **URL:** https://github.com/seomoz/reppy
- **Main functionality:** robots.txt parser for Python
- **Technical architecture:** Python/C++
- **Most useful features / ideas:** Agent selection and caching
- **Strengths:** Fast
- **Weaknesses:** Unmaintained; build issues on modern Python
- **Licence:** MIT
- **Used in this platform:** Not used; motivated writing a dependency-free parser

### 35. samclarke/robots-parser

- **URL:** https://github.com/samclarke/robots-parser
- **Main functionality:** Node robots.txt parser with wildcard support
- **Technical architecture:** JavaScript
- **Most useful features / ideas:** Clear rule-precedence tests
- **Strengths:** Small, maintained
- **Weaknesses:** JS
- **Licence:** MIT
- **Used in this platform:** Test-case inspiration

### 36. GateNLP/ultimate-sitemap-parser

- **URL:** https://github.com/GateNLP/ultimate-sitemap-parser
- **Main functionality:** Robust sitemap discovery/parsing (XML, text, RSS, gzip, index trees)
- **Technical architecture:** Python
- **Most useful features / ideas:** Discovery via robots.txt then well-known paths; tolerant parsing
- **Strengths:** Handles real-world mess
- **Weaknesses:** GPL-3.0
- **Licence:** GPL-3.0
- **Used in this platform:** Idea only (GPL): discovery order and gzip/text/index support, re-implemented

### 37. lgraubner/sitemap-generator

- **URL:** https://github.com/lgraubner/sitemap-generator
- **Main functionality:** Generates XML sitemaps by crawling
- **Technical architecture:** Node.js
- **Most useful features / ideas:** Only indexable canonical URLs
- **Strengths:** Simple
- **Weaknesses:** Unmaintained
- **Licence:** MIT
- **Used in this platform:** Adopted behaviour: generated sitemap lists only indexable canonical 200 pages, split at 50,000 URLs

### 38. iamvishnusankar/next-sitemap

- **URL:** https://github.com/iamvishnusankar/next-sitemap
- **Main functionality:** Sitemap/robots generation for Next.js
- **Technical architecture:** TypeScript
- **Most useful features / ideas:** Index splitting
- **Strengths:** Popular
- **Weaknesses:** Framework-specific
- **Licence:** MIT
- **Used in this platform:** Splitting rules reference

### 39. GoogleChrome/lighthouse

- **URL:** https://github.com/GoogleChrome/lighthouse
- **Main functionality:** Automated audits for performance, accessibility, best practices, SEO
- **Technical architecture:** Node.js, Chrome DevTools protocol
- **Most useful features / ideas:** Audit result model (score, savings, items)
- **Strengths:** The standard
- **Weaknesses:** Needs Chrome/Node
- **Licence:** Apache-2.0
- **Used in this platform:** Integrated two ways: PageSpeed Insights API (hosted Lighthouse + CrUX field data) and optional local CLI; one parser for both

### 40. GoogleChrome/lighthouse-ci

- **URL:** https://github.com/GoogleChrome/lighthouse-ci
- **Main functionality:** Lighthouse in CI with history
- **Technical architecture:** Node.js
- **Most useful features / ideas:** Score history over time
- **Strengths:** Official
- **Weaknesses:** CI oriented
- **Licence:** Apache-2.0
- **Used in this platform:** Adopted: stored run history and trend chart

### 41. GoogleChrome/web-vitals

- **URL:** https://github.com/GoogleChrome/web-vitals
- **Main functionality:** Library defining Core Web Vitals measurement and thresholds
- **Technical architecture:** JavaScript
- **Most useful features / ideas:** Good/needs-improvement/poor thresholds
- **Strengths:** Authoritative
- **Weaknesses:** Client-side library
- **Licence:** Apache-2.0
- **Used in this platform:** Thresholds used for metric ratings

### 42. sitespeedio/sitespeed.io

- **URL:** https://github.com/sitespeedio/sitespeed.io
- **Main functionality:** Performance testing toolkit with dashboards
- **Technical architecture:** Node.js, Browsertime, Docker
- **Most useful features / ideas:** Budgets and coaching advice
- **Strengths:** Deep performance tooling
- **Weaknesses:** Heavy stack
- **Licence:** MIT
- **Used in this platform:** Idea: recommendations grouped by topic

### 43. cloudfour/lighthouse-parade

- **URL:** https://github.com/cloudfour/lighthouse-parade
- **Main functionality:** Crawls a domain and runs Lighthouse on each page
- **Technical architecture:** TypeScript
- **Most useful features / ideas:** Batch Lighthouse over crawl
- **Strengths:** Useful CSV output
- **Weaknesses:** Slow by nature
- **Licence:** MIT
- **Used in this platform:** Roadmap idea: batch PSI over top pages

### 44. GoogleChromeLabs/psi

- **URL:** https://github.com/GoogleChromeLabs/psi
- **Main functionality:** PageSpeed Insights reporting for Node
- **Technical architecture:** JavaScript
- **Most useful features / ideas:** Simple PSI wrapper
- **Strengths:** Official sample
- **Weaknesses:** Archived
- **Licence:** Apache-2.0
- **Used in this platform:** API usage reference only

### 45. google/schemarama

- **URL:** https://github.com/google/schemarama
- **Main functionality:** Validation of structured data with shapes (ShEx/SHACL)
- **Technical architecture:** JavaScript
- **Most useful features / ideas:** Shape-based required/recommended properties per type
- **Strengths:** Standards-based
- **Weaknesses:** Archived
- **Licence:** Apache-2.0
- **Used in this platform:** Idea: per-type required/recommended property tables (ours are hand-maintained Python data)

### 46. microlinkhq/metascraper

- **URL:** https://github.com/microlinkhq/metascraper
- **Main functionality:** Extracts unified metadata from Open Graph, JSON-LD, meta tags
- **Technical architecture:** Node.js rule bundles
- **Most useful features / ideas:** Fallback chains for title/description/image
- **Strengths:** Well designed
- **Weaknesses:** Node
- **Licence:** MIT
- **Used in this platform:** Idea: extraction fallbacks

### 47. RehanSaeed/Schema.NET

- **URL:** https://github.com/RehanSaeed/Schema.NET
- **Main functionality:** schema.org types as C# classes
- **Technical architecture:** .NET
- **Most useful features / ideas:** Typed templates
- **Strengths:** Complete vocabulary
- **Weaknesses:** .NET
- **Licence:** MIT
- **Used in this platform:** Idea: template generator per type

### 48. adbar/trafilatura

- **URL:** https://github.com/adbar/trafilatura
- **Main functionality:** Main-content and metadata extraction from HTML
- **Technical architecture:** Python + lxml
- **Most useful features / ideas:** Boilerplate removal; Markdown output
- **Strengths:** Best-in-class accuracy, Apache-2.0
- **Weaknesses:** Adds latency per page
- **Licence:** Apache-2.0
- **Used in this platform:** Used as a dependency for loading pages into the content editor

### 49. mozilla/readability

- **URL:** https://github.com/mozilla/readability
- **Main functionality:** Reader-mode article extraction
- **Technical architecture:** JavaScript
- **Most useful features / ideas:** Boilerplate heuristics
- **Strengths:** Proven
- **Weaknesses:** JS
- **Licence:** Apache-2.0
- **Used in this platform:** Heuristic reference for main-text extraction

### 50. textstat/textstat

- **URL:** https://github.com/textstat/textstat
- **Main functionality:** Readability statistics (Flesch, etc.)
- **Technical architecture:** Python
- **Most useful features / ideas:** Formula implementations
- **Strengths:** Simple, MIT
- **Weaknesses:** English-centric
- **Licence:** MIT
- **Used in this platform:** Formulas re-implemented in ~40 lines to avoid a dependency; limitation documented

### 51. cdimascio/py-readability-metrics

- **URL:** https://github.com/cdimascio/py-readability-metrics
- **Main functionality:** Readability formulas for Python
- **Technical architecture:** Python + NLTK
- **Most useful features / ideas:** Grade-level outputs
- **Strengths:** Accurate
- **Weaknesses:** NLTK dependency
- **Licence:** MIT
- **Used in this platform:** Reference for formula checks

### 52. hilmanski/contentswift

- **URL:** https://github.com/hilmanski/contentswift
- **Main functionality:** Free content research/optimisation tool (Surfer-style)
- **Technical architecture:** TypeScript; SERP API for competitor pages
- **Most useful features / ideas:** Term-frequency comparison against top results
- **Strengths:** Right idea, open
- **Weaknesses:** Needs a SERP API; unmaintained since 2023; no licence
- **Licence:** no licence file (all rights reserved by default)
- **Used in this platform:** No code used. Idea adopted: compare draft terms/headings with pages that rank

### 53. karust/openserp

- **URL:** https://github.com/karust/openserp
- **Main functionality:** Self-hosted multi-engine search API
- **Technical architecture:** Go + headless browsers
- **Most useful features / ideas:** Uniform result schema across engines
- **Strengths:** Free, self-hosted
- **Weaknesses:** Scrapes engines (ToS/captcha risk)
- **Licence:** MIT
- **Used in this platform:** Not integrated by default; our SERP layer has a provider interface where it could be added

### 54. searxng/searxng

- **URL:** https://github.com/searxng/searxng
- **Main functionality:** Privacy-respecting metasearch engine with JSON API
- **Technical architecture:** Python/Flask; engine plugins
- **Most useful features / ideas:** JSON results incl. answers/infoboxes/suggestions
- **Strengths:** Huge community; free
- **Weaknesses:** AGPL-3.0; results are a blend, not Google's exact order
- **Licence:** AGPL-3.0
- **Used in this platform:** Supported as an external service over HTTP (no code linked, so AGPL does not affect our licence)

### 55. GeneralMills/pytrends

- **URL:** https://github.com/GeneralMills/pytrends
- **Main functionality:** Unofficial Google Trends client
- **Technical architecture:** Python
- **Most useful features / ideas:** Interest over time, related queries
- **Strengths:** Was the standard
- **Weaknesses:** Archived; breaks frequently; unofficial
- **Licence:** NOASSERTION
- **Used in this platform:** Not integrated (unreliable). Google Trends is listed as a limitation/roadmap item

### 56. chukhraiartur/seo-keyword-research-tool

- **URL:** https://github.com/chukhraiartur/seo-keyword-research-tool
- **Main functionality:** Google Autocomplete, People Also Ask and related searches via SerpApi
- **Technical architecture:** Python
- **Most useful features / ideas:** Combining suggestion sources
- **Strengths:** Simple
- **Weaknesses:** Needs SerpApi for most sources
- **Licence:** MIT
- **Used in this platform:** Idea: merge several suggestion sources and record which source produced each keyword

### 57. searchsolved/search-solved-public-seo

- **URL:** https://github.com/searchsolved/search-solved-public-seo
- **Main functionality:** Collection of Python SEO scripts (clustering, cannibalisation, internal linking)
- **Technical architecture:** Python/Streamlit
- **Most useful features / ideas:** SERP-overlap keyword clustering; GSC-based cannibalisation detection
- **Strengths:** Practitioner-proven techniques
- **Weaknesses:** Mixed licences per script; scripts not a product
- **Licence:** NOASSERTION
- **Used in this platform:** Techniques re-implemented from scratch: SERP-overlap clustering, query-with-multiple-pages cannibalisation

### 58. joshcarty/google-searchconsole

- **URL:** https://github.com/joshcarty/google-searchconsole
- **Main functionality:** Pythonic wrapper for the Search Console API
- **Technical architecture:** Python + google-api-python-client
- **Most useful features / ideas:** Query builder with dimensions and date ranges
- **Strengths:** Pleasant API
- **Weaknesses:** Thin maintenance
- **Licence:** MIT
- **Used in this platform:** API usage reference; we call the REST API directly with httpx to avoid the Google client dependency tree

### 59. AminForou/mcp-gsc

- **URL:** https://github.com/AminForou/mcp-gsc
- **Main functionality:** Search Console tools exposed over MCP
- **Technical architecture:** Python
- **Most useful features / ideas:** Useful canned analyses (declines, quick wins)
- **Strengths:** Popular
- **Weaknesses:** Agent-only
- **Licence:** MIT
- **Used in this platform:** Insight ideas: striking-distance queries, period-over-period declines

### 60. sundios/SEO-Dashboard

- **URL:** https://github.com/sundios/SEO-Dashboard
- **Main functionality:** GSC analytics dashboard
- **Technical architecture:** Next.js
- **Most useful features / ideas:** Comparison views
- **Strengths:** Readable UI
- **Weaknesses:** GSC only
- **Licence:** no licence file (all rights reserved by default)
- **Used in this platform:** UI reference for performance charts

### 61. goenning/google-indexing-script

- **URL:** https://github.com/goenning/google-indexing-script
- **Main functionality:** Requests indexing via the Indexing API
- **Technical architecture:** TypeScript
- **Most useful features / ideas:** Batch URL submission
- **Strengths:** Popular
- **Weaknesses:** Indexing API is officially only for job/broadcast pages
- **Licence:** MIT
- **Used in this platform:** Not implemented; documented as a limitation rather than encouraging off-label API use

### 62. commoncrawl/cdx_toolkit

- **URL:** https://github.com/commoncrawl/cdx_toolkit
- **Main functionality:** Client for Common Crawl and Wayback CDX indexes
- **Technical architecture:** Python
- **Most useful features / ideas:** URL-index queries
- **Strengths:** Official-adjacent
- **Weaknesses:** CDX answers 'which URLs exist', not 'who links to X'
- **Licence:** Apache-2.0
- **Used in this platform:** Evaluated for backlinks: the CDX index cannot return inbound links, so it was not integrated

### 63. commoncrawl/cc-pyspark

- **URL:** https://github.com/commoncrawl/cc-pyspark
- **Main functionality:** Spark jobs over Common Crawl (incl. link extraction)
- **Technical architecture:** PySpark
- **Most useful features / ideas:** Web-graph construction
- **Strengths:** The honest way to build a link index
- **Weaknesses:** Needs a cluster and terabytes
- **Licence:** MIT
- **Used in this platform:** Documented as the realistic path to an open backlink index (roadmap, out of scope for a local app)

### 64. lc/gau

- **URL:** https://github.com/lc/gau
- **Main functionality:** Fetch known URLs from Wayback, Common Crawl, OTX
- **Technical architecture:** Go
- **Most useful features / ideas:** Historical URL discovery
- **Strengths:** Fast
- **Weaknesses:** Recon tool
- **Licence:** MIT
- **Used in this platform:** Roadmap idea: discover legacy URLs to find redirect gaps

### 65. louislam/uptime-kuma

- **URL:** https://github.com/louislam/uptime-kuma
- **Main functionality:** Self-hosted uptime monitoring
- **Technical architecture:** Node.js + SQLite, Vue
- **Most useful features / ideas:** Simple monitors with intervals and notifications; SQLite
- **Strengths:** Loved for its ease of use
- **Weaknesses:** Uptime only
- **Licence:** MIT
- **Used in this platform:** Adopted: monitor = kind + interval + state; alerts feed; single-process scheduler

### 66. msgbyte/tianji

- **URL:** https://github.com/msgbyte/tianji
- **Main functionality:** Analytics + uptime + status pages
- **Technical architecture:** TypeScript
- **Most useful features / ideas:** Combined monitoring views
- **Strengths:** Active
- **Weaknesses:** Broad scope
- **Licence:** Apache-2.0
- **Used in this platform:** UI reference for alert lists

### 67. ollama/ollama

- **URL:** https://github.com/ollama/ollama
- **Main functionality:** Run open LLMs locally with an HTTP API
- **Technical architecture:** Go server
- **Most useful features / ideas:** Simple /api/chat endpoint
- **Strengths:** De-facto local LLM runtime, MIT
- **Weaknesses:** Model quality varies
- **Licence:** MIT
- **Used in this platform:** Integrated as the default optional AI provider over HTTP

### 68. AgriciDaniel/claude-seo

- **URL:** https://github.com/AgriciDaniel/claude-seo
- **Main functionality:** SEO skill pack for coding agents (audits, schema, content)
- **Technical architecture:** Python + prompt packs
- **Most useful features / ideas:** Task-specific prompts grounded in fetched page data
- **Strengths:** Popular
- **Weaknesses:** Requires an agent host; quality depends on the model
- **Licence:** MIT
- **Used in this platform:** Idea: one prompt per task with real data attached; we add an explicit no-invented-metrics system prompt

## Top 20 repositories worth studying most closely

Ranked by how much they informed this platform (functionality, code quality, reliability, maintenance, documentation and licence), not by stars.

| Rank | Repository | Why it matters here |
|---:|---|---|
| 1 | StJudeWasHere/seonaut | Closest model for our audit module: rule catalogue with severity + description, per-issue URL lists, crawl-to-crawl comparison |
| 2 | PhialsBasement/LibreCrawl | Adopted: optional Playwright rendering, multi-format export, anchor/term analysis. We persist crawls in a database instead |
| 3 | crawlseo/crawlseo | Adopted: outbound-services table in docs, autocomplete as free keyword source, robots per origin, redirect targets re-checked |
| 4 | every-app/open-seo | Adopted first-run admin flow. Deliberately the opposite data model: our core works with zero paid keys |
| 5 | janreges/siteone-crawler | Adopted: HSTS/HTTPS-enforcement/host-variant site checks, standalone downloadable report |
| 6 | eliasdabbas/advertools | Adopted ideas: treat crawl as a queryable dataset, sitemap/robots as structured reports. Log analysis is on our roadmap |
| 7 | scrapy/scrapy | Design reference (AutoThrottle, retry, depth). Not embedded: an httpx/asyncio crawler lives inside the API process |
| 8 | google/robotstxt | Our pure-Python matcher follows these semantics/RFC 9309 and is tested against them |
| 9 | GateNLP/ultimate-sitemap-parser | Idea only (GPL): discovery order and gzip/text/index support, re-implemented |
| 10 | GoogleChrome/lighthouse | Integrated two ways: PageSpeed Insights API (hosted Lighthouse + CrUX field data) and optional local CLI; one parser for both |
| 11 | adbar/trafilatura | Used as a dependency for loading pages into the content editor |
| 12 | lycheeverse/lychee | Adopted: treat 401/403/429/999 as 'unverifiable' not broken; HEAD then GET fallback |
| 13 | searxng/searxng | Supported as an external service over HTTP (no code linked, so AGPL does not affect our licence) |
| 14 | searchsolved/search-solved-public-seo | Techniques re-implemented from scratch: SERP-overlap clustering, query-with-multiple-pages cannibalisation |
| 15 | towfiqi/serpbear | Adopted: SQLite default; keyword table enriched with measured GSC data; position tracking via GSC rather than scraping |
| 16 | louislam/uptime-kuma | Adopted: monitor = kind + interval + state; alerts feed; single-process scheduler |
| 17 | SelmiAbderrahim/rankme.fast | Idea only (AGPL, no code): every rule has a one-sentence why + fix; provider interface for SERP/AI |
| 18 | hilmanski/contentswift | No code used. Idea adopted: compare draft terms/headings with pages that rank |
| 19 | joshcarty/google-searchconsole | API usage reference; we call the REST API directly with httpx to avoid the Google client dependency tree |
| 20 | commoncrawl/cc-pyspark | Documented as the realistic path to an open backlink index (roadmap, out of scope for a local app) |

## Key findings

1. **Most 'open-source Ahrefs/Semrush alternatives' are front-ends for paid data.** open-seo, rankme.fast, bisibility and (optionally) crawlseo obtain keywords, rankings and backlinks from DataForSEO. They are open source, but not usable for free. This platform takes the opposite position: everything in the core runs on data it measures itself or that the user already owns.
2. **The strongest genuinely free components are crawlers and auditors** (seonaut, LibreCrawl, siteone-crawler). None of them combines a persistent multi-site database, a deep rule set, Search Console, content optimisation and monitoring in one application.
3. **No open project has a web-scale backlink index.** The only open raw material is Common Crawl, which requires cluster-scale processing. Backlink features here therefore work on imported datasets plus live verification.
4. **Search volume has no free, legitimate, programmatic source.** Autocomplete endpoints give suggestions only. Projects that show volumes either buy them or guess. We show measured Search Console impressions and imported Keyword Planner values, and leave the field empty otherwise.
5. **Heavy infrastructure hurts adoption.** Projects needing MySQL/Mongo/Redis/Celery are routinely reported as hard to install; SQLite-first projects (Uptime Kuma, SerpBear) spread widely. Hence SQLite by default with PostgreSQL optional and no mandatory queue service.

## Licence review

This project is released under the **MIT licence**. All application code was written for this project; nothing was copied from the repositories above.

| Source licence | Repositories | How it was handled |
|---|---|---|
| MIT / BSD / Apache-2.0 | most of the list | Ideas studied; a few are runtime dependencies (see below). Compatible with MIT distribution. |
| GPL-2.0 / GPL-3.0 | ultimate-sitemap-parser, linkchecker, SEOMacroscope, gflare-tk | Concepts only. No code, tests or data copied; behaviour re-implemented independently. Not dependencies. |
| AGPL-3.0 | searxng, rankme.fast, bisibility | SearXNG can be *called over HTTP* as a separate, user-operated service; no AGPL code is linked or distributed. Others: ideas only. |
| No licence | seo-audits-toolkit, contentswift, several script collections | Treated as all-rights-reserved: read for ideas, nothing reused. |

### Runtime dependencies and their licences

| Component | Licence | | Component | Licence |
|---|---|---|---|---|
| FastAPI, Starlette, Pydantic | MIT / BSD-3 | | React, React Router, TanStack Query | MIT |
| SQLAlchemy, Alembic | MIT | | Vite, Tailwind CSS | MIT |
| httpx, httpcore, uvicorn | BSD-3 | | Recharts | MIT |
| lxml, tldextract, reportlab | BSD-3 | | lucide-react | ISC |
| trafilatura (+ courlan, htmldate, justext) | Apache-2.0 / BSD | | clsx | MIT |
| argon2-cffi, PyJWT, openpyxl, email-validator | MIT / Unlicense | | Playwright (optional) | Apache-2.0 |

Apache-2.0 dependencies require preserving their NOTICE/licence texts when redistributing bundles; `docs/THIRD_PARTY_LICENSES.md` records this.
