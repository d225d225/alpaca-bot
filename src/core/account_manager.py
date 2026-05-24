"""多帳戶管理：載入所有帳戶設定、建立對應 Client"""
import json
import logging
import os
from pathlib import Path
from typing import Iterator

from src.core.alpaca_client import AlpacaClient
from src.core.config import config

logger = logging.getLogger(__name__)


class AccountConfig:
    """單一帳戶設定物件"""

    def __init__(self, data: dict, source_file: Path):
        self.account_id  = data["account_id"]
        self.label       = data.get("label", self.account_id)
        self.api_key     = os.getenv(data["api_key_env"], config.ALPACA_API_KEY)
        self.api_secret  = os.getenv(data["api_secret_env"], config.ALPACA_API_SECRET)
        self.base_url    = data.get("base_url", config.ALPACA_BASE_URL)
        self.paper       = data.get("paper", True)
        self.active      = data.get("active", True)
        self.strategy_id = data.get("strategy_id", "")
        self.email_to    = data.get("email_to", config.EMAIL_TO)
        self.watchlists  = data.get("watchlists", {})
        self.source_file = source_file

    def __repr__(self):
        return f"<AccountConfig {self.account_id} strategy={self.strategy_id}>"

    def set_strategy(self, strategy_id: str) -> None:
        """切換策略並持久化更新到 JSON 檔"""
        self.strategy_id = strategy_id
        raw = json.loads(self.source_file.read_text())
        raw["strategy_id"] = strategy_id
        self.source_file.write_text(json.dumps(raw, ensure_ascii=False, indent=2))
        logger.info("帳戶 %s 切換策略 → %s", self.account_id, strategy_id)


class AccountManager:
    """管理所有帳戶 (load / iterate / build clients)"""

    def __init__(self, accounts_dir: Path | None = None):
        self._dir = Path(accounts_dir or config.ACCOUNTS_DIR)
        self._accounts: dict[str, AccountConfig] = {}
        self._clients:  dict[str, AlpacaClient]  = {}
        self._load_all()

    def _load_all(self) -> None:
        for f in sorted(self._dir.glob("account_*.json")):
            try:
                data = json.loads(f.read_text())
                acc  = AccountConfig(data, f)
                self._accounts[acc.account_id] = acc
                logger.info("載入帳戶：%s (%s)", acc.account_id, acc.label)
            except Exception as e:
                logger.error("載入帳戶失敗 %s: %s", f, e)

    def get_account(self, account_id: str) -> AccountConfig:
        if account_id not in self._accounts:
            raise KeyError(f"帳戶不存在：{account_id}")
        return self._accounts[account_id]

    def all_active(self) -> list[AccountConfig]:
        return [a for a in self._accounts.values() if a.active]

    def iter_active(self) -> Iterator[tuple[AccountConfig, AlpacaClient]]:
        for acc in self.all_active():
            yield acc, self.get_client(acc.account_id)

    def get_client(self, account_id: str) -> AlpacaClient:
        if account_id not in self._clients:
            acc = self.get_account(account_id)
            self._clients[account_id] = AlpacaClient(
                api_key=acc.api_key,
                api_secret=acc.api_secret,
                paper=acc.paper,
            )
        return self._clients[account_id]

    def __len__(self):
        return len(self._accounts)

    def __repr__(self):
        return f"<AccountManager accounts={list(self._accounts.keys())}>"
