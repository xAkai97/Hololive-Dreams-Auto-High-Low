"""Max Profit strategy — cushion to 19,800 then sprint for ~10k+ final win.

Mirrors the upstream legacy logic exactly. The optimal daily strategy for
~30,000-32,000 coins: carefully build to 19,800 then go all-in on a final
max double-up round.
"""
from typing import Optional

from strategies.base import BaseStrategy


class MaxProfitStrategy(BaseStrategy):
    """Maximize daily profit to ~32,000 coins.

    Cushion phase (daily < 19,800):
        - Cashout if next double overshoots 19,800
        - Cashout if win_rate < 60%
        - Force double if cashing would overshoot without reaching 10k
    Sprint phase (daily >= 19,800):
        - Ignore win_rate, keep doubling until cashout >= 10,000
    """

    name: str = "Max Profit (~32k)"

    def __init__(self):
        self.reset_round()

    def reset_round(self) -> None:
        self.base_cash: Optional[int] = None
        self.last_cashout: Optional[int] = None

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
        next_reward = next_reward or (current_cashout * 2)
        win_rate = win_rate if win_rate is not None else 1.0
        daily_coins = daily_coins or 0
        # Sprint: daily >= 19,800 — chase 10k+ cashout
        if daily_coins >= 19800:
            action = 'cashout' if current_cashout >= 10000 else 'challenge'
        # Cushion: daily < 19,800
        # Safe now, but next double overshoots 19,800
        elif daily_coins + current_cashout <= 19800 and daily_coins + next_reward > 19800:
            action = 'cashout'
        # Cashout itself overshoots 19,800
        elif daily_coins + current_cashout > 19800:
            action = 'cashout' if current_cashout >= 10000 else 'challenge'
        # Low win rate — play safe
        elif win_rate < 0.60:
            action = 'cashout'
        else:
            action = 'challenge'

        self.last_cashout = current_cashout if action == 'cashout' else None
        return action
