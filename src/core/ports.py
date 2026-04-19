"""
Comprehensive database of maritime ports and sea waypoints.

Each port entry is a dict with:
    latitude   – WGS-84 latitude in decimal degrees
    longitude  – WGS-84 longitude in decimal degrees
    name       – Human-readable label
    max_draft_m – Maximum vessel draft the port can handle (metres).
                  None ⇒ no draft restriction (deep water).
    aliases    – Alternate names/spellings for fuzzy lookup.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class PortInfo:
    port_id: str
    latitude: float
    longitude: float
    name: str
    max_draft_m: Optional[float] = None
    aliases: tuple[str, ...] = field(default_factory=tuple)


# ---------------------------------------------------------------------------
# Port catalogue
# ---------------------------------------------------------------------------

_RAW_PORTS: list[dict] = [
    # ── Black Sea ─────────────────────────────────────────────────────────
    dict(port_id="VARNA", lat=43.2141, lon=27.9147, name="Varna",
         draft=14.0, aliases=("varna",)),
    dict(port_id="CONSTANTA", lat=44.1598, lon=28.6348, name="Constanța",
         draft=19.0, aliases=("constanta", "constantza")),
    dict(port_id="ODESSA", lat=46.4825, lon=30.7233, name="Odessa",
         draft=13.0, aliases=("odesa", "odessa")),
    dict(port_id="NOVOROSSIYSK", lat=44.7234, lon=37.7686, name="Novorossiysk",
         draft=19.0, aliases=("novorossiysk",)),
    dict(port_id="BATUMI", lat=41.6168, lon=41.6367, name="Batumi",
         draft=13.0, aliases=("batumi",)),
    dict(port_id="SEVASTOPOL", lat=44.6054, lon=33.5254, name="Sevastopol",
         draft=12.0, aliases=("sevastopol",)),
    dict(port_id="BURGAS", lat=42.4975, lon=27.4728, name="Burgas",
         draft=12.5, aliases=("burgas", "bourgas")),

    # ── Turkish Straits ───────────────────────────────────────────────────
    dict(port_id="ISTANBUL", lat=41.0082, lon=28.9784, name="Istanbul",
         draft=15.0, aliases=("istanbul", "constantinople")),
    dict(port_id="CANAKKALE", lat=40.1553, lon=26.4142, name="Çanakkale",
         draft=15.0, aliases=("canakkale", "dardanelles", "gallipoli")),

    # ── Aegean / Greece ───────────────────────────────────────────────────
    dict(port_id="THESSALONIKI", lat=40.6401, lon=22.9444, name="Thessaloniki",
         draft=12.0, aliases=("thessaloniki", "saloniki", "salonica")),
    dict(port_id="PIRAEUS", lat=37.9475, lon=23.6425, name="Piraeus",
         draft=18.0, aliases=("piraeus", "athens", "pireas")),
    dict(port_id="HERAKLION", lat=35.3387, lon=25.1442, name="Heraklion",
         draft=12.0, aliases=("heraklion", "iraklion", "crete")),
    dict(port_id="PATRAS", lat=38.2466, lon=21.7346, name="Patras",
         draft=12.0, aliases=("patras", "patra")),

    # ── Turkey (Aegean & Med coast) ───────────────────────────────────────
    dict(port_id="IZMIR", lat=38.4192, lon=27.1287, name="Izmir",
         draft=14.0, aliases=("izmir", "smyrna")),
    dict(port_id="ANTALYA", lat=36.8841, lon=30.7056, name="Antalya",
         draft=12.0, aliases=("antalya",)),
    dict(port_id="MERSIN", lat=36.7990, lon=34.6380, name="Mersin",
         draft=14.0, aliases=("mersin", "icel")),
    dict(port_id="ISKENDERUN", lat=36.5867, lon=36.1654, name="İskenderun",
         draft=14.0, aliases=("iskenderun", "alexandretta")),

    # ── Cyprus & Levant ───────────────────────────────────────────────────
    dict(port_id="LIMASSOL", lat=34.6747, lon=33.0420, name="Limassol",
         draft=14.0, aliases=("limassol", "lemesos", "cyprus")),
    dict(port_id="BEIRUT", lat=33.9000, lon=35.5000, name="Beirut",
         draft=12.0, aliases=("beirut",)),
    dict(port_id="HAIFA", lat=32.8192, lon=34.9983, name="Haifa",
         draft=13.7, aliases=("haifa",)),
    dict(port_id="PORT_SAID", lat=31.2653, lon=32.3019, name="Port Said",
         draft=16.0, aliases=("port said", "portsaid")),
    dict(port_id="ALEXANDRIA", lat=31.2001, lon=29.9187, name="Alexandria",
         draft=15.0, aliases=("alexandria", "alex")),

    # ── Suez & Red Sea ────────────────────────────────────────────────────
    dict(port_id="SUEZ", lat=29.9668, lon=32.5498, name="Suez",
         draft=20.1, aliases=("suez", "suez canal")),
    dict(port_id="JEDDAH", lat=21.4858, lon=39.1925, name="Jeddah",
         draft=16.0, aliases=("jeddah", "jiddah")),

    # ── North Africa ──────────────────────────────────────────────────────
    dict(port_id="BENGHAZI", lat=32.1167, lon=20.0667, name="Benghazi",
         draft=10.0, aliases=("benghazi",)),
    dict(port_id="TRIPOLI_LY", lat=32.8752, lon=13.1875, name="Tripoli (Libya)",
         draft=10.0, aliases=("tripoli", "tarabulus")),
    dict(port_id="TUNIS", lat=36.8065, lon=10.1815, name="Tunis",
         draft=10.5, aliases=("tunis", "la goulette")),
    dict(port_id="ALGIERS", lat=36.7538, lon=3.0588, name="Algiers",
         draft=12.0, aliases=("algiers", "alger", "dzayer")),
    dict(port_id="ORAN", lat=35.6969, lon=-0.6331, name="Oran",
         draft=12.0, aliases=("oran",)),
    dict(port_id="TANGIER", lat=35.7595, lon=-5.8340, name="Tangier",
         draft=16.0, aliases=("tangier", "tanger")),
    dict(port_id="CASABLANCA", lat=33.5731, lon=-7.5898, name="Casablanca",
         draft=14.0, aliases=("casablanca",)),

    # ── Italy ─────────────────────────────────────────────────────────────
    dict(port_id="VENICE", lat=45.4408, lon=12.3155, name="Venice",
         draft=10.0, aliases=("venice", "venezia")),
    dict(port_id="TRIESTE", lat=45.6495, lon=13.7768, name="Trieste",
         draft=17.0, aliases=("trieste",)),
    dict(port_id="ANCONA", lat=43.6158, lon=13.5184, name="Ancona",
         draft=12.0, aliases=("ancona",)),
    dict(port_id="BARI", lat=41.1188, lon=16.8620, name="Bari",
         draft=10.0, aliases=("bari",)),
    dict(port_id="TARANTO", lat=40.4618, lon=17.2479, name="Taranto",
         draft=12.0, aliases=("taranto",)),
    dict(port_id="CATANIA", lat=37.5079, lon=15.0934, name="Catania",
         draft=12.0, aliases=("catania", "sicily east")),
    dict(port_id="PALERMO", lat=38.1157, lon=13.3615, name="Palermo",
         draft=12.0, aliases=("palermo", "sicily")),
    dict(port_id="NAPLES", lat=40.8518, lon=14.2681, name="Naples",
         draft=14.0, aliases=("naples", "napoli")),
    dict(port_id="SALERNO", lat=40.6824, lon=14.7681, name="Salerno",
         draft=12.0, aliases=("salerno",)),
    dict(port_id="GIOIA_TAURO", lat=38.4260, lon=15.8908, name="Gioia Tauro",
         draft=18.0, aliases=("gioia tauro",)),
    dict(port_id="GENOA", lat=44.4056, lon=8.9463, name="Genoa",
         draft=15.0, aliases=("genoa", "genova")),
    dict(port_id="LIVORNO", lat=43.5485, lon=10.3106, name="Livorno",
         draft=13.0, aliases=("livorno", "leghorn")),
    dict(port_id="CIVITAVECCHIA", lat=42.0930, lon=11.7868, name="Civitavecchia",
         draft=13.0, aliases=("civitavecchia", "rome port")),
    dict(port_id="CAGLIARI", lat=39.2152, lon=9.1097, name="Cagliari",
         draft=14.0, aliases=("cagliari", "sardinia")),

    # ── Malta ─────────────────────────────────────────────────────────────
    dict(port_id="MALTA", lat=35.9042, lon=14.5189, name="Valletta (Malta)",
         draft=17.0, aliases=("malta", "valletta")),

    # ── Adriatic (East) ──────────────────────────────────────────────────
    dict(port_id="DUBROVNIK", lat=42.6507, lon=17.8947, name="Dubrovnik",
         draft=10.0, aliases=("dubrovnik",)),
    dict(port_id="SPLIT", lat=43.5081, lon=16.4402, name="Split",
         draft=12.0, aliases=("split",)),
    dict(port_id="RIJEKA", lat=45.3271, lon=14.4422, name="Rijeka",
         draft=13.0, aliases=("rijeka", "fiume")),
    dict(port_id="KOPER", lat=45.5481, lon=13.7294, name="Koper",
         draft=15.0, aliases=("koper",)),
    dict(port_id="BAR", lat=42.0912, lon=19.0970, name="Bar",
         draft=12.0, aliases=("bar", "montenegro")),

    # ── Spain ─────────────────────────────────────────────────────────────
    dict(port_id="BARCELONA", lat=41.3851, lon=2.1734, name="Barcelona",
         draft=16.0, aliases=("barcelona",)),
    dict(port_id="VALENCIA", lat=39.4699, lon=-0.3763, name="Valencia",
         draft=16.0, aliases=("valencia",)),
    dict(port_id="CARTAGENA", lat=37.6000, lon=-0.9900, name="Cartagena",
         draft=14.0, aliases=("cartagena",)),
    dict(port_id="MALAGA", lat=36.7213, lon=-4.4214, name="Málaga",
         draft=12.0, aliases=("malaga",)),
    dict(port_id="CADIZ", lat=36.5271, lon=-6.2886, name="Cádiz",
         draft=14.0, aliases=("cadiz",)),
    dict(port_id="ALGECIRAS", lat=36.1271, lon=-5.4467, name="Algeciras",
         draft=16.0, aliases=("algeciras",)),
    dict(port_id="BILBAO", lat=43.2627, lon=-2.9253, name="Bilbao",
         draft=14.0, aliases=("bilbao",)),

    # ── France ────────────────────────────────────────────────────────────
    dict(port_id="MARSEILLE", lat=43.2965, lon=5.3698, name="Marseille",
         draft=14.5, aliases=("marseille", "marsiglia")),
    dict(port_id="SETE", lat=43.4036, lon=3.6966, name="Sète",
         draft=10.0, aliases=("sete",)),
    dict(port_id="LE_HAVRE", lat=49.4944, lon=0.1079, name="Le Havre",
         draft=15.5, aliases=("le havre",)),

    # ── Portugal ──────────────────────────────────────────────────────────
    dict(port_id="LISBON", lat=38.7223, lon=-9.1393, name="Lisbon",
         draft=14.5, aliases=("lisbon", "lisboa")),
    dict(port_id="SINES", lat=37.9567, lon=-8.8717, name="Sines",
         draft=28.0, aliases=("sines",)),

    # ── Gibraltar ─────────────────────────────────────────────────────────
    dict(port_id="GIBRALTAR", lat=36.1408, lon=-5.3536, name="Gibraltar",
         draft=11.0, aliases=("gibraltar", "gib")),

    # ── Northern Europe ───────────────────────────────────────────────────
    dict(port_id="ROTTERDAM", lat=51.9225, lon=4.4792, name="Rotterdam",
         draft=24.0, aliases=("rotterdam",)),
    dict(port_id="ANTWERP", lat=51.2194, lon=4.4025, name="Antwerp",
         draft=16.0, aliases=("antwerp", "anvers", "antwerpen")),
    dict(port_id="HAMBURG", lat=53.5511, lon=9.9937, name="Hamburg",
         draft=15.0, aliases=("hamburg",)),
    dict(port_id="BREMERHAVEN", lat=53.5396, lon=8.5809, name="Bremerhaven",
         draft=14.5, aliases=("bremerhaven", "bremen")),
    dict(port_id="SOUTHAMPTON", lat=50.8998, lon=-1.4044, name="Southampton",
         draft=16.0, aliases=("southampton",)),
    dict(port_id="FELIXSTOWE", lat=51.9559, lon=1.3511, name="Felixstowe",
         draft=16.0, aliases=("felixstowe",)),

    # ── Open-sea routing waypoints ────────────────────────────────────────
    # These ensure routes curve around land masses instead of cutting through.
    # EVERY waypoint must be in genuinely open water, and every corridor
    # leg (straight line between two connected nodes) must stay over sea.
    dict(port_id="WP_SOUTH_PELOPONNESE", lat=36.38, lon=22.50,
         name="South Peloponnese (open sea)", draft=None, aliases=()),
    dict(port_id="WP_SOUTH_CRETE", lat=34.80, lon=24.50,
         name="South of Crete (open sea)", draft=None, aliases=()),
    dict(port_id="WP_STRAIT_OTRANTO", lat=39.80, lon=19.00,
         name="Strait of Otranto (open sea)", draft=None, aliases=()),
    dict(port_id="WP_IONIAN_SEA", lat=37.50, lon=18.50,
         name="Ionian Sea (open sea)", draft=None, aliases=()),
    dict(port_id="WP_SOUTH_SICILY", lat=36.50, lon=14.50,
         name="South of Sicily (open sea)", draft=None, aliases=()),
    dict(port_id="WP_STRAIT_MESSINA", lat=38.20, lon=15.60,
         name="Strait of Messina (open sea)", draft=8.0, aliases=()),
    dict(port_id="WP_EAST_SICILY", lat=37.10, lon=15.35,
         name="East of Sicily (open sea)", draft=None, aliases=()),

    # Tyrrhenian Sea waypoints — well offshore of the Italian mainland
    dict(port_id="WP_TYRRHENIAN_SOUTH", lat=40.00, lon=13.00,
         name="South Tyrrhenian (open sea)", draft=None, aliases=()),
    dict(port_id="WP_TYRRHENIAN_NORTH", lat=42.00, lon=10.50,
         name="North Tyrrhenian (open sea)", draft=None, aliases=()),

    # Ligurian Sea — offshore of the Genoa-Livorno coast
    dict(port_id="WP_LIGURIAN_SEA", lat=43.30, lon=9.00,
         name="Ligurian Sea (open sea)", draft=None, aliases=()),

    # West of Corsica — ensures routes from France/Genoa go around Corsica
    dict(port_id="WP_WEST_CORSICA", lat=42.00, lon=8.00,
         name="West of Corsica (open sea)", draft=None, aliases=()),

    # Strait of Bonifacio area — between Corsica and Sardinia
    dict(port_id="WP_BONIFACIO", lat=41.00, lon=9.00,
         name="Strait of Bonifacio (open sea)", draft=11.0, aliases=()),

    # West of Sardinia — open water west of Sardinia
    dict(port_id="WP_WEST_SARDINIA", lat=40.00, lon=7.50,
         name="West of Sardinia (open sea)", draft=None, aliases=()),

    # South of Sardinia — open water south of Sardinia
    dict(port_id="WP_SOUTH_SARDINIA", lat=38.50, lon=9.00,
         name="South of Sardinia (open sea)", draft=None, aliases=()),

    # East of Sardinia — in the Tyrrhenian, clear of the island
    dict(port_id="WP_SARDINIA_EAST", lat=39.50, lon=10.50,
         name="East of Sardinia (open sea)", draft=None, aliases=()),

    dict(port_id="WP_BALEARIC_SEA", lat=39.50, lon=4.00,
         name="Balearic Sea (open sea)", draft=None, aliases=()),
    dict(port_id="WP_SPAIN_EAST", lat=39.00, lon=0.50,
         name="East of Spain (open sea)", draft=None, aliases=()),
    dict(port_id="WP_ALBORAN_SEA", lat=36.00, lon=-3.00,
         name="Alboran Sea (open sea)", draft=None, aliases=()),
    dict(port_id="WP_NORTH_AFRICA_MID", lat=34.50, lon=12.00,
         name="Central Mediterranean (open sea)", draft=None, aliases=()),
    dict(port_id="WP_BAY_BISCAY", lat=45.00, lon=-5.00,
         name="Bay of Biscay (open sea)", draft=None, aliases=()),
    dict(port_id="WP_CANTABRIAN_SEA", lat=44.00, lon=-3.50,
         name="Cantabrian Sea (open sea)", draft=None, aliases=()),
    dict(port_id="WP_ENGLISH_CHANNEL", lat=50.00, lon=-1.50,
         name="English Channel (open sea)", draft=None, aliases=()),
    dict(port_id="WP_STRAIT_DOVER", lat=51.10, lon=1.50,
         name="Strait of Dover (open sea)", draft=None, aliases=()),
    dict(port_id="WP_NORTH_SEA", lat=52.50, lon=3.00,
         name="North Sea (open sea)", draft=None, aliases=()),
    dict(port_id="WP_CAPE_ST_VINCENT", lat=36.80, lon=-9.20,
         name="Cape St Vincent (open sea)", draft=None, aliases=()),
    dict(port_id="WP_PORTUGAL_COAST", lat=39.50, lon=-10.00,
         name="Portugal Coast (open sea)", draft=None, aliases=()),
    dict(port_id="WP_CAPE_FINISTERRE", lat=43.00, lon=-9.50,
         name="Cape Finisterre (open sea)", draft=None, aliases=()),
    dict(port_id="WP_NORTH_CORUNA", lat=44.00, lon=-8.50,
         name="North Coruna (open sea)", draft=None, aliases=()),
    dict(port_id="WP_USHANT", lat=48.60, lon=-5.50,
         name="Ushant (open sea)", draft=None, aliases=()),
    dict(port_id="WP_GULF_OF_LION", lat=42.50, lon=4.50,
         name="Gulf of Lion (open sea)", draft=None, aliases=()),
    dict(port_id="WP_CAP_DE_CREUS", lat=42.30, lon=3.50,
         name="Cap de Creus (open sea)", draft=None, aliases=()),
    dict(port_id="WP_ALGERIAN_COAST", lat=37.00, lon=1.00,
         name="Algerian Coast (open sea)", draft=None, aliases=()),
    dict(port_id="WP_CAPE_BOUGAROUN", lat=37.50, lon=6.50,
         name="Cape Bougaroun (open sea)", draft=None, aliases=()),
    dict(port_id="WP_CAPE_BON", lat=37.20, lon=11.20,
         name="Cape Bon (open sea)", draft=None, aliases=()),
    dict(port_id="WP_MOROCCO_COAST", lat=34.00, lon=-8.00,
         name="Morocco Coast (open sea)", draft=None, aliases=()),
    dict(port_id="WP_ADRIATIC_MID", lat=43.00, lon=15.00,
         name="Mid Adriatic (open sea)", draft=None, aliases=()),
    dict(port_id="WP_ADRIATIC_NORTH", lat=44.50, lon=13.00,
         name="North Adriatic (open sea)", draft=None, aliases=()),
    dict(port_id="WP_EAST_MED", lat=33.50, lon=30.00,
         name="Eastern Mediterranean (open sea)", draft=None, aliases=()),
    dict(port_id="WP_NORTH_AEGEAN", lat=39.50, lon=24.50,
         name="North Aegean (open sea)", draft=None, aliases=()),
    dict(port_id="WP_CENTRAL_AEGEAN", lat=37.50, lon=25.00,
         name="Central Aegean (open sea)", draft=None, aliases=()),
    dict(port_id="WP_CAPE_MALEAS", lat=36.20, lon=23.40,
         name="Cape Maleas (open sea)", draft=None, aliases=()),
]


def _build_port_registry() -> dict[str, PortInfo]:
    registry: dict[str, PortInfo] = {}
    for p in _RAW_PORTS:
        info = PortInfo(
            port_id=p["port_id"],
            latitude=p["lat"],
            longitude=p["lon"],
            name=p["name"],
            max_draft_m=p.get("draft"),
            aliases=tuple(p.get("aliases", ())),
        )
        registry[info.port_id] = info
    return registry


PORT_REGISTRY: dict[str, PortInfo] = _build_port_registry()


def _build_lookup_index() -> dict[str, str]:
    """Build a case-insensitive lookup from names/aliases → port_id."""
    index: dict[str, str] = {}
    for port in PORT_REGISTRY.values():
        index[port.port_id.lower()] = port.port_id
        index[port.name.lower()] = port.port_id
        for alias in port.aliases:
            index[alias.lower()] = port.port_id
    return index


_LOOKUP_INDEX: dict[str, str] = _build_lookup_index()


def resolve_port(query: str) -> Optional[PortInfo]:
    """
    Resolve a user-supplied port name to a PortInfo.

    Supports: exact port_id (VARNA), city name (Varna), or alias (varna).
    Returns None if no match is found.
    """
    key = query.strip().lower()
    port_id = _LOOKUP_INDEX.get(key)
    if port_id:
        return PORT_REGISTRY[port_id]

    # Try matching with underscores replaced by spaces
    key_spaced = key.replace("_", " ")
    port_id = _LOOKUP_INDEX.get(key_spaced)
    if port_id:
        return PORT_REGISTRY[port_id]

    return None


def list_all_ports() -> list[PortInfo]:
    """Return all ports (excluding open-sea waypoints)."""
    return [p for p in PORT_REGISTRY.values() if not p.port_id.startswith("WP_")]


def search_ports(query: str) -> list[PortInfo]:
    """Return ports whose name or aliases contain the query string."""
    q = query.strip().lower()
    if not q:
        return list_all_ports()
    results = []
    for port in PORT_REGISTRY.values():
        if port.port_id.startswith("WP_"):
            continue
        if q in port.name.lower() or q in port.port_id.lower():
            results.append(port)
            continue
        if any(q in alias for alias in port.aliases):
            results.append(port)
    return results
