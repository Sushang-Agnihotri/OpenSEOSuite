"""Backlink analysis from data the user legitimately has: Search Console link exports, exports from other
tools, or any CSV. The toolkit does not own a web-scale link index (see KNOWN_LIMITATIONS.md); what it
adds is verification (is the link still live, anchor, rel) and analysis on top of imported data.
"""
from __future__ import annotations

import asyncio
import csv
import io
from collections import Counter
from datetime import timedelta
from urllib.parse import urlsplit

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..crawler.fetcher import Fetcher
from ..crawler.parser import parse_html
from ..crawler.urls import normalize_url, registrable_domain, strip_www
from ..db import session_scope
from ..jobs import JobContext
from ..models import Backlink, Crawl, Page, Site, utcnow

_COLS = {
    "source": ("source url", "source_url", "linking page", "linking pages", "referring page", "referring page url", "url from",
               "from", "source", "page url", "url", "link from"),
    "site": ("site", "linking site", "top linking sites", "referring domain", "domain"),
    "target": ("target url", "target_url", "target page", "url to", "to", "link url", "target", "destination"),
    "anchor": ("anchor", "anchor text", "link text", "link anchor"),
    "nofollow": ("nofollow", "rel", "link type", "type", "follow"),
}


def _nofollow(value: str | None) -> bool | None:
    v = (value or "").strip().lower()
    if not v:
        return None
    if v in ("true", "1", "yes", "nofollow") or "nofollow" in v or "ugc" in v or "sponsored" in v:
        return True
    if v in ("false", "0", "no", "follow", "dofollow"):
        return False
    return None


def import_csv(db: Session, site: Site, raw: bytes, origin: str = "import") -> dict:
    text = raw.decode("utf-8-sig", "replace")
    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    reader = csv.reader(io.StringIO(text), dialect)
    header = next(reader, None)
    if not header:
        raise ValueError("The CSV file is empty.")
    idx: dict[str, int] = {}
    for i, name in enumerate(header):
        n = name.strip().lower()
        for field, aliases in _COLS.items():
            if n in aliases and field not in idx:
                idx[field] = i
    if "source" not in idx and "site" not in idx:
        raise ValueError("CSV needs a source column (e.g. 'Source URL', 'Linking page') or a 'Site' column.")
    existing = {(s, t) for s, t in db.execute(select(Backlink.source_url, Backlink.target_url).where(Backlink.site_id == site.id))}
    added = skipped = 0
    for row in reader:
        if added >= 200_000:
            break
        def get(f, row=row):
            return row[idx[f]].strip() if f in idx and idx[f] < len(row) else ""
        src = get("source")
        domain_only = False
        if not src and get("site"):
            src, domain_only = f"https://{get('site').strip('/')}/", True
        elif src and "://" not in src:
            src = "https://" + src
        source = normalize_url(src)
        if not source:
            skipped += 1
            continue
        target = normalize_url(get("target"), site.url) if get("target") else None
        if (source, target) in existing:
            skipped += 1
            continue
        existing.add((source, target))
        db.add(Backlink(site_id=site.id, source_url=source, source_domain=registrable_domain(urlsplit(source).hostname or ""),
                        target_url=target, anchor=get("anchor")[:500] or None, nofollow=_nofollow(get("nofollow")),
                        origin=f"{origin}{':domain-level' if domain_only else ''}"[:30]))
        added += 1
    db.commit()
    return {"added": added, "skipped": skipped, "columns_detected": sorted(idx)}


def summary(db: Session, site: Site) -> dict:
    total = db.scalar(select(func.count()).select_from(Backlink).where(Backlink.site_id == site.id)) or 0
    if not total:
        return {"total": 0}
    domains = db.execute(select(Backlink.source_domain, func.count(), func.min(Backlink.first_seen))
                         .where(Backlink.site_id == site.id).group_by(Backlink.source_domain).order_by(func.count().desc()).limit(500)).all()
    n_domains = db.scalar(select(func.count(func.distinct(Backlink.source_domain))).where(Backlink.site_id == site.id))
    anchors = db.execute(select(Backlink.anchor, func.count()).where(Backlink.site_id == site.id, Backlink.anchor.isnot(None))
                         .group_by(Backlink.anchor).order_by(func.count().desc()).limit(100)).all()
    rel = dict(db.execute(select(Backlink.nofollow, func.count()).where(Backlink.site_id == site.id).group_by(Backlink.nofollow)).all())
    statuses = dict(db.execute(select(Backlink.status, func.count()).where(Backlink.site_id == site.id).group_by(Backlink.status)).all())
    targets = db.execute(select(Backlink.target_url, func.count()).where(Backlink.site_id == site.id, Backlink.target_url.isnot(None))
                         .group_by(Backlink.target_url).order_by(func.count().desc()).limit(200)).all()
    origins = dict(db.execute(select(Backlink.origin, func.count()).where(Backlink.site_id == site.id).group_by(Backlink.origin)).all())
    recent = db.scalar(select(func.count()).select_from(Backlink).where(Backlink.site_id == site.id, Backlink.first_seen >= utcnow() - timedelta(days=30)))
    # status of link destinations according to the latest crawl of the site
    crawl = db.scalar(select(Crawl).where(Crawl.site_id == site.id, Crawl.competitor_id.is_(None), Crawl.status == "completed").order_by(Crawl.id.desc()))
    status_of: dict[str, int | None] = {}
    if crawl and targets:
        urls = [t for t, _ in targets]
        status_of = dict(db.execute(select(Page.url, Page.status_code).where(Page.crawl_id == crawl.id, Page.url.in_(urls))).all())
    target_rows = [{"url": t, "backlinks": c, "status": status_of.get(t), "in_crawl": t in status_of} for t, c in targets]
    broken = [t for t in target_rows if t["in_crawl"] and (t["status"] is None or t["status"] >= 400)]
    host = strip_www(urlsplit(site.url).hostname or "")
    brand = host.split(".")[0]
    anchor_types = Counter()
    for a, c in anchors:
        al = (a or "").lower()
        kind = ("url" if al.startswith(("http", "www.")) or host in al else "brand" if brand and brand in al
                else "generic" if al in ("click here", "here", "website", "link", "read more", "this", "visit", "source", "learn more") else "keyword/other")
        anchor_types[kind] += c
    return {
        "total": total, "referring_domains": n_domains, "new_last_30_days": recent,
        "follow": rel.get(False, 0), "nofollow": rel.get(True, 0), "rel_unknown": rel.get(None, 0),
        "statuses": statuses, "origins": origins,
        "top_domains": [{"domain": d, "backlinks": c, "first_seen": f.isoformat() if f else None} for d, c, f in domains[:100]],
        "top_anchors": [{"anchor": a, "count": c} for a, c in anchors],
        "anchor_types": dict(anchor_types),
        "top_targets": target_rows[:100],
        "broken_targets": broken,
        "opportunities": (
            [{"type": "reclaim", "url": b["url"], "backlinks": b["backlinks"],
              "action": "This linked page is broken in your latest crawl. 301-redirect it to a relevant live page to recover the links."} for b in broken[:50]]
        ),
        "coverage_note": "Only links present in imported datasets are shown. This is not a complete picture of the web's links to your site.",
        "crawl_used_for_targets": crawl.id if crawl else None,
    }


async def verify_backlinks(site_id: int, ctx: JobContext | None = None, limit: int = 500) -> dict:
    """Fetch each linking page and confirm the link to the site still exists; record anchor and rel."""
    with session_scope() as db:
        site = db.get(Site, site_id)
        host = strip_www(urlsplit(site.url).hostname or "")
        rows = db.execute(select(Backlink.id, Backlink.source_url, Backlink.target_url).where(Backlink.site_id == site_id, ~Backlink.origin.like("%domain-level"))
                          .order_by(Backlink.last_checked.is_(None).desc(), Backlink.last_checked).limit(limit)).all()
    results: dict[int, dict] = {}
    done = 0
    async with Fetcher(timeout_s=15, retries=1, delay_s=0.5, concurrency=6) as fetcher:
        sem = asyncio.Semaphore(6)

        async def one(bid: int, source: str, target: str | None) -> None:
            nonlocal done
            async with sem:
                res = await fetcher.fetch_following(source, max_body=3_000_000)
                out = {"http_status": res.status, "status": "source_error"}
                if res.status == 200 and res.is_html:
                    page = await asyncio.to_thread(parse_html, res.body, res.final_url or source, res.headers.get("content-type", ""))
                    links = [lk for lk in page.links if strip_www(urlsplit(lk["url"]).hostname or "") == host]
                    exact = [lk for lk in links if target and lk["url"] == target]
                    hit = (exact or links or [None])[0]
                    if hit:
                        out.update(status="live", anchor=hit["anchor"] or None, nofollow=bool(hit["nofollow"] or hit.get("sponsored") or hit.get("ugc")),
                                   target_url=target or hit["url"])
                    else:
                        out["status"] = "lost"
                results[bid] = out
                done += 1
                if ctx:
                    ctx.update(done / max(len(rows), 1), f"Verified {done} of {len(rows)} linking pages")

        await asyncio.gather(*(one(*r) for r in rows))
    counts = Counter()
    with session_scope() as db:
        for bid, out in results.items():
            b = db.get(Backlink, bid)
            if b is None:
                continue
            for k, v in out.items():
                setattr(b, k, v)
            b.last_checked = utcnow()
            counts[out["status"]] += 1
    return {"checked": len(results), **counts}
