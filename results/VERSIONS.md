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

## v14 — CURRENT (2026-09-08 22:47 UTC) — funded, size 20, cap 3

| setting | value |
|---|---|
| **bank** | **$154.33**, all on the Crypto shard |
| size | **20 contracts** |
| buys per close | **3**, each ≥0.5¢ cheaper than the last |
| partial fills | down to 50% of size |
| price ceiling | 98.8¢ |
| worst case, one close | $60 |
| dollar brake | −$90 |
| **loss-count brake** | **3 losing trades** |
| **attempts per close** | **8**, separate from the 3-fill cap |
| max open positions | 4 |
| pid / code sha | 4074664 / `e4cdb6320807` |

The operator funded the account. The $150 landed on exchange_index 0, where it
could not have bought anything, and $113.0360 was moved to the Crypto shard.

---

## THE RUNAWAY — 2026-09-08 22:44:30Z, 160 refused orders in one second

**No money lost. Balance unchanged, zero fills, zero open positions.** Caught by
the monitor and stopped within seconds.

**Two of my own changes collided, and neither was wrong alone.**

1. **`pintake.MAX_TAKE_COUNT` was still 10**, so every order at size 20 was
   silently refused. **The FOURTH size-1 literal to break scaling in one day**,
   after the loss-abort range, the run-stake cap and the stake release.
   `take()` *returns* its violations rather than raising, so nothing noticed:
   the order records carry `status_code: null`, `parsed: false`, `error: null`.
2. **AMENDMENT 6 had just stopped a no-fill from consuming a scale-in slot.**
   That is correct — an unfilled order creates no exposure — and it earned
   +27.96¢ within five minutes of deployment. But it left **nothing bounding
   how many times we may try**, so a permanently refused order retried at 20 Hz
   forever.

**Fills and attempts needed separate budgets and only had one.**

### Three fixes

| | |
|---|---|
| `set_limits()` now raises `MAX_TAKE_COUNT` too | and `HARD_MAX` with it, announced, never silently. Still refuses to lower either. |
| a returned refusal is now an **error** | `order_errors` increments, so two in a row halt the run |
| `MAX_ATTEMPTS_PER_CLOSE = 8` | counted **before** the send, so a call that never returns still consumes one |

**Verified against the production endpoint without sending:** `check_take` at
size 20 returned `['count 20.0 exceeds MAX_TAKE_COUNT 10.0']` before the fix and
`[]` after.

### The lesson, and it is the second time today

I verified the process **started** and that its start record described the right
configuration. **I did not verify that an order at the new size would be
ACCEPTED.** That is one function call, no network, no money, and it is now part
of every deployment. *"The process is alive"* and *"the process can trade"* are
different claims.

---

## v13 — 2026-09-08 22:15 UTC — cap 2 → 3

**Withdrawn, then reinstated at the operator's instruction** (*"if you know the
idea works then do it"*). It is **not a new mechanism**: the scale-in rule has
been live since v3 and has produced second buys on real closes. Cap 3 only lets
the same proven rule repeat once more, and **the trade it adds is the cheapest
of the close** — every extra buy must clear `IMPROVE_BY`, so a third buy is at
least 1.0¢ below the first. Cheaper wins more *and* loses less, so cap 3 cannot
degrade the average price paid. Structurally, not merely empirically.

Measured with losses injected per close at the 2.31% exact upper bound:

| | typical result | ruined |
|---|---|---|
| size 20, cap 2 | $271 | 3.4% |
| **size 20, cap 3** | **$304** | **1.1%** |

**12% more money and a third of the ruin.** What it costs is exposure, not
per-contract risk.

**The self-test found the deployment bug for free.** With `--max-positions 3`,
the third buy plus a straggler still settling from the previous close would have
been silently refused. The flag is now 4.

---

## v11 — 2026-09-08 21:39 UTC — MORE BETS, same maximum exposure

| setting | value |
|---|---|
| size | 10 contracts |
| **partial fills** | **take `min(size, offered)` down to 50% of size** |
| **scale-in slot** | **consumed by a FILL, never by an attempt** |
| price ceiling | 98.8¢ |
| loss abort | −$30.00 |
| pid / code sha | 4052684 / `792ee01f2153` |

**Neither change raises the maximum exposure of a close.** That was the
constraint, because the balance cannot fund more.

### Change 1 — a no-fill no longer burns a scale-in slot: +33.3%

`fired[close_s]` was written when the SIGNAL fired, *before* the order was
sent, so an order filling **zero** contracts still burned one of the two
allowed buys and still raised the improve bar. **5 of our first 19 live orders
filled nothing**, and depth was not the cause — the misses had 562, 107, 93, 10
and 5 contracts on offer. Lost races, not thin books, so they recur.

| at the observed 26% miss rate | closes won | buys | expected |
|---|---|---|---|
| no-fill BURNS a slot (before) | 67 | 87 | $40.29 |
| **no-fill keeps the slot** | **80** | **119** | **$53.72** |

**Max exposure unchanged** — the cap always meant two *fills*; the bug made it
two *attempts*.

### Change 2 — take a partial down to half size: +1.3% at size 10, +5.4% at 25

| threshold | buys | expected |
|---|---|---|
| full size only (before) | 124 | $59.75 |
| **≥50% of size** | **125** | **$60.53** |
| ≥5% of size | 129 | $58.37 |

**Taking any scrap is worse than taking none:** a tiny early fill burns a slot
and raises the improve bar, trading a big cheap buy later for a small dear one
now. Half is the measured optimum at both sizes. Exposure can only fall.

### MEASURED AND REJECTED: `MAX_PER_CLOSE` 2 → 3

**+26.7%, larger than either change above, and NOT deployed because it cannot
be funded.** Worst close $30 against a $38.83 balance, and the rail would need
a brake at −$45 or looser. **This is the best available change the moment the
account is funded.**

### Three self-tests were inspecting themselves

`src.index("def trade_loop(")` matched this test file's OWN string literal,
because `selftest()` is defined above `trade_loop`. Every structural check
built on it was reading the test instead of the code and could have passed
vacuously. All three now anchor on a newline.

**Revert:** `MIN_FILL_FRAC = 1.0`, and move `_book_slot()` back above the order.
**Pre-registration:** `results/PREREG_pin_live_AMENDMENT_6.md`.

---

## v10 — 2026-09-08 21:14 UTC — size 10, and two silent killers removed

| setting | value |
|---|---|
| size | **10 contracts** |
| price ceiling | 98.8¢ |
| buys per close | up to 2, second only if ≥0.5¢ cheaper |
| window | tau 3–30 s |
| loss abort | **−$30.00**, and the order path now agrees |
| pid / code sha | 4056648 / `497c2f96b280` |

### First size-10 trade: +103.14¢, more than the whole day before it

```
21:30Z close   KXBTC15M  tau=7s  buy NO @0.8900  fair 0.00256  edge +10.058c
1,000 contracts on offer, we took 10
filled 10.0 @ 0.89, fee $0.0680  ->  settled NO, payout $10.00
stake $8.9000 + fee $0.0680      profit +$1.0314   = 11.59% on stake
```

**89¢ is the cheapest price we have ever paid**, and the cheapest price wins
more *and* loses less. Break-even at 89¢ is an 11% error rate; ours is 0.90%.

### Two size-1 literals were silently disarming the trader — found by audit

1. **The stake release gave back ONE contract instead of the whole fill.**
   pintake commits `filled × price`; reconcile released bare `price`. At size 5
   that stranded $3.90 per settled trade, turning the $60 run-stake cap back
   into a **cap on lifetime turnover** — every order refused after ~15 fills,
   6 at size 10. `take()` *returns* the refusal rather than raising, so nothing
   halted and nothing logged. Two give-up branches released **nothing at all**.
2. **`pintake.LOSS_ABORT` was a hard −$2.00.** One ordinary loss at size 5 is
   −$4.88, so **the first loss we ever took would have shut off all trading**,
   silently, while the −$21 brake sat untouched.

**Fixes:** a single `_release()` used on all three exit paths, releasing
`cost × contracts`; P&L booked on contracts actually filled; and
`pintake.set_limits()`, which raises the order-path rails to agree with the
run's own brake and **refuses to tighten**.

**The self-tests now sweep sizes 1, 5, 8, 10, 25**, include a positive
assertion that a one-contract release at size 5 leaks $3.90 so they cannot pass
vacuously, and scan the source to require every exit path to release.

### Depth tracking added

`close_summary` now carries min/p25/median/p75/max/total contracts offered
across every moment we could have bought, plus how many survive at each
candidate size. Early readings: **median 530 contracts** on one close, **101**
on another, with 414 moments surviving size 10.

**Revert:** `--size 5 --loss-abort -21.00`.
**Revert trigger:** any fill above 98.8¢, or a flip rate above 2.31%.

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
| won / lost | **20 / 0** |
| bank | **$154.9908** on the Crypto shard |
| biggest single trade | +103.14¢ (BTC, 10 at 89¢) |
| price paid, live | min **89.0¢**, max 99.60¢ |

### The 23:15 close is the clearest evidence yet that AMENDMENT 6 was right

```
23:14:32  SOL  @91.8c   race LOST, filled 0
23:14:33  DOGE @98.0c   FILLED 20        +37.25c
23:14:36  SOL  @96.9c   FILLED 10 of 11  +28.89c
```

**Under the old rule that close makes ZERO trades.** The lost race at 91.8¢
would have burned a slot *and* set the improve bar at 91.8¢, blocking both
trades that followed. Counterfactual, run explicitly: old rule 0 fills, new rule
2 fills, **+66.14¢ from a close that would have been silent.**

The second SOL order also fired the **partial-fill** rule for the first time: it
asked for 11 contracts because only 11 were offered, 11 clears the half-of-20
threshold, and the exchange filled 10. That change measured only +1.3% in
backtest and produced a 28.89¢ trade here.

Bank reconciles exactly: $154.3294 − $29.29 stakes − $0.0486 fees + $30.00
payouts = **$154.9908**, which is what the account reads.

**Standing caveat:** at the measured 0.90% flip rate, 20 straight wins is the
EXPECTED outcome. Nothing about the tail has been observed live.

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
