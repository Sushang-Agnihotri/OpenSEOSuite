"""Keyword research: suggestions from public autocomplete endpoints, intent classification, clustering,
keyword-to-page mapping and cannibalisation detection.

Data honesty: autocomplete endpoints return *suggestions only*. This module never produces search
volume, CPC or competition figures; those come solely from Search Console (measured) or from files
the user imports (e.g. a Google Ads Keyword Planner export).
"""
from __future__ import annotations

import asyncio
import json
import string
from collections import Counter, defaultdict

import httpx

from ..text import QUESTION_WORDS, STOPWORDS, content_tokens, stem, tokens

SOURCES = {
    "google": "Google Autocomplete (public suggestion endpoint, unofficial)",
    "bing": "Bing Autosuggest (public OpenSearch endpoint)",
    "duckduckgo": "DuckDuckGo autocomplete",
}
PREPOSITIONS = ("for", "with", "without", "vs", "versus", "near", "to", "like", "and", "or", "in", "on")
COMPARISONS = ("vs", "versus", "or", "alternative", "alternatives", "compared", "comparison", "like")

INTENT_SIGNALS = {
    "transactional": ("buy", "price", "prices", "pricing", "cheap", "cheapest", "discount", "coupon", "deal", "deals",
                      "order", "purchase", "for sale", "shop", "hire", "book", "booking", "quote", "subscribe",
                      "subscription", "download", "free trial", "cost", "rent", "supplier", "suppliers", "wholesale",
                      "manufacturer", "manufacturers", "exporter", "exporters", "delivery"),
    "commercial": ("best", "top", "review", "reviews", "vs", "versus", "compare", "comparison", "alternative",
                   "alternatives", "rated", "worth it", "pros and cons"),
    "navigational": ("login", "log in", "sign in", "signin", "website", "official", "homepage", "contact", "phone number",
                     "customer service", "app", "portal", "account", "dashboard"),
    "local": ("near me", "nearby", "open now", "closest", "directions", "in my area"),
    "informational": ("how", "what", "why", "when", "where", "who", "which", "guide", "tutorial", "tips", "ideas", "examples",
                      "example", "meaning", "definition", "learn", "benefits", "uses", "types", "history", "difference",
                      "can", "does", "is", "are", "should", "explained", "template", "checklist"),
}
_PRIORITY = ("local", "transactional", "commercial", "navigational", "informational")


def classify_intent(keyword: str) -> dict:
    """Rule-based search-intent estimate. Returns intent, matched signals and a rough confidence."""
    kw = " " + " ".join(tokens(keyword)) + " "
    hits: dict[str, list[str]] = {}
    for intent, signals in INTENT_SIGNALS.items():
        found = [s for s in signals if f" {s} " in kw]
        if found:
            hits[intent] = found
    if not hits:
        return {"intent": "informational", "signals": [], "confidence": 0.3, "method": "rule-based estimate (default)"}
    best = max(_PRIORITY, key=lambda i: (len(hits.get(i, [])), -_PRIORITY.index(i)))
    conf = min(0.95, 0.55 + 0.15 * len(hits[best]) - 0.1 * (len(hits) - 1))
    return {"intent": best, "signals": hits[best], "confidence": round(max(conf, 0.35), 2), "method": "rule-based estimate"}


def keyword_type(keyword: str, seed: str) -> str:
    toks = tokens(keyword)
    if not toks:
        return "suggestion"
    if toks[0] in QUESTION_WORDS:
        return "question"
    if any(t in COMPARISONS for t in toks):
        return "comparison"
    if any(t in PREPOSITIONS for t in toks):
        return "preposition"
    return "long-tail" if len(toks) >= 4 else "suggestion"


async def _google(client: httpx.AsyncClient, q: str, lang: str, country: str) -> list[str]:
    r = await client.get("https://suggestqueries.google.com/complete/search",
                         params={"client": "firefox", "q": q, "hl": lang, "gl": country})
    data = json.loads(r.content.decode(r.encoding or "utf-8", "replace"))
    return [s for s in data[1] if isinstance(s, str)]


async def _bing(client: httpx.AsyncClient, q: str, lang: str, country: str) -> list[str]:
    r = await client.get("https://api.bing.com/osjson.aspx", params={"query": q, "market": f"{lang}-{country.upper()}"})
    return [s for s in r.json()[1] if isinstance(s, str)]


async def _ddg(client: httpx.AsyncClient, q: str, lang: str, country: str) -> list[str]:
    r = await client.get("https://duckduckgo.com/ac/", params={"q": q, "type": "list", "kl": f"{country.lower()}-{lang}"})
    data = r.json()
    return [s for s in data[1] if isinstance(s, str)] if isinstance(data, list) and len(data) > 1 else []


_FETCHERS = {"google": _google, "bing": _bing, "duckduckgo": _ddg}


def expansion_queries(seed: str, depth: str) -> list[str]:
    seed = seed.strip()
    queries = [seed, f"{seed} "]
    queries += [f"{w} {seed}" for w in ("how", "what", "why", "when", "where", "which", "can", "is", "are", "best")]
    queries += [f"{seed} {p} " for p in ("for", "vs", "with", "without", "near", "like", "or")]
    if depth == "deep":
        queries += [f"{seed} {c}" for c in string.ascii_lowercase]
        queries += [f"{w} {seed}" for w in ("who", "does", "will", "should", "do")]
    return list(dict.fromkeys(queries))


async def suggest(seed: str, lang: str = "en", country: str = "us", sources: list[str] | None = None,
                  depth: str = "basic", client: httpx.AsyncClient | None = None) -> dict:
    """Collect keyword suggestions. Returns {keywords: [...], errors: {source: message}, queries: n}."""
    sources = [s for s in (sources or ["google", "bing", "duckduckgo"]) if s in _FETCHERS]
    queries = expansion_queries(seed, depth)
    found: dict[str, set[str]] = defaultdict(set)
    errors: dict[str, str] = {}
    own = client is None
    client = client or httpx.AsyncClient(timeout=10, headers={"User-Agent": "Mozilla/5.0 (compatible; UltimateSEOToolkit)"})
    sem = asyncio.Semaphore(4)

    async def one(source: str, q: str) -> None:
        if source in errors:
            return
        async with sem:
            try:
                for s in await _FETCHERS[source](client, q, lang, country):
                    s = " ".join(s.lower().split())
                    if s and len(s) <= 120:
                        found[s].add(source)
                await asyncio.sleep(0.12)
            except Exception as exc:  # noqa: BLE001 - a failing source must not break the others
                errors[source] = f"{type(exc).__name__}: {str(exc)[:160]}"

    try:
        await asyncio.gather(*(one(s, q) for s in sources for q in queries))
    finally:
        if own:
            await client.aclose()
    seed_norm = " ".join(seed.lower().split())
    rows = []
    for kw, srcs in found.items():
        if kw == seed_norm:
            continue
        intent = classify_intent(kw)
        rows.append({"keyword": kw, "sources": sorted(srcs), "source_count": len(srcs), "type": keyword_type(kw, seed_norm),
                     "words": len(kw.split()), "intent": intent["intent"], "intent_confidence": intent["confidence"],
                     "search_volume": None, "volume_status": "unavailable"})
    rows.sort(key=lambda r: (-r["source_count"], r["words"], r["keyword"]))
    return {"seed": seed_norm, "keywords": rows, "errors": errors, "queries": len(queries) * len(sources),
            "sources": {s: SOURCES[s] for s in sources}}


# --------------------------------------------------------------------------- clustering
def _signature(keyword: str) -> frozenset[str]:
    return frozenset(stem(t) for t in content_tokens(keyword))


def cluster_keywords(keywords: list[str], threshold: float = 0.5, seed: str | None = None) -> list[dict]:
    """Lexical clustering: keywords whose stemmed content-word sets have Jaccard similarity >= threshold are
    merged (single linkage). Words from the seed are ignored so clusters reflect the *modifiers*."""
    kws = list(dict.fromkeys(k.strip().lower() for k in keywords if k and k.strip()))[:3000]
    seed_sig = _signature(seed) if seed else frozenset()
    sigs = [(_signature(k) - seed_sig) or _signature(k) for k in kws]
    parent = list(range(len(kws)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    by_token: dict[str, list[int]] = defaultdict(list)
    for i, sig in enumerate(sigs):
        for t in sig:
            by_token[t].append(i)
    for members in by_token.values():
        for a_pos, a in enumerate(members[:400]):
            for b in members[a_pos + 1 : 400]:
                if find(a) == find(b):
                    continue
                inter = len(sigs[a] & sigs[b])
                if inter / len(sigs[a] | sigs[b]) >= threshold:
                    parent[find(a)] = find(b)
    groups: dict[int, list[int]] = defaultdict(list)
    for i in range(len(kws)):
        groups[find(i)].append(i)
    clusters = []
    for members in groups.values():
        counts = Counter(t for i in members for t in sigs[i])
        label_tokens = [t for t, _ in counts.most_common(2)]
        # prefer the shortest member keyword containing the top token as a readable label
        top = label_tokens[0] if label_tokens else ""
        candidates = [kws[i] for i in members if top and top in " ".join(stem(t) for t in tokens(kws[i]))]
        label = min(candidates or [kws[members[0]]], key=len)
        intents = Counter(classify_intent(kws[i])["intent"] for i in members)
        clusters.append({"label": label, "size": len(members), "keywords": [kws[i] for i in members],
                         "dominant_intent": intents.most_common(1)[0][0], "shared_terms": label_tokens})
    clusters.sort(key=lambda c: (-c["size"], c["label"]))
    return clusters


def cluster_by_serp(serp_urls: dict[str, list[str]], min_overlap: int = 3) -> list[dict]:
    """SERP-overlap clustering: keywords whose top results share >= min_overlap URLs target the same page."""
    kws = list(serp_urls)
    sets = [set(serp_urls[k][:10]) for k in kws]
    parent = list(range(len(kws)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for a in range(len(kws)):
        for b in range(a + 1, len(kws)):
            if len(sets[a] & sets[b]) >= min_overlap:
                parent[find(a)] = find(b)
    groups: dict[int, list[str]] = defaultdict(list)
    for i, k in enumerate(kws):
        groups[find(i)].append(k)
    return sorted(({"label": min(g, key=len), "size": len(g), "keywords": g} for g in groups.values()), key=lambda c: -c["size"])


# --------------------------------------------------------------------------- mapping / cannibalisation
def page_relevance(keyword: str, page: dict) -> float:
    """Score how strongly a page targets a keyword using title, H1, URL, description and body text."""
    kw_tokens = [stem(t) for t in content_tokens(keyword)] or [stem(t) for t in tokens(keyword)]
    if not kw_tokens:
        return 0.0

    def coverage(text: str) -> float:
        have = {stem(t) for t in tokens(text or "")}
        return sum(1 for t in kw_tokens if t in have) / len(kw_tokens)

    phrase = " ".join(tokens(keyword))
    title, h1 = page.get("title") or "", page.get("h1") or ""
    score = 3.0 * coverage(title) + 2.0 * coverage(h1) + 1.5 * coverage((page.get("url") or "").replace("-", " ").replace("/", " "))
    score += 1.0 * coverage(page.get("meta_description") or "")
    body = " ".join(tokens(page.get("text") or ""))[:20000]
    if body:
        score += 1.5 * coverage(body)
        occurrences = body.count(phrase)
        score += min(1.0, occurrences / 3)
    if phrase and phrase in " ".join(tokens(title)):
        score += 1.0
    return round(score, 2)


def map_keywords(keywords: list[str], pages: list[dict], min_score: float = 3.0) -> list[dict]:
    """For each keyword return the best-matching page and competing pages (cannibalisation risk)."""
    out = []
    for kw in keywords:
        scored = sorted(((page_relevance(kw, p), p) for p in pages), key=lambda x: -x[0])[:5]
        scored = [(s, p) for s, p in scored if s > 0]
        best = scored[0] if scored and scored[0][0] >= min_score else None
        competing = [{"url": p["url"], "title": p.get("title"), "score": s} for s, p in scored[1:]
                     if best and s >= max(min_score, 0.85 * best[0])]
        out.append({
            "keyword": kw,
            "best_page": {"url": best[1]["url"], "title": best[1].get("title"), "score": best[0]} if best else None,
            "status": "cannibalisation risk" if competing else "mapped" if best else "no matching page",
            "competing_pages": competing,
            "method": "on-page relevance estimate",
        })
    return out


def remove_stopwords(keyword: str) -> str:
    return " ".join(t for t in tokens(keyword) if t not in STOPWORDS)
