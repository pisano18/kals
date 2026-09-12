# RESULTS_count -- why we trade nothing on half the certain closes

Generated 2026-09-12T22:06:07Z by `research/pincount.py` on the REBUILT replay (`pinsim` commit with per-close rails). Every decision is pinrun's own `fair`, `net_edge`, `expected_value`, `billed_fee` and constants.

**Gate replayed:** `PIN=0.995 ceiling=0.98 tau=[3,30] SIZE=20 min_fill_frac=0.5 min_level=1 edge_floor=0.003 ev_floor=0.003 flip=0.009 dump=0.15 max_per_close=2 max_per_market=1 improve_by=0.005 book_age<=2000ms index_age<=2s`

**Window:** 180 book hours, 9 UTC days (2026-09-04 .. 2026-09-12), 697 closes seen. **696 closes carry a model-certain market inside the LIVE band tau [3,30]** -- that is the number section 1 decomposes. **697 carry one anywhere in the SCANNED band tau [3,60], and that is the fixed denominator for every $/close figure**, because it is the widest band any row here can see: no configuration can gain a close outside it, and no lever can flatter itself by shrinking its own denominator. Divide by 697 instead if you want $ per quarter-hour of wall-clock.

**Clustering:** one observation = one CLOSE. Twelve series settle on the same second at rho ~ 0.8, so per-market counts are reported as counts only and never as `n` for a t-statistic (CLAUDE.md hard rule 4).

**The book is not perfect, and here is how imperfect.** The collector stamps `_seq_gap` on any frame whose `seq` is not prev+1; at that instant the book for that subscription is provably wrong. This window contains **3,012 such flags over 675,547,581 delta messages across 180 hours (16.7 per hour, 0.00045%)**. Nothing below refuses a decision on a gap -- pinsim's own note explains why 11 events an hour cannot justify the decision-time cost -- so no number here should be believed to the cent.

**Loss rates:** no loss rate for US is quoted from the tape (CLAUDE.md 2026-09-10 rule 5). Every dollar column appears twice: `tape` is the settled outcome of each replayed fill and is a RANKING of levers only; `ev` is `pinrun.expected_value` at the price paid, which carries the project's own MEASURED_FLIP (0.9%) and is the criterion the live bot itself applies.

## 0. VERDICT — COUNT is a LIQUIDITY problem, and no threshold reaches it

*Hand-written on top of the generated tables below; every number in it is
reproduced by `research/pincount.py --report` and reconciled by hand in this
section. Nothing here is deployed and nothing here should be.*

**The answer to the question.** On the 333 model-certain closes in this 9-day
window where we traded nothing, the reason is not our rules and it is not
size. Per close, taking the cheapest offer that ever appeared on the model's
side at any second in tau [3,30]: **219 of 333 (65.8%) never saw anything
below 98.7c — the price where pinrun's own EV gate stops, not where the
ceiling stops; 73 of 333 (21.9%) never saw an ask on our side at all; and only
39 of 333 (11.7%) sit inside the reach of any price or size threshold.**
Underneath that, the mechanism is visible in the census and it is structural:
of 167,458 fresh model-certain market-seconds, **140,990 (84.2%) carry no ask
on the winning side, and 140,989 of those 140,990 carry one on the LOSING
side.** The book is not dead; it is one-sided against us. To buy a near-
certainty somebody has to bid the side that is about to lose, and when the
outcome becomes obvious nobody does. That is a capacity limit of the product
and no parameter of ours touches it. It also explains why being pickier has
failed three times: the offers are not there to be picky about.

**The single best change, and it should be measured, not deployed:
`PRICE_CEILING` 0.980 → 0.987.** It is the only lever whose sign is positive on
both components of the split. It buys **35 new closes (+$9.72) and 37 extra
fills on closes we already trade (+$7.36) = +$17.08 over 697 closes =
+$0.0245/close at size 20**, lifting the share of certain closes traded from
52.1% to 57.1%. 0.987 is the exact maximum: `ceiling 0.99` and `ceiling 0.995`
produce byte-identical rows, because pinrun's EV gate refuses everything
dearer — EV(0.987) = +0.31c clears the 0.30c floor and EV(0.988) = +0.21c does
not, hand-reconciled in the self-test. So "raise the ceiling to 0.99" is
arithmetically a no-op, and the brief's 0.99 and 0.995 were never available.

**And here is its cost, which is larger than the gain and is the reason this
is a proposal and not a change.** The +$17.08 is +0.9% of nothing much —
$1.90/day at size 20 against the base's $15.16/day — and it does not clear its
own bar: **t = +0.8 against a paired MDE of $0.0575/close.** Worse, the two
dollar columns disagree: tape says +$0.0245/close, `ev` (pinrun's own
`expected_value`) says **−$0.018/close**, and by this file's stated rule a
lever whose two columns disagree is not established. The reason they disagree
is the whole risk. **All 123 of the fills this lever adds are dearer than 98c,
one of them lost on the tape, and the break-even loss rate on that population
is between 1% and 2%:**

| loss rate on the 123 dear fills | the lever is worth |
|---|---|
| 0.8% (what the tape realised) | **+$12.98** |
| 1.0% | +$9.49 |
| **2.0%** | **−$14.00** |
| 3.4% (the only LIVE rate we have, on closes) | ≈ −$37.50 at 3.0% |

The tape's rate on that population is structurally 31× too optimistic
(CLAUDE.md 2026-09-10 rule 5: 0.11% on the tape against 3.4% live, intervals
that do not overlap), and **we have never bought above 98c, so there is no
live rate at these prices at all.** Narrower still: +$15.21 of the +$17.08
comes from 64 fills in the 98.5–98.7c bucket that went 64–0 on the tape, and a
single adverse fill in that bucket costs 19 × 0.9867 = **$18.75** — more than
the entire measured gain. **So the proposal is: run it live at one contract
above 98c and count, exactly as the hedge plant was run. Do not turn it on at
size 20 from this file.**

**The tau kill is CONFIRMED, on the rebuilt replay, at today's gate — both
halves of "dearer AND less accurate".** Less accurate: the model's flip rate
per certain MARKET is 0.202% [0.104, 0.352] at tau 21–30, **0.439% [0.284,
0.648] at 31–45 (2.2×) and 0.748% [0.533, 1.021] at 46–60 (3.7×)** — the same
wall AMENDMENT 4 found at the old PIN 0.98 gate, lower in level because the
gate is tighter, identical in shape. Dearer: the mean price paid rises
monotonically with the tau of the fill, 93.63c → 94.49c → 94.92c → 95.27c →
96.33c. And the P&L follows: TAU_MAX 60 earns **+$111.46 on 175 new closes and
loses $316.32 on the closes we already traded**, because an early dear fill
burns a `MAX_PER_CLOSE` slot and raises the `IMPROVE_BY` bar against the better
offer still to come — net −$0.2939/close. **TAU_MAX 35 is the one row positive
on both components (+$13.82 new, +$29.20 shared, +$0.0617/close) and it is
still inside its MDE of $0.1013 at t = +1.2; it is the only tau extension worth
re-asking on more tape, and the question it re-asks is where the wall starts,
not whether there is one.**

**The floor lever is the only thing in this report that clears its own MDE, and
it is negative.** `MIN_FILL_FRAC` 0.5 → 0.25 buys 5 new closes worth +$0.69 and
loses **$18.48** on the closes we already trade: **−$0.0255/close, t = −5.3
against an MDE of $0.0095.** Taking a scrap fill early spends a slot and raises
the improve bar against the better price seconds later — precisely what
pinrun's AMENDMENT 6 comment says, now re-measured on the rebuilt replay. Size
is not the constraint anyway: `too_shallow` is **2.0% of the certain markets on
silent closes and 4 of the 333 silent closes**. The authoritative SIZE sweep is
`research/pinlevels.py` → `results/RESULTS_levels.md`; nothing here should be
quoted against it.

**What would have to be true for any of this to be wrong, and what was
checked.** (1) *The census could be a statement about BTC rather than the
product* — it was, in the first version: counting BOOK STATES, a market whose
book changes ~7× a second contributed 204 rows where a thin altcoin
contributed 28, and the census read "an ask exists 84% of the time" when the
per-second truth is 15.8%. Aggregating to one row per (market, second) fixed
it and a planted self-test now fails if it regresses. (2) *The replay could be
missing the offers we actually hit* — it is the rebuilt `pinsim` (per-event
decisions, seq-ordered snapshots with real `_rx_ms`), which reproduces 9 of 9
of our real losses under the live gate; the decomposition calls its
`close_slot_ok`/`close_slot_book` rather than copying the rails. (3) *The
holdout could be refuting these levers* — **it is not; it has no power.** The
base gate itself earns $0.2722/close in the train half and $0.0174 in the
holdout while trading the same share of closes (51.8% vs 52.6%) at the same
mean price (95.61c vs 95.42c); the per-close sd rises to $3.4589 and the
holdout MDEs land at 5–20× the base's own holdout level. Every "fails in the
holdout" row is **no power, not no effect**. (4) *Counts could be inflated by a
perfect-book assumption* — this window carries **3,012 `_seq_gap` flags over
675.5M delta messages (16.7/hour)**, and coverage is 99.4% of the band's
market-seconds, with the missing seconds absent rather than stale, so every
count here is a lower bound.

**The bottom line for the operator.** The biggest number on the board was
"half the certain closes trade nothing". It is real — this file reproduces it
independently of the maker study at **52.2% traded against that study's 51.8%**
— but **88% of it is a book that has no seller on the winning side, and that is
not a number we can move with a constant.** The reachable remainder is worth
about five percentage points of count and roughly $1.90/day at size 20, with a
sign that depends on a loss rate the tape is forbidden to supply. **COUNT is
now measured and it is not where the next dollar is.** What is left in this
direction is not a threshold but an instrument: the offers DO exist for a
median 1.4 s, and whether we win the race for them is still the project's
largest unmeasured risk.

## 1. The decomposition

Live band only, so this is directly comparable with `RESULTS_maker.md`'s 411 of 793. Of **696 closes with a model-certain market in tau [3,30]**, we trade on **363 (52.2%)** and nothing at all on **333 (47.8%)**.

### Per MARKET, one reason each -- the closest rung it reached

| reason | cause | markets | share of certain |
|---|---|---|---|
| `bought` | traded | 475 | 7.6% |
| `dumped` | our rules | 2 | 0.0% |
| `no_improve` | our rules | 324 | 5.2% |
| `close_cap` | our rules | 671 | 10.7% |
| `over_ceiling` | PRICE | 350 | 5.6% |
| `no_edge` | PRICE | 1,092 | 17.4% |
| `too_shallow` | SIZE | 100 | 1.6% |
| `no_offer` | LIQUIDITY | 3,254 | 51.8% |
| `stale_book` | our book | 18 | 0.3% |
| **total certain markets** | | **6,286** | 100% |
| (`no_gate`: never certain) | no signal | 5 | -- |
| (`no_model`: no sigma/fair) | no signal | 0 | -- |

| cause | markets | share | the fix it implies |
|---|---|---|---|
| **LIQUIDITY** | 3,254 | 51.8% | nothing we can price -- nobody is offering |
| **PRICE** | 1,442 | 22.9% | raise PRICE_CEILING / EV_FLOOR |
| **our rules** | 997 | 15.9% | loosen a rail (measured elsewhere) |
| **traded** | 475 | 7.6% | none |
| **SIZE** | 100 | 1.6% | lower SIZE or MIN_FILL_FRAC |
| **our book** | 18 | 0.3% | faster book / longer staleness budget |

### The SAME table restricted to the closes we traded NOTHING on

This is the table the question asks for: the 333 certain closes where we bought nothing, decomposed over their markets. The rungs a traded close reaches -- `close_cap`, `no_improve`, `bought` -- cannot appear here, so what is left is the reason the close was untradeable.

| reason | cause | markets | share of certain markets on silent closes |
|---|---|---|---|
| `dumped` | our rules | 2 | 0.1% |
| `over_ceiling` | PRICE | 233 | 7.7% |
| `no_edge` | PRICE | 512 | 17.0% |
| `too_shallow` | SIZE | 61 | 2.0% |
| `no_offer` | LIQUIDITY | 2,185 | 72.6% |
| `stale_book` | our book | 18 | 0.6% |
| **total certain markets on silent closes** | | **3,011** | 100% |
| (`no_gate`) | no signal | 4 | -- |
| (`no_model`) | no sigma/fair | 0 | -- |

| cause | markets | share | the fix it implies |
|---|---|---|---|
| **LIQUIDITY** | 2,185 | 72.6% | nothing we can price -- nobody is offering |
| **PRICE** | 745 | 24.7% | raise PRICE_CEILING / EV_FLOOR |
| **SIZE** | 61 | 2.0% | lower SIZE or MIN_FILL_FRAC |
| **our book** | 18 | 0.6% | faster book / longer staleness budget |
| **our rules** | 2 | 0.1% | loosen a rail (measured elsewhere) |

### Per CLOSE -- the best rung any of its markets reached

| best reason on the close | cause | closes | share |
|---|---|---|---|
| `bought` | traded | 363 | 52.2% |
| `dumped` | our rules | 2 | 0.3% |
| `over_ceiling` | PRICE | 140 | 20.1% |
| `no_edge` | PRICE | 109 | 15.7% |
| `too_shallow` | SIZE | 9 | 1.3% |
| `no_offer` | LIQUIDITY | 71 | 10.2% |
| `stale_book` | our book | 2 | 0.3% |

**Read the per-close table, not the per-market one, for what to fix.** A close is tradeable if ANY of its twelve markets is; the per-market table is dominated by the many markets in a close we already traded.

### Coverage first -- how much of the band the tape actually holds

The live band is 28 seconds wide. **6,291 markets appear in it at all, so a complete tape would hold 176,148 market-seconds; the replay produced 175,058 (99.4%).**

The shortfall is NOT a stale book and cannot be read off the stale count. With no events arriving, `pinsim.Walk`'s clock never reaches those seconds and the replay generates no moment at all -- the second is absent, not stale. `results/RESULTS_tapegaps.md` measured 3.28% of trading-window seconds inside a silent run of >= 10 s, collector-side, with the book going quiet alongside the trades. **So every COUNT below is a lower bound**, and a market that never produced a single book event in the band does not appear in the market total above either.

### The offer census -- what was actually on our side of the book

Every certain (market, second) inside tau [3,30] with a fresh book and index. A CENSUS: market-seconds are the unit and are never used as `n` for a t-statistic. 167,818 certain market-seconds, of which 360 (0.2%) had a stale book or index and are excluded below.

| on our side of the book | market-seconds | share of fresh certain |
|---|---|---|
| an ask exists | 26,468 | 15.8% |
| ...and >= 10 contracts rest on it (the SIZE 20 floor) | 24,655 | 14.7% |
| ...and >= 10 AND at or below the 98c ceiling | 2,996 | 1.8% |
| ...>= 5 contracts | 24,877 | 14.9% |
| ...>= 5 AND at or below 98c | 3,058 | 1.8% |
| ...>= 2 contracts | 25,169 | 15.0% |
| ...>= 2 AND at or below 98c | 3,117 | 1.9% |
| ...>= 1 contract | 25,266 | 15.1% |
| ...>= 1 AND at or below 98c | 3,141 | 1.9% |
| NO ask on our side at any price | 140,990 | 84.2% |
| ...but the LOSING side still had an ask | 140,989 | 84.2% |
| ...and neither side had one (book dead) | 1 | 0.0% |

**The one-sidedness is the mechanism.** When the outcome becomes obvious the losing side's bids vanish, so the winner has no ask -- that is 140,989 of the 140,990 unoffered market-seconds (100.0%), where the book was NOT dead, just one-sided against us. That is a capacity limit, not a data limit, and no threshold reaches it.

Two SEPARATE distributions, not a subset: the left column is the cheapest ask of any size, the right the cheapest ask holding at least 10 contracts. A market-second can sit in different buckets in the two columns, so the right column is not a subset of the left.

| price bucket | market-seconds by CHEAPEST ask | market-seconds by cheapest >= 10-DEEP ask |
|---|---|---|
| <=98.0c | 3,165 | 2,996 |
| 98.0-98.7c | 1,047 | 1,044 |
| 98.7-99.0c | 1,216 | 1,216 |
| 99.0-99.5c | 3,034 | 2,869 |
| >99.5c | 18,006 | 16,530 |

### The silent closes, by the CHEAPEST offer that ever appeared on them

For each of the 333 certain closes we traded nothing on: the cheapest ask that appeared on the model's side, on any of its markets, at any second in tau [3,30], with a fresh book -- at two size floors. **98.7c is where pinrun's own EV gate stops, not where the ceiling stops** (hand-reconciled in the self-test: EV(0.987)=+0.31c clears the 0.30c floor and EV(0.988)=+0.21c does not), so the `98.0-98.7c` rows are the only price headroom that exists without also moving EV_FLOOR or MEASURED_FLIP.

| the best offer the close ever showed | closes | share of silent | the lever that would reach it |
|---|---|---|---|
| dearer than 98.7c only | 219 | 65.8% | EV_FLOOR / MEASURED_FLIP, not the ceiling |
| no ask on our side; the loser still had one | 71 | 21.3% | nothing -- LIQUIDITY (one-sided book) |
| deep, 98.0-98.7c | 35 | 10.5% | **PRICE_CEILING -> 0.987** |
| at or below 98c but under 10 deep | 3 | 0.9% | **MIN_FILL_FRAC (or SIZE)** |
| no ask on our side, ever | 2 | 0.6% | nothing -- LIQUIDITY |
| deep AND at or below 98c (blocked downstream) | 2 | 0.6% | none -- a rail or the edge/EV/dump test refused it |
| 98.0-98.7c and under 10 deep | 1 | 0.3% | BOTH of the above |

## 2. The MDE, stated before the estimates

Per-close P&L at the base gate has sd **$2.6843** over 697 closes, so the smallest change in $/close this window can distinguish from zero at t=1.96 is **$0.1996/close** on the LEVEL.

Every lever below is compared to the base on the SAME closes, so the relevant MDE is on the PAIRED difference, which is much smaller because the closes both configurations trade identically cancel. Each row carries its own paired MDE.

## 3. The size question -- SCOPE: the floor, not the size

`too_shallow` refuses an offer smaller than max(MIN_LEVEL, MIN_FILL_FRAC x SIZE) = 10 contracts at SIZE 20. Two DIFFERENT levers lower that floor: cut SIZE, which also cuts what we win on the deep books, or cut MIN_FILL_FRAC, which keeps the maximum at 20 and only allows a partial.

**The authoritative SIZE table is `results/RESULTS_levels.md`** (`research/pinlevels.py`), a concurrent full-history job sweeping SIZE over all 422 book hours with hedge on and off and bootstrap intervals. A full-history sweep supersedes anything a 7-day window can say about SIZE, so the SIZE rows below are printed for continuity with the decomposition and **must not be quoted against it**. What THIS file owns is the `too_shallow` COUNT above -- whether size is even the binding constraint -- and the MIN_FILL_FRAC rows, which that job does not sweep. **As of this build `results/RESULTS_levels.md` does not exist on disk**, so the SIZE question is formally unanswered here; do not read the collapsed rows below as the answer.

### MIN_FILL_FRAC -- the floor alone, maximum size unchanged

| config | floor | closes traded | fills | $/close (tape) | $/close (ev) | $/fill | mean px | days + | paired diff | MDE | t |
|---|---|---|---|---|---|---|---|---|---|---|---|
| BASE (live gate) | 10 | 363 (52.1%) | 475 | $0.1958 | $0.4194 | $0.2873 | 0.9556 | 7/9 | -- | -- | -- |
| SIZE 20 frac 0.25 | 5 | 368 (52.8%) | 483 | $0.1703 | $0.4005 | $0.2457 | 0.9556 | 6/9 | $-0.0255 | $0.0095 | -5.3 |
| SIZE 20 frac 0.05 | 1 | 371 (53.2%) | 491 | $0.1889 | $0.3768 | $0.2682 | 0.9553 | 5/9 | $-0.0069 | $0.0604 | -0.2 |

Where the difference comes from -- **a COUNT lever must earn it on NEW closes**, and the three components sum to the paired difference exactly:

| config | NEW closes | $ from new | closes LOST | $ lost | shared closes | extra fills on shared | $ change on shared |
|---|---|---|---|---|---|---|---|
| SIZE 20 frac 0.25 | 5 | $+0.69 | 0 | $+0.00 | 363 | +3 | $-18.48 |
| SIZE 20 frac 0.05 | 8 | $+0.61 | 0 | $+0.00 | 363 | +8 | $-5.40 |

<details><summary>SIZE rows, for continuity only -- RESULTS_levels.md is authoritative</summary>

### SIZE (superseded by results/RESULTS_levels.md)

| config | floor | closes traded | fills | $/close (tape) | $/close (ev) | $/fill | mean px | days + | paired diff | MDE | t |
|---|---|---|---|---|---|---|---|---|---|---|---|
| BASE (live gate) | 10 | 363 (52.1%) | 475 | $0.1958 | $0.4194 | $0.2873 | 0.9556 | 7/9 | -- | -- | -- |
| SIZE 10 | 5 | 368 (52.8%) | 483 | $0.0911 | $0.2174 | $0.1315 | 0.9556 | 7/9 | $-0.1047 | $0.0961 | -2.1 |
| SIZE 5 | 2.5 | 370 (53.1%) | 487 | $0.0525 | $0.1119 | $0.0751 | 0.9555 | 7/9 | $-0.1433 | $0.1480 | -1.9 |
| SIZE 2 | 1 | 371 (53.2%) | 491 | $0.0216 | $0.0450 | $0.0306 | 0.9553 | 7/9 | $-0.1742 | $0.1790 | -1.9 |
| SIZE 1 | 1 | 371 (53.2%) | 491 | $0.0107 | $0.0230 | $0.0152 | 0.9553 | 7/9 | $-0.1851 | $0.1891 | -1.9 |

Where the difference comes from -- **a COUNT lever must earn it on NEW closes**, and the three components sum to the paired difference exactly:

| config | NEW closes | $ from new | closes LOST | $ lost | shared closes | extra fills on shared | $ change on shared |
|---|---|---|---|---|---|---|---|
| SIZE 10 | 5 | $+0.69 | 0 | $+0.00 | 363 | +3 | $-73.65 |
| SIZE 5 | 7 | $+0.57 | 0 | $+0.00 | 363 | +5 | $-100.48 |
| SIZE 2 | 8 | $+0.30 | 0 | $+0.00 | 363 | +8 | $-121.74 |
| SIZE 1 | 8 | $+0.16 | 0 | $+0.00 | 363 | +8 | $-129.16 |

</details>

## 4. The ceiling question

PRICE_CEILING is 0.98. **Raising it alone cannot work above ~0.987**, because pinrun's EV gate (EV_FLOOR 0.003, MEASURED_FLIP 0.009) refuses everything dearer: EV(0.980)=+0.96c, EV(0.985)=+0.49c, EV(0.988)=+0.21c, EV(0.990)=+0.03c, EV(0.995)=-0.44c against a floor of 0.3c. The `noEV` rows lift that gate to show what is THERE; they are not a proposal, because the loss rate WE would suffer at 99c+ has never been measured live -- we have never bought above 0.98.

**And the live loss rate cannot price this lever, which is the honest answer to "use the live rate, not the tape rate".** The live rate we have is at the CLOSE level -- 2 losses in 59 closes at the current gate, `results/SKIM.md` -- and it is not decomposable by price. If 3.4% were applied flatly per fill, EV at 98.0c would be -1.54c per contract, i.e. every trade we take would lose money -- which is not what the live ledger records. So a flat rate is the wrong model, which is precisely why `MEASURED_FLIP` is estimated on DEAR trades only. **The consequence for this lever is that there is NO live loss rate above 98.0c at all, because we have never bought there.** Any ceiling above 98.7c is therefore an extrapolation and is not proposable from this file; the tape columns rank, they do not price.

### Ceiling

| config | floor | closes traded | fills | $/close (tape) | $/close (ev) | $/fill | mean px | days + | paired diff | MDE | t |
|---|---|---|---|---|---|---|---|---|---|---|---|
| BASE (live gate) | 10 | 363 (52.1%) | 475 | $0.1958 | $0.4194 | $0.2873 | 0.9556 | 7/9 | -- | -- | -- |
| ceiling 0.985 | 10 | 388 (55.7%) | 517 | $0.1989 | $0.4164 | $0.2682 | 0.9586 | 7/9 | $+0.0031 | $0.0127 | +0.5 |
| ceiling 0.987 | 10 | 398 (57.1%) | 548 | $0.2203 | $0.4014 | $0.2802 | 0.9615 | 8/9 | $+0.0245 | $0.0575 | +0.8 |
| ceiling 0.99 | 10 | 398 (57.1%) | 548 | $0.2203 | $0.4014 | $0.2802 | 0.9615 | 8/9 | $+0.0245 | $0.0575 | +0.8 |
| ceiling 0.995 | 10 | 398 (57.1%) | 548 | $0.2203 | $0.4014 | $0.2802 | 0.9615 | 8/9 | $+0.0245 | $0.0575 | +0.8 |
| ceiling 0.985 noEV | 10 | 388 (55.7%) | 517 | $0.1989 | $0.4164 | $0.2682 | 0.9586 | 7/9 | $+0.0031 | $0.0127 | +0.5 |
| ceiling 0.99 noEV | 10 | 436 (62.6%) | 608 | $0.2158 | $0.3811 | $0.2474 | 0.9657 | 7/9 | $+0.0200 | $0.0586 | +0.7 |
| ceiling 0.995 noEV | 10 | 484 (69.4%) | 714 | $0.1626 | $0.3308 | $0.1587 | 0.9722 | 6/9 | $-0.0332 | $0.0857 | -0.8 |
| ceiling 0.987 + TAU_MAX 45 | 10 | 501 (71.9%) | 746 | $0.2579 | $0.5599 | $0.2410 | 0.9606 | 6/9 | $+0.0621 | $0.2051 | +0.6 |

Where the difference comes from -- **a COUNT lever must earn it on NEW closes**, and the three components sum to the paired difference exactly:

| config | NEW closes | $ from new | closes LOST | $ lost | shared closes | extra fills on shared | $ change on shared |
|---|---|---|---|---|---|---|---|
| ceiling 0.985 | 25 | $+7.22 | 0 | $+0.00 | 363 | +17 | $-5.05 |
| ceiling 0.987 | 35 | $+9.72 | 0 | $+0.00 | 363 | +37 | $+7.36 |
| ceiling 0.99 | 35 | $+9.72 | 0 | $+0.00 | 363 | +37 | $+7.36 |
| ceiling 0.995 | 35 | $+9.72 | 0 | $+0.00 | 363 | +37 | $+7.36 |
| ceiling 0.985 noEV | 25 | $+7.22 | 0 | $+0.00 | 363 | +17 | $-5.05 |
| ceiling 0.99 noEV | 73 | $+17.10 | 0 | $+0.00 | 363 | +57 | $-3.17 |
| ceiling 0.995 noEV | 121 | $+21.38 | 0 | $+0.00 | 363 | +103 | $-44.51 |
| ceiling 0.987 + TAU_MAX 45 | 138 | $+75.69 | 0 | $+0.00 | 363 | +117 | $-32.41 |

### Ceiling with the EV gate lifted (COUNT ONLY, NOT A PROPOSAL)

| config | floor | closes traded | fills | $/close (tape) | $/close (ev) | $/fill | mean px | days + | paired diff | MDE | t |
|---|---|---|---|---|---|---|---|---|---|---|---|
| BASE (live gate) | 10 | 363 (52.1%) | 475 | $0.1958 | $0.4194 | $0.2873 | 0.9556 | 7/9 | -- | -- | -- |
| ceiling 0.985 noEV | 10 | 388 (55.7%) | 517 | $0.1989 | $0.4164 | $0.2682 | 0.9586 | 7/9 | $+0.0031 | $0.0127 | +0.5 |
| ceiling 0.99 noEV | 10 | 436 (62.6%) | 608 | $0.2158 | $0.3811 | $0.2474 | 0.9657 | 7/9 | $+0.0200 | $0.0586 | +0.7 |
| ceiling 0.995 noEV | 10 | 484 (69.4%) | 714 | $0.1626 | $0.3308 | $0.1587 | 0.9722 | 6/9 | $-0.0332 | $0.0857 | -0.8 |

Where the difference comes from -- **a COUNT lever must earn it on NEW closes**, and the three components sum to the paired difference exactly:

| config | NEW closes | $ from new | closes LOST | $ lost | shared closes | extra fills on shared | $ change on shared |
|---|---|---|---|---|---|---|---|
| ceiling 0.985 noEV | 25 | $+7.22 | 0 | $+0.00 | 363 | +17 | $-5.05 |
| ceiling 0.99 noEV | 73 | $+17.10 | 0 | $+0.00 | 363 | +57 | $-3.17 |
| ceiling 0.995 noEV | 121 | $+21.38 | 0 | $+0.00 | 363 | +103 | $-44.51 |

### The fills the ceiling lever ADDS, and the loss rate that flips their sign

Every fill `ceiling 0.987` takes, by price. The rows above 98.0c are the ones the lever adds and they are the whole of its risk. **The loss column is the REPLAY's population, not ours** -- it is here to locate the money, not to price it.

| price of the fill | fills | lost (replay) | total $ | $/fill | mean px |
|---|---|---|---|---|---|
| <=90c | 33 | 1 | $+53.78 | $+1.6298 | 0.8764 |
| 90-95c | 107 | 3 | $+72.66 | $+0.6790 | 0.9343 |
| 95-97c | 120 | 4 | $+5.44 | $+0.0453 | 0.9635 |
| 97-98c | 165 | 3 | $+8.69 | $+0.0527 | 0.9773 |
| **98.0-98.5c (new)** | 59 | 1 | $-2.23 | $-0.0377 | 0.9830 |
| **98.5-98.7c (new)** | 64 | 0 | $+15.21 | $+0.2377 | 0.9867 |

**123 fills above the 98c ceiling, 1 lost in the replay, $+12.98 realised.** At a mean 98.49c on 19.1 contracts, here is what the SAME fills are worth at other loss rates -- the arithmetic the tape cannot settle, because we have never bought above 98c live and so have no live rate at these prices:

| loss rate on the dear fills | $/dear fill | total over this window |
|---|---|---|
| 0.5% | $+0.1727 | $+21.24 |
| 1.0% | $+0.0772 | $+9.49 |
| 1.5% | $-0.0183 | $-2.26 |
| 2.0% | $-0.1139 | $-14.00 |
| 3.0% | $-0.3049 | $-37.50 |
| 5.0% | $-0.6870 | $-84.50 |

The replay realised 0.8% here. The tape's loss rate on a population like this is structurally ~31x too optimistic (0.11% tape vs 3.4% live at the current gate, intervals that do not overlap). **Between 1% and 2% the lever changes sign.**

## 5. The tau question, re-tested on the rebuilt replay

Extending TAU_MAX was killed as 'dearer AND less accurate' on the OLD replay, which sampled once a second and applied every snapshot at ts 0. Re-measured here.

Model accuracy by tau, from the replay -- what the model computed against what the market did, on every certain (market, second) moment. **This is a model-calibration statistic, not our loss rate**: its population is 'the model was certain', not 'someone sold it to us'.

Reported twice. Market-seconds are the raw census; **MARKETS is the unit that means anything**, because seconds inside one market are not independent (one wrong call prints ~28 wrong seconds).

| tau band | certain market-seconds | won | acc | certain MARKETS | won | acc | markets the model got WRONG |
|---|---|---|---|---|---|---|---|
| 0-4s | 12,445 | 12,445 | 100.000% | 6,238 | 6,238 | 100.00% | 0 |
| 5-9s | 30,996 | 30,995 | 99.997% | 6,241 | 6,240 | 99.98% | 1 |
| 10-14s | 30,567 | 30,557 | 99.967% | 6,171 | 6,168 | 99.95% | 3 |
| 15-19s | 30,036 | 30,009 | 99.910% | 6,070 | 6,061 | 99.85% | 9 |
| 20-24s | 29,429 | 29,410 | 99.935% | 5,963 | 5,959 | 99.93% | 4 |
| 25-29s | 28,690 | 28,664 | 99.909% | 5,817 | 5,810 | 99.88% | 7 |
| 30-34s | 27,968 | 27,917 | 99.818% | 5,681 | 5,670 | 99.81% | 11 |
| 35-39s | 27,153 | 27,101 | 99.808% | 5,518 | 5,502 | 99.71% | 16 |
| 40-44s | 26,301 | 26,230 | 99.730% | 5,375 | 5,354 | 99.61% | 21 |
| 45-49s | 25,392 | 25,301 | 99.642% | 5,208 | 5,188 | 99.62% | 20 |
| 50-54s | 24,384 | 24,273 | 99.545% | 5,021 | 4,995 | 99.48% | 26 |
| 55-59s | 23,311 | 23,170 | 99.395% | 4,812 | 4,779 | 99.31% | 33 |
| 60-64s | 4,554 | 4,525 | 99.363% | 4,554 | 4,525 | 99.36% | 29 |

**The same thing in AMENDMENT 4's own bands, which is the number that killed this lever.** pinrun's comment records, at the OLD gate PIN=0.98: tau 3-10 575 moments 0 flips; 11-20 1,772 / 0; 21-30 2,872 / 0; 31-45 7,302 / 25 (3.7x overconfident); 46-60 10,047 / 126 (10.9x). The gate is now 0.995, so the population is not the same one and the comparison is of TODAY'S gate against that wall.

| tau band | certain market-seconds | flips | flip rate | certain MARKETS | markets the model got WRONG | market flip rate | 95% CI on the market rate |
|---|---|---|---|---|---|---|---|
| 3-10s | 49,605 | 1 | 0.0020% | 6,277 | 1 | 0.016% | [0.000, 0.089] |
| 11-20s | 60,379 | 41 | 0.0679% | 6,158 | 11 | 0.179% | [0.089, 0.319] |
| 21-30s | 57,834 | 51 | 0.0882% | 5,944 | 12 | 0.202% | [0.104, 0.352] |
| 31-45s | 80,930 | 181 | 0.2237% | 5,692 | 25 | 0.439% | [0.284, 0.648] |
| 46-60s | 72,478 | 355 | 0.4898% | 5,213 | 39 | 0.748% | [0.533, 1.021] |

**And what the extra fills actually cost, which is the other half of the old kill ("dearer AND less accurate").** Every fill the widest configuration takes, grouped by the tau it was taken at. If the long horizon were dearer, the price column would rise with tau.

| tau of the fill | fills | mean price | tape wins | tape $/fill | mean contracts |
|---|---|---|---|---|---|
| 3-10s | 27 | 0.9363 | 27 | $+1.1109 | 18.7 |
| 11-20s | 42 | 0.9449 | 39 | $-0.2048 | 18.7 |
| 21-30s | 64 | 0.9492 | 59 | $-0.6187 | 19.1 |
| 31-45s | 138 | 0.9527 | 133 | $+0.1815 | 18.7 |
| 46-60s | 569 | 0.9633 | 547 | $-0.1322 | 18.8 |

### TAU_MAX

| config | floor | closes traded | fills | $/close (tape) | $/close (ev) | $/fill | mean px | days + | paired diff | MDE | t |
|---|---|---|---|---|---|---|---|---|---|---|---|
| BASE (live gate) | 10 | 363 (52.1%) | 475 | $0.1958 | $0.4194 | $0.2873 | 0.9556 | 7/9 | -- | -- | -- |
| TAU_MAX 35 | 10 | 394 (56.5%) | 527 | $0.2575 | $0.4803 | $0.3406 | 0.9548 | 7/9 | $+0.0617 | $0.1013 | +1.2 |
| TAU_MAX 40 | 10 | 431 (61.8%) | 598 | $0.2360 | $0.5541 | $0.2751 | 0.9538 | 7/9 | $+0.0402 | $0.1655 | +0.5 |
| TAU_MAX 45 | 10 | 461 (66.1%) | 660 | $0.2167 | $0.5920 | $0.2289 | 0.9550 | 6/9 | $+0.0209 | $0.2041 | +0.2 |
| TAU_MAX 60 | 10 | 538 (77.2%) | 840 | $-0.0981 | $0.6684 | $-0.0814 | 0.9587 | 5/9 | $-0.2939 | $0.3369 | -1.7 |

Where the difference comes from -- **a COUNT lever must earn it on NEW closes**, and the three components sum to the paired difference exactly:

| config | NEW closes | $ from new | closes LOST | $ lost | shared closes | extra fills on shared | $ change on shared |
|---|---|---|---|---|---|---|---|
| TAU_MAX 35 | 31 | $+13.82 | 0 | $+0.00 | 363 | +21 | $+29.20 |
| TAU_MAX 40 | 68 | $+40.01 | 0 | $+0.00 | 363 | +52 | $-11.98 |
| TAU_MAX 45 | 98 | $+66.86 | 0 | $+0.00 | 363 | +77 | $-52.27 |
| TAU_MAX 60 | 175 | $+111.46 | 0 | $+0.00 | 363 | +142 | $-316.32 |

### Combinations

| config | floor | closes traded | fills | $/close (tape) | $/close (ev) | $/fill | mean px | days + | paired diff | MDE | t |
|---|---|---|---|---|---|---|---|---|---|---|---|
| BASE (live gate) | 10 | 363 (52.1%) | 475 | $0.1958 | $0.4194 | $0.2873 | 0.9556 | 7/9 | -- | -- | -- |
| SIZE 5 + frac 0.05 | 1 | 371 (53.2%) | 491 | $0.0572 | $0.1077 | $0.0812 | 0.9553 | 6/9 | $-0.1386 | $0.1518 | -1.8 |
| SIZE 20 frac 0.05 + TAU_MAX 45 | 1 | 469 (67.3%) | 679 | $0.1327 | $0.5193 | $0.1362 | 0.9547 | 6/9 | $-0.0631 | $0.2048 | -0.6 |
| ceiling 0.987 + TAU_MAX 45 | 10 | 501 (71.9%) | 746 | $0.2579 | $0.5599 | $0.2410 | 0.9606 | 6/9 | $+0.0621 | $0.2051 | +0.6 |

Where the difference comes from -- **a COUNT lever must earn it on NEW closes**, and the three components sum to the paired difference exactly:

| config | NEW closes | $ from new | closes LOST | $ lost | shared closes | extra fills on shared | $ change on shared |
|---|---|---|---|---|---|---|---|
| SIZE 5 + frac 0.05 | 8 | $+0.59 | 0 | $+0.00 | 363 | +8 | $-97.20 |
| SIZE 20 frac 0.05 + TAU_MAX 45 | 106 | $+59.02 | 0 | $+0.00 | 363 | +87 | $-102.99 |
| ceiling 0.987 + TAU_MAX 45 | 138 | $+75.69 | 0 | $+0.00 | 363 | +117 | $-32.41 |

## 6. The holdout -- first 70% / last 30% of closes

Chronological split of the 697 certain closes: **488 train** (09-04T22 .. 09-10T12) and **209 holdout** (09-10T12 .. 09-12T18). Nothing is a survivor unless the paired difference holds in the holdout.

**READ THE POWER BEFORE THE TABLE.** The BASE gate itself earns $0.2722/close in the train half and $0.0174 in the holdout -- it trades the same share of closes in both (51.8% vs 52.6%) and pays the same mean price (0.9561 vs 0.9542), so the COUNT is stable and it is the OUTCOMES in the holdout window that are worse: 6 of 140 replayed fills lost there against 7 of 335 in the train half. **That is the replay's own population, not ours, and it is not a loss rate for us** (CLAUDE.md 2026-09-10 rule 5) -- it is quoted only to explain the variance. The consequence is that the holdout's per-close sd RISES to $3.4589, so its MDEs are 5-20x the base's own holdout level and **every 'fails in the holdout' below is NO POWER, not NO EFFECT**. The holdout can refute a lever that is large; it cannot confirm or deny one worth a few cents a close.

| config | train closes traded | train $/close | train diff | hold closes traded | hold $/close | hold diff | hold MDE | hold t | hold NEW closes | hold $ from new |
|---|---|---|---|---|---|---|---|---|---|---|
| BASE (live gate) | 253 | $0.2722 | -- | 110 | $0.0174 | -- | -- | -- | -- | -- |
| SIZE 10 | 257 | $0.1328 | $-0.1394 | 111 | $-0.0063 | $-0.0237 | $0.2237 | -0.2 | 1 | $+0.09 |
| SIZE 5 | 259 | $0.0707 | $-0.2015 | 111 | $0.0100 | $-0.0075 | $0.3503 | -0.0 | 1 | $+0.09 |
| SIZE 2 | 260 | $0.0308 | $-0.2414 | 111 | $0.0001 | $-0.0173 | $0.4218 | -0.1 | 1 | $+0.04 |
| SIZE 1 | 260 | $0.0149 | $-0.2573 | 111 | $0.0010 | $-0.0164 | $0.4467 | -0.1 | 1 | $+0.02 |
| SIZE 20 frac 0.25 | 257 | $0.2430 | $-0.0292 | 111 | $0.0004 | $-0.0171 | $0.0151 | -2.2 | 1 | $+0.09 |
| SIZE 20 frac 0.05 | 260 | $0.2679 | $-0.0043 | 111 | $0.0046 | $-0.0128 | $0.0890 | -0.3 | 1 | $+0.09 |
| ceiling 0.985 | 271 | $0.2774 | $+0.0052 | 117 | $0.0157 | $-0.0018 | $0.0304 | -0.1 | 7 | $+2.00 |
| ceiling 0.987 | 278 | $0.3069 | $+0.0347 | 120 | $0.0180 | $+0.0006 | $0.0320 | +0.0 | 10 | $+2.72 |
| ceiling 0.99 | 278 | $0.3069 | $+0.0347 | 120 | $0.0180 | $+0.0006 | $0.0320 | +0.0 | 10 | $+2.72 |
| ceiling 0.995 | 278 | $0.3069 | $+0.0347 | 120 | $0.0180 | $+0.0006 | $0.0320 | +0.0 | 10 | $+2.72 |
| ceiling 0.985 noEV | 271 | $0.2774 | $+0.0052 | 117 | $0.0157 | $-0.0018 | $0.0304 | -0.1 | 7 | $+2.00 |
| ceiling 0.99 noEV | 305 | $0.2973 | $+0.0251 | 131 | $0.0254 | $+0.0080 | $0.0336 | +0.5 | 21 | $+4.92 |
| ceiling 0.995 noEV | 340 | $0.2803 | $+0.0081 | 144 | $-0.1121 | $-0.1296 | $0.2084 | -1.2 | 34 | $+5.36 |
| TAU_MAX 35 | 275 | $0.3647 | $+0.0925 | 119 | $0.0074 | $-0.0101 | $0.2766 | -0.1 | 9 | $+4.59 |
| TAU_MAX 40 | 304 | $0.3843 | $+0.1121 | 127 | $-0.1101 | $-0.1275 | $0.4315 | -0.6 | 17 | $+8.13 |
| TAU_MAX 45 | 326 | $0.3170 | $+0.0448 | 135 | $-0.0173 | $-0.0347 | $0.3995 | -0.2 | 25 | $+15.20 |
| TAU_MAX 60 | 379 | $-0.0461 | $-0.3183 | 159 | $-0.2196 | $-0.2370 | $0.6962 | -0.7 | 49 | $+34.52 |
| SIZE 5 + frac 0.05 | 260 | $0.0799 | $-0.1923 | 111 | $0.0041 | $-0.0133 | $0.3507 | -0.1 | 1 | $+0.09 |
| SIZE 20 frac 0.05 + TAU_MAX 45 | 333 | $0.2398 | $-0.0324 | 136 | $-0.1172 | $-0.1347 | $0.3970 | -0.7 | 26 | $+10.87 |
| ceiling 0.987 + TAU_MAX 45 | 356 | $0.3459 | $+0.0738 | 145 | $0.0523 | $+0.0349 | $0.3583 | +0.2 | 35 | $+17.84 |

With 20 levers on the table, the multiple-looks bar at 5% two-sided is |t| >= 3.04 in the holdout, not 2.0.

