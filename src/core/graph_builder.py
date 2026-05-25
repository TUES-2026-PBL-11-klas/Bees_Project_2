"""
Build a NavigationGraph from the port catalogue.

Ports are connected along realistic maritime corridors.  Each edge
carries an optional *max_draft_m* restriction so that the routing
strategies can block passages that a particular vessel cannot traverse.
"""

from __future__ import annotations

from src.core.graph import NavigationGraph, Waypoint, haversine
from src.core.ports import PortInfo, repo as port_repo











_CORRIDORS: list[tuple] = [

    ("VARNA", "CONSTANTA", None),
    ("VARNA", "BURGAS", None),
    ("CONSTANTA", "ODESSA", None),
    ("NOVOROSSIYSK", "BATUMI", None),
    ("VARNA", "SEVASTOPOL", None),
    ("SEVASTOPOL", "NOVOROSSIYSK", None),
    ("SEVASTOPOL", "ODESSA", None),
    ("CONSTANTA", "SEVASTOPOL", None),
    ("BATUMI", "NOVOROSSIYSK", None),


    ("VARNA", "ISTANBUL", 15.0),
    ("CONSTANTA", "ISTANBUL", 15.0),
    ("BURGAS", "ISTANBUL", 15.0),


    ("ISTANBUL", "CANAKKALE", 15.0),


    ("CANAKKALE", "WP_NORTH_AEGEAN", None),
    ("WP_NORTH_AEGEAN", "THESSALONIKI", None),
    ("CANAKKALE", "WP_CENTRAL_AEGEAN", None),
    ("IZMIR", "WP_CENTRAL_AEGEAN", None),
    ("THESSALONIKI", "WP_NORTH_AEGEAN", None),
    ("WP_NORTH_AEGEAN", "WP_CENTRAL_AEGEAN", None),
    ("WP_CENTRAL_AEGEAN", "PIRAEUS", None),
    ("IZMIR", "WP_CENTRAL_AEGEAN", None),
    ("PIRAEUS", "HERAKLION", None),
    ("CANAKKALE", "WP_CENTRAL_AEGEAN", None),
    ("WP_CENTRAL_AEGEAN", "HERAKLION", None),
    ("IZMIR", "WP_CENTRAL_AEGEAN", None),


    ("PIRAEUS", "WP_CAPE_MALEAS", None),
    ("WP_CAPE_MALEAS", "WP_SOUTH_PELOPONNESE", None),
    ("WP_CAPE_MALEAS", "HERAKLION", None),
    ("PATRAS", "WP_SOUTH_PELOPONNESE", None),
    ("HERAKLION", "WP_SOUTH_PELOPONNESE", None),
    ("WP_SOUTH_PELOPONNESE", "WP_SOUTH_CRETE", None),
    ("WP_SOUTH_CRETE", "HERAKLION", None),


    ("IZMIR", "WP_EAST_MED", None),
    ("WP_EAST_MED", "ANTALYA", None),
    ("ANTALYA", "MERSIN", None),
    ("MERSIN", "ISKENDERUN", None),
    ("MERSIN", "LIMASSOL", None),
    ("ANTALYA", "LIMASSOL", None),
    ("HERAKLION", "LIMASSOL", None),
    ("LIMASSOL", "BEIRUT", None),
    ("LIMASSOL", "HAIFA", None),
    ("BEIRUT", "HAIFA", None),
    ("HAIFA", "PORT_SAID", None),
    ("LIMASSOL", "PORT_SAID", None),
    ("PORT_SAID", "ALEXANDRIA", None),
    ("WP_SOUTH_CRETE", "PORT_SAID", None),
    ("WP_SOUTH_CRETE", "WP_EAST_MED", None),
    ("WP_EAST_MED", "PORT_SAID", None),
    ("WP_EAST_MED", "ALEXANDRIA", None),
    ("WP_EAST_MED", "LIMASSOL", None),


    ("PORT_SAID", "SUEZ", 20.1, 400.0, 77.5),
    ("SUEZ", "JEDDAH", None),

    # --- Global Expansion Corridors ---
    ("JEDDAH", "WP_INDIAN_OCEAN_NORTH", None),
    ("WP_INDIAN_OCEAN_NORTH", "MUMBAI", None),
    ("MUMBAI", "WP_INDIAN_OCEAN_SOUTH", None),
    ("WP_INDIAN_OCEAN_SOUTH", "SINGAPORE", None),
    ("SINGAPORE", "SHANGHAI", None),
    ("SINGAPORE", "TOKYO", None),
    ("SUEZ", "WP_RED_SEA_MID", None),
    ("WP_RED_SEA_MID", "JEDDAH", None),
    ("SINGAPORE", "SYDNEY", None),
    ("SUEZ", "WP_ATLANTIC_NORTH", None),
    ("WP_ATLANTIC_NORTH", "ROTTERDAM_GLOBAL", None),
    ("ROTTERDAM_GLOBAL", "NEW_YORK", None),
    ("NEW_YORK", "SANTOS", None),
    ("SANTOS", "CAPE_TOWN", None),
    ("CAPE_TOWN", "WP_INDIAN_OCEAN_SOUTH", None),


    ("ALEXANDRIA", "WP_SOUTH_CRETE", None),
    ("BENGHAZI", "TRIPOLI_LY", None),
    ("BENGHAZI", "WP_SOUTH_CRETE", None),
    ("BENGHAZI", "WP_NORTH_AFRICA_MID", None),
    ("TRIPOLI_LY", "WP_NORTH_AFRICA_MID", None),


    ("WP_SOUTH_PELOPONNESE", "WP_IONIAN_SEA", None),
    ("WP_SOUTH_PELOPONNESE", "WP_STRAIT_OTRANTO", None),
    ("WP_IONIAN_SEA", "WP_STRAIT_OTRANTO", None),
    ("WP_IONIAN_SEA", "WP_SOUTH_SICILY", None),
    ("WP_IONIAN_SEA", "WP_EAST_SICILY", None),
    ("WP_IONIAN_SEA", "MALTA", None),
    ("WP_SOUTH_SICILY", "MALTA", None),
    ("WP_SOUTH_SICILY", "WP_EAST_SICILY", None),
    ("WP_EAST_SICILY", "CATANIA", None),
    ("WP_NORTH_AFRICA_MID", "MALTA", None),
    ("WP_NORTH_AFRICA_MID", "WP_SOUTH_SICILY", None),


    ("WP_STRAIT_OTRANTO", "TARANTO", None),
    ("WP_STRAIT_OTRANTO", "BARI", None),
    ("WP_STRAIT_OTRANTO", "BAR", None),
    ("WP_STRAIT_OTRANTO", "DUBROVNIK", None),
    ("BARI", "WP_ADRIATIC_MID", None),
    ("WP_ADRIATIC_MID", "ANCONA", None),
    ("ANCONA", "WP_ADRIATIC_NORTH", None),
    ("WP_ADRIATIC_NORTH", "VENICE", None),
    ("WP_ADRIATIC_NORTH", "TRIESTE", None),
    ("WP_ADRIATIC_NORTH", "KOPER", None),
    ("WP_ADRIATIC_NORTH", "RIJEKA", None),
    ("DUBROVNIK", "SPLIT", None),
    ("SPLIT", "WP_ADRIATIC_MID", None),
    ("BAR", "DUBROVNIK", None),


    ("CATANIA", "WP_EAST_SICILY", None),
    ("WP_EAST_SICILY", "WP_STRAIT_MESSINA", 8.0),
    ("WP_STRAIT_MESSINA", "GIOIA_TAURO", 8.0),



    ("NAPLES", "WP_TYRRHENIAN_SOUTH", None),
    ("SALERNO", "WP_TYRRHENIAN_SOUTH", None),
    ("GIOIA_TAURO", "WP_TYRRHENIAN_SOUTH", None),
    ("PALERMO", "WP_TYRRHENIAN_SOUTH", None),


    ("CATANIA", "WP_SOUTH_SICILY", None),


    ("PALERMO", "WP_CAPE_BON", None),
    ("MALTA", "WP_CAPE_BON", None),
    ("WP_CAPE_BON", "TUNIS", None),
    ("TUNIS", "WP_CAPE_BOUGAROUN", None),
    ("WP_CAPE_BOUGAROUN", "ALGIERS", None),


    ("WP_TYRRHENIAN_SOUTH", "WP_TYRRHENIAN_NORTH", None),
    ("WP_TYRRHENIAN_NORTH", "CIVITAVECCHIA", None),


    ("WP_TYRRHENIAN_NORTH", "WP_LIGURIAN_SEA", None),
    ("LIVORNO", "WP_LIGURIAN_SEA", None),
    ("GENOA", "WP_LIGURIAN_SEA", None),



    ("WP_TYRRHENIAN_NORTH", "WP_SARDINIA_EAST", None),
    ("WP_SARDINIA_EAST", "CAGLIARI", None),


    ("CAGLIARI", "WP_SOUTH_SARDINIA", None),
    ("WP_SOUTH_SARDINIA", "PALERMO", None),
    ("WP_SOUTH_SARDINIA", "WP_SOUTH_SICILY", None),


    ("CAGLIARI", "WP_WEST_SARDINIA", None),
    ("WP_WEST_SARDINIA", "WP_BALEARIC_SEA", None),
    ("WP_SOUTH_SARDINIA", "WP_WEST_SARDINIA", None),


    ("WP_WEST_CORSICA", "WP_WEST_SARDINIA", None),
    ("WP_WEST_CORSICA", "WP_BALEARIC_SEA", None),
    ("WP_WEST_CORSICA", "WP_LIGURIAN_SEA", None),
    ("WP_WEST_CORSICA", "GENOA", None),


    ("WP_BONIFACIO", "WP_SARDINIA_EAST", None),
    ("WP_BONIFACIO", "WP_WEST_CORSICA", None),
    ("WP_BONIFACIO", "WP_TYRRHENIAN_NORTH", None),


    ("GENOA", "WP_LIGURIAN_SEA", None),
    ("WP_LIGURIAN_SEA", "WP_GULF_OF_LION", None),
    ("WP_GULF_OF_LION", "MARSEILLE", None),
    ("MARSEILLE", "WP_GULF_OF_LION", None),
    ("WP_GULF_OF_LION", "SETE", None),
    ("SETE", "WP_CAP_DE_CREUS", None),
    ("WP_CAP_DE_CREUS", "BARCELONA", None),
    ("WP_GULF_OF_LION", "WP_CAP_DE_CREUS", None),
    ("WP_BALEARIC_SEA", "WP_CAP_DE_CREUS", None),
    ("WP_BALEARIC_SEA", "BARCELONA", None),
    ("BARCELONA", "WP_SPAIN_EAST", None),
    ("WP_SPAIN_EAST", "VALENCIA", None),
    ("VALENCIA", "WP_SPAIN_EAST", None),
    ("WP_SPAIN_EAST", "CARTAGENA", None),
    ("CARTAGENA", "WP_ALBORAN_SEA", None),
    ("MALAGA", "WP_ALBORAN_SEA", None),
    ("MALAGA", "ALGECIRAS", None),
    ("ALGECIRAS", "GIBRALTAR", None),


    ("ALGIERS", "WP_ALGERIAN_COAST", None),
    ("WP_ALGERIAN_COAST", "ORAN", None),
    ("ORAN", "WP_ALBORAN_SEA", None),
    ("ALGIERS", "WP_BALEARIC_SEA", None),
    ("WP_ALBORAN_SEA", "GIBRALTAR", None),
    ("WP_ALBORAN_SEA", "MALAGA", None),
    ("WP_ALBORAN_SEA", "ALGECIRAS", None),
    ("TANGIER", "GIBRALTAR", None),
    ("TANGIER", "ALGECIRAS", None),


    ("CADIZ", "WP_MOROCCO_COAST", None),
    ("WP_MOROCCO_COAST", "TANGIER", None),
    ("TANGIER", "CASABLANCA", None),
    ("CASABLANCA", "WP_MOROCCO_COAST", None),
    ("WP_MOROCCO_COAST", "SINES", None),
    ("SINES", "WP_PORTUGAL_COAST", None),
    ("CADIZ", "WP_CAPE_ST_VINCENT", None),
    ("WP_CAPE_ST_VINCENT", "WP_PORTUGAL_COAST", None),
    ("WP_PORTUGAL_COAST", "LISBON", None),


    ("LISBON", "WP_PORTUGAL_COAST", None),
    ("WP_PORTUGAL_COAST", "WP_CAPE_FINISTERRE", None),
    ("WP_CAPE_FINISTERRE", "WP_NORTH_CORUNA", None),
    ("WP_NORTH_CORUNA", "WP_BAY_BISCAY", None),
    ("WP_BAY_BISCAY", "WP_CANTABRIAN_SEA", None),
    ("WP_CANTABRIAN_SEA", "BILBAO", None),
    ("WP_BAY_BISCAY", "WP_USHANT", None),
    ("WP_USHANT", "WP_ENGLISH_CHANNEL", None),
    ("LE_HAVRE", "WP_ENGLISH_CHANNEL", None),
    ("WP_ENGLISH_CHANNEL", "SOUTHAMPTON", None),
    ("WP_ENGLISH_CHANNEL", "WP_STRAIT_DOVER", None),
    ("SOUTHAMPTON", "WP_STRAIT_DOVER", None),
    ("WP_STRAIT_DOVER", "WP_NORTH_SEA", None),
    ("WP_NORTH_SEA", "ROTTERDAM", None),
    ("WP_NORTH_SEA", "ANTWERP", None),
    ("WP_NORTH_SEA", "FELIXSTOWE", None),
    ("ROTTERDAM", "ANTWERP", None),
    ("ROTTERDAM", "HAMBURG", None),
    ("ROTTERDAM", "BREMERHAVEN", None),
    ("HAMBURG", "BREMERHAVEN", None),
]


_CACHED_GRAPH: Optional[NavigationGraph] = None

def get_graph() -> NavigationGraph:
    """
    Returns the singleton instance of the NavigationGraph.
    Builds the graph on the first call.
    """
    global _CACHED_GRAPH
    if _CACHED_GRAPH is None:
        _CACHED_GRAPH = build_navigation_graph()
    return _CACHED_GRAPH

def build_navigation_graph() -> NavigationGraph:
    """
    Build a fully connected maritime NavigationGraph.

    All edges are bidirectional.  Draft restrictions are applied to
    strait / canal passages.
    """
    graph = NavigationGraph()


    all_nodes = port_repo.list_all(only_ports=False)
    all_node_ids = {p.port_id for p in all_nodes}

    for port in all_nodes:
        graph.add_waypoint(Waypoint(
            node_id=port.port_id,
            latitude=port.latitude,
            longitude=port.longitude,
            name=port.name,
        ))

    for corridor in _CORRIDORS:
        src_id = corridor[0]
        dst_id = corridor[1]
        max_draft = corridor[2]
        max_length = corridor[3] if len(corridor) > 3 else None
        max_beam = corridor[4] if len(corridor) > 4 else None

        if src_id not in all_node_ids or dst_id not in all_node_ids:
            continue
        graph.add_edge(
            src_id, dst_id, bidirectional=True,
            max_draft_m=max_draft, max_length_m=max_length, max_beam_m=max_beam
        )

    # --- DYNAMIC MESH CONNECTION ---
    # Connect ports to the nearest global waypoints to ensure global connectivity
    all_nodes = port_repo.list_all(only_ports=False)
    waypoints = [p for p in all_nodes if p.is_waypoint]
    ports = [p for p in all_nodes if not p.is_waypoint]

    # Connect each port to its 3 nearest waypoints
    for port in ports:
        nearest = sorted(
            waypoints,
            key=lambda w: haversine(port.latitude, port.longitude, w.latitude, w.longitude)
        )[:3]
        for wp in nearest:
            graph.add_edge(port.port_id, wp.port_id, bidirectional=True)

    # Connect waypoints to each other if they are within a certain distance
    # (This creates the "ocean mesh")
    MAX_WP_DIST = 4000000 # 4000km
    for i in range(len(waypoints)):
        for j in range(i + 1, len(waypoints)):
            w1, w2 = waypoints[i], waypoints[j]
            if haversine(w1.latitude, w1.longitude, w2.latitude, w2.longitude) < MAX_WP_DIST:
                graph.add_edge(w1.port_id, w2.port_id, bidirectional=True)

    return graph
