"""Tests for the config.json -> strategy kwargs mapping (regression for B1/B2)."""
import sys
from pathlib import Path
import unittest

SRC_DIR = Path(__file__).resolve().parents[1] / 'src'
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from strategies import get_strategy, strategy_kwargs_from_config, CustomParametricStrategy


GUI_CONFIG = {
    "param_min_win_rate": 60,
    "param_cushion_target": 18000,
    "param_sprint_target": 8000,
    "param_max_doubles": 7,
    "param_drop_seven_eight": True,
}


class TestStrategyKwargsFromConfig(unittest.TestCase):
    def test_non_custom_modes_get_no_kwargs(self):
        self.assertEqual(strategy_kwargs_from_config("max_profit", GUI_CONFIG), {})

    def test_gui_keys_map_to_constructor_kwargs(self):
        kwargs = strategy_kwargs_from_config("custom_parametric", GUI_CONFIG)
        self.assertEqual(kwargs, {
            "min_win_rate": 0.60,
            "sprint_threshold": 18000,
            "sprint_cashout": 8000,
            "max_doubles": 7,
            "drop_on_seven_eight": True,
        })

    def test_kwargs_construct_strategy(self):
        strat = get_strategy("custom_parametric", **strategy_kwargs_from_config("custom_parametric", GUI_CONFIG))
        self.assertIsInstance(strat, CustomParametricStrategy)
        self.assertEqual(strat.sprint_threshold, 18000)
        self.assertEqual(strat.sprint_cashout, 8000)
        self.assertEqual(strat.max_doubles, 7)

    def test_invalid_values_are_skipped(self):
        kwargs = strategy_kwargs_from_config("custom_parametric", {"param_max_doubles": "abc", "param_cushion_target": None})
        self.assertEqual(kwargs, {})

    def test_mode_is_case_insensitive(self):
        self.assertIn("max_doubles", strategy_kwargs_from_config(" Custom_Parametric ", GUI_CONFIG))


if __name__ == "__main__":
    unittest.main()
