"""Offline simulation and Monte Carlo backtesting engine for Hololive Dreams casino mini-game.

Simulates:
1. Video Poker 5-card draw with 1 Joker (53-card deck), evaluating optimal holds via poker_core.
2. High-Low doubling with 52-card remaining deck tracking and strict tie-loss rules.
3. Daily bankroll progression up to the 20,000 cap (including cap overflow).
"""
from __future__ import annotations

import random
import sys
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, Type
import numpy as np

# Ensure src is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from poker_core import (
    JOKER_ID,
    PRIZES,
    calculate_best,
    _evaluate_category5,
    ENTRY_FEE,
)
from auto_bot import HighLowCounter
from strategies.base import BaseStrategy
from strategies import STRATEGY_REGISTRY, apply_strategy_modifiers


# Empirical Joker Poker payout distribution under optimal play (payout, probability)
# Source: Standard 53-card Joker Wild (Two Pair or Better) optimal paytable
POKER_PAYOUT_WEIGHTS: tuple[tuple[int, float], ...] = (
    (0, 0.5480),       # No win / One pair
    (200, 0.2100),     # Two Pair
    (200, 0.1350),     # Three of a Kind
    (400, 0.0420),     # Straight
    (700, 0.0360),     # Flush
    (800, 0.0210),     # Full House
    (1500, 0.0065),    # Four of a Kind
    (3000, 0.0010),    # Straight Flush
    (7000, 0.0004),    # Five of a Kind
    (10000, 0.0001),   # Royal Flush
)

_POKER_VALUES = [p[0] for p in POKER_PAYOUT_WEIGHTS]
_POKER_PROBS = [p[1] for p in POKER_PAYOUT_WEIGHTS]

# Empirical live-bot timing metrics (seconds) derived from gameplay session logs:
# - Card scan & burst detection interval: ~1.17s (average 25-frame burst across 150+ card flips)
# - Doubling step cycle: ~4.67s (guess click, flip/detect interval, OCR verify, decision)
# - Video Poker hand round: ~11.55s (deal 5 cards, optimal hold solver, replace click, draw, result)
# - Settlement credit wait & transition: ~4.5s (cashout stabilization)
# - Bust / fail transition: ~2.5s (fail screen acknowledge to restart)
TIME_CARD_SCAN_DETECT_SEC: float = 1.17
TIME_DOUBLING_STEP_SEC: float = 4.67
TIME_POKER_ROUND_SEC: float = 11.55
TIME_CASHOUT_SETTLE_SEC: float = 4.5
TIME_BUST_SETTLE_SEC: float = 2.5


@dataclass
class RoundResult:
    """Outcome of a single simulated video poker + High-Low round."""
    won_poker: bool
    initial_payout: int
    final_payout: int
    net_payout: int  # final_payout - ENTRY_FEE
    doubling_steps: int
    cashed_out: bool
    busted: bool
    reason: Optional[str] = None
    duration_seconds: float = 0.0


@dataclass
class DaySimulationResult:
    """Outcome of simulating an entire day's play under a specific strategy."""
    strategy_name: str
    total_coins: int
    total_fails: int
    total_rounds: int
    net_profit: int
    rounds: list[RoundResult] = field(default_factory=list)
    total_duration_seconds: float = 0.0

    @property
    def total_duration_minutes(self) -> float:
        return self.total_duration_seconds / 60.0

    @property
    def total_duration_hours(self) -> float:
        return self.total_duration_seconds / 3600.0


@dataclass
class MonteCarloSummary:
    """Aggregate statistics over N simulated days."""
    strategy_name: str
    days_simulated: int
    avg_coins: float
    min_coins: int
    max_coins: int
    median_coins: float
    avg_net_profit: float
    avg_fails: float
    avg_rounds: float
    pct_over_20k: float
    pct_over_30k: float
    pct_over_35k: float
    std_coins: float = 0.0
    pct_over_40k: float = 0.0
    avg_duration_minutes: float = 0.0
    min_duration_minutes: float = 0.0
    max_duration_minutes: float = 0.0

    @property
    def days(self) -> int:
        return self.days_simulated

    @property
    def mean_coins(self) -> float:
        return self.avg_coins

    @property
    def mean_fails(self) -> float:
        return self.avg_fails

    @property
    def pct_hit_cap(self) -> float:
        return self.pct_over_20k

    @property
    def pct_overflow_30k(self) -> float:
        return self.pct_over_30k

    @property
    def pct_overflow_40k(self) -> float:
        return self.pct_over_40k

    @property
    def avg_time_minutes(self) -> float:
        return self.avg_duration_minutes

    @property
    def avg_time_hours(self) -> float:
        return self.avg_duration_minutes / 60.0


class GameSimulator:
    """Simulates casino game rounds and daily sessions offline."""

    def __init__(
        self,
        seed: Optional[int] = None,
        num_decks: int = 1,
        tie_loses: bool = True,
        opportunistic_double_mode: str = "a_2_only",
        opp_a2: Optional[bool] = None,
        opp_3k: Optional[bool] = None,
        opp_4q: Optional[bool] = None,
        opp_5j: bool = False,
        opp_610: bool = False,
        opp_79: bool = False,
        opp_8: bool = False,
        mod_fast_build: bool = False,
        mod_drop_78: bool = False,
        mod_drop_6789: bool = False,
        mod_drop_8: bool = False,
        mod_free_roll: bool = False,
        mod_sprint_floor: bool = False,
        mod_mega_sprint: bool = False,
        cushion_target: int = 19800,
        time_poker_round: float = TIME_POKER_ROUND_SEC,
        time_doubling_step: float = TIME_DOUBLING_STEP_SEC,
        time_card_scan: float = TIME_CARD_SCAN_DETECT_SEC,
        time_cashout_settle: float = TIME_CASHOUT_SETTLE_SEC,
        time_bust_settle: float = TIME_BUST_SETTLE_SEC,
    ):
        self.rng = random.Random(seed)
        self.num_decks = num_decks
        self.tie_loses = tie_loses
        self.opportunistic_double_mode = opportunistic_double_mode
        self.opp_a2 = opp_a2 if opp_a2 is not None else (opportunistic_double_mode in ("a_2_only", "include_3_k", "include_4_q"))
        self.opp_3k = opp_3k if opp_3k is not None else (opportunistic_double_mode in ("include_3_k", "include_4_q"))
        self.opp_4q = opp_4q if opp_4q is not None else (opportunistic_double_mode == "include_4_q")
        self.opp_5j = opp_5j
        self.opp_610 = opp_610
        self.opp_79 = opp_79
        self.opp_8 = opp_8
        self.mod_fast_build = mod_fast_build
        self.mod_drop_78 = mod_drop_78
        self.mod_drop_6789 = mod_drop_6789
        self.mod_drop_8 = mod_drop_8
        self.mod_free_roll = mod_free_roll
        self.mod_sprint_floor = mod_sprint_floor
        self.mod_mega_sprint = mod_mega_sprint
        self.cushion_target = cushion_target
        self.time_poker_round = time_poker_round
        self.time_doubling_step = time_doubling_step
        self.time_card_scan = time_card_scan
        self.time_cashout_settle = time_cashout_settle
        self.time_bust_settle = time_bust_settle

    def draw_poker_hand(self, exact_poker: bool = False) -> tuple[int, list[int], int]:
        """Simulate a single video poker game.
        
        Args:
            exact_poker: If True, executes the full Numba JIT optimal hold solver.
                         If False, samples from the empirical paytable distribution (<0.01ms).

        Returns:
            (initial_payout, final_hand, category_id)
        """
        if not exact_poker:
            payout = self.rng.choices(_POKER_VALUES, weights=_POKER_PROBS, k=1)[0]
            return payout, [], 0

        # 53-card deck: 0..51 standard, 52 Joker
        deck = list(range(53))
        self.rng.shuffle(deck)

        initial_hand = deck[:5]
        remaining = deck[5:]

        # Solve optimal hold
        best_result, _ = calculate_best(initial_hand, "standard")
        held_indices = best_result.held_indices

        # Construct final hand
        final_hand = [initial_hand[i] for i in held_indices]
        needed = 5 - len(final_hand)
        final_hand.extend(remaining[:needed])

        # Evaluate final hand payout
        category = _evaluate_category5(
            final_hand[0], final_hand[1], final_hand[2], final_hand[3], final_hand[4]
        )
        payout = int(PRIZES[category])
        return payout, final_hand, category

    def play_high_low_round(
        self,
        strategy: BaseStrategy,
        initial_payout: int,
        daily_coins: int,
        max_doubles: int = 10,
        target_limit: int = 20000,
    ) -> RoundResult:
        strategy.reset_round()
        strategy.start_round(initial_payout, daily_coins)

        # High-Low uses ranks 2..14 (Ace = 14), 4 of each = 52 cards
        hl_deck: list[int] = []
        for rank in range(2, 15):
            hl_deck.extend([rank] * 4)
        self.rng.shuffle(hl_deck)

        counter = HighLowCounter()
        counter.reset()

        # First base card
        current_card = hl_deck.pop()
        counter.remove_cards([current_card])
        current_cashout = initial_payout
        doubling_steps = 0

        if current_cashout >= 10000:
            strategy.begin_settlement(cashout_requested=False)
            return RoundResult(
                won_poker=True,
                initial_payout=initial_payout,
                final_payout=current_cashout,
                net_payout=current_cashout - int(ENTRY_FEE),
                doubling_steps=0,
                cashed_out=True,
                busted=False,
                reason="max_payout_reached",
                duration_seconds=self.time_poker_round + self.time_cashout_settle,
            )

        while doubling_steps < max_doubles:
            next_reward = current_cashout * 2
            choice, win_rate = counter.get_best_choice_and_rate(current_card)

            decision = strategy.decide(
                current_cashout=current_cashout,
                next_reward=next_reward,
                win_rate=win_rate,
                daily_coins=daily_coins,
            )

            # Apply active strategy modifiers and opportunistic card overrides
            decision, mod_reason = apply_strategy_modifiers(
                decision=decision,
                card_val=current_card,
                current_cashout=current_cashout,
                next_reward=next_reward,
                daily_coins=daily_coins,
                target_limit=target_limit,
                cushion_target=self.cushion_target,
                opp_a2=self.opp_a2,
                opp_3k=self.opp_3k,
                opp_4q=self.opp_4q,
                opp_5j=self.opp_5j,
                opp_610=self.opp_610,
                opp_79=self.opp_79,
                opp_8=self.opp_8,
                mod_fast_build=self.mod_fast_build,
                mod_drop_78=self.mod_drop_78,
                mod_drop_6789=self.mod_drop_6789,
                mod_drop_8=self.mod_drop_8,
                mod_free_roll=self.mod_free_roll,
                mod_sprint_floor=self.mod_sprint_floor,
                mod_mega_sprint=self.mod_mega_sprint,
                win_rate=win_rate,
            )

            if mod_reason and decision == "challenge":
                if hasattr(strategy, "last_cashout"):
                    strategy.last_cashout = None

            if decision == "cashout" or decision == "stop":
                strategy.begin_settlement(cashout_requested=True)
                duration = (
                    self.time_poker_round
                    + (doubling_steps * self.time_doubling_step)
                    + self.time_cashout_settle
                )
                return RoundResult(
                    won_poker=True,
                    initial_payout=initial_payout,
                    final_payout=current_cashout,
                    net_payout=current_cashout - int(ENTRY_FEE),
                    doubling_steps=doubling_steps,
                    cashed_out=True,
                    busted=False,
                    reason=mod_reason or "cashout",
                    duration_seconds=duration,
                )

            # Strategy chose 'challenge'
            strategy.guess_clicked()

            if not hl_deck:
                # Fresh deck if exhausted
                for rank in range(2, 15):
                    hl_deck.extend([rank] * 4)
                self.rng.shuffle(hl_deck)

            next_card = hl_deck.pop()
            counter.remove_cards([next_card])

            # Evaluate outcome: ties are losses
            is_win = (choice == "high" and next_card > current_card) or (
                choice == "low" and next_card < current_card
            )

            if not is_win:
                # Busted after attempting a guess
                strategy.begin_settlement(cashout_requested=False)
                duration = (
                    self.time_poker_round
                    + ((doubling_steps + 1) * self.time_doubling_step)
                    + self.time_bust_settle
                )
                return RoundResult(
                    won_poker=True,
                    initial_payout=initial_payout,
                    final_payout=0,
                    net_payout=-int(ENTRY_FEE),
                    doubling_steps=doubling_steps,
                    cashed_out=False,
                    busted=True,
                    reason="guess_failed",
                    duration_seconds=duration,
                )

            # Win confirmed
            strategy.confirm_success()
            doubling_steps += 1
            current_cashout = next_reward
            current_card = next_card

            if current_cashout >= 10000:
                # In-game hard cap: double-up stops when payout reaches/exceeds 10,000 ("Ended due to reaching the max payout")
                strategy.begin_settlement(cashout_requested=False)
                duration = (
                    self.time_poker_round
                    + (doubling_steps * self.time_doubling_step)
                    + self.time_cashout_settle
                )
                return RoundResult(
                    won_poker=True,
                    initial_payout=initial_payout,
                    final_payout=current_cashout,
                    net_payout=current_cashout - int(ENTRY_FEE),
                    doubling_steps=doubling_steps,
                    cashed_out=True,
                    busted=False,
                    reason="max_payout_reached",
                    duration_seconds=duration,
                )

        # Reached game doubling cap (10 consecutive wins)
        strategy.begin_settlement(cashout_requested=False)
        duration = (
            self.time_poker_round
            + (doubling_steps * self.time_doubling_step)
            + self.time_cashout_settle
        )
        return RoundResult(
            won_poker=True,
            initial_payout=initial_payout,
            final_payout=current_cashout,
            net_payout=current_cashout - int(ENTRY_FEE),
            doubling_steps=doubling_steps,
            cashed_out=True,
            busted=False,
            reason="max_doubles_cap_reached",
            duration_seconds=duration,
        )

    def simulate_day(
        self,
        strategy_cls: Type[BaseStrategy],
        strategy_kwargs: Optional[dict] = None,
        max_daily_rounds: int = 500,
        exact_poker: bool = False,
        target_limit: int = 20000,
    ) -> DaySimulationResult:
        """Simulate a complete day until the target coin cap stops new games."""
        strategy = strategy_cls(**(strategy_kwargs or {}))
        if hasattr(strategy, "cushion_target"):
            strategy.cushion_target = self.cushion_target
        daily_coins = 0
        daily_fails = 0
        rounds: list[RoundResult] = []

        while daily_coins < target_limit and len(rounds) < max_daily_rounds:
            payout, _, _ = self.draw_poker_hand(exact_poker=exact_poker)
            if payout == 0:
                daily_fails += 1
                strategy.notify_fail()
                if hasattr(strategy, "_check_auto_adjust"):
                    strategy._check_auto_adjust(daily_coins, daily_fails, int(ENTRY_FEE))
                rounds.append(
                    RoundResult(
                        won_poker=False,
                        initial_payout=0,
                        final_payout=0,
                        net_payout=-int(ENTRY_FEE),
                        doubling_steps=0,
                        cashed_out=False,
                        busted=True,
                        reason="poker_loss",
                        duration_seconds=self.time_poker_round,
                    )
                )
                continue

            round_result = self.play_high_low_round(
                strategy=strategy,
                initial_payout=payout,
                daily_coins=daily_coins,
                target_limit=target_limit,
            )
            rounds.append(round_result)

            if round_result.final_payout > 0:
                daily_coins += round_result.final_payout
                strategy.notify_win()
            else:
                daily_fails += 1
                strategy.notify_fail()
                if hasattr(strategy, "_check_auto_adjust"):
                    strategy._check_auto_adjust(daily_coins, daily_fails, int(ENTRY_FEE))

        net_profit = daily_coins - (len(rounds) * int(ENTRY_FEE))
        total_duration = sum(r.duration_seconds for r in rounds)
        return DaySimulationResult(
            strategy_name=getattr(strategy, "name", strategy_cls.__name__),
            total_coins=daily_coins,
            total_fails=daily_fails,
            total_rounds=len(rounds),
            net_profit=net_profit,
            rounds=rounds,
            total_duration_seconds=total_duration,
        )

    def run_monte_carlo(
        self,
        strategy_cls: Type[BaseStrategy],
        strategy_kwargs: Optional[dict] = None,
        days: int = 100,
        exact_poker: bool = False,
        target_limit: int = 20000,
    ) -> MonteCarloSummary:
        """Run Monte Carlo simulation over N days and produce aggregate metrics."""
        results = [
            self.simulate_day(
                strategy_cls,
                strategy_kwargs,
                exact_poker=exact_poker,
                target_limit=target_limit,
            )
            for _ in range(days)
        ]

        coins = [r.total_coins for r in results]
        fails = [r.total_fails for r in results]
        rounds = [r.total_rounds for r in results]
        profits = [r.net_profit for r in results]
        durations = [r.total_duration_minutes for r in results]

        strategy_name = results[0].strategy_name if results else strategy_cls.__name__

        return MonteCarloSummary(
            strategy_name=strategy_name,
            days_simulated=days,
            avg_coins=float(np.mean(coins)),
            min_coins=int(np.min(coins)),
            max_coins=int(np.max(coins)),
            median_coins=float(np.median(coins)),
            avg_net_profit=float(np.mean(profits)),
            avg_fails=float(np.mean(fails)),
            avg_rounds=float(np.mean(rounds)),
            pct_over_20k=float(np.mean([1.0 if c >= 20000 else 0.0 for c in coins]) * 100),
            pct_over_30k=float(np.mean([1.0 if c >= 30000 else 0.0 for c in coins]) * 100),
            pct_over_35k=float(np.mean([1.0 if c >= 35000 else 0.0 for c in coins]) * 100),
            std_coins=float(np.std(coins)),
            pct_over_40k=float(np.mean([1.0 if c >= 40000 else 0.0 for c in coins]) * 100),
            avg_duration_minutes=float(np.mean(durations)),
            min_duration_minutes=float(np.min(durations)),
            max_duration_minutes=float(np.max(durations)),
        )

    def run_comparison(
        self,
        days: int = 100,
        exact_poker: bool = False,
        target_limit: int = 20000,
    ) -> list[MonteCarloSummary]:
        """Benchmark all registered strategies over N days and return sorted summaries."""
        summaries: list[MonteCarloSummary] = []
        for _, cls in STRATEGY_REGISTRY.items():
            summary = self.run_monte_carlo(cls, days=days, exact_poker=exact_poker, target_limit=target_limit)
            summaries.append(summary)
        summaries.sort(key=lambda s: s.avg_net_profit, reverse=True)
        return summaries


HighLowSimulator = GameSimulator


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Hololive Dreams Strategy Simulator & Benchmarker")
    parser.add_argument("--strategy", choices=list(STRATEGY_REGISTRY.keys()), default="max_profit",
                        help="Select a specific strategy to simulate")
    parser.add_argument("--compare", action="store_true", help="Benchmark and compare all registered strategies")
    parser.add_argument("--days", type=int, default=100, help="Number of simulated days per strategy")
    parser.add_argument("--exact", action="store_true", help="Run exact JIT poker solver instead of empirical distribution")
    args = parser.parse_args()

    sim = GameSimulator()

    if args.compare:
        print(f"=== Running Monte Carlo Benchmark across all {len(STRATEGY_REGISTRY)} strategies ({args.days} days each) ===\n")
        summaries: list[MonteCarloSummary] = []
        for key, cls in STRATEGY_REGISTRY.items():
            print(f"  -> Simulating {key}...", end="", flush=True)
            summary = sim.run_monte_carlo(cls, days=args.days, exact_poker=args.exact)
            summaries.append(summary)
            print(" Done.")

        # Sort by average net profit descending
        summaries.sort(key=lambda s: s.avg_net_profit, reverse=True)

        print("\n" + "=" * 105)
        print(f"{'Strategy':<28} | {'Avg Coins':>10} | {'Net Profit':>10} | {'Fails/Day':>9} | {'Avg Time':>9} | {'% >= 20k':>8} | {'% >= 30k':>8}")
        print("-" * 105)
        for s in summaries:
            time_str = f"{s.avg_duration_minutes:.1f}m"
            print(f"{s.strategy_name[:28]:<28} | {s.avg_coins:>10,.0f} | {s.avg_net_profit:>10,.0f} | {s.avg_fails:>9.1f} | {time_str:>9} | {s.pct_over_20k:>7.1f}% | {s.pct_over_30k:>7.1f}%")
        print("=" * 105)
    else:
        print(f"Running Monte Carlo simulation for '{args.strategy}' over {args.days} days...")
        summary = sim.run_monte_carlo(STRATEGY_REGISTRY[args.strategy], days=args.days, exact_poker=args.exact)
        print(f"\nResults for {summary.strategy_name}:")
        print(f"  Avg Daily Coins:   {summary.avg_coins:,.0f} (Min: {summary.min_coins:,}, Max: {summary.max_coins:,})")
        print(f"  Avg Net Profit:    {summary.avg_net_profit:,.0f} coins")
        print(f"  Avg Est. Runtime:  {summary.avg_duration_minutes:.1f} min / {summary.avg_duration_minutes / 60:.2f} hrs (Min: {summary.min_duration_minutes:.1f}m, Max: {summary.max_duration_minutes:.1f}m)")
        print(f"  Avg Fails/Day:     {summary.avg_fails:.1f} rounds ({summary.avg_fails * 50:,.0f} ticket coins)")
        print(f"  Avg Rounds/Day:    {summary.avg_rounds:.1f}")
        print(f"  Days >= 20,000:    {summary.pct_over_20k:.1f}%")
        print(f"  Days >= 30,000:    {summary.pct_over_30k:.1f}%")
        print(f"  Days >= 35,000:    {summary.pct_over_35k:.1f}%")
