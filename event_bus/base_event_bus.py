from abc import ABC, abstractmethod
from typing import Callable
from .event import Event

class BaseEventBus(ABC):
    """Interfaz abstracta para el bus de eventos."""

    @abstractmethod
    def publish(self, event: Event) -> None:
        """Publica un evento en el bus."""
        pass

    @abstractmethod
    def subscribe(self, event_type: str, callback: Callable[[Event], None]) -> None:
        """Suscribe un callback a un tipo de evento específico."""
        pass

    @abstractmethod
    def unsubscribe(self, event_type: str, callback: Callable[[Event], None]) -> None:
        """Desuscribe un callback de un tipo de evento."""
        pass

    @abstractmethod
    def start(self) -> None:
        """Inicia los procesos en segundo plano del bus (ej: workers)."""
        pass

    @abstractmethod
    def stop(self) -> None:
        """Detiene limpiamente los procesos del bus."""
        pass