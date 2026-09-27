"""Base class and common interface for all doubling strategies."""
from abc import ABC, abstractmethod
from typing import Optional


class BaseStrategy(ABC):
    """Abstract base class that all strategies must implement."""

    name: str = "Base Strategy"

    @abstractmethod
    def reset_round(self) -> None:
        """Reset internal round-specific state (e.g. at START_BET or HOLD_CARDS)."""
        pass

    @abstractmethod
    def start_round(self, base_cash: int, coins: int) -> None:
        """Initialize round parameters upon detecting initial payout."""
        pass

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

    def stage_after_credit(self, earned: int) -> Optional[int]:
        """Return the next stage index to persist, or None if strategy has no stages."""
        return None

    @property
    def expected_cash(self) -> Optional[int]:
        """Expected payout amount for this round, or None if uncalculated."""
        return None

    @property
    def complete(self) -> bool:
        """Whether this strategy has completed all its target goals."""
        return False

    @property
    def requires_ongoing_ocr(self) -> bool:
        """Whether this strategy requires reading real-time prize OCR mid-doubling."""
        return True
