import pytest
from bson import ObjectId
from src.models.vessel import Vessel, Tanker, ContainerShip

def test_base_vessel_raises_not_implemented():
    # Създаваме базов кораб само в паметта
    base_vessel = Vessel(
        company_id=ObjectId(),
        name="Base Ship",
        imo_number="IMO1234567",
        vessel_type="bulk_carrier"
    )

    # Проверяваме дали хвърля грешка, ако се опитаме да вземем капацитет от базовия клас
    with pytest.raises(NotImplementedError, match="Subclasses must implement this method"):
        base_vessel.get_capacity_info()

def test_tanker_capacity_info_hazardous():
    tanker = Tanker(
        company_id=ObjectId(),
        name="Black Pearl Oil",
        imo_number="IMO9876543",
        vessel_type="tanker",
        barrels_capacity=500000,
        is_hazardous=True
    )

    expected_info = "Capacity: 500000 barrels (Hazardous)"
    assert tanker.get_capacity_info() == expected_info

def test_tanker_capacity_info_non_hazardous():
    tanker = Tanker(
        company_id=ObjectId(),
        name="Fresh Water Carrier",
        imo_number="IMO5555555",
        vessel_type="tanker",
        barrels_capacity=100000,
        is_hazardous=False
    )

    expected_info = "Capacity: 100000 barrels (Non-hazardous)"
    assert tanker.get_capacity_info() == expected_info

def test_containership_capacity_info():
    container_ship = ContainerShip(
        company_id=ObjectId(),
        name="Ever Given",
        imo_number="IMO1112223",
        vessel_type="container_ship",
        teu_capacity=20000
    )

    expected_info = "Capacity: 20000 TEU"
    assert container_ship.get_capacity_info() == expected_info
