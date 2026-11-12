"""Keyword research, SERP analysis, content optimiser, schema tools and page speed."""
from __future__ import annotations

import json
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from ..audit.schema_validator import SPECS, TEMPLATES, all_types, generate_template, validate_jsonld
from ..content.optimizer import analyse_content
from ..crawler.fetcher import Fetcher
from ..crawler.parser import parse_html
from ..db import get_db
from ..integrations import pagespeed as psi
from ..keywords import research
from ..models import GscRow, Keyword, Page, PageSpeedResult, User
from ..reports.exports import to_csv, to_xlsx
from ..security.auth import current_user, get_site_for
from ..serp import analyzer as serp
from ..services.settings_store import get_setting
from .deps import checked_url, download, latest_crawl, read_upload

router = APIRouter(tags=["tools"])


# ----------------------------------------------------------------------------- keywords
class SuggestIn(BaseModel):
    seed: str = Field(min_length=1, max_length=120)
    lang: str = Field("en", pattern=r"^[a-z]{2}$")
    country: str = Field("us", pattern=r"^[a-zA-Z]{2}$")
    sources: list[Literal["google", "bing", "duckduckgo"]] = ["google", "bing", "duckduckgo"]
    depth: Literal["basic", "deep"] = "basic"


class ClusterIn(BaseModel):
    keywords: list[str] = Field(min_length=1, max_length=3000)
    seed: str | None = Field(None, max_length=120)
    threshold: float = Field(0.5, ge=0.1, le=1.0)


class KeywordsIn(BaseModel):
    keywords: list[str] = Field(min_length=1, max_length=2000)
    source: str = Field("manual", max_length=40)


@router.post("/keywords/suggest")
async def keyword_suggest(body: SuggestIn, user: User = Depends(current_user)) -> dict:
    result = await research.suggest(body.seed, body.lang, body.country.lower(), list(body.sources), body.depth)
    result["clusters"] = research.cluster_keywords([k["keyword"] for k in result["keywords"]], seed=body.seed)[:60]
    result["data_notes"] = [
        "Suggestions are real completions returned by the listed public endpoints at request time.",
        "Search volume, CPC and competition are NOT available from these sources and are never estimated here. "
        "Import a Google Ads Keyword Planner CSV or use Search Console impressions for measured demand.",
        "Intent labels are rule-based estimates.",
    ]
    return result


@router.post("/keywords/cluster")
def keyword_cluster(body: ClusterIn, user: User = Depends(current_user)) -> dict:
    return {"clusters": research.cluster_keywords(body.keywords, body.threshold, body.seed), "method": "Lexical (shared stemmed terms, Jaccard similarity)"}


@router.post("/keywords/intent")
def keyword_intent(body: KeywordsIn, user: User = Depends(current_user)) -> dict:
    return {"items": [{"keyword": k, **research.classify_intent(k)} for k in body.keywords[:2000]]}


def _gsc_metrics(db: Session, site_id: int) -> dict[str, dict]:
    rows = db.execute(select(GscRow.query, func.sum(GscRow.clicks), func.sum(GscRow.impressions),
                             func.sum(GscRow.position * GscRow.impressions) / func.nullif(func.sum(GscRow.impressions), 0))
                      .where(GscRow.site_id == site_id, GscRow.dataset == "query_page", GscRow.query.isnot(None)).group_by(GscRow.query)).all()
    return {q.lower(): {"clicks": round(c or 0), "impressions": round(i or 0), "position": round(p, 1) if p else None} for q, c, i, p in rows}


@router.get("/sites/{site_id}/keywords")
def list_keywords(site_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    site = get_site_for(db, user, site_id)
    gsc = _gsc_metrics(db, site.id)
    items = []
    for k in db.scalars(select(Keyword).where(Keyword.site_id == site.id).order_by(Keyword.keyword)):
        measured = gsc.get(k.keyword.lower())
        imported = (k.metrics or {}).get("imported") or {}
        items.append({"id": k.id, "keyword": k.keyword, "source": k.source, "intent": k.intent, "cluster": k.cluster,
                      "gsc": measured, "imported": imported,
                      "search_volume": imported.get("search_volume"),
                      "volume_status": "imported" if imported.get("search_volume") is not None else "unavailable",
                      "created_at": k.created_at.isoformat()})
    return {"items": items, "has_gsc_data": bool(gsc),
            "legend": {"gsc": "Measured by Google Search Console for your site", "imported": "Values from a file you imported",
                       "unavailable": "No legitimate free source; left empty rather than guessed"}}


@router.post("/sites/{site_id}/keywords", status_code=201)
def save_keywords(site_id: int, body: KeywordsIn, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    site = get_site_for(db, user, site_id)
    existing = {k.lower() for k in db.scalars(select(Keyword.keyword).where(Keyword.site_id == site.id))}
    added = 0
    for kw in dict.fromkeys(" ".join(k.lower().split())[:500] for k in body.keywords):
        if kw and kw not in existing:
            db.add(Keyword(site_id=site.id, keyword=kw, source=body.source, intent=research.classify_intent(kw)["intent"]))
            existing.add(kw)
            added += 1
    db.flush()
    all_kw = list(db.scalars(select(Keyword).where(Keyword.site_id == site.id)))
    label_of = {k: c["label"] for c in research.cluster_keywords([k.keyword for k in all_kw]) for k in c["keywords"]}
    for k in all_kw:
        k.cluster = label_of.get(k.keyword)
    db.commit()
    return {"added": added, "total": len(all_kw)}


@router.post("/sites/{site_id}/keywords/import")
async def import_keywords(site_id: int, file: UploadFile, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    """Import a keyword list with metrics, e.g. a Google Ads Keyword Planner export (Keyword, Avg. monthly searches, Competition, bids)."""
    import csv
    import io

    site = get_site_for(db, user, site_id)
    raw = await read_upload(file)
    text = raw.decode("utf-16" if raw[:2] in (b"\xff\xfe", b"\xfe\xff") else "utf-8-sig", "replace")
    lines = text.splitlines()
    start = next((i for i, ln in enumerate(lines[:10]) if "keyword" in ln.lower()), 0)
    try:
        dialect = csv.Sniffer().sniff("\n".join(lines[start : start + 5]), delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(io.StringIO("\n".join(lines[start:])), dialect=dialect)
    alias = {"keyword": ("keyword", "keywords", "search term", "query"), "search_volume": ("avg. monthly searches", "search volume", "volume", "avg monthly searches"),
             "competition": ("competition", "competition (indexed value)"), "cpc_low": ("top of page bid (low range)",), "cpc_high": ("top of page bid (high range)", "cpc")}
    existing = {k.keyword: k for k in db.scalars(select(Keyword).where(Keyword.site_id == site.id))}
    added = updated = 0
    for row in reader:
        norm = {(k or "").strip().lower(): (v or "").strip() for k, v in row.items()}
        rec: dict[str, Any] = {}
        for field, names in alias.items():
            for n in names:
                if norm.get(n):
                    rec[field] = norm[n]
                    break
        kw = " ".join(rec.pop("keyword", "").lower().split())[:500]
        if not kw:
            continue
        for f in ("search_volume", "cpc_low", "cpc_high"):
            if f in rec:
                try:
                    rec[f] = float(rec[f].replace(",", "").replace("$", "").replace("€", ""))
                except ValueError:
                    rec.pop(f)
        rec["file"] = (file.filename or "")[:120]
        if kw in existing:
            existing[kw].metrics = {**(existing[kw].metrics or {}), "imported": rec}
            updated += 1
        elif added < 20_000:
            k = Keyword(site_id=site.id, keyword=kw, source="import", intent=research.classify_intent(kw)["intent"], metrics={"imported": rec})
            db.add(k)
            existing[kw] = k
            added += 1
    db.commit()
    return {"added": added, "updated": updated}


@router.delete("/sites/{site_id}/keywords", status_code=204)
def delete_keywords(site_id: int, ids: list[int], user: User = Depends(current_user), db: Session = Depends(get_db)) -> None:
    site = get_site_for(db, user, site_id)
    db.execute(delete(Keyword).where(Keyword.site_id == site.id, Keyword.id.in_(ids[:5000])))
    db.commit()


@router.get("/sites/{site_id}/keywords/mapping")
def keyword_mapping(site_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    """Keyword-to-page mapping and cannibalisation risks, based on the latest crawl (on-page relevance estimate)."""
    site = get_site_for(db, user, site_id)
    crawl = latest_crawl(db, site.id)
    keywords = list(db.scalars(select(Keyword.keyword).where(Keyword.site_id == site.id).order_by(Keyword.keyword).limit(500)))
    if not crawl:
        return {"items": [], "crawl_id": None, "message": "Run a crawl first so keywords can be mapped to pages."}
    pages = [{"url": u, "title": t, "h1": h, "meta_description": d, "text": (x or "")[:6000]} for u, t, h, d, x in db.execute(
        select(Page.url, Page.title, Page.h1, Page.meta_description, Page.text).where(Page.crawl_id == crawl.id, Page.indexable.is_(True)).order_by(Page.pagerank.desc()).limit(1500))]
    items = research.map_keywords(keywords, pages)
    return {"items": items, "crawl_id": crawl.id, "pages_considered": len(pages),
            "summary": {s: sum(1 for i in items if i["status"] == s) for s in ("mapped", "cannibalisation risk", "no matching page")}}


@router.get("/sites/{site_id}/keywords/export")
def export_keywords(site_id: int, format: str = "csv", user: User = Depends(current_user), db: Session = Depends(get_db)):
    site = get_site_for(db, user, site_id)
    rows = [{"keyword": i["keyword"], "cluster": i["cluster"], "intent (estimate)": i["intent"], "source": i["source"],
             "gsc_clicks (measured)": (i["gsc"] or {}).get("clicks"), "gsc_impressions (measured)": (i["gsc"] or {}).get("impressions"),
             "gsc_avg_position (measured)": (i["gsc"] or {}).get("position"), "search_volume (imported)": i["search_volume"],
             "competition (imported)": i["imported"].get("competition")} for i in list_keywords(site_id, user, db)["items"]]
    if format == "xlsx":
        mapping = [{"keyword": m["keyword"], "status": m["status"], "best_page": (m["best_page"] or {}).get("url"),
                    "competing_pages": ", ".join(c["url"] for c in m["competing_pages"])} for m in keyword_mapping(site_id, user, db)["items"]]
        return download(to_xlsx({"Keywords": rows, "Page mapping": mapping}), f"keywords-{site.domain}.xlsx",
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    return download(to_csv(rows), f"keywords-{site.domain}.csv", "text/csv")


# ----------------------------------------------------------------------------- SERP
class SerpIn(BaseModel):
    keyword: str = Field(min_length=1, max_length=200)
    country: str = Field("us", pattern=r"^[a-zA-Z]{2}$")
    lang: str = Field("en", pattern=r"^[a-z]{2}$")
    urls: list[str] = Field(default_factory=list, max_length=20)  # manual mode: paste the ranking URLs
    my_url: str | None = Field(None, max_length=2048)
    fetch_pages: bool = True


@router.get("/serp/providers")
def serp_providers(user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    return {"configured": get_setting(db, "serp").get("provider", "none"), "providers": serp.PROVIDERS}


@router.post("/serp/analyze")
async def serp_analyze(body: SerpIn, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    features: list[str] = []
    if body.urls:
        results = [{"position": i + 1, "url": checked_url(u), "title": "", "snippet": ""} for i, u in enumerate(body.urls)]
        source = {"provider": "manual", "note": "URLs supplied manually; positions follow the order you entered."}
    else:
        try:
            found = await serp.search(get_setting(db, "serp"), body.keyword, body.country.lower(), body.lang)
        except serp.SerpError as exc:
            raise HTTPException(400, str(exc)) from exc
        results, features = found["results"], found["features"]
        source = {"provider": found["provider"], "note": found["note"]}
    my_url = checked_url(body.my_url) if body.my_url else None
    pages = {}
    if body.fetch_pages and results:
        targets = [r["url"] for r in results[:10]] + ([my_url] if my_url else [])
        pages = await serp.fetch_pages(list(dict.fromkeys(targets)), limit=11)
    out = serp.analyse(body.keyword, results, pages, features, my_url)
    out["source"] = source
    out["feature_note"] = "SERP features are only those the provider's API reports; absence here does not prove absence on Google."
    return out


# ----------------------------------------------------------------------------- content optimiser
class ContentIn(BaseModel):
    content: str = Field(min_length=1, max_length=400_000)
    keyword: str = Field(min_length=1, max_length=200)
    title: str | None = Field(None, max_length=500)
    meta_description: str | None = Field(None, max_length=1000)
    url: str | None = Field(None, max_length=2048)
    secondary_keywords: list[str] = Field(default_factory=list, max_length=30)
    competitor_urls: list[str] = Field(default_factory=list, max_length=10)
    use_serp: bool = False
    site_id: int | None = None
    suggest_questions: bool = False


@router.post("/content/analyze")
async def content_analyze(body: ContentIn, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    competitors: list[dict] = []
    notes: list[str] = []
    urls = [checked_url(u) for u in body.competitor_urls]
    if body.use_serp and not urls:
        try:
            urls = [r["url"] for r in (await serp.search(get_setting(db, "serp"), body.keyword))["results"][:8]]
        except serp.SerpError as exc:
            notes.append(f"SERP lookup skipped: {exc}")
    if urls:
        pages = await serp.fetch_pages(urls, limit=10)
        competitors = [{"url": u, **p} for u, p in pages.items() if p.get("status") == 200]
        failed = [u for u, p in pages.items() if p.get("status") != 200]
        if failed:
            notes.append(f"{len(failed)} competitor page(s) could not be fetched.")
    site_pages = None
    if body.site_id:
        site = get_site_for(db, user, body.site_id)
        crawl = latest_crawl(db, site.id)
        if crawl:
            site_pages = [{"url": u, "title": t, "h1": h} for u, t, h in db.execute(
                select(Page.url, Page.title, Page.h1).where(Page.crawl_id == crawl.id, Page.indexable.is_(True)).limit(3000))]
    questions = None
    if body.suggest_questions:
        try:
            sug = await research.suggest(body.keyword, sources=["google", "bing"], depth="basic")
            questions = [k["keyword"] for k in sug["keywords"] if k["type"] == "question"][:15]
        except Exception as exc:  # noqa: BLE001
            notes.append(f"Question suggestions unavailable: {exc}")
    result = analyse_content(body.content, body.keyword, title=body.title, meta_description=body.meta_description, url=body.url,
                             secondary_keywords=body.secondary_keywords, competitors=competitors, site_pages=site_pages,
                             question_keywords=questions)
    result["notes"] += notes
    result["competitors"] = [{"url": c["url"], "title": c.get("title"), "word_count": c.get("word_count")} for c in competitors]
    return result


class FetchIn(BaseModel):
    url: str = Field(max_length=2048)


@router.post("/content/fetch")
async def content_fetch(body: FetchIn, user: User = Depends(current_user)) -> dict:
    """Load an existing page into the editor (title, description, headings and main text)."""
    url = checked_url(body.url)
    async with Fetcher(timeout_s=20, retries=1) as fetcher:
        res = await fetcher.fetch_following(url, max_body=3_000_000)
    if res.status != 200 or not res.is_html:
        raise HTTPException(400, f"Could not load the page: {res.error or f'HTTP {res.status}'}")
    p = parse_html(res.body, res.final_url or url, res.headers.get("content-type", ""))
    md = "\n\n".join(f"{'#' * h['level']} {h['text']}" for h in p.headings[:3]) if not p.text else ""
    try:
        import trafilatura
        md = trafilatura.extract(res.body.decode("utf-8", "replace"), output_format="markdown", include_links=True, include_images=True) or md
    except Exception:  # noqa: BLE001 - fall back to plain text below
        pass
    return {"url": res.final_url or url, "title": p.title, "meta_description": p.meta_description, "content": md or p.text, "word_count": p.word_count}


# ----------------------------------------------------------------------------- schema tools
class SchemaValidateIn(BaseModel):
    url: str | None = Field(None, max_length=2048)
    jsonld: str | None = Field(None, max_length=500_000)


class SchemaGenerateIn(BaseModel):
    type: str = Field(max_length=40)
    values: dict[str, Any] = Field(default_factory=dict)


@router.get("/schema/types")
def schema_types(user: User = Depends(current_user)) -> dict:
    return {"templates": sorted(TEMPLATES), "validated_types": {t: {"required": s["required"], "recommended": s["recommended"]} for t, s in SPECS.items()}}


@router.post("/schema/validate")
async def schema_validate(body: SchemaValidateIn, user: User = Depends(current_user)) -> dict:
    items, parse_errors, microdata = [], [], []
    if body.jsonld:
        raw = body.jsonld.strip()
        if raw.lower().startswith("<script"):
            page = parse_html(f"<html><head>{raw}</head><body></body></html>".encode(), "https://input.invalid/")
            items, parse_errors = page.jsonld, page.jsonld_errors
        else:
            try:
                from ..crawler.parser import _flatten_jsonld
                items = _flatten_jsonld(json.loads(raw))
            except json.JSONDecodeError as exc:
                parse_errors = [f"Invalid JSON: {exc.msg} (line {exc.lineno}, column {exc.colno})"]
    elif body.url:
        url = checked_url(body.url)
        async with Fetcher(timeout_s=20, retries=1) as fetcher:
            res = await fetcher.fetch_following(url, max_body=3_000_000)
        if res.status != 200 or not res.is_html:
            raise HTTPException(400, f"Could not load the page: {res.error or f'HTTP {res.status}'}")
        page = parse_html(res.body, res.final_url or url, res.headers.get("content-type", ""))
        items, parse_errors, microdata = page.jsonld, page.jsonld_errors, page.microdata_types
    else:
        raise HTTPException(422, "Provide a URL or JSON-LD markup")
    result = validate_jsonld(items)
    return {**result, "parse_errors": parse_errors, "items": items[:40], "all_types": all_types(items), "microdata_types": microdata,
            "valid": not parse_errors and result["errors"] == 0}


@router.post("/schema/generate")
def schema_generate(body: SchemaGenerateIn, user: User = Depends(current_user)) -> dict:
    try:
        doc = generate_template(body.type, body.values)
    except KeyError:
        raise HTTPException(404, f"No template for '{body.type}'") from None
    text = json.dumps(doc, indent=2, ensure_ascii=False).replace("</", "<\\/")  # safe to embed inside <script>
    return {"jsonld": doc, "html": f'<script type="application/ld+json">\n{text}\n</script>', "validation": validate_jsonld([doc])}


# ----------------------------------------------------------------------------- page speed
class SpeedIn(BaseModel):
    url: str = Field(max_length=2048)
    strategy: Literal["mobile", "desktop"] = "mobile"
    source: Literal["psi", "local"] = "psi"
    site_id: int | None = None


@router.get("/pagespeed/status")
def pagespeed_status(user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    return {"psi_key_configured": bool(get_setting(db, "pagespeed").get("api_key")), "local_lighthouse": bool(psi.lighthouse_path()),
            "notes": ["The PageSpeed Insights API is free; without a key the anonymous quota is small and shared.",
                      "Field data (real-user Core Web Vitals incl. INP) comes from the Chrome UX Report and exists only for pages with enough traffic.",
                      "Local Lighthouse gives lab data only; install with: npm install -g lighthouse"]}


@router.post("/pagespeed/run")
async def pagespeed_run(body: SpeedIn, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    url = checked_url(body.url)
    site_id = get_site_for(db, user, body.site_id).id if body.site_id else None
    try:
        if body.source == "local":
            data = await psi.run_local_lighthouse(url, body.strategy)
        else:
            data = await psi.run_psi(url, body.strategy, get_setting(db, "pagespeed").get("api_key", ""))
    except Exception as exc:  # noqa: BLE001 - surfaced to the user as a failed run
        raise HTTPException(502, str(exc)) from exc
    row = PageSpeedResult(site_id=site_id, owner_id=user.id, url=url, strategy=body.strategy, source=data["source"], data=data)
    db.add(row)
    db.commit()
    return {"id": row.id, "url": url, "created_at": row.created_at.isoformat(), **data}


@router.get("/pagespeed/history")
def pagespeed_history(site_id: int | None = None, url: str | None = None, limit: int = 50, user: User = Depends(current_user), db: Session = Depends(get_db)) -> list[dict]:
    stmt = select(PageSpeedResult).where(PageSpeedResult.owner_id == user.id)
    if site_id:
        stmt = stmt.where(PageSpeedResult.site_id == site_id)
    if url:
        stmt = stmt.where(PageSpeedResult.url == url)
    return [{"id": r.id, "url": r.url, "strategy": r.strategy, "source": r.source, "created_at": r.created_at.isoformat(),
             "scores": (r.data or {}).get("scores"), "lab": (r.data or {}).get("lab"), "field": (r.data or {}).get("field")}
            for r in db.scalars(stmt.order_by(PageSpeedResult.id.desc()).limit(min(limit, 200)))]


@router.get("/pagespeed/{result_id}")
def pagespeed_result(result_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    r = db.get(PageSpeedResult, result_id)
    if r is None or r.owner_id != user.id:
        raise HTTPException(404, "Result not found")
    return {"id": r.id, "url": r.url, "created_at": r.created_at.isoformat(), **(r.data or {})}
