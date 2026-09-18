# PREREG -- A52: hedge on the JUMP, not on the belief

Written 2026-09-18, **before any result from this arm is read**. Bars are set
here and are not moved afterwards; if they move, the move is written under a
dated heading with the reason, per the standing rule.

## The operator's request this answers

*"I hope you're researching new ideas and strategies too"* and, on the same
day, *"I wish it would've hedged harder and bought more if it was certain of
the loss."*

## The finding it rests on

Every loss this bot has taken is a post-entry jump. Measured on 920 live and
paper markets with 19 model misses (`results/sigcheck_out.json`): each miss
contains a single-second index move of 10-18 sigma, sigma was understated
2-3x at entry, and the losers sit inside the winners' confidence range. A
scored vote of every entry-time warning was tested the same day and killed --
one flag catches 4 of 4 misses at 31-45 s and refuses 75% of wins; two flags
catch 1 of 4. **Nothing at entry sees the jump. The defence is after entry.**

## The claim

The hedge currently fires when the model's belief in our side falls through
60%. Belief is DOWNSTREAM of the jump: by the time it has fallen the market has
moved and the other side costs 50-70c. Our twelve real hedges paid 10c to 95c.

Firing on the jump itself -- the largest one-second move against our side
since entry, in sigma -- should fire EARLIER, while the market may still like
our side and the other side is 10-20c. A needed hedge then pays 80-90c a
contract instead of 30-50c; a wasted one costs a few dollars, not twenty.

Firing upper bound on the 920 markets, by threshold:

| window | threshold | losses caught | winners that would fire |
|---|---|---|---|
| live 3-30 s | 5 sigma | 11 of 11 | 42 of 463 (9%) |
| live 3-30 s | 8 sigma | 7 of 11 | 17 of 463 (4%) |
| live 3-30 s | 10 sigma | 5 of 11 | 8 of 463 (2%) |
| live 31-45 s | 8 sigma | 1 of 1 | 3 of 56 (5%) |

**What those records cannot say, stated first:** they hold the biggest move,
not WHEN it came relative to the price collapse. If the jump and the collapse
are the same second, the hedge fills at 60c anyway and this buys nothing over
the belief trigger. The smallest jump among the 19 misses is 4.3 sigma and the
largest among winners is 62.6, so no threshold is clean. **The money is in the
fill price**, and only an arm that actually tries to fill can measure it.

## What is running

One paper arm, identical to the live bot except `--hedge-jump 8`. The belief
trigger stays on; the jump is an ADDITIONAL reason to fire, and every alarm
records which reason fired (`trigger`) and the jump size (`jump_sd`), so the
two can be scored against each other on the same alarms.

8 sigma, not 5: 5 catches every loss but fires on 9% of winners, and at the
current hedge sizes 42 wasted premiums is more than the 11 losses are worth.
8 fires on 4% and still catches most. If 8 looks good the next arm tries 6.

**No money. `--live` is not passed and no sign-off is requested.**

## The bars, set now

Needs 25 alarms where the JUMP fired (not belief). Then, on those:

- PASS: the median fill price of the hedge leg is at least 15c below what the
  belief trigger paid on its own alarms over the same period, AND at least half
  the jump-fired alarms went on to be NEEDED (our side lost). That is the
  whole thesis: earlier, therefore cheaper, and mostly right.
- FAIL: fewer than a third of jump-fired alarms were needed. Then the trigger
  is buying insurance against noise and the premiums exceed the payouts.
- FAIL: the fill price is not cheaper. Then the jump and the collapse are the
  same second and there is nothing to be earlier than.

**What would make me abandon it entirely:** a jump-fired hedge on a market our
side went on to WIN by a wide margin (settle more than 2 sigma on our side),
five times in the first 25. That is the trigger firing on ordinary noise.

## What this does NOT change

The entry decision is untouched -- this refuses no trade. The belief trigger
is untouched. `HEDGE_JUMP_SIGMA` ships as `None`. The live bot is not affected
by this file.
