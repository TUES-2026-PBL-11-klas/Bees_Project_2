"""
Emissions & CII (Carbon Intensity Indicator) service.

Computes CO2 emissions from fuel burn and grades vessels against the
IMO's Carbon Intensity Indicator reference lines (MEPC.337(76),
MEPC.353(78), MEPC.354(78) — the 2023 CII framework).

Why this matters
----------------
Under the IMO's CII regulation and the EU Emissions Trading System (EU
ETS), every ship over 5,000 GT must report its annual carbon intensity
and is rated A (best) through E (worst). Ships rated D for three
consecutive years or E in any year must submit a corrective action plan.
The EU ETS additionally requires shipping companies to surrender
allowances proportional to CO2 emitted on voyages calling at EU ports.

This service provides the math that turns the existing ``estimated_fuel_tons``
output of the routing engine into:

* CO2 tonnes (per voyage)
* CII attained value (g CO2 / DWT-nm)
* IMO grade (A/B/C/D/E)
* Indicative EU ETS allowance cost (€)

The calculations are deliberately self-contained and dependency-free so
the same service can be called from the route response, a CSV export,
or a background sustainability dashboard.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


# ---------------------------------------------------------------------------
# Fuel emission factors (tonnes CO2 emitted per tonne of fuel burned).
# Sources: IMO MEPC.364(79) Annex 1; IPCC 2006 Guidelines.
# ---------------------------------------------------------------------------

FUEL_EMISSION_FACTORS: dict[str, float] = {
    "HFO":      3.114,   # Heavy Fuel Oil — most common deep-sea fuel
    "LFO":      3.151,   # Light Fuel Oil
    "MDO":      3.206,   # Marine Diesel Oil
    "MGO":      3.206,   # Marine Gas Oil
    "LNG":      2.750,   # Liquefied Natural Gas
    "METHANOL": 1.375,   # Methanol (CH3OH)
    "AMMONIA":  0.000,   # Green ammonia — combustion is carbon-free
    "BIO":      0.000,   # Sustainably-sourced biofuel (counted carbon-neutral)
}

DEFAULT_FUEL_TYPE = "HFO"


# ---------------------------------------------------------------------------
# CII reference lines per vessel type (MEPC.337(76)).
# Reference CII = a × DWT^(-c)        [g CO2 / DWT-nm]
# ---------------------------------------------------------------------------

_CII_REFERENCE_COEFFS: dict[str, tuple[float, float]] = {
    "bulk_carrier":     (4745.0,   0.622),
    "tanker":           (5247.0,   0.610),
    "container_ship":   (1984.0,   0.489),
    "gas_carrier":      (14405.91, 0.6610),
    "lng_carrier":      (9.827,    0.0000),    # treated as flat for >=100k DWT
    "ro_ro_ship":       (10952.0,  0.575),
    "general_cargo":    (31948.0,  0.792),
    "cruise_ship":      (17.232,   0.0000),    # flat reference per GT-class
    "ferry":            (10952.0,  0.575),     # approx as RoRo
}

# Default rating bands (MEPC.354(78), applicable from 2023). The bands shift
# year-over-year by a "reduction factor" — for 2024 they tighten by ~5%
# compared to the 2019 reference baseline; from 2026 they tighten further.
# Per the standard the boundaries are *multipliers* applied to the
# reference CII: a ship scoring below dd1*ref is A, between dd1 and dd2 is B,
# and so on.
_RATING_BANDS: dict[str, tuple[float, float, float, float]] = {
    "bulk_carrier":     (0.86, 0.94, 1.06, 1.18),
    "tanker":           (0.82, 0.93, 1.08, 1.28),
    "container_ship":   (0.83, 0.94, 1.07, 1.19),
    "gas_carrier":      (0.81, 0.91, 1.12, 1.44),
    "lng_carrier":      (0.89, 0.98, 1.06, 1.13),
    "ro_ro_ship":       (0.66, 0.90, 1.11, 1.37),
    "general_cargo":    (0.83, 0.94, 1.06, 1.19),
    "cruise_ship":      (0.87, 0.95, 1.06, 1.16),
    "ferry":            (0.66, 0.90, 1.11, 1.37),
}

# Year-over-year tightening factor on the CII required value, relative to
# the 2019 baseline. Reduction is cumulative.
_REDUCTION_FACTOR_BY_YEAR: dict[int, float] = {
    2023: 0.95,   # -5%
    2024: 0.93,   # -7%
    2025: 0.91,   # -9%
    2026: 0.89,   # -11%
    2027: 0.87,   # -13% (assumed continuation per IMO trajectory)
}

DEFAULT_RATING_BANDS = (0.86, 0.94, 1.06, 1.18)
DEFAULT_REFERENCE_COEFFS = (4745.0, 0.622)  # fall back to bulk carrier

# EU ETS coverage factor on voyages calling at an EU port — phased in:
# 2024 = 40 %, 2025 = 70 %, 2026 onwards = 100 % of CO2 emitted on the leg
# is subject to allowance surrender. Allowance price (EUA) here is just
# a sensible default; real systems should pull live from a market feed.
_ETS_COVERAGE_BY_YEAR: dict[int, float] = {
    2024: 0.40,
    2025: 0.70,
    2026: 1.00,
}
DEFAULT_EUA_PRICE_EUR = 75.0  # indicative spot price


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EmissionsResult:
    fuel_tons: float
    fuel_type: str
    co2_tons: float
    cii_attained: Optional[float]   # g CO2 / DWT-nm
    cii_required: Optional[float]
    cii_ratio: Optional[float]      # attained / required (lower is better)
    rating: Optional[str]           # "A".."E"
    eu_ets_eligible_co2_tons: Optional[float]
    eu_ets_allowance_cost_eur: Optional[float]

    def to_dict(self) -> dict:
        return {
            "fuel_tons":                    round(self.fuel_tons, 3),
            "fuel_type":                    self.fuel_type,
            "co2_tons":                     round(self.co2_tons, 3),
            "cii_attained_g_per_dwt_nm":    _round(self.cii_attained, 4),
            "cii_required_g_per_dwt_nm":    _round(self.cii_required, 4),
            "cii_ratio":                    _round(self.cii_ratio, 3),
            "rating":                       self.rating,
            "eu_ets_eligible_co2_tons":     _round(self.eu_ets_eligible_co2_tons, 3),
            "eu_ets_allowance_cost_eur":    _round(self.eu_ets_allowance_cost_eur, 2),
        }


def _round(value: Optional[float], ndigits: int) -> Optional[float]:
    return round(value, ndigits) if value is not None else None


def calculate_co2_tons(fuel_tons: float, fuel_type: str = DEFAULT_FUEL_TYPE) -> float:
    """Return CO2 tonnes emitted by burning ``fuel_tons`` of the given fuel."""
    if fuel_tons < 0:
        raise ValueError("fuel_tons must be non-negative")
    factor = FUEL_EMISSION_FACTORS.get(fuel_type.upper(), FUEL_EMISSION_FACTORS[DEFAULT_FUEL_TYPE])
    return fuel_tons * factor


def reference_cii(vessel_type: str, dwt_tons: float) -> float:
    """Required CII reference value for a vessel type and deadweight."""
    if dwt_tons <= 0:
        raise ValueError("dwt_tons must be positive")
    a, c = _CII_REFERENCE_COEFFS.get(vessel_type, DEFAULT_REFERENCE_COEFFS)
    if c == 0.0:
        return a
    return a * (dwt_tons ** (-c))


def required_cii_for_year(vessel_type: str, dwt_tons: float, year: int) -> float:
    """Required CII after the year-over-year IMO reduction factor."""
    ref = reference_cii(vessel_type, dwt_tons)
    factor = _REDUCTION_FACTOR_BY_YEAR.get(year, _REDUCTION_FACTOR_BY_YEAR[max(_REDUCTION_FACTOR_BY_YEAR)])
    return ref * factor


def attained_cii(co2_tons: float, dwt_tons: float, distance_nm: float) -> float:
    """Attained CII = grams CO2 emitted / (DWT × distance_nm)."""
    if dwt_tons <= 0 or distance_nm <= 0:
        raise ValueError("dwt_tons and distance_nm must be positive")
    co2_grams = co2_tons * 1_000_000.0
    return co2_grams / (dwt_tons * distance_nm)


def cii_rating(attained: float, required: float, vessel_type: str) -> str:
    """Return the IMO A–E grade for the (attained, required) pair."""
    bands = _RATING_BANDS.get(vessel_type, DEFAULT_RATING_BANDS)
    dd1, dd2, dd3, dd4 = bands
    ratio = attained / required
    if ratio <= dd1:
        return "A"
    if ratio <= dd2:
        return "B"
    if ratio <= dd3:
        return "C"
    if ratio <= dd4:
        return "D"
    return "E"


def eu_ets_allowance_cost(
    co2_tons: float,
    *,
    year: int,
    calls_at_eu_port: bool,
    eua_price_eur: float = DEFAULT_EUA_PRICE_EUR,
) -> tuple[float, float]:
    """
    Return ``(eligible_co2_tons, cost_eur)``.

    Under EU ETS for shipping (Directive 2003/87/EC as amended), voyages
    between two EU ports count 100 % of emissions; voyages between an EU
    port and a non-EU port count 50 %. The phase-in factor adjusts that
    by year (40 % in 2024, 70 % in 2025, 100 % thereafter). Voyages that
    do not touch an EU port are out of scope.
    """
    if not calls_at_eu_port:
        return 0.0, 0.0
    coverage = _ETS_COVERAGE_BY_YEAR.get(year, 1.0)
    eligible = co2_tons * coverage
    return eligible, eligible * eua_price_eur


class EmissionsService:
    """High-level service tying the helpers above into a single call."""

    def __init__(
        self,
        *,
        eua_price_eur: float = DEFAULT_EUA_PRICE_EUR,
        compliance_year: Optional[int] = None,
    ) -> None:
        self.eua_price_eur = eua_price_eur
        if compliance_year is None:
            from src.core.utc import utc_now
            compliance_year = utc_now().year
        self.compliance_year = compliance_year

    def evaluate_voyage(
        self,
        *,
        fuel_tons: float,
        vessel_type: str,
        distance_nm: float,
        dwt_tons: Optional[float] = None,
        fuel_type: str = DEFAULT_FUEL_TYPE,
        calls_at_eu_port: bool = False,
    ) -> EmissionsResult:
        """Evaluate a single voyage end-to-end.

        ``dwt_tons`` is required to grade CII; if it isn't supplied the
        result still includes CO2 and ETS but rating fields are ``None``.
        """
        co2 = calculate_co2_tons(fuel_tons, fuel_type)

        if dwt_tons and dwt_tons > 0 and distance_nm > 0:
            attained = attained_cii(co2, dwt_tons, distance_nm)
            required = required_cii_for_year(vessel_type, dwt_tons, self.compliance_year)
            ratio = attained / required if required > 0 else None
            grade = cii_rating(attained, required, vessel_type)
        else:
            attained = required = ratio = grade = None

        eligible_co2, cost_eur = eu_ets_allowance_cost(
            co2,
            year=self.compliance_year,
            calls_at_eu_port=calls_at_eu_port,
            eua_price_eur=self.eua_price_eur,
        )

        return EmissionsResult(
            fuel_tons=fuel_tons,
            fuel_type=fuel_type.upper(),
            co2_tons=co2,
            cii_attained=attained,
            cii_required=required,
            cii_ratio=ratio,
            rating=grade,
            eu_ets_eligible_co2_tons=eligible_co2,
            eu_ets_allowance_cost_eur=cost_eur,
        )
