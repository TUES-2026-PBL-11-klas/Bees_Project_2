"""Unit tests for AnalyticsService (#81). DB-free — uses stub history records."""

from dataclasses import dataclass
from typing import Optional

from src.core.services.analytics_service import AnalyticsService, aggregate


@dataclass
class StubHistory:
    total_distance_nm: float
    estimated_duration_h: float
    estimated_fuel_tons: float
    optimization_mode: str
    vessel_id: Optional[str] = "v1"
    company_id: Optional[str] = "c1"


class StubRepo:
    def __init__(self, items):
        self.items = items

    def get_by_vessel(self, vessel_id, limit=200):
        return [i for i in self.items if i.vessel_id == vessel_id][:limit]

    def get_by_company(self, company_id, limit=500):
        return [i for i in self.items if i.company_id == company_id][:limit]

    def get_recent(self, limit=1000):
        return self.items[:limit]


def _items():
    return [
        StubHistory(500, 36, 25, "fastest"),
        StubHistory(520, 38, 27, "fastest"),
        StubHistory(540, 41, 24, "eco"),
        StubHistory(560, 42, 26, "eco"),
    ]


def test_aggregate_handles_empty_input():
    agg = aggregate([])
    assert agg.sample_size == 0
    assert agg.avg_fuel_tons is None
    assert agg.stdev_fuel_tons is None


def test_aggregate_basic_mean_and_stdev():
    agg = aggregate(_items()[:2])  # fuel 25, 27
    assert agg.sample_size == 2
    assert agg.avg_fuel_tons == 26.0
    assert agg.stdev_fuel_tons == 1.0  # population stdev


def test_strategy_effectiveness_eco_vs_fastest():
    svc = AnalyticsService(history_repo=StubRepo(_items()))
    out = svc.strategy_effectiveness()
    assert out["sample_size"] == 4
    assert out["fastest"]["sample_size"] == 2
    assert out["eco"]["sample_size"] == 2
    # Eco fuel is 25 vs fastest 26 → -3.85%
    assert out["eco_vs_fastest_pct"]["fuel"] == round((25 - 26) / 26 * 100, 2)


def test_vessel_summary_splits_by_strategy():
    svc = AnalyticsService(history_repo=StubRepo(_items()))
    out = svc.vessel_summary("v1")
    assert out["vessel_id"] == "v1"
    assert out["overall"]["sample_size"] == 4
    assert out["by_strategy"]["fastest"]["sample_size"] == 2
    assert out["by_strategy"]["eco"]["sample_size"] == 2
