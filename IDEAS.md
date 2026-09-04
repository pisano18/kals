# The idea sweep — ranked, scored, and honest about what's already dead

Every idea here is scored on four things, because an idea that cannot be
tested with what we have is not yet an idea:

- **Mechanism** — what makes the price wrong.
- **Counterparty** — *who is on the other side, and why are they willing?*
  An edge with no answer to this is almost always a measurement bug.
- **Test** — the specific measurement, and what kills it.
- **Data** — on disk / needs collection / needs an account.

Ranked within tiers by (plausible effect) ÷ (minimum detectable effect).

---

## The three constants everything is scored against

**1. The fee is quadratic and the edge is not.** Taker fee is `0.07·p·(1−p)`,
largest at 50¢ (1.75¢) and vanishing into the wings (0.33¢ at 5¢). Makers pay
nothing. Any strategy priced at the money starts 1.75¢ behind.

**2. Almost every edge is zero at the money.** `d(fair)/d(log σ) = −z·φ(z)` is
exactly 0 at z = 0. A 50¢ binary carries no volatility information at all.
Peak sensitivity is |z| = 1, i.e. **16¢ / 84¢**.

**3. The wings are where making becomes possible.** Break-even uninformed
share `q = fee/(fee+h)`:

| price | fee | q at h=0.5¢ | q at h=1¢ | q at h=2¢ |
|---|---|---|---|---|
| 50¢ | 1.75¢ | 77.8% | 63.6% | 46.7% |
| 16¢ | 0.94¢ | 65.3% | 48.5% | 32.0% |
| 10¢ | 0.63¢ | 55.8% | 38.7% | 24.0% |
| 5¢ | 0.33¢ | 39.9% | 25.0% | 14.3% |

Needing 1 in 4 counterparties to be uninformed is a completely different
proposition from needing 4 in 5. **Every live thread in this project points
away from 50¢.** That convergence is the single most useful thing the
arithmetic has produced, and it was not obvious going in.

---

## 2026-09-04 — THE RE-GENERATION, under the relaxed goal

The user relaxed the goal: no longer "a flaw in the market", but ANY strategy
with positive expectancy after real costs. Twenty-one candidates were
generated from six lenses and each was audited by three adversaries
(arithmetic against the measured constants; duplication against this file's
graveyard; testability and power on the tape). Two died outright
(strike-formation gap at open; post-shock vol over-response — no reachable
MDE). The rest cluster into four families, ranked by profit x probability,
testability as the tiebreak:

**1. The pinned endgame** (`pin.py`, BUILT) — fair beyond 0.98 from locked
prints, quotes still on the wrong side of it. The panel's highest
confidence x edge cluster (four of the 21 candidates were this one idea).
The arithmetic skeptic killed one version's premise (there is no 1c floor —
ticks go to 0.1c in the wings) and `pin.py` does not rely on it.

**2. Follow the informed tail** (`informed.py` TAIL cell, BUILT) — the
+0.612c/t=54 markout, conditioned on size/burst/tau and run to settlement.
Est 0.7c against ~2.3c of taker cost; the tail decides, the pool does not.

**3. Conditional making** (`informed.py` HEADLINE + spread/burst/price
tables, BUILT) — the closest deficit to zero (-0.11c pooled). The skeptic's
strong counter, recorded so the real numbers are read against it: wide
spreads concentrate in exactly the price buckets whose markout is already
1.0-1.25c, so expect the spread cut to kill rather than save. Same run, free.

**4. Cross-strike dutch book** (`strikes.py`, BUILT) — not one of the 21;
needs no one to be wrong, only briefly inconsistent. Two fees charged, two
freshness tiers, episodes counted once.

**5. Queue position / fill-type decomposition** (C2; NEXT BUILD) — the power
auditor confirms decision-grade MDE from the now-trustworthy book; the
arithmetic auditor's caution stands: front-of-queue still eats every
through-sweep, so the decomposition decides, not the hope.

**6. Coin Race correlation** (collection STARTED — collector default now
includes KXCRYPTOLEAD15M/COMP15M; deploy = one file copy) — days of tape
needed before the first test.

**7. Hourly-crypto calibration via REST** (44 series, thousands of closes)
and **8. equities 15-min with a futures feed** — new machinery, ranked by
cost.

---

## TIER A — testable with data already on disk

### A1. Volatility under-response  ·  `research/voltiming.py`  ·  BUILT
**Mechanism** volatility clusters (confirmed, 5,195 windows) but implied vol
may not respond to it fully.
**Counterparty** whoever quotes σ off a slow or unconditional estimate. The
15-minute series are thin; nobody is running a GARCH per coin per quarter hour
for this size.
**Test** slope of `log(σ_realised/σ_implied)` on a backward-looking vol
forecast. Positive ⇒ under-response.
**Kill** slope indistinguishable from 0, or clears t>3 but the cents figure
misses the 1.44¢ hurdle at 16¢.
**Note** the intercept (systematic level error — `implied.py` already sees BTC
0.88, ETH 0.86) is much larger but much more fragile: any bias in our realised-σ
estimator lands entirely in it. The slope is immune to that. Report both, trust
the slope.

### A2. Maker uninformed share  ·  `research/maker.py`  ·  BUILT
**Mechanism** makers pay no fee; if enough flow is uninformed, the spread is
free money.
**Counterparty** bored/impatient retail versus informed takers.
**Test** signed post-fill markouts, 30–100× more powerful than replayed
settlement P&L (MDE 0.08–0.26¢ against a 0.5¢ target).
**Kill** measured `q` below the table above at every price.
**Upgrade waiting to be made** run it **per price bucket**. The current version
pools. Given the q table, the aggregate could fail while 5–10¢ passes
comfortably — and the aggregate is dominated by the mid-book where nothing can
work. This is the single highest-value small change on this list.

### A3. Tick quantisation in the wings  ·  NOT BUILT
**Mechanism** prices are integer cents. At 3¢ one tick is **33% of the price**
and the worst-case rounding error is 0.5¢ — larger than the 0.20¢ fee there.
**Counterparty** everyone, unavoidably: nobody can quote 2.4¢.
**Test** compute model fair to sub-cent precision, bucket by distance to the
nearest cent, and measure realised settlement against the quoted price. If
rounding is symmetric and unbiased there is nothing here; if the market
systematically rounds toward the round number, there is.
**Kill** rounding residual centred on zero, or our σ error swamping 0.5¢ —
which A1 measures directly, and is the likely outcome.
**Dependency** entirely parasitic on A1: a 6% σ error at 5¢ is worth more than
the whole tick effect. Do not run this before A1 reports.

### A4. Per-bucket adverse selection  ·  **DONE 2026-09-03 — every bucket loses**
**Mechanism** the σ-cancelling result — adverse selection per second is
`100·φ(z)/√var_factor(τ)·(r_live/60)`, asset-independent — says cost falls with
τ and with |z|. So the *safest* quoting region is far from close and far from
50¢, which is also the cheapest region for fees.
**Test** markouts bucketed by (τ, |z|) jointly rather than pooled.
**Kill** no region where markout beats the fee.
**Why it might not be dead** every published version of this measurement in the
project so far has pooled across exactly the dimension the theory says matters.

### A5. Does the book lead the index in a *tradeable* way?  ·  PARTLY DONE
**Status** `leadlag.py` refuted the naive version: the book **leads** the index
by 1s (β = 0.530 at lag −1, t = 29.4; −0.001 at lag +1, p = 0.37). No stale-quote
edge from watching the index.
**What is NOT yet tested** whether *our replica* (built from four venue feeds,
which we record) leads the **published** index by more than the book does. If
our replica is faster than the book on some subset of moves, that subset is
tradeable. `feeds.py` shows the replica lags the published index by 0–1s, which
is the wrong comparison — the comparison that matters is replica vs *book*.
**Kill** replica never leads the book.

### A6. Volatility term structure across τ  ·  `research/term.py`  ·  **BUILT**
**Mechanism** `var_factor(τ)` is exact and known. Implied σ backed out at
τ = 800 and at τ = 200 must agree. If the market prices a flat σ across τ while
the true term structure is not flat, the disagreement is arbitrage between two
contracts on the *same underlying and same close*.
**Counterparty** anyone quoting a single σ per market.
**Test** `implied.py` already produces (τ, iv) rows. Regress `log iv` on τ,
per market. A non-zero slope is either a real term structure or a pricing model
error — both are exploitable, and this needs **no directional view at all**.
**Kill** slope indistinguishable from zero after clustering by close time.
**Attractive because** it is a within-market comparison, so it is immune to the
realised-σ estimator bias that threatens A1's level term.
**BUILT, and sharper than the original idea.** Rather than only asking "is the
slope zero", the τ-profile of the inverted σ is a *fingerprint* of the market's
variance formula: flat if it uses the exact one, exploding into the close
(9.7× at τ=10) if it uses √τ, collapsing below 40s if it uses √(τ−39.5).
Self-test recovers a planted √τ book at β = 0.991 [0.981, 1.015]. A genuine
rising-vol *view* is separated from an arithmetic *error* by the pair of betas,
not either alone (√τ book: 0.991/−0.446; 40% rising view: 0.185/−0.175).
**And endgame.py has already priced the √τ case at +7.9c inside 60s.**
**Cost of building it:** found that `implied.collect`'s 30-second carry-forward
inverts stale quotes through a collapsed `var_factor` — 2s of staleness alone
fakes β = +0.062 (t = 6.0) on a flat book. Fixed; the level results were biased
UP by it, so they were conservative against the sub-1 finding.

### A7. WHERE a σ mispricing pays  ·  `research/surface.py`  ·  **BUILT, no data needed**
**Mechanism** not an edge of its own — the map from A1's number to a trade. If
implied σ is too low, prices are too confident, so the cheap side is the one
below 50¢. `z_true = z_market · r`, and **τ cancels exactly**, so the edge
depends on price alone.
**Result at r = 0.895** net is positive below ~30¢ and negative above, best at
7¢ (+1.82¢). A structural cliff at 10¢ where the tick goes 0.1¢ → 1¢ makes the
cost of crossing jump 10×. Break-even σ error: **1.8–2.5% below 10¢**, 10.7% at
30¢, never at 50¢.
**Kill** the availability table. The map assumes a one-tick book; if the wings
are quoted 1¢ wide the taper buys nothing, and if they are not quoted at all the
best cells do not exist. `surface.py --data` re-costs every cell with the
observed spread. **This is now the binding question for the whole candidate.**
**Why it is here** so the rule is written down *before* the number is
re-measured, rather than chosen after seeing the result.

---

## TIER B — needs collection we are not yet doing

### B1. Implied correlation on the Coin Race series  ·  HIGHEST UNEXPLORED VALUE
**Mechanism** `KXCRYPTOLEAD15M` and `KXCRYPTOCOMP15M` price *relative*
performance, so their price is a function of the **correlation** between two
coins, not just their vols. Invert the price for implied correlation. Realised
correlation is directly measurable from the venue feeds we already record at
1 Hz.
**Counterparty** correlation is materially harder to price than volatility, and
relative-performance products are where implied correlation is most often wrong
in every market where anyone has looked. There is no reason a thin 15-minute
crypto book prices it well.
**Test** implied ρ from the price versus realised ρ from feeds, same window.
**Data** the collector does not subscribe to these series. `everything.py`
step 1 patches `run_all.ps1` to add them — **this has never actually taken
effect, because the watchdog runs the collector from `C:\kals`, not the repo.**
Fixing that unlocks this entire branch.
**Kill** implied ρ tracks realised ρ within the fee.

### B2. Cross-series volatility spillover
**Mechanism** does coin A's realised vol predict coin B's *implied* vol?
**The problem, stated up front** twelve series at ρ ≈ 0.8 give **1.22 effective
independent units per close**, not 12. This is the trap that makes
cross-sectional crypto results look significant when they are not. Any test
here must cluster by close time and report n as close times.
**Why still worth doing** the *residual* after removing the common factor may
be far less correlated, and that residual is where a spillover would live.
**Kill** effect smaller than the MDE at 1.22 units/close — which is a very
large MDE, and this may be untestable in any reasonable time.

### B3. The comparison series' fee schedule
`exchange_index` and the non-crypto 15-minute series (`KXINX15M`, `KXNDQ15M`)
may carry a different fee multiplier. PLAN claimed 0.035 for financials against
crypto's 0.07; **that claim is refuted for the series we checked**, but not for
these two. Halving the fee halves every hurdle in this document and roughly
doubles the set of viable strategies. Cheap to check, large if true.

---

### A7. The endgame — the last sixty seconds  ·  `research/endgame.py`  ·  **UNFINISHED**
**Mechanism** with τ left, 60−τ settlement prints are already locked and on our
disk. The exact `sd/σ` collapses in a way no approximation follows: naive `√τ`
is **1.7× too large at 60s, 3.4× at 30s, 9.7× at 10s**, and `√(τ−39.5)` is
exact above 60s then divides by approximately nothing. This is the one region
where fair value barely depends on σ, because most of the answer is already
observed — close to the only measurement here that does not rest on a
volatility estimate. `openwindow.py` covers the first 60 seconds; nothing
covered the last.
**Status** Part 1 (the variance table) is exact and verified. **Part 2 does not
work and the module is not registered.** Against a book pricing naive `√τ` the
strategy is detected at |t| = 7.7 but *loses* 22.6¢ — if our model is right and
theirs is wrong we must make money, so the fixture or the entry rule is still
wrong. No number from it is usable yet.
**Already banked from it** two methodology results, both from failed
self-tests: taking the largest model-vs-market disagreement in a window is a
look-ahead worth −49.5¢ at t = −3.3 on a zero-edge tape; and a fixture that
clamps quotes to [1¢, 99¢] cannot be called "correctly priced", because the
clamp is itself a real mispricing in the endgame.
**Spin-off worth its own test** the exchange cannot quote below 1¢. In the
endgame true fair goes to 0 or 1, so selling a 1¢ contract genuinely worth
0.1¢ is a 0.9¢ edge against a 0.07¢ fee. Cheap to measure, and it needs no
model beyond the locked prints.

---

## TIER C — structural, low probability, high payoff

### C1. Settlement-mechanic edges near the boundary
`strike(N+1) == settle(N)` exactly, and settlement is the mean of 60 discrete
1-second prints. In the final 60 seconds the settlement value is *partially
locked*: `locked_sum` is known and only `r` seconds remain. Fair value becomes
near-deterministic as r → 0, while the market may still quote uncertainty.
**Kill** `openwindow.py`'s finding that the market already prices the locked
component. Worth re-checking specifically inside the last 20 seconds, which no
stage has isolated.

### C2. Queue position as the real maker edge
The fee theorem bounds E[P&L | fill] but says nothing about *which* fills you
get. Measured depth at touch is ~30 contracts (provisional, 2% sample). Being
first in queue at a price the market is about to leave is a different
distribution from the average fill.
**Kill** no measurable relationship between arrival order and markout.

### C3. Time-of-day and session effects
`chain.py` reports 04h vol peaks (XRP 1.36×, DOGE 1.38×, BNB 1.30×) — but that
was **a single day**, which is exactly how this project has produced fake
findings before. Needs many more days before it is anything.

---

## THE GRAVEYARD — do not re-propose these

| Idea | Why it died |
|---|---|
| Delta-hedging the binary | Costs 5–200× what it earns. Measured, not argued. |
| "Every game starts at 50¢" | False. `openwindow.py`. |
| Stock-index series charge half the crypto fee | False for every series checked. |
| The book lags the index (stale-quote edge) | Refuted — the book **leads** by 1s, t = 29.4. |
| Variance risk premium of 1.192× | A pooling artefact: sigmas averaged across series whose price levels differ by 10⁶. Per-series ratios are 0.86–1.25, and the liquid ones price vol *below* realised. |
| Wide maker quotes earn the spread | The fee theorem: `E[P&L | fill] ≤ −fee(p)`, **invariant to quote width**. Widening makes the taker more certain before they cross. |
| Depth at touch is 3,767 contracts | A mis-parsed REST field. Measured ~30. |
| Directional prediction from past returns | Up-rate 50.4%; sign test t under 1 after the tie fix. |
| Taker trading on order-flow imbalance | Real (t = +47 at k=1s, 798 closes, 4.7M market-seconds; placebo clean, backward t = +82) and ~100x too small. **Zero** trades cleared the cost of crossing at any horizon. `flow.py`. |
| Making the spread, any price bucket | Realised signed markout +0.612c at 1s, t = 54.4 on 798 closes, against 0.5c capture at a 1c median spread. Random-sign control reads -0.000c, so it is direction and not volatility. Loses -0.36c to -0.75c per fill in all seven price buckets. `maker.py`. |

---

## What I would do next, in order

1. **A2 per-price-bucket** — one small change to `maker.py`, and the q table
   says the pooled answer may be hiding a wing result.
2. **A6 term structure** — no directional view, no realised-σ estimator, purely
   within-market. Cleanest test on the list.
3. **Fix the collector sync, then B1** — implied correlation is the largest
   genuinely unexplored surface here, and it is one `git pull` and a watchdog
   restart away from having data.

**The honest prior:** the fee is 1.75¢ at the money and the liquid series quote
1¢ wide. That combination is not what an inefficient market looks like. The
wings are less watched and much cheaper, which is why everything above points
there — but "less watched" is a hypothesis about other people's attention, and
it is the assumption most likely to be wrong.
