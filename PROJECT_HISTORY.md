# PROJECT_HISTORY.md

Split out of `CLAUDE.md` on 2026-09-13 to cut what loads into context on every
single turn. Nothing here was changed, only moved.

**Read this file when** you need: why an approach was killed, which
measurement artefacts have bitten before, the two unreconciled thesis
versions, the kill-criteria change log, or the 2026-09-06 state snapshot.
Operating rules, hard rules, the resource protocol and every AMENDMENT stayed
in `CLAUDE.md` because they bind on every turn.

# Project history (appended 2026-09-06)

The sections below were supplied by the operator. Where the repo or the tape
could check a claim, it was checked; where they disagree, **both readings are
recorded and neither is picked**. Resolve the flagged items before relying on
either version.

## Operating rules

1. Never place, modify, or cancel a live Kalshi order. Read-only only.
2. Never move real money.
3. Do not resurrect a killed approach without evidence that specifically
   overturns the stated reason it was killed.
4. Do not touch the running collector in `C:\kals` — collecting since
   2026-08-25, and the data is not reproducible.

## Killed approaches

- **Dutch-book basket arbitrage** — killed structurally. The fee function peaks
  at `p = 0.50`, which prices out balanced baskets. Monte Carlo showed passive
  legging needs implausible fill rates.
- **Exhaustive-basket arbitrage** — killed empirically. A 16-hour run priced
  467,907 ladders and found no usable locks. Two false-positive classes: (a)
  categorical markets, where Kalshi's `mutually_exclusive` flag means
  *at most one wins*, not *exactly one wins*; (b) far-dated ladders, where
  sub-$1 totals are the time value of money rather than mispricing. Genuine
  numeric ladders ran ~13c too expensive at the median, best +7c at depth 0-1.
  The dead-bracket effect is real but insufficient.
- **15-minute scalping in low-volume markets** — superseded by the
  research-first plan.
- **Crypto delta-neutral basis trades** — yields below hurdle, and
  auto-deleveraging events destroyed correctly-hedged positions in late 2025.

*Repo note, not a contradiction:* `research/strikes.py` independently found
that the 15-minute crypto series carry **one strike per window**
(`strike(N+1) == settle(N)`), so ladder/basket arbitrage is **undefined** for
this product rather than merely unprofitable. The kills above concern
categorical and numeric-ladder markets elsewhere on Kalshi. The same scanner
applies unchanged to the Coin Race legs, which must sum to 100c.

## Confirmed mechanics

- Settlement = 60s BRTI average. Strike = opening 60s TWAP.
  `Var(settle - strike) = 880 * sigma^2`.
  *Verified:* `research/settlement_math.py` checks 880 against the
  continuous-time approximation. The strike identity is the same fact as
  `strike(N+1) == settle(N)` — abutting windows make the opening TWAP of one
  the closing TWAP of the last.
- Fees quadratic: `0.07 * P * (1-P)`, multiplier 1.
  *Verified:* `engine.fee_per_contract`, AND against real charges in the
  operator's own fill history (12.37 contracts at yes 0.16 charged $0.116400;
  `0.07*0.16*0.84*12.37 = 0.116400` exactly).
- **Makers pay no fee ON OUR SERIES — but this is a PER-SERIES property, not a
  platform one, and it must be checked before touching any new family.**
  `GET /series/{ticker}` returns `fee_type`, enumerated `quadratic` |
  `quadratic_with_maker_fees` | `quadratic_with_combo_maker_fees` | `flat`.
  Scanned 2026-09-06 across **13,839 series**: 13,676 `quadratic`, **160
  `quadratic_with_maker_fees`**, 3 combo. `KXCRYPTOLEAD15M`, `KXGOLD15M`,
  `KXBTC15M` and `KXTTELITEMATCH` are all plain `quadratic`, so makers pay
  nothing there. The 163 that DO charge makers are overwhelmingly Sports
  (`KXNFLGAME`, `KXMLBGAME` at multiplier 0.5, `KXINDY500`, `KXNFLMVP`) and
  would cost a maker `0.0175*P*(1-P)` = **0.44c at the money — larger than any
  maker edge this project has measured.** Checking `fee_type` is a one-line
  call and is now the FIRST thing to run on any new series.
- Tick grid `tapered_deci_cent`: 0.1c below 10c and above 90c, 1c between.
  *Verified:* `engine.tick_at`.
- WebSocket `cfbenchmarks_value` requires the param `index_ids`
  (`BRTI`, `ETHUSD_RTI`, ...). *Verified:* `kalshi_collector.py`.
- `/historical/*` is stale to ~2026-06-24 and ignores `series_ticker` on
  trades; use `/markets?status=settled` and `/markets/trades`.
  **Not verifiable from this repo** — no stored response proves the staleness
  date, and checking it needs a live API call.

## Known artefacts — do not repeat

1. **Truncation.** An earlier result claimed 26 mispriced cells with 21c
   edges. That was `limit=200` returning only each market's LAST 200 prints.
   Any analysis paging the trades endpoint must confirm full coverage first.
2. **Sweep-level reporting.** Kalshi reports a single sweep as multiple prints
   at different price levels. **SETTLED 2026-09-06 on `ts_ms`** over 12,000,000
   trades (`research/informed.py`, `sweep_shape()`):

   | multi-price (ticker, instant) groups | `ts_ms` | whole second | control |
   |---|---|---|---|
   | groups | 6,330,052 | 1,225,485 | 1,661,130 |
   | trades per group | **1.90** | **9.79** | 6.11 |
   | multi-price share | 10.7% | 57.2% | 76.9% |
   | single-sided AND monotone | **96.6%** | 28.3% | **12.9%** |
   | consecutive exchange `seq` | 99.8% | 23.2% | 32.8% |

   **The answer is PER LEVEL, and it rests on the shape, not the count.** At
   the true instant, multi-price groups are one-sided monotone ladders walking
   the taker's own direction over consecutive `seq` — a book being walked. The
   control (groups of trades ADJACENT in time but never simultaneous, drawn to
   the same size distribution) scores 12.9%, so the test is reading sweep
   structure and not merely that a busy book trends.

   **The earlier 59.0% / median-8-legs figure was wrong and must not be
   quoted.** It grouped by `msg.ts`, which is exactly `floor(ts_ms/1000)`, so
   "same instant" meant "same second". Its own arithmetic gave it away:
   4,000,001 trades in 401,591 groups is **9.96 prints per "instant" on one
   ticker**, where the true instant gives 1.90. Grouped by second, only 28.3%
   of multi-price groups have sweep shape at all. `ts_ms` is on 100% of trade
   messages, `created_time` on 0%, and `edge.load_trades` still reads `ts` —
   it was not changed, because that timestamp is what every other stage is
   calibrated against (see the reference-quote staleness item in `HANDOFF.md`).

   Consequence: the touch leg of a sweep is its own print at its own price and
   is already inside `at-touch`, so **the at-touch maker P&L stands as
   measured and the -0.42c branch is closed.** A per-print statistic can still
   weight one taker decision several times (median 4 legs, max 342).

   **Scope matters here, and getting it backwards destroys a valid result —
   see the contradiction flagged below.**

## Thesis state — TWO VERSIONS ON RECORD, NOT RECONCILED

**Version A (operator, and `RUNBOOK.md` lines 45 and 128):** full-tape
calibration on 2.1M trades across 450 markets shows the market is efficient.
71 price/time cells, mean `t = -0.008`, sd 0.775, only 3 cells at `|t| >= 2`
against 3.2 expected by chance; the single `t = 4.1` cell flips sign in
adjacent time buckets. Confidence in a tradeable edge: **~3-5%**.

**Version B (this repo's 2026-09-06 run outputs):** the sample is now
**38,519,252 trades over 14,485 markets with quotes and 10,796 with
settlements** — roughly 18x the trades and 24x the markets of Version A. On
that tape two results sit outside their own market-is-right nulls, out of
sample:

- `pin.py`, tau <= 20s, edge floor 0.5c: realised **+2.54c, t = +5.0** on 335
  closes against an MDE of 1.54c, with sigma recalibrated only on earlier
  closes. Its `t` has risen on every successive tape: 3.0, 3.7, 4.5, 4.9, 5.0.
- `informed.py`, fills at the touch: maker **+0.48c, t = +6.4** on 17,139,809
  fills over 1,071 closes, random-sign control clean at `t = -0.9`.

**These cannot both be current.** Version A's numbers are real but were
measured on a sample ~5% the size of today's, and the two live results
post-date it. Do not quote 3-5% as the standing confidence without saying
which sample it refers to, and do not quote the new results as settled either
— see `HANDOFF.md` (newest section first) for their caveats, chiefly that
`pin`'s tail is thin (1 flip in 262, headroom 1.9x) and the maker result's
**capacity is unmeasured**.

## Contradictions flagged, not resolved

1. **Cause of the 26-cell artefact.** The operator attributes it to
   truncation (`limit=200`). `RUNBOOK.md` line 20 attributes it to the wrong
   clustering unit — trade-count statistics wrong by ~14x. Both are real bugs
   and both were present; which produced that specific number is unresolved.
   Fixing only one is not sufficient.
2. **Deduplicating sweeps.** The operator's rule is "deduplicate sweeps into
   single economic trades before computing anything." That is right for
   **taker-decision** statistics, and wrong for **maker-fill** statistics.
   Per-level reporting is precisely why the at-touch maker measurement is
   valid: a quote resting at the touch is filled by the touch **leg**, which
   is its own print at its own price. Collapsing a sweep to one VWAP print
   would hide that leg in the deeper buckets and turn a measured +0.48c into
   roughly -0.42c — the exact question `sweep_shape()` was built to settle.
   Note also that this project already controls the "one event counted many
   times" problem for *inference* by clustering on close time and reporting
   `n` as markets or closes, which is a stronger fix than deduplication.
   **Apply per scope; do not apply globally.**
3. **Short-cadence equity markets.** The operator states none exist, so the
   half-fee lever is unavailable at frequency. `HANDOFF.md` line 1488 states
   the opposite from the authoritative `frequency` field: the true
   `fifteen_min` universe is 16 series — 14 crypto plus **`KXINX15M`
   (S&P 500) and `KXNDQ15M` (Nasdaq 100)**. `IDEAS.md` B3 lists their fee
   schedule as an open, cheap, high-value check. If the repo is right the
   lever may exist; if the operator is right B3 should be struck. One API call
   settles it.
4. **"Model vs book mid is the last test."** That test has been run.
   `endgame.py` and `pin.py` both score model fair value against the book, and
   the result is **not flat** — see Version B. Either this open question
   predates those stages and is already closed, or it means something narrower
   than `pin` measures. Clarify before applying the stated kill.

## Kill criteria

### CHANGE LOG — the bar has moved once, and the move is on the record

**The reason tonight's result counts is that the bar was set before the number
was seen. That is not erased by revising it, so both versions stand here with
their dates and the reason for the change.**

#### 2026-09-06, ORIGINAL (operator, set before any capacity measurement)

> **Threshold:** net +$50/day, after fees, at a size the depth measurement
> shows is actually fillable, sustained over the forward test. Rationale: I am
> not chasing a big number, I am chasing something that comes out on top
> consistently. If it clears $50/day honestly it is worth deploying small and
> scaling on evidence.

#### 2026-09-06, REVISED (operator, set AFTER seeing pin's measurement)

> **Threshold:** positive after fees at a fillable size, demonstrated
> out-of-sample on fresh tape, with a maximum drawdown I can sit through. Size
> is capped by drawdown, not by a dollars/day target.

#### 2026-09-06, FINAL — "CONSISTENTLY" DEFINED (operator, same day)

> **Threshold: positive expectancy.** "Consistently" means *likely to come out
> on top if it runs its course*. Not a t-statistic. Not a dollar target.

**By this definition `pin` is a PASS**, and was a pass all along: its 95%
bootstrap interval on per-close P&L excludes zero, at every fillable size
tested, on both the close-level and the day-level block bootstrap.

**Why it changed, twice, in one day — and this is the honest account.** The
first bar, +$50/day, came off a menu the assistant offered. It answered "is
this a business?" when the question was "is this real?", and it was anchored to
an arbitrary 50 contracts. That framing nearly threw away a working strategy.
The operator's words: *"the $50/day bar was a bad target and it nearly threw
away a working strategy; I'd rather be corrected than agreed with."*

**No measurement was re-run, re-fitted or re-weighted at any point.** Every
number is exactly as first computed. What changed is the question. Both earlier
bars stay above so that anyone reading later sees precisely what was promised
before the data spoke.

### THE UNITS. This is not cosmetic — the old unit was misleading.

At low hundreds to ~$1,000 of capital, absolute `$/day at 50 contracts` is the
wrong measure and actively misled this project. **Every result from 2026-09-06
onward is reported as:**

1. **$ per contract per day**
2. **PEAK CONCURRENT capital required** — positions here are held ≤60s and
   closes are 15 minutes apart, so exposure never overlaps across closes. Peak
   concurrent is the largest single close's notional, not the day's turnover.
3. **% return on capital deployed**

Measured for `pin` (tau≤20, one-per-close, cap 50): peak concurrent capital
**$49.70**, **$30.22/day** mean, **67.2% per day on peak capital**, 10 of 11
days positive.

**The capacity-matching argument, and where it holds.** The operator's case is
that a ~30%/day return survives *because* it is capacity-limited — no serious
player deploys $100 to make $33, so nobody competes it away. **That is sound
and it is the standard reason small-capacity edges persist.** Two caveats
recorded for honesty:

- Capacity-limitation explains why an edge *could* persist; it is not evidence
  that this one is real. A single retail script, not a fund, is the competitor
  that matters here — and the race question is what decides it.
- Return on capital is high partly because capital turns over ~37×/day. The
  binding constraint is **opportunity count × depth**, not capital. So % ROC is
  the right metric for *this* operator at *this* size, but it cannot be scaled
  by adding capital, and quoting it without that sentence would flatter it.

### The rest, unchanged from 2026-09-06

- **Minimum sample:** 500 fired closes of FORWARD tape, collected after the
  rule is frozen, scored standalone rather than pooled with the 336 we have.
  At ~37 fired closes/day that is ~14 days. Freeze the rule in writing before
  the window starts.

- **Result that ends the project:** not the death of a strategy — the death of
  the search. `pin` dies if the forward test at n>=500 fails to beat the
  mid-null. Market-making dies if the queue simulator puts expected fills x
  $0.005 under the threshold at max fillable size. Either one dying kills that
  strategy only. The PROJECT ends if both are dead AND 60 further days pass
  with no new idea clearing its own null. Pivoting to a new idea is expected,
  not a failure.

### Three consequences that bind

1. **"$/day" means fillable $/day.** Any figure quoted against the threshold
   must be at a size the resting-depth measurement supports, not at an assumed
   50 contracts.
2. **The forward window has not started.** It starts when `PREREG_pin.md` is
   signed. The 336 closes already measured are NOT part of it.
3. **A bar is never moved after seeing a result without saying so loudly and
   dating it.** Changing the question is legitimate. Changing the answer
   quietly is not.

---

