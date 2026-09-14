# PREREG_against -- was there any sign the 05:30 trade would go wrong?

Written 2026-09-14 ~06:15 ET, in answer to the operator's question after the
`KXBTC15M-26SEP140530-30` loss: *"Was there any sign anywhere that purchase
could've gone poor? What was its confidence? Does any data anywhere indicate
anything."*

**Short answer: yes, two signs, and NEITHER has enough data to act on.** This
file exists so that the bar is set now, before more data arrives, rather than
fitted to it later.

---

## 1. WHAT THE BOT ACTUALLY SAW

Everything recorded at the moment of the decision (AMENDMENT 36 logs the book):

| | |
|---|---|
| ticker | `KXBTC15M-26SEP140530-30` |
| side | **NO** -- betting the 60-second average lands BELOW the strike |
| model confidence | **99.992%** (`fair` 8e-05) |
| price paid | 97.2c (ask seen 97.9c) |
| edge at signal | **1.948c** |
| time to close | 13 seconds |
| quote age | 62 ms |
| index age | 0.93 s |
| strike | **77,695.85** |
| spot **at that instant** | **77,708.10** |
| one-second move (sigma) | 4.07 |
| contracts offered at 97.9c | **675** |
| whole ladder | 13,314 |

### The two things that stand out

**(a) The live price was already on the wrong side of the strike.** We bought
NO -- we needed the average to land below 77,695.85 -- while Bitcoin was
trading **$12.25 ABOVE it**. That is **3.0 one-second moves** past the line,
against us. The model's 99.992% came entirely from the 47 seconds already
locked on disk; the live price was pointing the other way the whole time.

**(b) The edge was 1.948c** -- the thinnest band the bot trades, against a
0.3c floor.

And a third worth recording though it is not tested below: **675 contracts
were resting at 97.9c**. Somebody was willing to sell 675 of a thing our model
called 99.992% certain, at a 2c discount, with 13 seconds left.
`RESULTS_select.md` already settled that this counterparty is informed by 26x.

---

## 2. WHAT THE WHOLE LIVE HISTORY SAYS ABOUT THOSE TWO

332 live entry fills matched to their signal, clustered **by close** per hard
rule 4.

### (a) Spot already past the strike against us

Measured as `(spot - strike) / sigma`, signed so **positive = the live price
is on the wrong side for our bet**.

| | fills | contracts | net | c/contract | closes | losing closes |
|---|---|---|---|---|---|---|
| against us by 1+ | 15 | 328 | **-$42.82** | **-13.05c** | **15** | 2 |
| everything else | 317 | 7,511 | +$206.90 | +2.75c | 239 | 7 |

### (b) Edge under 2 cents

| | fills | contracts | net | c/contract | closes | losing closes |
|---|---|---|---|---|---|---|
| edge < 2c | 104 | 2,345 | **-$52.01** | **-2.22c** | 102 | 3 |
| edge >= 2c | 228 | 5,494 | +$216.09 | +3.93c | 182 | 7 |

### (c) THE TWO TOGETHER -- and this is the striking cell

| price against us | edge under 2c | fills | contracts | net | c/contract | closes |
|---|---|---|---|---|---|---|
| **yes** | **yes** | **5** | **134** | **-$56.62** | **-42.25c** | **5** |
| yes | no | 10 | 194 | +$13.80 | +7.11c | 10 |
| no | yes | 99 | 2,211 | +$4.61 | +0.21c | 97 |
| no | no | 218 | 5,300 | +$202.29 | +3.82c | 173 |

**Five fills, across five closes, have lost $56.62 between them** -- more than
a third of every dollar this strategy has ever lost, out of 1.5% of its fills.
The 05:30 BTC trade is one of the five.

---

## 3. WHY THIS IS NOT A GATE, AND MUST NOT BECOME ONE YET

**Neither signal survives its own bootstrap over closes:**

| | closes | mean $/close | 95% | verdict |
|---|---|---|---|---|
| edge < 2c | 102 | -$0.510 | [-1.893, +0.457] | **includes zero -- no power** |
| against by 1+ | 15 | -$2.855 | [-11.798, +3.082] | **includes zero -- no power** |

And the reasons to distrust the 2x2 cell are all present at once:

1. **Five closes.** The repo's own floor is **30** before claiming
   significance. This is a sixth of that.
2. **Many looks.** Five features were tested at roughly five buckets each,
   then crossed. The best cell of ~30 looking extreme is what you would expect
   from noise.
3. **The cell was chosen after seeing the loss that motivated it.** That is the
   definition of fitting to the event.
4. **The single-feature versions both fail.** A finding whose parts have no
   power and whose interaction does is the exact shape of a mirage.
5. **It is partly mechanical.** `fair` already contains spot and strike, so
   "price against us" is not independent information -- it is a claim that the
   model is *overconfident in a particular region*, which is what
   `RESULTS_calib.md` already says (kurtosis 132 against a normal's 3).

---

## 4. THE PRE-REGISTERED BAR

**Nothing branches on either number until all of these hold**, counted only on
fills settling **after 2026-09-14 10:00Z**, so the deciding data is data this
file has never seen:

1. **At least 30 closes** land in the "price against us by 1+ sigma" bucket.
2. On those closes alone, the bucket's mean $/close bootstrap over closes is
   **entirely below zero**.
3. The same holds after dropping the single worst close, so one event cannot
   carry it.
4. The refusal is costed both ways: **how many WINNING closes a gate would
   have refused**, stated next to how many losses it avoids.
   `PROJECT_HISTORY` records that every entry gate previously tested cost
   **22-44 winning trades per loss avoided**; a gate that does not beat that
   ratio is worse than nothing.

**If the bar is met, the cheaper gate is the interaction, not either half** --
refuse only when the price is against us AND the edge is under 2c. That is 1.5%
of fills. Refusing all of "edge < 2c" would drop 30% of contracts on evidence
that has no power.

**Nothing needs to be logged to measure this.** `strike`, `spot`, `sigma` and
`edge_c` are already on every signal record, so the whole question is
answerable retroactively at any time. Re-run with:

    python research/pincap.py            # capacity, unrelated
    # the cross-tab above is in the session scratch; the inputs are the
    # signal records in results/pinrun-live-*.jsonl

---

## 5. WHAT THIS DOES NOT EXPLAIN

The 05:30 trade passed every gate the bot has, and the gates were right to pass
it by their own lights: 99.992% confident, 1.9c of edge over the floor, 97.2c
under the 98c ceiling, a 62 ms fresh quote, a 13,314-contract ladder.

**The model was not wrong about the locked seconds. It was wrong about how far
Bitcoin could move in thirteen.** `RESULTS_calib.md` measured exactly that and
said the error is **shape, not width** -- so no amount of widening sigma fixes
it, and `CURRENT_STATE.md` records that scaling sigma was already tried and
killed. A gate on "the live price is already against us" is the only untried
form that addresses the shape directly, which is why it is worth the 30 closes
rather than being dismissed now.
