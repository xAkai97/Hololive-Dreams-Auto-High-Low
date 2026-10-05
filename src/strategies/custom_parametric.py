"""Custom Parametric strategy — fully user-configurable via GUI settings.

All parameters are exposed through the config and can be set via the GUI.
This lets users define their own strategy by tuning thresholds, targets,
and behavior switches.
"""
from typing import Optional

from strategies.base import BaseStrategy


class CustomParametricStrategy(BaseStrategy):
    """User-defined strategy with configurable parameters.

    Parameters (set via config / GUI):
        cashout_target:      Cashout threshold during build phase (default: 6400)
        min_win_rate:        Minimum win_rate before forced cashout (default: 0.55)
        sprint_threshold:    Daily coins to enter sprint mode (default: 19800)
        sprint_cashout:      Min cashout to accept during sprint (default: 10000)
        max_doubles:         Max doubles per round, 0=unlimited (default: 0)
        drop_on_seven_eight: Always cashout on 7/8 cards (default: False)
        fail_safety_limit:   Switch to safe mode after N consecutive fails (default: 0=off)
    """

    name: str = "Custom Parametric"

    def __init__(
        self,
        cashout_target: int = 6400,
        min_win_rate: float = 0.55,
        sprint_threshold: int = 19800,
        sprint_cashout: int = 10000,
        max_doubles: int = 0,
        drop_on_seven_eight: bool = False,
        fail_safety_limit: int = 0,
    ):
        self.cashout_target = cashout_target
        self.min_win_rate = min_win_rate
        self.sprint_threshold = sprint_threshold
        self.sprint_cashout = sprint_cashout
        self.max_doubles = max_doubles
        self.drop_on_seven_eight = drop_on_seven_eight
        self.fail_safety_limit = fail_safety_limit

        self._consecutive_fails = 0
        self._in_safety_mode = False
        self.reset_round()

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

    def guess_clicked(self) -> None:
        self._doubles_this_round += 1

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

        # 1. Sprint check
        if daily_coins >= self.sprint_threshold:
            action = 'cashout' if current_cashout >= self.sprint_cashout else 'challenge'

        # 2. Fail safety check
        elif self._in_safety_mode:
            action = 'cashout' if current_cashout >= 200 else 'challenge'

        # 3. Max doubles check
        elif self.max_doubles > 0 and self._doubles_this_round >= self.max_doubles:
            action = 'cashout'

        # 4. Drop on 7/8 check (win_rate proxy: 7 or 8 gives ~50% rate)
        elif self.drop_on_seven_eight and win_rate <= 0.52:
            action = 'cashout'

        # 5. Win rate check
        elif win_rate < self.min_win_rate:
            action = 'cashout'

        # 6. Build targets
        # Guard: don't overshoot sprint threshold
        elif (daily_coins + current_cashout <= self.sprint_threshold
                and daily_coins + next_reward > self.sprint_threshold):
            action = 'cashout'

        # Overshoot sprint — force double if under sprint cashout
        elif daily_coins + current_cashout > self.sprint_threshold:
            action = 'cashout' if current_cashout >= self.sprint_cashout else 'challenge'

        # Cashout target reached
        elif current_cashout >= self.cashout_target:
            action = 'cashout'

        else:
            action = 'challenge'

        self.last_cashout = current_cashout if action == 'cashout' else None
        return action

    def notify_fail(self) -> None:
        """Called when a round fails. Tracks consecutive fails for safety switch."""
        self._consecutive_fails += 1
        if self.fail_safety_limit > 0 and self._consecutive_fails >= self.fail_safety_limit:
            self._in_safety_mode = True

    def notify_win(self) -> None:
        """Called when a round wins. Resets fail counter."""
        self._consecutive_fails = 0
