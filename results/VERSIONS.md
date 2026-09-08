# Live strategy versions — what is running, and how to go back

**Every change to what trades real money is listed here with its git SHA, the
evidence, and the exact command to revert.** Newest first.

---

## OUTAGE — 2026-09-08 14:40–15:44 UTC, ~1 hour, NO TRADING

**Cause:** three separate hardcoded rails silently refused every scale-up, and
I verified the process *started* rather than that it *survived*.

1. `pinrun` refused `--loss-abort` outside `[-5.00, 0.00)`. The −$10 (v5) and
   −$15 (v6) values were rejected and the process **exited immediately**.
2. `pinrun` refused `--max-positions > 3`. I passed 4.
3. `pintake.MAX_TAKE_COUNT` was **1 contract**, and `MAX_RUN_STAKE` was $5 —
   less than a single size-8 buy (~$7.60). So even with (1) and (2) fixed,
   **size 3 and size 8 would both have been refused at the order stage.**

**The operator noticed before I did** ("No bets have been bought since we upped
it"). The lesson is recorded, not just the fix: **check that a process is still
alive after it starts, and that its orders are accepted, before believing a
deployment.**

**Fixes:** the loss abort now **scales with size** (allowed range is roughly 2–4
ordinary losses at whatever size is trading) instead of a flat cap that was
right at size 1 and fatal at size 8. Order rails raised deliberately with the
reasoning in the source: `MAX_TAKE_COUNT` 1 → 10 (~8% of the median 125
resting at the touch), `HARD_MAX` 5 → 25, `MAX_RUN_STAKE` $5 → $60.

**`pintake`'s own self-test also had to be fixed** — it asserted "count 2 must
be refused", which was correct when the rail was 1 and became a *false alarm*
the moment it was raised. The rail tests are now written **relative to the
constants**, so they stay meaningful at any setting.

---

## v9 — CURRENT (2026-09-08 16:36 UTC) — back to a 98.8¢ ceiling

| setting | value |
|---|---|
| **price ceiling** | **98.8¢** |
| size | 5 contracts |
| buys per close | up to 2, second only if ≥0.5¢ cheaper |
| window | tau 3–30 s |
| loss abort | −$21.00 |
| pid / code sha | 3997812 / `d6826548c653` |

---

## v8 — 96¢ CEILING. IT *WAS* LIVE, IT SUPPRESSED TRADING, AND I TWICE GOT THE STORY WRONG

**This entry has been wrong twice. Both wrong versions are described here rather
than deleted, because the failure mode is the lesson.**

### Wrong version 1 (16:35 UTC): "v8 is live and it is safer AND more profitable"

Two of the three claims did not hold. Total realised profit goes DOWN when you
tighten (742.0¢ → 724.9¢); it only rises in EXPECTATION at an assumed 0.90%
flip rate (625.9¢ → 649.3¢). And "the dear trades were never paying for the
risk" was never measured — there are **zero flips in the entire eligible
sample at every ceiling**, and the 96–98.8¢ band realised **+2.087¢ per
contract** over 784 moments. I stated a model output as a measurement.

### Wrong version 2 (16:20 UTC): "the 96¢ ceiling was never live"

**Also wrong, and worse, because I acted on it.** I read the live process's own
start record, saw `"price_ceiling": 0.988`, and concluded the change had never
been applied.

**That field was DERIVED, not the constant.** The line was:

```python
price_ceiling=round(1.0 - MEASURED_FLIP - EV_FLOOR, 4)   #  = 0.988, ALWAYS
```

It reports the ceiling the EV arithmetic *implies*. It never read
`PRICE_CEILING` at all. **A process running a 96¢ ceiling truthfully logged
98.8¢.** My "verify what the process logged, not what the source says" rule was
right in principle and I applied it to a field that could not answer the
question.

### What actually gave it away — the operator noticed the symptom first

The operator said "haven't seen a trade in a while." The 16:30Z close then
showed this:

```
close 16:30Z  4,264 looks  954 tradeable  fired: FALSE
best: KXBTC15M NO @ 96.6c  edge +2.891c  tau 28s  665.71 contracts on offer
```

Every gate in the code on disk passes that moment: edge 2.891¢ ≥ 0.3¢,
EV 2.270¢ ≥ 0.3¢, price 96.6¢ ≤ 98.8¢. **The only rule that rejects 96.6¢ is a
96¢ ceiling.** Behaviour, not logs, proved it was live.

### Cost

Live signal history: **12 of our 16 real signals were above 96¢** (mean price
paid 97.61¢). The 96¢ ceiling was refusing roughly three quarters of our
trades, against a backtest that predicted it would refuse 30%.

### Two fixes, both in `pinrun.py`

1. **The start record now logs `PRICE_CEILING` itself**, with the derived value
   kept alongside as `ev_implied_ceiling`, plus a `code_sha` fingerprint of the
   running file. A log line can no longer describe code that is not running.
2. **`close_summary` now emits `over_ceiling` and `neg_ev`.** Both counters
   existed and neither was reported, so the refusal was invisible in the log
   that was written specifically to explain refusals.

### The standing rule this replaces

*"Check what the process logged at start"* is not enough. **A configuration
check must read a field that is derived from the constant it claims to
describe — and the way to prove a rule is live is to find a moment it changed
the behaviour.**

---

## v7 — 2026-09-08 16:12 UTC

| setting | value |
|---|---|
| size | **5 contracts** per buy |
| buys per close | up to 2, second only if ≥0.5¢ cheaper |
| window | tau 3–30 s |
| EV gate | ≥0.3¢ at 0.90% flip rate → ceiling 98.8¢ |
| worst case per close | **$10.00** |
| loss abort | **−$21.00** → survives 2.1 bad closes |

### First size-8 trade: WON +49.34¢

```
KXHYPE15M  tau=9s  buy NO @0.9350  fair 0.0103  edge +5.04c  size on offer 34
filled 8.0 @ 0.934, fee $0.0346  ->  settled, payout $8.00
stake $7.4720 + fee $0.0346 = $7.5066   profit +$0.4934   = 6.6% on stake
crypto shard $38.2157 -> $38.7091, reconciles exactly
```

**The rebuilt order rails work end to end at size 8.**

### The safety system caught two configuration errors in ten minutes

**1. Self-halt after the fill (correct).**
```
HALT: realised $+0.00 with $7.47 still open; one more contract
      could take this run past $-15.00
```
Size 8 with 2 buys can commit ~$16 against a −$15 brake. **The configuration
was self-contradictory** and the forward-looking loss bound refused to enter a
state where the brake could be breached. Exactly the right behaviour.

**2. The deployment rail then refused −$21 at size 5 — right call, wrong
arithmetic.** It sized the abort against **one contract** when a close can buy
**MAX_PER_CLOSE** of them. Fixed to use `size × MAX_PER_CLOSE` as the unit of
loss, because **the unit of loss is a CLOSE, not a contract**.

### The pattern, now explicit

This is the **third** time today a limit set for a size-1 proof silently
blocked scaling: the loss-abort range, `pintake`'s 1-contract order cap and $5
run stake, and now the abort's unit of measure. Every one of them was *correct
for size 1* and wrong afterwards.

**Rule going forward: any constant tied to size must be expressed in terms of
size, never as a literal.**

---

## v6 @ size 1 — CURRENT (2026-09-08 15:47 UTC)

| setting | value |
|---|---|
| window | tau 3–**30** s |
| model gate | p_flip ≤ 0.02 |
| EV gate | ≥0.3¢ expected at 0.90% flip rate → ceiling **98.8¢** |
| size | **1 contract** |
| buys per close | up to **2**, second only if ≥0.5¢ cheaper |
| max exposure/close | ~$1.90 |
| loss abort | −$3.00 |

**Deployed at size 1 deliberately.** The operator's instruction: only go one
step beyond a *proven* version, and only if each change passed its historic
test and its failure would be identifiable.

**Each change passed:**
- EV gate — 5 of 7 live trades were negative-EV; break-even price = 1−f is exact
- scale-in — 70 closes, 4.18¢ → 7.43¢/close, average price paid FELL
- tau 30 — 0 flips in 2,872 moments across 118 closes at tau 21–30

**Each failure is distinguishable:**
| symptom | cause | fix |
|---|---|---|
| flips on trades at tau > 20 | v4 | `--tau-max 20` |
| second buy at a WORSE price than the first | v3 | `MAX_PER_CLOSE = 1` |
| any fill above ~98.7¢ | EV gate not binding | check `MEASURED_FLIP` |
| flip rate > 2.31% | the whole ceiling is wrong | re-derive every threshold |

**Size stays at 1 until this version has traded and won on its own.** Scaling
is a separate, later decision — it does not accelerate learning, only exposure.

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
| orders sent | 16 |
| executed / no fill | 12 / 4 |
| settled and booked | 12 |
| won / lost | **12 / 0** |
| realised | **+70.65¢** |
| crypto shard | $38.7091 |
| price paid, live | min 93.50¢, mean **97.61¢**, max 99.60¢ |

Biggest single win: the size-8 HYPE trade, +49.34¢ (6.6% on stake). **Its
`settled` record is missing from the JSONL** because the process was stopped
between fill and settlement; the balance reconciles, so the trade is real, but
the log undercounts. Log scans of `kind == "settled"` return 11, not 12.

**Standing caveat:** at the measured 0.90% flip rate, 12 straight wins is the
*expected* outcome (0.11 losses expected). Nothing about the tail has been
observed live. At the live mean price of 97.61¢ the first loss costs roughly
**41 wins**, not ten.

## What to check first if it starts losing

1. **Flip rate by tau.** If flips appear above tau 20, v4 is the cause — revert
   to `TAU_MAX = 20`.
2. **Average fill price per close.** If the second buy is coming at *worse*
   prices, v3's mechanism has reversed — set `MAX_PER_CLOSE = 1`.
3. **Prices paid.** If trades are appearing above 98.5¢, the EV gate is not
   binding — check `MEASURED_FLIP` and `EV_FLOOR`.
4. **The measured flip rate itself.** Everything above is built on 0.90% from
   3 flips in 333. If the live rate exceeds 2.31% (the EXACT one-sided 95%
   Clopper-Pearson bound; the 1.80% figure quoted until 2026-09-08 was a normal
   approximation and is optimistic by 28% at only 3 events), the
   price ceiling is wrong and every threshold must be re-derived.
