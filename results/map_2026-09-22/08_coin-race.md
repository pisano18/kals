# 08 coin-race -- does the Coin Race deserve its share, and is it bleeding?

Investigator 08. Status: **COMPLETE** (2026-09-22 ~06:35-07:00Z). Read-only.
Collectors alive at the end (pids 105304, 105352); free RAM 2.0 GB; disk 33.7 GB.
Sources: Kalshi ledger (`results/kalshi_ledger.json`), our own logs
(`pinracepenny-live.jsonl`, `pinracearm-*.jsonl`, `pinrun-live-*.jsonl`), and the
tape (`orderbook_snapshot` + `orderbook_delta`, exchange `ts_ms`) for the three
race fills that did not fill at the price seen. No replay anywhere.

**Answer in one line:** the race is not bleeding (-$1.11 real in total). It does
not deserve the time it gets: its ceiling is a few dollars to ~$26/day, while
the pin bot swings +$116 to -$161 in a day. The most valuable thing it produced
is a millisecond-level picture of how a faster market maker picks off our
orders, and **the pin bot's own losses show the same signature** (F2).

---

## 1. Findings, ranked by dollars

### F2 (largest $, TRANSFERS TO THE PIN BOT). A fill that comes in 2c+ under the price we saw means a faster party has already moved. Those pin markets lost $270.91 on 6; the other 120 lost $19.27

- **Claim:** in the pin bot's logs, markets where any fill came in at least 2c
  under `ask_seen`: **6 markets, 2 net-negative, ledger net -$270.91**. Every
  other market with `ask_seen` logged: **120 markets, 2 net-negative, -$19.27**.
  Hypergeometric p = 0.011 (the chance of 2 or more of the 4 bad markets landing
  in a random 6).
- **Window:** 2026-09-19 22:29Z to 2026-09-22 06:29Z. That is when `ask_seen`/`want`
  started being logged. 126 markets, money from `kalshi_ledger.json`.
- **The two bad ones:** `KXHYPE15M-26SEP192345-45`, early leg, seen 97.5c,
  filled 94.1c. It was a hedge false alarm and lost -$148. `KXNEAR15M-26SEP211245-45`,
  early leg, seen 95.5c, filled 91.1c. It lost outright with a hedge, -$140.
  In both, `hedge_alarm` fired **2 seconds after the fill**. So the cheap fill
  was the earliest sign of the collapse, and it is visible at the fill.
- **Mechanism:** this is the race loss in F3, seen there at millisecond
  resolution. An immediate-or-cancel buy fills at anything at or under its
  limit. If the maker's price rises before we arrive, we are cancelled. If it
  falls (the market now rates our side lower), we are filled cheaper. Filled
  cheap therefore means the market moved against us before our order landed.
- **Pointer only (pin investigators should own it):** since 09-19 22:29Z,
  markets whose FIRST leg was the 45-second `early` leg: 87 markets, ledger net
  **-$384.15**. Markets whose first leg was `full` (tau of 30 s or less): 39
  markets, **+$93.97**. Of the early leg's 4 net-negative markets, 2 are hedge
  false alarms. The race model shows the same tau split (F4).
- **Confidence:** medium. n = 6 markets. The two bad markets are one outright
  loss and one hedge false alarm.
- **Artefact check:** could the cheap fill be a sweep artefact (the average
  across several price levels)? No. Sweeps make `exec` HIGHER than seen, not
  lower. All 6 are single-price fills under the seen ask.

### F1. The race is not bleeding: -$1.11 real on 16 races, confirmed by Kalshi's ledger

- `kalshi_ledger.json`, every `KXCRYPTOLEAD15M` row: 09-21 has 26 markets over
  15 races, **-$1.1971**. 09-22 has 1 race, **+$0.0842**. Lifetime race money,
  including the 09-07 and 09-15 pennies, is -$1.14. This matches `live_settled`
  exactly.
- By leg: 24 legs filled at 94-98c, all won (+$0.47 together). 2 legs at
  85-86c, both lost (-$1.73). 1 leg at 91c (09-22), won (+$0.08).
- For scale: that is about 1% of one good pin-bot day (+$76 to +$116).

### F3. v-race90's diagnosis is wrong. The book was 0.16 s old, not 5 minutes. The loss was a ~0.25 s race against a faster maker, and the new REST re-read did not stop the same pattern on its first live order

- **Loss 1 (09-21 13:29:20Z, SOL NO, decided at 93c, filled at 85c, -$0.86).**
  The bot's logged ladder was `[0.93x120, 0.94x2, 0.95x25, 0.96x120, 0.98x1,
  0.99x1178]`. That is EXACTLY the exchange book between **13:29:20.106Z and
  .262Z**, rebuilt from snapshot + deltas on exchange `ts_ms`. The order was
  created at **.267Z** (`client_order_id` pin-1789997360267). A maker quoting
  120-lots on a 3-4c ladder raised its SOL-YES bids to 11c (.262) and then 15c
  (.295). Our one contract filled against that new 15c bid at **.356Z**: the
  tape shows `yes 0.15 -1.00` at that instant. So the price the bot saw was
  about 0.16 s old, and the maker moved before our order existed. In the 10 s
  before the send, SOL NO's ask ranged 0.66-0.90. The 93c was a ~150 ms spike
  and the highest price in that window. The bot fires the moment a price looks
  good, so it samples the TOP of a flickering quote. It then pays the market's
  real level.
- **Loss 2 (09-21 20:14:19Z, XRP NO at 86c, -$0.87).** Not a flicker. The 86c
  offer appeared at .655Z, the order was created at .699Z and filled at .765Z,
  at 86c. This was a genuine near-tie (3.7 bp) at tau 41. The 90c floor would
  have blocked it.
- **v-race90's first real order (09-22 06:29:27Z, XRP YES).** Seen 97c, REST
  `fresh_ask` **97c (check passed)**, **filled 91c**. On the tape, 97c held from
  .642Z at 25 s to 27.155Z, then the 120-lot maker stepped down to 95c (.155)
  and 91c (.248). Our fill is at .332Z. It won (+$0.08), but it is the same 6c
  pickoff as loss 1, and it came AFTER the fresh read. A REST read shows the
  book at the moment of the read. The maker can move in the ~0.1 s between the
  read and the send, and the extra request makes that gap longer, not shorter.
- **VERSIONS.md says "(1) it never buys under 90c".** That is false as written.
  The floor applies to the price we DECIDE on. A buy fills at anything at or
  under its limit, so a larger flicker than 06:29's lands under 90c.
- **Dollars:** -$0.86 real. At the tape rule's 50-100 contracts, the same fill
  would cost -$43 to -$86.
- **Confidence:** high on the timing (six-level ladder match, and our own fill is
  visible on the tape). n = 2 flicker fills (1 lost, 1 won): not a rate.
- **Artefact check:** could the bot have been holding an older 93c? No 93c NO
  ask existed anywhere in 13:29:10-13:29:20.1Z. The full ladder matches only
  the .106-.262 state.

### F4. Every race loss since 09-21, real and paper, happened at tau 40-60. The real test runs out to tau 60. At tau 30 s or less, paper has 0 bad races in 88

- **Paper (all fair-model arms plus the penny process's paper side, arm3 and
  later, 09-16..09-22), distinct races with a 90c+ leg:**

  | tau band | races | bad |
  |---|---|---|
  | 2-30 s | **88** | **0** |
  | 31-45 s | 12 | 1 (`210930`, tau 40) |
  | 46-60 s | 13 | 1 (`211830`: ETH NO at 98c, tau 60, model 98.6%, lost) |

- **Real:** both losses came at tau 40-41. Of the 16 real races, only 4 had a leg
  at tau 30 s or less, and all 4 won.
- **Model calibration from our own logs:** worth of 0.90 or more, one
  observation per leg. At tau 31-45: 11 races, **2 bad (18%)**, against the
  model's 2.4%. At tau 46-60: 20 races, 1 bad (5%), against 2.2%. At tau 2-30:
  **136 races, 0 bad**, against 2.3%. So the model is overconfident beyond 30 s
  and, if anything, underconfident inside it. The chance of 3 or more bad races
  in 31 at the model's 2.3% is 0.034.
- **The tape agrees:** `RESULTS_coinrace_2026-09-21.md` found all 12 of its
  tau-60-or-less losses at tau 42-57.
- **Live config:** `--live-tau-max 60`. So the real test is spending its sends
  where every observed loss is.
- **Dollars:** -$1.73 real, which is all of the race's losses. On paper, racetau40
  is -$120.66 on its single bad race, while racectl (tau 30 s or less) is
  +$105.27.
- **Artefact check:** could the paper zero come from paper booking the seen
  price? No. The outcome is race-level. On all 16 real races, the paper side and
  the real side agreed on every race outcome, and the real legs were a subset of
  paper's (F5). The 88 races are shared across arms, so n is races, not legs.

### F5. Paper arms: race OUTCOMES are comparable to real; P&L and capacity are not

- On all 16 real races, every race real lost, paper also lost. Paper never lost
  a race that real won. Unlike the pin bot's tape-vs-live gap, here the paper
  side and the real side are the SAME live process deciding on the SAME book.
  So the win/lose outcome transfers.
- **What does not transfer:** price (paper booked 93c where real paid 85c) and
  size. Paper takes up to 250 contracts from the ladder, mostly the fast maker's
  120-lots. `fair0918` shows +$531.68 on 7,487 contracts in 3 days
  (~$177/day), which is fiction. The tape's own table has 8 of its 13 losses
  (tau 1-20) on 120-contract offers: 8.6% of races, against 1.6-3.1% for small
  offers.
- **Cancel selection:** 4 of 31 real orders were cancelled with no fill (2 of
  those races won, 2 lost). There is no sign yet that we only get filled in the
  bad races. n = 4.
- **Since 09-21, per arm:** racectl 7 races, 0 bad. raceedge0 17, 0 bad.
  fair0918 11, 0 bad (45 lifetime, 0 bad). racetau40 10, 1 bad. Penny-paper 25
  with a 90c+ leg, 2 bad (both beyond tau 30).

### F6. The ceiling, next to the pin bot and the time spent

- **Tape ceiling (optimistic, see F7):** tau 40 or less, 90c+, 50-100 contracts:
  **$16-26/day**.
- **Safe-size arithmetic (not a measurement):** tau 30 s or less gives about 13
  races a day with a 90c+ leg (88 races over about 6.5 days). The median
  top-of-book offer is 10-16 contracts, and the margin is about 1.9c a contract.
  That comes to **about $3/day**. The size above that is mostly the 120-lot
  maker, which is where the tape's losses sit.
- **The pin bot:** +$76 to +$116 on good days, -$161 on 09-19. The race's entire
  optimistic ceiling is smaller than the pin bot's normal day-to-day swing.
- **Time:** 27 commits touching race files since 09-01, with 8,601 lines added
  (5% of all research lines). **11 of the 20 commits on 09-21** were race
  commits. That was the day after the first losing day, while the hedge was the
  open wound.

### F7. The race tape study has a timing bias in the strategy's favour: the book is stamped with the recorder's receive time, the index with its own time

- `racebook.py` times ticker lines by `_rx_ms`, the time our collector received
  them. `idxload` times the index by the CF print `time`. Every ticker line
  carries the exchange's own `ts_ms`, and it is unused.
- **Collector receive lag on CRYPTOLEAD ticker lines** (54 hours sampled, 1 in
  12, 08-27..09-22): median 0.4-0.5 s, 90th percentile 1.5-2.3 s. At tau 30-60,
  **5-11% of lines lag more than 2 s and 1-4% more than 5 s**. It was 1.5-4.4 s
  at 09-21 13:29Z and 4-10 s at 09-22 06:29Z, while the bot's own socket was
  about 0.1 s.
- **Effect:** the "lag 2 (honest)" control is really about lag 1.5 on a typical
  line, and zero or less on the 5-11% of lines that arrive during bursts. Bursts
  are the fast moments where pickoffs happen. The bias favours the strategy. Its
  size is unmeasured (section 3).
- `replay.py` (the pin bot's loader) prefers the message `ts`, so the pin replay
  is not affected. Other tape tools were not checked.

### F8. Power: the penny test cannot reach a verdict as configured

- **Break-even loss rate per leg:** 1.86% at 98c, 2.79% at 97c, 5.60% at 94c
  (fee rounded up).
- **So far:** 0 losses in 13 races at 94-98c. That means the true loss rate
  could still be as high as **20.6%** (95% bound), 11 times break-even.
- **To prove profitable:** 160 races in a row with no loss just to bound the
  rate under break-even. 337 races (allowing 2 or fewer losses) for an 80%
  chance of proving it if the tape's 0.39% is true. 634 races if the truth is
  0.7%, and 1,238 if it is 1.0%.
- **To prove unprofitable:** 488 races if the truth is 3.7% (the tape plus the
  pin bot's gap). 204 races at 5%, 42 races at 10%.
- **Already rejected:** 2 losses in 16 has a 0.18% chance under the tape's
  0.39%, and 3.5% under break-even. But both losses were 85-86c legs, a
  population the 90c floor now removes.
- **The rails prevent getting there:** the test halts on its first loss, and the
  `--max-stake 20` counter never goes down on settlement. `LIVE["staked"]` only
  adds, so a process stops sending after about 20 legs, roughly 12 races. It
  would take 13-28 relaunches.
- **Timescale:** about 1.4 races an hour while running (16 races in about 12 h).
  At tau 30 s or less, about 13 a day, so **160 races is about 2 weeks and 337
  is about 4 weeks**. The whole test is worth about ±$5 in expectation at one
  contract.

## 2. Refuted or not supported

- **"The race book may sit five minutes unchanged, so the price was old"**
  (v-race90): refuted for loss 1 (the book was 0.16 s fresh). The 5-minute
  `MAX_BOOK_AGE_MS` played no part in either loss.
- **"The fresh read stops it":** not supported. On its first order it passed
  (97c) and the fill came 6c lower. At best it catches moves in the first ~0.1 s
  and adds ~0.1 s for the next move.
- **"The paper arm's rate will be 30x optimistic, as it was for the pin bot":**
  not seen on race outcomes (16 of 16 races agree). It IS seen on price and size.
- **"We only get filled on the losers":** not visible (4 cancels: 2 of those
  races won, 2 lost).
- **Loss 2 as a stale or flicker fill:** refuted. It was a fresh 86c on a real
  near-tie, blocked by the 90c floor.

## 3. Could not measure, and why

- **Re-running `racegrid` on exchange `ts_ms`:** it rebuilds the grid under
  `flow_cache/`, which is outside my write permission and heavy. So the size of
  the F7 bias is unknown.
- **Whether the 24 real winners filled against the 120-lot maker:** that needs
  7 more hours of `orderbook_delta` scanned (about 2 min each). I skipped it
  because it does not change a decision.
- **REST read latency:** `live_order` logs no timestamp for the REST response,
  so the gap between the read and the send cannot be measured from our logs.
- **Real loss rate at tau 30 s or less:** only 4 real races, too few for a rate.

## 4. Solutions worth testing

1. **Penny test: `--live-tau-max 30`** (was 60). *Blocks:* every leg at tau 31-60.
   That is 12 of the 16 real races on 09-21, and 3 of 3 bad races since 09-21.
   The race has no hedge, so nothing hedge-related can be blocked. *Validate:*
   real fills, per race, against a bar written before looking: **kill at 2
   losses at 94c+ within the first 50 races** (1.6% chance of a wrong kill if
   the tape's 0.39% is true; 56% chance of catching a 3.7% truth), and **pass
   at 160 races with 0 losses, or 337 with 2 or fewer**.
2. **Make the test able to finish.** Let the stake counter drop as races settle,
   or relaunch automatically. Replace halt-on-first-loss with the kill bar
   above. *Blocks:* nothing new. The cap stays per race, not per process.
3. **Replace the fresh read with a spike filter.** Two ways: refuse unless the
   ask has stayed at or above the decision price at every sample across the
   5-second confirm (today it only has to "keep qualifying" at 0.25 s samples),
   or refuse when the model's worth minus the median ask over the last 10 s is
   above X ("more edge is a danger signal", RESULTS §4). *Blocks:* legs bought
   at the top of a flickering quote. In loss 1, the 10-second median NO ask was
   about 78c against a 93c spike. *Validate:* on the tape with exchange `ts_ms`
   (not `_rx_ms`) first, then on real fills.
4. **Fix `racebook._fields` to use `ts_ms`**, then re-run the price-floor and tau
   tables before any further trust in the tape's $16-26/day.
5. **Pin bot (F2): log "filled 2c+ under seen" as a feature and pre-register
   it.** The candidate rule is: no further `full`/`topup` legs into a market
   whose first fill came in 2c+ under seen. *Blocks:* adding contracts to a
   market the maker has just repriced against us. **It must never block or delay
   a hedge.** It could only ever ADD to the hedge alarm, and at 2 of 6 that is
   not justified yet. *Validate:* live fills only. 6 markets in 2.3 days means
   about 30 in 10 days.
6. **Time allocation:** leave the race running unattended at one contract under
   bars 1-2, and spend no session time on it until the bar resolves. Everything
   it has taught is in F2-F4.

## Recommendation

**Pause race engineering; keep the one-contract test running unattended at tau
30 s or less, with the kill/pass bar in solution 1.** The bar decides it:
promote the race past pennies only after 160 real races with no loss, or 337
with 2 or fewer. Kill it at 2 losses at 94c+ within 50 races. Even if it passes,
it is worth about $3/day at safe size, and $16-26/day only on a tape count now
known to lean in its favour.
