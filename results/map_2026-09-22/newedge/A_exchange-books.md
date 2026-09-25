# A -- exchange-books: the constituent exchange feeds as a pre-entry signal

Investigator label `exchange-books`, 2026-09-23. **The headline is a NULL**:
nothing in the constituent exchange quotes, in their order-book depth, or in
how far the venues disagree -- read before we enter -- separates the markets
we lost. **101 cuts were tried across 415 TRAIN markets / 335 closes / 13
losing markets, so the bar is p < 0.0005; the best of the 101 is p = 0.0107
and it fails its own artefact check.** Two further exchange ideas are measured
and come out ACTIVELY NEGATIVE (sections 3 and 4) -- writing those down is
worth more than the null, because both look obviously good on paper. One real
finding came out of the work anyway: a coverage gap that would have made the
whole test impossible on 41% of our fills even if a signal had existed.

Sources: `C:\kals\feed_data\{index_replica,coinbase,bitstamp,kraken,gemini}`
and `C:\kals\kalshi_data\cfbenchmarks_value`, both streamed hour by hour on
the venue's / CF's OWN timestamps, never on `_rx`. Dollars are
`results/kalshi_ledger.json` (Kalshi's own settlements) joined to our own
fills in `results/pinrun-live-*.jsonl`. **No replay, no pinsim, nowhere in
this file.** Read-only throughout; no process was started, stopped or
signalled.

Scratch code (each file has a self-test that plants a known answer AND a
no-lookahead check): `...\scratchpad\newedge\exchange-books\` --
`pop.py`, `extract_replica.py`, `extract_depth.py`, `extract_index.py`,
`feat.py`, `build.py`, `test1.py` (quotes), `test2.py` (depth),
`test3.py` (alarm timing).

---

## 0. A CORRECTION anyone reusing this tape must know

**Kalshi ticker times are EASTERN, not UTC.** `KXBTC15M-26SEP081815-15`
closes at **22:15Z**, not 18:15Z: its first fill is stamped
`2026-09-08T22:14:36Z`, 24 s before close. `pop.py` adds +4 h (EDT) and then
ASSERTS that every first fill lands inside the 15 minutes before its close --
**788 of 788 do**. Reading the ticker as UTC windows the tape four hours early
and every feature comes out of pure noise; the first pass here did exactly
that and produced zero usable rows without any error.

(A January sample would need UTC-5. The +4 h is asserted, not assumed.)

**Population, all time:** 788 markets with at least one fill of ours,
09-08 08:00Z to 09-23 06:00Z. Kalshi's ledger on those: **+$548.75 net** --
**26 losing markets worth -$764.91** against **+$1,313.66** on the other 762.

---

## 1. FINDING -- 41% of our fills have NO constituent exchange feed at all, and we record three coins we have never traded

**Claim.** `feed_data` records 8 coins; the bot trades 9; they only half
overlap. Any exchange-book rule is unevaluable and undeployable on four of the
coins we trade, and three of the coins we pay disk for have never been traded
once.

**Evidence -- our own fills, by coin, with Kalshi's ledger dollars:**

| coin | markets | net $ | losing markets | loss $ | exchange feed? |
|---|---|---|---|---|---|
| ZEC | 70 | +148.09 | 1 | -8.63 | **no** |
| SOL | 96 | +112.61 | 3 | -50.65 | yes (3 venues) |
| ETH | 61 | +100.41 | 1 | -5.16 | yes (3) |
| DOGE | 74 | +100.11 | 3 | -16.73 | yes (2) |
| XRP | 100 | +67.50 | 2 | -81.55 | yes (3) |
| HYPE | 95 | +33.92 | 3 | -105.09 | **no** |
| BTC | 137 | +20.37 | 5 | -237.52 | yes (4) |
| BNB | 93 | +12.38 | 5 | -138.67 | **no** |
| NEAR | 62 | **-46.64** | 3 | -120.91 | **no** |
| ADA, LTC, BCH | **0** | -- | -- | -- | recorded anyway |

With a feed: 468 markets, +$400.99, 14 losers costing $391.61.
Without a feed: 320 markets, +$147.76, 12 losers costing $373.30.

So **half the loss dollars sit on coins the exchange feeds cannot see**, and
`spotlead.py`'s own run log already said so in August -- *"index ids with NO
replica (no constituent books recorded): BNBUSD_RTI, HYPEUSD_RTI,
NEARUSD_RTI, ZECUSD_RTI"* -- and nothing was done about it.

**Coverage that does exist, measured from one hour of `index_replica`:**

| coin | venues in the replica | n |
|---|---|---|
| BTC | bitstamp, coinbase, gemini, kraken | 4 |
| ETH, XRP, SOL, LTC | bitstamp, coinbase, kraken | 3 |
| ADA, DOGE | bitstamp, coinbase | 2 |
| BCH | bitstamp only | 1 |

Gemini records **BTC only** (its hour file carries 21,839 `update` messages
and no other symbol) -- so "venue disagreement" is a 4-venue number on BTC, a
3-venue number on ETH/XRP/SOL, **a 2-venue number on DOGE where the median is
the midpoint and the direction of the outlier carries no information at all**,
and **undefined on BCH**.

**Mechanism.** `CRYPTO_15M` in `kalshi_collector.py` and the venue symbol
lists in `crypto_feeds.py` were never reconciled after the traded universe
changed.

**Confidence: high.** It is a count of files and a count of fills.

**What would make it an artefact, and the check:** that the missing coins are
not listed on the recorded venues. BNB is not on Coinbase US; HYPE, NEAR and
ZEC are listed on Kraken and/or Coinbase. Not verified against a live venue
API -- this session made no network calls.

**The honest other half:** closing the gap buys nothing on its own, because
sections 2-5 show the features it would carry do not separate losers on the
five coins we DO cover. Coverage is a prerequisite for a future test, not an
edge. The one thing it is worth on its own is **NEAR, the only net-negative
coin we trade (-$46.64 over 62 markets, 3 losers costing $120.91)**, which no
exchange-level work can even look at today.

---

## 2. NULL -- no pre-entry exchange QUOTE feature separates our losers

**Population.** TRAIN = closes before 2026-09-21T04:00Z (end of 2026-09-20
ET), coin in {BTC, ETH, XRP, SOL, DOGE}, at least one fill of ours, ledger
dollars present: **415 markets over 335 closes, 13 losers costing $389.14,
against +$679.14 won.** HOLDOUT (09-21 ET on): 52 markets, 38 closes, **1
loser (-$2.47)** -- see section 6, the holdout has no power whatsoever.

**Features**, all from `index_replica` seconds **strictly before the entry
second**, 120 s lookback. `feat.py`'s self-test plants a move at and after the
entry second and fails unless the feature is unchanged, so lookahead cannot
leak in. Every feature is ranked WITHIN COIN, so none can pass by being a coin
proxy.

**Medians, losers vs winners (13 vs 402):**

| feature | losers | winners | direction |
|---|---|---|---|
| venue disagreement at entry, bps | 1.218 | 1.081 | +13%, noise |
| disagreement, max over 120 s, bps | 2.620 | 3.379 | **wrong way** |
| mean venue bid-ask at entry, bps | 0.126 | 0.499 | **wrong way** |
| most-deviating venue, signed toward the move that hurts us, bps | 0.661 | 0.501 | +32%, noise |
| 60 s drift signed the same way, bps | 0.197 | 0.393 | **wrong way** |
| exchange-built 1-s vol, bps | 0.421 | 0.420 | none |
| exchange vol / the sigma the model actually used | 0.805 | 0.888 | **wrong way** |

The markets we lost were entered into venue conditions that are, if anything,
**calmer and tighter across exchanges** than the ones we won.

**53 cuts tried, so the multiple-looks bar is p < 0.00094.** The best of the
53: adverse-signed 60 s drift, top 10% within coin -- 4 of 43 flagged markets
lost (9.3%) against 9 of 372 (2.4%), **p = 0.036**, 38x above the bar. It
would have saved $123.24 of losses and given up $75.11 of winnings: **+$48 on
a window that made $290**, from the single best of 53 tries. That is what
noise looks like.

**Cross-check against work already in the repo, which agrees.**
`results/RESULTS_disagree.md` (`pindis.py`, 6,647 coin-closes) tested the
same family against index blow-ups and found lifts of 0.67x-1.05x against an
MDE of 2.58x, with the sign flipping between halves on three of four features.
Different population, same answer. **That makes this a null from two
independent routes, and it should stop being re-tried.**

---

## 3. NULL -- the exchange ruler would have made the model MORE confident on the markets it lost, not less

This is the one that matters most, because "rebuild sigma from the venues" is
the obvious next idea and it is **actively harmful**.

The model's volatility ruler is a 300 s standard deviation of the CF index
(`sigma_win: 300`, `sigma_ruler: "live"` in the live `start` row). Rebuilding
the same ruler from the cross-venue median mid over the 120 s before entry and
dividing:

| | n | median exchange-vol / model-sigma | share below 1.0 |
|---|---|---|---|
| markets we LOST | 13 | **0.805** | 69% |
| markets we WON | 402 | 0.888 | 63% |

On the markets that cost us money the venues looked **calmer** than the index
did -- more so than on the markets we won. Swapping the ruler would have
lowered sigma exactly where it was already too low, raised `fair`, raised the
price the bot was willing to pay, and made the losses bigger.

**Artefact check, done:** my window is 120 s and the model's is 300 s, and a
shorter window reads lower on average -- which is why both numbers sit under
1.0. That bias is applied identically to losers and winners, so the
loser-vs-winner **comparison** stands; the absolute level does not. I have not
built a matched 300 s exchange ruler, and the level would have to be redone
before quoting it as calibration.

**Confidence: high on the direction, medium on the size.**

---

## 4. NULL -- an exchange-built jump alarm is NOT reliably earlier than the index-built one

The only exchange question that is not an entry signal. A post-fill alarm can
only trigger insurance (a hedge), never block one -- so it is allowed under
the BRIEF where an entry gate would not be.

**Method.** The live rule (`pinrun.jump_against`, `JUMP_SIGMA 3.0`,
`JUMP_LOOKBACK 3`): the first second after our entry where a one-second move
against our side reaches 3 sd of that series' own pre-entry 1-second sd.
Applied identically to (a) the CF index on its own print times and (b) the
cross-venue median mid.

| TRAIN | n | index alarm fired | exchange alarm fired | both fired | exchange EARLIER | same second | LATER |
|---|---|---|---|---|---|---|---|
| losers | 13 | 9 (69%) | 7 (54%) | 7 | 2 | 4 | 1 |
| winners | 402 | 77 (19%) | 81 (20%) | 53 | 9 | 38 | 6 |

Median difference: **0 seconds**, on losers and winners alike. The exchange
alarm **missed two losers the index caught** (`KXETH15M-26SEP121115-15`,
`KXBTC15M-26SEP121100-00`) and caught none the index missed, while adding 28
fresh false alarms on winners against 24 of the index's it fails to reproduce.

The two it did beat: `KXXRP15M-26SEP192345-45` (-$64.95) by 10 s, and
`KXSOL15M-26SEP110830-30` (-$12.16) by 3 s. Against that,
`KXSOL15M-26SEP120400-00` (-$18.88) fired 2 s LATE. Two hits out of seven,
one of them a miss in the other direction, is not a timing edge.

**Why, mechanically.** `results/spotlead_final.txt` already measured the real
lead and it is **~107 ms of ARRIVAL** (p25 82 ms, median 107 ms, 100.00% of
1.11M seconds) -- our replica is in hand before Kalshi's print, every time.
A tenth of a second is real but it is not a second, and this alarm resolves in
whole seconds. The same file's nowcast shows the replica buys 0.4-3.7% of
settlement-forecast RMSE at best. **The 107 ms is already spent** -- it is why
`index_age_s` sits at 0.2-1.0 s in the live `signal` rows.

**Confidence: high.** 13 losers is thin, but the winners' 402 markets show the
same median-zero difference with the same noise both ways.

---

## 5. NULL -- constituent DEPTH on the side that would hurt us does not separate our losers either

Coinbase top-of-book sizes and Bitstamp's five kept levels, read on the
venues' own timestamps, over the 120 s **strictly before** entry, expressed as
depth on the side that would have to absorb the move that hurts us -- the BID
when we hold YES, the ASK when we hold NO. Raw notional, share of both sides,
each at entry, as a 120 s median, and as the **minimum of the last 30 s**.
Coverage: Bitstamp 415 of 415 TRAIN markets (all 13 losers), Coinbase 348 of
415 (11 of 13 losers; its DOGE ticker is too sparse to reach the 20-second
floor on all but 6 markets).

**48 further cuts, so the honest joint bar across this whole file is
p < 0.0005 (101 cuts).**

The strongest thing found anywhere in this investigation, and it does not
survive its own artefact check:

| cut | flagged | losers in | losers out | rate in | rate out | p | saved $ | cost $ |
|---|---|---|---|---|---|---|---|---|
| Coinbase adverse-side notional, thinnest second of the last 30, bottom 20% in-coin | 70 | 6 | 5 | 8.57% | 1.80% | **0.0107** | 222.18 | 144.88 |

Raw medians looked dramatic -- **$0.098 of adverse-side top-of-book notional
at its thinnest second on the markets we lost, against $5.70 on the ones we
won, a 58x gap**.

**Why it is an artefact, checked three ways, all three negative:**

1. **The other venue says the opposite.** Bitstamp's 5-level depth on the same
   markets, same rule: BTC losers median **$41,849** of adverse-side notional
   against winners' **$30,548** -- the losers' books were *deeper*. Two
   venues measuring the same thing must not disagree in direction.
2. **One coin goes the wrong way.** Within coin, Coinbase: BTC 1.15 vs 30.35
   (losers 26x thinner), XRP 0.05 vs 21.66 (440x), ETH 0.002 vs 1.26 (n=1
   loser) -- but **SOL 6.81 vs 5.00, losers thicker**. The result is five BTC
   losers and two XRP losers pulling against three SOL losers.
3. **The statistic is an extreme value on a flickering quantity.** Coinbase's
   `best_bid_size` drops to near zero routinely within any 30-second window;
   a minimum over 30 seconds measures how often it flickered, not how thin the
   book was.

It is 21x above the bar, one of 101 cuts, and worth **+$77 net** (saved
$222.18, gave up $144.88) while blocking **70 of 415 markets, 17% of
everything we trade**, on a window that made $290. Not deployable, and after
the three checks above not even promising.

---

## 5b. NO POWER -- venue stress and being picked off on the fill

Tested because a fill that comes back under the ask seen is the one post-fill
signature the map already knows about, and "someone dumped into us" is exactly
what venue stress should precede.

**TRAIN, 231 markets where our log carries both the ask we saw and the price
we got: 5 came back 2c or more under that ask (2.2%).** Those 5 made $0.03
between them against +$178.52 on the other 226, and 1 of the 5 lost money
against 5 of 226.

**27 cuts, bar p < 0.00185.** Best: venue bid-ask spread at its 120 s maximum,
top 20% within coin -- 3 of 48 picked off (6.2%) vs 1.1%, **p = 0.062**, 33x
above the bar, on a numerator of three.

**This is NO POWER, not NO EFFECT.** Five events cannot distinguish a 3x lift
from nothing. It is the one exchange feature here that at least points the
right way twice in a row, and it is worth re-running when the count of
picked-off fills reaches ~30. Recording it as "tried, underpowered, re-run
later" rather than as a result.

---

## 6. COULD NOT MEASURE, and why

- **The holdout cannot confirm anything.** 09-21 ET onward is 52 markets, 38
  closes and **one** loser worth $2.47. A rule that halved the loss rate would
  be invisible there. Anything found in TRAIN here would have needed weeks of
  forward fills, not a holdout split.
- **BNB, HYPE, ZEC, NEAR: no constituent data exists.** 320 fills, $373.30 of
  losses, unreachable by any exchange-level feature today.
- **BCH has one venue, DOGE and ADA have two.** Disagreement is undefined at
  one venue, and at two the median is the midpoint so the outlier's direction
  is arithmetically fixed -- `feat.py` asserts this rather than pretending
  otherwise.
- **Cross-venue LEAD-LAG (which venue moves first) cannot be done from
  `index_replica`.** `crypto_feeds.upd()` stamps `time.time()` -- our receive
  clock, not the venue's -- so any per-venue lead measured from the replica is
  feed latency, not price discovery. Doing it properly needs the raw venue
  files, which do carry venue timestamps (coinbase `time`, kraken `timestamp`,
  bitstamp `microtimestamp`). Not attempted in this pass. Note that for a
  LIVE decision the receive clock is arguably the right one -- the bot can
  only act on what it has received -- which is why the disagreement and spread
  features above are still valid as stated.
- **Three corrupt gzip hours** were skipped rather than salvaged:
  `20260909T13`, `20260915T13` (index_replica, EOFError) and `20260915T20`
  (zlib invalid block). `research/gzsalvage.py` exists for this and was not
  used; the affected closes simply have no exchange row. 1 of 374 closes was
  dropped for having no usable cell.
- **A reader that matches nothing is invisible, and this tape has two
  quoting styles.** `crypto_feeds.py` writes COMPACT json (`"time":"`, no
  space); the first version of `extract_depth.py` looked for the
  pretty-printed form, matched zero lines, and wrote **373 empty cells with no
  error and exit code 0**. It now carries `assert_real()`, which runs against
  real bytes and fails if a key stops matching. Any new reader of these feeds
  needs the same assert -- this is the same failure mode as the 68,976,084
  unparsed deltas.
- **`C:\kals\cdc_data` (Crypto.com, a second venue) was not opened.** It is a
  prediction-market feed, not a spot book, so it belongs to a different
  investigator's brief.

---

## 7. SOLUTIONS WORTH TESTING

One thing to build, three things NOT to build, one thing left to test.
Nothing here is deployed or deployable today.

1. **Record the four missing coins.** Add BNB, HYPE, ZEC, NEAR to
   `crypto_feeds.py`; drop ADA, LTC and BCH, which we have never traded and
   which cost disk on a box that is 20.35 GB from a hard collection stop.
   *Blocks nothing. Gates nothing. Cannot touch a hedge.* It does not make
   money by itself -- it makes NEAR (-$46.64, our only losing coin) and HYPE
   and BNB ($243.76 of losses between them) measurable at all, which they are
   not today. Validation: `research/newseries.py`-style arrival check, then a
   repeat of sections 2-5 once there are ~30 losing closes on those coins.
   **This is a deployment change to a collector, so it needs the operator and
   it touches `C:\kals` -- not done here.**
2. **Do NOT gate on constituent depth.** Section 5: the one cut that looked
   real (Coinbase adverse-side depth at its thinnest second) is contradicted
   by Bitstamp on the same markets, reverses sign on SOL, and is an extreme
   value on a size that flickers to zero all day. It would block 17% of
   everything we trade for +$77 on a $290 window.
3. **Do NOT swap the volatility ruler to the venues.** Section 3 measures it
   going the wrong way on the markets we lost. Writing this down is the
   deliverable; it is a cheap-looking idea that would have cost money.
4. **Do NOT add an exchange-built jump alarm.** Section 4: median zero seconds
   earlier, misses two losers the index catches, adds 28 false alarms on
   winners. The 107 ms arrival lead is real and already spent.
5. **The only exchange-feed idea left standing is sub-second**, and it is not
   an alarm: the replica is in hand ~107 ms before every CF print, 100.00% of
   1.11M seconds (`spotlead_final.txt`). That is worth testing **only** on the
   hedge's price, not on entry and not as a gate -- when the hedge is chasing
   a quote in the last seconds, acting on the replica tick instead of waiting
   for the next index print is a tenth of a second of head start on the same
   information. Validation would have to be live A/B on fills (a paper arm
   cannot model whether the offer was ours), and it **must not be allowed to
   delay or block a hedge** -- it can only ever make one fire sooner.

---

*Resource check, per protocol: `kalshi_collector.py` (pid 105304, 47.3 MB) and
`crypto_feeds.py` (pid 105352, 38.9 MB) both alive at the end of this work.
Free RAM 2.73 GB, free disk 20.35 GB. Nothing under `C:\kals` was written or
touched; no process was signalled. Peak python here stayed well under 400 MB
(the tape is streamed hour by hour and cached as 33 MB of per-close cells).*
