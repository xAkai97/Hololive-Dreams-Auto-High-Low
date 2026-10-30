"""Adaptive Rush strategy — starts aggressive, auto-downshifts if failing.

Begins like Fastest Clear (max double-up every round) but automatically
switches to safe cushion mode if too many fails accumulate or if progress
is too slow. Once in cushion mode, it stays there (no switching back).
"""
from typing import Optional

from strategies.base import BaseStrategy, normalize_play_style

# Auto-adjust triggers
DEFAULT_FAIL_THRESHOLD = 10        # Consecutive fails before downshift
DEFAULT_NEGATIVE_THRESHOLD = -2000  # Net profit floor before downshift


class AdaptiveRushStrategy(BaseStrategy):
    """Start fast, auto-fallback to safe cushion if struggling.

    Rush mode:
        - Max double-up every round (like Fastest Clear)
    Auto-adjust triggers (any one switches to cushion):
        - Consecutive fails without a win (6 conservative / 10 default / 15 aggressive)
        - Net profit drops below floor (-1,000 conservative / -2,000 default / -3,000 aggressive)
    Cushion mode:
        - Small cashouts (3,200-6,400) to grind toward 19,800
        - Cashout if win_rate < floor (60% conservative / 55% default / 50% aggressive)
    Sprint (daily >= 19,800):
        - Max double-up for 10k+ final cashout
    """

    name: str = "Adaptive Rush (~25-32k)"
    cushion_target: int = 19800

    def __init__(self, play_style: str = "default"):
        self.play_style = normalize_play_style(play_style)
        self.reset_round()
        self._in_cushion_mode = False
        self._consecutive_fails = 0

    def reset_round(self) -> None:
        self.base_cash: Optional[int] = None
        self.last_cashout: Optional[int] = None
        self.intent_to_fail: bool = False

    def start_round(self, base_cash: int, coins: int) -> None:
        self.base_cash = base_cash

    @property
    def expected_cash(self) -> Optional[int]:
        return self.last_cashout

    def _check_auto_adjust(self, daily_coins: int, daily_fails: int, ticket_cost: int = 50) -> None:
        """Check if we should switch from rush to cushion mode."""
        if self._in_cushion_mode:
            return
        style = normalize_play_style(getattr(self, "play_style", "default"))
        neg_floor = -3000 if style == "aggressive" else (-1000 if style == "conservative" else DEFAULT_NEGATIVE_THRESHOLD)
        net_profit = daily_coins - (daily_fails * ticket_cost)
        if net_profit < neg_floor:
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
        cushion = getattr(self, "cushion_target", 19800)
        self.intent_to_fail = False

        # Sprint: daily >= cushion (both modes)
        if daily_coins >= cushion:
            action = 'cashout' if current_cashout >= 10000 else 'challenge'

        # Cushion mode (auto-adjusted)
        elif self._in_cushion_mode:
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
                cash_floor = 6400 if style == "aggressive" else 3200
                rate_floor = 0.50 if style == "aggressive" else (0.60 if style == "conservative" else 0.55)
                if current_cashout >= cash_floor or win_rate < rate_floor:
                    action = 'cashout'
                else:
                    action = 'challenge'

        # Rush mode (default)
        # Only cashout if it reaches daily cap
        elif daily_coins + current_cashout >= getattr(self, "target_limit", 20000):
            action = 'cashout'
        else:
            action = 'challenge'

        self.last_cashout = current_cashout if action == 'cashout' else None
        return action

    def notify_fail(self) -> None:
        """Called externally when a round fails. Tracks consecutive fails."""
        self._consecutive_fails += 1
        style = normalize_play_style(getattr(self, "play_style", "default"))
        fail_limit = 15 if style == "aggressive" else (6 if style == "conservative" else DEFAULT_FAIL_THRESHOLD)
        if self._consecutive_fails >= fail_limit:
            self._in_cushion_mode = True

    def notify_win(self) -> None:
        """Called externally when a round wins. Resets fail counter."""
        self._consecutive_fails = 0
