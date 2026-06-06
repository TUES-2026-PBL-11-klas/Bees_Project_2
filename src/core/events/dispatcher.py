import asyncio
import logging
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from src.infrastructure.repositories.audit_log_repository import AuditLogRepository

logger = logging.getLogger(__name__)


class EventDispatcher:
    def __init__(self):
        self._subscribers = defaultdict(list)
        self._lock = Lock()
        self._audit_repo = AuditLogRepository()
        self._executor = ThreadPoolExecutor(max_workers=5)
        self._ws_manager = None

    def set_ws_manager(self, ws_manager):
        """Attach a WebSocketManager for real-time event broadcasting."""
        self._ws_manager = ws_manager

    def subscribe(self, event_type: str, observer):
        with self._lock:
            if observer not in self._subscribers[event_type]:
                self._subscribers[event_type].append(observer)

    def unsubscribe(self, event_type: str, observer):
        with self._lock:
            if observer in self._subscribers[event_type]:
                self._subscribers[event_type].remove(observer)

    def dispatch(self, event):
        observers = self._subscribers.get(event.event_type, [])

        self._audit_repo.create_log(event.event_type, event.data)
        self._audit_repo.create_log(
            event_type=event.event_type,
            data=event.data,
            entity_id=event.data.get("zone_id")
        )

        for observer in observers:
            self._executor.submit(observer.update, event)

        if self._ws_manager:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(
                        self._ws_manager.broadcast({
                            "event_type": event.event_type,
                            "payload": event.data,
                        })
                    )
            except RuntimeError:
                pass  # No event loop running (e.g., in tests)

dispatcher = EventDispatcher()
