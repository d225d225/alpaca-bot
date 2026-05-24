"""
每日報告 Model（純 JSON，View 分離）
報告內容：帳戶快照、NAV、回撤、持倉、交易紀錄、市場績效
"""
import json
import logging
from dataclasses import dataclass, asdict, field
from datetime import date, datetime
from typing import Optional

import numpy as np
import pandas as pd

from src.core.alpaca_client import AlpacaClient
from src.trading.position_manager import get_positions_info, positions_to_dict
from src.market.market_data import get_returns_bulk, get_nasdaq_history, get_sp500_history
from src.market.pe_calculator import get_pe_bulk

logger = logging.getLogger(__name__)


@dataclass
class DailyReport:
    # 基本資訊
    account_id:   str
    strategy_id:  str
    report_date:  str                  # ISO 格式 "2026-05-24"
    generated_at: str                  # ISO datetime

    # 帳戶快照
    cash:            float = 0.0
    equity:          float = 0.0
    portfolio_value: float = 0.0
    long_market_value: float = 0.0

    # NAV & 損益
    nav:             float = 0.0       # 當日 NAV（等同 portfolio_value）
    nav_change_pct:  float = 0.0       # 相對前一交易日變化
    total_pl_pct:    float = 0.0       # 相對初始資本累積損益
    daily_pl:        float = 0.0       # 當日損益金額

    # 回撤
    max_drawdown_pct: float = 0.0      # 歷史最大回撤

    # 持倉清單
    positions: list = field(default_factory=list)

    # 今日交易
    trades: list = field(default_factory=list)

    # Top 10 股票
    top10_symbols: list  = field(default_factory=list)
    top10_returns: dict  = field(default_factory=dict)   # {sym: {1d,1w,1m}}
    top10_pe:      dict  = field(default_factory=dict)   # {sym: pe}
    top10_prices:  dict  = field(default_factory=dict)   # {sym: price}

    # 自選股三大類別
    watchlist_prices: dict = field(default_factory=dict) # {category: {sym: price}}

    # 指數比對
    nasdaq_1d_return: float = 0.0
    sp500_1d_return:  float = 0.0

    # 標記
    disclaimer: str = "以上資訊僅供參考，不構成投資建議。請自行評估投資風險。"

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, indent=indent)

    @classmethod
    def from_json(cls, raw: str) -> "DailyReport":
        return cls(**json.loads(raw))


def build_report(
    client: AlpacaClient,
    account_id: str,
    strategy_id: str,
    target_symbols: list[str],
    trades: list[dict],
    watchlists: dict[str, list[str]],
    prev_nav: float | None = None,
    initial_capital: float | None = None,
    nav_history: list[float] | None = None,
) -> DailyReport:
    """
    組建每日報告 Model
    所有 I/O 集中在此，Report View 不會直接呼叫 Alpaca / yfinance
    """
    account  = client.get_account()
    cash     = float(account.cash)
    equity   = float(account.equity)
    pv       = float(account.portfolio_value)
    long_mv  = float(account.long_market_value)

    positions = positions_to_dict(get_positions_info(client))

    # NAV 變化
    nav_change = ((pv - prev_nav) / prev_nav * 100) if prev_nav else 0.0
    total_pl   = ((pv - initial_capital) / initial_capital * 100) if initial_capital else 0.0
    daily_pl   = (pv - prev_nav) if prev_nav else 0.0

    # 最大回撤（依 NAV 歷史計算）
    max_dd = 0.0
    if nav_history and len(nav_history) > 1:
        series    = pd.Series(nav_history + [pv])
        roll_max  = series.cummax()
        drawdowns = (series - roll_max) / roll_max * 100
        max_dd    = round(float(drawdowns.min()), 2)

    # Top 10 市場資料
    top10_returns = get_returns_bulk(target_symbols)
    top10_pe      = get_pe_bulk(target_symbols)
    from src.market.market_data import get_prices_bulk
    top10_prices  = get_prices_bulk(target_symbols)

    # 自選股股價
    from src.market.stock_screener import get_watchlist_prices
    wl_prices = get_watchlist_prices(watchlists)

    # 指數當日漲跌
    nasdaq_ret = _index_1d_return("^IXIC")
    sp500_ret  = _index_1d_return("^GSPC")

    return DailyReport(
        account_id=account_id,
        strategy_id=strategy_id,
        report_date=date.today().isoformat(),
        generated_at=datetime.utcnow().isoformat() + "Z",
        cash=cash, equity=equity,
        portfolio_value=pv, long_market_value=long_mv,
        nav=pv,
        nav_change_pct=round(nav_change, 2),
        total_pl_pct=round(total_pl, 2),
        daily_pl=round(daily_pl, 2),
        max_drawdown_pct=max_dd,
        positions=positions,
        trades=trades,
        top10_symbols=target_symbols,
        top10_returns=top10_returns,
        top10_pe={k: v for k, v in top10_pe.items()},
        top10_prices=top10_prices,
        watchlist_prices=wl_prices,
        nasdaq_1d_return=nasdaq_ret,
        sp500_1d_return=sp500_ret,
    )


def _index_1d_return(symbol: str) -> float:
    try:
        import yfinance as yf
        hist = yf.Ticker(symbol).history(period="2d", auto_adjust=True)
        if len(hist) < 2:
            return 0.0
        s = float(hist["Close"].iloc[-2])
        e = float(hist["Close"].iloc[-1])
        return round((e - s) / s * 100, 2) if s else 0.0
    except Exception:
        return 0.0
