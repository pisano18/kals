# Clean-room rebuild, 2026-09-27 -- the operator's report

Written for the operator. Plain words. Every dollar figure below is what a
simulator says a rule *would* have made on recorded history, never a real
fill. "Train" = 2026-08-25..09-17 (24 days, the days the designers were allowed
to look at). "Test" = 2026-09-18..09-26 (9 days, locked away until each design
was frozen). "Base" fill = the kind assumption; "pessimistic" = the unkind one
(each design says what those mean; section 3 spells them out for the bot that
is running). A "close" is one quarter-hour; all coins settle together, so a
close is the honest unit, not a market.

**The one-line answer:** four teams that had never seen our strategy all found
the SAME edge we trade -- the last 30 seconds, when most of the settlement
average is already printed -- and nothing else. Two of the four were then
knocked down by a second pass (their money needed fills that vanish faster
than an order can arrive). The one that survived makes about **$48 a day on the
unkind fill ($76 kind) with a worst single loss of about $278**, and it is now
running on paper. The taker version (buying cheap offers, the way our live
bot does) showed 4x the money on paper but 56-70 of every 100 contracts it
counted were gone before an order could land.

## 1. What the fresh eyes found (one paragraph per school)

**Forecaster school -- "buy the nearly-decided side cheap in the last 30 s"
(taker).** Rule: when 30 or fewer prints are still to come, buy the side the
model says is ~99% decided if it is offered at 75-98.5c and the model beats the
price by 2c after the taker fee. Train: +$4,526 base / +$2,512 pessimistic
(24 days). Test: **+$2,338 base / +$1,643 pessimistic** over 9 days (about
$260 / $183 a day), 429 markets / 291 closes, about 7 losing contracts per
100, worst pessimistic day -$56. Refuter 1: no look-ahead in the code; the
money survives a 1-second-stale index (loses only 4%). Refuter 2 (high
confidence, REFUTED): the fill model assumes we replace the taker on every
printed trade. Rebuilding the order book shows 56 of every 100 contracts are
gone by the end of the same second (money falls to +$686) and 70 of 100 by the
next second (+$79, 4 of 9 days losing, loss rate rises from 7 to 14 per 100).
Only +$922 pessimistic came from offers that were visibly there a full second
before the decision. Size is fake: the money is linear in the cap because the
sim eats the market's whole taker flow. Verdict: the mispricing is real, the
reachability is a race this box may or may not win; the tape cannot say.

**Bettor school -- "near-certain corner with Kelly caps" (taker, last 60 s,
85-98c, only when the model is very sure).** Train: +$1,607 base / +$1,110
pessimistic from a $1,000 bank. Test: **+$362 base / +$323 pessimistic**, 356
markets / 273 closes, 8 losing markets (about 2 in 100), worst day -$189,
worst drawdown $242. Refuter 1 (REFUTED): the builder assumed every index print
is usable 0.15 s after its stamp, but on this box 39 of 100 prints arrive later
than that and 13 of 100 more than 1 s late -- and all the money sits in the last
15 s, exactly where late prints bite; the true size of the overstatement was
not finished. Refuter 2 (REFUTED): priced against the real book with a 1-second
"must still be there" rule the 9 test days make +$160, and +$54 (about $7 a
day) without one tape-hole day; 45 of every 100 of its markets are ones where
our own account already took the last-minute fills, so it would be racing us.
Its own conservative variant (last 30 s only) did better on test (+$462, 1 loss)
-- the same last-30-s story as everyone else. Dropped.

**Contrarian school -- "rest bids for the decided side and get paid by the
crowd's last-minute dumps, but only when the market itself agrees" (maker,
bids at 95/90/80c x 50).** Train: +$530 base / +$83 pessimistic. Test: **+$134
base / +$44 pessimistic**, 50 markets / 49 closes, 0 losses. Refuter 1 (not
refuted, but found a bug: one dump filled every ladder level without spending
its size, -5% on train) and counted 10 markets on 5 closes where the "locked"
side actually lost -- the 0-loss record is the crowd not dumping in those
seconds, not the lock never being wrong. Refuter 2 (high confidence, REFUTED):
the 0 losses need a cancel that lands in 1 millisecond; with a real 0.3-1 s
cancel, the informed sweeps the design itself documented (ETH 09-20, 2,801
contracts sold in a tenth of a second, 0.4 s BEFORE the index print moved)
fill all three levels: test +$169 with 1 loss in 86 closes, train +$614 with 5
losers, and at size 1,000 test is -$502 because losses grow with size and wins
do not. Dropped: same idea as the winner with a weaker guard and a tenth of the
money.

**Engineer school -- "locked-average ladder" (maker, last 30 s, rest bids at
model-minus-2c / -5c / -15c, 100 contracts each, only when the lead is bigger
than a quarter of the largest move ever seen at that second).** Train: +$2,996
base / +$1,678 pessimistic (24 days, 0 losses in 805 markets). Test: **+$686
base / +$430 pessimistic** over 9 days (about $76 / $48 a day), 190 markets /
167 closes (base), 0 losing markets under either fill, worst day +$11 (a
tape-hole day). The edge per contract is the same on train and test (about
2.7c); the drop is fewer fills (2,794 a day vs 4,514). Refuter 1 (not refuted):
every planted look-ahead test passes (future prints x1000, result flipped,
planted jump), sides/fees/day boundaries consistent, test days provably not
read during design. Refuter 2 (partial, 2 of 9 test days): a realistic fill
(only prints strictly through my price, order live 0.3 s after the decision)
keeps about 90 of every 100 dollars of base; if the order is absent 0.4 s of
every second because of cancel/replace churn, 54 of 100; the rebuilt book
confirms the sweeps really would have hit a resting bid (<2% of fills needed a
wall that was not shown). Capacity: about 1,000 contracts per market on busy
days, 300 on most -- a strategy for a $3-10k bank, not one that scales. **This
is the one chosen to run.** Caveat: 0 losses is partly by construction (the
lead floor is set from the train maximum), and 0 in 167 closes only says the
true loss rate is under about 2 per 100 closes; one full-ladder loss costs about
$278, or 6 days of pessimistic profit.

**Fifth school (microstructure).** No design record reached the selector; it
is unranked and unreported here.

## 2. Beliefs about these markets that were tested

TRUE (confirmed from the data, not assumed)
- Settlement is the plain average of the 60 index prints stamped in the last
  60 s (the print stamped AT the close is excluded), rounded half-up, YES if it
  is at or above the strike: reproduced 25,803 of 25,803 settlement values.
- Takers pay 0.07 x contracts x price x (1 - price); 1,268 of 1,268 settled
  markets in the account data match to a hundredth of a cent.
- With 30 s left the model's "99%+" calls come true 99.0-99.96 times in 100
  (2,272 closes).
- Strikes for 8 of 9 coins equal the previous market's settlement value
  exactly (25,412 of 25,412).

FALSE (the data contradicts it)
- "The unrounded average is compared with the strike." No -- the ROUNDED one
  is. 18 train markets settled YES with the raw average below the strike; the
  crowd sold 73,562 YES contracts at about 78c in the last 10 s of those
  markets, giving away about $20,500. Two clean-room simulators were "certain"
  of the wrong side there. The right threshold is strike minus half a unit.
- "The displayed strike is the strike." Not for DOGE: its floor_strike is the
  previous settlement cut to 6 decimals while the comparison uses 7 (2,832
  markets differ). Use the previous market's settlement value.
- "The Coin Race ranks rounded returns as its rules say." No: it ranks at full
  precision (14,105 of 14,105 legs); rounding would create 138 false ties.
- "A bell curve with the right width is good enough." No, past about 20 s
  out: 3-sigma moves happen 1.3-1.9 times in 100 instead of 0.27; the model is
  under-confident in the middle (says 85, gets 90) and over-confident in the
  tails (says 99.93, gets 99.2 at 46-60 s). Inside 30 s it is fine.
- "Second-by-second index moves are a random walk." Not for XRP (60-s
  variance 1.32x a random walk), HYPE (1.69x), ZEC; roughly true for BTC, BNB,
  DOGE.
- "The bigger the model's disagreement with the price, the better the bet."
  False at 90-180 s out: bets with an 8c+ model edge LOSE 0.1-7c per contract
  because the market moves before the index prints. True only inside ~30 s.
- "The index is the truth and the market is noise." The market LEADS the
  index by 1-2 s (6,333 jumps / 1,495 closes) and drifts about 4c in the 20 s
  before an index jump. An order priced from the index alone is stale exactly
  when it matters.
- "A model-driven taker makes money anywhere price < probability." No:
  weighted by contracts, the favoured side loses after fees in EVERY price band
  from 30c to 99.5c (70-90c: -17c per contract on 22.7 million contracts); the
  size sits in the markets the model gets wrong.
- "Being the maker (no fee) beats taking." Not as a blanket rule: resting bids
  at model-minus-0..3c lost $3,000-11,000 per 9 days in all 15 variants;
  whoever sells into a bid in the last 3 minutes knows something.
- "Takers buying the near-certain side cheap in the last seconds get robbed."
  No: in the last 8 s takers at 90-97c win 97.4 of 100, at 97-99c 99.75 of 100.
- "The last 0.8 s, when all 60 prints are known, is free money." No: 7.06
  million contracts traded there and takers netted -0.1c each; the crowd is
  already there.
- "The 2-3-minute favourite is fairly priced." No: buyers at 70-90c with
  2-3 min left win 76 of 100 paying about 81c (-5.4c each, 50.8 million
  contracts); but fading it statically gets swept when the market leads the
  index.
- "An offer that printed was available to me." No: 44-52 of 100 of the taker
  design's contracts were not in the book at the end of the previous second;
  56 of 100 gone within the printing second, 70 by the next.
- "A print stamped at T is usable at T + 0.15 s." Not on this box: median
  0.13 s, but 39 of 100 arrive later, 13 of 100 more than 1 s late, worst 7 s;
  the trade feed stalls the same way. Gate on RECEIVE time.
- "Zero losses in the simulator means zero losses." It can mean a 1-ms cancel,
  or that the crowd happened not to dump in the ~1 in 400-550 closes where the
  "locked" side lost.
- "More bank, more money." Only up to about $2-5k. Every design is capped by
  counterparty flow per market (median 100-500 contracts); the bettor design
  goes negative past ~$10k, the contrarian ladder at size 1,000 lost on test.
- "Losses on different coins are independent." No: 2.4x the independent rate
  of multi-coin losing closes; one close lost all 4 positions. Cap risk per
  close, not per market.
- "A replay showing +$34k in 9 days is an edge." One 37,312-contract print at
  0.1c; a price floor removes it.

UNPROVEN (24 + 9 days cannot settle it)
- Maker fee = 0 in these series: seen on 6-9 resting fills, none in a crypto
  up/down market. Probable; confirm on the first real resting fill.
- "The edge is stable": the all-prices taker band halved in the second half
  of train and fell further on test; the 30-60 s bettor bets flipped from
  making to losing money; the last-30-s favourites and the maker ladder held.
  Three of four designs made 20-40% less per day on test than on train.
- Why the 45-30 s window loses (-$558 on train) while 30-0 s wins (+$1,529).
- Whether the takers who dump the decided side into a thin book are informed
  (only the zero-loss count speaks to it).
- Whether our own account is the competitor: 0.4% of the taker design's
  contracts match its buys, but 45% of the bettor design's markets are ones
  where it had last-minute fills.

## 3. What is running in paper now

**Two paper processes are running, and BOTH implement the same design -- the
engineer's ladder (bot A).** The selector asked for a second bot (the taker
"favourites race" measurement bot, B) and a builder was assigned to it, but
the file it produced is the ladder rule again (its own docstring says
"Locked-average favourite ladder", its orders are bids at model-minus-2/5/15c,
its log has zero trigger or survival records). So the taker race -- whether
this box can reach a cheap offer before it vanishes -- is **not being
measured**. That was the only open question on the design with 4x the money.

| | bot A (ladder) | bot A again (mislabelled "favourite") |
|---|---|---|
| script | `C:\kals-repo\research\cleanroom\locked_average_ladder_re_paper.py` | `C:\kals-repo\research\cleanroom\locked_average_favourite_paper.py` |
| pid, started | 3575912, 09:47 AM ET | 3578084, 09:46 AM ET |
| log | `C:\kals-repo\results\cleanroom-locked_average_ladder_re.jsonl` | `C:\kals-repo\results\cleanroom-locked_average_favourite.jsonl` |
| runs for | 7 days (`--minutes 10080`) | 7 days |
| memory / index lag | 45 MB; prints arrive 87 ms after their stamp (99 of 100 under 140 ms) | 43 MB; 88 ms (99 of 100 under 126 ms) |
| self-test | 48 checks, passed at start | passed at start |
| can it send an order? | no -- the self-test scans the source for any order endpoint | no -- same |

Both were checked alive at 10:02 AM ET; both logs growing; the collectors and
the live bots untouched.

**The rule they run.** Up/down series only (9 coins), every second from 30 s to
1 s before close, decided 0.2 s after the second's index print is RECEIVED
(skipped if it has not arrived by 0.9 s). Projection = (prints already locked
+ remaining count x latest value) / 60; threshold = strike minus half a
rounding unit (DOGE: previous market's settlement value at 7 decimals). If the
lead over the threshold is at least a quarter of the largest move ever seen at
that second on train AND the model says 99.9%+: rest three bids for that side
at model-minus-2c, -5c, -15c, 100 contracts each; cap 300 per market; hold to
settlement; never take, never exit, never hedge. Orders go live 0.3 s after the
decision and a cancel takes 0.3 s too (on purpose: that is what killed the
contrarian design).

**What it assumes about fills (two models, both logged on every print).**
- *Opt (kind):* any trade after my order went live where the taker SOLD my
  side at or below my price fills me up to that trade's size. Assumes nobody
  is queued ahead of me at that price.
- *Pess (unkind):* a trade AT my price first has to eat every contract that
  was displayed ahead of me when I placed the order (I am last in line); a
  trade strictly through my price fills in full; a bid that would cross the
  displayed ask gets nothing.
- Counterparty: a taker dumping the decided side into a thin book in the last
  30 s. Maker fee assumed 0 (taker 0.07 x n x p x (1-p) charged only when a
  bid crosses the ask). Fee rule is an assumption; the docs page returned 429.

**What it has seen so far (2 closes, 18 markets -- NOT a result).** Every coin
was decided by 30 s out and the book was already at 99.9c on the winning side,
so bids 2-15c below the model sat behind 8-1,300 contracts and were never
reached: 54 orders, 0 fills, $0. This rule only fills when a market is still
mispriced inside the last 30 s (a late move through the strike) or a taker
walks the book. The 7-day run measures how often that happens live.

**The number to read after 7 days (pre-registered by the selector; do not
move it).** About 120 closes expected. PASS needs ALL of:
- net > $0 under pess AND under the queue model;
- losing markets 0 or 1 (2 or more = the lead floor failed out of sample: KILL);
- at least 870 contracts filled per day on average (half the test pessimistic
  rate; below that the flow a live bot needs is not there);
- worst pessimistic drawdown no more than $280;
- median print lag under 0.3 s and fewer than 20 of 100 decision seconds
  skipped for a late print.
On PASS the next step is a live test at 20 contracts per level (a fifth of
size) for 7 more days with a cap of one full ladder per close across all coins
(losses cluster by close). On FAIL: report which line failed and stop.

Read `close_summary` records for per-close money under both models, `fill`
records for what was ahead in the queue, `health` records for lag and gaps.
Two processes will produce two copies of the same answer; the second adds
nothing but a redundancy check and 43 MB.

## 4. What was not covered

- **The taker race was never built** (see section 3). The favourites design's
  fate depends on this box's order latency against offers that live under a
  second; no tape can answer it and no bot is measuring it.
- **Coin Race series (KXCRYPTOLEAD15M / KXCRYPTOCOMP15M):** every design
  excluded them; the digest only verified their settlement (unrounded ranking,
  38 real ties paying 50c).
- **Order books exist only for 09-24..26** (plus partial 09-18/19/22/23 from
  later digest workers). No train day has a book, so no design was checked
  against displayed size on train; the ladder's realistic-fill check covers
  2 of 9 test days only.
- **Tape gaps:** 08-25 partial, 08-26 mostly missing, 09-02/03 corrupt, holes
  on 09-09, 09-15, 09-22, 09-23 -- 2,502 up/down markets (278 per coin) lack a
  full settlement window and were skipped, which may bias toward calm hours.
  09-23 is a partial day in every table.
- **Unfinished refutations:** the bettor's honest-arrival rerun (8 of 9 days
  built, money never re-summed); the ladder's stricter-fill rerun (2 of 9 test,
  6 of 24 train days).
- **Maker fee 0** unverified in any crypto up/down market.
- **Live order latency** of this box: never measured; every "race" number
  above is a guess bracketed by two assumptions.
- **Per-coin, hour-of-day and weekday splits**; the unexplained 45-30 s loss;
  the "post after the sweep" fade of the 2-3-minute favourite and a 99.9c-bid
  rule for the last 8 s (both suggested by the contrarian's measurements, not
  built).
- 2026-09-27 (today, partial) excluded from everything.
- Time-boxes: digest, four designs, two refuters each, holdout, selection,
  two builds (60-120 min each) and this report (45 min).
