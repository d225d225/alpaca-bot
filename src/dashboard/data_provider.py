"""
Dashboard 統一資料存取層（DataProvider）

優先序（每個方法獨立降級）：
  1. Alpaca 即時 API   → 最新帳戶快照、即時持倉
  2. GitHub 報告 API   → 已 commit 的 JSON 報告（無需本地檔案）
  3. 本地 reports/     → 本機開發時的 fallback

設計原則：
  - Dashboard 只與 DataProvider 互動，不直接呼叫 Alpaca / 檔案系統
  - 無 API Key 時仍可展示歷史報告（唯讀模式）
  - 所有方法都有明確的 source 回傳，讓 UI 顯示資料來源
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

from src.report.report_model import DailyReport
from src.report.github_storage import fetch_report_github, list_dates_github, list_accounts_github
from src.report.report_storage import load_report, list_report_dates
from src.core.alpaca_client import AlpacaClient
from src.trading.position_manager import get_positions_info, positions_to_dict

logger = logging.getLogger(__name__)


@dataclass
class Snapshot:
    """帳戶快照（現金 / NAV / 持倉市值）"""
    cash:            float = 0.0
    equity:          float = 0.0
    portfolio_value: float = 0.0
    long_market_value: float = 0.0
    nav_change_pct:  float = 0.0
    source: str = "none"   # "live" | "report" | "none"


@dataclass
class NavPoint:
    date: str
    nav:  float


class DataProvider:
    """
    統一資料存取，支援 live / GitHub / local 三層降級。
    可在 Streamlit Cloud、本機、CI 任何環境使用。
    """

    def __init__(
        self,
        account_id:   str,
        api_key:      Optional[str] = None,
        api_secret:   Optional[str] = None,
        paper:        bool = True,
        github_repo:  str = "d225d225/alpaca-bot",
        github_token: Optional[str] = None,
    ):
        self.account_id   = account_id
        self._github_repo  = github_repo
        self._github_token = github_token
        self._client       = None
        self._live_ok      = False

        # 嘗試建立即時 Alpaca 連線
        if api_key and api_secret:
            try:
                self._client  = AlpacaClient(api_key, api_secret, paper)
                self._live_ok = True
                logger.info("DataProvider: 即時 API 可用（%s）", account_id)
            except Exception as e:
                logger.warning("DataProvider: Alpaca API 初始化失敗：%s", e)

    # ── 公開屬性 ─────────────────────────────────────────────────
    @property
    def is_live(self) -> bool:
        return self._live_ok

    # ── 帳戶快照 ─────────────────────────────────────────────────
    def get_snapshot(self) -> Snapshot:
        if self._live_ok:
            try:
                return self._snapshot_from_live()
            except Exception as e:
                logger.warning("即時快照失敗，降級到報告：%s", e)
        return self._snapshot_from_report()

    def _snapshot_from_live(self) -> Snapshot:
        acct = self._client.get_account()
        prev = self._prev_nav()
        pv   = float(acct.portfolio_value)
        chg  = ((pv - prev) / prev * 100) if prev else 0.0
        return Snapshot(
            cash=float(acct.cash),
            equity=float(acct.equity),
            portfolio_value=pv,
            long_market_value=float(acct.long_market_value),
            nav_change_pct=round(chg, 2),
            source="live",
        )

    def _snapshot_from_report(self) -> Snapshot:
        r = self.get_latest_report()
        if r:
            return Snapshot(
                cash=r.cash, equity=r.equity,
                portfolio_value=r.portfolio_value,
                long_market_value=r.long_market_value,
                nav_change_pct=r.nav_change_pct,
                source="report",
            )
        return Snapshot(source="none")

    def _prev_nav(self) -> Optional[float]:
        dates = self.list_report_dates()
        if not dates:
            return None
        r = self.get_report(dates[0])
        return r.nav if r else None

    # ── 持倉 ─────────────────────────────────────────────────────
    def get_positions(self) -> list[dict]:
        if self._live_ok:
            try:
                return positions_to_dict(get_positions_info(self._client))
            except Exception as e:
                logger.warning("即時持倉失敗，降級到報告：%s", e)
        r = self.get_latest_report()
        return r.positions if r else []

    # ── 報告 ─────────────────────────────────────────────────────
    def get_latest_report(self) -> Optional[DailyReport]:
        dates = self.list_report_dates()
        if not dates:
            return None
        return self.get_report(dates[0])

    def get_report(self, report_date: str) -> Optional[DailyReport]:
        """GitHub → 本地，依序嘗試"""
        r = fetch_report_github(self.account_id, report_date,
                                repo=self._github_repo)
        if r:
            return r
        return load_report(self.account_id, report_date)

    def list_report_dates(self) -> list[str]:
        """GitHub → 本地，依序嘗試"""
        dates = list_dates_github(self.account_id, repo=self._github_repo,
                                  token=self._github_token)
        if dates:
            return dates
        return list_report_dates(self.account_id)

    # ── NAV 歷史 ─────────────────────────────────────────────────
    def get_nav_history(self, days: int = 365) -> list[NavPoint]:
        """回傳最近 N 天的 (date, nav) 序列（升序）"""
        dates = self.list_report_dates()[:days]
        result = []
        for d in reversed(dates):
            r = self.get_report(d)
            if r:
                result.append(NavPoint(date=d, nav=r.nav))
        return result

    # ── 市場資料（不依賴 Alpaca，yfinance 即可）──────────────────
    def get_top10_from_report(self) -> Optional[dict]:
        """從最新報告取 Top 10 資料（不呼叫 yfinance）"""
        r = self.get_latest_report()
        if not r:
            return None
        return {
            "symbols": r.top10_symbols,
            "returns": r.top10_returns,
            "pe":      r.top10_pe,
            "prices":  r.top10_prices,
        }

    def get_watchlist_from_report(self) -> dict:
        r = self.get_latest_report()
        return r.watchlist_prices if r else {}

    def get_benchmark_returns(self) -> dict:
        r = self.get_latest_report()
        if r:
            return {"nasdaq": r.nasdaq_1d_return, "sp500": r.sp500_1d_return}
        return {"nasdaq": 0.0, "sp500": 0.0}


# ── 工廠函式（供 Streamlit 使用）────────────────────────────────
def make_provider_from_secrets(account_id: str) -> DataProvider:
    """
    從 Streamlit secrets 或環境變數建立 DataProvider。
    在 Streamlit Cloud 上會讀 st.secrets；本機讀 os.environ / .env。
    """
    try:
        import streamlit as st
        secrets = st.secrets
        api_key    = secrets.get("ALPACA_API_KEY", "")
        api_secret = secrets.get("ALPACA_API_SECRET", "")
        paper      = "paper" in secrets.get("ALPACA_BASE_URL", "paper")
        gh_repo    = secrets.get("GITHUB_REPO", "d225d225/alpaca-bot")
        gh_token   = secrets.get("GITHUB_TOKEN", None)
    except Exception:
        import os
        api_key    = os.getenv("ALPACA_API_KEY", "")
        api_secret = os.getenv("ALPACA_API_SECRET", "")
        paper      = "paper" in os.getenv("ALPACA_BASE_URL", "paper")
        gh_repo    = os.getenv("GITHUB_REPO", "d225d225/alpaca-bot")
        gh_token   = os.getenv("GITHUB_TOKEN", None)

    return DataProvider(
        account_id=account_id,
        api_key=api_key or None,
        api_secret=api_secret or None,
        paper=paper,
        github_repo=gh_repo,
        github_token=gh_token,
    )


def list_accounts_from_github(github_repo: str = "d225d225/alpaca-bot",
                               github_token: Optional[str] = None) -> list[str]:
    """從 GitHub 取得帳戶清單（不需本地 accounts/ 目錄）"""
    return list_accounts_github(repo=github_repo, token=github_token)
