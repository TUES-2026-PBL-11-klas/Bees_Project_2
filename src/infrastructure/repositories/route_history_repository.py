import logging
from typing import List, Optional

from src.models.route_history import RouteHistory

logger = logging.getLogger(__name__)


class RouteHistoryRepository:
    """Data-access layer for the RouteHistory collection."""

    def create(self, data: dict) -> RouteHistory:
        """Persist a new route-history record."""
        history = RouteHistory(**data)
        history.save()
        return history

    def get_by_id(self, history_id: str) -> Optional[RouteHistory]:
        """Fetch a single history record by its document ID."""
        return RouteHistory.objects(id=history_id).first()

    def get_by_vessel(self, vessel_id: str, limit: int = 50) -> List[RouteHistory]:
        """Return the most recent history entries for a given vessel."""
        return list(
            RouteHistory.objects(vessel_id=vessel_id)
            .order_by("-calculated_at")
            .limit(limit)
        )

    def get_by_company(self, company_id: str, limit: int = 50) -> List[RouteHistory]:
        """Return the most recent history entries for a given company."""
        return list(
            RouteHistory.objects(company_id=company_id)
            .order_by("-calculated_at")
            .limit(limit)
        )

    def get_recent(self, limit: int = 20) -> List[RouteHistory]:
        """Return the most recent history entries across all vessels."""
        return list(
            RouteHistory.objects()
            .order_by("-calculated_at")
            .limit(limit)
        )
