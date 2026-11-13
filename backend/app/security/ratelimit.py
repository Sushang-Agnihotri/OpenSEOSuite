"""In-memory sliding-window rate limiting and security headers (single-process deployments)."""
from __future__ import annotations

import ipaddress
import time
from collections import defaultdict, deque
from functools import lru_cache

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from ..config import get_settings


class SlidingWindow:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def _trim(self, key: str, window: float) -> deque[float]:
        now = time.monotonic()
        q = self._hits[key]
        while q and now - q[0] > window:
            q.popleft()
        return q

    def count(self, key: str, window: float = 60.0) -> int:
        """Hits inside the window, without recording a new one."""
        return len(self._trim(key, window))

    def hit(self, key: str, window: float = 60.0) -> None:
        self._trim(key, window).append(time.monotonic())
        self._prune(window)

    def clear(self, key: str) -> None:
        self._hits.pop(key, None)

    def allow(self, key: str, limit: int, window: float = 60.0) -> bool:
        q = self._trim(key, window)
        if len(q) >= limit:
            return False
        q.append(time.monotonic())
        self._prune(window)
        return True

    def _prune(self, window: float) -> None:
        if len(self._hits) > 20_000:  # bound memory
            now = time.monotonic()
            for k in [k for k, v in self._hits.items() if not v or now - v[-1] > window]:
                self._hits.pop(k, None)


limiter = SlidingWindow()
_SENSITIVE = ("/api/auth/login", "/api/auth/register")


@lru_cache(maxsize=8)
def _networks(spec: str) -> tuple:
    nets = []
    for item in spec.split(","):
        item = item.strip()
        if item:
            try:
                nets.append(ipaddress.ip_network(item, strict=False))
            except ValueError:
                continue
    return tuple(nets)


def _is_trusted(ip: str, nets: tuple) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return any(addr in n for n in nets)


def client_ip(request) -> str:
    """Address used for rate limiting.

    The socket peer is used unless it is a configured trusted reverse proxy (``SEO_TRUSTED_PROXIES``); only
    then is ``X-Forwarded-For`` consulted, taking the right-most hop that is not itself a trusted proxy, so a
    client cannot choose its own address by sending the header.
    """
    peer = request.client.host if request.client else "unknown"
    nets = _networks(get_settings().trusted_proxies)
    if not nets or not _is_trusted(peer, nets):
        return peer
    hops = [h.strip() for h in request.headers.get("x-forwarded-for", "").split(",") if h.strip()]
    for hop in reversed(hops):
        try:
            ipaddress.ip_address(hop)
        except ValueError:
            return peer  # a malformed header is never used as a rate-limit key
        if not _is_trusted(hop, nets):
            return hop
    return peer


_CSP = ("default-src 'self'; img-src 'self' data: https:; style-src 'self' 'unsafe-inline'; "
        "script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'; object-src 'none'")
# Swagger UI / ReDoc are loaded from a CDN by FastAPI, so the interactive docs get their own, narrower exception.
_DOCS_CSP = ("default-src 'self'; img-src 'self' data: https://fastapi.tiangolo.com; "
             "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com; "
             "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; font-src https://fonts.gstatic.com; "
             "worker-src blob:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; object-src 'none'")


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        s = get_settings()
        path = request.url.path
        if not path.startswith("/assets/"):
            ip = client_ip(request)
            if path in _SENSITIVE and request.method == "POST":
                ok = limiter.allow(f"auth:{ip}", s.login_rate_limit_per_minute)
            elif path.startswith("/api/"):
                ok = limiter.allow(f"api:{ip}", s.api_rate_limit_per_minute)
            else:  # the single-page app shell and anything that is not the API
                ok = limiter.allow(f"web:{ip}", s.api_rate_limit_per_minute)
            if not ok:
                return JSONResponse({"detail": "Too many requests. Please slow down."}, status_code=429,
                                    headers={"Retry-After": "60"})
        response = await call_next(request)
        h = response.headers
        h.setdefault("X-Content-Type-Options", "nosniff")
        h.setdefault("X-Frame-Options", "DENY")
        h.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        h.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=(), payment=(), usb=()")
        h.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        h.setdefault("Cross-Origin-Resource-Policy", "same-origin")
        if request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https":
            h.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        h.setdefault("Content-Security-Policy", _DOCS_CSP if path.startswith(("/api/docs", "/api/redoc")) else _CSP)
        if path.startswith("/api/"):
            h.setdefault("Cache-Control", "no-store")
        return response
