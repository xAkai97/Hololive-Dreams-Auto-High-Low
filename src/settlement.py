"""Confirm result amounts after the count-up animation, without game strategy."""


class SettlementReader:
    def __init__(self):
        self.reset()

    def reset(self):
        self.started = None
        self.candidate = None
        self.since = None
        self.samples = 0

    def observe(self, amount, now, expected=None):
        if self.started is None:
            self.started = now
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
        if now - self.started >= 8:
            raise RuntimeError('Settlement amount could not be confirmed reliably; stopped and excluded from ledger. Please check the settlement screen and daily balance.')
        return None


class SettlementManager:
    """Coordinates settlement payout observation, validation, and accounting for RESULT screens."""

    def __init__(self, settlement_reader=None, save_data_fn=None):
        self.settlement_reader = settlement_reader if settlement_reader is not None else SettlementReader()
        self.save_data_fn = save_data_fn
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
            from strategies import ThreeStagesStrategy

            if self.settlement_reader.started is None:
                print(tr('state_settlement_wait'))
            if strategy is not None:
                cashout_requested = (self.expected_cashout is not None)
                strategy.begin_settlement(cashout_requested)
                if isinstance(strategy, ThreeStagesStrategy):
                    if getattr(strategy, "expected_cash", None) is not None:
                        self.expected_cashout = strategy.expected_cash
                elif cashout_requested:
                    if getattr(strategy, "expected_cash", None) is not None:
                        self.expected_cashout = strategy.expected_cash
                else:
                    self.expected_cashout = None

            earned = self.settlement_reader.observe(amount, now, self.expected_cashout)
            if earned is None:
                return daily_coins, False

            daily_coins += earned
            net_profit = daily_coins - (daily_fails * ticket_cost)
            print(tr('settle_success', earned=earned, coins=daily_coins, fails=daily_fails, profit=net_profit))
            if on_stats_update:
                on_stats_update(daily_coins, daily_fails, net_profit)

            if self.save_data_fn:
                if strategy is not None and strategy.stage_after_credit(earned) is not None:
                    next_stage = strategy.stage_after_credit(earned)
                    self.save_data_fn(daily_coins, daily_fails, next_stage)
                    strategy.stage = next_stage
                else:
                    self.save_data_fn(daily_coins, daily_fails)
            self.has_tallied = True

        return daily_coins, True

