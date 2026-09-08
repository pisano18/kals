# AMENDMENT 5 — price ceiling 98.8c -> 96.0c

**Written 2026-09-08 ~16:30 UTC, BEFORE the change goes live.**

## What changes

`PRICE_CEILING = 0.96`. Nothing else. tau 3-30, model gate 0.98, scale-in cap
2, size 5, abort -$21 all unchanged.

## Why — it is safer AND more profitable

Measured on 5,219 qualifying moments from the order-book dataset:

| ceiling | closes | buys | avg price | headroom | profit/close | total |
|---|---|---|---|---|---|---|
| <=98.8c (now) | 83 | 129 | 93.94c | **1.4x** | 7.42c | 616c |
| <=98.0c | 80 | 119 | 93.08c | 2.2x | 8.30c | 664c |
| <=97.0c | 65 | 97 | 91.78c | 3.3x | 10.16c | 660c |
| **<=96.0c** | **58** | **84** | **90.80c** | **4.4x** | **11.20c** | **650c** |
| <=95.0c | 48 | 69 | 89.34c | 5.6x | 13.09c | 628c |

**Headroom** = how many times the measured 0.90% flip rate the *worst accepted
trade* could tolerate before its expected value turns negative. It is the
inverse of the price: paying 96c means losing money only if we are wrong more
than 4% of the time; paying 98.8c means 1.2%.

30% fewer trades, **51% more profit per opportunity**, and roughly the same
total. The expensive trades were never paying for the risk they carried.

## The principle this encodes

**The price paid sets how wrong we are allowed to be.**

| price | win | lose | max tolerable error |
|---|---|---|---|
| 93c | 7c | 93c | 7.0% |
| 96c | 4c | 96c | 4.0% |
| 99c | 1c | 99c | **1.0%** |

Our measured error is 0.90%. At 99c that is a 1.1x margin — one bad estimate
from negative. The EV gate already refuses the worst of these; this amendment
simply stops flirting with the boundary.

## What would make this wrong

1. If the flip rate is materially **lower** than 0.90% (the 0.3c-floor cell
   suggests 0.28%), the dear trades were fine and this discards real profit.
   The total-profit column shows the cost is small either way.
2. 58-83 closes is a thin sample; the per-close figures are noisy.
3. Fewer trades means slower learning about the tail.

## Revert condition

If fired closes fall below 10 per day, the ceiling is too tight to gather
evidence and should return to 97c.
