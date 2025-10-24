from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any, Callable, Dict, List


class EventBus:
    """A simple in-memory event bus for publishing and subscribing to events."""

    def __init__(self):
        """Initializes the EventBus with an empty dictionary of subscribers."""
        self._subscribers: Dict[str, List[Callable[[Any], Any]]] = defaultdict(list)

    def subscribe(self, event_type: str, callback: Callable[[Any], Any]):
        """Subscribes a callback function to a specific event type.

        Args:
            event_type: The type of event to subscribe to.
            callback: The function to call when the event is published.
        """
        self._subscribers[event_type].append(callback)

    def unsubscribe(self, event_type: str, callback: Callable[[Any], Any]):
        """Unsubscribes a callback function from a specific event type.

        Args:
            event_type: The type of event to unsubscribe from.
            callback: The function to remove from the subscribers.
        """
        if callback in self._subscribers[event_type]:
            self._subscribers[event_type].remove(callback)

    async def publish(self, event_type: str, data: Any):
        """Publishes an event to all subscribed callback functions.

        Args:
            event_type: The type of event to publish.
            data: The data associated with the event.
        """
        for callback in self._subscribers[event_type]:
            # Run callbacks concurrently if they are async
            if asyncio.iscoroutinefunction(callback):
                asyncio.create_task(callback(data))
            else:
                callback(data)


# Global instance of the event bus
event_bus = EventBus()
