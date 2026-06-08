import unittest
import time
import threading
from agenteagle.event_bus.in_memory_event_bus import InMemoryEventBus
from agenteagle.event_bus.event import Event
from agenteagle.event_bus.event_registry import global_event_registry


class TestEventBus(unittest.TestCase):
    def setUp(self):
        self.event_bus = InMemoryEventBus(max_workers=2)
        self.event_bus.start()
        global_event_registry.register_event_type("test.event", "Evento de prueba")
        self.received_events = []
        self.lock = threading.Lock()

    def tearDown(self):
        self.event_bus.stop()
        self.received_events.clear()

    def _callback(self, event: Event):
        with self.lock:
            self.received_events.append(event)

    def test_publish_and_subscribe(self):
        self.event_bus.subscribe("test.event", self._callback)

        event = Event(event_type="test.event", source="test_source", payload={"key": "value"})
        self.event_bus.publish(event)

        # Esperar procesamiento asíncrono
        time.sleep(0.5)

        self.assertEqual(len(self.received_events), 1)
        self.assertEqual(self.received_events[0].event_type, "test.event")
        self.assertEqual(self.received_events[0].source, "test_source")

    def test_multiple_listeners(self):
        def callback2(event: Event):
            with self.lock:
                self.received_events.append(event)

        self.event_bus.subscribe("test.event", self._callback)
        self.event_bus.subscribe("test.event", callback2)

        event = Event(event_type="test.event", source="multi_test", payload={})
        self.event_bus.publish(event)

        time.sleep(0.5)
        self.assertEqual(len(self.received_events), 2)

    def test_unsubscribe(self):
        self.event_bus.subscribe("test.event", self._callback)
        self.event_bus.unsubscribe("test.event", self._callback)

        event = Event(event_type="test.event", source="unsub_test", payload={})
        self.event_bus.publish(event)

        time.sleep(0.5)
        self.assertEqual(len(self.received_events), 0)

    def test_concurrent_events(self):
        """Prueba de 100 eventos simultáneos"""
        self.event_bus.subscribe("test.event", self._callback)

        def publish_event(i):
            self.event_bus.publish(Event(
                event_type="test.event",
                source="concurrent_test",
                payload={"index": i}
            ))

        threads = [threading.Thread(target=publish_event, args=(i,)) for i in range(100)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Esperar a que la cola procese todo
        self.event_bus._queue.join()
        time.sleep(0.5)

        self.assertEqual(len(self.received_events), 100)


if __name__ == '__main__':
    unittest.main()