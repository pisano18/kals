# POSTMORTEM 2026-09-27 -- the $131.98 BTC loss at 04:00Z (midnight ET)

Written 2026-09-27 by the post-mortem workflow (4 finders, 12 refuters, every
number from our own live fills, the settlement-index feed, the trade tape, the
exchange feeds and Kalshi's ledger; the replay was not used anywhere). Times
in this file are UTC as the repo requires; 04:00Z is midnight ET.

**The short version.** The bot's arithmetic was right and its inputs were
right; what beat it was a seller who knew something. Someone had been dumping
YES for a minute, flashed a fresh 1,000-lot offer at 98c in front of us, we
hit it, and five seconds later one Coinbase sell order dropped bitcoin $22 in
one second -- about 23 times the typical one-second wobble the bot was
pricing on. The only rule that would have refused this market is the
fresh-offer-while-others-sell gate (`--toxic-fresh`), which arm-toxic did
refuse and which went live at 05:08Z. On all our real fills since 09-09 that
gate is worth about +$23/day, but nearly all of that money is one bad day
(09-19) plus this loss, and in the first half of the record, when no such
loss came, it cost about $8/day in skipped winners. Every other candidate
rule loses money.

---

## 1. What happened, second by second

Market: `KXBTC15M-26SEP270000-00`, strike $84,389.59 (= last window's
settlement), closes 04:00:00Z. Settlement = the average of the 60 one-second
index prints from 03:59:00 to 03:59:59.

| time (UTC) | what happened |
|---|---|
| 03:57 - 03:59:06 | Bitcoin sat $0.20-$2 BELOW the strike. The market priced YES at 43-49c: a coin flip. |
| from 03:58:55 (65 s left) | Heavy selling of YES begins: in 5 s, takers sold 11,475 YES against 1,693 bought. YES fell to 25-28c by 03:59:15-30 (low 20c). |
| 03:59:07 (53 s left) | The index crossed ABOVE the strike, by $1-3. (First reports said 03:59:27; the feed says :07, so it had been on our side 24 s when we bought.) |
| 03:59:27-28 (32 s left) | A second jump to +$5.50..+$10.50 above strike. Bitstamp's top of book did not move for 5 s around this and Coinbase's last trade was still below the strike, so this pop came from a constituent exchange we do not record or from how the index weights depth. YES traded up from 27c to 64c. |
| 03:59:25-30 | In the last 5 s before we bought: 1,467 trades; takers sold 50,190 YES and bought 46,312 -- sellers still at least matching buyers while the price climbed to 97-98c. |
| 03:59:30.207 (29.8 s left) | **We bought 99 YES at 97.89c** ($97.05). The bot's belief was 99.8 in 100 (re-derived from its own inputs to nine digits: correct arithmetic). Index $7.00 above strike; 24 of the 31 already-locked prints were on our side, cushion $1.71 per print. The ask we hit was 148 ms old; takers had sold 56 in 100 of the last 3 s of YES volume. The 97.9c level was a 1,000-lot being added and cancelled within 3-15 ms dozens of times a second -- a flash, not a resting offer. |
| 03:59:30.595 | **We bought 99 YES at 97.0c** ($96.23). Ask 50 ms old; sold share 58 in 100. |
| 03:59:30.6 - 35.5 | Nothing recorded moved against us: Coinbase's mid sat +$7.36 above strike the whole five seconds. |
| 03:59:35.30-35.40 | A burst of NO buyers (YES sellers) hit YES at 99c: 28+128+154+197+50 contracts. |
| 03:59:35.50-35.53 | The Kalshi book collapsed 99c -> 55c (10,296 contracts in ~25 ms), reaching 33-45c by 35.6. Coinbase's first down-tick is stamped 35.518: the Kalshi dump and the Coinbase sweep happened in the same 10-20 ms, which is inside clock error. Nobody "saw Coinbase first"; the seller on Kalshi WAS the move. |
| 03:59:35.52-35.54 | One Coinbase sweep: BTC-USD $84,396.94 -> $84,375.31 in 20 ms. Gemini, Kraken, Bitstamp followed within 0.1-0.4 s. Not a lone-exchange glitch: a market-wide move. |
| 03:59:36.000 print | The index fell $22.12 in one second: from +$10.49 above strike to -$11.63 below. That is about 23 times the one-second wobble the bot was pricing on ($0.96/s over the last 5 min). An hour-long ruler read $1.55/s; a 30-min downside ruler $2.31/s (the hour held a -$39 one-second print at 03:10Z). Either wider ruler would have refused the entry (belief 96 / 88 in 100) -- see section 2 for why that still does not pay. |
| 03:59:36.149 / 36.265 | **Hedge fired** (belief now 4 in 100): bought 99 NO at 67c and 99 NO at 68c ($133.65). An exchange feed reacting to Coinbase would have bought NO 0.5 s earlier at 62-67c: $4-10 better, at most ~$26 with perfect timing. Nothing on the entry. |
| 03:59:36 - 04:00:00 | Index stayed $11.6-$18 below strike. Settlement $84,386.45, $3.14 under the strike. NO. |
| result | Paid $192.94 for YES + $133.65 for NO + $3.39 fee; got $198 back. **-$131.98** (log and Kalshi ledger agree to the cent). Without the hedge: -$194.33. |

Two side facts from the reconstruction that matter later:
- The recorder's Kalshi socket lagged 1.0-1.5 s during the 35.25-37.25 burst
  (normally 22 ms). The live bot's own book was current (it saw the 67c NO ask
  at 36.143, a level that first existed at 35.53). So anything REBUILT from the
  recorder (offer age, sold share) is about a second stale during bursts; the
  bot's own logged numbers are the ones a gate acts on.
- The live log `results/pinrun-live-20260925T122357Z.jsonl` on disk begins at
  09-26 07:31Z; the committed copy holds the missing first 19 hours (09-25
  12:24Z - 09-26 07:31Z, 9,972 lines, 55 markets, all wins, +$97.90). Disk +
  committed copy together are the full record with no overlap. Nobody
  concatenated them yet (a tracked live-state file; not done by this job).

---

## 2. Which rules would have refused this market, and what each costs on ALL our real fills

Population: every market the live bot entered 09-09 12Z .. 09-27 04Z and
settled (884-894 markets depending on the finder's join; 19-21 lost on our
own leg; ledger total about +$595). Money is the whole market including the
hedge, so "avoided" is the hedged loss and refusing an entry also removes
its hedge. Halves: H1 = 09-09..09-17 (~9 days), H2 = 09-18..09-27 (~10 days).
Every outcome below is our own fill -- no tape loss rates anywhere.

What n can see: with ~20 losses in ~880 markets (2.2 losses per 100), a band
of 130 markets has to lose about 5 per 100 (7 losses) before it is
distinguishable from the base rate; a band of 40 needs 4 losses. Anything
under that is "cannot tell", not "no effect".

| rule (refuse the entry when...) | refuses 09-27? | markets refused / total | losers among them | ALL: wins skipped / losses avoided / net ($) | H1 net ($) | H2 net ($) | refuters |
|---|---|---|---|---|---|---|---|
| **A. Fresh offer AND others selling** (`--toxic-fresh`: >20 s left, ask <500 ms old, sellers >50 in 100 of last 3 s) | **yes** (both legs: 148/50 ms, 56/58 in 100) | 134 / 665 early-entry markets (20 in 100) | 9 of 14 classifiable (6.7 per 100 vs 1.1 elsewhere) | 235.77 / 636.59 / **+400.82** (+$22.65/day) | **-65.67** (-$7.73/day; 1 loser in 43) | **+466.49** (+$50.71/day; 8 losers in 91) | 2 of 3 say it stands (high, medium); 1 says refuted (medium). Survives -- as an in-sample number. |
| B. Our side traded as a coin flip (<60c) inside the last 60 s | yes (46c at -60 s) | 642 / 879 (73 in 100 of everything we do) | 12 of 19 | 1,166.92 / 311.74 / **-855.17** (-$45/day) | -476.63 | -378.54 | 3 of 3: stands. Dead: this is the normal shape of our trade. |
| B2. same, threshold 80c / 90c | yes | 776 / 814 | 13 / 16 | -900.72 / -784.82 | -520 / -496 | -381 / -289 | same |
| C. Index crossed to our side <10 s ago ("wait") | no (24 s) | 137 / 884 | 5 (3.6 per 100) | 326 / 194 / **-101.33** (corrected; finder said -231.73) | -116.13 | +14.80 | Finder REFUTED (2 of 3): it dropped 31 markets incl. the -$130.40 BTC loss of 09-24 00:30Z, which crossed 1 s before we bought. Corrected, the 10-s wait is still a net loss overall but not "negative in both halves", and the band is under what n can see. |
| C2. crossed <20 s / <30 s ago | no / yes | 288 / 411 | 4 / 6 | -344 / -457 (corrected) | -291 / -416 | -53 / -41 | negative both halves; stands |
| D. Locked cushion under 1 / 2 / 4 wobbles per print | no (1.9) | 194 / 286 / 473 | -- | -454 / -450 / -720 | -300 / -347 / -462 | -154 / -103 / -259 | negative both halves; thinnest cushion was the BEST band |
| E. Wider volatility ruler (use the hour's wobble, $1.55/s, instead of the last 5 min) | **yes** (belief 96 in 100) | 465 / 853 | 11 of 18 | 809 / 486 / **-323.27** (-$17/day) | -232.97 | -90.30 | Catches this loss and 10 others but refuses 55 in 100 of our trades: costs more than it saves. Downside ruler ($2.31/s): -$501 (-$26/day). Also fires more hedges (unmodelled, makes it worse). |
| F. Index moved >=3 wobbles AGAINST us in the last 10 s | **no** (2.9) | 42 / 853 | 3 of 18 | 61.86 / 162.65 / **+100.79** (+$5/day) | +52.11 | +48.68 | Not new: a wider copy of the live `--jump-gate` (3 wobbles in 3 s, since 09-15); all 3 losers it "avoids" predate that gate; the H2 money is two hedge false alarms (XRP 09-20 -$64.95, BNB 09-26 -$20.29), 0 own-leg losers in 26. A hypothesis at n = 42; would not have caught 09-27. |
| G. An exchange feed (Coinbase etc.) as an entry gate | no (nothing moved against us before the sweep) | -- | 0 of 13 feed-coin losers were lone-exchange moves | saves $4-10 on THIS hedge, $0 on the entry | -- | -- | 3 of 3: stands. No identify-better lead here. |
| G2. Index disagrees with the exchanges at the send (>=1/2/3 wobbles richer for our side) | no | 137 / 83 / 51 of 379 | 3 / 1 / 0 | -8.56 / -60.32 / -94.45 | -- | -- | Null, but one refuter shows the >=1 cell swings +-$130 on the dropped 09-24 loss (a stale Kraken quote): undetermined at 8 losers, not measured-negative. |

### 2a. Rule A in detail, because it is the one that is live

What the three refuters agreed on:
- The arithmetic reproduces to the cent from raw files; sides, prices, times,
  hedges, ledger all tie out. The rule is exactly what `--toxic-fresh` does,
  never touches a hedge, and both 09-27 legs sit inside it on the bot's own
  numbers (arm-toxic refused them at 03:59:30Z).
- The bot's own logged offer age is the right input. The recorder's rebuilt
  book is wrong at millisecond resolution (its best ask sits below the price
  we actually paid in 52 of 144 legs and above it in 36), so tape-rebuilt ages
  only fill the days before 09-13 and under-count fresh offers there.

What they found that weakens it (each one is real):
1. **In-sample.** 7 of the 9 losers in the cell sit inside 09-13..09-24, the
   window PREREG_toxic used to choose the cell. Genuinely new evidence is
   pre-09-13 (15 markets, 1 loser, and that loser is "fresh" only by a
   rebuild convention a live gate cannot see -> really 0) and after the
   pre-registration (27 markets once the 19 missing log hours are restored,
   1 loser = this one). Take away this one loss and the post-PREREG slice is
   26 markets, 0 losers, gate net **-$38.57** (about -$17/day).
2. **Two days carry it.** 09-19 (the day hedges were blocked by since-fixed
   bugs) holds 4 of the 9 losers (-$314.61); 09-18 + 09-19 hold 6 of 9. Drop
   09-19 and 09-27 and the gate nets **-$75.53**. Losers fell on 5 of 19 days.
3. **It would not have caught the other big recent loss.** BTC 09-24 00:30Z
   (-$130.40) was a fresh offer (113 ms) but sellers were only 34-35 in 100
   (Kalshi's public trade history; method checked against 09-27 to 3 decimals).
   Of the two ~$130 losses in the last four days the gate catches one.
4. **Some of its "saves" are already refused by other live gates.** 5 of the 9
   cell losers (-$199.05) were entries today's bot no longer sends (10c edge
   cap above 20 s; 95c early floor). On the legs today's bot would still send:
   4 losers in 120 cell markets vs 4 in 452 elsewhere; gate money +$259.56
   all, H1 -$57.32, and the whole $437.55 avoided is four markets on three
   days (BNB and BTC 09-19, HYPE 09-21, BTC 09-27).
5. **The 09-27 legs cleared the bar barely** (56 and 58 in 100; the share
   first crossed 50 in the very 2 s we bought) and would not with a 5-s window
   (51 / 53). 31 of the 134 cell markets sit at 50-60 in 100.
6. **The pre-registered bar is not met**: >=2 losers in the holdout (have 1),
   7 days of bot-logged share (have ~2.3 usable days after the log gap).

What the cost looks like when the gate is wrong (no toxic loss arrives):
H1 measured: 43 refused markets, $82.28 of wins skipped over ~9 days =
**about $8/day**. Post-PREREG minus the trigger: 26 refused, $38.57 over ~2.3
days = **about $17/day**. Part of that is probably not real cost: since 09-25
the live bot got NO fill on 5 of the 14 fresh-and-selling offers it tried, so
a flashing offer often was not ours to take anyway.

What the gain looks like when it is right: one $130-$195 loss per event. In
H2 such events came on 09-18 (2), 09-19 (4, hedge-blocked), 09-21 (1),
09-27 (1); with today's hedges each costs roughly $50-$130.

---

## 3. Recommendation

**Keep `--toxic-fresh` on (it is live since 05:08Z, v-toxic-live) as a LIVE
TEST with a written kill, and read it on 10-01 the way described below. Do
not sell it to yourself as a measured +$23/day.**

Why keep rather than turn off and wait:
- The operator's standing order is lose less first. The gate is the only rule
  in the table that refuses this market AND is not a clear money-loser on the
  full record; its cost when idle is measured (about $8-17/day), its saves
  when right are $50-$195 each, and the mechanism (a flashed offer while the
  tape shows dumping = an informed seller) has timestamps behind it now.
- Turning it off to "read the pre-registered bar cleanly" buys a cleaner
  number at the price of eating the next toxic loss with real money. The bar
  said DEPLOY needs 2 holdout losers; the second loser IS the evidence, and it
  costs $130-$195 to collect.

The honest downside if it is wrong: **about $8-17 a day of skipped winners,
$60-$120 a week**, with no toxic loss to show for it. If H1 is the true
world (no fresh-and-selling loss in 9 days), a week of the gate costs about
$55-$120 net.

How to read it on 2026-10-01 (this REPLACES the PREREG_toxic read, because
with the gate live the refused set is no longer our own fills -- said loudly,
dated 2026-09-27):
- The bot logs every toxic_fresh refusal with its market. Their MARKET
  results are the tape population: they overstate what the gate cost (we
  would not have filled every one; the H2 fill miss was 5 of 14) and
  understate what it saved. So the refused set's result is an UPPER bound on
  cost and a LOWER bound on benefit -- one-sided in the safe direction.
- KEEP if the refused set over 09-27 05:08Z..10-01 holds >=1 market that
  settled against us, or its skipped-wins upper bound is under $75.
- TURN OFF if the refused set holds 0 markets that settled against us AND the
  upper bound on skipped wins is over $75 (PREREG's own KILL figure), or if
  the bot is refusing more than 25 in 100 of its early entries.
- Either way, the fresh AND selling cell of arm-live-frozen (no gate) is not a
  substitute: paper fills are the tape population.

One more thing the table says that is not about the gate: the loss size was
set by size, not by the rule -- 198 contracts at 97-98c in one market on one
close. Whether profit grows with size is an open ledger item (HOT AREAS);
the two ~$130 losses in four days are the argument for measuring it.

---

## 4. What was NOT measured

- **Whether refused offers would have filled.** Every "skipped win" assumes
  the flashed offer was ours to take. Live missed 5 of 14 such offers since
  09-25; the true cost of the gate is somewhere below the numbers above and
  was not measured.
- **The 60 "unknown" markets** (no tape or no offer age; 3 losers, -$176.55)
  are outside every cell. 8 trade-tape hours and 18 settlement-index hours are
  missing (09-23 16Z..09-24 01Z above all); the 09-24 -$130.40 loss was
  classified only through Kalshi's public trade history.
- **Why the 03:59:27 pop happened.** It came from a constituent exchange we
  do not record (LMAX / itBit / Crypto.com) or from depth weighting. An
  exchange feed cannot see it either.
- **Who flashes the 1,000-lot offers** and whether they target us (the
  market adapting to us is "believed, not measured" in THEORY.md section 9).
- **Hedge false alarms.** 8 markets where our side won but the hedge lost
  more than $1 (-$158 in total) are not in any own-leg loss count; the money
  columns include them as negative "wins".
- **A volatility ruler that catches this loss and still pays.** The hour
  ruler and the downside ruler both catch it and both lose money on the full
  record; nothing in between was searched, and searching would be tuning on
  this one loss.
- **The 19 missing log hours on disk** were restored only inside the
  refuters' scratch join, not in the repo file.
- **Days per half** are approximate (8.5-9 / 9.2-10) and each finder's $/day
  uses its own count; the signs do not depend on it.
- **Loss rates from the tape**: not measured, by rule, and none is quoted here.

Files behind this report (scratchpad, `...\scratchpad\pm\`): `toxic-history\`,
`coinflip-before\`, `index-freshness\`, `venue-sweep\` (finders) and the
twelve `refute-*` folders, each with its scripts and self-tests.
