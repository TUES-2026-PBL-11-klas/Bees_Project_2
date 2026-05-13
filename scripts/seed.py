import os
import sys
from datetime import datetime

import mongoengine as me

# Add project root to path so imports work
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

me.disconnect_all()

# Use localhost by default, but allow override via environment variable
mongodb_host = os.getenv("MONGODB_HOST", "localhost")
mongodb_port = int(os.getenv("MONGODB_PORT", "27017"))
mongodb_db = os.getenv("DB_NAME", "clearwake")

me.connect(db=mongodb_db, host=mongodb_host, port=mongodb_port)
print(f"Connected to MongoDB at {mongodb_host}:{mongodb_port}/{mongodb_db}")

# Clear existing data to avoid duplicates
print("Clearing existing data...")
me.disconnect_all()
me.connect(db=mongodb_db, host=mongodb_host, port=mongodb_port)

# Drop collections in reverse dependency order
from src.models.event import Event
from src.models.route import Route, Waypoint
from src.models.route_request import RouteRequest
from src.models.zone import Zone
from src.models.vessel import Vessel, VesselSpecs
from src.models.company import Company, ApiKey

Event.drop_collection()
print("  - Events cleared")
Route.drop_collection()
print("  - Routes cleared")
RouteRequest.drop_collection()
print("  - Route requests cleared")
Zone.drop_collection()
print("  - Zones cleared")
Vessel.drop_collection()
print("  - Vessels cleared")
Company.drop_collection()
print("  - Companies cleared")

print("Database cleared. Seeding fresh data...\n")


def point(lon: float, lat: float) -> dict:
    return {"type": "Point", "coordinates": [lon, lat]}


def polygon(coords: list[list[list[float]]]) -> dict:
    return {"type": "Polygon", "coordinates": coords}


companies = {
    "nordic": Company(
        name="Nordic Shipping AS",
        email="admin@nordicshipping.com",
        status="active",
        api_keys=[
            ApiKey(key_hash="abc123hash", label="production"),
            ApiKey(key_hash="abc123hash-dev", label="development"),
        ],
    ).save(),
    "baltic": Company(
        name="Baltic Cargo Lines",
        email="ops@balticcargo.com",
        status="trial",
        api_keys=[
            ApiKey(key_hash="def456hash", label="production"),
        ],
    ).save(),
    "med": Company(
        name="Med Atlantic Transport",
        email="hello@medatlantic.example",
        status="suspended",
        api_keys=[
            ApiKey(key_hash="ghi789hash", label="production"),
            ApiKey(key_hash="ghi789hash-backup", label="backup"),
        ],
    ).save(),
}

for key, company in companies.items():
    print(f"Company saved ({key}): {company.id}")

vessel_seed_data = [
    {
        "slug": "aurora",
        "company_key": "nordic",
        "name": "MV Aurora",
        "imo_number": "IMO9234567",
        "vessel_type": "container_ship",
        "specs": {"max_draft_m": 12.5, "max_speed_knots": 22, "length_m": 300, "beam_m": 45},
        "fuel_consumption_rate": 0.8,
        "current_status": "idle",
        "current_position": point(10.757, 59.912),
    },
    {
        "slug": "fjord",
        "company_key": "nordic",
        "name": "MV Fjord",
        "imo_number": "IMO9234568",
        "vessel_type": "tanker",
        "specs": {"max_draft_m": 14.0, "max_speed_knots": 18, "length_m": 250, "beam_m": 42},
        "fuel_consumption_rate": 1.05,
        "current_status": "en_route",
        "current_position": point(4.9041, 52.3676),
    },
    {
        "slug": "zephyr",
        "company_key": "baltic",
        "name": "MV Zephyr",
        "imo_number": "IMO9234569",
        "vessel_type": "ferry",
        "specs": {"max_draft_m": 8.5, "max_speed_knots": 26, "length_m": 180, "beam_m": 28},
        "fuel_consumption_rate": 0.62,
        "current_status": "docked",
        "current_position": point(2.1734, 41.3851),
    },
    {
        "slug": "horizon",
        "company_key": "med",
        "name": "MV Horizon",
        "imo_number": "IMO9234570",
        "vessel_type": "bulk_carrier",
        "specs": {"max_draft_m": 15.5, "max_speed_knots": 16, "length_m": 290, "beam_m": 48},
        "fuel_consumption_rate": 1.22,
        "current_status": "idle",
        "current_position": point(23.6425, 37.9475),
    },
    {
        "slug": "atlas",
        "company_key": "nordic",
        "name": "MV Atlas",
        "imo_number": "IMO9234571",
        "vessel_type": "ro_ro_ship",
        "specs": {"max_draft_m": 10.5, "max_speed_knots": 21, "length_m": 210, "beam_m": 32},
        "fuel_consumption_rate": 0.74,
        "current_status": "en_route",
        "current_position": point(8.9463, 44.4056),
    },
    {
        "slug": "borealis",
        "company_key": "nordic",
        "name": "MV Borealis",
        "imo_number": "IMO9234572",
        "vessel_type": "lng_carrier",
        "specs": {"max_draft_m": 13.8, "max_speed_knots": 19, "length_m": 285, "beam_m": 43},
        "fuel_consumption_rate": 1.16,
        "current_status": "idle",
        "current_position": point(5.3698, 43.2965),
    },
    {
        "slug": "meridian",
        "company_key": "baltic",
        "name": "MV Meridian",
        "imo_number": "IMO9234573",
        "vessel_type": "lpg_carrier",
        "specs": {"max_draft_m": 13.2, "max_speed_knots": 18, "length_m": 275, "beam_m": 41},
        "fuel_consumption_rate": 1.09,
        "current_status": "docked",
        "current_position": point(4.4777, 51.9244),
    },
    {
        "slug": "solstice",
        "company_key": "baltic",
        "name": "MV Solstice",
        "imo_number": "IMO9234574",
        "vessel_type": "chemical_tanker",
        "specs": {"max_draft_m": 12.9, "max_speed_knots": 17, "length_m": 240, "beam_m": 39},
        "fuel_consumption_rate": 1.18,
        "current_status": "idle",
        "current_position": point(-0.3763, 39.4699),
    },
    {
        "slug": "triton",
        "company_key": "med",
        "name": "MV Triton",
        "imo_number": "IMO9234575",
        "vessel_type": "car_carrier",
        "specs": {"max_draft_m": 11.0, "max_speed_knots": 20, "length_m": 230, "beam_m": 36},
        "fuel_consumption_rate": 0.76,
        "current_status": "en_route",
        "current_position": point(16.8620, 41.1188),
    },
    {
        "slug": "orion",
        "company_key": "med",
        "name": "MV Orion",
        "imo_number": "IMO9234576",
        "vessel_type": "general_cargo",
        "specs": {"max_draft_m": 10.8, "max_speed_knots": 16, "length_m": 205, "beam_m": 33},
        "fuel_consumption_rate": 0.81,
        "current_status": "idle",
        "current_position": point(27.9147, 43.2141),
    },
    {
        "slug": "polaris",
        "company_key": "nordic",
        "name": "MV Polaris",
        "imo_number": "IMO9234577",
        "vessel_type": "offshore_support",
        "specs": {"max_draft_m": 12.0, "max_speed_knots": 15, "length_m": 165, "beam_m": 34},
        "fuel_consumption_rate": 1.35,
        "current_status": "docked",
        "current_position": point(28.6348, 44.1598),
    },
    {
        "slug": "discovery",
        "company_key": "baltic",
        "name": "MV Discovery",
        "imo_number": "IMO9234578",
        "vessel_type": "research_vessel",
        "specs": {"max_draft_m": 9.4, "max_speed_knots": 14, "length_m": 150, "beam_m": 27},
        "fuel_consumption_rate": 0.68,
        "current_status": "idle",
        "current_position": point(30.7233, 46.4825),
    },
    {
        "slug": "valkyrie",
        "company_key": "med",
        "name": "MV Valkyrie",
        "imo_number": "IMO9234579",
        "vessel_type": "icebreaker",
        "specs": {"max_draft_m": 11.2, "max_speed_knots": 18, "length_m": 160, "beam_m": 30},
        "fuel_consumption_rate": 1.42,
        "current_status": "en_route",
        "current_position": point(37.7686, 44.7234),
    },
    {
        "slug": "sentinel",
        "company_key": "med",
        "name": "MV Sentinel",
        "imo_number": "IMO9234580",
        "vessel_type": "tugboat",
        "specs": {"max_draft_m": 8.1, "max_speed_knots": 13, "length_m": 65, "beam_m": 16},
        "fuel_consumption_rate": 1.31,
        "current_status": "docked",
        "current_position": point(41.6367, 41.6168),
    },
    {
        "slug": "seafarer",
        "company_key": "nordic",
        "name": "MV Seafarer",
        "imo_number": "IMO9234581",
        "vessel_type": "fishing_vessel",
        "specs": {"max_draft_m": 7.2, "max_speed_knots": 12, "length_m": 55, "beam_m": 14},
        "fuel_consumption_rate": 0.54,
        "current_status": "idle",
        "current_position": point(33.5254, 44.6054),
    },
    {
        "slug": "odyssey",
        "company_key": "baltic",
        "name": "MV Odyssey",
        "imo_number": "IMO9234582",
        "vessel_type": "cruise_ship",
        "specs": {"max_draft_m": 10.9, "max_speed_knots": 24, "length_m": 315, "beam_m": 38},
        "fuel_consumption_rate": 1.25,
        "current_status": "en_route",
        "current_position": point(27.4728, 42.4975),
    },
    {
        "slug": "aster",
        "company_key": "med",
        "name": "MV Aster",
        "imo_number": "IMO9234583",
        "vessel_type": "yacht",
        "specs": {"max_draft_m": 4.5, "max_speed_knots": 28, "length_m": 52, "beam_m": 11},
        "fuel_consumption_rate": 0.31,
        "current_status": "idle",
        "current_position": point(14.5189, 35.9042),
    },
    {
        "slug": "guardian",
        "company_key": "nordic",
        "name": "MV Guardian",
        "imo_number": "IMO9234584",
        "vessel_type": "patrol_boat",
        "specs": {"max_draft_m": 5.8, "max_speed_knots": 32, "length_m": 38, "beam_m": 9},
        "fuel_consumption_rate": 0.47,
        "current_status": "docked",
        "current_position": point(4.4792, 51.9225),
    },
    {
        "slug": "harvester",
        "company_key": "baltic",
        "name": "MV Harvester",
        "imo_number": "IMO9234585",
        "vessel_type": "dredger",
        "specs": {"max_draft_m": 9.8, "max_speed_knots": 11, "length_m": 92, "beam_m": 19},
        "fuel_consumption_rate": 1.48,
        "current_status": "idle",
        "current_position": point(13.7768, 45.6495),
    },
    {
        "slug": "voyager",
        "company_key": "med",
        "name": "MV Voyager",
        "imo_number": "IMO9234586",
        "vessel_type": "passenger_ship",
        "specs": {"max_draft_m": 11.5, "max_speed_knots": 23, "length_m": 240, "beam_m": 34},
        "fuel_consumption_rate": 0.97,
        "current_status": "en_route",
        "current_position": point(-5.3536, 36.1408),
    },
    {
        "slug": "nomad",
        "company_key": "nordic",
        "name": "MV Nomad",
        "imo_number": "IMO9234587",
        "vessel_type": "container_ship",
        "specs": {"max_draft_m": 12.0, "max_speed_knots": 21, "length_m": 290, "beam_m": 44},
        "fuel_consumption_rate": 0.83,
        "current_status": "idle",
        "current_position": point(12.3155, 45.4408),
    },
]

vessels = {}
for vessel_data in vessel_seed_data:
    vessel = Vessel(
        company_id=companies[vessel_data["company_key"]].id,
        name=vessel_data["name"],
        imo_number=vessel_data["imo_number"],
        vessel_type=vessel_data["vessel_type"],
        specs=VesselSpecs(**vessel_data["specs"]),
        fuel_consumption_rate=vessel_data["fuel_consumption_rate"],
        current_status=vessel_data["current_status"],
        current_position=vessel_data["current_position"],
    ).save()
    vessels[vessel_data["slug"]] = vessel
    print(f"Vessel saved ({vessel_data['slug']}): {vessel.id}")

zones = {
    "north_sea": Zone(
        name="North Sea Eco Zone",
        zone_type="eco",
        status="active",
        geometry=polygon([[
            [3.0, 51.0],
            [8.0, 51.0],
            [8.0, 56.0],
            [3.0, 56.0],
            [3.0, 51.0],
        ]]),
        description="Emissions-restricted zone",
        valid_from=datetime(2025, 1, 1),
    ).save(),
    "bosporus": Zone(
        name="Bosporus Conflict Zone",
        zone_type="conflict",
        status="inactive",
        geometry=polygon([[
            [28.5, 40.8],
            [29.8, 40.8],
            [29.8, 41.5],
            [28.5, 41.5],
            [28.5, 40.8],
        ]]),
        description="High traffic and restricted area",
        valid_from=datetime(2025, 2, 1),
        valid_until=datetime(2025, 12, 31),
    ).save(),
    "gibraltar": Zone(
        name="Gibraltar Temporary Zone",
        zone_type="temporary",
        status="active",
        geometry=polygon([[
            [-6.0, 35.9],
            [-5.0, 35.9],
            [-5.0, 36.4],
            [-6.0, 36.4],
            [-6.0, 35.9],
        ]]),
        description="Temporary traffic advisory",
        valid_from=datetime(2025, 3, 15),
    ).save(),
    "suez": Zone(
        name="Suez Canal Zone",
        zone_type="canal",
        status="active",
        geometry=polygon([[
            [31.5, 29.5],
            [33.0, 29.5],
            [33.0, 31.5],
            [31.5, 31.5],
            [31.5, 29.5],
        ]]),
        description="Canal corridor",
        valid_from=datetime(2025, 1, 1),
    ).save(),
}

for key, zone in zones.items():
    print(f"Zone saved ({key}): {zone.id}")

route_requests = {
    "rotterdam_hamburg": RouteRequest(
        company_id=companies["nordic"].id,
        vessel_id=vessels["aurora"].id,
        origin=point(4.4777, 51.9244),
        destination=point(9.9937, 53.5511),
        optimization_mode="eco",
        status="completed",
    ).save(),
    "genoa_marseille": RouteRequest(
        company_id=companies["nordic"].id,
        vessel_id=vessels["fjord"].id,
        origin=point(8.9463, 44.4056),
        destination=point(5.3698, 43.2965),
        optimization_mode="fastest",
        status="completed",
    ).save(),
    "barcelona_valencia": RouteRequest(
        company_id=companies["baltic"].id,
        vessel_id=vessels["zephyr"].id,
        origin=point(2.1734, 41.3851),
        destination=point(-0.3763, 39.4699),
        optimization_mode="eco",
        status="completed",
    ).save(),
    "piraeus_bari": RouteRequest(
        company_id=companies["med"].id,
        vessel_id=vessels["horizon"].id,
        origin=point(23.6425, 37.9475),
        destination=point(16.8620, 41.1188),
        optimization_mode="fastest",
        status="pending",
    ).save(),
}

for key, req in route_requests.items():
    print(f"RouteRequest saved ({key}): {req.id}")

routes = {
    "rotterdam_hamburg": Route(
        request_id=route_requests["rotterdam_hamburg"].id,
        company_id=companies["nordic"].id,
        vessel_id=vessels["aurora"].id,
        optimization_mode="eco",
        total_distance_nm=312.5,
        estimated_duration_h=18.0,
        estimated_fuel_tons=250.0,
        waypoints=[
            Waypoint(sequence=1, coordinates=[4.4777, 51.9244], point_type="port", name="Rotterdam"),
            Waypoint(sequence=2, coordinates=[6.5, 52.8], point_type="waypoint"),
            Waypoint(sequence=3, coordinates=[9.9937, 53.5511], point_type="port", name="Hamburg"),
        ],
    ).save(),
    "genoa_marseille": Route(
        request_id=route_requests["genoa_marseille"].id,
        company_id=companies["nordic"].id,
        vessel_id=vessels["fjord"].id,
        optimization_mode="fastest",
        total_distance_nm=114.2,
        estimated_duration_h=6.4,
        estimated_fuel_tons=120.8,
        waypoints=[
            Waypoint(sequence=1, coordinates=[8.9463, 44.4056], point_type="port", name="Genoa"),
            Waypoint(sequence=2, coordinates=[7.1, 43.9], point_type="waypoint"),
            Waypoint(sequence=3, coordinates=[5.3698, 43.2965], point_type="port", name="Marseille"),
        ],
    ).save(),
    "barcelona_valencia": Route(
        request_id=route_requests["barcelona_valencia"].id,
        company_id=companies["baltic"].id,
        vessel_id=vessels["zephyr"].id,
        optimization_mode="eco",
        total_distance_nm=136.0,
        estimated_duration_h=7.1,
        estimated_fuel_tons=84.2,
        waypoints=[
            Waypoint(sequence=1, coordinates=[2.1734, 41.3851], point_type="port", name="Barcelona"),
            Waypoint(sequence=2, coordinates=[1.2, 40.7], point_type="waypoint"),
            Waypoint(sequence=3, coordinates=[-0.3763, 39.4699], point_type="port", name="Valencia"),
        ],
    ).save(),
}

for key, route in routes.items():
    print(f"Route saved ({key}): {route.id}")

events = [
    Event(
        event_type="zone_closed",
        zone_id=zones["north_sea"].id,
        affected_routes=[routes["rotterdam_hamburg"].id],
        payload={"reason": "storm warning", "severity": "high"},
        status="pending",
    ).save(),
    Event(
        event_type="storm",
        affected_routes=[routes["genoa_marseille"].id],
        payload={"wind_speed_knots": 42, "wave_height_m": 4.5},
        status="dispatched",
    ).save(),
    Event(
        event_type="canal_blocked",
        zone_id=zones["suez"].id,
        affected_routes=[],
        payload={"reason": "maintenance", "expected_delay_hours": 8},
        status="pending",
    ).save(),
    Event(
        event_type="zone_opened",
        zone_id=zones["bosporus"].id,
        affected_routes=[routes["barcelona_valencia"].id],
        payload={"reason": "restrictions lifted"},
        status="resolved",
    ).save(),
]

for index, event in enumerate(events, start=1):
    print(f"Event saved ({index}): {event.id}")

print("\nSeeding complete.")
print(f"Companies: {Company.objects.count()}")
print(f"Vessels: {Vessel.objects.count()}")
print(f"Zones: {Zone.objects.count()}")
print(f"Route requests: {RouteRequest.objects.count()}")
print(f"Routes: {Route.objects.count()}")
print(f"Events: {Event.objects.count()}")
