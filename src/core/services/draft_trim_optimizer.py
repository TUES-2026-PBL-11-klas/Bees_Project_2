"""
Draft / trim optimization.

Background
----------
A ship's *draft* (T) is the vertical distance from the waterline to the
bottom of the hull.  Forward (T_f) and aft (T_a) drafts are usually
different; their difference is the *trim*::

    trim = T_a - T_f          (positive = stern-trim, bow-up)

Trim affects:

* **Wave-making resistance** – minimised near zero trim, increases with
  |trim|.
* **Frictional resistance** – grows with wetted surface area, which
  itself grows with mean draft.
* **Wave-induced added resistance** – grows with wave height; reduced
  by a slight bow-down trim in head seas.

We use a simple compact model that captures the dominant terms.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

# Empirical coefficients (calibrated against textbook hull-resistance
# curves; intentionally simple — the goal is *relative* optimisation,
# not an exact CFD prediction).
_K_FRICTION = 1.00
_K_WAVE_MAKING = 0.18
_K_WAVE_ADDED = 0.05


@dataclass
class DraftTrimInput:
    length_m: float
    beam_m: float
    max_draft_m: float
    speed_knots: float
    cargo_weight_t: float                # current cargo on board (tonnes)
    max_cargo_t: float                   # design max cargo (tonnes)
    wave_height_m: float = 0.0           # significant wave height
    water_depth_m: Optional[float] = None  # None ⇒ deep water


@dataclass(frozen=True)
class DraftTrimResult:
    optimal_trim_m: float
    optimal_mean_draft_m: float
    optimal_forward_draft_m: float
    optimal_aft_draft_m: float
    baseline_resistance_index: float
    optimized_resistance_index: float
    fuel_savings_pct: float
    notes: list[str]

    def as_dict(self) -> dict:
        return {
            "optimal_trim_m": round(self.optimal_trim_m, 3),
            "optimal_mean_draft_m": round(self.optimal_mean_draft_m, 3),
            "optimal_forward_draft_m": round(self.optimal_forward_draft_m, 3),
            "optimal_aft_draft_m": round(self.optimal_aft_draft_m, 3),
            "baseline_resistance_index": round(self.baseline_resistance_index, 4),
            "optimized_resistance_index": round(self.optimized_resistance_index, 4),
            "fuel_savings_pct": round(self.fuel_savings_pct, 2),
            "notes": self.notes,
        }


def _froude_number(speed_knots: float, length_m: float) -> float:
    if length_m <= 0:
        return 0.0
    speed_ms = speed_knots * 0.514444
    return speed_ms / max(0.001, (9.81 * length_m) ** 0.5)


def _resistance_index(mean_draft_m: float, trim_m: float, inp: DraftTrimInput) -> float:
    """
    Dimensionless resistance index — minimise this.

    Three additive terms:
      Friction:    K1 · S(T) · v²      with S ≈ L·(B + 2T)
      Wave-making: K2 · v⁴ · (1 + a·trim²) / L²
      Added-wave:  K3 · H² · (1 + b·(trim - trim_opt_for_waves)²)
    """
    L = inp.length_m
    B = inp.beam_m
    v_ms = inp.speed_knots * 0.514444
    H = inp.wave_height_m

    # Wetted surface area (rough approximation).
    S = max(1.0, L * (B + 2.0 * mean_draft_m))

    friction = _K_FRICTION * S * v_ms**2

    # Wave-making resistance grows with trim², modulated by Froude #.
    Fr = _froude_number(inp.speed_knots, L)
    wave_making = _K_WAVE_MAKING * v_ms**4 * (1.0 + 2.0 * trim_m**2) / max(1.0, L) ** 2
    wave_making *= 1.0 + 1.5 * Fr**2

    # Added wave resistance: in significant waves a small bow-down trim
    # (negative ~ -0.3 m) is optimal; with calm sea this term is ~0.
    trim_target = -0.3 if H >= 1.0 else 0.0
    added_wave = _K_WAVE_ADDED * H**2 * (1.0 + 0.7 * (trim_m - trim_target) ** 2)

    # Shallow-water correction (h/T ratio).
    if inp.water_depth_m is not None and mean_draft_m > 0:
        ratio = inp.water_depth_m / mean_draft_m
        if ratio < 3.0:
            friction *= 1.0 + 0.4 * (3.0 - ratio)

    return friction + wave_making + added_wave


def _mean_draft_from_cargo(inp: DraftTrimInput) -> float:
    """Linear approximation: draft scales with displacement (cargo) fraction."""
    if inp.max_cargo_t <= 0:
        return inp.max_draft_m * 0.6
    cargo_fraction = max(0.0, min(1.0, inp.cargo_weight_t / inp.max_cargo_t))
    light_draft = inp.max_draft_m * 0.45
    return light_draft + (inp.max_draft_m - light_draft) * cargo_fraction


def optimize(inp: DraftTrimInput) -> DraftTrimResult:
    """
    Compute the optimal trim (and forward/aft drafts) by minimising the
    resistance index over a 1-D grid search.

    Mean draft is fixed by cargo load — only trim is tunable, which
    matches how operators ballast in practice.
    """
    if inp.length_m <= 0 or inp.beam_m <= 0 or inp.max_draft_m <= 0:
        raise ValueError("length_m, beam_m and max_draft_m must be positive")
    if inp.speed_knots <= 0:
        raise ValueError("speed_knots must be positive")

    mean_draft = _mean_draft_from_cargo(inp)

    # Allowable trim is clamped so forward draft stays positive and aft
    # draft does not exceed the design maximum.
    trim_upper = min(2.5, 2.0 * (inp.max_draft_m - mean_draft))
    trim_lower = -min(2.5, 2.0 * mean_draft - 0.5)

    notes: list[str] = []
    if trim_upper < trim_lower:
        notes.append("Cargo load leaves no room to adjust trim; using zero trim.")
        trim_upper = trim_lower = 0.0

    baseline = _resistance_index(mean_draft, 0.0, inp)

    best_trim = 0.0
    best_resistance = baseline
    step = 0.05
    t = trim_lower
    while t <= trim_upper + 1e-9:
        r = _resistance_index(mean_draft, t, inp)
        if r < best_resistance:
            best_resistance = r
            best_trim = t
        t += step

    if inp.wave_height_m >= 1.0:
        notes.append(
            f"Significant waves ({inp.wave_height_m:.1f} m) — slight bow-down trim preferred.",
        )
    if inp.water_depth_m is not None and mean_draft > 0 and inp.water_depth_m / mean_draft < 3.0:
        notes.append(
            f"Shallow water (depth/draft = {inp.water_depth_m / mean_draft:.1f}); "
            "expect elevated friction.",
        )

    fwd = mean_draft - best_trim / 2.0
    aft = mean_draft + best_trim / 2.0
    savings = (baseline - best_resistance) / baseline * 100.0 if baseline > 0 else 0.0

    return DraftTrimResult(
        optimal_trim_m=best_trim,
        optimal_mean_draft_m=mean_draft,
        optimal_forward_draft_m=fwd,
        optimal_aft_draft_m=aft,
        baseline_resistance_index=baseline,
        optimized_resistance_index=best_resistance,
        fuel_savings_pct=savings,
        notes=notes,
    )
