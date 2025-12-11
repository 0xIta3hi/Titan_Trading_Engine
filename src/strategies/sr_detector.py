"""
Automated Support & Resistance (S/R) Detection.

Identifies key price levels where price has bounced/rejected in the past.
Uses these levels to filter mean reversion trades.
"""

import logging
from dataclasses import dataclass
from typing import Optional

import numpy as np
from scipy import signal

logger = logging.getLogger(__name__)


@dataclass
class SRLevel:
    """A support/resistance price level."""
    
    price: float
    level_type: str  # "SUPPORT" or "RESISTANCE"
    touches: int  # How many times price bounced at this level
    last_touch: float  # Most recent timestamp of touch
    strength: float  # Strength score (0-1), based on touches and recency


class SRDetector:
    """
    Detects Support and Resistance levels using local extrema.
    
    Algorithm:
    1. Find local maxima (resistance) and minima (support)
    2. Cluster nearby levels (within pip threshold)
    3. Score by number of touches and recency
    4. Return top N levels
    """
    
    def __init__(self, pip_threshold: float = 0.0010):
        """
        Initialize S/R detector.
        
        Args:
            pip_threshold: Minimum distance between distinct levels.
                          Default 0.0010 (10 pips for forex).
        """
        self.pip_threshold = pip_threshold
        self.sr_levels: dict[str, list[SRLevel]] = {}
        
        logger.info(f"SRDetector initialized (pip_threshold={pip_threshold})")
    
    def detect_levels(
        self,
        symbol: str,
        closes: list[float],
        window: int = 10,
        min_strength: float = 0.3,
    ) -> dict[str, list[SRLevel]]:
        """
        Detect S/R levels from close prices.
        
        Args:
            symbol: Trading symbol.
            closes: List of close prices (oldest to newest).
            window: Window for local extrema (number of candles).
            min_strength: Minimum strength score to include level (0-1).
        
        Returns:
            Dict with keys "support" and "resistance", each a list of SRLevel.
        """
        if len(closes) < window * 2:
            logger.warning(f"{symbol}: Not enough data for S/R detection")
            return {"support": [], "resistance": []}
        
        closes_array = np.array(closes, dtype=float)
        
        # Find local maxima (resistance)
        resistance_indices = signal.argrelextrema(closes_array, np.greater, order=window)[0]
        resistance_prices = closes_array[resistance_indices].tolist()
        
        # Find local minima (support)
        support_indices = signal.argrelextrema(closes_array, np.less, order=window)[0]
        support_prices = closes_array[support_indices].tolist()
        
        # Cluster levels that are too close together
        resistance_clustered = self._cluster_levels(resistance_prices)
        support_clustered = self._cluster_levels(support_prices)
        
        # Score levels by strength (touches + recency)
        resistance_levels = self._score_levels(
            symbol, resistance_clustered, "RESISTANCE", closes_array, min_strength
        )
        support_levels = self._score_levels(
            symbol, support_clustered, "SUPPORT", closes_array, min_strength
        )
        
        result = {
            "support": support_levels,
            "resistance": resistance_levels,
        }
        
        self.sr_levels[symbol] = support_levels + resistance_levels
        
        return result
    
    def _cluster_levels(self, prices: list[float]) -> list[float]:
        """
        Cluster nearby prices into single levels.
        
        E.g., if we have [1.1005, 1.1008, 1.1012], and pip_threshold=0.001,
        we cluster first two and keep third separate.
        """
        if not prices:
            return []
        
        prices_sorted = sorted(prices)
        clusters = []
        current_cluster = [prices_sorted[0]]
        
        for price in prices_sorted[1:]:
            if abs(price - current_cluster[-1]) <= self.pip_threshold:
                current_cluster.append(price)
            else:
                # Close current cluster, start new one
                clusters.append(np.mean(current_cluster))
                current_cluster = [price]
        
        clusters.append(np.mean(current_cluster))
        return clusters
    
    def _score_levels(
        self,
        symbol: str,
        prices: list[float],
        level_type: str,
        closes: np.ndarray,
        min_strength: float,
    ) -> list[SRLevel]:
        """
        Score each level by strength.
        
        Strength = (touches / max_possible_touches) * 0.7 + (recency_score) * 0.3
        """
        levels = []
        max_touches = 0
        
        for price in prices:
            # Count touches (how many times price was near this level)
            touches = np.sum(np.abs(closes - price) < self.pip_threshold)
            max_touches = max(max_touches, touches)
        
        if max_touches == 0:
            return []
        
        for price in prices:
            touches = np.sum(np.abs(closes - price) < self.pip_threshold)
            
            # Recency: higher score if level was touched recently
            last_touch_idx = np.where(np.abs(closes - price) < self.pip_threshold)[0]
            if len(last_touch_idx) > 0:
                last_touch = float(last_touch_idx[-1]) / len(closes)
            else:
                last_touch = 0.0
            
            # Combined strength score
            strength = (touches / max_touches) * 0.7 + last_touch * 0.3
            
            if strength >= min_strength:
                level = SRLevel(
                    price=price,
                    level_type=level_type,
                    touches=int(touches),
                    last_touch=last_touch,
                    strength=strength,
                )
                levels.append(level)
        
        # Sort by strength (strongest first)
        levels.sort(key=lambda x: x.strength, reverse=True)
        
        logger.debug(
            f"{symbol}: Detected {len(levels)} {level_type} levels. "
            f"Top 3: {[f'{l.price:.5f}({l.touches}x)' for l in levels[:3]]}"
        )
        
        return levels
    
    def is_near_sr(
        self,
        symbol: str,
        price: float,
        sr_type: str = "SUPPORT",
        distance_pips: float = 0.0015,
    ) -> bool:
        """
        Check if price is near a significant S/R level.
        
        Args:
            symbol: Trading symbol.
            price: Current price.
            sr_type: "SUPPORT" or "RESISTANCE".
            distance_pips: How close to a level to consider "near".
        
        Returns:
            True if price is near a strong level, False otherwise.
        """
        if symbol not in self.sr_levels:
            return False
        
        levels = [l for l in self.sr_levels[symbol] if l.level_type == sr_type]
        
        if not levels:
            return False
        
        # Check if price is within distance_pips of any level
        for level in levels:
            if abs(price - level.price) <= distance_pips:
                logger.info(
                    f"{symbol}: Price {price:.5f} is near {sr_type} "
                    f"@ {level.price:.5f} (strength: {level.strength:.2f})"
                )
                return True
        
        return False
    
    def get_nearest_level(
        self,
        symbol: str,
        price: float,
        sr_type: str = "SUPPORT",
    ) -> Optional[SRLevel]:
        """
        Get the nearest S/R level to current price.
        
        Args:
            symbol: Trading symbol.
            price: Current price.
            sr_type: "SUPPORT" or "RESISTANCE".
        
        Returns:
            Nearest SRLevel, or None if no levels exist.
        """
        if symbol not in self.sr_levels:
            return None
        
        levels = [l for l in self.sr_levels[symbol] if l.level_type == sr_type]
        
        if not levels:
            return None
        
        # Return level closest to price
        nearest = min(levels, key=lambda l: abs(l.price - price))
        return nearest
