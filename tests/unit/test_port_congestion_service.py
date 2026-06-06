"""Unit tests for PortCongestionService."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
import mongomock
import mongoengine
from bson import ObjectId

from src.core.services.port_congestion_service import PortCongestionService
from src.models.port_scheduling import DockReservation, Port


PORT_ID = "TEST_PORT"


@pytest.fixture(scope="module", autouse=True)
def mock_db():
    mongoengine.disconnect_all()
    mongoengine.connect(
        "testdb_port_congestion",
        host="mongodb://localhost",
        mongo_client_class=mongomock.MongoClient,
        uuidRepresentation="standard",
    )
    yield
    mongoengine.disconnect_all()


@pytest.fixture(autouse=True)
def clean_data():
    Port.drop_collection()
    DockReservation.drop_collection()


def _create_port(berth_count: int = 3) -> Port:
    p = Port(
        port_id=PORT_ID,
        name="Test Port",
        latitude=40.0,
        longitude=-3.0,
        berth_count=berth_count,
    )
    p.save()
    return p


def _make_reservation(
    *,
    berth: int,
    start: datetime,
    end: datetime,
    status: str = "scheduled",
) -> DockReservation:
    r = DockReservation(
        port_id=PORT_ID,
        berth_number=berth,
        vessel_id=ObjectId(),
        start_at=start,
        end_at=end,
        status=status,
    )
    r.save()
    return r


class TestForecastBasics:
    def test_unknown_port_raises_lookup_error(self):
        svc = PortCongestionService()
        with pytest.raises(LookupError):
            svc.forecast("NO_SUCH_PORT")

    def test_invalid_horizon_raises(self):
        _create_port()
        svc = PortCongestionService()
        with pytest.raises(ValueError):
            svc.forecast(PORT_ID, horizon_hours=0)

    def test_bucket_larger_than_horizon_raises(self):
        _create_port()
        svc = PortCongestionService()
        with pytest.raises(ValueError):
            svc.forecast(PORT_ID, horizon_hours=1, bucket_minutes=120)

    def test_empty_port_returns_zero_congestion(self):
        _create_port(berth_count=3)
        svc = PortCongestionService()
        f = svc.forecast(PORT_ID, horizon_hours=6)
        assert f.peak_score == 0.0
        assert all(b.confirmed_occupied == 0 for b in f.buckets)
        assert all(b.available_berths_estimate == 3 for b in f.buckets)
        assert f.berth_count == 3
        # 6 hours, hourly buckets → 6 entries
        assert len(f.buckets) == 6


class TestConfirmedReservations:
    def test_single_reservation_lifts_occupancy_in_its_window(self):
        _create_port(berth_count=2)
        start = datetime(2026, 6, 6, 12, 0)
        _make_reservation(
            berth=1, start=start, end=start + timedelta(hours=2),
        )
        svc = PortCongestionService(confirmed_weight=1.0)  # ignore history
        f = svc.forecast(PORT_ID, start_at=start, horizon_hours=4)
        # buckets 0 and 1 should be partially occupied (1/2 berths)
        assert f.buckets[0].confirmed_occupied == 1
        assert f.buckets[1].confirmed_occupied == 1
        assert f.buckets[2].confirmed_occupied == 0
        assert f.buckets[0].projected_occupancy == pytest.approx(0.5)
        assert f.buckets[2].projected_occupancy == 0.0

    def test_fully_booked_hour_saturates(self):
        _create_port(berth_count=2)
        start = datetime(2026, 6, 6, 12, 0)
        _make_reservation(berth=1, start=start, end=start + timedelta(hours=1))
        _make_reservation(berth=2, start=start, end=start + timedelta(hours=1))
        svc = PortCongestionService(confirmed_weight=1.0)
        f = svc.forecast(PORT_ID, start_at=start, horizon_hours=2)
        assert f.buckets[0].projected_occupancy == 1.0
        assert f.buckets[0].available_berths_estimate == 0.0

    def test_cancelled_reservation_does_not_count(self):
        _create_port(berth_count=1)
        start = datetime(2026, 6, 6, 12, 0)
        _make_reservation(
            berth=1, start=start, end=start + timedelta(hours=1),
            status="cancelled",
        )
        svc = PortCongestionService(confirmed_weight=1.0)
        f = svc.forecast(PORT_ID, start_at=start, horizon_hours=1)
        assert f.buckets[0].confirmed_occupied == 0


class TestHistoricalBaseline:
    def test_past_reservations_create_historical_signal(self):
        _create_port(berth_count=2)
        # Five Saturdays ago at 14:00–15:00, berth 1 was occupied.
        start = datetime(2026, 6, 6, 14, 0)  # Saturday
        for week in range(1, 6):
            past_start = start - timedelta(days=7 * week)
            _make_reservation(
                berth=1,
                start=past_start,
                end=past_start + timedelta(hours=1),
                status="completed",
            )

        # No confirmed bookings in the forecast window.
        svc = PortCongestionService(confirmed_weight=0.0)  # rely only on history
        f = svc.forecast(PORT_ID, start_at=start, horizon_hours=1)
        # Saturday 14:00 was historically busy → projected_occupancy > 0
        assert f.buckets[0].projected_occupancy > 0
        # But it's not full because only 1 / 2 berths were used.
        assert f.buckets[0].projected_occupancy < 1.0


class TestBlend:
    def test_blend_weighted_average(self):
        _create_port(berth_count=4)
        start = datetime(2026, 6, 6, 10, 0)
        # 2 of 4 berths confirmed → confirmed ratio 0.5
        _make_reservation(berth=1, start=start, end=start + timedelta(hours=1))
        _make_reservation(berth=2, start=start, end=start + timedelta(hours=1))

        # weight=0.7 means 0.7 × 0.5 + 0.3 × 0 = 0.35
        svc = PortCongestionService(confirmed_weight=0.7)
        f = svc.forecast(PORT_ID, start_at=start, horizon_hours=1)
        assert f.buckets[0].projected_occupancy == pytest.approx(0.35)
        assert f.buckets[0].available_berths_estimate == pytest.approx(4 * 0.65)
