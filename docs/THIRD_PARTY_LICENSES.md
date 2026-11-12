# Third-Party Licences

The project's own code is MIT-licensed and original. It depends on the open-source packages below. Licence identifiers are as declared
by each package at the time of writing; check the installed distributions (`pip-licenses`, `npx license-checker`) before redistributing
a bundle, and keep each package's licence/NOTICE file where its licence requires it (Apache-2.0).

## Backend (Python)

| Package | Licence | Use |
|---|---|---|
| FastAPI | MIT | Web framework |
| Starlette | BSD-3-Clause | ASGI toolkit (via FastAPI) |
| Pydantic, pydantic-settings | MIT | Validation and settings |
| uvicorn | BSD-3-Clause | ASGI server |
| SQLAlchemy | MIT | ORM |
| Alembic | MIT | Migrations |
| httpx, httpcore | BSD-3-Clause | HTTP client |
| anyio | MIT | Async networking backend |
| lxml | BSD-3-Clause | HTML/XML parsing |
| trafilatura (with courlan, htmldate, justext, lxml_html_clean) | Apache-2.0 / BSD | Main-content extraction |
| tldextract | BSD-3-Clause | Registrable-domain detection (bundled public-suffix snapshot, MPL-2.0 data) |
| argon2-cffi | MIT | Password hashing |
| PyJWT | MIT | Token signing |
| python-multipart | Apache-2.0 | File uploads |
| email-validator | Unlicense / CC0 | Email validation |
| openpyxl | MIT | Excel export |
| reportlab | BSD-3-Clause | PDF export |
| Playwright (optional) | Apache-2.0 | JavaScript rendering |
| psycopg (optional) | LGPL-3.0 | PostgreSQL driver, dynamically linked optional dependency |
| pytest, pytest-asyncio, ruff (development) | MIT / Apache-2.0 | Testing and linting |

## Frontend (JavaScript)

| Package | Licence | Use |
|---|---|---|
| React, React DOM | MIT | UI |
| React Router | MIT | Routing |
| TanStack Query | MIT | Data fetching |
| Recharts | MIT | Charts |
| lucide-react | ISC | Icons |
| clsx | MIT | Class names |
| Vite, @vitejs/plugin-react | MIT | Build |
| Tailwind CSS, PostCSS, Autoprefixer | MIT | Styling |
| TypeScript | Apache-2.0 | Type checking (development) |
| Vitest, Testing Library, jsdom (development) | MIT | Tests |

## External services (not distributed with this project)

| Service | Relationship |
|---|---|
| SearXNG (AGPL-3.0) | Optional, user-operated; contacted over HTTP only. No SearXNG code is included or linked. |
| Ollama (MIT) | Optional, user-operated; contacted over HTTP only. |
| Google PageSpeed Insights, Search Console, Programmable Search; Brave Search | Optional APIs used under the user's own account and those services' terms. |

## Projects studied for ideas

Listed with licences in `../RESEARCH/GITHUB_REPOSITORY_ANALYSIS.md`. No source code was copied from any of them; GPL/AGPL and unlicensed
projects were used as conceptual references only.
