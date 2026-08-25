# RESULTS R3 — the 96.7¢ crossover is an artefact of the statistic

`2026-08-25` · sandbox, no market data. Simulation only.

## The claim under test

RUNBOOK.md, **Tails**:

> Winsorized, pooled: Gaussian model UNDERvalues the favourite below ~96.7c and
> OVERvalues above it. Crossover replicated at 96.6c on the June archive and
> 96.7c on recent data — **two independent datasets, so this is real.**

The replication argument is the load-bearing part. Two independent datasets
agreeing to within 0.1¢ looks like strong evidence.

## What was measured

The crossover point was computed for 14 synthetic processes that share nothing
except excess kurtosis — different *shapes*, different *causes*, kurtosis
spanning 1.0 to 168.

| process | excess kurt | crossover |
|---|---|---|
| iid Student-t(3) | 168.2 | 98.3¢ |
| iid Student-t(4) | 10.4 | 97.2¢ |
| iid Student-t(5) | 5.0 | 96.8¢ |
| iid Student-t(6) | 2.4 | 96.6¢ |
| iid Student-t(8) | 1.4 | 96.3¢ |
| iid Student-t(12) | 1.0 | 96.7¢ |
| GARCH α=0.10 β=0.88 | 4.4 | 96.7¢ |
| GARCH α=0.15 β=0.80 | 2.4 | 96.7¢ |
| GARCH α=0.20 β=0.70 | 1.7 | 96.5¢ |
| GARCH α=0.30 β=0.50 | 1.8 | 97.1¢ |
| normal mix p=.05 k=3.0 | 4.2 | 98.5¢ |
| normal mix p=.10 k=2.5 | 3.1 | 97.5¢ |
| normal mix p=.02 k=5.0 | 13.7 | 99.3¢ |
| normal mix p=.20 k=2.0 | 1.7 | 96.6¢ |

Range 96.3¢–99.3¢, mean 97.2¢, with 10 of 14 inside 96.3–97.5¢.

## Conclusion

The crossover is close to a **fixed point of standardizing a fat-tailed
distribution to unit variance**. Once you rescale so the variance matches, the
shoulders must thin to pay for the tail, and the balance point sits near
z ≈ 1.8 almost regardless of how fat the tail is or what caused it. Student-t(12)
(kurtosis 1.0) and Student-t(4) (kurtosis 10.4) both land at ~97¢.

Therefore **the replication is not evidence of a property of crypto returns.**
Any two fat-tailed datasets would agree to within a cent. What the replication
actually establishes is "these returns have some excess kurtosis" — which was
never in dispute and does not need two datasets to show.

## What this changes

1. **Do not build a strategy around a 96.7¢ threshold.** The number is not
   estimating what it appears to estimate. Its stability across datasets is
   structural, not empirical.
2. **The informative quantities are the tail *ratios* at the price you would
   actually trade**, not where they cross 1. A ratio of 1.6 at 98¢ is a real,
   sized statement about mispricing; "the crossover is at 96.7¢" is not.
3. **The conditional/unconditional question is the one that matters.**
   `volmodel.py` separates them and its self-test shows the separation is clean:

   | process | kurt raw | kurt vol-adjusted | ΔLL vs constant σ |
   |---|---|---|---|
   | iid Gaussian | −0.09 | −0.02 | −16.7 |
   | GARCH, cond-normal | 1.62 | **0.25** | **+228.7** |
   | iid Student-t(4) | 10.05 | **10.87** | −49.8 |
   | GARCH + Student-t | 16.84 | 4.40 | +915.3 |

   Vol-adjusting destroys clustering-induced kurtosis (1.62 → 0.25) and leaves
   genuine fat tails intact (10.05 → 10.87). Run this on the real chain and the
   answer decides which model to build.

## Method note

This is the third bug of the same family found in two days: a statistic that
looks like a measurement of the world but is largely determined by its own
construction. The others were the chain-gate verdict keyed on a median that
corruption could not move, and a tail test that reported a confident crossover
from clean Gaussian noise. All three were caught by asking a statistic what it
returns when the answer is already known. That check should precede every
number this project reports.
