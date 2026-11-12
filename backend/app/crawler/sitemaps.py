"""XML sitemap discovery, parsing, validation and generation."""
from __future__ import annotations

import gzip
import re
from dataclasses import dataclass, field
from datetime import date
from urllib.parse import urlsplit
from xml.sax.saxutils import escape

from lxml import etree

from .fetcher import Fetcher
from .urls import normalize_url

MAX_SITEMAPS = 200
MAX_SITEMAP_BYTES = 52_428_800  # 50 MB uncompressed, per the sitemaps.org protocol
MAX_URLS_PER_FILE = 50_000
_W3C_DATE = re.compile(r"^\d{4}(-\d{2}(-\d{2}(T\d{2}:\d{2}(:\d{2}(\.\d+)?)?(Z|[+-]\d{2}:\d{2}))?)?)?$")


@dataclass
class SitemapFile:
    url: str
    status: int | None = None
    kind: str = "unknown"  # urlset|index|text|unknown
    url_count: int = 0
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    source: str = "robots.txt"


@dataclass
class SitemapReport:
    files: list[SitemapFile] = field(default_factory=list)
    urls: dict[str, dict] = field(default_factory=dict)  # normalised loc -> {lastmod, sitemap, hreflang}

    def to_dict(self) -> dict:
        return {
            "files": [f.__dict__ for f in self.files],
            "url_count": len(self.urls),
        }


def _valid_w3c_date(value: str) -> bool:
    if not _W3C_DATE.match(value):
        return False
    try:
        if len(value) >= 10:
            date.fromisoformat(value[:10])
        elif len(value) == 7:
            date.fromisoformat(value + "-01")
    except ValueError:
        return False
    return True


def _local(tag) -> str:
    return tag.rsplit("}", 1)[-1].lower() if isinstance(tag, str) else ""


def parse_sitemap(body: bytes, url: str) -> tuple[str, list[dict], list[str], list[str]]:
    """Return (kind, entries, errors, warnings). Entries: {loc, lastmod, alternates}."""
    errors: list[str] = []
    warnings: list[str] = []
    if body[:2] == b"\x1f\x8b":
        try:
            with gzip.GzipFile(fileobj=__import__("io").BytesIO(body)) as gz:
                body = gz.read(MAX_SITEMAP_BYTES + 1)
        except (OSError, EOFError) as exc:
            return "unknown", [], [f"Invalid gzip data: {exc}"], warnings
    if len(body) > MAX_SITEMAP_BYTES:
        errors.append("Sitemap is larger than 50 MB uncompressed")
        body = body[:MAX_SITEMAP_BYTES]
    stripped = body.lstrip(b"\xef\xbb\xbf \t\r\n")
    if not stripped.startswith(b"<"):
        lines = [ln.strip() for ln in stripped.decode("utf-8", "replace").splitlines() if ln.strip()]
        if lines and all(ln.startswith(("http://", "https://")) for ln in lines[:20]):
            return "text", [{"loc": ln, "lastmod": None, "alternates": []} for ln in lines[:MAX_URLS_PER_FILE]], errors, warnings
        return "unknown", [], ["Not an XML or plain-text sitemap"], warnings
    parser = etree.XMLParser(resolve_entities=False, no_network=True, recover=True, huge_tree=False, dtd_validation=False, load_dtd=False)
    try:
        root = etree.fromstring(stripped, parser=parser)
    except etree.XMLSyntaxError as exc:
        return "unknown", [], [f"XML syntax error: {exc}"], warnings
    if root is None:
        return "unknown", [], ["Empty or unparseable XML document"], warnings
    if parser.error_log:
        errors.append(f"XML is not well-formed: {parser.error_log[0].message} (line {parser.error_log[0].line})")
    kind = {"urlset": "urlset", "sitemapindex": "index"}.get(_local(root.tag), "unknown")
    if kind == "unknown":
        return kind, [], [f"Unexpected root element <{_local(root.tag)}>"], warnings
    if "sitemaps.org/schemas/sitemap" not in (root.tag if isinstance(root.tag, str) else ""):
        warnings.append("Root element is missing the sitemaps.org namespace")
    entries: list[dict] = []
    bad_dates = 0
    for node in root:
        if _local(node.tag) not in ("url", "sitemap"):
            continue
        loc, lastmod, alternates = None, None, []
        for child in node:
            name = _local(child.tag)
            if name == "loc":
                loc = (child.text or "").strip()
            elif name == "lastmod":
                lastmod = (child.text or "").strip() or None
            elif name == "link" and child.get("rel") == "alternate" and child.get("hreflang"):
                alternates.append({"hreflang": child.get("hreflang"), "href": child.get("href")})
        if not loc:
            errors.append("Entry without <loc>")
            continue
        if lastmod and not _valid_w3c_date(lastmod):
            bad_dates += 1
        entries.append({"loc": loc, "lastmod": lastmod, "alternates": alternates})
    if bad_dates:
        errors.append(f"{bad_dates} <lastmod> value(s) are not valid W3C datetime")
    if len(entries) > MAX_URLS_PER_FILE:
        errors.append(f"Sitemap lists {len(entries)} URLs; the limit is 50,000 per file")
        entries = entries[:MAX_URLS_PER_FILE]
    if not entries:
        warnings.append("Sitemap contains no entries")
    future = [e for e in entries if e["lastmod"] and e["lastmod"][:10] > date.today().isoformat()]
    if future:
        warnings.append(f"{len(future)} <lastmod> value(s) are in the future")
    return kind, entries, errors, warnings


async def discover_sitemaps(fetcher: Fetcher, start_url: str, robots_sitemaps: list[str], max_urls: int = 100_000) -> SitemapReport:
    report = SitemapReport()
    p = urlsplit(start_url)
    origin = f"{p.scheme}://{p.netloc}"
    queue: list[tuple[str, str]] = [(u, "robots.txt") for u in robots_sitemaps]
    if not queue:
        queue = [(f"{origin}/sitemap.xml", "default location"), (f"{origin}/sitemap_index.xml", "default location")]
    seen: set[str] = set()
    while queue and len(report.files) < MAX_SITEMAPS:
        raw, source = queue.pop(0)
        url = normalize_url(raw, origin)
        if not url or url in seen:
            continue
        seen.add(url)
        res = await fetcher.fetch_following(url, max_body=MAX_SITEMAP_BYTES)
        sf = SitemapFile(url=url, status=res.status, source=source)
        if res.status != 200:
            if source == "default location":
                continue  # absence at the conventional location is reported once, by the audit
            sf.errors.append(res.error or f"HTTP {res.status}")
            report.files.append(sf)
            continue
        kind, entries, errors, warnings = parse_sitemap(res.body, url)
        sf.kind, sf.errors, sf.warnings, sf.url_count = kind, errors, warnings, len(entries)
        report.files.append(sf)
        if kind == "index":
            queue.extend((e["loc"], f"index {url}") for e in entries)
            continue
        cross_host = 0
        for e in entries:
            if len(report.urls) >= max_urls:
                sf.warnings.append("URL limit reached; remaining sitemap entries were ignored")
                break
            loc = normalize_url(e["loc"])
            if not loc:
                sf.errors.append(f"Invalid <loc>: {e['loc'][:120]}")
                continue
            if urlsplit(loc).hostname != urlsplit(url).hostname:
                cross_host += 1
            report.urls.setdefault(loc, {"lastmod": e["lastmod"], "sitemap": url, "alternates": e["alternates"]})
        if cross_host:
            sf.warnings.append(f"{cross_host} URL(s) are on a different host than the sitemap")
    return report


def generate_sitemap(entries: list[tuple[str, str | None]]) -> list[str]:
    """Build sitemap XML documents (max 50,000 URLs each) from (url, lastmod) pairs."""
    docs: list[str] = []
    for i in range(0, max(len(entries), 1), MAX_URLS_PER_FILE):
        chunk = entries[i : i + MAX_URLS_PER_FILE]
        lines = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
        for url, lastmod in chunk:
            lines.append("  <url>")
            lines.append(f"    <loc>{escape(url)}</loc>")
            if lastmod:
                lines.append(f"    <lastmod>{escape(lastmod)}</lastmod>")
            lines.append("  </url>")
        lines.append("</urlset>")
        docs.append("\n".join(lines) + "\n")
    return docs
