"""
Titan Trading Engine - Entry Point

Phase 2: Real market data integration with MetaTrader 5.

Demonstrates:
1. EventBus pub/sub architecture.
2. Real-time regime detection (trending vs mean reversion).
3. Risk-managed order generation.
4. Live market data from MetaTrader 5.

Run: python main.py
"""

import asyncio
import logging
from datetime import datetime

from src.core.engine import EventBus, setup_event_loop
from src.core.events import TickEvent, SignalEvent, OrderRequestEvent, RegimeEvent
from src.core.feed import DataFeed
from src.strategies.supervisor import Supervisor
from src.strategies.math_utils import calculate_z_score
from src.execution.risk import RiskManager

# ============================================================================
# Configuration
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# Trading instruments
INSTRUMENTS = ["EURUSD", "USDJPY", "XAUUSD"]

# Account parameters
ACCOUNT_BALANCE = 100_000.0  # $100k paper trading
MAX_RISK_PER_TRADE = 500.0   # $500 per trade
MAX_DAILY_RISK = 2_000.0     # $2k per day

# Session duration
SESSION_DURATION_SECONDS = 3600  # Run for 1 hour (can be changed)

# ============================================================================
# Signal Generation (Simple Regime-Based Strategy)
# ============================================================================


class SimpleStrategy:
    """
    Simple strategy that generates signals based on regime events.

    When TRENDING regime: Generate BUY signals on uptrend, SELL on downtrend.
    When MEAN_REVERSION: Generate signals opposite to deviation direction.
    """

    def __init__(self, bus: EventBus, symbol: str) -> None:
        self.bus = bus
        self.symbol = symbol
        self._last_z_score = 0.0

        # Listen to regime changes
        self.bus.subscribe(RegimeEvent, self._on_regime_event)

    def _on_regime_event(self, event: RegimeEvent) -> None:
        """
        Generate trading signals based on regime detection.

        Args:
            event: RegimeEvent from supervisor.
        """
        if event.symbol != self.symbol:
            return

        logger.debug(
            f"{self.symbol}: Regime event: {event.regime_type} "
            f"(R²={event.r_squared:.3f}, Z={event.z_score:.2f})"
        )

        self._last_z_score = event.z_score

        # Generate signals based on regime
        if event.regime_type == "TRENDING":
            # Trend following: buy if uptrend, sell if downtrend
            direction = "BUY"  # Assume uptrend
            confidence = min(event.r_squared, 1.0)  # R² as confidence
        elif event.regime_type == "MEAN_REVERSION":
            # Counter-trend: fade the move
            if event.z_score > 0:
                direction = "SELL"  # Price too high, sell
            else:
                direction = "BUY"  # Price too low, buy
            confidence = min(abs(event.z_score) / 3.0, 1.0)  # |Z|/3 as confidence
        else:
            # RANGING: Uncertain, neutral signal
            logger.debug(f"{self.symbol}: Ranging market, skipping signal")
            return

        # Create and publish signal
        signal = SignalEvent(
            symbol=event.symbol,
            timestamp=event.timestamp,
            direction=direction,  # type: ignore
            confidence=confidence,
            regime=event.regime_type,
            price=100.0,  # Placeholder; actual price from tick
        )

        logger.info(
            f"{self.symbol}: Signal → {direction} ({confidence:.2%} confidence, {event.regime_type})"
        )

        import asyncio

        try:
            loop = asyncio.get_running_loop()
            asyncio.create_task(self.bus.publish(signal))
        except RuntimeError:
            logger.debug("No running loop for signal publish")


# ============================================================================
# Event Logging
# ============================================================================


def setup_event_logging(bus: EventBus) -> None:
    """
    Subscribe logging handlers to key events.

    Args:
        bus: EventBus to attach to.
    """

    def log_tick(event: TickEvent) -> None:
        logger.debug(f"✓ {event.symbol}: {event.mid_price:.5f} (spread: {event.spread:.1f} pips)")

    def log_signal(event: SignalEvent) -> None:
        logger.info(f"📊 {event.symbol}: SIGNAL {event.direction} ({event.confidence:.0%}) [{event.regime}]")

    def log_order(event: OrderRequestEvent) -> None:
        logger.info(
            f"📋 {event.symbol}: ORDER {event.direction} {event.quantity:.4f} "
            f"@ {event.price:.5f} (risk: ${event.risk_amount:.2f})"
        )

    def log_regime(event: RegimeEvent) -> None:
        logger.info(f"🔄 {event.symbol}: REGIME {event.regime_type} (R²={event.r_squared:.3f})")

    bus.subscribe(TickEvent, log_tick)
    bus.subscribe(SignalEvent, log_signal)
    bus.subscribe(OrderRequestEvent, log_order)
    bus.subscribe(RegimeEvent, log_regime)


# ============================================================================
# Main Integration
# ============================================================================


async def main() -> None:
    """
    Main async entry point: orchestrate the trading engine with real MT5 data.

    Sets up:
    1. EventBus with uvloop.
    2. MetaTrader 5 data feed for real market prices.
    3. Supervisors for regime detection.
    4. RiskManager for position validation.
    5. Simple strategy for signal generation.
    6. Real-time monitoring and logging.
    """
    logger.info("=" * 70)
    logger.info("Titan Trading Engine - Phase 2: Real Market Integration (MT5)")
    logger.info("=" * 70)

    # Setup event loop for high performance
    setup_event_loop()

    # Create event bus
    bus = EventBus()
    logger.info(f"✓ EventBus initialized")

    # Setup event logging
    setup_event_logging(bus)

    # Initialize data feed (real MT5 prices)
    logger.info(f"Connecting to MetaTrader 5...")
    data_feed = DataFeed(bus, symbols=INSTRUMENTS)
    logger.info(f"✓ DataFeed initialized for {INSTRUMENTS}")

    # Initialize supervisors (regime detectors)
    supervisors = {}
    for symbol in INSTRUMENTS:
        supervisor = Supervisor(
            bus,
            symbol=symbol,
            buffer_size=50,
            r2_trend_threshold=0.7,
            z_score_threshold=2.0,
        )
        supervisors[symbol] = supervisor
        logger.info(f"✓ Supervisor initialized for {symbol}")

    # Initialize risk manager
    risk_manager = RiskManager(
        bus,
        account_balance=ACCOUNT_BALANCE,
        max_risk_per_trade=MAX_RISK_PER_TRADE,
        max_daily_risk=MAX_DAILY_RISK,
    )
    logger.info(f"✓ RiskManager initialized (balance: ${ACCOUNT_BALANCE:,.2f})")

    # Initialize strategies
    strategies = {}
    for symbol in INSTRUMENTS:
        strategy = SimpleStrategy(bus, symbol)
        strategies[symbol] = strategy
        logger.info(f"✓ Strategy initialized for {symbol}")

    logger.info("=" * 70)
    logger.info(f"Starting live market session ({SESSION_DURATION_SECONDS}s)...")
    logger.info("=" * 70)

    # Start the data feed
    feed_task = asyncio.create_task(data_feed.start_stream())

    # Run for specified duration
    try:
        await asyncio.sleep(SESSION_DURATION_SECONDS)
    except KeyboardInterrupt:
        logger.info("\n⏸ Session interrupted by user")
    finally:
        # Stop the feed
        data_feed.stop()
        await feed_task

    # Final summary
    logger.info("=" * 70)
    logger.info("Session Complete - Final Metrics")
    logger.info("=" * 70)

    for symbol, supervisor in supervisors.items():
        metrics = supervisor.metrics
        logger.info(
            f"{symbol}: Regime={metrics['regime']}, "
            f"R²={metrics['r_squared']:.3f}, Z={metrics['z_score']:.2f}, "
            f"Ticks={metrics['tick_count']}"
        )

    risk_report = risk_manager.report()
    logger.info(
        f"\nRisk Report:\n"
        f"  Balance: ${risk_report['account_balance']:,.2f}\n"
        f"  Daily Loss: ${risk_report['daily_loss']:.2f}\n"
        f"  Remaining Daily Risk: ${risk_report['remaining_daily_risk']:.2f}\n"
        f"  Open Trades: {risk_report['open_trades']}\n"
        f"  Total Orders: {risk_report['total_orders']}"
    )

    logger.info("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
