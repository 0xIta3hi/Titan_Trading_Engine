"""
Multi-Timeframe (MTF) Trend Analysis.

Compares trends across multiple timeframes to filter out bad entry signals.
E.g., only take 5-min Buy signals if 1-Hour trend is up.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

import MetaTrader5 as mt5
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class TimeframeData:
    """OHLCV data for a specific timeframe."""
    
    symbol: str
    timeframe: str  # "M5", "H1", "D1"
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    slope: float = 0.0  # Linear regression slope


class MTFAnalyzer:
    """
    Multi-Timeframe analyzer.
    
    Fetches OHLCV bars from MT5 for multiple timeframes (M5, H1, D1)
    and calculates trend slopes using linear regression.
    """
    
    # MT5 timeframe constants
    TIMEFRAME_MAP = {
        "M5": mt5.TIMEFRAME_M5,
        "M15": mt5.TIMEFRAME_M15,
        "M30": mt5.TIMEFRAME_M30,
        "H1": mt5.TIMEFRAME_H1,
        "H4": mt5.TIMEFRAME_H4,
        "D1": mt5.TIMEFRAME_D1,
    }
    
    def __init__(self, symbols: list[str]):
        """
        Initialize MTF analyzer.
        
        Args:
            symbols: List of trading symbols.
        """
        self.symbols = symbols
        self._last_bars: dict[str, dict[str, TimeframeData]] = {
            s: {} for s in symbols
        }
        
        logger.info(f"MTFAnalyzer initialized for {symbols}")
    
    def get_bars(
        self,
        symbol: str,
        timeframe: str,
        count: int = 100,
    ) -> Optional[list[TimeframeData]]:
        """
        Fetch OHLCV bars from MT5.
        
        Args:
            symbol: Trading symbol (e.g., "EURUSD").
            timeframe: "M5", "H1", "D1", etc.
            count: Number of bars to fetch.
        
        Returns:
            List of TimeframeData objects, or None if error.
        """
        try:
            mt5_timeframe = self.TIMEFRAME_MAP.get(timeframe)
            if not mt5_timeframe:
                logger.error(f"Unknown timeframe: {timeframe}")
                return None
            
            # Fetch bars from MT5
            rates = mt5.copy_rates_from_pos(symbol, mt5_timeframe, 0, count)
            
            if rates is None or len(rates) == 0:
                logger.warning(f"No bars available for {symbol} {timeframe}")
                return None
            
            bars = []
            for rate in rates:
                bar = TimeframeData(
                    symbol=symbol,
                    timeframe=timeframe,
                    timestamp=datetime.fromtimestamp(rate['time']),
                    open=float(rate['open']),
                    high=float(rate['high']),
                    low=float(rate['low']),
                    close=float(rate['close']),
                    volume=int(rate['tick_volume']),
                )
                bars.append(bar)
            
            return bars
        
        except Exception as e:
            logger.error(f"Error fetching {symbol} {timeframe}: {e}")
            return None
    
    def calculate_slope(self, bars: list[TimeframeData]) -> float:
        """
        Calculate linear regression slope of close prices.
        
        Positive slope = uptrend, Negative slope = downtrend.
        
        Args:
            bars: List of TimeframeData.
        
        Returns:
            Slope value (can be positive or negative).
        """
        if len(bars) < 2:
            return 0.0
        
        closes = np.array([bar.close for bar in bars])
        x = np.arange(len(closes))
        
        # Linear regression: close = slope * x + intercept
        coefficients = np.polyfit(x, closes, 1)
        slope = float(coefficients[0])
        
        return slope
    
    def get_trend(self, symbol: str, timeframe: str, count: int = 100) -> dict:
        """
        Get trend analysis for a symbol/timeframe.
        
        Args:
            symbol: Trading symbol.
            timeframe: "M5", "H1", etc.
            count: Number of bars for analysis.
        
        Returns:
            Dict with keys:
                - 'slope': Linear regression slope
                - 'direction': "UP", "DOWN", or "FLAT"
                - 'bars': List of TimeframeData
                - 'close': Latest close price
        """
        bars = self.get_bars(symbol, timeframe, count)
        
        if not bars:
            return {
                'slope': 0.0,
                'direction': 'UNKNOWN',
                'bars': [],
                'close': 0.0,
            }
        
        slope = self.calculate_slope(bars)
        
        # Classify direction
        if slope > 0.00001:  # Small positive threshold to avoid noise
            direction = "UP"
        elif slope < -0.00001:
            direction = "DOWN"
        else:
            direction = "FLAT"
        
        return {
            'slope': slope,
            'direction': direction,
            'bars': bars,
            'close': bars[-1].close,
            'timestamp': bars[-1].timestamp,
        }
    
    def is_mtf_aligned(
        self,
        symbol: str,
        entry_timeframe: str = "M5",
        filter_timeframe: str = "H1",
        entry_direction: str = "BUY",
    ) -> bool:
        """
        Check if entry timeframe is aligned with filter timeframe.
        
        E.g., only take M5 Buy if H1 is also up.
        
        Args:
            symbol: Trading symbol.
            entry_timeframe: Timeframe for entry signal (default "M5").
            filter_timeframe: Timeframe for trend filter (default "H1").
            entry_direction: "BUY" or "SELL".
        
        Returns:
            True if aligned, False otherwise.
        """
        filter_trend = self.get_trend(symbol, filter_timeframe, count=100)
        
        if filter_trend['direction'] == 'UNKNOWN':
            logger.warning(f"{symbol}: Cannot determine {filter_timeframe} trend")
            return False
        
        if entry_direction == "BUY":
            # Only buy if higher timeframe is UP
            aligned = filter_trend['direction'] == "UP"
        else:  # SELL
            # Only sell if higher timeframe is DOWN
            aligned = filter_trend['direction'] == "DOWN"
        
        logger.info(
            f"{symbol}: MTF Check - {entry_timeframe} {entry_direction} "
            f"vs {filter_timeframe} {filter_trend['direction']}: "
            f"{'✓ ALIGNED' if aligned else '✗ BLOCKED'}"
        )
        
        return aligned
