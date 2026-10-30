# Decision Engine & Algorithm Guide

This document details the mathematical models, probability formulas, and computational algorithms powering the *Hololive Dreams Auto Bot*.

---

## 1. Numba JIT Poker Hand Evaluator (`src/poker_core.py`)

The poker mini-game is a **5-Card Draw** variant played with a **53-card deck** (standard 52 cards plus 1 Joker). The Joker acts as a wild card, automatically adopting the rank and suit that creates the highest-ranking hand.

### Payout Table
The game requires a minimum hand of **Two Pair** to qualify for a payout:
- **Royal Flush**: 10,000 coins
- **Five of a Kind**: 7,000 coins
- **Straight Flush**: 3,000 coins
- **Four of a Kind**: 1,500 coins
- **Full House**: 800 coins
- **Flush**: 700 coins
- **Straight**: 400 coins
- **Three of a Kind**: 200 coins
- **Two Pair**: 200 coins
- **One Pair / High Card**: 0 coins (forfeits the 50-coin ticket)

### Combinatorial Hold Optimization ($2^5 = 32$ Masks)
Given an initial dealt hand of 5 cards, there are $2^5 = 32$ distinct binary hold masks $M \in \{0, 1\}^5$, where $1$ denotes "hold" and $0$ denotes "discard and draw".

For each candidate mask $M$:
1. Let $k$ be the number of cards discarded ($0 \le k \le 5$).
2. The remaining deck consists of $53 - 5 = 48$ unseen cards.
3. The number of possible replacement card combinations is given by the binomial coefficient:
   $$\binom{48}{k} = \frac{48!}{k!(48-k)!}$$
4. The Expected Value $\mathbb{E}[M]$ of mask $M$ is calculated as:
   $$\mathbb{E}[M] = \frac{1}{\binom{48}{k}} \sum_{c \in \mathcal{C}(48, k)} \text{Payout}(\text{Hand}(M, c))$$
5. The algorithm selects the optimal mask $M^*$ that maximizes expected return:
   $$M^* = \arg\max_{M \in \{0, 1\}^5} \mathbb{E}[M]$$

### Numba JIT Performance
Evaluating thousands of 5-card combinations in pure Python per deal causes noticeable latency (100–300ms). Using `@numba.njit(fastmath=True)`, card integer bitmasks and evaluator loops are precompiled into optimized native machine code on startup (`warm_up()`), reducing evaluation latency to **$< 2$ milliseconds** per round.

---

## 2. Dynamic High-Low Card Counting

During the High-Low doubling phase, the player is shown a base card and must predict whether the next card drawn from the deck will have a higher or lower rank.

### Deck Depletion Model
A standard poker deck consists of 52 cards (ranks 2 through 14/Ace, 4 suits per rank). Unlike independent trials, the game draws without replacement within the current round, or resets upon reshuffle:
- We track the exact count $N_r$ of remaining cards for each rank $r \in [2, 14]$.
- Total remaining cards:
  $$N_{\text{total}} = \sum_{r=2}^{14} N_r$$

### The Tie-Push (Re-Roll) Rule
A critical rule of the game is: **Equal-rank ties are pushes (re-rolls)**. If the revealed card matches the base card's rank, the player does not forfeit the purse; instead, the player simply chooses High or Low again.

Let the base card rank be $B \in [2, 14]$:
- Favorable cards for **HIGH**:
  $$N_{\text{high}} = \sum_{r = B + 1}^{14} N_r$$
- Favorable cards for **LOW**:
  $$N_{\text{low}} = \sum_{r = 2}^{B - 1} N_r$$
- Tie cards (neutral push / replay):
  $$N_{\text{tie}} = N_B$$
- Total decisive cards (excluding ties):
  $$N_{\text{decisive}} = N_{\text{high}} + N_{\text{low}}$$

The exact real-time winning probabilities conditional on round resolution are:
$$P(\text{HIGH}) = \frac{N_{\text{high}}}{N_{\text{decisive}}}$$
$$P(\text{LOW}) = \frac{N_{\text{low}}}{N_{\text{decisive}}}$$

Under this push model:
- For **rank 2**: $N_{\text{low}} = 0 \implies P(\text{HIGH}) = \frac{N_{\text{high}}}{N_{\text{high}}} = \mathbf{100.0\%}$.
- For **rank Ace (14)**: $N_{\text{high}} = 0 \implies P(\text{LOW}) = \frac{N_{\text{low}}}{N_{\text{low}}} = \mathbf{100.0\%}$.

### Rank 8 Volatility Analysis
For rank 8 (the exact midpoint of cards 2 through 14):
- Higher cards (9, 10, J, Q, K, A): 6 ranks $\times 4 = 24$ cards.
- Lower cards (2, 3, 4, 5, 6, 7): 6 ranks $\times 4 = 24$ cards.
- Decisive cards: $24 + 24 = 48$ cards.

In a fresh remaining deck:
$$P(\text{HIGH}) = P(\text{LOW}) = \frac{24}{48} = \mathbf{50.00\%}$$
Under the game's tie-push rule (where drawing another 8 re-rolls rather than forfeiting), rank 8 is an exact **50/50 coin flip** rather than the legacy 47.1% (which assumed ties lose). However, because an exact 50.0% probability offers zero mathematical edge, doubling on 8 introduces high variance. The **Bailout on 8** modifier cashes out whenever rank 8 appears during bankroll construction to eliminate this coin-flip risk.

---

## 3. Two-Phase Cushion & Sprint Optimization

The daily game limit stops the player from starting new poker rounds once daily accumulated coins reach **20,000**. However, any round already in progress is allowed to finish.

```text
Daily Coin Bankroll: 0 ──────────────────────── 19,800 ─────── 20,000 ──────── 32,000+
                                   ▲                ▲
                            [CUSHION PHASE]    [SPRINT PHASE]
```

### 3.1 Cushion Phase ($< 19,800$ coins, Banking Ceiling $\le 19,900$)
- **Objective**: Reach the `19,800–19,900` cushion target without crossing 20,000 prematurely.
- **Even & Odd Parity Cushion Ceiling (`cushion + 100 = 19,900`)**:
  - Since the minimum qualifying poker hand is **200 coins** and hands like Flush (**700**) and Four of a Kind (**1,500**) produce odd-hundred totals, both **19,800** and **19,900** are the highest possible pre-cap totals strictly $< 20,000$.
  - The bot safely banks payouts up to $\text{Cushion Cap} = \text{Cushion Target} + 100 = 19,900$ whenever the next double would overshoot $19,900$ (e.g., `19,700 + 200 = 19,900`, `19,200 + 700 = 19,900`, `14,300 + 5,600 = 19,900`, `18,400 + 1,500 = 19,900`).
- **Early Overshoot & Intentional Double-Up Fail**:
  - In-game High-Low automatically terminates and forces settlement as soon as a payout reaches $\ge 10,000$ (*"Ended due to reaching the max payout"*), yielding fixed per-hand ceilings:
    - `200 / 400 / 800` $\rightarrow$ **`12,800`**
    - `700` (Flush) $\rightarrow$ **`11,200`**
    - `1,500 / 3,000` $\rightarrow$ **`12,000`**
    - `7,000` (Five of a Kind) $\rightarrow$ **`14,000`**
    - `10,000` (Royal Flush) $\rightarrow$ **`20,000`**
  - If a hand would overshoot $19,900$ before reaching the $19,800$ cushion ($\text{Daily Coins} < 19,800$ and $\text{Daily Coins} + \text{Cashout} \ge 20,000$):
    - If $\text{Daily Coins} + \text{Max Round Payout} \ge 32,600$ (e.g., `19,600 + 14,000 = 33,600` or `19,700 + 14,000 = 33,700` on Five of a Kind), the bot attempts the max payout early.
    - Otherwise ($\text{Daily Coins} + \text{Max Round Payout} < 32,600$), the bot enters Double Up and **intentionally selects the lower-probability High/Low choice** (`intent_to_fail`) to cancel the hand and preserve room for a full $32,600\text{–}32,700$ sprint.

### 3.2 Sprint Phase ($\ge 19,800$ coins: `19,800` or `19,900`)
- **Objective**: Maximize the payout of the final allowed round.
- **Decision Boundary**:
  - Once banked coins reach `19,800` or `19,900`, the bot initiates the final qualifying round.
  - The bot shifts into sprint mode, refusing early cashouts ($< 10,000$) and doubling to the hand's $\ge 10,000$ auto-settle cap ($11,200$, $12,000$, $12,800$, or $14,000$; or intentionally failing sub-threshold ceilings when Sprint Floor / Mega Sprint is active).
  - **Resulting Daily Yield**:
    $$\text{Final Bankroll} = (19,800\text{–}19,900) + \text{Sprint Win} \approx 31,000 \text{ to } 33,900 \text{ coins}$$

### 3.3 Gross Coins vs. Net Wallet Profit & The "True Max Coins" Paradox

Every round of poker requires a mandatory ticket entry fee of **50 coins**. Therefore, daily economic yield cannot be measured solely by the final gross balance displayed on screen:

$$\text{Net Profit} = \text{Gross Coins Settled} - (50 \times \text{Rounds Played})$$

The bot's strategies are divided into three distinct categories based on how they optimize this trade-off:

#### Category A: Maximum Net Profit (Recommended for Daily Farming)
- **Strategies**: `Balanced` (`balanced`, Default or Aggressive play style; `aggressive_balanced` supported as backward-compatible alias), `Adaptive Max Profit` (`max_profit`).
- **Mechanics**: Accepts the first sprint payout that reaches $\ge 11,200\text{–}12,800$ (e.g. Flush, Full House, Two Pair) without holding out exclusively for Five of a Kind.
- **Economics**: Completes the entire day in **12–15 minutes** with only **30–45 failed attempts** (ticket burn: $1,500\text{–}2,250$ coins).
- **Net Return**: Delivers **$+30,000$ to $+30,350$ actual net profit** added to the player's wallet.

#### Category B: Speed & Safe Grind (Fast or Conservative)
- **Strategies**: `Fastest Clear` (`fastest_clear`), `Adaptive Rush` (`adaptive_rush`), `Grinder` (`grinder`).
- **Mechanics**: Prioritizes speed or near-zero variance. `Fastest Clear` crosses the 20k threshold on the first high hand without staging a sprint; `Grinder` banks frequent small doubles.
- **Economics**: Completes in **3–7 minutes** with negligible ticket fees ($200\text{–}500$ coins).
- **Net Return**: Delivers **$+20,000$ to $+25,000$ net profit**.

#### Category C: Custom & Trophy (The 33.9k Screenshot Hunt)
- **Strategies**: `True Max Coins` (`true_max_coins`), `Custom Parametric` (`custom_parametric`).
- **The "True Max Coins" Paradox**:
  - `True Max Coins` strictly hunts the mathematical maximum gross score achievable in the game: $19,900 + 14,000 = \mathbf{33,900 \text{ coins}}$.
  - Achieving a 14,000 sprint payout requires starting from Five of a Kind ($7,000 \times 2 = 14,000$).
  - In a 53-card deck with 1 Joker, the probability of obtaining Five of a Kind is approximately **1 in 1,300 to 2,700 rounds**.
  - During the Sprint Phase, `True Max Coins` intentionally forfeits every non-Five-of-a-Kind hand to keep the round slot open.
  - At 50 coins per ticket, burning 1,300 to 2,700 hands incurs **$65,000$ to $135,000+$ coins in entry fees**.
  - **Net Economic Result**: The game end-screen displays **33,900 coins**, but the player's wallet suffers a **net loss of $-\$31,000$ to $-\$100,000+$ coins**.
  - `True Max Coins` is therefore designated as a **Trophy / Achievement mode**, while `Balanced` (Default or Aggressive style) is the optimal strategy for actual wallet wealth.

---

## 4. Monte Carlo Simulation Engine (`src/simulation.py`)

To evaluate and tune strategy parameters without risking in-game coins, `simulation.py` implements a vectorized Monte Carlo simulator:

1. **RNG Deck Generation**: Models true uniform Fisher-Yates card shuffles and draws without replacement.
2. **Strategy Benchmarking**: Simulates 1,000 to 50,000 simulated days per strategy.
3. **Statistical Metrics Tracked**:
   - **Average Daily Profit**: Total payout minus ticket entry fees ($50 \times \text{attempts}$).
   - **Bust Rate (% of days $< 20,000$)**: Measures bankroll volatility and failure frequency.
   - **Sprint Success Rate**: Percentage of days that successfully reach $\ge 30,000$ coins.
   - **Standard Deviation & Value at Risk (VaR)**: Measures consistency across varying seed distributions.
