from typing import List
from threading import Lock
from src.core.events.observer import Observer

class ZoneSubject:
    def __init__(self, zone_id: str):
        self.zone_id = zone_id
        self.status = "open"
        self._observers: List[Observer] = []
        self._lock = Lock()

    def attach(self, observer: Observer):
        with self._lock:
            self._observers.append(observer)

    def detach(self, observer: Observer):
        with self._lock:
            self._observers.remove(observer)

    def notify(self):
        from src.core.events.dispatcher import dispatcher
        from src.core.events.event import Event

        event = Event(
            event_type="ZONE_STATUS_CHANGED",
            data={"zone_id": self.zone_id, "status": self.status}
        )
        dispatcher.dispatch(event)

    def set_status(self, new_status: str):
        with self._lock:
            self.status = new_status
        self.notify()
