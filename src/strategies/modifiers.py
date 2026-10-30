"""Runtime strategy modifiers and overrides engine.

Provides modular overrides that can be applied to any doubling strategy:
1. Defensive Bailouts:
   - Bail on 6, 7, 8, 9 (mod_drop_6789): Drop out on wide middle danger zone in cushion phase.
   - Bail on 7 & 8 (mod_drop_78): Early cashout on 50/50 trap cards in cushion phase.
   - Bail on 8 (mod_drop_8): Early cashout on neutral 50/50 coin flip card (50.0%).
2. Small Hand Free-Roll (mod_free_roll): Always double small payouts (<= 200).
3. Fast Build (mod_fast_build): Force double if next reward still safely <= cushion_cap.
4. Force 19,900 Odd Cushion (mod_force_19900): Parity-aware cushion building to 19,900.
5. Opportunistic Card Overrides:
   - A & 2 (opp_a2, 100.0%)
   - 3 & K (opp_3k, ~91.7%)
   - 4 & Q (opp_4q, ~83.3%)
   - 5 & J (opp_5j, 75.0%)
   - 6 & 10 (opp_610, ~66.7%)
   - 7 & 9 (opp_79, ~58.3%)
   - 8 (opp_8, 50.0%)
6. Sprint Floors:
   - Hunt 14k Sprint (mod_hunt_14k): Hunts Five of a Kind (7,000 -> 14,000) with optional max attempts.
   - Mega Sprint Floor >= 12,800 (mod_mega_sprint): Pushes for 32k+ cap.
   - Sprint Floor >= 11,200 (mod_sprint_floor): Pushes past 10,000 to guarantee >= 30,000 daily total.
"""
from typing import Optional, Tuple

from strategies.base import get_max_round_payout, EARLY_MAX_PAYOUT_BENCHMARK


def apply_strategy_modifiers(
    decision: str,
    card_val: Optional[int],
    current_cashout: int,
    next_reward: int,
    daily_coins: int,
    target_limit: int = 20000,
    cushion_target: int = 19800,
    opp_a2: bool = True,
    opp_3k: bool = False,
    opp_4q: bool = False,
    opp_5j: bool = False,
    opp_610: bool = False,
    opp_79: bool = False,
    opp_8: bool = False,
    mod_fast_build: bool = False,
    mod_drop_78: bool = False,
    mod_drop_6789: bool = False,
    mod_drop_8: bool = False,
    mod_free_roll: bool = False,
    mod_sprint_floor: bool = False,
    mod_mega_sprint: bool = False,
    mod_force_19900: bool = False,
    mod_hunt_14k: bool = False,
    hunt_14k_attempts: int = 0,
    sprint_attempts: int = 0,
    force_adaptive_sprint: bool = False,
    win_rate: Optional[float] = None,
) -> Tuple[str, Optional[str]]:
    """Applies active modifiers to a strategy decision.

    Returns:
        (final_decision, override_reason)
        final_decision: 'challenge' or 'cashout' (or 'stop')
        override_reason: None if un-modified, or descriptive key.
    """
    if decision == "stop":
        return "stop", None

    current_cashout = current_cashout or 0
    next_reward = next_reward or (current_cashout * 2)
    daily_coins = daily_coins or 0

    if force_adaptive_sprint:
        mod_force_19900 = False
        mod_hunt_14k = False

    if mod_hunt_14k and hunt_14k_attempts > 0 and sprint_attempts >= hunt_14k_attempts:
        mod_hunt_14k = False

    # If Force 19,900 is active but daily is an even total > 19,200, 19,900 is unreachable
    # Treat daily >= cushion_target as sprint phase
    force_19900_unreachable = mod_force_19900 and (daily_coins % 200 == 0) and (daily_coins > 19200)

    eff_cushion = 19900 if (mod_force_19900 and not force_19900_unreachable) else cushion_target
    max_cushion_limit = max(1000, target_limit - 100)
    cushion_cap = min(max_cushion_limit, 19900 if mod_force_19900 else (cushion_target if cushion_target >= max_cushion_limit else cushion_target + 100))

    # 0. Force 19,900 Odd Cushion parity rules when under 19,900 and not in unreachable state
    if mod_force_19900 and not force_19900_unreachable and current_cashout > 0 and daily_coins < 19900:
        even_cap = min(19200, cushion_cap - 700)
        if (daily_coins % 200) == 0:
            if (current_cashout % 200) == 100 and daily_coins + current_cashout <= cushion_cap:
                return "cashout", "mod_force_19900"
            if (daily_coins + current_cashout) % 200 == 0:
                if daily_coins + current_cashout <= even_cap and daily_coins + next_reward > even_cap:
                    return "cashout", "mod_force_19900"
                if daily_coins + current_cashout > even_cap and current_cashout <= 10000:
                    if daily_coins + get_max_round_payout(current_cashout) < EARLY_MAX_PAYOUT_BENCHMARK:
                        return "challenge", "mod_force_19900_fail"
                    return "challenge", "mod_force_19900"
        else:
            # Odd daily total
            if (daily_coins + current_cashout) % 200 == 0 and daily_coins + current_cashout > even_cap:
                if daily_coins + next_reward <= cushion_cap:
                    return "challenge", "mod_force_19900"
                if current_cashout <= 10000:
                    if daily_coins + get_max_round_payout(current_cashout) < EARLY_MAX_PAYOUT_BENCHMARK:
                        return "challenge", "mod_force_19900_fail"
                    return "challenge", "mod_force_19900"

    # 1. Defensive Bailouts during cushion phase (< eff_cushion, and safe to bank <= cushion_cap)
    if (
        not mod_fast_build
        and current_cashout > 0
        and daily_coins < eff_cushion
        and daily_coins + current_cashout <= cushion_cap
        and decision == "challenge"
    ):
        if mod_drop_6789 and card_val in (6, 7, 8, 9):
            return "cashout", "mod_drop_6789"
        if mod_drop_78 and card_val in (7, 8):
            return "cashout", "mod_drop_78"
        if mod_drop_8 and card_val == 8:
            return "cashout", "mod_drop_8"

    # 2. Small Hand Free-Roll: Force doubling small initial hands (<= 200)
    if mod_free_roll and decision == "cashout" and current_cashout <= 200:
        max_allow = 19200 if (mod_force_19900 and (daily_coins % 200) == 0) else (target_limit - 1)
        if daily_coins + next_reward <= max_allow:
            return "challenge", "mod_free_roll"

    # 3. Fast Build: If strategy wanted to cash out early, but next reward safely fits within cushion_cap
    if mod_fast_build and decision == "cashout":
        max_fast = 19200 if (mod_force_19900 and (daily_coins % 200) == 0 and (next_reward % 200) == 0) else cushion_cap
        if daily_coins + next_reward <= max_fast:
            return "challenge", "mod_fast_build"

    # 4. Opportunistic High-Chance Card Override (strictly under daily target limit)
    # Exclude cards actively subject to defensive bailouts during cushion phase
    bail_cards = set()
    if daily_coins < eff_cushion:
        if mod_drop_6789:
            bail_cards.update((6, 7, 8, 9))
        if mod_drop_78:
            bail_cards.update((7, 8))
        if mod_drop_8:
            bail_cards.add(8)

    if not mod_fast_build and decision == "cashout" and card_val is not None and card_val not in bail_cards:
        should_opp = (
            (card_val in (2, 14) and opp_a2) or
            (card_val in (3, 13) and opp_3k) or
            (card_val in (4, 12) and opp_4q) or
            (card_val in (5, 11) and opp_5j) or
            (card_val in (6, 10) and opp_610) or
            (card_val in (7, 9) and opp_79) or
            (card_val == 8 and opp_8)
        )
        max_opp = 19200 if (mod_force_19900 and (daily_coins % 200) == 0 and (next_reward % 200) == 0) else (target_limit - 1)
        if should_opp and (daily_coins + next_reward <= max_opp):
            return "challenge", "opportunistic_card"

    # 5. Sprint Floors (during sprint phase: daily >= eff_cushion)
    if daily_coins >= eff_cushion:
        if 0 < current_cashout < 10000 and decision == "challenge":
            max_payout = get_max_round_payout(current_cashout)
            if mod_hunt_14k and max_payout < 14000:
                return "challenge", "mod_hunt_14k_fail"
            if mod_mega_sprint and max_payout < 12800:
                return "challenge", "mod_mega_sprint_fail"
            if mod_sprint_floor and max_payout < 11200:
                return "challenge", "mod_sprint_floor_fail"
        if decision == "cashout":
            if mod_hunt_14k and current_cashout < 14000:
                return "challenge", "mod_hunt_14k"
            if mod_mega_sprint and current_cashout < 12800:
                return "challenge", "mod_mega_sprint"
            if mod_sprint_floor and current_cashout < 11200:
                return "challenge", "mod_sprint_floor"

    return decision, None
