"""Unit tests for mathematical utilities."""

import numpy as np
import pytest

from src.strategies.math_utils import (
    calculate_slope_and_r_squared,
    calculate_z_score,
    calculate_position_size,
)


class TestSlopeAndRSquared:
    """Tests for calculate_slope_and_r_squared function."""

    def test_perfect_uptrend(self):
        """Test with perfectly linear uptrending data."""
        prices = np.array([100.0, 101.0, 102.0, 103.0, 104.0])
        slope, r2 = calculate_slope_and_r_squared(prices)

        assert slope > 0, "Uptrend should have positive slope"
        assert r2 > 0.99, "Perfect trend should have R² ≈ 1.0"

    def test_perfect_downtrend(self):
        """Test with perfectly linear downtrending data."""
        prices = np.array([105.0, 104.0, 103.0, 102.0, 101.0])
        slope, r2 = calculate_slope_and_r_squared(prices)

        assert slope < 0, "Downtrend should have negative slope"
        assert r2 > 0.99, "Perfect trend should have R² ≈ 1.0"

    def test_no_trend(self):
        """Test with flat (no trend) data."""
        prices = np.array([100.0, 100.0, 100.0, 100.0, 100.0])
        slope, r2 = calculate_slope_and_r_squared(prices)

        assert abs(slope) < 1e-10, "Flat data should have slope ≈ 0"
        assert r2 < 0.01, "Flat data should have R² ≈ 0"

    def test_noisy_trend(self):
        """Test with noisy trend data."""
        np.random.seed(42)
        x = np.arange(100)
        prices = 100.0 + 0.5 * x + np.random.normal(0, 2.0, 100)

        slope, r2 = calculate_slope_and_r_squared(prices)

        assert 0.4 < slope < 0.6, f"Slope should be near 0.5, got {slope}"
        assert 0.7 < r2 < 0.95, f"R² should be moderate, got {r2}"

    def test_insufficient_data(self):
        """Test that function raises error with < 2 prices."""
        with pytest.raises(ValueError):
            calculate_slope_and_r_squared(np.array([100.0]))


class TestZScore:
    """Tests for calculate_z_score function."""

    def test_at_mean(self):
        """Test Z-score when price equals mean."""
        prices = np.array([100.0, 100.0, 100.0, 100.0, 100.0])
        z = calculate_z_score(prices, window=5)

        assert abs(z) < 1e-10, "Z-score at mean should be 0"

    def test_above_mean(self):
        """Test Z-score when price is above mean."""
        prices = np.array([100.0, 100.0, 100.0, 100.0, 102.0])
        z = calculate_z_score(prices, window=5)

        assert z > 0, "Z-score above mean should be positive"

    def test_below_mean(self):
        """Test Z-score when price is below mean."""
        prices = np.array([100.0, 100.0, 100.0, 100.0, 98.0])
        z = calculate_z_score(prices, window=5)

        assert z < 0, "Z-score below mean should be negative"

    def test_extreme_deviation(self):
        """Test with extreme price deviation."""
        prices = np.array([100.0, 100.0, 100.0, 100.0, 105.0])
        z = calculate_z_score(prices, window=5)

        assert abs(z) > 1.0, "Extreme deviation should have |Z| > 1"

    def test_insufficient_data(self):
        """Test that function raises error when window too large."""
        with pytest.raises(ValueError):
            calculate_z_score(np.array([100.0, 101.0]), window=5)


class TestPositionSize:
    """Tests for calculate_position_size function."""

    def test_basic_calculation(self):
        """Test basic position sizing."""
        balance = 10_000.0
        risk_pct = 0.02  # 2%
        atr = 50.0
        contract_size = 10.0

        size = calculate_position_size(balance, risk_pct, atr, contract_size)

        # (10000 * 0.02) / (50 * 10) = 200 / 500 = 0.4
        expected = (balance * risk_pct) / (atr * contract_size)
        assert abs(size - expected) < 1e-6, f"Expected {expected}, got {size}"

    def test_higher_volatility_smaller_position(self):
        """Test that higher ATR results in smaller position size."""
        balance = 10_000.0
        risk_pct = 0.02

        size_low_vol = calculate_position_size(balance, risk_pct, atr=25.0)
        size_high_vol = calculate_position_size(balance, risk_pct, atr=50.0)

        assert size_low_vol > size_high_vol, "Higher volatility should result in smaller position"

    def test_invalid_risk_pct(self):
        """Test that invalid risk_pct raises error."""
        with pytest.raises(ValueError):
            calculate_position_size(10_000, risk_pct=1.5, atr=50)

        with pytest.raises(ValueError):
            calculate_position_size(10_000, risk_pct=0.0, atr=50)

    def test_invalid_atr(self):
        """Test that invalid ATR raises error."""
        with pytest.raises(ValueError):
            calculate_position_size(10_000, risk_pct=0.02, atr=0.0)

        with pytest.raises(ValueError):
            calculate_position_size(10_000, risk_pct=0.02, atr=-10.0)

    def test_invalid_contract_size(self):
        """Test that invalid contract_size raises error."""
        with pytest.raises(ValueError):
            calculate_position_size(10_000, risk_pct=0.02, atr=50, contract_size=0.0)
