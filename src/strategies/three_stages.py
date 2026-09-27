"""Three phases driven by confirmed wins, never by ongoing reward OCR.

Ported from the original PhasedStrategy by mwty-0415.
Stage 0: Max double-up (game auto-settles at ~10k)
Stage 1: Controlled wins targeting ~6,400 cashout
Stage 2: Max double-up again for final big win
"""
from typing import Optional

from challenge_reward import PRIZES
from strategies.base import BaseStrategy


class ThreeStagesStrategy(BaseStrategy):
    """Three stages strategy: Maximize -> Win Count -> Maximize."""

    name: str = "3 Stages: Max → Win Count → Max"

    def __init__(self, stage: int = 0):
        if type(stage) is not int or not 0 <= stage <= 3:
            raise ValueError('Invalid saved strategy stage')
        self.stage = stage
        self.reset_round()

    @property
    def complete(self) -> bool:
        return self.stage == 3

    @property
    def requires_ongoing_ocr(self) -> bool:
        return False

    def reset_round(self) -> None:
        self.base_cash: Optional[int] = None
        self.successes: int = 0
        self.pending_guess: bool = False
        self.target_wins: Optional[int] = None
        self.settling: bool = False

    def start_round(self, base_cash: int, coins: int) -> None:
        if base_cash not in PRIZES:
            raise ValueError('Unconfirmed initial poker reward')
        if self.base_cash is not None:
            return
        self.base_cash = base_cash
        if self.stage == 1:
            candidates = [n for n in range(32) if coins + base_cash * 2**n < 20000]
            if not candidates:
                raise RuntimeError('Initial payout for this round cannot reserve cap room for Stage 3; please handle manually.')
            self.target_wins = min(candidates, key=lambda n: (abs(base_cash * 2**n - 6400), n))

    @property
    def expected_cash(self) -> Optional[int]:
        return None if self.base_cash is None else self.base_cash * 2**self.successes

    def guess_clicked(self) -> None:
        if self.base_cash is None:
            raise RuntimeError('Initial hand payout not yet confirmed; cannot safely count wins. Please start from a fresh round.')
        self.pending_guess = True

    def confirm_success(self) -> None:
        # Repeated success frames and repeated clicks consume one pending guess.
        if self.pending_guess:
            self.successes += 1
            self.pending_guess = False

    def begin_settlement(self, cashout_requested: bool) -> None:
        if not self.settling:
            # At the game limit, the final win leads straight to RESULT.
            if not cashout_requested:
                self.confirm_success()
            self.settling = True

    def decide(
        self,
        current_cashout: Optional[int] = None,
        next_reward: Optional[int] = None,
        win_rate: Optional[float] = None,
        daily_coins: Optional[int] = None,
    ) -> str:
        if self.complete:
            return 'stop'
        if self.base_cash is None:
            raise RuntimeError('Initial hand payout not yet confirmed.')
        if self.stage == 1:
            if self.target_wins is None:
                raise RuntimeError('Target wins not calculated for stage 1.')
            if self.successes >= self.target_wins:
                return 'cashout'
        return 'challenge'

    def stage_after_credit(self, earned: int) -> int:
        # A confirmed successful settlement advances the phase independently
        # of the numeric target. The settlement reader verifies the amount.
        return min(3, self.stage + 1)
