# RESULTS_coin — does the run of SOL losses mean anything?

Asked by the operator 2026-09-12: *"the last three losses have been SOL, does
that mean anything?"* Produced by `research/pincoin.py`, whose `--selftest`
(43 checks, all green) gates every number below and refuses real data if any
check fails.

```
python research/pincoin.py --days 9 --split 5      # sections 1-7
python research/pincoin.py --scale-only --days 9   # section 5 alone
python research/pincoin.py --live-only             # sections 4 and 7 alone
python research/pincoin.py --selftest
```

Tape window: closes 2026-09-03T04:45Z .. 2026-09-12T04:45Z — 211 hours,
6,673,899 coin-seconds, 7,632 settled markets over 826 closes, 7,266 gate
entries over 808 closes. Live window: our own 198 settled gate fills over 195
closes, 2026-09-08T08:00Z .. 2026-09-12T13:00Z. The live sections grow every
day the bot runs; these numbers are as of that last close.

---

## VERDICT

**Probably not, and certainly not enough to act on — but SOL is the one coin
where I would not close the question.** At the current 0.995 gate SOL is **3
losing closes of 14 (21.4%, CI [4.7%, 50.8%])** while the other eight coins
are 1 of 101 between them. Taken alone that is a hypergeometric p of 0.0055.
Taken honestly — as *the worst of nine coins we went looking through*, scored
by re-dealing the losses at random while holding each coin's close count fixed
and using the worst coin's count as the statistic — it is **p = 0.060**. Over
all live runs, including the older 0.98 gate, it is **p = 0.333**. So: short of
significance on the only test that pays for the search, and the MDE says only
a coin running **4–6× the pool rate** was ever detectable here. This will not
resolve by staring at it; at ~25 bets/day it needs weeks.

**Two counting corrections came out of this, and both moved the answer more
than any coin effect did.**

1. **Three of the "NEAR losses" are three fills on ONE market.**
   `KXNEAR15M-26SEP082045-45`, paid 96.2c / 95.6c / 73.0c — one close, one
   settlement, one outcome. Clustered by close as hard rule 4 requires, NEAR is
   **1 of 18 overall and 0 of 10 at the current gate**, not 3 of 18. It was
   never the second-worst coin.
2. **Two of the "losses" were not bets the gate made.** Mid-session the live
   log grew a 1-contract ETH fill at 0.3c and a 1-contract SOL fill at 5.2c,
   and SOL went to 4-of-15 with the worst-of-nine p-value crossing 0.05 to
   **0.0285**. Both are `kind: "plant"` records — deliberate near-zero-price
   probes from another session's live hedge test (`results/PREREG_hedge.md`),
   each followed immediately by `hedge_alarm` with belief 0.000 and 0.020. They
   exist *to lose*. `load_live()` now drops plants and hedge legs by name and
   prints what it dropped; section 7, which requires a signal followed by a
   filled order, excludes them independently, and the two close counts agree at
   195. **A p-value that crosses 0.05 on two contracts bought to lose is the
   whole reason a bar has to be pre-registered rather than read off a moving
   sample.**

**On money the asymmetry is starker than on counts, and it deserves saying
plainly: at the current gate SOL is the only coin losing money.** Clustered by
close, plants and hedge legs excluded: SOL **−$38.39 over 14 closes
(−$2.74/close)**; all eight other coins positive, +$67 between them; the run
nets +$28.87. But that −$38 is *three events*, one of which is −$19.61 on its
own, and on the all-runs window the worst coin on money is NEAR at −$44.19 —
entirely from that single triple-filled 00:45 close. **Which coin is "worst on
money" therefore flips with the window, which is itself an argument against
acting per-coin.**

**The mechanism behind the losses is real and it survived its control.** All
six losing closes whose settlement is on file contained a one-second index move
past 5 sigma of that coin's own trailing sigma (5.4, 7.6, 10.5, 15.0, 20.0,
31.5), against **1.69 expected** from section 1's own per-coin base rates —
Poisson-binomial **p = 0.00044**; four of six passed 8 sigma against 0.60
expected, **p = 0.0012**. Belief collapse on a one-second jump is what kills
these bets. **But the denominator is large — 21.6–37.2% of *all* closes carry a
>5-sigma second in their final minute and we win nearly every one — so "there
was a jump" can never be a gate by itself.**

**On whether SOL's INDEX is structurally jumpier, three tests come back empty
and the one that looked positive is an artefact I went and checked.**

1. **At the gate, nothing.** Over 7,266 tape markets and 808 closes, no coin is
   flagged on belief collapse or on flip at the |z| > 2.77 nine looks require.
   SOL sits on the pool for both (collapse 0.37% vs 0.50%; flip 0.25% vs
   0.23%). The only cell past threshold is SOL's collapse in the **fit** half —
   z = −4.20, *zero* collapses in five days — and it **flips sign in the
   holdout** (0.87%, z = +0.69). Four of nine coins change sign across the
   split. That is the exact shape the RUNBOOK records for the dead t = 4.1
   cell. MDE: only a 2.8× flip or 1.9× collapse difference was detectable.
2. **The entry populations are interchangeable**, so the nulls are not hiding a
   selection difference: mean entry tau 28.7–29.4 s, median entry margin at the
   7.03-sigma cap for every coin, saturated share 73–85%.
3. **Section 1 does find large per-coin differences in one-second jump tails —
   NEAR +13.9 to +19.9 z, SOL −20 to −35 — but SOL and NEAR are precisely the
   two coins whose numbers are not comparable, and the quantization guard says
   so before the table is read.** SOL's index is quoted in 0.01 steps while its
   own one-second sigma is 0.0082, so **69.6% of SOL seconds print no change at
   all** and one step is 1.2 sigma (sigma/step = 0.8; NEAR 4.8; every other coin
   ≥ 10). SOL reading as the calmest feed in the book is the coarse grid, not
   safety; NEAR reading as the jumpiest is partly the same grid forcing its
   non-zero moves into large multiples. **Section 1 ranks the other seven
   coins. It does not rank SOL or NEAR, in either direction.**

**Chasing that artefact produced the one general finding worth keeping — and
then our own fills refused to confirm its prediction.** Asking what would have
to be true for "SOL is calm" to be wrong led to section 5: each feed's
one-second sd against its own 60-second sd ÷ √60, which is the exact scale
`pinrun.fair()` projects over. **All nine come in below 1** (0.79 HYPE to 0.97
BTC), so the one-second sigma the bot feeds `fair()` understates the diffusion
at the horizon it projects across and every z-score is inflated by 3–26%. This
is **not new** — it independently reproduces `results/RESULTS_implied.md`'s
"sigma does NOT scale as sqrt(t)" (BNB 0.94, BTC 0.97, ETH 0.90, HYPE 0.75,
NEAR 0.92, SOL 0.91, XRP 0.77, ZEC 0.83) on a different window with a different
estimator, which is worth more than a new claim. And it does **not** single out
SOL (0.90, mid-pack); HYPE is the worst feed at 0.79 and has zero live losses.

That finding has a sharp prediction, because an inflated z can only change a
decision *near the gate boundary*: losses should concentrate in entries barely
past 0.995 and be absent from the saturated ones 7 sigma out. **Section 7 tests
it on our own fills and it fails, in the direction that matters.** The loss rate
does not fall as entry confidence rises — the point estimate *rises* (2.1% →
2.6% → 8.7% across the three bands; every interval overlaps every other, so
nothing is significant either way, but a gate change justified by section 5
needs this table to lean the other way and it does not).

**Section 7 did turn up one unambiguous thing, and it is not about margin: our
entries are only ~12% saturated while the tape's gate entries are 73–85%
saturated.** We cannot buy what nobody offers, and in a decided market the
losing side's book is empty — so we systematically get the *less certain* end of
the same gate. That is the adverse selection CLAUDE.md rule 5 is about, measured
here in its own units, and it is the cleanest reason yet that no tape rate can
stand in for ours.

### What I would PROPOSE — nothing is deployed, and the main proposal is to change nothing yet

1. **No per-coin gate, no SOL blacklist, no per-coin `PIN` or `SIGMA_STRESS`
   today.** p = 0.060 on the corrected statistic, on 14 SOL closes, with every
   index test flat and section 1 unable to rank SOL at all. Fitting nine coins
   to seven losing closes is how this project has produced every edge it later
   had to retract.
2. **Instead, PRE-REGISTER the SOL test now, before more data arrives.** This is
   the one place the evidence justifies spending something. Write the bar in
   `results/PREREG_coin.md` before looking again: a fixed number of further SOL
   closes at the current gate, a fixed threshold on the worst-of-nine statistic,
   and the action if it fires. The p-value moved 0.060 → 0.0285 → 0.060 inside
   one afternoon as one plant went in and came out; that volatility is the
   argument for freezing the question, not for acting on it.
3. **Re-count the live ledger by CLOSE, permanently, in the reporting path, and
   exclude plants and hedge legs.** Both corrections above were pure counting,
   and both changed the headline. `pincoin.load_live()` does it correctly.
4. **The lever is still the exit.** The mechanism test points at the post-entry
   jump, and `results/SKIM.md` already has a belief stop catching 11 of 11 tape
   losers for 0.12% of winners. Nothing here gives a reason to spend effort on
   coins instead.
5. **If sigma is ever revisited it is pool-wide and needs its own
   pre-registration.** Setting `SIGMA_STRESS` per feed from section 5's measured
   sd60/sd1 (1.03× BTC to 1.26× HYPE) would make `fair()` project at the scale
   the index actually diffuses at. **Weakly held, not proposed for deployment:**
   it is fitted on the same nine days it is measured on, it needs a holdout and
   a pre-registered live bar (AMENDMENT 2026-09-10 rule 4), section 7 declines
   to confirm its prediction, and the realised tape flip rate at the gate is
   **0.23% against a nominal 0.5%** — the arithmetic says "overconfident", the
   outcomes do not agree, and the outcomes win.

**THE TAPE RATES IN SECTIONS 1, 2, 3 AND 6 RANK COINS AGAINST EACH OTHER. THEY
ARE NOT OUR LOSS RATE AND MUST NEVER BE QUOTED AS ONE.** The tape's population
is "the model crossed the gate"; ours is "someone actively sold it to us", and
only the second is adversely selected — a 31× gap with non-overlapping intervals
(CLAUDE.md, AMENDMENT 2026-09-10, rule 5), one of whose mechanisms section 7
measures directly (12% vs 73–85% saturated). Every statement about **our**
losses above comes from sections 4 and 7, which read
`results/pinrun-live-*.jsonl` and nothing else.

## What this did NOT measure

- **Whether an offer existed, or whether we would have won the race for it.** No
  order book is read anywhere in this file. A tape "gate entry" is the model
  crossing 99.5%, not a fill.
- **Our live loss rate beyond the 195 closes on file.** Seven losing closes
  cannot support a per-coin rate and the tape cannot substitute for them.
- **One of the seven losing closes** (`KXSOL15M-26SEP120400-00`) has no
  settlement in `fulltape/markets.json` yet, so section 6's index
  reconstruction covers six of seven. It is listed as excluded, not estimated.
- **Whether SOL's −$38.39 is a per-coin effect or three bad draws.** The money
  table above is a measurement; the attribution is not, and the worst coin on
  money flips between SOL and NEAR depending on the window chosen.
- **Whether a pool-wide or per-coin `SIGMA_STRESS` would have changed a live
  decision.** That needs `pinsim`, which is certified for decision reproduction
  and explicitly *not* for loss rates.
- **Why the `cost` field on some `settled` records disagrees with the `price` on
  the matching `signal`** (the DOGE close signals 0.53 and settles at 0.0998).
  It affects nothing above — outcomes and entry `fair` are what sections 4, 6
  and 7 use — but it is unresolved and someone should look.
- **The exchange-lead mechanism** — whether the constituent tapes moved before
  the CF print on these closes. `research/pinjump.py` owns that, and the feeds
  carry only BTC, ETH, SOL, XRP and DOGE.
- **ADA, BCH, TON, CRYPTOCOMP and CRYPTOLEAD.** No settled markets, so nine
  coins, not twelve or fourteen.
- **Unconditional kurtosis.** Section 1's denominator is deliberately the
  trailing-300s sigma *the bot actually uses*, which makes it the operationally
  relevant statistic and not a statement about unconditional tails.
  `research/volmodel.py` owns that separation.

## How to read the machine output below

Everything from here down is written by `pincoin.py` and regenerates from the
commands at the top. This verdict is dated prose and does **not** regenerate —
if the tables move, re-read it.

- **Section 1** — per-coin one-second jump tail. **Read the quantization guard
  at the end of it first**; it decides which coins the table can rank.
- **Sections 2/3** — belief collapse and flip at the gate: MDE stated before the
  estimate, fit/holdout split, guard nulls, entry-population check.
- **Section 4** — our own live fills, clustered by close, plants and hedge legs
  dropped by name.
- **Section 5** — the scale audit: is the one-second sigma the right scale?
- **Section 6** — our losing closes reconstructed on the index, with a base rate.
- **Section 7** — entry margin vs our own outcomes: section 5's prediction,
  tested and refuted.

---

```

==============================================================================
  1. ONE-SECOND JUMP TAIL, per coin, against the coin's OWN trailing-300s sigma
     826 closes, 7,632 markets, 6,673,899 coin-seconds scored

  coin        sec/coin      k>3      k>4      k>5      k>6      k>8        (rate per 10,000 seconds)
  KXBNB15M     741,545    245.3    127.0     71.9     43.4     19.0
  KXBTC15M     741,543    239.8    123.6     68.4     42.7     20.3
  KXDOGE15M    741,547    202.8    104.3     61.8     40.8     22.1
  KXETH15M     741,545    221.4    101.9     52.9     31.9     14.0
  KXHYPE15M    741,546    203.3    107.7     65.3     43.6     22.9
  KXNEAR15M    741,544    238.1    130.9     79.6     51.7     23.1
  KXSOL15M     741,543    178.5     77.9     41.3     25.6     12.9
  KXXRP15M     741,541    205.0    101.9     59.4     39.2     21.1
  KXZEC15M     741,545    185.7     99.6     62.6     42.7     23.5

  Gaussian expectation, per 10,000 s: k>3 27.0, k>4 0.633, k>5 0.0057, k>6 0.0000, k>8 0.0000
  -- every coin is orders of magnitude above it at k>=5, which is the excess kurtosis
     the RUNBOOK already records. The question here is only whether the coins DIFFER.

  Coin vs the pool of the other 8, clustered on the close (826 clusters).
  MULTIPLE LOOKS: 45 cells, so the threshold is |z| > 3.26, not 1.96.

  coin             k>3       k>4       k>5       k>6       k>8     (z)
  KXBNB15M       18.35     17.27     11.66      5.23     -2.27
  KXBTC15M       16.78     13.36      6.92      3.79      0.92
  KXDOGE15M      -7.20     -4.42     -1.21      1.13      6.03
  KXETH15M        5.55     -6.88    -14.05    -15.90    -19.08
  KXHYPE15M      -5.95     -0.60      3.28      5.23      6.92
  KXNEAR15M      13.90     19.76     19.87     16.88      6.68
  KXSOL15M      -20.42    -34.39    -35.21    -31.82    -22.56
  KXXRP15M       -5.74     -7.20     -5.06     -1.88      3.52
  KXZEC15M      -17.00     -7.88     -0.03      4.20      8.09

  Restricted to the LAST 60 SECONDS before each close -- the settlement window, where
  the bot actually lives and where a jump moves the locked average least but the
  remaining-print projection most:

  coin        sec/coin      k>3      k>4      k>5      k>6      k>8
  KXBNB15M      49,403    230.4    123.3     69.6     39.9     15.6
  KXBTC15M      49,400    207.5    108.7     58.3     36.4     18.6
  KXDOGE15M     49,403    170.6     92.1     55.9     38.1     21.1
  KXETH15M      49,403    186.4     86.6     46.2     28.5     14.2
  KXHYPE15M     49,401    189.3    102.0     63.6     45.1     24.7
  KXNEAR15M     49,400    223.1    128.1     77.1     50.0     22.7
  KXSOL15M      49,400    151.6     69.6     40.5     25.7     13.2
  KXXRP15M      49,399    168.8     83.6     49.8     31.0     19.6
  KXZEC15M      49,402    166.0     94.3     59.7     40.1     22.3

  Largest single one-second move ever printed by each feed, in units of that feed's
  own trailing sigma one second earlier -- the event the 99.5% gate has to survive:

  coin        max |move|/sigma            when (UTC)
  KXBNB15M                76.0   2026-09-06T01:18:38Z
  KXBTC15M                39.4   2026-09-05T02:27:50Z
  KXDOGE15M               65.2   2026-09-05T02:50:11Z
  KXETH15M                54.5   2026-09-04T08:46:12Z
  KXHYPE15M               65.1   2026-09-06T16:42:14Z
  KXNEAR15M               42.3   2026-09-07T12:36:37Z
  KXSOL15M                31.5   2026-09-12T02:59:49Z
  KXXRP15M                65.5   2026-09-05T07:43:40Z
  KXZEC15M               128.1   2026-09-06T11:25:43Z

  ARTEFACT GUARD -- QUANTIZATION. The feeds are quoted to a fixed number of decimals.
  A coin whose one-second sd is only a few quotation steps has a LUMPY move distribution,
  and lumpiness reads as a fat tail in any k-sigma statistic. Read this table BEFORE
  believing any difference above: a coin with sigma/step below ~5 is not comparable.

  coin        zero-move s    quote step   mean sigma  sigma/step
  KXBNB15M           8.2%     0.0010000    0.0419034        41.9
  KXBTC15M           0.5%     0.0100000    3.8248904       382.5
  KXDOGE15M         19.6%     0.0000010    0.0000082         8.2
  KXETH15M           9.7%     0.0100000    0.1435596        14.4
  KXHYPE15M          3.8%     0.0001000    0.0065876        65.9
  KXNEAR15M         37.4%     0.0001000    0.0004274         4.3
  KXSOL15M          69.6%     0.0100000    0.0081722         0.8
  KXXRP15M          15.5%     0.0000100    0.0001038        10.4
  KXZEC15M           0.1%     0.0001000    0.1923815      1923.8

==============================================================================
  2/3. GATE ENTRIES -- first second with tau <= 30 where the model crosses 0.995
     7,266 entries = 7,266 markets over 808 closes. ONE ENTRY PER MARKET.

  *** THESE ARE NOT OUR BETS AND THIS IS NOT OUR LOSS RATE. ***
  The tape's population is 'the model crossed the gate'. Ours is 'someone actively
  sold it to us', which is adversely selected and runs ~31x worse (CLAUDE.md,
  AMENDMENT 2026-09-10 rule 5). These numbers RANK COINS AGAINST EACH OTHER. Nothing
  else may be read off them.

  MDE STATED BEFORE THE ESTIMATE. Two-sided 5% Bonferroni'd over 9 coins, 80% power,
  coin vs pool, at the pooled rates below:

  coin        n mkts   flip MDE  = x pool   collapse MDE  = x pool
  KXBNB15M       808      0.65%      2.8x          0.95%      1.9x
  KXBTC15M       808      0.65%      2.8x          0.95%      1.9x
  KXDOGE15M      808      0.65%      2.8x          0.95%      1.9x
  KXETH15M       806      0.65%      2.8x          0.95%      1.9x
  KXHYPE15M      808      0.65%      2.8x          0.95%      1.9x
  KXNEAR15M      808      0.65%      2.8x          0.95%      1.9x
  KXSOL15M       807      0.65%      2.8x          0.95%      1.9x
  KXXRP15M       806      0.65%      2.8x          0.95%      1.9x
  KXZEC15M       807      0.65%      2.8x          0.95%      1.9x

  Read that column first: with ~807 entries per coin nothing short of a
  3x difference in flip rate is detectable. A coin that is genuinely twice as
  dangerous would NOT show up. 'No effect' and 'no power' are different results.

  FULL WINDOW (9 days)
  coin        mkts  closes  entry tau  collapse            95% CI    flip            95% CI    z col   z flip
  KXBNB15M     808     808       28.8     0.87%      [0.3%, 1.8%]   0.12%      [0.0%, 0.7%]     1.32    -1.71
  KXBTC15M     808     808       28.8     0.37%      [0.1%, 1.1%]   0.12%      [0.0%, 0.7%]    -0.58    -0.83
  KXDOGE15M    808     808       28.9     0.50%      [0.1%, 1.3%]   0.37%      [0.1%, 1.1%]    -0.00     0.82
  KXETH15M     806     806       28.7     0.25%      [0.0%, 0.9%]   0.12%      [0.0%, 0.7%]    -1.35    -0.75
  KXHYPE15M    808     808       29.4     0.74%      [0.3%, 1.6%]   0.37%      [0.1%, 1.1%]     0.95     0.82
  KXNEAR15M    808     808       29.3     0.37%      [0.1%, 1.1%]   0.25%      [0.0%, 0.9%]    -0.69     0.11
  KXSOL15M     807     807       28.7     0.37%      [0.1%, 1.1%]   0.25%      [0.0%, 0.9%]    -0.73     0.12
  KXXRP15M     806     806       29.1     0.62%      [0.2%, 1.4%]   0.37%      [0.1%, 1.1%]     0.54     0.82
  KXZEC15M     807     807       29.1     0.37%      [0.1%, 1.1%]   0.12%      [0.0%, 0.7%]    -0.56    -0.76
  POOL       7,266     808       29.0     0.50%                     0.23%

  FIT HALF -- closes up to 09-08T04:45Z
  coin        mkts  closes  entry tau  collapse            95% CI    flip            95% CI    z col   z flip
  KXBNB15M     464     464       29.0     0.86%      [0.2%, 2.2%]   0.00%      [0.0%, 0.8%]     1.16    -2.25
  KXBTC15M     464     464       29.0     0.43%      [0.1%, 1.5%]   0.00%      [0.0%, 0.8%]     0.08    -2.25
  KXDOGE15M    464     464       28.9     0.43%      [0.1%, 1.5%]   0.22%      [0.0%, 1.2%]     0.08     0.48
  KXETH15M     462     462       28.6     0.22%      [0.0%, 1.2%]   0.00%      [0.0%, 0.8%]    -0.89    -2.25
  KXHYPE15M    464     464       29.4     0.86%      [0.2%, 2.2%]   0.43%      [0.1%, 1.5%]     1.16     1.14
  KXNEAR15M    464     464       29.4     0.22%      [0.0%, 1.2%]   0.00%      [0.0%, 0.8%]    -0.90    -2.25
  KXSOL15M     463     463       28.6     0.00%      [0.0%, 0.8%]   0.00%      [0.0%, 0.8%]    -4.20    -2.25
  KXXRP15M     464     464       29.2     0.43%      [0.1%, 1.5%]   0.22%      [0.0%, 1.2%]     0.08     0.48
  KXZEC15M     464     464       29.1     0.22%      [0.0%, 1.2%]   0.22%      [0.0%, 1.2%]    -0.90     0.48
  POOL       4,173     464       29.0     0.41%                     0.12%

  HOLDOUT -- closes after 09-08T04:45Z (NOT looked at when the hypothesis was formed)
  coin        mkts  closes  entry tau  collapse            95% CI    flip            95% CI    z col   z flip
  KXBNB15M     344     344       28.5     0.87%      [0.2%, 2.5%]   0.29%      [0.0%, 1.6%]     0.65    -0.73
  KXBTC15M     344     344       28.6     0.29%      [0.0%, 1.6%]   0.29%      [0.0%, 1.6%]    -1.01    -0.32
  KXDOGE15M    344     344       28.8     0.58%      [0.1%, 2.1%]   0.58%      [0.1%, 2.1%]    -0.11     0.67
  KXETH15M     344     344       28.8     0.29%      [0.0%, 1.6%]   0.29%      [0.0%, 1.6%]    -1.01    -0.29
  KXHYPE15M    344     344       29.3     0.58%      [0.1%, 2.1%]   0.29%      [0.0%, 1.6%]    -0.11    -0.73
  KXNEAR15M    344     344       29.1     0.58%      [0.1%, 2.1%]   0.58%      [0.1%, 2.1%]    -0.11     0.67
  KXSOL15M     344     344       28.8     0.87%      [0.2%, 2.5%]   0.58%      [0.1%, 2.1%]     0.69     0.76
  KXXRP15M     342     342       29.1     0.88%      [0.2%, 2.5%]   0.58%      [0.1%, 2.1%]     0.70     0.68
  KXZEC15M     343     343       29.2     0.58%      [0.1%, 2.1%]   0.00%      [0.0%, 1.1%]    -0.07    -1.82
  POOL       3,093     344       28.9     0.61%                     0.39%

  Multiple looks on 9 coins: |z| > 2.77.
  Entries with no post-entry second (entered at tau 3) and therefore no collapse observation: 12 of 7,266

  GUARD NULL -- what the scan threw away, per coin (a guard that discards everything
  looks exactly like a thin tape, so it prints its own cost):
    KXBNB15M   29 no_sigma, 271 no_tick
    KXBTC15M   29 no_sigma, 273 no_tick
    KXDOGE15M  29 no_sigma, 269 no_tick
    KXETH15M   29 no_sigma, 271 no_tick
    KXHYPE15M  29 no_sigma, 270 no_tick
    KXNEAR15M  28 no_sigma, 273 no_tick
    KXSOL15M   29 no_sigma, 273 no_tick
    KXXRP15M   28 no_sigma, 276 no_tick
    KXZEC15M   29 no_sigma, 271 no_tick

  ARTEFACT GUARD -- IS THE ENTRY POPULATION THE SAME? A coin can look more dangerous
  simply because its gate entries carry less margin or arrive later. If these columns
  match across coins, a difference in the tables above is about the INDEX, not selection.

  coin            n  mean tau_in  median margin sd  saturated
  KXBNB15M      808         28.8              7.03      77.2%
  KXBTC15M      808         28.8              7.03      72.9%
  KXDOGE15M     808         28.9              7.03      79.1%
  KXETH15M      806         28.7              7.03      76.9%
  KXHYPE15M     808         29.4              7.03      84.5%
  KXNEAR15M     808         29.3              7.03      82.2%
  KXSOL15M      807         28.7              7.03      76.3%
  KXXRP15M      806         29.1              7.03      78.9%
  KXZEC15M      807         29.1              7.03      82.9%

  STABILITY ACROSS THE SPLIT (collapse rate, the statistic with enough events to move):
  coin        fit n  fit col  hold n  hold col    sign held?
  KXBNB15M      464    0.86%     344     0.87%           yes
  KXBTC15M      464    0.43%     344     0.29%            NO
  KXDOGE15M     464    0.43%     344     0.58%            NO
  KXETH15M      462    0.22%     344     0.29%           yes
  KXHYPE15M     464    0.86%     344     0.58%            NO
  KXNEAR15M     464    0.22%     344     0.58%           yes
  KXSOL15M      463    0.00%     344     0.87%            NO
  KXXRP15M      464    0.43%     342     0.88%           yes
  KXZEC15M      464    0.22%     343     0.58%           yes

==============================================================================
  4. OUR OWN LIVE FILLS -- the ONLY valid source for OUR loss rate
==============================================================================
  198 settled GATE fills, 195 distinct markets/closes, 2026-09-08T08:00:20Z .. 2026-09-12T13:00:20Z
  GUARD: dropped 2 one-contract hedge-test PLANT fills and 1 HEDGE legs -- neither is a gate decision. See load_live().
  Leaving them in is what briefly made SOL look significant: two plants bought at
  0.3c and 5.2c, which exist to LOSE, took SOL from 3-of-14 to 4-of-15 and the
  worst-of-nine p-value from 0.132 to 0.0285.

  *** THE FIRST CORRECTION IS A COUNTING ONE, AND IT MOVES THE ANSWER. ***
  9 losing FILLS sit on 7 losing MARKETS. The multiply-filled ones:
    KXNEAR15M-26SEP082045-45           3 fills, ONE close, ONE outcome (paid 0.962, 0.956, 0.73)
  Hundreds of fills can share one settlement, so `n` is markets and closes, never
  fills (CLAUDE.md hard rule 4). Counting fills is what turns one NEAR close into
  'three NEAR losses'.

  ALL live runs: 198 fills -> 195 closes, 7 losing closes (3.6%)
  coin          closes  lost    rate      95% CI (Clopper-Pearson)     P(>= this|one rate)
  KXSOL15M          23     3   13.0%                 [2.8%, 33.6%]                  0.0368
  KXXRP15M          29     1    3.4%                 [0.1%, 17.8%]                  0.6822
  KXBNB15M          22     1    4.5%                 [0.1%, 22.8%]                  0.5734
  KXDOGE15M         21     1    4.8%                 [0.1%, 23.8%]                  0.5556
  KXNEAR15M         18     1    5.6%                 [0.1%, 27.3%]                  0.4980
  KXBTC15M          36     0    0.0%                  [0.0%, 9.7%]                        
  KXHYPE15M         19     0    0.0%                 [0.0%, 17.6%]                        
  KXETH15M          15     0    0.0%                 [0.0%, 21.8%]                        
  KXZEC15M          12     0    0.0%                 [0.0%, 26.5%]                        
  ONE SHARED LOSS RATE for every coin: the chance the WORST coin still reaches
  3 losing closes is p = 0.3327 (7 losses over 195 closes, 200,000 random deals,
  max-per-coin-count statistic). The max is what pays for having noticed the coin
  AFTER the fact; a per-coin p-value would not.
  MDE at this live size: 15.4% against a base of 3.6% -- only a coin
  4x the pool rate is detectable, so 'no effect' and 'no power' are not distinguishable here.

  CURRENT GATE ONLY (pin = 0.995): 116 fills -> 115 closes, 4 losing closes (3.5%)
  coin          closes  lost    rate      95% CI (Clopper-Pearson)     P(>= this|one rate)
  KXSOL15M          14     3   21.4%                 [4.7%, 50.8%]                  0.0055
  KXDOGE15M          9     1   11.1%                 [0.3%, 48.2%]                  0.2814
  KXBTC15M          24     0    0.0%                 [0.0%, 14.2%]                        
  KXXRP15M          19     0    0.0%                 [0.0%, 17.6%]                        
  KXBNB15M          14     0    0.0%                 [0.0%, 23.2%]                        
  KXHYPE15M         11     0    0.0%                 [0.0%, 28.5%]                        
  KXNEAR15M         10     0    0.0%                 [0.0%, 30.8%]                        
  KXZEC15M           7     0    0.0%                 [0.0%, 41.0%]                        
  KXETH15M           7     0    0.0%                 [0.0%, 41.0%]                        
  ONE SHARED LOSS RATE for every coin: the chance the WORST coin still reaches
  3 losing closes is p = 0.0603 (4 losses over 115 closes, 200,000 random deals,
  max-per-coin-count statistic). The max is what pays for having noticed the coin
  AFTER the fact; a per-coin p-value would not.
  MDE at this live size: 20.1% against a base of 3.5% -- only a coin
  6x the pool rate is detectable, so 'no effect' and 'no power' are not distinguishable here.

  THE LOSS SEQUENCE THE OPERATOR ASKED ABOUT, oldest first:
    2026-09-09T00:45:20Z  KXNEAR15M-26SEP082045-45           gate 0.98  paid 0.962  -1929c
    2026-09-09T00:45:35Z  KXNEAR15M-26SEP082045-45           gate 0.98  paid 0.956  -1918c
    2026-09-09T00:45:50Z  KXNEAR15M-26SEP082045-45           gate 0.98  paid 0.73  -1413c
    2026-09-10T05:00:20Z  KXXRP15M-26SEP100100-00            gate 0.98  paid 0.82  -1661c
    2026-09-10T05:30:20Z  KXBNB15M-26SEP100130-30            gate 0.98  paid 0.94  -1760c
    2026-09-10T22:15:20Z  KXDOGE15M-26SEP101815-15           gate 0.995  paid 0.0998  -212c
    2026-09-11T12:30:20Z  KXSOL15M-26SEP110830-30            gate 0.995  paid 0.591  -1216c
    2026-09-12T03:00:20Z  KXSOL15M-26SEP112300-00            gate 0.995  paid 0.979  -1961c
    2026-09-12T08:00:20Z  KXSOL15M-26SEP120400-00            gate 0.995  paid 0.94  -1888c

  The last three losses at the current gate are KXSOL15M, KXSOL15M, KXSOL15M.
  GIVEN that the 4 losses fell on the coins they did, the chance the three most
  recent all share ONE coin is 25.0%. So the 'three in a row' framing
  adds essentially nothing beyond the count itself -- the evidence is the table
  above, not the ordering.

==============================================================================
  5. SCALE AUDIT -- is the ONE-SECOND sigma that fair() projects from the right scale?
==============================================================================
  sd of index differences at lag L, divided by sqrt(L), so a random walk gives the
  same number in every column. Divergence at lag 1 means the one-second sigma the
  bot feeds into fair() is not the feed's diffusion.

  coin              level       step  zero-1s         sd1    sd10/r10    sd30/r30    sd60/r60   sd1/sd60
  KXBNB15M       735.5297  0.0010000     8.2%   0.0488976   0.0499061   0.0516827   0.0534034      0.916
  KXBTC15M     78999.7361  0.0100000     0.5%   4.6113855   4.7711797   4.7609186   4.7784226      0.965
  KXDOGE15M        0.0875  0.0000010    19.7%   0.0000101   0.0000108   0.0000109   0.0000110      0.921
  KXETH15M      2482.6364  0.0100000     9.7%   0.1756470   0.1974216   0.2019538   0.2057953      0.854
  KXHYPE15M       84.3046  0.0001000     3.8%   0.0074636   0.0083984   0.0090452   0.0094125      0.793
  KXNEAR15M        2.2909  0.0001000    37.4%   0.0004818   0.0005017   0.0005258   0.0005363      0.898
  KXSOL15M       102.9693  0.0100000    69.6%   0.0090923   0.0097839   0.0099751   0.0101134      0.899
  KXXRP15M         1.4004  0.0000100    15.5%   0.0001238   0.0001455   0.0001506   0.0001533      0.808
  KXZEC15M      1107.1717  0.0001000     0.1%   0.2361463   0.2608832   0.2597940   0.2628005      0.899

  sd1/sd60 > 1: the bot's sigma is TOO BIG, fair() is pulled toward 50c, and the
                99.5% gate is HARDER to reach -- conservative.
  sd1/sd60 < 1: the bot's sigma is TOO SMALL, fair() is pushed toward 0/100c, and
                the gate fires on thinner evidence -- OVERCONFIDENT.

  Same numbers as a multiple of each feed's quote step, which is the quantity that
  decides whether the grid can distort the one-second estimate at all:

  coin         sigma_1s/step  60s move/step    sd1/sd60    comparable?
  KXBNB15M              48.9          413.7       0.916            yes
  KXBTC15M             461.1         3701.4       0.965            yes
  KXDOGE15M             10.1           85.3       0.921            yes
  KXETH15M              17.6          159.4       0.854            yes
  KXHYPE15M             74.6          729.1       0.793            yes
  KXNEAR15M              4.8           41.5       0.898       MARGINAL
  KXSOL15M               0.9            7.8       0.899             NO
  KXXRP15M              12.4          118.7       0.808            yes
  KXZEC15M            2361.5        20356.4       0.899            yes

  'comparable?' is about SECTION 1 only: a coin whose one-second sigma is under a
  few quote steps has a lumpy one-second move distribution, so its k-sigma
  exceedance RATE cannot be compared with a finely-quoted coin's in either
  direction. It does NOT mean the coin is safe or unsafe -- that is the sd1/sd60
  column's job.

==============================================================================
  6. OUR OWN LOSING CLOSES, RECONSTRUCTED ON THE INDEX -- with a base rate
==============================================================================
  7 losing closes in our own fill log. For each, the largest one-second
  index move in the final 60 s, in units of that feed's own sigma one second earlier.

  market                            close (UTC)            max |move|/sigma   at tau   result
  KXBNB15M-26SEP100130-30           2026-09-10T05:30:00Z                5.4       24       no
  KXDOGE15M-26SEP101815-15          2026-09-10T22:15:00Z               20.0       10      yes
  KXNEAR15M-26SEP082045-45          2026-09-09T00:45:00Z                7.6       16      yes
  KXSOL15M-26SEP110830-30           2026-09-11T12:30:00Z               10.5       26      yes
  KXSOL15M-26SEP112300-00           2026-09-12T03:00:00Z               31.5       11      yes
  KXXRP15M-26SEP100100-00           2026-09-10T05:00:00Z               15.0       20       no
  KXSOL15M-26SEP120400-00             settlement not yet in markets.json -- EXCLUDED, not estimated

  THE DENOMINATOR. From section 1's last-60s panel: the chance a close's final minute
  contains at least one such second at all, per coin. A big jump is NOT rare.

  coin            P(>5 sigma in 60s)    P(>8 sigma in 60s)
  KXBNB15M                     34.2%                  8.9%
  KXBTC15M                     29.6%                 10.6%
  KXDOGE15M                    28.5%                 11.9%
  KXETH15M                     24.2%                  8.2%
  KXHYPE15M                    31.8%                 13.8%
  KXNEAR15M                    37.2%                 12.7%
  KXSOL15M                     21.6%                  7.6%
  KXXRP15M                     25.9%                 11.1%
  KXZEC15M                     30.2%                 12.5%

  k > 5: 6 of 6 losing closes carried one. Expected 1.69 under each coin's
          own base rate -> Poisson-binomial P(>= 6 of 6) = 0.00044
  k > 8: 4 of 6 losing closes carried one. Expected 0.60 under each coin's
          own base rate -> Poisson-binomial P(>= 4 of 6) = 0.00120

  SO: belief collapse on a one-second jump is what kills these bets, and that is
  established against the base rate rather than asserted from the cases. But the
  base rate is HIGH -- a fifth to a third of all closes carry a >5-sigma second and
  we win nearly every one -- so 'there was a jump' can never be a gate by itself.
  n here is 6-7 CLOSES. It is a mechanism check, not a rate.

==============================================================================
  7. ENTRY MARGIN vs OUTCOME, on OUR OWN FILLS -- section 5's prediction, TESTED
==============================================================================
  Section 5's sigma understatement inflates every z-score, so it can only change a
  decision NEAR THE GATE. Prediction: losses concentrate in entries barely past
  0.995 and are absent from the saturated ones. Bands are on the LOWEST confidence
  actually bought on that close.
  This section requires a SIGNAL followed by a filled ORDER, so the hedge-test plants
  never enter it -- an independent route to the same exclusion section 4 makes by
  name, which is why the two close counts agree.

  ALL live runs: 195 closes with both an entry signal and a settlement
  entry confidence band     closes  lost    rate              95% CI   median margin
  0.9950-0.9990                 95     2    2.1%        [0.3%, 7.4%]          2.78 sd
  0.9990-0.99999                38     1    2.6%       [0.1%, 13.8%]          3.41 sd
  0.99999-1 (saturated)         23     2    8.7%       [1.1%, 28.0%]          7.03 sd
  saturated share of ENTRIES 11.8% (23/195); of LOSSES 28.6% (2/7)

  CURRENT GATE ONLY (pin = 0.995): 115 closes with both an entry signal and a settlement
  entry confidence band     closes  lost    rate              95% CI   median margin
  0.9950-0.9990                 74     2    2.7%        [0.3%, 9.4%]          2.77 sd
  0.9990-0.99999                27     1    3.7%       [0.1%, 19.0%]          3.36 sd
  0.99999-1 (saturated)         14     1    7.1%       [0.2%, 33.9%]          7.03 sd
  saturated share of ENTRIES 12.2% (14/115); of LOSSES 25.0% (1/4)

  Our losing closes, least confident first:
    KXNEAR15M-26SEP082045-45           gate 0.98  entry conf 0.981740  margin 2.09 sd
    KXBNB15M-26SEP100130-30            gate 0.98  entry conf 0.985070  margin 2.17 sd
    KXSOL15M-26SEP110830-30            gate 0.995  entry conf 0.995080  margin 2.58 sd
    KXSOL15M-26SEP120400-00            gate 0.995  entry conf 0.997640  margin 2.83 sd
    KXSOL15M-26SEP112300-00            gate 0.995  entry conf 0.999680  margin 3.41 sd
    KXXRP15M-26SEP100100-00            gate 0.98  entry conf 1.000000  margin 7.03 sd
    KXDOGE15M-26SEP101815-15           gate 0.995  entry conf 1.000000  margin 7.03 sd

  *** SECTION 5's PREDICTION FAILS, AND IT FAILS IN THE DIRECTION THAT MATTERS. ***
  The loss rate does not fall as entry confidence rises; the point estimate rises.
  Every interval overlaps every other -- with this many losing closes nothing here
  is significant in EITHER direction -- but a gate change justified by section 5
  would need this table to lean the other way, and it does not. So no PIN change, no
  margin cushion, and no per-coin sigma is proposed from this file.

  ONE THING IS CLEAR AND IT IS NOT ABOUT MARGIN: our entries are only ~12%
  saturated while the TAPE's gate entries are 73-85% saturated (section 2/3). We
  cannot buy what nobody offers, and in a decided market the losing side's book is
  empty -- so we systematically get the LESS certain end of the same gate. That is
  the adverse selection CLAUDE.md rule 5 is about, measured here in its own units.
```
