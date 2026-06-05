"""
TaskQueue abstraction with an in-process thread-pool implementation.

Job functions are registered by name, then callers enqueue work by
referencing that name plus a payload. The worker pool runs jobs
asynchronously and stores results / errors on the Job record so the
admin UI can inspect status.
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Job:
    id: str
    name: str
    payload: dict
    status: JobStatus = JobStatus.PENDING
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    finished_at: Optional[float] = None
    result: Any = None
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "payload": self.payload,
            "status": self.status.value,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "result": self.result,
            "error": self.error,
        }


class JobNotRegisteredError(KeyError):
    """Raised when a caller enqueues a job name that hasn't been registered."""


class TaskQueue:
    """Abstract queue interface — production can swap for RQ / Celery."""

    def register(self, name: str, fn: Callable[..., Any]) -> None:
        raise NotImplementedError

    def enqueue(self, name: str, **payload: Any) -> Job:
        raise NotImplementedError

    def get(self, job_id: str) -> Optional[Job]:
        raise NotImplementedError

    def list(self, limit: int = 100) -> list[Job]:
        raise NotImplementedError


class InProcessTaskQueue(TaskQueue):
    """
    Thread-pool backed implementation.

    * Workers are daemon threads — they don't block process shutdown.
    * Jobs are stored in-memory; restarts lose history. That matches the
      "stub" intent — production should run RQ + Redis.
    * ``wait_for(job_id, timeout)`` is provided for tests so they can
      block on completion.
    """

    def __init__(self, *, max_workers: int = 4, history_size: int = 500) -> None:
        self._jobs: dict[str, Job] = {}
        self._handlers: dict[str, Callable[..., Any]] = {}
        self._futures: dict[str, Future] = {}
        self._lock = threading.Lock()
        self._history_size = history_size
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers, thread_name_prefix="task-queue"
        )

    def register(self, name: str, fn: Callable[..., Any]) -> None:
        with self._lock:
            self._handlers[name] = fn

    def is_registered(self, name: str) -> bool:
        with self._lock:
            return name in self._handlers

    def enqueue(self, name: str, **payload: Any) -> Job:
        with self._lock:
            if name not in self._handlers:
                raise JobNotRegisteredError(name)
            fn = self._handlers[name]
            job = Job(id=uuid.uuid4().hex, name=name, payload=dict(payload))
            self._jobs[job.id] = job
            self._evict_if_full()

        future = self._executor.submit(self._run_job, job.id, fn, payload)
        with self._lock:
            self._futures[job.id] = future
        return job

    def get(self, job_id: str) -> Optional[Job]:
        with self._lock:
            return self._jobs.get(job_id)

    def list(self, limit: int = 100) -> list[Job]:
        with self._lock:
            jobs = list(self._jobs.values())
        jobs.sort(key=lambda j: j.created_at, reverse=True)
        return jobs[:limit]

    def wait_for(self, job_id: str, timeout: float = 5.0) -> Optional[Job]:
        """Block until the job finishes (or timeout). Test-only convenience."""
        with self._lock:
            future = self._futures.get(job_id)
        if future is None:
            return self.get(job_id)
        try:
            future.result(timeout=timeout)
        except Exception:
            # Exceptions are already captured on the Job record.
            pass
        return self.get(job_id)

    def shutdown(self, wait: bool = True) -> None:
        self._executor.shutdown(wait=wait)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _run_job(self, job_id: str, fn: Callable[..., Any], payload: dict) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return
            job.status = JobStatus.RUNNING
            job.started_at = time.time()

        try:
            result = fn(**payload)
            with self._lock:
                job.result = result
                job.status = JobStatus.COMPLETED
        except Exception as exc:
            logger.exception("Job %s (%s) failed", job_id, job.name)
            with self._lock:
                job.error = f"{type(exc).__name__}: {exc}"
                job.status = JobStatus.FAILED
        finally:
            with self._lock:
                job.finished_at = time.time()
                # Now that a job has reached a terminal state, drop the
                # oldest finished entries until we're under the cap.
                self._evict_if_full()

    def _evict_if_full(self) -> None:
        if len(self._jobs) <= self._history_size:
            return
        # Drop oldest finished jobs first.
        finished = sorted(
            (j for j in self._jobs.values()
             if j.status in (JobStatus.COMPLETED, JobStatus.FAILED)),
            key=lambda j: j.finished_at or 0,
        )
        for job in finished:
            del self._jobs[job.id]
            self._futures.pop(job.id, None)
            if len(self._jobs) <= self._history_size:
                return


# ---------------------------------------------------------------------------
# Default queue + job registration
# ---------------------------------------------------------------------------


_default_queue: Optional[InProcessTaskQueue] = None
_default_lock = threading.Lock()


def get_default_queue() -> InProcessTaskQueue:
    """Return the module-level default queue, lazily creating it."""
    global _default_queue
    with _default_lock:
        if _default_queue is None:
            _default_queue = InProcessTaskQueue()
            register_default_jobs(_default_queue)
        return _default_queue


def register_default_jobs(queue: TaskQueue) -> None:
    """Wire the application's known jobs onto *queue*."""
    # Local imports keep this module importable even when other code
    # paths haven't fully bootstrapped (e.g. tests).
    from src.infrastructure.queue.jobs import (
        run_grib_ingestion,
        run_analytics_rollup,
        run_ai_reroute,
        run_weather_refresh,
    )

    queue.register("grib_ingest", run_grib_ingestion)
    queue.register("analytics_rollup", run_analytics_rollup)
    queue.register("ai_reroute", run_ai_reroute)
    queue.register("weather_refresh", run_weather_refresh)
