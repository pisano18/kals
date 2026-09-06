# FEES, REBATES AND CHEAPER PRODUCTS

Run 2026-09-06 ~11:30-11:55 UTC from `C:\kals-repo`. All API calls read-only
against `https://api.elections.kalshi.com/trade-api/v2`. **No order endpoint was
touched.** Probe scripts live in `C:\Users\Joe\AppData\Local\Temp\kals-work\fees\`.

Every claim below is tagged **[API]** (live call this session), **[DOC]**
(Kalshi documentation), **[TAPE]** (local recorded data), or **[INFERENCE]**.

---

## THE HEADLINE

**Kalshi runs a Liquidity Incentive Program that pays makers for resting orders
whether or not they fill, and it is live right now on markets that resolve in 15
minutes.** `GET /incentive_programs` **[API]** returns a per-market, per-15-minute
reward pool. The 12 crypto up/down series this project has spent weeks on are the
**only** 15-minute family with **no** incentive program at all.

| family | reward/window | target size | windows/day | pool/day | recorded by collector? |
|---|---|---|---|---|---|
| `KXCRYPTOLEAD15M` (Coin Race, 5 coins) | **$20.00** | 1,000 | ~52 event-windows | **~$5,200** | **yes, already** |
| `KXGOLD15M` / `SILVER` / `WTI` / `NATGAS` / `COPPER` | **$20.00** | **300** | 24 each | **~$2,400** | **no** |
| `KXBTC15M` + 11 crypto siblings | **none** | — | — | **$0** | yes |

This is money that **does not require the market to be wrong.** You are paid for
posting depth. It is the first thing found in this project that pays for
inventory-provision rather than for a forecast.

---

## 1. KXINX15M / KXNDQ15M — CONTRADICTION 3 SETTLED

**Both sides of the repo's contradiction were half right, and the operator's
practical conclusion was correct.** **[API]**

`GET /series/KXINX15M` and `/series/KXNDQ15M` both return **200 OK**:

```
KXINX15M  "S&P 500 15-minute"    category=Financials  exchange_index=0
KXNDQ15M  "Nasdaq 100 15-minute" category=Financials  exchange_index=0
  frequency = "fifteen_min"     fee_type = "quadratic"    fee_multiplier = 1
```

So `HANDOFF.md` line 1992 is right that the `frequency` field lists them. **But
they have never listed a market.** **[API]**

```
/markets?series_ticker=KXINX15M   status=open     -> 0
                                  status=settled  -> 0
                                  (no status)     -> 0
/events?series_ticker=KXINX15M                    -> 0
```

Control: the identical query returns 5 markets for `KXBTC15M`, `KXINXU`
(S&P hourly) and `KXNASDAQ100U`, so the query shape is correct and the zero is
real, not a weekend artefact.

**Verdict: the series are registered product templates with zero markets. They
are not tradeable. `IDEAS.md` B3 should be struck** — not because the series
don't exist, but because there is nothing to trade and, decisively:

**There is no fee discount to be had anyway.** `fee_multiplier = 1` and
`fee_type = "quadratic"` on both, identical to `KXBTC15M`. The half-fee equity
lever does not exist. **This confirms `HANDOFF.md` section 6 and refutes
`PLAN.md`'s 0.035-vs-0.07 premise, from a live call.**

### Fee formula, multiplier, settlement mechanism

**Fee [DOC + API].** The model fee is `fee_multiplier * 0.07 * p * (1-p)` dollars
per contract. Confirmed arithmetically against Kalshi's own worked example in
`docs.kalshi.com/getting_started/fee_rounding.md`: a fill at p=0.055 is given a
model fee of `$0.00363825`, and `0.07 * 0.055 * 0.945 = 0.00363825` exactly.
**Makers pay zero model fee on `fee_type = "quadratic"` series** (see section 2).

**Multiplier is a rate, not a waiver flag — HANDOFF.md section 6 is WRONG on
this.** **[API]** Across all 13,839 series:

```
fee_multiplier:  1 -> 13,806     0.5 -> 19     0 -> 14
```

`HANDOFF.md` section 6 states "`fee_multiplier` is an integer 0/1 waiver flag,
not a rate". **There are 19 series at 0.5.** They are all MLB (section 2). That
sentence in HANDOFF.md needs correcting.

**Settlement mechanism [API], read from live `rules_primary`:**

- `KXBTC15M`: *"If the simple average of the sixty seconds of CF Benchmarks'
  BRTI before 7:30 AM EDT ... is at least the simple average o[f ...]"* — the
  60-print average is **confirmed directly from the API**, both for the settle
  and for the strike. The repo's `Var(settle-strike) = 880 sigma^2` model stands.
- The equity 15M series have no markets, so **no settlement mechanism can be
  observed for them.** Their `settlement_sources` field says
  *"For example, Google Finance"*, which is a spot quote, not an average
  **[INFERENCE]** — but with zero markets this is moot.

---

## 2. MAKER REBATES, VOLUME TIERS, PER-PRODUCT FEES

### YES — there are maker rebates, and they are better than nothing

`GET /incentive_programs` **[API]** — undocumented in this repo, never used.

```json
{"incentive_type": "liquidity", "incentive_description": "series_lip",
 "market_ticker": "KXGOLD15M-26SEP070000-00",
 "period_reward": 200000, "target_size_fp": "300.00",
 "discount_factor_bps": 5000,
 "start_date": "2026-09-07T03:45:00Z", "end_date": "2026-09-07T04:00:00Z",
 "paid_out": false}
```

`period_reward` is in **centi-cents — divide by 10,000 for USD** **[DOC]**. So
`200000` = **$20.00**, `1000000` = $100.00, `2000000` = $200.00.

**The program demonstrably pays.** `status=paid_out` returns 1,000+ rows with
`paid_out: true`, including 24 settled `KXCOPPER15M` windows and 23 each for
`KXSILVER15M`, `KXWTI15M`, `KXNATGAS15M`, `KXGOLD15M`. **[API]**

**Payout formula [DOC]** (Kalshi Help Center, *Liquidity Incentive Program*):

```
your reward = (your Time Period Score)
            * (Time Period Reward)
            * (non-excluded snapshots / total snapshots)
```

- The book is snapshotted **once per second at a random moment within the second.**
- A snapshot is **excluded** unless resting orders meet Target Size on **both**
  the yes and no sides.
- **Reference Price** = walk down from the best bid to the first level where
  cumulative resting size reaches **one fifth of Target Size**.
- Orders at or better than Reference Price get a 1.0x multiplier; worse ones are
  multiplied by `discount_factor ^ (ticks away)`. `discount_factor_bps = 5000`
  means **0.50 per tick** — a steep penalty, so only near-touch size scores.
- Raw score = `size * distance multiplier`, normalised per side, then your share
  across all participants.
- Rewards run **$1-$1,000 per market per day**, minimum payout $1.00. A verified
  SSN is needed for credits above IRS reporting thresholds.
- **You are paid even if your orders never fill.**

### Per-product fee differences that DO exist [API]

```
fee_type:   quadratic                        13,676
            quadratic_with_maker_fees           160   <- MAKERS PAY
            quadratic_with_combo_maker_fees       3   <- MAKERS PAY
```

**160 series charge makers.** They are Sports (107), Science & Tech (21),
Financials (13), Economics (10), Entertainment (7), Exotics (3), Crypto (2) —
including `KXATPMATCH` (tennis), `KXCPI`, `KXFED`, `KXBTCMAX125`. **All 26
fifteen-minute series are plain `quadratic`, so makers there pay nothing.**

**Half fees exist, on MLB.** 19 series carry `fee_multiplier = 0.5` **[API]**,
all `exchange_index = 3` ("Tennis & Baseball"), all `fee_type = "quadratic"`
(so no maker fee either): `KXMLBGAME`, `KXMLBF3`, `KXMLBF5`, `KXMLBF7`,
`KXMLBRFI` (run in first inning), `KXMLBEXTRAS`, `KXMLBHR`, `KXMLBKS`,
`KXMLBSPREAD`, `KXMLBTOTAL`, and 9 more. **Taker fee there is
`0.035 * p * (1-p)` — literally the half-fee lever `PLAN.md` wanted, on baseball
rather than equities.**

14 series carry `fee_multiplier = 0` (zero fees) but all are `one_off`/`annual`
political/crypto-EOY markets — useless at frequency.

**Fees can be overridden per event.** `GET /events/fee_changes` **[API]** returns
scheduled per-event overrides, e.g. `KXMLBGAME-26SEP082210CINLAD` scheduled to
`quadratic_with_maker_fees` at its game time. **Any strategy on those series must
re-read the override before quoting; the series-level field is not final.**

### Volume tiers: NO, not on the binary exchange

`/margin-rest/fees/get-fee-tiers` and `get-fee-tier-rates` exist **[DOC]** but
apply **only to Kalshi's margin/perps product**, not the event-contract exchange.
No volume-tiered taker discount is exposed for binaries. Volume tiers on the
prediction exchange gate **API rate limits**, not fees
(`Basic / Advanced / Expert / Premier / Paragon / Prime / Prestige`) **[DOC]**.

### The rounding fee — an unmodelled cost that lands on small orders [DOC]

`docs.kalshi.com/getting_started/fee_rounding.md`. This is not in the repo's
model and it matters at the operator's size.

- **Trade fee** = model fee rounded up to `$0.000001` (**not** to the cent —
  every third-party "ceil to next cent" source is wrong for the current API).
- **Rounding fee**: your balance must land on a grid — **`$0.01` for non-direct
  (FCM-cleared) members, `$0.0001` for direct members.** The shortfall is charged.
- **Rebate**: overpayment accumulates **per order across its fills** and is
  refunded in grid increments.

Kalshi's own worked example: a 1-contract buy at 5.5c with a model fee of
$0.0036 is charged **$0.005 total** — a **37% fee uplift** purely from rounding.

**`research/engine.py` `fee_per_contract()` is documented as the "large-order
limit" and omits this.** Consequences:

- Expected rounding cost is **~$0.005 per order**, not per contract. At 50
  contracts/order that is 0.01c/contract (ignorable). **At 1 contract/order it is
  0.5c/contract**, which is ~20% of pin's +2.54c edge and **larger than the entire
  measured maker edge of +0.48c/fill.**
- **A free fix [INFERENCE, from the documented mechanics]:** in the 10c-90c band
  the tick is 1c, so `price * size` is always a whole number of cents and a
  **maker** (zero model fee) incurs **zero** rounding fee at any size. In the
  deci-cent bands (<10c, >90c) the tick is 0.1c, so quote in **multiples of 10
  contracts** and the rounding fee is again exactly zero.
- **Becoming a "direct member" cuts the rounding grid 100x** ($0.01 -> $0.0001).
  Worth asking Kalshi what that requires — it is a pure cost reduction.

---

## 3. EVERYTHING THAT RESOLVES IN <= 30 MINUTES

Method: full series census (`/series`, **13,839 series** **[API]**) plus
`/markets?status=open&min_close_ts&max_close_ts` for the next 35 minutes, then
market lifetime = `close_time - open_time`. Not a ticker-substring scan.

### The true 15-minute universe is 26 series, not 14 and not 16 [API]

`frequency = "fifteen_min"` -> **26**. All are `fee_type=quadratic`,
`fee_multiplier=1` — **identical fees, no cheaper product among them.**

| series | cat | markets? | median volume/market | note |
|---|---|---|---|---|
| **KXBTC15M** | Crypto | live | **2,102,717** | most liquid 15M market |
| **KXGOLD15M** | Commod | **live** | **221,228** | **2.3x ETH15M. Not recorded.** |
| KXETH15M | Crypto | live | 96,209 | |
| **KXWTI15M** | Commod | **live** | **51,118** | not recorded |
| KXXRP15M | Crypto | live | 50,099 | |
| **KXSILVER15M** | Commod | **live** | **46,088** | not recorded |
| KXSOL15M | Crypto | live | 43,383 | |
| **KXCOPPER15M** | Commod | **live** | **11,081** | not recorded |
| **KXNATGAS15M** | Commod | **live** | **9,470** | not recorded |
| KXCRYPTOLEAD15M | Crypto | live | 188 | thin, **but LIP-paid** |
| KXDOGE15M, KXBNB15M, KXHYPE15M, KXNEAR15M, KXZEC15M | Crypto | live | — | recorded |
| KXINX15M, KXNDQ15M, KXGBPUSD15M, KXUSDJPY15M, KXPLATINUM15M, KXPALLADIUM15M, KXADA15M, KXBCH15M, KXTON15M, KXCRYPTOCOMP15M, KXGBPUSD15MTEST | mixed | **zero markets** | — | registered, unlisted |

(Volume is `volume_fp`, a fixed-point contract count; medians over the last 300
settled markets per series. Relative magnitudes are what matter.)

**`KXGOLD15M` is the second most liquid 15-minute market on Kalshi and this
project has never recorded a byte of it.**

### Commodity 15M settlement is NOT an average — pin does not transfer

**[API]**, live `rules_primary` on `KXGOLD15M-26SEP050000-00`:

> "If the close price of the 1-minute candlestick for Gold on Sep 5, 2026 at
> 12:00 AM EDT is at least the close price of the 1-minute Pyth GOLD candlestick
> at 11:45 PM EDT on September 4, 2026 ... then the market resolves to Yes."

Source agency is **Pyth**, one per commodity. Strike = 1-minute candle close at
T-15min; settle = 1-minute candle close at T. **A single point, not a mean of 60
prints.** So `Var(settle-strike)` does **not** collapse as tau -> 0, and
**pin's entire edge mechanism is absent here.** Do not port pin to gold expecting
the same numbers.

What *does* port unchanged: fees, the maker-pays-nothing structure, the tapered
tick, and the at-touch market-making shape — none of which depend on the
settlement mechanism.

Also **[API vs DOC contradiction]**: `COMMOD15M.pdf` says *"Minimum Tick ...
$0.01"*, but the live market object says `price_level_structure:
"tapered_deci_cent"` with 0.001 steps below 0.10 and above 0.90. **Trust the API.**
`Position Accountability Level: $25,000 per strike per Member` **[DOC]** — far
above the operator's size, not a constraint.

### Everything else open with <= 30 min to resolution, right now [API]

Snapshot at 2026-09-06 11:38 UTC (Sunday — equities and commodities shut):

| series | lifetime | ttl | vol24h | spread | verdict |
|---|---|---|---|---|---|
| crypto 15M (9 live) | 15.0 min | 5.7 min | BTC 76,385 / ETH 5,394 / XRP 2,592 | **1c** | the known ground |
| `KXCRYPTOLEAD15M` | 15.0 min | 5.7 min | thin | 2c-8c | **LIP-paid** |
| `KXMVECROSSCATEGORY` | **22.8 min** | 20.7 min | **0** | 0/0 | **dead.** `exchange_index=1` (Combos), `quadratic_with_combo_maker_fees` — makers pay. Ignore. |
| hourly crypto ladders (`KXBTC`,`KXBTCD`,`KXETH`,`KXETHD`,`KXSOL*`,`KXXRP*`,`KXHYPE*`,`KXBNB*`,`KXDOGE*`) | 60 min | **20.7 min** | thin | 1c at touch | 188-300 strikes/event. Spends its **last 30 min** inside the <=30-min bracket. |
| `KXTEMP{NYC,MIA,LAX,DC,CHI,AUS}H` hourly temperature | 60 min | 20.7 min | MIA 436, DC 15, rest ~0 | **10c** (MIA 0.13/0.23) | 10 strikes/city. Spread far too wide. |

`frequency` census **[API]**: `fifteen_min` 26, `hourly` 65, `daily` 279,
`weekly` 294, `monthly` 356, `quarterly` 3, `annual` 1,476, `custom` 5,710,
`one_off` 5,630. **Nothing exists between `fifteen_min` and `hourly`.** 15
minutes is the floor on Kalshi.

**Sports in-play** is `frequency="custom"` so cadence is not readable from the
field. The half-fee MLB set (`KXMLBRFI` run-in-first-inning, `KXMLBF3` first
three innings) resolves inside 30 minutes of first pitch **[INFERENCE — I did not
measure their actual open->settle times; none were open on a Sunday morning]**.
That is the one genuinely cheaper product found and it is **unmeasured**.

---

## 4. KXCRYPTOCOMP15M AND THE THREE DEAD CRYPTO SERIES — RESOLVED

**The tickers are all correct. The products simply have no markets.** **[API]**

| series | `/series/<t>` | markets (any status) | arriving on tape |
|---|---|---|---|
| `KXCRYPTOCOMP15M` | **200 OK** — "Crypto Comparison 15 minute" | **0** | no |
| `KXADA15M` | **200 OK** — "Cardano 15 Minute" | **0** | no |
| `KXBCH15M` | **200 OK** — "Bitcoin Cash 15 Minute" | **0** | no |
| `KXTON15M` | **200 OK** — "TON 15m" | **0** | no |

`research/newseries.py --data C:\kals\kalshi_data` **[TAPE]**, run this session:

```
asked for 14 series; 10 are arriving
*** 4 ASKED FOR AND NOT ARRIVING: KXADA15M, KXBCH15M, KXCRYPTOCOMP15M, KXTON15M
```

**The tape and the API agree exactly.** There is no ticker to fix and no
collector bug. `CLAUDE.md` line 149 and `HANDOFF.md`'s open item
*"Fix KXCRYPTOCOMP15M — the ticker is wrong or the series does not exist"* can be
**closed: the ticker is right, Kalshi has listed no markets.** Leaving them in
`CRYPTO_15M` is harmless — they cost nothing and will start recording by
themselves if Kalshi ever lists them.

---

## 5. SETTLEMENT LAG — MEASURED, AND IT IS NOT A CONSTRAINT

Nobody had checked this. Measured directly as `settlement_ts - close_time` over
the **last 500 settled markets per series** **[API]**:

| series | min | **p50** | p75 | p90 | p99 | frac >60s | frac >600s |
|---|---|---|---|---|---|---|---|
| KXBTC15M / ETH / XRP | 1.1s | **5.5s** | 11.2s | 21.2s | 55.5s | 0.8% | 0.4% |
| KXSOL15M | 1.1s | **5.5s** | 5.6s | 21.2s | 65.5s | 1.0% | 0.4% |
| commodity 15M (all 5) | 17.1s | **21.1s** | 25.5s | 25.5s | 341s | 1.6% | 0.6% |
| KXCRYPTOLEAD15M | 35.5s | **45.5s** | 65.5s | 335s | 575s | 26.0% | 0% |

**Crypto 15M capital comes back a median 5.5 seconds after close.** Commodity
21.1s. Both are trivial against a 15-minute cadence.

**Therefore settlement lag is NOT a capacity constraint at $1,000.** For `pin`
specifically it is not a constraint at all: pin enters at `tau <= 60s`, so the
capital it uses was released ~14 minutes earlier. **[INFERENCE]** The concern in
the job brief does not bind.

**Two real tail risks, both measured:**

1. **One exchange-wide 2-hour stall.** Exactly one window in each series' 500
   settled at **7,205s = 2h 0m 5s**, and it is the *same* window across all nine
   series — a single incident, not per-market noise. **~1 in 500 windows your
   whole book is frozen for two hours.** At $1,000 fully deployed that is a
   two-hour outage of 100% of capital.
2. **0.4-0.8% of windows take >10 minutes**, i.e. capital misses the next window
   entirely. Size for it: **do not plan on more than ~99% capital turnover.**

**Withdrawal (not settlement) is the slow leg [DOC]:** ACH withdrawals take
**3-5 business days**. Settlement credits the Kalshi balance in seconds; getting
money *out* is days. Irrelevant to recycling capital inside the platform, which
is what matters here.

*Caveat:* `settlement_ts` is the exchange's market-settlement timestamp. That
positions convert to spendable balance at that instant is **[INFERENCE]** from
`docs.kalshi.com/getting_started/market_settlement.md` ("Positions are
automatically resolved and funds transferred"). Confirming the balance is
*immediately re-usable* needs an authenticated `/portfolio` call, which is out of
scope here — but it needs no money, only the operator's key, and `GET /portfolio`
is read-only.

---

## 6. THE MONEY, RANKED BY RELIABILITY

### #1 — Liquidity Incentive Program on commodity 15M. Best risk-adjusted lead found.

**Why it is first: you are paid for posting depth, not for a forecast. The market
does not have to be wrong.**

Exact, measured **[API]**: `KXGOLD15M`, `KXSILVER15M`, `KXWTI15M`, `KXNATGAS15M`,
`KXCOPPER15M`. **$20.00 per market per 15-minute window. Target size 300
contracts. 24 windows/day per series**, at UTC `22:00-03:45` = **6:00 PM-11:45 PM
ET** — the US evening, when the operator is awake.

**Capital, in the units requested.** Quoting Target Size on both sides costs
`(yes_bid + no_bid) * size`, which is strictly **less than $1 * size** because the
spread is positive.

- **~$290 peak concurrent capital covers one market at full 300-contract target.**
- **$1,000 covers three of the five simultaneously (~$870 peak).**
- The 5 series run in the *same* 24 windows, so this is concurrent, not sequential.

**$ per contract per day.** The pool is $20 per market-window against 600 resting
contracts (300 each side) = **3.33c per resting contract per window** at 100%
share; **x 24 windows = $0.80 per resting contract per day, undiluted.** Divide by
your share.

**Return on capital, and I am giving the range because the share is unmeasured:**

| your share of pool | $/day on 3 markets | peak capital | **% return/day** |
|---|---|---|---|
| 100% (nobody else) | $1,440 | $870 | 165% — implausible |
| 25% | $360 | $870 | 41% |
| 10% | $144 | $870 | 17% |
| **5%** | **$72** | **$870** | **8.3%** |
| **1%** | **$14.40** | **$870** | **1.7%** |

**Even a 1% share beats pin's ~$33/day on a per-capital basis** (pin: $33/day on
$50-268 peak = 12-66%/day — comparable, but pin needs the market to be wrong and
this does not).

**What is NOT measured, and it is the whole question: my share.** The split is
`your score / all participants' scores`, and there is at least one incumbent —
live books on the incentivized `KXCRYPTOLEAD15M` markets show **1,001 and 1,121
contracts resting at the touch against a 1,000 target** **[API]**, which is a bot
sitting exactly on the number. I have not measured how many participants there are
on the commodity markets, nor what historical payouts actually were.

**The real risk is not the reward, it is the inventory.** You get filled, and
commodity 15M settles on a single Pyth candle close with no variance collapse to
protect you. The +0.48c/fill at-touch maker result was measured on **crypto** 15M
and does **not** automatically transfer. The $20 is Kalshi paying you to carry
exactly that risk.

### #2 — Coin Race LIP, on tape we already have

`KXCRYPTOLEAD15M`: **$20/market-window x 5 coins, ~52 event-windows/day,
~$5,200/day pool** **[API]**, and **`newseries.py` confirms it is already
recording** **[TAPE]**. But **Target Size is 1,000 contracts**, so covering both
sides of one market costs **~$950 — the operator's entire bankroll on a single
15-minute market.** Worse capital fit than the commodity set. Its value is that
**the scoring can be simulated offline today** (see Next Step).

### #3 — Half-fee MLB. Cheapest fees on Kalshi. Completely unmeasured.

19 series at `fee_multiplier = 0.5`, `fee_type = "quadratic"` **[API]** —
**`0.035 * p * (1-p)` taker, zero maker.** Half the fee of every crypto 15M
market. `KXMLBRFI` and `KXMLBF3` plausibly resolve inside 30 minutes
**[INFERENCE]**. Nothing about volume, spread or cadence measured. **Watch the
per-event override** — `/events/fee_changes` shows `KXMLBGAME` events being
flipped to `quadratic_with_maker_fees` at game time **[API]**.

### #4 — Free operational upgrades found in the docs [DOC], no analysis needed

- **A 5Hz CF Benchmarks feed exists** (`websockets/cfbenchmarks-value-5hz`). The
  collector subscribes to the 1/sec `cfbenchmarks_value`. **5x the index
  resolution** on the exact signal pin races against.
- **`cfbenchmarks_value` already carries "trailing 60-second and quarter-hour
  final-minute averages"** — Kalshi computes and broadcasts the settlement
  average itself. The project computes it from raw prints.
- **A Pyth value feed exists** (`websockets/pyth-value`) — first-party index for
  the commodity 15M markets, exactly as `cfbenchmarks_value` is for crypto.

**I did not change the collector.** `C:\kals\kalshi_collector.py` is the deployed
copy and collection is the operator's call.

---

## THE CHEAPEST NEXT STEP

**Simulate the LIP score offline against tape already on disk.** The collector
records `orderbook_snapshot` and `orderbook_delta` for `KXCRYPTOLEAD15M`
**[TAPE, confirmed by newseries.py this session]**. `flow.py`'s rebuilt book is
already replay-correct (seq-ordered, stale fills quarantined). The LIP rules are
now fully specified above: 1-second snapshots, Target Size 1,000 both sides,
Reference Price at one fifth of target, `0.50^ticks` distance decay.

So: **replay the recorded book, compute the exact LIP score of every resting
order, and answer "if I had rested N contracts at the touch, what share of the
$20 would I have won?"** That converts the single unmeasured number into a
measured one, using no new collection, no API calls, and no orders. It is the
whole difference between "the pool is $2,400/day" and "I make $X/day".

If that comes back positive, the second step is a **collector change to record
the five commodity 15M series** — which is the operator's call, and which is
where the better capital fit (target 300, not 1,000) actually lives.

---

## WHAT I COULD NOT DO

- **Did not measure my achievable LIP share.** Needs the offline replay above, or
  an authenticated `/portfolio` history, or a live test. This is the one number
  that turns #1 from a lead into a P&L.
- **Did not measure MLB in-play cadence, spread or volume.** No MLB markets were
  open on a Sunday morning; the half-fee claim is from the series object only.
- **Could not fetch `kalshi.com/docs/kalshi-fee-schedule.pdf`** — HTTP **429** from
  Kalshi's edge on every attempt, plain and browser-headered. The fee formula is
  instead confirmed arithmetically from the `docs.kalshi.com` fee_rounding worked
  example plus the API's `fee_type`/`fee_multiplier` fields, which is stronger than
  the PDF for per-series facts. Third-party fee blogs contradict each other and
  each other's rounding claims; none are used above.
- **`/incentive_programs` paging caps at 1,000 rows per status with no cursor**, so
  windows/day counts are lower bounds. Per-window figures ($20, target 300/1000)
  are exact and unaffected.
- **Did not verify that settled cash is instantly re-usable** — needs an
  authenticated read-only `/portfolio` call.

---

## RESOURCE STATE

- `kalshi_collector.py` (PID 2708908, 25.6 MB) — **ALIVE**
- `crypto_feeds.py` (PID 531268, 14.1 MB) — **ALIVE**
- Free RAM 3.7 GB, **free disk 52.1 GB**
- Nothing killed; no `*research*` process touched; no repo file modified.
- Total API calls this session: a few hundred read-only GETs. No order endpoint,
  no `/portfolio`.
