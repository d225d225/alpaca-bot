"""歷史報告儲存與讀取（JSON 檔案）"""
import json
import logging
from datetime import date
from pathlib import Path

from src.core.config import config
from src.report.report_model import DailyReport

logger = logging.getLogger(__name__)


def _report_path(account_id: str, report_date: str) -> Path:
    d = config.REPORT_DIR / account_id / report_date
    d.mkdir(parents=True, exist_ok=True)
    return d / "report.json"


def save_report(report: DailyReport) -> Path:
    """儲存每日報告到 reports/{account_id}/{date}/report.json"""
    path = _report_path(report.account_id, report.report_date)
    path.write_text(report.to_json(), encoding="utf-8")
    logger.info("報告已儲存：%s", path)
    return path


def load_report(account_id: str, report_date: str) -> DailyReport | None:
    """讀取指定帳戶、指定日期的報告"""
    path = _report_path(account_id, report_date)
    if not path.exists():
        logger.warning("報告不存在：%s", path)
        return None
    return DailyReport.from_json(path.read_text(encoding="utf-8"))


def list_report_dates(account_id: str) -> list[str]:
    """列出帳戶所有有報告的日期（降序）"""
    base = config.REPORT_DIR / account_id
    if not base.exists():
        return []
    dates = sorted(
        [d.name for d in base.iterdir() if d.is_dir() and (d / "report.json").exists()],
        reverse=True,
    )
    return dates


def load_nav_history(account_id: str, last_n: int = 365) -> list[float]:
    """載入最近 N 天的 NAV 歷史（供回撤計算）"""
    dates = list_report_dates(account_id)[:last_n]
    navs  = []
    for d in reversed(dates):
        r = load_report(account_id, d)
        if r:
            navs.append(r.nav)
    return navs


def load_prev_nav(account_id: str) -> float | None:
    """取得最近一次報告的 NAV（作為前日 NAV）"""
    dates = list_report_dates(account_id)
    if not dates:
        return None
    r = load_report(account_id, dates[0])
    return r.nav if r else None
