# B lost-races -- orders we sent that did not fill, and whether a latency fix wins them

**Status: COMPLETE** (2026-09-22 ~17:30Z). Read-only: nothing started, stopped or edited
outside this file and scratchpad `missed/lost-races/`. Network: ~80 public, unauthenticated GETs
to the order host over ~3 minutes (timing only).

Sources: all 126 `results/pinrun-live-*.jsonl` (1,219 entry `order` records, 2026-09-08 07:59Z ..
2026-09-22 15:59Z; 993 reached the exchange; hedges are separate `hedge` records and none are in
this set); send time to the ms for EVERY order from `client_order_id` (`pin-<ms>-..`, equal to
`t_ms_send` to 0-1 ms on the 13 v-safety1 orders); tape `trade` channel on exchange `ts_ms`
(289 hours streamed; 3 hours corrupt: 20260909T13, 20260915T13, 20260915T20); `ticker` channel
(1 update/s, so used only for "was it offered"); outcomes = Kalshi result (fulltape + ledger +
`settled` rows, 21,707 tickers, 0 conflicts). "$" on anything we did NOT fill is a hypothesis
(what the offer would have paid at Kalshi's result), never a loss rate of ours.

## The answer in three lines

1. **The races we lose are not a pool of good deals.** Offers another bot also wanted are, on our
   OWN fills, no better than offers nobody wanted; the specific races a realistic speed-up would
   have won lost at 3 of 61 closes and would have netted **-$96 in 14 days**. A faster bot also
   pays MORE when the book is collapsing under us. No latency fix here is "more money at no risk".
2. **The real missed-deal leak found is a counting bug, not speed:** five refusal gates run AFTER
   the per-market attempt counter, so a market can be locked out for the rest of the close without
   a single order sent. 32 of 34 lockouts since 09-17 were this. Upper bound **+$23 on 514
   contracts over ~5 days**; the fix blocks nothing.
3. **Side finding (lose-less):** every ~21 s the trading loop -- entries AND the hedge pass --
   freezes for **0.84-1.0 s** doing 11 sequential market-list GETs. Unpriced; cheap to fix.

## 1. Findings, ranked by dollars

### L1. Winning more races would NOT have made money -- the lost races are ordinary-to-worse offers, and speed costs money on collapse fills.

**Claim.** Of 993 orders that reached the exchange, 208 filled nothing and 86 filled part
(8,184 contracts unfilled; ~606 a day since sweep-depth, ~671 a day post-fix). A realistic
speed-up wins about a third of the races lost to another taker, and those won races are not
profitable on any measure we have.

**Who took the offers (tape, exchange time; our own fills excluded).**

| zero-fill orders with tape (202) | orders | closes | lost closes | unfilled | at ask seen $ |
|---|---|---|---|---|---|
| A: another taker bought our side at <= our limit between our send and our arrival | 104 | 86 | 3 | 3,070 | +6.80 |
| B: another taker had already taken it BEFORE we sent (median 61 ms before) | 83 | 72 | 3 | 2,723 | +29.44 |
| C: vanished with no trade (maker pulled) | 13 | 13 | 1 | 217 | -4.92 |
| our own earlier order took it | 2 | 2 | 1 | 40 | -19.01 |

Partial fills with tape (83): A 54 (51 closes, 1 lost, -$80.61 -- mostly BNB 09-19 12:30 ET),
B 22, no rival trade 7. So **~93% of lost races are lost to another taker, not to a maker pulling.**
The rival is usually ONE order (36 of 61 zero-fill A-races had a single competing order in the
window), median 30 contracts, as large as ours or larger in 38 of 61. Its first trade lands a
median **10 ms after our send stamp** (p10 -16, p90 +57): they react to the same moment we do
(rival trades cluster 0-200 ms into the second; the index print reaches Kalshi at +35-50 ms) and
simply get there first.

**Our timing (measured).** Our order reaches the exchange a median **72 ms after send** (p10 40,
p90 98; 755 of 763 filled orders found on the tape); the reply comes back ~20 ms later (p10 14,
p90 28 on most days). We lose A-races by a median **64 ms** (zero) / **66 ms** (partial).

| lost by at most | 11 ms | 25 ms | 43 ms | 54 ms | 79 ms |
|---|---|---|---|---|---|
| zero-fill A-races (of 104) | 5 | 13 | 35 | 45 | 67 |
| partial A-races (of 54) | 5 | 8 | 19 | 24 | 36 |

**What a speed-up would have won** (rival trades inside the saved window, priced at the rival's
price, fee included, Kalshi result; own orders' markets, tape-priced -- HYPOTHESIS):

| speed-up | races won | closes | lost closes | contracts | $ over 14 days |
|---|---|---|---|---|---|
| 11 ms (log after the POST) | 15 | 14 | 1 | 213 | -14.52 |
| 43 ms (keep the connection open) | 67 | 61 | 3 | 1,318 | **-96.11** |
| 79 ms (both + event-driven loop) | 99 | 88 | 3 | 2,004 | -78.55 |

The sign is set by 1-3 losing closes (NEAR 09-08 20:45 ET, DOGE 09-10 18:15 ET, HYPE 09-21
18:15 ET) and flips with ~10 ms of estimation error on single races; an earlier arrival estimator
gave -$45 at 43 ms. **Robust part: there is no sign of profit, and the won-race closes lost 3 of
61 (4.9%) against 2.5% on our fills.**

**Risk evidence from OUR OWN FILLS of the same kind** (the operator's rule): a fill is "contested"
when another taker bought our side at <= our limit within 100 ms of our fill.

| our fills | orders | closes | lost closes | contracts | naked $ | per contract |
|---|---|---|---|---|---|---|
| contested (a race we won) | 491 | 394 | 13 (3.3%) | 23,984 | +323.98 | +1.35c |
| nobody else there | 267 | 236 | 6 (2.5%) | 11,522 | +136.80 | +1.19c |
| partial fills in a contested race | 55 | 52 | 2 (3.8%) | 1,218 | -70.05 | -5.75c |

One-sided Fisher (contested loses more): p = 0.39. So extra race wins would be ordinary fills at
~+1.3c a contract at best: at 43 ms, ~1,318 contracts x 1.3c = **~+$17 in 14 days (~$1.2/day)**
as the optimistic case, against the -$96 direct estimate.

**The cost side -- speed pays MORE in a collapse (own fills).** 28 fills (27 closes, 7 lost)
landed >2c cheaper than the ask we saw; being ~100 ms slow saved **$163.98** against the seen
price on them (plus $16.18 on 100 fills 0-2c cheaper). A faster order gives some of that back --
upper bound $164 in 14 days; the trade tape shows the price was often already down 30-80 ms
before our fill (DOGE 09-18: 12c at -70 ms; SOL 09-09: 17-23c at -30..-81 ms), so the true cost
of 43 ms is well under the bound, and it is not measured. And the F2 hypothesis (03: fills on
offers <100 ms old lose more) points the same way: a faster loop buys younger offers.

**Confidence.** High on the counts and timings (arithmetic on logged ms stamps and exchange
stamps; 755/763 own fills matched). Low on any dollar sign (1-3 losing closes decide it).
**Artefact checks done:** (a) our own fills were first counted as "rivals" -- 46 zero-fill
A-races had another of our orders on the market within 1 s; excluding all 758 own fills by
exchange stamp changed A 105 -> 104, so it was not the cause; (b) old NO orders' limit was first
read in YES terms (397 orders) -- fixed from the order body before any number above; (c) the clock
offset between bot and exchange is absorbed by calibrating arrival on nearby own fills; it shifted
on 09-10 and 09-16 (reply leg 54-68 ms those days), handled by a local median.

### L2. A refused candidate burns one of the market's three "orders sent" -- and three refusals lock the market out for the rest of the close. (+$23.38 upper bound, ~5 days)

**Claim.** `MAX_ATTEMPTS_PER_MARKET = 3` is documented as "orders SENT into ONE market in one
close, filled or not" (pinrun.py:2856). But `attempts_tk[(close_s, tk)] += 1` runs at
**pinrun.py:11359**, right after the signal dict is built, and **five gates fire after it without
sending anything**: `early_cheap` (11421), `early_dear` (11449, flag since removed),
`early_wide` (11452), `staged_none` (11459), `price_band` (11468). Every other entry gate is above
the increment. The loop runs at ~20 Hz, so three passes (~150 ms) of e.g. `early_wide` at tau 45
set tried = 3, and `market_attempts` then refuses that market for the rest of the close --
including the <=30 s window and any top-up of an early position. The per-close counter
`attempts[close_s]` (cap 24) is burned the same way (its cap has never fired).

**Evidence.** 42 `market_attempts` refusals (one per close-market) in all live logs. 8 are the
09-15 409 TRADING_BLOCKED hours (orders that got a 409 were sent). **Of the 34 since 09-17, 32 had
fewer than three real orders** (28 had none) and every one of those 32 had `early_wide`,
`early_cheap` or `staged_none` among its prior refusals. Example: BTC 09-18 04:15 ET --
`early_wide` 3 looks at tau 45, then `market_attempts` for 742 looks; no order was ever sent.
Tape (`ticker`, 1/s) after each lockout, tau 30 to 3: our side was offered at 90-98c in **15 of
34**; none of those 15 lost. One order at the cheapest such second, capped at 79 contracts:
**514 contracts, +$23.38** (upper bound: ignores the edge/confidence gates it would still face;
tape-priced -- hypothesis). The 4 locked markets that lost were never offered at 90-98c after the
lock, so the lockout did not protect us from them.

**Dollars.** <= ~$4.7/day, beside the post-fix +$1.52/close. Small, but it is a bug against the
code's own stated intent, and it removes a block rather than adding one.

### L3. Every ~21 s the trading loop -- hedge pass included -- freezes ~0.9 s on 11 sequential REST calls. (unpriced; lose-less)

**Claim.** `trade_loop` refreshes the market universe inline (pinrun.py:10704,
`if now - uni_at > 20:`): one `kauth.get("/markets", series_ticker=...)` per series, 11 series,
each on a brand-new TLS connection, one after another, with no tau condition. Timed from this box
the way the bot does it: **998, 837, 897 ms per refresh** (per GET 64-126 ms). The period is
20 s + the refresh, so its phase drifts ~1 s per close and lands anywhere: in each close's last
30 s the bot is blind for ~1.3 s on average (~4.5%). During that time no offer is seen, no order
sent, and **no hedge fires**.

**Dollars.** Entries: ~4.5% of the <=30 s window's volume, ~40-50 contracts/day x 3-6c =
~$1.5-2.5/day (arithmetic, not measured). Hedges: 03 found one second of hedge timing on the
collapse fills is the difference between -$8 and -$98 on that set; a 0.9 s blind spot 4.5% of
the time is a tail risk, not priced. **Not verified in logs:** nothing records loop-pass times,
and a <1 s stall leaves no gap in per-second `hedge_quote` records (checked: 7 held markets since
v-safety1, no gaps > 1 s).

### L4. Where the time goes between "decide" and "the exchange has it" (measured)

| step | ms | source |
|---|---|---|
| loop wake after a new offer / index print | 0-50 (fixed `time.sleep(0.05)` per pass) | code; young-level ages at decision peak 20-50 ms (281 exact) |
| decide -> send (signal record + print + sweep/taper reads + their records) | median 11 (1-32), n = 13 | v-safety1 `t_ms_decide`/`t_ms_send` |
| RSA-PSS signing | 0.5 | timed |
| new TCP connection | 20.7 (18-25) | timed, 10 samples |
| new TLS 1.3 handshake | 22.2 (19-30) | timed, 10 samples |
| request to CloudFront + exchange match | ~20-30 | send->fill 72 minus the above |
| send -> our fill on the tape | **72** median (40-98) | 755 own fills |
| send -> reply | 93-96 median, same for won and lost races | `latency_ms`, all orders |

No REST call sits between decide and send (`pintake.take` -> `ordercli.send` only). The whole
fresh-connection cost is paid on every order because `ordercli.send` uses
`urllib.request.urlopen`. A kept-alive GET timed at **28 ms vs 75 ms** fresh (~47 ms saved).
Orders in a pass are sent one after another (each blocks ~95 ms): 106 orders were the second in a
burst; zero-fill 24% vs 21% for first orders -- a small effect.

### L5. For bar B5: lost races explain about a tenth of the <=30 s volume fall

Per watched close (close_summary, deduplicated), orders at tau <= 30:

| era | closes | orders/close | contracts asked/close | filled/close | fill share |
|---|---|---|---|---|---|
| B 09-12 .. 09-20 04:00Z | 748 | 0.62 | 30.0 | 25.0 | 84% |
| post-fix 09-20 04:00Z .. | 238 | 0.28 | 13.9 | 10.2 | 73% |

Filled per close fell 14.8; at post-fix asking, the lower fill share accounts for 1.5 (10%).
**~90% of the fall is orders never sent.** (25.0 matches FREEZE's era-B 25.2; 10.2 vs its 9.7.)
B5 decides; this is input, not a verdict.

## 2. Refuted or not supported

- **"A slow step between decision and send"** -- no REST call, 11 ms median in-process. The cost
  is the per-order connection set-up (L4), not a step.
- **"Makers pull the offers we lose"** -- 13 of 202 zero-fills; ~93% are lost to another taker.
- **"The offers we lose are the good ones"** -- own fills of contested offers: +1.35c/contract,
  3.3% losing closes vs +1.19c, 2.5% uncontested (p 0.39). No better.
- **"Our own repeat orders cause the zero fills"** -- 2 of 202.
- **"Serial sending in a pass loses races"** -- 24% vs 21% zero-fill, n = 106.
- **"Hedges would gain from speed"** -- since hedge-slip, 5 of 5 hedges filled first try, paying
  $0.69 in total above the ask seen.

## 3. Could not measure, and why

- **The bot's own feed lag** (exchange stamp -> our book). Not logged. B-races (taken a median
  61 ms before our send, yet still on our book at decision) imply our book is often 30-100+ ms
  behind; not measurable per order.
- **What a faster order would have paid on the 28 collapse fills.** Needs `orderbook_delta`
  (~250 MB/hour) for ~26 hours; skipped to protect the live bot's CPU and RAM (free RAM
  0.92-1.5 GB throughout). Bound given ($164).
- **Loop-pass timing / the universe-refresh stall in live logs.** No pass timestamps are logged.
- **Whether a lockout market would have passed edge/confidence in the <=30 s window** -- needs
  the model's fair per second; L2's $ is an upper bound for that reason.
- 6 zero-fill + 3 partial orders fall in corrupt tape hours; 10 zero-fill markets have no outcome.

## 4. Candidate ways to grab missed deals without added risk

Ranked by what they are worth for their risk. None may gate a hedge; each says what it blocks.

1. **Count an attempt only when an order is SENT (L2).** Move the two increments at
   pinrun.py:11359 to just before `pintake.take` (live) / the paper book (paper). **Size:** ~7
   lockouts a day, up to +$23 per ~5 days (514 contracts, 0 of 15 offered lockouts lost --
   tape-priced hypothesis). **Risk evidence:** every contract it admits still passes every gate a
   normal fill passes, at the same size and budget; the 160-order runaway guard is unchanged in
   what it counts as intended (orders sent). **Blocks:** nothing; it removes a block. **Hedge:**
   untouched (own counter, `MAX_HEDGE_ATTEMPTS_PER_CLOSE`). **Validate:** a self-test that three
   `early_wide` refusals leave tried = 0; live, `market_attempts` refusals with < 3 orders sent
   must go to zero, and those markets' <=30 s fills are tracked as their own class on the ledger.
   A code change -- **after the freeze**, or now as a paper arm (the paper path has the same bug).
2. **Take the universe refresh out of the trading loop's critical time (L3).** Either skip it
   while any watched market has tau < 60 (the next close's markets are listed 15 min ahead), or
   run it in a background thread. **Size:** ~4.5% of the <=30 s window (~$1.5-2.5/day arithmetic)
   plus hedge timeliness in that 4.5%. **Blocks:** nothing; it defers a discovery GET by <= 60 s.
   **Validate:** log `uni_ms` (refresh duration) and the loop's max pass gap per close; bar = no
   pass gap > 200 ms inside tau <= 45. Logging it is freeze-legal now.
3. **Do NOT buy speed to win races (L1).** Keep-alive (-43 ms), logging after the POST (-11 ms)
   and an event-driven loop (-~25 ms) are all real, but on every measure the races they win are
   ordinary-to-worse offers (-$96 at 43 ms, 3 of 61 closes lost), and speed pays more on collapse
   fills (up to $164 back). The one use of keep-alive worth keeping in mind is L3 (a 0.9 s stall
   becomes ~0.3 s). If ever built, it needs: a warm connection only if used within N s, a fresh one
   otherwise, and on any send error a reconcile by `client_order_id` -- never a blind resend
   (a POST on a connection the server just closed is ambiguous; K2 already halts on odd replies).
4. **Log to make this answerable, freeze-legal:** per order the exchange stamp of the book's last
   delta (feed lag), the loop pass duration, and on each `market_attempts` refusal the count of
   orders actually sent. Blocks nothing.

Collectors at finish (~17:35Z): `kalshi_collector.py` pid 105304 (51 MB) and `crypto_feeds.py` pid 105352 (43 MB) alive; disk 27 GB free; free RAM 1.5 GB.
