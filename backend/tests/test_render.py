"""JavaScript rendering (optional feature). Skipped when Playwright or its Chromium build is not installed."""
from __future__ import annotations

import pytest

from tests.conftest import wait_for_job

pytest.importorskip("playwright")


def _crawl(client, auth, site_id: int, render: bool) -> dict:
    r = client.post(f"/api/sites/{site_id}/crawls", headers=auth,
                    json={"max_urls": 4, "max_depth": 1, "delay_ms": 0, "use_sitemaps": False, "check_external_links": False, "render_js": render})
    assert r.status_code == 202, r.text
    job = wait_for_job(client, auth, r.json()["job_id"], timeout=240)
    if job["status"] == "failed" and ("Executable doesn't exist" in (job["error"] or "") or "playwright install" in (job["error"] or "")):
        pytest.skip("Chromium for Playwright is not installed (run: playwright install chromium)")
    assert job["status"] == "completed", job
    pages = client.get(f"/api/crawls/{r.json()['id']}/pages", headers=auth, params={"per_page": 50}).json()["items"]
    return {p["url"].rsplit("/", 1)[1]: p for p in pages}


def test_rendering_exposes_javascript_content(client, auth, fixture_site):
    site = client.post("/api/sites", headers=auth, json={"name": "JS", "url": fixture_site.url + "/js-page"}).json()
    try:
        raw = _crawl(client, auth, site["id"], render=False)
        assert raw["js-page"]["word_count"] < 20 and raw["js-page"]["h1"] is None and "js-only-link" not in raw
        rendered = _crawl(client, auth, site["id"], render=True)
        assert rendered["js-page"]["word_count"] > 300 and rendered["js-page"]["h1"] == "Rendered heading"
        assert "js-only-link" in rendered  # links created by JavaScript are discovered and crawled
    finally:
        client.delete(f"/api/sites/{site['id']}", headers=auth)
