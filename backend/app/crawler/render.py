"""Optional JavaScript rendering with Playwright (``pip install playwright && playwright install chromium``).

Every request the browser makes is intercepted and vetted (scheme, port, hostname, resolved addresses),
then performed with redirects disabled: a redirect response is never followed, because the browser
would follow it without consulting the interceptor. WebSockets are closed, heavy resource types are
skipped, and the final document URL is re-checked before its DOM is used. The request itself still
does its own DNS lookup after our check, so rendering offers weaker rebinding protection than the
HTTP fetcher (documented in KNOWN_LIMITATIONS.md).
"""
from __future__ import annotations

import logging
from urllib.parse import urlsplit

from ..config import get_settings
from ..security.ssrf import resolve_and_check, validate_url

log = logging.getLogger("seo.render")


def playwright_available() -> bool:
    try:
        import playwright  # noqa: F401
        return True
    except ImportError:
        return False


class Renderer:
    def __init__(self, user_agent: str, allow_private: bool, timeout_s: float = 25.0) -> None:
        self.user_agent = user_agent
        self.allow_private = allow_private
        self.timeout_ms = int(timeout_s * 1000)
        self._pw = None
        self._browser = None
        self._context = None

    async def start(self) -> None:
        from playwright.async_api import async_playwright

        self._pw = await async_playwright().start()
        self._browser = await self._pw.chromium.launch(headless=True, chromium_sandbox=get_settings().render_sandbox)
        self._context = await self._browser.new_context(user_agent=self.user_agent, service_workers="block")
        await self._context.route("**/*", self._guard)
        if hasattr(self._context, "route_web_socket"):
            await self._context.route_web_socket("**/*", self._close_ws)

    @staticmethod
    async def _close_ws(ws) -> None:
        await ws.close()

    async def _check(self, url: str) -> None:
        validate_url(url, self.allow_private)
        parts = urlsplit(url)
        await resolve_and_check(
            parts.hostname or "", parts.port or (443 if parts.scheme == "https" else 80), self.allow_private
        )

    async def _guard(self, route) -> None:
        req = route.request
        if req.resource_type in ("image", "media", "font"):
            await route.abort()
            return
        try:
            await self._check(req.url)
            # Perform the request ourselves without following redirects: the browser follows
            # redirects internally without calling this handler, which would bypass the checks.
            resp = await route.fetch(max_redirects=0, timeout=self.timeout_ms)
            if 300 <= resp.status < 400:
                await route.abort("blockedbyclient")
                return
            await route.fulfill(response=resp)
        except Exception:  # noqa: BLE001 - any failure means "do not load"
            try:
                await route.abort()
            except Exception:  # noqa: BLE001 - route already handled or page closed
                pass

    async def _safe_content(self, page) -> str | None:
        """DOM of the page, but only if the document and every frame still sit on a vetted URL."""
        try:
            if page.url in ("", "about:blank") or page.url.startswith("chrome-error:"):
                return None  # navigation never committed (blocked, refused or redirected)
            for frame in page.frames:
                if frame.url and frame.url not in ("about:blank", "about:srcdoc"):
                    await self._check(frame.url)
            return await page.content()
        except Exception as exc:  # noqa: BLE001
            log.warning("render discarded for %s: %s", page.url, exc)
            return None

    async def render(self, url: str) -> str | None:
        """Return the DOM serialised after scripts ran, or None on failure."""
        page = await self._context.new_page()
        try:
            try:
                await page.goto(url, wait_until="networkidle", timeout=self.timeout_ms)
            except Exception as exc:  # noqa: BLE001
                log.warning("render failed for %s: %s", url, exc)
            return await self._safe_content(page)
        finally:
            await page.close()

    async def close(self) -> None:
        for obj in (self._context, self._browser):
            try:
                if obj:
                    await obj.close()
            except Exception:  # noqa: BLE001
                pass
        if self._pw:
            await self._pw.stop()
