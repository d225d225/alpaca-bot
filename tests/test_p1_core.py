"""Phase 1 測試：基礎建設 & 多帳戶管理（15 cases）"""
import json
import os
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock


# ── TC-01: Config 基本讀取 ────────────────────────────────────────
class TestConfig:
    def test_config_has_alpaca_attrs(self):
        from src.core.config import Config
        assert hasattr(Config, "ALPACA_API_KEY")
        assert hasattr(Config, "ALPACA_API_SECRET")
        assert hasattr(Config, "ALPACA_BASE_URL")

    def test_config_paths_are_path_objects(self):
        from src.core.config import config
        assert isinstance(config.REPORT_DIR, Path)
        assert isinstance(config.ACCOUNTS_DIR, Path)
        assert isinstance(config.STRATEGIES_DIR, Path)

    def test_config_is_paper_detects_url(self, monkeypatch):
        from src.core import config as cfg_module
        monkeypatch.setenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets/v2")
        from importlib import reload
        reload(cfg_module)
        assert cfg_module.config.is_paper()

    def test_validate_alpaca_raises_without_keys(self, monkeypatch):
        from src.core.config import Config
        monkeypatch.setattr(Config, "ALPACA_API_KEY", "")
        monkeypatch.setattr(Config, "ALPACA_API_SECRET", "")
        with pytest.raises(EnvironmentError):
            Config.validate_alpaca()

    def test_validate_alpaca_passes_with_keys(self, monkeypatch):
        from src.core.config import Config
        monkeypatch.setattr(Config, "ALPACA_API_KEY", "test_key")
        monkeypatch.setattr(Config, "ALPACA_API_SECRET", "test_secret")
        Config.validate_alpaca()  # should not raise


# ── TC-02: AlpacaClient 初始化 ────────────────────────────────────
class TestAlpacaClient:
    @patch("src.core.alpaca_client.TradingClient")
    @patch("src.core.alpaca_client.StockHistoricalDataClient")
    def test_client_initializes(self, mock_data, mock_trading):
        from src.core.alpaca_client import AlpacaClient
        client = AlpacaClient("key", "secret", paper=True)
        assert client._key == "key"
        assert client._paper is True
        mock_trading.assert_called_once()
        mock_data.assert_called_once()

    @patch("src.core.alpaca_client.TradingClient")
    @patch("src.core.alpaca_client.StockHistoricalDataClient")
    def test_get_cash_returns_float(self, mock_data, mock_trading):
        from src.core.alpaca_client import AlpacaClient
        mock_acct = MagicMock()
        mock_acct.cash = "1000000"
        mock_trading.return_value.get_account.return_value = mock_acct
        client = AlpacaClient("key", "secret")
        assert client.get_cash() == 1_000_000.0

    @patch("src.core.alpaca_client.TradingClient")
    @patch("src.core.alpaca_client.StockHistoricalDataClient")
    def test_get_equity_returns_float(self, mock_data, mock_trading):
        from src.core.alpaca_client import AlpacaClient
        mock_acct = MagicMock()
        mock_acct.equity = "950000.50"
        mock_trading.return_value.get_account.return_value = mock_acct
        client = AlpacaClient("key", "secret")
        assert client.get_equity() == pytest.approx(950000.50)

    @patch("src.core.alpaca_client.TradingClient")
    @patch("src.core.alpaca_client.StockHistoricalDataClient")
    def test_is_market_open(self, mock_data, mock_trading):
        from src.core.alpaca_client import AlpacaClient
        mock_clock = MagicMock()
        mock_clock.is_open = True
        mock_trading.return_value.get_clock.return_value = mock_clock
        client = AlpacaClient("key", "secret")
        assert client.is_market_open() is True


# ── TC-03: AccountConfig ──────────────────────────────────────────
class TestAccountConfig:
    def _make_acc(self, tmp_path, data=None):
        from src.core.account_manager import AccountConfig
        default = {
            "account_id": "TEST123",
            "label": "Test",
            "api_key_env": "ALPACA_API_KEY",
            "api_secret_env": "ALPACA_API_SECRET",
            "paper": True,
            "active": True,
            "strategy_id": "momentum_top10",
        }
        if data:
            default.update(data)
        f = tmp_path / "account_TEST123.json"
        f.write_text(json.dumps(default))
        return AccountConfig(default, f)

    def test_account_config_basic(self, tmp_path):
        acc = self._make_acc(tmp_path)
        assert acc.account_id == "TEST123"
        assert acc.paper is True
        assert acc.strategy_id == "momentum_top10"

    def test_account_config_active_default(self, tmp_path):
        acc = self._make_acc(tmp_path)
        assert acc.active is True

    def test_set_strategy_updates_json(self, tmp_path):
        acc = self._make_acc(tmp_path)
        acc.set_strategy("value_top10")
        assert acc.strategy_id == "value_top10"
        raw = json.loads(acc.source_file.read_text())
        assert raw["strategy_id"] == "value_top10"


# ── TC-04: AccountManager ────────────────────────────────────────
class TestAccountManager:
    def _setup_accounts(self, tmp_path, count=2):
        for i in range(count):
            data = {
                "account_id": f"ACC00{i}",
                "label": f"Account {i}",
                "api_key_env": "ALPACA_API_KEY",
                "api_secret_env": "ALPACA_API_SECRET",
                "paper": True,
                "active": True,
                "strategy_id": "momentum_top10",
            }
            (tmp_path / f"account_ACC00{i}.json").write_text(json.dumps(data))

    def test_manager_loads_all_accounts(self, tmp_path):
        self._setup_accounts(tmp_path, 2)
        from src.core.account_manager import AccountManager
        mgr = AccountManager(accounts_dir=tmp_path)
        assert len(mgr) == 2

    def test_manager_get_account(self, tmp_path):
        self._setup_accounts(tmp_path, 1)
        from src.core.account_manager import AccountManager
        mgr = AccountManager(accounts_dir=tmp_path)
        acc = mgr.get_account("ACC000")
        assert acc.account_id == "ACC000"

    def test_manager_raises_for_unknown_account(self, tmp_path):
        self._setup_accounts(tmp_path, 1)
        from src.core.account_manager import AccountManager
        mgr = AccountManager(accounts_dir=tmp_path)
        with pytest.raises(KeyError):
            mgr.get_account("NONEXISTENT")

    def test_manager_all_active_excludes_inactive(self, tmp_path):
        data0 = {"account_id": "A1", "api_key_env": "ALPACA_API_KEY",
                  "api_secret_env": "ALPACA_API_SECRET", "active": True, "strategy_id": "m"}
        data1 = {"account_id": "A2", "api_key_env": "ALPACA_API_KEY",
                  "api_secret_env": "ALPACA_API_SECRET", "active": False, "strategy_id": "m"}
        (tmp_path / "account_A1.json").write_text(json.dumps(data0))
        (tmp_path / "account_A2.json").write_text(json.dumps(data1))
        from src.core.account_manager import AccountManager
        mgr = AccountManager(accounts_dir=tmp_path)
        active = mgr.all_active()
        assert len(active) == 1
        assert active[0].account_id == "A1"
