# PRE-REGISTRATION -- RACE HARDER: an IOC limit above the resting ask
## Written 2026-09-13 ~04:10 ET, BEFORE the code exists and BEFORE any live fill

**Rule:** a bar is never moved after seeing a result without saying so loudly,
and no threshold is deployed from a replay without a holdout split AND a
pre-registered live bar written before the number is seen (CLAUDE.md amendment
2026-09-10, item 4). This file states the bar first. **Nothing is deployed.**

## The change being proposed

Today `pintake.build_take()` sends an IOC limit at **exactly the ask we saw**.
If that level is gone by the time the order lands, we get nothing: 28.2% of our
orders zero-fill (`pinver`: fill ratio 71.8%, 249 filled / 113 zero-filled of
362 live orders carrying a latency).

The change is one number: send the limit at

    limit = min(PRICE_CEILING, highest price that still clears the SAME gate)

instead of at the observed ask, where "clears the same gate" is `pinrun`'s own
`net_edge`/`expected_value` at the *worst* price we could pay -- so every fill
this change adds passes the identical bar every fill today passes. It is not a
new rule; it is the existing rule applied to the price we might actually pay
rather than the price we hoped for.

## Why it is free on the fills we already get -- MEASURED, not assumed

A crossing IOC limit fills at the RESTING order's price, not at our limit. On
283 live fills the executed price was **at or below the signalled price on
every single one** -- 207 exactly at it, 76 strictly better (best -43c), and
**zero worse**. So raising the limit cannot make a fill we already win worse.
It can only add fills we do not get today.

*(That is now a confirmed contract fact and is recorded in RUNBOOK.md. It was
an assumption until it was checked; it is the load-bearing one here.)*

## What the tape says the change is worth

`research/pincontest.py`, 11,935 live-gate candidates on 716 closes,
2026-08-25 .. 2026-09-12. Of the 10,492 rows another taker hit within 1 s:

| | rows | share of contested |
|---|---|---|
| next level inside the 98c ceiling | 9,474 | 90.3% |
| **and still clears the same gate** | **4,514** | **43.0%** |
| inside the ceiling, under the edge floor | 4,960 | 47.3% |
| above the ceiling | 1,006 | 9.6% |

Median extra paid on a gate-clearing sweep **0.20c** (mean 0.70c, p90 2.00c)
against a mean edge at signal of +4.60c, and the level holds a median 115
contracts. Holdout split, first 70% of closes vs last 30%: gate-clearing share
**43.6% vs 42.0%**, median extra **0.20c vs 0.10c**. Stable.

**Expected effect, stated as arithmetic and not as a promise:** we lose 28.2%
of races; roughly 43% of those have a gate-clearing level above; so fill ratio
71.8% -> ~84%, about **+17% more fills** at the same per-fill bar. At today's
size that is order **+$4-6/day**. Small, and the reason to do it is that it is
nearly free, not that it is large.

## THE RISK THIS CANNOT MEASURE, STATED BEFORE THE BAR

The added fills are, by construction, fills in a market where somebody just
lifted the better offer. They are a different population from today's fills,
and the tape cannot tell us their loss rate -- rule 5, and the 31x gap it was
written for. One loss undoes ~27 wins, so a change that adds 17% volume and
raises the close-loss rate by even 0.5 pp is net negative. **That is the whole
risk and it is the reason this is a pre-registration and not a deployment.**

`pincontest`'s forward split leans the reassuring way (offers another taker hit
won 97.94% vs 90.99% for offers nobody touched) but that split is contaminated
by outcome leakage -- see RESULTS_contest.md section 2 -- and the clean
backward-looking version has **no power** (+1.27 pp, [-1.62, +4.57], MDE 4.05
pp). So the tape does not settle it and is not allowed to.

## THE LIVE BAR -- pass/fail, decided before the first swept fill

Scored over the first **60 live fills that were SWEPT** (the level we first saw
was gone and we filled higher), tagged in the live log as `swept: true` with
`ask_seen` and `exec_price` both recorded:

1. **Swept-fill loss rate <= 8.0%.** Today's all-version market-loss rate is
   4.13%; 8.0% is the point at which the added volume stops paying for itself
   at a 4.6c edge and a 96c loss. Above it, revert.
2. **Mean extra paid <= 1.0c.** The tape says 0.70c mean. Above 1.0c the
   ladder is not what the replay thought it was.
3. **Fill ratio rises to >= 80%** from 71.8%. If it does not, the mechanism is
   not what this file claims and the change should be reverted whether or not
   it is profitable, because something else is going on.
4. **No swept fill is ever above PRICE_CEILING, and none ever clears a gate it
   should not.** A single violation is an immediate revert, not a data point.

**If bar 1 fails, the change is reverted and this file records that it failed.**
Bars 2-4 failing means the implementation is wrong rather than the idea.

## Kill criterion for the idea itself

If after 60 swept fills the loss rate on swept fills is statistically
indistinguishable from unswept ones AND the $/day improvement is under $2, the
change stays but the idea is closed -- no further work on racing.

## What is NOT being proposed

- No change to PIN, the ceiling, tau, the edge floor, the EV floor, the depth
  floor, MAX_PER_CLOSE, BANK_BRAKE or the hedge.
- No sweep past a price that fails the current gate. Ever.
- No increase in size, positions or bank.
