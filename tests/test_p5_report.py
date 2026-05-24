"""Phase 5 測試：報告系統 Model/View（13 cases）"""
import json
import pytest
from pathlib import Path
from datetime import date


def _make_report(**kwargs):
    from src.report.report_model import DailyReport
    defaults = dict(
        account_id="TEST", strategy_id="momentum_top10",
        report_date="2026-05-24", generated_at="2026-05-24T21:00:00Z",
        cash=800_000.0, equity=1_000_000.0,
        portfolio_value=1_000_000.0, long_market_value=200_000.0,
        nav=1_000_000.0, nav_change_pct=0.5, total_pl_pct=0.0, daily_pl=5000.0,
        max_drawdown_pct=-2.5,
        top10_symbols=["AAPL", "MSFT"],
        top10_returns={"AAPL": {"1d": 1.2, "1w": 3.5, "1m": 8.0}},
        top10_pe={"AAPL": 28.5},
        top10_prices={"AAPL": 185.0},
    )
    defaults.update(kwargs)
    return DailyReport(**defaults)


# ── TC-21: JSON 序列化 ───────────────────────────────────────────
class TestReportModel:
    def test_report_to_json_is_valid(self):
        r = _make_report()
        raw = json.loads(r.to_json())
        assert raw["account_id"] == "TEST"
        assert raw["nav"] == 1_000_000.0

    def test_report_from_json_roundtrip(self):
        r = _make_report()
        r2 = r.from_json(r.to_json())
        assert r2.account_id == r.account_id
        assert r2.nav == r.nav

    def test_report_has_disclaimer(self):
        r = _make_report()
        assert len(r.disclaimer) > 10

    def test_report_date_format(self):
        r = _make_report()
        date.fromisoformat(r.report_date)  # should not raise

    def test_report_positions_default_empty(self):
        r = _make_report()
        assert isinstance(r.positions, list)


# ── TC-22: 報告儲存與讀取 ────────────────────────────────────────
class TestReportStorage:
    def test_save_creates_file(self, tmp_path, monkeypatch):
        from src.core.config import config
        monkeypatch.setattr(config, "REPORT_DIR", tmp_path)
        from src.report import report_storage
        monkeypatch.setattr(report_storage, "_report_path",
            lambda account_id, report_date: (
                (tmp_path / account_id / report_date).__class__.mkdir(
                    tmp_path / account_id / report_date, parents=True, exist_ok=True
                ) or tmp_path / account_id / report_date / "report.json"
            )
        )
        # 直接 patch REPORT_DIR
        import src.report.report_storage as rs
        rs_module_path = tmp_path
        r = _make_report()
        # 手動設定 REPORT_DIR
        import src.core.config as cfg
        original = cfg.config.REPORT_DIR
        cfg.config.REPORT_DIR = tmp_path
        try:
            path = rs.save_report(r)
            assert path.exists()
        finally:
            cfg.config.REPORT_DIR = original

    def test_load_report_returns_none_when_missing(self, tmp_path):
        import src.core.config as cfg
        original = cfg.config.REPORT_DIR
        cfg.config.REPORT_DIR = tmp_path
        try:
            from src.report.report_storage import load_report
            result = load_report("NOEXIST", "2099-01-01")
            assert result is None
        finally:
            cfg.config.REPORT_DIR = original

    def test_list_report_dates_empty(self, tmp_path):
        import src.core.config as cfg
        original = cfg.config.REPORT_DIR
        cfg.config.REPORT_DIR = tmp_path
        try:
            from src.report.report_storage import list_report_dates
            assert list_report_dates("NOEXIST") == []
        finally:
            cfg.config.REPORT_DIR = original


# ── TC-23: 報告 View ─────────────────────────────────────────────
class TestReportView:
    def test_text_summary_contains_nav(self):
        from src.report.report_view import render_text_summary
        r = _make_report()
        text = render_text_summary(r)
        assert "NAV" in text
        assert "TEST" in text

    def test_text_summary_contains_disclaimer(self):
        from src.report.report_view import render_text_summary
        r = _make_report()
        text = render_text_summary(r)
        assert "投資建議" in text or "不構成" in text

    def test_daily_email_renders_html(self):
        from src.report.report_view import render_daily_email
        r = _make_report()
        html = render_daily_email(r)
        assert "<html" in html.lower()
        assert "TEST" in html

    def test_top10_appears_in_email(self):
        from src.report.report_view import render_daily_email
        r = _make_report()
        html = render_daily_email(r)
        assert "AAPL" in html
