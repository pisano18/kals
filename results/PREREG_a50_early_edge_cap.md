# PREREG -- A50: cap the EDGE on the 45-second leg, so it can be sized up

Written 2026-09-18, **before any result from this arm is read**. Bars are set
here and are not moved afterwards; if they move, the move is written under a
dated heading with the reason, per the standing rule.

## The operator's question, which is what this answers

2026-09-18: *"the 45 second is profitable but barely and it's only okay
because it's just a 3rd, but that doesn't feel great still. The goal is to
eventually size it up, and it doesn't feel good that it can't do that. We need
to figure out how to be able to buy it at full price 45 seconds out."*

Right now the early leg is protected only by SIZE (a third of a bet) and a 90c
price floor. Size is a blunt instrument: it costs us on every good trade to
survive the bad ones. If there is a FILTER that removes the bad trades, the
size can come back.

## The claim

**On the early leg only, a big edge is a warning, not a prize -- and the sign
flips at 30 seconds.**

Measured over every signal in `results/pinrun-*.jsonl` joined to its own
settlement, split by `edge_c` (how far our model sat above the market on our
side, already net of fee):

| when | edge | bets | lost | $/bet |
|---|---|---|---|---|
| 31-45 s | under 3c | 177 | 3 | +0.06 |
| 31-45 s | 3-6c | 62 | 5 | **-0.57** |
| 31-45 s | 6c or more | 11 | 3 | **-3.01** |
| 30 s or less | under 3c | 934 | 15 | +0.14 |
| 30 s or less | 3-6c | 445 | 6 | +0.47 |
| 30 s or less | 6c or more | 263 | 1 | **+1.44** |

Live fills agree on the late half: 102 fills at 6c or more, 4 losses,
+3.08 $/bet. **There has never been a live early fill at 6c or more.**

**SOURCE AND ITS LIMIT (rule 5).** These are our own signals and settlements,
not the trade tape -- but the 31-45 s rows are dominated by PAPER arms, which
book a fill the moment they see an offer. Paper cannot know whether the offer
would have reached us, and on crypto the tape and our live fills once differed
31x in loss rate. **So the LEVELS above are not evidence and are not quoted as
such. The SHAPE -- profitable late, loss-making early, in the same edge band
-- is the claim, and this arm exists to test it on a population that is not
the one it was found in.**

Also: the join attributes a market's whole result to its FIRST signal's tau, so
a market bought early AND again inside 30 s counts once, under the early tau.
That blurs the two windows together and can only make the early rows look
BETTER than they are, never worse.

## Why it should be true -- mechanism, not a fitted curve

Settlement is the mean of 60 one-second prints. With `tau` seconds left,
`60 - tau` of them are already recorded:

| tau | prints locked | share of the answer already known |
|---|---|---|
| 15 s | 45 | 75% |
| 30 s | 30 | 50% |
| 45 s | 15 | 25% |

Late, our model is mostly reading data that has already happened, so a market
price six cents cheaper than the model is simply wrong -- and that
disagreement IS the edge we live on. Early, three quarters of the window has
not happened yet and our confidence comes from a volatility ESTIMATE. A market
that disagrees by six cents out there is usually disagreeing correctly.

**This is why raising the confidence bar cannot fix the early leg**, and it is
worth stating plainly because it is the obvious thing to try. Confidence is
computed FROM the volatility estimate. If the estimate is wrong, a 99.9%
reading built on it is wrong by the same amount. The market price is the only
input that does not come through that estimate, which is why the cap is set on
the price gap and not on the confidence.

The single loss in the current 45-second arm is the worked example: BNB at
22:00 on 09-17, bought at 93c while the model said 99.885% -- a 6.4c gap --
and it lost $18.69, which is more than the other seventeen trades made
together.

## What is running

One paper arm, identical to the live bot except:

```
--early-tau 45 --early-frac 1.0 --early-max-edge 3.0
```

So: FULL size on the early leg, and the early leg is taken only when our model
and the market are within 3 cents of each other. The control is the existing
`--early-tau 45 --early-frac 1.0` arm with no cap, already running.

**No money. `--live` is not passed and no sign-off is requested.**

## The bars, set now

**Stage 1 -- does the cap remove the right trades?** Needs 40 early-leg
markets settled on the capped arm.

- PASS: the capped arm's money per early market beats the uncapped control's,
  AND the control took at least 5 early trades the cap refused. Without that
  second half the comparison is two arms doing the same thing.
- FAIL: the capped arm is behind the control, or the cap refused fewer than 5
  trades in 40 markets -- in which case it is not doing anything and the
  finding above was noise.

**Stage 2 -- is it enough to carry full size?** Only if stage 1 passes. Needs
40 further early-leg markets.

- PASS, and only then is a live size increase proposed: at most 2 losing
  early markets in the 40, and no single early market losing more than 1.5x
  the arm's per-bet stake.
- FAIL, revert to a third size: 3 losses in 40, or 2 in the first 15. These
  are the same numbers as the A46/A49 stage-2 live bar, deliberately, so a
  bar is not quietly loosened by being restated.

**What would make me abandon the idea entirely:** the capped arm refusing 5 or
more trades that went on to WIN while itself losing money. That is the
expensive direction and it is the one the price floor already risks.

## What this does NOT change

Nothing on the main leg. Inside 30 seconds a wide edge is the single most
profitable thing the bot does (+1.44 $/bet on 263 paper bets, +3.08 $/bet on
102 live fills) and capping it there would throw the edge away rather than
protect it. `--early-max-edge` refuses to start without `--early-tau` above
30 for exactly this reason, and the self-test asserts the check sits inside
the early-leg block.

`EARLY_MAX_EDGE` ships as `None`. The live bot is untouched by this file.
