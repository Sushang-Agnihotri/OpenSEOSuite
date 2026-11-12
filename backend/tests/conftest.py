"""Test configuration: isolated data directory, the flawed fixture website and a crawled site shared by tests."""
from __future__ import annotations

import os
import tempfile
import time

_TMP = tempfile.mkdtemp(prefix="seotk-test-")
os.environ.update({
    "SEO_DATA_DIR": _TMP,
    "SEO_DATABASE_URL": "",
    "SEO_ALLOW_PRIVATE_NETWORKS": "true",  # the fixture site runs on 127.0.0.1
    "SEO_SCHEDULER_ENABLED": "false",
    "SEO_LOGIN_RATE_LIMIT_PER_MINUTE": "1000",
    "SEO_API_RATE_LIMIT_PER_MINUTE": "100000",
    "SEO_SECRET_KEY": "test-secret-key-that-is-long-enough-for-hs256",
})

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from tests.fixture_site import FixtureServer  # noqa: E402


@pytest.fixture(scope="session")
def fixture_site():
    srv = FixtureServer().start()
    yield srv
    srv.stop()


@pytest.fixture(scope="session")
def client():
    from app.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def auth(client):
    r = client.post("/api/auth/register", json={"email": "owner@example.com", "password": "correct horse battery"})
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def wait_for_job(client, auth, job_id: int, timeout: float = 180.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        job = client.get(f"/api/jobs/{job_id}", headers=auth).json()
        if job["status"] in ("completed", "failed", "cancelled"):
            return job
        time.sleep(0.3)
    raise AssertionError(f"job {job_id} did not finish in {timeout}s")


@pytest.fixture(scope="session")
def crawled(client, auth, fixture_site):
    """A site pointing at the fixture website with one completed crawl."""
    r = client.post("/api/sites", headers=auth, json={"name": "Fixture", "url": fixture_site.url + "/"})
    assert r.status_code == 201, r.text
    site = r.json()
    r = client.post(f"/api/sites/{site['id']}/crawls", headers=auth, json={"delay_ms": 0, "concurrency": 8, "max_urls": 200, "exclude_patterns": ["/big/"]})
    assert r.status_code == 202, r.text
    crawl = r.json()
    job = wait_for_job(client, auth, crawl["job_id"])
    assert job["status"] == "completed", job
    return {"site": site, "crawl_id": crawl["id"], "base": fixture_site.url}
