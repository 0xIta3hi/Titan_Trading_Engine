"""
High-performance async EventBus for the Titan trading engine.

Features:
- Pub/Sub pattern with type-safe subscribers.
- Auto-detection and installation of uvloop for production performance.
- Non-blocking async event dispatch.
- Task-safe subscriber management.
"""

import asyncio
import logging
from collections import defaultdict
from typing import Any, Callable, Type, TypeVar

# Attempt to use uvloop for faster event loop if available
try:
    import uvloop

    UVLOOP_AVAILABLE = True
except ImportError:
    UVLOOP_AVAILABLE = False

__all__ = ["EventBus", "setup_event_loop"]

logger = logging.getLogger(__name__)

T = TypeVar("T")
EventHandler = Callable[[Any], Any]


class EventBus:
    """
    Thread-safe, async-friendly event bus for Pub/Sub messaging.

    Supports multiple subscribers per event type with FIFO dispatch.
    Handlers are awaited if they are coroutines.

    Example:
        bus = EventBus()
        bus.subscribe(TickEvent, tick_handler)
        await bus.publish(tick_event)
    """

    def __init__(self) -> None:
        """Initialize the event bus with empty subscriber registry."""
        self._subscribers: dict[Type[Any], list[EventHandler]] = defaultdict(list)
        self._lock = asyncio.Lock()

    def subscribe(self, event_type: Type[T], handler: EventHandler) -> Callable[[], None]:
        """
        Subscribe a handler to an event type.

        Args:
            event_type: The event class to listen for (e.g., TickEvent).
            handler: Async or sync callable that receives the event.

        Returns:
            Unsubscribe function to remove this handler.

        Example:
            def on_tick(event: TickEvent) -> None:
                print(f"Tick: {event.symbol} @ {event.mid_price}")

            unsub = bus.subscribe(TickEvent, on_tick)
            # Later: unsub() to remove
        """
        self._subscribers[event_type].append(handler)

        def unsubscribe() -> None:
            self._subscribers[event_type].remove(handler)

        return unsubscribe

    async def publish(self, event: Any) -> None:
        """
        Publish an event to all subscribers.

        Handlers are dispatched sequentially in subscription order.
        If a handler is async, it is awaited. Exceptions in handlers
        are logged but do not block other subscribers.

        Args:
            event: The event instance to publish.
        """
        event_type = type(event)
        handlers = self._subscribers.get(event_type, [])

        if not handlers:
            logger.debug(f"No subscribers for {event_type.__name__}")
            return

        async with self._lock:
            for handler in handlers:
                try:
                    result = handler(event)
                    # If handler is async, await it
                    if hasattr(result, "__await__"):
                        await result
                except Exception as e:
                    logger.exception(
                        f"Error in {handler.__name__} while handling {event_type.__name__}: {e}"
                    )

    def subscriber_count(self, event_type: Type[T]) -> int:
        """
        Get the number of subscribers for an event type.

        Args:
            event_type: The event class to check.

        Returns:
            Number of currently registered handlers.
        """
        return len(self._subscribers.get(event_type, []))


def setup_event_loop() -> None:
    """
    Configure the asyncio event loop for production use.

    Attempts to use uvloop if available (faster than stdlib asyncio).
    Falls back to stdlib event loop if uvloop is not installed.

    This should be called at application startup.

    Example:
        setup_event_loop()
        asyncio.run(main())
    """
    if UVLOOP_AVAILABLE:
        asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
        logger.info("✓ uvloop event loop policy installed (high-performance mode)")
    else:
        logger.warning(
            "⚠ uvloop not available; using stdlib asyncio. "
            "For production, install uvloop: pip install uvloop"
        )
