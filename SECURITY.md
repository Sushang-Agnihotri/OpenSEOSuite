# Security Policy

## Reporting a vulnerability

Please do not open a public issue for security problems. Use GitHub's private vulnerability reporting ("Security" tab → "Report a
vulnerability") on the repository. Include the affected version, reproduction steps and impact. You should receive an acknowledgement
within a week.

## Threat model

The application is designed to be self-hosted by an individual or a small team. The main risks considered:

| Risk | Control |
|---|---|
| **SSRF** — a user (or a crawled page via redirects) makes the server fetch internal resources | URL validation (scheme, credentials, ports, internal hostnames, literal IPs) plus a connection-level guard: every outgoing connection resolves the hostname, refuses non-public addresses (loopback, RFC 1918, link-local/metadata, CGNAT, multicast, IPv4-mapped/NAT64/6to4 forms) and connects to the vetted IP, which defeats DNS rebinding. Redirects are followed manually so each hop is checked. Environment proxies are ignored. |
| **Crawler abuse** (using it as a proxy or attack tool) | Authentication required; crawls are scoped to the site's host; per-host rate limiting and robots.txt by default; response-size, redirect, depth and URL caps; binary bodies are not downloaded; fetched content is never returned raw to the client. |
| **Credential theft** | Argon2id password hashing; constant-work login for unknown accounts; login rate limiting; JWTs signed with a per-installation secret. |
| **Broken access control** | Every site-scoped query checks ownership; other users' objects return 404. Integration settings are administrator-only. Covered by tests that call every endpoint without credentials and as a second user. |
| **Injection** | SQLAlchemy bound parameters everywhere (no string-built SQL); sort keys are whitelisted; Pydantic validation on every request body. |
| **XSS** | The UI is a React SPA that never injects HTML from crawled data; API responses are JSON with `X-Content-Type-Options: nosniff`; a restrictive Content-Security-Policy and `X-Frame-Options: DENY` are sent. |
| **CSRF** | Not applicable: authentication uses an `Authorization` header, not cookies. The Search Console OAuth callback is protected by a signed, short-lived `state` token. |
| **Malicious uploads** | Only CSV/TSV/TXT, size-limited, parsed in memory, never written to disk or executed. |
| **Spreadsheet formula injection** | Exported cells that start with `= + - @` are prefixed with an apostrophe. |
| **XML attacks** (sitemaps) | lxml parser with entity resolution, DTD loading and network access disabled; decompressed size capped. |
| **Secrets in the repository** | No credentials are committed; `.env` and the data directory are git-ignored; the signing key is generated at first start. |

## Operator checklist

- Put the app behind HTTPS (reverse proxy) if it is reachable from other machines.
- After creating your accounts set `SEO_ALLOW_REGISTRATION=false`.
- Keep `SEO_ALLOW_PRIVATE_NETWORKS=false` unless you must audit internal sites; with it enabled any authenticated user can make the
  server request internal addresses.
- Protect the data directory: integration secrets (API keys, OAuth tokens) are stored unencrypted in the database.
- Run a single API process (background jobs and rate limits are per process).
- Back up `SEO_DATA_DIR`.

## Known gaps

- Tokens cannot be revoked individually; rotate `SEO_SECRET_KEY` to invalidate all sessions.
- In JavaScript-rendering mode the headless browser performs its own DNS resolution after the address check (weaker rebinding protection).
- Rate limiting is in-memory; it resets on restart and is not shared between processes.
- No audit log of user actions.
