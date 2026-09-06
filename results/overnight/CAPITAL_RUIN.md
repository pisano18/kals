# JOB C — CAPITAL, EXPOSURE AND RUIN ON $1,000

**Criticism C under attack:** *"Small capital cannot post competitive size
across five concurrent markets without excessive exposure. One or two bad
windows and the account is impaired or wiped."*

Written 2026-09-06. Tape `KXCRYPTOLEAD15M` (Coin Race), UTC 2026-09-04 →
2026-09-06, **249 complete five-leg closes over 2.59 full trading days**.
Collateral rule read off the live API and the exchange rulebook; every dollar
figure below is measured, none assumed. Both collectors verified alive before,
during and after every job (§Resources).

---

## THE ANSWER IN ONE PARAGRAPH

**Criticism C fails on this tape, and it fails on arithmetic that is hard to
argue with.** $1,000 funds **S = 100 on both sides of all five coins** with
room to spare: the largest peak concurrent capital ever measured, across 249
windows, is **$743.36** at S=100 and **$392.29** at S=50 — and the reason is
that a Coin Race contract has a **$1.00 notional**, so the most a two-sided
quote can lock is `S × (bid + ask-complement) ≈ S dollars per market`. The
account is **not wipeable by this strategy at any size tested**: probability of
ruin is **0.00%** at S = 10, 25, 50 and 100, under three resampling schemes,
at horizons of 5, 20, 250 **and 1,000** days, 20,000 paths each. It takes
**5.3 consecutive maximum-adverse windows at S=50** (79 minutes of uninterrupted
worst case) to lose $1,000, and the worst window the tape actually produced,
even redrawing which coin won, is **−$91.50**. The size that keeps a 1-in-20
bad week inside the operator's **$250** clause is **S ≈ 75** (measured: p95
five-day drawdown $228.47, P(dd≥$250) = 4.07%), which earns **$720/day on $349
of peak concurrent capital = 207%/day, $0.96 per resting contract per day**.
**But the criticism half-lands somewhere else than it aimed.** The exposure is
survivable; what is not underwritten is the *earning*. Strip the LIP rebate out
and the conservative fill model leaves **$12.74/day at S=50 with a 22.3% chance
of a $250 weekly drawdown** — a clear fail. **The rebate is 58% of the P&L at
S=50 and 96% of it under the conservative fill model. Criticism C is answered;
it was aimed at the wrong risk.**

| S=50, d=3, five coins, base fill model | value |
|---|---|
| net $/day | **$490.17** (rebate $284.28 + inventory $205.89) |
| **$ per resting contract per day** | **$0.9803** (500 resting contracts) |
| **peak CONCURRENT capital** | median **$233.91**, p95 $299.60, **max $392.29** |
| **% return on capital / day** | **209.6%** on median capital, **125.0%** on the worst-case peak |
| windows that lose money | 18% |
| worst single window | −$68.48 realised, −$91.50 under the worst coin |
| p95 five-day drawdown | $158.65 realised, **$187.50** with the winner redrawn |
| P(five-day drawdown ≥ $200) | 1.4% – 7.7% |
| **P(ruin), 1,000 days** | **0.00%** |

---

## 0. THE SELF-TEST — before any real data

`C:\Users\Joe\AppData\Local\Temp\kals-work\jobC2\selftest.py`

```
SELF-TEST: 41 checks passed, 0 FAILED
MUTATION : 15/15 killed = 100%
```

Every estimator checked against a hand-computed answer: resting collateral in
both books and in dollars; MECNET collateral against **Kalshi's own published
worked example** ($1.30 invested, $1 guaranteed, $0.30 held); settlement P&L of
a five-leg window under a named winner; the floor as a **min** over winners;
peak capital as the max over seconds of the **sum** over markets (not the sum
of per-market maxima); drawdown from the **running peak**; ruin along the path,
not at the end; and the barrier compared to the **drawdown**, not the equity.

The check the whole report rests on is the block bootstrap, because the brief
demanded whole-day blocks and I had to prove my code can see the difference:

| synthetic world | block width ÷ iid width | 5%-worst: iid vs block |
|---|---|---|
| uncorrelated | **1.01×** — they agree | — |
| shocks lasting 40 steps | **4.97× wider** | −15.3 vs **−107.0** |

Mutants killed include: collateral without the `/100`; collateral charging only
one book; MECNET guaranteeing the *best* outcome instead of the worst; the
window floor taking a max over winners; peak capital summing per-market maxima
(19 instead of the correct 17 on the test case); drawdown from zero; drawdown
tracking the running *minimum*; the block bootstrap silently degenerating to
iid; ruin tested on terminal equity only; and scoring a both-sides fill in one
market as a loss.

A second self-test, inside `part3.py`, proves the speed optimisation is exact:

```
compose() self-test: 0/400 disagree with the naive step-by-step walk (want 0);
mutant that drops the cross-block drawdown disagrees 200/200 (want 200)
```

### Reconciliation against `REBATE_RISK.md`

Same tape, independently re-aggregated to the **event** (five legs) rather than
the market:

| | REBATE_RISK.md | here |
|---|---|---|
| d=3 base, rebate $/close | 2.938 | **2.9612** |
| d=3 base, net $/close | 5.065 | **5.1059** |
| d=3 base, net $/day | 486 | **490** |
| d=3 base, contracts/market | 7.15 | **7.20** |
| d=3 conservative, net $/day | 295 | **297** |
| d=0 base, net $/day | 176 | **178** |

All within 1%. The small gap is that I drop the **whole event** when any of its
five legs is dirty (249 events kept, 11 dropped for truncated tape hours, 2 for
zero snapshots), because a four-leg event breaks the mutual-exclusion
arithmetic that this entire report turns on.

---

## 1. COLLATERAL, EXACTLY

### The rule, from primary sources — not assumed

| source | what it says |
|---|---|
| **live API**, `GET /markets` | `notional_value_dollars: "1.0000"` — one contract settles at $1 or $0 |
| **KalshiEX rulebook / CFTC filing** | the exchange *"cap-checks"* every order at submission and accepts it only if the account can *"fully collateralize the order, if filled"* |
| same | *"funds sufficient to cover the maximum possible loss a counterparty could incur upon liquidation or expiration"* |
| **live API**, `GET /events/KXCRYPTOLEAD15M-…` | `mutually_exclusive: true`, `collateral_return_type: "MECNET"`, 5 markets in the event |
| **help centre**, *Collateral Return* | collateral held = *total investment − guaranteed payout*; **"disabled by default for new users"**; the flag locks in *"at the first moment a user places their first order in a given event, even before any trade actually fills"*; **"there is no way to retroactively enable or disable"** it; **"enabling this feature may make you unable to sell positions for which you've already had collateral returned"** |
| **help centre**, *Closing or Modifying a Position* | **"If you have an open resting limit order on a position, you cannot partially or fully close that position until the resting order is cancelled."** |

So, with collateral return **off** (the default):

> A resting **BUY** of S contracts at p cents locks **S·p cents**. A resting
> **SELL of YES** is a **BUY of NO at (100−p)** and locks **S·(100−p)**. A
> two-sided quote of S at yes-bid *b* and no-bid *n* therefore locks
> **S·(b+n) = S·(100 − spread)** cents — **≈ S dollars per market, whatever
> the price.**

### What S=50 on both sides of five markets actually locks — measured

Second by second across every window, resting collateral plus the cost of
fills already taken, summed over the five legs, maximum over the window
(`part12.py`; cross-checked against the simulation's own per-market accounting,
ratio median **0.962**, p05 0.933 — my reconstruction is the tighter and
correct one, because the sum of per-market maxima is an upper bound):

**d = 3, five coins, dollars**

| S | min | p05 | p25 | **MED** | p75 | p95 | **max** |
|---|---|---|---|---|---|---|---|
| 10 | 27.60 | 44.40 | 45.60 | **49.30** | 55.20 | 66.10 | **83.96** |
| 25 | 69.00 | 111.00 | 114.00 | **119.84** | 135.00 | 160.85 | **200.15** |
| **50** | 138.00 | 222.00 | 228.00 | **233.91** | 259.08 | 299.60 | **392.29** |
| 100 | 276.00 | 443.72 | 455.00 | **463.06** | 491.82 | 552.10 | **743.36** |

**The naive rule of thumb is right in the middle and wrong in the tail.**

| S | naive `$S × 5` | measured median | measured MAX | max ÷ S |
|---|---|---|---|---|
| 10 | $50.00 | $49.30 (99%) | $83.96 | **8.40 markets' worth** |
| 25 | $125.00 | $119.84 (96%) | $200.15 | 8.01 |
| 50 | $250.00 | $233.91 (94%) | $392.29 | **7.85** |
| 100 | $500.00 | $463.06 (93%) | $743.36 | 7.43 |

**Capital planning must budget ~8×S, not 5×S.** The excess is the *handover*:
a Coin Race close every fifteen minutes means the previous window's unsettled
inventory overlaps the next window's fresh resting orders. That is the single
most important number in this section and it was not in the earlier work.

Also measured, and it complicates the picture: a leg carries a **two-sided**
book for only **357 of its 900 seconds** (median 355), and **all five legs are
two-sided in only 8.0% of seconds** (1 leg: 20.8%, 2: 29.2%, 3: 24.9%,
4: 17.2%). The peak capital is nevertheless 4.6–4.9 markets' worth of S,
because a one-sided book still takes a one-sided order and still locks
collateral, and because peak is a max.

### MECNET — real, quantified, and my recommendation is to leave it OFF

On the end-of-window inventory, MECNET (`invested − guaranteed payout`) would
return:

| S | invested in fills, median | MECNET held, median | fraction of inventory cash returned |
|---|---|---|---|
| 10 | $4.49 | $1.03 | **40%** |
| 25 | $7.68 | $2.31 | 37% |
| 50 | $8.59 | $3.00 | **35%** |
| 100 | $8.59 | $4.33 | 31% |

That is a real saving on the *inventory* leg — but inventory is the small part
of the capital; the resting orders are the large part, and nothing in Kalshi's
documentation says resting orders net. **Recommend leaving MECNET off**, for
three measured reasons: (1) $1,000 already funds S=100 without it; (2) it is
**irreversible per event** once the first order is placed; (3) the help centre
states it *"may make you unable to sell positions for which you've already had
collateral returned"* — a market maker who cannot exit a leg has traded a
capital saving for an inventory trap.

**Operational constraint found in the same search and worth as much as any
number here:** *"If you have an open resting limit order on a position, you
cannot partially or fully close that position until the resting order is
cancelled."* A two-sided quoter cannot flatten inventory without first
cancelling the quote — so the hedge-and-keep-quoting pattern is not available,
and every risk-reduction action costs the quote (and its rebate seconds).

---

## 2. WORST CASE PER WINDOW, EXACT

### The structure does most of the work

Exactly one of the five coins leads, so the five YES legs settle to **exactly
100c**. That is the contract, not a modelling choice. Three consequences, and
the second is the one the brief's phrasing missed:

**(a) Filling BOTH sides of one market is a profit, never a loss.** We hold S
YES and S NO, a guaranteed $1·S payout for `S·(b+n) < S·100` cents.

**(b) So "all five coins fill us" is not the worst case.** The worst case is
the **adversarial subset**: long YES in the four losers, long NO in the winner.
Exactly:

> **max loss = max over the winning coin W of  S · [ Σ_{i≠W} y_i + n_W ] cents**

where `y_i` is our yes-book price in leg *i* and `n_W` our no-book price in the
winner. The maximiser is the **cheapest** coin winning, because `n_W − y_W =
100 − 2·mid_W`.

**(c) Long YES in all five legs is a box.** It costs `Σ y_i` and pays exactly
100c. **Measured at d=3: across 13,463 seconds with all five legs two-sided,
`Σ y_i` exceeded 100c in ZERO of them**; mean 65.8c. At the touch (d=0) it
breaches in 62 of 13,463 seconds (**0.46%**) by at most **9c**. *(This
corrected an overstatement of my own: my first draft said "cannot lose", and
the d=0 column of my own table showed a maximum of 131c. At the recommended
d=3 the claim survives; at d=0 it does not.)*

### The exact numbers

Per contract of S, in cents, over the 249 complete windows. "Worst instant"
takes each leg's worst price anywhere in the window — the true supremum, since
the fills need not be simultaneous.

**d = 3 (the recommended distance)**

| | min | p05 | p25 | **MED** | p75 | p95 | **max** |
|---|---|---|---|---|---|---|---|
| **worst instant of the window** | 175 | 226 | 261 | **282** | 309 | 339 | **377** |
| at the window's median touch | 117 | 134 | 149 | **156** | 165 | 176 | 196 |
| sum of the five yes-book prices | 35 | 53 | 63 | **69** | 78 | 88 | 116 |
| sum of the five no-book prices | 274 | 329 | 343 | **352** | 359 | 367 | 378 |

**d = 0 (at the touch)** — worst instant: median **297**, max **392**.

### MAXIMUM LOSS PER WINDOW, in dollars (d=3)

| S | median window | **worst window in the tape** | as % of $1,000 |
|---|---|---|---|
| 10 | $28.20 | $37.70 | 3.8% |
| 25 | $70.50 | $94.25 | 9.4% |
| **50** | **$141.00** | **$188.50** | **18.9%** |
| 100 | $282.00 | $377.00 | **37.7%** |

### How many consecutive maximum-adverse windows would wipe $1,000?

| S | structural floor (median) | structural floor (worst seen) | **worst-coin floor given the fills we actually got** | realised worst window |
|---|---|---|---|---|
| 10 | 35.5 windows | 26.5 | 43.1 | 51.3 |
| 25 | 14.2 | 10.6 | 21.9 | 24.3 |
| **50** | **7.1** | **5.3** | **10.9** | **14.3** |
| 100 | 3.5 | **2.7** | 5.5 | 8.3 |

A close happens every fifteen minutes, so "5.3 windows" is **79 minutes of
uninterrupted worst case** — every leg filling only on the losing side, at the
worst price of its window, five closes running. **"One or two bad windows and
the account is wiped" is false at S ≤ 50 by a factor of 3–5, and at S=100 it is
arithmetically possible (2.7 windows) but requires the structural floor, which
is 2× worse than anything the tape produced even under an adversarial
counterfactual.**

---

## 3. RUIN SIMULATION

Per-window P&L = LIP rebate + settlement P&L of the inventory the quote picked
up, aggregated to the **event**. Bankroll $1,000, 96 closes/day, drawdown from
the running peak equity. Four schemes:

* **DAY** — resample whole UTC days, as the brief asked. **Only three days
  exist and two are partial**, so this is near-degenerate and is reported with
  that warning attached; its intervals are far too narrow to believe.
* **BLOCK** — circular block bootstrap over the 249-window chronological
  series, block length 96 (a day) and 24 (six hours). **249 distinct block
  starts instead of 3**, and any correlation shorter than L survives.
* **WINNER** — same windows, but the coin that wins is **redrawn** from the
  market's own closing price. The tape saw each outcome once; this samples the
  other four. It uses no assumed distribution: all five payoffs are computed
  exactly from the inventory we actually held. 300 independent series.
* **FLOOR** — the worst of the five outcomes in *every* window. A bound, not a
  probability.

### 5-day horizon (one week), 20,000 paths

| S | $/day | scheme | P(dd≥$200) | P(dd≥$500) | **P(ruin)** | med dd | p95 dd | p99 dd |
|---|---|---|---|---|---|---|---|---|
| 10 | 111 | BLOCK L=96 | 0.00% | 0.00% | **0.00%** | $42.91 | $49.58 | $63.15 |
| 10 | | WINNER | 0.00% | 0.00% | **0.00%** | $42.91 | $55.94 | $63.75 |
| 25 | 275 | BLOCK L=96 | 0.00% | 0.00% | **0.00%** | $88.88 | $96.45 | $129.21 |
| 25 | | WINNER | 0.01% | 0.00% | **0.00%** | $88.88 | $113.88 | $130.75 |
| **50** | **490** | BLOCK L=96 | 1.39% | 0.00% | **0.00%** | $140.66 | $158.15 | $208.89 |
| **50** | | BLOCK L=24 | 7.70% | 0.00% | **0.00%** | $140.66 | $213.11 | $254.22 |
| **50** | | **WINNER** | **1.73%** | **0.00%** | **0.00%** | $140.66 | **$187.50** | $224.54 |
| 100 | 963 | BLOCK L=96 | 90.20% | 0.00% | **0.00%** | $219.93 | $222.94 | $298.26 |
| 100 | | WINNER | 78.08% | 0.00% | **0.00%** | $219.93 | $274.20 | $301.95 |
| 50 | | *FLOOR* | *100%* | *100%* | *100%* | *$1,728* | *$1,938* | *$2,012* |

### Longer horizons (same schemes; median terminal shown for scale only)

| horizon | S | scheme | P(dd≥$200) | P(dd≥$500) | **P(ruin)** | p99 dd | median terminal |
|---|---|---|---|---|---|---|---|
| 20 days | 50 | WINNER | 7.70% | 0.00% | **0.00%** | $248 | $11,051 |
| 20 days | 100 | WINNER | 99.82% | 0.00% | **0.00%** | $356 | $20,860 |
| 250 days | 50 | WINNER | 63.90% | 0.00% | **0.00%** | $303 | $126,626 |
| **1,000 days** | 10 | WINNER | 0.00% | 0.00% | **0.00%** | $94 | $121,861 |
| **1,000 days** | 25 | WINNER | 0.58% | 0.00% | **0.00%** | $195 | $283,783 |
| **1,000 days** | **50** | **WINNER** | **98.34%** | **0.00%** | **0.00%** | **$328** | $503,497 |
| **1,000 days** | 100 | WINNER | 100% | **0.26%** | **0.00%** | $473 | $993,881 |

**Probability of ruin is 0.00% in every cell.** The only path to ruin is the
FLOOR — the worst of five coins winning every single window, 96 times a day,
which is not a scenario, it is a bound.

**Read the terminal bankrolls as a reductio, not a forecast.** $503k from
$1,000 in 1,000 days is arithmetically what a fixed-size, non-compounding
+$490/day produces, and it is obviously not achievable: at S=50 we are already
modelled at 11.5–12.1% of the paid side of every book, and the pool is
$20/window whether one maker or ten shares it. **Capacity, not capital, is the
binding constraint, and this report does not measure capacity.**

**The 20% barrier ($200) is where the interesting structure is.** Note that the
median drawdown is *identical* across every scheme and horizon at a given S
($140.66 at S=50, $219.93 at S=100). That is the signature of a **single
dominant episode** that almost every resampled path contains — see §4(b).

---

## 4. THE SIZE THAT SURVIVES A $250 DRAWDOWN CLAUSE

### The ladder, measured at seven sizes (d=3, five coins, 5-day drawdown)

**BASE fill model (sweep + size)**

| S | $/day | $/resting-contract/day | peak cap (med) | %/day | p95 dd | p99 dd | P(dd≥250) | **p95 dd, winner redrawn** | **P(dd≥250), redrawn** |
|---|---|---|---|---|---|---|---|---|---|
| 10 | 111.39 | 1.114 | $49.30 | 226% | 50.08 | 63.88 | 0.00% | 56.25 | 0.00% |
| 25 | 275.05 | 1.100 | $119.84 | 230% | 96.26 | 127.91 | 0.00% | 112.88 | 0.00% |
| 50 | 490.17 | 0.980 | $233.91 | 210% | 159.32 | 211.41 | 0.19% | 187.50 | 0.20% |
| 60 | 585.02 | 0.975 | $279.65 | 209% | 174.90 | 234.25 | 0.72% | 207.29 | 0.36% |
| **75** | **720.31** | **0.960** | **$348.75** | **207%** | **195.39** | **263.82** | **1.55%** | **228.47** | **4.07%** |
| 85 | 861.48 | 1.014 | $394.40 | 218% | 206.87 | 278.15 | 1.73% | 269.86 | **6.92%** |
| 100 | 962.63 | 0.963 | $463.06 | 208% | 222.36 | 298.06 | 2.69% | 275.23 | **20.38%** |

**CONSERVATIVE fill model (exact-price):** `P(dd≥$250) = 0.00%` at every size
up to S=100; p95 drawdown never exceeds $114 even with the winner redrawn. The
binding case is the base model, so the base model is what the answer uses.

### THE ANSWER

> **S = 75.** It is the largest size at which the 1-in-20 bad week stays inside
> $250 under the honest (winner-redrawn) tail: p95 five-day drawdown
> **$228.47**, P(dd ≥ $250) = **4.07%**. S=85 breaches on both readings
> (**$269.86**, **6.92%**). Linear interpolation puts the crossing at
> **S ≈ 78**; take 75 and stop.

**What S=75 earns:** **$720.31/day** = **$0.9604 per resting contract per day**
(750 resting contracts), on **$348.75** of median peak concurrent capital
(**max $577.36**) = **207% per day on capital**, or **2.15% per fifteen-minute
window turned over 96 times.**

**Sizing sanity, hand-checked:** at S=75 the structural worst-case window is
`75 × 2.82 = $211.50` median and `75 × 3.77 = $282.75` at the worst instant
seen. So the largest single-window loss the structure permits at S=75 is about
28% of the bankroll and 113% of the drawdown clause — **the clause binds on the
week, not on the window, which is the right way round.**

### (b) WHERE the drawdown actually is — and this is the caveat

**The whole drawdown at S=50 is one episode.**

```
BASE S=50: worst peak-to-trough $140.66 over windows 186..192
           — SIX consecutive closes on 2026-09-06.
```

The six worst single windows in 2.59 days:

| day | close | net | rebate | inventory | coin that won | contracts |
|---|---|---|---|---|---|---|
| 09-06 | 21:30 | **−$68.48** | +1.66 | −70.13 | **XRP** | 153 |
| 09-04 | 13:00 | −$47.54 | +3.71 | −51.25 | ETH | 85 |
| 09-04 | 00:15 | −$44.02 | +2.70 | −46.71 | **XRP** | 60 |
| 09-06 | 12:00 | −$39.67 | +2.95 | −42.62 | **XRP** | 107 |
| 09-06 | 21:15 | −$37.58 | +0.89 | −38.47 | HYPE | 102 |
| 09-04 | 22:15 | −$31.38 | +0.95 | −32.33 | HYPE | 46 |

**Concentration: the top-10 windows are 41.4% of all P&L and the bottom-10 are
−21.1%.** With 249 windows, that is a lot of the answer living in 4% of the
sample. Three of the six worst windows are XRP leading — and §5 shows XRP is
independently the worst coin to quote.

**So the bootstrap percentiles above are, in part, one episode re-shown many
times.** The honest statement is not "p95 = $187.50" but **"a $141 drawdown
happened once in 2.59 days, and resampling that tape cannot manufacture a
worse regime than the one it contains."** Rule of three: on 249 windows an
unseen-worse event is bounded only at `3/249 = 1.2%` per window.

### (c) THE SENSITIVITY THAT DECIDES EVERYTHING — shrink the rebate

The modelled share assumes nobody re-quotes against us. `REBATE_RISK.md`
model-risk #3 says that is the largest unpriced thing in the whole idea. If our
share is a fraction *m* of what is modelled:

| model | S | m | $/day | p95 5-day dd | p99 dd | **P(dd≥$250)** |
|---|---|---|---|---|---|---|
| BASE | 50 | 1.00 | **490.17** | 156.61 | 212.14 | 0.26% |
| BASE | 50 | 0.50 | 348.03 | 186.05 | 243.99 | 0.97% |
| BASE | 50 | 0.25 | 276.96 | 206.42 | 262.82 | 1.81% |
| BASE | 50 | **0.00** | **205.89** | 231.03 | 283.12 | **3.25%** |
| BASE | 100 | 0.25 | 471.24 | 320.30 | 410.05 | **86.97%** |
| BASE | 100 | 0.00 | 307.45 | 381.34 | 482.12 | **90.80%** |
| CONS | 25 | 0.00 | 22.73 | 213.51 | 260.29 | 1.65% |
| **CONS** | **50** | **0.00** | **12.74** | **339.64** | 421.84 | **22.29%** |
| CONS | 100 | 0.00 | 19.94 | 371.89 | 459.89 | 26.45% |

**This is the finding that matters.** With no rebate at all:

* under the **base** fill model the strategy still makes **$205.89/day** at
  S=50 and stays inside the clause (3.25%);
* under the **conservative** fill model it makes **$12.74/day at S=50** and
  breaches the $250 clause **22.3%** of weeks. That is a strategy that is not
  worth running and is not safe either.

The rebate is **58%** of the P&L at S=50 base and **96%** of it at S=50
conservative ($284.28 of $297.02). **Criticism C asked whether the exposure can
wipe the account. It cannot. The right question is whether the rebate is real,
and Job C cannot answer that.**

---

## 5. CONCENTRATION vs COIN COUNT

Matched on capital (~$47–49 of peak concurrent capital either way), d=3, base
fill model, 249 windows. Coins in this tape: **BTC, ETH, HYPE, SOL, XRP**.

| shape | $/day | sd per window | Sharpe/day | losing windows | worst window | peak cap (med) | %/day | **p95 5-day dd** | p99 dd |
|---|---|---|---|---|---|---|---|---|---|
| **FIVE coins, S=10** | **111.39** | 4.96 | **2.29** | 20% | −19.12 | $49.30 | 226% | **$49.26** | $62.99 |
| TWO coins, S=25 | 140.31 | 6.91 | 2.07 | 10% | −20.86 | $46.50 | 302% | $55.11 | $69.65 |
| ONE coin BTC, S=50 | 137.06 | 8.16 | 1.71 | 7% | −38.37 | $46.50 | 295% | $59.37 | $70.39 |
| ONE coin ETH, S=50 | 107.48 | 6.47 | 1.70 | 4% | −30.98 | $46.50 | 231% | $60.66 | $77.09 |
| ONE coin HYPE, S=50 | 111.03 | 8.03 | 1.41 | 8% | −38.30 | $46.50 | 239% | $76.58 | $87.15 |
| ONE coin SOL, S=50 | 82.38 | 5.55 | 1.51 | 5% | −28.90 | $46.50 | 177% | $45.09 | $57.81 |
| **ONE coin XRP, S=50** | **52.21** | 6.63 | **0.80** | 6% | **−58.00** | $46.50 | 112% | **$145.74** | **$182.82** |

### THE ANSWER

> **Five coins at S=10 beats the average single coin at S=50 on both axes:
> 1.14× the $/day ($111.39 vs $98.03) for 0.64× the p95 five-day drawdown
> ($49.26 vs $77.49), and the best Sharpe of any shape tested (2.29 vs 1.41–1.71).**
> Under the conservative fill model the same comparison gives 1.15× the $/day
> at 0.71× the drawdown.

Two honest qualifications, both of which cut against the headline:

1. **The best single coin beats five coins on $/day.** BTC alone at S=50 earns
   $137.06/day against $111.39 — but that is an **ex-post pick**, and the
   spread across coins is enormous ($52 to $137). The *worst* single coin, XRP,
   earns less than half of five-coins and carries **3× the drawdown**. The
   quantity a live operator can actually choose is "one coin", not "the coin
   that turned out best"; against that, five coins wins.
2. **Two coins at S=25 is marginally the best point on the frontier**
   ($140.31/day, dd $55.11, 302%/day on capital). The rebate share is *concave*
   in size — `ours / (ours + theirs)` — so spreading buys more total share, but
   the concavity has already mostly bitten by two markets.

### Why five coins is safer, and the limit of that argument

The structural reason is §2(c): the five legs are mutually exclusive and
exhaustive, so long-YES in all five is a box that costs 65.8c and pays 100c.
**But that hedge is almost never realised.** Measured (`part6.py`):

| S=50, base model | |
|---|---|
| windows with **no fill at all** | **36.1%** |
| windows touching **exactly one** leg | **32.1%** |
| windows holding **both sides** of some leg | 14.5% |
| **legs touched per window, mean** | **1.04 of 5** |
| largest single-leg position | median 14, p95 80, **max 150** contracts |
| spread of window P&L across the five possible winners | med $15.00, p95 $85.00, max $116.00 |

**The typical residual is one directional binary, not a five-leg box.** The
variance reduction that five coins delivers is therefore mostly *diversification
across time and across which coin gets hit*, not a within-window hedge. Say it
that way, not the other way.

---

## 6. WHAT WOULD MAKE THIS FICTION, AND WHAT THE CHECK SAID

| # | If this were true the result is fiction | What was measured | Verdict |
|---|---|---|---|
| 1 | **the tape was lucky** — 249 draws of a five-way outcome could be a good run | For every window, `E[pnl] = Σ pᵢ · pnl(coin i wins)` at the market's own closing price. BASE S=50: realised **$216.44/day** vs expected **$231.09/day** — realised is **$14.65/day WORSE** | **not lucky; if anything unlucky** |
| 1b | ditto, conservative model | CONS S=50: realised $12.89/day vs expected $2.39 — realised **$10.50/day BETTER** | **mildly lucky — the conservative inventory number is flattered and is reported as such** |
| 2 | the closing price is not a fair probability, so the redraw is meaningless | Calibration by bucket: implied 0.861 → actual 0.995 (favourites underpriced); implied 0.035 → actual 0.001 (long shots overpriced) | **a favourite–longshot bias, which makes the redraw a CONSERVATIVE stress: it over-weights long shots** |
| 3 | resting orders lock more than S·p, e.g. full $1 notional | Rulebook: collateral = *maximum possible loss*. `notional_value_dollars = 1.0000`. A BUY at p can only lose p | **holds** |
| 4 | peak capital is really the sum of per-market maxima | Reconstructed second by second and summed across legs: **96.2%** of the sum-of-maxima (median). The sum of maxima is an upper bound and is what the earlier work reported | **the earlier $254 figure was ~8% high on the median and, more importantly, silent about the $392 max** |
| 5 | "5 markets is the concurrency", so budget 5×S | Measured max is **7.4–8.4 markets' worth of S**, because consecutive closes hand over | **the 5×S rule understates the peak by up to 68%** |
| 6 | "long YES in all five legs cannot lose" | At d=3, `Σ yes-bids > 100c` in **0 of 13,463** all-five-two-sided seconds. At d=0, **62 of 13,463 = 0.46%**, worst overshoot 9c | **my own claim was wrong at d=0 and I corrected it; true at the recommended d=3** |
| 7 | the block bootstrap is really iid in disguise | Synthetic self-test: **1.01×** on uncorrelated data, **4.97×** wider on correlated data; the iid-in-disguise mutant is killed 200/200 | **holds** |
| 8 | the ruin figure is an artefact of resampling only 3 days | It is *partly* — DAY resampling has 3 blocks and its intervals are visibly too narrow. BLOCK (249 starts) and WINNER (300 series × 249 starts) both still give **P(ruin)=0.00%**, and the FLOOR bound gives 100%, so the machinery *can* print ruin | **P(ruin)=0 survives the widest honest scheme; the FLOOR proves the estimator is not blind** |
| 9 | one episode is carrying the whole drawdown | **Yes.** The entire S=50 drawdown is six consecutive closes on 2026-09-06; median dd is byte-identical across every scheme and horizon | **stated as a limitation, not hidden — see §4(b)** |
| 10 | the whole thing survives only because of a rebate nobody has been paid | **Yes.** Rebate is 58% of P&L (base) and 96% (conservative). At rebate ×0 the conservative model gives $12.74/day and breaches the clause 22.3% of weeks | **the real risk is here, not in the exposure** |
| — | the arithmetic does not reconcile | By hand: S=50 d=3, 2.9612 rebate + 2.1447 inventory = 5.1059 $/close × 96 = **$490.17/day**; ÷ 500 resting contracts = **$0.9803/contract/day**; ÷ $233.91 median capital = **209.6%/day** | **reconciles** |

---

## 7. WHERE I DISAGREE

1. **With the brief's phrasing of question 2.** *"If all five coins fill us on
   the losing side at S contracts"* is not the worst case and reads as though
   it might be. Filling *both* sides of a market is a guaranteed profit; the
   worst case is an adversarial **subset**. I computed the subset version, and
   it is **smaller** than a naive `5 × S × price` would suggest.
2. **With `REBATE_RISK.md`'s peak-capital figure of $254.** Measured properly
   as a max-over-seconds of the sum-over-legs it is **$233.91 median** — but
   **$392.29 max at S=50 and $743.36 at S=100**. The median was roughly right;
   the omission of the max is the error, and it is the max that a $1,000
   account has to fund.
3. **With the implicit "the five coins are the concurrency."** Consecutive
   closes overlap, so the true peak is **~8×S**, not 5×S.
4. **With the framing of criticism C itself.** It aims at exposure, and
   exposure is comfortably safe. The account cannot be wiped by this strategy
   at any size a $1,000 bankroll can post. The unsafe thing is that **58–96% of
   the P&L is a rebate nobody in this project has ever seen paid into an
   account.** A critic who wanted to kill this should attack the rebate, not
   the risk.
5. **With turning MECNET on**, even though it would return 31–40% of the
   inventory cash. It is irreversible per event and can block exits. Capital is
   not the binding constraint, so do not buy capital with optionality.
6. **Mildly, with the "5 coins" recommendation** — two coins at S=25 is
   marginally better on $/day *and* on drawdown than five at S=10. The
   difference is inside the noise of 2.59 days, so I would still run five for
   the coin-selection risk it removes, but the honest statement is that the
   evidence does not separate 2 from 5.

---

## 8. WHAT I COULD NOT DO

* **No live orders, no funded test.** Balance is `$0.0047`. Everything here is
  replay plus documentation. In particular **I could not observe what Kalshi
  actually locks for a resting order** — the rule is read off the rulebook and
  the `notional_value_dollars` field, not off an order acknowledgement.
* **Could not test whether MECNET applies to RESTING orders** or only to filled
  positions. The help centre says the *flag* is set at first order placement;
  it does not say the *calculation* nets unfilled orders. I assumed it does
  not, which is the conservative direction.
* **2.59 days of tape, 249 windows, one market family, one regime.** The
  whole-day block bootstrap the brief asked for has **three blocks**, two of
  them partial. Every percentile in §3 and §4 is a re-showing of one calm
  three-day window; a Coin Race close during a genuine crypto dislocation is
  not in this sample and this method cannot invent one.
* **Could not measure our own market impact.** Every fill and every rebate
  share assumes the historical tape is unchanged by our presence. At S=50 our
  size is ~40% of a median top-of-book level and we are modelled at 11.5–12.1%
  of the paid side.
* **Could not price capacity.** The 1,000-day terminal bankrolls are a
  reductio. Nothing here says how much size the $20/window pool supports before
  the share collapses.
* **Could not extract the CFTC rulebook PDF locally** (the repo has no
  `pypdf`/`pdfminer`/`fitz`, and the regex-based `jobc/pdftxt.py` returned 149
  bytes on one filing and hung on another — I killed it). The rulebook quotes
  above come from search-result extracts of the CFTC filings and the Kalshi
  help centre, **not** from a local full-text extraction. Treat them as
  well-sourced but not personally verified line-by-line.

---

## 9. NEXT STEP

**Nothing here changes the gating question, which is Job B's:** is the account
LIP-eligible, and does a payout actually land? §4(c) shows the whole risk case
turns on the rebate.

The cheapest thing Job C adds to that queue, and it needs no funding and no
sign-off:

1. **Confirm the collateral rule against a real order acknowledgement** — the
   one thing in §1 that is documentation rather than measurement. On Kalshi's
   **demo** environment (paper money, no real orders on the live exchange) a
   single resting two-sided quote of S=1 would settle it in one API call.
   **This still needs the operator's explicit sign-off** under the hard
   constraint, because it is an order, and I have not placed one.
2. **Budget 8×S, not 5×S.** At S=75 that is **$600 of the $1,000** against a
   measured max of $577.36. That is the number to write into the runbook.
3. **Leave collateral return OFF**, and know that flattening inventory requires
   cancelling the quote first.

**If the rebate is confirmed, the recommended configuration from this job is
S = 75, three ticks back, both books, all five coins** — $720/day, $349 median
peak capital, $577 worst-case peak capital, 207%/day, $0.96 per resting
contract per day, p95 weekly drawdown $228, P(ruin) 0.00%. **If the rebate is
not confirmed, none of that survives, and no size does.**

---

## RESOURCES

`kalshi_collector.py` (PID **3381772**) and `crypto_feeds.py` (PID **3385232**)
verified alive **before, during and after every heavy job** — checked five
times, the last after the final simulation. Free RAM 3.90 GB, free disk
**51.4 GB** (limit 6 GB). One stale process of my own (`jobc/pdftxt.py`, PID
3433756, catastrophic regex backtracking on a PDF) was killed by PID; nothing
else was killed and `python.exe` was never killed broadly. No call to
`replay.load_quotes`; every result reads the cached `rebate/tape.csv` and the
cached `sim_*.pkl` files.

## FILES

| path | what |
|---|---|
| `C:\Users\Joe\AppData\Local\Temp\kals-work\jobC2\selftest.py` | 41 hand-computed checks + 15 mutants, all killed |
| `...\jobC2\sim10.py`, `sim_mid.py` | the missing size arms (S=10, and 60/75/85) run through the **same** `rebate/sim.py` |
| `...\jobC2\build.py` | per-EVENT records: rebate, five legs, P&L under each of the five winners, peak concurrent capital |
| `...\jobC2\part12.py` | §1 collateral, §2 exact worst case |
| `...\jobC2\part3.py` | §3 ruin; the exact block-summary composition and its own self-test |
| `...\jobC2\part4.py`, `part4b.py` | §4 the size ladder and the rebate sensitivity |
| `...\jobC2\part5.py` | §5 concentration vs coin count |
| `...\jobC2\part6.py` | inventory shape, capital gate, concurrency |
| `...\jobC2\part7.py` | the two places my own tables contradicted my own prose |
| `...\jobC2\part8.py` | the full distribution and the per-day breakdown |
| `...\jobC2\part9.py` | the luck test and the calibration of the redraw |
| `...\jobC2\*.log` | every run's output verbatim |
| `...\jobC2\windows.pkl`, `ladder.pkl` | the per-window records everything above reads |
