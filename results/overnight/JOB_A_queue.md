# JOB A — the queue-position simulator

Run 2026-09-06 on the operator's box. Stage built: `research/queuesim.py`
(self-test green), logs `results/overnight/queuesim_full.log` and
`results/overnight/queuesim_where.log`.

---

## The answer, in plain language

**Against the kill criterion — net +$50/day after fees at a fillable size —
market-making CLEARS, at every size tested, under every cancel assumption,
with the whole bootstrap interval far above the threshold.**

    quote size S       contracts        contracts     $/day at    $/day     95% bootstrap
    per side/market    filled (11d)      per day       +0.48c     realised   on realised     verdict
      1                   412,373           40,602         195        309   [  +216,   +402]  PASS
     10                 3,441,972          338,901       1,627      2,980   [+2,137, +3,815]  PASS
     50                12,246,316        1,205,791       5,788     11,290   [+8,027,+14,529]  PASS
    100                19,828,566        1,952,351       9,371     18,385   [+12,752,+24,013] PASS
    500                57,866,389        5,697,613      27,349     50,465   [+31,693,+69,153] PASS

The threshold needs ~10,000 filled contracts a day. **One contract resting on
each side of each market delivers 40,602 contracts a day** — four times the
number required — and the whole 95% interval on the money sits between +$216
and +$402/day. The interval never comes near $50 from above at any size.

Under the most conservative variant I could construct — no queue-camping, so
any fill sends us to the back of the queue — the same table reads $294, $2,201,
$6,188, $8,170 and $12,621 per day, with 95% intervals of [+205, +382],
[+1,521, +2,871], [+4,163, +8,225], [+5,088, +11,257] and [+5,210, +20,086].
**Twenty cells, twenty PASSes, no cell straddling $50.**

**And the size of that margin is the main reason to be careful, not to be
pleased.** This measurement inserts a quote into a book that never contained
it, then credits it with fills that in reality would have gone to somebody
else. The eight things that would have to be true for it to be an artefact,
and what each one turned out to be, are in "What would have to be true" below.
One of my own explanations was retracted by the measurement; nothing I could
check moved the verdict; the things I could not check are named at the end.

`shufS`-style sign control clean at every size: sign-scrambled money is
+$11, +$344, -$210, +$1,290 and -$5,234/day at S = 1/10/50/100/500, every
interval straddling zero.

---

## What was built, and the self-test that is the deliverable

`research/queuesim.py` — **not** `research/queue.py`. `queue` is a
standard-library module and `research/` goes first on `sys.path` in every
stage. The stub was written and `python shadow.py ..` printed

    *** research\queue.py shadows the stdlib module `queue` on THIS Python (3.14).

and exited 1. This is the same class of failure as `research/compression.py`,
which killed 14 of 16 stages on 3.14 while passing every self-test on 3.11. The
stub was deleted and the file is `queuesim.py`. **This is a deviation from the
task's filename and it is deliberate; the repo's own preflight guard forbids
the requested name.**

`python research/queuesim.py --selftest` — **PASSED**, 26 checks, 0 failures:

* **(a) a planted fill rate, checked for EXACT equality in both directions.**
  Three synthetic books whose answer is closed form (the touch price alternates
  every second, so the quote always rejoins the back of a queue of `D`, and one
  trade of `V` arrives every tenth second, filling exactly
  `min(S, max(0, V - D))` per event). Checked at
  `(D,V) = (20,25), (20,200), (200,40)` × 3 cancel policies × 5 sizes:
  every cell exact to 1e-9. `D=200, V=40` returns exactly zero.
* **MUTATION check — the test has teeth.** The same planted world run through a
  deliberately broken estimator that ignores the queue returns
  `[199, 1990, 4975, 4975, 4975]` against the true `[199, 995, 995, 995, 995]`,
  and check (a) rejects it. A test that cannot fail is not a test.
* **(b) always last in queue, volume never exceeds the size ahead.** 1,999
  trades of 900 contracts into a level of 1,000 with the price moving every
  second: **zero fills under all three cancel policies**, with the diagnostic
  proving the simulator saw 1,799,100 contracts of volume at our price — so the
  zero is a zero, not a blindness.
* **(c) never at the touch.** Prints at 45/30/70/55/41/39 against a touch of 40:
  zero. A side with no touch at all: zero. A hole in the second grid drops the
  position rather than carrying it across: zero.
* **(d) the sign-scrambled companion.** A planted +40.000c per contract is
  recovered to 1e-9 on G=80 close clusters; the same fills with random signs
  come out −0.256c against an MDE of 1.344c — inside it.
* Plus: fills never exceed the volume printed at our price; fills are
  non-decreasing in S; a quote 1c off the touch collapses to zero on a tape
  where the on-touch version fills 4,179; the no-camp bound is a bound; and the
  verdict plumbing itself — an interval straddling $50 must read INCONCLUSIVE,
  one wholly below must read MISS.

**Preflight, both required guards, both clean:**

    python research/shadow.py ..    -> clean, 51 files, 36 stdlib modules probed, exit 0
    python research/markers.py ..   -> clean, every stage that says it loaded nothing then stops, exit 0

---

## The model, and every assumption in it

1. We rest S contracts at the touch on one side. Both sides simulated
   separately; the two-sided quoter gets the sum. Fills split 48.1–49.0% bid.
2. **Queue position: we always join the BACK.** On posting or re-posting,
   `ahead` = the entire size displayed at that price. We never assume a better
   position than last.
3. **The clock is one second and the reference book is STRICTLY EARLIER.** The
   book governing second `t` is the state at the END of second `t−1` — the same
   strictly-before rule `informed.py` uses, and the rule that stops a quote
   stamped inside the trade's own second being read as the book before it.
4. A taker consumes front-first: `fill = min(S_rem, max(0, V − ahead))`,
   `ahead -> max(0, ahead − V)`.
5. **Sweeps print per level** (settled 2026-09-06 on 12M trades at true
   `ts_ms`), so the touch leg of a sweep is its own print and does count. No
   de-duplication, which is correct for a maker-fill statistic and wrong for a
   taker-decision one.
6. **Cancels are the one genuinely unknowable piece** and all three readings are
   reported. They turn out not to be load-bearing (below).
7. After a complete fill we do not re-post inside the same second; we rejoin at
   the back at the next second boundary. That is a one-second re-quote latency.
8. Makers pay no fee (`RUNBOOK`, confirmed mechanics), so gross = net here.

**Input:** `flow_cache/*.v4.csv.gz`, mined by `flow.py` from
orderbook_snapshot + orderbook_delta + ticker in seq order with stale books
quarantined. **No rebuild was triggered.** 11 of 13 days are cached
(20260825–20260904); **20260905 and 20260906 have tape but no cached book and
were excluded** rather than pay ~100 minutes for a cold rebuild.

---

## Coverage

    book          6,549,810 market-seconds over 7,941 markets, 11 cached days
                  702,732 rows (10.7%) from the rebuilt delta book
                  5,847,078 rows (89.3%) from the ticker channel
    settlements   7,941 of 7,941 book markets matched (100%)
    closes        883 distinct closes over 10.16 days = 86.9 closes/day
                  8.99 markets per close, 9 live series
    trades        240 files; 30,069,663 prints inside a book window
                  13,861,494 (46.1%) exactly at the touch
                  28,827,212 kept within 6c of the touch
                  1,882,181,038 contracts in a window; 752,095,427 (40.0%)
                  at the touch, of which 598,293,195 on the exact 1c grid
                  and 153,802,231 (20.4%) in the 0.1c tick zone
    dropped       outside a window 682,118; no touch that second 1,842;
                  more than 6c out 1,242,451; ticker absent from the
                  cached book 2,466,745

**The tapered tick is handled, and it costs the headline about half the fills.**
`engine.tick_at` is 0.1c below 10c and above 90c, but `flow.py` stores top of
book as `int(round(dollars*100))`, so in that zone 0.9950 and 0.9990 both land
on 100 and a print up to 0.5c from the true touch would read as at the touch.
**The headline therefore quotes only inside 10c–90c**, where the grid is exact.
8,577,354 prints carried sub-cent prices. Putting the 0.1c zone back roughly
doubles the fills and barely moves the money — S=50 goes from 12.2M to 22.0M
contracts and $11,290 to $11,566/day — i.e. the excluded zone is volume with
almost no per-contract edge, so excluding it is conservative on fills and
neutral on dollars.

---

## What fraction of the time our quote is at the touch at all

    market-second pairs simulated                   13,086,222
      with a touch on the quoted side, exact grid    9,271,703   70.9%
      skipped: touch in the 0.1c tick zone           3,826,705   29.2%
      skipped: hole in the second grid                       0    0.0%
    touch price still the touch one second later     6,085,093   46.5% of all pairs
                                                                 65.6% of quoted seconds
    a trade printed at our exact resting price       2,100,812   16.1% of all pairs
                                                                 22.7% of quoted seconds
    contracts printed at our resting price         598,239,210

So: we are at the touch on ~71% of market-seconds; of those, our quote survives
the second as the touch about two thirds of the time and is run over the other
third; and roughly one quoted second in four sees a print at our price.

---

## The queue ahead of us

    queue AHEAD of us when a trade arrives (9,587,778 draws)
      contracts   p10 23   p25 166   MEDIAN 1,464   p75 3,626   p90 5,733

    size resting AT the touch when we post (280,098 subsampled draws)
      contracts   p10  6   p25  24   MEDIAN    54   p75   145   p90 1,059

    trade size at our price, every print   p10 0  median  10  p90 113  p99   702
    trade size of the prints that FILL us  p10 1  median  14  p90 150  p99 1,253

The two depth lines differ by ~27x because trades arrive when the book is deep
— activity and depth move together. **The fills are selected toward larger
takers** (median 14 vs 10 contracts, p99 1,253 vs 702), which is exactly the
direction that would make +0.48c per fill the wrong price for our fills. That
is checked directly against real settlements below rather than argued.

---

## PLAN.md's kill number, confirmed AND refuted

PLAN sec.4 went taker-only on "best bid 0.40 with 3,767 contracts resting".
Re-measured off the websocket stream on 6,549,810 market-seconds
(13,099,620 touch observations, both sides):

    contracts AT the touch
      p10 3   p25 15   MEDIAN 46   p75 120   p90 534   p99 7,593   p99.9 12,622   max 85,219

    the 40c slice: 65,546 market-seconds with a best bid of exactly 40c
      bid size there  p10 6  MEDIAN 44  p90 1,144  p99 7,889  p99.9 14,479  max 22,478

    market-seconds with 3,767+ resting on EITHER touch: 449,336 (6.860%)

**CONFIRMED as an observation, REFUTED as a fact about the book.** A touch
holding 3,767+ contracts happens on 6.9% of market-seconds, and at a best bid
of exactly 40c the p90 is 1,144 and the maximum is 22,478 — so the number
PLAN.md recorded is real and could have been seen. But the **median touch is 46
contracts**, eighty times smaller, and the median at 40c specifically is 44. The
strategy was killed on a p93 observation treated as typical. RUNBOOK's separate
note that the REST endpoint returns levels ascending and truncates from the
bottom is consistent with how such a reading would have been produced.

---

## The money, and its concentration

    realised P&L per FILLED CONTRACT, clustered on close time, G = 883 closes
      S=1     +0.811c   t 6.94   MDE 0.230
      S=10    +0.944c   t 7.44   MDE 0.249
      S=50    +1.052c   t 7.69   MDE 0.268
      S=100   +1.108c   t 7.66   MDE 0.284
      S=500   +1.152c   t 7.06   MDE 0.320

    concentration of the MONEY over 883 closes
      S       top 5   top 10   top 25    $/day dropping top 10 / top 25
      1          7%      14%      30%         +270 /   +221
      10         7%      14%      29%       +2,606 / +2,165
      50         8%      14%      30%       +9,814 / +8,113
      100        9%      15%      32%      +15,817 / +12,898
      500       10%      18%      38%      +41,828 / +32,119

    concentration of the FILL VOLUME
      every size: top 5 ~1%, top 10 ~2%, top 25 ~5-6%

**This is the sharpest contrast with `pin`, and it is the reason the two
verdicts differ.** `pin` at cap 50 had the top 10 of 336 closes carrying 45% of
the money and dropping them left $19/day — the operator's own definition of a
lottery ticket. Here the top 10 of 883 closes carry 14%, and dropping the top 25
still leaves $8,113/day at S=50. The money is spread across the tape, not
sitting in a handful of closes.

**Cancel assumption is not load-bearing:**

    policy       S=10 $/day    S=50 $/day    S=100 $/day
    behind            3,105        11,586         18,862      (pessimistic)
    prorata           2,980        11,290         18,385      (headline)
    front             2,971        11,191         18,314      (optimistic)

A 3.5% spread across the whole range of what the tape cannot tell us. The
unknowable piece does not decide anything.

---

## What would have to be true for this to be an artefact

**1. `count_fp` (trade size) is not the same unit as `yes_bid_size_fp` (book
size).** If trades were quoted in a different unit the whole fill model would be
scale-wrong. **CHECKED and reconciled by hand.** On 14 markets, `sum(count_fp)`
over the market's life against the ticker channel's independent cumulative
`volume_fp`: ratios 0.472 to 0.500. `volume_fp` counts both sides, and on a
single message `dollar_volume` = 2,308,359 exactly equals `volume_fp`/2 =
4,616,718/2. So `count_fp` is contracts, one side, the same unit the book quotes
sizes in. *KXBTC15M really does trade ~2.3 million contracts per 15-minute
window.*

**2. Trades are duplicated in the tape.** **CHECKED.** 479,949 trade messages
over six hours carry 479,949 distinct `trade_id`. Zero duplicates.

**3. The book is crossed or locked, so one print fills both our quotes.**
**CHECKED.** 0 crossed and 0 locked books in 6,549,810 market-seconds.

**4. The trade clock and the book clock disagree.** `flow.py` mines the book on
the collector's local receive second (`_rx_ms`), so trades are matched on
`_rx_ms` too. **MEASURED:** 8.59% of trades fall in a different second under
`_rx_ms` than under Kalshi's `ts_ms`; receive lag median 15 ms, p99 1,913 ms.
Using the receive clock is both the consistent choice and the realistic one — a
live maker only knows what has arrived.

**5. The estimator credits fills at prices where we were not resting.** The
real-data placebo moves our quote inside the book:

    quoting 1c inside the touch, S=50:  7,532,977 contracts   61.5% of the on-touch total
    quoting 2c inside the touch, S=50:  3,863,598 contracts   31.6%
    quoting 5c inside the touch, S=50:  1,021,906 contracts    8.3%

    **Read this honestly: 61.5% at one tick is NOT a clean zero and I am not
    going to call it one.** A quote one tick behind the touch genuinely does
    fill — that is what happens when the touch moves down through it, and with a
    median spread of 1c that happens constantly. The informative reading is the
    gradient: 61.5% -> 31.6% -> 8.3%. The estimator is strongly price-sensitive,
    and requirement (c) — never crediting a fill our quote could not have
    received — is enforced structurally (the fill test is `trade price == our
    resting price`) and verified against a clean zero in the self-test, where the
    trade prices never equal the quote.

**6. The per-contract edge on OUR fills is not what `informed.py` measured.**
This is the one that matters most, because +0.48c per fill is the whole
economic case. Our fills earn **+0.81c to +1.15c per contract, roughly double
+0.48c, and the number RISES with quote size** — the opposite of what adverse
selection would do. So I measured the population our fills are drawn from:
**every at-touch print in the exact-1c grid, whether we won it or not.**

    BENCHMARK, every at-touch fill, exact 1c grid, 883 closes
      per PRINT      +0.781c   t 7.73   MDE 0.198   on 10,672,189 prints
      per CONTRACT   +0.774c   t 5.74   MDE 0.265   on 598,293,195 contracts
    informed.py, at-touch, per print, ALL prices:  +0.48c   t 6.4

Two things fall out, and one of them **retracts a hypothesis I had written
down before measuring it**:

* **Per print and per contract agree to 0.007c.** So contract-weighting is
  neutral in this population and my first explanation — "our number is per
  contract, informed's is per print, and big prints pay the maker more" — is
  **wrong and withdrawn.**
* The whole gap from +0.48c to +0.78c is therefore **the tick-zone restriction
  alone**. The exact-1c band is the *wider* half of the market: **mean spread
  2.52c when the best bid is in 10c–90c against 1.42c outside** (median 1c in
  both). `informed.py` measures at-touch `mkS` = +0.02c (t=0.3) — at-touch
  takers carry no information — and `maker = half-spread − mkS` holds by
  construction, so the maker keeps essentially the whole half-spread. A ~2.5c
  mean spread implies a ~1.25c half-spread and +0.78c sits inside it. **The
  arithmetic reconciles, and it is the half-spread, not a new edge.**

That leaves the *residual*: our queue-selected fills earn 5% more than the
population at S=1 and 49% more at S=500. **The rise with size is the
queue-camping the one-second clock hands us** — forbid it (next section) and
the curve turns over: +0.819c at S=1, peaking at +0.949c at S=50, falling to
+0.765c at S=500, which is the population rate again. That turn-over is the
adverse-selection signature, and it only becomes visible once camping is
removed.

**7. The money is really the `pin` effect in disguise, made in the last seconds
before close where the settlement average is nearly known.** Checked by
time-to-close bucket — see below and `results/overnight/queuesim_where.log`.

**8. We are not adding money, we are taking someone else's.** True, and it is
the right way to read the size. 598,239,210 contracts printed at our price over
10.16 days; at ~1c per contract the entire at-touch maker pool is on the order
of **598,293,195 x 0.774c = $4,630,789, or $455,786 a day, shared by every
maker at the touch**. Our S=50 headline of $11,290/day is **2.5% of that pool**
against the **2.05%** of at-touch volume the simulator wins
(12,246,316 / 598,239,210); under the no-camp bound it is 1.4% of the pool on
1.3% of the volume. **The number is large because the pool is enormous, not
because the per-contract edge is** — and every dollar of it is a dollar some
existing maker does not get.

---

## Arithmetic reconciled by hand

    S=50:  12,246,316 contracts / 883 closes            = 13,868 per close
           13,868 x 86.9 closes/day                     = 1,205,129 /day   (printed 1,205,791)
           1,205,791 x $0.0048                          = $5,788/day       (printed 5,788)  OK
           $11,290/day / 1,205,791 contracts            = 0.936c per contract, volume weighted
           close-clustered per contract                 = 1.052c            consistent
           $11,290/day x 10.16 days                     = $114,706 total
           12,246,316 x 0.936c                          = $114,626 total    OK

    fills as a share of the flow at our price
           12,246,316 / 598,239,210                     = 2.05%
    per market-side
           12,246,316 / (7,941 markets x 2 sides)       = 771 contracts per 15-min window
           771 / 50                                     = 15.4 complete fills, one per 58s

---

## One market, one fill, walked by hand

`KXSOL15M-26AUG292015-15`, close 1788048900, settled NO (`result` 0.0, so
Y = 0c). 853 book seconds covering tau 30s to 882s; 2,519 prints on the ticker
in those hours, 58,133 contracts; 1,256 of them on the bid, 30,097 contracts.

    FILL EVENT at second 1788048059   (tau = 841s)
      book at END of second 1788048058:  bid 31c size 1.00   ask 35c   (src T)
      -> we rest 50 at 31c and join the BACK:  ahead = 1.00
         print 31c x 0.40 : min(50.00, max(0, 0.40 - 1.00)) = 0.00   ahead -> 0.60
         print 31c x 1.00 : min(50.00, max(0, 1.00 - 0.60)) = 0.40   ahead -> 0.00
      book at END of second 1788048059:  bid 31c size 0.60
      P&L: bought YES at 31c, Y = 0c  ->  -31c x 0.40 = -$0.12

    the NEXT second, 1788048060, shows the queue state being CARRIED, which is
    the part a naive re-derivation gets wrong:
      book at END of 1788048059: bid still 31c, size 0.60 -- price held, so we
      do NOT re-post; our ahead is still 0.00 from the sweep above.
         print 31c x 0.60 : fill 0.60      (we are at the FRONT)
         print 29c x 273.38 : not our price (31c), ignored
         print 31c x 1.00 : fill 1.00
         print 29c x 47.14, 29c x 158.81 : ignored

**Two things this makes concrete.** First, the price-filter really does bite:
479 contracts printed at 29c in that one second and none of them touched us.
Second, this is the queue-camping the one-second clock hands us — after the
sweep at 31c we sit at the front and take the next prints in full.

**And this market LOSES.** Bid side, S=50: 92 fill events, 478.1 contracts,
**−$88.17**. We bought YES at 31c over and over while the market walked down to
29c and settled at zero. The aggregate is positive because the ask side is the
other half of the same spread; quoting one side only is not the strategy and
this market is what it looks like when the tape runs you over.

## Inventory and cash, which the fill count hides

    net position left on the book at settlement, per market, S=50
      |net| contracts   median 127   p90 618   p99 1,646   max 4,334

    cash turned over per close (sum of price x size), S=50
      $ median 6,410   p90 11,794   max 18,076

At S=50 the strategy turns over roughly **$557,000 of cash a day** to make
$11,290 — a 2% margin on turnover, which is an ordinary market-making margin and
a further sign the per-contract number is not absurd. But the *capital at risk*
is small: a median 127-contract net position per market across ~9 markets is on
the order of $1,100 of settlement exposure at a time. **$11,290/day against that
is a daily return no competitive market pays, and an implausible return on
capital is the signature of a missing constraint rather than of an edge.** The
missing constraint is almost certainly competition (see item 8 above) and
queue-position realism at sub-second scale (see the no-camp bound).

---

## The no-camp bound — the number to quote if only one may be quoted

At one-second resolution, once a taker has cleared the queue our quote sits at
the FRONT for the rest of that second and for every later second the price
holds. On a market printing 40+ trades a second that is a position no real
maker keeps against sub-100ms competitors. `recycle=False` forbids it: **any
fill ends our participation for that second and we rejoin at the BACK next
second with what is left of the order, never topped back up.**

    S      contracts     contracts/day    $/day     95% bootstrap        verdict
      1      391,555            38,553      294   [   +205,    +382]     PASS
     10    2,748,398           270,611    2,201   [ +1,521,  +2,871]     PASS
     50    7,528,235           741,241    6,188   [ +4,163,  +8,225]     PASS
    100   10,813,341         1,064,698    8,170   [ +5,088, +11,257]     PASS
    500   21,474,860         2,114,447   12,621   [ +5,210, +20,086]     PASS

    per contract   +0.819c t 6.94 | +0.899c t 6.80 | +0.949c t 6.50
                   +0.910c t 5.83 | +0.765c t 4.17          (S = 1/10/50/100/500)
    top-10 closes   14% | 14% | 16% | 20% | 30% of the money
    drop top 10     $257 | $1,914 | $5,235 | $6,646 | $8,958 per day
    net position left at settlement per market, S=50:
                    median 73   p90 354   p99 1,142   max 2,576

Camping is worth 5% of the fills at S=1, 20% at S=10, 39% at S=50, 45% at
S=100 and 63% at S=500 — so it matters more the larger the quote, exactly as
you would expect, and **it is nearly irrelevant at the size the measurement is
cleanest at.** Removing it also restores the adverse-selection curve: the
per-contract edge now peaks at S=50 and falls back to the population rate by
S=500 instead of rising monotonically.

**Every cell still PASSES with the whole interval above $50/day.**

## Where the money comes from — the last two artefact hunts

S=50, exact-1c grid, camping allowed; total $114,663 on 12,246,316 filled
contracts = 0.9363c per contract, volume weighted.

    by TIME TO CLOSE          contracts    share          $   c/contract
      tau <= 30s                  3,032     0.0%        105       3.458
      31 - 60s                  125,042     1.0%        802       0.641
      61 - 180s               1,056,219     8.6%     15,001       1.420
      181 - 420s              3,224,414    26.3%     11,022       0.342
      421 - 900s              7,837,607    64.0%     87,734       1.119

    by FILL PRICE             contracts    share          $   c/contract
      1 - 10c                   287,947     2.4%      1,481       0.514
      11 - 25c                2,299,001    18.8%     26,058       1.133
      26 - 45c                2,998,648    24.5%     32,426       1.081
      46 - 55c                1,486,438    12.1%     15,922       1.071
      56 - 75c                2,868,586    23.4%     19,618       0.684
      76 - 90c                2,305,694    18.8%     19,157       0.831

**This is NOT the `pin` effect wearing a different hat.** The last minute
before close carries **1.0% of the volume and $907 of $114,663 — 0.8% of the
money.** 77% of the money is made between 421 and 900 seconds from close, in
the first half of the market's life, which is where market-making money is
supposed to be and where the settlement average is least knowable.

**It is not the deci-cent zone leaking back in either.** The money is spread
over every price bucket at 12–25% of volume each, and the bucket nearest the
excluded zone (1–10c) has both the smallest share (2.4%) and the *lowest*
per-contract edge (0.514c).

    per-close correlation, money vs at-touch volume    -0.097
    per-close correlation, money vs contracts filled   -0.003
    883 closes   mean $129.86   median $135.16   profitable 62.2%
    per close   p10 -$552.7   p25 -$199.9   median +$135.2
                p75 +$481.5   p90 +$825.9   worst -$2,648   best +$1,958

**Mean ≈ median and 62% of closes profitable: this is not a lottery ticket.**
The money does not track volume (r = −0.10) or fill count (r = −0.00), so the
total is not simply a restatement of how busy the tape was. **But the worst
close (−$2,648) is larger than the best (+$1,958), and a quarter of closes lose
$200 or more.** That tail is real and belongs next to the mean.

Reconciles: $129.86/close × 86.9 closes/day = $11,285/day against the printed
$11,290. Total $114,663 against the hand figure $114,706.

---

## What is NOT measured, and remains open

1. **Our own size is not in the tape's book.** At S=50 against a median touch of
   54 contracts we would be roughly half the level; the other makers would see us
   and either price-improve or pull, and taker behaviour is conditioned on a book
   that did not contain us. **S=1 is the only size where this perturbation is
   negligible — and S=1 still returns $309/day with a 95% interval of
   [+216, +402]. The objection cannot overturn the verdict, only the magnitude at
   large S.**
2. **Sub-second queue racing.** The clock here is one second and HANDOFF records
   that whole-second stamps leave the reference quote a median 1.75s old in
   truth. Who wins a queue slot inside a second is not decidable on this tape.
3. **Latency, cancel/repost round trips, rate limits, and whether Kalshi would
   let us rest this size.**
4. **Two days of tape (20260905, 20260906) are excluded** because `flow_cache`
   is not warm for them, and 2,466,745 trades were dropped because their ticker
   has no cached book row.
5. **The forward test has not started.** The kill criteria require 500 fired
   closes of FORWARD tape after the rule is frozen in writing. The 883 closes
   here are not part of it.
6. **The deci-cent zone is not decidable from this cache.** Deciding it needs
   `flow.py` to store top of book on the tapered grid rather than
   `int(round(dollars*100))` — a one-line change and a full cold rebuild.

---

## Verdict

**MARKET-MAKING CLEARS the +$50/day threshold.** At every size from 1 to 500
contracts; under all three cancel assumptions; under the conservative no-camp
bound as well as the headline; with the entire bootstrap interval above the
threshold in all twenty of those cells; with a clean sign-scrambled control;
with the money spread over 883 closes rather than concentrated in ten; and with
the per-contract rate independently confirmed at +0.774c (t=5.74) on the whole
at-touch population it is drawn from.

**The number to quote is the most conservative one that is still clean: S = 1
contract per side per market, no queue-camping — $294/day, 95% [+205, +382],
on 38,553 filled contracts a day.** That is the size at which our own presence
is not distorting the book we are simulating against, and it is still six times
the threshold. The fill count alone is four times what the criterion requires.

**What this does not say.** It clears on eleven days of recorded tape against a
book that never contained us. It has not cleared forward, at real latency,
against makers who would see us arrive. The implied return on the capital at
risk (a median 73–127 contract net position per market) is far too high for a
competitive venue, and an implausible return on capital is the signature of a
missing constraint, not of a generous market. The most likely missing
constraint is simply that our fills would come out of a ~$456k/day pool the
existing makers are already sharing, and they would not hand over 1-2.5% of it
without reacting.

**Per the operator's kill criteria this is the outcome that keeps the search
alive: market-making does NOT die here.** The next step is not to scale it —
it is to freeze the rule in writing at S = 1 and start the 500-close forward
window, which at 86.9 closes/day is about six days of tape.

---

## Like you're five:

I wrote a little pretend trader. It stands in the queue at the shop counter
offering to buy or sell at the best price on the board, and it always goes to
the *back* of whatever queue is already there. Then I replayed eleven days of
what really happened at that counter, second by second, and counted how often
the queue in front of my pretend trader got used up so that a customer reached
*it*.

Before trusting the counter at all, I gave it fake days where I already knew the
answer: days where it should get exactly 995 items, days where it should get
exactly none because the queue in front is always too long, and days where the
customers are buying something else entirely so it should get nothing. It got
every one of those exactly right, and I also gave it a deliberately broken
version to make sure my checks would catch a bad counter. They did.

On the real days the pretend trader gets filled a lot — about 39,000 items a day
even when it only ever offers one at a time — and each item it trades is worth
about three quarters of a penny to it. The rule the operator set is "make at
least $50 a day". This makes about $294 a day at its most cautious setting, and
I checked that the money is not coming from one lucky afternoon (the ten best
days out of 883 are only a seventh of it) and not from the last few seconds
before each race finishes (that part is less than one percent of it).

But this is a *pretend* trader in a *recording*. The real people at the counter
never saw it. Everything it "earns" is money one of them actually earned, so if
it really turned up they would move, or stand in front of it, or stop leaving a
gap. It also earns about $300 a day while only ever having about $1,000 tied up,
which is a rate of return nobody in a busy shop leaves lying around — and when a
sum looks too good like that, the usual reason is that something has been left
out of the pretend version, not that the shop is generous. So: the recording
says yes, loudly. The recording cannot say what happens when someone is looking
back at you.

## What I need from you:

Nothing, this job is complete. Two decisions are waiting on you, though, and
neither blocks anything tonight:

1. **Freeze the rule and start the forward window?** The kill criteria need 500
   fired closes of forward tape after the rule is written down. At 883 closes in
   10.16 days that is ~6 days of forward tape, far cheaper than `pin`'s 19. The
   rule I would freeze, verbatim: *rest S contracts at the touch on both sides
   of every crypto 15-minute market whose touch price is between 10c and 90c,
   re-quoting at most once a second, always joining the back of the queue, and
   holding every fill to settlement.*
2. **Is `S = 1` the size worth deploying first?** It is the only size at which
   our own order is not a material part of the level we are simulating against,
   and it already clears the threshold six times over at $294/day. Everything
   above S=10 is measuring a book we would have changed.
3. **Do you want the 0.1c tick zone decided?** It is 20.4% of at-touch volume
   and currently excluded because `flow.py` rounds top of book to whole cents.
   Deciding it is a one-line change to `flow.py` plus a full cold rebuild
   (~100 min). I did not trigger one.
