# ATTACK — LENS 2: THE STATISTICS AND THE TAIL

**Adversary 2 of 3. No stake. Default REFUTED.** Written 2026-09-06, from
`C:\Users\Joe\AppData\Local\Temp\kals-work\L2`. Every number below was computed
in this session from the primary artefacts of the three Reality jobs, from the
raw tape at `C:\kals\kalshi_data` (read-only), or from live authenticated
read-only GETs. No orders were placed and no real money was used.

---

## VERDICT

**The claim SURVIVES my lens, and I could not kill it. What I found instead is
that the three Reality jobs disagree with each other by a factor of 2.9 on the
single most important number in the project — the rebate — and that two of the
three are wrong.**

`IMPACT.md` says the rebate is **$838/day**. `INVENTORY_PNL.md` says
**$271/day** and calls the operator's 111%/day "CONFIRMED". `CAPITAL_RUIN.md`
says **$284/day**. All three describe the identical quantity: 50 lots a side,
3 ticks back, five coins, average-of-sides reading. They cannot all be right.

I adjudicated it four independent ways and **IMPACT.md is right**. The other
two rest on a book that is emptied 45 seconds into every 15-minute window by a
bug in the shared cached simulator, and the "CONFIRMED" in `INVENTORY_PNL.md`
is a coincidence: two errors landed it near the number it was checking.

My own corrected figure, after fixing three things `IMPACT.md` got wrong in its
own favour, is **$779/day of rebate (day-clustered 95% CI [$743, $816]) on a
resting-capital peak of $458**. That is still **2.4x the claim under attack**,
so the honest outcome of my attack is that the claim is *understated*, not
inflated — the least comfortable place for an adversary to land. §4 says
exactly what would still have to be true for it to be wrong.

**The statistics are not the weak point.** I looked hard for the failures the
brief pointed me at and mostly did not find them: the five coins really are
independent for the rebate (intra-window ICC **-0.0014**, design effect
**1.00**), the qualifying haircut is applied exactly **once** in all three
reports, and the sampling error on the headline is genuinely small
(**+/-$20/day** iid, **+/-$20/day** window-clustered, **+/-$43/day**
day-clustered). The weak point is **specification**, and it is a 3x fork that
nobody posed.

---

## 1. THE 2.9x CONTRADICTION, AND HOW IT WAS SETTLED

### 1.1 The two books agree on our SHARE and disagree only on QUALIFICATION

Both jobs compute the same thing: `$20 x (sum of our per-second share over
qualifying seconds) / (seconds in the period)`. Decomposed from their own
artefacts:

| | IMPACT.md (`impact/cap.pkl`) | cached sim (`jobb/recs.pkl`) |
|---|---|---|
| our share of a side, qualifying seconds | **11.41%** | **11.49%** |
| qualifying fraction | **74.29%** | **26.02%** |
| $/leg-window | $1.7457 | $0.5655 |
| $/day | **$837.95** | **$271.43** |
| legs with **zero** qualifying snapshots in 900 s | **0 of 1,078** | **189 of 1,235 (15.3%)** |

The share estimates agree to **0.7% relative**. The entire 2.9x is the
qualifying fraction. That is the fingerprint of *missing deep size*: raw depth
decides qualification, distance-weighted score decides share, and on this book
they are almost unrelated. Measured on the correct book over 31,982
side-samples: **the median side has 83.1% of its raw depth sitting 8c or more
below the reference price, and its LIP score is only 9.8% of its raw depth.**
The size that qualifies a snapshot is almost entirely size that scores nothing.

### 1.2 The bug, named and located

`C:\Users\Joe\AppData\Local\Temp\kals-work\rebate\extract.py` writes every
`orderbook_snapshot` message as a bare marker and **discards its level
arrays**:

```python
rows.append((int(ts), 2, int(m.get("seq") or 0), d["market_ticker"],
             "", 0, 0.0, ""))          # <- no levels captured
```

`rebate/sim.py` then reads that marker and **empties the book**:

```python
if rank == 2:
    m.book = Book()          # <- wipes every resting level
```

That code is upstream of `INVENTORY_PNL.md`, `CAPITAL_RUIN.md` and
`REBATE_RISK.md`. All three inherit it.

### 1.3 Four independent lines of evidence, all pointing the same way

**(a) The raw tape. Coin Race snapshots DO carry levels, and the brief is
wrong.** Scanning every `orderbook_snapshot` file for 2026-09-04 -> 06:

```
levelled=False  in-window=False   n=2695
levelled=True   in-window=True    n=1360
```

Perfect correspondence, **zero exceptions in 4,055 messages**. Every market
gets exactly one levelled snapshot and it arrives **inside** its window (p5
16.3 s, median **45.1 s**, p95 70.6 s). A real one:

```json
"yes_dollars_fp": [["0.0100","7002.00"],["0.0200","301.00"],["0.0300","120.00"], ...]
"no_dollars_fp" : [["0.0100","2152.00"],["0.0200","1.00"],["0.3800","120.00"], ...]
```

Median depth at that snapshot: **2,316 yes / 3,124 no**, and **94.6% of them
already qualify on both sides**. The cached sim throws all of it away, 45
seconds into the window, and those levels emit no further deltas because nobody
cancels them. The brief's rule *"snapshots for this series carry NO level
arrays"* is true only of the post-close snapshots, which are 66.5% of them by
count and 0% of the ones that matter.

**(b) Live authenticated orderbooks.** `GET /markets/{t}/orderbook` on the five
open Coin Race legs, 2026-09-06 19:49Z: raw depth **4,123-5,813 yes** and
**5,845-6,098 no**, and **5 of 5 qualify**. A 43-sample poll across the 20:00Z
rollover:

```
19:49:53 .. 19:54:53   5/5 qualify every sample, depth ~4,000 / ~6,000
19:55:13 .. 19:59:53   the book unwinds; by 19:59:53, 0/5 qualify
20:00:13 (new window)  5/5 qualify within 13 seconds of the open
```

Live qualification, raw-depth rule: **109 of 155** side-samples in the second
half of the closing window (**70.3%**) and **70 of 70** in the first four
minutes of the new one (**100%**); **179 of 225 overall (79.6%)**. It is not
26%.

**(c) Kalshi's own payment record.** A programme can only be paid if at least
one snapshot qualified. From the cached 177,036-programme pull
(`atkL1/progs.jsonl`), Coin Race programmes by the UTC day their window ended:

```
2026-08-25  99.0%   08-26 100%   08-27 97.5%   08-28 97.9%   08-29 95.2%
2026-08-30 100%     08-31 100%   09-01 100%    09-02 100%    09-03 100%
2026-09-04 100%     ----------   09-05 43.8%   09-06  7.9%   <- processing lag
```

On the eleven fully-settled days: **5,151 of 5,200 paid = 99.06%**, so **0.94%
never paid**. Now the prediction of each candidate reconstruction:

| reconstruction / rule | legs that never qualify | consistent with 0.94%? |
|---|---|---|
| **IMPACT.md book, raw-depth rule** | **0.8%** (11 / 1,345) | **YES — to 0.12pp** |
| cached sim book | 15.3% | no |
| raw depth excluding the 1c wall | 35.2% | no |
| depth within 10c of the touch | 61.7% | no |
| distance-weighted score >= 1000 | 89.9% | no |

The reading that matches Kalshi's own books is the one `IMPACT.md` used, and it
matches to a tenth of a percentage point. Everything else is refuted.

**(d) Internal consistency.** My minute-by-minute reconstruction (§2) sums to
$830.01/day, the same figure my aggregate pass produced by a different route.

### 1.4 What this does NOT contaminate

The same bug that destroyed qualification barely touched the share (11.49% vs
11.41%), because what it lost was deep static size. So **the fill and inventory
results of jobs B and C are probably largely intact** — I am not claiming
otherwise. What it lost is queue we would genuinely have been behind (on the
correct book the median side has **120 lots resting at better prices than our
quote**, and our own price is empty 52.6% of the time), so their fill counts
are an **upper** bound and their inventory risk is priced **too high**, not too
low. That is the direction that favours the strategy, and it is a reason to
re-run B and C on the corrected book rather than to discard them.

---

## 2. THE CORRECTED NUMBER, WITH ITS DISTRIBUTION

Three things `IMPACT.md` got wrong in its own favour. I re-ran its own code
path with each fixed (`L2/allcap.py`, `L2/variants.py`, 1,345 markets, 17-20 s
per pass).

| step | $/day | change |
|---|---|---|
| `IMPACT.md` as published | **837.95** | — |
| use the programme's own **900-second** denominator, not the 892 s of tape | 830.01 | -0.95% |
| drop the **>=99% reconstruction gate** (it keeps the busy markets) | **779.46** | **-6.1%** |
| the programme ran 473.8 leg-windows/day on average, not 480 | **769.5** | -1.3% |

**The survivorship step is the real one.** The 267 markets the gate dropped pay
**$1.2501** per leg-window against the survivors' **$1.7457**, and the 108
markets too quiet to score at all pay **$0.7497** — 43% of the mean. The gate
is a data-quality filter that correlates with the thing being measured.

### The distribution, all 1,345 legs, raw-depth rule, 900 s denominator

| | per leg-window |
|---|---|
| p1 | $0.1472 |
| p5 | $0.5369 |
| p25 | $1.0482 |
| **median** | **$1.5549** |
| p75 | $2.2194 |
| p95 | $2.8153 |
| p99 | $3.0438 |
| **mean** | **$1.6239** |
| sd | $0.7307 |
| paying under 1 cent | **0.8%** (11 legs) |

**By day**: 26SEP03 $749.60 | 26SEP04 $804.12 | 26SEP05 $770.18 | 26SEP06
$763.08. **Day-clustered 95% CI: [$743, $816]/day** (t = 3.182, 4 days).
**Whole-day bootstrap, 20,000 reps: [$760, $797].**

### Peak concurrent capital — IMPACT.md's is the wrong measurement

`impact/capital.py` takes the max **within each event's own window**, so it
cannot see the second at which one window's orders and the next window's
overlap. Re-measured on the **wall clock**, summed over every live Coin Race
market, 237,777 seconds:

| | resting only, wall clock | IMPACT.md, per event | CAPITAL_RUIN.md, +fills |
|---|---|---|---|
| median | $176.50 | $184.50 | $233.91 |
| p95 | $227.00 | $230.50 | $299.60 |
| p99 | $235.50 | — | — |
| **max** | **$458.00** | **$232.50** | **$392.29** |

### Money, stated the way the operator asked

| | value |
|---|---|
| **$/day (rebate only)** | **$779** [$743, $816] day-clustered |
| **$/contract/day** | **$1.559** (500 resting contracts) |
| **peak concurrent capital** | p99 **$235.50** resting; **$458.00** worst second; **$392.29** including fills (CAPITAL_RUIN.md) |
| **% return on capital/day** | **331%** on the p99 routine peak; **199%** on the with-fills max; **170%** on the worst second |
| worst leg-window in 1,345 | **$0.00** (11 legs paid under 1c) |
| worst day in the sample | $749.60/day equivalent |
| ruin probability from the rebate leg | **zero — a rebate cannot be negative.** All ruin lives in inventory, which is jobs B and C |

Under the *"plus"* rather than *"average"* reading of the two sides, every
figure above **doubles**. Still unresolved after three jobs.

### The rebate is earned early and the risk is carried late

Nobody had looked inside the window. Minute by minute, 1,078 legs
(`L2/profile.py`):

```
min   1   2   3   4   5   6   7   8   9  10  11  12  13  14  15
qual 96% 99% 99% 98% 97% 97% 96% 93% 87% 81% 59% 51% 32% 17%  5%
$    83  81  78  76  73  71  68  64  58  53  43  38  25  14   4
```

**90.2% of the money is earned in the first 11 minutes; the last four minutes
pay 9.8%.** The book unwinds into the close — confirmed independently on the
live poll. The operator is therefore holding inventory through the four minutes
of highest settlement risk while being paid almost nothing for it. **Cancelling
at T-4 min costs ~10% of the rebate and removes the worst-priced exposure in
the window.** That is a free, testable improvement and it is in none of the
three reports.

---

## 3. THE FOUR THINGS LENS 2 WAS SENT TO CHECK

### 3.1 "Is any bootstrap resampling WINDOWS iid rather than whole DAYS?"

**No, and it would not have mattered.** All three handled the unit honestly:

* `jobb/daily.py` runs a circular moving-block bootstrap at block lengths 1, 4,
  16, 32 and 96 windows, prints **all** of them, shows the autocorrelation
  (+0.089 at lag 1, ~0 beyond), and labels the iid row "WRONG".
* `jobC2/part3.py` runs a whole-day resample **and** block bootstraps **and** a
  winner-redraw, and self-tests that its block code can tell a correlated world
  from an uncorrelated one (4.97x wider on 40-step shocks, 1.01x on none). That
  is a real planted-answer test of the estimator.
* `IMPACT.md` reports **no interval at all** — which is the actual omission.

I supplied the missing intervals. On its 1,078 leg-windows the mean payout has
SE **$0.02137** iid, **$0.02135** clustered by 15-minute window (G=265), and
**$0.02813** clustered by day (G=4). **Design effect: 1.00 for windows, 1.73
for days.** Whole-day bootstrap of the published headline: **[$819, $862]**.

So the honest answer to the question as posed is: *the sampling error is small
and clustering barely moves it.* The uncertainty that matters is not sampling;
it is (i) which reading of the rule is right and (ii) three and a half days of
tape.

**The one place small-n does bite** is `INVENTORY_PNL.md`'s headline interval
**[+$71, +$882]/day**, a t-interval on **n = 3 days, 2 dof**. I reproduce the
arithmetic exactly (mean 476.26, sd 163.3, se 94.3, t=4.303, +/-405.6).
`BIASES.md` §17 sets the floor at **thirty** clusters and this is three. The
report flags it in prose and then quotes it in the headline table anyway. It
should be quoted as "we cannot bound this", not as a number.

### 3.2 "Is the qualifying-snapshot haircut applied once, twice, or not at all?"

**Exactly once, everywhere. Nobody double-counted it and nobody dropped it.**
The three differ only in the denominator:

| file | formula | denominator | error |
|---|---|---|---|
| `impact/capital.py` | `POOL x mean(share over qualifying) x qq/qn` | observed seconds, **mean 892.1** | **+0.89%** |
| `jobb/core.py` | `score x REWARD / 900` | **900** — correct | none |
| `jobC2/build.py` | `REWARD x score / snap_tot` | observed, **~851** | **+5.8%** |

`INVENTORY_PNL.md` §Artefact-5 identifies this exact error, fixes it, and docks
itself 4.5%. `CAPITAL_RUIN.md`, written after it, uses `snap_tot` and does not.
**That is why the two reports quote $271/day and $284/day for the same thing,
and neither says so.** `CAPITAL_RUIN.md`'s "reconciliation against
`REBATE_RISK.md`, all within 1%" is a reconciliation of two uncorrected
numbers.

**The brief's 28.9% appears in none of the three.** The measured values are
**74.3%** (correct book) and **26.0%** (wiped book). 28.9% is close to the
broken one — so the original claim under attack was itself built on the broken
book, which is why fixing it makes the number bigger rather than smaller.

### 3.3 "Are the five coins treated as independent anywhere they are not?"

**For the rebate: they are independent, I checked, and treating them so is
correct.** Intra-class correlation of the five legs' payouts inside one
15-minute window: **-0.0014** over 260 windows, mean 4.07 legs per window, Kish
design effect **1.00**. Within a day: ICC 0.00090. The mutual-exclusion
constraint (the five yes-prices sum to 100c) binds the *prices*, not the
*rebate*, and the rebate is paid for resting size on both books of every leg.

**For the inventory: the coins are NOT exchangeable, and every counterfactual
in `INVENTORY_PNL.md` §3 that reshuffles them is biased.** `jobb/corr.py`
reports, without comment, that the realised sd of residual P&L is **15.51**
against **18.54** when the winning coin is redrawn. I ran that as a proper
permutation test, 4,000 redraws, positions and prices held fixed
(`L2/winner.py`; the identity `r_k + deterministic = realised residual` checks
to 1e-14 on all 247 windows):

| model | realised sd | redrawn sd | p(sd <= realised) | realised mean | redrawn mean | p(mean >= realised) |
|---|---|---|---|---|---|---|
| base d=3 | **15.51** | 18.54 +/- 0.91 | **0.0002** | +1.601 | +1.997 +/- 0.934 | 0.668 |
| exact d=3 | 7.38 | 8.28 +/- 0.59 | 0.056 | +0.076 | -0.684 +/- 0.426 | 0.036 |
| sweep d=3 | **25.24** | 34.06 +/- 1.51 | **0.0002** | -0.982 | +4.635 +/- 1.638 | **0.9995** |
| **base d=0** | **22.42** | 30.01 +/- 1.98 | **0.0002** | **-2.475** | **+9.669 +/- 1.552** | **1.0000** |

Read the last row. At the touch, the realised P&L is **7.8 standard errors
BELOW** what a random winner would have produced. That is adverse selection,
measured: the coin that wins is systematically the one our fills are wrong on.
**Redrawing the winner, or redistributing the position "balanced across five
coins", deletes it and inflates the mean by +$0.40 to +$12.14 per window — up
to $1,165/day of pure artefact at d=0.** `INVENTORY_PNL.md` warns about exactly
this for its balanced-residual variant, in prose, and is right to; I have now
put a number and a p-value on it, and it is larger than the warning implies.
**The one-next-step in that report — simulate the balanced residual as a
quoting rule — must be run against this null, or it will "find" the artefact.**

The extreme tail, in contrast, is *not* lucky: p(worst <= realised) = 0.49 and
the realised p1 (-$46.71) equals the redrawn p1 (-$46.70). So the reported
worst window of -$70.13 is a fair draw. It is the bulk dispersion that is
flattered, not the tail.

### 3.4 "Recompute the headline by hand"

Everything reproduces except one line.

| claim | source | my recomputation | verdict |
|---|---|---|---|
| $837.95/day | IMPACT §9 | $1.745739 x 480 = **$837.95** | exact |
| $/contract/day $1.676 | IMPACT §9 | 837.95/500 = **1.6759** | exact |
| 363.5%/day | IMPACT §9 | 837.95/230.50 = **363.5%** | arithmetic exact, denominator wrong (§2) |
| day means 866/861/817/828 | IMPACT §9 | **866.04 / 861.47 / 816.55 / 827.94** | exact |
| gross pool $9,600/day | IMPACT §1.3 | $20 x 5 x 96; API confirms 5 legs/window on **all 1,277** windows, `period_reward` 200000 and `target_size_fp` 1000.00 on **all 6,385** programmes | exact |
| **"20 x 0.1174 x 0.7416 x 480 = $835.81"** | IMPACT §9 | its own `cap.pkl` holds mean share **0.11414**, not 0.1174; 20 x 0.11414 x 0.74294 x 480 = **$814.05** | **cannot reproduce** |
| $271.43/day, 111.0% | INVENTORY_PNL | $2.8274 x 96 = **$271.43**; /244.55 = **111.0%** | exact |
| $479.0/day net, 196% | INVENTORY_PNL | 4.989 x 96 = **478.9**; /244.55 = **195.8%** | exact |
| [+71, +882] day CI | INVENTORY_PNL | mean 476.26, sd 163.3, t(2)=4.303 -> **[+70.7, +881.8]** | exact |
| $490.17/day, 209.6% | CAPITAL_RUIN | 5.1059 x 96 = **490.2**; /233.91 = **209.6%** | exact |
| rebate 2.31x from S=50 -> 100 | INVENTORY_PNL §6 | 6.518/2.827 = **2.305x**; on **live** books I measure **2.129x** (25->50 is 1.849x, 100->200 is 1.521x) | mechanism real, 8% weaker on the true book |

**The one line I cannot reproduce** is IMPACT's own hand-check. Its artefact
holds a mean share of 11.41%, not the 11.74% the report multiplies by, and the
product of the two means is $814, not $838. The report calls the $835.81-vs-
$837.94 gap "Jensen from multiplying per-window rather than pooled means"; it
is a **positive covariance between share and qualifying fraction** (mean of the
product 0.087287 vs product of the means 0.084797), which is a different thing
and worth naming, because it says busy windows are good for us twice over. The
headline itself is unaffected.

**Also checked and cleared, because it is the one place our own order could
manufacture the result:** `impact/lip.add_share` recomputes the Reference Price
**with** our 50 lots in the book, which can pull the reference up and collapse
the denominator. On live books that convention is worth almost nothing — share
**11.32%** with the reference free to move vs **11.30%** with it frozen. The
super-linear scaling it drives is real but modest (2.129x from S=50 to 100).

---

## 4. WHAT WOULD STILL HAVE TO BE TRUE — RANKED

The number survived. Here is what it needs.

1. **"Your share of the yes side PLUS your share of the no side" must mean the
   average.** If it is literal, $779 becomes **$1,558**. Three jobs and three
   adversaries have now left this untouched. It is a **factor of two on the
   headline and it is one email to Kalshi support or one $5 live order.**
2. **"The depth that must be resting on each side" must mean raw depth.** I
   swept it: raw -> **$779/day**, excluding the 1c wall -> **$263/day**, depth
   within 10c of the touch -> **$5.86/day**, distance-weighted score ->
   **$1.56/day**. Kalshi's own 99.06% payout rate refutes the last three (they
   imply 35%, 62% and 90% of programmes never paying, against an observed
   0.94%). It does **not** cleanly separate raw from ex-1c on payout alone, and
   ex-1c would cut the number by two thirds. *Note the coincidence and do not
   read it as corroboration:* ex-1c on the **correct** book gives
   **$262.64/day**, almost exactly the **$271/day** the **broken** book gave.
   Two different errors, one number.
3. **The LIP denominator must contain only orders the public depth feed
   publishes.** Our share is 50/(visible score + 50) on a visible score of
   ~293. Hidden or non-published resting interest shrinks it proportionally.
   Untestable from public data; unchanged from IMPACT's own §8.
4. **Nobody must re-optimise against a new, persistent 15% claimant.** The
   longest response any tape can test is one window lagged. Unchanged.
5. **The programme must keep running ~474 leg-windows a day at $20.** Two of
   the twelve full days in the API pull ran 88 windows, not 96.

I could not break 1-4 and neither could anyone else. **Every one of them is a
question about the rule or about the future, not about the book.** The book
work is, in my judgement, now finished.

---

## 5. `BIASES.md` PATTERNS, CHECKED AGAINST ALL THREE REPORTS

| # | pattern | found? |
|---|---|---|
| 1 | look-ahead / hindsight | **no.** The winner-permutation test at d=0 reads 7.8 SE *against* the strategy; look-ahead reads the other way. |
| 2 | occupation-time sampling | **no.** All three step a one-second calendar grid; `rebate/sim.py` explicitly carries the score across quiet seconds and says why. |
| 4 | wrong clustering unit | **no harm.** I measured the ICC: design effect 1.00 for the rebate; jobB clusters its per-contract SEs on the market. |
| 7 | pooling across the dimension that matters | **partly.** IMPACT pools 1,078 leg-windows into one mean and extrapolates x480 from an unbalanced panel (only 108 of 265 events have all five legs). |
| 8 | selection on the measured quantity | **YES, new.** IMPACT's >=99% *reconstruction-quality* gate correlates with book activity, which is the thing being measured. Worth +6.1%. |
| 11 | trimmed statistic reported as the full one | **no.** jobB reports full and trimmed side by side. |
| 12 | silent empty loader read as a null | **YES, new instance.** `rebate/extract.py` silently drops the snapshot level arrays; nothing prints the ceiling; 26% qualification is then read as a measurement. |
| 13 | multiple looks | **no.** Three fill models x two distances, all reported. |
| 14 | detection asserted without power | **partly.** IMPACT prints no MDEs. I computed them and they are fine: the "post inside" null has MDE 0.148 lots/lot, and the paid-share erosion null has MDE **3.21% relative** = **$27/day** at $830/day. **IMPACT's central null IS powered for the money question.** Its "no window-to-window adaptation, lagged corr +0.041" is the one assertion with no interval attached. |
| 16 | the fixture disagrees with the collector | **YES, new instance.** `rebate/selftest.py` tests the scorer and the fill queue and **never feeds the replay a snapshot message at all**, so the `m.book = Book()` line was never executed by any fixture. |
| 17 | cluster SE off a handful of clusters | **YES.** `INVENTORY_PNL.md`'s headline [+$71, +$882] is a t-interval on **three** days against a stated floor of thirty. |
| 19 | the integrity check was the bug | **YES.** Treating a snapshot as a book reset is a correctness guard. It discarded ~74% of the depth on a healthy feed and printed nothing about how much it threw away. |

Meta-rule 1 of `BIASES.md` — *"every exciting result this project has produced
so far was a measurement bug"* — held again, but pointing the other way: the
bug was in the **boring** number, and removing it made the exciting one bigger.

---

## 6. WHERE I DISAGREE, VERBATIM

> **`INVENTORY_PNL.md`:** "The **111%/day rebate-only figure in the claim under
> attack is CONFIRMED** — independently re-derived here at $271/day on $245 of
> median peak concurrent capital = 110.9%/day."

**Disagree.** It is not independent — it is the same cached sim as
`REBATE_RISK.md`, sharing the same `extract.py`. And it is not a confirmation:
the book it was computed on is emptied 45 seconds into every window, and the
correct figure is 2.9x larger. Two errors landed it on the number it was
checking. Delete the word CONFIRMED.

> **`INVENTORY_PNL.md`:** "**6. That the LIP scorer is the buggy flat-tick
> one.** *Confirmed, and it cuts the conservative way.* ... Per the brief's item
> 3 that **understates** our share ... so **the rebate leg here is a lower
> bound** on that axis."

**Disagree.** `IMPACT.md` §1.1 established, two ways, that Coin Race is
`linear_cent`, and I re-verified the API field myself: the flat 1c tick is
**correct** for this series, not conservative. The rebate leg there is a lower
bound for a completely different reason — the wiped book — which that report
did not find.

> **`CAPITAL_RUIN.md`:** "### Reconciliation against `REBATE_RISK.md` ... All
> within 1%."

**Disagree that this is a check.** Both sides come from the same cached sim.
Two numbers out of one broken pipeline agreeing to 1% is a determinism test,
not a validation. It also uses `snap_tot` as the denominator — the error
`INVENTORY_PNL.md` had already found and fixed — so the two reports differ by
5.8% on the rebate and neither notices.

> **`IMPACT.md`:** "The cross-check — Kalshi paid $8,294 of $9,477 advertised,
> 87.5% — is consistent with a high number but does not pin the rule."

**Disagree with the framing, and it undersells the evidence.** `paid_out` is a
per-programme **boolean**, so 87.5% is the share of *programmes* flagged paid,
not the share of *dollars* distributed; as a check on the qualifying *fraction*
it has no power at all. But used correctly it is far stronger than the report
claims: the fraction of programmes that **never** paid (0.94% on settled days)
is a sharp prediction, and only the raw-depth reading matches it (0.8%). That
is the strongest single piece of evidence in this file, and `IMPACT.md` had it
in hand and did not use it.

> **`IMPACT.md`:** "PEAK CONCURRENT CAPITAL ... p95 $230.50, worst single second
> $232.50 ... **% return on capital 363.5%/day**."

**Disagree.** That is the max within one event's own window and it cannot see
the handover. On the wall clock the resting-only peak reaches **$458.00**, and
`CAPITAL_RUIN.md` independently measured **$392.29** including fills — a report
`IMPACT.md` does not cite. The return is **170-199%/day**, not 363.5%.

> **The brief:** "Snapshots for this series carry NO level arrays (a 15-min
> market opens with an empty book)."

**Disagree, and this instruction caused the whole mess.** 1,360 of 4,055 Coin
Race snapshots carry `yes_dollars_fp`/`no_dollars_fp`, and they are exactly the
in-window ones, arriving at a median 45 s with median depth 2,316/3,124. The
brief's own hard rule is what sent the cached sim into the bug.

> **The critic (criticism B):** "a binary that can move 10-30c before
> settlement."

**Agree with `INVENTORY_PNL.md` that this understates it** — on a 0/100 binary
the settlement move is the whole distance, sd 42c. Adding to it: the move is
concentrated in the four minutes that pay 9.8% of the rebate.

---

## 7. WHAT I COULD NOT DO

* **Could not settle the "plus vs average" 2x.** No public artefact
  distinguishes them. It needs one small live order, or Kalshi support.
* **Could not separate "raw depth" from "raw depth excluding the 1c wall"** as
  the Target Size test. Both survive the payout check; they differ by 3x on the
  headline ($779 vs $263). This is now the single largest open question and no
  tape can close it.
* **Could not re-run jobs B and C on the corrected book.** Their fill and
  inventory results stand on the wiped book. I established the direction (less
  queue => more fills => inventory risk over-stated) and that the share is
  almost unaffected, but the corrected joint distribution of (rebate,
  inventory) does not yet exist. It needs `rebate/extract.py` to capture
  `yes_dollars_fp`/`no_dollars_fp` and `sim.py` to load them instead of calling
  `Book()` — a ten-line change and one re-run.
* **Only 3.5 days of Coin Race book data exist.** Every day-level interval in
  this project has n <= 4 and none can carry a between-regime tail. My
  [$743, $816] is a statement about 2026-09-03 -> 06, not about next week.
* **Did not re-derive the fill model, the taker-toxicity numbers, or the
  settlement P&L.** Out of lens.
* **No live orders. No real money.** Every API call was an authenticated
  read-only GET.

---

## 8. THE ONE NEXT STEP

**Fix `rebate/extract.py` to keep the snapshot levels, re-run the three cached
sims, and re-issue `INVENTORY_PNL.md` and `CAPITAL_RUIN.md` from the corrected
book.** Ten lines in a file that already exists; no new data, no orders. Until
it is done the operator is holding two reports whose headline rebate is wrong
by a factor of 2.9 and one that is right for reasons the other two contradict.

Immediately after that, and before any size: **one $5 live order to settle the
"plus vs average" reading**, which is worth more than every remaining tape
question combined.

---

## 9. FILES

```
C:\Users\Joe\AppData\Local\Temp\kals-work\L2\
  livedepth.py   live authenticated depth on the 5 open Coin Race legs
  poll.py        43-sample poll across the 20:00Z rollover -> poll.jsonl (215 rows)
  livescore.py   LIP scorer + SELF-TEST (8 hand-checked assertions, PASS);
                 qualification under 3 readings, share under 2 ref conventions
  snapchk.py     do Coin Race snapshots carry level arrays, and when
  cluster.py     clustered SEs, ICC, design effect, whole-day bootstrap
  winner.py      winner-permutation test of the residual P&L (4,000 redraws)
  allcap.py      survivorship: rebate for ALL 1,345 markets  -> allcap.pkl
  variants.py    headline under 4 readings x 2 market sets   -> variants.pkl
  queue.py       real size resting in front of our quote
  capital2.py    wall-clock concurrent capital; where qualifying depth sits
  profile.py     minute-by-minute rebate profile inside the window
```

Self-test discipline: `livescore.py` refuses to touch live data until eight
hand-computed assertions pass, including the two cases that separate the
"reference price moves with our order" reading from the frozen one. Every heavy
pass ran in 17-20 s; none used `replay.load_quotes`.

**Collectors:** `kalshi_collector.py` PID **3381772** and `crypto_feeds.py` PID
**3385232** verified alive before, during and after every job (my own query
processes excluded from the filter). **Free disk 50.7 GB** at the end, above
the 6 GB floor throughout. No `python.exe` was killed.
