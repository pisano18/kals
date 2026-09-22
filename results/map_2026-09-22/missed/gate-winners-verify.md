# Adversarial verification of `C_gate-winners.md`

**Status: COMPLETE (2026-09-22 ~18:10Z).** Read-only. My own scripts and data in scratchpad
`missed/verify-gate-winners/` (vparse, vfills, lock, samekind, risk2, tape1, t1m, t1a, t2, t3). Everything
below is re-derived from the raw sources -- all 126 `pinrun-live-*.jsonl`, the Kalshi ledger
(`pinledger.pnl`, 758 markets, +$503.78), the `ticker` and `market_lifecycle_v2` tape, and `pinrun.fair`
through `pinsim.TapeIndex` for decision reproduction only. **Tape = what was offered and how a market
settled. Every risk number is our own fills.** n = closes.
At finish: free RAM 1.70 GB, disk 27 GB, both recorders alive (105304 at 53 MB, 105352 at 45 MB). My tape
passes carried their own 1.0 GB free-RAM guard and stopped themselves twice before finishing on a retry.

## Summary of verdicts

| candidate (from the report) | verdict |
|---|---|
| 1a. Count an attempt only when an order is SENT (the lockout bug) | **survives**, but worth ~$2 a day, not $3, and now with the right risk evidence |
| 1b. Let `staged_none` reach into the deeper ladder | **weakened** -- own fills of that exact kind are net negative on one loss |
| 2. Raise `price_ceiling` in the last 10 s | **refuted as a grab** -- my own tape count of the whole pool tops out at ~$11 in 2.5 days |
| 3. Loosen `edge_floor` / `price_ceiling` generally | **refuted** -- confirmed tape illusion |
| 4. Loosen `confidence` | **refuted** -- reproduced; our own fills below the line lost |
| 5. Loosen `dump_guard` / `early_cheap` / `against_thin` | **refuted as a grab** (nothing there), and the report's own-fill evidence for two of them is the wrong population |
| 6. Loosen the capacity gates | **refuted** -- confirmed, every refusal was on a market already held |

---

## 1a. Count an attempt only when an order is SENT -- SURVIVES, at about $2 a day

**Mechanism: confirmed independently.** `pinrun.py` 11358-11359 increments `attempts[close_s]` and
`attempts_tk[(close_s, tk)]` before the early-leg gates at 11404-11470 (`early_cheap`, `early_dear`,
`early_wide`, `staged_none`, `price_band`). My parse of all 126 logs: 42 `market_attempts` lockouts ever;
**32 followed an early-leg refusal in the SAME second and had 0-1 real orders** (the other 10 are genuine
3-order caps, 09-15 and 09-20). 12 of the 32 are after 09-20 04:00Z. The close-level cap (`attempts_cap`,
24) has never fired, so the phantom counts never locked a whole close. The hedge increments
`attempts[close_s]` (10418) but never reads it or `attempts_tk`, so the fix cannot touch a hedge -- confirmed.

**Size: the report's +$15.65 reproduces, but it overstates what the fix is worth going forward.**
Re-valuing the report's 12 model-passing markets at MY per-band margins from our own <= 30 s fills (ledger,
since 09-10: <93c +6.48c/contract, 93-95c +4.07, 95-96c +1.66, 96-97c +2.90, 97-98c +0.91) gives **+$16.85
at the first passing moment**. Then:

- **10 of the 32 lockouts, and $6.95 of the $16.85, came from configs that no longer run**: the A50 bug that
  applied `early_wide` to the FULL leg (fixed 09-18 ~19Z -- ZEC 09-18 11:15 ET $2.92 and BTC 14:45 ET $3.18)
  and the 3c early edge cap, now 10c ($0.72 + $0.13). Under today's flags `early_wide` is in fact dead:
  `early_cheap` catches everything under 90c first, and above 90c a 10c edge is arithmetically impossible.
- **Three of the twelve are not new deals.** XRP 09-18 22:30 ET already held 81 at 97.64c and its passing
  moment was 97.9c -- the per-market re-buy band refuses that. ZEC 09-19 07:30 ET was a second bet on a
  market already holding 108; BNB 09-20 19:00 ET a top-up of an 8.5-contract early fill. F5's own argument
  ("loosening capacity means buying more of an outcome we already hold") applies to these.
- **Under today's config: ~$9-10 over 5.1 days, about $2 a day, and $6.35 of that is ONE market** --
  KXBTC15M-26SEP191645-45 (`early_cheap` at 85c at 35 s, then 1,634 contracts offered at 89c at 29.5 s with
  the model at 99.80%). Without it, ~$0.7 a day. 22 of the 32 lockouts are of a kind today's config still
  produces, about 4 a day.
- My own tape check, independent of the replay: 14 of the 32 locked markets had our side offered at <= 98c
  with >= 1 contract after the lockout at 3-30 s, and all 14 settled our way (32 of 32 outcomes from the
  lifecycle tape). That is the tape's upper bound, not a risk number.

**Risk: the report's evidence was the wrong population; the right population now exists and does NOT look
worse.** The report cited all <= 30 s fills (my recount: 12 losing closes of 387 since 09-10, +2.50c a
contract, ledger +$559). But a released market is one that tripped an early-leg gate first -- 7
`early_cheap` (our side offered UNDER 90c at 31-45 s while the model was already sure), 10 `early_wide`,
15 `staged_none`. So I built the same-kind sample two ways:

1. **Before the early leg existed (09-08 .. 09-17 13:05Z), replaying pinrun's own model at every second from
   45 s to 31 s on all 413 of our <= 30 s filled markets** (decision reproduction only; same code path the
   report validated at 141 of 155 signals within 0.001). Markets where the model was >= 99.5% while the tape
   offered our side under 90c -- exactly what `early_cheap` refuses and then locks today: **20 closes, 0
   lost, +6.81c a contract, ledger +$52.43**, against 11 of 315 closes lost and +2.63c for all 413. (95%
   upper bound on 0 of 20 is 16.8% -- it cannot prove safety, but there is no sign of a worse rate.)
2. **After 09-17, markets that tripped an early-leg gate and were bought anyway** (the gate fired once or
   twice, so the cap was not reached): **18 closes, 1 lost, ledger -$34.11, -3.04c a contract.** That single
   loss is KXBNB15M-26SEP191230-30, which belongs to candidate 1b, not to the counter fix.

Combined: 38 closes, 1 lost (2.6%) against our own 3.1-3.5% baseline. That is the honest statement -- **the
released trades measure like the trades we already take, on 38 closes**, and the fix does not create a new
kind of exposure. It is still 38 closes and one event.

**What it blocks: nothing.** It removes a refusal. Real sends are still counted, so the 160-order runaway
guard is unchanged, and the hedge never reads either counter.

## 1b. Let `staged_none` reach into the deeper ladder -- WEAKENED, and it should not ride along with 1a

Mechanism confirmed: `take_n` stays the TOUCH size (line ~11095), `depth_floor` passes on the ladder reach,
then `staged_none` refuses on ANY leg when the touch holds under 1 contract -- a refusal that exists only
because the early leg is switched on. **Own fills of exactly this kind** (touch under one contract, bought
through the deeper ladder): 8 full-leg `staged_none`-then-filled markets since 09-17 plus 3 dust-touch fills
from before the early leg existed = **11 closes, 1 lost, net about -$35.5**, the loss being 84.5 contracts
at 97.3c on KXBNB15M-26SEP191230-30 (ledger -$61.75). One event on 11 closes proves nothing either way, but
it is the only same-kind evidence there is and it is negative. This is a separate decision from the counter
and needs its own bar.

## 2. Raise `price_ceiling` in the last 10 s -- REFUTED as a grab (and the report's size was a lower bound)

The report's "at most +$5.52" came from refusal records, and the log keeps only the FIRST refusal per
(market, gate): 353 of the 366 never-bought `price_ceiling` markets post-fix had their first refusal outside
the last 10 s, so their later last-10-s refusals are invisible. I sized the pool from the tape instead --
every post-fix market we never bought that any price gate refused, our side's ask at 3-10 s with >= 1
contract:

| hypothetical ceiling | markets | closes | contracts | avg price | $ if it NEVER lost | break-even loss rate |
|---|---|---|---|---|---|---|
| 99c | 13 | 12 | 618 | 98.75c | +$7.19 | 1.16% |
| 99.5c | 25 | 22 | 1,177 | 99.05c | +$10.37 | 0.88% |
| 99.65c (edge floor binds above this) | 28 | 25 | 1,429 | 99.15c | +$11.31 | 0.79% |

So even with the masking fixed the whole pool is ~$4.50 a day at its most optimistic, it costs $6-14 for
every 1% of losing closes, and our cleanest slice (last 10 s: 0 losing closes of 73) cannot demonstrate a
rate under 0.8%. Not worth a live change; if anyone wants it, it is a pre-registered paper arm with the flag
proven to fire, and the arm still cannot measure our loss rate on a real adverse fill.

## 3. Loosen `edge_floor` / `price_ceiling` generally -- REFUTED, confirmed

My recount of our own fills that paid 97.5-98c on average, all time: **4 losing closes of 303 (1.3%, 95%
range 0.4-3.3%)**; the report's per-fill cut gives 5 of 283 (1.8%). Break-even is 0.20% (edge_floor, avg
99.79c) and 0.73% (price_ceiling, avg 99.21c) -- at or below the bottom of our measured range either way.
We have 7 filled markets above 98c ever (all 09-08), 0 lost: far too few. One caveat the report does not
state: its dollar columns extrapolate a 97.5-98c loss rate to 99-99.8c offers. That cuts both ways and does
not rescue loosening, which needs positive proof of a rate under 0.73% that no slice of our fills provides.

## 4. Loosen `confidence` -- REFUTED, reproduced with one label wrong

Reproduced exactly with the report's per-fill pairing: model under 99.5%, paid >= 90c -> 40 fills, **35
closes, 2 lost, -5.43c a contract, -$33.36 at fill level** (the report calls this "ledger -$46.36"; the
ledger over those 40 markets is -$35.71, and it includes a 73c fill made at 99.8% confidence). Just above
the line: 326 fills, 269 closes, 5 lost, +1.71c, +$284.48. Per-market with my own pairing it is 1 of 36
closes and +$7.36 -- the whole result turns on one close (KXNEAR15M-26SEP082045-45), and every fill in the
sample is from the 09-08..09-10 pin-0.98 era at size 1-20. Neither version is evidence that loosening is
safe, and 213 of the report's 353 in-window offer moments had the model BELOW the asking price, which is not
a deal by our own model.

## 5. `dump_guard` / `early_cheap` / `against_thin` -- nothing to grab, and two evidence bases are misattributed

- **`early_cheap` "2 of 2 closes lost"** is KXBTC15M-26SEP172115-15 (ask SEEN 97.8c, filled at 53c) and
  KXDOGE15M-26SEP180015-15 (ask seen 97.6c, filled at 11c) -- book collapses inside the round trip. The gate
  reads the ask BEFORE sending, so it could not have blocked either; DOGE's ledger is +$4.36 because the
  hedge paid. **We have zero early-leg fills where the ASK itself was under 90c.** The gate's value is
  unmeasured on our own fills, in either direction.
- **`dump_guard` "7 of 16 closes, -$91.77"** uses the execution price too and includes those same collapse
  fills. At the ask the guard actually sees (signal price >= 15c under the model), all time: **8 closes, 3
  lost, ledger -$34.27.** Same direction, smaller, tiny n.
- Either way there is nothing to collect: post-fix these gates blocked 2, 4 and 15 markets, and the
  `against_thin` refusals averaged 98.97c -- above the ceiling we already refuse.

## 6. Capacity gates -- REFUTED, confirmed

Every post-fix `close_budget` (31), `max_per_market` (8), `rebuy_band` (52) and `early_once` (74) refusal was
on a market already holding a fill at that moment. Since v-safety1, 341 of 341 refusals carry `budget_left`
and none is <= 0. Stale-data attribution also reproduces exactly: 120 of 147 `book_stale` and 44 of 75
`index_stale` post-fix refusals sit inside the 09-22 00:50-05:38Z outage.
**Limit worth passing to B5:** the refusal log dedupes per (market, gate), so "the budget never ran out" is
proven only at each market's FIRST refusal, not at every look in the close.

## Not re-derived

- The 79-market / 353-moment in-window offer set of F2 (tape + replay) -- I checked its risk side, not its
  count.
- The `spot >= 1.5 sd` side lead. It remains a hypothesis for B1, as the report says.
- Our loss rate above 98c: still unmeasurable (7 fills ever, none since 09-09).

## What I would change in the report

1. Quote the lockout fix as **~$2 a day under today's flags** (with two thirds of it one market), not $3, and
   say that $6.95 of the $16.85 came from configs that no longer exist.
2. Split the `staged_none` ladder change out of candidate 1 -- it is the one piece with negative same-kind
   evidence.
3. Replace the F3 risk sentence ("the same kind of trade the bot already takes", backed by all <= 30 s
   fills) with the same-kind numbers above: 38 closes, 1 loss.
4. Drop `early_cheap`'s "2 of 2 lost" and `dump_guard`'s -$91.77 as evidence; both are execution-price
   populations the gates cannot see.
5. Say that the last-10-s ceiling figure is a LOWER bound from a deduped log; the tape's own bound is
   +$11.31 in 2.5 days, which still kills it.
