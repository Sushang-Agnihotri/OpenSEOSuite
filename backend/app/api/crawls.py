"""Crawls, pages, issues, links, architecture, sitemaps, structured data, hreflang, local SEO and exports."""
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, case, delete, func, or_, select
from sqlalchemy.orm import Session

from ..audit.hreflang import locale_from_path
from ..audit.rules import RULES, SEVERITIES, rule_dict
from ..audit.schema_validator import LOCAL_TYPES, all_types, recommend_types, validate_jsonld
from ..crawler.engine import CrawlConfig
from ..crawler.sitemaps import generate_sitemap
from ..db import get_db
from ..jobs import jobs
from ..models import Citation, Crawl, Issue, Link, Page, Site, User
from ..reports.exports import audit_pdf, to_csv, to_xlsx
from ..security.auth import current_user, get_site_for
from ..text import content_tokens, is_question, stem
from .deps import download, get_crawl_for, page_params
from .sites import crawl_out, start_crawl

router = APIRouter(tags=["crawls"])
_SEV_ORDER = case({s: i for i, s in enumerate(SEVERITIES)}, value=Issue.severity)
PAGE_SORTS = {"url": Page.url, "status": Page.status_code, "depth": Page.depth, "inlinks": Page.inlinks, "words": Page.word_count,
              "pagerank": Page.pagerank, "score": Page.score, "issues": Page.issue_count, "response": Page.response_ms,
              "size": Page.size_bytes, "title": Page.title}


# Same definition of "broken" as the audit (audit/analysis.py): internal links to any error; external links to hard
# errors only (401/403/405/406/429/999, timeouts and blocked requests are unverifiable rather than broken).
_BROKEN_LINK = or_(
    and_(Link.target_status >= 400, or_(Link.is_internal.is_(True), Link.target_status.notin_((401, 403, 405, 406, 429, 999)))),
    and_(Link.target_status.is_(None), Link.target_error.isnot(None),
         or_(Link.is_internal.is_(True), and_(Link.target_error != "timeout", Link.target_error.notlike("blocked%")))),
)


def page_row(p: Page) -> dict:
    return {"id": p.id, "url": p.url, "status_code": p.status_code, "error": p.error, "content_type": p.content_type, "is_html": p.is_html,
            "redirect_to": p.redirect_to, "depth": p.depth, "found_via": p.found_via, "blocked_by_robots": p.blocked_by_robots,
            "in_sitemap": p.in_sitemap, "indexable": p.indexable, "indexability_reason": p.indexability_reason, "title": p.title,
            "meta_description": p.meta_description, "h1": p.h1, "canonical": p.canonical, "meta_robots": p.meta_robots, "lang": p.lang,
            "word_count": p.word_count, "size_bytes": p.size_bytes, "response_ms": p.response_ms, "inlinks": p.inlinks,
            "outlinks": p.outlinks, "external_outlinks": p.external_outlinks, "pagerank": p.pagerank, "score": p.score,
            "issue_count": p.issue_count}


# ----------------------------------------------------------------------------- crawl lifecycle
@router.post("/sites/{site_id}/crawls", status_code=202)
async def create_crawl(site_id: int, config: CrawlConfig | None = None, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    site = get_site_for(db, user, site_id)
    cfg = config or CrawlConfig(**(site.crawl_config or {}))
    return crawl_out(start_crawl(db, site, user, cfg))


@router.get("/sites/{site_id}/crawls")
def list_crawls(site_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)) -> list[dict]:
    site = get_site_for(db, user, site_id)
    return [crawl_out(c) for c in db.scalars(select(Crawl).where(Crawl.site_id == site.id, Crawl.competitor_id.is_(None)).order_by(Crawl.id.desc()).limit(100))]


@router.get("/crawls/{crawl_id}")
def get_crawl(crawl_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    crawl = get_crawl_for(db, user, crawl_id)
    out = crawl_out(crawl, with_stats=True)
    if crawl.job_id:
        from ..models import Job
        job = db.get(Job, crawl.job_id)
        if job:
            out["job"] = {"id": job.id, "status": job.status, "progress": job.progress, "message": job.message}
    return out


@router.post("/crawls/{crawl_id}/cancel")
def cancel_crawl(crawl_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    crawl = get_crawl_for(db, user, crawl_id)
    return {"cancelled": bool(crawl.job_id and jobs.cancel(crawl.job_id))}


@router.delete("/crawls/{crawl_id}", status_code=204)
def delete_crawl(crawl_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)) -> None:
    crawl = get_crawl_for(db, user, crawl_id)
    if crawl.status in ("queued", "running"):
        raise HTTPException(409, "Cancel the crawl before deleting it")
    for model in (Issue, Link, Page):
        db.execute(delete(model).where(model.crawl_id == crawl.id))
    db.delete(crawl)
    db.commit()


# ----------------------------------------------------------------------------- pages
def _page_query(crawl_id: int, q: str | None, status: str | None, indexable: str | None, kind: str | None, rule: str | None):
    stmt = select(Page).where(Page.crawl_id == crawl_id)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(Page.url.ilike(like), Page.title.ilike(like)))
    if status:
        if status == "error":
            stmt = stmt.where(Page.status_code.is_(None), Page.blocked_by_robots.is_(False))
        elif status == "blocked":
            stmt = stmt.where(Page.blocked_by_robots.is_(True))
        elif re.fullmatch(r"[1-5]xx", status):
            base = int(status[0]) * 100
            stmt = stmt.where(Page.status_code >= base, Page.status_code < base + 100)
        elif status.isdigit():
            stmt = stmt.where(Page.status_code == int(status))
    if indexable in ("true", "false"):
        stmt = stmt.where(Page.is_html.is_(True), Page.indexable.is_(indexable == "true"))
    if kind == "html":
        stmt = stmt.where(Page.is_html.is_(True))
    elif kind == "other":
        stmt = stmt.where(Page.is_html.is_(False))
    if rule:
        stmt = stmt.where(Page.id.in_(select(Issue.page_id).where(Issue.crawl_id == crawl_id, Issue.rule_id == rule)))
    return stmt


@router.get("/crawls/{crawl_id}/pages")
def list_pages(crawl_id: int, q: str | None = Query(None, max_length=200), status: str | None = None, indexable: str | None = None,
               kind: str | None = None, rule: str | None = None, sort: str = "url", order: str = "asc", page: int = 1, per_page: int = 50,
               user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    crawl = get_crawl_for(db, user, crawl_id)
    stmt = _page_query(crawl.id, q, status, indexable, kind, rule)
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    col = PAGE_SORTS.get(sort, Page.url)
    offset, limit = page_params(page, per_page)
    rows = db.scalars(stmt.order_by(col.desc().nulls_last() if order == "desc" else col.asc().nulls_last(), Page.id).offset(offset).limit(limit)).all()
    return {"total": total, "page": page, "per_page": limit, "items": [page_row(p) for p in rows]}


@router.get("/crawls/{crawl_id}/pages/{page_id}")
def page_detail(crawl_id: int, page_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    crawl = get_crawl_for(db, user, crawl_id)
    p = db.get(Page, page_id)
    if p is None or p.crawl_id != crawl.id:
        raise HTTPException(404, "Page not found")
    issues = db.scalars(select(Issue).where(Issue.crawl_id == crawl.id, Issue.page_id == p.id).order_by(_SEV_ORDER)).all()
    inlinks = db.execute(select(Link.source_url, Link.anchor, Link.nofollow).where(Link.crawl_id == crawl.id, Link.target_url == p.url).limit(200)).all()
    outlinks = db.execute(select(Link.target_url, Link.anchor, Link.nofollow, Link.is_internal, Link.target_status, Link.target_error)
                          .where(Link.crawl_id == crawl.id, Link.source_page_id == p.id).limit(500)).all()
    data = dict(p.data or {})
    schema = validate_jsonld(data.get("jsonld") or [])
    q_heads = sum(1 for h in data.get("headings", []) if is_question(h.get("text", "")))
    return {
        **page_row(p), "data": data, "inlink_count": p.inlinks, "outlink_count": p.outlinks,
        "issues": [{**rule_dict(i.rule_id), "details": i.details} for i in issues],
        "inlinks": [{"url": u, "anchor": a, "nofollow": n} for u, a, n in inlinks],
        "outlinks": [{"url": u, "anchor": a, "nofollow": n, "internal": i, "status": s, "error": e} for u, a, n, i, s, e in outlinks],
        "schema": {**schema, "recommendations": recommend_types({"url": p.url, "depth": p.depth, "types": all_types(data.get("jsonld") or []), "question_headings": q_heads})},
    }


# ----------------------------------------------------------------------------- issues
@router.get("/crawls/{crawl_id}/issues")
def issue_summary(crawl_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    crawl = get_crawl_for(db, user, crawl_id)
    rows = db.execute(select(Issue.rule_id, func.count()).where(Issue.crawl_id == crawl.id).group_by(Issue.rule_id)).all()
    order = {s: i for i, s in enumerate(SEVERITIES)}
    groups = sorted(({**rule_dict(r), "count": c} for r, c in rows if r in RULES), key=lambda g: (order[g["severity"]], -g["count"]))
    return {"crawl": crawl_out(crawl), "groups": groups,
            "by_severity": {s: sum(g["count"] for g in groups if g["severity"] == s) for s in SEVERITIES},
            "by_category": {c: sum(g["count"] for g in groups if g["category"] == c) for c in sorted({g["category"] for g in groups})},
            "scoring": "Each page starts at 100 and loses 25/10/4/1 points per critical/high/medium/low rule that fires on it. "
                       "Site score = average page score minus 10/5/2/0.5 per site-wide critical/high/medium/low rule."}


@router.get("/crawls/{crawl_id}/issues/{rule_id}")
def issue_detail(crawl_id: int, rule_id: str, page: int = 1, per_page: int = 50, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    crawl = get_crawl_for(db, user, crawl_id)
    if rule_id not in RULES:
        raise HTTPException(404, "Unknown rule")
    offset, limit = page_params(page, per_page)
    base = select(Issue).where(Issue.crawl_id == crawl.id, Issue.rule_id == rule_id)
    total = db.scalar(select(func.count()).select_from(base.subquery()))
    rows = db.scalars(base.order_by(Issue.url).offset(offset).limit(limit)).all()
    return {"rule": rule_dict(rule_id), "total": total, "page": page, "per_page": limit,
            "items": [{"page_id": i.page_id, "url": i.url, "details": i.details} for i in rows]}


# ----------------------------------------------------------------------------- links / redirects / duplicates
@router.get("/crawls/{crawl_id}/links")
def list_links(crawl_id: int, kind: str = "broken", q: str | None = Query(None, max_length=200), page: int = 1, per_page: int = 50,
               user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    crawl = get_crawl_for(db, user, crawl_id)
    stmt = select(Link).where(Link.crawl_id == crawl.id)
    if kind == "broken":
        stmt = stmt.where(_BROKEN_LINK)
    elif kind == "internal":
        stmt = stmt.where(Link.is_internal.is_(True))
    elif kind == "external":
        stmt = stmt.where(Link.is_internal.is_(False))
    elif kind == "redirect":
        stmt = stmt.where(Link.target_status >= 300, Link.target_status < 400)
    elif kind == "nofollow":
        stmt = stmt.where(Link.nofollow.is_(True))
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(Link.source_url.ilike(like), Link.target_url.ilike(like), Link.anchor.ilike(like)))
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    offset, limit = page_params(page, per_page)
    rows = db.scalars(stmt.order_by(Link.target_url, Link.id).offset(offset).limit(limit)).all()
    return {"total": total, "page": page, "per_page": limit,
            "items": [{"source_url": lk.source_url, "source_page_id": lk.source_page_id, "target_url": lk.target_url, "anchor": lk.anchor,
                       "nofollow": lk.nofollow, "internal": lk.is_internal, "status": lk.target_status, "error": lk.target_error} for lk in rows]}


@router.get("/crawls/{crawl_id}/redirects")
def redirects(crawl_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    items = _redirect_rows(db, get_crawl_for(db, user, crawl_id))
    return {"total": len(items), "items": items}


def _redirect_rows(db: Session, crawl: Crawl) -> list[dict]:
    rows = db.execute(select(Page.id, Page.url, Page.status_code, Page.redirect_to, Page.inlinks).where(Page.crawl_id == crawl.id, Page.redirect_to.isnot(None)).limit(5000)).all()
    target = {u: t for _, u, _, t, _ in rows}
    status = dict(db.execute(select(Page.url, Page.status_code).where(Page.crawl_id == crawl.id, Page.url.in_(list(set(target.values()))))).all()) if target else {}
    items = []
    for pid, url, code, to, inlinks in rows:
        chain, seen, cur, loop = [], {url}, to, False
        while cur and len(chain) < 15:
            chain.append(cur)
            if cur in seen:
                loop = True
                break
            seen.add(cur)
            cur = target.get(cur)
        items.append({"page_id": pid, "url": url, "status_code": code, "chain": chain, "hops": len(chain), "loop": loop,
                      "final_url": chain[-1] if chain else None, "final_status": status.get(chain[-1]) if chain else None, "inlinks": inlinks})
    items.sort(key=lambda r: (-int(r["loop"]), -r["hops"]))
    return items


@router.get("/crawls/{crawl_id}/duplicates")
def duplicates(crawl_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    crawl = get_crawl_for(db, user, crawl_id)
    out = {}
    for rule in ("duplicate_content", "near_duplicate_content", "title_duplicate", "description_duplicate", "h1_duplicate"):
        rows = db.execute(select(Issue.url, Issue.page_id, Issue.details).where(Issue.crawl_id == crawl.id, Issue.rule_id == rule).limit(2000)).all()
        groups: dict[frozenset, dict] = {}
        for url, _pid, details in rows:
            key = frozenset([url, *(details or {}).get("other_urls", [])])
            g = groups.setdefault(key, {"value": (details or {}).get("value"), "urls": sorted(key)})
            g["count"] = len(g["urls"])
        out[rule] = sorted(groups.values(), key=lambda g: -g["count"])[:200]
    return out


# ----------------------------------------------------------------------------- architecture / internal linking
@router.get("/crawls/{crawl_id}/internal-links")
def internal_links(crawl_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    crawl = get_crawl_for(db, user, crawl_id)
    base = select(Page).where(Page.crawl_id == crawl.id, Page.is_html.is_(True), Page.status_code == 200)
    top = db.scalars(base.order_by(Page.pagerank.desc()).limit(50)).all()
    weak = db.scalars(base.where(Page.indexable.is_(True)).order_by(Page.inlinks.asc(), Page.pagerank.asc()).limit(50)).all()
    orphans = db.scalars(select(Page).join(Issue, Issue.page_id == Page.id).where(Issue.crawl_id == crawl.id, Issue.rule_id == "orphan_page").limit(500)).all()
    bucket = case((Page.inlinks == 0, "0"), (Page.inlinks == 1, "1"), (Page.inlinks <= 5, "2-5"), (Page.inlinks <= 20, "6-20"), else_="21+")
    dist = db.execute(select(bucket, func.count()).where(Page.crawl_id == crawl.id, Page.is_html.is_(True), Page.status_code == 200).group_by(bucket)).all()
    anchors = db.execute(select(Link.anchor, func.count(), func.count(func.distinct(Link.target_url)))
                         .where(Link.crawl_id == crawl.id, Link.is_internal.is_(True), Link.anchor.isnot(None))
                         .group_by(Link.anchor).order_by(func.count().desc()).limit(100)).all()
    generic = {"click here", "here", "read more", "learn more", "more", "link", "this", "details", "view", "continue", "see more", "view more"}
    return {
        "top_pages": [page_row(p) for p in top], "weak_pages": [page_row(p) for p in weak], "orphans": [page_row(p) for p in orphans],
        "inlink_distribution": {k: v for k, v in dist},
        "depth_distribution": (crawl.stats or {}).get("depth_distribution", {}),
        "anchors": [{"anchor": a, "links": c, "targets": t, "generic": a.lower() in generic, "ambiguous": t > 3 and a.lower() not in generic} for a, c, t in anchors],
        "pagerank_note": "Internal PageRank approximates how link equity flows inside the site (average page = 1.0). "
                         "It is computed from crawled internal links only and is unrelated to any search engine's metric.",
    }


@router.get("/crawls/{crawl_id}/link-opportunities")
def link_opportunities(crawl_id: int, limit: int = 100, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    """Topic-based suggestions: page A mentions the topic of page B (B's title/H1 terms) but does not link to it."""
    crawl = get_crawl_for(db, user, crawl_id)
    pages = db.execute(select(Page.id, Page.url, Page.title, Page.h1, Page.inlinks, Page.pagerank)
                       .where(Page.crawl_id == crawl.id, Page.indexable.is_(True)).order_by(Page.pagerank.desc()).limit(1500)).all()
    targets = []
    df: Counter = Counter()
    for pid, url, title, h1, inlinks, _pr in pages:
        key = tuple(dict.fromkeys(stem(t) for t in content_tokens(h1 or title or "")))[:5]
        if len(key) >= 2:
            targets.append((pid, url, title or h1, key, inlinks))
            df.update(set(key))
    # ignore terms that appear in most page titles (brand names, boilerplate)
    common = {t for t, c in df.items() if c > max(3, 0.3 * len(targets))}
    targets = [(pid, url, label, tuple(k for k in key if k not in common), inl) for pid, url, label, key, inl in targets]
    targets = [t for t in targets if len(t[3]) >= 2]
    existing = defaultdict(set)
    for src, tgt in db.execute(select(Link.source_page_id, Link.target_url).where(Link.crawl_id == crawl.id, Link.is_internal.is_(True))):
        existing[src].add(tgt)
    suggestions = []
    sources = db.execute(select(Page.id, Page.url, Page.title, Page.text).where(Page.crawl_id == crawl.id, Page.indexable.is_(True))
                         .order_by(Page.pagerank.desc()).limit(600)).all()
    for sid, surl, stitle, text in sources:
        stems = {stem(t) for t in content_tokens((text or "")[:25000])}
        for tid, turl, label, key, inl in targets:
            if tid == sid or turl in existing[sid]:
                continue
            if all(k in stems for k in key):
                suggestions.append({"source_url": surl, "source_title": stitle, "target_url": turl, "target_title": label,
                                    "matched_terms": list(key), "target_inlinks": inl})
    suggestions.sort(key=lambda s: (s["target_inlinks"], -len(s["matched_terms"])))
    return {"total": len(suggestions), "items": suggestions[: max(1, min(limit, 500))],
            "method": "A source page is suggested when its body text contains every significant word of the target page's H1/title "
                      "and no link exists yet. Review each suggestion: lexical matching cannot judge context."}


@router.get("/crawls/{crawl_id}/graph")
def link_graph(crawl_id: int, limit: int = 150, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    crawl = get_crawl_for(db, user, crawl_id)
    limit = max(10, min(limit, 400))
    nodes = db.execute(select(Page.id, Page.url, Page.title, Page.depth, Page.pagerank, Page.inlinks, Page.status_code, Page.indexable)
                       .where(Page.crawl_id == crawl.id, Page.is_html.is_(True)).order_by(Page.pagerank.desc()).limit(limit)).all()
    ids = {n[0] for n in nodes}
    by_url = {n[1]: n[0] for n in nodes}
    edges = set()
    for src, tgt in db.execute(select(Link.source_page_id, Link.target_url).where(Link.crawl_id == crawl.id, Link.is_internal.is_(True), Link.source_page_id.in_(ids))):
        t = by_url.get(tgt)
        if t and t != src:
            edges.add((src, t))
    total = db.scalar(select(func.count()).select_from(Page).where(Page.crawl_id == crawl.id, Page.is_html.is_(True)))
    return {"nodes": [{"id": i, "url": u, "path": urlsplit(u).path or "/", "title": t, "depth": d, "pagerank": pr, "inlinks": inl, "status": s, "indexable": ix}
                      for i, u, t, d, pr, inl, s, ix in nodes],
            "edges": [{"source": s, "target": t} for s, t in list(edges)[:6000]], "total_pages": total, "shown": len(nodes)}


# ----------------------------------------------------------------------------- sitemaps
@router.get("/crawls/{crawl_id}/sitemaps")
def sitemap_report(crawl_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    crawl = get_crawl_for(db, user, crawl_id)
    sm = (crawl.stats or {}).get("sitemap") or {}
    non_indexable = db.execute(select(Page.id, Page.url, Page.status_code, Page.indexability_reason).where(
        Page.crawl_id == crawl.id, Page.in_sitemap.is_(True), Page.indexable.is_(False)).limit(1000)).all()
    missing = db.execute(select(Page.id, Page.url, Page.inlinks).where(Page.crawl_id == crawl.id, Page.in_sitemap.is_(False), Page.indexable.is_(True))
                         .order_by(Page.pagerank.desc()).limit(1000)).all()
    mismatched = db.execute(select(Page.id, Page.url, Page.canonical).where(Page.crawl_id == crawl.id, Page.in_sitemap.is_(True), Page.canonical.isnot(None),
                                                                            Page.canonical != Page.url).limit(1000)).all()
    indexable_total = db.scalar(select(func.count()).select_from(Page).where(Page.crawl_id == crawl.id, Page.indexable.is_(True)))
    return {
        "files": sm.get("files", []), "url_count": sm.get("url_count", 0), "urls_crawled": sm.get("urls_crawled", 0),
        "with_lastmod": sm.get("with_lastmod", 0), "lastmod_by_year": sm.get("lastmod_by_year", {}), "not_crawled": sm.get("not_crawled", []),
        "robots": ((crawl.stats or {}).get("site_checks") or {}).get("robots"),
        "non_indexable_in_sitemap": [{"page_id": i, "url": u, "status_code": s, "reason": r} for i, u, s, r in non_indexable],
        "indexable_missing_from_sitemap": [{"page_id": i, "url": u, "inlinks": n} for i, u, n in missing],
        "canonical_mismatch": [{"page_id": i, "url": u, "canonical": c} for i, u, c in mismatched],
        "indexable_pages": indexable_total,
        "indexing_note": "Whether Google has indexed a URL can only be confirmed through Search Console. Connect it to see impressions per page.",
    }


@router.get("/crawls/{crawl_id}/sitemap.xml")
def generated_sitemap(crawl_id: int, part: int = 1, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Generate a sitemap from the indexable, canonical 200 pages found by the crawl."""
    crawl = get_crawl_for(db, user, crawl_id)
    urls = db.scalars(select(Page.url).where(Page.crawl_id == crawl.id, Page.indexable.is_(True)).order_by(Page.depth.asc().nulls_last(), Page.url)).all()
    docs = generate_sitemap([(u, None) for u in urls])
    if part < 1 or part > len(docs):
        raise HTTPException(404, "No such sitemap part")
    name = f"sitemap-{part}.xml" if len(docs) > 1 else "sitemap.xml"
    return download(docs[part - 1].encode("utf-8"), name, "application/xml")


@router.get("/crawls/{crawl_id}/compare/{other_id}")
def compare_crawls(crawl_id: int, other_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    """What changed between two crawls of the same site (URLs added/removed, issues fixed/new)."""
    a, b = get_crawl_for(db, user, crawl_id), get_crawl_for(db, user, other_id)
    if a.site_id != b.site_id:
        raise HTTPException(400, "Crawls belong to different sites")
    ua = set(db.scalars(select(Page.url).where(Page.crawl_id == a.id)))
    ub = set(db.scalars(select(Page.url).where(Page.crawl_id == b.id)))
    ra, rb = (a.stats or {}).get("issues_by_rule", {}), (b.stats or {}).get("issues_by_rule", {})
    rules = sorted(set(ra) | set(rb), key=lambda r: SEVERITIES.index(RULES[r].severity) if r in RULES else 9)
    return {"current": crawl_out(a), "previous": crawl_out(b), "score_change": None if a.score is None or b.score is None else round(a.score - b.score, 1),
            "urls_added": sorted(ua - ub)[:500], "urls_removed": sorted(ub - ua)[:500], "added_count": len(ua - ub), "removed_count": len(ub - ua),
            "issues": [{**rule_dict(r), "current": ra.get(r, 0), "previous": rb.get(r, 0), "change": ra.get(r, 0) - rb.get(r, 0)} for r in rules if r in RULES]}


# ----------------------------------------------------------------------------- structured data / hreflang / local
@router.get("/crawls/{crawl_id}/schema")
def schema_report(crawl_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    crawl = get_crawl_for(db, user, crawl_id)
    pages, type_pages = [], defaultdict(int)
    without = 0
    for pid, url, depth, indexable, data in db.execute(select(Page.id, Page.url, Page.depth, Page.indexable, Page.data).where(
            Page.crawl_id == crawl.id, Page.is_html.is_(True), Page.status_code == 200).execution_options(yield_per=300)):
        data = data or {}
        items = data.get("jsonld") or []
        types = all_types(items)
        for t in set(types):
            type_pages[t] += 1
        result = validate_jsonld(items)
        q_heads = sum(1 for h in data.get("headings", []) if is_question(h.get("text", "")))
        recs = recommend_types({"url": url, "depth": depth, "types": types, "question_headings": q_heads}) if indexable else []
        if not items and not data.get("microdata_types") and not data.get("jsonld_errors"):
            without += 1
        if items or data.get("jsonld_errors") or data.get("microdata_types") or recs:
            pages.append({"page_id": pid, "url": url, "types": types, "microdata": data.get("microdata_types", []),
                          "errors": result["errors"] + len(data.get("jsonld_errors", [])), "warnings": result["warnings"],
                          "problems": (data.get("jsonld_errors", []) + [f["message"] for f in result["findings"] if f["level"] != "warning"])[:8],
                          "recommended": recs})
    pages.sort(key=lambda p: (-p["errors"], -p["warnings"]))
    return {"types": dict(sorted(type_pages.items(), key=lambda kv: -kv[1])), "pages": pages[:1000], "pages_without_schema": without,
            "pages_with_errors": sum(1 for p in pages if p["errors"]),
            "note": "Validation covers required/recommended properties for common rich-result types; it is not a full schema.org validator."}


@router.get("/crawls/{crawl_id}/hreflang")
def hreflang_report(crawl_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    crawl = get_crawl_for(db, user, crawl_id)
    langs, locales = Counter(), Counter()
    pages = []
    html_langs = Counter()
    for pid, url, lang, _indexable, data in db.execute(select(Page.id, Page.url, Page.lang, Page.indexable, Page.data).where(
            Page.crawl_id == crawl.id, Page.is_html.is_(True), Page.status_code == 200).execution_options(yield_per=300)):
        html_langs[(lang or "missing").lower()] += 1
        loc = locale_from_path(urlsplit(url).path)
        if loc:
            locales[loc] += 1
        alts = (data or {}).get("hreflang") or []
        if alts:
            for a in alts:
                langs[a["lang"].lower()] += 1
            pages.append({"page_id": pid, "url": url, "html_lang": lang, "alternates": alts[:40]})
    rules = [r for r in RULES.values() if r.id.startswith(("hreflang_", "intl_", "lang_"))]
    counts = dict(db.execute(select(Issue.rule_id, func.count()).where(Issue.crawl_id == crawl.id, Issue.rule_id.in_([r.id for r in rules])).group_by(Issue.rule_id)).all())
    sm_alternates = bool(((crawl.stats or {}).get("sitemap") or {}).get("files"))
    return {"pages_with_hreflang": len(pages), "hreflang_values": dict(langs.most_common(60)), "html_lang_values": dict(html_langs.most_common(40)),
            "url_locales": dict(locales.most_common(40)), "pages": pages[:500],
            "issues": [{**rule_dict(r.id), "count": counts.get(r.id, 0)} for r in rules if counts.get(r.id)],
            "is_multilingual": len(pages) > 0 or len([k for k in html_langs if k != "missing"]) > 1 or len(locales) > 1,
            "sitemap_checked": sm_alternates}


_PHONE = re.compile(r"(?:\+|00)?\d[\d\s().-]{7,17}\d")


def _norm_phone(p: str | None) -> str:
    digits = re.sub(r"\D", "", p or "")
    return digits[-10:] if len(digits) >= 10 else digits


def _norm_text(t: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (t or "").lower()).strip()


@router.get("/crawls/{crawl_id}/local")
def local_seo(crawl_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    """LocalBusiness schema, NAP (name/address/phone) consistency across pages and imported citations."""
    crawl = get_crawl_for(db, user, crawl_id)
    businesses, location_pages = [], []
    phones_seen: Counter = Counter()
    for pid, url, title, wc, data, text in db.execute(select(Page.id, Page.url, Page.title, Page.word_count, Page.data, Page.text).where(
            Page.crawl_id == crawl.id, Page.is_html.is_(True), Page.status_code == 200).execution_options(yield_per=200)):
        data = data or {}
        path = urlsplit(url).path.lower()
        is_loc = any(s in path for s in ("/location", "/store", "/branch", "/office", "/contact", "/find-us", "/areas"))
        local_items = [i for i in (data.get("jsonld") or []) if isinstance(i, dict) and set(all_types([i])[:1]) & LOCAL_TYPES]
        for item in local_items:
            addr = item.get("address") if isinstance(item.get("address"), dict) else {}
            address = ", ".join(str(addr.get(k)) for k in ("streetAddress", "addressLocality", "addressRegion", "postalCode", "addressCountry") if addr.get(k))
            result = validate_jsonld([item])
            businesses.append({"page_id": pid, "url": url, "name": item.get("name"), "phone": item.get("telephone"), "address": address or (item.get("address") if isinstance(item.get("address"), str) else None),
                               "has_geo": bool(item.get("geo")), "has_hours": bool(item.get("openingHoursSpecification") or item.get("openingHours")),
                               "problems": [f["message"] for f in result["findings"]][:6]})
        if is_loc or local_items:
            found = {_norm_phone(m) for m in _PHONE.findall((text or "")[:20000])}
            found.discard("")
            for ph in found:
                phones_seen[ph] += 1
            location_pages.append({"page_id": pid, "url": url, "title": title, "word_count": wc, "has_local_schema": bool(local_items),
                                   "phones_in_text": sorted(found)[:5], "has_map": "google.com/maps" in json.dumps(data.get("mixed_content", [])) or data.get("iframes", 0) > 0,
                                   "issues": [m for m, bad in (("No LocalBusiness schema", not local_items), ("Thin content (<200 words)", (wc or 0) < 200),
                                                               ("No phone number in page text", not found)) if bad]})
    citations = db.scalars(select(Citation).where(Citation.site_id == crawl.site_id)).all()
    names = Counter(_norm_text(b["name"]) for b in businesses if b["name"])
    phones = Counter(_norm_phone(b["phone"]) for b in businesses if b["phone"])
    addresses = Counter(_norm_text(b["address"]) for b in businesses if b["address"])
    ref = {"name": names.most_common(1)[0][0] if names else None, "phone": phones.most_common(1)[0][0] if phones else None,
           "address": addresses.most_common(1)[0][0] if addresses else None}
    citation_rows = []
    for c in citations:
        mismatch = [f for f, val, norm in (("name", c.name, _norm_text), ("phone", c.phone, _norm_phone), ("address", c.address, _norm_text))
                    if val and ref[f] and norm(val) != ref[f]]
        citation_rows.append({"id": c.id, "source": c.source, "url": c.url, "name": c.name, "address": c.address, "phone": c.phone,
                              "mismatches": mismatch, "consistent": not mismatch})
    return {
        "businesses": businesses, "location_pages": location_pages[:500], "citations": citation_rows,
        "nap": {"reference": ref, "name_variants": len(names), "phone_variants": len(phones), "address_variants": len(addresses),
                "consistent": len(names) <= 1 and len(phones) <= 1 and len(addresses) <= 1,
                "reference_source": "Most common values in the site's own LocalBusiness markup"},
        "has_local_schema": bool(businesses),
        "gbp_note": "Google Business Profile data requires API access that Google grants per project; this module works from your site's "
                    "markup and citation lists you import (CSV with source, url, name, address, phone).",
    }


# ----------------------------------------------------------------------------- exports
def _dataset(db: Session, crawl: Crawl, dataset: str, limit: int = 200_000) -> list[dict]:
    if dataset == "pages":
        rows = db.scalars(select(Page).where(Page.crawl_id == crawl.id).order_by(Page.url).limit(limit)).all()
        return [{k: v for k, v in page_row(p).items() if k != "id"} for p in rows]
    if dataset == "issues":
        rows = db.execute(select(Issue.severity, Issue.category, Issue.rule_id, Issue.url, Issue.details).where(Issue.crawl_id == crawl.id)
                          .order_by(_SEV_ORDER, Issue.rule_id, Issue.url).limit(limit)).all()
        return [{"severity": s, "category": c, "issue": RULES[r].title if r in RULES else r, "url": u, "details": d,
                 "recommended_fix": RULES[r].fix if r in RULES else ""} for s, c, r, u, d in rows]
    if dataset in ("links", "broken_links"):
        stmt = select(Link.source_url, Link.target_url, Link.anchor, Link.is_internal, Link.nofollow, Link.target_status, Link.target_error).where(Link.crawl_id == crawl.id)
        if dataset == "broken_links":
            stmt = stmt.where(_BROKEN_LINK)
        return [{"source_url": s, "target_url": t, "anchor": a, "internal": i, "nofollow": n, "target_status": st, "target_error": e}
                for s, t, a, i, n, st, e in db.execute(stmt.limit(limit))]
    if dataset == "redirects":
        return [{"url": r["url"], "status_code": r["status_code"], "hops": r["hops"], "loop": r["loop"], "final_url": r["final_url"],
                 "final_status": r["final_status"], "chain": " -> ".join(r["chain"])} for r in _redirect_rows(db, crawl)]
    raise HTTPException(400, "Unknown dataset. Use pages, issues, links, broken_links or redirects.")


@router.get("/crawls/{crawl_id}/export")
def export_crawl(crawl_id: int, dataset: str = "pages", format: str = "csv", user: User = Depends(current_user), db: Session = Depends(get_db)):
    crawl = get_crawl_for(db, user, crawl_id)
    site = db.get(Site, crawl.site_id)
    name = f"{site.domain}-crawl{crawl.id}"
    if format == "xlsx" and dataset == "all":
        summary = [{"metric": k, "value": json.dumps(v) if isinstance(v, dict | list) else v} for k, v in (crawl.stats or {}).items()
                   if k not in ("sitemap", "site_checks", "issues_by_rule")]
        sheets = {"Summary": summary, "Issues": _dataset(db, crawl, "issues"), "Pages": _dataset(db, crawl, "pages"),
                  "Broken links": _dataset(db, crawl, "broken_links"), "Redirects": _dataset(db, crawl, "redirects")}
        return download(to_xlsx(sheets), f"{name}.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    rows = _dataset(db, crawl, dataset)
    if format == "csv":
        return download(to_csv(rows), f"{name}-{dataset}.csv", "text/csv")
    if format == "xlsx":
        return download(to_xlsx({dataset.title(): rows}), f"{name}-{dataset}.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    if format == "json":
        return download(json.dumps({"crawl": crawl_out(crawl, with_stats=True), dataset: rows}, default=str, ensure_ascii=False).encode("utf-8"),
                        f"{name}-{dataset}.json", "application/json")
    raise HTTPException(400, "Unknown format. Use csv, xlsx or json.")


@router.get("/crawls/{crawl_id}/report.pdf")
def audit_report(crawl_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    crawl = get_crawl_for(db, user, crawl_id)
    if crawl.status != "completed":
        raise HTTPException(409, "The report is available once the crawl has completed")
    site = db.get(Site, crawl.site_id)
    groups = []
    for rule_id, count in db.execute(select(Issue.rule_id, func.count()).where(Issue.crawl_id == crawl.id).group_by(Issue.rule_id)):
        if rule_id in RULES:
            urls = db.scalars(select(Issue.url).where(Issue.crawl_id == crawl.id, Issue.rule_id == rule_id).order_by(Issue.url).limit(15)).all()
            groups.append({"rule_id": rule_id, "count": count, "urls": urls})
    pdf = audit_pdf(site.name, site.url, {"id": crawl.id, "finished_at": crawl.finished_at.strftime("%Y-%m-%d %H:%M") if crawl.finished_at else None,
                                          "score": crawl.score, "stats": crawl.stats}, groups)
    return download(pdf, f"seo-audit-{site.domain}-crawl{crawl.id}.pdf", "application/pdf")
