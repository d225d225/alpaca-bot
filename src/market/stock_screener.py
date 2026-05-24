"""選股篩選器：根據策略條件過濾候選股票"""
import logging
from src.market.market_data import get_top_n_nasdaq, get_current_price
from src.market.pe_calculator import get_pe_bulk
from src.strategy.strategy_loader import Strategy

logger = logging.getLogger(__name__)


def screen_stocks(strategy: Strategy) -> list[str]:
    """
    根據策略規則篩選目標股票清單
    1. 取候選股（市值排名 or 自定義清單）
    2. 套用 filters（最低股價、最高 PE、最低成交量）
    3. 回傳最多 top_n 檔
    """
    # ① 取候選清單
    if strategy.universe == "CUSTOM" and strategy.custom_symbols:
        candidates = strategy.custom_symbols
    elif strategy.universe in ("NASDAQ_TOP_MC", "SP500"):
        candidates = get_top_n_nasdaq(n=20)  # 取多一些再過濾
    else:
        candidates = get_top_n_nasdaq(n=20)

    logger.info("候選股票 %d 檔：%s", len(candidates), candidates)

    # ② 套用 filters
    filters      = strategy.filters
    min_price    = float(filters.get("min_price", 0))
    max_pe       = float(filters.get("max_pe", 9999))
    min_volume   = int(filters.get("min_volume", 0))

    pe_data = get_pe_bulk(candidates) if max_pe < 9999 else {}

    passed = []
    for sym in candidates:
        price = get_current_price(sym)
        if price < min_price:
            logger.debug("%s 股價 %.2f < min_price %.2f，跳過", sym, price, min_price)
            continue
        if max_pe < 9999:
            pe = pe_data.get(sym)
            if pe is not None and pe > max_pe:
                logger.debug("%s PE %.1f > max_pe %.1f，跳過", sym, pe, max_pe)
                continue
        passed.append(sym)
        if len(passed) >= strategy.top_n:
            break

    logger.info("篩選後目標股票 %d 檔：%s", len(passed), passed)
    return passed


def get_watchlist_prices(watchlists: dict[str, list[str]]) -> dict[str, dict[str, float]]:
    """取得三大類別自選股的最新股價"""
    from src.market.market_data import get_prices_bulk
    result = {}
    for category, symbols in watchlists.items():
        prices = get_prices_bulk(symbols)
        result[category] = prices
    return result
