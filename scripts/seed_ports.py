import logging
import random
from src.infrastructure.repositories.port_repository import PortRepository
from src.infrastructure.database.database import init_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Base ports for key hubs
HUB_PORTS = [
    dict(port_id="VARNA", lat=43.2141, lon=27.9147, name="Varna", draft=14.0, aliases=("varna",)),
    dict(port_id="SUEZ", lat=29.9668, lon=32.5498, name="Suez", draft=20.1, aliases=("suez", "suez canal")),
    dict(port_id="SINGAPORE", lat=1.29027, lon=103.85195, name="Singapore", draft=20.0, aliases=("singapore",)),
    dict(port_id="SHANGHAI", la=31.2304, lon=121.4737, name="Shanghai", draft=15.0, aliases=("shanghai",)),
    dict(port_id="NEW_YORK", lat=40.7128, lon=-74.0060, name="New York", draft=14.0, aliases=("new york", "nyc")),
    dict(port_id="ROTTERDAM", lat=51.9225, lon=4.4792, name="Rotterdam", draft=24.0, aliases=("rotterdam",)),
    dict(port_id="SANTOS", lat=-23.9608, lon=-46.3345, name="Santos", draft=15.0, aliases=("santos", "brazil")),
    dict(port_id="CAPE_TOWN", lat=-33.9249, lon=18.4241, name="Cape Town", draft=13.0, aliases=("cape town",)),
    dict(port_id="SYDNEY", lat=-33.8688, lon=151.2093, name="Sydney", draft=14.0, aliases=("sydney",)),
    dict(port_id="TOKYO", lat=35.6762, lon=139.6503, name="Tokyo", draft=16.0, aliases=("tokyo",)),
    dict(port_id="MUMBAI", lat=19.0760, lon=72.8777, name="Mumbai", draft=14.0, aliases=("mumbai",)),
]

def generate_dummy_ports(count=1000):
    """Generates a set of dummy ports distributed across the globe for testing."""
    dummy_ports = []
    for i in range(count):
        lat = random.uniform(-60, 60)
        lon = random.uniform(-180, 180)
        p_id = f"PORT_{i:04d}"
        dummy_ports.append({
            "port_id": p_id,
            "lat": lat,
            "lon": lon,
            "name": f"Dummy Port {i}",
            "draft": random.uniform(10, 20),
            "aliases": (f"dummy_{i}",),
            "is_waypoint": False
        })
    return dummy_ports

def seed_ports():
    init_db()
    repo = PortRepository()

    all_ports = []

    # 1. Add hubs
    for p in HUB_PORTS:
        # Fix potential 'la' vs 'lat'
        lat = p.get("lat") or p.get("la")
        all_ports.append({
            "port_id": p["port_id"],
            "latitude": lat,
            "longitude": p["lon"],
            "name": p["name"],
            "max_draft_m": p["draft"],
            "aliases": list(p["aliases"]),
            "is_waypoint": False
        })

    # 2. Add 1000 dummy ports
    dummies = generate_dummy_ports(1000)
    for d in dummies:
        all_ports.append({
            "port_id": d["port_id"],
            "latitude": d["lat"],
            "longitude": d["lon"],
            "name": d["name"],
            "max_draft_m": d["draft"],
            "aliases": list(d["aliases"]),
            "is_waypoint": False
        })

    # 3. Add Waypoints (Global Mesh)
    # We create a grid of waypoints across the ocean to ensure connectivity
    waypoints = []
    for lat in range(-60, 61, 10):
        for lon in range(-180, 181, 20):
            w_id = f"WP_G_{lat}_{lon}"
            waypoints.append({
                "port_id": w_id,
                "latitude": float(lat),
                "longitude": float(lon),
                "name": f"Global Waypoint {lat},{lon}",
                "max_draft_m": None,
                "aliases": [],
                "is_waypoint": True
            })

    all_ports.extend(waypoints)
    repo.upsert_many(all_ports)
    logger.info(f"Successfully seeded {len(all_ports)} ports/waypoints.")

if __name__ == "__main__":
    seed_ports()
