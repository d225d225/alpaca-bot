"""Phase 4 測試：交易引擎 & 再平衡（16 cases）"""
import pytest
from unittest.mock import MagicMock, patch
import math


# ── TC-16: 下單邏輯 ──────────────────────────────────────────────
class TestOrderManager:
    def _mock_client(self):
        client = MagicMock()
        order = MagicMock()
        order.id     = "order-123"
        order.status = "accepted"
        client.trading.submit_order.return_value = order
        return client

    def test_buy_order_returns_info(self):
        from src.trading.order_manager import place_buy_order
        client = self._mock_client()
        result = place_buy_order(client, "AAPL", 5)
        assert result is not None
        assert result["action"] == "BUY"
        assert result["symbol"] == "AAPL"
        assert result["qty"] == 5

    def test_buy_order_zero_qty_returns_none(self):
        from src.trading.order_manager import place_buy_order
        client = self._mock_client()
        result = place_buy_order(client, "AAPL", 0)
        assert result is None

    def test_sell_order_returns_info(self):
        from src.trading.order_manager import place_sell_order
        client = self._mock_client()
        result = place_sell_order(client, "TSLA", 3)
        assert result["action"] == "SELL"
        assert result["qty"] == 3

    def test_sell_order_negative_qty_returns_none(self):
        from src.trading.order_manager import place_sell_order
        client = self._mock_client()
        result = place_sell_order(client, "TSLA", -1)
        assert result is None

    def test_buy_calls_notify(self):
        from src.trading.order_manager import place_buy_order
        client   = self._mock_client()
        notified = []
        place_buy_order(client, "NVDA", 2, notify_fn=notified.append)
        assert len(notified) == 1
        assert notified[0]["symbol"] == "NVDA"

    def test_buy_api_failure_returns_none(self):
        from src.trading.order_manager import place_buy_order
        client = MagicMock()
        client.trading.submit_order.side_effect = RuntimeError("API error")
        result = place_buy_order(client, "AAPL", 1)
        assert result is None


# ── TC-17: 整數股計算 ─────────────────────────────────────────────
class TestWholeShares:
    def test_floor_to_whole_share(self):
        cash = 10_000.0
        price = 170.0
        qty = math.floor(cash / price)
        assert qty == 58
        assert isinstance(qty, int)

    def test_whole_share_when_price_exact(self):
        cash = 1_000.0
        price = 100.0
        qty = math.floor(cash / price)
        assert qty == 10

    def test_zero_qty_when_price_exceeds_cash(self):
        cash = 50.0
        price = 200.0
        qty = math.floor(cash / price)
        assert qty == 0


# ── TC-18: 持倉管理 ──────────────────────────────────────────────
class TestPositionManager:
    def _mock_position(self, symbol, qty, avg, curr):
        p = MagicMock()
        p.symbol          = symbol
        p.qty             = str(qty)
        p.avg_entry_price = str(avg)
        p.current_price   = str(curr)
        p.market_value    = str(qty * curr)
        p.unrealized_pl   = str((curr - avg) * qty)
        p.unrealized_plpc = str((curr - avg) / avg)
        return p

    def test_positions_info_returns_list(self):
        from src.trading.position_manager import get_positions_info
        client = MagicMock()
        client.get_positions.return_value = [
            self._mock_position("AAPL", 10, 150.0, 165.0)
        ]
        result = get_positions_info(client)
        assert len(result) == 1
        assert result[0].symbol == "AAPL"

    def test_unrealized_pl_pct_positive(self):
        from src.trading.position_manager import get_positions_info
        client = MagicMock()
        client.get_positions.return_value = [
            self._mock_position("AAPL", 10, 100.0, 110.0)
        ]
        result = get_positions_info(client)
        assert result[0].unrealized_pl_pct == pytest.approx(10.0, rel=0.01)

    def test_stop_loss_triggers(self):
        from src.trading.position_manager import PositionInfo, check_stop_loss
        pos = PositionInfo("TSLA", 5, 200.0, 184.0, 920.0, -80.0, -8.0)
        assert check_stop_loss(pos, stop_loss_pct=-8.0) is True

    def test_stop_loss_not_triggered(self):
        from src.trading.position_manager import PositionInfo, check_stop_loss
        pos = PositionInfo("TSLA", 5, 200.0, 196.0, 980.0, -20.0, -1.0)
        assert check_stop_loss(pos, stop_loss_pct=-8.0) is False

    def test_take_profit_triggers(self):
        from src.trading.position_manager import PositionInfo, check_take_profit
        pos = PositionInfo("NVDA", 2, 400.0, 500.0, 1000.0, 200.0, 25.0)
        assert check_take_profit(pos, take_profit_pct=25.0) is True

    def test_take_profit_not_triggered(self):
        from src.trading.position_manager import PositionInfo, check_take_profit
        pos = PositionInfo("NVDA", 2, 400.0, 420.0, 840.0, 40.0, 5.0)
        assert check_take_profit(pos, take_profit_pct=25.0) is False


# ── TC-19: 再平衡計畫 ────────────────────────────────────────────
class TestRebalancer:
    def _make_strategy(self):
        s = MagicMock()
        s.alloc_fraction.return_value = 0.10
        s.alloc_pct = 10
        s.whole_shares = True
        s.top_n = 3
        return s

    @patch("src.trading.rebalancer.get_positions_info")
    @patch("src.trading.rebalancer.get_prices_bulk")
    def test_plan_creates_buy_for_new_symbol(self, mock_prices, mock_positions):
        mock_prices.return_value = {"AAPL": 150.0, "MSFT": 300.0, "NVDA": 500.0}
        mock_positions.return_value = []  # 無持倉
        client = MagicMock()
        client.get_portfolio_value.return_value = 100_000.0
        from src.trading.rebalancer import compute_rebalance_plan
        plans = compute_rebalance_plan(client, self._make_strategy(), ["AAPL", "MSFT", "NVDA"])
        buy_plans = [p for p in plans if p.action == "BUY"]
        assert len(buy_plans) > 0

    @patch("src.trading.rebalancer.get_positions_info")
    @patch("src.trading.rebalancer.get_prices_bulk")
    def test_plan_sells_non_target_holdings(self, mock_prices, mock_positions):
        from src.trading.position_manager import PositionInfo
        mock_prices.return_value = {"AAPL": 150.0}
        mock_positions.return_value = [
            PositionInfo("OLD_STOCK", 10, 100.0, 110.0, 1100.0, 100.0, 10.0)
        ]
        client = MagicMock()
        client.get_portfolio_value.return_value = 50_000.0
        from src.trading.rebalancer import compute_rebalance_plan
        plans = compute_rebalance_plan(client, self._make_strategy(), ["AAPL"])
        sell_plans = [p for p in plans if p.action == "SELL" and p.symbol == "OLD_STOCK"]
        assert len(sell_plans) == 1
