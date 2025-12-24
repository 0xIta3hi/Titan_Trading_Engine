# 🔧 Troubleshooting Guide

## ❌ Error: "AutoTrading disabled by client"

### Problem
```
Order FAILED: XAUUSD BUY 7018.6526 @ 100.00000 (Error: AutoTrading disabled by client)
```

### Root Cause
MetaTrader 5 has the AutoTrading checkbox disabled. This is a safety feature in MT5 that prevents external programs from placing trades.

### ✅ Solution (Takes 1 minute)

1. **Open MetaTrader 5**
2. **Go to Tools → Options** (or Alt+O)
3. **Click "Expert Advisors" tab**
4. **Check the boxes:**
   - ✅ Allow automated trading
   - ✅ Allow DLL imports
   - ✅ Allow live trading

5. **Click OK**
6. **Restart the trading engine**

### Verification
Look for:
```
✅ ORDER EXECUTED: EURUSD BUY 7.5 @ 1.08572
```

Instead of:
```
❌ ORDER FAILED: ... (Error: AutoTrading disabled)
```

---

## ⚠️ Error: "Invalid prices for XAUUSD"

### Problem
```
⚠️  XAUUSD price out of range: 100.00. This usually means the symbol is not properly configured.
```

### Root Cause
The symbol XAUUSD is selected in MT5 but not showing correct price data. This can happen if:
- Symbol not subscribed in MT5
- Wrong XAUUSD instrument (should be Spot Gold, not Futures)
- Connection issue with data feed

### ✅ Solution

**Option 1: Fix the Symbol (Recommended)**
1. Open MetaTrader 5
2. Press Ctrl+U to open Symbols
3. Find XAUUSD
4. Right-click → Show in Market Watch
5. Ensure BID/ASK prices show correctly (should be 2400-2700 range)

**Option 2: Remove XAUUSD Temporarily**
Edit `main.py` and change:
```python
# Line 41 - Current
SYMBOLS = ["EURUSD", "USDJPY", "XAUUSD"]

# Change to
SYMBOLS = ["EURUSD", "USDJPY"]
```

**Option 3: Use Mock Data**
If you don't have real MT5 data, the system automatically switches to mock data:
```
⚠️  Using MOCK market data (MT5 terminal not connected)
```

This is fine for testing and backtesting.

---

## ❌ Error: "MetaTrader 5 terminal is not running"

### Problem
```
ConnectionError: MetaTrader 5 terminal is not running.
Please start MT5 and ensure you are logged in.
```

### Root Cause
Either:
- MT5 is not running
- MT5 is running but not logged in to an account
- MT5 crashed or disconnected

### ✅ Solution

1. **Open MetaTrader 5**
2. **Log in with your broker account**
   - Enter username and password
   - Select broker/server
   - Click OK
3. **Wait for connection** (usually 10-30 seconds)
4. **Restart the trading engine**

### Verify Connection
In MT5, you should see:
- ✅ Green account login at bottom left
- ✅ "Connected" status
- ✅ Account number visible
- ✅ Balance showing in Account Information

---

## ⚠️ Warning: "No tick data available for EURUSD"

### Problem
```
[WARNING] No tick data available for EURUSD
```

Appears repeatedly, no data is flowing.

### Root Cause
MT5 has the symbol but it's not selected for data streaming.

### ✅ Solution

1. Open MetaTrader 5
2. Press Ctrl+U (Symbols dialog)
3. Find the symbol (EURUSD, USDJPY, XAUUSD)
4. Right-click → Show in Market Watch
5. The symbol should move to the left panel

Restart the engine. Should now see:
```
[INFO] Subscribed to EURUSD
```

---

## 🚀 Trades Not Executing (But No Error)

### Problem
Engine is running, signals are generated, but no trades execute.

### Root Cause
Usually one of:
1. **Insufficient account balance** - Risk amount > balance
2. **Market closed** - Weekend/non-trading hours
3. **Order type not supported** - Broker doesn't support IOC orders
4. **Position limit hit** - Broker limit on open positions

### ✅ Solution

**Check Account Balance:**
```python
# In main.py, line 48
ACCOUNT_BALANCE = 1_000_000.0  # Make sure this matches your MT5 balance
```

**Check Market Hours:**
- Forex: Open 22:00 UTC Sunday - 22:00 UTC Friday
- Gold: Similar to Forex
- Check your specific broker's schedule

**Check Position Limit:**
- Most brokers allow 5-10 open positions
- Current setup uses 3 symbols max, should be fine

**Enable DLL imports** (if using custom MT5):
- Tools → Options → Expert Advisors
- ✅ Allow DLL imports

---

## 💰 Balance Not Updating

### Problem
`Current Balance: $1,000,000.00` stays the same even after trades.

### Root Cause
The engine uses simulated balance updates (not reading real balance from MT5 API).

### ✅ Solution

This is normal in simulation mode. For real trading:

1. Check real balance in MT5 Account Information
2. The engine tracks P&L separately for reporting
3. Enable AutoTrading to use real account balance

To verify trades are executing:
```
✅ ORDER EXECUTED: EURUSD BUY 7.5 @ 1.08572
```

Look for "EXECUTED" not "SIMULATED".

---

## 🔄 Signals But No Trades (Even with AutoTrading On)

### Problem
```
📊 EURUSD: SIGNAL BUY (73%) [TRENDING]
```
But no ORDER EXECUTED follows.

### Root Cause
Risk management rejected the trade. Reasons:
1. **Daily limit exceeded** - Already spent $50k today
2. **Per-trade risk too high** - Single trade > $10k
3. **Confidence too low** - Signal < 50% confidence
4. **Signal rejected** - Some validation failed

### ✅ Solution

**Check the logs for rejection reason:**
```
[INFO] Signal rejected: daily risk exceeded ($50000 limit)
```

**If daily limit exceeded:**
- Wait for next trading day
- OR reduce MAX_DAILY_RISK in main.py (line 50)

**If per-trade risk too high:**
- Reduce MAX_RISK_PER_TRADE in main.py (line 49)
- Example: $5,000 instead of $10,000

**If confidence too low:**
- This is working as designed (signal quality filter)
- Usually resolves naturally as market conditions improve

---

## 📊 Extreme P&L Values

### Problem
```
Total P&L: +$999,999,999.00 (clearly wrong)
```

### Root Cause
Price data issue or calculation error.

### ✅ Solution

1. **Restart the engine**
   ```bash
   Ctrl+C
   python main.py
   ```

2. **Check XAUUSD price**
   - Make sure it's in 2400-2700 range (not 100)
   - See "Invalid prices for XAUUSD" section above

3. **Verify symbol data**
   - Open MT5 Market Watch
   - Check all symbols show reasonable prices

---

## 🧪 Testing Without AutoTrading

Want to test without enabling AutoTrading? Use simulation mode:

```bash
python test_live_trading.py --duration 30
```

This:
- ✅ Generates synthetic signals
- ✅ Executes trades in simulation
- ✅ Shows performance metrics
- ✅ Doesn't require AutoTrading enabled
- ✅ Doesn't place real trades

Great for:
- Testing the engine
- Verifying signal generation
- Checking risk management
- Demo purposes

---

## 🆘 Still Not Working?

### Collect Information
1. **Screenshot of the error**
2. **Full error message from logs**
3. **Your broker name** (some don't support certain orders)
4. **MT5 version** (Tools → About MetaTrader 5)
5. **Python version** (`python --version`)

### Check logs
```bash
# Tail the output for errors
python main.py 2>&1 | grep -i error
```

### Common Brokers & Settings
- **IC Markets**: Supports IOC, all symbols, typically no limits
- **Oanda**: Limited symbols, may need FXCM/Oanda specific settings
- **IG**: Limited to certain pairs, check symbol availability
- **Saxo Bank**: Full support, premium broker

Ensure your broker supports:
- ✅ IOC (Instant-or-Cancel) order filling
- ✅ Forex pairs (EURUSD, USDJPY)
- ✅ Gold (XAUUSD) if using it
- ✅ API access for automated trading

---

## ✅ Success Checklist

If all of these show green, you're ready to trade:

- [ ] MT5 running and logged in
- [ ] ✅ Allow automated trading (enabled)
- [ ] ✅ Allow DLL imports (enabled)
- [ ] Symbols showing in Market Watch (EURUSD, USDJPY, XAUUSD)
- [ ] Prices updating (not frozen)
- [ ] Engine starting without connection errors
- [ ] Signals being generated (📊 SIGNAL messages)
- [ ] Trades executing (✅ ORDER EXECUTED messages)
- [ ] P&L updating in real-time

Once all green, you're live! 🚀

