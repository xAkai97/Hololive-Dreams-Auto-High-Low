"""Base class and common interface for all doubling strategies."""
from abc import ABC, abstractmethod
from typing import Optional


class BaseStrategy(ABC):
    """Abstract base class that all strategies must implement."""

    name: str = "Base Strategy"

    base_cash: Optional[int] = None
    last_cashout: Optional[int] = None

    def reset_round(self) -> None:
        """Reset internal round-specific state (e.g. at START_BET or HOLD_CARDS)."""
        self.base_cash = None
        self.last_cashout = None

    def start_round(self, base_cash: int, coins: int) -> None:
        """Initialize round parameters upon detecting initial payout."""
        self.base_cash = base_cash

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
