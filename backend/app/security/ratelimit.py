"""In-memory sliding-window rate limiting and security headers (single-process deployments)."""
from __future__ import annotations

import time
from collections import defaultdict, deque

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from ..config import get_settings


class SlidingWindow:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str, limit: int, window: float = 60.0) -> bool:
        now = time.monotonic()
        q = self._hits[key]
        while q and now - q[0] > window:
            q.popleft()
        if len(q) >= limit:
            return False
        q.append(now)
        if len(self._hits) > 20_000:  # bound memory
            for k in [k for k, v in self._hits.items() if not v or now - v[-1] > window]:
                self._hits.pop(k, None)
        return True


limiter = SlidingWindow()
_SENSITIVE = ("/api/auth/login", "/api/auth/register")


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        s = get_settings()
        path = request.url.path
        if path.startswith("/api/"):
            ip = request.client.host if request.client else "unknown"
            if path in _SENSITIVE and request.method == "POST":
                ok = limiter.allow(f"auth:{ip}", s.login_rate_limit_per_minute)
            else:
                ok = limiter.allow(f"api:{ip}", s.api_rate_limit_per_minute)
            if not ok:
                return JSONResponse({"detail": "Too many requests. Please slow down."}, status_code=429,
                                    headers={"Retry-After": "60"})
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        if not path.startswith(("/api/docs", "/api/redoc")):
            response.headers.setdefault(
                "Content-Security-Policy",
                "default-src 'self'; img-src 'self' data: https:; style-src 'self' 'unsafe-inline'; "
                "script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'",
            )
        return response
