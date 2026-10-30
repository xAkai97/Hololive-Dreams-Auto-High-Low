"""Aggressive Balanced strategy — backward-compatible alias for BalancedStrategy(play_style='aggressive')."""
from strategies.balanced import BalancedStrategy


class AggressiveBalancedStrategy(BalancedStrategy):
    """Higher profit Balanced variant targeting ~28,000-30,000 coins (Balanced with 'aggressive' play style)."""

    name: str = "Aggressive Balanced (~28k)"
    cushion_target: int = 19800

    def __init__(self, play_style: str = "aggressive"):
        super().__init__(play_style=play_style)

