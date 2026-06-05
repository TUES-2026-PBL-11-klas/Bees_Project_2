"""
Route analytics service (GitHub issue #81).

Aggregates RouteHistory records into per-vessel / per-strategy summaries:
average fuel consumption, distance, duration, deviation from estimate,
and strategy-vs-strategy effectiveness comparisons.

The service is intentionally Mongo-agnostic at the boundary — it takes a
list[RouteHistory] (or anything with the same attribute surface) so it
can be exercised in tests with plain stub objects.
"""

from __future__ import annotations

from dataclasses import dataclass
from statistics import mean, pstdev
from typing import Iterable, Optional

from src.infrastructure.repositories.route_history_repository import (
    RouteHistoryRepository,
)


@dataclass(frozen=True)
class Aggregate:
    sample_size: int
    avg_distance_nm: Optional[float]
    avg_duration_h: Optional[float]
    avg_fuel_tons: Optional[float]
    stdev_fuel_tons: Optional[float]

    def as_dict(self) -> dict:
        return {
            "sample_size": self.sample_size,
            "avg_distance_nm": self.avg_distance_nm,
            "avg_duration_h": self.avg_duration_h,
            "avg_fuel_tons": self.avg_fuel_tons,
            "stdev_fuel_tons": self.stdev_fuel_tons,
        }


def _avg(values: list[float]) -> Optional[float]:
    return round(mean(values), 4) if values else None


def _stdev(values: list[float]) -> Optional[float]:
    return round(pstdev(values), 4) if len(values) >= 2 else None


def _collect(entries: Iterable, field: str) -> list[float]:
    return [
        float(getattr(e, field))
        for e in entries
        if getattr(e, field, None) is not None
    ]


def aggregate(entries: Iterable) -> Aggregate:
    """Aggregate a flat iterable of RouteHistory records into one summary."""
    entries = list(entries)
    fuel = _collect(entries, "estimated_fuel_tons")
    return Aggregate(
        sample_size=len(entries),
        avg_distance_nm=_avg(_collect(entries, "total_distance_nm")),
        avg_duration_h=_avg(_collect(entries, "estimated_duration_h")),
        avg_fuel_tons=_avg(fuel),
        stdev_fuel_tons=_stdev(fuel),
    )


class AnalyticsService:
    """High-level operations exposed by /api/v1/analytics endpoints."""

    def __init__(
        self,
        history_repo: Optional[RouteHistoryRepository] = None,
    ) -> None:
        self._history = history_repo or RouteHistoryRepository()

    # ── Per-vessel summary ───────────────────────────────────────────
    def vessel_summary(self, vessel_id: str, limit: int = 200) -> dict:
        entries = self._history.get_by_vessel(vessel_id, limit=limit)
        return {
            "vessel_id": vessel_id,
            "overall": aggregate(entries).as_dict(),
            "by_strategy": {
                mode: aggregate(
                    [e for e in entries if e.optimization_mode == mode]
                ).as_dict()
                for mode in ("fastest", "eco")
            },
        }

    # ── Per-company summary ──────────────────────────────────────────
    def company_summary(self, company_id: str, limit: int = 500) -> dict:
        entries = self._history.get_by_company(company_id, limit=limit)
        return {
            "company_id": company_id,
            "overall": aggregate(entries).as_dict(),
            "by_strategy": {
                mode: aggregate(
                    [e for e in entries if e.optimization_mode == mode]
                ).as_dict()
                for mode in ("fastest", "eco")
            },
        }

    # ── Strategy effectiveness ───────────────────────────────────────
    def strategy_effectiveness(self, limit: int = 1000) -> dict:
        """
        Compare 'fastest' vs 'eco' aggregates over recent history.

        We report eco-vs-fastest deltas so callers can answer "is eco
        actually saving fuel in practice?" without doing math themselves.
        """
        entries = self._history.get_recent(limit=limit)
        fastest = aggregate([e for e in entries if e.optimization_mode == "fastest"])
        eco = aggregate([e for e in entries if e.optimization_mode == "eco"])

        def _delta(a: Optional[float], b: Optional[float]) -> Optional[float]:
            if a is None or b is None or b == 0:
                return None
            return round((a - b) / b * 100, 2)

        return {
            "sample_size": len(entries),
            "fastest": fastest.as_dict(),
            "eco": eco.as_dict(),
            "eco_vs_fastest_pct": {
                "distance": _delta(eco.avg_distance_nm, fastest.avg_distance_nm),
                "duration": _delta(eco.avg_duration_h, fastest.avg_duration_h),
                "fuel":     _delta(eco.avg_fuel_tons,  fastest.avg_fuel_tons),
            },
        }
