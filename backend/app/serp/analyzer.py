"""SERP providers and analysis.

Only sources that permit programmatic access are supported: a self-hosted SearXNG instance, the
Google Programmable Search JSON API, the Brave Search API, or URLs supplied manually by the user.
Search-result pages of Google/Bing are never scraped directly.
"""
from __future__ import annotations

import asyncio
from collections import Counter
from urllib.parse import urlsplit

import httpx

from ..audit.schema_validator import all_types
from ..crawler.fetcher import Fetcher
from ..crawler.parser import parse_html
from ..crawler.urls import normalize_url, registrable_domain
from ..keywords.research import classify_intent
from ..text import content_tokens, is_question, stem, tfidf_terms

PROVIDERS = {
    "none": "No provider configured (paste result URLs manually)",
    "searxng": "SearXNG (self-hosted metasearch, free)",
    "google_cse": "Google Programmable Search JSON API (100 free queries/day)",
    "brave": "Brave Search API (free tier available)",
}
AUTHORITY_DOMAINS = {
    "wikipedia.org", "youtube.com", "amazon.com", "reddit.com", "quora.com", "linkedin.com", "facebook.com",
    "instagram.com", "pinterest.com", "x.com", "twitter.com", "medium.com", "forbes.com", "nytimes.com", "bbc.com",
    "bbc.co.uk", "cnn.com", "theguardian.com", "apple.com", "microsoft.com", "google.com", "github.com",
    "stackoverflow.com", "imdb.com", "tripadvisor.com", "yelp.com", "ebay.com", "walmart.com", "etsy.com",
    "healthline.com", "webmd.com", "mayoclinic.org", "nih.gov", "britannica.com", "investopedia.com", "indeed.com",
    "glassdoor.com", "booking.com", "alibaba.com", "indiamart.com", "flipkart.com",
}


class SerpError(RuntimeError):
    pass


async def search(settings: dict, keyword: str, country: str = "us", lang: str = "en", num: int = 10) -> dict:
    """Query the configured provider. Returns {provider, results:[{position,url,title,snippet}], features}."""
    provider = settings.get("provider", "none")
    async with httpx.AsyncClient(timeout=20) as client:
        try:
            if provider == "searxng":
                base = (settings.get("searxng_url") or "").rstrip("/")
                if not base:
                    raise SerpError("SearXNG URL is not configured")
                r = await client.get(f"{base}/search", params={"q": keyword, "format": "json", "language": f"{lang}-{country.upper()}"})
                r.raise_for_status()
                data = r.json()
                items = [{"url": i.get("url"), "title": i.get("title"), "snippet": i.get("content")} for i in data.get("results", [])]
                features = [f for f, k in (("answer box", "answers"), ("knowledge panel", "infoboxes"), ("related searches", "suggestions")) if data.get(k)]
            elif provider == "google_cse":
                if not settings.get("google_cse_key") or not settings.get("google_cse_cx"):
                    raise SerpError("Google Programmable Search key and engine ID (cx) are required")
                r = await client.get("https://www.googleapis.com/customsearch/v1", params={
                    "key": settings["google_cse_key"], "cx": settings["google_cse_cx"], "q": keyword,
                    "gl": country, "hl": lang, "num": min(num, 10)})
                r.raise_for_status()
                data = r.json()
                items = [{"url": i.get("link"), "title": i.get("title"), "snippet": i.get("snippet")} for i in data.get("items", [])]
                features = ["spelling suggestion"] if data.get("spelling") else []
            elif provider == "brave":
                if not settings.get("brave_key"):
                    raise SerpError("Brave Search API key is required")
                r = await client.get("https://api.search.brave.com/res/v1/web/search",
                                     params={"q": keyword, "country": country, "search_lang": lang, "count": min(num, 20)},
                                     headers={"X-Subscription-Token": settings["brave_key"], "Accept": "application/json"})
                r.raise_for_status()
                data = r.json()
                items = [{"url": i.get("url"), "title": i.get("title"), "snippet": i.get("description")}
                         for i in (data.get("web") or {}).get("results", [])]
                features = [name for name, key in (("FAQ", "faq"), ("knowledge panel", "infobox"), ("videos", "videos"),
                                                   ("news", "news"), ("discussions", "discussions"), ("local pack", "locations")) if data.get(key)]
            else:
                raise SerpError("No SERP provider is configured. Add one in Settings or paste result URLs manually.")
        except httpx.HTTPStatusError as exc:
            raise SerpError(f"{PROVIDERS.get(provider, provider)} answered HTTP {exc.response.status_code}") from exc
        except httpx.HTTPError as exc:
            raise SerpError(f"Could not reach {PROVIDERS.get(provider, provider)}: {exc}") from exc
    results = []
    for item in items:
        url = normalize_url(item.get("url") or "")
        if url and len(results) < num:
            results.append({"position": len(results) + 1, "url": url, "title": item.get("title") or "", "snippet": item.get("snippet") or ""})
    return {"provider": provider, "results": results, "features": features,
            "note": "Positions reflect this provider's ordering, which can differ from what a user sees on Google."}


async def fetch_pages(urls: list[str], limit: int = 10) -> dict[str, dict]:
    """Fetch and parse result pages through the SSRF-safe fetcher."""
    out: dict[str, dict] = {}
    async with Fetcher(timeout_s=15, retries=1, delay_s=0.2, concurrency=5) as fetcher:
        async def one(url: str) -> None:
            res = await fetcher.fetch_following(url, max_body=3_000_000)
            if res.status == 200 and res.is_html:
                p = await asyncio.to_thread(parse_html, res.body, res.final_url or url, res.headers.get("content-type", ""))
                out[url] = {"status": 200, "title": p.title, "meta_description": p.meta_description, "word_count": p.word_count,
                            "headings": p.headings[:80], "text": p.text[:30000], "schema_types": all_types(p.jsonld),
                            "images": len(p.images), "internal_links": sum(1 for lk in p.links if urlsplit(lk["url"]).hostname == urlsplit(url).hostname),
                            "external_links": sum(1 for lk in p.links if urlsplit(lk["url"]).hostname != urlsplit(url).hostname)}
            else:
                out[url] = {"status": res.status, "error": res.error or f"HTTP {res.status}"}
        await asyncio.gather(*(one(u) for u in urls[:limit]))
    return out


def estimate_difficulty(keyword: str, results: list[dict], pages: dict[str, dict]) -> dict:
    """Transparent 0-100 difficulty *estimate* from observable SERP traits. It is not a link-based metric and
    is not comparable to Ahrefs KD or Semrush KD."""
    if not results:
        return {"score": None, "status": "unavailable", "reason": "No SERP data"}
    top = results[:10]
    kw = {stem(t) for t in content_tokens(keyword)}
    authority = sum(1 for r in top if registrable_domain(urlsplit(r["url"]).hostname or "") in AUTHORITY_DOMAINS
                    or (urlsplit(r["url"]).hostname or "").endswith((".gov", ".edu")))
    homepages = sum(1 for r in top if urlsplit(r["url"]).path in ("", "/"))
    exact_titles = sum(1 for r in top if kw and kw <= {stem(t) for t in content_tokens(r["title"])})
    lengths = [p["word_count"] for u, p in pages.items() if p.get("status") == 200 and p.get("word_count")]
    avg_words = sum(lengths) / len(lengths) if lengths else None
    n = len(top)
    components = {
        "authority_domains": round(40 * authority / n, 1),
        "homepage_results": round(15 * homepages / n, 1),
        "optimised_titles": round(25 * exact_titles / n, 1),
        "content_depth": round(min(20.0, 20 * (avg_words or 0) / 2500), 1) if avg_words else 0.0,
    }
    score = round(sum(components.values()))
    return {"score": score, "status": "estimated", "label": "hard" if score >= 60 else "medium" if score >= 35 else "easier",
            "components": components,
            "inputs": {"authority_domains": authority, "homepage_results": homepages, "titles_matching_keyword": exact_titles,
                       "avg_word_count": round(avg_words) if avg_words else None, "results_considered": n},
            "method": "Heuristic from SERP composition; no backlink data is used."}


def analyse(keyword: str, results: list[dict], pages: dict[str, dict], features: list[str] | None = None,
            my_url: str | None = None) -> dict:
    """Summarise what the ranking pages have in common and where the user's page falls short."""
    ok = {u: p for u, p in pages.items() if p.get("status") == 200}
    competitor_pages = {u: p for u, p in ok.items() if u != my_url}
    rows = []
    for r in results:
        p = pages.get(r["url"], {})
        title = p.get("title") or r["title"]
        rows.append({**r, "domain": urlsplit(r["url"]).hostname, "fetched": p.get("status") == 200, "error": p.get("error"),
                     "title": title, "title_length": len(title or ""), "meta_description": p.get("meta_description") or r.get("snippet"),
                     "word_count": p.get("word_count"), "h1": next((h["text"] for h in p.get("headings", []) if h["level"] == 1), None),
                     "h2_count": sum(1 for h in p.get("headings", []) if h["level"] == 2),
                     "schema_types": p.get("schema_types", []), "images": p.get("images"),
                     "is_homepage": urlsplit(r["url"]).path in ("", "/")})
    counts = [p["word_count"] for p in competitor_pages.values() if p.get("word_count")]
    heading_docs = [" . ".join(h["text"] for h in p.get("headings", []) if h["level"] in (2, 3)) for p in competitor_pages.values()]
    heading_topics = tfidf_terms(heading_docs, limit=25)
    body_terms = tfidf_terms([p.get("text", "") for p in competitor_pages.values()], limit=40)
    title_terms = Counter(t for r in results for t in set(content_tokens(r["title"])))
    questions = list(dict.fromkeys(h["text"] for p in competitor_pages.values() for h in p.get("headings", [])
                                   if is_question(h["text"]) and 15 < len(h["text"]) < 140))[:20]
    schema = Counter(t for p in competitor_pages.values() for t in p.get("schema_types", []))
    intent = classify_intent(keyword)
    domain_kinds = Counter()
    for r in results:
        host = urlsplit(r["url"]).hostname or ""
        path = urlsplit(r["url"]).path.lower()
        if any(s in path for s in ("/product", "/shop", "/buy", "/p/", "/store")):
            domain_kinds["product/category pages"] += 1
        elif any(s in path for s in ("/blog", "/guide", "/how-to", "/article", "/wiki", "/learn")) or "wikipedia" in host:
            domain_kinds["articles/guides"] += 1
        elif path in ("", "/"):
            domain_kinds["homepages"] += 1
        else:
            domain_kinds["other pages"] += 1
    gaps = None
    if my_url and my_url in ok:
        mine = ok[my_url]
        my_text = " ".join(content_tokens(mine.get("text", "")))
        my_headings = " ".join(content_tokens(" ".join(h["text"] for h in mine.get("headings", []))))
        gaps = {
            "missing_terms": [t for t in body_terms if t["share"] >= 0.4 and t["term"] not in my_text][:20],
            "missing_heading_topics": [t for t in heading_topics if t["term"] not in my_headings][:15],
            "word_count": mine.get("word_count"), "median_competitor_words": sorted(counts)[len(counts) // 2] if counts else None,
            "missing_schema_types": [t for t, c in schema.items() if c >= 2 and t not in mine.get("schema_types", [])],
        }
    return {
        "keyword": keyword, "intent": intent, "features": features or [], "results": rows,
        "result_types": dict(domain_kinds),
        "summary": {
            "pages_analysed": len(competitor_pages),
            "avg_word_count": round(sum(counts) / len(counts)) if counts else None,
            "median_word_count": sorted(counts)[len(counts) // 2] if counts else None,
            "avg_title_length": round(sum(len(r["title"]) for r in results) / len(results)) if results else None,
            "common_title_terms": [{"term": t, "results": c} for t, c in title_terms.most_common(12) if c > 1],
            "schema_types": dict(schema.most_common(12)),
        },
        "heading_topics": heading_topics, "common_terms": body_terms, "questions": questions,
        "content_gaps": gaps,
        "difficulty": estimate_difficulty(keyword, results, pages),
    }
