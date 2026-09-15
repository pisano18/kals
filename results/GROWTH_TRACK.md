# GROWTH_TRACK -- are we on track?

*Written by `research/pingrow.py`. Re-run it any day: the actuals extend
and the projection re-anchors on the real bank. Compare the ON TRACK
line at the bottom.*

**Last updated: 2026-09-14 23:35 ET**


---

## Part 1 -- every day, actual

Bank is the balance at the START of that ET day. Before 2026-09-12 the bot
ran a fixed size and never read the balance, so those rows are inferred
backwards from P&L off the first real read ($193.76).

| day | # | version | bank start | size | max/close | trades | won | lost | losing closes | contracts | c/contract | net | cumulative | return |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-09-07 | 1 | pre-pin  natgas market-making, both sides quoted | $65.18 | 20 | - | 16 quotes | 0 | 0 | 0 | 0 | - | **$0.00** | $0.00 | 0.0% |
| 2026-09-08 | 2 | *(smoke test 06:34-07:15Z)* | $41.04 | 0.01 | - | 1 | 1 | 0 | 0 | 0.01 | - | **$0.00** | $0.00 | 0.0% |
| 2026-09-08 | 2 | v0-v14   pin goes live 07:09Z; EV gate, tau 30, size 1->20 | $190.66 | 20 | 40 | 36 | 30 | 3 | 1 | 374 | -11.59c | **-43.36** | -43.36 | -22.7% |
| 2026-09-09 | 3 | v14      size 20 fixed; first big loss (NEAR -$52.60) | $147.29 | 20 | 40 | 39 | 39 | 0 | 0 | 708 | +6.88c | **+48.74** | +5.37 | +33.1% |
| 2026-09-10 | 4 | v15-v16  scale-in, price ceiling | $196.03 | 20 | 40 | 45 | 42 | 3 | 3 | 836 | +0.03c | **+0.23** | +5.60 | +0.1% |
| 2026-09-11 | 5 | v17      15c dump guard live 08:29 ET | $196.26 | 20 | 40 | 51 | 43 | 2 | 2 | 879 | -0.28c | **-2.50** | +3.10 | -1.3% |
| 2026-09-12 | 6 | v18-v22  AUTO-SIZING BEGINS; hedge trigger 0.80 | $193.76 | 66 | 132 | 92 | 90 | 2 | 2 | 1680 | +2.31c | **+38.75** | +41.85 | +20.0% |
| 2026-09-13 | 7 | v-pick   best-market-first (A24) 20:35 ET | $198.70 | 47 | 94 | 49 | 49 | 0 | 0 | 2194 | +5.23c | **+114.77** | +156.62 | +57.8% |
| 2026-09-14 | 8 | v-ladder 02:1 ET, v-spend, v-brake20, v-nofloor 10:53 ET, v-jump 21:39 ET | $324.28 | 59 | 118 | 61 | 59 | 2 | 2 | 3319 | +2.44c | **+81.14** | +237.76 | +25.0% |
| **TOTAL** | | | | | | **373** | **352** | **12** | **10** | **9990** | **+2.38c** | **+237.76** | | |

**Funding.** $38.83 at the first pin version. One deposit of $150, of which
only **$113.04** reached the crypto shard -- the rest landed on a shard where
it could not trade. **No deposit since.** The 09-13 and 09-14 bank moves match
P&L to within 4 cents, so everything after that is traded money.

*(The $65.18 on 09-07 and $41.04 on 09-08 are balances on different shards
at different moments, not a loss between them -- the account holds more than
one and only the crypto shard can trade these markets.)*

**The shape of it.** The first four pin days (09-08..09-11) netted **+$3.11
combined** at a fixed size of 20. Every dollar since is the last three days,
which is exactly when auto-sizing arrived and the execution fixes landed:
contracts per unit of size went **25 -> 47 -> 58** as the ladder sweep and
then the depth-floor removal went in. Same model; it just started buying what
was in front of it.

---

## Part 2 -- projection

Anchored on the real bank, **$394.59**, and the CURRENT version's measured rate:
**58 contracts per unit of size per day**, from the window since the depth
floor came off (2026-09-14 14:53Z, 12.2 hours, 21 closes).

That window earned +2.74c per contract and contained **no losses**, so the
projection does not use it. The cases are **1.5c / 2.4c / 3.5c**, where 2.4c
is our all-time live average with every loss included.

Size = bank / 5.88. The depth curve is `research/pincap.py`'s measured
ladder scaling, so bigger orders earn proportionally less per contract.

### The cap, and why 500

`pinrun` caps size at **250** contracts today. That number was chosen
before the book had ever been measured. `research/pincap.py` then walked
**13,984 real ask ladders**: a **500-lot still fills in full on 75.3%** of
tradeable moments, at a mean price of 95.45c against 95.10c for a 50-lot.
So **500 is the largest size the market is measured to support**, and it is
the cap used below. Past 500 there is no measurement and this file refuses
to guess -- size simply stops growing there.

Reaching 500 needs a bank of **$2,940** (500 x 5.88). For comparison, the
250 cap needs $1,470 and is reached roughly a week earlier.

**The risk does not change shape.** At any size, one worst-case close costs
`2 x size x 0.98` -- a third of the bank, by design. At 500 that is **$980**
of a $2,940 bank. The 20% drawdown brake still stops the bot before a full
worst close completes.

### LOW -- 1.5c per contract

| date | day | bank start | size | max/close | contracts | net | cumulative | return |
|---|---|---|---|---|---|---|---|---|
| Tue 15 Sep | 1 | $394.59 | 67 | 134 | 3,892 | +58.14 | 58.14 | +14.7% |
| Wed 16 Sep | 2 | $452.73 | 77 | 154 | 4,466 | +66.35 | 124.49 | +14.7% |
| Thu 17 Sep | 3 | $519.08 | 88 | 177 | 5,120 | +75.61 | 200.10 | +14.6% |
| Fri 18 Sep | 4 | $594.69 | 101 | 202 | 5,866 | +86.01 | 286.10 | +14.5% |
| Sat 19 Sep | 5 | $680.69 | 116 | 232 | 6,714 | +97.65 | 383.75 | +14.3% |
| Sun 20 Sep | 6 | $778.34 | 132 | 265 | 7,677 | +110.68 | 494.43 | +14.2% |
| Mon 21 Sep | 7 | $889.02 | 151 | 302 | 8,769 | +125.26 | 619.69 | +14.1% |
| Tue 22 Sep | 8 | $1,014.28 | 172 | 345 | 10,005 | +141.42 | 761.11 | +13.9% |
| Wed 23 Sep | 9 | $1,155.70 | 197 | 393 | 11,400 | +159.23 | 920.34 | +13.8% |
| Thu 24 Sep | 10 | $1,314.93 | 224 | 447 | 12,970 | +178.71 | 1,099.05 | +13.6% |
| Fri 25 Sep | 11 | $1,493.64 | 254 | 508 | 14,733 | +199.97 | 1,299.02 | +13.4% | *(250 cap would bind here)*
| Sat 26 Sep | 12 | $1,693.61 | 288 | 576 | 16,706 | +223.80 | 1,522.81 | +13.2% |
| Sun 27 Sep | 13 | $1,917.40 | 326 | 652 | 18,913 | +249.64 | 1,772.45 | +13.0% |
| Mon 28 Sep | 14 | $2,167.04 | 369 | 737 | 21,376 | +277.43 | 2,049.89 | +12.8% |
| Tue 29 Sep | 15 | $2,444.48 | 416 | 831 | 24,112 | +307.06 | 2,356.94 | +12.6% |
| Wed 30 Sep | 16 | $2,751.53 | 468 | 936 | 27,141 | +338.28 | 2,695.22 | +12.3% |
| Thu 01 Oct | 17 | $3,089.81 | 500 | 1000 | 29,000 | +356.63 | 3,051.85 | +11.5% | **<== 500 CAP, flat from here**
| Fri 02 Oct | 18 | $3,446.44 | 500 | 1000 | 29,000 | +356.63 | 3,408.48 | +10.3% |
| Sat 03 Oct | 19 | $3,803.07 | 500 | 1000 | 29,000 | +356.63 | 3,765.11 | +9.4% |
| Sun 04 Oct | 20 | $4,159.70 | 500 | 1000 | 29,000 | +356.63 | 4,121.73 | +8.6% |
| Mon 05 Oct | 21 | $4,516.32 | 500 | 1000 | 29,000 | +356.63 | 4,478.36 | +7.9% |
| Tue 06 Oct | 22 | $4,872.95 | 500 | 1000 | 29,000 | +356.63 | 4,834.99 | +7.3% |
| Wed 07 Oct | 23 | $5,229.58 | 500 | 1000 | 29,000 | +356.63 | 5,191.62 | +6.8% |
| Thu 08 Oct | 24 | $5,586.21 | 500 | 1000 | 29,000 | +356.63 | 5,548.25 | +6.4% |
| Fri 09 Oct | 25 | $5,942.84 | 500 | 1000 | 29,000 | +356.63 | 5,904.88 | +6.0% |
| Sat 10 Oct | 26 | $6,299.47 | 500 | 1000 | 29,000 | +356.63 | 6,261.51 | +5.7% |
| Sun 11 Oct | 27 | $6,656.10 | 500 | 1000 | 29,000 | +356.63 | 6,618.14 | +5.4% |

- reaches 500 contracts on **Thu 01 Oct** (day 17), bank $3,090
- steady state from there: **$357/day**, flat
- for comparison, capped at 250 it would be **$197/day** -- the extra
  250 contracts are worth **$160/day more**, forever

### EXPECTED -- 2.4c per contract

| date | day | bank start | size | max/close | contracts | net | cumulative | return |
|---|---|---|---|---|---|---|---|---|
| Tue 15 Sep | 1 | $394.59 | 67 | 134 | 3,892 | +93.02 | 93.02 | +23.6% |
| Wed 16 Sep | 2 | $487.61 | 83 | 166 | 4,810 | +113.97 | 206.99 | +23.4% |
| Thu 17 Sep | 3 | $601.58 | 102 | 205 | 5,934 | +139.11 | 346.10 | +23.1% |
| Fri 18 Sep | 4 | $740.69 | 126 | 252 | 7,306 | +169.05 | 515.15 | +22.8% |
| Sat 19 Sep | 5 | $909.74 | 155 | 309 | 8,974 | +204.74 | 719.89 | +22.5% |
| Sun 20 Sep | 6 | $1,114.48 | 190 | 379 | 10,993 | +246.54 | 966.43 | +22.1% |
| Mon 21 Sep | 7 | $1,361.02 | 231 | 463 | 13,425 | +294.77 | 1,261.20 | +21.7% |
| Tue 22 Sep | 8 | $1,655.79 | 282 | 563 | 16,333 | +350.95 | 1,612.15 | +21.2% | *(250 cap would bind here)*
| Wed 23 Sep | 9 | $2,006.74 | 341 | 683 | 19,794 | +415.54 | 2,027.69 | +20.7% |
| Thu 24 Sep | 10 | $2,422.28 | 412 | 824 | 23,893 | +487.58 | 2,515.26 | +20.1% |
| Fri 25 Sep | 11 | $2,909.85 | 495 | 990 | 28,703 | +565.98 | 3,081.24 | +19.5% |
| Sat 26 Sep | 12 | $3,475.83 | 500 | 1000 | 29,000 | +570.61 | 3,651.85 | +16.4% | **<== 500 CAP, flat from here**
| Sun 27 Sep | 13 | $4,046.44 | 500 | 1000 | 29,000 | +570.61 | 4,222.45 | +14.1% |
| Mon 28 Sep | 14 | $4,617.04 | 500 | 1000 | 29,000 | +570.61 | 4,793.06 | +12.4% |
| Tue 29 Sep | 15 | $5,187.65 | 500 | 1000 | 29,000 | +570.61 | 5,363.67 | +11.0% |
| Wed 30 Sep | 16 | $5,758.26 | 500 | 1000 | 29,000 | +570.61 | 5,934.27 | +9.9% |
| Thu 01 Oct | 17 | $6,328.86 | 500 | 1000 | 29,000 | +570.61 | 6,504.88 | +9.0% |
| Fri 02 Oct | 18 | $6,899.47 | 500 | 1000 | 29,000 | +570.61 | 7,075.49 | +8.3% |
| Sat 03 Oct | 19 | $7,470.08 | 500 | 1000 | 29,000 | +570.61 | 7,646.09 | +7.6% |
| Sun 04 Oct | 20 | $8,040.68 | 500 | 1000 | 29,000 | +570.61 | 8,216.70 | +7.1% |
| Mon 05 Oct | 21 | $8,611.29 | 500 | 1000 | 29,000 | +570.61 | 8,787.31 | +6.6% |
| Tue 06 Oct | 22 | $9,181.90 | 500 | 1000 | 29,000 | +570.61 | 9,357.91 | +6.2% |

- reaches 500 contracts on **Sat 26 Sep** (day 12), bank $3,476
- steady state from there: **$571/day**, flat
- for comparison, capped at 250 it would be **$315/day** -- the extra
  250 contracts are worth **$255/day more**, forever

### HIGH -- 3.5c per contract

| date | day | bank start | size | max/close | contracts | net | cumulative | return |
|---|---|---|---|---|---|---|---|---|
| Tue 15 Sep | 1 | $394.59 | 67 | 134 | 3,892 | +135.65 | 135.65 | +34.4% |
| Wed 16 Sep | 2 | $530.24 | 90 | 180 | 5,230 | +180.02 | 315.67 | +34.0% |
| Thu 17 Sep | 3 | $710.26 | 121 | 242 | 7,006 | +237.07 | 552.74 | +33.4% |
| Fri 18 Sep | 4 | $947.33 | 161 | 322 | 9,344 | +309.94 | 862.68 | +32.7% |
| Sat 19 Sep | 5 | $1,257.27 | 214 | 428 | 12,402 | +400.68 | 1,263.37 | +31.9% |
| Sun 20 Sep | 6 | $1,657.96 | 282 | 564 | 16,354 | +512.40 | 1,775.76 | +30.9% | *(250 cap would bind here)*
| Mon 21 Sep | 7 | $2,170.35 | 369 | 738 | 21,408 | +648.19 | 2,423.96 | +29.9% |
| Tue 22 Sep | 8 | $2,818.55 | 479 | 959 | 27,802 | +804.70 | 3,228.66 | +28.6% |
| Wed 23 Sep | 9 | $3,623.25 | 500 | 1000 | 29,000 | +832.13 | 4,060.79 | +23.0% | **<== 500 CAP, flat from here**
| Thu 24 Sep | 10 | $4,455.38 | 500 | 1000 | 29,000 | +832.13 | 4,892.93 | +18.7% |
| Fri 25 Sep | 11 | $5,287.52 | 500 | 1000 | 29,000 | +832.13 | 5,725.06 | +15.7% |
| Sat 26 Sep | 12 | $6,119.65 | 500 | 1000 | 29,000 | +832.13 | 6,557.20 | +13.6% |
| Sun 27 Sep | 13 | $6,951.79 | 500 | 1000 | 29,000 | +832.13 | 7,389.33 | +12.0% |
| Mon 28 Sep | 14 | $7,783.92 | 500 | 1000 | 29,000 | +832.13 | 8,221.47 | +10.7% |
| Tue 29 Sep | 15 | $8,616.06 | 500 | 1000 | 29,000 | +832.13 | 9,053.60 | +9.7% |
| Wed 30 Sep | 16 | $9,448.19 | 500 | 1000 | 29,000 | +832.13 | 9,885.74 | +8.8% |
| Thu 01 Oct | 17 | $10,280.33 | 500 | 1000 | 29,000 | +832.13 | 10,717.87 | +8.1% |
| Fri 02 Oct | 18 | $11,112.46 | 500 | 1000 | 29,000 | +832.13 | 11,550.00 | +7.5% |
| Sat 03 Oct | 19 | $11,944.59 | 500 | 1000 | 29,000 | +832.13 | 12,382.14 | +7.0% |

- reaches 500 contracts on **Wed 23 Sep** (day 9), bank $3,623
- steady state from there: **$832/day**, flat
- for comparison, capped at 250 it would be **$460/day** -- the extra
  250 contracts are worth **$372/day more**, forever


---

## Part 3 -- ON TRACK?

Fill this in as the days land. The projection re-anchors every time this is
re-run, so compare the **actual net** against the EXPECTED row for that date
as it stood on 2026-09-15.

| date | projected net (expected) | actual net | on track? |
|---|---|---|---|
| 2026-09-15 | +93.02 | | |
| 2026-09-16 | +113.97 | | |
| 2026-09-17 | +139.11 | | |
| 2026-09-18 | +169.05 | | |
| 2026-09-19 | +204.74 | | |
| 2026-09-20 | +246.54 | | |
| 2026-09-21 | +294.77 | | |
| 2026-09-22 | +350.95 | | |
| 2026-09-23 | +415.54 | | |
| 2026-09-24 | +487.58 | | |
| 2026-09-25 | +565.98 | | |
| 2026-09-26 | +570.61 | | |
| 2026-09-27 | +570.61 | | |
| 2026-09-28 | +570.61 | | |
| 2026-09-29 | +570.61 | | |

**What would put us off track, and what it would mean:**

- **net below the LOW case two days running** -- the edge is decaying, or the
  market got harder. Check `python research/pinhealth.py` first: the kill line
  is +1.53c per contract.
- **contracts per unit of size falling below ~40** -- we are not filling what
  we used to. That is execution, not edge.
- **two losing closes in a day** -- the loss brake stops the bot at two, so
  this shows up as a halt, not a drawdown.
- **hitting the cap early with the bank still small** -- means the edge ran
  hot, not that anything is wrong.
