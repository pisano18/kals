# SECOND INCOME SCAN -- 2026-09-25 (written 03:35 UTC, jobs still running)

Read-only, GET-only. Nothing `--live`, no order on any venue, no process
touched, `kalshi_data` / `feed_data` untouched (read only). Every Kalshi call
was signed with `research/kauth.py` (GET-only by construction); every
Polymarket US call used the operator's existing read key through
`C:\kals\poly_us.py` (GET-only) or the public gateway. Times in this file are
UTC (repo convention). Scratch under
`C:\Users\Joe\AppData\Local\Temp\claude\C--kals-repo\47b37ac1-655c-4d72-a81b-a48e9625d5bd\scratchpad\` (`SCR` below), prefix `scan_`.

**Handed back early at the coordinator's request.** Four measurement jobs are
still running (section 7 gives each one's log and the single command that
reads it). Everything below is what was measured up to 03:33 UTC.

Resource check at 03:33 UTC: `kalshi_collector.py` (pid 2532788, 42 MB) and
`crypto_feeds.py` (pid 105352, 36 MB) alive; the six scan processes use
29-100 MB each (largest: the enumeration at 100 MB); free RAM 1.9 GB; free
disk 15.4 GB (guard 6 GB). The enumeration's raw file
`SCR\scan_enum_markets.jsonl.gz` is 236 MB and growing -- delete it once
`scan_classify.py` has run.

---

## 1. Ranked answer -- realistic dollars a day, with the evidence

Realistic = what OUR bank (~$900, size = bank/11.76 = ~76 contracts on the
15-minute markets, 1 contract on hourly BTC per `SCALING_PLAN_2026-09-24.md`)
could plausibly capture. "Tape" numbers are what somebody bought, never our
fill or loss rate. Where a number is unknown it says unknown.

| # | family | realistic $/day | what was measured | cheapest test, and days |
|---|---|---|---|---|
| 1 | **Polymarket US BTC 15-min and 1-hour up/down** -- the SAME contract as `KXBTC15M` (same BRTI 60-s average, same strike to the cent, same ">= strike pays Up" tie rule; verified on the 03:15Z close: Kalshi strike 84194.85, Polymarket price-to-beat 84194.85) | **$0-15 incremental, unknown** | 269 closed 15-min windows since launch 09-22 15:15Z: median 4,423 shares traded per window, top-10% 117,804, max 223,812, 126 of 269 windows with ZERO trades (mostly 02Z, 16Z, 20Z hours). Live book at 03:10Z (5 min out): 43 bid levels / 6 ask levels, 9,500 bid shares and 6,300 ask shares resting -- a real book, roughly 1/10th-1/50th of Kalshi's. One window joined second-by-second on the real-time feed (03:30Z close, decided early by 10 bps): the winner was NOT buyable at <= 98c on either venue inside 90 s. Taker fee 0.0695·p·(1-p) (Kalshi's is 0.07); **makers get PAID 0.0125·p·(1-p)** (Kalshi pays makers nothing). | Already running: `SCR\scan_poly_ws.py` records the real-time book + every trade. Rerun it for 3 days across US hours (`python SCR\scan_poly_ws.py 259200`), read with `python SCR\scan_poly_ws_report.py`. Pass bar (written now): inside 45 s with >= 10 bps margin, the winner offered at <= 98c on >= 15% of seconds with median size >= 50 shares, and no window where Polymarket's touch lags Kalshi's by > 3 s on a >= 5c move. Then a 1-contract live test with per-order sign-off. |
| 2 | **Kalshi hourly + 5 PM strike ladders on ETH / SOL / XRP / DOGE** (`KXETHD`, `KXSOLD`, `KXXRPD`, `KXDOGED`) and the hourly **bracket** series (`KXBTC`, `KXETH`, ...) -- same rule and same index feed as `v-btcd1` | **$0-10, low** | One close measured against the index (03:00Z, 11 PM ET): winning-side supply at <= 98c with >= 10 bps margin inside 45 s was ZERO on every ladder; at 46-120 s BTCD offered 452-1,672 contracts per poll at 94-98c, SOLD 4-8, ETHD/XRPD/DOGED 0. The 5 PM ladders (50 rungs) are open all day with 1-2c spreads on 10-21 rungs. Huge 99c asks on SOLD/ETHD (37,203 per rung on 14-28 rungs) are one maker selling the LOSING side at 99c -- worthless, not supply. | The bot already has the code path (`--series KXBTCD --series-size 1`). Add `--series KXETHD` etc. to the paper arm for 7 days and read fired/no_offer per close. |
| 3 | **Crypto one-touch monthlies** (`KXBTCMAXMON`, `KXETHMAXMON`, `KXSOLMAXMON`, `KXXRPMAXMON`, `KXBTCMINMON`) -- once the 60-s trimmed mean of the index crosses the strike, YES is decided and Kalshi closes the market early; we hold the same index at 1 s | **$2-10, needs data** | 33 YES-settled markets Jul-Sep: YES bought at <= 97c inside the last 10 min before the early close = 16,053 contracts, $3,738 gross (tape); last 30 min $29,760; last 2 min only $13. Concentrated in 3 events (BTC $67.5k on 08-19, XRP $1.60 on 08-25, ETH $2,750 on 09-21). ~16 crosses a month across the 4 coins. The daily/weekly versions (`KXBTCMAXD`, `KXBTCMAXW`, `KXDOGEMAXW`) have 0 open and 0 settled markets -- dead series. | Replicate the rule from the tape (rolling 60-s 20% trimmed mean, minute checks) for the 09-03 and 09-21 crosses and time the cross against the trades; then a quake-style watcher for 14 days. |
| 4 | **Ladder monotonicity / both-sides arbitrage** on the crypto ladders | **$0 so far** | 1,496 polls of 27 events (every rung's bid/ask/size every 30 s, every 5 s in the last 2 min) between 02:55Z and 03:33Z: **0 candidate violations, 0 confirmed.** Still running to ~07:25Z. | Read `SCR\scan_ladder_violations.jsonl` when it ends; if still 0 after 4 h, kill. |
| 5 | **Sports markets, final minute** (ESPN-settled game winners; hundreds of games a week) | **unknown, unmeasured** | Could not measure from this box: ESPN's public scoreboard API returns HTTP 403 here (two header variants). Kalshi lists them (`KXNFLGAME`, `KXMLBGAME`, `KXNCAAFGAME`, spreads, totals); Novig offers the same games in-play with a taker fee of 0.03·p·(1-p) and 50% maker credit. | Needs a live score feed first (a paid odds/score API or the league feeds); then poll the Kalshi book in the last 2 minutes of 20 games. 3 evenings. |
| 6 | **Trump Truth Social weekly post count** (`KXTRUTHSOCIAL`, Roll Call count, weekly) -- a running public count that locks strikes as it passes them | **<$1** | 10 open markets, $26,819 volume in 24 h, one close a week. | Not worth a build alone. |
| 7 | **S&P 500 / Nasdaq-100 daily close** (`KXINXU`, `KXNASDAQ100U`, `KXINX`, `KXNASDAQ100`) | **$0 -- kill** | Settlement is ONE value at ONE instant (THEORY 1b); strikes are $5 apart on ~7,700 (6.5 bps) while the closing auction moves more than that; the only "public early" data is the exchange imbalance feed, which is a paid pro feed, not public. Books: 5,000 x 5,000 at 52/54c (a market maker), $1,689 volume in 24 h for 200 markets. | none |
| 8 | **Crypto.com (CDNA) 5/15/20-min binaries** | **$0 -- killed 09-16, re-checked** | Prior kill stands (`RESULTS_cdna_venue.md`: spreads 8-24c minutes before expiry, book dies at 42 s). Fresh check 03:10Z: of 5,000 listed instruments, 0 BTC binaries expiring inside 2 h (only FX 5-minute ones at that hour). | none |
| 9 | **Rain / gas / daily temperature / ERCOT / air quality / box office / app rankings / Google Trends** | **$0-3** | Rain, gas, daily temperatures killed earlier (IDEAS_2026-09-24 section 3). Hourly temperature and quakes have watchers running (OPEN_WORK A5/A6). Air quality (6 series), box office (4), app rankings (23), Google Trends (25), Wikipedia (2), river levels (10): every one is `one_off` or `custom` -- no cadence, no repeatable close. ERCOT peak (`KXTXERCOTPEAKD`): 1 close a day, $24,311 volume in 24 h, still needs-data as before. | none new |
| 10 | **ForecastEx / Robinhood-Rothera / PrizePicks / Sporttrade / Gemini** | **$0 -- kill** | Section 5. | none |

**The single best one to test first: #1, Polymarket US.** It is the trade the
bot already makes, on a second book, with the same feed we already hold, the
same fee, and a maker rebate Kalshi does not pay. The recorder is running now;
the 3-day run and its bar are written above.

**Cross-venue "same contract, two prices" arbitrage between Kalshi and
Polymarket US: not found in real-time data.** The cached public gateway showed
packages costing $0.89-0.99 for a $1.00 payoff, but that gateway's quotes
refresh only every ~30 s (observed: identical bid/ask/size for 28-30 s while
Kalshi's book moved 10c) and every such "arb" vanished on the real-time feed:
one window joined second-by-second, package cost >= $1.00 at every second but
one (0.9960 at 75 s out, 0.18c edge, on a decided market). Not a $ source
until 3 days of real-time data say otherwise.

---

## 2. Polymarket US -- what it is, what is allowed, what is not

**This corrects the 09-06 / 09-24 record.** `CROSS_VENUE.md` and
IDEAS_2026-09-24 kill #10 said polymarket.us lists no short-dated crypto
(shortest 36.8 h). That was true on 09-06; **since 2026-09-22 15:15Z it lists
BTC 15-minute and 60-minute up/down windows continuously**, and its docs
describe hourly/daily/weekly above-below ladders and price ranges (not yet
listed: at 03:00Z the active crypto list was 54 hand-listed long-dated
markets + 1 live 15-min + 1 live 1-hour window).

What exists and how it settles (docs: https://docs.polymarket.us/trader-guide/crypto-schema.md , https://docs.polymarket.us/faqs/crypto-faqs.md ; verified against live market objects):
- Up/Down 15m and 1h, slug `cpc-btc-updown-15m-YYYY-MM-DD-HHMMz`. "Up if the
  price at the end is greater than or equal to the price at the start; each
  price is the simple average of the 60 BRTI prints in the last minute before
  that time, rounded to 2 decimals." Identical to `KXBTC15M` (rule text read
  from Kalshi's market object: "at least the simple average of the sixty
  seconds of CF Benchmarks' BRTI before ..."). Strike identity verified on the
  03:15Z close (both 84194.85). Only BTC so far. 15-min windows are listed
  ~12 h ahead, 1-hour ~24 h ahead; trading stops at the window end; the
  instrument expires 30 min later.
- Fees (https://docs.polymarket.us/fees.md): taker `0.0695 x contracts x p x (1-p)`;
  **maker rebate `0.0125 x contracts x p x (1-p)`** (paid to the maker, not
  charged). At 97c: taker 0.20c, maker earns 0.036c. Banker's rounding to the
  cent per order. Volume rebates for takers over $250k/month.
- API: public gateway `https://gateway.polymarket.us/v1/markets` (no key,
  20 requests/s per IP) gives best bid/ask but is a **cached snapshot
  refreshed every ~30 s** (measured); `/v1/markets/{slug}/book` and `/bbo`
  exist only after a window has traded (404 before). **Real-time data needs
  the key: `wss://api.polymarket.us/v1/ws/markets`** with the same Ed25519
  headers `poly_us.py` uses; full book on every change plus every trade with
  maker/taker side. Working recorder: `SCR\scan_poly_ws.py` (14,800 frames in
  17 min at 03:33Z). Orders (not used): `ORDER_TYPE_LIMIT/MARKET`, time in
  force `IMMEDIATE_OR_CANCEL`, `FILL_OR_KILL`, `GTC`, `GTD`, `DAY`, and a
  `participateDontInitiate` post-only flag; 20 requests/s per key; a 5-second
  stopgap rejects orders the exchange cannot process in time. Docs:
  https://docs.polymarket.us/api-reference/orders/create-order.md ,
  https://docs.polymarket.us/api-reference/websocket/markets.md ,
  https://docs.polymarket.us/api-reference/rate-limits.md
- Volume (public gateway BBO on all 349 closed windows since launch):
  15-min: 269 windows, 9.32 M shares total, median 4,423 per window, top-10%
  117,804, max 223,812, 126 zero-trade windows. 1-hour: 80 windows, 1.11 M
  shares, median 0, top-10% 55,594. By hour of window start (UTC): median
  25-70k shares at 00-09Z and 13-19Z, 21-22Z; near zero at 02Z, 16Z, 20Z and
  10-12Z. For scale, `KXBTC15M` runs ~315k contracts per market.
- Live book, 03:15Z window at 5 min out: 0.93/0.94, 43 bid levels (9,500
  shares) vs 6 ask levels (6,300 shares). Real-time feed at the 03:30Z close:
  the decided side had 1,800-7,200 shares offered at 1c on the LOSING side and
  no bid on the winner -- same shape as Kalshi at the same seconds.

**Allowed / not allowed.**
- Polymarket US is QCX LLC, a CFTC-designated contract market (the licensed
  US entity; polymarket.com is geoblocked for US persons and is not proposed).
  KYC'd US customers, USD. The operator's account exists and answers the
  positions endpoint (empty positions at 03:20Z); the balance endpoint
  variants all returned 404 from the API, so the balance is unknown here.
- **Crypto contracts:** no state restriction is stated in the crypto FAQ or
  the market objects. **Sports contracts are the restricted class**: Nevada
  obtained a temporary restraining order (Jan 2026), Massachusetts and
  Tennessee have acted or announced action, and "well over a dozen states"
  had cease-and-desist letters or suits against prediction platforms by
  mid-2026 -- these target sports event contracts (sources:
  https://www.saturdaydownsouth.com/prediction-markets/polymarket-promo-code/legal-states/ ,
  https://deadspin.com/prediction-markets/polymarket/legal/ ,
  https://predscope.com/guide/polymarket-us ). Whether the operator's own
  state can trade crypto contracts is answered by his app, not by the API.
- Perpetuals/leverage products announced by Polymarket are not on the US
  venue's market list read tonight.

**Why it matters beyond "a second book":** the same settlement print decides
both venues, so a YES on one and a NO on the other is a true riskless package
when the two asks sum under $1.00 minus fees. Tonight's real-time join found
none. The pin trade itself (buy the decided side at <= 98c inside 45 s) is
untested there -- the one recorded window was decided early with no supply on
either venue. The 3-day recording decides it.

---

## 3. Kalshi: every open series, by settlement mechanism (COMPLETE -- see 3b for the finished count)

`SCR\scan_enum.py` pages `GET /markets?status=open&limit=1000`. At 03:33Z it
had read **4,730,000 open markets in 881 series** (37 minutes) and was still
paging -- almost all of the count is multivariate parlay combinations
(`mve_collection_ticker` set), which the aggregation skips. `GET /series`
returns 14,379 series in one call (no paging), each with
`settlement_sources`, `frequency`, `fee_type`. When it finishes:

    python SCR\scan_classify.py      # classes (a)/(b)/(c), top families by volume and cadence
    del SCR\scan_enum_markets.jsonl.gz

What was learned before it finished, from direct series probes (all GET):

- **Class (a), formula on a public feed we already hold (CF Benchmarks RTIs):**
  15-min up/down (12 series, live), Coin Race 15-min (live), hourly ladders
  `KXBTCD/KXETHD/KXSOLD/KXXRPD/KXDOGED` (188/300/300/75/55 rungs, 1c ticks,
  1-7c median spreads on the quoted rungs, hourly events appear ~1 h before
  close, none 02:00-05:00 ET), hourly brackets `KXBTC/KXETH/KXSOL/KXXRP/KXDOGE`
  (same rungs as ranges, 2-17c spreads), 5 PM daily ladders (50 rungs, open
  ~28 h ahead), monthly one-touch max/min (section 1 #3), weekly BTC-vs-ETH/
  SOL/HYPE (`KXBTCVSETH` etc.: 0 open markets tonight). Daily/weekly one-touch
  and `KXBTCVS*` are dead series (0 open, 0 settled).
- **Class (a), other public feeds:** Pyth (15-min/hourly/daily/weekly gold,
  silver, WTI, natgas, EURUSD, USDJPY, GBPUSD) -- instant settlement, killed
  09-17/18 (IDEAS kill #4); "Google Finance" equity indices (`KXINX*`,
  `KXNASDAQ100*`, `KXDJI`, `INXW`) -- instant, kill (#7 above); The Weather
  Company temperature/rain (killed or under watch); AAA gas (killed); ERCOT
  load (needs-data); NY Fed SOFR daily (`KXSOFRD`, a next-morning release, not
  a live feed); Roll Call Truth Social count (weekly).
- **Class (a), sports scores (ESPN / league official):** the largest family
  by series count (1,000+ series) -- unmeasured here (feed blocked, #5).
- **Class (b), discrete events:** economic releases (all close BEFORE the
  number, killed before), USGS quakes (watcher running), awards, elections.
- **Class (c):** news-consensus and council markets -- out of scope.

---

## 4. Ladder arbitrage, measured live (RUNNING, ends ~07:25Z)

`SCR\scan_ladder.py`: every 30 s (5 s inside the last 120 s) it pages every
rung of every open event in 12 crypto ladder/bracket series and looks for:

- MONO: for two rungs K_low < K_high, `yes_bid(K_high) > yes_ask(K_low)` --
  buy YES on the LOWER strike at its ask, sell YES on the HIGHER strike into
  its bid; the position pays 0 or 1 and the credit is banked up front, so it is
  riskless. (The task text had the legs the other way round -- buy the high
  strike, sell the low -- which is a strangle that LOSES when the settle lands
  between the strikes; the scanner counts the riskless direction.)
- BOTH: `yes_ask + no_ask < 1.00` on one rung.
- BRKT: mutually exclusive brackets whose asks sum under 1.00 or bids over 1.00.

Any candidate seen in the batch quotes (which Kalshi's REST `/markets` serves
tens of seconds stale, CROSS_VENUE 7.4) is re-read with fresh `/orderbook`
calls on both legs and then followed every 3 s for up to 60 s to bound its
persistence.

**Result at 03:33Z: 1,496 polls, 27 events (9 that closed at 03:00Z, 9 closing
04:00Z, 9 five-PM ladders), 183 polls inside the last 2 minutes -- 0 candidate
violations, 0 confirmed, $0 available.** The books are consistent: on the
quoted rungs (10-21 of the 50 five-PM rungs; 4-15 of the hourly rungs) spreads
are 1-7c and every rung's ask sits above the next rung's bid. Latency a bot
would need: irrelevant until a violation is ever seen. Persistence: nothing
to time.

Winning-side supply on the 03:00Z close (index-joined, `scan_ladder_join.py`),
average per poll of rungs / contracts offered on the WINNING side at <= 98c
with the projected settle >= 10 bps clear of the strike:

| series | 0-45 s | 46-90 s | 91-120 s |
|---|---|---|---|
| KXBTCD | 0 / 0 | 0.4 / 452 | 1.5 / 1,672 |
| KXBTC (brackets) | 0 / 0 | 0.2 / 20 | 1.4 / 132 |
| KXSOLD | 0 / 0 | 0.4 / 4 | 1.0 / 8 |
| KXETHD, KXXRPD, KXDOGED, KXETH, KXXRP, KXDOGE | 0 / 0 | 0 / 0 | 0 / 0 |

One close at 11 PM ET is one observation; the 04:00Z and 05:00Z closes are
being recorded (a scheduled job writes `SCR\scan_ladder_join_0400.txt` and
`SCR\scan_ladder_report_0400.txt` after 04:03Z).

---

## 5. Other US venues -- one paragraph each

- **Robinhood prediction hub** -- routes to KalshiEX, ForecastEx, Rothera (its
  own CFTC exchange with Susquehanna) and NADEX/CDNA; the crypto pages are
  Kalshi's contracts verbatim ("BTC price on Sep 24, 2026 at 11pm EDT",
  "XRP 15 min"), so it is Kalshi's book with an extra $0.01/contract
  commission. Rothera itself carries World Cup and baseball contracts only,
  no crypto, no public API. Kill as a second book (already killed 09-06).
  https://robinhood.com/us/en/newsroom/the-world-cup-is-now-trading-on-robinhood-and-rothera/ ,
  https://www.axios.com/2026/09/08/robinhood-crypto-og-kalshi-prediction-markets
- **Crypto.com / CDNA** -- public REST (`api.crypto.com/dcm/v1/public/...`),
  5/15/20-minute binaries on a 60-s trimmed-mean index; killed 09-16 on
  measured 8-24c spreads and a book that dies at 42 s; tonight 0 BTC binaries
  expiring within 2 h. `C:\kals\cdc_record.py` keeps recording it. Kill.
  `results/RESULTS_cdna_venue.md`
- **ForecastEx (via Interactive Brokers)** -- economic releases, climate,
  central-bank rates; weekly/monthly/quarterly/annual only; $0.01 exchange fee
  per YES/NO pair; positions earn a coupon (Fed funds minus 0.5%); IBKR Web API
  can trade them. No sub-day cadence, no live feed to be faster than. Kill.
  https://www.interactivebrokers.com/campus/trading-course/forecastex/
- **Novig** -- sports-only peer-to-peer exchange, CFTC approval mid-2026,
  nationwide rollout planned; API-first (Ed25519/P-256 signed REST +
  WebSocket, OpenAPI spec); in-play trading is offered (`OPEN_INGAME` state,
  all resting orders voided at game start); taker fee `0.03 x p x (1-p) x N`
  on game markets (less than half of Kalshi's), makers earn 50% of the taker
  fee. No settlement source named. Relevant only for a sports final-minute
  strategy or a Kalshi-vs-Novig same-game pair; needs an account and a score
  feed. Needs-data. https://docs.novig.com/api/concepts/fees.md ,
  https://docs.novig.com/api/concepts/event-lifecycle.md
- **PrizePicks predictions** -- Kalshi provides "the markets, pricing, and
  resolution"; it is Kalshi's book. Kill.
  https://www.goal.com/en-us/betting/prediction-market-apps/bltc49cdaecf6750c3e
- **Sporttrade** -- exited all US online markets 2026-05-25 pending its CFTC
  application. Kill. https://www.yogonet.com/international/news/2026/05/19/121042-sporttrade-to-exit-us-online-sports-betting-markets-while-awaiting-cftc-decision
- **Gemini Predictions** -- killed 09-24 (empty book at the seconds that
  matter). Unchanged.

---

## 6. Creative candidates (task 4) -- kept / killed

- **KEPT, needs data: crypto one-touch monthlies** (section 1 #3). We hold the
  index that decides them at 1 s; Kalshi's early close arrives minutes to
  hours after the cross (three markets closed in the same second on 08-19,
  i.e. batch processing). Tape: $3,738 gross at <= 97c in the last 10 minutes
  before close over 33 crosses. The rule (rolling 60-s 20% trimmed mean,
  evaluated each minute) is replicable from the tape; cross time vs trade time
  is the measurement. Watcher pattern: `research/quakewatch.py`.
- **KEPT, needs a feed: sports final minute** (section 1 #5).
- **KEPT, tiny: Truth Social weekly count lock** (#6).
- **KILLED: S&P/Nasdaq daily close "last 30 s" pin** -- instant settlement,
  strikes finer than the auction noise, imbalance feed not public.
- **KILLED: SOFR daily** -- a 8 AM next-day release, nothing to be early to.
- **KILLED for cadence: air quality, box office, app rankings, streaming
  charts, Google Trends, Wikipedia, river levels** -- every series is
  `one_off`/`custom`, no repeating close.
- **Already covered elsewhere:** hourly temperature (`wxwatch.py`, supply ~0),
  quakes (`quakewatch.py`), ERCOT (needs 5-minute load history), rain/gas/daily
  temperature (killed 09-24).

---

## 7. Jobs still running -- log and the one command that reads each

All under `SCR`. None writes outside the scratchpad. Each stops on its own at
the time shown; the `.stop` files stop the two newer ones early.

| job | what it records | ends | read it with |
|---|---|---|---|
| `scan_enum.py` (pid 2850892) | every open Kalshi market, aggregated per series | when paging ends (4.73 M markets at 03:33Z) | `python SCR\scan_classify.py` (progress: `tail -1 SCR\scan_enum.out`) |
| `scan_ladder.py` (pid 2850500) | every rung of 12 crypto ladder/bracket series, 30 s / 5 s late; violations confirmed with fresh books | ~07:25Z | `python SCR\scan_ladder_report.py` ; `python SCR\scan_ladder_join.py` ; violations in `SCR\scan_ladder_violations.jsonl` ; log `SCR\scan_ladder.log` |
| `scan_poly_ws.py` (pid 2854376) | Polymarket US real-time book + trades, BTC 15m/1h | ~06:53Z (or `SCR\scan_poly_ws.stop`) | `python SCR\scan_poly_ws_report.py` (joins to Kalshi's ticker tape and BRTI, per second) |
| `scan_poly2.py` (pid 2854660) | Polymarket cached-gateway quotes vs Kalshi orderbook, 2 s late | ~07:07Z (or `SCR\scan_poly2.stop`) | `python SCR\scan_poly_report.py` -- remember the gateway is a ~30 s cache |
| `scan_poly_book.py` (pid 2856100) | Polymarket cached full depth vs Kalshi depth-10 in the last 75 s | ~07:09Z (or `SCR\scan_poly_book.stop`) | `SCR\scan_poly_book.jsonl.gz` (raw; no report script yet) |
| `scan_poly.py` (pid 2852248) | superseded first version; its gateway `/bbo` calls 404 until a window trades -- harmless, ignore | ~07:12Z | nothing |
| scheduled shell job | after 04:03Z reruns the ladder join/report and the Polymarket join | ~04:05Z | `SCR\scan_ladder_join_0400.txt`, `SCR\scan_ladder_report_0400.txt`, `SCR\scan_poly_ws_report_0400.txt` |

Also on disk: `SCR\scan_poly_census.json` (349 Polymarket windows' shares
traded / settlement), `SCR\scan_poly_ws_report_0330.txt` (the one joined
window), `SCR\scan_enum_series.json` (once the enumeration ends).

---

## 8. What would have to be true for the good numbers to be artefacts

- Polymarket volume: `sharesTraded` was read from the gateway BBO of expired
  windows; if that field counts both sides of each match, halve every volume
  number. Not checked.
- The one-touch $3,738: counted from `taker_side == yes` trades in the 10
  minutes before Kalshi's early close; if the cross happened AFTER those
  trades (buyers anticipating, not lagging), the money was risk money, not
  lock money. The tape join decides it.
- The ladder "0 violations": the batch quote is stale by tens of seconds, so a
  violation living under ~30 s could be missed between polls; the 5-s cadence
  in the last 2 minutes narrows that only there.

---

## 3b. Enumeration finished (03:40 UTC): 5,693,069 open markets in 4,196 series

`scan_enum.py` ended after 5,694 pages (45 min). The count is dominated by
multivariate parlay combinations, which were skipped in the per-series
aggregation. The 236 MB raw file was deleted; the per-series summary is
`SCR\scan_enum_series.json` (4.5 MB) and the classification output is
`SCR\scan_classify.txt`. Classes by keyword over `settlement_sources` +
`rules_primary`: sports score / league official **1,022 series**; formula on a
public feed **498**; discrete public event **1,376**; news / council **245**;
unclassified **1,055** (mostly elections, entertainment, e-sports, AI
leaderboards).

What the finished list changes in section 1:

- **Sports is the biggest mechanically-settled pool on Kalshi by a factor of
  ten and it is unmeasured here.** 24-hour volume: `KXNFLTD` (touchdown
  scorer props) $7.45 M, `KXNCAAFGAME` $7.22 M, `KXMLBGAME` $6.64 M,
  `KXNCAAFSPREAD` $3.08 M, `KXNCAAFTOTAL` $2.28 M, `KXMLBTOTAL` $1.81 M,
  `KXNFLGAME` $1.03 M -- against `KXBTCD` $1.40 M and `KXBTC15M` $0.95 M.
  All settle on a final score published by ESPN / the league. This is why
  item #5 (final-minute pin on a live score feed) is the one unmeasured
  family that could matter; it needs a score feed this box cannot reach
  (ESPN 403) and a study of who is selling in the last minute.
- **Among the crypto ladders only ETH has real volume besides BTC:** `KXETHD`
  $109k/24 h, `KXBTC` brackets $11k, `KXSOLD` $10k, `KXXRPD` $5.8k, `KXHYPED`
  $1.3k, `KXDOGED` $0.9k, `KXBNBD` $0.2k. Item #2 is therefore "add KXETHD",
  not the whole set.
- **Highest cadence on the exchange:** `KXNASDAQ100U` (2,800 open markets,
  7 closes in the next 24 h) and `KXINXU` (420, 7 closes) -- the hourly
  equity ladders, instant settlement, already killed; then `KXRAIN` (4 closes)
  and the crypto ladders (2 each, 03:00Z and 04:00Z at the time of the read).
- **New continuous-public-number families found, all small or slow:**
  `KXRT` (Rotten Tomatoes score at a date; $766k/24 h across 223 markets, but
  one close a week and the number only moves when reviews land),
  `KXTRUMPAPPROVE` (RealClearPolitics average, $55k, 1 close/24 h),
  `KXNETFLIXRANKSHOW/MOVIE` (weekly Netflix chart, $17k each), `KXHORMUZWEEKLY`
  (IMF PortWatch ship count, $45k, weekly), AI-leaderboard shares
  (`KXANTHSHARE`, `KXGOOGSHARE`, `KXANTHVSPEND` ..., OpenRouter / Vercel
  dashboards, $25-44k, one-off dates). None has a sub-day close; none earns a
  test before #1-#3.
