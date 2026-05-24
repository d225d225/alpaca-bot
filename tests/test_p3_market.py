"""Phase 3 測試：市場資料 & 選股（14 cases）"""
import pytest
from unittest.mock import patch, MagicMock
import pandas as pd


# ── TC-11: Top 10 排名 ───────────────────────────────────────────
class TestTop10:
    @patch("src.market.market_data.yf.Ticker")
    def test_top_n_returns_n_symbols(self, mock_ticker):
        mock_info = MagicMock()
        mock_info.market_cap = 1_000_000_000
        mock_ticker.return_value.fast_info = mock_info
        from src.market.market_data import get_top_n_nasdaq
        result = get_top_n_nasdaq(5)
        assert len(result) == 5

    @patch("src.market.market_data.yf.Ticker")
    def test_top_n_symbols_are_strings(self, mock_ticker):
        mock_info = MagicMock()
        mock_info.market_cap = 500_000_000
        mock_ticker.return_value.fast_info = mock_info
        from src.market.market_data import get_top_n_nasdaq
        result = get_top_n_nasdaq(3)
        assert all(isinstance(s, str) for s in result)

    @patch("src.market.market_data.yf.Ticker")
    def test_top_n_sorts_by_market_cap(self, mock_ticker):
        # 給不同市值，確認排序
        from src.market.market_data import NASDAQ_TOP20_SYMBOLS
        caps = {sym: float(i + 1) * 1e9 for i, sym in enumerate(NASDAQ_TOP20_SYMBOLS)}
        def side_effect(sym):
            m = MagicMock()
            m.fast_info.market_cap = caps.get(sym, 0)
            return m
        mock_ticker.side_effect = side_effect
        from src.market.market_data import get_top_n_nasdaq
        result = get_top_n_nasdaq(5)
        assert result[0] == NASDAQ_TOP20_SYMBOLS[-1]  # 最大市值在最後一個


# ── TC-12: 報酬率計算 ────────────────────────────────────────────
class TestReturnCalc:
    @patch("src.market.market_data.yf.Ticker")
    def test_return_pct_positive(self, mock_ticker):
        hist = pd.DataFrame({"Close": [100.0, 110.0]})
        mock_ticker.return_value.history.return_value = hist
        from src.market.market_data import get_return_pct
        r = get_return_pct("AAPL", "1d")
        assert r == pytest.approx(10.0, rel=0.01)

    @patch("src.market.market_data.yf.Ticker")
    def test_return_pct_negative(self, mock_ticker):
        hist = pd.DataFrame({"Close": [100.0, 90.0]})
        mock_ticker.return_value.history.return_value = hist
        from src.market.market_data import get_return_pct
        r = get_return_pct("AAPL", "1d")
        assert r == pytest.approx(-10.0, rel=0.01)

    @patch("src.market.market_data.yf.Ticker")
    def test_return_pct_insufficient_data_returns_zero(self, mock_ticker):
        hist = pd.DataFrame({"Close": [100.0]})
        mock_ticker.return_value.history.return_value = hist
        from src.market.market_data import get_return_pct
        r = get_return_pct("AAPL", "1d")
        assert r == 0.0

    @patch("src.market.market_data.get_return_pct")
    def test_returns_bulk_has_all_periods(self, mock_ret):
        mock_ret.return_value = 1.5
        from src.market.market_data import get_returns_bulk
        result = get_returns_bulk(["AAPL"])
        assert "1d" in result["AAPL"]
        assert "1w" in result["AAPL"]
        assert "1m" in result["AAPL"]


# ── TC-13: 本益比 ────────────────────────────────────────────────
class TestPECalc:
    @patch("src.market.pe_calculator.yf.Ticker")
    def test_pe_returns_float_when_available(self, mock_ticker):
        mock_ticker.return_value.info = {"trailingPE": 25.5}
        from src.market.pe_calculator import get_pe_ratio
        pe = get_pe_ratio("AAPL")
        assert pe == pytest.approx(25.5)

    @patch("src.market.pe_calculator.yf.Ticker")
    def test_pe_returns_none_for_negative_eps(self, mock_ticker):
        mock_ticker.return_value.info = {
            "trailingPE": None, "forwardPE": None,
            "currentPrice": 100, "trailingEps": -5.0
        }
        from src.market.pe_calculator import get_pe_ratio
        pe = get_pe_ratio("XYZ")
        assert pe is None

    @patch("src.market.pe_calculator.yf.Ticker")
    def test_pe_bulk_returns_dict(self, mock_ticker):
        mock_ticker.return_value.info = {"trailingPE": 20.0}
        from src.market.pe_calculator import get_pe_bulk
        result = get_pe_bulk(["AAPL", "MSFT"])
        assert "AAPL" in result
        assert "MSFT" in result

    def test_pe_label_low(self):
        from src.market.pe_calculator import pe_label
        assert "低估" in pe_label(12.0)

    def test_pe_label_reasonable(self):
        from src.market.pe_calculator import pe_label
        assert "合理" in pe_label(20.0)

    def test_pe_label_none(self):
        from src.market.pe_calculator import pe_label
        assert "N/A" in pe_label(None)
