"""SQLAlchemy ORM models."""
from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import JSON, Boolean, Date, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, deferred, mapped_column, relationship

from .db import Base


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Site(Base):
    __tablename__ = "sites"
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    url: Mapped[str] = mapped_column(String(2048))
    domain: Mapped[str] = mapped_column(String(255), index=True)
    gsc_property: Mapped[str | None] = mapped_column(String(512), nullable=True)
    crawl_config: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    crawls: Mapped[list[Crawl]] = relationship(back_populates="site", cascade="all, delete-orphan", passive_deletes=True)


class Competitor(Base):
    __tablename__ = "competitors"
    id: Mapped[int] = mapped_column(primary_key=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    url: Mapped[str] = mapped_column(String(2048))
    domain: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Crawl(Base):
    __tablename__ = "crawls"
    id: Mapped[int] = mapped_column(primary_key=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id", ondelete="CASCADE"), index=True)
    competitor_id: Mapped[int | None] = mapped_column(ForeignKey("competitors.id", ondelete="CASCADE"), nullable=True, index=True)
    job_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="queued")  # queued|running|completed|failed|cancelled
    start_url: Mapped[str] = mapped_column(String(2048))
    config: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    stats: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    pages_crawled: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    site: Mapped[Site] = relationship(back_populates="crawls")


class Page(Base):
    """One crawled URL (HTML page, redirect, asset or failed request)."""

    __tablename__ = "pages"
    id: Mapped[int] = mapped_column(primary_key=True)
    crawl_id: Mapped[int] = mapped_column(ForeignKey("crawls.id", ondelete="CASCADE"))
    url: Mapped[str] = mapped_column(String(2048))
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    content_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    is_html: Mapped[bool] = mapped_column(Boolean, default=False)
    redirect_to: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    depth: Mapped[int | None] = mapped_column(Integer, nullable=True)
    found_via: Mapped[str] = mapped_column(String(20), default="link")  # start|link|sitemap|redirect
    blocked_by_robots: Mapped[bool] = mapped_column(Boolean, default=False)
    in_sitemap: Mapped[bool] = mapped_column(Boolean, default=False)
    indexable: Mapped[bool] = mapped_column(Boolean, default=False)
    indexability_reason: Mapped[str | None] = mapped_column(String(120), nullable=True)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    meta_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    h1: Mapped[str | None] = mapped_column(Text, nullable=True)
    canonical: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    meta_robots: Mapped[str | None] = mapped_column(String(255), nullable=True)
    lang: Mapped[str | None] = mapped_column(String(35), nullable=True)
    word_count: Mapped[int] = mapped_column(Integer, default=0)
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    response_ms: Mapped[int] = mapped_column(Integer, default=0)
    content_hash: Mapped[str | None] = mapped_column(String(40), nullable=True)
    simhash: Mapped[str | None] = mapped_column(String(16), nullable=True)
    inlinks: Mapped[int] = mapped_column(Integer, default=0)
    outlinks: Mapped[int] = mapped_column(Integer, default=0)
    external_outlinks: Mapped[int] = mapped_column(Integer, default=0)
    pagerank: Mapped[float] = mapped_column(Float, default=0.0)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    issue_count: Mapped[int] = mapped_column(Integer, default=0)
    data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)  # headings, images, og, schema, hreflang ...
    text: Mapped[str | None] = deferred(mapped_column(Text, nullable=True))  # extracted body text (truncated)

    __table_args__ = (
        Index("ix_pages_crawl_url", "crawl_id", "url"),
        Index("ix_pages_crawl_status", "crawl_id", "status_code"),
    )


class Link(Base):
    __tablename__ = "links"
    id: Mapped[int] = mapped_column(primary_key=True)
    crawl_id: Mapped[int] = mapped_column(ForeignKey("crawls.id", ondelete="CASCADE"))
    source_page_id: Mapped[int] = mapped_column(Integer, index=True)
    source_url: Mapped[str] = mapped_column(String(2048))
    target_url: Mapped[str] = mapped_column(String(2048))
    anchor: Mapped[str | None] = mapped_column(String(500), nullable=True)
    kind: Mapped[str] = mapped_column(String(12), default="a")  # a|img
    nofollow: Mapped[bool] = mapped_column(Boolean, default=False)
    is_internal: Mapped[bool] = mapped_column(Boolean, default=True)
    target_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    target_error: Mapped[str | None] = mapped_column(String(300), nullable=True)

    __table_args__ = (
        Index("ix_links_crawl_target", "crawl_id", "target_url"),
        Index("ix_links_crawl_internal", "crawl_id", "is_internal"),
    )


class Issue(Base):
    __tablename__ = "issues"
    id: Mapped[int] = mapped_column(primary_key=True)
    crawl_id: Mapped[int] = mapped_column(ForeignKey("crawls.id", ondelete="CASCADE"))
    page_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    url: Mapped[str] = mapped_column(String(2048))
    rule_id: Mapped[str] = mapped_column(String(60))
    severity: Mapped[str] = mapped_column(String(10))
    category: Mapped[str] = mapped_column(String(30))
    details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    __table_args__ = (Index("ix_issues_crawl_rule", "crawl_id", "rule_id"),)


class Job(Base):
    __tablename__ = "jobs"
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    site_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    kind: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(20), default="queued")
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    result: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Keyword(Base):
    __tablename__ = "keywords"
    id: Mapped[int] = mapped_column(primary_key=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id", ondelete="CASCADE"), index=True)
    keyword: Mapped[str] = mapped_column(String(500))
    source: Mapped[str] = mapped_column(String(40), default="manual")
    intent: Mapped[str | None] = mapped_column(String(20), nullable=True)
    cluster: Mapped[str | None] = mapped_column(String(255), nullable=True)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    __table_args__ = (Index("ix_keywords_site_kw", "site_id", "keyword", unique=True),)


class GscRow(Base):
    """Search Console performance data. ``dataset`` tells which dimensions are populated."""

    __tablename__ = "gsc_rows"
    id: Mapped[int] = mapped_column(primary_key=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id", ondelete="CASCADE"))
    dataset: Mapped[str] = mapped_column(String(20))  # query_page|country|device|appearance
    day: Mapped[date | None] = mapped_column(Date, nullable=True)
    query: Mapped[str | None] = mapped_column(String(700), nullable=True)
    page: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    country: Mapped[str | None] = mapped_column(String(8), nullable=True)
    device: Mapped[str | None] = mapped_column(String(12), nullable=True)
    appearance: Mapped[str | None] = mapped_column(String(60), nullable=True)
    clicks: Mapped[float] = mapped_column(Float, default=0)
    impressions: Mapped[float] = mapped_column(Float, default=0)
    position: Mapped[float | None] = mapped_column(Float, nullable=True)
    source: Mapped[str] = mapped_column(String(10), default="api")  # api|csv

    __table_args__ = (Index("ix_gsc_site_ds_day", "site_id", "dataset", "day"),)


class Backlink(Base):
    __tablename__ = "backlinks"
    id: Mapped[int] = mapped_column(primary_key=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id", ondelete="CASCADE"), index=True)
    source_url: Mapped[str] = mapped_column(String(2048))
    source_domain: Mapped[str] = mapped_column(String(255), index=True)
    target_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    anchor: Mapped[str | None] = mapped_column(String(500), nullable=True)
    nofollow: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    origin: Mapped[str] = mapped_column(String(30), default="import")  # which dataset supplied the row
    status: Mapped[str] = mapped_column(String(20), default="unverified")  # unverified|live|lost|source_error
    http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    first_seen: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    last_checked: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Monitor(Base):
    __tablename__ = "monitors"
    id: Mapped[int] = mapped_column(primary_key=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(30))  # uptime|audit|sitemap|metadata|competitor|gsc
    name: Mapped[str] = mapped_column(String(255))
    interval_hours: Mapped[float] = mapped_column(Float, default=24)
    config: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    state: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_run: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    next_run: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Alert(Base):
    __tablename__ = "alerts"
    id: Mapped[int] = mapped_column(primary_key=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id", ondelete="CASCADE"), index=True)
    monitor_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    severity: Mapped[str] = mapped_column(String(10), default="medium")
    title: Mapped[str] = mapped_column(String(300))
    message: Mapped[str] = mapped_column(Text, default="")
    data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class PageSpeedResult(Base):
    __tablename__ = "pagespeed_results"
    id: Mapped[int] = mapped_column(primary_key=True)
    site_id: Mapped[int | None] = mapped_column(ForeignKey("sites.id", ondelete="CASCADE"), nullable=True, index=True)
    owner_id: Mapped[int] = mapped_column(Integer, index=True)
    url: Mapped[str] = mapped_column(String(2048))
    strategy: Mapped[str] = mapped_column(String(10))
    source: Mapped[str] = mapped_column(String(20))  # psi_api|local_lighthouse
    data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Citation(Base):
    """Local-SEO citation (business listing) imported by the user."""

    __tablename__ = "citations"
    id: Mapped[int] = mapped_column(primary_key=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id", ondelete="CASCADE"), index=True)
    source: Mapped[str] = mapped_column(String(255))
    url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(60), nullable=True)


class Setting(Base):
    """Instance-wide key/value settings (integration credentials, provider choices)."""

    __tablename__ = "settings"
    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
