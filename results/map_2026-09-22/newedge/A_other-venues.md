# A -- other venues and everything else we record

Label `other-venues`. Read-only; no process started, stopped or signalled.
TRAIN only: closes 2026-09-16T14Z .. 2026-09-21T03Z (= through 2026-09-20 ET).
**HOLDOUT (09-21 on) was not looked at.**

Scripts, each with a passing `--selftest`, in
`<scratchpad>/newedge/other-venues/`: `cdc_contracts.py`, `cdc_book.py`,
`idx.py`, `kaltick.py`.

**Provenance.** Everything below is from the TAPE (what the venues and the
index DID) and is therefore a **hypothesis** by the 2026-09-10 amendment. No
loss rate of ours is quoted from it. No live dollars are claimed. The one
independent check that matters passed: the CF-index outcome derived here agrees
with Crypto.com's own terminal quote on **232 of 232** decidable BTC/ETH
contracts, so the outcome column is not the weak link.

**Resource check.** Start RAM 3.2 GB / end 2.97 GB; peak python here under
350 MB. Disk 21 GB free (above the 6 GB hard collection stop, still the real
deadline). `kalshi_collector.py` (pid 105304, 47 MB), `crypto_feeds.py`
(105352, 39 MB) and `cdc_record.py` (345648, 38 MB) all alive at the end.

---

## 1. Findings, ranked by what they are worth

### F1 -- we hold working read-only keys to a venue whose settlement rule is 5-15x kinder than Kalshi's, and we record none of it

`C:\kals\poly_us.py` plus `C:\kals\polymarket_key.json` are a finished, signed,
read-only client for **polymarket.us (QCX LLC, the CFTC-licensed US venue)**.
The Ed25519 signing problem that killed nineteen earlier attempts is solved in
that file. Per its own header it lists 5-minute, 15-minute and hourly crypto
markets on **seven coins (BTC, ETH, SOL, XRP, DOGE, HYPE, BNB)** and settles on
a **Chainlink TWAP over the WHOLE window**, against a strike that is the price
at the window's start.

**There is no `poly_data` directory. Nothing has ever been recorded.**
`poly_close.py` was written to answer the one question that matters -- does
anyone quote in the last seconds -- and it prints to the screen; there is no
output file anywhere on this box.

Why that settlement rule matters, computed with the repo's own
`engine.var_factor` (cross-checked to six decimals):

| seconds left | Kalshi (60 s average) | Poly 5-min TWAP | Poly 15-min TWAP |
|---|---|---|---|
| 15 | 0.587 | 0.117 (5.0x smaller) | 0.039 (15x) |
| 30 | 1.621 | 0.324 (5.0x) | 0.108 (15x) |
| 45 | 2.953 | 0.591 (5.0x) | 0.197 (15x) |
| 60 | 4.528 | 0.906 (5.0x) | 0.302 (15x) |

(units: standard deviation of settlement-minus-strike per unit of one-second
index sigma)

At 30 seconds left Kalshi has 30 of its 60 settlement seconds still unwritten;
a 5-minute TWAP has 30 of 300 and a 15-minute TWAP has 30 of 900. **The same
index shock that turns a 99c Kalshi pin into a total loss is a five-to-fifteen
times smaller event there.** The loss class we are bleeding on -- fat tails in
the last 30-60 s, which `signature/` says no pre-entry feature separates -- is
structurally 5-15x weaker on that venue.

What is NOT known and decides it: whether anyone quotes into the last 30
seconds (Crypto.com does not -- F2), the Chainlink oracle's own cadence and
staleness, and the cost to trade. **This is a one-night recording job, not a
research project**, and it is the only item in this assignment that could
plausibly move money.

### F2 -- Crypto.com is dead as a second pin venue, now measured across the whole venue

Confirms, at ~7x the sample and across all 20 coins, what an earlier session
found (`poly_close.py` header: "measured across 52,174 snapshots"). n = 6,956
fifteen-minute contracts, 364,120 book readings, TRAIN.

Seconds before expiry of **the last poll that still had any quote**:

| coin | p50 | quoted inside the last 10 s |
|---|---|---|
| **BTC** | **0.9 s** | 298 of 349 (85%) |
| **ETHER** | **1.4 s** | 290 of 349 (83%) |
| SOL, XRP, DOGE, ADA, BCH, LTC, LINK, AVAX, DOT, HBAR, SHIB, PEPE, BONK, FLOKI | 41.8-42.7 s | 0-2% |
| CRO | 121.4 s | 1% |
| XLM | 315.0 s | 0% |
| ONDO, SEI | never quotes | 0% |

58.8% of all contracts have their last quote in the 40-45 s bin -- a rule, not
thin liquidity. Median ask-minus-bid away from expiry: **BTC and ETH 3c;
everything else 13-24c**, flat across the whole window. A 13-24c spread cannot
hold any edge this project has ever measured.

**The BTC/ETH exception is not an exception.** Inside the final 15 seconds
their book is **stale and one-sided**: median age of the exchange's own book
timestamp 13.5 s (BTC) and 23.6 s (ETH), and 88% / 95% of readings have only
one side quoted. Buying the side that book itself calls near-certain (cost
0.95-0.99) loses **10 of 53 (18.9%) at 30 s left and 10 of 59 (16.9%) at 45 s**
on BTC -- gross -17.6c and -15.5c per contract. That is a stale quote being
picked off, not a market.

Access is separately blocked (HANDOFF: FIX-only for CDNA prediction contracts;
our key returns 40101 on every `/dcm` and `/fcm` endpoint). **Do not re-open
Crypto.com.**

### F3 -- Crypto.com's prices are strictly worse-informed than Kalshi's, at every horizon

Their strikes differ from Kalshi's (median 0.027% of level for BTC, which is
0.32 of the market-implied sigma at the same moment; p90 1.26 sigma), so a raw
price comparison is meaningless. Corrected by regressing the probit price gap
on the strike gap (R^2 0.63-0.71, which also backs out the implied sigma), then
scoring both venues against the settled outcome:

| seconds left | closes | Brier, Kalshi | Brier, Crypto.com shifted to Kalshi's strike | best weight on Crypto.com |
|---|---|---|---|---|
| 60 | 101 | **0.1066** | 0.1576 | 0.0 |
| 90 | 149 | **0.1223** | 0.1624 | 0.0 |
| 120 | 184 | **0.1318** | 0.1561 | 0.0 |
| 180 | 67 | **0.1009** | 0.1129 | 0.0 |
| 300 | 74 | **0.1186** | 0.1370 | 0.0 |

Log-loss agrees. Every blend weight above zero makes the forecast worse.
**Crypto.com adds no information to the Kalshi price at any horizon.**

### F4 -- Crypto.com does not lead Kalshi

Probit price changes over matched 60-120 s legs, 184 triples on 107 closes:

- Crypto.com move vs the **same-period** Kalshi move: **r = 0.861** (it tracks).
- Crypto.com move vs the **next** Kalshi move: **r = 0.017**.
- The part of the Crypto.com move orthogonal to Kalshi's, vs the next Kalshi
  move: **r = -0.075**.

MDE: with 107 closes we could have detected |r| >= 0.19 at p < 0.05. A lead
bigger than that is ruled out. A smaller one would be unusable anyway, because
our recording of that venue is a REST poll: median gap between distinct book
reads 0 s, p90 **10.4 s**, p99 45.0 s.

### F5 -- the cross-venue "arbitrage" costs $1.14 to buy a $1.00 payoff

Because the strikes differ, the only package that always pays at least $1 is:
buy Kalshi YES + Crypto.com NO when Crypto.com's strike is the higher one, and
the mirror when it is lower. **My first cut got this wrong** -- taking the
cheaper of the two directions regardless of strike order made 668 of 866 look
like free money. The wrong-direction package pays ZERO when settlement lands
between the two strikes. Corrected:

| seconds left | pairs | closes | package cost p25 / p50 | priced under $1.00 |
|---|---|---|---|---|
| 60 | 122 | 101 | 1.070 / 1.241 | 12 (10%) |
| 90 | 218 | 149 | 1.057 / 1.171 | 20 (9%) |
| 120 | 280 | 184 | 1.044 / 1.146 | 21 (8%) |
| 180 | 111 | 67 | 1.042 / 1.107 | 6 (5%) |
| 300 | 135 | 74 | 1.053 / 1.095 | 7 (5%) |

Kalshi's taker fee is included; **Crypto.com's fee is unknown and is not.**
Across all 866 pairs: 66 under $1.00 (8%), median gross **2.5c**, median
smaller-side size 78 contracts, on 39 closes. Total $1,094 over 5.5 days if
every one were filled instantly at both quotes -- which is fantasy: 19% of that
total is five prints, three of which show sizes of 0, 5 and 10 contracts, and
the Crypto.com side is a REST read up to 10 s old. Not a trade.

### F6 -- what our own recording of the second venue actually is

Complete: 161 hourly files per channel since 2026-09-16T14Z, **no missing hours
in `book` or `instruments`**, one missing hour (20260918T06) in `tickers` and
`trades`, two truncated gzips (20260916T14 and T16, salvageable with
`gzsalvage.py`; 2 of 110). Our own network latency is fine -- receive minus the
exchange's book timestamp, p50 124 ms BTC / 98 ms ETH -- so the staleness in F2
is **their** book, not our feed. Books are polled only inside 7 minutes of
expiry (`cdc_record.py NEAR_EXPIRY_S = 420`), so nothing earlier exists.

Traded notional there, 09-17..09-21Z: **BTC $2.69M, ETH $0.47M, every other
coin under $11k.** The venue is BTC and ETH and nothing else.

---

## 2. Refuted / not supported

- **"A second venue gives us capacity."** It does not. 18 of 20 coins have no
  market in the window we trade; the two that do are stale and one-sided there.
- **"Crypto.com lists 13 coins Kalshi does not, so 13 more markets."** True and
  worthless: those books vanish at 42 s, carry 16-24c spreads, and four of them
  traded under $700 in five days.
- **"Another venue's price is a second opinion that could catch our bad
  entries."** Measured and false (F3): best weight on it is zero at every
  horizon.
- **"Cross-venue arbitrage."** Median package costs $1.14 for a $1 payoff.
- **My own first cut of that arbitrage**, which said 668 of 866 packages were
  free money. Recorded here so the next session does not repeat it.
- **Blockchain / on-chain flow as a signal for this strategy.** Argued against
  in section 5 rather than assumed useful.

## 3. Could not measure, and why

- **Whether polymarket.us quotes into the last 30 seconds.** Nothing is
  recorded and I may not start a process. This is the one open question here.
- **Crypto.com's fees**, so F5 is gross only.
- **Crypto.com's own settlement index** -- on no endpoint we found. Worked
  around: their terminal quote agrees with the CF-index outcome 232 of 232.
- **Anything before 2026-09-16T14Z** on that venue; recording started then.
- **09-18T17:15Z onward from `fulltape/markets.json`** -- it stops there, so
  every outcome here is derived from the index tape instead, validated against
  markets.json where they overlap (max relative error 4e-5, which is the
  published strike's own rounding).

Multiple looks: roughly 80 cells were inspected across this file, so the
significance bar would be 0.05/80 = 0.0006. **Nothing here is claimed as a
significant positive.** The only positive-looking numbers (the winner-side ask
table, the 66 sub-$1 packages) are explicitly not claimed.

## 4. Solutions worth testing, in priority order

1. **Record polymarket.us, read-only.** `poly_us.py` already signs;
   `poly_close.py` already knows the market-slug scheme. One hourly-gzip
   recorder in the shape of `cdc_record.py` (books inside 7 minutes of close,
   5-min and 15-min crypto, seven coins). **Cost: another writer on a disk that
   is 21 GB from a hard collection stop** -- cap it; it is small beside
   `kalshi_data`'s 130 MB/hour. Validation after ~3 days: the exact F2 table --
   last quote before expiry, spread by seconds-left, and whether the
   near-certain side is ever buyable under 99c. It touches no live code and
   blocks nothing.
2. **Then price the pin there** with the F1 variance table. Any loss-rate claim
   must come from our own fills, never from that tape.
3. **Do not re-open Crypto.com** unless someone wants its BTC/ETH 3c mid-window
   market for a different strategy; it is access-blocked anyway.
4. **Nothing here should change the live bot.** No gate, brake or hedge change
   is proposed, so nothing here can block a hedge.

## 5. What a professional records that we do not -- and the one to add

We already record Kalshi's full book (71 GB of deltas), trades, ticker, the
1/sec CF settlement index, four constituent exchange books, and a second
prediction venue. Missing:

| not recorded | timescale of its signal | verdict for THIS strategy |
|---|---|---|
| perp funding rates, open interest | hours to days | **no** -- our bet is 15 minutes long and half-settled when we enter |
| futures basis / CME | hours to days | **no** |
| **exchange liquidation prints** (Binance `!forceOrder@arr`, Bybit `allLiquidation`) | **seconds** | the only one on our clock |
| on-chain flow / mempool | BTC blocks 10 min, ETH 12 s, exchange deposits move price over hours | **no.** For a 60-second average of an index built from exchange order books, the price is made on the exchanges we already tape, not on the chain |
| the oracle behind the other venues (Chainlink BTC/USD) | seconds | only if we go to Polymarket -- record it WITH that venue, not before |

**The one to add first is none of them.** We own 9.2 GB of Bitstamp books,
2.4 GB of Coinbase and 316 MB of Kraken that the brief itself calls barely
mined, and the disk is 21 GB from stopping the tape. Adding a feed before
mining those makes the real deadline worse.

**If one is added anyway, it is exchange liquidation prints** -- public,
WebSocket, and tiny beside the order-book tape. The reason is specific: our
guards already react to an index jump that HAS happened, but a liquidation
cascade is auto-correlated over tens of seconds, so a liquidation print is
evidence the move will CONTINUE through the remaining settlement seconds --
the fat-tail class `signature/` says no pre-entry feature separates. That is a
hypothesis; it would be tested on our own fills before anything gated an entry,
and it would gate nothing else, never a hedge.
