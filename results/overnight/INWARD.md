# INWARD — making what we already have work better, prove faster, or die cheaper

Job 5, 2026-09-06. No new territory generated. Everything below is a change
to, or a test of, `pin` and the LIP rebate.

**Collectors: `kalshi_collector.py` (PID 3381772) and `crypto_feeds.py`
(PID 3385232) were alive at the start of this job and alive at the end, same
PIDs. Free RAM 4.1 GB throughout, free disk 51.7 GB. No `load_quotes` call was
made; everything ran off `rows_tau60.pkl` and `depth_map.pkl`.**

Scripts written: `C:\Users\Joe\AppData\Local\Temp\kals-work\inward\`
(`exitlib.py`, `exitmain.py`, `rule.py`, `robust.py`, `capital.py`,
`lagcap.py`, `lagreal.py`, `mde.py`, `api.py`, `settlelag.py`, `posture.py`,
`qualify.py`, `dutycycle.py`, `probe.py`).

---

## THE FOUR THINGS THAT CHANGED TONIGHT

1. **`pin` has a leg that reliably loses money and it is half the trades.**
   Removing it — one binary structural choice, no fitted threshold — takes the
   frozen rule from **$100.40/day to $119.89/day** and shortens the forward
   test from **5.6 days to 3.7 days**. Same entries, same size clause.
2. **Early exit is dead, and cheaply.** Every horizon loses money against
   hold-to-settlement, and — the surprise — it does not free capital either.
   Peak concurrent capital is $267–268 under *every* exit policy including
   hold, because the peak is set by three entries four seconds apart.
3. **The fee formula is now verified against real charged money** for the first
   time in this project. Continuous `0.07·n·p·(1−p)` matched four real Kalshi
   fills to under 0.02c. The "round up to the next cent" variant is **wrong**
   and would have overstated costs.
4. **The rebate's exclusion rule points at a bigger number than the one on the
   board**, in a regime nobody has been quoting into. At the end of a 15-minute
   Coin Race window the yes side collapses and the market stops qualifying —
   four of five markets were excluded at the instant I sampled — and the
   missing depth costs one to five cents a contract. That needs the operator.

---

## 1. pin's RULE — what single change most improves $/capital/day?

### The measurement base

The frozen PREREG rule replayed from cache: every market, `tau<=60`, floor
0.5c, walk-forward `k`, size `min(100, 0.25 × depth)`.

    2,641 trades from _walk_markets   ->  2,307 after the size clause
    (2 had no quote at the entry second; 332 had depth < 4 contracts, so
     0.25 x depth rounds to zero and the trade cannot be taken at all)
    696 closes over 9.58 days = 72.6 fired closes/day
    mean fill 34.4 contracts, mean cost basis $0.494/contract

### THE ANSWER: pin is two opposite strategies wearing one rule, and one loses

`pin` fires when the model calls the outcome decided (`fair >= 0.98` or
`<= 0.02`). But the trade that results is **not always a bet on that call**:

* sometimes it **buys the near-certain side at a discount** — the ask is still
  selling a near-won contract at 96c. Cost basis ~$0.95–0.99. **FAVOURITE.**
* sometimes it **buys the near-impossible side**, because the model thinks the
  market's tail is priced too cheap — buying YES at 0.5c when the model says
  1.85c, or selling YES at 99.5c when the model says 98.8c. Cost basis
  ~$0.005. **LONGSHOT.**

These are opposite bets on opposite errors. The favourite leg needs only the
settlement *mean* to be nearly locked, which is arithmetic. The longshot leg
needs our *tail probability* to beat the market's, which is the one thing this
project has repeatedly failed at. The rule currently takes both.

    cell                          trades  c/contract   $/day  PEAK $  %/day  maxDD    worst      t
    FROZEN: both directions         2307       1.212  100.40     268   37.5  50.22   -50.22   5.11
    buys the FAVOURITE only         1177       3.026  119.89     267   44.9  50.22   -50.22   6.31
    buys the LONGSHOT only          1130      -0.451  -19.49       2 -835.3 205.60    -2.49  -4.75

    95% percentile bootstrap over closes, 4,000 reps:
      both directions      $100.40/day   [ +64.95, +139.59]   excludes zero
      favourite only       $119.89/day   [ +85.45, +160.35]   excludes zero
      longshot only        -$19.49/day   [ -25.28,   -9.99]   EXCLUDES ZERO ON THE LOSS SIDE

The condition is `side == ("yes" if fair >= 0.5 else "no")`. It is one bit. It
agrees with "cost basis above 50c" on 2,624 of 2,639 trades; the 15
disagreements are books so dislocated the edge exceeds 48c, and they are dealt
with below.

**`c/contract` is also `$/contract/day` here**, because the whole book turns
over inside one minute and is flat again before the next close: 8,283
contracts/day at 1.212c each is $100.40/day.

### What would make this an artefact, and what the check said

**(a) A handful of garbage prints carry it.** The top 5 winners are 24.7% of
the leg, and there are 15 trades with an edge over 48c. Checked:

    favourite leg WITHOUT those 15 trades:  1,164 trades, $101.80/day, t=9.96,
                                            peak $267, maxDD $27.90
    favourite leg, P&L winsorised at the 1st/99th percentile:  $105.88/day

So the 15 extreme prints are worth $18/day **and all of the extra drawdown** —
without them maxDD falls from $50.22 to $27.90. The finding survives both
haircuts and still beats the frozen rule's $100.40. **If those 15 are real
fills the leg earns $119.89; if they are unfillable garbage it earns $101.80.
Either way it beats taking both directions.**

**(b) It is one coin, or one day.** Checked both:

    series with n>=20 trades that are POSITIVE:  9 of 9
      KXBTC15M $40.38/day   KXHYPE15M $24.74   KXXRP15M $13.72   KXZEC15M $13.27
      KXETH15M $9.12   KXBNB15M $8.13   KXDOGE15M $4.77   KXNEAR15M $4.70   KXSOL15M $1.07

    by DAY:      favourite positive 11/11        longshot positive 1/11

**(c) It is the existing spread filter in disguise.** It is not. All four
cells, so this is a whole comparison and not half of one:

    direction   spread        trades   $/day   c/contract
    favourite   >= median        894   99.42        4.198
    favourite   <  median        455   20.47        1.284
    longshot    >= median        537   -6.46       -0.476
    longshot    <  median        753  -13.03       -0.439

The favourite leg is positive in **both** spread cells; the longshot leg is
negative in **both**. Separate cuts, and direction is the stronger one.

**(d) The longshot leg is a lottery ticket whose payoff has not arrived yet.**
This is the one that deserves care, because a strategy that wins rarely and
hugely looks exactly like this while it is working. The longshot leg wins **3
times in 1,290 trades**. Wins total +$45.54, losses −$232.29. To break even it
needs 15.3 wins — a 1.19% hit rate — against 0.23% observed. The Poisson upper
95% bound on 3 events in 1,290 trials is 0.68%, which still loses. And the
per-close bootstrap, which resamples the closes containing those wins, has an
upper bound of −$9.99/day. **It does not need more time to become profitable;
it needs a different tail model.**

### What the direction filter costs

Honest cost: the longshot trades are the ones nobody competes for, so they are
the easy races. Recomputed from `survival_join.pkl` (335 traced levels):

    cell               median survival   race won @82ms   money kept @82ms
    all                     1.248 s           90.1%            91.1%
    buys FAVOURITE          1.071 s           88.3%            91.5%
    buys LONGSHOT        never depleted        97.1%            98.5%

The filter makes the average race slightly harder (90.1% -> 88.3% won) and the
money kept slightly *better* (91.1% -> 91.5%), because the races we lose are
still the cheap ones (mean edge of races won 4.28c vs 2.08c for races lost).

### The cap is the other lever, and it is larger than the edge

`0.25 × depth` is the safety property — it is what guarantees we never eat a
whole resting level. **The `100` is not a safety property, it is a money cap**,
and peak concurrent capital says the account is barely being used:

    variant           cap  trades  avg fill   $/day  PEAK $  %/day on peak  %/day on $1,000  maxDD
    frozen             25    2307      16.0   39.02     130          30.1            3.90    37.05
    frozen             50    2307      24.6   69.99     201          34.9            7.00    46.20
    frozen            100    2307      34.4  100.40     268          37.5           10.04    50.22
    frozen            200    2307      47.2  149.53     443          33.8           14.95    50.22
    frozen            400    2307      62.8  201.28     809          24.9           20.13    50.22
    frozen           none    2307     162.0  657.27    4458          14.7           65.73   356.47

    favourite only     25    1177      16.2   46.92     130          36.1            4.69    37.05
    favourite only     50    1177      24.5   82.42     201          41.1            8.24    46.20
    favourite only    100    1177      32.3  119.89     267          44.9           11.99    50.22
    favourite only    200    1177      41.1  178.20     443          40.3           17.82    50.22
    favourite only    400    1177      50.1  241.61     809          29.9           24.16    50.22
    favourite only   none    1177      75.5  755.31    4458          16.9           75.53    50.22

**The frozen rule uses $268 of a $1,000 account.** Raising the cap to 200 is
the single largest $/day change available and it keeps the safety property
intact — 0.25 × depth still never eats more than a quarter of a level.

**Do not read cap 400 or `none` as free money.** Three reasons; I only measured
the first:
1. Drawdown: at `none` the frozen rule's maxDD goes to $356 and blows the
   operator's $250 clause. At 200 and 400 it does not move at all ($50.22),
   because the losing closes happen in thin books that the cap never bound.
2. **The race was measured for 30 contracts** (median 0.70 s to fill 30). A
   100- or 200-contract order is a different race and nobody has measured it.
   This is the reason not to jump to 400.
3. The cap is a *number*, so changing it is a parameter change and it must be
   set before the forward window opens, not after.

### Ranking of the candidates, by $/day at unchanged risk

    change                                 delta $/day   delta %/day on peak   new parameter?
    1. buy the FAVOURITE only                   +19.5           +7.4 pp        NO (binary, structural)
    2. cap 100 -> 200                           +49.1           -3.7 pp        yes (a number)
    1 and 2 together                            +77.8           +2.8 pp        one number
    3. read orderbook_delta not ticker      (already frozen)                   NO
    4. spread >= median filter                   -7.4           +9.9 pp        yes (a number)

The spread filter *loses* $7.44/day and buys 9.9 points of return-on-peak. With
peak capital at $268 of $1,000, return-on-peak is not the binding number —
**take the $/day**. That reverses the earlier reading of the spread filter.

### A CORRECTION TO PREREG §3b

PREREG's feed table reads:

    ticker (~320 ms)           77% races won    94% $/day kept vs ideal
    orderbook_delta (~82 ms)   88% races won    91% $/day kept vs ideal

That is internally contradictory — winning *more* races cannot keep *less*
money — and the 94% is wrong. Recomputed from the same `survival_join.pkl`:

    361 ms (ticker)            76.1% races won    90.7% money kept
     82 ms (orderbook_delta)   90.1% races won    91.1% money kept

The races-won column is right. The money-kept column should read 90.7% / 91.1%.
The conclusion (read `orderbook_delta`) is unchanged and slightly strengthened.

---

## 2. CHEAPER KILLS — what would kill pin faster than 500 closes?

### KILLED TONIGHT, FOR FREE: the commodity 15M families are not an out-of-sample family

The obvious cheap test is "run the same rule on a different underlying". The
five commodity 15-minute families went into the collector this morning, so
their tape starts tonight. **They will not test pin.** From
`GET /markets?series_ticker=...&status=settled`, `rules_primary` verbatim:

    KXBTC15M   "If the simple average of the SIXTY SECONDS of CF Benchmarks'
                BRTI before 3:00 PM EDT ... is at least the simple average of
                the sixty seconds ... before 2:45 PM EDT"

    KXGOLD15M  "If the CLOSE PRICE of the 1-MINUTE CANDLESTICK for Gold on
                Sep 5, 2026 at 12:00 AM EDT is at least the close price of the
                1-minute Pyth GOLD candlestick at 11:45 PM EDT"

**pin's entire mechanism is that 60 of the 60 settlement prints are already
locked on our disk at `tau=60`.** Gold, silver, WTI, natgas and copper settle
on a *single* candlestick close. There is nothing to lock, no variance
collapse, no edge of this shape. Running pin there is not an out-of-sample test
of pin, it is a different strategy with no prior. **That saves a week of tape
and a week of analysis, tonight, for the cost of two API calls.** (Feeds differ
too: crypto is CF Benchmarks, all five commodities are Pyth.)

There is no untouched slice of *crypto* tape either — the scan already spans
2026-08-25 to 2026-09-06, and 150 closes of it are consumed by the walk-forward
warm-up. There is no free out-of-sample hiding in what we hold.

### THE CHEAPEST REAL KILL: run the race live, read-only, for one day

The forward test measures **whether the edge exists**. It does not measure the
thing most likely to kill this, which is **whether we can get the fill** — and
that has only ever been measured from recordings, never through our own
production stack.

    THE TEST. Subscribe to orderbook_delta. Run the frozen rule in real time.
    When it fires, stamp the decision time, then keep watching that exact
    (ticker, side, price) level and record how long it survives. PLACE NO
    ORDER. Compare survival against our own measured end-to-end reaction time.

    COST. One process, one day, zero dollars, no operator sign-off (read only).
    ~74 fired closes/day, ~270 signals/day at the every-market rule.

    KILL RULE, stated before the run. The recordings say 88-90% of levels
    survive 82 ms and 91% of the money is kept.
      * below 60% of levels surviving  -> $/day falls under the PREREG MDE and
                                          the 500-close test cannot pass. STOP.
      * below 30%                      -> pin is dead regardless of edge.
      * above 80%                      -> the recorded measurement is confirmed
                                          through the live stack, and the
                                          forward test is worth its 7 days.

Strictly cheaper than the forward test, runs in parallel with it, tests a
*different* failure mode. **It should run before the forward window opens.**

### THE SECOND CHEAPEST: the direction filter shortens the forward test itself

Same MDE arithmetic as PREREG §5b, recomputed per rule:

                                        frozen rule        favourite only
    fired closes/day                          72.6                  56.2
    mean $/close                            1.3824                2.1316
    sd $/close                              7.1438                7.8368
    t over the backtest                       5.11                  6.31
    closes to detect HALF the edge             410                   208
    days to detect HALF the edge               5.6                   3.7
    closes to detect a QUARTER                1641                   831
    days to detect a QUARTER                  22.6                  14.8

**The same change that adds $19.5/day makes the forward test 1.53x faster.**
500 closes of the favourite-only rule detects half its edge at a 1.55x margin
instead of 1.10x — the difference between "just barely" and "comfortably".

### A KILL THAT IS ALREADY IN THE DATA AND NOBODY HAS READ AS ONE

The longshot leg is an internal falsification test of pin's own model that has
already run and already failed: `t = -4.75`, bootstrap upper bound −$9.99/day,
10 of 11 days negative. It says **the model's tail probabilities are worse than
the market's**. It does *not* kill the favourite leg — that depends on the
settlement mean being locked, not on the tail shape — but it is the first
evidence generated inside this project that part of pin's engine is wrong, and
it should be recorded as such rather than absorbed into a blended average that
hides it.

---

## 3. EARLY EXIT — modelled, and it is dead

### The machinery, self-tested first

`inward/exitlib.py`. Ten self-test groups, run on import, raising rather than
printing a wrong number:

* fee arithmetic by hand (`fee_c(0.96) = 0.2688`, symmetric, `fee_c(0.5)=1.75`)
* **stale book**: a round trip into an unmoved book must lose exactly the
  spread plus both fees, = −0.7505c, and must be negative
* **caught-up book**: bid 0.958 -> 0.985 gives exactly +2.128c
* the NO side must mirror the YES side exactly
* settlement pays ONE fee, an exit pays TWO, and the difference is exactly the
  second fee (`fee_c(1.0) = 0`)
* cost basis; peak-capital interval accounting (overlap adds, disjoint does not)
* book forward-fill and quote age
* **2 of 2 deliberately wrong exit estimators killed** — one that forgets the
  exit fee, one that sells at the ask instead of the bid

The tapered tick needs no assumption here: exit prices are read from the actual
observed book, which is already on whatever grid the series uses. My first hand
constant was wrong (−0.75057 vs the true −0.750452) and the self-test caught
it before any real data was touched.

### The result

Same entries, same size clause, capped by the depth available on the **exit**
side as well as the entry side. Where `tau <= H` the position cannot be exited
and falls back to hold, which is why "% exited" is not 100%.

    policy                   $/contract/day   $/day   PEAK $   %/day on peak   maxDD   worst close      t   % exited
    HOLD to settlement            0.01212    100.40      268           37.50   50.22       -50.22    5.11        0%
    EXIT at +5s                   0.00114      9.46      267            3.54   83.93       -31.84    0.66       78%
    EXIT at +10s                  0.00524     43.39      267           16.25   36.42       -36.42    2.97       77%
    EXIT at +30s                  0.00988     81.87      268           30.58   48.11       -48.11    4.95       62%
    EXIT at close-1s              0.00922     76.37      268           28.52   49.65       -49.65    3.99       82%
    EXIT +5s if profitable        0.00842     69.79      267           26.14   50.22       -50.22    3.80       19%
    EXIT +10s if profitable       0.00874     72.47      267           27.14   47.24       -47.24    3.90       28%
    EXIT +30s if profitable       0.01115     92.42      268           34.52   50.22       -50.22    4.73       28%

    bootstrap over closes:  EXIT at +5s  [-16.40, +39.61]  INCLUDES ZERO
                            every other policy excludes zero; none beats HOLD

("if profitable" is not look-ahead: the decision uses only the book at the exit
second. It is still worse than holding.)

### WHY — the book does not catch up

    H         n   mean exit c   mean settle c   exit>0 %   median spread at exit
    5      2273        -0.554          +0.629       28%          0.20c
    10     2204        -0.173          +0.552       37%          0.10c
    30     1724        +0.032          +0.335       46%          0.10c
    close-1 2306       +0.279          +0.681       45%          0.10c

The round trip is **cheap** — median spread at the entry second is 0.20c and
71% of entries are inside 0.5c, because pin trades in the tapered-tick wings
where the tick is 0.1c. The cost of crossing is not the problem. **The problem
is that the stale quote is still stale.** Five seconds after we lift a 96c ask
on a 99c-fair contract, the bid has not moved, and we would be selling back
into the same staleness that made the trade. The edge is realised at
settlement, not by the book repricing. Even at close−1s, exiting captures
0.279c of an available 0.681c.

### AND THE PREMISE OF THE QUESTION IS WRONG: capital is not the binding constraint

The job says capital lockup is "THE binding constraint at $1,000". Measured, it
is not:

    PEAK CONCURRENT CAPITAL   hold to settlement  $268
                              exit at +5s         $267
                              exit at +10s        $267
                              exit at +30s        $268

Exit frees no capital because the concurrency is **not** spread across the
minute. The peak close is:

    close 1788600600, $268 total
      tau=60  n= 91  $89.9  KXNEAR15M
      tau=60  n= 79  $78.1  KXZEC15M
      tau=56  n=100  $99.0  KXBTC15M
      tau=33  n=100  $ 0.8  KXBNB15M     <- the longshot leg, 0.8c of capital

Three large entries inside four seconds. No exit horizon of 5 s or more can
release the first before the third arrives. Median trades per close is 3, p90
is 6, max is 8; the most that ever enter on the same second is 3. The 99th
percentile of concurrent capital does fall (from $189 held to $115 at +5s) but
the peak — which is what a $1,000 account must cover — does not.

Capital is committed **4.5% of the wall clock** (37,274 of 828,000 seconds).
The position is flat and the cash is free the other 95.5% of the time.

### The one thing that could have made capital bind — checked, and it does not

This account's own settlement history has a KXBTC15M position whose settlement
was booked **14.5 hours** after the fill. If collateral is really held that
long, everything above collapses:

    settlement lag applied to every position:
      lag 0 (close)   frozen $268   favourite $267    fits $1,000
      lag 15 min             $469             $469    fits
      lag 1 h                $896             $896    fits, barely
      lag 4 h               $2480            $2477    DOES NOT FIT
      lag 14.3 h            $7291            $7282    DOES NOT FIT

So I measured it properly. `settlement_ts` is a public field on every settled
market object. Pulled 4,000 settled markets across ten crypto series:

    series             n    min   p50   p90   p99      max   >15 min   >1 h
    KXBTC15M         400      1     6    21    56     7205      0.2%   0.2%
    KXETH15M         400      1     5    21    55     7205      0.2%   0.2%
    (all nine up/down series identical to within a second)
    KXCRYPTOLEAD15M  400     35    45   335   345      345      0.0%   0.0%

    ALL 4,000: min 1s, median 6s, p90 35s, p99 335s, max 7,205s (2.0 h)
      over 1 min   128  (3.20%)      over 15 min   9  (0.23%)
      over 5 min    90  (2.25%)      over 1 h      9  (0.23%)
                                     over 4 h      0  (0.00%)

    PEAK CAPITAL WITH THE MEASURED LAG (worst of 20 draws)
      frozen rule     cap 100 -> $305      cap 200 -> $462     both fit $1,000
      favourite only  cap 100 -> $365      cap 200 -> $497     both fit $1,000

**The market settles in seconds.** The account's 14.5-hour record is on the
*balance-credit* clock, not the market clock, and three of that account's other
four settlements were booked 2–180 s after close. The discrepancy is
unresolved and is the one open question on capital: if collateral follows the
*account* clock rather than the *market* clock, the 4-hour row applies and the
answer flips. **A funded account with one open position resolves it in one
afternoon** — watch when `/portfolio/balance` frees.

### Verdict on early exit

**Do not build it.** It costs $18–91/day and buys $0–100 of peak capital that
we do not need. The only property it has that holding does not is that a sale
never waits on a settlement, and settlement takes six seconds.

---

## 4. THE REBATE, SHARPENED — the cheapest posture that still scores

### The two facts that decide it

**Score is denominated in CONTRACTS. Collateral is denominated in DOLLARS.**
Raw score is `Order Size × Distance Multiplier`; the price does not enter. A
resting bid at 2c locks 2c per contract and scores exactly as much as a resting
bid at 50c. So

    rebate per dollar of collateral  =  multiplier / price

**The Reference Price is defined by a cumulative-size walk to one fifth of the
Target Size.** An order *at* the reference price therefore has, by
construction, roughly 200 contracts queued ahead of it. **Full credit and a
deep queue are the same place** — there is no trade-off to make between scoring
and not being filled, as long as you rest at the ref rather than at the touch.

Measured on five live Coin Race markets. Grid is `linear_cent` (read from
`price_level_structure`, not assumed), so one tick is a full cent and one tick
below the ref is a 0.50 multiplier, not 0.5^10.

    market/side   touch    ref   depth   queue ahead   $ coll/50   share@ref   share@ref-1tick
    HYPE/yes       0.01   0.01     134             0        0.50       27.2%             15.7%
    SOL/yes        0.01   0.01    1132             0        0.50        4.2%              2.2%
    BTC/yes        0.12   0.04    1421           130        2.00       10.2%              5.4%
    ETH/yes        0.25   0.21    1855           132       10.50       16.1%              8.8%
    XRP/yes        0.38   0.34    2216           120       17.00       16.3%              8.9%
    XRP/no         0.50   0.46    2847           134       23.00       16.2%              8.8%
    ETH/no         0.67   0.63    3073           120       31.50       16.8%              9.1%
    BTC/no         0.80   0.76    3573           120       38.00       16.1%              8.8%
    SOL/no         0.87   0.83    3096           120       41.50       15.6%              8.4%
    HYPE/no        0.89   0.86    3193           120       43.00       17.0%              9.3%

Ranked by rebate dollars per dollar of collateral per window, the spread across
sides is **145x** ($5.435 for HYPE/yes down to $0.038 for SOL/no) for shares
all within a factor of two of each other. **The entire variation is price, not
score.**

### AND THEN THE EXCLUSION RULE TOOK IT BACK — the check that matters

The rule excludes a snapshot unless **both** sides carry the Target Size. The
sides with the best score-per-dollar are the thin ones, and a thin side is
exactly the one that fails the exclusion. **HYPE/yes carries 134 contracts
against a 1,000 target, so every snapshot of that market is excluded and its
27.2% share is worth $0.** My own ranking was wrong for two minutes; the
correction is the finding, and it is the same shape as the `ts_ms` bug — a
number that looked good because a filter had not been applied.

### The corrected answer to "cheapest posture that still scores"

**Rest at the Reference Price, on the cheapest side of a market whose BOTH
sides already clear the target.** Of the ten live sides above that selects
`BTC/yes` at 4c and `ETH/yes` at 21c: full multiplier, 130+ contracts of queue
ahead, $2.00 and $10.50 of collateral per 50 contracts, for 10.2% and 16.1% of
the side. Resting one tick below the ref halves the score to buy queue depth we
already have — on this grid it is not worth it.

**Maximum loss is the collateral.** A 50-contract bid at 4c can lose at most
$2.00, and if filled we hold 50 contracts that occasionally pay $50. Adverse
selection on that leg is real — pin measured the longshot leg at −0.45c per
contract — but the rebate at 4c is worth about 2c per contract per window,
roughly 4x the adverse selection. The real cost of being filled is that the
order stops resting and stops scoring for the remainder of the window.

### THE THING THAT NEEDS THE OPERATOR — filling the hole beats filling the queue

Run the same arithmetic forwards. At the instant I sampled (19:15 UTC, the last
seconds of a 15-minute window):

    market  side   depth   short of 1,000   touch   cost to fill at touch   our share after   $/window
    XRP     yes     3499   -- qualifies --   0.81
    XRP     no      1616   -- qualifies --   0.09
    SOL     yes        0            1,000    0.01                  $10.00           100.0%     $10.00
    SOL     no      3088   -- qualifies --   0.94
    HYPE    yes      248              752    0.05                  $37.60            85.4%      $8.54
    HYPE    no      3193   -- qualifies --   0.83
    ETH     yes       15              985    0.02                  $19.70            99.2%      $9.92
    ETH     no      3073   -- qualifies --   0.91
    BTC     yes       19              981    0.02                  $19.62            99.0%      $9.90
    BTC     no      3324   -- qualifies --   0.96

    four of five markets EXCLUDED at that instant
    cost to make all four qualify: $86.92 of collateral
    value if it held EVERY window:  $38.36/window = $3,683/day

**$3,683/day is 38% of the entire Coin Race pool and I do not believe it**, so
I measured the duty cycle rather than reporting it. 58 rounds over 263 seconds,
290 market-observations, live:

    coin    n   qualifies %   yes depth p50   no depth p50   median yes shortfall
    BTC    58          72%            4508           6173                      0
    ETH    58          72%            4126           6073                      0
    HYPE   58          72%            5443           6071                      0
    SOL    58          72%            4431           6073                      0
    XRP    58          72%            4483           6073                      0

    overall 72.4% of observations qualify
    the YES side is short in 10% of observations; the NO side in 2%

**So the one-instant table was the end of a window, not the normal state.** Mid
window the books carry four to six thousand contracts a side and qualify
comfortably. The hole opens when the race is decided and the losing coins' yes
sides empty. Scaling the instant by the measured duty cycle rather than
assuming it is permanent:

    incremental value = (extra qualifying fraction) x (our share) x pool
                      ~ 0.10 to 0.28  x  ~0.55  x  $20  =  $1.10 to $3.08 per
                        market-window, i.e. $528 to $1,478/day over 5 markets

against $10–$38 of collateral per market. **That is still the largest number
found in this project, on the smallest capital, and it is not the same
opportunity as competing for share of a busy book.** But the aggregation of
"Time Period Score" across snapshots is not pinned down in the rules I have,
so treat the range as an order of magnitude and not an estimate.

**Why it might not be money — none of these is resolved:**
1. Position and order limits. 1,000 contracts on a new, unfunded account may
   simply be refused. Nobody has checked what limit applies.
2. Anyone can do the same for the same $10. The share collapses the moment a
   second participant fills the same hole — and the fact that nobody fills it
   today is itself evidence of a constraint I have not found.
3. Being filled ends the score for the rest of the window, and a 1c bid on the
   losing leg of a coin race is precisely what a seller wants to hit.
4. Kalshi may treat one participant supplying an entire side as non-bona-fide
   liquidity. The rules quoted so far do not address it.
5. The "share of yes **plus** share of no" 2x ambiguity is still open, so every
   figure here may be double.

**The cheapest decisive test, and it needs the operator's sign-off because it
is a live order:** fund ~$25, post 1,000 contracts at 1c on one excluded Coin
Race yes side for one 15-minute window at the end of a race, then read
`/incentive_programs` for that market 2–48 h later (minimum observed settlement
lag for a paid programme is 2.0 h). Maximum loss if fully filled is $10, and
you keep 1,000 lottery tickets. One order, one window, one number back: either
about $10 or about $0.

---

## 5. API STOCKTAKE

Twenty-three GET probes, authenticated. **13 returned 200.** There is no POST
anywhere in `kauth.py`, so no order endpoint was reachable.

### Called for the first time tonight, and worth something

    GET /portfolio/orders/queue_positions?market_tickers=...
        400 without the parameter, so it EXISTS. Queue position for a resting
        order -- the single missing input for every maker and rebate fill model
        in this project. Needs a resting order, so it needs funding, but it
        converts "where would we be in the queue" from a simulation into a
        reading.

    GET /markets/{ticker}  ->  settlement_ts
        The field that settled the capital question in section 3. Public, 400
        markets per call, and it retires an assumption sitting under every
        dollar figure here.

    GET /portfolio/fills, /portfolio/settlements
        Four real fills from August -- the only real money this project has
        ever touched. They verified the fee formula (section 6). Nobody had
        opened them.

    GET /communications/rfqs
        200 and populated. There is a live RFQ system on this exchange.
        /communications/quotes is gated per participant (403: "either
        creator_user_id or rfq_creator_user_id must be filled"), so RFQs are
        visible and quotes are not. An entirely unexamined product surface.

    GET /multivariate_event_collections
        200 and populated -- composite contracts built across event legs (the
        sample returned an NFL cross-category shard with 9 associated event
        tickers). If the legs are individually quoted, the composite is a
        pricing-consistency surface: the same shape as the chain work, on a
        family nobody here has looked at.

    GET /milestones, /structured_targets
        200. Reference data (entities, films, people, event metadata) rather
        than tradeable surface. Catalogued, not pursued.

    GET /exchange/schedule, /exchange/status, /exchange/user_data_timestamp
        200. Maintenance windows and per-index trading flags. Operational, and
        the right place to look before blaming a gap in the tape on us.

    GET /markets/trades
        200. The public trade tape across ALL series, not only subscribed ones.
        A cheap way to survey liquidity in a family before committing the
        collector to it.

### 404 / not present — recorded so nobody probes them twice

    /exchange/announcements   /portfolio/resting_order_total_value
    /portfolio/summary/total_traded   /series/list   /collection
    /lookup/schedule   /user/data_timestamp

### Product families nobody here has looked at

    RFQ / quotes                      a negotiated-liquidity channel
    multivariate event collections    composite legs, consistency surface
    KXCRYPTOCOMP15M                   in the collector's default list, ZERO
                                      messages in the last six hours of tape
    KXADA15M, KXBCH15M, KXTON15M      same: subscribed, silent
    the five commodity 15M families   tape starts tonight; NOT usable for pin
                                      (section 2), but they are LIP-paid and
                                      that is why they were added

---

## 6. GROUND TRUTH — the fee formula, verified against real charged money

Every P&L number in this project rests on `fee = 0.07·n·p·(1−p)`. Kalshi's
published formula rounds **up to the next cent**, and the repo does not. Nobody
had ever checked against a real charge. This account has four:

    market                        n       price   fee charged   0.07*n*p*(1-p)   ceil to cent
    KXBTC15M-26AUG222115-15   12.37      0.8400      0.116400         0.116377         0.1200
    KXBTC15M-26AUG150130-30   38.97      0.4700      0.679600         0.679520         0.6800
    KXBTCD-26AUG1501-T63099   54.99      0.3300      0.851100         0.851080         0.8600
    KXBTC15M-26AUG150045-45   19.32      0.4900      0.338000         0.337965         0.3400

**4 of 4 match the continuous formula to under 0.02c. The round-up-to-cent
variant is wrong** — the first row was charged $0.1164, not $0.12. The repo's
`fee_per_contract` is correct as written. The fractional counts (`12.37`,
`38.97`) also confirm the `_fp` fractional-size fields are real and not a
display artefact.

---

## 7. WHAT I WOULD CHANGE IN PREREG, BEFORE THE WINDOW OPENS

A proposal, not a change. PREREG is unsigned and the window has not started, so
this is the last moment such a change is free; after the signature it restarts
the clock at zero.

1. **Add the direction clause.** *Take the trade only when it buys the side the
   model calls near-certain.* One binary structural condition, no threshold,
   theoretically motivated, +$19.5/day, forward test 1.53x faster, 11/11 days
   and 9/9 series positive, and the leg it removes is negative at t = −4.75
   with a bootstrap excluding zero on the loss side.
2. **Decide the cap now.** 100 -> 200 is +$49/day at unchanged drawdown, peak
   capital $443 of $1,000. It is a number, so it must be chosen before the
   window and not after. **Recommend 200, not 400**, purely because the fill
   race has only ever been measured at 30 contracts.
3. **Fix §3b's money-kept column** to 90.7% / 91.1%.
4. **Drop the spread filter from consideration.** It costs $7.44/day to buy
   return-on-capital we do not need at $268 of $1,000.
5. **Run the live read-only race harness before the window opens**, with the
   kill rule in section 2 written down first.

---

## 8. WHAT I COULD NOT DO

* **Whether collateral follows the market clock (6 s) or the account clock
  (up to 14.5 h).** Both measured; they disagree; only a funded account with
  one open position can tell which releases the cash.
* **The 2x "plus vs average" rebate ambiguity.** Still open, still unresolved
  from the text, and it doubles or halves every rebate number in section 4.
* **The race at 100 or 200 contracts.** Every survival figure is for 30 or
  fewer. This is the reason not to raise the cap past 200.
* **A full-window rebate duty cycle.** 4.4 minutes of live sampling and one
  end-of-window instant are not a distribution. The 28.9% tape figure and my
  72.4% live figure are consistent with a hole that opens at the end of each
  race, but the shape is a guess.
* **Any live order.** No POST exists in `kauth.py`. The Coin Race
  make-it-qualify test in section 4 is the only thing here that needs the
  operator, and it needs $25 and one order.

---

## 9. NEXT STEP, ONE THING

**Run the live read-only race harness for 24 hours before the forward window
opens.** It costs nothing, needs no sign-off, needs no money, produces ~270
signals a day, and it tests the failure mode that would make all of section 1
worthless — whether we can actually get the fill through our own stack. If it
passes, open the forward window on the amended rule (direction clause, cap 200)
and it converges in 3.7 days instead of 5.6.
