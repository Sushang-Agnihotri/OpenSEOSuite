# Feature Comparison

How this platform compares with commercial SEO suites, and exactly where each capability's data comes from.
Statements about commercial tools describe their publicly documented feature sets; their prices and limits change, so none are quoted.

Legend: **Yes** = implemented and tested here · **Partial** = implemented with a stated limitation · **No** = not available · **n/a** = the product does not target this area

## 1. Capability matrix

| Capability | Ahrefs | Semrush | Screaming Frog | Sitebulb | Surfer SEO | Moz Pro | This platform |
|---|---|---|---|---|---|---|---|
| Site crawler (own bot) | Yes | Yes | Yes | Yes | n/a | Yes | **Yes** (async, robots-aware, resumable history) |
| JavaScript rendering | Yes | Yes | Yes | Yes | n/a | Partial | **Yes** (optional Playwright install) |
| Technical audit rules | ~170 | ~140 | ~300 filters | ~300 hints | n/a | ~40 | **Yes** (95 rules, 4 severities, fix text) |
| Issue prioritisation & score | Yes | Yes | Partial | Yes | n/a | Yes | **Yes** (documented formula) |
| Redirect chains / loops | Yes | Yes | Yes | Yes | n/a | Yes | **Yes** |
| Duplicate / near-duplicate content | Yes | Yes | Yes | Yes | n/a | Yes | **Yes** (hash + SimHash) |
| hreflang validation | Yes | Yes | Yes | Yes | n/a | Partial | **Yes** (codes, reciprocity, targets) |
| Structured-data validation | Partial | Yes | Yes | Yes | n/a | No | **Partial** (25 types, required/recommended) |
| XML sitemap audit + generation | Yes | Yes | Yes | Yes | n/a | Partial | **Yes** |
| Internal link graph + PageRank | Yes | Yes | Yes | Yes | Partial | Partial | **Yes** |
| Crawl comparison over time | Yes | Yes | Yes | Yes | n/a | Yes | **Yes** |
| Core Web Vitals / Lighthouse | Yes | Yes | Yes (PSI) | Yes | n/a | Partial | **Yes** (PSI API + optional local Lighthouse) |
| Keyword suggestions | Yes | Yes | n/a | n/a | Yes | Yes | **Yes** (Google/Bing/DuckDuckGo autocomplete) |
| Search volume | Yes (own DB) | Yes (own DB) | n/a | n/a | Yes | Yes | **Partial** (GSC impressions; imported Keyword Planner) |
| Keyword difficulty | Yes (link-based) | Yes | n/a | n/a | Yes | Yes | **Partial** (SERP-composition estimate, labelled) |
| Keyword clustering | Yes | Yes | n/a | n/a | Yes | Partial | **Yes** (lexical; SERP-overlap function) |
| Search intent | Yes | Yes | n/a | n/a | Yes | Yes | **Partial** (rule-based estimate) |
| Cannibalisation detection | Partial | Yes | n/a | n/a | Partial | Partial | **Yes** (crawl-based and GSC-based) |
| SERP analysis | Yes | Yes | n/a | n/a | Yes | Yes | **Partial** (needs SearXNG / Google CSE / Brave key, or pasted URLs) |
| Daily rank tracking (any keyword, any location) | Yes | Yes | n/a | n/a | Partial | Yes | **Partial** (own site via GSC average position only) |
| Competitor traffic / ranking keywords | Yes | Yes | n/a | n/a | No | Yes | **No** (proprietary datasets) |
| Competitor on-site comparison | Partial | Partial | Manual | Manual | Partial | Partial | **Yes** (crawl both, compare measured metrics) |
| Backlink index (web-scale) | Yes | Yes | n/a | n/a | No | Yes | **No** |
| Backlink analysis of own data | Yes | Yes | n/a | n/a | No | Yes | **Yes** (imports + live verification) |
| Content editor with optimisation score | Partial | Yes | n/a | n/a | Yes | Partial | **Yes** |
| Search Console integration | Yes | Yes | Yes | Yes | Yes | Partial | **Yes** (OAuth + CSV import) |
| Local SEO (listings management) | No | Yes | n/a | n/a | No | Yes (Moz Local) | **Partial** (schema, NAP consistency, citation imports) |
| Scheduled monitoring + alerts | Yes | Yes | Partial | Partial | No | Yes | **Yes** |
| PDF / Excel / CSV / JSON reports | Yes | Yes | Yes | Yes | Partial | Yes | **Yes** |
| AI assistance | Yes | Yes | Partial | No | Yes | Partial | **Partial** (optional, local Ollama or own API key) |
| Log-file analysis | No | Yes | Separate product | No | n/a | No | **No** (roadmap) |
| Self-hosted, data stays local | No | No | Desktop | Desktop | No | No | **Yes** |
| Cost | Subscription | Subscription | Annual licence | Subscription | Subscription | Subscription | **Free (MIT)** |

Other tools the brief names: **SE Ranking** and **Mangools** are primarily rank-tracking/keyword suites built on proprietary keyword and
SERP databases (same gaps as Ahrefs/Semrush above); **Ubersuggest** is a lighter version of the same model; **SEO PowerSuite** is a desktop
bundle (crawler + rank tracker + link tools) whose crawler/audit portion is the part this platform matches.

## 2. Where each number comes from

| Data | Source in this platform | Status | Notes |
|---|---|---|---|
| Crawl data, statuses, links, content, issues | Our crawler | Measured | Limited by the crawl's URL cap and robots.txt |
| Internal PageRank, depth, orphan pages | Computed from the crawled link graph | Measured (model) | Internal only; unrelated to any search engine's metric |
| SEO score | Formula over detected issues | Derived | Formula is documented in the UI and README |
| Clicks, impressions, CTR, average position | Google Search Console API or CSV export | Measured by Google | Own verified sites only; anonymised queries are omitted by Google |
| Keyword suggestions | Public autocomplete endpoints of Google, Bing, DuckDuckGo | Measured (suggestions) | Unofficial endpoints; may change or rate-limit |
| Search volume, CPC, competition | Google Ads Keyword Planner CSV the user imports | Imported | Never estimated; empty when not imported |
| Search intent | Rule-based classifier | Estimated | Labelled as such |
| Keyword difficulty | SERP composition heuristic | Estimated | Not link-based; not comparable with commercial KD scores |
| Opportunity ('extra clicks') | GSC impressions x generic CTR curve | Estimated | Basis shown next to every figure |
| SERP results | SearXNG / Google Programmable Search API / Brave Search API / pasted URLs | Measured via provider | Provider ordering may differ from a live Google SERP |
| Core Web Vitals (field) | Chrome UX Report via PageSpeed Insights API | Measured by Google | Only for URLs/origins with enough traffic |
| Lighthouse lab metrics | PageSpeed Insights API or local Lighthouse | Measured (lab) | Single run; lab results vary between runs |
| Backlinks | User imports (GSC links export, other tools, CSV) | Imported + verified | Coverage equals the imported data; no global index |
| Competitor metrics | Our crawl of the competitor site | Measured | On-site facts only |
| AI text | Local model or user's API | Generated | Prompted with real data; must be reviewed |

## 3. What cannot be reproduced for free, and why

| Commercial capability | Why it is not reproducible | What we offer instead |
|---|---|---|
| Web-scale backlink index (Ahrefs, Semrush, Moz) | Requires continuously crawling billions of pages and storing the link graph | Import any link dataset, verify links live, analyse anchors/domains/targets, find broken link targets to reclaim |
| Keyword databases with volumes for any query | Built from licensed clickstream and ads data | Autocomplete suggestions, GSC impressions for your own queries, Keyword Planner import |
| Competitors' organic keywords and traffic estimates | Derived from the above keyword + SERP databases | Topical overlap/gaps from crawling competitors' sites |
| Rank tracking for arbitrary keywords/locations | Needs large-scale SERP collection (against search engines' terms without an API) | GSC average position for your own site; pluggable SERP providers for spot checks |
| Domain Rating / Domain Authority | Functions of proprietary link indexes | Not offered; internal PageRank is clearly labelled as internal |
| Google Business Profile management | API access is granted per project by Google | LocalBusiness markup checks, NAP consistency, citation list imports |
| Requesting indexing for any URL | The Indexing API is restricted to job-posting and livestream pages | Sitemap generation and validation; indexing status via Search Console data |
| Google Trends | No official API | Not integrated (unofficial clients break frequently) |

## 4. Ideas adopted, by source

See `GITHUB_REPOSITORY_ANALYSIS.md` for the per-repository notes. In summary:

- **Audit model** (rule catalogue, severity, explanation, fix, affected URLs, crawl comparison): seonaut, Sitebulb-style hints.
- **Crawler behaviour** (RFC 9309 robots, per-host throttling, retry with Retry-After, HEAD-then-GET link checks, unverifiable statuses): Scrapy, google/robotstxt, lychee, linkinator, crawlseo.
- **Sitemap handling** (discovery order, index trees, gzip/text, 50k split): ultimate-sitemap-parser (concepts), sitemaps.org protocol.
- **SQLite-first, single-process deployment**: Uptime Kuma, SerpBear.
- **Content optimisation against ranking pages**: contentswift (concept), Surfer-style term comparison.
- **Keyword techniques** (multi-source suggestions, SERP-overlap clustering, GSC cannibalisation): practitioner scripts, re-implemented.
- **Honest outbound-service documentation**: crawlseo.
- **Optional local AI**: Ollama.
