# THE MINIMUM INFORMATIVE LIVE TEST — designed, priced, ready for sign-off

**Job 1, 2026-09-06, 19:00–19:50 UTC. NO ORDERS PLACED. NO ORDERS AMENDED. NO
ORDERS CANCELLED.** Everything below is authenticated read-only GET, public
documentation quoted verbatim, and replay of the local tape.

Account state confirmed at the top of this run: `balance_dollars 0.0047`,
`positions []`, `orders []`, `withdrawals []`.

---

## THE ANSWER IN ONE PARAGRAPH

**The 1-contract quote is dead, and it is not the cent-rounding that kills it.**
Kalshi's published terms carry a **$1.00 minimum payout per programme**, and an
"individual programme" is one market for one 15-minute window. A 1-contract
two-sided quote earns **$0.037** per programme; across **4,067 replayed
market-windows it cleared $1.00 exactly zero times**. It is not a small
measurement — it is no measurement. The smallest instrument that reliably
produces a *readable* payout is **50 contracts a side on one Coin Race market**,
which pays on 90.2% of programmes (91.2% on HYPE). That costs **$41.50 of
collateral, recycled every 15 minutes**, and its exact worst case is **$46.50
per window**. Eight consecutive windows — two hours — cost at most **$150 if
you fund $150, because Kalshi is fully cash-collateralised and cannot take more
than the balance**, and they settle the critic's question at
`P(false negative) = 8.5e-9`.

**RECOMMENDATION: fund $150 to exchange shard 2 and run HYPE-50-8. Do not run
the 1-contract test — it measures nothing and still costs money.**

---

## FIVE THINGS THAT CHANGED WHILE PRICING THIS, ALL MEASURED

| # | Was | Is | Why it matters |
|---|---|---|---|
| 1 | "rounded down to the nearest cent" is the floor | **$1.00 minimum per programme** | 27x bigger than assumed. Kills S<25 outright. |
| 2 | qualification 26.0% of snapshots | **65.5%** (median 70.7%), replay validated to **0.00%** against the live book | the rebate is 2.5x more payable than `REBATE_RISK.md` says |
| 3 | the 2x "yes PLUS no" ambiguity is unresolved | **RESOLVED: there is no 2x** | the optimistic case evaporates; our average-of-sides implementation was exactly right |
| 4 | Coin Race tick is tapered | **`linear_cent`**, read from `price_level_structure` | modelled share at S=50 is 11.80%, not 12.55% |
| 5 | orders can be placed once funded | **Coin Race is on exchange shard 2, which holds $0.00** | an unmoved dollar means every order is rejected |

---

## 1. DOES A 1-CONTRACT QUOTE SCORE? — YES. DOES IT GET PAID? — NO.

### The floor, verbatim, from two first-party pages

`help.kalshi.com/en/articles/13823851-liquidity-incentive-program`, under
**Rewards Structure**:

> Time periods: Up to 31 days each, and time periods may overlap
> Daily rewards: $1-$1,000 per market, per day
> **Minimum payout: $1.00 (rounded down to nearest cent)**

`help.kalshi.com/en/articles/16076644-liquidity-and-volume-incentive-programs-where-to-find-them`:

> For liquidity programs, rewards are rounded down to the nearest cent, and
> **a final reward below $1 for an individual program is not paid.**

And, on the same page, what "an individual program" is:

> **Each program has its own market, start and end time, and reward pool** — and,
> for liquidity programs, a Target Size and Discount Factor.

That is exactly one row of `GET /incentive_programs`. Live example pulled this
run:

```
{"id": "c81b1e0d-7fdb-4959-8b77-a8e06d507a95",
 "market_ticker": "KXCRYPTOLEAD15M-26SEP070000-HYPE",
 "start_date": "2026-09-07T03:45:00Z", "end_date": "2026-09-07T04:00:00Z",
 "period_reward": 200000, "target_size_fp": "1000.00",
 "discount_factor_bps": 5000, "paid_out": false}
```

**One market. Fifteen minutes. $20.00. Own UUID. That is the programme, and
$1.00 is the floor on it.**

### What one contract actually earns — 4,067 market-windows

Replayed from the local tape, 29 Aug – 6 Sep, five coins, 1-second resolution,
the verbatim rule on the verified `linear_cent` grid:

| S (each side) | modelled score share | mean $/programme | median | **% of programmes ≥ $1.00** | $/programme actually paid | **$ deleted by the floor** |
|---|---|---|---|---|---|---|
| **1** | 0.28% | **0.0373** | 0.0375 | **0.0%** | **0.0000** | **100.0%** |
| 5 | — | 0.1842 | 0.1850 | 0.0% | 0.0000 | 100.0% |
| 10 | — | 0.3625 | 0.3647 | 0.0% | 0.0000 | 100.0% |
| 25 | 6.37% | 0.8633 | 0.8698 | 39.6% | 0.5034 | 41.7% |
| 50 | 11.80% | 1.6018 | 1.6121 | 76.6% | 1.4584 | 8.9% |
| 75 | 16.49% | 2.2401 | 2.2612 | 87.3% | 2.1649 | 3.4% |
| 100 | 20.60% | 2.8000 | 2.8302 | 91.1% | 2.7480 | 1.9% |
| 200 | 32.98% | 4.4985 | 4.5395 | 96.4% | 4.4827 | 0.4% |

**0 of 4,067.** Not "usually rounds to zero" — never once, on any coin, on any
of nine days. The brief's estimate of $0.02–$0.10 a window was right (measured
$0.037); the floor it had to clear was 27x higher than the brief thought.

**Arithmetic check by hand.** One contract at the Reference Price against a
median side score of ~260: share = 1/261 = 0.383% on one side. Average the two
sides ≈ 0.28%. Reward = 0.0028 × $20 × 0.655 = **$0.0367**. The replay says
$0.0373. Agrees.

### The floor is not just a test problem — it is a strategy problem

Nobody had priced it. At the recommended production configuration (S=50) the
floor **deletes 8.9% of the modelled rebate**: $768.84/day naive becomes
$700.04/day paid. At S=25 it deletes **41.7%**. Below S=25 it deletes
**everything**. Any future sizing work must apply it *per market per
fifteen minutes*, not to the daily total.

---

## 2. THE SMALLEST SIZE THAT RELIABLY CLEARS THE FLOOR

Finer sweep, 1,818 market-windows (2–5 Sep), 364 of them HYPE:

| S | mean $/programme | **≥$1.00, all coins** | **≥$1.00, HYPE only** | $ paid/programme |
|---|---|---|---|---|
| 20 | 0.7176 | 22.0% | 28.3% | 0.2473 |
| 25 | 0.8828 | 40.1% | 53.3% | 0.5067 |
| 30 | 1.0432 | 52.6% | 66.5% | 0.7336 |
| 35 | 1.1984 | 63.0% | 78.6% | 0.9549 |
| 40 | 1.3491 | 69.5% | 84.1% | 1.1432 |
| 45 | 1.4951 | 75.8% | 88.5% | 1.3329 |
| **50** | **1.6383** | **80.4%** | **91.2%** | **1.5081** |
| 60 | 1.9102 | 85.7% | 93.1% | 1.8158 |
| 80 | 2.4113 | 91.7% | 96.4% | 2.3593 |

**S = 50 on HYPE is the answer.** 91.2% of programmes pay. Going to 80
contracts to buy the last 5 points of reliability costs 60% more collateral and
60% more downside; it is not worth it for a test.

Why HYPE, measured over 4,067 market-windows:

| coin | qualification | $/programme @50 | **% paying ≥$1** | median worst-case price `max(ref_y, ref_n)` |
|---|---|---|---|---|
| **HYPE** | **71.7%** | **1.877** | **90.2%** | **0.69** |
| XRP | 66.5% | 1.661 | 78.7% | 0.78 |
| SOL | 66.7% | 1.627 | 79.9% | 0.74 |
| BTC | 62.3% | 1.481 | 69.3% | 0.76 |
| ETH | 60.4% | 1.359 | 64.9% | 0.80 |

HYPE is simultaneously the **highest-paying and the cheapest to be wrong on**.
That is not a coincidence: its yes price sits near 0.20 rather than 0.02, so
both reference prices are away from the extremes.

---

## 3. EXACT COLLATERAL

**The rule.** Kalshi is fully cash-collateralised. `Buying Yes vs Selling No`
(help, 17 Mar 2026): *"there's no inherent difference between buying a Yes
contract and selling a No contract... the combined value of all Yes and No
contracts for a given market always equals $1."* A resting **sell of yes at
price q is a resting buy of no at (1 − q)**. `Collateral Return` (help, 17 May
2026) states the default explicitly by contrast: without netting, *"we take the
full $1.30 of your available funds"* — i.e. **the full premium, held from the
moment the order rests** (*"this includes any cancelled/unfilled resting
orders"*).

So a two-sided quote of S contracts holds **S × (price_yes + price_no)**.

**Measured, over 48,866 qualifying snapshot-seconds:**

| | median | p99 | absolute |
|---|---|---|---|
| `ref_yes + ref_no` (collateral per contract-pair) | **$0.830** | $0.940 | < $1.000 by construction |
| `ref_yes` | 0.05 (HYPE 0.20) | — | — |
| `ref_no` | 0.76 (HYPE 0.61) | — | — |

**A two-sided 1-contract quote ties up $0.83.** The brief's "about $1" was
right. It is also the only thing about the 1-contract idea that was right.

**At S=50 on one market: $41.50 median, $46.50 at p99, $50.00 absolute.**
This is *concurrent* capital. It is released at every window close and re-used,
so it does **not** scale with the number of windows.

> **NOT VERIFIED ON THIS ACCOUNT.** Every historical fill is `is_taker: true`;
> this account has never rested an order, so the hold has never been observed in
> its own ledger. **Stage 0 below verifies it for $0.01.**

### Two collateral traps found while pricing this

* **`netting_enabled` (Collateral Return) locks on your FIRST order in an
  event and can never be changed for that event** — *"this includes any
  cancelled/unfilled resting orders"*. With it ON you *"may be unable to sell
  positions for which you've already had collateral returned"*, which breaks the
  stop condition. **Confirm it is OFF (the default) before the first order.**
* **Coin Race is on exchange shard 2 ("Crypto"). Shard 2 holds $0.0000.**
  `GET /portfolio/balance?exchange_index=2` → `"balance_dollars": "0.0000"`.
  Balances are per shard. Funds must be moved by
  `POST /portfolio/intra_account_transfer` or at
  `kalshi.com/account/exchange-indexes`. `intra_exchange_transfers_active: true`
  as of this run.
* **Fund by ACH, not debit card.** This account's own three deposits carry
  `fee_cents` of 20/1021 and 38/1939 — **1.96%**. On $1,000 that is $20, more
  than the entire expected payout of this test.

---

## 4. WORST CASE — EXACT DOLLARS

**Both sides filling is not the bad case; it is a locked profit.** If both fill,
you hold S yes and S no, which pay exactly $S at settlement regardless of the
outcome, against a cost of S × (p_y + p_n) < $S. Profit = S × (1 − p_y − p_n) ≥ 0.

The bad case is **one side filling and settling against you**. Per market-window
that is exactly **S × max(ref_yes, ref_no)**.

Measured over 22,973 synchronised qualifying seconds:

| | median | p95 | p99 | **absolute maximum observed** |
|---|---|---|---|---|
| one market, per contract | 0.760 | 0.890 | 0.920 | **0.980** (HYPE: 0.930) |
| five markets, per contract, mutual exclusivity applied | 1.500 | 1.720 | 1.790 | **1.870** |

Mutual exclusivity matters and it helps: exactly one of the five coins settles
YES, so at most one no-leg can lose while the other four must win. The correct
bound is `max_j [ ref_no(j) + Σ_{i≠j} ref_yes(i) ]`, not the sum of the
per-market maxima. Measured, that is **1.87 per contract, against a naive
additive bound of 4.90 — a 2.6x overstatement if you ignore the structure.**

### The recommended configuration, in dollars

| | S=50, one market (HYPE) | S=50, five markets |
|---|---|---|
| concurrent collateral | **$41.50** (p99 $46.50) | $207.50 (p99 $235.00) |
| **worst case, one window** | **$46.50** (HYPE max ref 0.93) | **$93.50** |
| worst case, 8 windows, arithmetic | $372.00 | $748.00 |
| **HARD CAP — what you can actually lose** | **= the funded balance** | = the funded balance |

**The hard cap is real and exchange-enforced.** Every position is fully
pre-collateralised, so the account cannot go negative, and once the balance is
consumed further orders are rejected — the test halts itself. **Fund $150 to
shard 2 and $150 is the exact maximum loss**, whatever happens.

The $372 arithmetic bound requires the losing side to fill *in full* in *every
one* of eight windows and settle against you *every time*. The tape says what
actually reaches a quote at the Reference Price:

* volume trading **at or through** the reference price: **11.4%** of taker
  volume on the yes side, **22.4%** on the no side (80 market-windows)
* at S=50 that caps fills at **mean 18.0, median 3.0** contracts per
  market-window across both sides; **40% of market-windows have zero exposure**
* and that ignores the ~200 contracts of queue sitting ahead of you at the
  reference level, which is where the Target/5 threshold is crossed
* pricing every one of those contracts as a total loss gives **$7.26 per
  market-window on average, $40.50 at the observed maximum**

For orientation only, not my measurement: `REBATE_RISK.md` measured the maker
side of 449,803 contracts at **+1.309 c/contract gross to settlement, zero fee**.
The expected fill P&L is mildly *positive*; the exposure above is variance, not
drift.

---

## 5. HOW MANY WINDOWS — THE POWER CALCULATION

**The estimator is not noisy.** A programme's reward *is* the realised score
share, already averaged over ~900 snapshots:
`realised share = paid $ / (pool × q)`, with `q` measured from our own tape
(validated below to 0.00%). The uncertainty is entirely *between* windows.

### The question as posed: 12.55% modelled vs 3% real

3% is `f = 0.25` of the modelled 11.80%. At f = 0.25 every programme's reward
falls to a mean of $0.40 — **below the floor, so $0.00 is paid on essentially
every programme**. Under the model, 90.2% of HYPE programmes pay.

| N programmes | P(observe zero payouts \| model true) |
|---|---|
| 4 (1 hour) | 9.2 × 10⁻⁵ |
| **8 (2 hours)** | **8.5 × 10⁻⁹** |

**Four programmes settle 12.55%-vs-3%. Eight settle it beyond argument.** This
question is cheap because the floor turns a large shortfall into a hard zero.

### The expensive question: is the model 20–30% optimistic?

HYPE, S=50, paid mean **$1.811**, sd **$0.771**, CV 0.43:

| N | hours | expect | 95% band | **detects realised share ≤ … of modelled (95%/80%)** |
|---|---|---|---|---|
| 4 | 1 | $7.25 | [$4.22, $10.27] | 40% |
| **8** | **2** | **$14.49** | **[$10.22, $18.76]** | **58%** |
| 12 | 3 | $21.74 | [$16.50, $26.97] | 66% |
| 20 | 5 | $36.23 | [$29.47, $42.99] | 73% |
| 48 | 12 | $86.95 | [$76.48, $97.41] | 83% |
| 96 | 24 | $173.89 | [$159.09, $188.70] | 88% |

Quoting all five coins in the same window instead (5 programmes per window,
S=50, sd $2.532 on a $7.291 mean, CV 0.35):

| windows | hours | programmes | detects share ≤ … |
|---|---|---|---|
| 4 | 1 | 20 | 51% |
| 12 | 3 | 60 | 72% |
| 20 | 5 | 100 | 78% |
| 48 | 12 | 240 | 86% |

**MDE statement.** Two hours on one market detects a realised share **42% below
modelled**. Detecting a 20% shortfall needs **24 hours on one market or 12 hours
on five** — five times the capital and five times the downside. That is a
second-stage decision, not a first-stage one.

---

## 6. HOW WE READ THE RESULT — AND THE ONE FINDING THAT NEARLY KILLS THE TEST

### There is NO API endpoint that reports incentive earnings. None.

I enumerated the complete published API surface from `docs.kalshi.com/sitemap.xml`
(240 reference pages). The **only** incentive endpoint is
`api-reference/incentive-programs/get-incentives` — *programme definitions*.
The entire portfolio surface is: `get-balance`, `get-deposits`, `get-fills`,
`get-positions`, `get-settlements`, `get-withdrawals`,
`get-intra-account-transfer(s)`, `get-subaccount-netting`,
`get-subaccount-transfers`, `get-target-balance-allocation`,
`get-total-resting-order-value`. **No credits, no ledger, no activity, no
rewards.** Kalshi says so itself: *"Incentive program definitions ... are
available through the public Trade API"* — definitions, and nothing else.

Probed anyway, all authenticated, all **404**:

```
/portfolio/incentives  /portfolio/rewards  /portfolio/credits  /portfolio/ledger
/portfolio/transactions  /portfolio/account_history  /portfolio/balance_history
/portfolio/incentive_payouts  /portfolio/liquidity_incentives  /portfolio/payouts
/portfolio/earnings  /portfolio/statements  /incentives  /rewards  /user/rewards
  ... 22 candidates, every one 404
/portfolio/summary/total_resting_order_value -> 403 permission_denied
```

**This does not kill the test, because there are three readable channels:**

1. **`paid_out` on the exact programme id — free, authenticated, and it is a
   clean trigger.** Measured lag for Coin Race, 6,385 programme rows:

   | hours since window end | % `paid_out: true` |
   |---|---|
   | 0–6 | 0.0% |
   | 6–12 | 0.0% |
   | 12–18 | 20.8% |
   | 24–30 | 25.0% |
   | 36–42 | 70.8% |
   | **42–48** | **100.0%** |

   **The money is processed within 48 hours.** Record the eight programme UUIDs
   at placement time, poll `GET /incentive_programs` until all eight flip.

2. **`GET /portfolio/balance` on shard 2.** With `positions []`, `orders []` and
   a known funded amount, every dollar is accounted for: `balance = funded −
   Σ(premium on open orders and positions) + Σ(settlements) − Σ(fees) + REWARD`.
   Fills, fees and settlements are all readable
   (`/portfolio/fills`, `/portfolio/settlements`), so **the reward is the
   residual and it is unambiguous**. Snapshot the balance at T0 and after all
   eight programmes flip `paid_out`.

3. **`GET /portfolio/deposits`** — the only portfolio endpoint carrying a `type`
   field (currently `"debit"` on all three rows). If a reward credit lands there
   it is a *labelled* record. Unknown until tested; check it.

   And in the UI, for confirmation only: **Menu → Rewards / kalshi.com/incentives**
   (Current month, Lifetime — *"paid rewards, not pending estimates"*) and
   **Account → Activity → Credits**, which identifies *"the event, payment date,
   amount, and whether it was a liquidity or volume reward"*.

### The cost of this: the test does not answer within the window

*"Rewards are not credited in real time. Final scoring occurs after a program
ends, and payment follows in a later processing run. Timing can vary."*
**Place Sunday, read Tuesday.** Budget 48 hours, not 2.

### A bonus the test settles for free

Credits identify *the event*, and the Rewards page *"groups programs by event"*.
So the test also resolves whether the $1.00 floor is applied **per market-window**
(as I have priced it, costing 8.9% of the rebate at S=50) or **after aggregation
across the five coins of an event** (in which case the floor is nearly
irrelevant). Quote all five coins in at least one window and the answer falls
out of the credit records. That is worth $46.50 on its own.

---

## 7. STOP CONDITIONS AND HOW FAST WE CAN STOP

**Kill switch: `DELETE /portfolio/events/orders`.** One call, cancels every
resting order on the account, costs **2 tokens from a 100-token write bucket
that refills at 100/s** (`GET /account/limits`: `write {bucket_capacity: 100,
refill_rate: 100}`, `read {600, 200}`). **Sub-second, and it can be issued ~50
times a second if needed.**

**Belt and braces, so a dead bot cannot leave anything resting:** every order
goes in with `time_in_force: good_till_canceled` and
`expiration_time = window close`. The exchange cancels them even if the process
dies. Also set `cancel_order_on_pause: true`.

**Abort immediately if any of these:**

| trigger | why | detection |
|---|---|---|
| net realised loss on the test > **$60** | ~4x the expected payout; the thesis is not worth this | `/portfolio/fills` + `/portfolio/settlements`, every window |
| any single window's fills exceed **60 contracts** on one side | measured p90 exposure is 51 at S=50; past that the book is behaving unlike the tape | `/portfolio/fills` |
| `ref_yes + ref_no ≥ 0.99` | our own two orders would cross each other — measured on **0.065%** of market-seconds | pre-flight check on every re-quote |
| `ref_no > 0.93` on HYPE | the largest reference price in 19,801 qualifying seconds; beyond it we are in untested territory | pre-flight check |
| shard-2 balance < $60 | not enough for the next window; stop cleanly rather than get rejected | `/portfolio/balance?exchange_index=2` |
| `paid_out` still false at **+72h** | the read channel has failed; stop and re-plan rather than spend more | `/incentive_programs` |
| exchange pause, or `trading_active: false` on shard 2 | | `/exchange/status` |

**Post-only is mandatory.** `post_only: true` on every order guarantees we never
cross, never pay the 7% quadratic taker fee, and stay a maker
(`maker_fees_dollars: "0.000000"` on this account's own orders;
`KXCRYPTOLEAD15M` is `fee_type: "quadratic"`, `fee_multiplier: 1` → makers pay
nothing). Set `self_trade_prevention_type` explicitly, because we quote both
sides of the same market.

**Re-quote load is trivial.** The Reference Price changes a **median 125 times
per market-window** (max 320). At 2 writes per change that is 0.28 writes/second
against a 100/second budget.

---

## THE ORDER TICKET — what the operator is signing

### Stage 0 — instrument check. Total exposure: $0.01. Run this first.

1. Confirm **Collateral Return is OFF** in account settings (it locks per event
   on the first order and cannot be undone).
2. Transfer **$150** to **exchange shard 2**. Verify:
   `GET /portfolio/balance?exchange_index=2` → `"150.0000"`.
3. Place **ONE** order: buy 1 YES at **$0.01** on the Coin Race leg whose best
   yes bid is currently **≥ $0.10** (check the book first; the median best yes
   is 0.12, and HYPE's is 0.20 — but ETH's can sit at 0.02, so read it, do not
   assume). `side: "bid"`, `count: "1"`, `price: "0.0100"`, `post_only: true`,
   `time_in_force: "good_till_canceled"`, `expiration_time` = window close.
   Nine-plus ticks below the touch it will not fill — **and if it somehow does,
   the entire loss is one cent.**
4. Read `/portfolio/balance?exchange_index=2`. **It must drop by exactly $0.01.**
   That verifies the collateral rule on this account's own ledger for the first
   time.
5. `DELETE /portfolio/events/orders`. Balance must return to $150.00. **Time it.**

If step 4 shows anything other than a $0.01 hold, **stop** — the collateral model
is wrong and every number above needs redoing.

### Stage 1 — the measurement. "HYPE-50-8".

```
market      KXCRYPTOLEAD15M-<yymmmdd><HHMM>-HYPE     (one market, one at a time)
size        50 contracts resting on the YES side, 50 on the NO side
price       exactly AT the current Reference Price on each side,
            re-quoted when the reference moves (median 125 times/window)
flags       post_only=true, tif=good_till_canceled,
            expiration_time=window close, cancel_order_on_pause=true
duration    8 consecutive 15-minute windows = 2 hours = 8 programmes
guards      skip a side if ref_yes+ref_no >= 0.99, or if ref_no > 0.93
```

| | |
|---|---|
| concurrent collateral | **$41.50** median, $46.50 p99, $50.00 absolute |
| **exact worst case, one window** | **$46.50** |
| **exact worst case, whole test** | **$150 — the funded amount. Exchange-enforced.** |
| expected LIP payout | **$14.49**, 95% band **[$10.22, $18.76]** |
| expected programmes paying | **7.2 of 8** |
| taker fees paid | **$0.00** (post_only + maker-exempt series) |
| read window | **≤48 hours** after the last window closes |

### The decision rule, fixed before the data

* **0 of 8 pay.** Realised share is below `1.00/(20 × 0.717)` = **7.0%**, i.e.
  ≤59% of modelled, and probably far worse. `P(this | model true) = 8.5e-9`.
  **The strategy is dead. Do not fund it.**
* **Total < $10.22.** Realised share is significantly below modelled. Re-price
  everything at the observed share before committing capital.
* **Total in [$10.22, $18.76] with ~7 of 8 paying.** The static-book model has
  survived its first contact with a live posted order. **Proceed to Stage 2.**
* **Total > $18.76.** Suspect the reward is aggregated across the five coins of
  an event rather than floored per market. Good news, but re-derive before
  scaling.

### Stage 2 — only after Stage 1 passes

Five coins, S=50, 20 windows (5 hours) = **100 programmes**. Concurrent
collateral **$207.50**; worst case **$93.50 per window**; expected payout
**$145.80**; detects a realised share **22% below modelled**. It also resolves
the per-market-vs-per-event floor question from the credit records.

**Do not skip Stage 1 and start here.** Stage 1 costs $150 of exposure to
eliminate the world in which Stage 2 loses $500 measuring a strategy that pays
nothing.

---

## WHAT WOULD MAKE THIS FICTION, AND WHAT THE CHECK SAID

| # | If this were true the design is wrong | What was measured | Verdict |
|---|---|---|---|
| A | the tape replay overstates book depth, so qualification and share are inflated | 405 live `GET /orderbook` polls over 199s on 5 markets, replayed second-by-second from the tape over the same seconds: **median depth error 0.0 contracts, median side-score relative error 0.00%, reference price agreement 98.0%** | **replay is exact** |
| B | 65.5% qualification is my bug; `REBATE_RISK.md`'s 26.0% is right | reconciled on the same four windows (26SEP0320xx). One window agrees closely (585/476/670/652/689 vs 516/470/634/625/682); the other three show their pipeline at **0, 0, 0** where the book was demonstrably full. Zeros are the signature of a missed opening snapshot. | **theirs is understated; mine is validated against the live API and theirs is not** |
| C | the "yes share PLUS no share" wording doubles the money | verbatim: *"your share of the yes side plus your share of the no side, so a single snapshot is worth at most 2.0 across all participants"*, then *"Your Time Period score = your total snapshot scores ÷ **all participants' total** snapshot scores"*. The 2.0 is in the denominator: `Σ(y+n) / (2N) = mean of (y+n)/2`. | **no 2x. The average implementation is exactly the rule.** |
| D | the tapered tick applies to Coin Race | `GET /markets/KXCRYPTOLEAD15M-…-BTC`: `price_level_structure: "linear_cent"`, `price_ranges: [{start 0.0000, end 1.0000, step 0.0100}]` | **flat 1c. Modelled share is 11.80% at S=50, not 12.55%.** |
| E | one good hour was cherry-picked | 4,067 market-windows over **nine** dates; per-date `%≥$1` at S=50 ranges 59.1%–83.6%, per-hour 50%–85% | **stable** |
| F | the worst case is the sum of the five per-market maxima | mutual exclusivity binds: `max_j [ref_no(j) + Σ_{i≠j} ref_yes(i)]` = **1.87/contract vs a naive 4.90** | **the naive bound overstates by 2.6x; I report the correct one** |
| G | $0.02–$0.10 per window survives the cent rounding, so 1 contract works | it survives the *cent* rounding and dies on the **$1.00 programme floor**, 0 of 4,067 | **the brief asked the right question and the answer is no** |
| H | fills at the reference price are frequent | 11.4% (yes) / 22.4% (no) of taker volume reaches the reference price; **40% of market-windows have zero exposure**; and this ignores ~200 contracts of queue ahead | **exposure is an upper bound and it is small** |

---

## WHAT THIS DESIGN STILL CANNOT SETTLE

1. **Eligibility.** LIP excludes non-US users, Kalshi affiliates, IBs, FCMs and
   their customers, and needs *"a verified Social Security Number on file to
   receive reward credits above annual IRS reporting thresholds"*. **No API
   endpoint exposes eligibility** — `/users/self`, `/user`, `/account`,
   `/account/profile` are all 404. If the account is ineligible, the test pays
   $0 and looks exactly like a failed strategy. **Check this in the app before
   funding.**
2. **Whether the $1.00 floor is per market-window or per event.** Priced the
   conservative way. Stage 2 resolves it; Stage 1 does not.
3. **The re-quote latency penalty.** The model assumes we are at the Reference
   Price every second. A real bot is stale for part of the 125 moves per window.
   The live test measures this *inclusive* — which is the point — but cannot
   separate it from competitor reaction.
4. **Whether competitors react over days rather than minutes.** Two hours cannot
   see a rival who re-sizes tomorrow.
5. **Anything about size beyond 50.** At S=200 the model claims 33% of a side.
   That is not credible and the test does not probe it.

---

## PROVENANCE

* **[DOC-verbatim]** `help.kalshi.com/en/articles/13823851-liquidity-incentive-program`
  (updated this week) and `.../16076644-liquidity-and-volume-incentive-programs-where-to-find-them`
  (26 Jul 2026), `.../13823816-collateral-return` (17 May 2026),
  `.../13823811-limit-orders`, `.../trading/buying-yes-vs-selling-no`.
  Raw HTML fetched and stripped, not summarised.
  The Feb-2026 CFTC rule filing (`cftc.gov/.../rules02112639183.pdf`) **could not
  be read** — subset fonts with custom encodings defeated the extractor, and
  `curl` to cftc.gov fails TLS (exit 60) in this environment. A model-generated
  summary of it contradicted the help centre on two points (it called the
  Reference Price "the midpoint" and added a 5-minute opening exclusion), so
  **it is not used anywhere above.**
* **[API]** `kauth.py` authenticated GETs: `/incentive_programs` (177,018 rows,
  178 pages), `/markets`, `/markets/{t}/orderbook`, `/series/{s}`,
  `/portfolio/{balance,fills,orders,positions,settlements,deposits,withdrawals}`,
  `/account/limits`, `/exchange/status`. **Zero write calls were made.**
* **[TAPE]** `C:\kals\kalshi_data\{orderbook_snapshot,orderbook_delta,trade}`,
  read-only. 4,067 KXCRYPTOLEAD15M market-windows, 29 Aug – 6 Sep 2026, 1 Hz.
  `20260906T14` and `20260902T00/T21`, `20260903T07` are truncated
  (`invalid block type`) and were **skipped, not partially used**.
* **[LIVE]** 405 orderbook polls, 19:15–19:19 UTC 2026-09-06, used only to
  validate the replay.
* Scripts: `C:\Users\Joe\AppData\Local\Temp\kals-work\livetest\`
  — `replay.py` (book replay + size sweep), `valid.py` (live-vs-tape validation),
  `worst.py` (exact worst case with mutual exclusivity), `fills.py` (exposure at
  the reference price), `paidlag.py` (`paid_out` lag), `power.py`, `cfg.py`.
* **Collector health after all jobs: `kalshi_collector.py` PID 3381772 ALIVE,
  `crypto_feeds.py` PID 3385232 ALIVE. Free disk C: 51.3 GB.**
