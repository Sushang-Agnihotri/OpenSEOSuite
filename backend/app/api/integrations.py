"""Search Console, backlinks, monitoring/alerts, settings, AI and local-SEO citation imports."""
from __future__ import annotations

import csv
import io
from datetime import date, timedelta
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session

from ..audit.rules import RULES, rule_dict
from ..db import get_db, session_scope
from ..integrations import ai, gsc
from ..jobs import jobs
from ..models import Alert, Backlink, Citation, Crawl, GscRow, Issue, Link, Monitor, Page, Site, User, utcnow
from ..reports.exports import to_csv, to_xlsx
from ..security.auth import admin_user, create_access_token, current_user, decode_token, get_site_for
from ..services import backlinks as bl
from ..services import competitors as comp_service
from ..services import monitoring
from ..services.settings_store import DEFAULTS, get_setting, masked, set_setting
from .deps import download, get_crawl_for, latest_crawl, page_params, read_upload

router = APIRouter(tags=["integrations"])


# ----------------------------------------------------------------------------- Search Console
@router.get("/gsc/status")
def gsc_status(user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    cfg = get_setting(db, "gsc")
    return {"client_configured": bool(cfg.get("client_id") and cfg.get("client_secret")), "connected": gsc.is_connected(db, user.id),
            "redirect_uri": gsc.redirect_uri()}


@router.get("/gsc/auth-url")
def gsc_auth_url(user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    try:
        return {"url": gsc.auth_url(db, create_access_token(user.id, purpose="gsc_oauth", minutes=15))}
    except gsc.GscError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/gsc/callback", response_class=HTMLResponse, include_in_schema=False)
async def gsc_callback(code: str | None = None, state: str | None = None, error: str | None = None, db: Session = Depends(get_db)):
    """OAuth redirect target. The signed ``state`` identifies the user and protects against CSRF."""
    def page(msg: str) -> HTMLResponse:
        return HTMLResponse(f"<!doctype html><meta charset='utf-8'><title>Search Console</title><body style='font-family:system-ui;padding:3rem'>"
                            f"<h2>{msg}</h2><p><a href='/settings'>Return to the app</a></p></body>")
    if error or not code or not state:
        return page("Search Console connection was cancelled.")
    user_id = decode_token(state, purpose="gsc_oauth")
    try:
        await gsc.exchange_code(db, user_id, code)
        db.commit()
    except gsc.GscError:
        return page("Google rejected the request. Check the OAuth client settings and try again.")
    return page("Search Console connected. You can close this tab.")


@router.post("/gsc/disconnect")
def gsc_disconnect(user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    gsc.disconnect(db, user.id)
    db.commit()
    return {"ok": True}


@router.get("/gsc/properties")
async def gsc_properties(user: User = Depends(current_user), db: Session = Depends(get_db)) -> list[dict]:
    try:
        return await gsc.list_properties(db, user.id)
    except gsc.GscError as exc:
        raise HTTPException(400, str(exc)) from exc


class GscSyncIn(BaseModel):
    days: int = Field(90, ge=3, le=480)


@router.post("/sites/{site_id}/gsc/sync", status_code=202)
async def gsc_sync(site_id: int, body: GscSyncIn | None = None, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    site = get_site_for(db, user, site_id)
    if not site.gsc_property:
        raise HTTPException(400, "Choose a Search Console property for this site first")
    if not gsc.is_connected(db, user.id):
        raise HTTPException(400, "Search Console is not connected")
    days, prop, uid, sid = (body or GscSyncIn()).days, site.gsc_property, user.id, site.id

    async def _job(ctx):
        ctx.update(0.1, "Downloading Search Console data", force=True)
        with session_scope() as s:
            return await gsc.sync(s, uid, sid, prop, days)

    return {"job_id": jobs.start("gsc_sync", _job, owner_id=user.id, site_id=site.id)}


@router.post("/sites/{site_id}/gsc/import")
async def gsc_import(site_id: int, file: UploadFile, replace: bool = False, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    site = get_site_for(db, user, site_id)
    try:
        return gsc.import_csv(db, site.id, await read_upload(file), replace)
    except gsc.GscError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/sites/{site_id}/gsc/performance")
def gsc_performance(site_id: int, start: date | None = None, end: date | None = None, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    return gsc.performance(db, get_site_for(db, user, site_id).id, start, end)


@router.get("/sites/{site_id}/gsc/insights")
def gsc_insights(site_id: int, days: int = Query(28, ge=7, le=180), user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    return gsc.insights(db, get_site_for(db, user, site_id).id, days)


@router.delete("/sites/{site_id}/gsc/data", status_code=204)
def gsc_clear(site_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)) -> None:
    site = get_site_for(db, user, site_id)
    db.execute(delete(GscRow).where(GscRow.site_id == site.id))
    db.commit()


# ----------------------------------------------------------------------------- backlinks
@router.get("/sites/{site_id}/backlinks/summary")
def backlink_summary(site_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    return bl.summary(db, get_site_for(db, user, site_id))


@router.get("/sites/{site_id}/backlinks")
def backlink_list(site_id: int, q: str | None = Query(None, max_length=200), status: str | None = None, rel: str | None = None,
                  page: int = 1, per_page: int = 50, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    site = get_site_for(db, user, site_id)
    stmt = select(Backlink).where(Backlink.site_id == site.id)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(Backlink.source_url.ilike(like), Backlink.target_url.ilike(like), Backlink.anchor.ilike(like)))
    if status:
        stmt = stmt.where(Backlink.status == status)
    if rel in ("follow", "nofollow"):
        stmt = stmt.where(Backlink.nofollow.is_(rel == "nofollow"))
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    offset, limit = page_params(page, per_page)
    rows = db.scalars(stmt.order_by(Backlink.source_domain, Backlink.id).offset(offset).limit(limit)).all()
    return {"total": total, "page": page, "per_page": limit, "items": [_backlink_out(b) for b in rows]}


def _backlink_out(b: Backlink) -> dict:
    return {"id": b.id, "source_url": b.source_url, "source_domain": b.source_domain, "target_url": b.target_url, "anchor": b.anchor,
            "nofollow": b.nofollow, "origin": b.origin, "status": b.status, "http_status": b.http_status,
            "first_seen": b.first_seen.isoformat(), "last_checked": b.last_checked.isoformat() if b.last_checked else None}


@router.post("/sites/{site_id}/backlinks/import")
async def backlink_import(site_id: int, file: UploadFile, origin: str = Query("import", max_length=20, pattern=r"^[a-z0-9_-]+$"),
                          user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    site = get_site_for(db, user, site_id)
    try:
        return bl.import_csv(db, site, await read_upload(file), origin)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/sites/{site_id}/backlinks/verify", status_code=202)
async def backlink_verify(site_id: int, limit: int = Query(300, ge=1, le=5000), user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    site = get_site_for(db, user, site_id)
    sid = site.id

    async def _job(ctx):
        return await bl.verify_backlinks(sid, ctx, limit)

    return {"job_id": jobs.start("backlink_verify", _job, owner_id=user.id, site_id=site.id)}


@router.delete("/sites/{site_id}/backlinks", status_code=204)
def backlink_clear(site_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)) -> None:
    site = get_site_for(db, user, site_id)
    db.execute(delete(Backlink).where(Backlink.site_id == site.id))
    db.commit()


@router.get("/sites/{site_id}/backlinks/export")
def backlink_export(site_id: int, format: str = "csv", user: User = Depends(current_user), db: Session = Depends(get_db)):
    site = get_site_for(db, user, site_id)
    rows = [{k: v for k, v in _backlink_out(b).items() if k != "id"} for b in db.scalars(select(Backlink).where(Backlink.site_id == site.id).limit(200_000))]
    if format == "xlsx":
        s = bl.summary(db, site)
        return download(to_xlsx({"Backlinks": rows, "Referring domains": s.get("top_domains", []), "Anchors": s.get("top_anchors", [])}),
                        f"backlinks-{site.domain}.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    return download(to_csv(rows), f"backlinks-{site.domain}.csv", "text/csv")


# ----------------------------------------------------------------------------- local SEO citations
@router.post("/sites/{site_id}/citations/import")
async def citations_import(site_id: int, file: UploadFile, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    """CSV columns: source, url, name, address, phone (e.g. an export from a listings tool or a hand-made sheet)."""
    site = get_site_for(db, user, site_id)
    reader = csv.DictReader(io.StringIO((await read_upload(file)).decode("utf-8-sig", "replace")))
    db.execute(delete(Citation).where(Citation.site_id == site.id))
    n = 0
    for row in reader:
        r = {(k or "").strip().lower(): (v or "").strip() for k, v in row.items()}
        source = r.get("source") or r.get("directory") or r.get("site") or r.get("platform")
        if not source or n >= 5000:
            continue
        db.add(Citation(site_id=site.id, source=source[:255], url=(r.get("url") or r.get("listing url") or "")[:2048] or None,
                        name=(r.get("name") or r.get("business name") or "")[:255] or None,
                        address=(r.get("address") or "")[:500] or None, phone=(r.get("phone") or r.get("telephone") or "")[:60] or None))
        n += 1
    db.commit()
    return {"imported": n}


# ----------------------------------------------------------------------------- monitoring & alerts
class MonitorIn(BaseModel):
    kind: Literal["uptime", "audit", "sitemap", "metadata", "competitor", "gsc"]
    name: str | None = Field(None, max_length=255)
    interval_hours: float | None = Field(None, ge=0.25, le=24 * 60)
    config: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True


class MonitorPatch(BaseModel):
    name: str | None = Field(None, max_length=255)
    interval_hours: float | None = Field(None, ge=0.25, le=24 * 60)
    config: dict[str, Any] | None = None
    enabled: bool | None = None


def _monitor_out(m: Monitor) -> dict:
    state = m.state or {}
    summary = None
    if m.kind == "uptime":
        summary = {u: v for u, v in state.items() if isinstance(v, dict)}
    elif m.kind == "sitemap":
        summary = {"urls": state.get("count")}
    elif m.kind == "audit":
        summary = {k: state.get(k) for k in ("last_crawl_id", "score")}
    elif m.kind == "gsc":
        summary = {"tracked": len(state.get("positions", {})), "as_of": state.get("as_of"), "note": state.get("note")}
    return {"id": m.id, "site_id": m.site_id, "kind": m.kind, "kind_label": monitoring.KINDS[m.kind], "name": m.name,
            "interval_hours": m.interval_hours, "config": m.config, "enabled": m.enabled, "last_status": m.last_status,
            "last_run": m.last_run.isoformat() if m.last_run else None, "next_run": m.next_run.isoformat() if m.next_run else None,
            "summary": summary}


def _clean_config(config: dict) -> dict:
    from ..crawler.engine import CrawlConfig
    from .deps import checked_url
    out: dict[str, Any] = {}
    if isinstance(config.get("urls"), list):
        out["urls"] = [checked_url(str(u)) for u in config["urls"][:50]]
    if isinstance(config.get("crawl"), dict):
        out["crawl"] = CrawlConfig(**config["crawl"]).model_dump(exclude_unset=True)
    for key, lo, hi in (("position_change", 1, 50), ("days", 7, 180)):
        if key in config:
            out[key] = max(lo, min(hi, float(config[key])))
    return out


@router.get("/monitoring/kinds")
def monitor_kinds(user: User = Depends(current_user)) -> dict:
    return {"kinds": monitoring.KINDS, "default_interval_hours": monitoring.DEFAULT_INTERVAL}


@router.get("/sites/{site_id}/monitors")
def list_monitors(site_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)) -> list[dict]:
    site = get_site_for(db, user, site_id)
    return [_monitor_out(m) for m in db.scalars(select(Monitor).where(Monitor.site_id == site.id).order_by(Monitor.id))]


@router.post("/sites/{site_id}/monitors", status_code=201)
def create_monitor(site_id: int, body: MonitorIn, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    site = get_site_for(db, user, site_id)
    if db.scalar(select(func.count()).select_from(Monitor).where(Monitor.site_id == site.id)) >= 30:
        raise HTTPException(400, "A site can have at most 30 monitors")
    interval = body.interval_hours or monitoring.DEFAULT_INTERVAL[body.kind]
    if body.kind == "audit":
        interval = max(interval, 6)
    m = Monitor(site_id=site.id, kind=body.kind, name=body.name or monitoring.KINDS[body.kind].split(" (")[0], interval_hours=interval,
                config=_clean_config(body.config), enabled=body.enabled, next_run=utcnow())
    db.add(m)
    db.commit()
    return _monitor_out(m)


def _get_monitor(db: Session, user: User, monitor_id: int) -> Monitor:
    m = db.get(Monitor, monitor_id)
    if m is None:
        raise HTTPException(404, "Monitor not found")
    get_site_for(db, user, m.site_id)
    return m


@router.patch("/monitors/{monitor_id}")
def update_monitor(monitor_id: int, body: MonitorPatch, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    m = _get_monitor(db, user, monitor_id)
    if body.name is not None:
        m.name = body.name
    if body.interval_hours is not None:
        m.interval_hours = max(body.interval_hours, 6) if m.kind == "audit" else body.interval_hours
        m.next_run = utcnow() + timedelta(hours=m.interval_hours)
    if body.config is not None:
        m.config = _clean_config(body.config)
    if body.enabled is not None:
        m.enabled = body.enabled
    db.commit()
    return _monitor_out(m)


@router.delete("/monitors/{monitor_id}", status_code=204)
def delete_monitor(monitor_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)) -> None:
    db.delete(_get_monitor(db, user, monitor_id))
    db.commit()


@router.post("/monitors/{monitor_id}/run", status_code=202)
async def run_monitor_now(monitor_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    m = _get_monitor(db, user, monitor_id)
    return {"job_id": monitoring.start_monitor_job(m.id)}


@router.get("/alerts")
def list_alerts(site_id: int | None = None, unread: bool = False, page: int = 1, per_page: int = 50,
                user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    sites = {s.id: s.name for s in db.scalars(select(Site).where(Site.owner_id == user.id))}
    stmt = select(Alert).where(Alert.site_id.in_(list(sites) or [-1]))
    if site_id:
        stmt = stmt.where(Alert.site_id == site_id)
    if unread:
        stmt = stmt.where(Alert.read.is_(False))
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    offset, limit = page_params(page, per_page)
    rows = db.scalars(stmt.order_by(Alert.created_at.desc(), Alert.id.desc()).offset(offset).limit(limit)).all()
    return {"total": total, "unread": db.scalar(select(func.count()).select_from(Alert).where(Alert.site_id.in_(list(sites) or [-1]), Alert.read.is_(False))),
            "items": [{"id": a.id, "site_id": a.site_id, "site": sites.get(a.site_id), "severity": a.severity, "title": a.title, "message": a.message,
                       "data": a.data, "read": a.read, "created_at": a.created_at.isoformat()} for a in rows]}


class AlertsRead(BaseModel):
    ids: list[int] | None = None  # None = all


@router.post("/alerts/read")
def mark_alerts_read(body: AlertsRead, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    site_ids = list(db.scalars(select(Site.id).where(Site.owner_id == user.id)))
    stmt = select(Alert).where(Alert.site_id.in_(site_ids or [-1]), Alert.read.is_(False))
    if body.ids is not None:
        stmt = stmt.where(Alert.id.in_(body.ids[:5000]))
    n = 0
    for a in db.scalars(stmt):
        a.read = True
        n += 1
    db.commit()
    return {"updated": n}


@router.get("/alerts/export")
def export_alerts(user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = [{k: a[k] for k in ("created_at", "site", "severity", "title", "message", "read")} for a in list_alerts(None, False, 1, 500, user, db)["items"]]
    return download(to_csv(rows), "alerts.csv", "text/csv")


# ----------------------------------------------------------------------------- settings (admin)
@router.get("/settings")
def read_settings(user: User = Depends(admin_user), db: Session = Depends(get_db)) -> dict:
    return {k: masked(k, get_setting(db, k)) for k in DEFAULTS}


class SettingsIn(BaseModel):
    serp: dict[str, str] | None = None
    pagespeed: dict[str, str] | None = None
    ai: dict[str, str] | None = None
    gsc: dict[str, str] | None = None


@router.put("/settings")
def write_settings(body: SettingsIn, user: User = Depends(admin_user), db: Session = Depends(get_db)) -> dict:
    data = body.model_dump(exclude_none=True)
    if "serp" in data and data["serp"].get("provider") not in (None, "none", "searxng", "google_cse", "brave"):
        raise HTTPException(422, "Unknown SERP provider")
    if "ai" in data and data["ai"].get("provider") not in (None, "none", "ollama", "openai_compatible"):
        raise HTTPException(422, "Unknown AI provider")
    for key, value in data.items():
        for k, v in value.items():
            if len(v) > 2048:
                raise HTTPException(422, f"Value for {key}.{k} is too long")
            if k.endswith("url") and v and not v.startswith(("http://", "https://")):
                raise HTTPException(422, f"{key}.{k} must be an http(s) URL")
        set_setting(db, key, value)
    db.commit()
    return read_settings(user, db)


# ----------------------------------------------------------------------------- AI
class AITaskIn(BaseModel):
    task: str
    site_id: int | None = None
    crawl_id: int | None = None
    page_id: int | None = None
    rule_id: str | None = None
    keyword: str | None = Field(None, max_length=200)
    serp: dict[str, Any] | None = None  # result of /serp/analyze, passed back by the UI
    note: str = Field("", max_length=500)


@router.get("/ai/status")
async def ai_status(user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    st = await ai.status(get_setting(db, "ai"))
    st["tasks"] = {k: {"label": v["label"], "needs": v["needs"]} for k, v in ai.TASKS.items()}
    return st


def _audit_context(db: Session, crawl: Crawl) -> dict:
    stats = crawl.stats or {}
    rules = sorted(((r, c) for r, c in (stats.get("issues_by_rule") or {}).items() if r in RULES),
                   key=lambda rc: (["critical", "high", "medium", "low"].index(RULES[rc[0]].severity), -rc[1]))
    return {"site_score": crawl.score, "urls_crawled": stats.get("total_urls"), "indexable_pages": stats.get("indexable_pages"),
            "issues_by_severity": stats.get("issues_by_severity"), "links": stats.get("links"), "redirects": stats.get("redirects"),
            "issues": [{"title": RULES[r].title, "severity": RULES[r].severity, "affected_urls": c, "fix": RULES[r].fix} for r, c in rules[:40]]}


def _page_context(db: Session, crawl: Crawl, page_id: int) -> dict:
    p = db.get(Page, page_id)
    if p is None or p.crawl_id != crawl.id:
        raise HTTPException(404, "Page not found")
    text = db.scalar(select(Page.text).where(Page.id == p.id)) or ""
    data = p.data or {}
    return {"url": p.url, "title": p.title, "meta_description": p.meta_description, "h1": p.h1, "word_count": p.word_count,
            "headings": [f"H{h['level']}: {h['text']}" for h in (data.get("headings") or [])[:40]],
            "existing_schema_types": [i.get("@type") for i in (data.get("jsonld") or []) if isinstance(i, dict)],
            "content_excerpt": text[:5000]}


@router.post("/ai/run")
async def ai_run(body: AITaskIn, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    if body.task not in ai.TASKS:
        raise HTTPException(404, "Unknown AI task")
    needs = ai.TASKS[body.task]["needs"]
    crawl = get_crawl_for(db, user, body.crawl_id) if body.crawl_id else None
    site = get_site_for(db, user, body.site_id) if body.site_id else (db.get(Site, crawl.site_id) if crawl else None)
    if crawl is None and site is not None:
        crawl = latest_crawl(db, site.id)
    data: dict[str, Any] = {}
    if needs in ("audit", "issue", "page", "page_links", "gsc") and crawl is None and needs != "gsc":
        raise HTTPException(400, "This task needs a completed crawl")
    if needs == "audit":
        data = {"site": site.url if site else None, "audit": _audit_context(db, crawl)}
        if site and body.task == "action_plan":
            ins = gsc.insights(db, site.id)
            if ins.get("has_data"):
                data["search_console"] = {"opportunities": ins["opportunities"][:15], "declining_queries": ins["declining_queries"][:15]}
    elif needs == "issue":
        if not body.rule_id or body.rule_id not in RULES:
            raise HTTPException(400, "rule_id is required")
        rows = db.execute(select(Issue.url, Issue.details).where(Issue.crawl_id == crawl.id, Issue.rule_id == body.rule_id).limit(10)).all()
        total = db.scalar(select(func.count()).select_from(Issue).where(Issue.crawl_id == crawl.id, Issue.rule_id == body.rule_id))
        data = {"rule": rule_dict(body.rule_id), "affected_url_count": total, "examples": [{"url": u, "details": d} for u, d in rows]}
    elif needs == "page":
        if not body.page_id:
            raise HTTPException(400, "page_id is required")
        data = {"page": _page_context(db, crawl, body.page_id), "target_keyword": body.keyword}
    elif needs == "page_links":
        if not body.page_id:
            raise HTTPException(400, "page_id is required")
        target = _page_context(db, crawl, body.page_id)
        linked = set(db.scalars(select(Link.target_url).where(Link.crawl_id == crawl.id, Link.source_page_id == body.page_id)))
        cands = db.execute(select(Page.url, Page.title, Page.h1).where(Page.crawl_id == crawl.id, Page.indexable.is_(True), Page.id != body.page_id)
                           .order_by(Page.pagerank.desc()).limit(120)).all()
        data = {"target_page": target, "candidate_pages": [{"url": u, "title": t, "h1": h} for u, t, h in cands if u not in linked][:80]}
    elif needs == "competitors":
        if site is None:
            raise HTTPException(400, "site_id is required")
        cmp = comp_service.compare(db, site)
        for c in cmp["competitors"]:
            if c.get("profile"):
                c["profile"].get("keyword_overlap", {}).pop("top_shared", None)
        data = cmp
    elif needs == "serp":
        if not body.serp or not body.keyword:
            raise HTTPException(400, "Run a SERP analysis first, then request the brief")
        s = body.serp
        data = {"keyword": body.keyword, "intent": s.get("intent"), "summary": s.get("summary"), "heading_topics": (s.get("heading_topics") or [])[:20],
                "common_terms": (s.get("common_terms") or [])[:30], "questions": (s.get("questions") or [])[:15],
                "results": [{"position": r.get("position"), "title": r.get("title"), "url": r.get("url"), "word_count": r.get("word_count"),
                             "h2_count": r.get("h2_count")} for r in (s.get("results") or [])[:10]]}
    elif needs == "gsc":
        if site is None:
            raise HTTPException(400, "site_id is required")
        ins = gsc.insights(db, site.id)
        if not ins.get("has_data") or not ins.get("dated"):
            raise HTTPException(400, "This task needs dated Search Console data covering two comparison periods")
        data = {"window_days": ins["window_days"], "declining_queries": ins["declining_queries"][:25], "declining_pages": ins["declining_pages"][:15],
                "lost_queries": ins["lost_queries"][:15]}
        if crawl:
            urls = [d["key"] for d in ins["declining_pages"][:15]]
            found = db.execute(select(Issue.url, Issue.rule_id).where(Issue.crawl_id == crawl.id, Issue.url.in_(urls), Issue.severity.in_(("critical", "high")))).all()
            data["audit_findings_on_declining_pages"] = [{"url": u, "issue": RULES[r].title} for u, r in found if r in RULES]
    try:
        text = await ai.complete(get_setting(db, "ai"), ai.build_prompt(body.task, data, body.note))
    except ai.AIError as exc:
        raise HTTPException(400, str(exc)) from exc
    cfg = get_setting(db, "ai")
    return {"task": body.task, "output": text, "provider": cfg.get("provider"), "model": cfg.get("model"),
            "grounding": "Generated from the data shown in this app for the selected item. Verify before acting; a language model can still be wrong."}
