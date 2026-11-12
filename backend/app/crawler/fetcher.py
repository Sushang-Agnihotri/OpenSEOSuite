"""SSRF-safe HTTP fetching with size limits, retries, manual redirect handling and per-host throttling."""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from urllib.parse import urlsplit

import httpx

from ..config import get_settings
from ..security.ssrf import SafeNetworkBackend, UnsafeURLError, validate_url
from .urls import normalize_url

REDIRECT_CODES = {301, 302, 303, 307, 308}
RETRY_CODES = {429, 500, 502, 503, 504}


def _is_textual(content_type: str) -> bool:
    return (not content_type or content_type.startswith("text/")
            or content_type in ("application/xhtml+xml", "application/xml", "application/json"))


@dataclass
class FetchResult:
    url: str
    status: int | None = None
    headers: dict[str, str] = field(default_factory=dict)
    body: bytes = b""
    error: str | None = None
    elapsed_ms: int = 0
    truncated: bool = False
    redirect_to: str | None = None  # normalised Location target for 3xx responses
    final_url: str | None = None  # when follow=True
    chain: list[dict] = field(default_factory=list)  # [{url, status}] when follow=True
    redirect_loop: bool = False

    @property
    def content_type(self) -> str:
        return self.headers.get("content-type", "").split(";")[0].strip().lower()

    @property
    def is_html(self) -> bool:
        return self.content_type in ("text/html", "application/xhtml+xml")


class HostThrottle:
    """Guarantees a minimum delay between request starts for the same host."""

    def __init__(self, delay_s: float) -> None:
        self.delay = max(0.0, delay_s)
        self._next: dict[str, float] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        self.overrides: dict[str, float] = {}  # host -> crawl-delay from robots.txt

    async def wait(self, host: str) -> None:
        delay = max(self.delay, self.overrides.get(host, 0.0))
        if delay <= 0:
            return
        lock = self._locks.setdefault(host, asyncio.Lock())
        async with lock:
            now = time.monotonic()
            wait = self._next.get(host, 0.0) - now
            if wait > 0:
                await asyncio.sleep(wait)
            self._next[host] = time.monotonic() + delay


class Fetcher:
    def __init__(
        self,
        user_agent: str | None = None,
        timeout_s: float = 20.0,
        retries: int = 2,
        max_body_bytes: int | None = None,
        delay_s: float = 0.0,
        concurrency: int = 10,
        allow_private: bool | None = None,
    ) -> None:
        s = get_settings()
        self.allow_private = s.allow_private_networks if allow_private is None else allow_private
        self.retries = max(0, retries)
        self.max_body = max_body_bytes or s.crawl_max_body_mb * 1024 * 1024
        self.throttle = HostThrottle(delay_s)
        transport = httpx.AsyncHTTPTransport(
            retries=0, limits=httpx.Limits(max_connections=concurrency * 2, max_keepalive_connections=concurrency)
        )
        # Route every outgoing connection through the vetted-address backend (see security/ssrf.py).
        transport._pool._network_backend = SafeNetworkBackend(self.allow_private)  # noqa: SLF001
        self.client = httpx.AsyncClient(
            transport=transport,
            timeout=httpx.Timeout(timeout_s, connect=min(10.0, timeout_s)),
            follow_redirects=False,
            trust_env=False,  # never use proxies from the environment: they would bypass address checks
            headers={
                "User-Agent": user_agent or s.user_agent,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en;q=0.9,*;q=0.5",
                "Accept-Encoding": "gzip, deflate",
            },
        )

    async def close(self) -> None:
        await self.client.aclose()

    async def __aenter__(self) -> Fetcher:
        return self

    async def __aexit__(self, *exc) -> None:
        await self.close()

    async def _once(self, url: str, method: str, max_body: int, text_only: bool = False) -> FetchResult:
        res = FetchResult(url=url)
        try:
            validate_url(url, self.allow_private)
        except UnsafeURLError as exc:
            res.error = f"blocked: {exc}"
            return res
        await self.throttle.wait(urlsplit(url).hostname or "")
        started = time.monotonic()
        try:
            async with self.client.stream(method, url) as resp:
                res.elapsed_ms = int((time.monotonic() - started) * 1000)  # time to first byte
                res.status = resp.status_code
                res.headers = {k.lower(): v for k, v in resp.headers.items()}
                if resp.status_code in REDIRECT_CODES and resp.headers.get("location"):
                    res.redirect_to = normalize_url(resp.headers["location"], url)
                elif method != "HEAD" and not (text_only and not _is_textual(res.content_type)):
                    chunks: list[bytes] = []
                    size = 0
                    async for chunk in resp.aiter_bytes():
                        size += len(chunk)
                        if size > max_body:
                            chunks.append(chunk[: max(0, max_body - (size - len(chunk)))])
                            res.truncated = True
                            break
                        chunks.append(chunk)
                    res.body = b"".join(chunks)
        except UnsafeURLError as exc:
            res.error = f"blocked: {exc}"
        except httpx.TimeoutException:
            res.error = "timeout"
        except httpx.TooManyRedirects:
            res.error = "too many redirects"
        except httpx.HTTPError as exc:
            res.error = f"{type(exc).__name__}: {exc}"[:300] or "connection error"
        except Exception as exc:  # noqa: BLE001 - decoding errors, invalid URLs etc.
            res.error = f"{type(exc).__name__}: {exc}"[:300]
        return res

    async def fetch(self, url: str, method: str = "GET", max_body: int | None = None,
                    text_only: bool = False) -> FetchResult:
        """Fetch a single URL without following redirects. Retries transient failures.

        With ``text_only`` the body of binary responses (images, PDFs, archives) is not downloaded.
        """
        limit = max_body or self.max_body
        res = await self._once(url, method, limit, text_only)
        attempt = 0
        while attempt < self.retries and (
            (res.error and not res.error.startswith("blocked")) or res.status in RETRY_CODES
        ):
            attempt += 1
            retry_after = res.headers.get("retry-after", "") if res.status == 429 else ""
            delay = min(float(retry_after), 30.0) if retry_after.isdigit() else 0.6 * (2 ** (attempt - 1))
            await asyncio.sleep(delay)
            res = await self._once(url, method, limit, text_only)
        return res

    async def fetch_following(self, url: str, method: str = "GET", max_redirects: int = 10,
                              max_body: int | None = None) -> FetchResult:
        """Fetch a URL following redirects manually so the full chain is recorded and every hop is vetted."""
        chain: list[dict] = []
        seen: set[str] = set()
        current = url
        res = FetchResult(url=url)
        for _ in range(max_redirects + 1):
            if current in seen:
                res.redirect_loop = True
                res.error = "redirect loop"
                break
            seen.add(current)
            res = await self.fetch(current, method, max_body)
            chain.append({"url": current, "status": res.status, "error": res.error})
            if res.redirect_to and res.status in REDIRECT_CODES:
                current = res.redirect_to
                continue
            break
        else:
            res.error = "too many redirects"
        res.chain = chain
        res.final_url = current
        res.url = url
        return res

    async def check(self, url: str) -> FetchResult:
        """Lightweight availability check (HEAD, falling back to a small GET)."""
        saved, self.retries = self.retries, min(self.retries, 1)  # checks favour speed over persistence
        try:
            res = await self.fetch_following(url, "HEAD")
            refused = res.status is None and res.error and res.error.startswith(("blocked", "ConnectError"))
            if not refused and (res.status is None or res.status in (403, 405, 501) or res.status >= 500):
                res = await self.fetch_following(url, "GET", max_body=64 * 1024)
            return res
        finally:
            self.retries = saved
