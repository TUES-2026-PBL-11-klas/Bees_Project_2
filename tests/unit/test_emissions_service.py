"""Unit tests for the emissions / CII service."""

from __future__ import annotations

import pytest

from src.core.services.emissions_service import (
    DEFAULT_FUEL_TYPE,
    EmissionsService,
    FUEL_EMISSION_FACTORS,
    attained_cii,
    calculate_co2_tons,
    cii_rating,
    eu_ets_allowance_cost,
    reference_cii,
    required_cii_for_year,
)


class TestFuelToCO2:
    def test_hfo_factor_is_3p114(self):
        # 100 t HFO → 311.4 t CO2.
        assert calculate_co2_tons(100, "HFO") == pytest.approx(311.4, abs=0.01)

    def test_lng_burns_cleaner_than_hfo(self):
        assert calculate_co2_tons(100, "LNG") < calculate_co2_tons(100, "HFO")

    def test_ammonia_is_zero_carbon(self):
        assert calculate_co2_tons(100, "AMMONIA") == 0.0

    def test_unknown_fuel_falls_back_to_default(self):
        assert calculate_co2_tons(50, "WHIMSY") == pytest.approx(
            50 * FUEL_EMISSION_FACTORS[DEFAULT_FUEL_TYPE]
        )

    def test_negative_fuel_raises(self):
        with pytest.raises(ValueError):
            calculate_co2_tons(-1, "HFO")


class TestReferenceCII:
    def test_bulk_carrier_reference_decreases_with_dwt(self):
        # Per MEPC.337(76) the curve is monotonically decreasing in DWT.
        a = reference_cii("bulk_carrier", 30_000)
        b = reference_cii("bulk_carrier", 200_000)
        assert a > b

    def test_required_for_year_tightens_over_time(self):
        # 2026 reduction factor is stricter than 2023.
        early = required_cii_for_year("tanker", 100_000, 2023)
        late = required_cii_for_year("tanker", 100_000, 2026)
        assert late < early

    def test_unknown_vessel_type_falls_back(self):
        # Should not raise; returns *some* reference.
        ref = reference_cii("flying_carpet", 50_000)
        assert ref > 0


class TestAttainedAndRating:
    def test_attained_is_grams_per_dwt_nm(self):
        # 100 t CO2 → 100_000_000 g; over 50_000 DWT × 1000 nm = 5e7 → 2.0
        assert attained_cii(100.0, 50_000, 1000) == pytest.approx(2.0)

    def test_rating_A_when_well_below_required(self):
        # attained / required = 0.50 → A band (≤ 0.86 for bulk_carrier)
        assert cii_rating(attained=5.0, required=10.0, vessel_type="bulk_carrier") == "A"

    def test_rating_E_when_well_above_required(self):
        # ratio 2.0 → past the dd4=1.18 cutoff → E
        assert cii_rating(attained=20.0, required=10.0, vessel_type="bulk_carrier") == "E"

    def test_rating_boundary_dd1_is_A(self):
        # Exactly at the dd1 boundary should still be A (≤ comparison).
        assert cii_rating(attained=8.6, required=10.0, vessel_type="bulk_carrier") == "A"

    def test_rating_just_above_dd2_is_C(self):
        # ratio 0.95 → above dd2 (0.94), below dd3 (1.06) → C
        assert cii_rating(attained=9.5, required=10.0, vessel_type="bulk_carrier") == "C"


class TestEUETS:
    def test_no_eu_call_means_no_cost(self):
        eligible, cost = eu_ets_allowance_cost(100.0, year=2025, calls_at_eu_port=False)
        assert eligible == 0.0
        assert cost == 0.0

    def test_phase_in_factor_2024_is_40_percent(self):
        eligible, _ = eu_ets_allowance_cost(100.0, year=2024, calls_at_eu_port=True)
        assert eligible == pytest.approx(40.0)

    def test_phase_in_factor_2026_is_full(self):
        eligible, _ = eu_ets_allowance_cost(100.0, year=2026, calls_at_eu_port=True)
        assert eligible == pytest.approx(100.0)

    def test_cost_uses_supplied_price(self):
        _, cost = eu_ets_allowance_cost(
            100.0, year=2025, calls_at_eu_port=True, eua_price_eur=80.0,
        )
        # 70 t × 80 €/t = 5600
        assert cost == pytest.approx(5600.0)


class TestEvaluateVoyageEndToEnd:
    def test_full_voyage_returns_complete_result(self):
        svc = EmissionsService(compliance_year=2025)
        result = svc.evaluate_voyage(
            fuel_tons=50.0,
            vessel_type="bulk_carrier",
            distance_nm=1200.0,
            dwt_tons=80_000.0,
            fuel_type="HFO",
            calls_at_eu_port=True,
        )
        assert result.co2_tons == pytest.approx(155.7, abs=0.1)
        assert result.cii_attained is not None
        assert result.cii_required is not None
        assert result.rating in {"A", "B", "C", "D", "E"}
        assert result.eu_ets_eligible_co2_tons == pytest.approx(155.7 * 0.7, abs=0.1)

    def test_missing_dwt_still_returns_co2(self):
        svc = EmissionsService(compliance_year=2025)
        result = svc.evaluate_voyage(
            fuel_tons=25.0,
            vessel_type="tanker",
            distance_nm=500.0,
            dwt_tons=None,
            fuel_type="MGO",
        )
        assert result.co2_tons > 0
        assert result.rating is None
        assert result.cii_attained is None

    def test_dict_form_rounds_consistently(self):
        svc = EmissionsService(compliance_year=2025)
        d = svc.evaluate_voyage(
            fuel_tons=10.0,
            vessel_type="container_ship",
            distance_nm=100.0,
            dwt_tons=50_000.0,
            calls_at_eu_port=True,
        ).to_dict()
        assert isinstance(d["co2_tons"], float)
        assert isinstance(d["rating"], str)
