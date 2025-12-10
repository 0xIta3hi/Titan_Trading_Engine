"""Unit tests for regime detection supervisor."""

import numpy as np
import pytest
from datetime import datetime

from src.core.engine import EventBus
from src.core.events import TickEvent, RegimeEvent
from src.strategies.supervisor import Supervisor


@pytest.mark.asyncio
async def test_supervisor_initialization(bus):
    """Test supervisor initialization."""
    supervisor = Supervisor(bus, symbol="EURUSD", buffer_size=50)

    assert supervisor.symbol == "EURUSD"
    assert supervisor.current_regime is None
    assert supervisor.price_buffer_size == 0


@pytest.mark.asyncio
async def test_supervisor_buffering(bus):
    """Test that supervisor accumulates prices in buffer."""
    supervisor = Supervisor(bus, symbol="EURUSD", buffer_size=10)

    for i in range(5):
        tick = TickEvent(
            symbol="EURUSD",
            timestamp=datetime.utcnow(),
            bid=1.0850 + i * 0.0001,
            ask=1.0855 + i * 0.0001,
        )
        await bus.publish(tick)

    assert supervisor.price_buffer_size == 5


@pytest.mark.asyncio
async def test_supervisor_ignores_other_symbols(bus):
    """Test that supervisor only processes its symbol."""
    supervisor = Supervisor(bus, symbol="EURUSD")

    tick_eurusd = TickEvent(
        symbol="EURUSD",
        timestamp=datetime.utcnow(),
        bid=1.0850,
        ask=1.0855,
    )

    tick_usdjpy = TickEvent(
        symbol="USDJPY",
        timestamp=datetime.utcnow(),
        bid=145.0,
        ask=145.1,
    )

    await bus.publish(tick_eurusd)
    await bus.publish(tick_usdjpy)

    assert supervisor.price_buffer_size == 1  # Only EURUSD


@pytest.mark.asyncio
async def test_supervisor_trending_regime(bus):
    """Test detection of trending regime (R² > 0.7)."""
    supervisor = Supervisor(bus, symbol="EURUSD", buffer_size=50, r2_trend_threshold=0.7)

    regime_events = []

    def capture_regime(event: RegimeEvent) -> None:
        regime_events.append(event)

    bus.subscribe(RegimeEvent, capture_regime)

    # Generate uptrending prices
    base_price = 1.0850
    for i in range(30):
        price = base_price + i * 0.0001  # Steady uptrend
        tick = TickEvent(
            symbol="EURUSD",
            timestamp=datetime.utcnow(),
            bid=price,
            ask=price + 0.00005,
        )
        await bus.publish(tick)

    # Should detect trending regime
    assert supervisor.current_regime == "TRENDING"
    assert supervisor.metrics["r_squared"] > 0.7


@pytest.mark.asyncio
async def test_supervisor_mean_reversion_regime(bus):
    """Test detection of mean reversion regime (|Z-score| > 2.0)."""
    supervisor = Supervisor(
        bus, symbol="EURUSD", buffer_size=20, z_score_threshold=2.0
    )

    regime_events = []

    def capture_regime(event: RegimeEvent) -> None:
        regime_events.append(event)

    bus.subscribe(RegimeEvent, capture_regime)

    # Generate data with extreme deviation
    base_price = 1.0850
    # First, establish mean
    for i in range(15):
        tick = TickEvent(
            symbol="EURUSD",
            timestamp=datetime.utcnow(),
            bid=base_price,
            ask=base_price + 0.00005,
        )
        await bus.publish(tick)

    # Then extreme deviation
    tick_extreme = TickEvent(
        symbol="EURUSD",
        timestamp=datetime.utcnow(),
        bid=base_price + 0.01,  # Huge spike
        ask=base_price + 0.01 + 0.00005,
    )
    await bus.publish(tick_extreme)

    # Should detect mean reversion regime
    assert supervisor.current_regime == "MEAN_REVERSION"
    assert abs(supervisor.metrics["z_score"]) > 2.0


@pytest.mark.asyncio
async def test_supervisor_ranging_regime(bus):
    """Test detection of ranging regime (no clear trend or reversion)."""
    supervisor = Supervisor(
        bus, symbol="EURUSD", buffer_size=20, r2_trend_threshold=0.7
    )

    # Generate flat price data (ranging)
    base_price = 1.0850
    for i in range(20):
        price = base_price + np.random.normal(0, 0.00005)
        tick = TickEvent(
            symbol="EURUSD",
            timestamp=datetime.utcnow(),
            bid=price,
            ask=price + 0.00005,
        )
        await bus.publish(tick)

    # Should detect ranging regime
    assert supervisor.current_regime == "RANGING"
    assert supervisor.metrics["r_squared"] < 0.7


def test_supervisor_metrics(bus):
    """Test metrics property returns correct data."""
    supervisor = Supervisor(bus, symbol="EURUSD")

    metrics = supervisor.metrics

    assert "regime" in metrics
    assert "r_squared" in metrics
    assert "z_score" in metrics
    assert "tick_count" in metrics
    assert "buffer_size" in metrics

    assert metrics["regime"] is None
    assert metrics["tick_count"] == 0
