# B_holdout -- adversarial re-derivation and HOLDOUT test of the 22 newedge candidates

**COMPLETE.** 2026-09-23. Every number below was produced by my own code in
`scratchpad/newedge/verify/`, from Kalshi's settlement ledger, the bot's own live
logs and the raw tape. No pinsim, no pindata, no replay import anywhere.

Role: I did not run the hunts. I re-derive every number with my own code
(`scratchpad/newedge/verify/`), apply each rule UNCHANGED to the HOLDOUT
(closes 2026-09-21 ET 00:00 onward = 2026-09-21T04:00Z onward, which contains
the DOGE 10:45 PM loss), attack it, and check it can never delay a hedge.

## 0. My own base, built from scratch, and it matches theirs

`verify/common.py` re-derives money straight from Kalshi's `/portfolio/settlements`
(payout - both sides' cost - fees, payout taken from `market_result` x the
contract count, never `revenue`), joins it to the first filled `order` in the
live logs and to the `signal` in the same second, and cuts the population at
2026-09-21T04:00Z (= 2026-09-21 00:00 ET).

| | markets | closes | net | losing markets |
|---|---|---|---|---|
| ALL | 788 | 579 | +$548.75 | 26 |
| TRAIN (to 09-20 ET) | 697 | 509 | +$482.88 | 23 |
| **HOLDOUT (09-21 ET on)** | **91** | **70** | **+$65.86** | **3** |

That reproduces the realised-vol, exchange-books and cross-coin hunts' base
exactly (697 / 509 / +$482.88 / 23 losers), so they were all reading the same
money. Ticker close times were independently checked against the bot's own
`close_s` field on 15,498 refusal records: 15,498 agree, 0 disagree.

**The three HOLDOUT losers** (this is the bar every candidate has to clear):

| market | ET | $ | tau | price | `level_age_ms` | hedged |
|---|---|---|---|---|---|---|
| KXNEAR15M-26SEP211245-45 | 09-21 12:45 | -59.09 | 44 | 0.955 | 75 | yes |
| KXHYPE15M-26SEP211815-15 | 09-21 18:15 | -31.27 | 43 | 0.980 | 57 | yes |
| KXDOGE15M-26SEP222245-45 | 09-22 22:45 | -2.47 | 11 | 0.980 | 38 | yes |

Free RAM 2.82 GB at start, free disk 20.04 GB. No process touched.

---

## 1. kalshi-book #1 -- CLEAN/REST (level age + book imbalance). **WEAKENED, and the imb half is REFUTED.**

### 1a. The rule splits into two very different things, and the hunt reported them as one

`livebook.level_age_ms` returns `(age, exact)`. **`exact=False` means the level
was already in the snapshot and the "age" is just time since our subscription.**
On our fills those rows have a median age of **829,492 ms (13.8 minutes)** -- they
pass any threshold automatically. So "age >= 100 ms" is really two populations:

| TRAIN | markets | closes | losers | net | c/contract |
|---|---|---|---|---|---|
| `exact=False` (never saw the level appear -> auto-pass) | 153 | 134 | 1 | +$290.23 | 2.796 |
| `exact=True` and age >= 100 ms | 146 | 133 | 4 | +$250.55 | 2.641 |
| **`exact=True` and age < 100 ms (the blocked half)** | **140** | **126** | **8** | **-$105.57** | **-1.235** |

| HOLDOUT | markets | closes | losers | net | c/contract |
|---|---|---|---|---|---|
| `exact=False` | 34 | 31 | 0 | +$56.39 | 2.658 |
| `exact=True` and age >= 100 ms | 21 | 21 | 0 | +$37.28 | 3.259 |
| **`exact=True` and age < 100 ms** | **36** | **32** | **3** | **-$27.80** | **-1.462** |

The fresh-level half is the only negative bucket in either half of the sample, and
**all three HOLDOUT losers are in it** (level ages 75, 57, 38 ms). That part is
out-of-sample support the hunt did not have when it wrote the rule down.

### 1b. It is NOT a proxy for tau, price, leg or side

TRAIN medians, `exact=False` / blocked / `exact=True` kept: tau **28 / 28 / 30**,
price **0.9750 / 0.9730 / 0.9720**. Correlation of log10(level age) with tau is
**+0.026** (TRAIN) and **-0.004** (HOLDOUT); with price +0.127 / +0.171; with
size +0.092 / +0.119. Leg mix is the same. So it is a genuinely different cut
from every price/tau/confidence gate already priced.

Coin is the one imbalance: BTC is 32 of the 140 blocked (23%) against 6 of 153
`exact=False` (4%) -- BTC's book moves fastest, so that is mechanical. Within
coin the sign is not uniform: BTC blocked -$162.57 (4 losers) vs kept +$91.81 (0);
but DOGE, ETH, SOL and ZEC blocked buckets are all POSITIVE.

### 1c. The dollar case is 100% one bug day. This is the finding that matters.

| TRAIN, leave one ET day out | blocked bucket n | losers | net |
|---|---|---|---|
| drop 09-13 | 123 | 8 | -$152.03 |
| drop 09-14 | 124 | 7 | -$111.52 |
| drop 09-15 | 126 | 8 | -$136.61 |
| drop 09-16 | 126 | 7 | -$138.17 |
| drop 09-17 | 119 | 7 | -$128.98 |
| drop 09-18 | 115 | 8 | -$141.76 |
| **drop 09-19** | **120** | **3** | **+$206.51** |
| drop 09-20 | 127 | 8 | -$136.45 |

Excluding 09-19 -- the day CURRENT_STATE.md and memory both record as gates and
brakes blocking hedges, since fixed -- blocking the fresh-level half would have
**COST $206.51** on 120 markets, and its loss rate falls to 3/120 = 2.5% against
4/246 = 1.6% kept. Dropping the single biggest loss alone (KXBTC 09-19 16:00,
-$107.95) takes the bucket from -$105.57 to **+$2.38**.

Within-day permutation, 20,000 draws, outcomes shuffled inside each ET day:
TRAIN P(net <= observed) = 0.0018, P(losers >= observed) = 0.0146; TRAIN+HOLDOUT
0.0006 and 0.0025. Against the total-looks bar across all five hunts (~230 cuts
-> 0.05/230 = 0.0002) **nothing here clears**, and the one number that comes
close is the dollar permutation, which is the 09-19 number.

### 1d. The `imb` half adds nothing out of sample and is contaminated

I rebuilt imbalance myself from `kalshi_data\ticker` (391,712 rows, 228 hour
files, 4 missing incl. the 09-22 04Z outage hour), taking the last row whose
**exchange** `ts_ms` <= entry - 1.0 s, our side = yes-ask when buying yes and
yes-bid when buying no.

- I reproduce their TRAIN split in shape: CLEAN 200 markets / 2 losing markets /
  +$438.86 vs REST 238 / 11 / -$5.23 (they reported CLEAN 198/0/+$426.06 and
  REST 240/9/+$6.77 -- their "0 losses" is a leg count, and on markets CLEAN
  holds 2 losers, worst -$12.14).
- **HOLDOUT: it does not separate.** CLEAN 25 markets / 0 losers / +$58.39;
  REST 62 / 3 / **+$3.66**. Fisher p = 0.357. REST is net POSITIVE, so blocking
  or down-sizing it would have lost money in the holdout.
- **imb contributes nothing on its own out of sample.** Among not-fresh holdout
  markets: imb<=0.5 -> 0 losers +$58.39; imb>0.5 -> 0 losers +$33.98. Among
  fresh: 1 loser vs 2 losers.
- **Receive-time contamination, measured: 135 of the 525 ticker rows I used
  (25.7%) were RECEIVED AFTER our entry second** -- median 1.97 s late, up to
  11.21 s. The bot could not have known them. `ticker` receive lag is p50 288 ms,
  p90 4,030 ms, p99 8,985 ms.
- **Internal contradiction:** the row used is a median **1.6 s** old on exchange
  time (p90 1.8 s, p99 447 s), and the hunt's own robustness check says the
  signal dies within 3 s. A signal with a 3-second half-life cannot be read
  reliably from a 1.6-second-old row.

### 1e. Hedge safety

`level_age_ms` and `imb` as proposed sit at the entry decision only. Neither is
consulted in `hedge`, `hedge_panic` or the early leg, and the S1 form (a size
multiplier) cannot refuse anything. **Hedge-safe** -- but only if written as S1
or S3 and only inside the entry branch; the 09-19 lesson is that a gate written
"defensively" is what silenced hedges.

### Verdict on kalshi-book #1

**WEAKENED.** What survives: `level_age_exact AND level_age_ms < 100` ranks our
losses, in TRAIN (8 of 13) and out of sample (**3 of 3**), and it is not a proxy
for tau, price, leg or side. What does NOT survive: every dollar claim (one bug
day carries all of it), the "0 losses in CLEAN" headline (2 losing markets on my
count), and the whole `imb` half (no holdout separation, a quarter of its rows
arrived after we had already traded). **REFUTED as a money rule; alive as a
ranking signal worth logging.**

---

## THE HONEST MDE, FIRST, BECAUSE IT GOVERNS EVERYTHING BELOW

Per-close realised P&L: TRAIN mean +$0.949, sd $8.61 over 509 closes; HOLDOUT
mean +$0.941, sd $8.61 over 70 closes.

- **The HOLDOUT total of +$65.86 carries a 95% range of -$75.39 to +$207.11.**
  The holdout cannot tell a good week from a bad one. It certainly cannot rank
  sub-rules inside itself.
- TRAIN's +$482.88 carries +/- $422.13. Even the whole training total is only
  barely distinguishable from zero.
- **Loss-rate MDE on the holdout:** flag 30 of the 91 markets and you need
  3 of them to be losers for a one-sided p < 0.05 -- a 10.0% flagged rate
  against 3.30% overall, a **3.0x lift**. Flag 20 and you need a 4.5x lift.
  Anything smaller than 3x is invisible here.
- Clopper-Pearson: 0 of 25 = [0%, 13.7%]; 0 of 55 = [0%, 6.5%]; 3 of 36 =
  [1.8%, 22.5%]. The "zero losers" buckets are consistent with the base rate.

**Multiple-looks bar across the whole sweep.** Declared looks: realised-vol 15,
kalshi-book ~75, exchange-books 101, cross-coin 14, other-venues ~35 -> **~240**,
so 0.05/240 = **0.00021**. I added 41 more cuts of my own (counted at the end),
which does not move the bar materially. **Not one candidate in the sweep clears
0.00021 on a pre-entry cut.** The only cut that does is kalshi-book #2's
post-fill marker, and that one cannot gate anything.

So: every "survives" below means *survives as a ranking or a diagnostic*. None
of them means *deploy this and the money follows*.

---

## 2. kalshi-book #2 -- "fill came back >= 2c under the ask". **SURVIVES out of sample, but the mechanism is NOT adverse selection.**

The post-fill marker, my own join of `order.ask_seen` to `order.exec_price`
(515 fills carry both):

| | markets | losers | net | $/market |
|---|---|---|---|---|
| TRAIN, came back >= 2c cheap | 13 | 3 (23%) | -$58.14 | -$4.47 |
| TRAIN, the rest | 411 | 10 (2.4%) | +$449.10 | +$1.09 |
| **HOLDOUT, came back >= 2c cheap** | **3** | **2 (67%)** | **-$54.85** | **-$18.28** |
| HOLDOUT, the rest | 88 | 1 (1.1%) | +$120.72 | +$1.37 |

Holdout Fisher p = 0.0022 on one pre-specified look. **Two of the three holdout
losers are in it** (NEAR -$59.09, DOGE -$2.47). The pre-entry proxy also
reproduces: `level_age_ms < 300` flags 6.2% cheap in the holdout against 0.0%
for age >= 300 ms.

### But look at what the 16 markets actually are

| market | ask seen -> paid | gap | $ |
|---|---|---|---|
| KXDOGE15M-26SEP180015-15 | 0.976 -> 0.1100 | **86.6c** | +4.36 |
| KXBTC15M-26SEP172115-15 | 0.978 -> 0.5300 | **44.8c** | -27.87 |
| KXBTC15M-26SEP141930-30 | 0.970 -> 0.8000 | 17.0c | +11.14 |
| KXZEC15M-26SEP172115-15 | 0.973 -> 0.8700 | 10.3c | +12.09 |
| KXBNB15M-26SEP190145-45 | 0.850 -> 0.7498 | 10.0c | -57.76 |
| ... 11 more at 2.1c-9.5c | | | |

`exec_price` is the **volume-weighted average over a sweep**. A gap of 86.6c is
not "the ask collapsed", it is `--sweep-depth`/`--depth-ladder` reaching down the
ladder. Median price paid on the 16 is **0.8964** against **0.9763** on
everything else, so the marker is largely *the average price we paid*, which is
already a known axis.

**Inside a price band it disappears at this n:** restricting to a paid price of
0.93-0.975 leaves 5 cheap fills (2 losers, -$38.05) against 189 (4 losers,
+$260.20). Five events cannot separate anything.

**Verdict: SURVIVES as a loss marker, REFUTED as "adverse selection on the
fill".** It is mostly a sweep-depth / average-price measure. Reconciling it with
the map's "7 of 27 closes" figure (a different definition) is still open, exactly
as the hunt itself said.

## 3. kalshi-book #3 -- the nine book-shape nulls. **SURVIVES (accept the kill), with the MDE restated.**

I did not re-derive all nine; with 3 holdout losers I could not test any of them
out of sample, and saying otherwise would be inventing power I do not have.
I accept them as *not found*, and the number that matters is the one the hunt
already gave: with 9-17 losses the MDE is a ~9-10% flagged loss rate, so an
effect smaller than ~4x the base rate is invisible. My holdout MDE (3.0x on 30
flagged markets) says the same thing from the other side.

**One correction.** Their point (9), "level_age alone is a knife edge -- +$90 on
TRAIN at 100 ms, break-even by 200 ms", is right about the DOLLARS and wrong
about the loss count. My TRAIN numbers for blocking `age < X`:

| threshold | blocked markets | blocked losers | blocking gains |
|---|---|---|---|
| 100 ms | 140 | 8 | +$105.57 |
| 200 ms | 175 | 8 | +$20.47 |
| 300 ms | 193 | 11 | +$47.78 |
| 500 ms | 212 | 11 | +$0.47 |
| 1000 ms | 240 | 11 | **-$79.76** |

The dollars are noise across thresholds. The loss COUNT is stable (the kept half
holds 5, 5, 2, 2, 2 losers) and in the HOLDOUT the kept half holds **0 at every
threshold from 100 to 1000 ms**. So it is a knife edge on money and a plateau on
ranking -- and the ranking is the part worth logging.

---

## 4. realised-vol #1 -- the fat-tail mixture curve. **MEASUREMENT CONFIRMED (and about a third of the far tail is a ruler artefact). THE PROPOSAL IS REFUTED: it would stop the bot trading.**

### 4a. I rebuilt the grid from the raw index tape with my own code and it holds

`verify/grid.py`, `cfbenchmarks_value` only, 2026-09-08..09-21, **n = 14,267
samples per tau** (11 coins x 96 quarter-hour closes x 14 days, exogenous grid,
`var_factor(tau, [1.0])` = the bot's own assumption), sigma = sd of consecutive
1-second differences over the trailing window, exactly `pinrun._sig_over`.

| tau, sigma window | sd(z) | \|z\|>2 | \|z\|>3 | \|z\|>4 | \|z\|>6 | \|z\|>8 |
|---|---|---|---|---|---|---|
| **45, 300 s (live)** | **1.153** | **6.399%** | **2.019%** | **0.862%** | **0.315%** | **0.168%** |
| 45, 1800 s | 1.041 | 5.222% | 1.703% | 0.645% | 0.182% | 0.119% |
| 45, 3600 s | 1.050 | 4.984% | 1.703% | 0.673% | 0.203% | 0.126% |
| 30, 300 s | 1.264 | 5.902% | 2.222% | 1.072% | 0.421% | 0.161% |
| 30, 3600 s | 1.153 | 4.633% | 1.689% | 0.806% | 0.189% | 0.105% |
| 15, 300 s | 1.082 | 4.724% | 1.857% | 0.981% | 0.329% | 0.126% |
| 10, 300 s | 1.074 | 4.906% | 2.096% | 1.086% | 0.428% | 0.217% |
| 10, 3600 s | 0.974 | 3.890% | 1.745% | 0.932% | 0.343% | 0.126% |
| *normal says* | 1.000 | 4.550% | 0.270% | 0.00633% | 0.0000002% | ~0 |

Their tau=45 row: sd 1.134 / 6.39% / 2.13% / 0.928% / 0.308% / 0.122%. Mine on a
shorter window: 1.153 / 6.399% / 2.019% / 0.862% / 0.315% / 0.168%. **The
measurement is real and reproduces.** |z|>4 is 136x the normal rate (they said
147x); |z|>6 is 0.315%, about 1 in 317 (they said 1 in 325).

### 4b. The artefact check they did not do, and it costs them about a third of the far tail

z is a realised move divided by a **trailing** vol estimate. That ratio is
fat-tailed whenever volatility clusters, even if the settlement move is
conditionally normal. So I re-ran the identical grid with a 1800 s and a 3600 s
ruler. Lengthening the ruler cuts |z|>4 from **0.862% to 0.673%** and |z|>6 from
**0.315% to 0.203%** at tau=45, and sd(z) from 1.153 to 1.050.

So **~22% of the |z|>4 tail and ~36% of the |z|>6 tail is the 300-second ruler
being too short, not a genuine fat tail.** The rest is real: 0.673% against
0.00633% is still 106x. Their "sd(z) between 0.88 and 1.13 bounds any width error
at +/- 13%" is the wrong bound -- the ruler error shows up in the TAIL, not in the
sd, which is the whole point of their own AMENDMENT 20 finding.

**One sub-claim does NOT reproduce.** They say "below |z|=2 the model is if
anything too WIDE (3.33% vs 4.55% at tau=10)". My tau=10 / 300 s gives |z|>2 =
**4.906%**, i.e. slightly too NARROW. Since "keep the normal below |z|=2" is the
load-bearing assumption of their proposed mixture, that matters.

### 4c. The proposal, priced on our own fills and Kalshi's ledger. It stops the bot.

`verify/mix.py`. For each fill I take the `fair` the bot logged, invert it to z,
replace the normal tail with their measured mixture (log-linear between the
grid knots, normal below |z|=2), recompute `fair` and `edge_c`, and apply the
LIVE gates: `PIN = 0.995`, `EDGE_FLOOR = 0.003` (both are pinrun defaults --
`restart_bot.ps1` passes neither).

| | markets kept | closes | losers | net kept | markets dropped | net dropped |
|---|---|---|---|---|---|---|
| TRAIN | **52** | 51 | 2 | +$52.26 | **645** | +$430.63 |
| HOLDOUT | **0** | 0 | 0 | $0.00 | **91** | +$65.86 |

**93% of TRAIN and 100% of the HOLDOUT stops being a trade.** The reason is
arithmetic, not tuning: under the measured mixture the one-sided tail at |z|=3 is
~1.0%, so **`fair` can never reach 0.995 until |z| > ~5.2**. A flat haircut shows
the same cliff -- 0.25c drops 511 of 697 TRAIN markets, 0.50c drops 670 and all
91 holdout markets:

| flat fair haircut | TRAIN dropped (losers, net) | HOLDOUT dropped |
|---|---|---|
| 0.25c | 511 (18, +$325.41) | 75 (2, +$70.77) |
| 0.50c | 670 (21, +$475.65) | **91 (3, +$65.86)** |
| 0.75c | 697 (23, +$482.88) | 91 |

The mixture's largest reduction in `fair` is ~1.2c and it peaks near |z| = 2-3,
not at the extreme -- so it does not "lower fair only at extreme confidence"; it
lowers it most in the middle of our book.

**And it does not help the losses it was built for.** The three worst TRAIN
losses move `fair` by -0.80c, -1.11c and -0.86c and their `edge_c` stays at
2.61c, 6.12c and 2.92c, all far above the 0.3c floor. The mixture would not have
refused a single one of them; it would only have refused the winners.

### 4d. The honest version of the finding is a price ceiling, and that is a wash

If the model is 9-136x overconfident at the extreme, the money question is what
we will PAY. `PRICE_CEILING` is already **0.980** (`pinrun.py:3101`, moved
98.8c -> 98.0c on 2026-09-09) and it fired **1,345** times. Tightening it:

| ceiling | TRAIN blocked (losers, net) | HOLDOUT blocked (losers, net) |
|---|---|---|
| 0.975 | 250 (7, -$18.17) -> blocking **gains $18** | 42 (2, +$5.31) -> blocking **costs $5** |
| 0.970 | 356 (9, +$48.61) -> costs $49 | 52 (2, +$17.43) -> costs $17 |
| 0.965 | 428 (9, +$149.65) -> costs $150 | 62 (2, +$40.26) -> costs $40 |

By price bucket, c/contract TRAIN / HOLDOUT: <0.90 **6.85 / 6.93**; 0.94-0.96
0.16 / -11.44; 0.96-0.97 2.67 / 3.42; 0.97-0.98 0.75 / 2.18; 0.98-0.99
0.01 / -1.29. The cheap fills are the best in both halves (n = 39 / 4), and the
0.98-0.99 bucket is the worst in both -- but 0.980 is already the ceiling, so
there is ~1c of room and it is worth about nothing.

**Verdict: the measurement SURVIVES with a third of the far tail attributed to the
ruler. The rule is REFUTED -- it would have taken the bot to 0 trades in the
holdout.** The finding's real use is what it says about the 45-second leg, not
about `conf_of`.

## 5. realised-vol #2 -- our entries sit in a fatter tail than a random moment. **SURVIVES, and it is worse than they said.**

`verify/fillz.py` -- index tape only, z computed at each fill's OWN entry second
and OWN tau, 783 of 788 fills joined (5 lost to index gaps).

| | n | sd(z) | \|z\|>2 | \|z\|>3 | \|z\|>4 | \|z\|>6 | \|z\|>8 |
|---|---|---|---|---|---|---|---|
| **our fills, all** | 783 | **1.638** | 10.47% | 5.36% | 2.94% | **1.15%** | 0.64% |
| our fills, TRAIN | 696 | 1.672 | 10.63% | 5.32% | 3.02% | 1.29% | 0.72% |
| our fills, HOLDOUT | 87 | 1.336 | 9.20% | 5.75% | 2.30% | 0.00% | 0.00% |
| exogenous grid, tau=45 | 14,267 | 1.153 | 6.40% | 2.02% | 0.86% | **0.32%** | 0.17% |

They reported sd(z) = 1.439 and |z|>6 = 0.861%; I get **1.638 and 1.15%**, so
our own entry moments are **3.7x fatter at |z|>6** than an unconditional moment,
not 2.8x. Direction and conclusion identical, magnitude larger.

The post-fill split reproduces in both halves -- TRAIN losers vs winners median
|z| **3.54 vs 0.50**, absolute miss in units of the coin's typical 45-second miss
**1.53 vs 0.21**; HOLDOUT **3.43 vs 0.55** and **2.95 vs 0.25** (3 losers). That
separation is close to tautological (a loser IS a market where the index crossed)
so it earns nothing; the unconditional comparison is the finding.

**Confound not cleared, and it cannot be from this sample:** a signal requires the
model to be confident, and confidence is itself a function of recent quiet, so
"our entry seconds" is a selected population. The hunt said this. I agree and I
cannot fix it either. **SURVIVES as a diagnostic; pre_entry: false, correctly.**

## 6. realised-vol #3 -- "calm 300-second ruler is dangerous". **The KILL survives. The gradient on OUR MONEY does not exist, and in the holdout it runs the other way.**

`verify/fillz.py`, rv5 = realised 1-second index vol in the 300 s before entry,
ranked against that coin's own median across our fills.

| TRAIN quintile (139-140 markets each) | losers | net | $/market | median rel-vol |
|---|---|---|---|---|
| q1 calmest | 5 | **+$78.11** | 0.562 | 0.55 |
| q2 | 6 | +$142.81 | 1.027 | 0.78 |
| q3 | 3 | +$73.40 | 0.528 | 0.96 |
| q4 | 5 | +$74.93 | 0.539 | 1.16 |
| q5 stormiest | 4 | +$112.06 | 0.800 | 1.57 |

Loss counts 5/6/3/5/4 -- flat. **Blocking the calmest fifth would have cost
$78.11**, not $52.30. Not monotone in either money or losses.

| HOLDOUT tercile (29 each) | losers | net | $/market |
|---|---|---|---|
| calmest | **0** | **+$54.08** | **+1.865** |
| middle | 1 | +$8.07 | +0.278 |
| stormiest | 2 | -$0.11 | -0.004 |

**In the holdout the calmest third is the BEST third and the stormiest is the
worst** -- the exact reverse of the index-side gradient. **The kill stands and is
more expensive than they priced it. Do not build a calm-market gate. SURVIVES as
a kill; the "calm is dangerous" framing is REFUTED on our money in both halves.**

## 7. realised-vol #4 -- jumps do not cluster once the level is known. **CONFIRMED.**

`verify/jump.py`, causal EWMA sigma (halflife 300 s, 600-return warm-up),
78,492 coin-minute pairs, 2026-09-17..09-21, index feed only.

- 6-sigma: 14.55% of all minutes carry one; **16.46%** of the 11,419 minutes
  after a jump minute; **14.23%** of the 67,073 after a quiet one -> **1.156x**
  (they said 1.12x).
- 8-sigma: 6.66% after a jump vs 6.95% after quiet -> **0.958x**, i.e. the
  wrong way (they said 1.014x).
- Backward-looking companion: r(log realised 1-second vol, minute to minute) =
  **0.991** on the same 78,492 pairs. The estimator finds clustering when it is
  there; it is not blind.

**CONFIRMED. A jump cooldown has no statistical basis and would block a sixth of
all entry opportunities for a 1.16x change in a rate. Do not build it.**

## 8. realised-vol #5 -- no cushion floor pays. **CONFIRMED, and in the HOLDOUT the sign flips.**

Cushion = `|spot - strike| / sigma` straight from the bot's own `signal` record.

| TRAIN floor | blocks | of which losers | avoids | gives up | NET |
|---|---|---|---|---|---|
| 1 sigma | 43 | 0 | $0.00 | $64.77 | **-$64.77** |
| 2 sigma | 97 | 6 | $108.20 | $164.66 | **-$56.46** |
| 3 sigma | 166 | 9 | $226.01 | $254.37 | **-$28.36** |
| 4 sigma | 254 | 13 | $322.56 | $380.33 | **-$57.78** |
| 6 sigma | 417 | 16 | $387.63 | $628.60 | **-$240.97** |
| 8 sigma | 551 | 20 | $528.64 | $845.41 | **-$316.77** |

Every floor loses money. TRAIN losers' median cushion 3.24 vs winners' 5.13 --
the direction they describe. **In the HOLDOUT the losers' median cushion is
7.14 against the winners' 6.50 -- HIGHER.** Every holdout floor loses money too
(-$14.18 at 1 sigma up to -$88.63 at 6). **CONFIRMED kill, strengthened.**

## 9. realised-vol #6 -- "the middle of the settlement window is where the money dies". **REFUTED out of sample.**

| tau band | TRAIN mkts / losers / $ per market | TRAIN ex-09-19 | **HOLDOUT** |
|---|---|---|---|
| <= 10 s | 76 / 1 / **+2.48** | 74 / 1 / +2.48 | 10 / 0 / **+4.28** |
| 11-20 s | 129 / 4 / +1.24 | 124 / 4 / +1.10 | 8 / 1 / +1.98 |
| 21-35 s | 349 / 15 / +0.24 | 325 / 11 / +0.79 | 28 / 0 / **+1.84** |
| 36-60 s | 143 / 3 / +0.36 | 101 / 1 / +1.28 | **45 / 2 / -0.99** |

TRAIN reproduces to the cent. **But in the holdout the 21-35 band has ZERO losers
and makes +$1.84 a market, while the 36-60 band loses $44.38 with 2 of the 3
losers.** The specific claim ("the middle, not the 45-second leg") is refuted.

What survives is the plain gradient the map already has: **short tau is better**.
tau <= 10 earns 5.19 c/contract in TRAIN and 4.53 in HOLDOUT; tau 36-60 earns
0.55 and **-2.02**. That is the same late-leg fact the missed-deals work priced,
not a new finding. **REFUTED as stated; the underlying tau gradient SURVIVES.**

---

## 10. cross-coin #1 -- the model's mistakes are correlated across coins. **CONFIRMED, and the one close is WORSE than they described.**

I rebuilt 2026-09-11 **12:30Z (08:30 ET)** from the index alone (`verify/close1.py`),
strike = the mean of the previous window's 60 prints, mu and sd at tau=45 with
the bot's own `var_factor`:

| coin | model z vs strike at tau=45 | surprise z | crossed? |
|---|---|---|---|
| HYPE | -8.66 | **+11.10** | YES |
| NEAR | -8.37 | +8.81 | YES |
| DOGE | -8.05 | +9.48 | YES |
| BCH | -6.88 | +11.22 | YES |
| XRP | -4.03 | +11.11 | YES |
| BNB | -3.85 | +7.63 | YES |
| SOL | -3.58 | +9.15 | YES |
| BTC | +2.12 | +7.03 | . |
| ETH | +6.48 | +10.72 | . |
| ZEC | +12.31 | +22.42 | . |
| ADA | +0.66 | +10.26 | . |

**Every one of the eleven coins' surprises is POSITIVE, from +7.03 to +22.42.**
Of the 9 coins the model was more than 2.58 sigma sure about, **7 crossed**, not
6 of 8. The crossings are by 3.6 to 8.7 sigma, so it is not a rounding hair, and
the window has full 1-second coverage on every coin, so it is not a feed gap.
The next close (12:45Z) then moved every coin +11 to +30 sigma the other way.

This is not 1.22 effective independent bets. In the tail it is **one bet**.

Their dollars-at-risk table reproduces almost exactly (mine / theirs): TRAIN
median **$42.41** / $41.02, p90 **$145.01** / $142.13, max **$312.79** / $312.79;
HOLDOUT median **$75.20**, p90 **$149.20**, max **$237.74** -- all three exact.
Worst close realised **-$108.86** (09-19 23:45 ET, HYPE + XRP, $312.79 at risk).
21 of 509 TRAIN closes lost money (4.1%, -$646.55 between them); 3 of 70 in the
holdout (4.3%, -$92.83).

**CONFIRMED. Hedge-safe: it proposes nothing that gates anything.**

## 11. THE SIZE-UP NUMBER (what the operator asked for). **The naive answer is wrong by nearly half.**

Two facts from the logs decide this:

1. **We already get 94.9% of what we ask for** -- 38,059 of 40,123 contracts
   requested, and 88.7% of markets fill in full. Execution is not the cap.
2. **But in 437 of 774 markets (56.5%) the BOOK ran out before SIZE did**
   (`take_n < size`). A SIZE increase changes nothing in those.

Splitting our money that way:

| | markets | net | losers | worst losses |
|---|---|---|---|---|
| **book-binding** (SIZE increase does NOTHING) | 437 | +$199.82 | 14 | BTC -107.95, BTC -66.34, XRP -64.95, NEAR -59.09 |
| **size-binding** (SIZE increase scales this) | 337 | +$347.07 | 12 | BNB -61.75, BNB -57.76, HYPE -31.27 |

**The four biggest losses we have ever taken are all in the half a size increase
cannot reach.** So size-up is asymmetric in our favour on this tape:

| | net | worst single close | max at risk in one close |
|---|---|---|---|
| **today (x1.0)** | +$546.89 | **-$108.86** | $312.79 |
| SIZE x1.5 | +$720.43 | -$108.86 | $394.67 |
| **SIZE x2.0** | **+$893.96** | **-$123.51** | **$526.23** |
| SIZE x3.0 | +$1,241.03 | -$185.26 | $789.34 |
| *(naive linear x2, what a spreadsheet says)* | *+$1,093.78* | *-$217.73* | *$625.57* |

x2 buys about **+63% of the money for +13% of the worst close** -- not +100% for
+100%. Contracts grow by **between x1.00 and x1.28**, never x2.

**Four things that arithmetic does NOT include, and every one cuts against it:**

- It assumes the book had **unlimited depth above SIZE** in the 337 size-binding
  markets. The true depth is not logged (that is exactly what kalshi-book's S2
  asks for). x1.00 on contracts is equally consistent with the data.
- A bigger order **sweeps deeper and pays worse**. Our own fills already show
  sweeps reaching 3c to 86c below the ask seen. Margin per contract falls at
  larger size and I cannot say by how much.
- `close_budget` is **exactly 2.00 x SIZE** (median spent $158 against median
  size 79, verified on 478 refusals), so doubling SIZE doubles the per-close
  dollar cap automatically. The 478 turned-away coin-markets would partly become
  fills -- more markets than this table counts, and finding 10 says their losses
  arrive together.
- **The tail is a single-close basket event** (finding 10). A close holding 6
  coins at $626 at risk, on a day like 2026-09-11 12:30Z, loses most of it at
  once. Nothing downstream catches that: `--loss-abort -60.00` fires after the
  close resolves and every leg is already bought.

## 12. cross-coin #2 -- multi-coin closes are our best closes. **The ladder reproduces; the CAUSAL reading does not.**

| coins in the close | TRAIN closes / mkts / net / c-per-contract / bad | HOLDOUT |
|---|---|---|---|
| 1 | 340 / 340 / +$179.51 / **1.168** / 13 (3.8%) | 50 / 50 / +$0.54 / **0.019** / 3 |
| 2 | 152 / 304 / +$241.38 / **1.577** / 10 (3.3%) | 19 / 38 / +$62.84 / **2.771** / 0 |
| 3 | 15 / 45 / +$45.24 / **2.608** / 0 | 1 / 3 / +$2.48 / 2.363 / 0 |
| 4 | 2 / 8 / +$16.75 / 3.460 / 0 | - |

That is their table to the cent, and it does reproduce in the holdout.

**But the rank effect does not survive a tau control.** They attribute it to the
later leg buying more of the variance collapse. Splitting TRAIN by (tau band x
rank):

| | rank 1 | rank 2 |
|---|---|---|
| tau <= 20 | 3.615 c/ct (130 mkts) | 4.189 (75) |
| tau 21-35 | **0.875** (272) | **-0.332** (77) |
| tau 36-60 | **-0.272** (107) | **+3.000** (36) |

The sign flips between bands. Median tau by rank is 29 / 24 / 27 and median price
0.973 / 0.965 / 0.966, so rank IS partly a tau-and-price proxy, and once tau is
held the second leg is not reliably better. n per cell is 36-77.

**The confound they named is also not cleared and I could not clear it either:** a
2-coin close is a close where two takeable offers existed, so the ladder is
partly a market-quality proxy. **WEAKENED. The paper-arm test they propose
("more coins, same money") is still the right test and still risks nothing --
but it should be pre-registered on c/contract INSIDE a tau band, not overall.**

## 13. cross-coin #3 -- `--max-positions` is dead code; `close_budget` is the lever. **CONFIRMED exactly.**

My own count over all 128 live runs: `max_per_close` / `max_positions` refusals
**0**; `close_budget` refusals **478**, all distinct (close, coin) pairs, on
**70 closes**. Median `spent` $158.00 against median `size_now` 79.0 -> the
budget is **2.00 x SIZE exactly**. By ET day: 09-14 126, 09-15 72, 09-16 63,
09-17 70, 09-18 90, 09-19 18, 09-20 21, 09-21 10, 09-23 8.

Full gate census, so nobody has to recount it: `no_offer` 6,989, `edge_floor`
3,262, `price_ceiling` 1,345, `depth_floor` 1,250, `confidence` 1,024,
`close_budget` 478, `book_stale` 258, `early_once` 213, `both_sides` 150,
`index_stale` 111, `rebuy_band` 103, `jump_against` 93, `against_thin` 53,
`market_attempts` 43, `book_suspect` 35, `staged_none` 30, `max_per_market` 28,
`dump_guard` 21, `early_wide` 18, `no_sigma` 18, `early_cheap` 8.

**CONFIRMED.** Their honest refusal to price the 478 is correct -- the gate fires
before the book is read, so no log line knows whether an offer existed.
**Hedge-safe: moving the check after the book read changes when we refuse, not
what; it must still go through a paper arm because a stale price read there once
killed the live bot.**

---

## 14. exchange-books #1 -- 41% of our fills sit on coins with no feed. **CONFIRMED to the cent. The DISK argument is wrong.**

Every per-coin number reproduces exactly from my own ledger join (788 markets,
+$548.75):

| coin | feed? | markets | net | losers (cost) |
|---|---|---|---|---|
| NEAR | no | 62 | **-$46.64** | 3 (-$120.91) |
| BNB | no | 93 | +$12.38 | 5 (-$138.67) |
| BTC | yes | 137 | +$20.37 | 5 (-$237.52) |
| HYPE | no | 95 | +$33.92 | 3 (-$105.09) |
| XRP | yes | 100 | +$67.50 | 2 |
| DOGE | yes | 74 | +$100.11 | 3 |
| ETH | yes | 61 | +$100.41 | 1 |
| SOL | yes | 96 | +$112.61 | 3 |
| ZEC | no | 70 | +$148.09 | 1 |
| ADA / LTC / BCH | yes | **0** | - | - |

With a feed 468 markets +$400.99; without 320 markets +$147.76. **The HOLDOUT
strengthens it: feed coins +$109.41 on 52 markets with 1 loser; no-feed coins
-$43.55 on 39 markets with 2 of the 3 losers (NEAR, HYPE).**

Venue symbol lists verified directly: Coinbase carries ADA, BCH, BTC, DOGE, ETH,
LTC, SOL, XRP; Bitstamp the same eight. **BNB, HYPE, ZEC and NEAR are on no
venue we record.**

**CORRECTION to their disk argument.** Measured from file sizes on 2026-09-22:
bitstamp 0.14 GB/day, coinbase 0.11, gemini 0.05, kraken 0.02, index_replica
0.01 -- **feed_data is 0.33 GB/day out of a 3.99 GB/day total. kalshi_data
is 3.66 GB/day.** ADA+BCH+LTC are 30.5% of bitstamp's bytes, so dropping them
saves about **0.08 GB/day, 2% of the burn.** It is free to do and it buys no
disk time. **At 3.99 GB/day with 19.40 GB free and a 6 GB hard stop, the
collection deadline is 3.4 days, tighter than the map's 4.6-4.8.**

**Confound, total and unfixable:** "has a feed" is a fixed coin set, so the
comparison is entirely "NEAR and HYPE are our worst coins". The absence of a feed
does not cause the loss; it makes it unmeasurable. That is their claim too.
**SURVIVES as an inventory. Buys no money by itself.**

## 15. exchange-books #2-#6 -- the constituent-quote nulls and negatives. **NOT RE-DERIVED; I could not, and neither could anyone at this n.**

These are: no pre-entry quote feature separates losers (#2); rebuilding sigma
from the venues would make the bot MORE confident where it lost (#3); an
exchange-built jump alarm is not earlier than the index one (#4); venue depth
does not separate losers and its best cut fails three artefact checks (#5);
venue stress predicting a picked-off fill has no power at n=5 (#6).

**I did not re-run them.** Their TRAIN population is 415 markets with 13 losers;
the holdout adds **3 losers**. My holdout MDE says a subgroup needs a **3.0x
lift** to show at all. Re-running a 53-cut search against 3 events would produce
noise dressed as confirmation, and the brief's rule is that "no power" and "no
effect" are different results.

What I can say without re-running:

- **#3 (venue-built sigma is harmful) is the one worth acting on, and it is an
  argument by direction, not significance.** My independent grid supports the
  underlying point from a different side: lengthening the ruler (300 s to
  3600 s) LOWERS the fat tail, so shortening it or rebuilding it from a noisier
  source raises it. Do not rebuild sigma from the venues.
- **#4 (jump alarm) cannot block a hedge** -- an alarm only ever fires one. The
  risk is 28 false triggers on winners, which is cost, not a blocked hedge.
  Their reading is right.
- **#6's "5 picked-off fills" vs the map's "27 closes"** is still unreconciled,
  and my section 2 above explains part of the gap: ask_seen minus exec_price is
  dominated by sweep depth, so the definition decides the population.

**All five stand as NOT FOUND, explicitly not as PROVEN ABSENT.**

## 16. other-venues #1 -- polymarket.us / Chainlink TWAP. **The arithmetic is EXACTLY right and the inference from it is backwards.**

I recomputed sd(settle - mu) in units of one-second index sigma with the repo's
own weighting, and every figure matches to four decimals: at tau=30 **1.6206 /
0.3241 / 0.1080**; at 45 **2.9531 / 0.5906 / 0.1969**; at 60 **4.5280 / 0.9056 /
0.3019**. Files confirmed present: C:\kals\poly_us.py, poly_close.py,
polymarket_key.json; **no poly_data directory exists.**

**But the ratio is exactly N_twap / N_kalshi for every tau <= 60** -- 5.000000 at
tau 10, 20, 30, 45 and 60. It is the trivial statement that a 300-second average
has 5x less variance than a 60-second one. Quoting it per-tau makes it read as a
tau-structure finding; it is not one.

**And lower settlement variance is not automatically an edge -- it is the
opposite of our edge.** Our whole pin rests on the variance collapsing LATE, so a
cushion becomes near-certain in the last 45 seconds and the market has not
finished pricing it. On a 15-minute TWAP the collapse happens 15x earlier, so the
near-certain side is near-certain for minutes and would already be quoted at
99.9c. There is no 96-98c left to buy. Their own "unknown and decisive -- does
anyone quote into the last 30 seconds there" is the whole question, and it points
the other way from the headline.

**WEAKENED: the arithmetic SURVIVES, the "5-15x structurally weaker loss class"
inference is REFUTED as stated.** A read-only recorder still costs almost no
disk and answers it; it is not the priority the finding implies.

## 17. other-venues #2 -- Crypto.com is dead as a pin venue. **CONCLUSION CONFIRMED. THE NUMBERS DO NOT REPRODUCE.**

verify/cdc.py: 139,007 instruments carrying an expiry_timestamp_ms, 162 book
hour-files, restricted to contracts whose own OPEN_TIME/CLOSE_TIME span is 15
minutes. Seconds before expiry of the last book reading that still carried a
quote, on the venue's OWN timestamp:

| coin | n | p25 | **p50** | p75 | their p50 |
|---|---|---|---|---|---|
| BTC | 543 | 5.5 | **21.8** | 39.1 | 0.9 |
| ETH | 545 | 29.0 | **29.6** | 35.8 | 1.4 |
| SOL, XRP, DOGE, ADA, BCH, LTC, LINK, AVAX, DOT, HBAR, SHIB | ~540 each | 52-59 | **59.3-59.9** | ~59.9 | 41.8-42.7 |
| FLOKI | 539 | 57.6 | 63.6 | 117.9 | ~42 |
| PEPE / BONK | 538 | ~59.7 | 152 / 153 | 312 / 331 | ~42 |
| CRO | 499 | 124.2 | 155.3 | 268.5 | 121.4 |
| XLM | 480 | 312.1 | 321.0 | 330.7 | 315.0 |

**The book is gone about 60 seconds before expiry on eleven coins, not about 42.**
And **10.5% of contracts have their last quote in the 40-45 s bin, not 58.8%.**
BTC and ETH survive to 21.8 s and 29.6 s, not 0.9 s and 1.4 s. My last poll lands
a median **25.2 s AFTER** expiry (theirs: 1.5 s), so our definitions of "the last
poll" differ and theirs should be re-derived before either set is quoted.

**The conclusion is unaffected and is in fact stronger: the book vanishes BEFORE
the window our edge lives in, on nearly every coin.** But the specific numbers in
their entry should not be quoted. **CONFIRMED as a kill; the table is REFUTED.**

## 18. other-venues #3, #4, #5 -- Crypto.com is worse-informed, does not lead, no arbitrage. **NOT RE-DERIVED.**

These three rest on the same cdc book that section 17 shows I read differently
from them. Re-deriving the Brier comparison and the 866 matched pairs needs the
strike-gap regression rebuilt, and I ran out of budget. They are internally
consistent, they all point the same way (do not build a cross-venue gate), and
the direction is corroborated by the structural kill in 17. **I record them as
UNVERIFIED, not as confirmed.** Their author caught and corrected their own worst
error (668 "free money" packages down to 66), which is the behaviour that usually
means the rest was done carefully.

## 19. other-venues #6 -- on-chain is the wrong feed. **SURVIVES as an argument; the disk premise is wrong.**

The mechanism argument is sound and needs no data: settlement is a 60-second
average of an index built from the exchange order books we already tape, so the
price is made on the venues, not on the chain, and BTC blocks (10 min), ETH
blocks (12 s), funding (hours) and basis (hours) are all slower than a bet that
is already half-settled when we enter.

The **disk premise is wrong in our favour**: feed_data is 0.33 GB/day of a
3.99 GB/day burn, so adding a liquidation feed costs nothing measurable. The real
hog is kalshi_data at 3.66 GB/day, and orderbook_delta is most of it.
**SURVIVES.**

---

## 20. COULD A HEDGE EVER BE DELAYED? Checked in the code, not assumed.

- `hedge_should_fire(belief)` is `belief < HEDGE_BELIEF` (0.25). Anything that
  LOWERS the model's confidence makes the hedge fire **earlier, never later**.
  That is the safe direction, and it is the direction realised-vol #1 pushes.
- **But there is a live trap.** `hedge_normal_ok` (pinrun.py:1838) requires
  `(1 - belief) >= PIN and 0 < ask <= PRICE_CEILING`. It is OFF today
  (`HEDGE_NORMAL = False`, and `--hedge-normal` is not in `restart_bot.ps1`).
  **If anyone ever turns it on AND ships a fatter `conf_of`, the hedge is
  silently blocked**, because under the measured mixture `1 - belief` can
  essentially never reach 0.995. That is precisely the 2026-09-19 failure class
  that cost $106.73 in one day. Written down here so it is priced before, not
  after.
- `level_age_ms` and `imb` (kalshi-book #1, #2) are read only at the entry
  decision. Neither appears anywhere in the hedge, panic-hedge or early-leg
  paths. As a size multiplier (S1) they cannot refuse anything at all.
- `close_budget` (cross-coin #3) is an entry gate. Moving it after the book read
  changes WHEN we refuse, not WHAT. Still a behaviour change; still needs an arm.
- The exchange jump alarm (exchange-books #4) can only ever FIRE a hedge, never
  suppress one. Its cost is false alarms, not a blocked hedge.

**No candidate in this sweep, as written, can delay a hedge. One combination
can: fatter `conf_of` plus `--hedge-normal`.**

## 21. LOOKS, HONESTLY COUNTED

Declared by the five hunts: realised-vol 15, kalshi-book ~75, exchange-books 101,
cross-coin 14, other-venues ~35. **~240.** I added roughly **55** of my own
(level-age thresholds x6, exact/inexact split, within-coin, leave-one-day-out,
2 permutations, 4 imb thresholds, CLEAN/REST, 2 imb-within-bucket cuts, the
cheap-fill marker and its price-band control, the mixture pricing plus 6 flat
haircuts, 8 price ceilings plus the bucket table, 6 cushion floors x 2 halves,
3 tau-band populations, 2 ladder tables plus the rank x tau grid, 2 calm-quintile
tables, 2 jump-cluster rates, the 12-cell tau x ruler grid, 4 size-scalings).

**Bar: 0.05 / 295 = 0.00017.** The best pre-entry p anywhere in the sweep is
kalshi-book #1's within-day dollar permutation at 0.0006, and that number is
carried entirely by 2026-09-19. **Nothing clears.** The only cut that does is the
post-fill "came back cheap" marker (holdout Fisher p = 0.0022, TRAIN 0.0054),
and it can gate nothing.

## 22. VERDICTS

| # | candidate | verdict |
|---|---|---|
| RV1 | fat-tail mixture inside `conf_of` | **measurement SURVIVES** (~1/3 of the far tail is the 300 s ruler); **rule REFUTED** -- it drops 645/697 TRAIN and 91/91 HOLDOUT fills, and would have refused none of the three worst losses |
| RV2 | our entry seconds are fatter than random | **SURVIVES, stronger** (3.7x at \|z\|>6, not 2.8x). Diagnostic only |
| RV3 | "calm ruler is dangerous", do not gate on it | **kill SURVIVES**; the calm quintile made +$78.11 in TRAIN and was the BEST third in the HOLDOUT, so the framing is **REFUTED on our money** |
| RV4 | jumps do not cluster; no cooldown | **CONFIRMED** (1.156x at 6 sigma, 0.958x at 8, companion r = 0.991) |
| RV5 | no cushion floor pays | **CONFIRMED, stronger** -- in the HOLDOUT losers' cushions are LARGER than winners' |
| RV6 | the middle of the window is where money dies | **REFUTED out of sample** -- in the HOLDOUT tau 21-35 has 0 losers and tau 36-60 holds 2 of 3. The plain short-tau gradient survives |
| KB1 | CLEAN = level age >= 100 ms AND imb <= 0.5 | **WEAKENED.** Level-age half ranks losses (3 of 3 in the HOLDOUT) and is not a tau/price/leg proxy. Every dollar claim is one bug day. `imb` half **REFUTED** -- no HOLDOUT separation, 25.7% of its rows arrived after we traded |
| KB2 | "came back >= 2c under the ask" | **SURVIVES as a marker** (HOLDOUT 2 of 3 losers, p = 0.0022) but the **mechanism is REFUTED** -- it is mostly sweep depth and average price paid |
| KB3 | nine book-shape nulls | **SURVIVES as a kill**, with the MDE restated. One number corrected (level-age dollars) |
| CC1 | the model's misses are correlated across coins | **CONFIRMED, worse** -- 7 of 9 confident coins crossed at 12:30Z on 09-11, with all eleven surprises positive (+7.0 to +22.4 sigma) |
| CC2 | multi-coin closes are better; 2nd/3rd leg better | **WEAKENED** -- the ladder reproduces in the HOLDOUT, but rank flips sign inside a tau band, so it is partly tau and partly market quality |
| CC3 | `--max-positions` is dead; `close_budget` is the lever | **CONFIRMED exactly** (0 vs 478 refusals, budget = 2.00 x SIZE) |
| EB1 | 4 traded coins have no feed; 3 recorded coins are never traded | **CONFIRMED to the cent, HOLDOUT strengthens**; the **disk argument is WRONG** (saves 2% of the burn) |
| EB2-6 | quote, ruler, jump-alarm, depth and pickoff results | **NOT RE-DERIVED.** Not enough holdout events to test. Stand as NOT FOUND |
| OV1 | polymarket.us TWAP is 5-15x tighter | **arithmetic CONFIRMED exactly**; **inference REFUTED** -- the ratio is trivially N/N and an earlier collapse is priced earlier, which removes the edge rather than creating it |
| OV2 | Crypto.com withdraws the book before our window | **kill CONFIRMED and stronger**; **the table is REFUTED** (60 s not 42 s; 10.5% not 58.8%; BTC 21.8 s not 0.9 s) |
| OV3-5 | worse-informed, no lead, no arbitrage | **UNVERIFIED.** Direction corroborated by OV2 |
| OV6 | on-chain is the wrong feed | **SURVIVES**; disk premise corrected (feed_data is 8% of the burn) |

## 23. WHAT I WOULD ACTUALLY DO, RANKED

1. **Log the book (kalshi-book's S2) and change nothing else.** Put `imb`,
   `our_sz`, `opp_sz`, `spread_c` and the existing `level_age_ms` /
   `level_age_exact` into `signal` AND `refused`. Four dictionary fields. It
   blocks nothing, gates nothing, cannot touch a hedge, and it is the only way
   any of section 1 ever becomes testable from data the bot actually saw rather
   than from a tape where a quarter of the rows arrive late. **Do it regardless
   of every other verdict here, and do it while the disk still has 3.4 days.**
2. **Do not ship the fat-tail mixture.** It would have stopped the bot trading.
   If confidence honesty is wanted, the lever is `PRICE_CEILING`, already at
   0.980, and tightening it to 0.975 is worth +$18 in TRAIN and -$5 in HOLDOUT.
3. **Do not ship any of: a calm-market gate, a jump cooldown, a cushion floor, a
   venue-built sigma, a cross-venue confirmation gate, a CLEAN/REST entry
   block.** Each is priced above and each loses money or is one bug day wide.
4. **The one thing with real money in it is SIZE, and section 11 is the honest
   number:** x2 buys about +63% of the profit for +13% of the worst close,
   because 56.5% of our markets are already book-limited and the four worst
   losses we have ever taken are all in that half. The uncertainty is one-sided
   and large -- contracts grow between x1.00 and x1.28, and a bigger sweep pays
   worse prices that are not in the arithmetic.
5. **Before any size increase, make "dollars at risk in this close" a live
   number.** It does not exist today; it is only implied inside a `close_budget`
   refusal. The tail acts on exactly that quantity (section 10) and
   `--loss-abort` cannot catch it because every leg is bought before the close
   resolves.

## 24. RESOURCES

Free RAM 2.86 GB at the end (2.82 at the start); free disk 19.40 GB.
`kalshi_collector.py` and `crypto_feeds.py` both verified alive -- the newest
`cfbenchmarks_value` and `coinbase` hour files were both being written at
07:18Z, the current hour. No process was started, stopped or signalled. Nothing
under `C:\kals` was written. Everything I produced is in
`scratchpad/newedge/verify/` and this file.

**Total burn measured at 3.99 GB/day (kalshi_data 3.66, feed_data 0.33). With
19.40 GB free and a 6 GB hard stop that is 3.4 days, not 4.6.**

---

## 25. APPENDIX -- "would one more loss have made the day negative?"

Not part of the assignment, but it is the operator's live question and it falls
straight out of the same ledger join, so it should not have to be re-derived.
Kalshi's ledger, by ET day, every pin crypto market:

| ET day | markets | net | losers | loss $ | worst single market |
|---|---|---|---|---|---|
| 09-08 | 31 | -$40.59 | 1 | -$52.60 | -$52.60 |
| 09-09 | 40 | +$48.74 | 0 | - | - |
| 09-10 | 44 | +$0.23 | 3 | -$36.32 | -$17.60 |
| 09-11 | 49 | +$1.25 | 2 | -$31.77 | -$19.61 |
| 09-12 | 94 | +$38.06 | 4 | -$33.76 | -$18.88 |
| 09-13 | 49 | +$114.78 | 1 | -$1.10 | -$1.10 |
| 09-14 | 61 | +$81.10 | 2 | -$64.16 | -$34.26 |
| 09-15 | 35 | +$76.32 | 0 | - | - |
| 09-16 | 45 | +$85.11 | 3 | -$21.83 | -$12.14 |
| 09-17 | 55 | +$99.87 | 1 | -$27.87 | -$27.87 |
| 09-18 | 68 | +$91.85 | 0 | - | - |
| **09-19** | 73 | **-$223.46** | 6 | -$402.67 | **-$107.95** |
| 09-20 | 53 | +$109.63 | 0 | - | - |
| 09-21 | 48 | -$2.97 | 2 | -$90.36 | -$59.09 |
| 09-22 | 34 | +$53.70 | 1 | -$2.47 | -$2.47 |
| 09-23 (part) | 9 | +$15.13 | 0 | - | - |

**Yes -- one loss of the size we actually take flips a normal day.** A day makes
$50-$110 and a single bad market costs $30-$108. Concretely: add one 09-21-sized
loss (-$59.09) to 09-22 and the day goes from +$53.70 to **-$5.39**; add it to
09-23 so far and +$15.13 becomes **-$43.96**. Five of the sixteen days are
already in that state (09-08, 09-10, 09-11, 09-19, 09-21).

That is the whole shape of this strategy and it is not new damage: we win about
$1 a market 97 times and lose $30-$100 the other 3. It is also exactly why
section 11's asymmetry matters -- a size increase scales the $1 wins but cannot
reach the four biggest losses, which were all book-limited.
