# RESULTS_book -- does the order book warn of a jump?

*`research/pinbook.py`, 2026-09-13T19:19Z. 11420 coin-closes over 1692 closes, 2026-08-25T05:15Z .. 2026-09-13T19:00Z (19.6 days). From `feed_data/bitstamp` -- 8.3 GB of order-book snapshots on the exchanges behind the index, never opened before. No Kalshi order book, no replay, no fills, no P&L.*

**This is the first thing tried here that is not a price.** The index lead-lag test failed and exchange disagreement failed; both used prices. This is how much SIZE stands behind the price, which no price series can contain.

Floods: **221 of 11420 (1.94%)**. MDE, stated before the estimate: **2.53x**. Under that is NO POWER, not NO EFFECT.

| feature | bottom fifth | top fifth | lift | 95% by-close | strength | beats MDE? |
|---|---|---|---|---|---|---|
| `spread_rel` | 2.14% | 2.10% | **0.98x** | [0.63, 1.54] | 1.02x | no |
| `depth5` | 2.01% | 1.80% | **0.89x** | [0.60, 1.36] | 1.12x | no |
| `imbalance` | 2.01% | 1.75% | **0.87x** | [0.57, 1.41] | 1.15x | no |
| `touch` | 1.79% | 2.45% | **1.36x** | [0.95, 2.10] | 1.36x | no |
| `withdrawal` | 1.74% | 1.65% | **0.95x** | [0.57, 1.54] | 1.05x | no |

Strongest: **`touch`**, lift 1.36x [0.95, 2.10], strength 1.36x against an MDE of 2.53x. **Does not clear it** -- no power, not no effect.

## Holdout

| feature | first 70% | last 30% | same direction? |
|---|---|---|---|
| `touch` | 1.28x | 1.01x | yes |
| `imbalance` | 0.91x | 1.08x | **no** |
| `depth5` | 0.91x | 0.86x | yes |
| `withdrawal` | 0.83x | 1.27x | **no** |
| `spread_rel` | 1.14x | 0.57x | **no** |

