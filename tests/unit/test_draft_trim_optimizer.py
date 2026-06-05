"""Unit tests for the draft / trim optimizer (#80)."""

import pytest

from src.core.services.draft_trim_optimizer import (
    DraftTrimInput,
    DraftTrimResult,
    optimize,
)


def _base(**overrides) -> DraftTrimInput:
    defaults = dict(
        length_m=180.0,
        beam_m=32.0,
        max_draft_m=12.0,
        speed_knots=14.0,
        cargo_weight_t=15000.0,
        max_cargo_t=30000.0,
        wave_height_m=0.0,
        water_depth_m=None,
    )
    defaults.update(overrides)
    return DraftTrimInput(**defaults)


def test_optimum_is_near_zero_in_calm_water():
    """With no waves the wave-making term dominates; optimum trim ≈ 0."""
    result = optimize(_base())
    assert isinstance(result, DraftTrimResult)
    assert abs(result.optimal_trim_m) <= 0.1


def test_optimum_shifts_bow_down_in_heavy_seas():
    """With significant waves, slight negative (bow-down) trim wins."""
    result = optimize(_base(wave_height_m=3.0))
    assert result.optimal_trim_m < 0.0
    # Notes flag the wave condition.
    assert any("waves" in n.lower() for n in result.notes)


def test_forward_and_aft_drafts_match_mean_and_trim():
    result = optimize(_base())
    expected_fwd = result.optimal_mean_draft_m - result.optimal_trim_m / 2.0
    expected_aft = result.optimal_mean_draft_m + result.optimal_trim_m / 2.0
    assert pytest.approx(expected_fwd, abs=1e-6) == result.optimal_forward_draft_m
    assert pytest.approx(expected_aft, abs=1e-6) == result.optimal_aft_draft_m


def test_mean_draft_scales_with_cargo_load():
    light = optimize(_base(cargo_weight_t=0))
    full = optimize(_base(cargo_weight_t=30000))
    assert full.optimal_mean_draft_m > light.optimal_mean_draft_m


def test_shallow_water_flag():
    result = optimize(_base(water_depth_m=18.0))  # depth/draft ~ 2.0
    assert any("shallow" in n.lower() for n in result.notes)


def test_invalid_input_raises():
    with pytest.raises(ValueError):
        optimize(_base(length_m=0.0))
    with pytest.raises(ValueError):
        optimize(_base(speed_knots=0.0))


def test_savings_is_non_negative():
    """Optimizer can't make things worse than the baseline (zero-trim) case."""
    result = optimize(_base(wave_height_m=2.5))
    assert result.fuel_savings_pct >= 0.0
