# 03 execution -- what do we lose between deciding and filling?

Investigator 03 "execution". Status: COMPLETE (2026-09-22). Read-only; nothing was started, stopped or edited outside this file and the scratchpad. At finish: kalshi_collector (pid 105304) and crypto_feeds (pid 105352) alive, 33 GB free disk.
Sources: all 124 `results/pinrun-live-*.jsonl` (1,198 entry orders, 2026-09-08
07:59Z .. 2026-09-22 06:29Z), each `order` paired 1:1 with the `signal` that
preceded it in the same file; per-market money from `results/kalshi_ledger.json`
via `pinledger.pnl`; outcomes from fulltape `markets.json` + ledger + every
`settled` row in `results/*.jsonl` (21,491 tickers, zero conflicts).
Scripts: scratchpad `map/03/{outcomes,extract,a*.py}`.
"naked $" = filled x (payout - exec) - fee for the ENTRY order only (no hedge);
"ledger $" = Kalshi's per-market net, hedge included. naked $ on all 747 filled
markets = $496.19; ledger on the same 747 = $484.98 (hedging net -$11).

## 1. Findings, ranked by dollars

**Headline.** Since 2026-09-13 04:14Z (when the bot started logging how old
the offer it buys is), there were 15 losing pin markets totalling **-$607.99**
(Kalshi ledger, hedges included). **11 of them, -$564.38 (93%), contain a fill
with one of two execution markers**: the fill landed >2c cheaper than the ask
we saw (F1), or the offer we bought was under 100 ms old (F2). Markets with a
marker: 157 closes, **-$155.11**. Markets without: 249 closes, **+$592.41**.
F1 is solid (p = 3e-6) but not visible before sending; F2 is visible before
sending but is a hypothesis (p = 0.016, does not clear a multiple-looks bar).
Nothing here is a stale book (R1), and none of the volume features is the
bleed (F5).

| # | what | window | closes | lost | $ |
|---|---|---|---|---|---|
| F1 | fill >2c cheaper than ask seen | all live | 27 | 7 | -102.69 ledger |
| F2 | offer <100 ms old | 09-13 .. 09-22 | 152 | 8 | -115.79 ledger (-257.75 naked since 09-18) |
| F1+F2 | either marker | 09-13 .. 09-22 | 157 | 10 | -155.11 ledger |
| F3 | hedge paid above first ask (before hedge-slip) | 09-12 .. 09-21 | 17 mkts | - | -46.01 (fixed 09-19 22:50Z) |
| F4 | unfilled contracts, priced at ask seen | all | 223 | 8 | +15.18 missed / -70.40 avoided |
| F5 | sweep-depth extra contracts | 09-14 12:54Z .. | 152 | 2 | +188.29 (made money) |

### F1. A fill that lands MORE THAN 2c CHEAPER than the ask we saw is the market telling us we are wrong -- and we lose on it about 1 time in 4.

**Claim.** When the exec price comes back >2c below the ask the bot read, the
book collapsed during the ~100 ms between reading it and the order landing;
those fills lost at 7 of 27 closes (26%) against 12 of 520 closes (2.3%) for every other fill,
and cost **-$102.69 (ledger) over the whole live life, -$116.73 since
sweep-depth went live (09-14 12:54Z), on 13 closes, 4 lost.**

**Mechanism.** Every entry is an IOC BUY with a limit at or above the ask seen
(since 09-13 the limit is `sweep_limit()`, normally 98c). A buy limit accepts
ANY cheaper price -- there is no such thing as a minimum price on a buy. So if
between our book read and the order's arrival the other side re-prices (a
crypto-wide move the market sees before our index does), we are filled at the
NEW, lower price by exactly the people who just re-priced. The dump guard
(`DUMP_DISCOUNT` 15c below fair -> refuse) protects only the price we SAW; the
price we GET is never checked. Examples (ledger-confirmed prices):

| UTC | market | ask seen | exec | n | our fair | result | ledger $ |
|---|---|---|---|---|---|---|---|
| 09-18 01:14:22 | BTC 21:15 ET | 97.8c | **53.0c** | 99 | 99.56% | lost | -27.87 (hedged) |
| 09-18 04:14:28 | DOGE 00:15 ET | 97.6c | **11.0c** | 33.6 | 99.71% | lost | +4.36 (hedged) |
| 09-19 05:44:36 | BNB 01:45 ET | 85.0c | **74.99c** | 76 | 99.93% | lost | -57.76 |
| 09-21 16:44:16 | NEAR 12:45 ET | 95.5c | **91.1c** | 81 | 99.56% | lost | -59.09 (hedged) |

On 09-18 the BTC ladder we logged held 1,939 contracts at 97.9c and 2,947 at
98c; we were filled 99 at an AVERAGE of 53c. That book did not exist when the
order arrived.

**Evidence** (slippage = exec - ask seen, per entry order, classes fixed before
the numbers were read):

| exec vs seen | orders | closes | lost closes | loss rate | naked $ | 
|---|---|---|---|---|---|
| >2c cheaper | 28 | 27 | 7 | 26% | -102.99 |
| 0.05-2c cheaper | 99 | 93 | 3 | 3% | +84.69 |
| at seen (+-0.05c) | 414 | 344 | 7 | 2.0% | +235.82 |
| 0.05-1c dearer (swept) | 180 | 154 | 2 | 1.3% | +186.77 |
| 1-3c dearer | 40 | 37 | 0 | 0% | +121.78 |
| >3c dearer | 12 | 12 | 1 | 8% | -29.88 |

Per market (ledger, hedge included), since sweep-depth 09-14 12:54Z: markets
with a >2c-cheaper fill 14 mkts / 13 closes / 4 lost / **-$116.73**; every other
pin market +$420.

**Confidence.** High that the pattern is real (7/27 vs 12/520 closes, one-sided
Fisher p = 3e-6), but n = 27 closes is under the 30-close floor, so the exact
loss rate is loose. **Artefact checks:** exec prices confirmed against Kalshi's
own ledger for 7 of the markets (e.g. BTC 21:15 YES 99 @ 0.5300); units are
dollars throughout (exec range 0.0998-0.996, decided from the whole sample);
outcome is Kalshi's `market_result`. Two fills on the same close (09-18 01:14Z
BTC + ZEC, both collapsed) are one close, counted once.

**Tape check (what the market did, not our loss rate).** For all 13 >2c-cheaper
fills since 09-17 I found OUR fill on the `trade` channel (same `ts_ms`, taker
= our side, count = our fill exactly). In every one the collapse starts in the
**last 250 ms before our fill** -- e.g. BTC 09-18: 97.4-97.9c for 1.5 s, then
31,403 contracts of NO-taking in the 250 ms before our fill took YES to 42c; we
were one of the trades inside that wave, not ahead of it. So this is a race
lost in the ~100 ms send window (median send->response 104 ms on these,
93 ms on the rest), not a stale book the bot could have rejected: book age at
decision was 1-6 ms on the four losers, and rebuilding the exchange's book
from the tape matched the ladder the bot logged at 0-250 ms (R1). **Nothing the bot saw before sending
separated these from normal fills** (book age, index age and tau medians are
the same as the rest; see F2 for the one observable that does lean).

**Tested on request: "fills 2-5c+ below the ask seen lost 6 of 15, -$271 on
6 markets since 09-19 22:29Z".** Measured from the order records and the
ledger, I can reproduce the 6-of-15 only as an ALL-TIME count at >= 5c under
(15 fills, 6 lost, ledger -$32.51 on those 15 markets). Since 09-19 22:29Z:

| exec vs ask seen, since 09-19 22:29Z | fills | lost | markets | ledger $ |
|---|---|---|---|---|
| >= 1c under | 9 | 1 | 9 | -76.81 |
| >= 2c under | 6 | 1 | 6 | -85.91 |
| >= 5c under | 2 | 0 | 2 | +12.90 |
| not under | 116 | 1 | 110 | +115.05 |

The one loss is NEAR 12:45 ET 09-21 (-$59.09). The other big number in the
>= 2c row is HYPE 23:45 ET 09-19 (-$43.92), whose entry WON (+$5.74) and lost
the money on a hedge false alarm. **I cannot find -$271 on 6 markets in this
window**; all four losing pin markets since 09-19 22:29Z total -$199.22 and
two of them had no below-seen fill at all. The pattern is real over the whole
life (above) but in this window it is one loss, not six.

**Early leg (tau 31-45).** Since the early leg went live (09-17 13:05Z):
>= 2c-under fills on the EARLY leg 7 fills / 6 closes / **3 lost / -$104.62
naked**; on the full leg 5 fills / 5 closes / 1 lost / -$38.60. Early-leg
fills that were not under: 145 closes, 3 lost, +$84.33. The early leg carries
65% of fills and 58% (7 of 12) of the collapse fills -- no over-representation
in count, but 3 of its 6 collapse closes lost. n is far too small to split
further. Also: **all 4 losing pin markets since 09-19 22:29Z were early-leg
entries at tau 33-44** (XRP 23:45 ET 09-19 -$64.95 and HYPE -$43.92 both won
the entry and lost on the hedge; NEAR -$59.09 and HYPE 18:15 ET 09-21 -$31.27
lost the entry).

**Dollars.** -$102.69 ledger all-time on 27 closes (-$116.73 since 09-14 on 13
closes), beside +$587.67 ledger on every other pin market.

### F2. Offers that had JUST appeared (<100 ms old) are where the losses live -- and it got much worse from 09-18.

**Claim.** The bot records how long the price level it buys has been resting
(`level_age_ms`, exact when it watched the level appear). Fills on a level
younger than 100 ms lost at 8 of 152 closes (5.3%) and **-$114.70 naked**;
fills on older levels lost at 3 of 259 closes (1.2%) and **+$556.48**.
Since 2026-09-18 00:00Z: fresh **79 closes, 7 lost (8.9%), -$257.75**; older
**130 closes, 1 lost, +$278.33**. Before 09-18 fresh levels were fine (73
closes, 1 lost, +$143.05). Ledger (hedge included): markets with a fresh-level
fill **-$115.79** on 152 closes. It is BTC-heavy: BTC fresh 37 closes, 4 lost,
-$193.97 vs BTC older 35 closes, 0 lost, +$95.33; other coins fresh 126
closes, 4 lost (3.2%), +$79.26 vs older 238 closes, 3 lost (1.3%), +$461.15.
The loss RATE is higher on fresh levels for both groups; only BTC's fresh
fills are net negative.

**Mechanism (proposed, not proven).** A level that has rested for seconds is a
passive quote nobody has bothered to move -- the cheap supply the whole
strategy lives on (levels already resting at subscription: 149 closes, **zero
losses**, +$324). A level born in the last 100 ms is someone reacting to
something RIGHT NOW -- usually a spot move our 1/sec index has not shown yet --
and offering the side they now think will lose. A fresh level is also simply
the fingerprint of a book that is moving, which is when every F1 collapse
happened (10 of the 28 F1 fills are on <100 ms levels).

**Evidence.** 510 fills 2026-09-13 04:14Z .. 09-22 with `level_age_ms`
(338 exact). Threshold sweep (cumulative, exact ages):

| level younger than | closes | lost | naked $ | vs older: closes | lost | naked $ |
|---|---|---|---|---|---|---|
| 100 ms | 152 | 8 (5.3%) | **-114.70** | 259 | 3 (1.2%) | +556.48 |
| 250 ms | 188 | 9 (4.8%) | -6.93 | 226 | 2 (0.9%) | +448.70 |
| 1,000 ms | 228 | 10 (4.4%) | +76.36 | 184 | 1 (0.5%) | +365.42 |

Model edge at entry is the same for both groups (median 2.30c fresh vs 2.24c
older; ask 97.3c vs 97.4c; tau 28 vs 30), so the model cannot see this.

**By ET day, naked entry $ (lost closes / closes).** Every day, fills on OLDER
levels made money -- including both losing days. The swings are the fresh ones:

| ET day | fresh <100 ms | older levels |
|---|---|---|
| 09-13 | +52.95 (0/17) | +65.33 (0/26) |
| 09-14 | -18.19 (1/15) | +46.01 (1/36) |
| 09-15 | +32.73 (0/15) | +45.36 (0/16) |
| 09-16 | +48.72 (0/13) | +65.91 (1/26) |
| 09-17 | -1.25 (1/18) | +73.26 (0/29) |
| 09-18 | +26.89 (1/21) | +56.88 (0/34) |
| **09-19** | **-213.94 (3/19)** | +86.90 (1/42) |
| 09-20 | +31.07 (0/12) | +81.78 (0/29) |
| **09-21** | **-76.89 (2/21)** | +33.19 (0/20) |

F1 and F2 together (either marker), since 09-13 04:14Z: 157 closes, 9 lost,
**-$154.23**; neither marker: 255 closes, 2 lost, **+$596.01**.
One-sided Fisher p for fresh-vs-older lost closes: 0.016 all period, 0.005
since 09-18. I looked at ~25 cells (book age, index age, latency, level age,
tau x ~5 buckets), so the multiple-looks bar is ~0.002: **F2 does not clear
it. F1 does (p = 3e-6; 7/27 vs 12/520 closes).**

**Confidence: LOW-MEDIUM -- a hypothesis, not a result.** The tape did NOT
corroborate it: the market's mid 2 s, 5 s and 10 s after our fill moved no
worse after fresh-level fills than after older ones (5 s: -0.99c vs -1.01c
per close; fresh-minus-older -0.27c against a shuffled-label 95% band of
[-2.16c, +1.98c]; 509 fills, ticker channel). So the ONLY evidence is 8 vs 3
settled losses (12 losing closes in
total). the 100 ms cut was a bucket edge chosen before reading the table, but
the finer split is non-monotonic (0-50 ms: 104 closes, 2 lost, +$262.77;
50-100 ms: 59 closes, 7 lost, -$377.48), which is what noise looks like as
often as it is what a mechanism looks like. The first-half/second-half flip is
itself a warning that this could be a regime or a coincidence of 7 bad closes.
**What would make it an artefact:** `level_age_ms` is only exact for a level
born by delta; a reconnect resets ages to "unknown" (exact=False), so the
old-and-safe group is partly "levels present at snapshot". The fresh/old split
does NOT depend on that group (exact-only ages >= 100 ms: 153 closes, 3 lost,
+$231).

### F3. The hedge's own execution chased a falling price: $46 paid above the first ask, and one hedge that never filled.

**Claim.** Before `--hedge-slip 0.03` went live (2026-09-19 22:50Z) a hedge
was an IOC at EXACTLY the ask seen; in a collapse that ask is gone before the
order lands, so the hedge missed, re-read, and bought higher a second later.
**Measured: $46.01 paid above the first ask seen across 17 hedged markets**
(of which $7.49 is NEAR 09-21's deliberate proportional top-up, so ~$38.52
is chase), concentrated in three markets: BNB 09-19 12:30 ET 8 tries, first
ask 44c, paid 74.3c avg on 84.5 -> +$25.62; BTC 09-14 01:30 ET 43c -> 58c,
+$9.00; BTC 09-17 21:15 ET 63c -> 72c on 99, +$8.91. And BNB 09-19 01:45 ET
tried 51c, 70c, 76c and hedged **1 of 76** -- that market lost -$57.76; what
a first-try fill would have saved is NOT measured (depth at 51c unknown).

**Since hedge-slip (limit = ask + 3c):** 5 hedge orders, 5 filled in full on
the first try (09-20 XRP, HYPE; 09-21 NEAR x2, HYPE). n = 5 -- consistent,
not proof. Source: `hedge` records, all live logs. Confidence: high on the
$46 (it is arithmetic on logged prices); the fix is already live.

### F4. Orders that did not fill (fully) cost nothing -- the unfilled part would have LOST money.

**Claim.** Of 972 orders that reached the exchange, 199 filled nothing and 85
filled part; 81.9% of contracts asked were filled. Pricing every unfilled
contract at the ask we saw and Kalshi's result:

| what did not fill | orders | closes | lost closes | unfilled contracts | would-have $ |
|---|---|---|---|---|---|
| zero-fill IOCs, all time | 199 | 145 | 6 (4.1%) | 5,707 | **+15.18** |
| partial-fill remainders, all time | 85 | 78 | 2 | 1,893 | **-70.40** |
| zero-fill since 09-14 12:54Z | 66 | 56 | 2 | 3,173 | +14.65 |
| partial remainders since 09-14 12:54Z | 51 | 46 | 1 | 1,536 | -80.80 |

**Mechanism.** An IOC misses when the offer was taken or pulled in the ~100 ms
of flight. That is disproportionately the offers someone else wanted to
remove -- the same selection as F1, working in our favour. Zero-fill closes
lost at 4.1%, about double the filled rate. **Missed profit is ~$15 in two
weeks: fill rate is not a lever.** The -$80.80 is dominated by one market
(BNB 09-19 12:30 ET: asked 171, got 82.8, lost) -- one-market caveat.

Two one-off order failures, both old: 25 orders refused **409
TRADING_BLOCKED** on 2026-09-15 15:44-19:44Z (4 closes, none lost; would-have
+$46.61 at ask seen; the bot kept sending for 4 hours) and 201 orders refused
locally by pintake's count rail on 2026-09-08 22:29-22:44Z (2 closes, +$69.60).
Neither recurs in the current code as far as the logs show.

### F5 (not a bleed). The volume features -- sweep, sweep-depth, depth-ladder, more coins per close -- MADE money on live fills.

Since sweep-depth went live (2026-09-14 12:54Z), splitting every fill that
landed at or above the ask seen into the touch part (priced at the ask seen)
and the part above the touch (priced at the implied remainder of the average):

| part | orders | contracts | naked $ | per contract | lost closes |
|---|---|---|---|---|---|
| orders that took only the touch | 206 | 12,017 | +97.92 | +0.81c | 4 of 171 |
| touch part of deeper orders | 177 | 3,954 | +68.36 | +1.73c | 2 of 152 |
| **contracts ABOVE the touch** | 177 | **8,671** | **+188.29** | **+2.17c** | 2 of 152 |

Sweep-depth sizing overall (actual minus a touch-only counterfactual, all
classes): **+$170.51** (-$12.99 on the F1 fills it enlarged, +$24.44 on
0-2c-cheaper fills, +$159.06 on the rest). Caveat: the touch-only
counterfactual assumes the extra contracts would not have been bought on a
later pass, so it is an UPPER bound on what sweep-depth added.
Depth-ladder proper (a fill whose touch was under the 1-contract floor):
3 fills, +$10.63 -- with `--min-fill-frac 0` since 09-14 15:53Z the floor is
1 contract, so this feature almost never acts. Fills where sweep-depth lifted
a 1-10 contract touch: 89 closes, 1 lost ($0.98), +$176.13.
Price paid above the ask seen on swept fills: $130.20 over 232 orders --
the cost of the extra contracts, already inside the +$188.

More coins per close (`improve-scope market`, `pick best`): 2nd-and-later
coins of a close made +$130.59 (41 closes, 0 lost, 09-13..09-17) and
+$116.63 (79 closes, 1 lost, since 09-17 13:05Z). First coin of the close
since 09-17: **200 closes, 7 lost, -$61.60.** Same-market repeat fills
(early leg top-ups, improve-max re-buys): 26 orders, -$1.66.

**So the growth changes did not cause the bleed on these numbers. The bleed
is concentrated in F1/F2 fills, which are mostly FIRST fills of a close.**


## 2. Refuted or not supported

### R1. "The pin bot decided on a stale book, like the coin race did" -- REFUTED on 6 of 6 collapse fills checked.

The coin race's loss (decided 93c, filled 85c) came from a REST book up to 5
minutes old. The pin bot's book is a live WebSocket book, and I tested whether
it was stale directly: rebuilt the exchange's book from the tape
(`orderbook_snapshot` + `orderbook_delta` applied by EXCHANGE `ts_ms`) at
0-5,000 ms before each decision and matched it to the 12-level ladder the bot
LOGGED in its `signal` record. Best match: BTC 09-18 **100 ms** (mismatch 15
contracts vs 3,400+ at 250 ms and beyond), ZEC 09-18 **100 ms**, BNB 09-19
**0 ms (exact match, mismatch 0.0)**, ZEC 09-19 **0 ms**, NEAR 09-21 ~250 ms
(book moving every 100 ms, no clean match), DOGE 09-18 ambiguous (the two
levels the bot bought, 97.6c x34 and 97.7c x434, exist on the tape only in the
last ~100 ms -- the bot saw them within ~15 ms of their birth, per its own
`level_age_ms` 15). **The bot's book was 0-250 ms behind the exchange, not
seconds. It lost a ~100 ms race, it did not trade on a stale picture.** A REST
re-read before sending (the v-race90 fix) would add ~100 ms and read the same
exchange; it is not the fix here.

Scripts: `map/03/staleness.py`, decision time taken as our fill's exchange
stamp minus 100 ms (the bot does not log decision time below one second, so
+-100 ms of the "best match" is timing slack).

### R2 (side finding). The COLLECTOR's feed -- the tape -- runs 2-5 SECONDS late during bursts.

While testing R1: the collector's own `_rx_ms - ts_ms` on `orderbook_delta`
has a median of 28-38 ms but a **p90 of 2.7-4.7 s in every hour checked**, and
was 1.9-4.4 s in the second before 4 of 8 collapse fills (BTC 09-18 2,147 ms,
DOGE 09-18 4,408 ms, ZEC 09-18 2,120 ms, ZEC 09-19 1,902 ms), while the bot's
separate connection was fresh (R1). So it is the collector's backlog. Anything
that times the tape by `_rx_ms` is seconds wrong exactly when prices move;
`pinsim` times deltas by `ts_ms` (checked, fine) but snapshots by `_rx_ms`.
Correlation worth noting, NOT a bot observable: fills where the collector's
median ticker-channel lag in [-1.5 s, +0.5 s] was >= 1 s: 130 closes, **8 lost
(6.2%), -$104.16 naked**; under 1 s: 303 closes, 3 lost, +$511.30. Collector
lag = "the whole market is in a message burst" -- the same busy-book condition
as F1/F2.

### R3. Book age, index age and send latency do not separate losers.

Limits: `MAX_BOOK_AGE_MS = 2000` (time since last WS message), `MAX_INDEX_AGE_S
= 2`. On fills: book age median 7 ms won / 5 ms lost (max 447 ms -- the 2,000 ms
limit never came close to binding on a fill; it bound 249 times, 120 of them
in the 09-22 outage). Index age median 230 ms won / 310 ms lost. Send->response
median 93 ms won / 98 ms lost (p90 117 / 142). No bucket of any of the three
has a loss rate distinguishable from the rest at this n.

### R4. The growth features are not the bleed. See F5: sweep-depth +$170.51 upper bound, extra coins per close +$247, depth-ladder +$10.63.

### R5. Fill rate is not a lever. See F4: every unfilled contract, priced at the ask we saw, would have made +$15.18 (zero fills) and -$70.40 (partial remainders).


## 3. Could not measure, and why

- **The bot's decision-to-send time.** `signal` and `order` are stamped to
  the second; `latency_ms` covers send->response only (median 93 ms). The
  in-process gap is unlogged, so "latency between signal and order" is known
  only as "same second".
- **The bot's own feed lag** (`rx - ts_ms` of its last applied delta). Not
  logged. R1 inferred it on 6 events by matching ladders; it cannot be
  checked on the other ~500 fills.
- **What an immediate hedge on an F1 fill would have saved.** Tape top-of-book
  after each F1 fill gives -$8.11 (hedging 1 s after) vs -$98.37 (2 s after)
  against -$102.99 naked -- the answer flips with one second of timing, and
  the top of book often held 0-20 contracts against our 70-100. Not a number.
- **Whether unfilled contracts would really have filled at the ask seen** (F4
  prices them there; that is the optimistic case).
- **10 zero-fill orders on 8 markets** with no outcome in fulltape, the
  ledger or any `settled` row -- excluded (all 2026-09-12..14).
- **Paper arms**: not used. A paper arm fills against the book it sees, so it
  cannot be filled cheaper than seen and cannot reproduce F1 or F2.
- Three `ticker` tape hours are corrupt (20260915T13, 20260915T20,
  20260922T06): 1 of 510 fills has no markout.

## 4. Solutions worth testing

None of these may block a hedge; each says what it would block.

1. **Log what is missing -- zero trading risk, do first.** On every `signal`:
   the book's last exchange `ts_ms` and `rx - ts` (feed lag), and a millisecond
   decision timestamp; on every `order`: the send timestamp. Blocks nothing.
   Makes F1/F2 and staleness auditable on every future fill instead of 6.
   Validation: the first day's records show feed lag median ~30 ms like R1.
2. **Pre-register F2 on live fills with NO code change** (level age is already
   logged). Bar, written before the data exists: over the next 60 closes with
   a fill on a <100 ms exact level, **>= 4 lost closes (>= 6.7%) AND naked $ < 0
   -> build item 3; <= 1 lost -> drop F2.** ~152 such closes took 9 days, so
   ~3-4 days. Source: live fills only. Blocks nothing.
3. **Only if item 2 passes: a young-offer entry gate, as "wait and re-check",
   not "refuse".** If the level we would buy is <100 ms old (exact), skip this
   pass; if it is still resting on a later pass it is by then old and is
   taken normally. **Blocks:** entry orders on offers born in the last 100 ms
   -- since 09-13 that was 181 of 510 fills, 10,095 of 31,576 contracts (32%),
   152 closes, -$115.79 ledger (but +$143.05 naked in the 09-13..09-17 half:
   it would have cost money then). **Must not touch the hedge path** (a hedge
   buys insurance at any age); self-test: the hedge's `pintake.take` call site
   never reaches the gate. Validation: live, alternate closes on/off for ~2
   weeks, compare loss rate and $ per close by half.
4. **F1 has no pre-send fix.** A buy limit cannot refuse a cheaper price, the
   book was fresh (R1), and nothing observable separated these fills. The
   candidate is a post-fill response: a fill >2c under the ask seen is the
   market disagreeing within 100 ms, so raise the hedge alarm on it
   regardless of the model's belief. Unpriceable from the tape (see 3.).
   Validate as a SHADOW first: on each such fill, log the opposite side's
   ask and depth from the bot's own book at +100 ms, +500 ms, +1 s, send
   nothing; after 10 events compute locked-vs-naked from our own book.
   Blocks nothing (it adds a hedge, never gates one).
5. **Keep `--hedge-slip 0.03`** (F3). Track first-try hedge fill: bar >= 80%
   of hedge contracts filled on the first order; so far 5 of 5 orders.
6. **Do not chase fill rate, and do not revert sweep / sweep-depth / extra
   coins** (F4, F5): the unfilled contracts were worth +$15 and the extra
   contracts made money.
7. Minor: on 409 `TRADING_BLOCKED` pause and alert instead of retrying (09-15:
   25 refused orders over 4 hours). Blocks only orders the exchange refuses.
