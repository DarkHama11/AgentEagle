import logging
import threading
import uuid
from typing import Dict, List, Callable, Any

logger = logging.getLogger(__name__)

class EventBus:
    def __init__(self):
        self._subscribers: Dict[str, List[Callable]] = {}
        self._lock = threading.Lock()

    def subscribe(self, event_type: str, callback: Callable):
        with self._lock:
            if event_type not in self._subscribers:
                self._subscribers[event_type] = []
            self._subscribers[event_type].append(callback)
        logger.debug(f"[EventBus] Suscrito a: {event_type}")

    def publish(self, event_type: str, payload: Dict[str, Any]):
        logger.info(f"[EventBus] Publicando evento: {event_type}")
        with self._lock:
            callbacks = list(self._subscribers.get(event_type, []))

        event_data = {"type": event_type, "payload": payload, "id": str(uuid.uuid4())}
        for callback in callbacks:
            try:
                callback(event_data)
            except Exception as e:
                logger.error(f"[EventBus] Error en suscriptor: {e}", exc_info=True)
