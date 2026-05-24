"""
再平衡引擎
規則：
  - 前 N 檔各佔 10%（alloc_pct）的投資組合
  - 只買整數股
  - 新資金進來時觸發一次再平衡
  - 每月初觸發一次再平衡
"""
import logging
import math
from dataclasses import dataclass

from src.core.alpaca_client import AlpacaClient
from src.trading.order_manager import place_buy_order, place_sell_order
from src.trading.position_manager import get_positions_info
from src.market.market_data import get_prices_bulk
from src.strategy.strategy_loader import Strategy

logger = logging.getLogger(__name__)


@dataclass
class RebalancePlan:
    symbol:      str
    action:      str        # "BUY" | "SELL" | "HOLD"
    current_qty: int
    target_qty:  int
    diff_qty:    int
    price:       float
    reason:      str = ""


def compute_rebalance_plan(
    client: AlpacaClient,
    strategy: Strategy,
    target_symbols: list[str],
) -> list[RebalancePlan]:
    """
    計算再平衡計畫
    target_symbols: 已篩選好的目標股票清單（最多 top_n 檔）
    """
    portfolio_value = client.get_portfolio_value()
    alloc_amt       = portfolio_value * strategy.alloc_fraction()

    prices = get_prices_bulk(target_symbols)
    positions_map = {p.symbol: p for p in get_positions_info(client)}

    plans: list[RebalancePlan] = []

    # ① 計算新目標持倉
    for sym in target_symbols:
        price = prices.get(sym, 0)
        if price <= 0:
            logger.warning("%s 股價為 0，跳過", sym)
            continue

        # 目標股數（只買整數股）
        target_qty = int(math.floor(alloc_amt / price)) if strategy.whole_shares else alloc_amt / price
        curr_pos   = positions_map.get(sym)
        current_qty = curr_pos.qty if curr_pos else 0
        diff = target_qty - current_qty

        if diff > 0:
            action = "BUY"
        elif diff < 0:
            action = "SELL"
        else:
            action = "HOLD"

        plans.append(RebalancePlan(
            symbol=sym, action=action,
            current_qty=current_qty, target_qty=target_qty,
            diff_qty=abs(diff), price=price,
            reason=f"配置 {strategy.alloc_pct}% = ${alloc_amt:.0f}，每股 ${price:.2f}",
        ))

    # ② 清倉不在目標清單的舊持倉
    target_set = set(target_symbols)
    for sym, pos in positions_map.items():
        if sym not in target_set and pos.qty > 0:
            plans.append(RebalancePlan(
                symbol=sym, action="SELL",
                current_qty=pos.qty, target_qty=0,
                diff_qty=pos.qty, price=pos.current_price,
                reason="不在新目標清單，全數清倉",
            ))

    return plans


def execute_rebalance(
    client: AlpacaClient,
    plans: list[RebalancePlan],
    notify_fn=None,
) -> list[dict]:
    """執行再平衡：先賣後買（避免資金不足）"""
    executed = []

    # 先賣
    for plan in plans:
        if plan.action == "SELL" and plan.diff_qty > 0:
            result = place_sell_order(client, plan.symbol, plan.diff_qty, notify_fn)
            if result:
                executed.append(result)

    # 再買
    for plan in plans:
        if plan.action == "BUY" and plan.diff_qty > 0:
            result = place_buy_order(client, plan.symbol, plan.diff_qty, notify_fn)
            if result:
                executed.append(result)

    logger.info("再平衡完成，共執行 %d 筆交易", len(executed))
    return executed


def rebalance(
    client: AlpacaClient,
    strategy: Strategy,
    target_symbols: list[str],
    notify_fn=None,
) -> list[dict]:
    """完整再平衡流程：計畫 → 執行"""
    if not client.is_market_open():
        logger.warning("市場休市，跳過再平衡")
        return []
    plans   = compute_rebalance_plan(client, strategy, target_symbols)
    results = execute_rebalance(client, plans, notify_fn)
    return results
