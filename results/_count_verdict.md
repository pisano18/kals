## 0. VERDICT — COUNT is a LIQUIDITY problem, and no threshold reaches it

*Hand-written on top of the generated tables below; every number in it is
reproduced by `research/pincount.py --report` and reconciled by hand in this
section. Nothing here is deployed and nothing here should be.*

**The answer to the question.** On the 333 model-certain closes in this 9-day
window where we traded nothing, the reason is not our rules and it is not
size. Per close, taking the cheapest offer that ever appeared on the model's
side at any second in tau [3,30]: **219 of 333 (65.8%) never saw anything
below 98.7c — the price where pinrun's own EV gate stops, not where the
ceiling stops; 73 of 333 (21.9%) never saw an ask on our side at all; and only
39 of 333 (11.7%) sit inside the reach of any price or size threshold.**
Underneath that, the mechanism is visible in the census and it is structural:
of 167,458 fresh model-certain market-seconds, **140,990 (84.2%) carry no ask
on the winning side, and 140,989 of those 140,990 carry one on the LOSING
side.** The book is not dead; it is one-sided against us. To buy a near-
certainty somebody has to bid the side that is about to lose, and when the
outcome becomes obvious nobody does. That is a capacity limit of the product
and no parameter of ours touches it. It also explains why being pickier has
failed three times: the offers are not there to be picky about.

**The single best change, and it should be measured, not deployed:
`PRICE_CEILING` 0.980 → 0.987.** It is the only lever whose sign is positive on
both components of the split. It buys **35 new closes (+$9.72) and 37 extra
fills on closes we already trade (+$7.36) = +$17.08 over 697 closes =
+$0.0245/close at size 20**, lifting the share of certain closes traded from
52.1% to 57.1%. 0.987 is the exact maximum: `ceiling 0.99` and `ceiling 0.995`
produce byte-identical rows, because pinrun's EV gate refuses everything
dearer — EV(0.987) = +0.31c clears the 0.30c floor and EV(0.988) = +0.21c does
not, hand-reconciled in the self-test. So "raise the ceiling to 0.99" is
arithmetically a no-op, and the brief's 0.99 and 0.995 were never available.

**And here is its cost, which is larger than the gain and is the reason this
is a proposal and not a change.** The +$17.08 is +0.9% of nothing much —
$1.90/day at size 20 against the base's $15.16/day — and it does not clear its
own bar: **t = +0.8 against a paired MDE of $0.0575/close.** Worse, the two
dollar columns disagree: tape says +$0.0245/close, `ev` (pinrun's own
`expected_value`) says **−$0.018/close**, and by this file's stated rule a
lever whose two columns disagree is not established. The reason they disagree
is the whole risk. **All 123 of the fills this lever adds are dearer than 98c,
one of them lost on the tape, and the break-even loss rate on that population
is between 1% and 2%:**

| loss rate on the 123 dear fills | the lever is worth |
|---|---|
| 0.8% (what the tape realised) | **+$12.98** |
| 1.0% | +$9.49 |
| **2.0%** | **−$14.00** |
| 3.4% (the only LIVE rate we have, on closes) | ≈ −$37.50 at 3.0% |

The tape's rate on that population is structurally 31× too optimistic
(CLAUDE.md 2026-09-10 rule 5: 0.11% on the tape against 3.4% live, intervals
that do not overlap), and **we have never bought above 98c, so there is no
live rate at these prices at all.** Narrower still: +$15.21 of the +$17.08
comes from 64 fills in the 98.5–98.7c bucket that went 64–0 on the tape, and a
single adverse fill in that bucket costs 19 × 0.9867 = **$18.75** — more than
the entire measured gain. **So the proposal is: run it live at one contract
above 98c and count, exactly as the hedge plant was run. Do not turn it on at
size 20 from this file.**

**The tau kill is CONFIRMED, on the rebuilt replay, at today's gate — both
halves of "dearer AND less accurate".** Less accurate: the model's flip rate
per certain MARKET is 0.202% [0.104, 0.352] at tau 21–30, **0.439% [0.284,
0.648] at 31–45 (2.2×) and 0.748% [0.533, 1.021] at 46–60 (3.7×)** — the same
wall AMENDMENT 4 found at the old PIN 0.98 gate, lower in level because the
gate is tighter, identical in shape. Dearer: the mean price paid rises
monotonically with the tau of the fill, 93.63c → 94.49c → 94.92c → 95.27c →
96.33c. And the P&L follows: TAU_MAX 60 earns **+$111.46 on 175 new closes and
loses $316.32 on the closes we already traded**, because an early dear fill
burns a `MAX_PER_CLOSE` slot and raises the `IMPROVE_BY` bar against the better
offer still to come — net −$0.2939/close. **TAU_MAX 35 is the one row positive
on both components (+$13.82 new, +$29.20 shared, +$0.0617/close) and it is
still inside its MDE of $0.1013 at t = +1.2; it is the only tau extension worth
re-asking on more tape, and the question it re-asks is where the wall starts,
not whether there is one.**

**The floor lever is the only thing in this report that clears its own MDE, and
it is negative.** `MIN_FILL_FRAC` 0.5 → 0.25 buys 5 new closes worth +$0.69 and
loses **$18.48** on the closes we already trade: **−$0.0255/close, t = −5.3
against an MDE of $0.0095.** Taking a scrap fill early spends a slot and raises
the improve bar against the better price seconds later — precisely what
pinrun's AMENDMENT 6 comment says, now re-measured on the rebuilt replay. Size
is not the constraint anyway: `too_shallow` is **2.0% of the certain markets on
silent closes and 4 of the 333 silent closes**. The authoritative SIZE sweep is
`research/pinlevels.py` → `results/RESULTS_levels.md`; nothing here should be
quoted against it.

**What would have to be true for any of this to be wrong, and what was
checked.** (1) *The census could be a statement about BTC rather than the
product* — it was, in the first version: counting BOOK STATES, a market whose
book changes ~7× a second contributed 204 rows where a thin altcoin
contributed 28, and the census read "an ask exists 84% of the time" when the
per-second truth is 15.8%. Aggregating to one row per (market, second) fixed
it and a planted self-test now fails if it regresses. (2) *The replay could be
missing the offers we actually hit* — it is the rebuilt `pinsim` (per-event
decisions, seq-ordered snapshots with real `_rx_ms`), which reproduces 9 of 9
of our real losses under the live gate; the decomposition calls its
`close_slot_ok`/`close_slot_book` rather than copying the rails. (3) *The
holdout could be refuting these levers* — **it is not; it has no power.** The
base gate itself earns $0.2722/close in the train half and $0.0174 in the
holdout while trading the same share of closes (51.8% vs 52.6%) at the same
mean price (95.61c vs 95.42c); the per-close sd rises to $3.4589 and the
holdout MDEs land at 5–20× the base's own holdout level. Every "fails in the
holdout" row is **no power, not no effect**. (4) *Counts could be inflated by a
perfect-book assumption* — this window carries **3,012 `_seq_gap` flags over
675.5M delta messages (16.7/hour)**, and coverage is 99.4% of the band's
market-seconds, with the missing seconds absent rather than stale, so every
count here is a lower bound.

**The bottom line for the operator.** The biggest number on the board was
"half the certain closes trade nothing". It is real — this file reproduces it
independently of the maker study at **52.2% traded against that study's 51.8%**
— but **88% of it is a book that has no seller on the winning side, and that is
not a number we can move with a constant.** The reachable remainder is worth
about five percentage points of count and roughly $1.90/day at size 20, with a
sign that depends on a loss rate the tape is forbidden to supply. **COUNT is
now measured and it is not where the next dollar is.** What is left in this
direction is not a threshold but an instrument: the offers DO exist for a
median 1.4 s, and whether we win the race for them is still the project's
largest unmeasured risk.
