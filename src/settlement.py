"""Confirm result amounts after the count-up animation, without game strategy."""


from typing import Any

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

    def observe(self, amount, now, expected=None, timeout=_DEFAULT_TIMEOUT, fast_mode: bool = False):
        if self.started is None:
            self.started = now
        self.last_observed = amount

        # Reject impossible numbers (e.g. OCR noise like 160015 not divisible by 50 or out of bounds)
        if amount > 0 and not is_valid_settlement_amount(amount):
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
    ):
        self.settlement_reader = settlement_reader if settlement_reader is not None else SettlementReader()
        self.save_data_fn = save_data_fn
        self.recovery_mode = recovery_mode
        self.on_prompt_settlement = on_prompt_settlement
        self.has_tallied = False
        self.expected_cashout = None

    def reset_round(self, strategy=None):
        self.has_tallied = False
        self.settlement_reader.reset()
        self.expected_cashout = None
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
    ) -> int:
        """Credit a confirmed or recovered payout amount once per round."""
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
                earned = self.settlement_reader.observe(amount, now, self.expected_cashout, timeout=timeout)
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
            )

        return daily_coins, True


