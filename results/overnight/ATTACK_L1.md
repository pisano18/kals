# ATTACK L1 — THE POOL AND THE SHARE

**Adversary 1 of 3. No stake. Default REFUTED when uncertain.**

Everything below was re-derived from primary sources in this session: 177,036
programme records pulled fresh from the authenticated `GET /incentive_programs`,
2,200+ live orderbook samples pulled fresh from `GET /markets/{t}/orderbook`, and
2.5 million orderbook deltas read from the tape. No live orders, no real money.
Read-only authenticated GETs only (`kauth.py` has no order path by construction).

---

## VERDICT IN ONE LINE

**The pool survives. The share survives. The headline number does not — it is
WRONG BY A FACTOR OF ~2.5 IN THE OPERATOR'S FAVOUR, and the whole gap is one
multiplication in `research/lipscore.py`.** The correct rebate, measured on live
exchange books with the tick grid the API actually reports for this series, is
**~$770/day on ~$230 of peak concurrent capital = ~334%/day**, not $282–348/day
and 111%/day. Nothing in Lens 1 kills it. What has to be true for it to be money
is listed in §8, and §9 is the fact that should worry the operator most.

I found six errors. **Five of them are errors in the operator's own favour** —
they make the strategy look better than the brief claims. One (the "2x") was
never a real upside and is now closed. The direction matters more than the size:
a research line that keeps turning up mistakes that flatter it has not been
checked hard enough.

---

## 1. THE POOL — RE-DERIVED, AND THE UNIT IS PINNED

### 1.1 The pull the brief made was truncated by more than half

```
brief:  "80,000 programmes seen, 68,805 paid. $5,051,195 paid over 86.8 days
         = $58,171/day = ~$1.75M/month"

mine:   177,036 unique programmes (89 pages @ limit=2000, zero duplicate ids)
        166,135 with paid_out=true
        $11,106,404 of advertised reward on programmes flagged paid
        span of paid end_dates: 2025-09-25 .. 2026-09-06 = 346.7 days
```

`$5,051,195 / 86.8 days` is a partial numerator over a wrong denominator. The
lifetime rate is **$31,987/day**. The *recent* rate (30 complete days, excluding
the 2-day `paid_out` flag lag) is **$71,166/day = $2.17M/month**. So the
exchange-wide pool is real and about 24% bigger than the brief claims, but the
brief's arithmetic to get there was wrong twice and the two errors partly
cancelled.

Also: 22,275 of the 177,036 programmes are `incentive_type: volume`, not
`liquidity` (no `target_size_fp`, no `discount_factor_bps`). The brief's total
silently mixes the two. Liquidity is 91.8% of lifetime spend.

### 1.2 `period_reward` IS 1e-4 dollars. Now proven, not inferred.

The brief's proof (`KXTRUMPACT 909090 × 11 = $1,000`) is not a proof: it shows
the pool is designed as a round number in *some* unit. `10,000,000 raw` is
equally "round" at $1,000 (1e-4), $100 (1e-5) or $10,000 (1e-3).

The discriminator is the documented range, verbatim from Kalshi's help centre:
*"Daily rewards: $1-$1,000 per market, per day"*. Across the 86,962 liquidity
programmes whose window is ≤24 h (so one programme = one market-day):

| unit | min programme | max programme | below the $1 floor | above the $1,000 cap |
|---|---|---|---|---|
| 1e-3 | $10.00 | $27,450.00 | 0 | **6,405 (7.37%)** |
| **1e-4** | **$1.0000** | **$2,745.00** | **0** | **2 (0.002%)** |
| 1e-5 | $0.10 | $274.50 | 1 | 0 |

Only at **1e-4** do both documented bounds bind exactly. The smallest liquidity
programme on the entire exchange is `period_reward = 10,000` = **exactly $1.00**,
the documented floor; and programmes land on `10,000,000` = **exactly $1,000.00**,
the documented cap (KXBONDIOUT, KXNOEMOUT, KXGOVSHUTLENGTH, KXINSURRECTION). At
1e-5 nothing ever reaches the cap and the floor is breached; at 1e-3 the cap is
breached 6,405 times. **VERIFIED: Coin Race = $20.00 per coin per 15-minute
window.**

Corroborating: `KXTRUMPENDORSEMENTS` runs 6 markets at `1,666,666` each =
`9,999,996` = **$999.9996** — `floor(10,000,000/6)` per market. The design target
is a round $1,000 in units of $0.0001.

### 1.3 Coin Race, re-measured

```
6,385 KXCRYPTOLEAD15M programmes, ALL of them:
   incentive_type  liquidity     incentive_description  series_lip
   period_reward   200000 ($20)  target_size_fp         1000.00
   discount_factor 5000 (0.50)   window length          900 s (6,380 of 6,385)

day        n   paid    pct   advertised   flagged-paid
2026-08-25 480  475   99.0%      $9,600         $9,500
2026-08-26 480  480  100.0%      $9,600         $9,600
2026-08-28 480  470   97.9%      $9,600         $9,400
2026-08-30 480  480  100.0%      $9,600         $9,600
2026-09-01 480  480  100.0%      $9,600         $9,600
2026-09-04 480  480  100.0%      $9,600         $9,600
2026-09-05 480  210   43.8%      $9,600         $4,200   <- flag lag
2026-09-06 480   30    6.2%      $9,600           $600   <- flag lag
```

11 full days: **$9,600/day advertised, $8,222/day flagged paid (85.6%)**, and the
shortfall is entirely the 1–2 day lag on the flag; steady state is 97.5–100%.
Close to the brief's $9,477 / $8,294. **The pool claim survives.**

### VERBATIM DISAGREEMENT — 1

> Brief: *"80,000 programmes seen, 68,805 paid. $5,051,195 paid over 86.8 days
> = $58,171/day = ~$1.75M/month across all families."*

Wrong on every number, from a truncated pull. Correct: **177,036 programmes,
166,135 paid, $11,106,404 over 346.7 days = $31,987/day lifetime; $71,166/day =
$2.17M/month over the last 30 days.**

### 1.4 THE THING NOBODY PRICED: the programme is thirteen days old

`KXCRYPTOLEAD15M`'s first LIP programme starts **2026-08-24T16:46:35Z**. There
are 6,385 programmes = **13.3 days** of history, and Coin Race alone is
**13.5% of the entire exchange's daily liquidity-incentive spend**
($9,600 of $71,166). The help centre says *"Kalshi can end or modify the program
at any time"*. A strategy whose entire P&L is this rebate is a bet on a 13-day-old,
highly concentrated line item. That is not a modelling risk; it is the risk.

---

## 2. THE 2x IS DEAD. IT WAS NEVER THERE.

The brief calls this "UNRESOLVED" and says *"if 'plus' is literal every figure
DOUBLES. Nobody has settled this."* It is settled, from the same help-centre page
the rest of the rules were quoted from, and it settles **against** the upside.

Verbatim, Steps 3 and 4:

> *"Both sides count separately. Your snapshot score is your share of the yes
> side **plus** your share of the no side, so a single snapshot is worth **at
> most 2.0 across all participants**"*
>
> *"Your Time Period score = your total snapshot scores **÷ all participants'
> total snapshot scores**"*
>
> *"Your reward = Your Time Period Score × Time Period Reward × (non-excluded
> snapshots ÷ total snapshots), rounded down to the nearest cent"*

The "plus" is literal — and it cancels. Per snapshot, shares sum to 1.0 on the
yes side and 1.0 on the no side, so *"all participants' total snapshot scores"* =
**2.0 per non-excluded snapshot**, which the page states outright. Therefore

```
TimePeriodScore = Σ_t (s_yes + s_no) / (2 · N_qualifying)
reward          = TimePeriodScore · R · (N_qualifying / N_total)
                = R · mean over ALL snapshots of (s_yes + s_no)/2
```

which is **exactly the average-of-sides implementation**. It is not
"conservative". It is right. Verified numerically in `selftest.py`
(Nq=600, Nt=900, sy=0.10, sn=0.14 → $1.6000 both ways). Kalshi's own worked
example confirms the shape: *"If your share of the Time Period score is 20%, you
would earn 20% × $100 × (8,000 ÷ 10,000) = $16.00"* — a share, normalised to 1
across participants.

### VERBATIM DISAGREEMENT — 2

> Brief: *"UNRESOLVED 2x: 'Your snapshot score is your share of the yes side PLUS
> your share of the no side.' We implement the AVERAGE (conservative). If 'plus'
> is literal every figure DOUBLES. Nobody has settled this."*

**Settled: it does not double, ever.** The doubling in Step 3 is divided back out
by the Step-4 normalisation, and Kalshi says so in the same sentence ("at most
2.0 across all participants"). Delete the 2x from every future report. The only
remaining place a >1x can hide is different, and is §8.5.

---

## 3. THE ERROR THAT PRODUCED THE HEADLINE: a 0.289 where ~0.71 belongs

`research/lipscore.py`, last lines, verbatim:

```python
print(f"    AFTER the 28.9% haircut:   flat ${POOL*mf*96*5*0.289:,.0f}   "
      f"tapered ${POOL*mt*96*5*0.289:,.0f}")
```

It **multiplies by 0.289** and calls it a "28.9% haircut". A 28.9% haircut is a
multiplication by 0.711. The line is only arithmetically right if 28.9% is the
fraction of snapshots that DO qualify — and `HANDOFF.md:429` says exactly that
(`snapshots qualifying (both sides >= 1000)  80,047 of 276,600 = 28.9%`). So the
code is consistent with a *measurement*, and the measurement is the thing that is
wrong (§6). But the word "haircut" is the opposite of the arithmetic, and that
word is what propagated into the brief.

This single line is the whole gap between the two reports on the operator's desk:

```
lipscore.py "after the 28.9% haircut", tapered      $377/day   <- the brief's $282-348
the same model, 28.9% read as a haircut (x0.711)    $928/day
the Reality job's tape measurement                  $838/day
```

`$377 / 0.289 × 0.711 = $927`. **The brief and the Reality job are the same
calculation with opposite readings of one number.** Neither is an independent
confirmation of the other, and the operator should stop treating them as two
sources.

---

## 4. THE TICK GRID: the brief uses the wrong one, and it flatters us

The brief: *"mean 12.55% using the TAPERED tick (0.1c below 10c and above 90c —
engine.tick_at)"*.

`engine.py:235` is

```python
def tick_at(p):
    return 0.001 if (p > 0.90 or p < 0.10) else 0.01
```

— a hard-coded taper with no series argument. But the API reports the grid per
series, and for this series it is **flat**:

```
GET /markets?series_ticker=KXCRYPTOLEAD15M   (all five open markets, 2026-09-06)
  price_level_structure : "linear_cent"
  price_ranges          : [{start "0.0000", end "1.0000", step "0.0100"}]
```

`lipscore.py`'s own comment block says this, and says the taper *"inflated our
modelled share from 11.31% to 12.55% — an error in our own favour, which is the
direction that matters."* The brief quotes the 12.55% anyway. Note also that
`lipscore.py`'s **top docstring contradicts its own comment block** — the
docstring calls the tapered tick "correct" and the flat one "conservative but
wrong"; the comment 20 lines below says the reverse and is the one that matches
the API. The docstring is stale and should be deleted before it misleads again.

Measured on today's live books (`lipscore.py` run at 20:11 UTC):
**flat 12.12%, tapered 13.58% — the wrong grid adds 12%.**

Why it flatters us: the taper turns a 1-cent gap into 10 ticks, so the enormous
1-cent junk levels get `0.5^10 = 0.001` instead of `0.5^1 = 0.5`. That shrinks
the denominator most on the *dead* coins — exactly the legs where our share is
worst. In today's pull ETH/yes scored 2,747 flat but 1,249 tapered, and the share
went 1.8% → 3.8%. **The wrong grid doubles our number precisely where the truth
is worst.**

### VERBATIM DISAGREEMENT — 3

> Brief: *"Share at S=50 measured 4.2%–18.3% across ten live sides, mean 12.55%
> using the TAPERED tick (0.1c below 10c and above 90c — engine.tick_at). A
> flat-1c-tick implementation understates our share; that bug is fixed in
> research/lipscore.py."*

Backwards for this series. **KXCRYPTOLEAD15M is `linear_cent`.** The flat
implementation is the correct one here and the tapered one **overstates** our
share by ~12%. The "fix" applies to the crypto up/down series
(`tapered_deci_cent`), not to Coin Race, and `lipscore.py` says so itself.

---

## 5. THE SHARE — ATTACKED THREE WAYS, AND IT HOLDS

### 5.1 Reference-price walk on the NO book — CORRECT, checked

The rule is *"walking down from the best bid"*. The API's `no_dollars` array is a
**bid book in no-price terms**: at 19:45 today `no_bid_dollars 0.86` alongside
`yes_ask_dollars 0.14` (= 1 − 0.86). Sorting the no array descending therefore
starts at the best NO bid — the level nearest the money — and walks away from it,
the same direction as walking down the yes bids. `lipscore.score_side` does
`sorted(..., reverse=True)` on the raw array for both sides. **No sign error, no
side error.** There is no alternative reading: the no side contains no yes-bids
to walk down.

`ref = first level where cumulative size ≥ Target/5 = 200` is also implemented
correctly (`if cum >= TARGET / 5.0`), and `TARGET = 1000` matches
`target_size_fp = "1000.00"` from the API for all 6,385 Coin Race programmes.

One real defect in `lipscore.py`: it computes the share as `50.0 / (a + 50.0)`,
i.e. it never gives our order a **price**, and so implicitly assigns it a 1.0
multiplier. That happens to be right for postures at or above the reference price
(which touch−3c usually is, §5.3) and wrong for anything deeper. It is not
modelling "3 ticks behind the touch"; it is modelling "at or better than the
reference price".

### 5.2 The mechanism, hand-reconciled on one real book

The reason 50 lots can take a tenth of a side is not subtle and is not an
artefact. Live XRP yes book, 20:11:04 UTC, verbatim from the API:

```
 0.81  size  117.51   cum   117.51
 0.77  size  120.00   cum   237.51   <== REFERENCE PRICE (cum >= 1000/5 = 200)
 0.73  size  120.00   cum   357.51
 0.69  size  120.00   ... a 4-cent ladder, 120 lots a rung, 16 rungs
 0.01  size 1002.00   cum  2920.51

score:  0.81 -> 117.510  (>= ref, x1)
        0.77 -> 120.000  (== ref, x1)
        0.73 ->   7.500  (4 ticks below ref, x0.0625)
        0.69 ->   0.469  (8 ticks)
        0.64 ->   0.015  (13 ticks)
        rest ->   ~0
        TOTAL SIDE SCORE = 245.494

our 50 lots at 0.78 (= touch - 3c) is ABOVE the 0.77 reference -> x1.0 -> 50.0
SHARE = 50.00 / (245.494 + 50.00) = 16.92%
```

Hand-computed and machine-computed agree to six decimals. **The whole side scores
245 because the incumbent quotes 4-cent rungs and `0.5^4 = 0.0625` annihilates
everything below the second rung.** Our order three cents back is still at or
above the reference price, so it takes full credit against a denominator only 5×
its own size. The share is real — and it is a property of *the incumbent's rung
spacing*, not of the rule. §8.1 prices what happens when that changes.

### 5.3 Live measurement — real orderbooks, no reconstruction anywhere

`GET /markets/{t}/orderbook?depth=100` every ~5 s across all five open Coin Race
markets, 20:00–20:45 UTC 2026-09-06, 2,101 in-window market-instants.

```
depth per side          yes med 4,448 [p05 2,923, p95 13,256]
                        no  med 6,073 [p05 3,105, p95  6,397]
best-bid -> REFERENCE gap, in ticks
                        yes mean 3.47  med 4  p10 1  p90 5   (>= 3 in 77.4%)
                        no  mean 3.93  med 4  p10 3  p90 5   (>= 3 in 97.7%)
```

**The median reference price sits four ticks below the touch.** That is the
measured reason "3 ticks back keeps 93% of the rebate" is true — I measure
**98%** — and it is why the cliff is one tick further out, not here:

| posture | mean share | $/leg-window | $/day (480) |
|---|---|---|---|
| touch (back 0) | 9.456% | $2.0919 | $1,004 |
| touch − 1c | 9.406% | $2.0829 | $1,000 |
| touch − 2c | 9.374% | $2.0770 | $997 |
| **touch − 3c** | **9.337%** | **$2.0684** | **$993** |
| touch − 4c | 8.583% | $1.8937 | $909 |

(These live figures already contain the qualification haircut and cover
20:00–20:45 UTC only — the strongest hours of the day. §6.4 and §7 correct to a
full day.)

**Infeasibility, unpriced anywhere else:** on **20% of yes-side samples the best
bid is ≤ 3 cents**, so "3 ticks behind the touch" is below the $0.01 minimum price
and the posture degenerates to resting at 1c. On the dead coins the yes book
collapses to 1–2 cents where thousands of contracts sit and 50 lots take 1.8% of
the side, not 12%. Any live implementation needs an explicit rule for this; the
brief has none.

---

## 6. THE NUMBER EVERYTHING HINGES ON IS THE QUALIFICATION RATE, AND EVERY TAPE MEASUREMENT OF IT IS UNSOUND

`reward = R × qualifying_fraction × share|qualifying`. The share is stable
(11–12% on both tape days and on live books). The qualifying fraction is where
the reports disagree by 3.4×, and I found out why.

### 6.1 The tape is blind to the first ~45 seconds of every Coin Race window

Measured against the API's own `open_time` for six random markets:

```
KXCRYPTOLEAD15M-26SEP042315-SOL   open 03:00:00Z   first delta +43.021 s
KXCRYPTOLEAD15M-26SEP051030-ETH   open 14:15:00Z   first delta +60.528 s
KXCRYPTOLEAD15M-26SEP051730-SOL   open 21:15:00Z   first delta +39.195 s
KXCRYPTOLEAD15M-26SEP051630-BTC   open 20:15:00Z   first delta +42.860 s
KXCRYPTOLEAD15M-26SEP051530-ETH   open 19:15:00Z   first delta +43.316 s
KXCRYPTOLEAD15M-26SEP042130-HYPE  open 01:15:00Z   first delta +68.228 s
```

The collector discovers each new market ~45 s after it opens, and the snapshot it
gets on subscribe carries **no level arrays at all** — 0 of 1,440 Coin Race
snapshots in a full day have any `yes`/`no` key, only `market_ticker` and
`market_id`. The book that already exists at +45 s is therefore invisible
forever. The symptom is unmistakable: replaying a full day of deltas drives the
book negative **11,941 times across all 485 markets — every single one — for
3,014,142 contracts of unexplained cancellation.**

I corrected this the standard way (a level's unseen initial size = the maximum
deficit its running sum ever reaches) and then **measured the residual against the
live API for the same market at the same instant**, 420 side-instants,
20:00–20:05 UTC:

| | live depth (med) | reconstructed | ratio med | p10 | p90 |
|---|---|---|---|---|---|
| yes, raw | 4,274 | 2,178 | **0.514** | 0.482 | 0.603 |
| yes, floor-corrected | 4,274 | 2,251 | **0.529** | 0.514 | 0.625 |
| no, raw | 6,073 | 3,720 | **0.613** | 0.558 | 0.786 |
| no, floor-corrected | 6,073 | 3,960 | **0.652** | 0.574 | 0.800 |

**A tape-only Coin Race book is missing 35–47% of the resting depth, and the
floor correction recovers almost none of it**, because the missing orders are
placed before the collector joins and are never cancelled inside the window. This
is a first-order defect in every tape-based Coin Race book measurement anyone has
made, mine included.

### 6.2 …but it barely biases the SHARE, and I checked that too

My first reaction was that a half-size denominator doubles the modelled share.
That would have been a clean kill of every tape number. **It is not what
happens.** Locating the missing mass by distance from the touch:

```
missing size by ticks below the live best bid
   0 ticks    122,928   5.4%
   1 tick     135,758   6.0%
   2-5 ticks  299,702  13.2%
   6-14 ticks 232,024  10.2%
  >=15 ticks 1,482,523 65.2%   <- the 1-cent junk; multiplier 0.5^15 = 3e-5
```

Two-thirds of what the tape misses is deep junk that scores nothing. The
consequence for the number that matters:

```
SHARE RATIO recon/live at back=3, S=50  (n = 1,160 side-instants)
   median 1.002    p10 1.000    p90 2.383    mean 1.266
```

**The tape's share is unbiased at the median and overstates by ~27% on average**,
with a fat right tail. So the share survives the tape; the *qualification test*
does not, because it is a hard 1,000-contract threshold on total depth, and a
book measured at half its true size fails a threshold test far more often than it
should. **That is why 28.9% is wrong — and why my own floor-corrected tape figure
of 61.3% is also wrong.**

### 6.3 Live qualification, and the structure nobody has reported

Live, 2,101 in-window market-instants:

| decile of the 15-minute window | qualifying |
|---|---|
| 0–9% | 100.0% |
| 10–19% | 100.0% |
| 20–29% | 100.0% |
| 30–39% | 100.0% |
| 40–49% | 100.0% |
| 50–59% | 100.0% |
| 60–69% | 99.4% |
| **70–79%** | **62.4%** |
| **80–89%** | **13.4%** |
| **90–99%** | **0.0%** |

**Pooled: 80.9%.** The Coin Race book is fully qualified for the first eleven
minutes and then dies. **In the last 90 seconds of every window, on live exchange
books, not one snapshot qualified.** That is not a reconstruction artefact — it is
market makers pulling before the race resolves, and it costs ~19% of the pool on
its own. The tape's decile profile has the same shape (81% → 6% across the
window), so both sources agree on the shape and differ only on the level.

### VERBATIM DISAGREEMENT — 4

> `HANDOFF.md:429`: *"snapshots qualifying (both sides >= 1000) 80,047 of 276,600
> = 28.9%"*, and `results/OVERNIGHT.md:52`: *"snapshots qualifying **28.9%** (71%
> of the pool is never paid to anyone)"*.

**Refuted, by a mechanism rather than a re-count.** 28.9% is what you measure when
your book is missing 35–47% of its depth and you then apply a hard threshold at
1,000 contracts. Live, the figure is **80.9%** in the hours I sampled. The
parenthetical is wrong for a second, independent reason: an excluded snapshot
shrinks what Kalshi disburses, it does not mean 71% of the pool "is never paid to
anyone" — the pool that is paid is shared among whoever is resting.

> `results/overnight/IMPACT.md:48`: *"the brief assumes 28.9%, I measure 74.16%"*

Closer, and directionally right, but also from the tape and therefore also
unsound at the level. My live number is 80.9% for 20:00–20:45 UTC; corrected to a
full 24-hour day (§6.4) it is ~67–78%.

### 6.4 The day shape — the live poll covers the best 45 minutes of the day

The tape's *level* is unsound but its *shape* is not, and the shape is large:

```
tape 2026-09-05, share|qualifying by UTC hour:  11.1% - 14.3%   (flat)
tape 2026-09-05, qualification by UTC hour:     45% (05h) - 76% (23h)
   00-14 UTC mean 53%      15-23 UTC mean 74%
tape 2026-09-04 (18 h): qualification 71.5%, share|qualifying 11.8%
tape 2026-09-05 (24 h): qualification 61.3%, share|qualifying 12.3%
```

Qualification in the quiet hours is ~0.72× the afternoon. Scaling my live 80.9%
by the tape's own day/afternoon ratio gives a **full-day qualification of
67–78%**.

---

## 7. THE HEADLINE, RE-DERIVED

```
$/day  =  $20 pool  x  480 leg-windows/day  x  qualification  x  share|qualifying
```

Full-day estimate: the tape's per-leg-window *shape* for two complete days,
rescaled so its 20:00–22:00 UTC hours match the live measurement (factor 1.060
for 09-05, 1.103 for 09-04).

| | 2026-09-05 (24 h) | 2026-09-04 (18 h, 06–24 UTC) |
|---|---|---|
| **$/day** | **$769.00** | **$893.28** |
| $/leg-window mean | $1.6021 | $1.8610 |
| p01 | $0.0000 | $0.0000 |
| **p05** | **$0.0019** | **$0.8506** |
| p10 | $0.1251 | $1.0366 |
| p25 | $1.0156 | $1.3054 |
| median | $1.6579 | $1.7727 |
| p75 | $2.2798 | $2.4817 |
| p95 | $2.9450 | $3.0501 |
| max | $3.2850 | $3.4641 |
| leg-windows paying < 1 cent | **6.4%** | 2.7% |
| leg-windows paying < $1.00 | **24.3%** | 9.3% |
| by coin ($/leg-window) | BTC 1.55 ETH 1.25 HYPE 1.90 SOL 1.57 XRP 1.75 | BTC 1.75 ETH 1.70 HYPE 2.14 SOL 1.77 XRP 1.95 |

09-04 is missing the thin 00:00–06:00 hours, so it is the optimistic end of the
range; 09-05 is a complete UTC day and is the number I would use.

**Peak concurrent capital, measured on live books** — 50 lots a side, 3 ticks
behind the touch, all five legs at the same instant (163 instants where all five
were sampled together):

```
median $213.00    p05 $208.00    p95 $225.50    MAX $230.50
```

Independently reproduces the Reality job's $230.50, and sits a little below the
brief's $254.

### THE NUMBERS, AS ASKED

```
$/CONTRACT/DAY      $769 / 500 resting contracts (50 x 2 sides x 5 legs)
                    = $1.538 per resting contract per day
PEAK CONCURRENT     $230.50 max, $225.50 p95, $213.00 median
% RETURN            $769 / $230.50 = 334%/day
                    plausible range $620 - $970/day = 269% - 421%/day
FULL DISTRIBUTION   per leg-window (n=485, one full UTC day):
                    p01 $0.000 | p05 $0.002 | p10 $0.125 | p25 $1.016
                    | med $1.658 | p75 $2.280 | p95 $2.945 | max $3.285
                    6.4% of leg-windows pay under one cent
                    day-to-day: $769.00 and $893.28 (2 days; 09-04 is 18 h)
```

Sensitivity, because the honest answer is a rectangle, not a point:

```
             qualification ->  29%     50%     61%     72%     81%     99%
share 10.76% (live, back=3)    $299    $516    $633    $739    $833  $1,027
share 12.12% (lipscore flat)   $336    $582    $713    $832    $938  $1,157
share 12.55% (the brief)       $348    $602    $739    $861    $971  $1,198
```

The brief's $348 sits in the bottom-left corner — the corner where **both** inputs
are wrong in the same direction.

### VERBATIM DISAGREEMENT — 5

> The claim under attack: *"~$282–348/day of REBATE on ~$254 of peak concurrent
> capital = ~111%/day."*

**Refuted as too LOW, by 2.2–2.8×.** The rebate is ~$770/day (range $620–$970) on
$230.50 of peak capital = ~334%/day. The operator's instinct that the number
"looks insane" is right — and it is worse than the number he was shown. **Lens 1
does not contain the thing that makes it sane.**

---

## 8. WHAT WOULD STILL HAVE TO BE TRUE

I could not kill it inside Lens 1. This is the exhaustive list of what has to
hold, each with what I measured.

**8.1 The incumbent must keep quoting 4-cent rungs. MEASURED — and this is the
single biggest fragility.** The entire edge is that the reference price sits four
ticks below the touch, so an order three ticks back still earns a 1.0 multiplier.
Counterfactual on the same live books with the reference price forced to the best
bid (what happens if the incumbent tightens to 1-cent rungs, or if Kalshi raises
Target Size so 200 contracts is reached at the touch):

| posture | share, ref 4 ticks down | share, ref AT the touch | $/day |
|---|---|---|---|
| back = 0 | 9.456% | 20.162% | $1,004 → $2,177 |
| **back = 3** | **9.337%** | **3.829%** | **$993 → $418** |
| back = 4 | 8.583% | 2.118% | $909 → $230 |

**At touch − 3c the rebate falls 58% if the reference price moves to the touch.**
The posture is not robust; it is tuned to one competitor's current
parameterisation. Standing at the touch is robust — it gets *better* — but that
is the posture the fill analysis rejected. Anyone deploying this must monitor the
best-bid-to-reference gap every window and re-peg on it, not on the touch.

**8.2 The `$1.00` minimum payout must not apply per market-window. MEASURED.**
Verbatim: *"Minimum payout: $1.00 (rounded down to nearest cent)."* If that is a
per-time-period minimum — and a Coin Race time period *is* one 15-minute market —
then **24.3% of leg-windows (09-05) pay zero instead of their computed value**
and $769/day becomes **$721/day**; on 09-04, 9.3% and $893 → $868. Small, but a
real unpriced haircut that nobody has mentioned.

**8.3 The public orderbook must be the book Kalshi scores.** Untestable from
outside. The exchange's own `yes_bid_size_fp` on `/markets` matches the top of
`orderbook_fp` exactly where I could compare (ETH 0.07 / 15.00 on both), so there
is no evidence of hidden size — but absence of evidence is all I have.

**8.4 "Kalshi scores every resting order that helps reach the Target Size on its
side" must not mean a hard cut at Target Size. MEASURED, AND IT IS BENIGN.** I
implemented the restrictive reading — only the top 1,000 contracts walking down
from the best bid earn credit, anything deeper earns zero — and it **helps**:
share 9.79% vs 9.34%, $1,044/day vs $993/day, because our order at touch−3c is
inside the top 1,000 while the junk that inflates the denominator is not. This was
my best candidate for a clean kill and it died. (In a synthetic book with a thick
near-touch ladder the same reading takes our share to **zero** — see
`selftest.py` — so it is benign *given the current book shape*, which is 8.1
again.)

**8.5 "all participants' total snapshot scores" must mean everyone.** If the
120-lot ladder belongs to a designated market maker excluded from the LIP (the
filed Eligible Participants clause excludes *"members with a Market Maker
Agreement"*), the Step-4 denominator might be *eligible* participants only, and
our share would renormalise **upwards**, possibly several-fold. This is the only
remaining place a >1x can hide. I took the conservative reading throughout. It
cannot be settled from outside the exchange — only by posting a small order and
reading the credit that arrives.

**8.6 The programme must survive.** 13.3 days old, 13.5% of exchange-wide
liquidity-incentive spend, terminable at will.

---

## 9. THE FACT THAT SHOULD WORRY THE OPERATOR MOST, AND IT IS NOT AN ARITHMETIC ERROR

I measured the **total resting capital of the entire Coin Race book** — every
resting order from every participant, all five legs, both sides, at one instant
(163 instants where all five legs were sampled together):

```
whole book, five legs, one instant:  median $5,812   p05 $5,546   p95 $6,776   max $7,352
of which levels at <= 2c ("junk"):   6.1% of that capital
our proposed posture:                median   $213                            max   $230
```

**Everyone in the Coin Race book put together has about $5,800 of capital resting
against a pool of $9,600 per day.** If the rebate is what my own arithmetic says,
that book is earning ~165%/day on committed capital, in public, on an exchange
anyone can join, in a programme that has been running for thirteen days. It is not
100× deeper. Three explanations, and only one is good for us:

1. **The main liquidity provider is ineligible for the LIP** (§8.5). Then the pool
   is under-claimed and the strategy is better than modelled.
2. **Fills and inventory eat the rebate.** The book is 120 lots a rung because
   that is the inventory the incumbent is willing to hold, not because it is
   rebate-optimal. This is criticisms B and C, and it is the explanation I would
   bet on.
3. **The payout is not what the help centre describes.**

I cannot distinguish these from outside. **Nothing in Lens 1 — not the pool, not
the unit, not the share, not the reference-price walk, not the tick grid —
explains why $5,800 of visible capital is leaving a 165%/day return on the
table.** The explanation is in the two lenses I was not given, or in a $1 live
test.

---

## 10. SELF-TEST AND ARTEFACT CHECKS

Before touching real data the scorer was checked against a hand-computed
synthetic book (`selftest.py`; every assertion passes):

```
book {0.50:150, 0.49:100, 0.48:800, 0.10:5000}, target 1000, discount 0.5
  HAND: ref = 0.49 (cum 150, then 250 >= 200)
        score = 150 + 100 + 800(0.5) + 5000(0.5^39) = 650.0000000
        our 50 at 0.47 = 2 ticks under ref -> 12.5 ; share 12.5/662.5 = 1.886792%
  CODE: ref 0.49  total 662.5000000  ours 12.5  share 1.886792%          PASS
  cap reading       HAND 625.0 / share 0        CODE 625.000000 / 0      PASS
  ref-at-touch      HAND 406.25 / 1.538462%     CODE 406.250000 / 1.538462%  PASS
  payout identity   TimePeriodScore x R x Nq/Nt == R x mean[(sy+sn)/2]   MATCH
```

Artefact checks run against my own results. **Three of them changed the answer.**

1. **"The tape's denominator is half-size, so every tape share is 2× too high"** —
   would have been a clean kill of every tape-based number in the project.
   **Checked and REJECTED**: the missing mass is 65% deep junk, and the measured
   recon/live share ratio is 1.002 at the median (mean 1.266). I dropped the
   claim rather than report it.
2. **"The end-of-window collapse is an artefact of my own floor correction"** —
   mechanically plausible, because a level whose true initial size exceeds my
   recovered initial size clips to zero early and stays there. **Checked against
   live books and CONFIRMED REAL**: 0.0% of *live* snapshots qualify in the last
   90 seconds of a window.
3. **`depth=200` on the orderbook endpoint returns HTTP 400**, and my helper
   parsed the error body into an empty book — silently producing five markets
   with "zero depth" and halving a share estimate. Caught by noticing
   `live_depth 0` against a tape that plainly had orders. **Max depth is 100.**
4. **"Polled markets that returned empty books are thin markets"** — no, they were
   markets past their close time still listed as `status: active`. Fixed by
   filtering every sample to `[open_time, close_time)`.
5. **"12.55% is a static-snapshot artefact"** — the criticism I was sent to test.
   **REJECTED**: across 2,100+ live orderbooks spanning three windows the
   share|qualifying is 11.5%, and across two full days of tape it is 11.8% and
   12.3%. It is not one lucky snapshot.
6. One tape file, `orderbook_delta/20260904T07.jsonl.gz`, is **corrupt**
   (`zlib.error: Error -3 while decompressing data: invalid block type`) after
   1,751,501 lines. The 09-04 day is therefore 18 hours, not 24, and is reported
   as such rather than silently patched.

---

## 11. WHAT I COULD NOT DO

* **I could not settle §8.5** — whether the Step-4 denominator includes
  ineligible participants. It is the only remaining multiplier and it can only go
  our way. It needs one small live order and a look at the credit.
* **I could not measure a full day of LIVE books.** My live sample is 45 minutes
  of a Sunday afternoon. Every full-day figure in §7 is a tape *shape* rescaled to
  a live *level*, and the rescaling factor (1.06–1.10) is itself measured on two
  hours.
* **I could not verify that `paid_out: true` means the full `period_reward` was
  disbursed.** The API exposes no paid amount. Every "$X paid" figure in this
  report and in the brief is *advertised reward on programmes flagged paid*; the
  actual disbursement is at most that and is scaled by the qualifying fraction.
  This is a genuine hole in everybody's evidence, mine included.
* **I could not test criticisms A, B or C.** Not my lens. §9 argues that B and C
  are where the answer lives.

---

## 12. NEXT STEP — ONE THING, CHEAP, DECISIVE

Post **one contract** — not fifty — on one side of one Coin Race market, three
ticks behind the touch, for one 15-minute window, **with the operator's explicit
per-instance sign-off**. Worst case: about $0.99 of capital at risk plus fees.

What it settles that nothing else can:

* whether the credit arrives at all, and in what form;
* §8.5 — divide the credit received by $20 and compare with the modelled share;
* §8.2 — whether a sub-$1 window pays anything;
* §8.3 — whether the scored book is the published book.

One dollar buys the answer to the three questions that a tape, an API and a month
of analysis cannot.

**Second, free, and it should happen anyway:** fix the collector's ~45-second
market-discovery lag on 15-minute series, or persist the level arrays from the
subscribe snapshot. Until that is fixed, no tape-based Coin Race book measurement
in this project can be trusted at the level — only at the shape.

---

### ARTEFACTS

```
C:\Users\Joe\AppData\Local\Temp\kals-work\atkL1\pull.py         full paginated /incentive_programs pull
C:\Users\Joe\AppData\Local\Temp\kals-work\atkL1\progs.jsonl     177,036 programme records
C:\Users\Joe\AppData\Local\Temp\kals-work\atkL1\unit.py         the 1e-4 unit proof
C:\Users\Joe\AppData\Local\Temp\kals-work\atkL1\unit2.py        floor/cap test on <=24h windows
C:\Users\Joe\AppData\Local\Temp\kals-work\atkL1\pool.py         Coin Race daily pool
C:\Users\Joe\AppData\Local\Temp\kals-work\atkL1\poll.py         live orderbook poller (GET only)
C:\Users\Joe\AppData\Local\Temp\kals-work\atkL1\livepoll.jsonl  live orderbook samples
C:\Users\Joe\AppData\Local\Temp\kals-work\atkL1\livepoll2.jsonl live orderbook samples
C:\Users\Joe\AppData\Local\Temp\kals-work\atkL1\final.py        live LIP scorer, four rule readings
C:\Users\Joe\AppData\Local\Temp\kals-work\atkL1\selftest.py     hand-checked self-test (passes)
C:\Users\Joe\AppData\Local\Temp\kals-work\atkL1\calib.py        tape vs live depth calibration
C:\Users\Joe\AppData\Local\Temp\kals-work\atkL1\calib2.py       where the missing mass sits; share ratio
C:\Users\Joe\AppData\Local\Temp\kals-work\atkL1\qualprofile.py  qualification by decile / hour / coin
C:\Users\Joe\AppData\Local\Temp\kals-work\atkL1\dist.py         calibrated full-day distribution
C:\Users\Joe\AppData\Local\Temp\kals-work\atkL1\sens.py         the sensitivity rectangle
C:\Users\Joe\AppData\Local\Temp\kals-work\atkL1\byhour.py       day-shape of share and qualification
```

Collectors verified alive after every heavy job: `kalshi_collector.py` (PID
3381772) and `crypto_feeds.py` (PID 3385232) were both running at the end of this
job. Free disk 51 GB (well above the 6 GB floor).
