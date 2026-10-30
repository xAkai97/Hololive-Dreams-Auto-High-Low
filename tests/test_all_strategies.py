import sys
from pathlib import Path
import unittest

SRC_DIR = Path(__file__).resolve().parents[1] / 'src'
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from strategies import (
    STRATEGY_REGISTRY,
    get_strategy,
    MaxProfitStrategy,
    TrueMaxProfitStrategy,
    TrueMaxCoinsStrategy,
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
            "balanced",
            "max_profit",
            "fastest_clear",
            "adaptive_rush",
            "grinder",
            "custom_parametric",
            "true_max_coins",
        }
        self.assertEqual(set(STRATEGY_REGISTRY.keys()), expected_keys)
        self.assertEqual(list(STRATEGY_REGISTRY.keys())[0], "balanced")

    def test_factory_instantiation(self):
        for key in STRATEGY_REGISTRY:
            strat = get_strategy(key)
            self.assertIsNotNone(strat)
            self.assertTrue(hasattr(strat, "decide"))
        # Test backward-compatibility aliases
        strat_alias = get_strategy("true_max_profit")
        self.assertIsInstance(strat_alias, TrueMaxCoinsStrategy)
        strat_agg = get_strategy("aggressive_balanced")
        self.assertIsInstance(strat_agg, BalancedStrategy)
        self.assertEqual(strat_agg.play_style, "aggressive")


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

    def test_dynamic_cushion_19900_even_and_odd_payouts(self):
        # 19,700 + 200 = 19,900 (<= 19,900, next 400 -> 20,100 > 19,900) -> cashout to reach 19,900
        self.assertEqual(self.strat.decide(200, 400, 0.85, 19700), "cashout")
        self.assertFalse(self.strat.intent_to_fail)
        # Once at 19,900, next round enters sprint phase
        self.assertEqual(self.strat.decide(200, 400, 0.85, 19900), "challenge")
        self.assertFalse(self.strat.intent_to_fail)

        # 19,200 + 700 (Flush) = 19,900 -> cashout
        self.assertEqual(self.strat.decide(700, 1400, 0.80, 19200), "cashout")
        # 14,300 + 5,600 (Flush x8) = 19,900 -> cashout
        self.assertEqual(self.strat.decide(5600, 11200, 0.80, 14300), "cashout")
        # 18,400 + 1,500 (Four of a Kind) = 19,900 -> cashout
        self.assertEqual(self.strat.decide(1500, 3000, 0.80, 18400), "cashout")
        # 19,600 + 200 = 19,800 (next 400 -> 20,000 > 19,900) -> cashout to reach 19,800
        self.assertEqual(self.strat.decide(200, 400, 0.80, 19600), "cashout")

    def test_early_overshoot_intentional_fail_vs_high_payout_sprint(self):
        # At 19,700 or 19,600 with Five of a Kind (7,000 -> 14,000 max):
        # 19,600 + 14,000 = 33,600 >= 32,600 -> challenge to WIN (intent_to_fail = False)
        self.assertEqual(self.strat.decide(7000, 14000, 0.75, 19600), "challenge")
        self.assertFalse(self.strat.intent_to_fail)
        self.assertEqual(self.strat.decide(7000, 14000, 0.75, 19700), "challenge")
        self.assertFalse(self.strat.intent_to_fail)

        # At 19,500 with Flush (700 -> 11,200 max): 19,500 + 11,200 = 30,700 < 32,600 -> purposely fail
        self.assertEqual(self.strat.decide(700, 1400, 0.75, 19500), "challenge")
        self.assertTrue(self.strat.intent_to_fail)

        # At 19,700 with Straight (400 -> 12,800 max): 19,700 + 12,800 = 32,500 < 32,600 -> purposely fail
        self.assertEqual(self.strat.decide(400, 800, 0.75, 19700), "challenge")
        self.assertTrue(self.strat.intent_to_fail)

        # At 18,400 with Five of a Kind (7,000 -> 14,000 max): 18,400 + 14,000 = 32,400 < 32,600 -> purposely fail
        self.assertEqual(self.strat.decide(7000, 14000, 0.75, 18400), "challenge")
        self.assertTrue(self.strat.intent_to_fail)

        # At 13,600 with Royal Flush (10,000 -> 20,000 max): 13,600 + 20,000 = 33,600 >= 32,600 -> challenge to WIN
        self.assertEqual(self.strat.decide(10000, 20000, 0.75, 13600), "challenge")
        self.assertFalse(self.strat.intent_to_fail)


class TestTrueMaxProfitStrategy(unittest.TestCase):
    def setUp(self):
        self.strat = TrueMaxProfitStrategy(hunt_14k_attempts=3)

    def test_parity_aware_19900_cushion(self):
        # Even daily coins (e.g. 10,000) + Flush (700) flips parity to odd (10,700) -> lock in immediately!
        self.assertEqual(self.strat.decide(700, 1400, 0.85, 10000), "cashout")
        self.assertFalse(self.strat.intent_to_fail)

        # Even daily coins at 19,200 + 200 = 19,400 (> 19,200 even ceiling) -> must double or fail, not cash out at 19,800
        self.assertEqual(self.strat.decide(400, 800, 0.85, 19400), "challenge")
        self.assertTrue(self.strat.intent_to_fail)

        # Odd daily coins (19,700) + 200 = 19,900 -> cashout to hit 19,900
        self.assertEqual(self.strat.decide(200, 400, 0.85, 19700), "cashout")
        self.assertFalse(self.strat.intent_to_fail)

    def test_sprint_hunts_five_of_a_kind_and_respects_attempt_limit(self):
        # At 19,900, non-Five-of-a-Kind hand (200 -> max 12,800 < 14,000) is purposely failed for first 3 attempts
        for attempt in range(3):
            self.strat.start_round(base_cash=200, coins=19900)
            self.assertEqual(self.strat.decide(200, 400, 0.85, 19900), "challenge")
            self.assertTrue(self.strat.intent_to_fail)
            self.strat.notify_fail()

        # On 4th attempt (after 3 failed hunt attempts), falls back to Adaptive Max Profit (challenges normally)
        self.strat.start_round(base_cash=200, coins=19900)
        self.assertEqual(self.strat.decide(200, 400, 0.85, 19900), "challenge")
        self.assertFalse(self.strat.intent_to_fail)

    def test_sprint_five_of_a_kind_doubles_to_14000(self):
        self.strat.start_round(base_cash=7000, coins=19900)
        self.assertEqual(self.strat.decide(7000, 14000, 0.70, 19900), "challenge")
        self.assertFalse(self.strat.intent_to_fail)
        self.assertEqual(self.strat.decide(14000, 28000, 0.70, 19900), "cashout")

    def test_live_intercept_switches_to_adaptive(self):
        self.strat.force_adaptive_sprint = True
        self.strat.start_round(base_cash=200, coins=19900)
        self.assertEqual(self.strat.decide(200, 400, 0.85, 19900), "challenge")
        self.assertFalse(self.strat.intent_to_fail)


class TestFastestClearStrategy(unittest.TestCase):
    def setUp(self):
        self.strat = FastestClearStrategy()

    def test_always_challenges_until_cap_reached(self):
        # Even with low win rate, always double
        self.assertEqual(self.strat.decide(3200, 6400, 0.40, 5000), "challenge")

    def test_cashout_when_daily_plus_current_hits_20k(self):
        # 14000 + 6400 = 20400 >= 20000 -> cashout
        self.assertEqual(self.strat.decide(6400, 12800, 0.70, 14000), "cashout")

    def test_custom_target_limit(self):
        self.strat.target_limit = 25000
        # 14000 + 6400 = 20400 < 25000 -> challenge
        self.assertEqual(self.strat.decide(6400, 12800, 0.70, 14000), "challenge")
        # 14000 + 12800 = 26800 >= 25000 -> cashout
        self.assertEqual(self.strat.decide(12800, 25600, 0.70, 14000), "cashout")

    def test_reset_round_clears_intent_to_fail(self):
        self.strat.intent_to_fail = True
        self.strat.last_cashout = 6400
        self.strat.base_cash = 200
        self.strat.reset_round()
        self.assertFalse(self.strat.intent_to_fail)
        self.assertIsNone(self.strat.last_cashout)
        self.assertIsNone(self.strat.base_cash)


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

    def test_play_styles_aggressive_default_conservative(self):
        agg = BalancedStrategy(play_style="aggressive")
        dflt = BalancedStrategy(play_style="default")
        cons = BalancedStrategy(play_style="conservative")

        # Build phase at win_rate=0.52 (daily=5000, cashout=1600):
        # aggressive (>=0.50) challenges, default (<0.55) and conservative (<0.60) cashout
        self.assertEqual(agg.decide(1600, 3200, 0.52, 5000), "challenge")
        self.assertEqual(dflt.decide(1600, 3200, 0.52, 5000), "cashout")
        self.assertEqual(cons.decide(1600, 3200, 0.52, 5000), "cashout")

        # Build phase at win_rate=0.57 (daily=5000, cashout=1600):
        # aggressive and default challenge, conservative (<0.60) cashes out
        self.assertEqual(agg.decide(1600, 3200, 0.57, 5000), "challenge")
        self.assertEqual(dflt.decide(1600, 3200, 0.57, 5000), "challenge")
        self.assertEqual(cons.decide(1600, 3200, 0.57, 5000), "cashout")

        # Build phase cashout target: conservative cashes out at 3200, default/aggressive continue
        self.assertEqual(cons.decide(3200, 6400, 0.75, 5000), "cashout")
        self.assertEqual(dflt.decide(3200, 6400, 0.75, 5000), "challenge")


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

    def test_rush_mode_custom_target_limit(self):
        self.strat.target_limit = 25000
        # 14000 + 6400 = 20400 < 25000 -> challenge
        self.assertEqual(self.strat.decide(6400, 12800, 0.70, 14000), "challenge")
        # 14000 + 12800 = 26800 >= 25000 -> cashout
        self.assertEqual(self.strat.decide(12800, 25600, 0.70, 14000), "cashout")

    def test_reset_round_clears_intent_to_fail(self):
        self.strat.intent_to_fail = True
        self.strat.last_cashout = 6400
        self.strat.base_cash = 200
        self.strat.reset_round()
        self.assertFalse(self.strat.intent_to_fail)
        self.assertIsNone(self.strat.last_cashout)
        self.assertIsNone(self.strat.base_cash)


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
            self.assertEqual(self.strat.decide(400, 800, 0.70, 1000), "challenge")
            self.strat.guess_clicked()
        # 5th double attempt hits MAX_DOUBLES limit -> cashout
        self.assertEqual(self.strat.decide(800, 1600, 0.70, 1000), "cashout")

    def test_grinder_notify_push_does_not_consume_doubles(self):
        self.strat.start_round(base_cash=200, coins=1000)
        self.strat.guess_clicked()
        self.assertEqual(self.strat._doubles_this_round, 1)
        self.strat.notify_push()
        self.assertEqual(self.strat._doubles_this_round, 0)


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
        strat.guess_clicked()
        strat.guess_clicked()
        strat.guess_clicked()
        self.assertEqual(strat.decide(800, 1600, 0.70, 5000), "cashout")


if __name__ == "__main__":
    unittest.main()
