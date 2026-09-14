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
