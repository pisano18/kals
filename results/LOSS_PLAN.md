# What happens when we lose — written BEFORE the first loss

**Set 2026-09-08, at the operator's instruction: *"You better have a strategy
and a plan if it loses."* Written before any loss has occurred, so it cannot
be rationalised afterwards.**

---

## The single most important sentence in this file

**We have won 18 in a row and that is not evidence of anything.** At the 0.90%
error rate we believe, 18 straight wins is the *expected* outcome — 0.16 losses
expected. A perfect streak looks identical whether the edge is real or whether
we have been fortunate. **The first loss is not a failure of the strategy. It
is the first genuinely informative event this project has produced.**

The plan below is built so that we react to the *rate* losses arrive at, not
to the fact of a loss.

---

## Live configuration this plan covers

| | |
|---|---|
| bank | **$154.33**, all on the Crypto shard (exchange_index 2) |
| size | **20 contracts** |
| buys per close | up to **2**, each ≥0.5¢ cheaper than the last |
| worst case, one close | **$40** |
| dollar brake | **−$60** (39% of the bank) |
| **loss-count brake** | **3 losing trades, then stop** |
| process | pid 4071500 |

**Only ONE thing changed from the configuration that has won 18 of 18: the
size.** Cap 3 measured better and was withdrawn before it traded, because
deploying it alongside a doubling of size would have been two changes at once
with one of them unproven. A measured improvement is not a proven one.

**Why not the configuration that earns most.** Measured with losses injected
per close at the 2.31% upper bound, $154 bank:

| | typical result | ruined | status |
|---|---|---|---|
| **size 20, cap 2** | **$271** | **3.4%** | **LIVE — the proven rule, bigger** |
| size 25, cap 2 | $304 | 2.8% | not deployed |
| size 20, cap 3 | $304 | 1.1% | measured better, **never traded live** |
| size 40, cap 2 | $380 | worst path reaches **$0.00** | rejected outright |

**Size 40 earns the most and is the only setting that can reach zero**, because
the brake scales with the bet: at size 40 it sits at −$120 of a $154 bank and
fires after the money is already gone. **The brake must be small relative to
the ACCOUNT, not merely proportionate to the BET.** At size 20 cap 2 the brake
is −$60, which is 39% of the bank and leaves $94 to continue with.

Cap 3 is the better setting on every number I have, and it is not deployed. It
has never placed a live order. It goes in only after size 20 has proved itself
on the rule that already works.

---

## THE THREE BRAKES, in the order they will fire

**1. The loss-COUNT brake — 3 losing trades, then halt.**
This is the new one and it is the important one. The dollar brake asks *"have
we lost too much?"*. This asks *"is the model still what we think it is?"*.
At ~50 trades a day a 0.90% rate predicts **0.45 losses per day**, so three in
one run is roughly a **1% event** — rare enough to stop and re-measure rather
than trade through.

**2. The dollar brake — −$90 realised, then halt.** Forward-looking: it refuses
to enter a state where one more contract could breach the limit, so it stops
*before* the number is hit, not after.

**3. The order-path brake — the same −$90, enforced independently** inside
`pintake`. Two brakes that cannot silently disagree, because `set_limits()`
refuses to tighten below what the run configured.

**A halt stops trading. It does not close positions.** Anything already open
settles normally within 60 seconds of its close.

---

## What I do, by how many losses have arrived

### One loss — EXPECTED. Do not touch anything.

At 0.90%, one loss per ~111 trades is normal. **Reacting to it would be the
mistake.** What I do instead, without stopping the trader:

1. **Reconstruct the trade tick by tick.** What was the required move at the
   moment we bought, in sigma? How much did the index actually move? The HYPE
   trade needed 2.32σ and got 1.29σ, so we won with 44% of the cushion intact.
   A loss that took 2.5σ against us is an ordinary tail event. A loss that took
   0.5σ means **the model is broken**, and those are completely different.
2. **Check the settlement arithmetic by hand** against Kalshi's published
   60-second average. If our number and theirs disagree, the loss is a *bug*,
   not a tail, and everything stops immediately.
3. **Check the price paid.** A loss above 98.8¢ means the ceiling is not
   binding and something is wrong with the EV gate.
4. **Recompute the flip rate** including this event and re-derive every
   threshold from it.

### Two losses — watch closely, still do not intervene.

Re-run the above for both. **The specific thing I am looking for is whether
they share a cause**: same coin, same tau, same hour, same sigma regime. Two
independent tail events are noise. Two losses that rhyme are a signal.

### Three losses — THE TRADER HALTS ITSELF. I do not restart it blind.

Before a single further order:

1. **Re-derive the flip rate** from every live trade. If the live rate exceeds
   **2.31%** — the exact one-sided 95% bound on the 3-in-333 we built
   everything on — **every threshold in this system is wrong and must be
   rebuilt from scratch.** The price ceiling, the EV floor, the size, all of it.
2. **Re-run the falsification suite** (`pinmirror.py`): the mirror rule must
   still refuse every trade, the forced-wrong rule must still lose, and the
   shuffled-outcome placebo must still be badly negative. If any of those has
   changed, the edge is gone rather than merely smaller.
3. **Re-run `pinstress.py`** at the *newly measured* rate and see what size,
   if any, the remaining bank supports.
4. **Report to the operator with the numbers before restarting anything.**

---

## What ends this, and I am writing the number down now

**The strategy is dead if the live flip rate exceeds 2.31% over 50+ settled
trades.** That is not a feeling, it is the exact upper bound of the measurement
the entire system rests on. Above it, the price ceiling is in the wrong place
and every profit figure in this repository is an artefact.

**It is NOT dead because of a bad day.** A −$90 halt on a $154 bank is a 58%
drawdown and it is survivable. The stress test says that at the rate we
believe, that outcome has a 0.1% chance; at the rate we cannot rule out, 1.1%.

---

## Loss mitigation that is measured but NOT deployed

**Buying the cheap opposite side when a position turns** cuts ruin risk roughly
in half at zero measured cost, if and only if it triggers late — once the model
is **90%** sure the position is lost.

| trigger | false alarms in 165 live positions | profit destroyed |
|---|---|---|
| 5% (the intuitive one) | 9 | **26.5%** |
| 50% | 1 | 6.7% |
| **90%** | **0** | **0.0%** |

**It is not live, for one honest reason.** A hedge asks us to buy the side that
is now *winning*, and we measured that the winning side has no seller in
**33,427 of 33,431** decided moments. Whether the hedge is purchasable at the
moment we need it is **unmeasured**, and I will not build a safety net without
looking for the holes first. That measurement is the next job.

---

## What the operator does

**Nothing, unless I ask.** The brakes are automatic and the trader stops itself.
There is no action that needs a human at 3 a.m.

If you want to check on it yourself:

```powershell
Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
  Where-Object {$_.CommandLine -like '*pinrun*'} | Select-Object ProcessId
```

Nothing returned means it has halted — either a brake fired or it crashed, and
the last lines of `results/pinrun-live-*.jsonl` say which.

**Money rule, unchanged and not negotiable: I will never deposit, never borrow,
never use margin. If more is ever needed I say so and you decide.**
