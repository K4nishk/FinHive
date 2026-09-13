"""Container and event bus tests."""
import pytest

from loan_manager.application.event_bus import EventBus


class TestEventBus:
    def test_subscribe_and_publish(self):
        bus = EventBus()
        received = []

        class MyEvent:
            pass

        bus.subscribe(MyEvent, lambda e: received.append(e))

        event = MyEvent()
        bus.publish(event)
        assert len(received) == 1
        assert received[0] is event

    def test_publish_no_subscribers(self):
        bus = EventBus()

        class MyEvent:
            pass

        # Should not raise
        bus.publish(MyEvent())

    def test_multiple_subscribers(self):
        bus = EventBus()
        received_a = []
        received_b = []

        class MyEvent:
            pass

        bus.subscribe(MyEvent, lambda e: received_a.append(1))
        bus.subscribe(MyEvent, lambda e: received_b.append(2))

        bus.publish(MyEvent())
        assert len(received_a) == 1
        assert len(received_b) == 1
