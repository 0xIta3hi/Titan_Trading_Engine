"""
Mathematical utilities for quantitative analysis in Titan trading engine.

Implements statistical measures using numpy for high-performance vector operations:
- Trend Detection: Slope and R² calculation via OLS regression.
- Mean Reversion: Z-score for identifying extreme deviations.
- Position Sizing: Inverse volatility (ATR-based) Kelly-adjacent sizing.

All functions are vectorized with numpy for speed. No pandas in the hot loop.
"""

import numpy as np
from typing import Tuple

__all__ = [
    "calculate_slope_and_r_squared",
    "calculate_z_score",
    "calculate_position_size",
]


def calculate_slope_and_r_squared(prices: np.ndarray) -> Tuple[float, float]:
    """
    Calculate linear trend slope and R² goodness-of-fit for a price series.

    Uses Ordinary Least Squares (OLS) regression:
        prices[i] ≈ α + β * i + ε

    where:
    - β (slope): Trend direction and magnitude.
    - R²: Coefficient of determination [0, 1], indicating trend strength.

    Args:
        prices: 1D numpy array of prices (e.g., closing prices).

    Returns:
        (slope, r_squared): Tuple of slope (float) and R² (float).

    Raises:
        ValueError: If prices array has < 2 elements.

    Example:
        >>> prices = np.array([100, 101, 102, 103, 104])
        >>> slope, r2 = calculate_slope_and_r_squared(prices)
        >>> print(f"Slope: {slope:.4f}, R²: {r2:.4f}")
        Slope: 1.0000, R²: 1.0000  # Perfect uptrend
    """
    if len(prices) < 2:
        raise ValueError(f"Prices must have at least 2 elements, got {len(prices)}")

    n = len(prices)
    x = np.arange(n, dtype=np.float64)
    y = np.asarray(prices, dtype=np.float64)

    # OLS: β = cov(x, y) / var(x)
    x_mean = np.mean(x)
    y_mean = np.mean(y)

    covariance = np.mean((x - x_mean) * (y - y_mean))
    x_variance = np.mean((x - x_mean) ** 2)

    if x_variance == 0:
        return 0.0, 0.0

    slope = covariance / x_variance
    intercept = y_mean - slope * x_mean

    # Predictions and residuals
    y_pred = intercept + slope * x
    residuals = y - y_pred

    # R² = 1 - (SS_res / SS_tot)
    ss_res = np.sum(residuals**2)
    ss_tot = np.sum((y - y_mean) ** 2)

    if ss_tot == 0:
        r_squared = 0.0
    else:
        r_squared = max(0.0, 1.0 - (ss_res / ss_tot))

    return float(slope), float(r_squared)


def calculate_z_score(prices: np.ndarray, window: int = 20) -> float:
    """
    Calculate Z-score of the most recent price relative to the rolling mean.

    Identifies mean-reversion opportunities:
    - Z-score > +2: Price is +2σ above mean (potential short opportunity).
    - Z-score < -2: Price is -2σ below mean (potential long opportunity).
    - Z-score ≈ 0: Price near equilibrium (neutral).

    Uses rolling window statistics to detect deviations from local mean.

    Args:
        prices: 1D numpy array of prices.
        window: Look-back period for mean and std (default 20).

    Returns:
        z_score: Float representing deviation in standard deviations.

    Raises:
        ValueError: If prices has < window elements.

    Example:
        >>> prices = np.array([100, 101, 99, 102, 98, 105, 97, 110])
        >>> z = calculate_z_score(prices, window=4)
        >>> print(f"Z-score: {z:.2f}")  # Extreme deviation
    """
    if len(prices) < window:
        raise ValueError(
            f"Prices must have at least {window} elements, got {len(prices)}"
        )

    prices_array = np.asarray(prices, dtype=np.float64)
    current_price = prices_array[-1]

    # Use the last 'window' prices for rolling statistics
    window_prices = prices_array[-window:]
    mean = np.mean(window_prices)
    std = np.std(window_prices, ddof=1)  # ddof=1 for sample std

    # Avoid division by zero
    if std < 1e-10:
        return 0.0

    z_score = (current_price - mean) / std
    return float(z_score)


def calculate_position_size(
    balance: float,
    risk_pct: float,
    atr: float,
    contract_size: float = 1.0,
) -> float:
    """
    Calculate position size using inverse volatility (ATR-based) Kelly-adjacent sizing.

    Higher volatility (ATR) → smaller positions.
    Lower volatility (ATR) → larger positions.

    Formula:
        position_size = (balance * risk_pct) / (atr * contract_size)

    This ensures risk per trade is constant regardless of market volatility,
    improving risk-adjusted returns.

    Args:
        balance: Account balance in base currency.
        risk_pct: Risk per trade as percentage [0.0, 1.0] (e.g., 0.02 = 2% risk).
        atr: Average True Range (volatility measure) in pips.
        contract_size: Pip value per lot (default 1.0 for normalized measures).

    Returns:
        position_size: Number of units to trade.

    Raises:
        ValueError: If ATR is ≤ 0 or risk_pct not in [0, 1].

    Example:
        >>> balance = 10000  # USD
        >>> risk_pct = 0.02  # 2% risk per trade
        >>> atr = 50  # 50 pips volatility
        >>> contract_size = 10  # 10 USD per pip per lot
        >>> size = calculate_position_size(balance, risk_pct, atr, contract_size)
        >>> print(f"Position: {size:.2f} lots")
        Position: 0.40 lots  # (10000 * 0.02) / (50 * 10)
    """
    if not 0.0 < risk_pct < 1.0:
        raise ValueError(f"risk_pct must be in (0, 1), got {risk_pct}")

    if atr <= 0:
        raise ValueError(f"ATR must be > 0, got {atr}")

    if contract_size <= 0:
        raise ValueError(f"contract_size must be > 0, got {contract_size}")

    risk_amount = balance * risk_pct
    position_size = risk_amount / (atr * contract_size)

    return float(position_size)
