from bson import ObjectId

from src.models.vessel import (
    BulkCarrier,
    CarCarrier,
    ChemicalTanker,
    ContainerShip,
    CruiseShip,
    Dredger,
    Ferry,
    FishingVessel,
    GeneralCargo,
    Icebreaker,
    LNGCarrier,
    LPGCarrier,
    OffshoreSupport,
    PassengerShip,
    PatrolBoat,
    ResearchVessel,
    RoRoShip,
    Tanker,
    Tugboat,
    Yacht,
    Vessel,
)


def test_vessel_factory_returns_subclass_for_known_type():
    vessel = Vessel.build(
        company_id=ObjectId(),
        name="Test LNG",
        imo_number="IMO0000001",
        vessel_type="lng_carrier",
        fuel_consumption_rate=10.0,
    )

    assert isinstance(vessel, LNGCarrier)
    assert vessel.calculate_fuel(100.0) == 1250.0


def test_tanker_fuel_calculation():
    tanker = Tanker(
        company_id=ObjectId(),
        name="Tanker One",
        imo_number="IMO1234567",
        vessel_type="tanker",
        fuel_consumption_rate=10.0,
    )

    assert tanker.calculate_fuel(100.0) == 1200.0


def test_container_ship_fuel_calculation():
    container_ship = ContainerShip(
        company_id=ObjectId(),
        name="Container One",
        imo_number="IMO7654321",
        vessel_type="container_ship",
        fuel_consumption_rate=10.0,
    )

    assert container_ship.calculate_fuel(100.0) == 1100.0


def test_additional_vessel_variant_fuel_calculations():
    variants = [
        (BulkCarrier, "bulk_carrier", 1150.0),
        (PassengerShip, "passenger_ship", 1180.0),
        (Ferry, "ferry", 1120.0),
        (RoRoShip, "ro_ro_ship", 1140.0),
        (LNGCarrier, "lng_carrier", 1250.0),
        (LPGCarrier, "lpg_carrier", 1220.0),
        (ChemicalTanker, "chemical_tanker", 1230.0),
        (CarCarrier, "car_carrier", 1140.0),
        (GeneralCargo, "general_cargo", 1130.0),
        (OffshoreSupport, "offshore_support", 1300.0),
        (ResearchVessel, "research_vessel", 1200.0),
        (Icebreaker, "icebreaker", 1400.0),
        (Tugboat, "tugboat", 1350.0),
        (FishingVessel, "fishing_vessel", 1160.0),
        (CruiseShip, "cruise_ship", 1170.0),
        (Yacht, "yacht", 1080.0),
        (PatrolBoat, "patrol_boat", 1280.0),
        (Dredger, "dredger", 1320.0),
    ]

    for model_cls, vessel_type, expected in variants:
        instance = model_cls(
            company_id=ObjectId(),
            name=f"{vessel_type} One",
            imo_number=f"IMO{vessel_type[:7].upper()}",
            vessel_type=vessel_type,
            fuel_consumption_rate=10.0,
        )
        assert instance.calculate_fuel(100.0) == expected
