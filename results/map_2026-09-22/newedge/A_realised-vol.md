# A — realised volatility vs the model (label: realised-vol)

COMPLETE. Read-only. All money from Kalshi's own ledger
(`results/kalshi_ledger.json`, `research/pinledger.pnl`). Index numbers from
the raw `cfbenchmarks_value` tape on EXCHANGE print time, never receive time.

TRAIN = closes up to 2026-09-20 ET. HOLDOUT = 09-21 on, not searched.

## What was built (scratchpad, read-only inputs)

- `volmin.py` — streams 622 hourly `cfbenchmarks_value` files (2026-08-25 →
  2026-09-21T03Z), **23,748,372 prints**, 11 coins, into per (coin, UTC minute)
  realised-variance and jump aggregates from 1-second log returns on the
  exchange `time` field. Jumps are scored against a CAUSAL EWMA sigma
  (halflife 300 s, 600-return warm-up), so every feature is computable before
  the second it scores. Self-test plants a constant-sigma world (must recover
  sigma, must find ~no jumps) and a world with 10-sigma jumps every 2000 s
  (must find them), and checks a 60-second gap is counted, never turned into
  a fake 1-second return. Uses `research/gzsalvage.iter_lines` — 21 of the 622
  hour files needed salvage.
- `fills.py` — our OWN fills. 1,275 `order` records, **823 filled**, over
  **788 distinct markets**, all 788 present in Kalshi's ledger. Entry time
  from `client_order_id` (`pin-<epoch_ms>-…`), which every order carries
  (`t_ms_send` exists on only 69). The ticker stamp was VERIFIED as Eastern,
  not assumed: reading it as UTC+4h reproduces `t_send + tau_at_send` with
  median error 0 s over 1,034 orders; UTC+0h is off by 14,400 s.
- `join.py` — pre-entry features per market, TRAIN/HOLDOUT split.

## Our own fills, the population every risk number below uses

| | TRAIN (≤09-20 ET) | HOLDOUT (09-21+) |
|---|---|---|
| markets filled | 697 | 85 |
| **closes (n)** | **509** | 65 |
| net, Kalshi ledger | **+$482.88** | +$62.65 |
| losing markets | **23** | 2 |
| dollars lost on them | **-$672.08** | -$90.36 |

(Ledger over all 788 filled markets: +$548.75, 26 losers, -$764.91 lost
against +$1,313.66 won.)

## Finding 1 — the 1-second index is not remotely normal, and it is not a tick artefact

Per-coin 1-second log returns, 2026-08-25 → 09-21T03Z, jumps scored against
the causal EWMA sigma:

| coin | 1s returns | sd (bp) | ≥4σ | ≥6σ | ≥8σ |
|---|---|---|---|---|---|
| BRTI (BTC) | 2,175,762 | 0.61 | 1 in 94 | 1 in 291 | 1 in 678 |
| ETH | 2,175,762 | 0.74 | 1 in 114 | 1 in 361 | 1 in 818 |
| SOL | 2,175,760 | 0.94 | 1 in 145 | 1 in 434 | 1 in 845 |
| XRP | 2,175,758 | 0.94 | 1 in 117 | 1 in 311 | 1 in 582 |
| DOGE | 2,175,758 | 1.08 | 1 in 114 | 1 in 315 | 1 in 602 |
| ZEC | 2,175,761 | 1.80 | 1 in 116 | 1 in 274 | 1 in 517 |
| NEAR | 2,175,761 | 1.98 | 1 in 89 | 1 in 252 | 1 in 575 |
| **ALL** | **23,748,221** | 1.14 | **1 in 105** | **1 in 290** | **1 in 601** |

A normal curve says 1 in 15,787 / 1 in 1.0 billion / 1 in 810 trillion.
Observed 6-sigma is **3.5 million times** more common than normal.

Artefact checked: price discreteness. SOL quotes 2 dp on ~$108 (one tick =
0.93 bp) and 48.6% of its 1-second returns are exactly zero, which would
shrink the EWMA sigma and inflate z. But the two most continuous series —
ZEC (0.0% zero returns) and BTC (0.3%) — show the SAME order of jump
frequency, and SOL is the *least* jumpy of all. Discreteness is not what
produces this.


## Finding 2 — THE BIG ONE: the model's own predictive curve, rebuilt exactly, is right in WIDTH and catastrophically wrong in SHAPE

`research/calib.py` in the scratchpad rebuilds pinrun's OWN numbers from the
raw index — `mu = (locked_sum + r*spot)/60` (pinrun.py:2814) and
`sd = sigma_300 * sqrt(var_factor(r,[1.0]))` (pinrun.py:2817), with
`sigma_300` recomputed by pinrun's own `_sig_over(ticks, 300)` rule — and
compares them with the settlement that actually happened (the mean of the 60
prints in `[close-60, close-1]`). `z = (settle - mu)/sd`. Its self-test
fails if an honest world is called fat, or if a world whose ruler window is
calm and whose last 45 s are violent is called honest.

**A) exogenous grid** — every quarter-hour close, every coin, fixed tau.
27,906 samples per tau, 2026-08-25 → 09-21. This is what the INDEX did; it is
not a claim about how often we lose.

| tau | sd(z) | \|z\|>2 | \|z\|>3 | \|z\|>4 | \|z\|>6 | \|z\|>8 |
|---|---|---|---|---|---|---|
| 45 s | 1.134 | 6.39% | 2.13% | **0.928%** | **0.308%** | 0.122% |
| 30 s | 1.128 | 5.34% | 1.99% | 0.946% | 0.344% | 0.115% |
| 15 s | 0.973 | 4.05% | 1.43% | 0.745% | 0.272% | 0.097% |
| 10 s | 0.883 | 3.33% | 1.29% | 0.606% | 0.197% | 0.061% |
| **normal says** | 1.000 | 4.55% | 0.270% | **0.0063%** | **0.0000002%** | ~0 |

The WIDTH is fine — sd(z) is 0.88 to 1.13, so `sigma_300` is not systematically
too small, and simply multiplying sigma would not fix this. **The SHAPE is the
whole problem.** A 4-sigma miss is 147x more common than the model's curve
allows and a 6-sigma miss is ~1 in 325 where the model prices it at ~1 in a
billion. Below |z| = 2 the model is if anything too WIDE (3.3% vs 4.55% at
tau=10), which is why its everyday prices look sane and its rare days do not.

**B) our own fill moments** (entry second, entry tau), TRAIN, n=697 markets /
509 closes: sd(z) = **1.439**, |z|>4 = **2.15%**, |z|>6 = **0.861%**
(1 in 116), |z|>8 = 0.574% (1 in 174).

Our entry moments are **~2.8x fatter in the tail than a random moment**
(0.861% vs 0.308% at |z|>6). Adverse selection is visible in the INDEX
itself, not just in the book: the seconds someone chooses to sell us a 96c
contract are seconds when the index is genuinely about to do something large.
6 of 697 against 2.15 expected; one look; treat as suggestive, not settled.
(HOLDOUT n=85: sd(z)=1.157, |z|>4 = 1.18%, no |z|>6.)

Artefact checked: `var_factor(r, [1.0])` assumes 1-second index increments are
uncorrelated. If they were positively correlated the true variance would be
larger and part of this "fat tail" would really be a WIDTH error. But sd(z)
comes out between 0.88 and 1.13 across taus, which bounds any width error at
about +/-13% -- nowhere near enough to produce a 147x ratio at |z|>4. And
reproducing the bot's own rho assumption is the right thing to do here: the
question is what the MODEL believed, and that assumption is part of the model.

## Finding 3 — the "calm ruler is dangerous" effect is REAL, and it can never pay. Here is exactly why.

This is the most useful thing in this file, because it closes a live idea.

AMENDMENT 20 / `results/RESULTS_ruler.md` found the calmest fifth of the
300-second ruler window misses 4.05x more often than the choppiest. **That
reproduces cleanly here at the settlement horizon** — exogenous grid, tau=45,
n=5,544 per bucket, quintiles of realised 1-second vol in the 5 minutes before
entry (relative to that coin's own median):

| calm -> stormy | \|z\|>3 | \|z\|>4 | \|z\|>6 | **median \|settle-mu\|**, in units of that coin's typical miss | **p99.9 \|settle-mu\|** |
|---|---|---|---|---|---|
| 1 calmest | 3.72% | **1.912%** | 0.595% | **0.531** | 9.39 |
| 2 | 2.33% | 0.992% | 0.289% | 0.766 | 14.06 |
| 3 | 1.53% | 0.505% | 0.126% | 0.988 | 13.08 |
| 4 | 1.68% | 0.649% | 0.307% | 1.286 | 26.34 |
| 5 stormiest | 1.30% | **0.505%** | 0.198% | **2.066** | **37.16** |

Same shape on `rv5/rv60` (the 5-minute ruler against the hour): |z|>4 goes
1.804% -> 0.541%, cleanly monotone, which is precisely the "quiet patch, short
ruler" mechanism.

**And it cancels itself.** Going from calm to stormy the standardised miss
gets 3.8x THINNER while the absolute miss gets 3.9x BIGGER (median 0.531 ->
2.066; at the p99.9 that matters, 9.39 -> 37.16; the single worst, 16.3 ->
153.9, a 9x spread). **A binary pays out on the absolute move against the
cushion, not on z.** A 4-sigma miss in a calm market is 4 sigma of a tiny
number and does not reach the strike. So the regime that looks dangerous in
standardised units is the SAFE one in dollars, and the two effects are not
independent — they are the same fact seen twice.

That is why it does not pay on our own money. Our 697 TRAIN fills, quintiles of
the same feature:

| calm -> stormy | markets | closes | losers | lost | won | net | $/market |
|---|---|---|---|---|---|---|---|
| 1 calmest | 139 | 114 | 6 (4.3%) | -$186.07 | +$238.37 | +$52.30 | $0.376 |
| 2 | 139 | 126 | 6 (4.3%) | -$70.66 | +$248.26 | +$177.60 | $1.278 |
| 3 | 139 | 129 | 3 (2.2%) | -$140.71 | +$216.96 | +$76.26 | $0.549 |
| 4 | 139 | 131 | 4 (2.9%) | -$156.44 | +$224.52 | +$68.08 | $0.490 |
| 5 stormiest | 141 | 120 | 4 (2.8%) | -$118.21 | +$226.86 | +$108.65 | $0.771 |

**Blocking the calmest fifth would have given up $238.37 of winnings to avoid
$186.07 of losses — a net LOSS of $52.30** over 13 days, beside the +$482.88
the whole TRAIN half made. Confidence: high that it does not pay; the
mechanism is measured on 27,721 grid samples, not inferred.

## Finding 4 — jumps do not cluster once you know the volatility level

396,188 coin-minutes. A 6-sigma print appears in 17.15% of minutes overall;
**18.81% after a minute that had one, 16.80% after a quiet one — 1.12x.** At
8-sigma there is nothing at all: 9.14% after a jump minute, 9.01% after a quiet
one.

The backward-looking companion is huge, so this is not a blind estimator: log
realised 1-second vol has **r = 0.716 minute-to-minute** (n=394,815) and
**r = 0.660 five minutes ahead** (n=394,485). Volatility is enormously
predictable. What is memoryless is the STANDARDISED tail, once the causal EWMA
has already absorbed the level.

The level does carry one thing, and it is the Finding-3 gradient again: a
6-sigma print lands in **20.85%** of minutes following the calmest vol quintile
against **15.08%** following the stormiest (n=79,010 each).

**Consequence: "a jump just fired, stand down for a minute" has no statistical
basis.** `--jump-gate` earns its keep by reacting to a move that has already
gone against us in the CURRENT market, not by forecasting the next jump.

Intraday shape of 6-sigma prints, per million 1-second prints (base 3,445):
quietest 10:00 ET at 2,579, busiest 17:00 ET at 4,074. A 1.6x swing, real but
far too small to gate on, and our 24 hourly cells hold 0-3 losers each.

## Finding 5 — no cushion floor pays, in EITHER ruler, and the worst losses had the biggest cushions

Losers' cushion (how far spot already sat on our side of the strike at entry)
is genuinely smaller than winners': median **1.91 vs 2.89** in units of that
coin's typical 45-second settlement miss, and **3.24 vs 5.13** in units of the
model's own 300-second sigma. The signal is real and useless — the
distributions overlap almost completely.

Priced on our own 697 TRAIN fills (dollars are Kalshi's ledger):

| floor: cushion under X x the coin's TYPICAL miss | blocked | losers caught | losses avoided | winnings given up | NET |
|---|---|---|---|---|---|
| 0.25 | 42 | 2 | +$46.42 | -$92.55 | **-$46.13** |
| 0.75 | 80 | 4 | +$81.48 | -$143.81 | **-$62.33** |
| 1.50 | 154 | 8 | +$151.08 | -$241.86 | **-$90.78** |
| 2.00 | 234 | 14 | +$320.14 | -$345.66 | **-$25.52** |
| 3.00 | 363 | 17 | +$370.77 | -$541.61 | **-$170.85** |

The model's own sigma ruler is no better (best cell -$14.07 at a 3-sigma floor,
-$333.17 at 8). **This was the point of trying the absolute ruler instead of
the sigma ruler: the reframing does not rescue it.**

And the decisive detail: the three worst TRAIN losses had cushions of **9.24,
7.64 and 6.73 times the model's own sigma** —

| ticker | day ET | pnl | tau | price | cushion / sigma |
|---|---|---|---|---|---|
| KXBTC15M-26SEP191600-00 | 09-19 | -$107.95 | 45 | 0.980 | 9.24 |
| KXBTC15M-26SEP190200-00 | 09-19 | -$66.34 | 35 | 0.943 | 7.64 |
| KXXRP15M-26SEP192345-45 | 09-19 | -$64.95 | 41 | 0.977 | 6.73 |

No cushion floor that leaves a business standing stops those. They are the
tail of Finding 1, not thin trades.

## Finding 6 — MDE: on our own fills this question cannot be answered yet

509 TRAIN closes, **22 of them contain a losing market (4.32%)**. Clustering by
close, at 80% power and alpha = 0.05/9 looks:

| a regime covering | detectable only if its loss rate is |
|---|---|
| 20% of closes (101) | >= 18.9% vs 4.3% — **4.4x** |
| 33% of closes (169) | >= 15.1% — **3.5x** |
| 50% of closes (254) | >= 13.3% — **3.1x** |

Every volatility effect the index shows is 1.1x to 3.8x. **So the nine null
cuts below are "no power", not "no effect", and nobody should read them as
proof a regime does not exist.** The honest statement: no volatility regime
separates our own losers by enough to be worth acting on, and the measurable
mechanism (Finding 3) says the direction would be wrong anyway.

## Refuted / not supported

- **Saturday.** The weekday table shows Saturday at 10 losers in 167 markets
  (6.0%), -$185.41 net, the only negative weekday. It is **entirely
  2026-09-19** (73 markets, 6 losers, -$223.46 — the known-bug day where gates
  blocked hedges). The other Saturday, 09-12, was 94 markets, 4 losers,
  **+$38.06**. Two Saturdays is n=2 days. Not a finding.
- **Coin-level jumpiness.** BTC (0.61 bp/s) and BNB (0.59 bp/s) are our two
  quietest coins and carry $376 of the $672 lost — which reads like Finding 3
  at the coin level. Ex-09-19 it vanishes: quiet coins (BTC/BNB/ETH) $1.24 a
  market on 233, the other six $1.07 on 391. The two JUMPIEST coins, ZEC
  (1.80 bp/s) and NEAR (1.98), are our best and our worst. No relationship.
- **AMENDMENT 20's `max(300s, 3600s)` ruler as a FILTER.** At entry, the ratio
  sd3600/sd300 is **1.062 median on our 23 losers and 1.070 on our 674
  winners** — indistinguishable. It is above 1 on 62.7% of our fills, so
  switching to the max would have raised sigma on most of them and lowered
  confidence on winners and losers in the same proportion. As a humility knob
  it may still be right (Finding 3 says the shape needs fixing); as a way of
  picking out the losers it has nothing.
- **Market-wide stress.** 6-sigma prints across all 11 coins in the 15 minutes
  before entry: the 60+ bucket (28 markets) has zero losers and the 10-29
  bucket (272 markets) has 11. Backwards, and not close to significant.
- **ET hour of the close.** 24 cells, 0-3 losers each. Worst is 16:00 ET
  (-$77.83 on 29 markets) and it is two fills on 09-19 and 09-14. Nothing
  survives 24 looks.
- **Absolute vol level, 5 / 15 / 60 minute windows, terciles.** Loss rates
  2.2%-4.3% everywhere; no monotone dollar gradient.

Cuts tried, all counted: rv5_rel, rv15_rel, rv60_rel, rv5/rv60, 6-sigma count
last 60 min, 8-sigma count last 60 min, market-wide 6-sigma last 15 min, ET
hour, weekday, rv5_rel quintiles, sd3600/sd300 at entry, coin, tau, absolute
cushion floor, sigma cushion floor. **15 looks. The bar was 0.05/9 = 0.0056
for the nine pre-registered regime cuts; nothing came near it.**

## Could not measure

- **Whether a fixed mixture curve would have changed our live fills.** That
  needs the decision re-run, which is `pinsim`, which is a hypothesis by the
  operator's rule. What IS measured here is the input to that change — the
  real tail weights — from the index alone.
- **Signed direction of the settlement miss on the grid.** The grid has no
  strike, so |z| is unsigned there. On our own fills the signed version is
  what the pnl already tells us.
- **TONUSD_RTI.** Zero prints in the tape over this window (known live gap).
  ADA has 1,990,620 prints against 2,175,762 for the other ten.

## Solutions worth testing

1. **Fix the CURVE, not the participation. `conf_of` is a normal CDF and the
   truth at |z|>4 is 147x heavier.** Replace it with a two-component mixture
   whose tail weight is set from the grid above (|z|>3 = 2.13%, |z|>4 = 0.928%,
   |z|>6 = 0.308% at tau=45, and the tau=30/15/10 rows for the rest). This
   **blocks nothing**: it lowers `fair` only at extreme confidence, which
   shrinks `edge_c` on exactly the 96-99c trades whose tail is the whole loss
   book, so it acts through SIZE and the price the bot is willing to pay.
   Validated on live fills by a synced paper arm carrying only that change,
   read through `h2h` (same markets as live), plus a check that the flag ever
   fired. **What it would block: nothing directly** — but it lowers belief, and
   belief drives the hedge, so the arm must be checked explicitly for hedges it
   would have suppressed before this goes anywhere near live.
2. **Do NOT ship a volatility-regime gate, a jump-cluster stand-down, or a
   cushion floor in either ruler.** All three are priced above and all three
   cost money. This section exists so the next session does not rebuild them.
3. **Worth someone else's assignment: tau.** Not a volatility finding, but it
   is the largest gradient in anything I touched and it is pre-entry knowable.
   TRAIN, ex-09-19: tau<=10 is **$2.48/market** (1 loser in 74), 11-20 $1.10
   (4 in 124), 21-35 **$0.79** (11 in 325), 36-60 $1.28 (1 in 101). With 09-19
   included the 21-35 band collapses to $0.24 a market and holds 15 of the 23
   losers. The 45-second leg is not the problem; the middle of the window is.

## Holdout

Untouched except the totals: 85 markets, 65 closes, **+$62.65**, 2 losers,
-$90.36. Calibration on those 85: sd(z) = 1.157, |z|>4 = 1.18%, no |z|>6.
Nothing above needed spending it, because nothing above passed on TRAIN.

## Housekeeping

`kalshi_collector.py` (pid 105304, 47 MB) and `crypto_feeds.py` (pid 105352,
39 MB) both alive after every job. Disk **21 GB** free (guard 6 GB). Free RAM
2.83 GB; the biggest job here peaked well under 400 MB. Nothing was started,
stopped or signalled; nothing was written outside this file and the scratchpad
folder `.../scratchpad/newedge/realised-vol/` (`volmin.py`, `fills.py`,
`join.py`, `ruler.py`, `calib.py`, and their CSVs).
