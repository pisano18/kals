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
