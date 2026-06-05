"""Unit tests for the GRIB / current-parsing helpers (#77)."""

from __future__ import annotations

import math

import pytest

from src.core.grib_parser import (
    CurrentVector,
    _stokes_drift,
    _first,
    get_current_effect_on_heading,
)


# ---------------------------------------------------------------------------
# CurrentVector dataclass
# ---------------------------------------------------------------------------


def test_current_vector_derives_speed_and_direction():
    # 1 m/s east, 0 m/s north → speed 1 m/s, direction 90° (eastward).
    c = CurrentVector(u_ms=1.0, v_ms=0.0)
    assert pytest.approx(c.speed_ms) == 1.0
    assert pytest.approx(c.speed_knots, rel=1e-3) == 1.94384
    assert pytest.approx(c.direction_deg) == 90.0


def test_current_vector_due_north():
    c = CurrentVector(u_ms=0.0, v_ms=1.0)
    assert pytest.approx(c.direction_deg) == 0.0


def test_current_vector_zero_speed_is_zero_direction():
    c = CurrentVector(u_ms=0.0, v_ms=0.0)
    assert c.speed_ms == 0.0
    assert c.speed_knots == 0.0


# ---------------------------------------------------------------------------
# Stokes drift
# ---------------------------------------------------------------------------


def test_stokes_drift_returns_zero_when_inputs_missing():
    assert _stokes_drift(None, 8.0, 180.0) == CurrentVector(0.0, 0.0)
    assert _stokes_drift(2.0, None, 180.0) == CurrentVector(0.0, 0.0)
    assert _stokes_drift(2.0, 8.0, None) == CurrentVector(0.0, 0.0)
    assert _stokes_drift(2.0, 0.0, 180.0) == CurrentVector(0.0, 0.0)


def test_stokes_drift_magnitude_matches_formula():
    # U_s ≈ 0.01 * H * (2π / T)
    h, t = 3.0, 9.0
    expected_speed = 0.01 * h * (2 * math.pi / t)
    vec = _stokes_drift(h, t, 0.0)  # waves coming from north → drift to the south
    assert pytest.approx(vec.speed_ms, rel=1e-6) == expected_speed


def test_stokes_drift_direction_is_opposite_of_wave_from():
    # Waves come from the north (0°); drift goes south (180°).
    vec = _stokes_drift(2.0, 8.0, 0.0)
    # 180° in our convention has v_ms < 0 (southward) and ~zero u.
    assert vec.v_ms < 0.0
    assert pytest.approx(vec.u_ms, abs=1e-9) == 0.0


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------


def test_first_returns_first_non_none():
    assert _first([None, None, 4.2, 5.0]) == 4.2


def test_first_returns_none_when_empty():
    assert _first(None) is None
    assert _first([]) is None
    assert _first([None, None]) is None


# ---------------------------------------------------------------------------
# Heading effect
# ---------------------------------------------------------------------------


def test_heading_effect_neutral_with_zero_current():
    factor = get_current_effect_on_heading(CurrentVector(0.0, 0.0), 90.0, 14.0)
    assert factor == 1.0


def test_heading_effect_favourable_when_current_aligns_with_heading():
    # Current flowing east (direction_deg = 90°), vessel heading east.
    east = CurrentVector(u_ms=1.0, v_ms=0.0)
    factor = get_current_effect_on_heading(east, heading_deg=90.0, vessel_speed_knots=14.0)
    assert factor > 1.0


def test_heading_effect_opposed_when_current_against_heading():
    east = CurrentVector(u_ms=1.0, v_ms=0.0)
    # Vessel heading west (270°) — current pushes against it.
    factor = get_current_effect_on_heading(east, heading_deg=270.0, vessel_speed_knots=14.0)
    assert factor < 1.0


def test_heading_effect_zero_speed_is_neutral():
    east = CurrentVector(u_ms=1.0, v_ms=0.0)
    assert get_current_effect_on_heading(east, 90.0, 0.0) == 1.0
