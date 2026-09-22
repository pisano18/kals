# A -- supply-gap: what was offered at 90-98c on the model's side inside 30/45 s, what we bought, and why not the rest

**Status: COMPLETE (2026-09-22, ~19:1xZ).** Read-only throughout; nothing started, stopped or edited
outside this file and my scratchpad. At finish: `kalshi_collector` (105304) and `crypto_feeds`
(105352) both alive, free RAM 1.87 GB, free disk 27 GB. My own python peaked at 58 MB; RAM dipped to
0.71-0.99 GB twice while other sessions ran, so I stopped my second job and started nothing new
until it recovered.

**Window:** closes 2026-09-20 00:00 ET (04:00Z) .. 2026-09-22 ~16:20Z -- 236 watched closes.
**Sources:** supply = `orderbook_snapshot` + `orderbook_delta` rebuilt per market on the EXCHANGE
`ts_ms` (58 hours, 1,998 markets), cross-checked against the `ticker` channel; the model = pinrun's
own `fair()` through `pinsim.TapeIndex` (decision reproduction only); what we did = all 126
`pinrun-live-*.jsonl`; money = our OWN fills (785, with outcomes from Kalshi's ledger). n = closes.
**The tape is used only for what was OFFERED and what the market did. Every risk and every dollar
below is priced from our own fills** (CLAUDE.md rule 5). Scripts: scratchpad
`missed/supply-gap/` (logs, fairs, books, tsupply, compare, perday, analyze, attempts, final).

Model check: recomputed fair vs the bot's logged fair -- median |diff| 3e-6 on 155 post-fix signals
(same side 155 of 155), 0 on 4,039 refusals (p90 9e-5). Index-derived outcome matches Kalshi's
result 2,007 of 2,007 markets.

---

## 1. Findings, ranked by dollars

### A1. The <=30 s window did not stop buying -- what it buys stopped being OFFERED. Supply at 90-98c while our model is >= 99.5% sure is down ~54%, and it has been falling since 09-16, a day BEFORE the 45 s leg existed. ($ not recoverable: this is the ceiling on everything else here)

Same measure in both eras (tape `ticker`, exchange `ts_ms`, end-of-second touch on the side the
model favoured, model recomputed): markets per WATCHED close whose favoured side stood at 90-98c
with >= 1 contract at some second in tau 3-30 while the model was >= 99.5% sure.

| per watched close, tau 3-30 | steady era (09-13 02Z..09-17 13:05Z, 385 closes) | post-fix (09-20 04Z..09-22 16Z, 219 closes) |
|---|---|---|
| offered at 90-98c AND model >= 99.5% | **0.514** | **0.237** (-54%) |
| offered at 90-98c, any confidence | 0.839 | 0.603 (-28%) |
| we bought | 0.504 | 0.192 (-62%) |
| contracts offered (capped 50/market) | 21.9 | 9.2 |
| contracts we bought | 29.8 | 10.2 |

By ET day (`bought` = a <=30 s fill in that market):

| ET day | closes | offered & confident | offered any conf | we bought | model >= 99.5% market-seconds/close |
|---|---|---|---|---|---|
| 09-13 Sun | 95 | 0.684 | 0.926 | 0.516 | 243 |
| 09-14 Mon | 91 | 0.549 | 0.868 | 0.604 | 241 |
| 09-15 Tue | 69 | 0.522 | 0.942 | 0.493 | 239 |
| 09-16 Wed | 93 | 0.333 | 0.710 | 0.430 | 244 |
| 09-17 Thu (to 13:05Z) | 29 | 0.241 | 0.379 | 0.276 | 247 |
| 09-17 Thu (after) | 57 | 0.333 | 0.807 | 0.281 | 242 |
| 09-18 Fri | 95 | 0.305 | 0.663 | 0.211 | 244 |
| 09-19 Sat | 95 | 0.463 | 0.884 | 0.253 | 241 |
| 09-20 Sun | 92 | 0.293 | 0.587 | 0.207 | 244 |
| 09-21 Mon | 84 | 0.214 | 0.631 | 0.179 | 244 |
| 09-22 Tue | 43 | 0.163 | 0.581 | 0.186 | 243 |

- **The model is not less sure.** Seconds per close at >= 99.5% confidence are flat (239-247 every
  day of both eras). What changed is the PRICE at those seconds: when we are sure, the market is now
  at 98c+ or shows nothing.
- Splitting the -62% fall in markets bought at <=30 s: supply explains ~87%, capture (0.98 -> 0.81
  of what was offered) ~13%, half of that being markets the 45 s leg already held. **The capture half
  is NOT established** -- day by day bought/offered swings 0.55 to 1.29 (we also buy offers the 1/s
  ticker never samples). The supply half is: weekday medians 0.522 (09-14..16) -> 0.214 (09-18, 21, 22).
- **Baseline check** (the recurring bug here): measured against the MEDIAN steady day, not the best;
  and post-fix weekdays are below even the lowest full steady day (09-16, 0.333). Sunday vs Sunday
  0.684 -> 0.293.
- **Artefact check:** the ticker is a ~1/s sample and its message rate fell too (median messages per
  market in the last 60 s 39/37/36/35 -> 37/30/29). The post-fix half of this table is confirmed
  against the full order book (A3); the steady era is not (no book rebuild for it -- ~50 min of tape
  reading I did not have). Treat the direction as solid, the -54% as approximate.

### A2. The rule that decides whether ANY missed deal is worth chasing: at 95c or cheaper it survives even the bad end of our own loss rate; at 96c+ it does not.

Our own fills only, n = closes, Clopper-Pearson 95%:

| our <=30 s fills at 90-98c | closes | losing closes | loss rate | contracts | c/contract |
|---|---|---|---|---|---|
| lifetime | 393 | 9 | 2.29% [1.05, 4.30] | 21,938 | +2.01c |
| since the jump gate (09-15 01:39Z) | 156 | 2 | 1.28% [0.16, 4.55] | 13,524 | +2.65c |
| lifetime, 90-96c | 140 | 4 | 2.86% [0.78, 7.15] | 6,672 | +4.26c |
| lifetime, 96-98c | 303 | 6 | 1.98% [0.73, 4.26] | 15,266 | +1.03c |

Break-even loss rate by price (1 - price - fee): 92c 7.5%, 94c 5.6%, **95c 4.7%**, 96c 3.7%, 97c
2.8%, 98c 1.9%. Our lifetime rate's upper bound is 4.30%. **So a chased contract at 95c or below is
still positive even if our true loss rate is at the bad end of what we have measured; at 96c and
above it is not.** A price cap near 95c is what makes "grab more" risk-neutral instead of risk-adding.

Margin per contract from our own fills since 09-15 (90-98c): tau 0-10 s +3.91c (26 closes, 0 lost),
11-20 s +3.56c (52, 0), 21-30 s +1.83c (96, 2), 31-45 s +0.24c (152, 4). By price at <=30 s:
90-92c +8.1..8.8c, 92-94c +6.2..6.5c, 94-96c +4.2..4.9c, 96-98c +0.8..2.5c. Cells with zero losing
closes mean "no loss seen yet", not "safe" -- every cell is under the 30-close floor.

### A3. The whole missed-deal pile is small: 925 contracts at <=30 s and 600 at 31-45 s over 236 closes, about $25 at our own margins (~$10 a day). Two thirds of the <=30 s pile is the close's contract budget, and the budget went to 45 s-leg bets that earn a fifth as much.

Offers confirmed by BOTH the rebuilt book (depth present for a whole second) and the 1/s ticker,
capped at one bet per market-window (SIZE; 45 s leg SIZE x early_frac), model >= 99.5%:

| tau 3-30 (<=30 s) | market-windows | contracts | $ at our own fills' margin |
|---|---|---|---|
| offered | 30 | 1,950 | |
| we bought | | 1,025 | |
| **gap** | | **925** | **+$21.56** |
| - close budget spent (logged `close_budget`) | 5 (4 closes) | 323 | +$5.81 |
| - close budget spent (SILENT, no log line -- A4) | 4 (4 closes) | 262 | +$7.26 |
| - `market_attempts` lockout (A5) | 3 (3 closes) | 204 | +$5.35 |
| - `both_sides` (we held the other side) | 1 | 81 | +$1.80 |
| - `against_thin` (risk gate) | 1 | 55 | +$1.34 |

| tau 31-45 (45 s leg) | market-windows | contracts | $ |
|---|---|---|---|
| offered | 40 | 2,925 | |
| we bought | | 2,324 | |
| **gap** | | **600** | **+$3.80** |
| - `market_attempts` lockout | 5 (4 closes) | 365 | +$2.81 |
| - `early_cheap` / `dump_guard` (risk gates) | 2 | 156 | +$0.38 |
| - silent budget skip | 1 | 77 | +$0.59 |
| - order sent, filled 0 (lost the race) | 1 | 76 | +$0.59 |

- **Split by price** (this is the number that matters after A2): of the <=30 s gap, **380 contracts
  were at 95c or cheaper and are worth +$14.98**; 545 contracts were dearer than 95c and worth only
  +$6.57 at historical margins -- and negative at the top of our loss-rate interval. At 31-45 s
  only 156 of 600 contracts were <= 95c (+$0.38).
- Only **29 of 236 watched closes** had a confirmed standing 90-98c offer at <=30 s that our model
  was sure about. This is the same message as A1: there is very little to grab.
- **The budget items are concrete.** Every one of the 10 budget-blocked market-windows had its
  close's budget already spent by TWO 45 s-leg buys:

  | close (ET) | blocked market | contracts | ask | tau | the two bets that had spent the budget |
  |---|---|---|---|---|---|
  | 09-21 13:45 | KXZEC15M | 77 | 93.8c | 18 | XRP 45 s @97.7c, SOL 39 s @97.5c |
  | 09-20 23:45 | KXSOL15M | 77 | 94.2c | 30 | ETH 45 s @91.9c, SOL 45 s @97.2c |
  | 09-20 23:45 | KXETH15M | 77 | 96.9c | 28 | (same close) |
  | 09-21 13:30 | KXETH15M | 77 | 95.5c | 5 | XRP 36 s @97.6c, SOL 33 s @95.0c |
  | 09-20 07:15 | KXSOL15M / KXHYPE15M | 72 / 67 | 96.8c / 98.0c | 30 / 30 | XRP 45 s @97.1c, SOL 37 s @97.9c |
  | 09-20 08:45 | KXSOL15M | 73 | 97.5c | 25 | HYPE 45 s @96.9c, SOL 39 s @97.0c |
  | 09-21 00:00 | KXHYPE15M | 40 | 96.3c | 25 | BTC 45 s @97.4c, SOL 33 s @97.9c |
  | 09-20 23:45 | KXDOGE15M (45 s) | 77 | 98.0c | 40 | (same close) |
  | 09-20 11:30 | KXXRP15M | 24 | 97.3c | 28 | four 45 s-leg buys |

  Post-fix ledger by leg: 45 s-leg-only markets **+0.74c a contract** (+$33.45, 4,548 contracts, 72
  markets); <=30 s-only markets **+3.96c** (+$93.58, 2,361 contracts, 40 markets). The budget was
  being spent five-for-one in the wrong window. **All 10 cases are before `--early-frac 0.333`
  (09-22 11:42Z), which already cuts the 45 s leg to a third of SIZE: after that change two early
  legs spend 0.67 x SIZE and leave 1.33 x SIZE for the <=30 s window.** No close on 09-22 has
  exhausted the base budget (18 of the 82 post-fix closes with fills did, the last on 09-21 23:00Z). So most of this item is ALREADY FIXED; what remains is A4 and A5.

### A4. A silent refusal nobody can see: once two bets are in, the third bet the bot is sized for is dropped with no log line -- and FREEZE bar B5 cannot see it. (339 contracts, +$7.85 in the window)

`pinrun.py` lines 11316-11323, after every gate has passed:

```
state["signals"] += 1
if CLOSE_BUDGET:
    _left = close_budget() - (contracts already bought this close)
    if _left <= 0:
        continue          # <-- no _gate(), no refusal record, no close_summary count
```

`close_budget()` is the BASE `2 x SIZE`. But `close_budget_for()` -- the gate 150 lines earlier --
grants `base + 1 x SIZE` for a new coin (A56) or inside the last 15 s (A59/A61), and
`worst_close_cost()` and the bank brake already price THREE bets, not two. So the third bet is
allowed by the gate, priced into the bet size, and then silently discarded; it can only ever be
taken as an *extension* of an order that started with base room left (the critic's "a third market
appeared in 4 of 126 closes").

Measured from the bot's own counter: run `20260920T023207Z` exited with `state.signals` = 102
against 5 `signal` records and 0 post-counter gate looks -- **97 looks passed every gate and vanished
unlogged**. In this window it cost 339 confirmed contracts (+$7.85 at our margins).

**This matters beyond the money: B5 counts refusals, and these are not refusals.** Any B5 verdict of
"not our gates -- the offers were not there" will be right for the wrong reason unless this is logged.

### A5. `market_attempts` was written to stop 160 ORDERS into one market. It counts REFUSALS as attempts, so three refusals lock a market out of the whole close -- 569 contracts, +$8.16 in the window; 42 lockouts lifetime.

The attempt counters (`attempts`, `attempts_tk`) are incremented at the signal point, **before** the
45 s-leg gates and `staged_none`. Three refusals there -- 150 ms at 20 Hz -- reach
`MAX_ATTEMPTS_PER_MARKET = 3` and the market is refused for the rest of the close, including the
<=30 s window.

- Post-fix: **13 markets locked out in 12 closes**, every one with `tried` = 3. 12 of the 13 also
  carry a `staged_none` or `early_cheap`/`early_wide` refusal -- the thing that burnt the attempts.
  Lifetime: **42 lockouts in 36 closes** (15 with `staged_none`, 10 with `early_wide`, 5 with
  `early_cheap`).
- Of those 13, **11 market-windows still had a confirmed standing 90-98c offer while the model was
  >= 99.5% sure and were never bought: 272 contracts at <=30 s, 521 at 31-45 s**, +$8.16 at our
  margins. Example: KXBTC15M-26SEP200515-15, 09-20 09:15 ET -- `staged_none` at tau 45 (touch under
  1 contract), then at tau 23 the book stood at 95.1c with 5,198 contracts and the bot never looked.
- The burner itself is worth naming: `staged_none` fires when the TOUCH holds under 1 contract, even
  though `depth_floor` two gates earlier has already checked the LADDER behind it and passed, and the
  sweep that would fill from that ladder happens later in the order path. A thin touch with a fat
  ladder is exactly the book we sweep.

### A6. Being switched off costs more than every gate in A3 put together: 364 contracts at <=30 s (+$28.35 at our margins) were offered while the bot was down or blind.

09-20 03:45-04:41Z (drawdown brake, three restarts each re-halting) and the 09-22 00:50-05:38Z
Kalshi outage. Peak measure, so it is an upper bound, but it is the largest single item in this
report and the only one that needs no change to any rule. 31-45 s adds 728 contracts (+$4.75).

### A7. Lost races and flicker: real, but not a free lever.

- Our own orders, post-fix: <=30 s 19 zero-fill (726 contracts, 15 closes, the side won in all of
  them) + 7 partials (167); at the ask we saw and the real outcome: +$16.12 and +$3.25. At 31-45 s:
  14 zero-fill (455 contracts, one side lost) **-$36.14**, 12 partials +$8.31. Investigator B
  (lost-races) owns this; its P1 is ~47 ms of avoidable TCP/TLS handshake per order.
- Flicker: in the book, a maker posts and cancels 2-contract quotes at 91.8-92c every 5-30 ms. On the
  PEAK measure 439 contracts at <=30 s (+$7.31) never stood a whole second. Catching those means
  resting our own orders (becoming the maker), which is a different -- and adversely selected -- risk.

---

## 2. Refuted or not supported

- **"Tape supply at 90-98c was flat while our buying fell 65%" (map G2 / 09 F3) -- not for the supply
  WE can use.** 09 F3 counted contracts TRADED at 90-97.9c by anyone, which is mostly the market
  being 90-98% sure. Conditioned on OUR model being >= 99.5% sure -- the only supply the bot may buy
  -- offers per close fell 54% (A1). Both statements are true, of different populations.
- **"The gap is mostly gates."** It is not: 925 contracts at <=30 s in 2.5 days, of which the risk
  gates (`against_thin`, `dump_guard`, `early_cheap`) hold 211. The pile is small because the supply
  is small.
- **"The 45 s leg is stealing the <=30 s window's markets."** Not market-for-market: in the confirmed
  <=30 s gap no market-window is blocked by `staged_none` (the 45 s leg having filled that market),
  and only one by `both_sides`. The crowd-out the 45 s leg really causes is in CONTRACTS -- the close
  budget (A3) -- and `--early-frac 0.333` has already cut that.
- **A measurement bug I made and caught, recorded so nobody repeats it:** the first book rebuild
  showed fat 90-98c offers standing for whole windows in markets where BOTH the `ticker` channel and
  the bot's own book said there was no bid at all. Cause: a delta line carrying the collector's
  `_seq_gap` field puts an extra `}` after `_rx_ms`; my receive-time parse raised, the fallback set
  rx = 0, and the market's opening SNAPSHOT was applied out of order, leaving levels the deltas had
  already removed (17,024 phantom contracts on KXBNB15M-26SEP211845-45). Fixed; the whole 58-hour
  window was rebuilt. Three instruments, two agreeing against the third, is what found it.

## 3. Could not measure, and why

- **Whether the steady era's supply would look the same through the order book.** The era comparison
  (A1) is ticker-only; a book rebuild for 09-13..09-17 is ~50 minutes of tape reading and RAM was at
  the 1.0 GB line for part of this session.
- **Whether we would have WON any missed offer.** Nobody can: the tape's population is "an offer was
  sitting there", ours is "someone sold it to us" (rule 5). What I can say is that these offers STOOD
  for at least a full second, which is the opposite of the fresh-offer class that loses (03 F2).
- **Exact attempt counts per market.** The counter is incremented in code, and refusals are logged
  once per (close, market, gate), so lockouts are counted from the `market_attempts` record, not
  reconstructed second by second.
- **Sub-second detail of our own reads.** The bot's book is its own WebSocket; I can see what the
  exchange published, not what the bot's copy held at that millisecond.

## 4. Candidate ways to grab missed deals without added risk

Each with its size in this window (236 closes, 2.5 days) and what it would block. **None of these
touches the hedge path; all are entry-path only.**

1. **Log the silent budget skip (A4).** Pure logging, FREEZE-legal, blocks nothing. Size: it is the
   only way B5 can tell "the offers were not there" from "we refused them without saying so", and it
   covers 339 contracts (+$7.85) in this window. Risk evidence: none needed -- it changes no decision.
2. **Count an attempt only when an ORDER IS SENT (A5).** Move the two counter increments below the
   45 s-leg gates, or increment them where the order is sent. That restores the gate to what A26
   wrote it for (160 orders into one market) and stops three refusals from locking a market out.
   Size: 569 contracts (+$8.16) here, 42 lockouts lifetime. What it blocks: nothing -- a market must
   still pass every gate, and `MAX_ATTEMPTS_PER_MARKET = 3` still caps real orders. Risk evidence:
   the markets it would unlock are ordinary gate-passing markets; our own fills of that kind are the
   +2.0c/contract population of A2. Test: a paper arm with the counter moved, compared on shared
   closes (it must show MORE orders on the same markets, not different markets).
3. **Let the third bet actually be takeable (A4), with the 95c cap from A2.** Change
   `close_budget()` to `close_budget_for(...)` at line 11319 so the extra-coin / last-15-s allowance
   the bot is already SIZED for can open an order, and require price <= 95c for that third bet.
   Size: 339 contracts (+$7.85) here, most of it at 94-97c so the cap would take roughly half.
   What it blocks: nothing new; it ALLOWS a third bet in ~5 of 236 closes. Risk: the worst close is
   unchanged (3 bets is already what `worst_close_cost` and the bank brake price), but realised
   exposure in those closes rises by one bet -- so it is "inside the risk we are already sized for",
   not "no risk". FREEZE: this is a flag/behaviour change -- paper arm first.
4. **`staged_none` should read the ladder, not the touch (A5).** It refuses when the TOUCH holds
   under 1 contract although `depth_floor` has already passed on the ladder behind it and the sweep
   would fill from that ladder. Making it test the same reach `depth_floor` uses removes the main
   attempt-burner. What it blocks: nothing; it stops refusing a book we can actually sweep.
   Size: it is the cause behind 12 of 13 lockouts in A5. Paper arm first.
5. **Uptime (A6) is the biggest single item here: 364 contracts, +$28.35.** No rule changes, no new
   risk: KalsBoot "run whether logged on", and a drawdown brake that does not re-halt on every
   restart (map K4). Validation is trivial -- closes watched per day.
6. **What NOT to do.** Do not chase the >95c part of the gap (545 contracts, +$6.57 at historical
   margins, negative at the top of our loss interval, A2). Do not loosen `confidence`: the 4,908
   contracts offered at <=30 s while the model was under 99.5% are the population our own fills lost
   5.7% of closes on (investigator C, 2 of 35 closes, -5.43c a contract). Do not rest maker orders to
   catch flicker.

## 5. For FREEZE bar B5 (do not duplicate its decision -- this is input)

- Post-fix, <=30 s, outside the 45 s leg: confirmed standing supply **8.6 contracts a watched close**
  against B5's reference of 25-27.65. We bought 10.2 a close (more than the standing measure, because
  we also take offers the 1/s ticker never samples). **The gap to the reference is absent supply, not
  refused volume** -- which is B5's answer (b), on an instrument B5 does not use.
- B5's LOW/HIGH bounds are built from refusal records. **They cannot contain the silent skip (A4)**,
  and `market_attempts` (A5) is dropped from B5's HIGH bound by the same argument used for
  `max_per_market` -- but unlike `max_per_market` it fires on markets we do NOT hold. Both belong in
  the HIGH bound, or the bound is not an upper bound.
