"""
Build a NavigationGraph from the world port catalogue + ocean grid.

The graph is built once and cached as a module-level singleton so that
all API endpoints share the same instance.  Construction takes < 1 s.

Architecture
------------
1. All world ports are added as graph nodes.
2. An ocean waypoint grid (5° spacing, land-excluded) is generated.
3. Each port is auto-connected to its 3 nearest grid nodes.
4. Each grid node is connected to its 8 adjacent neighbours.
5. Hand-crafted corridors for straits/canals with draft restrictions
   are layered on top.

This guarantees that A* can find a path between *any* two ports.
"""

from __future__ import annotations

import logging
import time
from threading import Lock
from typing import Optional

from src.core.graph import NavigationGraph, Waypoint
from src.core.ocean_grid import (
    generate_ocean_grid,
    find_nearest_grid_nodes,
    get_adjacent_grid_ids,
)

logger = logging.getLogger(__name__)

_graph: Optional[NavigationGraph] = None
_graph_lock = Lock()


def _load_ports() -> list[dict]:
    """Load the world-ports list, falling back to the legacy inline list."""
    try:
        from src.core.world_ports import WORLD_PORTS
        return WORLD_PORTS
    except ImportError:
        logger.warning("world_ports.py not found — falling back to legacy ports.py")
        from src.core.ports import _RAW_PORTS
        return _RAW_PORTS


# These override the auto-generated grid edges with explicit draft /
# length / beam restrictions where they matter.
#
# Format: (src_id, dst_id, max_draft_m [, max_length_m [, max_beam_m]])
#
_RESTRICTED_CORRIDORS: list[tuple] = [
    # Bosphorus / Dardanelles
    ("VARNA", "ISTANBUL", 15.0),
    ("CONSTANTA", "ISTANBUL", 15.0),
    ("BURGAS", "ISTANBUL", 15.0),
    ("ISTANBUL", "CANAKKALE", 15.0),

    # Suez Canal
    ("PORT_SAID", "SUEZ", 20.1, 400.0, 77.5),

    # Strait of Messina
    ("WP_EAST_SICILY", "WP_STRAIT_MESSINA", 8.0),
    ("WP_STRAIT_MESSINA", "GIOIA_TAURO", 8.0),

    # Strait of Bonifacio
    ("WP_BONIFACIO", "WP_SARDINIA_EAST", 11.0),
    ("WP_BONIFACIO", "WP_WEST_CORSICA", 11.0),
]

# Connections between nearby ports that should have a direct edge
# rather than going through the ocean grid, for route quality.
_DIRECT_CORRIDORS: list[tuple[str, str]] = [
    # Black Sea
    ("VARNA", "CONSTANTA"),
    ("VARNA", "BURGAS"),
    ("CONSTANTA", "ODESSA"),
    ("NOVOROSSIYSK", "BATUMI"),
    ("SEVASTOPOL", "NOVOROSSIYSK"),
    ("SEVASTOPOL", "ODESSA"),
    ("CONSTANTA", "SEVASTOPOL"),
    ("VARNA", "SEVASTOPOL"),
    # Direct deep-water hop so Burgas → Sevastopol doesn't have to detour
    # through Varna (the old graph forced this and the Burgas→Varna leg
    # clipped the Bulgarian coast).
    ("BURGAS", "SEVASTOPOL"),

    # Aegean
    ("CANAKKALE", "THESSALONIKI"),
    ("CANAKKALE", "IZMIR"),
    ("THESSALONIKI", "PIRAEUS"),
    ("PIRAEUS", "HERAKLION"),
    ("IZMIR", "PIRAEUS"),

    # Eastern Med
    ("HERAKLION", "LIMASSOL"),
    ("ANTALYA", "MERSIN"),
    ("MERSIN", "ISKENDERUN"),
    ("MERSIN", "LIMASSOL"),
    ("LIMASSOL", "BEIRUT"),
    ("LIMASSOL", "HAIFA"),
    ("BEIRUT", "HAIFA"),
    ("HAIFA", "PORT_SAID"),
    ("LIMASSOL", "PORT_SAID"),
    ("PORT_SAID", "ALEXANDRIA"),

    # Red Sea
    ("SUEZ", "JEDDAH"),

    # North Africa
    ("ALEXANDRIA", "BENGHAZI"),
    ("BENGHAZI", "TRIPOLI_LY"),
    ("TRIPOLI_LY", "TUNIS"),
    ("TUNIS", "ALGIERS"),
    ("ALGIERS", "ORAN"),
    ("ORAN", "TANGIER"),
    ("TANGIER", "CASABLANCA"),

    # Adriatic
    ("TARANTO", "BARI"),
    ("BARI", "ANCONA"),
    ("ANCONA", "VENICE"),
    ("VENICE", "TRIESTE"),
    ("TRIESTE", "KOPER"),
    ("KOPER", "RIJEKA"),
    ("BAR", "DUBROVNIK"),
    ("DUBROVNIK", "SPLIT"),
    ("SPLIT", "RIJEKA"),

    # Tyrrhenian / Ligurian
    ("NAPLES", "SALERNO"),
    ("GIOIA_TAURO", "NAPLES"),
    ("CATANIA", "PALERMO"),
    ("PALERMO", "NAPLES"),
    ("NAPLES", "CIVITAVECCHIA"),
    ("CIVITAVECCHIA", "LIVORNO"),
    ("LIVORNO", "GENOA"),

    # West Med
    ("GENOA", "MARSEILLE"),
    ("MARSEILLE", "SETE"),
    ("SETE", "BARCELONA"),
    ("BARCELONA", "VALENCIA"),
    ("VALENCIA", "CARTAGENA"),
    ("CARTAGENA", "MALAGA"),
    ("MALAGA", "ALGECIRAS"),
    ("ALGECIRAS", "GIBRALTAR"),
    ("GIBRALTAR", "TANGIER"),
    ("CADIZ", "ALGECIRAS"),

    # Atlantic / Iberian
    ("CADIZ", "CASABLANCA"),
    ("CADIZ", "LISBON"),
    ("LISBON", "SINES"),

    # English Channel / North Sea
    ("LE_HAVRE", "SOUTHAMPTON"),
    ("SOUTHAMPTON", "FELIXSTOWE"),
    ("FELIXSTOWE", "ROTTERDAM"),
    ("ROTTERDAM", "ANTWERP"),
    ("ROTTERDAM", "HAMBURG"),
    ("ROTTERDAM", "BREMERHAVEN"),
    ("HAMBURG", "BREMERHAVEN"),

    # Sardinia / Malta
    ("CAGLIARI", "PALERMO"),
    ("MALTA", "CATANIA"),
    ("MALTA", "TUNIS"),
]

# Existing legacy open-sea waypoints that should be preserved for
# backward-compatible corridor routing.
_LEGACY_WAYPOINTS: list[dict] = [
    dict(port_id="WP_SOUTH_PELOPONNESE", lat=36.38, lon=22.50, name="South Peloponnese (open sea)"),
    dict(port_id="WP_SOUTH_CRETE", lat=34.80, lon=24.50, name="South of Crete (open sea)"),
    dict(port_id="WP_STRAIT_OTRANTO", lat=39.80, lon=19.00, name="Strait of Otranto (open sea)"),
    dict(port_id="WP_IONIAN_SEA", lat=37.50, lon=18.50, name="Ionian Sea (open sea)"),
    dict(port_id="WP_SOUTH_SICILY", lat=36.50, lon=14.50, name="South of Sicily (open sea)"),
    dict(port_id="WP_STRAIT_MESSINA", lat=38.20, lon=15.60, name="Strait of Messina (open sea)"),
    dict(port_id="WP_EAST_SICILY", lat=37.10, lon=15.35, name="East of Sicily (open sea)"),
    dict(port_id="WP_TYRRHENIAN_SOUTH", lat=40.00, lon=13.00, name="South Tyrrhenian (open sea)"),
    dict(port_id="WP_TYRRHENIAN_NORTH", lat=42.00, lon=10.50, name="North Tyrrhenian (open sea)"),
    dict(port_id="WP_LIGURIAN_SEA", lat=43.30, lon=9.00, name="Ligurian Sea (open sea)"),
    dict(port_id="WP_WEST_CORSICA", lat=42.00, lon=8.00, name="West of Corsica (open sea)"),
    dict(port_id="WP_BONIFACIO", lat=41.00, lon=9.00, name="Strait of Bonifacio (open sea)"),
    dict(port_id="WP_WEST_SARDINIA", lat=40.00, lon=7.50, name="West of Sardinia (open sea)"),
    dict(port_id="WP_SOUTH_SARDINIA", lat=38.50, lon=9.00, name="South of Sardinia (open sea)"),
    dict(port_id="WP_SARDINIA_EAST", lat=39.50, lon=10.50, name="East of Sardinia (open sea)"),
    dict(port_id="WP_BALEARIC_SEA", lat=39.50, lon=4.00, name="Balearic Sea (open sea)"),
    dict(port_id="WP_SPAIN_EAST", lat=39.00, lon=0.50, name="East of Spain (open sea)"),
    dict(port_id="WP_ALBORAN_SEA", lat=36.00, lon=-3.00, name="Alboran Sea (open sea)"),
    dict(port_id="WP_NORTH_AFRICA_MID", lat=34.50, lon=12.00, name="Central Mediterranean (open sea)"),
    dict(port_id="WP_BAY_BISCAY", lat=45.00, lon=-5.00, name="Bay of Biscay (open sea)"),
    dict(port_id="WP_CANTABRIAN_SEA", lat=44.00, lon=-3.50, name="Cantabrian Sea (open sea)"),
    dict(port_id="WP_ENGLISH_CHANNEL", lat=50.00, lon=-1.50, name="English Channel (open sea)"),
    dict(port_id="WP_STRAIT_DOVER", lat=51.10, lon=1.50, name="Strait of Dover (open sea)"),
    dict(port_id="WP_NORTH_SEA", lat=52.50, lon=3.00, name="North Sea (open sea)"),
    dict(port_id="WP_CAPE_ST_VINCENT", lat=36.80, lon=-9.20, name="Cape St Vincent (open sea)"),
    dict(port_id="WP_PORTUGAL_COAST", lat=39.50, lon=-10.00, name="Portugal Coast (open sea)"),
    dict(port_id="WP_CAPE_FINISTERRE", lat=43.00, lon=-9.50, name="Cape Finisterre (open sea)"),
    dict(port_id="WP_NORTH_CORUNA", lat=44.00, lon=-8.50, name="North Coruna (open sea)"),
    dict(port_id="WP_USHANT", lat=48.60, lon=-5.50, name="Ushant (open sea)"),
    dict(port_id="WP_GULF_OF_LION", lat=42.50, lon=4.50, name="Gulf of Lion (open sea)"),
    dict(port_id="WP_CAP_DE_CREUS", lat=42.30, lon=3.50, name="Cap de Creus (open sea)"),
    dict(port_id="WP_ALGERIAN_COAST", lat=37.00, lon=1.00, name="Algerian Coast (open sea)"),
    dict(port_id="WP_CAPE_BOUGAROUN", lat=37.50, lon=6.50, name="Cape Bougaroun (open sea)"),
    dict(port_id="WP_CAPE_BON", lat=37.20, lon=11.20, name="Cape Bon (open sea)"),
    dict(port_id="WP_MOROCCO_COAST", lat=34.00, lon=-8.00, name="Morocco Coast (open sea)"),
    dict(port_id="WP_ADRIATIC_MID", lat=43.00, lon=15.00, name="Mid Adriatic (open sea)"),
    dict(port_id="WP_ADRIATIC_NORTH", lat=44.50, lon=13.00, name="North Adriatic (open sea)"),
    dict(port_id="WP_EAST_MED", lat=33.50, lon=30.00, name="Eastern Mediterranean (open sea)"),
    dict(port_id="WP_NORTH_AEGEAN", lat=39.50, lon=24.50, name="North Aegean (open sea)"),
    dict(port_id="WP_CENTRAL_AEGEAN", lat=37.50, lon=25.00, name="Central Aegean (open sea)"),
    dict(port_id="WP_CAPE_MALEAS", lat=36.20, lon=23.40, name="Cape Maleas (open sea)"),
    # All deep-water, well clear of any coastline so port-to-port edges
    # routed via them never clip land.
    dict(port_id="WP_BLACK_SEA_WEST", lat=43.50, lon=30.50, name="Western Black Sea (open sea)"),
    dict(port_id="WP_BLACK_SEA_NW",   lat=44.60, lon=31.20, name="NW Black Sea (open sea)"),
    dict(port_id="WP_BLACK_SEA_CENTRAL", lat=43.00, lon=34.00, name="Central Black Sea (open sea)"),
    dict(port_id="WP_BLACK_SEA_EAST", lat=43.20, lon=38.50, name="Eastern Black Sea (open sea)"),
]

# Legacy corridor edges between legacy WP_ nodes and nearby ports.
_LEGACY_WP_CORRIDORS: list[tuple[str, str]] = [
    ("CANAKKALE", "WP_NORTH_AEGEAN"),
    ("WP_NORTH_AEGEAN", "THESSALONIKI"),
    ("WP_NORTH_AEGEAN", "WP_CENTRAL_AEGEAN"),
    ("WP_CENTRAL_AEGEAN", "PIRAEUS"),
    ("WP_CENTRAL_AEGEAN", "HERAKLION"),
    ("IZMIR", "WP_CENTRAL_AEGEAN"),
    ("PIRAEUS", "WP_CAPE_MALEAS"),
    ("WP_CAPE_MALEAS", "WP_SOUTH_PELOPONNESE"),
    ("WP_CAPE_MALEAS", "HERAKLION"),
    ("PATRAS", "WP_SOUTH_PELOPONNESE"),
    ("HERAKLION", "WP_SOUTH_PELOPONNESE"),
    ("WP_SOUTH_PELOPONNESE", "WP_SOUTH_CRETE"),
    ("WP_SOUTH_CRETE", "HERAKLION"),
    ("WP_SOUTH_CRETE", "PORT_SAID"),
    ("WP_SOUTH_CRETE", "WP_EAST_MED"),
    ("WP_EAST_MED", "ANTALYA"),
    ("WP_EAST_MED", "PORT_SAID"),
    ("WP_EAST_MED", "ALEXANDRIA"),
    ("WP_EAST_MED", "LIMASSOL"),
    ("IZMIR", "WP_EAST_MED"),
    ("ALEXANDRIA", "WP_SOUTH_CRETE"),
    ("BENGHAZI", "WP_SOUTH_CRETE"),
    ("BENGHAZI", "WP_NORTH_AFRICA_MID"),
    ("TRIPOLI_LY", "WP_NORTH_AFRICA_MID"),
    ("WP_SOUTH_PELOPONNESE", "WP_IONIAN_SEA"),
    ("WP_SOUTH_PELOPONNESE", "WP_STRAIT_OTRANTO"),
    ("WP_IONIAN_SEA", "WP_STRAIT_OTRANTO"),
    ("WP_IONIAN_SEA", "WP_SOUTH_SICILY"),
    ("WP_IONIAN_SEA", "WP_EAST_SICILY"),
    ("WP_IONIAN_SEA", "MALTA"),
    ("WP_SOUTH_SICILY", "MALTA"),
    ("WP_SOUTH_SICILY", "WP_EAST_SICILY"),
    ("WP_EAST_SICILY", "CATANIA"),
    ("WP_NORTH_AFRICA_MID", "MALTA"),
    ("WP_NORTH_AFRICA_MID", "WP_SOUTH_SICILY"),
    ("WP_STRAIT_OTRANTO", "TARANTO"),
    ("WP_STRAIT_OTRANTO", "BARI"),
    ("WP_STRAIT_OTRANTO", "BAR"),
    ("WP_STRAIT_OTRANTO", "DUBROVNIK"),
    ("BARI", "WP_ADRIATIC_MID"),
    ("WP_ADRIATIC_MID", "ANCONA"),
    ("ANCONA", "WP_ADRIATIC_NORTH"),
    ("WP_ADRIATIC_NORTH", "VENICE"),
    ("WP_ADRIATIC_NORTH", "TRIESTE"),
    ("WP_ADRIATIC_NORTH", "KOPER"),
    ("WP_ADRIATIC_NORTH", "RIJEKA"),
    ("SPLIT", "WP_ADRIATIC_MID"),
    ("CATANIA", "WP_SOUTH_SICILY"),
    ("NAPLES", "WP_TYRRHENIAN_SOUTH"),
    ("SALERNO", "WP_TYRRHENIAN_SOUTH"),
    ("GIOIA_TAURO", "WP_TYRRHENIAN_SOUTH"),
    ("PALERMO", "WP_TYRRHENIAN_SOUTH"),
    ("PALERMO", "WP_CAPE_BON"),
    ("MALTA", "WP_CAPE_BON"),
    ("WP_CAPE_BON", "TUNIS"),
    ("TUNIS", "WP_CAPE_BOUGAROUN"),
    ("WP_CAPE_BOUGAROUN", "ALGIERS"),
    ("WP_TYRRHENIAN_SOUTH", "WP_TYRRHENIAN_NORTH"),
    ("WP_TYRRHENIAN_NORTH", "CIVITAVECCHIA"),
    ("WP_TYRRHENIAN_NORTH", "WP_LIGURIAN_SEA"),
    ("LIVORNO", "WP_LIGURIAN_SEA"),
    ("GENOA", "WP_LIGURIAN_SEA"),
    ("WP_TYRRHENIAN_NORTH", "WP_SARDINIA_EAST"),
    ("WP_SARDINIA_EAST", "CAGLIARI"),
    ("CAGLIARI", "WP_SOUTH_SARDINIA"),
    ("WP_SOUTH_SARDINIA", "PALERMO"),
    ("WP_SOUTH_SARDINIA", "WP_SOUTH_SICILY"),
    ("CAGLIARI", "WP_WEST_SARDINIA"),
    ("WP_WEST_SARDINIA", "WP_BALEARIC_SEA"),
    ("WP_SOUTH_SARDINIA", "WP_WEST_SARDINIA"),
    ("WP_WEST_CORSICA", "WP_WEST_SARDINIA"),
    ("WP_WEST_CORSICA", "WP_BALEARIC_SEA"),
    ("WP_WEST_CORSICA", "WP_LIGURIAN_SEA"),
    ("WP_WEST_CORSICA", "GENOA"),
    ("WP_BONIFACIO", "WP_TYRRHENIAN_NORTH"),
    ("WP_LIGURIAN_SEA", "WP_GULF_OF_LION"),
    ("WP_GULF_OF_LION", "MARSEILLE"),
    ("WP_GULF_OF_LION", "SETE"),
    ("SETE", "WP_CAP_DE_CREUS"),
    ("WP_CAP_DE_CREUS", "BARCELONA"),
    ("WP_GULF_OF_LION", "WP_CAP_DE_CREUS"),
    ("WP_BALEARIC_SEA", "WP_CAP_DE_CREUS"),
    ("WP_BALEARIC_SEA", "BARCELONA"),
    ("BARCELONA", "WP_SPAIN_EAST"),
    ("WP_SPAIN_EAST", "VALENCIA"),
    ("WP_SPAIN_EAST", "CARTAGENA"),
    ("CARTAGENA", "WP_ALBORAN_SEA"),
    ("MALAGA", "WP_ALBORAN_SEA"),
    ("ALGIERS", "WP_ALGERIAN_COAST"),
    ("WP_ALGERIAN_COAST", "ORAN"),
    ("ORAN", "WP_ALBORAN_SEA"),
    ("ALGIERS", "WP_BALEARIC_SEA"),
    ("WP_ALBORAN_SEA", "GIBRALTAR"),
    ("WP_ALBORAN_SEA", "ALGECIRAS"),
    ("TANGIER", "GIBRALTAR"),
    ("CADIZ", "WP_MOROCCO_COAST"),
    ("WP_MOROCCO_COAST", "TANGIER"),
    ("WP_MOROCCO_COAST", "SINES"),
    ("SINES", "WP_PORTUGAL_COAST"),
    ("CADIZ", "WP_CAPE_ST_VINCENT"),
    ("WP_CAPE_ST_VINCENT", "WP_PORTUGAL_COAST"),
    ("WP_PORTUGAL_COAST", "LISBON"),
    ("WP_PORTUGAL_COAST", "WP_CAPE_FINISTERRE"),
    ("WP_CAPE_FINISTERRE", "WP_NORTH_CORUNA"),
    ("WP_NORTH_CORUNA", "WP_BAY_BISCAY"),
    ("WP_BAY_BISCAY", "WP_CANTABRIAN_SEA"),
    ("WP_CANTABRIAN_SEA", "BILBAO"),
    ("WP_BAY_BISCAY", "WP_USHANT"),
    ("WP_USHANT", "WP_ENGLISH_CHANNEL"),
    ("LE_HAVRE", "WP_ENGLISH_CHANNEL"),
    ("WP_ENGLISH_CHANNEL", "SOUTHAMPTON"),
    ("WP_ENGLISH_CHANNEL", "WP_STRAIT_DOVER"),
    ("SOUTHAMPTON", "WP_STRAIT_DOVER"),
    ("WP_STRAIT_DOVER", "WP_NORTH_SEA"),
    ("WP_NORTH_SEA", "ROTTERDAM"),
    ("WP_NORTH_SEA", "ANTWERP"),
    ("WP_NORTH_SEA", "FELIXSTOWE"),
    # Connect Black Sea ports to deep-water waypoints so cross-sea routes
    # take an offshore great-circle instead of coast-clipping straight
    # lines (e.g. Burgas → Sevastopol used to detour via Varna).
    ("BURGAS", "WP_BLACK_SEA_WEST"),
    ("VARNA",  "WP_BLACK_SEA_WEST"),
    ("CONSTANTA", "WP_BLACK_SEA_WEST"),
    ("CONSTANTA", "WP_BLACK_SEA_NW"),
    ("ODESSA",    "WP_BLACK_SEA_NW"),
    ("SEVASTOPOL","WP_BLACK_SEA_NW"),
    ("SEVASTOPOL","WP_BLACK_SEA_CENTRAL"),
    ("WP_BLACK_SEA_WEST",    "WP_BLACK_SEA_NW"),
    ("WP_BLACK_SEA_WEST",    "WP_BLACK_SEA_CENTRAL"),
    ("WP_BLACK_SEA_NW",      "WP_BLACK_SEA_CENTRAL"),
    ("WP_BLACK_SEA_CENTRAL", "WP_BLACK_SEA_EAST"),
    ("WP_BLACK_SEA_EAST",    "NOVOROSSIYSK"),
    ("WP_BLACK_SEA_EAST",    "BATUMI"),
]


def _build_graph() -> NavigationGraph:
    """
    Construct the full navigation graph from world ports + ocean grid.

    This is the heavy-lifting function called once at startup.
    """
    t0 = time.time()
    graph = NavigationGraph()

    raw_ports = _load_ports()
    port_ids: set[str] = set()

    for p in raw_ports:
        pid = p["port_id"]
        graph.add_waypoint(Waypoint(
            node_id=pid,
            latitude=p["lat"],
            longitude=p["lon"],
            name=p["name"],
        ))
        port_ids.add(pid)

    logger.info("Loaded %d ports", len(port_ids))

    for wp in _LEGACY_WAYPOINTS:
        wid = wp["port_id"]
        if not graph.has_waypoint(wid):
            graph.add_waypoint(Waypoint(
                node_id=wid,
                latitude=wp["lat"],
                longitude=wp["lon"],
                name=wp["name"],
            ))

    grid_nodes = generate_ocean_grid(step_deg=5.0)
    grid_index: dict[str, Waypoint] = {}
    for gn in grid_nodes:
        graph.add_waypoint(gn)
        grid_index[gn.node_id] = gn

    logger.info("Generated %d ocean grid nodes", len(grid_nodes))

    for p in raw_ports:
        pid = p["port_id"]
        nearest = find_nearest_grid_nodes(
            p["lat"], p["lon"], grid_nodes, k=3, max_distance_m=3_000_000.0,
        )
        for gn in nearest:
            if not _has_edge(graph, pid, gn.node_id):
                graph.add_edge(pid, gn.node_id, bidirectional=True)

    for wp in _LEGACY_WAYPOINTS:
        wid = wp["port_id"]
        nearest = find_nearest_grid_nodes(
            wp["lat"], wp["lon"], grid_nodes, k=2, max_distance_m=2_000_000.0,
        )
        for gn in nearest:
            if not _has_edge(graph, wid, gn.node_id):
                graph.add_edge(wid, gn.node_id, bidirectional=True)

    for gn in grid_nodes:
        neighbours = get_adjacent_grid_ids(gn, grid_index, step_deg=5.0)
        for nb in neighbours:
            if not _has_edge(graph, gn.node_id, nb.node_id):
                graph.add_edge(gn.node_id, nb.node_id, bidirectional=True)

    for src_id, dst_id in _DIRECT_CORRIDORS:
        if graph.has_waypoint(src_id) and graph.has_waypoint(dst_id):
            if not _has_edge(graph, src_id, dst_id):
                graph.add_edge(src_id, dst_id, bidirectional=True)

    for src_id, dst_id in _LEGACY_WP_CORRIDORS:
        if graph.has_waypoint(src_id) and graph.has_waypoint(dst_id):
            if not _has_edge(graph, src_id, dst_id):
                graph.add_edge(src_id, dst_id, bidirectional=True)

    for corridor in _RESTRICTED_CORRIDORS:
        src_id = corridor[0]
        dst_id = corridor[1]
        max_draft = corridor[2]
        max_length = corridor[3] if len(corridor) > 3 else None
        max_beam = corridor[4] if len(corridor) > 4 else None

        if graph.has_waypoint(src_id) and graph.has_waypoint(dst_id):
            graph.add_edge(
                src_id, dst_id, bidirectional=True,
                max_draft_m=max_draft, max_length_m=max_length, max_beam_m=max_beam,
            )

    elapsed = time.time() - t0
    logger.info(
        "Navigation graph built: %d nodes, %d edges in %.3fs",
        graph.node_count(), graph.edge_count(), elapsed,
    )

    return graph


def _has_edge(graph: NavigationGraph, src_id: str, dst_id: str) -> bool:
    """Check if a directed edge already exists."""
    for edge in graph.get_edges(src_id):
        if edge.destination.node_id == dst_id:
            return True
    return False


def build_navigation_graph() -> NavigationGraph:
    """
    Return the shared NavigationGraph singleton.

    Thread-safe: the graph is built exactly once, then cached.
    Subsequent calls return the same instance immediately.
    """
    global _graph
    if _graph is not None:
        return _graph

    with _graph_lock:
        # Double-check after acquiring the lock
        if _graph is not None:
            return _graph
        _graph = _build_graph()
        return _graph
