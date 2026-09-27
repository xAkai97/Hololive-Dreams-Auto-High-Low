"""Aggressive Balanced strategy — like Balanced but pushes harder for ~28-30k.

More aggressive thresholds: lower win_rate floors, higher cashout targets,
willing to let rounds ride longer for bigger payouts.
"""
from typing import Optional

from strategies.base import BaseStrategy


class AggressiveBalancedStrategy(BaseStrategy):
    """Higher profit Balanced variant targeting ~28,000-30,000 coins.

    Build phase (daily < 12,000):
        - Cashout at 6,400+ only
        - Cashout if win_rate < 50%
    Push phase (12k <= daily < 19,800):
        - Let rounds ride to game cap when possible
        - Only bail at very low win_rate (< 45%)
        - Guard: cashout if next double overshoots 19,800
    Sprint phase (daily >= 19,800):
        - Max double-up for 10k+ cashout
    """

    name: str = "Aggressive Balanced (~28k)"

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
        # Sprint: daily >= 19,800
        if daily_coins >= 19800:
            action = 'cashout' if current_cashout >= 10000 else 'challenge'

        # Push: 12,000 <= daily < 19,800
        elif daily_coins >= 12000:
            if daily_coins + current_cashout <= 19800 and daily_coins + next_reward > 19800:
                action = 'cashout'
            elif daily_coins + current_cashout > 19800:
                action = 'cashout' if current_cashout >= 10000 else 'challenge'
            elif win_rate < 0.45:
                action = 'cashout'
            else:
                action = 'challenge'

        # Build: daily < 12,000
        else:
            if daily_coins + current_cashout <= 19800 and daily_coins + next_reward > 19800:
                action = 'cashout'
            elif current_cashout >= 6400:
                action = 'cashout'
            elif win_rate < 0.50:
                action = 'cashout'
            else:
                action = 'challenge'

        self.last_cashout = current_cashout if action == 'cashout' else None
        return action
