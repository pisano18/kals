# The factor programme — what sets the price we'll pay, recomputed every second

**Written 2026-09-08.** The operator's instruction: the threshold must be
recomputed every second from the current average, the time left, and every
other factor that genuinely helps — and I should be generating the candidates,
not waiting to be handed them. This is my list, the reasoning for each, and
the order I'd test them in.

## The quantity being estimated

Everything below feeds **one number**:

```
required_move = (60/r) × (K_eff − mu)        exact algebra, no model
p_flip        = P(the remaining r prints average that move, in that direction)
threshold     = 1 − p_flip − margin          the most we'll pay, this second
```

`required_move` is arithmetic. **`p_flip` is where every factor earns or fails
to earn its place.** A factor is only worth having if it measurably improves
`p_flip` — judged by proper scoring (Brier / log-loss) against realised
outcomes, on the population of *genuinely available trades*, walk-forward.

## Tier 1 — the spot market itself (LARGELY UNTESTED, HIGHEST VALUE)

We hold **9.1 GB** of constituent exchange data — Coinbase, Kraken, Bitstamp,
Gemini — and have never used a byte of it in a trading decision. The settlement
index is *computed from these books*, so this is not a correlated signal, it is
the **input**.

| # | factor | why it should predict `p_flip` |
|---|---|---|
| 1 | **index replica vs published index** | `feed_data/index_replica` already emits a per-second size-weighted consolidated mid. If it leads the published print, the "unknown" prints become **partly known** — the single biggest possible improvement, because it converts forecasting into computing. |
| 2 | **spot book depth within N bps** | The direct answer to "how far can it move": a thin book means a given volume moves price further. Depth is the physical constraint on the move we're betting against. |
| 3 | **cross-exchange dispersion** | Four exchanges, four prices. When they disagree the index is unstable and the next print is less predictable. Free from `per_ex`. |
| 4 | **spot trade volume and imbalance** | Volume is the fuel for movement; signed imbalance gives direction. |
| 5 | **spot spread** | A widening spread is stress and precedes jumps. |
| 6 | **size at the touch vs recent trade size** | If typical trade size exceeds resting depth, the price is one order away from moving. |

## Tier 2 — the index's own behaviour

| # | factor | why |
|---|---|---|
| 7 | **empirical move quantiles** | Replaces the bell curve, which understates crypto tails by 37–127 sigma on measured data. |
| 8 | **volatility at several horizons** (30/120/300/900 s) | One 300 s window is arbitrary; short-horizon vol should matter more at small `r`. |
| 9 | **jump-robust volatility** | One jump inflates plain SD for the whole window and freezes us out of good trades. |
| 10 | **vol-of-vol** | How much to trust the vol estimate itself. |
| 11 | **increment autocorrelation** | `var_factor` accepts a correlation sequence and every call site passes white noise. Nobody has checked. |
| 12 | **index staleness** | If the feed has stalled, the last print persists — and a stale print may jump to catch up. |
| 13 | **transient** (spot vs its own trailing mean) | The documented cause of the only replayed loss. 1.20σ at the flip vs 0.29σ when correct. |
| 14 | **drift toward or away from the strike** | Same distance is far more dangerous when moving toward the line. |
| 15 | **travel so far this window** | A window that has already moved a lot may keep moving. |

## Tier 3 — the Kalshi contract

| # | factor | why |
|---|---|---|
| 16 | **quote age** | Cuts both ways and must be measured: an old quote is probably an absent quoter (safe); a fresh one may be someone who just repriced (dangerous). |
| 17 | **market-implied vs our probability** | The disagreement IS the adverse selection. Measured: 0.01% flip over all calls, **0.90% over trades taken**. Does a bigger apparent bargain predict a worse outcome? |
| 18 | **contract book depth and spread** | Capacity, and a proxy for how confident the other side is. |
| 19 | **offer size** | Is a 5-lot offer more dangerous than a 200-lot one? |
| 20 | **sibling agreement** | Eleven coins settle at the same second. A market disagreeing with its siblings is a warning. |

## Tier 4 — regime

| # | factor | why |
|---|---|---|
| 21 | **hour of day** | The live run is overnight; the evidence came from the US afternoon. |
| 22 | **cross-asset jump** | BTC moving is a live warning for an alt trade about to be placed. |
| 23 | **locked-window coverage** | Missing ticks are silently rescaled today; that is unquantified error. |
| 24 | **which coin** | DOGE's tick grid is 7 digits and BTC's is 2. They are not the same instrument. |

## Tier 5 — the structural change

| # | idea | why |
|---|---|---|
| 25 | **rest at the threshold instead of racing for it** | Maker fee is **zero** (7% of a 3¢ edge), no race to lose, and anyone can fill us. The settlement input is public, so a counterparty can only be *faster*, never better informed — a survivable disadvantage. |
| 26 | **trade earlier where the arithmetic allows** | Deeper book, less competition. Only where already-published prints settle it — never on a forecast. |

## Method

1. **One dataset**, one row per genuinely available trade, every factor
   attached, outcome held separate. Testing a factor becomes a query.
2. **Each factor alone first** — Brier/log-loss lift over the current model.
   A factor that cannot beat the baseline alone does not get into a
   combination on hope.
3. **Then pairs, then triples**, by forward selection on out-of-fold loss.
   Report how many combinations were tried; the significance bar depends on it.
4. **Walk-forward always**, with a deliberately-leaking control that must score
   better — otherwise the harness cannot detect leakage.
5. **Judged on money**, not accuracy: `$/day = edge × fillable size ×
   opportunities`. A better-calibrated rule that trades a third as often is
   worse.
6. **Consistency across days**, not a good average.

## Honest ranking of expected value

1. **Index replica lead** — converts prediction into calculation. Nothing else
   available changes the problem this fundamentally.
2. **Resting instead of racing** — removes the fee and the race in one move.
3. **Spot depth and dispersion** — the direct measure of how far price can go.
4. **Empirical tails conditioned on regime** — fixes a known, measured, large
   error in the current model.
5. Everything else.
