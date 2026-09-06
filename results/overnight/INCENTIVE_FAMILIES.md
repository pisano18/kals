# JOB 2 — The incentive families nobody has looked at

Run 2026-09-06, 16:57–18:30 UTC. Authenticated GET only. No orders placed.
Account balance confirmed $0.0047 (unfunded).

---

## HEADLINE — the brief's premise is inverted

The brief said KXDIESELD pays "$140 PER PERIOD ... SEVEN TIMES the crypto rate."

**$140 is real, but the period is 17.95 HOURS, not 15 minutes.**

| family | pool/period | period length | **$/hour/market** |
|---|---|---|---|
| KXCRYPTOLEAD15M | $20 | 15 min | **$80.00** |
| KXSILVER/GOLD/WTI/NATGAS/COPPER 15M | $20 | 15 min | **$80.00** |
| KXDIESELD | $140 | 17.95 h | **$7.80** |
| KXAAAGASD* (12 states) | $100 | 15.98 h | **$6.26** |
| KXRAIN | $100 | 43.8 h | **$2.28** |
| KXTTELITEMATCH | $20 | 163 h | **$0.12** |

Crypto is not 7x worse. It is **10x better than the best "new" family**, and
capital is locked for 15 minutes instead of 18 hours. Every family in the brief
is a worse version of what this project already has.

**The six best-paying liquidity programmes on Kalshi are all already in
`kalshi_collector.py`.** The best *uncollected* family is KXDIESELD at $7.80/hr.

---

## The endpoint is 177x bigger than the brief assumed

The brief said "1,000 rows was the limit and may be truncated". It was truncated
— badly. Paging `next_cursor` to exhaustion:

* **176,914 programs**, 177 pages, zero duplicate ids
* **2025-09-18 → 2026-09-07** — a full year of history
* **3,813 distinct families ever; 248 live right now**
* Two types: `liquidity` 154,639 and **`volume` 22,275** (the brief missed this
  type entirely)
* `paid_out` is populated: 165,124 true / 11,790 false — a historical record of
  which pools actually settled

The families in the brief were simply the first page sorted by start date. The
brief's counts ("KXDIESELD 21 programs") are page-1 counts, not totals (672).

Total pool across the exchange on the last complete day (2026-09-05 UTC):
**$152,307/day** across 535 families. Prior days: $156,710, $159,357.

### The volume programme — dead

`incentive_type='volume'`, 22,275 programs, dominated by **KXBTC15M (9,781) and
KXETH15M (8,299)** — series this project already collects — at $20 per ~13-min
period = **$95/hr/market**, the highest rate ever seen on the exchange.
**It ended 2026-05-12.** Zero live. Historical curiosity, no money in it today.
Worth knowing Kalshi ran it and switched it off.

---

## THE DECIDING QUESTION — is the target reachable?

Measured on live order books via `GET /markets/{ticker}/orderbook`.

### Two sampling bugs caught before they became findings

1. **First run: 0% qualification, all books empty.** Artefact check: the same
   ticker had a full book three minutes earlier. Cause — those markets had
   **closed at 17:00** and the book emptied. `GET /markets?status=open` returns
   markets that are already closed; the filter is stale. Must filter on
   `close_time > now` yourself.
2. **Second run: 0% again.** Cause — after filtering by `close_time` the list
   came back newest-first, so I sampled **tomorrow's windows**, which have not
   opened for trading. Must sort by `close_time` ascending and take the
   soonest-closing group.

Both would have produced a confident, wrong "the target is never reached".

### The real structure

A KXCRYPTOLEAD15M market lives **exactly 15 minutes** (open 17:00, close 17:15)
and the incentive window covers its whole life. Only the one currently-trading
window has a book at all; the other 200+ "live" markets are empty until their
window opens. The correct denominator is the active window, not the family.

### Measurement — 1,040 snapshots, 5 coins, 2 full windows

| | |
|---|---|
| snapshots where **both sides ≥ target 1000** | **671 / 1,040 = 64.5%** |
| (second window, sampled start to finish) | **605 / 605 = 100%** |
| median YES depth / NO depth | 4,270 / 6,074 vs target 1,000 |
| median reference price | YES 5c, NO 78c |
| **median share of side score with 100 contracts** | **YES 14.8%, NO 27.7%** |
| capital for 100 contracts on both sides | **$83 / market** |

Per coin (qualification rate, YES share, NO share): BTC 66.8% / 9.1% / 21.9%;
ETH 70.7% / 3.8% / 27.9%; HYPE 68.8% / 26.7% / 27.7%; SOL 58.2% / 26.7% / 27.8%;
XRP 58.2% / 3.8% / 28.0%.

The 28.9% figure in HANDOFF.md understates it. On Coin Race the target is met
comfortably — median depth is 4–6x target.

### Why 100 contracts buys a quarter of the side — hand-verified

Live XRP book, checked by hand against the formula:

```
NO side, best-first          cum
  95c   120                  120
  92c    14                  134
  91c   301                  435   <- cum first crosses target/5 = 200 here
  87c   120                  555        REFERENCE PRICE = 91c
  83c   120                  675
  ... 3c-spaced ladder down to 1c, 6,148 total
```

Score = 120 + 14 + 301 (all at or better than 91c, multiplier 1.0)
      + 120 x 0.5^4 (87c, 4 ticks) + 120 x 0.5^8 (83c) + ...
      = **~443 score from 6,148 contracts of depth.**

My 100 at 91c → 100 / (443 + 100) = **18.4%.**

**The halving per tick is the whole game.** Someone is running a 120-lot ladder
every 3 cents; at 3 ticks that is 12.5% credit, at 6 ticks 1.6%. Their 6,148
contracts score less than 500. Only depth within ~2 ticks of the reference price
exists at all. Reconciled by hand; the script agrees.

Corollary: posting one tick *better* than the reference (92c, +$1 per 100
contracts) **moves the reference to 92c and demotes the 301 at 91c to 0.5x**.
Cheap offence, cheap defence. Adding at or below the reference does not move it.

---

## Economics, ranked at a fixed $500 of capital

`$/day` assumes 100 contracts resting on each side of each concurrent market,
qualification-rate weighted, pool split 50/50 across the two sides.

| family | cap/mkt | mkts @ $500 | contracts | $/day | **%/day on capital** | $/contract/day |
|---|---|---|---|---|---|---|
| **KXCRYPTOLEAD15M** | $90 | 5.0 | 1,000 | **$1,508** | **335%** | **$1.508** |
| KXSBUXCC | $87 | 5.8 | 1,149 | $50.79 | 10.2% | $0.044 |
| KXRAIN | $94 | 5.3 | 1,064 | $29.84 | 6.0% | $0.028 |
| KXYTVIEWSW | $18 | 27.8 | 5,556 | $27.63 | 5.5% | $0.005 |
| KXAAAGASD | $95 | 5.3 | 1,053 | $26.82 | 5.4% | $0.026 |
| KXAAAGASDPA | $99 | 5.1 | 1,010 | $8.40 | 1.7% | $0.008 |
| KXMLBPLAYOFFS | $99 | 5.1 | 1,010 | $3.86 | 0.8% | $0.004 |
| KXDIESELD | $89 | 5.6 | 1,124 | $2.82 | 0.6% | $0.003 |
| KXHEADLINE | $99 | 5.1 | 1,010 | $1.54 | 0.3% | $0.002 |

The 13-minute 1,040-sample run gives the crypto row as **$1,318/day on $415 peak
capital = 318%/day, $1.32/contract/day**, capturing **13.7%** of that family's
$9,600/day pool. Use that number, not the 60-second sweep row.

KXTTELITEMATCH and KXALBUMSTREAMS **never qualified** in live sampling — median
depth 0–10 against a 1,000 target. Their pools ($14,009/day and $6,324/day, the
two largest on the exchange) are very likely paid to nobody. Do not chase them.

---

## I do not believe 318%/day, and here is exactly why

The measurement is sound for what it measures: real books, formula reconciled by
hand, two sampling bugs caught and killed. The leap from *"14.8%/27.7% of the
side's score"* to *"$1,318/day in the account"* rests on assumptions I could not
verify with GET:

1. **The 50/50 side split is assumed, not verified.** `discount_factor_bps=5000`
   is far more likely to *be* the 0.5 per-tick decay factor than a side split —
   the families at 2500/4000/3000/1000 bps would then be harsher decay curves.
   If the split is not 50/50 this is wrong by up to 2x either way. All six
   top-rate families are uniformly 5000 bps, so the *ranking* is unaffected.
2. **Eligibility is unverified.** No GET endpoint exposes LIP participation
   (`/incentive_programs/summary`, `/portfolio/incentives`,
   `/incentive_program_participation` all 404). If LIP is restricted to
   designated market makers, this is $0.
3. **The competitive response is not modelled.** Taking 13.7% of a pool changes
   what the incumbent ladder does. The 0.1c-tick defence above costs a rival
   almost nothing.
4. **Fill risk is unpriced.** Resting 100 NO at 91c means losing $91 if that coin
   leads. Median volume is only **285 contracts per 15-min market**, so fills are
   rare — but a rare fill in a market like this is informed flow, which is
   exactly the adverse selection `research/informed.py` exists to measure.
5. **Sunday afternoon.** Weekday books will be deeper and more contested.
6. **No quoting bot exists.** This requires always-on cancel/replace at the
   reference price across 5 markets rolling every 15 minutes.

Even after a 90% haircut for all six, this is **$132/day on ~$415** — still
larger than pin's whole measured range ($30–101/day). That is the finding.

---

## Fees and tick grids

Every family checked returns `fee_type: quadratic, fee_multiplier: 1` — the same
`0.07*p*(1-p)` as crypto. **No family has a fee advantage.**

Tick grids differ, and it matters because the multiplier halves per *tick*:

* `linear_cent` (1c everywhere) — KXCRYPTOLEAD15M, KXRAIN, KXAAAGASD*,
  KXDIESELD, KXTTELITEMATCH, most others.
* **`tapered_deci_cent`** — all five commodity 15M families: **0.1c steps below
  10c and above 90c**, 1c between. Reference prices sit at 5c and 78c on the
  comparable crypto books, i.e. right in the deci-cent zone. There, one cent of
  price = **10 ticks = 0.5^10 = 0.001**. Whole-cent ladders score *nothing*, and
  the participant nearest the reference price takes essentially the entire side.
  Winner-take-all at 0.1c granularity.

---

## What the families actually are

| family | resolves on | source | market life | schedule |
|---|---|---|---|---|
| KXCRYPTOLEAD15M | which of BTC/ETH/SOL/XRP/HYPE has the highest return in the 15 min | CF Benchmarks | **15 min** | 96 windows x 5 coins, **7 days/week** = $9,600/day |
| KXGOLD/SILVER/WTI/NATGAS/COPPER 15M | 1-min candle close >= candle close 15 min earlier | **Pyth** | **15 min** | 96 windows/day **weekdays only**; Sat 16, Sun 8. $1,920/day each on a weekday, $9,600/day across the five |
| KXDIESELD | daily diesel price above strike | AAA | 1,079 min | 1 window/day, ~16-21 concurrent strikes |
| KXAAAGASD + 12 state variants | daily avg regular gas price above strike | AAA | 959 min | 1 window/day, ~11-17 strikes each |
| KXRAIN | daily precipitation > 0 in a city | The Weather Company | 2,630 min | ~41 cities concurrent |
| KXTTELITEMATCH | TT Elite Series table tennis match winner | TT Elite/Sofascore | 10,415 min | up to 733 concurrent — **never qualifies** |
| KXSBUXCC | Starbucks card data | Carbon Arc | 1,440 min | ~9-25 concurrent |
| KXHEADLINE / KXYTVIEWSW / KXMLBPLAYOFFS | headlines / YouTube views / MLB | various | 14 days | long-dated, low rate |

None of the brief's families resolve in <= 30 minutes. **KXCRYPTOLEAD15M and the
five commodity 15M families are the only <= 30-minute markets with a programme**,
and they are the highest-paying ones.

---

## The commodity 15M trap — measured, and it is not what it looks like

Target 300 instead of 1,000 looks like a 3.3x easier bar at the same $80/hr.
It is not, and the reason inverts the whole thesis:

| series | median volume per 15-min market | median open interest |
|---|---|---|
| KXGOLD15M | **130,883** | 43,370 |
| KXWTI15M | 42,235 | 16,135 |
| KXSILVER15M | 38,366 | 14,073 |
| KXCOPPER15M | 9,066 | 3,525 |
| KXNATGAS15M | 6,551 | 2,921 |
| **KXCRYPTOLEAD15M** | **285** | **184** |

The commodity markets are **100–450x more heavily traded** than Coin Race.
Target 300 will be met trivially — by real market makers, on a 0.1c grid, in a
winner-take-all decay regime.

**KXCRYPTOLEAD15M wins because it is neglected, not because the target is low.**
285 contracts a window trade against 4,000–6,000 of resting depth: a couple of
ladder bots quoting into a market nobody trades. That is why $83 of capital buys
a quarter of the side.

**I could not measure a commodity 15M book.** They trade 22:00–04:00 UTC on a
Sunday and were empty during this session. This is the single biggest gap here.

---

## Which series to record — recommendation only, no files edited

`kalshi_collector.py` was **not modified**. Both collectors verified alive at the
end of this job (PIDs 3381772 / 3385232, unchanged since 10:57), 52 GB disk free,
4 GB RAM free.

**The good news: nothing high-rate is missing.** `CRYPTO_15M` already contains
KXCRYPTOLEAD15M and all five commodity 15M series (added today). The top six
families by $/hr/market are all covered. No urgent recording gap exists.

Two recommendations for the operator:

1. **Highest value: capture a commodity 15M weekday session.** 22:00–04:00 UTC
   tonight, and the full 96-window weekday schedule from Monday. This is the one
   family class measured at $80/hr/market that has **never had its book
   observed**, and the deci-cent grid makes it a structurally different game.
   Already in the collector list — just confirm the subscription actually took
   (`research/newseries.py`), because the file's own comments note a prior
   `--series` change that silently never took effect.
2. **`discover()` uses `status: "open"` (line 169).** I proved that filter
   returns markets that have already closed and whose books are empty. It is
   probably good enough for a 30-second re-subscribe loop, but if any window is
   being missed at its open, this is where to look.

KXDIESELD, KXAAAGASD*, KXRAIN: **do not add.** At $7.80/hr and below with
16–44 hour capital lockups they are 10–35x worse per dollar-day than what is
already recorded, and disk is 40–80 MB/day/series.

---

## Which one I would put a dollar on first

**KXCRYPTOLEAD15M** — and the honest reason is uncomfortable: it is the family
this project already collects, already has a tape for, and already understands.
The 61,000-row page-1 sample sent the brief hunting for exotic families, and the
answer came back pointing at the one already on the desk.

* $80/hr/market, the joint-highest rate on the exchange, **7 days a week**
  (the commodity families stop at the weekend)
* 15-minute capital lockup — capital turns over 96 times a day
* $415 buys 100 contracts on both sides of all 5 coins
* measured 64.5% qualification, 14.8%/27.7% of side score, on 1,040 live snapshots
* neglected: 285 contracts a window trade against 6,000 of resting depth
* **already recorded** — a tape exists to backtest against from today

### Next step, in order

1. **Settle the 50/50 side-split question.** It is a 2x factor on every number
   above and it is the cheapest thing to resolve — Kalshi's LIP documentation or
   support, not an API call. Nothing else should be built until this is known.
2. **Replay the collected KXCRYPTOLEAD15M `orderbook_delta` tape** through
   `analyse()` in `job2/lipdepth.py` to get qualification and score-share across
   a full week of weekday sessions, instead of 13 minutes of a Sunday. The tape
   is being written right now.
3. **Measure the commodity 15M books tonight (22:00 UTC).** Same script, target
   300, and check whether the deci-cent grid concentrates the score as predicted.
4. Only then: a quoting bot, and only then a funding conversation.

**No live orders were placed and no money was committed. Everything above is
GET-only measurement.**

---

## Files

| path | what |
|---|---|
| `C:\Users\Joe\AppData\Local\Temp\kals-work\job2\pull_programs.py` | pages the whole endpoint to exhaustion |
| `C:\Users\Joe\AppData\Local\Temp\kals-work\job2\programs.json` | all 176,914 programs, 2025-09-18 → 2026-09-07 |
| `C:\Users\Joe\AppData\Local\Temp\kals-work\job2\lipdepth.py` | `book()` + `analyse()` — the LIP scoring model, hand-verified |
| `C:\Users\Joe\AppData\Local\Temp\kals-work\job2\sampler.py` | live-market discovery (close_time filter + ascending sort) |
| `C:\Users\Joe\AppData\Local\Temp\kals-work\job2\longsamp.py` / `longsamp.json` | the 1,040-snapshot run |
| `C:\Users\Joe\AppData\Local\Temp\kals-work\job2\sweep.py` / `sweep.json` | cross-family live sweep |
| `C:\Users\Joe\AppData\Local\Temp\kals-work\job2\rate2.py` | $/hour/market and $/day-per-family from history |
