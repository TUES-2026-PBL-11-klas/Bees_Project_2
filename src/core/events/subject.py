from typing import List
from threading import Lock
from core.events.observer import Observer

class Zone:
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
        from core.events.dispatcher import dispatch_notification
        for observer in self._observers:
            dispatch_notification(observer, self.zone_id, self.status)

    def set_status(self, new_status: str):
        with self._lock:
            self.status = new_status
        self.notify()
