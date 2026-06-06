"""Unit tests for the dynamic weather-zone generator."""

from __future__ import annotations

import pytest
import mongomock
import mongoengine

from src.core.services.weather_zone_service import (
    AUTO_STORM_NAME_PREFIX,
    WeatherZoneService,
    exceeds_storm_threshold,
)
from src.models.zone import Zone


# Common bbox used by the test samples.
EAST_MED_BBOX = {
    "min_lat": 30.0, "max_lat": 37.5,
    "min_lon": 16.0, "max_lon": 36.0,
}


@pytest.fixture(scope="module", autouse=True)
def mock_db():
    mongoengine.disconnect_all()
    mongoengine.connect(
        "testdb_weather_zones",
        host="mongodb://localhost",
        mongo_client_class=mongomock.MongoClient,
        uuidRepresentation="standard",
    )
    yield
    mongoengine.disconnect_all()


@pytest.fixture(autouse=True)
def clean_zones():
    Zone.drop_collection()


def _calm_sample(region_id: str = "east_med") -> dict:
    return {
        "region_id": region_id,
        "region_name": "East Mediterranean",
        "bbox": EAST_MED_BBOX,
        "wave_height": 0.8,
        "wind_speed_10m": 5.0,
    }


def _storm_sample(region_id: str = "east_med", *, wave: float = 6.0, wind: float = 12.0) -> dict:
    return {
        "region_id": region_id,
        "region_name": "East Mediterranean",
        "bbox": EAST_MED_BBOX,
        "wave_height": wave,
        "wind_speed_10m": wind,
    }


class TestThreshold:
    def test_wave_height_above_default_is_storm(self):
        assert exceeds_storm_threshold({"wave_height": 4.5}) is True

    def test_wind_speed_above_default_is_storm(self):
        assert exceeds_storm_threshold({"wind_speed_10m": 25.0}) is True

    def test_calm_sample_is_not_storm(self):
        assert exceeds_storm_threshold({"wave_height": 1.0, "wind_speed_10m": 5.0}) is False

    def test_missing_fields_default_to_calm(self):
        assert exceeds_storm_threshold({}) is False

    def test_custom_thresholds_are_honoured(self):
        sample = {"wave_height": 2.0}
        assert exceeds_storm_threshold(sample, wave_height_threshold_m=5.0) is False
        assert exceeds_storm_threshold(sample, wave_height_threshold_m=1.5) is True


class TestRefreshCreates:
    def test_storm_sample_creates_zone(self):
        svc = WeatherZoneService()
        summary = svc.refresh([_storm_sample("east_med")])
        assert summary["created"] == ["east_med"]
        zones = list(Zone.objects(name=f"{AUTO_STORM_NAME_PREFIX}east_med"))
        assert len(zones) == 1
        z = zones[0]
        assert z.zone_type == "temporary"
        assert z.status == "active"
        assert z.valid_from is not None
        assert z.valid_until is not None
        assert z.valid_until > z.valid_from
        # Polygon should be closed (first == last)
        ring = z.geometry["coordinates"][0]
        assert ring[0] == ring[-1]

    def test_calm_sample_creates_nothing(self):
        svc = WeatherZoneService()
        summary = svc.refresh([_calm_sample("east_med")])
        assert summary["created"] == []
        assert Zone.objects().count() == 0

    def test_missing_bbox_is_skipped_not_raised(self):
        svc = WeatherZoneService()
        bad = {"region_id": "x", "wave_height": 10.0, "wind_speed_10m": 50.0}
        summary = svc.refresh([bad])
        assert summary["skipped"] == ["x"]
        assert Zone.objects().count() == 0


class TestRefreshUpdatesAndRetires:
    def test_second_storm_sample_extends_existing_zone(self):
        svc = WeatherZoneService()
        svc.refresh([_storm_sample("east_med")])
        # Now refresh again with same storm; should *extend* not duplicate.
        summary = svc.refresh([_storm_sample("east_med", wave=8.0, wind=22.0)])
        assert summary["extended"] == ["east_med"]
        assert summary["created"] == []
        assert Zone.objects(name=f"{AUTO_STORM_NAME_PREFIX}east_med").count() == 1

    def test_calm_after_storm_retires_zone(self):
        svc = WeatherZoneService()
        svc.refresh([_storm_sample("east_med")])
        assert Zone.objects(name=f"{AUTO_STORM_NAME_PREFIX}east_med").first().status == "active"
        summary = svc.refresh([_calm_sample("east_med")])
        assert summary["retired"] == ["east_med"]
        z = Zone.objects(name=f"{AUTO_STORM_NAME_PREFIX}east_med").first()
        assert z is not None
        assert z.status == "inactive"

    def test_multiple_regions_processed_independently(self):
        svc = WeatherZoneService()
        samples = [
            _storm_sample("east_med"),
            _calm_sample("black_sea"),
            _storm_sample("baltic"),
        ]
        summary = svc.refresh(samples)
        assert sorted(summary["created"]) == ["baltic", "east_med"]
        assert summary["retired"] == []  # no pre-existing storm in black_sea
