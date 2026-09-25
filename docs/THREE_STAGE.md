# Three-Stage Doubling Strategy Guide

In the strategy dropdown menu, select **"3 stages: Max → Win count → Max"** (Legacy remains the default option).

---

## Strategy Overview

- **Stages 1 & 3**: Continues doubling until the game forces an automatic settlement (no arbitrary software cashout threshold like 12,800 is applied).
- **Stage 2**: Inspects the initial hand payout once at the start of the round to determine a target number of consecutive doubling wins, rather than relying on unstable OCR readings during fast animations.
- **Strict Win Confirmation**: A win is only registered when the High/Low choice is confirmed by the subsequent in-game success prompt. Ties, repeated frames, and retry attempts do not count toward the win count.
- **Losses & Resets**: A loss resets the current round's win count to 0 and retries the same stage. Only a confirmed settlement advances to the next stage.

---

## Stage 2 Win Count Targets

| Initial Payout | Stage 2 Win Target | Expected Payout |
|:---|---:|---:|
| 200 | 5 | 6,400 |
| 400 | 4 | 6,400 |
| 700 | 3 | 5,600 |
| 800 | 3 | 6,400 |
| 1,500 | 2 | 6,000 |
| 3,000 | 1 | 6,000 |
| 7,000 / 10,000 | 0 | 7,000 / 10,000 |

> [!NOTE]
> At the start of Stage 2, target win counts that would push cumulative daily earnings to 20,000 or higher are dynamically excluded to reserve cap room for Stage 3. If even an immediate cashout would breach the daily limit, the bot halts for manual handling.

---

## Ledger & Persistence

- Settlement totals are validated against the initial payout multiplied by confirmed doubling steps, guarding against OCR digit-truncation issues.
- Daily coins and stage progress are persisted in `daily_coins.json`. Progress is preserved across restarts on the same day and automatically resets when the date changes.
- Mid-round bot restarts stop and request a fresh round to prevent inaccurate win-count guesses.
- Automation safely stops once Stage 3 completes.

---

## Credits

- Strategy design and original implementation by [harrykuang-dev](https://github.com/harrykuang-dev).

