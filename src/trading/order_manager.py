"""訂單管理：市價買入、市價賣出、即時通知"""
import logging
from datetime import datetime

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce

from src.core.alpaca_client import AlpacaClient

logger = logging.getLogger(__name__)


def place_buy_order(
    client: AlpacaClient,
    symbol: str,
    qty: int,
    notify_fn=None,
) -> dict | None:
    """
    以市價買入整數股
    qty 必須 >= 1
    回傳訂單資訊 dict，失敗回傳 None
    """
    if qty < 1:
        logger.warning("買入 %s 數量 %d < 1，略過", symbol, qty)
        return None
    try:
        req = MarketOrderRequest(
            symbol=symbol,
            qty=qty,
            side=OrderSide.BUY,
            time_in_force=TimeInForce.DAY,
        )
        order = client.trading.submit_order(req)
        info = {
            "action":    "BUY",
            "symbol":    symbol,
            "qty":       qty,
            "order_id":  str(order.id),
            "status":    str(order.status),
            "timestamp": datetime.utcnow().isoformat(),
        }
        logger.info("✅ 買入 %s x%d  訂單 %s", symbol, qty, order.id)
        if notify_fn:
            notify_fn(info)
        return info
    except Exception as e:
        logger.error("買入 %s 失敗：%s", symbol, e)
        return None


def place_sell_order(
    client: AlpacaClient,
    symbol: str,
    qty: int,
    notify_fn=None,
) -> dict | None:
    """以市價賣出整數股"""
    if qty < 1:
        logger.warning("賣出 %s 數量 %d < 1，略過", symbol, qty)
        return None
    try:
        req = MarketOrderRequest(
            symbol=symbol,
            qty=qty,
            side=OrderSide.SELL,
            time_in_force=TimeInForce.DAY,
        )
        order = client.trading.submit_order(req)
        info = {
            "action":    "SELL",
            "symbol":    symbol,
            "qty":       qty,
            "order_id":  str(order.id),
            "status":    str(order.status),
            "timestamp": datetime.utcnow().isoformat(),
        }
        logger.info("🔴 賣出 %s x%d  訂單 %s", symbol, qty, order.id)
        if notify_fn:
            notify_fn(info)
        return info
    except Exception as e:
        logger.error("賣出 %s 失敗：%s", symbol, e)
        return None


def close_position(client: AlpacaClient, symbol: str, notify_fn=None) -> dict | None:
    """清倉指定股票"""
    pos = client.get_position(symbol)
    if not pos:
        logger.info("%s 無持倉，略過清倉", symbol)
        return None
    qty = int(abs(float(pos.qty)))
    return place_sell_order(client, symbol, qty, notify_fn)
