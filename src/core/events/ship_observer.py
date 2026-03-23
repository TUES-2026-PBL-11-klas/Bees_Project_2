from core.events.observer import Observer


class ShipObserver(Observer):
    def __init__(self, ship_id: str):
        self.ship_id = ship_id

    def update(self, event):
        print(f"[Ship {self.ship_id}] received event: {event.event_type} | data: {event.data}")
