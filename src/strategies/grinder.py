"""Grinder strategy — ultra-safe small cashouts, one final sprint.

The lowest risk strategy. Takes the first safe cashout opportunity in every
round, never voluntarily doubles more than needed. Grinds slowly toward
19,800, then does one final max double-up attempt.
"""
from typing import Optional

from strategies.base import BaseStrategy

MAX_DOUBLES = 4  # Never voluntarily double more than this many times


class GrinderStrategy(BaseStrategy):
    """Minimum risk, guaranteed ~20,000+ coins.

    Build phase (daily < 19,800):
        - Cashout at first opportunity >= 200
        - Never double more than 4 times voluntarily
        - Win_rate floor: 60%
    Sprint phase (daily >= 19,800):
        - One final max double-up attempt for 10k+
    """

    name: str = "Grinder (~20-25k)"

    def __init__(self):
        self.reset_round()
        self._doubles_this_round = 0

    def reset_round(self) -> None:
        self.base_cash: Optional[int] = None
        self.last_cashout: Optional[int] = None
        self._doubles_this_round = 0

    def start_round(self, base_cash: int, coins: int) -> None:
        self.base_cash = base_cash
        self._doubles_this_round = 0

    @property
    def expected_cash(self) -> Optional[int]:
        return self.last_cashout

    def decide(
        self,
        current_cashout: Optional[int] = None,
        next_reward: Optional[int] = None,
        win_rate: Optional[float] = None,
        daily_coins: Optional[int] = None,
    ) -> str:
        current_cashout = current_cashout or 0
        next_reward = next_reward or (current_cashout * 2)
        win_rate = win_rate if win_rate is not None else 1.0
        daily_coins = daily_coins or 0
        self._doubles_this_round += 1

        # Sprint: daily >= 19,800
        if daily_coins >= 19800:
            action = 'cashout' if current_cashout >= 10000 else 'challenge'

        # Build: daily < 19,800
        # Hit max doubles — take whatever we have
        elif self._doubles_this_round >= MAX_DOUBLES:
            action = 'cashout'
        # Low win rate — bail
        elif win_rate < 0.60:
            action = 'cashout'
        # Guard: don't overshoot 19,800
        elif daily_coins + current_cashout <= 19800 and daily_coins + next_reward > 19800:
            action = 'cashout'
        # Overshoot — force double if small
        elif daily_coins + current_cashout > 19800:
            action = 'cashout' if current_cashout >= 10000 else 'challenge'
        # Any reasonable cashout — take it (grinder mentality)
        elif current_cashout >= 1600:
            action = 'cashout'
        else:
            action = 'challenge'

        self.last_cashout = current_cashout if action == 'cashout' else None
        return action
