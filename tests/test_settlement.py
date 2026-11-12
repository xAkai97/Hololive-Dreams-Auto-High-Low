import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import contextlib
import io
import unittest

from settlement import (
    SettlementManager,
    SettlementReader,
    is_valid_hand_payout,
    is_valid_settlement_amount,
    validate_and_correct_payout,
)


class SettlementTests(unittest.TestCase):
    def replay(self, frames):
        writes, clicks = [], []
        mgr = SettlementManager(
            settlement_reader=SettlementReader(),
            save_data_fn=lambda c, f, *a: writes.append(c),
        )
        daily_coins = 360
        daily_fails = 0

        with contextlib.redirect_stdout(io.StringIO()):
            for current_state, now, amount in frames:
                if current_state in ("START_BET", "HOLD_CARDS"):
                    mgr.reset_round()
                elif current_state == "RESULT":
                    daily_coins, can_proceed = mgr.process_result(
                        amount=amount,
                        now=now,
                        daily_coins=daily_coins,
                        daily_fails=daily_fails,
                    )
                    if can_proceed:
                        clicks.append(True)

        return daily_coins, writes, clicks

    def test_count_up_then_stable_400(self):
        frames = [
            ("RESULT", i * 0.25, amount)
            for i, amount in enumerate([20, 60, 280, 40, 400, 400, 400, 400, 400, 400, 400])
        ]
        coins, writes, _ = self.replay(frames)
        self.assertEqual((coins, writes), (760, [760]))

    def test_zero_is_retried_and_not_clicked_away(self):
        self.assertEqual(self.replay([("RESULT", 0, 0)])[:], (360, [], []))
        frames = [("RESULT", i * 0.25, 0 if i < 7 else 400) for i in range(12)]
        self.assertEqual(self.replay(frames)[:2], (760, [760]))

    def test_unknown_does_not_duplicate_credit(self):
        frames = [("RESULT", i * 0.25, 400) for i in range(11)]
        frames += [("UNKNOWN", 3, 0), ("RESULT", 3.25, 400)]
        self.assertEqual(self.replay(frames)[:2], (760, [760]))

    def test_next_round_can_credit_again(self):
        for state in ("START_BET", "HOLD_CARDS"):
            frames = [("RESULT", i * 0.25, 400) for i in range(11)]
            frames += [(state, 3, 0)]
            frames += [("RESULT", 4 + i * 0.25, 200) for i in range(11)]
            self.assertEqual(self.replay(frames)[:2], (960, [760, 960]))

    def test_timeout_for_zero_or_unstable_values(self):
        for values in ([0] * 33, [200, 400] * 17):
            reader = SettlementReader()
            with self.assertRaises(RuntimeError):
                for i, amount in enumerate(values):
                    self.assertIsNone(reader.observe(amount, i * 0.25))

    def test_animation_samples_cannot_satisfy_stability(self):
        reader = SettlementReader()
        for i in range(8):
            self.assertIsNone(reader.observe(200, i * 0.25))
        for now in (2, 2.25, 2.5):
            self.assertIsNone(reader.observe(400, now))
        self.assertEqual(reader.observe(400, 2.75), 400)

    def test_custom_ticket_cost(self):
        reported = []
        mgr = SettlementManager()
        # 10 fails with ticket_cost=100 -> fee = 1000. Earned = 400. Profit = 400 - 1000 = -600
        with contextlib.redirect_stdout(io.StringIO()):
            for i in range(12):
                mgr.process_result(
                    amount=400,
                    now=i * 0.25,
                    daily_coins=0,
                    daily_fails=10,
                    on_stats_update=lambda c, f, p: reported.append((c, f, p)),
                    ticket_cost=100,
                )
        self.assertEqual(reported, [(400, 10, -600)])

    def test_max_payout_auto_settle_after_challenge_credits_without_error(self):
        from strategies.max_profit import MaxProfitStrategy

        strat = MaxProfitStrategy()
        # Strategy decides to challenge 6000 -> 12000
        decision = strat.decide(current_cashout=6000, next_reward=12000, win_rate=0.75, daily_coins=4200)
        self.assertEqual(decision, "challenge")
        self.assertIsNone(strat.expected_cash)

        # Game hits max payout and lands directly on RESULT with 12000
        mgr = SettlementManager(save_data_fn=lambda *a: None)
        coins = 4200
        with contextlib.redirect_stdout(io.StringIO()):
            for i in range(12):
                coins, can_proceed = mgr.process_result(
                    amount=12000,
                    now=i * 0.25,
                    daily_coins=coins,
                    daily_fails=15,
                    strategy=strat,
                )
        self.assertTrue(can_proceed)
        self.assertEqual(coins, 16200)

    def test_is_valid_settlement_amount(self):
        self.assertFalse(is_valid_settlement_amount(160015))
        self.assertFalse(is_valid_settlement_amount(0))
        self.assertFalse(is_valid_settlement_amount(-200))
        self.assertFalse(is_valid_settlement_amount(70000))
        self.assertFalse(is_valid_settlement_amount("1600"))
        self.assertTrue(is_valid_settlement_amount(1600))
        self.assertTrue(is_valid_settlement_amount(200))
        self.assertTrue(is_valid_settlement_amount(12800))
        self.assertTrue(is_valid_settlement_amount(50))

    def test_impossible_amount_rejected_by_reader(self):
        reader = SettlementReader(timeout=8.0)
        # Observing impossible amount (160015) 10 times does not produce candidate
        for i in range(10):
            self.assertIsNone(reader.observe(160015, i * 0.25))
        self.assertIsNone(reader.candidate)

    def test_auto_recovery_uses_expected_cashout_on_timeout(self):
        reader = SettlementReader(timeout=2.0)
        mgr = SettlementManager(settlement_reader=reader, recovery_mode="auto")
        mgr.expected_cashout = 1600

        coins = 1200
        with contextlib.redirect_stdout(io.StringIO()):
            # Simulate 10 frames of impossible OCR noise (160015) over 2.5s
            for i in range(11):
                coins, can_proceed = mgr.process_result(
                    amount=160015,
                    now=i * 0.25,
                    daily_coins=coins,
                    daily_fails=5,
                )
                if can_proceed:
                    break
        self.assertTrue(can_proceed)
        self.assertEqual(coins, 2800)  # 1200 + 1600

    def test_manual_recovery_invokes_prompt_callback(self):
        reader = SettlementReader(timeout=2.0)
        prompt_called = []

        def mock_prompt(expected, observed):
            prompt_called.append((expected, observed))
            return 1600

        mgr = SettlementManager(
            settlement_reader=reader,
            recovery_mode="manual",
            on_prompt_settlement=mock_prompt,
        )
        mgr.expected_cashout = 1600

        coins = 1200
        with contextlib.redirect_stdout(io.StringIO()):
            for i in range(11):
                coins, can_proceed = mgr.process_result(
                    amount=160015,
                    now=i * 0.25,
                    daily_coins=coins,
                    daily_fails=5,
                )
                if can_proceed:
                    break
        self.assertTrue(can_proceed)
        self.assertEqual(prompt_called, [(1600, 160015)])
        self.assertEqual(coins, 2800)

    def test_is_valid_hand_payout(self):
        # Base Flush = 700 (max hand payout = 11200)
        self.assertTrue(is_valid_hand_payout(700, 700))
        self.assertTrue(is_valid_hand_payout(1400, 700))
        self.assertTrue(is_valid_hand_payout(2800, 700))
        self.assertTrue(is_valid_hand_payout(5600, 700))
        self.assertTrue(is_valid_hand_payout(11200, 700))
        self.assertFalse(is_valid_hand_payout(22400, 700))
        self.assertFalse(is_valid_hand_payout(1600, 700))
        self.assertFalse(is_valid_hand_payout(3200, 700))
        self.assertFalse(is_valid_hand_payout(2100, 700))
        self.assertFalse(is_valid_hand_payout(0, 700))

        # Base Two Pair / Straight = 400 (max hand payout = 12800)
        self.assertTrue(is_valid_hand_payout(400, 400))
        self.assertTrue(is_valid_hand_payout(800, 400))
        self.assertTrue(is_valid_hand_payout(1600, 400))
        self.assertTrue(is_valid_hand_payout(3200, 400))
        self.assertTrue(is_valid_hand_payout(12800, 400))
        self.assertFalse(is_valid_hand_payout(25600, 400))
        self.assertFalse(is_valid_hand_payout(700, 400))
        self.assertFalse(is_valid_hand_payout(1400, 400))

    def test_validate_and_correct_payout(self):
        # Valid amount untouched
        amt, valid, corr = validate_and_correct_payout(11200, 700)
        self.assertEqual((amt, valid, corr), (11200, True, False))

        # Missing trailing zero corrected
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            amt, valid, corr = validate_and_correct_payout(1120, 700)
        self.assertEqual((amt, valid, corr), (11200, True, True))
        self.assertIn("Payout validation failed", out.getvalue())
        self.assertIn("Corrected payout", out.getvalue())

        # Trailing noise digit corrected
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            amt, valid, corr = validate_and_correct_payout(28005, 700)
        self.assertEqual((amt, valid, corr), (2800, True, True))

        # Expected cashout match when scanned amount is wrong
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            amt, valid, corr = validate_and_correct_payout(9999, 700, expected=5600)
        self.assertEqual((amt, valid, corr), (5600, True, True))

        # Predicted from (base_prize, win_count) when both result screen OCR and expected are missed
        amt, valid, corr = validate_and_correct_payout(0, 700, expected=None, win_count=4)
        self.assertEqual((amt, valid, corr), (11200, True, True))

        # Edit-distance-1 single digit OCR substitution (e.g. 11280 -> 11200)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            amt, valid, corr = validate_and_correct_payout(11280, 700)
        self.assertEqual((amt, valid, corr), (11200, True, True))

    def test_credit_payout_still_adds_valid_settlement_when_base_prize_stale(self):
        mgr = SettlementManager(recovery_mode="auto", base_prize=200)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            coins = mgr.credit_payout(earned=2000, daily_coins=5000, daily_fails=0, base_prize=200)
        self.assertEqual(coins, 7000)
        self.assertIn("Payout validation failed", out.getvalue())

    def test_settlement_manager_corrects_invalid_power_of_two_payout(self):
        reader = SettlementReader(timeout=2.0)
        mgr = SettlementManager(settlement_reader=reader, recovery_mode="auto", base_prize=700)
        coins = 1000
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            for i in range(11):
                coins, can_proceed = mgr.process_result(
                    amount=1120,
                    now=i * 0.25,
                    daily_coins=coins,
                    daily_fails=0,
                    base_prize=700,
                )
                if can_proceed:
                    break
        self.assertTrue(can_proceed)
        self.assertEqual(coins, 12200)  # 1000 + 11200
        self.assertIn("Payout validation failed", out.getvalue())
        self.assertIn("Corrected payout", out.getvalue())


if __name__ == "__main__":
    unittest.main()
