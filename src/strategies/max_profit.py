"""Max Profit strategies — Adaptive Max Profit (~29-33k) & True Max Profit (33.9k).

Provides two Max Profit policies:
1. MaxProfitStrategy (Adaptive Max Profit): Dynamically cushions to 19,800 or 19,900
   and sprints for 10k-14k+ (or early sprints if daily + max_payout >= 32,600).
2. TrueMaxProfitStrategy (Max Profit - Can Take a Long Time): Parity-aware cushion
   to 19,900, then hunts Five of a Kind (7,000 -> 14,000) for a 33,900 daily finish,
   with configurable max attempts and live adaptive intercept fallback.
"""
from typing import Optional

from strategies.base import BaseStrategy, get_max_round_payout, TRUE_MAX_EARLY_BENCHMARK, normalize_play_style


class MaxProfitStrategy(BaseStrategy):
    """Adaptive Max Profit (~29,000-33,700 coins).

    Cushion phase (daily < 19,800):
        - Cashout if current fits <= 19,900 (cushion + 100) and next double overshoots 19,900
        - Cashout if win_rate < floor (55% aggressive / 60% default / 65% conservative)
        - If cashing out overshoots 19,900 (< 10k): attempt max payout if daily + max_payout >= cushion + 12,800,
          else purposely fail double up
    Sprint phase (daily >= 19,800):
        - Ignore win_rate, keep doubling until cashout >= 10,000
    """

    name: str = "Adaptive Max Profit (~29-33k)"
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

        # Sprint: daily >= cushion (19,800-19,900) — chase 10k+ cashout
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
                min_rate = 0.55 if style == "aggressive" else (0.65 if style == "conservative" else 0.60)
                if win_rate < min_rate:
                    action = 'cashout'
                else:
                    action = 'challenge'

        self.last_cashout = current_cashout if action == 'cashout' else None
        return action


AdaptiveMaxProfitStrategy = MaxProfitStrategy


class TrueMaxCoinsStrategy(BaseStrategy):
    """True Max Coins (19,900 + 14,000 = 33,900 coins; 33.9k trophy hunt).

    NOTE: Chasing Five of a Kind (14,000) for a 33,900 gross coin total takes an average
    of 1,300-2,700 rounds, burning 65,000-135,000+ coins in 50-coin ticket fees and yielding
    a severe negative net wallet profit (-30k to -100k+). Use for trophy screenshots only.

    Cushion phase (daily < 19,900):
        - Parity-aware building to 19,900 (locks in odd hundred on 700/1,500, caps even totals at 19,200)
        - Early overshoot only plays to win if daily + max_payout >= 33,700 (e.g. 19,700 + 14,000)
    Sprint phase (daily == 19,900):
        - Hunts Five of a Kind (7,000 -> 14,000) for 33,900 total; purposely fails lower hands
        - Automatically falls back to Adaptive Max Profit if hunt_14k_attempts is reached or
          live Intercept (force_adaptive_sprint) is activated.
    """

    name: str = "True Max Coins (33.9k Trophy Hunt)"
    cushion_target: int = 19900

    def __init__(self, hunt_14k_attempts: int = 0, play_style: str = "default"):
        self.play_style = normalize_play_style(play_style)
        self.hunt_14k_attempts = max(0, int(hunt_14k_attempts or 0))
        self._sprint_attempts = 0
        self._in_sprint_round = False
        self.force_adaptive_sprint = False
        self.reset_round()

    def reset_round(self) -> None:
        self.base_cash: Optional[int] = None
        self.last_cashout: Optional[int] = None
        self.intent_to_fail: bool = False
        self._in_sprint_round = False

    def start_round(self, base_cash: int, coins: int) -> None:
        self.base_cash = base_cash
        cushion = getattr(self, "cushion_target", 19900)
        # In sprint round if at or above 19,900, OR if daily is an even total > 19,200 where 19,900 is unreachable
        coins_val = coins or 0
        self._in_sprint_round = (coins_val >= cushion) or ((coins_val % 200 == 0) and coins_val > 19200)

    def _is_adaptive_fallback(self) -> bool:
        if getattr(self, "force_adaptive_sprint", False):
            return True
        if self.hunt_14k_attempts > 0 and self._sprint_attempts >= self.hunt_14k_attempts:
            return True
        return False

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
        self.intent_to_fail = False

        # Fallback to Adaptive Max Profit when Intercept is active or 5OAK attempts exhausted
        if self._is_adaptive_sprint_fallback(daily_coins):
            eff_cushion = 19800
            if daily_coins >= eff_cushion:
                action = 'cashout' if current_cashout >= 10000 else 'challenge'
            else:
                guard = self.evaluate_cushion_guard(
                    current_cashout=current_cashout,
                    next_reward=next_reward,
                    daily_coins=daily_coins,
                    cushion=eff_cushion,
                    sprint_floor=10000,
                    force_19900=False,
                )
                if guard is not None:
                    action = guard
                elif win_rate < 0.60:
                    action = 'cashout'
                else:
                    action = 'challenge'
            self.last_cashout = current_cashout if action == 'cashout' else None
            return action

        cushion = getattr(self, "cushion_target", 19900)
        # Sprint phase at 19,900: only accept Five of a Kind (7,000 -> 14,000)
        if daily_coins >= cushion:
            self._in_sprint_round = True
            max_payout = get_max_round_payout(current_cashout)
            if current_cashout >= 14000:
                action = 'cashout'
            elif max_payout >= 14000:
                action = 'challenge'
            else:
                action = 'challenge'
                self.intent_to_fail = True
        else:
            guard = self.evaluate_cushion_guard(
                current_cashout=current_cashout,
                next_reward=next_reward,
                daily_coins=daily_coins,
                cushion=cushion,
                sprint_floor=14000,
                force_19900=(cushion == 19900),
            )
            if guard is not None:
                action = guard
                # In True Max Profit, even an early Five of a Kind only sprints if daily + 14,000 >= TRUE_MAX_EARLY_BENCHMARK
                if action == 'challenge' and not self.intent_to_fail:
                    if daily_coins + get_max_round_payout(current_cashout) < TRUE_MAX_EARLY_BENCHMARK:
                        self.intent_to_fail = True
            elif win_rate < 0.60:
                action = 'cashout'
            else:
                action = 'challenge'

        self.last_cashout = current_cashout if action == 'cashout' else None
        return action

    def _is_adaptive_sprint_fallback(self, daily_coins: int) -> bool:
        return self._is_adaptive_fallback()

    def notify_fail(self) -> None:
        if self._in_sprint_round:
            self._sprint_attempts += 1


TrueMaxProfitStrategy = TrueMaxCoinsStrategy
