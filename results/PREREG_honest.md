# PRE-REGISTRATION -- AMENDMENT 19, honest confidence
## Written 2026-09-13 ~06:00 ET, BEFORE any live run with `--honest`

**Nothing is deployed.** `HONEST_CONF` is False and a self-test asserts it.

## The measurement this rests on

`research/pincalib.py`, 109,122 z-scores over 1,672 closes, 19.2 days, from the
1-per-second settlement index alone -- no order book, no replay, no fills. `z`
is how many of its own standard deviations the model sits from the strike;
only the side we lose on is counted.

| the model says it is this sure | it will be wrong | it IS wrong | off by |
|---|---|---|---|
| 99.00% | 1.00% | 2.10% | 2.1x |
| 99.50% | 0.50% | 1.67% | 3.3x |
| **99.85%** (where the gate operates) | **0.15%** | **1.21%** | **8.0x** |
| 99.99% | 0.01% | 0.70% | 69.6x |

The body is nearly right -- sd(z) = 1.151, 15% too narrow. The tail is not:
kurtosis 132 against a normal's 3.

## The change

`fair()` maps z through the measured table instead of `Phi()`. One function,
`conf_of`, and a self-test asserts `ND.cdf` appears nowhere else in the working
code, so no gate can read a different distribution from the one `fair()` uses.

Effect at PIN 0.995: it demands **z >= 4.33** where today it demands z >= 2.58.
Every stated confidence falls, so every computed edge falls with it -- roughly
1c per contract at the gate's typical z, edge that was never there.

## What I do NOT know, stated before the bar

**How many trades survive.** The only way to count that offline is the replay,
and per CLAUDE.md (2026-09-13) a replay finding is a hypothesis whatever its n.
So the trade count is measured LIVE or not at all. It could be a 90% cut.

**Whether a stricter gate lowers OUR loss rate at all.** The 8.0x is the index
population -- any moment, no counterparty. Ours is "someone actively sold it to
us", and the two differ by 31x (rule 5). A gate calibrated on the first may do
nothing to the second. This is the real risk and it is not small.

## THE LIVE BAR -- decided before the first honest fill

Run `--honest` alongside nothing else changed. Scored at **40 fills or 14 days,
whichever comes first**:

1. **Loss rate on honest-gate fills strictly below the concurrent baseline.**
   Baseline is the live all-history market-loss rate, 4.13%. Not "lower on
   average" -- the point estimate must be below AND the run must have produced
   at least 40 fills to say anything at all.
2. **Trade count >= 25% of the current rate.** Below that the strategy is not
   a strategy any more, whatever its loss rate, and the honest answer is that
   the edge does not survive honest arithmetic. That is a legitimate result and
   it gets written down as one.
3. **$/day must not fall by more than half.** Fewer, safer trades are only
   worth it if the money mostly survives.

**All three must hold.** If 1 fails, revert. If 1 holds and 2 fails, the
finding is "the edge does not survive honest arithmetic" and the strategy is
re-opened from scratch, not patched.

## Kill criterion for the idea

If after 40 fills the loss rate is indistinguishable from baseline while the
trade count is down by more than half, the table is not measuring anything
about our own population and this line of work stops.

## What is NOT proposed

No change to PRICE_CEILING, MEASURED_FLIP, EV_FLOOR, EDGE_FLOOR, the sweep,
the hedge, BANK_BRAKE or size. `--honest` is one flag and it only ever makes
the model less sure.
