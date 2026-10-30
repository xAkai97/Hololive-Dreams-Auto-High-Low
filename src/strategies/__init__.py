"""Strategy package providing modular doubling policies for Hololive Dreams Auto Bot."""
from typing import Any, Callable, Optional, Union, Type

from strategies.base import BaseStrategy, get_max_round_payout, normalize_play_style, VALID_PLAY_STYLES
from strategies.max_profit import (
    MaxProfitStrategy,
    AdaptiveMaxProfitStrategy,
    TrueMaxProfitStrategy,
    TrueMaxCoinsStrategy,
)
from strategies.fastest_clear import FastestClearStrategy
from strategies.balanced import BalancedStrategy
from strategies.aggressive_balanced import AggressiveBalancedStrategy
from strategies.adaptive_rush import AdaptiveRushStrategy
from strategies.grinder import GrinderStrategy
from strategies.custom_parametric import CustomParametricStrategy
from strategies.modifiers import apply_strategy_modifiers

__all__ = [
    "BaseStrategy",
    "get_max_round_payout",
    "normalize_play_style",
    "VALID_PLAY_STYLES",
    "MaxProfitStrategy",
    "AdaptiveMaxProfitStrategy",
    "TrueMaxProfitStrategy",
    "TrueMaxCoinsStrategy",
    "FastestClearStrategy",
    "BalancedStrategy",
    "AggressiveBalancedStrategy",
    "AdaptiveRushStrategy",
    "GrinderStrategy",
    "CustomParametricStrategy",
    "get_strategy",
    "strategy_kwargs_from_config",
    "apply_strategy_modifiers",
    "STRATEGY_REGISTRY",
]

STRATEGY_REGISTRY: dict[str, Type[BaseStrategy]] = {
    # Category A: Maximum Net Profit (~30k Wallet Gain)
    "balanced": BalancedStrategy,
    "max_profit": MaxProfitStrategy,
    # Category B: Speed & Stability Grinding
    "fastest_clear": FastestClearStrategy,
    "adaptive_rush": AdaptiveRushStrategy,
    "grinder": GrinderStrategy,
    # Category C: Specialized & Trophy
    "custom_parametric": CustomParametricStrategy,
    "true_max_coins": TrueMaxCoinsStrategy,
}


def get_strategy(name: str, **kwargs) -> BaseStrategy:
    """Factory function to instantiate a strategy by key or name."""
    normalized = str(name).strip().lower()
    if normalized in ("adaptive_max_profit", "maxprofit"):
        normalized = "max_profit"
    elif normalized in ("true_max_profit", "true_max_coins_possible", "truemaxprofit", "truemaxcoins"):
        normalized = "true_max_coins"
    elif normalized in ("aggressive_balanced", "aggressivebalanced"):
        return AggressiveBalancedStrategy(**kwargs)

    for key, cls in STRATEGY_REGISTRY.items():
        if normalized == key.lower():
            return cls(**kwargs)

    raise ValueError(f"Unknown strategy mode: '{name}'. Available: {list(STRATEGY_REGISTRY.keys())}")


# config.json key -> (CustomParametricStrategy kwarg, converter).
# GUI "Cushion Target" is the daily-coin threshold that enters sprint mode;
# GUI "Sprint Target" is the minimum cashout accepted while sprinting.
_CUSTOM_PARAM_MAP: dict[str, tuple[str, Callable[[Any], Any]]] = {
    "param_min_win_rate": ("min_win_rate", lambda v: float(v) / 100.0),
    "param_cushion_target": ("sprint_threshold", int),
    "param_sprint_target": ("sprint_cashout", int),
    "param_cashout_target": ("cashout_target", int),
    "param_max_doubles": ("max_doubles", int),
    "param_drop_seven_eight": ("drop_on_seven_eight", bool),
    "param_fail_safety_limit": ("fail_safety_limit", int),
}


def strategy_kwargs_from_config(mode: str, config: dict) -> dict:
    """Translate saved config values into constructor kwargs for ``mode``."""
    norm = str(mode).strip().lower()
    kwargs = {}
    if "play_style" in config and config["play_style"] is not None:
        style = normalize_play_style(config["play_style"])
        if style != "default":
            kwargs["play_style"] = style
    if norm in ("true_max_coins", "true_max_profit", "true_max_coins_possible"):
        if "hunt_14k_attempts" in config and config["hunt_14k_attempts"] is not None:
            try:
                kwargs["hunt_14k_attempts"] = int(config["hunt_14k_attempts"])
            except (TypeError, ValueError):
                pass
        return kwargs
    if norm != "custom_parametric":
        return kwargs
    for key, (kwarg, convert) in _CUSTOM_PARAM_MAP.items():
        if key in config and config[key] is not None:
            try:
                kwargs[kwarg] = convert(config[key])
            except (TypeError, ValueError):
                pass
    return kwargs
