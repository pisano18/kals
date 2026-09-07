# Kalshi liquidity-rebate project — state of evidence, 2026-09-07 05:40Z

**Purpose of this document.** It is a self-contained brief for an independent
reviewer. It states what has been *measured*, what has been *retracted*, and
what is *still unknown*, with the evidence for each. It deliberately includes
the errors, because several headline numbers in this project have been
measurement bugs and the corrections are the most useful part of the record.

**Nothing here is a recommendation to trade.** Total money at risk so far:
**about four cents**, in deliberate probes.

---

## 0. THE SETUP

An operator with **$20.00** on Kalshi wants to test whether the exchange's
**Liquidity Incentive Program (LIP)** — which pays you for *resting* orders,
filled or not — is a tradeable edge. The framing is explicitly
*information per dollar*, not return: the $20 is for learning.

Infrastructure: a WebSocket collector has been recording Kalshi's order book,
trades and settlement index continuously since 2026-08-25 (`orderbook_snapshot`,
`orderbook_delta`, `trade`, `ticker`, `cfbenchmarks_value`), plus constituent
crypto exchange feeds. All analysis is replayed off that tape.

---

## 1. THE SCORING RULE — and an unresolved fork that changes everything

Kalshi's help centre states, verbatim:

- Snapshots are taken **once per second at a random moment within the second**.
- **Target Size** is *"the depth that must be resting on each side for a
  snapshot to count"* — it is **aggregate book depth, not your own size**.
- **Reference Price**: *"Walking down from the best bid, the first price level
  at which cumulative resting size reaches one fifth of the Target Size... it
  is not always the best bid or ask — a small order alone at the top of the
  book does not set it."*
- Orders at or better than the Reference Price get a **1.0** multiplier; below
  it, `discount_factor ^ (ticks below)`. `discount_factor_bps: 5000` → **0.50**.
- *"Your snapshot score is your share of the yes side **plus** your share of
  the no side, so a single snapshot is worth at most 2.0 across all
  participants."*
- *"Your Time Period score = your total snapshot scores ÷ **all participants'**
  total snapshot scores."*
- `reward = TimePeriodScore × PeriodReward × (non-excluded ÷ total snapshots)`,
  **rounded down to the cent**.
- A snapshot is **excluded** if the market is closed or if resting depth fails
  to reach Target Size on **either** side.
- **Minimum payout $1.00.**

### 1a. SETTLED: there is no "2×"

A long-standing open item was whether "share of yes **plus** share of no"
doubles every figure. It does not. The numerator is `(s_yes + s_no)`; the
denominator — *all participants' total* — is **2.0 per qualifying snapshot**.
So

```
TimePeriodScore = Σ(s_yes + s_no) / (2·N_qual)
reward          = TimePeriodScore × R × (N_qual / N_total)
                = R × mean over ALL snapshots of (s_yes + s_no)/2
```

The conservative "average of the two sides" implementation was exactly right.
**The qualification haircut must be applied exactly once** — by averaging over
*all* snapshots, not by multiplying again afterwards. Applying it twice is a
live failure mode: one internal file did exactly that.

### 1b. UNRESOLVED, AND IT IS THE BIGGEST OPEN ITEM: Rule A vs Rule B

Two mutually incompatible versions of the Reference Price are on record.

| | Rule A (help centre) | Rule B (CFTC filing rules02112639183, 11 Feb 2026) |
|---|---|---|
| Reference Price | walk down until cumulative size reaches **Target/5** (60 contracts) | the Reference Price **is the best bid**; the walk stops at the **full Target Size** (300) |
| Orders below it | score `0.5^ticks` — **always something** | **not Qualifying Bids at all — exactly zero** |

On the same tape the two differ by **1.44×–1.76×** at 20 contracts a side, in
**every window, in all five families**. Every share number this project has
produced assumes **Rule A**.

**Consequences if Rule B is live:** all modelled shares are 1.44–1.76× too low;
the family ranking inverts (gold stops being worthless and becomes the best
venue); and the recommendation "stand one tick behind the touch" scores
**exactly zero**, not 0.5×, in 5.6–57.3% of snapshots.

**A cheap discriminator exists and has never been tried.** Kalshi renders a
per-order qualification indicator (a dot plus an "efficiency percentage") on
resting orders in reward markets. Resting one order *at* the touch (a positive
control that must read 100% under both rules) and one **3 ticks behind** would
read **12.5%** under Rule A and **gray / non-qualifying** under Rule B. Cost:
about **$2.45**. This is the single highest information-per-dollar action
identified.

---

## 2. WHAT IS MEASURED AND STANDS

### 2a. Programme economics (from the API, 178,245 programmes paginated)

- `period_reward` is in units of **1e-4 dollars**. `200000` = **$20.00** per
  market per 15-minute window. Proven arithmetically: `KXTRUMPACT` 909090 × 11
  markets and `KXTRUMPENDORSEMENTS` 1428571 × 7 both give exactly $1,000.00
  (= 10,000,000/11 and /7).
- Historical payout: **$5,051,195 over 86.8 days** across all families
  (~$58,171/day). Coin Race alone: **$9,600/day advertised, ~$8,294/day paid**,
  95–100% of programmes paid.
- Minimum pool observed is **$10** (n=8,644 at exactly $10), matching the
  filing's "$10–$1,000 per calendar day", **not** the help centre's "$1–$1,000".

### 2b. The five commodity families — first tape ever recorded

`KXGOLD15M, KXSILVER15M, KXWTI15M, KXNATGAS15M, KXCOPPER15M`. All
`exchange_index 0`, all `fee_type: quadratic` (**makers pay nothing**),
`target_size 300` (versus Coin Race's 1000), `$20` per 15-minute window,
`discount_factor_bps 5000`.

**Tick grid is NOT uniform and this has bitten twice:**
`price_level_structure` lives on the **market** record, *not* the series —
gold/silver/WTI are `tapered_deci_cent` (0.1c below 10c and above 90c, 1c
between); natgas/copper are `linear_cent`. The market record also carries
`price_ranges` giving the exact step per band, which should be used instead of
any hardcoded rule.

**Windows per day: ~89, not 24.** (See retraction §3a.)

### 2c. Book reconstruction — the rule, established by counting

| | carries level arrays | bare |
|---|---|---|
| **FIRST** snapshot of a market | **264** | 14 |
| **LATER** snapshots | **0** | 468 |

The first `orderbook_snapshot` carries the opening ladder in
`yes_dollars_fp` / `no_dollars_fp` (median depth **86,526 yes / 68,866 no**);
every later one is a bare resync marker. **Correct rule: SET the book when a
snapshot carries levels, CLEAR it when it does not.** Clearing on *every*
snapshot destroys the opening ladder for the market's whole life and produces a
**26% qualification rate where ~97% is correct**. Two internal files contained
that bug.

Also: sizes are fractional and must be rounded — float residue leaves levels
holding 3e-7 contracts that a naive `>0` test treats as live top-of-book.

### 2d. Qualification rate: 93–99%

Measured on tonight's tape with correct reconstruction, 16–24 complete windows
per family: Gold 98.5%, Silver 99.3%, WTI 99.0%, NatGas 97.1%, Copper 93.0%.

### 2e. Net P&L per family (the headline measurement)

S = 20 contracts per side, re-pegged to the reference price each second, **back
of queue** (pessimistic), $1.00 floor applied per window, inventory marked to
the settled result. n = 24 settled windows per family, 125 markets, 6 h of tape.

| family | grid | gross rebate | paid after floor | inventory P&L | **NET / window** | worst |
|---|---|---|---|---|---|---|
| KXNATGAS15M | cent | 1.746 | 1.712 | +0.458 | **+2.170** | −7.50 |
| KXCOPPER15M | cent | 0.996 | 0.480 | +1.343 | **+1.824** | −6.80 |
| KXSILVER15M | taper | 1.125 | 0.770 | +0.644 | **+1.415** | −5.34 |
| KXGOLD15M | taper | 0.453 | 0.000 | +0.436 | **+0.436** | −4.40 |
| KXWTI15M | taper | 1.051 | 0.793 | −0.564 | **+0.229** | −8.45 |

**Inventory P&L is mostly positive.** The mechanism: when both legs fill you
hold a YES *and* a NO in the same market, which must pay exactly $1.00 against
a cost of ~$0.97. That 3c is the maker's spread.

**THIS IS AN UPPER BOUND.** The model has **no cash constraint** — it rests and
fills 20 on both sides (~$19.40) without checking the cash existed at that
instant. A capital-constrained version is running.

### 2f. Placement: the reference price IS the touch here

Share of qualifying snapshots where the reference price equals the best price:
**Gold 82.4%, WTI 71.1%, Silver 62.3%, NatGas 57.7%, Copper 56.9%.** Median 0
ticks behind, both sides, every family. This is the **opposite of Coin Race**,
where the reference sits a median 4 ticks below the touch.

Mechanism, verified: the reference equals the touch exactly when the touch
alone holds ≥ Target/5 = 60 contracts. Median size at the touch is 71–522
contracts. It is book shape, not a coding artefact (99.83–100% agreement over
26,044–33,536 side-snapshots per family).

**Consequence:** "stand back at the reference price" buys almost no fill
protection here — it sheds only 5–16% of taker volume while costing 6–13% of
credit at S=20. In 4 of 5 families that is a *bad* trade. The real lever is one
tick behind the touch: keeps 64–73% of credit, sheds 45–64% of exposure.

### 2g. Account and order mechanics (all verified live)

- **Order API is V2.** `POST /portfolio/orders` returns **410
  `deprecated_v1_order_endpoint`**. Correct: `POST /portfolio/events/orders`,
  body `{ticker, side ("bid"=buy YES / "ask"=sell YES), count (fp string),
  price (fp dollars string), time_in_force, self_trade_prevention_type,
  client_order_id, post_only, exchange_index}`.
- **Cancel:** `DELETE /portfolio/events/orders/{id}?exchange_index=N`. The
  query parameter is **required off shard 0** — without it the cancel returns
  404 and **silently does not cancel**. Kalshi signs the path *without* the
  query string.
- **Resting orders DO reserve funds, cumulatively.** Proven by a straddle test
  on a shard holding $0.0286: an order needing $0.0150 was accepted, one
  needing $0.0250 was refused `insufficient_balance`. Arithmetic closes exactly
  ($0.0286 − $0.0100 − $0.0150 = $0.0036 available).
- **But `balance_dollars` is GROSS** — it does not net out reserves, in the API
  *or* in the app, and `/portfolio/summary/total_resting_order_value` returns
  403. `GET /portfolio/resting_order_value` is documented but **404s**. There is
  **no readable available-funds figure**; a client must track reserves itself.
- **Netting is OFF**, read directly: `GET /portfolio/subaccounts/netting` →
  `enabled: false` on both shards. Kalshi's help centre: Collateral Return
  *"gives you cash back early when you buy hedged positions"* — it applies to
  **filled** positions, **not resting orders**, so it does **not** reduce the
  capital needed to quote. And *"may make you unable to sell positions for which
  you've already had collateral returned."* The flag *"is enabled at the first
  moment a user places their first order in a given event"* and *"there is no
  way to retroactively enable or disable"* it.
- **Consequence — no clean exit at full deployment.** Netting off: you can sell,
  but posting the sell reserves `(1−p)`, cash a deployed account lacks. Netting
  on: you may be unable to sell at all. **Every "hedge if it goes wrong" in
  every plan so far is unfunded.**
- **Kalshi supports fractional contracts** (a real fill of **0.02** contracts
  exists).
- **Fees round UP.** `0.07 × 0.56 × 0.44 × 0.02 = $0.000345` predicted,
  **$0.000400** charged. Second instance: fill at 0.30, exact 0.0147,
  charged **0.0150**.
- **Makers pay nothing — proven non-vacuously.** Every prior fill on the account
  was `is_taker: true`, making a zero maker fee trivially true; that inference
  was retracted once. A resting 1c YES bid was then hit with **`is_taker:
  false`, `fee_cost: 0.000000`**.
- **Shards:** funds sit in four wallets; commodities are `exchange_index 0`,
  Coin Race is `2`. The app auto-transfers between them (observed: $0.0300
  moved 0→2 at the exact timestamp of a manual trade). `POST
  /portfolio/intra_exchange_instance_transfers` **404s** though the GET works;
  the documented mechanism is `PUT /portfolio/target_balance_allocation`,
  untested.
- **Deposits:** bank transfer **free**; the account's two card deposits were
  charged **1.96%**.
- **Our resting size IS visible in the public depth feed** — 1.00 contract
  placed at an empty $0.02 level appeared as `1.00 @ $0.02` in `yes_dollars`
  within 20 s. Every share figure assumes this and it had never been tested.

### 2h. Adverse selection — demonstrated live, for one cent

A 1c YES bid was rested when the book was **bid 18c / ask 21c** — 17 cents
below the touch, apparently unfillable. Twelve minutes later the contract had
collapsed; the book walked down through 6c, 4c, 2c and **hit the 1c bid on the
way down**. It settled worthless.

The fill did not arrive because someone blundered. It arrived because the
contract had become worth about a cent. Conditional on being filled, the win
probability is ~1%, not the ~21% implied when the order was placed:
`0.01 × $0.99 − 0.99 × $0.01 = $0.0000` — **exactly fair**. The 99:1 payout is
precisely cancelled by the 1:99 odds *given a fill*.

---

### 2i. THE CAPITAL-CONSTRAINED RESULT — the marginal dollar dies at $60

Same model as §2e, but posting only the size the cash actually supports
(netting off, so the two legs do not offset; a fill converts reserve into a
position that is not released until settlement). Net $/window:

| family | $20 | **$60** | $150 | $500 |
|---|---|---|---|---|
| KXNATGAS15M | +1.084 | **+2.170** | +2.170 | +2.170 |
| KXCOPPER15M | +1.861 | **+1.824** | +1.824 | +1.824 |
| KXSILVER15M | +0.806 | **+1.415** | +1.415 | +1.415 |
| KXWTI15M | **−1.363** | +0.229 | +0.229 | +0.229 |
| KXGOLD15M | **−1.441** | +0.436 | +0.436 | +0.436 |

Mean size actually resting: **6.2–12.1 contracts at $20** versus **19.1–19.8 at
$60**. **$150 and $500 are identical to $60** — the constraint stops binding
there. At $20 most windows fall under the $1.00 floor and pay zero, and gold
and WTI go outright negative.

**The number this project distrusts in its own result:** ×89 windows/day gives
$193/day on $60 of capital, a >300%/day return. That is the shape of figure
this project has been wrong about repeatedly. It rests on **6 hours of
Sunday-evening tape** (the weekend reopening — plausibly the least
representative session of the week) and assumes ~22 h/day of continuous
quoting with a re-peg roughly every 5 s, i.e. **~15,000 order operations per
day**, against unknown rate limits. **The per-window figures are defensible;
the per-day figures are not, and should not be quoted.**

## 3. RETRACTIONS — every headline this project got wrong

### 3a. "The commodity families run a 6-hour session, 24 windows/day" — WRONG
Measured on **2026-09-06, a Sunday** — the CME futures weekend reopening.
Thursday 2026-09-03: **89 settled markets per family**, closes in 23 of 24 ET
hours (one empty hour at 04:00 ET, unexplained). Saturday: 1. So every
"$/session" figure published was **~3.7× too low**.

### 3b. "3.3× cheaper than Coin Race" — WRONG COMPARISON
That was the ratio of *target sizes* (300 vs 1000), not of *share obtained*.
Measured: 50 contracts buys ~21% of silver's or copper's no side versus 11.80%
on Coin Race — **~1.8×**, not 3.3×.

### 3c. A single book poll is a selection artefact
The first poll of copper's no side scored **96** (implying a 34% share at
S=50). Six polls give a median of **185** and a range of **104–858**.

### 3d. "Makers pay nothing" (first version) — VACUOUS
Cited `maker_fees_dollars: 0.000000` on four orders that were all
`is_taker: true`. Trivially true. Retracted, then re-established properly (§2g).

### 3e. "Nothing has ever been paid" — WRONG
Read only page one of `/incentive_programs`, which is all future windows.
Paginating showed **68,805 of 80,000 paid**.

### 3f. Two of my own measurement scripts, tonight
1. `price_level_structure` read from `/series`, where it does not exist → grid
   came back `None` → cents applied to every family: **the exact bug the script
   was written to fix.**
2. **`taker_side` ignored.** On Kalshi's dual book a taker buying YES consumes a
   resting **NO** bid and vice versa, so at most one of two quotes can be hit by
   any trade. Counting every trade against both produced "40.0 fills" (both
   sides full) in nearly every window and a spurious +$1.48 inventory P&L.
3. A probe script named `bisect.py` **shadowed the stdlib module** and produced
   an unrelated import error that masked the real API response.
4. A detector that reported "0.0% of snapshots carry levels" — and a confident
   verdict refuting a correct report — because its key list omitted the `_fp`
   suffix. Only the key-set histogram printed beside it exposed the error.
   **A detector that reports absence must print what it did see.**

### 3g. Ranking incentive families by `period_reward` without dividing by period length
Claimed one family paid 7× crypto; per hour it pays a tenth.

---

## 4. THE RUIN ANALYSIS — why $20 specifically fails

Independent adversarial pass, reproduced on tape:

- Collateral per two-sided pair is **$0.96–0.99**, so $20 buys ~**20 pairs in
  ONE family**. Spreading across all five puts every one under the $1.00 floor
  and pays **literally $0.00**.
- At S=20 the **re-hedge headroom** (`B/S − C`) is **0.87–2.87 cents**. The
  un-filled leg's reference price moves further than that in **34–45% of
  60-second intervals**. So the first fill converts a "locked pair" into a naked
  directional position **by arithmetic, with no market view required**.
- Worst window: **−$19.96 to −$19.97 in all five families**; **12.2%** of
  window-family observations lose >90% of the account; 21.7% lose >50%.
- The reference price travels a median **0.560–0.748** *within* a single
  15-minute window. Settlement is not the risk — the journey is.
- A stale, un-repegged quote loses **−10.30 c/contract**. Re-pegging is forced
  roughly **once per 5.4 seconds**.
- There is **no fundable stop** (§2g).

**The $1.00 floor is the binding constraint throughout, and it is a cliff:**
earning $0.99 in a window pays **zero**, not $0.99.

---

## 5. OPEN QUESTIONS, RANKED

1. **Payout TIMING is not understood, though the programme is alive.**
   Resolved tonight: 178,340 programmes scanned, the latest `end_date` marked
   paid is **2026-09-07 05:30Z (minutes old)** and **3,056 programmes are
   scheduled for future windows**, so the programme is being funded and the
   "CFTC scope clause expired 2026-09-01" hypothesis is NOT supported.
   **But the timing model is broken and this matters, because it is the
   readout.** Three things do not reconcile: (a) an inferred daily batch at
   05:00–05:15Z **did not fire** — watched live, **0 of 14** programmes ending
   03:45Z/04:00Z flipped over 40 minutes; (b) yet something ending 05:30Z is
   already marked paid, a ~15-minute lag against a measured profile of 22–24 h;
   (c) **6,200 ended programmes remain unpaid past 26 h**, the oldest from
   2026-03-15. Candidate explanations not yet separated: `paid_out` may be set
   at creation for some incentive types; there may be more than one incentive
   type in the feed (`incentive_description: series_lip` is one); or the flag
   may not mean money moved. **Until this is resolved, "post a quote, wait, read
   the credit" has no defined waiting time.**
2. **Rule A or Rule B** (§1b) — changes every share number by 1.44–1.76× and
   inverts the family ranking.
3. **Has a LIP credit ever landed in any account?** Nobody in this project has
   seen one. There is **no API line item** — a credit is readable only as a
   balance residual, which does reconcile to **$0.0000** over the account's
   entire life, so a $1.00 credit would be unambiguous.
4. **Realised share once we are in the book.** All shares are modelled on an
   undisturbed book. Bounded, not eliminated: across 239,955 natural
   experiments nobody steps strictly inside an added order (slope
   −0.010 ± 0.051 lots/lot) and paid share moves +0.03% ± 1.15% per 50 lots.
   But every one of those events is an *existing* participant observed for
   ≤30 s; a new persistent participant taking ~15% of a pool is a different
   question, and the response operates over days, which tape cannot settle.
5. **Whether the visible book is the whole book.** If Kalshi scores orders the
   public depth feed does not publish, every share is overstated. Untestable
   from public data. Flagged as the largest unquantified risk.

---

## 6. WHAT IS *NOT* THE REBATE STRATEGY, AND IS BETTER EVIDENCED

Two other results on the same tape:

- **`pin`** — a taker strategy exploiting the collapse of settlement variance
  near expiry (settlement is the mean of 60 one-second prints, so
  `Var(settle − strike) = 880σ²` and sd collapses far faster than √time).
  Out of sample: **+2.54c/contract, t = +5.0** on 335 closes against an MDE of
  1.54c. Bootstrap 95% CI on $/day **[+19, +48]**; peak concurrent capital
  **$49.70**. Its `t` has risen on every successive tape (3.0 → 5.0). Main
  untested risk: the backtest always wins the race for a stale quote; reality
  will not.
- **`informed`** — maker fills at the touch: **+0.48c/fill, t = +6.4** on 17.1M
  fills, random-sign control clean at t = −0.9. Capacity unmeasured.

**On evidence, `pin` is the strongest thing here and needs ~$50.**

---

## 7. WHAT WOULD BE MOST USEFUL FROM A REVIEWER

1. **Adjudicate Rule A vs Rule B** if you can find the operative document.
2. **Attack §2e.** Is inventory P&L really positive, or is the two-sided fill
   model too generous? Specifically: is it legitimate to assume both legs fill
   at *our* quoted prices when we re-peg every second?
3. **Is there a readout we have missed?** The whole difficulty is that the
   $1.00 floor censors the result to a single bit arriving 24–48 h later.
4. **Is the programme alive?** Independent confirmation either way.
5. Anything in §3 that suggests a class of error still uncaught.

---

*Total spent to date: ~$0.04. No strategy has been deployed. The kill criterion
on record is "positive expectancy at a fillable size, out of sample, with a
drawdown the operator can sit through" — deliberately not a t-statistic and not
a dollar target.*
