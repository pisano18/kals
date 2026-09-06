# ADVERSARY 3 / LENS 3 — THE THINGS NOBODY MEASURED

Run 2026-09-06, 19:50–20:25 UTC. No orders placed, no money moved.
Authenticated read-only GETs, one live full-depth orderbook poll, and a replay
of three days of recorded books. No live orders were placed or contemplated.
Working files: `C:\Users\Joe\AppData\Local\Temp\kals-work\advl3\`.

Tags: **[LIVE]** = this account's authenticated API call today.
**[DOC]** = a primary Kalshi document retrieved today.
**[MEAS]** = computed by me today from real books — either the live orderbook
poll I ran, or a replay of the recorded tape (2026-09-04..06). Each use says which.
**[INFER]** = reasoning, explicitly not measured.

---

## VERDICT

**REFUTED — but not the way I expected, and I corrected myself once on the way.**

Kalshi publishes **two mutually contradictory descriptions of how the LIP scores
an order.** Both are primary Kalshi sources, both retrieved today. For 50
contracts resting 3 ticks behind the touch they disagree by **2.1x on score**,
and the disagreement is amplified by a **$1.00 minimum payout** that neither the
brief nor any of the three Reality jobs modelled.

Measured on **1,332 market-windows of recorded Coin Race books (2026-09-04..06),
948,974 qualifying side-seconds**:

| | score | PAID $/leg-window | % windows paid | **$/day** | peak capital | **%/day** |
|---|---:|---:|---:|---:|---:|---:|
| Help-centre rule ("one fifth") | 11.01% | $1.97 | 94.3% | **$933** | $232.50 | **401%** |
| **CFTC-filed rule (ref = best bid)** | **5.23%** | **$0.46** | **28.6%** | **$220** | **$232.50** | **94.6%** |
| the claim under attack | — | — | — | $282–348 | $254 | 111% |

**Three things follow, and the third is the one that matters.**

1. **The claim's $282–348/day does not reproduce under either rule.** Under the
   help-centre rule the right answer is ~2.9x larger. Under the filed rule it is
   ~$220/day. The claim's number brackets the filed-rule answer, but it was not
   derived that way — it came from the help-centre rule with a 28.9% qualifying
   haircut and **no $1.00 floor at all**. Two errors of opposite sign happening
   to land near the truth is not a validated number.

2. **The 2x upside is dead.** Both documents independently confirm the snapshot
   "plus" is divided straight back out. Nothing doubles (§3).

3. **The $1.00 floor turns a smooth rebate into a lottery, and nobody knew it was
   there.** Under the filed rule the *median leg-window pays exactly zero*:

   | filed rule, 50 lots, 3 back | p05 | p25 | **med** | p75 | p95 | max |
   |---|---:|---:|---:|---:|---:|---:|
   | PAID $/leg-window | 0.00 | 0.00 | **0.00** | 1.06 | 2.07 | 6.71 |

   **951 of 1,332 windows (71.4%) pay nothing.** The whole $220/day arrives from
   a 28.6% minority. Day to day that swings **$123 → $325** across three
   consecutive days (2.6x), against the help-centre rule's ±3%. The mean survives
   the floor; the *distribution* does not, and this project has reported means.

**What would still have to be true for the number to work:** that Kalshi runs its
help-centre article rather than the algorithm it certified to the CFTC. That is
the single load-bearing assumption in the whole project and it has never been
tested. §8 gives a $47, one-window experiment that settles it by sign.

---

## 0. WHAT I ACTUALLY RAN

| # | thing | method |
|---|---|---|
| 1 | Retrieved and read Kalshi's **Feb-11-2026 CFTC rule filing**, Appendix A, in full | [DOC] local text extract, normalised, quoted verbatim below |
| 2 | Retrieved Kalshi's **help-centre LIP article** | [DOC] `help.kalshi.com/en/articles/13823851` |
| 3 | Polled **11,034 full-depth live Coin Race orderbooks** over ~32 min, all 5 coins, ~0.45 s cadence, 15 market-windows | [MEAS] `advl3/poll.py` → `books.jsonl` |
| 3b | **Replayed 1,334 recorded Coin Race markets across 3 days** (2026-09-04..06) from the cached delta+snapshot tape — 948,974 qualifying side-seconds, 1,332 scored market-windows | [MEAS] `advl3/tape.py`, `tapemoney.py`, `sweep.py` |
| 4 | Implemented the filed algorithm **literally**, with a 13-case self-test | [MEAS] `advl3/filedrule.py` |
| 5 | Enumerated **all 6,385 Coin Race incentive programmes** | [LIVE] `/incentive_programs`, 40 pages |
| 6 | **Measured** this account's API rate limit two ways | [LIVE] `/account/limits` + a concurrency ramp |
| 7 | Reconciled **settlement fees against fill fees** on this account's own history | [LIVE] n=4, exact |
| 8 | Enumerated **all 194 scheduled per-event fee overrides** | [LIVE] `/events/fee_changes` |
| 9 | Cross-checked the **exchange schedule** against the programme calendar | [LIVE] two independent sources |
| 10 | Probed 20 endpoints for **reward visibility / withdrawability** | [LIVE] |

Both collectors verified alive at the start and end of the heavy work
(`kalshi_collector.py` PID 3381772, `crypto_feeds.py` PID 3385232). Free disk
52 GB throughout — never near the 6 GB stop.

---

## 1. THE FINDING THAT MATTERS: KALSHI PUBLISHES TWO DIFFERENT SCORING RULES

### 1.1 The CFTC filing, verbatim [DOC]

From *KalshiEX LLC — Amendment to August 2025 Liquidity Incentive Program*,
filed 11 February 2026, effective 28 February 2026, Appendix A:

> "First, Kalshi will initialize the Qualifying Yes Bids to the empty set.
> **If the highest yes bid price exists and is less than the highest possible
> price, it is assigned to the Reference Yes Price.** The exchange will
> initialize the Qualifying Yes Total Size to zero and set the current bid price
> to the Reference Yes Price. Kalshi will add the size available at the current
> bid price to the Qualifying Yes Total Size, and add all bids at the current bid
> price to the Qualifying Yes Bids. **If the Qualifying Yes Total Size is greater
> than or equal to the target size, the procedure is stopped here.** Otherwise,
> Kalshi will find the next highest yes bid price and repeat **without
> reinitializing** the Qualifying Yes Total Size, Qualifying Yes Bids, **or
> Reference Yes Price.** If no more bids exist, Kalshi will clear the Qualifying
> Yes Bids, as there were not enough bids to reach the Target Size."

> "If there is at least one Qualifying Yes Bid, **each Qualifying Yes Bid is
> assigned a score equal to the Discount Factor taken to the Nth power multiplied
> by its size, where N is the number of ticks between the Reference Yes Price and
> the price of the Qualifying Yes Bid.**"

So under the filed rule:

* **Reference Price = the best bid.** Assigned once, explicitly never
  reinitialised.
* The walk down the book decides only **which** bids qualify, and it stops at
  **Target Size (1,000)** — not one fifth of it.
* **Every** qualifying bid is discounted by `0.5^N` from the best bid. There is
  **no flat full-credit region**. The bid at the touch gets `N=0 → 1.0`; a bid
  3 ticks back gets `0.5³ = 0.125`.

### 1.2 The help centre, verbatim [DOC]

> "Walking down from the best bid, it is the first price level at which
> cumulative resting size reaches **one fifth of the Target Size**."
> "Orders priced at or better than the Reference Price get **full credit
> (1.0x multiplier)**."

The phrase **"one fifth" appears zero times in the filing**, and the filing's
Target-Size stopping condition appears nowhere in the help article.

### 1.3 These are not two wordings of one rule. They are different algorithms.

Under the help rule the reference price sinks to wherever cumulative size
reaches 200, so a wide band of the book gets **1.0x** and the denominator is
pinned near 200 — a 50-lot order mechanically wins ~50/250 ≈ 20% of a side
almost regardless of the book. Under the filed rule the reference is the touch,
the discount bites from the first tick, and **the size at the touch takes ~88%
of the entire side score**.

**Measured on 5,600+ live books, both rules, identical inputs [MEAS]:**

| | help-centre rule | **filed rule** | ratio |
|---|---:|---:|---:|
| our share of a side, 50 @ touch−3c | **15.30%** | **4.60%** | **3.3x** |
| p05 / median / p95 | 6.6 / 16.3 / 17.1 % | 3.8 / 4.6 / 4.8 % | |

The filed-rule distribution is far tighter because it is mechanically
determined: our score is `50 × 0.125 = 6.25` against a side score of ~137.

---

## 2. THE $1.00 MINIMUM PAYOUT — A CLIFF NOBODY MODELLED

Both documents agree on this, and **no report in this project has it**.

Filing [DOC]: *"Each Time Period Liquidity Provider Score is multiplied by the
Time Period Reward, and **if the result is greater than or equal to $1.00, the
result is paid out** to the corresponding user, rounded down to the nearest
cent."*

Help centre [DOC]: *"Minimum payout: $1.00 (rounded down to nearest cent)."*

**The Time Period is one 15-minute market-window, and the reward is $20.**
Verified on all 6,385 Coin Race programmes [LIVE]:

```
Time Period duration: 900.0 s   x 6,380    (5 legacy rows at 804.2 s)
period_reward:        200000    x 6,385    = $20.00 exactly
target_size_fp:       1000.00   x 6,385
discount_factor_bps:  5000      x 6,385    = 0.50
paid_out:             5,507 true / 878 false
```

**Therefore the payout threshold is a Time Period Score of exactly 5.00%.**
Below 5.00% you are not paid pro-rata. **You are paid nothing.**

This makes the payoff a **step function** in both size and distance-from-touch.
Every figure in this project has been computed as a linear mean, which silently
credits sub-$1 windows that will never be paid.

### 2.1 Where the cliff falls — measured on 1,332 recorded market-windows [MEAS]

50 contracts a side, both sides, all five coins, 2026-09-04..06, replayed from
the recorded orderbook deltas and snapshots. Payout = score x $20 x
(non-excluded/total), $1.00 floor, floored to the cent.

| rule | haircut | score | gross $/win | **PAID $/win** | % windows paid | **$/day (474 leg-win)** |
|---|---|---:|---:|---:|---:|---:|
| help-centre | applied | 11.01% | 2.015 | **1.968** | 94.3% | **$933** |
| help-centre | none | 11.01% | 2.203 | 2.177 | 97.4% | $1,033 |
| **filed** | **applied** | **5.23%** | **0.958** | **0.464** | **28.6%** | **$220** |
| filed | none | 5.23% | 1.046 | 0.564 | 34.8% | $267 |

The filed-rule score, **5.23% mean, sits almost exactly on the 5.00% payout
threshold.** That is why the outcome is a lottery rather than an income: the
per-window score distribution straddles the cliff.

| per-window score | p05 | p25 | med | p75 | p95 | fraction >= 5.00% |
|---|---:|---:|---:|---:|---:|---:|
| help-centre rule | 5.85% | 8.28% | 11.00% | 13.83% | 16.01% | **97.4%** |
| **filed rule** | **2.35%** | **3.45%** | **4.46%** | **5.75%** | **11.03%** | **34.8%** |

**Correction to my own first pass, stated plainly.** My initial 35-minute live
poll (10 market-windows) gave **0 of 10 windows paid, $0.00/day** under the filed
rule, and I had written that up as a clean kill. Extending to 1,332 windows of
recorded tape moved it to **28.6% of windows paid, $220/day**. **My live-poll
sample was too small and I was overstating the kill.** The 3-day tape figure is
the one to use. What survives from the small sample is the mechanism, not the
zero.

### 2.2 How thin is the miss? Thinner than anyone would like [MEAS]

Our score 3 ticks back is `S × 0.5³`. The side score is dominated by the size
`Q` resting at the touch, which carries multiplier 1.0. Solving by hand:

```
   6.25 / (Q + 6.25)  >=  0.05     ->     Q  <=  118.75 contracts
```

**Measured size at the touch: 120 contracts, in 4,754 of 6,239 observed sides
(76.2%).** The break-even is 118.75. **We miss by 1.25 contracts.**

| size at touch | n sides | median filed-rule share @ touch−3c |
|---|---:|---:|
| 0–49 | 486 | 6.88% |
| 50–99 | 23 | 6.28% |
| **100–149** | **6,842** | **4.60%** |
| 150–199 | 23 | 3.25% |
| 300–349 | 159 | 1.62% |

**I want to be explicit that this makes the result fragile.** It is decided by
one counterparty's choice of 120 lots. Across 948,974 recorded side-seconds on
three separate days the touch was 120 contracts in **610,025 cases (64.3%)** and
in [100,149] in **68.7%** — so the 120 is persistent, not a one-evening artefact.
But the *margin* is 1.25 contracts. Move our size to 60, or step in to 2 ticks
back, and the sign flips.

**So the honest statement is not "the strategy is dead."** It is: **the claimed
configuration sits within 1% of a discontinuity nobody knew was there, on the
wrong side of it, and the whole payoff distribution is determined by which side
of that 1% you land on.**

### 2.3 THE SHARPEST RESULT: "3 ticks back keeps 93% of the rebate" is FALSE

The brief's central risk trade is: *"Standing 3 ticks back keeps 93% of the
rebate, cuts fills 60%, and flips fill P&L positive."* The 93% is where the whole
strategy comes from — it is what makes standing away from the touch look free.

**It is a help-centre-rule artefact.** Under that rule the reference price sinks
below your order, you get the flat 1.0x multiplier, and distance genuinely costs
almost nothing (I measure 10.96% at 3 back vs 11.99% at the touch = **91%**,
reproducing the brief's 93%). Under the filed rule the multiplier is `0.5^ticks`
from the touch, so three ticks costs you a **factor of eight**.

Measured on the same 1,332 recorded windows, filed rule, 50 lots [MEAS]:

| ticks back | score | PAID $/win | % windows paid | $/day | peak cap | %/day | **rebate kept** |
|---:|---:|---:|---:|---:|---:|---:|---:|
| **0** (at touch) | 25.28% | 4.610 | 99.6% | **$2,186** | $245 | 892% | 100% |
| 1 | 15.57% | 2.833 | 98.8% | $1,344 | $240 | 560% | 61% |
| 2 | 9.07% | 1.532 | 84.6% | $727 | $235 | 309% | 33% |
| **3** | **5.23%** | **0.464** | **28.6%** | **$220** | **$230** | **96%** | **10%** |
| 4 (at 100 lots) | 5.21% | 0.462 | 28.5% | $219 | $455 | 48% | — |

**Three ticks back keeps 10% of the paid rebate, not 93%.** The $1.00 floor does
most of that damage: the score falls 4.8x but the *paid* amount falls 9.9x,
because the floor amputates the bottom of the distribution.

### 2.4 The cheapest fix is one cent, not more capital

| configuration | $/day | peak capital | **%/day** | zero-pay windows |
|---|---:|---:|---:|---:|
| 50 lots, **3** ticks back (the claim) | $220 | $230 | 96% | **71.4%** |
| 50 lots, **2** ticks back | **$727** | **$235** | **309%** | 15.4% |
| 100 lots, 3 ticks back | $725 | $460 | 158% | 15.5% |
| 150 lots, 3 ticks back | $1,058 | $690 | 153% | 2.9% |

**Stepping in one tick is worth 3.3x, for $5 more capital.** It dominates
doubling size, which buys the same $/day for twice the capital — the two rows are
the same trade (`size x 0.5^ticks` is the only quantity that matters) but one
costs $235 and the other $460.

**This is a real result but it is not free, and the cost is outside my lens.**
One tick closer to the touch is materially more fill risk, which is exactly what
criticisms A and B price. My contribution is that the *rebate* side of that trade
has been mis-stated by roughly 9x, so the trade needs re-solving from scratch.

**Self-consistency check on my own implementation.** Under the filed rule the
score should depend only on `size x 0.5^back`. Three independent configurations
share `effective = 12.5` and `6.25`:

```
  size 100 @ 3 back -> 9.05%      size  50 @ 2 back -> 9.07%     (effective 12.50)
  size  50 @ 3 back -> 5.23%      size 100 @ 4 back -> 5.21%     (effective  6.25)
```

Agreement to 0.02 percentage points on independently replayed data. The residual
gap at `back=1` (15.57% vs 15.26/15.29%) is real and explained: one tick back is
postable on low-priced yes sides where three ticks back falls off the grid.

---

## 3. THE 2x AMBIGUITY IS SETTLED. IT RESOLVES AGAINST DOUBLING.

The brief says: *"Your snapshot score is your share of the yes side PLUS your
share of the no side. We implement the AVERAGE (conservative). If 'plus' is
literal every figure DOUBLES. Nobody has settled this."*

**It is settled, by both documents independently, and nothing doubles.**

**Help centre, verbatim [DOC]:**
> "Your snapshot score is your share of the yes side plus your share of the no
> side, **so a single snapshot is worth at most 2.0 across all participants**."

**Filing, verbatim [DOC]:**
> "The sum of all Normalized Qualifying Yes Scores and Normalized Qualifying No
> Scores corresponding to bids submitted by a single user is that user's Snapshot
> Liquidity Provider Score."

> "After the Time Period has elapsed, the Snapshot Liquidity Provider Scores are
> totaled for each user and **divided by the sum of all Snapshot Liquidity
> Provider Scores** to create a final liquidity provider score for each user for
> the time period."

The "plus" is real **at snapshot level**, and it is then **divided straight back
out** by the time-period normalisation. Each qualifying snapshot contributes
exactly 2.0 to the grand denominator (1.0 from the yes normalisation, 1.0 from
the no). So:

```
TimePeriodScore(u) = SUM_s [ yesShare_s(u) + noShare_s(u) ]  /  ( 2 x N_snapshots )
                   = mean over snapshots of  (yesShare + noShare) / 2
                   = THE AVERAGE OF THE TWO SIDE SHARES, exactly.
```

Hand-check: a lone participant holding 100% of both sides scores 2.0; the sum
over all users is 2.0; their Time Period Score is 1.0; they are paid **$20, not
$40.** The pool is paid **once**. Holding 20% of yes and 0% of no scores 0.2 out
of 2.0 = 0.10 → paid 10% of the pool = the average of 20% and 0%. Confirmed.

**The average reading is not "conservative". It is correct.** Every figure in
this project that carried an "or double this" caveat should have the caveat
deleted. **The upside case is gone.**

---

## 4. THE SEVEN LENS-3 QUESTIONS, ANSWERED

### (a) Can an unfunded account place a resting order? What is the minimum deposit?

**Not answerable without a POST, and I did not make one.** Balance today is
**$0.0047** [LIVE]. A resting *buy* is fully collateralised at its premium, so
50 lots at 17c reserves $8.50; the configuration reserves ~$233 across five
coins. Deposit minimums were measured by Job 2 (debit $10 / 2% fee, ACH $10 /
free, **wire $1,000 — exactly the floor, no fee, and the only method exempt from
a withdrawal hold**). I add nothing and dispute nothing there.

### (b) Market-maker registration, SSN, minimum account size?

**No registration. And applying would disqualify you.** Filing, verbatim [DOC]:

> "'Eligible Participants' are all Kalshi members, except the following:
> (i) affiliates of Kalshi; **(ii) members who have executed a Market Maker
> Agreement with Kalshi**; (iii) Introducing Brokers, Futures Commission
> Merchants, and customers thereof when transacting via the IB or FCM."

I re-read this in the primary text and **confirm Job 2's finding exactly**.
There is no minimum account size anywhere in the filing. SSN: **no KYC or tax
endpoint exists in the v2 API** — I re-probed and confirm the 404s.

### (c) Per-account cap on incentive earnings?

**None.** The filing caps only the schedule variables — Time Period ≤ 31 days,
Target Size 100–20,000, Discount Factor ≤ 1.00, Time Period Reward $10–$1,000
per calendar day. Payment is a pure pro-rata share of a fixed pool. **The
binding constraint is the pool ($20/market/window), not a rulebook cap.**
Confirmed from the primary text; Job 2 is right.

### (d) Do maker orders pay any fee we have ignored? — NO, and I checked harder than the series field

Three independent [LIVE] confirmations:

1. `GET /series/KXCRYPTOLEAD15M` → `fee_type: "quadratic"`, `fee_multiplier: 1`.
   Only `quadratic_with_maker_fees` / `quadratic_with_combo_maker_fees` charge
   makers.
2. `GET /events/fee_changes` — I paged **all 194 scheduled per-event fee
   overrides**. They cover 19 series, **all MLB**. **Zero touch any 15M or crypto
   series.** So no scheduled override will flip Coin Race to maker fees.
3. This account's own order records carry a distinct `maker_fees_dollars` field.
   Lifetime maker fees charged: **$0.000000**.

Caveat, stated plainly: this account has never *been* a maker (all 4 orders were
takers), so item 3 is consistent-with rather than proof-of. Items 1 and 2 are the
proof.

### (f) Is there a settlement fee on inventory held to expiry? — NO, measured exactly

I reconciled every settlement against its originating fill [LIVE, n=4]:

| ticker | settlement `fee_cost` | fill `fee_cost` | maker | taker |
|---|---:|---:|---:|---:|
| KXBTC15M-26AUG222115-15 | 0.116400 | 0.116400 | 0 | 0.116400 |
| KXBTC15M-26AUG150130-30 | 0.679600 | 0.679600 | 0 | 0.679600 |
| KXBTCD-26AUG1501-T63099.99 | 0.851100 | 0.851100 | 0 | 0.851100 |
| KXBTC15M-26AUG150045-45 | 0.338000 | 0.338000 | 0 | 0.338000 |
| **TOTAL** | **1.985100** | **1.985100** | **0** | **1.985100** |

**Difference: 0.000000.** The settlement record restates the fee already paid at
the fill. **There is no separate settlement fee.** Holding inventory to expiry
costs nothing extra in fees — the cost is the price move, which is criticism B.

### (g) API rate limits — MEASURED, not inferred, and the answer is better than Job 2's

Job 2 reported: *"Current tier of this account [INFER]: **not exposed by any
endpoint** — I probed `/account/usage_level`, `/account/api_usage_level`,
`/account/tier`, `/account/rate_limits`; all 404. Unupgraded accounts start at
Basic, so assume Basic."*

**I disagree with the premise. It IS exposed.** `GET /account/limits` → **200**
[LIVE]:

```json
{"grants": [],
 "read":  {"bucket_capacity": 600, "refill_rate": 200},
 "usage_tier": "basic",
 "write": {"bucket_capacity": 100, "refill_rate": 100}}
```

So the tier is a **measurement**, not an assumption: **basic**, no grants. And
the write bucket detail is the part that matters — **`bucket_capacity` equals
`refill_rate`, so there is ZERO burst reserve on writes.**

**Independent confirmation by a concurrency ramp** [LIVE]. GETs cost 10 tokens;
read bucket is 600:

| concurrent GETs | wall | req/s | codes |
|---:|---:|---:|---|
| 5 | 0.172 s | 29 | all 200 |
| 20 | 0.084 s | 240 | all 200 |
| 40 | 0.094 s | 424 | all 200 |
| **60** | **0.104 s** | **579** | **all 200** |

60 GETs × 10 tokens = **600 = bucket_capacity exactly.** The ramp and the
reported bucket reconcile to the token. Sustained read ceiling = 200/10 =
**20 GET/s**; polling 10 books at 1 Hz is 50% of budget.

**Third confirmation, from sustained load rather than a burst:** my 32-minute
book poll made **11,034 successful authenticated GETs at ~11 req/s (110 tokens/s,
55% of the read budget) and received ZERO 429s.** **Reads are not a constraint.**

**Writes: I measured the load instead of assuming it.** From the live poll, I
counted how often the touch actually moves — because you only need to
cancel-and-replace when it does:

* touch moved in **566 of 1,865** consecutive polls = **30.3%** at ~0.45 s
  cadence ≈ **0.67 moves/s/market**
* touch dwell time: p25 **0.79 s**, median **0.89 s**, p75 2.39 s, p95 9.17 s,
  mean 2.68 s

Costing each re-peg at 1 cancel (2 tokens) + 1 create (10) = 12 tokens, across
all five coins and both sides:

| write tokens/s needed | p50 | p75 | p90 | p95 | p99 | **max** |
|---|---:|---:|---:|---:|---:|---:|
| event-driven re-pegging | **36** | 48 | 72 | 84 | 96 | **132** |

Mean over the whole poll: **22.1 tokens/s** against a 100/s budget.
**Seconds exceeding the budget: 2 of 361 = 0.6%.**

**Verdict on (g), and I disagree with Job 2's conclusion:** Job 2 declared the
configuration **"INFEASIBLE — 20% over, sustained 429s"** by assuming blind 1 Hz
cancel-and-replace of all ten quotes (120 tokens/s). That assumption is wrong —
the LIP pays for **what is resting at each snapshot** and pays nothing for churn,
so you re-quote on touch movement, not on a clock. **Measured, the real load is
22 tokens/s mean and 96 at p99, which fits inside basic.** The residual hazard
is the **zero burst reserve**: the worst observed second needs 132 tokens, 32%
over, and with `bucket_capacity == refill_rate` there is nothing to absorb it.
That needs a client-side token bucket and a queue, not a tier upgrade.
`POST /account/api_usage_level/upgrade` exists (cost 30) if it is ever needed —
**I did not call it; it is a POST.**

### (e) The 2x — see section 3. Settled, does not double.

---

## 5. FIVE MORE THINGS NOBODY MEASURED

### 5.1 The tick on Coin Race is a FLAT CENT. The "tapered tick fix" is a bug.

Every one of the five live markets reports [LIVE]:

```
"price_level_structure": "linear_cent",
"price_ranges": [{"start":"0.0000","end":"1.0000","step":"0.0100"}]
```

One range, step 0.01, no taper. Confirmed across **6,400+ book snapshots: not a
single sub-cent price level appears**, and `pls` took exactly one value,
`linear_cent`, in every record.

The brief states: *"mean 12.55% using the TAPERED tick... A flat-1c-tick
implementation understates our share; that bug is fixed in
`research/lipscore.py`."* **That is backwards.** `research/lipscore.py` already
carries a comment (added 15:05 today) recording the correct field values — but
its *running code* still prints the tapered branch as `"TAPERED tick (correct)"`
and computes its headline from it, and its module docstring still says the flat
implementation "got it wrong". The corrected knowledge exists in a comment and
has not reached the numbers.

**Magnitude, measured live today:** flat 12.07% vs tapered 12.90% — a **6.4%**
overstatement, not a 5x one. It matters only where the reference price falls
below 10c (2 of 10 sides at the moment I ran it), because that is the only place
the taper changes anything. **I checked before claiming, and the tick is a real
error but a small one.** The `ticks_between(lo, hi, structure=...)` helper in
`lipscore.py` accepts a `structure` argument that `score_side` never passes, so
the flat branch is unreachable from the live path.

### 5.2 The book is essentially ONE participant's 120-lot ladder

Size at the touch was **exactly 120 contracts in 4,754 of 6,239 observed sides
(76.2%)** [MEAS], and the ladders run 120 lots at 3-cent intervals down 30+
cents. The whole rebate calculation is a calculation against one bot.

This cuts both ways and I will not pretend otherwise. It makes our relative size
large (good), and it means one counterparty can re-price the entire denominator
by changing a single parameter (bad). **The break-even in §2.2 is `Q ≤ 118.75`
and they post 120. If that 120 is itself tuned to a threshold, it will move when
we arrive.** Reality-1 measured no adaptation over a one-window lag; that is the
longest horizon a tape can test, and I agree with their conclusion that the
question is now a live-test question.

### 5.3 In 9.4% of sides, an order 3 ticks back scores EXACTLY ZERO, not a discount

Under the filed rule the qualifying walk **stops** once cumulative size reaches
Target Size. Anything below the stopping price is not discounted — it is
**excluded**. Measured [MEAS]:

* walk reaches touch−3c: **5,239** sides
* **walk STOPS ABOVE touch−3c: 543 sides = 9.4%** → our order scores 0
* a single level ≥ 1,000 sitting at the touch ("a wall"): **276 sides = 4.4%**
  (the size 1,001 appears 70 times — one contract over Target Size, which does
  not look accidental)

**I formed the hypothesis that an incumbent posts Target-Size+1 at the touch to
lock everyone out, then went and tested it: it happens, but only 4.4% of the
time in this sample.** The hypothesis is not the main mechanism. Reported
because I chased it and it did not pay off.

### 5.4 On the yes side you often cannot stand 3 ticks back at all

Coin Race is a five-way mutually exclusive race, so four of five coins trade
their yes side at 1–10c. Measured over 6,400+ snapshots [MEAS]:

* **yes side completely EMPTY (no resting bid at all): 1,100 snapshots**
* of non-empty yes sides, **684 of 2,499 (27.4%) have a best bid ≤ 3c**, so
  "touch − 3 ticks" is ≤ 0 and **the order cannot be placed on the grid**
* no side is almost never off-grid (41 cases)

When a side is unpostable your share of it is 0, and since the Time Period Score
is the **average** of the two side shares (§3), **your score halves on those
market-windows**. No report in this project applies that.

Snapshot qualification (both sides reach Target Size 1,000) measured across my
poll: **56.5%**. For comparison, `lipscore.py` hard-codes **28.9%** and
Reality-1 measured **74.16%**. **Three efforts, three answers, a 2.6x spread on
a directly multiplicative term, and nobody has reconciled them.** My figure is
biased low because my sample over-weights the first ~35 s after a market opens
with an empty book; Reality-1's is from a fuller reconstruction and is probably
the better estimate. **This term deserves one careful measurement rather than
three casual ones.**

### 5.5 The exchange closes every Thursday 03:00–05:00 — confirmed twice

`GET /exchange/schedule` [LIVE] returns, uniquely for Thursday, two sessions:
`00:00–03:00` and `05:00–00:00`. Every other weekday is continuous.

Cross-checked against the programme calendar itself [LIVE] — 6,385 Coin Race
programmes bucketed by ET weekday × hour show a clean hole and nothing else:

```
        0   1   2   3   4   5   6  ...
  Wed  40  40  40  40  40  40  40  ...
  Thu  40  40  40   .   .  40  40  ...     <- zero programmes, ET hours 3 and 4
  Fri  40  40  40  40  40  40  40  ...
```

**8 leg-windows a week are not 96/day but 94.86/day** — a 1.19% haircut on every
per-day figure in this project, and a weekly point at which all resting orders
must be re-established.

---

## 6. TWO OPERATIONAL FINDINGS FOR THE LIVE TEST

### 6.1 There is NO API surface for LIP reward credits. You cannot attribute a payment.

I probed 20 candidate endpoints [LIVE]. All 404: `/portfolio/incentives`,
`/portfolio/rewards`, `/portfolio/liquidity_rewards`, `/portfolio/credits`,
`/portfolio/transactions`, `/portfolio/ledger`, `/portfolio/statements`,
`/portfolio/bonuses`, `/portfolio/incentive_programs`,
`/incentive_programs/participation`, `/portfolio/settlements/incentives`,
`/portfolio/summary`.

The **only** observable is the balance moving. `/incentive_programs` exposes
`paid_out` as a boolean for the *programme*, with **no per-user amount field**
(confirmed across all 5,507 paid Coin Race programmes: the only paid-related key
is `paid_out` itself).

**Consequence for the test design, and it is the important one:** with five
coins × 96 windows you would see one aggregate balance change and could not
attribute it. **So the live test must be designed so the two candidate rules
predict different SIGNS, not different magnitudes.** Section 8 does exactly that.

### 6.2 `GET /portfolio/orders/queue_positions` exists and nobody in this project has used it

[LIVE] — returns **200** with `{"queue_positions": null}` for this account
(no resting orders), and accepts either `market_tickers` or `event_ticker`.

The brief's fill economics turn entirely on an *assumed* queue position —
front-of-queue **+0.560 c/contract** versus back-of-queue **−1.462** or
**−4.730**, a swing of over 5 cents a contract, and the single largest modelled
quantity in the project. **This endpoint reports the real answer directly once an
order is resting.** Any live test should read it every window; it converts the
biggest assumption in the model into a measurement for zero extra risk.

---

## 7. ARTEFACT CHECKS — WHAT WOULD MAKE MY KILL WRONG, AND WHAT I FOUND

I ran five. **Two changed my answer and one nearly reversed it.**

**1. "The filed rule is a mis-reading."** — CHECKED, SURVIVES. The alternative
reading of *"without reinitializing … or Reference Yes Price"* is that the
Reference is updated to the current price each iteration and ends at the
**deepest** qualifying level. Under that reading `N` = ticks between the deepest
level and each bid, so orders **at the touch** get the largest discount and
resting far from the market pays best. That is backwards for a programme whose
stated purpose is *"to increase liquidity on the central limit order book and
thereby enhance pricing efficiency."* It is incoherent; my reading is the only
one that makes the programme do what it says. Stated so you can disagree with it.

**2. "The share collapse is a tick-grid artefact."** — CHECKED, CHANGED MY
ANSWER. My first hand-calculation on a stale book gave a 5.2x tapered-vs-flat
gap and I nearly reported the tick as the kill. Running it live gave **1.07x**.
The tick only matters where the reference price sits under 10c. **I was wrong by
5x on my own first pass and the live run caught it.** The tick is §5.1, a 6%
error, not the story.

**3. "The self-test passes because the test is wrong."** — CHECKED, FOUND A REAL
BUG IN MY HAND-ARITHMETIC. Two of thirteen self-test cases failed by exactly
`120 × 0.5²⁴ = 7.15e-6`. The cause: **injecting our own 50 contracts shortens the
qualifying walk by one rung** (cumulative size reaches Target Size sooner), so the
deepest rung drops out of the qualifying set. My hand-computed expectation
summed 9 rungs; the truth is 8. **The code was right and I was wrong**; after
correcting the expectation both cases pass at **0.00e+00**. This is a genuine
mechanical property — your own size can push other people's orders out of the
scored set — and it is in no report.

**4. "The 47.5% qualification rate is a sampling artefact."** — CHECKED,
CONFIRMED AS AN ARTEFACT OF MY SAMPLE. My poll straddles a window boundary and
over-weights the first ~35 s of a fresh market, when the book is empty. On the
fuller sample it rises to 56.5%. **I flag my own number as biased low and defer
to Reality-1's 74.16% as the better estimate** (§5.4). It does not change the
filed-rule verdict — that zero survives with **no haircut at all**.

**5. "The 120-lot touch is peculiar to today, and the whole kill rests on 35
minutes of one Sunday evening."** — I wrote this up as the main hole in my work,
then went and closed it. I replayed **1,334 recorded Coin Race markets across
2026-09-04, 05 and 06** from the cached delta+snapshot tape (book resets applied,
sizes rounded to 2dp so float residue does not create phantom top-of-book levels).
**948,974 qualifying side-seconds.** The touch was **exactly 120 contracts in
610,025 of them (64.3%)**, and in [100,149] in **68.7%**. Median 120 on all three
days separately. **The ladder is persistent and the premise holds.**

The same replay is what corrected my headline (§2.1): the filed rule pays $220/day,
not the $0/day my 35-minute sample showed. **The check that closed the hole also
overturned my own conclusion, which is the outcome I should want and did not
expect.**

**6. "The replay is wrong."** — CHECKED, and it self-validates. Under the filed
rule the score can depend only on `size x 0.5^ticks_back`. Three independently
replayed configurations sharing an effective score agree to **0.02 percentage
points** (§2.4). An implementation that got the walk, the reference or the tick
wrong would not produce that identity.

---

## 6. TWO OPERATIONAL FINDINGS FOR THE LIVE TEST

### 6.1 There is NO API surface for LIP reward credits. You cannot attribute a payment.

I probed 20 candidate endpoints [LIVE]. All 404: `/portfolio/incentives`,
`/portfolio/rewards`, `/portfolio/liquidity_rewards`, `/portfolio/credits`,
`/portfolio/transactions`, `/portfolio/ledger`, `/portfolio/statements`,
`/portfolio/bonuses`, `/portfolio/incentive_programs`,
`/incentive_programs/participation`, `/portfolio/settlements/incentives`,
`/portfolio/summary`.

The **only** observable is the balance moving. `/incentive_programs` exposes
`paid_out` as a boolean for the *programme*, with **no per-user amount field**
(confirmed across all 5,507 paid Coin Race programmes: the only paid-related key
is `paid_out` itself).

**Consequence for the test design, and it is the important one:** with five
coins × 96 windows you would see one aggregate balance change and could not
attribute it. **So the live test must be designed so the two candidate rules
predict different SIGNS, not different magnitudes.** Section 8 does exactly that.

### 6.2 `GET /portfolio/orders/queue_positions` exists and nobody in this project has used it

[LIVE] — returns **200** with `{"queue_positions": null}` for this account
(no resting orders), and accepts either `market_tickers` or `event_ticker`.

The brief's fill economics turn entirely on an *assumed* queue position —
front-of-queue **+0.560 c/contract** versus back-of-queue **−1.462** or
**−4.730**, a swing of over 5 cents a contract, and the single largest modelled
quantity in the project. **This endpoint reports the real answer directly once an
order is resting.** Any live test should read it every window; it converts the
biggest assumption in the model into a measurement for zero extra risk.

---

## 7. ARTEFACT CHECKS — WHAT WOULD MAKE MY KILL WRONG, AND WHAT I FOUND

I ran five. **Two changed my answer and one nearly reversed it.**

**1. "The filed rule is a mis-reading."** — CHECKED, SURVIVES. The alternative
reading of *"without reinitializing … or Reference Yes Price"* is that the
Reference is updated to the current price each iteration and ends at the
**deepest** qualifying level. Under that reading `N` = ticks between the deepest
level and each bid, so orders **at the touch** get the largest discount and
resting far from the market pays best. That is backwards for a programme whose
stated purpose is *"to increase liquidity on the central limit order book and
thereby enhance pricing efficiency."* It is incoherent; my reading is the only
one that makes the programme do what it says. Stated so you can disagree with it.

**2. "The share collapse is a tick-grid artefact."** — CHECKED, CHANGED MY
ANSWER. My first hand-calculation on a stale book gave a 5.2x tapered-vs-flat
gap and I nearly reported the tick as the kill. Running it live gave **1.07x**.
The tick only matters where the reference price sits under 10c. **I was wrong by
5x on my own first pass and the live run caught it.** The tick is §5.1, a 6%
error, not the story.

**3. "The self-test passes because the test is wrong."** — CHECKED, FOUND A REAL
BUG IN MY HAND-ARITHMETIC. Two of thirteen self-test cases failed by exactly
`120 × 0.5²⁴ = 7.15e-6`. The cause: **injecting our own 50 contracts shortens the
qualifying walk by one rung** (cumulative size reaches Target Size sooner), so the
deepest rung drops out of the qualifying set. My hand-computed expectation
summed 9 rungs; the truth is 8. **The code was right and I was wrong**; after
correcting the expectation both cases pass at **0.00e+00**. This is a genuine
mechanical property — your own size can push other people's orders out of the
scored set — and it is in no report.

**4. "The 47.5% qualification rate is a sampling artefact."** — CHECKED,
CONFIRMED AS AN ARTEFACT OF MY SAMPLE. My poll straddles a window boundary and
over-weights the first ~35 s of a fresh market, when the book is empty. On the
fuller sample it rises to 56.5%. **I flag my own number as biased low and defer
to Reality-1's 74.16% as the better estimate** (§5.4). It does not change the
filed-rule verdict — that zero survives with **no haircut at all**.

**5. "The 120-lot touch is peculiar to today."** — **NOT CHECKED. This is the
main hole in my work.** My measurement is ~35 minutes of one Sunday evening on
five markets and ten market-windows. The 120 recurs in 76% of sides *within that
sample*, which is not evidence that it recurs across days. **The kill in §2.2
rests on a number I observed for half an hour.** It should be re-measured across
the recorded tape for 2026-09-04 onward before anyone acts on it.

---

## 8. THE EXPERIMENT THAT SETTLES IT — $47, ONE WINDOW, BINARY READOUT

Everything above reduces to one unresolved fork: **does Kalshi run its help-centre
article or the algorithm it certified to the CFTC?** No amount of tape answers it.
It needs one live order, and it can be made to answer by **sign, not magnitude** —
which matters because §6.1 established there is no API that attributes a reward
to a market-window, so the only readout is the balance moving.

**Design.** In **one** Coin Race market, for **one** 15-minute window, rest
**50 contracts on each side at exactly 3 ticks behind each touch**, re-pegged when
the touch moves. Place nothing else that window.

**Capital at risk: 50 x (p_yes + p_no) = $46.50 measured median, $47.50 at p95.**
Not $1,000. Not $232. **Forty-seven dollars**, for fifteen minutes.

**The two rules predict opposite outcomes:**

| | predicted score | x $20 x haircut | vs the $1.00 floor | **observable** |
|---|---:|---:|---|---|
| help-centre rule | 11.0% | $1.97 | above | **balance rises ~$1.97** |
| **filed rule** | 5.2% | $0.46 | **below** | **balance does not move at all** |

**Paid or not paid. There is no overlap and no calibration needed.** One window
discriminates. Repeat it three or four times to beat the 28.6%/94.3% pay
frequencies into significance — still under $200 of capital, never held overnight,
in markets that settle in fifteen minutes.

**Run it 3 ticks back, not at the touch.** At the touch both rules pay and the
test tells you nothing. The claim's own posture is, by luck, the maximally
informative one.

**Two free riders on the same test:**
* read `GET /portfolio/orders/queue_positions` each window (§6.2) — settles the
  front-vs-back-of-queue assumption worth 5c/contract;
* log every 429 — settles the write-budget question against the measured 22
  tokens/s mean and 132 tokens/s worst second (§4g).

**This requires the operator's explicit per-instance sign-off. I have not placed
it and I am not asking for it here — I am reporting that $47 buys the answer to
the question the whole project rests on.**

---

## 9. WHERE I DISAGREE — VERBATIM

**With the brief, on the tick.**
> *"Share at S=50 measured 4.2%-18.3% across ten live sides, mean 12.55% using the
> TAPERED tick (0.1c below 10c and above 90c -- engine.tick_at). A flat-1c-tick
> implementation understates our share; that bug is fixed in research/lipscore.py."*

**Wrong, and backwards.** `KXCRYPTOLEAD15M` is `price_level_structure:
"linear_cent"`, one range 0.00-1.00 step 0.0100 [LIVE, all 5 markets]. Confirmed
independently from the recorded tape: **3,962,084 delta prices, 100.0% whole
cents, zero sub-cent** [MEAS]. The flat implementation was right; the "fix"
introduced the error. It is a ~6% overstatement, not fatal — but the direction is
in our favour, which is the direction that matters. `research/lipscore.py` already
carries a correct comment about this; its running code and docstring still do not.

**With the brief, on the scoring rule.**
> *"Reference Price: 'walking down from the best bid, the first price level at
> which cumulative resting size reaches one fifth of the Target Size'."*

That is the help-centre wording and it is genuine — but **"one fifth" appears
nowhere in the CFTC filing**, which says the Reference Price *is the best bid* and
is explicitly never reinitialised. The brief presents one of two contradictory
Kalshi documents as settled fact. It is not settled.

**With the brief, on the 2x.**
> *"UNRESOLVED 2x: 'Your snapshot score is your share of the yes side PLUS your
> share of the no side.' We implement the AVERAGE (conservative). If 'plus' is
> literal every figure DOUBLES. Nobody has settled this."*

**Settled, by both documents, today. Nothing doubles.** The help centre's own next
clause — *"so a single snapshot is worth at most 2.0 across all participants"* —
and the filing's time-period re-normalisation both divide the "plus" back out. The
average is not conservative, it is exact. **Delete the caveat.**

**With the brief, on the risk trade.**
> *"Standing 3 ticks back keeps 93% of the rebate, cuts fills 60%, and flips fill
> P&L positive."*

Under the filed rule it keeps **10%** of the paid rebate (§2.3). The 93% is a
help-centre-rule artefact. This is the load-bearing sentence of the whole
strategy and it is conditional on the rule question nobody has tested.

**With Job 2 (`FUNDING_ELIGIBILITY.md`), on rate limits.**
> *"Current tier of this account [INFER]: **not exposed by any endpoint** -- I
> probed /account/usage_level, /account/api_usage_level, /account/tier,
> /account/rate_limits; all 404."*

**`GET /account/limits` returns 200** with `usage_tier`, and both token buckets
[LIVE]. The tier is measurable, not an inference. Job 2's *conclusion* (basic) was
right; its claim that no endpoint exposes it was wrong.

> *"**On Basic the described configuration cannot run.** ... 120 tokens/second ...
> INFEASIBLE -- 20% over, sustained 429s."*

**I disagree with the premise.** That assumes blind 1 Hz cancel-and-replace of all
ten quotes. The LIP pays for what is *resting* at each snapshot and pays nothing
for churn, so you re-quote on touch movement. **Measured: 22.1 tokens/s mean, 96
at p99, exceeding the 100/s budget in 2 of 361 seconds (0.6%).** It fits. The real
hazard is that `bucket_capacity == refill_rate` on writes — **zero burst
reserve** — and the worst observed second needed 132 tokens.

**With Reality-1, on the tick and the rule.** Its library
(`kals-work/impact/lib.py`) implements `need = target / 5.0` (the help-centre
rule) on the tapered grid (`tick_u = 1 if u > 900 or u < 100 else 10`). Its
self-test is thorough and its implementation is faithful **to that spec**. The
error is in the spec, not the code. Its `$838/day` is the help-centre-rule branch
of my §2.1 table (I get $933 on the same rule with a different sample), and it
carries **no $1.00 floor**, which is what turns 94.3% paid windows into 28.6%
under the other rule.

**Where I agree with Reality-1 and add nothing:** criticism A's dilution question
is not answerable from tape at horizons beyond one window, and it is now a
live-test question. Its peak-capital figure is right — I measure **$46.50 median
per market x 5 legs = $232.50**, against its $230.50, from a completely
independent replay.

---

## 10. WHAT I COULD NOT DO

* **Could not settle which scoring rule Kalshi runs.** Both are primary Kalshi
  sources and they contradict. This is the single load-bearing uncertainty and it
  is not resolvable from documents or tape. §8 resolves it for $47.
* **Could not retrieve the CURRENT filing.** The one I read is the Feb-11-2026
  amendment, which by its own terms ran *"until the earlier of September 1, 2026,
  or the date that Kalshi amends or terminates the Program."* **That date has
  passed.** Programmes are still being scheduled and paid, so it was extended by a
  filing I could not retrieve (`kalshi.com/regulatory/notices` returned HTTP 429).
  The help-centre article may describe that newer version — which would make the
  "one fifth" rule current and the filed rule stale. **I cannot rule that out and
  it would reverse my verdict.**
* **Could not verify SSN / KYC status.** No such endpoint exists in the v2 API
  (re-confirmed, all 404). Requires the operator to log in.
* **Could not test whether an unfunded account can place an order**, or measure
  the collateral rule, without a POST.
* **Could not measure anything about fills or inventory.** No fill P&L, no
  inventory distribution, no ruin probability. That is criticisms B and C.
  **Nothing in this report bounds the downside of the trade as a whole** — it
  prices the rebate only.
* **Could not reconcile the qualifying-snapshot fraction.** Three measurements
  exist: 28.9% (`lipscore.py`, hard-coded), 56.5% (my live poll, biased low by
  window-boundary sampling), 74.16% (Reality-1). My tape replay produces a
  per-window haircut implicitly (mean gross/score ratio ~91%). **A 2.6x spread on
  a directly multiplicative term, unreconciled.**
* **Did not test the incumbent's response.** Every number assumes the 120-lot
  ladder is exogenous. It is one participant and the break-even is 1.25 contracts
  away from their current choice.

---

## 11. SUMMARY TABLE

| question | answer | source |
|---|---|---|
| (a) unfunded account / min deposit | not testable without a POST; wire $1,000, no fee, no hold | [LIVE]+Job 2 |
| (b) MM registration / SSN / min size | **no registration; executing an MM Agreement DISQUALIFIES you**; no min size; SSN not API-visible | [DOC] filing, verbatim |
| (c) per-account earnings cap | **none** — caps are on the schedule variables only | [DOC] filing |
| (d) maker fees | **zero.** `fee_type: quadratic`; all 194 scheduled fee overrides are MLB, none touch 15M/crypto | [LIVE] |
| (e) the 2x | **settled — does not double.** Snapshot "plus" is divided back out | [DOC] both sources |
| (f) settlement fee | **none.** settlement `fee_cost` - fill `fee_cost` = 0.000000, n=4 | [LIVE] |
| (g) rate limits | tier **measurable** at `/account/limits` = basic; reads fine; writes fit event-driven (22 tok/s mean) but **zero burst reserve** | [LIVE]+[MEAS] |
| **the scoring rule** | **two contradictory Kalshi documents, 2.1x apart on score, straddling a $1.00 floor** | [DOC] both |
| **the $1.00 minimum payout** | **real, per 15-min window, = a 5.00% score threshold; unmodelled everywhere** | [DOC] both |
| the tick | **flat 1c** — 3,962,084 recorded prices, 100% whole cents | [LIVE]+[MEAS] |
| Thursday closure | 03:00–05:00 ET weekly; 94.86 windows/day, not 96 | [LIVE] x2 |

### The money, stated as required

**Rebate only. No fill P&L, no inventory. 1,332 recorded market-windows,
2026-09-04..06.**

| | help-centre rule | **filed rule** |
|---|---:|---:|
| $/leg-window (mean PAID) | $1.968 | **$0.464** |
| per-leg-window distribution | p05 0.00, p25 1.49, **med 1.98**, p75 2.58, p95 3.05 | p05 0.00, p25 0.00, **med 0.00**, p75 1.06, p95 2.07, max 6.71 |
| windows paying **zero** | 76/1,332 = 5.7% | **951/1,332 = 71.4%** |
| **$/day** (474.3 leg-windows) | **$933** | **$220** |
| **peak concurrent capital** | \$232.50 (med \$46.50/market x 5; p95 \$237.50) | same |
| **% return on capital / day** | **401%** | **94.6%** |
| **$/contract/day** (500 resting) | $1.866 | **$0.440** |
| worst day of three | $906 (09-06) | **$123 (09-04)** |
| best day of three | $964 (09-04) | $325 (09-06) |
| day-to-day swing | ±3% | **2.6x** |

**Worst case within my lens:** the worst leg-window pays $0.00, and under the
filed rule that is the *median* outcome, not the tail. Ruin probability is **not
estimable here** and is **not zero** — this measures rebate accrual only. Capital
at risk is mechanically bounded at ~$232.50 of resting premium, but that is the
cost of the orders, not the loss. The loss lives in the inventory left when one
side fills and the other does not, which is criticisms B and C.

---

## 11b. CROSS-VALIDATION: TWO INDEPENDENT DATASETS, SAME ANSWER

The two measurements share no code path and no data. One is **live REST polling**
of `/markets/{ticker}/orderbook` (11,034 snapshots, 15 market-windows, tonight).
The other is a **replay of recorded WebSocket deltas and snapshots** (1,332
market-windows, three days), reconstructed with book resets and 2dp size
rounding. Same scorer, different books.

| 50 lots, 3 ticks back, filed rule | live REST poll | recorded-tape replay |
|---|---:|---:|
| market-windows | 15 | 1,332 |
| score | 4.39% | 5.23% |
| PAID $/leg-window | $0.285 | $0.464 |
| % windows paid | 20% | 28.6% |
| median window | **$0.00** | **$0.00** |
| $/day | $137 | $220 |
| peak capital | $232.50 | $232.50 |

| same, help-centre rule | live | tape |
|---|---:|---:|
| score | 11.25% | 11.01% |
| PAID $/leg-window | $1.519 | $1.968 |
| % windows paid | 73% | 94.3% |
| $/day | $729 | $933 |

**The scores agree to within 0.8 and 0.24 percentage points respectively.** The
paid amounts differ more because the live sample contains partial windows (two of
three closes are truncated by the start and end of my poll), which depresses the
non-excluded fraction. **The tape figures are the ones to use.**

**One number moved decisively as the sample grew, and it was mine.** Snapshot
qualification (both sides reaching Target Size 1,000) measured **47.5%** on my
first 2,984 snapshots, **56.5%** on 3,599, and **71.4%** on the complete 11,034 —
converging on Reality-1's **74.16%**. **My early figures were biased low exactly
as I suspected and flagged, and Reality-1's number is the right one.** The 28.9%
hard-coded in `research/lipscore.py` is wrong and should be replaced.

---

## 12. THE ONE-LINE RECOMMENDATION

**Do not fund $1,000 against this number.** Fund the minimum, place **$47 of
resting orders for one 15-minute window at 3 ticks back**, and read whether the
balance moves. That single binary observation is worth more than every dollar of
analysis in this directory, because it settles which of Kalshi's two published
scoring rules is real — and with it, whether the answer is $933/day, $220/day of
lottery tickets, or something the incumbent takes away once we arrive.

**And if it does prove out: step in one tick.** Three ticks back is not the safe
choice it was modelled to be; under the filed rule it is where the payout floor
eats 90% of the rebate.
