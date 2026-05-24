"""持倉管理：計算損益、停損停利檢查、持倉報告"""
import logging
from dataclasses import dataclass, field

from src.core.alpaca_client import AlpacaClient

logger = logging.getLogger(__name__)


@dataclass
class PositionInfo:
    symbol:       str
    qty:          int
    avg_cost:     float
    current_price: float
    market_value: float
    unrealized_pl: float
    unrealized_pl_pct: float
    side:         str = "long"

    @property
    def is_profitable(self) -> bool:
        return self.unrealized_pl > 0


def get_positions_info(client: AlpacaClient) -> list[PositionInfo]:
    """從 Alpaca 取得所有持倉，轉為 PositionInfo 列表"""
    positions = client.get_positions()
    result = []
    for p in positions:
        avg_cost = float(p.avg_entry_price or 0)
        curr     = float(p.current_price or 0)
        qty      = int(float(p.qty or 0))
        mv       = float(p.market_value or 0)
        upl      = float(p.unrealized_pl or 0)
        upl_pct  = ((curr - avg_cost) / avg_cost * 100) if avg_cost else 0
        result.append(PositionInfo(
            symbol=p.symbol,
            qty=qty,
            avg_cost=avg_cost,
            current_price=curr,
            market_value=mv,
            unrealized_pl=upl,
            unrealized_pl_pct=round(upl_pct, 2),
        ))
    return result


def check_stop_loss(pos: PositionInfo, stop_loss_pct: float) -> bool:
    """
    停損判斷：當跌幅超過 stop_loss_pct 時觸發
    stop_loss_pct 為負數，例如 -8 代表跌 8% 停損
    """
    return pos.unrealized_pl_pct <= stop_loss_pct


def check_take_profit(pos: PositionInfo, take_profit_pct: float) -> bool:
    """停利判斷：當漲幅超過 take_profit_pct 時觸發"""
    return pos.unrealized_pl_pct >= take_profit_pct


def positions_to_dict(positions: list[PositionInfo]) -> list[dict]:
    """轉為可序列化的 dict 列表（供報告使用）"""
    return [
        {
            "symbol":           p.symbol,
            "qty":              p.qty,
            "avg_cost":         p.avg_cost,
            "current_price":    p.current_price,
            "market_value":     p.market_value,
            "unrealized_pl":    p.unrealized_pl,
            "unrealized_pl_pct": p.unrealized_pl_pct,
        }
        for p in positions
    ]
