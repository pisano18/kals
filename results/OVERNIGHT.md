# OVERNIGHT — 2026-09-07 into 2026-09-08

**1.** pin now has a working live body: WebSocket order book (`livebook.py`,
26 ms, top-3 identical to REST), taker order rails (`pintake.py`, IOC limit,
proven with two real DEMO orders), and the runner that joins them
(`pinrun.py`, 28 self-test checks green).
**2.** TWO measured bugs found in the settlement model — the one the
BACKTEST also uses. The window is `[close-60, close-1]`, not `[close-59,
close]` (108/108 markets). And Kalshi ROUNDS the settlement to the strike's
precision before comparing, which our model ignored.
**3.** Replaying the frozen rule over 3 hours of today's tape with full book
vision: **8 closes fired, 7 won** (+0.56 to +4.76c). The single loss
(−90.9c) is the rounding bug, not bad luck.
**4.** The taker fee is fractional (ceil to $0.0001) — **0.14c at size 1**,
not 1c. A 1–3c win survives. That threat to the whole strategy is cleared.
**5.** No live pin order has been placed yet. Account flat at $41.04.

---

## What was wrong with the model, and how it was caught

Both were found by checking our arithmetic against **Kalshi's own published
numbers**, not by inspection.

### Bug 1 — the settlement window is off by one second

Settlement is the mean of 60 one-second prints. We had `[close-59, close]`.
It is `[close-60, close-1]`. Checked against Kalshi's `avg_60s_data` and the
identity `strike(N+1) == settle(N)`:

| index / close | Kalshi floor_strike | mean[c-60..c-1] | mean[c-59..c] |
|---|---|---|---|
| BRTI 00:45Z | 79199.01 | **79199.0060** | 79199.3023 |
| BRTI 01:00Z | 79283.84 | **79283.8392** | 79284.1180 |
| BRTI 00:30Z | 79009.66 | **79009.6628** | 79009.2292 |
| ETH 01:00Z | 2494.95 | **2494.9530** | 2494.9690 |

108 of 108 markets agree with the left column. The error substitutes live
spot for one already-locked print: 13% of the true sd at tau=20, **135% at
tau=5**, 7.6× at tau=2. `settlewin.py`, `endgame.py` and `pin.py` all carry
the old window.

### Bug 2 — settlement is rounded before it is compared

`custom_strike.round_digits` is 2 for BTC/ETH/BNB, 4 for the rest. Kalshi
rounds the 60-print mean to that precision, writes it as `expiration_value`,
and settles YES iff **that** ≥ `floor_strike`. So the real threshold is
`K − 0.5×10⁻ᵈ`.

This is not academic. It is the ONLY loss in today's replay:

> `KXETH15M-26SEP071745-45`, strike **2492.82**, tape settle **2492.8158**.
> Rounds to 2492.82 → **YES**. Our model: fair 0.017, i.e. "98% sure NO",
> and would have bought NO at 0.903 for **−90.91c**.

Over the replayed hours that one line is the difference between **+7.7c and
−79.2c**.

## What the replay actually showed (3 h, 12 closes, 108 markets)

Frozen rule (tau≤20, fee-netted 0.5c floor, ≥1 whole contract resting),
one fire per close:

| close | market | side | price | result |
|---|---|---|---|---|
| 21:15Z | KXHYPE15M | NO @0.9890 | | **+1.02c** |
| 21:30Z | KXSOL15M | YES @0.9770 | | **+2.14c** |
| 21:45Z | KXETH15M | NO @0.9030 | | **−90.91c** ← the rounding bug |
| 22:00Z | KXXRP15M | YES @0.9910 | | **+0.84c** |
| 22:15Z | KXDOGE15M | NO @0.9940 | | **+0.56c** |
| 22:30Z | KXBTC15M | NO @0.9940 | | **+0.56c** |
| 23:45Z | KXHYPE15M | NO @0.9800 | | **+1.86c** |
| 00:00Z | KXSOL15M | NO @0.9490 | | **+4.76c** |

Correct side on **31 of 39** episodes and **12 of 13** markets; all eight
wrong belong to that one ETH market. n=12 closes says **nothing** about the
size of the edge — one flip dominates the sum. It validates logic and fire
rate only.

Episode lifetime: median 163 ms, 18/39 ≥ 200 ms, 14/39 ≥ 500 ms. Round trip
to Kalshi measured at **90 ms median** (min 81, p90 156). So roughly half
the opportunities are reachable event-driven — and almost none by REST
polling, which is the whole explanation of the earlier zero-signal run.

## Why the earlier paper run saw nothing

Not evidence about pin. `pinlive.py` polled `/markets/{t}/orderbook` at ~9
GETs/s across 9–12 markets and was rate-limited into blindness: **202 of 211
skips were `no_book`**. Replaying those same hours with full vision found 39
qualifying episodes. Fixed by reading the `orderbook_delta` WebSocket.

## Bugs found in our own new code, before money

- `close_s` computed with `time.mktime(...) - time.timezone`, which ignores
  DST — **off by 3600 s**. pin would have been silently dead all night.
  Fixed with `calendar.timegm`; verified tau=211 s against a live market.
- `risk_abort` read `LEDGER["halted"]` and `["stake"]`. The real keys are
  `halt` and `committed`, so **both checks were silently dead** — the same
  shape as last night's abort sitting behind a `continue`. Fixed, plus a
  self-test that scans the abort's own source and fails if it reads a ledger
  key that does not exist.
- `pintake`'s verifier REFUTED the first version: a 2xx with
  `remaining_count > 0` is a **RESTING** order, and the ledger read it as
  cancelled and released the stake. Fixed and re-proven.
- Two self-tests that matched their own source text (a literal in the test
  was found by the test). Fixed by building the needle at runtime.

## Rails in force for any live run

| rail | value |
|---|---|
| size | 1 contract (`HARD_MAX` 5 that nothing may exceed) |
| stake cap | $5.00 committed per process |
| loss abort | realised ≤ −$2.00, checked FIRST in the loop |
| order type | IOC limit at the seen price, `post_only=False` — never rests |
| window | only markets closing within 90 s |
| one fire | per close, across all coins (the unit the backtest measured) |
| staleness | book ≤ 2 s, index ≤ 2 s, no `suspect` book |
| dust | the level must hold ≥ 1 whole contract |

## Open, and honest

- **The backtest's +2.54c / t=+5.0 was computed WITH both bugs.** It is being
  re-run corrected. Until that returns, the OOS number should not be quoted.
- The loss abort reads *realised* P&L, but pin holds to settlement — which
  happens after a short run ends. So within a single run the **stake cap is
  the real limit**, not the loss abort. Worst case for a run is therefore
  bounded by $5, not by −$2.
- Fill rate in the race is still unmeasured. Predicted 40–60%.
