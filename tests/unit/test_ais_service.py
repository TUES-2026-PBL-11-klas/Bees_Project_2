"""Unit tests for the AIS cache and message parser."""

from __future__ import annotations

import time

from src.core.services import ais_service
from src.core.services.ais_service import (
    AISCache,
    AISPosition,
    _extract_position,
)


def _position(mmsi: int = 1234567, lat: float = 0.0, lon: float = 0.0) -> AISPosition:
    return AISPosition(mmsi=mmsi, lat=lat, lon=lon, name="TEST")


class TestAISCache:
    def test_upsert_and_snapshot(self):
        cache = AISCache()
        cache.upsert(_position(1, 10.0, 20.0))
        cache.upsert(_position(2, -10.0, -20.0))
        snap = cache.snapshot()
        assert len(snap) == 2
        assert {p.mmsi for p in snap} == {1, 2}

    def test_bbox_filter(self):
        cache = AISCache()
        cache.upsert(_position(1, 10.0, 20.0))   # inside
        cache.upsert(_position(2, 60.0, 60.0))   # outside
        snap = cache.snapshot(bbox=(0.0, 0.0, 30.0, 30.0))
        assert [p.mmsi for p in snap] == [1]

    def test_upsert_replaces_previous(self):
        cache = AISCache()
        cache.upsert(_position(1, 10.0, 20.0))
        cache.upsert(_position(1, 11.0, 21.0))
        snap = cache.snapshot()
        assert len(snap) == 1
        assert snap[0].lat == 11.0

    def test_stale_entries_are_evicted(self):
        cache = AISCache(max_age_seconds=1)
        old = _position(1)
        old.updated_at = time.time() - 100
        cache.upsert(old)
        # Fresh entry survives.
        cache.upsert(_position(2))
        snap = cache.snapshot()
        assert [p.mmsi for p in snap] == [2]

    def test_limit_caps_results(self):
        cache = AISCache()
        for i in range(50):
            cache.upsert(_position(i))
        snap = cache.snapshot(limit=10)
        assert len(snap) == 10


class TestExtractPosition:
    def test_position_report_minimal(self):
        msg = {
            "MessageType": "PositionReport",
            "MetaData": {"MMSI": 111222333, "ShipName": " ATLANTIC EXPLORER "},
            "Message": {"PositionReport": {"Latitude": 12.34, "Longitude": -56.78,
                                           "Sog": 14.2, "Cog": 90.0}},
        }
        pos = _extract_position(msg)
        assert pos is not None
        assert pos.mmsi == 111222333
        assert pos.lat == 12.34
        assert pos.lon == -56.78
        assert pos.sog == 14.2
        assert pos.cog == 90.0
        assert pos.name == "ATLANTIC EXPLORER"

    def test_missing_coordinates_returns_none(self):
        msg = {
            "MessageType": "PositionReport",
            "MetaData": {"MMSI": 1},
            "Message": {"PositionReport": {}},
        }
        assert _extract_position(msg) is None

    def test_unknown_message_type_returns_none(self):
        msg = {"MessageType": "StandardClassBPositionReport", "Message": {}}
        # Not in our handled list.
        assert _extract_position(msg) is None

    def test_static_data_refreshes_name_on_existing(self):
        # Seed the cache with a position first.
        ais_service.cache.upsert(_position(42, 1.0, 2.0))
        msg = {
            "MessageType": "ShipStaticData",
            "MetaData": {"MMSI": 42, "ShipName": "RENAMED"},
            "Message": {"ShipStaticData": {"Type": 70}},
        }
        pos = _extract_position(msg)
        assert pos is not None
        assert pos.name == "RENAMED"
        assert pos.ship_type == 70

    def test_static_data_unknown_mmsi_is_ignored(self):
        msg = {
            "MessageType": "ShipStaticData",
            "MetaData": {"MMSI": 999999999, "ShipName": "GHOST"},
            "Message": {"ShipStaticData": {}},
        }
        # Nothing seeded for this MMSI.
        assert _extract_position(msg) is None


class TestEnableFlag:
    def test_disabled_when_no_api_key(self, monkeypatch):
        monkeypatch.delenv("AIS_API_KEY", raising=False)
        assert ais_service.is_enabled() is False
        assert ais_service.make_consumer() is None

    def test_enabled_when_api_key_present(self, monkeypatch):
        monkeypatch.setenv("AIS_API_KEY", "test-key")
        assert ais_service.is_enabled() is True
        consumer = ais_service.make_consumer()
        assert consumer is not None
        assert consumer.api_key == "test-key"
