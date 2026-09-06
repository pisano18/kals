# JOB 3 — RISK / REWARD

**How `pin` should be sized against the operator's $250 drawdown clause.**
Written 2026-09-06. Everything from the caches; no `load_quotes`, no tape read.
Both collectors verified alive before, during and after.

---

## THE ANSWER IN ONE PARAGRAPH

**`pin` is two strategies wearing one name, and only one of them makes money.**
The **DEAR** leg (buy near-certainty at ~97c) earns **$102.66/day** on **$267 of
peak concurrent capital** — **38.4% per day on capital deployed, $0.0260 per
contract per day** — with a max drawdown of **$28.64**. The **CHEAP** leg (sell
near-certainty, i.e. buy a ~1c lottery ticket) earns **−$1.54/day**, and its 95%
interval spans zero on both bootstraps, so the honest verdict is **no
measurable edge**. It costs **$150.99 of drawdown** to hold — **5.3× the DEAR
leg's** — and it is what turns the whole strategy's worst close from $28.64
into $51.05. **Dropping it raises $/day slightly, halves the drawdown, cuts
top-10 concentration from 36.6% to 22.0%, and takes the worst simulated 7-day
path drawdown from $228.7 to $109.9.** A daily max-loss stop cannot help,
because `pin`'s entire observed drawdown is **one close**, not a streak.
**The $250 clause does not bind at the frozen size** — depth does, at roughly
2× — and capital binds at 3.7×.

---

## 0. THE CELL, AND WHAT IS IN-SAMPLE

The frozen PREREG rule: `tau<=60s`, edge floor `0.5c`, pin threshold `0.98`,
**every market at every close**, rule `"first"`, size **`min(100, 0.25 ×
resting depth at the touch)`**. Walk-forward throughout: every trade priced by
a `k` fitted only on closes strictly earlier than its own (`k` ranged
**1.215 → 1.555** over the window).

| | |
|---|---|
| rows | 169,254 (`rows_tau60.pkl`) |
| closes available in window | **842** over **9.583 days** (87.9/day) |
| closes that fired | 712 |
| trades | **2,638** |
| UTC days | **11** (two partial at the edges) |
| series | **9** — BNB, BTC, DOGE, ETH, HYPE, NEAR, SOL, XRP, ZEC |
| depth attach failures | 2 of 2,641 |

**Reconciliation against `PREREG_pin.md` §3, which this pipeline reproduces
exactly:**

| | PREREG §3 | measured here |
|---|---|---|
| trades | 2,638 | **2,638** |
| $/day | $101 | **$101.12** |
| max drawdown | $51 | **$51.05** |
| average fill | 30.4 contracts | **30.4** |

One line does **not** reconcile: PREREG §3 says *"2,638 trades over 364
closes"*. I count **712 fired closes** and 842 available. The trade count,
$/day, drawdown and fill all match to the cent, so the arithmetic agrees and
the "364" appears to be a stale figure carried into that document. **Flagged,
not fixed** — I did not write to `PREREG_pin.md`.

**WHAT IS IN-SAMPLE.** Everything. The `k` is walk-forward, but **all 95 cells
below were scored on the same 9.583 days**. The leg split, the stop level, the
coin count and the size multiple are all chosen with this tape in view. See §8.

---

## 1. THE SELF-TEST — the deliverable

Written before any of the real data was scored, in
`C:\Users\Joe\AppData\Local\Temp\kals-work\job3rr\selftest.py`.

```
ALL 60 CHECKS PASSED
```

The check the whole report rests on is **#6**, because the task says the
close-level iid bootstrap flatters us and I had to prove my code can see that:

| synthetic world | block width vs iid width |
|---|---|
| no within-day correlation | 0.74× — **they agree** |
| strong within-day shock (sd 5 vs noise 1) | **9.9× wider** |

and on the correlated world the iid 5%-worst week reads **−1,961** where the
block bootstrap reads **−3,865**. So the machinery reproduces exactly the
failure the task warned about, on data where the answer is known.

Also checked against hand-computed answers: `maxdd` from the running peak (not
from zero), Kelly's textbook `(p−c)/(1−c)` plus log-growth optimality by
simulation, leg additivity to 1e-9 on a fixed universe, peak capital as the
**max** over closes (not the sum), partial-day scaling, and the stop-loss
firing on the breaching close in **time** order with a reset at the day
boundary.

### MUTATION TEST — 23 deliberately wrong estimators

```
KILL RATE: 23/23 = 100%
```

(`mutate.py`; for scale, `pin`'s own self-test kills 67% and `informed`'s 40%.)
Killed include: drawdown measured from zero; capital summed across closes
instead of maxed; cents/dollars dropped; the horizon bootstrap resampling
**closes instead of whole days**; the stop walking input order; the stop
dropping its breaching close (a look-ahead); Kelly's denominator; the fixed
universe dropped, which is what makes the legs stop adding up.

**One mutant survived the first run** — `by_day` not ordering closes within a
day — because my ordering test happened to use a case where input order already
matched time order. The test was rewritten to differ, and it now kills it. That
is the mutation test doing its job on my own test.

---

## 2. SPLIT THE LEGS

**DEAR** = the market prices near-certainty too cheaply, so we buy it at ~97c;
wins ~2.6c almost always, loses ~95c on a flip.
**CHEAP** = the market prices near-certainty too dearly, so we sell it — which
is buying the near-impossible side at ~1c; loses ~0.8c almost always, wins ~90c
on a flip.

The cut is at **50c of cost per contract**. It is a gap, not a slice through a
crowd: **only 64 of 2,638 contracts (2.4%) cost between 10c and 90c**, and
sweeping the cut from 5c to 90c moves nothing that matters (§7A).

### Shape

| leg | n | closes | paid | flips | flip rate | c/contract | worst c |
|---|---|---|---|---|---|---|---|
| **DEAR** | 1,333 | 564 | 97.2c | 12 | **0.90%** | **+1.74** | −99.3 |
| **CHEAP** | 1,305 | 573 | 0.8c | 1,296 | **99.31%** | **−0.15** | −43.7 |
| BOTH | 2,638 | 712 | 49.5c | 1,308 | 49.6% | +0.81 | −99.3 |

### The money, at the frozen PREREG size

| | **DEAR** | **CHEAP** | BOTH |
|---|---|---|---|
| contracts/day | 3,955 | 4,423 | 8,378 |
| **$/contract/day** | **+0.0260** | **−0.0003** | +0.0121 |
| **$/day** | **+102.66** | **−1.54** | +101.12 |
| 95% CI over **closes** | [+82.12, +124.08] | [−27.30, +32.58] | [+64.67, +142.51] |
| 95% CI over **whole DAYS** | [+76.29, +162.74] | [−23.48, +17.95] | [+65.40, +161.17] |
| **peak concurrent capital** | **$267.21** | **$21.44** | $268.01 |
| median close capital | $46.42 | $0.26 | $30.85 |
| **% return on peak capital/day** | **38.4%** | −7.2% | 37.7% |
| worst close | −$28.64 | −$22.41 | −$51.05 |
| worst day | **+$14.28** | −$38.61 | +$10.47 |
| **max drawdown** | **−$28.64** | **−$150.99** | −$51.05 |
| $/day per $ of drawdown | **3.59** | −0.01 | 1.98 |
| days positive | **11 / 11** | 3 / 11 | 11 / 11 |
| top-10 closes, % of gross | **22.0%** | — | 36.6% |

```
ARITHMETIC CHECK, reconciled by hand three ways
  additivity   DEAR 102.663330165 + CHEAP -1.539369889
             - BOTH 101.123960275  =  0.000000000000
  units        DEAR  $983.8569 / 9.5833 d          = $102.6633/day
               DEAR  3955.1 ctr/day x $0.025957/ctr = $102.6633/day
               CHEAP 4423.2 ctr/day x -$0.000348    = $ -1.5394/day
  drawdown     BOTH maxDD -51.0496 == worst close -51.0496   (one close)
               DEAR maxDD -28.6367 == worst close -28.6367   (one close)
```

**DEAR is 101.5% of the $/day and 99.7% of the peak capital. CHEAP is −1.5% of
the money and 8.0% of the capital — and 5.3× the drawdown.**

On a $1,000 account, DEAR alone is **10.3%/day on the whole bankroll** and
**38.4%/day on the $267 actually at risk at the peak**.

### CHEAP is not "proven negative" — it is unmeasurable

| | |
|---|---|
| winners | **9 of 1,305 (0.69%)** |
| winners worth | +$279.94 |
| losers worth | −$294.69 |
| net | −$14.75 over 9.58 days |
| remove the single best winner | −$11.75/day |
| add one more winner of median size | −$0.66/day |
| closes needed to resolve a $10/day edge | 7,786 = **89 days** |
| closes needed to resolve a $25/day edge | 1,246 = 14 days |

**Both intervals span zero.** The correct statement is *no power*, not *no
effect*. What is **not** ambiguous is the drawdown: **$150.99 to hold a
position whose expectation cannot be measured in 89 days**, at 8% of the
capital. That is the argument for dropping it, and it is a risk argument, not
an edge-mining one.

### Corroboration on four independently-built trade sets

Rebuilding the whole walk-forward with `k` deliberately multiplied changes
*which* trades fire, so these are five different trade populations:

| k multiple | n DEAR | n CHEAP | DEAR $/day | CHEAP $/day | DEAR maxDD | CHEAP maxDD |
|---|---|---|---|---|---|---|
| ×1.00 (fitted) | 1,333 | 1,305 | **+102.66** | −1.54 | −28.64 | −150.99 |
| ×0.50 | 2,979 | 51 | +52.44 | +5.45 | −317.39 | −30.43 |
| ×0.80 | 2,048 | 604 | +101.55 | +19.74 | −98.63 | −69.89 |
| ×1.20 | 854 | 2,024 | +61.35 | −0.89 | −44.09 | −148.18 |
| ×2.00 | 143 | 3,657 | +20.94 | −46.74 | −16.30 | −508.26 |

**Stated precisely, because the loose version would overstate it:** CHEAP is
negative in 3 of 5 and positive in 2; where it is positive it has 51 and 604
trades. It never exceeds **+$19.74/day** in any construction, while DEAR earns
**$21–103/day** in all five. **DEAR carries the money in every construction;
CHEAP's sign is not stable in any of them.**

---

## 3. SIZING RULES

Two tables, because one of them lies alone. "At natural size" is the money
question but a rule that simply bets more wins it; "at equal mean size" holds
every rule to the same **total contracts** so only the *allocation* differs.

### FULL pin — at natural size

| rule | mean n | $/day | 95% CI DAYS | worst close | maxDD | peak $ | %/day |
|---|---|---|---|---|---|---|---|
| **PREREG min(100, 0.25·depth)** | 30.4 | **101.12** | [+65.4, +161.2] | **−51.05** | **−51.05** | 268 | **38%** |
| flat 50 min(50, depth) | 34.5 | 82.75 | [+57.3, +139.6] | −114.89 | −114.89 | 289 | 29% |
| flat 100 min(100, depth) | 56.9 | 157.74 | [+107.4, +259.0] | −151.14 | −151.14 | 529 | 30% |
| flat 25 min(25, depth) | 19.4 | 41.64 | [+29.1, +73.7] | −82.12 | −82.12 | 161 | 26% |

**The frozen depth-proportional rule beats every flat cap on drawdown, and
beats flat 50 and flat 25 on money as well.** Flat 25 earns *less* than PREREG
**and** carries 1.6× the drawdown. Caveat in §7D: part of that advantage rests
on a depth/edge association this sample cannot support.

### FULL pin — at equal mean size (30.44 contracts/trade)

| rule | n>0 | **% contracts to DEAR** | $/day | 95% CI DAYS | maxDD | %/day |
|---|---|---|---|---|---|---|
| PREREG (reference) | 2,638 | 47% | 101.12 | [+65.4, +161.2] | −51.05 | 38% |
| proportional to edge | 2,638 | 53% | 129.81 | [+88.1, +217.0] | −151.14 | 34% |
| Kelly on the k-refitted p | 2,638 | **33%** | **50.30** | [+19.9, +101.1] | −120.52 | 30% |
| Kelly, k too SMALL by 20% | 1,610 | **88%** | **176.62** | [+135.9, +271.5] | −151.14 | 35% |
| Kelly, k too BIG by 20% | 2,067 | **11%** | **7.38** | [−24.3, +44.3] | −219.38 | 7% |
| flat (equal weight) | 2,638 | 51% | 71.23 | [+49.1, +121.5] | −105.41 | 28% |

**The single most useful finding in this section: the entire spread of sizing
outcomes is the DEAR share of contracts.** 11% → $7.38/day, 33% → $50.30,
47% → $101.12, 53% → $129.81, 88% → $176.62. Monotone with one exception (flat,
51% → $71.23). **"Which sizing rule" is a proxy question; "how much of the
book is the lottery leg" is the real one.**

### DEAR leg only — at equal mean size (28.43)

| rule | $/day | 95% CI DAYS | maxDD | %/day |
|---|---|---|---|---|
| PREREG (reference) | **102.66** | [+76.3, +162.7] | **−28.64** | **38%** |
| proportional to edge | 123.36 | [+90.1, +208.1] | −114.55 | 35% |
| Kelly on the k-refitted p | 88.83 | [+67.4, +154.5] | −103.52 | 34% |
| Kelly, k too SMALL by 20% | 82.71 | [+65.9, +138.0] | −89.58 | 36% |
| Kelly, k too BIG by 20% | 117.50 | [+79.6, +198.4] | −114.55 | 28% |
| flat (equal weight) | 76.20 | [+62.9, +121.8] | −86.53 | 33% |

**With the CHEAP leg gone, Kelly's k-sensitivity collapses from a 24× spread
($7 → $177) to a 1.4× spread ($83 → $118).** Every alternative rule beats
PREREG on nothing and loses to it on drawdown by 3–4×.

### Fractional Kelly is not a real dial here

Unscaled full Kelly on a $1,000 bank wants a **median 970 contracts per trade**
against a **median resting depth of 62**. Depth is smaller than raw Kelly on
**94.0% of trades**. Full Kelly asks for a median **32% of the bank on one
trade** (72% on the DEAR leg alone). **Any Kelly fraction above ~3% of full is
clipped by depth**, so only the *shape* of the allocation survives, never the
level. Kelly is a re-weighting rule here, not a leverage rule.

### k wrong for real — a wrong k changes WHICH trades fire

| | trades (DEAR) | $/day | 95% CI DAYS | worst close | maxDD | peak $ |
|---|---|---|---|---|---|---|
| k as fitted | 2,638 (1,333) | **101.12** | [+65.4, +161.2] | −51.05 | −51.05 | 268 |
| **k ×0.80** | 2,652 (2,048) | **+121.29** | [+84.4, +201.1] | −90.07 | −99.77 | 357 |
| **k ×1.20** | 2,878 (854) | **+60.46** | [+31.4, +113.3] | −44.10 | −46.99 | 322 |
| k ×0.50 | 3,030 (2,979) | +57.90 | [+10.6, +172.2] | −122.24 | **−317.19** | 354 |
| k ×2.00 | 3,800 (143) | **−25.81** | [−67.3, +7.8] | −7.45 | **−368.50** | 166 |

**±20% is survivable in both directions: $60–121/day and drawdown inside
$100.** ±50–100% is not: **k ×0.50 blows the $250 clause on drawdown alone
(−$317) while still showing a positive $/day**, and k ×2.00 loses money at a
−$368 drawdown. The fitted `k` moved 1.215→1.555 over the window (±12% around
its midpoint), so ±20% is a realistic stress and ±50% is a model failure.

Removing the CHEAP leg does **not** protect against a too-small `k` (k ×0.50
DEAR-only still draws down −$317.39) but does protect against a too-large one
(k ×2.00 DEAR-only: **+$20.94/day, −$16.30 drawdown**).

---

## 4. THE DAILY MAX-LOSS STOP — it cannot help, and here is why

| limit $ | days hit | $/day | vs no stop | worst day | maxDD |
|---|---|---|---|---|---|
| 5 | 2 | 51.08 | **−50.04** | −36.05 | **−51.05** |
| 10 | 2 | 51.08 | −50.04 | −36.05 | −51.05 |
| 15–30 | 1 | 70.74 | **−30.39** | −36.05 | **−51.05** |
| 40–150 | 0 | 101.12 | 0.00 | +10.47 | −51.05 |
| none | 0 | 101.12 | — | +10.47 | −51.05 |

**DEAR only:** the stop never fires above $15, and at $5–10 it costs $27.95/day
and improves the drawdown by **$0.00**.

**The mechanism, and it is decisive: `pin`'s max drawdown IS its worst single
close.** −$51.05 maxDD and −$51.05 worst close are the same number, for both
cells. There has never been a losing streak. A stop that fires *after* the
close that caused the loss cannot prevent that loss, and can only forbid the
recovery — which is why the stop makes the **worst day worse** (+$10.47 →
−$36.05) while leaving maxDD untouched.

**Verdict: no daily max-loss stop helps over this sample at any level. Below
$40 it costs $30–50/day and buys nothing. Above $40 it is a no-op.** A stop
would only start to matter if `pin` ever produced a *streak*, and the honest
reason it has not is that 11 days is not enough tape to contain one.

*(This is one path. Picking the limit that scores best on it would be fitting a
stop to the drawdown that happened, which is why the whole sweep is printed.)*

---

## 5. COIN COUNT AS A DIAL

The task asked for 1/3/6/12. **The tape carries 9 series, so 12 is not
measurable here.** Each row averages over up to 60 random subsets of that size,
which is what removes the selection from "which coins".

### At natural size (capital grows with N)

| coins | coins/close | $/day | [min, max] over subsets | peak cap $ | $/day per $cap | worst close | maxDD | $/day per $DD | top-10 % gross |
|---|---|---|---|---|---|---|---|---|---|
| **FULL pin** ||||||||||
| 1 | 1.00 | 11.24 | [−2.0, +32.0] | 98.8 | 0.114 | −10.62 | −15.14 | 0.74 | 54.9 |
| 3 | 1.61 | 33.45 | [+7.8, +67.1] | 174.3 | 0.192 | −21.65 | −23.55 | 1.42 | 42.8 |
| 6 | 2.65 | 69.37 | [+34.0, +93.3] | 236.0 | 0.294 | −33.87 | −34.01 | 2.04 | 39.3 |
| 9 | 3.71 | 101.12 | — | 268.0 | 0.377 | −51.05 | −51.05 | 1.98 | 36.6 |
| **DEAR only** ||||||||||
| 1 | 1.00 | 11.41 | [+3.4, +41.5] | 98.8 | 0.115 | −6.77 | −6.77 | 1.69 | 45.8 |
| 3 | 1.31 | 34.35 | [+11.8, +68.3] | 174.3 | 0.197 | −13.73 | −13.73 | 2.50 | 29.8 |
| 6 | 1.86 | 68.67 | [+36.1, +90.9] | 233.5 | 0.294 | −20.60 | −20.60 | 3.33 | 25.4 |
| 9 | 2.36 | 102.66 | — | 267.2 | 0.384 | −28.64 | −28.64 | **3.59** | **22.0** |

### With PEAK CAPITAL HELD FIXED at the 1-coin level — the extra coins cannot buy leverage

| coins | size × | $/day | peak cap $ | worst close | maxDD | $/day per $DD |
|---|---|---|---|---|---|---|
| **FULL** 1 | 1.000 | 11.24 | 98.8 | −10.62 | −15.14 | 0.74 |
| 3 | 0.577 | 19.41 | 98.8 | −11.98 | −13.32 | 1.46 |
| 6 | 0.420 | 28.57 | 98.8 | −14.60 | −14.65 | 1.95 |
| 9 | 0.369 | **37.28** | 98.8 | −18.82 | −18.82 | **1.98** |
| **DEAR** 1 | 1.000 | 11.41 | 98.8 | −6.77 | −6.77 | 1.69 |
| 3 | 0.576 | 19.95 | 98.8 | −8.16 | −8.16 | 2.45 |
| 6 | 0.422 | 29.25 | 98.8 | −9.02 | −9.02 | 3.24 |
| 9 | 0.370 | **37.96** | 98.8 | −10.59 | −10.59 | **3.59** |

### Does the leverage-not-breadth finding continue? **No — it reverses.**

The HANDOFF note records that going 1.0 → 1.6 coins/close pushed top-10
concentration from 45% to 56%. **On this tape the opposite happens, in every
column:**

* **concentration FALLS** with more coins: 54.9% → 36.6% (FULL), 45.8% → 22.0%
  (DEAR);
* **risk-adjusted return RISES at constant capital**: 0.74 → 1.98 (FULL),
  1.69 → 3.59 (DEAR);
* at fixed $98.80 of peak capital, 9 coins earn **3.3×** what 1 coin earns
  while the drawdown grows only **1.24×** (FULL) / **1.56×** (DEAR).

**That is diversification, not leverage.** Two caveats: the earlier note was
measured on a smaller tape at `tau<=20`, so this is not a like-for-like
refutation; and the *width* of the subset range at N=1 ([−2.0, +32.0]) shows
how much a single-coin result depends on which coin, which is exactly the
uncertainty that averaging over subsets is meant to price.

---

## 6. THE SIZE THAT FITS $250

The clause is *"cumulative drawdown from peak exceeds $250"*, so the quantity
to bound is the **max drawdown of a path**, not a week's total P&L.

### First: the day-block drawdown bootstrap is DEGENERATE here, and my first pass reported its output as if it meant something

All 11 days are **net positive**. Concatenating any number of net-positive days
produces a path that drifts up, so its drawdown can never exceed the worst
**within-day** dip — which is why every quantile printed the same number and
`P(dd > $250)` printed `0.00%` at every size, including $404/day. **That is not
evidence of safety; it is the bootstrap refusing to answer.** Corrected here
with a ladder of three, weakest first:

| method | what it can produce | what it forbids |
|---|---|---|
| day-block | nothing worse than one bad day | **degenerate on this tape** |
| iid over closes | runs of bad closes | clustering |
| **flip @ CP-95% upper** | runs **and** a flip rate at the upper bound 9.6 days can bound it to | a regime this tape never held |

The tail event is a **DEAR flip** (a near-certain contract settling the other
way). Measured: **9 flip closes of 564 fired DEAR closes = 1.60%**, Clopper-
Pearson 95% upper bound **2.77%**. Flips cluster — the 12 flips fell on 9
closes and 5 days, with **4 coins flipping in one close** and **7 flips in one
day** — so the stress draws whole flip-closes, preserving that.

### The ladder, on 7-day paths (520 / 412 closes), 20,000 reps

The size rule `n = min(m·100, m·0.25·depth, depth)` is **exactly linear in m
for m ≤ 4** (verified elementwise), so P&L, capital and every drawdown scale by
`m` exactly. At `m = 4` the rule asks for the whole resting level, which is a
hard ceiling whatever the risk budget says.

**FULL pin (both legs)**

| m | $/day | peak cap $ | obs maxDD | 7d dd p50 | 7d dd p95 | **7d dd p99** | 7d dd worst of 20,000 | fits $1,000? |
|---|---|---|---|---|---|---|---|---|
| 0.50 | 50.56 | 134 | −25.5 | −26.3 | −48.3 | −60.3 | −114.4 | yes |
| **1.00** | **101.12** | **268** | **−51.0** | −52.5 | −96.6 | **−120.7** | **−228.7** | yes |
| 1.50 | 151.69 | 402 | −76.6 | −78.8 | −145.0 | −181.0 | −343.1 | yes |
| 2.00 | 202.25 | 536 | −102.1 | −105.1 | −193.3 | −241.3 | −457.5 | yes |
| 3.00 | 303.37 | 804 | −153.1 | −157.6 | −289.9 | −362.0 | −686.2 | yes |
| 4.00 | 404.50 | 1,072 | −204.2 | −210.1 | −386.6 | −482.7 | −914.9 | **NO** |

**DEAR leg only**

| m | $/day | peak cap $ | obs maxDD | 7d dd p50 | 7d dd p95 | **7d dd p99** | 7d dd worst of 20,000 | fits $1,000? |
|---|---|---|---|---|---|---|---|---|
| 0.50 | 51.33 | 134 | −14.3 | −14.3 | −24.4 | −30.6 | −54.9 | yes |
| **1.00** | **102.66** | **267** | **−28.6** | −28.6 | −48.8 | **−61.2** | **−109.9** | yes |
| 1.50 | 153.99 | 401 | −43.0 | −43.0 | −73.2 | −91.8 | −164.8 | yes |
| 2.00 | 205.33 | 534 | −57.3 | −57.3 | −97.6 | −122.4 | −219.8 | yes |
| 3.00 | 307.99 | 802 | −85.9 | −85.9 | −146.4 | −183.6 | −329.7 | yes |
| 4.00 | 410.65 | 1,069 | −114.5 | −114.5 | −195.1 | −244.8 | −439.6 | **NO** |

### What binds, in order

| constraint | FULL pin | DEAR only |
|---|---|---|
| $250 at the **99th pct** of a 7-day path | m = **2.07** → $209/day | m = **4.08** → $419/day |
| $250 at the **worst of 20,000** paths | m = **1.09** → $111/day | m = **2.27** → $234/day |
| $1,000 of peak concurrent capital | m = 3.73 → $377/day | m = 3.74 → $384/day |
| half the resting level left intact | m = 2.00 → $202/day | m = 2.00 → $205/day |
| the whole level (hard ceiling) | m = 4.00 | m = 4.00 |

**THE ANSWER TO THE QUESTION AS ASKED: the $250 clause costs $0/day at the
frozen size, because it does not bind there.** At `m = 1` the 99th-percentile
7-day drawdown is **$120.7** (FULL) and **$61.2** (DEAR) — less than half the
budget.

**But read the "worst of 20,000" row before relaxing.** At the frozen size the
full strategy's worst simulated 7-day path is **−$228.7**, which is **91% of
the clause**. One path in 20,000 already nearly breaches at `m = 1`, and a
1-in-20,000 margin on 11 days of tape is not comfort. **The DEAR leg alone puts
that number at −$109.9 — 44% of the clause — for +$1.54/day.** That is the
sharpest risk argument in this report.

**Recommended size: `m = 1`, DEAR leg only.** $102.66/day, peak concurrent
capital $267, 38.4%/day on capital, worst simulated 7-day drawdown $110.
Going to `m = 2` doubles the money to $205/day and is inside every constraint,
but it doubles the fraction of the resting level consumed from 25% to 50% —
i.e. it doubles how aggressive the fill assumption is, which is the one thing
this backtest cannot test at all (PREREG §6.1). **Do not raise `m` before the
forward test has measured the fill.**

### The 5-day week in P&L, block-bootstrapped over whole days

| cell | m | 1% worst | 5% worst | median | 95% | weeks losing |
|---|---|---|---|---|---|---|
| FULL pin | 1.0 | +135.85 | +195.15 | +428.18 | +737.37 | **0.0%** |
| DEAR only | 1.0 | +205.69 | +259.01 | +427.47 | +703.51 | **0.0%** |

PREREG §5 quotes "+$27" for the 1%-worst 5-day week; on this larger tape it is
**+$136**. **Both carry the same defect and it is fatal to the number: 11 days,
none of them negative.** A bootstrap over 11 winning days cannot produce a
losing week. **Do not use this table as a downside estimate.** It is here only
because §5 of the PREREG quotes its predecessor.

### A measured stress instead of a bootstrap

At the Clopper-Pearson 95% upper bound on the DEAR flip rate:

| flip rate | measured on | DEAR $/day |
|---|---|---|
| 0.90% (observed, trades) | — | **102.66** |
| 1.45% (CP upper, **trade** level) | 12/1,333 | **81.33** |
| 2.77% (CP upper, **close** level, clustering preserved) | 9/564 | **≈96** |
| 2.68% (breakeven, trade level) | — | **33.61** |

**The trade-level bound is the harsher of the two** (it ignores that a flip
close still contains winners), so the honest range at the 95% upper bound is
**$81–96/day**, and the leg does not reach breakeven until the flip rate
**triples**, to 2.68%.

**Do not compare the two bounds to each other — they are different units.**
1.45% is a *per-trade* rate and 2.77% a *per-close* rate; only the trade-level
pair is like-for-like against the trade-level breakeven. On that comparison:
**CP 95% upper bound 1.45% vs breakeven 2.68% = 1.84× headroom at the bound.**
That is the tail that matters, and it is thinner than the drawdown tables make
it look.

---

## 7. WHAT WOULD MAKE THIS AN ARTEFACT — and what the check said

The leg result is convenient, so each way it could be false was checked.

**A. The 50c cut is arbitrary.** Swept it.

| cut | DEAR $/day | CHEAP $/day | DEAR maxDD | CHEAP maxDD |
|---|---|---|---|---|
| 2c | 120.83 | −19.70 | −51.05 | −207.64 |
| 10c | 101.03 | +0.09 | −51.05 | −148.23 |
| **50c** | **102.66** | **−1.54** | **−28.64** | **−150.99** |
| 90c | 64.65 | +36.47 | −28.64 | −90.69 |

Flat from 5c to 75c because almost nothing lives there. **The finding does not
depend on the cut.** (At 90–95c the "DEAR" set starts excluding real DEAR
trades, which is why it decays.)

**B. CHEAP's minus sign is one bad day.** No — 8 of 11 days negative. But it
**is** decided by ~2 lottery tickets (§2), so the verdict is *no power*, not
*negative*. Stated as such throughout.

**C. DEAR's $/day is a few enormous trades.** Top-10 closes are **23.9%** of
DEAR's total (46.8% for BOTH); **558 of 564 fired closes are positive (98.9%)**.
Jackknife over days, dropping each in turn: **+$86 to +$109/day**, and dropping
the single best day (2026-09-05, +$254.68) still leaves **+$85.88/day**.
**DEAR is broad; the concentration in `pin` is the CHEAP leg.**

**D. The size-weighted per-contract edge (2.60c) exceeds the unweighted (1.74c),
which flatters the depth-proportional size rule.** This is the weakest point in
the report and it is not resolved.

| depth bucket | n | contracts | c/contract | share of $ |
|---|---|---|---|---|
| 0–20 | 397 | 638 | 1.09 | 0.7% |
| 20–60 | 259 | 2,456 | 1.36 | 3.4% |
| 60–150 | 297 | 7,262 | 1.46 | 10.8% |
| 150–400 | 242 | 13,746 | **2.84** | 39.6% |
| 400+ | 138 | 13,800 | **3.24** | 45.5% |

The bucket means rise monotonically, but **Spearman rank corr(depth,
per-contract P&L) = +0.034, permutation two-sided p = 0.199 (2,000 shuffles)**.
**The rank test does not support a depth/edge relationship.** So: 85% of the
DEAR money comes from the 380 deep-book trades, mostly because depth-
proportional sizing *puts more contracts there by construction*, and the
apparent per-contract rise is not statistically supported. PREREG §2's claim of
"no monotone decay with depth" survives; a monotone *increase* does not.
**Consequence: PREREG's advantage over flat sizing in §3 may be partly this
unsupported association, and should be re-checked on forward tape.**

**E. The DEAR tail is bigger than 12 flips suggests.** Clopper-Pearson 95%
upper bound on the flip rate is **1.45%** against a **2.68%** breakeven —
**1.84× headroom at the bound**. Even the pessimistic end of what 1,333 trades
can bound leaves the leg profitable.

**F. `walk_markets_k` (which records `k` per trade) forked `pin`'s rule.** It
did not: asserted identical on all 533 trades of the `tau<=20` cell before any
scoring ran.

---

## 8. WHAT IS IN-SAMPLE, AND THE PRICE OF SWEEPING

| | cells |
|---|---|
| part 1 legs × cut sweep | 11 |
| part 2 sizing rules | 20 |
| part 2 k mis-specification | 10 |
| part 3 stop-loss limits | 22 |
| part 4 coin count | 16 |
| part 5 size multiples | 16 |
| **TOTAL** | **95** |

Bonferroni: a single cell needs **p < 0.00053** to carry 5% family-wise weight.

**Nothing here is out-of-sample in the selection sense.** The `k` is walk-
forward; the *choices* are not. Specifically:

* **The leg split is a post-hoc cut on this tape.** The label is computable at
  entry (it is just the price paid), so a live rule "take only trades costing
  ≥50c" needs no look-ahead — but the *decision* to use it was made after seeing
  9.58 days of results. It is not in the frozen PREREG rule, and adopting it
  mid-window would restart the forward test at zero (PREREG §4).
* **The two headline claims are read off the whole sweep, not its maximum.**
  "DEAR carries the money" holds in all 8 cut cells and all 5 `k`-perturbed
  trade sets. "The stop does not help" holds at all 11 limits in both cells.
  Neither is the argmax of anything.
* **The 5-day-week table and every `P(dd>$250)` are lower bounds**, because 11
  days containing no losing day cannot produce a losing week.

---

## 9. WHAT I COULD NOT DO

1. **12 coins.** The tape carries 9 series. The dial stops at 9.
2. **Any out-of-sample test.** There is one window and 95 cells were scored on
   it. The forward test in `PREREG_pin.md` is still unsigned and unstarted.
3. **The race.** Every number assumes we get the quote. PREREG §6.1 names this
   as the primary open risk and nothing here bounds it. `m = 2` doubles the
   share of the level consumed from 25% to 50% and is therefore **not** a free
   doubling, whatever the risk tables say.
4. **A real bad week.** No bootstrap on 11 winning days can make one. The
   flip-rate stress at the CP upper bound is the strongest thing available and
   it is still bounded by the closes this tape contains.
5. **I did not modify `PREREG_pin.md`.** The "364 closes" discrepancy in §3 and
   the "+$27 worst week" in §5 are both flagged above; changing a frozen
   pre-registration is the operator's call, not mine.
6. **No orders.** Read-only throughout; nothing was placed, and this is a
   backtest of recorded tape, not a paper trade.

---

## 10. NEXT STEP

**Put one number in front of the operator: pre-register the DEAR-only variant
alongside the frozen rule, and score both in the same forward window.**

It costs nothing to run both — the leg label is a price comparison at entry, so
one live process can record both P&L streams from identical fills. The forward
test then answers the only question this tape cannot: whether dropping a leg
that earns −$1.54/day and costs $151 of drawdown is a real risk improvement or
selection on 9.58 days of my own error.

Concretely, for the operator's signature:

* size **`m = 1`** — `min(100, 0.25 × resting depth)`, unchanged;
* **peak concurrent capital needed: $267** (fund $400 for headroom, not $1,000);
* expected **$102/day** at 38.4%/day on capital, **$0.026 per contract per day**;
* **no daily stop** — it demonstrably cannot help a one-close drawdown;
* keep all 9 coins — at fixed capital they are diversification, not leverage;
* re-examine at **$250** cumulative drawdown — which at this size the DEAR leg
  **never reached in 20,000 simulated 7-day paths** (worst: $109.9). It would
  take `m = 2.27` before the worst of 20,000 paths touches the clause.

---

### Files

| | |
|---|---|
| report | `C:\kals-repo\results\overnight\RISK_REWARD.md` |
| machinery | `C:\Users\Joe\AppData\Local\Temp\kals-work\job3rr\rr3.py` |
| **self-test (60 checks)** | `...\job3rr\selftest.py` |
| **mutation test (23/23)** | `...\job3rr\mutate.py` |
| builder | `...\job3rr\build.py`, `...\job3rr\build_kmul.py` |
| part 1 legs | `...\job3rr\part1_legs.py` → `part1.log` |
| part 1 artefact checks | `...\job3rr\part1b_verify.py` → `part1b.log` |
| part 2 sizing | `...\job3rr\part2_sizing.py` → `part2.log` |
| parts 3/4/5 | `...\job3rr\part345.py` → `part345.log` |
| parts 4b/5b corrections | `...\job3rr\part45b.py` → `part45b.log` |
| final numbers | `...\job3rr\final_numbers.py` → `final.log` |
| corroboration | `...\job3rr\corrob.log` |

**Collectors: `kalshi_collector.py` (PID 3381772) and `crypto_feeds.py`
(PID 3385232) verified alive at the start, middle and end of this job. No
`load_quotes` call was made. Free RAM never fell below 3.9 GB; free disk 51.9 GB.**
