"""本益比（P/E Ratio）計算模組

本益比（P/E）= 股價 ÷ 每股盈餘（EPS）
當 EPS ≤ 0 時（虧損公司）回傳 None，代表不適用。
"""
import logging
import yfinance as yf

logger = logging.getLogger(__name__)


def get_pe_ratio(symbol: str) -> float | None:
    """
    取得個股本益比
    - 優先使用 trailingPE（過去 12 個月實際 EPS）
    - 若無則嘗試 forwardPE（預估 EPS）
    - 虧損公司（EPS<0）回傳 None
    回傳值：float（本益比）| None（不適用或取得失敗）
    """
    try:
        info = yf.Ticker(symbol).info
        pe = info.get("trailingPE") or info.get("forwardPE")
        if pe is None:
            # 手動計算：price / eps
            price = info.get("currentPrice") or info.get("regularMarketPrice") or 0
            eps   = info.get("trailingEps") or 0
            if eps and eps > 0 and price:
                pe = round(price / eps, 2)
            else:
                return None
        return round(float(pe), 2) if pe and pe > 0 else None
    except Exception as e:
        logger.warning("無法取得 %s 本益比：%s", symbol, e)
        return None


def get_pe_bulk(symbols: list[str]) -> dict[str, float | None]:
    """批次取得多檔股票本益比，回傳 {symbol: pe_or_None}"""
    return {sym: get_pe_ratio(sym) for sym in symbols}


def pe_label(pe: float | None) -> str:
    """本益比中文說明（供 Email / Dashboard 顯示）"""
    if pe is None:
        return "N/A（虧損或資料不足）"
    if pe < 15:
        return f"{pe:.1f}（低估）"
    if pe < 25:
        return f"{pe:.1f}（合理）"
    if pe < 50:
        return f"{pe:.1f}（偏高）"
    return f"{pe:.1f}（極高，注意風險）"
