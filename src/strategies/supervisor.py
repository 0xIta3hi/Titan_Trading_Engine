"""
Market regime detection supervisor for Titan trading engine.

Monitors price action and emits regime signals based on statistical measures:
- TRENDING: Strong linear trend (R² > 0.7).
- MEAN_REVERSION: Extreme price deviations (|Z-score| > 2.0).
- RANGING: No clear trend or reversion (0.2 < R² < 0.7).

Maintains a rolling price buffer and delegates calculations to math_utils.
"""

import logging
from datetime import datetime
from collections import deque
from typing import Deque, Optional

import numpy as np

from src.core.engine import EventBus
from src.core.events import TickEvent, RegimeEvent
from src.strategies.math_utils import (
    calculate_slope_and_r_squared,
    calculate_z_score,
)

__all__ = ["Supervisor"]

logger = logging.getLogger(__name__)


class Supervisor:
    """
    Real-time regime detector for currency pairs or commodities.

    Maintains a sliding window of prices and emits regime events based on:
    1. R² > 0.7: Strong trend detected.
    2. |Z-score| > 2.0: Mean reversion opportunity.
    3. 0.2 ≤ R² ≤ 0.7: Ranging market (indecisive).

    Attributes:
        symbol: Currency pair or instrument (e.g., 'EURUSD').
        buffer_size: Number of bars to maintain for regime detection.
        r2_trend_threshold: R² threshold for trend regime (default 0.7).
        r2_ranging_floor: R² floor below which regime is indecisive (default 0.2).
        z_score_threshold: Z-score magnitude for mean reversion (default 2.0).
    """

    def __init__(
        self,
        bus: EventBus,
        symbol: str,
        buffer_size: int = 50,
        r2_trend_threshold: float = 0.7,
        r2_ranging_floor: float = 0.2,
        z_score_threshold: float = 2.0,
    ) -> None:
        """
        Initialize the regime supervisor.

        Args:
            bus: EventBus instance for publishing regime events.
            symbol: Currency pair or instrument code.
            buffer_size: Rolling window size (default 50 bars).
            r2_trend_threshold: R² threshold to classify as trending (default 0.7).
            r2_ranging_floor: R² floor for ranging market (default 0.2).
            z_score_threshold: |Z-score| for mean reversion signal (default 2.0).
        """
        self.bus = bus
        self.symbol = symbol
        self.buffer_size = buffer_size
        self.r2_trend_threshold = r2_trend_threshold
        self.r2_ranging_floor = r2_ranging_floor
        self.z_score_threshold = z_score_threshold

        # Price buffer: deque for O(1) append and maxlen auto-discard
        self._price_buffer: Deque[float] = deque(maxlen=buffer_size)

        # State tracking
        self._current_regime: Optional[str] = None
        self._last_r2: float = 0.0
        self._last_z_score: float = 0.0
        self._tick_count: int = 0

        # Subscribe to tick events
        self.bus.subscribe(TickEvent, self._on_tick)

    def _on_tick(self, event: TickEvent) -> None:
        """
        Handle incoming tick events and update regime detection.

        Args:
            event: TickEvent containing market data.
        """
        # Only process ticks for our symbol
        if event.symbol != self.symbol:
            return

        # Add mid-price to buffer
        self._price_buffer.append(event.mid_price)
        self._tick_count += 1

        # Need at least 3 prices to run analysis
        if len(self._price_buffer) < 3:
            logger.debug(f"{self.symbol}: Buffering prices ({len(self._price_buffer)}/3)")
            return

        # Calculate regime metrics
        self._analyze_regime(event.timestamp)

    def _analyze_regime(self, timestamp: datetime) -> None:
        """
        Analyze current price buffer and detect regime changes.

        Emits RegimeEvent if regime classification changes or threshold conditions met.

        Args:
            timestamp: Event timestamp for logging.
        """
        prices = np.array(list(self._price_buffer), dtype=np.float64)

        # Calculate trend strength
        slope, r2 = calculate_slope_and_r_squared(prices)

        # Calculate mean reversion signal
        z_score = calculate_z_score(prices, window=min(20, len(prices) - 1))

        self._last_r2 = r2
        self._last_z_score = z_score

        # Determine regime classification
        new_regime = self._classify_regime(r2, z_score, slope)

        # Emit event if regime changed
        if new_regime != self._current_regime:
            logger.info(
                f"{self.symbol}: Regime change → {new_regime} "
                f"(R²={r2:.3f}, Z={z_score:.2f}, slope={slope:.6f})"
            )
            self._current_regime = new_regime

            # Publish regime event to bus
            regime_event = RegimeEvent(
                timestamp=timestamp,
                symbol=self.symbol,
                regime_type=new_regime,  # type: ignore
                r_squared=r2,
                z_score=z_score,
            )

            # Non-blocking publish; let subscribers handle
            import asyncio

            try:
                loop = asyncio.get_running_loop()
                asyncio.create_task(self.bus.publish(regime_event))
            except RuntimeError:
                # No running loop; schedule for later
                logger.debug(f"No event loop for immediate publish; buffering {new_regime}")

    def _classify_regime(self, r2: float, z_score: float, slope: float) -> str:
        """
        Classify market regime based on statistical metrics.

        Logic:
        1. If R² > threshold and slope significant → TRENDING.
        2. If |Z-score| > threshold → MEAN_REVERSION.
        3. Otherwise → RANGING.

        Args:
            r2: Coefficient of determination [0, 1].
            z_score: Z-score of current price vs mean.
            slope: Slope of linear fit.

        Returns:
            Regime type as string: "TRENDING", "MEAN_REVERSION", or "RANGING".
        """
        # Trending regime: strong linear trend
        if r2 > self.r2_trend_threshold and abs(slope) > 1e-6:
            return "TRENDING"

        # Mean reversion regime: extreme deviation
        if abs(z_score) > self.z_score_threshold:
            return "MEAN_REVERSION"

        # Ranging regime: weak trend and moderate deviation
        return "RANGING"

    @property
    def current_regime(self) -> Optional[str]:
        """Get the currently detected regime."""
        return self._current_regime

    @property
    def price_buffer_size(self) -> int:
        """Get the current size of the price buffer."""
        return len(self._price_buffer)

    @property
    def metrics(self) -> dict:
        """
        Get current regime metrics for monitoring/debugging.

        Returns:
            Dictionary with keys: 'regime', 'r_squared', 'z_score', 'tick_count'.
        """
        return {
            "regime": self._current_regime,
            "r_squared": self._last_r2,
            "z_score": self._last_z_score,
            "tick_count": self._tick_count,
            "buffer_size": len(self._price_buffer),
        }
