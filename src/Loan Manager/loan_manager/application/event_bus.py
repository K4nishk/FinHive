from collections import defaultdict
from typing import Any, Callable


class EventBus:
    def __init__(self) -> None:
        self._handlers: dict[type, list[Callable]] = defaultdict(list)

    def subscribe(self, event_type: type, handler: Callable) -> None:
        self._handlers[event_type].append(handler)

    def publish(self, event: Any) -> None:
        for handler in self._handlers.get(type(event), []):
            handler(event)
