from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from tradingview_ta import TA_Handler, Interval
import uvicorn

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

@app.get("/")
def root():
    return {"status": "TradingView API is running", "version": "1.0"}

@app.post("/get-data")
def get_trading_data(request: SymbolRequest):
    try:
        # Map interval string to Interval enum
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
        
        analysis = handler.get_analysis()
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
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/get-multi-timeframe")
def get_multi_timeframe(request: SymbolRequest):
    """Get data for multiple timeframes at once"""
    try:
        timeframes = ["1H", "15M", "5M"]
        result = {}
        
        for tf in timeframes:
            request.interval = tf
            data = get_trading_data(request)
            result[tf] = data["data"]
        
        return {"success": True, "data": result}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
