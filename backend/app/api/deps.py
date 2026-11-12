"""Shared API helpers."""
from __future__ import annotations

from fastapi import HTTPException, Response, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import Crawl, Site, User
from ..security.ssrf import UnsafeURLError, validate_url


def get_crawl_for(db: Session, user: User, crawl_id: int) -> Crawl:
    crawl = db.get(Crawl, crawl_id)
    if crawl is None:
        raise HTTPException(404, "Crawl not found")
    site = db.get(Site, crawl.site_id)
    if site is None or site.owner_id != user.id:
        raise HTTPException(404, "Crawl not found")
    return crawl


def latest_crawl(db: Session, site_id: int, completed_only: bool = True) -> Crawl | None:
    q = select(Crawl).where(Crawl.site_id == site_id, Crawl.competitor_id.is_(None))
    if completed_only:
        q = q.where(Crawl.status == "completed")
    return db.scalar(q.order_by(Crawl.id.desc()))


def checked_url(url: str) -> str:
    """Validate a user-supplied URL against the SSRF policy and return it, or raise HTTP 422."""
    url = (url or "").strip()
    if url and "://" not in url:
        url = "https://" + url
    try:
        return validate_url(url, get_settings().allow_private_networks)
    except UnsafeURLError as exc:
        raise HTTPException(422, f"URL not allowed: {exc}") from exc


async def read_upload(file: UploadFile, allowed_ext: tuple[str, ...] = (".csv", ".tsv", ".txt")) -> bytes:
    """Read an uploaded file with extension and size limits (files are parsed in memory, never stored)."""
    name = (file.filename or "").lower()
    if not name.endswith(allowed_ext):
        raise HTTPException(415, f"Unsupported file type. Allowed: {', '.join(allowed_ext)}")
    limit = get_settings().max_upload_mb * 1024 * 1024
    data = await file.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(413, f"File is larger than {get_settings().max_upload_mb} MB")
    utf16 = data[:2] in (b"\xff\xfe", b"\xfe\xff")  # Google Ads Keyword Planner exports are UTF-16
    if b"\x00" in data[:4096] and not utf16:
        raise HTTPException(415, "File does not look like text/CSV")
    return data


def download(content: bytes, filename: str, media_type: str) -> Response:
    safe = "".join(c if c.isalnum() or c in "-_." else "-" for c in filename)
    return Response(content, media_type=media_type, headers={"Content-Disposition": f'attachment; filename="{safe}"'})


def page_params(page: int, per_page: int) -> tuple[int, int]:
    per_page = max(1, min(per_page, 500))
    return (max(1, page) - 1) * per_page, per_page
