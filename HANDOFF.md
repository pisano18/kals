# HANDOFF — read this first in a new session

---

## 2026-09-06 — pin is STILL strengthening; the at-touch maker row is
## contaminated and its verdict is not yet readable

### pin, third look, out of sample

    tau <= 20s          n     MDE   claimed  REALISED       t   mid-null top
      floor 0.3c      360   1.46c    +2.98c    +1.94c    +4.0        +0.55c
      floor 0.5c      319   1.57c    +3.27c    +2.36c    +4.5        +0.48c
      floor 1.0c      222   2.22c    +5.75c    +2.14c    +2.9        +0.79c
    tau <= 60s: +0.24 / +0.20 / +0.32c, all t < 1. Still nothing.

**t has risen every time more tape arrived: +3.0 in sample, +3.7, now +4.5.**
That is what a real effect does and a fitted one does not. It clears its MDE
(2.36 vs 1.57) and the market-is-right null (top +0.48c), out of sample, with
the confidence refitted only on earlier closes.

**My reporting of it was wrong and is fixed.** The line read "paid 74.9c, won
77.4%, win +3.7c, loss -2.2c" -- and win minus loss must be 100c for ANY
binary, so that pair was impossible. The trades are two opposite populations:
DEAR ones bought near 96c (win +4c, lose -96c) and CHEAP ones bought near 2c
(win +98c, lose -2c). Their average, 74.9c, is a price at which nothing was
ever bought. Each population is separately zero-EV if the market is right, so
the +2.36c is edge over the market either way -- but the two legs are now
printed separately, with their own counts, prices, win rates and P&L.

The stated confidence is still fiction: >=98% claimed, 77% delivered.

### The maker at-touch row cannot be read yet

    filldepth      trades      mkS      t    maker      t
      at-touch  24,630,462   -0.71c  -10.0   +0.52c    +7.0
      0-1c-out   7,014,249   +0.89c  +11.4   +0.10c    +1.2
      1-3c-out   2,983,928   +2.78c  +32.3   -0.13c    -1.6
      3c+-out    1,968,990   +8.62c  +39.8   -0.37c    -1.8

The shape is exactly what a maker would want: the money is AT THE TOUCH
(+0.52c, t=+7.0, on two thirds of all trades) and negative out in the ladder,
which is the opposite of the fear that killed the last version of this idea.
Takers who print at the touch have NEGATIVE information (-0.71c); the informed
ones sweep (+8.62c at 3c+ out). Economically coherent.

**But the at-touch half-spread came back as -0.19c, and a maker who captures
less than nothing is not a maker -- it is a stale reference quote.** The
bucket test was `beyond <= 0.05`, which sweeps in every print that landed
INSIDE the recorded quote, i.e. every case where the book had already moved
and our reference was old. Those fills belong to nobody.

Fixed: `inside-stale` is its own bucket now, and the whole split is repeated
against a reference quote at most 2 seconds old (`filldepth2s`). If at-touch
and at-touch(fresh) disagree, that difference IS the staleness. Until that run
lands, **the maker verdict is unresolved -- not positive.**

---

## 2026-09-05 — pin SURVIVES out of sample, and the maker correction was
## not the one I proposed

### pin: out of sample it got STRONGER, and it is a different bet than I said

    tau <= 20s, out of sample, sigma recalibrated on earlier closes only
      floor 0.3c  k 0.50->1.26  n=307  MDE 1.69c  REALISED +1.82c  t=+3.2
      floor 0.5c  k 1.37->1.35  n=270  MDE 1.82c  REALISED +2.27c  t=+3.7
      floor 1.0c  k 1.36->1.59  n=187  MDE 2.61c  realised +2.06c  t=+2.4 (inside MDE)
    tau <= 60s: nothing, again.

The 0.5c cell beats its MDE (2.27 vs 1.82) and the market-is-right null
(top +0.78c) with a HIGHER t than in sample (+3.7 vs +3.0). The effect is
still confined to tau <= 20s, which remains the settlement arithmetic's own
prediction.

**But it is not the strategy I described.** Backing the entry price out of
(mean P&L, flip rate):

    in sample   paid ~91.5c   won 94.3%   edge +2.8pp
    out of sample paid ~70.3c  won 74.1%   edge +3.7pp

The recalibration shrinks fair, which shrinks every edge, so only the LARGEST
market-model disagreements still clear the floor -- and those are much cheaper
entries. So the out-of-sample bet is not "buy a 92c near-certainty": it is
"buy at 70c something that wins 74% of the time". Same money, completely
different risk, and the only way to see it was to solve for it by hand. `pin`
now prints entry, win rate, mean win and mean loss on every line.

The model's stated confidence remains fiction at every cut: it says >=98% and
delivers 74-94%. The edge is real in the P&L; the CONFIDENCE is not, and no
position size should ever be taken from it.

### maker: the horizon was NOT the correction. The capture was.

The measured curve:

    cell        half-spread    1s      5s     30s    120s    300s   settle
    ALL              0.73c   0.60c   0.61c   0.64c   0.62c   0.47c   0.39c
      maker net              +0.13   +0.12   +0.09   +0.12   +0.27   +0.35
    1c spread        0.57c   0.50c   0.51c   0.53c   0.53c   0.39c   0.27c
      maker net              +0.08   +0.07   +0.05   +0.04   +0.18   +0.30
    >=5c spread      4.02c   2.30c   2.35c   2.70c   2.37c   2.31c   3.03c
      maker net              +1.72   +1.66   +1.32   +1.65   +1.71   +0.99

Impact does peak near 30s and decay, but only from 0.64c to 0.39c. That is
NOT what flips the sign. **The markouts agree with maker.py (0.600 vs
0.612c). The capture does not: maker.py used half the MEDIAN spread, 0.50c;
the measured mean signed (trade price - pre-trade mid) is 0.73c.** The verdict
turned on that one assumption, and the maker net is positive at EVERY horizon
once the capture is measured rather than assumed.

**Do not trade this yet, and the reason is specific.** A fill 3c from the mid
pays the maker 3c -- but only a maker QUOTING 3c out collects it, and they are
filled far less often. The +0.35c may be an average over a ladder nobody can
rest the whole of. `informed.py` now splits every measure by how far the print
landed from the pre-trade touch (at-touch / 0-1c / 1-3c / 3c+). **The at-touch
row is the only line a maker at the best bid or offer can actually collect.**
If the positive number lives in the -out rows, maker.py was right for the
wrong reason and this is not a strategy.

---

## 2026-09-04 (evening) — FIRST RESULTS FROM THE FOUR NEW STAGES

### pin — the strongest signal this project has produced, and it is marginal

    tau <= 20s
      floor 0.3c   n=362   MDE 1.69c   claimed +2.51c   REALISED +1.70c  t=+3.0
      floor 0.5c   n=316   MDE 2.27c   claimed +3.81c   REALISED +2.29c  t=+3.0
      floor 1.0c   n=240   MDE 3.47c   claimed +6.54c   REALISED +2.87c  t=+2.5
      floor 2.0c   n=151   MDE 6.00c   claimed +12.01c  REALISED +4.73c  t=+2.4
    tau <= 60s: +0.23 / +0.04 / -0.49 / -0.52c, all t < 1. NOTHING.

The mid-null tops out at +0.32c and the realised is +1.70c, so it beats the
market-is-right null. **And the effect lives ONLY at tau <= 20s**, which is
what the settlement arithmetic predicts: at tau=20 forty of the sixty prints
are locked, at tau=60 none are. A result that appears exactly where the theory
says it must is worth more than the same t-stat appearing anywhere.

Two things keep it honest. Realised sits AT the MDE (1.70 vs 1.69) — the
smallest effect this sample could certify. And every cell is flagged **BELOW
the fair band**: claimed +2.51c against realised +1.70c, worsening to +12.01c
against +4.73c at the 2c floor. The bias grows with the size of the
disagreement, which is the signature of selecting on OUR error rather than the
market's.

So `pin.py` now walks forward: sigma is recalibrated on closes strictly
earlier than the one being traded, by matching the model's stated confidence
to the rate the stated side actually won. Self-tested against a model fed a
sigma 4x too small — the fit recovers **k = 4.14** and cuts the total damage
from -257c to -82c, while leaving a correctly-specified model at k = 1.07 with
its harvest intact.

### informed — making may not be dead, and that is a correction

`maker.py` measured the resting side's markout at 1s/5s/30s (0.612/0.624/
0.657c), compared it to a 0.5c capture, and this file recorded market-making
as closed. `informed.py` measured the SAME quantity **to settlement** and got
**+0.38c** — against a trade-weighted half-spread of 0.63c, that is
**+0.25c per fill, positive**.

    ALL      mkS +0.38c (t=6.5)   follow -1.12c (t=-20.1)   maker +0.35c (t=6.2)
    spread >=5c                                             maker +0.96c (t=5.4)
    shufS ~0 everywhere (max |t| 2.1) -- the random-sign control is clean

Both numbers cannot be the maker's cost. Either impact peaks near 30s and
decays by settlement — in which case **a maker who holds to expiry never pays
the peak, and maker.py measured an exit nobody is forced to take** — or one of
the two is wrong. `informed.py` now prints the full curve (1s/5s/30s/120s/
300s/settlement) with the maker's net at each, so the next run settles it by
measurement. The half-spread on that table is derived, not assumed:
maker = half - mkS holds exactly by construction.

**Do not act on this yet.** It is a horizon distinction that could still be an
artefact, and it needs the curve before anything is rewritten.

### informed — the two pre-registered cells both fail

* TAIL (follow the informed tail): follow **+0.01c, t=0.1**. Dead.
* HEADLINE (quote where spreads are wide): mkS **rises** with spread —
  0.27c at 1c, 3.11c at >=5c. Wide spreads mean MORE informed takers, not
  fewer. The adversarial panel predicted exactly this and it is confirmed.

### strikes — undefined, not negative

7,907 events scanned, **every one a single strike**. These contracts carry one
strike per window (strike(N+1) == settle(N)), so there is no second leg to
cross against. Cross-strike arbitrage is not mispriced here — the question
does not exist for this product. It WOULD exist for the Coin Race
(KXCRYPTOLEAD15M), whose legs must sum to 100c. The stage now says so rather
than printing a bare zero.

### Coin Race recording is LIVE

`KXCRYPTOLEAD15M` is arriving: 1,071 quotes, 144 trades, 2,422 book updates in
one hour. `KXCRYPTOCOMP15M` is NOT — along with the long-standing ADA, BCH and
TON. The ticker is wrong or the series does not exist under that name.

---

## 2026-09-04 — WHAT IS ACTUALLY OPTIMISTIC, AND WHAT IT WOULD PAY

One cell on disk beats its own market-is-right null. `RESULTS_endgame.md`,
settlement P&L, tau <= 60s:

    trades 705   claimed 1.87c   REALISED +0.86c   t 1.33   MDE 1.93c
    market-right null [-2.26, +0.57]c

**+0.86c sits above the null's top of +0.57c.** Every other strategy cell in
this project sits inside or below its null. This one does not — it is the only
positive signal that survived contact with the right null.

It is NOT proven and must not be reported as such: t = 1.33, and the MDE of
1.93c is larger than the effect, so this sample could never have certified
0.86c whether it was real or not. Underpowered is not the same as refuted, and
this is the one place the distinction matters.

`pin.py` is the tighter filter on exactly this region: only seconds where the
locked prints put fair beyond 0.98 (or below 0.02) and a quote is still on the
wrong side. If the endgame edge is real it should CONCENTRATE there, which
raises the effect against the same noise.

### The money, if it holds

Contracts pay $1, so 1c = $0.01/contract. Measured: 80 closes/day, 13.4
strikes per close, depth 55 at the touch (28/55/124 quartiles).

    floor    one trade/close, 40 lots, 0.86c    $24/day     $8.9k/yr
    central  3 strikes/close,  50 lots, 1.5c    $180/day    $66k/yr
    high     5 strikes/close,  50 lots, 3.0c    $598/day    $218k/yr

**The binding constraint is depth, not edge.** 55 contracts at the touch is
$55 of book. This strategy cannot be scaled by betting bigger; only by
covering more strikes and more closes. Any plan that assumes size is wrong
about this market.

---

## 2026-09-03 (evening) — BOTH structural strategies are now closed

On the full tape: 5,947,458 market-seconds, 7,176 markets, **798 close-time
clusters**. Forty-eight times the previous sample.

### Taking on order flow: real, and ~100x too small

| horizon | slope | t |
|---|---|---|
| k = 1s | +0.0000c | **+47.33** |
| k = 5s | +0.0000c | +37.12 |
| k = 30s | +0.0000c | +18.11 |
| k = 60s | +0.0000c | +11.62 |

Controls are now clean at full power: **placebo** t = −0.41 / +0.13 / +0.77,
all inside their MDE; **backward** t = +82.5. And the money block:

    k = 1s / 5s / 10s / 30s   ZERO trades cleared the cost of crossing

Median spread is **1 cent** — the minimum tick in the 10-90c band. There is no
room to quote inside it, and a forecast worth hundredths of a cent cannot pay
it. **Closed.**

### Making the spread: adverse selection eats it, in every bucket

`maker.py` completed for the first time (it had timed out at 3600s twice) and
delivered the number the whole maker question rests on. 27,760,728 trades,
77 million markouts, 798 clusters.

    horizon   signed markout       t         p    net @0.5c
         1s           0.612c    54.4    0.0000     -0.112c
         5s           0.624c    52.0    0.0000     -0.124c
        30s           0.657c    40.6    0.0000     -0.157c

The random-sign control reads −0.000c (t = −0.2), so this is **direction, not
volatility** — the trap that once made a zero-adverse-selection tape fire at
t = +11.

Per price bucket, capture against need:

| price | fills | markout (need) | capture | net | |
|---|---|---|---|---|---|
| 0-8c | 3,990,931 | 0.436c | 0.050c | −0.386c | loses |
| 8-16c | 1,940,005 | 1.018c | 0.500c | −0.518c | loses |
| 16-30c | 3,101,529 | 1.141c | 0.500c | −0.641c | loses |
| 30-70c | 9,850,731 | 0.856c | 0.500c | −0.356c | loses |
| 70-84c | 2,961,810 | 1.250c | 0.500c | −0.750c | loses |
| 84-92c | 1,768,775 | 1.131c | 0.500c | −0.631c | loses |
| 92-100c | 3,655,710 | 0.529c | 0.050c | −0.479c | loses |

Every bucket, by a wide margin, on millions of fills. **Closed.**

That is eight ideas dead: delta-hedging, "every game starts at 50c",
opening-value, lead-lag stale quotes, endgame, calibration/volatility, taker
order flow, and making the spread.

### The book, measured properly at last

    spread, cents                 1 /  1 /  2      (25th / median / 75th)
    contracts AT the touch       28 / 55 / 124
    contracts within 3 cents     76 / 124 / 216

### Still not clean: the book is replayed out of order

92% of rows had to fall back to the ticker channel, and where the rebuilt book
was valid it agreed with the ticker channel on only **81-85%** of comparisons.
The per-day diagnostic named the cause: 426-712 "gaps" a day with a **median
gap size of 1**, plus 74-198 "restarts" — the signature of a single adjacent
pair swapped.

`_rx_ms` is a millisecond stamp and the merge breaks ties by channel
directory, so messages sharing a millisecond arrive in alphabetical order of
channel rather than the order Kalshi sent them. `Book.apply` deletes a level
whose size reaches zero, so a subtraction applied before its matching addition
destroys that level permanently.

Fixed with a bounded reorder buffer keyed on seq. Measured on the fixture with
the buffer disabled: **27,650 false gaps, 13,825 false restarts, and 34,744 of
34,838 rows falling back to the ticker channel** — the real-data signature
exactly. With it: byte-identical output to the cleanly ordered feed.

This does not revive either dead idea (the placebo is clean and the money
block is empty by two orders of magnitude), but it is what a trustworthy book
requires, and C2 — queue position — is the only maker idea left standing and
needs one.

---

## 2026-09-03 — order flow predicts. It is ~100x too small to pay a spread.

First real answer from `flow.py`, on 124,378 market-seconds over 1,430 markets
and 323 close-time clusters. **This is 3% of the tape** — see the data-loss note
below — so every number here is provisional on power, not on method.

### The measurement

| horizon | slope (c per contract of OFI) | t | MDE | |
|---|---|---|---|---|
| k = 1s | +0.0000 | **+3.96** | 0.0000 | beats MDE |
| k = 2s | +0.0000 | **+3.39** | 0.0000 | beats MDE |
| k = 5s | +0.0001 | **+3.65** | 0.0000 | beats MDE |
| k = 10s | +0.0001 | **+2.52** | 0.0001 | beats MDE |
| k = 30s | +0.0003 | **+3.60** | 0.0002 | beats MDE |
| k = 60s | +0.0005 | +1.88 | 0.0006 | inside MDE |

The controls behave. **Backward** (the move that has already finished) reads
t = +12.99 / +9.76 / +3.45 at k = 1/5/30 — flow follows price mechanically, so
an instrument that could not find that would make the forward zeros
meaningless. **Placebo** (real flow against a moment 300s away in the same
market) reads t = −1.16 / −1.71 / +0.47; the middle one is marginally outside
its MDE with the wrong sign, which is one marginal cell in three looks.

**So order flow does carry information about the next move.** That is a real
fact about the book and it is the first positive result in this project.

### And it is worth nothing to a taker

    k =  1s   trained slope +0.0000c, only 0 trades cleared the cost of crossing
    k =  5s   trained slope +0.0001c, only 0 trades cleared the cost of crossing
    k = 10s   trained slope +0.0001c, only 0 trades cleared the cost of crossing
    k = 30s   trained slope +0.0005c, only 6 trades cleared the cost of crossing

Median spread is **2c**, plus a quadratic fee at both ends. A one-standard-
deviation burst of order flow predicts hundredths of a cent. **The signal is
roughly two orders of magnitude smaller than the cost of acting on it.** Taker
order-flow trading is dead, and no amount of extra tape changes that — more
data measures the same tiny number more precisely.

Seven ideas are now closed: delta-hedging, market-making (on the old depth
number), opening-value, lead-lag stale quotes, endgame, calibration, and taker
order flow.

### The book, from the websocket, on 124,378 market-seconds

    spread, cents                     1 /   2 /   6      (25th / median / 75th)
    contracts AT the touch           22 /  42 /  83
    contracts within 3 cents         75 / 123 / 214

`book.py` independently reads **65 contracts** median at the bid off the
`ticker` channel over 5.9M quote-seconds. Two different channels, two different
code paths, same order of magnitude — and both an order of magnitude away from
PLAN sec.4's mis-parsed 3,767. That correction was already known; this is the
first time it has been confirmed from the reconstructed book.

**This is where the project should go next.** Makers pay no fee, earn the
spread rather than paying it, and the queue in front of them is tens of
contracts rather than thousands. The one thing that kills a maker is adverse
selection — filled precisely when wrong — and a signal far too small to pay 2c
of spread is not too small to decide when to pull a resting quote. `maker.py`
has now timed out at 3600s on two consecutive runs and its verdict has not
printed; a fill model built on the reconstructed book (queue position, size
ahead, drain rate) is the missing instrument.

### The data loss, and its third form

The run kept 3% of the tape. Every day printed one subscription, ~460 forward
seq jumps, ~800 books invalidated, and 55 of 62 million deltas dropped onto
invalid books.

The collector subscribes `orderbook_delta`, `trade` and `ticker` in a **single
subscribe call**, so Kalshi numbers all three under one sid with one counter.
Reading `seq` off the orderbook messages alone reads every ticker and trade in
between as a hole, and a hole invalidates every book under the sid — with one
sid, that is every market at once.

**This is the third form of the same mistake in this one file**: the first
version did sequence bookkeeping after filtering by ticker, the second after
filtering by channel. Sequence bookkeeping must precede *every* filter.

The mine now reads all four channels, and uses `ticker` to re-anchor top of
book after a genuine gap instead of going dark until the next snapshot. It also
reports, per day and on real data, how often the book replayed from 400 million
deltas agrees with the top of book the ticker channel hands over whole.

---

## 2026-09-02 — a new question: does the ORDER FLOW know?

The volatility thread is closed. calfit puts `a` at 1.01–1.17 across seven taus
with six of seven CIs containing 1; reconcile, restricted to the quoted span,
agrees; the walk-forward is inside its MDE at every horizon and negative in six
of eight series. **The price is not wrong in any way this project has been able
to measure**, and that is now six dead ideas plus volatility: delta-hedging,
market-making, opening-value, lead-lag stale quotes, endgame, and calibration.

Every one of those asked the same question — *is the price wrong*. There is one
more question the tape can answer and it has never been asked.

### `research/flow.py` — the largest thing on disk, finally read

`orderbook_delta` is **395,685,479 messages, ~3.6 GB, about twenty times the
rest of the tape put together**, and effectively untouched. `book.py` reaches it
but holds every message in RAM to sort by sequence, measured at ~30 GB against a
16 GB machine, so the depth number the project actually uses comes from
`depth_from_ticker` — a shortcut over the small `ticker` channel.

It never needed the sort. Within one collector file the messages are already in
arrival order, so a k-way merge across files yields a globally time-ordered
stream in memory proportional to the **number of files**, not the number of
messages. Book state is proportional to the markets alive at once, which for
15-minute contracts is a handful. Measured at **~116,000 messages/second**:
about an hour for the whole tape, cached one file per day, so every run after
the first takes seconds.

The question:

    x   order flow imbalance over second t (Cont-Kukanov-Stoikov, level 1)
    y   the mid change from the end of t to the end of t+k

`x` is complete before `y` begins. The split is at a **second boundary, not a
message boundary** — message-level overlap is the single easiest way to
manufacture this exact result.

What it enforces, all of it checked by the self-test rather than asserted in a
comment:

* the grid is **exogenous** — every second in the window is emitted, message or
  not, so the sample is not built out of exactly the moments the answer is
  about. Forward-fill is bounded by a global clock, so a dead collector cannot
  read as a calm market.
* cluster-robust on close time, `G` = closes, and the **MDE printed before the
  estimate**.
* a **time-shifted placebo**: real flow against a moment 300s away in the same
  market. Must read zero.
* a **backward check** that must be large. A forward zero from an estimator
  never shown capable of finding anything is not a result.
* **money, out of sample**: slope fitted on the first half of the tape, traded
  on the second, paying the full spread and the quadratic fee at both ends.

It also re-measures, from the websocket stream, the resting-depth number
PLAN sec.4 used to kill market-making — which came from a REST endpoint RUNBOOK
separately records as returning levels ascending and truncating from the bottom.

**Nothing has been run against real data yet.** Two fixture bugs were found and
fixed getting the self-test to pass, both recorded as BIASES.md pattern 18, and
one real bug fell out of them: sequence bookkeeping sat after the ticker filter,
so skipping tickers we have no settlement for would have read holes in our
sample as holes in Kalshi's stream and invalidated every book we hold.

---

## 2026-09-01 — the volatility question, mostly answered

Three days of instrument-building produced an answer, and it is close to "the
market is right".

### calfit: one parameter for the whole calibration curve

P(win) = Phi(a * Phi^-1(price)), fitted by maximum likelihood over every settled
market. a = 1 is calibrated. It is not an arbitrary curve — a is exactly
sigma_implied/sigma_true, so **a = 1/r**, the same parameter reconcile.py gets
from settlement dispersion by an unrelated route.

| tau | a | 95% CI | t vs 1 |
|---|---|---|---|
| 120s | 1.0122 | [0.938, 1.086] | 0.32 |
| 240s | 1.0233 | [0.950, 1.097] | 0.62 |
| 360s | 1.0736 | [0.996, 1.152] | 1.85 |
| 480s | 1.0832 | [0.988, 1.178] | 1.72 |
| 600s | 1.0018 | [0.898, 1.105] | 0.03 |
| 720s | 1.1710 | [1.034, 1.307] | 2.46 |
| 840s | 1.1543 | [0.937, 1.372] | 1.39 |

**Six of seven CIs contain 1.** The one that does not is a single cell of seven
looks, where a family-wise 5% needs |t| > 2.69. Every point estimate is above 1,
but the taus overlap heavily so that is not seven independent votes.

### reconcile was comparing two different periods

Widening the settlement fetch to 10,798 markets collapsed every ratio — BNB
0.715 → 0.524, XRP 0.810 → 0.481. A market underpricing volatility two to one
over 580 closes is not a finding, it is a mismatch: the numerator (implied RMS)
could only be measured over the ~164 recorded hours while the denominator drew
on 1,198 settlements spanning ~300 hours. **Volatility clusters**, so a
denominator from a different stretch of tape is a different number.

Restricted to the quoted span, the two instruments broadly agree:

| series | reconcile r | calfit 1/a |
|---|---|---|
| BTC | 0.967 | 0.970 |
| NEAR | 0.964 | 0.961 |
| DOGE | 0.856 | 0.990 |
| ETH | 0.814 | 0.937 |
| BNB | 0.806 | 0.888 |

**r ≈ 0.85–0.97.** Implied volatility perhaps 3–15% under settlement dispersion.
Small, possibly real, at the edge of what ~170 hours of tape resolves.

### calib's rotation faded under more data

The finding that survived everything else — outcomes more extreme than prices —
largely evaporated when the settlements tripled: 20c from −3.5c to −1.9c, 90c
from +4.5c to +0.5c, every bucket now under |t| = 1.5. **That is what a
small-sample artefact looks like when the sample grows.**

### patterntrade could not have answered either way

−1.04c at 583 clusters, inside its null — but its MDE is 5.7c against a 3–5c
effect. One trade per market at a 46c per-trade sd is an expensive way to ask.
Not a refutation; a statement that the instrument was the wrong shape.

### oos.py — the only test here that is not in-sample

Everything above describes the whole tape at once. `oos` walks closes in time
order, fits `a` on markets that settled **strictly before** each close, trades
that close off it, and settles. Its self-test proves the absence of look-ahead
rather than asserting it: `a` jumps 0.80 → 1.30 mid-fixture and the fit must
LAG it (0.834 → 0.905 across the jump, reaching 1.301 only 280 closes later).
Nothing that peeks can lag. MDE 2.34c at 460 closes.

### Where this leaves the project

The measurement problem is solved; the question is now simply whether anything
is there. **The binding constraint is the length of the quote tape**, not the
analysis — `oos` prints how many more closes each edge size would need.

If `oos` ties its market-is-right null, the volatility thread is finished and
the next direction is `orderbook_delta`: **395 million messages**, by far the
largest dataset here and essentially unmined — `book` currently runs in under a
minute off the cheap ticker-derived path.

---

## 2026-08-29 — RETRACTIONS. Read this before any number below it.

A seven-lens adversarial audit of the code written on 28 August claimed 43
defects; 16 survived three independent refuters each, 8 of them critical. Two
of those invalidate results published in the section below and reported to the
operator. **The retractions come first because the wrong numbers were stated
with confidence and travelled.**

### RETRACTED: endgame's real-data P&L (−21c to −39c, t = −4.2 to −7.8)

It measured nothing.

    won = 1.0 if b["settle"] else 0.0

`kalshi_fulltape.py` writes `settle` as the **settled index LEVEL** (~79,500)
and the outcome as `result`, guarded so `settle` is never zero. That truthiness
test returned 1.0 for **every market on the tape**: every yes-side trade booked
a win, every no-side trade booked a loss, and the realised column was a pure
function of the yes/no trade mix.

I used that number to argue the project's σ chain was confidently wrong. **That
argument is withdrawn.** The σ-vs-outcome contradiction below stands on calib
alone until endgame is re-run.

No test could see it: endgame's fixture wrote `"settle": settle > strike`, a
bool — the only fixture in the repo that disagreed with the collector's schema.
`replay.py` and `edge.py` both write it as a price with a separate `result`.
Fixed with `outcome_of()`, a `sane_or_die()` YES-rate gate, a fixture on the
collector's schema, and a self-test that fails if the broken reading and the
correct one ever agree again.

### RETRACTED: term.py's term structure (free power law +0.111, t = 8.41)

Indistinguishable from an artefact of term.py's own staleness tolerance.

`STALE_TOL = 0.02` was only ever exercised against a fixture emitting a quote
every 3 seconds, so every row it had ever seen was 0–2s old. On the same
**exact-model** book — true β exactly zero — with quotes 20s apart:

| spacing | β on sqrt(τ) | β on free power law |
|---|---|---|
| 3s | −0.003 (t=−0.95) | +0.001 (t=+0.46) |
| 10s | −0.156 (t=−4.76) | +0.032 (t=+3.44) |
| 20s | −0.487 (t=−7.74) | **+0.119 (t=+7.70)** |

Against the tape's reported **+0.111 (t=8.41)**. Setting the tolerance to zero
returned 0.0000, so the admitted staleness was the entire effect.

Fixed at the source, not with a tighter bound: `implied.collect()` now inverts
every carried-forward quote at the second it was **issued**. That removes the
bias exactly and keeps *more* data than a zero tolerance did. Verified 0.0000
at 3s, 10s and 20s spacing.

**The claim "the market is not making a variance-formula error" is therefore
unproven, not disproven.** It must be re-measured.

### SUSPECT: surface's "best reachable cell, 4–6c at +1.24c"

`availability()` medianed the spread over raw **messages**. The ticker channel
is publish-on-change, so a tight book republishes far more often than a wide
one and the median is dragged toward the tightest book in the bucket — the
occupation-time bias that `implied.collect()` was fixed for the same week,
reappearing in a new file. On a two-market fixture it flipped the sign of a
bucket's net. Now an exogenous one-quote-per-second grid plus a per-market
column. **Re-run before quoting.**

### The other five criticals

- `endgame.redraw_null` resettled from the **model's own** fair value, so its
  mean is the claimed edge by construction — and it was printed as "null" with
  main() reading a result inside it as "nothing here". Inside that band means
  the model is **right**. Now two bands, labelled: a market-right null and a
  model band.
- `surface.kelly()` omitted the taker fee, printing a **positive stake** on
  rows its own NET column declared unprofitable.
- `go.py`'s cfbenchmarks_value EMPTY marker required the word "data" after the
  feed name. Zero of the seven messages stages actually print matched it, so
  five stages could report `ok` on an index feed delivering nothing.
- `go.py` flagged **every successful endgame run** EMPTY, because one sentence
  of prose contained "no quotes". `markers.py` now enforces the rule that
  separates the real case from the accident.
- `run_when_away.ps1`'s HEAD-vs-origin gate passed when **both** sides were
  `$null` — exactly when git is broken and provenance is unknowable.

### What this run taught that outlives the individual bugs

**Every one of these was invisible to the self-tests, and each for the same
structural reason: the fixture and the real world differed in one detail the
fixture's author chose.** A bool where the collector writes a float. A 3-second
quote spacing where the channel is publish-on-change. A message stream where
the sampling is per-second. Pattern 15 in `BIASES.md` was written about Python
versions; it is much wider than that. **A fixture is a claim about reality, and
an untested claim about reality is exactly what this project exists to
distrust.**

The one number that survived the audit untouched is calib's grid column, and
that is not a coincidence: it makes no model assumption at all. It counts.

---

## 2026-08-28 (evening) — a whole run lost to a filename

The 17:26 run produced nothing. Fourteen of sixteen stages died on the same
line:

```
File "research/replay.py", line 47, in <module>
    import gzip
File "C:\Python314\Lib\gzip.py", line 16, in <module>
    from compression._common import _streams
ModuleNotFoundError: No module named 'compression._common'; 'compression' is not a package
```

**Python 3.14 added a stdlib package called `compression`.** The repo had a
`research/compression.py` (added in `6f6ac20`, after the last run that worked),
and every stage puts `research/` first on `sys.path`, so `import gzip` found
ours. Renamed to `research/patterntrade.py`.

**Read this part, not the fix.** Four separate things had to be true, and each
one is a lesson that outlives this bug:

1. **It was invisible on the machine the code is written on.** That container
   runs Python 3.11, where `gzip` imports `_compression` (underscore) and
   `compression` is not in `sys.stdlib_module_names` at all. Every self-test
   passed. The development environment differing from the run environment is
   now a known, named risk in this project.
2. **The self-tests structurally could not see it.** They import their own
   modules and never `gzip`. Only stages that load real data import `gzip`, and
   those are exactly the stages that get skipped when there is no data — so the
   gate is blind to the whole class by construction.
3. **The gate never ran.** `run_when_away.ps1` drives stages one at a time with
   `--only`, and `--only` skips self-tests by design.
4. **It looked like sixteen separate failures.** An environment bug does not
   present as one bug; it presents as everything being broken at once, which is
   the hardest shape to diagnose from a results file.

Guards added:

- **`research/shadow.py`.** Deliberately does *not* rely on a stdlib name list,
  because a name check against the *running* interpreter is exactly the check
  that would have passed here. It (a) puts `research/` first on `sys.path` as
  every stage does, imports every stdlib module the repo names, and checks each
  resolves outside the repo — which catches transitive shadows like
  `gzip → compression` where the shadowed name never appears in our source; and
  (b) carries an explicit list of names that are stdlib in Pythons *newer* than
  the one running, so a 3.11 container flags a file that will only break on
  3.14. Its self-test asserts that exact case. A `ModuleNotFoundError` naming
  the module *itself* is a platform difference (`winreg` on Linux), not a
  shadow — a real shadow reports a *different* name, as `compression._common`
  did.
- **`go.py` PREFLIGHT**, which runs even under `--only` and stops the run before
  any stage. Environment bugs belong in front of the fast path.

Nothing was lost but the evening: the recorder is independent and kept running
throughout.

---

## 2026-08-28 (later) — endgame repaired, and a rule written down before the number

Three things landed after the audit. Nothing here has touched real data yet;
all of it is arithmetic and fixtures.

### 1. `endgame.py` part 2 was broken by its own fixture, in two ways

It had been failing since it was written, and the estimator was never at fault.

- `strike = settle + gauss(0, 3.0)` drew the strike from the **future**
  settlement value, so `settle - strike` was independent of everything knowable
  at decision time and the true probability of every market was 50%. Measured
  directly: rows the model priced at 0.041 won **27.4%** of the time; rows it
  priced at 0.959 won **76%**. A book on `sqrt(tau)` — pulled toward 50c by a
  sigma 9.7x too large — was therefore *closer to the truth* than the exact
  model, and fading it correctly lost 22.6c.
- Each window reset `px = S0` and wrote ticks over `[close-900, close]`, and
  `close(w) - 900 == close(w-1)`, so every window **clobbered the previous
  window's final settlement print** with a value ~180 dollars away. `settle`
  was computed before the clobber; `fair()` read after it.

Repaired (one continuous tape, `strike(N+1) == settle(N)`), it is silent
against a correctly-priced book at every tau cap and finds a `sqrt(tau)` book
at **+7.9c (t=4.9)** inside 60s rising to **+12.1c (t=6.4)** inside 15s — with
**claimed edge matching realised P&L inside a standard error in every cell**.
That agreement is the assertion. Detection alone is cheap.

Two results worth keeping from the repair:

- A book on `sqrt(tau-39.5)` is **invisible**, and not because the estimator is
  weak: that approximation collapses below ~40s, driving its own quotes outside
  the range the exchange can quote. Its error region censors itself.
- **A pooled sigma manufactures edge.** Book quotes each window's own true
  sigma, scan uses one pooled sigma per series — true edge exactly zero,
  claimed **+2.5c**, realised **−4.2c**, stable across seeds. `endgame.main()`
  now prices each market off its own pre-endgame path. *Every other stage in
  this project pools.*

### 2. `term.py` — the first vol measurement immune to our own sigma estimator

Every other vol result here is a **level**: implied over a realised sigma we
estimated, so any bias in our estimator lands in the answer. This measures a
**shape** within a single market against itself. Invert every quote through the
exact `var_factor`: a market using the same formula is **flat in tau**, whatever
it believes. `sqrt(tau)` makes implied sigma explode into the close (9.7x at
tau=10); `sqrt(tau-39.5)` makes it collapse below 40s.

Self-test recovers a planted `sqrt(tau)` book at **beta = 0.998 [0.994, 1.001]**
and `sqrt(tau-39.5)` at 1.039 [0.982, 1.096], reads flat on a flat book
(beta = -0.000), and separates a
genuine rising-vol *view* from an arithmetic *error* by the **pair** of betas
(a sqrt(tau) book reads 0.998/−0.580; a 40% rising-vol view reads 0.119/−0.157).

**It found a real bias in `implied.collect` on the way.** The 30-second
carry-forward inverts a stale quote through a `var_factor` that has since
collapsed: sd/sigma falls from 0.893 at tau=20 to 0.327 at tau=10, so a
30s-old quote at tau=10 returns **7.58x** the sigma the quoter used — a
rising-into-the-close bias with exactly the shape of the signature term.py
looks for. On a fixture whose truth is flat, 2s of allowed staleness alone gives
beta = **+0.062 at t = 6.0**. `collect()` now carries the quote's age; term.py
drops any quote whose sd(tau) has moved >2% since it was posted, and reads
0.000. **The level results in implied.py are biased UP by this, which makes
every ratio it reports conservative against the finding that the ratio is
below 1.**

### 3. `surface.py` — the map from the finding to a trade, written down first

The project had a candidate (implied/true sigma = 0.895) and no answer to
"which contract, at what price, for how much". That needs no data.

If the market's sigma is too low its prices are too **confident**, so the cheap
side is always the one below 50c. A market quoting mid `m` believes
`z_m = Phi^-1(m)`, the true z is `z_m * r`, and true fair is `Phi(z_m * r)`.
**The var_factor cancels, so the edge does not depend on tau at all.** Only the
cost depends on price: the quadratic fee peaks at 50c, and the tick is tapered
(0.1c below 10c, 1c above).

At r = 0.895:

| mid | gross | cost | NET | break-even r |
|---|---|---|---|---|
| 5c | 2.05c | 0.39c | **+1.66c** | 0.978 |
| 7c | 2.33c | 0.51c | **+1.82c** | 0.975 |
| 10c | 2.57c | 1.16c | +1.41c | 0.951 |
| 16c | 2.67c | 1.46c | +1.21c | 0.941 |
| 30c | 1.94c | 1.98c | −0.04c | 0.893 |
| 50c | 0.00c | 2.25c | −2.25c | never |

Positive below ~30c, negative above, best at 7c. There is a **structural cliff
at 10c**: the TICK goes 0.1c → 1c in one step. The cost of crossing goes
0.51c → 1.16c, which is 2.28x rather than 10x — the quadratic fee dominates
below 10c and moves smoothly — while the gross edge barely moves at all. Below 10c the market only has to be wrong
about sigma by **1.8–2.5%** for the trade to pay; at 30c it must be wrong by
10.7%; at 50c no error is ever enough. **Fourth independent line pointing away
from 50c.**

Verified not against itself but against a settled simulation — real 900s tape,
real 60-print settlement, market quoting `r × sigma`, one trade per window held
to expiry. Analytic vs simulated agrees to |t| ≤ 1.2 across four cells while
mean tau moves from 342s to 825s, which is the tau-cancellation tested rather
than asserted. The `r = 0.999` row correctly **loses** 1.5c: a market that is
right must cost you the spread and the fee.

**The map assumes a one-tick book, which is a floor and not a measurement**, and
that assumption does most of the work below 10c. `surface.py --data` re-costs
every cell with the observed median spread per bucket, with quote-seconds and
distinct markets beside it. **Read that table, not the map, wherever it has
data.** If the wings are quoted 1c wide, the taper buys nothing; if they are not
quoted at all, the best cells do not exist.

### What this changes about what to do next

The order of operations is now: `surface` (no data) says where to look,
`term` says whether the market's error is a formula or a view, `endgame` prices
the formula case, and `implied`/`reconcile` say whether r is below 1 at all —
on **fresh** data. All four are in `run_when_away.ps1`.

---

## AUDIT OF 2026-08-28 — every estimator vs the 14-pattern bias catalogue

A 51-agent audit read all twelve estimator modules against the fourteen bias
patterns this project has actually shipped, then adversarially verified every
claim. 39 claimed → 15 survived: 4 critical, 9 material, 2 cosmetic. ALL are
now fixed (see the commit trail of 2026-08-28). The ones that changed
conclusions:

- **implied.py sampled implied vol at QUOTE times** (occupation-time): quote
  intensity rises with vol, so every implied/realised ratio was biased UP —
  the vol-underpricing candidate is STRONGER than published. Now an exogenous
  per-second grid.
- **implied.py's inversion deleted only the negative half** of a symmetric
  error (`sd <= 0 → None`), manufacturing the 45–55c "frown" (1.166 row) out
  of a flat surface. The inversion now returns the SIGNED estimate; medians
  are unbiased; downstream consumers guard against rare nonpositive medians.
- **pathstats weighted clusters 1/K where K counts FUTURE gridpoints** —
  −1.46c of fake reversion from an exact martingale. Pooled mean +
  cluster-robust SE now. Every previously published pathstats table is void.
- **edge.py scored the model at the gridpoint against a trade print up to
  60s stale** — a proper scoring rule pays the fresher forecast by
  construction (fixture: t=13, +7.55c for 20s). Market side now reads the
  BOOK MID at the same second.
- **feeds.py's imbalance predictor was read up to ~1s INSIDE its own
  prediction window** (last-write-wins bucketing) — the h=1 row was largely
  contemporaneous. Predictor is now the prior second's state.
- **proxy.py regressed every asset's markets on BTC-only candidates**
  (attenuation → false negatives) and tested against a zero null when any
  sub-second quote lag makes the honest-maker null NEGATIVE. Now BTC-only
  markets + an explicit delta-confound control row that candidates must beat.
- **cross.py counted each market five times** (one per ttc), used iid SEs on
  clustered closes, and priced markets with FULL-SAMPLE index variance
  (look-ahead). One obs per close, moving-block SE, causal prefix-sum g0.
  Its "clean null" stands a fortiori (its t's shrink).

The catalogue self-audit also matters: calib.py — excluded from the audit as
"written this week" — carried pattern 8 (cluster by close, not market),
caught separately the same day. Exclusions are where bugs live.

STATUS OF THE ONE LIVE CANDIDATE: implied/settle-sigma = 0.895 median over
the full 399-window recording, four series' CIs exclude 1 (BNB 0.725, DOGE
0.754, XRP 0.820, SOL 0.842). The occupation-time fix moves these DOWN
(stronger). Standard before trading: the same measurement, below 1, on fresh
data the finding has never seen. The recorder is collecting that data now.


Everything needed to continue is in this repo. Nothing lives only in a chat.
Read this file, then `STATUS.md`, then `PLAN_V3.md`. `RUN_WHEN_HOME.md` is the
operator's card.

- **Branch**: `claude/file-uploads-70rtjl` (this is also the remote default —
  a plain `git pull` gets it).
- **Head at handoff**: see `git log -1`. Run 2 findings are in the section below.
- **User's machine**: Windows 11, Python 3.14.6, repo `C:\kals-repo`, data
  `C:\kals` (`kalshi_data/`, `feed_data/`, `fulltape/`, `run_all.ps1`).
- **State**: 19 self-tests, all passing. One full real run completed
  2026-08-26 (203 min); its findings and its faults are below.

---

## THE MAKER QUESTION — PRICED, AND IT IS WORSE THAN IT LOOKED

Run 2 reopened market-making by replacing PLAN.md's mis-parsed "3,767
contracts resting" with a measured ~30. Makers genuinely pay no fee: all
sixteen fifteen-minute series are fee_type="quadratic" (the only
quadratic_with_maker_fees series anywhere are KXBTCMAX125/150). The tick is
1c, the liquid series quote 1c wide, ZEC 7c and NEAR 8c.

**A first pass compared the half-spread against per-second diffusion and
concluded the wings were viable (quote beyond 92.1c at 900s). That framing is
wrong and optimistic**, and `research/maker.py` now says so in its own
docstring. You are not run over by the average second; you are run over by the
seconds in which somebody chose to trade with you.

### The fee theorem
A rational taker crosses only when their estimate beats the touch by more than
the fee, so E[F | ask lifted] >= a + fee(p), and

    E[maker P&L per fill] <= a - (a + fee(p)) = -fee(p)

**and the bound is invariant to how wide you quote** — widening raises the
half-spread on both sides and it cancels. Against informed flow a maker loses
the TAKER's fee every fill: -1.75c at 50c, -0.63c at 90c, -0.33c at 95c.
Paying no maker fee is why anyone quotes at all; it is not an edge.

Independent confirmations of the same answer: a queue/diffusion argument (30
contracts ahead, a 1-tick ATM level lives ~541ms at tau=900 while only ~9.4
contracts of one-side flow arrive, so the modal outcome is the level moving
away and the fills that DO occur are informed bursts, E[drift|fill] ~ 1.55c,
net -1.05c); and the transaction-cost split (at 50c the maker captures
h/(h+fee) = 22% of what counterparties pay, Kalshi takes 78%).

### So the strategy reduces to ONE measurable number
Noise flow pays you the half-spread; informed flow costs you the fee.

    E[P&L per fill] = q*h - (1-q)*fee      break-even q = fee/(fee+h)

At 50c that is **78% of all flow must be uninformed**; at 90c, 56%. That is
not assumable — it is exactly the signed markout `maker.py` measures.

### Two fatal bugs in the first maker.py, both of which its self-test passed
1. The pre-trade mid was "last quote at or before t". Book updates share the
   trade's integer second constantly, so it read the POST-trade mid and
   attenuated a planted 1.000c to **0.000c**.
2. The headline compared |post-trade move| against |random-grid move| — a
   volatility test, not a direction test. Trades cluster in volatile seconds,
   so on a tape with provably ZERO directional information it fired at
   **t = +171**.

Both fixed; both now planted in the self-test. **The deeper lesson: the
self-test exercised the SIGNED path while main() reported the ABSOLUTE path.
Testing a different quantity than you report is indistinguishable from not
testing.**

### What a paper trade can and cannot do (measured, not argued)
At 185 close-time clusters the P&L minimum detectable effect is 2.64c at a 95c
price and **8.46c at 55c** — and making happens mid-book, so 8.46c is the
honest number. Confirming a 0.5c edge from settlement P&L needs ~6,550
clusters (68 days) at 95c and ~54,000 (564 days) at 55c. **For a maker, extra
fills buy ZERO additional power on settlement P&L**, because every fill in one
market settles on the same single outcome.

The alternative is not a longer paper trade but a different estimator: signed
post-fill markouts have per-fill sd 1.36-2.47c, cluster SE 0.028-0.094c, and
an MDE of **0.08-0.26c at 185 clusters — 30-100x more powerful** than replayed
P&L, against a target quantity of ~0.5c. That is the measurement to run.

### The 59.9% index coverage is NOT a 40% hole rate
It is ONE contiguous ~18.6-hour recorder outage (the PC crash) inside a
46.36-hour wall-clock span, plus ~2,000s of short transport interruptions.
Dedup is definitively excluded: replay's own parse counter (999,590) exactly
equals the sum of the ten per-index distinct-second counts, and the live rate
measures 1.000 Hz/index. The data that exists is dense and fine.

### implied.py's pooling bug is fixed
Five sites pooled raw sigmas across series spanning 1e6 in price. The "1.192x
variance risk premium" was 0.7839/0.0118, where 0.0118 is literally SOL's
realised sigma alone and BTC+ETH supply 97.6% of the numerator. Now pools
per-series ratios, with a self-test that plants three series priced 1,000,000x
apart carrying a common ratio and checks the price level does not leak.

---

## RUN 2 (2026-08-27 02:39, 154 min) — THE FIRST COMPLETE RUN

All 13 stages produced data. 46.4 hours recorded, 72.6M orderbook deltas
parsed (100% of them, against 0% in run 1). Findings, and what is still wrong:

- **The maker strategy's death sentence was based on a mis-parsed number.**
  PLAN.md sec.4 killed it on "best bid 0.40 with 3,767 contracts resting",
  from a REST call RUNBOOK separately records as mis-parsed. Measured from the
  websocket: **median depth at the touch is 30 contracts**, 32 at 40c, 20 at
  50c. That is 125x smaller and a joinable queue. **NOT YET CONFIRMED** — see
  the sid bug below; it was measured on 24 of 1,090 markets.
- **PLAN_V3's #1 ranked idea is refuted.** "Does the book follow the index?"
  — it does not. The book **leads** by one second: beta 0.530 at lag -1
  (t=29.4, 108 df) against -0.001 at lag +1 (p=0.37). Corroborated by feeds,
  where our own replica also lags the published index by 0-1s. There is no
  stale-quote edge available from watching the index. Most likely the CF index
  is timestamped ~1s behind the information the market already has.
- **Implied vs realised volatility, per series** (the only trustworthy cut):
  BTC 0.88, ETH 0.86, SOL 0.89, BNB 0.94, DOGE 0.94, ZEC 1.03, NEAR 1.02,
  XRP 1.10, HYPE 1.25. The liquid series price volatility BELOW realised —
  the opposite of a variance risk premium. **The report's headline "VARIANCE
  RISK PREMIUM 1.192x" and the 59x-141x "vs realised" columns in the term and
  smile tables are a POOLING ARTEFACT** — implied.py averages sigmas across
  series whose price levels differ by six orders of magnitude (BTC ~5.59
  $/sqrt(s), DOGE ~0.00002). It must pool the per-series RATIOS, not the raw
  sigmas. **Unfixed.**
- **Cross-sectional: a clean null.** All 9 series "in line", max |t| = 2.2
  (BTC absolute 0.62c). 509-533 clusters each.
- **Replay P&L: -13.20, null 95% [-657, +365], 73rd percentile.** Nothing.
- **Median spread is 1.00c** on the liquid series (ZEC 7c, NEAR 8c) —
  consistent with a flat 1-cent tick, so §8 item 1 leans that way.
- **Index coverage is 59.9% and flagged GAPPY** on every one of the ten
  indices: ~100,005 seconds present out of 166,896 in the span. Four in ten
  index prints are missing. This degrades every model-based test and is
  **undiagnosed** — is it the feed, the subscription, or the reader?

### Bugs found in run 2, fixed
- **`book.py` checked sequence continuity per TICKER.** The collector
  subscribes a LIST of market_tickers in one call, so Kalshi's `seq`
  increments per SUBSCRIPTION across every market in it. Consecutive deltas
  for one ticker jump by however many other markets spoke in between, so
  nearly every delta read as a gap: 74,343,133 deltas parsed, **24 of 1,090
  markets** rebuilt. Now keyed on `sid`, with a gap invalidating every book
  under that subscription. Self-test (8 markets interleaved on one sid)
  reproduces it: 8 of 328 states under the old logic, 328 of 328 under the
  new. **The depth figure above must be re-measured after this.**
- **`go.py`'s EMPTY flag matched bare substrings**, so `"1,090 markets"`
  matched `"0 markets"` and five stages that had each loaded ~710,000
  messages were labelled `EMPTY -- no data loaded`. A false EMPTY is worse
  than none: it buries a real result under the one label that says do not read
  this. Now boundary-anchored regexes.

### Operational note from the watchdog log
Recording is healthy (~76 MB/h kalshi, ~89 MB/h feeds). The size column looks
frozen for most of each hour and then jumps at :04 — that is Windows not
updating directory metadata until the hourly file closes, not a stall.
**But free disk swung 71.5 -> 36.5 -> 44.7 GB in five hours** while the data
directories grew ~100 MB/h. Something else on that machine is taking and
releasing tens of gigabytes. The watchdog halts below 5 GB.

---

## 0. THE ONE URGENT THING

**Both recorders are dead** and have been since 2026-08-26 (feed_data stopped
~03:59 UTC, kalshi_data ~05:41 UTC — they died when the user's PC crashed and
never came back). Recording time is the only thing in this project that cannot
be recovered later.

```powershell
powershell -ExecutionPolicy Bypass -File C:\kals\run_all.ps1
```

Restart just after the top of an hour (see §5, gzip trailers).

---

## 1. THE GOAL, VERBATIM

A bot that makes **consistent money on markets resolving every 30 minutes or
less**. The user's words: *"crypto, metal, anything as long as it's a market
that runs on 30 min intervals or less, doesn't have to be Kalshi, as long as a
strategy exists."* And: *"It doesn't have to be a Kalshi error that we try to
take advantage of… The prompt is just to make money."*

It **will run with real money**. The user has explicitly asked for wide,
aggressive idea generation, and has criticised narrow searching before:
*"Just because you can't think of something immediately doesn't mean it's not
there."*

### Hard rules (from RUNBOOK.md, non-negotiable)
1. **NEVER place, amend or cancel an order.** No `POST /portfolio/orders`,
   ever. There is no order code in this repo and none may be added.
2. **Never write, move or delete anything under `kalshi_data/` or
   `feed_data/`.** A collector is writing there and exchange feeds have no
   backfill.
3. Cluster by market/close-time, always. Report `n` as markets or clusters,
   never trades.
4. Never claim a result that was not measured.
5. Every estimator must be calibrated against a known answer before it touches
   real data.
6. Never infer a price's unit from a single observation's magnitude.

---

## 2. THE SETTLEMENT MODEL (established and verified)

Kalshi 15-min crypto binaries. Settlement = mean of the 60 discrete 1-second
CF Benchmarks index prints before close, compared to the same for the 60 prints
before open. Therefore:

- **`strike(N+1) == settle(N)` exactly.** Verified bit-for-bit in 19,471 of
  19,471 within-run consecutive pairs. (See §4 for what this does and does not
  prove.)
- `Var(settle − strike) = 880σ²` — MC-verified in `settlement_math.py`.
- Before the averaging window: `Var = σ²(τ − 39.50)`, τ = seconds to close.
  RUNBOOK's old `σ²(τ+20)` was wrong; at 120s it overstates vol by 32%.
- Inside the window: `Var = σ²·r(r+1)(2r+1)/21600`, r = ticks not yet locked.
  The continuous `σ²r³/10800` fails exactly where we would trade.
- Fair value: `Φ( ((locked_sum + r·spot)/60 − K) / sd )`. **One free
  parameter: σ.**
- `d(fair)/d(log σ) = −z·φ(z)`, maximised at **0.242**. A relative error ε in
  σ moves fair value by up to 0.242ε — this is the floor under every σ-based
  edge. A 33-second σ̂ carries 12.3% error = a **2.98¢ phantom edge**, and the
  engine built on it traded 18–28% of windows against a *provably fair* book
  and lost 3.7¢/contract.
- Fee: quadratic, `ceil(0.07·P·(1−P)·n)` — 0.33¢ at 95¢.
- **TICK SIZE IS UNRESOLVED AND MATTERS.** Code assumes a tapered grid (0.1¢
  below 10¢/above 90¢, 1¢ between). The API's `price_ranges` on market objects
  says **step = 0.01 on notional 1.0000, i.e. a flat 1-cent tick**. If the flat
  tick is right, every target edge under 1¢ is unactionable regardless of
  whether it exists. **Resolve this from the API before sizing anything.**

### The independent-unit result (the most important number in the project)
Twelve crypto series close **simultaneously** at ρ≈0.8, worth **1.22 effective
independent units**. So the independent observation is the **close time**, not
the market — **4 per hour**. 26 hours of recording = **104 clusters**, not
1,248 markets. Every earlier "n = 4,300 markets" overstated the sample ~12×.

Consequence, from `power.py`: the smallest P&L edge detectable from replayed
data is ~2.9¢ at 1 day, 1.5¢ at 7 days, 0.8¢ at 30 days. Tradeable edges here
are 0.5–2¢. **Replayed P&L cannot confirm a strategy at any recording length
you will have.** The deploy decision must rest on a per-second mechanism
(leadlag/feeds/proxy/pathstats get 3,600 obs/hour instead of 4).

---

## 3. THE FIRST REAL RUN (2026-08-26) — WHAT IT ACTUALLY SHOWED

The run completed, all six steps reported "ok", and **94% of recorded data was
never read**.

**Cause**: Kalshi emits its websocket fields with unit suffixes, as STRINGS —
`yes_bid_dollars`, `yes_ask_dollars`, `yes_bid_size_fp`, `yes_ask_size_fp` on
`ticker`; `price_dollars`, `delta_fp` on `orderbook_delta`. Loaders asked for
`yes_bid` / `price` / `delta` and got nothing.

- **68,976,084 of 68,976,084** orderbook deltas unparsed (2.0 GB).
- 7 stages loaded zero quotes (replay, leadlag, cross, openwindow, implied,
  pathstats, proxy); `book` loaded zero deltas. All exited 0.
- Fixed in `8af76b4`, with self-tests that reproduce the exact failure
  (`0 of 300 quotes`, `120 deltas unparsed`) when the fix is reverted.

**Eight independent verifiers recomputed the run from the raw cache.** The
arithmetic transcribed perfectly — ~340 printed cells all reproduce. Every
problem was in *what* was computed.

### THE ONE FINDING THAT SURVIVES

**Volatility clustering in 15-minute settlement returns.** `ac1` of `|r|` =
0.281–0.373 across the six series with adequate history (BTC 0.297, ETH 0.299,
XRP 0.373, DOGE 0.346, BNB 0.281, HYPE 0.315). It survives:
- one-day circular block bootstrap: t = 5.3–10.4
- a fully non-parametric median-indicator sign test: t = 8.3–14.2
- 99% winsorization, and dropping the single largest-|r| day
- full time-of-day de-seasonalization

It clears the corrected bar (|t| = 3.76) independently in all six. Corroborated
out-of-sample by `volmodel`: a causal EWMA σ beats an expanding-window constant
σ per-window in **BTC (63.6% win rate, t = +13.7) and ETH (57.3%, t = +7.3)**
— and *only* those two (XRP +2.6, BNB +1.3, DOGE −0.8, HYPE −1.6).

**It is not yet money.** `volmodel` states the condition itself: this is an edge
only if *the book's σ is slow*. The stage that measures that (`implied.py`)
returned zero observations. **This is the next experiment — see §7.**

### TWO CORRECTLY-MEASURED NULLS (real, not empty)
- **`pathstats`**: the contract price is a martingale on trade-print evidence.
  54 tests, max |t| = 2.5 against its own computed bar of 3.31, 405 close-time
  clusters. Strengthened by the fact its contaminated input pushes *toward*
  false positives.
- **`placebo`**: no exploitable terminal-calibration edge in 3,600 markets and
  8,024,108 prints. The run's largest |t| (4.341) sits at the **55.5th
  percentile** of what an efficient market produces on the same tape.
- **No directional edge.** Up-rate 50.4% over 5,195 markets; every series'
  deviation is smaller than its own MDE.

### THINGS THAT LOOKED REAL AND ARE NOT
- `KXSOL15M ac2 = −0.2227, t = −4.4` — **one pair** of 398 supplies 74% of the
  numerator; delete it and ac2 = −0.058. Also from a stale cache.
- **04h volatility peaks** (XRP 1.36×, DOGE 1.38×, BNB 1.30×) — a single day,
  2026-08-22, supplies 76–85% of the bucket via one ~19σ move shared across all
  three. Rotation test p = 0.59 / 0.82 / 0.94.
- **`volmodel` dLL headline** (+347.7 to +733.2) — the top 20 observations of
  946–2,548 are 44–105% of the total. Above 100% means the other ~1,000 windows
  are net negative. Block-bootstrap t = 1.2–2.4.
- **All six "MISPRICED" D-FINAL calibration cells** — killed three independent
  ways, including placebo's own null.

---

## 4. WHAT IS KNOWN TO BE WRONG WITH THE TOOLING'S OWN CLAIMS

- **GATE C is weaker than advertised.** `strike(N+1)==settle(N)` holds
  bit-exact in 19,471/19,471 *within-run* pairs but only **1 of 73** pairs that
  straddle a data gap. It verifies that Kalshi copied a field, not that
  settlement is computed correctly. The docstring's "stronger settlement gate
  than kalshi_gate1.py" should be restated.
- **`KXDOGE15M`'s GATE C `*FAIL*` is a false alarm** — `floor_strike` is
  quantized to 1e-6 while `expiration_value` carries 1e-7. The identity holds
  in 1,978/1,978 pairs under `floor(settle × 1e6)/1e6`, always one-sided
  (strike ≤ settle).
- ~~**`chain.py` uses iid SEs (`1/√n`) on both autocorrelation tables**~~ —
  **FIXED.** Both tables now divide by a moving-block-bootstrap SE and print
  the old iid `t` beside it, so the inflation is visible rather than implied.
  A new self-test section 6 measures the two rulers against a known answer:
  150 datasets of 1,200 windows with **true ρ = 0** and heavy vol
  clustering, counting how often a nominal 95% interval actually contains the
  truth.

  | ruler | median SE | 95% coverage |
  |---|---|---|
  | iid `1/√n` | 0.0289 | **69%** |
  | moving-block bootstrap | 0.0484 | **91%** |

  The iid SE is **1.67× too small** on this fixture, so every `t` in the
  return table was inflated by that factor — and the fixture's returns have
  *zero* true autocorrelation. This is the more important half: the clustering
  we confirmed does not just break the |r| table's SE, it breaks the RETURN
  table's SE too, because a return series with clustered variance is not iid
  even when its autocorrelation is exactly zero. On the synthetic GARCH cases
  the |r| `t` falls from 12.5 to 8.8 (g=0.30) and 26.8 to 18.5 (g=0.60);
  expect a similar haircut on the real series.

  The block bootstrap covers 91%, not 95% — mildly optimistic in finite
  samples. Both a HAC/Newey–West SE and subsampling were calibrated against
  the same fixture; HAC landed at the same 89–91% coverage and subsampling
  worse, so the bootstrap was kept for needing no bandwidth choice. The `|t|
  > 3` verdict bar (rather than 1.96) absorbs the residual.

  Sign persistence keeps its binomial SE `√(0.25/n)`: measured against the
  same process it is correctly calibrated (ratio 1.05), because signs are
  insensitive to heteroskedasticity. That is now the most robust column in the
  return table, not the least.

  **Still iid:** `power_analysis()` (`--power`) computes its false-positive
  columns with `ac_t`, not the block SE. Its `g = 0` row is homoskedastic so
  that row is sound, but the garch rows understate the bar.
- ~~**`KXBTC15M` was not pulled in the 2026-08-26 run**~~ — **FIXED**, and the
  cause was not a failure. The cache-skip condition was `have >= markets*0.9`,
  size only: BTC's cache was long enough, so the pull was skipped and BTC
  never appeared in the run log. The anchor of the detectability table came
  from a ~10-hour-old cache and nothing in the output said so. The condition is
  now size **and** age (`STALE_HOURS = 6`), and a **DATA PROVENANCE** table
  prints before GATE C with each series' market count, `cache`/`pulled`, the
  age of its newest settlement, pages fetched, and retries spent.

  The 429 truncations were a separate fault in `fetch_settled`: it `break`ed
  out of the pagination loop on *any* non-200 and on *any* exception, and
  returned the short list with no way for a caller to tell "this is the whole
  history" from "we gave up here". So a rate limit was reported as a fact
  about the market. It now retries with exponential backoff (0.5/1/2/4/8s),
  honours a `Retry-After` header verbatim, does **not** retry a 4xx that isn't
  429, and fills a `stats` dict whose `truncated` flag distinguishes a short
  history from a short pull. Self-test section 7 drives six scripted cases
  (429-then-ok, `Retry-After`, 429-forever, 404, timeout-then-ok, clean
  exhaustion) through an injected session and asserts the flag and the backoff
  growth on each.
- ~~**`doctor.channel_stats` undercounts** wherever `mid-write > 0`~~ —
  **FIXED.** It used plain `gzip.open`, which dies inside a torn member and
  surrenders everything written after it; the proof was in the run itself
  (86,338 seconds recovered by `feeds.py` against 83,463 messages counted on
  the same channel). It now reads through `gzsalvage`, and a self-test builds
  the exact shape a crash leaves — a member torn mid-write followed by a
  complete member appended on restart — and asserts the census beats
  `gzip.open` on it: **24 lines vs 84**. The `mid-write` column now means
  "salvaged", not "discarded", and the census says so in words.

---

## 5. INFRASTRUCTURE FACTS THAT COST DATA

- **The collector cannot write a gzip trailer on Windows.**
  `loop.add_signal_handler` raises `NotImplementedError` there and was silently
  swallowed, so `c.w.close()` never ran. A restart *inside the same UTC hour*
  then appended a second gzip member behind an untrailered first, and the
  standard reader threw the **whole file** away — reproduced faithfully:
  **0 of 10 records recovered**. `research/gzsalvage.py` reads those files
  member-by-member and recovers them (0→40, 0→60 in its self-test); every
  loader now goes through it. The collector fix (signal fallback + try/finally)
  stops new files being written that way. **Restart near :00.**
- **Memory**: `replay.load_quotes` and `book.rebuild` used to hold whole
  channels as Python dicts — measured 1,330 bytes of peak RSS per message.
  Both stream now: **220 B/msg, 6×**. `orderbook_delta` at 1.9 GB still
  projects ~15 GB peak; `everything.py` preflight prints the projection.
  **A PC crash an hour into a run was this.**
- ~~**Bitstamp is 92.6% waste**~~ — **FIXED, effective on the collector's next
  restart.** `crypto_feeds.py` subscribes to `order_book_<pair>`, Bitstamp's
  100-bid/100-ask FULL SNAPSHOT channel, and the repo only ever reads
  `bids[0]`/`asks[0]` (`feeds.load_tob`, `proxy.py`'s constituent series).
  3.1 GB of 3.2 GB `feed_data`.

  Not switched to `diff_order_book_` — that channel is *larger*, being full
  depth deltas, and it would require carrying book state to recover the touch
  we already get for free. Instead the record is trimmed to
  `BITSTAMP_KEEP_LEVELS = 5` a side at write time, with `--book-levels 0`
  restoring the old behaviour byte-for-byte.

  Measured, on 200 records of the real shape at the gzip level actually used:
  **712 → 29 bytes per record, a 95.9% cut.** Against Bitstamp's 92.6% share
  that is ~89% off `feed_data`'s growth rate. The saving is measured on a
  synthetic record of the same shape, not on the real file — real books have
  less regular prices and sizes, so they compress worse and the true saving
  should be at least this.

  Trimming is stamped into the record as `_depth: {bids, asks, kept}`, giving
  what the venue actually sent. A silently truncated archive is the kind of
  thing that produces a confident wrong answer two months from now: a future
  reader must be able to tell a five-level book from a market that only had
  five levels.

  The self-test's decisive check is end to end, not structural — it writes a
  full-depth file and a trimmed one, runs the project's own `load_tob` over
  both, and asserts the results are identical (and that they are not both
  empty, which would compare nothing and pass). It also proves `--book-levels
  0` reproduces the original bytes exactly, and that a book already shallower
  than the limit is left completely untouched, stamp included.

  **Levels 2-100 already on disk keep their full depth; nothing recorded so
  far is altered. What gets trimmed from here cannot be recovered.**
- **The watchdog runs the collectors from `C:\kals`, not the repo.**
  `run_all.ps1` does `Set-Location C:\kals` then `python crypto_feeds.py`, so
  it launches the copies sitting next to the data. **A `git pull` updates the
  repo and changes nothing about what is recording** — every collector fix
  this project has made could have been sitting unused, and nothing in any run
  said so. `everything.py` step `0c` now hashes both collectors against the
  repo and reports drift; `--sync-collectors` copies them, backing each up to
  `.bak` and gating on its own `--selftest` where it has one and a compile
  check where it does not (no self-test must not mean "never sync", which
  would pin the file forever). The copy does not affect the RUNNING processes
  — the watchdog has to restart.
- Channels named `ok` and `subscribed` are being written as data channels (the
  collector routes purely on the `type` field). Harmless, tiny.

---

## 6. MARKET FACTS ESTABLISHED FROM THE API

- **There is no fee discount for equities.** `fee_multiplier` is an integer
  **0/1 waiver flag**, not a rate — only 3 series of 1,289 carry 0. All 68
  S&P/Nasdaq series and all 14 crypto 15M series carry `fee_multiplier=1`,
  `fee_type="quadratic"`. PLAN.md's 0.035-vs-0.07 premise is **refuted**.
  `fee_type` also takes `"quadratic_with_maker_fees"` on some series.
  **Open**: read Kalshi's published schedule keyed on `exchange_index`
  (0 = financials, 2 = crypto), present on both series and market objects.
- **The true ≤15-minute universe is 16 series** by the authoritative
  `frequency` field (`"fifteen_min"`): 14 crypto + **`KXINX15M` (S&P 500) and
  `KXNDQ15M` (Nasdaq 100)**. Nothing exists between `fifteen_min` and
  `hourly`; there are 44 hourly series. A ticker-substring scan is unreliable
  (it false-positives `KXUST30M`, a *30-year* Treasury, monthly).
- **`KXCRYPTOLEAD15M` ("Coin Race")** — which of BTC/ETH/SOL/XRP/HYPE has the
  highest return over a 15-min window. One market per coin per event,
  `expiration_value` holds the winning ticker. **This is computable from index
  feeds already recorded**: P(coin i has max 15-min return). Genuinely
  different shape from a binary, and unexplored.
- **`KXCRYPTOCOMP15M`** returned 0 settled markets; the query is correct, the
  series simply has no settled history yet.

---

## 7. THE NEXT EXPERIMENT (both adjudicators independently agreed)

**Get `implied.py` to produce output, and compare the book's implied σ against
the EWMA σ forecast, window by window.**

Why: after every correction, exactly one finding survives (volatility
clustering), and `volmodel` states its own condition — *"this only survives as
an edge if the book's sigma really is slow. That is the thing to measure, not
to assume."* The stage that measures it returned zero observations because of
the field rename, which is now fixed. It needs no new recording; 26 hours are
already on disk.

Order of operations:
1. Restart the recorder (§0).
2. `git pull` in `C:\kals-repo`.
3. `python research\everything.py` — one command, no arguments, 30–60 min.
   It now reads the 2 GB it ignored, and flags any stage that loads no data as
   `EMPTY` rather than `ok`.
4. Read `power.py`'s detectability table **before** `RESULTS.md`.

---

## 8. STILL OPEN / NOT YET DONE

Ranked by information unlocked per unit of work:

1. **Tick size** (tapered vs flat 1¢) — the probe is now built; it needs a run
   from a machine that can reach the API (this session's proxy returns 403 on
   `api.elections.kalshi.com`, a policy denial, not a transport fault). Step 2
   fetches `/series/KXBTC15M` and a live market, then prints **every** field in
   either response whose name could describe a tick, verbatim, rather than
   reading a schema I have not seen — naming the field wrong and getting zero
   back would answer the question with silence. `ticker` is excluded from the
   match: it contains `tick`, and without that exclusion every response
   reports a hit and the honest "the API carries no tick field" verdict can
   never print. Exercised against five synthetic responses (tapered
   `price_ranges`, flat `tick_size`, a deeply nested `minimum_price_increment`,
   one with nothing, and one hiding a tick field *under* a key containing
   "ticker").
2. ~~Replace `chain.py`'s iid SEs with block-bootstrap~~ — done, and the
   self-test now measures the coverage of both rulers rather than asserting
   the new one is better. Re-read the run-2 return-autocorrelation verdicts
   with the block `t`; the iid ones were ~1.7× too large.
3. ~~Make `doctor.channel_stats` use `gzsalvage`~~ — done; the census is no
   longer a lower bound.
4. ~~Fix `chain.py`'s HTTP 429 handling and make it actually pull
   `KXBTC15M`~~ — done; see the provenance table. Series-level staleness is
   now printed once, up front, rather than marked in every table — if that
   turns out not to be enough, the per-table marker is the next step.
5. Restate GATE C's claim (§4).
6. ~~Switch Bitstamp to the delta channel (§5)~~ — done differently and
   better: the record is trimmed to 5 levels at write time (95.9%
   measured), because the delta channel is bigger than the snapshot one.
   Takes effect when the collector next restarts.
7. Reopen the fee question via `exchange_index` (§6).
8. Model `KXCRYPTOLEAD15M` (§6) — unexplored, and computable from data in hand.
9. The 87-idea adversarial sweep produced 16 survivors and 6 rated worthwhile;
   **the synthesis agent never returned and that list was lost.** Worth
   regenerating if broad idea coverage is wanted again.

---

## 9. METHOD — WHY THIS PROJECT WORKS THE WAY IT DOES

Every large edge this project has produced has been a measurement bug. Roughly
thirty have been caught, every one by a self-test planting a known answer:
occupation-time selection bias, σ-noise selection, tick-quantization giving the
model a free win (t=10.6), a reflecting-barrier generator, per-observation
cents/dollars inference (a 75¢/contract phantom), pricing eleven series off
bitcoin (+6.13¢/contract at t=4.9 against two fair books), differencing across
data gaps, an `except Exception` swallowing a `NameError` as "0 rows".

So: **a statistic without a calibrated null is not evidence.** Anything
eye-catching is a bug until it survives its own null. Prefer estimators whose
correct answer is known in advance. And the corrected significance bar for one
`go.py` run (294 statistics) is **|t| = 3.76 on a normal** — but several
statistics here are *t* on ~19 degrees of freedom, where the same bar is
**4.66**. Re-measuring on fresh data beats any correction.

### The generative methods that produced the surviving ideas
1. Differentiate the pricing function; sort candidates by *which parameter they
   live in* (μ-based edges are robust, σ-based ones are capped by our own σ̂
   error). This one move re-ranked everything.
2. Hunt for what is *arithmetically determined* rather than predicted
   (`strike(N+1)=settle(N)`, the locked partial average).
3. Attack the *premises* of existing claims, not the conclusions. Killing "every
   window opens at 50¢" produced the openwindow idea.
4. Ask what nobody has ever looked at (second zero; 3 GB/day of feeds no code
   had read).
5. Invert: not "where's the edge" but "what would the market have to be doing,
   and who would be doing it?" → `proxy.py`.
6. Price the exit before the entry — this killed perp delta-hedging in one
   calculation (10.9¢ at 900s to 98¢ at 30s, against 0.5–2¢ edges).

---

## 10. FILE MAP

**Runner**: `research/everything.py` — one command, does everything, writes
`REPORT.md` + a zip. `research/go.py` — self-test gate + 13 analysis stages.

**Model & power**: `settlement_math.py` (exact model, MC-verified),
`power.py` (minimum detectable effect + multiple-testing), `tdist.py`
(Student-t), `viability.py` (edge → Sharpe/drawdown/time-to-validate),
`settlewin.py` (shared conditional-mean helper).

**Data plumbing**: `doctor.py` (schema prober — writes `schema.json`),
`gzsalvage.py` (recovers restart-damaged gzip), `replay.py` (loaders + replay),
`book.py` (order-book rebuild).

**Analysis stages**: `chain.py`, `volmodel.py`, `placebo.py`, `cross.py`,
`openwindow.py`, `implied.py`, `feeds.py`, `pathstats.py`, `proxy.py`,
`leadlag.py`, `edge.py`, `engine.py` (decision logic, **no order code**).

**Docs**: `STATUS.md`, `PLAN_V3.md` (ranked edge list), `RUNBOOK.md` (hard
rules + API traps), `RUN_WHEN_HOME.md` (operator card), `research/RESULTS_R1..R6.md`
(earlier findings, each with its method note).

**Recorders** (root): `kalshi_collector.py`, `crypto_feeds.py`, `run_all.ps1`.
