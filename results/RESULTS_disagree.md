# RESULTS_disagree -- do the exchanges disagreeing predict a blow-up?

*`research/pindis.py`, 2026-09-13T12:07Z. 6647 coin-closes over 1670 closes, 2026-08-25T04:15Z .. 2026-09-13T12:00Z (19.3 days). From `feed_data/index_replica` -- the per-venue bids and asks BEHIND the settlement index, which the index itself cannot contain. No Kalshi order book, no replay, no fills, no P&L.*

Floods: **123 of 6647 (1.85%)**. MDE, stated before the estimate: **2.58x**. Anything under that is NO POWER, not NO EFFECT.

| feature | bottom fifth floods | top fifth floods | lift | 95% by-close | strength | beats MDE? |
|---|---|---|---|---|---|---|
| `spread_rel` | 2.03% | 1.36% | **0.67x** | [0.36, 1.30] | 1.48x | no |
| `wmid_gap` | 2.26% | 1.88% | **0.84x** | [0.48, 1.52] | 1.19x | no |
| `n_ex` | 2.41% | 2.03% | **0.85x** | [0.33, 1.40] | 1.18x | no |
| `quote_spread` | 1.65% | 1.73% | **1.05x** | [0.58, 1.97] | 1.05x | no |

Strongest: **`spread_rel`**, lift 0.67x [0.36, 1.30], strength 1.48x against an MDE of 2.58x. **Does not clear the bar** -- no power, not no effect.

## Holdout

| feature | lift first 70% | lift last 30% | same direction? |
|---|---|---|---|
| `spread_rel` | 0.52x | 1.14x | **no** |
| `wmid_gap` | 0.66x | 0.92x | yes |
| `n_ex` | 0.55x | 1.55x | **no** |
| `quote_spread` | 0.72x | 1.82x | **no** |

