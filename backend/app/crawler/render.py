"""Optional JavaScript rendering with Playwright (``pip install playwright && playwright install chromium``).

Every request the browser makes is intercepted: non-http(s) schemes and hosts that resolve to
non-public addresses are aborted, and heavy resource types are skipped. Note that the browser
performs its own DNS lookup after our check, so rendering offers weaker rebinding protection than
the HTTP fetcher (documented in KNOWN_LIMITATIONS.md).
"""
from __future__ import annotations

import logging
from urllib.parse import urlsplit

from ..security.ssrf import UnsafeURLError, resolve_and_check, validate_url

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
        self._host_ok: dict[str, bool] = {}

    async def start(self) -> None:
        from playwright.async_api import async_playwright

        self._pw = await async_playwright().start()
        self._browser = await self._pw.chromium.launch(headless=True)
        self._context = await self._browser.new_context(user_agent=self.user_agent, service_workers="block")
        await self._context.route("**/*", self._guard)

    async def _guard(self, route) -> None:
        req = route.request
        url = req.url
        if req.resource_type in ("image", "media", "font"):
            await route.abort()
            return
        try:
            validate_url(url, self.allow_private)
            parts = urlsplit(url)
            host = parts.hostname or ""
            if host not in self._host_ok:
                await resolve_and_check(host, parts.port or (443 if parts.scheme == "https" else 80), self.allow_private)
                self._host_ok[host] = True
        except (UnsafeURLError, Exception):  # noqa: BLE001 - any failure means "do not load"
            await route.abort()
            return
        await route.continue_()

    async def render(self, url: str) -> str | None:
        """Return the DOM serialised after scripts ran, or None on failure."""
        page = await self._context.new_page()
        try:
            await page.goto(url, wait_until="networkidle", timeout=self.timeout_ms)
            return await page.content()
        except Exception as exc:  # noqa: BLE001
            log.warning("render failed for %s: %s", url, exc)
            try:
                return await page.content()
            except Exception:  # noqa: BLE001
                return None
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
