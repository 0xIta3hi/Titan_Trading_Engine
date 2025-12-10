"""Core event-driven trading infrastructure."""

from src.core.engine import EventBus, setup_event_loop
from src.core.events import (
    EventType,
    TickEvent,
    SignalEvent,
    OrderRequestEvent,
    RegimeEvent,
)

__all__ = [
    "EventBus",
    "setup_event_loop",
    "EventType",
    "TickEvent",
    "SignalEvent",
    "OrderRequestEvent",
    "RegimeEvent",
]
