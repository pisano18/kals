# THE GOLD CUTOFF TEST — everything, for independent review
**2026-09-07 07:00Z. The code is written and dry-run clean. NO LIVE ORDER FOR
THIS TEST HAS BEEN PLACED.** Total money this project has ever risked: about
$1.60, in deliberate probes. Current account: **$65.19**.

This document is self-contained. It includes the plan, the pre-registered
prediction, the full source of the script that will run, every measurement it
rests on, every retraction, and the specific questions a reviewer can help
with. **Assume nothing here is true because it is written confidently — nine
things in this project have already been retracted, and they are all listed.**

---

# PART 1 — THE QUESTION, AND WHY IT IS WORTH REAL MONEY

## 1.1 What the programme pays

Kalshi's Liquidity Incentive Program pays for **resting** orders, filled or
not. Verbatim from the help centre:

- Snapshots once per second, at a random moment within the second.
- **Target Size** = *"the depth that must be resting on each side for a
  snapshot to count"* — aggregate book depth, not ours. For our markets: 300.
- **Reference Price** = *"Walking down from the best bid, the first price level
  at which cumulative resting size reaches one fifth of the Target Size... it
  is not always the best bid or ask — a small order alone at the top of the
  book does not set it."*
- Orders at or better than the Reference Price get multiplier **1.0**; below
  it, `discount_factor ^ (ticks below)`. `discount_factor_bps 5000` → **0.50**.
- *"Kalshi scores every resting order **that helps reach the Target Size** on
  its side."*
- *"Your snapshot score is your share of the yes side plus your share of the no
  side, so a single snapshot is worth at most 2.0 across all participants."*
- *"Your Time Period score = your total snapshot scores ÷ all participants'
  total snapshot scores."*
- `reward = TimePeriodScore × PeriodReward × (non-excluded ÷ total snapshots)`,
  **rounded down to the cent**.
- Excluded if the market is closed **or** either side fails Target Size.
- **Minimum payout $1.00.**

Algebraically the "plus" does not double anything:
`reward = R × mean over ALL snapshots of (share_yes + share_no)/2`. The
qualification haircut is applied **exactly once**, by that averaging.

## 1.2 THE FORK — and it is not the A/B question two reviewers answered

Two outside AIs were asked to adjudicate "Rule A (help centre) vs Rule B (CFTC
filing)" and both said Rule A. **I think both missed that the help text
contains two different steps, not two competing rules:**

| step | text | effect |
|---|---|---|
| set the reference | *"first price level at which cumulative resting size reaches **one fifth** of the Target Size"* | reference sits where cum ≥ 60 |
| decide what is scored | *"every resting order **that helps reach the Target Size**"* | only size inside the walk to cum = 300 counts at all |

One reviewer quoted filing text saying the walk *"continues until the full
Target Size is reached, at which point the procedure stops"* and then concluded
"there is no hard cutoff." **That sentence contradicts that conclusion.**

### The cutoff is not a detail. Measured on 127,000 book-seconds:

| family | denominator, no cutoff | denominator, cutoff | our share @20, no cutoff | with cutoff | ratio |
|---|---|---|---|---|---|
| KXGOLD15M | 1,856 | **300** | 1.97% | **7.12%** | **3.61×** |
| KXCOPPER15M | 604 | 219 | 4.62% | 9.28% | 2.01× |
| KXWTI15M | 571 | 245 | 4.62% | 8.45% | 1.83× |
| KXSILVER15M | 511 | 230 | 5.31% | 8.99% | 1.69× |
| KXNATGAS15M | 226 | 144 | 8.92% | 12.67% | 1.42× |

### Confirmed against a real book the operator photographed

Kalshi app, KXCOPPER15M, 2026-09-07 06:38Z:
```
Asks   96c x 990     97c x 2,264   98c x 1,901
Bids   98c x 498     97c x 2,049   90c x 29      <- second screenshot, later book
Bids   95c x 2       94c x 29      93c x 2,040   <- first screenshot
```
- In the **first** book the touch holds **2 contracts** — under 60 — so the
  reference is **93c, three ticks back**. Exactly as the help text warns.
- In the **second** the touch holds **498**, so the reference **is** the touch.
- On the second book: no cutoff → denominator ≈ 498 + 0.5×2,049 + … ≈ **1,523**;
  cutoff → **300**. Share at 20 contracts: **1.3% vs 6.25%, a 4.8× difference.**

**The whole question is one big level just behind the reference.** The deep
book (bids at 25c, 16c, 9c, 7c, also photographed) sits ~90 ticks down and
scores `0.5^90` ≈ 0 under either rule. It is irrelevant.

## 1.3 Why the $1.00 floor makes this a BINARY, and only in gold

| gold, S=20/side | share | reward/window | clears $1.00? |
|---|---|---|---|
| **no cutoff** | 1.97% | $0.39 | **NO → pays $0.00** |
| **cutoff** | 7.12% | $1.42 | **YES → pays $1.42** |

Eight windows therefore predict **$0.00** or **$8.50–$11.40**. No ambiguous
middle. Every other family pays under both readings, so their result would be
uninformative. **Gold is the only discriminating venue, and it is the family I
have been calling worthless all night.**

---

# PART 2 — THE PRE-REGISTERED PREDICTION (committed before any order)

Committed as `results/PREREG_gold.md`, git `74ad54c`, timestamped before the
script existed.

**Design:** `KXGOLD15M`, 8 consecutive 15-minute windows, 20 contracts each
side, quoted at the Reference Price, re-pegged, `post_only` throughout.

| quantity | if NO cutoff | if CUTOFF |
|---|---|---|
| rebate/window | $0.39 gross → **$0.00 paid** | $1.42 gross → **$1.42 paid** |
| windows clearing the floor | **0 of 8** | **6–8 of 8** |
| **total credit after 48 h** | **$0.00** | **$8.50 – $11.40** |

Inventory P&L is a separate noisy term and is **not** the measurement:
expected **+$0.44/window**, sd ~$3, worst gold window on tape **−$4.40**.
Over 8 windows: expect **+$3.50**, band **[−$12, +$12]**.

Also predicted, so a surprise is visible:
- `balance_dollars` will **not** move while orders rest (it is gross of
  reserves — there is no readable available-funds figure anywhere).
- Fills will show `is_taker: false`, `fee_cost: 0.000000`.
- **No credit before 48 hours.** A $0.00 reading earlier is meaningless.

## Decision rule, fixed in advance
- **≥ $6** → cutoff is real. Every share figure is understated 1.4–3.6×; gold
  is a good venue; re-run the family ranking before deploying further.
- **exactly $0.00** → no cutoff. Published tables stand, gold stays dead,
  natgas is the only viable family.
- **$0.01–$5.99** → neither model is right. STOP, re-fit, do not scale.
- **nothing after 72 h** → the readout has failed. That is a finding about the
  programme, not the rule. Stop spending on rebates.

**The confound I cannot remove:** if the account is ineligible, $0.00 is
indistinguishable from "no cutoff". Recorded in advance.

---

# PART 3 — WHAT IS ALREADY ESTABLISHED (challenge any of it)

## 3.1 Programme and payout mechanics
- `period_reward` is in 1e-4 dollars: `200000` = **$20.00** per market per
  15-min window. Proven arithmetically (909090 × 11 = 1428571 × 7 = $1,000.00).
- **The programme is alive.** 178,340 programmes paginated; latest paid
  `end_date` minutes old; **3,056 scheduled for future windows**. The
  "Feb 2026 filing expired 2026-09-01" theory is not supported.
- **Two incentive types:** `volume` (22,275 programmes, **100%** paid) and
  `liquidity` (156,097, 92.9%), of which `series_lip` — ours — is **77.6%**.
  The never-paid mass sits in thin families (weather `KXTEMP*` 3,094 unpaid
  past 200 h; table tennis 869). **Untested hypothesis: an unpaid pool may mean
  nobody qualified, not payment pending.**
- **Our five families pay 94.8–98.1%.** Readout is **>48 h**: nothing pays
  before it, 99–100% after.

| family | 0–2h | 2–6h | 6–12h | 24–48h | >48h | overall |
|---|---|---|---|---|---|---|
| Gold | 0% | 0% | 0% | — | **99%** | 98.1% (n=2,428) |
| Silver | 0% | 0% | 0% | — | 99% | 98.0% (n=2,428) |
| WTI | 0% | 0% | 0% | — | 99% | 98.0% (n=2,428) |
| NatGas | 0% | 0% | 0% | — | 100% | 94.8% (n=650) |
| Copper | 0% | 0% | 0% | — | 100% | 95.1% (n=650) |
| Coin Race | 0% | 0% | 0% | 96% | 99% | 91.1% (n=6,425) |

- **REFUTED BY OBSERVATION:** an agent inferred a daily payout batch at
  05:00–05:15Z from 178,245 records. A watcher held 14 programmes across that
  window for **93 minutes**: **0 of 14 flipped.** Watching beat inferring.
- **A LIP credit has no API line item.** `/incentives` 404s; 26 guessed paths
  404. It is readable only as a balance residual — which reconciles to
  **$0.0000** over the account's entire life, so a $1.00 credit is unambiguous.

## 3.2 The markets
All five: `exchange_index 0`, `fee_type quadratic` (**makers pay nothing**),
`target_size 300`, `$20`/15-min window, `discount_factor_bps 5000`.

- **Tick grid is not uniform**, and `price_level_structure` lives on the
  **market** record, not the series: gold/silver/WTI `tapered_deci_cent`,
  natgas/copper `linear_cent`. The market record also carries `price_ranges`
  with the exact step per band — use it rather than any hardcoded rule.
- **~89 windows/day on weekdays**, closes in 23 of 24 ET hours (one empty hour
  at 04:00 ET, unexplained). Confirmed running today (Labor Day) with no gap
  over an hour.
- **Qualification 93–99%.**

## 3.3 Book reconstruction (this destroyed two earlier findings)
| | carries level arrays | bare |
|---|---|---|
| **FIRST** snapshot of a market | **264** | 14 |
| **LATER** snapshots | **0** | 468 |

The first `orderbook_snapshot` carries the opening ladder in
`yes_dollars_fp`/`no_dollars_fp` (median **86,526 yes / 68,866 no**); later ones
are bare resync markers. **SET the book when a snapshot has levels, CLEAR it
when it does not.** Clearing on every snapshot destroys the ladder for the
market's life and yields a **26% qualification rate where ~97% is correct**.
Sizes are fractional; float residue leaves levels holding 3e-7 contracts that a
naive `>0` test treats as live top-of-book.

## 3.4 Net P&L per family, S=20, back of queue, $1.00 floor applied
n = 24 settled windows each, 125 markets, 6 h tape, correct per-family grid,
`taker_side` respected:

| family | gross rebate | paid | inventory P&L | **NET/window** | worst |
|---|---|---|---|---|---|
| KXNATGAS15M | 1.746 | 1.712 | +0.458 | **+2.170** | −7.50 |
| KXCOPPER15M | 0.996 | 0.480 | +1.343 | **+1.824** | −6.80 |
| KXSILVER15M | 1.125 | 0.770 | +0.644 | **+1.415** | −5.34 |
| KXGOLD15M | 0.453 | 0.000 | +0.436 | **+0.436** | −4.40 |
| KXWTI15M | 1.051 | 0.793 | −0.564 | **+0.229** | −8.45 |

**Inventory P&L is mostly POSITIVE.** When both legs fill you hold a YES and a
NO in the same market: exactly one pays $1.00, and the pair cost ~$0.97. That
3c is the maker's spread. An earlier agent's negative figure measured adverse
selection against our *quote* rather than against the $1.00 the pair is worth.

### Capital-constrained: the marginal dollar dies at $60
| family | $20 | **$60** | $150 | $500 |
|---|---|---|---|---|
| NatGas | +1.08 | **+2.17** | +2.17 | +2.17 |
| Copper | +1.86 | **+1.82** | +1.82 | +1.82 |
| Silver | +0.81 | **+1.42** | +1.42 | +1.42 |
| WTI | **−1.36** | +0.23 | +0.23 | +0.23 |
| Gold | **−1.44** | +0.44 | +0.44 | +0.44 |

Mean size actually resting: **6.2–12.1 at $20** vs **19.1–19.8 at $60**.
$150 and $500 are identical to $60. **This is why the operator deposited to $65
and why more would be dead capital for this test.**

**A number this project refuses to quote:** ×89 windows/day gives ~$193/day on
$60, a >300%/day return. It rests on 6 hours of **Sunday-evening** tape (the
weekend reopening) and assumes ~22 h/day of quoting with a re-peg every ~5 s ≈
**15,000 order operations/day** against unknown rate limits. **Per-window
figures are defensible; per-day figures are not.**

## 3.5 Order and account mechanics, all verified live
- **V2 API.** `POST /portfolio/orders` returns **410 deprecated_v1**. Correct:
  `POST /portfolio/events/orders`, body `{ticker, side ("bid"=buy YES /
  "ask"=sell YES), count (fp string), price (fp dollars string),
  time_in_force, self_trade_prevention_type, client_order_id, post_only,
  exchange_index}`.
- **Cancel:** `DELETE /portfolio/events/orders/{id}?exchange_index=N`. The query
  parameter is **required off shard 0** — without it the cancel returns 404 and
  **silently does not cancel**. Kalshi signs the path **without** the query.
- **A 400 "post only cross" STILL CREATES a cancelled order record.** Order
  audits must filter on status or they double-count.
- **Resting orders DO reserve cash, cumulatively.** Proven by a straddle on a
  shard holding $0.0286: $0.0150 accepted, $0.0250 refused
  `insufficient_balance`; arithmetic closes exactly.
- **`balance_dollars` is GROSS** — it never nets out reserves, in API or app.
  `/portfolio/summary/total_resting_order_value` 403s;
  `GET /portfolio/resting_order_value` is documented but **404s**. There is **no
  readable available-funds figure**; a client must track reserves itself.
- **NETTING IS OFF**, read directly from `GET /portfolio/subaccounts/netting`.
  Collateral Return applies to **filled** hedged positions, not resting orders,
  so it does **not** reduce quoting capital — and Kalshi's own text says it
  *"may make you unable to sell positions for which you've already had
  collateral returned."* The flag locks at the first order in an event and
  **can never be changed**. **Therefore there is NO fundable stop-loss at full
  deployment: size is the only control.**
- **Makers pay nothing — proven non-vacuously.** A resting 1c YES bid was hit:
  `is_taker: false`, `fee_cost: 0.000000`. (Every earlier fill was a taker,
  which made the zero trivially true; that inference was retracted once.)
- **Fractional contracts are supported** (a real 0.02-contract fill exists).
- **Fees round UP:** 0.07×0.56×0.44×0.02 = $0.000345 predicted, **$0.000400**
  charged. Second instance: exact 0.0147 → charged 0.0150.
- **Our resting size IS visible in the public depth feed** — 1.00 contract at an
  empty $0.02 level appeared as `1.00 @ $0.02` within 20 s. Every share figure
  assumes this; it had never been tested.
- **`/markets` quotes are stale** — an order priced off them was rejected
  "post only cross" three ticks below the quoted bid. Use the orderbook.
- Deposits: **bank transfer free**, card **1.96%**.
- **There is no margin, no borrowing and no leverage on Kalshi.** Maximum loss
  is capped at deposited cash.

## 3.6 Adverse selection, demonstrated live for one cent
A 1c YES bid was rested when the book was **18c/21c** — 17 cents below the
touch, apparently unfillable. Twelve minutes later the contract collapsed and
the book walked down through 6c, 4c, 2c and **hit the 1c bid on the way down**.
It settled worthless.

The fill did not arrive because someone blundered. It arrived because the
contract had become worth about a cent. Conditional on a fill the win
probability is ~1%, not the ~21% implied at placement:
`0.01 × $0.99 − 0.99 × $0.01 = $0.0000` — **exactly fair.**

A second resting fill (copper at 79c) settled **yes** for **+$0.21**. n=2, one
each way. **That is what a fair coin looks like. The rebate is the thesis; the
fill P&L is not.**

---

# PART 4 — THE SCRIPT THAT WILL RUN

`research/goldquote.py`, git `d6562cd`. Self-test passes; dry run clean.

## 4.1 Safety design
| rail | why |
|---|---|
| `post_only` always | rests or is rejected; can never cross, never take, never pay a taker fee |
| **cancel BEFORE place** on every re-peg | placing first briefly holds two orders on a side and doubles the reserve — the documented path to a naked position |
| **both legs or neither** | see the bug in §4.3 |
| cumulative collateral cap **$21.00** | on a binary the total deployed **is** the maximum loss |
| loss abort **−$15.00** | checked against the exchange's own numbers every 20 ticks |
| `PRICE_MIN/MAX 0.20–0.80` | never quote a decided market (see §4.3) |
| `MIN_WINDOW_SECONDS 780` | never join a window late (see §4.3) |
| cancel-all in `finally`, **verified** against the paged `?status=resting` list | a silently-failed cancel leaves live exposure nobody is watching |
| `--dry-run` | every read and every calculation, sends nothing |

## 4.2 What it does each tick (3 s cadence)
1. Read the live orderbook (not `/markets`).
2. Compute the Reference Price each side: walk down, first level where
   cumulative ≥ Target/5 = 60.
3. Skip if either side's depth < 300 (the snapshot would be excluded anyway).
4. Skip and stand down if `ref_yes` is outside 0.20–0.80.
5. Build **both** orders; validate **both** against the rails and the pair's
   collateral against the cumulative cap. If either fails → **cancel both**.
6. Re-peg only the side whose reference moved: cancel, verify, place.
7. Every 20 ticks: read balance + positions, abort if P&L ≤ −$15.
8. At window end: cancel both, verify, move to the next fresh window.

## 4.3 THREE BUGS FOUND BEFORE IT RAN — reviewers should hunt for a fourth

**(a) One-sided quoting, found by the dry run.** On a 95c market the YES leg
cost $19.04 and was refused by `MAX_NOTIONAL $15` — and the loop **placed the
NO leg anyway**, then sat quoting one side continuously. *A safety ceiling was
creating the naked directional exposure the design exists to prevent.* Fixed:
both legs are built and validated together; any failure stands down both.

**(b) Joining a window late, caught by the operator.** The bot took the first
open market, which could have 60 seconds left. Since
`reward = R × mean over ALL snapshots`, joining at minute 14 earns ~1/15 of the
window ≈ $0.09 → **under the floor → zero**, while carrying full fill risk.
Fixed: take the freshest window, refuse anything under 780 s.

**(c) Quoting a decided market, caught by reading the live book.** Gold was at
`ref_yes 0.988 / ref_no 0.011`. Twenty a side there costs **$19.76** on the YES
leg and **$0.22** on the NO leg: both filling locks a guaranteed $20.00 for
$19.98 — **two cents** — while a YES-only fill leaves **$19.76 at risk to earn
$0.24**, and a one-sided fill is exactly what arrives when the price is about
to move. Fixed by the price band.

## 4.4 Dry-run output, current code
```
=== window 1/1: KXGOLD15M-26SEP070300-00 closes 07:00:00Z (848s of quoting) ===
  [dry] yes 20 @ 0.5600 (ref 0.5600, collateral $11.20)
  [dry] no  20 @ 0.5700 (ref 0.4300, collateral $8.60)
  [dry] yes 20 @ 0.5700 (ref 0.5700, collateral $11.40)   <- re-pegged
```
Pair collateral **$19.80** against the $21 cap. `ref_yes + ref_no = 0.99`, so
the pair costs 99c for a guaranteed $1.00 — a locked 1c per pair before any
rebate.

---

# PART 5 — EVERY RETRACTION (nine so far)

1. **"6-hour commodity session, 24 windows/day"** — measured on a **Sunday**
   (CME weekend reopening). Weekdays run **89**. Every $/session figure was
   3.7× too low.
2. **"3.3× cheaper than Coin Race"** — that was the ratio of *target sizes*,
   not of *share obtained*. Measured ~1.8×.
3. **A single book poll is a selection artefact** — first poll of copper's no
   side scored 96 (→34% share); six polls give a median of 185, range 104–858.
4. **"Makers pay nothing" (first version)** — cited four orders that were all
   `is_taker: true`. Vacuous. Re-established properly later.
5. **"Nothing has ever been paid"** — read only page one of
   `/incentive_programs`, which is all future windows. 68,805 of 80,000 paid.
6. **Ranked families by `period_reward` without dividing by period length** —
   claimed one paid 7× crypto; per hour it pays a tenth.
7. **`price_level_structure` read from `/series`, where it does not exist** →
   grid came back `None` → cents applied to every family: *the exact bug the
   script was written to fix.*
8. **`taker_side` ignored** — on Kalshi's dual book a taker buying YES consumes
   a resting **NO** bid and vice versa, so at most one of two quotes can be hit
   by any trade. Counting both produced "40.0 fills" in nearly every window and
   a spurious +$1.48 inventory P&L.
9. **The UI qualification indicator does not exist.** A planning agent asserted
   Kalshi renders a per-order dot and efficiency percentage; it was relayed
   without verification. The operator photographed the order screen, position
   screen, market screen and full order book of a market **confirmed to have a
   live `series_lip` programme running at that moment** — no dot, no
   percentage anywhere.

Two near-misses worth recording as method:
- A detector reported "0.0% of snapshots carry levels" and a confident
  refutation of a correct report, because its key list omitted the `_fp`
  suffix. Only the key-set histogram printed beside it caught the error.
  **A detector that reports absence must print what it did see.**
- A probe named `bisect.py` shadowed the stdlib module and produced an import
  error that masked the real API response.

---

# PART 6 — WHAT I WANT FROM A REVIEWER

1. **The cutoff.** Not "A or B" — the specific question is whether scoring
   stops at cumulative = Target Size. If you can find the **operative** notice
   that replaced the Feb 2026 filing after 2026-09-01, that settles it without
   spending anything. Kalshi's regulatory notices page is the pointer; its
   embedded documents have defeated two web readers so far.
2. **Attack §3.4.** Is inventory P&L really positive? Specifically: is it
   legitimate to assume both legs fill at *our* re-pegged prices? A one-sided
   or staggered fill model may flip the sign.
3. **Find bug (d) in `goldquote.py`** (source below). Three were found before
   it ran; the base rate suggests a fourth.
4. **Is 8 windows enough?** The prediction is $0.00 vs $8.50–11.40. If the
   share estimate's error bars straddle the $1.00 floor, the test proves
   nothing and needs a different size or count. Say which.
5. **The readout.** A credit has no API line item and appears only as a balance
   residual, 48+ h later, and 22% of `series_lip` programmes never pay at all.
   Is there a cleaner readout we have missed?
6. **The unpaid-pool hypothesis.** Does `paid_out: false` mean "nobody
   qualified" rather than "payment pending"? If so, thin families are empty
   space rather than broken, and that reframes the whole opportunity.

**Please distinguish what you verified from what you are repeating.** This
project has nine retractions; the most useful thing you can do is create a
tenth.

---

# PART 7 — FULL SOURCE OF THE SCRIPT

Reproduced verbatim so it can be reviewed without repository access.

```python
#!/usr/bin/env python3
# VERSION: 2026-09-07-g1
"""goldquote.py -- the two-sided quoter for the gold cutoff test.

WHAT IT DOES
  Rests S contracts on each side of one KXGOLD15M market at the LIP Reference
  Price, re-pegs as that price moves, and stops after N windows. It exists to
  answer ONE pre-registered question (results/PREREG_gold.md): does Kalshi's
  scoring stop at the full Target Size? Gold is the only family where the two
  answers straddle the $1.00 minimum payout, so the result is a binary.

SAFETY, and why each rail is here
  post_only ALWAYS -- an order that rests or is rejected. It can never cross,
    never take liquidity, never pay a taker fee.
  CANCEL BEFORE PLACE on every re-peg. Placing first would briefly hold TWO
    orders on one side and double the reserve; with a small account that is the
    documented path to a naked position (HANDOFF, ruin analysis).
  A cumulative collateral cap, checked before every order. On a binary the
    total deployed IS the maximum loss.
  A loss abort, checked every loop against the exchange's own numbers.
  Cancel-everything in a finally block, VERIFIED against the paged
    ?status=resting listing -- a cancel that silently fails leaves live
    exposure nobody is watching (that bug was real and is fixed in ordercli).
  --dry-run does every read and every calculation and sends nothing.

USAGE
  python goldquote.py --selftest
  python goldquote.py --dry-run --windows 1
  python goldquote.py --live --windows 8
"""
import argparse
import datetime as dt
import json
import sys
import time

sys.path.insert(0, r"C:\kals-repo\research")
import ordercli as oc

KEY_ID = "b48b406b-b498-4d14-b640-be989913526f"
KEY_FILE = r"C:\kals\kalshi.pem"
SERIES = "KXGOLD15M"
TARGET = 300.0
DISC = 0.50
LOSS_ABORT = -15.00          # dollars of realised+unrealised loss
CADENCE = 3.0                # seconds between re-peg checks

# DO NOT QUOTE AN ALREADY-DECIDED MARKET.
# Observed live 2026-09-07 06:42Z: KXGOLD15M ref_yes 0.988 / ref_no 0.011.
# Quoting 20 a side there costs $19.76 on the YES leg and $0.22 on the NO leg.
# Both legs filling locks a guaranteed $20.00 for $19.98 -- two cents. But a
# YES-ONLY fill leaves $19.76 at risk to earn $0.24, and a one-sided fill is
# precisely what arrives when the price is about to move (adverse selection,
# demonstrated live twice tonight). The rebate is a few dollars; it cannot pay
# for that tail.
# So: only quote when the reference price is away from the extremes, which
# bounds the one-sided exposure at SIZE x PRICE_MAX.
PRICE_MIN, PRICE_MAX = 0.20, 0.80

# NEVER JOIN A WINDOW LATE. The operator caught this before it ran.
# reward = R x mean over ALL snapshots in the period of our share. Join a
# 900-second window with 60 seconds left and we are present for 1/15 of the
# snapshots, so a $1.42 window pays about $0.09 -- under the $1.00 floor, so
# ZERO. We would carry the full fill risk for no possible credit.
# Require most of the window to remain, otherwise wait for the next one.
MIN_WINDOW_SECONDS = 780      # of a 900 s window; refuse anything shorter


def ref_price(levels, target=TARGET):
    """Reference Price: walking DOWN from the best, the first level at which
    cumulative resting size reaches ONE FIFTH of Target Size."""
    lv = sorted(levels, reverse=True)
    if not lv:
        return None, 0.0
    depth = sum(s for _, s in lv)
    cum = 0.0
    for p, s in lv:
        cum += s
        if cum >= target / 5.0:
            return p, depth
    return lv[-1][0], depth


def book(api, tk):
    st, ob = api("GET", "/markets/" + tk + "/orderbook", query={"depth": "60"})
    o = (ob or {}).get("orderbook_fp") or {}
    y = [(round(float(p), 4), float(s))
         for p, s in (o.get("yes_dollars") or []) if float(s) > 0.005]
    n = [(round(float(p), 4), float(s))
         for p, s in (o.get("no_dollars") or []) if float(s) > 0.005]
    return y, n


def selftest():
    print("=" * 74)
    print("SELF-TEST -- the reference price and the rails")
    print("=" * 74)
    fails = []

    # reference price: a small order alone at the top must NOT set it
    lv = [(0.60, 5.0), (0.59, 10.0), (0.58, 100.0), (0.57, 500.0)]
    r, d = ref_price(lv)
    print(f"\n  book {lv}")
    print(f"    target/5 = {TARGET/5:.0f}; cumulative reaches it at {r}")
    # hand-check: cumulative 5, 15, 115 -> first level reaching 60 is 0.58
    print(f"    hand-check: cum 5, 15, 115 -> first >= 60 is at 0.58")
    if r != 0.58:
        fails.append(f"reference {r}, hand-check says 0.58")

    # REAL BOOK, photographed by the operator 2026-09-07 06:38Z on
    # KXCOPPER15M: touch holds 2 contracts, so the reference must NOT be the
    # touch. cum 2, 31, 2071 -> first >= 60 is 0.93.
    real = [(0.95, 2.0), (0.94, 29.0), (0.93, 2040.0)]
    rr, _ = ref_price(real)
    print(f"\n  real copper book {real}")
    print(f"    reference {rr} (expect 0.93 -- a 2-contract touch cannot set it)")
    if rr != 0.93:
        fails.append(f"reference {rr} on the real book, expected 0.93")

    lv2 = [(0.60, 500.0)]
    r2, _ = ref_price(lv2)
    print(f"\n  a single deep level at the touch: ref {r2} (expect 0.60)")
    if r2 != 0.60:
        fails.append("a level holding more than target/5 must set the ref")

    r3, d3 = ref_price([])
    print(f"  empty book: ref {r3}, depth {d3} (expect None, 0.0)")
    if r3 is not None:
        fails.append("empty book must give no reference")

    # the rails we depend on
    oc.set_env(True)
    print(f"\n  production ceilings: count {oc.MAX_COUNT}, per-order "
          f"${oc.MAX_NOTIONAL}, cumulative ${oc.MAX_DEPLOYED}")
    b = oc.build_order("KXTEST", "bid", 0.50, oc.MAX_COUNT, "t")
    if b.get("post_only") is not True:
        fails.append("post_only not forced")
    over = oc.build_order("KXTEST", "bid", 0.99, oc.MAX_COUNT, "t")
    if not oc.check_limits(over):
        fails.append("a full-size order at 0.99 was not refused by MAX_NOTIONAL")
    print(f"    full size at 0.99 (collateral ${oc.collateral(over):.2f}) -> "
          f"{'REFUSED' if oc.check_limits(over) else '*** ALLOWED ***'}")

    # an ask must reserve (1-p), not p
    a = oc.build_order("KXTEST", "ask", 0.20, 10, "t")
    if abs(oc.collateral(a) - 8.0) > 1e-9:
        fails.append(f"ask collateral {oc.collateral(a)}, expected 8.00")
    print(f"    ask 10 @ 0.20 reserves ${oc.collateral(a):.2f} (expect 8.00 = "
          f"10 x (1-0.20))")

    print()
    if fails:
        print("*** SELF-TEST FAILED ***")
        for f in fails:
            print("   - " + f)
        return False
    print("SELF-TEST PASSED")
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--size", type=float, default=20.0)
    ap.add_argument("--windows", type=int, default=8)
    a = ap.parse_args()

    if a.selftest:
        raise SystemExit(0 if selftest() else 1)
    if not selftest():
        raise SystemExit("self-test failed; refusing to trade")
    if not (a.dry_run or a.live):
        raise SystemExit("pass --dry-run or --live")

    oc.set_env(True)
    pk = oc.load_key(KEY_FILE)
    BASE = oc.PROD

    def api(m, p, body=None, query=None):
        return oc.send(BASE, pk, KEY_ID, m, p, body=body, query=query)

    def balance():
        st, b = api("GET", "/portfolio/balance")
        return float((b or {}).get("balance_dollars") or 0)

    start_bal = balance()
    print(f"\n  starting balance ${start_bal:.4f}   size {a.size:.0f}/side   "
          f"{a.windows} window(s)   {'DRY RUN' if a.dry_run else '*** LIVE ***'}")
    print(f"  caps: cumulative ${oc.MAX_DEPLOYED:.2f}, abort at "
          f"${LOSS_ABORT:.2f}\n")

    live = {"yes": None, "no": None}      # side -> (order_id, price, count)
    log = []
    windows_done = 0
    aborted = None

    def cancel_side(side):
        cur = live.get(side)
        if not cur:
            return
        oid, px, cnt = cur
        if a.live:
            st, r, still = oc.cancel(BASE, pk, KEY_ID, oid, 0)
            if still:
                raise RuntimeError(f"CANCEL FAILED and order {oid} is STILL "
                                   f"RESTING -- aborting rather than continue")
        live[side] = None

    def cancel_all():
        for s in ("yes", "no"):
            try:
                cancel_side(s)
            except Exception as e:
                print(f"  !! {e}")
        if a.live:
            rest, ok = oc.resting_orders(BASE, pk, KEY_ID)
            if not ok:
                print("  !! COULD NOT VERIFY -- check for resting orders BY HAND")
            else:
                print(f"  resting after cleanup: {len(rest)}")
                for o in rest:
                    print(f"     {o.get('ticker')} @ {o.get('yes_price_dollars')}")

    try:
        while windows_done < a.windows and not aborted:
            st, b = api("GET", "/markets", query={"series_ticker": SERIES,
                                                  "status": "open", "limit": "3"})
            mks = (b or {}).get("markets", [])
            if not mks:
                print("  no open gold market; waiting")
                time.sleep(10)
                continue
            # pick the market with the MOST time left, and refuse to join late
            def left(mm):
                return (dt.datetime.fromisoformat(
                    mm["close_time"].replace("Z", "+00:00"))
                    - dt.datetime.now(dt.timezone.utc)).total_seconds()
            mks = sorted([x for x in mks if x.get("close_time")],
                         key=left, reverse=True)
            if not mks or left(mks[0]) < MIN_WINDOW_SECONDS:
                secs = left(mks[0]) if mks else 0
                print(f"  only {secs:.0f}s left in the freshest window "
                      f"(need {MIN_WINDOW_SECONDS}s) -- waiting for the next")
                time.sleep(min(30, max(5, secs + 5)))
                continue
            m = mks[0]
            tk = m["ticker"]
            close = dt.datetime.fromisoformat(
                m["close_time"].replace("Z", "+00:00"))
            print(f"\n  === window {windows_done+1}/{a.windows}: {tk} "
                  f"closes {m['close_time']} ({left(m):.0f}s of quoting) ===")
            wstart = balance()
            ticks = 0

            while dt.datetime.now(dt.timezone.utc) < close - dt.timedelta(seconds=8):
                y, n = book(api, tk)
                ry, dy = ref_price(y)
                rn, dn = ref_price(n)
                if ry is None or rn is None or dy < TARGET or dn < TARGET:
                    time.sleep(CADENCE)
                    continue
                if not (PRICE_MIN <= ry <= PRICE_MAX):
                    # decided market -- a one-sided fill here risks the whole
                    # deployment to earn cents. Stand down, and make sure we
                    # are not left resting into it.
                    if live["yes"] or live["no"]:
                        print(f"    ref_yes {ry:.3f} outside "
                              f"[{PRICE_MIN},{PRICE_MAX}] -- standing down")
                        cancel_side("yes")
                        cancel_side("no")
                    time.sleep(CADENCE)
                    continue

                # BOTH LEGS OR NEITHER.
                # The dry run caught this: when one leg was refused by a rail
                # the loop placed the OTHER one anyway and sat quoting a single
                # side continuously -- which is the naked directional exposure
                # this design exists to avoid. A safety ceiling was CREATING
                # the unsafe state. Build both, validate both, then act.
                plan = {}
                for side, ref in (("yes", ry), ("no", rn)):
                    px = ref if side == "yes" else round(1.0 - ref, 4)
                    o_side = "bid" if side == "yes" else "ask"
                    plan[side] = (ref, px, oc.build_order(
                        tk, o_side, px, a.size,
                        f"gq-{side}-{int(time.time()*1000) % 1000000}"))
                bad = {s: oc.check_limits(v[2]) for s, v in plan.items()}
                pair_collat = sum(oc.collateral(v[2]) for v in plan.values())
                rest, ok = (oc.resting_orders(BASE, pk, KEY_ID) if a.live
                            else ([], True))
                if not ok:
                    raise RuntimeError("cannot read resting orders")
                held = sum(oc.order_collateral(o) for o in rest
                           if o.get("order_id") not in
                           {live[s][0] for s in ("yes", "no") if live[s]})
                blocked = [f"{s}:{b}" for s, b in bad.items() if b]
                if held + pair_collat > oc.MAX_DEPLOYED:
                    blocked.append(f"pair ${pair_collat:.2f} + held ${held:.2f} "
                                   f"> cap ${oc.MAX_DEPLOYED:.2f}")
                if blocked:
                    if live["yes"] or live["no"]:
                        print(f"    PAIR BLOCKED {blocked} -- standing down "
                              f"(never one-sided)")
                        cancel_side("yes")
                        cancel_side("no")
                    time.sleep(CADENCE)
                    continue

                # both legs are legal; re-peg only the ones that moved
                for side in ("yes", "no"):
                    ref, px, body = plan[side]
                    cur = live.get(side)
                    if cur and abs(cur[1] - ref) < 1e-9:
                        continue                      # already at the reference
                    cancel_side(side)                 # CANCEL BEFORE PLACE
                    if a.dry_run:
                        live[side] = ("DRY", ref, a.size)
                        print(f"    [dry] {side} {a.size:.0f} @ {px:.4f} "
                              f"(ref {ref:.4f}, collateral "
                              f"${oc.collateral(body):.2f})")
                    else:
                        stx, r = api("POST", "/portfolio/events/orders", body=body)
                        if stx in (200, 201):
                            live[side] = (r.get("order_id"), ref, a.size)
                            print(f"    {side} {a.size:.0f} @ {px:.4f} "
                                  f"(ref {ref:.4f}) -> {stx}")
                        else:
                            print(f"    {side} @ {px:.4f} -> {stx} "
                                  f"{json.dumps(r)[:120] if isinstance(r,dict) else r}")
                            # a leg failed to place -- do not run one-sided
                            print(f"    leg failed; cancelling the other side")
                            cancel_side("yes" if side == "no" else "no")
                            break
                ticks += 1
                if ticks % 20 == 0 and a.live:
                    cur_bal = balance()
                    st, p = api("GET", "/portfolio/positions")
                    exposure = sum(float(x.get("market_exposure_dollars") or 0)
                                   for x in (p or {}).get("market_positions", []))
                    pnl = (cur_bal + exposure) - start_bal
                    print(f"    .. bal ${cur_bal:.2f} exposure ${exposure:.2f} "
                          f"P&L ${pnl:+.2f}")
                    if pnl <= LOSS_ABORT:
                        aborted = f"loss abort: P&L ${pnl:+.2f} <= ${LOSS_ABORT}"
                        break
                time.sleep(CADENCE)

            cancel_all()
            windows_done += 1
            wend = balance()
            log.append({"window": windows_done, "ticker": tk,
                        "balance_delta": round(wend - wstart, 4)})
            print(f"  window {windows_done} done; balance ${wend:.4f} "
                  f"(delta ${wend-wstart:+.4f})")
            if aborted:
                break
            time.sleep(4)
    except KeyboardInterrupt:
        aborted = "interrupted by operator"
    except Exception as e:
        aborted = f"exception: {e}"
        print(f"\n  !! {e}")
    finally:
        print("\n  --- CLEANUP ---")
        cancel_all()
        end_bal = balance()
        print(f"\n  windows completed : {windows_done}")
        print(f"  balance           : ${start_bal:.4f} -> ${end_bal:.4f} "
              f"({end_bal-start_bal:+.4f})")
        if aborted:
            print(f"  ABORTED           : {aborted}")
        print(f"  per-window        : {json.dumps(log)}")
        print(f"\n  The rebate, if any, is NOT in this number. It appears in the")
        print(f"  balance 48+ hours from now. Read it against PREREG_gold.md.")


if __name__ == "__main__":
    main()
```

## The order layer it calls (`research/ordercli.py`), key functions

```python
CEILINGS = {
    # env:  (MAX_COUNT, MAX_NOTIONAL, MAX_OPEN_ORDERS, MAX_DEPLOYED)
    #  MAX_DEPLOYED is CUMULATIVE collateral across every resting order
    #  plus the one being placed. On a binary that sum IS the maximum
    #  loss. Per-order ceilings never bounded it: a repeg loop at the
    #  permitted S=5 still deploys the whole account (ruin adversary,
    #  2026-09-07).
    # RAISED 2026-09-07 for the gold cutoff test (PREREG_gold.md S5).
    # The cumulative cap IS the maximum loss on a binary: $21 of $65.19.
    # MAX_NOTIONAL MUST BE REACHABLE: at MAX_COUNT=20 the largest
    # possible collateral is 20 x 0.99 = $19.80, so a $20 per-order cap
    # could never fire -- the same dead-ceiling bug the self-test caught
    # on this file at MAX_COUNT=5. $15 binds and still allows a full-size
    # leg priced up to 0.75.
    "prod": (20.0, 15.00, 4, 21.00),
    "demo": (2000.0, 50.00, 12, 50.00),
}
MAX_COUNT, MAX_NOTIONAL, MAX_OPEN_ORDERS, MAX_DEPLOYED = CEILINGS["prod"]


def set_env(is_prod):
    """Select the ceiling set. Called once, before any order is built."""
    global MAX_COUNT, MAX_NOTIONAL, MAX_OPEN_ORDERS, MAX_DEPLOYED
    MAX_COUNT, MAX_NOTIONAL, MAX_OPEN_ORDERS, MAX_DEPLOYED = CEILINGS[
        "prod" if is_prod else "demo"]


def load_key(path):
    from cryptography.hazmat.primitives import serialization
    with open(path, "rb") as f:
        return serialization.load_pem_private_key(f.read(), password=None)


def sign_headers(pk, key_id, method, path):
    """Kalshi RSA-PSS over timestamp+method+path. The path EXCLUDES the query."""
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding
    ts = str(int(time.time() * 1000))
    sig = pk.sign((ts + method + path).encode(),
                  padding.PSS(mgf=padding.MGF1(hashes.SHA256()),
                              salt_length=padding.PSS.DIGEST_LENGTH),
                  hashes.SHA256())
    return {"KALSHI-ACCESS-KEY": key_id,
            "KALSHI-ACCESS-TIMESTAMP": ts,
            "KALSHI-ACCESS-SIGNATURE": base64.b64encode(sig).decode(),
            "Content-Type": "application/json",
            "Accept": "application/json"}


def build_order(ticker, side, price, count, client_id, exchange_index=0):
    """The V2 request body, taken from Kalshi's own create-order-v2 reference.

    side is "bid" (buy YES) or "ask" (sell YES, i.e. economically buy NO).
    price and count are FIXED-POINT STRINGS in dollars, 2-4 decimals.

    Do not re-derive these names from /portfolio/orders records: those are V1
    RESPONSE objects and using them as a request schema is what produced the
    410 on 2026-09-06.

    post_only is not optional and is not an argument.
    """
    return {
        "ticker": ticker,
        "side": side,
        "count": f"{float(count):.2f}",
        "price": f"{float(price):.4f}",
        "time_in_force": "good_till_canceled",
        "self_trade_prevention_type": "maker",
        "post_only": True,                  # <-- CANNOT CROSS. The whole rail.
        "client_order_id": client_id,
        "exchange_index": int(exchange_index),
    }


def collateral(body):
    """What the exchange actually freezes. A bid at p costs p; an ask at p is
    a sale of YES, which costs (1 - p). Getting this backwards would understate
    the risk of every sell-side quote."""
    c = float(body["count"])
    p = float(body["price"])
    return c * (p if body["side"] == "bid" else (1.0 - p))


def check_limits(body):
    """Refuse before signing, not after. Returns a list of violations."""
    bad = []
    c = float(body["count"])
    p = float(body["price"])
    if c > MAX_COUNT:
        bad.append(f"count {c} exceeds MAX_COUNT {MAX_COUNT}")
    if c <= 0:
        bad.append(f"count {c} is not positive")
    if not (0.0 < p < 1.0):
        bad.append(f"price {p} is outside (0,1)")
    if collateral(body) > MAX_NOTIONAL:
        bad.append(f"collateral {collateral(body):.2f} exceeds MAX_NOTIONAL "
                   f"{MAX_NOTIONAL}")
    if body.get("post_only") is not True:
        bad.append("post_only is not True -- this order could TAKE liquidity")
    if body.get("time_in_force") != "good_till_canceled":
        bad.append(f"time_in_force is {body.get('time_in_force')!r}, not "
                   f"good_till_canceled")
    if body.get("side") not in ("bid", "ask"):
        bad.append(f"side is {body.get('side')!r}, not bid or ask")
    return bad


def token_for(body, base):
```
