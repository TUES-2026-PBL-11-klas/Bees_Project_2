from typing import List, Optional
import re
from src.models.port import Port


_DEFAULT_PORT_CATALOG: list[dict] = [
    {"port_id": "GENOA", "latitude": 44.4056, "longitude": 8.9463, "name": "Genoa", "max_draft_m": 15.0, "aliases": ["genova"], "is_waypoint": False},
    {"port_id": "MARSEILLE", "latitude": 43.2965, "longitude": 5.3698, "name": "Marseille", "max_draft_m": 15.0, "aliases": ["marseilles"], "is_waypoint": False},
    {"port_id": "MALTA", "latitude": 35.8989, "longitude": 14.5146, "name": "Malta", "max_draft_m": 20.0, "aliases": ["valletta", "malta"], "is_waypoint": False},
    {"port_id": "PIRAEUS", "latitude": 37.9420, "longitude": 23.6460, "name": "Piraeus", "max_draft_m": 18.0, "aliases": ["piraeus"], "is_waypoint": False},
    {"port_id": "THESSALONIKI", "latitude": 40.6401, "longitude": 22.9444, "name": "Thessaloniki", "max_draft_m": 17.0, "aliases": ["thessaloniki"], "is_waypoint": False},
    {"port_id": "CANAKKALE", "latitude": 40.1553, "longitude": 26.4142, "name": "Canakkale", "max_draft_m": 15.0, "aliases": ["canakkale"], "is_waypoint": False},
    {"port_id": "ISTANBUL", "latitude": 41.0082, "longitude": 28.9784, "name": "Istanbul", "max_draft_m": 15.0, "aliases": ["istanbul"], "is_waypoint": False},
    {"port_id": "HERAKLION", "latitude": 35.3387, "longitude": 25.1442, "name": "Heraklion", "max_draft_m": 15.0, "aliases": ["heraklion"], "is_waypoint": False},
    {"port_id": "PATRAS", "latitude": 38.2466, "longitude": 21.7346, "name": "Patras", "max_draft_m": 15.0, "aliases": ["patras"], "is_waypoint": False},
    {"port_id": "WP_LIGURIAN_SEA", "latitude": 43.20, "longitude": 9.50, "name": "Ligurian Sea Waypoint", "max_draft_m": None, "aliases": [], "is_waypoint": True},
    {"port_id": "WP_GULF_OF_LION", "latitude": 42.50, "longitude": 6.50, "name": "Gulf of Lion Waypoint", "max_draft_m": None, "aliases": [], "is_waypoint": True},
    {"port_id": "WP_IONIAN_SEA", "latitude": 38.00, "longitude": 19.50, "name": "Ionian Sea Waypoint", "max_draft_m": None, "aliases": [], "is_waypoint": True},
    {"port_id": "WP_STRAIT_OTRANTO", "latitude": 40.00, "longitude": 18.50, "name": "Strait of Otranto Waypoint", "max_draft_m": None, "aliases": [], "is_waypoint": True},
    {"port_id": "WP_SOUTH_PELOPONNESE", "latitude": 36.60, "longitude": 22.80, "name": "South Peloponnese Waypoint", "max_draft_m": None, "aliases": [], "is_waypoint": True},
    {"port_id": "WP_CAPE_MALEAS", "latitude": 36.40, "longitude": 23.30, "name": "Cape Maleas Waypoint", "max_draft_m": None, "aliases": [], "is_waypoint": True},
    {"port_id": "WP_CENTRAL_AEGEAN", "latitude": 38.20, "longitude": 24.20, "name": "Central Aegean Waypoint", "max_draft_m": None, "aliases": [], "is_waypoint": True},
    {"port_id": "WP_NORTH_AEGEAN", "latitude": 39.60, "longitude": 25.40, "name": "North Aegean Waypoint", "max_draft_m": None, "aliases": [], "is_waypoint": True},
]


def _build_port_document(port_data: dict) -> Port:
    return Port(
        port_id=port_data["port_id"],
        latitude=port_data["latitude"],
        longitude=port_data["longitude"],
        name=port_data["name"],
        max_draft_m=port_data.get("max_draft_m"),
        aliases=list(port_data.get("aliases", [])),
        is_waypoint=port_data.get("is_waypoint", False),
    )


def _default_port_documents(only_ports: bool = True) -> List[Port]:
    ports: List[Port] = []
    for port_data in _DEFAULT_PORT_CATALOG:
        if only_ports and port_data.get("is_waypoint", False):
            continue
        ports.append(_build_port_document(port_data))
    return ports

class PortRepository:
    def create(self, port_data: dict) -> Port:
        port = Port(**port_data)
        port.save()
        return port

    def get_by_id(self, port_id: str) -> Optional[Port]:
        port = Port.objects(port_id=port_id).first()
        if port:
            return port

        for candidate in _default_port_documents(only_ports=False):
            if candidate.port_id == port_id:
                return candidate

        return None

    def search(self, query: str) -> List[Port]:
        q = query.strip().lower()
        if not q:
            return self.list_all()

        regex = re.compile(q, re.IGNORECASE)
        # In MongoDB, we can query for any element in the aliases list that matches the regex
        # Or just return everything and filter in Python for smaller sets, but let's use MongoDB
        return list(Port.objects(
            # OR query: (name matches) OR (aliases match)
            # This can be done using the Q operator in mongoengine
        ))

    def list_all(self, only_ports: bool = True) -> List[Port]:
        if Port.objects.count() == 0:
            return _default_port_documents(only_ports=only_ports)

        if only_ports:
            return list(Port.objects(is_waypoint=False))
        return list(Port.objects())

    def upsert_many(self, ports_list: List[dict]):
        for p_data in ports_list:
            port_id = p_data.get("port_id")
            if not port_id:
                continue

            Port.objects(port_id=port_id).update_one(
                set__latitude=p_data.get("latitude"),
                set__longitude=p_data.get("longitude"),
                set__name=p_data.get("name"),
                set__max_draft_m=p_data.get("max_draft_m"),
                set__aliases=p_data.get("aliases", []),
                set__is_waypoint=p_data.get("is_waypoint", False),
                upsert=True
            )

    def resolve_port(self, query: str) -> Optional[Port]:
        """
        Resolve a user-supplied query to a Port.
        Matches port_id, name, or aliases (case-insensitive).
        """
        q = query.strip().lower()

        # 1. Try exact port_id (case-insensitive)
        port = Port.objects(port_id=q.upper()).first()
        if port: return port

        # 2. Try exact name match (case-insensitive)
        port = Port.objects(name=re.compile(f"^{re.escape(q)}$", re.IGNORECASE)).first()
        if port: return port

        # 3. Try aliases (case-insensitive)
        port = Port.objects(aliases=re.compile(f"^{re.escape(q)}$", re.IGNORECASE)).first()
        if port: return port

        for candidate in _default_port_documents(only_ports=False):
            aliases = [alias.lower() for alias in candidate.aliases]
            if (
                candidate.port_id.lower() == q
                or candidate.name.lower() == q
                or q in aliases
            ):
                return candidate

        return None
