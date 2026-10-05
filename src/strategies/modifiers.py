"""Runtime strategy modifiers and overrides engine.

Provides modular overrides that can be applied to any doubling strategy:
1. Defensive Bailouts:
   - Bail on 6, 7, 8, 9 (mod_drop_6789): Drop out on wide middle danger zone in cushion phase.
   - Bail on 7 & 8 (mod_drop_78): Early cashout on 50/50 trap cards in cushion phase.
   - Bail on 8 (mod_drop_8): Early cashout on single worst negative EV card (47.1%).
2. Small Hand Free-Roll (mod_free_roll): Always double small payouts (<= 200) until >= 800.
3. Fast Build (mod_fast_build): Force double if next reward still safely <= cushion_target (e.g. 19,800).
4. Opportunistic Card Overrides:
   - A & 2 (opp_a2, ~94.1%)
   - 3 & K (opp_3k, ~86.3%)
   - 4 & Q (opp_4q, ~78.4%)
   - 5 & J (opp_5j, ~70.6%)
   - 6 & 10 (opp_610, ~62.7%)
   - 7 & 9 (opp_79, ~54.9%)
   - 8 (opp_8, ~47.1%)
5. Sprint Floors:
   - Mega Sprint Floor >= 12,800 (mod_mega_sprint): Pushes for 32k+ cap.
   - Sprint Floor >= 11,200 (mod_sprint_floor): Pushes past 10,000 to guarantee >= 30,000 daily total.
"""
from typing import Optional, Tuple


def apply_strategy_modifiers(
    decision: str,
    card_val: Optional[int],
    current_cashout: int,
    next_reward: int,
    daily_coins: int,
    target_limit: int = 20000,
    cushion_target: int = 19800,
    opp_a2: bool = True,
    opp_3k: bool = True,
    opp_4q: bool = True,
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

    # 1. Defensive Bailouts during cushion phase (< cushion_target)
    if not mod_fast_build and current_cashout > 0 and daily_coins < cushion_target and decision == "challenge":
        if mod_drop_6789 and card_val in (6, 7, 8, 9):
            return "cashout", "mod_drop_6789"
        if mod_drop_78 and card_val in (7, 8):
            return "cashout", "mod_drop_78"
        if mod_drop_8 and card_val == 8:
            return "cashout", "mod_drop_8"

    # 2. Small Hand Free-Roll: Force doubling small initial hands (<= 200) until >= 800
    if mod_free_roll and decision == "cashout" and current_cashout <= 200:
        if daily_coins + next_reward < target_limit:
            return "challenge", "mod_free_roll"

    # 3. Fast Build: If strategy wanted to cash out early, but next reward safely fits within cushion
    if mod_fast_build and decision == "cashout":
        if daily_coins + next_reward <= cushion_target:
            return "challenge", "mod_fast_build"

    # 4. Opportunistic High-Chance Card Override (strictly under daily target limit)
    # Exclude cards actively subject to defensive bailouts during cushion phase
    bail_cards = set()
    if daily_coins < cushion_target:
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
        if should_opp and (daily_coins + next_reward < target_limit):
            return "challenge", "opportunistic_card"

    # 5. Sprint Floors (during sprint phase: daily >= cushion_target)
    if decision == "cashout" and daily_coins >= cushion_target:
        if mod_mega_sprint and current_cashout < 12800:
            return "challenge", "mod_mega_sprint"
        if mod_sprint_floor and current_cashout < 11200:
            return "challenge", "mod_sprint_floor"

    return decision, None
