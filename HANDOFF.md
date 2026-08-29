# HANDOFF — read this first in a new session

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
at **+6.5c (t=4.1)** inside 60s rising to **+12.1c (t=6.4)** inside 15s — with
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

Self-test recovers a planted `sqrt(tau)` book at **beta = 0.991 [0.981, 1.015]**
and `sqrt(tau-39.5)` at 1.153, reads flat on a flat book, and separates a
genuine rising-vol *view* from an arithmetic *error* by the **pair** of betas
(a sqrt(tau) book reads 0.991/−0.446; a 40% rising-vol view reads 0.185/−0.175).

**It found a real bias in `implied.collect` on the way.** The 30-second
carry-forward inverts a stale quote through a `var_factor` that has since
collapsed: sd/sigma falls from 0.893 at tau=20 to 0.327 at tau=10, so a
30s-old quote at tau=10 returns **~6.8x** the sigma the quoter used — a
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
at 10c**: the tick goes 0.1c → 1c, so the cost of crossing jumps 10x in one step
while the gross edge barely moves. Below 10c the market only has to be wrong
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
