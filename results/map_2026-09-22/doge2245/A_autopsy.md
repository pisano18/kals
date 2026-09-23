# A_autopsy — KXDOGE15M-26SEP222245-45

Close `2026-09-23T02:45:00Z` = **10:45 PM ET 09-22**. Kalshi ledger: **-$2.4673**
on the market. The day around it: +$52.89 before this settle, +$50.42 after.

**DATA CORRECTION, IN THE FIRST SENTENCE (the task brief was wrong about this).**
The brief said the Kalshi tape was deaf 00:11Z–02:5xZ and the 1/sec settlement
index was missing for this close, so a reconstruction from exchange feeds would
be needed. **It is not missing.** `kalshi_data/cfbenchmarks_value/20260923T02.jsonl.gz`
resumes at `1790130161` = **02:22:41Z** and holds **60 of 60** `DOGEUSD_RTI`
prints for the settlement window. It calibrates exactly:

| check | value |
|---|---|
| 02:30 close settle from the tape | `0.10170363` |
| the 02:45 strike Kalshi published | `0.1017036` |

`strike(N+1) == settle(N)` to seven decimals, so the window definition and the
data source are both confirmed. **Everything below rests on the real index, not
on a reconstruction.** The `index_replica` rebuild was done first and is kept
only as an independent cross-check; where it is used it is labelled.

Reconciliation of the money, by hand, against Kalshi's own settlement row
(`results/kalshi_ledger.json`, key `KXDOGE15M-26SEP222245-45|2026-09-23T02:45:08.250107Z`):

```
 2 NO  @ 93.4c  = 186.80c + fee 0.86c   -> log says -187.67c
11 NO  @  7.1c  =  78.10c + fee 5.06c   -> log says  -83.18c
 2 YES @ 94.75c = 189.50c + fee 0.70c   -> log says   +9.80c
11 YES @ 98.6c  =1084.60c + fee 1.07c   -> log says  +14.33c
                                   sum  =          -246.72c
Kalshi: 13 NO $2.649 + 13 YES $12.74113 + fee $0.07717, payout $13.00 = -$2.4673
```

---

## 1. What the DOGE price did

**Answer: the index sat 1.1e-05 BELOW the strike with 11 seconds left, then made
one +9.8e-05 print — 8.9 times its own one-second standard deviation — and held
the new level for the last 10 seconds. It settled 9.8 millionths of a dollar
above the strike.**

Settle (real index, 60/60 prints) = `0.10171337`. Strike = `0.1017036`.
**Settle − strike = +9.767e-06 — 9.8 parts per million of a dollar, 0.96 basis
points of price.** That is how much we lost by.

The running settlement average, computed the model's own way
(`(locked + r·spot)/60`, `r = tau − 1`, `sd = sigma·sqrt(var_factor(r,[1.0]))`,
sigma = the 1.1e-05 the bot logged):

| tau | locked prints | their mean vs strike | spot vs strike | running mean vs strike | r | sd of remaining | z | P(NO) |
|---|---|---|---|---|---|---|---|---|
| 45 | 16 | −6.98e-06 | −1.86e-05 | **−1.550e-05** | 44 | 3.14e-05 | −0.49 | 0.689 |
| 20 | 41 | −1.62e-05 | +9.40e-06 | **−8.083e-06** | 19 | 9.11e-06 | −0.89 | 0.813 |
| 12 | 49 | −1.39e-05 | +3.40e-06 | **−1.075e-05** | 11 | 4.12e-06 | **−2.61** | **0.9954** |
| 11 | 50 | −1.36e-05 | +3.40e-06 | **−1.075e-05** | 10 | 3.60e-06 | −2.99 | 0.9986 |
| 10 | 51 | −1.13e-05 | **+1.014e-04** | **+5.583e-06** | 9 | 3.10e-06 | +1.80 | **0.036** |
| 0 | 60 | +9.77e-06 | +1.124e-04 | **+9.767e-06** | 0 | — | — | 0 |

These reproduce the bot's own log: it recorded `spot 0.101707` at tau 12 (index
print `0.1017070`) and `fair 0.00441` → z = −2.619; the table's −2.61 differs only
by sigma rounding. The tau-10 flip: the bot's belief went 0.99867 → **0.05143**,
and the table says why — the running mean crossed from −1.075e-05 to +5.583e-06.

**What moved it.** One print. Second `1790131489` → `1790131490`:
`0.1017070` → `0.1018050`, **+9.80e-05 = 8.9 one-second sigma**, and it stayed
up: the last 11 prints averaged **+1.153e-04** above the strike (10.5 sigma).
Cross-checked on the constituent feeds (`index_replica`, coinbase+bitstamp+kraken
mid): the same second shows coinbase DOGE jump to 0.10179/0.10184 and bitstamp
follow to 0.101842 — a real cross-exchange move of about +0.11%, not an index
artefact.

**How many standard deviations of the REMAINING window was the tau-12 margin?**
The brief's framing (spot 3.4e-06 above the strike) is not the margin the model
used. The model's margin is the **running average**, and the 49 already-locked
prints averaged **1.39e-05 BELOW** the strike, which dragged the running mean to
1.075e-05 below it even with spot above.

- **Cushion at tau 12 = 2.61 standard deviations of the remaining window**
  (1.075e-05 / 4.124e-06). That is the entire margin the 99.56% was built on.
- Stated as a price move: for YES to win, the remaining 11 prints had to average
  **+6.204e-05 above the strike = 5.64 one-second sigma = 6.1 basis points**, and
  hold it. They averaged +1.153e-04 — **it overshot the requirement 1.9x**.

**Why one print could do it.** At tau 10 the sd of the whole remaining window was
3.095e-06, while a single print carries 9/60 of the settle estimate. So one
+9.80e-05 print moved the settle estimate +1.470e-05 = **4.7 sd in one second**.
The variance collapse that makes the strategy work also makes a single jumpy
print able to cross the whole cushion.

---

## 2. Why the bot thought it was 99.56% safe at tau 12 after a coin flip at tau 45

**Answer: the variance collapse is working exactly as designed and is not the
problem. The problem is the Gaussian tail bolted onto it. Measured on the real
index over 13.4 hours, the thing the model called 0.441% happens 1.435% of the
time — 3.3x too thin. The bot's sigma, by contrast, was right to 1%.**

The mechanism first, since it is sound. At tau 45 only 16 of the 60 prints were
locked and 44 were still to come, so the sd of the remaining window was 3.14e-05
— **wider than the 1.55e-05 the running mean sat below the strike.** For YES the
remaining 44 prints only had to average +2.5e-06 above the strike (0.23 sigma),
which is nothing. Hence 68.9% (the bot logged 67.1%), refused by gate
`confidence` against `pin 0.995`. By tau 12, 49 prints were locked, the sd of the
remaining window had collapsed 7.6x to 4.12e-06, and the same 1.08e-05 gap was
now 2.61 sd. Nothing moved; the ruler shrank. That is the whole edge and it is
real.

**But 2.61 sd is a thin cushion to call 99.56%, and the Gaussian says so far too
confidently.** Measured on the real `DOGEUSD_RTI` feed — 48,284 prints over
13.4 hours (09-22 11:00Z–23:00Z plus 02:22–02:59Z), 45,862 one-second samples —
standardising the realised settle deviation by the model's own local ruler
(trailing 300 s sigma, exactly the bot's `sigma_win`, times
`sqrt(var_factor(11,[1.0]))`):

| z | model tail Phi(−z) | MEASURED tail | ratio | exceedances |
|---|---|---|---|---|
| 1.000 | 15.866% | 13.355% | 0.8x | 6125 |
| 1.500 | 6.681% | 6.249% | 0.9x | 2866 |
| 2.000 | 2.275% | 3.125% | 1.4x | 1433 |
| 2.330 | 0.990% | 2.008% | 2.0x | 921 |
| **2.619** | **0.441%** | **1.435%** | **3.3x** | 658 |
| 2.990 | 0.139% | 1.005% | 7.2x | 461 |
| 3.500 | 0.023% | 0.687% | 29.5x | 315 |
| 4.000 | 0.003% | 0.484% | 153x | 222 |
| 5.000 | 0.00003% | 0.275% | 9584x | 126 |

`z = 2.619` **is this trade**. `z = 2.990` is the tau-11 second, where the model
said 99.86%.

- The body is fine (0.8–0.9x at z = 1–1.5). The distribution is not wider, it is
  **fat-tailed**: sd of the standardised deviation is 1.143, only 14% too small,
  yet the 2.6-sigma tail is 3.3x and the 4-sigma tail 153x.
- **The 658 exceedances are 208 independent runs, in 171 distinct minutes,
  touching 53 of the 56 15-minute closes in the window.** So n as episodes is
  ~208, not 658 — comfortably over the 30 floor, and the event is not one freak
  afternoon.
- **The bot's sigma was not the error.** Real-index 1-second sd over the 300 s
  before tau 12 = 1.0860e-05 against the 1.1000e-05 the bot logged — **0.99x**.
  The volatility estimate was essentially perfect. (Largest single 1-second move
  in the 13.4 h: 8.18e-04 = 74x sigma. Jumps of the size that beat us are
  ordinary for DOGE.)
- The `index_replica` cross-check, over a different 8.9 hours, gave the same
  shape and a slightly fatter 2.619 tail (2.01%); the replica's own quote noise
  makes it the looser of the two, so 1.435% is the number to use.

**What the market thought.** We bought NO at 93.4c and at 7.1c, i.e. we sold YES
at 6.6c and 92.9c. The 6.6c YES bid we crossed implies **P(YES) = 6.6%** against
the model's 0.441% — **15x**. The measured tail (1.435%) sits between the two,
so the trade was still positive-expectation, just much thinner than the bot
believed.

**The price ceiling is where this bites.** EV per contract at z = 2.619:

| NO price | EV on the model (0.441%) | EV on the measured tail (1.435%) |
|---|---|---|
| 93.4c | +5.719c | +4.725c |
| 97.0c | +2.349c | +1.355c |
| 97.5c | +1.879c | +0.885c |
| **98.0c** (the ceiling) | **+1.419c** | **+0.425c** |
| 98.5c | +0.949c | −0.045c |
| 99.0c | +0.489c | −0.505c |

Break-even at this confidence is **98.46c**. The ceiling is 98.0c, so it is not
broken — but at the ceiling the real edge is **0.425c, not 1.419c: the model
overstates the marginal trade's edge by 3.3x.** And the same second, a 27-lot at
98.1c was refused by `price_ceiling` — that refusal, which exists for unrelated
reasons, is the only thing standing between the live bot and negative EV here.

**Live-fill corroboration (our own fills, never the tape).** 128 live run files,
172 entry fills with a matched signal `fair`, grouped by the model's loss chance
at entry:

| band | markets | distinct closes | lost | loss rate | 95% CI |
|---|---|---|---|---|---|
| model loss chance < 0.4% | 118 | 90 | 1 | 0.8% | [0.0%, 4.6%] |
| **model loss chance 0.4–0.5%** (this trade: 0.441%) | **43** | **39** | **2** | **4.7%** | [0.6%, 15.8%] |

The marginal band — exactly what `pin 0.995` admits — loses 5.6x as often as the
safe band, on a scale where the model says the difference should be 0.45% vs
~0.2%. **The intervals overlap, so this on its own is not significant** and I am
not claiming it is; it points the same way as the tail table, which is the
well-powered measurement. The band's two losses are this market (−$2.47) and
`KXNEAR15M-26SEP211245-45` (−$59.09, the largest single-market loss on record);
the one loss above 99.6% was `KXHYPE15M-26SEP211815-15` (−$31.27).

**So: working as designed, and overconfident.** The collapse is real and the
sigma is right. The 99.56% is wrong by 3.3x because it is a Gaussian tail on a
jumpy index, and the trade passed `pin 0.995` by **0.059 percentage points**
(99.559% against a 99.500% bar).

---

## 3. The fills

Three entry orders, all `immediate_or_cancel`, all sent as "sell YES at 2c"
(`price 0.0200`, `side ask`) with `limit_sent 0.98` — i.e. buy NO at up to 98.0c.

| # | t | tau | ask seen | count asked | filled | exec (NO) | exec (YES) | level age | latency | status |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 02:44:48Z | 12 | 98.0c | 2.00 | **2.0** | **93.4c** | 6.6c | 866,790 ms, **not exact** | 159.1 ms | executed |
| 2 | 02:44:48Z | 12 | 93.4c | **82.00** | **0.0** | — | — | 129 ms, exact | 159.2 ms | **canceled** |
| 3 | 02:44:49Z | 11 | 98.0c | 11.00 | **11.0** | **7.1c** | 92.9c | **38 ms**, exact | 175.2 ms | executed |

Then `refused`, gate `max_per_market`, `fills: 2` — the market was closed to
further entries.

**How a 98.0c ask became a 7.1c fill: it is price improvement, not a bad fill,
and it is the single biggest reason this loss was cheap.** The order is an IOC
*ask* (sell YES) with a 2c limit. An aggressive IOC executes against the best
resting bid, whatever it is. The bot's book said the best YES bid was 2c (NO ask
98.0c, the level 38 ms old). In the 175 ms between send and fill the book
flipped: the best YES bid was **92.9c**. So we sold YES at 92.9c and bought NO at
**7.1c instead of 98.0c — 90.9c per contract better.**

**On 11 contracts that saved 11 × 90.9c = $10.00.** If that order had filled at
the ask it saw, the leg would have cost −$10.83 instead of −$0.83 and the market
would have been **−$12.47, not −$2.47**.

Note what this proves about the timing: the YES side was already bidding 92.9c at
02:44:49Z. Order 2 asked for 82 and got nothing for the same reason — the 62.4
offer at 93.4c (the level whose age was 129 ms) was gone inside 159 ms. Both
facts are the same event: **the NO offer side was pulled and the YES bid side
jumped, inside one second, and our orders crossed it mid-flip.**

Two of the three orders sat on levels the repo has already flagged as the loss
population: `RESULTS_select.md` found every model failure on levels under 0.25 s
old and none on levels resting 30 s+. Order 2's level was **129 ms** old and
order 3's was **38 ms** old. (Order 1's `level_age_ms 866790` with
`level_age_exact: false` is not a stale quote — it is a lower bound measured from
the ticker's orderbook snapshot, and 866.79 s before 02:44:48.8Z is 02:30:22Z,
exactly when the `watch` record added DOGE. It means "we never saw this level
appear", not "this level is 14 minutes old".)

**What we held going into the last 10 seconds:** 13 NO contracts.

| | contracts | price | cost | fee | at risk |
|---|---|---|---|---|---|
| order 1 | 2 | 93.4c | 186.80c | 0.86c | 187.67c |
| order 3 | 11 | 7.1c | 78.10c | 5.06c | 83.18c |
| **total** | **13** | **avg 20.38c** | **264.90c** | **5.92c** | **270.82c** |

Average cost 20.38c per contract (20.83c with fees). Maximum loss 270.82c.
Payout had NO won: $13.00.

Also relevant: the loop was **slow** in exactly these seconds —
`loop` records show 288, 232, 270, 423 and 256 ms per pass with `near: true` and
`n_slow` climbing to 6, against the ~50 ms of a healthy 20 Hz loop. The tau-0
pass took 1729 ms because a `universe` refresh ran (1678 ms).

**And the model went blind for the last 9 seconds.** `last_belief` is recomputed
from `fair()` on every loop pass, yet the `hedge_quote` records show it
byte-identical at `0.0514329175139725` for tau 9, 8, 7, 6, 5, 4, 3, 2 and 1.
`fair()` cannot return the same value nine times while `r` shrinks, unless
`partial()` returned the same `(locked, r)` — i.e. **no new index print arrived
after tau 10.** (Same signature at tau 12/11: belief identical at
`0.9955949944046358` while `index_age_s` went 0.52 → 0.80 → 1.04.) It changed
nothing here, because we were already hedged, but for those 9 seconds the bot
was holding a position on a frozen model.

---

## 4. The hedge, priced from the `hedge_quote` records

**Answer: insurance cost 6.6c at tau 11 and 93.4c one second later. It was
never cheap while the 11-lot was held, and the 0.40 trigger cost nothing —
no belief threshold could have fired earlier, because the belief itself only
moved when the price did. The hedge recovered 24.13c of a 270.82c exposure:
8.9%.**

A YES hedge bought at ask `q` recovers `100 − q − fee` per contract when the
market settles YES (fee = `ceil(0.07·q·(1−q)·10000)/10000`):

| tau | YES ask | size offered | net recovery/contract | held then | best recovery on what we held |
|---|---|---|---|---|---|
| 12 | **6.7c** | **86.80** | **+92.86c** | 2 | **+185.72c** |
| 11 | **6.6c** | **29.00** | **+92.96c** | 2 | **+185.92c** |
| 10 | 93.4c | **1.00** | +6.16c | 13 | +6.16c (size 1) |
| 9 | 98.7c | 74.41 | +1.21c | 13 | +15.73c |
| 8 | 99.0c | 450.71 | +0.93c | 13 | +12.09c |
| 7 | 99.0c | 374.71 | +0.93c | 13 | +12.09c |
| 6 | 99.8c | 301.00 | +0.18c | 13 | +2.34c |
| 5 | 99.8c | 197.00 | +0.18c | 13 | +2.34c |
| 4 | 99.8c | 197.83 | +0.18c | 13 | +2.34c |
| 3 | 99.8c | 299.00 | +0.18c | 13 | +2.34c |
| 2 | 99.2c | 200.00 | +0.74c | 13 | +9.62c |
| 1 | 99.7c | 17.00 | +0.27c | 13 | +3.51c |

**The insurance repriced 14x in one second: 6.6c at tau 11, 93.4c at tau 10, and
the size at 93.4c was 1.0 contract.** That is the whole story of why the hedge
recovered nothing.

Best case by the second the trigger fires (the 2-lot and the 11-lot must be
treated separately, because the 11-lot did not exist until tau 11):

| trigger second | 2-lot leg | 11-lot leg | market total |
|---|---|---|---|
| tau 12 (2 held; 86.8 offered at 6.7c) | −187.67 + 185.72 = **−1.95c** | −83.18 + 18.3 = −64.9c | **≈ −$0.67** |
| tau 11, before our own fill (29.0 at 6.6c) | −187.67 + 185.92 = **−1.75c** | −83.18 + 18.3 = −64.9c | **≈ −$0.67** |
| **tau 10 — WHAT HAPPENED** | −187.67 + 9.80 = −177.87c | −83.18 + 14.33 = −68.85c | **−$2.47** |
| tau 9 | −187.67 + 2.42 = −185.25c | −83.18 + 13.31 = −69.87c | ≈ −$2.55 |
| never | −187.67c | −83.18c | −$2.71 |

So **perfect hedging was worth $1.80 of this $2.47**, and every cent of it is on
the 2-lot. Note the bot beat its own tau-10 quote: the `hedge` record shows it
swept (`ask 0.936, ask_size 2.0, limit_sent 0.966, swept: true`) and got both
contracts at 94.75c where the top-of-book quote was 93.4c for size 1 — +9.80c
rather than the +6.16c the table allows.

**What the 0.40 trigger cost: nothing.** `hedge_belief` is 0.25 and
`HEDGE_PANIC` 0.40; both fired in the same instant. Belief was **0.99867** on one
loop pass of tau 10 and **0.05143** on the next pass of the same second. Any
threshold between 0.05 and 0.9956 fires at exactly that instant. A threshold of
0.99, 0.95, 0.60, 0.40 or 0.25 — all identical here. **The threshold was never
the binding constraint; the belief signal itself had no lead time.**

**Could ANY trigger have done materially better?** Only on the 2-lot, and only by
not being a trigger:

- **Belief-based: no.** Belief was 0.9956 at tau 11. The only belief line that
  fires at tau 12 is one above 0.9956 — i.e. above the `pin 0.995` entry bar,
  which means "insure every position the instant it fills".
- **Jump-based: no.** `hedge_jump` was null in this run, but both `hedge_alarm`
  records logged `jump_sd: null` and the jump did not exist before the print that
  moved the belief. The jump and the belief move are the same event.
- **Market-price-based: no.** The YES ask was 6.7c at tau 12 and went *down* to
  6.6c at tau 11. The market gave no warning either. The flip happened inside the
  same ~175 ms as our own tau-11 fill.
- **Unconditional insure-at-fill: yes, for the 2-lot only.** It captures 6.7c
  insurance on 93.4c of risk. The cost of that policy is 93.4 + 6.7 = 100.1c plus
  ~0.88c of fees for a guaranteed 100c payout — **a locked ~1.0c per contract
  against the ~5.3c per contract the unhedged trade expects**, i.e. it hands back
  about a fifth of the gross edge on every trade to cover this one. Numbers only;
  no recommendation here.
- **The 11-lot could never be insured cheaply, as a matter of arithmetic.** We
  bought it at 7.1c, which means the YES bid was already 92.9c. "NO cost 7.1c"
  and "YES insurance costs 93c" are the same fact. Its maximum loss was 83.18c
  and the best achievable recovery was ~+18c (1 contract at 93.4c plus 10 at
  98.7c) against the +14.33c actually got — **about 4c of headroom.**

---

## 5. Cheap by luck or by design?

**Answer: overwhelmingly by luck. We held 13 of the 82 the bot asked for, and 82
of that 83% vanished in 159 ms. The same event at the size actually ordered would
have cost about −$76 — 31x this loss.**

Why we held 13 when `size_now` was 82 and `max_per_market` allowed 2 fills of up
to 82 each (164 contracts, ~$160 at the ceiling):

1. **Order 1 asked for 2, not 82** — `take_n 2.0`, because the bot's book showed
   only 2.0 offered at 98.0c and nothing under it (`ladder_under: 0`, ladder
   starting at 98.5c). Thin top-of-book, not a gate. → 2 contracts.
2. **`price_ceiling` blocked a 27-lot at 98.1c in the same second** (`refused`,
   `price 0.981, size 27.0, ceiling 0.98`). Had the ceiling been 98.5c we would
   have added 27 at 98.1c → about **$26.5 more loss**. This is design, and it
   helped.
3. **Order 2 asked for 82 and filled ZERO.** The fresh book showed 62.4 at 93.4c
   with 6,195.4 total under the ceiling; `taper` capped the ask at `size_now`
   (82) with `sweep_headroom_c 4.6`; 159 ms later the whole NO offer side was
   gone. **This is pure luck and it is 83% of the intended exposure.**
4. **Order 3 asked for 11** (the refreshed book's 98.0c level held 11,
   `ladder_under: 11.0`) and got 11 — at 7.1c, another piece of luck worth $10.
5. **`max_per_market` (2 fills) then refused everything else** — `refused`,
   `gate: max_per_market, fills: 2`. Design, and it capped the market at 13.

**Full-size counterfactual — the order that was actually sent:**

```
82 NO @ 93.4c        = $76.59 + fee $0.3539          = -$76.94 unhedged
hedge 60@98.6c + 22@99.0c = $80.94 + fee $0.0681, pays $82.00 = +$0.99
                                              net  = -$75.95
```

(The hedge prices come from the `hedge_quote` records: 74.41 offered at 98.7c at
tau 9 and 450.71 at 99.0c at tau 8 — 82 contracts were coverable, at ~1c of
recovery each.) **−$75.95 against the −$2.47 actually booked: 31x.** If the
second fill had also gone (164 contracts) it is roughly −$152, and with a 98.5c
ceiling add ~$26. The task's $70–80 estimate is right.

**What was design and did help:** `price_ceiling 0.98` (blocked 27 contracts),
`max_per_market 2` (blocked every fill after the second), and the IOC-at-limit
order style, which is what turned a mid-flip book into a 90.9c price improvement
rather than a fill at the ask.

**What was luck:** the 82-lot evaporating in 159 ms (~$74 not lost) and the
11-lot's 90.9c price improvement (~$10 not lost). **Together, luck accounts for
about $84 of the $86.5 that this event could have cost.** The hedge accounts for
$0.24 of it.

---

## Could not measure

- **Whether the bot's index websocket actually disconnected at tau 9.** The
  frozen belief is strong evidence that no new print reached `fair()`, but
  `pinrun` logs no index-disconnect record and `_hquiet` produced nothing in this
  run, so the cause (Kalshi's degraded websocket vs. something local) is not
  established from the log. The collector's own feed was back from 02:22:41Z, so
  the exchange was publishing.
- **Whether the 4.7% loss rate in the 0.4–0.5% confidence band is real.** 2 of 43
  markets over 39 closes, 95% CI [0.6%, 15.8%], overlapping the safe band's
  [0.0%, 4.6%]. Needs more closes, and the entry-fill population only matched a
  `signal` fair on 172 of 811 order records.
- **Whether the measured tail generalises past DOGE.** The 13.4-hour table is
  DOGE only. Every other coin is a separate measurement.

## Housekeeping

Read-only throughout; no process touched, no file written outside this one and
the scratchpad. `kalshi_collector.py` and `crypto_feeds.py` both **alive** —
`kalshi_data/cfbenchmarks_value/20260923T03.jsonl.gz` and
`feed_data/coinbase/20260923T03.jsonl.gz` were both being written at 03:33:3xZ
against a wall clock of 03:33:36Z. Free RAM 1.48 GB, free disk **24.08 GB**
(guard is 6 GB). Peak python footprint this job: well under 400 MB (the largest
object held was 48,284 floats).
