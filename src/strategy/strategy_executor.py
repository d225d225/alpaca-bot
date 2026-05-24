"""策略執行器：整合選股 → 停損停利 → 再平衡"""
import logging
from datetime import date

from src.core.alpaca_client import AlpacaClient
from src.core.account_manager import AccountConfig
from src.strategy.strategy_loader import Strategy
from src.market.stock_screener import screen_stocks
from src.trading.position_manager import get_positions_info, check_stop_loss, check_take_profit
from src.trading.order_manager import close_position
from src.trading.rebalancer import rebalance

logger = logging.getLogger(__name__)


def run_strategy(
    client: AlpacaClient,
    account: AccountConfig,
    strategy: Strategy,
    notify_fn=None,
) -> dict:
    """
    單一帳戶的完整策略執行流程：
    1. 選股（篩選目標清單）
    2. 停損 / 停利檢查
    3. 再平衡
    回傳執行摘要 dict
    """
    logger.info("═══ 開始執行策略 [%s] 帳戶 [%s] ═══", strategy.strategy_id, account.account_id)
    summary = {
        "account_id":  account.account_id,
        "strategy_id": strategy.strategy_id,
        "date":        date.today().isoformat(),
        "target_symbols": [],
        "stop_actions": [],
        "rebalance_trades": [],
        "errors": [],
    }

    # ① 選股
    try:
        target = screen_stocks(strategy)
        summary["target_symbols"] = target
        logger.info("目標股票：%s", target)
    except Exception as e:
        summary["errors"].append(f"選股失敗：{e}")
        logger.error("選股失敗：%s", e)
        return summary

    # ② 停損 / 停利
    try:
        positions = get_positions_info(client)
        for pos in positions:
            if check_stop_loss(pos, strategy.stop_loss_pct):
                logger.warning("⚠️  停損觸發：%s (%.2f%%)", pos.symbol, pos.unrealized_pl_pct)
                result = close_position(client, pos.symbol, notify_fn)
                if result:
                    result["reason"] = "stop_loss"
                    summary["stop_actions"].append(result)
            elif check_take_profit(pos, strategy.take_profit_pct):
                logger.info("🎯 停利觸發：%s (%.2f%%)", pos.symbol, pos.unrealized_pl_pct)
                result = close_position(client, pos.symbol, notify_fn)
                if result:
                    result["reason"] = "take_profit"
                    summary["stop_actions"].append(result)
    except Exception as e:
        summary["errors"].append(f"停損停利檢查失敗：{e}")
        logger.error("停損停利失敗：%s", e)

    # ③ 再平衡
    try:
        trades = rebalance(client, strategy, target, notify_fn)
        summary["rebalance_trades"] = trades
    except Exception as e:
        summary["errors"].append(f"再平衡失敗：{e}")
        logger.error("再平衡失敗：%s", e)

    logger.info("═══ 策略執行完成 ═══")
    return summary
