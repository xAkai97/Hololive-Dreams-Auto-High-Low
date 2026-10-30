"""Edge-case, mutation, and fuzzing test fixtures for core pure functions and parsers."""
import sys
from pathlib import Path
import unittest

SRC_DIR = Path(__file__).resolve().parents[2] / 'src'
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import auto_bot
from poker_core import card_id, _evaluate_category5, calculate_best, JOKER_ID
from reward_vision import _DIGIT_TRANSLATE_TABLE
from settlement import is_valid_settlement_amount
from strategies.base import get_max_round_payout
from strategies import STRATEGY_REGISTRY, get_strategy


class TestConfigParserFuzz(unittest.TestCase):
    """Stress test config parser helpers against corrupted and adversarial payloads."""

    def test_cfg_get_int_malicious_inputs(self):
        fuzz_cases = [
            ("NaN", 50),
            ("Infinity", 50),
            ("-Infinity", 50),
            (None, 50),
            ([], 50),
            ({}, 50),
            ("\x00nullbyte", 50),
            ("99999999999999999999999999999999999999999", 50),  # Clamped to max_val
            (-99999999999999999999999999999999999999999, 50),  # Clamped to min_val
            (float("nan"), 50),
            (float("inf"), 50),
            (3.14159, 3),
            ("  100  \n", 100),
            (True, 1),
            (False, 0),
        ]
        for val, expected_or_type in fuzz_cases:
            cfg = {"test_key": val}
            res = auto_bot.cfg_get_int(cfg, "test_key", default=50, min_val=0, max_val=100000)
            self.assertIsInstance(res, int)
            self.assertGreaterEqual(res, 0)
            self.assertLessEqual(res, 100000)

    def test_cfg_get_str_malicious_inputs(self):
        fuzz_cases = [
            (None, "default"),
            (12345, "12345"),
            ([], "default"),
            ({}, "default"),
            ("\x00\x01\x02", "\x00\x01\x02"),
            ("   padded_key   \t", "padded_key"),
        ]
        for val, expected in fuzz_cases:
            cfg = {"test_key": val}
            res = auto_bot.cfg_get_str(cfg, "test_key", default="default")
            self.assertIsInstance(res, str)
            self.assertEqual(res, expected)

    def test_cfg_get_bool_malicious_inputs(self):
        fuzz_cases = [
            (True, True),
            (False, False),
            ("true", True),
            ("True", True),
            ("1", True),
            ("yes", True),
            ("false", False),
            ("0", False),
            ("no", False),
            (None, False),
            ([], False),
            ({}, False),
            (1, True),
            (0, False),
            (999, True),
        ]
        for val, expected in fuzz_cases:
            cfg = {"test_key": val}
            res = auto_bot.cfg_get_bool(cfg, "test_key", default=False)
            self.assertIsInstance(res, bool)
            self.assertEqual(res, expected)


class TestMaxPayoutAndSettlementFuzz(unittest.TestCase):
    """Stress test payout boundary calculations and settlement validators."""

    def test_get_max_round_payout_boundaries(self):
        boundaries = [
            (-500, 0),
            (0, 0),
            (1, 16384),
            (200, 12800),
            (400, 12800),
            (700, 11200),
            (800, 12800),
            (1500, 12000),
            (3000, 12000),
            (7000, 14000),
            (10000, 20000),
            (12800, 12800),
            (14000, 14000),
            (20000, 20000),
            (999999, 999999),
        ]
        for cashout, expected in boundaries:
            self.assertEqual(get_max_round_payout(cashout), expected)

    def test_is_valid_settlement_amount_fuzz(self):
        valid = [50, 100, 200, 700, 12800, 14000, 20000, 33900, 60000]
        invalid = [
            -50, 0, 25, 49, 51, 60050, 100000,
            True, False, 200.0, "200", None, [], {}, float("nan")
        ]
        for v in valid:
            self.assertTrue(is_valid_settlement_amount(v), f"Expected {v} to be valid")
        for inv in invalid:
            self.assertFalse(is_valid_settlement_amount(inv), f"Expected {inv} to be invalid")


class TestRewardVisionDigitTranslationFuzz(unittest.TestCase):
    """Stress test OCR digit normalization against noisy substitutions and surrogate strings."""

    def test_digit_translate_table_mutations(self):
        test_strings = [
            ("16O0", "1600"),
            ("SB1O", "5810"),
            ("l28OO", "12800"),
            ("Q4OO", "0400"),
            ("   \n\t14000   ", "14000"),
            ("S0O8", "5008"),
        ]
        for raw, expected in test_strings:
            cleaned = raw.strip().translate(_DIGIT_TRANSLATE_TABLE)
            self.assertEqual(cleaned, expected)
            self.assertTrue(cleaned.isdigit())


class TestPokerEvaluatorFuzz(unittest.TestCase):
    """Stress test 5-card evaluation with edge hand combinations."""

    def test_5card_combinations_with_jokers(self):
        # 4 Aces + Joker = Five of a Kind (category index 8)
        c_aces = [card_id("A", "S"), card_id("A", "H"), card_id("A", "D"), card_id("A", "C"), JOKER_ID]
        cat = _evaluate_category5(c_aces[0], c_aces[1], c_aces[2], c_aces[3], c_aces[4])
        self.assertEqual(cat, 8)  # 8 = Five of a Kind

        # 4 Kings without Joker = Four of a Kind (category index 6)
        c_kings = [card_id("K", "S"), card_id("K", "H"), card_id("K", "D"), card_id("K", "C"), card_id("2", "S")]
        cat = _evaluate_category5(c_kings[0], c_kings[1], c_kings[2], c_kings[3], c_kings[4])
        self.assertEqual(cat, 6)  # 6 = Four of a Kind

        # Royal Flush with Joker: 10, J, Q, K of Spades + Joker (category index 9)
        c_royal = [card_id("10", "S"), card_id("J", "S"), card_id("Q", "S"), card_id("K", "S"), JOKER_ID]
        cat = _evaluate_category5(c_royal[0], c_royal[1], c_royal[2], c_royal[3], c_royal[4])
        self.assertEqual(cat, 9)  # 9 = Royal Flush


class TestStrategyDecideFuzz(unittest.TestCase):
    """Fuzz strategy decide() methods with boundary, negative, and extreme numeric inputs."""

    def test_all_strategies_survive_fuzzed_parameters(self):
        fuzzed_scenarios = [
            (0, 0, 0.0, 0),
            (-500, -1000, -0.5, -2000),
            (999999, 1999998, 2.5, 999999),
            (200, 400, None, None),
            (None, None, 0.75, 19800),
        ]
        for key in STRATEGY_REGISTRY:
            strat = get_strategy(key)
            strat.reset_round()
            for current, next_r, win_rate, daily in fuzzed_scenarios:
                try:
                    action = strat.decide(
                        current_cashout=current,
                        next_reward=next_r,
                        win_rate=win_rate,
                        daily_coins=daily,
                    )
                    self.assertIn(action, ("cashout", "challenge", "stop"))
                except Exception as e:
                    self.fail(f"Strategy {key} crashed on input ({current}, {next_r}, {win_rate}, {daily}): {e}")


if __name__ == "__main__":
    unittest.main()
