"""
Real-time market data feed from MetaTrader 5.

Provides live price streaming to the trading engine with minimal latency.
Polls MT5 at high frequency and publishes TickEvents to the EventBus.

Features:
- High-frequency polling (100 Hz) from MT5 terminal
- Automatic deduplication of identical prices
- Fallback mock mode for testing without MT5 terminal
- Exception isolation and error recovery
"""

import asyncio
import logging
import random
from datetime import datetime
from typing import Dict, List, Optional, Union

import MetaTrader5 as mt5

from .engine import EventBus
from .events import TickEvent

logger = logging.getLogger(__name__)


class DataFeed:
    """
    Real-time market data feed from MetaTrader 5.
    
    Polls MT5 for price updates and publishes them as TickEvents to the EventBus.
    This is the "heartbeat" of Titan - high-frequency polling from MT5 RAM
    replaces WebSockets (which MT5 doesn't natively support).
    
    Attributes:
        bus: EventBus instance for event publishing.
        symbols: List of symbols to stream (e.g., ['EURUSD', 'USDJPY']).
    """

    def __init__(self, bus: EventBus, symbols: List[str]):
        """
        Initialize the data feed.
        
        Args:
            bus: EventBus instance for publishing TickEvents.
            symbols: List of currency pairs/instruments to stream.
            
        Raises:
            ConnectionError: If MT5 terminal is not running.
        """
        self.bus = bus
        self.symbols = symbols
        self.running = False
        
        # Keep track of last known tick timestamp to avoid duplicate events
        self._last_tick_time: Dict[str, int] = {s: 0 for s in symbols}
        
        # Verify MT5 is connected
        if not mt5.initialize():
            raise ConnectionError(
                "MetaTrader 5 terminal is not running. "
                "Please start MT5 and ensure you are logged in."
            )
        
        logger.info(f"MT5 initialized. Account: {mt5.account_info().login}")
        
        # Enable all symbols for tick data subscription
        for symbol in symbols:
            if not mt5.symbol_select(symbol, True):
                logger.warning(f"Could not select symbol: {symbol}")
            else:
                logger.info(f"Subscribed to {symbol}")

    async def start_stream(self) -> None:
        """
        Start streaming market data from MT5.
        
        Continuously polls MT5 at 10ms intervals (100 ticks/second) and
        publishes TickEvents for price changes. This frequency is sufficient
        for swing trading and regime detection.
        
        MT5 doesn't support async WebSockets natively, so we poll the terminal's
        RAM at high frequency instead. This is still microseconds-fast per poll.
        
        Can be stopped with stop() method.
        """
        self.running = True
        logger.info(f"Starting Data Feed for: {self.symbols}")
        
        while self.running:
            try:
                # Poll all symbols for latest ticks
                for symbol in self.symbols:
                    tick_data = mt5.symbol_info_tick(symbol)
                    
                    # Skip if no data available for this symbol
                    if tick_data is None:
                        logger.warning(f"No tick data available for {symbol}")
                        continue
                    
                    # Skip if price hasn't changed (avoid duplicate events)
                    # time_msc is milliseconds since epoch
                    if tick_data.time_msc == self._last_tick_time[symbol]:
                        continue
                    
                    # Update last seen timestamp
                    self._last_tick_time[symbol] = tick_data.time_msc
                    
                    # Create TickEvent from MT5 data
                    tick_event = TickEvent(
                        symbol=symbol,
                        timestamp=datetime.fromtimestamp(tick_data.time),
                        bid=tick_data.bid,
                        ask=tick_data.ask,
                        volume=tick_data.volume_real,
                    )
                    
                    # Publish to event bus (non-blocking async)
                    await self.bus.publish(tick_event)

            except Exception as e:
                logger.error(f"Feed Error: {e}")
                # Backoff on error to avoid rapid retries
                await asyncio.sleep(1.0)
            
            # Polling frequency: 10ms = 100 Hz
            # Fast enough for real-time regime detection, slow enough to not waste CPU
            await asyncio.sleep(0.01)

    def stop(self) -> None:
        """Stop the data feed stream."""
        self.running = False
        logger.info("Data Feed Stopped.")

    def __del__(self) -> None:
        """Cleanup: shutdown MT5 connection."""
        try:
            mt5.shutdown()
            logger.debug("MT5 connection closed.")
        except Exception:
            pass


class MockDataFeed:
    """
    Mock market data feed for testing without MT5 terminal.
    
    Generates synthetic price data with realistic market behavior:
    - Random walk with drift (trends)
    - Mean reversion (overbought/oversold)
    - Volatility clustering
    
    Useful for:
    - Development and testing
    - Backtesting strategies
    - Demo presentations
    
    Attributes:
        bus: EventBus instance for event publishing.
        symbols: List of symbols to generate data for.
        base_prices: Initial prices for each symbol.
    """

    def __init__(
        self,
        bus: EventBus,
        symbols: List[str],
        base_prices: Optional[Dict[str, float]] = None,
    ):
        """
        Initialize the mock data feed.
        
        Args:
            bus: EventBus instance for publishing TickEvents.
            symbols: List of symbols to generate data for.
            base_prices: Starting prices for each symbol.
                        Defaults to realistic Forex prices.
        """
        self.bus = bus
        self.symbols = symbols
        self.running = False
        
        # Default prices for common Forex pairs
        self.prices = base_prices or {
            "EURUSD": 1.0850,
            "USDJPY": 149.50,
            "XAUUSD": 2650.00,
        }
        
        # Volatility per symbol (as percentage for consistent behavior)
        self.volatilities = {
            "EURUSD": 0.0015,  # ~15 pips daily
            "USDJPY": 0.0200,  # ~200 pips daily
            "XAUUSD": 0.01,    # ~1% daily
        }
        
        # Trend state per symbol (for synthetic trending regime)
        self.trends = {s: random.choice([-1, 0, 1]) for s in symbols}
        
        logger.info(f"MockDataFeed initialized for: {symbols}")
        logger.warning("⚠️  Using MOCK market data (MT5 terminal not connected)")

    async def start_stream(self) -> None:
        """
        Generate synthetic market data and publish TickEvents.
        
        Simulates realistic price movements including trends, reversions,
        and volatility. Runs at 10ms intervals (100 Hz).
        """
        self.running = True
        logger.info(f"Starting Mock Data Feed for: {self.symbols}")
        
        while self.running:
            try:
                for symbol in self.symbols:
                    # Generate synthetic price with trend + noise
                    current_price = self.prices[symbol]
                    volatility = self.volatilities.get(symbol, 0.01)
                    
                    # Random walk with drift (trend)
                    drift = self.trends[symbol] * volatility * 0.5
                    noise = random.gauss(0, volatility)
                    
                    # Change trend occasionally (regime switching)
                    if random.random() < 0.02:  # 2% chance per tick
                        self.trends[symbol] = random.choice([-1, 0, 1])
                    
                    # Update price
                    new_price = current_price * (1 + drift + noise)
                    self.prices[symbol] = new_price
                    
                    # Create TickEvent with realistic bid/ask spread
                    spread = volatility * 0.05  # 5% of volatility
                    bid = new_price - spread / 2
                    ask = new_price + spread / 2
                    
                    tick_event = TickEvent(
                        symbol=symbol,
                        timestamp=datetime.utcnow(),
                        bid=bid,
                        ask=ask,
                        volume=random.uniform(1000, 5000),
                    )
                    
                    # Publish to event bus
                    await self.bus.publish(tick_event)

            except Exception as e:
                logger.error(f"Mock Feed Error: {e}")
                await asyncio.sleep(1.0)
            
            # Polling frequency: 10ms = 100 Hz
            await asyncio.sleep(0.01)

    def stop(self) -> None:
        """Stop the mock data feed stream."""
        self.running = False
        logger.info("Mock Data Feed Stopped.")


def create_data_feed(
    bus: EventBus,
    symbols: List[str],
    use_mock: bool = False,
) -> Union[DataFeed, MockDataFeed]:
    """
    Factory function to create appropriate data feed.
    
    Automatically selects MT5 or mock feed. If use_mock=False,
    attempts real MT5 connection and falls back to mock on failure.
    
    Args:
        bus: EventBus for event publishing.
        symbols: List of symbols to stream.
        use_mock: If True, force mock mode. If False, try MT5 first.
        
    Returns:
        DataFeed (real MT5) or MockDataFeed (synthetic data).
    """
    if use_mock:
        logger.info("Forcing mock data feed mode")
        return MockDataFeed(bus, symbols)
    
    try:
        logger.info("Attempting to connect to MetaTrader 5...")
        feed = DataFeed(bus, symbols)
        logger.info("✓ Connected to real MT5 terminal")
        return feed
    except ConnectionError as e:
        logger.warning(f"MT5 connection failed: {e}")
        logger.warning("Falling back to mock data feed for testing...")
        return MockDataFeed(bus, symbols)
