import sys
from pathlib import Path
import unittest

SRC_DIR = Path(__file__).resolve().parents[1] / 'src'
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from strategies import (
    STRATEGY_REGISTRY,
    get_strategy,
    Legacy101Strategy,
    ThreeStagesStrategy,
    MaxProfitStrategy,
    FastestClearStrategy,
    BalancedStrategy,
    AggressiveBalancedStrategy,
    AdaptiveRushStrategy,
    GrinderStrategy,
    CustomParametricStrategy,
)


class TestStrategyRegistry(unittest.TestCase):
    def test_registry_completeness(self):
        expected_keys = {
            "legacy_101",
            "three_stages",
            "max_profit",
            "fastest_clear",
            "balanced",
            "aggressive_balanced",
            "adaptive_rush",
            "grinder",
            "custom_parametric",
        }
        self.assertEqual(set(STRATEGY_REGISTRY.keys()), expected_keys)

    def test_factory_instantiation(self):
        for key in STRATEGY_REGISTRY:
            strat = get_strategy(key)
            self.assertIsNotNone(strat)
            self.assertTrue(hasattr(strat, "decide"))


class TestLegacy101Strategy(unittest.TestCase):
    def setUp(self):
        self.strat = Legacy101Strategy()

    def test_target_achieved(self):
        # daily >= 19800 and cashout >= 10000 -> cashout
        self.assertEqual(self.strat.decide(12800, 25600, 0.70, 20000), "cashout")
        self.assertEqual(self.strat.last_reason, "legacy_sprint_goal")

    def test_sprint_continue(self):
        # daily >= 19800 and cashout < 10000 -> challenge
        self.assertEqual(self.strat.decide(3200, 6400, 0.70, 20000), "challenge")
        self.assertEqual(self.strat.last_reason, "legacy_sprint_chase")

    def test_cushion_warning(self):
        # total + current <= 19800 and total + next > 19800 -> cashout
        self.assertEqual(self.strat.decide(3200, 6400, 0.70, 15000), "cashout")
        self.assertEqual(self.strat.last_reason, "legacy_cushion_brake")

    def test_force_double(self):
        # total + current > 19800 and current < 10000 -> challenge
        self.assertEqual(self.strat.decide(400, 800, 0.70, 19800), "challenge")
        self.assertEqual(self.strat.last_reason, "legacy_sprint_chase")

    def test_lucky_cashout(self):
        # total + current > 19800 and current >= 10000 -> cashout
        self.assertEqual(self.strat.decide(10000, 20000, 0.70, 11000), "cashout")
        self.assertEqual(self.strat.last_reason, "legacy_cushion_windfall")

    def test_low_rate_cashout(self):
        # win_rate < 0.60 -> cashout
        self.assertEqual(self.strat.decide(800, 1600, 0.55, 5000), "cashout")
        self.assertEqual(self.strat.last_reason, "legacy_low_winrate")


class TestThreeStagesStrategy(unittest.TestCase):
    def test_stage_0_and_2_always_challenge(self):
        for stage in (0, 2):
            strat = ThreeStagesStrategy(stage=stage)
            strat.start_round(400, 0)
            self.assertEqual(strat.decide(), "challenge")

    def test_stage_1_targets_cushion(self):
        strat = ThreeStagesStrategy(stage=1)
        # 12800 coins + 400 base -> target_wins = 4 (400 * 2^4 = 6400, 12800 + 6400 < 20000)
        strat.start_round(400, 12800)
        self.assertEqual(strat.target_wins, 4)
        for _ in range(4):
            self.assertEqual(strat.decide(), "challenge")
            strat.guess_clicked()
            strat.confirm_success()
        self.assertEqual(strat.decide(), "cashout")
        self.assertEqual(strat.expected_cash, 6400)


class TestMaxProfitStrategy(unittest.TestCase):
    def setUp(self):
        self.strat = MaxProfitStrategy()

    def test_cushion_overshoot_guard(self):
        # daily (18000) + current (1600) <= 19800, next (3200) > 19800 -> cashout
        self.assertEqual(self.strat.decide(1600, 3200, 0.75, 18000), "cashout")

    def test_cushion_low_win_rate(self):
        # win_rate < 0.60 -> cashout
        self.assertEqual(self.strat.decide(800, 1600, 0.55, 5000), "cashout")

    def test_cushion_safe_continue(self):
        # safe to double: 5000 + 1600 <= 19800 and rate >= 0.60 -> challenge
        self.assertEqual(self.strat.decide(800, 1600, 0.70, 5000), "challenge")

    def test_sprint_at_19800(self):
        # daily >= 19800, cashout < 10000 -> challenge
        self.assertEqual(self.strat.decide(3200, 6400, 0.50, 19800), "challenge")
        # daily >= 19800, cashout >= 10000 -> cashout
        self.assertEqual(self.strat.decide(10000, 20000, 0.50, 19800), "cashout")


class TestFastestClearStrategy(unittest.TestCase):
    def setUp(self):
        self.strat = FastestClearStrategy()

    def test_always_challenges_until_cap_reached(self):
        # Even with low win rate, always double
        self.assertEqual(self.strat.decide(3200, 6400, 0.40, 5000), "challenge")

    def test_cashout_when_daily_plus_current_hits_20k(self):
        # 14000 + 6400 = 20400 >= 20000 -> cashout
        self.assertEqual(self.strat.decide(6400, 12800, 0.70, 14000), "cashout")


class TestBalancedStrategy(unittest.TestCase):
    def setUp(self):
        self.strat = BalancedStrategy()

    def test_build_phase_cashout_at_6400(self):
        # daily < 15000, cashout >= 6400 -> cashout
        self.assertEqual(self.strat.decide(6400, 12800, 0.70, 8000), "cashout")

    def test_build_phase_low_rate(self):
        # daily < 15000, rate < 0.55 -> cashout
        self.assertEqual(self.strat.decide(800, 1600, 0.52, 8000), "cashout")

    def test_push_phase_allows_higher_cashout(self):
        # 15000 <= daily < 19800: safe double without overshooting 19800 (15000 + 1600 = 16600 <= 19800)
        # rate 0.52 (>= 0.50) -> challenge
        self.assertEqual(self.strat.decide(800, 1600, 0.52, 15000), "challenge")

    def test_sprint_phase(self):
        # daily >= 19800, current < 10000 -> challenge
        self.assertEqual(self.strat.decide(6400, 12800, 0.45, 19800), "challenge")
        # daily >= 19800, current >= 10000 -> cashout
        self.assertEqual(self.strat.decide(10000, 20000, 0.45, 19800), "cashout")


class TestAggressiveBalancedStrategy(unittest.TestCase):
    def setUp(self):
        self.strat = AggressiveBalancedStrategy()

    def test_build_phase_more_lenient_rate(self):
        # daily < 12000, win rate 0.52 (>= 0.50) -> challenge
        self.assertEqual(self.strat.decide(1600, 3200, 0.52, 5000), "challenge")
        # rate < 0.50 -> cashout
        self.assertEqual(self.strat.decide(1600, 3200, 0.48, 5000), "cashout")

    def test_push_phase_threshold(self):
        # 12000 <= daily < 19800: safe double (13000 + 3200 = 16200 <= 19800)
        # rate 0.46 (>= 0.45) -> challenge
        self.assertEqual(self.strat.decide(1600, 3200, 0.46, 13000), "challenge")
        # rate < 0.45 -> cashout
        self.assertEqual(self.strat.decide(1600, 3200, 0.42, 13000), "cashout")


class TestAdaptiveRushStrategy(unittest.TestCase):
    def setUp(self):
        self.strat = AdaptiveRushStrategy()

    def test_rush_mode_initially(self):
        # Rush mode behaves like Fastest: challenges even on low win rate
        self.assertEqual(self.strat.decide(1600, 3200, 0.45, 0), "challenge")

    def test_auto_adjust_on_net_profit_loss(self):
        # daily_fails = 50 * 50 = -2500 net profit (< -2000 floor)
        self.strat._check_auto_adjust(daily_coins=0, daily_fails=50)
        self.assertTrue(self.strat._in_cushion_mode)
        # Now in cushion mode: cashout at 6400
        self.assertEqual(self.strat.decide(6400, 12800, 0.70, 5000), "cashout")


class TestGrinderStrategy(unittest.TestCase):
    def setUp(self):
        self.strat = GrinderStrategy()

    def test_low_win_rate_cashout(self):
        # win_rate < 0.60 -> cashout
        self.assertEqual(self.strat.decide(400, 800, 0.55, 1000), "cashout")

    def test_max_doubles_limit(self):
        # Grinder has max 4 doubles per round
        self.strat.start_round(base_cash=200, coins=1000)
        for _ in range(4):
            self.strat.decide(400, 800, 0.70, 1000)
        # 5th double attempt hits MAX_DOUBLES limit -> cashout
        self.assertEqual(self.strat.decide(800, 1600, 0.70, 1000), "cashout")


class TestCustomParametricStrategy(unittest.TestCase):
    def test_custom_parameters(self):
        strat = CustomParametricStrategy(
            cashout_target=3200,
            min_win_rate=0.55,
            sprint_threshold=19800,
            sprint_cashout=10000,
            max_doubles=3,
            drop_on_seven_eight=True,
        )
        strat.start_round(base_cash=200, coins=5000)

        # Drop on middle card (rate < 0.54)
        self.assertEqual(strat.decide(200, 400, 0.51, 5000), "cashout")

        # Win rate between min_win_rate (0.55) and middle threshold
        self.assertEqual(strat.decide(200, 400, 0.58, 5000), "challenge")

        # 3 doubles completed -> max doubles hit
        strat.decide(200, 400, 0.70, 5000)
        strat.decide(400, 800, 0.70, 5000)
        self.assertEqual(strat.decide(800, 1600, 0.70, 5000), "cashout")


if __name__ == "__main__":
    unittest.main()
