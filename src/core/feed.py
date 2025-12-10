"""
Real-time market data feed from MetaTrader 5.

Provides live price streaming to the trading engine with minimal latency.
Polls MT5 at high frequency and publishes TickEvents to the EventBus.
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, List

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
        except Exception:
            pass
    
