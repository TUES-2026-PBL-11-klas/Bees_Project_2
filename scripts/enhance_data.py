#!/usr/bin/env python3
"""Enhance database with additional sample data for ClearWake Logistics."""

import sys
sys.path.insert(0, '/app')

from datetime import datetime, timedelta, timezone
from mongoengine import connect, disconnect
from src.core.config import settings

connect(db=settings.DB_NAME, host=settings.MONGODB_URI)

from src.models.company import Company
from src.models.vessel import Vessel, VesselSpecs
from src.models.zone import Zone
from src.models.event import Event
from src.models.audit_log import AuditLog
from src.models.route import Route, RouteRequest, Waypoint

def get_or_create_company():
    """Get ClearWake Logistics company or create it."""
    company = Company.objects(email="ops@clearwake.demo").first()
    if not company:
        company = Company(
            name="ClearWake Logistics",
            email="ops@clearwake.demo",
            status="active",
        ).save()
        print(f"Created company: {company.email}")
    else:
        print(f"Using existing company: {company.email}")
    return company

def create_additional_vessels(company_id):
    """Add more vessels to the fleet."""
    vessels_data = [
        {
            "name": "CW Pioneer",
            "imo_number": "9456123",
            "vessel_type": "general_cargo",
            "fuel_consumption_rate": 0.065,
            "current_status": "en_route",
            "specs": {
                "max_draft_m": 11.5,
                "max_speed_knots": 16.0,
                "length_m": 180.0,
                "beam_m": 28.0,
            },
        },
        {
            "name": "CW Navigator",
            "imo_number": "9567234",
            "vessel_type": "container_ship",
            "fuel_consumption_rate": 0.078,
            "current_status": "docked",
            "specs": {
                "max_draft_m": 13.8,
                "max_speed_knots": 21.0,
                "length_m": 260.0,
                "beam_m": 30.0,
            },
        },
        {
            "name": "CW Explorer",
            "imo_number": "9678345",
            "vessel_type": "research_vessel",
            "fuel_consumption_rate": 0.055,
            "current_status": "idle",
            "specs": {
                "max_draft_m": 8.5,
                "max_speed_knots": 14.0,
                "length_m": 120.0,
                "beam_m": 20.0,
            },
        },
        {
            "name": "CW Titan",
            "imo_number": "9789456",
            "vessel_type": "bulk_carrier",
            "fuel_consumption_rate": 0.092,
            "current_status": "en_route",
            "specs": {
                "max_draft_m": 16.0,
                "max_speed_knots": 15.0,
                "length_m": 240.0,
                "beam_m": 38.0,
            },
        },
        {
            "name": "CW Express",
            "imo_number": "9890567",
            "vessel_type": "ferry",
            "fuel_consumption_rate": 0.048,
            "current_status": "en_route",
            "specs": {
                "max_draft_m": 7.2,
                "max_speed_knots": 28.0,
                "length_m": 145.0,
                "beam_m": 24.0,
            },
        },
    ]

    created = 0
    for data in vessels_data:
        existing = Vessel.objects(imo_number=data["imo_number"]).first()
        if not existing:
            specs = VesselSpecs(**data["specs"])
            Vessel(
                company_id=company_id,
                name=data["name"],
                imo_number=data["imo_number"],
                vessel_type=data["vessel_type"],
                specs=specs,
                fuel_consumption_rate=data["fuel_consumption_rate"],
                current_status=data["current_status"],
            ).save()
            created += 1

    print(f"Added {created} new vessels")
    return created

def create_additional_zones():
    """Add more maritime zones."""
    zones_data = [
        {
            "name": "Gibraltar Traffic Separation Scheme",
            "zone_type": "temporary",
            "status": "active",
            "description": "High-traffic shipping lane at Gibraltar Strait",
            "geometry": {
                "type": "Polygon",
                "coordinates": [[
                    [-5.6, 35.9],
                    [-5.2, 35.9],
                    [-5.2, 36.2],
                    [-5.6, 36.2],
                    [-5.6, 35.9],
                ]],
            },
        },
        {
            "name": "Malta Freeport Area",
            "zone_type": "port",
            "status": "active",
            "description": "Major transshipment hub in Mediterranean",
            "geometry": {
                "type": "Polygon",
                "coordinates": [[
                    [14.48, 35.87],
                    [14.54, 35.87],
                    [14.54, 35.93],
                    [14.48, 35.93],
                    [14.48, 35.87],
                ]],
            },
        },
        {
            "name": "Adriatic Shipping Lane",
            "zone_type": "eco",
            "status": "active",
            "description": "Protected shipping corridor with emissions restrictions",
            "geometry": {
                "type": "Polygon",
                "coordinates": [[
                    [13.5, 43.5],
                    [15.5, 43.5],
                    [15.5, 45.5],
                    [13.5, 45.5],
                    [13.5, 43.5],
                ]],
            },
        },
        {
            "name": "Aegean Island Hopping Route",
            "zone_type": "temporary",
            "status": "active",
            "description": "Seasonal high-traffic ferry route",
            "geometry": {
                "type": "Polygon",
                "coordinates": [[
                    [24.5, 35.0],
                    [26.5, 35.0],
                    [26.5, 38.0],
                    [24.5, 38.0],
                    [24.5, 35.0],
                ]],
            },
        },
        {
            "name": "Strait of Sicily Corridor",
            "zone_type": "canal",
            "status": "active",
            "description": "Key passage between eastern and western Mediterranean",
            "geometry": {
                "type": "Polygon",
                "coordinates": [[
                    [12.0, 35.5],
                    [14.5, 35.5],
                    [14.5, 37.5],
                    [12.0, 37.5],
                    [12.0, 35.5],
                ]],
            },
        },
    ]

    created = 0
    for data in zones_data:
        existing = Zone.objects(name=data["name"]).first()
        if not existing:
            Zone(
                name=data["name"],
                zone_type=data["zone_type"],
                status=data["status"],
                description=data.get("description"),
                geometry=data["geometry"],
            ).save()
            created += 1

    print(f"Added {created} new zones")
    return created

def create_events(company_id):
    """Create sample events for monitoring."""
    now = datetime.now(timezone.utc)

    events_data = [
        {
            "event_type": "zone_opened",
            "description": "Bosporus zone reopened after maintenance",
        },
        {
            "event_type": "storm",
            "description": "Severe weather warning in Adriatic Sea",
        },
        {
            "event_type": "canal_blocked",
            "description": "Temporary restriction in Suez Canal northbound",
        },
        {
            "event_type": "zone_closed",
            "description": "Eco zone temporarily closed for inspection",
        },
    ]

    created = 0
    zones = list(Zone.objects.all()[:4])

    for i, data in enumerate(events_data):
        event = Event(
            event_type=data["event_type"],
            zone_id=zones[i % len(zones)].id if zones else None,
            affected_routes=[],
            payload={"reason": data["description"], "severity": "medium"},
            status=["pending", "dispatched", "resolved", "pending"][i % 4],
            created_at=now - timedelta(hours=i * 6),
        )
        event.save()
        created += 1

    print(f"Created {created} events")
    return created

def create_sample_routes(company_id):
    """Create sample route requests and calculated routes."""
    vessels = list(Vessel.objects(company_id=company_id)[:5])

    if not vessels:
        print("No vessels found for route creation")
        return 0

    routes_data = [
        {
            "origin": {"port_id": "VARNA", "coordinates": [27.9147, 43.2141]},
            "destination": {"port_id": "ISTANBUL", "coordinates": [28.9784, 41.0082]},
            "optimization_mode": "fastest",
        },
        {
            "origin": {"port_id": "PIRAEUS", "coordinates": [23.6425, 37.9475]},
            "destination": {"port_id": "LIMASSOL", "coordinates": [33.042, 34.6747]},
            "optimization_mode": "fuel_efficient",
        },
        {
            "origin": {"port_id": "GENOA", "coordinates": [8.9463, 44.4056]},
            "destination": {"port_id": "BARCELONA", "coordinates": [2.1734, 41.3851]},
            "optimization_mode": "balanced",
        },
        {
            "origin": {"port_id": "ROTTERDAM", "coordinates": [4.4792, 51.9225]},
            "destination": {"port_id": "HAMBURG", "coordinates": [9.9937, 53.5511]},
            "optimization_mode": "fastest",
        },
    ]

    created = 0
    for data in routes_data:
        request = RouteRequest(
            company_id=company_id,
            vessel_id=vessels[created % len(vessels)].id if vessels else None,
            origin_port=data["origin"]["port_id"],
            destination_port=data["destination"]["port_id"],
            optimization_mode=data["optimization_mode"],
        )
        request.save()

        route = Route(
            request_id=request.id,
            company_id=company_id,
            vessel_id=vessels[created % len(vessels)].id if vessels else None,
            optimization_mode=data["optimization_mode"],
            is_valid=True,
            total_distance_nm=150.0 + (created * 50),
            estimated_time_hours=12.0 + (created * 3),
            estimated_fuel_tons=25.0 + (created * 8),
        )

        origin = data["origin"]["coordinates"]
        dest = data["destination"]["coordinates"]
        route.waypoints = [
            Waypoint(sequence=0, coordinates=origin, point_type="origin"),
            Waypoint(sequence=1, coordinates=dest, point_type="destination"),
        ]

        route.save()
        created += 1

    print(f"Created {created} sample routes")
    return created

def create_audit_entries():
    """Create audit log entries for tracking."""
    now = datetime.now(timezone.utc)

    audit_data = [
        {"event_type": "system_startup", "action": "executed", "entity_type": "system"},
        {"event_type": "data_enhancement", "action": "executed", "entity_type": "database"},
        {"event_type": "vessel_added", "action": "created", "entity_type": "vessel"},
        {"event_type": "zone_added", "action": "created", "entity_type": "zone"},
    ]

    for data in audit_data:
        AuditLog(
            event_type=data["event_type"],
            entity_type=data["entity_type"],
            action=data["action"],
            changed_by="data-enhancement-script",
            details={"source": "enhance_data.py", "timestamp": str(now)},
        ).save()

    print(f"Created {len(audit_data)} audit log entries")

def print_summary():
    """Print database summary."""
    print("\n" + "=" * 50)
    print("DATABASE SUMMARY")
    print("=" * 50)
    print(f"Companies:    {Company.objects.count()}")
    print(f"Vessels:      {Vessel.objects.count()}")
    print(f"Zones:        {Zone.objects.count()}")
    print(f"Routes:       {Route.objects.count()}")
    print(f"Events:       {Event.objects.count()}")
    print(f"Audit Logs:   {AuditLog.count()}")
    print("=" * 50)

if __name__ == "__main__":
    try:
        print("Starting data enhancement...")

        # Get or create company
        company = get_or_create_company()

        # Add data
        create_additional_vessels(company.id)
        create_additional_zones()
        create_events(company.id)
        create_sample_routes(company.id)
        create_audit_entries()

        # Print summary
        print_summary()

    finally:
        disconnect()
