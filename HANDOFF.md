# HANDOFF — read this first in a new session

---

## 2026-09-06 (re-scope) — the goal is MONEY. pin is a PASS. And I was
## wrong that the race is unmeasurable.

### Three corrections, all of them mine

**1. "The race is unanswerable from recordings" was wrong.** I said it twice
and it was a habit, not a fact. `orderbook_delta` carries **microsecond**
timestamps, a sequence number and a signed `delta_fp` per price level, so the
life of the exact level `pin` wants to hit is directly reconstructable.
Measurement running. Measured alongside it: round-trip latency from this box to
Kalshi is **median 30-36 ms**, min 29 ms, worst 199 ms, over read-only GETs.

**2. `$/day at 50 contracts` was the wrong unit and it misled the project.** At
$1,000 of capital the right units are $/contract/day, PEAK CONCURRENT capital,
and % return on capital. Restated:

    tau<=20 one-per-close cap 50   peak capital $49.70   $30.22/day   67.2%/day
    tau<=60 every-mkt cap100 f0.25 peak capital $268     $88.10/day   37.7%/day

**3. The close-level bootstrap understated the risk question and I nearly
handed over a number that flattered us.** It said the 1%-worst week was
**+$47**, which is an artefact of resampling closes **iid** — that destroys the
only mechanism that makes a real bad week, namely a volatile session where the
model is wrong across many closes at once. Redone as a BLOCK bootstrap over
whole days:

    tau<=20 one cap 50    10 days, 1 negative, worst day -$18.30, mean +$30.22
    tau<=60 allm f0.25    11 days, 0 negative, worst day +$10.47, mean +$88.10
    5-day week, resampling DAYS:  1%-worst +$27, 0.3% of weeks lose money

**The operator's $150 bad-week limit (20% of $750) does not bind at this
size. DEPTH binds.** The caveat that matters more than the number: 10-11 days
contains no crash and no volatility regime. This measures variance, not tail.

### pin is a PASS under the operator's definition of "consistently"

Positive expectancy, i.e. likely to come out on top if it runs its course. The
bootstrap interval excludes zero at every fillable size, on both close-level
and day-level resampling, and 10 of 11 days were positive. Recorded in
`CLAUDE.md` with both superseded bars and the reason each changed.

### The re-scope: every approach tried so far needs the MARKET TO BE WRONG

pin, informed, baskets, lead-lag, calibration, and all eight graveyard entries
share one structure: they pay only if the price is mistaken. **That is the
hardest and least reliable way to make money, and it was never what was
asked for.** The search is restructured around money that does not require
anyone to be wrong:

1. **Cross-venue.** Two venues pricing the SAME event differently needs no
   model, no null and no settlement mathematics. Never priced. Now running.
2. **Fees and rebates.** Cheaper fees on identical mechanics is free money.
   One API call, open for weeks.
3. **Being paid for a service** rather than for being right — market-making is
   this, and it is the other live idea.
4. **Relative value.** rho ~ 0.8 was only ever treated as a risk; the spread
   between two correlated series is hedged against what moves them both, and
   Coin Race legs MUST sum to 100c.
5. **Early exit.** Everything holds to settlement. Exiting when the stale quote
   catches up is the same signal with far lower capital lockup, which is the
   binding constraint at $1,000.

---

## 2026-09-06 (threshold revised) — pin is NOT dead. It is small, and the
## interval excludes zero. The bar moved, loudly and on the record.

### The correction

The previous entry graded pin FAIL against +$50/day and called it dead. The
operator has replaced that threshold, **after seeing the number**, and has
required both versions be recorded with the reason. See `CLAUDE.md`
"Kill criteria — change log". In short:

    OLD  net +$50/day at a fillable size
    NEW  positive after fees at a fillable size, demonstrated out of sample
         on fresh tape, with a maximum drawdown the operator can sit through.
         Size is capped by DRAWDOWN, not by a dollars/day target.

**No measurement changed. Nothing was re-run, re-fitted or re-weighted.** What
changed is the question. The 95% bootstrap interval at a fillable cap of 50 is
**[+19, +48] $/day** and it **excludes zero**; grading that FAIL against a
round number buried the actual finding, which is that pin is *small* and
*confidently positive*.

> **pin makes ~$33/day and we are confident it is positive.**

pin goes to **forward test, not the graveyard**. `PREREG_pin.md` is being
drafted with the size clause set by the depth measurement rather than by an
assumed 50 contracts, and **the forward clock does not start until the
operator signs it**.

### I withdraw the word "lottery ticket" on my own evidence

I applied the operator's pre-set drop-ten screen correctly and then attached a
label the same data contradicts. **78.3% of closes are individually
profitable.** A lottery ticket loses most of the time and pays rarely; pin
wins most of the time with a fat right tail. That is the opposite shape. The
concentration number stands unchanged and is a real risk — top 10 of 336
closes carry 45% of the money, top 25 carry 73% — but the label was wrong and
is withdrawn independently of any further test.

### THREE THINGS THAT DID NOT CHANGE, and travel with every pin number

**1. THE RACE. This is the primary open risk to pin, above everything else.**
The backtest cannot test whether we win the race for a stale quote. In the
backtest we always get it. In reality we are racing everyone else for the same
mispriced quote, and the most mispriced quotes are the ones most worth racing
for. **Real fills will be worse than backtest fills by an unknown amount, and
the amount is not bounded by anything measured so far.** Any statement of
pin's edge that does not carry this sentence is incomplete.

**2. NINE DAYS. The worst close in the sample is not the real downside.**
336 closes at 37.2/day is **9.0 days** of out-of-sample tape. Wherever
**-$38.65** appears as "worst close", it means "worst close observed in nine
days" and nothing more. A 9-day maximum is not a drawdown estimate; the true
tail is unobserved and, per the rule of three, a loss worse than anything seen
is entirely consistent with this sample.

**3. Concentration is real, and the drop-ten screen was harsh.** Most
fat-tailed strategies fail it. Keep the number, drop the verdict: top 10 = 45%
of the money, drop-ten leaves $19/day. Whether that lumpiness is a defect or
just the shape of the thing depends on whether the big closes are predictable
EX ANTE — which is now a queued measurement, not an assumption.

### Still open, in the operator's order

1. Repo-wide **96-vs-63.3 closes/day audit**. `portfolio()` computes
   `day = mu * 96 * contracts / 100`, but available closes run 63.3/day in the
   measured window. Every published $/day built on 96 may be inflated by up to
   **2.58x** (96/37.2 where the strategy fires) — list every number affected.
2. **Are the top closes predictable ex ante** from model-vs-book gap, realised
   vol, tau, time of day, coin, depth at touch, or spread width? Fit early,
   test late, walk forward. If yes, there is a better-shaped strategy inside
   pin: 73% of the money at 7% of the trades needs far less size, and size is
   the binding constraint. If no, the lumpiness is a risk to live with.
3. Everything already queued overnight.

---

## 2026-09-06 (verdict) — pin IS DEAD against the kill criteria. The edge
## is real; it cannot be filled at a size that pays.

Nothing here retracts the edge. `+2.54c` per contract at `t=+5.0` out of
sample stands. What fails is capacity, and the four pre-freeze checks the
operator demanded are what killed it.

### The bootstrap interval, not the point estimate, decides

Threshold: net +$50/day at a fillable size. 20,000-rep percentile bootstrap
over CLOSES — no normal-theory SE, because the distribution is nothing like
one (see concentration).

    variant   cap   $/day        95% interval      verdict
    one        50      33      [  +19,   +48 ]     FAIL
    one        69      45      [  +28,   +61 ]     INCONCLUSIVE
    every mkt  50      49      [  +22,   +76 ]     INCONCLUSIVE
    every mkt  69      64      [  +30,   +99 ]     INCONCLUSIVE

**Nothing clears.** A pass needs the whole interval above $50; the best honest
cell straddles it from $22 to $76. cap 100 is treated as UNAVAILABLE, not as
clearing: it consumes the entire resting level 60-62% of the time, which
assumes winning a race for a stale quote that this backtest cannot test — and
stale quotes are thin precisely because size does not sit on a price about to
be wrong.

### Concentration is the headline, and t=+5.0 was flattering it

    one/close cap 50    top 5 = 30%   top 10 = 45%   top 25 = 73% of the money
    every mkt cap 50    top 5 = 41%   top 10 = 56%   top 25 = 86%

    drop the best closes        one-per-close      every-market
      drop none                    $33/day            $49/day
      drop top 10                  $19/day            $22/day   [ +1, +40]
      drop top 25                  $10/day             $7/day   [-14, +24]

**The operator's own test was "if dropping ten closes takes it under $20/day,
this is a lottery ticket and not an edge." One-per-close lands at $19/day.**

**RETRACTED 2026-09-06 by the operator and by me, on this page's own evidence.**
78% of closes are individually
profitable, so it is not a coin flip — but the money lives in a handful of
closes and normal-theory SEs on that distribution overstate the confidence.

### AND THE EVERY-MARKET RESCUE MAKES CONCENTRATION WORSE, NOT BETTER

This retracts my own recommendation from earlier today. I proposed fixing the
four dead series to reach ~$65/day on the grounds that more coins is more
money at the same per-market size. The money part is true. The independence
part is false: going from one coin per close to 1.6 pushed top-10
concentration from **45% to 56%** and top-25 from **73% to 86%**. Coins at one
close are the same bet at rho ~ 0.8, so extra series amplify the same few big
closes rather than adding breadth — which is also why t falls 4.6 -> 3.6 while
the money rises. **Fixing the dead series would buy leverage, not
diversification, and should not be sold as a route past the threshold.**

### The two arithmetic reconciliations

**Worst close is -$38.65 at caps 50, 69, 100 and 250 — not a bug.** That close
(1788293700) holds a single trade whose resting depth was **40.1 contracts**,
below every cap tested. The cap never binds there, so raising it cannot make
that particular close worse. Confirmed explicitly rather than assumed.

**Fire rate: 37.2/day is right, 26.5 was mine and wrong.** The error was
dividing out-of-sample trades by a span that includes the 150-close warmup.
Measured: 723 closes in the tau<=20 scan over 12.2 days; the OOS window holds
572 available closes over 9.0 days; 336 fired = **58.7% of available closes,
37.2/day**. Note also that available closes run 63.3/day, not the 96 that
`portfolio()` assumes, so that constant is wrong on two counts.

### What this does and does not kill

Per the operator's criteria, this kills **pin** — not the project, and not the
search. `pin` dies here on capacity rather than on the forward test, which is
a cheaper death and an earlier one. The rule was never frozen and the 19-day
forward clock never started, which is the correct outcome: 19 days spent
confirming a miss would have been the waste.

**The queue-position simulator is now the main event.** Market-making is the
remaining live strategy and its capacity question is unmeasured.

---

## 2026-09-06 (depth) — pin is a TAKER and the book is thin. Every dollar
## figure so far assumed 50 contracts fill. 42% of the time they do not.

### What is actually resting where pin decides to hit

`side="yes"` lifts the ask, `side="no"` hits the bid (`endgame.evaluate`), so
the size that matters is at the touch, which `load_quotes` already carries. No
orderbook rebuild was needed. 336 of 336 trades matched a quote, median quote
age 0s, no empty touches.

    resting size, contracts    p10 2   p25 15   MEDIAN 69   p75 193   p90 455
                               min 0   max 113,600   mean 644

Mean 644 against median 69: the distribution is wildly skewed and the mean is
not usable. Would NOT fill: **10 contracts 20.2%, 25 contracts 31.2%,
50 contracts 42.3%, 100 contracts 60.1%** of the time.

### The money, restated at a size the book offers

    variant       cap   avg filled   $/close   $/day    worst   t   eats level
    one/close      50         35.0      0.90      33   -38.65  4.6       43.2%
    every market   50         35.4      1.31      49   -46.33  3.6       42.2%
    one/close     100         58.6      1.61      60   -38.65  5.7       61.6%
    every market  100         59.8      2.36      88   -88.20  4.0       60.4%

**Against the kill criterion (net +$50/day at a fillable size): pin MISSES.**
$33/day one-per-close, $49/day every-market — one dollar short — at 50
contracts, a size that already fails to fill 42% of the time.

The published $122/day was two compounding fictions: full fills (35.0/50 =
0.70) and 96 closes/day where the cell fires 37.2 (0.39). 0.70 x 0.39 x 122 =
$33.4. Reconciles.

### The two ways over the line, and what each costs

**Take more per market.** cap 100 clears at $60-88/day, but consumes the
ENTIRE resting level 60-62% of the time. That is not a passive take; it is the
sweep behaviour `informed.py` measures at +8.6c of adverse move, and it
assumes winning the race for a stale quote in full against everyone else who
wants it. This backtest cannot test that. **Do not bank it.**

**Trade more markets.** This is the sound one. Depth binds PER MARKET, and
twelve series settle on the same tick, so more coins is more money at the same
per-market size. Measured: every-market makes **1.48x** the money of
one-per-close (+$49 vs +$33) for **1.20x** the tail (-$46.33 vs -$38.65) —
sub-linear, i.e. favourable, and it does not eat books any deeper (42.2% vs
43.2%).

**But the t-stat falls, 4.6 -> 3.6.** Twelve correlated coins summed within a
close add variance without adding independent observations, exactly as
IDEAS.md B2's rho ~ 0.8 predicts. More money, less certainty. Both are true
and the report must carry both.

### The cheapest principled route over $50/day is fixing the dead series

`allm` gets 1.59 coins/close from the **9** series that return settled
markets. `KXADA15M`, `KXBCH15M`, `KXTON15M` and `KXCRYPTOCOMP15M` return zero.
At the same per-market size, 12 live series would give ~2.1 coins/close and
roughly **$65/day** — over the threshold without eating a single book deeper
and without touching the rule. That is CLAUDE.md next-action #3 and it is now
the highest-value item on the list, not a housekeeping chore.

This is also the only route that does not risk selecting a variant because it
clears the bar. Hunting floors or tau cuts until one prints $50 is exactly the
"selecting on our own error" trap `fit_k` was written for.

### Adverse selection checked, and it is NOT the problem

Sizing to depth means betting more where the book is deeper, which is only
free if depth is uncorrelated with edge quality. Measured P&L per contract by
depth bucket: <5 +4.13c, 5-15 +1.34c, 15-40 +1.17c, 40-100 +1.91c, 100-300
+3.68c, 300+ +1.66c. **No decay.** Size-weighting helps slightly (+0.176c at
cap 100). The benign explanation holds; the problem is purely that the book is
thin and that taking it all is unpriceable.

### Concentration, which matters for the forward test

At cap 50 the top 10 of 336 closes carry **45%** of the money and the top 25
carry **73%**. A 500-close forward window in which those few closes do not
recur would collapse the result. Worth stating before the clock starts.

### Operational

One run was killed by the harness for low memory (two processes each holding a
full `load_quotes`). The collector was never at risk — it sits at 25 MB and
kept writing throughout; the harness kills the largest offender, which was
mine. Rebuilt as one load with a TARGETED quote pass (533 ticker-instants
instead of every quote for 14,597 markets) and both cells are cached, so
future variants cost seconds rather than a reload.

---

## 2026-09-06 — JUDGEMENT, NOT MEASUREMENT: confidence and capacity

Everything else in this file is measured. **This section is not.** It is the
subjective read that formed over the whole project, written down because it
existed only in conversation and would otherwise be lost. Treat every number
below as an opinion with a name on it, and do not cite it as a result.

### Confidence that `pin` makes real money

| claim | confidence |
|---|---|
| the arithmetic is right (the settlement average IS knowable early) | ~99% |
| the pattern is real in the recorded tape | ~85% |
| it still works next month | ~60% |
| it survives live trading — latency, queue, partial fills | **~40%** |
| it makes *meaningful* money | ~15% |

**Overall: ~40% this makes real money, and if it does it is ~$10-25k/year,
not more.** The gap between 85% and 40% is everything the tape cannot test:
getting an order in inside the last twenty seconds, actually being filled, and
Kalshi noticing. Those only appear with money at risk.

The recommendation that follows from it: **do not scale.** If the remaining
checks come back clean, run it live with a few hundred pounds for a fortnight.
Reality is the only test left and it is cheap to buy.

### Capacity if `pin` runs on all twelve series at once

`evaluate()` takes one trade per CLOSE, which is a statistical rule, not a
trading limit — so every table in this file measures roughly one twelfth of
what a live book could hold. All twelve crypto series settle on the same
quarter hour.

Measured on a six-coin fixture at rho = 0.85 (`pin.py` self-test): money per
close scaled **8.2x**, and the per-close spread scaled **5.2x** against the
**1.9x** that independence would give.

**That is leverage, not diversification.** Twelve correlated coins are twelve
times the money AND very nearly twelve times the loss on the close that goes
wrong. Scaling the earlier $28-69/day by the coin count suggests **$300-400/day
territory** — but that number is an extrapolation from a fixture, not a
measurement, and the honest version needs `run_portfolio` to actually execute
against real data. **It never has.** Read its worst-close column before
believing any of this.

---

## 2026-09-06 (later still) — the sweep question is SETTLED: PER LEVEL, on
## shape rather than on a count. And pin's report contradicts itself.

### The answer, and it no longer depends on the clock

    12,000,000 trades                ts_ms    whole second      CONTROL
                                (true inst.)      (msg.ts)   (adjacent)
      groups                     6,330,052     1,225,485     1,661,130
      trades per group                1.90          9.79          6.11
      multi-price groups            10.7%         57.2%         76.9%

      SHAPE of the multi-price groups -- no clock involved:
      single-sided                  96.7%         32.4%         18.0%
      monotone price ladder         99.6%         44.0%         50.0%
      single-sided AND monotone     96.6%         28.3%         12.9%
        ...walking taker's way      96.6%         27.3%         10.0%
      consecutive exchange seq      99.8%         23.2%         32.8%

**PER LEVEL.** At the true instant, multi-price groups are one-sided monotone
ladders walking the taker's own direction over consecutive `seq` — a book
being walked, not trades coinciding. The CONTROL is the operator's suggestion
and it is what the first version lacked: groups of trades ADJACENT in time but
never simultaneous, drawn to the same size distribution. It scores **15.3%** against
the real **96.6%**, so the test is reading sweep structure and not merely that
a busy book trends.

*(Corrected: the first control drew 6.11 trades per group against 1.90 for the
real groups, and every all-N-legs test gets harder as N grows, so its 12.9%
was a handicapped baseline rather than the chance rate. Re-scored per leg
count and re-weighted to the real size distribution it is 15.3%. The contrast
holds at every stratum — at n=2, where monotone is free, real 92.5% against
control 23.1% on 157,301 and 138,564 groups; at n=12, 98.3% against 5.0%.)* Also checked: `is_block_trade` is false on
1,255,096 of 1,255,096 trades, so negotiated blocks are not manufacturing the
ladders.

So the touch leg of a sweep is its own print at its own price, is already
inside `at-touch`, and **the maker verdict is re-reported unchanged: +0.48c
stands; the -0.42c branch is closed.**

### The 59% was grouped by SECOND, and its own arithmetic said so

`sweep_shape()` grouped on `round(float(t), 3)` with `t` from
`edge.load_trades`, which reads `msg.ts`. On disk `msg.ts` is exactly
`floor(ts_ms/1000)` on **4,168,479 of 4,168,479** trades, so "same instant"
meant "same second". `ts_ms` is on **100%** of trade messages and was never
read; `created_time` is on **0%**, so the `ts or created_time` fallback never
fires.

The tell was already printed: **4,000,001 trades in 401,591 groups is 9.96
prints per "instant" on one ticker**, where the true instant gives 1.90. Ten
prints in one millisecond on a single 15-minute binary is not credible; ten in
one second is ordinary. Grouped by second, only 28.3% of multi-price groups
have sweep shape at all — the rest is pooling. The old diagnostic would have
returned PER LEVEL off a tape with no sweeps in it, and the self-test now
contains exactly that tape.

`edge.load_trades` was **not** changed. Its whole-second timestamp is what
every other stage is calibrated against, and moving it is a decision, not a
cleanup — see the next section.

### UNRESOLVED, and it is a decision: every reference quote is ~1.1s too old

`schema.json` pins `ts -> msg.ts` for **both** channels and `load_quotes` then
does `int(round(t))`, so both sides of the at-touch classification are snapped
to whole seconds and `measure()`'s strictly-earlier rule cannot see inside
one. Measured on 251,526 trades over three hours:

    true age of the reference quote     p25    median    p75   >2s old
      second stamps (running today)    1.39s    1.75s   2.17s    34.2%
      true ms stamps                   0.34s    0.65s   1.01s    14.1%

The `filldepth2s/at-touch` row is defined as "reference quote at most 2s old",
and on second stamps a quote the code believes is inside 2s is typically
1.4–2.2s old in truth. A sub-second adverse-selection question is being decided
against a median 1.75s-stale quote.

**It is safe on the look-ahead axis** — 0.00% of selected quotes land after
their trade under either rule, so this is staleness, not leakage. Two things
argue it is not urgent: `filldepth/at-touch` (no freshness filter) and
`filldepth2s/at-touch` agree to 0.01c, so the result is not resting on that
filter. But it moves numbers in `calib`, `edge`, `informed` and `maker`, and
the direction of its effect on +0.48c is unknown. **Not applied.**

### The maker row's half-spread is an identity, not a measurement

`RESULTS_informed.md` line 145 states it plainly: *"half-spread is derived, not
assumed: maker = half - mkS holds exactly by construction, so half = maker +
mkS."* So "0.49c, exactly half the 1c tick, as it must be" is a consistency
check, not independent corroboration. The independently measured quantities are
`maker` (+0.48c, t=6.4) and `mkS` (+0.01c, t=0.1). The arithmetic reconciles:
0.49 − 0.27 = 0.22 at 1s, 0.49 − 0.01 = 0.48 at settlement.

### RETRACTED, and replaced: pin's fair-band flag was floating-point dust

**My previous entry framed this as two competing criteria and that was
wrong.** `pin.py:213-216` is a single `if/elif` with one AND condition —

    if  sm["mean"] > nm["hi"] and sm["mean"] >= nf["lo"]:  -> beats the null
    elif sm["mean"] < nf["lo"]:                            -> BELOW the band

— and the report footer describes that same line. There was never a
disagreement between `fit_k`'s docstring and the footer. Withdrawn.

**The real fault is worse and it is now fixed.** The fair band is a
**discrete** distribution. Every row in a pinned cell carries a model
probability at 0.98+ or 0.02-, so one simulated re-settlement differs from the
next by whole FLIPS and the per-trade mean moves in steps of `100/n` cents —
0.2976c at n=336. 2,000 draws produced **11 distinct values**, not a smooth
curve:

        +2.2487c   n=  16   cum  1.2%
        +2.5463c   n=  88   cum  5.6%   <-- the 2.5% cut lands INSIDE this atom
        +2.8439c   n= 238   cum 17.5%

The realised result **is** that atom. `nf["lo"]` was `+2.546269041666672` and
the realised `+2.5462690416666676` — the flag fired on a difference of
**-4.4e-15**. More reps cannot help: at reps=50,000 the answer was byte-
identical, because the discreteness is intrinsic and not sampling error. So
the operator's Monte-Carlo-noise hypothesis was the right suspicion about the
wrong mechanism.

`redraw_null` now takes `value=` and returns a mid-p percentile **rank**
(strictly-below plus half the ties), and `pin.block` thresholds that instead of
the band edge, printing TIED rather than resolving a tie. Re-scored:

    tau<=20s, floor 0.5c   fair-band rank across 10 seeds at reps=50,000
      mean 4.08%   sd 0.06%   min 4.00%   max 4.16%
      seeds calling it BELOW the 2.5% band:  0 of 10

**That cell is NOT below the fair band.** It beats the market-is-right null
(+2.546c against a mid-null top of +0.761c at reps=50,000) and sits at the 4.1st
percentile of its own model's distribution — low, honestly low, but inside.
`pin --selftest` still passes.

The 1.0c and 2.0c floors are a different matter: they are far below their
bands, not tied to them, and this fix does not rescue them.

### The money column assumes it trades every close, and it does not

`portfolio()` computes `day = mu * 96 * contracts / 100` — 96 closes a day,
i.e. every 15-minute close. Measured: the tape holds **1,201 distinct closes
over 12.7 days** (94.8/day, so the 96 grid is right), but the `tau<=20s`
cell fires on **336** of them — 28%, about 26-30 traded closes per day once
the 150-close warmup is removed. The printed figures are therefore roughly
**3.2-3.6x too high**:

    tau<=20s floor 0.5c        printed      corrected for fire rate
      one per close          $+122/day            ~$34-39/day
      every market           $+190/day            ~$53-60/day
    tau<=60s floor 0.5c
      every market           $+143/day            ~$84/day

The worst-close dollars are unaffected — those are per close, not per day.

### The portfolio table, both rows, both cuts — the half I left out

I previously quoted only the worst-close column, which is half a comparison.
Verbatim from `RESULTS_pin.md` (run 0419):

    tau <= 20s, floor 0.5c
      one per close   336 trades over 336 closes (1.0 coins/close, max 1)
                    per close +2.55c t=+5.0 MDE 1.01c  WORST close  -96.3c
                    at 50 contracts: $+122/day  worst single close $-48.13
      every market    533 trades over 336 closes (1.6 coins/close, max 7)
                    per close +3.95c t=+4.5 MDE 1.73c  WORST close  -96.3c
                    at 50 contracts: $+190/day  worst single close $-48.13
    tau <= 60s, floor 0.5c
      one per close   713 trades over 713 closes (1.0 coins/close, max 1)
                    per close +0.25c t=+0.9 MDE 0.56c  WORST close  -99.3c
                    at 50 contracts: $+12/day   worst single close $-49.63
      every market   2641 trades over 713 closes (3.7 coins/close, max 9)
                    per close +2.99c t=+3.4 MDE 1.72c  WORST close -427.4c
                    at 50 contracts: $+143/day  worst single close $-213.68

**Read whole, the basket is not the warning I made it sound like.**

* At `tau<=20s`, going from 1.0 to 1.6 coins per close raises the return
  **+2.55c -> +3.95c (1.55x)** and leaves the worst close **unchanged at
  -96.3c**. More money, identical tail. That is strictly better.
* At `tau<=60s`, the return goes **+0.25c -> +2.99c (12.0x)** while the worst
  close goes **-99.3c -> -427.4c (4.3x)**. Return grows ~2.8x faster than the
  tail. Sub-linear, and therefore an argument FOR the basket, not against.
* The caveat that survives: the `tau<=60s` one-per-close base is +0.25c with
  MDE 0.56c — **below its own MDE, i.e. no measured effect**. A 12x multiple
  on a non-result is not a 12x anything. The every-market row at +2.99c,
  t=+3.4, MDE 1.72c does clear its MDE.
* Best cell on both axes is `tau<=20s every market`: highest return AND the
  smaller tail (-96.3c against -427.4c). It dominates `tau<=60s every market`.

Dollar arithmetic reconciles: 3.95c x 50 contracts = 197.5c = $1.975/close,
x96 = $189.6 ~ the printed $+190. Worst -96.3c x 50 = -$48.15 ~ the printed
$-48.13.

### Housekeeping

* **`pin` has now run with the portfolio table.** `CLAUDE.md`'s next-action #1
  is already done: run 0419 executed at 944e8cb, which contains
  `run_portfolio`, and `RESULTS_pin.md` carries the all-coins block. Its
  warning lands as predicted — at `tau<=60s` the worst single close is
  **−427.4c** across coins against **−96.3c** for one, i.e. leverage, not
  diversification.
* The published `RESULTS_informed.md` from that run still carries the old
  59.0% section. Its tables are unaffected — sweep shape is a pure diagnostic
  whose return value nothing consumes — so the run does not need re-running;
  only that section is superseded.

---

## 2026-09-06 (evening) — MARKET-MAKING IS CONFIRMED. pin's tail arrived
## exactly where the bound said it would.

### The sweep question is settled: Kalshi prints PER LEVEL

    4,000,001 trades in 401,591 (ticker, instant) groups
      single print at that instant          103,314   25.7%
      several prints, SAME price             61,386
      several prints, DIFFERENT prices      236,891   59.0%
      legs per multi-price group: median 8, max 806

**59% of same-instant groups carry different prices, median 8 legs.** So the
touch leg of every sweep is its own print and is already inside `at-touch`.
The at-touch maker P&L stands as measured, and the -0.42c alternative is dead.

### The maker result, on 17.1 million fills

    filldepth2s/at-touch   half-spread 0.49c
      markout   0.27c @1s   0.29 @5s   0.32 @30s   0.15 @300s   0.01 @settle
      maker net +0.22c @1s                                      +0.48c @settle

    at-touch  17,139,809 trades  1,071 closes
      taker information (mkS)  +0.02c   t=0.2    <- ZERO
      maker P&L                +0.48c   t=6.4
      random-sign control      -0.01c   t=-0.9   <- clean

A maker resting at the touch collects 0.49c of half-spread -- exactly half the
1c tick, as it must be -- and the takers who fill them carry **no information
at all** (t=0.2 on seventeen million observations). The informed flow sweeps:
+8.6c at 3c+ out. That is the textbook shape and this is the first time this
project has measured it.

It also pins maker.py's error precisely: **its 0.50c capture was right.** It
compared that capture against the ALL-FILLS markout of 0.612c when the
at-touch population is only 0.27c. Two different populations, one comparison.

**What is NOT yet known is capacity.** +0.48c is per fill; how many fills a
real quote receives depends on queue position, and 55 contracts sit at the
touch. That is the next build and the only thing between this and a number in
dollars. Do not multiply 17.1M by anything.

### pin: the tail arrived, and it landed inside the bound

    tau <= 20s, out of sample
      floor 0.3c  n=376  MDE 1.44c  REALISED +2.13c  t=+4.4
        DEAR n=309 paid 97c  1 flip  bound 1.29%  breakeven 2.47%  headroom 1.9x
      floor 0.5c  n=335  MDE 1.54c  REALISED +2.54c  t=+5.0
        DEAR n=262 paid 96c  1 flip  bound 1.53%  breakeven 2.93%  headroom 1.9x
      floor 1.0c  n=233  MDE 2.13c  realised +2.23c  t=+3.1
        DEAR n=171           2 flips bound 2.92%  breakeven 2.96%  headroom 1.0x

**t has risen on every single tape: 3.0, 3.7, 4.5, 4.9, now 5.0.**

And the loss that had never been seen has now been seen. Last tape reported
0 flips in 260 and a 95% upper bound of 1.15%; this one reports **1 flip in
262**, a rate of 0.38% -- inside the bound, as it should be. Headroom fell
from 2.5x to 1.9x, which is what happens when an unobserved tail becomes an
observed one. That is the rule of three doing its job rather than failing.

The high floors are now marginal: floor 1.0c out of sample has headroom 1.0x,
and in sample floor 2.0c is 0.8x. **The low floors are the strategy; the
aggressive ones are not safely positive.** Take more, smaller edges.

### Not in this run

It was launched at 785fe20, before the all-coins portfolio table was pushed.
The twelve-series capacity question is unanswered and needs one more run.

---

## 2026-09-06 (later) — pin's real shape, and the one fact the maker
## verdict hangs on

### pin: splitting the legs shows a clean, tradeable strategy

    tau <= 20s, out of sample, floor 0.5c
      n=333 closes   MDE 1.55c   REALISED +2.53c   t=+4.9
        DEAR   n=260  paid 96c  won 260/260  P&L +2.91c
        CHEAP  n= 73  paid  1c  won   2/73   P&L +1.19c

**t is now +4.9** (from +3.0, +3.7, +4.5 on successive tapes). And the split
resolves the "26% flip rate" that looked alarming: EVERY flip was in the CHEAP
leg losing its 1c premium. The two legs are different businesses:

* **DEAR is the original thesis, and it works.** Pay 96c for a contract the
  locked prints say is decided; it paid out **260 times out of 260**. This is
  the strategy I described at the start, and it is the one carrying the money
  (260 x 2.91c = 757c against CHEAP's 87c).
* **CHEAP is a lottery ticket** -- buy at 1c, win 99c about 3% of the time.
  Positive by payoff ratio rather than by the model being right (any rate
  above ~1% is +EV), and on 73 trades with 2 wins it is far too noisy to
  claim. It should probably be dropped rather than defended.

**The risk is entirely unobserved and is now priced in the report.** A flip at
a 96c entry costs -96.3c, which is 33 winners. Zero flips in 260 gives a 95%
upper bound of 1.15% on the true rate (rule of three); breakeven is **2.9%**.
So there is about **2.5x headroom** -- comfortable, but resting on a tail that
has never once been seen. Every pin line now prints flips, the upper bound,
the breakeven rate and the headroom.

    money, DEAR leg only: 24 trades/day
      at  40 contracts   $28/day    $10.0k/yr
      at  55 contracts   $38/day    $13.8k/yr
      at 100 contracts   $69/day    $25.1k/yr

### maker: the at-touch row came back CLEAN, and now hangs on one fact

Quarantining the stale fills fixed it. `filldepth2s/at-touch` (reference quote
at most 2s old):

    half-spread +0.49c   markout 0.28c @1s ... 0.02c @settlement
    maker net   +0.22c @1s   +0.47c @settlement    (t=+6.1, 16.8M trades)
    at-touch taker information: mkS +0.03c, t=0.4  -- ZERO

That is the shape a maker wants: the money is at the touch, takers who fill
there carry no information at all, and the informed ones sweep (+8.61c at 3c+
out, t=40.4). It also locates maker.py's error precisely: **its capture (0.50c)
was RIGHT; its markout was the ALL-FILLS 0.612c when the at-touch population
is only 0.28c.** It compared two different populations.

**But one unverified assumption decides everything.** A maker at the touch is
filled at the touch by any order that reaches it -- including the first leg of
a sweep that goes on to eat three levels. Whether that fill is already counted
depends purely on how Kalshi prints a sweep:

* **per level** -> the touch leg is its own print, already inside `at-touch`,
  and **+0.47c stands**
* **one print at VWAP** -> the touch leg is invisible in the -out buckets, a
  touch maker eats it unpriced, and the volume-weighted answer is **-0.42c**

+0.47c against -0.42c is the difference between a strategy and nothing, and it
is settled by a reporting convention rather than by anything about the market.
`sweep_shape()` now counts trades sharing an exact instant on one ticker and
reports how many carry DIFFERENT prices. Many => per level => the number
stands. Near zero => the at-touch figure is an overstatement.

**Until that prints, the maker verdict is unresolved.**

---

## 2026-09-06 — pin is STILL strengthening; the at-touch maker row is
## contaminated and its verdict is not yet readable

### pin, third look, out of sample

    tau <= 20s          n     MDE   claimed  REALISED       t   mid-null top
      floor 0.3c      360   1.46c    +2.98c    +1.94c    +4.0        +0.55c
      floor 0.5c      319   1.57c    +3.27c    +2.36c    +4.5        +0.48c
      floor 1.0c      222   2.22c    +5.75c    +2.14c    +2.9        +0.79c
    tau <= 60s: +0.24 / +0.20 / +0.32c, all t < 1. Still nothing.

**t has risen every time more tape arrived: +3.0 in sample, +3.7, now +4.5.**
That is what a real effect does and a fitted one does not. It clears its MDE
(2.36 vs 1.57) and the market-is-right null (top +0.48c), out of sample, with
the confidence refitted only on earlier closes.

**My reporting of it was wrong and is fixed.** The line read "paid 74.9c, won
77.4%, win +3.7c, loss -2.2c" -- and win minus loss must be 100c for ANY
binary, so that pair was impossible. The trades are two opposite populations:
DEAR ones bought near 96c (win +4c, lose -96c) and CHEAP ones bought near 2c
(win +98c, lose -2c). Their average, 74.9c, is a price at which nothing was
ever bought. Each population is separately zero-EV if the market is right, so
the +2.36c is edge over the market either way -- but the two legs are now
printed separately, with their own counts, prices, win rates and P&L.

The stated confidence is still fiction: >=98% claimed, 77% delivered.

### The maker at-touch row cannot be read yet

    filldepth      trades      mkS      t    maker      t
      at-touch  24,630,462   -0.71c  -10.0   +0.52c    +7.0
      0-1c-out   7,014,249   +0.89c  +11.4   +0.10c    +1.2
      1-3c-out   2,983,928   +2.78c  +32.3   -0.13c    -1.6
      3c+-out    1,968,990   +8.62c  +39.8   -0.37c    -1.8

The shape is exactly what a maker would want: the money is AT THE TOUCH
(+0.52c, t=+7.0, on two thirds of all trades) and negative out in the ladder,
which is the opposite of the fear that killed the last version of this idea.
Takers who print at the touch have NEGATIVE information (-0.71c); the informed
ones sweep (+8.62c at 3c+ out). Economically coherent.

**But the at-touch half-spread came back as -0.19c, and a maker who captures
less than nothing is not a maker -- it is a stale reference quote.** The
bucket test was `beyond <= 0.05`, which sweeps in every print that landed
INSIDE the recorded quote, i.e. every case where the book had already moved
and our reference was old. Those fills belong to nobody.

Fixed: `inside-stale` is its own bucket now, and the whole split is repeated
against a reference quote at most 2 seconds old (`filldepth2s`). If at-touch
and at-touch(fresh) disagree, that difference IS the staleness. Until that run
lands, **the maker verdict is unresolved -- not positive.**

---

## 2026-09-05 — pin SURVIVES out of sample, and the maker correction was
## not the one I proposed

### pin: out of sample it got STRONGER, and it is a different bet than I said

    tau <= 20s, out of sample, sigma recalibrated on earlier closes only
      floor 0.3c  k 0.50->1.26  n=307  MDE 1.69c  REALISED +1.82c  t=+3.2
      floor 0.5c  k 1.37->1.35  n=270  MDE 1.82c  REALISED +2.27c  t=+3.7
      floor 1.0c  k 1.36->1.59  n=187  MDE 2.61c  realised +2.06c  t=+2.4 (inside MDE)
    tau <= 60s: nothing, again.

The 0.5c cell beats its MDE (2.27 vs 1.82) and the market-is-right null
(top +0.78c) with a HIGHER t than in sample (+3.7 vs +3.0). The effect is
still confined to tau <= 20s, which remains the settlement arithmetic's own
prediction.

**But it is not the strategy I described.** Backing the entry price out of
(mean P&L, flip rate):

    in sample   paid ~91.5c   won 94.3%   edge +2.8pp
    out of sample paid ~70.3c  won 74.1%   edge +3.7pp

The recalibration shrinks fair, which shrinks every edge, so only the LARGEST
market-model disagreements still clear the floor -- and those are much cheaper
entries. So the out-of-sample bet is not "buy a 92c near-certainty": it is
"buy at 70c something that wins 74% of the time". Same money, completely
different risk, and the only way to see it was to solve for it by hand. `pin`
now prints entry, win rate, mean win and mean loss on every line.

The model's stated confidence remains fiction at every cut: it says >=98% and
delivers 74-94%. The edge is real in the P&L; the CONFIDENCE is not, and no
position size should ever be taken from it.

### maker: the horizon was NOT the correction. The capture was.

The measured curve:

    cell        half-spread    1s      5s     30s    120s    300s   settle
    ALL              0.73c   0.60c   0.61c   0.64c   0.62c   0.47c   0.39c
      maker net              +0.13   +0.12   +0.09   +0.12   +0.27   +0.35
    1c spread        0.57c   0.50c   0.51c   0.53c   0.53c   0.39c   0.27c
      maker net              +0.08   +0.07   +0.05   +0.04   +0.18   +0.30
    >=5c spread      4.02c   2.30c   2.35c   2.70c   2.37c   2.31c   3.03c
      maker net              +1.72   +1.66   +1.32   +1.65   +1.71   +0.99

Impact does peak near 30s and decay, but only from 0.64c to 0.39c. That is
NOT what flips the sign. **The markouts agree with maker.py (0.600 vs
0.612c). The capture does not: maker.py used half the MEDIAN spread, 0.50c;
the measured mean signed (trade price - pre-trade mid) is 0.73c.** The verdict
turned on that one assumption, and the maker net is positive at EVERY horizon
once the capture is measured rather than assumed.

**Do not trade this yet, and the reason is specific.** A fill 3c from the mid
pays the maker 3c -- but only a maker QUOTING 3c out collects it, and they are
filled far less often. The +0.35c may be an average over a ladder nobody can
rest the whole of. `informed.py` now splits every measure by how far the print
landed from the pre-trade touch (at-touch / 0-1c / 1-3c / 3c+). **The at-touch
row is the only line a maker at the best bid or offer can actually collect.**
If the positive number lives in the -out rows, maker.py was right for the
wrong reason and this is not a strategy.

---

## 2026-09-04 (evening) — FIRST RESULTS FROM THE FOUR NEW STAGES

### pin — the strongest signal this project has produced, and it is marginal

    tau <= 20s
      floor 0.3c   n=362   MDE 1.69c   claimed +2.51c   REALISED +1.70c  t=+3.0
      floor 0.5c   n=316   MDE 2.27c   claimed +3.81c   REALISED +2.29c  t=+3.0
      floor 1.0c   n=240   MDE 3.47c   claimed +6.54c   REALISED +2.87c  t=+2.5
      floor 2.0c   n=151   MDE 6.00c   claimed +12.01c  REALISED +4.73c  t=+2.4
    tau <= 60s: +0.23 / +0.04 / -0.49 / -0.52c, all t < 1. NOTHING.

The mid-null tops out at +0.32c and the realised is +1.70c, so it beats the
market-is-right null. **And the effect lives ONLY at tau <= 20s**, which is
what the settlement arithmetic predicts: at tau=20 forty of the sixty prints
are locked, at tau=60 none are. A result that appears exactly where the theory
says it must is worth more than the same t-stat appearing anywhere.

Two things keep it honest. Realised sits AT the MDE (1.70 vs 1.69) — the
smallest effect this sample could certify. And every cell is flagged **BELOW
the fair band**: claimed +2.51c against realised +1.70c, worsening to +12.01c
against +4.73c at the 2c floor. The bias grows with the size of the
disagreement, which is the signature of selecting on OUR error rather than the
market's.

So `pin.py` now walks forward: sigma is recalibrated on closes strictly
earlier than the one being traded, by matching the model's stated confidence
to the rate the stated side actually won. Self-tested against a model fed a
sigma 4x too small — the fit recovers **k = 4.14** and cuts the total damage
from -257c to -82c, while leaving a correctly-specified model at k = 1.07 with
its harvest intact.

### informed — making may not be dead, and that is a correction

`maker.py` measured the resting side's markout at 1s/5s/30s (0.612/0.624/
0.657c), compared it to a 0.5c capture, and this file recorded market-making
as closed. `informed.py` measured the SAME quantity **to settlement** and got
**+0.38c** — against a trade-weighted half-spread of 0.63c, that is
**+0.25c per fill, positive**.

    ALL      mkS +0.38c (t=6.5)   follow -1.12c (t=-20.1)   maker +0.35c (t=6.2)
    spread >=5c                                             maker +0.96c (t=5.4)
    shufS ~0 everywhere (max |t| 2.1) -- the random-sign control is clean

Both numbers cannot be the maker's cost. Either impact peaks near 30s and
decays by settlement — in which case **a maker who holds to expiry never pays
the peak, and maker.py measured an exit nobody is forced to take** — or one of
the two is wrong. `informed.py` now prints the full curve (1s/5s/30s/120s/
300s/settlement) with the maker's net at each, so the next run settles it by
measurement. The half-spread on that table is derived, not assumed:
maker = half - mkS holds exactly by construction.

**Do not act on this yet.** It is a horizon distinction that could still be an
artefact, and it needs the curve before anything is rewritten.

### informed — the two pre-registered cells both fail

* TAIL (follow the informed tail): follow **+0.01c, t=0.1**. Dead.
* HEADLINE (quote where spreads are wide): mkS **rises** with spread —
  0.27c at 1c, 3.11c at >=5c. Wide spreads mean MORE informed takers, not
  fewer. The adversarial panel predicted exactly this and it is confirmed.

### strikes — undefined, not negative

7,907 events scanned, **every one a single strike**. These contracts carry one
strike per window (strike(N+1) == settle(N)), so there is no second leg to
cross against. Cross-strike arbitrage is not mispriced here — the question
does not exist for this product. It WOULD exist for the Coin Race
(KXCRYPTOLEAD15M), whose legs must sum to 100c. The stage now says so rather
than printing a bare zero.

### Coin Race recording is LIVE

`KXCRYPTOLEAD15M` is arriving: 1,071 quotes, 144 trades, 2,422 book updates in
one hour. `KXCRYPTOCOMP15M` is NOT — along with the long-standing ADA, BCH and
TON. The ticker is wrong or the series does not exist under that name.

---

## 2026-09-04 — WHAT IS ACTUALLY OPTIMISTIC, AND WHAT IT WOULD PAY

One cell on disk beats its own market-is-right null. `RESULTS_endgame.md`,
settlement P&L, tau <= 60s:

    trades 705   claimed 1.87c   REALISED +0.86c   t 1.33   MDE 1.93c
    market-right null [-2.26, +0.57]c

**+0.86c sits above the null's top of +0.57c.** Every other strategy cell in
this project sits inside or below its null. This one does not — it is the only
positive signal that survived contact with the right null.

It is NOT proven and must not be reported as such: t = 1.33, and the MDE of
1.93c is larger than the effect, so this sample could never have certified
0.86c whether it was real or not. Underpowered is not the same as refuted, and
this is the one place the distinction matters.

`pin.py` is the tighter filter on exactly this region: only seconds where the
locked prints put fair beyond 0.98 (or below 0.02) and a quote is still on the
wrong side. If the endgame edge is real it should CONCENTRATE there, which
raises the effect against the same noise.

### The money, if it holds

Contracts pay $1, so 1c = $0.01/contract. Measured: 80 closes/day, 13.4
strikes per close, depth 55 at the touch (28/55/124 quartiles).

    floor    one trade/close, 40 lots, 0.86c    $24/day     $8.9k/yr
    central  3 strikes/close,  50 lots, 1.5c    $180/day    $66k/yr
    high     5 strikes/close,  50 lots, 3.0c    $598/day    $218k/yr

**The binding constraint is depth, not edge.** 55 contracts at the touch is
$55 of book. This strategy cannot be scaled by betting bigger; only by
covering more strikes and more closes. Any plan that assumes size is wrong
about this market.

---

## 2026-09-03 (evening) — BOTH structural strategies are now closed

On the full tape: 5,947,458 market-seconds, 7,176 markets, **798 close-time
clusters**. Forty-eight times the previous sample.

### Taking on order flow: real, and ~100x too small

| horizon | slope | t |
|---|---|---|
| k = 1s | +0.0000c | **+47.33** |
| k = 5s | +0.0000c | +37.12 |
| k = 30s | +0.0000c | +18.11 |
| k = 60s | +0.0000c | +11.62 |

Controls are now clean at full power: **placebo** t = −0.41 / +0.13 / +0.77,
all inside their MDE; **backward** t = +82.5. And the money block:

    k = 1s / 5s / 10s / 30s   ZERO trades cleared the cost of crossing

Median spread is **1 cent** — the minimum tick in the 10-90c band. There is no
room to quote inside it, and a forecast worth hundredths of a cent cannot pay
it. **Closed.**

### Making the spread: adverse selection eats it, in every bucket

`maker.py` completed for the first time (it had timed out at 3600s twice) and
delivered the number the whole maker question rests on. 27,760,728 trades,
77 million markouts, 798 clusters.

    horizon   signed markout       t         p    net @0.5c
         1s           0.612c    54.4    0.0000     -0.112c
         5s           0.624c    52.0    0.0000     -0.124c
        30s           0.657c    40.6    0.0000     -0.157c

The random-sign control reads −0.000c (t = −0.2), so this is **direction, not
volatility** — the trap that once made a zero-adverse-selection tape fire at
t = +11.

Per price bucket, capture against need:

| price | fills | markout (need) | capture | net | |
|---|---|---|---|---|---|
| 0-8c | 3,990,931 | 0.436c | 0.050c | −0.386c | loses |
| 8-16c | 1,940,005 | 1.018c | 0.500c | −0.518c | loses |
| 16-30c | 3,101,529 | 1.141c | 0.500c | −0.641c | loses |
| 30-70c | 9,850,731 | 0.856c | 0.500c | −0.356c | loses |
| 70-84c | 2,961,810 | 1.250c | 0.500c | −0.750c | loses |
| 84-92c | 1,768,775 | 1.131c | 0.500c | −0.631c | loses |
| 92-100c | 3,655,710 | 0.529c | 0.050c | −0.479c | loses |

Every bucket, by a wide margin, on millions of fills. **Closed.**

That is eight ideas dead: delta-hedging, "every game starts at 50c",
opening-value, lead-lag stale quotes, endgame, calibration/volatility, taker
order flow, and making the spread.

### The book, measured properly at last

    spread, cents                 1 /  1 /  2      (25th / median / 75th)
    contracts AT the touch       28 / 55 / 124
    contracts within 3 cents     76 / 124 / 216

### Still not clean: the book is replayed out of order

92% of rows had to fall back to the ticker channel, and where the rebuilt book
was valid it agreed with the ticker channel on only **81-85%** of comparisons.
The per-day diagnostic named the cause: 426-712 "gaps" a day with a **median
gap size of 1**, plus 74-198 "restarts" — the signature of a single adjacent
pair swapped.

`_rx_ms` is a millisecond stamp and the merge breaks ties by channel
directory, so messages sharing a millisecond arrive in alphabetical order of
channel rather than the order Kalshi sent them. `Book.apply` deletes a level
whose size reaches zero, so a subtraction applied before its matching addition
destroys that level permanently.

Fixed with a bounded reorder buffer keyed on seq. Measured on the fixture with
the buffer disabled: **27,650 false gaps, 13,825 false restarts, and 34,744 of
34,838 rows falling back to the ticker channel** — the real-data signature
exactly. With it: byte-identical output to the cleanly ordered feed.

This does not revive either dead idea (the placebo is clean and the money
block is empty by two orders of magnitude), but it is what a trustworthy book
requires, and C2 — queue position — is the only maker idea left standing and
needs one.

---

## 2026-09-03 — order flow predicts. It is ~100x too small to pay a spread.

First real answer from `flow.py`, on 124,378 market-seconds over 1,430 markets
and 323 close-time clusters. **This is 3% of the tape** — see the data-loss note
below — so every number here is provisional on power, not on method.

### The measurement

| horizon | slope (c per contract of OFI) | t | MDE | |
|---|---|---|---|---|
| k = 1s | +0.0000 | **+3.96** | 0.0000 | beats MDE |
| k = 2s | +0.0000 | **+3.39** | 0.0000 | beats MDE |
| k = 5s | +0.0001 | **+3.65** | 0.0000 | beats MDE |
| k = 10s | +0.0001 | **+2.52** | 0.0001 | beats MDE |
| k = 30s | +0.0003 | **+3.60** | 0.0002 | beats MDE |
| k = 60s | +0.0005 | +1.88 | 0.0006 | inside MDE |

The controls behave. **Backward** (the move that has already finished) reads
t = +12.99 / +9.76 / +3.45 at k = 1/5/30 — flow follows price mechanically, so
an instrument that could not find that would make the forward zeros
meaningless. **Placebo** (real flow against a moment 300s away in the same
market) reads t = −1.16 / −1.71 / +0.47; the middle one is marginally outside
its MDE with the wrong sign, which is one marginal cell in three looks.

**So order flow does carry information about the next move.** That is a real
fact about the book and it is the first positive result in this project.

### And it is worth nothing to a taker

    k =  1s   trained slope +0.0000c, only 0 trades cleared the cost of crossing
    k =  5s   trained slope +0.0001c, only 0 trades cleared the cost of crossing
    k = 10s   trained slope +0.0001c, only 0 trades cleared the cost of crossing
    k = 30s   trained slope +0.0005c, only 6 trades cleared the cost of crossing

Median spread is **2c**, plus a quadratic fee at both ends. A one-standard-
deviation burst of order flow predicts hundredths of a cent. **The signal is
roughly two orders of magnitude smaller than the cost of acting on it.** Taker
order-flow trading is dead, and no amount of extra tape changes that — more
data measures the same tiny number more precisely.

Seven ideas are now closed: delta-hedging, market-making (on the old depth
number), opening-value, lead-lag stale quotes, endgame, calibration, and taker
order flow.

### The book, from the websocket, on 124,378 market-seconds

    spread, cents                     1 /   2 /   6      (25th / median / 75th)
    contracts AT the touch           22 /  42 /  83
    contracts within 3 cents         75 / 123 / 214

`book.py` independently reads **65 contracts** median at the bid off the
`ticker` channel over 5.9M quote-seconds. Two different channels, two different
code paths, same order of magnitude — and both an order of magnitude away from
PLAN sec.4's mis-parsed 3,767. That correction was already known; this is the
first time it has been confirmed from the reconstructed book.

**This is where the project should go next.** Makers pay no fee, earn the
spread rather than paying it, and the queue in front of them is tens of
contracts rather than thousands. The one thing that kills a maker is adverse
selection — filled precisely when wrong — and a signal far too small to pay 2c
of spread is not too small to decide when to pull a resting quote. `maker.py`
has now timed out at 3600s on two consecutive runs and its verdict has not
printed; a fill model built on the reconstructed book (queue position, size
ahead, drain rate) is the missing instrument.

### The data loss, and its third form

The run kept 3% of the tape. Every day printed one subscription, ~460 forward
seq jumps, ~800 books invalidated, and 55 of 62 million deltas dropped onto
invalid books.

The collector subscribes `orderbook_delta`, `trade` and `ticker` in a **single
subscribe call**, so Kalshi numbers all three under one sid with one counter.
Reading `seq` off the orderbook messages alone reads every ticker and trade in
between as a hole, and a hole invalidates every book under the sid — with one
sid, that is every market at once.

**This is the third form of the same mistake in this one file**: the first
version did sequence bookkeeping after filtering by ticker, the second after
filtering by channel. Sequence bookkeeping must precede *every* filter.

The mine now reads all four channels, and uses `ticker` to re-anchor top of
book after a genuine gap instead of going dark until the next snapshot. It also
reports, per day and on real data, how often the book replayed from 400 million
deltas agrees with the top of book the ticker channel hands over whole.

---

## 2026-09-02 — a new question: does the ORDER FLOW know?

The volatility thread is closed. calfit puts `a` at 1.01–1.17 across seven taus
with six of seven CIs containing 1; reconcile, restricted to the quoted span,
agrees; the walk-forward is inside its MDE at every horizon and negative in six
of eight series. **The price is not wrong in any way this project has been able
to measure**, and that is now six dead ideas plus volatility: delta-hedging,
market-making, opening-value, lead-lag stale quotes, endgame, and calibration.

Every one of those asked the same question — *is the price wrong*. There is one
more question the tape can answer and it has never been asked.

### `research/flow.py` — the largest thing on disk, finally read

`orderbook_delta` is **395,685,479 messages, ~3.6 GB, about twenty times the
rest of the tape put together**, and effectively untouched. `book.py` reaches it
but holds every message in RAM to sort by sequence, measured at ~30 GB against a
16 GB machine, so the depth number the project actually uses comes from
`depth_from_ticker` — a shortcut over the small `ticker` channel.

It never needed the sort. Within one collector file the messages are already in
arrival order, so a k-way merge across files yields a globally time-ordered
stream in memory proportional to the **number of files**, not the number of
messages. Book state is proportional to the markets alive at once, which for
15-minute contracts is a handful. Measured at **~116,000 messages/second**:
about an hour for the whole tape, cached one file per day, so every run after
the first takes seconds.

The question:

    x   order flow imbalance over second t (Cont-Kukanov-Stoikov, level 1)
    y   the mid change from the end of t to the end of t+k

`x` is complete before `y` begins. The split is at a **second boundary, not a
message boundary** — message-level overlap is the single easiest way to
manufacture this exact result.

What it enforces, all of it checked by the self-test rather than asserted in a
comment:

* the grid is **exogenous** — every second in the window is emitted, message or
  not, so the sample is not built out of exactly the moments the answer is
  about. Forward-fill is bounded by a global clock, so a dead collector cannot
  read as a calm market.
* cluster-robust on close time, `G` = closes, and the **MDE printed before the
  estimate**.
* a **time-shifted placebo**: real flow against a moment 300s away in the same
  market. Must read zero.
* a **backward check** that must be large. A forward zero from an estimator
  never shown capable of finding anything is not a result.
* **money, out of sample**: slope fitted on the first half of the tape, traded
  on the second, paying the full spread and the quadratic fee at both ends.

It also re-measures, from the websocket stream, the resting-depth number
PLAN sec.4 used to kill market-making — which came from a REST endpoint RUNBOOK
separately records as returning levels ascending and truncating from the bottom.

**Nothing has been run against real data yet.** Two fixture bugs were found and
fixed getting the self-test to pass, both recorded as BIASES.md pattern 18, and
one real bug fell out of them: sequence bookkeeping sat after the ticker filter,
so skipping tickers we have no settlement for would have read holes in our
sample as holes in Kalshi's stream and invalidated every book we hold.

---

## 2026-09-01 — the volatility question, mostly answered

Three days of instrument-building produced an answer, and it is close to "the
market is right".

### calfit: one parameter for the whole calibration curve

P(win) = Phi(a * Phi^-1(price)), fitted by maximum likelihood over every settled
market. a = 1 is calibrated. It is not an arbitrary curve — a is exactly
sigma_implied/sigma_true, so **a = 1/r**, the same parameter reconcile.py gets
from settlement dispersion by an unrelated route.

| tau | a | 95% CI | t vs 1 |
|---|---|---|---|
| 120s | 1.0122 | [0.938, 1.086] | 0.32 |
| 240s | 1.0233 | [0.950, 1.097] | 0.62 |
| 360s | 1.0736 | [0.996, 1.152] | 1.85 |
| 480s | 1.0832 | [0.988, 1.178] | 1.72 |
| 600s | 1.0018 | [0.898, 1.105] | 0.03 |
| 720s | 1.1710 | [1.034, 1.307] | 2.46 |
| 840s | 1.1543 | [0.937, 1.372] | 1.39 |

**Six of seven CIs contain 1.** The one that does not is a single cell of seven
looks, where a family-wise 5% needs |t| > 2.69. Every point estimate is above 1,
but the taus overlap heavily so that is not seven independent votes.

### reconcile was comparing two different periods

Widening the settlement fetch to 10,798 markets collapsed every ratio — BNB
0.715 → 0.524, XRP 0.810 → 0.481. A market underpricing volatility two to one
over 580 closes is not a finding, it is a mismatch: the numerator (implied RMS)
could only be measured over the ~164 recorded hours while the denominator drew
on 1,198 settlements spanning ~300 hours. **Volatility clusters**, so a
denominator from a different stretch of tape is a different number.

Restricted to the quoted span, the two instruments broadly agree:

| series | reconcile r | calfit 1/a |
|---|---|---|
| BTC | 0.967 | 0.970 |
| NEAR | 0.964 | 0.961 |
| DOGE | 0.856 | 0.990 |
| ETH | 0.814 | 0.937 |
| BNB | 0.806 | 0.888 |

**r ≈ 0.85–0.97.** Implied volatility perhaps 3–15% under settlement dispersion.
Small, possibly real, at the edge of what ~170 hours of tape resolves.

### calib's rotation faded under more data

The finding that survived everything else — outcomes more extreme than prices —
largely evaporated when the settlements tripled: 20c from −3.5c to −1.9c, 90c
from +4.5c to +0.5c, every bucket now under |t| = 1.5. **That is what a
small-sample artefact looks like when the sample grows.**

### patterntrade could not have answered either way

−1.04c at 583 clusters, inside its null — but its MDE is 5.7c against a 3–5c
effect. One trade per market at a 46c per-trade sd is an expensive way to ask.
Not a refutation; a statement that the instrument was the wrong shape.

### oos.py — the only test here that is not in-sample

Everything above describes the whole tape at once. `oos` walks closes in time
order, fits `a` on markets that settled **strictly before** each close, trades
that close off it, and settles. Its self-test proves the absence of look-ahead
rather than asserting it: `a` jumps 0.80 → 1.30 mid-fixture and the fit must
LAG it (0.834 → 0.905 across the jump, reaching 1.301 only 280 closes later).
Nothing that peeks can lag. MDE 2.34c at 460 closes.

### Where this leaves the project

The measurement problem is solved; the question is now simply whether anything
is there. **The binding constraint is the length of the quote tape**, not the
analysis — `oos` prints how many more closes each edge size would need.

If `oos` ties its market-is-right null, the volatility thread is finished and
the next direction is `orderbook_delta`: **395 million messages**, by far the
largest dataset here and essentially unmined — `book` currently runs in under a
minute off the cheap ticker-derived path.

---

## 2026-08-29 — RETRACTIONS. Read this before any number below it.

A seven-lens adversarial audit of the code written on 28 August claimed 43
defects; 16 survived three independent refuters each, 8 of them critical. Two
of those invalidate results published in the section below and reported to the
operator. **The retractions come first because the wrong numbers were stated
with confidence and travelled.**

### RETRACTED: endgame's real-data P&L (−21c to −39c, t = −4.2 to −7.8)

It measured nothing.

    won = 1.0 if b["settle"] else 0.0

`kalshi_fulltape.py` writes `settle` as the **settled index LEVEL** (~79,500)
and the outcome as `result`, guarded so `settle` is never zero. That truthiness
test returned 1.0 for **every market on the tape**: every yes-side trade booked
a win, every no-side trade booked a loss, and the realised column was a pure
function of the yes/no trade mix.

I used that number to argue the project's σ chain was confidently wrong. **That
argument is withdrawn.** The σ-vs-outcome contradiction below stands on calib
alone until endgame is re-run.

No test could see it: endgame's fixture wrote `"settle": settle > strike`, a
bool — the only fixture in the repo that disagreed with the collector's schema.
`replay.py` and `edge.py` both write it as a price with a separate `result`.
Fixed with `outcome_of()`, a `sane_or_die()` YES-rate gate, a fixture on the
collector's schema, and a self-test that fails if the broken reading and the
correct one ever agree again.

### RETRACTED: term.py's term structure (free power law +0.111, t = 8.41)

Indistinguishable from an artefact of term.py's own staleness tolerance.

`STALE_TOL = 0.02` was only ever exercised against a fixture emitting a quote
every 3 seconds, so every row it had ever seen was 0–2s old. On the same
**exact-model** book — true β exactly zero — with quotes 20s apart:

| spacing | β on sqrt(τ) | β on free power law |
|---|---|---|
| 3s | −0.003 (t=−0.95) | +0.001 (t=+0.46) |
| 10s | −0.156 (t=−4.76) | +0.032 (t=+3.44) |
| 20s | −0.487 (t=−7.74) | **+0.119 (t=+7.70)** |

Against the tape's reported **+0.111 (t=8.41)**. Setting the tolerance to zero
returned 0.0000, so the admitted staleness was the entire effect.

Fixed at the source, not with a tighter bound: `implied.collect()` now inverts
every carried-forward quote at the second it was **issued**. That removes the
bias exactly and keeps *more* data than a zero tolerance did. Verified 0.0000
at 3s, 10s and 20s spacing.

**The claim "the market is not making a variance-formula error" is therefore
unproven, not disproven.** It must be re-measured.

### SUSPECT: surface's "best reachable cell, 4–6c at +1.24c"

`availability()` medianed the spread over raw **messages**. The ticker channel
is publish-on-change, so a tight book republishes far more often than a wide
one and the median is dragged toward the tightest book in the bucket — the
occupation-time bias that `implied.collect()` was fixed for the same week,
reappearing in a new file. On a two-market fixture it flipped the sign of a
bucket's net. Now an exogenous one-quote-per-second grid plus a per-market
column. **Re-run before quoting.**

### The other five criticals

- `endgame.redraw_null` resettled from the **model's own** fair value, so its
  mean is the claimed edge by construction — and it was printed as "null" with
  main() reading a result inside it as "nothing here". Inside that band means
  the model is **right**. Now two bands, labelled: a market-right null and a
  model band.
- `surface.kelly()` omitted the taker fee, printing a **positive stake** on
  rows its own NET column declared unprofitable.
- `go.py`'s cfbenchmarks_value EMPTY marker required the word "data" after the
  feed name. Zero of the seven messages stages actually print matched it, so
  five stages could report `ok` on an index feed delivering nothing.
- `go.py` flagged **every successful endgame run** EMPTY, because one sentence
  of prose contained "no quotes". `markers.py` now enforces the rule that
  separates the real case from the accident.
- `run_when_away.ps1`'s HEAD-vs-origin gate passed when **both** sides were
  `$null` — exactly when git is broken and provenance is unknowable.

### What this run taught that outlives the individual bugs

**Every one of these was invisible to the self-tests, and each for the same
structural reason: the fixture and the real world differed in one detail the
fixture's author chose.** A bool where the collector writes a float. A 3-second
quote spacing where the channel is publish-on-change. A message stream where
the sampling is per-second. Pattern 15 in `BIASES.md` was written about Python
versions; it is much wider than that. **A fixture is a claim about reality, and
an untested claim about reality is exactly what this project exists to
distrust.**

The one number that survived the audit untouched is calib's grid column, and
that is not a coincidence: it makes no model assumption at all. It counts.

---

## 2026-08-28 (evening) — a whole run lost to a filename

The 17:26 run produced nothing. Fourteen of sixteen stages died on the same
line:

```
File "research/replay.py", line 47, in <module>
    import gzip
File "C:\Python314\Lib\gzip.py", line 16, in <module>
    from compression._common import _streams
ModuleNotFoundError: No module named 'compression._common'; 'compression' is not a package
```

**Python 3.14 added a stdlib package called `compression`.** The repo had a
`research/compression.py` (added in `6f6ac20`, after the last run that worked),
and every stage puts `research/` first on `sys.path`, so `import gzip` found
ours. Renamed to `research/patterntrade.py`.

**Read this part, not the fix.** Four separate things had to be true, and each
one is a lesson that outlives this bug:

1. **It was invisible on the machine the code is written on.** That container
   runs Python 3.11, where `gzip` imports `_compression` (underscore) and
   `compression` is not in `sys.stdlib_module_names` at all. Every self-test
   passed. The development environment differing from the run environment is
   now a known, named risk in this project.
2. **The self-tests structurally could not see it.** They import their own
   modules and never `gzip`. Only stages that load real data import `gzip`, and
   those are exactly the stages that get skipped when there is no data — so the
   gate is blind to the whole class by construction.
3. **The gate never ran.** `run_when_away.ps1` drives stages one at a time with
   `--only`, and `--only` skips self-tests by design.
4. **It looked like sixteen separate failures.** An environment bug does not
   present as one bug; it presents as everything being broken at once, which is
   the hardest shape to diagnose from a results file.

Guards added:

- **`research/shadow.py`.** Deliberately does *not* rely on a stdlib name list,
  because a name check against the *running* interpreter is exactly the check
  that would have passed here. It (a) puts `research/` first on `sys.path` as
  every stage does, imports every stdlib module the repo names, and checks each
  resolves outside the repo — which catches transitive shadows like
  `gzip → compression` where the shadowed name never appears in our source; and
  (b) carries an explicit list of names that are stdlib in Pythons *newer* than
  the one running, so a 3.11 container flags a file that will only break on
  3.14. Its self-test asserts that exact case. A `ModuleNotFoundError` naming
  the module *itself* is a platform difference (`winreg` on Linux), not a
  shadow — a real shadow reports a *different* name, as `compression._common`
  did.
- **`go.py` PREFLIGHT**, which runs even under `--only` and stops the run before
  any stage. Environment bugs belong in front of the fast path.

Nothing was lost but the evening: the recorder is independent and kept running
throughout.

---

## 2026-08-28 (later) — endgame repaired, and a rule written down before the number

Three things landed after the audit. Nothing here has touched real data yet;
all of it is arithmetic and fixtures.

### 1. `endgame.py` part 2 was broken by its own fixture, in two ways

It had been failing since it was written, and the estimator was never at fault.

- `strike = settle + gauss(0, 3.0)` drew the strike from the **future**
  settlement value, so `settle - strike` was independent of everything knowable
  at decision time and the true probability of every market was 50%. Measured
  directly: rows the model priced at 0.041 won **27.4%** of the time; rows it
  priced at 0.959 won **76%**. A book on `sqrt(tau)` — pulled toward 50c by a
  sigma 9.7x too large — was therefore *closer to the truth* than the exact
  model, and fading it correctly lost 22.6c.
- Each window reset `px = S0` and wrote ticks over `[close-900, close]`, and
  `close(w) - 900 == close(w-1)`, so every window **clobbered the previous
  window's final settlement print** with a value ~180 dollars away. `settle`
  was computed before the clobber; `fair()` read after it.

Repaired (one continuous tape, `strike(N+1) == settle(N)`), it is silent
against a correctly-priced book at every tau cap and finds a `sqrt(tau)` book
at **+7.9c (t=4.9)** inside 60s rising to **+12.1c (t=6.4)** inside 15s — with
**claimed edge matching realised P&L inside a standard error in every cell**.
That agreement is the assertion. Detection alone is cheap.

Two results worth keeping from the repair:

- A book on `sqrt(tau-39.5)` is **invisible**, and not because the estimator is
  weak: that approximation collapses below ~40s, driving its own quotes outside
  the range the exchange can quote. Its error region censors itself.
- **A pooled sigma manufactures edge.** Book quotes each window's own true
  sigma, scan uses one pooled sigma per series — true edge exactly zero,
  claimed **+2.5c**, realised **−4.2c**, stable across seeds. `endgame.main()`
  now prices each market off its own pre-endgame path. *Every other stage in
  this project pools.*

### 2. `term.py` — the first vol measurement immune to our own sigma estimator

Every other vol result here is a **level**: implied over a realised sigma we
estimated, so any bias in our estimator lands in the answer. This measures a
**shape** within a single market against itself. Invert every quote through the
exact `var_factor`: a market using the same formula is **flat in tau**, whatever
it believes. `sqrt(tau)` makes implied sigma explode into the close (9.7x at
tau=10); `sqrt(tau-39.5)` makes it collapse below 40s.

Self-test recovers a planted `sqrt(tau)` book at **beta = 0.998 [0.994, 1.001]**
and `sqrt(tau-39.5)` at 1.039 [0.982, 1.096], reads flat on a flat book
(beta = -0.000), and separates a
genuine rising-vol *view* from an arithmetic *error* by the **pair** of betas
(a sqrt(tau) book reads 0.998/−0.580; a 40% rising-vol view reads 0.119/−0.157).

**It found a real bias in `implied.collect` on the way.** The 30-second
carry-forward inverts a stale quote through a `var_factor` that has since
collapsed: sd/sigma falls from 0.893 at tau=20 to 0.327 at tau=10, so a
30s-old quote at tau=10 returns **7.58x** the sigma the quoter used — a
rising-into-the-close bias with exactly the shape of the signature term.py
looks for. On a fixture whose truth is flat, 2s of allowed staleness alone gives
beta = **+0.062 at t = 6.0**. `collect()` now carries the quote's age; term.py
drops any quote whose sd(tau) has moved >2% since it was posted, and reads
0.000. **The level results in implied.py are biased UP by this, which makes
every ratio it reports conservative against the finding that the ratio is
below 1.**

### 3. `surface.py` — the map from the finding to a trade, written down first

The project had a candidate (implied/true sigma = 0.895) and no answer to
"which contract, at what price, for how much". That needs no data.

If the market's sigma is too low its prices are too **confident**, so the cheap
side is always the one below 50c. A market quoting mid `m` believes
`z_m = Phi^-1(m)`, the true z is `z_m * r`, and true fair is `Phi(z_m * r)`.
**The var_factor cancels, so the edge does not depend on tau at all.** Only the
cost depends on price: the quadratic fee peaks at 50c, and the tick is tapered
(0.1c below 10c, 1c above).

At r = 0.895:

| mid | gross | cost | NET | break-even r |
|---|---|---|---|---|
| 5c | 2.05c | 0.39c | **+1.66c** | 0.978 |
| 7c | 2.33c | 0.51c | **+1.82c** | 0.975 |
| 10c | 2.57c | 1.16c | +1.41c | 0.951 |
| 16c | 2.67c | 1.46c | +1.21c | 0.941 |
| 30c | 1.94c | 1.98c | −0.04c | 0.893 |
| 50c | 0.00c | 2.25c | −2.25c | never |

Positive below ~30c, negative above, best at 7c. There is a **structural cliff
at 10c**: the TICK goes 0.1c → 1c in one step. The cost of crossing goes
0.51c → 1.16c, which is 2.28x rather than 10x — the quadratic fee dominates
below 10c and moves smoothly — while the gross edge barely moves at all. Below 10c the market only has to be wrong
about sigma by **1.8–2.5%** for the trade to pay; at 30c it must be wrong by
10.7%; at 50c no error is ever enough. **Fourth independent line pointing away
from 50c.**

Verified not against itself but against a settled simulation — real 900s tape,
real 60-print settlement, market quoting `r × sigma`, one trade per window held
to expiry. Analytic vs simulated agrees to |t| ≤ 1.2 across four cells while
mean tau moves from 342s to 825s, which is the tau-cancellation tested rather
than asserted. The `r = 0.999` row correctly **loses** 1.5c: a market that is
right must cost you the spread and the fee.

**The map assumes a one-tick book, which is a floor and not a measurement**, and
that assumption does most of the work below 10c. `surface.py --data` re-costs
every cell with the observed median spread per bucket, with quote-seconds and
distinct markets beside it. **Read that table, not the map, wherever it has
data.** If the wings are quoted 1c wide, the taper buys nothing; if they are not
quoted at all, the best cells do not exist.

### What this changes about what to do next

The order of operations is now: `surface` (no data) says where to look,
`term` says whether the market's error is a formula or a view, `endgame` prices
the formula case, and `implied`/`reconcile` say whether r is below 1 at all —
on **fresh** data. All four are in `run_when_away.ps1`.

---

## AUDIT OF 2026-08-28 — every estimator vs the 14-pattern bias catalogue

A 51-agent audit read all twelve estimator modules against the fourteen bias
patterns this project has actually shipped, then adversarially verified every
claim. 39 claimed → 15 survived: 4 critical, 9 material, 2 cosmetic. ALL are
now fixed (see the commit trail of 2026-08-28). The ones that changed
conclusions:

- **implied.py sampled implied vol at QUOTE times** (occupation-time): quote
  intensity rises with vol, so every implied/realised ratio was biased UP —
  the vol-underpricing candidate is STRONGER than published. Now an exogenous
  per-second grid.
- **implied.py's inversion deleted only the negative half** of a symmetric
  error (`sd <= 0 → None`), manufacturing the 45–55c "frown" (1.166 row) out
  of a flat surface. The inversion now returns the SIGNED estimate; medians
  are unbiased; downstream consumers guard against rare nonpositive medians.
- **pathstats weighted clusters 1/K where K counts FUTURE gridpoints** —
  −1.46c of fake reversion from an exact martingale. Pooled mean +
  cluster-robust SE now. Every previously published pathstats table is void.
- **edge.py scored the model at the gridpoint against a trade print up to
  60s stale** — a proper scoring rule pays the fresher forecast by
  construction (fixture: t=13, +7.55c for 20s). Market side now reads the
  BOOK MID at the same second.
- **feeds.py's imbalance predictor was read up to ~1s INSIDE its own
  prediction window** (last-write-wins bucketing) — the h=1 row was largely
  contemporaneous. Predictor is now the prior second's state.
- **proxy.py regressed every asset's markets on BTC-only candidates**
  (attenuation → false negatives) and tested against a zero null when any
  sub-second quote lag makes the honest-maker null NEGATIVE. Now BTC-only
  markets + an explicit delta-confound control row that candidates must beat.
- **cross.py counted each market five times** (one per ttc), used iid SEs on
  clustered closes, and priced markets with FULL-SAMPLE index variance
  (look-ahead). One obs per close, moving-block SE, causal prefix-sum g0.
  Its "clean null" stands a fortiori (its t's shrink).

The catalogue self-audit also matters: calib.py — excluded from the audit as
"written this week" — carried pattern 8 (cluster by close, not market),
caught separately the same day. Exclusions are where bugs live.

STATUS OF THE ONE LIVE CANDIDATE: implied/settle-sigma = 0.895 median over
the full 399-window recording, four series' CIs exclude 1 (BNB 0.725, DOGE
0.754, XRP 0.820, SOL 0.842). The occupation-time fix moves these DOWN
(stronger). Standard before trading: the same measurement, below 1, on fresh
data the finding has never seen. The recorder is collecting that data now.


Everything needed to continue is in this repo. Nothing lives only in a chat.
Read this file, then `STATUS.md`, then `PLAN_V3.md`. `RUN_WHEN_HOME.md` is the
operator's card.

- **Branch**: `claude/file-uploads-70rtjl` (this is also the remote default —
  a plain `git pull` gets it).
- **Head at handoff**: see `git log -1`. Run 2 findings are in the section below.
- **User's machine**: Windows 11, Python 3.14.6, repo `C:\kals-repo`, data
  `C:\kals` (`kalshi_data/`, `feed_data/`, `fulltape/`, `run_all.ps1`).
- **State**: 19 self-tests, all passing. One full real run completed
  2026-08-26 (203 min); its findings and its faults are below.

---

## THE MAKER QUESTION — PRICED, AND IT IS WORSE THAN IT LOOKED

Run 2 reopened market-making by replacing PLAN.md's mis-parsed "3,767
contracts resting" with a measured ~30. Makers genuinely pay no fee: all
sixteen fifteen-minute series are fee_type="quadratic" (the only
quadratic_with_maker_fees series anywhere are KXBTCMAX125/150). The tick is
1c, the liquid series quote 1c wide, ZEC 7c and NEAR 8c.

**A first pass compared the half-spread against per-second diffusion and
concluded the wings were viable (quote beyond 92.1c at 900s). That framing is
wrong and optimistic**, and `research/maker.py` now says so in its own
docstring. You are not run over by the average second; you are run over by the
seconds in which somebody chose to trade with you.

### The fee theorem
A rational taker crosses only when their estimate beats the touch by more than
the fee, so E[F | ask lifted] >= a + fee(p), and

    E[maker P&L per fill] <= a - (a + fee(p)) = -fee(p)

**and the bound is invariant to how wide you quote** — widening raises the
half-spread on both sides and it cancels. Against informed flow a maker loses
the TAKER's fee every fill: -1.75c at 50c, -0.63c at 90c, -0.33c at 95c.
Paying no maker fee is why anyone quotes at all; it is not an edge.

Independent confirmations of the same answer: a queue/diffusion argument (30
contracts ahead, a 1-tick ATM level lives ~541ms at tau=900 while only ~9.4
contracts of one-side flow arrive, so the modal outcome is the level moving
away and the fills that DO occur are informed bursts, E[drift|fill] ~ 1.55c,
net -1.05c); and the transaction-cost split (at 50c the maker captures
h/(h+fee) = 22% of what counterparties pay, Kalshi takes 78%).

### So the strategy reduces to ONE measurable number
Noise flow pays you the half-spread; informed flow costs you the fee.

    E[P&L per fill] = q*h - (1-q)*fee      break-even q = fee/(fee+h)

At 50c that is **78% of all flow must be uninformed**; at 90c, 56%. That is
not assumable — it is exactly the signed markout `maker.py` measures.

### Two fatal bugs in the first maker.py, both of which its self-test passed
1. The pre-trade mid was "last quote at or before t". Book updates share the
   trade's integer second constantly, so it read the POST-trade mid and
   attenuated a planted 1.000c to **0.000c**.
2. The headline compared |post-trade move| against |random-grid move| — a
   volatility test, not a direction test. Trades cluster in volatile seconds,
   so on a tape with provably ZERO directional information it fired at
   **t = +171**.

Both fixed; both now planted in the self-test. **The deeper lesson: the
self-test exercised the SIGNED path while main() reported the ABSOLUTE path.
Testing a different quantity than you report is indistinguishable from not
testing.**

### What a paper trade can and cannot do (measured, not argued)
At 185 close-time clusters the P&L minimum detectable effect is 2.64c at a 95c
price and **8.46c at 55c** — and making happens mid-book, so 8.46c is the
honest number. Confirming a 0.5c edge from settlement P&L needs ~6,550
clusters (68 days) at 95c and ~54,000 (564 days) at 55c. **For a maker, extra
fills buy ZERO additional power on settlement P&L**, because every fill in one
market settles on the same single outcome.

The alternative is not a longer paper trade but a different estimator: signed
post-fill markouts have per-fill sd 1.36-2.47c, cluster SE 0.028-0.094c, and
an MDE of **0.08-0.26c at 185 clusters — 30-100x more powerful** than replayed
P&L, against a target quantity of ~0.5c. That is the measurement to run.

### The 59.9% index coverage is NOT a 40% hole rate
It is ONE contiguous ~18.6-hour recorder outage (the PC crash) inside a
46.36-hour wall-clock span, plus ~2,000s of short transport interruptions.
Dedup is definitively excluded: replay's own parse counter (999,590) exactly
equals the sum of the ten per-index distinct-second counts, and the live rate
measures 1.000 Hz/index. The data that exists is dense and fine.

### implied.py's pooling bug is fixed
Five sites pooled raw sigmas across series spanning 1e6 in price. The "1.192x
variance risk premium" was 0.7839/0.0118, where 0.0118 is literally SOL's
realised sigma alone and BTC+ETH supply 97.6% of the numerator. Now pools
per-series ratios, with a self-test that plants three series priced 1,000,000x
apart carrying a common ratio and checks the price level does not leak.

---

## RUN 2 (2026-08-27 02:39, 154 min) — THE FIRST COMPLETE RUN

All 13 stages produced data. 46.4 hours recorded, 72.6M orderbook deltas
parsed (100% of them, against 0% in run 1). Findings, and what is still wrong:

- **The maker strategy's death sentence was based on a mis-parsed number.**
  PLAN.md sec.4 killed it on "best bid 0.40 with 3,767 contracts resting",
  from a REST call RUNBOOK separately records as mis-parsed. Measured from the
  websocket: **median depth at the touch is 30 contracts**, 32 at 40c, 20 at
  50c. That is 125x smaller and a joinable queue. **NOT YET CONFIRMED** — see
  the sid bug below; it was measured on 24 of 1,090 markets.
- **PLAN_V3's #1 ranked idea is refuted.** "Does the book follow the index?"
  — it does not. The book **leads** by one second: beta 0.530 at lag -1
  (t=29.4, 108 df) against -0.001 at lag +1 (p=0.37). Corroborated by feeds,
  where our own replica also lags the published index by 0-1s. There is no
  stale-quote edge available from watching the index. Most likely the CF index
  is timestamped ~1s behind the information the market already has.
- **Implied vs realised volatility, per series** (the only trustworthy cut):
  BTC 0.88, ETH 0.86, SOL 0.89, BNB 0.94, DOGE 0.94, ZEC 1.03, NEAR 1.02,
  XRP 1.10, HYPE 1.25. The liquid series price volatility BELOW realised —
  the opposite of a variance risk premium. **The report's headline "VARIANCE
  RISK PREMIUM 1.192x" and the 59x-141x "vs realised" columns in the term and
  smile tables are a POOLING ARTEFACT** — implied.py averages sigmas across
  series whose price levels differ by six orders of magnitude (BTC ~5.59
  $/sqrt(s), DOGE ~0.00002). It must pool the per-series RATIOS, not the raw
  sigmas. **Unfixed.**
- **Cross-sectional: a clean null.** All 9 series "in line", max |t| = 2.2
  (BTC absolute 0.62c). 509-533 clusters each.
- **Replay P&L: -13.20, null 95% [-657, +365], 73rd percentile.** Nothing.
- **Median spread is 1.00c** on the liquid series (ZEC 7c, NEAR 8c) —
  consistent with a flat 1-cent tick, so §8 item 1 leans that way.
- **Index coverage is 59.9% and flagged GAPPY** on every one of the ten
  indices: ~100,005 seconds present out of 166,896 in the span. Four in ten
  index prints are missing. This degrades every model-based test and is
  **undiagnosed** — is it the feed, the subscription, or the reader?

### Bugs found in run 2, fixed
- **`book.py` checked sequence continuity per TICKER.** The collector
  subscribes a LIST of market_tickers in one call, so Kalshi's `seq`
  increments per SUBSCRIPTION across every market in it. Consecutive deltas
  for one ticker jump by however many other markets spoke in between, so
  nearly every delta read as a gap: 74,343,133 deltas parsed, **24 of 1,090
  markets** rebuilt. Now keyed on `sid`, with a gap invalidating every book
  under that subscription. Self-test (8 markets interleaved on one sid)
  reproduces it: 8 of 328 states under the old logic, 328 of 328 under the
  new. **The depth figure above must be re-measured after this.**
- **`go.py`'s EMPTY flag matched bare substrings**, so `"1,090 markets"`
  matched `"0 markets"` and five stages that had each loaded ~710,000
  messages were labelled `EMPTY -- no data loaded`. A false EMPTY is worse
  than none: it buries a real result under the one label that says do not read
  this. Now boundary-anchored regexes.

### Operational note from the watchdog log
Recording is healthy (~76 MB/h kalshi, ~89 MB/h feeds). The size column looks
frozen for most of each hour and then jumps at :04 — that is Windows not
updating directory metadata until the hourly file closes, not a stall.
**But free disk swung 71.5 -> 36.5 -> 44.7 GB in five hours** while the data
directories grew ~100 MB/h. Something else on that machine is taking and
releasing tens of gigabytes. The watchdog halts below 5 GB.

---

## 0. THE ONE URGENT THING

**Both recorders are dead** and have been since 2026-08-26 (feed_data stopped
~03:59 UTC, kalshi_data ~05:41 UTC — they died when the user's PC crashed and
never came back). Recording time is the only thing in this project that cannot
be recovered later.

```powershell
powershell -ExecutionPolicy Bypass -File C:\kals\run_all.ps1
```

Restart just after the top of an hour (see §5, gzip trailers).

---

## 1. THE GOAL, VERBATIM

A bot that makes **consistent money on markets resolving every 30 minutes or
less**. The user's words: *"crypto, metal, anything as long as it's a market
that runs on 30 min intervals or less, doesn't have to be Kalshi, as long as a
strategy exists."* And: *"It doesn't have to be a Kalshi error that we try to
take advantage of… The prompt is just to make money."*

It **will run with real money**. The user has explicitly asked for wide,
aggressive idea generation, and has criticised narrow searching before:
*"Just because you can't think of something immediately doesn't mean it's not
there."*

### Hard rules (from RUNBOOK.md, non-negotiable)
1. **NEVER place, amend or cancel an order.** No `POST /portfolio/orders`,
   ever. There is no order code in this repo and none may be added.
2. **Never write, move or delete anything under `kalshi_data/` or
   `feed_data/`.** A collector is writing there and exchange feeds have no
   backfill.
3. Cluster by market/close-time, always. Report `n` as markets or clusters,
   never trades.
4. Never claim a result that was not measured.
5. Every estimator must be calibrated against a known answer before it touches
   real data.
6. Never infer a price's unit from a single observation's magnitude.

---

## 2. THE SETTLEMENT MODEL (established and verified)

Kalshi 15-min crypto binaries. Settlement = mean of the 60 discrete 1-second
CF Benchmarks index prints before close, compared to the same for the 60 prints
before open. Therefore:

- **`strike(N+1) == settle(N)` exactly.** Verified bit-for-bit in 19,471 of
  19,471 within-run consecutive pairs. (See §4 for what this does and does not
  prove.)
- `Var(settle − strike) = 880σ²` — MC-verified in `settlement_math.py`.
- Before the averaging window: `Var = σ²(τ − 39.50)`, τ = seconds to close.
  RUNBOOK's old `σ²(τ+20)` was wrong; at 120s it overstates vol by 32%.
- Inside the window: `Var = σ²·r(r+1)(2r+1)/21600`, r = ticks not yet locked.
  The continuous `σ²r³/10800` fails exactly where we would trade.
- Fair value: `Φ( ((locked_sum + r·spot)/60 − K) / sd )`. **One free
  parameter: σ.**
- `d(fair)/d(log σ) = −z·φ(z)`, maximised at **0.242**. A relative error ε in
  σ moves fair value by up to 0.242ε — this is the floor under every σ-based
  edge. A 33-second σ̂ carries 12.3% error = a **2.98¢ phantom edge**, and the
  engine built on it traded 18–28% of windows against a *provably fair* book
  and lost 3.7¢/contract.
- Fee: quadratic, `ceil(0.07·P·(1−P)·n)` — 0.33¢ at 95¢.
- **TICK SIZE IS UNRESOLVED AND MATTERS.** Code assumes a tapered grid (0.1¢
  below 10¢/above 90¢, 1¢ between). The API's `price_ranges` on market objects
  says **step = 0.01 on notional 1.0000, i.e. a flat 1-cent tick**. If the flat
  tick is right, every target edge under 1¢ is unactionable regardless of
  whether it exists. **Resolve this from the API before sizing anything.**

### The independent-unit result (the most important number in the project)
Twelve crypto series close **simultaneously** at ρ≈0.8, worth **1.22 effective
independent units**. So the independent observation is the **close time**, not
the market — **4 per hour**. 26 hours of recording = **104 clusters**, not
1,248 markets. Every earlier "n = 4,300 markets" overstated the sample ~12×.

Consequence, from `power.py`: the smallest P&L edge detectable from replayed
data is ~2.9¢ at 1 day, 1.5¢ at 7 days, 0.8¢ at 30 days. Tradeable edges here
are 0.5–2¢. **Replayed P&L cannot confirm a strategy at any recording length
you will have.** The deploy decision must rest on a per-second mechanism
(leadlag/feeds/proxy/pathstats get 3,600 obs/hour instead of 4).

---

## 3. THE FIRST REAL RUN (2026-08-26) — WHAT IT ACTUALLY SHOWED

The run completed, all six steps reported "ok", and **94% of recorded data was
never read**.

**Cause**: Kalshi emits its websocket fields with unit suffixes, as STRINGS —
`yes_bid_dollars`, `yes_ask_dollars`, `yes_bid_size_fp`, `yes_ask_size_fp` on
`ticker`; `price_dollars`, `delta_fp` on `orderbook_delta`. Loaders asked for
`yes_bid` / `price` / `delta` and got nothing.

- **68,976,084 of 68,976,084** orderbook deltas unparsed (2.0 GB).
- 7 stages loaded zero quotes (replay, leadlag, cross, openwindow, implied,
  pathstats, proxy); `book` loaded zero deltas. All exited 0.
- Fixed in `8af76b4`, with self-tests that reproduce the exact failure
  (`0 of 300 quotes`, `120 deltas unparsed`) when the fix is reverted.

**Eight independent verifiers recomputed the run from the raw cache.** The
arithmetic transcribed perfectly — ~340 printed cells all reproduce. Every
problem was in *what* was computed.

### THE ONE FINDING THAT SURVIVES

**Volatility clustering in 15-minute settlement returns.** `ac1` of `|r|` =
0.281–0.373 across the six series with adequate history (BTC 0.297, ETH 0.299,
XRP 0.373, DOGE 0.346, BNB 0.281, HYPE 0.315). It survives:
- one-day circular block bootstrap: t = 5.3–10.4
- a fully non-parametric median-indicator sign test: t = 8.3–14.2
- 99% winsorization, and dropping the single largest-|r| day
- full time-of-day de-seasonalization

It clears the corrected bar (|t| = 3.76) independently in all six. Corroborated
out-of-sample by `volmodel`: a causal EWMA σ beats an expanding-window constant
σ per-window in **BTC (63.6% win rate, t = +13.7) and ETH (57.3%, t = +7.3)**
— and *only* those two (XRP +2.6, BNB +1.3, DOGE −0.8, HYPE −1.6).

**It is not yet money.** `volmodel` states the condition itself: this is an edge
only if *the book's σ is slow*. The stage that measures that (`implied.py`)
returned zero observations. **This is the next experiment — see §7.**

### TWO CORRECTLY-MEASURED NULLS (real, not empty)
- **`pathstats`**: the contract price is a martingale on trade-print evidence.
  54 tests, max |t| = 2.5 against its own computed bar of 3.31, 405 close-time
  clusters. Strengthened by the fact its contaminated input pushes *toward*
  false positives.
- **`placebo`**: no exploitable terminal-calibration edge in 3,600 markets and
  8,024,108 prints. The run's largest |t| (4.341) sits at the **55.5th
  percentile** of what an efficient market produces on the same tape.
- **No directional edge.** Up-rate 50.4% over 5,195 markets; every series'
  deviation is smaller than its own MDE.

### THINGS THAT LOOKED REAL AND ARE NOT
- `KXSOL15M ac2 = −0.2227, t = −4.4` — **one pair** of 398 supplies 74% of the
  numerator; delete it and ac2 = −0.058. Also from a stale cache.
- **04h volatility peaks** (XRP 1.36×, DOGE 1.38×, BNB 1.30×) — a single day,
  2026-08-22, supplies 76–85% of the bucket via one ~19σ move shared across all
  three. Rotation test p = 0.59 / 0.82 / 0.94.
- **`volmodel` dLL headline** (+347.7 to +733.2) — the top 20 observations of
  946–2,548 are 44–105% of the total. Above 100% means the other ~1,000 windows
  are net negative. Block-bootstrap t = 1.2–2.4.
- **All six "MISPRICED" D-FINAL calibration cells** — killed three independent
  ways, including placebo's own null.

---

## 4. WHAT IS KNOWN TO BE WRONG WITH THE TOOLING'S OWN CLAIMS

- **GATE C is weaker than advertised.** `strike(N+1)==settle(N)` holds
  bit-exact in 19,471/19,471 *within-run* pairs but only **1 of 73** pairs that
  straddle a data gap. It verifies that Kalshi copied a field, not that
  settlement is computed correctly. The docstring's "stronger settlement gate
  than kalshi_gate1.py" should be restated.
- **`KXDOGE15M`'s GATE C `*FAIL*` is a false alarm** — `floor_strike` is
  quantized to 1e-6 while `expiration_value` carries 1e-7. The identity holds
  in 1,978/1,978 pairs under `floor(settle × 1e6)/1e6`, always one-sided
  (strike ≤ settle).
- ~~**`chain.py` uses iid SEs (`1/√n`) on both autocorrelation tables**~~ —
  **FIXED.** Both tables now divide by a moving-block-bootstrap SE and print
  the old iid `t` beside it, so the inflation is visible rather than implied.
  A new self-test section 6 measures the two rulers against a known answer:
  150 datasets of 1,200 windows with **true ρ = 0** and heavy vol
  clustering, counting how often a nominal 95% interval actually contains the
  truth.

  | ruler | median SE | 95% coverage |
  |---|---|---|
  | iid `1/√n` | 0.0289 | **69%** |
  | moving-block bootstrap | 0.0484 | **91%** |

  The iid SE is **1.67× too small** on this fixture, so every `t` in the
  return table was inflated by that factor — and the fixture's returns have
  *zero* true autocorrelation. This is the more important half: the clustering
  we confirmed does not just break the |r| table's SE, it breaks the RETURN
  table's SE too, because a return series with clustered variance is not iid
  even when its autocorrelation is exactly zero. On the synthetic GARCH cases
  the |r| `t` falls from 12.5 to 8.8 (g=0.30) and 26.8 to 18.5 (g=0.60);
  expect a similar haircut on the real series.

  The block bootstrap covers 91%, not 95% — mildly optimistic in finite
  samples. Both a HAC/Newey–West SE and subsampling were calibrated against
  the same fixture; HAC landed at the same 89–91% coverage and subsampling
  worse, so the bootstrap was kept for needing no bandwidth choice. The `|t|
  > 3` verdict bar (rather than 1.96) absorbs the residual.

  Sign persistence keeps its binomial SE `√(0.25/n)`: measured against the
  same process it is correctly calibrated (ratio 1.05), because signs are
  insensitive to heteroskedasticity. That is now the most robust column in the
  return table, not the least.

  **Still iid:** `power_analysis()` (`--power`) computes its false-positive
  columns with `ac_t`, not the block SE. Its `g = 0` row is homoskedastic so
  that row is sound, but the garch rows understate the bar.
- ~~**`KXBTC15M` was not pulled in the 2026-08-26 run**~~ — **FIXED**, and the
  cause was not a failure. The cache-skip condition was `have >= markets*0.9`,
  size only: BTC's cache was long enough, so the pull was skipped and BTC
  never appeared in the run log. The anchor of the detectability table came
  from a ~10-hour-old cache and nothing in the output said so. The condition is
  now size **and** age (`STALE_HOURS = 6`), and a **DATA PROVENANCE** table
  prints before GATE C with each series' market count, `cache`/`pulled`, the
  age of its newest settlement, pages fetched, and retries spent.

  The 429 truncations were a separate fault in `fetch_settled`: it `break`ed
  out of the pagination loop on *any* non-200 and on *any* exception, and
  returned the short list with no way for a caller to tell "this is the whole
  history" from "we gave up here". So a rate limit was reported as a fact
  about the market. It now retries with exponential backoff (0.5/1/2/4/8s),
  honours a `Retry-After` header verbatim, does **not** retry a 4xx that isn't
  429, and fills a `stats` dict whose `truncated` flag distinguishes a short
  history from a short pull. Self-test section 7 drives six scripted cases
  (429-then-ok, `Retry-After`, 429-forever, 404, timeout-then-ok, clean
  exhaustion) through an injected session and asserts the flag and the backoff
  growth on each.
- ~~**`doctor.channel_stats` undercounts** wherever `mid-write > 0`~~ —
  **FIXED.** It used plain `gzip.open`, which dies inside a torn member and
  surrenders everything written after it; the proof was in the run itself
  (86,338 seconds recovered by `feeds.py` against 83,463 messages counted on
  the same channel). It now reads through `gzsalvage`, and a self-test builds
  the exact shape a crash leaves — a member torn mid-write followed by a
  complete member appended on restart — and asserts the census beats
  `gzip.open` on it: **24 lines vs 84**. The `mid-write` column now means
  "salvaged", not "discarded", and the census says so in words.

---

## 5. INFRASTRUCTURE FACTS THAT COST DATA

- **The collector cannot write a gzip trailer on Windows.**
  `loop.add_signal_handler` raises `NotImplementedError` there and was silently
  swallowed, so `c.w.close()` never ran. A restart *inside the same UTC hour*
  then appended a second gzip member behind an untrailered first, and the
  standard reader threw the **whole file** away — reproduced faithfully:
  **0 of 10 records recovered**. `research/gzsalvage.py` reads those files
  member-by-member and recovers them (0→40, 0→60 in its self-test); every
  loader now goes through it. The collector fix (signal fallback + try/finally)
  stops new files being written that way. **Restart near :00.**
- **Memory**: `replay.load_quotes` and `book.rebuild` used to hold whole
  channels as Python dicts — measured 1,330 bytes of peak RSS per message.
  Both stream now: **220 B/msg, 6×**. `orderbook_delta` at 1.9 GB still
  projects ~15 GB peak; `everything.py` preflight prints the projection.
  **A PC crash an hour into a run was this.**
- ~~**Bitstamp is 92.6% waste**~~ — **FIXED, effective on the collector's next
  restart.** `crypto_feeds.py` subscribes to `order_book_<pair>`, Bitstamp's
  100-bid/100-ask FULL SNAPSHOT channel, and the repo only ever reads
  `bids[0]`/`asks[0]` (`feeds.load_tob`, `proxy.py`'s constituent series).
  3.1 GB of 3.2 GB `feed_data`.

  Not switched to `diff_order_book_` — that channel is *larger*, being full
  depth deltas, and it would require carrying book state to recover the touch
  we already get for free. Instead the record is trimmed to
  `BITSTAMP_KEEP_LEVELS = 5` a side at write time, with `--book-levels 0`
  restoring the old behaviour byte-for-byte.

  Measured, on 200 records of the real shape at the gzip level actually used:
  **712 → 29 bytes per record, a 95.9% cut.** Against Bitstamp's 92.6% share
  that is ~89% off `feed_data`'s growth rate. The saving is measured on a
  synthetic record of the same shape, not on the real file — real books have
  less regular prices and sizes, so they compress worse and the true saving
  should be at least this.

  Trimming is stamped into the record as `_depth: {bids, asks, kept}`, giving
  what the venue actually sent. A silently truncated archive is the kind of
  thing that produces a confident wrong answer two months from now: a future
  reader must be able to tell a five-level book from a market that only had
  five levels.

  The self-test's decisive check is end to end, not structural — it writes a
  full-depth file and a trimmed one, runs the project's own `load_tob` over
  both, and asserts the results are identical (and that they are not both
  empty, which would compare nothing and pass). It also proves `--book-levels
  0` reproduces the original bytes exactly, and that a book already shallower
  than the limit is left completely untouched, stamp included.

  **Levels 2-100 already on disk keep their full depth; nothing recorded so
  far is altered. What gets trimmed from here cannot be recovered.**
- **The watchdog runs the collectors from `C:\kals`, not the repo.**
  `run_all.ps1` does `Set-Location C:\kals` then `python crypto_feeds.py`, so
  it launches the copies sitting next to the data. **A `git pull` updates the
  repo and changes nothing about what is recording** — every collector fix
  this project has made could have been sitting unused, and nothing in any run
  said so. `everything.py` step `0c` now hashes both collectors against the
  repo and reports drift; `--sync-collectors` copies them, backing each up to
  `.bak` and gating on its own `--selftest` where it has one and a compile
  check where it does not (no self-test must not mean "never sync", which
  would pin the file forever). The copy does not affect the RUNNING processes
  — the watchdog has to restart.
- Channels named `ok` and `subscribed` are being written as data channels (the
  collector routes purely on the `type` field). Harmless, tiny.

---

## 6. MARKET FACTS ESTABLISHED FROM THE API

- **There is no fee discount for equities.** `fee_multiplier` is an integer
  **0/1 waiver flag**, not a rate — only 3 series of 1,289 carry 0. All 68
  S&P/Nasdaq series and all 14 crypto 15M series carry `fee_multiplier=1`,
  `fee_type="quadratic"`. PLAN.md's 0.035-vs-0.07 premise is **refuted**.
  `fee_type` also takes `"quadratic_with_maker_fees"` on some series.
  **Open**: read Kalshi's published schedule keyed on `exchange_index`
  (0 = financials, 2 = crypto), present on both series and market objects.
- **The true ≤15-minute universe is 16 series** by the authoritative
  `frequency` field (`"fifteen_min"`): 14 crypto + **`KXINX15M` (S&P 500) and
  `KXNDQ15M` (Nasdaq 100)**. Nothing exists between `fifteen_min` and
  `hourly`; there are 44 hourly series. A ticker-substring scan is unreliable
  (it false-positives `KXUST30M`, a *30-year* Treasury, monthly).
- **`KXCRYPTOLEAD15M` ("Coin Race")** — which of BTC/ETH/SOL/XRP/HYPE has the
  highest return over a 15-min window. One market per coin per event,
  `expiration_value` holds the winning ticker. **This is computable from index
  feeds already recorded**: P(coin i has max 15-min return). Genuinely
  different shape from a binary, and unexplored.
- **`KXCRYPTOCOMP15M`** returned 0 settled markets; the query is correct, the
  series simply has no settled history yet.

---

## 7. THE NEXT EXPERIMENT (both adjudicators independently agreed)

**Get `implied.py` to produce output, and compare the book's implied σ against
the EWMA σ forecast, window by window.**

Why: after every correction, exactly one finding survives (volatility
clustering), and `volmodel` states its own condition — *"this only survives as
an edge if the book's sigma really is slow. That is the thing to measure, not
to assume."* The stage that measures it returned zero observations because of
the field rename, which is now fixed. It needs no new recording; 26 hours are
already on disk.

Order of operations:
1. Restart the recorder (§0).
2. `git pull` in `C:\kals-repo`.
3. `python research\everything.py` — one command, no arguments, 30–60 min.
   It now reads the 2 GB it ignored, and flags any stage that loads no data as
   `EMPTY` rather than `ok`.
4. Read `power.py`'s detectability table **before** `RESULTS.md`.

---

## 8. STILL OPEN / NOT YET DONE

Ranked by information unlocked per unit of work:

1. **Tick size** (tapered vs flat 1¢) — the probe is now built; it needs a run
   from a machine that can reach the API (this session's proxy returns 403 on
   `api.elections.kalshi.com`, a policy denial, not a transport fault). Step 2
   fetches `/series/KXBTC15M` and a live market, then prints **every** field in
   either response whose name could describe a tick, verbatim, rather than
   reading a schema I have not seen — naming the field wrong and getting zero
   back would answer the question with silence. `ticker` is excluded from the
   match: it contains `tick`, and without that exclusion every response
   reports a hit and the honest "the API carries no tick field" verdict can
   never print. Exercised against five synthetic responses (tapered
   `price_ranges`, flat `tick_size`, a deeply nested `minimum_price_increment`,
   one with nothing, and one hiding a tick field *under* a key containing
   "ticker").
2. ~~Replace `chain.py`'s iid SEs with block-bootstrap~~ — done, and the
   self-test now measures the coverage of both rulers rather than asserting
   the new one is better. Re-read the run-2 return-autocorrelation verdicts
   with the block `t`; the iid ones were ~1.7× too large.
3. ~~Make `doctor.channel_stats` use `gzsalvage`~~ — done; the census is no
   longer a lower bound.
4. ~~Fix `chain.py`'s HTTP 429 handling and make it actually pull
   `KXBTC15M`~~ — done; see the provenance table. Series-level staleness is
   now printed once, up front, rather than marked in every table — if that
   turns out not to be enough, the per-table marker is the next step.
5. Restate GATE C's claim (§4).
6. ~~Switch Bitstamp to the delta channel (§5)~~ — done differently and
   better: the record is trimmed to 5 levels at write time (95.9%
   measured), because the delta channel is bigger than the snapshot one.
   Takes effect when the collector next restarts.
7. Reopen the fee question via `exchange_index` (§6).
8. Model `KXCRYPTOLEAD15M` (§6) — unexplored, and computable from data in hand.
9. The 87-idea adversarial sweep produced 16 survivors and 6 rated worthwhile;
   **the synthesis agent never returned and that list was lost.** Worth
   regenerating if broad idea coverage is wanted again.

---

## 9. METHOD — WHY THIS PROJECT WORKS THE WAY IT DOES

Every large edge this project has produced has been a measurement bug. Roughly
thirty have been caught, every one by a self-test planting a known answer:
occupation-time selection bias, σ-noise selection, tick-quantization giving the
model a free win (t=10.6), a reflecting-barrier generator, per-observation
cents/dollars inference (a 75¢/contract phantom), pricing eleven series off
bitcoin (+6.13¢/contract at t=4.9 against two fair books), differencing across
data gaps, an `except Exception` swallowing a `NameError` as "0 rows".

So: **a statistic without a calibrated null is not evidence.** Anything
eye-catching is a bug until it survives its own null. Prefer estimators whose
correct answer is known in advance. And the corrected significance bar for one
`go.py` run (294 statistics) is **|t| = 3.76 on a normal** — but several
statistics here are *t* on ~19 degrees of freedom, where the same bar is
**4.66**. Re-measuring on fresh data beats any correction.

### The generative methods that produced the surviving ideas
1. Differentiate the pricing function; sort candidates by *which parameter they
   live in* (μ-based edges are robust, σ-based ones are capped by our own σ̂
   error). This one move re-ranked everything.
2. Hunt for what is *arithmetically determined* rather than predicted
   (`strike(N+1)=settle(N)`, the locked partial average).
3. Attack the *premises* of existing claims, not the conclusions. Killing "every
   window opens at 50¢" produced the openwindow idea.
4. Ask what nobody has ever looked at (second zero; 3 GB/day of feeds no code
   had read).
5. Invert: not "where's the edge" but "what would the market have to be doing,
   and who would be doing it?" → `proxy.py`.
6. Price the exit before the entry — this killed perp delta-hedging in one
   calculation (10.9¢ at 900s to 98¢ at 30s, against 0.5–2¢ edges).

---

## 10. FILE MAP

**Runner**: `research/everything.py` — one command, does everything, writes
`REPORT.md` + a zip. `research/go.py` — self-test gate + 13 analysis stages.

**Model & power**: `settlement_math.py` (exact model, MC-verified),
`power.py` (minimum detectable effect + multiple-testing), `tdist.py`
(Student-t), `viability.py` (edge → Sharpe/drawdown/time-to-validate),
`settlewin.py` (shared conditional-mean helper).

**Data plumbing**: `doctor.py` (schema prober — writes `schema.json`),
`gzsalvage.py` (recovers restart-damaged gzip), `replay.py` (loaders + replay),
`book.py` (order-book rebuild).

**Analysis stages**: `chain.py`, `volmodel.py`, `placebo.py`, `cross.py`,
`openwindow.py`, `implied.py`, `feeds.py`, `pathstats.py`, `proxy.py`,
`leadlag.py`, `edge.py`, `engine.py` (decision logic, **no order code**).

**Docs**: `STATUS.md`, `PLAN_V3.md` (ranked edge list), `RUNBOOK.md` (hard
rules + API traps), `RUN_WHEN_HOME.md` (operator card), `research/RESULTS_R1..R6.md`
(earlier findings, each with its method note).

**Recorders** (root): `kalshi_collector.py`, `crypto_feeds.py`, `run_all.ps1`.
