from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit, urlunsplit
from typing import Optional

import mongoengine as me
from mongoengine.connection import get_connection

from src.core.config import settings
from src.models.audit_log import AuditLog
from src.models.company import Company
from src.models.event import Event
from src.models.route import Route
from src.models.vessel import Vessel, VesselSpecs
from src.models.zone import Zone


def _swap_host(uri: str, new_host: str) -> str:
    parts = urlsplit(uri)
    netloc = parts.netloc

    if "@" in netloc:
        userinfo, hostport = netloc.rsplit("@", 1)
    else:
        userinfo, hostport = "", netloc

    host, sep, port = hostport.partition(":")
    replaced_hostport = f"{new_host}{sep}{port}" if sep else new_host
    replaced_netloc = f"{userinfo}@{replaced_hostport}" if userinfo else replaced_hostport

    return urlunsplit((parts.scheme, replaced_netloc, parts.path, parts.query, parts.fragment))


def _connection_candidates(uri: str) -> list[str]:
    candidates = [uri]

    parsed = urlsplit(uri)
    hostport = parsed.netloc.rsplit("@", 1)[-1]
    host = hostport.partition(":")[0]

    if host == "mongo":
        candidates.append(_swap_host(uri, "localhost"))
    elif host == "localhost":
        candidates.append(_swap_host(uri, "mongo"))

    unique_candidates: list[str] = []
    for candidate in candidates:
        if candidate not in unique_candidates:
            unique_candidates.append(candidate)
    return unique_candidates


def connect_db() -> str:
    last_error: Optional[Exception] = None

    for uri in _connection_candidates(settings.MONGODB_URI):
        try:
            me.disconnect(alias="default")
            me.connect(
                db=settings.DB_NAME,
                host=uri,
                alias="default",
                serverSelectionTimeoutMS=3000,
            )
            get_connection(alias="default").admin.command("ping")
            return uri
        except Exception as exc:  # pragma: no cover - best effort fallback
            last_error = exc

    raise RuntimeError(
        f"Could not connect to MongoDB for database '{settings.DB_NAME}'. "
        f"Last error: {last_error}"
    )


def ensure_indexes() -> None:
    for model in (Company, Vessel, Zone, Route, Event, AuditLog):
        model.ensure_indexes()


def upsert_company() -> tuple[Company, str]:
    email = "ops@clearwake.demo"
    company = Company.objects(email=email).first()

    if company is None:
        company = Company(
            name="ClearWake Logistics",
            email=email,
            status="active",
        ).save()
        return company, "created"

    company.name = "ClearWake Logistics"
    company.status = "active"
    company.save()
    return company, "updated"


def upsert_vessels(company_id) -> dict[str, int]:
    created = 0
    updated = 0

    seeds = [
        {
            "name": "CW Atlas",
            "imo_number": "9303805",
            "vessel_type": "container_ship",
            "fuel_consumption_rate": 0.085,
            "current_status": "idle",
            "specs": {
                "max_draft_m": 14.5,
                "max_speed_knots": 22.0,
                "length_m": 294.0,
                "beam_m": 32.2,
            },
        },
        {
            "name": "CW Aurora",
            "imo_number": "9811000",
            "vessel_type": "tanker",
            "fuel_consumption_rate": 0.11,
            "current_status": "docked",
            "specs": {
                "max_draft_m": 16.2,
                "max_speed_knots": 16.5,
                "length_m": 250.0,
                "beam_m": 44.0,
            },
        },
        {
            "name": "CW Horizon",
            "imo_number": "9743109",
            "vessel_type": "bulk_carrier",
            "fuel_consumption_rate": 0.095,
            "current_status": "en_route",
            "specs": {
                "max_draft_m": 15.8,
                "max_speed_knots": 14.5,
                "length_m": 225.0,
                "beam_m": 36.0,
            },
        },
    ]

    for seed in seeds:
        vessel = Vessel.objects(imo_number=seed["imo_number"]).first()
        specs = VesselSpecs(**seed["specs"])

        if vessel is None:
            payload = {
                "company_id": company_id,
                "name": seed["name"],
                "imo_number": seed["imo_number"],
                "vessel_type": seed["vessel_type"],
                "specs": specs,
                "fuel_consumption_rate": seed["fuel_consumption_rate"],
                "current_status": seed["current_status"],
            }
            Vessel.build(**payload).save()
            created += 1
            continue

        vessel.company_id = company_id
        vessel.name = seed["name"]
        vessel.vessel_type = seed["vessel_type"]
        vessel.specs = specs
        vessel.fuel_consumption_rate = seed["fuel_consumption_rate"]
        vessel.current_status = seed["current_status"]
        vessel.save()
        updated += 1

    return {"created": created, "updated": updated}


def upsert_zones() -> dict[str, int]:
    created = 0
    updated = 0

    now = datetime.now(timezone.utc)

    seeds = [
        {
            "name": "Suez Canal Control Area",
            "zone_type": "canal",
            "status": "active",
            "description": "Operational constraints in the Suez canal passage.",
            "geometry": {
                "type": "Polygon",
                "coordinates": [[
                    [32.14, 30.12],
                    [32.72, 30.12],
                    [32.72, 31.18],
                    [32.14, 31.18],
                    [32.14, 30.12],
                ]],
            },
        },
        {
            "name": "Bosporus Traffic Zone",
            "zone_type": "temporary",
            "status": "active",
            "description": "Temporary high-traffic safety zone around Bosporus.",
            "valid_from": now,
            "valid_until": now + timedelta(days=14),
            "geometry": {
                "type": "Polygon",
                "coordinates": [[
                    [28.90, 40.93],
                    [29.36, 40.93],
                    [29.36, 41.30],
                    [28.90, 41.30],
                    [28.90, 40.93],
                ]],
            },
        },
        {
            "name": "Black Sea Eco Protection Zone",
            "zone_type": "eco",
            "status": "active",
            "description": "Ecological protection area with speed and emissions limits.",
            "geometry": {
                "type": "Polygon",
                "coordinates": [[
                    [30.20, 43.80],
                    [31.80, 43.80],
                    [31.80, 44.80],
                    [30.20, 44.80],
                    [30.20, 43.80],
                ]],
            },
        },
    ]

    for seed in seeds:
        zone = Zone.objects(name=seed["name"]).first()

        if zone is None:
            Zone(**seed).save()
            created += 1
            continue

        zone.zone_type = seed["zone_type"]
        zone.status = seed["status"]
        zone.description = seed.get("description")
        zone.geometry = seed["geometry"]
        zone.valid_from = seed.get("valid_from")
        zone.valid_until = seed.get("valid_until")
        zone.save()
        updated += 1

    return {"created": created, "updated": updated}


def create_bootstrap_audit_log() -> None:
    AuditLog(
        event_type="database_bootstrap",
        entity_type="event",
        action="created",
        changed_by="bootstrap-script",
        details={"db": settings.DB_NAME},
    ).save()


def run_seed() -> None:
    company, company_state = upsert_company()
    vessel_stats = upsert_vessels(company.id)
    zone_stats = upsert_zones()
    create_bootstrap_audit_log()

    print("Seed complete")
    print(f"  Company: {company_state} ({company.email})")
    print(
        "  Vessels: "
        f"created={vessel_stats['created']} updated={vessel_stats['updated']}"
    )
    print(
        "  Zones: "
        f"created={zone_stats['created']} updated={zone_stats['updated']}"
    )


def print_collection_counts() -> None:
    print("Collection counts")
    print(f"  companies: {Company.objects.count()}")
    print(f"  vessels: {Vessel.objects.count()}")
    print(f"  zones: {Zone.objects.count()}")
    print(f"  routes: {Route.objects.count()}")
    print(f"  events: {Event.objects.count()}")
    print(f"  audit_logs: {AuditLog.objects.count()}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bootstrap ClearWake MongoDB database")
    parser.add_argument(
        "--no-seed",
        action="store_true",
        help="Create collections/indexes only, without seed data",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    uri = connect_db()
    print(f"Connected to MongoDB: {uri} / db={settings.DB_NAME}")

    ensure_indexes()

    if not args.no_seed:
        run_seed()

    print_collection_counts()
    me.disconnect(alias="default")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
