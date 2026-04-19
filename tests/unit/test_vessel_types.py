import pytest
from pydantic import ValidationError

from src.models.vessel import VESSEL_TYPE_OPTIONS, VESSEL_TYPES, format_vessel_type_label
from src.schemas.vessel import VesselCreateSchema, VesselUpdateSchema


def test_vessel_type_options_match_model_choices():
    assert [option["value"] for option in VESSEL_TYPE_OPTIONS] == list(VESSEL_TYPES)


def test_vessel_type_label_is_human_readable():
    assert format_vessel_type_label("ro_ro_ship") == "Ro Ro Ship"


def test_vessel_create_rejects_unknown_type():
    with pytest.raises(ValidationError):
        VesselCreateSchema(
            company_id="000000000000000000000001",
            name="Test Vessel",
            imo_number="IMO0000001",
            vessel_type="submarine",
        )


def test_vessel_update_accepts_missing_type():
    vessel = VesselUpdateSchema(name="Updated Vessel")
    assert vessel.vessel_type is None
