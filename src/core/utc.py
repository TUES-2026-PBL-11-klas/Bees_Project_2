"""
Drop-in replacement for ``datetime.utcnow()``.

``datetime.utcnow()`` is deprecated in Python 3.12+ and slated for
removal in a future version. The recommended replacement,
``datetime.now(timezone.utc)``, returns an *aware* datetime — which is
not a drop-in substitute in this codebase because every Mongo-engine
``DateTimeField`` returns *naive* UTC, and aware ↔ naive subtraction
raises ``TypeError``.

``utc_now()`` returns a naive UTC datetime computed via the non-deprecated
``datetime.now(timezone.utc)`` API, preserving the original semantics
while silencing the deprecation warning.
"""

from __future__ import annotations

from datetime import datetime, timezone


def utc_now() -> datetime:
    """Current UTC time as a naive datetime (drop-in for ``datetime.utcnow()``)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)
