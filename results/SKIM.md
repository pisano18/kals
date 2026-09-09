# SKIM — everything that matters, short

**Read this instead of the long messages. Updated as things change.**

---

## RIGHT NOW

| | |
|---|---|
| bank | **$110.45** |
| record | 30 wins, 3 losses |
| live | size **20**, 2 buys per close, ceiling **98.0¢**, tau 3–30 |
| restart it | **`RESTART.md`** in the repo root — one line to paste |
| brakes | −$60 · 3 losing **closes** · 2 order errors · 8 attempts/close |
| day | started $38.83, funded +$113.04 → **−$41.54** |

---

## THE ONE LOSS, IN FOUR LINES

Three buys, **one market**, one close. 96.2¢ / 95.6¢ / 73.0¢. All lost together. **−$52.60.**
The index sat still for 8 seconds, then moved 0.0021 **in one second** and never came back.
Settlement checked independently: **the arithmetic is not broken.**
The brake stopped it. Nothing was left open.

---

## WHAT I GOT WRONG (and corrected)

| I said | truth |
|---|---|
| hedging cuts ruin risk **30×** | assumed unlimited depth. Only **6 of 12** hedges are deep enough at size 20 |
| model is **3×** overconfident | **1.43×**, CI [1.18, 1.70]. My 3× rested on 10 closes |
| tighten the gate to 1.5% | costs **22–44 winning trades per loss avoided** |
| the scale-in rule caused the loss | **not supported** — loss rate is flat by buy index |
| stale sigma was the warning sign | **dead**, p = 0.14–0.99 |
| a $28.92 balance drop was unexplained | it was committed stake, to the cent. I reported before subtracting |

**Seven size-1 constants broke scaling in one day.** Any constant tied to size must be written in terms of size.

---

## THE BEST THING LEARNED (2026-09-09, Joe's argument)

**"Unless it eliminates 100% of losses it just makes earning back our blunders
more difficult."** Correct, and it kills every probability gate: each costs
22–44 winning trades to avoid a loss worth ~24 wins, so it's a wash AND it
burns the wins we recover with.

**But the recovery ratio is a PRICE lever, not a probability one, and it is
arithmetic:**

| price paid | a win pays | wins to recover one loss |
|---|---|---|
| 98.8¢ | 1.11¢ | **89** |
| 98.0¢ | 1.86¢ | 53 |
| 96.0¢ | 3.73¢ | 26 |
| 90.0¢ | 9.37¢ | **10** |

Ceiling moved 98.8¢ → **98.0¢**: measured 129 trades/742¢ → 118 trades/**768¢**,
and wins-to-recover 16 → 14. **More money and better resilience at once.**

---

## THE ANALOGUE STUDY — a lesson worth more than the result

Joe's idea: find historic moments that look exactly like the one we lost on,
see what happened next. **It looked like a hit: 200 nearest analogues crossed
36% of the time against a 10% base rate, 3.5x, p=0.0003.**

**The verifier killed it with the null the study never ran.** The target
fingerprint was chosen BECAUSE IT FLIPPED. If flip probability varies across
feature space — and volatility clustering guarantees it does — then picking a
target from flipped cells buys a lift with **zero predictive content**.

Re-run with targets drawn from other flipped cells: **median placebo = 1.96x.**
Nearly two thirds of the 3.5x was free. Corrected p = **0.159. Not significant.**
The jump result went from 2.20x to **0.59x** in units of current volatility.

**THE RULE THIS GIVES US: when you search for things resembling a known bad
outcome, your control must also be drawn from bad outcomes.** Otherwise you
measure your own selection.

Also costed and rejected: repricing with `max(sigma_30, sigma_300)` refuses
**963 winners for 6 losses avoided**, net −4,538¢.

---

## OPEN QUESTIONS — where pushback is worth most

1. **THE RACE.** 26% of orders fill nothing. Depth is not the cause (misses had 562, 107, 93 contracts on offer). Our round trip is ~100ms whether we win or lose; misses happen on *fresher* prices. Suggests we lose to **already-resting** orders, not faster ones. Unmeasurable from tape so far.
2. **THE HEDGE, RE-AIMED.** Earlier study optimised **expected value** and rejected it. Joe's objective is different: *"losing 1–5 wins worth more frequently beats one loss costing tens to a hundred wins."* **Under that objective the earlier answer does not apply.** Being re-tested.
3. **PLAYING TOO CLOSE TO THE LINE.** Is there a minimum absolute distance to the strike below which we should never trade, regardless of what the model says?
4. **CAP 3 vs CAP 2.** Cap 3 measured better (12% more money, a third of the ruin) and is currently OFF only because the bank cannot fund its brake. Restore it at ~$150.
5. **SNAPSHOT BUG, OPEN.** `pindata.Book.snapshot()` reads the wrong keys, so every replayed book is delta-only. Direction is conservative. Any new replay must use the `_fp` keys.

---

## WHAT IS SETTLED, DON'T RE-LITIGATE

- Settlement = mean of 60 one-second prints over `[close-60, close-1]`. Reproduced on 9,124 of 9,124 markets.
- Fee = `ceil(0.07·p·(1−p)·n, $0.0001)`. Makers pay zero.
- **In a decided market the losing side's book is EMPTY** — 33,427 of 33,431 moments. That is why we miss closes, and no threshold change fixes it.
- Market impact does **not** block scaling: 10 → 125 contracts keeps 10.2–11.3× of the naive 12.5×. **Capital is the constraint.**
- Cheap prices win more *and* lose less. Break-even at 90¢ is a 10% error rate; at 98¢ it is 2%.
- **Price and risk are different things.** Our dearest trade (98.7¢) was our safest (0.001% model risk).

---

## HOUSE RULES

- Never deposit, never margin, never borrow. Say when funds are needed.
- Never claim an unmeasured result. Report failures, don't estimate.
- A bar is never moved after seeing a result without saying so loudly.
- **Argue with Joe.** He has asked not to be agreed with by default.
