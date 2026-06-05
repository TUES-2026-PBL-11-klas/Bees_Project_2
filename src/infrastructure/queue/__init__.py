"""
Background task queue (issue #85).

* TaskQueue — abstract queue interface.
* InProcessTaskQueue — thread-pool backed implementation suitable for
  single-process deployments and tests.
* Job, JobStatus — value objects describing scheduled work.

Production deployments can swap InProcessTaskQueue for an RQ / Celery
implementation that conforms to the same TaskQueue interface; the
public API (enqueue / get / list / register) and the job functions
themselves do not change.
"""

from src.infrastructure.queue.task_queue import (
    InProcessTaskQueue,
    Job,
    JobNotRegisteredError,
    JobStatus,
    TaskQueue,
    get_default_queue,
    register_default_jobs,
)

__all__ = [
    "InProcessTaskQueue",
    "Job",
    "JobNotRegisteredError",
    "JobStatus",
    "TaskQueue",
    "get_default_queue",
    "register_default_jobs",
]
