"""Unit tests for event-driven architecture."""

import pytest
from datetime import datetime

from src.core.engine import EventBus
from src.core.events import TickEvent, SignalEvent, OrderRequestEvent


@pytest.mark.asyncio
async def test_eventbus_pub_sub():
    """Test basic pub/sub functionality."""
    bus = EventBus()
    received_events = []

    def handler(event: TickEvent) -> None:
        received_events.append(event)

    bus.subscribe(TickEvent, handler)

    tick = TickEvent(
        symbol="EURUSD",
        timestamp=datetime.utcnow(),
        bid=1.0850,
        ask=1.0855,
    )

    await bus.publish(tick)

    assert len(received_events) == 1
    assert received_events[0].symbol == "EURUSD"


@pytest.mark.asyncio
async def test_multiple_subscribers():
    """Test that multiple subscribers receive the same event."""
    bus = EventBus()
    results = {"handler1": [], "handler2": []}

    def handler1(event: TickEvent) -> None:
        results["handler1"].append(event)

    def handler2(event: TickEvent) -> None:
        results["handler2"].append(event)

    bus.subscribe(TickEvent, handler1)
    bus.subscribe(TickEvent, handler2)

    tick = TickEvent(
        symbol="EURUSD",
        timestamp=datetime.utcnow(),
        bid=1.0850,
        ask=1.0855,
    )

    await bus.publish(tick)

    assert len(results["handler1"]) == 1
    assert len(results["handler2"]) == 1


@pytest.mark.asyncio
async def test_unsubscribe():
    """Test unsubscribe functionality."""
    bus = EventBus()
    received = []

    def handler(event: TickEvent) -> None:
        received.append(event)

    unsub = bus.subscribe(TickEvent, handler)

    tick = TickEvent(
        symbol="EURUSD",
        timestamp=datetime.utcnow(),
        bid=1.0850,
        ask=1.0855,
    )

    await bus.publish(tick)
    assert len(received) == 1

    unsub()

    await bus.publish(tick)
    assert len(received) == 1  # Should still be 1, handler removed


@pytest.mark.asyncio
async def test_async_handler():
    """Test that async handlers are properly awaited."""
    bus = EventBus()
    received = []

    async def async_handler(event: TickEvent) -> None:
        received.append(event)

    bus.subscribe(TickEvent, async_handler)

    tick = TickEvent(
        symbol="EURUSD",
        timestamp=datetime.utcnow(),
        bid=1.0850,
        ask=1.0855,
    )

    await bus.publish(tick)

    assert len(received) == 1


@pytest.mark.asyncio
async def test_subscriber_count():
    """Test subscriber count tracking."""
    bus = EventBus()

    def handler1(event: TickEvent) -> None:
        pass

    def handler2(event: TickEvent) -> None:
        pass

    assert bus.subscriber_count(TickEvent) == 0

    bus.subscribe(TickEvent, handler1)
    assert bus.subscriber_count(TickEvent) == 1

    bus.subscribe(TickEvent, handler2)
    assert bus.subscriber_count(TickEvent) == 2


def test_event_immutability():
    """Test that events are immutable (frozen dataclass)."""
    tick = TickEvent(
        symbol="EURUSD",
        timestamp=datetime.utcnow(),
        bid=1.0850,
        ask=1.0855,
    )

    with pytest.raises(Exception):  # FrozenInstanceError
        tick.bid = 1.0900  # type: ignore


def test_event_properties():
    """Test event property calculations."""
    tick = TickEvent(
        symbol="EURUSD",
        timestamp=datetime.utcnow(),
        bid=1.0850,
        ask=1.0855,
    )

    assert abs(tick.mid_price - 1.08525) < 1e-5
    assert abs(tick.spread - 50.0) < 0.1  # 50 pips


def test_signal_event_validation():
    """Test that SignalEvent validates confidence."""
    # Valid confidence
    signal = SignalEvent(
        symbol="EURUSD",
        timestamp=datetime.utcnow(),
        direction="BUY",
        confidence=0.75,
        regime="TRENDING",
        price=1.0850,
    )
    assert signal.confidence == 0.75

    # Invalid confidence > 1.0
    with pytest.raises(ValueError):
        SignalEvent(
            symbol="EURUSD",
            timestamp=datetime.utcnow(),
            direction="BUY",
            confidence=1.5,
            regime="TRENDING",
            price=1.0850,
        )

    # Invalid confidence < 0.0
    with pytest.raises(ValueError):
        SignalEvent(
            symbol="EURUSD",
            timestamp=datetime.utcnow(),
            direction="BUY",
            confidence=-0.1,
            regime="TRENDING",
            price=1.0850,
        )
