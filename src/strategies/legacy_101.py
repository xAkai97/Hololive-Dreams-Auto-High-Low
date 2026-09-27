"""1.0.1 Legacy strategy — upstream original cushion/sprint logic.

Ported from the original inline decision tree in auto_bot.py by mwty-0415.
The logic is preserved exactly: cushion under 19,800, sprint above.
"""
from typing import Optional

from strategies.base import BaseStrategy


class Legacy101Strategy(BaseStrategy):
    """The original 1.0.1 legacy risk control and doubling strategy.

    Cushion phase (daily < 19,800):
        - Cashout if next double overshoots 19,800
        - Cashout if win_rate < 60%
        - Force double if cashing out would overshoot 19,800 without reaching 10k
    Sprint phase (daily >= 19,800):
        - Ignore win_rate, keep doubling until cashout >= 10,000
    """

    name: str = "1.0.1 Legacy"

    def __init__(self):
        self.reset_round()
        self.last_reason: Optional[str] = None
        self.last_meta: dict = {}

    def reset_round(self) -> None:
        self.base_cash: Optional[int] = None
        self.last_cashout: Optional[int] = None
        self.last_reason = None
        self.last_meta = {}

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
        # === Sprint phase: daily >= 19,800 ===
        if daily_coins >= 19800:
            if current_cashout >= 10000:
                self.last_reason = 'legacy_sprint_goal'
                self.last_meta = {'cashout': current_cashout}
                action = 'cashout'
            else:
                self.last_reason = 'legacy_sprint_chase'
                self.last_meta = {'cashout': current_cashout, 'reward': next_reward}
                action = 'challenge'

        # === Cushion phase: daily < 19,800 ===
        # 1. Safe to cashout now, but next double would overshoot 19,800
        elif daily_coins + current_cashout <= 19800 and daily_coins + next_reward > 19800:
            self.last_reason = 'legacy_cushion_brake'
            self.last_meta = {'cashout': current_cashout, 'total': daily_coins + current_cashout}
            action = 'cashout'

        # 2. Cashout itself overshoots 19,800
        elif daily_coins + current_cashout > 19800:
            if current_cashout >= 10000:
                self.last_reason = 'legacy_cushion_windfall'
                self.last_meta = {'cashout': current_cashout}
                action = 'cashout'
            else:
                self.last_reason = 'legacy_cushion_force_double'
                self.last_meta = {'cashout': current_cashout, 'total': daily_coins + current_cashout}
                action = 'challenge'

        # 3. Low win rate — play safe
        elif win_rate < 0.60:
            self.last_reason = 'legacy_low_winrate'
            self.last_meta = {'rate': win_rate, 'cashout': current_cashout}
            action = 'cashout'

        # 4. Safe, keep going
        else:
            self.last_reason = 'legacy_safe_continue'
            self.last_meta = {'cashout': current_cashout, 'reward': next_reward}
            action = 'challenge'

        self.last_cashout = current_cashout if action == 'cashout' else None
        return action
