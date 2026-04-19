from src.core.events.dispatcher import EventDispatcher
from src.core.events.zone_observer import ZoneObserver

dispatcher = EventDispatcher()

zone_observer = ZoneObserver()

dispatcher.subscribe("ZONE_STATUS_CHANGED", zone_observer)
