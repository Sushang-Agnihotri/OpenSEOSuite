"""Site-wide analysis run after a crawl: link graph, redirects, duplicates, canonicals, hreflang,
sitemap consistency, image checks, scoring and summary statistics."""
from __future__ import annotations

from collections import Counter, defaultdict, deque
from types import SimpleNamespace
from urllib.parse import urlsplit

from sqlalchemy import delete, insert, select, text, update

from ..crawler.parser import hamming
from ..crawler.sitemaps import SitemapReport
from ..db import session_scope
from ..models import Crawl, Issue, Link, Page
from .hreflang import language_of, locale_from_path
from .rules import PAGE_PENALTY, RULES, SITE_PENALTY
from .schema_validator import all_types

DEEP = 4
LARGE_IMAGE = 300_000
NEAR_DUP_BITS = 3
_UNVERIFIABLE = {401, 403, 405, 406, 429, 999}
SITE_RULE_IDS = {r.id for r in RULES.values() if r.scope == "site"}
POST_RULES = {  # rules produced by this module; cleared before re-analysis
    "redirect_loop", "redirect_chain", "redirect_broken", "link_to_redirect", "broken_internal_link",
    "broken_external_link", "broken_image", "img_large", "orphan_page", "deep_page", "single_inlink",
    "title_duplicate", "description_duplicate", "h1_duplicate", "duplicate_content", "near_duplicate_content",
    "canonical_broken", "canonical_chain", "hreflang_no_return", "hreflang_broken", "intl_duplicate",
    "sitemap_non_indexable", "not_in_sitemap",
} | SITE_RULE_IDS


def is_broken_external(status: int | None, error: str | None) -> bool:
    if status is None:
        return bool(error) and error != "timeout" and not error.startswith("blocked")
    return status >= 400 and status not in _UNVERIFIABLE


def pagerank(n: int, out_edges: list[set[int]], damping: float = 0.85, iterations: int = 40) -> list[float]:
    """Power-iteration PageRank; result is scaled so the average node scores 1.0."""
    if n == 0:
        return []
    rank = [1.0 / n] * n
    for _ in range(iterations):
        new = [(1.0 - damping) / n] * n
        dangling = 0.0
        for i, targets in enumerate(out_edges):
            if targets:
                share = damping * rank[i] / len(targets)
                for t in targets:
                    new[t] += share
            else:
                dangling += rank[i]
        if dangling:
            extra = damping * dangling / n
            new = [v + extra for v in new]
        delta = sum(abs(a - b) for a, b in zip(new, rank, strict=True))
        rank = new
        if delta < 1e-9:
            break
    return [r * n for r in rank]


def near_duplicate_pairs(items: list[tuple[int, str]]) -> dict[int, set[int]]:
    """Find items whose SimHash differs by <= NEAR_DUP_BITS bits using 4x16-bit banding."""
    buckets: dict[tuple[int, int], list[int]] = defaultdict(list)
    values = {}
    for key, sh in items:
        v = int(sh, 16)
        values[key] = sh
        for band in range(4):
            buckets[(band, (v >> (band * 16)) & 0xFFFF)].append(key)
    pairs: dict[int, set[int]] = defaultdict(set)
    for members in buckets.values():
        if len(members) < 2:
            continue
        head = members[:200]  # cap comparisons for very large buckets of templated pages
        for a in members:
            for b in head:
                if a != b and b not in pairs[a] and hamming(values[a], values[b]) <= NEAR_DUP_BITS:
                    pairs[a].add(b)
                    pairs[b].add(a)
    return pairs


def analyse_crawl(crawl_id: int, *, sitemap: SitemapReport | None = None, site_checks: dict | None = None,
                  external_status: dict[str, dict] | None = None, image_status: dict[str, dict] | None = None,
                  limit_hit: bool = False) -> dict:
    sitemap = sitemap or SitemapReport()
    site_checks = site_checks or {}
    external_status = external_status or {}
    image_status = image_status or {}
    issues: list[dict] = []

    with session_scope() as db:
        crawl = db.get(Crawl, crawl_id)
        start_url = crawl.start_url
        db.execute(delete(Issue).where(Issue.crawl_id == crawl_id, Issue.rule_id.in_(POST_RULES)))

        cols = (Page.id, Page.url, Page.status_code, Page.error, Page.is_html, Page.redirect_to, Page.indexable,
                Page.indexability_reason, Page.title, Page.meta_description, Page.h1, Page.canonical, Page.content_hash,
                Page.simhash, Page.lang, Page.in_sitemap, Page.blocked_by_robots, Page.found_via, Page.word_count,
                Page.response_ms, Page.content_type, Page.size_bytes)
        pages = [SimpleNamespace(**row._mapping) for row in db.execute(select(*cols).where(Page.crawl_id == crawl_id))]
        by_url = {p.url: p for p in pages}
        by_id = {p.id: p for p in pages}
        index = {p.id: i for i, p in enumerate(pages)}
        n = len(pages)

        def add(rule_id: str, page, details: dict) -> None:
            r = RULES[rule_id]
            issues.append({"crawl_id": crawl_id, "page_id": page.id if page is not None else None,
                           "url": page.url if page is not None else start_url, "rule_id": rule_id,
                           "severity": r.severity, "category": r.category, "details": details})

        # ---------------------------------------------------------------- redirects
        def resolve(url: str) -> tuple[list[str], str]:
            """Follow redirect_to pointers. Returns (hops, outcome) with outcome ok|loop|broken|external|unknown."""
            hops, seen, cur = [], {url}, url
            while True:
                p = by_url.get(cur)
                if p is None:
                    ext = external_status.get(cur)
                    if ext is None:
                        return hops, "unknown"
                    return hops, "broken" if is_broken_external(ext.get("status"), ext.get("error")) else "external"
                if not p.redirect_to:
                    bad = p.status_code is None or p.status_code >= 400
                    return hops, "broken" if bad and not p.blocked_by_robots else "ok"
                hops.append(p.redirect_to)
                if p.redirect_to in seen:
                    return hops, "loop"
                seen.add(p.redirect_to)
                cur = p.redirect_to
                if len(hops) > 20:
                    return hops, "loop"

        final_of: dict[str, str] = {}
        redirect_rows = []
        for p in pages:
            if not p.redirect_to:
                continue
            hops, outcome = resolve(p.url)
            final_of[p.url] = hops[-1] if hops else p.url
            redirect_rows.append({"url": p.url, "status": p.status_code, "hops": len(hops), "chain": hops[:12], "outcome": outcome})
            if outcome == "loop":
                add("redirect_loop", p, {"chain": hops[:12]})
            else:
                if len(hops) > 1:
                    add("redirect_chain", p, {"hops": len(hops), "chain": hops[:12]})
                if outcome == "broken":
                    add("redirect_broken", p, {"chain": hops[:12]})

        # ---------------------------------------------------------------- links
        out_edges: list[set[int]] = [set() for _ in range(n)]
        in_sources: list[set[int]] = [set() for _ in range(n)]
        broken_int: dict[int, list] = defaultdict(list)
        broken_ext: dict[int, list] = defaultdict(list)
        to_redirect: dict[int, list] = defaultdict(list)
        target_updates: dict[str, tuple[int | None, str | None]] = {}
        link_counts = Counter()
        for src_id, target, anchor, nofollow, internal in db.execute(
            select(Link.source_page_id, Link.target_url, Link.anchor, Link.nofollow, Link.is_internal)
            .where(Link.crawl_id == crawl_id).execution_options(yield_per=5000)
        ):
            link_counts["internal" if internal else "external"] += 1
            if internal:
                t = by_url.get(target)
                if t is None:
                    continue  # not crawled (limit reached or excluded)
                target_updates[target] = (t.status_code, t.error)
                if src_id in index and t.id != src_id:
                    if not nofollow:
                        out_edges[index[src_id]].add(index[t.id])
                    in_sources[index[t.id]].add(index[src_id])
                if t.blocked_by_robots:
                    continue
                if t.status_code is None or t.status_code >= 400:
                    broken_int[src_id].append({"url": target, "status": t.status_code, "error": t.error, "anchor": anchor})
                elif t.redirect_to:
                    to_redirect[src_id].append({"url": target, "status": t.status_code, "final": final_of.get(target)})
            else:
                ext = external_status.get(target)
                if ext is None:
                    continue
                target_updates[target] = (ext.get("status"), ext.get("error"))
                if is_broken_external(ext.get("status"), ext.get("error")):
                    broken_ext[src_id].append({"url": target, "status": ext.get("status"), "error": ext.get("error"), "anchor": anchor})
        for src_id, items in broken_int.items():
            link_counts["broken_internal"] += len(items)
            add("broken_internal_link", by_id[src_id], {"count": len(items), "links": items[:25]})
        for src_id, items in broken_ext.items():
            link_counts["broken_external"] += len(items)
            add("broken_external_link", by_id[src_id], {"count": len(items), "links": items[:25]})
        for src_id, items in to_redirect.items():
            add("link_to_redirect", by_id[src_id], {"count": len(items), "links": items[:25]})
        if target_updates:
            stmt = text("UPDATE links SET target_status = :s, target_error = :e WHERE crawl_id = :c AND target_url = :u")
            db.execute(stmt, [{"s": s, "e": e, "c": crawl_id, "u": u} for u, (s, e) in target_updates.items()])

        # redirects pass link equity and reachability to their target
        for p in pages:
            if p.redirect_to and p.redirect_to in by_url:
                out_edges[index[p.id]] = {index[by_url[p.redirect_to].id]}

        # ---------------------------------------------------------------- depth (BFS) and PageRank
        depth: list[int | None] = [None] * n
        start = by_url.get(start_url)
        if start is not None:
            depth[index[start.id]] = 0
            dq = deque([index[start.id]])
            while dq:
                i = dq.popleft()
                step = 0 if pages[i].redirect_to else 1
                for j in out_edges[i]:
                    nd = depth[i] + step
                    if depth[j] is None or nd < depth[j]:
                        depth[j] = nd
                        (dq.appendleft if step == 0 else dq.append)(j)
        ranks = pagerank(n, out_edges)

        # ---------------------------------------------------------------- architecture
        sitemap_has_urls = bool(sitemap.urls)
        for i, p in enumerate(pages):
            p.inlinks = len(in_sources[i])
            p.depth = depth[i]
            p.pagerank = round(ranks[i], 4) if ranks else 0.0
            if not p.indexable:
                continue
            if p.inlinks == 0 and p.url != start_url and depth[i] is None:
                add("orphan_page", p, {"found_via": p.found_via})
            elif depth[i] is not None and depth[i] > DEEP:
                add("deep_page", p, {"depth": depth[i]})
            if p.inlinks == 1 and depth[i] not in (None, 0, 1):
                add("single_inlink", p, {})
            if sitemap_has_urls and not p.in_sitemap:
                add("not_in_sitemap", p, {})
        for p in pages:
            if p.in_sitemap and not p.indexable:
                add("sitemap_non_indexable", p, {"reason": p.indexability_reason or (f"HTTP {p.status_code}" if p.status_code else p.error),
                                                 "sitemap": sitemap.urls.get(p.url, {}).get("sitemap")})

        # ---------------------------------------------------------------- duplicates
        indexable = [p for p in pages if p.indexable]
        dup_groups = {}
        for attr, rule in (("title", "title_duplicate"), ("meta_description", "description_duplicate"),
                           ("h1", "h1_duplicate"), ("content_hash", "duplicate_content")):
            groups: dict[str, list] = defaultdict(list)
            for p in indexable:
                v = getattr(p, attr)
                if v and (attr != "content_hash" or p.word_count >= 30):
                    groups[v.strip().lower() if attr != "content_hash" else v].append(p)
            groups = {k: v for k, v in groups.items() if len(v) > 1}
            dup_groups[rule] = len(groups)
            for value, members in groups.items():
                for p in members:
                    others = [m.url for m in members if m.id != p.id]
                    add(rule, p, {"value": None if attr == "content_hash" else value[:200], "count": len(members), "other_urls": others[:10]})
        candidates = [(p.id, p.simhash) for p in indexable if p.simhash and p.word_count >= 50]
        near = near_duplicate_pairs(candidates)
        near_count = 0
        for pid, others in near.items():
            p = by_id[pid]
            others = [by_id[o].url for o in others if by_id[o].content_hash != p.content_hash]
            if others:
                near_count += 1
                add("near_duplicate_content", p, {"other_urls": others[:10]})
        dup_groups["near_duplicate_pages"] = near_count

        # ---------------------------------------------------------------- canonicals
        for p in pages:
            if not p.is_html or not p.canonical or p.canonical == p.url:
                continue
            t = by_url.get(p.canonical)
            if t is None:
                continue
            if t.status_code != 200 or t.indexability_reason in ("noindex", "blocked by robots.txt"):
                add("canonical_broken", p, {"canonical": p.canonical, "status": t.status_code, "reason": t.indexability_reason})
            elif t.canonical and t.canonical != t.url:
                add("canonical_chain", p, {"canonical": p.canonical, "points_to": t.canonical})

        # ---------------------------------------------------------------- per-page JSON data pass
        hreflang_of: dict[int, list[dict]] = {}
        schema_types = Counter()
        pages_with_schema = 0
        start_data: dict = {}
        for pid, data in db.execute(select(Page.id, Page.data).where(Page.crawl_id == crawl_id, Page.is_html.is_(True))
                                    .execution_options(yield_per=500)):
            data = data or {}
            p = by_id[pid]
            if p.url == start_url or (start is not None and final_of.get(start_url) == p.url):
                start_data = data
            if data.get("hreflang"):
                hreflang_of[pid] = data["hreflang"]
            types = all_types(data.get("jsonld") or [])
            if types or data.get("microdata_types"):
                pages_with_schema += 1
            schema_types.update(types)
            if image_status and data.get("images"):
                broken, large = [], []
                for img in data["images"]:
                    st = image_status.get(img["src"])
                    if not st:
                        continue
                    if (st.get("status") or 0) >= 400 and st.get("status") not in _UNVERIFIABLE:
                        broken.append({"url": img["src"], "status": st["status"]})
                    elif st.get("bytes") and st["bytes"] > LARGE_IMAGE:
                        large.append({"url": img["src"], "bytes": st["bytes"]})
                if broken:
                    add("broken_image", p, {"count": len(broken), "images": broken[:20]})
                if large:
                    add("img_large", p, {"count": len(large), "images": large[:20]})

        # ---------------------------------------------------------------- hreflang reciprocity
        for pid, alts in hreflang_of.items():
            p = by_id[pid]
            missing, broken = [], []
            for alt in alts:
                href = alt["href"]
                if href == p.url:
                    continue
                t = by_url.get(href)
                if t is None:
                    continue
                if t.status_code != 200 or not t.indexable:
                    broken.append({"hreflang": alt["lang"], "url": href, "status": t.status_code, "reason": t.indexability_reason})
                    continue
                back = {a["href"] for a in hreflang_of.get(t.id, [])}
                if p.url not in back:
                    missing.append({"hreflang": alt["lang"], "url": href})
            if missing:
                add("hreflang_no_return", p, {"alternates": missing[:20]})
            if broken:
                add("hreflang_broken", p, {"alternates": broken[:20]})
        by_hash: dict[str, list] = defaultdict(list)
        for p in indexable:
            if p.content_hash and p.word_count >= 30:
                by_hash[p.content_hash].append(p)
        for members in by_hash.values():
            locales = {language_of(m.lang) or "" for m in members} | {locale_from_path(urlsplit(m.url).path) or "" for m in members}
            if len(members) > 1 and len(locales - {""}) > 1 and not any(m.id in hreflang_of for m in members):
                for m in members:
                    add("intl_duplicate", m, {"other_urls": [o.url for o in members if o.id != m.id][:10]})

        # ---------------------------------------------------------------- site-level rules
        robots = site_checks.get("robots") or {}
        if robots:
            if robots.get("blocks_start"):
                add("robots_blocks_site", None, {"robots_status": robots.get("status")})
            if (robots.get("status") or 0) >= 500:
                add("robots_unreachable", None, {"status": robots.get("status")})
            elif not robots.get("present"):
                add("robots_missing", None, {"status": robots.get("status")})
            if robots.get("errors"):
                add("robots_syntax", None, {"errors": robots["errors"]})
        good_files = [f for f in sitemap.files if f.status == 200 and f.kind != "unknown"]
        if not good_files:
            add("sitemap_missing", None, {})
        elif robots.get("present") and not robots.get("sitemaps"):
            add("sitemap_not_in_robots", None, {"sitemaps": [f.url for f in good_files][:5]})
        bad_files = [f for f in sitemap.files if f.errors]
        if bad_files:
            add("sitemap_invalid", None, {"sitemaps": [{"url": f.url, "errors": f.errors[:5]} for f in bad_files][:10]})
        hv = site_checks.get("http_version")
        if hv and hv.get("status") is not None and not (hv.get("redirect_to") or "").startswith("https://"):
            if hv["status"] < 400:
                add("https_not_enforced", None, hv)
        var = site_checks.get("host_variant")
        if var and var.get("status") == 200 and var.get("final_host") == var.get("host"):
            add("host_variants", None, var)
        if start is not None and start_data:
            if start_url.startswith("https://") and not start_data.get("hsts"):
                add("hsts_missing", None, {})
            if not start_data.get("favicon"):
                add("favicon_missing", None, {})

        # ---------------------------------------------------------------- persist issues, score
        for i in range(0, len(issues), 2000):
            db.execute(insert(Issue), issues[i : i + 2000])
        db.flush()
        page_rules: dict[int, set[tuple[str, str]]] = defaultdict(set)
        sev_counts, rule_counts, cat_counts = Counter(), Counter(), Counter()
        site_penalty = 0.0
        for pid, rule_id, sev, cat in db.execute(select(Issue.page_id, Issue.rule_id, Issue.severity, Issue.category).where(Issue.crawl_id == crawl_id)):
            sev_counts[sev] += 1
            rule_counts[rule_id] += 1
            cat_counts[cat] += 1
            if pid is None:
                site_penalty += SITE_PENALTY[sev]
            else:
                page_rules[pid].add((rule_id, sev))
        updates, scored = [], []
        for p in pages:
            rules = page_rules.get(p.id, set())
            score = None
            if p.is_html or p.status_code is None or (p.status_code or 0) >= 400:
                if not p.blocked_by_robots:
                    score = max(0.0, 100.0 - sum(PAGE_PENALTY[s] for _, s in rules))
                    scored.append(score)
            updates.append({"id": p.id, "inlinks": p.inlinks, "depth": p.depth, "pagerank": p.pagerank,
                            "score": score, "issue_count": len(rules)})
        for i in range(0, len(updates), 2000):
            db.execute(update(Page), updates[i : i + 2000])
        site_score = round(max(0.0, (sum(scored) / len(scored) if scored else 0.0) - site_penalty), 1) if scored else None

        # ---------------------------------------------------------------- statistics
        status_classes = Counter()
        for p in pages:
            if p.blocked_by_robots:
                status_classes["blocked"] += 1
            elif p.status_code is None:
                status_classes["error"] += 1
            else:
                status_classes[f"{p.status_code // 100}xx"] += 1
        html_ok = [p for p in pages if p.is_html and p.status_code == 200]
        depth_dist = Counter(str(p.depth) if p.depth is not None else "unreachable" for p in html_ok)
        reasons = Counter(p.indexability_reason for p in pages if p.is_html and not p.indexable and p.indexability_reason)
        types = Counter((p.content_type or "unknown").split("/")[-1] if p.status_code else "n/a" for p in pages)
        stats = {
            "score": site_score,
            "total_urls": n,
            "html_pages": len(html_ok),
            "indexable_pages": len(indexable),
            "non_indexable_pages": len(html_ok) - len(indexable),
            "non_indexable_reasons": dict(reasons),
            "status_classes": dict(status_classes),
            "content_types": dict(types.most_common(12)),
            "depth_distribution": dict(depth_dist),
            "issues_by_severity": {s: sev_counts.get(s, 0) for s in ("critical", "high", "medium", "low")},
            "issues_by_category": dict(cat_counts),
            "issues_by_rule": dict(rule_counts),
            "affected_pages": len(page_rules),
            "avg_word_count": round(sum(p.word_count for p in indexable) / len(indexable)) if indexable else 0,
            "avg_response_ms": round(sum(p.response_ms for p in html_ok) / len(html_ok)) if html_ok else 0,
            "links": {"internal": link_counts["internal"], "external": link_counts["external"],
                      "broken_internal": link_counts["broken_internal"], "broken_external": link_counts["broken_external"],
                      "external_checked": len(external_status)},
            "images_checked": len(image_status),
            "redirects": {"total": len(redirect_rows), "chains": sum(1 for r in redirect_rows if r["hops"] > 1),
                          "loops": sum(1 for r in redirect_rows if r["outcome"] == "loop")},
            "duplicates": dup_groups,
            "schema": {"pages_with_schema": pages_with_schema, "types": dict(schema_types.most_common(40))},
            "hreflang_pages": len(hreflang_of),
            "sitemap": {**sitemap.to_dict(),
                        "urls_crawled": sum(1 for p in pages if p.in_sitemap),
                        "with_lastmod": sum(1 for v in sitemap.urls.values() if v.get("lastmod")),
                        "lastmod_by_year": dict(Counter(v["lastmod"][:4] for v in sitemap.urls.values() if v.get("lastmod"))),
                        "not_crawled": [u for u in sitemap.urls if u not in by_url][:200]},
            "site_checks": site_checks,
            "limit_reached": limit_hit,
        }
        crawl.stats = stats
        crawl.score = site_score
        crawl.pages_crawled = n
        return stats
