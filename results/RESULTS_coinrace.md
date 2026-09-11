# The Coin Race — measured 2026-09-11

`KXCRYPTOLEAD15M`: which of BTC, ETH, SOL, XRP, HYPE has the highest return
over a 15-minute window. Five legs, one winner, `fee_type: quadratic` with
multiplier 1 — **makers pay nothing**, checked against `/series`.

Two files, deliberately separate so the forecast could not be re-tuned after
the price was seen: `research/pinlead.py` (does it work) and
`research/pinleadprice.py` (what does it cost).

---

## A. The settlement rule — SOLVED, 773 of 773

Settlement is the highest value of

    (mean of the 60 one-second CF Benchmarks prints over [close-60, close-1])
  ÷ (mean of the 60 one-second prints over [open-60,  open-1])

| denominator tried | reproduces Kalshi's own `expiration_value` |
|---|---|
| **60-second TWAP at the open** | **773 / 773 = 100.00%** (95% CI on misses [0.00, 0.48]) |
| single spot print at the open | 713 / 773 = 92.24% |

Both candidates were scored side by side and the file picks neither by
preference — it reports both. **The denominator is known the moment the
window opens**, because `strike(N+1) == settle(N)` on this product. Only the
numerator is unresolved, and it is the same quantity `pin` already forecasts.

Margin between first and second place, in return units: p05 0.00005,
median 0.00065, p75 0.00132. **Races are tight** — half are decided by under
7 basis points.

---

## B. Naming the leader early — IT WORKS

773 events, 9 days. The base rate is 20% because there are five legs.

| tau | named right | 95% CI |
|---|---|---|
| 60 | 91.5% | [89.3, 93.3] |
| 45 | 95.5% | [93.8, 96.8] |
| 30 | 97.8% | [96.5, 98.7] |
| 25 | 98.8% | [97.8, 99.5] |
| **20** | **99.5%** | [98.7, 99.9] |
| 15 | 99.6% | [98.9, 99.9] |
| 10 | 99.6% | [98.9, 99.9] |
| 5 | 100.0% | [99.5, 100.0] |
| 3 | 100.0% | [99.5, 100.0] |

Stable day to day: 98–100% at tau 20 on every one of nine days.

---

## C. What the market charges — THE STAGE THAT NEARLY KILLED IT

Instrument: the **trade tape**, for the reason established in `pintrades.py`.
A YES-taker print at price P proves an ask existed at P that second. A book
replay is structurally blind to executions; this is not.

Purchase rule **FIRST** = cross at the earliest YES-taker print in the band,
scored against the forecast we would actually hold at that second.

| tau band | events with a price | coverage | accuracy | avg paid | break-even | **edge/contract** | loss rate |
|---|---|---|---|---|---|---|---|
| 45–61 | 385 | 50% | 89.4% | 89.07c | 88.64c | **−0.18c** | 10.6% [7.8, 14.2] |
| 30–45 | 269 | 35% | 90.3% | 88.64c | 89.68c | +1.22c | 9.7% [6.4, 13.8] |
| 20–30 | 141 | 18% | 93.6% | 90.63c | 93.17c | +2.56c | 6.4% [3.0, 11.8] |
| 15–20 | 79 | 10% | 97.5% | 94.71c | 97.28c | +2.52c | 2.5% [0.3, 8.8] |
| 10–15 | 53 | 7% | 96.2% | 91.17c | 95.95c | **+4.72c** | 3.8% [0.5, 13.0] |
| 5–10 | 50 | 6% | 96.0% | 90.92c | 95.71c | **+4.83c** | 4.0% [0.5, 13.7] |

**The market is efficient early and slips late.** At tau 45–61 it charges
89.07c for something worth 89.4% — dead on, and slightly negative after the
fee. The edge appears only inside the last 30 seconds, and it grows as the
close approaches. That is exactly the mechanism: our information hardens as
prints lock in, and the quoted price does not harden as fast.

### Cheap legs are cheap because they lose — the same cliff as `pintrades`

Standing aside unless the price is below a limit looks superb per contract
and is a trap. At tau 45–61:

| limit | events | accuracy | avg paid | edge/contract | loss rate |
|---|---|---|---|---|---|
| take anything | 385 | 89.4% | 89.07c | −0.18c | 10.6% |
| ≤ 98c | 291 | 86.3% | 81.98c | +3.61c | 13.7% |
| ≤ 95c | 147 | 75.5% | 66.44c | +7.91c | 24.5% |
| ≤ 90c | 120 | 70.8% | 60.39c | +9.12c | 29.2% |
| ≤ 80c | 94 | 64.9% | 53.33c | +10.11c | **35.1%** |

Identical in shape to the discount cliff on the up/down series: **the price
falls because the leg is losing.** The per-contract column rises the whole
way down and the loss rate triples. A rule chasing that column would lose a
third of its bets.

---

## The two bugs this measurement was born with, both caught here

1. **LOOK-AHEAD.** v1 scored every purchase against the tau-20 forecast,
   including purchases at tau 45–61. At tau 50 that forecast is 30 seconds of
   future index prints away. It reported **98.9%** accuracy in the top band
   where the truth is **89.4%**, and turned a marginal result into a
   spectacular one. Fixed by emitting one forecast per tau and matching each
   trade to the smallest grid tau ≥ its own. A self-test now asserts, for
   every tau, that the forecast used is never from the future.
2. **TAU RUNS BACKWARDS.** The "FIRST" rule used `min()` on `(tau, price)`,
   which is the SMALLEST tau — the LAST trade before the close, the most
   informed and the dearest. It reported **98.6%** at tau 20–30 where the
   truth is **93.6%**. Fixed to `max()`.

Both inflated the result. Neither was catchable by reading the table.

## The caveat that survives — tradeability selects against us

Accuracy over all 773 events is not accuracy we can realise, because we can
only buy when somebody is trading, and those are the closer races.

| tau band | all events | tradeable subset |
|---|---|---|
| 45–61 | 91.5% | 89.6% |
| 30–45 | 95.5% | 90.3% |
| 15–20 | 99.5% | 97.5% |
| 10–15 | 99.6% | 96.2% |

**Never quote the 99.5% as the accuracy of a trade.** The right number is the
90–97% in the band being traded.

## What is still unproven

- **The race.** These are other people's fills. Winning them is assumed.
- **Coverage is 6–18% of events** in the profitable bands, so this is roughly
  6–10 opportunities a day, not 96.
- **The intervals are wide.** At tau 10–15 the loss rate is 3.8% with an upper
  bound of 13.0%; at 13% a 91c purchase loses money. The sign is not secure.
- The five legs summed 87c once in 26 events, on **non-simultaneous** prints,
  so that is a place to look and not a lock.

## Verdict

**Real but small, and not yet deployable.** At size 20 the profitable bands
are worth roughly $0.50–$0.95 per traded event on 6–10 events a day — call it
**$5–10/day**, against `pin`'s ~$25–30/day, with a loss rate of 2.5–6.4%
rather than `pin`'s 3.4%. It is additive rather than competing, because it
prices an ORDER rather than a LEVEL and so is short the common move that
makes twelve `pin` markets settle as ~1.22 independent bets.

**Next step is a penny test, not a deployment** — and per the standing rule
that needs per-order sign-off, so it has not been placed.
