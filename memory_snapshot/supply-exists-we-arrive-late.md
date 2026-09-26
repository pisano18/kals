---
name: supply-exists-we-arrive-late
description: "MEASURED 2026-09-22 (outranks the older corrections below): offers at 90-98c AT OUR CONFIDENCE fell 54% from 09-16; all-taker volume (up 7% vs a median day) is the wrong pool; missed deals are $3-5/day, not $50-60"
metadata: 
  node_type: memory
  type: project
  originSessionId: 4b086199-b082-458d-9cf9-786f0eb4321e
  modified: 2026-09-18T06:12:58.497Z
---

**MEASURED PROPERLY 2026-09-22, and this outranks everything below.** The
question "did the pool shrink" was always being asked of the WRONG pool.
Counting OFFERS at 90-98c on the model's side while the model is >= 99.5%
sure, per watched close (full order-book rebuild on exchange timestamps,
results/map_2026-09-22/missed/A_supply-gap.md):
**0.514 per close (09-13..09-17) -> 0.237 post-fix, -54%**, starting 09-16 --
a day BEFORE the 45 s leg. Our take rate did NOT move (0.504 -> 0.192) and
the model is as confident as ever. All-taker volume at 90-98c (what
`bargains` and pinsupply count, and what "supply is flat" rested on) is NOT
that pool: the prices moved to 98c+ or vanished.
Consequence: the critic's "up to $50-60/day of missed buying" was an
arithmetic ceiling on a false premise. The real missed pile is ~$10/day gross
and the grabbable part is **$3-5/day** (attempts lockout, universe refresh,
budget skip). Uptime was worth more than every gate change combined.

*(Superseded below: the 09-18 correction, right about the baseline error,
wrong to conclude there was no decline in what we can actually buy.)*

**CORRECTED AGAIN 2026-09-18 ~06:1xZ, and this correction outranks the one
below it. "The pool halved" was measured against 09-09..09-12 -- the four
HIGHEST days in the entire record. That is a baseline error, the same class as
quoting a loss rate off the tape: the number was real, the comparison was not.
Run `python research/pinsupply.py` for the live version of this; its
`baseline()` refuses to report a window without also reporting the mean AND
median of every earlier day, so it cannot happen quietly again.**

| measure, last 5 days vs... | bargains/close | contracts |
|---|---|---|
| the 4 days before (09-09..12) | **-62%** | -47% |
| every earlier day (mean) | -19% | +3% |
| **a NORMAL earlier day (median)** | **+7%** | **+22%** |

Two independent checks agree there is no decline:

- **Kalshi's own REST history, 67 days back to 2026-07-13** (2.5x our tape,
  `results/kalshi_volume_history.json`): contracts/day on the nine 15-minute
  crypto series went 160M in mid-July to 259M this week, **+61%, an all-time
  high**. The 09-08..12 week was 219M -- BELOW the week before it. So whatever
  spiked in our bargain count that week, it was not exchange volume.
- **Volatility does not explain the swing either**: r = -0.38 over 24 days,
  which accounts for 14% of it. A quiet week does NOT explain a thin week.

Two measurement traps found while checking, both worth remembering: the
commodity series joined the tape on 09-14 and added 10-15k bargains a day, so
any trend must use the nine crypto series only; and Kalshi's Bitcoin index is
called **`BRTI`**, not `BTCUSD_RTI` -- asking for the wrong name read 90 hours,
matched nothing, raised no error and wrote a volatility file with zero days.

**What `bargains` can and cannot see:** it counts EXECUTED takes of the winning
side at 90-98c with a settlement on file. It cannot see a resting offer nobody
took, it falls if prices drift above 98c, and one missing settlement drops a
whole day. It is one measure, not the measure.

---

*The superseded 2026-09-18 ~03:3xZ correction, kept so the change is visible.
Its table is still the right data; its conclusion is the baseline error.*

## What actually happened

`results/RESULTS_pickoff.md`, bargains per close (a taker buying the WINNING
side at 90-98c inside 60 s of the close):

| day | bargains/close | our share |
|---|---|---|
| 09-08 | 507 | 5% |
| 09-09 | 1,263 | 7% |
| 09-10 | **1,425** | 4% |
| 09-11 | 1,137 | 10% |
| 09-12 | 1,285 | 8% |
| **09-13** | **619** | 7% |
| 09-14 | 614 | 4% |
| 09-15 | 689 | 3% |
| 09-16 | 559 | 6% |
| 09-17 | **491** | 8% |

**The pool MORE THAN HALVED on 09-13 and has kept sliding.** *(WRONG -- see the
correction at the top. It halved from a four-day spike, not from normal.)*
**Our share did not move -- it sits between 3% and 10% across the whole period,
before and after.** *(This half is still true.)*

Our own fills fell from 94/day (09-12) to ~50/day (09-17), which is the same
shape as the pool, not the shape of a share loss.

**So the cause is the POOL, not our speed and not our gates.** Our order
latency is 88 ms and improving; the gate review found only $2-10/day of
loosening available; the ceiling only buys expensive leftovers. All of those
were the wrong tree.

## What it argues for

*(Written under the halving reading. A second product is still worth having --
more venues is real diversification -- but it is no longer URGENT, because the
pool is not drying up.)* Joe's crypto.com FIX push: see
`results/cryptocom_fixapi_email.md`.

**Still true, and still worth acting on:** the median bargain is taken 38-45 s
before the close while our window starts at 30 s, so being late costs us at
the margin even though it is not the main story.

## The other half: we lose more when the cushion is thin

Measured the same night, across every live signal joined to its settlement --
how many standard deviations the spot sat from the strike when we bought:

| cushion | markets | lost |
|---|---|---|
| under 3 sd | 164 | 6 (3.7%) |
| 3-4 sd | 112 | 3 (2.7%) |
| 4-6 sd | 108 | 1 (0.9%) |
| over 6 sd | 174 | 3 (1.7%) |

**Six of thirteen all-time losses sat under 3 sd.** The -$27.87 Bitcoin loss
was at **2.70 sd**: $21 above the strike on a $76,500 coin, which the model
called 99.56% safe because it maps distance through a NORMAL curve. The index
has measured kurtosis 132 against a normal's 3, so the tail that gate depends
on is roughly 44x fatter than assumed. **A minimum sigma cushion is the first
idea that would have prevented real losses rather than trimming volume.** Cost
in forgone winners is not yet measured -- that is the paper arm to run.

## Also remember

A fill far BELOW the ask we saw is not a bargain, it is the alarm that the
world changed while the order was in flight (97.8c seen, 53.0c paid). A limit
price is a MAXIMUM, so no price rule prevents it; only SIZE bounds it.

See [[next-session-first-jobs]].
