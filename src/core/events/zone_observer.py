from src.core.events.observer import Observer


class ZoneObserver(Observer):
    def update(self, event):
        zone_id = event.data.get("zone_id")
        status = event.data.get("status")

        print(f"[NOTIFICATION] Zone {zone_id} changed to {status}")
