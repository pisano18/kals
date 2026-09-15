# GROWTH_TRACK -- are we on track?

*Written by `research/pingrow.py`. Re-run it any day: the actuals extend
and the projection re-anchors on the real bank. Compare the ON TRACK
line at the bottom.*

**Last updated: 2026-09-14 23:25 ET**


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

### A) CAPPED at 250 contracts -- what runs today

| case | cap day | bank at cap | steady $/day | bank +3 days |
|---|---|---|---|---|
| **LOW 1.5c** | Fri 25 Sep (day 10) | $1,494 | **$197** | $2,085 |
| **EXPECTED 2.4c** | Tue 22 Sep (day 7) | $1,656 | **$315** | $2,602 |
| **HIGH 3.5c** | Sun 20 Sep (day 5) | $1,658 | **$460** | $3,038 |

### B) UNCAPPED -- if the cap is raised to whatever the book supports

| case | day 7 | day 14 | day 21 | size at day 21 | $/day at day 21 |
|---|---|---|---|---|---|
| **LOW 1.5c** | $1,014 | $2,444 | $5,339* | 908* | $573 |
| **EXPECTED 2.4c** | $1,656 | $5,748* | $16,911* | 2876* | $2,816 |
| **HIGH 3.5c** | $2,819 | $13,883* | $63,578* | 10813* | $15,437 |

**\* beyond 500 contracts nothing is measured.** `pincap.py` walked real
ladders out to 500; past that the depth curve is held flat, which is
almost certainly too kind. Treat any starred figure as an upper bound on
an upper bound -- at those sizes we would be a visible share of a book
whose median resting order is 20 contracts, and the crowd of ~130
suppliers that makes this work would notice us.

**Day by day, EXPECTED case, capped** -- the one to check against:

| date | day | bank start | size | max/close | contracts | net | return |
|---|---|---|---|---|---|---|---|
| Tue 15 Sep | 1 | $394.59 | 67 | 134 | 3892 | +93.02 | +23.6% |
| Wed 16 Sep | 2 | $487.61 | 83 | 166 | 4810 | +113.97 | +23.4% |
| Thu 17 Sep | 3 | $601.58 | 102 | 205 | 5934 | +139.11 | +23.1% |
| Fri 18 Sep | 4 | $740.69 | 126 | 252 | 7306 | +169.05 | +22.8% |
| Sat 19 Sep | 5 | $909.74 | 155 | 309 | 8974 | +204.74 | +22.5% |
| Sun 20 Sep | 6 | $1114.48 | 190 | 379 | 10993 | +246.54 | +22.1% |
| Mon 21 Sep | 7 | $1361.02 | 231 | 463 | 13425 | +294.77 | +21.7% |
| Tue 22 Sep | 8 | $1655.79 | 250 | 500 | 14500 | +315.37 | +19.0% | **<== 250 CAP**
| Wed 23 Sep | 9 | $1971.16 | 250 | 500 | 14500 | +315.37 | +16.0% |
| Thu 24 Sep | 10 | $2286.54 | 250 | 500 | 14500 | +315.37 | +13.8% |
| Fri 25 Sep | 11 | $2601.91 | 250 | 500 | 14500 | +315.37 | +12.1% |

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
| 2026-09-22 | +315.37 | | |
| 2026-09-23 | +315.37 | | |
| 2026-09-24 | +315.37 | | |
| 2026-09-25 | +315.37 | | |

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
