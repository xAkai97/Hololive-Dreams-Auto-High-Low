"""Fastest Clear strategy — all-or-nothing max double-up every round.

The fastest way to hit 20,000+ coins. Every round goes for max double-up
(letting the game auto-settle at ~10k). Only cashout if doing so reaches
the daily cap. Highest variance, fastest completion.
"""
from typing import Optional

from strategies.base import BaseStrategy, normalize_play_style


class FastestClearStrategy(BaseStrategy):
    """Reach 20,000+ coins as fast as possible.

    Always max double-up (game auto-settles at ~10k cap).
    Only cashout if daily + cashout >= 20,000 (or >= 6,400 on <55% odds in conservative mode).
    Stop when daily >= 20,000.
    """

    name: str = "Fastest Clear (~20k)"

    def __init__(self, play_style: str = "default"):
        self.play_style = normalize_play_style(play_style)
        self.reset_round()

    def reset_round(self) -> None:
        super().reset_round()
        self.base_cash = None
        self.last_cashout = None

    def start_round(self, base_cash: int, coins: int) -> None:
        self.base_cash = base_cash

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
        daily_coins = daily_coins or 0

        # Only cashout if it completes the daily cap
        target = getattr(self, "target_limit", 20000)
        if daily_coins + current_cashout >= target:
            self.last_cashout = current_cashout
            return 'cashout'

        style = normalize_play_style(getattr(self, "play_style", "default"))
        if style == "conservative" and current_cashout >= 6400 and (win_rate is not None and win_rate < 0.55):
            self.last_cashout = current_cashout
            return 'cashout'

        # Otherwise always keep doubling — let game cap handle it
        self.last_cashout = None
        return 'challenge'
