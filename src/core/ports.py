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


def _load_raw_ports() -> list[dict]:
    """
    Load port data from the world-ports module, falling back to a
    minimal inline list if the module isn't available yet.
    """
    try:
        from src.core.world_ports import WORLD_PORTS
        return WORLD_PORTS
    except ImportError:
        return _FALLBACK_PORTS


# Minimal fallback so the system boots even if world_ports.py is missing.
_FALLBACK_PORTS: list[dict] = [
    dict(port_id="VARNA", lat=43.2141, lon=27.9147, name="Varna",
         draft=14.0, aliases=("varna",)),
    dict(port_id="ISTANBUL", lat=41.0082, lon=28.9784, name="Istanbul",
         draft=15.0, aliases=("istanbul", "constantinople")),
    dict(port_id="PIRAEUS", lat=37.9475, lon=23.6425, name="Piraeus",
         draft=18.0, aliases=("piraeus", "athens", "pireas")),
    dict(port_id="ROTTERDAM", lat=51.9225, lon=4.4792, name="Rotterdam",
         draft=24.0, aliases=("rotterdam",)),
]


# ── The original _RAW_PORTS is preserved so that graph_builder.py can
#    fall back to it when world_ports.py hasn't been installed.
_RAW_PORTS: list[dict] = _load_raw_ports()


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

    key_spaced = key.replace("_", " ")
    port_id = _LOOKUP_INDEX.get(key_spaced)
    if port_id:
        return PORT_REGISTRY[port_id]

    return None


def list_all_ports() -> list[PortInfo]:
    """Return all ports (excluding open-sea waypoints and ocean grid nodes)."""
    return [
        p for p in PORT_REGISTRY.values()
        if not p.port_id.startswith("WP_") and not p.port_id.startswith("OG_")
    ]


def search_ports(query: str) -> list[PortInfo]:
    """Return ports whose name or aliases contain the query string."""
    q = query.strip().lower()
    if not q:
        return list_all_ports()
    results = []
    for port in PORT_REGISTRY.values():
        if port.port_id.startswith("WP_") or port.port_id.startswith("OG_"):
            continue
        if q in port.name.lower() or q in port.port_id.lower():
            results.append(port)
            continue
        if any(q in alias for alias in port.aliases):
            results.append(port)
    return results
