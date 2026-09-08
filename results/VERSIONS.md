# Live strategy versions — what is running, and how to go back

**Every change to what trades real money is listed here with its git SHA, the
evidence, and the exact command to revert.** Newest first. If performance
degrades, this is the file to read.

---

## v5 — CURRENT (2026-09-08 ~15:40 UTC)

| setting | value |
|---|---|
| window | `tau` 3–**30** s |
| model gate | `p_flip` ≤ 0.02 (fair ≥0.98 or ≤0.02) |
| edge floor | 0.3¢ after fee |
| **EV gate** | ≥0.3¢ expected at the measured 0.90% flip rate → price ceiling ~98.5¢ |
| **size** | **3 contracts** per buy |
| buys per close | up to 2, second only if ≥0.5¢ cheaper |
| max exposure/close | ~$5.70 |
| loss abort | **−$10.00** |
| stake cap | $5.00 committed (pintake) |

**Change from v4:** size 1 → 3, loss abort −$3 → −$10.

**Why:** the edge rests on 354 out-of-sample closes (+2.51¢, t=+4.1), all four
falsification controls passing (mirror refused 70/70, forced-wrong lost 70/70,
placebo bled −48.68¢/trade), and zero flips in 5,219 moments under tau 30.
Scaling does not accelerate learning — trade *count* does — so this is purely a
decision about how much to risk on evidence already in hand.

**Why the abort moved:** at size 3 one ordinary loss is −$2.85. A −$3 brake
would fire on the *first expected event* rather than on a malfunction. −$10 is
roughly 3–4 losses, which at a 0.9% rate is a genuine anomaly.

**Revert:** `git checkout 45966b9 -- research/pinrun.py` then relaunch with
`--size 1 --loss-abort -3.00`.

---

## v4 — 2026-09-08 15:20 UTC — SHA `45966b9`

Window **20 → 30 seconds**. Model calibration measured by horizon: 0 flips in
5,219 moments below tau 30; 3.7× overconfident at 31–45; **10.9× at 46–60**.
The overconfidence is entirely a long-horizon effect, which also explains why
the `tau<=60` backtest cell was dead. Roughly doubles qualifying moments.

**Revert:** set `TAU_MAX = 20`.
**Revert trigger:** any flip on a trade at tau > 20 → review; a second → revert.

---

## v3 — 2026-09-08 15:00 UTC — SHA `d04647d`

**Scale in as the price improves**: up to 2 buys per close, the second only at
≥0.5¢ better. Measured 4.18¢ → 8.87¢ per opportunity, average price paid FELL
95.53¢ → 94.28¢. Waiting instead is strictly worse (skipping one tick missed 7
of 70 closes).

**Revert:** `MAX_PER_CLOSE = 1`.
**Revert trigger:** average fill price across a close exceeding the first
fill's price over 50+ closes.

---

## v2 — 2026-09-08 11:35 UTC — SHA `c3aca51`

**EV gate.** Replaced "model edge ≥ floor" with `EV = (1−f)(1−p) − f·p − fee ≥
0.3¢` at the **measured** 0.90% flip rate, implying a price ceiling near 98.5¢.
Found because 5 of the first 7 live trades were negative-EV: breakeven price is
exactly `1 − f = 99.1¢`, and the model's own fair value implied 0.06% error
where reality is 0.90%.

Effect: profit per trade 1.41¢ → 3.42¢.

**Revert:** remove the `expected_value` check.

---

## v1 — 2026-09-08 08:20 UTC — SHA `2489d73`

**Edge floor 0.5¢ → 0.3¢.** Out of sample the looser floor gave 389 closes /
+2.76¢ / t=+5.6 / 1 flip in 359, against 354 / +2.51¢ / t=+4.1 / 3 flips in 333.

**Revert:** `EDGE_FLOOR = 0.005`.
**Revert trigger:** live flip rate ≥ 1.0%.

---

## v0 — 2026-09-08 07:09 UTC — first live version

tau 3–20, fair ≥0.98/≤0.02, edge ≥0.5¢, one buy per close, size 1,
loss abort −$3.00. First real trade 08:00Z (BTC YES @0.992, won +0.74¢).

---

## Running record

| | |
|---|---|
| trades settled | 11 |
| won / lost | 11 / 0 |
| realised | +21.31¢ |
| balance | $41.0386 → $41.2517 |

**Standing caveat:** at the measured 0.90% flip rate, 11 straight wins is the
*expected* outcome (0.1 losses expected). Nothing about the tail has been
observed live. The first loss will cost roughly ten wins.

## What to check first if it starts losing

1. **Flip rate by tau.** If flips appear above tau 20, v4 is the cause — revert
   to `TAU_MAX = 20`.
2. **Average fill price per close.** If the second buy is coming at *worse*
   prices, v3's mechanism has reversed — set `MAX_PER_CLOSE = 1`.
3. **Prices paid.** If trades are appearing above 98.5¢, the EV gate is not
   binding — check `MEASURED_FLIP` and `EV_FLOOR`.
4. **The measured flip rate itself.** Everything above is built on 0.90% from
   3 flips in 333. If the live rate exceeds 1.80% (its 95% upper bound), the
   price ceiling is wrong and every threshold must be re-derived.
