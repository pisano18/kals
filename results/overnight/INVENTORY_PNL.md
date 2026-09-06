# THE JOINT DISTRIBUTION OF (REBATE, INVENTORY P&L) — CRITICISM B, MEASURED

**Job B, overnight 2026-09-06.** Tape `KXCRYPTOLEAD15M` (Coin Race),
**247 fifteen-minute windows x 5 coins = 1,235 markets**, UTC 2026-09-04 ->
2026-09-06. Settlement truth from `market_lifecycle_v2` for every market.
Three fill models, S = 50 a side, both books, 0 and 3 ticks behind the touch.

---

## THE ANSWER IN ONE PARAGRAPH

**The rebate survives its own fills — and criticism B is half right in a way
that matters more than either half alone.** It is *wrong* that inventory P&L
eats the rebate: three ticks behind the touch the inventory P&L is
**statistically indistinguishable from zero** in all three fill models
(+1.2 c/ctr, +6.0, −0.1; only one of the three clears t=2, and its 95% interval
runs down to +0.7). It is *right* that the distribution was never subtracted,
and that the distribution is where the account lives: per 15-minute window the
rebate is **$2.83 with a standard deviation of $2.10**, and the inventory P&L
sitting next to it has a standard deviation of **$16.54 — 5.8x the entire
rebate**. So the correct statement is not "rebate minus inventory is positive"
but:

> **You are paid $271/day of rebate, reliably. The fills bolted onto it are a
> coin-flip worth $0 +/- $208/day that multiplies your variance sixfold. The
> right move is to take the rebate and engineer the fills away, not to count
> them as profit.**

And the single most important new fact, which nobody had looked at: **the five
coins do not hedge each other, and the reason is fixable.**

---

## HEADLINE NUMBERS — the format the operator asked for

Base (`sweep-with-size`) fill model, S = 50, **3 ticks back**, 5 coins,
500 contracts resting in total, 247 windows.

| | rebate only | rebate + inventory |
|---|---|---|
| **$ / 15-min window** | 2.827 | 4.989 |
| **$ / day (96 windows)** | **271.4** | **479.0** |
| **$ / contract / day** (500 resting) | **0.543** | **0.958** |
| **PEAK CONCURRENT capital** | median **$244.55**, p95 $308, max $403 | same |
| **% return on capital / day** | **111%** | **196%** |
| % return per window | 1.16% | 2.04% |
| **95% CI on $/day, day-level, n=3** | — | **[+71, +882]** |
| 95% CI on $/day, 16-window block bootstrap | [+257, +309] (1) | [+89, +739] |
| windows that LOSE money | 0% (rebate cannot be negative) | **18.2%** |

(1) carried from the prior job; the rebate leg is identical across fill models
by construction, so its interval is unchanged.

The **111%/day rebate-only figure in the claim under attack is CONFIRMED** —
independently re-derived here at $271/day on $245 of median peak concurrent
capital = 110.9%/day. It is $271 rather than the claimed $282 because this job
uses the **correct 900-snapshot denominator** (the incentive period is exactly
900 s on all 6,385 `KXCRYPTOLEAD15M` programmes) instead of the ~861 seconds
the tape happens to contain. That is a 4.5% haircut and the earlier figure was
that much too high.

---

## 1. THE PER-WINDOW DISTRIBUTION

All figures $ per 15-minute window across all five coins, n = 247.

### 3 ticks behind the touch — the proposed configuration

| | mean | sd | p1 | p5 | median | p95 | **worst** | % neg |
|---|---|---|---|---|---|---|---|---|
| **rebate** | +2.827 | 2.10 | +0.14 | +0.61 | +2.28 | +7.41 | 0.00 | 0% |
| **inventory P&L**, exact-price model | +0.134 | 7.97 | −24.39 | −9.19 | 0.00 | +10.03 | **−39.80** | 20.2% |
| **inventory P&L**, base model | +2.162 | 16.54 | −44.83 | −21.48 | 0.00 | +30.96 | **−70.13** | 26.7% |
| **inventory P&L**, full-sweep model | −0.115 | 27.44 | −84.23 | −44.33 | 0.00 | +35.85 | **−158.50** | 31.6% |
| **NET**, exact | +2.961 | 8.46 | −22.50 | −7.06 | +2.17 | +13.31 | −38.25 | 12.1% |
| **NET**, base | +4.989 | 16.84 | −42.18 | −20.05 | +2.72 | +34.33 | **−68.63** | **18.2%** |
| **NET**, sweep | +2.712 | 27.49 | −82.25 | −41.86 | +2.28 | +39.12 | −155.66 | 26.7% |

### At the touch (0 ticks) — for contrast, and it is worse

| | mean | sd | p1 | p5 | worst | % neg |
|---|---|---|---|---|---|---|
| **NET**, exact | +1.626 | 7.61 | −29.27 | −9.42 | −41.07 | 13.8% |
| **NET**, base | +1.697 | 22.62 | −82.60 | −33.11 | −122.58 | 27.9% |
| **NET**, sweep | **−2.880** | 40.53 | −192.79 | −60.25 | −210.87 | 39.7% |

Three ticks back roughly **halves the variance and triples the mean**. That is
the whole case for standing back, and it survives the distributional test that
the mean-only version did not have to pass.

### The actual joint table (base, d=3, counts of windows)

| rebate \ inventory | < −20 | −20..−5 | −5..0 | exactly 0 | 0..+5 | +5..+20 | > +20 | row |
|---|---|---|---|---|---|---|---|---|
| < $0.50 | 1 | 1 | 0 | 4 | 2 | 2 | 0 | 10 |
| $0.50–1.50 | 2 | 1 | 4 | 33 | 10 | 11 | 6 | 67 |
| $1.50–3.00 | 9 | 12 | 12 | 33 | 8 | 14 | 8 | 96 |
| $3.00–5.00 | 2 | 3 | 6 | 9 | 4 | 4 | 4 | 32 |
| > $5.00 | 1 | 9 | 3 | 9 | 7 | 4 | 9 | 42 |
| **col** | **15** | **26** | **25** | **88** | **31** | **35** | **27** | **247** |

Two things read straight off it. **(a) 88 of 247 windows (36%) have exactly
zero inventory P&L** — we were never filled, and collected the rebate for
free. **(b) The big rebate windows are also the big inventory windows**: in the
top rebate band the inventory sd is $22.42 against $8.20 in the bottom band.

| rebate band | n | mean inventory | sd | worst | mean NET | % windows losing money |
|---|---|---|---|---|---|---|
| < $0.50 | 10 | −0.65 | 8.20 | −20.60 | −0.38 | 20% |
| $0.50–1.50 | 67 | +3.97 | 13.25 | −38.47 | +5.03 | 6% |
| $1.50–3.00 | 96 | −0.64 | 15.85 | −70.13 | +1.63 | 26% |
| $3.00–5.00 | 32 | +1.03 | 15.30 | −51.25 | +4.72 | 16% |
| > $5.00 | 42 | +7.20 | 22.42 | −29.04 | +14.10 | 21% |

The rebate is not free of risk; it is *sold with* risk, because a window busy
enough to keep both sides above the 1,000-lot target is a window busy enough to
run you over. The linear correlation is only +0.097 — weak — but the
conditional variance is not.

---

## 2. PER DAY, AND THE BLOCK BOOTSTRAP

### The three real UTC days (base, d=3), $ scaled to 96 windows

| day | windows | rebate | matched | residual | **NET** | **NET/96 win** |
|---|---|---|---|---|---|---|
| 2026-09-04 | 90 | 340.13 | +90.32 | +187.20 | 617.65 | **+658.83** |
| 2026-09-05 | 96 | 192.03 | +14.24 | +137.98 | 344.25 | **+344.25** |
| 2026-09-06 | 61 | 166.21 | +33.93 | +70.36 | 270.49 | **+425.69** |
| **all** | 247 | 698.37 | +138.49 | +395.54 | 1,232.40 | **+478.99** |

### The clustering the operator was worried about is NOT in this tape

Autocorrelation of NET across consecutive windows, base d=3:

```
lag 1  +0.089    lag 2  -0.013    lag 4  +0.044    lag 8  +0.031    lag 16 -0.031
```

Near zero at every lag, in every model. **The block bootstrap therefore barely
differs from the iid one** — which is itself the finding, and it is the honest
version of the iid-bootstrap failure the brief warned about. The earlier
project was flattered by an iid *close-level* bootstrap; here we ran the block
version anyway and it says the same thing, for a reason we can point at.

### Block bootstrap of a 96-window day, base d=3, by block length

| block | mean | p1 | p5 | median | p95 | P(day < 0) |
|---|---|---|---|---|---|---|
| 1 window (iid — wrong on principle) | 480 | +113 | +212 | +474 | +758 | 0.1% |
| 4 windows = 1 hour | 480 | +70 | +191 | +480 | +772 | 0.4% |
| **16 windows = 4 hours** | **481** | **+89** | **+208** | **+486** | **+739** | **0.2%** |
| 32 windows = 8 hours | 478 | +120 | +231 | +474 | +736 | 0.0% |
| 96 windows = 1 whole day | 477 | +180 | +238 | +460 | +657 | 0.0% |

Week (672 windows, 16-window blocks): mean **+$3,356**, p1 **+$2,359**,
p5 +$2,656, P(week < 0) = **0.0%**.

### ...and why that interval is TOO NARROW

The bootstrap resamples inside three UTC days. It cannot see day-to-day regime
change, and the three days differ by nearly 2x ($659 / $344 / $426). The
honest interval is the **day-level** one, and it has n = 3:

| model / d | the three days, $/96 win | mean | **95% CI on $/day (t, 2 dof)** |
|---|---|---|---|
| exact d=0 | 199, 10, 324 | 177 | [−215, +570] |
| exact d=3 | 441, 123, 308 | 290 | [−106, +687] |
| base d=0 | 150, 64, 337 | 184 | [−164, +531] |
| **base d=3** | 659, 344, 426 | **476** | **[+71, +882]** |
| sweep d=0 | −44, −748, 121 | −223 | [−1,370, +924] |
| sweep d=3 | 571, −59, 305 | 272 | [−513, +1,057] |

**Report the day-level interval, not the bootstrap one.** Three days is not
enough to pin a rate that moves this much between days, and pretending
otherwise is exactly the error the brief flagged.

### Worst observed contiguous runs (real order, base d=3)

| run | worst | when | best |
|---|---|---|---|
| 1 window | **−$68.63** | 2026-09-06 01h | +$117.71 |
| 4 windows (1 h) | **−$130.36** | 2026-09-06 00h | +$164.28 |
| 16 windows (4 h) | **−$109.27** | 2026-09-05 21h | +$229.77 |
| 96 windows (1 day) | **+$173.89** | — | +$675.85 |

**No 96-window run in the tape was negative** in the base model at d=3. At the
touch the worst 16-window run was −$238.90 and the worst 96-window run was
−$155.80 — the touch loses whole days; three ticks back did not.

Per-hour NET, base d=3 (n=63 hours): mean +$19.56, sd $36.72, worst −$82.17,
best +$154.44, 21% of hours negative.

---

## 3. THE CORRELATION THAT MATTERS — AND IT IS THE HEADLINE FINDING

> "*If a move goes against us on one coin it may go FOR us on another. This
> could be the single most important fact in the whole strategy and nobody has
> looked.*"

**It was worth looking, and the answer is: they do not hedge, they are
effectively independent, and the reason is a fixable property of how we quote —
not a property of the market.**

Measured, base d=3, 247 windows:

```
pairwise corr of per-coin inventory P&L       +0.017   (10 pairs, range -0.063..+0.141)
var(5-coin sum) 240.7  vs  sum of the five vars 225.1   ratio 1.069
sd of residual P&L:  ACTUAL 15.51 | winner reshuffled 18.54 | five INDEPENDENT binaries 18.73
   -> the "exactly one coin wins" constraint changes risk by -1% vs independence
```

### Why, exactly

Write our unmatched (naked) position on coin *i* as `r_i` YES-equivalent
contracts bought at average yes-price `a_i`. Exactly one coin settles YES
(verified: 330 of 1,650 settlements are YES, exactly one per event), so

```
residual P&L = SUM_i r_i (V_i - a_i)/100
             = r_k                      <- $1 per contract on the WINNING coin
             - SUM_i r_i a_i / 100      <- deterministic
```

Every random thing collapses into `r_k`: the position we happen to be holding
on whichever coin wins. With `p = 1/5`,

```
one-winner:  var(r_k) = p*SUM r_i^2 - p^2*(SUM r_i)^2
independent:          = p(1-p)*SUM r_i^2
hedge value           = p^2 * [ (SUM r_i)^2 - SUM r_i^2 ]
```

The hedge exists **only if more than one leg is non-zero and the legs share a
sign**. Verified numerically:

| residual book | sd, one-winner | sd, independent | hedge |
|---|---|---|---|
| **one leg of 50** | 20.00 | 20.00 | **0%** |
| five equal LONG legs | **0.00** | 44.72 | **100%** |
| five equal SHORT legs | **0.00** | 44.72 | **100%** |
| three long, two short | 48.99 | 44.72 | **worse than independent** |

**And we hold, on average, a residual position on 1.04 of the 5 markets per
window.** 86.6% of windows have every residual leg pointing the same way —
because there is usually only *one* leg. With exactly one non-zero leg
`SUM r^2 = (SUM r)^2` and the two variances are algebraically **identical**.
The one-winner structure buys us **exactly nothing**, which is precisely what
the −1% measurement says.

### The lever this hands us — and the honest size of it

The same algebra says a residual that is **equal and same-signed across all
five coins has zero settlement risk — not low, zero.** That is not a
diversification argument, it is an identity: if `r_i = r` for all *i*, then
`r_k = r` whatever wins. The strategy as specified throws that away by letting
fills land wherever they land, and the rebate is paid for resting size, so it
is blind to the residual's shape.

Measured on the actual positions — same total signed exposure, same
exposure-weighted average entry price, redistributed equally across the five
coins:

| | mean $/win | sd | p1 | p5 | **worst window** | % neg |
|---|---|---|---|---|---|---|
| residual, **as it actually landed** (base d=3) | +1.601 | 15.51 | −45.39 | −23.57 | **−70.13** | 26.3% |
| residual, **balanced across five coins** | +2.167 | **11.46** | −30.84 | −14.22 | **−34.50** | 25.1% |
| residual, actual (base d=0) | −2.475 | 22.42 | −85.10 | −37.71 | **−146.45** | 59.1% |
| residual, balanced (base d=0) | +9.665 | **18.00** | −37.64 | −12.69 | **−45.34** | 20.2% |

**The risk half of this is real and is the point: sd falls 26% and the worst
window halves, from −$70.13 to −$34.50.** Note the sd does not fall to zero
even though settlement risk does — the residual `r_k` term becomes exactly
constant, and the $11.46 that remains is *cross-window* variation in the
deterministic `SUM r_i a_i` term (some windows simply carry more exposure at
worse prices). That is not settlement risk at all.

**The P&L half of it must NOT be quoted.** The counterfactual raises the mean
(+1.60 -> +2.17 at d=3, and −2.48 -> +9.67 at d=0, which would imply
$1,328/day). That is an artefact: it assumes we could have obtained the same
average price while being balanced, i.e. it silently removes the adverse
selection that produced the lopsided book in the first place. **Treat the
balanced-residual variant as a risk reduction of ~26% in sd and ~50% in the
worst window, with zero assumed P&L benefit, until it is simulated as an
actual quoting rule rather than a re-allocation of hindsight.**

Concentration by coin (base d=3, 247 windows) — no coin dominates the rebate,
but the inventory P&L is entirely idiosyncratic, which is the same finding
again:

| coin | rebate | inventory P&L | NET | contracts | windows filled |
|---|---|---|---|---|---|
| BTC | 127.0 | +221.6 | 348.6 | 1,900 | 49 |
| ETH | 110.2 | +162.0 | 272.3 | 1,766 | 46 |
| HYPE | 179.7 | +98.2 | 277.9 | 2,301 | 62 |
| SOL | 143.0 | +63.1 | 206.1 | 1,098 | 41 |
| XRP | 138.4 | **−10.8** | 127.5 | 1,894 | 60 |

---

## 4. THE "10–30c MOVE" — THE CRITIC UNDERSTATED IT

Distribution of the adverse move `(fill price − settlement)` per contract,
contract-weighted, base d=3, 376 fills / 8,960 contracts:

```
mean  -5.96c (i.e. P&L +5.96c)      sd  42.02c
p1 -88   p5 -77   p25 -36   median -10   p75 +29   p95 +63   p99 +84   max +91
```

| move against us | share of contracts | | move FOR us | share |
|---|---|---|---|---|
| >= 10c | **37.0%** | | >= 10c | 51.4% |
| >= 20c | **31.1%** | | >= 20c | 37.9% |
| >= 30c | **23.5%** | | >= 30c | 30.7% |
| >= 50c | **9.6%** | | >= 50c | 17.0% |
| >= 70c | **3.6%** | | >= 70c | 6.8% |
| >= 90c | 0.6% | | >= 90c | 0.5% |

**On a binary that settles 0 or 100 the move is never "10–30c" at settlement —
it is the whole distance from the fill price to 0 or to 100.** The per-contract
standard deviation is 42c against a mean edge of 6c: a signal-to-noise of 0.14
per contract. The critic named the right risk and then named it three times too
small.

At the touch the same distribution has mean **+1.46c against us** and a median
of **+1c** — i.e. at the touch the median fill loses.

---

## 5. NET: DOES THE REBATE SURVIVE ITS OWN FILLS?

**Yes at three ticks back, no at the touch, and the surviving margin is the
rebate — not the fills.**

### Is the inventory P&L different from zero? (t on 247 windows)

| model / d | mean $/win | sd | SE | t | p | 95% CI |
|---|---|---|---|---|---|---|
| exact d=0 | −1.401 | 7.50 | 0.477 | **−2.94** | 0.003 | [−2.34, −0.47] |
| exact d=3 | +0.134 | 7.97 | 0.507 | +0.26 | 0.792 | [−0.86, +1.13] |
| base d=0 | −1.330 | 22.58 | 1.437 | −0.93 | 0.355 | [−4.15, +1.49] |
| base d=3 | +2.162 | 16.54 | 1.053 | **+2.05** | 0.040 | [+0.10, +4.23] |
| sweep d=0 | −5.907 | 40.56 | 2.581 | **−2.29** | 0.022 | [−10.97, −0.85] |
| sweep d=3 | −0.115 | 27.44 | 1.746 | −0.07 | 0.947 | [−3.54, +3.31] |

The **residual** (naked) part alone, which is the part criticism B is actually
about: exact d=3 t = +0.16, **base d=3 t = +1.62**, sweep d=3 t = −0.61. **Not
one of them is significant.**

### Per-contract edge, standard error CLUSTERED ON THE MARKET

Contracts inside one market share **one** settlement, so the independent unit
is the market, not the contract. Ignoring that inflates t by roughly 6x.

| model / d | markets w/ fills | contracts | edge c/ctr | clustered SE | t | 95% CI |
|---|---|---|---|---|---|---|
| exact d=0 | 471 | 7,318 | −4.730 | 2.024 | −2.34 | [−8.70, −0.76] |
| exact d=3 | 127 | 2,821 | +1.171 | 4.070 | +0.29 | [−6.81, +9.15] |
| base d=0 | 715 | 22,468 | −1.462 | 1.564 | −0.94 | [−4.53, +1.60] |
| **base d=3** | 258 | 8,960 | **+5.960** | 2.693 | **+2.21** | [+0.68, +11.24] |
| sweep d=0 | 767 | 51,918 | −2.810 | 1.166 | −2.41 | [−5.10, −0.52] |
| sweep d=3 | 318 | 20,371 | −0.140 | 2.012 | −0.07 | [−4.08, +3.80] |

**At the touch, the inventory P&L is significantly negative in two of three
models. Three ticks back, it is indistinguishable from zero in two of three
and only marginally positive in the third.** The three d=3 intervals overlap
heavily and all sit close to zero.

### Decomposition: matched vs naked (base, d=3)

| component | mean $/win | sd | worst | % neg |
|---|---|---|---|---|
| **matched** (both sides filled; settlement cancels) | +0.561 | 3.74 | −19.72 | 4.5% |
| **residual** (the naked binary criticism B is about) | +1.601 | 15.52 | −70.13 | 26.3% |

3.45 matched pairs and 29.4 residual contracts per window; a residual exists on
1.04 of 5 markets. The matched leg is the honest market-making profit — you
bought yes at bid−3 and no at (no-bid)−3, locking >= 6 ticks plus the spread —
and it is small and stable. Note it is **not risk-free**: `matched` is negative
in 4.5% of windows, because the two legs fill at different times and the touch
can trend between them (worst −$19.72). **The residual is where all the
variance lives, and its t is 1.62. It is not money you can bank.**

### The bottom line, stated plainly

> **The rebate survives.** $271/day of rebate is earned on $245 of median peak
> concurrent capital, it does not depend on any fill model, and it is not
> destroyed by the fills that come with it.
>
> **The fills are worth zero.** The +$208/day of inventory P&L in the base
> model's point estimate has a t of 2.05 on 247 windows and a t of 1.62 on the
> part that carries the risk; the other two fill models put it at +$13/day and
> −$11/day. Budget it at **$0 +/- $208/day** and treat any realised fill profit
> as luck.
>
> **What the fills definitely do is multiply the variance by six.** Rebate-only
> sd is $2.10/window; rebate-plus-fills is $16.84.

---

## 6. THE TAIL, AND A $1,000 ACCOUNT

### A hard bound before any simulation

We **buy** binaries on both books. A bought binary cannot lose more than the
premium paid, and Kalshi holds full collateral, so **capital deployed is
capital at risk and the worst a single window can cost is the capital in it.**

| S | capital/window median | p95 | **max = absolute single-window bound** | worst window observed | as % of $1,000 |
|---|---|---|---|---|---|
| 25 | $126 | $165 | $205 | −$40.37 | 4.0% |
| 50 | $245 | $308 | **$403** | **−$68.63** | 6.9% |
| 100 | $482 | $574 | $764 | −$117.21 | 11.7% |

**One window cannot wipe this account. Only a run of them can.**

### Block-bootstrapped equity paths, $1,000 bank, 16-window blocks, 20,000 reps

| model / d | 1 day p1 | 1 week p1 | 30 days p1 | worst drawdown p1 (30 d) | **P(50% drawdown in 30 d)** | **P(ruin in 30 d)** |
|---|---|---|---|---|---|---|
| **base d=3** | +$85 | +$2,356 | +$12,269 | −$340 | **0.01%** | **0.00%** |
| exact d=3 | +$80 | +$1,404 | +$7,270 | −$104 | 0.00% | 0.00% |
| **sweep d=3** | −$358 | +$196 | +$4,387 | −$1,093 | **68.5%** | **2.06%** |
| base d=0 | −$369 | −$224 | +$2,024 | −$1,216 | **75.7%** | **4.39%** |

**Criticism C's "one or two windows and the account is impaired" is false as
stated** — no single window can take more than the deployed capital, and the
worst observed took $68.63. But under the deliberately-too-aggressive sweep
model, or at the touch, a **30-day 50% drawdown is more likely than not**, and
outright ruin runs 2–4%. The ordering is unambiguous: **the touch is dangerous
for a $1,000 bank; three ticks back is not.**

### Size scaling — measured, not assumed (real S=25/50/100 runs at d=3)

| S | rebate/win | inv/win | NET/win | sd | p1 | worst | capital | **%/day** | ctr/win |
|---|---|---|---|---|---|---|---|---|---|
| 25 | 1.416 | +1.394 | 2.810 | 10.21 | −25.26 | −40.37 | $126 | **214%** | 24.3 |
| **50** | 2.827 | +2.162 | **4.989** | 16.84 | −42.18 | −68.63 | **$245** | **196%** | 36.3 |
| 100 | 6.518 | +3.229 | 9.747 | 25.79 | −57.25 | −117.21 | $482 | **194%** | 49.6 |

Scaling from S=50 -> S=100 (linear would be 2.00x): rebate **2.31x**
(super-linear — our own size helps pull the reference price up), contracts
**1.37x**, capital 1.95x, sd 1.53x, worst window 1.71x. **Return on capital is
flat at ~195%/day across the whole size range, and the tail grows more slowly
than the size.** A $1,000 bank comfortably carries S=100 (p95 capital $574).

---

## WHAT WOULD HAVE TO BE TRUE FOR THIS TO BE AN ARTEFACT — AND WHAT THE CHECK SAID

**1. That my P&L accounting is wrong.** *Checked and cleared.* 20/20
self-tests pass before any tape is touched (single fills in both directions,
the hedge identity that YES at p plus NO at 100−p is exactly zero, a locked
spread paying its width whatever settles, the fee knob, and the rebate
arithmetic including the ceiling that a 100% share for 900/900 seconds pays
exactly the $20 pool). Then the independent check: my per-contract P&L
reproduces the prior job's TABLE A **to three decimal places** on all three
fill models at d=0 (−4.730 / −1.462 / −2.810), computed from a different code
path. The locked/residual split is asserted to 1e-6 against the total on every
one of 1,235 markets.

**2. That the positive inventory P&L at d=3 is just "short yes in a market
where 4 of 5 settle NO".** *Checked — and it is not that, but it is not solid
either.* Our residual legs are 68% short-yes, and a short-yes book wins 80% of
the time by construction, so over 2.6 days it would look profitable whether or
not there is an edge. But the fills do **not** land at longshot prices: the
average yes price is 44.36c on the long book and 42.47c on the short book —
i.e. the contested markets — and the realised yes-rate on our short book was
37.0%, so the base-rate story does not explain it. Per-direction edges are
+5.48c (short) and +6.95c (long), consistent with the mechanical explanation
(three ticks back you buy below the bid and sell above the ask, so both
directions can carry edge). **But the three fill models disagree on the sign of
the long-side edge** (+6.95 / −8.12 / −3.20 c/ctr), which is the honest
reading: the sample cannot resolve it.

**3. That a handful of lucky settlements carry it.** *Checked — partly true,
but not the main weakness.* The best 5 of 247 windows carry 55% of the total
inventory P&L. But removing the best 5 **and** the worst 5 leaves
+$2.06/window against +$2.16 — so it is not one lottery ticket. The weakness is
the t-statistic, not the concentration.

**4. That the block bootstrap is flattering me the way the iid one did before.**
*Checked directly.* Autocorrelation is ~0 at lags 1/2/4/8/16, so block and iid
give the same answer and the block bootstrap's [+89, +739] is real *within*
these three days. It is still too narrow, because it cannot see between-day
regime change and the three days differ by 2x. **The day-level interval
[+71, +882] is the one to quote.**

**5. That the rebate denominator is inflated.** *Found and fixed.* The prior
job divided by the ~861 snapshot-seconds the tape contained; the incentive
period is exactly 900 s (start_date -> end_date) on all 6,385
`KXCRYPTOLEAD15M` programmes in the cached `/incentive_programs` pull, with
`period_reward` 200000 (= $20.00), `target_size_fp` 1000.00,
`discount_factor_bps` 5000. Using 900 cuts the rebate 4.5% ($282 -> $271/day).

**6. That the LIP scorer is the buggy flat-tick one.** *Confirmed, and it cuts
the conservative way.* The cached sim scores distance as `0.50 ** (ref − p)`
with `p` in integer cents, i.e. a **flat 1c tick**. Per the brief's item 3 that
**understates** our share in the tapered zone, so **the rebate leg here is a
lower bound** on that axis. I could not re-run with the tapered tick without a
full ~5 GB replay while the collectors were live.

---

## WHERE I DISAGREE

**With the critic.** "Your calculation never subtracts the DISTRIBUTION of
inventory P&L" — fair, and now done. But the conclusion he expects does not
follow: subtracting it **does not kill the trade at three ticks back**, and the
inventory P&L there is indistinguishable from zero rather than the large
negative he implies. His "10–30c" is also wrong in the other direction: on a
0/100 binary the settlement move is 0–100c, sd 42c, and 23.5% of contracts move
>= 30c against us.

**With criticism C** ("one or two windows and the account is impaired"). False
as stated. A bought binary's loss is capped at the premium; the maximum a
single window can cost at S=50 is $403 and the worst observed was $68.63. The
real version of C is a *slow* impairment: at the touch, or under the aggressive
fill model, a 50% drawdown inside 30 days runs 68–76%.

**With the brief's hope that the five coins hedge.** They do not, and the
reason is not the market — it is that we only hold one leg. The brief's
instinct was right that this is the most important unexamined fact; the answer
just runs the other way, and it comes with the lever that fixes it.

**With the surviving headline.** The $479/day base-model NET should **not** be
quoted to the operator. Quote **$271/day of rebate plus the fills' $0**, i.e.
plan on $271/day and 111%/day, and treat anything above it as unearned.

---

## WHAT I COULD NOT DO

* **Only three UTC days of book data exist** (2026-09-04 -> 06; Coin Race book
  data starts 09-04). A day-block bootstrap has n = 3 and cannot carry an
  interval; the day-level t-interval with 2 dof is the best available and it is
  wide ([+71, +882]/day).
* **Could not re-score with the tapered tick** — the cached sims use the flat
  1c tick. Stated as a conservative bound rather than corrected.
* **The 2x ambiguity is untouched.** "Your snapshot score is your share of the
  yes side PLUS your share of the no side" is implemented here as the
  conservative *average*. If "plus" is literal, **every rebate figure in this
  report doubles**: $543/day rebate, $750/day net, 222%/day on capital. Still
  unresolved.
* **Criticism A (competitive response) is not modelled.** Every rebate figure
  assumes nobody reprices when our 50 lots appear. That is the largest untested
  assumption behind the surviving number, and it belongs to Job A.
* **All fills are simulated.** No live orders were placed and no real money was
  used. Only authenticated read-only GETs were made.
* 55 markets were dropped for falling in a truncated collector hour and 20 for
  covering < 700 s of their window; 1,235 of 1,310 survive, and all 247 usable
  windows have all five coins present.

---

## THE ONE NEXT STEP

**Simulate the balanced-residual variant as an actual QUOTING RULE, on the tape
we already have.** Instead of letting fills land where they land, skew or pull
quotes on the coins where we are already filled and lean into the ones where we
are not, so the residual ends up equal and same-signed across all five coins.

The hindsight re-allocation above (section 3) puts the prize at **sd −26% and
the worst window halved (−$70.13 -> −$34.50)** with the P&L benefit discarded
as an artefact. That is worth having on its own, and it costs no rebate,
because the rebate pays for resting size and is blind to the residual's shape.
The reason it must be re-run as a rule and not a re-allocation is that skewing
quotes changes which fills you get — the same objection the critic makes in
criticism A — so the honest version has to pay for itself inside the fill
engine. It needs no new data and no live orders: `rebate/sim.py` already
carries the quoting logic and would need a per-window inventory-aware `want`
price.

If it works, the strategy becomes "$271/day of rebate with the inventory tail
engineered out", which is a far better product than "$479/day +/- $400".

---

### Reproduction

```
C:\Users\Joe\AppData\Local\Temp\kals-work\jobB\
  core.py       accounting + rebate formula (900-snapshot denominator)
  selftest.py   20 assertions, run BEFORE any tape        -> 20 passed, 0 failed
  build.py      per-market records, 3 fill models         -> recs.pkl
  decomp.py     exact matched/residual split (asserted 1e-6)
  dist.py       per-window marginals
  corr.py       five-coin hedging structure
  moves.py      per-contract adverse-move distribution
  daily.py      per-day + block bootstrap + worst runs
  sig.py        t-tests, concentration, hedging algebra
  sizes.py      real S=25/50/100 scaling
  ruin.py       equity paths, drawdown, ruin
  joint.py      the joint table + market-clustered SEs
  artefact.py   the artefact checks
  lever.py      the balanced-residual counterfactual
```

Source pickles are the prior job's cached sims in
`C:\Users\Joe\AppData\Local\Temp\kals-work\rebate\` (`sim_distq_sweepq.pkl`,
`sim_dist2_replenish.pkl`, `sim_distsw_sweep.pkl`, `sim_distq25_sweepq.pkl`,
`sim_distq100_sweepq.pkl`). Settlements re-derived from
`C:\kals\kalshi_data\market_lifecycle_v2` (read-only). Incentive-programme
parameters from the cached `/incentive_programs` pull at
`C:\Users\Joe\AppData\Local\Temp\kals-work\job2\programs.json`.

**Collectors verified alive after every heavy step:** `kalshi_collector.py`
(pid 3381772) and `crypto_feeds.py` (pid 3385232) both running at start and at
finish. Free disk 52 GB throughout.
