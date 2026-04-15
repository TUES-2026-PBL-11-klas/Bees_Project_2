import threading
import time

from src.core.services.vessel_status_service import VesselStatusService


class DummyVessel:
    def __init__(self, status: str):
        self.current_status = status

    def update(self, **data):
        self.current_status = data["current_status"]

    def reload(self):
        return self


class OverlapRepository:
    def __init__(self):
        self.vessel = DummyVessel("idle")
        self.updating = False
        self.overlap_detected = False

    def get_by_id(self, vessel_id: str):
        return self.vessel

    def update(self, vessel_id: str, data: dict):
        if self.updating:
            self.overlap_detected = True
        self.updating = True
        try:
            time.sleep(0.02)
            self.vessel.update(**data)
            return self.vessel
        finally:
            self.updating = False


def test_parallel_status_updates_are_serialized_by_lock():
    repo = OverlapRepository()
    service = VesselStatusService(repo)
    statuses = [f"status_{i}" for i in range(10)]

    threads = []
    for status in statuses:
        thread = threading.Thread(
            target=lambda status=status: service.update_vessel("vessel-1", {"current_status": status})
        )
        threads.append(thread)
        thread.start()

    for thread in threads:
        thread.join()

    assert repo.overlap_detected is False
    assert repo.vessel.current_status in statuses
