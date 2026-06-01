import logging

from src.core.events.observer import Observer
from src.core.events.dispatcher import dispatcher

logger = logging.getLogger(__name__)

# AI event types this observer reacts to
AI_EVENT_TYPES = (
    "ZONE_STATUS_CHANGED",
    "zone_closed",
    "zone_opened",
    "storm",
    "vessel_anomaly",
    "weather_alert",
)


class AIObserver(Observer):
    """
    Event observer that routes dispatched events to the AI module.

    When a relevant event fires (zone status change, vessel anomaly, storm,
    etc.) this observer delegates to AIService for reroute evaluation,
    anomaly logging, and recommendation generation.
    """

    def __init__(self):
        self._ai_service = None  # lazy-loaded to avoid circular imports

    @property
    def ai_service(self):
        if self._ai_service is None:
            from src.core.services.ai.ai_service import AIService
            self._ai_service = AIService()
        return self._ai_service

    def update(self, event):
        """Called by the EventDispatcher when a subscribed event fires."""
        logger.info(
            "[AIObserver] Processing event: %s | data: %s",
            event.event_type,
            event.data,
        )
        try:
            self.ai_service.process_event(event)
        except Exception as exc:
            logger.error(
                "[AIObserver] Error processing event %s: %s",
                event.event_type,
                exc,
                exc_info=True,
            )


def register_ai_observer():
    """
    Subscribe the AIObserver to all relevant event types on the
    global dispatcher.  Call this once during application startup.
    """
    ai_observer = AIObserver()
    for event_type in AI_EVENT_TYPES:
        dispatcher.subscribe(event_type, ai_observer)
    logger.info(
        "[AIObserver] Registered for %d event types", len(AI_EVENT_TYPES)
    )
    return ai_observer
