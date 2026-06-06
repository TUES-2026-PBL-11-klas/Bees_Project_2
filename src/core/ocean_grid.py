"""
Ocean waypoint grid generator for global maritime routing.

Produces a coarse grid of open-sea waypoints at a configurable degree
interval.  Points that fall on major landmasses are excluded using fast
bounding-box checks.  The resulting grid, combined with port-to-grid
edges, guarantees that A* can find a path between any two ports on Earth.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

from src.core.graph import Waypoint

# Land bounding boxes (conservative rectangles covering major landmasses)
# Format: (min_lat, max_lat, min_lon, max_lon)
# A grid point inside ANY of these boxes is considered "land" and skipped.

_LAND_BOXES: list[tuple[float, float, float, float]] = [
    # Africa
    (-35, 37, -18, 52),

    # Europe (mainland)
    (36, 71, -10, 40),

    # Asia (mainland bulk)
    (10, 75, 40, 140),

    # Indian subcontinent
    (8, 35, 68, 90),

    # Southeast Asian peninsula
    (1, 24, 92, 110),

    # China coast / Korea / Japan
    (22, 55, 100, 145),

    # North America
    (15, 72, -170, -50),

    # Central America
    (7, 20, -92, -77),

    # South America
    (-56, 13, -82, -34),

    # Australia
    (-44, -10, 112, 154),

    # New Zealand
    (-47, -34, 166, 179),

    # Greenland
    (59, 84, -74, -10),

    # Antarctica
    (-90, -60, -180, 180),

    # Madagascar
    (-26, -12, 43, 50),

    # Borneo
    (-4, 7, 108, 119),

    # Sumatra
    (-6, 6, 95, 106),

    # Java
    (-9, -6, 105, 115),

    # Papua New Guinea
    (-10, -1, 140, 155),

    # Philippines (Mindanao/Luzon core)
    (5, 19, 117, 127),

    # Iceland
    (63, 67, -25, -13),

    # Sri Lanka
    (6, 10, 79, 82),

    # Taiwan
    (22, 26, 120, 122),

    # Cuba
    (19, 24, -85, -74),

    # Hispaniola
    (17, 20, -75, -68),

    # Great Britain
    (50, 59, -6, 2),

    # Ireland
    (51, 56, -11, -6),
]

# Coastal water corridors that should NOT be blocked even though they
# fall inside a coarse land bounding box.  These are critical chokepoints
# and straits where we want grid nodes.
# Format: (lat, lon) tuples — if a grid point is within 2° of any of
# these, it is forced to be "ocean" regardless of bounding-box checks.
_WATER_OVERRIDES: list[tuple[float, float]] = [
    # Mediterranean
    (35.0, -5.0),   # Strait of Gibraltar
    (37.0, 15.0),   # Strait of Messina
    (35.5, 24.0),   # South Crete
    (40.5, 27.0),   # Dardanelles approach
    (31.0, 32.5),   # Suez approach
    (41.0, 29.0),   # Bosphorus

    # Red Sea / Gulf
    (12.5, 43.5),   # Bab el-Mandeb
    (27.0, 56.0),   # Strait of Hormuz
    (30.0, 48.0),   # Persian Gulf

    # Southeast Asia
    (1.3, 104.0),   # Singapore Strait
    (-6.0, 106.0),  # Sunda Strait
    (-8.5, 116.0),  # Lombok Strait
    (5.0, 100.0),   # Malacca Strait north

    # East Asia
    (34.0, 130.0),  # Korea Strait
    (25.0, 120.0),  # Taiwan Strait
    (22.0, 114.0),  # South China Sea / HK approach

    # Americas
    (9.0, -79.5),   # Panama Canal approach
    (48.5, -65.0),  # St Lawrence
    (30.0, -88.0),  # Gulf of Mexico

    # English Channel / North Sea
    (51.0, 1.5),    # Strait of Dover
    (50.0, -1.5),   # English Channel

    # Scandinavia straits
    (56.0, 11.0),   # Kattegat / Skagerrak
    (55.5, 13.0),   # Øresund

    # Black Sea (enclosed within Europe bbox — force grid nodes)
    (43.0, 35.0),   # Central Black Sea
    (43.0, 30.0),   # Western Black Sea
    (42.0, 37.0),   # Eastern Black Sea
    (44.0, 33.0),   # Northern Black Sea
    (41.5, 28.0),   # Sea of Marmara approach

    # Baltic Sea (enclosed within Europe bbox)
    (57.0, 19.0),   # Central Baltic
    (59.0, 21.0),   # Gulf of Finland approach
    (64.0, 21.0),   # Gulf of Bothnia
    (55.0, 15.0),   # Southern Baltic
    (58.0, 10.0),   # Skagerrak

    # Caspian Sea
    (42.0, 51.0),   # Caspian
    (39.0, 51.0),   # South Caspian

    # Sea of Japan / East Sea
    (40.0, 135.0),  # Sea of Japan
    (37.0, 132.0),  # Korea Strait approach

    # Yellow Sea / East China Sea
    (33.0, 125.0),  # East China Sea
    (36.0, 123.0),  # Yellow Sea

    # South China Sea
    (15.0, 115.0),  # Central SCS
    (10.0, 112.0),  # Southern SCS
    (8.0, 108.0),   # Gulf of Thailand approach

    # Bay of Bengal
    (15.0, 85.0),   # Central Bay of Bengal
    (10.0, 80.0),   # Sri Lanka approach

    # Arabian Sea
    (15.0, 65.0),   # Central Arabian Sea
    (20.0, 60.0),   # Gulf of Oman approach
    (25.0, 55.0),   # Persian Gulf mouth

    # Cape of Good Hope
    (-35.0, 20.0),  # Cape approach
    (-34.0, 26.0),  # South Africa east coast

    # Japan straits
    (41.0, 140.0),  # Tsugaru Strait
    (34.0, 133.0),  # Inland Sea

    # Torres Strait
    (-10.0, 142.0),

    # Mozambique Channel
    (-15.0, 42.0),
    (-20.0, 36.0),

    # Caribbean
    (18.0, -67.0),  # Mona Passage
    (22.0, -80.0),  # Florida Straits
]


def is_ocean(lat: float, lon: float) -> bool:
    """Fast check: return True if (lat, lon) is likely open ocean."""
    for wlat, wlon in _WATER_OVERRIDES:
        if abs(lat - wlat) <= 2.0 and abs(lon - wlon) <= 2.0:
            return True

    for min_lat, max_lat, min_lon, max_lon in _LAND_BOXES:
        if min_lat <= lat <= max_lat and min_lon <= lon <= max_lon:
            return False

    return True


def generate_ocean_grid(step_deg: float = 5.0) -> list[Waypoint]:
    """
    Generate a global grid of ocean waypoints at *step_deg* intervals.

    Points that fall on major landmasses (detected via bounding-box
    checks) are excluded.  Returns ~2,000–3,000 Waypoint objects
    depending on the step size.
    """
    grid_nodes: list[Waypoint] = []

    lat = -75.0
    while lat <= 75.0:
        lon = -180.0
        while lon < 180.0:
            if is_ocean(lat, lon):
                node_id = f"OG_{lat:+06.0f}_{lon:+07.0f}".replace(
                    "+", "P"
                ).replace("-", "N").replace(".", "")
                grid_nodes.append(
                    Waypoint(
                        node_id=node_id,
                        latitude=lat,
                        longitude=lon,
                        name=f"Ocean grid {lat:.0f}°, {lon:.0f}°",
                    )
                )
            lon += step_deg
        lat += step_deg

    return grid_nodes


def _haversine_fast(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Approximate great-circle distance in metres (for sorting only)."""
    R = 6_371_000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def find_nearest_grid_nodes(
    lat: float,
    lon: float,
    grid_nodes: list[Waypoint],
    k: int = 3,
    max_distance_m: float = 2_000_000.0,
) -> list[Waypoint]:
    """
    Return the *k* nearest grid nodes to a given (lat, lon), within
    *max_distance_m* metres.
    """
    scored = []
    for node in grid_nodes:
        d = _haversine_fast(lat, lon, node.latitude, node.longitude)
        if d <= max_distance_m:
            scored.append((d, node))
    scored.sort(key=lambda x: x[0])
    return [node for _, node in scored[:k]]


def get_adjacent_grid_ids(
    node: Waypoint,
    grid_index: dict[str, Waypoint],
    step_deg: float = 5.0,
) -> list[Waypoint]:
    """
    Return the directly adjacent (N/S/E/W + diagonals) grid neighbours
    of a grid node.
    """
    lat = node.latitude
    lon = node.longitude
    neighbours: list[Waypoint] = []

    for dlat in (-step_deg, 0.0, step_deg):
        for dlon in (-step_deg, 0.0, step_deg):
            if dlat == 0.0 and dlon == 0.0:
                continue
            n_lat = lat + dlat
            n_lon = lon + dlon
            # Wrap longitude
            if n_lon >= 180.0:
                n_lon -= 360.0
            elif n_lon < -180.0:
                n_lon += 360.0

            nid = f"OG_{n_lat:+06.0f}_{n_lon:+07.0f}".replace(
                "+", "P"
            ).replace("-", "N").replace(".", "")

            if nid in grid_index:
                neighbours.append(grid_index[nid])

    return neighbours
