# PRE-REGISTRATION — the gold cutoff test

**Written 2026-09-07 06:45Z. NO ORDER FOR THIS TEST HAS BEEN PLACED.**
This file exists so the result cannot be rationalised afterwards. Every number
below is fixed now.

---

## 1. THE QUESTION

Does Kalshi's liquidity scoring **stop counting once cumulative resting size
reaches the full Target Size (300)**, or does it score every level in the book?

This is not a refinement. Measured over 127,000 book-seconds it changes our
share by **1.42x–3.61x**, and it changes which family is best.

Two outside reviewers were asked to adjudicate and both declared it settled in
favour of "no cutoff". **Neither addressed the measurement**, and one quoted
filing text saying the walk *"continues until the full Target Size is reached,
at which point the procedure stops"* immediately before concluding there is no
cutoff. The help centre contains BOTH steps and they are not alternatives:

> *"Walking down from the best bid, [the Reference Price] is the first price
> level at which cumulative resting size reaches **one fifth** of the Target
> Size"* — sets the reference
>
> *"Kalshi scores every resting order **that helps reach the Target Size** on
> its side"* — restricts what is scored at all

---

## 2. WHY GOLD, AND WHY THIS IS A BINARY

The $1.00-per-programme minimum payout turns a continuous disagreement into a
clean binary, and **only in gold do the two answers straddle it**:

| | our share/side | reward/window | clears $1.00? |
|---|---|---|---|
| **no cutoff** (what this project has assumed) | 1.97% | $0.39 | **NO -> pays $0.00** |
| **cutoff at Target Size** | 7.12% | $1.42 | **YES -> pays $1.42** |

Measured denominators, median over 27,178 side-snapshots: **1,856** without the
cutoff, **300** with it. Gold's qualification rate is 98.5%.

Other families do not discriminate: natgas pays under both readings, so its
result would be uninformative.

---

## 3. THE PREDICTION — fixed before any order

**Design:** `KXGOLD15M`, **8 consecutive 15-minute windows**, **20 contracts on
each side**, quoted at the Reference Price and re-pegged as it moves,
`post_only` throughout.

| quantity | if NO cutoff | if CUTOFF |
|---|---|---|
| rebate per window | $0.39 gross -> **$0.00 paid** | $1.42 gross -> **$1.42 paid** |
| windows clearing the $1.00 floor | **0 of 8** | **6-8 of 8** |
| **total credit after 48 h** | **$0.00** | **$8.50 – $11.40** |

**Inventory P&L is a separate, noisy term and is NOT the measurement.**
Expected +$0.44/window (measured), sd ~$3/window, worst gold window on tape
**−$4.40**. Over 8 windows: expect **+$3.50**, with a realistic band of
**[−$12, +$12]**.

**Also predicted (so a surprise is visible):**
- `balance_dollars` will NOT move while orders rest — it is gross of reserves.
- Fills will show `is_taker: false` and `fee_cost: 0.000000`.
- No credit will appear before **48 hours**. A $0.00 reading before then is
  meaningless and must not be interpreted.

---

## 4. THE DECISION RULE — fixed before any order

- **Credit ≥ $6** → **the cutoff is real.** Every share figure in this project
  is understated 1.4–3.6×; gold is a good venue rather than a worthless one;
  re-run the family ranking before deploying further.
- **Credit exactly $0.00** → **no cutoff.** The published tables stand, gold
  stays dead, and natural gas is the only viable family at this bankroll.
- **Credit between $0.01 and $5.99** → neither model is right. **STOP** and
  re-fit the share function against the realised number; do not scale.
- **No credit visible after 72 h** → the readout itself has failed. That is a
  finding about the programme, not about the rule. **STOP** spending on rebates.

**What would make me wrong regardless of the result:** if the account turns out
to be ineligible, a $0.00 reading is indistinguishable from "no cutoff". This
is the one confound I cannot remove and it is recorded here in advance.

---

## 5. LIMITS — hard, and enforced in code

| | |
|---|---|
| max deployed collateral, cumulative | **$21.00** (of $65.19) |
| max per order | 20 contracts, $20.00 collateral |
| abort if realised loss reaches | **−$15.00** |
| abort if any cancel cannot be verified | immediately |
| every order | `post_only` — cannot cross, cannot pay a taker fee |
| untouched | ~$44 of the account |

`ordercli.py` production ceilings are being raised from
(count 5, notional $2.50, deployed $2.50) to (count 20, notional $20, deployed
$21) **for this test**. That is a deliberate change, recorded here because a
limit must never move quietly.

---

## 6. WHAT THIS TEST CANNOT SETTLE

- Whether our *realised* share matches the modelled share — only the binary
  above, because the floor censors everything else.
- Eligibility (see §4).
- Anything about weekday behaviour at scale; this is 2 hours on a holiday
  Monday.
- Whether competitors react to a persistent new participant. Two hours cannot
  see a response that operates over days.
