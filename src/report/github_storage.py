"""
GitHub 遠端報告存取
從 GitHub Raw Content API 讀取已 commit 的 JSON 報告
這樣 Dashboard 不需本地 reports/ 目錄，部署在任何地方都能用
"""
import logging
import requests
from typing import Optional

from src.report.report_model import DailyReport

logger = logging.getLogger(__name__)

GITHUB_RAW  = "https://raw.githubusercontent.com"
GITHUB_API  = "https://api.github.com"
DEFAULT_REPO   = "d225d225/alpaca-bot"
DEFAULT_BRANCH = "main"


def fetch_report_github(
    account_id:  str,
    report_date: str,
    repo:   str = DEFAULT_REPO,
    branch: str = DEFAULT_BRANCH,
    timeout: int = 10,
) -> Optional[DailyReport]:
    """
    從 GitHub Raw 下載單一日報 JSON。
    回傳 DailyReport 物件；若不存在或網路失敗回傳 None。
    """
    url = (
        f"{GITHUB_RAW}/{repo}/{branch}"
        f"/reports/{account_id}/{report_date}/report.json"
    )
    try:
        resp = requests.get(url, timeout=timeout)
        if resp.status_code == 200:
            logger.debug("GitHub 報告讀取成功：%s / %s", account_id, report_date)
            return DailyReport.from_json(resp.text)
        logger.debug("GitHub 報告不存在 [%d]：%s / %s", resp.status_code, account_id, report_date)
        return None
    except requests.RequestException as e:
        logger.warning("GitHub 網路失敗：%s", e)
        return None


def list_dates_github(
    account_id: str,
    repo:   str = DEFAULT_REPO,
    branch: str = DEFAULT_BRANCH,
    token:  Optional[str] = None,
    timeout: int = 10,
) -> list[str]:
    """
    透過 GitHub Contents API 列出帳戶所有有報告的日期（降序）。
    token 可選，設定後提升 API 速率限制（60 → 5000 req/hr）。
    """
    url = f"{GITHUB_API}/repos/{repo}/contents/reports/{account_id}"
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        resp = requests.get(url, headers=headers, timeout=timeout)
        if resp.status_code == 200:
            data = resp.json()
            dates = sorted(
                [item["name"] for item in data if item.get("type") == "dir"],
                reverse=True,
            )
            logger.debug("GitHub 日期清單：%d 筆  帳戶 %s", len(dates), account_id)
            return dates
        logger.debug("GitHub 目錄不存在 [%d]：%s", resp.status_code, account_id)
        return []
    except requests.RequestException as e:
        logger.warning("GitHub 目錄查詢失敗：%s", e)
        return []


def list_accounts_github(
    repo:   str = DEFAULT_REPO,
    branch: str = DEFAULT_BRANCH,
    token:  Optional[str] = None,
    timeout: int = 10,
) -> list[str]:
    """列出 reports/ 目錄下所有帳戶 ID（即子目錄名稱）"""
    url = f"{GITHUB_API}/repos/{repo}/contents/reports"
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        resp = requests.get(url, headers=headers, timeout=timeout)
        if resp.status_code == 200:
            return [item["name"] for item in resp.json() if item.get("type") == "dir"]
        return []
    except requests.RequestException as e:
        logger.warning("GitHub 帳戶清單失敗：%s", e)
        return []
