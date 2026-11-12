"""URL normalisation and scope helpers."""
from __future__ import annotations

import posixpath
import re
from functools import lru_cache
from urllib.parse import quote, unquote, urljoin, urlsplit, urlunsplit

import tldextract

_extract = tldextract.TLDExtract(suffix_list_urls=())  # bundled public-suffix snapshot, no network
_SKIP_SCHEMES = ("mailto:", "tel:", "javascript:", "data:", "sms:", "ftp:", "file:", "blob:", "about:", "callto:", "whatsapp:")
_ASSET_EXT = re.compile(
    r"\.(?:jpe?g|png|gif|webp|avif|svg|ico|bmp|tiff?|css|js|mjs|json|xml|rss|atom|pdf|zip|gz|rar|7z|tar|"
    r"mp[34]|avi|mov|wmv|webm|ogg|wav|flac|woff2?|ttf|eot|otf|docx?|xlsx?|pptx?|exe|dmg|apk|csv|txt)$",
    re.I,
)


def normalize_url(url: str, base: str | None = None) -> str | None:
    """Resolve against ``base``, drop fragments, lower-case scheme/host, remove default ports."""
    if not url:
        return None
    url = url.strip()
    if not url or url.startswith("#") or url.lower().startswith(_SKIP_SCHEMES):
        return None
    try:
        if base:
            url = urljoin(base, url)
        p = urlsplit(url)
        scheme = p.scheme.lower()
        if scheme not in ("http", "https") or not p.hostname:
            return None
        host = p.hostname.lower().rstrip(".")
        try:
            host = host.encode("idna").decode("ascii")
        except UnicodeError:
            pass
        port = p.port
    except ValueError:
        return None
    if ":" in host:  # IPv6 literal
        host = f"[{host}]"
    netloc = host if port in (None, 80 if scheme == "http" else 443) else f"{host}:{port}"
    path = p.path or "/"
    if "/./" in path or "/../" in path or path.endswith(("/.", "/..")):
        trailing = path.endswith("/") or path.endswith(("/.", "/.."))
        path = posixpath.normpath(path)
        if trailing and not path.endswith("/"):
            path += "/"
    path = quote(unquote(path), safe="/:@!$&'()*+,;=-._~%")
    query = p.query.replace(" ", "%20")
    if len(netloc) + len(path) + len(query) > 2000:
        return None
    return urlunsplit((scheme, netloc, path, query, ""))


def host_of(url: str) -> str:
    return (urlsplit(url).hostname or "").lower()


def strip_www(host: str) -> str:
    return host[4:] if host.startswith("www.") else host


@lru_cache(maxsize=50_000)
def registrable_domain(host: str) -> str:
    ext = _extract(host)
    return (ext.top_domain_under_public_suffix or host).lower()


def looks_like_asset(url: str) -> bool:
    return bool(_ASSET_EXT.search(urlsplit(url).path))


class Scope:
    """Decides whether a URL belongs to the site being crawled."""

    def __init__(self, start_url: str, include_subdomains: bool = False) -> None:
        self.host = strip_www(host_of(start_url))
        self.domain = registrable_domain(self.host)
        self.include_subdomains = include_subdomains

    def contains(self, url: str) -> bool:
        h = strip_www(host_of(url))
        if h == self.host:
            return True
        if self.include_subdomains:
            return h == self.domain or h.endswith("." + self.domain)
        return False
