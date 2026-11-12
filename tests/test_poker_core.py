"""Tests for poker_core pure-python logic and JIT coverage."""

import sys
import unittest
from pathlib import Path

import numpy as np

SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from poker_core import (
    JOKER_ID,
    SUIT_SYMBOLS,
    _evaluate_category5,
    _evaluate_mask,
    calculate_best,
    card_id,
    card_text,
    card_text_console,
    verify_engine,
    warm_up,
)


class TestPokerCoreComprehensive(unittest.TestCase):
    def test_card_id_and_text(self):
        self.assertEqual(card_id("JOKER", ""), JOKER_ID)
        self.assertEqual(card_id("王", ""), JOKER_ID)
        self.assertEqual(card_id("joker", "s"), JOKER_ID)

        # 2 of Spades = 0
        c0 = card_id("2", "S")
        self.assertEqual(c0, 0)
        self.assertEqual(card_text(0), f"{SUIT_SYMBOLS[0]}2")
        self.assertEqual(card_text_console(0), "S2")

        # Ace of Clubs = 12 * 4 + 3 = 51
        c51 = card_id("A", "C")
        self.assertEqual(c51, 51)
        self.assertEqual(card_text(51), f"{SUIT_SYMBOLS[3]}A")
        self.assertEqual(card_text_console(51), "CA")

        # Joker text
        self.assertEqual(card_text(JOKER_ID), "JOKER")
        self.assertEqual(card_text_console(JOKER_ID), "JOKER")

    def test_evaluate_category5_pure_python(self):
        """Test _evaluate_category5.py_func directly for coverage of all categories."""
        eval_fn = getattr(_evaluate_category5, "py_func", _evaluate_category5)

        # Out of bounds / invalid
        self.assertEqual(eval_fn(-1, 0, 1, 2, 3), 0)
        self.assertEqual(eval_fn(0, 1, 2, 3, 53), 0)

        # 8: Five of a Kind (with Joker): 4 Aces + Joker
        # Aces: 48(S), 49(H), 50(D), 51(C)
        self.assertEqual(eval_fn(48, 49, 50, 51, JOKER_ID), 8)

        # 9: Royal Flush (Natural or with Joker): 10, J, Q, K, A of Spades
        # 10=32, J=36, Q=40, K=44, A=48
        self.assertEqual(eval_fn(32, 36, 40, 44, 48), 9)
        # Royal flush with Joker
        self.assertEqual(eval_fn(32, 36, 40, 44, JOKER_ID), 9)

        # 7: Straight Flush: 5, 6, 7, 8, 9 of Hearts
        # 5=13, 6=17, 7=21, 8=25, 9=29
        self.assertEqual(eval_fn(13, 17, 21, 25, 29), 7)
        # Straight flush A-2-3-4-5 (Wheel) of Hearts: A=49, 2=1, 3=5, 4=9, 5=13
        self.assertEqual(eval_fn(49, 1, 5, 9, 13), 7)
        # Wheel straight flush with Joker
        self.assertEqual(eval_fn(49, 1, 5, 9, JOKER_ID), 7)

        # 6: Four of a Kind: 4 Kings + 2 of Hearts
        # K: 44, 45, 46, 47; 2H: 1
        self.assertEqual(eval_fn(44, 45, 46, 47, 1), 6)
        # Three Queens + Joker + 2 of Hearts = Four of a Kind
        # Q: 40, 41, 42
        self.assertEqual(eval_fn(40, 41, 42, JOKER_ID, 1), 6)

        # 5: Full House: 3 Jacks + 2 Tens
        # J: 36, 37, 38; 10: 32, 33
        self.assertEqual(eval_fn(36, 37, 38, 32, 33), 5)
        # Two pairs + Joker = Full House
        self.assertEqual(eval_fn(36, 37, 32, 33, JOKER_ID), 5)

        # 4: Flush: 2, 4, 6, 8, 10 of Diamonds (not straight)
        # D suits: % 4 == 2. 2D=2, 4D=10, 6D=18, 8D=26, 10D=34
        self.assertEqual(eval_fn(2, 10, 18, 26, 34), 4)
        # Flush with Joker
        self.assertEqual(eval_fn(2, 10, 18, 26, JOKER_ID), 4)

        # 3: Straight: 5S, 6H, 7D, 8C, 9S (mixed suits)
        # 5S=12, 6H=17, 7D=22, 8C=27, 9S=28
        self.assertEqual(eval_fn(12, 17, 22, 27, 28), 3)
        # Wheel Straight (A, 2, 3, 4, 5 mixed suits)
        # AS=48, 2H=1, 3D=6, 4C=11, 5S=12
        self.assertEqual(eval_fn(48, 1, 6, 11, 12), 3)
        # Straight with Joker
        self.assertEqual(eval_fn(12, 17, 22, 27, JOKER_ID), 3)
        # Wheel Straight with Joker
        self.assertEqual(eval_fn(48, 1, 6, 11, JOKER_ID), 3)

        # 2: Three of a Kind: 3 Eights + 2S + 3H
        # 8: 24, 25, 26; 2S=0, 3H=5
        self.assertEqual(eval_fn(24, 25, 26, 0, 5), 2)
        # Pair + Joker = Three of a kind
        self.assertEqual(eval_fn(24, 25, 0, 5, JOKER_ID), 2)

        # 1: Two Pair: 2 Jacks + 2 Tens + 2S
        self.assertEqual(eval_fn(36, 37, 32, 33, 0), 1)

        # 0: One Pair: 2 Queens + 2S, 3H, 4D (No win)
        self.assertEqual(eval_fn(40, 41, 0, 5, 10), 0)
        # Joker with high cards = One Pair (No win)
        self.assertEqual(eval_fn(40, 0, 5, 10, JOKER_ID), 0)

        # 0: High Card: 2S, 4H, 6D, 8C, 10S
        self.assertEqual(eval_fn(0, 9, 18, 27, 32), 0)

    def test_evaluate_mask_pure_python(self):
        """Test _evaluate_mask.py_func directly for full branch coverage (draw 0, 1, 2, 3, 4, 5)."""
        eval_mask = getattr(_evaluate_mask, "py_func", _evaluate_mask)
        initial = np.array(
            [card_id("A", "S"), card_id("K", "S"), card_id("Q", "S"), card_id("J", "S"), card_id("10", "S")],
            dtype=np.int16,
        )

        # Draw 0 (mask 31)
        tot, pay, _win, _cnt = eval_mask(initial, 31, True)
        self.assertEqual(tot, 1)
        self.assertGreater(pay, 0)

        # Draw 1 (mask 15)
        tot, _pay, _win, _cnt = eval_mask(initial, 15, True)
        self.assertEqual(tot, 48)

        # Draw 2 (mask 7)
        tot, pay, _win, _cnt = eval_mask(initial, 7, True)
        self.assertEqual(tot, 48 * 47 // 2)

        # Non-standard mode branch
        tot_ns, _, _, _ = eval_mask(initial, 15, False)
        self.assertEqual(tot_ns, 49)

    def test_calculate_best_validations(self):
        # Invalid lengths and constraints
        with self.assertRaises(ValueError):
            calculate_best([0, 1, 2, 3])
        with self.assertRaises(ValueError):
            calculate_best([0, 0, 1, 2, 3])
        with self.assertRaises(ValueError):
            calculate_best([JOKER_ID, JOKER_ID, 1, 2, 3])
        with self.assertRaises(ValueError):
            calculate_best([-5, 1, 2, 3, 4])
        with self.assertRaises(ValueError):
            calculate_best([100, 1, 2, 3, 4])

        # Valid run
        best, all_results = calculate_best(
            [card_id("A", "S"), card_id("K", "S"), card_id("Q", "S"), card_id("J", "S"), card_id("10", "S")]
        )
        self.assertEqual(best.mask, 31)
        self.assertEqual(len(all_results), 32)

    def test_warm_up_and_verify(self):
        verify_engine()
        warm_up()


if __name__ == "__main__":
    unittest.main()
