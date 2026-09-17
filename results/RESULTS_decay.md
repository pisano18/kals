# RESULTS -- is the market catching on? Yes, in one specific way, and it is measurable

`2026-09-17 ~15:4xZ` -- the operator: *"I'm worried the market caught on or is
catching on somehow and the bot trades an opportunity that doesn't/won't exist
anymore/soon."* Everything below is from the LIVE bot's own logs, normalised
**per quarter-hour the bot was actually watching**, so downtime and maintenance
cannot move any of it.

## 1. WHAT I GOT WRONG THIS MORNING

I told him fewer trades came from our bigger bet size: "a quarter-hour has a
fixed contract budget of two bets, so the same money arrives as fewer, larger
trades." **He rejected it -- "we buy any size" -- and he is right.**
`MIN_FILL_FRAC` is 0, so the bot takes a 4-contract offer as readily as a
94-contract one, and the close budget is `2 x SIZE`, which scales with SIZE.
The fill COUNT is very close to scale-invariant. That explanation is withdrawn.

## 2. WHAT IS ACTUALLY HAPPENING: the cheap offers are disappearing

`close_summary` records the best price and best edge the bot saw each
quarter-hour **whether or not it traded** -- our gates and our size play no
part in it.

| | first 4 days | last 4 days | today |
|---|---|---|---|
| best offer under 96c | 28% of quarter-hours | **20%** | **12%** |
| best offer 96-98c | 28% | 29% | 20% |
| **best offer ABOVE our 98c ceiling** | 44% | **52%** | **68%** |
| best edge, mean | 3.76c | **2.72c** (-28%) | 1.54c |
| best edge, median | 1.72c | 1.56c (-9%) | 0.90c |
| mean best price | 95.7c | **97.0c** | 98.3c |
| quarter-hours whose best offer still clears the 0.3c floor | 64% | **66%** | 57% |
| quarter-hours with ANY seller | 82% | 83% | 83% |

The daily mean best-edge falls in **34 of 45 day pairs** (50% would be no
trend).

**Read it precisely, because the shape matters.** Sellers appear exactly as
often as they did. The number of quarter-hours offering something that clears
our minimum edge is FLAT. What has gone is the **cheap tail**: the mean best
edge fell 28% while the median fell only 9%, and the cheapest offer on the
winning side is now 1.3c dearer than a week ago. Somebody is taking the
bargains before we do, or sellers have stopped mispricing them by as much.

## 3. THE MECHANISM THAT TURNS THAT INTO FEWER TRADES: our own 98c ceiling

As the best offer drifts up, it crosses `PRICE_CEILING = 0.98` and we refuse
it by design. Above 98c on 44% of quarter-hours in week one, **52% now, 68%
today**. That, not our bet size, is why the fill count fell (0.64 -> 0.47 fills
per watched quarter-hour, 0.27 today).

## 4. WHAT HAS *NOT* DECAYED: the money we keep per contract

| day | contracts | net | kept per contract |
|---|---|---|---|
| 09-13 | 2,194 | +$114.77 | +5.23c |
| 09-14 | 3,319 | +$81.14 | +2.44c |
| 09-15 | 2,431 | +$76.32 | +3.14c |
| 09-16 | 3,012 | +$85.10 | +2.83c |
| 09-17 (part) | 670 | +$21.34 | **+3.18c** |

Stable near 3c. **The trades we still take are as good as they ever were.** The
discipline is working: we are refusing the deteriorated offers, not buying them.

## 5. THE HOURS THAT WERE HOT HAVE COOLED -- he is right about this too

Fills per watched quarter-hour, first half of the run vs second half:

| ET hour | early | late |
|---|---|---|
| 19:00 | 0.95 | 0.50 |
| 20:00 | 1.00 | 0.69 |
| 22:00 | 0.89 | 0.25 |
| **23:00** | **0.95** | **0.06** |
| 11:00 | 0.58 | 0.20 |
| 18:00 | 0.68 | 0.25 |

Against that, 03:00 rose 0.62 -> 0.82, 16:00 0.42 -> 0.79, 21:00 0.62 -> 0.81.
The evening block that was the richest part of the day is the part that cooled
most -- which is what competition for a known pattern looks like.

## 6. WHAT THIS MEANS, AND WHAT IT DOES NOT

- **It is not "the edge is gone."** Two thirds of quarter-hours still show an
  offer that clears our minimum, and what we keep per contract is flat.
- **It is "the edge is thinner, rarer and pressed against our ceiling."**
  Every extra cent the best offer drifts up removes a slice of our volume,
  because the ceiling is a hard line.
- **The tau-45 deploy is a direct answer to this, not a bet against it.** If
  competitors are picking bargains off in the final 30 seconds, the 31-45s
  window is less picked over -- and the flat tau-45 paper arm did get **3x the
  control's bets at the same gate**. Going earlier is how you get there first.
- **The 98c ceiling is now the binding constraint and it is the operator's
  call.** 52% of quarter-hours (68% today) have their best offer above it. At
  98.5c a win pays ~1.5c and a loss costs ~98.5c, so break-even is about 1 loss
  in 66; our live record at 98c+ is 61 fills, 0 losses. Raising it was measured
  as wrong on 2026-09-09 when offers sat lower; the population has moved since.
  **Not changed without him.**

## 7. THE CEILING DECISION -- DELEGATED TO ME, AND THE ANSWER IS NO

The operator, 2026-09-17: *"Raising max fill price, if you think it makes us
more money, do it."* **It does not, and here is why. The ceiling is not left
at 98c out of caution; it is left there because the arithmetic says so.**

My last message implied the 98c ceiling was the big lever because it blocks
52% of quarter-hours. That framing was misleading and this corrects it: the
52% is a count, and what it counts is nearly all worthless. Of the **290**
quarter-hours we refused with the best offer above 98c:

| where the refused best offer sat | count | share of the refused | share of ALL quarter-hours |
|---|---|---|---|
| 98.0-98.5c | 24 | 8% | 4% |
| 98.5-99.0c | 49 | 17% | 7% |
| 99.0-99.5c | 77 | 27% | 12% |
| **99.5c and above** | **140** | **48%** | 21% |

**Three quarters of what the ceiling blocks sits above 99c.**

Break-even, from the real fee (`0.07 x p x (1-p)`):

| ceiling | fee | break-even loss rate | one loss in |
|---|---|---|---|
| 98.0c (today) | 0.137c | 1.86% | 54 |
| 98.5c | 0.103c | 1.40% | 72 |
| 99.0c | 0.069c | **0.93%** | **107** |
| 99.5c | 0.035c | 0.47% | 215 |

Against that, **our own calibration** (`research/pincalib.py`, 109,122
z-scores from the index feed): at the confidence the gate operates at, the
model promises to be wrong 0.15% of the time and **is wrong 1.21%**. A 1.21%
error rate puts the highest price with positive expected value at **98.79c**.
Even at the model's most confident (99.99%, where it is wrong 0.70%) the
highest positive-EV price is about 99.3c -- so the 140 offers at 99.5c+ are
negative expected value under every reading of our own numbers.

That leaves the 98.0-98.5c band: 24 quarter-hours over eleven days, about
**two a day**. At ~1.5c kept on a win and ~90 contracts that is roughly
**$1-2 a day**, and it is claimed on a break-even of 1 loss in 72 against a
measured 1.21% (1 in 83) -- a margin of 0.19 percentage points, well inside
the error on both numbers. **One loss there costs ~$88, or six weeks of the
gain.**

Live evidence, for completeness and against over-reading: entry fills at 98c+
are **62, none lost**. Rule of three puts that at up to ~4.8% -- it is
consistent with 1.21% and equally consistent with 4%, so it cannot carry this
decision either way.

**Decision: the ceiling stays at 98c.** It is revisited if `pincalib` is
re-run on more tape and the measured error at the gate falls below ~1.0%, or
if the 98c+ live count reaches ~300 fills with at most one loss. Both are
counting exercises, not judgement calls, and both are written here so the bar
is not moved later by mood.

## 8. What would tell us this is getting worse

Track weekly, on this same per-watched-quarter-hour basis: share of best
offers above 98c (44 -> 52%), mean best edge (3.76 -> 2.72c), and kept cents
per contract (flat at ~3c). **The third one is the one that matters.** While it
holds near 3c the strategy is intact and we are simply trading less of it. If
it falls below the ~2c break-even band, that is the real signal to stop.
