import sys
from pathlib import Path
SRC_DIR = Path(__file__).resolve().parents[1] / 'src'
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import contextlib
import io
import unittest

from settlement import SettlementReader, SettlementManager


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
                if current_state in ('START_BET', 'HOLD_CARDS'):
                    mgr.reset_round()
                elif current_state == 'RESULT':
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
        frames = [('RESULT', i * .25, amount) for i, amount in enumerate(
            [20, 60, 280, 40, 400, 400, 400, 400, 400, 400, 400])]
        coins, writes, _ = self.replay(frames)
        self.assertEqual((coins, writes), (760, [760]))

    def test_zero_is_retried_and_not_clicked_away(self):
        self.assertEqual(self.replay([('RESULT', 0, 0)])[:], (360, [], []))
        frames = [('RESULT', i * .25, 0 if i < 7 else 400) for i in range(12)]
        self.assertEqual(self.replay(frames)[:2], (760, [760]))

    def test_unknown_does_not_duplicate_credit(self):
        frames = [('RESULT', i * .25, 400) for i in range(11)]
        frames += [('UNKNOWN', 3, 0), ('RESULT', 3.25, 400)]
        self.assertEqual(self.replay(frames)[:2], (760, [760]))

    def test_next_round_can_credit_again(self):
        for state in ('START_BET', 'HOLD_CARDS'):
            frames = [('RESULT', i * .25, 400) for i in range(11)]
            frames += [(state, 3, 0)]
            frames += [('RESULT', 4 + i * .25, 200) for i in range(11)]
            self.assertEqual(self.replay(frames)[:2], (960, [760, 960]))

    def test_timeout_for_zero_or_unstable_values(self):
        for values in ([0] * 33, [200, 400] * 17):
            reader = SettlementReader()
            with self.assertRaises(RuntimeError):
                for i, amount in enumerate(values):
                    self.assertIsNone(reader.observe(amount, i * .25))

    def test_animation_samples_cannot_satisfy_stability(self):
        reader = SettlementReader()
        for i in range(8):
            self.assertIsNone(reader.observe(200, i * .25))
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
        self.assertEqual(decision, 'challenge')
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


if __name__ == '__main__':
    unittest.main()
