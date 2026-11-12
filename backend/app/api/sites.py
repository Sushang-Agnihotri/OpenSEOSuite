"""Sites, dashboard, competitors and jobs."""
from __future__ import annotations

from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..crawler.engine import CrawlConfig, run_crawl
from ..crawler.urls import normalize_url, registrable_domain
from ..db import get_db
from ..jobs import jobs
from ..models import Alert, Backlink, Competitor, Crawl, GscRow, Job, Keyword, Monitor, Site, User
from ..reports.exports import competitor_pdf
from ..security.auth import current_user, get_site_for
from ..services import competitors as comp_service
from .deps import checked_url, download, latest_crawl

router = APIRouter(tags=["sites"])


class SiteIn(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    url: str = Field(min_length=3, max_length=2048)
    crawl_config: CrawlConfig | None = None


class SitePatch(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    crawl_config: CrawlConfig | None = None
    gsc_property: str | None = Field(None, max_length=512)


class CompetitorIn(BaseModel):
    name: str | None = Field(None, max_length=255)
    url: str = Field(min_length=3, max_length=2048)


def crawl_out(c: Crawl, with_stats: bool = False) -> dict:
    out = {"id": c.id, "site_id": c.site_id, "competitor_id": c.competitor_id, "status": c.status, "start_url": c.start_url,
           "score": c.score, "pages_crawled": c.pages_crawled, "error": c.error, "job_id": c.job_id, "config": c.config,
           "created_at": c.created_at.isoformat() if c.created_at else None,
           "started_at": c.started_at.isoformat() if c.started_at else None,
           "finished_at": c.finished_at.isoformat() if c.finished_at else None,
           "issues_by_severity": (c.stats or {}).get("issues_by_severity")}
    if with_stats:
        out["stats"] = c.stats or {}
    return out


def site_out(db: Session, s: Site) -> dict:
    last = latest_crawl(db, s.id)
    active = db.scalar(select(Crawl).where(Crawl.site_id == s.id, Crawl.competitor_id.is_(None), Crawl.status.in_(("queued", "running"))).order_by(Crawl.id.desc()))
    return {"id": s.id, "name": s.name, "url": s.url, "domain": s.domain, "gsc_property": s.gsc_property,
            "crawl_config": CrawlConfig(**(s.crawl_config or {})).model_dump(), "created_at": s.created_at.isoformat(),
            "last_crawl": crawl_out(last) if last else None, "active_crawl": crawl_out(active) if active else None}


def start_crawl(db: Session, site: Site, user: User, config: CrawlConfig, competitor: Competitor | None = None) -> Crawl:
    """Create a crawl row and schedule it as a background job."""
    target = Crawl.competitor_id == competitor.id if competitor else Crawl.competitor_id.is_(None)
    busy = db.scalar(select(func.count()).select_from(Crawl).where(
        Crawl.site_id == site.id, Crawl.status.in_(("queued", "running")), target))
    if busy:
        raise HTTPException(409, "A crawl is already running for this target")
    crawl = Crawl(site_id=site.id, competitor_id=competitor.id if competitor else None,
                  start_url=competitor.url if competitor else site.url, config=config.model_dump())
    db.add(crawl)
    db.commit()
    crawl_id = crawl.id

    async def _job(ctx):
        return await run_crawl(crawl_id, ctx)

    crawl.job_id = jobs.start("competitor_crawl" if competitor else "crawl", _job, owner_id=user.id, site_id=site.id)
    db.commit()
    return crawl


# ----------------------------------------------------------------------------- sites
@router.get("/sites")
def list_sites(user: User = Depends(current_user), db: Session = Depends(get_db)) -> list[dict]:
    return [site_out(db, s) for s in db.scalars(select(Site).where(Site.owner_id == user.id).order_by(Site.name))]


@router.post("/sites", status_code=201)
def create_site(body: SiteIn, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    url = normalize_url(checked_url(body.url))
    if not url:
        raise HTTPException(422, "Invalid URL")
    site = Site(owner_id=user.id, name=body.name.strip(), url=url, domain=registrable_domain(urlsplit(url).hostname or ""),
                crawl_config=(body.crawl_config or CrawlConfig()).model_dump())
    db.add(site)
    db.commit()
    return site_out(db, site)


@router.get("/sites/{site_id}")
def get_site(site_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    return site_out(db, get_site_for(db, user, site_id))


@router.patch("/sites/{site_id}")
def update_site(site_id: int, body: SitePatch, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    site = get_site_for(db, user, site_id)
    if body.name is not None:
        site.name = body.name.strip()
    if body.crawl_config is not None:
        site.crawl_config = body.crawl_config.model_dump()
    if body.gsc_property is not None:
        site.gsc_property = body.gsc_property or None
    db.commit()
    return site_out(db, site)


@router.delete("/sites/{site_id}", status_code=204)
def delete_site(site_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)) -> None:
    site = get_site_for(db, user, site_id)
    if db.scalar(select(func.count()).select_from(Crawl).where(Crawl.site_id == site.id, Crawl.status.in_(("queued", "running")))):
        raise HTTPException(409, "A crawl is still running for this site. Cancel it and try again.")
    db.delete(site)
    db.commit()


@router.get("/sites/{site_id}/overview")
def site_overview(site_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    site = get_site_for(db, user, site_id)
    history = db.scalars(select(Crawl).where(Crawl.site_id == site.id, Crawl.competitor_id.is_(None), Crawl.status == "completed")
                         .order_by(Crawl.id.desc()).limit(30)).all()
    last = history[0] if history else None
    return {
        "site": site_out(db, site),
        "latest": crawl_out(last, with_stats=True) if last else None,
        "history": [{"id": c.id, "date": c.finished_at.isoformat() if c.finished_at else None, "score": c.score, "pages": c.pages_crawled,
                     **{k: (c.stats or {}).get("issues_by_severity", {}).get(k, 0) for k in ("critical", "high", "medium", "low")}}
                    for c in reversed(history)],
        "counts": {
            "keywords": db.scalar(select(func.count()).select_from(Keyword).where(Keyword.site_id == site.id)),
            "backlinks": db.scalar(select(func.count()).select_from(Backlink).where(Backlink.site_id == site.id)),
            "competitors": db.scalar(select(func.count()).select_from(Competitor).where(Competitor.site_id == site.id)),
            "monitors": db.scalar(select(func.count()).select_from(Monitor).where(Monitor.site_id == site.id, Monitor.enabled.is_(True))),
            "unread_alerts": db.scalar(select(func.count()).select_from(Alert).where(Alert.site_id == site.id, Alert.read.is_(False))),
            "gsc_rows": db.scalar(select(func.count()).select_from(GscRow).where(GscRow.site_id == site.id)),
        },
    }


@router.get("/dashboard")
def dashboard(user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    sites = db.scalars(select(Site).where(Site.owner_id == user.id).order_by(Site.name)).all()
    site_ids = [s.id for s in sites]
    alerts = db.scalars(select(Alert).where(Alert.site_id.in_(site_ids)).order_by(Alert.created_at.desc()).limit(10)).all() if site_ids else []
    recent_jobs = db.scalars(select(Job).where(Job.owner_id == user.id).order_by(Job.id.desc()).limit(8)).all()
    names = {s.id: s.name for s in sites}
    return {
        "sites": [site_out(db, s) for s in sites],
        "alerts": [{"id": a.id, "site": names.get(a.site_id), "site_id": a.site_id, "severity": a.severity, "title": a.title,
                    "created_at": a.created_at.isoformat(), "read": a.read} for a in alerts],
        "jobs": [job_out(j) for j in recent_jobs],
    }


# ----------------------------------------------------------------------------- competitors
@router.get("/sites/{site_id}/competitors")
def competitor_comparison(site_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    return comp_service.compare(db, get_site_for(db, user, site_id))


@router.post("/sites/{site_id}/competitors", status_code=201)
def add_competitor(site_id: int, body: CompetitorIn, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    site = get_site_for(db, user, site_id)
    url = normalize_url(checked_url(body.url))
    if not url:
        raise HTTPException(422, "Invalid URL")
    if db.scalar(select(func.count()).select_from(Competitor).where(Competitor.site_id == site.id)) >= 10:
        raise HTTPException(400, "A site can have at most 10 competitors")
    domain = registrable_domain(urlsplit(url).hostname or "")
    comp = Competitor(site_id=site.id, name=(body.name or domain).strip(), url=url, domain=domain)
    db.add(comp)
    db.commit()
    return {"id": comp.id, "name": comp.name, "url": comp.url, "domain": comp.domain}


@router.delete("/sites/{site_id}/competitors/{competitor_id}", status_code=204)
def delete_competitor(site_id: int, competitor_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)) -> None:
    site = get_site_for(db, user, site_id)
    comp = db.get(Competitor, competitor_id)
    if comp is None or comp.site_id != site.id:
        raise HTTPException(404, "Competitor not found")
    db.delete(comp)
    db.commit()


class CompetitorCrawlIn(BaseModel):
    max_urls: int = Field(150, ge=1, le=5000)


@router.post("/sites/{site_id}/competitors/{competitor_id}/crawl", status_code=202)
async def crawl_competitor(site_id: int, competitor_id: int, body: CompetitorCrawlIn | None = None,
                           user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    site = get_site_for(db, user, site_id)
    comp = db.get(Competitor, competitor_id)
    if comp is None or comp.site_id != site.id:
        raise HTTPException(404, "Competitor not found")
    cfg = CrawlConfig(max_urls=(body or CompetitorCrawlIn()).max_urls, check_external_links=False, check_images=False, delay_ms=500, concurrency=3)
    return crawl_out(start_crawl(db, site, user, cfg, comp))


@router.get("/sites/{site_id}/competitors/report.pdf")
def competitor_report(site_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    site = get_site_for(db, user, site_id)
    return download(competitor_pdf(comp_service.compare(db, site)), f"competitors-{site.domain}.pdf", "application/pdf")


# ----------------------------------------------------------------------------- jobs
def job_out(j: Job) -> dict:
    return {"id": j.id, "kind": j.kind, "status": j.status, "progress": j.progress, "message": j.message, "site_id": j.site_id,
            "error": j.error, "result": j.result, "created_at": j.created_at.isoformat(),
            "finished_at": j.finished_at.isoformat() if j.finished_at else None}


@router.get("/jobs")
def list_jobs(limit: int = 30, user: User = Depends(current_user), db: Session = Depends(get_db)) -> list[dict]:
    return [job_out(j) for j in db.scalars(select(Job).where(Job.owner_id == user.id).order_by(Job.id.desc()).limit(min(limit, 200)))]


@router.get("/jobs/{job_id}")
def get_job(job_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    job = db.get(Job, job_id)
    if job is None or job.owner_id != user.id:
        raise HTTPException(404, "Job not found")
    return job_out(job)


@router.post("/jobs/{job_id}/cancel")
def cancel_job(job_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    job = db.get(Job, job_id)
    if job is None or job.owner_id != user.id:
        raise HTTPException(404, "Job not found")
    return {"cancelled": jobs.cancel(job_id)}
