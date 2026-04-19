"""
Build a NavigationGraph from the port catalogue.

Ports are connected along realistic maritime corridors.  Each edge
carries an optional *max_draft_m* restriction so that the routing
strategies can block passages that a particular vessel cannot traverse.
"""

from __future__ import annotations

from src.core.graph import NavigationGraph, Waypoint
from src.core.ports import PORT_REGISTRY, PortInfo


# ---------------------------------------------------------------------------
# Maritime corridors
# ---------------------------------------------------------------------------
# Each tuple is (source_id, destination_id, max_draft_m | None).
# max_draft_m is the shallowest point along the edge; vessels whose
# draft exceeds this value must find an alternative.
# All connections are bidirectional.
# ---------------------------------------------------------------------------

_CORRIDORS: list[tuple] = [
    # ── Black Sea internal ────────────────────────────────────────────────
    ("VARNA", "CONSTANTA", None),
    ("VARNA", "BURGAS", None),
    ("CONSTANTA", "ODESSA", None),
    ("ODESSA", "NOVOROSSIYSK", None),
    ("NOVOROSSIYSK", "BATUMI", None),
    ("VARNA", "SEVASTOPOL", None),
    ("SEVASTOPOL", "NOVOROSSIYSK", None),
    ("SEVASTOPOL", "ODESSA", None),
    ("CONSTANTA", "SEVASTOPOL", None),
    ("BATUMI", "NOVOROSSIYSK", None),

    # ── Black Sea → Sea of Marmara (Bosphorus) ──────────────────────────
    ("VARNA", "ISTANBUL", 15.0),
    ("CONSTANTA", "ISTANBUL", 15.0),
    ("BURGAS", "ISTANBUL", 15.0),

    # ── Sea of Marmara → Aegean (Dardanelles) ───────────────────────────
    ("ISTANBUL", "CANAKKALE", 15.0),

    # ── Aegean ────────────────────────────────────────────────────────────
    ("CANAKKALE", "THESSALONIKI", None),
    ("CANAKKALE", "IZMIR", None),
    ("THESSALONIKI", "PIRAEUS", None),
    ("IZMIR", "PIRAEUS", None),
    ("PIRAEUS", "HERAKLION", None),
    ("PIRAEUS", "PATRAS", None),
    ("CANAKKALE", "HERAKLION", None),
    ("IZMIR", "HERAKLION", None),

    # ── South of Greece ──────────────────────────────────────────────────
    ("PIRAEUS", "WP_SOUTH_PELOPONNESE", None),
    ("PATRAS", "WP_SOUTH_PELOPONNESE", None),
    ("HERAKLION", "WP_SOUTH_PELOPONNESE", None),
    ("WP_SOUTH_PELOPONNESE", "WP_SOUTH_CRETE", None),
    ("WP_SOUTH_CRETE", "HERAKLION", None),

    # ── Eastern Mediterranean ─────────────────────────────────────────────
    ("IZMIR", "ANTALYA", None),
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

    # ── Suez Canal & Red Sea ─────────────────────────────────────────────
    ("PORT_SAID", "SUEZ", 20.1, 400.0, 77.5),
    ("SUEZ", "JEDDAH", None),

    # ── Libya coast ──────────────────────────────────────────────────────
    ("ALEXANDRIA", "BENGHAZI", None),
    ("BENGHAZI", "TRIPOLI_LY", None),
    ("BENGHAZI", "WP_SOUTH_CRETE", None),
    ("BENGHAZI", "WP_NORTH_AFRICA_MID", None),
    ("TRIPOLI_LY", "WP_NORTH_AFRICA_MID", None),

    # ── Ionian Sea / Strait of Otranto ──────────────────────────────────
    ("WP_SOUTH_PELOPONNESE", "WP_IONIAN_SEA", None),
    ("WP_SOUTH_PELOPONNESE", "WP_STRAIT_OTRANTO", None),
    ("WP_IONIAN_SEA", "WP_STRAIT_OTRANTO", None),
    ("WP_IONIAN_SEA", "WP_SOUTH_SICILY", None),
    ("WP_IONIAN_SEA", "CATANIA", None),
    ("WP_IONIAN_SEA", "MALTA", None),
    ("WP_SOUTH_SICILY", "MALTA", None),
    ("WP_SOUTH_SICILY", "CATANIA", None),
    ("WP_NORTH_AFRICA_MID", "MALTA", None),
    ("WP_NORTH_AFRICA_MID", "WP_SOUTH_SICILY", None),

    # ── Adriatic ─────────────────────────────────────────────────────────
    ("WP_STRAIT_OTRANTO", "TARANTO", None),
    ("WP_STRAIT_OTRANTO", "BARI", None),
    ("WP_STRAIT_OTRANTO", "BAR", None),
    ("WP_STRAIT_OTRANTO", "DUBROVNIK", None),
    ("TARANTO", "BARI", None),
    ("BARI", "ANCONA", None),
    ("ANCONA", "VENICE", None),
    ("VENICE", "TRIESTE", None),
    ("TRIESTE", "KOPER", None),
    ("ANCONA", "RIJEKA", None),
    ("RIJEKA", "TRIESTE", None),
    ("DUBROVNIK", "SPLIT", None),
    ("SPLIT", "RIJEKA", None),
    ("BAR", "DUBROVNIK", None),

    # ── Strait of Messina & Tyrrhenian ───────────────────────────────────
    ("CATANIA", "WP_STRAIT_MESSINA", 8.0),
    ("WP_STRAIT_MESSINA", "GIOIA_TAURO", 8.0),

    # ── Tyrrhenian Sea ───────────────────────────────────────────────────
    # South Tyrrhenian: Naples and nearby ports connect via offshore WP
    ("NAPLES", "WP_TYRRHENIAN_SOUTH", None),
    ("SALERNO", "WP_TYRRHENIAN_SOUTH", None),
    ("GIOIA_TAURO", "WP_TYRRHENIAN_SOUTH", None),
    ("PALERMO", "WP_TYRRHENIAN_SOUTH", None),

    # Palermo and Catania stay over water (across north Sicily coast)
    ("CATANIA", "PALERMO", None),

    # North Africa connections via sea
    ("PALERMO", "TUNIS", None),
    ("MALTA", "TUNIS", None),
    ("TUNIS", "ALGIERS", None),

    # North Tyrrhenian: connects to Italian west-coast ports offshore
    ("WP_TYRRHENIAN_SOUTH", "WP_TYRRHENIAN_NORTH", None),
    ("WP_TYRRHENIAN_NORTH", "CIVITAVECCHIA", None),

    # Ligurian Sea: offshore hub between Genoa, Livorno, and Tyrrhenian
    ("WP_TYRRHENIAN_NORTH", "WP_LIGURIAN_SEA", None),
    ("LIVORNO", "WP_LIGURIAN_SEA", None),
    ("GENOA", "WP_LIGURIAN_SEA", None),

    # ── Sardinia / Corsica routing ───────────────────────────────────────
    # East of Sardinia (Tyrrhenian side)
    ("WP_TYRRHENIAN_NORTH", "WP_SARDINIA_EAST", None),
    ("WP_SARDINIA_EAST", "CAGLIARI", None),

    # South of Sardinia
    ("CAGLIARI", "WP_SOUTH_SARDINIA", None),
    ("WP_SOUTH_SARDINIA", "PALERMO", None),
    ("WP_SOUTH_SARDINIA", "WP_SOUTH_SICILY", None),

    # West of Sardinia (towards Balearic Sea)
    ("CAGLIARI", "WP_WEST_SARDINIA", None),
    ("WP_WEST_SARDINIA", "WP_BALEARIC_SEA", None),
    ("WP_SOUTH_SARDINIA", "WP_WEST_SARDINIA", None),

    # West of Corsica (for routes between France/Genoa and Sardinia/Tyrrhenian)
    ("WP_WEST_CORSICA", "WP_WEST_SARDINIA", None),
    ("WP_WEST_CORSICA", "WP_BALEARIC_SEA", None),
    ("WP_WEST_CORSICA", "WP_LIGURIAN_SEA", None),
    ("WP_WEST_CORSICA", "GENOA", None),

    # Bonifacio Strait (between Corsica and Sardinia, restricted draft)
    ("WP_BONIFACIO", "WP_SARDINIA_EAST", None),
    ("WP_BONIFACIO", "WP_WEST_CORSICA", None),
    ("WP_BONIFACIO", "WP_TYRRHENIAN_NORTH", None),

    # ── Western Mediterranean ────────────────────────────────────────────
    ("GENOA", "MARSEILLE", None),
    ("MARSEILLE", "SETE", None),
    ("SETE", "BARCELONA", None),
    ("MARSEILLE", "BARCELONA", None),
    ("WP_BALEARIC_SEA", "BARCELONA", None),
    ("WP_BALEARIC_SEA", "MARSEILLE", None),
    ("BARCELONA", "VALENCIA", None),
    ("VALENCIA", "CARTAGENA", None),
    ("CARTAGENA", "MALAGA", None),
    ("MALAGA", "ALGECIRAS", None),
    ("ALGECIRAS", "GIBRALTAR", None),
    ("ALGECIRAS", "CADIZ", None),

    # ── North Africa (West) ──────────────────────────────────────────────
    ("ALGIERS", "ORAN", None),
    ("ORAN", "WP_ALBORAN_SEA", None),
    ("ALGIERS", "WP_BALEARIC_SEA", None),
    ("WP_ALBORAN_SEA", "GIBRALTAR", None),
    ("WP_ALBORAN_SEA", "MALAGA", None),
    ("WP_ALBORAN_SEA", "ALGECIRAS", None),
    ("TANGIER", "GIBRALTAR", None),
    ("TANGIER", "ALGECIRAS", None),

    # ── Atlantic (Iberian coast) ─────────────────────────────────────────
    ("GIBRALTAR", "CADIZ", None),
    ("CADIZ", "LISBON", None),
    ("LISBON", "SINES", None),
    ("SINES", "LISBON", None),
    ("CADIZ", "TANGIER", None),
    ("TANGIER", "CASABLANCA", None),
    ("CASABLANCA", "SINES", None),

    # ── Atlantic (northern leg) ──────────────────────────────────────────
    ("LISBON", "WP_CAPE_FINISTERRE", None),
    ("WP_CAPE_FINISTERRE", "BILBAO", None),
    ("BILBAO", "WP_BAY_BISCAY", None),
    ("WP_BAY_BISCAY", "LE_HAVRE", None),
    ("WP_BAY_BISCAY", "WP_CAPE_FINISTERRE", None),
    ("LE_HAVRE", "WP_ENGLISH_CHANNEL", None),
    ("WP_ENGLISH_CHANNEL", "SOUTHAMPTON", None),
    ("WP_ENGLISH_CHANNEL", "WP_NORTH_SEA", None),
    ("SOUTHAMPTON", "WP_NORTH_SEA", None),
    ("WP_NORTH_SEA", "ROTTERDAM", None),
    ("WP_NORTH_SEA", "ANTWERP", None),
    ("WP_NORTH_SEA", "FELIXSTOWE", None),
    ("ROTTERDAM", "ANTWERP", None),
    ("ROTTERDAM", "HAMBURG", None),
    ("ROTTERDAM", "BREMERHAVEN", None),
    ("HAMBURG", "BREMERHAVEN", None),
]


def build_navigation_graph() -> NavigationGraph:
    """
    Build a fully connected maritime NavigationGraph.

    All edges are bidirectional.  Draft restrictions are applied to
    strait / canal passages.
    """
    graph = NavigationGraph()

    # Register every port as a waypoint
    for port in PORT_REGISTRY.values():
        graph.add_waypoint(Waypoint(
            node_id=port.port_id,
            latitude=port.latitude,
            longitude=port.longitude,
            name=port.name,
        ))

    # Add edges along corridors
    for corridor in _CORRIDORS:
        src_id = corridor[0]
        dst_id = corridor[1]
        max_draft = corridor[2]
        max_length = corridor[3] if len(corridor) > 3 else None
        max_beam = corridor[4] if len(corridor) > 4 else None

        if src_id not in PORT_REGISTRY or dst_id not in PORT_REGISTRY:
            continue
        graph.add_edge(
            src_id, dst_id, bidirectional=True,
            max_draft_m=max_draft, max_length_m=max_length, max_beam_m=max_beam
        )

    return graph
