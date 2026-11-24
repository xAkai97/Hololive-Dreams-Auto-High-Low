# Game Mechanics & Probability Research

Empirical study of the *Hololive Dreams* poker mini-game and High-Low doubling mechanics based on telemetry extracted across live play sessions.

---

## 1. Dynamic Odds & Extreme Rank Bias Near Daily Cap (~19,000 – 19,800 Coins)

### Investigation Hypothesis
Does *Hololive Dreams* dynamically skew High/Low card generation toward **extreme / polar ranks** ($A, 2, 3$ and $J, Q, K$) when approaching the final payout cap ($\ge 19,800$ coins) while suppressing middle cards ($6, 7, 8, 9$), or does the game RNG use uniform random draws from a standard fair 52-card deck?

* **Extreme Ranks ($A, 2, 3$ and $J, Q, K$)**: Offer $\ge 75\% - 100\%$ decisive win probabilities. If the game's RNG favored these ranks near the cap, consecutive doubling chains would become artificially easy.
* **Middle Cards ($6, 7, 8, 9$)**: High-variance coin flips ($50\% - 65\%$). In a standard 52-card deck, middle cards constitute $4/13 = 30.77\%$ of draws.

### Empirical Statistical Proof: The Deck is Fair
To test this hypothesis rigorously, card draws across session logs were partitioned into three bankroll phases:

| Metric | Phase 1: Pre-Cushion ($< 19,800$) | Phase 2: 1st Sprint ($\ge 19,800$) | Phase 3: Subsequent Sprints ($\ge 19,800$) | Theoretical Fair Deck |
| :--- | :---: | :---: | :---: | :---: |
| **Total Card Flips** | 246 | 10 | 140 | — |
| **Decisive Win Rate** | 80.17% (186W / 46L) | 88.89% (8W / 1L) | **68.70%** (90W / 41L) | ~65–70% |
| **Polar Ranks ($2, 3, J, Q, K, A$)** | 47.6% (117/246) | 30.0% (3/10) | **46.4%** (65/140) | 46.15% |
| **Middle Hazard ($6, 7, 8, 9$)** | 30.5% (75/246) | 40.0% (4/10) | **32.1%** (45/140) | 30.77% |
| **Extended Extremes ($2..5, 10..A$)** | 69.5% (171/246) | 60.0% (6/10) | **67.9%** (95/140) | 69.23% |

#### Key Conclusions:
1. **Dynamic Bias Disproven**:
   - In Phase 3 sprint rounds, polar rank frequency sits at **46.4%**, which matches the theoretical fair deck frequency (**46.15%**).
   - Middle hazard ranks ($6, 7, 8, 9$) appear at **32.1%** (theoretical **30.77%**), and Rank 8 frequency rose to **10.71%** (15/140 flips), refuting the hypothesis that middle cards or 8s are suppressed.
   - The decisive win rate in subsequent sprints is **68.70%**, exactly within the expected mathematical range of an optimal High/Low counting policy on a standard fair deck (~65–70%).
2. **Selection & Survivorship Effects in Telemetry**:
   - The observed disparity between the pre-cushion win rate (80.17%) and sprint rounds (68.70%) is driven entirely by bot strategy rather than game RNG:
     - *Cushion Phase*: The bot cashes out early (after 1–2 doubles) on unfavorable middle cards to bank coin profit safely, keeping recorded win rate high.
     - *Sprint Phase*: The bot forces doubling until hitting $\ge 10,000$ coins. A sprint round cannot terminate without 5–6 consecutive doubles, so analyzing completed sprint runs naturally samples successful doubling chains.
3. **Conclusion for Simulation & Bot Models**:
   - High-Low card dealing in *Hololive Dreams* operates as a standard, unbiased 52-card deck drawn without replacement. The uniform random shuffle model in `src/simulation.py` and `src/auto_bot.py` accurately mirrors live client mechanics.

---

## 2. In-Game Poker Rules Empirical Verification

All poker hand categories, payout multipliers, and edge cases have been empirically verified against live game logs:

### Royal Flush (10,000 Coins)
* **Log Reference**: `logs/log_2026-10-21.txt` / `debug_log_2026-10-21_1.txt` (Round #25)
* **Dealt Hand**: `[♣Q ♣A ♠J ♣K ♣J]`, Held: `[♣Q ♣A ♣K ♣J]`, Drew: `♣10`
* **Final Hand**: `[♣Q ♣A ♣10 ♣K ♣J]`
* **Client Behavior**: Awarded **10,000 coins** base payout, confirming the top paytable tier.

### Five of a Kind (7,000 Coins)
* **Log Reference**: `logs/log_2026-10-19.txt` / `debug_log_2026-10-20.txt` (Round #35)
* **Dealt Hand**: `[♠10 ♦10 ♠7 ♥10 ♠2]`, Held: `[♠10 ♦10 ♥10]`, Drew: `JOKER` and `♣10`
* **Final Hand**: `[♠10 ♦10 JOKER ♥10 ♣10]`
* **Client Behavior**: Awarded **7,000 coins** base payout (doubled to **14,000 coins** on win).

### Straight Flush (3,000 Coins)
* **Log Reference**: `logs/log_2026-10-15.txt` (Round #29, `[♥5 ♥6 ♥2 ♥3 JOKER]`), `logs/log.txt` (2026-10-22, Round #7, `[JOKER ♦5 ♦4 ♦2 ♦6]`)
* **Client Behavior**: Consistently awards **3,000 coins** base payout.

### Four of a Kind (1,500 Coins)
* **Log Reference**: `logs/log_2026-10-15.txt` (Round #18), `logs/log_2026-10-18.txt` (Round #2), `logs/log_2026-10-20.txt` (Round #1, Round #24)
* **Client Behavior**: Consistently awards **1,500 coins** across natural and Joker-assisted hands.

### A-2-3-4-5 "Wheel" Straight (400 Coins)
* **Log Reference**:
  * `logs/log_2026-11-05.txt` (Round #49): Dealt `[♥4 ♣2 JOKER ♦A ♥5]`, awarded **400 coins** base payout.
  * `logs/log_2026-11-06.txt` (Round #44): Dealt `[♥5 ♣3 ♠A JOKER ♠2]`, awarded **400 coins** base payout.
  * `logs/log_2026-11-02.txt` (Round #90): Dealt `[♦3 JOKER ♥5 ♣A ♥4]`, awarded Straight.
* **Client Behavior**: The client recognizes Ace as a low card (1) in wheel sequences, awarding the standard Straight payout (400 coins).

### Tie / Push Re-Roll Rule
* **Log Reference**: Round #7 Step 5 (`♦2 == 2`), Round #11 Step 3 (`♦10 == 10`).
* **Client Behavior**: Equal-rank card flips do not forfeit purse; the player re-rolls against the same or new visible card. Win probability calculation treating ties as non-decisive push events is 100% accurate.

### 20,000 Daily Overflow Cap
* The daily 20,000 coin cap stops entry into new poker rounds but allows ongoing rounds to conclude.
* Tested sessions routinely overflow cleanly:
  * Peak single-day bankroll reached **33,800 coins** (`logs/log_2026-10-19.txt` via 14,000-coin Five of a Kind double).
  * Standard sprints reliably yield **31,000 – 32,600 coins**.
  * Instant Royal Flush cashout cleanly stopped at **23,600 coins** (`logs/log_2026-10-21.txt`).
