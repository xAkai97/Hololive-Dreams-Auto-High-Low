"""Grinder strategy — ultra-safe small cashouts, one final sprint.

The lowest risk strategy. Takes the first safe cashout opportunity in every
round, never voluntarily doubles more than needed. Grinds slowly toward
19,800, then does one final max double-up attempt.
"""
from typing import Optional

from strategies.base import BaseStrategy, normalize_play_style

MAX_DOUBLES = 4  # Never voluntarily double more than this many times


class GrinderStrategy(BaseStrategy):
    """Minimum risk, guaranteed ~20,000+ coins.

    Build phase (daily < 19,800):
        - Cashout at first opportunity >= threshold (800 conservative / 1,600 default / 3,200 aggressive)
        - Max doubles limit (3 conservative / 4 default / 5 aggressive)
        - Win_rate floor (65% conservative / 60% default / 55% aggressive)
    Sprint phase (daily >= 19,800):
        - One final max double-up attempt for 10k+
    """

    name: str = "Grinder (~20-25k)"
    cushion_target: int = 19800

    def __init__(self, play_style: str = "default"):
        self.play_style = normalize_play_style(play_style)
        self.reset_round()

    def reset_round(self) -> None:
        self.base_cash: Optional[int] = None
        self.last_cashout: Optional[int] = None
        self.intent_to_fail: bool = False
        self._doubles_this_round = 0

    def start_round(self, base_cash: int, coins: int) -> None:
        self.base_cash = base_cash
        self._doubles_this_round = 0

    @property
    def expected_cash(self) -> Optional[int]:
        return self.last_cashout

    def guess_clicked(self) -> None:
        self._doubles_this_round += 1

    def notify_push(self) -> None:
        if self._doubles_this_round > 0:
            self._doubles_this_round -= 1

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

        cushion = getattr(self, "cushion_target", 19800)
        self.intent_to_fail = False

        # Sprint: daily >= cushion
        if daily_coins >= cushion:
            action = 'cashout' if current_cashout >= 10000 else 'challenge'
        else:
            guard = self.evaluate_cushion_guard(
                current_cashout=current_cashout,
                next_reward=next_reward,
                daily_coins=daily_coins,
                cushion=cushion,
                sprint_floor=10000,
            )
            if guard is not None:
                action = guard
            else:
                style = normalize_play_style(getattr(self, "play_style", "default"))
                max_d = 5 if style == "aggressive" else (3 if style == "conservative" else MAX_DOUBLES)
                min_rate = 0.55 if style == "aggressive" else (0.65 if style == "conservative" else 0.60)
                cash_floor = 3200 if style == "aggressive" else (800 if style == "conservative" else 1600)
                if self._doubles_this_round >= max_d or win_rate < min_rate or current_cashout >= cash_floor:
                    action = 'cashout'
                else:
                    action = 'challenge'

        self.last_cashout = current_cashout if action == 'cashout' else None
        return action
