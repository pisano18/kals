# ATTACK: THE LIVE TEST DESIGN

**Adversary pass, 2026-09-06 ~20:00-20:30 UTC. NO ORDERS PLACED, AMENDED OR
CANCELLED. Zero write calls.** Authenticated read-only GETs, first-party help
pages fetched as raw HTML by me, the local tape, and one independent live 1 Hz
orderbook poll of my own.

Target: `results/overnight/LIVE_TEST_DESIGN.md`.

---

## VERDICT IN ONE PARAGRAPH

**The instrument is right and the read-out is broken.** The $1.00 per-programme
floor is real (I re-fetched the page and quote it below), the 1-contract quote
really does die 4,067 times out of 4,067, the modelled 11.8% share survives an
independent live check at **11.74%**, and the collateral numbers reproduce to
the cent. But the design's primary read channel — poll `paid_out` on the eight
programme UUIDs — **cannot work**: `/incentive_programs` returns byte-identical
rows to an *anonymous* caller, and 31,593 past programmes already read
`paid_out: true` on an account that has never rested an order. Every decision
rule phrased as "N of 8 pay" is unreadable. Separately, `P(false negative) =
8.5e-9` is an artefact of assuming eight consecutive 15-minute windows are
independent; the honest bound from 744 *real* consecutive blocks is **< 0.40%**,
a 470,000x overstatement. And the whole $150 exercise is aimed at a scenario
that a **free** historical measurement already makes implausible: I measured the
competitor-reaction function the critic names, over 15,686 real arrivals with a
placebo control, and it is **1.98% of share over five minutes**, not a 4x
collapse.

**RECOMMENDATION: do not fund $150. Do Step 0 for $0.00 and Step 1 for $8.30.**
The $1.00 floor governs *payment*, not *measurement*; the design conflated them
and sized the test 16x too large as a result.

---

## PART 1 — WHAT SURVIVES (ranked by reliability)

These I attacked and could not break. Ranked most to least reliable.

### 1. The $1.00 minimum payout per programme. **CONFIRMED, verbatim, independently.**

I re-fetched `help.kalshi.com/en/articles/16076644-...` myself as raw HTML and
stripped it. The sentence is there:

> "For liquidity programs, rewards are rounded down to the nearest cent, and **a
> final reward below $1 for an individual program is not paid.**"

and on the same page, what a programme is:

> "Each program has its own market, start and end time, and reward pool"

and on `.../13823851-liquidity-incentive-program`, under Rewards Structure:

> "Daily rewards: $1-$1,000 per market, per day
> **Minimum payout: $1.00 (rounded down to nearest cent)**"

A Coin Race market exists for exactly fifteen minutes, so one market = one
window = one $20 programme, and $20 sits inside the "$1-$1,000 per market, per
day" band. The design's reading is right.

**I go further than the design here.** It lists "whether the $1.00 floor is per
market-window or per event" as unresolved, and prices Stage 2 partly to settle
it — "That is worth $46.50 on its own." It is not. The event-grouping sentence
the design worries about is explicitly about the *discovery page display*:

> "The table groups programs by event. If one event has several incentivized
> markets, the Total rewards amount may combine the pools for those markets.
> **Open the exact market and check its Rewards popover to see that market's
> individual program and pool.**"

That is display grouping, immediately disclaimed. **Do not spend $46.50 to
re-learn it.**

### 2. The 1-contract quote is dead. **REPRODUCED EXACTLY.**

I re-derived the whole sweep from their own `allwin2.pkl` (4,067 market-windows)
with my own floor code:

| S | mean $/programme | %>=$1.00 | $ paid | deleted by floor |
|---|---|---|---|---|
| 1 | 0.0373 | **0.0%** | 0.0000 | 100.0% |
| 5 | 0.1842 | 0.0% | 0.0000 | 100.0% |
| 10 | 0.3625 | 0.0% | 0.0000 | 100.0% |
| 25 | 0.8633 | 39.6% | 0.5014 | 41.9% |
| 50 | 1.6018 | 76.6% | 1.4546 | 9.2% |
| 100 | 2.8000 | 91.1% | 2.7435 | 2.0% |

Their published table matches mine to the fourth decimal. Per-coin at S=50 also
matches (HYPE 90.2% >= $1, mean paid $1.807, sd $0.770). **Their arithmetic is
honest.** The brief was right to ask and the answer is no.

### 3. The modelled share at S=50. **CONFIRMED BY MY OWN LIVE POLL.**

I did not trust their replay, so I ran my own: a 1 Hz authenticated poll of every
open Coin Race market for two consecutive windows (2,819 book snapshots,
20:02-20:17 UTC), scored with a scorer I wrote from the verbatim rule text, on
the `linear_cent` grid, with our own 50 contracts added to both the score
denominator *and* the Target-Size depth test.

```
  MEAN over 10 live market-windows: qualification 100.0%
      share 11.74%   reward $2.348/window   (10/10 clear $1.00)
```

Their replay says 11.29% (q=inc/seen) or 11.80% (q=inc/900). **My independent
live number is 11.74%.** This is the single most load-bearing number in the
project and it survives a clean-room check.

### 4. Collateral and worst case. **REPRODUCED TO THE CENT, LIVE.**

From the same live poll, computed independently:

```
  ref_yes+ref_no   median $0.830   p99 $0.910   max $0.940
       -> S=50 collateral   $41.50 median, $45.50 p99
  max(ref_yes,ref_no) median $0.780  max $0.930
       -> S=50 worst case per window   $46.50
```

The design states $41.50 median and $46.50 worst case. Identical. The claim that
a resting sell of yes at q is a resting buy of no at (1-q) and that the exchange
holds the full premium is consistent with everything I can see.

### 5. Fully cash-collateralised; max loss = funded balance. **CONSISTENT WITH THE LEDGER.**

All four historical settlements lose at most the premium paid; nothing in the
ledger shows an obligation exceeding pre-posted collateral. The claim that
funding $150 caps the loss at $150 is sound. I could not falsify it.

### 6. No incentive-earnings endpoint. **REPRODUCED — I looked myself.**

I probed 22 candidates of my own choosing, including ones not on their list:

```
404  /incentive_programs/estimates      404  /portfolio/incentive_earnings
404  /incentive_programs/earnings       404  /portfolio/liquidity_earnings
404  /portfolio/reward_estimates        404  /portfolio/incentives/estimate
404  /portfolio/credits                 404  /portfolio/activity
404  /portfolio/rewards/current_month   404  /rewards/lifetime
404  /portfolio/summary                 404  /portfolio/reward_summary
```

Their claim stands: **the public Trade API exposes programme definitions and
nothing else.** Kalshi says so itself ("Incentive program definitions ... are
available through the public Trade API").

### 7. Eligibility is not API-readable. **REPRODUCED.**

`/users/self`, `/user`, `/account`, `/account/profile`, `/account/status`,
`/users/{my-uuid}`, `/account/kyc`, `/account/tax` — all 404. `/account/limits`
returns only `{"grants": [], "usage_tier": "basic", ...}`. Confirmed: nothing
exposes LIP eligibility. (But see Part 3 — it is answerable for **$0.00** and the
design says it is not.)

### 8. Coin Race is on shard 2 and shard 2 is empty. **CONFIRMED TWICE.**

`GET /series/KXCRYPTOLEAD15M` -> `exchange_index: 2`. `GET /exchange/status` ->
index 2 is `"Crypto"`. `GET /portfolio/balance` ->
`[{0: "0.0047"}, {1: "0.0000"}, {2: "0.0000"}, {3: "0.0000"}]`. Every order on
an unfunded shard 2 would be rejected. Real, and correctly flagged.

### 9. Capital does recycle inside 15 minutes. **CONFIRMED — with a correction (see Part 2.9).**

A settled Coin Race market shows `close_time 19:45:00Z`,
`settlement_ts 19:50:45Z`, `settlement_timer_seconds: 1`. Positions clear
**5m45s after close**, so collateral is genuinely reusable window to window.

### 10. The fee formula. **HOLDS ON 4 OF 4 FILLS — the entire population.**

The brief asserts `0.07*p*(1-p)`. I checked every fill, not a sample, with
exact decimal arithmetic. The rounding rule is **ceil to 1e-4 dollars** (not to
the cent — these are fractional contracts):

```
KXBTC15M-26AUG222115-15  n=12.37 y=0.16  0.07*0.16*0.84*12.37 = 0.11637696 -> 0.1164  actual 0.116400  OK
KXBTC15M-26AUG150130-30  n=38.97 y=0.47  0.07*0.47*0.53*38.97 = 0.67951989 -> 0.6796  actual 0.679600  OK
KXBTCD-26AUG1501-T63099  n=54.99 y=0.33  0.07*0.33*0.67*54.99 = 0.85108023 -> 0.8511  actual 0.851100  OK
KXBTC15M-26AUG150045-45  n=19.32 y=0.49  0.07*0.49*0.51*19.32 = 0.33796476 -> 0.3380  actual 0.338000  OK
```

**4/4 exact.** Note the population is four, all taker, all buy, all shard 0, all
`KXBTC*`. It says nothing about `KXCRYPTOLEAD15M` and nothing about makers.

---

## PART 2 — WHAT DIES. VERBATIM DISAGREEMENTS.

### 2.1 THE READ-OUT IS BROKEN. This is the one that matters.

The design writes:

> "**`paid_out` on the exact programme id — free, authenticated, and it is a
> clean trigger.** ... Record the eight programme UUIDs at placement time, poll
> `GET /incentive_programs` until all eight flip."

and builds every decision rule on it:

> "* **0 of 8 pay.** ... **The strategy is dead. Do not fund it.**"
> "* **Total in [$10.22, $18.76] with ~7 of 8 paying.**"

**`paid_out` is a global attribute of the programme, not of your account.** Two
independent proofs, both run this session:

1. I fetched the same 1,000-programme page **authenticated** and **anonymously**
   and diffed it field by field:

```
auth 200 1000   unauth 200 1000
common ids 1000
rows differing between AUTHENTICATED and ANONYMOUS: 0
paid_out differing: 0
```

   An anonymous caller sees the identical `paid_out`. It cannot be per-account.

2. Their own data proves it. Paging 40,000 programme rows, **31,593 past
   programmes read `paid_out: true`** — on an account whose every historical
   fill is `is_taker: true` and which, as the design itself states, "has never
   rested an order". If `paid_out` were per-account it would be false everywhere.

**Consequence.** `paid_out` flips when Kalshi processes the programme and pays
*whoever* earned it. It will flip for all eight of our windows whether we earn
$14 or $0. The design's stated 42-48h `paid_out` lag table is a measurement of
**Kalshi's settlement pipeline**, not of our earnings. Every "N of 8" rule is
unreadable, and the headline "settles it in 8 windows at P(false
negative)=8.5e-9" is not deliverable through the channel the design names.

What survives: read-out channel 2 (balance residual on shard 2) gives the
**total** and nothing else, and channel 3 is a guess. Per-window observability
exists only in the app (Account -> Activity -> Credits, which per the help page
"identify the event, payment date, amount"). **The design must be rewritten to
read dollars from the balance and the app, and every rule stated as a count of
paying programmes must be restated in dollars.**

### 2.2 `P(false negative) = 8.5e-9` is fiction.

The design writes:

> "| **8 (2 hours)** | **8.5 × 10⁻⁹** |"
> "**Four programmes settle 12.55%-vs-3%. Eight settle it beyond argument.**"

8.5e-9 is exactly `(1 - 0.902)^8`, i.e. eight independent coin flips. Eight
*consecutive* 15-minute windows on the *same* market are not independent: same
competitors, same hour, same book regime. I measured it — lag-1 autocorrelation
of consecutive-window paid dollars on HYPE is **0.094**, and the variance of the
8-window total is inflated **1.48x** over iid.

The honest calculation uses real consecutive blocks. I built all 744 of them
(nine contiguous HYPE runs, 807 windows):

```
blocks with ZERO payers: 0 / 744
```

Zero observed. By the rule of three, the 95% upper bound on P(0 of 8 pay | model
true) is `3/744 = 0.0040`. **The defensible number is "< 0.40%". The design
asserts 8.5e-9 — an overstatement of confidence of 470,166x.**

The *conclusion* survives (at a share of 3% the test does discriminate: I
simulated it, `P(0 of 8 pay) = 1.0000` at f=0.25). The *number* is invented.

### 2.3 The 95% band and the "$10.22" decision rule are wrong, and the error kills good strategies.

The design writes:

> "| **8** | **2** | **$14.49** | **[$10.22, $18.76]** | **58%** |"
> "* **Total < $10.22.** Realised share is significantly below modelled.
>   Re-price everything at the observed share before committing capital."

That band is `mean +/- 1.96 * sd/sqrt(8)` under independence. Against the 744
real blocks:

| | design | empirical (real blocks) | + q correction (2.4) |
|---|---|---|---|
| expected 8-window total | $14.49 | $14.54 | **$13.79** |
| 95% band | [$10.22, $18.76] | [$8.61, $18.84] | **[$7.77, $18.04]** |
| **P(total < $10.22) when the model is EXACTLY TRUE** | implied 2.5% | 6.18% | **9.01%** |

**The design's own kill rule fires on a correct model 9% of the time.** That is
the expensive error: it is the rule that would abandon a working strategy.

### 2.4 The expected payout is overstated 4.6% by dividing by the wrong denominator.

The rule is explicit: reward is scaled by "(non-excluded snapshots ÷ **total**
snapshots)", and a 15-minute programme has 900 one-second snapshots. Their
replay divides by `seen` — the number of seconds it could reconstruct:

```
snapshots reconstructed per 900-second window: mean 860.5  median 861  min 818
q as the replay computes it (inc/seen): 0.6904
q as the RULE defines it   (inc/900):   0.6598
=> rewards overstated by x1.0463  (4.6%)
```

The ~40 missing seconds sit at the window open, before the first book state
arrives — precisely the seconds least likely to qualify. Treating them as
non-existent rather than as excluded inflates every reward. Corrected:

* HYPE S=50 mean reward **$1.877 -> $1.796**
* % clearing $1.00 **90.2% -> 88.9%**
* **expected 8-window total $14.49 -> $13.79**

### 2.5 "makers genuinely pay nothing" is not evidenced. The cited evidence is vacuous.

The brief and the design both lean on:

> "`maker_fees_dollars: "0.000000"` on this account's own orders"

All four orders are `type: "market"` and 100% taker-filled
(`taker_fill_cost_dollars` positive, `maker_fill_cost_dollars: "0.000000"` on
every one). **A maker fee field on an order with no maker fill is necessarily
zero and carries no information.** The account has never placed a *limit* order,
let alone had one fill as maker. `GET /series/KXCRYPTOLEAD15M` carries only
`fee_type: "quadratic"`, `fee_multiplier: 1` and **no maker-fee field at all**,
which is suggestive but is not the same as a measurement. The honest status:
*plausible, unverified, and unverifiable from this account until it rests an
order.* Do not present it as confirmed.

### 2.6 "orders []" is false, and the P&L does not reconcile.

The design opens: "Account state confirmed at the top of this run:
`balance_dollars 0.0047`, `positions []`, `orders []`". `GET /portfolio/orders`
returns **four orders**. (Resting orders are empty; the statement as written is
not.)

More seriously, the brief says the fee formula was confirmed "**FROM THE
ACCOUNT'S OWN LEDGER**". The formula is confirmed. The *ledger* is not — I tried
to close it and could not:

```
premium paid    56.320200
fees             1.985100
settle revenue  19.320000
NET P&L        -38.985300
deposits gross 39.60   deposit fees 0.58   net-of-fee 39.02
MODEL A (credited = gross):     39.60 - 38.9853 = 0.6147  vs balance 0.0047  residual $0.6100
MODEL B (credited = gross-fee): 39.02 - 38.9853 = 0.0347  vs balance 0.0047  residual $0.0300
```

Neither model closes. The best is off by **exactly 3.00 cents**; the other by
61 cents. This matters because **read-out channel 2 is the balance residual** —
the design proposes to infer the reward as "the residual" from the balance
equation. On a $39 account that equation already carries an unexplained $0.03.
Against an expected $13.79 that is 0.2% and the method survives on magnitude,
but it should be stated as "reconciles to within $0.03", not "confirmed".

### 2.7 One of the four operator prerequisites is readable from the API.

The design writes:

> "(2) Confirm Collateral Return (`netting_enabled`) is OFF; it locks per event
> on the first order and cannot be undone"

listed under "**needs_operator**" as something only the operator can check in the
app. It is an authenticated GET:

```
200  /portfolio/subaccounts/netting
     {"netting_configs": [{"enabled": false, "exchange_index": 0, "subaccount_number": 0}]}
```

Netting is **off** on shard 0; shard 2 has no config row (i.e. default). The
design probed `/portfolio/subaccount_netting` (singular) and got a 404 and
concluded it was app-only. The path is `/portfolio/subaccounts/netting`.

### 2.8 The crossing guard is understated 2x, and the replay produces impossible books.

The design writes:

> "| `ref_yes + ref_no ≥ 0.99` | our own two orders would cross each other —
> measured on **0.065%** of market-seconds |"

Their own saved array (`refs.pkl`, 48,866 qualifying seconds) says:

```
seconds with refsum >= 0.99 : 0.129%      (design says 0.065%)
seconds with refsum >  1.00 : 0.121%   (59 seconds)
max refsum 1.49
```

A book with `ref_yes + ref_no > 1.00` is crossed, and reference prices sit
*below* the best bids, so it is doubly impossible. 59 seconds of the replay are
physically unrealisable and were not flagged. It is a small artefact, but it is
in the array used to price the collateral, and the guard threshold derived from
it is stated at half its measured rate.

### 2.9 "does not scale with the number of windows" — the windows overlap.

The design writes:

> "This is *concurrent* capital. It is released at every window close and
> re-used, so it does **not** scale with the number of windows."

The next window **opens at the moment the previous one closes** (open 19:30,
close 19:45; the next opens 19:45), but the previous market settles at
`19:50:45` — `settlement_ts` minus `close_time` = **5m45s**. Resting-order
collateral is released at close, but *filled* positions are not, so for **38% of
every 15-minute cycle** you carry the previous window's filled inventory *and*
the new window's full quote. Measured fills are small (mean 18 contracts per
market-window across both sides), so realistically ~$14 of overlap and harmless
at $150 funded. But at Stage 2's $207.50 concurrent the overlap is real money and
it is unpriced.

### 2.10 The MDE is 51%, not 42% — though censoring rescues the test.

Their MDE uses `2.80 * sd/sqrt(8) = 2.80 * 2.178 = $6.10` on $14.46, i.e. 42%.
With the empirical block SE of 2.650 it is `2.80 * 2.650 = $7.42`, i.e. **51%**.

In the design's favour, I then computed the power curve *properly*, scaling each
window's raw reward by a shortfall factor f, applying the floor, and summing over
real consecutive blocks. Censoring amplifies the signal and the test is **more**
powerful than the linear MDE implies:

| shortfall f | mean 8-window total | power at a true-5% threshold |
|---|---|---|
| 1.00 | $14.54 | 0.050 (false alarm) |
| 0.80 | $11.10 | 0.237 |
| 0.70 | $9.15 | 0.617 |
| 0.58 | ~$6.6 | **0.929** |
| 0.50 | $4.64 | 1.000 |

So "detects a 42% shortfall at 80% power" is *conservative* — real power there is
0.93. **But the number was computed the wrong way and happens to land safe.**
And the blind spot is unchanged and is the one that matters: at f=0.80 (a 20%
model error) power is **0.237**. To reach 80% power against a 20% shortfall takes
**32-48 windows, 8-12 hours**, not 8.

---

## PART 3 — IS A LIVE TEST EVEN THE RIGHT NEXT STEP?

Two findings say the design is aimed at the wrong target and priced 16x too high.

### 3.1 The competitor-reaction function IS estimable from history. I estimated it.

The critic's demand, verbatim:

> "The instant size is posted at the front, competitors improve or hit. No amount
> of historical reconstruction closes it."

The *fills* half ("or hit") is not reconstructable — agreed. But the *reaction*
half ("competitors improve") is, and nobody tried. Rivals' reactions to *other
people's* size are all over the tape.

I replayed 457,264 Coin Race deltas across ten hours, rebuilt both books at
every event, and found every arrival of **>= 50 contracts at or above the live
Reference Price** on a side that was already qualifying. For each, I tracked the
side's total qualifying score forward, and I ran a **placebo control** of random
seconds in the same markets to net out ordinary book churn.

```
                        median share the arriver keeps
lag       arrivals (n=15,686)     placebo (n=6,879)     EXCESS DILUTION
 60 s            0.9816                0.9888               0.73%
300 s            0.9487                0.9679               1.98%
```

**A 50-contract order posted at the Reference Price loses about 2% of its share
to competitor response over five minutes.** Not 75%. This is n=15,686,
placebo-controlled, and it cost nothing.

It does not *close* the critic's demand — these are reactions to incumbents'
size, possibly the same maker replenishing a ladder, and a genuinely new
entrant might draw a different response; and it cannot see a rival who
re-sizes tomorrow. But it makes the 12.55%-to-3% collapse that Stage 1 exists to
rule out **quantitatively implausible**, and Stage 1 is blind (power 0.237) to
the 20% shortfall that remains live.

### 3.2 The $1.00 floor governs PAYMENT, not MEASUREMENT. The design conflated them.

This is the design's central error of sizing. It reasons: a payout below $1.00
is not paid, therefore a test below S=50 "is not a small measurement — it is no
measurement". That is true only if the *sole* observable is the credit.

It is not. From the page the design itself quotes, but from a paragraph it did
not use:

> "For eligible signed-in users: **a liquidity earnings estimate and its 'as of'
> time**, when a positive estimate is available"

and:

> "When you have a resting order in a market with an active liquidity program, a
> dot can appear next to your resting quantity: **Blue dot**: the current price
> level appears to qualify on that side of the live book. Hover to see an
> **estimated efficiency percentage**..."

Kalshi computes your realised liquidity score **live, from its own recorded
snapshots, including every competitor reaction and your actual queue position**,
and shows it to you. That is exactly the quantity the critic says only filled
orders can produce — and it is **not censored by the $1.00 floor**, which
applies to the final credit.

Priced against the same replay:

| S | collateral (med) | **absolute worst case** | modelled share | estimate $/window | separation from a 4x-degraded share |
|---|---|---|---|---|---|
| 5 | $4.15 | $4.90 | 1.30% | $0.184 | 14 cents |
| **10** | **$8.30** | **$9.80** | **2.56%** | **$0.362** | **27 cents** |
| 25 | $20.75 | $24.50 | 6.09% | $0.863 | 65 cents |
| 50 | $41.50 | $49.00 | 11.29% | $1.602 | 120 cents |

**S=10 two-sided on one market costs $8.30 of collateral, has an absolute worst
case of $9.80, and separates the model from a 4x-degraded share by 27 cents of
displayed estimate.** That is the same hypothesis the design proposes to test
with $150 of funding and $46.50 per window.

I also checked whether the test could be made cheaper still by quoting only the
cheap side. **It cannot, and I am refuting my own idea:** the cheap side is cheap
precisely because it is the penny-stacked side where the qualifying score is
~5,000 and our share collapses to ~3%. Time-averaged over my live poll the
expensive side carries **75-86%** of the score on four of five coins. One-sided
quoting on the expensive side saves ~8% of capital for ~20% of the score. **The
design's two-sided quote is correct.** Only the *size* is wrong.

### 3.3 Eligibility — the design's #1 "cannot settle" — costs $0.00, not $150.

The design writes:

> "**No API endpoint exposes eligibility** ... If the account is ineligible, the
> test pays $0 and looks exactly like a failed strategy. **Check this in the app
> before funding.**"

Right that the API cannot answer it. But it lists this under prerequisites to
*funding $150*. The Rewards page (Menu -> Rewards, `kalshi.com/incentives`) is
described as showing "Current month and Lifetime rewards **for signed-in
users**", and the market popover shows the estimate "**for eligible signed-in
users**". **Opening the app and looking costs nothing, requires no funding, no
transfer and no order, and it is strictly the first thing to do.**

---

## PART 4 — WHAT I RECOMMEND INSTEAD

**Do not run HYPE-50-8 as specified.** Not because the instrument is wrong — it
is well built — but because its read-out does not work, its stop rule fires on a
correct model 9% of the time, and it is 16x larger than the question needs.

**STEP 0 — $0.00, no funding, no transfer, no order.**
Open the app. (a) Rewards page: does it render for this account, and does it show
Current month / Lifetime? (b) Open any live Coin Race market and hover the
Rewards badge: does the popover show Target Size, Discount Factor, and — the
tell — an *earnings estimate* line for eligible users? This settles eligibility,
which every downstream dollar depends on. It is free. Do it first.

**STEP 1 — $8.30 of collateral, $9.80 absolute worst case.**
Transfer ~$25 to shard 2 (ACH, not debit — this account's own deposits were
charged 1.96%). Post **10 contracts on each side of one Coin Race market, at the
Reference Price, post_only, expiring at window close**. One window. This single
action verifies, for under ten dollars, four things the design spends $150 on:

1. the collateral hold on this account's own ledger — never once observed,
   because all four historical orders are market orders that filled instantly;
2. whether the blue dot and the efficiency percentage appear (read-out exists);
3. whether a positive earnings estimate is shown (eligibility, confirmed a
   second way);
4. a first read of realised score share, uncensored by the $1.00 floor.

If the estimate is absent or unreadable, you have learned that for $9.80 instead
of $150, and *then* the payment-based test is the only route and the design's
S=50 sizing becomes correct.

**STEP 2 — only if the estimate is readable and tracks the model.**
Scale to S=50 for the *payment* confirmation, but restate every decision rule in
dollars read from the shard-2 balance and the app's Credits view — **never from
`paid_out`** — and use the corrected thresholds: expected **$13.79**, empirical
95% band **[$7.77, $18.04]**, and a kill threshold **below $7.77**, not $10.22.

**Do not** run the design's Stage 0 as written. A 1-contract order at $0.01 nine
ticks below the touch is guaranteed a **gray** dot and no earnings estimate; it
verifies the collateral cent and nothing else, and it forgoes the read-out and
eligibility checks that are the actual unknowns.

---

## PART 5 — WHAT I COULD NOT DO

* **Could not read `kalshi.com/regulatory/notices`** — the governing terms the
  help centre defers to. First fetch returned HTTP 429; the retry returned a
  client-rendered shell with 421 characters of text and no notices. The design
  could not read the CFTC PDF either. **Neither of us has read the governing
  document. Everything about the $1.00 floor and eligibility rests on the help
  centre, which is first-party but explicitly subordinate to the notices page.**
* **Could not verify the maker fee** on `KXCRYPTOLEAD15M`. No maker fill exists
  on this account, the series object has no maker-fee field, and I could not
  locate the fee-schedule help article (the ID I tried served the Bug Bounty
  page). Unverified, in both directions.
* **Could not confirm the earnings estimate exists.** My Step 1 recommendation
  turns on a paragraph of Kalshi help text describing a UI element. I have not
  seen it, it "may be unavailable in some layouts", and it needs a resting order
  to appear. That is the risk Step 1 is priced to absorb.
* **Could not close the $0.03 ledger residual.**
* **Could not test whether reaction to a *new entrant* differs from reaction to
  an incumbent's replenishment.** Unfalsifiable from history; it is the one part
  of the critic's demand that genuinely needs live posting.

---

## PROVENANCE

* **[API]** `kauth.py` GETs only, zero writes: `/incentive_programs` (40,000 rows
  authenticated and 1,000 anonymous for the diff), `/markets`,
  `/markets/{t}/orderbook`, `/series/KXCRYPTOLEAD15M`, `/exchange/status`,
  `/exchange/schedule`, `/account/limits`,
  `/portfolio/{balance,orders,fills,settlements,positions,deposits,withdrawals,
  subaccounts/netting,target_balance_allocation}`, plus 22 probe paths.
* **[LIVE]** My own 1 Hz poll, 2,819 book snapshots, 5 markets, two consecutive
  windows, 20:02-20:17 UTC 2026-09-06, scored by my own implementation of the
  verbatim rule. `atkLT/livepoll2.py`, `atkLT/scorelive.py`.
* **[TAPE]** `C:\kals\kalshi_data\orderbook_delta`, read-only, 457,264 Coin Race
  deltas over ten hours of 2026-09-06 for the reaction study.
* **[REPLAY]** Their `allwin2.pkl` (4,067 market-windows) and `refs.pkl`
  (48,866 seconds), re-derived with my own floor, block and power code.
* **[DOC]** `help.kalshi.com/en/articles/16076644-...` and `...13823851-...`,
  raw HTML fetched by me this session and stripped, not summarised.
* Scripts: `C:\Users\Joe\AppData\Local\Temp\kals-work\atkLT\` —
  `p1.py p2.py p3.py` (paid_out), `led.py recon.py` (forensics),
  `rederive.py power.py power2.py final.py` (replay + power),
  `react.py react2.py` (reaction), `livepoll2.py scorelive.py minimal.py`
  (live), `probe.py elig.py settle.py qual.py`.
* **Collector health after all jobs: `kalshi_collector.py` PID 3381772 ALIVE,
  `crypto_feeds.py` PID 3385232 ALIVE. Free disk C: 50.7 GB.**
