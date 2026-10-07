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

### The Tie-Loss Penalty
A critical rule of the game is: **Equal-rank ties are losses**. If the revealed card matches the base card's rank, the player loses the entire accumulated round payout.

Let the base card rank be $B \in [2, 14]$:
- Favorable cards for **HIGH**:
  $$N_{\text{high}} = \sum_{r = B + 1}^{14} N_r$$
- Favorable cards for **LOW**:
  $$N_{\text{low}} = \sum_{r = 2}^{B - 1} N_r$$
- Tie cards (instant loss):
  $$N_{\text{tie}} = N_B$$

The exact real-time winning probabilities are:
$$P(\text{HIGH}) = \frac{N_{\text{high}}}{N_{\text{total}}}$$
$$P(\text{LOW}) = \frac{N_{\text{low}}}{N_{\text{total}}}$$
$$P(\text{LOSE}) = 1 - \max(P(\text{HIGH}), P(\text{LOW})) = \frac{\min(N_{\text{high}}, N_{\text{low}}) + N_{\text{tie}}}{N_{\text{total}}}$$

### Rank 8 Volatility Analysis
For rank 8 (the exact midpoint of cards 2 through 14):
- Higher cards (9, 10, J, Q, K, A): 6 ranks $\times 4 = 24$ cards.
- Lower cards (2, 3, 4, 5, 6, 7): 6 ranks $\times 4 = 24$ cards.
- Tie cards (8s remaining): up to 3 cards.

In a fresh 51-card remaining deck:
$$P(\text{HIGH}) = P(\text{LOW}) = \frac{24}{51} \approx 47.06\%$$
Because the probability of winning on rank 8 is **strictly less than 50%**, doubling on 8 carries negative expected return ($<1.0\times$). The **Bailout on 8** modifier exploits this math by cashing out whenever rank 8 appears during bankroll construction.

---

## 3. Two-Phase Cushion & Sprint Optimization

The daily game limit stops the player from starting new poker rounds once daily accumulated coins reach **20,000**. However, any round already in progress is allowed to finish.

```text
Daily Coin Bankroll: 0 ──────────────────────── 19,800 ─────── 20,000 ──────── 32,000+
                                   ▲                ▲
                            [CUSHION PHASE]    [SPRINT PHASE]
```

### 1. Cushion Phase ($< 19,800$ coins)
- **Objective**: Reach the cushion target without crossing 20,000 prematurely.
- **Decision Boundary**:
  - The bot verifies that the next doubling payout $R_{\text{next}}$ will not overshoot the cap:
    $$\text{Daily Coins} + R_{\text{next}} \le \text{Cushion Target (19,800)}$$
  - If a double would breach the cushion, the bot cashes out immediately to bank the safe coins.

### 2. Sprint Phase ($\ge 19,800$ coins)
- **Objective**: Maximize the payout of the final allowed round.
- **Decision Boundary**:
  - Once banked coins $\ge 19,800$, the bot initiates the final qualifying round.
  - The bot shifts into sprint mode, refusing early cashouts ($< 10,240$) and doubling aggressively to capture a massive final payout ($10,240$, $12,800$, or $20,480$).
  - **Resulting Daily Yield**:
    $$\text{Final Bankroll} = 19,800 + \text{Sprint Win} \approx 30,000 \text{ to } 32,600+ \text{ coins}$$

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
