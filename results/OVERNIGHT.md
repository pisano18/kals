# OVERNIGHT — 2026-09-06

## Read these five lines first

1. **WHAT DIED — `pin`.** Not on edge, on capacity. It is a taker; the median
   resting size where it hits is 69 contracts and 50 fails to fill 42.3% of
   the time. Bootstrap 95% interval on $/day at cap 50: **[+19, +48]**
   one-per-close (FAIL) and **[+22, +76]** every-market (INCONCLUSIVE) against
   your +$50/day threshold. Nothing clears. Drop the ten best closes and it is
   $19–22/day — **by your own test, a lottery ticket, not an edge.**
2. **WHAT SURVIVED — market-making,** and it is now the only live strategy.
   +0.48c per fill, t=+6.4, on 17.1M at-touch fills; capacity was the open
   question and the queue-position simulator (JOB A) was built to answer it.
3. **WHAT CHANGED — I retracted my own recommendation from yesterday evening.**
   I proposed fixing the four dead series to reach ~$65/day. The money part
   holds; the independence part does not. Going 1.0 → 1.6 coins/close pushed
   top-10 concentration from 45% → 56%. More series buys **leverage, not
   diversification**, and must not be sold as a route past the threshold.
4. **WHAT NEEDS YOU** — see "Needs you" below. Nothing is frozen; the 19-day
   forward clock has NOT started, which is the right outcome.
5. **WHAT I COULDN'T DO** — see "Not done, and why" at the foot. Nothing was
   silently dropped.

**Status of this file:** written after priority 1 completed, then updated as
each overnight job landed. If a section says RUNNING or NOT REACHED, that is
literal — it was not finished, and I have not guessed at its result.

---

## Priority 1 — the four pre-freeze checks — COMPLETE

All four ran on cached out-of-sample cells. 20,000-rep percentile bootstrap
over **closes**, not trades, because hundreds of trades share one settlement
outcome.

### 1. Concentration — the headline, not a footnote

You were right that `t=+5.0` was flattering it. Normal-theory standard errors
assume nothing like this distribution.

| cap 50 | one-per-close | every-market |
|---|---|---|
| top 5 closes | 30% of the money | 41% |
| top 10 | **45%** | **56%** |
| top 25 | 73% | 86% |
| closes individually profitable | 263/336 (78.3%) | 264/336 (78.6%) |

| drop the best closes | one-per-close | every-market |
|---|---|---|
| drop none | $33/day | $49/day |
| **drop top 10** | **$19/day** | **$22/day**  [+1, +40] |
| drop top 25 | $10/day | $7/day  [−14, +24] |

Your test was: *"if dropping ten closes takes it under $20/day, this is a
lottery ticket and not an edge, and I want it said that way."* One-per-close
lands at **$19/day**. **Said that way: pin is a lottery ticket.**

The mitigating fact, stated because it is true: 78% of closes are individually
profitable, so it is not a coin flip. But the money lives in a handful of
closes, and that is what the normal-theory `t` was hiding.

### 2. Intervals, not point estimates

| variant | cap | $/day | 95% bootstrap interval | verdict |
|---|---|---|---|---|
| one-per-close | 25 | 17 | [+9, +25] | FAIL |
| one-per-close | 50 | 33 | [+19, +48] | **FAIL** |
| one-per-close | 69 | 45 | [+28, +61] | INCONCLUSIVE |
| every-market | 25 | 26 | [+11, +39] | FAIL |
| every-market | 50 | 49 | [+22, +76] | **INCONCLUSIVE** |
| every-market | 69 | 64 | [+30, +99] | INCONCLUSIVE |

A pass needs the **whole interval** above $50. Nothing does. cap 100 is
recorded as **UNAVAILABLE**, not as clearing — it consumes the entire resting
level 60–62% of the time, which assumes winning a race for a stale quote that
this backtest cannot test.

### 3. The every-market rescue, with the identical per-market haircut

**It already carried it.** The $49/day figure is computed with
`min(cap, depth)` applied **per market**, the same haircut as one-per-close.
My earlier "$51/day, right at your line" was an extrapolation from the +3.95c
per-close figure *before* the haircut; the measured post-haircut number is
**$49/day, interval [+22, +76] — INCONCLUSIVE.** The rescue does not rescue.

Worse: per-market p25 depth is 15, so a 50-contract order fails to fill in
roughly 31% of individual markets, and stacking markets **concentrates** the
result rather than diversifying it (top-10 45% → 56%).

### 4. The two arithmetic reconciliations

**Worst close −$38.65 at caps 50, 69, 100 AND 250 — not a bug, confirmed
explicitly.** That close (`1788293700`) holds a **single** trade whose resting
depth was **40.1 contracts** — below every cap tested. The cap never binds
there, so raising it cannot make that particular close worse. Verified by
printing the trade list and its depths, not by reasoning.

**Fire rate: 37.2/day is correct; my 26.5 was wrong.** I had divided
out-of-sample trades by a span that included the 150-close warmup. Measured:

- 723 closes in the `tau<=20` scan over 12.2 days
- the OOS window holds **572 available closes over 9.0 days**
- **336 fired = 58.7% of available closes = 37.2/day**

A third error surfaced while reconciling: `portfolio()` assumes **96
closes/day**, but available closes run **63.3/day** in this window. So that
constant was wrong on two counts, not one.

### The verdict this forces

**`pin` is dead against your kill criteria.** It dies on capacity, not on the
forward test — a cheaper death and an earlier one. The rule was never frozen
and the forward clock never started; 19 days spent confirming a miss would
have been the waste. Written into `HANDOFF.md` and `CLAUDE.md`, commit
`1a5e9f9`.

The per-contract edge (+2.54c, t=+5.0 out of sample) is **not** retracted. It
is real. It simply cannot be filled at a size that pays.

---

## Priority 2–6 — overnight run

Workflow `wf_91a8161c-989`, all subagents pinned to **Opus at `max` effort** —
no cheaper model checks an Opus result.

| # | job | status |
|---|---|---|
| 2 | JOB A — queue-position simulator + self-test | see below |
| — | 3 adversarial refuters against JOB A | see below |
| 3 | AGENT ADVERSARIAL pass 1 | see below |
| 4 | AGENT RISK/REWARD | see below |
| 5 | AGENT NEW DIRECTIONS | see below |
| 6 | JOB B tie audit · JOB C API · JOB D stage suite | see below |

Individual reports land in `results/overnight/`.

*(This table is rewritten with real outcomes as each job returns. Any row
still reading "see below" with no section underneath did not finish.)*

---

## Needs you

1. **Nothing is frozen and nothing should be.** `pin` failed before the freeze
   step, which is the system working.
2. **A decision once the queue simulator lands:** if market-making also misses
   $50/day at a fillable size, both live strategies are dead, and your criteria
   then start a 60-day clock on the search itself. That is your call, not mine.
3. **Model/effort:** I cannot set my own. You are on Opus 5 at `max`; subagents
   are explicitly pinned to Opus/`max` in the workflow script.

## Not done, and why

*(populated as the night resolves — a failed job honestly reported beats one
quietly skipped)*

- Cache pre-build succeeded: `rows_tau60.pkl` (169,254 rows) and
  `depth_map.pkl` (831,100 ticker-second depth entries), so no agent needs
  `load_quotes` and the OOM risk is removed structurally rather than by asking
  agents to be careful.
- One job was OOM-killed earlier in the day (two processes each holding a full
  `load_quotes`). **The collectors were never at risk** — both sit at 13–25 MB
  and kept writing throughout; the harness kills the largest offender, which
  was mine. Resource protocol now written into `CLAUDE.md`.

## Resource state

| | |
|---|---|
| free disk | 52.5 GB (was 7.0 GB — your uninstall landed) |
| free RAM | 5.0 GB of 15.8 GB after cache build |
| `kalshi_collector.py` | **UP**, pid 2708908, since 09-04 |
| `crypto_feeds.py` | **UP**, pid 531268, since 08-27 |
