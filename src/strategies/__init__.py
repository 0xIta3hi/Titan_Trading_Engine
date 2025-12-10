"""Trading strategies and mathematical utilities."""

from src.strategies.supervisor import Supervisor
from src.strategies.math_utils import (
    calculate_slope_and_r_squared,
    calculate_z_score,
    calculate_position_size,
)

__all__ = [
    "Supervisor",
    "calculate_slope_and_r_squared",
    "calculate_z_score",
    "calculate_position_size",
]
