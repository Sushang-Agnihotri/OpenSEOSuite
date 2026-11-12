# API Guide

The complete, always-current reference is generated from the code:

- Swagger UI: `http://localhost:8000/api/docs`
- ReDoc: `http://localhost:8000/api/redoc`
- OpenAPI schema: `http://localhost:8000/api/openapi.json`

All endpoints live under `/api`, accept and return JSON (exports return files) and, except for the few listed as public, require
`Authorization: Bearer <token>`.

## Authentication

| Method | Path | Notes |
|---|---|---|
| GET | `/auth/status` | Public. Whether any account exists and whether registration is open |
| POST | `/auth/register` | `{email, password}`; the first account becomes administrator |
| POST | `/auth/login` | `{email, password}` → `{access_token, user}` |
| GET | `/auth/me` | Current user |
| POST | `/auth/password` | Change password |

## Endpoint groups

| Area | Endpoints (prefix `/api`) |
|---|---|
| Sites | `GET/POST /sites`, `GET/PATCH/DELETE /sites/{id}`, `GET /sites/{id}/overview`, `GET /dashboard` |
| Crawls | `POST/GET /sites/{id}/crawls`, `GET/DELETE /crawls/{id}`, `POST /crawls/{id}/cancel`, `GET /crawls/{a}/compare/{b}` |
| Crawl data | `GET /crawls/{id}/pages` (search, filters, sort, pagination), `/pages/{page_id}`, `/links`, `/redirects`, `/duplicates` |
| Audit | `GET /crawls/{id}/issues`, `/issues/{rule_id}`, `GET /rules` (public rule catalogue) |
| Architecture | `GET /crawls/{id}/internal-links`, `/link-opportunities`, `/graph` |
| Sitemaps / schema / i18n / local | `GET /crawls/{id}/sitemaps`, `/sitemap.xml`, `/schema`, `/hreflang`, `/local`; `POST /sites/{id}/citations/import` |
| Exports | `GET /crawls/{id}/export?dataset=pages|issues|links|broken_links|redirects|all&format=csv|xlsx|json`, `GET /crawls/{id}/report.pdf` |
| Keywords | `POST /keywords/suggest`, `/keywords/cluster`, `/keywords/intent`; `GET/POST/DELETE /sites/{id}/keywords`, `/keywords/import`, `/keywords/mapping`, `/keywords/export` |
| SERP | `GET /serp/providers`, `POST /serp/analyze` |
| Content | `POST /content/analyze`, `POST /content/fetch` |
| Schema tools | `GET /schema/types`, `POST /schema/validate`, `POST /schema/generate` |
| Page speed | `GET /pagespeed/status`, `POST /pagespeed/run`, `GET /pagespeed/history`, `GET /pagespeed/{id}` |
| Competitors | `GET/POST /sites/{id}/competitors`, `DELETE .../{cid}`, `POST .../{cid}/crawl`, `GET .../report.pdf` |
| Backlinks | `GET /sites/{id}/backlinks`, `/backlinks/summary`, `POST /backlinks/import`, `/backlinks/verify`, `GET /backlinks/export`, `DELETE /backlinks` |
| Search Console | `GET /gsc/status`, `/gsc/auth-url`, `/gsc/properties`, `POST /gsc/disconnect`; `POST /sites/{id}/gsc/sync`, `/gsc/import`, `GET /gsc/performance`, `/gsc/insights`, `DELETE /gsc/data` |
| Monitoring | `GET /monitoring/kinds`, `GET/POST /sites/{id}/monitors`, `PATCH/DELETE /monitors/{id}`, `POST /monitors/{id}/run`, `GET /alerts`, `POST /alerts/read`, `GET /alerts/export` |
| Jobs | `GET /jobs`, `GET /jobs/{id}`, `POST /jobs/{id}/cancel` |
| Settings (admin) | `GET/PUT /settings` |
| AI (optional) | `GET /ai/status`, `POST /ai/run` |
| System | `GET /health` (public) |

Long-running operations (crawls, backlink verification, Search Console sync, monitor runs) return `202` with a `job_id`; poll
`GET /jobs/{id}` until `status` is `completed`, `failed` or `cancelled`.

## Example: audit a site from a script

```bash
BASE=http://localhost:8000/api
TOKEN=$(curl -s $BASE/auth/login -H 'Content-Type: application/json' \
  -d '{"email":"you@example.com","password":"your password"}' | python -c "import sys,json;print(json.load(sys.stdin)['access_token'])")
AUTH="Authorization: Bearer $TOKEN"

# create the site and start a crawl
SITE=$(curl -s $BASE/sites -H "$AUTH" -H 'Content-Type: application/json' -d '{"name":"Example","url":"https://example.com"}' \
  | python -c "import sys,json;print(json.load(sys.stdin)['id'])")
CRAWL=$(curl -s $BASE/sites/$SITE/crawls -H "$AUTH" -H 'Content-Type: application/json' -d '{"max_urls":200}')
CRAWL_ID=$(echo $CRAWL | python -c "import sys,json;print(json.load(sys.stdin)['id'])")
JOB_ID=$(echo $CRAWL | python -c "import sys,json;print(json.load(sys.stdin)['job_id'])")

# wait for it
until curl -s $BASE/jobs/$JOB_ID -H "$AUTH" | grep -Eq '"status":"(completed|failed|cancelled)"'; do sleep 3; done

# results
curl -s $BASE/crawls/$CRAWL_ID/issues -H "$AUTH"
curl -s -o audit.pdf  "$BASE/crawls/$CRAWL_ID/report.pdf" -H "$AUTH"
curl -s -o crawl.xlsx "$BASE/crawls/$CRAWL_ID/export?dataset=all&format=xlsx" -H "$AUTH"
```

## Conventions

- Pagination: `page` (1-based) and `per_page` (max 500); responses contain `total`, `page`, `per_page`, `items`.
- Errors: `{"detail": "message"}` (or FastAPI's validation array for 422). Objects owned by another user return 404.
- Rate limits: 600 requests/minute per IP by default (10/minute for login and registration); exceeding them returns 429.
- Provenance: responses that include estimates carry a `method`, `basis`, `note` or `status` field saying so.
