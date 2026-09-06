# PREREG — `pin` forward test

**Status: DRAFT, UNSIGNED. The forward window has NOT started.**
Drafted 2026-09-06 by Claude. It starts only when the operator signs at the
foot of this file with a date. Nothing in the 336–2,638 closes already
measured counts toward it.

---

## Why this document exists

The whole value of the result depends on the rule being fixed **before** the
data that judges it exists. Everything measured so far is backtest: the rule
below was chosen partly by looking at that backtest, and that is stated openly
in §6. The forward test is what converts a chosen rule into an honest one, and
it only works if nothing here moves afterwards.

---

## 1. The rule, frozen

**Entry.** For every market in the twelve 15-minute crypto series, at every
second with `tau <= 60` seconds to close, compute model fair value from the
settlement model (`Var(settle - strike) = 880·sigma²`, sigma refit walk-forward
on closes strictly earlier than the one being traded, `k` refit every 10 closes
after a 150-close warmup). Take the trade when the fee-netted edge against the
book clears **0.5c**, at the **earliest** qualifying second, never the best one.

- `tau_max = 60s`
- `edge floor = 0.5c`
- `pin threshold = 0.98` (fair ≥ 0.98 or ≤ 0.02)
- **every market at each close**, not one per close
- rule = `"first"` (earliest qualifying second; taking the maximum
  disagreement in a window is look-ahead and was measured at −49.5c on a
  zero-edge tape)

**These are all pre-existing parameters in `pin.py`, not new ones.** `FLOORS`,
`TAU_MAX` and the two portfolio variants were in the file before tonight.

## 2. The size clause — set by the depth measurement, not by assumption

**Size = `min(100, 0.25 × resting_size_at_the_touch)` contracts.**

Where `resting_size_at_the_touch` is `yes_ask_size_fp` when buying YES and
`yes_bid_size_fp` when buying NO, from the last ticker message at or before the
entry second.

**Why a fraction of the touch rather than a fixed 50.** Measured resting size
where `pin` hits: p10 **2**, p25 **15**, median **69**, p75 **193**, p90 **455**.
A flat 50 fails to fill **42.3%** of the time and consumes the **entire**
resting level **42–46%** of the time. Consuming the whole level assumes we win
the race for a stale quote against everyone else who wants it — which this
backtest cannot test, and which the operator has ruled unavailable at cap 100.
It is the same assumption at cap 50, merely smaller.

`0.25 × depth` never consumes more than a quarter of the level. **Measured:
0% of trades eat the whole level under this rule.** It also *earns more*,
because it sizes up on deep books and down on thin ones, and per-contract edge
does not decay with depth (measured by depth bucket: `<5` +4.13c, `40–100`
+1.91c, `100–300` +3.68c, `300+` +1.66c — no monotone decay).

**Average fill under this rule: 30.4 contracts.**

## 3. What it is expected to do

Backtest, out-of-sample walk-forward, 2,638 trades over 364 closes in 9.6 days,
20,000-rep percentile bootstrap **over closes**:

| | |
|---|---|
| $/day | **$101** |
| 95% bootstrap interval | **[+$65, +$143]** — excludes zero |
| max drawdown observed | **$51** |
| $/day per $ of max drawdown | 1.98 |
| worst single close | see §5 — this number is not a downside estimate |
| trades eating the whole level | **0%** |

## 4. Success and failure, decided in advance

Per the operator's revised kill criteria (2026-09-06):

- **Sample:** **500 fired closes** of forward tape, scored **standalone**, not
  pooled with anything measured before the signature date. At the measured fire
  rate (~38 closes/day at `tau<=60` every-market) that is **~13 days**.
- **PASS:** the 95% bootstrap interval on per-close P&L **excludes zero on the
  positive side**, AND realised max drawdown stays inside the tolerance in §5.
- **FAIL:** the interval includes zero, or the drawdown tolerance is breached.
- **The forward test is scored on the rule exactly as frozen above.** If any
  parameter is changed after the window opens, the window restarts at zero.

## 5. The drawdown clause — NEEDS THE OPERATOR'S NUMBER

The revised threshold says *"a maximum drawdown I can sit through"*, and it has
no number. **An unquantified drawdown limit is not a kill criterion — it can
absorb any result, which is the exact failure mode this document exists to
prevent.** So a number goes here, or the criterion is incomplete.

**What was measured:** max drawdown **$51** over 9.6 days, at the size in §2.
The longest underwater stretch was tens of consecutive closes.

**What that number is NOT.** It is the worst drawdown seen in **nine days**. It
is a *lower bound* on the true drawdown, not an estimate of it. By the rule of
three, having seen no worse loss in 364 closes bounds the rate of a worse one
only at 3/364 ≈ 0.8% per close — which at 38 closes/day is roughly **once a
month**. Wherever `−$38.65` or `−$46.33` appears as "worst close", it means
*worst close observed in nine days* and nothing more.

**Proposed clause, for the operator to accept or replace:**

> Stop the forward test and re-examine if cumulative drawdown from peak exceeds
> **$250**, i.e. ~5× the observed maximum and ~2.5 days of expected P&L.
> Scale size linearly to whatever drawdown tolerance is chosen: the rule in §2
> is stated at a base unit, and halving the cap halves both the P&L and the
> drawdown.

`[ ] Accept $250   [ ] Use instead: $______   [ ] Different rule: __________`

## 6. Known weaknesses — stated before the test, not after

1. **THE RACE IS THE PRIMARY OPEN RISK, above everything else.** The backtest
   always gets the quote. In reality we are racing everyone else for the same
   mispriced quote, and the most mispriced quotes are the most worth racing
   for. Real fills will be worse than backtest fills **by an unknown amount
   that nothing measured so far bounds.** The `0.25 × depth` rule reduces this
   exposure but does not remove it: we still must be early enough to get a
   quarter of the level. **If the forward test underperforms the backtest, this
   is the first place to look.**
2. **Selection.** The rule was chosen after looking at roughly 44 backtest
   cells (2 tau cuts × 2 filters × 3 caps × 3 fractions, plus 8 earlier).
   Selecting the best of many is selecting on our own error — the trap `fit_k`
   was written for. The forward test is the correction for this, which is
   precisely why it must be run before any of these figures are believed.
   *Deliberately excluded* from the rule: the `spread >= median` filter, which
   scored better on drawdown efficiency (2.42 vs 1.98) but is the most
   data-selected element on the table. Fewer chosen parameters, cleaner test.
3. **Nine days.** Every backtest number rests on 9.0–9.6 days of tape.
4. **Concentration.** Top 10 of 336 closes carry 45–56% of the money; top 25
   carry 73–86%. Real, and a screen most fat-tailed strategies fail. It is
   partly predictable ex ante — a walk-forward model on entry-time features
   (edge, spread, extremity; **depth excluded** because it enters the P&L
   arithmetic and would be tautological) raises per-contract edge from 2.32c to
   **5.17c** in its top quartile at `tau<=20`, and win rate from 90% to 96%.
   But **filtering lowers total $/day** (50 → 29) because size is capped per
   trade by depth, not by capital. It buys drawdown, not income. Not in the
   frozen rule.
5. **78.3% of closes are individually profitable.** Recorded because it is the
   fact that makes "lottery ticket" the wrong description, and that label — mine
   — is withdrawn.
6. **Fees** are in every number (`0.07·p·(1−p)` per contract, taker side).
7. **No order has ever been placed by this project.** A forward test on
   *recorded tape* is still a backtest of a frozen rule; it is not a paper
   trade and it is not a live trade. That distinction stays explicit.

## 7. What "starting the clock" means operationally

1. The operator signs below.
2. The signature timestamp is recorded, and only closes **after** it count.
3. The collector keeps running; no change to `CRYPTO_15M` during the window,
   because adding series mid-test changes the population being measured.
4. `pin` is scored standalone at n≥500 and the result written to
   `results/RESULTS_pin_forward.md`, whatever it says.

---

## Signature

I have read §1–§7, including the weaknesses in §6, and I am freezing this rule.

```
Operator: ______________________     Date/time (UTC): ______________________

Drawdown clause chosen (§5): ______________________
```

**Until this is signed the forward window has not started and no number in
this file may be described as a forward result.**
