"""
Multi-leg voyage planner.

A real-world voyage is rarely a single point-to-point hop — operators
load cargo at port A, top up bunkers at B, discharge at C, then pick
up the return cargo at D. This service:

* Calculates each leg using the existing routing strategies
* Aggregates total distance, duration, and fuel across legs
* Optionally re-orders the *intermediate* ports (the first and last
  port are always honoured) to minimise total fuel — useful when the
  operator is willing to swap discharge order to save bunker spend

The order optimisation is bounded: for ≤ 7 intermediate ports we try
every permutation (≤ 5040 candidate orderings, evaluated using the
already-cached graph), and for larger sets we fall back to a 2-opt
heuristic seeded with the input order.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from itertools import permutations
from typing import Callable, Optional

from src.core.graph import NavigationGraph, Waypoint
from src.core.routing.strategy import (
    DEFAULT_SPEED_KNOTS,
    METRES_PER_NM,
    RoutingStrategy,
    VesselConstraints,
)

logger = logging.getLogger(__name__)


PathFn = Callable[[str, str], Optional[list[Waypoint]]]


@dataclass(frozen=True)
class Leg:
    from_port: str
    to_port: str
    distance_nm: float
    duration_h: float
    fuel_tons: float
    waypoints: list[Waypoint] = field(default_factory=list)

    def to_dict(self, include_waypoints: bool = True) -> dict:
        out = {
            "from_port":      self.from_port,
            "to_port":        self.to_port,
            "distance_nm":    round(self.distance_nm, 2),
            "duration_h":     round(self.duration_h, 2),
            "fuel_tons":      round(self.fuel_tons, 3),
        }
        if include_waypoints:
            out["waypoints"] = [
                {"sequence": i, "coordinates": [wp.longitude, wp.latitude]}
                for i, wp in enumerate(self.waypoints)
            ]
        return out


@dataclass(frozen=True)
class VoyagePlan:
    order: list[str]
    legs: list[Leg]
    total_distance_nm: float
    total_duration_h: float
    total_fuel_tons: float
    reordered: bool
    legs_failed: int

    def to_dict(self, include_waypoints: bool = True) -> dict:
        return {
            "port_order":           list(self.order),
            "total_distance_nm":    round(self.total_distance_nm, 2),
            "total_duration_h":     round(self.total_duration_h, 2),
            "total_fuel_tons":      round(self.total_fuel_tons, 3),
            "reordered":            self.reordered,
            "legs_failed":          self.legs_failed,
            "legs":                 [leg.to_dict(include_waypoints) for leg in self.legs],
        }


# ---------------------------------------------------------------------------
# Distance / fuel helpers — small, deterministic, no DB.
# ---------------------------------------------------------------------------


def _path_distance_metres(path: list[Waypoint]) -> float:
    """Haversine distance through a waypoint sequence."""
    if len(path) < 2:
        return 0.0
    total = 0.0
    prev = path[0]
    for wp in path[1:]:
        total += _haversine_m(prev, wp)
        prev = wp
    return total


def _haversine_m(a: Waypoint, b: Waypoint) -> float:
    import math
    R = 6_371_000.0
    lat1 = math.radians(a.latitude)
    lat2 = math.radians(b.latitude)
    dlat = math.radians(b.latitude - a.latitude)
    dlon = math.radians(b.longitude - a.longitude)
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * R * math.asin(math.sqrt(h))


def _leg_fuel_tons(distance_nm: float, vessel: Optional[VesselConstraints]) -> float:
    """Distance × fuel rate × type multiplier, in tonnes."""
    rate = 0.05  # safe default tonnes / nm if nothing else known
    multiplier = 1.0
    if vessel is not None:
        if vessel.fuel_consumption_rate:
            rate = float(vessel.fuel_consumption_rate)
        if vessel.fuel_multiplier:
            multiplier = float(vessel.fuel_multiplier)
        if vessel.hydro_resistance_coef:
            multiplier *= float(vessel.hydro_resistance_coef)
    return distance_nm * rate * multiplier


def _leg_duration_h(distance_nm: float, vessel: Optional[VesselConstraints]) -> float:
    speed = (
        vessel.max_speed_knots
        if vessel and vessel.max_speed_knots
        else DEFAULT_SPEED_KNOTS
    )
    return distance_nm / speed if speed > 0 else 0.0


# ---------------------------------------------------------------------------
# Public planner
# ---------------------------------------------------------------------------


class MultiLegPlanner:
    """Plan a voyage that touches an ordered list of ports."""

    MAX_PERMUTATION_INTERMEDIATES = 7

    def __init__(self, graph: NavigationGraph, strategy: RoutingStrategy) -> None:
        self.graph = graph
        self.strategy = strategy

    # ----- core building block: compute a single leg -----

    def _compute_leg(
        self,
        from_id: str,
        to_id: str,
        vessel: Optional[VesselConstraints],
    ) -> Optional[Leg]:
        try:
            path = self.strategy.calculate_route(self.graph, from_id, to_id, vessel=vessel)
        except KeyError:
            return None
        if not path:
            return None
        distance_nm = _path_distance_metres(path) / METRES_PER_NM
        return Leg(
            from_port=from_id,
            to_port=to_id,
            distance_nm=distance_nm,
            duration_h=_leg_duration_h(distance_nm, vessel),
            fuel_tons=_leg_fuel_tons(distance_nm, vessel),
            waypoints=path,
        )

    # ----- plan the voyage in the input order -----

    def plan(
        self,
        port_ids: list[str],
        vessel: Optional[VesselConstraints] = None,
    ) -> VoyagePlan:
        if len(port_ids) < 2:
            raise ValueError("multi-leg voyage requires at least 2 ports")

        legs: list[Leg] = []
        failed = 0
        for a, b in zip(port_ids[:-1], port_ids[1:]):
            leg = self._compute_leg(a, b, vessel)
            if leg is None:
                failed += 1
                continue
            legs.append(leg)

        total_dist = sum(l.distance_nm for l in legs)
        total_dur = sum(l.duration_h for l in legs)
        total_fuel = sum(l.fuel_tons for l in legs)

        return VoyagePlan(
            order=list(port_ids),
            legs=legs,
            total_distance_nm=total_dist,
            total_duration_h=total_dur,
            total_fuel_tons=total_fuel,
            reordered=False,
            legs_failed=failed,
        )

    # ----- plan with order optimisation -----

    def plan_optimised(
        self,
        port_ids: list[str],
        vessel: Optional[VesselConstraints] = None,
        objective: str = "fuel",
    ) -> VoyagePlan:
        """
        Try to find a port ordering that minimises ``objective`` (``"fuel"``
        or ``"distance"``).  The first and last ports are held fixed.
        """
        if len(port_ids) < 3:
            # Nothing to reorder.
            return self.plan(port_ids, vessel)

        start, *middle, end = port_ids

        # Pre-compute pairwise legs over the unique set of nodes so we
        # only invoke the underlying routing strategy once per (a, b).
        unique = {start, end, *middle}
        cache: dict[tuple[str, str], Optional[Leg]] = {}
        for a in unique:
            for b in unique:
                if a == b:
                    continue
                cache[(a, b)] = self._compute_leg(a, b, vessel)

        def score(order: list[str]) -> Optional[float]:
            total = 0.0
            for x, y in zip(order[:-1], order[1:]):
                leg = cache.get((x, y))
                if leg is None:
                    return None
                total += leg.fuel_tons if objective == "fuel" else leg.distance_nm
            return total

        baseline_order = [start, *middle, end]
        best_order = baseline_order
        best_score = score(baseline_order)

        if len(middle) <= self.MAX_PERMUTATION_INTERMEDIATES:
            # Exhaustive search of intermediate permutations.
            for perm in permutations(middle):
                candidate = [start, *perm, end]
                s = score(candidate)
                if s is None:
                    continue
                if best_score is None or s < best_score:
                    best_score = s
                    best_order = candidate
        else:
            # 2-opt heuristic seeded with the input order.
            current = baseline_order[:]
            improved = True
            while improved:
                improved = False
                for i in range(1, len(current) - 2):
                    for j in range(i + 1, len(current) - 1):
                        candidate = current[:i] + current[i:j + 1][::-1] + current[j + 1:]
                        s = score(candidate)
                        if s is not None and (best_score is None or s < best_score):
                            best_score = s
                            best_order = candidate
                            current = candidate
                            improved = True

        plan = self.plan(best_order, vessel)
        return VoyagePlan(
            order=plan.order,
            legs=plan.legs,
            total_distance_nm=plan.total_distance_nm,
            total_duration_h=plan.total_duration_h,
            total_fuel_tons=plan.total_fuel_tons,
            reordered=best_order != baseline_order,
            legs_failed=plan.legs_failed,
        )
