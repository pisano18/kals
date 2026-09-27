# THEORY.md -- how these markets move, why the edge exists, and what we actually know

**Written 2026-09-17 for the models that come after.** `CURRENT_STATE.md` says
what is running. `HANDOFF.md` is the chronological log. `PROJECT_HISTORY.md`
says what was killed. **This file is different: it is the MENTAL MODEL.** Why
the thing works at all, what the mechanism is, which beliefs are load-bearing,
and which of them are actually evidenced. If you read one file before changing
the strategy, read this one, then check its claims -- every section says what
would falsify it.

---

## 1. The instrument

Kalshi 15-minute binary markets. Each asks: **will the index be above strike K
at the close?** It pays $1.00 or $0.00. We are always a TAKER (immediate-or-
cancel, never resting). Takers pay `0.07 * p * (1-p)` per contract; makers pay
nothing. At 95c the fee is 0.33c; at 50c it is 1.75c. **The fee is smallest
exactly where we trade, which is not a coincidence -- it is most of why buying
near-certainties is viable at all.**

Two families, and they behave in OPPOSITE ways. Getting this backwards is the
single most expensive mistake available here.

### 1a. Crypto (KXBTC15M and 11 siblings) -- settles on a 60-second AVERAGE

Settlement is the **mean of 60 one-second CF Benchmarks prints** over the final
minute. And `strike(N+1) == settle(N)` exactly: each window's strike is the
previous window's settlement. (That identity is why cross-strike arbitrage is
*undefined* here rather than merely absent -- there is one strike per window.)

The consequence is the whole business. With `tau` seconds left, `60 - tau` of
those prints are **already recorded and cannot change**. Only `tau` of them are
still unknown. So

    settle = (locked_sum + sum of tau unknown prints) / 60

and the variance of what remains is `Var(settle - strike) = 880 * sigma^2` at
tau = 10, not the `sigma^2 * tau` a random walk would give. **Uncertainty
collapses far faster than `sqrt(tau)`** -- 9.7x faster at tau = 10. Fair value
is `Phi(((locked_sum + tau*spot)/60 - K) / sd)`, and its sensitivity to sigma
is exactly zero at 50c (which is why a sigma error is survivable near the
middle and dangerous near the edges).

**So crypto certainty ARRIVES LATE and arrives fast.** At 3 minutes out almost
nothing is locked; at 30 seconds half the average is already on disk; at 5
seconds the answer is nearly arithmetic. Our whole edge is buying the moment
the arithmetic is decided but before the price fully reflects it.

### 1a-ii. WHY 60 SECONDS IS A WALL, AND WHY 30 AND 45 ARE ROUND NUMBERS

The operator asked the right question: *"The number should be based on math and
it seems highly unlikely the math would select such a clean number like 45."*

He is right that 45 is not derived, and there is a clean reason the numbers
look round. **The settlement window is exactly the last 60 seconds** --
`settlewin.partial()` sets `lo = close_sec - N_AVG` with `N_AVG = 60`, and
returns "nothing locked in yet" before that. So the fraction of the settlement
average already determined is

    locked fraction = (60 - tau) / 60        for tau <= 60, and ZERO beyond it

| tau | share of the settlement already fixed |
|---|---|
| 60 s | 0% |
| 45 s | 25% |
| 30 s | 50% |
| 20 s | 67% |
| 10 s | 83% |

**So 30 and 45 are round in TAU because they are round in LOCKED FRACTION --
one half and one quarter.** That is the whole explanation for the clean
numbers, and it means the answer to "can we go further back" is:

**No further than 60 seconds, and that is arithmetic, not opinion.** At tau =
60 nothing is locked, the averaging has not begun, and our entire mechanism --
knowing part of the answer already -- contributes exactly zero. Past 60 we
would be forecasting a price a minute out with no privileged information,
which is what every other participant is doing.

**The market's own record agrees with the arithmetic, which is the strongest
kind of confirmation.** By markets, buyers of 95-98c lose 2.8% at 31-45 s
(25-50% locked), 3.6% at 46-60 s (0-23% locked, break-even ~3.4%), and 4.9% at
61-90 s (nothing locked). The edge decays to zero exactly where the locked
fraction does.

**One correction to how people think about TAU_MAX here.** The bot's real
decision is already continuous and derived: `fair()` computes the win
probability from the locked sum, the spot, sigma and the strike, and the gate
is "probability >= 99.5%". **That is the math choosing the moment, per market,
every second.** TAU_MAX is a separate, cruder rail bolted on top of it. What
that rail actually protects is not the settlement arithmetic but the SIGMA
estimate: the less of the average is locked, the more `fair` leans on a
volatility guess, so an error in sigma is amplified as tau grows. If TAU_MAX is
ever revisited, the principled replacement is not another round number -- it is
to require more confidence when less is locked.

### 1b. Commodities (KXGOLD15M, KXWTI15M, KXSILVER15M, KXCOPPER15M, KXNATGAS15M) -- settle on ONE INSTANT

The rules text is explicit: settlement is the **close of the 1-minute Pyth
candle** at the close, and the strike is the **previous candle's close**. There
is no averaging. Nothing locks in progressively. The outcome is decided by one
price at one instant, at the very end.

**So commodity certainty has a completely different shape: a U.** Measured over
5 days, gold at 95-99c, counted in MARKETS (rule 4):

| when | markets | favourite lost |
|---|---|---|
| last 15 s | 149 | 2 |
| 16-90 s | 423 | 21 |
| 91-180 s | 379 | 2 |

Good at both ends, dangerous in the middle. **The mechanism:** far from the
close, the price has already walked a long way from the strike, and the market
still prices in a reversion that mostly does not come -- the favourite is
UNDERPRICED. In the middle, the outcome genuinely hangs on where the last
candle closes, so a "near-certainty" is not one and the buyers get picked off.
In the last seconds the candle is nearly formed and it is decided again.

**This was discovered late (2026-09-17) and only because someone looked past
60 seconds.** Every earlier commodity read said "only the last seconds work",
which was an artefact of never looking further out. *Falsifiable:* if the U
disappears on the next 5 days of tape, the mechanism story is wrong.

**Corollary worth carrying:** crypto's edge lives in the last minute and
commodities' edge lives at both ends, and the reason is entirely in the
settlement formula. **Before trading any new series, read its settlement rule
first and predict the time-shape from it.** Averaged settlement -> late
certainty. Instant settlement -> U-shape. This is the most transferable thing
in this file.

---

## 2. Why there is money here at all

A binary at 97c that resolves YES 99% of the time pays `0.99*0.03 - 0.01*0.97
- fee = +1.8c` a contract. Small, frequent, and it compounds. The question is
always **why is anyone selling at 97c when the answer is nearly known?**

Honest answers, in order of how much of the edge each probably explains:

1. **They have not done the locked-average arithmetic.** Most participants
   price a 15-minute crypto binary as if the outcome were a fresh coin flip
   scaled by time remaining. It is not: most of the average is already fixed.
   This is the only explanation that is genuinely *structural*.
2. **Inventory and exit.** A holder who wants out before the close sells at a
   discount to certainty. This is real, and it is why offers exist at all.
3. **Fee asymmetry.** Makers pay nothing, so resting an offer near certainty is
   cheap for them and only we pay to cross.
4. **They are right and we are wrong.** This is the one that costs money, and
   it is not rare: our live loss rate is 4.66% of closes while the model claims
   99.5% confidence. See section 4.

**What would falsify the whole thesis:** the loss rate on our fills rising to
where `(1-p)` no longer covers it -- roughly 3.4% at 96.5c, 1.5% at 98.5c.
We are at 4.66% of CLOSES but our fills cluster at 95-98c and we are still net
positive, which means the loss rate *per fill* is lower than the per-close
number and the winners are carrying it. **Watch the per-fill loss rate at each
price band, not the headline.**

---

## 3. THE POPULATION TRAP -- the most important epistemics in this project

**The tape and our fills are different populations, and they differ by 31x.**

- The tape's population is *"an offer was sitting there at price p"*.
- Ours is *"somebody chose to sell it to US, right then"*.

Measured 2026-09-11 at the identical gate: tape says 0.11% lose (1 of 891
markets, CI [0.00, 0.61]); live says 3.4% (2 of 59, CI [0.4, 11.7]). **The
intervals do not overlap.** The difference is adverse selection and it is
structural and permanent: the offer that reaches a taker is disproportionately
the one an informed seller wanted gone. The 82c XRP fill we actually took does
not exist anywhere in the replayed book.

**Operational rules that follow, and they are not negotiable:**
- The tape is valid for: what the index did, what the market did, what prices
  existed. It is **INVALID** for how often WE lose or what a rule would cost US.
- A paper arm can **KILL** an idea. It can never **DEPLOY** one. Only live
  fills can, which is why penny tests exist.
- The backtest (`pinsim.py`) is certified only for reproducing decisions, never
  loss rates. Any finding resting on it is a hypothesis; say so in the first
  sentence.

This rule has been broken repeatedly, including by me, and it produced every
"large edge" that later evaporated.

---

## 4. Clustering, and why `n` is almost always smaller than it looks

All twelve crypto series settle on the **same quarter hour** and are roughly
0.8 correlated. Twelve markets on one close are worth about **1.22 independent
observations, not 12**. So:

- Report `n` in markets or closes, never trades. Hundreds of trades share one
  settlement.
- A cell that reads "10% lost" on 3,000 trades may be three markets.
- This is not pedantry: on 2026-09-17 gold's "0.1% lost on 2,102 trades" became
  **1 loss in 53 markets** when counted properly -- break-even, not a gold mine.
  The by-markets recount changed the entire commodity design.

**Corollary about the model's calibration.** The model claims 99.5% and we lose
4.66% of closes. That is a 9x gap, and it is NOT mainly model error: measured
on the index alone across 14,261 closes, the model is wrong 0.058% of moments
at 31-45 s and 0.021% at 21-30 s -- roughly 1/200th of the live loss rate.
**Our losses are overwhelmingly adverse fills, not bad arithmetic.** This
matters enormously for what to tune: tightening the confidence gate cannot fix
a problem the confidence gate did not cause.

---

## 5. What actually stops us buying (measured, 5,269 live refusals)

| gate | share | what it means |
|---|---|---|
| no_offer | 51.8% | nobody was selling the side we wanted |
| edge_floor | 17.9% | edge under 0.3c after fee |
| depth_floor | 7.5% | book offered less than we asked |
| price_ceiling | 7.0% | ask above 98c |
| confidence | 5.6% | model not 99.5% sure |
| close_budget | 5.1% | the close's contract budget was spent |
| both_sides | 2.4% | |
| everything else | under 1.5% each | book_stale, jump_against, dump_guard, ... |

**Read this table before proposing a change.** Half of everything is "nobody
was selling", which no gate change can fix -- it is a supply problem, not a
policy problem. The largest gate WE chose is the edge floor.

**There is NO price floor.** We will buy at any price the confidence gate
allows. Of 472 live fills: 0.4% under 50c, 6% at 80-90c, 21% at 90-95c, 58% at
95-98c, 14% above 98c; the cheapest fill was **10 cents**. The only price
restriction is the 98c CEILING. (The 90c number that appears in commodity work
is `cmdarm`'s window, a different system entirely. If a future reader thinks
crypto has a 90c floor, they have confused the two -- it has happened.)

### 5a-ii. THE SQUEEZE: why the run earns less per day than it did

Measured 2026-09-17. **The margin is NOT falling. The volume is.**

| ET day | bets | contracts | cents per contract | made |
|---|---|---|---|---|
| 09-13 | 50 | 2,194 | 5.23c | +$114.77 |
| 09-14 | 63 | 3,319 | 2.44c | +$81.14 |
| 09-15 | 35 | 2,431 | 3.14c | +$76.32 |
| 09-16 | 48 | 3,012 | 2.83c | +$85.10 |
| 09-17 | 29 | 1,682 | 3.13c | +$52.60 |

Cents per contract is flat at 2.4-3.1c. What has fallen is how many bets exist
to make. **We are being squeezed from both ends of the price range:**

- **From above:** the share of refusals that are "too expensive" -- price
  ceiling plus edge floor, which the review showed are the same class because
  every edge_floor refusal sits at 99.2c or higher -- has gone from **20.4% of
  refusals on 09-13 to 29.0% on 09-17**, with the ceiling class alone doubling
  from 4.4% to 8.6%. Offers are drifting above 98c.
- **From below:** the dump guard refuses everything under ~84.5c
  (`results/RESULTS_dumpguard.md`). An earlier claim here that this costs $82
  a week was WRONG and is corrected in that file: of 17 flagged markets the bot
  BOUGHT 10 of them seconds later when the discount narrowed, so they were
  delayed rather than blocked. Its true cost is unmeasured and small.

So the honest diagnosis is not "the edge is decaying". It is **"the window of
prices we are willing to pay is narrowing while the market drifts out of it."**
Those are different problems with different fixes, and the second one is
partly self-inflicted.

### 5a. THE CAPACITY CEILING -- the most important structural fact about this strategy

The funnel, in markets (not evaluations): **7,422 markets watched -> 526 we
decided to buy (7.1%) -> 467 filled (6.3%).**

`no_offer` is by far the largest blocker, and it is REAL, not a book-reading
artefact. Every one of the 2,736 `no_offer` records was checked: **2,736 of
2,736 had genuinely no ask at all on the side we wanted** -- not an ask at 100c,
not an ask we discarded for size or staleness. Nothing. Meanwhile **2,551 of
them (93%) DID have an ask on the losing side.**

On a binary book those two facts are the same fact. An ask on the loser at 2c
is a bid for the winner at 98c. So the picture is: **when the outcome becomes
obvious, the winning side has BIDS but no ASKS.** Everyone wants to buy the
near-certain dollar; nobody will sell it. That is not a policy we can loosen.
It is the supply of the whole strategy.

**The one avenue it leaves is resting a bid and waiting -- and that has been
measured and KILLED**, with a mechanism that should be remembered every time
someone re-proposes it (`results/RESULTS_maker.md`, 9 days, 7,266 gated
markets, 793 closes; resting loses to taking in 113 of 114 rows):

> a bid resting one tick under the ask for 5 s was filled on **29.0% of the
> markets that went on to WIN** and on **100% of the 17 that LOST**.

Nobody sells you a near-certain contract for no reason. The seller who reaches
down to your bid is the one who already knows. Resting does not even deliver a
better price (94.16c vs the taker's 94.05c), because the entries where a
resting bid fills are the contested expensive ones. Cancelling on a belief flip
does not save it either: every loser fill lands BEFORE the pull.

**What this means for anyone hunting for money here:** roughly a third of all
opportunities are unreachable by any gate change, and the reachable levers are
only the ones we chose -- the edge floor (12.7% of watched markets), the
ceiling (5.0%), depth (5.3%), and the close budget (3.6%). Do not spend effort
trying to convert `no_offer`; spend it on those four, on the SIZE of the fills
we do get, and on losing less.

---

## 6. The wobble: when a favourite is really flipping

Conditioned only on what a trader could SEE -- the lowest price the favourite
(>=90c with a minute left) traded at inside the last 30 seconds -- across 1,717
crypto markets:

| favourite fell to | markets | it then LOST |
|---|---|---|
| stayed 90c+ | 1,511 | 0 |
| 80-90c | 17 | 0 |
| 70-80c | 16 | 0 |
| 50-70c | 15 | 0 |
| **under 50c** | **158** | **120 (76%)** |

**A dip that stops above 50c recovered 48 times out of 48. A crossing below 50c
was a real flip three times in four.** The 50c line is the table's own break,
not a fitted parameter.

Why this matters: our model re-prices from the index alone and panics at moves
the market shrugs off. The market's own price is a second, partly independent
opinion, and above 50c it has been the better one. This motivated AMENDMENT 47
(`--hedge-price`, shipped OFF, in paper). *Falsifiable:* if the 50-90c bucket
ever accumulates real losses, the "dips recover" claim dies.

---

## 7. How the bot is built, in one page

- `research/pinrun.py` (~7,000 lines) is the bot: one process, a 20 Hz loop
  over every open market, a decision per market per tick, orders via
  `pintake.take` (IOC, `post_only=False`, never rests).
- `research/pintake.py` is the ONLY path to the wire. Every rail is checked
  BEFORE signing, and the self-test reads the function's own source to prove
  the check precedes the send. Production must be explicitly armed.
- `research/livebook.py` maintains the order book from the WebSocket feed;
  `IndexWS` carries the 1/sec settlement index on its own authenticated socket
  (reading the collector's growing gzip once a second cost more than a second).
- Sizing is automatic from the bank (`BANK_BRAKE 3.0`), with a 20% drawdown
  brake against a persisted high-water mark.
- Paper arms are the same file with different flags, so an experiment is never
  a different implementation. This is why arm-vs-control comparisons mean
  something.
- The self-heal stack: `watch_bot.ps1` restarts on a stale HEARTBEAT (not a
  live process -- **"running is not working"**), `boot_all.ps1` is an
  idempotent supervisor, `restart_bot.ps1` checks FLAT/HOLDING via
  `pinflat.py` before restarting.
- **Tickers encode EASTERN time, not UTC.** `KXBTC15M-26SEP170000-00` closes at
  midnight ET = 04:00Z. This has caused two separate wrong-answer bugs.
  `research/pinday.py` is now the only place day totals are computed.

---

## 8. The recurring bug classes (every one of these has bitten, most twice)

1. **Population confusion** -- quoting a tape number as if it were ours. See 3.
2. **Trades where closes belong** -- see 4.
3. **The ET/UTC ticker clock** -- see 7.
4. **A refusal record marks a MOMENT, not a market.** Before claiming a gate
   cost money, check whether the market was traded anyway a second later. On
   2026-09-17 this turned a confident "the dump guard blocked $82 of winners"
   into "it delayed 10 of 17 and we own them". Same family as counting trades
   where rule 4 wants closes.
5. **Reading a field that does not exist scores every row the same way.**
   Order records carry the side in `body.side` (`bid`=YES, `ask`=NO) and have
   no `want`; hedge records use `side`, not `want`. Both mistakes were made in
   one day and each one INVERTED the conclusion -- once to "all 14 hedges
   wasted", once to "13 of 13 cheap fills lost". If a result is unanimous,
   suspect the field before believing the finding.
4. **Self-test needles that match the self-test's own source.** A check like
   `src.index("def trade_loop(")` finds the literal inside the test and slices
   the wrong region, then passes vacuously. **Build needles from pieces.**
5. **Asserting the RUNNING value instead of the SHIPPED default.** A gate that
   reads the live global fails the moment an arm sets the flag. Assert against
   an explicit `_DEFAULT_*`.
6. **`None` meaning two things** -- "not supplied" and "off" in the same
   argument. Use a sentinel.
7. **A guard measuring the wrong quantity.** The commodity test capped GROSS
   TURNOVER at $10 and halted a working experiment, when the actual risk was
   bounded at ~$2 by a loss brake. Turnover is not risk when capital recycles.
8. **A rail written for one caller applied to another.** `pintake`'s 90-second
   window is right for crypto and silently refused every commodity far-window
   order until it was made per-caller.

---

## 9. What is BELIEVED vs MEASURED (be honest about which you are standing on)

**Measured on live fills (strongest):** our loss rate; the fill fraction and
that it falls as size grows; hedging's net effect (+$14.30 over 12 hedges);
that we trade below 90c.

**Measured on the tape (valid for market behaviour, NOT our losses):** the
U-shape in commodities; the wobble table; the crypto time-frontier at ~60 s;
where volume sits by seconds-to-close.

**Measured on the index alone (no book, so no adverse selection):** model
calibration -- 0.058% wrong at 31-45 s. This is the cleanest evidence we have
about the MODEL, and it is why model error is not our problem.

**Believed but not established:** that the 0.3c edge floor is the right number
(inherited, never re-measured against live fills); that MAX_PER_CLOSE = 2 is
correctly sized now that SIZE autosizes; that the 98c ceiling is optimal
(the arithmetic supports it at today's loss rate, but the loss rate is the
input and it moves); that the market is not adapting to us.

**Known unresolved tension:** the drawdown brake is 20% of the high-water mark
while `BANK_BRAKE 3.0` implies the worst close costs bank/3 -- a 1.66x
inconsistency, harmless only because two coins have never both lost on one
close (0 of 101). The operator has accepted "whichever comes first". If that
0-of-101 ever becomes 1, this matters immediately.

---

## 10. If you change one thing, change it like this

1. Write the bar FIRST, in `results/PREREG_*.md`, before you see the number.
2. Run it as a paper arm beside an unchanged control, same file, different flag.
3. Read it only at the pre-registered minimum n, in markets or closes.
4. If it passes, it earns a LIVE test with its own bar -- not a deployment.
5. Log a `v-<name>` entry in `results/VERSIONS.md` **at the moment of deploy**,
   with the copy-pasteable revert.
6. Never move a bar after seeing the result without saying so loudly and
   dating it.

The reason for all of this ceremony is in section 3: the cheap ways of
evaluating an idea are measuring a different population than the one that takes
our money.

---

## 11. Added 2026-09-27 after the $131.98 BTC loss (results/POSTMORTEM_2026-09-27.md)

Four things the post-mortem changed or sharpened in the model above.

1. **"Someone actively sold it to us" now has timestamps.** In the 04:00Z BTC
   market the offer we hit was a 1,000-lot flashed at 97.9c and cancelled
   within 3-15 ms, dozens of times a second, while takers had sold 56-58% of
   the last 3 s of YES volume. A NO-taker burst hit YES at 99c 130-220 ms
   before the Kalshi book collapsed 99c -> 55c, and that collapse is stamped
   within 10-20 ms of Coinbase's first down-tick (inside clock error). The
   seller on Kalshi did not react to the exchange move; the seller WAS the
   move. Consequence for section 3: an exchange feed cannot see this class of
   loss coming (0 of 13 feed-coin losers were lone-venue moves; nothing moved
   against the entry in the 5 s before the sweep). The only decision-time
   marks are on the Kalshi book itself: offer age and the taker sell share.

2. **Model error is still not the problem, and neither is the ruler.** The
   bot's 0.998 re-derives to nine digits from its inputs. The move that
   settled it was -$22.12 in one second: 23 of the 5-minute ruler's wobbles
   and still 14 of the hour's. A wider ruler (hour, or 30-min downside) would
   have refused this entry and 10 other losers, but refuses 465 of 853 of our
   markets and loses $17-26/day on the full record, in both halves. There is
   no width at which a one-second $22 print is priced at 30 s to close
   without giving up most of the trade. The defence against this loss class
   is a gate on the SELLER (section 11.1), not on the volatility input.

3. **Waiting is not protective.** "The index only just crossed to our side"
   does not separate our losers (5 of 137 under 10 s vs 2.2 per 100 overall,
   under what n can see) and every wait-N-seconds or bigger-cushion rule
   loses money. The thinnest locked cushion was the best band. The 09-27
   entry had been on our side 24 s. "It was a coin flip a minute earlier" is
   the ordinary shape of 73 in 100 of our markets and the losers in that band
   sit exactly at the base rate.

4. **New measurement bug classes for section 8:**
   - **The recorder's book is not the bot's book at millisecond resolution.**
     Rebuilt from orderbook_delta, the best ask sat BELOW the price our IOC
     actually paid in 52 of 144 legs (phantom levels) and ABOVE it in 36
     (missing levels), and the recorder's Kalshi socket lagged 1.0-1.5 s
     during the 09-27 burst. The fill proves the bot's book. For offer age and
     sell share, the bot's own logged value is primary; a tape rebuild only
     fills days the bot did not log, and under-detects fresh offers there.
   - **A source log that silently lost 19 hours.** The on-disk
     `pinrun-live-20260925T122357Z.jsonl` begins 09-26 07:31Z; the committed
     copy holds 09-25 12:24Z onward. A finder counted 18 holdout markets where
     there were 27. Before trusting a log, count its settled markets per day
     against `kalshi_ledger.json`.
   - **Dropping rows for a missing feed hour drops the losers with them.** The
     index-freshness finder lost 31 markets to missing index hours, including
     the second-largest loss in the set, and its "negative in both halves"
     flipped in one half when it was put back. Print every dropped row's
     money, not the first five.
   - **A random-sign control must keep the flagged set the same size.** A
     null that flags twice as many markets as the observed rule has a
     narrower spread and manufactures P < 0.001 where the exact answer is
     0.05-0.07.

5. **Text correction to section 1a.** "Var(settle - strike) = 880 sigma^2 at
   tau = 10" does not match `engine.var_factor`, which gives the sum of
   k^2 for k = 1..10 = 385 over 60^2; the section's own "9.7x" ratio matches
   385, not 880. Typo in the prose, not a code bug. (CLAUDE.md's settlement
   paragraph repeats the 880.)

**What would falsify 11.1-11.2:** a week of the live `--toxic-fresh` gate
whose refused set contains no market that settled against us while it skips
more than $75 of wins (PREREG_toxic's own KILL figure); or a loss of this
size whose entry the gate passed (as it would have passed the 09-24 00:30Z
-$130.40 loss: fresh offer, sellers only 34 in 100).

## 12. Added 2026-09-27 after the "why no money" synthesis (results/WHY_NO_MONEY_2026-09-27.md)

Four things changed in the model. Every number is our own fills, 09-09..09-27.

1. **The edge is a thin per-contract margin, and it did not move; the bank did.**
   Losing markets per 100 were 2.3 then 2.0. What changed is that a loss is
   now 41 wins instead of 15: SIZE followed the bank ($190 -> $1,150) while the
   market kept selling roughly the same 20-70 cheap contracts a market, so the
   average win went $1.69 -> $1.93 and the average loss $25 -> $80. In bank
   terms a win is 0.20% of the bank (was 0.60%) and a loss item 6.2% (was
   5.5%): per $100 staked the bot keeps 2c where it kept 39c. Consequence for
   section 2: profit is (price margin) x (contracts filled at that margin),
   and the second factor is capped by supply, not by the bank. Doubling SIZE
   past the cheap supply adds variance, not return. The per-CONTRACT loss
   share rose 1.88 -> 2.93 per 100 because losers carry 1.5-2x the contracts
   of winners in H2 (double same-second legs; early third-size legs on the
   winners) -- a composition effect, not worse picking.

2. **Two thirds of markets are now the 45-second leg.** 328 of 499 H2 markets
   opened at 31-45 s with a third of SIZE at ~97c (31 of 471 in H1); only 28
   ever topped up. It netted +$51 after its own hedges (-$72). The main leg
   (first fill <= 30 s) still prices at 95.7c and, without the two double-leg
   BTC markets, still earns 2.6c a contract -- H1's number. So "the strategy
   stopped working" is false; "the strategy is now mostly a different, dearer,
   smaller leg plus two double bets" is what the record says. The arm without
   the early leg made less on the same hours (it adds markets), and the arm
   with a FULL early leg made more on a no-loss window while 09-19's $403 fell
   in the days it ran full: the early leg's SIZE is an open question, its
   existence is not.

3. **No loss identifier holds in both halves (sharpens section 3 and 11.1).**
   The toxic cell, the >= 10x wall, the 45-s confidence cell, BTC, the 98c
   band and the 0.998-0.9995 belief bin each hold most of H2's losses and none
   or a costly handful of H1's. Each is 1-2 events written after the fact; a
   5-vs-2-per-100 difference needs ~400 markets (60-160 days). The population
   trap has a time axis too: a cell found on this month's losers is the tape
   population of next month's. Rules are therefore ranked by what they do to
   the SIZE of the worst market (1xSIZE cap: $193 -> $95, gates nothing, costs
   ~$2/day) rather than by in-sample money, which every fitted stack can drive
   to "no losing day on record" (critic s5: the proof it is fitted).

4. **Hedge false alarms scale with the position.** The three H2 false alarms
   were 88-104 contracts ($172); the same photo-finish alarms in H1 cost $8-20.
   Any size cap therefore also shrinks the insurance leak; and the hedge rule
   is priced about fair (-$29 lifetime, +$31 under the 0.40 rule), so changing
   it is a variance decision until the pre-registered hair-over read lands.

**What would falsify 12.1-12.3:** a week in which the main leg (<= 30 s) earns
under 1c a contract with no double-leg loser in it (then the margin itself has
gone, not the composition); or the early leg's top-up filling in most markets
once the ceiling is 97.8c (then supply was not the cap on the win); or a loss
identifier that holds at the base-rate bar in a half it was not built on.
