import pandas as pd
from ta.trend import ADXIndicator, EMAIndicator, SMAIndicator
from ta.momentum import RSIIndicator
import numpy as np

def calculate_supertrend(df, period=10, multiplier=3):
    """Calculates Supertrend indicator."""
    high = df['High'].squeeze()
    low = df['Low'].squeeze()
    close = df['Close'].squeeze()
    
    # Calculate True Range (TR)
    t1 = high - low
    t2 = abs(high - close.shift(1))
    t3 = abs(low - close.shift(1))
    tr = pd.DataFrame({'t1': t1, 't2': t2, 't3': t3}).max(axis=1)
    
    # Calculate Average True Range (ATR)
    atr = tr.ewm(alpha=1/period, adjust=False).mean() # RMA calculation for ATR

    # Basic Upper and Lower Bands
    hl2 = (high + low) / 2
    final_ub = hl2 + (multiplier * atr)
    final_lb = hl2 - (multiplier * atr)

    supertrend = pd.Series(index=df.index, dtype='float64')
    direction = pd.Series(index=df.index, dtype='int32') # 1 for uptrend, -1 for downtrend
    
    # Initialize
    for i in range(period, len(df)):
        if i == period:
            supertrend.iloc[i] = final_ub.iloc[i]
            direction.iloc[i] = 1
            continue
            
        # Update Final Upper Band
        if final_ub.iloc[i] < final_ub.iloc[i-1] or close.iloc[i-1] > final_ub.iloc[i-1]:
            final_ub.iloc[i] = final_ub.iloc[i]
        else:
            final_ub.iloc[i] = final_ub.iloc[i-1]
            
        # Update Final Lower Band
        if final_lb.iloc[i] > final_lb.iloc[i-1] or close.iloc[i-1] < final_lb.iloc[i-1]:
            final_lb.iloc[i] = final_lb.iloc[i]
        else:
            final_lb.iloc[i] = final_lb.iloc[i-1]
            
        # Calculate Direction and Supertrend value
        if close.iloc[i] > final_ub.iloc[i-1]:
            direction.iloc[i] = 1
        elif close.iloc[i] < final_lb.iloc[i-1]:
            direction.iloc[i] = -1
        else:
            direction.iloc[i] = direction.iloc[i-1]
            
        if direction.iloc[i] == 1:
            supertrend.iloc[i] = final_lb.iloc[i]
        else:
            supertrend.iloc[i] = final_ub.iloc[i]
            
    df['Supertrend'] = supertrend
    df['Supertrend_Direction'] = direction
    return df

def calculate_indicators(df):
    """Calculates all necessary indicators for the strategy."""
    if df.empty or len(df) < 50:
        return df

    close = df['Close'].squeeze()
    high = df['High'].squeeze()
    low = df['Low'].squeeze()
    vol = df['Volume'].squeeze()

    # Moving Averages
    df['EMA_50'] = EMAIndicator(close=close, window=50).ema_indicator()
    df['EMA_200'] = EMAIndicator(close=close, window=200).ema_indicator()
    
    # RSI
    df['RSI'] = RSIIndicator(close=close, window=14).rsi()
    
    # ADX
    adx_ind = ADXIndicator(high=high, low=low, close=close, window=14)
    df['ADX'] = adx_ind.adx()
    
    # Volume Logic
    df['Volume_SMA'] = vol.rolling(window=20).mean()
    # Continuous Volume Increasing (Ensure finished days: Yesterday > Day Before)
    df['Volume_Increasing'] = (vol.shift(1) > vol.shift(2))
    
    # Golden Crossover (SMA 50 > SMA 200)
    df['SMA_50'] = SMAIndicator(close=close, window=50).sma_indicator()
    df['SMA_200'] = SMAIndicator(close=close, window=200).sma_indicator()
    df['Golden_Cross'] = df['SMA_50'] > df['SMA_200']
    
    # Supertrend
    df = calculate_supertrend(df, period=10, multiplier=3)
    
    df.dropna(inplace=True)
    return df

def check_entry_condition(row):
    try:
        # Strict Strategy for Higher Win Rates
        # Volume must be > 1.5x the 20-day avg on the last completed day (shift(1))
        vol_surge = row['Volume'] > (row['Volume_SMA'] * 1.5)
        
        if (row['RSI'] > 60 and 
            row['Golden_Cross'] and
            row['Volume_Increasing'] and
            vol_surge and
            row['Close'] > row['EMA_50'] and 
            row['EMA_50'] > row['EMA_200'] and
            row['Close'] > row['Supertrend']):
            return True
        return False
    except KeyError:
        return False

def check_exit_condition(row):
    try:
        # Exit quickly if macro drops, or if fast momentum breaks to lock in profit/cut losses early
        # Exit quickly if macro drops, or if momentum breaks
        if (row['Close'] < row['Supertrend'] or 
            row['EMA_50'] < row['EMA_200']):
            return True
        return False
    except KeyError:
        return False

def run_backtest(df, interval="1d"):
    """
    Simulates trades over historical dates with time-based stop limits.
    """
    trades = []
    in_position = False
    entry_price = 0
    entry_date = None
    bars_held = 0
    target_price = 0
    
    # 60 days = ~12 weeks. 12 bars = 12 weeks for weekly chart.
    if interval == "1d":
        max_bars = 60
    elif interval == "1mo":
        max_bars = 3
    else:
        max_bars = 12
    
    for date, row in df.iterrows():
        if not in_position:
            if check_entry_condition(row):
                in_position = True
                entry_price = row['Close']
                entry_date = date.strftime('%Y-%m-%d')
                bars_held = 0
                
                # Calculate structural Take-Profit at 1:2 R:R (with a minimum 5% floor)
                sl = row['Supertrend']
                risk = entry_price - sl if entry_price > sl else entry_price * 0.05
                target_price = max(entry_price + (risk * 2), entry_price * 1.05)
        else:
            bars_held += 1
            
            # 1. Trigger Take-Profit if intraday High touches our Target
            if row['High'] >= target_price:
                exit_price = target_price
                exit_date = date.strftime('%Y-%m-%d')
                profit = (exit_price - entry_price) / entry_price * 100
                
                trades.append({
                    "entry_date": entry_date,
                    "exit_date": exit_date,
                    "entry_price": round(entry_price, 2),
                    "exit_price": round(exit_price, 2),
                    "profit_percent": round(float(profit), 2),
                    "win": bool(profit >= 1.0),
                    "exit_reason": "Hit Target"
                })
                in_position = False
                continue

            # 2. Trigger Time Stop if trade drags sideways too long
            if bars_held >= max_bars:
                exit_price = row['Close']
                exit_date = date.strftime('%Y-%m-%d')
                profit = (exit_price - entry_price) / entry_price * 100
                
                trades.append({
                    "entry_date": entry_date,
                    "exit_date": exit_date,
                    "entry_price": round(entry_price, 2),
                    "exit_price": round(exit_price, 2),
                    "profit_percent": round(float(profit), 2),
                    "win": bool(profit >= 5.0),
                    "exit_reason": "Time Stop"
                })
                in_position = False
                continue
                
            # 3. Trigger Trailing Stop Loss if momentum completely breaks
            if check_exit_condition(row):
                exit_price = row['Close']
                exit_date = date.strftime('%Y-%m-%d')
                profit = (exit_price - entry_price) / entry_price * 100
                
                trades.append({
                    "entry_date": entry_date,
                    "exit_date": exit_date,
                    "entry_price": round(entry_price, 2),
                    "exit_price": round(exit_price, 2),
                    "profit_percent": round(float(profit), 2),
                    "win": bool(profit >= 5.0),
                    "exit_reason": "Stop Loss"
                })
                in_position = False
    
    # If still in position at the end, mark it as open or force close
    if in_position:
        last_date = df.index[-1]
        exit_price = df['Close'].iloc[-1]
        profit = (exit_price - entry_price) / entry_price * 100
        trades.append({
            "entry_date": entry_date,
            "exit_date": last_date.strftime('%Y-%m-%d'),
            "entry_price": round(float(entry_price), 2),
            "exit_price": round(float(exit_price), 2),
            "profit_percent": round(float(profit), 2),
            "win": bool(profit >= 1.0),
            "exit_reason": "Open"
        })

    win_count = sum([1 for t in trades if t.get('win', False)])
    total_trades = len(trades)
    win_rate = (win_count / total_trades * 100) if total_trades > 0 else 0
    
    return {
        "total_trades": total_trades,
        "wins": win_count,
        "losses": total_trades - win_count,
        "win_rate": round(win_rate, 2),
        "trades": trades
    }
