"""
Predictive ETA calculation for vessels on active routes.

Applies correction factors for weather (seasonal Mediterranean patterns),
zone restrictions, and vessel performance characteristics to produce a
more realistic arrival estimate than raw distance / speed.
"""

import logging
import math
from datetime import datetime
from typing import Optional

from src.core.config import settings
from src.core.routing.strategy import DEFAULT_SPEED_KNOTS, METRES_PER_NM

logger = logging.getLogger(__name__)

# Vessel-type performance multipliers.
# Values > 1.0 mean slower-than-nominal; < 1.0 mean faster.
_VESSEL_PERFORMANCE: dict[str, float] = {
    "bulk_carrier": 1.05,
    "tanker": 1.04,
    "container_ship": 1.00,
    "lng_carrier": 1.03,
    "lpg_carrier": 1.03,
    "chemical_tanker": 1.04,
    "general_cargo": 1.02,
    "passenger_ship": 0.98,
    "cruise_ship": 0.97,
    "ferry": 0.99,
    "ro_ro_ship": 1.01,
    "car_carrier": 1.02,
    "offshore_support": 1.06,
    "research_vessel": 1.03,
    "icebreaker": 1.08,
    "tugboat": 1.10,
    "fishing_vessel": 1.04,
    "yacht": 0.98,
    "patrol_boat": 0.96,
    "dredger": 1.12,
}


class ETAPredictor:
    """
    Predicts a corrected ETA for a vessel on a given route by combining
    base distance/speed calculations with real-world correction factors.
    """

    def __init__(self, ai_repo, route_repo, vessel_repo) -> None:
        self._ai_repo = ai_repo
        self._route_repo = route_repo
        self._vessel_repo = vessel_repo

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def predict_eta(self, vessel_id: str, route_id: str) -> dict:
        """
        Compute a predicted ETA for *vessel_id* on *route_id*.

        Returns a dict with ``original_eta_h``, ``predicted_eta_h``,
        ``confidence``, and the individual correction ``factors``.
        """
        vessel = self._vessel_repo.get_by_id(vessel_id)
        if vessel is None:
            return {"error": f"Vessel {vessel_id} not found."}

        route = self._route_repo.get_by_id(route_id)
        if route is None:
            return {"error": f"Route {route_id} not found."}

        # Determine effective speed.
        speed_knots = DEFAULT_SPEED_KNOTS
        if vessel.specs and vessel.specs.max_speed_knots:
            speed_knots = vessel.specs.max_speed_knots

        # Remaining distance.
        remaining_nm = self._calculate_remaining_distance(vessel, route)

        # Base (uncorrected) ETA.
        original_eta_h = remaining_nm / speed_knots if speed_knots > 0 else 0.0

        # Correction factors.
        weather_factor = self._calculate_weather_factor()
        zone_factor = self._calculate_zone_factor(route)
        vessel_factor = self._calculate_vessel_factor(vessel)

        factors = {
            "weather": round(weather_factor, 4),
            "zone": round(zone_factor, 4),
            "vessel_performance": round(vessel_factor, 4),
        }

        combined_factor = weather_factor * zone_factor * vessel_factor
        predicted_eta_h = original_eta_h * combined_factor

        confidence = self._calculate_confidence(factors)

        # Persist the prediction.
        try:
            self._ai_repo.create_eta_prediction({
                "vessel_id": vessel_id,
                "route_id": route_id,
                "original_eta_h": round(original_eta_h, 4),
                "predicted_eta_h": round(predicted_eta_h, 4),
                "confidence": round(confidence, 4),
                "factors": factors,
                "remaining_distance_nm": round(remaining_nm, 4),
                "speed_knots": round(speed_knots, 2),
            })
        except Exception:
            logger.exception("Failed to persist ETA prediction.")

        logger.info(
            "ETA prediction for vessel %s on route %s: %.2f h (original %.2f h, confidence %.2f)",
            vessel_id,
            route_id,
            predicted_eta_h,
            original_eta_h,
            confidence,
        )

        return {
            "vessel_id": vessel_id,
            "route_id": route_id,
            "original_eta_h": round(original_eta_h, 4),
            "predicted_eta_h": round(predicted_eta_h, 4),
            "confidence": round(confidence, 4),
            "factors": factors,
            "remaining_distance_nm": round(remaining_nm, 4),
            "speed_knots": round(speed_knots, 2),
        }

    # ------------------------------------------------------------------
    # Correction factors
    # ------------------------------------------------------------------

    @staticmethod
    def _calculate_weather_factor() -> float:
        """
        Seasonal Mediterranean weather factor.

        Summer (May–Sep): ``AI_WEATHER_FACTOR_SUMMER`` (calmer seas).
        Winter (Oct–Apr): ``AI_WEATHER_FACTOR_WINTER`` (rougher seas).
        """
        month = datetime.now().month
        if 5 <= month <= 9:
            return settings.AI_WEATHER_FACTOR_SUMMER
        return settings.AI_WEATHER_FACTOR_WINTER

    def _calculate_zone_factor(self, route) -> float:
        """
        Check whether any route waypoints are near active restricted zones.

        Each zone overlap adds a 10–20 % slowdown.  Returns a multiplier
        ≥ 1.0.
        """
        if not route.waypoints:
            return 1.0

        try:
            from src.infrastructure.repositories.zone_repositories import ZoneRepository
            zone_repo = ZoneRepository()
            active_zones = zone_repo.get_active()
        except Exception:
            logger.debug("Could not load zones for ETA zone-factor calculation.")
            return 1.0

        if not active_zones:
            return 1.0

        zone_hits = 0
        for wp in route.waypoints:
            if not wp.coordinates or len(wp.coordinates) < 2:
                continue
            wp_lon, wp_lat = wp.coordinates[0], wp.coordinates[1]
            for zone in active_zones:
                if zone.zone_type == "canal":
                    continue
                proximity_nm = self._haversine_distance(
                    wp_lat, wp_lon,
                    self._polygon_centroid_lat(zone.geometry),
                    self._polygon_centroid_lon(zone.geometry),
                )
                # If waypoint is within 30 NM of a restricted zone centre,
                # consider it "affected".
                if proximity_nm < 30.0:
                    zone_hits += 1
                    break  # One hit per waypoint is enough.

        if zone_hits == 0:
            return 1.0

        # Each affected waypoint adds ~3 % (capped at 20 %).
        factor = 1.0 + min(zone_hits * 0.03, 0.20)
        return factor

    @staticmethod
    def _calculate_vessel_factor(vessel) -> float:
        """
        Performance correction based on vessel type.

        Returns a multiplier where > 1.0 slows the ETA (older / heavier
        classes) and < 1.0 speeds it up (lighter / faster classes).
        """
        v_type = vessel.vessel_type or "general_cargo"
        return _VESSEL_PERFORMANCE.get(v_type, 1.0)

    # ------------------------------------------------------------------
    # Distance helpers
    # ------------------------------------------------------------------

    def _calculate_remaining_distance(self, vessel, route) -> float:
        """
        Compute the remaining route distance in nautical miles.

        If the vessel has a ``current_position``, find the nearest
        waypoint on the route and sum the leg distances from there to
        the final waypoint.  Otherwise fall back to the full route
        distance.
        """
        if not route.waypoints:
            return route.total_distance_nm or 0.0

        if not vessel.current_position:
            return route.total_distance_nm or 0.0

        vessel_coords = vessel.current_position.get("coordinates", [])
        if len(vessel_coords) < 2:
            return route.total_distance_nm or 0.0

        vessel_lon, vessel_lat = vessel_coords[0], vessel_coords[1]

        # Nearest waypoint index.
        best_idx = 0
        best_dist = float("inf")
        for i, wp in enumerate(route.waypoints):
            if not wp.coordinates or len(wp.coordinates) < 2:
                continue
            d = self._haversine_distance(
                vessel_lat, vessel_lon, wp.coordinates[1], wp.coordinates[0]
            )
            if d < best_dist:
                best_dist = d
                best_idx = i

        # Sum remaining legs.
        remaining = best_dist
        for i in range(best_idx, len(route.waypoints) - 1):
            wp_a = route.waypoints[i]
            wp_b = route.waypoints[i + 1]
            if (
                wp_a.coordinates
                and wp_b.coordinates
                and len(wp_a.coordinates) >= 2
                and len(wp_b.coordinates) >= 2
            ):
                remaining += self._haversine_distance(
                    wp_a.coordinates[1],
                    wp_a.coordinates[0],
                    wp_b.coordinates[1],
                    wp_b.coordinates[0],
                )

        return remaining

    # ------------------------------------------------------------------
    # Confidence
    # ------------------------------------------------------------------

    @staticmethod
    def _calculate_confidence(factors: dict) -> float:
        """
        Produce a confidence score (0.0–1.0) based on how many factors
        deviate from 1.0.

        Starts at 0.95; each factor that is not exactly 1.0 reduces
        confidence by 0.10 (floored at 0.30).
        """
        confidence = 0.95
        for value in factors.values():
            if abs(value - 1.0) > 0.001:
                confidence -= 0.10
        return max(round(confidence, 4), 0.30)

    # ------------------------------------------------------------------
    # Geometry utilities
    # ------------------------------------------------------------------

    @staticmethod
    def _haversine_distance(
        lat1: float, lon1: float, lat2: float, lon2: float
    ) -> float:
        """Great-circle distance in nautical miles."""
        R_NM = 3440.065
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        d_phi = math.radians(lat2 - lat1)
        d_lambda = math.radians(lon2 - lon1)

        a = (
            math.sin(d_phi / 2) ** 2
            + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
        )
        return R_NM * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    @staticmethod
    def _polygon_centroid_lat(geometry: dict) -> float:
        """Return the average latitude of a GeoJSON Polygon's outer ring."""
        try:
            coords = geometry.get("coordinates", [[]])[0]
            if not coords:
                return 0.0
            return sum(c[1] for c in coords) / len(coords)
        except (AttributeError, IndexError, TypeError):
            return 0.0

    @staticmethod
    def _polygon_centroid_lon(geometry: dict) -> float:
        """Return the average longitude of a GeoJSON Polygon's outer ring."""
        try:
            coords = geometry.get("coordinates", [[]])[0]
            if not coords:
                return 0.0
            return sum(c[0] for c in coords) / len(coords)
        except (AttributeError, IndexError, TypeError):
            return 0.0
