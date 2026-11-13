"""Scheduled monitoring: uptime, recurring audits, sitemap changes, metadata changes, competitor changes and
Search Console keyword tracking. A lightweight in-process scheduler checks for due monitors once a minute."""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

from sqlalchemy import func, select

from ..crawler.engine import CrawlConfig, run_crawl
from ..crawler.fetcher import Fetcher
from ..crawler.parser import parse_html
from ..crawler.robots import RobotsRules
from ..crawler.sitemaps import discover_sitemaps
from ..db import session_scope
from ..jobs import JobContext, JobLimitError, jobs
from ..models import Alert, Competitor, Crawl, GscRow, Keyword, Monitor, Page, Site, utcnow

log = logging.getLogger("seo.monitor")
KINDS = {
    "uptime": "Page availability (HTTP status of key URLs)",
    "audit": "Recurring technical audit (crawl, compare with the previous one, includes broken links)",
    "sitemap": "Sitemap change detection (URLs added or removed)",
    "metadata": "Metadata change detection (title, description, canonical, robots, H1)",
    "competitor": "Competitor monitoring (home-page metadata and sitemap changes)",
    "gsc": "Keyword tracking via Search Console (position changes of saved keywords)",
}
DEFAULT_INTERVAL = {"uptime": 1, "audit": 168, "sitemap": 24, "metadata": 24, "competitor": 24, "gsc": 24}


async def _snapshot(fetcher: Fetcher, url: str) -> dict:
    res = await fetcher.fetch_following(url, max_body=3_000_000)
    snap = {"status": res.status, "error": res.error, "final_url": res.final_url}
    if res.status == 200 and res.is_html:
        p = await asyncio.to_thread(parse_html, res.body, res.final_url or url, res.headers.get("content-type", ""))
        snap.update(title=p.title, description=p.meta_description, canonical=p.canonical, robots=p.meta_robots,
                    h1=next((h["text"] for h in p.headings if h["level"] == 1), None))
    return snap


async def _sitemap_urls(fetcher: Fetcher, url: str) -> list[str]:
    from urllib.parse import urlsplit

    p = urlsplit(url)
    res = await fetcher.fetch_following(f"{p.scheme}://{p.netloc}/robots.txt", max_body=512_000)
    rules = RobotsRules(res.body.decode("utf-8", "replace") if res.status == 200 else "", res.status or 599)
    report = await discover_sitemaps(fetcher, url, rules.sitemaps, max_urls=50_000)
    return sorted(report.urls)


def _diff_meta(label: str, url: str, old: dict, new: dict) -> list[dict]:
    alerts = []
    for field in ("title", "description", "canonical", "robots", "h1"):
        if old.get(field) != new.get(field):
            sev = "high" if field in ("robots", "canonical") else "medium"
            alerts.append({"severity": sev, "title": f"{label}: {field} changed", "message": f"{url}\nBefore: {old.get(field)!r}\nNow: {new.get(field)!r}",
                           "data": {"url": url, "field": field, "before": old.get(field), "after": new.get(field)}})
    return alerts


async def run_monitor(monitor_id: int, ctx: JobContext | None = None) -> dict:
    with session_scope() as db:
        mon = db.get(Monitor, monitor_id)
        if mon is None:
            return {}
        site = db.get(Site, mon.site_id)
        kind, cfg, state = mon.kind, dict(mon.config or {}), dict(mon.state or {})
        site_id, site_url, owner_id = site.id, site.url, site.owner_id
        crawl_cfg = dict(site.crawl_config or {})
        competitors = [(c.id, c.name, c.url) for c in db.scalars(select(Competitor).where(Competitor.site_id == site.id))]
        gsc_prop = site.gsc_property
    alerts: list[dict] = []
    status = "ok"
    first_run = not state

    if kind in ("uptime", "metadata", "sitemap", "competitor"):
        async with Fetcher(timeout_s=20, retries=1, delay_s=0.3, concurrency=4) as fetcher:
            if kind == "uptime":
                urls = cfg.get("urls") or [site_url]
                for url in urls[:50]:
                    res = await fetcher.fetch_following(url, max_body=65_536)
                    ok = res.status is not None and res.status < 400
                    was_ok = state.get(url, {}).get("ok", True)
                    if not ok:
                        status = "problem"
                        if was_ok:
                            alerts.append({"severity": "critical", "title": "Page is down", "message": f"{url} answered {res.status or res.error}",
                                           "data": {"url": url, "status": res.status, "error": res.error}})
                    elif not was_ok:
                        alerts.append({"severity": "low", "title": "Page recovered", "message": f"{url} is reachable again (HTTP {res.status})", "data": {"url": url}})
                    state[url] = {"ok": ok, "status": res.status, "response_ms": res.elapsed_ms, "checked": utcnow().isoformat()}
            elif kind == "metadata":
                urls = cfg.get("urls")
                if not urls:
                    with session_scope() as db:
                        crawl = db.scalar(select(Crawl).where(Crawl.site_id == site_id, Crawl.competitor_id.is_(None), Crawl.status == "completed").order_by(Crawl.id.desc()))
                        urls = [site_url] + (list(db.scalars(select(Page.url).where(Page.crawl_id == crawl.id, Page.indexable.is_(True))
                                                             .order_by(Page.pagerank.desc()).limit(20))) if crawl else [])
                for url in list(dict.fromkeys(urls))[:50]:
                    snap = await _snapshot(fetcher, url)
                    if url in state:
                        alerts += _diff_meta("Metadata", url, state[url], snap)
                    state[url] = snap
            elif kind == "sitemap":
                urls = await _sitemap_urls(fetcher, site_url)
                if not first_run:
                    old = set(state.get("urls", []))
                    added, removed = sorted(set(urls) - old), sorted(old - set(urls))
                    if added or removed:
                        alerts.append({"severity": "medium" if removed else "low", "title": f"Sitemap changed: {len(added)} added, {len(removed)} removed",
                                       "message": "\n".join([f"+ {u}" for u in added[:20]] + [f"- {u}" for u in removed[:20]]),
                                       "data": {"added": added[:500], "removed": removed[:500]}})
                state = {"urls": urls[:50_000], "count": len(urls)}
            elif kind == "competitor":
                for cid, name, url in competitors:
                    key = str(cid)
                    snap = await _snapshot(fetcher, url)
                    sm = await _sitemap_urls(fetcher, url)
                    old = state.get(key)
                    if old:
                        alerts += _diff_meta(f"Competitor {name}", url, old.get("meta", {}), snap)
                        added = sorted(set(sm) - set(old.get("sitemap", [])))
                        if added and old.get("sitemap"):
                            alerts.append({"severity": "low", "title": f"Competitor {name} published {len(added)} new URL(s)",
                                           "message": "\n".join(added[:25]), "data": {"competitor": name, "added": added[:500]}})
                    state[key] = {"meta": snap, "sitemap": sm[:20_000]}
    elif kind == "audit":
        with session_scope() as db:
            prev = db.scalar(select(Crawl).where(Crawl.site_id == site_id, Crawl.competitor_id.is_(None), Crawl.status == "completed").order_by(Crawl.id.desc()))
            prev_stats, prev_score = (dict(prev.stats or {}), prev.score) if prev else ({}, None)
            config = CrawlConfig(**{**crawl_cfg, **(cfg.get("crawl") or {})}).model_dump()
            crawl = Crawl(site_id=site_id, start_url=site_url, config=config, job_id=ctx.job_id if ctx else None)
            db.add(crawl)
            db.flush()
            crawl_id = crawl.id
        await run_crawl(crawl_id, ctx)
        with session_scope() as db:
            crawl = db.get(Crawl, crawl_id)
            stats, score = dict(crawl.stats or {}), crawl.score
        if prev_score is not None and score is not None:
            if prev_score - score >= 3:
                alerts.append({"severity": "high", "title": f"SEO score dropped from {prev_score} to {score}",
                               "message": "The latest scheduled audit scored lower than the previous one.", "data": {"crawl_id": crawl_id}})
            before, now = prev_stats.get("issues_by_rule", {}), stats.get("issues_by_rule", {})
            from ..audit.rules import RULES
            new_rules = [r for r in now if r not in before and RULES[r].severity in ("critical", "high")]
            if new_rules:
                alerts.append({"severity": "high", "title": f"{len(new_rules)} new critical/high issue type(s)",
                               "message": "\n".join(f"{RULES[r].title}: {now[r]} URL(s)" for r in new_rules), "data": {"crawl_id": crawl_id, "rules": new_rules}})
            b_old, b_new = (prev_stats.get("links") or {}).get("broken_internal", 0), (stats.get("links") or {}).get("broken_internal", 0)
            if b_new > b_old:
                alerts.append({"severity": "high", "title": f"Broken internal links increased from {b_old} to {b_new}", "message": "", "data": {"crawl_id": crawl_id}})
        state = {"last_crawl_id": crawl_id, "score": score}
    elif kind == "gsc":
        from ..integrations import gsc
        with session_scope() as db:
            if gsc_prop and gsc.is_connected(db, owner_id):
                try:
                    await gsc.sync(db, owner_id, site_id, gsc_prop, days=int(cfg.get("days", 30)))
                except gsc.GscError as exc:
                    status = "problem"
                    alerts.append({"severity": "medium", "title": "Search Console sync failed", "message": str(exc), "data": {}})
            hi = db.scalar(select(func.max(GscRow.day)).where(GscRow.site_id == site_id, GscRow.dataset == "query_page"))
            tracked = [k.lower() for k in db.scalars(select(Keyword.keyword).where(Keyword.site_id == site_id))]
            if hi and tracked:
                def avg_pos(start, end):
                    q = (select(GscRow.query, func.sum(GscRow.position * GscRow.impressions) / func.nullif(func.sum(GscRow.impressions), 0))
                         .where(GscRow.site_id == site_id, GscRow.dataset == "query_page", GscRow.day.between(start, end), GscRow.query.in_(tracked))
                         .group_by(GscRow.query))
                    return {k: v for k, v in db.execute(q) if v is not None}
                now_p = avg_pos(hi - timedelta(days=6), hi)
                old_p = avg_pos(hi - timedelta(days=13), hi - timedelta(days=7))
                threshold = float(cfg.get("position_change", 3))
                for kw, pos in now_p.items():
                    if kw in old_p and abs(pos - old_p[kw]) >= threshold:
                        worse = pos > old_p[kw]
                        alerts.append({"severity": "high" if worse else "low",
                                       "title": f"“{kw}” {'dropped' if worse else 'improved'} from position {old_p[kw]:.1f} to {pos:.1f}",
                                       "message": "Average position over the last 7 days of Search Console data versus the 7 days before (measured).",
                                       "data": {"keyword": kw, "before": round(old_p[kw], 1), "after": round(pos, 1)}})
                state = {"positions": {k: round(v, 1) for k, v in now_p.items()}, "as_of": hi.isoformat()}
            elif not hi:
                status = "no data"
                state = {"note": "No Search Console data yet. Connect Search Console or import a CSV."}

    with session_scope() as db:
        mon = db.get(Monitor, monitor_id)
        if mon is None:
            return {}
        mon.state, mon.last_run, mon.last_status = state, utcnow(), status
        mon.next_run = utcnow() + timedelta(hours=mon.interval_hours)
        for a in alerts:
            db.add(Alert(site_id=site_id, monitor_id=monitor_id, **a))
    return {"monitor_id": monitor_id, "alerts": len(alerts), "status": status}


_active_monitors: set[int] = set()


class MonitorBusyError(RuntimeError):
    """The monitor (or its site's crawl) is already running."""


def start_monitor_job(monitor_id: int) -> int:
    if monitor_id in _active_monitors:
        raise MonitorBusyError("This monitor is already running")
    with session_scope() as db:
        mon = db.get(Monitor, monitor_id)
        site = db.get(Site, mon.site_id)
        owner_id, site_id, kind = site.owner_id, site.id, mon.kind
        if kind == "audit" and db.scalar(select(Crawl.id).where(Crawl.site_id == site_id, Crawl.status.in_(("queued", "running"))).limit(1)):
            raise MonitorBusyError("A crawl is already running for this site")
        mon.next_run = utcnow() + timedelta(hours=mon.interval_hours)  # avoid double scheduling while it runs

    async def _job(ctx: JobContext) -> dict:
        try:
            return await run_monitor(monitor_id, ctx)
        except Exception:
            with session_scope() as db:
                m = db.get(Monitor, monitor_id)
                if m:
                    m.last_run, m.last_status = utcnow(), "error"
            raise
        finally:
            _active_monitors.discard(monitor_id)

    _active_monitors.add(monitor_id)
    try:
        return jobs.start(f"monitor:{kind}", _job, owner_id=owner_id, site_id=site_id)
    except Exception:
        _active_monitors.discard(monitor_id)
        raise


async def scheduler_loop(interval_s: float = 60.0) -> None:
    """Runs forever: start a job for every enabled monitor whose next_run has passed."""
    await asyncio.sleep(5)
    while True:
        try:
            with session_scope() as db:
                due = list(db.scalars(select(Monitor.id).where(Monitor.enabled.is_(True), (Monitor.next_run.is_(None)) | (Monitor.next_run <= utcnow())).limit(20)))
            for mid in due:
                try:
                    start_monitor_job(mid)
                except (MonitorBusyError, JobLimitError):
                    continue  # still running, or its owner is at the job cap: try again next tick
        except Exception:  # noqa: BLE001 - the scheduler must survive transient database errors
            log.exception("scheduler tick failed")
        await asyncio.sleep(interval_s)
