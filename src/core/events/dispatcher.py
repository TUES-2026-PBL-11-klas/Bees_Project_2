from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from threading import Lock


class EventDispatcher:
    def __init__(self):
        self._subscribers = defaultdict(list)
        self._lock = Lock()
        self._executor = ThreadPoolExecutor(max_workers=5)

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

        for observer in observers:
            self._executor.submit(observer.update, event)
dispatcher = EventDispatcher()
