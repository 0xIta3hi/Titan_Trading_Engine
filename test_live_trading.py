#!/usr/bin/env python3
"""
Live trading simulator - Tests order execution and P&L tracking.

Simulates realistic trading scenarios to verify:
1. Order execution on signals
2. P&L calculation
3. Position tracking
4. Risk management
5. Performance reporting

Run: python test_live_trading.py --duration 10
"""

import asyncio
import sys
import logging
from datetime import datetime
from typing import Optional

from src.core.engine import EventBus, setup_event_loop
from src.core.events import TickEvent, SignalEvent
from src.execution.risk import RiskManager
from src.execution.executor import OrderExecutor

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# Configuration
INSTRUMENTS = ["EURUSD", "USDJPY", "XAUUSD"]
ACCOUNT_BALANCE = 1_000_000.0
MAX_RISK_PER_TRADE = 10_000.0
MAX_DAILY_RISK = 50_000.0
TEST_DURATION = 30  # seconds


class LiveTradingSimulator:
    """Simulates live trading with realistic signals and market data."""
    
    def __init__(self, duration: int = 30):
        """Initialize simulator."""
        self.duration = duration
        self.setup_event_loop()
        self.bus = EventBus()
        
        # Initialize components
        self.risk_manager = RiskManager(
            self.bus,
            account_balance=ACCOUNT_BALANCE,
            max_risk_per_trade=MAX_RISK_PER_TRADE,
            max_daily_risk=MAX_DAILY_RISK,
        )
        
        self.executor = OrderExecutor(
            self.bus,
            account_balance=ACCOUNT_BALANCE,
        )
        
        # Prices for market data
        self.prices = {
            "EURUSD": 1.0850,
            "USDJPY": 149.50,
            "XAUUSD": 2650.00,
        }
        
        self.signal_count = 0
    
    @staticmethod
    def setup_event_loop() -> None:
        """Configure asyncio event loop."""
        setup_event_loop()
    
    async def run_simulation(self) -> None:
        """Run the trading simulation."""
        logger.info("=" * 70)
        logger.info("🧪 LIVE TRADING SIMULATION")
        logger.info("=" * 70)
        logger.info(f"\nAccount Balance: ${ACCOUNT_BALANCE:,.2f}")
        logger.info(f"Max Risk/Trade: ${MAX_RISK_PER_TRADE:,.2f}")
        logger.info(f"Max Daily Risk: ${MAX_DAILY_RISK:,.2f}")
        logger.info(f"Duration: {self.duration} seconds\n")
        
        # Generate market data and signals
        start_time = datetime.utcnow()
        tick_count = 0
        
        while (datetime.utcnow() - start_time).total_seconds() < self.duration:
            # Generate ticks for each symbol
            for symbol in INSTRUMENTS:
                # Simulate price movement (random walk)
                import random
                self.prices[symbol] *= (1 + random.gauss(0, 0.0005))
                
                # Publish tick
                tick = TickEvent(
                    symbol=symbol,
                    timestamp=datetime.utcnow(),
                    bid=self.prices[symbol] * 0.99998,
                    ask=self.prices[symbol] * 1.00002,
                    volume=random.uniform(1000, 5000),
                )
                await self.bus.publish(tick)
                tick_count += 1
                
                # Generate signal every 20 ticks (20% of ticks become signals)
                if random.random() < 0.05:
                    self._generate_signal(symbol)
            
            await asyncio.sleep(0.1)  # 100ms between tick batches
        
        # Print results
        logger.info(f"\n{'=' * 70}")
        logger.info("📊 SIMULATION RESULTS")
        logger.info(f"{'=' * 70}")
        
        logger.info(f"\nMarket Data:")
        logger.info(f"  Total Ticks: {tick_count}")
        logger.info(f"  Symbols: {', '.join(INSTRUMENTS)}")
        logger.info(f"  Final Prices:")
        for symbol in INSTRUMENTS:
            logger.info(f"    {symbol}: {self.prices[symbol]:.5f}")
        
        # Executor performance
        perf = self.executor.get_performance_report()
        logger.info(f"\n💰 LIVE TRADING RESULTS:")
        logger.info(f"  Trading Signals: {self.signal_count}")
        logger.info(f"  Executed Trades: {perf['trades']['total_trades']}")
        logger.info(f"  Starting Balance: ${perf['account']['starting_balance']:,.2f}")
        logger.info(f"  Current Balance: ${perf['account']['current_balance']:,.2f}")
        logger.info(f"  Total P&L: ${perf['account']['total_pnl']:,.2f}")
        logger.info(f"  Return: {perf['account']['return_pct']:.2f}%")
        
        logger.info(f"\n📈 TRADE STATISTICS:")
        logger.info(f"  Total Trades: {perf['trades']['total_trades']}")
        logger.info(f"  Wins: {perf['trades']['winning_trades']}")
        logger.info(f"  Losses: {perf['trades']['losing_trades']}")
        logger.info(f"  Win Rate: {perf['trades']['win_rate_pct']:.1f}%")
        logger.info(f"  Open Positions: {perf['trades']['open_positions']}")
        
        logger.info(f"\n💵 P&L BREAKDOWN:")
        logger.info(f"  Realized P&L: ${perf['pnl']['realized']:,.2f}")
        logger.info(f"  Unrealized P&L: ${perf['pnl']['unrealized']:,.2f}")
        logger.info(f"  Total P&L: ${perf['pnl']['total']:,.2f}")
        
        logger.info(f"\n{'=' * 70}")
        if perf['trades']['total_trades'] > 0:
            logger.info("✅ SIMULATION SUCCESSFUL - Trades Executed")
        else:
            logger.info("⚠️  NO TRADES EXECUTED - Check signal generation")
        logger.info(f"{'=' * 70}\n")
    
    def _generate_signal(self, symbol: str) -> None:
        """Generate a test signal."""
        import random
        
        self.signal_count += 1
        direction = random.choice(["BUY", "SELL"])
        confidence = random.uniform(0.5, 0.95)
        
        signal = SignalEvent(
            symbol=symbol,
            timestamp=datetime.utcnow(),
            direction=direction,
            confidence=confidence,
            regime=random.choice(["TRENDING", "MEAN_REVERSION"]),
            price=self.prices[symbol],
        )
        
        logger.debug(
            f"📊 Signal: {symbol} {direction} "
            f"(confidence: {confidence:.0%}, regime: {signal.regime})"
        )
        
        # Publish signal (triggers risk manager and executor)
        try:
            loop = asyncio.get_running_loop()
            asyncio.create_task(self.bus.publish(signal))
        except RuntimeError:
            pass


async def main() -> None:
    """Main entry point."""
    # Parse args
    duration = TEST_DURATION
    if "--duration" in sys.argv:
        try:
            idx = sys.argv.index("--duration")
            duration = int(sys.argv[idx + 1])
        except (ValueError, IndexError):
            pass
    
    # Run simulation
    simulator = LiveTradingSimulator(duration=duration)
    await simulator.run_simulation()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\n⏸ Simulation aborted by user")
    except Exception as e:
        logger.exception(f"❌ Simulation failed: {e}")
        sys.exit(1)
