# ACCOUNT FORENSICS — the complete real-money record of this Kalshi account

Run 2026-09-06 ~19:20Z. All figures from authenticated read-only GETs against
`api.elections.kalshi.com/trade-api/v2` plus the public trade tape for the four
markets involved. **No orders were placed, amended or cancelled.** Raw pulls are
in `C:\Users\Joe\AppData\Local\Temp\kals-work\job3f\`.

---

## 0. BOTTOM LINE

The account's entire life is **4 fills, 4 orders, 4 settlements, 3 deposits, 0
withdrawals**. It is not a research record. It is two evenings of manual
directional punting on Bitcoin, three weeks ago, and it lost **99.9% of every
dollar ever put in**.

| | |
|---|---|
| Gross deposited | **$39.60** |
| Debit-card deposit fees | $0.58 |
| Net credited to balance | **$39.02** |
| Contracts bought | 125.65 (fractional) |
| Notional bought | $56.3202 |
| Trading fees paid | **$1.9851** |
| Settlement revenue received | $19.32 |
| **Gross trading P&L** | **-$37.0002** |
| **Net trading P&L (after fees)** | **-$38.9853** |
| Current balance | **$0.0047** |
| Peak balance ever | $38.5252 |
| Fraction of net deposits lost | **99.91%** |

Four things it settles that no backtest could:

1. **Kalshi's fee is `ceil(0.07*p*(1-p)*n , $0.0001)`** — ceiling to a
   hundredth of a cent, not to a cent. Exact on 4/4 fills.
   `kalshi_backtest.py` uses cent-ceiling and is **wrong**.
2. **Four market orders, up to 54.99 contracts, filled entirely at one price
   with zero ticks of slippage.** Not "about one price" — `taker_fill_cost /
   fill_count` equals the printed price *exactly*, to the cent, on all four.
3. **This account has never rested a single order.** Maker behaviour is
   completely unevidenced. `maker_fill_cost_dollars = 0.000000` on 4/4 orders.
4. **No incentive credit has ever been received** — and it is bounded, not
   assumed: deposits + settlements alone reconcile the balance to within
   **$0.03**, so any incentive credit in this account's history is at most $0.03.

And one thing found by accident that is worth more than all of the above —
see section 7: **the liquidity programme on the very series this account traded
(KXBTC15M) was switched off by Kalshi on 2026-05-12 after 107 days.** The
programme the whole plan rests on (Coin Race) is 15 days old, and 78 of the 107
series Kalshi has ever paid more than $20k on are already dead. Survival-
corrected, Coin Race's median remaining life is about **107 days** — a quarter,
not a year. Price the strategy accordingly.

---

## 1. TOTAL REALISED P&L, RECONCILED BY HAND

### 1.1 Completeness of the pull

Every endpoint was paginated to exhaustion and the result cross-checked against
every filter that could plausibly hide rows:

```
/portfolio/fills        limit=200                         -> 4, cursor END
                        min_ts=0 / 1 / 1600000000         -> 4  (no default lookback)
                        min_ts=1 & max_ts=2000000000      -> 4
/portfolio/orders       status = executed                 -> 4
                        status = resting/canceled/pending -> 0, 0, 0
/portfolio/settlements  limit=200, min_ts=1               -> 4
/portfolio/deposits                                       -> 3
/portfolio/withdrawals                                    -> 0
/portfolio/positions    settlement_status all/settled/unsettled -> 0, 0, 0
```

The small count is real, not a truncation artefact: widening the time window
five different ways returns the same 4 rows, and the status filters partition
cleanly (4 executed + 0 resting + 0 canceled + 0 pending = 4 total).

These endpoints returned **404**: `/portfolio/transactions`, `/portfolio/ledger`,
`/portfolio/account_history`, `/portfolio/pnl`, `/portfolio/summary`,
`/portfolio/rewards`, `/portfolio/incentives`, `/portfolio/credits`,
`/portfolio/adjustments`, `/portfolio/statements`, `/portfolio/bonuses`,
`/user/balance`. **There is no general cash-ledger endpoint on this API key.**

### 1.2 The complete cash ledger, in order

Balance in cents. Deposits credited net of their card fee (justified below).

```
2026-08-15 04:28:00Z (Sat 00:28 ET) DEPOSIT  +1000.00 -> 1000.00  $10.00 gross, fee $0.00
2026-08-15 04:34:03Z (Sat 00:34 ET) BUY       -980.48 ->   19.52  KXBTC15M-26AUG150045-45 yes 19.32@0.49
2026-08-15 04:45:06Z (Sat 00:45 ET) DEPOSIT  +1901.00 -> 1920.52  $19.39 gross, fee $0.38
2026-08-15 04:45:12Z (Sat 00:45 ET) SETTLE   +1932.00 -> 3852.52  ...150045-45 -> YES.  WIN
2026-08-15 04:45:15Z (Sat 00:45 ET) BUY      -1899.78 -> 1952.74  KXBTCD-26AUG1501-T63099.99 yes 54.99@0.33
2026-08-15 05:02:42Z (Sat 01:02 ET) SETTLE      +0.00 -> 1952.74  ...T63099.99 -> NO.   LOSS
2026-08-15 05:19:05Z (Sat 01:19 ET) BUY      -1899.55 ->   53.19  KXBTC15M-26AUG150130-30 yes 38.97@0.47
2026-08-15 05:30:02Z (Sat 01:30 ET) SETTLE      +0.00 ->   53.19  ...150130-30 -> NO.   LOSS
2026-08-15 05:30:37Z (Sat 01:30 ET) DEPOSIT  +1001.00 -> 1054.19  $10.21 gross, fee $0.20
2026-08-23 01:06:24Z (Sat 21:06 ET) BUY      -1050.72 ->    3.47  KXBTC15M-26AUG222115-15 no 12.37@0.84
2026-08-23 15:35:37Z (Sun 11:35 ET) SETTLE      +0.00 ->    3.47  ...222115-15 -> YES.  LOSS
```

### 1.3 Reconciliation, and a $0.03 hole

```
computed final balance   3.4700 c   = $0.034700
API balance_dollars      0.4700 c   = $0.004700
RESIDUAL                 3.0000 c   = $0.030000   UNEXPLAINED
```

**Deposit-fee convention.** `fee_cents / (amount_cents - fee_cents)` = 38/1901 =
1.9989% and 20/1001 = 1.998%. So the card fee is **2% of the net credited**, the
gross `amount_cents` is what hit the card, and the balance receives
`amount - fee`. Under the alternative reading (balance gets `amount`, fee taken
off-platform) the residual is $0.61 instead of $0.03, so the net-credit reading
is right. The first $10 deposit carried **no fee** — presumably a first-deposit
waiver.

**The $0.03 is exactly round**, which rules out accumulated fractional rounding
(that would leave a ragged residual). It is a discrete three-cent debit that
appears on **no readable endpoint**. I could not find it. I tested and rejected:
cent-ceiling of cost (2.0c), cent-ceiling of fee (1.5c), cent-ceiling of the
combined debit (1.5c), a 2%-of-gross deposit fee (1.2c) — none produce 3.00c.

**Why this matters beyond three cents.** It is proof that *the API is not a
complete cash ledger for this account*. Money can move in and out of the balance
without appearing in fills, orders, settlements, deposits or withdrawals. If the
operator ever runs the liquidity programme, **a LIP credit will very likely
arrive by exactly this invisible mechanism and will not be auditable from any
endpoint tested here.** Payout verification will have to be done by differencing
`/portfolio/balance` on a schedule, not by reading a ledger. That is a concrete
instrumentation requirement for the live test, and it is cheap to build.

---

## 2. WHAT THE STRATEGY ACTUALLY WAS

There was no strategy. There was a Saturday night.

| | Session 1 | Session 2 |
|---|---|---|
| When (ET) | Sat 2026-08-15, 00:34-01:19 | Sat 2026-08-22, 21:06 |
| Trades | 3 | 1 |
| Elapsed | 45 minutes | single trade |

* **Series:** 3 x `KXBTC15M` (BTC up in the next 15 minutes), 1 x `KXBTCD`
  (BTC daily level). 100% Bitcoin. Nothing else was ever traded.
* **Direction:** 3 x buy YES, 1 x buy NO. All **buys**; the account has never
  sold, never shorted by selling, never closed a position.
* **Order type:** **all four `type: "market"`**, with the price field pinned to
  the worst-case cap (0.99 / 0.01) — i.e. unlimited-price market orders.
* **Taker/maker:** **4/4 `is_taker: true`**.
* **Size:** 12.37 / 19.32 / 38.97 / 54.99 contracts. These are not round, because
  they are **dollar-denominated orders**: cost + fee comes to $9.80, $19.00,
  $19.00, $10.51. The operator typed a dollar amount, not a contract count.
  Sizes ran at the **48th-72nd percentile** of print size in those markets.
* **Exit:** **none, ever.** All four positions were held to settlement.
  `remaining_count_fp = 0.00` on every order; there is not one sell fill.
* **Timing within the market:** entered 4-6 minutes into a 15-minute window
  (t+244s, t+245s, t+385s), i.e. mid-window, ~11 minutes from expiry. The daily
  was entered 15 minutes before its close.
* **Bankroll behaviour:** each trade consumed essentially the whole balance, and
  the account was **re-funded from the card three times inside 62 minutes** to
  keep trading. That is the signature of chasing, not of a sized programme.

The account is **22 days old** (first deposit 2026-08-15) and has been
**dormant for 14 days**.

### 2.1 How each position actually went

Reconstructed from the full public trade tape — 90,169 prints across the four
markets, summed volume matching the API's `volume_fp` to **ratio 1.0000** on all
four, with **zero duplicate trade_ids**, so the tape pull is provably complete.

| Market | Entry | Result | MFE (best mark) | MAE | Realised |
|---|---|---|---|---|---|
| KXBTC15M-26AUG150045-45 | yes 19.32 @ 0.49 | **YES — WIN** | 0.999 @ +615s | 0.46 @ +7s | **+$9.52** |
| KXBTCD-26AUG1501-T63099.99 | yes 54.99 @ 0.33 | NO — loss | 0.34 @ +8s | 0.01 @ +459s | **-$19.00** |
| KXBTC15M-26AUG150130-30 | yes 38.97 @ 0.47 | NO — loss | 0.51 @ +143s | 0.001 @ +577s | **-$19.00** |
| KXBTC15M-26AUG222115-15 | no 12.37 @ 0.84 | YES — loss | 0.999 @ +478s | 0.05 @ +514s | **-$10.51** |

The fourth trade is the one to remember. He bought NO at 0.84. With **38 seconds
left in the market** his NO was marked at **0.999** — a near-certain $1.97 win.
Thirty-six seconds later it was marked **0.05**. BTC crossed the $77,305.87
strike in the last half-minute and the position went from won to worthless.
Final prints were 0.85-0.90 YES.

Holding to settlement cost real money: exiting each position at its best
post-entry mark would have returned **+$13.91** instead of **-$38.99**, a swing
of **$52.89**. That is an after-the-fact upper bound, not an achievable
strategy — but the direction is unambiguous, and it is consistent with the
repo's own finding that these 15-minute markets are dominated by a violent
endgame.

### 2.2 Settlement latency — a capital-lockup tail nobody has priced

| Market | `settlement_timer_seconds` | Actual close -> settle |
|---|---|---|
| KXBTC15M-26AUG150130-30 | 1 | **2.4 s** |
| KXBTC15M-26AUG150045-45 | 1 | **12.4 s** |
| KXBTCD-26AUG1501-T63099.99 | 60 | **162.4 s** |
| KXBTC15M-26AUG222115-15 | 1 | **51,637 s (14h 20m)** |

One of four settlements took **fourteen hours and twenty minutes** against a
declared 1-second timer. For a capital-constrained strategy that recycles the
same few hundred dollars across consecutive 15-minute windows, a 14-hour lockup
on a position is not a rounding error — it is the difference between running and
being flat for a day. n=1, but it happened on 25% of this account's settlements.

---

## 3. FEE DRAG — AND A CORRECTION TO THE BACKTEST

### 3.1 The formula, pinned exactly

The brief's `0.07*p*(1-p)` is right about the shape and silent about the
rounding. The rounding is now determined, because one of the four fills
discriminates between the candidates:

| Market | n | p | **ACTUAL** | ceil 1e-4 | unrounded | ceil cent |
|---|---|---|---|---|---|---|
| KXBTC15M-26AUG150045-45 | 19.32 | 0.49 | 0.338000 | **0.338000 OK** | 0.337965 | 0.34 |
| KXBTCD-26AUG1501-T63099.99 | 54.99 | 0.33 | 0.851100 | **0.851100 OK** | 0.851080 | 0.86 |
| KXBTC15M-26AUG150130-30 | 38.97 | 0.47 | 0.679600 | **0.679600 OK** | 0.679520 | 0.68 |
| KXBTC15M-26AUG222115-15 | 12.37 | 0.84 | 0.116400 | **0.116400 OK** | 0.116377 | 0.12 |

`KXBTC15M-26AUG150130-30` is the discriminating case: raw = 0.6795199,
**nearest**-1e-4 gives 0.6795 (wrong), **ceiling**-1e-4 gives 0.6796 (right).

> **fee = ceil( 0.07 * p * (1-p) * n , $0.0001 )**, where `p` is the price of the
> side bought, and `n` may be fractional. Exact on 4/4. Makers pay $0.00.

### 3.2 Scoring `kalshi_backtest.py`

`kalshi_backtest.py:44` — `fee(p,n) = math.ceil(0.07*p*(1-p)*n*100)/100.0` —
ceilings to the **cent**. Against the four real charges it overstates by:

```
+0.59%   +1.05%   +0.06%   +3.09%       aggregate +0.75%  ($2.0000 vs $1.9851)
```

The error is small at size and grows as size shrinks and p goes extreme — it is
worst (3.09%) on the smallest, most-extreme-priced fill. Any per-contract or
small-clip backtest is biased pessimistic; anything at 50+ contracts is fine.
`research/edge.py` and `research/engine.py` use the unrounded
`0.07*p*(1-p)` and are within **0.008%** of truth — those are correct in
practice. `FEES_AND_PRODUCTS.md:187` already flags that "ceil to next cent" is
wrong, but the code was never updated to match the doc.

### 3.3 The drag itself

| Denominator | Fee drag |
|---|---|
| of notional bought ($56.3202) | **3.525%** |
| of net deposits ($39.02) | 5.087% |
| of gross P&L magnitude ($37.0002) | 5.365% |
| of the total loss ($38.9853) | 5.092% |
| mean fee per contract | $0.015798 |

Fees turned a -$37.00 gross into a -$38.99 net. **A maker would have paid zero
of it.** That 3.5%-of-notional round-trip tax is the confirmed, ledger-level
size of the maker/taker edge in this account — not a modelled figure, a charged
one.

### 3.4 Any fill where the formula fails?

**None.** 4/4 reproduce to the last of six decimal places. No unknown fee
schedule is in evidence. Caveat: all four are buys, all four are takers, all
four are BTC, and all four are in the 0.33-0.84 price band. **The formula is
unverified for sells, for makers, for other product families, and for prices
outside 0.33-0.84.** In particular the fee on the *maker* side is confirmed only
as "$0.000000 on four orders that had no maker fills" — which is no confirmation
at all. It rests on documentation, not on this ledger.

---

## 4. WERE ANY ORDERS EVER RESTING? — NO. NONE. EVER.

This was the highest-value question in the brief and the answer is a clean,
total negative.

```
orders?status=resting   -> 0
orders?status=canceled  -> 0
orders?status=pending   -> 0
orders?status=executed  -> 4   (= all of them)
```

On all four orders:

```
type                    = "market"          (never "limit")
initial_count_fp        = fill_count_fp     (19.32=19.32, 54.99=54.99, 38.97=38.97, 12.37=12.37)
remaining_count_fp      = 0.00
maker_fill_cost_dollars = 0.000000
maker_fees_dollars      = 0.000000
last_update_time        = created_time      (to the microsecond, on all four)
```

`last_update_time == created_time` to the microsecond is the decisive detail:
**no order ever existed for a measurable instant without being filled.** Nothing
ever sat in a book. There is no queue-position data, no fill-rate data, no
adverse-selection data, no cancel/replace behaviour, and no rebate history.

**Consequence for the live-test decision.** The critic's fourth demand —
"realised score share after simulated or live posting... only filled orders do" —
is not merely unanswered by history. It is unanswered by *this account*, which
has never performed the action in question even once. The forensics cannot
shrink the live test. It confirms the test is unavoidable.

---

## 5. ANY INCENTIVE CREDIT EVER RECEIVED? — NO, AND IT IS BOUNDED AT $0.03

Every ledger-shaped endpoint was probed. `/portfolio/rewards`,
`/portfolio/incentives`, `/portfolio/liquidity_rewards`, `/portfolio/credits`,
`/portfolio/bonuses`, `/portfolio/adjustments`, `/portfolio/promotions`,
`/incentive_programs/participation`, `/incentive_programs/rewards`,
`/incentive_programs/payouts`, `/incentive_programs/my_scores` — **all 404.**
There is no per-account incentive endpoint on this API surface.

So the claim is made by exhaustion of the balance instead, which is stronger:

> The three deposits ($39.02 net) and the one winning settlement ($19.32),
> minus the four trade costs and fees, account for the balance to within
> **$0.0300**. Therefore **the total of all credits this account has ever
> received that are not a deposit or a settlement is at most $0.03**, and the
> unexplained residual is a *debit*, not a credit.

No incentive money has ever touched this account. The account has never been
eligible — see section 7 — and has never rested an order to earn any.

---

## 6. LESSONS — SCORING THE MODELS AGAINST REAL EXECUTIONS

Four executions is a tiny sample, but they are *real*, and three model
assumptions are directly testable against them.

### 6.1 Slippage: the models are pessimistic. Confirmed, hard.

`research/patterntrade.py:63` assumes `HALF_SPREAD = 0.005` ("the liquid series
quote 1c wide"). What did four unlimited-price **market** orders actually pay?

```
KXBTC15M-26AUG150045-45    19.32 -> 1 print, 1 price, 9.466800/19.32  = 0.4900 EXACT
KXBTCD-26AUG1501-T63099.99 54.99 -> 1 print, 1 price, 18.146700/54.99 = 0.3300 EXACT
KXBTC15M-26AUG150130-30    38.97 -> 1 print, 1 price, 18.315900/38.97 = 0.4700 EXACT
KXBTC15M-26AUG222115-15    12.37 -> 1 print, 1 price, 10.390800/12.37 = 0.8400 EXACT
```

**Zero ticks of slippage on 4/4.** This is airtight rather than approximate: if
an order had swept two levels the volume-weighted average would not land exactly
on a tick. It does, on all four, to the cent.

Two things follow. First, **market orders of 12-55 contracts do not move these
books** — the half-spread is the whole cost, there is no impact term. Second,
and more useful, this is a **measured lower bound on top-of-book depth**: the
ask held **at least 54.99** contracts in KXBTCD and **at least 38.97 / 19.32 /
12.37** in KXBTC15M at those instants.

That bound bears on the modelled 12.55% LIP share at 50 contracts a side, but
only weakly, and in a direction worth stating honestly: a 12.55% share implies
roughly 350-400 contracts of competing effective size in the scored levels. A
single level holding at least 55 contracts is **consistent with** that and
**does not confirm it**. It is mild corroboration that the operator would be a
small fish, not evidence about share. Do not cite it as such.

### 6.2 Tick grid: right where the money is, wrong elsewhere

`tick_at(p) = 0.001 if (p>0.90 or p<0.10) else 0.01`, used identically in
`kalshi_backtest.py` and `research/engine.py`. Checked against every distinct
price in 90,169 real prints:

* **Zero sub-cent prices inside [0.10, 0.90] in all four markets.** The
  cent-in-the-middle rule is confirmed.
* **KXBTC15M** (`price_level_structure: "tapered_deci_cent"`): sub-cent prices
  observed at 0.0010-0.0990 and 0.9010-0.9990, min gap 0.0010. **tick_at() is
  correct.**
* **KXBTCD** (`price_level_structure: "linear_cent"`): **705 prints below $0.10
  (13.6% of the market, 103,615 contracts) and not one sub-cent price** — the
  distinct set below 0.10 is exactly {0.01 ... 0.09}, min gap 0.0100.
  **tick_at() is wrong here**, inventing ten times the price levels that exist.

The API hands you the answer in `market.price_level_structure`. The code
hardcodes one rule for every product. The families the LIP money is in are
`tapered_deci_cent`, so **this bug does not touch the Coin Race thesis** — but
it silently corrupts anything modelled on dailies, and it is a two-line fix.

### 6.3 The mirror trade: what the maker on the other side earned

Binary settlement makes the counterparty's P&L exactly computable.

| Trade | Maker's side | Maker P&L | Maker fees | My P&L | My fee |
|---|---|---|---|---|---|
| ...150045-45 | sold yes @0.49 x19.32 | -$9.85 | $0.00 | +$9.85 | $0.3380 |
| ...T63099.99 | sold yes @0.33 x54.99 | +$18.15 | $0.00 | -$18.15 | $0.8511 |
| ...150130-30 | sold yes @0.47 x38.97 | +$18.32 | $0.00 | -$18.32 | $0.6796 |
| ...222115-15 | sold no @0.84 x12.37 | +$10.39 | $0.00 | -$10.39 | $0.1164 |
| **TOTAL** | | **+$37.00** | **$0.00** | **-$37.00** | **$1.9851** |

Sums to zero to six decimals. The makers who filled this account made **$37.00
and paid nothing**; the account lost $37.00 **and paid $1.99 to the house**.
The maker side won 3 of 4.

**3-of-4 is an anecdote, not a result.** At n=4 a fair coin produces 3+ wins
about 31% of the time. It proves nothing about maker edge. What it *does*
illustrate exactly is the structural asymmetry that is not in dispute: the maker
paid $0.00 in fees on $56.32 of notional, and the taker paid $1.99. That part is
arithmetic, not sampling.

### 6.4 Did realised fills match modelled fills in size and price?

Honestly: **the comparison the brief hoped for cannot be made.**

* The local order-book tape (`C:\kals\kalshi_data`) begins **2026-08-25T03:00Z**.
  The last fill was **2026-08-23T01:06Z**. The tape starts **two days after the
  account stopped trading**, and ten days after three of the four fills. There
  is no book snapshot for any execution this account ever made.
* Public *trade* prints were recoverable (and were, completely — that is what
  sections 2.1 and 6.1 are built on), but public prints have **no bid/ask and no
  depth**. Fill price versus the touch, queue position, and depth at the touch
  are all unrecoverable beyond the lower bounds in 6.1.
* Every fill is a **taker market order**, so there is **no modelled maker fill to
  score against**. The fill model in `JOB_A_REFUTE_lens1_fillmodel.md` is
  untouched by this evidence in either direction.

What the history *does* score, it scores cleanly: the **fee** model (3.2), the
**tick** model (6.2) and the **slippage** model (6.1). Two were wrong, in
opposite directions, and both are now pinned to real charges.

---

## 7. THE FINDING THAT WAS NOT ON THE LIST

Chasing "was this account's series ever incentivised?" turned up the single most
decision-relevant fact in this report. I paginated `/incentive_programs` to
**cursor exhaustion** — 178 pages, **177,014 programmes**.

### 7.1 The brief's programme numbers are substantially understated

| | Brief | Measured (cursor exhausted) |
|---|---|---|
| Programmes | 80,000 | **177,014** |
| Paid | 68,805 | **165,972** |
| Dollars paid | $5,051,195 | **$11,090,509** |

The brief paginates with `cursor`; the field is **`next_cursor`**. Using
`cursor` silently returns page one and stops. **Anything downstream of that
80,000-row pull is built on 45% of the data.**

Paid dollars by programme-start month:

```
2025-09     57,395     2026-03    641,959     2026-07  2,127,455
2025-10    311,445     2026-04  1,099,321     2026-08  2,488,425
2025-11    232,721     2026-05  1,527,110     2026-09    495,180 (partial)
2025-12    204,030     2026-06  1,298,060
2026-01    242,518
2026-02    365,700
```

The real August run-rate is **$2.49M/month**, not $1.75M, and it has grown every
month bar one. The pool is **bigger** than believed. That is the good news, and
it is the last of it.

### 7.2 Kalshi rotates these programmes off. It already did it to this account's series.

| Series | Programmes | Paid | First window | Last window | Status |
|---|---|---|---|---|---|
| **KXBTC15M** | 9,781 | **$162,600** | 2026-01-26 | **2026-05-12** | **DEAD 117 days** |
| **KXETH15M** | 8,299 | **$147,770** | 2026-02-13 | **2026-05-12** | **DEAD 117 days** |
| KXCRYPTOLEAD15M (Coin Race) | 6,385 | $127,700 | **2026-08-24** | 2026-09-07 | LIVE, **15 days old** |
| KXGOLD15M / KXSILVER15M / KXWTI15M | 2,420 ea | ~$47,600 ea | 2026-08-03 | 2026-09-07 | LIVE, 36 days |
| KXTEMPCHIH / DCH / LAXH / NYCH / AUSH | ~2,400 ea | $186k-235k ea | 2026-07-08 | **2026-08-04** | **all DEAD, same day** |
| KXMIDTERMMOV | 3,343 | $294,205 | 2026-04-28 | 2026-05-06 | DEAD (9-day life) |

**KXBTC15M — three of this account's four trades — paid makers $10-20 per
15-minute window, $162,600 over 107 days, and Kalshi switched it off on
2026-05-12.** KXETH15M was switched off **the same day**. The five
city-temperature programmes were switched off together on **2026-08-04**. This
is not attrition; it is deliberate, simultaneous, series-wide termination with
no notice visible anywhere in the API.

Across the **107 series Kalshi has paid more than $20,000 on**, programme
lifetime (first to last scheduled window):

```
min 1d     p25 28d     MEDIAN 58d     p75 146d     max 326d
78 of 107 are dead (no window scheduled in the last 2 days); 29 are live.
```

**How long has Coin Race got? Do not subtract.** My first pass took "median 58
days, Coin Race is 15 days old" and reported 43 days left. **That is wrong** —
it ignores that surviving 15 days is itself information. Conditioning properly:

```
series that survived at least 15 days:  n = 93 of 107
their median TOTAL life:                122 days
=> median REMAINING life from day 15:   107 days
```

And that 107 is **conservative**: 29 of the 107 series are still alive, so their
observed lifetimes are right-censored lower bounds and the true median is higher.

So the honest reading is not "Coin Race dies in six weeks". It is: **a programme
that has already reached day 15 has a median of about 107 more days**, which is
— by coincidence that is worth noting rather than trusting — almost exactly the
**107-day life of KXBTC15M**, its direct predecessor in the same asset class,
same 15-minute crypto structure, same exchange, same programme design.

The risk is real but it is a **quarter, not a month**.

### 7.3 What this does to the live-test decision

It does not kill it. It sharpens it, in the operator's favour:

* **It raises the value of testing now, but does not panic.** Median remaining
  life is about **107 days**, not six weeks. That is enough runway to run a
  small live test properly rather than rushing it — but it is not enough to
  spend another month on historical reconstruction first. The critic's demand —
  only filled orders settle realised share — now has a clock on it, and the
  clock reads one quarter, not one year.
* **It caps how much the answer is worth.** Whatever share the live test
  measures, it should be capitalised over roughly **a quarter** of Coin Race,
  not indefinitely. Any business case that annualises the Coin Race rate is
  wrong: **no crypto 15-minute programme on this exchange has ever run a year,
  and the two that came closest both died on 2026-05-12.**
* **It argues for measuring the machinery, not the market.** The durable asset
  is a working, verified maker loop that can be pointed at whichever series is
  incentivised this month — 3,358 distinct series have had programmes. The
  perishable asset is Coin Race specifically.
* **It adds a monitoring requirement that costs nothing.** `next_cursor`-correct
  daily scans of `/incentive_programs` would have given 117 days of warning that
  KXBTC15M was dead. The same scan is the early-warning system for Coin Race.

---

## 8. WHAT THIS REPORT CANNOT SETTLE

Stated plainly, because the sample is four:

* **Nothing about maker behaviour.** Zero resting orders ever. No queue data, no
  fill rates, no adverse selection, no rebates. Section 4 is a total negative.
* **Nothing about realised LIP score share.** The account has never been in an
  incentivised market while it was incentivised.
* **Nothing statistical about edge.** n=4, one winner. The maker's 3-of-4 is
  noise (p is about 0.31 under a fair coin).
* **The fee formula for sells, makers, non-BTC products, and prices outside
  0.33-0.84.** Verified only for taker buys in that band.
* **The $0.03.** Unexplained. Bounded, immaterial in itself, but proof the API is
  not a complete cash ledger — which is a real instrumentation gap for verifying
  any future incentive payout.
* **Fill-versus-book comparison.** The local tape starts 2026-08-25T03:00Z, two
  days after the last fill. Permanently unrecoverable for these executions.
* **Whether Coin Race will actually be terminated.** Section 7 establishes a base
  rate and a precedent in the same asset class. It is not a prediction.

---

## 9. ONE OPERATIONAL FACT FOR SIZING THE LIVE TEST

The operator has ~$1,000. **This account has never held more than $38.53.** It
has never processed a deposit larger than $19.39, has never made a withdrawal,
and has been dormant 14 days. Card deposits cost **2%** — funding $1,000 by the
route used so far would cost **$20** before a single order.

Anything in the live-test design that assumes a funded, exercised account is
assuming something this ledger does not support. Deposit rails, withdrawal rails
and maker-order placement are all **completely unexercised**. The first live
test should expect to spend some of its budget discovering that, and the plan
should treat "can this account actually rest an order and get filled" as a
finding in its own right, not as a precondition.

---

### Provenance

Raw JSON: `C:\Users\Joe\AppData\Local\Temp\kals-work\job3f\`
— `fills.json` (4), `orders.json` (4), `settlements.json` (4), `deposits.json` (3),
`withdrawals.json` (0), `pubtrades.json` (90,169 prints), `lip_series.json`,
`lip_btc15m.json`, `lip8.out`.

Scripts: `pull.py`, `pull2.py`, `probe2.py`, `probe3.py`, `recon.py`, `match.py`,
`verif2.py`, `score.py`, `exc.py`, `final.py`, `lip6.py`, `lip7.py`, `lip8.py`,
`surv.py`.
All access read-only GET via `kauth.py`. No order endpoint was contacted.

Collectors verified alive after the run: `kalshi_collector.py` PID 3381772,
`crypto_feeds.py` PID 3385232; tape writing `20260906T19.jsonl.gz` at 19:17Z.
Free disk 52 GB.
