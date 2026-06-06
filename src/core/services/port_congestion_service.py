"""
Port congestion forecasting.

Predicts berth availability at a port over a future horizon by combining
two signals:

1. **Confirmed bookings.**  Existing ``DockReservation`` documents whose
   ``[start_at, end_at)`` window overlaps the target hour count as
   guaranteed-occupied berths.
2. **Historical baseline.**  An average occupancy curve computed from
   past reservations keyed by ``(day_of_week, hour_of_day)`` gives a
   prior for how busy this port tends to be at that time, so an hour
   with zero confirmed bookings but a historically saturated profile is
   correctly flagged as congested.

The two signals are blended (``α × confirmed + (1 - α) × historical``)
into a single occupancy probability per hour in ``[0, 1]``; multiplying
by ``berth_count`` gives expected occupied berths and the per-hour
``available_berths`` projection.

Latencies are dominated by Mongo IO, so the service reads every
relevant reservation in *one* round-trip rather than per bucket.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from src.core.utc import utc_now
from src.models.port_scheduling import DockReservation, Port

logger = logging.getLogger(__name__)


DEFAULT_HORIZON_HOURS = 24
DEFAULT_BUCKET_MINUTES = 60
DEFAULT_CONFIRMED_WEIGHT = 0.7
DEFAULT_HISTORY_LOOKBACK_DAYS = 90


@dataclass(frozen=True)
class CongestionBucket:
    start_at: datetime
    end_at: datetime
    confirmed_occupied: int
    historical_occupancy: float          # in [0, 1]
    projected_occupancy: float           # in [0, 1]
    available_berths_estimate: float     # ≥ 0
    congestion_score: float              # in [0, 1], higher = worse

    def to_dict(self) -> dict:
        return {
            "start_at":                   self.start_at.isoformat(),
            "end_at":                     self.end_at.isoformat(),
            "confirmed_occupied_berths":  self.confirmed_occupied,
            "historical_occupancy":       round(self.historical_occupancy, 3),
            "projected_occupancy":        round(self.projected_occupancy, 3),
            "available_berths_estimate":  round(self.available_berths_estimate, 2),
            "congestion_score":           round(self.congestion_score, 3),
        }


@dataclass(frozen=True)
class CongestionForecast:
    port_id: str
    berth_count: int
    horizon_hours: int
    bucket_minutes: int
    confirmed_weight: float
    generated_at: datetime
    buckets: list[CongestionBucket]
    peak_score: float
    average_score: float

    def to_dict(self) -> dict:
        return {
            "port_id":           self.port_id,
            "berth_count":       self.berth_count,
            "horizon_hours":     self.horizon_hours,
            "bucket_minutes":    self.bucket_minutes,
            "confirmed_weight":  self.confirmed_weight,
            "generated_at":      self.generated_at.isoformat(),
            "peak_congestion_score":     round(self.peak_score, 3),
            "average_congestion_score":  round(self.average_score, 3),
            "buckets":           [b.to_dict() for b in self.buckets],
        }


class PortCongestionService:
    """Forecast berth availability per hour over a configurable horizon."""

    def __init__(
        self,
        *,
        history_lookback_days: int = DEFAULT_HISTORY_LOOKBACK_DAYS,
        confirmed_weight: float = DEFAULT_CONFIRMED_WEIGHT,
    ) -> None:
        if not 0.0 <= confirmed_weight <= 1.0:
            raise ValueError("confirmed_weight must be in [0, 1]")
        self.history_lookback_days = history_lookback_days
        self.confirmed_weight = confirmed_weight

    # ------------------------------------------------------------------

    def forecast(
        self,
        port_id: str,
        *,
        start_at: Optional[datetime] = None,
        horizon_hours: int = DEFAULT_HORIZON_HOURS,
        bucket_minutes: int = DEFAULT_BUCKET_MINUTES,
    ) -> CongestionForecast:
        if horizon_hours <= 0 or bucket_minutes <= 0:
            raise ValueError("horizon_hours and bucket_minutes must be positive")
        if bucket_minutes > horizon_hours * 60:
            raise ValueError("bucket_minutes cannot exceed horizon")

        port = Port.objects(port_id=port_id).first()
        if port is None:
            raise LookupError(f"Port '{port_id}' not found")

        start = (start_at or utc_now()).replace(microsecond=0)
        end = start + timedelta(hours=horizon_hours)
        berth_count = int(port.berth_count or 1)

        confirmed = self._confirmed_reservations(port_id, start, end)
        historical = self._historical_occupancy(port_id, berth_count, start, end)

        buckets: list[CongestionBucket] = []
        cursor = start
        delta = timedelta(minutes=bucket_minutes)
        while cursor < end:
            bucket_end = cursor + delta
            occupied = self._count_active(confirmed, cursor, bucket_end)
            confirmed_ratio = min(1.0, occupied / berth_count) if berth_count else 0.0
            hist_ratio = historical.get(self._historical_key(cursor), 0.0)

            projected = (
                self.confirmed_weight * confirmed_ratio
                + (1.0 - self.confirmed_weight) * hist_ratio
            )
            projected = max(0.0, min(1.0, projected))
            available = max(0.0, berth_count * (1.0 - projected))

            buckets.append(CongestionBucket(
                start_at=cursor,
                end_at=bucket_end,
                confirmed_occupied=occupied,
                historical_occupancy=hist_ratio,
                projected_occupancy=projected,
                available_berths_estimate=available,
                congestion_score=projected,
            ))
            cursor = bucket_end

        peak = max((b.congestion_score for b in buckets), default=0.0)
        avg = sum(b.congestion_score for b in buckets) / len(buckets) if buckets else 0.0

        return CongestionForecast(
            port_id=port_id,
            berth_count=berth_count,
            horizon_hours=horizon_hours,
            bucket_minutes=bucket_minutes,
            confirmed_weight=self.confirmed_weight,
            generated_at=utc_now(),
            buckets=buckets,
            peak_score=peak,
            average_score=avg,
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _confirmed_reservations(
        self,
        port_id: str,
        start: datetime,
        end: datetime,
    ) -> list[DockReservation]:
        """Single query: reservations whose [start_at, end_at) intersects [start, end)."""
        return list(
            DockReservation.objects(
                port_id=port_id,
                status__in=["scheduled", "active"],
                start_at__lt=end,
                end_at__gt=start,
            )
        )

    @staticmethod
    def _count_active(
        reservations: list[DockReservation],
        bucket_start: datetime,
        bucket_end: datetime,
    ) -> int:
        """How many reservations overlap [bucket_start, bucket_end)."""
        return sum(
            1
            for r in reservations
            if r.start_at < bucket_end and r.end_at > bucket_start
        )

    def _historical_occupancy(
        self,
        port_id: str,
        berth_count: int,
        start: datetime,
        end: datetime,
    ) -> dict[tuple[int, int], float]:
        """
        Build a {(weekday, hour): mean_occupancy_ratio} map from past
        reservations in the configured lookback window. Each past
        reservation contributes ``1 / berth_count`` to every hour it
        covered, normalised by the number of historical days seen.
        """
        lookback_start = start - timedelta(days=self.history_lookback_days)
        past = list(
            DockReservation.objects(
                port_id=port_id,
                start_at__lt=start,
                end_at__gt=lookback_start,
                status__in=["scheduled", "active", "completed"],
            )
        )

        if not past or berth_count <= 0:
            return {}

        per_hour_sum: dict[tuple[int, int], float] = defaultdict(float)
        seen_days: set[tuple[int, int, int, int, int]] = set()

        for r in past:
            # Walk every hour the reservation covered (within the lookback
            # window) and accumulate 1 / berth_count.
            cursor = max(r.start_at, lookback_start).replace(minute=0, second=0, microsecond=0)
            stop = min(r.end_at, start)
            while cursor < stop:
                key = self._historical_key(cursor)
                per_hour_sum[key] += 1.0 / berth_count
                seen_days.add((cursor.year, cursor.month, cursor.day, key[0], key[1]))
                cursor += timedelta(hours=1)

        # Average each (weekday, hour) by the number of distinct historical
        # days it appeared in. This compensates for varying lookback length
        # across hours.
        per_hour_days: dict[tuple[int, int], int] = defaultdict(int)
        for (_y, _m, _d, weekday, hour) in seen_days:
            per_hour_days[(weekday, hour)] += 1

        averaged: dict[tuple[int, int], float] = {}
        for key, total in per_hour_sum.items():
            denominator = per_hour_days.get(key, 1)
            averaged[key] = min(1.0, total / denominator)
        return averaged

    @staticmethod
    def _historical_key(dt: datetime) -> tuple[int, int]:
        return dt.weekday(), dt.hour
