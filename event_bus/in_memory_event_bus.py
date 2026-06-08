import threading
import queue
import logging
from typing import Callable, List, Dict
from event_bus.base_event_bus import BaseEventBus
from event_bus.event import Event
from event_bus.event_registry import global_event_registry

event_logger = logging.getLogger("AgentEagle.Events")


class InMemoryEventBus(BaseEventBus):
    def __init__(self, max_workers: int = 4):
        self._subscribers: Dict[str, List[Callable[[Event], None]]] = {}
        self._lock = threading.RLock()
        self._queue: queue.Queue = queue.Queue()
        self._running = False
        self._workers: List[threading.Thread] = []
        self._max_workers = max_workers

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        for i in range(self._max_workers):
            worker = threading.Thread(target=self._process_queue, name=f"EventBusWorker-{i}", daemon=True)
            worker.start()
            self._workers.append(worker)

        event_logger.info(
            f"InMemoryEventBus iniciado con {self._max_workers} workers.",
            extra={'event_type': 'SYSTEM', 'source': 'event_bus', 'status': 'STARTED'}
        )

    def stop(self) -> None:
        self._running = False
        for _ in self._workers:
            self._queue.put(None)
        for worker in self._workers:
            worker.join(timeout=2.0)
        self._workers.clear()

        event_logger.info(
            "InMemoryEventBus detenido limpiamente.",
            extra={'event_type': 'SYSTEM', 'source': 'event_bus', 'status': 'STOPPED'}
        )

    def _process_queue(self) -> None:
        while self._running:
            try:
                item = self._queue.get(timeout=0.5)
                if item is None:
                    break
                event, callbacks = item
                self._execute_callbacks(event, callbacks)
                self._queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                event_logger.error(
                    f"Error crítico en worker del Event Bus: {e}",
                    extra={'event_type': 'SYSTEM', 'source': 'event_bus', 'status': 'ERROR'},
                    exc_info=True
                )

    def _execute_callbacks(self, event: Event, callbacks: List[Callable]) -> None:
        for callback in callbacks:
            try:
                callback(event)
                event_logger.info(
                    "Evento procesado correctamente",
                    extra={'event_type': event.event_type, 'source': event.source, 'status': 'SUCCESS'}
                )
            except Exception as e:
                event_logger.error(
                    f"Error en callback: {e}",
                    extra={'event_type': event.event_type, 'source': event.source, 'status': 'FAILED'}
                )

    def publish(self, event: Event) -> None:
        if not global_event_registry.is_valid_type(event.event_type):
            event_logger.warning(
                f"Evento no registrado publicado: {event.event_type}",
                extra={'event_type': event.event_type, 'source': event.source, 'status': 'WARNING'}
            )
            global_event_registry.register_event_type(event.event_type, "Auto-registrado dinámicamente")

        with self._lock:
            callbacks = self._subscribers.get(event.event_type, []).copy()

        if callbacks:
            self._queue.put((event, callbacks))
        else:
            event_logger.debug(
                f"Evento '{event.event_type}' publicado sin suscriptores.",
                extra={'event_type': event.event_type, 'source': event.source, 'status': 'DEBUG'}
            )

    def subscribe(self, event_type: str, callback: Callable[[Event], None]) -> None:
        if not global_event_registry.is_valid_type(event_type):
            global_event_registry.register_event_type(event_type, "Auto-registrado dinámicamente")

        with self._lock:
            if event_type not in self._subscribers:
                self._subscribers[event_type] = []
            if callback not in self._subscribers[event_type]:
                self._subscribers[event_type].append(callback)
                event_logger.debug(
                    f"Suscripción añadida: {callback.__name__} -> {event_type}",
                    extra={'event_type': event_type, 'source': 'event_bus', 'status': 'SUBSCRIBED'}
                )

    def unsubscribe(self, event_type: str, callback: Callable[[Event], None]) -> None:
        with self._lock:
            if event_type in self._subscribers:
                try:
                    self._subscribers[event_type].remove(callback)
                    event_logger.debug(
                        f"Suscripción eliminada: {callback.__name__} <- {event_type}",
                        extra={'event_type': event_type, 'source': 'event_bus', 'status': 'UNSUBSCRIBED'}
                    )
                except ValueError:
                    pass