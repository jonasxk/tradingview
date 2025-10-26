from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from tradingview_ta import TA_Handler, Interval
import uvicorn
import time
import logging
from typing import Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="TradingView Data API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class SymbolRequest(BaseModel):
    symbol: str
    exchange: str = "OANDA"
    screener: str = "forex"
    interval: str = "1H"
    lookback_days: Optional[int] = 7

last_request_time = 0
MIN_REQUEST_INTERVAL = 0.5

def rate_limit():
    global last_request_time
    current_time = time.time()
    time_since_last = current_time - last_request_time
    
    if time_since_last < MIN_REQUEST_INTERVAL:
        sleep_time = MIN_REQUEST_INTERVAL - time_since_last
        time.sleep(sleep_time)
    
    last_request_time = time.time()

def get_analysis_with_retry(handler, max_retries=3):
    for attempt in range(max_retries):
        try:
            rate_limit()
            analysis = handler.get_analysis()
            return analysis
        except Exception as e:
            logger.warning(f"Attempt {attempt + 1} failed: {str(e)}")
            if attempt < max_retries - 1:
                wait_time = (attempt + 1) * 2
                time.sleep(wait_time)
            else:
                raise e

@app.get("/")
def root():
    return {"status": "TradingView API is running", "version": "2.1"}

@app.get("/health")
def health():
    return {"status": "healthy", "endpoints": ["/get-data", "/get-multi-timeframe", "/get-historical-with-levels"]}

@app.post("/get-data")
def get_trading_data(request: SymbolRequest):
    """Get current data with TradingView indicators"""
    try:
        interval_map = {
            "1M": Interval.INTERVAL_1_MINUTE,
            "5M": Interval.INTERVAL_5_MINUTES,
            "15M": Interval.INTERVAL_15_MINUTES,
            "1H": Interval.INTERVAL_1_HOUR,
            "4H": Interval.INTERVAL_4_HOURS,
            "1D": Interval.INTERVAL_1_DAY
        }
        
        interval_enum = interval_map.get(request.interval, Interval.INTERVAL_1_HOUR)
        
        handler = TA_Handler(
            symbol=request.symbol,
            exchange=request.exchange,
            screener=request.screener,
            interval=interval_enum
        )
        
        analysis = get_analysis_with_retry(handler)
        indicators = analysis.indicators
        
        output = {
            "symbol": request.symbol,
            "exchange": request.exchange,
            "screener": request.screener,
            "timeframe": request.interval,
            "timestamp": indicators.get("time", ""),
            "price": {
                "open": indicators.get("open", 0),
                "high": indicators.get("high", 0),
                "low": indicators.get("low", 0),
                "close": indicators.get("close", 0),
                "volume": indicators.get("volume", 0)
            },
            "trend": {
                "recommendation": analysis.summary.get("RECOMMENDATION", "NEUTRAL"),
                "buy_signals": analysis.summary.get("BUY", 0),
                "sell_signals": analysis.summary.get("SELL", 0),
                "neutral_signals": analysis.summary.get("NEUTRAL", 0)
            },
            "indicators": {
                "rsi": indicators.get("RSI", 0),
                "macd": indicators.get("MACD.macd", 0),
                "macd_signal": indicators.get("MACD.signal", 0),
                "ema20": indicators.get("EMA20", 0),
                "ema50": indicators.get("EMA50", 0),
                "ema200": indicators.get("EMA200", 0),
                "sma20": indicators.get("SMA20", 0),
                "sma50": indicators.get("SMA50", 0),
                "sma200": indicators.get("SMA200", 0),
                "atr": indicators.get("ATR", 0),
                "stoch_k": indicators.get("Stoch.K", 0),
                "stoch_d": indicators.get("Stoch.D", 0),
                "bb_upper": indicators.get("BB.upper", 0),
                "bb_lower": indicators.get("BB.lower", 0),
                "adx": indicators.get("ADX", 0)
            },
            "oscillators_summary": analysis.oscillators.get("RECOMMENDATION", "NEUTRAL"),
            "ma_summary": analysis.moving_averages.get("RECOMMENDATION", "NEUTRAL")
        }
        
        return {"success": True, "data": output}
        
    except Exception as e:
        logger.error(f"Error processing {request.symbol}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/get-multi-timeframe")
def get_multi_timeframe(request: SymbolRequest):
    """Get data for multiple timeframes at once"""
    try:
        timeframes = ["1H", "15M", "5M"]
        result = {}
        
        for i, tf in enumerate(timeframes):
            request.interval = tf
            data = get_trading_data(request)
            result[tf] = data["data"]
            
            if i < len(timeframes) - 1:
                time.sleep(1)
        
        return {"success": True, "data": result}
        
    except Exception as e:
        logger.error(f"Error in multi-timeframe: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/get-historical-with-levels")
def get_historical_with_levels(request: SymbolRequest):
    """Get historical candles with price action levels using yfinance"""
    try:
        # Try to import yfinance
        try:
            import yfinance as yf
            import pandas as pd
        except ImportError as ie:
            logger.error(f"yfinance not installed: {str(ie)}")
            raise HTTPException(
                status_code=501, 
                detail="Historical data endpoint requires yfinance package. Use /get-data instead."
            )
        
        # Symbol mapping for Yahoo Finance
        symbol_map = {
            "EURUSD": "EURUSD=X",
            "GBPUSD": "GBPUSD=X",
            "USDJPY": "USDJPY=X",
            "AUDUSD": "AUDUSD=X",
            "USDCAD": "USDCAD=X",
            "USDCHF": "USDCHF=X",
            "NZDUSD": "NZDUSD=X",
            "GBPJPY": "GBPJPY=X",
            "EURJPY": "EURJPY=X",
            "XAUUSD": "GC=F",
            "XAGUSD": "SI=F",
            "BTCUSD": "BTC-USD",
            "ETHUSD": "ETH-USD",
            "BTCUSDT": "BTC-USD",
            "ETHUSDT": "ETH-USD"
        }
        
        yahoo_symbol = symbol_map.get(request.symbol, f"{request.symbol}=X")
        
        # Interval mapping
        interval_map = {
            "1M": "1m",
            "5M": "5m", 
            "15M": "15m",
            "1H": "1h",
            "4H": "4h",
            "1D": "1d"
        }
        
        yf_interval = interval_map.get(request.interval, "1h")
        lookback = request.lookback_days
        
        # Fetch data from Yahoo Finance
        logger.info(f"Fetching {yahoo_symbol} with interval {yf_interval} for {lookback} days")
        ticker = yf.Ticker(yahoo_symbol)
        df = ticker.history(period=f"{lookback}d", interval=yf_interval)
        
        if df.empty:
            raise HTTPException(
                status_code=404, 
                detail=f"No data found for {yahoo_symbol}. Symbol may not be available on Yahoo Finance."
            )
        
        logger.info(f"Retrieved {len(df)} candles for {yahoo_symbol}")
        
        # Calculate price action levels
        period_high = float(df['High'].max())
        period_low = float(df['Low'].min())
        period_range = period_high - period_low
        current_price = float(df['Close'].iloc[-1])
        
        # Recent 3-day levels
        recent_df = df.tail(72) if len(df) >= 72 else df
        recent_high = float(recent_df['High'].max())
        recent_low = float(recent_df['Low'].min())
        avg_range = float(df['High'].subtract(df['Low']).mean())
        
        # Convert all candles to list
        candles = []
        for idx, row in df.iterrows():
            candles.append({
                "time": idx.isoformat(),
                "open": float(row['Open']),
                "high": float(row['High']),
                "low": float(row['Low']),
                "close": float(row['Close']),
                "volume": float(row['Volume'])
            })
        
        # Get TradingView indicators for current candle
        interval_tv_map = {
            "1M": Interval.INTERVAL_1_MINUTE,
            "5M": Interval.INTERVAL_5_MINUTES,
            "15M": Interval.INTERVAL_15_MINUTES,
            "1H": Interval.INTERVAL_1_HOUR,
            "4H": Interval.INTERVAL_4_HOURS,
            "1D": Interval.INTERVAL_1_DAY
        }
        
        handler = TA_Handler(
            symbol=request.symbol,
            exchange=request.exchange,
            screener=request.screener,
            interval=interval_tv_map.get(request.interval, Interval.INTERVAL_1_HOUR)
        )
        
        analysis = get_analysis_with_retry(handler)
        indicators = analysis.indicators
        
        output = {
            "symbol": request.symbol,
            "exchange": request.exchange,
            "screener": request.screener,
            "timeframe": request.interval,
            "lookback_days": lookback,
            "total_candles": len(df),
            "price_action_levels": {
                "period_high": period_high,
                "period_low": period_low,
                "period_range": period_range,
                "recent_high_3d": recent_high,
                "recent_low_3d": recent_low,
                "avg_candle_range": avg_range,
                "current_position_in_range": ((current_price - period_low) / period_range * 100) if period_range > 0 else 50
            },
            "candles": candles,
            "current_indicators": {
                "rsi": indicators.get("RSI", 0),
                "atr": indicators.get("ATR", 0),
                "ema20": indicators.get("EMA20", 0),
                "ema50": indicators.get("EMA50", 0),
                "ema200": indicators.get("EMA200", 0),
                "adx": indicators.get("ADX", 0),
                "macd": indicators.get("MACD.macd", 0),
                "macd_signal": indicators.get("MACD.signal", 0),
                "stoch_k": indicators.get("Stoch.K", 0),
                "stoch_d": indicators.get("Stoch.D", 0),
                "bb_upper": indicators.get("BB.upper", 0),
                "bb_lower": indicators.get("BB.lower", 0)
            },
            "recommendation": analysis.summary.get("RECOMMENDATION", "NEUTRAL")
        }
        
        return {"success": True, "data": output}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Historical data error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error fetching historical data: {str(e)}")

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 8000))
    logger.info(f"Starting server on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
