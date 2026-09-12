# RESULTS — pinmaker: how to buy better (take vs rest)

`2026-09-12 09:33 UTC` — `research/pinmaker.py`, trade tape only.

---

## VERDICT — RESTING IS WORSE THAN TAKING, AND THIS IS A KILL, NOT A SHRUG

**Taking the ask is the right way to buy, and the reason is not the price — it
is who fills a resting bid.** Across 9 days, 206 trade hours, 7,266 gated
markets and 793 closes, resting earns less per close than crossing the spread
in **113 of the 114 rule-versus-TAKE rows printed below** — every rule, every horizon, both entry
frames, fit and holdout, all three fill models — the single exception being
`REST-BID` under the live guards in the entry-A frame at **+$0.0061, t = +1.41**,
which is well inside its own noise. *Where it clears its pre-stated MDE, and
where it only fails to:* in the entry-B frame **every one of the nine
rule × horizon cells beats its MDE in ALL and in FIT**, and `REST-1`/`REST-AT`
beat it in the holdout too. In the entry-A frame `REST-1` and `REST-AT` at
R = 5 s and R = 10 s beat their MDE in ALL, FIT **and** holdout, with exactly
one exception (`REST-1` at R = 10 s in the fit, −$0.0107 against an MDE of
$0.0115, marginally inside); the R = 2 s cells and `REST-BID` mostly do not,
and for those the honest reading is **no power, not no effect** — R = 2 s
carries a per-close sd 4× larger precisely because a 2-second bid sometimes
dodges a loser by luck. At the bot's real
entry (entry B, first second an offer at or below the 98c ceiling actually
traded) taking makes **$+0.8241 per close at 20 contracts (t = +7.34)** against
**$+0.4653 for resting one tick below the ask for 5 s (t = +4.65)** — a gap of
**−$0.3587 per close, t = −5.79, against an MDE of $0.1737**. At the literal
gate second (entry A, no selection on a cheap print existing) the same
comparison is **$+0.0532 vs $+0.0389 per close, −$0.0143, t = −5.76, MDE
$0.0070**. **The mechanism is adverse selection and it is close to total: a bid
resting one tick under the ask for 5 s is filled on 29.0% of the markets that
went on to WIN (1,909 of 6,594) and on 100% of the 17 that LOST** — and at 14
of 14 losers in the entry-B frame, whose exact 95% lower bound is 80.7%,
nowhere near the winners' 66.8% [63.2, 70.3]. Nobody sells you a near-certain
contract for no reason; the seller who reaches down to our bid is the one who
already knows. **Resting does not even deliver a better price**, which is the
detail that should end the intuition: per entry `REST-1` bids strictly one tick
*under* the ask, yet its mean price PAID in the entry-B frame is **94.16c
against TAKE's 94.05c** — because the entries where a resting bid gets filled
are the contested, expensive ones, and the cheap uncontested offers are exactly
the ones nobody sells into. **The fee we would save is the smaller number by 2–5×**: at
entry A's 99.44c mean the whole taker fee is 0.039c per contract = $0.0078 per
close at size 20, against a measured cost of $0.0143 (1.8×), and at entry B's
94.05c it is 0.392c = $0.0783 against $0.3587 (4.6×). **The obvious defence
fails too** — cancelling the bid the moment the model's own belief turns changes
nothing at all (belief falls below 90% after entry on just 36 of 6,611 entries,
all 17 losers among them, median 5 s after entry, and every loser fill lands
*before* the pull). The seller is ahead of our index. **And this is the third
time the per-contract column has pointed the wrong way**: per contract, resting
at the touch looks 3.9× better than taking in the entry-A frame (+1.04c vs
+0.27c). Per close it is worse. Rarity again.

**What would have to be true for this to be an artefact, and it was checked.**
(1) *Entry B selects on the exact second a cheap offer traded, which is the best
possible moment for a taker.* True, and that is why entry A exists — it makes no
such selection and reaches the same verdict with the same sign and a larger
t. (2) *The fill model could be under-counting winner fills, which would make
resting look falsely bad.* The `opt` model counts **any** print at or below our
price as a full fill of 20 at the front of the queue; it is the most generous
definition available, and the queue-realistic `pess` model (only a print
strictly **through** our level) still puts resting at −$0.0200 per close on
entry A (t = −4.74) and −$0.3629 on entry B (t = −4.60). (3) *Losers might
simply be busier markets where any order fills, rather than informed sellers.*
**This instrument cannot separate those two and I am not claiming it can** —
the only thing that fills a bid on the near-certain side is somebody selling
the near-certain side, so "busy" and "informed" are the same event here. What
can be said is that it is not "everything fills eventually": at R = 2 s the
loser fill rate is already 75–86% against 12–22% on winners, so the separation
is present at the shortest horizon and does not need time to accumulate. Which
of the two labels is right does not change the P&L, and the P&L is the answer.
(4) *Queue position might rescue it.* It cannot, and it runs the
wrong way: **79.9% of taker groups trade at a single price level and 55.9% of
contracts transact at the group's touch**, so a resting bid joins a queue at the
one level everybody hits — while a losing market gaps *through* that level, where
queue position gives no protection at all. The real-world number should be worse
than the one measured here, not better.

## PROPOSAL — nothing here is deployed, and nothing should be

1. **Keep the taker path exactly as it is.** No change to `pinrun`. The maker
   framing is dead for this gate at these prices, and it is dead on a measured
   difference rather than on an absence of power.
2. **Do not resurrect "rest instead of take" from the per-contract column.**
   It is the same shape that killed "wait for a 5–10c discount" (2026-09-11)
   and "stop paying above 94c" (2026-09-12). Write it into the killed list with
   its reason: *the seller who crosses to a resting bid on a near-certain
   contract is adversely selected, at a fill-rate ratio of 1.3–5.3× loser to
   winner, and that cost is 2–5× the entire fee it saves.*
3. **The lever with headroom is COUNT, not price.** An acceptable offer
   demonstrably traded on only **694 of 7,266 gated markets (9.6%)** and on
   **411 of 793 closes (51.8%)**. Half the closes we are confident about are
   never traded at all because nobody is offering. That is where the money is,
   and it is a different question from this one.
4. **One thing a resting order could still buy us, and it is information, not
   profit.** The primary open risk on the whole strategy is unchanged and
   unmeasurable from tape: *whether we win the race for the offer we take.* A
   1-contract bid parked one tick under the ask at the gate, never scaled, would
   record whether it fills and when — the only instrument that can see queue
   position from the inside. It would cost under a dollar per event. **That is
   a measurement proposal, not a trade, and under the amended rule 1 it needs
   the operator's per-order sign-off; it is not requested here.**

## WHAT THIS DOES NOT MEASURE — read before using any number above

* **Whether a fill would be OURS.** Every fill in this report, taker and maker
  alike, assumes we win the race. Live, the taker path fills 70% of its
  attempts; the maker path has no measured analogue. This is still the biggest
  unknown in the project and nothing here touched it.
* **Our loss rate.** Every loss rate in this report is the TAPE's, on other
  people's fills. Per the standing house rule it is used to RANK the rules
  against each other and for nothing else. Live loss rates come from live fills.
* **Resting depth.** TAKE is priced as a full fill of 20 at the inferred ask;
  prints cannot see the size behind it.
* **Fills inside the last 3 seconds** cannot be cancelled by the alarm test,
  because the model window stops at `TAU_MIN`.
* **Excluded, from both arms equally:** 217 gated markets with no prints in the
  window (3.0%) and 438 where no ask could be inferred from prints within 60 s
  (6.0%). Exclusion is paired, so it cannot bias the comparison, but it does
  mean the levels describe markets that printed.
* **`REST-AT` is not a placeable maker order.** A bid at the current ask
  crosses and bills the taker fee. It is priced here with zero fee purely as
  the arithmetic ceiling on "resting never costs us a worse price".
* **Entry A's inferred ask is stale by a median 6 s**, because at the first
  gated second the most recent same-side print is usually old. That is the
  reason entry B exists, and the reason the absolute levels to quote are
  entry B's.

---

## Sample

* gate: the first second with belief >= 99.5% and 3 <= tau <= 30s, computed by calling `pinrun.fair()` through `pinsim.TapeIndex` -- the live model itself, not a copy of it.
* size 20 contracts. Taker fee `ceil(0.07*n*p*(1-p), $0.0001)`; maker fee zero (`fee_type quadratic`, verified per series).
* **ENTRY A -- first gated second (the question as asked)**: 6,611 entries, 793 closes, 10 UTC days (2026-09-03 .. 2026-09-12); median tau at entry 30s; median inferred ask 99.9c (90th pct 99.9c); median ask age 6s; a bid was inferable for 98.4%.
* **ENTRY B -- first gated second whose ask is at or below the live ceiling 98.0c (what the bot does)**: 694 entries, 411 closes, 10 UTC days (2026-09-03 .. 2026-09-12); median tau at entry 23s; median inferred ask 96.8c (90th pct 98.0c); median ask age 0s; a bid was inferable for 100.0%.
* counters: `{'markets': 7371, 'no_model': 99, 'gate': 7266, 'B_never_tradeable': 6355, 'A_no_bid_inferable': 104, 'A_drop_no_ask': 438, 'drop_no_prints': 217, 'never_gated': 6, 'truncated_gz': 3}`

**Both entry sets are reported because entry A is not the live bot.** The bot re-reads the book every ~50 ms and buys the FIRST acceptable offer, so a single snapshot at the first gated second catches it before any acceptable offer exists: entry A's median ask sits above the live 98c ceiling, which the bot would refuse outright. Entry A answers the question exactly as posed; entry B is the one whose absolute level means anything.

---

# ENTRY A (first gated second)


## ALL — 10 UTC day labels, 2026-09-03 .. 2026-09-12


**MDE, stated before the estimates** (`opt`, n=793 closes, 80% power at alpha 0.05, paired per close). Below this line, 'no advantage' means 'no power', not 'no effect':

| comparison | R | sd of per-close difference | MDE ($/close at 20) |
|---|---|---|---|
| REST-1 - TAKE | 2s | $0.2518 | **$0.0250** |
| REST-AT - TAKE | 2s | $0.2503 | **$0.0249** |
| REST-BID - TAKE | 2s | $0.2893 | **$0.0288** |
| REST-1 - TAKE | 5s | $0.0700 | **$0.0070** |
| REST-AT - TAKE | 5s | $0.0688 | **$0.0068** |
| REST-BID - TAKE | 5s | $0.1498 | **$0.0149** |
| REST-1 - TAKE | 10s | $0.0694 | **$0.0069** |
| REST-AT - TAKE | 10s | $0.0681 | **$0.0068** |
| REST-BID - TAKE | 10s | $0.1446 | **$0.0144** |

### R = 2s, fill rule `opt`  (6,611 entries over 793 closes)

| rule | entries | fills | fill rate | mean price paid | loss rate on filled (TAPE) | 95% CI | P&L/contract | **$/close at 20** | t | vs TAKE $/close | t(diff) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| TAKE | 6,611 | 6,611 | 100.0% | 99.44c | 0.26% | [0.15, 0.41] | +0.27c | **$+0.0532** | +2.81 | — | — |
| REST-1 | 6,611 | 1,403 | 21.2% | 98.13c | 1.00% | [0.55, 1.67] | +0.87c | **$+0.0366** | +2.91 | $-0.0166 | -1.86 |
| REST-AT | 6,611 | 2,228 | 33.7% | 98.84c | 0.63% | [0.34, 1.05] | +0.53c | **$+0.0357** | +2.83 | $-0.0175 | -1.97 |
| REST-BID | 6,507 | 958 | 14.7% | 97.42c | 1.36% | [0.72, 2.31] | +1.22c | **$+0.0349** | +2.93 | $-0.0182 | -1.78 |

### R = 5s, fill rule `opt`  (6,611 entries over 793 closes)

| rule | entries | fills | fill rate | mean price paid | loss rate on filled (TAPE) | 95% CI | P&L/contract | **$/close at 20** | t | vs TAKE $/close | t(diff) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| TAKE | 6,611 | 6,611 | 100.0% | 99.44c | 0.26% | [0.15, 0.41] | +0.27c | **$+0.0532** | +2.81 | — | — |
| REST-1 | 6,611 | 1,926 | 29.1% | 98.45c | 0.88% | [0.51, 1.41] | +0.67c | **$+0.0389** | +2.07 | $-0.0143 | -5.76 |
| REST-AT | 6,611 | 3,377 | 51.1% | 99.12c | 0.50% | [0.29, 0.80] | +0.38c | **$+0.0384** | +2.04 | $-0.0148 | -6.05 |
| REST-BID | 6,507 | 1,366 | 21.0% | 97.79c | 1.17% | [0.67, 1.90] | +1.04c | **$+0.0428** | +2.34 | $-0.0104 | -1.96 |

### R = 10s, fill rule `opt`  (6,611 entries over 793 closes)

| rule | entries | fills | fill rate | mean price paid | loss rate on filled (TAPE) | 95% CI | P&L/contract | **$/close at 20** | t | vs TAKE $/close | t(diff) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| TAKE | 6,611 | 6,611 | 100.0% | 99.44c | 0.26% | [0.15, 0.41] | +0.27c | **$+0.0532** | +2.81 | — | — |
| REST-1 | 6,611 | 2,229 | 33.7% | 98.60c | 0.76% | [0.44, 1.22] | +0.64c | **$+0.0429** | +2.28 | $-0.0103 | -4.17 |
| REST-AT | 6,611 | 4,131 | 62.5% | 99.25c | 0.41% | [0.24, 0.66] | +0.34c | **$+0.0426** | +2.27 | $-0.0106 | -4.36 |
| REST-BID | 6,507 | 1,624 | 25.0% | 97.92c | 1.05% | [0.61, 1.67] | +1.03c | **$+0.0504** | +2.69 | $-0.0028 | -0.54 |

**Adverse selection: who fills us?** 6,594 entries went on to WIN, 17 went on to LOSE. If resting were harmless the two fill rates would match.

| rule | R | fill rate on WINNERS | fill rate on LOSERS | loser fills / winner fills |
|---|---|---|---|---|
| REST-1 | 2s | 21.1% (1,389/6,594) | 82.4% (14/17) | **3.91x** |
| REST-1 | 5s | 29.0% (1,909/6,594) | 100.0% (17/17) | **3.45x** |
| REST-1 | 10s | 33.5% (2,212/6,594) | 100.0% (17/17) | **2.98x** |
| REST-AT | 2s | 33.6% (2,214/6,594) | 82.4% (14/17) | **2.45x** |
| REST-AT | 5s | 51.0% (3,360/6,594) | 100.0% (17/17) | **1.96x** |
| REST-AT | 10s | 62.4% (4,114/6,594) | 100.0% (17/17) | **1.60x** |
| REST-BID | 2s | 14.6% (945/6,490) | 76.5% (13/17) | **5.25x** |
| REST-BID | 5s | 20.8% (1,350/6,490) | 94.1% (16/17) | **4.52x** |
| REST-BID | 10s | 24.8% (1,607/6,490) | 100.0% (17/17) | **4.04x** |

**Cancel on alarm** (`opt`): pull the bid at the first second AFTER entry at which belief in our side falls below the threshold, effective one second later.

* belief fell below 90% after entry on **36 of 6,611** entries (0.5%), 17 of them on the 17 that lost; median 5s after entry.
* belief fell below 70% after entry on **25 of 6,611** entries (0.4%), 17 of them on the 17 that lost; median 6s after entry.

| rule | R | cancel below | fills | fills on LOSERS | $/close at 20 | t | vs TAKE | t(diff) |
|---|---|---|---|---|---|---|---|---|
| REST-1 | 2s | never | 1,403 | 14 of 17 | $+0.0366 | +2.91 | $-0.0166 | -1.86 |
| REST-1 | 2s | 90% | 1,403 | 14 of 17 | $+0.0366 | +2.91 | $-0.0166 | -1.86 |
| REST-1 | 2s | 70% | 1,403 | 14 of 17 | $+0.0366 | +2.91 | $-0.0166 | -1.86 |
| REST-1 | 5s | never | 1,926 | 17 of 17 | $+0.0389 | +2.07 | $-0.0143 | -5.76 |
| REST-1 | 5s | 90% | 1,926 | 17 of 17 | $+0.0389 | +2.07 | $-0.0143 | -5.76 |
| REST-1 | 5s | 70% | 1,926 | 17 of 17 | $+0.0389 | +2.07 | $-0.0143 | -5.76 |
| REST-1 | 10s | never | 2,229 | 17 of 17 | $+0.0429 | +2.28 | $-0.0103 | -4.17 |
| REST-1 | 10s | 90% | 2,229 | 17 of 17 | $+0.0429 | +2.28 | $-0.0103 | -4.17 |
| REST-1 | 10s | 70% | 2,229 | 17 of 17 | $+0.0429 | +2.28 | $-0.0103 | -4.17 |
| REST-BID | 2s | never | 958 | 13 of 17 | $+0.0349 | +2.93 | $-0.0182 | -1.78 |
| REST-BID | 2s | 90% | 958 | 13 of 17 | $+0.0349 | +2.93 | $-0.0182 | -1.78 |
| REST-BID | 2s | 70% | 958 | 13 of 17 | $+0.0349 | +2.93 | $-0.0182 | -1.78 |
| REST-BID | 5s | never | 1,366 | 16 of 17 | $+0.0428 | +2.34 | $-0.0104 | -1.96 |
| REST-BID | 5s | 90% | 1,366 | 16 of 17 | $+0.0428 | +2.34 | $-0.0104 | -1.96 |
| REST-BID | 5s | 70% | 1,366 | 16 of 17 | $+0.0428 | +2.34 | $-0.0104 | -1.96 |
| REST-BID | 10s | never | 1,624 | 17 of 17 | $+0.0504 | +2.69 | $-0.0028 | -0.54 |
| REST-BID | 10s | 90% | 1,624 | 17 of 17 | $+0.0504 | +2.69 | $-0.0028 | -0.54 |
| REST-BID | 10s | 70% | 1,624 | 17 of 17 | $+0.0504 | +2.69 | $-0.0028 | -0.54 |

## FIT — everything before the cut (2026-09-03 06:15Z .. 2026-09-08 04:30Z)


**MDE, stated before the estimates** (`opt`, n=456 closes, 80% power at alpha 0.05, paired per close). Below this line, 'no advantage' means 'no power', not 'no effect':

| comparison | R | sd of per-close difference | MDE ($/close at 20) |
|---|---|---|---|
| REST-1 - TAKE | 2s | $0.0930 | **$0.0122** |
| REST-AT - TAKE | 2s | $0.0931 | **$0.0122** |
| REST-BID - TAKE | 2s | $0.1396 | **$0.0183** |
| REST-1 - TAKE | 5s | $0.0884 | **$0.0116** |
| REST-AT - TAKE | 5s | $0.0876 | **$0.0115** |
| REST-BID - TAKE | 5s | $0.1435 | **$0.0188** |
| REST-1 - TAKE | 10s | $0.0880 | **$0.0115** |
| REST-AT - TAKE | 10s | $0.0871 | **$0.0114** |
| REST-BID - TAKE | 10s | $0.1467 | **$0.0192** |

### R = 2s, fill rule `opt`  (3,833 entries over 456 closes)

| rule | entries | fills | fill rate | mean price paid | loss rate on filled (TAPE) | 95% CI | P&L/contract | **$/close at 20** | t | vs TAKE $/close | t(diff) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| TAKE | 3,833 | 3,833 | 100.0% | 99.41c | 0.13% | [0.04, 0.30] | +0.42c | **$+0.0827** | +6.90 | — | — |
| REST-1 | 3,833 | 875 | 22.8% | 98.19c | 0.57% | [0.19, 1.33] | +1.24c | **$+0.0551** | +4.88 | $-0.0277 | -6.35 |
| REST-AT | 3,833 | 1,336 | 34.9% | 98.83c | 0.37% | [0.12, 0.87] | +0.79c | **$+0.0539** | +4.81 | $-0.0289 | -6.62 |
| REST-BID | 3,774 | 618 | 16.4% | 97.43c | 0.81% | [0.26, 1.88] | +1.76c | **$+0.0555** | +5.15 | $-0.0272 | -4.17 |

### R = 5s, fill rule `opt`  (3,833 entries over 456 closes)

| rule | entries | fills | fill rate | mean price paid | loss rate on filled (TAPE) | 95% CI | P&L/contract | **$/close at 20** | t | vs TAKE $/close | t(diff) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| TAKE | 3,833 | 3,833 | 100.0% | 99.41c | 0.13% | [0.04, 0.30] | +0.42c | **$+0.0827** | +6.90 | — | — |
| REST-1 | 3,833 | 1,218 | 31.8% | 98.50c | 0.41% | [0.13, 0.96] | +1.09c | **$+0.0676** | +5.83 | $-0.0151 | -3.64 |
| REST-AT | 3,833 | 2,016 | 52.6% | 99.11c | 0.25% | [0.08, 0.58] | +0.65c | **$+0.0664** | +5.80 | $-0.0163 | -3.97 |
| REST-BID | 3,774 | 872 | 23.1% | 97.81c | 0.57% | [0.19, 1.33] | +1.62c | **$+0.0722** | +6.54 | $-0.0105 | -1.56 |

### R = 10s, fill rule `opt`  (3,833 entries over 456 closes)

| rule | entries | fills | fill rate | mean price paid | loss rate on filled (TAPE) | 95% CI | P&L/contract | **$/close at 20** | t | vs TAKE $/close | t(diff) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| TAKE | 3,833 | 3,833 | 100.0% | 99.41c | 0.13% | [0.04, 0.30] | +0.42c | **$+0.0827** | +6.90 | — | — |
| REST-1 | 3,833 | 1,401 | 36.6% | 98.63c | 0.36% | [0.12, 0.83] | +1.01c | **$+0.0720** | +6.19 | $-0.0107 | -2.60 |
| REST-AT | 3,833 | 2,473 | 64.5% | 99.23c | 0.20% | [0.07, 0.47] | +0.56c | **$+0.0710** | +6.19 | $-0.0118 | -2.88 |
| REST-BID | 3,774 | 1,038 | 27.5% | 97.97c | 0.48% | [0.16, 1.12] | +1.55c | **$+0.0822** | +7.32 | $-0.0006 | -0.08 |

**Adverse selection: who fills us?** 3,828 entries went on to WIN, 5 went on to LOSE. If resting were harmless the two fill rates would match.

| rule | R | fill rate on WINNERS | fill rate on LOSERS | loser fills / winner fills |
|---|---|---|---|---|
| REST-1 | 2s | 22.7% (870/3,828) | 100.0% (5/5) | **4.40x** |
| REST-1 | 5s | 31.7% (1,213/3,828) | 100.0% (5/5) | **3.16x** |
| REST-1 | 10s | 36.5% (1,396/3,828) | 100.0% (5/5) | **2.74x** |
| REST-AT | 2s | 34.8% (1,331/3,828) | 100.0% (5/5) | **2.88x** |
| REST-AT | 5s | 52.5% (2,011/3,828) | 100.0% (5/5) | **1.90x** |
| REST-AT | 10s | 64.5% (2,468/3,828) | 100.0% (5/5) | **1.55x** |
| REST-BID | 2s | 16.3% (613/3,769) | 100.0% (5/5) | **6.15x** |
| REST-BID | 5s | 23.0% (867/3,769) | 100.0% (5/5) | **4.35x** |
| REST-BID | 10s | 27.4% (1,033/3,769) | 100.0% (5/5) | **3.65x** |

**Cancel on alarm** (`opt`): pull the bid at the first second AFTER entry at which belief in our side falls below the threshold, effective one second later.

* belief fell below 90% after entry on **17 of 3,833** entries (0.4%), 5 of them on the 5 that lost; median 5s after entry.
* belief fell below 70% after entry on **8 of 3,833** entries (0.2%), 5 of them on the 5 that lost; median 6s after entry.

| rule | R | cancel below | fills | fills on LOSERS | $/close at 20 | t | vs TAKE | t(diff) |
|---|---|---|---|---|---|---|---|---|
| REST-1 | 2s | never | 875 | 5 of 5 | $+0.0551 | +4.88 | $-0.0277 | -6.35 |
| REST-1 | 2s | 90% | 875 | 5 of 5 | $+0.0551 | +4.88 | $-0.0277 | -6.35 |
| REST-1 | 2s | 70% | 875 | 5 of 5 | $+0.0551 | +4.88 | $-0.0277 | -6.35 |
| REST-1 | 5s | never | 1,218 | 5 of 5 | $+0.0676 | +5.83 | $-0.0151 | -3.64 |
| REST-1 | 5s | 90% | 1,218 | 5 of 5 | $+0.0676 | +5.83 | $-0.0151 | -3.64 |
| REST-1 | 5s | 70% | 1,218 | 5 of 5 | $+0.0676 | +5.83 | $-0.0151 | -3.64 |
| REST-1 | 10s | never | 1,401 | 5 of 5 | $+0.0720 | +6.19 | $-0.0107 | -2.60 |
| REST-1 | 10s | 90% | 1,401 | 5 of 5 | $+0.0720 | +6.19 | $-0.0107 | -2.60 |
| REST-1 | 10s | 70% | 1,401 | 5 of 5 | $+0.0720 | +6.19 | $-0.0107 | -2.60 |
| REST-BID | 2s | never | 618 | 5 of 5 | $+0.0555 | +5.15 | $-0.0272 | -4.17 |
| REST-BID | 2s | 90% | 618 | 5 of 5 | $+0.0555 | +5.15 | $-0.0272 | -4.17 |
| REST-BID | 2s | 70% | 618 | 5 of 5 | $+0.0555 | +5.15 | $-0.0272 | -4.17 |
| REST-BID | 5s | never | 872 | 5 of 5 | $+0.0722 | +6.54 | $-0.0105 | -1.56 |
| REST-BID | 5s | 90% | 872 | 5 of 5 | $+0.0722 | +6.54 | $-0.0105 | -1.56 |
| REST-BID | 5s | 70% | 872 | 5 of 5 | $+0.0722 | +6.54 | $-0.0105 | -1.56 |
| REST-BID | 10s | never | 1,038 | 5 of 5 | $+0.0822 | +7.32 | $-0.0006 | -0.08 |
| REST-BID | 10s | 90% | 1,038 | 5 of 5 | $+0.0822 | +7.32 | $-0.0006 | -0.08 |
| REST-BID | 10s | 70% | 1,038 | 5 of 5 | $+0.0822 | +7.32 | $-0.0006 | -0.08 |

## HOLDOUT — the last 4 days (2026-09-08 04:45Z .. 2026-09-12 04:45Z)


**MDE, stated before the estimates** (`opt`, n=337 closes, 80% power at alpha 0.05, paired per close). Below this line, 'no advantage' means 'no power', not 'no effect':

| comparison | R | sd of per-close difference | MDE ($/close at 20) |
|---|---|---|---|
| REST-1 - TAKE | 2s | $0.3706 | **$0.0566** |
| REST-AT - TAKE | 2s | $0.3681 | **$0.0562** |
| REST-BID - TAKE | 2s | $0.4131 | **$0.0630** |
| REST-1 - TAKE | 5s | $0.0307 | **$0.0047** |
| REST-AT - TAKE | 5s | $0.0274 | **$0.0042** |
| REST-BID - TAKE | 5s | $0.1582 | **$0.0241** |
| REST-1 - TAKE | 10s | $0.0293 | **$0.0045** |
| REST-AT - TAKE | 10s | $0.0259 | **$0.0040** |
| REST-BID - TAKE | 10s | $0.1418 | **$0.0216** |

### R = 2s, fill rule `opt`  (2,778 entries over 337 closes)

| rule | entries | fills | fill rate | mean price paid | loss rate on filled (TAPE) | 95% CI | P&L/contract | **$/close at 20** | t | vs TAKE $/close | t(diff) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| TAKE | 2,778 | 2,778 | 100.0% | 99.48c | 0.43% | [0.22, 0.75] | +0.05c | **$+0.0132** | +0.32 | — | — |
| REST-1 | 2,778 | 528 | 19.0% | 98.03c | 1.70% | [0.78, 3.21] | +0.27c | **$+0.0116** | +0.46 | $-0.0016 | -0.08 |
| REST-AT | 2,778 | 892 | 32.1% | 98.84c | 1.01% | [0.46, 1.91] | +0.15c | **$+0.0111** | +0.44 | $-0.0022 | -0.11 |
| REST-BID | 2,733 | 340 | 12.4% | 97.41c | 2.35% | [1.02, 4.58] | +0.24c | **$+0.0071** | +0.30 | $-0.0061 | -0.27 |

### R = 5s, fill rule `opt`  (2,778 entries over 337 closes)

| rule | entries | fills | fill rate | mean price paid | loss rate on filled (TAPE) | 95% CI | P&L/contract | **$/close at 20** | t | vs TAKE $/close | t(diff) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| TAKE | 2,778 | 2,778 | 100.0% | 99.48c | 0.43% | [0.22, 0.75] | +0.05c | **$+0.0132** | +0.32 | — | — |
| REST-1 | 2,778 | 708 | 25.5% | 98.36c | 1.69% | [0.88, 2.94] | -0.06c | **$-0.0000** | -0.00 | $-0.0132 | -7.93 |
| REST-AT | 2,778 | 1,361 | 49.0% | 99.15c | 0.88% | [0.46, 1.54] | -0.03c | **$+0.0005** | +0.01 | $-0.0128 | -8.57 |
| REST-BID | 2,733 | 494 | 18.1% | 97.76c | 2.23% | [1.12, 3.95] | +0.02c | **$+0.0029** | +0.07 | $-0.0103 | -1.20 |

### R = 10s, fill rule `opt`  (2,778 entries over 337 closes)

| rule | entries | fills | fill rate | mean price paid | loss rate on filled (TAPE) | 95% CI | P&L/contract | **$/close at 20** | t | vs TAKE $/close | t(diff) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| TAKE | 2,778 | 2,778 | 100.0% | 99.48c | 0.43% | [0.22, 0.75] | +0.05c | **$+0.0132** | +0.32 | — | — |
| REST-1 | 2,778 | 828 | 29.8% | 98.54c | 1.45% | [0.75, 2.52] | +0.01c | **$+0.0035** | +0.09 | $-0.0097 | -6.06 |
| REST-AT | 2,778 | 1,658 | 59.7% | 99.27c | 0.72% | [0.37, 1.26] | +0.01c | **$+0.0043** | +0.10 | $-0.0089 | -6.32 |
| REST-BID | 2,733 | 586 | 21.4% | 97.83c | 2.05% | [1.06, 3.55] | +0.12c | **$+0.0075** | +0.18 | $-0.0058 | -0.75 |

**Adverse selection: who fills us?** 2,766 entries went on to WIN, 12 went on to LOSE. If resting were harmless the two fill rates would match.

| rule | R | fill rate on WINNERS | fill rate on LOSERS | loser fills / winner fills |
|---|---|---|---|---|
| REST-1 | 2s | 18.8% (519/2,766) | 75.0% (9/12) | **4.00x** |
| REST-1 | 5s | 25.2% (696/2,766) | 100.0% (12/12) | **3.97x** |
| REST-1 | 10s | 29.5% (816/2,766) | 100.0% (12/12) | **3.39x** |
| REST-AT | 2s | 31.9% (883/2,766) | 75.0% (9/12) | **2.35x** |
| REST-AT | 5s | 48.8% (1,349/2,766) | 100.0% (12/12) | **2.05x** |
| REST-AT | 10s | 59.5% (1,646/2,766) | 100.0% (12/12) | **1.68x** |
| REST-BID | 2s | 12.2% (332/2,721) | 66.7% (8/12) | **5.46x** |
| REST-BID | 5s | 17.8% (483/2,721) | 91.7% (11/12) | **5.16x** |
| REST-BID | 10s | 21.1% (574/2,721) | 100.0% (12/12) | **4.74x** |

**Cancel on alarm** (`opt`): pull the bid at the first second AFTER entry at which belief in our side falls below the threshold, effective one second later.

* belief fell below 90% after entry on **19 of 2,778** entries (0.7%), 12 of them on the 12 that lost; median 4s after entry.
* belief fell below 70% after entry on **17 of 2,778** entries (0.6%), 12 of them on the 12 that lost; median 5s after entry.

| rule | R | cancel below | fills | fills on LOSERS | $/close at 20 | t | vs TAKE | t(diff) |
|---|---|---|---|---|---|---|---|---|
| REST-1 | 2s | never | 528 | 9 of 12 | $+0.0116 | +0.46 | $-0.0016 | -0.08 |
| REST-1 | 2s | 90% | 528 | 9 of 12 | $+0.0116 | +0.46 | $-0.0016 | -0.08 |
| REST-1 | 2s | 70% | 528 | 9 of 12 | $+0.0116 | +0.46 | $-0.0016 | -0.08 |
| REST-1 | 5s | never | 708 | 12 of 12 | $-0.0000 | -0.00 | $-0.0132 | -7.93 |
| REST-1 | 5s | 90% | 708 | 12 of 12 | $-0.0000 | -0.00 | $-0.0132 | -7.93 |
| REST-1 | 5s | 70% | 708 | 12 of 12 | $-0.0000 | -0.00 | $-0.0132 | -7.93 |
| REST-1 | 10s | never | 828 | 12 of 12 | $+0.0035 | +0.09 | $-0.0097 | -6.06 |
| REST-1 | 10s | 90% | 828 | 12 of 12 | $+0.0035 | +0.09 | $-0.0097 | -6.06 |
| REST-1 | 10s | 70% | 828 | 12 of 12 | $+0.0035 | +0.09 | $-0.0097 | -6.06 |
| REST-BID | 2s | never | 340 | 8 of 12 | $+0.0071 | +0.30 | $-0.0061 | -0.27 |
| REST-BID | 2s | 90% | 340 | 8 of 12 | $+0.0071 | +0.30 | $-0.0061 | -0.27 |
| REST-BID | 2s | 70% | 340 | 8 of 12 | $+0.0071 | +0.30 | $-0.0061 | -0.27 |
| REST-BID | 5s | never | 494 | 11 of 12 | $+0.0029 | +0.07 | $-0.0103 | -1.20 |
| REST-BID | 5s | 90% | 494 | 11 of 12 | $+0.0029 | +0.07 | $-0.0103 | -1.20 |
| REST-BID | 5s | 70% | 494 | 11 of 12 | $+0.0029 | +0.07 | $-0.0103 | -1.20 |
| REST-BID | 10s | never | 586 | 12 of 12 | $+0.0075 | +0.18 | $-0.0058 | -0.75 |
| REST-BID | 10s | 90% | 586 | 12 of 12 | $+0.0075 | +0.18 | $-0.0058 | -0.75 |
| REST-BID | 10s | 70% | 586 | 12 of 12 | $+0.0075 | +0.18 | $-0.0058 | -0.75 |

## Fill-definition sensitivity (ENTRY A (first gated second), R=5s)

The three definitions bracket queue position, which prints cannot see: `opt` assumes we are at the front of the queue, `size` needs enough contracts through our price to fill 20, `pess` needs the level cleared outright.

### R = 5s, fill rule `opt`  (6,611 entries over 793 closes)

| rule | entries | fills | fill rate | mean price paid | loss rate on filled (TAPE) | 95% CI | P&L/contract | **$/close at 20** | t | vs TAKE $/close | t(diff) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| TAKE | 6,611 | 6,611 | 100.0% | 99.44c | 0.26% | [0.15, 0.41] | +0.27c | **$+0.0532** | +2.81 | — | — |
| REST-1 | 6,611 | 1,926 | 29.1% | 98.45c | 0.88% | [0.51, 1.41] | +0.67c | **$+0.0389** | +2.07 | $-0.0143 | -5.76 |
| REST-AT | 6,611 | 3,377 | 51.1% | 99.12c | 0.50% | [0.29, 0.80] | +0.38c | **$+0.0384** | +2.04 | $-0.0148 | -6.05 |
| REST-BID | 6,507 | 1,366 | 21.0% | 97.79c | 1.17% | [0.67, 1.90] | +1.04c | **$+0.0428** | +2.34 | $-0.0104 | -1.96 |

### R = 5s, fill rule `size`  (6,611 entries over 793 closes)

| rule | entries | fills | fill rate | mean price paid | loss rate on filled (TAPE) | 95% CI | P&L/contract | **$/close at 20** | t | vs TAKE $/close | t(diff) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| TAKE | 6,611 | 6,611 | 100.0% | 99.44c | 0.26% | [0.15, 0.41] | +0.27c | **$+0.0532** | +2.81 | — | — |
| REST-1 | 6,611 | 1,667 | 25.2% | 98.41c | 1.02% | [0.60, 1.63] | +0.57c | **$+0.0288** | +1.55 | $-0.0244 | -7.31 |
| REST-AT | 6,611 | 2,863 | 43.3% | 99.08c | 0.59% | [0.35, 0.95] | +0.32c | **$+0.0281** | +1.51 | $-0.0251 | -7.57 |
| REST-BID | 6,507 | 1,194 | 18.3% | 97.76c | 1.34% | [0.77, 2.17] | +0.90c | **$+0.0326** | +1.80 | $-0.0205 | -3.81 |

### R = 5s, fill rule `pess`  (6,611 entries over 793 closes)

| rule | entries | fills | fill rate | mean price paid | loss rate on filled (TAPE) | 95% CI | P&L/contract | **$/close at 20** | t | vs TAKE $/close | t(diff) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| TAKE | 6,611 | 6,611 | 100.0% | 99.44c | 0.26% | [0.15, 0.41] | +0.27c | **$+0.0532** | +2.81 | — | — |
| REST-1 | 6,611 | 1,431 | 21.6% | 98.12c | 1.12% | [0.64, 1.81] | +0.77c | **$+0.0332** | +2.03 | $-0.0200 | -4.74 |
| REST-AT | 6,611 | 1,926 | 29.1% | 98.57c | 0.88% | [0.51, 1.41] | +0.55c | **$+0.0323** | +1.72 | $-0.0209 | -8.53 |
| REST-BID | 6,507 | 789 | 12.1% | 97.03c | 1.90% | [1.07, 3.12] | +1.07c | **$+0.0258** | +1.63 | $-0.0274 | -4.35 |

## The live guards (ENTRY A (first gated second))


### With the live guards on (ceiling 98.0c, refuse a discount >= 15c), R=5s, `opt`

| rule | entries allowed | fills | $/close at 20 | t | vs TAKE | t(diff) |
|---|---|---|---|---|---|---|
| TAKE | 481 | 481 | $+0.0315 | +4.11 | — | — |
| REST-1 | 483 | 418 | $+0.0287 | +3.71 | $-0.0028 | -2.19 |
| REST-AT | 481 | 425 | $+0.0289 | +3.73 | $-0.0026 | -2.64 |
| REST-BID | 808 | 359 | $+0.0376 | +5.12 | $+0.0061 | +1.41 |

---

# ENTRY B (first tradeable second, ask <= ceiling)


## ALL — 10 UTC day labels, 2026-09-03 .. 2026-09-12


**MDE, stated before the estimates** (`opt`, n=411 closes, 80% power at alpha 0.05, paired per close). Below this line, 'no advantage' means 'no power', not 'no effect':

| comparison | R | sd of per-close difference | MDE ($/close at 20) |
|---|---|---|---|
| REST-1 - TAKE | 2s | $1.3861 | **$0.1915** |
| REST-AT - TAKE | 2s | $1.2871 | **$0.1779** |
| REST-BID - TAKE | 2s | $1.7360 | **$0.2399** |
| REST-1 - TAKE | 5s | $1.2567 | **$0.1737** |
| REST-AT - TAKE | 5s | $1.1432 | **$0.1580** |
| REST-BID - TAKE | 5s | $1.6724 | **$0.2311** |
| REST-1 - TAKE | 10s | $1.2526 | **$0.1731** |
| REST-AT - TAKE | 10s | $1.1373 | **$0.1572** |
| REST-BID - TAKE | 10s | $1.3740 | **$0.1899** |

### R = 2s, fill rule `opt`  (694 entries over 411 closes)

| rule | entries | fills | fill rate | mean price paid | loss rate on filled (TAPE) | 95% CI | P&L/contract | **$/close at 20** | t | vs TAKE $/close | t(diff) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| TAKE | 694 | 694 | 100.0% | 94.05c | 2.02% | [1.11, 3.36] | +3.59c | **$+0.8241** | +7.34 | — | — |
| REST-1 | 694 | 398 | 57.3% | 94.16c | 3.02% | [1.57, 5.21] | +2.82c | **$+0.4243** | +4.35 | $-0.3998 | -5.85 |
| REST-AT | 694 | 422 | 60.8% | 94.30c | 2.84% | [1.48, 4.91] | +2.86c | **$+0.4610** | +4.60 | $-0.3631 | -5.72 |
| REST-BID | 694 | 262 | 37.8% | 92.06c | 4.20% | [2.11, 7.39] | +3.74c | **$+0.4075** | +4.82 | $-0.4165 | -4.86 |

### R = 5s, fill rule `opt`  (694 entries over 411 closes)

| rule | entries | fills | fill rate | mean price paid | loss rate on filled (TAPE) | 95% CI | P&L/contract | **$/close at 20** | t | vs TAKE $/close | t(diff) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| TAKE | 694 | 694 | 100.0% | 94.05c | 2.02% | [1.11, 3.36] | +3.59c | **$+0.8241** | +7.34 | — | — |
| REST-1 | 694 | 468 | 67.4% | 94.16c | 2.99% | [1.64, 4.97] | +2.85c | **$+0.4653** | +4.65 | $-0.3587 | -5.79 |
| REST-AT | 694 | 493 | 71.0% | 94.29c | 2.84% | [1.56, 4.72] | +2.87c | **$+0.5039** | +4.91 | $-0.3202 | -5.68 |
| REST-BID | 694 | 317 | 45.7% | 92.01c | 4.10% | [2.20, 6.91] | +3.89c | **$+0.4675** | +5.28 | $-0.3566 | -4.32 |

### R = 10s, fill rule `opt`  (694 entries over 411 closes)

| rule | entries | fills | fill rate | mean price paid | loss rate on filled (TAPE) | 95% CI | P&L/contract | **$/close at 20** | t | vs TAKE $/close | t(diff) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| TAKE | 694 | 694 | 100.0% | 94.05c | 2.02% | [1.11, 3.36] | +3.59c | **$+0.8241** | +7.34 | — | — |
| REST-1 | 694 | 494 | 71.2% | 94.22c | 2.83% | [1.56, 4.71] | +2.94c | **$+0.4968** | +4.95 | $-0.3273 | -5.30 |
| REST-AT | 694 | 520 | 74.9% | 94.36c | 2.69% | [1.48, 4.48] | +2.95c | **$+0.5341** | +5.20 | $-0.2899 | -5.17 |
| REST-BID | 694 | 346 | 49.9% | 91.94c | 4.05% | [2.23, 6.70] | +4.01c | **$+0.4703** | +4.63 | $-0.3537 | -5.22 |

**Adverse selection: who fills us?** 680 entries went on to WIN, 14 went on to LOSE. If resting were harmless the two fill rates would match.

| rule | R | fill rate on WINNERS | fill rate on LOSERS | loser fills / winner fills |
|---|---|---|---|---|
| REST-1 | 2s | 56.8% (386/680) | 85.7% (12/14) | **1.51x** |
| REST-1 | 5s | 66.8% (454/680) | 100.0% (14/14) | **1.50x** |
| REST-1 | 10s | 70.6% (480/680) | 100.0% (14/14) | **1.42x** |
| REST-AT | 2s | 60.3% (410/680) | 85.7% (12/14) | **1.42x** |
| REST-AT | 5s | 70.4% (479/680) | 100.0% (14/14) | **1.42x** |
| REST-AT | 10s | 74.4% (506/680) | 100.0% (14/14) | **1.34x** |
| REST-BID | 2s | 36.9% (251/680) | 78.6% (11/14) | **2.13x** |
| REST-BID | 5s | 44.7% (304/680) | 92.9% (13/14) | **2.08x** |
| REST-BID | 10s | 48.8% (332/680) | 100.0% (14/14) | **2.05x** |

**Cancel on alarm** (`opt`): pull the bid at the first second AFTER entry at which belief in our side falls below the threshold, effective one second later.

* belief fell below 90% after entry on **32 of 694** entries (4.6%), 14 of them on the 14 that lost; median 4s after entry.
* belief fell below 70% after entry on **22 of 694** entries (3.2%), 14 of them on the 14 that lost; median 4s after entry.

| rule | R | cancel below | fills | fills on LOSERS | $/close at 20 | t | vs TAKE | t(diff) |
|---|---|---|---|---|---|---|---|---|
| REST-1 | 2s | never | 398 | 12 of 14 | $+0.4243 | +4.35 | $-0.3998 | -5.85 |
| REST-1 | 2s | 90% | 398 | 12 of 14 | $+0.4243 | +4.35 | $-0.3998 | -5.85 |
| REST-1 | 2s | 70% | 398 | 12 of 14 | $+0.4243 | +4.35 | $-0.3998 | -5.85 |
| REST-1 | 5s | never | 468 | 14 of 14 | $+0.4653 | +4.65 | $-0.3587 | -5.79 |
| REST-1 | 5s | 90% | 467 | 13 of 14 | $+0.4765 | +4.76 | $-0.3475 | -5.48 |
| REST-1 | 5s | 70% | 467 | 13 of 14 | $+0.4765 | +4.76 | $-0.3475 | -5.48 |
| REST-1 | 10s | never | 494 | 14 of 14 | $+0.4968 | +4.95 | $-0.3273 | -5.30 |
| REST-1 | 10s | 90% | 493 | 13 of 14 | $+0.5080 | +5.07 | $-0.3161 | -5.01 |
| REST-1 | 10s | 70% | 493 | 13 of 14 | $+0.5080 | +5.07 | $-0.3161 | -5.01 |
| REST-BID | 2s | never | 262 | 11 of 14 | $+0.4075 | +4.82 | $-0.4165 | -4.86 |
| REST-BID | 2s | 90% | 262 | 11 of 14 | $+0.4075 | +4.82 | $-0.4165 | -4.86 |
| REST-BID | 2s | 70% | 262 | 11 of 14 | $+0.4075 | +4.82 | $-0.4165 | -4.86 |
| REST-BID | 5s | never | 317 | 13 of 14 | $+0.4675 | +5.28 | $-0.3566 | -4.32 |
| REST-BID | 5s | 90% | 316 | 12 of 14 | $+0.4777 | +5.44 | $-0.3464 | -4.19 |
| REST-BID | 5s | 70% | 316 | 12 of 14 | $+0.4777 | +5.44 | $-0.3464 | -4.19 |
| REST-BID | 10s | never | 346 | 14 of 14 | $+0.4703 | +4.63 | $-0.3537 | -5.22 |
| REST-BID | 10s | 90% | 345 | 13 of 14 | $+0.4806 | +4.76 | $-0.3435 | -5.05 |
| REST-BID | 10s | 70% | 345 | 13 of 14 | $+0.4806 | +4.76 | $-0.3435 | -5.05 |

## FIT — everything before the cut (2026-09-03 06:45Z .. 2026-09-08 04:30Z)


**MDE, stated before the estimates** (`opt`, n=249 closes, 80% power at alpha 0.05, paired per close). Below this line, 'no advantage' means 'no power', not 'no effect':

| comparison | R | sd of per-close difference | MDE ($/close at 20) |
|---|---|---|---|
| REST-1 - TAKE | 2s | $1.5679 | **$0.2784** |
| REST-AT - TAKE | 2s | $1.5631 | **$0.2775** |
| REST-BID - TAKE | 2s | $1.6279 | **$0.2890** |
| REST-1 - TAKE | 5s | $1.4289 | **$0.2537** |
| REST-AT - TAKE | 5s | $1.4206 | **$0.2522** |
| REST-BID - TAKE | 5s | $1.5118 | **$0.2684** |
| REST-1 - TAKE | 10s | $1.4229 | **$0.2526** |
| REST-AT - TAKE | 10s | $1.4140 | **$0.2510** |
| REST-BID - TAKE | 10s | $1.5271 | **$0.2711** |

### R = 2s, fill rule `opt`  (420 entries over 249 closes)

| rule | entries | fills | fill rate | mean price paid | loss rate on filled (TAPE) | 95% CI | P&L/contract | **$/close at 20** | t | vs TAKE $/close | t(diff) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| TAKE | 420 | 420 | 100.0% | 94.35c | 0.95% | [0.26, 2.42] | +4.37c | **$+0.9504** | +9.19 | — | — |
| REST-1 | 420 | 241 | 57.4% | 94.83c | 1.24% | [0.26, 3.59] | +3.93c | **$+0.5049** | +9.63 | $-0.4454 | -4.48 |
| REST-AT | 420 | 255 | 60.7% | 95.04c | 1.18% | [0.24, 3.40] | +3.78c | **$+0.5095** | +10.01 | $-0.4409 | -4.45 |
| REST-BID | 420 | 162 | 38.6% | 92.78c | 1.85% | [0.38, 5.32] | +5.37c | **$+0.4923** | +8.35 | $-0.4581 | -4.44 |

### R = 5s, fill rule `opt`  (420 entries over 249 closes)

| rule | entries | fills | fill rate | mean price paid | loss rate on filled (TAPE) | 95% CI | P&L/contract | **$/close at 20** | t | vs TAKE $/close | t(diff) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| TAKE | 420 | 420 | 100.0% | 94.35c | 0.95% | [0.26, 2.42] | +4.37c | **$+0.9504** | +9.19 | — | — |
| REST-1 | 420 | 280 | 66.7% | 94.90c | 1.43% | [0.39, 3.62] | +3.67c | **$+0.5317** | +7.93 | $-0.4187 | -4.62 |
| REST-AT | 420 | 296 | 70.5% | 95.07c | 1.35% | [0.37, 3.42] | +3.58c | **$+0.5440** | +8.31 | $-0.4064 | -4.51 |
| REST-BID | 420 | 197 | 46.9% | 92.88c | 2.03% | [0.56, 5.12] | +5.09c | **$+0.5507** | +7.56 | $-0.3997 | -4.17 |

### R = 10s, fill rule `opt`  (420 entries over 249 closes)

| rule | entries | fills | fill rate | mean price paid | loss rate on filled (TAPE) | 95% CI | P&L/contract | **$/close at 20** | t | vs TAKE $/close | t(diff) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| TAKE | 420 | 420 | 100.0% | 94.35c | 0.95% | [0.26, 2.42] | +4.37c | **$+0.9504** | +9.19 | — | — |
| REST-1 | 420 | 297 | 70.7% | 94.86c | 1.35% | [0.37, 3.41] | +3.79c | **$+0.5712** | +8.40 | $-0.3792 | -4.20 |
| REST-AT | 420 | 314 | 74.8% | 95.06c | 1.27% | [0.35, 3.23] | +3.67c | **$+0.5820** | +8.79 | $-0.3683 | -4.11 |
| REST-BID | 420 | 218 | 51.9% | 92.94c | 1.83% | [0.50, 4.63] | +5.23c | **$+0.6042** | +8.24 | $-0.3462 | -3.58 |

**Adverse selection: who fills us?** 416 entries went on to WIN, 4 went on to LOSE. If resting were harmless the two fill rates would match.

| rule | R | fill rate on WINNERS | fill rate on LOSERS | loser fills / winner fills |
|---|---|---|---|---|
| REST-1 | 2s | 57.2% (238/416) | 75.0% (3/4) | **1.31x** |
| REST-1 | 5s | 66.3% (276/416) | 100.0% (4/4) | **1.51x** |
| REST-1 | 10s | 70.4% (293/416) | 100.0% (4/4) | **1.42x** |
| REST-AT | 2s | 60.6% (252/416) | 75.0% (3/4) | **1.24x** |
| REST-AT | 5s | 70.2% (292/416) | 100.0% (4/4) | **1.42x** |
| REST-AT | 10s | 74.5% (310/416) | 100.0% (4/4) | **1.34x** |
| REST-BID | 2s | 38.2% (159/416) | 75.0% (3/4) | **1.96x** |
| REST-BID | 5s | 46.4% (193/416) | 100.0% (4/4) | **2.16x** |
| REST-BID | 10s | 51.4% (214/416) | 100.0% (4/4) | **1.94x** |

**Cancel on alarm** (`opt`): pull the bid at the first second AFTER entry at which belief in our side falls below the threshold, effective one second later.

* belief fell below 90% after entry on **15 of 420** entries (3.6%), 4 of them on the 4 that lost; median 5s after entry.
* belief fell below 70% after entry on **7 of 420** entries (1.7%), 4 of them on the 4 that lost; median 6s after entry.

| rule | R | cancel below | fills | fills on LOSERS | $/close at 20 | t | vs TAKE | t(diff) |
|---|---|---|---|---|---|---|---|---|
| REST-1 | 2s | never | 241 | 3 of 4 | $+0.5049 | +9.63 | $-0.4454 | -4.48 |
| REST-1 | 2s | 90% | 241 | 3 of 4 | $+0.5049 | +9.63 | $-0.4454 | -4.48 |
| REST-1 | 2s | 70% | 241 | 3 of 4 | $+0.5049 | +9.63 | $-0.4454 | -4.48 |
| REST-1 | 5s | never | 280 | 4 of 4 | $+0.5317 | +7.93 | $-0.4187 | -4.62 |
| REST-1 | 5s | 90% | 280 | 4 of 4 | $+0.5317 | +7.93 | $-0.4187 | -4.62 |
| REST-1 | 5s | 70% | 280 | 4 of 4 | $+0.5317 | +7.93 | $-0.4187 | -4.62 |
| REST-1 | 10s | never | 297 | 4 of 4 | $+0.5712 | +8.40 | $-0.3792 | -4.20 |
| REST-1 | 10s | 90% | 297 | 4 of 4 | $+0.5712 | +8.40 | $-0.3792 | -4.20 |
| REST-1 | 10s | 70% | 297 | 4 of 4 | $+0.5712 | +8.40 | $-0.3792 | -4.20 |
| REST-BID | 2s | never | 162 | 3 of 4 | $+0.4923 | +8.35 | $-0.4581 | -4.44 |
| REST-BID | 2s | 90% | 162 | 3 of 4 | $+0.4923 | +8.35 | $-0.4581 | -4.44 |
| REST-BID | 2s | 70% | 162 | 3 of 4 | $+0.4923 | +8.35 | $-0.4581 | -4.44 |
| REST-BID | 5s | never | 197 | 4 of 4 | $+0.5507 | +7.56 | $-0.3997 | -4.17 |
| REST-BID | 5s | 90% | 197 | 4 of 4 | $+0.5507 | +7.56 | $-0.3997 | -4.17 |
| REST-BID | 5s | 70% | 197 | 4 of 4 | $+0.5507 | +7.56 | $-0.3997 | -4.17 |
| REST-BID | 10s | never | 218 | 4 of 4 | $+0.6042 | +8.24 | $-0.3462 | -3.58 |
| REST-BID | 10s | 90% | 218 | 4 of 4 | $+0.6042 | +8.24 | $-0.3462 | -3.58 |
| REST-BID | 10s | 70% | 218 | 4 of 4 | $+0.6042 | +8.24 | $-0.3462 | -3.58 |

## HOLDOUT — the last 4 days (2026-09-08 04:45Z .. 2026-09-12 04:45Z)


**MDE, stated before the estimates** (`opt`, n=162 closes, 80% power at alpha 0.05, paired per close). Below this line, 'no advantage' means 'no power', not 'no effect':

| comparison | R | sd of per-close difference | MDE ($/close at 20) |
|---|---|---|---|
| REST-1 - TAKE | 2s | $1.0476 | **$0.2306** |
| REST-AT - TAKE | 2s | $0.6567 | **$0.1445** |
| REST-BID - TAKE | 2s | $1.8937 | **$0.4168** |
| REST-1 - TAKE | 5s | $0.9288 | **$0.2044** |
| REST-AT - TAKE | 5s | $0.4361 | **$0.0960** |
| REST-BID - TAKE | 5s | $1.8959 | **$0.4173** |
| REST-1 - TAKE | 10s | $0.9306 | **$0.2048** |
| REST-AT - TAKE | 10s | $0.4360 | **$0.0960** |
| REST-BID - TAKE | 10s | $1.1023 | **$0.2426** |

### R = 2s, fill rule `opt`  (274 entries over 162 closes)

| rule | entries | fills | fill rate | mean price paid | loss rate on filled (TAPE) | 95% CI | P&L/contract | **$/close at 20** | t | vs TAKE $/close | t(diff) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| TAKE | 274 | 274 | 100.0% | 93.61c | 3.65% | [1.76, 6.61] | +2.39c | **$+0.6299** | +2.67 | — | — |
| REST-1 | 274 | 157 | 57.3% | 93.14c | 5.73% | [2.65, 10.60] | +1.13c | **$+0.3003** | +1.28 | $-0.3296 | -4.00 |
| REST-AT | 274 | 167 | 60.9% | 93.17c | 5.39% | [2.49, 9.98] | +1.44c | **$+0.3864** | +1.59 | $-0.2435 | -4.72 |
| REST-BID | 274 | 100 | 36.5% | 90.90c | 8.00% | [3.52, 15.16] | +1.10c | **$+0.2773** | +1.43 | $-0.3526 | -2.37 |

### R = 5s, fill rule `opt`  (274 entries over 162 closes)

| rule | entries | fills | fill rate | mean price paid | loss rate on filled (TAPE) | 95% CI | P&L/contract | **$/close at 20** | t | vs TAKE $/close | t(diff) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| TAKE | 274 | 274 | 100.0% | 93.61c | 3.65% | [1.76, 6.61] | +2.39c | **$+0.6299** | +2.67 | — | — |
| REST-1 | 274 | 188 | 68.6% | 93.07c | 5.32% | [2.58, 9.56] | +1.61c | **$+0.3634** | +1.56 | $-0.2665 | -3.65 |
| REST-AT | 274 | 197 | 71.9% | 93.11c | 5.08% | [2.46, 9.14] | +1.82c | **$+0.4422** | +1.84 | $-0.1877 | -5.48 |
| REST-BID | 274 | 120 | 43.8% | 90.57c | 7.50% | [3.49, 13.76] | +1.93c | **$+0.3395** | +1.74 | $-0.2904 | -1.95 |

### R = 10s, fill rule `opt`  (274 entries over 162 closes)

| rule | entries | fills | fill rate | mean price paid | loss rate on filled (TAPE) | 95% CI | P&L/contract | **$/close at 20** | t | vs TAKE $/close | t(diff) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| TAKE | 274 | 274 | 100.0% | 93.61c | 3.65% | [1.76, 6.61] | +2.39c | **$+0.6299** | +2.67 | — | — |
| REST-1 | 274 | 197 | 71.9% | 93.26c | 5.08% | [2.46, 9.14] | +1.67c | **$+0.3824** | +1.65 | $-0.2475 | -3.39 |
| REST-AT | 274 | 206 | 75.2% | 93.29c | 4.85% | [2.35, 8.75] | +1.86c | **$+0.4604** | +1.92 | $-0.1694 | -4.95 |
| REST-BID | 274 | 128 | 46.7% | 90.25c | 7.81% | [3.81, 13.90] | +1.94c | **$+0.2646** | +1.14 | $-0.3653 | -4.22 |

**Adverse selection: who fills us?** 264 entries went on to WIN, 10 went on to LOSE. If resting were harmless the two fill rates would match.

| rule | R | fill rate on WINNERS | fill rate on LOSERS | loser fills / winner fills |
|---|---|---|---|---|
| REST-1 | 2s | 56.1% (148/264) | 90.0% (9/10) | **1.61x** |
| REST-1 | 5s | 67.4% (178/264) | 100.0% (10/10) | **1.48x** |
| REST-1 | 10s | 70.8% (187/264) | 100.0% (10/10) | **1.41x** |
| REST-AT | 2s | 59.8% (158/264) | 90.0% (9/10) | **1.50x** |
| REST-AT | 5s | 70.8% (187/264) | 100.0% (10/10) | **1.41x** |
| REST-AT | 10s | 74.2% (196/264) | 100.0% (10/10) | **1.35x** |
| REST-BID | 2s | 34.8% (92/264) | 80.0% (8/10) | **2.30x** |
| REST-BID | 5s | 42.0% (111/264) | 90.0% (9/10) | **2.14x** |
| REST-BID | 10s | 44.7% (118/264) | 100.0% (10/10) | **2.24x** |

**Cancel on alarm** (`opt`): pull the bid at the first second AFTER entry at which belief in our side falls below the threshold, effective one second later.

* belief fell below 90% after entry on **17 of 274** entries (6.2%), 10 of them on the 10 that lost; median 3s after entry.
* belief fell below 70% after entry on **15 of 274** entries (5.5%), 10 of them on the 10 that lost; median 3s after entry.

| rule | R | cancel below | fills | fills on LOSERS | $/close at 20 | t | vs TAKE | t(diff) |
|---|---|---|---|---|---|---|---|---|
| REST-1 | 2s | never | 157 | 9 of 10 | $+0.3003 | +1.28 | $-0.3296 | -4.00 |
| REST-1 | 2s | 90% | 157 | 9 of 10 | $+0.3003 | +1.28 | $-0.3296 | -4.00 |
| REST-1 | 2s | 70% | 157 | 9 of 10 | $+0.3003 | +1.28 | $-0.3296 | -4.00 |
| REST-1 | 5s | never | 188 | 10 of 10 | $+0.3634 | +1.56 | $-0.2665 | -3.65 |
| REST-1 | 5s | 90% | 187 | 9 of 10 | $+0.3918 | +1.69 | $-0.2381 | -2.98 |
| REST-1 | 5s | 70% | 187 | 9 of 10 | $+0.3918 | +1.69 | $-0.2381 | -2.98 |
| REST-1 | 10s | never | 197 | 10 of 10 | $+0.3824 | +1.65 | $-0.2475 | -3.39 |
| REST-1 | 10s | 90% | 196 | 9 of 10 | $+0.4108 | +1.77 | $-0.2191 | -2.74 |
| REST-1 | 10s | 70% | 196 | 9 of 10 | $+0.4108 | +1.77 | $-0.2191 | -2.74 |
| REST-BID | 2s | never | 100 | 8 of 10 | $+0.2773 | +1.43 | $-0.3526 | -2.37 |
| REST-BID | 2s | 90% | 100 | 8 of 10 | $+0.2773 | +1.43 | $-0.3526 | -2.37 |
| REST-BID | 2s | 70% | 100 | 8 of 10 | $+0.2773 | +1.43 | $-0.3526 | -2.37 |
| REST-BID | 5s | never | 120 | 9 of 10 | $+0.3395 | +1.74 | $-0.2904 | -1.95 |
| REST-BID | 5s | 90% | 119 | 8 of 10 | $+0.3654 | +1.89 | $-0.2645 | -1.77 |
| REST-BID | 5s | 70% | 119 | 8 of 10 | $+0.3654 | +1.89 | $-0.2645 | -1.77 |
| REST-BID | 10s | never | 128 | 10 of 10 | $+0.2646 | +1.14 | $-0.3653 | -4.22 |
| REST-BID | 10s | 90% | 127 | 9 of 10 | $+0.2905 | +1.26 | $-0.3394 | -3.85 |
| REST-BID | 10s | 70% | 127 | 9 of 10 | $+0.2905 | +1.26 | $-0.3394 | -3.85 |

## Fill-definition sensitivity (ENTRY B (first tradeable second, ask <= ceiling), R=5s)

The three definitions bracket queue position, which prints cannot see: `opt` assumes we are at the front of the queue, `size` needs enough contracts through our price to fill 20, `pess` needs the level cleared outright.

### R = 5s, fill rule `opt`  (694 entries over 411 closes)

| rule | entries | fills | fill rate | mean price paid | loss rate on filled (TAPE) | 95% CI | P&L/contract | **$/close at 20** | t | vs TAKE $/close | t(diff) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| TAKE | 694 | 694 | 100.0% | 94.05c | 2.02% | [1.11, 3.36] | +3.59c | **$+0.8241** | +7.34 | — | — |
| REST-1 | 694 | 468 | 67.4% | 94.16c | 2.99% | [1.64, 4.97] | +2.85c | **$+0.4653** | +4.65 | $-0.3587 | -5.79 |
| REST-AT | 694 | 493 | 71.0% | 94.29c | 2.84% | [1.56, 4.72] | +2.87c | **$+0.5039** | +4.91 | $-0.3202 | -5.68 |
| REST-BID | 694 | 317 | 45.7% | 92.01c | 4.10% | [2.20, 6.91] | +3.89c | **$+0.4675** | +5.28 | $-0.3566 | -4.32 |

### R = 5s, fill rule `size`  (694 entries over 411 closes)

| rule | entries | fills | fill rate | mean price paid | loss rate on filled (TAPE) | 95% CI | P&L/contract | **$/close at 20** | t | vs TAKE $/close | t(diff) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| TAKE | 694 | 694 | 100.0% | 94.05c | 2.02% | [1.11, 3.36] | +3.59c | **$+0.8241** | +7.34 | — | — |
| REST-1 | 694 | 408 | 58.8% | 94.06c | 3.19% | [1.71, 5.39] | +2.75c | **$+0.4209** | +4.88 | $-0.4031 | -5.05 |
| REST-AT | 694 | 430 | 62.0% | 94.30c | 3.26% | [1.79, 5.40] | +2.44c | **$+0.3780** | +3.85 | $-0.4460 | -7.09 |
| REST-BID | 694 | 282 | 40.6% | 91.87c | 4.61% | [2.48, 7.75] | +3.52c | **$+0.3947** | +4.52 | $-0.4293 | -5.15 |

### R = 5s, fill rule `pess`  (694 entries over 411 closes)

| rule | entries | fills | fill rate | mean price paid | loss rate on filled (TAPE) | 95% CI | P&L/contract | **$/close at 20** | t | vs TAKE $/close | t(diff) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| TAKE | 694 | 694 | 100.0% | 94.05c | 2.02% | [1.11, 3.36] | +3.59c | **$+0.8241** | +7.34 | — | — |
| REST-1 | 694 | 434 | 62.5% | 94.22c | 3.00% | [1.60, 5.07] | +2.79c | **$+0.4611** | +5.27 | $-0.3629 | -4.60 |
| REST-AT | 694 | 468 | 67.4% | 94.35c | 2.99% | [1.64, 4.97] | +2.66c | **$+0.4410** | +4.43 | $-0.3831 | -6.22 |
| REST-BID | 694 | 257 | 37.0% | 91.74c | 5.06% | [2.72, 8.49] | +3.20c | **$+0.3540** | +4.04 | $-0.4701 | -5.73 |

## The live guards (ENTRY B (first tradeable second, ask <= ceiling))


### With the live guards on (ceiling 98.0c, refuse a discount >= 15c), R=5s, `opt`

| rule | entries allowed | fills | $/close at 20 | t | vs TAKE | t(diff) |
|---|---|---|---|---|---|---|
| TAKE | 654 | 654 | $+0.5336 | +6.20 | — | — |
| REST-1 | 647 | 439 | $+0.3187 | +3.72 | $-0.2150 | -8.86 |
| REST-AT | 654 | 468 | $+0.3580 | +4.15 | $-0.1756 | -8.54 |
| REST-BID | 613 | 286 | $+0.3291 | +4.72 | $-0.2046 | -3.41 |

---

# Touch versus sweep at our gate

* **142,320 taker groups** (same ticker, same `ts_ms` -- the true instant, per CLAUDE.md) buying the near-certain side inside 3-30s of close on the markets we entered, 30,127,527 contracts in all.
* **79.9% of groups trade at ONE price level** -- they take the touch and stop.
* **55.9% of all contracts** transact at the group's best (touch) level; the remaining 44.1% are swept deeper.
* legs per group: mean 2.44, median 1, max 224; price levels per group mean 1.40.

**THE CAVEAT THIS PRODUCES, and it stands whichever way the number fell.** The level a resting bid would sit at is the level most takers hit first, so we would be joining a queue at that level behind resting size that prints cannot see. Every `opt` fill rate above therefore OVERSTATES what we would actually receive; `pess` is the floor. Nothing in the trade tape can close that gap -- only resting a real order can.
