# Clean room vs the bot we run -- 2026-09-27

Written 14:10Z (10:10 AM ET) for the operator, 45-minute box. Left side of every
comparison = what our own docs and live record say (THEORY.md, WHY_NO_MONEY,
POSTMORTEM, MODEL_CALIBRATION, RESULTS_maker, MAKER_SIM, the ledger, the live
logs). Right side = what four teams found from the raw tape alone, never having
seen our strategy (`results/CLEANROOM_2026-09-27.md` and the folders under
`scratchpad/clean/`). Two numbers below were measured fresh for this report
(section 2B and 2C); the rest are quoted. Every clean-room dollar is a
simulator on recorded history; every incumbent dollar is our own fills.

**One-line answer.** Four strangers rebuilt our strategy: last 30 seconds,
locked average, near-certain side, and nothing else pays. They agree with us
on the mechanics, the shape of the edge, the fee, the supply cap and "the
seller knows". They disagree on ONE thing that matters -- whether a resting bid
can make money -- and their design for it is different enough from the two we
killed that it deserves its pre-registered paper read, not a re-kill. Their
biggest open question (the taker race) our live log already answers.

---

## 1. Where the clean room re-derived what we already believe

| belief | ours (source, number) | clean room (number) |
|---|---|---|
| Settlement = average of the 60 prints stamped close-60 s .. close-1 s, rounded half-up to the coin's decimals, YES if that rounded value is at or above the strike | `pinrun.eff_strike`: threshold = strike - half a rounding unit; outcomes agree with Kalshi on 12,607 of 12,607 markets through 09-18 (MODEL_CALIBRATION s1) | reproduces Kalshi's settlement value on 25,803 of 25,803 markets, the result on 25,802; 18 train markets settled YES with the raw average under the strike, and the crowd gave away ~$20,500 selling them |
| Next strike = last settlement, exactly | 108 of 108 (pinrun docstring) | 25,412 of 25,412 for 8 of 9 coins |
| DOGE's displayed strike is cut to 6 decimals; use the 7-decimal value | pinrun reads `custom_strike.floor_strike` (the full string) since 09-25; 791 of 1,401 DOGE strikes differ by 1e-7, outcome agreed on all 1,401 | 2,832 DOGE strikes differ; use the previous settlement value |
| Takers pay 0.07 x price x (1-price) per contract | `billed_fee`, ledger ties to the cent | 1,268 of 1,268 account fills match to a hundredth of a cent |
| The money is in the last 30 s and nowhere else (locked fraction: 0% at 60 s, 50% at 30 s) | THEORY 1a-ii: buyers of 95-98c lose 2.8 per 100 at 31-45 s, 3.6 at 46-60 s, 4.9 at 61-90 s -- the edge dies where the locked fraction does | all four designs landed in the last 30 s; 45-30 s window -$558 on train vs 30-0 s +$1,529; an 8c+ model edge at 90-180 s LOSES 0.1-7c a contract |
| Supply, not the bank, caps the profit | WHY_NO_MONEY: bet grew 4x ($190 -> $1,150 bank), a win grew $1.69 -> $1.93, a loss $25 -> $80; offers under 97.5c: 30-68 a day -> zero on 9 of 10 days since 09-17 | "more bank, more money" true only to $2-5k; counterparty flow 100-500 contracts a market (median); the taker design's money is linear in its cap because the sim eats the whole market |
| An offer that printed was not necessarily ours to take | live fill rate 70%; 5 of 14 fresh offers missed since 09-25; THEORY 3: the tape and our fills differ 31x | 56 of 100 contracts gone within the printing second, 70 by the next; the taker design falls from +$2,338 to +$79 over 9 days |
| The seller who fills a resting bid knows something | RESULTS_maker: a bid one tick under the ask fills on 29% of winners and 100% of the 17 losers; MAKER_SIM: two-sided quoting loses 1.60c a contract on every day, even first in queue; POSTMORTEM: "the seller on Kalshi WAS the move" | 15 variants of resting at model-minus-0..3c lost $3,000-11,000 per 9 days; the contrarian design died of one ETH sweep (2,801 contracts in 0.1 s, 0.4 s BEFORE the index moved); "the market leads the index by 1-2 s" |
| An exchange feed cannot save the entry | FEED_LEAD: before 6 of 8 losers the books had not moved at all | same fact, other words: an order priced from the index alone is stale exactly when it matters |
| The model is wrong only in its "near-certain" tail, and fine inside ~20-30 s | MODEL_CALIBRATION: above 0.999 it is 20-80x overconfident at 45 s and 30 s; 0 losses in ~38,000 cells at 10 s and 5 s; the index's tail is 132 vs a bell curve's 3 | 3-sigma moves happen 1.3-1.9 times in 100 instead of 0.27 past 20 s; "says 99.93, gets 99.2" at 46-60 s; inside 30 s the 99%+ calls come true 99.0-99.96 in 100 |
| Losses on different coins land together | THEORY 4: 12 coins on one close are worth ~1.2 independent looks; caps are per close | 2.4x the independent rate of multi-coin losing closes; one close lost all 4 positions; "cap risk per close, not per market" |
| The very last second is not free money | THEORY 5a: when the outcome is obvious the winning side has bids and no asks (2,736 of 2,736 `no_offer` refusals had genuinely no ask) | 7.06 million contracts traded in the last 0.8 s; takers netted -0.1c each |

Two more of the clean room's "FALSE beliefs" are things we never held: "the
index is truth and the market is noise" (our wobble table and the 0.40 hedge
use the market's price as a second opinion) and "a model taker makes money
anywhere price < probability" (we only buy above 0.995 inside 45 s).

---

## 2. Where it contradicts us, or tested what we never did

### 2A. A resting bid CAN make money -- the one real disagreement
- **Ours:** killed twice. Resting one tick under the ask (RESULTS_maker, 793
  closes): worse than taking in 113 of 114 rows, fills 100% of losers. Quoting
  both sides at the touch (MAKER_SIM, 413 closes): -1.60c a contract, every day.
  `CURRENT_STATE`: "Market making on 15-min crypto: dead."
- **Clean room:** the engineer's ladder -- bids 2c, 5c and 15c UNDER the model's
  price, 100 each, last 30 s only, only when the model says 99.9%+ AND the lead
  is at least a quarter of the largest move ever seen at that second -- made
  +$430 (unkind fill) / +$686 (kind) over 9 unseen days, 167 closes, 0 losing
  markets, worst day +$11; about 2.7c a contract on both halves. Survived a
  0.3-s order-and-cancel delay (keeps ~90 of 100 dollars) and a rebuilt-book
  check on 2 of 9 days.
- **Which side the data supports:** both are right about the design they
  tested. The two we killed rest AT or ONE TICK under the price and are filled
  by anyone; the ladder rests deep and fires only when a taker DUMPS the
  decided side into a thin book. The clean room's own contrarian design (bids at
  95/90/80c, weaker lead guard) died of exactly our mechanism, and the ladder's
  0 losses are partly by construction (the lead floor is the train maximum) --
  0 in 167 closes only says "under about 2 losses per 100 closes", and one full
  ladder loss is about $278, six days of profit. Its first 2 live closes: 54
  orders, 0 fills (the book was already at 99.9c). What we know that it does
  not: paper fills of a resting bid are the tape population; on our own record
  that population hid every loser.
- **Decisive measurement:** the 7-day paper run it is already on
  (pre-registered: net > $0 under both fill models, 0-1 losing markets, >= 870
  contracts a day, worst drawdown <= $280). Its fill count is the real test: if
  the book is at 99.9c before 30 s on most closes it dies on its own bar. Then,
  only on PASS, live at 20 contracts a level, one ladder per close, and the
  loss rate read per FILLED market.

### 2B. Losses cluster by close: THEORY's "0 of 101" is stale
- **Ours:** THEORY 9: "two coins have never both lost on one close (0 of 101)";
  the bank rules (bank/3 per close vs the 20% brake) lean on it.
- **Clean room:** 2.4x the independent rate on the tape; one close lost all 4.
- **Measured now (ledger, all crypto fills):** 241 closes held 2 or more of our
  markets; 1 of them had two losers -- 09-19 11:45 PM ET, HYPE -$43.92 and XRP
  -$64.95 (the XRP one an insurance false alarm), -$108.87 together. Expected
  if independent: 0.3 closes. One event decides nothing, but "never" is gone.
- **Decisive:** nothing to build -- count it at every read. A per-close dollar
  cap (not just contracts) is the cheap protection; the clean-room bot's live
  plan already has one.

### 2C. The taker race -- the clean room's biggest open question, already answered by our log
- **Clean room:** the taker design showed 4x the ladder's money but "whether
  this box can reach a cheap offer before it vanishes ... no bot is measuring
  it" and "live order latency of this box: never measured".
- **Ours, measured now:** the live bot logs every order's round trip: 505
  orders, median 100 ms, 9 in 10 under 152 ms, 1 in 100 over 529 ms; fill rate
  70% (THEORY 9); 5 of 14 fresh offers missed since 09-25. So we win the race
  about 7 times in 10, and the clean room's taker design IS our bot with a
  wider price window (75-98.5c vs our 97.8c ceiling) and no seller gate. Its
  "+$1,643 in 9 days" is the tape population the 31x rule forbids quoting.

### 2D. A big lead helps (them) vs "waiting is not protective" (us)
- Ours (POSTMORTEM rule D, our fills): a cushion floor of 1/2/4 wobbles costs
  $450-720; the thinnest cushion was the best band. Theirs: the ladder needs a
  lead of a quarter of the worst move ever seen at that second.
- Not a contradiction once the design is named: for a TAKER a cushion gate
  only refuses winners; a resting bid needs the cushion because it is filled
  by the dump. Decisive: tag the paper ladder's fills by lead size.

### 2E. The 45-second leg
- Theirs: 45-30 s loses on the tape (-$558 train, all takers). Ours: the live
  45-s leg netted +$51 after its hedges (-$72) on 328 markets -- $0.16 a
  market, not distinguishable from zero.
- Live fills beat the tape, and both say the same thing: that leg has not paid
  for itself yet. Decisive: `arm-early-full` vs live, and the leg's own margin
  per contract over its next ~300 markets (WHY_NO_MONEY idea 1-2).

### 2F. Things they tested that we never did
1. **Rounding ties.** 95 of 25,803 settlements sit exactly on a half unit and a
   float mean rounds them one digit wrong; only an exact-decimal mean gets all
   25,803. Our threshold arithmetic is float. Matters only for a market that
   settles within a hair of the strike; a $0 code check (`eff_strike`,
   `endgame.outcome_of`).
2. **Coin Race ranks at full precision**, not the 2 decimals its rules say
   (14,105 of 14,105 legs; rounding would invent 138 ties). Check
   `pinracearm.py` does not round; a tie counts as a loss for its stop rail.
3. **The index is not a random walk for XRP (1.32x), HYPE (1.69x), ZEC.** Our
   ruler carries lag-1/lag-2 autocorrelation (`engine.var_factor`), and our
   per-coin calibration points the same way (HYPE 26x, ZEC 13x, BNB 12x
   overconfident) -- but every wider-sigma proposal lost $229-424 on our fills
   (MODEL_CALIBRATION s0.5). Same lead, same dead end, unless per-coin.
4. **The 2-3-minute favourite at 70-90c loses its buyers 5.4c a contract**
   (50.8 million contracts) -- and fading it gets swept. Not a trade; a fact.
5. **Late prints.** On the recorder's socket 39 of 100 prints arrive more than
   0.15 s after their stamp and 13 of 100 more than 1 s late; FEED_LEAD found
   our bot holds a print 0.2 s (median) to 1.0 s (slowest tenth) after stamp.
   The clean room's LIVE sockets see 87 ms median, 131 ms at the 99th -- the
   tape's lag is the recorder's, not the box's. Our entry path has no
   print-age gate (only the hedge pass, `MAX_INDEX_AGE_S = 2`).

---

## 3. Beliefs we rely on that the clean room could NOT confirm

- **Makers pay no fee in crypto up/down.** Seen only on 6 commodity markets and
  1 race leg; we have never rested an order in these series. Immaterial in
  size (0.03c vs 2-15c margins) but the first resting fill must be checked.
- **The edge is stable.** Three of their four designs made 20-40% less on the
  9 unseen days than on train; the all-price taker band halved. Our week 2 was
  $8 a day vs $61. Neither side can say whether the market changed or we did
  (our share of the cheap supply is unmeasured -- WHY_NO_MONEY idea 5).
- **Our loss rate per market (2.0-2.4 in 100).** The clean room has no fills of
  its own and cannot see adverse selection at all; 45% of its bettor design's
  markets are ones we already took the last-minute fills in. Nothing on its
  side confirms or denies our number.
- **Any loss identifier (toxic gate, fresh offer, wall).** Its designs carry no
  seller gate and it lists "are the dumpers informed?" as unproven. Same
  verdict as WHY_NO_MONEY point 8: the record cannot yet.
- **Why 45-30 s loses while 30-0 wins.** Our locked-fraction story (1a-ii) fits
  its numbers but it could not test the cause.
- **THEORY's "Var = 880 sigma^2 at 10 s".** The clean room derived sd from the
  sum of k^2 (385 at k = 10), which matches `engine.var_factor`; the 880 in
  THEORY/CLAUDE.md prose stays a typo (THEORY 11.5).

---

## 4. What its paper bot does that ours could adopt, and the bar before it may

| idea | what it is | evidence bar before live | cost to check |
|---|---|---|---|
| Deep resting ladder as a SECOND leg | when there is no ask (52% of our refusals), rest bids at 2/5/15c under the model, last 30 s, 99.9%+, big lead only | (1) the 7-day paper PASS on all five pre-registered lines, esp. >= 870 contracts a day; (2) live 20 a level, one ladder per close, 7 days; (3) 0-1 losing markets in the first 100 FILLED markets, counted from our fills, not paper; (4) maker fee seen as 0 on the first fill | $0 now; ~$50 a level x 3 at step 2 |
| Per-close dollar cap | one full ladder per close across all coins | none beyond a VERSIONS entry; gates no hedge; add to the live bot's per-close contract cap | $0 |
| Decide on RECEIVE time, skip a late second | act 0.2 s after the print arrives; if it has not by 0.9 s, do nothing that second | count from our own log how many entries used a print older than 0.5 s and how those markets settled; only then a gate | $0, one log pass |
| Exact-decimal rounding at the strike | ties (95 in 25,803) rounded like Kalshi does | a self-test with the ETH 2500.155 tie; no live bar needed | $0 |
| Print-lag percentiles in the heartbeat | p50/p90/p99 of stamp-to-receive every minute | none; instrumentation | $0 |

Not adoptable: its taker design (it is ours without the seller gate and with a
looser ceiling -- WHY_NO_MONEY P2 says the 98c band earned $0), and its bettor
design (Kelly sizing into a supply-capped market; the clean room dropped it).

**Housekeeping found on the way:** both clean-room paper processes run the
SAME ladder (the "favourite" file is the ladder again), so the second adds
nothing but 43 MB; THEORY 9's "0 of 101" needs the 1-of-241 correction.
Recorders alive after every job (collector pid 2532788, feeds pid 105352);
live bot 3510420 and both paper bots alive; free disk 67.3 GB; nothing under
`C:\kals` written; no orders sent; no replay used for any dollar of ours.
