from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from event_bus.base_event_bus import BaseEventBus  # <-- CAMBIO AQUÍ


class BaseAgent(ABC):
    """Clase base abstracta para todos los agentes."""

    name: str = "base_agent"
    description: str = "Descripción base del agente"
    capabilities: List[str] = []

    def __init__(self, event_bus: Optional[BaseEventBus] = None):
        self.event_bus = event_bus

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if cls.name == "base_agent":
            raise ValueError(f"La clase {cls.__name__} debe definir el atributo de clase 'name'.")
        if not cls.description or cls.description == "Descripción base del agente":
            raise ValueError(f"La clase {cls.__name__} debe definir el atributo de clase 'description'.")

    @abstractmethod
    def execute(self, action: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        pass