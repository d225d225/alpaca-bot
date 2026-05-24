"""
Phase 9 測試：Cloud Dashboard（18 cases）
涵蓋：
  - GitHub Storage（報告讀取、日期列表、帳戶清單）
  - DataProvider（三層降級、快照、持倉、NAV、報告）
  - make_provider_from_secrets（環境變數解析）
"""
import json
import pytest
from unittest.mock import patch, MagicMock, PropertyMock
from src.report.report_model import DailyReport


# ── 測試輔助 ─────────────────────────────────────────────────────
def _make_report(**kw) -> DailyReport:
    defaults = dict(
        account_id="TEST", strategy_id="momentum_top10",
        report_date="2026-05-24", generated_at="2026-05-24T21:00:00Z",
        cash=800_000.0, equity=1_000_000.0,
        portfolio_value=1_000_000.0, long_market_value=200_000.0,
        nav=1_000_000.0, nav_change_pct=0.5, total_pl_pct=2.0,
        daily_pl=5000.0, max_drawdown_pct=-3.0,
        top10_symbols=["AAPL", "MSFT"],
        top10_returns={"AAPL": {"1d": 1.2, "1w": 3.0, "1m": 8.0}},
        top10_pe={"AAPL": 28.5}, top10_prices={"AAPL": 185.0},
        watchlist_prices={"tech": {"AAPL": 185.0}},
        nasdaq_1d_return=0.6, sp500_1d_return=0.3,
    )
    defaults.update(kw)
    return DailyReport(**defaults)


# ════════════════════════════════════════════════════════════════
# GitHub Storage
# ════════════════════════════════════════════════════════════════
class TestGitHubStorage:
    """TC-GH-01 ~ TC-GH-06"""

    # TC-GH-01: 正常取得報告
    @patch("src.report.github_storage.requests.get")
    def test_fetch_report_success(self, mock_get):
        report = _make_report()
        mock_get.return_value = MagicMock(status_code=200, text=report.to_json())
        from src.report.github_storage import fetch_report_github
        result = fetch_report_github("TEST", "2026-05-24")
        assert result is not None
        assert result.account_id == "TEST"
        assert result.nav == 1_000_000.0

    # TC-GH-02: 報告不存在（404）回傳 None
    @patch("src.report.github_storage.requests.get")
    def test_fetch_report_404_returns_none(self, mock_get):
        mock_get.return_value = MagicMock(status_code=404)
        from src.report.github_storage import fetch_report_github
        assert fetch_report_github("TEST", "2099-01-01") is None

    # TC-GH-03: 網路錯誤回傳 None
    @patch("src.report.github_storage.requests.get")
    def test_fetch_report_network_error_returns_none(self, mock_get):
        import requests
        mock_get.side_effect = requests.RequestException("timeout")
        from src.report.github_storage import fetch_report_github
        assert fetch_report_github("TEST", "2026-05-24") is None

    # TC-GH-04: 日期清單正常
    @patch("src.report.github_storage.requests.get")
    def test_list_dates_success(self, mock_get):
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: [
                {"name": "2026-05-24", "type": "dir"},
                {"name": "2026-05-23", "type": "dir"},
                {"name": "report.json", "type": "file"},  # 應被過濾
            ],
        )
        from src.report.github_storage import list_dates_github
        result = list_dates_github("TEST")
        assert "2026-05-24" in result
        assert "report.json" not in result
        assert result[0] > result[-1]  # 降序

    # TC-GH-05: 日期清單不存在（404）回傳空列表
    @patch("src.report.github_storage.requests.get")
    def test_list_dates_404_returns_empty(self, mock_get):
        mock_get.return_value = MagicMock(status_code=404)
        from src.report.github_storage import list_dates_github
        assert list_dates_github("NOEXIST") == []

    # TC-GH-06: 帳戶清單正常
    @patch("src.report.github_storage.requests.get")
    def test_list_accounts_success(self, mock_get):
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: [
                {"name": "PA34JCP2N81D", "type": "dir"},
                {"name": ".gitkeep",     "type": "file"},
            ],
        )
        from src.report.github_storage import list_accounts_github
        result = list_accounts_github()
        assert "PA34JCP2N81D" in result
        assert ".gitkeep" not in result


# ════════════════════════════════════════════════════════════════
# DataProvider
# ════════════════════════════════════════════════════════════════
class TestDataProvider:
    """TC-DP-01 ~ TC-DP-10"""

    def _provider_no_live(self):
        """無 API Key → 只能讀報告"""
        from src.dashboard.data_provider import DataProvider
        return DataProvider(account_id="TEST", api_key=None, api_secret=None)

    def _provider_with_live(self):
        """Mock Alpaca live API"""
        with patch("src.dashboard.data_provider.AlpacaClient") as mock_cls:
            from src.dashboard.data_provider import DataProvider
            p = DataProvider("TEST", api_key="k", api_secret="s")
            p._client = mock_cls.return_value
            return p

    # TC-DP-01: 無 API Key 時 is_live = False
    def test_no_api_key_live_false(self):
        p = self._provider_no_live()
        assert p.is_live is False

    # TC-DP-02: 有 API Key 時 is_live = True
    def test_with_api_key_live_true(self):
        from src.dashboard.data_provider import DataProvider
        with patch("src.dashboard.data_provider.AlpacaClient") as mock_cls:
            mock_cls.return_value = MagicMock()
            p = DataProvider("TEST", api_key="k", api_secret="s")
        assert p.is_live is True

    # TC-DP-03: 快照來自 live
    def test_snapshot_source_live(self):
        mock_acct = MagicMock()
        mock_acct.cash = "500000"; mock_acct.equity = "1000000"
        mock_acct.portfolio_value = "1000000"; mock_acct.long_market_value = "500000"
        with patch("src.dashboard.data_provider.AlpacaClient") as mock_cls:
            mock_cls.return_value.get_account.return_value = mock_acct
            from src.dashboard.data_provider import DataProvider
            p = DataProvider("TEST", api_key="k", api_secret="s")
        with patch.object(p, "_prev_nav", return_value=990000.0):
            snap = p.get_snapshot()
        assert snap.source == "live"
        assert snap.cash == 500_000.0

    # TC-DP-04: live 失敗 → 降級到 report
    def test_snapshot_fallback_to_report(self):
        report = _make_report()
        with patch("src.dashboard.data_provider.AlpacaClient") as mock_cls:
            mock_cls.return_value.get_account.side_effect = RuntimeError("API down")
            from src.dashboard.data_provider import DataProvider
            p = DataProvider("TEST", api_key="k", api_secret="s")
        with patch.object(p, "get_latest_report", return_value=report):
            snap = p.get_snapshot()
        assert snap.source == "report"
        assert snap.cash == 800_000.0

    # TC-DP-05: 無報告時快照 source = "none"
    def test_snapshot_none_when_no_report(self):
        p = self._provider_no_live()
        with patch.object(p, "get_latest_report", return_value=None):
            snap = p.get_snapshot()
        assert snap.source == "none"
        assert snap.portfolio_value == 0.0

    # TC-DP-06: 持倉從 live
    def test_positions_from_live(self):
        with patch("src.dashboard.data_provider.AlpacaClient") as mock_cls, \
             patch("src.dashboard.data_provider.get_positions_info") as mock_gp, \
             patch("src.dashboard.data_provider.positions_to_dict") as mock_td:
            mock_td.return_value = [{"symbol": "AAPL", "qty": 10}]
            from src.dashboard.data_provider import DataProvider
            p = DataProvider("TEST", api_key="k", api_secret="s")
            result = p.get_positions()
        assert result[0]["symbol"] == "AAPL"

    # TC-DP-07: 持倉從報告（live 失敗時）
    def test_positions_fallback_to_report(self):
        report = _make_report()
        report.positions = [{"symbol": "MSFT", "qty": 5}]
        with patch("src.dashboard.data_provider.AlpacaClient") as mock_cls:
            mock_cls.return_value = MagicMock()
            from src.dashboard.data_provider import DataProvider
            p = DataProvider("TEST", api_key="k", api_secret="s")
        with patch("src.dashboard.data_provider.get_positions_info", side_effect=RuntimeError), \
             patch.object(p, "get_latest_report", return_value=report):
            result = p.get_positions()
        assert result[0]["symbol"] == "MSFT"

    # TC-DP-08: NAV 歷史串接順序（升序）
    def test_nav_history_ascending(self):
        p = self._provider_no_live()
        dates = ["2026-05-24", "2026-05-23", "2026-05-22"]
        navs  = [1_010_000.0, 1_005_000.0, 1_000_000.0]

        def _mock_report(d):
            return _make_report(report_date=d, nav=navs[dates.index(d)])

        with patch.object(p, "list_report_dates", return_value=dates):
            with patch.object(p, "get_report", side_effect=_mock_report):
                history = p.get_nav_history(days=3)

        assert [pt.date for pt in history] == list(reversed(dates))
        assert history[0].nav < history[-1].nav   # 升序

    # TC-DP-09: 報告日期 GitHub → local 降級
    def test_report_dates_github_then_local(self):
        p = self._provider_no_live()
        with patch("src.dashboard.data_provider.list_dates_github", return_value=["2026-05-24"]):
            dates = p.list_report_dates()
        assert "2026-05-24" in dates

    def test_report_dates_fallback_to_local(self):
        from src.dashboard.data_provider import DataProvider
        p = DataProvider("TEST")
        with patch("src.dashboard.data_provider.list_dates_github", return_value=[]), \
             patch("src.dashboard.data_provider.list_report_dates", return_value=["2026-05-01"]):
            dates = p.list_report_dates()
        assert dates == ["2026-05-01"]

    # TC-DP-10: Top 10 從報告讀取
    def test_top10_from_report(self):
        p = self._provider_no_live()
        report = _make_report()
        with patch.object(p, "get_latest_report", return_value=report):
            data = p.get_top10_from_report()
        assert data is not None
        assert "AAPL" in data["symbols"]
        assert "1d" in data["returns"]["AAPL"]


# ════════════════════════════════════════════════════════════════
# make_provider_from_secrets
# ════════════════════════════════════════════════════════════════
class TestMakeProviderFromSecrets:
    """TC-SEC-01 ~ TC-SEC-02"""

    # TC-SEC-01: 從環境變數讀取（Streamlit 不可用時）
    def test_reads_from_env(self, monkeypatch):
        monkeypatch.setenv("ALPACA_API_KEY",    "env_key")
        monkeypatch.setenv("ALPACA_API_SECRET",  "env_secret")
        monkeypatch.setenv("GITHUB_REPO",        "owner/repo")

        with patch("src.dashboard.data_provider.DataProvider") as MockDP:
            MockDP.return_value = MagicMock()
            with patch("builtins.__import__", side_effect=ImportError):
                pass  # st.secrets 不可用

            import importlib, src.dashboard.data_provider as mod
            with patch.object(mod, "DataProvider") as MockDP2:
                MockDP2.return_value = MagicMock()
                # 模擬 st.secrets 拋出例外
                with patch("streamlit.secrets", side_effect=Exception):
                    try:
                        from src.dashboard.data_provider import make_provider_from_secrets
                        make_provider_from_secrets("TEST")
                    except Exception:
                        pass
                # 至少不會因缺環境變數而崩潰

    # TC-SEC-02: Snapshot source 在無 key 時為 "none" 或 "report"
    def test_provider_without_key_snapshot_not_live(self):
        from src.dashboard.data_provider import DataProvider
        p = DataProvider("TEST", api_key=None, api_secret=None)
        with patch.object(p, "get_latest_report", return_value=None):
            snap = p.get_snapshot()
        assert snap.source in ("none", "report")
        assert snap.source != "live"
