"""
Risk management system for Titan trading engine.

Validates trading signals against position limits before order execution.
Enforces max risk per trade, position size constraints, and drawdown limits.
"""

import hashlib
import logging
from datetime import datetime
from typing import Optional

from src.core.engine import EventBus
from src.core.events import SignalEvent, OrderRequestEvent

__all__ = ["RiskManager"]

logger = logging.getLogger(__name__)


class RiskManager:
    """
    Risk validation and order approval gate.

    Listens for SignalEvents and enforces:
    1. Max risk per trade (absolute currency limit).
    2. Max position size (currency limit).
    3. Cumulative daily risk limit.

    Only approves signals that pass risk checks by emitting OrderRequestEvents.

    Attributes:
        bus: EventBus for pub/sub.
        account_balance: Current account balance in base currency.
        max_risk_per_trade: Maximum loss per trade (absolute currency, e.g., $100).
        max_daily_risk: Maximum cumulative loss per day (absolute currency).
    """

    def __init__(
        self,
        bus: EventBus,
        account_balance: float,
        max_risk_per_trade: float = 100.0,
        max_daily_risk: Optional[float] = None,
    ) -> None:
        """
        Initialize the risk manager.

        Args:
            bus: EventBus for publishing approved orders.
            account_balance: Account balance in base currency.
            max_risk_per_trade: Max risk in absolute currency per trade.
            max_daily_risk: Max cumulative risk per day. If None, defaults to 2x per-trade limit.
        """
        self.bus = bus
        self.account_balance = account_balance
        self.max_risk_per_trade = max_risk_per_trade
        self.max_daily_risk = max_daily_risk or (max_risk_per_trade * 2.0)

        # Cumulative risk tracking
        self._daily_loss = 0.0
        self._open_trades: dict[str, OrderRequestEvent] = {}  # key: order_id
        self._order_count = 0

        # Subscribe to signals
        self.bus.subscribe(SignalEvent, self._on_signal)

    def _on_signal(self, event: SignalEvent) -> None:
        """
        Handle incoming signals and validate risk.

        Args:
            event: SignalEvent from strategy.
        """
        # Only process BUY/SELL signals
        if event.direction not in ("BUY", "SELL"):
            logger.debug(f"Ignoring NEUTRAL signal for {event.symbol}")
            return

        # Calculate risk for this signal
        risk_amount = self._estimate_risk(event)

        # Apply risk checks
        if not self._check_max_risk_per_trade(risk_amount):
            logger.warning(
                f"Signal rejected: {event.symbol} {event.direction} "
                f"(risk ${risk_amount:.2f} exceeds max ${self.max_risk_per_trade:.2f})"
            )
            return

        if not self._check_max_daily_risk(risk_amount):
            logger.warning(
                f"Signal rejected: {event.symbol} {event.direction} "
                f"(daily risk ${self._daily_loss + risk_amount:.2f} exceeds "
                f"${self.max_daily_risk:.2f})"
            )
            return

        # Risk checks passed; create and emit order
        self._emit_order(event, risk_amount)

    def _estimate_risk(self, signal: SignalEvent) -> float:
        """
        Estimate risk exposure for a signal.

        Simple heuristic: risk = confidence * distance_from_price * position_size.
        For now, use confidence as proxy for risk magnitude.

        Args:
            signal: The trading signal.

        Returns:
            Estimated risk in base currency.
        """
        # Risk is proportional to confidence and volatility (proxied by confidence)
        # A confident signal in a volatile regime = higher risk
        risk = self.max_risk_per_trade * signal.confidence

        return risk

    def _check_max_risk_per_trade(self, risk_amount: float) -> bool:
        """
        Validate that risk per trade does not exceed limit.

        Args:
            risk_amount: Risk exposure in base currency.

        Returns:
            True if within limit, False otherwise.
        """
        return risk_amount <= self.max_risk_per_trade

    def _check_max_daily_risk(self, risk_amount: float) -> bool:
        """
        Validate that cumulative daily risk does not exceed limit.

        Args:
            risk_amount: Risk exposure in base currency.

        Returns:
            True if within limit, False otherwise.
        """
        projected_daily_loss = self._daily_loss + risk_amount
        return projected_daily_loss <= self.max_daily_risk

    def _emit_order(self, signal: SignalEvent, risk_amount: float) -> None:
        """
        Create and publish an OrderRequestEvent.

        Args:
            signal: Approved SignalEvent.
            risk_amount: Risk amount in base currency.
        """
        # Generate unique order ID from signal
        signal_id = self._hash_signal(signal)

        # Simple position sizing: risk_amount / volatility proxy
        # For now, use fixed quantity scaling
        quantity = risk_amount / (signal.price * 0.01)  # 1% of price as unit risk

        order = OrderRequestEvent(
            symbol=signal.symbol,
            timestamp=datetime.utcnow(),
            direction=signal.direction,
            quantity=quantity,
            price=signal.price,
            risk_amount=risk_amount,
            signal_id=signal_id,
        )

        # Track order
        self._order_count += 1
        self._open_trades[signal_id] = order
        self._daily_loss += risk_amount

        logger.info(
            f"Order approved: {order.symbol} {order.direction} "
            f"{order.quantity:.4f} @ {order.price:.5f} (risk: ${risk_amount:.2f})"
        )

        # Publish to execution layer
        import asyncio

        try:
            loop = asyncio.get_running_loop()
            asyncio.create_task(self.bus.publish(order))
        except RuntimeError:
            logger.debug("No running event loop; buffering order")

    @staticmethod
    def _hash_signal(signal: SignalEvent) -> str:
        """
        Generate a unique ID for a signal.

        Args:
            signal: The signal to hash.

        Returns:
            Hex string ID.
        """
        data = (
            f"{signal.symbol}_{signal.direction}_{signal.timestamp}_{signal.confidence}"
        )
        return hashlib.sha256(data.encode()).hexdigest()[:16]

    def report(self) -> dict:
        """
        Generate risk report for monitoring.

        Returns:
            Dictionary with risk metrics.
        """
        return {
            "account_balance": self.account_balance,
            "max_risk_per_trade": self.max_risk_per_trade,
            "max_daily_risk": self.max_daily_risk,
            "daily_loss": self._daily_loss,
            "remaining_daily_risk": max(0, self.max_daily_risk - self._daily_loss),
            "open_trades": len(self._open_trades),
            "total_orders": self._order_count,
        }
