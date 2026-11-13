"""Background job runner.

Jobs are asyncio tasks inside the API process with their state persisted in the ``jobs`` table. This
keeps the default installation free of Redis/Celery (which is not supported on Windows) while still
running long crawls off the request path. See ARCHITECTURE_DECISIONS.md (ADR-003).
"""
from __future__ import annotations

import asyncio
import logging
import time
import traceback
from collections.abc import Awaitable, Callable

from .config import get_settings
from .db import session_scope
from .models import Job, utcnow

log = logging.getLogger("seo.jobs")


class JobLimitError(RuntimeError):
    """The account already has the maximum number of queued or running background jobs."""


class JobContext:
    def __init__(self, job_id: int) -> None:
        self.job_id = job_id
        self._last_write = 0.0

    def update(self, progress: float | None = None, message: str | None = None, force: bool = False) -> None:
        now = time.monotonic()
        if not force and now - self._last_write < 1.0:
            return
        self._last_write = now
        with session_scope() as db:
            job = db.get(Job, self.job_id)
            if job is None:
                return
            if progress is not None:
                job.progress = round(max(0.0, min(1.0, progress)), 4)
            if message is not None:
                job.message = message[:500]


JobFunc = Callable[[JobContext], Awaitable[dict | None]]


class JobManager:
    def __init__(self) -> None:
        self._tasks: dict[int, asyncio.Task] = {}
        self._owners: dict[int, int | None] = {}
        self._sem: asyncio.Semaphore | None = None

    def _semaphore(self) -> asyncio.Semaphore:
        if self._sem is None:
            self._sem = asyncio.Semaphore(get_settings().max_concurrent_jobs)
        return self._sem

    def start(self, kind: str, func: JobFunc, owner_id: int | None = None, site_id: int | None = None) -> int:
        """Create a job row and schedule ``func``. Must be called from the event loop thread."""
        if owner_id is not None:
            limit = get_settings().max_jobs_per_user
            active = sum(1 for jid, owner in self._owners.items() if owner == owner_id and jid in self._tasks)
            if active >= limit:
                raise JobLimitError(f"You already have {active} background jobs queued or running (limit {limit}). "
                                    "Wait for some to finish or cancel them first.")
        with session_scope() as db:
            job = Job(kind=kind, owner_id=owner_id, site_id=site_id, status="queued", message="Waiting for a free worker")
            db.add(job)
            db.flush()
            job_id = job.id
        task = asyncio.get_running_loop().create_task(self._run(job_id, func), name=f"job-{job_id}")
        self._tasks[job_id] = task
        self._owners[job_id] = owner_id
        task.add_done_callback(lambda _t, j=job_id: (self._tasks.pop(j, None), self._owners.pop(j, None)))
        return job_id

    async def _run(self, job_id: int, func: JobFunc) -> None:
        ctx = JobContext(job_id)
        status, error, result = "completed", None, {}
        try:
            async with self._semaphore():
                self._set(job_id, status="running", message="Starting")
                result = await func(ctx) or {}
        except asyncio.CancelledError:
            status = "cancelled"
        except Exception as exc:  # noqa: BLE001 - job failures are recorded, never crash the server
            status, error = "failed", f"{type(exc).__name__}: {exc}"
            log.error("job %s failed: %s\n%s", job_id, error, traceback.format_exc())
        fields = {"status": status, "error": error, "result": result, "finished_at": utcnow()}
        if status == "completed":
            fields["progress"] = 1.0
        self._set(job_id, **fields)

    @staticmethod
    def _set(job_id: int, **fields) -> None:
        with session_scope() as db:
            job = db.get(Job, job_id)
            if job:
                for k, v in fields.items():
                    setattr(job, k, v)

    def cancel(self, job_id: int) -> bool:
        task = self._tasks.get(job_id)
        if task and not task.done():
            task.cancel()
            return True
        return False

    def is_active(self, job_id: int) -> bool:
        t = self._tasks.get(job_id)
        return bool(t and not t.done())

    async def shutdown(self) -> None:
        for t in list(self._tasks.values()):
            t.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks.values(), return_exceptions=True)


jobs = JobManager()


def mark_interrupted_jobs() -> None:
    """On startup, anything still marked queued/running belonged to a previous process."""
    from .models import Crawl  # local import to avoid a cycle

    with session_scope() as db:
        for job in db.query(Job).filter(Job.status.in_(("queued", "running"))):
            job.status, job.error, job.finished_at = "failed", "Interrupted by a server restart", utcnow()
        for crawl in db.query(Crawl).filter(Crawl.status.in_(("queued", "running"))):
            crawl.status, crawl.error, crawl.finished_at = "failed", "Interrupted by a server restart", utcnow()
