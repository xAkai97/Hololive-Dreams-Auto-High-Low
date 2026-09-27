# Hololive Dreams Auto High & Low — Strategy Guide

## Game Rules

| Rule | Value |
|------|-------|
| **Double-up cap** | ~10,000 coins per round (game auto-settles) |
| **Daily earning cap** | 20,000 coins (soft — can't start a new round once reached) |
| **Overshoot** | Allowed — final win is fully credited even if it exceeds 20k |
| **Unlimited plays** | No limit on rounds, only on daily total |

> **Optimal daily max:** ~32,000 coins — earn ~19,800 in small cashouts, then max double-up (~12,800) on the final round.

---

## Available Strategies

### 1. Legacy 1.0.1 (`legacy_101`)

The original strategy by the upstream developer. Decision logic:

- **Cushion phase** (daily < 19,800):
  - Cashout if next double overshoots 19,800
  - Cashout if win rate < 60%
  - Force double if cashing out would overshoot 19,800 without reaching 10k
- **Sprint phase** (daily ≥ 19,800):
  - Ignore win rate, keep doubling until cashout ≥ 10,000

**Expected:** ~20k-30k | **Risk:** Medium | **Time:** Medium

---

### 2. Three Stages (`three_stages`)

The original 3-phase strategy by the upstream developer:

- **Stage 1:** Max double-up (game auto-settles at ~10k)
- **Stage 2:** Controlled wins targeting ~6,400 cashout
- **Stage 3:** Max double-up again for final big win

> ⚠️ This strategy uses stage persistence. If the bot is stopped mid-round, the stage may not save correctly. Use the stageless strategies for better stop/resume behavior.

**Expected:** ~32k | **Risk:** Medium | **Time:** Long

---

### 3. Max Profit (`max_profit`)

Maximizes daily profit to ~32,000 coins. Same logic as Legacy but optimized:

- **Cushion** (daily < 19,800): Safe cashouts, guard against overshooting 19,800
- **Sprint** (daily ≥ 19,800): Chase 10k+ cashout, ignore win rate

**Expected:** ~30k-32k | **Risk:** Medium-High | **Time:** Medium-Long

---

### 4. Fastest Clear (`fastest_clear`)

Reach 20,000+ coins as fast as possible. All-or-nothing:

- Every round goes for max double-up (game auto-settles at ~10k cap)
- Only cashout if doing so reaches the daily cap
- Stop when daily ≥ 20,000

**Expected:** ~20k-22k | **Risk:** Highest | **Time:** Fastest (2-3 good rounds)

---

### 5. Balanced (`balanced`)

Reliable ~25,000 coins with moderate risk:

- **Build** (daily < 15,000): Cashout at 6,400+, win rate floor 55%
- **Push** (15k ≤ daily < 19,800): Higher threshold, win rate floor 50%
- **Sprint** (daily ≥ 19,800): Max double-up for 10k+

**Expected:** ~25k-28k | **Risk:** Moderate | **Time:** Medium

---

### 6. Aggressive Balanced (`aggressive_balanced`)

Like Balanced but pushes harder:

- **Build** (daily < 12,000): Cashout at 6,400+, win rate floor 50%
- **Push** (12k ≤ daily < 19,800): Let rounds ride, win rate floor 45%
- **Sprint** (daily ≥ 19,800): Max double-up for 10k+

**Expected:** ~28k-30k | **Risk:** Medium-High | **Time:** Medium

---

### 7. Adaptive Rush (`adaptive_rush`)

Starts aggressive, auto-downshifts if failing too much:

- **Rush mode (default):** Max double-up every round (like Fastest)
- **Auto-adjust triggers:** 10+ consecutive fails OR net profit < -2,000
- **Cushion mode (fallback):** Small cashouts (3,200+), win rate floor 55%
- **Sprint** (daily ≥ 19,800): Max double-up for 10k+

Once in cushion mode, stays there (no switching back).

**Expected:** ~25k-32k | **Risk:** Self-adjusting | **Time:** Adaptive

---

### 8. Grinder (`grinder`)

Ultra-safe, minimum risk:

- **Build** (daily < 19,800): Cashout at 1,600+, max 4 doubles per round, win rate floor 60%
- **Sprint** (daily ≥ 19,800): One final max double-up attempt

**Expected:** ~20k-25k | **Risk:** Lowest | **Time:** Longest

---

### 9. Custom Parametric (`custom_parametric`)

Fully user-configurable strategy. Set your own parameters via the GUI:

| Parameter | Config Key | Default | Description |
|-----------|-----------|---------|-------------|
| Cashout Target | `param_cashout_target` | 6400 | Cashout threshold during build phase |
| Min Win Rate | `param_min_win_rate` | 55 (%) | Minimum win rate before forced cashout |
| Sprint Threshold | `param_sprint_threshold` | 19800 | Daily coins to enter sprint mode |
| Sprint Cashout | `param_sprint_cashout` | 10000 | Min cashout to accept during sprint |
| Max Doubles | `param_max_doubles` | 0 | Max doubles per round (0 = unlimited) |
| Drop on 7/8 | `param_drop_seven_eight` | false | Always cashout when facing a 7 or 8 |
| Fail Safety | `param_fail_safety_limit` | 0 | After N fails, switch to safe mode (0 = off) |

**Expected:** Varies | **Risk:** User-defined | **Time:** Varies

---

## Opportunistic High-Chance Doubling (Under Limit)

In addition to each strategy's built-in decision tree, the bot provides toggleable **Opportunistic Doubling** directly on the **Auto Bot** tab in the main UI:

| Toggle | Default | Target Cards | Win Odds |
|:---|:---:|:---|:---:|
| **A & 2** | **Enabled (ON)** | Ace (14) & 2 | ~92.3% ($\ge 90\%$) |
| **3 & K** | **Toggleable (OFF)** | 3 & King (13) | ~84.6% ($\ge 82\%$) |
| **4 & Q** | **Toggleable (OFF)** | 4 & Queen (12) | ~76.9% ($\ge 74\%$) |

### Decision Override Logic
1. Whenever the active strategy decides to **Cashout**, the bot checks the visible base card before taking the payout.
2. If the visible card matches an enabled toggle (e.g. an Ace or 2), the bot **overrides the cashout** to continue doubling (`challenge`).
3. **Strict Lockout Prevention Guard:**
   $$\text{daily\_coins} + \text{next\_reward} < \text{target\_limit}$$
   - With the default 20,000 target limit, the maximum post-double payout allowed under this rule is **19,800**.
   - Landing on 20,000 on the dot (e.g. `18,400 + 1,600 = 20,000`) is strictly **disallowed**. This guarantees the bot never locks itself out of starting the final round, preserving the opportunity to sprint for a 10,000+ overflow payout.

---

## Quick Comparison

| Strategy | Expected | Risk | Time | Best For |
|----------|----------|------|------|----------|
| Legacy | ~20-30k | Medium | Medium | Original experience |
| Three Stages | ~32k | Medium | Long | Stage-based play |
| Max Profit | ~32k | Med-High | Med-Long | Maximum coins |
| Fastest Clear | ~20k | Highest | Fastest | Speed runs |
| Balanced | ~25k | Moderate | Medium | Reliable daily |
| Aggressive Balanced | ~28k | Med-High | Medium | Higher profit balance |
| Adaptive Rush | ~25-32k | Adaptive | Adaptive | Smart risk management |
| Grinder | ~20-25k | Lowest | Longest | Safety first |
| Custom | Varies | Custom | Varies | Full control |
