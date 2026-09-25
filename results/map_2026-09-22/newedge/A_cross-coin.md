# A. CROSS-COIN

Run 2026-09-23. Read-only. Free RAM 3.08 GB at start, free disk 22.6 GB;
`kalshi_collector.py` and `crypto_feeds.py` untouched and still running (no
process was started, stopped or signalled by this job).

Scratchpad: `C:\Users\Joe\AppData\Local\Temp\claude\C--kals-repo\47b37ac1-655c-4d72-a81b-a48e9625d5bd\scratchpad\newedge\cross-coin\`
(`tape.py` the index reader, `build2.py` the fills join, `corr2.py` the
correlated-miss test, `feat.py` / `impulse.py` the feature sweep).

## Sources and what each is allowed to say

- **Money: `results/kalshi_ledger.json`** (Kalshi's own settlements), 9 crypto
  up/down series only -- BTC ETH XRP SOL BNB DOGE HYPE ZEC NEAR. Coin race
  (`KXCRYPTOLEAD15M`) and commodities excluded. `payout` is the winning side's
  `count_fp`, never `revenue` (which reads 0 on a hedged market).
- **Decisions: `results/pinrun-live-*.jsonl`** (`signal`, `refused`, `order`,
  `hedge*`) -- what the bot believed about every coin at every second.
- **Index: `C:\kals\kalshi_data\cfbenchmarks_value`**, 379 hourly files
  (2026-09-07..09-23), streamed one hour at a time on the EXCHANGE timestamp
  inside `msg.data`, never `received_at`. 14.77 M lines, 243 s, peak RSS well
  under 200 MB. Truncated gzip handled with `research/gzsalvage.iter_lines`.
  **The tape is used only for what the index did and what the model computed.
  Every dollar and every risk number below is from the ledger or our own fills.**

### Correctness gate on the tape rebuild (this is why the numbers can be trusted)

The reader rebuilds, for every coin and every 15-minute close, exactly what
`pinrun.fair` would have computed at tau=45 and tau=30: `K` = the 60-second
settlement average at the previous close (`avg_60s_data.value`), `partial()`
from `settlewin`, `sigma` = `IndexWS._sig_over` over 300 s (SIGMA_RULER
"live", SIGMA_STRESS 1.0), `var_factor(r,[1.0])` from `engine`.

Checked against the bot's own logged values on 783 real fills:

- **strike: 782 of 783 match, median relative error 3.3e-07.**
- **sigma: 777 of 783 within 35%, median relative error 0.6%.**
- settle direction vs Kalshi's `market_result`: 778 of 783; all 5 misses are
  within 1e-5 of the strike (true coin flips plus strike rounding).

**A BUG WORTH RECORDING FOR EVERY OTHER INVESTIGATOR: the datetime in a
Kalshi ticker is EASTERN, not UTC.** `KXBTC15M-26SEP080400` closes at
08:00:00Z. My first pass treated it as UTC and every close time was 4 hours
wrong. The first sigma pass also used `_semi_over` (the undeployed downside
ruler) instead of `_sig_over` and ran 1.5x too wide. Both were caught only by
the gate above; neither would have shown up as an error.

---

# 1. FINDINGS, RANKED BY DOLLARS

## F1. THE MODEL'S MISTAKES ARE CORRELATED ACROSS COINS. RISK DOES NOT DIVERSIFY BY HOLDING MORE COINS IN ONE CLOSE.

**Claim.** When the model is wrong it is often wrong on most of the board at
the same second. One close in the window had **6 of the 8 coins the model was
at least 99.5% sure about all settle the wrong way**. Independence puts that
single close at 9e-13.

**Evidence (index tape; about what the index did and what the model computed).**
20,540 decisions at the live confidence floor (PIN 0.995) across 1,315 TRAIN
closes, at tau=45 and tau=30 separately:

| | tau=45 | tau=30 |
|---|---|---|
| sure decisions | 9,806 | 10,734 |
| closes | 1,315 | 1,314 |
| misses | 16 (0.163%) | 12 (0.112%) |
| model said it would miss | 0.013% | 0.007% |
| **overconfidence** | **12.9x** | **16.9x** |
| misses per close | 1305 x 0, 8 x 1, **1 x 2, 1 x 6** | 1308 x 0, 4 x 1, **1 x 2, 1 x 6** |
| closes with >= 2 misses: observed / independence | 2 / 0.088 | 2 / 0.049 |
| Poisson P | **0.0036** | **0.0011** |
| closes with >= 6 misses: observed / independence | 1 / **8.7e-13** | 1 / **1.3e-13** |

The 12.9x / 16.9x also independently reproduces the known "the model is ~9x
overconfident on our fills" result, on a completely different population.

**Mechanism, read straight off the tape.** The close is **2026-09-11 08:30 ET**
(12:30Z). The previous 15 minutes had the whole basket **down 32.8 bp**. At
45 s to go six coins sat *below* their strikes at z = -3.7 to -8.8 (the model
read NO at 0.9999 to 1.000000 -- DOGE z -8.41, HYPE -8.83, NEAR -8.64), and
the entire basket **snapped +32.2 bp in the last 45 seconds**, carrying all six
back over their strikes at once. BTC, ETH and ZEC were already on the other
side and won. The *next* close moved +206 bp: a market-wide impulse was
starting. Each coin's sigma was measured from its own previous 300 quiet
seconds, so nine independent rulers were all stale at the same instant.
**One common factor, nine positions, one clock.**

**What this costs in real money, from the ledger.** The per-close exposure is
what the tail acts on, not the per-market exposure:

| | TRAIN (515 closes) | HOLDOUT 09-21 on (70 closes) |
|---|---|---|
| dollars at risk in ONE close, median | $41.02 | $75.20 |
| p90 | $142.13 | $149.20 |
| **max** | **$312.79** | **$237.74** |
| worst close realised | -$108.86 (09-19 23:45 ET, on $312.79 at risk) | -$59.09 |

A full basket flip inside a close loses essentially everything at risk in that
close. **The `--loss-abort -60.00` day brake cannot prevent it** -- every leg
is already bought before the close resolves. The only live control that limits
it is the per-close dollar budget, and that budget is `2 x SIZE` (measured in
F3). **So the correct way to read a size increase is: it scales the correlated
single-close tail one-for-one, and nothing downstream catches it.**

**What would make this an artefact, and it was checked.** (a) A wrong strike
would manufacture fake misses -- checked, 782 of 783 strikes match the bot's
own to 3.3e-07. (b) A feed gap at the previous close would corrupt `K` for all
coins at once, which is exactly this signature -- checked, the 12:30Z close has
full 1-second coverage and the six missed coins settled 4 to 60 bp past their
strikes, not by a rounding hair. (c) It is one close, so the *rate* is not
estimable; the *shape* is, and 6-of-8 is not reachable by independent draws.

## F2. OUR MULTI-COIN CLOSES ARE OUR BEST CLOSES, AND THE 2nd AND 3rd BET IN A CLOSE ARE BETTER THAN THE 1st.

**Claim.** Nothing in our realised margins says a marginal extra coin in a
close is a worse bet. The opposite: it is a better one, in TRAIN and in the
untouched HOLDOUT.

**Evidence, Kalshi ledger dollars, TRAIN (closes to 2026-09-20 ET):**

| coins in the close | closes | markets | contracts | net $ | c/contract | bad markets |
|---|---|---|---|---|---|---|
| 1 | 345 | 345 | 15,420 | 158.29 | **1.027** | 17 (4.93%) |
| 2 | 152 | 304 | 15,306 | 240.73 | **1.573** | 11 (3.62%) |
| 3 | 16 | 48 | 1,756 | 47.11 | **2.683** | 1 (2.08%) |
| 4 | 2 | 8 | 484 | 16.75 | **3.460** | 0 |

HOLDOUT (09-21 ET on, 70 closes, ONE look): 1 coin +0.019 c/contract (3 of 50
bad); 2 coins **+2.771** (0 of 38 bad); 3 coins +2.363. Same ladder.

**By entry order inside the close** (TRAIN):

| entry | markets | contracts | net $ | c/contract | bad | median tau | median price |
|---|---|---|---|---|---|---|---|
| 1st | 509 | 23,299 | 272.32 | 1.169 | 18 | 29 s | 97.3c |
| 2nd | 169 | 8,748 | 180.18 | **2.060** | 6 | 24 s | 96.5c |
| 3rd | 17 | 670 | 24.23 | **3.617** | 0 | 23 s | 97.0c |

Like-for-like, inside the 17 closes that reached 3 coins: 1st 2.261, 2nd
2.346, **3rd 3.617** c/contract, zero bad markets at any rank.

**Mechanism.** The later bet in a close is taken at a shorter tau (24 s vs
29 s) and a lower price (96.5c vs 97.3c), so it buys more of the variance
collapse for less. It is the cheap late leg the missed-deals work already
priced at +5.45c/contract at 90-95c inside 30 s.

**What would make it an artefact, and how far it was checked.** A 2-coin close
is a close where two takeable offers existed, so the ladder is partly a
*market-quality* proxy and the causal reading ("hold more coins") is NOT
established. The restricted table (within >= 3-coin closes only) removes that
confound for the rank comparison and the ordering survives. The conservative
statement both tables support: **the per-close budget is not protecting our
margin; it is only protecting the bankroll** -- and F1 says the bankroll
protection is real and is the only one we have.

## F3. WHAT LIMITS COINS PER CLOSE IS THE DOLLAR BUDGET (2 x SIZE), NOT THE POSITION COUNT. `--max-positions 3` HAS NEVER ONCE FIRED.

- `max_per_close` refusals in 128 live runs: **0**.
- `close_budget` refusals on coin markets: **478**, all distinct
  (close, coin) pairs, on **70 closes**. Median `spent` $158, median `budget`
  $158, median `size_now` 79 contracts -> **budget = 2.00 x SIZE** exactly.
- Per ET day: 09-14 126, 09-15 72, 09-16 63, 09-17 70, 09-18 90, 09-19 18,
  09-20 19, 09-21 12, 09-23 8.

**HYPOTHESIS, index only, not money:** of the 478 turned-away (close, coin)
pairs, the model's side went on to win **370 of 371** usable ones (0.27% index
miss rate, the ordinary tape rate). **This cannot be priced from here** --
`close_budget` fires BEFORE the book is read (pinrun's own comment says so:
"close_budget refusals are counted, not valued"), so nothing in the log knows
whether a takeable offer existed, and the missed-deals work found only 29 of
236 closes had a confirmed standing offer we did not take. Do not put a dollar
figure on this until that gate is moved after the book read.

---

# 2. REFUTED OR NOT SUPPORTED

## N1. "The other coins at our decision second predict our market." NO -- eight feature families, nothing.

Tested on the 20,540 tape decisions (28 misses) and on our 697 TRAIN fills.
Quintiles were printed for each; none monotone, and tau=45 and tau=30
contradict each other wherever one looks interesting:

| # | cross-coin feature at the decision second | result |
|---|---|---|
| C1 | how many other sure coins DISAGREE with our side | not monotone; opp=2 reads 40x at tau=45 and opp>=3 reads 23x at tau=30 |
| C2 | how many other coins are contested (conf < 0.99) | q1 has 0 misses at tau=45 and 6 at tau=30 |
| C3 | basket volatility now vs 15 min ago | flat |
| C4 | our coin's vol change divided by the basket's ("is my ruler stale?") | flat |
| C5 | basket median abs(z) | not monotone |
| C6 | cross-sectional spread of abs(z) | not monotone |
| C7 | size of the basket's last completed 15-min move | q4 37x, q5 8.6x -- not monotone |
| C8 | our side is betting the last basket move CONTINUES | 2.9x at BOTH taus -- see below |

**C8 looked like the answer and is not.** With-move 0.2426% vs against-move
0.0829% at tau=45, and 0.1653% vs 0.0570% at tau=30, with the model pricing
both groups identically. **Drop the single 09-11 08:30 ET close and it
vanishes**: tau=30 becomes 0.0552% vs 0.0571% -- identical. Six of the nine
"with-move" misses were that one close.

**The honest reason nothing can be found here, stated as an MDE.** Sixteen
misses at tau=45, and 8 of them sit in 2 closes. Clustered by close, the
effective sample is about **ten independent miss events in five weeks**. For a
pre-declared fifth of the population (4,100 decisions, 5.6 expected misses) to
clear the multiple-looks bar (0.05 / 14 looks = 0.0036) it needs **14 misses,
a 2.5x concentration**. Anything smaller is invisible. **This is not "no
effect", it is "no power", and no amount of cleverness with this tape fixes
it** -- the binding constraint is the number of independent bad closes, which
grows at about two a week.

## N2. "The unanimous basket marks our losers." It looked strong on our own fills and the tape kills it.

From the fills it was the best thing found: flag UNANIMOUS = at least 6 other
coins observed, at least 5 of them >= 99.5% sure, **none on the opposite side**.
TRAIN 31 markets, -$176.03 on 2,348 contracts (**-7.50 c/contract**, 4 of 31
bad) against +$675.75 / +2.157 c/contract on the other 666 markets. HOLDOUT
agreed in sign (4 markets, -$29.44, 1 of 4 bad). Permutation with closes
shuffled inside the ET day: P = 0.034.

**It does not survive.** (a) Day-blocked it is one day: 09-14, 09-15, 09-16,
09-18 and 09-20 all favour unanimous; 09-19 alone carries -$216 of the -$176
(day-blocked t = -0.63 on 6 days). (b) On the tape, with 100x the n, unanimous
baskets **miss LESS**, not more -- 0.068% vs 0.234% at tau=45 and 0.024% vs
0.171% at tau=30 -- and the overconfidence RATIO is identical in both groups
(13.2x vs 13.4x). (c) P = 0.034 does not clear 0.05/14. **Do not deploy it.**

## N3. "Two coins in one close lose together more often than independence says." Our own fills cannot tell, and the MDE says why.

TRAIN, 170 multi-coin closes: closes with >= 2 outright losses **0**
(independence expects 0.06); closes with >= 2 hedged markets **1** (expects
0.12). To reject independence on our own fills would need a **23x to 41x**
concentration -- that is the MDE, and it is useless. F1 answers the same
question from the index, where the n exists.

## N4. "False-alarm hedges fire on several coins at once." n = 1.

The hedge machinery (`hedge`, `hedge_alarm`, `hedge_panic`, `hedge_prop`,
`hedge_gave_up`, `hedge_no_ask`) fired on 20 closes across the whole history
and on **two different coins in the same close exactly once**: 09-19 23:45 ET,
HYPE (belief 0.4368) and XRP (belief 0.2733) one second apart, both false
alarms, both settled the way we were already positioned, **-$108.86 together**
-- about half of that day's -$223.46. Every market that held both legs at
settlement: 20 markets, 7 false alarms (-$137.57), 11 real saves (-$309.11),
2 with no side on record. **One event is not a pattern**, and the correct
reading is that it is F1 seen from the hedge side: one common factor dropped
two beliefs in the same second.

---

# 3. COULD NOT MEASURE, AND WHY

- **What the 478 `close_budget` refusals were worth.** The gate fires before
  the book read, so no log line knows whether an offer existed. Moving the
  budget check after the book read is the whole fix, and pinrun's own comment
  already names it.
- **Whether a basket-wide impulse is visible in the CONSTITUENT books before
  the CF index prints it.** `C:\kals\feed_data` was not opened: the F1 event is
  a single close, so even a perfect lead signal has n=1 to be fitted on. The
  right order is to get more independent bad closes first, and that is calendar
  time, not analysis.
- **`C:\kals\cdc_data` (Crypto.com), `orderbook_delta` / `orderbook_snapshot`.**
  Not opened. RAM budget (~500 MB cap with the live bot and the paper fleet up)
  and the same n=10 ceiling.
- **Whether holding 3 coins would have changed a real close.** There are only
  16 three-coin closes and 2 four-coin closes in TRAIN.

---

# 4. SOLUTIONS WORTH TESTING

Ranked. Every one states what it blocks. **None of them touches the hedge
path: no proposal here can delay, resize or suppress a hedge.**

### S1. Size from the CLOSE, not from the market. (lose less; no entry blocked)

F1 says exposure inside one close is one bet, not k independent bets. The live
bot already has the right lever -- `close_budget` = 2 x SIZE -- but it was set
as "two markets at full size", not as a tail number. Make the per-close budget
an explicit dollar cap tied to the bank and let the coin count float under it.
**What it blocks:** nothing new. It re-labels an existing cap and, at the same
total, lets a close hold 3 or 4 coins at smaller size instead of 2 at full
size, which F2 says is the better margin anyway.
**Validated on:** live fills -- per-close realised P&L and per-close dollars at
risk, both already computable from `kalshi_ledger.json` (the table in F1).
**Pre-registered bar before deploying:** median c/contract must not fall, and
max dollars at risk in one close must fall. Both readable in ~150 closes.

### S2. Publish "dollars at risk in this close" as a first-class live number.

Today the only per-close exposure figure is implied by `spent` inside a
`close_budget` refusal. The tail in F1 acts on exactly this quantity and
nothing displays it. **Blocks nothing** (logging only, and the logging IS the
test). Cheap, and it is the input S1 needs.

### S3. A paper arm at `close_budget = 3 x SIZE`, size scaled to hold the dollar cap flat.

F2's ladder, holdout-confirmed, says the 2nd and 3rd coin are the better bets.
This tests "more coins, same money" rather than "more money". **Blocks nothing;
risks nothing** (paper). **Bar:** pre-register c/contract >= live and max
per-close risk <= live, over >= 150 closes, before the number is read.

### S4. Do NOT deploy the unanimous-basket gate, and keep the record of why.

N2 is the strongest-looking thing in this file and the tape says it is
backwards. It would have blocked 31 entries, giving up +$68.66 of wins to avoid
-$244.69 of losses on our fills -- and on 100x the index n it would have been
blocking the **safest** population.

### S5. Move the `close_budget` check after the book read (F3).

Until then the 478 refusals cannot be valued and the only honest answer to "are
we leaving money at the budget?" is "unknown". It also gives S1 and S3 a
scorable gate. **Blocks nothing** -- it changes when we refuse, not what we
refuse. The code comment warns this is a real behaviour change, so it belongs
in a paper arm first.

---

## Multiple-looks accounting (declared, not reconstructed)

14 cut families: coins-per-close, same-vs-mixed side, oth_sure, oth_contested,
oth_same, oth_opp, oth_seen (our fills); C1..C8 (tape). Bar for any single
claim: **0.05 / 14 = 0.0036**. F1's close-level test clears it at both taus
(0.0036, 0.0011) and its 6-of-8 close clears it by twelve orders of magnitude.
N2 (P = 0.034) does not. F2 is not a significance claim -- it is a margin
ladder that reproduces in an untouched holdout.
