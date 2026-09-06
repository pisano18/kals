# REFUTER — JOB A queue simulator — Lens 3 of 3: the statistics and the arithmetic

Run 2026-09-06 on the operator's box. Everything below was executed, not read.
Scripts: `C:\Users\Joe\AppData\Local\Temp\kals-work\refute3\{decomp,markout,orient,spread,variants}.py`

**Verdict: REFUTED.** Not on the fill count, and not on the bootstrap — both of
those reproduce exactly. Refuted on the one arithmetic check the report used to
decide the number was not too big, and on what the money actually is.

---

## PART 1 — what I could NOT break (stated first, because it is most of it)

I re-ran the pipeline from my own script against the same cached book and the
same trade tape, all 11 cached days, and reproduced the headline to the cent:

| quantity | report | my independent rerun |
|---|---|---|
| closes / span / closes-per-day | 883 / 10.16 d / 86.9 | 883 / 10.156 d / 86.94 |
| contracts filled S=1 | 412,373 | 412,373 |
| contracts filled S=50 | 12,246,316 | 12,246,316 |
| total P&L S=50 | $114,663 | $114,662.98 |
| $/day S=1, 95% close bootstrap | $309 [+216, +402] | $309 [+217, +402] |
| $/day S=50, 95% close bootstrap | $11,290 [+8,027, +14,529] | $11,290 [+8,070, +14,490] |
| no-camp S=50 | $6,188 [+4,163, +8,225] | $6,188 [+4,184, +8,239] |
| placebo 1c behind, S=50, contracts | 7,532,977 | 7,532,977 |
| concentration S=50 top5 / top10 / top25 | 8% / 14% / 30% | 8% / 14% / 30% |
| drop top 10 / top 25, S=50 | $9,814 / $8,113 | $9,814 / $8,113 |

(interval differs in the third digit only because I used 5,000 bootstrap reps
against the stage's 20,000.)

On the four things this lens was told to check:

1. **The bootstrap IS over closes, not trades.** `boot_ci(mpc, cpd)`
   (`queuesim.py:289`) resamples the per-close money vector built over
   `sorted(res["closes"])` — 883 distinct close timestamps, each the sum over
   the ~9 markets settling on that quarter hour. That is the clustering unit
   CLAUDE.md rule 4 requires. `clustered()` (line 321) equal-weights the same
   883 clusters for the per-contract t-stats.
2. **A day-block bootstrap — which the report did NOT run and which `pin` did —
   does not change the verdict.** I ran it: S=1 $285/day 95% [+203, +373];
   S=50 $10,424/day 95% [+7,550, +13,466], n = 11 days. Per-day totals at S=50:
   7801, 3089, 10849, 14545, 15285, 20540, 8959, 12068, 11882, 6215, 3429 — all
   eleven days positive.
3. **Concentration was really measured**, and reproduces exactly (above).
4. **No point estimate is being read as a pass at the $50 boundary.**
   `verdict()` (line 311) tests `b["day_lo"] >= 50`, the bootstrap LOWER bound,
   and the self-test checks that a [44, 57] interval must read INCONCLUSIVE.

**Units**, since this lens was told to check them:

* **86.9 closes/day is BELOW the product's true 96/day** (4 per hour × 24). The
  tape holds 883 of the ~975 closes its own 10.156-day span implies. Scaling by
  86.9 is therefore *conservative*: mean-per-close × 96 gives $12,466/day at
  S=50, and total ÷ 11 calendar days gives $10,424/day. This error runs against
  the report's own case, not for it.
* **`MAKER_CENTS = 0.48` is cents per contract**, print-weighted and
  close-clustered (`informed.py:482`, `maker = -sgn*(Y - price_c)`, one value
  per print). Applying it to a pooled contract count in the `$/day at +0.48c`
  column is a weighting mismatch, but a small one — it is not the defect.
* Trade size really is contracts: raw `count_fp` arrives as `"6.00"`, `"19.00"`,
  `"75.00"`, same unit and scale as the book's `yes_bid_size_fp`. No 100× error.

**Orientation checks — so the number is NOT a sign flip:**

* Book: `bid < ask` on **1,395,520 of 1,395,520** cached market-seconds, and the
  cache matches the raw ticker channel row-for-row on a spot check.
* `outcome_of()` is not inverted: mean LAST observed book mid is **95.33c for
  outcome 1** and **4.45c for outcome 0**; 97.8% sign agreement on 1,690 markets.
* `taker_side -> BID/ASK` is right: prints assigned to BID sit on the previous
  second's bid 1,449,239 times against the ask 368,688; assigned to ASK, on the
  ask 1,499,968 against the bid 377,889.
* `python queuesim.py --selftest` is genuinely green — 26 checks, mutation check
  included. **But all 26 test fill MECHANICS.** Nothing plants a world where the
  maker's settlement P&L must be zero. Check (d) plants +40.000c per contract
  and recovers it; its companion control scrambles the sign **per fill**, which
  destroys per-market accumulation and therefore cannot detect an artefact that
  lives in an accumulated position. The estimator has been shown able to reject
  a spurious *fill rate*, never a spurious *edge*.

---

## PART 2 — THE DEFECT

### 2a. The central artefact check compares two differently-weighted means, and fails when weighted consistently

The report's item 6 — "the one that matters most" — measures the population the
fills are drawn from and concludes:

> "our queue-selected fills earn 5% more than the population at S=1 and 49% more
> at S=500"

Both sides of that comparison are **close-equal-weighted**. The dollars are not.
Weighted the way the money is actually made — pooled, per contract — on the same
11 days through the same code path:

| per contract | report (close-clustered) | POOLED (volume-weighted) |
|---|---|---|
| whole at-touch population, exact-1c grid | **+0.774c** | **+0.4337c** |
| our fills, S=1 | +0.811c (+4.8%) | +0.7608c (**+75%**) |
| our fills, S=50 | +1.052c (+36%) | +0.9363c (**+116%**) |

The population's per-print figure moves the same way: report +0.781c, pooled
**+0.5619c**.

So a quote that **always joins the back of the queue** earns **more than twice**
the per-contract rate of the flow it is standing in. The report's check was
built to detect exactly this and could not see it, because the close-clustering
that is right for a *t-statistic* is wrong for a *reconciliation*.

The same mis-weighting inflates the report's defence of the magnitude — "we are
only 2.5% of a $455,786/day pool":

| | report | recomputed at the pooled rate |
|---|---|---|
| at-touch maker pool, 598,293,195 contracts | × 0.774c = $4.63M = **$455,786/day** | × 0.4337c = $2.59M = **$255,494/day** |
| our S=50 share of the money | 2.5% | **4.4%** |
| our S=500 share of the money ($50,465/day) | not stated | **19.8%** |

Money share against volume share, every size — 0.069% / 0.575% / 2.05% / 3.31% /
9.67% of at-touch volume, for 0.12% / 1.17% / 4.42% / 7.20% / 19.8% of the money
— is a flat **~2.0×** the population rate. That ratio is the artefact, and it is
invisible in the report because the two numbers being divided were weighted
differently.

### 2b. "The arithmetic reconciles, and it is the half-spread" divides a volume-weighted P&L by a TIME-weighted spread

The report's reconciliation:

> "mean spread 2.52c when the best bid is in 10c-90c ... A ~2.5c mean spread
> implies a ~1.25c half-spread and +0.78c sits inside it. **The arithmetic
> reconciles, and it is the half-spread, not a new edge.**"

I reproduced the 2.52c: it is **2.640c** over 4,632,107 market-seconds with the
bid in band — a **time**-weighted mean, with **median 1c**, 52.1% of seconds at
1c or less and only 2.0% at 10c or more. A maker never collects the spread
standing while nothing trades. Volume-weighted at the instant a trade arrives,
on the identical rows:

| half-spread, volume-weighted | cents |
|---|---|
| every at-touch print, exact-1c grid | **+0.5317** |
| queuesim's own fills, S=1 | +0.7436 |
| queuesim's own fills, S=50 | +0.6876 |
| the figure used for the reconciliation | *1.26* |

Median spread at our own fills is **1c**, and **81.8%** of our filled volume sits
at a spread of 1c or less.

**The repo's own prior stage already said so.** `results/RESULTS_informed.md`
line 132, the `filldepth/at-touch` row, derives the half-spread as
`maker + mkS = 0.48 + 0.02 =` **0.50c**. The queuesim report's 1.26c contradicts
informed.py's at-touch half-spread by 2.5×; 0.50c agrees with my 0.53c to a
hundredth of a cent.

So the half-spread does not cover the number. The exact decomposition (identity
verified to the cent, 11 days) shows what the rest is:

| | realised /contract | = half-spread | + markout mid → settlement |
|---|---|---|---|
| population, every at-touch print | +0.4337c | +0.5317c | **−0.0979c** (healthy adverse selection) |
| our fills, S=1 | +0.7608c | +0.7436c | +0.0172c |
| our fills, S=50 | +0.9363c | +0.6876c | **+0.2487c** |

The markout term **flips sign relative to the population and grows with quote
size**. A larger passive quote must be MORE adversely selected, not less. The
report saw the per-contract rate rising with S and blamed queue camping; the
decomposition says the half-spread part FALLS with S (0.744 → 0.688, as
expected) and the entire rise sits in the settlement term.

A check needing no settlement at all confirms the population's direction. Signed
maker markout `mid(t+h) − mid(t−1)` on 126,384,557 at-touch contracts (2 days):

    h        1s       5s      15s      30s      60s     120s
    c    -0.264   -0.341   -0.365   -0.329   -0.304   -0.295

The book itself says a maker at the touch **loses ~0.3c of mid value on every
contract filled**. Half-spread 0.53c minus that is ~+0.2c per contract — the
population's +0.43c order of magnitude, and nowhere near the +0.94c to +1.15c
the simulator credits itself at S ≥ 50.

### 2c. At the headline size the P&L is not market-making revenue — the net cash flow is NEGATIVE

Exact accounting identity, verified to the cent:
`P&L = terminal value of the inventory left at settlement + net cash`

| S=50, 11 days, headline variant | |
|---|---|
| net cash (sold − bought) | **−$5,768.97** |
| terminal inventory value (`Σ net_market × Y`) | **+$120,431.95** |
| total P&L | +$114,662.98 |

The simulated market maker **pays out more than it takes in**, and **105% of the
reported profit is the settlement value of the inventory it is left holding**.
That is a directional position, not a spread. Under the no-camp bound it is
still 71% ($44,676 of $62,845). At S=1 the split is honest ($2,045 cash /
$1,092 inventory) — a point in favour of the S=1 row specifically — but the
report presents all twenty cells as one result and quotes $11,290 and
$50,465/day as market-making.

And that position lands on the right side of the outcome far more often than a
passive quote can. Over the whole at-touch population (2 days, no simulator
involved, just every print):

    maker's implied net, summed over markets settling YES : +1,589,385 contracts (LONG the winner)
    ... over markets settling NO                          : -4,310,570 contracts (SHORT the loser)
    total maker net                                       : -2,721,185
    outcome-INDEPENDENT expectation for the YES bucket    : -1,344,491

The mechanical expectation is the opposite sign: a market walking up to YES lifts
the maker's ask, so a maker ends SHORT in YES markets. The observed +2.93M
contract swing toward "correct" exposure is 3.3× the entire at-touch P&L for
those days.

### 2d. The report's own placebo contains the refutation — it only reported the fill count, never the money

The report ran a quote one cent behind the touch, saw 61.5% of the on-touch fills
and wrote "61.5% at one tick is NOT a clean zero and I am not going to call it
one." It never priced it. I did, S=50, same 11 days:

| S=50, 11 days | at the touch (headline) | at the touch, no camp | **1c BEHIND the touch** |
|---|---|---|---|
| contracts | 12,246,316 | 7,528,235 | 7,532,977 |
| $/day | +11,290 | +6,188 | **+3,276** |
| pooled c/contract | +0.9363 | +0.8348 | **+0.4416** |
| volume-wtd half-spread | +0.6876 | +0.6736 | +0.6974 |
| markout mid → settlement | **+0.2487** | +0.1612 | **−0.2558** |
| net cash (sold − bought) | **−$5,769** | +$18,169 | **+$246,550** |
| terminal inventory value | **+$120,432** | +$44,676 | **−$213,282** |
| inventory as % of P&L | **105%** | 71% | **−641%** |

Move the quote one tick and the P&L structure **inverts**. The behind-the-touch
quote behaves exactly like a real market maker: large positive cash flow from
spread capture, properly *negative* markout (−0.256c of adverse selection), and a
terminal inventory that LOSES money because it accumulates the loser — which is
what a passive quote filled by a market moving through it must do. Its net rate,
**+0.4416c per contract, is statistically the same as the whole at-touch
population's +0.4337c.**

The at-touch quote does the opposite in every line. Two quotes one cent apart
cannot have structurally opposite P&L composition unless something in the
on-touch construction is selecting on the outcome.

The control that was run cannot see any of this: `run()` scrambles the sign
**per fill** (`sh[close] += rng.choice((1.0,-1.0)) * pnl * q`), which destroys the
per-market accumulation. The right null for a hold-to-settlement strategy
scrambles the OUTCOME per market.

---

## What this does and does not overturn

* It does **not** overturn the fill count. 40,602 contracts/day at S=1 is
  reproduced and I found no defect in the queue mechanics themselves.
* It does **not** overturn the $50/day verdict *at S=1, on the criterion as
  written*. The criterion is `expected fills × $0.005`: 40,602 × $0.0048 =
  $195/day, and even the population's pooled +0.4337c gives $176/day.
* It **does** overturn the reported REALISED money at every size above S=1, the
  claim that the per-contract rate is corroborated by the population it is drawn
  from, the claim that it "is the half-spread", and the "only 2.5% of a big pool"
  defence.
* It **does** overturn the report's reading of its own risk. At S=50 and above
  this is not a spread business with an inventory by-product; it is an inventory
  bet with a spread by-product, priced by a close-level bootstrap that treats
  883 closes as independent draws while nine coins settle on the same quarter
  hour and consecutive quarter-hours share one crypto trend.

**The honest number to quote is S=1, no camping, at the population rate rather
than the realised one: 38,553 contracts/day × 0.4337c = $167/day — still above
the $50 line.** Every larger cell is contaminated by the selection measured
above, and the headline $294/day already carries ~35% of its money as terminal
inventory rather than spread.

**Recommended next measurement, before any rule is frozen:** re-run the stage
with the settlement term removed — mark every fill to the mid at t+300s instead
of to `Y` — and report that number as the maker result. If it collapses toward
+0.2c per contract, as the markout curve says it must, the capacity answer is
roughly a fifth of what is on the table.

---

## Resources

* Both collectors alive before, during and after every job:
  `kalshi_collector.py` pid 2708908 (25–26 MB), `crypto_feeds.py` pid 531268
  (14 MB). No `python.exe` was killed; nothing filtered on anything but my own
  scripts.
* Nothing written to `kalshi_data/` or `feed_data/`; both opened read-only.
* `replay.load_quotes` was NOT called. My heaviest process peaked at 490 MB and
  free RAM never went below 3.27 GB. Another agent's `survival.py` (462 MB) ran
  throughout and was left alone.
* Free disk 52.05 GB on C:, well above the 4 GB stop threshold.

## Like you're five:

Someone built a pretend shopkeeper that stands at the back of the queue offering
to buy and sell, replayed eleven real days, and said it makes $294 to $11,290 a
day. I checked their sums.

Their counting is right — I got the same fill numbers and the same dollars, to
the penny. But I split the money into two piles: the pile you earn from the gap
between your buying price and your selling price (that is what a shopkeeper
earns), and the pile you earn because of what you were left holding when the
race finished (that is a bet on the winner). At the big sizes, the shopkeeper
pile is *negative* — the pretend shop pays out more cash than it takes in — and
more than all the profit comes from being left holding the winning ticket. A
shopkeeper who always stands at the back of the queue cannot keep ending up with
the winning ticket. So that money is almost certainly a mistake in the pretend
version, not a real profit.

The clearest proof is their own control. They tried the same pretend shopkeeper
standing one penny further back, mentioned it filled a lot, and never checked
what it earned. I checked: it earns exactly the ordinary amount everyone else at
that counter earns, and it is left holding the *losing* ticket, which is what
should happen. Move the offer one penny and the whole shape of the money flips.
That is a sign the on-the-touch version is picking up something it should not.

## What I need from you:

Nothing, this job is complete. One recommendation for whoever reads it: do not
freeze the market-making rule on the realised-money column. Re-run the stage
marking fills to the book price five minutes later instead of to the settlement,
and use that as the maker number. If it lands near +0.2c per contract, as the
markout curve says, the capacity figure is about a fifth of what is currently on
the table — still above $50/day at S=1, but not the six-to-250× margin the
report claims.
