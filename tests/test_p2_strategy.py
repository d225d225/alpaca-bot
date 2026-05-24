"""Phase 2 測試：JSON 策略引擎（12 cases）"""
import json
import pytest
from pathlib import Path


def _write_strategy(tmp_path, data: dict) -> Path:
    f = tmp_path / f"{data['strategy_id']}.json"
    f.write_text(json.dumps(data))
    return f


def _write_schema(tmp_path) -> Path:
    schema = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "required": ["strategy_id", "name", "universe", "top_n", "alloc_pct"],
        "properties": {
            "strategy_id": {"type": "string"},
            "name":        {"type": "string"},
            "universe":    {"type": "string", "enum": ["NASDAQ_TOP_MC", "SP500", "CUSTOM"]},
            "top_n":       {"type": "integer", "minimum": 1, "maximum": 50},
            "alloc_pct":   {"type": "number", "minimum": 1, "maximum": 100},
            "whole_shares":       {"type": "boolean"},
            "stop_loss_pct":      {"type": "number", "maximum": 0},
            "take_profit_pct":    {"type": "number", "minimum": 0},
            "notify_on_trade":    {"type": "boolean"},
            "custom_symbols":     {"type": "array", "items": {"type": "string"}},
            "rebalance":   {"type": "object"},
            "filters":     {"type": "object"},
        }
    }
    f = tmp_path / "schema.json"
    f.write_text(json.dumps(schema))
    return f


VALID_STRATEGY = {
    "strategy_id": "momentum_top10",
    "name": "動能前十",
    "universe": "NASDAQ_TOP_MC",
    "top_n": 10,
    "alloc_pct": 10.0,
    "whole_shares": True,
    "stop_loss_pct": -8,
    "take_profit_pct": 25,
    "notify_on_trade": True,
    "rebalance": {"on_new_funds": True, "monthly": True},
    "filters": {"min_price": 5},
}


# ── TC-06: Schema 格式驗證 ────────────────────────────────────────
class TestStrategySchema:
    def test_valid_strategy_passes(self, tmp_path):
        _write_schema(tmp_path)
        _write_strategy(tmp_path, VALID_STRATEGY)
        from src.strategy.strategy_loader import StrategyLoader
        loader = StrategyLoader(tmp_path)
        assert "momentum_top10" in loader

    def test_missing_required_field_fails(self, tmp_path):
        _write_schema(tmp_path)
        bad = {k: v for k, v in VALID_STRATEGY.items() if k != "name"}
        _write_strategy(tmp_path, bad)
        from src.strategy.strategy_loader import StrategyLoader
        loader = StrategyLoader(tmp_path)
        assert "momentum_top10" not in loader  # 驗證失敗，不載入

    def test_invalid_universe_fails(self, tmp_path):
        _write_schema(tmp_path)
        bad = {**VALID_STRATEGY, "universe": "INVALID_UNIVERSE"}
        _write_strategy(tmp_path, bad)
        from src.strategy.strategy_loader import StrategyLoader
        loader = StrategyLoader(tmp_path)
        assert "momentum_top10" not in loader

    def test_top_n_out_of_range_fails(self, tmp_path):
        _write_schema(tmp_path)
        bad = {**VALID_STRATEGY, "top_n": 100}  # max 50
        _write_strategy(tmp_path, bad)
        from src.strategy.strategy_loader import StrategyLoader
        loader = StrategyLoader(tmp_path)
        assert "momentum_top10" not in loader


# ── TC-07: Strategy 物件屬性 ─────────────────────────────────────
class TestStrategyObject:
    def _loader(self, tmp_path):
        _write_schema(tmp_path)
        _write_strategy(tmp_path, VALID_STRATEGY)
        from src.strategy.strategy_loader import StrategyLoader
        return StrategyLoader(tmp_path)

    def test_strategy_top_n(self, tmp_path):
        s = self._loader(tmp_path).get("momentum_top10")
        assert s.top_n == 10

    def test_strategy_alloc_fraction(self, tmp_path):
        s = self._loader(tmp_path).get("momentum_top10")
        assert s.alloc_fraction() == pytest.approx(0.10)

    def test_strategy_rebalance_flags(self, tmp_path):
        s = self._loader(tmp_path).get("momentum_top10")
        assert s.should_rebalance_on_new_funds() is True
        assert s.should_rebalance_monthly() is True

    def test_strategy_stop_loss_negative(self, tmp_path):
        s = self._loader(tmp_path).get("momentum_top10")
        assert s.stop_loss_pct <= 0

    def test_strategy_not_found_raises(self, tmp_path):
        loader = self._loader(tmp_path)
        with pytest.raises(KeyError):
            loader.get("nonexistent_strategy")


# ── TC-08: 多策略載入 ────────────────────────────────────────────
class TestMultiStrategy:
    def test_two_strategies_load(self, tmp_path):
        _write_schema(tmp_path)
        _write_strategy(tmp_path, VALID_STRATEGY)
        s2 = {**VALID_STRATEGY, "strategy_id": "value_top10", "name": "價值策略"}
        _write_strategy(tmp_path, s2)
        from src.strategy.strategy_loader import StrategyLoader
        loader = StrategyLoader(tmp_path)
        assert len(loader.all_strategies()) == 2

    def test_strategy_ids_list(self, tmp_path):
        _write_schema(tmp_path)
        _write_strategy(tmp_path, VALID_STRATEGY)
        from src.strategy.strategy_loader import StrategyLoader
        loader = StrategyLoader(tmp_path)
        assert "momentum_top10" in loader.strategy_ids()

    def test_contains_operator(self, tmp_path):
        _write_schema(tmp_path)
        _write_strategy(tmp_path, VALID_STRATEGY)
        from src.strategy.strategy_loader import StrategyLoader
        loader = StrategyLoader(tmp_path)
        assert "momentum_top10" in loader
        assert "ghost_strategy" not in loader
