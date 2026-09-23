# C_options — every way KXDOGE15M-26SEP222245-45 could have been prevented or made smaller, with the price of each on OUR OWN LIVE FILLS

Close `2026-09-23T02:45:00Z` = **10:45 PM ET 09-22**. Kalshi's ledger: **−$2.4673**.

**Source of every dollar below: Kalshi's own settlement rows (`results/kalshi_ledger.json`)
joined to our own order records (`results/pinrun-live-*.jsonl`, 128 files).** No tape,
no replay, no simulator anywhere in this file. Match built independently of
`B_verify`: **1,263 entry orders, 812 filled, 514 of them paired to their own `signal`,
491 markets, 353 closes, +$481.17 on 31,428 contracts = +1.531c per contract, 14 losing
markets worth −$544.93.** (B_verify matched 513 fills / 490 markets / +$480.61 and
listed 10 losers; my join finds four more losing markets — `KXXRP15M-26SEP192345-45`
−$64.95, `KXHYPE15M-26SEP192345-45` −$43.92, `KXDOGE15M-26SEP160900-00` −$12.14,
`KXNEAR15M-26SEP160430-30` −$9.22 — and scores `KXDOGE15M-26SEP180015-15` as a +$4.36
winner. The two baselines agree to $0.56.)

**How a gate is priced.** A gate is applied to every matched entry leg. A market counts
as blocked only when **every** leg of it is refused, and then its whole ledger row is
removed — the hedge existed only because the entry did. Partial markets are counted
separately and reported. This makes each cost an **upper bound** in one direction (a
price gate would often still have bought a cheaper rung in the same market) and a
**lower bound** in the other (blocked budget does not reappear elsewhere — already
measured FALSE for this bot, `restart_bot.ps1` line ~300: in the last ten seconds we
already cannot fill our size, so there is nowhere for freed budget to go).

**Every threshold in this file was chosen after seeing these fills.** Each is a
hypothesis needing a pre-registered bar, and every "near-free" slice below has its sign
decided by one close — stated per row.

---

## 1. RANKED BY NET DOLLARS ON OUR LIVE RECORD

`+` = we would have MORE money; `−` = the option costs more than it saves.
"saves here" is what it does to this market's −$2.4673.

| # | option | net on our record | saves here | closes | blocks a hedge? | visible before entry? |
|---|---|---|---|---|---|---|
| 1 | **Insure at once when a fill lands ≥2c under the ask we saw** (= freeze bar **B3**) | **+$108 indicated, only +$1.76 priceable** | **+$1.76 (71%)** | 14 flagged | **no — it ADDS a hedge** | no (post-fill) |
| 2 | Refuse when the other coins are mid-rough (`cond_x` 0.8–1.1) | **+$3.40** | +$2.47 | 102 | no | yes |
| 3 | **Let a panic hedge pay any price under $1** (drop the 3c slip cap on a panic only) | **+$0.10 to +$0.41 here; +$21.7 in the pre-fix era** | +$0.10–0.41 | 1 event at 3c | **no — it only ADDS fills** | n/a (hedge) |
| 4 | Sell the position instead of hedging it | **$0.00 — arithmetic identity** | $0.00 | 22 | no | n/a |
| 5 | Refuse offers < 250 ms old | −$13.27 | **$0** | 181 | no | yes |
| 6 | **Price ceiling 97.5c on the ASK we see** (from 98.0c) | **−$13.48** | **+$2.47 (100%)** | 179 | no | yes |
| 7 | Cap dollars-at-risk at $80 a market | −$23.08 | $0 | 92 | no | yes |
| 8 | `max_per_market` 1 fill instead of 2 | −$30.86 | +$0.69 | 22 | no | yes |
| 9 | **Insure EVERY fill at the fill second** | **−$41.84 (−$51 corrected)** | +$1.76 | 19 | no | n/a |
| 10 | Price ceiling 97.0c on the ask | −$104.65 | +$2.47 | 232 | no | yes |
| 11 | `late_pin 0.9975` extended out to tau ≤ 12 | −$126.54 | +$2.47 | 41 | no | yes |
| 12 | Refuse when the model and market disagree (edge > 4c) | −$228.21 | $0 | 95 | no | yes |
| 13 | **Refuse when our confidence ROSE > 0.20 during the close** | **−$231.51** | +$2.47 | 84 | no | yes |
| 14 | **Refuse a market whose own model was under 0.70 earlier in the close** | **−$368.03** | +$2.47 | 164 | no | yes |
| 15 | **Minimum cushion z ≥ 3.0 sd at entry** | **−$414.06** | +$2.47 | 271 | no | yes |
| 16 | `--honest` as the confidence gate (z ≥ 4.32) | −$530 (B_verify) | +$2.47 | 352 | no | yes |
| 17 | Hedge on the market price instead of belief | **−$22.8 on the one record we have** | $0 | 1 | **YES — it already delayed one** | n/a |
| 18 | Zero-fill brake (order 2 filled 0 → do not send order 3) | untestable, **n = 4** | +$0.83 | 4 | no | yes |

**Nothing on this list both prevents this loss and pays for itself, except option 1,
which is already pre-registered and already collecting.** The two cheapest preventions
(rows 5 and 6) each cost about $13 over 179–181 closes and each hold 40–80% of all our
loss dollars — but each one's sign turns on a single close, so neither is a result yet.

---

## 2. PREVENTION CANDIDATES

### 2.1 A minimum cushion in sigmas at entry — the most expensive idea on the list, and the mechanism refutes it

The task's prompt: *"6 of 13 early losses sat under 3 sd."* On the fills joined to
Kalshi's money that is true and useless, because **so did most of the winners.**

| cushion floor | markets blocked | closes | contracts | net blocked | winners blocked | losers blocked |
|---|---|---|---|---|---|---|
| z ≥ 2.70 | 170 | 149 | 10,697 | **+$197.21** | 163 (+$330.25) | 7 (−$133.04) |
| z ≥ 2.80 | 236 | 198 | 15,032 | **+$263.81** | 228 (+$463.19) | 8 (−$199.38) |
| **z ≥ 3.00** | **327** | **271** | **21,168** | **+$414.06** | **318 (+$675.19)** | **9 (−$261.13)** |
| z ≥ 3.25 | 385 | 300 | 24,639 | +$414.47 | 374 (+$798.31) | 11 (−$383.84) |
| z ≥ 3.50 | 409 | 315 | 26,264 | +$320.07 | 396 (+$855.77) | 13 (−$535.71) |

Read the last row: a 3.5-sigma floor catches **13 of our 14 losing markets** and still
costs us **$320**, because it also refuses $856 of winners. There is no floor that pays.

**Why, mechanically:** the z of our 14 losing markets is 2.59, 2.60, 2.62, 2.62, 2.62,
2.66, 2.67, 2.73, 3.00, 3.15, 3.18, 3.26, 3.35 and **7.03**. A 7.03-sigma loss
(`KXNEAR15M-26SEP160430-30`, −$9.22) cannot be excluded by any cushion. This is the
same fact `pincalib.py` measured on 1,672 closes and `B_verify` §0 re-derived: the tail
is fat **everywhere**, so moving the bar moves the trade count, not the loss rate.
**REJECT.**

- Visible before entry: yes. Blocks a hedge: no. Blocks: entries at low cushion.
- Bar: none worth writing. The measurement above is the answer.

### 2.2 A cap on how far `fair` may move between tau 45 and entry — costs $231 to save $2.47

This market's own model said **0.6713** for NO at tau 45 (`refused`, gate `confidence`,
`fair 0.32867`) and **0.99559** at tau 12. That is a rise of **+0.324** in 33 seconds
with the price barely moving — the ruler shrank, not the world.

| rule | markets | closes | net blocked | winners | losers |
|---|---|---|---|---|---|
| refuse if confidence rose > 0.10 in this close | 125 | 117 | +$245.16 | 123 (+$309.38) | 2 (−$64.22) |
| **refuse if confidence rose > 0.20** | **89** | **84** | **+$231.51** | **88 (+$233.97)** | **1 (−$2.47)** |
| refuse if confidence rose > 0.30 | 76 | 71 | +$210.39 | 75 (+$212.86) | 1 (−$2.47) |
| refuse if confidence rose > 0.40 | 62 | 58 | +$177.62 | 62 (+$177.62) | 0 |

**The "confidence jumped during the close" population is 89 markets and 88 of them
won.** The one loser is this market. It costs **$231.51 to save $2.47 — 94:1.**
A rising confidence is not a warning sign, it is the edge itself: the variance collapse
IS confidence rising while nothing moves. **REJECT.**

### 2.3 Refusing a market whose own model was a coin flip 30 s earlier — costs $368

| rule | markets | closes | net blocked | winners | losers |
|---|---|---|---|---|---|
| **refuse if our model was < 0.70 for this side earlier in the close** | 180 | 164 | **+$368.03** | 177 (+$448.98) | 3 (−$80.95) |
| refuse if < 0.80 | 197 | 176 | +$399.97 | 194 (+$480.92) | 3 (−$80.95) |
| refuse if < 0.90 | 235 | 207 | +$422.08 | 231 (+$564.79) | 4 (−$142.70) |

Same mechanism as 2.2 and the same verdict. Note the direction: the stricter the rule,
the MORE money it costs. **REJECT.**

### 2.4 A price ceiling on the ASK, 97.5c — the only prevention that is nearly free, and the only one that stops this market

**This is the one option that would have produced a $0.00 outcome here.** Both filling
orders saw an ask of **98.0c** (order 1 filled at 93.4c, order 3 at 7.1c); the deployed
`price_ceiling 0.98` let them through and refused a third at 98.1c. A 97.5c ceiling
refuses both, and order 2 (ask 93.4c) filled nothing anyway. **Market = $0.00.**

The whole record, cut on the ask we SEE (which is what a gate can read; the price we
PAY is only known afterwards):

| ask we saw | markets | closes | contracts | lost | net | per contract |
|---|---|---|---|---|---|---|
| 96.0–97.0c | 76 | 72 | 4,707 | **0** | +$141.80 | **+3.012c** |
| 97.0–97.5c | 75 | 71 | 4,880 | 1 | +$81.47 | +1.670c |
| **97.5–98.0c** | **204** | **179** | **11,844** | **6** | **+$13.48** | **+0.114c** |
| everything else | 287 | — | 19,584 | 8 | +$467.69 | +2.388c |

**38% of every contract we have ever bought was bought on an ask above 97.5c. Those
11,844 contracts tied up $11,509 of capital and returned $13.48 — a tenth of a cent
each — and they hold 6 of our 14 losing markets, worth −$215.85.**

- Resampled chance that slice even made money: **0.584** — a coin flip on its own sign.
- Its worst close, `26SEP191600` (−$107.95), is **50% of all the loss in the slice**.
  Remove that one close and the slice nets +$121.43.
- So: **the cost of adopting this is −$13.48 and the arithmetic is a near-tie, not a win.**
  What it buys is variance: 40% of our loss dollars, for a tenth of a cent a contract.
- Prior art, do not re-litigate: this was examined on 2026-09-18 for the 45-second leg
  only (`--early-max-price`) and rejected because *"the blocked budget would flow to the
  5.6c last-ten-seconds window... measured FALSE"*. That argument is about **making
  more** and it still holds. The number above is about **losing less**, which is a
  different question and was not the one answered then.
- **A ceiling change cannot be shipped by flag today.** `--price-ceiling 0.99` took the
  live bot down for four minutes on 2026-09-18 because four older self-tests assert the
  98c ceiling against the RUNNING value (`v-ceiling99`). Those must be rewritten first.
- Visible before entry: **yes**. Blocks a hedge: **no** — it is an entry price test and
  touches no hedge path.
- **Bar (paper arm, during the freeze):** run `--early-max-price 0.975` and a second arm
  with a whole-book 97.5c ceiling beside live, both synced by `sync_arms.ps1`. Register
  before reading: **PASS only if the arm is ahead of live by ≥ $0.25 a close over 200
  closes with resampled P ≥ 0.90 AND no single close is > 50% of the gain.** On this
  record the honest expectation is a small LOSS, so the arm is really there to measure
  whether the loss-dollar reduction is real out of sample. Blocks: entries only.

### 2.5 A price-through rule at entry — there was nothing to act on

This market's price-through happened on the FILL, not the order: both filling orders
sent a limit exactly equal to the ask they saw (`sweep_headroom_c 0.0`). Only order 2 —
the one that filled nothing — carried headroom (4.6c). **A no-price-through entry rule
changes nothing here.** It becomes a hedge trigger instead: §4.1.

### 2.6 A tighter freshness rule — real signal, does not catch this market

| rule | markets | closes | contracts | net blocked | winners | losers |
|---|---|---|---|---|---|---|
| refuse levels < 250 ms old | 207 | 181 | 12,502 | **+$13.27** | 198 (+$454.83) | **9 (−$441.56)** |
| refuse levels < 150 ms old | 182 | 161 | 10,742 | **−$68.94** | 174 (+$372.15) | 8 (−$441.09) |
| refuse levels < 50 ms old | 102 | 96 | 5,732 | +$108.50 | 99 (+$226.58) | 3 (−$118.08) |

**9 of our 14 losing markets — 81% of all loss dollars — were bought on offers under
250 ms old, and refusing all of them costs $13.27.** Its sign also turns on one close
(remove `26SEP192345` and the slice nets +$122.13; resampled P 0.550).

**It does not block this market.** Order 3's level was 38 ms old, but order 1's age was
`866790 ms, level_age_exact false` — the "we never saw this level appear" reading — so
under any honest implementation order 1 passes and we still hold the 2-lot (−$1.78).

This is already **freeze bar B2**, on the 45-second leg, out of sample, with its own
power statement (needs ~570 closes, past the freeze). Do not re-cut it. **The new thing
worth adding is one line of logging:** B2 cannot class a level whose age is a lower
bound, and that is exactly the leg that lost here.

### 2.7 `late_pin 0.9975` extended out to tau ≤ 12 — costs $126.54

| rule | markets | closes | net blocked | winners | losers |
|---|---|---|---|---|---|
| **require 0.9975 at tau ≤ 12** (live: tau ≤ 10) | 43 | 41 | **+$126.54** | 41 (+$130.11) | 2 (−$3.56) |
| require 0.9975 at tau ≤ 11 | 37 | 35 | +$112.02 | 36 (+$113.11) | 1 (−$1.10) |

Refuses this trade outright (confidence 0.99559 < 0.9975). **Costs $126.54 to save
$2.47.** B_verify priced a plain "refuse tau ≤ 12" at +$76.16; mine is the
confidence-conditional version and is more expensive. Same verdict. **REJECT.**

### 2.8 Refusing when the model and the market disagree — costs $228, and it is backwards

We crossed a 6.6c YES bid, so the market said 6.6% where the model said 0.441% — 15x.
A gate on that is arithmetically a gate on our edge: `edge_c` here was **5.728c, the
single best-looking opportunity of the whole close** (`close_summary.best_ticker` = ours).

| rule | markets | closes | net blocked | winners | losers |
|---|---|---|---|---|---|
| refuse edge > 3c | 147 | 135 | +$266.95 | 140 (+$552.12) | 7 (−$285.16) |
| refuse edge > 4c | 102 | 95 | +$228.21 | 96 (+$454.28) | 6 (−$226.07) |
| refuse edge > 5c | 70 | 68 | +$152.98 | 65 (+$349.15) | 5 (−$196.17) |

Note it does NOT block this market at the 4c or 5c setting under my "all legs" rule —
orders 1 and 3 carried `edge_c 1.422`; only the zero-filling order 2 had 5.728c.
**REJECT.**

### 2.9 The cross-coin roughness we already log and never gate — the only prevention with a positive sign

`pinrun` records `cond_x` (the OTHER ten coins' mean roughness, this coin excluded by
construction) on every signal and **deliberately does not gate on it**, because
`pintail.py` found every fixed threshold failed out of sample. This trade carried
`cond_x 0.8402, cond_n 1, cond_own 0.6391`.

| other coins' mean roughness | markets | closes | lost | net | per contract |
|---|---|---|---|---|---|
| 0.0–0.5 | 44 | — | 0 | +$100.53 | — |
| 0.5–0.8 | 246 | — | 7 | +$277.24 | — |
| **0.8–1.1 (this trade)** | **119** | **102** | **6** | **−$3.40** | **−0.046c** |
| 1.1+ | 52 | — | 1 | +$46.93 | — |

Refusing the 0.8–1.1 band would have made us **$3.40 richer** and avoided **6 of 14
losing markets (−$221.01)**, over 102 closes. Resampled P(the band made money) =
**0.521** — a coin flip; its worst close (−$59.09) is the whole sign.

**This is the only prevention on the list that does not cost money, and it is exactly
the kind of slice this repo has been burned by before.** Treat as a hypothesis.
**Bar (logging only, no trading change):** `cond_x` is already on every signal. Register
now, before more data: over the next 150 closes, does the 0.8–1.1 band's per-contract
return stay below the rest by ≥ 1.0c with resampled P ≥ 0.90 and no single close > 50%
of the gap? Nothing trades on it until that passes. Blocks: nothing, it is a log.

---

## 3. SIZE CANDIDATES — was 13 of 82 luck, or the depth taper?

**Luck, and the base rate is not rare.** Across every entry order we have ever sent:

| | |
|---|---|
| entry orders | 1,263 |
| contracts asked | 51,363 |
| contracts filled | 37,613 = **73.2%** |
| orders that filled **nothing** | **451 = 35.7%** |
| orders that filled partially | 90 = 7.1% |
| orders that filled in full | 722 = 57.2% |
| orders asking ≥ 40 contracts | 489, of which **73 (14.9%) filled nothing**; mean fill share 81.6% |

Order 2 asked 82 and got 0. That is not this event — it is the routine zero fill, and
B_verify's exchange clocks put its round trip 140 ms before the move even started.
**So the honest statement is: this market pays about −$77 roughly two times in three,
and we drew the other one.** Nothing in the sizing changed that.

The taper did the opposite of protecting us: `taper` capped a 6,195-contract flat ladder
at `size_now` 82, and `sweep_depth` then raised the ask from 62.4 to **82**.

### 3.1 Cap dollars-at-risk per market

| cap | markets touched | closes | net change | winners trimmed |
|---|---|---|---|---|
| $20 | 436 | 322 | **−$307.99** | 424 |
| $40 | 362 | 278 | −$167.96 | 351 |
| $60 | 282 | 223 | −$79.79 | 274 |
| **$80** | **109** | **92** | **−$23.08** | 104 |
| $100 | 41 | 39 | −$16.56 | 39 |

Every cap costs money, because our losing markets are 14 of 491. A $80 cap would have
cut the worst single market (−$107.95 on $107.80 of capital) to about −$80 and cost
$23.08 net. **It does nothing here — this market risked $2.65.** REJECT as an earner;
it is a drawdown control, and the operator already chose that trade-off once
(`--bank-brake 4.00`, "divide by 8", 2026-09-18).

### 3.2 `max_per_market` 1 fill instead of 2

Order 3 was our second fill. With a one-fill cap we hold 2 contracts: **−187.67c +
9.80c = −$1.78, saving $0.69.** Across the record it touches 23 markets / 22 closes and
costs **−$30.86** (pro-rated by contracts). **REJECT**, but note the shape: the second
fill is worth about $1.34 a market on average and cost us $0.83 here.

---

## 4. HEDGE CANDIDATES

### 4.1 Insure at once when a fill lands ≥ 2c under the ask we saw — the best option on the list, and it is already pre-registered as freeze bar B3

**Both of this market's filling orders are in that population:** order 1 filled at 93.4c
against a 98.0c ask (**4.6c through**) and order 3 at 7.1c against a 98.0c ask (**90.9c
through**). A fill far under the ask we saw means our cached book was wrong — the only
hard, same-second evidence we had.

What it is worth **here**, priced from our own `hedge_quote` records:

| | |
|---|---|
| tau 12, order 1 fills 2 @ 93.4c | same-second YES ask **6.7c, size 86.8** |
| insure 2 contracts there | 93.4c + 6.7c + 0.88c fees = 100.98c for a certain 100c = **−0.98c locked** |
| the 2-lot then costs | −1.95c instead of −177.87c |
| **market total** | **−$0.708 instead of −$2.4673 → saves $1.76, 71% of the loss** |

**A warning about B3's own valuation rule, for whoever runs `barcheck`.** B3 prices
insurance at "the quoted ask in the fill's second". For order 3 that quote is
**6.6c at tau 11 — and it is stale.** Our own fill in that same second sold YES at
92.9c, which proves the YES side had already repriced. Scored B3's way this market
credits **+$9.39** on the 11-lot and turns a −$2.47 loss into a profit. **That is
fiction.** The rule needs one line: *a quote is not usable if our own fill in the same
second executed on the other side of it.* Without it, B3 will pass on invented money.

Over the whole live record the flagged population is:

| | markets | closes | contracts | lost | net |
|---|---|---|---|---|---|
| fill ≥ 2c under the ask seen | **15** | **14** | 1,013 | **5 (33.3%)** | **−$119.70** |
| every other market | 476 | — | — | 9 (1.89%) | +$600.86 |

Resampled chance that the flagged population made money: **0.091**. Its members:
−$59.09 NEAR, −$57.76 BNB, −$43.92 HYPE, −$27.87 BTC, −$2.47 DOGE, then eleven winners
totalling +$71.42.

**Indicated value ≈ +$108** (insurance locks about −1.2c a contract, so 1,013 contracts
cost about −$12 instead of −$119.70). **I cannot price 14 of the 15**: `hedge_quote`
only exists from 2026-09-22T11:52:44Z, so the YES ask at those fills is not in our logs
and no other source is admissible for our own money. That is precisely why B3 samples
20 flagged closes.

- Blocks a hedge: **no — it only adds one**, and B3 already forbids it from using the
  belief hedge's retry budget.
- Visible before entry: **no**, and that is the point: B_verify's exchange clocks show
  the move began 61 ms AFTER we committed, so the fill is the earliest honest signal.
- **Bar: B3 as written, plus the stale-quote rule above.** ~2.1 flagged closes a day, so
  ~9–10 days.

### 4.2 A faster or different belief trigger — worth exactly nothing here

The belief was **0.99867** on one pass of tau 10 and **0.05143** on the next pass of the
same second. **Any threshold from 0.05 to 0.9956 fires at the identical instant.**
The live 0.25 and the 0.40 panic line cost nothing. Confirmed independently.

The insurance price by the second it fires:

| trigger second | market total |
|---|---|
| tau 12 (YES ask 6.7c, 86.8 offered) | **−$0.71** |
| tau 11 (6.6c, 29.0 offered) | −$0.71 |
| **tau 10 — what happened** | **−$2.4673** |
| tau 9 | −$2.55 |
| never | −$2.71 |

**Perfect belief timing was worth $1.76, all of it on the 2-lot** — and there was no
belief line that reached it, because belief only moved when the price did.

### 4.3 Hedging on the MARKET PRICE instead of belief — this one can block a hedge, and it already has

Measured on every held position with per-second quote records (28 markets): **exactly
one ever saw the YES ask cross 50c, and it was the same second the belief collapsed.**
Zero seconds of lead, n = 28.

Worse, we have a live record of a price condition **delaying** a hedge.
`KXBNB15M-26SEP190145-45`, 2026-09-19, a −$57.76 market:

```
tau 23  hedge_alarm  belief 0.22714
tau 23  hedge_wait_price  ask 0.21  our_price 0.79  threshold 0.6   <- the hedge did not go
tau 21  hedge  ask 0.51  asked 7.0   -> filled 0
tau 20  hedge  ask 0.70  asked 76.0  -> filled 0      (96 contracts were offered)
tau 19  hedge  ask 0.76  asked 25.0  -> filled 1
tau 18  hedge_gave_up  tries 5
```

Insurance on 76 contracts cost **21c** when the price filter refused it and **76c**
three seconds later. **The delay is worth about −$22.8 on that market alone**
(76 × 30c of price it gave up between the wait and the first real attempt).
`--hedge-price` is **not** currently passed (`CURRENT_STATE.md`). **Do not re-enable
it.** This is the memory rule "a gate must never block a hedge" with a price on it.

### 4.4 Let a panic hedge pay any price under $1 — a cap being removed, not a gate being added

**A hedge that fills nothing is our most expensive failure mode, and it has happened 10
times in 37 attempts.**

| era | hedge attempts | markets | filled nothing |
|---|---|---|---|
| before `--hedge-slip 0.03` (limit = the ask we saw) — to 2026-09-19T22:50:22Z | 29 | 14 | **9 (31%)** |
| after `--hedge-slip 0.03` | 8 | 5 | **1 (12%)** — this market |

The pre-fix cases, with the money beside them:

| market | ledger | what happened |
|---|---|---|
| `KXBNB15M-26SEP190145-45` | **−$57.76** | asked 76 at a 70c ask with **96 offered → 0 filled**; ended with 1 contract of 76 hedged |
| `KXBTC15M-26SEP172115-15` | −$27.87 | asked 99 at 63c → 0; at 66c (7,419 offered) → 0; filled 99 at 72c. **9c × 99 = $8.91** |
| `KXBNB15M-26SEP191230-30` | −$61.75 | a 1.7-contract leg filled 0 at 57c, 62c and 77c against 60 offered |

The ask on those markets moved **15–19.5c in a single second**. `v-hedgefill` (the 3c
slip) fixed the worst of it. **This market shows the remaining gap: the ask went
0.949 → 0.980, 3.1c, just past the 3c cap, so the 11-lot's hedge filled 0 and paid
98.6c one second later instead of the 94.9c on screen** — costing $0.10–0.41 (only 1
contract was actually offered at 94.9c, so the realistic figure is nearer $0.10).

`hedge_panic` already bypasses `hedge_price`, `hedge_normal` and `attempt_cap`. **It
does not bypass the slip cap.** Making it do so is a cap being removed — it can only
ever add a fill, never block or delay one.

- **Bar (logging first, then a one-line safety change):** count every hedge attempt that
  fills 0 and the ask one second later, across live runs. Register: if the mean cost of
  a zero-filled panic attempt over the next 10 events exceeds 2c a contract, let panic
  price at 0.999. n after the 3c fix is **1** — this is the honest reason to log before
  changing anything.
- Also from B_verify §3, still standing: `hedge_last_try` blocks a retry for the rest of
  the wall-clock second **even after a fill of zero**. Here that was 656 ms with
  `hedge_max_tries 30` and 9 seconds left. Lifting the block *after a zero fill* removes
  a delay.

### 4.5 A standing cheap protective leg bought at entry — measured on our own fills, it is a shutdown

Priced leg by leg from our own same-second `hedge_quote` (the whole window in which such
a quote exists, 2026-09-22T11:52:44Z onward):

| | |
|---|---|
| markets / closes / legs | **24 / 19 / 29** |
| contracts held on those legs | 1,142, of which **884 coverable** at the quoted size |
| **ACTUAL** on those legs | **+$40.68 = +3.562c a contract** |
| **IF INSURED at the fill second** | **−$1.16 = −0.102c a contract** |
| difference | **−$41.84** |
| legs where insuring was worse | **27 of 29** |

The two legs where it "helped" are this market's, and one of them is the stale 6.6c
quote from §4.1 — scored honestly the total is nearer **−$10.7, a cost of about $51.**

**Why it can never work: buying NO at p and YES at about (100−p) is buying a certain
100c for 100c plus two taker fees.** Here: 93.4c + 6.7c + 0.88c of fees = 100.98c for a
guaranteed 100c — **−0.98c locked, every time**, against **+1.531c a contract actually
realised across 31,428 contracts**. Blanket insurance hands back **64% of everything we
earn** and it is the fee, not the spread, that does it (the two sides were only 0.1c
apart). REJECT — and note this is the one number in `A_autopsy.md` that could have moved
live code the wrong way; B_verify caught it and this measurement, on our own money,
agrees.

### 4.6 Selling instead of hedging — identical to the cent, with one unmeasured exception

On a Kalshi binary, **selling the NO you hold and buying the YES against it are the same
trade.** Selling 13 NO into the NO bid at 6.6c is executing against the same resting
orders as buying 13 YES at a 93.4c ask — same ladder, same depth (the NO bid ladder is
the YES ask ladder mirrored), and the same fee, because the fee is `0.07·n·p·(1−p)` and
`p(1−p)` is symmetric: buying YES at 98.6c and selling NO at 1.4c both pay
**0.097c a contract.** Net effect here: **$0.00.** Selling does free the cash a second
earlier (`budget_left` was 233 after this trade), which is a budget point, not a P&L one.

**The one thing I could not settle, and it is worth settling:** whether Kalshi charges
the same taker fee to CLOSE a position as to open the opposite one. **We have never sold
a position, so our logs cannot answer it.** If closing is cheaper, selling beats hedging
by up to 0.9c a contract on every hedge — worth about **$8.63** over the 959 hedge
contracts across our 22 two-sided markets. Small, but it is free money and one demo
order would establish it.

### 4.7 The 11-lot could not be insured in any material way

We bought NO at 7.1c, which means we sold YES into a 92.9c bid: "NO costs 7.1c" and
"YES insurance costs ~93c" are the same fact. Max loss on the leg 83.18c; best reachable
recovery about +24.8c (1 @ 93.4c + 10 @ 98.0c, B_verify's depth bound) against +14.33c
achieved. **About 10c of headroom on an 83c leg.** The hedge as executed recovered
24.13c of 270.82c at risk — **8.9%** — and the ceiling on that number was set by depth
one second after the flip, not by our trigger.

---

## 5. WHERE THE HONEST ANSWER IS "COST OF DOING BUSINESS"

**This was a cheap, correctly-sized, positive-expectation loss, and it is the cheapest
of our 14 losing markets.**

| | |
|---|---|
| capital at risk | **$2.65** (13 contracts at an average of 20.38c) |
| our 13 other losing markets | 32–110 contracts at 53–98c, **$29.54 to $107.80** at risk |
| the day it sat in | **+$52.89 before this settle, +$50.42 after** |
| the whole record around it | +$481.17 over 491 markets / 353 closes |

Three of the four things that kept it cheap were **design and worked**:
`price_ceiling 0.98` refused a 27-lot at 98.1c (about **$26.1** not lost),
`max_per_market 2` closed the market after two fills, and the IOC-at-limit order style
is what turned a mid-flip book into **90.9c a contract of price improvement, $10.00**.
The fourth was the routine 35.7% zero fill, which is **luck we win about two times in
three against us**, worth about **$74**.

The entry itself was right under every calibration we own. B_verify priced all 513 of
our matched fills through the repo's measured tail: **not one was negative-expectation**
(Gaussian +3.445c, honest +2.450c, realised +1.688c a contract). This one, at 93.4c with
a 2.62-sigma cushion, was **+4.5c a contract of honest expectation**. It lost by
**9.8 parts per million of a dollar** — 0.96 basis points — on a single index print that
arrived **61 ms after we had already committed**.

**What that means for the money: the strategy pays about 1.5c a contract and this loss
cost 20.4c a contract on 13 contracts. We need roughly 13 winning contracts to pay for
it. We buy about 90 a close.** The only two levers that matter are the ones in §4.1 and
§4.4 — both of which ADD a hedge and neither of which can block one.

---

## 6. COULD NOT MEASURE

- **What insurance cost at 14 of the 15 price-through fills.** `hedge_quote` starts
  2026-09-22T11:52:44Z; the YES ask at those earlier fills is in no admissible source.
  The +$108 in row 1 of the ranking is therefore **indicated, not measured**.
- **Whether a wider panic slip would have filled.** n = 1 event since the 3c cap went in.
  Only 1 contract was offered at the price on screen, so even the $0.41 is an upper bound.
- **Whether any of the three near-free filters (§2.4, §2.6, §2.9) is real.** Each one's
  sign is decided by a single close (resampled P 0.52–0.58) and every threshold was
  picked after seeing these fills.
- **Whether Kalshi's fee differs for closing a position.** We have never sold one.
- **The Kalshi book between 02:44:49.046 and .221.** All four market channels stop at
  02:31:5xZ; our own fill price is the only witness.
- **How much of the $13.48 / $13.27 cost is real.** Blocking an ask does not always lose
  the market: a cheaper rung often existed in the same close, so both figures overstate
  the cost, by an amount I cannot bound from the logs.

---

## 7. WHAT I WOULD DO, IN ORDER

1. **Add the stale-quote rule to B3 before it decides anything** (§4.1). One line; it is
   the difference between B3 reading −$2.47 and reading +$9.39 on this market.
2. **Log, don't gate: zero-filled panic hedges and their one-second price move**
   (§4.4). The only change that could ever be made here removes a cap.
3. **Register the `cond_x` band as a logging bar** (§2.9). It is the only prevention with
   a positive sign and the repo has already been burned once by exactly this kind of cut.
4. **A paper arm at `--early-max-price 0.975`** (§2.4), knowing the honest expectation is
   a small loss and what is being bought is 40% of our loss dollars.
5. **Leave the entry gate alone.** Every cushion, confidence-move, coin-flip-earlier,
   edge-cap and late-tau rule above costs between $126 and $530 to save $2.47.

---

## Housekeeping

Read-only throughout. No process started, stopped or signalled. Nothing written outside
this file and
`C:\Users\Joe\AppData\Local\Temp\claude\C--kals-repo\47b37ac1-655c-4d72-a81b-a48e9625d5bd\scratchpad\doge2245\design\`.

**Collectors alive** — `kalshi_data/cfbenchmarks_value/20260923T04.jsonl.gz` written at
**04:24:02Z** and `feed_data/coinbase/20260923T04.jsonl.gz` at **04:24:05Z**, against a
wall clock of 04:24:05Z. **Free RAM 3.12 GB. Free disk 23.39 GB** (guard 6 GB).
Peak python footprint: the whole job holds 1,263 order dicts and 491 market rows — far
under 400 MB. No tape hour was opened by this job; every number here comes from
`results/kalshi_ledger.json` and `results/pinrun-live-*.jsonl`.
