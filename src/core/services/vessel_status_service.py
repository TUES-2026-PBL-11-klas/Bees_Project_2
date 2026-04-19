import threading
from typing import Optional

from src.infrastructure.repositories.vessel_repository import VesselRepository
from src.models.vessel import Vessel


class VesselStatusService:
    """Thread-safe service for vessel status updates.

    The lock protects the full read-modify-write cycle for updating
    `current_status`. The protected critical section covers:
      1. loading the vessel from the repository,
      2. applying the status update,
      3. reloading the updated vessel before returning it.
    """

    def __init__(self, repository: VesselRepository):
        self._repository = repository
        self._status_lock = threading.Lock()

    def update_vessel(self, vessel_id: str, data: dict) -> Optional[Vessel]:
        if "current_status" in data:
            return self.update_status(vessel_id, data)
        return self._repository.update(vessel_id, data)

    def update_status(self, vessel_id: str, data: dict) -> Optional[Vessel]:
        with self._status_lock:
            vessel = self._repository.get_by_id(vessel_id)
            if not vessel:
                return None

            vessel.update(**data)
            vessel.reload()
            return vessel
