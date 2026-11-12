"""Crawl orchestration: frontier, workers, persistence and hand-off to the site-wide analysis."""
from __future__ import annotations

import asyncio
import logging
import re
from urllib.parse import urlsplit

from pydantic import BaseModel, Field, field_validator
from sqlalchemy import insert, select, update

from ..audit.page_checks import check_page, check_url, indexability, robots_directives
from ..audit.rules import RULES
from ..config import get_settings
from ..db import session_scope
from ..jobs import JobContext
from ..models import Crawl, Issue, Link, Page, utcnow
from .fetcher import REDIRECT_CODES, Fetcher, FetchResult
from .parser import ParsedPage, parse_html
from .robots import RobotsRules
from .sitemaps import SitemapReport, discover_sitemaps
from .urls import Scope, normalize_url, strip_www

log = logging.getLogger("seo.crawler")
FLUSH_EVERY = 40


class CrawlConfig(BaseModel):
    max_urls: int = Field(500, ge=1)
    max_depth: int = Field(15, ge=0, le=100)
    concurrency: int = Field(5, ge=1, le=32)
    delay_ms: int = Field(200, ge=0, le=60_000)
    timeout_s: float = Field(20, ge=2, le=120)
    retries: int = Field(2, ge=0, le=5)
    respect_robots: bool = True
    include_subdomains: bool = False
    use_sitemaps: bool = True
    follow_nofollow: bool = False
    check_external_links: bool = True
    max_external_links: int = Field(500, ge=0, le=20_000)
    check_images: bool = True
    max_images: int = Field(300, ge=0, le=5_000)
    render_js: bool = False
    user_agent: str | None = Field(None, max_length=300)
    include_patterns: list[str] = Field(default_factory=list, max_length=20)
    exclude_patterns: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("include_patterns", "exclude_patterns")
    @classmethod
    def _valid_regex(cls, v: list[str]) -> list[str]:
        for p in v:
            if len(p) > 200:
                raise ValueError("pattern too long")
            re.compile(p)
        return v

    @field_validator("max_urls")
    @classmethod
    def _cap(cls, v: int) -> int:
        return min(v, get_settings().crawl_max_urls_hard_limit)


class Crawler:
    def __init__(self, crawl_id: int, ctx: JobContext | None = None) -> None:
        self.crawl_id = crawl_id
        self.ctx = ctx
        with session_scope() as db:
            crawl = db.get(Crawl, crawl_id)
            self.start_url = normalize_url(crawl.start_url) or crawl.start_url
            self.cfg = CrawlConfig(**(crawl.config or {}))
        s = get_settings()
        self.user_agent = self.cfg.user_agent or s.user_agent
        self.fetcher = Fetcher(user_agent=self.user_agent, timeout_s=self.cfg.timeout_s, retries=self.cfg.retries,
                               delay_s=self.cfg.delay_ms / 1000, concurrency=self.cfg.concurrency)
        self.scope = Scope(self.start_url, self.cfg.include_subdomains)
        self.extra_hosts: set[str] = set()
        self.robots: dict[str, RobotsRules] = {}
        self._robots_locks: dict[str, asyncio.Lock] = {}
        self.sitemap = SitemapReport()
        self.depths: dict[str, int | None] = {}
        self.found_via: dict[str, str] = {}
        self.queue: asyncio.Queue = asyncio.Queue()
        self.buffer: list[dict] = []
        self.crawled = 0
        self.limit_hit = False
        self.external_redirect_targets: set[str] = set()
        self.image_urls: dict[str, None] = {}
        self.site_checks: dict = {}
        self.renderer = None
        self._include = [re.compile(p) for p in self.cfg.include_patterns]
        self._exclude = [re.compile(p) for p in self.cfg.exclude_patterns]

    # ------------------------------------------------------------------ scope / robots
    def in_scope(self, url: str) -> bool:
        return self.scope.contains(url) or strip_www(urlsplit(url).hostname or "") in self.extra_hosts

    def _wanted(self, url: str) -> bool:
        if self._exclude and any(p.search(url) for p in self._exclude):
            return False
        return not self._include or any(p.search(url) for p in self._include) or url == self.start_url

    async def robots_for(self, url: str) -> RobotsRules:
        p = urlsplit(url)
        origin = f"{p.scheme}://{p.netloc}"
        if origin in self.robots:
            return self.robots[origin]
        lock = self._robots_locks.setdefault(origin, asyncio.Lock())
        async with lock:
            if origin not in self.robots:
                res = await self.fetcher.fetch_following(f"{origin}/robots.txt", max_body=512 * 1024)
                status = res.status if res.status is not None else 599
                text = res.body.decode("utf-8", "replace") if res.status == 200 else ""
                if res.status == 200 and "<html" in text[:500].lower():
                    status, text = 404, ""  # soft 404 page served for robots.txt
                rules = RobotsRules(text, status)
                self.robots[origin] = rules
                delay = rules.crawl_delay(self.user_agent)
                if delay and self.cfg.respect_robots:
                    self.fetcher.throttle.overrides[p.hostname or ""] = min(delay, 30.0)
        return self.robots[origin]

    # ------------------------------------------------------------------ frontier
    def enqueue(self, url: str, depth: int | None, via: str) -> None:
        if url in self.depths:
            return
        if depth is not None and depth > self.cfg.max_depth:
            return
        if not self._wanted(url):
            return
        if len(self.depths) >= self.cfg.max_urls:
            self.limit_hit = True
            return
        self.depths[url] = depth
        self.found_via[url] = via
        self.queue.put_nowait(url)

    async def _worker(self) -> None:
        while True:
            url = await self.queue.get()
            try:
                await self._process(url)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 - one bad page must not stop the crawl
                log.exception("error processing %s", url)
                self.buffer.append({"page": self._row(url, error=f"internal error: {exc}"[:300]), "links": [], "issues": [("fetch_error", {"error": str(exc)[:200]})]})
            finally:
                self.crawled += 1
                self.queue.task_done()
                if len(self.buffer) >= FLUSH_EVERY:
                    await self._flush()
                if self.ctx:
                    self.ctx.update(min(0.8, 0.8 * self.crawled / max(len(self.depths), 1)),
                                    f"Crawled {self.crawled} of {len(self.depths)} discovered URLs")

    def _row(self, url: str, **extra) -> dict:
        row = {"crawl_id": self.crawl_id, "url": url, "depth": self.depths.get(url),
               "found_via": self.found_via.get(url, "link"), "in_sitemap": url in self.sitemap.urls,
               "data": {}}
        row.update(extra)
        return row

    async def _process(self, url: str) -> None:
        depth = self.depths.get(url)
        if self.cfg.respect_robots:
            rules = await self.robots_for(url)
            if not rules.allowed(url, self.user_agent):
                self.buffer.append({"page": self._row(url, blocked_by_robots=True, indexability_reason="blocked by robots.txt"),
                                    "links": [], "issues": [("blocked_by_robots", {})]})
                return
        res = await self.fetcher.fetch(url, text_only=True)
        row = self._row(url, status_code=res.status, error=res.error, content_type=res.content_type or None,
                        response_ms=res.elapsed_ms,
                        size_bytes=len(res.body) or int(res.headers.get("content-length", "0") or 0 if (res.headers.get("content-length") or "0").isdigit() else 0))
        findings: list[tuple[str, dict]] = []
        links: list[dict] = []
        x_robots = res.headers.get("x-robots-tag")

        if res.status is None:
            row["indexability_reason"] = "fetch error"
            findings.append(("fetch_error", {"error": res.error}))
        elif res.status in REDIRECT_CODES and res.redirect_to:
            row["redirect_to"] = res.redirect_to
            row["indexability_reason"] = "redirect"
            if url == self.start_url and not self.in_scope(res.redirect_to):
                self.extra_hosts.add(strip_www(urlsplit(res.redirect_to).hostname or ""))
            if self.in_scope(res.redirect_to):
                self.enqueue(res.redirect_to, depth, "redirect")
            else:
                self.external_redirect_targets.add(res.redirect_to)
            if res.status in (302, 303, 307):
                findings.append(("redirect_temporary", {"status": res.status, "target": res.redirect_to}))
        elif res.status >= 500:
            row["indexability_reason"] = "server error"
            findings.append(("http_5xx", {"status": res.status}))
        elif res.status >= 400:
            row["indexability_reason"] = "client error"
            findings.append(("http_4xx", {"status": res.status}))
        elif res.is_html and res.body:
            body = res.body
            rendered = False
            if self.renderer is not None:
                html = await self.renderer.render(url)
                if html:
                    body, rendered = html.encode("utf-8"), True
            parsed: ParsedPage = await asyncio.to_thread(
                parse_html, body, url, "text/html; charset=utf-8" if rendered else res.headers.get("content-type", ""))
            directives = robots_directives(parsed.meta_robots, x_robots)
            ok, reason = indexability(res.status, True, directives, parsed.canonical, url)
            h1 = next((h["text"] for h in parsed.headings if h["level"] == 1 and h["text"]), None)
            data = parsed.to_data()
            data["x_robots_tag"] = x_robots
            data["rendered"] = rendered
            data["truncated"] = res.truncated
            data["hsts"] = bool(res.headers.get("strict-transport-security"))
            row.update(is_html=True, indexable=ok, indexability_reason=reason, title=parsed.title,
                       meta_description=parsed.meta_description, h1=h1, canonical=parsed.canonical,
                       meta_robots=parsed.meta_robots, lang=parsed.lang, word_count=parsed.word_count,
                       content_hash=parsed.content_hash, simhash=parsed.simhash, text=parsed.text, data=data)
            findings.extend(check_page(url, parsed, status=res.status, headers=res.headers, size=len(res.body),
                                       elapsed_ms=res.elapsed_ms, indexable=ok, directives=directives))
            page_nofollow = "nofollow" in directives
            internal = external = 0
            seen_targets: set[tuple[str, str]] = set()
            for link in parsed.links:
                target = link["url"]
                key = (target, link["anchor"])
                if key in seen_targets:
                    continue
                seen_targets.add(key)
                is_internal = self.in_scope(target)
                nofollow = link["nofollow"] or page_nofollow
                links.append({"crawl_id": self.crawl_id, "source_url": url, "target_url": target,
                              "anchor": link["anchor"] or None, "kind": "a", "nofollow": nofollow, "is_internal": is_internal})
                if is_internal:
                    internal += 1
                    if not nofollow or self.cfg.follow_nofollow:
                        self.enqueue(target, None if depth is None else depth + 1, "link")
                else:
                    external += 1
            row["outlinks"], row["external_outlinks"] = internal, external
            if any(lk["nofollow"] and lk["is_internal"] for lk in links) and not page_nofollow:
                findings.append(("nofollow_internal", {"count": sum(1 for lk in links if lk["nofollow"] and lk["is_internal"])}))
            if parsed.canonical and parsed.canonical != url and self.in_scope(parsed.canonical):
                self.enqueue(parsed.canonical, None, "canonical")
            for alt in parsed.hreflang:
                if alt["href"].startswith("http") and self.in_scope(alt["href"]):
                    self.enqueue(alt["href"], None, "hreflang")
            if self.cfg.check_images:
                for img in parsed.images:
                    if len(self.image_urls) >= self.cfg.max_images:
                        break
                    if img["src"].startswith("http"):
                        self.image_urls.setdefault(img["src"], None)
        else:
            row["indexability_reason"] = "non-HTML"

        if row.get("is_html") or (res.status and res.status < 300):
            findings.extend(check_url(url))
        self.buffer.append({"page": row, "links": links, "issues": findings})

    # ------------------------------------------------------------------ persistence
    async def _flush(self) -> None:
        batch, self.buffer = self.buffer, []
        if batch:
            await asyncio.to_thread(self._flush_sync, batch)

    def _flush_sync(self, batch: list[dict]) -> None:
        with session_scope() as db:
            pages = [Page(**item["page"]) for item in batch]
            db.add_all(pages)
            db.flush()
            link_rows: list[dict] = []
            issue_rows: list[dict] = []
            for page, item in zip(pages, batch, strict=True):
                for link in item["links"]:
                    link["source_page_id"] = page.id
                    link_rows.append(link)
                for rule_id, details in item["issues"]:
                    rule = RULES[rule_id]
                    issue_rows.append({"crawl_id": self.crawl_id, "page_id": page.id, "url": page.url, "rule_id": rule_id,
                                       "severity": rule.severity, "category": rule.category, "details": details})
            if link_rows:
                db.execute(insert(Link), link_rows)
            if issue_rows:
                db.execute(insert(Issue), issue_rows)
            crawl = db.get(Crawl, self.crawl_id)
            crawl.pages_crawled = (crawl.pages_crawled or 0) + len(pages)

    # ------------------------------------------------------------------ site-level network checks
    async def _site_checks(self) -> None:
        p = urlsplit(self.start_url)
        host = p.hostname or ""
        checks: dict = {}
        rules = self.robots.get(f"{p.scheme}://{p.netloc}")
        if rules is not None:
            checks["robots"] = {"status": rules.status, "present": rules.present, "errors": rules.errors[:20],
                                "sitemaps": rules.sitemaps[:50], "blocks_start": not rules.allowed(self.start_url, self.user_agent),
                                "crawl_delay": rules.crawl_delay(self.user_agent)}
        if p.scheme == "https" and p.port is None:
            res = await self.fetcher.fetch(f"http://{host}{p.path or '/'}", "GET", max_body=4096)
            checks["http_version"] = {"status": res.status, "redirect_to": res.redirect_to, "error": res.error}
        if host.count(".") >= 1 and not re.fullmatch(r"[\d.]+", host) and p.port is None:
            variant = host[4:] if host.startswith("www.") else f"www.{host}"
            res = await self.fetcher.fetch_following(f"{p.scheme}://{variant}/", "GET", max_body=4096)
            final_host = urlsplit(res.final_url or "").hostname
            checks["host_variant"] = {"host": variant, "status": res.status, "final_host": final_host, "error": res.error}
        self.site_checks = checks

    async def _check_targets(self, urls: list[str], image: bool = False) -> dict[str, dict]:
        results: dict[str, dict] = {}
        sem = asyncio.Semaphore(self.cfg.concurrency * 2)
        done = 0

        async def one(u: str) -> None:
            nonlocal done
            async with sem:
                res: FetchResult = await self.fetcher.check(u)
                entry = {"status": res.status, "error": res.error, "hops": max(0, len(res.chain) - 1), "final_url": res.final_url}
                if image:
                    cl = res.headers.get("content-length", "")
                    entry["bytes"] = int(cl) if cl.isdigit() else None
                    entry["type"] = res.content_type
                results[u] = entry
                done += 1
                if self.ctx:
                    self.ctx.update(None, f"Checking {'images' if image else 'external links'}: {done}/{len(urls)}")

        await asyncio.gather(*(one(u) for u in urls))
        return results

    # ------------------------------------------------------------------ main
    async def run(self) -> dict:
        from ..audit.analysis import analyse_crawl  # local import: analysis imports crawler helpers

        self._set(status="running", started_at=utcnow())
        workers: list[asyncio.Task] = []
        try:
            if self.cfg.render_js:
                from .render import Renderer, playwright_available
                if not playwright_available():
                    raise RuntimeError("JavaScript rendering requested but Playwright is not installed "
                                       "(pip install playwright && playwright install chromium)")
                self.renderer = Renderer(self.user_agent, self.fetcher.allow_private, self.cfg.timeout_s)
                await self.renderer.start()

            rules = await self.robots_for(self.start_url)
            if self.cfg.use_sitemaps:
                if self.ctx:
                    self.ctx.update(0.01, "Discovering sitemaps", force=True)
                self.sitemap = await discover_sitemaps(self.fetcher, self.start_url, rules.sitemaps,
                                                       max_urls=max(self.cfg.max_urls * 4, 5000))
            workers = [asyncio.create_task(self._worker()) for _ in range(self.cfg.concurrency)]
            self.enqueue(self.start_url, 0, "start")
            await self.queue.join()
            if self.cfg.use_sitemaps:  # URLs only the sitemap knows about (orphan candidates)
                for loc in self.sitemap.urls:
                    if loc not in self.depths and self.in_scope(loc):
                        self.enqueue(loc, None, "sitemap")
                await self.queue.join()
            await self._flush()

            if self.ctx:
                self.ctx.update(0.82, "Running site-level checks", force=True)
            await self._site_checks()
            link_status: dict[str, dict] = {}
            if self.cfg.check_external_links and self.cfg.max_external_links:
                with session_scope() as db:
                    ext = list(db.scalars(select(Link.target_url).where(Link.crawl_id == self.crawl_id, Link.is_internal.is_(False))
                                          .distinct().limit(self.cfg.max_external_links)))
                targets = list(dict.fromkeys(ext + sorted(self.external_redirect_targets)))[: self.cfg.max_external_links]
                link_status = await self._check_targets(targets)
            image_status = await self._check_targets(list(self.image_urls)[: self.cfg.max_images], image=True) if self.image_urls else {}

            if self.ctx:
                self.ctx.update(0.9, "Analysing site structure and issues", force=True)
            stats = await asyncio.to_thread(
                analyse_crawl, self.crawl_id, sitemap=self.sitemap, site_checks=self.site_checks,
                external_status=link_status, image_status=image_status, limit_hit=self.limit_hit)
            self._set(status="completed", finished_at=utcnow())
            return {"crawl_id": self.crawl_id, "pages": self.crawled, "score": stats.get("score")}
        except asyncio.CancelledError:
            await self._flush()
            self._set(status="cancelled", finished_at=utcnow())
            raise
        except Exception as exc:
            await self._flush()
            self._set(status="failed", finished_at=utcnow(), error=f"{type(exc).__name__}: {exc}"[:1000])
            raise
        finally:
            for w in workers:
                w.cancel()
            await asyncio.gather(*workers, return_exceptions=True)
            if self.renderer is not None:
                await self.renderer.close()
            await self.fetcher.close()

    def _set(self, **fields) -> None:
        with session_scope() as db:
            db.execute(update(Crawl).where(Crawl.id == self.crawl_id).values(**fields))


async def run_crawl(crawl_id: int, ctx: JobContext | None = None) -> dict:
    return await Crawler(crawl_id, ctx).run()
