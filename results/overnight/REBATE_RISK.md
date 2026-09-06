# THE COIN RACE REBATE'S INVENTORY RISK — MEASURED

**Job 1, overnight 2026-09-06.** Tape: `KXCRYPTOLEAD15M` (Coin Race), UTC
2026-09-04 → 2026-09-06, **1,253 clean markets across 251 fifteen-minute
closes**, 3.90M book events, 17,043 prints, 1,053,590 weighted
snapshot-seconds. Settlement truth from `market_lifecycle_v2` (`result`,
`settlement_value`) for **every** market scored.

---

## THE ANSWER IN ONE PARAGRAPH

The rebate survives the inventory test, **but only because you never have to
quote at the touch.** At the touch the idea is marginal: you are a newcomer at
the back of a queue, so the only prints that reach you are the ones that clear
the whole level — and those are the toxic ones. Net at the touch is
**+$1.8/close under two fill models and −$2.7/close under the third**, and it
is negative on two of the four dates in the tape. But Kalshi's Liquidity
Incentive Programme does **not** pay for being at the touch. It pays full
credit at or above a *reference price* that sits a **median four ticks below
the touch**, because the median top-of-book size is 120 contracts against the
200 needed to make the touch the reference. Standing **three ticks back keeps
93% of the rebate, cuts fills by 60%, and flips the fill P&L from negative to
positive.** So the answer to *"you only get paid where you get run over"* is
**no — and that is the whole finding.**

**Recommended configuration: S = 50 contracts, 3 ticks behind the touch, both
books, all five coins.**

| | rebate only | rebate + fills (base) | rebate + fills (conservative) |
|---|---|---|---|
| $ / 15-min close | 2.94 | 5.07 | 3.07 |
| **$ / day (96 closes)** | **282** | **486** | **295** |
| 95% bootstrap over 251 closes, $/day | [257, 309] | [+290, +692] | [+197, +398] |
| peak concurrent capital | $254 (measured $196 median, $367 max) | | |
| **% return on capital / day** | **111%** | 191% | 116% |
| per 15-minute window | 1.16% | 2.0% | 1.2% |
| **$ / contract / day** (500 resting) | **0.564** | 0.973 | 0.589 |
| positive on each of 4 dates? | — | **yes, 4/4** | **yes, 4/4** |

The 111%/day is not a typo and is not exotic: **the same $254 of collateral
turns over 96 times a day.** Per turn it earns 1.16%.

---

## OPERATOR QUESTION (a): IS THE FLOW ABSENT?

**No. The flow is there; the queue is the gate.**

Coin Race markets trade **409.7 contracts per market** (513,367 contracts over
1,253 markets, 14,382 prints). That is not a dead market.

What is scarce is *flow that reaches a newcomer*. Resting 50 contracts at the
touch on both books, joining the **back** of the queue each time the touch
moves:

### TABLE A — fill rate at the touch, three fill models

| S | model | contracts / market | contracts / day (480 mkts) | fill P&L c/ctr |
|---|---|---|---|---|
| 10 | exact-price (lower bound) | 2.33 | 1,118 | −4.464 |
| 25 | exact-price | 4.12 | 1,975 | −4.927 |
| 50 | exact-price | 5.84 | 2,803 | −4.730 |
| 100 | exact-price | 7.72 | 3,703 | −4.224 |
| 10 | **sweep+size (BASE)** | 6.41 | 3,076 | −2.323 |
| 25 | **sweep+size (BASE)** | 12.16 | 5,835 | −1.792 |
| 50 | **sweep+size (BASE)** | 17.93 | 8,607 | −1.462 |
| 100 | **sweep+size (BASE)** | 24.23 | 11,629 | −1.034 |
| 10 | full sweep (upper bound) | 9.45 | 4,535 | −2.981 |
| 25 | full sweep | 21.91 | 10,518 | −2.952 |
| 50 | full sweep | 41.44 | 19,889 | −2.810 |
| 100 | full sweep | 78.90 | 37,874 | −2.665 |

**Only 4% of the volume reaches us** at S=50 in the base model (17.9 of 409.7).
62% of markets fill us not at all. So: rebate real, flow real, *our* flow thin.

### The three fill models, and why there are three

1. **exact-price (lower bound).** We fill only when the tape shows a print at
   exactly our price and it is big enough to clear the queue ahead of us. This
   **cannot fill an order resting where nobody was resting historically** —
   and 82% / 91% / 65% of the levels 1 / 2 / 3 ticks behind the touch are
   empty (§C9). So it badly understates fills once we step back.
2. **sweep with size (BASE).** One marketable taker order is reported as one
   print per level, so summing the prints in a millisecond gives the taker's
   total size *Q*. Our fill is `clamp(Q − A, 0, S)` where *A* is the real
   resting size priced ahead of us, **capped at the deepest price the taker
   actually printed at** — a marketable *limit* order will not go past its own
   limit however empty the book below is. This is the physically correct model.
3. **full sweep (upper bound).** Any print deeper than our price takes us in
   full, i.e. the taker had unlimited extra size for us. Deliberately too
   aggressive; it brackets the answer.

The first correction mattered: without the limit-price cap, the sweep model
filled us at prices the taker was never willing to pay and reported +$5.2/close
of phantom profit at d=8. With the cap it reports +$1.19.

---

## OPERATOR QUESTION (b): ARE THE FILLS TOXIC?

**Two different answers, and both are needed.**

### The market's takers are NOT informed — measured with no model at all

`takerpnl.py` uses only the trade tape and the settlement records: no queue
model, no fill engine, no rebate model. For each of 14,382 prints (449,803
contracts) it computes what the taker made, holding to settlement.

```
TAKER, per contract, size-weighted:
  gross P&L to settlement      -1.309 c
  quadratic fee                -0.954 c
  NET                          -2.263 c
  price paid vs mid            -3.957 c   (they pay the spread)

MAKER on the other side, per contract, ZERO fee (fee_type = quadratic):
  gross P&L to settlement      +1.309 c
```

**Whoever trades on Coin Race loses 1.3c a contract before fees and 2.3c
after.** That is better than the crypto series in `informed.py` (+0.48c/fill
for the maker); the average Coin Race maker earns **+1.31c/fill**. On this
measure the answer to (b) is an unambiguous *no, the takers know nothing*.

### But the fills WE would get are adversely selected — by queue position

The market's *average* maker is not us. We are the newcomer at the back. The
same fill engine, changing **only** the queue assumption:

| queue | S | contracts / market | fill P&L c/ctr |
|---|---|---|---|
| **front** of queue (exact-price) | 50 | 156.79 | **+0.560** |
| **back** of queue (sweep+size) | 50 | 17.90 | **−1.462** |
| **back** of queue (exact-price) | 50 | 5.83 | **−4.730** |

Front-of-queue reproduces the model-free +1.3c almost exactly. Back-of-queue
is negative. **Queue position does not merely ration fills, it selects the bad
ones**: the only prints that reach the back of a level are the ones large
enough to consume it, and those are the ones after which the price moves
through.

### Markouts, S = 50 at the touch

| | vs mid at fill | +1s | +5s | +30s | **SETTLE** |
|---|---|---|---|---|---|
| exact-price | +2.337 | −0.554 | −0.051 | −1.310 | **−4.730** |
| base (sweep+size) | — | — | — | — | **−1.462** |

Split by book (exact-price, S=50): filled on the YES book (we bought yes)
4,241 contracts at **−5.337 c/ctr**; filled on the NO book (we sold yes)
3,078 contracts at **−3.893 c/ctr**. Both sides lose; it is not a one-sided
story.

### It is not the taker's *timing* — placebo test

A negative markout is only "toxicity" if a random moment would have been
better. **C7:** for every real fill, draw a random second in the *same market*
and the *same minute-to-close bucket*, on the *same book side*, same size.

| S | real | time-matched placebo | real − matched, per close | 95% bootstrap over 210 closes |
|---|---|---|---|---|
| 10 | −4.464 | −4.571 | +$0.015 | [−0.207, +0.233] |
| 25 | −4.927 | −5.047 | +$0.030 | [−0.433, +0.499] |
| 50 | −4.730 | −5.721 | +$0.345 | [−0.449, +1.157] |
| 100 | −4.224 | −5.721 | +$0.689 | [−0.542, +1.976] |

**Every interval contains zero and every point estimate is positive.** The
taker who hits us did not pick a better second than chance. The loss at the
touch is not informed flow; it is the *price* — resting at the touch on a
product whose five mids sum to 103.5c (§C6) is simply a bad place to stand.

> The first version of this placebo drew uniformly over the market's life and
> reported a spectacular "+5.2c of toxicity avoided". It was confounded: real
> fills cluster in the last two minutes (57% of contracts within 2 minutes of
> close) and `E[settle − mid]` swings from +16c at 14 minutes left to −3c at
> the close. Matching on minutes-to-close killed the effect entirely. **That
> number is withdrawn.**

---

## THE DISTANCE QUESTION — AND IT IS THE WHOLE ANSWER

### C1: the LIP reference price is nowhere near the touch

The rule: *"walking down from the best bid, the first price level at which
cumulative resting size reaches one fifth of the Target Size"*. Target 1,000,
so **200 contracts**. Measured over 545,329 market-seconds where that side had
≥1,000 depth:

```
                 ticks from touch to the reference price
YES book   0:16.8%  1:13.0%  2: 2.6%  3: 5.5%  4:39.8%  5: 8.4%  6+:13.8%
NO  book   0: 2.7%  1: 2.4%  2: 1.6%  3:13.5%  4:50.8%  5:10.9%  6+:18.1%
median top-of-book size 120  (200 needed to make the touch the reference)
```

**The modal gap is 4 ticks.** Everything from the touch down to the reference
scores multiplier **1.0**. Only below it does the 0.50-per-tick halving start.
And the programme states **no obligations** — no mandatory two-sided quoting,
no maximum spread, no minimum uptime. Nothing requires us to be at the touch.

### TABLE B — the distance sweep, S = 50

Base fill model (sweep + size):

| d | ctr/mkt | fill c/ctr | rebate $/close | net $/close | net $/day | peak cap $ | %/day | 95% boot net $/day |
|---|---|---|---|---|---|---|---|---|
| 0 | 17.93 | −1.462 | 3.145 | 1.836 | 176 | 284 | 62% | [−101, +445] |
| 1 | 10.31 | +0.832 | 3.072 | 3.501 | 336 | 267 | 126% | [+131, +536] |
| 2 | 8.10 | +3.225 | 2.992 | 4.296 | 412 | 260 | 158% | [+220, +610] |
| **3** | **7.15** | **+5.960** | **2.938** | **5.065** | **486** | **254** | **191%** | **[+290, +692]** |
| 4 | 4.23 | +9.176 | 2.715 | 4.652 | 447 | 243 | 184% | [+274, +616] |
| 5 | 3.00 | +4.390 | 1.820 | 2.478 | 238 | 237 | 100% | [+84, +386] |
| 6 | 2.24 | +6.350 | 1.181 | 1.892 | 182 | 233 | 78% | [+60, +306] |
| 7 | 1.97 | +2.603 | 0.796 | 1.052 | 101 | 229 | 44% | [−19, +222] |
| 8 | 1.46 | +8.465 | 0.572 | 1.189 | 114 | 226 | 51% | [+8, +221] |

Conservative fill model (exact-price), same size:

| d | ctr/mkt | fill c/ctr | rebate $/close | net $/close | net $/day | 95% boot net $/day |
|---|---|---|---|---|---|---|
| 0 | 5.84 | −4.730 | 3.145 | 1.766 | 169 | [+81, +260] |
| 1 | 2.02 | −0.215 | 3.072 | 3.051 | 293 | [+236, +352] |
| 2 | 1.12 | +1.995 | 2.992 | 3.104 | 298 | [+229, +366] |
| **3** | **2.25** | **+1.171** | **2.938** | **3.069** | **295** | **[+197, +398]** |
| 4 | 1.05 | +4.228 | 2.715 | 2.937 | 282 | [+202, +361] |
| 5 | 0.65 | +1.839 | 1.820 | 1.880 | 180 | [+117, +246] |

**The rebate decays by 7% over three ticks and by only 14% over four. Fills
fall 60% and their sign flips.** The two independent fill models put net $/day
at d=3 at **$486** and **$295** — very different fill counts, same conclusion.

### TABLE C — rebate alone (assume every fill nets exactly zero)

This is the number to underwrite. It has no directional bet in it.

| S, d | reb $/close | **reb $/day** | peak cap $ | %/day on capital | 95% boot $/day |
|---|---|---|---|---|---|
| S=50 d=0 | 3.1445 | 301.87 | 283.69 | 106% | [275, 330] |
| S=50 d=1 | 3.0723 | 294.94 | 266.93 | 110% | [269, 323] |
| S=50 d=2 | 2.9919 | 287.23 | 260.43 | 110% | [262, 315] |
| **S=50 d=3** | **2.9377** | **282.01** | **254.33** | **111%** | **[257, 309]** |
| S=50 d=4 | 2.7152 | 260.66 | 243.37 | 107% | [238, 285] |
| S=50 d=5 | 1.8202 | 174.74 | 237.43 | 74% | [159, 192] |
| S=50 d=8 | 0.5720 | 54.91 | 225.63 | 24% | [48, 63] |
| S=10 d=0 | 0.6373 | 61.18 | 62.26 | 98% | [55, 67] |
| S=25 d=0 | 1.5633 | 150.07 | 148.75 | 101% | [136, 165] |
| S=100 d=0 | 9.1526 | 878.64 | 540.83 | 162% | [806, 959] |

*(These bootstrap intervals are sampling error only. The model risk — §"what
would make this fiction" — is far larger, and no interval here contains it.)*

### The step-back is a real property of the book, not a fitting artefact

The fill count at d=3 exceeds d=2 at S=25, 50 **and** 100. That monotonicity
violation is explained, not waved away: the book is a lattice of mostly-empty
levels.

```
d   median size   mean size   p90 size   % EMPTY
0          120         395        123      0.0%
1            0         306        120     81.8%
2            0          68          0     90.7%
3            0          50        120     65.0%
4          120         251        170     39.7%
```

Size clusters at the touch and again around 4 ticks back; 1–2 ticks back is
usually a hole. A taker's limit stops where the size is, so d=2 sees fewer
sweeps than d=3–4 — which is also why the exact-price model (which cannot fill
in a hole) needs the sweep model beside it.

### Independent corroboration: deep prints are good for the maker

From the model-free taker P&L, by how deep the print was relative to the touch:

| ticks past the touch | contracts | taker gross | **maker gross** |
|---|---|---|---|
| inside / stale | 16,868 | +2.887 | −2.887 |
| at touch | 343,575 | −1.088 | **+1.088** |
| 1 | 45,292 | −0.092 | +0.092 |
| 2 | 6,230 | −2.559 | +2.559 |
| 3 | 5,810 | +0.723 | −0.723 |
| 4 | 14,514 | −4.495 | **+4.495** |
| 5 | 17,513 | −10.418 | **+10.418** |

Sweeps overshoot and revert. Standing 3–5 ticks back and being taken by an
impatient sweep is the *profitable* fill on this product — measured without
any of my simulation machinery.

---

## PEAK CONCURRENT CAPITAL

Measured second by second across every Coin Race market with a live two-sided
book. Resting a two-sided quote costs `S × (B + N)` cents, where `B + N =
100 − spread`; nothing nets until settlement.

```
markets quoted at the same second: median 5   p90 5   max 8
sum over live markets of (B+N), cents:  median 391   p99 480   max 734

resting-order collateral alone, DOLLARS:
   S       median      p99       max
   10       39.10    48.00     73.40
   25       97.75   120.00    183.50
   50      195.50   240.00    367.00
  100      391.00   480.00    734.00
```

Adding the cost of inventory already filled, the simulation's peak is
**$254 at S=50 d=3**. Against the $1,000 budget: **S=50 uses 25–37% of
capital; S=100 uses 49–73% and is the largest size that fits.**

Two windows do not overlap (max 8 markets at once, not 10), so the five coins
are the concurrency, not the calendar.

---

## SEPARATE FINDING — THE LEGS SUM TO 100, AND THERE IS NO ARBITRAGE

Exactly one coin leads, so the five YES legs settle to exactly 100c. Checked at
every event-second with all five legs two-sided (96,851 of 183,778 = 52.7%),
sized by the smallest executable leg, net of the quadratic taker fee
`ceil(0.07·p·(1−p)·n)` on all five legs:

```
BUY all 5 YES  (sum of asks < 100)
    seconds where the raw inequality held : 22   (0.02%)
    still positive AFTER taker fees       : 0
    best sum seen 95c, median 98c

SELL all 5 YES (sum of bids > 100)
    seconds where the raw inequality held : 404  (0.42%)
    still positive AFTER taker fees       : 4
    best net $0.11, then $0.04, $0.02, $0.01 — four seconds in three days
```

**Dead.** Five legs at p≈0.2 cost ≈5.6c of fee; the median dislocation is 1c.
You would need the bids to sum past 106c, which never happens. **There is no
structural lock here.** The one thing worth carrying forward: as a *maker* the
fee is zero, so a two-sided quoter who happens to be filled on several legs of
the same close holds a partial box — the five legs hedge each other, which is
why the per-close P&L in Table B is far less volatile than a single leg's.

---

## WHAT WOULD MAKE THIS FICTION, AND WHAT THE CHECK SAID

| # | If this were true the result is fiction | What was measured | Verdict |
|---|---|---|---|
| C0 | `period_reward: 200000` is not $20 | Live `GET /incentive_programs`: 345 Coin Race programmes, one per market, 15-min windows, `period_reward` 200000, `target_size_fp` 1000, `discount_factor_bps` 5000. Units confirmed in `FEES_AND_PRODUCTS.md` [DOC]: centi-cents ÷ 10,000 | **holds** |
| C1 | "halving per tick" means only the touch scores | Reference price is a **median 4 ticks below** the touch; median top-of-book 120 vs 200 needed | **the premise was wrong, not the result** |
| C2 | the mid is a fair value, so a negative markout proves informed flow | `E[settle − mid] = −1.006c` overall and swings +16c → −3c across the market's life | **mid is biased; markouts alone prove nothing** |
| C6 | ditto | the five yes mids sum to **median 103.5c**, not 100 | **confirms C2** |
| C3/C7 | the takers time their entry | time-matched placebo −5.72c vs real −4.73c; per-close difference +$0.35, 95% [−0.45, +1.16] | **no timing toxicity** |
| C9 | fills at d=3 > d=2 is a bug | 82/91/65% of levels at d=1/2/3 are **empty**; size clusters at the touch and at d≈4 | **a property of the book** |
| C5 | the queue assumption drives everything | front-of-queue +0.560 c/ctr on 157 ctr/mkt; back-of-queue −1.462 on 17.9 | **queue position selects fill quality — reported as the finding, not hidden** |
| — | the fill engine over-fills below the taker's limit | added the limit-price cap; d=8 net fell from +$5.2/close to +$1.19 | **caught and fixed before reporting** |
| — | one lucky day carries it | d=2 and d=3 are positive on **all four** dates under **both** fill models; d=0 is negative on two of four | **stable at d≥2, not at d=0** |
| — | the arithmetic does not reconcile | by hand: 20 × 0.1207 share × 0.265 qualification = **$0.6397**/market vs simulated **$0.6393** | **reconciles** |

### Self-test, before any real data

`selftest.py`: the LIP scorer and the queue engine on hand-computed books, then
mutation testing.

```
A. LIP SCORER, hand-computed ........................ 10/10 OK
B. MUTATION TEST of the scorer
     no discount at all ............................. KILLED
     reference price = best bid ..................... KILLED
     target 5000 not 1000 ........................... KILLED
     discount 0.90 not 0.50 ......................... KILLED
C. QUEUE / FILL ENGINE, hand-computed ................ 4/4 OK
D. MUTATION TEST of the fill engine
     we always jump the queue ....................... KILLED
     no partial fills ............................... KILLED
     any print past the queue fills us fully ........ KILLED
E. BOOK ARITHMETIC ................................... 4/4 OK
F. score_fast (hot path) == score_side (reference)
     4000 random books: 0 mismatches ................ OK

7 of 7 mutants killed (100%).
```

The trade-side convention was decided **from the data, not the field name** —
getting it backwards flips every markout:

```
taker_book_side='bid' -> printed at the ASK 6,033 times, at the BID 0
taker_book_side='ask' -> printed at the BID 6,271 times, at the ASK 0
```

So `bid` = taker bought yes = **maker was on the NO book**; `ask` = taker sold
yes = **maker was on the YES book**.

---

## WHAT IS STILL UNPRICED, IN ORDER OF HOW MUCH IT COULD COST

1. **ELIGIBILITY IS A HARD GATE AND IT IS NOT A CODING PROBLEM.** LIP requires
   *a verified SSN on file above IRS reporting thresholds*; non-US users,
   Kalshi affiliates, IBs and FCMs are excluded. **If the operator's account
   does not meet this, every number above is zero.** Check this before writing
   a single line of quoting code.
2. **NOBODY HAS EVER SEEN A PAYMENT.** Every live programme reads
   `paid_out: false`. The pool is confirmed to *exist*; it is not confirmed to
   *land in an account*. The cheapest possible verification is one funded
   window at S=5.
3. **THE PRO-RATA MODEL ASSUMES NOBODY REACTS.** At S=50 we are modelled at
   **11.5–12.1% of the paid side**; at S=100, **25–34%**. The 11.5% figure is
   already a material presence and the 34% figure is not credible — other
   makers would re-quote. Sensitivity: at half the modelled share the rebate is
   $141/day (55%/day on capital); at a quarter, $70/day (28%/day). It stays
   positive but stops being remarkable.
4. **Only 26.0% of snapshots qualify** (both sides ≥ 1,000 depth). 74% of the
   pool is never paid to anyone. Our own 50 contracts move that from ~25.0% to
   26.0%; 100 contracts move it to 27.0%. The whole result scales linearly in
   this number and it is a property of *other people's* quoting.
5. **Three days, 251 closes, one market family.** Day-to-day rebate varies
   $2.32–$4.48 per close — competition changes daily.
6. **The requote policy is idealised.** The simulation keeps our order exactly
   *d* ticks behind the touch and rejoins at the back on every move. A real bot
   has latency and would sometimes be stale-and-at-the-touch, which is the bad
   place. Unmeasured.
7. **Two truncated tape hours** (`20260904T07`, `20260906T14`, plus the
   in-progress `20260906T17`) produce incomplete books; **57 markets touching
   them were dropped from every result**, not silently kept.

---

## WHAT I COULD NOT DO

* **No live orders, no funded test.** The account is unfunded and the hard
  constraint stands. Everything here is replay.
* **Could not observe an actual LIP payout.** Requires a funded, eligible
  account and one settled window.
* **Could not measure our own market impact.** Every fill model assumes the
  historical tape is unchanged by our presence. It would not be: at S=50 our
  size is ~40% of a median top-of-book level.
* **Could not test the other LIP families** (`KXDIESELD`, `KXAAAGASD`, table
  tennis, the five commodity 15-minute series). The reference-price finding in
  C1 is the transferable one and should be re-measured on each: it depends
  entirely on top-of-book size versus `target/5`, which differs per family
  (target 300 → only 60 contracts needed).

---

## NEXT STEP

**Ask the operator whether the account is LIP-eligible (verified SSN, US,
not an affiliate/IB/FCM). Nothing else on this idea is worth an hour until
that is answered `yes`.**

If yes, the cheapest next measurement is a **paper-quoting harness**: subscribe
to `orderbook_delta`, maintain the book, compute where our order *would* sit
3 ticks behind the touch, and log every second's reference price, our
multiplier and our modelled share — live, against the real book, with no
orders. That converts model risk #3 (do others react?) into a measurement,
and it needs no funding and no sign-off.

Then, and only with explicit per-instance sign-off: **one window, five coins,
S = 5 contracts, 3 ticks back. Peak capital $25.** That is enough to confirm a
payout lands, which is the one thing no amount of replay can establish.

---

## FILES

| path | what |
|---|---|
| `C:\Users\Joe\AppData\Local\Temp\kals-work\rebate\common.py` | tape reader that survives truncated gz (lip2.py discarded whole files) |
| `...\rebate\extract.py` | distils the series into `tape.csv`, 4.22M rows, merged on `ts_ms` with trades ordered before deltas |
| `...\rebate\replay.py` | two-book model: yes level p = bid p for YES; no level q = offer YES at 100−q |
| `...\rebate\selftest.py` | hand-computed scorer + queue tests, 7 mutants, 4000-book fast/reference agreement |
| `...\rebate\sim.py` | the simulation; four fill policies (`replenish`, `front`, `sweep`, `sweepq`) |
| `...\rebate\diag.py` | decides the trade-side convention from the data |
| `...\rebate\arb.py` | the sum-to-100 structural check |
| `...\rebate\checks.py` | C1 reference price, C2 mid bias, C3 placebo, C4 fill timing, C5 queue bracket |
| `...\rebate\check2.py` | C6 sum of mids, C7 time-matched placebo, C8 bootstrap over closes |
| `...\rebate\check3.py` | C9 level occupancy, C10 peak concurrent capital, C11 implied share |
| `...\rebate\takerpnl.py` | the model-free taker/maker P&L — no simulation in it at all |
| `...\rebate\final.py`, `dist.py`, `report.py` | the tables above |

**Collectors: `kalshi_collector.py` (PID 3381772) and `crypto_feeds.py`
(PID 3385232) were alive before, during and after every heavy job. Free RAM
4.1 GB, free disk 51.9 GB. Nothing was killed.**
