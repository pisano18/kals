# Overnight review — 2026-09-14, ~04:00–05:00 ET

Written by a session with no memory of the 09-13/14 work, deliberately, per the
operator's instruction to re-rank by importance rather than by momentum.

**Nothing that trades was changed.** The live bot, both collectors and all
seven paper arms were left alone. Only documentation was edited.

---

## 0. Nothing broke

- Live bot pid 1409808 alive, last record 08:05Z. Bank **$341.27** (a new
  high-water), SIZE **58**.
- `kalshi_collector.py` pid 123296 and `crypto_feeds.py` pid 124060 alive since
  Sep 9, 42.9 MB and 25.5 MB. No process above 69 MB.
- Disk **38 GB** free (guard 6). RAM 4.65 GB free of 15.79.
- `python research/versioncheck.py` → clean.
- `python research/pinhealth.py` → 22 self-test checks OK, **no decay pattern**,
  most recent day +3.81c/contract against a +1.53c kill line.

---

## 1a. RETRACTION, 05:30 ET — A SIXTH HEDGE FIRED AND REVERSED SECTION 1

**Section 1 below is superseded. Do not act on it.** It is kept unedited so the
reversal is visible.

At **05:30 ET (09:29:49Z)**, minutes after section 1 was written, the live bot
hedged `KXBTC15M-26SEP140530-30`. It is the largest hedge ever placed and it
was **right**.

| | |
|---|---|
| entry | NO, **60 contracts** @ 97.2c, edge only 1.948c, tau 13 |
| belief 2 seconds later | **0.214** — a collapse from certainty in two seconds |
| hedge | YES, 60 @ 58c (ask was 61c) |
| result | **YES** — our entry lost |
| entry leg settled | **−$58.43** |
| hedge leg settled | **+$24.18** (`pnl_c 2417.68`, matches the hand calculation exactly) |
| close net | **−$34.26** instead of **−$58.43** |

**The hedge saved $24.18.** Belief was 0.214, so at the 0.10 trigger section 1
recommends, **this hedge would not have fired** and the close would have cost
$24.18 more.

### The running total, all six live hedges

| trigger | net effect over all 6 events |
|---|---|
| **0.80 — what is live now** | **+$15.10** |
| 0.10 — what section 1 recommended | +$0.05 |
| 0.30 | +$24.23 |

**The sign flipped when n went from 5 to 6.** Section 1 stated that n=5 was the
honest sample and then led with a recommendation anyway. That was the error,
and it is the exact failure this repo's own rules exist to prevent. **The live
0.80 setting is now net positive and should not be changed.**

The 0.30 column is NOT a recommendation. It is a threshold picked after seeing
which six events worked, on six events.

**What does survive is a mechanism, not a threshold.** The two hedges that paid
had hard, fast collapses — belief **0.02** and **0.214**. The four that cost
money had mild ones — **0.525, 0.643, 0.664, 0.887**. Still six events.

**Section 1's SECOND recommendation is unaffected and still stands.** An EV
gate on the hedge (`h < 1 − belief`, which `hedge_edge_c()` already computes and
its own docstring calls "DIAGNOSTIC, not a gate") would have **allowed** this
hedge (`edge_c +20.56`) and blocked only the two that fired at negative edge —
BTC 11:00 (`−2.72`) and ZEC 20:00 (`−32.52`). Blocking both is +$2.80 − $2.13 =
**+$0.67**, and it never touches either hedge that mattered.

**Every rail behaved correctly.** Bank $354.89 → $320.64, size re-sized 60 → 54
within the same second (AMENDMENT 30 working as designed), drawdown 9.6%
against the 20% brake.

---

## 1. THE HEDGE HAS COST REAL MONEY — from our own fills, not the tape

Every live hedge since the feature went in, reconstructed from dollars paid in
versus dollars paid out. (The log's own `pnl_c` rows under-count the entry leg
after a partial hedge fill, so they were not used.)

| close | our side | belief at alarm | hedge paid | our side won? | hedge effect |
|---|---|---|---|---|---|
| SOL 09-12 06:00 | NO 1 @ 5.2c | 0.020 | 94.9c | no | **+$0.05** |
| BTC 09-12 11:00 | NO 20 @ 90.0c | 0.887 | 14c | **yes** | **−$2.80** |
| ETH 09-12 11:15 | NO 20 @ 98.0c | 0.664 | 26/27c | **yes** | **−$5.26** |
| ZEC 09-12 20:00 | YES 11 @ 96.2c | 0.525 | 80/81c | no | **+$2.13** |
| BNB 09-13 12:30 | NO 32 @ 92.3c | 0.643 | 10c | **yes** | **−$3.20** |
| ETH 09-12 05:45 | YES 1 @ 0.3c | 0.000 | never filled | no | $0 |
| | | | | | **NET −$9.08** |

Three of five hedges turned a winning close into a losing one.

**Independently confirmed by a second ledger.** `pinhealth.py` reports all-in
P&L of **+$184.40**; counting entry legs only gives **+$196.26**. The gap,
**−$11.86**, is the hedge plus its fees. Two ledgers built from different
fields agree the hedge is the difference, and agree on the sign.

At a **0.10** trigger only the SOL hedge (belief 0.02) fires. We keep $2.80 +
$5.26 + $3.20 and give back the $2.13 ZEC rescue: **+$9.13 better on live
money.**

This agrees in sign with `results/RESULTS_flip.md` (594 tape entries: 0.80 is
in the negative band, 0.10 is +0.49c/contract). The table above is live fills,
so it is not a tape claim about our losses.

### Why lowering the trigger does not remove tail protection

In `RESULTS_flip.md` the rescues are **25 of 29 losing entries at every
threshold from 0.90 down to 0.10 — identical**. What changes is the false
alarms: 38 at 0.90, 1 at 0.10. Cutting the trigger removes false alarms and
keeps every rescue.

### A second, separable defect: the hedge has no EV gate

Hedging is profitable only when the hedge ask `h` is below the model's own
probability that we are wrong: **`h < 1 − belief`**. `pinrun.hedge_edge_c()`
computes exactly that and its docstring says **"DIAGNOSTIC, not a gate"**. The
only gate, `hedge_ask_ok()`, asks merely that the leg cost under $1.00.

So two hedges fired at their own negative edge — BTC at `edge_c = −2.72`, ZEC
at `−32.52` and `−33.52`. The entry path has an EV gate; the hedge path does
not.

Note the honest complication: the two hedges that were **+EV by the model's own
number** (ETH `+5.58`, BNB `+25.68`) still lost money, because the belief
collapse was a false alarm. Across all five events the mean belief at the alarm
was ~0.55 and our side won **4 of 5**. The collapse signal is mis-calibrated in
the direction that costs money.

**Sample: 5 hedge events.** That is the honest n. But the alarm fires on ~2% of
legs, and **zero hedges have fired in any paper arm** (checked, all seven), so
the `--hedge-belief 0.10` arm has produced no information and will not produce
any quickly. Waiting for n=30 means paying the premium for months.

---

## 2. THE UNCOMFORTABLE ONE: the edge rests on one day, and we keep resetting the clock

Per-close live P&L, 244 closes, entry legs only:

| | |
|---|---|
| total | **+$196.26** |
| winning closes | 236 (+$338.15) |
| losing closes | **8** (−$141.88) |
| mean per close | +$0.804, bootstrap 95% **[+0.159, +1.331]** |
| median close | +$0.78 |
| **worst close** | **−$52.60** |

One average loss (−$17.7) erases 12 winning closes. The worst erased 37.

**Drop 2026-09-13 and the whole thing stops being distinguishable from zero.**

| population | closes | total | mean/close | 95% |
|---|---|---|---|---|
| all live | 244 | +$196.26 | +$0.804 | [+0.159, +1.331] |
| **minus 09-13** | 200 | +$63.10 | +$0.315 | **[−0.437, +0.900]** |

09-13 is **68% of every dollar the strategy has ever made**, on one day of
seven.

**It is NOT a jackpot, and that matters.** Within 09-13: 44 closes, best single
close only +$15.55, top three 23.7% of the day, and the **worst close of the
day was +$0.42 — no loss at all**. It is the least concentrated day in the
sample. The difference between a good day and a flat one is entirely whether a
−$12 to −$52 loss lands.

**And a loss-free stretch that long is ordinary luck.** All 8 losses fall on
Sep 09–12. Sep 13–14 is 58 closes with none. At the 3.28% base rate the chance
of 58 clean closes is **14%** — unremarkable.

### The current configuration looks better, and has much less evidence

The 15c dump guard (AMENDMENT 10) went live 2026-09-11 08:29 ET. Verified: of
257 signals after it, **zero** carry a discount over 15c; all 11 such fills
predate it, and four of them are named losses in its own self-test. The guard
works.

| since the dump guard | |
|---|---|
| 182 fills, 4,958 contracts | **+$189.58 = +3.824c/contract** |
| 134 closes, 3 losing | **2.24%** |
| worst close | **−$17.94** |
| mean per close | +$1.415, 95% **[+0.837, +1.947]** |
| **minus 09-13** | 90 closes, +$56.42, 95% **[−0.095, +1.226]** |

So the current version is confidently positive on 134 closes — but 70% of that
is still one day, and without it the interval touches zero.

**The re-ranking this implies.** The bot has changed roughly fifteen times in
six days, and every change restarts the evidence clock. Of this week's
amendments — 23, 24, 26, 28, 29, 31, 35, 36 — **every single one makes the bot
buy MORE or buy sooner. Not one changes which trades we refuse.** The only
loss-side mechanisms are the drawdown brake (a stop, not a filter) and the
hedge, which section 1 shows is currently negative.

Break-even is an 8.55–11.36% loss rate and we run at 2.24–4.10%. That margin is
the entire thesis and it rests on **8 events**.

---

## 3. CAPACITY IS NOT THE CEILING — BANK IS

`results/pinlevels_rows.jsonl`, 13,984 gate-passing candidate moments over 738
closes. Walk each ask ladder buying up to N contracts, never above the 98c
ceiling. (The script self-tests against a planted ladder with a known answer
and against a flat ladder that must show zero impact.) This asks only what the
market offered, which is what the tape is valid for.

| order size | filled in full | mean price | mean edge | vs a 50-lot |
|---|---|---|---|---|
| 25 | 98.0% | 95.06c | 4.458c | |
| **50** | **97.1%** | **95.10c** | **4.422c** | **1.00x** |
| 125 | 92.5% | 95.21c | 4.322c | 2.40x |
| **250** | **85.9%** | **95.31c** | **4.221c** | **4.51x** |
| 500 | 75.3% | 95.45c | 4.092c | 8.16x |

**Buying five times as much moves the average price 0.21c and costs 4.5% of the
edge.** Price impact is nearly nothing out to 250, and 86% of moments still
fill a full 250-lot.

This retires the "capacity wall" worry in its current form and moves the
binding constraint to **SIZE = bank / 5.88, capped at 250**. At $341 that is
58. Reaching the 250 cap needs a bank near **$1,470**.

Caveat that travels with it: at five times the size a loss is five times too,
and nothing above 55 contracts has ever lost. See section 4.

---

## 4. THE TWO BRAKES CONTRADICT EACH OTHER

- `BANK_BRAKE = 3.0` sizes so that the **worst single close costs 32% of the
  bank** — that is the stated design in its own comment, chosen 2026-09-13.
- `MAX_DRAWDOWN = 0.20` **halts the bot at 20% below the high-water mark** —
  chosen 2026-09-14, the day after.

At today's numbers: bank $341.27, SIZE 58, `MAX_PER_CLOSE` 2, so the worst
close is `2 x 58 x 0.98 = $113.68` = **33% of bank**, against a drawdown limit
of **$68.25**. **One maximally bad close is 1.67x the amount that stops the
bot.** The sizer is permitted to build a position that ends the run in a single
event.

A consistent pair would be `BANK_BRAKE 5.0` (worst close 20%) or
`MAX_DRAWDOWN 0.35`. This is a decision, not a bug — but the two numbers were
set a day apart against different pictures and have never been read together.

**Related:** `--loss-abort` auto-sets to **−$232** at this bank, which is 68%
of it, and `max_run_stake` is **$358 — more than the bank**. `VERSIONS.md`
says "all three brakes now run together, answering different questions". In
practice only the drawdown brake can fire first; the other two are 3.4x looser.

---

## 5. THE DEPTH GATE AND THE ORDER SIZER DISAGREE — same class as AMENDMENT 35

`pinrun.py:4772` refuses a market when `take_n < max(MIN_LEVEL, MIN_FILL_FRAC x
SIZE)`, where `take_n = min(SIZE, touch size)` — **the touch only**.

The AMENDMENT 35 sweep that reads the whole ladder lives at `pinrun.py:5099`,
**inside the order path, after that refusal has already `continue`d**.

So a market showing 3 contracts at the touch with 1,600 sitting one tick down —
exactly the 02:00 SOL shape that motivated A35 — is still **refused outright**
at SIZE 58, because `0.10 x 58 = 5.8 > 3`. A35 fixed how much we ask for; it
did not fix the gate that decides whether to ask at all.

Measured, from live gate-audit records: **63 depth-floor refusals, 7 of which
(11%) passed edge, EV and the ceiling** — real chances dropped on a number that
no longer describes what the bot can fill.

### Gate ordering also mis-attributes

Evaluation order is `no_offer → confidence → depth_floor → edge_floor →
dump_guard → improve_by → rebuy_band → price_ceiling → ev_floor`.

`depth_floor` runs **before** `edge_floor`, so a thin book at a price we would
never have taken is charged to depth. **89% of depth-floor refusals would have
failed a later gate anyway.** `pinattrib.py`'s "binding-by-construction" claim
is correct as written, but the depth column reads far more important than it is.

---

## 6. SMALLER THINGS, MEASURED

**Where the money comes from, by price paid** (320 live entry fills):

| price | fills | contracts | net | c/contract | losers |
|---|---|---|---|---|---|
| under 90c | 30 | 887 | +$75.95 | +8.56c | 4 |
| 90–94c | 41 | 1,015 | +$74.91 | +7.38c | 0 |
| **94–96c** | **56** | **1,148** | **−$4.38** | **−0.38c** | **3** |
| 96–97.5c | 79 | 1,561 | +$17.96 | +1.15c | 2 |
| 97.5c+ | 114 | 2,583 | +$31.82 | +1.23c | 1 |

Cheap fills are 26% of contracts and 77% of the profit. The 94–96c hole was
logged in `CURRENT_STATE.md` at 49 fills as "no power"; it is now 56 fills and
1,148 contracts and has **not improved with more data**. Still not evidence —
but it has stopped looking like noise and deserves a pre-registered bar.

**Quote age has produced zero information.** `level_age_ms` is recorded on 64
live fills across all four age buckets and **every bucket has zero losses**,
because no loss has occurred since logging began. `CURRENT_STATE.md` calls it
"the best lead open"; it is currently the lead with the least data.

**By time-to-close** (tau at send): 3–7s +7.52c (0 losses), 8–14s +6.09c (1),
**15–21s −5.38c (4 losses in 34 fills)**, 22–30s +2.55c (5). The hole is
non-monotonic and confined to fills under 96c; n=15 in the cells that matter.
Not actionable — noted so it is not re-discovered as new.

**The `edge >= 25c` trap is already fixed.** 3 of 5 such fills lost, but all
five predate the dump guard, which now refuses them. No action needed; this is
recorded so the next session does not propose the guard that already exists.

**Resting limit orders — the repo already contains the argument against them in
this window.** `RESULTS_select.md` settled that the last-30-seconds
counterparty is informed by 26x. A resting bid in that window is volunteering
to be the informed party's counterparty. The encouraging maker result
(`RESULTS_informed.md`, +0.48c/fill) was measured at the touch across the whole
day — a different population from the endgame. Do not read one as support for
the other. The fee saved by resting is 0.33c at 95c, about 9% of a 3.8c edge,
so the fee is not the prize either.

---

## 7. HOUSEKEEPING — what changed, and what deliberately did not

**Changed (documentation only):**

1. `CLAUDE.md` — the "State as of 2026-09-06" block and "What this project has
   never done" removed and **moved verbatim to `PROJECT_HISTORY.md`**. They
   described `pin` as a pre-live research result, listed four next actions all
   since closed, and ended with *"No order has ever been placed. No money has
   been deployed."* `CLAUDE.md` is loaded on **every turn**, so a false
   statement there is read as current by every fresh session.
2. `CLAUDE.md` — the opening "What this is" paragraph said "No money has been
   deployed". Replaced with a statement that real money is deployed and a
   pointer to `CURRENT_STATE.md`.
3. `CLAUDE.md` — hard rule 1 still read "Never place, amend, or cancel an
   order" with its narrowing amendment 500 lines below. A pointer now sits on
   the rule itself.
4. `.gitignore` — `results/dashboard.html` (840 KB, rebuilt every two minutes).

Net: `CLAUDE.md` 28,996 → 27,208 bytes, saved on every turn, nothing deleted.

**Deliberately NOT cleaned, and why:**

- The six `kals-report-*.zip` (3.2 MB) — snapshots of past report state; they
  may be the only copy of a claim's context.
- 18 zero-byte files in `results/` — empty, so they cost nothing, and their
  existence records that a job ran.
- `research/__pycache__` (5.2 MB) — regenerable, but seven `pinrun` processes
  including the live bot are importing from it. Not worth 5 MB.
- `research/_*.py` scratch verifiers — cost nothing per turn and may back a
  past claim.
- `pintool.py` (pid 517404) has been idle since Sep 11 at 8.8 MB. It is the old
  tool the operator dislikes. Left running; 8.8 MB is not a reason to touch a
  process.

Disk is 38 GB free. There is no cleanup here worth any risk.

---

## 8. PAPER ARMS at 04:05 ET — all 2–3 hours old, all too short except one

| arm | settles | net | losses |
|---|---|---|---|
| `--tau-max 55` (early entry) | 18 | **−$12.92** | 1 |
| `--tau-max 55 --pin 0.990` | 19 | +$10.74 | 0 |
| `--hedge-belief 0.10` | 9 | +$6.11 | 0 |
| `--pick first` (A24 control) | 20 | +$14.11 | 0 |
| paper twin of live | 7 | +$3.55 | 0 |
| `--sigma-ruler maxdown --pin 0.990` | 20 | +$32.16 | 0 |

Early entry keeps losing, consistent with the handoff. **Every other arm is
uninformative at this length**, and the hedge arm is structurally uninformative
— zero hedges have fired in any paper arm, ever.


---

# PART 2 — THE HUNT FOR A LOSS FILTER, 2026-09-14 afternoon/evening ET

The operator, verbatim: *"Do whatever it takes to find something real here that
reduces our losses without also taking our winners with it."* This is what was
tried, in order, and what survived. **Nothing entry-side survived a fair test.
One structural fact did, and it points at a paper arm, not a gate.**

## What was tried and killed (each by holdout or placebo)

| candidate | looked like | on data it had not seen | verdict |
|---|---|---|---|
| cushion under 2 one-second moves | +$47.67 saved | **reverses** (+5.36c → −8.51c) | dead |
| touch under 15 contracts (best single rule of ~300) | +$65.91 | **costs $23.27**; 16% of coin-flip shuffles match | dead |
| touch < 21.5 AND book age < 6 ms (best pair of ~45,000) | +$79.63 | **costs $5.13** | dead |
| hedge trigger 0.60 instead of 0.80 | +0.5c/contract unclustered | **+0.12c clustered by market** (25 losing markets) | wash |
| hedge trigger 0.90 instead of 0.80 | +0.26c/contract clustered | live 7 events say −$2.97 | wash |
| rate-of-change hedge trigger | plausible | false alarms are cliffs too (73% same-second vs 56%) | dead before build |
| quote resting ≥ 3 s (RESULTS_select's lead) | tape: 0 failures in 302 | live: fresh offers earn **2.7x per contract** and carried 1 of 2 logged losses | trades profit for safety ~1:1 |

`research/pinsep.py` is the reusable search, with holdout and placebo built in.
Re-run it at 40–50 losses; at 12 every answer is an accident.

## The one structural fact that IS real

**When a trade loses, the collapse begins within seconds of our entry.**

| population | seconds from entry to belief crossing 0.90 |
|---|---|
| tape, 25 losing markets | median **2 s**; 64% within 3 s; 80% within 5 s |
| ours, 10 losing markets | 1, 2, 2, 3, 4, 6, 7, 11, 19, never — median **~4 s**; 40% within 3 s |

That is not "we held it and it drifted." It is "we bought and it jumped." The
mechanism is already settled in `RESULTS_select.md`: the seller is informed by
26x. The timing signature says *how* — the cheap offer we take is the leading
edge of the jump the seller already sees.

## What that implies, and why it is not a gate yet

A **confirmation wait** — see the signal, wait k seconds, buy only if belief is
still over 0.90 and the offer is still there. On the cache:

| wait | of the tape's losers we would still buy | of its winners we would still buy |
|---|---|---|
| 2 s | 36% | 34% |
| 3 s | **3%** | 31% |
| 5 s | **0%** | 36% |

It removes essentially every loss. **It also removes two thirds of the
winners**, because most offers are gone within seconds (42% survive 1 s, 31%
survive 3 s). And the survivors are the resting quotes — makers, not dumpers —
which on our own 93 logged fills earn **1.16c per contract against 3.18c** for
the fresh ones. Fresh offers are both the danger and most of the profit.

Rough dollars on our history: a 5 s wait keeps ~36% of winners (~$122) and
none of the entry-leg losses (−$260 avoided) versus the actual ~+$78 on entry
legs — **better by ~$40 on a third of the volume, before the hedge**, and that
assumes the surviving winners are average, which they are not. Honest range:
modest positive to break-even in dollars, far better per contract, far less
volume. **It conflicts directly with the operator's stated #1 priority of
buying everything available.**

**Only a paper arm can price this.** The cache cannot say what the surviving
offers' edge is or what our fill rate becomes. Flag design, not built:
`--confirm k` — hold a signal k seconds, re-check belief ≥ 0.90 and the offer,
then send. Variant worth running alongside: confirm only when the quote is
under 1 s old, buy resting quotes at once.

## Hedge: the level is a wash, the SPEED is worth ~17c per rescued contract

Clustered by market (1,192 markets, 25 losers): trigger 0.60 → +0.84c, 0.70 →
+0.69c, 0.80 → +0.72c, 0.90 → +0.98c per contract. Three sources disagree on
direction inside a 0.3c band. **Leave it at 0.80.**

What moves is the price: hedging at the 0.90 crossing instead of the 0.70
crossing gets a mean **16.7c better hedge price** on the 25 losers (10 of 25
gain 14–70c, 14 gain nothing, 1 loses 9c). Every second of delay is paid for.
A rate trigger cannot buy that second (false alarms are cliffs too). The one
untested lever with a mechanism is **cross-coin warning** — twelve indices
move together at rho ~0.8 and a BTC collapse may precede an alt's by a second
or two. `leadlag.py` measured contract-follows-index, never coin-follows-coin.
Unbuilt.

## The un-hedgeable loss

BNB 2026-09-10 01:30: belief never left 1.000 and it lost. No warning, no
hedge possible. One of ten. The floor on any loss-side rule.


---

# PART 3 — WHICH EARNS MOST, ACCOUNTING FOR LOSSES  (2026-09-14 evening ET)

The operator's question: *"buy then hedge harder once we know, or wait then
buy and lose 1/3, or a third option, or a dynamic blend?"* Three tools built
and run: `pinstrat.py` (every strategy on the same markets), the crossing-
instant test (collapse vs wobble), and `pinxlead.py` (cross-coin warning).

## 1. Buy-then-hedge beats wait-then-buy by about 2.5x — `research/pinstrat.py`

Same 227 markets (192 closes, 9 losers) for every strategy, one row per
market, bootstrap by close, 60/40 holdout on close time. **Per 100 markets
SEEN**, so a wait is charged for the trades it never makes, at our loss rate:

| strategy | trades | losses | per trade | **per 100 seen** | first 60% | last 40% |
|---|---|---|---|---|---|---|
| buy now, no hedge | 227 | 9 | +1.91c | +190c | +2.46c | **−0.25c** |
| buy now, hedge 0.90 | 227 | 13 | +2.44c | +243c | +2.43c | +1.62c |
| **buy now, hedge 0.80 — LIVE** | 227 | 11 | +2.75c | **+273c** | +2.68c | +1.98c |
| buy now, hedge 0.70 | 227 | 8 | +3.09c | +307c | +3.14c | +2.13c |
| wait 3 s, no hedge | **69** | **0** | +3.37c | +103c | +3.64c | +2.91c |
| wait 3 s, then hedge | 69 | 3 | +2.26c | +69c | | |
| wait 5 s, no hedge | 69 | 0 | +3.35c | +102c | +3.34c | +3.36c |
| wait 5 s, then hedge | 69 | 3 | +2.23c | +68c | | |

Waiting has the best per-trade number and zero losses, and **throws away 70%
of trades to get it**. Both halves of the holdout agree on the ranking. **No
hedge at all goes negative on the last 40%** — the hedge is what keeps the
recent stretch positive.

The 0.70-vs-0.80 gap (+34c per 100) **reverses sign** on the full 1,192-market
cut (+0.69c vs +0.72c per contract). Inside noise. Trigger stays at 0.80.

**The confirmation-wait paper arm is therefore NOT worth building.** The tape
already says it loses in total, and the live fill data says its survivors —
the resting quotes — earn a third of what the fresh ones do.

## 2. Collapse vs wobble CAN be told apart at the instant the trigger fires — by depth, not speed

47 markets crossed 0.80 (one row per market). 31 went on under 0.60 (23 lost,
8 won — real collapses). 16 bottomed in 0.60–0.80 (2 lost, 14 won — wobbles).

| at the first tick through 0.80 | real collapse | wobble |
|---|---|---|
| belief lands at (median) | **0.13** (p25 0.01, p75 0.44) | **0.70** (p25 0.64, p75 0.76) |
| other side's ask (median) | 62c | 36c |

**Rule: at the 0.80 crossing, hedge only if belief has already fallen under
0.60.** Keeps 27 of 31 real (87%), fires on **0 of 16** wobbles. The
other-side ask separates less well (30c: 23 of 31 vs 8 of 16).

**Why it is a refinement, not a breakthrough.** Cutting 16 wobbles saves ~40c
each; missing 4 real collapses costs ~40c each; on the two cuts of the tape
the net is inside noise and reverses. It is a cleaner mechanism than the level
trigger — the size of the first crack is the signal — and worth a paper flag
(`--hedge-first-tick 0.60`) when there is nothing better to run. Not now.

## 3. Cross-coin warning: DEAD — `research/pinxlead.py`

2,007 close windows, 1,834 scored per coin, index alone. Self-test recovers a
planted 2-second lag and passes a null.

**Every coin moves with BTC in the SAME second** (r 0.25–0.59 at lag 0). BTC
leads by one second at r 0.06–0.11 — statistically real on 1,834 closes,
practically nothing. Before an alt JUMPS (>3 sd in one second), BTC's move in
the prior 3 s is +0.3 to +0.6 sd against a calm baseline of 0.55; the share
with BTC already ≥1 sd the same way is **15–23% vs a 15–17% baseline**. XRP is
the only coin with any daylight (23% vs 16%). **The alt's jump is news to BTC
too.** There is no warning to be had from the leader.

## 4. The answers, in the operator's own framing

- *How often does a winner wobble and recover?* 2.9% dip under 0.90; 1.9%
  under 0.80; **0.7% under 0.60**. Losers: 100% / 100% / 92%.
- *Sell and hedge?* The same action: buying the other side IS selling ours,
  and `RESULTS_exit` showed selling outright gets a worse price.
- *Wait then buy, or buy then hedge?* **Buy then hedge, by 2.5x in total.**
- *Dynamic blend?* The data supports exactly one dynamic element — the depth
  of the first crack — and it is worth roughly nothing over the level trigger.
- *Cross-coin?* Measured. Dead.

**What is running is, on every test here, the best of the options measured.**


---

# PART 4 — THE BTC 05:30 LOSS, SECOND BY SECOND  (2026-09-14 late evening ET)

Official CF Benchmarks print against Bitstamp's BTC/USD book mid (189 ticks in
20 s — the raw exchange feeds ARE sub-second). Strike 77,695.85. We bought NO
at 09:29:47–48Z, needing the 60-second average to land BELOW it.

| time Z | Bitstamp mid vs strike | official print vs strike |
|---|---|---|
| :42 | −13.68 | −10.24 |
| :45 | −13.68 | −8.67 |
| **:46.0** | −2.10 | **+9.86 ← official first above** |
| :46.5 | +3.79 ← Bitstamp first above | |
| **:47** (we buy) | +3.79 | **+12.25** |
| :48 | +24.07 | +34.57 |
| :49 | +43.13 | +52.14 |
| :53 | +52.35 | +63.72 |

**Three things this settles.**

1. **The feed was not the problem.** The official print led Bitstamp by half a
   second — the composite index is faster than any one exchange. The
   information was on our screen a full second before we bought. The
   "sub-second feed" hypothesis from earlier today is withdrawn.

2. **The model saw the jump and priced it as survivable — correctly, IF it had
   stopped.** Spot at +12 with 47 prints locked well below still averages under
   the strike. Belief 99.99% NO was the right number for a one-off move.

3. **It lost because the move kept going**: +18.5, +22.3, +17.6, +17.6 in four
   consecutive seconds. A 4.5-sigma jump was the START of a 15-sigma run. The
   model treats each second as an independent draw around the new level.
   That is the assumption to test, and it is testable on 18,000 closes.

So the question is no longer "can we see it sooner" — we saw it. It is
"after a jump, does the index keep going, and by how much." If it does, the
fix is conditional, not global: widen the model only in the seconds after a
jump, which is exactly what CURRENT_STATE's dead "scale sigma by k" never did.


---

# PART 5 — WHAT WAS MISSING: JUMPS CONTINUE  (2026-09-15 ~01:30 ET)

The operator: *"I know there's something missing and this isn't the absolute
max peak performance of the bot, help figure out what it is!"*

## The chain that found it

1. Does the order BOOK crack before our belief? **Yes, on 12 of 12 tape
   losers, by ~1.6 s.** But as a replacement trigger it false-alarms 3x more
   (9.3% vs 3.4% of winners) and nets **-1.22c/contract**. Blending it with
   belief: at the second the book cracks, belief is still 0.998 on losers AND
   winners — nothing to blend. Dead.
2. Is it our feed, then? `index_age_s` is `now - print_second`; our fastest
   receipt is 0.11 s, so the 0.39 s median is mostly waiting for the NEXT
   print. And on the BTC 05:30 loss the **official print led Bitstamp by
   half a second** — the composite is faster than any exchange. **The
   information was on screen a full second before we bought.** Feed
   hypothesis withdrawn.
3. So why did the model buy? It saw spot +12 over the strike and said 99.99%
   — correctly for a one-off move: 47 locked prints below still average under
   the strike. **It lost because the move continued: +18, +22, +18, +18 in
   four seconds.** The model treats each second as an independent draw.
4. **Test that on 17,811 jumps.** After a >3 sd second, the next 5 s: p90
   +4.2 sd (calm +2.1), p95 +6.7 (+3.2), p99 **+15.4** (+7.0). Share followed
   by another >=5 sd: **7.9% vs 2.2% calm vs 1.3% Gaussian.** The median is
   ~0. The tail is 3.6–6x. **The model's independence assumption fails
   exactly after a jump, exactly in the tail, which is exactly where every
   loss lives.**
5. **Then on our own fills** (sign bug caught and fixed — first run had the
   dangerous bucket as our safest): >=3 sd against us in the prior 3 s —
   7 fills, **28.6% lost** vs 2.5%, -$65.67. Gate cost $4.92 for $70.59.
   Both holdout halves positive. Threshold and lookback fixed before the
   fill test.

## What shipped

AMENDMENT 40, `--jump-gate`, **default OFF**, paper arm running (pid
1646604). Self-tests plant the BTC 05:30 moves (refused), HYPE's +0.3 sd
(passes), both sides' sign, a 2.9 sd near-miss, missing data, and the null.
One of my own tests asserted the RUNNING flag instead of the default and made
the flag-on boot refuse — mistake #7 from the handoff, an hour after citing
it — caught by the boot check, fixed.

## What it is and is not

It is the first entry rule today with a mechanism measured independently of
the fills that motivated it, that survives a holdout, and that costs under
$5. It catches the *jump* losses (2 of 12, 27% of loss dollars). It does not
catch the *no-warning* kind. It is 7 fills; the bootstrap interval touches
zero; it earns its keep on the mechanism, not the count.

**The deeper version** is a model change: widen sigma for a few seconds after
a jump by the measured tail ratio. That refuses the same entries by lowering
confidence AND fires the hedge sooner on a position held through a jump.
`CURRENT_STATE`'s "scale sigma by k" was global and dead; this is conditional
on the one state where the model is provably wrong. Not built. Needs its own
self-tests and a paper arm.


---

# PART 6 — DEPLOYED AND ARMED  (2026-09-14 ~22:00 ET)

The operator: *"If it earns more money, do it! But perhaps also have a paper
trade version going for each and both that check if these implementations
weren't in (the version running today) would we earn more. That's the realest
check if it's good. We'll compare all in 3 days."*

## Live

**v-jump.** `--jump-gate` on. Restarted clean 21:39 ET, pid 1647780, both
recorders confirmed writing. `versioncheck` clean.

## The comparison, all auto-sized off the same bank

| arm | pid | jump gate | widening | started |
|---|---|---|---|---|
| **LIVE** | 1647780 | **on** | off | 21:39 ET |
| CONTROL (today's version, unchanged) | 1649636 | off | off | 21:39 ET |
| WIDEN | 1650424 | off | **on** | 21:42 ET |
| BOTH | 1643080 | **on** | **on** | 21:42 ET |
| GATE twin (paper copy of live) | 1646604 | on | off | 21:28 ET |

**Compare on 2026-09-17**: net per contract and losing closes, per arm. The
CONTROL arm is the one that answers the operator's question directly —
"would today's version have earned more without it."

## AMENDMENT 41 shipped, flag OFF

The model version: for 5 s after any >=3 sd second, sigma x2.0 at both the
entry and the hedge. Mechanism self-test on the BTC 05:30 shape: confidence
in NO falls from 0.9986 to 0.9327 — that trade is not made. Both `fair()`
sites carry it, so a held position is priced by the model that bought it.

## Read on the 17th

`python research/pinhedgelive.py` for the hedge; per-arm net from the
`settled` records in each arm's `results/pinrun-paper-*.jsonl`. The four
arms started within 30 minutes of each other on the same bank, so a straight
comparison of net and losing closes is fair. Three days at ~40 closes a day
is ~120 closes each — enough to see a gap in losses, not enough to prove a
gap in cents per contract unless it is large.


---

# PART 7 — WHAT TODAY WOULD HAVE LOOKED LIKE  (2026-09-14 ~22:30 ET)

The operator: *"What would've happened if it ran today vs what did happen?"*
`research/pinreplay41.py` — every one of today's 59 live fills reproduced
through pinrun's own `fair()` and `IndexWS`, with the index object rebuilt
per second so it can never see the future (self-tested). Reproduction check:
replayed belief vs the belief the bot logged — median difference 0.00000,
max 0.00164 over 59 fills.

| | fills refused | of which lost | winners given up | net for the day |
|---|---|---|---|---|
| **as it happened** | — | — | — | **+$22.84** (2 losses) |
| **A40 jump gate (live now)** | 1 | 1 (BTC 05:30, −$58.43) | 0 | **+$81.28** (+$58.43) |
| **A41 widening (paper)** | 10* | 1 (the same BTC) | 9 worth $23.07 | **+$54.89** (+$32.05) |
| both | 10* | 1 | 9 | +$54.89 |

\* the replay lists 11; one (DOGE 15:14, belief 0.9942 both ways) sits
inside the replay's own precision of the 99.5% gate and is not a widening
effect. The honest widening count is 10.

**The hedge.** On the one loss that would still have been made (HYPE 16:00),
the widened model fires the hedge at the **same second** (19 s left) — HYPE's
collapse was not preceded by a jump (+0.3 sd), so the widening never
engaged. **Zero** new false hedges on today's winners.

**What this says.** Today the gate was strictly better: it refused exactly
the loss and nothing else. The widening refused the same loss and nine
winners worth $23 — the symmetric-widening cost, stated in advance: moderate
jumps that did not continue. One day. The paper arms will say whether that
ratio holds; today it was $58 saved for $23 given up, which is still +$32.

**What it cannot say.** Nothing about trades either rule would have ADDED
(there are none — both only refuse or fire earlier), and nothing about the
hedge PRICE at an earlier second, which needs the book at that second.


---

# PART 8 — ALL FOUR VERSIONS ON TODAY, ALL-IN  (2026-09-15 ~03:00 ET)

Operator: *"calculate what would've happened today if you had this latest
version and the gate running simultaneously today."*

`research/pinreplay41.py`, rebuilt so it calls **pinrun's own
`widen_factor()`** instead of its own copy — the first version reimplemented
the rule symmetrically, so AMENDMENT 42 would have been invisible to it and
the replay would have scored the old rule while reporting the new one. It now
also carries the **hedge legs** of each market, so every row is all-in and
comparable to the $76 the operator sees.

61 live fills, 2026-09-14 ET. Reproduction check against the beliefs the bot
logged at the time: median difference 0.00000, max 0.00164.

| scenario | refused | losses | entries | hedges | **ALL-IN** | vs actual |
|---|---|---|---|---|---|---|
| as it happened | 0 | 2 | +$27.82 | +$53.47 | **+$81.30** | — |
| **A40 jump gate (LIVE now)** | 1 | 1 | +$86.26 | +$29.30 | **+$115.55** | **+$34.26** |
| A41/42 widening | 10 | 1 | +$59.99 | +$29.30 | +$89.28 | +$7.99 |
| **BOTH together** | 10 | 1 | +$59.99 | +$29.30 | **+$89.28** | **+$7.99** |

**BOTH is identical to widening alone.** The widening already refuses the one
trade the gate refuses, plus nine more — so on today's data the gate adds
nothing on top of the widening, and the widening *subtracts* from the gate.
The gate is the precise instrument; the widening is the blunt one.

**Note on the count:** one of the ten (DOGE 15:14) shows belief 0.9942 at a
multiplier of x1.0 — it sits a hair under the 99.5% gate in the replay's own
arithmetic and is not a widening effect. The honest widening cost today is
**8 winners worth ~$22**, plus the BTC loss it correctly refused.

**The asymmetry helped, a little.** At the symmetric 2.0 the widening netted
+$54.89 on entries; at 1.5 for favourable jumps, +$59.99. The nine winners are
still refused — their beliefs fall from ~0.998 to ~0.97, still under the
99.5% gate even at the gentler multiplier. So AMENDMENT 42 is directionally
right and was not enough to save them.

**The hedge.** On HYPE — the loss neither rule prevents — the widened model
fires at the **same second**, because no jump preceded that collapse. Zero
new false hedges on today's winners.

**One day, one jump-loss.** The gate looks perfect because today contained
exactly one trade of the kind it exists to refuse. The arms decide.

## The seven arms now running

| arm | gate | widen | favour | log |
|---|---|---|---|---|
| **LIVE** | on | — | — | `pinrun-live-20260915T013908Z` |
| GATE twin | on | — | — | `...paper-20260915T012843Z` |
| CONTROL | off | — | — | `...paper-20260915T013933Z` |
| ~~WIDEN sym~~ | off | on | 2.0 | stopped 02:47Z |
| ~~BOTH sym~~ | on | on | 2.0 | stopped 02:47Z |
| **WIDEN** | off | on | **1.5** | `...paper-20260915T024715Z` |
| **BOTH** | on | on | **1.5** | `...paper-20260915T024718Z` |

Compare 2026-09-17 on all-in net and losing closes.
