# Where this is, in plain terms

_Updated after the code-review pass and the detectability work._

## The goal, unchanged

A bot that makes consistent money on markets that resolve every 30 minutes or
less. Kalshi's 15-minute crypto series is where the data is, but nothing here
is committed to Kalshi.

## The single most important thing found so far

Not an edge. A measuring stick.

Twelve crypto series close **at the same instant** and are ~0.8 correlated. So
the independent unit is the **close time**, not the market. Four close times an
hour. A day of recording is **96 observations**, not 1,152. Every "n = 3,456
markets" in an earlier report was overstating the sample by about twelve times.

Run through that, here is the smallest edge the P&L backtest could actually
detect, at 80% power:

| recording | independent obs | smallest detectable edge | after correcting for multiple tests |
|---|---|---|---|
| 1 day | 96 | 2.9¢ / contract | 3.8¢ |
| 3 days | 288 | 2.1¢ | 3.0¢ |
| 7 days | 672 | 1.5¢ | 2.3¢ |
| 30 days | 2,880 | 0.8¢ | 1.3¢ |
| 90 days | 8,640 | 0.5¢ | 0.8¢ |

The edges worth trading in this market are **0.5–2¢ per contract**. Read the
table against that:

> **Replayed P&L cannot confirm the strategy at any recording length you are
> going to have.** Confirming a 1¢ edge honestly needs about 45 days of
> continuous recording, and the disk gives about 10.

That is not a reason to stop. It is a reason to stop expecting the answer to
come from the backtest, and to get it from a **mechanism you can point at**
instead — something measured per second rather than per close.

## Which is why the per-second questions are the whole game

| kind of question | observations per hour | tools |
|---|---|---|
| "did this have made money" | **4** | replay, edge, cross |
| "does the book lag the index" | **3,600** | leadlag, feeds, proxy, pathstats, openwindow, implied |

Nine hundred times the data. That is the reason `PLAN_V3` ranks the plumbing
questions above the opinion ones — and now it is a measured reason rather than
a hunch. A lead-lag beta is measurable to 0.008 on three days of feed. A P&L
edge is not measurable at all.

**The deploy decision has to rest on a pre-trade mechanism**: "the book follows
the index by k seconds, here is the coefficient, here is what k seconds is
worth given that settlement is a 60-second average." Not on "the backtest made
money."

## Two things that were quietly inflating every result

Both found by simulating the estimators against known answers.

1. **The lead-lag t-statistic was being read as a z.** `feeds.py` and
   `leadlag.py` build their standard error from ~20 blocks, so it is a t on 19
   degrees of freedom. Comparing it to 1.96 rejects a true null 7.7% of the
   time, not 5%; at |t| = 4 a result is **twelve times** more likely to be
   noise than it reads. Fixed — both files now print the degrees of freedom and
   the correct p-value.

2. **One `go.py` run emits about 294 t-statistics.** At the usual threshold, 15
   of them are expected to fire on noise alone. The corrected bar is **|t| =
   3.8**, not 3. Anything between is a lead to re-measure, never a finding.

And one that cannot be fixed, only known: the per-cluster P&L is a few binary
payoffs near 95¢, so its average is skewed and its t is **anti-conservative at
small samples** — a true null fires 12.6% of the time at 60 clusters, 8.6% at
150, 4.0% at 1,200. A day of recording is 96 clusters.

## The code review

Fourteen findings, all fixed, each with a test that fails without the fix. The
severe ones, because they show the shape of the risk here:

- **`book.py` discarded every order-book update.** It read the whole delta
  channel before opening the first snapshot file, so 400 deltas rebuilt 1 book
  state instead of 401. The queue-depth number that killed the maker strategy
  was measured on books that had never had a delta applied.
- **`edge.py` priced eleven series off bitcoin.** It scored every market
  against whichever index loaded first. Cost of the bug, measured: **+6.13¢ per
  contract at t = 4.9 against two books that are both exactly fair.**
- **`chain.py` differenced across holes.** `build_chains` splits on gaps
  specifically so we never do that, and the next function concatenated the
  chains back into one list.
- **`chain.py` could delete its own history.** A failed API pull assigned `[]`
  over a good cached series and wrote it.
- **`settlement_math.py` could not fail.** `go.py` called it with no flag; it
  printed the word FAIL inside its own output and exited 0. The first gate in
  the run was decorative.
- **`engine.py` leaked committed capital.** Buying YES then NO netted the
  position to zero, so settlement returned early and never released the cash;
  the exposure cap ratcheted shut for the rest of the session.
- **`pathstats.py` invented close times** from the last quote, mis-stamping
  every time-to-close. Demonstrated: a tape truncated 600s early yields 200
  honest rows, or 2,000 fabricated ones each labelled ten minutes wrong.

Nothing here was exotic. Every one of them produces a *confident* wrong answer,
which is the only kind that costs money.

## Confidence, honestly

- **That the tools now measure what they claim: high.** Eighteen self-tests,
  each planting a known answer and checking it comes back. Twenty-plus
  measurement bugs have been caught this way, including five in the
  detectability code itself, four of which were mine and written this week.
- **That an exploitable edge exists: unknown, and that is the honest answer.**
  Nothing has been measured on real data yet. The tools are ready; the data is
  on your machine.
- **That if an edge exists we will find it at this data volume: moderate, and
  only for the per-second questions.** The per-close questions are out of
  reach and will stay out of reach.
- **That a found edge survives fees and adverse selection: low until measured.**
  The fee alone is 0.33¢ at 95¢. Hedging with perps is closed permanently —
  it costs 10.9¢ (900s) to 98¢ (30s) per contract against edges of 0.5–2¢.

## What actually happens next

1. Run `research/power.py` first, with your real recording length. It tells you
   which stages in `RESULTS.md` could have said anything at all.
2. Run `go.py`. Send back `RESULTS.md`.
3. Read every stage against its detectability line. A stage below its line
   produced **no information** — do not record it as "no edge found".
4. If something survives at |t| > 3.8, do not trade it. Re-measure it on data
   recorded *after* it was found. Fresh data beats every correction.

## Standing rules

- Nothing in this repository places, amends, or cancels an order, and no flag
  enables one.
- Never report a number that was not measured.
- `n` is a count of markets or close-time clusters. Never trades.
- Every large edge this project has produced so far has been a measurement bug.
  Treat anything eye-catching as a bug until it survives its own null.
