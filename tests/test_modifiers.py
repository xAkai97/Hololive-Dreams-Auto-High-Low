"""Unit tests for Strategy Modifiers and Overrides Engine."""
import unittest
import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from strategies.modifiers import apply_strategy_modifiers


class TestStrategyModifiers(unittest.TestCase):
    def test_stop_never_overridden(self):
        dec, reason = apply_strategy_modifiers(
            decision="stop",
            card_val=14,
            current_cashout=5000,
            next_reward=10000,
            daily_coins=5000,
            mod_fast_build=True,
            mod_drop_78=True,
            mod_sprint_floor=True,
        )
        self.assertEqual(dec, "stop")
        self.assertIsNone(reason)

    def test_mod_drop_78(self):
        # 1. 7 or 8 during cushion phase (< 19,800) should drop
        dec, reason = apply_strategy_modifiers(
            decision="challenge",
            card_val=7,
            current_cashout=800,
            next_reward=1600,
            daily_coins=5000,
            cushion_target=19800,
            mod_drop_78=True,
        )
        self.assertEqual(dec, "cashout")
        self.assertEqual(reason, "mod_drop_78")

        dec8, reason8 = apply_strategy_modifiers(
            decision="challenge",
            card_val=8,
            current_cashout=800,
            next_reward=1600,
            daily_coins=10000,
            cushion_target=19800,
            mod_drop_78=True,
        )
        self.assertEqual(dec8, "cashout")
        self.assertEqual(reason8, "mod_drop_78")

        # 2. When disabled, should remain challenge
        dec_off, reason_off = apply_strategy_modifiers(
            decision="challenge",
            card_val=7,
            current_cashout=800,
            next_reward=1600,
            daily_coins=5000,
            mod_drop_78=False,
        )
        self.assertEqual(dec_off, "challenge")
        self.assertIsNone(reason_off)

        # 3. Card is not 7 or 8 (e.g., 9)
        dec_9, _ = apply_strategy_modifiers(
            decision="challenge",
            card_val=9,
            current_cashout=800,
            next_reward=1600,
            daily_coins=5000,
            mod_drop_78=True,
        )
        self.assertEqual(dec_9, "challenge")

        # 4. In sprint phase (daily_coins >= cushion_target), drop_78 does not force cashout
        dec_sprint, _ = apply_strategy_modifiers(
            decision="challenge",
            card_val=7,
            current_cashout=800,
            next_reward=1600,
            daily_coins=19850,
            cushion_target=19800,
            mod_drop_78=True,
        )
        self.assertEqual(dec_sprint, "challenge")

    def test_mod_fast_build(self):
        # 1. Strategy wants cashout at 800 (next 1600), total would be 5000+1600=6600 <= 19800
        dec, reason = apply_strategy_modifiers(
            decision="cashout",
            card_val=6,
            current_cashout=800,
            next_reward=1600,
            daily_coins=5000,
            cushion_target=19800,
            mod_fast_build=True,
        )
        self.assertEqual(dec, "challenge")
        self.assertEqual(reason, "mod_fast_build")

        # 2. Next reward exceeds cushion target (e.g. 19000 + 1600 = 20600 > 19800) -> do NOT force double
        dec_over, reason_over = apply_strategy_modifiers(
            decision="cashout",
            card_val=6,
            current_cashout=800,
            next_reward=1600,
            daily_coins=19000,
            cushion_target=19800,
            mod_fast_build=True,
        )
        self.assertEqual(dec_over, "cashout")
        self.assertIsNone(reason_over)

        # 3. When disabled, stays cashout
        dec_off, reason_off = apply_strategy_modifiers(
            decision="cashout",
            card_val=6,
            current_cashout=800,
            next_reward=1600,
            daily_coins=5000,
            mod_fast_build=False,
        )
        self.assertEqual(dec_off, "cashout")
        self.assertIsNone(reason_off)

    def test_mod_sprint_floor(self):
        # In sprint phase (daily_coins >= cushion_target), if current_cashout < 11200, push forward
        dec, reason = apply_strategy_modifiers(
            decision="cashout",
            card_val=5,
            current_cashout=10000,
            next_reward=20000,
            daily_coins=19800,
            cushion_target=19800,
            mod_sprint_floor=True,
        )
        self.assertEqual(dec, "challenge")
        self.assertEqual(reason, "mod_sprint_floor")

        # If current_cashout is already >= 11200, allows cashout
        dec_high, reason_high = apply_strategy_modifiers(
            decision="cashout",
            card_val=5,
            current_cashout=12800,
            next_reward=25600,
            daily_coins=19800,
            cushion_target=19800,
            mod_sprint_floor=True,
        )
        self.assertEqual(dec_high, "cashout")
        self.assertIsNone(reason_high)

        # In cushion phase (< cushion_target), sprint floor does not activate
        dec_cush, _ = apply_strategy_modifiers(
            decision="cashout",
            card_val=5,
            current_cashout=10000,
            next_reward=20000,
            daily_coins=10000,
            cushion_target=19800,
            mod_sprint_floor=True,
        )
        self.assertEqual(dec_cush, "cashout")

    def test_opportunistic_cards(self):
        # A (14) and 2:
        dec_a, reason_a = apply_strategy_modifiers(
            decision="cashout",
            card_val=14,
            current_cashout=800,
            next_reward=1600,
            daily_coins=10000,
            target_limit=20000,
            opp_a2=True,
        )
        self.assertEqual(dec_a, "challenge")
        self.assertEqual(reason_a, "opportunistic_card")

        # Exceeding target limit should block opportunistic doubling
        dec_limit, reason_limit = apply_strategy_modifiers(
            decision="cashout",
            card_val=14,
            current_cashout=800,
            next_reward=1600,
            daily_coins=19000,
            target_limit=20000,
            opp_a2=True,
        )
        self.assertEqual(dec_limit, "cashout")
        self.assertIsNone(reason_limit)


    def test_mod_drop_6789(self):
        for rank in (6, 7, 8, 9):
            dec, reason = apply_strategy_modifiers(
                decision="challenge",
                card_val=rank,
                current_cashout=800,
                next_reward=1600,
                daily_coins=5000,
                cushion_target=19800,
                mod_drop_6789=True,
            )
            self.assertEqual(dec, "cashout")
            self.assertEqual(reason, "mod_drop_6789")

        # 5 and 10 should not drop on mod_drop_6789
        for safe_rank in (5, 10):
            dec, reason = apply_strategy_modifiers(
                decision="challenge",
                card_val=safe_rank,
                current_cashout=800,
                next_reward=1600,
                daily_coins=5000,
                cushion_target=19800,
                mod_drop_6789=True,
            )
            self.assertEqual(dec, "challenge")
            self.assertIsNone(reason)

    def test_mod_drop_8(self):
        # 8 drops out
        dec8, reason8 = apply_strategy_modifiers(
            decision="challenge",
            card_val=8,
            current_cashout=800,
            next_reward=1600,
            daily_coins=5000,
            cushion_target=19800,
            mod_drop_8=True,
        )
        self.assertEqual(dec8, "cashout")
        self.assertEqual(reason8, "mod_drop_8")

        # 7 and 9 should NOT drop when only mod_drop_8 is active
        for safe_rank in (7, 9):
            dec, reason = apply_strategy_modifiers(
                decision="challenge",
                card_val=safe_rank,
                current_cashout=800,
                next_reward=1600,
                daily_coins=5000,
                cushion_target=19800,
                mod_drop_8=True,
            )
            self.assertEqual(dec, "challenge")
            self.assertIsNone(reason)

    def test_mod_free_roll(self):
        # Initial payouts <= 200 force challenge
        for cashout in (50, 100, 200):
            dec, reason = apply_strategy_modifiers(
                decision="cashout",
                card_val=7,
                current_cashout=cashout,
                next_reward=cashout * 2,
                daily_coins=5000,
                target_limit=20000,
                mod_free_roll=True,
            )
            self.assertEqual(dec, "challenge")
            self.assertEqual(reason, "mod_free_roll")

        # Payout > 200 (e.g. 400) does not force challenge
        dec_high, reason_high = apply_strategy_modifiers(
            decision="cashout",
            card_val=7,
            current_cashout=400,
            next_reward=800,
            daily_coins=5000,
            target_limit=20000,
            mod_free_roll=True,
        )
        self.assertEqual(dec_high, "cashout")
        self.assertIsNone(reason_high)

        # Exceeding target limit blocks free roll
        dec_limit, reason_limit = apply_strategy_modifiers(
            decision="cashout",
            card_val=7,
            current_cashout=200,
            next_reward=400,
            daily_coins=19800,
            target_limit=20000,
            mod_free_roll=True,
        )
        self.assertEqual(dec_limit, "cashout")
        self.assertIsNone(reason_limit)

    def test_mod_mega_sprint(self):
        # In sprint phase (daily >= cushion), cashout < 12800 is forced to challenge
        dec, reason = apply_strategy_modifiers(
            decision="cashout",
            card_val=5,
            current_cashout=11200,
            next_reward=22400,
            daily_coins=19800,
            cushion_target=19800,
            mod_mega_sprint=True,
        )
        self.assertEqual(dec, "challenge")
        self.assertEqual(reason, "mod_mega_sprint")

        # If current_cashout >= 12800, cashout is allowed
        dec_high, reason_high = apply_strategy_modifiers(
            decision="cashout",
            card_val=5,
            current_cashout=12800,
            next_reward=25600,
            daily_coins=19800,
            cushion_target=19800,
            mod_mega_sprint=True,
        )
        self.assertEqual(dec_high, "cashout")
        self.assertIsNone(reason_high)

    def test_opportunistic_cards_expanded(self):
        pairs = [
            ((5, 11), {"opp_5j": True}),
            ((6, 10), {"opp_610": True}),
            ((7, 9), {"opp_79": True}),
            ((8,), {"opp_8": True}),
        ]
        for ranks, kw in pairs:
            for rank in ranks:
                dec, reason = apply_strategy_modifiers(
                    decision="cashout",
                    card_val=rank,
                    current_cashout=800,
                    next_reward=1600,
                    daily_coins=5000,
                    target_limit=20000,
                    **kw,
                )
                self.assertEqual(dec, "challenge")
                self.assertEqual(reason, "opportunistic_card")

                # If flag is False, stays cashout
                off_kw = {k: False for k in kw}
                dec_off, reason_off = apply_strategy_modifiers(
                    decision="cashout",
                    card_val=rank,
                    current_cashout=800,
                    next_reward=1600,
                    daily_coins=5000,
                    target_limit=20000,
                    **off_kw,
                )
                self.assertEqual(dec_off, "cashout")
                self.assertIsNone(reason_off)

    def test_debug_logging(self):
        try:
            import auto_bot
        except ImportError:
            self.skipTest("auto_bot dependencies (numpy/cv2) not installed in environment")
        from unittest.mock import patch
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            test_debug_file = Path(tmpdir) / "debug_log.txt"
            with patch.object(auto_bot, "DEBUG_LOG_FILE", test_debug_file):
                # When debug_logging is False
                auto_bot._debug_logging_enabled = None
                with patch.object(auto_bot, "load_config", return_value={"debug_logging": False}):
                    auto_bot.log_debug("This should not be written")
                    self.assertFalse(test_debug_file.exists())

                # When debug_logging is True
                auto_bot._debug_logging_enabled = None
                with patch.object(auto_bot, "load_config", return_value={"debug_logging": True}):
                    auto_bot.log_debug("This should be written")
                    self.assertTrue(test_debug_file.exists())
                    content = test_debug_file.read_text(encoding="utf-8")
                    self.assertIn("This should be written", content)
                auto_bot._debug_logging_enabled = None

    def test_defensive_bailout_suppresses_contradictory_card_override(self):
        # Even if opp_8 is True, mod_drop_8 or mod_drop_6789 or mod_drop_78 must suppress doubling on 8
        dec, reason = apply_strategy_modifiers(
            decision="cashout",
            card_val=8,
            current_cashout=800,
            next_reward=1600,
            daily_coins=5000,
            cushion_target=19800,
            target_limit=20000,
            opp_8=True,
            mod_drop_8=True,
        )
        self.assertEqual(dec, "cashout")
        self.assertIsNone(reason)

        # 7/9 override suppressed by mod_drop_78
        dec7, reason7 = apply_strategy_modifiers(
            decision="cashout",
            card_val=7,
            current_cashout=800,
            next_reward=1600,
            daily_coins=5000,
            cushion_target=19800,
            target_limit=20000,
            opp_79=True,
            mod_drop_78=True,
        )
        self.assertEqual(dec7, "cashout")
        self.assertIsNone(reason7)

        # 6/10 override for card 6 suppressed by mod_drop_6789
        dec6, reason6 = apply_strategy_modifiers(
            decision="cashout",
            card_val=6,
            current_cashout=800,
            next_reward=1600,
            daily_coins=5000,
            cushion_target=19800,
            target_limit=20000,
            opp_610=True,
            mod_drop_6789=True,
        )
        self.assertEqual(dec6, "cashout")
        self.assertIsNone(reason6)


if __name__ == "__main__":
    unittest.main()

