# SKIM — everything that matters, short

**Read this instead of the long messages. Updated as things change.**

---

## RIGHT NOW

| | |
|---|---|
| bank | **$110.45** |
| record | 30 wins, 3 losses |
| live | size **20**, 2 buys per close, ceiling **98.0¢**, tau 3–30, **gate 0.995 (was 0.98 — AMENDMENT 9, 2026-09-10)** |
| restart it | **`RESTART.md`** in the repo root — one line to paste |
| brakes | −$60 · 3 losing **closes** · 2 order errors · 8 attempts/close |
| day | started $38.83, funded +$113.04 → **−$41.54** |

---

## ⭐⭐ 2026-09-10 — WHY THE LOSS RATE PROBLEM IS NOT A SIGNAL PROBLEM

**Two investigations ran in parallel on different hypotheses. They converge on
the same answer, and it is not the answer either was looking for.**

### The fact that reframes everything

| population | loss rate | 95% interval |
|---|---|---|
| backtest, moments we could actually have bought | **0.79%** | [0.10%, 2.82%] |
| live, what actually happened | **8.8%** | [2.9%, 19.3%] |

**Those intervals do not overlap.** Whatever is losing our money live is *not
present in the historical tape at anything like the live rate*. So no amount of
factor-hunting on tape can find it — and six investigations failing was the
tape telling us that, not us being unlucky.

### What was measured, and what died

**1. The model's tail IS too thin, and it IS state-dependent. (real, well powered)**
`pintail.py`, **9,159 settled markets over 1,019 closes**, settlement model
reconciled to 3.8e-07 first.

| | measured | the model claims |
|---|---|---|
| mean forecast error | **0.657 sd** | 0.798 sd |
| chance of an error past the gate, the losing way | **2.58%** | 2.00% |

**The model is not wrong in scale — it is wrong in SHAPE.** Errors are usually
*smaller* than it thinks, occasionally far larger. And the tail moves with
conditions: **2.22% when no other coin is moving, 6.60% when three or more are.**

**2. But no gate built on it survives out of sample. (the important negative)**
Thresholds fitted on the first 70% of closes and re-measured on the last 30%:

| refuse when | profit change, fit | profit change, **holdout** |
|---|---|---|
| 1+ other coins moving | +18.5% | **−18.0%** |
| cross-market roughness ≥ 1.4 | +16.3% | **−8.4%** |
| 2+ other coins moving | +11.3% | **−6.6%** |

**Every one of them.** The conditions are real; a *fixed threshold* on them is
not. Deploying one today would be curve fitting, and I am not doing it.

**3. Cheap fills are not the culprit. (refuted)** The suspicion was that a
seller dumping a near-certainty far below fair value knows something. Tested
properly, controlling for price level: **0 flips in 73 high-discount closes.**
The live-sized version of the claim (~25% flips on discounted fills) is refuted
outright at P ≈ 7e-10. Anything under ~10% is simply invisible in this sample.

**4. The live/backtest sigma gap. (refuted, and I was wrong)** The live bot
computes sigma as a standard deviation about the mean; the backtest uses a
root-mean-square. I expected live to be systematically smaller — a looser gate
than the backtest scores. Measured on the same 9,159 seconds: ratio **1.0008**,
tails **2.58% vs 2.57%**. Dividing by (n−1) almost exactly cancels the mean
subtraction. **Not the bug.**

### What was DEPLOYED (logging only, no money at risk)

`pinrun` now records the market-wide conditions at the instant of every
decision: `cond_x` (how rough the *other ten* coins are, this one excluded),
`cond_n` (how many of them are moving), `cond_own`. Self-tested, including the
exclusion — the traded coin's own spike must leave its own index *exactly*
unchanged, or it is the refuted own-sigma filter under a new name.

**Logged, not gated on.** We have zero live records of the conditions our
losses happened in, and the tape has been shown unable to explain them.

### THE FORECAST, REBUILT ON AMENDMENT 9 (2026-09-10 12:0xZ) — `pinproj.py`

Bank **$140.24**. Every input re-measured, none inherited from the old forecast.

| | old gate 0.98 | **new gate 0.995** |
|---|---|---|
| price we pay | 93.1¢ | **97.0¢** |
| fills/day | 65 | **50** (−22%) |
| loss rate | **5.95% actual** | ~0.51% expected |
| break-even loss rate | 6.43% | **2.78%** |
| **safety margin** | **1.08×** | **5.5×** |
| profit per contract | +0.48¢ | **+2.27¢** |
| days to the 125 cap | 33 | **11** |
| income at the cap | $39/day | **$142/day · $4,275/mo · $52k/yr** |

**DAYS TO EACH SIZE** (measured inputs, 0.51% loss, 97.0¢, 50 fills/day):

| size | day | bank | $/day there | $/month |
|---|---|---|---|---|
| 20 | now | $140 | $22.80 | $684 |
| 30 | 2 | $192 | $34.20 | $1,026 |
| 50 | 5 | $306 | $57.00 | $1,710 |
| 80 | 8 | $494 | $91.20 | $2,736 |
| **125 (cap)** | **11** | **$813** | **$142.50** | **$4,275** |

**The ladder is set by the brake, not by hope:** size may rise only when the
bank covers `3 losing closes × 2 buys × size × price`. At $140 and 97¢ that
funds exactly size 20.

**THE HONEST COMPARISON.** The old gate had a *higher ceiling* ($360–474/day if
its loss rate had been low) because it bought at 93.1¢ and cheap contracts pay
more. It was running at a **1.08× margin over break-even** and it actually
lost **−$15.02 over 84 fills.** A ceiling you never reach is worth nothing.
The change bought a 5.5× margin for a lower ceiling. That is the trade, stated
plainly, and it is reversible in one line.

**THE BIGGEST LEVER IS NOT THE GATE — IT IS THE PRICE.** At the same 0.51%
loss rate: 97.0¢ → $143/day, 96.0¢ → $201/day, **95.0¢ → $259/day.** One cent
cheaper is worth more than anything else on the board. The ZEC fill proves the
two are separable: **93.3¢ AND 3.05 sd deep.** Getting deep markets at cheap
prices — patience, queue position, scale-in — is now the highest-value work.

**What is thin:** 50 fills/day rests on 7 fills over 3.3 h. The model predicts
$22.80/day at size 20; the first 3.3 h ran at ~$28/day — consistent, but that
is one afternoon. Sensitivity tables for loss rate × price × fill rate are in
`results/pinproj.log`.

**If the loss rate is really 2%+ at 97¢ we are near break-even** (2.78%) and
the answer is a cheaper price, not a stricter gate.

### DEPLOYED 08:4xZ — AMENDMENT 9: confidence gate 0.98 → 0.995. THE BAR MOVED.

The one lever with holdout evidence. It refuses the two margin bands that
flip at 1.8–3.1% and keeps everything at 2.6 sd or deeper (0.5%, then 0 of
7,868). Tape flips 18 → 10, holdout 3 → 1, no loss of opportunities in market
count. **It would have skipped 3 of our 5 losses and no deep win.** Cost
unmeasured: expect fewer fills at higher prices — the next day tells. Size,
brakes, ceiling unchanged. Revert is one line (`VERSIONS.md`).

The exchange-tick veto (the XRP mechanism) is **proven on events, not as a
rule** — 2 of 7 tape flips have the signature, p=0.07, 0 of 2 holdout flips
caught. Logged, not deployed (IDEAS_LOG S).

### LATER THE SAME NIGHT — three more results, one of them the lead we needed

**1. The model is right at its own boundary and never wrong deep inside.** Measured
at the second the bot actually fires (10,796 markets walked): flips are **1.8–3.1%
at 2.05–2.6 sd, 0.5% at 2.6–4 sd, and 0 of 7,868 above 4 sd.** Holds on a
holdout. Our live boundary fills lost 3/32 — inside that interval. **Two of our
three recent losses are exactly this: the boundary's own ~2%.** Raising the gate
to 0.995 halves tape flips at zero market-count cost; a margin-aware EV line is
correct but would not have removed a single live loss (it refuses 17 small
winners). Neither deployed; both logged (IDEAS_LOG K–M).

**2. The XRP loss was a sub-second information lead, not a model error.** At the
signal second the CF index printed **1.39075** while **Coinbase had already
traded 1.38950.** The seller at 82¢ had seen the exchange tick; the index caught
up one second later and fell ~10 sd. Our data was fresh — the *print* was stale
inside its own second. We already record every exchange tick (`feed_data`) and
have never used it. **This is the next test and the most promising lever of the
week: refuse to fire when the freshest exchange tick disagrees with the CF print
by more than ~2 sd.** It costs nothing when nothing is moving.

**3. Live P&L, reconciled to the bank: −$15.02 over all 84 fills.** The earlier
"+$26.50" excluded the −$52.60 NEAR close.

### The one thing that would actually settle it

**~70 more live fills with these columns attached.** That is the sample that
distinguishes a 25% problem from a 5% one. Tape alone would need ~10 more days
for the crude version and ~44 days for the fine one, and the interval mismatch
above says even then it would be answering about a different population.

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

## THE HEDGE: TESTED PROPERLY UNDER JOE'S OBJECTIVE. IT DOES NOT WORK.

Three tracks, six agents, all refuted. **No hedge gets near the target.**

| | worst loss, in wins to recover |
|---|---|
| Joe's target | **1–5 wins** |
| no hedge | 21.8 |
| best hedge, with realistic depth | **20.7** |

**It moves the worst loss by one win.** And it costs **−6.9% of all profit** on
the window we actually trade, for **zero measured benefit** there (0 losers in
83 closes). The headline +39% came entirely from tau 31–60, a window
AMENDMENT 4 already removed from the live rule.

**Break-even for the rule is a 0.90% loss rate. Our live constant IS 0.90%.**
A coin flip on our own best estimate.

### Why insurance is never cheap here

There IS enough time — losers cross at median tau 14 and 97–100% of alarms fire
with ≥3 seconds left. **The constraint is PRICE, not latency.** The market
reprices in the same instant the move happens, so by the time we know, the
other side already costs what it is worth.

### Two things that kill the "warning sign" idea for good

- **`mu` crossing the strike is a near-perfect classifier** — losers cross
  100% of the time, winners essentially never. But it arrives at the *same
  moment* as the price. It is a report, not a warning.
- **Tonight the cushion |spot − K| GREW from 0.00085 to 0.00135 as the trade
  died.** An unsigned-distance alarm is structurally incapable of warning.

### The win unit was optimistic and the corrected figure is worse

Median winning close is **$0.78**, median 3.26¢ per contract. So the worst
close, −$37.50, is **47.8 wins at the median**, not 20.8. The recovery problem
is bigger than I said.

---

## ⭐ THE PRICE LADDER — the biggest finding, measured 2026-09-09

22,568 model-confident moments. **Cheap trades flip ~5× more often and are far
SAFER, because break-even rises faster than the flip rate.**

| price | flip rate | break-even | margin |
|---|---|---|---|
| 70–85¢ | 2.50% | 18.2% | **7× safe** |
| 93–97¢ | 1.95% | 4.2% | 2× safe |
| **98–100¢** | **0.53%** | **0.30%** | **LOSES MONEY** |

**83% of everything our model likes sits in the band that loses money.** The
98.0¢ ceiling now has outcome data behind it, not just arithmetic.

**NEXT ACTION, not yet deployed: SIZE INVERSELY WITH PRICE.** We currently stake
the same on a 2×-margin bet as a 7×-margin one. The 22¢ SOL trade had 200
contracts available and we took 20. Needs: cheap-offer frequency (only 3 of
22,568 moments were under 70¢), market impact at size, and a bank that funds it.

---

## ⭐⭐⭐ THE THING WE MUST DO — Joe, 2026-09-10

> *"We can control our own losses because we already do. We don't try to buy
> into every bet, we look at the conditions and see if it's favorable. We need
> better conditions, and a faster understanding of how 'favorable' changes."*

**He is right and it corrects me.** I had said we cannot control how often we
lose — only what a loss costs and when we stop. That is wrong. **The gate IS a
choice about frequency.** Every close we decline is a loss we chose not to
take. What is true is only that we have not yet found a BETTER rule for
choosing.

### Why six investigations all came back empty

We judge "favourable" with **ONE number per trade**: how far the index must
move, divided by a volatility estimate averaged over the trailing 300 seconds.

That number is **slow** (five minutes of history), **isolated** (one coin, blind
to the other eleven), and **measurably wrong in the tail** (the gaussian is 9.3×
too thin at 3 sigma, 176× at 4).

**Every fix attempted this week was a FILTER BOLTED ONTO THAT ONE NUMBER** —
flatness, sigma regime, recent jump, price velocity, model-vs-market divergence,
cushion ratio, k-NN fingerprints. All six failed, and they failed for the same
reason: *asking a slow blind measure to say something it cannot*. The forensics
proved it directly — once `z` is held fixed, **nothing else adds anything.**

### So the answer is not another filter. It is a better signal.

Measure **the conditions themselves**, across all twelve coins, continuously,
and let the definition of favourable move with them:

- realised volatility **now** (1s / 5s / 30s), not a 300-second average
- **how many coins are moving at once** — a cross-market roughness index. The
  per-coin version is what got refuted; the cross-market version is untested.
- the rate of change of roughness, not its level
- book-side signals: spread widening, depth thinning, quote churn

Then tighten the gate while it is elevated and loosen while it is flat, instead
of holding one fixed threshold through calm and storm alike.

### The evidence this is the right target

**All five losses live in TWO hours out of thirty.** Twenty-eight hours with
none. Losses are not a steady drip; they arrive in bursts, because volatility
arrives in bursts. A fixed threshold cannot see a burst. **A live conditions
measure is the only proposal we have that aims at the FREQUENCY of losses
rather than their size.**

First test (weak version, using a loss as the signal): the close immediately
after a losing close is **1.8×** more dangerous, dying to nothing by 4 closes.
Right shape, but p = 0.318 on 22 events — not significant. **The strong version
uses live conditions, available before any loss, across 53,555 rows instead of
22 events. It has never been run.**

---

## ⭐⭐ THE BACKTEST IS FIXED, AND THE REMAINING GAP HAS A SUSPECT

**Two real bugs fixed 2026-09-10.** `Book.snapshot()` read `yes_dollars`; the
tape sends `yes_dollars_fp`, so snapshot seeding NEVER worked and every replayed
book was delta-only. And `fulltape/markets.json` was stale to 09-06, so all
three real losses had no settlement and were invisible. `research/pinverify.py`
is the acceptance test: **3 real losses AND 2 real wins must all reproduce.**
It now passes. It caught two errors of mine first, including a fixture where I
had typed the wrong side for 4 of 5 trades.

| | fixed | old (broken) |
|---|---|---|
| rows | **53,555** | 28,479 |
| closes | **151** | 80 |
| losing closes | **1 = 0.66%** | 0 = 0.00% |
| avg price | 93.77¢ | 93.06¢ |
| profit/contract | **+5.38¢** | +6.50¢ |

**But the backtest still says 0.66% while live says 5.71% (2 in 35).**

### THE SUSPECT: we are filled at prices nobody meant to give us

| | n | asked | paid | improvement |
|---|---|---|---|---|
| wins | 78 | 94.91¢ | 94.41¢ | **0.49¢** |
| **losses** | 5 | 90.90¢ | 88.16¢ | **2.74¢** |

Fills bettering our ask by **>0.5¢ lost 25% of the time**; fills at or near our
ask lost **5.1%**. The worst: we bid **95.7¢ on XRP and were filled at 82¢** —
13.7¢ of unexpected generosity, and it lost $16.61.

**The mechanism: the backtest models the trade we INTENDED, at the displayed
price. Live we get the trade someone CHOSE to hand us — and a seller in a hurry
often knows something.** That is a different, adversely-selected population, and
it would explain the whole 0.66%-vs-5.71% gap without the replay being wrong.

### THE EVIDENCE AGAINST IT, which matters

**Our single biggest win was also our biggest price improvement.** The 22¢ SOL
fill was bid at 56¢ — **34¢ of improvement** — and made **+$15.36**. So a
surprising fill is not simply poison; it is HIGH VARIANCE. Of the two largest
improvements on record, one won huge and one lost huge.

**And it rests on five losses.** The 25%-vs-5% split turns on ONE loss among
four improved fills. Three patterns of exactly this shape have already dissolved
under proper testing this week. **Do not deploy anything on it.**

### HOW TO SETTLE IT

The rebuilt dataset carries `price` and `spread` per moment, so the modelled
fill can be compared against the touch across 53,555 rows rather than 83. Test
whether flip rate rises with the gap between ask and fill, clustered by close,
with a shuffled control. If it survives, the fix is not a gate but a **price
sanity check**: refuse a fill that betters our ask by more than X, because it is
not the trade we priced.

---

## 📌 FRIDAY LIST — raised by Joe 2026-09-09, not yet started

### 1. ROBINHOOD RUNS THE SAME MARKET ON THE SAME PRICE SOURCE

Joe: *"Robinhood has the exact same 15 min average market and same price source
as Kalshi."*

**This attacks our actual binding constraint.** We measured that the limit on
earnings is not capital and not our rules — it is that **8 of 30 closes have
nothing to buy at all** (the losing side's book is empty in 33,427 of 33,431
decided moments). A second venue settling on the *same index* is a second shot
at the same certainty. Potentially double the opportunities for the same
research.

**Check in this order, cheapest first:**
1. Is there an API, and does it allow programmatic orders?
2. Fee schedule — Kalshi is `ceil(0.07·p·(1−p)·n)` and makers pay zero. If
   Robinhood charges differently the whole price ladder shifts.
3. Settlement wording: is it the same 60-print average over the same window,
   and the same rounding? `strike − 0.5·10^−digits` matters enormously.
4. Do prices actually diverge between venues? If the same outcome is 94¢ on
   one and 97¢ on the other, that is a real edge on top of the strategy.

**Caution worth stating up front:** "same price source" is a claim to verify,
not assume. This project has been burned by assumed field semantics twice
(DOGE's 7 round-digits, the `_fp` snapshot keys). Read their contract wording
before writing any code.

### 2. A DESKTOP WINDOW INTO THE BOT'S BRAIN — two modes

**LIVE** — what the bot is seeing and thinking right now.
**SANDBOX** — the same panels, driven by historic tape instead of the live feed,
with every constant editable. Joe's name for it, and the name carries the point:
*a place to play with past data and made-up values without touching real money.*
Scrub to any past close, change the ceiling / size / cap / gate, and watch what
the bot WOULD have done. Every rejected idea in IDEAS_LOG could have been
answered here in minutes instead of by a six-agent workflow.

**The sandbox must make one thing impossible: mistaking it for live.** Different
ground colour, a permanent banner, and no code path to the order API at all —
not a disabled button, an absent one.

Joe: *"I want a desktop tool to live view the bot what it's seeing and reading
and get a peek into its brain."*

Everything needed is **already being logged** — `pinrun-live-*.jsonl` carries,
per close: every market watched, the index spot and its age, sigma, the
computed fair value, the required move, the price on offer and its depth, which
gate refused it, order latency, and the fill. Nothing new needs instrumenting.

What is missing is a **reader**. Shape worth building:
- the 15-minute countdown, and for each of the 12 markets: spot vs strike, how
  far it must move to flip, and the model's confidence
- a live funnel per close — looked → decided → offered → passed the gates →
  fired — so a quiet close explains itself
- the price ladder colour-coded by wins-to-recover, since that is the number
  that actually matters
- the brakes: realised P&L against −$60, losing closes against 3

**AND AN EQUITY CURVE, TREATED LIKE A TICKER.** Joe: *"track the bets we do and
my balance amount in a stock like line graph with all the things a regular
stock has, exc % change and all the other things."*

The balance line, with every trade marked on it, plus the standard readouts a
ticker carries:

| | |
|---|---|
| headline | balance, absolute change, **% change**, up/down colour |
| ranges | today · 7d · 30d · all — each with its own % change |
| session bar | open · high · low · current, and the day's range |
| **max drawdown** | peak-to-trough, in dollars, % **and wins-to-recover** |
| volume | trades per period, fill rate, and races lost |
| markers | every fill on the curve, hover for coin/price/size/result; **losses flagged** |
| return | since inception, and annualised **with the capacity ceiling stated** |
| capital | deployed vs idle — this strategy caps out around $940 |

**Two things a normal ticker does NOT have, and this one must:** the *wins to
recover* figure on every drawdown, because that is the operator's own unit; and
an explicit note that annualised return is meaningless past the capacity
ceiling, so the chart cannot imply compounding that the market will not allow.

---

### 3. DUST FILLS BURN A SCALE-IN SLOT (found live 2026-09-10 03:44Z)

`KXBTC15M` filled **0.02 contracts** at 97.9¢ — worth about **0.03¢** — and it
consumed one of the two buys allowed for that close.

Same shape as the no-fill bug fixed on 09-08, one layer down: `MIN_FILL_FRAC`
gates what we ASK for, nothing gates what we GET. A fill under some fraction of
the requested size should not book a slot, since it creates almost no exposure
and blocks a real position behind it. Cheap fix, needs a self-test that a dust
fill does not book and a real partial still does.

---

### 4. SWEEP THE SURPLUS ONCE WE HIT THE CAPACITY CEILING

Joe's instinct, 2026-09-10: once the bet size caps out, the extra money is doing
nothing, so take it off the table.

**He is right about the money and wrong about the reason.** The cap does not make
anything "guaranteed won" — every close still risks the full stake, and at size
125 a losing close costs about $120. What is true is that **only ~$940 is doing
any work**. Above that, capital sits idle *and stays exposed to the account's
own risk of ruin* for zero return.

**POLICY: once size caps at ~125 contracts, sweep everything above ~$1,100 out
of the Crypto shard.** That surplus is then genuinely out of reach. It also
means a catastrophic loss rate can only ever destroy the working float, not the
winnings.

Needs: a withdrawal path (never automatic — the operator moves money, not me),
a float threshold with hysteresis so it does not sweep and refund daily, and the
size ladder recomputed against the *float*, not the total balance.

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
