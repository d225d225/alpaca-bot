"""Alpaca API 客戶端封裝（alpaca-py SDK）"""
import logging
from functools import lru_cache
from alpaca.trading.client import TradingClient
from alpaca.trading.models import TradeAccount, Position, Order
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest, StockLatestQuoteRequest
from alpaca.data.timeframe import TimeFrame
from src.core.config import config

logger = logging.getLogger(__name__)


def build_trading_client(api_key: str, api_secret: str, paper: bool = True) -> TradingClient:
    """建立 TradingClient，支援 paper / live 切換"""
    return TradingClient(api_key=api_key, secret_key=api_secret, paper=paper)


def build_data_client(api_key: str, api_secret: str) -> StockHistoricalDataClient:
    """建立歷史資料 Client"""
    return StockHistoricalDataClient(api_key=api_key, secret_key=api_secret)


class AlpacaClient:
    """單一帳戶的 Alpaca 操作封裝"""

    def __init__(self, api_key: str, api_secret: str, paper: bool = True):
        self._key = api_key
        self._secret = api_secret
        self._paper = paper
        self.trading = build_trading_client(api_key, api_secret, paper)
        self.data    = build_data_client(api_key, api_secret)
        logger.info("AlpacaClient 初始化完成 (paper=%s)", paper)

    # ── 帳戶資訊 ────────────────────────────────────────────────
    def get_account(self) -> TradeAccount:
        return self.trading.get_account()

    def get_cash(self) -> float:
        return float(self.get_account().cash)

    def get_equity(self) -> float:
        return float(self.get_account().equity)

    def get_portfolio_value(self) -> float:
        return float(self.get_account().portfolio_value)

    # ── 持倉 ────────────────────────────────────────────────────
    def get_positions(self) -> list[Position]:
        return self.trading.get_all_positions()

    def get_position(self, symbol: str) -> Position | None:
        try:
            return self.trading.get_open_position(symbol)
        except Exception:
            return None

    # ── 訂單 ────────────────────────────────────────────────────
    def get_orders(self, status: str = "open") -> list[Order]:
        from alpaca.trading.requests import GetOrdersRequest
        from alpaca.trading.enums import QueryOrderStatus
        req = GetOrdersRequest(status=QueryOrderStatus(status))
        return self.trading.get_orders(filter=req)

    def cancel_all_orders(self) -> None:
        self.trading.cancel_orders()
        logger.info("已取消所有未成交訂單")

    # ── 市場狀態 ────────────────────────────────────────────────
    def is_market_open(self) -> bool:
        clock = self.trading.get_clock()
        return clock.is_open

    def get_next_open(self):
        return self.trading.get_clock().next_open

    # ── 行情 ────────────────────────────────────────────────────
    def get_latest_quotes(self, symbols: list[str]) -> dict:
        req = StockLatestQuoteRequest(symbol_or_symbols=symbols)
        quotes = self.data.get_stock_latest_quote(req)
        return {sym: float(q.ask_price or q.bid_price or 0) for sym, q in quotes.items()}

    def get_latest_price(self, symbol: str) -> float:
        prices = self.get_latest_quotes([symbol])
        return prices.get(symbol, 0.0)
