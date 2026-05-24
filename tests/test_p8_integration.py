"""Phase 8 整合測試：跨模組流程（12 cases）"""
import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock


# ── TC-36: 報告完整流程 ──────────────────────────────────────────
class TestReportIntegration:
    def _make_full_report(self):
        from src.report.report_model import DailyReport
        return DailyReport(
            account_id="INT_TEST",
            strategy_id="momentum_top10",
            report_date="2026-05-24",
            generated_at="2026-05-24T21:00:00Z",
            cash=800_000.0, equity=1_050_000.0,
            portfolio_value=1_050_000.0, long_market_value=250_000.0,
            nav=1_050_000.0, nav_change_pct=0.48, total_pl_pct=5.0,
            daily_pl=5000.0, max_drawdown_pct=-3.2,
            positions=[{"symbol": "AAPL", "qty": 10, "avg_cost": 180.0,
                        "current_price": 185.0, "market_value": 1850.0,
                        "unrealized_pl": 50.0, "unrealized_pl_pct": 2.78}],
            trades=[{"action": "BUY", "symbol": "AAPL", "qty": 10,
                     "order_id": "abc", "status": "filled", "timestamp": "2026-05-24T21:01:00Z"}],
            top10_symbols=["AAPL", "MSFT", "NVDA"],
            top10_returns={"AAPL": {"1d": 0.5, "1w": 2.1, "1m": 5.3}},
            top10_pe={"AAPL": 28.5, "MSFT": 32.0},
            top10_prices={"AAPL": 185.0, "MSFT": 420.0, "NVDA": 900.0},
            watchlist_prices={"tech": {"AAPL": 185.0}, "ai": {"NVDA": 900.0}},
            nasdaq_1d_return=0.65, sp500_1d_return=0.32,
        )

    def test_report_json_contains_all_fields(self):
        r = self._make_full_report()
        data = json.loads(r.to_json())
        for field in ["account_id", "nav", "positions", "trades", "top10_symbols",
                      "top10_returns", "top10_pe", "top10_prices", "watchlist_prices",
                      "nasdaq_1d_return", "sp500_1d_return", "max_drawdown_pct"]:
            assert field in data, f"Missing field: {field}"

    def test_email_html_contains_positions(self):
        from src.report.report_view import render_daily_email
        r = self._make_full_report()
        html = render_daily_email(r)
        assert "AAPL" in html

    def test_email_html_contains_trades(self):
        from src.report.report_view import render_daily_email
        r = self._make_full_report()
        html = render_daily_email(r)
        assert "買入" in html or "BUY" in html

    def test_email_html_contains_watchlist(self):
        from src.report.report_view import render_daily_email
        r = self._make_full_report()
        html = render_daily_email(r)
        assert "tech" in html.lower() or "NVDA" in html

    def test_text_summary_shows_nav_change(self):
        from src.report.report_view import render_text_summary
        r = self._make_full_report()
        text = render_text_summary(r)
        assert "+0.48%" in text or "0.48" in text

    def test_text_summary_has_top10_section(self):
        from src.report.report_view import render_text_summary
        r = self._make_full_report()
        text = render_text_summary(r)
        assert "Top 10" in text or "AAPL" in text


# ── TC-37: 策略 → 報告 Pipeline ─────────────────────────────────
class TestStrategyReportPipeline:
    @patch("src.strategy.strategy_executor.rebalance")
    @patch("src.strategy.strategy_executor.get_positions_info", return_value=[])
    @patch("src.strategy.strategy_executor.screen_stocks")
    def test_strategy_produces_target_symbols(self, mock_screen, mock_pos, mock_rebal):
        mock_screen.return_value = ["AAPL", "MSFT", "NVDA"]
        mock_rebal.return_value = []
        from src.strategy.strategy_executor import run_strategy
        client = MagicMock()
        account = MagicMock()
        account.account_id = "TEST"
        strategy = MagicMock()
        strategy.strategy_id = "s"
        strategy.stop_loss_pct = -8
        strategy.take_profit_pct = 25
        summary = run_strategy(client, account, strategy)
        assert len(summary["target_symbols"]) == 3

    @patch("src.strategy.strategy_executor.rebalance")
    @patch("src.strategy.strategy_executor.get_positions_info", return_value=[])
    @patch("src.strategy.strategy_executor.screen_stocks", return_value=["X"])
    def test_summary_has_no_errors_on_success(self, mock_screen, mock_pos, mock_rebal):
        mock_rebal.return_value = []
        from src.strategy.strategy_executor import run_strategy
        client = MagicMock()
        account = MagicMock()
        account.account_id = "T"
        strategy = MagicMock()
        strategy.strategy_id = "s"
        strategy.stop_loss_pct = -8
        strategy.take_profit_pct = 25
        summary = run_strategy(client, account, strategy)
        assert summary["errors"] == []


# ── TC-38: 多帳戶串列執行 ────────────────────────────────────────
class TestMultiAccountExecution:
    def test_multiple_accounts_iterable(self, tmp_path):
        import json
        for i, aid in enumerate(["ACC_A", "ACC_B"]):
            data = {
                "account_id": aid,
                "api_key_env": "ALPACA_API_KEY",
                "api_secret_env": "ALPACA_API_SECRET",
                "active": True,
                "strategy_id": "momentum_top10",
            }
            (tmp_path / f"account_{aid}.json").write_text(json.dumps(data))
        from src.core.account_manager import AccountManager
        mgr = AccountManager(accounts_dir=tmp_path)
        active = mgr.all_active()
        assert len(active) == 2
        ids = [a.account_id for a in active]
        assert "ACC_A" in ids and "ACC_B" in ids

    def test_each_account_has_independent_strategy(self, tmp_path):
        import json
        data_a = {"account_id": "ACC_A", "api_key_env": "ALPACA_API_KEY",
                  "api_secret_env": "ALPACA_API_SECRET", "active": True,
                  "strategy_id": "momentum_top10"}
        data_b = {"account_id": "ACC_B", "api_key_env": "ALPACA_API_KEY",
                  "api_secret_env": "ALPACA_API_SECRET", "active": True,
                  "strategy_id": "value_top10"}
        (tmp_path / "account_ACC_A.json").write_text(json.dumps(data_a))
        (tmp_path / "account_ACC_B.json").write_text(json.dumps(data_b))
        from src.core.account_manager import AccountManager
        mgr = AccountManager(accounts_dir=tmp_path)
        assert mgr.get_account("ACC_A").strategy_id == "momentum_top10"
        assert mgr.get_account("ACC_B").strategy_id == "value_top10"

    def test_strategy_switch_per_account(self, tmp_path):
        import json
        data = {"account_id": "SWITCH", "api_key_env": "ALPACA_API_KEY",
                "api_secret_env": "ALPACA_API_SECRET", "active": True,
                "strategy_id": "momentum_top10"}
        f = tmp_path / "account_SWITCH.json"
        f.write_text(json.dumps(data))
        from src.core.account_manager import AccountManager
        mgr = AccountManager(accounts_dir=tmp_path)
        acc = mgr.get_account("SWITCH")
        acc.set_strategy("value_top10")
        assert acc.strategy_id == "value_top10"
        reloaded = json.loads(f.read_text())
        assert reloaded["strategy_id"] == "value_top10"

    def test_inactive_account_not_executed(self, tmp_path):
        import json
        data = {"account_id": "INACTIVE", "api_key_env": "ALPACA_API_KEY",
                "api_secret_env": "ALPACA_API_SECRET", "active": False,
                "strategy_id": "momentum_top10"}
        (tmp_path / "account_INACTIVE.json").write_text(json.dumps(data))
        from src.core.account_manager import AccountManager
        mgr = AccountManager(accounts_dir=tmp_path)
        assert len(mgr.all_active()) == 0
