"""Confirm result amounts after the count-up animation, without game strategy."""


from typing import Any, Optional

try:
    from auto_bot import SafeStop
except ImportError:
    class SafeStop(Exception):
        pass


class SettlementTimeoutError(RuntimeError):
    """Raised when settlement payout reading fails to stabilize within timeout."""

    def __init__(self, message, last_amount=0, expected=None):
        super().__init__(message)
        self.last_amount = last_amount
        self.expected = expected


def is_valid_settlement_amount(amount: int) -> bool:
    """Validate that the payout is a plausible number in the Hololive Dreams mini-game.

    Payouts must be positive integers, multiples of 50, and <= 60000.
    """
    if not isinstance(amount, int):
        return False
    return 50 <= amount <= 60000 and (amount % 50 == 0)


def _get_max_hand_payout(base_prize: int) -> int:
    """Return the maximum possible single-round payout for a starting hand prize.

    In Hololive Dreams, doubling up stops once the payout reaches >= 10,000
    (and Royal Straight Flush 10,000 can double once to 20,000).
    """
    if base_prize <= 0:
        return 60000
    if base_prize == 10000:
        return 20000
    cash = base_prize
    while cash < 10000:
        cash *= 2
    return cash


def is_valid_hand_payout(amount: int, base_prize: int) -> bool:
    """Validate that the payout is a valid power-of-two multiple of the starting hand prize."""
    if not isinstance(amount, int) or amount <= 0:
        return False
    if not isinstance(base_prize, int) or base_prize <= 0:
        return is_valid_settlement_amount(amount)
    if amount < base_prize or amount > _get_max_hand_payout(base_prize):
        return False
    if amount % base_prize != 0:
        return False
    ratio = amount // base_prize
    return (ratio & (ratio - 1)) == 0 and is_valid_settlement_amount(amount)


def validate_and_correct_payout(
    observed_amount: int,
    base_prize: Optional[int],
    expected: Optional[int] = None,
    win_count: Optional[int] = None,
) -> tuple[int, bool, bool]:
    """Validate observed settlement payout against hand base prize and correct if possible.

    Returns:
        (final_amount, is_valid, was_corrected)
    """
    try:
        from auto_bot import log_debug
    except ImportError:
        def log_debug(msg): pass
    try:
        from localization import tr
    except ImportError:
        def tr(key, **kwargs): return f"[{key}]"

    predicted_by_wins = (
        base_prize * (2 ** win_count)
        if (isinstance(base_prize, int) and base_prize > 0 and isinstance(win_count, int) and 0 <= win_count <= 10)
        else None
    )
    eff_expected = expected if (expected is not None and is_valid_settlement_amount(expected)) else predicted_by_wins

    if not isinstance(observed_amount, int) or observed_amount <= 0:
        if eff_expected is not None and is_valid_settlement_amount(eff_expected):
            if base_prize is None or is_valid_hand_payout(eff_expected, base_prize):
                return eff_expected, True, True
        return observed_amount, False, False

    if base_prize is None or base_prize <= 0:
        if is_valid_settlement_amount(observed_amount):
            return observed_amount, True, False
        return observed_amount, False, False

    # Check if observed amount is directly valid
    if is_valid_hand_payout(observed_amount, base_prize):
        return observed_amount, True, False

    # Validation failed: scanned amount is not a valid power-of-two multiple of base_prize
    print(tr('warn_payout_mismatch', observed=observed_amount, base=base_prize))
    log_debug(f"[Payout Warning] Validation failed: scanned {observed_amount} is not a valid power-of-two multiple of base hand {base_prize}!")

    # Attempt correction
    corrected = None
    max_hand = _get_max_hand_payout(base_prize)
    valid_multipliers = [base_prize * (2 ** k) for k in range(12) if base_prize * (2 ** k) <= max_hand]

    # Priority 1: If expected cashout (or base_prize * 2^win_count) matches a valid power-of-two multiple
    if eff_expected is not None and is_valid_hand_payout(eff_expected, base_prize):
        corrected = eff_expected

    # Priority 2: Missing trailing zero (e.g. OCR read 1120 instead of 11200, 280 instead of 2800)
    elif is_valid_hand_payout(observed_amount * 10, base_prize):
        corrected = observed_amount * 10

    # Priority 3: Trailing noise digit (e.g. OCR read 112005 instead of 11200, or 28005 instead of 2800)
    elif (not is_valid_settlement_amount(observed_amount) or observed_amount > 20000) and is_valid_hand_payout(observed_amount // 10, base_prize):
        corrected = observed_amount // 10

    # Priority 4: Unique prefix match among valid multipliers when a trailing digit was truncated
    else:
        obs_str = str(observed_amount)
        matches = [m for m in valid_multipliers if m > observed_amount and str(m).startswith(obs_str)]
        if len(matches) == 1:
            corrected = matches[0]
        else:
            # Priority 5: Edit-distance-1 single digit substitution (e.g. 11280 -> 11200, 5680 -> 5600)
            ed1_matches = [
                m for m in valid_multipliers
                if len(str(m)) == len(obs_str)
                and sum(1 for a, b in zip(str(m), obs_str) if a != b) == 1
            ]
            if len(ed1_matches) == 1:
                corrected = ed1_matches[0]

    if corrected is not None and is_valid_hand_payout(corrected, base_prize):
        print(tr('settle_payout_corrected', observed=observed_amount, corrected=corrected, base=base_prize))
        log_debug(f"[Settlement Correction] Corrected payout: scanned={observed_amount} -> corrected={corrected} (base={base_prize}, expected={eff_expected})")
        return corrected, True, True

    return observed_amount, False, False


_DEFAULT_TIMEOUT = object()


class SettlementReader:
    def __init__(self, timeout: float = 8.0, fast_mode: bool = False):
        self.timeout = timeout
        self.fast_mode = bool(fast_mode)
        self.last_observed = 0
        self.last_valid_observed = 0
        self.reset()

    def reset(self):
        self.started = None
        self.candidate = None
        self.since = None
        self.samples = 0
        self.last_observed = 0
        self.last_valid_observed = 0

    def observe(self, amount, now, expected=None, timeout=_DEFAULT_TIMEOUT, fast_mode: bool = False, base_prize: Optional[int] = None):
        if self.started is None:
            self.started = now
        self.last_observed = amount

        # Reject impossible numbers (e.g. OCR noise like 160015 not divisible by 50 or out of bounds)
        if amount > 0 and not is_valid_settlement_amount(amount):
            if base_prize and is_valid_hand_payout(amount * 10, base_prize):
                amount = amount * 10
                self.last_valid_observed = amount
            else:
                amount = 0
        elif amount > 0 and base_prize and not is_valid_hand_payout(amount, base_prize):
            if is_valid_hand_payout(amount // 10, base_prize):
                amount = amount // 10
                self.last_valid_observed = amount
            else:
                amount = 0
        elif amount > 0:
            self.last_valid_observed = amount

        eff_timeout = self.timeout if timeout is _DEFAULT_TIMEOUT else timeout
        is_fast = self.fast_mode or fast_mode or (eff_timeout is None)

        if is_fast and amount > 0 and expected is not None and amount == expected:
            self.candidate = amount
            self.since = now
            self.samples = max(1, self.samples + 1)
            return amount

        min_anim_wait = 0.0 if is_fast else 1.5
        mismatch_expected = (
            expected is not None
            and amount != expected
            and (not is_fast or (amount < expected and now - self.started < 1.5))
        )
        # Never reuse samples collected during the initial animation window.
        if now - self.started < min_anim_wait or amount <= 0 or mismatch_expected:
            self.candidate = self.since = None
            self.samples = 0
        elif amount != self.candidate:
            self.candidate, self.since, self.samples = amount, now, 1
        else:
            self.samples += 1

        if is_fast and self.samples >= 2 and self.since is not None and now - self.since >= .10:
            return self.candidate
        if self.samples >= 3 and self.since is not None and now - self.since >= .6:
            return self.candidate
        if eff_timeout is not None and now - self.started >= eff_timeout:
            raise SettlementTimeoutError(
                'Settlement amount could not be confirmed reliably; stopped and excluded from ledger. Please check the settlement screen and daily balance.',
                last_amount=self.last_observed,
                expected=expected,
            )
        return None


class SettlementManager:
    """Coordinates settlement payout observation, validation, and accounting for RESULT screens."""

    def __init__(
        self,
        settlement_reader=None,
        save_data_fn=None,
        recovery_mode: str = "auto",
        on_prompt_settlement=None,
        base_prize: Optional[int] = None,
    ):
        self.settlement_reader = settlement_reader if settlement_reader is not None else SettlementReader()
        self.save_data_fn = save_data_fn
        self.recovery_mode = recovery_mode
        self.on_prompt_settlement = on_prompt_settlement
        self.has_tallied = False
        self.expected_cashout = None
        self.base_prize = base_prize

    def reset_round(self, strategy=None):
        self.has_tallied = False
        self.settlement_reader.reset()
        self.expected_cashout = None
        self.base_prize = None
        if strategy is not None:
            strategy.reset_round()

    def credit_payout(
        self,
        earned: int,
        daily_coins: int,
        daily_fails: int,
        strategy=None,
        on_stats_update=None,
        ticket_cost: int = 50,
        base_prize: Optional[int] = None,
    ) -> int:
        """Credit a confirmed or recovered payout amount once per round."""
        eff_base = base_prize or self.base_prize
        if eff_base is None and strategy is not None:
            eff_base = getattr(strategy, "base_cash", None)

        if eff_base and not is_valid_hand_payout(earned, eff_base):
            win_cnt = getattr(strategy, "win_count", None) if strategy is not None else None
            earned, valid, _ = validate_and_correct_payout(
                earned, eff_base, self.expected_cashout, win_count=win_cnt
            )
            if not valid and not is_valid_settlement_amount(earned):
                return daily_coins

        if self.has_tallied or not is_valid_settlement_amount(earned):
            return daily_coins
        from localization import tr

        daily_coins += earned
        net_profit = daily_coins - (daily_fails * ticket_cost)
        print(tr('settle_success', earned=earned, coins=daily_coins, fails=daily_fails, profit=net_profit))
        try:
            from auto_bot import log_debug
            log_debug(f"[Settlement Credited] +{earned} coins | Daily Total: {daily_coins} | Fails: {daily_fails} | Net: {net_profit}")
        except ImportError:
            pass
        if on_stats_update:
            on_stats_update(daily_coins, daily_fails, net_profit)

        if strategy is not None:
            strategy.notify_win()

        if self.save_data_fn:
            self.save_data_fn(daily_coins, daily_fails)
        self.has_tallied = True
        return daily_coins

    def process_result(
        self,
        amount: int,
        now: float,
        daily_coins: int,
        daily_fails: int,
        strategy=None,
        on_stats_update=None,
        ticket_cost: int = 50,
        on_prompt_settlement=None,
        timeout: Any = _DEFAULT_TIMEOUT,
        base_prize: Optional[int] = None,
    ) -> tuple[int, bool]:
        """
        Process an observed payout amount during the RESULT state.

        Returns:
            (new_daily_coins, can_proceed)
            can_proceed is True when the payout has been settled (or was already settled),
            allowing the caller to click confirm. False when reading is still stabilizing.
        """
        if not self.has_tallied:
            from localization import tr

            eff_base = base_prize or self.base_prize
            if eff_base is None and strategy is not None:
                eff_base = getattr(strategy, "base_cash", None)

            if self.settlement_reader.started is None:
                print(f"\n" + tr('state_settlement_wait'))
            if strategy is not None:
                cashout_requested = (self.expected_cashout is not None)
                strategy.begin_settlement(cashout_requested)
                if cashout_requested:
                    if getattr(strategy, "expected_cash", None) is not None:
                        self.expected_cashout = strategy.expected_cash
                else:
                    self.expected_cashout = None

            prompt_fn = on_prompt_settlement or self.on_prompt_settlement
            try:
                earned = self.settlement_reader.observe(amount, now, self.expected_cashout, timeout=timeout, base_prize=eff_base)
            except RuntimeError as err:
                recovery = self.recovery_mode or "auto"
                last_amt = getattr(err, "last_amount", amount)
                try:
                    from auto_bot import log_debug
                except ImportError:
                    def log_debug(msg): pass

                if recovery == "auto" and self.expected_cashout:
                    earned = self.expected_cashout
                    print(tr('settle_auto_recovered', observed=last_amt, expected=earned))
                    log_debug(f"[Settlement Recovery] OCR discrepancy (observed={last_amt}). Auto-recovered using expected={earned}")
                elif eff_base and recovery == "auto":
                    win_cnt = getattr(strategy, "win_count", None) if strategy is not None else None
                    corr, valid, _ = validate_and_correct_payout(
                        last_amt, eff_base, self.expected_cashout, win_count=win_cnt
                    )
                    if valid:
                        earned = corr
                    elif prompt_fn:
                        earned = prompt_fn(self.expected_cashout, last_amt)
                        if earned is None:
                            raise SafeStop("Settlement confirmation cancelled or stopped by user.")
                    else:
                        raise SafeStop(f"Settlement OCR recovery failed: {err}") from err
                elif recovery == "manual" and prompt_fn:
                    earned = prompt_fn(self.expected_cashout, last_amt)
                    if earned is None:
                        raise SafeStop("Settlement confirmation cancelled or stopped by user.")
                    print(tr('settle_manual_confirmed', amount=earned))
                    log_debug(f"[Settlement Manual] Confirmed payout: {earned}")
                elif recovery == "manual" and self.expected_cashout:
                    earned = self.expected_cashout
                    print(tr('settle_auto_recovered', observed=last_amt, expected=earned))
                    log_debug(f"[Settlement Recovery] OCR discrepancy (observed={last_amt}). Auto-recovered using expected={earned}")
                else:
                    raise SafeStop(f"Settlement OCR recovery failed: {err}") from err

            if earned is None:
                return daily_coins, False

            daily_coins = self.credit_payout(
                earned=earned,
                daily_coins=daily_coins,
                daily_fails=daily_fails,
                strategy=strategy,
                on_stats_update=on_stats_update,
                ticket_cost=ticket_cost,
                base_prize=eff_base,
            )

        return daily_coins, True


