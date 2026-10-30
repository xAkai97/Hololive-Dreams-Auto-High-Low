"""Balanced strategy — moderate risk for reliable ~25,000 coins.

Three phases based on daily coin total:
- Build: conservative cashouts at 3,200-6,400
- Push: raise threshold, more aggressive
- Sprint: max double-up for final big win
"""
from typing import Optional

from strategies.base import BaseStrategy, normalize_play_style


class BalancedStrategy(BaseStrategy):
    """Reliable ~25,000-30,000 coins with staged progression and tunable Play Style.

    Play Styles:
    - Default (~25k-30k):
        Build (< 15k): cashout >= 6,400 or win_rate < 55%
        Push (15k-19.8k): cashout >= 10,000 or win_rate < 50%
    - Aggressive (~28k-30k, former Aggressive Balanced):
        Build (< 12k): cashout >= 6,400 or win_rate < 50%
        Push (12k-19.8k): ride to cap, cashout only if win_rate < 45%
    - Conservative (~23k-27k):
        Build (< 16k): cashout >= 3,200 or win_rate < 60%
        Push (16k-19.8k): cashout >= 6,400 or win_rate < 55%
    Sprint phase (daily >= 19,800):
        - Max double-up for 10k+ cashout
    """

    name: str = "Balanced (~25-30k)"
    cushion_target: int = 19800

    def __init__(self, play_style: str = "default"):
        self.play_style = normalize_play_style(play_style)
        self.reset_round()

    def reset_round(self) -> None:
        self.base_cash: Optional[int] = None
        self.last_cashout: Optional[int] = None
        self.intent_to_fail: bool = False

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
                if style == "aggressive":
                    if daily_coins >= 12000:
                        action = 'cashout' if win_rate < 0.45 else 'challenge'
                    else:
                        action = 'cashout' if (current_cashout >= 6400 or win_rate < 0.50) else 'challenge'
                elif style == "conservative":
                    if daily_coins >= 16000:
                        action = 'cashout' if (current_cashout >= 6400 or win_rate < 0.55) else 'challenge'
                    else:
                        action = 'cashout' if (current_cashout >= 3200 or win_rate < 0.60) else 'challenge'
                else:
                    if daily_coins >= 15000:
                        action = 'cashout' if (current_cashout >= 10000 or win_rate < 0.50) else 'challenge'
                    else:
                        action = 'cashout' if (current_cashout >= 6400 or win_rate < 0.55) else 'challenge'

        self.last_cashout = current_cashout if action == 'cashout' else None
        return action
