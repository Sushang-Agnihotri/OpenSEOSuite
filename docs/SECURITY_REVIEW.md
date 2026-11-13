# Security review (0.1.0)

This records what was checked before publication, what was found, and what is still open. It is an honest account, not a
certificate: the review was carried out by reading the code (including an independent, adversarial read-only review pass),
by running static scanners and dependency audits, and by writing regression tests for every confirmed problem.
**No external penetration test has been done.** Treat the application as suitable for a trusted team on a network you control, not as
hardened for hostile multi-tenant hosting.

## Method

| Step | Tool or approach | Result |
|---|---|---|
| Independent code review | Adversarial read of every outbound request path, auth/authorisation path, parser, export, upload, static-file, OAuth and deployment file | 18 findings (below) |
| Python dependency audit | `pip-audit` | 1 advisory left, not reachable (see "Accepted") |
| Frontend dependency audit | `npm audit` | 8 advisories (2 critical, 1 high) before; **0** after upgrading Vite, Vitest and React Router |
| Static analysis | `ruff` with the security rule set (`S`) and `bandit` | Only false positives left (see "Accepted") |
| Regression tests | 60 new tests (53 backend, 7 frontend): matching, DoS, auth, limits, OAuth, SSRF, headers, caps, safe links | all pass |
| Live check | Hardened server run locally: headers, token invalidation, UNC-style paths, OAuth fragment flow, body limit, Swagger UI under its CSP | as designed |

## Findings and status

Severity is the reviewer's estimate for a default installation unless noted.

| # | Severity | Finding | Status |
|---|---|---|---|
| 1 | High (only with the optional rendering extra) | Playwright followed redirects without consulting the request interceptor, so a page could bounce the headless browser to an internal address and have its DOM stored | **Fixed.** Every browser request is vetted and then performed with redirects disabled; WebSockets are closed; every frame URL is re-checked before the DOM is used; the Chromium sandbox is on by default (`SEO_RENDER_SANDBOX`). The browser/Playwright still resolve DNS themselves, so rebinding protection is weaker than for plain fetching (documented) |
| 2 | High (only if the `lighthouse` CLI is installed) | Local Lighthouse validated only the first hostname; Chrome then followed redirects freely; no concurrency limit; `--no-sandbox`; stderr echoed | **Mitigated.** Administrator-only; one run at a time; sandbox kept unless running as root; the final URL is re-checked and the result discarded if it is not public; errors are logged, not echoed. Chrome can still *request* an internal URL during the run (blind SSRF) — do not install Lighthouse on a server that can reach sensitive internal services |
| 3 | Medium | A crawled site's `robots.txt` could freeze the whole server (regex built from `Disallow` wildcards, catastrophic backtracking) | **Fixed.** Linear-time matcher with no regular-expression engine; results identical to the old matcher on normal rules (tested) |
| 4 | Medium | User-supplied include/exclude **regular expressions** ran on the event loop | **Fixed, behaviour change.** Patterns are now plain text with `*`, `^`, `$` (same linear matcher). Regular expressions are no longer accepted |
| 5 | Medium | No request-body size limit; bodies were read before authentication | **Fixed.** Middleware rejects by `Content-Length` and counts streamed bytes: 1 MB for JSON, `SEO_MAX_UPLOAD_MB` + 1 for uploads |
| 6 | Medium (Windows hosts) | Catch-all static route resolved attacker-chosen UNC paths (SMB connection, NTLM hash leak) | **Fixed.** The path is rejected syntactically (leading `/`, `\`, `:`, `..`, NUL) before any filesystem call; tested with the filesystem call patched to fail |
| 7 | Medium | Search Console OAuth `state` was not bound to the browser session: a victim finishing someone else's consent link attached their Google account to the attacker's account | **Fixed.** The callback only forwards `code`/`state` in the URL fragment to the app, which completes the exchange with the signed-in user's token; `state` carries a one-time server-side nonce and must belong to that user |
| 8 | Medium | No total deadline per fetch: a slow-drip server could hold a job slot for days | **Fixed.** Overall deadline (3 x timeout plus a 256 KiB/s minimum transfer rate) on every request |
| 9 | Medium/Low | Open registration by default, first-account race, public status leaked network policy, Compose published on all interfaces | **Fixed.** Registration closed by default after the first account (`SEO_ALLOW_REGISTRATION=true` to open); first-admin creation is atomic; the status endpoint hides the network policy from anonymous callers; Compose binds to `127.0.0.1` by default (`SEO_BIND`). *Still true:* when registration is open, the "email already registered" answer reveals which emails have accounts |
| 10 | Low | Rate limiting keyed on the socket peer (shared bucket behind a proxy, spoofable if `X-Forwarded-For` were trusted blindly) | **Fixed.** `SEO_TRUSTED_PROXIES` selects the proxies whose `X-Forwarded-For` is believed (right-most untrusted hop); malformed headers are ignored; a per-account failed-login lockout (20 per 15 minutes) was added; the app shell is rate limited too |
| 11 | Low | Unbounded links per page | **Partly fixed.** 5,000 links per page; text and JSON-LD were already capped. There is no per-crawl total row budget yet |
| 12 | Low | `javascript:` / `data:` URLs from crawled data could become live links (blocked in practice by the CSP) | **Fixed.** Only `http(s)` strings render as links |
| 13 | Low | Administrator-set integration URLs (AI, SearXNG) bypass the SSRF guard and responses were echoed | **Mitigated by design.** Pointing at `localhost` (Ollama) is the intended use, so these URLs are trusted administrator configuration. Credentials/query/fragment are rejected and remote error bodies are no longer echoed |
| 14 | Low | No per-user job fairness; "run now" bypassed the one-crawl-per-site rule | **Fixed.** `SEO_MAX_JOBS_PER_USER` (default 8); a monitor cannot be started twice; audit monitors respect a running crawl |
| 15 | Low | Hostile HTML parsed on the event loop in two endpoints | **Fixed.** Parsing runs in a worker thread |
| 16 | Low | Secret key file readable by other local users; tokens survived a password change | **Fixed.** Key created with mode 0600; tokens carry a password fingerprint, so changing the password ends every older session. *Still true:* no individual revocation, no "log out everywhere" button, integration secrets are stored unencrypted in the database |
| 17 | Low | The SSRF guard is installed through a private `httpcore` attribute; deprecated IPv6 ranges counted as public | **Fixed.** Construction fails loudly if the attribute disappears; `::/96` and `fec0::/10` are refused |
| 18 | Info | Docs exempt from CSP, no HSTS/Permissions-Policy, query strings in uvicorn's access log, unpinned CI actions | **Fixed.** Narrow CSP for the docs pages, `Strict-Transport-Security` over HTTPS, `Permissions-Policy`, COOP/CORP, `Cache-Control: no-store` on the API, uvicorn access log silenced (the app logs paths only), GitHub Actions pinned to commit SHAs, Dependabot enabled, a scheduled security workflow added. *Not done:* Docker base images pinned by digest; Python dependencies are not hash-locked |

## Dependency advisories

| Package | Advisory | Action |
|---|---|---|
| `vite` (build tool) | dev-server request issues (high) | upgraded to 6.4.x |
| `vitest` / `tinypool` (test tool) | prototype pollution to code execution (critical) | upgraded to 4.1.x |
| `react-router-dom` | open redirect via backslash, deserialisation of SSR errors | upgraded to 7.18.x (the app uses no SSR) |
| `setuptools` (build tool in the development venv) | several | upgraded; it is not a runtime dependency |

## Accepted / not reachable

- `soupsieve` 2.10, `GHSA-mmhr-3c5m-f64f`: polynomial-time CSS selectors on very deeply nested documents. It is pulled in by
  `beautifulsoup4`, which this application never calls; no fixed release exists yet. The scheduled workflow ignores this single
  advisory and should be revisited when a fix ships.
- `bandit` low-severity notes: `"bearer"` / token URL strings flagged as passwords, `xml.sax.saxutils.escape` flagged although it only
  *escapes* text, deliberate best-effort `try/except` blocks. All reviewed, none exploitable.

## Not covered

- No dynamic scanner (ZAP, Burp) and no fuzzing run.
- Browser rendering and Lighthouse were exercised functionally, not attacked end to end with a live malicious server.
- PostgreSQL-specific behaviour, and the memory/CPU cost of analysing sites of hundreds of thousands of pages.
- Docker image hardening beyond running as a non-root user, dropping capabilities and `no-new-privileges`.

## Reporting

See `SECURITY.md`.
