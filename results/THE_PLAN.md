# THE PLAN — what to do with the $20, and what it would take to do better

**Written 2026-09-07 06:05Z. Nothing in it has been executed.**
Money spent by this project to date: **about four cents.**

---

## 0. THE SHORT VERSION

**Do not deploy the rebate strategy yet, and do not fund it yet.** One thing
must be settled first, it costs **under $1 of refundable collateral**, and
until it is settled half the numbers in this project are wrong by 1.44–1.76×
in an unknown direction.

Then, if it resolves the way we expect: **$60 total**, not $150 and not $500.
The marginal value of a dollar measurably dies at $60.

---

## 1. WHAT IS ALREADY SETTLED (do not re-litigate these)

| question | answer | how |
|---|---|---|
| Is the programme alive? | **Yes.** 3,056 future windows scheduled; latest paid `end_date` minutes old | 178,340 programmes paginated |
| Do our five families pay? | **Yes, 94.8–98.1%** | per-family, n=650–2,428 each |
| How long until we can read a credit? | **>48 h** (Coin Race 24–48 h). Nothing pays before 48 h; after it, 99–100% | paid-rate by age bucket |
| Do makers pay a fee? | **No.** `is_taker: false`, `fee_cost: 0.000000` | a real resting fill, non-vacuous |
| Are our resting orders visible to the scoring feed? | **Yes** — 1.00 contract at an empty level appeared in the public book in 20 s | live probe |
| Do resting orders reserve cash? | **Yes, cumulatively.** `balance_dollars` is GROSS and never shows it | straddle test, arithmetic closes exactly |
| Is there a "2×" in the scoring? | **No.** The denominator is 2.0 per snapshot, so it is the average of the two sides | algebra + Kalshi's worked example |
| Qualification rate | **93–99%** (not the 26% two internal files claimed — that was a book-reconstruction bug) | direct count on tape |
| Is there margin/leverage? | **None exists on Kalshi.** Max loss is capped at deposited cash | fully cash-collateralised |

---

## 2. STEP ONE — SETTLE THE RULE FORK. Under $1. Do this before anything else.

### The problem
Two incompatible versions of the Reference Price are on record:

- **Rule A (help centre):** walk down from the best price until cumulative
  resting size reaches **one fifth** of Target Size (60 contracts). Orders below
  it score `0.5^ticks` — **always something**.
- **Rule B (CFTC filing):** the Reference Price **is the best bid**, and the
  walk runs to the **full** Target Size (300). Orders behind that depth are
  **not qualifying at all — exactly zero**.

On the same tape they differ by **1.44–1.76× at S=20, in every window, in all
five families.** Every number this project has produced assumes **Rule A**.

If Rule B is live: all shares are 1.44–1.76× understated, the family ranking
inverts (gold becomes the best venue rather than the worst), and the
"stand one tick behind the touch" idea scores **zero**, not 0.5×.

### The test
Kalshi renders a per-order **qualification indicator** — a dot plus an
"efficiency percentage" — on resting orders in reward markets. This project has
never looked at it. It is a live, per-second, un-floored readout of exactly the
quantity every model here estimates.

**Rest two 1-contract orders in one commodity market and photograph the
indicator on each:**

| order | placement | Rule A predicts | Rule B predicts |
|---|---|---|---|
| **CONTROL** | 1 tick *better* than the best bid | qualifying, **100%** | qualifying, **100%** |
| **PROBE** | **3 ticks behind** the best bid | qualifying, **12.5%** (= 0.5³) | **gray / non-qualifying, 0%** |

The control is a positive control: it must read 100% under *both* rules, so a
gray control means the instrument is broken rather than telling us about the
rule.

**Cost:** collateral only — roughly **$0.50–$1.00 total for both orders**,
returned in full on cancel. Both are `post_only` and behind the touch, so
neither can cross. Realistic risk if one fills: under $1.

### Decision rule, fixed in advance
- **control 100% + probe 12.5%** → Rule A. Every model stands. Proceed to §3.
- **control 100% + probe gray/0%** → Rule B. **STOP.** Three measurement jobs
  must be re-run before any money moves; the current family ranking is void.
- **control 100% + probe some other %** → read the exponent straight off it
  (50% ⇒ reference one tick lower than modelled; 25% ⇒ two). **Best outcome** —
  it hands us the function directly. Re-fit, cheap.
- **control gray, or no indicator at all** → the instrument does not render for
  this account. **STOP** — the next step is a support question, not a trade.

---

## 3. STEP TWO — THE FUNDED TEST, only if Step One returns Rule A

### Why $60 and not more
Net $/window at 20 contracts a side, by bankroll (measured, capital-constrained,
back of queue, $1.00 floor applied per window):

| family | $20 | **$60** | $150 | $500 |
|---|---|---|---|---|
| KXNATGAS15M | +1.08 | **+2.17** | +2.17 | +2.17 |
| KXCOPPER15M | +1.86 | **+1.82** | +1.82 | +1.82 |
| KXSILVER15M | +0.81 | **+1.42** | +1.42 | +1.42 |
| KXWTI15M | **−1.36** | +0.23 | +0.23 | +0.23 |
| KXGOLD15M | **−1.44** | +0.44 | +0.44 | +0.44 |

**$150 and $500 are identical to $60.** Mean size actually resting:
**6.2–12.1 contracts at $20** versus **19.1–19.8 at $60**. At $20 most windows
fall under the $1.00 floor and pay nothing, and two families go outright
negative. **$60 is where the constraint stops binding. Everything above it is
dead capital for this test.**

### The shape
- **One family: KXNATGAS15M.** Thinnest book (side score ~210 vs gold's ~1,079),
  so our dollars buy the largest share; best $/window at every bankroll; and
  4–20× better than any other family per unit of fill risk.
- **20 contracts each side, at the reference price, re-pegged.** Re-pegging is
  not optional: a static quote's share goes to zero in 10% of 30-second windows,
  and a never-moved quote loses **−10.30 c/contract**.
- **Eight consecutive windows** (two hours). Not one — one window is a coin flip.
- **Then stop and wait 48+ hours** for the credit.

### Pre-registered prediction — write this down before sending anything
- Rebate paid: **$1.71/window × 8 = $13.70**, of which windows clearing the
  $1.00 floor: **~7 of 8**.
- Inventory P&L: **+$0.46/window × 8 = +$3.66**, sd ~$3/window.
- **Total expected: ~$17**, with a realistic band of **[$4, $25]**.
- Worst single window observed on tape: **−$7.50**.
- `balance_dollars` will **not** move while orders rest. That is expected and is
  not evidence of anything.

### Decision rule, fixed in advance
- **Credit lands within [$8, $25]** → the model is calibrated. Scale to a
  second family.
- **Credit lands but under $8** → realised share is below modelled. Do not
  scale; re-fit the share model against the realised number.
- **Credit is $0.00 across all eight windows** → either we never cleared the
  floor or we are not eligible. **STOP** and resolve which before spending more.
- **Inventory loss exceeds $15 at any point** → **STOP the run immediately**,
  regardless of rebate.

---

## 4. THE RISKS I AM NOT ABLE TO REMOVE

1. **There is no fundable stop-loss at full deployment.** Netting is OFF
   (read directly). Selling to flatten reserves `(1−p)` per contract — cash a
   deployed account does not have. Turning netting ON has the opposite problem:
   Kalshi's own text says it *"may make you unable to sell positions for which
   you've already had collateral returned"*, and the setting **locks at the
   first order in an event and can never be changed**. **Any plan that says
   "hedge if it goes wrong" is unfunded. Size is the only control.**
2. **The daily figures are not credible and I will not quote them.** ×89
   windows gives ~$193/day on $60 — a >300% daily return. It rests on **6 hours
   of Sunday-evening tape** (the weekend reopening, plausibly the least
   representative session of the week) and assumes ~22 h/day of quoting with a
   re-peg every ~5 s ≈ **15,000 order operations/day**, against unknown rate
   limits. **The per-window figures are defensible; the per-day figures are not.**
3. **All shares are modelled on an undisturbed book.** Bounded, not eliminated:
   across 239,955 natural experiments nobody steps strictly inside an added
   order and paid share moves +0.03% ± 1.15% per 50 lots. But every one of those
   is an *existing* participant observed for ≤30 s. A new persistent participant
   is a different question and tape cannot settle it.
4. **The visible book may not be the whole book.** If Kalshi scores orders the
   public depth feed does not publish, every share here is overstated.
   Untestable from public data. Largest unquantified risk.
5. **Weekday behaviour is unmeasured.** Everything rests on one Sunday session.
   Weekday tape is accumulating now.

---

## 5. WHAT I RECOMMEND, IN ORDER

1. **Tonight, for under $1:** run the two-order rule test (§2). It is the
   highest information-per-dollar action available and it gates everything else.
2. **Do not fund anything until §2 returns.** If it returns Rule B, three jobs
   must be re-run and the family ranking is void — funding first would be
   funding the wrong market.
3. **If Rule A: add $40** (total $60), run the eight-window test in natural gas,
   and wait 48 hours to read it.
4. **Independently of all of the above:** `pin` — the taker strategy at
   **+2.54 c/contract, t = +5.0 out of sample**, needing **~$50 peak concurrent
   capital** for a bootstrap 95% CI of **[+19, +48] $/day** — is the
   best-evidenced result this project has, and its forward test has never been
   started because its pre-registration is unsigned. If capital is going to be
   deployed at all, that is the stronger claim on it.

---

*Kill criterion on record, unchanged: positive expectancy at a fillable size,
demonstrated out of sample on fresh tape, with a drawdown the operator can sit
through. Deliberately not a t-statistic and not a dollar target.*
