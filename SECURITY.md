# Security Policy

## Reporting a vulnerability

Please do not open a public issue for security problems. Use GitHub's private vulnerability reporting ("Security" tab → "Report a
vulnerability") on the repository. Include the affected version, reproduction steps and impact. You should receive an acknowledgement
within a week.

What was reviewed, what was found and what is still open is recorded in [`docs/SECURITY_REVIEW.md`](docs/SECURITY_REVIEW.md).

## Threat model

The application is designed to be self-hosted by an individual or a small team on a network they control. The main risks considered:

| Risk | Control |
|---|---|
| **SSRF** — a user (or a crawled page via redirects) makes the server fetch internal resources | URL validation (scheme, credentials, ports, internal hostnames, literal IPs) plus a connection-level guard: every outgoing connection resolves the hostname, refuses non-public addresses (loopback, RFC 1918, link-local/metadata, CGNAT, multicast, IPv4-mapped/compatible, NAT64/6to4, site-local) and connects to the vetted IP, which defeats DNS rebinding. Redirects are followed manually so each hop is checked. Environment proxies are ignored. The guard refuses to install silently if the HTTP library changes. JavaScript rendering vets each browser request and disallows redirects |
| **Crawler abuse** (using it as a proxy or attack tool) | Authentication required; crawls are scoped to the site's host; per-host rate limiting and robots.txt by default; response-size, redirect, depth, URL and links-per-page caps; an overall deadline per request; binary bodies are not downloaded; fetched content is never returned raw to the client |
| **Denial of service** | No user- or site-supplied regular expressions (robots rules and crawl filters use a linear matcher); request-body size limit before anything is read; per-account background-job cap; hostile HTML is parsed off the event loop; sitemap/gzip size caps |
| **Credential theft** | Argon2id password hashing; constant-work login for unknown accounts; per-address and per-account login throttling; JWTs signed with a per-installation secret (key file created owner-only); changing the password ends all older sessions |
| **Broken access control** | Every site-scoped query checks ownership; other users' objects return 404. Integration settings and local Lighthouse runs are administrator-only. Covered by tests that call every endpoint without credentials and as a second user |
| **Injection** | SQLAlchemy bound parameters everywhere; sort keys are whitelisted; Pydantic validation on every request body; subprocesses use argument lists, never a shell |
| **XSS** | React SPA that never injects HTML from crawled data; only `http(s)` strings become links; JSON responses with `X-Content-Type-Options: nosniff`; restrictive Content-Security-Policy, `X-Frame-Options: DENY`, `Permissions-Policy`, cross-origin isolation headers, HSTS over HTTPS |
| **CSRF / OAuth login CSRF** | No cookies: authentication uses an `Authorization` header. The Search Console OAuth `state` is signed, single-use and bound to the account that started the flow; the code is exchanged only with that account's token |
| **Malicious uploads** | Only CSV/TSV/TXT, size-limited (and refused before being read), parsed in memory, never written to disk or executed |
| **Spreadsheet formula injection** | Exported cells that start with `= + - @` are prefixed with an apostrophe |
| **XML attacks** (sitemaps) | lxml parser with entity resolution, DTD loading and network access disabled; decompressed size capped |
| **Path traversal / UNC paths** | Static-file requests are vetted syntactically before any filesystem access |
| **Secrets in the repository** | No credentials are committed; `.env` and the data directory are git-ignored; the signing key is generated at first start |
| **Vulnerable dependencies** | `npm audit` clean; scheduled `pip-audit`/`npm audit`/`bandit` workflow; Dependabot; GitHub Actions pinned to commit SHAs |

## Operator checklist

- Put the app behind HTTPS (reverse proxy) if it is reachable from other machines, and set `SEO_TRUSTED_PROXIES` to the proxy's
  address so rate limiting sees real client addresses. Docker Compose publishes on `127.0.0.1` only; set `SEO_BIND=0.0.0.0` (or put
  the proxy in front) to expose it deliberately.
- Registration is closed after the first account. Keep it closed unless you want self-service sign-ups (`SEO_ALLOW_REGISTRATION=true`).
- Keep `SEO_ALLOW_PRIVATE_NETWORKS=false` unless you must audit internal sites; with it enabled any authenticated user can make the
  server request internal addresses.
- Do not install the Lighthouse CLI or the Playwright rendering extra on a server that can reach sensitive internal services unless you
  need them: a browser follows redirects and sub-resources the application cannot fully police.
- Treat the administrator-configured integration URLs (AI, SearXNG) as trusted: they may point at internal addresses (e.g. Ollama).
- Protect the data directory: integration secrets (API keys, OAuth tokens) are stored unencrypted in the database.
- Run a single API process (background jobs and rate limits are per process).
- Back up `SEO_DATA_DIR`.

## Known gaps

- Tokens cannot be revoked individually (changing the password or rotating `SEO_SECRET_KEY` invalidates sessions); there is no
  "sign out everywhere" button and no way to disable another user's account in the UI.
- In JavaScript-rendering mode the browser resolves DNS itself after the address check (weaker rebinding protection); local Lighthouse
  can request internal addresses during a run (blind SSRF), although its results are discarded.
- Rate limiting and lockouts are in-memory; they reset on restart and are not shared between processes.
- With registration open, the "email already registered" response reveals which emails have accounts.
- No audit log of user actions; no per-crawl total row budget (a hostile site can still make a crawl store a lot of data within the URL cap).
- Python dependencies are not hash-locked; Docker base images are not pinned by digest.
- No external penetration test has been performed.
