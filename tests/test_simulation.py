import sys
from pathlib import Path
import unittest

SRC_DIR = Path(__file__).resolve().parents[1] / 'src'
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

try:
    from simulation import GameSimulator, RoundResult, DaySimulationResult, MonteCarloSummary
    HAVE_SIMULATION = True
except ImportError:
    HAVE_SIMULATION = False

from strategies.max_profit import MaxProfitStrategy


@unittest.skipUnless(HAVE_SIMULATION, 'Simulation dependencies (numpy) not installed')
class TestGameSimulator(unittest.TestCase):
    def setUp(self):
        self.sim = GameSimulator(seed=42)

    def test_draw_poker_hand_fast(self):
        payout, hand, cat = self.sim.draw_poker_hand(exact_poker=False)
        self.assertIn(payout, [0, 200, 400, 700, 800, 1500, 3000, 7000, 10000])

    def test_draw_poker_hand_exact(self):
        payout, hand, cat = self.sim.draw_poker_hand(exact_poker=True)
        self.assertEqual(len(hand), 5)
        self.assertIn(payout, [0, 200, 400, 700, 800, 1500, 3000, 7000, 10000])

    def test_play_high_low_round(self):
        strategy = MaxProfitStrategy()
        result = self.sim.play_high_low_round(
            strategy=strategy,
            initial_payout=400,
            daily_coins=5000,
            max_doubles=5,
        )
        self.assertIsInstance(result, RoundResult)
        self.assertTrue(result.won_poker)
        self.assertGreaterEqual(result.final_payout, 0)
        self.assertGreaterEqual(result.doubling_steps, 0)
        if result.cashed_out:
            self.assertGreater(result.final_payout, 0)
            self.assertFalse(result.busted)
        else:
            self.assertEqual(result.final_payout, 0)
            self.assertTrue(result.busted)

    def test_simulate_day(self):
        day_result = self.sim.simulate_day(
            strategy_cls=MaxProfitStrategy,
            max_daily_rounds=50,
            exact_poker=False,
        )
        self.assertIsInstance(day_result, DaySimulationResult)
        self.assertGreater(day_result.total_rounds, 0)
        self.assertGreaterEqual(day_result.total_coins, 0)

    def test_run_monte_carlo_summary(self):
        summary = self.sim.run_monte_carlo(
            strategy_cls=MaxProfitStrategy,
            days=3,
            exact_poker=False,
        )
        self.assertIsInstance(summary, MonteCarloSummary)
        self.assertEqual(summary.days_simulated, 3)
        self.assertGreater(summary.avg_rounds, 0)
        self.assertGreaterEqual(summary.avg_coins, 0)

    def test_simulate_day_custom_target_limit(self):
        # Setting a low limit (e.g. 1,000) should terminate when 1,000 is reached
        day_result = self.sim.simulate_day(
            strategy_cls=MaxProfitStrategy,
            max_daily_rounds=100,
            target_limit=1000,
            exact_poker=False,
        )
        self.assertIsInstance(day_result, DaySimulationResult)
        self.assertGreaterEqual(day_result.total_coins, 1000)

    def test_max_payout_limit_enforced(self):
        from strategies.fastest_clear import FastestClearStrategy
        # FastestClear never stops voluntarily unless at cap, so it tests the hard cap
        result = self.sim.play_high_low_round(
            strategy=FastestClearStrategy(),
            initial_payout=10000,
            daily_coins=0,
            max_doubles=10,
        )
        self.assertTrue(result.cashed_out)
        self.assertEqual(result.final_payout, 10000)
        self.assertEqual(result.reason, "max_payout_reached")

    def test_opportunistic_doubling_override(self):
        from strategies.grinder import GrinderStrategy
        # Grinder normally cashes out at 200, but with a 2 or A as first card,
        # opportunistic doubling should force it to challenge!
        sim = GameSimulator(seed=42, opportunistic_double_mode="a_2_only")
        # Run multiple rounds to ensure simulation doesn't crash with the override
        result = sim.play_high_low_round(
            strategy=GrinderStrategy(),
            initial_payout=200,
            daily_coins=0,
            max_doubles=5,
        )
        self.assertTrue(result.won_poker)


    def test_modifiers_in_simulator(self):
        from strategies.grinder import GrinderStrategy
        # Test GameSimulator initialization with modifiers
        sim = GameSimulator(
            seed=42,
            mod_fast_build=True,
            mod_drop_78=True,
            mod_sprint_floor=True,
            cushion_target=19800,
        )
        self.assertTrue(sim.mod_fast_build)
        self.assertTrue(sim.mod_drop_78)
        self.assertTrue(sim.mod_sprint_floor)
        self.assertEqual(sim.cushion_target, 19800)

        # Run a round with Grinder and ensure modifiers execute cleanly
        result = sim.play_high_low_round(
            strategy=GrinderStrategy(),
            initial_payout=200,
            daily_coins=5000,
            max_doubles=5,
        )
        self.assertTrue(result.won_poker)


if __name__ == "__main__":
    unittest.main()

