"""策略載入器：讀取 JSON、驗證 Schema、回傳策略物件"""
import json
import logging
from pathlib import Path

import jsonschema

from src.core.config import config

logger = logging.getLogger(__name__)

_SCHEMA_PATH = config.STRATEGIES_DIR / "schema.json"


def _load_schema() -> dict:
    return json.loads(_SCHEMA_PATH.read_text())


class Strategy:
    """策略物件 — 所有欄位皆為屬性，不可修改原始資料"""

    def __init__(self, data: dict, source_file: Path):
        self._data       = data
        self.source_file = source_file
        self.strategy_id     = data["strategy_id"]
        self.name            = data["name"]
        self.universe        = data["universe"]
        self.top_n           = int(data["top_n"])
        self.alloc_pct       = float(data["alloc_pct"])
        self.whole_shares    = bool(data.get("whole_shares", True))
        self.stop_loss_pct   = float(data.get("stop_loss_pct", -8))
        self.take_profit_pct = float(data.get("take_profit_pct", 25))
        self.notify_on_trade = bool(data.get("notify_on_trade", True))
        self.custom_symbols  = list(data.get("custom_symbols", []))
        self.rebalance       = data.get("rebalance", {"on_new_funds": True, "monthly": True})
        self.filters         = data.get("filters", {})

    def should_rebalance_on_new_funds(self) -> bool:
        return self.rebalance.get("on_new_funds", True)

    def should_rebalance_monthly(self) -> bool:
        return self.rebalance.get("monthly", True)

    def alloc_fraction(self) -> float:
        """每檔配置比例（0.1 = 10%）"""
        return self.alloc_pct / 100.0

    def __repr__(self):
        return f"<Strategy {self.strategy_id} top_n={self.top_n} alloc={self.alloc_pct}%>"


class StrategyLoader:
    """從 strategies/ 目錄載入所有策略，並快取"""

    def __init__(self, strategies_dir: Path | None = None):
        self._dir      = Path(strategies_dir or config.STRATEGIES_DIR)
        self._schema   = _load_schema()
        self._cache: dict[str, Strategy] = {}
        self._load_all()

    def _load_all(self) -> None:
        for f in sorted(self._dir.glob("*.json")):
            if f.name == "schema.json":
                continue
            try:
                data = json.loads(f.read_text())
                jsonschema.validate(instance=data, schema=self._schema)
                s = Strategy(data, f)
                self._cache[s.strategy_id] = s
                logger.info("載入策略：%s（%s）", s.strategy_id, s.name)
            except jsonschema.ValidationError as e:
                logger.error("策略格式錯誤 %s: %s", f.name, e.message)
            except Exception as e:
                logger.error("載入策略失敗 %s: %s", f, e)

    def get(self, strategy_id: str) -> Strategy:
        if strategy_id not in self._cache:
            raise KeyError(f"策略不存在：{strategy_id}")
        return self._cache[strategy_id]

    def all_strategies(self) -> list[Strategy]:
        return list(self._cache.values())

    def strategy_ids(self) -> list[str]:
        return list(self._cache.keys())

    def __contains__(self, strategy_id: str) -> bool:
        return strategy_id in self._cache
