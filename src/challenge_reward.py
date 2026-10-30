"""Validate and stabilize challenge OCR before any strategy sees a number."""

try:
    from poker_core import VALID_PRIZES as PRIZES
except ImportError:
    PRIZES = (200, 400, 700, 800, 1500, 3000, 7000, 10000)

try:
    from auto_bot import SafeStop
except ImportError:
    class SafeStop(Exception):
        pass


VALID_NEXT_REWARDS = frozenset(prize * 2**n for prize in PRIZES for n in range(1, 33))


def valid_next_reward(value):
    return value in VALID_NEXT_REWARDS


def _is_power_of_two_multiple(value: int, base: int) -> bool:
    if not isinstance(value, int) or not isinstance(base, int):
        return False
    if base <= 0 or value < base or (value % base) != 0:
        return False
    ratio = value // base
    return (ratio & (ratio - 1)) == 0


class ChallengeRewardReader:
    def __init__(self, fast_mode: bool = False):
        self.fast_mode = bool(fast_mode)
        self.reset_round()

    def reset_round(self):
        self.last = None
        self.reset_prompt()

    def reset_prompt(self):
        self.started = self.candidate = self.since = None
        self.samples = 0

    def observe(self, value, now, timeout=8.0, fast_mode: bool = False):
        if self.started is None:
            self.started = now
        plausible = valid_next_reward(value)
        if self.last is not None:
            plausible = plausible and _is_power_of_two_multiple(value, self.last)
        if not plausible:
            self.candidate = self.since = None
            self.samples = 0
        elif self.candidate != value:
            self.candidate, self.since, self.samples = value, now, 1
        else:
            self.samples += 1
        is_fast = self.fast_mode or fast_mode or (timeout is None)
        if is_fast and self.samples >= 1 and self.candidate is not None:
            self.last = value
            return value
        if self.samples >= 2 and now - self.since >= .25:
            self.last = value
            return value
        if timeout is not None and now - self.started >= timeout:
            raise SafeStop('Challenge payout cannot be confirmed; stopped. Will not use inaccurate or fallback payout to decide doubling. Please check the game screen.')
        return None
