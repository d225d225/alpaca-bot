"""Phase 4 延伸測試：再平衡進階（12 cases）"""
import pytest
from unittest.mock import MagicMock, patch


def _make_strategy(alloc_pct=10, top_n=3, stop_loss=-8, take_profit=25):
    s = MagicMock()
    s.alloc_fraction.return_value = alloc_pct / 100
    s.alloc_pct = alloc_pct
    s.top_n = top_n
    s.stop_loss_pct = stop_loss
    s.take_profit_pct = take_profit
    s.whole_shares = True
    s.rebalance = {"on_new_funds": True, "monthly": True}
    s.should_rebalance_on_new_funds.return_value = True
    s.should_rebalance_monthly.return_value = True
    return s


# ── TC-19: 再平衡計畫進階 ────────────────────────────────────────
class TestRebalancePlan:
    @patch("src.trading.rebalancer.get_positions_info", return_value=[])
    @patch("src.trading.rebalancer.get_prices_bulk")
    def test_plan_hold_when_already_correct(self, mock_prices, mock_positions):
        from src.trading.position_manager import PositionInfo
        from src.trading.rebalancer import compute_rebalance_plan
        import math
        price = 100.0
        portfolio = 10_000.0
        alloc = portfolio * 0.10
        target_qty = math.floor(alloc / price)  # 10
        pos = PositionInfo("AAPL", target_qty, price, price, target_qty * price, 0.0, 0.0)
        mock_positions.return_value = [pos]
        mock_prices.return_value = {"AAPL": price}
        client = MagicMock()
        client.get_portfolio_value.return_value = portfolio
        plans = compute_rebalance_plan(client, _make_strategy(top_n=1), ["AAPL"])
        hold = [p for p in plans if p.symbol == "AAPL" and p.action == "HOLD"]
        assert len(hold) == 1

    @patch("src.trading.rebalancer.get_positions_info", return_value=[])
    @patch("src.trading.rebalancer.get_prices_bulk")
    def test_qty_is_integer(self, mock_prices, mock_positions):
        from src.trading.rebalancer import compute_rebalance_plan
        mock_prices.return_value = {"AAPL": 123.45}
        mock_positions.return_value = []
        client = MagicMock()
        client.get_portfolio_value.return_value = 50_000.0
        plans = compute_rebalance_plan(client, _make_strategy(top_n=1), ["AAPL"])
        for p in plans:
            assert isinstance(p.target_qty, int)

    @patch("src.trading.rebalancer.get_positions_info", return_value=[])
    @patch("src.trading.rebalancer.get_prices_bulk")
    def test_plan_sell_when_price_zero_skipped(self, mock_prices, mock_positions):
        from src.trading.rebalancer import compute_rebalance_plan
        mock_prices.return_value = {"BAD": 0.0}
        mock_positions.return_value = []
        client = MagicMock()
        client.get_portfolio_value.return_value = 10_000.0
        plans = compute_rebalance_plan(client, _make_strategy(top_n=1), ["BAD"])
        assert all(p.symbol != "BAD" for p in plans)


# ── TC-20: 再平衡執行順序（先賣後買）───────────────────────────
class TestRebalanceExecution:
    @patch("src.trading.rebalancer.place_sell_order")
    @patch("src.trading.rebalancer.place_buy_order")
    def test_sell_before_buy(self, mock_buy, mock_sell):
        mock_sell.return_value = {"action": "SELL", "symbol": "OLD", "qty": 5, "order_id": "s1", "status": "ok", "timestamp": "x"}
        mock_buy.return_value  = {"action": "BUY",  "symbol": "NEW", "qty": 3, "order_id": "b1", "status": "ok", "timestamp": "x"}
        from src.trading.rebalancer import RebalancePlan, execute_rebalance
        plans = [
            RebalancePlan("OLD", "SELL", 5, 0, 5, 100.0),
            RebalancePlan("NEW", "BUY",  0, 3, 3, 150.0),
        ]
        client = MagicMock()
        call_order = []
        mock_sell.side_effect = lambda *a, **kw: (call_order.append("SELL"), {"action":"SELL","symbol":"OLD","qty":5,"order_id":"s1","status":"ok","timestamp":"x"})[1]
        mock_buy.side_effect  = lambda *a, **kw: (call_order.append("BUY"),  {"action":"BUY","symbol":"NEW","qty":3,"order_id":"b1","status":"ok","timestamp":"x"})[1]
        execute_rebalance(client, plans)
        assert call_order.index("SELL") < call_order.index("BUY")

    @patch("src.trading.rebalancer.place_sell_order", return_value=None)
    @patch("src.trading.rebalancer.place_buy_order", return_value=None)
    def test_market_closed_rebalance_skips(self, mock_buy, mock_sell):
        from src.trading.rebalancer import rebalance
        client = MagicMock()
        client.is_market_open.return_value = False
        result = rebalance(client, _make_strategy(), ["AAPL"])
        assert result == []
        mock_buy.assert_not_called()
        mock_sell.assert_not_called()


# ── TC-21: 策略執行器整合 ────────────────────────────────────────
class TestStrategyExecutor:
    @patch("src.strategy.strategy_executor.rebalance", return_value=[])
    @patch("src.strategy.strategy_executor.get_positions_info", return_value=[])
    @patch("src.strategy.strategy_executor.screen_stocks", return_value=["AAPL", "MSFT"])
    def test_run_strategy_returns_summary(self, mock_screen, mock_positions, mock_rebalance):
        from src.strategy.strategy_executor import run_strategy
        client = MagicMock()
        account = MagicMock()
        account.account_id = "TEST"
        strategy = _make_strategy()
        strategy.strategy_id = "test_strat"
        summary = run_strategy(client, account, strategy)
        assert "target_symbols" in summary
        assert summary["target_symbols"] == ["AAPL", "MSFT"]

    @patch("src.strategy.strategy_executor.rebalance", return_value=[])
    @patch("src.strategy.strategy_executor.get_positions_info", return_value=[])
    @patch("src.strategy.strategy_executor.screen_stocks", side_effect=Exception("網路錯誤"))
    def test_run_strategy_handles_screen_error(self, mock_screen, mock_positions, mock_rebalance):
        from src.strategy.strategy_executor import run_strategy
        client = MagicMock()
        account = MagicMock()
        account.account_id = "TEST"
        summary = run_strategy(client, account, _make_strategy())
        assert len(summary["errors"]) > 0

    @patch("src.strategy.strategy_executor.rebalance", return_value=[])
    @patch("src.strategy.strategy_executor.get_positions_info")
    @patch("src.strategy.strategy_executor.screen_stocks", return_value=["AAPL"])
    def test_stop_loss_triggers_close_position(self, mock_screen, mock_positions, mock_rebalance):
        from src.trading.position_manager import PositionInfo
        from src.strategy.strategy_executor import run_strategy
        pos = PositionInfo("OLD", 5, 200.0, 180.0, 900.0, -100.0, -10.0)  # -10% 停損
        mock_positions.return_value = [pos]
        with patch("src.strategy.strategy_executor.close_position") as mock_close:
            mock_close.return_value = {"action": "SELL", "symbol": "OLD", "qty": 5,
                                       "order_id": "x", "status": "ok", "timestamp": "t"}
            client = MagicMock()
            account = MagicMock()
            account.account_id = "T"
            strategy = _make_strategy(stop_loss=-8, take_profit=25)
            strategy.strategy_id = "s"
            run_strategy(client, account, strategy)
            mock_close.assert_called_once()

    @patch("src.strategy.strategy_executor.rebalance", return_value=[])
    @patch("src.strategy.strategy_executor.get_positions_info")
    @patch("src.strategy.strategy_executor.screen_stocks", return_value=["AAPL"])
    def test_notify_called_on_trade(self, mock_screen, mock_positions, mock_rebalance):
        mock_positions.return_value = []
        from src.strategy.strategy_executor import run_strategy
        client = MagicMock()
        account = MagicMock()
        account.account_id = "T"
        strategy = _make_strategy()
        strategy.strategy_id = "s"
        notified = []
        mock_rebalance.return_value = [{"action": "BUY", "symbol": "AAPL", "qty": 3,
                                        "order_id": "o1", "status": "ok", "timestamp": "t"}]
        summary = run_strategy(client, account, strategy, notify_fn=notified.append)
        assert isinstance(summary, dict)
