import logging
from typing import List, Dict, Any

logger = logging.getLogger("AgentEagle.EventRegistry")


class EventRegistry:
    """Registro central de tipos de eventos permitidos en el sistema."""

    def __init__(self):
        self._registered_types: Dict[str, Dict[str, Any]] = {}

    def register_event_type(self, event_type: str, description: str) -> None:
        """Registra un nuevo tipo de evento con su descripción."""
        if event_type in self._registered_types:
            logger.warning(f"El tipo de evento '{event_type}' ya está registrado. Sobrescribiendo.")

        self._registered_types[event_type] = {
            "event_type": event_type,
            "description": description
        }
        logger.debug(f"Tipo de evento registrado: {event_type}")

    def list_event_types(self) -> List[Dict[str, Any]]:
        """Retorna todos los tipos de eventos registrados."""
        return list(self._registered_types.values())

    def is_valid_type(self, event_type: str) -> bool:
        """Valida si un tipo de evento está registrado."""
        return event_type in self._registered_types


# Instancia global singleton para uso compartido
global_event_registry = EventRegistry()