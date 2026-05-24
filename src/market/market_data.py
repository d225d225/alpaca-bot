"""市場資料模組：股價、報酬率、市值排名（yfinance）"""
import logging
from datetime import datetime, timedelta
from functools import lru_cache

import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)

# NASDAQ 市值前 20（定期更新此列表即可，無需改程式碼）
NASDAQ_TOP20_SYMBOLS = [
    "MSFT", "AAPL", "NVDA", "AMZN", "GOOGL",
    "META", "TSLA", "AVGO", "COST", "NFLX",
    "AMD",  "ADBE", "QCOM", "INTC", "CMCSA",
    "PEP",  "CSCO", "TMUS", "INTU", "AMAT",
]


def get_top_n_nasdaq(n: int = 10) -> list[str]:
    """回傳 NASDAQ 市值前 n 檔代碼（依 yfinance marketCap 排序）"""
    data = []
    for sym in NASDAQ_TOP20_SYMBOLS:
        try:
            info = yf.Ticker(sym).fast_info
            mc = getattr(info, "market_cap", None) or 0
            data.append((sym, mc))
        except Exception as e:
            logger.warning("無法取得 %s 市值：%s", sym, e)
    data.sort(key=lambda x: x[1], reverse=True)
    top = [s for s, _ in data[:n]]
    logger.info("NASDAQ Top %d: %s", n, top)
    return top


def get_current_price(symbol: str) -> float:
    """取得個股最新收盤價（或盤中價）"""
    try:
        t = yf.Ticker(symbol)
        price = t.fast_info.last_price
        return float(price) if price else 0.0
    except Exception as e:
        logger.warning("無法取得 %s 價格：%s", symbol, e)
        return 0.0


def get_prices_bulk(symbols: list[str]) -> dict[str, float]:
    """批次取得多檔股價，回傳 {symbol: price}"""
    try:
        tickers = yf.download(symbols, period="1d", progress=False, auto_adjust=True)
        close = tickers["Close"]
        if isinstance(close, pd.Series):
            close = close.to_frame(name=symbols[0])
        return {sym: float(close[sym].dropna().iloc[-1]) for sym in symbols if sym in close.columns}
    except Exception as e:
        logger.error("批次取價失敗：%s", e)
        return {sym: get_current_price(sym) for sym in symbols}


def get_return_pct(symbol: str, period: str = "1d") -> float:
    """
    計算個股指定期間報酬率（%）
    period: "1d" | "5d" | "1mo" | "3mo" | "6mo" | "1y"
    """
    period_map = {"1d": "2d", "1w": "5d", "1m": "1mo", "5d": "5d", "1mo": "1mo"}
    yf_period = period_map.get(period, period)
    try:
        hist = yf.Ticker(symbol).history(period=yf_period, auto_adjust=True)
        if len(hist) < 2:
            return 0.0
        start = float(hist["Close"].iloc[0])
        end   = float(hist["Close"].iloc[-1])
        return round((end - start) / start * 100, 2) if start else 0.0
    except Exception as e:
        logger.warning("報酬率計算失敗 %s [%s]: %s", symbol, period, e)
        return 0.0


def get_returns_bulk(symbols: list[str]) -> dict[str, dict[str, float]]:
    """批次計算多檔股票的 1D / 1W / 1M 報酬率"""
    result = {}
    for sym in symbols:
        result[sym] = {
            "1d": get_return_pct(sym, "1d"),
            "1w": get_return_pct(sym, "1w"),
            "1m": get_return_pct(sym, "1m"),
        }
    return result


def get_benchmark_history(symbol: str = "^IXIC", days: int = 365) -> pd.Series:
    """取得指數歷史（預設 NASDAQ Composite）"""
    end   = datetime.now()
    start = end - timedelta(days=days)
    hist  = yf.Ticker(symbol).history(start=start, end=end, auto_adjust=True)
    return hist["Close"].rename(symbol)


def get_sp500_history(days: int = 365) -> pd.Series:
    return get_benchmark_history("^GSPC", days)


def get_nasdaq_history(days: int = 365) -> pd.Series:
    return get_benchmark_history("^IXIC", days)
