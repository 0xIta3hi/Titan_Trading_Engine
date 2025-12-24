#!/usr/bin/env python3
"""
Test script for MT5 DataFeed integration.

Tests:
1. MT5 connection and initialization
2. Real data feed from MT5 terminal
3. Mock fallback mode
4. Event publishing and subscription
5. High-frequency tick streaming

Usage:
    python test_mt5_integration.py [--mock]
    
Options:
    --mock          Force mock data feed mode (for testing without MT5)
    --duration 30   Run for specified seconds (default: 30)
"""

import asyncio
import sys
import logging
from datetime import datetime
from typing import Optional

from src.core.engine import EventBus, setup_event_loop
from src.core.events import TickEvent
from src.core.feed import create_data_feed, DataFeed, MockDataFeed

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# Test configuration
INSTRUMENTS = ["EURUSD", "USDJPY", "XAUUSD"]
TEST_DURATION = 30  # seconds


class DataFeedTester:
    """Test harness for DataFeed verification."""

    def __init__(self, bus: EventBus, feed_type: str = "auto"):
        """
        Initialize tester.
        
        Args:
            bus: EventBus instance
            feed_type: "auto", "mt5", or "mock"
        """
        self.bus = bus
        self.feed_type = feed_type
        self.tick_counts = {s: 0 for s in INSTRUMENTS}
        self.last_prices = {s: None for s in INSTRUMENTS}
        self.min_prices = {s: float('inf') for s in INSTRUMENTS}
        self.max_prices = {s: float('-inf') for s in INSTRUMENTS}
        self.start_time: Optional[datetime] = None

    async def run_test(self, duration: int = 30) -> None:
        """
        Run the DataFeed integration test.
        
        Args:
            duration: Test duration in seconds
        """
        logger.info("=" * 70)
        logger.info("🧪 MT5 DataFeed Integration Test")
        logger.info("=" * 70)

        # Create appropriate feed
        logger.info(f"\nInitializing {self.feed_type} data feed...")
        try:
            if self.feed_type == "mt5":
                from src.core.feed import DataFeed
                data_feed = DataFeed(self.bus, INSTRUMENTS)
            elif self.feed_type == "mock":
                from src.core.feed import MockDataFeed
                data_feed = MockDataFeed(self.bus, INSTRUMENTS)
            else:  # auto
                data_feed = create_data_feed(self.bus, INSTRUMENTS, use_mock=False)
            
            logger.info(f"✓ Feed initialized (type: {type(data_feed).__name__})")
        except ConnectionError as e:
            logger.error(f"❌ Failed to initialize feed: {e}")
            return

        # Subscribe to ticks
        self.bus.subscribe(TickEvent, self._on_tick)
        logger.info("✓ Tick handler subscribed")

        # Start data feed
        logger.info(f"\nStreaming for {duration} seconds...\n")
        self.start_time = datetime.now()
        
        feed_task = asyncio.create_task(data_feed.start_stream())
        
        try:
            await asyncio.sleep(duration)
        except KeyboardInterrupt:
            logger.info("\n⏸ Test interrupted by user")
        finally:
            data_feed.stop()
            try:
                await asyncio.wait_for(feed_task, timeout=2.0)
            except asyncio.TimeoutError:
                feed_task.cancel()
                try:
                    await feed_task
                except asyncio.CancelledError:
                    pass

        # Print results
        self._print_results(duration)

    def _on_tick(self, event: TickEvent) -> None:
        """Handle tick event."""
        self.tick_counts[event.symbol] += 1
        mid_price = event.mid_price
        
        self.last_prices[event.symbol] = mid_price
        self.min_prices[event.symbol] = min(self.min_prices[event.symbol], mid_price)
        self.max_prices[event.symbol] = max(self.max_prices[event.symbol], mid_price)
        
        # Log every 50th tick for each symbol
        if self.tick_counts[event.symbol] % 50 == 0:
            logger.info(
                f"✓ {event.symbol}: {mid_price:.5f} "
                f"[{self.min_prices[event.symbol]:.5f} - {self.max_prices[event.symbol]:.5f}] "
                f"(tick #{self.tick_counts[event.symbol]})"
            )

    def _print_results(self, duration: int) -> None:
        """Print test results."""
        logger.info("\n" + "=" * 70)
        logger.info("📊 TEST RESULTS")
        logger.info("=" * 70)

        total_ticks = sum(self.tick_counts.values())
        
        logger.info(f"\n⏱️  Duration: {duration} seconds")
        logger.info(f"📈 Total Ticks Received: {total_ticks}")
        logger.info(f"📊 Average Frequency: {total_ticks / duration:.1f} ticks/sec")

        logger.info(f"\n{'-' * 70}")
        logger.info(f"{'Symbol':<12} {'Ticks':<10} {'Freq':<10} {'Last':<12} {'Range':<18}")
        logger.info(f"{'-' * 70}")

        for symbol in INSTRUMENTS:
            count = self.tick_counts[symbol]
            freq = count / duration if duration > 0 else 0
            last = self.last_prices[symbol]
            min_p = self.min_prices[symbol]
            max_p = self.max_prices[symbol]
            
            if last is not None:
                range_str = f"{min_p:.5f} - {max_p:.5f}"
            else:
                range_str = "N/A"
            
            logger.info(
                f"{symbol:<12} {count:<10} {freq:>6.1f} Hz  "
                f"{(last or 0):<12.5f} {range_str:<18}"
            )

        logger.info(f"{'-' * 70}")

        # Validation
        logger.info(f"\n✅ VALIDATION CHECKS:")
        
        all_pass = True
        
        # Check: All symbols received ticks
        all_symbols_ok = all(count > 0 for count in self.tick_counts.values())
        status = "✓ PASS" if all_symbols_ok else "✗ FAIL"
        logger.info(f"  {status}: All symbols received ticks")
        all_pass &= all_symbols_ok
        
        # Check: Frequency is reasonable (at least 50 Hz minimum)
        min_freq = min(
            (self.tick_counts[s] / duration for s in INSTRUMENTS),
            default=0
        )
        freq_ok = min_freq >= 50
        status = "✓ PASS" if freq_ok else "✗ FAIL"
        logger.info(f"  {status}: Minimum frequency {min_freq:.1f} Hz (target: 50+ Hz)")
        all_pass &= freq_ok
        
        # Check: Prices are reasonable
        prices_ok = all(
            self.last_prices[s] is not None and
            self.min_prices[s] > 0 and
            self.max_prices[s] > self.min_prices[s]
            for s in INSTRUMENTS
        )
        status = "✓ PASS" if prices_ok else "✗ FAIL"
        logger.info(f"  {status}: Price ranges are valid")
        all_pass &= prices_ok

        logger.info(f"\n{'=' * 70}")
        if all_pass:
            logger.info("🎉 ALL TESTS PASSED")
        else:
            logger.info("⚠️  SOME TESTS FAILED")
        logger.info("=" * 70)


async def main() -> None:
    """Main entry point."""
    # Parse command line args
    use_mock = "--mock" in sys.argv
    
    duration = TEST_DURATION
    if "--duration" in sys.argv:
        try:
            idx = sys.argv.index("--duration")
            duration = int(sys.argv[idx + 1])
        except (ValueError, IndexError):
            duration = TEST_DURATION

    # Setup
    setup_event_loop()
    bus = EventBus()

    # Determine feed type
    feed_type = "mock" if use_mock else "auto"

    # Run test
    tester = DataFeedTester(bus, feed_type=feed_type)
    await tester.run_test(duration=duration)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\n⏸ Test aborted by user")
    except Exception as e:
        logger.exception(f"❌ Test failed: {e}")
        sys.exit(1)
