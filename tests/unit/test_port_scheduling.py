"""Unit tests for port scheduling models. Focus on conflict logic."""

from datetime import datetime, timedelta
from types import SimpleNamespace

from src.models.port_scheduling import DockReservation, PortSchedule


def _res(start_offset_h, end_offset_h, *, port="BURGAS", berth=1, status="scheduled"):
    base = datetime(2026, 6, 10, 8, 0, 0)
    return DockReservation(
        port_id=port,
        berth_number=berth,
        vessel_id="6a2276a96ee02e77a5f911f3",
        start_at=base + timedelta(hours=start_offset_h),
        end_at=base + timedelta(hours=end_offset_h),
        status=status,
    )


def test_overlap_same_berth_conflicts():
    a = _res(0, 8)
    b = _res(4, 12)
    assert a.conflicts_with(b) is True
    assert b.conflicts_with(a) is True


def test_back_to_back_slots_do_not_conflict():
    a = _res(0, 8)
    b = _res(8, 16)  # open-interval — touching boundary is OK
    assert a.conflicts_with(b) is False


def test_different_berth_never_conflicts():
    a = _res(0, 8, berth=1)
    b = _res(4, 12, berth=2)
    assert a.conflicts_with(b) is False


def test_different_port_never_conflicts():
    a = _res(0, 8, port="BURGAS")
    b = _res(4, 12, port="VARNA")
    assert a.conflicts_with(b) is False


def test_cancelled_slots_do_not_conflict():
    a = _res(0, 8, status="cancelled")
    b = _res(4, 12)
    assert a.conflicts_with(b) is False
    assert b.conflicts_with(a) is False


def test_blackout_window_active():
    schedule = PortSchedule(port_id="BURGAS")
    schedule.blackouts = [
        {
            "start": datetime(2026, 6, 15, 0, 0),
            "end":   datetime(2026, 6, 16, 0, 0),
            "reason": "maintenance",
        }
    ]
    assert schedule.is_blackout_active(datetime(2026, 6, 15, 12, 0)) is True
    assert schedule.is_blackout_active(datetime(2026, 6, 17, 0, 0)) is False
