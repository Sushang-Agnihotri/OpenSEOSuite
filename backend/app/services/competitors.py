"""Competitor comparison built from crawls of the user's site and of each competitor (all values measured
by our own crawler unless labelled as estimates)."""
from __future__ import annotations

from collections import Counter

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import Competitor, Crawl, Page, Site
from ..text import term_counts


def latest_crawl(db: Session, site_id: int, competitor_id: int | None = None) -> Crawl | None:
    q = select(Crawl).where(Crawl.site_id == site_id, Crawl.status == "completed")
    q = q.where(Crawl.competitor_id == competitor_id) if competitor_id else q.where(Crawl.competitor_id.is_(None))
    return db.scalar(q.order_by(Crawl.id.desc()))


def crawl_profile(db: Session, crawl: Crawl) -> dict:
    """Measured facts about one crawl plus a term profile (document frequency of terms in titles and H1s)."""
    rows = db.execute(select(Page.url, Page.title, Page.h1, Page.meta_description, Page.word_count, Page.inlinks, Page.outlinks,
                             Page.depth, Page.pagerank, Page.data)
                      .where(Page.crawl_id == crawl.id, Page.indexable.is_(True)).limit(5000)).all()
    terms: Counter = Counter()
    page_terms = []
    h2_total = img_total = 0
    for url, title, h1, _desc, _wc, _in, _out, _depth, pr, data in rows:
        tc = set(term_counts(f"{title or ''} . {h1 or ''}", max_n=2))
        terms.update(tc)
        page_terms.append((url, title, pr, tc))
        heads = (data or {}).get("headings") or []
        h2_total += sum(1 for h in heads if h.get("level") == 2)
        img_total += len((data or {}).get("images") or [])
    n = len(rows)
    stats = crawl.stats or {}
    titles = [len(r[1]) for r in rows if r[1]]
    descs = [len(r[3]) for r in rows if r[3]]
    return {
        "crawl_id": crawl.id, "crawled_at": crawl.finished_at.isoformat() if crawl.finished_at else None,
        "score": crawl.score, "urls_crawled": stats.get("total_urls", crawl.pages_crawled), "limit_reached": stats.get("limit_reached", False),
        "indexable_pages": n, "sitemap_urls": (stats.get("sitemap") or {}).get("url_count", 0),
        "sitemap_files": len((stats.get("sitemap") or {}).get("files", [])),
        "avg_word_count": round(sum(r[4] for r in rows) / n) if n else 0,
        "avg_title_length": round(sum(titles) / len(titles)) if titles else 0,
        "avg_description_length": round(sum(descs) / len(descs)) if descs else 0,
        "pages_missing_description": sum(1 for r in rows if not r[3]),
        "avg_internal_links_out": round(sum(r[6] for r in rows) / n, 1) if n else 0,
        "avg_inlinks": round(sum(r[5] for r in rows) / n, 1) if n else 0,
        "avg_depth": round(sum(r[7] for r in rows if r[7] is not None) / max(1, sum(1 for r in rows if r[7] is not None)), 1),
        "avg_h2_per_page": round(h2_total / n, 1) if n else 0, "avg_images_per_page": round(img_total / n, 1) if n else 0,
        "issues_by_severity": stats.get("issues_by_severity", {}),
        "schema_types": (stats.get("schema") or {}).get("types", {}),
        "avg_response_ms": stats.get("avg_response_ms"),
        "_terms": terms, "_page_terms": page_terms,
    }


def compare(db: Session, site: Site) -> dict:
    own_crawl = latest_crawl(db, site.id)
    competitors = db.scalars(select(Competitor).where(Competitor.site_id == site.id).order_by(Competitor.id)).all()
    own = crawl_profile(db, own_crawl) if own_crawl else None
    own_terms: Counter = own["_terms"] if own else Counter()
    out_comp = []
    for c in competitors:
        crawl = latest_crawl(db, site.id, c.id)
        running = db.scalar(select(func.count()).select_from(Crawl).where(Crawl.competitor_id == c.id, Crawl.status.in_(("queued", "running"))))
        entry = {"id": c.id, "name": c.name, "url": c.url, "domain": c.domain, "crawl_running": bool(running), "profile": None}
        if crawl:
            prof = crawl_profile(db, crawl)
            their: Counter = prof.pop("_terms")
            pages = prof.pop("_page_terms")
            if own:
                shared = [t for t in their if t in own_terms]
                gaps = sorted(((t, df) for t, df in their.items() if t not in own_terms and df >= 2), key=lambda x: (-x[1], x[0]))
                unique = sorted(((t, df) for t, df in own_terms.items() if t not in their and df >= 2), key=lambda x: -x[1])
                union = len(set(their) | set(own_terms))
                opportunities = []
                for url, title, pr, tc in sorted(pages, key=lambda p: -(p[2] or 0)):
                    missing = [t for t in tc if " " in t and t not in own_terms]
                    if missing and title:
                        opportunities.append({"url": url, "title": title, "internal_pagerank": pr, "topics_you_lack": missing[:5]})
                    if len(opportunities) >= 25:
                        break
                prof["keyword_overlap"] = {
                    "shared_terms": len(shared), "overlap_share": round(len(shared) / union, 3) if union else 0,
                    "top_shared": sorted(shared, key=lambda t: -(their[t] + own_terms[t]))[:30],
                    "gaps": [{"term": t, "competitor_pages": df} for t, df in gaps[:60]],
                    "your_unique_terms": [{"term": t, "your_pages": df} for t, df in unique[:30]],
                    "method": "Terms from page titles and H1 headings of crawled indexable pages (measured). "
                              "Shows topical overlap, not ranking keywords.",
                }
                prof["content_opportunities"] = opportunities
            entry["profile"] = prof
        out_comp.append(entry)
    if own:
        own.pop("_terms"), own.pop("_page_terms")
    return {
        "site": {"id": site.id, "name": site.name, "url": site.url, "profile": own},
        "competitors": out_comp,
        "notes": [
            "All figures come from this toolkit's own crawls and are limited by each crawl's URL cap.",
            "Indexed-page counts are not verifiable without search-engine data; sitemap size and indexable crawled pages are shown instead.",
            "Ranking keywords, traffic and backlink totals of competitors are not available without proprietary datasets.",
        ],
    }
