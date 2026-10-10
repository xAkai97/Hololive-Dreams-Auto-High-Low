import unittest
from src.auto_bot import HighLowCounter, get_card_point_value
from src.poker_core import _evaluate_category5


class DummyCard:
    def __init__(self, card_id, rank="A", suit="S"):
        self.card_id = card_id
        self.rank = rank
        self.suit = suit
        self.rank_score = 0.95
        self.rank_margin = 0.30


class TestDealReconciliation(unittest.TestCase):
    def test_deck_counter_reconciliation_on_deal_change(self):
        counter = HighLowCounter()
        self.assertEqual(counter.total_cards, 52)

        # Initial hand dealt: 5 cards
        initial_cards = [
            DummyCard(0, "2", "S"),
            DummyCard(4, "3", "S"),
            DummyCard(8, "4", "S"),
            DummyCard(12, "5", "S"),
            DummyCard(16, "6", "S"),
        ]
        values1 = [get_card_point_value(c) for c in initial_cards]
        counter.remove_cards(values1)
        self.assertEqual(counter.total_cards, 47)

        # Deal changed on screen mid-round (e.g. animation stabilized or user resync)
        # Without counter.reset(), removing the new 5 cards would double-deduct to 42.
        counter.reset()
        self.assertEqual(counter.total_cards, 52)

        new_cards = [
            DummyCard(1, "2", "H"),
            DummyCard(5, "3", "H"),
            DummyCard(9, "4", "H"),
            DummyCard(13, "5", "H"),
            DummyCard(17, "6", "H"),
        ]
        values2 = [get_card_point_value(c) for c in new_cards]
        counter.remove_cards(values2)
        self.assertEqual(counter.total_cards, 47)

    def test_evaluate_category5_boundary_protection(self):
        # Invalid / out of bounds card IDs should safely return 0 without raising exceptions
        cat_negative = _evaluate_category5(-1, 0, 1, 2, 3)
        self.assertEqual(cat_negative, 0)

        cat_overflow = _evaluate_category5(99, 0, 1, 2, 3)
        self.assertEqual(cat_overflow, 0)


if __name__ == "__main__":
    unittest.main()
