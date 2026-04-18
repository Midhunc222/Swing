from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import yfinance as yf
import pandas as pd
from tickers import NIFTY_500_TICKERS, NIFTY_100_TICKERS, NIFTY_50_TICKERS
from strategy import calculate_indicators, run_backtest, check_entry_condition
from typing import List, Optional
import os
import time
import requests

# Configure yfinance to use a browser-like User-Agent
# This reduces the chance of 403 Forbidden errors on Vercel
session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
})

app = FastAPI(title="Nifty 500 Swing Analyzer")

# In-Memory Cache — expires at midnight (new trading day)
DATA_CACHE = {}

def is_cache_valid(cache_key: str) -> bool:
    """Cache is valid only if it was built today (same calendar date)."""
    if cache_key not in DATA_CACHE:
        return False
    from datetime import datetime, timezone
    cached_date = DATA_CACHE[cache_key]['date']
    today = datetime.now().strftime('%Y-%m-%d')
    return cached_date == today

# Allow CORS for local dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class BacktestRequest(BaseModel):
    ticker: str
    interval: str = "1d" # '1d', '1wk'

@app.get("/api/tickers")
async def get_tickers():
    return {"tickers": NIFTY_500_TICKERS}

# Sector benchmark PE/PB ranges (approximate NSE sector medians)
SECTOR_BENCHMARKS = {
    "Technology": {"pe": 30, "pb": 6, "peg": 1.5},
    "Financial Services": {"pe": 18, "pb": 2.5, "peg": 1.2},
    "Healthcare": {"pe": 28, "pb": 4, "peg": 1.8},
    "Consumer Cyclical": {"pe": 35, "pb": 5, "peg": 1.5},
    "Consumer Defensive": {"pe": 40, "pb": 8, "peg": 2.0},
    "Industrials": {"pe": 30, "pb": 4, "peg": 1.5},
    "Energy": {"pe": 12, "pb": 1.8, "peg": 1.0},
    "Basic Materials": {"pe": 15, "pb": 2.0, "peg": 1.2},
    "Utilities": {"pe": 18, "pb": 2.5, "peg": 1.5},
    "Real Estate": {"pe": 20, "pb": 2.0, "peg": 1.3},
    "Communication Services": {"pe": 25, "pb": 3.5, "peg": 1.4},
    "default": {"pe": 25, "pb": 3.5, "peg": 1.5},
}

@app.get("/api/fundamentals/{ticker}")
async def get_fundamentals(ticker: str):
    try:
        info = yf.Ticker(ticker).info
        sector = info.get("sector", "default")
        bench = SECTOR_BENCHMARKS.get(sector, SECTOR_BENCHMARKS["default"])

        def fmt(v, decimals=2):
            if v is None or v == 'N/A': return None
            try: return round(float(v), decimals)
            except: return None

        def fmt_large(v):
            if v is None: return None
            try:
                v = float(v)
                if v >= 1e12: return f"₹{v/1e12:.2f}T"
                if v >= 1e9:  return f"₹{v/1e9:.2f}B"
                if v >= 1e7:  return f"₹{v/1e7:.2f}Cr"
                return f"₹{v:,.0f}"
            except: return None

        pe   = fmt(info.get("trailingPE"))
        fpe  = fmt(info.get("forwardPE"))
        pb   = fmt(info.get("priceToBook"))
        peg  = fmt(info.get("pegRatio"))
        ev_ebitda = fmt(info.get("enterpriseToEbitda"))
        roe  = fmt(info.get("returnOnEquity"))
        debt_eq = fmt(info.get("debtToEquity"))
        div_yield = fmt(info.get("dividendYield"))
        profit_margin = fmt(info.get("profitMargins"))
        revenue_growth = fmt(info.get("revenueGrowth"))
        earnings_growth = fmt(info.get("earningsGrowth"))
        promoter_holding = fmt(info.get("heldPercentInsiders"))

        # Entry suggestion logic
        signals = []
        cautions = []
        if pe and bench["pe"]:
            if pe < bench["pe"] * 0.8:  signals.append(f"PE ({pe}) is undervalued vs sector ({bench['pe']}x)")
            elif pe > bench["pe"] * 1.4: cautions.append(f"PE ({pe}) is expensive vs sector ({bench['pe']}x)")
        if pb and bench["pb"]:
            if pb < bench["pb"] * 0.8: signals.append(f"PB ({pb}) is below sector avg ({bench['pb']}x) — asset cheap")
            elif pb > bench["pb"] * 1.5: cautions.append(f"PB ({pb}) is stretched vs sector ({bench['pb']}x)")
        if peg and peg < 1.0: signals.append(f"PEG ({peg}) < 1 — growth potentially underpriced")
        if roe and float(roe) > 0.18: signals.append(f"ROE ({round(roe*100,1)}%) shows strong capital efficiency")
        if debt_eq and float(debt_eq) < 0.5: signals.append("Low Debt/Equity — financials are clean")
        elif debt_eq and float(debt_eq) > 1.5: cautions.append(f"High Debt/Equity ({debt_eq}) — watch leverage")
        if revenue_growth and float(revenue_growth) > 0.15: signals.append(f"Revenue growing {round(revenue_growth*100,1)}% YoY")
        if earnings_growth and float(earnings_growth) > 0.20: signals.append(f"Earnings growing {round(earnings_growth*100,1)}% YoY")

        lt_verdict = "Attractive" if len(signals) >= 3 else "Neutral" if len(signals) >= 1 else "Avoid"
        swing_verdict = "Strong" if (pe and pe < bench["pe"] and revenue_growth and float(revenue_growth) > 0) else "Moderate"

        officers = info.get("companyOfficers", [])
        mgmt = [{"name": o.get("name",""), "title": o.get("title","")} for o in officers[:4]]

        return {
            "name": info.get("longName", ticker),
            "sector": sector,
            "industry": info.get("industry", "N/A"),
            "description": (info.get("longBusinessSummary", "") or "")[:400] + "...",
            "market_cap": fmt_large(info.get("marketCap")),
            "pe": pe, "forward_pe": fpe, "pb": pb, "peg": peg,
            "ev_ebitda": ev_ebitda, "roe": fmt(roe*100 if roe else None, 1),
            "debt_to_equity": debt_eq,
            "dividend_yield": fmt(div_yield*100 if div_yield else None, 2),
            "profit_margin": fmt(profit_margin*100 if profit_margin else None, 1),
            "revenue_growth": fmt(revenue_growth*100 if revenue_growth else None, 1),
            "earnings_growth": fmt(earnings_growth*100 if earnings_growth else None, 1),
            "promoter_holding": fmt(promoter_holding*100 if promoter_holding else None, 1),
            "sector_bench": bench,
            "ltp": fmt(info.get("currentPrice") or info.get("regularMarketPrice")),
            "52w_high": fmt(info.get("fiftyTwoWeekHigh")),
            "52w_low": fmt(info.get("fiftyTwoWeekLow")),
            "management": mgmt,
            "signals": signals,
            "cautions": cautions,
            "lt_verdict": lt_verdict,
            "swing_verdict": swing_verdict,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/screener")
async def screen_stocks(interval: str = "1d", force: bool = False):
    breakout_stocks = []
    # Multi-tier speed logic for Vercel vs Local
    is_vercel = os.environ.get('VERCEL') == '1'
    tickers = NIFTY_50_TICKERS if is_vercel else NIFTY_500_TICKERS
    period = "1y" if is_vercel else ("2y" if interval == "1d" else "max")
    
    cache_key = f"screener_{interval}"
    now = time.time()
    
    try:
        # Use the optimized tickers for this environment
        if not force and is_cache_valid(cache_key):
            data = DATA_CACHE[cache_key]['data']
        else:
            from datetime import datetime
            # Pass the custom session to yfinance
            data = yf.download(tickers, period=period, interval=interval, group_by="ticker", threads=True, progress=False, session=session)
            DATA_CACHE[cache_key] = {'data': data, 'date': datetime.now().strftime('%Y-%m-%d')}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Data Download Failed: {str(e)}")

    
    total_universe = len(tickers)
    success_count = 0
    fail_count = 0
    
    for ticker in tickers:
        try:
            if len(data.columns.levels[0]) > 0 and ticker in data.columns.levels[0]:
                 df = data[ticker].copy()
            else:
                 df = data.copy()
                 
            df.dropna(how='all', inplace=True)
            if df.empty or len(df) < 50:
                continue
                
            df = calculate_indicators(df)
            if df.empty:
                continue
                
            last_bar = df.iloc[-1]
            vol = float(last_bar['Volume'])
            vol_sma = float(last_bar['Volume_SMA'])
            adx = float(last_bar['ADX'])
            rsi = float(last_bar['RSI'])
            supertrend_val = float(last_bar['Supertrend'])
            close_price = float(last_bar['Close'])

            # --- SELECTIVE BACKTESTING (Optimization for Serverless) ---
            # Define basic technical filter (within buffer of supertrend and showing momentum)
            sl_buffer = 1.12 if interval == "1d" else 1.25
            is_breakout_candidate = (
                close_price > supertrend_val and 
                close_price <= supertrend_val * sl_buffer and
                rsi > 55 # Slightly loose RSI for candidate check
            )

            # Skip heavy simulation if it's not even a candidate
            if not is_breakout_candidate:
                success_count += 1
                continue

            # --- HEAVY SIMULATION (Only for candidates) ---
            bt_results = run_backtest(df, interval=interval)
            win_rate = bt_results["win_rate"]
            
            from datetime import datetime
            
            # SL and Target Logic (minimum 5% target floor)
            sl = round(supertrend_val, 2)
            risk = close_price - sl
            target = round(max(close_price + (risk * 2), close_price * 1.05), 2)

            # Historical Holding Logic
            trades = bt_results.get("trades", [])
            winning_trades = [t for t in trades if t.get("win")]
            avg_hold_days = 0
            if winning_trades:
                total_days = 0
                for t in winning_trades:
                    try:
                        edate = datetime.strptime(t["entry_date"], "%Y-%m-%d")
                        xdate = datetime.strptime(t["exit_date"], "%Y-%m-%d")
                        total_days += (xdate - edate).days
                    except: pass
                avg_hold_days = max(1, total_days // len(winning_trades))
            
            if avg_hold_days > 0:
                from datetime import timedelta
                # Project the calendar target date based on historical hold average
                est_exit_date = (datetime.now() + timedelta(days=avg_hold_days)).strftime('%d %b %Y')
                
                if interval == "1mo":
                    months = max(1, avg_hold_days // 30)
                    hold_duration = f"{months} Months (until ~{est_exit_date})"
                elif interval == "1wk":
                    weeks = max(1, avg_hold_days // 7)
                    hold_duration = f"{weeks} Weeks (until ~{est_exit_date})"
                else:
                    hold_duration = f"{avg_hold_days} Days (until ~{est_exit_date})"
            else:
                hold_duration = "N/A"
            
            if win_rate >= 50 and vol > vol_sma and adx > 25:
                conviction = "High"
                reason = "High historical win-rate backed by strong volume surge and active ADX trend."
            elif win_rate >= 40 and rsi > 60:
                conviction = "Medium"
                reason = "Good RSI momentum and moderate historical edge, though lacking perfect volume/trend."
            else:
                conviction = "Low"
                reason = "Historically underperforms (low win-rate)."

            sl_buffer = 1.12 if interval == "1d" else 1.25
            
            # Filter ONLY for High and Medium conviction, AND ensure it is an early catch (within safe Supertrend buffer)
            # SANITY CHECK: Ensure CMP is strictly > SL so inverted/broken suggestions are never returned
            if conviction in ["High", "Medium"] and close_price > supertrend_val and close_price <= supertrend_val * sl_buffer:
                breakout_stocks.append({
                    "ticker": ticker,
                    "close": round(close_price, 2),
                    "rsi": round(rsi, 2),
                    "volume": vol,
                    "vol_ratio": round(vol / vol_sma, 2) if vol_sma > 0 else 0,
                    "ema_50": round(float(last_bar['EMA_50']), 2),
                    "ema_200": round(float(last_bar['EMA_200']), 2),
                    "win_rate": win_rate,
                    "conviction": conviction,
                    "reason": reason,
                    "sl": sl,
                    "target": target,
                    "duration": hold_duration,
                    "supertrend": sl
                })
            
            # If we reached here without exception, parsing succeeded entirely
            success_count += 1
            
        except Exception as e:
            fail_count += 1
            pass
            
    # Sort by Conviction (High > Medium) and then by Win Rate (Descending)
    conviction_order = {"High": 0, "Medium": 1, "Low": 2}
    breakout_stocks.sort(key=lambda x: (conviction_order.get(x["conviction"], 3), -x["win_rate"]))

    return {
        "breakouts": breakout_stocks,
        "metrics": {
            "total_universe": total_universe,
            "successfully_scanned": success_count,
            "failed_tickers": fail_count
        }
    }

@app.post("/api/backtest")
async def do_backtest(req: BacktestRequest):
    ticker = req.ticker
    period = "2y"
    if req.interval == "1wk":
        period = "5y"
    elif req.interval == "1mo":
        period = "max"
    df = yf.download(ticker, period=period, interval=req.interval, progress=False)
    
    if df.empty:
        raise HTTPException(status_code=404, detail="No data found")
        
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.droplevel(1)
        
    df.dropna(how='all', inplace=True)
    
    try:
        df = calculate_indicators(df)
        if df.empty:
             raise HTTPException(status_code=400, detail="Not enough data for indicators")
        results = run_backtest(df, interval=req.interval)
        return {
            "ticker": ticker,
            "interval": req.interval,
            "results": results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# NO StaticFiles mounting or root route on Vercel as it handles static hosting natively
