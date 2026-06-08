import json
import logging
import threading
from typing import Callable, Dict
import redis
from event_bus.base_event_bus import BaseEventBus      # <-- CAMBIO AQUÍ
from event_bus.event import Event                      # <-- CAMBIO AQUÍ
from event_bus.event_registry import global_event_registry # <-- CAMBIO AQUÍ

event_logger = logging.getLogger("AgentEagle.Events")

class RedisEventBus(BaseEventBus):
    def __init__(self, redis_url: str = "redis://localhost:6379/0", prefix: str = "agenteagle"):
        self.redis_url = redis_url
        self.prefix = prefix
        self._redis_client: redis.Redis = redis.from_url(redis_url, decode_responses=True)
        self._pubsub = self._redis_client.pubsub()
        self._running = False
        self._listener_thread: threading.Thread = None
        self._callbacks: Dict[str, Callable[[Event], None]] = {}

    def _get_channel(self, event_type: str) -> str:
        return f"{self.prefix}:{event_type}"

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._listener_thread = threading.Thread(target=self._listen, daemon=True)
        self._listener_thread.start()
        event_logger.info("RedisEventBus iniciado y escuchando.")

    def stop(self) -> None:
        self._running = False
        if self._pubsub:
            self._pubsub.close()
        if self._listener_thread:
            self._listener_thread.join(timeout=2.0)
        event_logger.info("RedisEventBus detenido.")

    def _listen(self) -> None:
        while self._running:
            try:
                message = self._pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if message and message['type'] == 'message':
                    channel = message['channel']
                    event_type = channel.replace(f"{self.prefix}:", "", 1)
                    try:
                        data = json.loads(message['data'])
                        event = Event(
                            event_id=data['event_id'],
                            event_type=data['event_type'],
                            source=data['source'],
                            payload=data['payload']
                        )
                        self._execute_callback(event_type, event)
                    except json.JSONDecodeError as e:
                        event_logger.error(f"Error decodificando evento de Redis: {e}")
            except redis.ConnectionError as e:
                event_logger.error(f"Error de conexión con Redis: {e}")
                break

    def _execute_callback(self, event_type: str, event: Event) -> None:
        callback = self._callbacks.get(event_type)
        if callback:
            try:
                callback(event)
                event_logger.info(f"{event.timestamp.isoformat()} | {event.event_type} | {event.source} | SUCCESS | Evento procesado (Redis)")
            except Exception as e:
                event_logger.error(f"{event.timestamp.isoformat()} | {event.event_type} | {event.source} | FAILED | Error en callback: {e}")

    def publish(self, event: Event) -> None:
        channel = self._get_channel(event.event_type)
        try:
            self._redis_client.publish(channel, json.dumps(event.to_dict()))
        except redis.ConnectionError as e:
            event_logger.error(f"Fallo al publicar en Redis: {e}")

    def subscribe(self, event_type: str, callback: Callable[[Event], None]) -> None:
        if not global_event_registry.is_valid_type(event_type):
            global_event_registry.register_event_type(event_type, "Auto-registrado dinámicamente")
        channel = self._get_channel(event_type)
        self._pubsub.subscribe(**{channel: lambda msg: None})
        self._callbacks[event_type] = callback
        event_logger.debug(f"Suscripción Redis añadida: {channel}")

    def unsubscribe(self, event_type: str, callback: Callable[[Event], None]) -> None:
        channel = self._get_channel(event_type)
        self._pubsub.unsubscribe(channel)
        if event_type in self._callbacks:
            del self._callbacks[event_type]
        event_logger.debug(f"Suscripción Redis eliminada: {channel}")