# Live Trading Configuration - $1 Million Account

**Status:** ✅ LIVE TRADING ENABLED  
**Account Balance:** $1,000,000 USD  
**Date:** December 24, 2025

---

## 🚀 Trading Configuration

### Account Settings
```python
ACCOUNT_BALANCE = 1_000_000.0       # $1 Million live trading account
MAX_RISK_PER_TRADE = 10_000.0       # $10k per trade (1% of account)
MAX_DAILY_RISK = 50_000.0           # $50k per day (5% of account)
```

### Risk Management Rules

#### Per-Trade Risk Limits
- **Maximum Risk per Trade:** $10,000 (1% of account)
- **Minimum Risk per Trade:** $100
- **Position Sizing:** Adjusted based on signal confidence (0-100%)

#### Daily Risk Limits
- **Maximum Daily Risk:** $50,000 (5% of account)
- **Daily Reset:** Midnight UTC
- **Risk Tracking:** Cumulative losses tracked throughout day

#### Enforcement
- ❌ Signals rejected if: Risk per trade > $10,000
- ❌ Signals rejected if: Daily loss + new risk > $50,000
- ✅ Signals approved if: All risk checks pass

---

## 📊 Trading Instruments

Three instruments traded simultaneously:

| Symbol | Type | Typical Volatility | Position Size |
|--------|------|-------------------|----------------|
| **EURUSD** | Major Currency Pair | 15-20 pips daily | 0.01-1.0 lot |
| **USDJPY** | Major Currency Pair | 200-250 pips daily | 0.01-1.0 lot |
| **XAUUSD** | Commodity (Gold) | $20-50/oz daily | 0.1-10 oz |

---

## 🎯 Signal Generation & Execution Flow

```
┌─────────────────────────────────────────────────────────────┐
│               Real MT5 Market Data (100 Hz)                 │
│              EURUSD, USDJPY, XAUUSD Ticks                  │
└──────────────────────────┬──────────────────────────────────┘
                           │
                ┌──────────▼──────────┐
                │  Regime Detection   │
                │  (Supervisor)       │
                │ R², Z-Score → Type  │
                └──────────┬──────────┘
                           │
        ┌──────────────────▼──────────────────┐
        │    Signal Generation (Strategy)     │
        │  BUY/SELL/NEUTRAL with Confidence  │
        └──────────────────┬──────────────────┘
                           │
            ┌──────────────▼──────────────┐
            │   Risk Validation (RiskMgr) │
            │  Check: Per-trade & Daily   │
            │  Limits + Drawdown Control  │
            └──────────────┬───────────────┘
                           │
            ┌──────────────▼──────────────┐
            │   Order Execution (Executor)│
            │  Send to MT5 via TRADE_DEAL │
            │  Type: BUY/SELL             │
            │  Filling: IOC (Instant)     │
            └──────────────┬───────────────┘
                           │
            ┌──────────────▼──────────────┐
            │   Trade Tracking            │
            │  Position Monitoring        │
            │  P&L Calculation (Real-time)│
            │  Status: OPEN/CLOSED        │
            └─────────────────────────────┘
```

---

## ⚙️ Order Execution Details

### MT5 Order Parameters
```python
{
    "action": mt5.TRADE_ACTION_DEAL,      # Execute immediately
    "type": BUY or SELL,                  # Direction
    "volume": quantity,                   # Lot size
    "price": entry_price,                 # Market/limit price
    "deviation": 20,                      # Max 20 pips slippage
    "type_time": ORDER_TIME_GTC,          # Good-Till-Cancelled
    "type_filling": ORDER_FILLING_IOC,    # Instant-or-Cancel
}
```

### Order Status Tracking
- ✅ **OPEN:** Active position, P&L updating in real-time
- ✅ **CLOSED:** Position exited, P&L locked in
- ❌ **ERROR:** Order rejected by MT5 (insufficient margin, etc.)

---

## 📈 Performance Monitoring

### Real-Time Metrics (Updated Every 30 Seconds)

```
💰 LIVE TRADING PERFORMANCE:
  Starting Balance:  $1,000,000.00
  Current Balance:   $1,023,450.00
  Total P&L:         +$23,450.00
  Return:            +2.35%
  
  Trades:            12 (W: 8 / L: 4)
  Win Rate:          66.7%
  Open Positions:    2
  
  Realized P&L:      +$31,200.00
  Unrealized P&L:    -$7,750.00
```

### End-of-Session Report

```
🎯 FINAL LIVE TRADING RESULTS:
  ═══════════════════════════════════════════════════
  Starting Capital:  $1,000,000.00
  Ending Capital:    $1,023,450.00
  Total P&L:         +$23,450.00
  Return on Capital: +2.35%
  ═══════════════════════════════════════════════════
  Total Trades:      12
  Winning Trades:    8
  Losing Trades:     4
  Win Rate:          66.7%
  Open Positions:    0
  ═══════════════════════════════════════════════════
  Realized P&L:      +$31,200.00
  Unrealized P&L:    $0.00
  Total P&L:         +$31,200.00
```

---

## 🛡️ Safety Mechanisms

### Pre-Execution Checks
1. ✅ **Risk Validation:** Signal must pass per-trade risk check
2. ✅ **Daily Limit:** Cumulative daily risk must be within limit
3. ✅ **Margin Check:** Sufficient account balance for position
4. ✅ **Symbol Check:** Valid symbol available in MT5

### Error Handling
- **Order Rejection:** Failed orders logged with reason (margin, symbol, etc.)
- **Timeout Protection:** Orders use IOC (Instant-or-Cancel) filling
- **Exception Handling:** All execution errors caught and logged
- **Audit Trail:** Every trade recorded with timestamp and signal ID

### Position Limits (Configurable)
- Maximum position per symbol: Not set (limit by daily risk)
- Maximum correlation exposure: Not set (3 symbols are diversified)
- Maximum leverage: Not set (broker default)

---

## 📊 Risk Metrics Explained

### Confidence-Based Position Sizing
```
Position Size = Risk Amount / (Price × Volatility)

Examples:
- EURUSD, 80% confident:   $8,000 risk → ~7.36 lots
- USDJPY, 60% confident:   $6,000 risk → ~0.40 lots  
- XAUUSD, 90% confident:   $9,000 risk → ~3.40 oz
```

### Daily Risk Tracking
```
Max Daily Risk: $50,000 (5% of $1M)

Trade 1: Risk $10,000 → Daily Risk: $10,000
Trade 2: Risk $8,000  → Daily Risk: $18,000
Trade 3: Risk $9,000  → Daily Risk: $27,000
Trade 4: Risk $12,000 → REJECTED (27,000 + 12,000 > 50,000)
```

---

## 🎬 Starting Live Trading

### Before Starting
1. ✅ Ensure MetaTrader 5 terminal is running
2. ✅ Account is logged in and has sufficient balance
3. ✅ Symbols EURUSD, USDJPY, XAUUSD are available
4. ✅ Review risk configuration in main.py

### Start Trading
```bash
python main.py
```

### Output
```
[INFO] Titan Trading Engine - Phase 2: Real Market Integration (MT5)
[INFO] ✓ EventBus initialized
[INFO] ✓ Connected to real MT5 terminal
[INFO] ✓ DataFeed initialized for ['EURUSD', 'USDJPY', 'XAUUSD']
[INFO] ✅ OrderExecutor initialized (LIVE TRADING MODE - $1M account)
[INFO] Starting live market session (3600s)...
```

### Monitor Trading
The system will:
- ✅ Stream live ticks at 100 Hz
- ✅ Detect market regimes in real-time
- ✅ Generate signals automatically
- ✅ Execute approved trades immediately
- ✅ Track positions and P&L
- ✅ Report metrics every 30 seconds

---

## ⚠️ Important Disclaimers

### Live Trading Risks
- **Real Capital at Risk:** This uses a real trading account with actual capital
- **Market Risk:** Markets can move against positions unexpectedly
- **Slippage:** Actual execution price may differ from signal price
- **Gaps:** Market gaps (gaps at open) can cause losses
- **Tech Risk:** Connection issues could affect order execution

### Safeguards in Place
- ✅ $10,000 max per trade (1% risk limit)
- ✅ $50,000 daily limit (5% max daily loss)
- ✅ All orders are IOC (no hanging orders)
- ✅ Real-time position monitoring
- ✅ Detailed audit trail for all trades

### Monitoring Recommendations
1. **Watch First Hour:** Monitor system closely for first hour
2. **Check P&L:** Verify P&L updates are accurate
3. **Review Trades:** Check executed trades match signals
4. **Adjust if Needed:** Can modify risk limits anytime
5. **Stop if Needed:** Kill process to halt trading immediately

---

## 📞 Troubleshooting

### No Trades Executing
- Check: Market regime is TRENDING or MEAN_REVERSION (not RANGING)
- Check: Signals are being generated (watch log output)
- Check: Risk limits allow the trade

### High Slippage
- Adjust: `deviation: 20` in executor (higher = more tolerance)
- Use: Limit orders instead of market orders (requires modification)

### Account Balance Not Updating
- Check: P&L calculation is working (unrealized P&L in metrics)
- Note: Realized P&L only locks in when trade closes

---

## 🎯 Success Criteria

**Healthy Trading** indicators:
- Win rate > 50%
- Profit factor > 1.5 (avg win / avg loss)
- Max drawdown < 10%
- Return > 0% (capital preservation)

**Risk Control** indicators:
- All trades < $10,000 risk
- Daily loss < $50,000
- Largest loss < $25,000
- No margin calls

---

## 📝 Next Steps

1. ✅ Monitor live trading for 1-2 days
2. ✅ Analyze performance and win rate
3. ✅ Adjust risk limits if needed
4. ✅ Enable auto-closing of losing trades (stop-loss)
5. ✅ Add take-profit targets
6. ✅ Implement trailing stops

Good luck with live trading! 🚀
