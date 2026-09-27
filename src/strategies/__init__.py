"""Strategy package providing modular doubling policies for Hololive Dreams Auto Bot."""
from typing import Optional, Union, Type

from strategies.base import BaseStrategy
from strategies.legacy_101 import Legacy101Strategy
from strategies.three_stages import ThreeStagesStrategy
from strategies.max_profit import MaxProfitStrategy
from strategies.fastest_clear import FastestClearStrategy
from strategies.balanced import BalancedStrategy
from strategies.aggressive_balanced import AggressiveBalancedStrategy
from strategies.adaptive_rush import AdaptiveRushStrategy
from strategies.grinder import GrinderStrategy
from strategies.custom_parametric import CustomParametricStrategy

__all__ = [
    "BaseStrategy",
    "Legacy101Strategy",
    "ThreeStagesStrategy",
    "MaxProfitStrategy",
    "FastestClearStrategy",
    "BalancedStrategy",
    "AggressiveBalancedStrategy",
    "AdaptiveRushStrategy",
    "GrinderStrategy",
    "CustomParametricStrategy",
    "get_strategy",
    "STRATEGY_REGISTRY",
]

STRATEGY_REGISTRY: dict[str, Type[BaseStrategy]] = {
    "legacy_101": Legacy101Strategy,
    "three_stages": ThreeStagesStrategy,
    "max_profit": MaxProfitStrategy,
    "fastest_clear": FastestClearStrategy,
    "balanced": BalancedStrategy,
    "aggressive_balanced": AggressiveBalancedStrategy,
    "adaptive_rush": AdaptiveRushStrategy,
    "grinder": GrinderStrategy,
    "custom_parametric": CustomParametricStrategy,
}


def get_strategy(name: str, stage: int = 0, **kwargs) -> BaseStrategy:
    """Factory function to instantiate a strategy by key or name."""
    normalized = str(name).strip().lower()
    for key, cls in STRATEGY_REGISTRY.items():
        if normalized == key.lower():
            if cls is ThreeStagesStrategy:
                return cls(stage=stage, **kwargs)
            return cls(**kwargs)

    raise ValueError(f"Unknown strategy mode: '{name}'. Available: {list(STRATEGY_REGISTRY.keys())}")
