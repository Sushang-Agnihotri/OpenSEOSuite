"""API-level regression tests for the security review: auth, limits, OAuth binding, caps, headers."""
from __future__ import annotations

import asyncio
import os
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.config import Settings, get_settings
from app.crawler.fetcher import Fetcher
from app.crawler.parser import MAX_LINKS_PER_PAGE, parse_html
from app.security.ratelimit import client_ip, limiter
from app.security.ssrf import is_ip_allowed


def _login(client, email: str, password: str) -> dict:
    r = client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _second_user(client, email: str = "member@example.com", password: str = "member password 123") -> dict:
    r = client.post("/api/auth/register", json={"email": email, "password": password})
    if r.status_code == 409:
        return _login(client, email, password)
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


# ------------------------------------------------------------------------------------------- SSRF edges
def test_deprecated_ipv6_ranges_are_not_public():
    assert not is_ip_allowed("::127.0.0.1")
    assert not is_ip_allowed("::10.0.0.1")
    assert not is_ip_allowed("fec0::1")
    assert not is_ip_allowed("::ffff:127.0.0.1")
    assert is_ip_allowed("2606:4700:4700::1111")
    assert is_ip_allowed("8.8.8.8")
    assert is_ip_allowed("::1", allow_private=True)  # local development must keep working


# -------------------------------------------------------------------------- static files / UNC paths
def test_spa_path_is_vetted_before_the_filesystem_is_touched(tmp_path, monkeypatch):
    from app.main import _static_file

    (tmp_path / "app.js").write_text("x")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "a.css").write_text("x")
    dist = tmp_path.resolve()
    assert _static_file(dist, "app.js") == dist / "app.js"
    assert _static_file(dist, "sub/a.css") == dist / "sub" / "a.css"
    assert _static_file(dist, "missing.js") is None

    def boom(self, *a, **k):
        raise AssertionError("the filesystem was touched for a hostile path")

    monkeypatch.setattr(Path, "resolve", boom)
    for hostile in ("/attacker/share/x", "\\\\attacker\\share\\x", "..\\..\\secret", "../secret", "a/../../secret", "C:/Windows/win.ini",
                    "c:secret", "a\x00b", "", "//host/share"):
        assert _static_file(dist, hostile) is None, hostile


# ------------------------------------------------------------------------------------- body size limit
def test_oversized_json_body_is_refused_before_authentication(client):
    big = b'{"email":"a@b.co","password":"' + b"x" * (2 * 1024 * 1024) + b'"}'
    r = client.post("/api/auth/login", content=big, headers={"content-type": "application/json"})
    assert r.status_code == 413


def test_chunked_body_cannot_dodge_the_limit(client):
    def chunks():
        for _ in range(40):
            yield b"x" * 65536  # 2.5 MB, no Content-Length header

    r = client.post("/api/auth/login", content=chunks(), headers={"content-type": "application/json"})
    assert r.status_code == 413


def test_oversized_upload_is_refused(client, auth, monkeypatch):
    monkeypatch.setattr(get_settings(), "max_upload_mb", 1)
    r = client.post("/api/sites/1/keywords/import", headers=auth, files={"file": ("k.csv", b"a,b\n" * 800_000, "text/csv")})
    assert r.status_code == 413


def test_normal_requests_still_work(client, auth):
    assert client.get("/api/auth/me", headers=auth).status_code == 200


# ------------------------------------------------------------------------------------------ accounts
def test_password_change_ends_old_sessions(client):
    old = _second_user(client, "rotate@example.com", "first password 123")
    assert client.get("/api/auth/me", headers=old).status_code == 200
    r = client.post("/api/auth/password", headers=old, json={"current_password": "first password 123", "new_password": "second password 456"})
    assert r.status_code == 200
    fresh = {"Authorization": f"Bearer {r.json()['access_token']}"}
    assert client.get("/api/auth/me", headers=old).status_code == 401  # tokens from before the change are dead
    assert client.get("/api/auth/me", headers=fresh).status_code == 200
    assert client.post("/api/auth/login", json={"email": "rotate@example.com", "password": "first password 123"}).status_code == 401
    _login(client, "rotate@example.com", "second password 456")


def test_tokens_without_the_password_fingerprint_are_rejected(client):
    from app.security.auth import create_access_token

    me = client.get("/api/auth/me", headers=_second_user(client)).json()
    legacy = {"Authorization": f"Bearer {create_access_token(me['id'])}"}  # a validly signed token with no fingerprint
    assert client.get("/api/auth/me", headers=legacy).status_code == 401


def test_registration_can_be_closed(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "allow_registration", False)
    assert client.get("/api/auth/status").json()["registration_open"] is False
    r = client.post("/api/auth/register", json={"email": "late@example.com", "password": "late password 123"})
    assert r.status_code == 403


def test_registration_is_closed_by_default():
    assert Settings.model_fields["allow_registration"].default is False  # (the test environment overrides it)


def test_status_hides_network_policy_from_anonymous_callers(client, auth):
    assert "private_networks_allowed" not in client.get("/api/auth/status").json()
    assert "private_networks_allowed" in client.get("/api/auth/status", headers=auth).json()


def test_failed_logins_lock_the_account_temporarily(client):
    email = "victim@example.com"
    limiter.clear(f"fail:{email}")
    try:
        for _ in range(20):
            assert client.post("/api/auth/login", json={"email": email, "password": "nope nope nope"}).status_code == 401
        r = client.post("/api/auth/login", json={"email": email, "password": "nope nope nope"})
        assert r.status_code == 429 and r.headers.get("retry-after")
    finally:
        limiter.clear(f"fail:{email}")


def test_successful_login_resets_the_failure_counter(client):
    me = "reset@example.com"
    _second_user(client, me, "reset password 123")
    limiter.clear(f"fail:{me}")
    for _ in range(5):
        assert client.post("/api/auth/login", json={"email": me, "password": "wrong wrong"}).status_code == 401
    _login(client, me, "reset password 123")
    assert limiter.count(f"fail:{me}", 900) == 0


# ------------------------------------------------------------------------------------ proxy / client IP
def _req(peer: str, xff: str | None = None):
    headers = {"x-forwarded-for": xff} if xff else {}
    return SimpleNamespace(client=SimpleNamespace(host=peer), headers=headers)


def test_forwarded_for_is_ignored_unless_the_peer_is_a_trusted_proxy(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "trusted_proxies", "")
    assert client_ip(_req("203.0.113.9", "1.2.3.4")) == "203.0.113.9"
    monkeypatch.setattr(s, "trusted_proxies", "10.0.0.0/8, 172.17.0.2")
    assert client_ip(_req("203.0.113.9", "1.2.3.4")) == "203.0.113.9"  # an untrusted peer cannot choose its address
    assert client_ip(_req("10.0.0.5", "1.2.3.4")) == "1.2.3.4"
    assert client_ip(_req("10.0.0.5", "9.9.9.9, 1.2.3.4, 10.0.0.9")) == "1.2.3.4"  # spoofed left entries are ignored
    assert client_ip(_req("172.17.0.2")) == "172.17.0.2"
    assert client_ip(_req("10.0.0.5", "garbage, 10.1.1.1")) == "10.0.0.5"


# --------------------------------------------------------------------------------------- Search Console
def test_oauth_state_is_bound_to_the_account_and_single_use(client):
    from app.integrations import gsc

    a = client.get("/api/auth/me", headers=_second_user(client, "oauth-a@example.com")).json()["id"]
    b = client.get("/api/auth/me", headers=_second_user(client, "oauth-b@example.com")).json()["id"]
    state = gsc.issue_state(a)
    with pytest.raises(gsc.GscForbidden):
        gsc.consume_state(state, b)  # a victim completing someone else's consent link is refused
    state = gsc.issue_state(a)
    gsc.consume_state(state, a)
    with pytest.raises(gsc.GscForbidden):
        gsc.consume_state(state, a)  # replay


def test_oauth_exchange_rejects_a_state_from_another_account(client):
    from app.integrations import gsc

    a = client.get("/api/auth/me", headers=_second_user(client, "oauth-c@example.com")).json()["id"]
    other = _second_user(client, "oauth-d@example.com")
    r = client.post("/api/gsc/exchange", headers=other, json={"code": "abc", "state": gsc.issue_state(a)})
    assert r.status_code == 403
    assert client.post("/api/gsc/exchange", headers=other, json={"code": "abc", "state": "not-a-token"}).status_code == 403  # never 401: that would sign the user out


def test_oauth_callback_only_forwards_to_the_app(client):
    r = client.get("/api/gsc/callback?code=abc&state=xyz", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/search-console#gsc_code=abc&gsc_state=xyz"  # fragment: not sent to servers or logs
    assert r.headers["cache-control"] == "no-store" and r.headers["referrer-policy"] == "no-referrer"
    cancelled = client.get("/api/gsc/callback?error=access_denied", follow_redirects=False)
    assert cancelled.headers["location"] == "/search-console#gsc_error=cancelled"
    assert client.get("/api/gsc/callback?code=" + "a" * 3000 + "&state=x", follow_redirects=False).headers["location"].endswith("cancelled")


# ----------------------------------------------------------------------------------------- job caps
def test_per_user_job_cap(client, monkeypatch):
    from app.jobs import JobLimitError, JobManager

    monkeypatch.setattr(get_settings(), "max_jobs_per_user", 1)

    async def scenario():
        mgr, gate = JobManager(), asyncio.Event()

        async def work(_ctx):
            await gate.wait()
            return {}

        mgr.start("t", work, owner_id=1)
        with pytest.raises(JobLimitError):
            mgr.start("t", work, owner_id=1)
        mgr.start("t", work, owner_id=None)  # system jobs are not capped
        gate.set()
        await asyncio.sleep(0.3)
        mgr.start("t", work, owner_id=1)  # a finished job frees the slot
        await mgr.shutdown()

    asyncio.run(scenario())


def test_monitor_cannot_be_started_twice(client, auth, crawled, monkeypatch):
    from app.services import monitoring

    sid = crawled["site"]["id"]
    m = client.post(f"/api/sites/{sid}/monitors", headers=auth, json={"kind": "uptime", "interval_hours": 6}).json()
    monkeypatch.setattr(monitoring, "_active_monitors", {m["id"]})
    r = client.post(f"/api/monitors/{m['id']}/run", headers=auth)
    assert r.status_code == 409


# ----------------------------------------------------------------------------------- admin-only / input
def test_local_lighthouse_requires_an_administrator(client, crawled):
    member = _second_user(client)
    r = client.post("/api/pagespeed/run", headers=member, json={"url": crawled["base"] + "/", "source": "local", "strategy": "mobile"})
    assert r.status_code == 403


@pytest.mark.parametrize("url", ["http://user:pw@internal.example/", "http://host.example/path?x=1", "http://host.example/#frag", "ftp://host.example/"])
def test_integration_urls_are_restricted(client, auth, url):
    r = client.put("/api/settings", headers=auth, json={"ai": {"provider": "ollama", "base_url": url}})
    assert r.status_code == 422, r.text


# ------------------------------------------------------------------------------------------- headers
def test_security_headers(client):
    h = client.get("/api/health").headers
    assert h["x-content-type-options"] == "nosniff" and h["x-frame-options"] == "DENY"
    assert "script-src 'self'" in h["content-security-policy"] and "object-src 'none'" in h["content-security-policy"]
    assert h["permissions-policy"].startswith("camera=()")
    assert h["cross-origin-opener-policy"] == "same-origin" and h["cache-control"] == "no-store"
    assert "strict-transport-security" not in h
    assert "max-age" in client.get("/api/health", headers={"X-Forwarded-Proto": "https"}).headers["strict-transport-security"]
    docs = client.get("/api/docs").headers["content-security-policy"]
    assert "cdn.jsdelivr.net" in docs and "frame-ancestors 'none'" in docs


# ---------------------------------------------------------------------------------------------- files
@pytest.mark.skipif(os.name == "nt", reason="POSIX permission bits")
def test_generated_secret_key_is_owner_only(tmp_path):
    s = Settings(_env_file=None, data_dir=str(tmp_path), secret_key="")
    assert len(s.jwt_secret) >= 48
    assert (tmp_path / ".secret_key").stat().st_mode & 0o777 == 0o600


# ------------------------------------------------------------------------------------- fetch deadline
def test_slow_drip_server_cannot_hold_a_connection_forever():
    async def drip(_reader, writer):
        writer.write(b"HTTP/1.1 200 OK\r\nContent-Type: text/html\r\nContent-Length: 1000000\r\n\r\n")
        try:
            for _ in range(200):
                writer.write(b"a")
                await writer.drain()
                await asyncio.sleep(0.2)  # always inside the per-read timeout
        except (ConnectionError, asyncio.CancelledError):
            pass
        finally:
            writer.close()

    async def scenario():
        server = await asyncio.start_server(drip, "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        started = time.monotonic()
        async with Fetcher(timeout_s=0.5, retries=0, allow_private=True) as f:
            res = await f.fetch(f"http://127.0.0.1:{port}/", max_body=1000)
        server.close()
        return res, time.monotonic() - started

    res, elapsed = asyncio.run(scenario())
    assert res.error == "timeout" and elapsed < 6


# ---------------------------------------------------------------------------------------- parser caps
def test_link_extraction_is_capped():
    anchors = "".join(f'<a href="/p{i}">l{i}</a>' for i in range(MAX_LINKS_PER_PAGE + 1500))
    page = parse_html(f"<html><head><title>t</title></head><body>{anchors}</body></html>".encode(), "https://example.com/", "text/html")
    assert len(page.links) == MAX_LINKS_PER_PAGE


# ------------------------------------------------------------------------------------ crawl persistence
def test_crawl_totals_include_a_slow_final_batch(client, auth, fixture_site, monkeypatch):
    """Pages are written in batches of 40. A batch still being written when the crawl ends used to be missing from the
    totals (a flaky 460-of-500 on slow CI disks); the final flush must wait for it."""
    from app.crawler import engine
    from tests.conftest import wait_for_job

    original = engine.Crawler._flush_sync

    def slow(self, batch):
        time.sleep(0.03 * len(batch))  # a full batch of 40 takes longer than the small final one, so it finishes last
        return original(self, batch)

    monkeypatch.setattr(engine.Crawler, "_flush_sync", slow)
    site = client.post("/api/sites", headers=auth, json={"name": "Slow flush", "url": fixture_site.url + "/big/0"}).json()
    try:
        r = client.post(f"/api/sites/{site['id']}/crawls", headers=auth,
                        json={"max_urls": 100, "delay_ms": 0, "concurrency": 16, "use_sitemaps": False, "check_external_links": False}).json()
        assert wait_for_job(client, auth, r["job_id"], timeout=120)["status"] == "completed"
        stats = client.get(f"/api/crawls/{r['id']}", headers=auth).json()["stats"]
        assert stats["total_urls"] == 100 and stats["html_pages"] == 100
    finally:
        client.delete(f"/api/sites/{site['id']}", headers=auth)
