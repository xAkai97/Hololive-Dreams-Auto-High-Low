"""Adaptive Rush strategy — starts aggressive, auto-downshifts if failing.

Begins like Fastest Clear (max double-up every round) but automatically
switches to safe cushion mode if too many fails accumulate or if progress
is too slow. Once in cushion mode, it stays there (no switching back).
"""
from typing import Optional

from strategies.base import BaseStrategy

# Auto-adjust triggers
DEFAULT_FAIL_THRESHOLD = 10        # Consecutive fails before downshift
DEFAULT_NEGATIVE_THRESHOLD = -2000  # Net profit floor before downshift


class AdaptiveRushStrategy(BaseStrategy):
    """Start fast, auto-fallback to safe cushion if struggling.

    Rush mode:
        - Max double-up every round (like Fastest Clear)
    Auto-adjust triggers (any one switches to cushion):
        - More than 10 consecutive fails without a win
        - Net profit drops below -2,000
    Cushion mode:
        - Small cashouts (3,200-6,400) to grind toward 19,800
        - Cashout if win_rate < 55%
    Sprint (daily >= 19,800):
        - Max double-up for 10k+ final cashout
    """

    name: str = "Adaptive Rush (~25-32k)"

    def __init__(self):
        self.reset_round()
        self._in_cushion_mode = False
        self._consecutive_fails = 0

    def reset_round(self) -> None:
        self.base_cash: Optional[int] = None
        self.last_cashout: Optional[int] = None

    def start_round(self, base_cash: int, coins: int) -> None:
        self.base_cash = base_cash

    @property
    def expected_cash(self) -> Optional[int]:
        return self.last_cashout

    def _check_auto_adjust(self, daily_coins: int, daily_fails: int, ticket_cost: int = 50) -> None:
        """Check if we should switch from rush to cushion mode."""
        if self._in_cushion_mode:
            return
        net_profit = daily_coins - (daily_fails * ticket_cost)
        if net_profit < DEFAULT_NEGATIVE_THRESHOLD:
            self._in_cushion_mode = True

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
        # Sprint: daily >= 19,800 (both modes)
        if daily_coins >= 19800:
            action = 'cashout' if current_cashout >= 10000 else 'challenge'

        # Cushion mode (auto-adjusted)
        elif self._in_cushion_mode:
            if daily_coins + current_cashout <= 19800 and daily_coins + next_reward > 19800:
                action = 'cashout'
            elif daily_coins + current_cashout > 19800:
                action = 'cashout' if current_cashout >= 10000 else 'challenge'
            elif current_cashout >= 3200:
                action = 'cashout'
            elif win_rate < 0.55:
                action = 'cashout'
            else:
                action = 'challenge'

        # Rush mode (default)
        # Only cashout if it reaches daily cap
        elif daily_coins + current_cashout >= 20000:
            action = 'cashout'
        else:
            action = 'challenge'

        self.last_cashout = current_cashout if action == 'cashout' else None
        return action

    def notify_fail(self) -> None:
        """Called externally when a round fails. Tracks consecutive fails."""
        self._consecutive_fails += 1
        if self._consecutive_fails >= DEFAULT_FAIL_THRESHOLD:
            self._in_cushion_mode = True

    def notify_win(self) -> None:
        """Called externally when a round wins. Resets fail counter."""
        self._consecutive_fails = 0
