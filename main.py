"""
Titan Trading Engine - Entry Point

Phase 2: Real market data integration with MetaTrader 5 + Comprehensive Analytics.

Demonstrates:
1. EventBus pub/sub architecture.
2. Real-time regime detection (trending vs mean reversion).
3. Risk-managed order generation.
4. Live market data from MetaTrader 5.
5. OHLCV market analytics.
6. P&L tracking, Sharpe ratio, drawdown analysis.
7. Real-time metrics reporting.

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
from src.strategies.mtf_analyzer import MTFAnalyzer
from src.execution.risk import RiskManager
from src.analytics.metrics import MarketAnalytics

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
    Strategy with Multi-Timeframe (MTF) Trend Filtering.

    When TRENDING regime: Generate BUY signals on uptrend, SELL on downtrend.
    When MEAN_REVERSION: Generate signals opposite to deviation direction.
    
    **NEW:** Only take signals if the 1-Hour trend aligns with entry direction.
    """

    def __init__(self, bus: EventBus, symbol: str, mtf_analyzer: MTFAnalyzer) -> None:
        self.bus = bus
        self.symbol = symbol
        self._last_z_score = 0.0
        self.mtf = mtf_analyzer

        # Listen to regime changes
        self.bus.subscribe(RegimeEvent, self._on_regime_event)

    def _on_regime_event(self, event: RegimeEvent) -> None:
        """
        Generate trading signals based on regime detection + MTF filter.

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

        # ✅ NEW: MTF TREND FILTER
        # Only take the signal if the 1-Hour trend aligns with entry direction
        mtf_aligned = self.mtf.is_mtf_aligned(
            self.symbol,
            entry_timeframe="M5",
            filter_timeframe="H1",
            entry_direction=direction,
        )
        
        if not mtf_aligned:
            logger.info(
                f"{self.symbol}: ✗ Signal BLOCKED by MTF filter. "
                f"{direction} on M5 but H1 trend doesn't support it."
            )
            return  # Don't take the signal

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
    Main async entry point with comprehensive analytics.

    Sets up:
    1. EventBus with uvloop.
    2. MetaTrader 5 data feed for real market prices.
    3. MarketAnalytics for OHLCV, P&L, Sharpe ratio tracking.
    4. Supervisors for regime detection.
    5. RiskManager for position validation.
    6. Strategies for signal generation.
    7. Live metrics reporter (every 30 seconds).
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

    # Initialize market analytics
    session_start = datetime.now()
    analytics = MarketAnalytics(INSTRUMENTS, session_start)
    logger.info("✓ MarketAnalytics initialized")

    # Subscribe analytics to ticks
    def update_analytics(event: TickEvent) -> None:
        analytics.update_tick(
            event.symbol,
            event.timestamp,
            event.bid,
            event.ask,
            event.volume,
        )

    bus.subscribe(TickEvent, update_analytics)

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

    # Initialize Multi-Timeframe analyzer
    mtf_analyzer = MTFAnalyzer(INSTRUMENTS)
    logger.info("✓ MTFAnalyzer initialized (M5 entries filtered by H1 trend)")

    # Subscribe to orders to record trades in analytics
    def record_order(event: OrderRequestEvent) -> None:
        analytics.record_trade(
            symbol=event.symbol,
            direction=event.direction,
            entry_price=event.price,
            quantity=event.quantity,
            risk_amount=event.risk_amount,
            confidence=event.confidence,
            regime=event.regime,
        )

    bus.subscribe(OrderRequestEvent, record_order)

    # Initialize strategies with MTF filtering
    strategies = {}
    for symbol in INSTRUMENTS:
        strategy = SimpleStrategy(bus, symbol, mtf_analyzer)
        strategies[symbol] = strategy
        logger.info(f"✓ Strategy initialized for {symbol} (with MTF filter)")

    logger.info("=" * 70)
    logger.info(f"Starting live market session ({SESSION_DURATION_SECONDS}s)...")
    logger.info("=" * 70)

    # Periodic metrics reporter (every 30 seconds)
    async def report_metrics() -> None:
        while True:
            try:
                await asyncio.sleep(30)

                logger.info("\n" + "=" * 70)
                logger.info("📊 LIVE MARKET METRICS (30s snapshot)")
                logger.info("=" * 70)

                for symbol in INSTRUMENTS:
                    daily = analytics.get_daily_stats(symbol)
                    logger.info(
                        f"\n{symbol}:"
                        f"\n  Open:  {daily.open:.5f}"
                        f"\n  High:  {daily.high:.5f} @ {daily.high_timestamp.strftime('%H:%M:%S')}"
                        f"\n  Low:   {daily.low:.5f} @ {daily.low_timestamp.strftime('%H:%M:%S')}"
                        f"\n  Close: {daily.close:.5f}"
                        f"\n  Range: {daily.range():.5f} ({daily.range_pct():.2f}%)"
                        f"\n  Volume: {daily.volume:.0f}"
                    )

                # Portfolio metrics
                portfolio = analytics.get_portfolio_metrics(ACCOUNT_BALANCE, risk_manager.account_balance)
                logger.info(
                    f"\n💼 PORTFOLIO METRICS:"
                    f"\n  Balance:        ${portfolio.current_balance:,.2f}"
                    f"\n  P&L:            ${portfolio.total_pnl():,.2f} ({portfolio.total_return_pct():.2f}%)"
                    f"\n  Total Trades:   {portfolio.total_trades}"
                    f"\n  Wins:           {portfolio.winning_trades} ({portfolio.win_rate():.1f}%)"
                    f"\n  Losses:         {portfolio.losing_trades}"
                    f"\n  Profit Factor:  {portfolio.profit_factor():.2f}x"
                    f"\n  Avg Win:        ${portfolio.avg_win():,.2f}"
                    f"\n  Avg Loss:       ${portfolio.avg_loss():,.2f}"
                    f"\n  Expectancy:     ${portfolio.expectancy():,.2f}/trade"
                    f"\n  Sharpe Ratio:   {portfolio.sharpe_ratio():.2f}"
                    f"\n  Max Drawdown:   {portfolio.max_drawdown():.2f}%"
                    f"\n  Recovery Factor:{portfolio.recovery_factor():.2f}"
                )

                logger.info("=" * 70 + "\n")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in metrics reporter: {e}")

    # Start metrics reporter and data feed
    metrics_task = asyncio.create_task(report_metrics())
    feed_task = asyncio.create_task(data_feed.start_stream())

    # Run for specified duration
    try:
        await asyncio.sleep(SESSION_DURATION_SECONDS)
    except KeyboardInterrupt:
        logger.info("\n⏸ Session interrupted by user")
    finally:
        # Stop all tasks
        data_feed.stop()
        metrics_task.cancel()

        try:
            await feed_task
        except asyncio.CancelledError:
            pass

        try:
            await metrics_task
        except asyncio.CancelledError:
            pass

    # Final summary
    logger.info("\n" + "=" * 70)
    logger.info("📋 SESSION COMPLETE - FINAL REPORT")
    logger.info("=" * 70)

    for symbol in INSTRUMENTS:
        daily = analytics.get_daily_stats(symbol)
        logger.info(
            f"\n{symbol} DAILY SUMMARY:"
            f"\n  Open:      {daily.open:.5f}"
            f"\n  High:      {daily.high:.5f}"
            f"\n  Low:       {daily.low:.5f}"
            f"\n  Close:     {daily.close:.5f}"
            f"\n  Daily Move:{daily.range_pct():.2f}%"
        )

    portfolio = analytics.get_portfolio_metrics(ACCOUNT_BALANCE, risk_manager.account_balance)
    logger.info(
        f"\n💰 FINAL PORTFOLIO METRICS:"
        f"\n  Starting Balance:    ${ACCOUNT_BALANCE:,.2f}"
        f"\n  Ending Balance:      ${portfolio.current_balance:,.2f}"
        f"\n  Total P&L:           ${portfolio.total_pnl():,.2f}"
        f"\n  Return:              {portfolio.total_return_pct():.2f}%"
        f"\n"
        f"\n  Total Trades:        {portfolio.total_trades}"
        f"\n  Winning Trades:      {portfolio.winning_trades}"
        f"\n  Losing Trades:       {portfolio.losing_trades}"
        f"\n  Win Rate:            {portfolio.win_rate():.1f}%"
        f"\n"
        f"\n  Profit Factor:       {portfolio.profit_factor():.2f}x"
        f"\n  Largest Win:         ${portfolio.largest_win:,.2f}"
        f"\n  Largest Loss:        ${portfolio.largest_loss:,.2f}"
        f"\n  Avg Win:             ${portfolio.avg_win():,.2f}"
        f"\n  Avg Loss:            ${portfolio.avg_loss():,.2f}"
        f"\n  Expectancy:          ${portfolio.expectancy():,.2f}/trade"
        f"\n"
        f"\n  Sharpe Ratio:        {portfolio.sharpe_ratio():.2f} (>1.0 is good)"
        f"\n  Max Drawdown:        {portfolio.max_drawdown():.2f}%"
        f"\n  Recovery Factor:     {portfolio.recovery_factor():.2f}"
    )

    logger.info("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
