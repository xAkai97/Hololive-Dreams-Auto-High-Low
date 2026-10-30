"""Base class and common interface for all doubling strategies."""
from abc import ABC, abstractmethod
from typing import Optional


def get_max_round_payout(cashout: int, cap: int = 10000) -> int:
    """Return the fixed maximum payout a hand can reach before the game auto-settles at >= cap."""
    if cashout <= 0:
        return 0
    if cashout == 10000:
        return 20000
    val = cashout
    while val < cap:
        val *= 2
    return val


EARLY_MAX_PAYOUT_BENCHMARK = 32600  # Minimum total daily coins to justify early sprint under cushion
TRUE_MAX_EARLY_BENCHMARK = 33600    # Minimum total daily coins to justify early Five of a Kind in True Max
VALID_PLAY_STYLES = ("aggressive", "default", "conservative")


def normalize_play_style(play_style: Optional[str]) -> str:
    """Normalize a play style string to 'aggressive', 'default', or 'conservative'."""
    if not play_style:
        return "default"
    val = str(play_style).strip().lower()
    return val if val in VALID_PLAY_STYLES else "default"


class BaseStrategy(ABC):
    """Abstract base class that all strategies must implement."""

    name: str = "Base Strategy"
    play_style: str = "default"

    base_cash: Optional[int] = None
    last_cashout: Optional[int] = None
    intent_to_fail: bool = False
    force_adaptive_sprint: bool = False

    def reset_round(self) -> None:
        """Reset internal round-specific state (e.g. at START_BET or HOLD_CARDS)."""
        self.base_cash = None
        self.last_cashout = None
        self.intent_to_fail = False

    def start_round(self, base_cash: int, coins: int) -> None:
        """Initialize round parameters upon detecting initial payout."""
        self.base_cash = base_cash

    def evaluate_cushion_guard(
        self,
        current_cashout: int,
        next_reward: int,
        daily_coins: int,
        cushion: int = 19800,
        sprint_floor: int = 10000,
        force_19900: bool = False,
        target_limit: int = 20000,
    ) -> Optional[str]:
        """Shared cushion boundary and early-overshoot evaluation for strategies.

        Returns:
            'cashout' if payout safely reaches the cushion ceiling (or locks in odd parity under force_19900),
            'challenge' if payout overshoots the ceiling (setting self.intent_to_fail when max_payout < benchmark),
            None if normal strategy phase rules should proceed.
        """
        strict_odd = force_19900 or (cushion == 19900 and not getattr(self, "force_adaptive_sprint", False))
        max_possible_cushion = max(1000, target_limit - 100)
        cushion_cap = min(max_possible_cushion, 19900 if strict_odd else (cushion if cushion >= max_possible_cushion else cushion + 100))

        if strict_odd:
            # 19,900 is an odd hundred ((val // 100) % 2 == 1).
            even_cap = min(19200, cushion_cap - 700)  # 19,200 leaves room for a 700 Flush
            # When daily_coins is an even hundred, only an un-doubled 700 (Flush) or 1,500 (Four of a Kind)
            # flips parity to an odd hundred; doubling 700->1400 or 1500->3000 makes it even again.
            if (daily_coins % 200) == 0:
                if (current_cashout % 200) == 100 and daily_coins + current_cashout <= cushion_cap:
                    return "cashout"
                if daily_coins + current_cashout <= even_cap and daily_coins + next_reward > even_cap:
                    return "cashout"
                if daily_coins + current_cashout > even_cap and (daily_coins + current_cashout) % 200 == 0:
                    if current_cashout >= sprint_floor and daily_coins + current_cashout >= EARLY_MAX_PAYOUT_BENCHMARK:
                        return "cashout"
                    max_payout = get_max_round_payout(current_cashout)
                    if daily_coins + max_payout < EARLY_MAX_PAYOUT_BENCHMARK:
                        self.intent_to_fail = True
                    return "challenge"
            else:
                # daily_coins is an odd hundred. We WANT to land on an odd hundred (e.g. 19,900).
                # Adding an odd hundred cashout (e.g. 700, 1500) would make total EVEN!
                # If adding current_cashout makes total even and > even_cap, we must not bank it.
                if (daily_coins + current_cashout) % 200 == 0 and daily_coins + current_cashout > even_cap:
                    # Doubling an odd hundred makes it even, which when added to odd daily keeps total ODD!
                    if daily_coins + next_reward <= cushion_cap:
                        return "challenge"
                    # If doubling would overshoot cushion_cap, check if max payout justifies sprint
                    if current_cashout >= sprint_floor and daily_coins + current_cashout >= EARLY_MAX_PAYOUT_BENCHMARK:
                        return "cashout"
                    max_payout = get_max_round_payout(current_cashout)
                    if daily_coins + max_payout < EARLY_MAX_PAYOUT_BENCHMARK:
                        self.intent_to_fail = True
                    return "challenge"

        if daily_coins + current_cashout <= cushion_cap and daily_coins + next_reward > cushion_cap:
            return "cashout"
        if daily_coins + current_cashout > cushion_cap:
            near_cap = (daily_coins + current_cashout >= target_limit) or (cushion >= target_limit - 500)
            if current_cashout >= sprint_floor and (not near_cap or daily_coins + current_cashout >= EARLY_MAX_PAYOUT_BENCHMARK):
                return "cashout"
            # Only trigger intent_to_fail if cashing out would lockout the target limit (>= target_limit)
            # or if cushion is near target_limit (>= target_limit - 500)
            if near_cap:
                max_payout = get_max_round_payout(current_cashout)
                if daily_coins + max_payout < EARLY_MAX_PAYOUT_BENCHMARK:
                    self.intent_to_fail = True
            return "challenge"
        return None

    @abstractmethod
    def decide(
        self,
        current_cashout: Optional[int] = None,
        next_reward: Optional[int] = None,
        win_rate: Optional[float] = None,
        daily_coins: Optional[int] = None,
    ) -> str:
        """Decide next action. Returns 'cashout', 'challenge', or 'stop'."""
        pass

    def guess_clicked(self) -> None:
        """Hook called when a High or Low guess icon is clicked."""
        pass

    def notify_push(self) -> None:
        """Hook called when a High-Low tie (push) occurs."""
        pass

    def confirm_success(self) -> None:
        """Hook called when a success/win transition is detected."""
        pass

    def begin_settlement(self, cashout_requested: bool) -> None:
        """Hook called when transitioning to RESULT state."""
        pass

    def notify_win(self) -> None:
        """Hook called when a round completes with a win/cashout."""
        pass

    def notify_fail(self) -> None:
        """Hook called when a round ends in a fail/bust."""
        pass

    @property
    def expected_cash(self) -> Optional[int]:
        """Expected payout amount for this round, or None if uncalculated."""
        return self.last_cashout

    @property
    def requires_ongoing_ocr(self) -> bool:
        """Whether this strategy requires reading real-time prize OCR mid-doubling."""
        return True
