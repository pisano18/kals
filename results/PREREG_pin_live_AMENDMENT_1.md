# AMENDMENT 1 to PREREG_pin_live.md — lower the edge floor 0.5c → 0.3c

**Written 2026-09-08 08:20 UTC, BEFORE the change goes live.** Dated and
stated loudly because this project's absolute rule is that a bar is never
moved after seeing a result without saying so.

## What changes

| | before | after |
|---|---|---|
| net edge floor (after taker fee) | **0.5c** | **0.3c** |
| everything else | unchanged | unchanged |

tau window [3, 20], PIN gate 0.98 / 0.02, one fire per close, size 1, resting
level ≥ 1 whole contract, loss abort −$3.00, stake cap $5.00: **all unchanged.**

## Why — the evidence, which pre-dates the decision

From the corrected out-of-sample backtest (`pin.py` re-run 2026-09-08 after
both settlement-model fixes; sigma recalibrated only on closes strictly
earlier than the one traded):

```
edge floor 0.3c  k 0.51->1.08  n= 389 closes  MDE 1.49c  realised +2.76c (t=+5.6)
    DEAR n=359 paid 97c won 100%  P&L +2.34c    CHEAP n=30 paid 2c won 10% P&L +7.73c
    DEAR tail: 1 flip in 359 -> 95% upper bound 1.11%  breakeven 2.35%  headroom 2.1x
    mid-null [-2.90,+0.44]  fair-band [+1.73,+3.01]  <-- beats the market-is-right null
    ranks: mid 100.0%  fair 76.3%

edge floor 0.5c  k 1.00->1.12  n= 354 closes  MDE 1.84c  realised +2.51c (t=+4.1)
    DEAR n=333 paid 97c won 99%   P&L +2.24c    CHEAP n=21 paid 3c won 10% P&L +6.66c
    DEAR tail: 3 flips in 333 -> 95% upper bound 1.80%  breakeven 2.26%  headroom 1.3x
    ranks: mid 100.0%  fair 8.5%
```

The looser floor is better on **every** dimension measured:

- **more opportunities**: 389 vs 354 closes (+9.9%)
- **larger realised edge**: +2.76c vs +2.51c per contract
- **stronger statistic**: t=+5.6 vs +4.1
- **FEWER errors**: 1 flip in 359 vs 3 in 333 — 0.28% vs 0.90%
- **more safety margin**: headroom 2.1× vs 1.3× against breakeven
- **better calibrated**: realised sits at fair-band rank 76.3% (comfortably
  inside the band) versus 8.5% at the 0.5c floor (near its bottom edge)

## What would make this wrong, stated before the fact

1. **Multiple comparisons.** Four floors were tested (0.3 / 0.5 / 1.0 / 2.0)
   on the same 9-day sample, so picking the best is mildly self-flattering.
   With four looks the threshold rises from |t|≈2.0 to roughly |t|≈2.5.
   t=+5.6 clears it, but the *point estimate* should be expected to shrink.
2. **Same-sample selection.** The comparison that chose 0.3c used the same
   closes it is scored on. The forward test below is what settles it.
3. **The fewer-flips result is counterintuitive.** A looser floor admitting
   *fewer* errors is not what one would predict; it may be sampling noise on
   1 versus 3 events. Both counts are small and neither is significant on its
   own. **This is the weakest link in the case and is recorded as such.**
4. If the live flip rate at the 0.3c floor exceeds **1.0%** over the forward
   window, this amendment is wrong and the floor returns to 0.5c.

## The forward test this starts

- **Metric:** realised cents per contract, and flip rate among trades priced
  ≥90c (the "dear" trades that carry the tail risk).
- **Success:** realised > 0 with a flip rate below 1.0%.
- **Failure, and the revert condition:** flip rate ≥ 1.0%, or realised
  cents per contract negative over ≥ 100 fired closes.
- **Sample:** counted from this amendment forward only. Trades before it are
  not pooled in.

## What is NOT changing, and why

The dynamic floor — a threshold computed per trade from the required move and
the *empirical* distribution of index moves — is **not** deployed here. It is
a materially larger change, it is still under walk-forward test, and it must
clear a leak check and an adversarial review before it goes near real money.
This amendment is the small, already-evidenced step only.
