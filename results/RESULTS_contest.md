# RESULTS_contest -- did anyone else want the offer?

*`research/pincontest.py`, 2026-09-13T07:57Z. 11935 candidate offers on 716 closes, 2026-08-25T05:44Z .. 2026-09-12T17:15Z (18.5 days). Population `live`. Contest window 1000 ms. 4749 of our own executions removed from the tape. Our own live fills (282 order/hedge records) were matched against the tape and 4749 executions removed. (re-scored from cache)*

**THIS FILE COMPARES TWO TAPE POPULATIONS WITH EACH OTHER AND DOES NOTHING ELSE.** Neither arm is a loss rate of ours and neither may be quoted as one (CLAUDE.md 2026-09-10, rule 5). No P&L is computed here.

## 0. Power, before the estimate

rho between coins sharing a close is measured at 0.621, design effect 30.69x. The smallest accuracy gap this split can call at alpha=0.05 two-sided with 80% power is **4.35 pp**. A gap smaller than that is NO POWER, not NO EFFECT.

## 1. The FORWARD split -- who else took it, after our moment

| arm | rows | closes | lost | the model's side won | 95% CP (deflated) |
|---|---|---|---|---|---|
| CONTESTED -- another taker bought it | 10492 | 706 | 216 | 97.94% | [96.01, 99.21] |
| CLEAR -- nobody did | 1443 | 309 | 130 | 90.99% | [85.50, 94.65] |
| all candidates | 11935 | 716 | 346 | 97.10% | [95.00, 98.58] |

**Gap (contested minus clear): +6.95 pp, 95% by-close bootstrap [+3.09, +11.32], 100.0% of resamples at or above zero.**

Standardised on the contested arm's own (confidence x tau) mix, covering 100% of it: contested 97.94%, clear 90.94%, gap +7.00 pp.

## 2. THE LEAKAGE CHECK -- and it fires, so read this before section 1

A forward window sees the future. If the model's side is going to WIN, its price walks to $1 and any ask left resting below that gets lifted by somebody -- it is free money and the exchange is full of takers. If it is going to LOSE, the ask is never lifted at any price. So 'was it taken' is partly CAUSED by the outcome, and the longer the window the more of the gap is that mechanism rather than information anyone had at our moment. The table below is the test: if the split were information, widening the window would add noise and shrink the gap. It does the opposite.

| window | contested rows | share | contested acc | clear acc | gap |
|---|---|---|---|---|---|
| 250 ms | 8072 | 67.6% | 98.13% | 94.95% | +3.18 pp |
| 1000 ms | 10492 | 87.9% | 97.94% | 90.99% | +6.95 pp |
| 5000 ms | 11654 | 97.6% | 97.92% | 62.99% | +34.93 pp |
| 60000 ms | 11828 | 99.1% | 97.89% | 9.35% | +88.55 pp |

**A gap that grows without limit as the window widens is the outcome leaking in, not a signal.** Section 1 is therefore valid for what it was built for -- selecting the population that resembles our own fills -- and INVALID as a trading rule. The tradeable version is section 3, which can only look backwards.

## 3. The BACKWARD split -- what was knowable at our moment

Same test, same window length, run over the 1000 ms BEFORE the decision instead of after. Every input here exists at the moment the order would be sent, so a rule may be built on it. MDE **4.05 pp**.

| arm | rows | closes | lost | the model's side won | 95% CP (deflated) |
|---|---|---|---|---|---|
| someone took this level JUST BEFORE us | 10151 | 680 | 275 | 97.29% | [95.05, 98.79] |
| nobody had | 1784 | 414 | 71 | 96.02% | [92.48, 98.14] |

**Gap: +1.27 pp, 95% by-close bootstrap [-1.62, +4.57], 78.6% of resamples at or above zero. Standardised +1.30 pp (coverage 100%).**

## 4. How fast the competition arrives

Of 10492 contested rows, the first competing take lands after p10 6 ms, median 67 ms, p90 528 ms. 77% of them are gone inside 250 ms.

The level was fully consumed (competing contracts >= the depth we measured) on 7197 of 10492 contested rows, 68.6%.

## 5. What each arm holds -- a guard that discards data, costed

- **CONTESTED**: 10492 rows (87.9%), 706 closes, 9561837 contracts of resting depth, mean discount 4.85c, mean tau 20.7 s.
- **CLEAR**: 1443 rows (12.1%), 309 closes, 739008 contracts of resting depth, mean discount 4.64c, mean tau 21.8 s.
- **BACKWARD-contested**: 10151 rows (85.1%), 680 closes, 9582356 contracts of resting depth, mean discount 4.94c, mean tau 20.7 s.
- **BACKWARD-clear**: 1784 rows (14.9%), 414 closes, 718489 contracts of resting depth, mean discount 4.17c, mean tau 21.6 s.

## 6. The price of racing harder

A taker limit above the resting ask pays the RESTING price when it wins -- an IOC limit that crosses fills at the resting order's price -- so racing harder is free on every race we already win. It costs something only on the races we lose today, and only up to the next level.

| of 10492 contested rows | rows | share |
|---|---|---|
| next level inside the 98c ceiling | 9474 | 90.3% |
| **and still clears the SAME gate (edge >= 0.3c after fee)** | **4514** | **43.0%** |
| inside the ceiling but under the edge floor | 4960 | 47.3% |
| next level above the ceiling | 1006 | 9.6% |
| nothing above at all | 12 | 0.1% |

On the rows that still clear the gate the next level costs a median **0.20c** more (mean 0.70c, p90 2.00c) and holds a median 115 contracts. The tick above 90c is 0.1c, which is why the median is what it is.

