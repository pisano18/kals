# IMPACT — Criticism A: does the Coin Race book fight back?

**Job A.** Series KXCRYPTOLEAD15M (Coin Race). Tape 2026-09-04 → 2026-09-06,
`orderbook_delta` + `orderbook_snapshot` + `trade` + `ticker`.
Everything below is measured from the reconstructed book. No orders were placed.
All API calls were authenticated read-only GETs.

---

## VERDICT

**Criticism A dies at the horizon it was posed at, and survives only at a horizon
this data cannot reach.**

The claim was: *"the moment you post size to earn that share, others improve
inside you or hit you and leave you with inventory. Market-making edge is eroded
by the act of participating."*

Measured on 239,955 natural experiments — every single-delta addition of ≥25
lots within 3c of the touch, over 1,078 markets:

| what criticism A predicts | measured | verdict |
|---|---|---|
| others post **inside** you in proportion to your size | **−0.010 ± 0.051** lots per lot (30 s) | **refuted** — indistinguishable from zero |
| others **crowd in** with competing size | **+1.07 ± 0.21** lots per lot (30 s) | **confirmed as a flow** |
| your **paid share** is therefore eroded | **+0.03% ± 1.15%** per 50 lots | **refuted** — zero to within ±2.3% (95% CI) |

The crowding is real but it is *flow*, not *stock*. 75.1% of all additions are
cancelled at the same price for the same size, median lifetime **169 ms**. The
LIP samples once per second and pays on what is resting. Fifty lots posted
induces ~53 lots of gross inflow spread over 30 s; at a 169 ms mean resting life
that is **+0.30 lots** of average resting size against a side score of ~293 —
a 0.09% dilution. The two independent measurements reconcile (§6).

**What survives:** every event in this sample is an *existing* participant's
order, observed over ≤30 seconds. A new, persistent participant taking ~15% of
the pool in 480 leg-windows a day is a different stimulus, and the strategic
response to it operates over days. That is not testable without posting (§7).

---

## 0. The number got BIGGER, which is bad news, not good

Reassembling the claim from measured parts gives **$838/day on $230 peak
capital**, against the $282–348/day under attack. I did not find a kill; I found
a larger number, and a larger number deserves more suspicion, not less. §8 lists
what would have to be true for mine to be wrong. The single largest driver of
the gap is the qualifying fraction: the brief assumes 28.9%, **I measure 74.16%**,
and Kalshi's own paid-vs-advertised ratio ($8,294 / $9,477 = 87.5%) is
consistent with a high number and not with 28.9%.

---

## 1. Corrections to inherited assumptions (re-derived, not adopted)

Three things in the brief are wrong for this series. Each was checked two ways.

**1.1 The tick is NOT tapered for Coin Race.** CLAUDE.md's hard rule says the
tick is 0.1c below 10c and above 90c. That is true of KXBTC15M/KXETH15M and
false here.

- `GET /markets?series_ticker=KXCRYPTOLEAD15M` → `price_level_structure =
  "linear_cent"`, `price_ranges` step `0.0100`. The same call on KXBTC15M →
  `"tapered_deci_cent"`.
- **All 3,962,084 Coin Race deltas and all 31,788 snapshot levels sit exactly on
  a whole cent.** Zero exceptions.

Assuming the taper here inflates the modelled share, i.e. errs in our favour.
`research/lipscore.py` was independently corrected for this during the run.

**1.2 Snapshots are NOT always empty — they are book RESETS.** The brief says
Coin Race snapshots carry no level arrays. That is true only of the snapshot at
market open. **1,335 of 1,345 markets receive a *levelled* snapshot** carrying
the full opening ladder. `orderbook_delta` and `orderbook_snapshot` share
`sid=4`, so their `seq` orders them exactly; `ts_ms` cannot, because snapshots
carry only `_rx_ms`.

Discarding those levels is not cosmetic. It cost every market its opening
120-lot ladder and its 5,000-lot wall at 1c for the market's entire life — those
levels emit no further deltas until somebody cancels them. **It read as a 24.8%
qualifying rate against a true 74.2%.** I made this mistake, caught it because
two of my own scripts disagreed with each other, and fixed it in every consumer.

**1.3 The programme parameters, from `GET /incentive_programs`** (6,385 Coin
Race programmes, 60 pages walked): `target_size_fp` **1000.00**,
`discount_factor_bps` **5000** → 0.50, `period_reward` **200000** in units of
1e-4 dollars → **$20.00 per leg per 15-minute window**, `incentive_description`
`series_lip`. 6,385 programmes / 1,277 windows = **exactly 5.0 legs per window**.
Gross pool **$9,600/day**.

---

## 2. Is the reconstructed book real? (the gate everything else stands on)

The `ticker` channel publishes `yes_bid`/`yes_ask` independently of the delta
stream, so it is a genuine external check. A resting NO bid at q is the YES ask
at 100−q; that mapping was checked, not assumed.

Getting from 73% to 99.6% took three fixes, two of them mine:

| state | in-window top-of-book agreement |
|---|---|
| naive (ignore snapshots) | 80.0% bid / 77.2% ask |
| + snapshots as resets | 89.4% / 81.3% |
| + exact 2-decimal size arithmetic | **99.565%** (tie-tolerant, 319,064 comparisons) |

The third fix matters and was not obvious. Sizes are **fractional** on this
exchange (`count_fp` `"46.87"`, `delta_fp` `"-93.00"`). Accumulating them in
float leaves residue, and a level holding 3×10⁻⁷ contracts is a live level to a
naive `> 0` test — which moves the top of book. Sweeping the threshold:

```
ignore levels with size <= 0.000 :   73.490% agreement
ignore levels with size <= 0.005 :   99.931%     <-- float residue, not a real level
ignore levels with size <= 1.000 :   88.968%     <-- sub-lot orders ARE real
```

Rounding to 2dp after every application makes it exact. **Given a matching
price, size agreement is 100.000%** (95,916 bid and 88,377 ask comparisons) —
the level accounting is not approximately right, it is right.

I also confirmed the stream is not lossy: merged `sid=4` sequence numbers across
three sample hours are missing **9, 8 and 11 of ~2.1 million** (0.0004%), every
gap a single message. Data loss cannot explain anything.

**Gate applied:** 1,078 of 1,237 markets reconstruct to ≥99% and only those are
used. Truncated source files (`20260904T07`, `20260906T14`, `20260906T18` — the
live one) lost their tails; the rest of each file was kept.

**Window definition, proven not guessed:** the ticker date-time is the market's
CLOSE in Eastern time and it trades the preceding 15 minutes.
`KXCRYPTOLEAD15M-26SEP070000-HYPE` → programme `start 2026-09-07T03:45:00Z`,
`end 04:00:00Z`, and 04:00Z is 00:00 ET.

---

## 3. Self-test before real data

The estimator was required to recover a *planted* response and, more
importantly, to report **none** where none exists. Three stationary synthetic
worlds (every resting order has a finite lifetime so the book does not explode):

```
world       n_ev   d oth/dS   d can/dS   d ins/dS
null       47703      0.062      1.173     -0.099
fight      66060      0.570      2.116      0.559
cede        1892      0.426      1.814     -0.244

NULL: d(others added)/dS is ~0 (|slope| < 0.15)                ok
FIGHT: recovers the dilution-adjusted 0.578 (+-0.15)           ok
NULL: cancel slope is the adder's OWN scheduled cancel, ~1.0   ok
CEDE: cancel slope EXCEEDS null by the planted 0.80 (+-0.25)   ok
NULL: d(posted inside)/dS is ~0 (|slope| < 0.15)               ok
FIGHT: d(posted inside)/dS recovers 0.80 (+-0.25)              ok
```

Two design failures were caught here rather than in the results:

- **The control group was unusable.** My first design compared "after an
  addition" against "no ≥25 addition in the previous 500 ms". In a book where
  such additions arrive twice a second that set is nearly empty, and any control
  drawn from it is already contaminated — which biases the measured response
  **towards zero**. Zero is the answer that flatters us. Replaced by a
  dose-response design in which every observation is an addition and the
  treatment intensity is its size.
- **A measurement window anchored to the event price is an artefact machine.**
  Anchoring the "others added" band at the event price makes the window
  mechanically wider for events priced further back; since size and price
  correlate, that alone produced a **spurious −1.3 slope in a world where nothing
  responded to anything**. The band is now anchored to the touch.

**Dilution, and its direction.** In the fight world the planted responses are
themselves additions near the touch, so they re-enter the sample as events with
no response of their own: 66,060 events vs 47,703, so the recoverable slope is
0.80 × 0.722 = 0.578, not 0.80 — and 0.570 was recovered. The same dilution
applies to real data, so **every slope below is a lower bound on the true
response**, and low is the flattering direction.

---

## 4. Q1 — the response function

239,955 additions of ≥25 lots within 3c of the touch, ≥40 s before close.
Slopes are pooled within strata of (distance back, time-to-close, book score),
with market-clustered standard errors.

### 4.1 The artefact check that flipped the sign

The naive slope was **−1.93** — the book appears to *cede*, which flatters us.
So: what would have to be true for that to be an artefact? The S∈[25,50) bin is
68% of all events and shows others adding 11,633 lots in 30 s against 3,300–4,500
for every larger bin. If small additions simply happen in busier books, the
slope is measuring composition. **It is:**

```
S 25-50      n=164183   mean arrival bucket 3.40   mean book score 140.2
S 50-100     n=26046    mean arrival bucket 1.56   mean book score 260.1
S 100-200    n=44618    mean arrival bucket 1.11   mean book score 257.0
S 200-9999   n=5108     mean arrival bucket 1.28   mean book score 615.3
```

Adding the local arrival rate to the strata:

```
sample                   outcome     no rate control   WITH rate control
all events               oth30000     -2.443+-1.344     0.885+-0.206
non-ladder               oth30000     -0.414+-0.646     1.043+-0.208
S>=50 only               oth30000      1.021+-0.206     1.081+-0.207
non-ladder & S>=50       oth30000      1.046+-0.205     1.066+-0.213
```

The S≥50 subsample — structurally immune to that composition problem — gives
**+1.02 without the control and +1.08 with it**. Stable. The negative sign was
an artefact confined to the small-add bin, and the honest answer is the
opposite of the naive one.

### 4.2 The three channels, separated

| channel | horizon | slope (S≥50, non-ladder) |
|---|---|---|
| others **add** in the scoring band | 5 s | **+0.291 ± 0.108** |
| others **add** in the scoring band | 30 s | **+1.046 ± 0.205** |
| others post **strictly inside** you | 30 s | **−0.034 ± 0.053** |
| gross **cancels** in the band | 30 s | +0.06 to +0.36 (dominated by the adder's own cancel — the null world shows this is mechanically ~1.0) |

**They crowd. They do not step in front.** The "inside" slope is within one
standard error of zero in every specification.

### 4.3 In paid units — the measurement that decides it

Endpoint measures mislead in opposite directions, so the money-correct quantity
is our share **averaged over the one-second snapshot grid the LIP actually
samples**, for the 30 s before an addition versus the 30 s after:

```
all additions >=25   +0.000005 +- 0.000229 /lot  ->  +0.03% +- 1.15% per 50 lots  (n=16793)
additions >=50       +0.000013 +- 0.000262 /lot  ->  +0.06% +- 1.31% per 50 lots  (n= 4123)
```

**Zero, with a 95% interval of roughly [−2.2%, +2.3%] per 50 lots posted.**

---

## 5. Q2 — how fast does the front re-form?

99,957 consumptions of the touch level:

| | |
|---|---|
| p10 | 23 ms |
| p25 | 158 ms |
| **median** | **1,214 ms** |
| p75 | 8.0 s |
| p90 | 50.4 s |
| under 100 ms | 20.7% |
| under 1 s | 47.1% |
| never within 60 s | 9.2% |

Where it comes back: **same price 71.0%**, +1c 9.1%, +2c 4.4%, +3c 4.4%,
never 9.0%.

**Implication: queue position is close to worthless.** Half the time the front
is rebuilt before the LIP's next one-second snapshot, at the same price. This is
consistent with the previously measured 62% of markets filling us not at all. It
cuts both ways — it is why a passive quote survives, and why it earns little
from priority.

---

## 6. Q3 — elasticity of our share, and the reconciliation

X, the size others add into the scoring band over 30 s (our share is
S/(score + S + X)):

| distance back | n | p25 | median | p75 | p95 |
|---|---|---|---|---|---|
| 0c | 8,333 | 1,547 | 3,468 | 6,731 | 25,310 |
| 3c | 33,205 | 1,256 | 3,103 | 7,075 | 52,140 |

Our 50 lots is ~1.6% of the median 30-second flow. The book is a torrent.

**Flow is not stock, and the LIP pays on stock.** Converting the induced flow at
various assumed resting lifetimes, against a median side score of 293:

```
life  0.17s -> +  0.30 lots resting -> share 14.58% -> 14.56%  (-0.09% relative)
life  1.00s -> +  1.77 lots resting -> share 14.58% -> 14.50%  (-0.51% relative)
life  3.00s -> +  5.30 lots resting -> share 14.58% -> 14.36%  (-1.52% relative)
life 10.00s -> + 17.67 lots resting -> share 14.58% -> 13.86%  (-4.90% relative)
```

The measured lifetime is 169 ms median. The paid-units measurement found
+0.03% ± 1.15%. **These agree for any resting life up to several seconds.** Two
independent measurements, one from flow and one from paid share, are consistent —
neither has to be discarded to believe the other.

---

## 7. Q4 — who is actually in this book

938,465 additions across 400 markets.

**7.1 It is one bot, and its size is 120.**

| size | % of all adds | % of adds **at the touch** |
|---|---|---|
| **120.00** | **37.83%** | **65.19%** |
| 1.00 | 4.94% | 3.06% |
| 25.00 | 4.73% | 2.18% |

Two-thirds of everything posted at the front of this book is exactly 120.00
lots. The opening snapshot shows it plainly — 120-lot rungs at every third cent
up both sides, seeded in the **same millisecond across all five legs**:

```
KXCRYPTOLEAD15M-26SEP042015-BTC
 yes: 1c x5000, 2c/5c/8c/11c/15c x120
 no : 1c x150,  30c/33c/36c/.../75c x120
```

Price stride from best to second-best level: 4c 33.7%, 3c 27.6%, 1c 20.0%.

**7.2 The critic's "500 contracts instantly layered in front" is not what happens.**

```
400-  499 :   1512  (0.1611% of adds)
500-  599 :    533  (0.0568%)
...
10000-10099:  1794  (0.1912%)     <- the 1c wall
largest single addition seen: 10,000 lots
```

Additions of 400+ lots are ~0.4% of all additions. Enormous ones (9,000–10,000)
do exist, but they are the deep 1c wall, which the discount factor renders
worthless: 5,000 lots 20c below the reference price score 5,000 × 0.5²⁰ ≈ 0.005.
**The critic is right that a bot sits at the front and wrong about its size and
its behaviour.**

**7.3 It moves at machine speed, and mostly it flickers.**

- 75.1% of additions are cancelled at the same price for the same size.
  Round-trip: p10 7 ms, **median 169 ms**, p75 895 ms. 52.5% under 200 ms.
- Inter-delta latency within a market: p10 1 ms, median 7 ms, p90 316 ms.

**7.4 On a slow clock it does not adapt.** A 30-second event study is blind to
strategic response, so: within each coin, across consecutive 15-minute windows,
does the bot post more when the book is more crowded?

```
coin          n   corr(sc,lad)  corr(sc_t, lad_t+1)
POOLED     1078        -0.281            +0.041
```

The contemporaneous correlation is negative (it fills voids). The **lagged
correlation is +0.04 — no detectable adaptation to the previous window's
competitive state.** Its rung size is rigidly 120 across all three days. This is
evidence, not proof, of an open-loop policy.

---

## 8. Q5 — the honest bound: what I did NOT answer

**Answered (and criticism A refuted on these):**
1. Do others post *inside* size placed near the touch? No — slope 0 ± 0.05.
2. Do others crowd in with competing size? Yes — ~1 lot per lot, but as flow
   with a 169 ms half-life, worth 0–1.5% of our share.
3. Is a resting quote's *paid* share eroded when size lands next to it?
   No — 0 ± 2.3%.
4. Does the incumbent adapt window to window? No — lagged corr +0.04.

**Not answered, and not answerable without placing an order:**

1. **We would be a new, persistent participant.** Every event in this sample is
   an existing participant's order, seen for ≤30 seconds. Quoting 480
   leg-windows a day, every day, taking ~15% of a pool, is a different stimulus
   from a 120-lot flicker. Nothing in three days of tape contains that
   experiment.
2. **Targeted response.** Competitors see order-level data we do not. A response
   aimed at one counterparty need not show up in aggregate deltas.
3. **The equilibrium horizon.** The longest response I could test is one
   15-minute window lagged. A rational incumbent re-optimises over days. The
   120-lot rung is a policy parameter its operator can change in one deploy.
4. **Kalshi's own reaction.** $20/leg/window and the 1000-lot target are
   parameters they set and can change; the programme has already been observed
   paying $8,294/day against $9,477 advertised.
5. **Fill and inventory P&L** — criticisms B and C, out of scope for Job A, and
   the place the remaining danger now lives.

**My estimate of the fraction answered: the mechanical, short-horizon half of
criticism A is settled and it fails. The strategic half is untouched.** I would
not describe criticism A as dead; I would describe it as relocated from
milliseconds to days, where it is no longer testable from a tape and only a
small live order can settle it.

---

## 9. Money (rebate only — no fill P&L, no inventory)

50 lots on **both** sides of **all five** legs, 3c behind each touch.

**Peak concurrent capital** (all 5 legs, both sides, max over each window;
265 events):

| | |
|---|---|
| p5 | $92.00 |
| median | $184.50 |
| p95 | **$230.50** |
| worst single second | **$232.50** |

**Rebate per leg-window** (n = 1,078 — the unit the programme actually pays):

| | |
|---|---|
| p5 | $0.6873 |
| p25 | $1.1730 |
| median | $1.6972 |
| p75 | $2.3319 |
| p95 | $2.8829 |
| **mean** | **$1.7457** |

Not one leg-window of 1,078 paid under a cent; the p05 is 39% of the mean. The
distribution has no left tail to speak of — which is exactly what a rebate,
as opposed to a trade, should look like.

**Scaled to a day** (5 legs × 96 windows = 480 leg-windows):

| | |
|---|---|
| **$/day** | **$837.95** |
| **peak concurrent capital** | **$230.50** (p95) / $232.50 (worst second) |
| **% return on capital** | **363.5%/day** |
| **$/contract/day** | **$1.676** per resting contract (500 resting) |

**Stability across the sample:**

```
26SEP03    62 leg-windows  mean $1.8042  ->  $866.04/day
26SEP04   383 leg-windows  mean $1.7947  ->  $861.47/day
26SEP05   387 leg-windows  mean $1.7011  ->  $816.55/day
26SEP06   246 leg-windows  mean $1.7249  ->  $827.94/day
```

**Components, all measured:**
- qualifying snapshots (both sides ≥ Target Size 1000): **74.16%** of 1,927,586
  side-seconds
- our share of a side, 50 lots at touch−3c, qualifying seconds only:
  p05 0.00%, p25 5.80%, **median 15.38%**, p75 16.39%, p95 17.88%, **mean 11.74%**
- a 3c-back quote earns **full credit 94.40%** of the time; mean distance
  multiplier **0.9620** — an independent confirmation of the inherited "3 ticks
  back keeps 93% of the rebate"
- this uses the **conservative average-of-sides** reading. If "your share of the
  yes side PLUS your share of the no side" is literal, **every figure doubles**.
  Still unresolved.

### What would have to be true for $838/day to be an artefact

Ranked by how much I worry:

1. **The LIP denominator may include orders absent from the public depth feed.**
   My share is 50/(visible score + 50) and the visible score is only ~293. If
   Kalshi scores orders the public book does not publish, my denominator is too
   small and my share too large. **Untestable from public data.** This is the
   biggest single risk and it is unquantified.
2. **The "average of yes and no" normalisation is assumed, not proven.** It sets
   the answer to within a factor of two.
3. **The qualification rule may carry conditions I cannot see** (a spread
   requirement, a stricter sense of "open"). My 74.16% is
   depth-on-both-sides-only. The cross-check — Kalshi paid $8,294 of $9,477
   advertised, 87.5% — is consistent with a high number but does not pin the
   rule.
4. **The strategic response of §8.** At ~15% of the pool we would be one of the
   largest participants on the series. That is precisely the stimulus this data
   does not contain.
5. Sub-lot fractional orders are real and score; whether the LIP counts them is
   assumed.

**None of these is checkable without either better documentation or a live
order.** The result of Job A is therefore: criticism A does not kill the trade,
and the burden has shifted onto (1) and (2), which are questions about the rule,
not about the book.

---

## Files

Working code and caches (all pure stdlib — no numpy anywhere in this repo):

```
C:\Users\Joe\AppData\Local\Temp\kals-work\impact\
  extract2.py   Coin Race tape: deltas + snapshots + seq, 0.1c fidelity
  replay.py     book replay (snapshot resets, exact 2dp size arithmetic)
  lip.py        LIP scorer on the linear_cent grid  [self-test: PASS]
  study.py      the dose-response estimator          [self-test: PASS]
  recon5.py     reconstruction vs exchange ticker -> good_markets.pkl
  dust.py       the 0.005-contract threshold sweep
  seqgap.py     sid=4 sequence contiguity (stream is lossless)
  grid.py       linear_cent proof, two independent ways
  params.py     programme parameters from GET /incentive_programs
  hft.py        who is in the book and how fast
  artefact.py   the arrival-rate control that flipped the sign
  path.py       paid-units erosion (one-second snapshot grid)
  capital.py    peak concurrent capital and payout distribution
  slow.py       does the incumbent adapt window to window
  final.py      re-formation price, full-credit rate, flow/stock reconciliation
  tape2.pkl (92 MB), good_markets.pkl, agg.pkl, cap.pkl, path.pkl
```

Collectors `kalshi_collector.py` (PID 3381772) and `crypto_feeds.py`
(PID 3385232) verified alive after every heavy job and at the end of the run;
`orderbook_delta/20260906T19.jsonl.gz` was still growing. Free disk 52 GB
throughout.
