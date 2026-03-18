from abc import ABC, abstractmethod

class Observer(ABC):
    @abstractmethod
    def update(self, zone_id: str, status: str):
        pass
