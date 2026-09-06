# JOB 2 — FUNDING AND ELIGIBILITY MECHANICS

Run 2026-09-06, ~19:00–19:20 UTC. Account `4a175683-fae3-4fb0-a27f-6fdf40c7587a`,
balance $0.0047. **No orders placed, no money moved. Authenticated GETs only.**

Every claim is tagged **[LIVE]** (this account's own authenticated API call today),
**[DOC]** (published Kalshi / CFTC document) or **[INFER]** (reasoning, not measured).

---

## 0. THE HEADLINE — READ THIS BEFORE THE SIX ANSWERS

Two findings outrank everything the job asked for. Both are **[LIVE]**.

### 0.1 The BTC and ETH 15-minute liquidity programmes are DEAD, and have been since 12 May 2026

I paged the entire `/incentive_programs` collection — **178 pages, 177,014
programmes** (the brief said 80,000; it has more than doubled). Grouping every
programme by series and taking the maximum `end_date`:

| series | programmes ever | **scheduled in future** | last `end_date` | target_size |
|---|---:|---:|---|---:|
| **KXBTC15M** | 9,781 | **0** | **2026-05-12T16:45Z** | *field absent* |
| **KXETH15M** | 8,299 | **0** | **2026-05-12T16:45Z** | *field absent* |
| KXCRYPTOLEAD15M (Coin Race) | 6,385 | **180** | 2026-09-07T04:00Z | 1000.00 |
| KXSILVER15M | 2,420 | 24 | 2026-09-07T04:00Z | 300.00 |
| KXSOL15M, KXXRP15M, KXDOGE15M, KXBNB15M, KXADA15M | **0** | 0 | never existed | — |

BTC15M and ETH15M have had **no incentive programme for 117 days**. Their 18,080
historical rows carry **no `target_size_fp` field at all** — so any share model
fitted on those two series was fitted on markets that now pay nothing and whose
qualifying threshold was never published.

**The complete set of live 15-minute (900 s) programmes, right now**, at a steady
96 windows/day when open [LIVE]:

| series | markets/window | windows/day | **daily pool** | target/side | **hours** |
|---|---:|---:|---:|---:|---|
| KXCRYPTOLEAD15M (Coin Race) | 5 | 96 | **$9,600** | 1,000 | **24/7** |
| KXSILVER15M | 1 | 96 | $1,920 | 300 | CME futures hours |
| KXGOLD15M | 1 | 96 | $1,920 | 300 | CME futures hours |
| KXCOPPER15M | 1 | 96 | $1,920 | 300 | CME futures hours |
| KXNATGAS15M | 1 | 96 | $1,920 | 300 | CME futures hours |
| KXWTI15M | 1 | 96 | $1,920 | 300 | CME futures hours |
| **TOTAL** | **10 live at once, weekdays** | | **$19,200/day** | | |

**The commodity five are weekday-only, and I nearly got this wrong.** At the moment
I write this (Sunday 15:26 ET) there are **zero open commodity 15M markets** — all
are `initialized`, opening later. Counting historical programmes by ET weekday
[LIVE] shows why:

| series | Mon | Tue | Wed | Thu | Fri | Sat | Sun |
|---|---:|---:|---:|---:|---:|---:|---:|
| KXSILVER15M | 427 | 480 | 480 | 456 | 479 | **5** | **69** |
| KXCRYPTOLEAD15M | 700 | 960 | 960 | 880 | 960 | **960** | **785** |

Silver's 69 Sunday programmes fall **only in ET hours 18-23**, and its 5 Saturday
programmes only in ET hour 0. That is exactly CME futures hours: the commodity
series shut down around 1am ET Saturday and reopen **6pm ET Sunday** — matching
the 22:00 UTC programme start I saw scheduled. Roughly **41 hours dead per week**.

**Coin Race covers all 24 ET hours on both Saturday and Sunday.** Crypto never
closes. Averaged over a full week the commodity pool is worth ~$7,100/day against
Coin Race's flat $9,600/day.

Confirmed against the programme counts themselves: Coin Race ran 480 programmes/day
on 2026-09-04 and 09-05 (= 96 × 5), each commodity series 96/day. Coin Race's
$9,600/day reconciles with the brief's "$9,477/day advertised" to 1.3%.

**I initially misread this as a 6-hour overnight block and a $6,000 pool — that was
the schedule *lookahead*, not a restriction. The correct figure is $19,200/day
across 10 concurrently-live markets**, which is more than enough surface for a
"5 markets, both sides" configuration without ever touching Coin Race's mutual
exclusivity.

Coin Race is not *a* candidate. Among 15-minute **crypto** markets it is **the only
one left**. But the five commodity 15M series are a comparable pool in aggregate,
are **not mutually exclusive with each other** (unlike Coin Race, where exactly one
coin wins), and carry a **target size of 300 rather than 1,000** — a qualifying
threshold three times easier to meet, which matters a great deal because a snapshot
pays *nobody* unless both sides reach the target. **They deserve a hard look before
Coin Race is assumed to be the venue** — with two caveats: they are weekday-only,
and five commodity contracts are not five independent bets, so the diversification
is smaller than the count suggests.

### 0.2 The CFTC has ordered every exchange to re-file its incentive programmes by 14 September 2026 — eight days from now

The governing filing I retrieved (**Feb 11 2026 amendment**, [DOC] primary) says the
Program runs "until the earlier of **September 1, 2026**, or the date that Kalshi
amends or terminates the Program." **That date has already passed.**

The programme is nevertheless demonstrably alive — programmes are scheduled out to
2026-09-26 and rewards were being credited today [LIVE] — so it was extended by a
filing I could not retrieve. Search results report Kalshi refiled its *Volume*
Incentive Program on 4 Aug 2026 "in response to a CFTC request asking every DCM to
review and amend its incentive filings by **14 September 2026**" [DOC, secondary].

**The economics of this project rest on a subsidy whose published legal authority
expired five days ago, under a regulator-imposed review closing in eight days.**
Whatever the live test costs, spend it *before* 14 September, and commit no capital
on the assumption the programme survives that date unchanged.

### 0.3 The filed scoring rule is NOT the rule the 12.55% headline was computed under

This is outside Job 2's remit. I report it because it is load-bearing on the number
the whole project rests on, and I found it while reading the filing for §4.

The brief states the scoring rule as: *"Reference Price is the first level, walking
down from the best bid, where cumulative size reaches ONE FIFTH of Target Size."*

**The phrase "one fifth" — and every variant I searched (`fifth`, `20%`, `0.2`,
`/5`, `divided by five`) — appears ZERO times in the Feb 11 2026 CFTC filing** [LIVE
grep of the extracted text]. The filing says something different, verbatim:

> "If the highest yes bid price exists and is less than the highest possible price,
> **it is assigned to the Reference Yes Price**. ... Kalshi will add the size
> available at the current bid price to the Qualifying Yes Total Size ... If the
> Qualifying Yes Total Size is **greater than or equal to the target size**, the
> procedure is stopped here. Otherwise, Kalshi will find the next highest yes bid
> price and repeat **without reinitializing** the Qualifying Yes Total Size,
> Qualifying Yes Bids, **or Reference Yes Price**."

So under the filed rule the **Reference Price is simply the best bid**, fixed at
initialisation and explicitly never updated. The walk down the book determines only
*which* bids qualify (stop at **Target Size**, not one fifth of it). The multiplier
is therefore `0.5 ^ (ticks below the best bid)`.

**The two rules give materially different answers.** Computed on one frozen live
Coin Race book (`KXCRYPTOLEAD15M-26SEP061530-BTC`, target 1,000, discount 0.50,
posting 50 contracts; every figure hand-reconciled — the yes-side ladder sums
170 + 2.125 + 7.5 + 1.71875 + 0.0586 + 0.0037 + 0.0002 = 181.40625, and
50 / 181.40625 = 27.56%):

| | **filed rule** | brief's rule |
|---|---:|---:|
| 50 at the best bid (yes) | **27.56%** | 14.90% |
| 50 one tick behind (yes) | **15.98%** | 14.90% |
| 50 at the best bid (no) | **27.76%** | 15.66% |
| 50 one tick behind (no) | **16.12%** | 15.66% |

**Under the filed rule, holding the best bid is worth ~1.7x being one tick behind
(27.6% vs 16.0%). Under the brief's rule, queue position is worth exactly nothing
(14.90% either way).** The brief's modelled 12.55% mean sits near its own rule's
output and roughly half the filed rule's at-the-touch figure.

Three caveats, stated plainly: this is **one snapshot of one market**, not a
distribution; it assumes my size does not change anyone else's behaviour (precisely
what the critic says cannot be assumed); and **the Feb 11 filing nominally expired
on 1 September and I could not retrieve its successor**, so the rule actually in
force today is genuinely uncertain.

**That uncertainty is an argument for the live test, not against it — and it gives
the test a second, sharper job.** Posting 50 contracts at the best bid in one market
and one tick behind in another, then comparing realised credits, **discriminates
between the two rules directly**: the filed rule predicts a ~1.7x gap, the brief's
rule predicts none. That costs nothing beyond the test already planned and settles
which scoring model the P&L should be built on.

---

## 1. MINIMUM DEPOSIT AND FUNDING METHODS

`GET /portfolio/deposits` works, and this account has three real deposits [LIVE]:

| created (UTC) | gross | fee | fee % | type | status | **clear lag** |
|---|---:|---:|---:|---|---|---:|
| 2026-08-15T04:28:00 | $10.00 | $0.00 | 0.00% | debit | applied | **0 s** |
| 2026-08-15T04:45:06 | $19.39 | $0.38 | 1.96% | debit | applied | **0 s** |
| 2026-08-15T05:30:37 | $10.21 | $0.20 | 1.96% | debit | applied | **0 s** |

Measured, not quoted: **debit deposits credit instantly** — `created_ts` equals
`finalized_ts` exactly, all three. The ~2% card fee is real and is taken *out of*
the amount charged: $10.21 charged credits $10.01. **The first $10.00 deposit was
charged no fee**, consistent with a first-deposit waiver.

| method | minimum | Kalshi fee | time to clear | source |
|---|---|---|---|---|
| **Debit card** | $10 | **2%** (first deposit appears waived) | **instant — measured, n=3** | [LIVE]+[DOC] |
| **ACH / bank** | **$10** | **$0** | partial credit may be immediate; **full settle up to 5 business days**; ~2-day hold before withdrawable | [DOC] |
| **Wire** | **$1,000** — smaller wires are *returned* | $0 from Kalshi (your bank may charge) | same day | [DOC] |
| **Crypto** (via Zero Hash) | none listed | small surcharge | ~30 min | [DOC, secondary] |

**At $1,000 this is a real, quantified choice:**
- Debit = **$20 of fees**, funded in seconds.
- ACH = **$0**, but up to 5 business days, plus ~2 more before withdrawable.
- Wire = **$0 Kalshi fee**, same day — and $1,000 is *exactly* the minimum, sitting on the floor.

### Security holds — the part that actually decides the method

Newly deposited funds are subject to a withdrawal hold. From Kalshi's own
security-holds page [DOC, primary]:

- **Subject to a hold:** debit card / Apple Pay / Google Pay, **bank transfer (ACH)**
- **Exempt from any hold:** **wire transfer**, crypto, PayPal/Venmo, Cash App
- Duration: "Available once deposit settles" when withdrawing to the *same* method;
  "**Up to 2 days after settlement**" when withdrawing to a *different* method
- "Holds only apply to the original deposited amount. **Earnings beyond your
  deposited amounts can be withdrawn immediately** once they are settled cash."

A third-party guide claims a flat **seven-day** hold on all new deposits. **Kalshi's
own page does not say that, and I am going with Kalshi's.** I flag the conflict
because the difference matters: under ACH the $1,000 could be locked for anywhere
between "on settlement" and seven days, and the settlement itself takes up to five
business days. Two independent Kalshi pages agree that **wire is exempt** — the
wire page states "wire-deposited funds are available for withdrawal immediately."

**Revised recommendation — wire, not ACH.**

| | fee on $1,000 | time in | withdrawable |
|---|---:|---|---|
| **Wire** | **$0** from Kalshi (bank may charge) | same day if sent before 4pm ET | **immediately — no hold** |
| ACH | $0 | up to 5 business days | on settlement, +2 days to a different method (third-party source claims 7 days) |
| Debit | **$20** | instant | held until settled, +2 days to a different method |

**Wire is the right method for this test.** It is the only one that keeps the
$1,000 withdrawable on demand, it costs nothing at Kalshi, and $1,000 is exactly
the minimum — the test is sized precisely at the wire floor. The one caveat: wires
**below** $1,000 are automatically returned and take 3-5 business days to come
back, so it must be sent for the full $1,000 or more, in one transfer [DOC].

Do not use debit for $1,000 — a pure $20 loss, which is one entire Coin Race
window's pool. Use ACH only if no wire is available and the money will not be
needed back quickly.

Note in passing: LIP reward credits are *earnings*, not deposits, so they are
withdrawable as soon as they are settled cash and are not caught by any hold [DOC].

Caveat [INFER]: this account's largest deposit ever is $19.39. Per-method daily
deposit limits at the $1,000 level are **untested**, and no endpoint exposes them
(`/portfolio/deposit_limits` and eight similar paths all 404 [LIVE]).

---

## 2. SSN ON FILE, AND THE IRS THRESHOLD

**Is a verified SSN on file for this account? I could not determine this, and I want
to be explicit that I could not.** [LIVE — negative result]

Every plausible surface returned **404**: `/users/me`, `/user`, `/account`,
`/account/kyc`, `/account/identity`, `/account/tax`, `/account/profile`,
`/portfolio/kyc`, `/portfolio/profile`, `/portfolio/documents`,
`/portfolio/tax_documents`, `/users/self`, `/portfolio/restrictions`,
`/portfolio/limits`.

**The Kalshi v2 API exposes no KYC or tax-status endpoint. This question cannot be
answered by API and must be answered by the operator logging in.**

[INFER, strong but still inference]: the account has completed debit-card deposits
and executed trades on a CFTC-regulated DCM, both of which require completed
identity verification, and Kalshi collects SSN from US members at signup. So an SSN
is very likely on file. **That is not a measurement.**

**The threshold.** The LIP help page says "a verified Social Security Number (SSN)
must be on file to receive reward credits above annual IRS reporting thresholds"
but gives no number [DOC]. The number is the **1099-MISC** threshold, which the One
Big Beautiful Bill Act **raised from $600 to $2,000 for payments made from 2026**
[DOC, secondary — tax-practitioner sources, not Kalshi].

**Are rewards below the threshold still paid?** No Kalshi document I found says
either way. [INFER]: the sentence conditions the SSN requirement *on* being above
the threshold, which reads as "below it, no SSN needed" — but that is an inference
from one sentence's grammar and is **not** a safe basis for planning. Sub-threshold
rewards remain taxable income whether or not a form is issued [DOC].

**Practical read for a $1,000 test:** a test earning under $2,000 of reward credits
in calendar 2026 is below the reporting threshold anyway, so this is very unlikely
to gate the *experiment*. It would gate a scaled-up operation.

---

## 3. DOES PARTICIPATION REQUIRE REGISTRATION? — DECISIVE, AND THE ANSWER IS GOOD

This was flagged as the question that could kill the project. **It does not.**

From Kalshi's own CFTC rule filing, verbatim [DOC, primary — I pulled the PDF and
extracted its text locally after the fetcher choked on the font encoding]:

> "**Eligible Participants**" are all Kalshi members, except the following:
> (i) affiliates of Kalshi; (ii) members who have executed a Market Maker Agreement
> with Kalshi; (iii) Introducing Brokers, Futures Commission Merchants, and
> customers thereof when transacting via the IB or FCM.

> "Eligible Participants can receive incentives for improving liquidity via resting
> orders."

**No application, no registration, no opt-in, no market-maker status.** Being an
ordinary Kalshi member *is* the qualification. Resting a qualifying order in a
programme market is the entire mechanism.

**The risk runs opposite to what was feared:** executing a **Market Maker Agreement
would *disqualify* this account** from the LIP. Kalshi's help centre confirms MM
status is separately gated — "granted following a thorough review of financial
resources, trading experience, and business reputation" [DOC]. **Do not apply for
market-maker status. It would remove eligibility.**

One item to confirm by eye: non-US members are ineligible [DOC]. Not in doubt here,
but it is a membership attribute the API does not show.

---

## 4. PER-ACCOUNT CAPS ON INCENTIVE EARNINGS

**There is no per-account cap.** [DOC, primary]

The filing caps only the *schedule variables*, verbatim:

> 1. "Time Period" shall be no greater than 31 days;
> 2. "Target Size" will be greater than 100 contracts and less than 20,000 contracts;
> 3. "Discount Factor" will be no greater than 1.00; and
> 4. "Time Period Reward" shall be no less than $10 and no greater than $1,000 per calendar day encompassed in the Time Period.

Payment is `Time Period Liquidity Provider Score × Time Period Reward` — a pure
pro-rata share of a fixed pool. **A single participant taking 100% of a window's
score is paid 100% of that window's pool.** The cap is on the pool, not the person.

Live values confirm the pools in force [LIVE]: `period_reward` 200000 = **$20** per
market per 15-minute window (some BTC/ETH history at 100000 = $10);
`discount_factor_bps` 5000 = **0.50**, matching the 0.50^ticks taper.

**The binding constraint is not a cap — it is the pool.** Coin Race is $20 per
market-window. Winning 12.55% of a $20 pool is **$2.51 per market-window.** That is
the real ceiling to reason about, not a rulebook limit.

---

## 5. API RATE LIMITS — THE PROPOSED CONFIGURATION IS INFEASIBLE ON BASIC

Token costs are **live from this account** — `GET /account/endpoint_costs` [LIVE]:

- `default_cost`: **10** tokens
- **cost 2**: `DELETE /portfolio/events/orders`, `DELETE /portfolio/events/orders/:order_id`, `DELETE /portfolio/events/orders/batched`, `GET /portfolio/orders/:order_id`
- `POST /account/api_usage_level/upgrade`: 30 — **the upgrade endpoint exists and is self-service** (not called; it is a POST)

So **create = 10 tokens, cancel = 2 tokens.**

Tiers [DOC]:

| tier | read tok/s | write tok/s | write bucket |
|---|---:|---:|---|
| **Basic** | 200 | **100** | **1 second** |
| Advanced | 300 | 300 | 2 seconds |
| Expert | 600 | 600 | 2 s |
| Premier | 1,000 | 1,000 | 2 s |
| Paragon / Prime / Prestige | 2,000 / 4,000 / 10,000 | 2,000 / 4,000 / 8,000 | 2 s |

**Arithmetic for "both sides of 5 markets, re-quoted once a second":**

```
10 resting quotes (5 markets x 2 sides), full cancel-and-replace each second:
   10 cancels x  2 tokens =  20
   10 creates x 10 tokens = 100
                            ---
              write load  = 120 tokens/second
```

| tier | budget | load | verdict |
|---|---:|---:|---|
| **Basic** | 100/s, 1 s bucket, no burst reserve | **120/s** | **INFEASIBLE — 20% over, sustained 429s** |
| Advanced | 300/s, 600 burst | 120/s | **40% utilisation — comfortable** |

**On Basic the described configuration cannot run.** Batching does not rescue it:
batch create is billed **10 tokens per order**, batch cancel **2 per order** —
batching saves round-trips, not tokens [DOC]. 429s carry no `Retry-After` and no
`X-RateLimit-*` headers, so the client must choose its own backoff [DOC].

Basic's actual ceiling is 100 ÷ 12 = **8.3 quote-replacements/second** — four
markets both sides, not five.

**Two ways out, and the second is better:**

1. **Upgrade to Advanced.** Self-service via `POST /account/api_usage_level/upgrade`
   [LIVE — endpoint confirmed to exist]. Takes the load to 40%. **I did not call it:
   it is a POST that changes account configuration and needs your sign-off.**

2. **Stop re-quoting every second.** The scoring rule pays for **size resting at a
   good price at each 1-per-second snapshot** — it pays nothing for churn. An order
   that sits still scores identically to one cancelled and replaced at the same
   price. Re-quote only when the book moves against you and the write load drops by
   roughly an order of magnitude, putting the configuration inside Basic with room
   to spare. **The "10 order ops/second" in the brief is a worst case, not a
   requirement of the programme.**

Read side is not a constraint either way: GETs cost 10, Basic allows 200/s = 20
GET/s; polling 5 books once a second is 25% of budget, and a WebSocket feed costs
nothing against it.

Current tier of this account [INFER]: **not exposed by any endpoint** — I probed
`/account/usage_level`, `/account/api_usage_level`, `/account/tier`,
`/account/rate_limits`; all 404 [LIVE]. Unupgraded accounts start at Basic, so
assume Basic until the upgrade call is made.

---

## 6. SETTLEMENT TIMING — MEASURED TWO INDEPENDENT WAYS

### 6a. From this account's own settlement history [LIVE, n=4]

`settled_time` minus `close_time`, with close times pulled per-ticker from
`/markets/{ticker}` rather than inferred from the ticker string:

| market | close_time | settled_time | **lag** |
|---|---|---|---:|
| KXBTC15M-26AUG150130-30 | 2026-08-15T05:30:00Z | 05:30:02.371 | **2.4 s** |
| KXBTC15M-26AUG150045-45 | 2026-08-15T04:45:00Z | 04:45:12.378 | **12.4 s** |
| KXBTCD-26AUG1501 (hourly, `settlement_timer_seconds`=60) | 2026-08-15T05:00:00Z | 05:02:42.421 | **162.4 s** |
| KXBTC15M-26AUG222115-15 | 2026-08-23T01:15:00Z | 2026-08-23T15:35:37 | **51,637 s = 14.34 h** |

Three of four settled in seconds. **One took 14.3 hours.** I could not explain the
outlier: it was a total loss (revenue 0), but so were two of the three fast ones, so
"losses settle lazily" does not explain it. It closed 21:15 ET Saturday and settled
11:35 ET Sunday. **1-in-4 is too high a rate to dismiss and n=4 is too small to
trust.** Open risk.

### 6b. Live, sub-second, measured today [LIVE, n=14 across two consecutive windows]

Because n=4 is not evidence, I polled the exchange through two real closes
(19:15:00Z and 19:30:00Z today) at ~0.6 s resolution, read-only
`GET /markets/{ticker}`. Seconds from `close_time` to `status=finalized`:

| market | 19:15 window | 19:30 window |
|---|---:|---:|
| KXBTC15M | 7.74 | **6.65** |
| KXETH15M | 13.80 | **11.50** |
| CoinRace-SOL | 37.52 | 48.15 |
| CoinRace-HYPE | 37.61 | **51.42** |
| CoinRace-XRP | 38.77 | 48.06 |
| CoinRace-ETH | 42.81 | 47.26 |
| CoinRace-BTC | 42.90 | 48.32 |

| group | n | min | max | mean |
|---|---:|---:|---:|---:|
| **Coin Race** | 10 | 37.52 | **51.42** | **44.28** |
| **BTC15M / ETH15M** | 4 | 6.65 | 13.80 | 9.92 |

Trading stops within **0.7 s** of close (measured on all 14). Determination follows
in **6.7–51.4 s**, and the split between the two groups is stable across both
windows — this is a structural property of the series, not noise.

**The operationally important line: Coin Race — the only 15-minute crypto series
still paying — finalises in 37–51 s, about 4.5x slower than BTC15M/ETH15M
(6.7–13.8 s).** The next window opens the instant the old one closes, so capital
held in a Coin Race position is unavailable for roughly **the first 4–6% of the
next window.** Real, and worth building into the quoter's schedule, but **not a
binding capacity constraint at $1,000** — the worst case observed is under a
minute against a 15-minute cycle.

**Capital recycling at $1,000 is therefore not gated by settlement.** It is gated by
collateral sitting in *resting orders*, which never settle at all — they are locked
until filled or cancelled. `GET /margin/balance` [LIVE] exposes exactly this as
**`resting_orders_margin`** (currently $0.0000), alongside `available_balance` and
`settled_funds`.

### 6c. But reward credits are NOT fast — measured [LIVE, n=24,285]

Capital recycles in seconds. **The subsidy does not.** Bucketing all short-window
crypto-15M programmes by age since window end:

| age since window end | n | paid | **paid %** |
|---|---:|---:|---:|
| 0–12 h | 220 | 0 | **0.0%** |
| 12–24 h | 240 | 60 | 25.0% |
| 24–48 h | 480 | 275 | 57.3% |
| **48–72 h** | 480 | 480 | **100.0%** |
| 3–7 d | 1,880 | 1,880 | 100.0% |
| >7 d | 20,965 | 20,892 | 99.7% |

**Nothing is paid within 12 hours. Full payment lands 48–72 hours after the window
closes.** Essentially every crypto-15M window eventually pays (99.7–100%), which is
a genuinely good sign for programme reliability — but rewards are **not** working
capital and cannot fund the next window. At $1,000 with a 2–3 day reward lag, the
subsidy accrues behind the trading capital; it does not compound into it.

---

## 7. TWO LEDGER FACTS CONFIRMED, ONE SHARPENED

**The taker fee is not 0.07·p·(1−p) — it is that value rounded UP to the nearest
$0.0001.** All four fills match to the last digit [LIVE]:

| market | n | p | 0.07·p·(1−p)·n | **ceil to 1e-4** | actual |
|---|---:|---:|---:|---:|---:|
| KXBTC15M-26AUG222115-15 | 12.37 | 0.16 | 0.116377 | **0.1164** | 0.116400 |
| KXBTC15M-26AUG150130-30 | 38.97 | 0.47 | 0.679520 | **0.6796** | 0.679600 |
| KXBTCD-26AUG1501 | 54.99 | 0.33 | 0.851080 | **0.8511** | 0.851100 |
| KXBTC15M-26AUG150045-45 | 19.32 | 0.49 | 0.337965 | **0.3380** | 0.338000 |

Rounding is to $0.0001 — the same 1e-4 unit as `period_reward`. Four for four.

**Makers pay nothing:** `maker_fees_dollars` = "0.000000" on all four orders [LIVE].

**Full ledger reconciliation** [LIVE]: deposits credited $39.02 − trade cost
$56.3202 − trade fees $1.9851 + settlement revenue $19.32 = **$0.0347**, against an
actual balance of **$0.0047**. **Residual $0.0300, unexplained.** It closes to 0.08%
of the money that moved, and it validates the deposit-fee interpretation used in §1
(fee deducted from the amount charged), but I did not chase the last 3 cents to
ground and am not claiming the ledger fully reconciles. Separately,
`/margin/balance` reports `settled_funds` **$0.0091** where `/portfolio/balance`
reports **$0.0047** — two live endpoints, two different numbers for the same
account, also unexplained.

---

## WHAT THIS SETTLES, AND WHAT IT DOES NOT

**Settled:**
- Eligibility is automatic; no application. **Q3 — the question that could have killed the project — is answered, and the answer is yes.** (§3)
- No per-account cap exists. (§4)
- Funding is cheap and fast: ACH at $0 or wire at $0, not debit at $20. (§1)
- Capital frees in seconds after a close, not minutes. (§6a/6b)
- Reward credits take 48–72 hours. (§6c)
- The fee formula exactly, including its rounding rule. (§7)

**Not settled, and gating:**
- **Whether the SSN is on file** — no API surface exists; the operator must look. (§2)
- **The current API tier** — no API surface exists; assume Basic. (§5)
- **Whether the LIP survives the CFTC's 14 September re-filing deadline.** (§0.2)
- **Which reference-price rule is actually in force** — the filed rule and the
  brief's rule differ by ~1.7x on queue position, and the filing I could retrieve
  nominally expired on 1 September. (§0.3)
- **Why 1 of 4 historical settlements took 14.3 hours.** (§6a)
- **Deposit limits at $1,000** — this account has never moved more than $19.39. (§1)
- **The exact ACH withdrawal-hold length** — Kalshi's page and a third-party guide
  disagree (settlement+2 days vs 7 days). Moot if funding by wire. (§1)

## RECOMMENDED ACTIONS

1. **Log in and confirm the SSN is on file.** One minute, and no API can do it. (§2)
2. **Fund by WIRE, for exactly $1,000 or more, in one transfer.** $0 Kalshi fee,
   same day, and the only method with **no withdrawal hold** — the money stays
   pullable if the test goes wrong. Never debit ($20). ACH only as a fallback. (§1)
3. **Do not apply for market-maker status** — it would *remove* LIP eligibility. (§3)
4. **Re-point the test.** BTC15M and ETH15M pay nothing and have not since 12 May.
   The live surface is Coin Race ($9,600/day, target 1,000, **24/7**) plus five
   commodity 15M series ($9,600/day combined, target **300**, **weekday-only**).
   **Look at the commodities before assuming Coin Race is the venue** — the lower
   target is a real edge. **If the test runs on a weekend, Coin Race is the only
   option.** (§0.1)
5. **Decide the API tier before the test, not during it.** Either upgrade to Advanced
   (self-service POST, needs sign-off) or design the quoter to re-quote on
   book-change rather than on a 1 Hz timer — the second is free and is what the
   scoring rule actually rewards. (§5)
6. **Have the test discriminate between the two scoring rules** — post at the touch
   in one market and one tick behind in another. It costs nothing extra and settles
   which model the P&L should be built on. (§0.3)
7. **Move before 14 September** if the test is going to happen at all. (§0.2)

---

## PROVENANCE

Working files, all under `C:\Users\Joe\AppData\Local\Temp\kals-work\jobFUND\`:

| file | what it is |
|---|---|
| `ledger.json` | this account's settlements, fills, orders |
| `iplag.json` | all 177,014 incentive programmes, paged |
| `live_short.json` | the 300 live short-window programmes |
| `lagpoll2.jsonl` | the live close poll, 14 finalizations at ~0.6 s resolution |
| `book_snapshot.json` | the frozen Coin Race book used for §0.3 |
| `lip2.txt` | extracted text of the Feb 11 2026 CFTC filing |
| `pdf_x.py` | PDF extractor with ToUnicode CMap support |
| `refprice2.py` | the §0.3 scoring comparison, with the ladder walk printed |

`pdf_x.py` exists because the repo's `pdftxt.py` returns font-table bytes rather
than text for this filing — it scrapes every stream including embedded fonts. The
new one restricts to content streams and maps CIDs through the ToUnicode CMaps.
Worth keeping for future CFTC filings.

**Two false starts, recorded so they are not repeated:**
1. The first lag poller silently collected nothing for an hour. `GET /markets?series_ticker=X` with no status filter returns the **30 furthest-future** markets, so the one about to close is never in the list. Fixed by polling `GET /markets/{ticker}` directly.
2. I first read the commodity 15M programmes as a 6-hour overnight block worth $6,000. That was the schedule lookahead. The real figure is $19,200/day across 10 concurrent markets, weekday-only for the commodity five.

**Resource check at end of run:** `kalshi_collector.py` (PID 3381772) and
`crypto_feeds.py` (PID 3385232) **both alive**. Disk free on C: **52 GB**. My own
lag poller (PID 3439388) was stopped cleanly after the second window; no background
jobs of mine are still running.

**Nothing was ordered, amended, cancelled or funded. Every call in this job was a
GET. The one state-changing endpoint I found — `POST /account/api_usage_level/upgrade`
— was deliberately not called and needs the operator's sign-off.**
