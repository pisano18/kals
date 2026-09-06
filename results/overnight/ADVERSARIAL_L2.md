# ADVERSARIAL REVIEW — LENS 2 of 2: the statistics and the self-tests

**Targets:** `RISK_REWARD.md` (job 3, risk/reward) and `HARDEN.md` (job 4,
mutation hardening), with a BIASES.md pass over the rest of tonight.
Written 2026-09-06. **I have no stake in any result and I default to refuted.**
Everything below was RUN, not read: 6 mutation panels re-executed, 5 new
mutation panels of my own written and executed, and every headline number in
`RISK_REWARD.md` recomputed from the same cached inputs.

Both collectors verified alive at start and end (§Resources). No `load_quotes`,
no tape read, no API call, no order.

---

## THE ANSWER IN ONE PARAGRAPH

**Two of tonight's claims do not survive, and one of them is blocking.**
**(1) The repository at `HEAD` cannot run its own self-test** — a clean
checkout of `HEAD` dies with `KeyError: 'atoms'` on line 580 of `pin.py`
*before a single check executes*, because `pin.py` was committed reading three
keys that an **uncommitted** `endgame.py` provides. `HARDEN.md` states "no
estimator was touched" and lists two changed files; there are three, and the
third is load-bearing for both its panels. **(2) The DEAR-only recommendation's
risk case is one trade wide.** DEAR-only's max drawdown is −$28.64 only if the
leg cut sits **above 35c**; at any cut ≤35c it is **−$51.05, identical to full
`pin`**, because one contract — `KXSOL15M-26SEP042130-30`, paid 35.0c, −$22.41
— crosses the line. The report's §7A says *"The finding does not depend on the
cut"* while printing the counterexample two lines above it. **(3) The 100%
mutation kill rate reproduces exactly, and is 100% against the 24 mutations its
author chose**: my first six independent mutations produced **two survivors**,
one of them a **live look-ahead in `walk_forward`** that changes the fixture's
out-of-sample trade count from 14 to 0 and passes every check. Set against
that: `RISK_REWARD.md` is scrupulously honest about being in-sample, its
clustering unit is **correct** (the close time, pooled across coins, 3.71
series per close), and its own machinery `rr3.py` killed **4 of 4** independent
mutations I wrote against it, including both of the ones my brief named.
**The money that survives is smaller than published: DEAR's $102.66/day becomes
$77–80/day once the deep books — which have never flipped — are assumed to flip
at the same rate as the shallow ones, which is what the report's own §7D
conclusion requires.**

---

## 0. WHAT I RE-RAN, AND WHAT REPRODUCED

Credit first, because a review that only finds fault is not a measurement.

| re-run by me | claimed | I measured | verdict |
|---|---|---|---|
| `mutate.py` (panel A, 16 mutations) | pin 9/9, informed 5/5 = 100% | **pin 9 killed 0 survived 0 crashed; informed 5/5** | **reproduces exactly** |
| `mutate2.py` vs current tree (panel B, 10) | 10 killed, 0 survived | **10 killed, 0 survived, 0 crashed** | **reproduces exactly** |
| `mutate2.py` vs `job4/pre` tree | 0 killed, 10 survived | **0 killed, 10 survived** | **reproduces exactly** |
| "zero deletions, all additions inside `selftest()`" | +156/−0, +182/−0 | `git diff --numstat`: **156 0**, **182 0**; single hunks at `pin.py:846` (inside `selftest` 558-1018) and `informed.py:867` | **HOLDS — no assertion was weakened** |
| `job4/pre/{pin,informed}.py` == `HEAD` | implied | sha256 identical to `git show HEAD:` | **HOLDS** |
| `job3rr/selftest.py` | 60 checks | **ALL 60 CHECKS PASSED** | **reproduces** |
| `job3rr/mutate.py` | 23/23 = 100% | **KILL RATE: 23/23 = 100%** | **reproduces** |
| RISK_REWARD §7F wrapper equivalence | asserted on 533 trades at `tau<=20` | I ran it at **`tau<=60`, the cell actually used: 2,641 trades, IDENTICAL** | **half a comparison, now whole, and it holds** |
| RISK_REWARD arithmetic (legs, additivity, $/day, peak capital) | see §1/§2 | recomputed from `tr_allm_t60_f0.5_w150.pkl` | **all reproduce to the cent** |

**The reported kill rates are real.** Nothing in `HARDEN.md`'s panel is
fabricated or mis-scored, and its "before" tree is genuinely `HEAD`'s
`pin.py`/`informed.py`. My disagreements below are about what those numbers
license, not about whether they were measured.

---

## 1. BLOCKING — `HEAD` DOES NOT RUN. THE THIRD, UNDECLARED FILE.

`HARDEN.md` opens:

> **This job earns $0.** It does not change a single published number -- every
> line added lives inside `selftest()` and **no estimator was touched** (338
> lines added, 0 deleted, verified by diff).

and closes §6 with:

> **I did not commit.** The working tree carries the changes; both self-tests
> pass, so the overnight runner will pick them up cleanly if it starts.

`git diff --numstat` on the working tree:

```
10      0       research/endgame.py     <-- NOT MENTIONED ANYWHERE IN HARDEN.md
182     0       research/informed.py
156     0       research/pin.py
```

`endgame.py` **is** an estimator — `pin` imports `scan`, `evaluate`,
`summarise`, `redraw_null`, `mde`, `fee_cents` and `outcome_of` from it — and
the uncommitted hunk adds three keys to `redraw_null`'s return value:

```
res["atoms"]   = len(set(out))
res["lo_mass"] = out.count(res["lo"]) / float(reps)
res["hi_mass"] = out.count(res["hi"]) / float(reps)
```

**`pin.py` at `HEAD` already reads all three** (lines 309-312, 580, 582, 629),
committed in `02e3697`. `endgame.py`'s half was never committed. I extracted a
clean `HEAD` tree with `git archive` and ran it:

```
$ KALS_SELFTESTED=0 python pin.py --selftest        # tree = git archive HEAD
  SELF-TEST -- against known answers
  A book that freezes 90 seconds out while the index decides ...
Traceback (most recent call last):
  File "...headtree\research\pin.py", line 580, in selftest
    f"(rank {100*nm['rank']:.1f}%, {nm['atoms']} atoms), "
KeyError: 'atoms'
EXIT=1
```

**Consequences, in order of severity.**

1. **`pin` has been un-runnable at `HEAD` since commit `02e3697`** — twelve
   commits back, spanning two automated runs. Every run since has passed only
   because the working tree carried the fix. `pin.py:1028` (`raise SystemExit
   ("self-test failed; refusing to touch real data")`) never executes; the
   process dies earlier and louder, which is the only good news here.
2. **`HARDEN.md`'s file list is wrong in the direction that breaks things.**
   Anyone who commits the two files it names, as it names them, ships a `pin`
   that cannot start.
3. **Both of `HARDEN.md`'s panels stand on the undeclared file.** `mutate.py`
   copies `C:\kals-repo\research`; `job4/pre/` contains `HEAD`'s `pin.py` and
   `informed.py` but the **working-tree `endgame.py`** (sha256 differs from
   `HEAD`, 50,342 vs 49,735 bytes). That is the right call for a comparable
   before/after — a pure-`HEAD` tree would have crashed both baselines — but it
   is not what the report says the tree is, and the report's "before" column is
   therefore not measured against the committed state of the repository.
4. This is **BIASES pattern 15, environment divergence**, in its purest form:
   a self-test that has only ever been run on the machine's dirty working tree
   cannot certify anything about the tree the runner will check out.

**Fix, one line, and it is not mine to commit:** `git add research/endgame.py`
before anything else is committed. Until then no commit of `pin.py` is safe.

---

## 2. THE 100% IS 100% OF A PANEL THE AUTHOR CHOSE — AND I BROKE IT IN SIX TRIES

`HARDEN.md` §5 is honest about this in advance:

> **WHAT IS STILL NOT PROVEN.** The panel is 24 mutations I chose. 100% means
> the gate covers these 24 named failure modes and their mirrors -- it is not a
> proof of completeness, and the next person to write a mutation this panel
> does not contain may well find it survives.

I am that person. Six mutations, written blind against the *new* guards,
`C:\Users\Joe\AppData\Local\Temp\adv2\mutate3.py`:

```
  baseline pin -> PASS ; baseline informed -> PASS
  1. [pin     ] walk_forward trains on the CURRENT close too (1-close look-ahead)  SURVIVED
  2. [pin     ] fee_cents HALVED -- a self-consistent wrong fee formula            KILLED
  3. [pin     ] warmup 150 -> 2: k fitted on two closes, still 'walk-forward'      SURVIVED
  4. [informed] SE clustered on TRADES, not closes (the project's pattern 4)       KILLED
  5. [informed] cluster key becomes the trade -- every cluster has one observation KILLED
  6. [informed] sign-scramble control is the MEASURE shrunk 1000x, not a scramble  KILLED

  KILLED 4  SURVIVED 2  CRASH 0  NOT-APPLIED 0
```

**`informed`'s new guards are strong** — 3 for 3, including both of the ones my
brief specifically named (SE clustered on trades instead of closes; a cluster
key that makes every cluster a singleton). Guard I1's hand-arithmetic on
`G=40 n=80` is doing exactly the work it claims.

**`pin`'s guard 4 has a structural hole, and it is in the property the whole
strategy rests on.** `HARDEN.md` describes guard 4 as

> (truncation test: removing only FUTURE closes must leave every refitted `k`
> bit-identical -- 9 closes checked, 0 moved)

and its verdict on the division of labour:

> Neither guard is sufficient alone. Together they cover the printed table:
> guard 4 owns the estimator, guard 7 owns the call site.

The code is `pin.py:829`:

```python
_tg, kpg = walk_forward([r for r in rows3 if r["close"] <= cig], ...)
```

**`<=` includes the close being traded.** So a `walk_forward` that trains on
close *i*'s own settled outcomes before pricing close *i* is bit-identical
under truncation and walks straight through. My mutation moves
`seen.extend(...)` above the `if i >= warmup:` block — five lines, a textbook
one-close look-ahead — and I measured what it does to the fixture
(`adv2/lookahead_probe.py`):

```
HONEST     : 14 trades, realised mean -3.9808c, k range 1.000000..6.474590
   truncation <= (the shipped guard)   9 checked, 0 k moved   -> passes
LOOK-AHEAD :  0 trades, realised mean +nan c, k range 4.285996..6.474590
   truncation <= (the shipped guard)   9 checked, 0 k moved   -> passes
```

The mutation is not cosmetic: it moves the fitted `k` floor from 1.00 to 4.29
and takes the fixture's out-of-sample trade set **from 14 trades to zero**, and
the entire self-test still returns PASS.

**A guard that does kill it, written and demonstrated.** The discriminating
property is not truncation but outcome-independence: `k` applied at close *i*
must not depend on the *outcome* of close *i* or any later close. Corrupt
`result` on every row with `close >= ci` and demand `k[ci]` is bit-identical
(`adv2/guard4_fix.py`):

```
  HONEST       outcome-perturbation test: 9 closes checked, 0 k moved (worst |dk| 0)        -> passes
  LOOK-AHEAD   outcome-perturbation test: 9 closes checked, 2 k moved (worst |dk| 0.465489) -> FAILS -- look-ahead caught
```

Only 2 of 9 move, because the look-ahead only bites on refit closes — but 2 > 0
is all a gate needs. **This is a drop-in replacement for guard 4's loop and it
costs one extra `walk_forward` call per checked close.**

**Survivor 2 (`warmup 150 -> 2`)** is the softer one: `k` fitted on two closes
is still "walk-forward" and nothing objects. That is BIASES pattern 17 (a
statistic off a handful of clusters) applied to the calibration rather than to
the result, and there is no floor on it anywhere.

**Revised honest kill rate for `pin`'s gate: 14 of 14 on the author's panel,
12 of 16 (75%) once six independent mutations are added.** `HARDEN.md`'s own
framing — *"Report half a comparison as half a comparison: 67%/40% was half a
comparison"* — applies to its own 100% with equal force.

---

## 3. `RISK_REWARD.md` — WHERE IT IS RIGHT, AND IT MATTERS

My brief asked three questions. Two of them come back clean and I will not
manufacture a complaint.

**Is any bootstrap resampling TRADES rather than CLOSES? NO.** `rr3.score()`
aggregates every trade into `pnl[close]` over a **fixed universe of closes**
before any resampling happens, so `boot_closes` and `boot_days` can only ever
see per-close dollars. I verified the cluster is the *close time shared across
coins*, not the market:

```
closes that fired: 712; carrying >1 series: 612 (86.0%); mean series/close 3.71
```

That is the correct unit under BIASES #4 (*"clustering by market when the shared
shock is the close TIME across all series"*), and it is the unit used. I then
attacked it directly with two mutations of `rr3.py`
(`adv2/rr3_mutate.py`) — both **KILLED**:

```
  baseline selftest -> PASS
  1. score() keys P&L on the TRADE: the bootstrap unit becomes the trade  KILLED
  2. universe silently shrinks to the closes that fired                   KILLED
  3. closes ordered by P&L, not by time                                   KILLED
  4. peak capital = MEAN over fired closes, not the max                   KILLED
```

**4 of 4.** `job3rr`'s self-test is the strongest gate I found tonight — it is
the only one that survived an independent panel.

**Is any figure presented as out-of-sample actually in-sample? NO — because
none is presented as out-of-sample.** §0 says, in bold:

> **WHAT IS IN-SAMPLE.** Everything. The `k` is walk-forward, but **all 95
> cells below were scored on the same 9.583 days**.

I could not find a violation of this. The `k` really is walk-forward (`seen` is
extended only *after* the close is traded, `pin.py:180`), the wrapper really is
identical to `pin._walk_markets` (I completed the check at `tau<=60`: 2,641
trades, identical), and the two headline claims are read off whole sweeps
rather than off an argmax — I confirmed the 50c cut is **not** the argmax of
DEAR $/day (2c gives $120.83 against 50c's $102.66).

**Multiple comparisons: 95 cells is an undercount, and Bonferroni is
decoration here.** The 95 excludes the choices made *before* job 3 started —
`build.py` produced six cells (`tau ∈ {20,30,60}` × `variant ∈ {one, allm}`)
and exactly one is analysed — so the true family is at least 101. More to the
point, the report computes `p < 0.00053` and then **never reports a p-value for
anything**, only bootstrap CIs. A family-wise threshold that is never applied
to a member of the family is a sentence, not a correction.

---

## 4. THE DEAR-ONLY RECOMMENDATION IS ONE TRADE WIDE — MY SHARPEST DISAGREEMENT

The report's recommendation is *"`m = 1`, DEAR leg only"*, and the case for it
is risk, not money (DEAR-only is worth **+$1.54/day** more). Verbatim, §2:

> **Dropping it raises $/day slightly, halves the drawdown, cuts top-10
> concentration from 36.6% to 22.0%, and takes the worst simulated 7-day path
> drawdown from $228.7 to $109.9.**

and §6:

> **The DEAR leg alone puts that number at −$109.9 — 44% of the clause — for
> +$1.54/day.** That is the sharpest risk argument in this report.

and §7A, defending the 50c cut:

> Flat from 5c to 75c because almost nothing lives there. **The finding does
> not depend on the cut.**

**That last sentence is false for the column the recommendation rests on.** I
swept the cut at 5c resolution (`adv2/cutsweep.py`):

```
 cut c  nDEAR  DEAR $/day  DEAR maxDD  DEAR worst close  CHEAP maxDD
    10   1341      101.03      -51.05            -51.05      -148.23
    20   1338      103.17      -51.05            -51.05      -153.03
    25   1337       99.22      -51.05            -51.05      -115.15
    30   1336      100.35      -51.05            -51.05      -125.95
    35   1336      100.35      -51.05            -51.05      -125.95
    40   1334      102.39      -28.64            -28.64      -148.37
    45   1333      102.66      -28.64            -28.64      -150.99
    50   1333      102.66      -28.64            -28.64      -150.99
```

**$/day is flat (99.2 – 103.2). The drawdown is a step function, and the step
is between 35c and 40c.** At any cut at or below 35c, **DEAR-only's max
drawdown is −$51.05 — exactly full `pin`'s — and "halves the drawdown" becomes
"changes nothing".** The step is one contract:

```
contracts costing 25c-50c: 4 trades
   KXSOL15M-26SEP042130-30   cost 35.0c  size 61.2  $ -22.41  close 1788571800
   KXBTC15M-26SEP021515-15   cost 29.0c  size 35.5  $ -10.81  close 1788376500
   KXZEC15M-26AUG310215-15   cost 42.0c  size  6.0  $  -2.62  close 1788156900
   KXZEC15M-26AUG292100-00   cost 35.0c  size  4.5  $  +2.85  close 1788051600
```

`KXSOL15M-26SEP042130-30` sits in the same close as DEAR's −$28.64 worst close.
Classify it DEAR and that close becomes −$51.05.

**Why this is a bias and not bad luck.** The leg split is, by the report's own
admission, *"a post-hoc cut on this tape"* whose *"decision to use it was made
after seeing 9.58 days of results"*. The cut was placed at 50c. The single
observation that would overturn the risk claim sits at 35c — **15 cents away,
inside the very region the report calls empty**. "Almost nothing lives there"
is the reason a single item there is decisive, not a defence against it. This
is BIASES **#13, multiple looks** (*"Choosing the tau cap, price band or window
after seeing which one worked"*), and the report printed the counterexample in
its own §7A table and then wrote the opposite sentence over it.

**What I am NOT claiming.** DEAR-only is still the better cell on $/day-per-$
of-drawdown at the 50c cut, CHEAP is still unmeasurable, and the *money*
finding ("DEAR carries the money") is robust across all eight cuts and all five
`k`-perturbed trade sets — that part survives everything I threw at it. What
does not survive is the *risk* argument that justifies the recommendation.

**Required correction:** §7A's "The finding does not depend on the cut" must be
split — "$/day does not depend on the cut; the drawdown improvement exists only
for cuts above 35c and is decided by one 61-contract SOL trade."

---

## 5. 85% OF THE MONEY COMES FROM BOOKS THAT HAVE NEVER FLIPPED

§7D is the report's own weakest-point section and it is honestly flagged, but
it stops one step short of the number that matters. Verbatim:

> **The rank test does not support a depth/edge relationship.** So: 85% of the
> DEAR money comes from the 380 deep-book trades, mostly because
> depth-proportional sizing *puts more contracts there by construction*, and
> the apparent per-contract rise is not statistically supported.

I decomposed the buckets instead of rank-correlating a two-point distribution
(`adv2/depth_edge.py`, `adv2/noflip.py`):

```
       depth     n  flips   flip%   win c   loss c   mean c     ctr
      0-20      397      4   1.01%    2.48   -95.01     1.50     638
     20-60      259      4   1.54%    2.33   -98.07     0.78    2456
     60-150     297      4   1.35%    2.47   -93.32     1.18    7262
    150-400     242      0   0.00%    3.00     0.00     3.00   13746
    400-+       138      0   0.00%    3.24     0.00     3.24   13800
```

**Every one of the 12 DEAR flips is in a book shallower than 150. The two
deepest buckets — 380 trades over 282 closes, 27,546 contracts, 85% of the
DEAR dollars — have had zero tail events.** Their +3.00c and +3.24c per
contract are not a higher edge; they are a win margin with no losses in it yet.

Two consequences, and the second is the money.

**(a) The report under-states the association, then draws the wrong comfort
from its own null.** A close-clustered bootstrap of (deep − shallow)
per-contract edge gives **+1.883c, 95% CI [+0.894, +3.102], excluding zero** —
so the association *is* there in-sample; the Spearman test simply had no power
against a distribution that is +2.6c with probability 0.991 and −95c otherwise.
Reporting `p = 0.199` as "not supported" is BIASES **#14, detection asserted
without power**, with the sign reversed: a null used as reassurance.

**(b) Take §7D's own conclusion seriously and a quarter of the headline
disappears.** If depth and edge are *not* related — which is what §7D concludes
— then deep books must be assumed to flip at the same rate as shallow ones:

```
DEAR total as measured                                        $983.86 = $102.66/day
if deep books flip at the pooled DEAR rate 0.90%              $739.58 = $ 77.17/day  (-24.8%)
if deep books flip at CP95 upper 0.79% (rule of three, 0/380) $770.78 = $ 80.43/day  (-21.7%)
if deep books flip at the report's own close-level 1.60%      $549.70 = $ 57.36/day  (-44.1%)
```

**The report cannot have both §7D's conclusion and its own $102.66/day
headline.** They are the same claim with opposite signs. The honest central
estimate for a depth-weighted book is **$77–80/day, not $102.66**, and the
report's own trade-level CP stress ($81.33/day) already lands in that range —
it is presented as a pessimistic tail when it is closer to the middle.

This does not kill `pin`. $77/day on $267 of peak concurrent capital is still
**28.9%/day on capital deployed** and still **$0.0195/contract/day**. It means
the published number is about 25% too high, and it means the forward test's
first job is to see a flip in a deep book.

---

## 6. THE "WORST OF 20,000 PATHS" IS SEED NOISE

§6 promotes a single order statistic to a binding constraint:

> **But read the "worst of 20,000" row before relaxing.** At the frozen size the
> full strategy's worst simulated 7-day path is **−$228.7**, which is **91% of
> the clause**. One path in 20,000 already nearly breaches at `m = 1` [...]

and derives from it *"$250 at the worst of 20,000 paths: m = 1.09 → $111/day"*.
The published figure is `random.Random(6)`. I re-ran the identical stress on
seeds 6, 1-5 and 7-10 (20,000 paths each):

```
FULL: worst-of-20000 = -229, -226, -217, -217, -269, -260, -213, -247, -238, -198
      2 of 10 seeds BREACH -$250 at m=1;  the report published -228.7 (seed 6)
DEAR: worst-of-20000 = -110, -103,  -99, -102, -102, -117, -133, -113, -136, -107
      0 of 10 seeds breach;  the report published -109.9 (seed 6)
      p99, by contrast: FULL -118.7..-120.8 (spread 2.1), DEAR -59.7..-61.3 (spread 1.6)
```

**The minimum of 20,000 draws has a 25% seed-to-seed spread; the 99th
percentile has a 2% one.** On two of ten seeds the frozen size *already
breaches* the $250 clause on this measure, and the implied binding multiple
`250/|worst|` ranges **0.93 – 1.26** for FULL (published: 1.09) and
**1.84 – 2.53** for DEAR (published: 2.27).

**Verdict:** the p99 rows are sound and should carry the argument; the "worst
of 20,000" column should be deleted or given an error bar. The *direction* of
the report's conclusion survives — DEAR-only really is the safer cell on every
seed — but "91% of the clause" is not a measurement, and neither is `m = 1.09`.

---

## 7. THE "95% CI OVER WHOLE DAYS" IS AN INTERVAL FOR A DIFFERENT NUMBER

Every table in §2 and §3 prints a `95% CI DAYS` next to a `$/day`. They are not
the same estimator. `rr3.boot_days` rescales each day to a 96-close equivalent
(`rate[d] = tot[d] * 96 / nc[d]`) and resamples *those*:

```
B. DEAR
   headline  total/span            =  +102.66 $/day
   mean of RAW day totals          =   +89.44
   mean of SCALED day rates        =  +115.06   <-- what boot_days is an interval FOR
   boot_days 95% CI                = [+76.29, +162.74]  midpoint +119.51
   headline inside CI? True; CI centred on the headline? False
   top-3 scaled day rates: 2026-09-06 +270.3 (from 33 closes, x2.91),
                           2026-09-05 +254.7 (from 96 closes, x1.00),
                           2026-09-04 +133.9 (from 95 closes, x1.01)
```

**Three different "per day" numbers are in circulation — $89.44, $102.66 and
$115.06 — and the CI printed beside $102.66 is built around $115.06**, 12%
above it and asymmetric by $17. The driver is the partial-day extrapolation:
**the single largest "day" in the DEAR resample set, +$270.3, is a 33-close
fragment multiplied by 2.91.** The scaling is defensible in isolation (a
partial day should not masquerade as a quiet one) but it manufactures the
upper tail of every day-level interval in the report out of a third of a day of
tape, and the same tape's two partial days sit at opposite ends of the range.

There is a second, smaller inconsistency in the same family: `boot_days` treats
a day as 96 closes, while the §7C jackknife treats a day as `n_closes/842` of
the span. That is why the report's *"dropping the single best day (2026-09-05,
+$254.68) still leaves +$85.88/day"* is `729.18/8.4906` where the 96-close
convention gives **$84.95**. A 1.1% difference, reconciled, not an error — but
the project should pick one definition of a day.

**Recommended correction:** label the day interval as what it is — *"95% CI on
the mean full-day-equivalent rate (mean $115.06/day)"* — or drop the two
partial days and report `n = 9`.

---

## 8. A CROSS-REPORT INCONSISTENCY: THE SAME DEGENERATE BOOTSTRAP, RETRACTED IN ONE FILE AND HEADLINED IN ANOTHER

`RISK_REWARD.md` §6 does something admirable — it retracts its own first pass:

> ### First: the day-block drawdown bootstrap is DEGENERATE here, and my first
> pass reported its output as if it meant something
> All 11 days are **net positive**. [...] **That is not evidence of safety; it
> is the bootstrap refusing to answer.**

`CAPITAL_RUIN.md`, written the same night, leads its headline paragraph with:

> probability of ruin is **0.00%** at S = 10, 25, 50 and 100, under three
> resampling schemes, at horizons of 5, 20, 250 **and 1,000** days, 20,000
> paths each.

and then, 280 lines later, concedes the identical defect:

> Every percentile in §3 and §4 is a re-showing of one calm three-day window; a
> Coin Race close during a genuine crypto dislocation is not in this sample and
> **this method cannot invent one.**

A resampling scheme over windows with a large positive mean, none of which
contains a losing regime, **cannot produce ruin at any horizon**; `P(ruin) =
0.00% over 1,000 days` is arithmetic, not evidence. It is the same number
`RISK_REWARD.md` retracted, in the same position `RISK_REWARD.md`'s first pass
put it. **The retraction should propagate: `P(ruin) = 0.00%` belongs in
`CAPITAL_RUIN.md`'s "what the bootstrap refuses to answer" section, not in its
opening paragraph.**

(The same partial-day rescaling flagged in §7 above also appears in
`INVENTORY_PNL.md`'s day table — 61 windows scaled to 96 — though there it is
printed alongside the raw window counts and the report explicitly tells the
reader to use the n=3 day-level interval instead. That one is handled honestly.)

---

## 9. WHAT WOULD MAKE **MY** FINDINGS AN ARTEFACT — AND WHAT THE CHECK SAID

| my claim | how it could be wrong | what I did | result |
|---|---|---|---|
| `HEAD` is broken | I extracted the tree wrongly, or `KALS_SELFTESTED` matters | `git archive HEAD` into a clean dir; ran with the same env `mutate.py` uses | crash reproduced verbatim, exit 1 |
| the look-ahead survives | my mutation is a no-op, so surviving means nothing | measured the fixture with and without: k floor 1.00→4.29, trades 14→0 | the mutation is live and material |
| the look-ahead is undetectable | maybe some other guard would catch it on a different fixture | ran the FULL `pin --selftest`, not just guard 4 — the whole gate returns PASS | survives the whole gate |
| guard 4 is fixable | maybe no cheap check discriminates | wrote the outcome-perturbation check and ran it on both trees | honest 0/9, mutant 2/9 — it discriminates |
| the 35c trade decides the drawdown | maybe the cut sweep is noisy | swept at 5c resolution and enumerated all four trades in 25c–50c | one trade, exact, reproducible |
| deep books have no flips | maybe a bucket-boundary artefact | checked at ≥150 as one bucket: 380 trades, 282 closes, **0** flips | holds; rule-of-three CP95 upper 0.785%/trade |
| the seed spread is real | maybe `Random(6)` is special or `stress` is stateful | 10 independent seeds, fresh `Random` each, same 20,000 reps | spread 25% on the min, 2% on p99 |
| `rr3` kills my mutations | maybe my mutations crashed rather than failed | two of four crashed on the first attempt; I repaired both to non-crashing forms and re-ran | 4/4 KILLED, 0 crashes |
| the day CI is mis-centred | maybe I mis-read `boot_days` | recomputed the scaled rates by hand and compared to `boot_days`' own output | 115.06 vs a CI midpoint of 119.51 |

**Where I could be wrong and am not claiming otherwise:** my six-mutation panel
is as arbitrary as the author's 24, and 2 survivors out of 6 is not an estimate
of anything — it is an existence proof that the panel was not exhaustive, which
is exactly what `HARDEN.md` §5 already said.

---

## 10. WHAT SURVIVES, RANKED BY RELIABILITY OF THE MONEY

**1. `pin`'s DEAR leg, at a lower number than published.** ~**$77–80/day**
(not $102.66) on **$267 peak concurrent capital** = **28.9–30.1%/day on capital
deployed**, **$0.0195–0.0203/contract/day**. Does **not** need the market to be
wrong in any exotic sense — it needs a stale quote to still be there when we
take it, which is a fill question, not a forecasting one. It is the only thing
tonight with 11/11 positive days, a leg-level clustered interval excluding
zero, and an estimator whose look-ahead I checked myself and could not break
(the wrapper equivalence holds at the cell actually used). **Haircut reason:
85% of it comes from books that have not yet had a tail event.**

**2. The self-test machinery in `job3rr` (`rr3.py`).** Earns $0 directly, but
it is the only gate tonight that killed an independent panel (4/4) including
both clustering attacks. If any of tonight's code is to be trusted with the
forward test's arithmetic, it is this.

**3. `informed`'s new guards.** 3/3 against my independent mutations. Real
hardening.

**4. `pin`'s new guards 5, 6, 7.** Real, and guard 7's data-flow spy is the
right idea — but guard 4, the one that owns the out-of-sample property, has a
hole I demonstrated and can be fixed in one line.

**REFUTED / must be corrected before anyone acts on them:**

* *"The finding does not depend on the cut"* (§7A) — false for the drawdown.
* *"halves the drawdown ... $228.7 to $109.9"* (§2) — true only for cuts >35c.
* *"worst simulated 7-day path is −$228.7, which is 91% of the clause"* (§6) —
  seed-dependent; 2 of 10 seeds breach.
* *"$250 at the worst of 20,000 paths: m = 1.09"* (§6) — really 0.93–1.26.
* *"The rank test does not support a depth/edge relationship"* (§7D) — the
  clustered bootstrap says it does; and taking §7D at its word costs 25% of the
  headline.
* *"no estimator was touched ... both self-tests pass"* (`HARDEN.md`) — a third
  file was touched, it is an estimator, and without it `HEAD` does not run.
* *"P(ruin) = 0.00%"* (`CAPITAL_RUIN.md` headline) — the same degenerate
  bootstrap `RISK_REWARD.md` retracted in §6.

---

## 11. WHAT I COULD NOT DO

1. **I could not test whether the look-ahead survivor exists in the real
   pipeline.** It does not — `pin.py:180` is correct today. What I proved is
   that the *gate* would not tell you if it stopped being correct. That is a
   claim about the gate, not about the published numbers.
2. **I could not run a full mutation panel against `endgame.py`**, which is
   where `fee_cents`, `evaluate`, `redraw_null` and `outcome_of` actually live
   and which `HARDEN.md` §9 correctly names as the next target. Everything I
   checked in `pin` stands on it.
3. **I could not resolve the depth/edge question**, only bound it. Zero events
   in 380 trades admits any flip rate up to 0.785%; only forward tape settles
   it, and the first deep-book flip is the observation that matters.
4. **I did not re-derive `RISK_REWARD.md`'s coin-count or stop-loss sections**
   from scratch. I checked their inputs and their arithmetic identities
   (`maxdd == worst_close` for both cells, which is what makes the stop
   conclusion follow) but I did not re-run the 60-subset averaging.
5. **I did not commit anything, modify any estimator, or touch
   `PREREG_pin.md`.** The `endgame.py` staging problem in §1 is a one-line
   `git add` and it is the operator's call.
6. **No orders, no API calls, no `load_quotes`, no tape read.** Everything came
   from `job3rr`'s cached trade sets, `rows_tau60.pkl`, `depth_map.pkl` and the
   repository itself.

---

## 12. NEXT STEP — ONE THING, AND IT IS FREE

**`git add research/endgame.py` before any other commit**, then replace guard
4's `<=` truncation with the outcome-perturbation check in
`C:\Users\Joe\AppData\Local\Temp\adv2\guard4_fix.py`. Together that is under
twenty lines, it costs no money, and it removes the two ways the pin edifice
can silently stop being what it says it is: a repository that cannot start, and
a look-ahead that nothing would report.

Then, for the forward test: **pre-register the leg cut at 50c *and* at 25c**,
because those two rules give the same $/day and opposite drawdowns on this
tape, and one 61-contract SOL trade is not a basis for choosing between them.

---

## FILES

| | |
|---|---|
| this report | `C:\kals-repo\results\overnight\ADVERSARIAL_L2.md` |
| my mutation panel (2 survivors) | `C:\Users\Joe\AppData\Local\Temp\adv2\mutate3.py` |
| look-ahead is live | `C:\Users\Joe\AppData\Local\Temp\adv2\lookahead_probe.py` |
| **the guard that kills it** | `C:\Users\Joe\AppData\Local\Temp\adv2\guard4_fix.py` |
| rr3 mutation panel (4/4 killed) | `C:\Users\Joe\AppData\Local\Temp\adv2\rr3_mutate.py` |
| statistics attack (cluster, CI, seeds) | `C:\Users\Joe\AppData\Local\Temp\adv2\rr_attack.py` |
| the 35c cut | `C:\Users\Joe\AppData\Local\Temp\adv2\cutsweep.py` |
| depth / zero-flip decomposition | `C:\Users\Joe\AppData\Local\Temp\adv2\depth_edge.py`, `noflip.py` |
| wrapper equivalence at `tau<=60` | `C:\Users\Joe\AppData\Local\Temp\adv2\wrapper_eq.py` |
| re-run panel logs | `C:\Users\Joe\AppData\Local\Temp\kals-work\adv2_mutate_rerun.txt`, `...\adv2\ext_after_rerun.txt`, `...\adv2\ext_before_rerun.txt` |
| clean `HEAD` tree that crashes | `C:\Users\Joe\AppData\Local\Temp\adv2\headtree\research` |

## RESOURCES

Both collectors verified ALIVE at the start and at the end of this review, same
PIDs throughout, both started 10:57:01: **`kalshi_collector.py` PID 3381772**
(WS 46 MB) and **`crypto_feeds.py` PID 3385232** (WS 38 MB). No python process
was killed and no filter matched anything but its own query. Free disk **51.3
GB** (hard stop 6 GB). Free RAM **3.81 GB** at the end; the heaviest single job
was `wrapper_eq.py` (two walk-forwards over `rows_tau60.pkl`, 18 MB pickle,
8.7 s) and `replay.load_quotes` was never called.
