# PRE-REGISTRATION 2 — the first live rebate run

**Written 2026-09-07 08:20Z. Nothing has been placed.**
Supersedes `PREREG_gold.md` in PURPOSE but does not replace it — that file
stays untouched so the record shows what was predicted before the filing was
read.

---

## 0. WHY THIS IS A DIFFERENT TEST

`PREREG_gold.md` was designed to discriminate between two readings of the
scoring rule. **That question was then settled for free** by reading the
operative CFTC filing of 2026-07-15: the walk stops once cumulative qualifying
size reaches Target Size, and only qualifying bids are scored.

So the rule question is closed. **Four questions remain that no document and no
amount of tape can answer**, and only a live quote can:

1. **Has a LIP credit ever landed in this account?** Nobody in this project has
   ever seen one. There is no API line item; it is visible only as a balance
   residual, which reconciles to $0.0000 over the account's whole life — so a
   credit of $1.00 or more would be unambiguous.
2. **Is the account actually eligible?** No endpoint exposes it. A credit
   proves it; nothing else does.
3. **Does our modelled share survive contact with the book?** Every share
   figure is computed from a book we are not standing in. The credit measures
   the real one.
4. **Do competitors react?** Fully logged so it can be reviewed afterwards.

---

## 1. THE DESIGN

- **Venue:** the thinnest qualifying commodity family at run time (measured
  live; NatGas and Copper were thinnest overnight, but family quality moves
  hour to hour — Copper's denominator went 337 -> 1,132 in fifty minutes).
- **Size:** 20 contracts each side, quoted at the Reference Price, re-pegged
  by atomic amend.
- **Duration:** 4 consecutive windows (~1 hour), hard wall-clock stop 45 min.
- **Capital:** ~$19.10 deployed of $65.18. Cap $21.00, now genuinely enforced
  (it counts filled inventory, which it did not before).
- **Abort:** −$15.00 mark-to-market, checked every 6 cycles (~18 s).

## 2. THE PREDICTION — fixed now

| quantity | prediction |
|---|---|
| share of a side at S=20 | **5.9%** (measured, our size inside the walk) |
| gross rebate per window | **$1.18** |
| windows clearing the $1.00 floor | **2 to 4 of 4** |
| **total credit, readable 48 h later** | **$2.00 – $4.72** |
| inventory P&L over 4 windows | **−$3 to +$3**, expected ≈ 0 |
| fills | `is_taker: false`, `fee_cost: 0.000000` |
| `balance_dollars` while resting | **will not move** — it is gross of reserves |
| credit before 48 h | **none**; a $0.00 reading earlier means nothing |

**Hand-check:** 20/(323+20) = 5.83%; $20 × 0.0583 = $1.17/window; 4 windows
× $1.17 × ~0.75 qualifying = **$3.50**.

## 3. DECISION RULE — fixed now

- **Credit $2.00–$5.00** → the model is calibrated. Scale to $160 and 50
  contracts, which the measured curve says earns $2.63/window.
- **Credit $0.01–$1.99** → we cleared the floor in fewer windows than modelled.
  The share model is optimistic. Re-fit before scaling; do NOT scale.
- **Credit exactly $0.00** → three causes are indistinguishable and must be
  separated before another dollar is spent: (a) not eligible, (b) share below
  the floor in every window, (c) credits do not reach this account at all.
  The run log records our own share per second, so (b) is checkable from it.
- **Nothing after 72 h** → the readout has failed. That is a finding about the
  programme, not the strategy.
- **Inventory loss reaches −$15** → the run aborts itself, regardless of rebate.

**Confound I cannot remove:** ineligibility and a sub-floor share both produce
$0.00. The log distinguishes them only if our measured share is comfortably
above the floor throughout.

## 4. WHAT IT CANNOT SETTLE

- The daily figures. Four windows is one hour, not 89.
- Competitor response over days. One hour cannot see someone who re-sizes
  tomorrow.
- Behaviour at the 4pm ET crowd peak, where the Coin Race denominator is
  **25× thicker** (6,330 vs 250) and our share would fall to ~0.31%.
- Anything at a size above 20.

## 5. WHAT WOULD MAKE ME WRONG

If the credit lands **materially above $4.72**, the share model is
understated and every capacity figure in this project is too low — the same
class of error made twice tonight in both directions. That would be good news
and therefore gets checked hardest.
