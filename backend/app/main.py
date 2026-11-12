"""FastAPI application factory."""
from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .api import auth, crawls, integrations, sites, tools
from .config import APP_NAME, APP_VERSION, get_settings
from .jobs import jobs, mark_interrupted_jobs
from .security.ratelimit import RateLimitMiddleware

log = logging.getLogger("seo.app")
BACKEND_DIR = Path(__file__).resolve().parent.parent


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {"ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"), "level": record.levelname, "logger": record.name,
                   "message": record.getMessage()}
        for key in ("request_id", "method", "path", "status", "duration_ms"):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging() -> None:
    s = get_settings()
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter() if s.log_json else logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s"))
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(s.log_level.upper())
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def run_migrations() -> None:
    """Bring the database schema up to date (Alembic ``upgrade head``)."""
    from alembic.config import Config

    from alembic import command

    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    cfg.attributes["configure_logger"] = False
    command.upgrade(cfg, "head")


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    run_migrations()
    mark_interrupted_jobs()
    scheduler = None
    if get_settings().scheduler_enabled:
        from .services.monitoring import scheduler_loop
        scheduler = asyncio.create_task(scheduler_loop(), name="scheduler")
    log.info("%s %s started", APP_NAME, APP_VERSION)
    yield
    if scheduler:
        scheduler.cancel()
    await jobs.shutdown()


def create_app() -> FastAPI:
    s = get_settings()
    app = FastAPI(title=APP_NAME, version=APP_VERSION, lifespan=lifespan, docs_url="/api/docs", redoc_url="/api/redoc",
                  openapi_url="/api/openapi.json",
                  description="Self-hosted, open-source SEO platform: crawler, technical audit, keyword research, SERP and "
                              "content analysis, Search Console, page speed, monitoring and reporting.")
    app.add_middleware(RateLimitMiddleware)
    origins = [o.strip() for o in s.cors_origins.split(",") if o.strip()]
    if origins:
        app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["*"], allow_headers=["Authorization", "Content-Type"],
                           expose_headers=["Content-Disposition"])

    @app.middleware("http")
    async def access_log(request: Request, call_next):
        rid = uuid.uuid4().hex[:12]
        started = time.monotonic()
        try:
            response = await call_next(request)
        except Exception:  # noqa: BLE001 - last line of defence: log with a reference id, never leak internals
            log.exception("unhandled error", extra={"request_id": rid, "method": request.method, "path": request.url.path})
            return JSONResponse({"detail": "Internal server error", "reference": rid}, status_code=500)
        if request.url.path.startswith("/api/"):
            log.info("%s %s -> %s", request.method, request.url.path, response.status_code,
                     extra={"request_id": rid, "method": request.method, "path": request.url.path, "status": response.status_code,
                            "duration_ms": int((time.monotonic() - started) * 1000)})
        response.headers["X-Request-ID"] = rid
        return response

    for r in (auth.router, sites.router, crawls.router, tools.router, integrations.router):
        app.include_router(r, prefix="/api")

    @app.get("/api/health", tags=["system"])
    def health() -> dict:
        return {"status": "ok", "version": APP_VERSION}

    @app.get("/api/rules", tags=["system"])
    def rules() -> list[dict]:
        from .audit.rules import RULES, rule_dict
        return [rule_dict(r) for r in RULES]

    dist = (BACKEND_DIR / s.frontend_dist).resolve()
    if (dist / "index.html").exists():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        def spa(path: str):
            if path.startswith("api/"):
                return JSONResponse({"detail": "Not found"}, status_code=404)
            candidate = (dist / path).resolve()
            if path and candidate.is_file() and dist in candidate.parents:
                return FileResponse(candidate)
            return FileResponse(dist / "index.html")

    return app


app = create_app()
