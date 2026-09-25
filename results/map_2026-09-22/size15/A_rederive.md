# A_rederive — is the 1.5x size step safe? Independent re-derivation

**2026-09-23. Label `rederive`.** My own join of `results/pinrun-live-*.jsonl`
(`signal` -> `order` -> `settled`) against `results/kalshi_ledger.json`
(Kalshi's own settlement rows). Nothing here comes from `C_decide.md`,
`pindata` or `pinsim`. Scripts live in the session scratchpad under
`size15\rederive\` (`join.py`, `step1..step12`).

**Reconciliation my join passes:** grouping by ET day reproduces
09-19 = **-$223.46** exactly, the corrected figure in `CURRENT_STATE.md`.
Fill rate reproduces at **94.9%** (38,844 of 40,936 contracts), matching the
figure C_decide quotes.

---

## VERDICT — the operator's condition is NOT met

He wrote: *"if ... the worst close is genuinely unchanged let's do it."*

**It is not unchanged. It gets about 50% worse.** The worst close goes from
**-$108.86 to -$163.29**, and the most money committed in one close goes from
**$312.79 to $469.18** — 80% of the $584.46 he has put in.

The reason C_decide got the opposite answer is one factual error, below.

---

## 0. THE LOAD-BEARING CLAIM IN C_decide.md IS FALSE

C_decide: *"the four biggest losses we have ever taken are ALL in that half
[where the offer ran out] ... A bigger size could not have made any of them
worse, because there was no more contract to buy."*

Straight off the `signal` records that produced those very fills:

| loss (Kalshi ledger) | we bought | offered AT THE TOUCH | whole ladder at/under 98c |
|---|---|---|---|
| BTC 09-19 16:00Z **-$107.95** | 110 | **482.43** | 482.43 |
| BTC 09-19 02:00Z **-$66.34** | 70 | 143.99 | **48,604** |
| XRP 09-19 23:45Z **-$64.95** | 104 | 313.5 | 549 |
| NEAR 09-21 12:45Z **-$59.09** | 81 | 104 | 317 |
| BNB 09-19 01:45Z **-$57.76** | 76 | 60 @85c | **11,761** |
| HYPE 09-19 23:45Z **-$43.92** | 104 | 225 | 227.5 |

Every one was capped by **our own SIZE**, not by the offer — `take_n =
min(SIZE, offered)` returned SIZE in all six. Only **BNB 09-19 12:30Z
(-$61.75)** was genuinely depth-limited (asked 171, filled 82.8).

Re-run at 1.5x with the extra contracts capped at the logged ladder and priced
by walking it: **-$107.95 becomes -$161.93; -$66.34 -> -$99.48; -$64.95 ->
-$97.42; -$59.09 -> -$88.64.**

**Why C_decide went wrong:** its "the offer ran out" test compares the FILL to
SIZE, which counts every early leg (which only ever asks for a third of SIZE)
and every budget-trimmed order as "ran out". I cannot reproduce 56.5% under
any definition — closest are `touch < SIZE` at 45.4% and `fill < asked` at
11.4% (per market, n=800). And none of those is the right test, because the
bot already sweeps the whole ladder up to 98c (`--sweep-depth`), so the touch
is not the constraint.

---

## 1. DEPTH — what did we take, and what was still there?

Population: **459 fills over 426 markets and 301 closes, 2026-09-15 to
09-23** — every fill with a full logged ladder (`ladder_under` starts
2026-09-15 07:29Z; the 374 earlier markets cannot be measured at all).

| | |
|---|---|
| ladder at/under 98c **<= what we took** (nothing more to buy) | **116 of 518 = 22.4%** |
| more was genuinely there | **402 = 77.6%** |
| median contracts still on offer above our fill | **299.5** (p25 90, p75 1,007, p90 5,515) |
| ladder / our fill | median **3.76x**, p25 1.10x, p90 63.9x |
| ladder >= 1.5x our fill | **70.8%** |

Of the 518, 61 (11.8%) were short-filled; 57 of those 61 still had ladder
left. Of the 457 that filled completely, 112 (24.5%) had nothing more.

**A warning about the 3,192 figure the operator saw.** That is `ladder_total`
on the SOL 09-23 04:59:57Z signal — the WHOLE book up to 99.9c. Only **851 of
it sat at or under our 98c ceiling**, and across the record the usable share
is a median of **6.6%** of `ladder_total` (median total 3,348, median usable
294). Above 99.1c a contract loses money on average whatever the model says
(`expected_value`), so most of any big ladder number is unreachable by design,
not by size. We took 82 of the 851 that were reachable there.

## 2. IS DEEP DEPTH SOL-ONLY? No — and SOL is not even the deepest

| coin | share of our fills | median ladder <=98c | p90 | median as x our SIZE | depth >= 1.5x SIZE | full 1.5x step possible |
|---|---|---|---|---|---|---|
| BTC | 17.4% | **3,797** | 43,523 | 48.7x | 90% | **90%** |
| SOL | 12.8% | 288 | 879 | 3.6x | 75% | 72% |
| XRP | 12.5% | 262 | 1,109 | 3.2x | 83% | 81% |
| HYPE | 11.8% | 274 | 1,159 | 3.1x | 66% | 69% |
| BNB | 11.9% | 140 | 2,785 | 1.6x | 50% | **52%** |
| DOGE | 9.1% | 209 | 638 | 2.4x | 69% | 75% |
| ZEC | 8.9% | 232 | 2,717 | 2.4x | 69% | 71% |
| NEAR | 7.9% | **118** | 464 | 1.3x | 44% | **49%** |
| ETH | 7.6% | 427 | 3,088 | 5.3x | 76% | 76% |
| **all** | 100% | **294** | 4,925 | 3.5x | 70% | 71% |

It is general, not SOL. **BTC is 13x deeper than SOL.** The thin ones are
**NEAR and BNB** — and those two produced four of our seven biggest losses.
Extra size lands hardest where depth is best (BTC), which is not necessarily
where the edge is.

## 3. THE HONEST 1.5x — capped at the ladder, priced by walking it

Method, validated before it is used:

1. For each fill I recompute the order the bot would have sent from the
   **logged ladder**, using `pinrun.sweep_limit`, `pinrun.taper_take` and
   `pinrun.net_edge` — the bot's own functions. **This reproduces the exact
   count the bot actually sent in 80.5% of clean cases** (leg=full, tau>10,
   n=113), median relative error 0.0000.
2. The ladder also **prices our real fills to the cent**: ladder-implied VWAP
   vs actual `exec_price`, n=449, **median +0.000c**, mean -0.50c. So the
   logged ladder is a fair pricing source.
3. At 1.5x every cap in the chain scales (SIZE, the taper cap, the close
   budget, the early-leg fraction) — **only the ladder does not**. Extra
   contracts are capped there, priced with `pinrun.hedge_vwap` walking the
   rungs ABOVE what we already took, never above 98c, and filled at the same
   rate that order actually achieved (the cautious choice).

**What the ladder allows:** full 1.5x on **328 of 459 fills (71.5%)**; nothing
at all on 92 (20%); partial on 39.

**What the extra contracts cost:** **+0.57c per contract more** than we
actually paid (median +0.00c, p90 +0.80c).

| over 426 markets / 301 closes / 9 days | total |
|---|---|
| today (1x), Kalshi ledger | **+$306.63** |
| **1.5x, honest (depth cap + ladder price + fee)** | **+$431.23** |
| delta | **+$124.60 (+40.6%)** |
| 1.5x if every extra contract always filled (upper bound) | +$441.84 |
| naive flat x1.5 — what C_decide's table does | +$459.94 |
| 1.5x with the `--loss-cap 200` day-halt modelled | +$514.71 (+67.9%) |
| 1.5x excluding 09-19 (the fixed hedge-bug day) | +$755 vs +$530 (+42.5%) |

**Uncertainty (cluster bootstrap over the 301 closes, B=4,000):**
delta **+$124.60, 95% [-$82.85, +$291.58]**, **negative in 10.8% of draws**.
That is +$13.84 a day on a 9-day window containing 13 losing markets. It is a
plausible gain, not a reliable one.

**The extra contracts are worse than the ones we already buy:** +2.211c each
against **+2.437c** for the base (unhedged markets, 11,761 extra contracts vs
27,627 base). Still positive — the taper is doing its job — but thinner.

**Close-budget interaction (C_decide's point 3, now priced).** The budget is
`MAX_PER_CLOSE x SIZE`, so it grows 1.5x too. Of the 69 budget refusals with
the numbers logged (490 refusals total across 73 closes), **54 (78%) would now
pass**, adding a market to **24 closes**. That is not extra profit in the
table above — it is extra *concentration* in the one tail we actually fear.

## 4. WORST CLOSE AND THE CORRELATED TAIL

| | 1x | 1.5x |
|---|---|---|
| worst single close (09-19 23:45Z, HYPE+XRP) | **-$108.86** | **-$163.29** |
| 2nd worst (BTC 09-19 16:00Z) | -$107.95 | **-$161.93** |
| most dollars committed in one close (both legs) | **$312.79** | **$469.18** |
| that as a share of the $584.46 put in | 54% | **80%** |
| bound: all 3 legs lose at 98c, no insurance (`worst_close_cost`) | $249.90 (size 85) | **$373.38** (size 127) |
| that bound vs $584.46 put in / vs the $1,002 bank | 43% / 25% | **64% / 37%** |

The bound **understates** it: `worst_close_cost` does not count the insurance
premium. On 09-19 23:45Z we committed $312.79 against a bound of $305.76,
because the hedge cost $113 on top.

**Correlated closes, our own record:** 561 closes with no loser, **24 with
exactly one, 1 with two** (09-19 23:45Z, HYPE and XRP together, -$108.86).
The basket has bitten us once in 586 closes.

**The 09-11 12:30 ET (16:30Z) event.** From Kalshi's own settlements
(`fulltape/markets.json`) **7 of the 9 coins settled NO at that one close** —
the basket effect is real. But **we held ONE market there (XRP) and it WON,
+$0.42**; the bot was watching two markets that week. That event has never
touched our money, and "7 of 9 the model called 99.5%+" is about the model,
not about our fills. At 1.5x it still costs nothing, because we were not in it.

**The worst PLAUSIBLE close at 1.5x — every leg loses, no insurance — is
$373, which is 64% of everything he has put in, gone in one minute.** Nothing
stops it: `--loss-abort` and `--loss-cap` act after settlement, and every leg
is bought before the close resolves.

## 5. WHICH RAIL BINDS FIRST AT 1.5x

At bank $1,002.27: brake 4.00 -> size **85**; brake 2.67 -> size **127**
(1.49x). In order of what binds:

1. **THE HEDGE — this is the one that breaks.** At 1.5x the insurance must
   cover 127-190 contracts where today it covers 85-127. On our own fills the
   hedge has already got **less than it asked for in 12 of 37 fires (72.1% of
   contracts filled)**, and the insurance book we watch while holding
   (`hedge_quote`, n=1,428) holds **>=150 contracts only 54% of the time and
   >=200 only 50%** (median 199, p25 38). **A 1.5x position with a 1x hedge is
   a 1.5x naked loss.** The five recent full covers are real, and they are
   five.
2. **`--loss-cap 200` — fixed dollars, does NOT scale with size.** At 1.5x a
   single worst close (-$163) leaves $37 of the day's allowance. Modelled over
   the 9 days it halts 09-19 at **15:59 ET instead of 23:44 ET** — protective
   (it is why the halt-aware total is higher) but it also means one bad close
   ends the trading day.
3. **`AUTO_SIZE_MAX 250`** arrives at a bank of **$1,960** instead of $2,940 —
   two-thirds of the runway.
4. **The bank brake itself**: the bank covers **2.67 worst closes instead of
   4**. That is the whole trade, stated plainly.
5. **Does NOT break:** `pintake.MAX_TAKE_COUNT`, `HARD_MAX`, `MAX_RUN_STAKE`
   and `loss_abort` are all re-derived by `apply_size()` with `max()`, and
   `pintake.set_limits` refuses a tightening — checked in code, and the live
   `autosize` records show them moving (`max_take_count 163.5`,
   `max_run_stake 664` at size 83). The taper also scales with SIZE and is
   what keeps the extra contracts at +2.2c instead of at the 98c ceiling.

## 6. WHAT WOULD MAKE MY OWN ANSWER WRONG

- **The ladder is one book read at the decision instant.** My reconstruction
  misses the real count in 1 of 5 cases, p90 error +17%. Checked: median error
  0.000, so it is noise, not bias.
- **Only 426 of our 800 markets can be measured** — everything before
  2026-09-15 07:29Z has no `ladder_under`. That window contains the 09-19
  disaster, so the downside may be over-weighted by one broken day; excluding
  it the delta is +$225 on +$530 (+42.5%), the same shape.
- **13 losing markets in the window.** Every risk number here rests on 13
  observations, and that cuts toward caution.
- **Hedged markets (12 of 426)** are modelled as both legs scaling together.
  If the insurance is not there at 1.5x, those markets are strictly worse than
  I have shown.
- I did **not** use the replay for anything.

## 7. WHAT I WOULD DO INSTEAD

1. **Fix the hedge's reach before the position grows.** We already log
   `hedge_quote`; measure the ask-side ladder at the alarm second and either
   raise `--hedge-slip` or accept a partial deliberately. A 1.5x bet with a 1x
   hedge is the 09-19 failure repeated with more money. Blocks nothing, gates
   nothing, cannot touch a hedge.
2. **Show dollars-committed-in-this-close as a live number.** At 1.5x the
   number to watch is $469, not $313.
3. **If more size is wanted, take it per coin: BTC, ETH and XRP only** — where
   the ladder supports the full step 76-90% of the time — and leave NEAR and
   BNB at 1x. That buys most of the upside in the deep coins and none of it in
   the two thin ones that produced four of our seven worst losses. It is a
   per-coin size multiplier, not a brake change, and it blocks nothing.
4. **If the full step is taken anyway, cut `--loss-cap` with it** (200 ->
   ~135) so the day-stop still fires after two bad closes rather than one.
