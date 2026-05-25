from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional
from src.infrastructure.repositories.port_repository import PortRepository

@dataclass(frozen=True)
class PortInfo:
    port_id: str
    latitude: float
    longitude: float
    name: str
    max_draft_m: Optional[float] = None
    aliases: tuple[str, ...] = field(default_factory=tuple)

def _to_port_info(port) -> PortInfo:
    return PortInfo(
        port_id=port.port_id,
        latitude=port.latitude,
        longitude=port.longitude,
        name=port.name,
        max_draft_m=port.max_draft_m,
        aliases=tuple(port.aliases)
    )

repo = PortRepository()

def resolve_port(query: str) -> Optional[PortInfo]:
    """
    Resolve a user-supplied port name to a PortInfo.
    Supports: exact port_id (VARNA), city name (Varna), or alias (varna).
    Returns None if no match is found.
    """
    port = repo.resolve_port(query)
    return _to_port_info(port) if port else None

def list_all_ports() -> list[PortInfo]:
    """Return all ports (excluding open-sea waypoints)."""
    ports = repo.list_all(only_ports=True)
    return [_to_port_info(p) for p in ports]

def search_ports(query: str) -> list[PortInfo]:
    """Return ports whose name or aliases contain the query string."""
    q = query.strip().lower()
    if not q:
        return list_all_ports()

    all_ports = repo.list_all(only_ports=True)
    results = []
    for p in all_ports:
        if q in p.name.lower() or q in p.port_id.lower():
            results.append(_to_port_info(p))
            continue
        if any(q in alias.lower() for alias in p.aliases):
            results.append(_to_port_info(p))
    return results
