"""Unit tests for the in-process TaskQueue (#85)."""

from __future__ import annotations

import threading
import time

import pytest

from src.infrastructure.queue import (
    InProcessTaskQueue,
    JobNotRegisteredError,
    JobStatus,
)


def test_enqueue_runs_registered_handler_with_payload():
    queue = InProcessTaskQueue(max_workers=2)
    queue.register("double", lambda x: x * 2)

    job = queue.enqueue("double", x=21)
    finished = queue.wait_for(job.id, timeout=2.0)

    assert finished is not None
    assert finished.status == JobStatus.COMPLETED
    assert finished.result == 42
    assert finished.error is None
    queue.shutdown()


def test_enqueue_unknown_job_raises():
    queue = InProcessTaskQueue()
    with pytest.raises(JobNotRegisteredError):
        queue.enqueue("never_registered")
    queue.shutdown()


def test_failed_job_records_error():
    queue = InProcessTaskQueue()

    def boom() -> None:
        raise RuntimeError("kaboom")

    queue.register("boom", boom)
    job = queue.enqueue("boom")
    finished = queue.wait_for(job.id, timeout=2.0)

    assert finished.status == JobStatus.FAILED
    assert "kaboom" in (finished.error or "")
    assert finished.started_at is not None and finished.finished_at is not None
    queue.shutdown()


def test_list_returns_jobs_in_recent_first_order():
    queue = InProcessTaskQueue(max_workers=1)
    queue.register("noop", lambda: None)

    ids = []
    for _ in range(3):
        ids.append(queue.enqueue("noop").id)
        time.sleep(0.01)
    for jid in ids:
        queue.wait_for(jid, timeout=2.0)

    listed = queue.list()
    listed_ids = [j.id for j in listed]
    assert listed_ids == list(reversed(ids))
    queue.shutdown()


def test_history_eviction_keeps_only_history_size_entries():
    queue = InProcessTaskQueue(max_workers=1, history_size=3)
    queue.register("noop", lambda: None)

    submitted = [queue.enqueue("noop").id for _ in range(10)]
    for jid in submitted:
        queue.wait_for(jid, timeout=2.0)

    assert len(queue.list()) == 3
    queue.shutdown()


def test_concurrent_enqueue_is_thread_safe():
    queue = InProcessTaskQueue(max_workers=4)
    queue.register("noop", lambda: None)

    job_ids: list[str] = []
    lock = threading.Lock()

    def submitter() -> None:
        for _ in range(20):
            jid = queue.enqueue("noop").id
            with lock:
                job_ids.append(jid)

    threads = [threading.Thread(target=submitter) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(job_ids) == 80
    assert len(set(job_ids)) == 80  # ids are unique
    for jid in job_ids:
        queue.wait_for(jid, timeout=2.0)
    queue.shutdown()
