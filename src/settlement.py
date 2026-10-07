"""Confirm result amounts after the count-up animation, without game strategy."""


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


class SettlementReader:
    def __init__(self, timeout: float = 8.0):
        self.timeout = timeout
        self.last_observed = 0
        self.reset()

    def reset(self):
        self.started = None
        self.candidate = None
        self.since = None
        self.samples = 0
        self.last_observed = 0

    def observe(self, amount, now, expected=None):
        if self.started is None:
            self.started = now
        self.last_observed = amount

        # Reject impossible numbers (e.g. OCR noise like 160015 not divisible by 50 or out of bounds)
        if amount > 0 and not is_valid_settlement_amount(amount):
            amount = 0

        # Never reuse samples collected during the initial animation window.
        if (now - self.started < 1.5 or amount <= 0
                or (expected is not None and amount != expected)):
            self.candidate = self.since = None
            self.samples = 0
        elif amount != self.candidate:
            self.candidate, self.since, self.samples = amount, now, 1
        else:
            self.samples += 1
        if self.samples >= 3 and now - self.since >= .6:
            return self.candidate
        if now - self.started >= self.timeout:
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
                print(tr('state_settlement_wait'))
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
                earned = self.settlement_reader.observe(amount, now, self.expected_cashout)
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
                        raise
                    print(tr('settle_manual_confirmed', amount=earned))
                    log_debug(f"[Settlement Manual] Confirmed payout: {earned}")
                elif recovery == "manual" and self.expected_cashout:
                    earned = self.expected_cashout
                    print(tr('settle_auto_recovered', observed=last_amt, expected=earned))
                    log_debug(f"[Settlement Recovery] OCR discrepancy (observed={last_amt}). Auto-recovered using expected={earned}")
                else:
                    raise

            if earned is None:
                return daily_coins, False

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

        return daily_coins, True


