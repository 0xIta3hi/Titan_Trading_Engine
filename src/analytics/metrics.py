"""
Market analytics and performance metrics.

Provides real-time OHLCV data, Sharpe ratio, drawdown analysis, 
and comprehensive trading performance statistics.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class OHLCV:
    """Open, High, Low, Close, Volume data for a candle."""
    
    symbol: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    
    def __repr__(self) -> str:
        return (
            f"OHLCV({self.symbol} {self.timestamp.strftime('%H:%M:%S')}: "
            f"O={self.open:.5f} H={self.high:.5f} L={self.low:.5f} "
            f"C={self.close:.5f} V={self.volume:.0f})"
        )


@dataclass
class DailyStats:
    """Daily market statistics for a single symbol."""
    
    symbol: str
    date: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    high_timestamp: datetime = field(default_factory=datetime.now)
    low_timestamp: datetime = field(default_factory=datetime.now)
    
    def range(self) -> float:
        """Daily price range in pips (or points)."""
        return self.high - self.low
    
    def range_pct(self) -> float:
        """Daily price range as percentage."""
        if self.open == 0:
            return 0.0
        return ((self.high - self.low) / self.open) * 100


@dataclass
class TradeRecord:
    """Record of executed trade for P&L tracking."""
    
    symbol: str
    direction: str  # "BUY" or "SELL"
    entry_price: float
    entry_timestamp: datetime
    quantity: float
    risk_amount: float
    confidence: float
    regime: str
    
    exit_price: Optional[float] = None
    exit_timestamp: Optional[datetime] = None
    
    def pnl(self) -> Optional[float]:
        """Realized P&L in USD. None if position still open."""
        if self.exit_price is None:
            return None
        
        if self.direction == "BUY":
            return (self.exit_price - self.entry_price) * self.quantity
        else:  # SELL
            return (self.entry_price - self.exit_price) * self.quantity
    
    def pnl_pct(self) -> Optional[float]:
        """Return as percentage. None if position still open."""
        if self.exit_price is None:
            return None
        
        if self.direction == "BUY":
            return ((self.exit_price - self.entry_price) / self.entry_price) * 100
        else:  # SELL
            return ((self.entry_price - self.exit_price) / self.entry_price) * 100
    
    def status(self) -> str:
        """Return 'OPEN' or 'CLOSED'."""
        return "CLOSED" if self.exit_price else "OPEN"
    
    def duration(self) -> Optional[timedelta]:
        """Time held (None if still open)."""
        if self.exit_timestamp is None:
            return None
        return self.exit_timestamp - self.entry_timestamp


@dataclass
class PortfolioMetrics:
    """Aggregate portfolio performance statistics."""
    
    initial_balance: float
    current_balance: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    
    largest_win: float = 0.0
    largest_loss: float = 0.0
    
    gross_profit: float = 0.0
    gross_loss: float = 0.0
    
    returns: list[float] = field(default_factory=list)  # Daily returns for Sharpe
    equity_curve: list[float] = field(default_factory=list)  # Balance over time
    
    def total_pnl(self) -> float:
        """Total profit/loss."""
        return self.current_balance - self.initial_balance
    
    def total_return_pct(self) -> float:
        """Total return as percentage."""
        if self.initial_balance == 0:
            return 0.0
        return (self.total_pnl() / self.initial_balance) * 100
    
    def win_rate(self) -> float:
        """Win rate as percentage."""
        if self.total_trades == 0:
            return 0.0
        return (self.winning_trades / self.total_trades) * 100
    
    def profit_factor(self) -> float:
        """Gross profit / Gross loss ratio."""
        if self.gross_loss == 0:
            return 0.0 if self.gross_profit == 0 else float('inf')
        return self.gross_profit / abs(self.gross_loss)
    
    def avg_win(self) -> float:
        """Average winning trade."""
        if self.winning_trades == 0:
            return 0.0
        return self.gross_profit / self.winning_trades
    
    def avg_loss(self) -> float:
        """Average losing trade."""
        if self.losing_trades == 0:
            return 0.0
        return self.gross_loss / self.losing_trades
    
    def expectancy(self) -> float:
        """Expected value per trade."""
        if self.total_trades == 0:
            return 0.0
        return (self.gross_profit + self.gross_loss) / self.total_trades
    
    def sharpe_ratio(self, risk_free_rate: float = 0.02) -> float:
        """
        Sharpe ratio (annualized).
        
        Args:
            risk_free_rate: Annual risk-free rate (default 2%).
        
        Returns:
            Sharpe ratio. Higher is better (>1.0 is good, >2.0 is excellent).
        """
        if len(self.returns) < 2:
            return 0.0
        
        returns = np.array(self.returns)
        mean_return = np.mean(returns)
        std_return = np.std(returns)
        
        if std_return == 0:
            return 0.0
        
        # Annualize (assuming daily returns, 252 trading days/year)
        daily_excess_return = mean_return - (risk_free_rate / 252)
        sharpe = (daily_excess_return / std_return) * np.sqrt(252)
        
        return float(sharpe)
    
    def max_drawdown(self) -> float:
        """
        Maximum drawdown from peak equity.
        
        Returns:
            Drawdown as percentage. Always <= 0.
        """
        if len(self.equity_curve) < 2:
            return 0.0
        
        equity = np.array(self.equity_curve)
        peak = np.maximum.accumulate(equity)
        drawdown = (equity - peak) / peak
        
        return float(np.min(drawdown) * 100)
    
    def recovery_factor(self) -> float:
        """
        Total return / Max drawdown (absolute value).
        Higher is better. Measures return per unit of drawdown risk.
        """
        max_dd = self.max_drawdown()
        if max_dd == 0 or max_dd > 0:  # No valid drawdown
            return 0.0
        
        return self.total_return_pct() / abs(max_dd)


class MarketAnalytics:
    """
    Real-time market analytics engine.
    
    Tracks OHLCV bars, daily statistics, and trade records for
    comprehensive market and portfolio analysis.
    """
    
    def __init__(self, symbols: list[str], session_start: datetime):
        """
        Initialize analytics.
        
        Args:
            symbols: List of trading symbols.
            session_start: Session start time for daily metrics reset.
        """
        self.symbols = symbols
        self.session_start = session_start
        
        # OHLCV tracking (1-minute bars)
        self._current_minute: dict[str, Optional[OHLCV]] = {s: None for s in symbols}
        self._minute_bars: dict[str, list[OHLCV]] = {s: [] for s in symbols}
        
        # Daily stats
        self._daily_stats: dict[str, DailyStats] = {
            s: DailyStats(
                symbol=s,
                date=session_start,
                open=0.0,
                high=0.0,
                low=0.0,
                close=0.0,
                volume=0.0,
            )
            for s in symbols
        }
        
        # Trade tracking
        self._trades: list[TradeRecord] = []
        
        logger.info(f"MarketAnalytics initialized for {symbols}")
    
    def update_tick(self, symbol: str, timestamp: datetime, bid: float, ask: float, volume: float) -> None:
        """
        Update with a new tick.
        
        Args:
            symbol: Trading symbol.
            timestamp: Tick timestamp.
            bid: Bid price.
            ask: Ask price.
            volume: Trade volume.
        """
        mid = (bid + ask) / 2
        
        # Update daily stats
        daily = self._daily_stats[symbol]
        if daily.open == 0:
            daily.open = mid
        
        daily.high = max(daily.high, mid)
        daily.low = min(daily.low, mid) if daily.low > 0 else mid
        daily.close = mid
        daily.volume += volume
        
        if mid == daily.high:
            daily.high_timestamp = timestamp
        if mid == daily.low:
            daily.low_timestamp = timestamp
    
    def get_daily_stats(self, symbol: str) -> DailyStats:
        """Get daily OHLCV and statistics."""
        return self._daily_stats[symbol]
    
    def get_all_daily_stats(self) -> dict[str, DailyStats]:
        """Get daily stats for all symbols."""
        return self._daily_stats.copy()
    
    def record_trade(
        self,
        symbol: str,
        direction: str,
        entry_price: float,
        quantity: float,
        risk_amount: float,
        confidence: float,
        regime: str,
    ) -> TradeRecord:
        """
        Record a new trade entry.
        
        Args:
            symbol: Trading symbol.
            direction: "BUY" or "SELL".
            entry_price: Entry price.
            quantity: Position size.
            risk_amount: Risk in USD.
            confidence: Signal confidence (0-100%).
            regime: Market regime (TRENDING, MEAN_REVERSION, RANGING).
        
        Returns:
            TradeRecord instance.
        """
        trade = TradeRecord(
            symbol=symbol,
            direction=direction,
            entry_price=entry_price,
            entry_timestamp=datetime.now(),
            quantity=quantity,
            risk_amount=risk_amount,
            confidence=confidence,
            regime=regime,
        )
        self._trades.append(trade)
        return trade
    
    def close_trade(self, trade: TradeRecord, exit_price: float) -> None:
        """
        Close a trade with exit price.
        
        Args:
            trade: TradeRecord to close.
            exit_price: Exit price.
        """
        trade.exit_price = exit_price
        trade.exit_timestamp = datetime.now()
    
    def get_portfolio_metrics(self, initial_balance: float, current_balance: float) -> PortfolioMetrics:
        """
        Calculate aggregate portfolio metrics.
        
        Args:
            initial_balance: Starting account balance.
            current_balance: Current account balance.
        
        Returns:
            PortfolioMetrics with all statistics.
        """
        closed_trades = [t for t in self._trades if t.exit_price is not None]
        
        winning_trades = [t for t in closed_trades if (t.pnl() or 0) > 0]
        losing_trades = [t for t in closed_trades if (t.pnl() or 0) < 0]
        
        gross_profit = sum(t.pnl() for t in winning_trades)
        gross_loss = sum(t.pnl() for t in losing_trades)
        
        # Collect daily returns (simplified: use trade returns)
        returns = [t.pnl_pct() or 0 for t in closed_trades]
        
        # Build equity curve
        equity_curve = [initial_balance]
        running_equity = initial_balance
        for trade in self._trades:
            if trade.pnl() is not None:
                running_equity += trade.pnl()
                equity_curve.append(running_equity)
        
        metrics = PortfolioMetrics(
            initial_balance=initial_balance,
            current_balance=current_balance,
            total_trades=len(self._trades),
            winning_trades=len(winning_trades),
            losing_trades=len(losing_trades),
            largest_win=max((t.pnl() for t in winning_trades), default=0.0),
            largest_loss=min((t.pnl() for t in losing_trades), default=0.0),
            gross_profit=gross_profit,
            gross_loss=gross_loss,
            returns=returns,
            equity_curve=equity_curve,
        )
        
        return metrics
    
    def get_trades(self, symbol: Optional[str] = None, status: Optional[str] = None) -> list[TradeRecord]:
        """
        Filter trades.
        
        Args:
            symbol: Filter by symbol (None = all).
            status: Filter by "OPEN" or "CLOSED" (None = all).
        
        Returns:
            List of matching trades.
        """
        trades = self._trades
        
        if symbol:
            trades = [t for t in trades if t.symbol == symbol]
        
        if status:
            trades = [t for t in trades if t.status() == status]
        
        return trades
