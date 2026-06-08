import logging
from typing import Any, Dict
from core.event_bus import EventBus

logger = logging.getLogger(__name__)

class BaseAgent:
    def __init__(self, name: str, event_bus: EventBus):
        self.name = name
        self.event_bus = event_bus
        logger.info(f"[{self.name}] Inicializado.")

    def subscribe(self, event_type: str, callback: Any):
        self.event_bus.subscribe(event_type, callback)

    def publish(self, event_type: str, payload: Dict[str, Any]):
        self.event_bus.publish(event_type, payload)
