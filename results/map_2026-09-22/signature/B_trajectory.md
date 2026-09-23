# B_trajectory -- the fair trajectory and the cushion (TRAIN half only)

Label `hunt-trajectory`. Written 2026-09-22 (ET evening), read-only throughout.

**The question:** does a late swing in the model's own confidence (coin flip at
45 s -> confident at entry), a thin cushion measured in sd of the remaining
window, or an earlier confidence refusal in the same close separate losers
from winners? Interaction with tau and leg type included.

**The answer in one line: yes, the trajectory separates -- in the OPPOSITE
direction to tonight's DOGE lead.** A market the model *doubted* earlier in
the same close is the single best-paying bucket in the whole table (0 losses
in 68 markets, $2.95 a market against $0.68 overall, and it replicates out of
sample). The DOGE cushion signature is not a warning at all: gating on it
would have *cost* money in both halves.

## Scope, sources, discipline

- TRAIN = closes up to 2026-09-20 23:59:59 ET: **718 fills, 697 markets, 509
  closes, 17 losses (2.44%), +$482.88.** Holdout (09-21 on) = 93 fills, 82
  markets, 64 closes, 3 losses, +$50.73. Reproduces the table's own split
  exactly.
- Money is **Kalshi's ledger** (`results/kalshi_ledger.json` via
  `research/pinledger.py`), one row per market, net of any hedge. A market with
  two fills carries one ledger row, so every dollar figure here is deduped by
  ticker. No loss rate or dollar figure in this file comes from the tape or the
  replay.
- n is **markets and closes**, never trades or fills. Every bucket prints both.
- **82 cuts were tried.** The multiple-looks bar is therefore
  **0.05 / 82 = 0.00061**. It is printed against every claim. Five additional
  looks at the holdout were confirmations of rules already fixed on TRAIN, not
  searches, and are labelled as such.

### A correction to the shared table's trajectory columns -- read this first

`conf_t45 … conf_t15` in `table/fills.jsonl` read `p["fair"][g+d]` for
`d in (0, 1, -1, 2, -2)`, so **they can return the entry's own signal
record**: a tau-45 fill's `conf_t45` is itself, and a tau-43 fill's `conf_t45`
can come from the tau-43 record. They are not usable as warnings as they
stand. Worse, even when strictly earlier, the "earlier" reading is often
1-3 seconds before the fill (a ladder leg or a partial), which carries no
trajectory information at all.

So the trajectory was rebuilt from the logs (`refused` + `signal` records with
both `fair` and `tau`; 15,213 records over 7,920 markets) with two rules:

1. **strictly earlier** -- recorded at a tau *greater* than the entry tau;
2. **a real gap** -- at least 5 s (also tested at 10 s and 15 s).

Coverage in TRAIN, at gap >= 5 s: **230 of 697 markets**. The other 467 have no
earlier evaluation of that market logged at all, because the bot enters at the
first second it is allowed to. The feature is *unknown*, not false, for two
thirds of the book, and any rule built on it must say what it does when the
feature is unknown.

Builders: `scratchpad/signature/hunt-trajectory/{traj.py, aug.py, aug2.py,
search.py, lib.py}`.

---

## Finding 1 (the money). The model doubting our own side earlier in the close is the best-paying signal in the table -- the exact reverse of the DOGE lead

**Claim.** When the bot's own fair value put our side **below 50%** at some
logged second at least 5 s before the entry, and it then became confident
enough to buy, that market paid **$3.16 a market with zero losses** against a
book-wide $0.69. The ordering is monotone in the model's earlier doubt, and it
survives out of sample.

TRAIN, market level, ledger dollars:

| earlier reading, >= 5 s before entry | markets | closes | losses | $ total | $/market | $/contract |
|---|---|---|---|---|---|---|
| our side was **< 50%** (doubted) | 50 | 46 | **0** | **+157.76** | **+3.16** | +4.63c |
| our side was 50-97% | 144 | 123 | 4 (2.8%) | +123.61 | +0.86 | +1.28c |
| no earlier reading logged | 469 | 368 | 10 (2.1%) | +268.58 | +0.57 | +1.58c |
| our side was already **>= 97%** | 34 | 34 | 3 (8.8%) | **-67.06** | **-1.97** | -3.48c |
| TRAIN, everything | 697 | 509 | 17 (2.44%) | +482.88 | +0.69 | +1.51c |

The four buckets are exhaustive and their dollars sum to +$482.89 against the
ledger's +$482.88 (1c of rounding).

**Evidence that this is not the size drift or the calendar.** Money per market
rose all week with autosize, and the doubt bucket does not exist before
2026-09-14 (the bot only began logging enough earlier evaluations then). So the
test used is a **permutation within each calendar day**: the bucket labels are
reshuffled among that day's markets, 20,000 draws, day composition held fixed.

- TRAIN, doubt bucket: **$+3.16 a market, p = 0.0001** -- passes the 0.05/82 =
  0.00061 bar.
- For comparison, `tau <= 15` alone: $+1.94 a market, p = 0.0017 (does **not**
  pass).
- All data (TRAIN + holdout): $+2.95 a market, p < 0.0001.

**It is not just late entry.** Inside `tau <= 15` the doubt bucket still adds:
32 markets / 30 closes at **$3.09** a market and 0 losses, against 117 markets
at $1.63 a market and 2 losses. Median contracts are 72 in the doubt bucket
and 74 in the 50-97% bucket that earns $0.86, so it is not position size
either. Zero of the 68 markets were hedged, so no hedge arithmetic is involved.

**Holdout, one confirmatory look, rule fixed on TRAIN:** 18 markets, 18
closes, **0 losses, +$42.82** -- 22% of the holdout's markets carrying 84% of
its +$50.73, and none of its 3 losses.

**Mechanism, and it is the `pin` edge itself.** Settlement is the mean of 60
one-second prints and `Var(settle - strike) = 880 sigma^2`, so the truth
collapses far faster than `sqrt(tau)`. A market the model doubted at 45 s and
is sure of at 20 s is one where **the locked prints did the work**: the
settlement average has walked away from the strike and there is physically
less window left to walk back. The market has not re-priced that arithmetic,
which is why we still pay ~96.6c. A market the model was already sure of at
45 s is sure because the *distance* is large and obvious; the price is
therefore right, there is nothing to win (+1.3c a contract), and the residual
losses there are genuine surprises (-3.5c a contract).

**What would make it an artefact, and whether it was checked.**

- *Size/calendar drift.* Checked -- within-day permutation, and median
  contracts matched against a bucket earning a quarter as much.
- *It is really just `tau <= 15`.* Checked -- it adds inside `tau <= 15`, and
  `tau <= 15` alone fails the bar.
- *One coin or one day.* Checked -- 9 coins (ZEC 13, BTC 10, SOL 8, XRP 7,
  DOGE 7, BNB 6, NEAR 6, HYPE 6, ETH 5), 9 separate days, 64 closes with no
  close counted twice.
- *A hedge effect.* Checked -- 0 of 68 markets were hedged.
- **Not checked, and it is the real limit:** zero losses in 68 markets is
  *not* a demonstrated zero. Base rate predicts 1.75 losses; P(0) = 0.17. The
  claim that passes the bar is the **money per market**, not "it never loses".

**Confidence: moderate-to-good on the money, weak on the loss rate.** The
feature is only available on a third of fills and only from 09-14 on.

---

## Finding 2 (a change NOT to make, worth more than most changes to make). The DOGE cushion signature does not warn -- gating it would have cost money in both halves

Tonight's DOGE row is real and the arithmetic in the lead is right: at tau 12
the spot was **0.82 sd of the remaining window on the WRONG side of the
strike** (`cushion_sd -0.82`) and the model still read 99.56%, because the
locked prints supplied 1.31x the whole z-score (`frac_locked 1.31`). It is a
vivid, correct diagnosis of that one loss. **It does not generalise.**

TRAIN, every cushion cut tried:

| cut (all computable before entry) | markets | closes | losses | rate | $ total | Poisson p |
|---|---|---|---|---|---|---|
| `cushion_sd < 0` (spot on the wrong side) | 35 | 35 | 2 | 5.7% | **+30.59** | 0.21 |
| `cushion_sd < 0.5` | 40 | 39 | 2 | 5.0% | +41.61 | 0.26 |
| `cushion_sd < 1.0` | 51 | 50 | 3 | 5.9% | +16.80 | 0.13 |
| `cushion_sd < 2.0` | 91 | 88 | 4 | 4.4% | -42.87 | 0.18 |
| `frac_locked > 1.0` (the DOGE signature) | 32 | 32 | 2 | 6.2% | +10.81 | 0.17 |
| `frac_locked > 0.75` | 41 | 40 | 2 | 4.9% | +26.68 | 0.25 |
| `frac_locked > 0.5` | 58 | 57 | 3 | 5.2% | -35.97 | 0.15 |
| `locked_sd > 2.0` | 44 | 43 | 2 | 4.5% | +31.23 | 0.29 |
| `cushion_sd < 0` AND `conf >= 0.99` | 29 | 29 | 2 | 6.9% | +23.58 | 0.16 |
| `cushion_sd < 0` AND refused for confidence earlier (the full DOGE rule) | 18 | 18 | 1 | 5.6% | +13.34 | 0.36 |
| `frac_locked > 1` AND `tau <= 15` | 25 | 25 | 1 | 4.0% | +15.13 | 0.46 |

Every version roughly doubles the loss *rate* and every version **made
money**. Nothing is within two orders of magnitude of the 0.00061 bar.

**In the 17 TRAIN losses the signature is almost absent.** Only 2 of 17 had a
negative cushion (BTC 09-14 05:30 at -7.08, SOL 09-11 08:30 at -0.84). The
median loser's cushion is **+3.23 sd** and the median winner's is +3.55 -- no
separation. Median `frac_locked` is -0.03 for losers and -0.16 for winners.

**Holdout, one confirmatory look:** `cushion_sd < 0` is 3 markets, 1 loss
(that loss *is* tonight's DOGE, -$2.47), **+$5.29 net**. Same for
`frac_locked > 1` -- the same 3 markets. A gate on either would have blocked
DOGE and still ended the holdout $5.29 poorer.

**The one dollar-negative cushion cut is a price confound.**
`cushion_sd < 2.0` is -$42.87 over 91 markets, which looks like a case. But
**5 of those 91 markets are the known sub-90c population and carry -$35.73 of
the -$42.87.** Split by price, the cushion stops separating: at 90-97c it is
-$14.64 over 38 markets, at >= 97c it is +$7.50 over 48. The sub-90c
population is Finding A's, not the cushion's -- 39 TRAIN markets priced under
90c hold 7 of the 17 losses (17.9%) whichever side of the cushion cut they sit.

**Confidence: high, because it is a null with money on both sides of it.**
A cushion or locked-prints gate is a change that would have lost $30.59 on
TRAIN and $5.29 on the holdout while blocking one $2.47 loss.

---

## Finding 3 (underpowered, do not deploy). Entering late into a market the model was ALREADY sure of points the right way but fails confirmation

The mirror of Finding 1, stated as a gate: **refuse when the model was already
>= 97% on our side at least 5 s earlier in the same close and we are now
entering at tau <= 30.**

- TRAIN: **18 markets, 18 closes, 3 losses (16.7%)** against the 2.44% base,
  which predicts 0.44. Poisson **p = 0.026** -- fails the 0.00061 bar by a
  factor of 43.
- Dollars: would have **saved $88.98** of losses and **blocked $21.97** of
  winners, net **+$67.01** on a TRAIN that made +$482.88.
- It survives dropping 09-19 completely: the 3 losses are 09-08, 09-10 and
  09-14. That is one of the few cuts in this file that does not depend on the
  bug day.
- **Holdout: 5 markets, 0 losses, +$14.06. It does NOT confirm.**
- Not a price confound: restricted to price >= 90c it is 15 markets, 1 loss,
  -$20.33 (p = 0.19) -- weaker, and the losses move to the sub-90c side.

**The wider 36-market version** (drop the tau <= 30 leg) is 36 markets, 35
closes, 4 losses (11.1%), **-$117.19**, p = 0.038, and its 32 winners netted
**-$0.34** -- but $53.14 of that is two 09-19 false-alarm hedges. Dropping
those two markets: 34 markets, 4 losses, -$64.06. Dropping 09-19 instead:
32 markets, 4 losses, -$87.40. Dropping both: 31 markets, 4 losses, -$78.18.
It is dollar-negative on every slice.

**This is a power failure, not a null.** With 18 markets and a 2.44% base,
clearing the 0.05/82 bar needs 5 losses, and 80% power needs a *true* loss
rate of **37.3%**. We measured 16.7%. The MDE table:

| bucket size | losses the base predicts | losses the 0.05/82 bar needs | true rate needed for 80% power |
|---|---|---|---|
| 18 markets | 0.44 | 5 | 37.3% |
| 36 markets | 0.88 | 6 | 22.0% |
| 50 markets | 1.22 | 7 | 18.2% |
| 91 markets | 2.22 | 9 | 12.5% |

Nothing in this feature family can be established as a *gate* at this n. It
can only be instrumented.

**Mechanism if it is real:** the offer we finally took had been standing while
the model already liked it, i.e. nobody else took the cheap side either --
the adversely-selected population. That is the same mechanism as Finding 1
seen from the other end, and it is why the two findings must be one flag with
a sign, not two gates.

---

## Refuted or not supported

1. **"Refused for confidence earlier in the same close" is not a warning.**
   Confirms the table's null on the TRAIN half: 279 markets / 214 closes /
   6 losses (2.2%) / +$384.77 against 418 markets / 11 losses (2.6%) /
   +$98.12. No TRAIN market was ever refused for confidence twice
   (`conf_ref_n_earlier >= 2` is empty), so there is no dose-response to test.
2. **The confidence swing has no warning shape in the direction the lead
   suggests.** `swing > 0.10` is 148 markets / 3 losses / +$265.02;
   `swing > 0.30` is 85 markets / **0 losses** / +$258.00; `swing > 0.50` is 50
   markets / 0 losses / +$157.76. Bigger swing, better outcome -- the reverse
   of the lead. Confidence never *fell* between an earlier reading and entry
   in any TRAIN fill (0 of 718), so "conf deteriorating into the entry" is not
   a population that exists.
3. **Leg type does not separate.** `early` 168 markets / 4 losses (2.4%) /
   -$15.09; `full` 73 / 2 (2.7%) / +$71.66; no leg field (older runs) 456 / 11
   (2.4%) / +$426.31. `tau >= 31` and `leg == 'early'` are the **same 168
   markets**, so those are one look, not two.
4. **Tau alone separates only weakly and is dominated by Finding 1.**
   `tau <= 15` 149 markets / 2 losses (1.3%) / +$289.35; `tau 16-29` 259 / 8
   (3.1%) / +$120.18; `tau == 30` 128 / 3 (2.3%) / +$110.34; `tau >= 31` 168 /
   4 (2.4%) / -$15.09. p ranges 0.3-0.9. None passes.
5. **The cushion x tau and cushion x leg interactions are empty.**
   `cushion < 2 AND tau >= 31` is **one** market, because a thin cushion at
   tau >= 31 barely occurs -- the remaining-window sd is large that early, so
   everything looks thin-cushion-free by construction. The interaction the
   task asked for cannot be estimated on the early leg at all.

## Could not measure, and why

- **Whether these rules would simply have re-bought the same market a second
  or two later at a worse price.** The refusal side is not logged with these
  features, so a blocked entry's counterfactual is unknown. This is the same
  gap the table flags as its proposal 4 and it applies to every rule here.
- **The trajectory before 2026-09-14.** No earlier evaluations were logged in
  enough markets, so Finding 1's population starts on 09-14. The within-day
  permutation controls for that in the estimate but cannot create the missing
  days.
- **Anything about tonight's DOGE close from the exchange tape.** The tape is
  deaf from 2026-09-23 00:11Z. Every number about DOGE here is from the bot's
  own logs and Kalshi's ledger.
- **Loss rates from the tape or the replay.** Not attempted, by rule.

## Solutions worth testing

1. **A paper arm that sizes UP on Finding 1: multiply the position by ~1.5-2x
   when the bot's own fair for our side was < 50% at any logged second >= 5 s
   earlier in this close, and by 1.0x when the feature is unknown.** Validated
   on live fills as dollars per market in the flagged bucket against the
   unflagged bucket, within-day, over >= 30 flagged closes -- roughly two weeks
   at the current 3-4 flagged markets a day. **It blocks nothing.** It never
   touches a hedge: it changes only entry size, and only upward. This is a
   "make more" proposal, so it sits below the two below in the standing
   priority order but it is the only one whose statistics pass the bar.
2. **Log the flag, gate on nothing (Finding 3).** Add
   `traj_min_conf_ge5s` and `traj_gap_s` to the `signal` and `refused`
   records so the "already sure >= 5 s ago" population accumulates with its
   refusals attached. At the current rate it needs ~6 weeks to reach the n a
   gate would require (91 markets for a 12.5% MDE). Blocks nothing; it is
   logging only.
3. **Do not ship a cushion or locked-prints gate.** Finding 2 is a reason to
   *not* make a change that tonight's loss argues for. If it is shipped anyway,
   ship it as a paper arm, and the pre-registered bar is that it must beat live
   by more than the +$30.59 (TRAIN) and +$5.29 (holdout) it would have thrown
   away.

## Housekeeping

Read-only throughout. No process started, stopped or signalled. Both
collectors verified alive after every job -- `kalshi_collector` pid 105304
(55 MB), `crypto_feeds` pid 105352 (52 MB). Peak python footprint for this
work was ~60 MB (the table is 1.6 MB of JSONL; the tape was never opened).
Free RAM 2.31 GB, free disk 22.7 GB.
