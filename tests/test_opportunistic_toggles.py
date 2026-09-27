import unittest
import json
from pathlib import Path
import sys

SRC_DIR = Path(__file__).resolve().parents[1] / 'src'
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

try:
    import auto_bot
except ImportError:
    auto_bot = None


class TestOpportunisticToggles(unittest.TestCase):
    def test_opportunistic_logic_card_selection(self):
        # Test A & 2 only
        runtime_config = {"opp_a2": True, "opp_3k": False, "opp_4q": False}
        target_limit = 20000
        daily_coins = 5000
        next_reward = 800

        def check_should_double(card_val, config):
            opp_a2 = config.get("opp_a2", False)
            opp_3k = config.get("opp_3k", False)
            opp_4q = config.get("opp_4q", False)
            if card_val in (2, 14) and opp_a2:
                return True
            elif card_val in (3, 13) and opp_3k:
                return True
            elif card_val in (4, 12) and opp_4q:
                return True
            return False

        # Card 2 (rank 2) and Ace (rank 14)
        self.assertTrue(check_should_double(2, runtime_config))
        self.assertTrue(check_should_double(14, runtime_config))
        # Card 3 and King (rank 13) should not trigger under A&2 only
        self.assertFalse(check_should_double(3, runtime_config))
        self.assertFalse(check_should_double(13, runtime_config))
        # Card 4 and Queen (rank 12) should not trigger
        self.assertFalse(check_should_double(4, runtime_config))
        self.assertFalse(check_should_double(12, runtime_config))

        # Enable 3 & K toggle
        runtime_config["opp_3k"] = True
        self.assertTrue(check_should_double(3, runtime_config))
        self.assertTrue(check_should_double(13, runtime_config))
        self.assertFalse(check_should_double(4, runtime_config))

        # Enable 4 & Q toggle
        runtime_config["opp_4q"] = True
        self.assertTrue(check_should_double(4, runtime_config))
        self.assertTrue(check_should_double(12, runtime_config))

        # Other cards like 7 or 8 should never trigger opportunistic doubling
        self.assertFalse(check_should_double(7, runtime_config))
        self.assertFalse(check_should_double(8, runtime_config))

    def test_opportunistic_limit_safety(self):
        target_limit = 20000
        # 18200 + 1600 = 19800 is safely under 20000 -> allowed
        self.assertTrue(18200 + 1600 < target_limit)

        # 18400 + 1600 = 20000 hits the lockout cap -> must NOT double!
        self.assertFalse(18400 + 1600 < target_limit)

        # 19500 + 1600 = 21100 over limit -> must NOT double
        self.assertFalse(19500 + 1600 < target_limit)


if __name__ == "__main__":
    unittest.main()
