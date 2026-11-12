"""Security tests: SSRF protection, authentication, authorisation, input handling and rate limiting."""
from __future__ import annotations

import socket

import pytest

from app.crawler.fetcher import Fetcher
from app.security.auth import hash_password, verify_password
from app.security.ratelimit import SlidingWindow, limiter
from app.security.ssrf import UnsafeURLError, is_ip_allowed, resolve_and_check, validate_url


@pytest.mark.parametrize("url", [
    "http://127.0.0.1/", "http://localhost/", "http://10.0.0.5/", "http://192.168.1.1/admin", "http://172.16.0.1/",
    "http://169.254.169.254/latest/meta-data/", "http://[::1]/", "http://[::ffff:127.0.0.1]/", "http://0.0.0.0/",
    "http://100.64.0.1/", "http://[fd00::1]/", "http://[64:ff9b::7f00:1]/", "http://2130706433/", "http://intranet/",
    "http://printer.local/", "http://db.internal/", "ftp://example.com/", "file:///etc/passwd", "gopher://example.com/",
    "http://user:pass@example.com/", "http://example.com:22/", "http://example.com:6379/", "", "not a url",
])
def test_validate_url_rejects(url):
    with pytest.raises(UnsafeURLError):
        validate_url(url, allow_private=False)


@pytest.mark.parametrize("url", ["https://example.com/", "http://example.com:8080/x?y=1", "https://sub.example.co.uk/a", "https://93.184.216.34/"])
def test_validate_url_accepts(url):
    assert validate_url(url, allow_private=False) == url


def test_ip_policy():
    assert is_ip_allowed("93.184.216.34") and is_ip_allowed("2606:2800:220:1:248:1893:25c8:1946")
    for ip in ("127.0.0.1", "10.1.2.3", "192.168.0.1", "169.254.169.254", "::1", "fe80::1", "224.0.0.1", "0.0.0.0", "::ffff:10.0.0.1", "2002:7f00:1::"):
        assert not is_ip_allowed(ip), ip
    assert is_ip_allowed("127.0.0.1", allow_private=True) and not is_ip_allowed("224.0.0.1", allow_private=True)


async def test_resolution_is_checked_at_connect_time(monkeypatch):
    """A public-looking hostname that resolves to an internal address must be refused (DNS rebinding / split-horizon)."""
    import asyncio

    async def fake_getaddrinfo(host, port, **kw):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.7", port))]

    monkeypatch.setattr(asyncio.get_running_loop(), "getaddrinfo", fake_getaddrinfo)
    with pytest.raises(UnsafeURLError):
        await resolve_and_check("public-looking.example", 80, allow_private=False)
    async with Fetcher(allow_private=False, retries=0) as fetcher:
        res = await fetcher.fetch("http://public-looking.example/")
        assert res.status is None and res.error.startswith("blocked")
        # one address public, one private: still refused
        async def mixed(host, port, **kw):
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", port)), (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", port))]
        monkeypatch.setattr(asyncio.get_running_loop(), "getaddrinfo", mixed)
        res = await fetcher.fetch("http://mixed.example/")
        assert res.error.startswith("blocked")


async def test_fetcher_blocks_private_targets_and_redirects(fixture_site):
    async with Fetcher(allow_private=False, retries=0) as strict:
        res = await strict.fetch(fixture_site.url + "/")
        assert res.status is None and res.error.startswith("blocked")
    async with Fetcher(allow_private=True, retries=0) as lax:
        res = await lax.fetch_following(fixture_site.url + "/redirect-1")
        assert res.status == 200 and [h["status"] for h in res.chain] == [301, 302, 200] and res.final_url.endswith("/about")
        loop = await lax.fetch_following(fixture_site.url + "/loop-a")
        assert loop.redirect_loop
        big = await lax.fetch(fixture_site.url + "/img/large.jpg", max_body=1000)
        assert big.truncated and len(big.body) <= 1000  # response size limits are enforced
        skipped = await lax.fetch(fixture_site.url + "/img/large.jpg", text_only=True)
        assert skipped.status == 200 and skipped.body == b""  # binary bodies are not downloaded during crawls


def test_password_hashing():
    h = hash_password("s3cret-passphrase")
    assert h.startswith("$argon2id$") and "s3cret" not in h
    assert verify_password("s3cret-passphrase", h) and not verify_password("wrong", h) and not verify_password("x", "not-a-hash")


def test_sliding_window():
    w = SlidingWindow()
    assert all(w.allow("k", 3) for _ in range(3)) and not w.allow("k", 3) and w.allow("other", 3)


# ------------------------------------------------------------------ API-level
def test_auth_required_everywhere(client):
    app = client.app
    public = {"/api/auth/status", "/api/auth/register", "/api/auth/login", "/api/health", "/api/rules", "/api/gsc/callback",
              "/api/openapi.json", "/api/docs", "/api/redoc", "/api/docs/oauth2-redirect"}
    checked = 0
    for path, ops in app.openapi()["paths"].items():
        if path in public:
            continue
        for method in ops:
            url = path.replace("{site_id}", "1").replace("{crawl_id}", "1").replace("{page_id}", "1").replace("{rule_id}", "x") \
                .replace("{job_id}", "1").replace("{monitor_id}", "1").replace("{competitor_id}", "1").replace("{result_id}", "1").replace("{other_id}", "1")
            r = client.request(method.upper(), url)
            assert r.status_code == 401, f"{method.upper()} {path} answered {r.status_code} without credentials"
            checked += 1
    assert checked > 80


def test_register_login_and_token_checks(client, auth):
    assert client.get("/api/auth/me", headers=auth).json()["is_admin"] is True  # first account is the administrator
    assert client.post("/api/auth/register", json={"email": "owner@example.com", "password": "another password"}).status_code == 409
    assert client.post("/api/auth/register", json={"email": "short@example.com", "password": "short"}).status_code == 422
    assert client.post("/api/auth/register", json={"email": "not-an-email", "password": "long enough password"}).status_code == 422
    assert client.post("/api/auth/login", json={"email": "owner@example.com", "password": "wrong password"}).status_code == 401
    assert client.post("/api/auth/login", json={"email": "nobody@example.com", "password": "wrong password"}).status_code == 401
    ok = client.post("/api/auth/login", json={"email": "OWNER@example.com", "password": "correct horse battery"})
    assert ok.status_code == 200 and "password" not in ok.text.replace("password_hash", "")
    assert client.get("/api/auth/me", headers={"Authorization": "Bearer garbage"}).status_code == 401
    forged = ok.json()["access_token"][:-4] + "AAAA"
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {forged}"}).status_code == 401


def test_tenant_isolation_and_admin_only(client, auth, crawled):
    r = client.post("/api/auth/register", json={"email": "second@example.com", "password": "second user password"})
    other = {"Authorization": f"Bearer {r.json()['access_token']}"}
    assert r.json()["user"]["is_admin"] is False
    sid, cid = crawled["site"]["id"], crawled["crawl_id"]
    for url in (f"/api/sites/{sid}", f"/api/sites/{sid}/overview", f"/api/crawls/{cid}", f"/api/crawls/{cid}/pages", f"/api/crawls/{cid}/issues",
                f"/api/crawls/{cid}/export", f"/api/crawls/{cid}/report.pdf", f"/api/sites/{sid}/keywords", f"/api/sites/{sid}/backlinks/summary",
                f"/api/sites/{sid}/monitors", f"/api/sites/{sid}/gsc/performance", f"/api/sites/{sid}/competitors"):
        assert client.get(url, headers=other).status_code == 404, url
    assert client.delete(f"/api/sites/{sid}", headers=other).status_code == 404
    assert client.post(f"/api/sites/{sid}/crawls", headers=other, json={}).status_code == 404
    assert client.get("/api/sites", headers=other).json() == []
    assert client.get("/api/settings", headers=other).status_code == 403
    assert client.put("/api/settings", headers=other, json={"ai": {"provider": "ollama"}}).status_code == 403


def test_settings_secrets_are_masked(client, auth):
    r = client.put("/api/settings", headers=auth, json={"pagespeed": {"api_key": "AIza-super-secret"}, "serp": {"provider": "brave", "brave_key": "brv-secret"}})
    assert r.status_code == 200 and "super-secret" not in r.text and "brv-secret" not in r.text
    assert r.json()["pagespeed"]["api_key"] == "********"
    # echoing the mask back must not overwrite the stored secret
    client.put("/api/settings", headers=auth, json={"pagespeed": {"api_key": "********"}})
    from app.db import session_scope
    from app.services.settings_store import get_setting
    with session_scope() as db:
        assert get_setting(db, "pagespeed")["api_key"] == "AIza-super-secret"
    assert client.put("/api/settings", headers=auth, json={"serp": {"provider": "evil"}}).status_code == 422
    assert client.put("/api/settings", headers=auth, json={"serp": {"searxng_url": "file:///etc/passwd"}}).status_code == 422
    client.put("/api/settings", headers=auth, json={"serp": {"provider": "none", "brave_key": ""}, "pagespeed": {"api_key": ""}})


def test_injection_inputs_are_inert(client, auth, crawled):
    cid = crawled["crawl_id"]
    for payload in ("' OR '1'='1", "'; DROP TABLE pages;--", "%' UNION SELECT password_hash FROM users--", "<script>alert(1)</script>"):
        r = client.get(f"/api/crawls/{cid}/pages", headers=auth, params={"q": payload, "sort": payload, "status": payload})
        assert r.status_code == 200 and r.json()["total"] == 0
        assert r.headers["content-type"].startswith("application/json")
    assert client.get(f"/api/crawls/{cid}/pages", headers=auth).json()["total"] > 30  # table still intact
    r = client.post("/api/sites", headers=auth, json={"name": "<img src=x onerror=alert(1)>", "url": "https://example.com"})
    assert r.status_code == 201 and r.headers["x-content-type-options"] == "nosniff"
    client.delete(f"/api/sites/{r.json()['id']}", headers=auth)


def test_unsafe_urls_rejected_by_api(client, auth, monkeypatch):
    from app.config import get_settings
    monkeypatch.setattr(get_settings(), "allow_private_networks", False)
    for url in ("http://169.254.169.254/latest/meta-data/", "http://localhost:8000/", "file:///etc/passwd", "http://10.0.0.1/"):
        assert client.post("/api/sites", headers=auth, json={"name": "x", "url": url}).status_code == 422, url
        assert client.post("/api/schema/validate", headers=auth, json={"url": url}).status_code == 422, url
        assert client.post("/api/content/fetch", headers=auth, json={"url": url}).status_code == 422, url
        assert client.post("/api/pagespeed/run", headers=auth, json={"url": url}).status_code == 422, url


def test_upload_restrictions(client, auth, crawled):
    sid = crawled["site"]["id"]
    assert client.post(f"/api/sites/{sid}/backlinks/import", headers=auth, files={"file": ("x.exe", b"MZ\x00\x00", "application/octet-stream")}).status_code == 415
    assert client.post(f"/api/sites/{sid}/backlinks/import", headers=auth, files={"file": ("x.csv", b"PK\x03\x04\x00\x00binary", "text/csv")}).status_code == 415
    from app.config import get_settings
    big = b"source url\n" + b"https://example.com/a\n" * (get_settings().max_upload_mb * 1024 * 1024 // 20)
    assert client.post(f"/api/sites/{sid}/backlinks/import", headers=auth, files={"file": ("x.csv", big, "text/csv")}).status_code == 413


def test_login_rate_limit(client, monkeypatch):
    from app.config import get_settings
    monkeypatch.setattr(get_settings(), "login_rate_limit_per_minute", 5)
    limiter._hits.clear()
    codes = [client.post("/api/auth/login", json={"email": "owner@example.com", "password": "bad"}).status_code for _ in range(8)]
    assert codes[:5] == [401] * 5 and codes[5:] == [429] * 3
    limiter._hits.clear()


def test_security_headers(client):
    r = client.get("/api/health")
    assert r.headers["x-frame-options"] == "DENY" and "default-src 'self'" in r.headers["content-security-policy"]
    assert r.headers["referrer-policy"] and r.headers["x-request-id"]
