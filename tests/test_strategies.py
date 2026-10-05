import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[1] / 'src'
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import unittest
from strategies import (
    BaseStrategy,
    MaxProfitStrategy,
    FastestClearStrategy,
    get_strategy,
)


class TestStrategies(unittest.TestCase):
    def test_factory_get_strategy(self):
        self.assertIsInstance(get_strategy("max_profit"), MaxProfitStrategy)
        self.assertIsInstance(get_strategy("fastest_clear"), FastestClearStrategy)

        with self.assertRaises(ValueError):
            get_strategy("non_existent_strategy")

    def test_max_profit_target_achieved(self):
        strat = MaxProfitStrategy()
        # Daily coins >= 19800 and cashout >= 10000 -> cashout
        decision = strat.decide(current_cashout=12800, next_reward=25600, win_rate=0.75, daily_coins=20000)
        self.assertEqual(decision, 'cashout')

    def test_max_profit_sprint_continue(self):
        strat = MaxProfitStrategy()
        # Daily coins >= 19800 but cashout < 10000 -> challenge
        decision = strat.decide(current_cashout=3200, next_reward=6400, win_rate=0.75, daily_coins=20050)
        self.assertEqual(decision, 'challenge')

    def test_max_profit_cushion_warning(self):
        strat = MaxProfitStrategy()
        # total + current <= 19800 and total + next > 19800 -> cashout
        decision = strat.decide(current_cashout=3200, next_reward=6400, win_rate=0.80, daily_coins=14000)
        self.assertEqual(decision, 'cashout')

    def test_max_profit_lucky_cashout(self):
        strat = MaxProfitStrategy()
        # total + current > 19800 and current >= 10000 -> cashout
        decision = strat.decide(current_cashout=10000, next_reward=20000, win_rate=0.80, daily_coins=11000)
        self.assertEqual(decision, 'cashout')

    def test_max_profit_force_double(self):
        strat = MaxProfitStrategy()
        # total + current > 19800 and current < 10000 -> challenge
        decision = strat.decide(current_cashout=400, next_reward=800, win_rate=0.80, daily_coins=19800)
        self.assertEqual(decision, 'challenge')

    def test_max_profit_low_rate_cashout(self):
        strat = MaxProfitStrategy()
        # win_rate < 0.60 -> cashout
        decision = strat.decide(current_cashout=800, next_reward=1600, win_rate=0.55, daily_coins=5000)
        self.assertEqual(decision, 'cashout')

    def test_max_profit_safe_continue(self):
        strat = MaxProfitStrategy()
        decision = strat.decide(current_cashout=800, next_reward=1600, win_rate=0.72, daily_coins=5000)
        self.assertEqual(decision, 'challenge')

    def test_aliases_and_subclasses(self):
        self.assertTrue(issubclass(MaxProfitStrategy, BaseStrategy))

    def test_high_low_counter_probability(self):
        try:
            from auto_bot import HighLowCounter
        except ImportError:
            self.skipTest("numpy or cv2 not installed")
        counter = HighLowCounter()
        choice, rate = counter.get_best_choice_and_rate(7)
        self.assertEqual(choice, 'high')
        self.assertAlmostEqual(rate, 28 / 52, places=4)

        # After removing 4 sevens, total cards = 48, rate = 28 / 48
        counter.remove_cards([7, 7, 7, 7])
        choice, rate = counter.get_best_choice_and_rate(7)
        self.assertEqual(choice, 'high')
        self.assertAlmostEqual(rate, 28 / 48, places=4)

    def test_card_recognizer_precomputed_shifts(self):
        try:
            import numpy as np
            from recognizer import CardRecognizer
        except ImportError:
            self.skipTest("numpy or cv2 not installed")
        mask = np.zeros((64, 64), dtype=np.uint8)
        mask[20:44, 20:44] = 255
        shifts = CardRecognizer._precompute_shifts(mask)
        self.assertEqual(len(shifts), 49)

        # Exact match should yield 1.0
        score = CardRecognizer._shape_score(mask, shifts)
        self.assertEqual(score, 1.0)


if __name__ == '__main__':
    unittest.main()

