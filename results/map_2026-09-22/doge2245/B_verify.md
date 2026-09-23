# B_verify — adversarial verification of `A_autopsy.md`
### KXDOGE15M-26SEP222245-45, close 2026-09-23T02:45:00Z (10:45 PM ET 09-22), Kalshi ledger −$2.4673

**IN PROGRESS — updated as each check lands.** Every number below was
re-derived with my own code in
`C:\Users\Joe\AppData\Local\Temp\claude\C--kals-repo\47b37ac1-655c-4d72-a81b-a48e9625d5bd\scratchpad\doge2245\verify\`.
Read-only throughout; no process touched.

## Headline: the autopsy is substantially right, and it missed the thing that matters

Most of it reproduces exactly — I re-derived every load-bearing number with my
own code and the arithmetic holds. **Four claims are refuted, three are weakened,
and one of its central findings turns out to be a re-discovery of a measurement
already in this repo with 30x more closes — together with a fix that is already
written, already tabulated, already pre-registered, and switched OFF.**

| claim | verdict |
|---|---|
| The index is NOT missing; 60/60 prints; settle 0.10171337 | **SURVIVES — strengthened** |
| Cushion at tau 12 = 2.61 sd; YES won by 9.8 ppm | **SURVIVES** (exact z = 2.6193) |
| The bot's sigma was right | **SURVIVES — strengthened to exact** |
| The Gaussian tail is ~3.3x too thin at this z | **SURVIVES — but not new; already 1,672 closes in-repo** |
| The 7.1c fill is price improvement, saved $10.00 | **SURVIVES — confirmed against Kalshi's own cost field** |
| "Perfect hedging was worth $1.80" | **SURVIVES** ($1.76 on my arithmetic) |
| Same event at full size ≈ 31x | **SURVIVES** (my figure −$76.8, 31.1x) |
| "Insure-at-fill hands back a fifth of the gross edge" | **REFUTED — it hands back 117-135% of it; it is a shutdown, not a policy** |
| "The model went blind for 9 seconds" | **REFUTED — logging artefact of `pinrun.py:10968`; every print arrived** |
| "Order 2's zero fill and the flip are the same event" | **REFUTED — two exchanges' clocks put it 140 ms early** |
| "658 exceedances = 208 independent runs, the well-powered measurement" | **REFUTED as a power claim — n is 53 closes of one coin** |
| "Could not measure whether the tail generalises past DOGE" | **REFUTED — already measured, 1,672 closes, every coin** |
| "The 11-lot's best recovery was +18c, 4c of headroom" | **WEAKENED — ~+25c reachable, ~10c of headroom; a depth bound, not arithmetic** |
| Live band contrast 0.8% vs 4.7% | **WEAKENED — 1.60% vs 3.33% on 3x the sample, and both bands made money** |

**The three things worth acting on, none of which are in `A_autopsy.md`:**

1. **`--honest` — the measured fix for exactly this mechanism — has never run
   once.** It would have refused this trade (confidence 0.98388 vs `pin 0.995`).
   Three self-test fixtures that hard-code Gaussian answers have blocked it since
   2026-09-17. Section 0.
2. **Two independent exchange clocks say the move began 61 ms AFTER we sent the
   order.** Nothing was visible at decision time, so every market-reading
   prevention is hindsight — and the $74 that "luck" saved was the routine 35.7%
   zero-fill rate, not this event. **This loss pays −$77 about two times in
   three.** Section 2.
3. **The money is not being lost here.** 18% of every contract we have bought was
   bought at 98c or more, over 102 closes, for **−$4.40** — and that bucket holds
   our largest single loss (−$107.95). This market paid 20.38c average and risked
   $2.65. Section 7c.

---

## 0. THE FINDING THE AUTOPSY MISSED — the fix is written, measured, pre-registered, and has never once run

This is worth more than everything else in this file put together, so it goes first.

The autopsy's section 2 concludes "the problem is the Gaussian tail bolted onto
[the variance collapse]... at z = 2.619 the model says 0.441% and the truth is
1.435%, 3.3x." **That is correct. It is also already in this repository,
measured 30x better, with the fix already coded.**

`research/pincalib.py` → `results/RESULTS_calib.md`, built 2026-09-13:
**109,122 z-scores over 1,672 closes, 19.2 days, every coin**, from the
settlement index alone. It found sd(z) = 1.151, kurtosis 132, and:

| model says it is this sure | promised failure | realised | off by |
|---|---|---|---|
| 99.00% | 1.00% | 2.0995% | 2.1x |
| **99.50%** | **0.500%** | **1.6734%** | **3.3x** |
| 99.85% | 0.150% | 1.2069% | 8.0x |
| 99.99% | 0.010% | 0.6965% | 69.6x |

I read `results/calib_table.json` (n 109122, closes 1672) and interpolated it
at this trade's exact z myself:

```
z = 2.6193   Gaussian tail 0.441%   measured tail 1.612%   ratio 3.7x
```

The autopsy's own DOGE-only 13.4-hour figure was **1.435%**. The repo's
1,672-close figure is **1.612%**. They agree to within 12%, so the autopsy's
number is CONFIRMED by a far better-powered independent measurement — and is
slightly on the optimistic side.

**And the fix is `pinrun.py`'s own `--honest` flag** (AMENDMENT 19, lines
2688-2760). It routes `fair()`'s z through that measured table instead of
`Phi()`. Running the table myself at this trade's z:

| | this trade |
|---|---|
| model confidence (deployed, Gaussian) | **0.99559** → passes `pin 0.995` by 0.059 pp |
| honest confidence (same z, measured table) | **0.98388** |
| verdict under `--honest` | **REFUSED** |

`--honest` with `pin 0.995` demands **z ≥ 4.316** (I computed it; `PREREG_honest.md`
says 4.33 — match). This trade was z = 2.6193. **It would never have been placed.**

**`honest_conf: false` in the live bot's own `start` record for this run.** And:

> `results/arm-tau45honest.err` (2026-09-17 01:47): `self-test failed -- nothing ran`

**`--honest` has never run. Not live, not on a paper arm, not once.** The single
attempt, five days ago, died at startup with three self-test failures, and all
three are old checks that hard-code *Gaussian* answers:

1. `the corrected model says YES (fair 0.9941)` — the check wants 1.0; the
   measured table's ceiling is 0.9941.
2. `doubling sigma lowers confidence in NO from 0.50125 to 0.50125` — the
   measured table is flat near z = 0, so the two are equal and the check fails.
3. `a decision at z=2.40 clears 0.990 (0.98027)` — under the measured table
   z = 2.40 gives 0.98027, so it does not clear 0.990.

None of these is a defect in `--honest`. All three are self-test fixtures
asserting the *distribution* rather than the *code path*. This is the exact
failure mode already written down in this project's memory ("pinrun self-tests
at STARTUP with flags applied and old checks assert running values").

**So: the mechanism that lost this market is measured on 1,672 closes, the
remedy is written and pre-registered, and it has been blocked for five days by
three test fixtures — and nothing reported that.** Fixing those three fixtures
so a `--honest` paper arm can start is the highest-value thing in this autopsy.

---

## 1. The price — SURVIVES, exactly

I pulled `DOGEUSD_RTI` out of `kalshi_data/cfbenchmarks_value/20260923T02.jsonl.gz`
with my own reader. 60 of 60 prints present for `[close−60, close−1]`, no gap.
**Stronger than the autopsy claimed: CF's own `avg_60s_data` block travels on the
same message and states `window_size: 60`, so the exchange itself certifies all
60 prints — and its published average is byte-identical to my own mean.**

| | value |
|---|---|
| my mean of the 60 prints | `0.10171337` |
| CF's own published 60 s average, stamped at the close | `0.10171337` |
| the 02:30 window, same two ways | `0.10170363` / `0.10170363` |
| the 02:45 strike Kalshi published | `0.1017036` |

`strike(N+1) == settle(N)`. Window definition and data source both confirmed
twice over. **Settle − strike = +9.767e−06 = 9.8 parts per million = 0.96 bp.**

My own z table (own `var_factor`, and `eff_strike = strike − 0.5·10⁻⁷` because
the signal logged `digits: 7`):

| tau | locked | locked mean − K | spot − K | running mean − K | r | sd remaining | z | P(NO) |
|---|---|---|---|---|---|---|---|---|
| 45 | 16 | −6.98e−06 | −1.86e−05 | −1.550e−05 | 44 | 3.142e−05 | −0.49 | 0.6886 |
| 20 | 41 | −1.62e−05 | +9.40e−06 | −8.083e−06 | 19 | 9.112e−06 | −0.88 | 0.8110 |
| **13** | 48 | −1.43e−05 | +5.40e−06 | −1.035e−05 | 12 | 4.674e−06 | **−2.20** | **0.9862** |
| **12** | 49 | −1.393e−05 | +3.40e−06 | **−1.075e−05** | 11 | 4.085e−06 | **−2.619** | **0.99559** |
| 11 | 50 | −1.358e−05 | +3.40e−06 | −1.075e−05 | 10 | 3.564e−06 | −2.97 | 0.9985 |
| 10 | 51 | −1.133e−05 | +1.014e−04 | +5.583e−06 | 9 | 3.066e−06 | +1.82 | 0.0344 |
| 0 | 60 | — | +1.124e−04 | +9.767e−06 | 0 | — | — | 0 |

**I added the tau-13 row the autopsy did not have, and it matters: at tau 13 the
model was at 98.62%, below `pin 0.995`. The trade fired the very first second it
crossed the bar.** It cleared 0.995 by 0.059 percentage points and was taken
immediately. That is the marginal trade by construction, not by accident.

- **Cushion at tau 12 = 2.619 sd of the remaining window** (1.070e−05 / 4.085e−06).
  The autopsy's 2.61 is right to two decimals; it used the nominal strike and a
  rounded sigma and the two errors partly cancelled. 2.6193 is the exact figure
  and it reproduces the bot's logged `fair 0.00441` to five decimals.
- The 49 locked prints averaged **1.393e−05 BELOW** the strike. The brief's
  "spot 3.4e−06 above the strike" is indeed not the margin. **SURVIVES.**
- YES needed the remaining 11 prints to average **+6.176e−05** above the strike
  = 5.61 sigma = 6.07 bp. They averaged **+1.153e−04** — overshot 1.87x. **SURVIVES.**
- At tau 10 one print carries 9/60 of the settle estimate, so the +9.80e−05 print
  moved the estimate +1.470e−05 = **4.75 sd in one second**. **SURVIVES.**

### The sigma claim — SURVIVES, and is stronger than stated

The autopsy compared its measured 1.0860e−05 against "the 1.1000e−05 the bot
logged" and called it 0.99x. **The logged field is `round(sg, 6)`, so it only
says sigma was somewhere in 1.05e−05 to 1.15e−05.** Taking a rounded log field
as exact is not a safe method. Doing it the other way round instead — inverting
the bot's own logged `fair` through my z arithmetic:

```
bot's implied sigma (from fair 0.004405, exact mu−K, exact var_factor) = 1.08960e-05
my trailing-300s sigma from the collector's tape, the bot's own recipe        = 1.08960e-05
```

**Identical to six significant figures.** The bot's volatility estimate was not
approximately right, it was exactly right, and its index history matched the
collector's print for print. The conclusion survives; the method that got there
did not.

---

## 2. The exchange-feed reconstruction — the attack lands, and it produced the single best finding

The brief asked whether a rebuild from `feed_data` is trustworthy for a
ten-second window. **It is not, at the resolution this question needs — and it
does not matter, because it answers a better question instead.**

**Which exchanges carry DOGE:** coinbase (ticker), kraken (ticker), bitstamp
(order book). **Gemini carries no DOGE at all** — I checked 21,241 lines.
So three feeds, not five.

**Why the rebuild cannot resolve this trade** (`index_replica`, per-second):

| | |
|---|---|
| `n_ex` for tau 15 → tau 11 | **1** — bitstamp alone. Coinbase and kraken absent for the five seconds before the flip. |
| kraken's mid, tau 10 → tau 1 | **frozen at 0.1017339 for ten consecutive seconds** — a stale quote counted as a live exchange |
| replica vs the real index, quiet second (tau 11) | 7e−07 apart |
| replica vs the real index, the decisive second (tau 10) | **4.2e−05 apart — four times the entire 1.07e−05 cushion** |

So: in quiet water the rebuild tracks the index to under a millionth; in the one
second that decided the market it is off by 4x the whole margin, and it was
running on a single exchange immediately beforehand. **Had the index truly been
missing, no honest statement about which side of the strike the settle landed
could have been made.** The autopsy was right to use the index and right to
label the replica a cross-check; but "it agrees on shape" is all it can support.

### What the raw exchange feeds DO establish, and it is the answer to the operator's question

Coinbase timestamps its own ticks. Bitstamp timestamps its own book to the
microsecond. Both are independent of Kalshi and of us.

| event | timestamp (UTC) |
|---|---|
| order 2 decided / sent | 1790131488.806 / **.808** |
| order 2's round trip completes, 0 of 82 filled | **1790131488.967** |
| order 3 decided / sent | 1790131489.044 / **.046** |
| **coinbase DOGE starts moving** — 26 ticks, 0.10172 → 0.10194 | **1790131489.107 → .213** |
| bitstamp's book still quiet at 0.101697 / 0.101703 | 1790131489.110 |
| bitstamp's book has jumped to 0.101770 / 0.101822 | 1790131489.307 |
| order 3 fills, 11 @ 7.1c | ≈ 1790131489.221 |

Two independent exchanges put the start of the move at **1790131489.11 ± 0.2 s**.

1. **The move began 61 milliseconds AFTER we sent order 3.** At the moment of
   decision the constituent books were quiet — coinbase had not printed a DOGE
   tick for **14.8 seconds**. There was nothing to see, so no gate, filter,
   jump detector, freshness check or sigma could have seen it. **Every
   "prevention" that reads the market at decision time is hindsight.**
2. **Order 2's zero fill was NOT part of the flip.** Its round trip finished
   **140 ms before the move started**. The autopsy says "both facts are the same
   event: the NO offer side was pulled and the YES bid side jumped, inside one
   second, and our orders crossed it mid-flip." **REFUTED by two exchanges'
   clocks.** Order 2 lost an ordinary race to another taker — and I measured
   that base rate: **451 of 1,263 live entry orders fill nothing, 35.7%**
   (AMENDMENT 18 quotes 28.2% on a smaller sample).
3. So the $74 that order 2's zero fill saved is not event-specific luck. It is
   **the routine 36% coin-flip that AMENDMENT 18 exists to reduce.** Raising our
   fill rate raises the size of this loss class one-for-one. That trade-off is
   not written down anywhere.

---

## 3. The fills and the 7.1c — SURVIVES, confirmed three independent ways

The task asked whether the 7.1c is a logging artefact or a NO/YES mix-up. It is
neither.

| test | result |
|---|---|
| `exec_price 0.071 + exec_yes_price 0.929` | = 1.000 exactly |
| 2 × 93.4c + 11 × **7.1c** | = **$2.6490** = Kalshi's own `no_total_cost_dollars` **2.649000**, to the cent |
| the same sum if order 3 had filled at the 98.0c ask it saw | $12.6480 — Kalshi would have booked ~$12.60, not $2.649 |
| side mix-up? | 13 NO *and* 13 YES on one row; `market_result yes`; payout $13.00 on the YES side. A mix-up would put ~$12.7 on the NO line. It says $2.649. |

Full reconciliation with my own fee function (`ceil(0.07·n·p·(1−p))` to $0.0001):

```
 NO  cost  $2.649000   Kalshi no_total_cost_dollars   2.649000   exact
 YES cost $12.741000   Kalshi yes_total_cost_dollars 12.741130   −$0.00013
 fees      $0.077200   Kalshi fee_cost                0.077170   +$0.00003
 payout $13.00                                    NET  −$2.4673 = Kalshi's −$2.4673
```

**The 7.1c is real and it is price improvement worth exactly $10.00** (90.9c ×
11). Had that leg filled at its ask the market would have been −$12.47.
**SURVIVES.**

Two corrections to the autopsy's fill table, from the raw records:

- Order 2's signal carried `ladder_under: 6195.4`, but **6,095 of those 6,195
  sat on one level at 97.9c.** An 82-contract IOC at limit 98.0c would have
  swept 62.4 @ 93.4c then 19.6 @ 97.7c, not 82 flat at 93.4c.
- Order 1's `level_age_ms 866790` with `level_age_exact: false` is a lower bound
  from the 02:30:22Z snapshot, i.e. "we never saw this level appear". The
  autopsy reads this correctly; I confirm it — 866.79 s before 02:44:48.8Z is
  02:30:22Z, the second the `watch` record added DOGE.

### The "9 blind seconds" — REFUTED

The autopsy: "`last_belief` is recomputed from `fair()` on every loop pass, yet
the `hedge_quote` records show it byte-identical at `0.0514329175139725` for tau
9 → 1 ... **no new index print arrived after tau 10**."

`pinrun.py` line **10968**, inside the hedge pass and **above** the `fair()` call:

```python
if _hid in hedged or _hid.startswith("hedge-"):
    continue
```

Once a position is fully hedged it is added to `hedged` and the loop skips it
before `fair()` runs, so `last_belief[ticker]` is never written again.
`hedge_quote` (line 11464) only *reads* `last_belief`. The 2-lot was hedged at
tau 10 and the 11-lot at tau 9; every `hedge_quote` from tau 8 down reads a
value nobody is updating. **The frozen belief is a logging artefact of correct
behaviour, not a blind model.**

And the collector's own tape settles the factual question: **every one of the
last ten prints arrived** (tau 10 … tau 0, no gap). The index never stopped.

The autopsy's *parallel* observation is correct, though, and I confirm it: the
tau-12 and tau-11 beliefs really are identical at `0.9955949944046358` while
`index_age_s` went 0.52 → 0.80 → 1.04, because the print for second
…489 had not yet reached the bot. **A print that arrived 6 ms sooner would have
made the bot MORE confident, not less** (z would have gone 2.619 → 2.97, since
`r` falls to 10 and the value was unchanged at 0.1017070). So index staleness
did not cause this, and a fresher feed would have made it worse.

Measured on our own fills, staleness is not a signal at all:

| population | fills | contracts | markets | closes | lost | rate | net $ | c/contract |
|---|---|---|---|---|---|---|---|---|
| index print ≥ 1.0 s old at the send | 73 | 4,409 | 73 | 70 | 2 | 2.74% | +$67.64 | +1.534c |
| index print < 1.0 s old | 440 | 26,991 | 422 | 319 | 9 | 2.13% | +$462.54 | +1.714c |

### One thing the autopsy missed: the hedge could not retry for 656 ms

The 11-lot's first hedge (tau 10, `limit_sent 0.979` against `ask 0.949`,
`ask_size 1.0`) filled **zero**. `hedge_last_try[_hid] = now_s` then blocked any
retry until the wall-clock second advanced — **656 ms** — and by then the ask was
98.0c. The one-try-per-second rule is deliberate and documented (an early alarm
burned five tries in 250 ms), but a try that bought **nothing** is not the spam
risk it guards against, and `hedge_max_tries` was 30 with 9 seconds left.
Here it cost about **4c** (only 1 contract was offered at 94.9c anyway), so it is
not this market's problem — but on a larger position in a faster book it is
uncapped, and lifting the block *after a zero fill* removes a delay rather than
adding a gate.

---

## 4. The hedge — mostly SURVIVES, one number REFUTED and one WEAKENED

My own recovery arithmetic at each second's logged YES ask reproduces the
autopsy's table cent for cent (+92.86c, +92.96c, +6.16c, +1.21c, …). The
insurance really did reprice **14x in one second**, 6.6c → 93.4c. **SURVIVES.**

What perfect timing was worth, my figures:

| | market total |
|---|---|
| insure the 2-lot at tau 12 (86.8 offered at 6.7c) | **−$0.7080** |
| insure the 2-lot at tau 11 (29.0 offered at 6.6c) | **−$0.7059** |
| what happened (trigger at tau 10) | **−$2.4673** |
| never hedge at all | **−$2.7085** |

**Perfect insurance on the 2-lot was worth $1.76** (the autopsy said $1.80 — it
used an 18.3c recovery on the 11-lot instead of the 14.33c actually achieved).
**SURVIVES.** The hedge as executed recovered 24.13c of 270.82c at risk, 8.9%.
**SURVIVES.**

**The 0.40 trigger cost nothing. SURVIVES.** Belief was 0.99867 on one pass of
tau 10 and 0.05143 on the next; any threshold from 0.05 to 0.9956 fires at the
same instant. And I can now say *why* no earlier trigger was possible: the
underlying move had not happened yet — coinbase was quiet until
1790131489.107. `jump_sd` was `null` on both alarms because there was no jump to
measure.

### REFUTED — "insure-at-fill hands back about a fifth of the gross edge"

```
buy NO 93.4c + buy YES 6.7c = 100.10c, + fees 0.44c + 0.44c = 100.98c
                                        for a certain payout of 100c
                        LOCKED LOSS = -0.98c per contract, guaranteed
```

Insure-at-fill does not cost a fifth of the edge. It converts a positive
expectation into a certain small loss:

| the unhedged trade's EV at 93.4c, priced on | EV | what insure-at-fill costs |
|---|---|---|
| the model's 0.441% | +5.719c | −6.699c = **117% of it** |
| the repo's measured tail, 1.612% | +4.548c | −5.528c = **122% of it** |
| our own live rate in this band, 3.33% | +2.830c | −3.810c = **135% of it** |

**A blanket insure-at-fill is not a policy with a price, it is a shutdown.** The
autopsy's own arithmetic (100.1c + 0.88c for 100c) is correct; calling the result
"a fifth of the gross edge" is wrong by a factor of six, and it makes a
catastrophic option look affordable. This is the one number in `A_autopsy.md`
that could move live code in the wrong direction.

### WEAKENED — "the 11-lot could never be insured, as a matter of arithmetic"

Two different bounds are being conflated.

- **The arithmetic bound is real:** we bought NO at 7.1c, which means we sold YES
  at 92.9c into a resting bid, so the YES ask was ≥ 92.9c. Best conceivable
  recovery = 11 × (100 − 92.9 − 0.47) = **+73.02c**, leaving the leg at −10.16c.
- **The depth bound is what actually bound:** the tau-9 `hedge` record shows
  `ask 0.98, ask_size 60.41`. A limit of exactly 0.98 rather than the swept 0.999
  gives 1 @ 93.4c + 10 @ 98.0c = **+24.78c**, leaving the leg at −58.40c.
- **Achieved: +14.33c.** So the headroom was **≈ +10.5c**, not the autopsy's ~4c.

Still small, and the conclusion (the 11-lot was uninsurable in any material
sense) stands. But the claim is a *depth* claim dressed as an *arithmetic* one,
and it understates the reachable best by 6c.

### A caveat neither report can escape

**The Kalshi order-book tape is genuinely deaf for this window** — I checked all
four market channels: `orderbook_delta` stops at 1790130712363 = **02:31:52Z**,
`ticker` and `trade` at 02:31:4xZ, and there is one `orderbook_snapshot` at
02:31:20Z. Only `cfbenchmarks_value` reconnected. **So every statement about the
Kalshi book in the final 15 seconds rests on the bot's own cached snapshots and
cannot be independently checked.** And those snapshots are one-per-second reads
of a cache: at tau 10 `hedge_quote` said `ask 0.934 size 1.0` while the two
`hedge` records in the same second saw `0.936 size 2.0` and `0.949 size 1.0`.
The prices are trustworthy to the tick; **the sizes in the autopsy's hedge table
are not trustworthy to the contract.**

---

## 5. Luck, not design — SURVIVES, with the mechanism corrected

Full size as actually ordered, sweeping the real ladder order 2 saw:

```
sweep 62.4 @ 93.4c + 19.6 @ 97.7c = $77.4308 + fee $0.3002  = -$77.7310 unhedged
hedge 74.41 @ 98.7c + 7.59 @ 99.0c = $81.0290, pays $82.00  =      +$0.9710
                                                       NET  =     -$76.7600
```

**−$76.76 against −$2.4673 = 31.1x.** The autopsy's −$75.95 and "31x"
**SURVIVE**; it used 82 flat at 93.4c and so was $0.8 optimistic.

Luck accounting, my figures: $74.29 (order 2's zero fill) + $10.00 (order 3's
price improvement) = **$84.29 of luck**, against $2.47 booked. The autopsy's
"~$84 of the ~$86.5" is **exact**. `price_ceiling 0.98` blocking a 27-lot at
98.1c avoided about **$26.1** more (27 × 98.1c at risk, ~+$0.35 recovered by a
98.6c hedge) — design, and it worked. `max_per_market 2` closed the market after
two fills — design.

**But the mechanism is not what the autopsy says, and the correction makes this
worse rather than better.** The $74.29 is not the flip evaporating our order; it
is the ordinary 35.7% zero-fill rate, 140 ms before the flip began. We win that
race about 64% of the time. **So the honest statement is not "we got lucky", it
is: this event pays out −$77 roughly two times in three, and we drew the other
one.** Nothing about the size, the gates or the hedge changes that; only the
race does.

---

## 6. The tail finding is right — but the autopsy's own evidence for it does not carry the weight it claims

Section 2 of the autopsy reports a DOGE-only measurement: "45,862 one-second
samples ... **658 exceedances ... 208 independent runs ... 53 of 56 closes**", and
calls it "the well-powered measurement".

**It is not well-powered, and this repo's own hard rule 4 says why: `n` is closes.**
The quantity being measured — did the settle land more than z of its own sd on
the wrong side — has **one outcome per close**, and every one-second sample
inside a close shares that one settle. A single bad close contributes hundreds of
"exceedances"; the exceedance *count* is occupation time, which is exactly the
selection CLAUDE.md warns against under "sample on an exogenous grid". Stated
honestly, the autopsy's evidence is **53 closes of one coin**, where a Gaussian
predicts 0.23 events and the measured rate predicts 0.76. Those are
indistinguishable.

**The conclusion is nonetheless correct, because a far better measurement of
exactly this already exists in the repo** (section 0 above): `pincalib.py`,
**1,672 closes**, all coins, 19.2 days — and it puts the tail at z = 2.6193 at
**1.612%** against the autopsy's 1.435%. So:

- the autopsy's **number** is confirmed to within 12% by a 30x better sample;
- the autopsy's **own evidence for it** is weak and mislabelled as strong;
- the autopsy's "could not measure: whether the tail table generalises past DOGE"
  is **wrong — it was already measured across every coin on 2026-09-13.**

`sd(z) = 1.143` (autopsy) vs `1.151` (repo, 1,672 closes): agreement.
"Fat tails, not mis-scaled vol": **SURVIVES**, and the repo says the same thing
and adds the two tests the autopsy did not run — scaling sigma by 1.25x makes
the surviving candidates *worse*, and no Student-t fits.

### And what the market thought — SURVIVES

We crossed a 6.6c YES bid, so the market priced P(YES) at 6.6–6.7% (the book was
0.1c wide) against the model's 0.441% — **15x**. The measured 1.612% sits between.
**SURVIVES.** But note what this implies: the market-implied risk is mechanically
1 − (the price we pay), so "refuse when the market disagrees with the model by
more than 10x" is identical to "refuse the cheapest NO", i.e. refuse our
highest-edge trades. `close_summary` makes that concrete — **this market was the
single best-looking opportunity of the whole close** (`best_edge_c 5.728`,
`best_fair 0.00441`, `best_price 0.934`, `best_ticker` = ours). The best-looking
trade of the close is the one that lost.

### The break-even price, corrected

| | at z = 2.6193 |
|---|---|
| Gaussian tail | 0.441% → break-even NO price 99.13c |
| autopsy's measured tail 1.435% | break-even **98.46c** |
| **repo's 1,672-close table, 1.612%** | break-even **98.27c** |
| EV at the 98.0c ceiling, honest tail | **+0.248c per contract** (autopsy said +0.425c) |
| EV at 93.4c, honest tail | **+4.548c per contract** |

So the autopsy's break-even is 0.19c too generous and its ceiling EV is 1.7x too
generous. And the claim that `price_ceiling` is "the only thing standing between
the live bot and negative EV here" is **WEAKENED**: `expected_value()` already
applies a flat 0.9% flip (break-even ~99.0c) and `ev_implied_ceiling` is 0.988.
Three caps overlap; 98.0c is merely the tightest.

**The real point, which neither the flat-flip test nor the Gaussian gate sees:
the flat 0.9% flip is roughly half the honest 1.6% at the exact z where the gate
lets trades through.** At the `pin 0.995` bar (z = 2.576) the honest tail is
1.663% and the honest break-even price is **98.22c** — 0.22c above the deployed
ceiling. The marginal trade earns about a fifth of a cent per contract while
risking 98.

---

## 7. NEW — what our OWN fills say, on 3x the sample the autopsy used

The autopsy matched **172** entry fills to a signal `fair`. Matching on
`(run, ticker, second, ask_seen == signal price)` I matched **513** of 811
filled entry orders, across **352 closes**, and joined every one to Kalshi's own
settlement row. This is the population CLAUDE.md's rule 5 says is the only valid
source for how often *we* lose.

### 7a. The band table — the autopsy's contrast does not hold up, but the honest table does

| band | markets | closes | lost | rate | 95% CI | net $ | Gaussian says | honest table says |
|---|---|---|---|---|---|---|---|---|
| model loss chance < 0.4% | 376 | 299 | 6 | **1.60%** | [0.59, 3.44] | **+$347.16** | 0.17% | 1.25% |
| **0.4–0.5% (this trade)** | 120 | 111 | 4 | **3.33%** | [0.92, 8.31] | **+$144.79** | 0.45% | 1.62% |
| all matched fills | 490 | 352 | 10 | 2.04% | [0.98, 3.72] | +$480.61 | | |

Against the autopsy's 0.8% (1 of 118) and 4.7% (2 of 43): on the larger sample
the contrast falls from **5.6x to 2.1x**. **WEAKENED.** The direction holds.

What is new and matters more:

1. **On our own fills the Gaussian is off by 9.4x and 7.4x. The repo's honest
   table is off by 1.3x and 2.1x.** `PREREG_honest.md` names as its central
   unknown "whether a gate calibrated on the index does anything to our
   population, and the two differ by 31x". **This answers it: the honest table
   lands within a factor of two of our live loss rate where the Gaussian is out
   by an order of magnitude.** The residual 1.3–2.1x is the adverse selection the
   index population cannot see.
2. **Both bands made money.** The marginal band — the one the autopsy points at —
   returned **+$144.79**.

### 7b. Pricing every live fill three ways — this is the load-bearing result

513 fills, **31,400 contracts**, 343 closes. For each fill I took its own z, read
the repo's measured tail at that z, and priced the contract honestly:

| bucket | fills | contracts | Gaussian EV | honest EV | ACTUAL |
|---|---|---|---|---|---|
| honest EV ≥ +0.3c | 488 | 30,069 | +$1,062.95 | +$765.85 | +$505.11 |
| honest EV 0 to +0.3c | 25 | 1,331 | +$18.93 | +$3.32 | +$25.07 |
| **honest EV negative** | **0** | **0** | — | — | — |
| **TOTAL** | **513** | **31,400** | **+$1,081.88** | **+$769.17** | **+$530.18** |
| per contract | | | **+3.445c** | **+2.450c** | **+1.688c** |

**Not one of our 513 live entry fills was negative-expectation under the honest
tail.** The fat tail does not make the strategy bad; it takes it from 3.4c to
2.4c per contract. And our realised 1.688c is **31% below even the honest number**
— $239 short over 31,400 contracts — which is the adverse selection on top.

**This kills `--honest`-as-a-gate as a recommendation.** At `pin 0.995` the
honest table demands z ≥ 4.316; that would have refused essentially every one of
these fills, forfeiting **+$530** of realised entry profit to avoid 11 losing
markets. The table belongs in the *price* test, not the *confidence* gate.

### 7c. Where the money is actually being lost — by price paid

| price paid | fills | contracts | markets | closes | lost | rate | net $ | c/contract |
|---|---|---|---|---|---|---|---|---|
| under 90c | 19 | 1,154 | 19 | 18 | 4 | 21.05% | +$0.75 | +0.065c |
| 90–94c | 45 | 3,206 | 43 | 42 | 2 | 4.65% | **+$153.28** | **+4.781c** |
| 94–96c | 54 | 3,740 | 53 | 51 | 2 | 3.77% | +$41.33 | +1.105c |
| 96–97c | 62 | 3,879 | 62 | 57 | 0 | 0.00% | **+$123.84** | **+3.193c** |
| 97–97.5c | 50 | 3,280 | 50 | 48 | 1 | 2.00% | +$0.84 | **+0.026c** |
| 97.5–98c | 173 | 10,473 | 168 | 150 | 1 | 0.60% | +$214.54 | +2.049c |
| **98c and up** | **110** | **5,669** | **106** | **102** | 1 | 0.94% | **−$4.40** | **−0.078c** |
| total | 513 | 31,400 | | | | | +$530.18 | +1.688c |

**18% of every contract we have ever bought was bought at 98c or more, over 102
closes, and it has returned minus four dollars.** Honest EV says it *should*
return +0.25c/contract = +$14; it returned −$4.40. Both numbers are "nothing",
and they sit next to our single largest loss.

**Stated as the half-comparison it is:** that bucket's sign is decided by one
market, `KXBTC15M-26SEP191600-00` — **110 contracts at 98.00c, −$107.95**, at a
model loss chance of 0.00056 (the *most* confident reading we have ever traded).
The bucket's wins total about +$103. At 98c the arithmetic needs ~50 wins per
loss and we lose about 1 market in 106, so **the bucket is a coin-flip on its own
sign by construction** — near-zero mean, enormous variance, 98c of capital at
risk per contract to earn a quarter of a cent.

Every losing market in the matched set, ranked (Kalshi's own money):

| net $ | ticker | contracts | avg price | tau | model fair |
|---|---|---|---|---|---|
| **−107.95** | KXBTC15M-26SEP191600-00 | 110.0 | **98.00c** | 45 | 0.00056 |
| −66.34 | KXBTC15M-26SEP190200-00 | 70.0 | 94.40c | 35 | 0.00313 |
| −61.75 | KXBNB15M-26SEP191230-30 | 82.8 | 97.27c | 23 | 0.99863 |
| −59.09 | KXNEAR15M-26SEP211245-45 | 81.0 | 91.10c | 44 | 0.99557 |
| −57.76 | KXBNB15M-26SEP190145-45 | 76.0 | 74.98c | 24 | 0.99926 |
| −29.90 | KXHYPE15M-26SEP141600-00 | 62.0 | 95.16c | 30 | 0.00383 |
| −27.87 | KXBTC15M-26SEP172115-15 | 99.0 | 53.00c | 38 | 0.99561 |
| **−2.47** | **KXDOGE15M-26SEP222245-45** | **13.0** | **20.38c** | 11 | 0.00441 |
| −0.47 | KXBNB15M-26SEP161230-30 | 1.0 | 97.70c | 30 | 0.00479 |
| +4.36 | KXDOGE15M-26SEP180015-15 | 33.6 | 11.00c | 32 | 0.99707 |

**−$409.25 over 10 markets.** Loss size is contracts × price, and this market was
cheap on both: 13 × 20.38c = **$2.65 at risk**, against 62–110 contracts at
53–98c in every other one. **DOGE-2245 is not a member of the population that is
costing money.** It is the cheapest loss on the list.

---

## 8. Is any claimed prevention visible BEFORE the entry, or is it hindsight?

The task's third attack. I scored every candidate on our own live fills, so each
one is quoted with what it would have blocked and what that cost.

| candidate | visible before the send? | what it blocks, on our own fills | verdict |
|---|---|---|---|
| Anything that reads the market at decision time (jump gate, book age, level freshness on price, market-implied disagreement) | **NO — the move began 61 ms after the send; coinbase had been silent 14.8 s** | — | **HINDSIGHT** |
| Tighter `max_index_age_s` (was 2 s, the print was 1.04 s old) | yes | 73 fills / 70 closes / **+$67.64**, and the missing print was *identical in value* — a fresher feed raises z from 2.619 to 2.97, i.e. MORE confident | **REFUTED — would make it worse** |
| `late_tau 12` instead of 10 (so `late_pin 0.9975` covers tau 11–12) | **yes — refuses this trade outright at conf 0.99559** | 30 fills / 1,651 contracts / 28 closes / **+$76.16, +4.61c per contract** — our most profitable slice | **REJECT: costs $76 to save $2.47** |
| `--honest` as the confidence gate (z ≥ 4.32) | **yes — refuses this trade at conf 0.98388** | essentially all 513 fills; **forfeits +$530**, and zero of them were honestly negative-EV | **REJECT as a gate; ADOPT as the price test** |
| Zero-fill brake (order 2 filled 0 of 82 → don't send order 3 76 ms later) | **yes — this is real information, logged at 02:44:48.967** | only **4 fills in the entire live history** came within 1.5 s of a zero fill; 1 of 4 lost (this one); +$1.48 | **UNTESTABLE — n = 4, far under the 30-close floor. Do not deploy.** |
| Level age < 250 ms (`RESULTS_select`'s slice; order 3's level was 38 ms old) | yes | 226 fills / 187 closes / 8 of our 10 losses / 3.72% vs 1.83%, but still **+$82.87** | signal is real, blanket block still forfeits $83 |
| **Level age < 250 ms AND price ≥ 98.0c** | yes | **39 fills / 1,561 contracts / 37 closes / −$80.92, −5.18c per contract** | **strongest identified population — but see the caveat** |
| Price ≥ 98.0c alone | yes | 110 fills / 5,669 contracts / 102 closes / **−$4.40** | see below |

**Nothing would have stopped this loss without costing more than it saved.** Every
gate that refuses this trade refuses a slice that has made money. The exchange
clocks say why: at the instant of the decision there was nothing to see.

**Two caveats I am required to state.** Every price and level slice above was
chosen *after* looking at these fills, so each is a hypothesis, not a result — and
`pinrun`'s own self-test currently asserts that nothing branches on `level_age_ms`
precisely because `RESULTS_select`'s slices were chosen the same way. And the
−$80.92 in the best-looking cell is **one market** (the −$107.95 BTC fill) against
about +$27 of wins; 37 closes clears the floor for the *rate* but the *money* is a
single draw. A pre-registered live bar is the only honest next step.

---

## 9. Could not measure

- **Whether the Kalshi book really collapsed, independently of our own records.**
  All four market channels stop at 02:31:5xZ; only `cfbenchmarks_value`
  reconnected. Every book statement here is our own cached snapshot.
- **Whether the bot's index socket differed from the collector's.** The sigma
  back-out proves its tick history matched the collector's exactly up to tau 12,
  and the "9 blind seconds" is explained by the `hedged` skip, so there is no
  longer any evidence of a socket problem — but no disconnect record exists either
  way.
- **Whether the ≥98c bucket is genuinely negative.** Its sign turns on one market.
- **Whether the fresh-level × expensive-price cell is real.** Same single market.
- **The intra-second Kalshi book between 02:44:49.046 and .221.** Our fill price
  is the only witness.
- **Whether `--honest` actually reduces OUR loss rate.** 7a says it predicts it
  within 1.3–2.1x, which is far better than the Gaussian's 7–9x, but the flag has
  never run once.

---

## 10. Solutions worth testing, in the operator's priority order

**1. Fix the three self-test fixtures blocking `--honest`, then run it as a paper
arm.** It is the only measured correction to the mechanism that lost this market,
and it has been unrunnable since 2026-09-17 because three checks assert Gaussian
answers (`fair 0.9941` vs 1.0; `0.50125 → 0.50125`; `z = 2.40` not clearing
0.990). Validation: `PREREG_honest.md` already holds the bar (40 fills or 14
days, loss rate strictly below the 4.13% baseline). **Blocks nothing** — a paper
arm places no money. Note before starting it: run the startup path with the flag
applied first, because that is exactly what failed last time.

**2. Put the honest tail in the PRICE test, not the confidence gate.** 7b shows
the gate version forfeits +$530 and zero fills are honestly negative-EV; 7c shows
the money is flat-to-negative above 97c. `expected_value()` currently charges a
flat 0.9% flip regardless of z, which is about **half** the honest 1.66% at the
`pin 0.995` bar. Replacing the flat flip with `honest_tail(z)` makes the ceiling
z-dependent: **97.9c at the pin bar, loosening to ~99.0c at z ≥ 4**. Validation:
live, on fills at ≥97c, against the 97–98c and 98c+ rows in 7c. **What it blocks:**
expensive marginal fills only; it *loosens* at high confidence, and it touches no
hedge path.

**3. Say out loud that raising the fill rate raises this loss class.** 451 of
1,263 entry orders (35.7%) fill nothing, and that coin-flip is what turned −$77
into −$2.47 here. AMENDMENT 18 exists to reduce it. Nothing in the repo prices
that trade-off. Validation: it is already measurable — score AMENDMENT 18's
fill-rate gain against the change in mean loss size per losing market.

**4. Let a hedge retry immediately after a ZERO fill.** `hedge_last_try` blocked
the 11-lot's retry for 656 ms while the ask went 94.9c → 98.0c. Worth only ~4c
here (no depth existed), but it is uncapped on a larger position. This **removes**
a block rather than adding a gate, which is the only kind of hedge change this
project's own history permits. Validation: count zero-filled hedge attempts and
the price move over the following second, across live runs.

**5. Do NOT deploy: insure-at-fill, `late_tau 12`, a tighter index-age gate, a
market-disagreement gate, or a zero-fill brake.** Each is priced above. The first
costs 117–135% of the edge; the second costs +$76 to save $2.47; the third makes
the decision *more* confident; the fourth is arithmetically "refuse the cheapest
NO"; the fifth has n = 4.

---

## 11. VERDICT PER CLAIM

**Section 1 — the price**

| claim | verdict |
|---|---|
| The brief was wrong; the index is NOT missing; 60/60 prints | **SURVIVES** — and strengthened: CF's own `avg_60s_data` states `window_size: 60` and its published average equals my mean exactly |
| 02:30 settle `0.10170363` == published 02:45 strike `0.1017036` | **SURVIVES** |
| Settle `0.10171337`; YES won by +9.77e−06 = 9.8 ppm = 0.96 bp | **SURVIVES** |
| The z/running-mean table at tau 45/20/12/11/10/0 | **SURVIVES** — reproduced to the digit with my own `var_factor` |
| Cushion at tau 12 = 2.61 sd | **SURVIVES** — exact value 2.6193; the autopsy's 2.61 came from a nominal strike and a rounded sigma cancelling |
| The 49 locked prints averaged 1.39e−05 BELOW strike, so spot-vs-strike is not the margin | **SURVIVES** |
| YES needed the last 11 prints to average +6.204e−05 (5.64 sigma); got +1.153e−04, overshot 1.9x | **SURVIVES** (my figures +6.176e−05, 5.61 sigma, 1.87x) |
| One print moved the settle estimate 4.7 sd in one second | **SURVIVES** (4.75) |
| "One print" did it | **WEAKENED** — tau 10 was +9.80e−05 and tau 9 added +4.70e−05; it was a two-second, 106 ms cross-exchange repricing, not one print |
| The jump is a real cross-exchange move, not an index artefact | **SURVIVES** — coinbase and bitstamp independently, to the millisecond |

**Section 2 — the 99.56%**

| claim | verdict |
|---|---|
| The variance collapse is sound and is the edge | **SURVIVES** |
| The bot's sigma was right | **SURVIVES** — exact, 1.08960e−05 both ways; the 0.99x came from treating a `round(sg,6)` log field as exact |
| The Gaussian tail is ~3.3x too thin at z = 2.619 | **SURVIVES** — repo's 1,672-close table says 1.612% vs 0.441% = 3.7x |
| "The 658 exceedances are 208 independent runs ... the well-powered measurement" | **REFUTED as a power claim** — one outcome per close; the real n is 53 closes of one coin, which cannot distinguish 0.44% from 1.4% |
| "Could not measure whether the tail generalises past DOGE" | **REFUTED** — already measured on 1,672 closes, every coin, 2026-09-13 |
| Market implied 6.6% vs model 0.441%; truth between | **SURVIVES** |
| Break-even NO price 98.46c; EV at the ceiling +0.425c | **WEAKENED** — on the repo's table, 98.27c and **+0.248c** |
| "`price_ceiling` is the only thing between the live bot and negative EV" | **WEAKENED** — `expected_value` (flat 0.9% flip) and `ev_implied_ceiling 0.988` also cap; 98.0c is merely tightest |
| Live band contrast 0.8% vs 4.7% (5.6x) | **WEAKENED** — on 3x the sample, 1.60% vs 3.33% (2.1x), and both bands made money |

**Section 3 — the fills**

| claim | verdict |
|---|---|
| 7.1c is price improvement, not a bad fill, worth $10.00 | **SURVIVES** — confirmed against Kalshi's own `no_total_cost_dollars` |
| Not a NO/YES mix-up, not a logging artefact | **SURVIVES** — three independent checks |
| Order 1's 866,790 ms level age is "never saw it appear", not stale | **SURVIVES** |
| 13 NO, 264.90c + 5.92c fee = 270.82c at risk, avg 20.38c | **SURVIVES** — matches Kalshi to the cent |
| The loop was slow in these seconds (`slow_passes_near` 6, worst near pass 1729 ms) | **SURVIVES** |
| "Order 2's zero fill and the flip are the same event" | **REFUTED** — order 2's round trip ended 140 ms before the move began; it was the routine 35.7% zero fill |
| "The model went blind for the last 9 seconds / no index print arrived after tau 10" | **REFUTED** — `pinrun.py:10968` skips hedged positions above `fair()`, so `last_belief` stops being written; every print did arrive |
| Belief identical at tau 12 and 11 because the print had not arrived | **SURVIVES** |

**Section 4 — the hedge**

| claim | verdict |
|---|---|
| Insurance repriced 14x in one second (6.6c → 93.4c, size 1.0) | **SURVIVES** |
| Per-contract recovery at each second (+92.86, +92.96, +6.16, +1.21c) | **SURVIVES** |
| Perfect timing was worth $1.80 | **SURVIVES** ($1.76) |
| Never hedging = −$2.71 | **SURVIVES** (−$2.7085) |
| Hedge recovered 24.13c of 270.82c = 8.9% | **SURVIVES** |
| The 0.40 trigger cost nothing; no belief, jump or price trigger had lead time | **SURVIVES** — and the exchange clocks now prove *why*: the move started 61 ms after we committed |
| "Insure-at-fill hands back about a fifth of the gross edge" | **REFUTED** — it locks −0.98c/contract against +4.5c expected: **117–135% of the edge**, a shutdown not a policy |
| "The 11-lot could never be insured, as a matter of arithmetic ... ~4c of headroom" | **WEAKENED** — arithmetic bound is real (YES ask ≥ 92.9c), but the binding constraint was depth; reachable best ≈ +24.8c, headroom ≈ **+10.5c** |

**Section 5 — luck**

| claim | verdict |
|---|---|
| Full size ≈ −$76, 31x this loss | **SURVIVES** (−$76.76, 31.1x) |
| Luck ≈ $84 of the ~$86.5; hedge $0.24 | **SURVIVES** (my $84.29) |
| `price_ceiling` blocked a 27-lot at 98.1c, ~$26.5 avoided — design | **SURVIVES** (~$26.1) |
| `max_per_market` capped the market at 13 — design | **SURVIVES** |
| "The 82-lot evaporating in 159 ms" was luck tied to the flip | **REFUTED as mechanism** — it was the ordinary 35.7% zero-fill rate, 140 ms early. Still luck, but *routine* luck, which means this event pays −$77 about two times in three. |

**The autopsy's own "could not measure" list**

| item | verdict |
|---|---|
| Whether the index socket dropped at tau 9 | **ANSWERED — it did not.** The freeze is the `hedged` skip; all ten final prints arrived. |
| Whether the 4.7% band rate is real | **still open**, and the point estimate falls to 3.33% [0.92, 8.31] on 3x the sample |
| Whether the tail table generalises past DOGE | **ANSWERED — yes, already measured on 1,672 closes across every coin** |

---

## Housekeeping

Read-only throughout. No process started, stopped or signalled; nothing written
outside this file and my scratchpad. Collectors **alive** —
`kalshi_data/cfbenchmarks_value/20260923T04.jsonl.gz` and
`feed_data/coinbase/20260923T04.jsonl.gz` both being written at 04:02Z against a
wall clock of 04:02:55Z. **Free RAM 0.99 GB** (the brief's stop line; I stopped
reading the tape at that point and finished from cached results). **Free disk
22 GB**, guard 6 GB. Largest object held: 5,190 floats plus 513 dicts — peak
python footprint far under 400 MB.

Tape hours touched, read-only: `cfbenchmarks_value` 20260922T23, 20260923T00,
20260923T02; `feed_data/{coinbase,kraken,bitstamp,gemini,index_replica}`
20260923T02; `kalshi_data/{ticker,trade,orderbook_delta,orderbook_snapshot}`
20260923T02.
