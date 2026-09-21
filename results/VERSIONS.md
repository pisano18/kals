# v-hedge25 -- 2026-09-21 ~19:0xZ -- LIVE: the hedge trigger moves 60% -> 25%

The operator set the objective: *"It's not cutting losses that matters it's
losing the least amount of money."* And the task: *"tune it to catch the most
it can while having enough certainty to offset as much total losses as
possible."*

**REVERT:** set `"--hedge-belief", "0.60",` in `restart_bot.ps1` and run
`powershell -ExecutionPolicy Bypass -File C:\kals-repo\restart_bot.ps1`

## The instrument -- `research/hedgetune.py`, new

Every earlier answer scored a trigger at the price available **at the alarm
second**. That is only right for an alarm already under the trigger when it
fired. Any lower trigger has to WAIT, and insurance gets dearer as confidence
falls -- which is precisely what A76 cost us today. Pricing a wait at the
pre-wait price flatters it by that whole amount.

So this rebuilds, for all 16 alarms with an entry signal: our **confidence
second by second** from the 1/sec index (`settlewin.partial` plus pinrun's own
`eff_strike`, `var_factor`, `conf_of` -- only the two live reads replaced),
and the **hedge price and depth second by second** from the ticker tape. Then
it buys at the first second confidence falls under the trigger, at the price
quoted then, capped by what was offered.

## The dial

| trigger | fires | real | right | the losses | false alarms | TOTAL |
|---|---|---|---|---|---|---|
| **<60% (what we ran)** | 14 | 8 | 57% | -$235.91 | -$134.13 | **-$370.05** |
| <40% | 11 | 8 | 73% | -$242.57 | -$79.02 | -$321.58 |
| **<25% (now live)** | 10 | 8 | 80% | -$276.86 | +$3.71 | **-$273.15** |
| <20% | 8 | 8 | 100% | -$276.94 | +$22.38 | -$254.56 |
| never hedge | 0 | - | - | -$346.78 | +$22.38 | -$324.40 |

**The 0.60 trigger was the worst of every option, including not hedging at
all.** It fires on 14 alarms of which 8 were real; the six false ones cost
$156. At 0.25 it still catches **all 8 real losses** -- not one is missed --
and pays for only two false alarms.

## Why 0.25 and not lower

0.20 and below have never once hedged a bet that went on to win (8 for 8) and
read better still. The **leave-one-out** decides it:

| trigger | worst drop-one, against never hedging |
|---|---|
| <60% | **-$79.30** |
| <30% | -$43.01 |
| **<25%** | **+$23.50** |

0.25 is the loosest trigger where dropping the single most influential alarm
STILL leaves hedging ahead. That is the most coverage the evidence supports,
which is exactly what was asked for.

## Left on the table, deliberately

Sizing to cover the money at risk instead of matching the position reads
**-$220.42** at this trigger, another $53, worst drop-one **+$47.79**. It
needs a new flag and does not go in the same change as this one.

---

# v-hedgelastweek -- 2026-09-21 ~17:5xZ -- LIVE: the hedge is last week's, exactly

The operator: *"make sure that my hedge right now is functioning just like it
did last week. The time were it was cutting them in half and even caused a
profit. I want that exact code as my hedge. The other stuff we changed that's
good stays, but for the hedge I want that one."*

**REVERT, copy-pasteable:** put `"--hedge-price", "0.60",` back into
`restart_bot.ps1`, then run
`powershell -ExecutionPolicy Bypass -File C:\kals-repo\restart_bot.ps1`

## What changed

`--hedge-price 0.60` is REMOVED. With `--no-hedge-prop` from earlier today,
the hedge is now exactly what it was during the week he is describing: the
WHOLE position, at the alarm, with no price gate.

## He is right, and the start records prove it

Every hedge he remembers ran with `hedge_price: None`:

| hedge | unhedged | hedged | cut |
|---|---|---|---|
| BTC 09-14 | -$58.43 | -$34.26 | 41% |
| HYPE 09-14 | -$59.20 | -$29.90 | 49% |
| BNB 09-16 | -$0.98 | -$0.47 | 52% |
| DOGE 09-18 04:15Z | -$3.93 | **+$4.36** | a loss turned into a profit |

The flag was not added until the **2026-09-18 22:46Z** run, after all four.

## Every real-money alarm, replayed against the book at the alarm second

| policy | the 10 losses | 8 false alarms | total |
|---|---|---|---|
| never hedge | -$346.84 | +$22.38 | -$324.46 |
| **LAST WEEK (no price gate)** | **-$235.93** | -$109.38 | -$345.31 |
| with the 0.60 gate | -$280.70 | -$55.76 | -$336.46 |
| A76 proportional | -$246.54 | -$136.20 | -$382.74 |

**The trade-off, stated plainly so nobody is surprised later.** Last week's
rule cuts the LOSSES by **32%** against the gate's 19%, and would have made
today's NEAR **-$48.16 instead of -$74.25**. It costs $53 more on the false
alarms and is $9 worse on the 18-alarm total. The operator has chosen the
loss cut with those numbers in front of him. The total is dominated by two
false alarms on 09-19 and is not what he is optimising.

## What the gate was for, so it is not re-added blindly

It refuses a hedge when insurance is CHEAP -- when the market has not yet
agreed with our model. Of the nine hedges it blocks across the 18 alarms,
**six were false alarms** and it saved us on those. It also blocked today's,
**by one cent**: the NO was 39c against a 40c line.

The replacement is not a price line, it is telling a false alarm from a real
one. The false alarms cluster at 14, 18, 37 and 37c while the big real losses
sat at 44, 52 and 65c. That is being tested now and nothing goes back in
until it is.

## Kept from this week, because it is execution and not a gate

`--hedge-slip 0.03`, `--hedge-max-tries 30` and the 120-attempt cap stay. They
make the hedge order actually cross; last week's 5 tries left hedges unfilled.

---

# v-hedgefull -- 2026-09-21 ~17:0xZ -- LIVE: A76 PROPORTIONAL HEDGING IS OFF

Flag added: `--no-hedge-prop`.

**REVERT, copy-pasteable:** delete the `"--no-hedge-prop",` line from
`restart_bot.ps1`, then run
`powershell -ExecutionPolicy Bypass -File C:\kals-repo\restart_bot.ps1`

## What the bot now does differently

It hedges the WHOLE position the moment belief crosses `--hedge-belief` 0.60,
instead of buying nothing above 40% belief, half at 40%, and topping up later.

## Why -- every real-money alarm we have, replayed against the book

A76 fired for the first time today on `KXNEAR15M-26SEP211245-45` and cost
$59.09. All 18 lifetime alarms with a settlement were replayed against the
**order book at the alarm second**, read from the ticker tape, with every
hedge sized by what was actually offered at that second:

| policy | total over 18 alarms |
|---|---|
| never hedge at all | -$324.46 |
| hedge the whole position at the alarm, no price gate | -$345.31 |
| ...and skip insurance over 60c | -$271.42 |
| ...and skip insurance over 70c | **-$269.10** |
| cover the whole money at risk | -$319.24 |
| **A76 proportional, as deployed** | **-$382.74** |

**A76 is the worst of every policy tested** -- $58 worse than never hedging
and $113 worse than hedging in full at the alarm. The mechanism is not
subtle: the price of insurance tracks the belief, so waiting for belief to
fall guarantees paying up. Today the NO was **39c with 44 contracts offered**
at the alarm second. A76 bought nothing, then paid **70c** eleven seconds
later and **90.5c** three seconds after that, to protect contracts bought at
91.1c. That last leg could never have paid for itself.

`--hedge-price 0.60` is unchanged and still gates the normal path, which is
what the 60c row above measures.

## What was tested and REJECTED, so it is not re-proposed

**Sizing the hedge to cover the whole loss** -- the operator has asked for
this repeatedly and it is right in principle. Two walls, both measured:

* **Depth.** Covering the money needs `risk/(1-price)` contracts: 121 today
  against 44 offered, and short of depth on **9 of 18** alarms, once needing
  1,151 against 3 offered.
* **False alarms.** Where the depth did exist and the bet then WON, full
  cover turned +$5.73 into -$45.66. Across all 18 it is -$319.24, no better
  than 1x.

**Oversizing** reads spectacularly in-sample (6x the position = -$84.80) and
is fitted: chosen on the first nine alarms it **loses $84** on the last nine.
The reverse split chooses 1x at 0.70 and gains $52. Only the 1x rule survives
both directions.

## The bar

Below 40% belief the bet lost **6 times in 7**, so waiting is not information,
it is paying more for the same insurance. If the next 10 alarms under
full-at-alarm hedging are still net negative against never hedging, then
hedging itself goes, not the sizing. `arm-nohedge` answers that without risk.

---

# v-nocap -- 2026-09-20 -- LIVE: the 97.5c early-leg ceiling is REMOVED, hours after it shipped

The operator: *"I actually really want to keep the 45 normal"* and *"If you
think dropping sweep cap makes more do it. I just want the most money."*

## The measurement that killed it

The 45-second leg is not the risky leg. It is the LOW-MARGIN leg, and its
loss rate is BETTER than the main window's:

| leg | markets | contracts | avg paid | money | c/contract | **loss rate** |
|---|---|---|---|---|---|---|
| 45s early | 136 | 8,671 | 96.87c | +$110.67 | 1.28c | **1.5%** |
| main window | 515 | 21,431 | 95.45c | +$441.53 | 2.06c | 2.5% |

Two losing markets in 136, and the hedge turned one of them into **+$4.36**.

The ceiling would have touched **51% of its fills**. The case for it was that
the blocked budget would flow into the 5.6c-a-contract last-ten-seconds
window. **That thesis is now measured and it is FALSE:**

| window | fills | avg filled | avg our bet | we get |
|---|---|---|---|---|
| last 10s | 50 | 62.6 | 65.8 | 95% |
| 11-30s | 225 | 62.4 | 75.8 | 82% |
| 31-45s | 140 | 64.4 | 93.4 | **69%** |

In every window we already fill less than we ask for, and the shortfall grows
with our bet. **There is nowhere for the budget to go** -- the book in the
good window is thinner than we have grown. Blocking the early leg would not
have moved money to a better window; it would simply have been less trading.

`--early-max-price` stays in the code for a paper arm to test properly.

## The bigger thing this turned up

Our bet has outgrown the window that pays best. At 31-45s we fill 69% of what
we ask for; the last ten seconds -- 5.6c a contract, zero losing closes in 71
-- is the hardest place to put size. This is the same finding as "a bigger
bet does not earn more" (correlation -0.05 over six days) arriving from a
different direction, and it is an argument for a SMALLER bet, not a bigger
one. Not acted on; raised for the operator.

## Also confirmed, no change needed

**`depth_floor` is not costing us anything.** It fired 886 times, which
looked like the biggest gate in the bot. Of the 774 that fired under the
live `--min-fill-frac 0`, **every single one had under ONE contract on
offer** (median 0.29). The floor is already 1 contract and the bot already
takes whatever is there. The operator asked "we should be buying 20 if
that's all that's available" -- we already do.

---

# v-earlycap -- 2026-09-20 -- LIVE: a 97.5c ceiling on the 45-second leg, and the loss cap is a DAY not a run

Two changes, both on the operator's word: *"Sure cut to 97.5 I like that. The
whole point is better pricing so that's good"* and *"Yes loss cap change"*.

## A78 -- `--early-max-price 0.975`

The 31-45 s early leg refuses an ask above 97.5c. Measured, live fills:

| window | c/contract | losing closes |
|---|---|---|
| 31-45 s (the early leg) | **1.14c** | 2 of 99 |
| 16-30 s | 1.22c | |
| 6-10 s | **5.63c** | **0 of 71** |

Above 97.5c the early leg risks 98c to make 1.8c, fifteen seconds before the
information the strategy rests on arrives. That is exactly the fill that cost
**-$107.95**: `KXBTC15M-26SEP191600-00`, NO at 98c at tau 45, while the same
model sixteen seconds later said **YES at 99.79%** with YES offered at 92.6c.

**What it blocks:** early fills above 97.5c. It cannot touch the main window
(that leg is `full`), it cannot touch a hedge, and at the shipped default of
1.0 it blocks nothing -- the flag is what turns it on. Refusals log as
`early_dear`, registered in `pinattrib.py` so the gate report can score it.

## A79 -- the loss cap survives restarts

`--loss-cap 200` was **$200 PER RUN**. 2026-09-19 had **thirteen runs**, each
starting with a fresh $200 of permission, and the day reached **-$223.46**. A
cap that resets whenever the watchdog restarts the bot is not a cap.

`results/pinrun-dayloss.json` now holds the ET day's realised total, written
on every LIVE settlement before the log line. `risk_abort` compares the DAY
first and names it. Seeded at deploy from Kalshi's own books: 2026-09-20 was
+$26.88 over 10 markets, so the full $200 of room was intact.

Paper arms never touch the file. A new ET day (04:00Z) starts clean. Wins
count, so a profitable day can never halt on it. A NaN or infinity is refused
on the way in AND on the way out -- a poisoned total would have made every
comparison False for ever, which is a cap that silently stops being one.

## Also in this deploy

- The self-test check `index("book.depth") > index('rec("signal"') - 4000` was
  a character budget standing in for "the depth read is not on the 20 Hz
  path". Adding the A78 gate broke it even though the gate sits AFTER the
  read and cannot make it run more often. Replaced with the real property:
  the read must come after the `confidence` and `no_offer` gates and before
  the signal record.

## Revert

```powershell
# drop the ceiling: remove "--early-max-price", "0.975", from restart_bot.ps1
# drop the day cap: git revert the A79 commit (it has no flag)
powershell -ExecutionPolicy Bypass -File C:\kals-repo\restart_bot.ps1
```

---

# v-noboost -- 2026-09-20 -- LIVE: the 90-94c 1.5x boost is removed, on its own pre-registered bar

`--band-mult 0.90 0.94 1.5` (A53, v-bands, live since 09-18 22:46Z) shipped
with this bar written at deploy: **"revert at the FIRST loss on a boosted fill
in the first 20 boosted closes; at 20 clean, raise to 2.0."**

The first boosted loss came on the **third** boosted close:
`KXBNB15M-26SEP191230-30`, -$61.75, where the 1.5x multiplied the order into
83 contracts on a level that held 23. `band_boost_off` fired at
2026-09-19T16:30:20Z, as designed -- **but the switch lives in process memory
and every restart re-armed it.** The bot has restarted eight times since.

Lifetime, live fills: **3 boosts, 92 boosted contracts, +$5.28, 1 losing
close.** The bar is met. The flag goes. This is not a judgement about the
90-94c band -- it is the best band we have (70 closes, 1 loss, 6.4c a
contract) -- it is the bot keeping a promise it wrote down before the data
came in.

Restore: put `"--band-mult", "0.90", "0.94", "1.5",` back in `restart_bot.ps1`
and restart. A persistent off-switch would be the right way to bring it back.

## Also corrected here

v-hedgefill's DEPLOY block says `--hedge-slip` went live at 21:58:25Z. The
21:58 restart shipped the A70 CODE with the flag at its 0.0 default; the flag
itself first appears in a `start` record at **2026-09-19T22:50:22Z**. So
`--hedge-slip 0.03` has been live since 22:50Z, not 21:58Z.

---

# v-proportion -- 2026-09-20 -- LIVE: hedge in proportion to conviction, and a quarter off the bet

**DEPLOYED 2026-09-20 05:46:57Z (01:46 ET), pid 1412748, SHA `0061111`.** First autosize: 20 -> 70 contracts at the $825.04 bank (was 93 at brake 3.00). Start record: hedge_prop True, full 0.20, half 0.40. One live process, no halt.

**On the operator's word.** On the hedge: *"Sure on
proportion but make sure if it starts at half then drops below 20 you buy the
rest of the hedge."* On size: *"Make the bet size only a quarter smaller not
half then as proportional."*

## Why

Every alarm the bot has ever raised (18) was rebuilt second-by-second from
the raw CF Benchmarks index. **Nothing visible at the alarm second separates
a real collapse from a false alarm** -- crossing depth, market-wide or not,
belief level, seconds left: every one overlaps. The information arrives
1-10 s later, and on a real collapse the other side is at 99c by then
(trade tape: 58c -> 99c in 5 s on BTC 09-14; 51c -> 87c on HYPE 09-14).
So a confirmation delay is +$37 across everything and **-$79 with the
09-19 23:45 close removed** -- its whole benefit is one close. A hedge
cannot be made rarer without making it useless. It can be made SMALLER
where the model is least sure.

Under the current rules (`--hedge-price 0.60` since 09-18) the hedge is **9
saves (+$112.86) to 2 false alarms (-$116.87)**. Both false alarms were one
close, hedged in FULL at 27% and 50% belief -- a coin flip locked in at
46c -- on 104-contract positions, the largest ever held. Full hedges under
20% belief have been right every time.

Two corrections to earlier reporting, same day: `KXBTC15M-26SEP172115-15`
was a REAL loss (the bot restarted holding it and never wrote a settlement),
not a false alarm; and five of the seven lifetime false alarms fired under
the old 0.80 threshold and are already blocked by `--hedge-price 0.60`.

## A76 -- the rule

Share of the position that should carry a hedge leg:

| belief in our side | hedged |
|---|---|
| at or under **20%** | all of it |
| at or under **40%** | half |
| above 40% | none -- a coin flip is not a collapse |

**The top-up (the operator's condition):** the hedge tracks a TARGET against
what is already covered. A position half-hedged at 30% whose belief falls to
15% buys the other half. A position whose belief recovers is never sold
down.

On tonight's two: XRP 104 -> 52 contracts, HYPE 104 -> 0. On the nine real
losses: three at 52-56% belief would have gone unhedged (~$32 of saves) and
two at 21-24% would have been halved (~$16). Net about +$40 better than the
current rule on the same 15 clusters that produced it. **Below the
30-cluster floor; the operator chose it knowing that.**

What it blocks, per the 09-19 rule: the hedge entirely between 40% and 60%
belief, and half of it between 20% and 40%. `hedge_want()` can never return
more than the contracts still uncovered. `--no-hedge-prop` restores today's
all-or-nothing; `--hedge-prop-full` / `--hedge-prop-half` move the bands.

## The bet: `--bank-brake 3.00 -> 4.00`

Three quarters of the bet: ~69 contracts at the $821 bank instead of ~93.
Size has not been earning more (no correlation between size and daily money
-- the price paid rose with it) and the cheap end of the book has halved,
so a big order walks further up the ladder for less. The ratio stays the
brake.

## Evidence

- Self-test: A76 driven by tonight's real numbers (104 @ 0.27326 -> 52; 104
  @ 0.50066 -> 0), the top-up step by step (30% -> 52, then 15% -> the other
  52, then nothing), the no-sell rule (recovery -> 0, never negative), the
  exposure bound (never more than uncovered), garbage in -> 0 not raise (the
  hedge pass has no try/except), and `--no-hedge-prop` = today exactly.
  Structural: an idle second `continue`s BEFORE a try is counted; the alarm
  is keyed on its own set; live AND paper judge "done" against the uncovered
  count so a half hedge stays open for its top-up.
- Startup path run with the exact deploy flag list, paper.

## Revert

```powershell
# hedge back to all-or-nothing, bet back to 3.00: edit restart_bot.ps1
#   add   "--no-hedge-prop",
#   set   "--bank-brake", "3.00",
powershell -ExecutionPolicy Bypass -File C:\kals-repo\restart_bot.ps1
```

---

# v-settledonly -- 2026-09-19 -- LIVE: an unsettled bet is no longer counted as a loss

**The operator, and the log agreed with him word for word:** *"I don't know
why it seems like it was calculating the total lost before the bet has
settled. If it was seeing a current bet is down 100 then adding that to the
loss total that is wrong. You should only wait for the bet to end and be
finalized before you count it because that's only the true total."*

## What was wrong

`risk_abort`'s forward-looking bound was
`realised - open_cost - one more contract`, and **`open_cost` is the full
PURCHASE PRICE of everything open, not its mark to market.** So every held
bet was written off as a TOTAL loss the instant it filled -- on a strategy
that wins about 97 times in 100. Real pause records:

```
pause: loss bound: realised $+43.56 with $145.00 still open
pause: loss bound: realised  $+0.00 with $101.15 still open
pause: loss bound: realised $+31.19 with $210.06 still open
```

**It paused the bot while the run was UP $43.56.**

## And it cost no trades -- CURRENT_STATE was wrong about that

Measured across every live run: **28 pause->resume spans, and in ZERO of
them did the bot signal or send an order.** The operator said the cap had not
cost us bets and he was right. `CURRENT_STATE.md` claimed it "blocks NEW
trades for the rest of that close"; that claim was never measured and is
withdrawn.

What it really was: noise in the log, sitting on the same code path whose
`continue` skipped a hedge and cost **$107.95** earlier the same day.

## What it is now

The loss brake is the SETTLED check that already sat one line above it:
`realised <= loss_abort`. Nothing replaced the forward bound.

**WHAT THAT GIVES UP, AND THE OPERATOR HAS BEEN TOLD THE NUMBER.** The run
stops on $200 of FINALISED losses, and whatever is in flight at that moment
is on top. In flight is bounded elsewhere and always was -- the open cap
(`max_positions x SIZE` contracts), the stake cap, and the per-close budget.
At 98 contracts that is **$200 settled plus at most 3 x 98 x $0.98 = $288
open, so about $488 worst case against the old ~$200.**

The old comment defended the bound by saying a settled-only abort "is inert
entirely if the settlement reader is failing". That hole is real and is now
covered properly by A71's `RECONCILE_FAIL_HALT`, which halts on the reader
being broken rather than guessing at losses that have not happened.

## Evidence

- **849 self-test checks pass.** The A73 checks are driven by the FIVE REAL
  (realised, open) pairs from the live log, at the size the bot was actually
  running; each must now be a no-op, and each must come back under the flag.
- `PLANTED: $200.00 of FINALISED losses still halts the run` -- the brake
  that now carries the whole job is asserted to fire, and asserted not to
  fire a cent under.
- The loss bound is asserted to still sit BELOW the hedge pass (A69).
- Startup path run with the exact deploy flag list, paper: SELF-TEST PASSED,
  exit 0.

## Revert, copy-pasteable

Add the flag to `restart_bot.ps1` -- no code change needed:

```
"--loss-bound-open",
```

or revert the commit:

```powershell
cd C:\kals-repo
git revert --no-edit <SHA>
powershell -ExecutionPolicy Bypass -File C:\kals-repo\restart_bot.ps1
```

---

# v-hedgefill -- 2026-09-19 -- LIVE: the hedge could not fill, and paper could not hedge at all

**Deployed by this session on the operator's instruction: *"I'm not
restarting for you you just do it and stop asking me to"* and, on
`--hedge-slip`, *"Yes Turn the thing you want to change on."*** Deploy time,
pid and SHA are recorded in the DEPLOY block at the end of this entry.

`--hedge-slip 0.03` is now passed by `restart_bot.ps1`. A71 is code, not a
flag, so it went live with the same restart.

**`--loss-cap 200` was NOT changed.** It is what the operator asked for
("Cap losses at 200, keep bet size") and he did not answer the question about
raising it, so it stays. A69 already made the pause safe -- the hedge runs
regardless of it.

## A71.1 -- every paper arm has been an unhedged bot

The hedge pass skips any position missing from `hedge_meta`, and `hedge_meta`
was written at two sites, both live-only. A paper position never had a
strike, so its belief was never computed, so the alarm never fired.

**Measured: the five paper arms running on 09-19 logged 151 signals between
them, ZERO `hedge_alarm` and ZERO `hedge` records. Live on the same markets:
2 alarms, 8 hedges, 2 panics.**

A filled hedge turns a -73c..-96c loss into -26.9c per contract. So every
arm-vs-live head to head has compared a bot that eats its losses whole
against one that insures them. **Arm numbers on losing closes are not
comparable before this SHA.** It also means no hedge change was ever
testable without real money -- A62, A69 and A70 all went straight to live.

## A71.2 -- an ENTRY rail could permanently disable a hedge

The hedge's per-close cap read `attempts`, which the entry path increments,
against `MAX_ATTEMPTS_PER_CLOSE` = 24. Twelve coins settle on the same
quarter hour, so the bot's own buying could spend the budget and then refuse
-- permanently, via `hedged.add()` -- to insure a position already held.
The hedge now counts its own sends against `MAX_HEDGE_ATTEMPTS_PER_CLOSE`
= 120, above anything ordinary hedging can reach (3 positions x 30 tries,
one per second).

## A71.3 -- three hedge skips were silent

No `hedge_meta`, no sigma, no fair value: all skipped the hedge writing
nothing. A feed stutter during a collapse looked exactly like the A69 pause
bug. They now write `hedge_blind`, deduped per (position, reason).

## A71.4 -- bookkeeping above the hedge could kill the process

`report_closes()` and `reconcile()` run before the hedge pass and neither was
wrapped. A69 moved the hedge above the risk check because a `continue` there
cost $107.95; an exception above it ends the process holding a position,
which is the $66.34 loss from the same day. Both are now guarded. A
persistent reconcile failure still halts -- a frozen ledger makes every brake
in `risk_abort` inert -- but it halts IN `risk_abort`, below the hedge pass,
so the last iteration insures what is open first.

## A70 -- `--hedge-slip` (ships at 0.0, OFF)

The entry path has sent a limit above the touch and sized from the ladder
since A35. The hedge sent the ask it saw and the touch size -- one stale
level, priced to the tick -- so when the market moved, which is when a hedge
is needed, the IOC crossed nothing.

**All 29 live hedge attempts, the failures:**

| ticker | tau | asked | touch | filled |
|---|---|---|---|---|
| KXBTC15M-26SEP172115-15 | 36 | 99 | 283.8 | **0** |
| KXBTC15M-26SEP172115-15 | 35 | 99 | 7419.0 | **0** |
| KXBNB15M-26SEP190145-45 | 20 | 76 | 96.0 | **0** |
| KXBNB15M-26SEP190145-45 | 19 | 25 | 25.0 | **1** |
| KXBNB15M-26SEP191230-30 | 11 | 28 | 28.0 | **1** |

Ten of twenty-nine filled nothing or one contract against a book displaying
everything we asked for. The 01:45 BNB close is the **only escape failure in
the project's history** (-$57.76): A62 removed the FILTERS that blocked it
and it still did not fill, because nothing had fixed the EXECUTION.

`hedge_depth()` can only return MORE than the touch, so no hedge that fills
today stops filling; the ladder's contribution is capped at the contracts
still unhedged, past which a leg is naked (A63). `hedge_vwap()` makes a paper
arm pay the ladder average, not the touch.

## Evidence

- **832 self-test checks pass, 66 new.** `shadow.py` and `markers.py` clean.
  `versioncheck.py` clean.
- The launcher's exact flag list **plus `--hedge-slip 0.03`** was run through
  the startup path in paper before commit -- the check that has stopped this
  bot booting five times.
- Fill counts are from live fills only (rule 5). No replay was used.

## Revert, copy-pasteable

```powershell
cd C:\kals-repo
git revert --no-edit 1bd47c9
powershell -ExecutionPolicy Bypass -File C:\kals-repo\restart_bot.ps1
```

A70 alone is off by default; simply do not pass `--hedge-slip`. A71 has no
flag -- reverting the commit is the way back.

---

# v-taper -- 2026-09-19 ~13:2xZ -- LIVE: buy LESS as the price gets worse (A67), and a bounded bet on the side that is now winning (A68)

Both came out of `KXBNB15M-26SEP191230-30`, which cost **$61.75**.

## A67 `--no-taper` (the taper is ON)

The bot signalled that close at **91.5c** and the 82.8 contracts it got cost
an average of **97.27c**. A35 sized the order from `buyable()` -- every
contract under the 98c sweep limit -- and 11,937 were. Only **23** of them
were at 91.5c.

A35's own comment says why it thought that was safe: *"every extra contract
is already gate-approved."* True and not sufficient. 91.5c clears the gate by
7.8c; 98c clears it by 1.7c. Buying the same quantity of each treats a fifth
of the edge as the whole of it.

Now each price level is weighted by how much of the touch's edge survives
there -- full size at the best price, `size x (edge here / edge at touch)`
above it, nothing once the edge is gone. **On that exact book it asks for 47
instead of 114.**

`--taper-floor FRAC` additionally refuses any level worth less than FRAC of
the touch's edge (default 0.0 = take them, in proportion).

## A68 `--rebuy-mult` (ships at 1.0)

Operator: *"at 15% confidence if our confidence is accurate shouldn't we have
known it's 100% flipping ... even extra than the hedge."*

**Measured, live fills only: every market whose belief fell under the 40%
panic line went on to lose. 6 of 6.** The model is CONSERVATIVE down there --
at 0-5% belief it implies ~98% should lose and 100% did. Above 60% belief 0
of 4 lost, so a mild wobble does recover and this must not fire on one.

So while belief is at or under the panic line, more of the side we hedged
INTO is an ordinary bet at 85c-or-better odds, **capped at 1.0x the contracts
held on the losing side**.

**THE TAIL, STATED IN ADVANCE.** On the BNB close: +$19 expected, and **-$51
worse than the hedge alone** in the ~15% case where it comes back. That is
the trade. A63 was refused for having no cap at all (it would have bought 138
more and taken the worst case from +$3 to -$134); the bet was never the
problem, the size was. n = 6 closes, so the multiple ships at 1.0 and the
caution goes into the size rather than into refusing.

## Evidence and revert

Startup path run with the launcher's exact flag list, paper, `--minutes
0.35`: SELF-TEST PASSED, clean stderr. New checks assert the taper against
the real BNB book and the cap against the real contract counts.

- taper off: add `"--no-taper"` to `restart_bot.ps1`.
- the extra bet off: add `"--rebuy-mult", "0"`.
- both are code-default ON, so reverting the commit reverts them.

---

# v-mirror -- 2026-09-19 12:26:03Z -- LIVE: the bot publishes its contract size so paper arms trade proportionally

SHA: see `git log --oneline -1` at deploy (A66 commit "A66: paper arms trade
the size LIVE trades, and the self-test can no longer forge it").

## What the bot now does differently

On every autosize it writes `results/pinrun-live-size.json`. **Nothing about
its own trading changes** -- no gate, no price, no size, no rail. The file is
write-only from live's point of view; only paper arms read it.

## Why

Paper arms were pinned at 20 contracts while live ran 109. Zero autosize
records across all 43 arms since 2026-09-14, because `read_bank()` needs a
key a paper arm does not have and must never be given. So every arm's dollar
figure was measured at a stake that never faced live's depth.

## Evidence

Measured, not modelled: 0 autosize records in 43 arm logs before; 62 records
reading "mirroring live size 110" after `restart_arms.ps1`. Live's own first
autosize on this version wrote the file at 12:26:04Z with size 110, bank
$970.58.

## The bug this shipped with, caught in paper within two minutes

The startup self-test drives `autosize_tick` with a fake $60 bank and
published `{"size": 7.0}` into the real mirror; 36 arms then sized themselves
to SEVEN. Same shape as the 2026-09-14 high-water-mark outage. `SIZE_MIRROR`
is now sandboxed for the whole self-test, with a check that a pathless
`publish_size()` leaves the real file byte-identical. **No real money was
involved at any point** -- live neither reads the file nor changes behaviour
because of it.

## Revert

`restart_bot.ps1` needs no change -- there is no flag. To stop arms copying
live, add `"--no-size-mirror"` to the arm launchers (`start_sigma.ps1`,
`start_bands.ps1`, `boot_all.ps1`), or delete
`results/pinrun-live-size.json` and arms fall back to `--size` within the
hour. To revert the code: `git revert 277be1f`.

---

# v-cap200 -- 2026-09-19 ~03:1xZ -- LIVE: a hard $200 loss cap; the bet size is UNCHANGED

Operator, immediately after depositing: *"Cap losses at 200, keep bet size."*
Bank went $674 -> **$927.62**.

## 1. `--bank-brake` STAYS AT 3.00 -- the size ratio does not move

**CORRECTED 2026-09-19 03:3xZ, in the operator's own words:** *"Wait why that
seemed perfectly fine I want the same size ratio just after $200 in losses
brake."*

This entry first shipped `--bank-brake` 3.00 -> 4.08, which cut the bet from
**105 contracts to 77** at the $928 bank. That was a size change he did not
ask for -- "keep bet size" meant keep the RATIO, and the ratio is the brake.
It was live for one close (03:30:58Z -> 03:3xZ, size 77, no fills) and is
reverted. The bet is 105 contracts again and the bank covers a bad close
**3.0x**.

What the deposit buys is unchanged either way: the **close budget** rises with
the bank at any brake, and that is what `close_budget` was refusing 423
markets for.

## 2. AMENDMENT 65: `--loss-cap 200`

The loss abort has always been DERIVED -- `-2 x SIZE x MAX_PER_CLOSE`, a band
that survives two worst closes -- so it **grew with the bank**. It had already
reached **-$420** at 105 contracts, and nothing let the operator say "whatever
the arithmetic thinks, stop at two hundred dollars".

`abort_for()` now returns the TIGHTER of the band and the cap:

| SIZE | derived band | with a $200 cap |
|---|---|---|
| 105 | -$420 | **-$200** |
| 77 | -$308 | **-$200** |
| 20 | -$80 | -$80 (the band is tighter; a cap never RAISES the limit) |

**It is re-applied on every autosize**, not once at start-up. A cap applied
once is undone the next time the bank moves -- which is precisely how the old
one-way ratchet let the stop follow the bank up and never come back down.

A stray minus sign on the flag is ignored: the cap is a magnitude, so
`--loss-cap -200` and `--loss-cap 200` mean the same thing and neither can
turn a cap into a licence.

## What the cap can and cannot do

`LOSS_ABORT` is a **running-total** stop: once the run's settled P&L reaches
-$200 every further buy is refused. It is not a per-close stop and cannot be
one -- at 105 contracts a close holding all three legs has $309 at stake, so
one catastrophic close can pass straight through $200. `--max-losses 2` is the
brake that actually bounds that, and it is unchanged.

## Revert

`restart_bot.ps1`: delete `"--loss-cap", "200"` for the derived band
(-$630 at 105 contracts).

---

# v-late15 -- 2026-09-19 ~02:5xZ -- LIVE: the extra BUDGET reaches 15 s while the 1.5x boost stays at 10

Operator, on being shown that 423 markets were refused for `close_budget`:
*"Those sound like good trades why refuse them."* Then: *"Then increase to
15 seconds if it means better cheaper buys."*

## Why they were refused, and it is not a shortage

On the **97 closes where the budget actually ran out**:

| | |
|---|---|
| budget spent at MORE than 15 s left | **75%** of fills, median **97.6c** |
| budget spent at 15 s or less | 25% of fills, median 96.0c |
| when the refusals landed | median **21 s**; **38% inside 15 s** |

**We were spending three quarters of each close's budget early at 97.6c --
worth about 2.2c a contract -- and then refusing the cheaper trades later
because it was gone.** Not a budget shortage: the wrong trades first.

## The change

`--late-tau` was doing two unrelated jobs:

- **when an order may be 1.5x SIZE** (A48) -- extra RISK, on the bets with
  the least time to recover. Wants a TIGHT window. **Stays at 10 s.**
- **when a close may spend an extra bet of budget** (A59) -- not extra risk
  at all, only permission to spend what the close was already allowed.
  Wants a WIDE one. **Now 15 s, via `--late-extra-tau`.**

At a shared value of 10 the entire 11-15 second band was left out -- 38% of
every `close_budget` refusal we have.

## What it cannot do

It cannot raise the worst close. The extra bet still SHARES the
`--extra-coin` allowance (A61), so `worst_close_cost` is unchanged at three
bets, the bet size is unchanged at ~76 contracts, and the bank still covers
the worst close 3.0x.

## Revert

`restart_bot.ps1`: delete `"--late-extra-tau", "15",` and the budget window
falls back to `--late-tau` (10 s), which is the shipped behaviour.

---

# v-panic40 -- 2026-09-19 ~02:2xZ -- LIVE: the no-block line moves to 40% belief

Operator: *"Nothing can block a hedge under 40%. And most hedges just
shouldn't be getting 'blocked' anyway."*

## Every hedge we have ever placed, by the belief that triggered it

| belief | ask | what it did to the close |
|---|---|---|
| 2.0% | 95c | **HELPED** |
| 11.6% | 76c | **HELPED** -- the BNB that cost $57.98; its 21c hedge was BLOCKED |
| 21.4% | 43c | **HELPED** (+$24.18) |
| 24.3% | 74c | **HELPED** (+$8.29) |
| 48.5% | 15c | hurt (-$13.83) |
| 52.5% | 80c | **HELPED** |
| 53.3% | 47c | **HELPED** |
| 55.9% | 51c | **HELPED** (+$29.30) |

(Four more at 64-89% belief all hurt, but `--hedge-belief 0.60` already
stops the hedge firing that high, so they cannot recur.)

**Every hedge at or under 24.3% belief helped.** The only one that hurt sat
at **48.5%** and was bought at **15c** -- precisely what `--hedge-price
0.60` refuses.

## So the 40% line is the right one

- **Below 40%:** nothing touches the hedge. Not the market-agreement test,
  not the normal-bet test, not the attempt cap, not the try cap. Only
  arithmetic: the leg must cost under $1, and there must be an ask.
- **40-60%:** the market-agreement rule survives, and on this record it
  blocks the ONE hedge that hurt and passes all three that helped.

Of the eight hedges that would fire under today's trigger, exactly one is
still subject to a filter, and it is the one that lost money. That is what
"most hedges shouldn't be getting blocked" looks like in code.

## Revert

`--hedge-panic 0` disables the bypass entirely -- the behaviour that cost
$57.98. `--hedge-panic 0.35` returns to the first version of this rule.

---

# v-nohedgeblock -- 2026-09-19 ~02:1xZ -- LIVE: NO filter may block a hedge on a collapsed bet, and it keeps trying for 30 s

**This entry exists because a rule I deployed four hours earlier cost
$57.98.** The operator: *"NOTHING SHOULD BE BLOCKING A HEDGE ON A LIVE BET
WITH A 22% CONFIDENCE RATING ... I HAVE SAID OVER AND OVER HOW CRITICAL
HEDGING IS."* He is right and this should never have shipped.

## What happened -- KXBNB15M-26SEP190145-45

| seconds left | event |
|---|---|
| 30 | signalled YES at 97c, order filled NOTHING |
| 25 | dump guard refused an 82c offer as too-good-to-be-true |
| 24 | signalled at 85c -- **filled 76 contracts at 74.98c**, the book collapsed inside the round trip |
| 23 | hedge alarm, belief **0.227** |
| **23** | **hedge BLOCKED by `--hedge-price 0.60`** -- the other side was 21c, but OUR side still quoted 79c |
| 21 | tried at 51c, filled 0 |
| 20 | tried at 70c, filled 0 |
| 19 | tried at 76c, filled **1 contract** |
| 18 | **gave up** (HEDGE_MAX_TRIES was 5), eighteen seconds still on the clock |
| settle | **-$57.98** |

| hedge at | cost | the close nets |
|---|---|---|
| **23 s at 21c** | $15.96 | **+$3.06** |
| 21 s at 51c | $38.76 | -$19.74 |
| 19 s at 76c | $57.76 | -$38.74 |

**A $61 swing, lost to a filter.**

## A62: below 35% belief, nothing may block a hedge

`hedge_panic(belief)` is true at or under **0.35**. In a panic the loop
bypasses **every discretionary filter**:

- the market-agreement test (A47, `--hedge-price`)
- the normal-bet test (A51, `--hedge-normal`)
- the per-close attempt cap
- the try cap

What still applies is arithmetic rather than opinion: the leg must cost
under $1 (`hedge_ask_ok` -- a leg at or over $1 cannot beat holding), and
there must be an ask to hit. **A missing belief is NOT a panic**: it must
not trigger the one path that ignores every other safeguard.

**Why the market-agreement rule was wrong here.** Its evidence was 5 of 5
cheap hedges hurting -- but those were FALSE ALARMS, positions that
recovered. This was a real collapse: our model knew in one second and the
market took two more. What the market thinks is not evidence against our
own model; it is a two-second lag we have now measured and paid for.

**And the operator's standing answer to the objection**, said many times
before tonight: a hedge that turns out wrong is not a trap. *"ONCE
CONFIDENCE REBUILDS ON EITHER SIDE YOU CAN JUST BUY MORE OF THAT SIDE."*
Being on both sides is recoverable; being naked in a collapse is not.

Above 35% belief the market-agreement rule still applies, which is where
its evidence actually came from.

## A62b: HEDGE_MAX_TRIES 5 -> 30

Five tries gave up at 18 s with the position naked. The runaway that cap
was written for is ORDERS PER SECOND, and the one-per-second pacing is what
prevents that -- not the total. 30 cannot outlive a close (the window is
45 s).

## What is NOT fixed, and is the next thing to look at

**The entry.** The dump guard refused 82c as a crazy deal (over 15c under
fair), the next signal came at 85c -- 14.9c under, squeaking below the bar
by a tenth of a cent -- and the IOC then swept down to **74.98c, 25c under
fair**. The guard checks the price we SEE; it cannot check the price we
GET. Someone sold us 76 contracts at 75c because they knew where BNB was
going. A fill far below the ask we saw is a picked-off signal and nothing
currently reacts to it.

## Revert

`--hedge-panic 0` disables the bypass entirely (that is the behaviour that
cost $57.98). A62b is code: set `HEDGE_MAX_TRIES` back to 5.

---

# v-latebudget -- 2026-09-19 ~01:3xZ -- LIVE: the extra-bet allowance actually works now, and it reaches the last ten seconds

Operator: *"Fix the one that refused 126 markets too that's really bad."*
Two things, and the first is a defect in what went live three hours ago.

## 1. AMENDMENT 61: the third-coin allowance could not fire in 68% of closes

`close_budget_for` required `len(coins) >= MAX_PER_CLOSE` before granting
anything -- I read "after two have been maxed out" as two COINS. **But a
close spends its budget in CONTRACTS.** One market taking two bets exhausts
it without a second coin ever existing, and **282 of our 417 closes hold
exactly one coin**. So the allowance deployed at 00:03 tonight was dead in
more than two thirds of closes.

Measured on the 126 markets `close_budget` refused inside the last ten
seconds:

| what it was | count | fixed by |
|---|---|---|
| a NEW coin with fewer than two coins held | **97** | A61, this entry |
| a coin we already held | 29 | A59, below |

The test is gone. Nothing else guards it and nothing needs to: the function
is only consulted when the base budget is under pressure, the caller still
refuses unless `spent` is under the number it returns, and the exposure was
already counted in `worst_close_cost`. **Risk unchanged, allowance 3.5x more
usable.**

## 2. `--late-extra 1` goes live, SHARING the allowance rather than adding one

Inside `--late-tau` (10 s) a close may spend one extra bet whatever it
already holds -- the 29 above, and any top-up.

**It shares the extra bet with the coin allowance rather than adding a
second.** Summing them would put the worst close at FOUR bets and, at a
fixed brake, cut the bet a quarter to pay for a case that has never
happened. At a $640 bank and a 3.00 brake:

| | bet size | worst close | bank covers |
|---|---|---|---|
| third coin only (00:03 tonight) | 72 | $211.68 | 3.02x |
| **third coin + late top-up, shared** | **72** | **$211.68** | **3.02x** |

**The bet size does not move and neither does the worst case.**

## Why that window is worth it -- our own live fills

| seconds left | fills | contracts | median price | per contract | losing |
|---|---|---|---|---|---|
| 0-5 | 23 | 1,028 | 94.3c | 5.354c | 0 |
| 6-10 | 45 | 2,158 | 94.8c | 5.461c | 0 |
| 16-30 | 344 | 13,023 | 97.2c | 2.103c | 11 |
| 31-45 | 81 | 3,933 | 97.8c | 2.197c | 1 |

## Revert

`restart_bot.ps1`, then `.
estart_bot.ps1`:

- **the late allowance only:** delete `"--late-extra", "1",`.
- **both allowances:** delete that and `"--extra-coin", "1",`, and set
  `"--bank-brake", "4.08"` (or the size stays cut for nothing).

A61's fix is code, not a flag; reverting it means reverting the commit.

---

# v-cheap -- 2026-09-19 ~01:0xZ -- LIVE: the 96.5c price floor is gone, and a top-up can finally be boosted

Two changes, one cause. The operator: *"WOAH WHAT WE CANT BUY CHEAPER THAN
96.5??? ... boost needs to apply to all trades ... please get rid of
whatever is blocking us from cheap trades."*

## 1. `--early-max-edge` 3.0 -> 10.0 : the cap was a price floor in disguise

Our model is usually ~100% sure, so edge is `(1 - price) - fee`. A cap on
EDGE is therefore a floor on PRICE, and nobody intended it:

| price | edge | 3c cap | 10c cap |
|---|---|---|---|
| 90.0c | 9.37c | refused | allowed |
| 94.0c | 5.60c | refused | allowed |
| 96.0c | 3.73c | refused | allowed |
| 96.5c | 3.26c | refused | allowed |
| 97.0c | 2.79c | allowed | allowed |

**That is why every fill was 97-98c.** The 90c floor we deployed on 09-18
as the adverse-selection guard never got a chance to bind. At 10.0 the
floor binds instead, so the 31-45 s leg may now buy 90-98c.

It refused 18 live trades, the cheapest **90.0c with 8.88c of edge**.

**What we give up.** A50 was built on the TAPE -- 6c+ edges at 31-45 s lost
3 of 11 -- and rule 5 says the tape cannot price our losses. The one live
loss of that shape was 93c, 6.43c edge, -$18.69, in the uncapped arm. Both
uncapped arms lead live (+12% on 27 markets, +41% on 28); neither is old
enough to be a result.

**BAR: revert to 3.0 at TWO losing closes on early fills under 96c in the
first 40 such fills.** The 90c floor does not move tonight.

## 2. A60: the top-up re-cap now counts the late boost

`_stage46` capped a top-up at `SIZE - early_held`, whatever A48's boost had
asked for. So a market entered outside the last 10 seconds could NEVER be
boosted inside it -- which is why, in 547 filled markets, **not one was
bought outside 10 s and again inside it**.

Holding 60 of an 80-contract bet, a top-up at 8 s could add 20 more; it may
now add 60. The boost's own conditions still decide whether the extra
contracts are bought: `--late-pin 0.9975` and `--late-jump 2.0` are
unchanged, and a larger cap cannot raise a number the boost never widened.

## What this does NOT fix, and the arm that tests it

`close_budget` still refused 126 markets inside the last 10 seconds -- 97
we did not hold and 29 we did. `--late-extra` (A59) adds a bet of budget
there and is PAPER ONLY tonight: `arm-lateextra` and `arm-nocap-late`.

## Why the last ten seconds is worth this trouble

Our own live fills, every one:

| seconds left | fills | contracts | median price | per contract | losing |
|---|---|---|---|---|---|
| 0-5 | 23 | 1,028 | 94.3c | 5.354c | 0 |
| 6-10 | 45 | 2,158 | 94.8c | 5.461c | 0 |
| 16-30 | 344 | 13,023 | 97.2c | 2.103c | 11 |
| 31-45 | 81 | 3,933 | 97.8c | 2.197c | 1 |

## Revert

`restart_bot.ps1`, then `.
estart_bot.ps1`:

- **the price floor only:** set `"--early-max-edge", "3.0"`.
- **the top-up boost only:** it is code, not a flag -- set `--late-mult 1.0`
  to switch the whole late boost off, or revert commit.

---

# v-thirdcoin -- 2026-09-19 ~00:2xZ -- LIVE: a third COIN may spend beyond the close budget, and the brake moves 4.08 -> 3.00

Operator: *"if we've never lost multiple coins at once, allow extra total
size if it comes in the way of an extra coin after two have been maxed out.
I'm okay with that."*

## The condition he set, measured

**Of 417 closes we have traded, 19 had a losing coin and NOT ONE had two.**
In every one of the nineteen, the other coins at that close won or there
were none. Twelve of those closes already held three coins.

Why it is not luck: a close loses only when the last seconds move against
the side we took ON THAT COIN. Correlated moves across coins are common;
correlated moves that cross twelve different strikes in the same direction
inside the same second are not.

## And the budget really does bind

`close_budget` refused **326 markets on a coin we were NOT holding** -- about
**65 a day** -- against 95 on a coin we already had. So this is not a
theoretical allowance.

## What the bot does differently

A close may now spend **one extra bet of budget on a coin it is not already
holding**, once the base budget has been spread across MAX_PER_CLOSE coins.
A coin we ALREADY hold gets nothing extra: the argument is that two COINS
have never lost together, and topping up the first coin adds a second bet on
it, not a second coin.

## The price, and the choice he has

`worst_close_cost` grows from two bets to three, and **every rail reads it**
-- the bank brake, the loss abort, the stake cap -- so the extra coin is
paid for in the bet size rather than discovered in a drawdown. At a $640
bank:

| brake | extra-coin | bet size | worst close | bank covers it |
|---|---|---|---|---|
| 4.08 | 0 (before tonight) | 80 | $157 | 4.1x |
| 4.08 | 1 | **53** | $156 | 4.1x |
| **3.00** | **1 (deployed)** | **72** | **$212** | **3.0x** |
| 2.72 | 1 | 80 | $235 | 2.7x |

He asked for extra TOTAL size, not the same total spread thinner, so the
brake moves to **3.00**: bets 80 -> 72, a third coin allowed, worst close
$157 -> $212. **One line changes it either way** -- 4.08 keeps tonight's
risk exactly and accepts 53-contract bets; 2.72 keeps 80-contract bets and
a $235 worst close.

## Also in this restart

- **AMENDMENT 57, `--sigma-stress`** exists as a flag now (it was a constant).
  It multiplies the volatility estimate EVERYWHERE -- entry, sweep limit and
  hedge. **Not live**: four paper arms run it at 0.8, 1.25, 1.5 and 2.0, and
  a live run refuses anything under 1.0.
- **AMENDMENT 58**, every settled record now carries a `boost` field: one
  plain sentence saying whether the last-seconds boost fired and why not.

## Revert

`restart_bot.ps1`, then `.
estart_bot.ps1`:

- **third coin only:** delete `"--extra-coin", "1",` and set
  `"--bank-brake", "4.08"`. Both, or the bet size stays cut for nothing.

---

# v-late10 -- 2026-09-18 ~23:5xZ -- LIVE: 1.5x the bet inside the last 10 seconds, on three conditions the operator set

Operator: *"Yes a48 live, make sure it's got good confidence when buying in
the last 10 seconds, have it run at the full normal rate immediately, cut at
first loss. If it looks like it's going to a loss don't buy the extra, and
obviously if it's losing hedge if possible in those last seconds."*

## What the bot does differently

Inside the last 10 seconds one order may reach **1.5 x SIZE** (about 120
contracts at tonight's 80), through the same three rails A45 and A53 use:
the drawdown headroom `(bank - 0.8 x high-water) / ceiling`, what the book
holds at or under the sweep limit, and the close budget.

## Evidence

**The paper arm, 49 markets over 29 hours, ZERO losses, +15.1% against the
live bot on the same markets** (scaled to our own contract volume, so it
compares the strategy and not the stake). It is the only arm old enough to
read that beats live and was not already deployed. Independently, our own
live fills say the window itself is where the money is:

| seconds left | contracts | per contract | losing closes |
|---|---|---|---|
| 0-5 | 1,028 | 5.35c | 0 |
| 6-15 | 4,125 | 3.80c | - |
| 16-30 | 11,363 | 1.90c | - |

**What is NOT proven:** that a 1.5x order fills at the same price as a 1x
one. Paper cannot see a seller choosing to hit us. Rule 5.

## The three conditions, each in code

**1. "good confidence" -- `--late-pin 0.9975`.** The EXTRA contracts need
99.75% confidence in our side where an ordinary bet needs 99.5%. Measured on
all 109 live signals inside 10 seconds: the bar allows 71% of them, and the
ONE that ever lost sat at **99.612%** -- under the bar, so it would have
been refused the extra. The ordinary bet is untouched at every confidence.

**2. "don't buy the extra if it looks like a loss" -- `--late-jump 2.0`.**
A one-second move of 2 sigma against our side skips the boost.
**It must be TIGHTER than `--jump-gate`'s 3.0**, which already refuses the
whole trade: every candidate reaching the boost has passed that bar, so a
`--late-jump` at or above 3.0 could never fire. This was going to ship at
4.0 -- decoration in the start record and in this file. `pinrun` now refuses
to start on such a value, and the same guard refuses a `--late-pin` that is
not above the ordinary gate. Honest limit: jumps are rare (27 refusals in
eleven days), so this is a safety valve, not a volume lever. Condition 1 is
the one doing the work.

**3. "cut at first loss" -- no flag, the bot does it.** One late-boosted
loss sets `LATE_MULT` back to 1.0 for the rest of the run and writes
`late_boost_off`. The extra cost of the boost is therefore bounded by ONE
trade's extra size, about $37 at tonight's bet.

**And hedging is unchanged** -- it fires on belief at any tau including
inside the last seconds, now with the v-bands rule that the market must
agree.

## Revert

`restart_bot.ps1`, then `.
estart_bot.ps1`:

- **boost only:** delete `"--late-tau", "10", "--late-mult", "1.5",`
- **its conditions only:** delete the `--late-pin` and `--late-jump` lines
  (this returns A48 to exactly the arm that was measured)
- **all of it:** delete all four.

---

# v-bands -- 2026-09-18 ~22:3xZ -- LIVE: hedge only when the market agrees, and 1.5x at 90-94c that switches itself off after one boosted loss (`c015709`, off-switch and the skip's withdrawal in the commit after)

Two flags in `restart_bot.ps1` (a third was staged and withdrawn before it ran -- section 2), one entry, each with its own revert line.
Operator, 2026-09-18: *"Okay remove insurance. But keep hedging. We can remove
94-96. If it's safe then yea you figure out a way to buy more beneath 94."*

## 1. `--hedge-price 0.60` (AMENDMENT 47, live for the first time)

**What the bot does differently.** It still buys the other side when its own
belief in our side falls below 0.60 (`--hedge-belief 0.60`, unchanged) -- but
now ONLY if the market agrees: our side must also be trading under 60c, i.e.
the other side's ask must be over 40c. A hedge bought at 10-27c, when the
market still gave our side 73-90%, was insurance against a scare; a hedge at
47-74c is the market confirming the loss.

**Evidence (live fills, every hedge ever placed).** 9 genuine hedged
closes (the two `plant_attempt` test trades and two standalone cheap bets
excluded). The first cut of this table missed the two full-size losses of
09-14 because it was built from legs under 50c; the operator asked "this
version better still hedge when I lose", and the answer is in the rows:

| hedge ask | our side's price | closes | primary lost? | helped | hurt | net vs no hedge |
|---|---|---|---|---|---|---|
| 10-27c | 73-90c | 5 | no (all false alarms) | 0 | 5 | **-$41.72** |
| 43c, 47c, 51c, 58c, 74c | 26-57c | 4 | yes, 4 of 4 | 4 | 0 | **+$62.28** |

The real losses: BTC 09-14 (-$58.43, hedged at 43c and 58c, +$24.18 back),
HYPE 09-14 (-$59.20, hedged at 51c, +$29.30 back), DOGE 09-18 (-$3.93,
hedged at 74c, +$8.29), BNB 09-16 (-$0.98, hedged at 47c, +$0.51). Every
one of those hedges was bought with our side under 60c, so the rule passes
all four; every false alarm was bought with our side at 73c or more, so the
rule blocks all five. The margin between the two groups is 57c vs 73c. It is
also the same number as the belief trigger, so the rule reads: hedge when the
model AND the market both put us under 60%.

**Pre-registered bar.** Every alarm now writes `hedge_wait_price` when the
market disagrees. After 20 such waits, score them: if the blocked hedges
would have helped by more than the fired ones cost, lower the threshold to
0.70. If a position we waited on then lost unhedged, that is the price of
this rule and it is counted against it.

## 2. `--skip-band 0.94 0.96` -- STAGED, THEN WITHDRAWN BEFORE IT RAN

The flag exists (gate `price_band`; the sweep stops under a skipped band)
and stays in the code, OFF. It was in `restart_bot.ps1` for about an hour on
09-18 and was taken out before the operator restarted, because he asked the
right question: *"are we sure there's a correlation behind the 94 band
losing ... and it's not just coincidence."* It was coincidence.

The "+0.8% on 83 closes" that justified it is the WHOLE history, and three
of its four losses are from the first-week bot (09-09 NEAR, 09-10 BNB, 09-12
SOL) before the jump gate, the both-sides guard and the close-clustered
brake existed. On the modern bot (09-13 on): 38 closes, 1 loss, +$51.82 on
$2,305 -- **2.25%**, better than 96-97.5c (1.18%) and level with 97.5c+
(2.03%). The 95% bounds on every band from 94c up overlap. And the slot
argument had no evidence either: not one refusal under 94c has ever been for
a close budget or a position cap. The skip would have cost about 6.5 fills a
day at ~2.3% of ~$59 -- roughly $8/day -- to prevent nothing measurable.

Lesson, already in memory as "check the log dates against the deploy first"
and broken again here: split by bot era BEFORE recommending a refusal.
The paper arm `arm-b-skip9496` now tests the skip beside the control.

## 3. `--band-mult 0.90 0.94 1.5` (AMENDMENT 53, new)

**What the bot does differently.** Inside 90.0-93.9c one order may reach
1.5 x SIZE (about 117 contracts at today's 78), through the same three rails
A45 and A48 use: the drawdown headroom `(bank - 0.8 x high-water) / ceiling`,
what the book actually holds at or under the sweep limit, and the close
budget. After one ordinary loss the headroom alone shrinks the boost back to
SIZE. The order path's count cap now admits the multiple (it did not admit
A48's, which was a latent refusal). An early leg keeps the boost through the
A46 re-cap (`SIZE x mult`), so the 45 s leg can carry it.

**Evidence.** 90-94c: 64 live closes, 0 losses; the 95% upper bound on that
is about 4.6%, against an 8% break-even. On 09-18 the touch at 90-94c held a
median 192 contracts against the 97 we took (4 of 5 signals had 1.5x
available). What is NOT proven: that a 1.5x order fills at the same price
and the same loss rate -- a bigger order meets a smarter seller, and that is
the population rule 5 exists for. Hence 1.5x and not 2x, and the bar below.

**Pre-registered bar, ENFORCED BY THE BOT.** One boosted loss switches
`--band-mult` off for the rest of the run (`band_boost_off` record); the
extra cost of the boost is therefore bounded by one trade's extra size,
about $36 at today's bet. Revert the flag at the FIRST loss on a boosted
fill in the first 20 boosted closes. At 20 boosted closes with no loss and an average
fill within 0.3c of the ask seen, raise to 2.0 (the `arm-b-mult2` paper arm
runs it meanwhile). `band_boost` records carry was/now/cap/avail/room so the
binding rail is visible on every boost.

## What this is expected to be worth

Small and positive per day, larger for what it unlocks: the 1.5x step at
recent frequency (4-7 such fills a day, ~$70 stake) adds roughly $3/day at
the band's 8%; going to 2x and to 80-90c adds several times that. The skip
moves risk, not money. The hedge rule saves about the $33 it has cost so far
per week of similar alarms.

## Revert

All three are FLAGS. Edit `restart_bot.ps1`, then run `.\restart_bot.ps1`:

- **hedge rule only:** delete the `"--hedge-price", "0.60",` line.
- **1.5x only:** delete the `"--band-mult", "0.90", "0.94", "1.5"` line.
- **both:** delete both lines.

The paper arms in `start_bands.ps1` each change one of these against the
new baseline; `arm-b-control` is the new baseline itself in paper.

---

# v-ceiling99 -- 2026-09-18 ~17:4xZ -- NEVER LIVE: the 99c cap took the bot DOWN for ~5 minutes and was reverted

**What happened.** `restart_bot.ps1` was given `--price-ceiling 0.99` and the
bot did not come back: `pinrun` runs its own self-test at startup WITH the flag
already applied, and four older checks assert the 98c ceiling against the
RUNNING value (`worst_close_cost(20) must be ... 39.2, got 39.6`, `ladder_under
... under the 98c ceiling`, two A45 room checks "at the 98c ceiling"). They
failed, the process wrote "self-test failed -- nothing ran", and the live bot
was down from ~17:04 to ~17:09Z. The operator saw it before I did: "Also the
bot is down." My own `--selftest` had passed because it ran WITHOUT the flag.

**Reverted** to the 98c default. The `--price-ceiling` flag stays in the code
(the declared default is asserted, so it is harmless) but MUST NOT be passed
live until those four checks are rewritten against `_DEFAULT_PRICE_CEILING`.
This is the trap already in memory -- self-tests asserting running values
instead of declared defaults -- and it bit a fifth time.

**And the operator's condition was not met.** He said "As long as you're
certain 99c is more profitable." The evidence is 82 live markets at 98-99c,
1 loss (1.22%) against a ~1.4% break-even -- a margin of 0.2 points on one
loss, whose 95% upper bound is near 5%. That is "probably", not "certain".

## What the change WOULD be, for when he decides

**Operator, twice: "The two gates that trim volume without preventing loss,
remove or severely lessen them" and, shown the numbers, "I'm just following
your words."** The cap would become a FLAG at 0.99; the declared default stays
0.98.

## The two numbers he was following, reconciled

`pinattrib` reports, per gate, what every BLOCKED refusal would have paid if
it had filled, using the market's real settlement. Those are UPPER BOUNDS --
every refusal filled, none lost -- and they were quoted to him as money on the
table without the tail beside them. Put beside it:

| gate | "if filled" | per trade | our REAL record in that band | one loss |
|---|---|---|---|---|
| 98c cap | +$122.80 (379 trades) | 32c | 82 live markets, 1 lost, **+$51.07** | ~$76 |
| thin-profit floor | +$136.51 (1,048 trades) | 13c | 5 live markets, +$0.03 | ~$76 |

**The cap is lifted** because the band it excludes has a real, positive live
record including its one loss. The 09-09 resilience arithmetic is unchanged
and still true -- a loss at 98.5c takes ~65 wins to earn back where one at
98c takes 53 -- and he chose the volume with that in front of him.

**The floor is NOT lowered.** At ~99.5c a win is 13c and a loss $76, so one
loss erases 580 wins; break-even is one loss in 200. The 1,048 blocked
trades span roughly 300 closes (rule 4), which bounds the loss rate at
about 1 in 100 -- five times break-even. At any loss rate the data allows the
expected value is negative; the +$136.51 is the ceiling of the outcome, not
its middle. Standing offer: it moves only on his explicit word after this.

## Side effect

The ceiling enters the bet-size divisor: bank / (4.08 * 2 * 0.99) = 8.08, so
size is about 1% smaller than at 0.98. The bank-divisor self-test tolerance
was widened to admit it.

## Revert

```powershell
cd C:\kals-repo
# restart_bot.ps1: delete the "--price-ceiling", "0.99" line
.\restart_bot.ps1
```

---

# v-early-full2 -- 2026-09-18 ~17:0xZ -- LIVE: the 31-45 s leg goes from a THIRD to FULL size

**Operator: "If you're ready, then yes increase to 45."** `restart_bot.ps1`
now passes `--early-frac 1.0` (was `0.333`). The 90c floor and the 3c edge cap
on the early leg are unchanged.

## Why the third was never supported by the evidence

It was a precaution from a mechanism story -- at 45 s only a quarter of the
settlement average is locked -- and the live record does not bear it out:

| live window | markets | model misses | net |
|---|---|---|---|
| 31-45 s | 57 | 1 (hedged to +$4.36) | +$64.79 |
| 3-30 s | 475 | 11 | +$496.62 |

Same miss rate. The raw market at 31-45 s FAILS break-even on the tape in every
price band this week (research on 2026-09-18, `supplyclock.py`), so what makes
the live number good is the confidence filter doing real work at 45 s -- the
test it needed to pass.

Every miss in both windows is a single-second jump of 10-18 sigma with sigma
understated 2-3x at entry, and the losers sit inside the winners' confidence
range (`sigcheck.py`). No entry filter separates them: a 1.5x sigma stress
refuses all four 45 s misses and 88% of the wins. The defence is the hedge,
which is +$46.55 net across every alarm.

## Why full size matters more than the miss rate

Post-fix (after v-a8fix), of 34 early legs on live, **26 got no top-up because
by 30 s nothing was left to buy** (`no_offer`), 3 were topped up, 1 hit the
depth floor, 4 had no look. The early leg is not a starter position; on three
markets in four it IS the trade. At a third size that forgoes two thirds of
the position. Post-fix early legs at a third: 31 markets, 31 won, 0 lost,
+$33.59 -- roughly +$100 at full.

## The tail, stated

A jump loss at full size is three times a jump loss at a third. The one live
45 s miss cost the model leg $3.93 at a third; at full it is about $12 before
the hedge. The stage-2 bar from `PREREG_staged.md` still governs: revert to a
third at 3 losing early markets in 40, or 2 in the first 15.

## Revert

```powershell
cd C:\kals-repo
# restart_bot.ps1: change "--early-frac", "1.0" back to "--early-frac", "0.333"
.\restart_bot.ps1
```

---

# v-oilsweet -- 2026-09-18 ~15:4xZ -- LIVE: oil moves to 16-30 s at 93-99c, and to $20

**Operator: "Okay just do 16-30 93c+ then do a paper arm for 2-30. Increase to
$20."** `cmdlive` now runs `LIVE_WINDOWS = ("wti-sweet",)`, `LIVE_MAX_TAU = 30`,
launched with `--size 20`.

## Why the old window was wrong

The 0-15 s rule came from a MECHANISM STORY -- inside 15 seconds the one-minute
settlement candle is nearly formed -- and `research/oilband.py` measured the
story wrong. It walked **147,401 WTI takers over 287 settled closes**, counted
by CLOSE and not by trade (rule 4), and oil is better between 16 and 30 seconds
than inside 15 **at every price they share**:

| seconds | price | closes | lost | break-even | c/contract |
|---|---|---|---|---|---|
| 0-15 | 95-97c | 55 | 1 (1.82%) | 3.73% | +2.79 |
| **16-30** | **95-97c** | **41** | **0** | 3.73% | **+3.54** |
| 0-15 | 93-95c | 43 | 3 (6.98%) | 5.61% | **fails** |
| **16-30** | **93-95c** | **47** | **1 (2.13%)** | 5.61% | **+5.05** |

So the clock and the price floor INTERACT: under 95c is dangerous inside 15
seconds and safe between 16 and 30. The old rule had the worse half of the
clock AND a floor that excluded the best cell.

## Why 93-99c and not the wider clock the operator asked about

He asked whether 2-30 s would beat 16-30 s, since it fires more often. On the
tape it does -- 73 closes to 57, $32 to $28. But its extra closes carry THREE
losses instead of one, and losses are what get worse when a tape offer becomes
a real fill (rule 5, the 31x). Stressed at 2x, 3x and 5x the tape loss rate,
dollars over those three days at $10 a bet:

| rule | tape | 2x | 3x | 5x |
|---|---|---|---|---|
| 2-15 95-99c (the old live rule) | $13 | $8 | $4 | **-$5** |
| 2-30 93-97c | $32 | $27 | $22 | $13 |
| 2-45 93-97c | $33 | $20 | $7 | **-$17** |
| **16-30 93-99c** | **$29** | **$28** | **$27** | **$24** |

The rules that look best on tape are the ones that collapse. This one holds one
loss in 86 closes, and multiplying one loss by five is still one loss. It also
answers the volume worry outright: **86 closes, MORE than the 72 the old live
rule got** -- widening the PRICE band buys the volume back without buying the
losses.

**Rule 5 stands: this is all tape.** A paper arm on `2:30:0.93:0.99` is running
alongside (`results/cmdarm-wide230.jsonl`) so the wider clock keeps being
measured on real fills without being paid for.

## Size $10 -> $20

Operator's instruction. `MAX_CONTRACTS` is 40 and $20 at the 93c floor is 22
contracts, so the contract ceiling is not binding. The brake is unchanged:
stops at $25 net down or 4 losses in a day.

## Revert

```powershell
cd C:\kals-repo
# research/cmdlive.py: LIVE_WINDOWS = ("wti-near",) and LIVE_MAX_TAU = 15
# then relaunch with --size 10
```

---

# v-bank8 -- 2026-09-18 ~07:0xZ -- LIVE: one bet is the bank divided by 8, and the 45-second leg refuses a wide edge

Two changes, both of which REDUCE risk, deployed together on the operator's
word. `restart_bot.ps1` now also passes `--bank-brake 4.08 --early-max-edge 3.0`.

## 1. Bet size: bank/5.88 -> bank/8

**Operator: "Sure divide by 8."** He asked whether we were betting too high and
was shown this, at a $613.66 bank and 104 contracts a bet:

| if this happens | costs | quarter-hours to earn back |
|---|---|---|
| a typical loss (our 16 losses averaged) | $31 | 12 (~8 hours) |
| the worst we have ever taken | $93 | 37 (~1 day) |
| insurance fails completely, 96c to zero | $100 | 40 (~1.1 days) |

Size is `bank / (BANK_BRAKE * MAX_PER_CLOSE * PRICE_CEILING)`, so `BANK_BRAKE`
3.0 -> 4.08 makes the divisor 7.997. At the same bank: **104 contracts -> 76,
about $75 a bet.** The worst one close can cost falls from 33% of the bank to
25%; the earning rate falls by about a quarter. He was shown both halves.

It is now a FLAG rather than an edit, so the risk setting can be moved and
reverted without touching the source. `bank_brake` and the derived
`bank_divisor` are both in the start record -- a log showing the size but not
the brake cannot say whether a small size meant caution or a small bank.

## 2. AMENDMENT 50: the 31-45 s leg refuses a WIDE edge

**Operator, on the 45-second leg: "It's earning good it'd be a shame to shut it
off, but also a shame to lose money... It might mean smaller gains but that's
better than none."**

This is a REFUSAL, not a new way to buy, so its worst case is fewer trades --
which is why it went live ahead of its paper arm finishing. Measured over every
signal joined to its settlement, split by how far our model sat above the
market on our side:

| when | model above market | bets | lost | $/bet |
|---|---|---|---|---|
| 31-45 s | under 3c | 177 | 3 | +0.06 |
| 31-45 s | 3-6c | 62 | 5 | **-0.57** |
| 31-45 s | 6c or more | 11 | 3 | **-3.01** |
| 30 s or less | 6c or more | 263 | 1 | **+1.44** |

Live fills agree on the late half: 102 fills at 6c+, 4 losses, +3.08 $/bet.
There has never been a live early fill at 6c+.

**Rule 5 limit, stated:** the 31-45 s rows are dominated by PAPER arms, which
book a fill the moment they see an offer. The LEVELS are not evidence; the
SHAPE is, and the shape is what this acts on. A paper arm at FULL early size
with the same 3c cap is running as the confirmation
(`results/PREREG_a50_early_edge_cap.md`, bars written before any result).

**Why the sign flips:** settlement is the mean of 60 one-second prints. At 15 s
left, 45 are already recorded and a cheap market price is simply wrong -- that
disagreement IS the edge. At 45 s only 15 are, and our confidence rests on a
volatility estimate, so a market disagreeing by six cents is usually right.
**Inside 30 s nothing changes.** `--early-max-edge` refuses to start without
`--early-tau` above 30, and the self-test asserts the check sits inside the
early-leg block. Refusals log as `early_wide` and are named in `pinattrib`.

## Revert

Both are FLAGS, so neither revert needs a code change. Edit
`restart_bot.ps1`, then run `.\restart_bot.ps1`:

- **Size only:** change `"--bank-brake", "4.08"` to `"--bank-brake", "3.0"`.
- **45-second cap only:** delete the `"--early-max-edge", "3.0",` line.
- **Both:** delete both lines.

---

# v-early49 -- 2026-09-18 ~02:3xZ -- LIVE: the 31-45 s leg reopens at a THIRD, with a 90c price floor

**Operator: "Can you re open 45 seconds with a cap at 90c, or whatever number
you like?"** `restart_bot.ps1` passes
`--early-tau 45 --early-frac 0.333 --early-min-price 0.90`.

**Why it is back at all.** `results/RESULTS_pickoff.md`: the cheap offers are
taken a median of **41 seconds** before the close while our window starts at
**30**. The 31-45 s band is where the trades we are missing actually live, so
closing it gives up the only lever aimed at the real problem.

**Why a THIRD, not a full bet.** Full-size life: 31 markets, 29 settled, **29
won, +$35.81** -- then one fill took **$27.87** back.
`KXBTC15M-26SEP172115-15`: ask seen **97.8c**, **FILLED AT 53.0c**, 99
contracts, because the book collapsed inside our 160 ms round trip. **A limit
price is a MAXIMUM, so no price rule can prevent that fill -- only size bounds
it.** At a third the same event costs about $9.

**AMENDMENT 49, the 90c floor.** An early leg now also needs the ask at or
above `EARLY_MIN_PRICE` (0.90). Out at 31-45 s only a quarter of the
settlement average is locked, so `fair` leans much harder on the sigma
estimate; a cheap ask there is the market disagreeing with us exactly where
the model is weakest. **Inside TAU_MAX the full leg is untouched** -- we still
buy at any price down to the dump guard's 84.5c in the 3-30 s window.
Refusals log as `early_cheap` and are named in `pinattrib`, so the floor's
cost is measurable rather than invisible.

**Shipped defaults unchanged and asserted:** `_DEFAULT_EARLY_TAU_MAX = 30`
(off), `_DEFAULT_EARLY_MIN_PRICE = 0.90`.

**Bar:** `results/PREREG_staged.md` stage 2 still stands -- revert at 3 losses
on early-leg closes in the first 40, or 2 in the first 15. The count restarts,
because the size and the floor both changed.

**REVERT:**

```
git revert --no-edit <this commit>
powershell -File C:\kals-repo
estart_bot.ps1
```

or drop `--early-tau/--early-frac/--early-min-price` from `restart_bot.ps1`.

# v-a8fix -- 2026-09-17 ~21:0xZ -- AMENDMENT 8's both-sides guard finally reads the right variable

**Found by the fresh-eyes review of the whole crypto buy path, and confirmed by
three independent readers plus an adversarial verifier.**

**The bug.** The both-sides test sat at `pinrun.py:~5883` and compared
`prev["sides"][tk] != want`. But `want` is not assigned until ~140 lines below,
inside the same scan loop. So it compared the side we hold in THIS market
against the side we happened to want in the PREVIOUS market of the scan -- or
`None` on the first pass.

**What that did.** It blocked roughly **94% of re-looks at a market we already
hold**, including legitimate SAME-side top-ups, and it let a genuine
opposite-side buy through whenever the previous market in the scan happened to
want the same side. Both directions wrong, neither detectable by reading the
gate's name in a log.

**The fix.** The comparison moved to immediately after `want` is assigned --
the first line in the loop where it is meaningful -- and is now a named
function, `_both_sides_block(prev, ticker, want)`, so it can be tested
directly. Only an OPPOSITE side blocks; a same-side re-look is a top-up and
passes.

**What the bot now does differently.** Top-ups on a market we already hold are
no longer blocked at random. Every other gate -- ceiling, edge, EV, dump guard,
rebuy band, per-market cap -- still applies to them unchanged, so this does not
create a new trade type, it stops suppressing an existing one.

**Money.** Small and honestly bounded: the verifier put it at **$5-$40 over the
four days the guard has been reachable**, of which only about $5 is grounded in
live fills (8 of 174 filled markets since 09-14 had an unfinished position, 174
contracts short, worth $4.80 at the measured 2.76c a contract). The original
review claimed $242; that did not survive checking.

**Risk.** This LOOSENS a gate, so it can only increase trading. The protection
it was supposed to provide is now actually present for the first time -- before
the fix, a real opposite-side buy could slip through. So it is safer in the
direction that matters and looser in the direction that costs money.

**Self-tests:** opposite side blocks, same side passes, a different market is
unaffected, all the null paths return False, and the loop is asserted to call
it AFTER `want` exists.

**Deploys on the next restart of `pinrun.py --live`** -- there is no flag; it
is a plain bug fix in the file the watchdog launches.

**REVERT:**

```
git revert --no-edit <this commit>
powershell -File C:\kals-repo
estart_bot.ps1
```

# v-early-full -- 2026-09-17 ~19:5xZ -- LIVE: the 31-45 s leg becomes a FULL bet

**Operator: "Bump 45 seconds up to normal price as well."** `restart_bot.ps1`
now passes `--early-tau 45 --early-frac 1.0` (was `0.333`, and `0.5` before
that on the same day).

**What the bot does differently.** A market that passes every gate with 31-45
seconds left is now bought at **full size**, not a third. The top-up leg
becomes a no-op by construction: `staged_take` returns `size - early_held`,
which is zero once the position is already full. **One early leg per market is
still enforced** by the `early_once` refusal, so this cannot double up, and
`MAX_PER_MARKET` is untouched. In effect `TAU_MAX` is 45 for the first bet.

**What supports it.**

- The flat tau-45 paper arm is the same configuration and has **33 settled
  closes, 0 losses, +$10.17**, with 22 NEW markets (ones that exist only
  because of 31-45 s) and **0 lost**. It takes +230% more closes than its
  control.
- On the tape BY MARKETS (rule 4), buyers of 95-98c lost **2.8% at 31-45 s
  (606 markets)** against **3.9% at 16-30 s (389 markets)**; at 98-99c it is
  0.9% (751) against 1.4% (483). **The earlier window is not the worse one on
  the market's own record.** Break-even is ~3.4% at 96.5c.
- Model error at 31-45 s is 0.058% of moments against 0.021% at 21-30 s
  (`pinbefore`, 14,261 closes, index only). Both are ~1/200th of our 4.66%
  live loss rate, so **the risk here is adverse selection, not arithmetic.**
- Live so far on the staged third: 3 early legs, 3 won.

**What it gives up, stated because it is real.** At a third we took a foot in
the door early and completed at 30 s when more of the settlement average was
locked. At full size we commit at the earlier, worse-information moment and
cannot improve the price afterwards. The compensating fact is that the tape
says 31-45 s is not a worse window; the uncompensated risk is that the tape
cannot see adverse selection, which is precisely what killed every optimistic
tape number this project has produced (rule 5, 31x).

**THE BAR IS UNCHANGED AND STILL BINDING** -- `results/PREREG_staged.md`
stage 2, scored over the first 40 live closes carrying an early leg:
**revert at 3 losses in 40, or 2 in the first 15.** Three closes are in.

**REVERT:**

```
git checkout HEAD~1 -- restart_bot.ps1
powershell -File C:\kals-repo
estart_bot.ps1
```

or edit `--early-frac 1.0` back to `0.333` and restart. Setting it to `0`
disables the early leg entirely and returns the bot to TAU_MAX 30.

# v-cmdpenny -- 2026-09-17 16:14Z -- LIVE: the COMMODITY PENNY TEST, gold and oil, ONE contract

**Operator, 2026-09-17: "I'm ready for commodity penny testing"**, and then
*"Make the good commodities live, also run paper tests on the ones you don't
have confidence in, but do your best to create the best strategy you possibly
can for them."*

**This is a SECOND live process, not a change to the crypto bot.** `pinrun.py
--live` is untouched: same flags, same size, same gates. Nothing about
v-staged or any earlier version changed.

    C:\Python314\python.exe -u research\cmdlive.py --live
        --signoff "commodity penny test" --minutes 1440

**What it does.** Watches KXGOLD15M and KXWTI15M. When the book offers the
priced-in side inside one of that series' windows, it buys **one contract**.
First live fill, 16:14:5xZ: `KXWTI15M-26SEP171215-15` YES @ 90c, 1 contract,
41 s left, $0.90 committed.

**The windows** (`cmdarm.BANDS`, imported by reference so the paper control
cannot drift from the live test), from the grid's BY-MARKETS table:

| window | when | price | tape, by markets |
|---|---|---|---|
| gold-near | 2-15 s, **skips 08-14 ET** | 95-99c | 149 / 2 lost; inside COMEX hours 32 / 2, outside 117 / 0 |
| gold-far | 91-180 s | 95-99c | 379 / 2 lost (0.5%) |
| wti-near | 2-60 s | 95-99c | 254 / 3 |
| wti-mid | 16-45 s | 90-95c | 104 / 6 (5.8% against a 7.5% break-even) |
| wti-far | 121-180 s | 90-99c | 308 / 6; its 90-95c corner is the best commodity cell found, 105 / 3, +4.16c |

The shape behind them: commodities are good at BOTH ENDS of the quarter hour
and dangerous between 16 and 90 seconds -- the opposite of crypto, because
they settle on the CLOSE of a 1-minute candle rather than a 60-second average.

**Silver, copper and natural gas are PAPER ONLY** (`cmdarm.py`, all five
series), each on the best window its series has: silver 121-180 s at 95-99c
(187 / 2 -- silver's near window was the mistake, not the series), copper
46-90 s at 98-99c (227 / 2, and the middle is where every other series is
worst), natural gas 91-120 s at 95-98c (96 / 3, +0.14c, the weakest window in
the file). `cmdarm` also runs `anti-silver-mid`, a window the grid says LOSES
5-12%, as a negative control. `cmdlive.LIVE_SERIES` and an "anti" label check
mean none of those can reach the wire even if passed on the command line.

**What it can cost.** One contract per order; **$10.00 total across the run**,
counted from fills; 60 orders; **2 losses and it writes its own stop file**; a
$300 account floor so the crypto bot's capital is untouchable; 90-99c only;
never inside 2 s. Realistic worst case is the 2-loss brake at about $2.
Balance at launch $579.44.

**Evidence, and its limit.** All tape (rule 5). The tape says an offer was
taken at that price, not that WE could take it; on crypto those populations
differed 31x in loss rate. Measuring that gap IS this test.
`results/PREREG_commodity_live.md` fixes the bar BEFORE the first fill: kill
at 3 losses in 30 fills, or if silver's paper control beats gold and oil;
proceed only at <= 1 loss in 30 fills with at least 20 fills; **no size
increase without a fresh sign-off.**

**Deliberately NOT in `boot_all.ps1`.** A process that spends money should not
come back from a reboot without a human deciding.

**REVERT -- either alone is enough:**

```
type nul > C:\kals-repo
esults\cmdlive.stop
powershell -Command "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | ? { $_.CommandLine -like '*cmdlive.py*' } | % { Stop-Process -Id $_.ProcessId -Force }"
```

Deleting `results/cmdlive.stop` is what allows a restart. The crypto bot is
unaffected by either command.

# v-staged -- 2026-09-17 ~15:1xZ -- LIVE: a THIRD of a bet at 31-45 s, topped up at 30

**Operator, 2026-09-17: "As long as you have the 45 second is built as safely
as you described, deploy now."** And, on the same message: *"Unless you can
give me a reason to feel okay about the way less opportunity we're getting
push the 45 second."*

`restart_bot.ps1` now passes `--early-tau 45 --early-frac 0.333`, and
`EARLY_LIVE_OK` is True in `research/pinrun.py`. The fraction is his:
*"Bump it down to 1/3 the current size instead of half."* At SIZE 94 the early
leg is ~31 contracts, ~$30 at 97c.

**What the bot does differently.** With 31-45 seconds left, a market that
passes EVERY existing gate (confidence, edge, depth, ceiling, EV, dump guard,
jump gate) may be bought for **one third of a bet**. With 30 seconds or less it is
**topped up to a full bet** only if the same gate still passes at that
moment's price. One early leg per market. If belief has collapsed by the
top-up point, the top-up fails the confidence gate and the hedge pass -- which
covers every open position every second -- buys the other side at belief
< 0.60. **`TAU_MAX` is still 30: a FULL bet can never be bought early.**

**THIS IS A BAR OVERRIDE AND IT IS RECORDED AS ONE.** `results/PREREG_staged.md`
stage 1 asked for 30 paper closes and 20 early markets before reading
anything; the staged arm had run ~20 minutes. The operator deployed on the
evidence that existed:

- the flat tau-45 paper arm, 9.2 h: **27 bets, 27 won, 0 lost**, 3x the
  control's bet count, +0.03c on the 8 markets both arms bought;
- `pinbefore` on the index alone (14,261 closes): model error at 31-45 s is
  **0.058%** against 0.021% at 21-30 s, both trivial next to a 4.66% live
  loss rate;
- exposure per early leg is ONE THIRD of today's per-market worst case.

**The STAGE 2 live bar in PREREG_staged.md is unchanged and now governs:**
40 live closes carrying an early leg; **revert at 3 losses, or 2 in the first
15**; top-up price within 1.0c of the early price; net positive.

**Revert, copy-pasteable:**

```powershell
cd C:\kals-repo
git checkout 83fd965 -- restart_bot.ps1
powershell -ExecutionPolicy Bypass -File C:\kals-repo\restart_bot.ps1
```

(The code can stay; without the flag it buys no early leg. To disable it
everywhere, set `EARLY_LIVE_OK = False` in `research/pinrun.py`.)

---

# (superseded by v-staged above) AMENDMENT 46 -- built, paper only -- 2026-09-17 14:3xZ

**Live flags unchanged, `versioncheck` clean, full self-test exit 0.** The
file on disk changed again, and the live bot restarts from it. Operator:
*"implement tau 45 in a safe way. Maybe not buying full coins and topping up
what's available once we hit the normal purchase point?"*

`--early-tau 45 --early-frac 0.5` (refused live until `EARLY_LIVE_OK` is
flipped in a commit citing `results/PREREG_staged.md`): with 31-45 s left a
market that passes every gate may be bought for half a bet; with <= 30 s left
it is topped up to a full bet if the gate still passes; if belief collapsed
first the hedge pass covers the half. `staged_take()`; records carry `leg`.
Also fixes AMENDMENT 45 so the paper path widens too (the first version
widened only live orders).

Revert (code only; live bot unaffected until its next restart):

```powershell
cd C:\kals-repo
git checkout bc05d04 -- research/pinrun.py research/pinattrib.py
```

---

# (NOT DEPLOYED) AMENDMENT 45 -- one-coin depth. FLAG IS OFF LIVE. -- 2026-09-17 13:2xZ

**The live bot's flags did not change and `versioncheck` is clean.** But
`research/pinrun.py` on disk did change, and the live bot restarts from that
file, so this is recorded here. The full self-test passed (exit 0) before the
file was left in place; the paper arm started from it at ~13:25Z.

`--one-coin-depth --one-coin-max 2.0` (refused with `--live`) lets ONE market
take more than SIZE from a deep offer at the same limit, capped by the lowest
of: the multiple x SIZE, the close budget, and the drawdown brake's headroom
`(bank - 0.8 x high-water) / 0.98` -- so a single widened position can never
halt the bot. `one_coin_cap()`; bar in `results/PREREG_onecoin.md`; evidence
in `results/RESULTS_quiet.md`. Operator, 2026-09-17: "Build the one coin
depth" and "The brakes are a whichever comes first, which I'm fine with."

Revert (removes the code; the live bot is unaffected until its next restart):

```powershell
cd C:\kals-repo
git checkout eade429 -- research/pinrun.py
```

---

# v-selfheal -- 2026-09-17 04:22Z -- the bot relaunches itself until it works, and the operator gets buttons

**Operator instruction, 2026-09-17: "Does the bot automatically catch itself
being down and relaunch until it works? If not it should. Tonight has
maintenance 3-5am it should auto fire back up when it's done without you or I
needing to do anything. Also ... a program on my desktop and I can click start
pause and stop."**

**The bot's own flags did NOT change** (`versioncheck` clean). What changed is
everything around it:

- `watch_bot.ps1` (rewritten, swapped in at 04:22Z, pid 507780): checks every
  30 s; 4 quick restarts per 15 min, then one every 3 min FOREVER (it used to
  stop for good after 4 in an hour -- during a 2-hour exchange outage that gave
  up in the first 10 minutes). A bot alive but silent 25 min is restarted as
  hung. A money-brake halt (loss COUNT / loss abort / DRAWDOWN) waits 15 min
  before the first relaunch. A stand-down flag `results\pinrun-live.stop`
  stops all relaunching until removed.
- `restart_bot.ps1`: the "is it holding a bet" check is now
  `research\pinflat.py`. The old count (filled orders > settled records)
  DEADLOCKED when the bot died holding a bet: the settled record never came,
  so the restart refused forever, every minute. pinflat reads each open
  fill's close time from its ticker: dead + market closed = flat.
- `boot_all.ps1` + scheduled task **KalsBoot** (at logon +1 min, and every 10
  min all day): starts whatever is missing -- run_all.ps1 (collectors),
  watch_bot.ps1, cdc_record, the paper arms -- and refuses to start collectors
  if any python process hides its command line (the 2026-09-14 lesson).
  Nothing starts the LIVE bot except watch_bot -> restart_bot.
- `research\pindesk.py`, desktop shortcut **Pin Bot**: START / PAUSE / STOP,
  status, health, money, trades, days, losses, logs. PAUSE waits for open bets
  to settle before stopping; STOP asks first if a bet is open. Both set the
  stand-down flag so the watchdog does not undo them.

**Amended 05:1xZ the same night -- THE TICKER'S CLOCK IS EASTERN.**
`KXXRP15M-26SEP170000-00` settled at 04:00:20Z: "26SEP17 0000" is midnight
ET. The first `pinflat.close_epoch` read it as UTC and put every close FOUR
HOURS EARLY, so its "dead bot + market already closed = flat" rule would have
called a market closed while it still had up to four hours to run. Caught
because the app's day totals did not match the operator's ($63.75 vs his
$85.11 for Sep 16; correct now, $85.10). Fixed in `pinflat.close_epoch` with
`downtime.et_offset`, self-test pins 26SEP161000 -> 14:00Z and a January
ticker -> +5 h. `pindesk` gained the operator's second round the same night:
% returns, sortable columns, an interactive chart, a "What's this?" mode,
per-row stories, a Market tab, hedge verdicts and a System tab.

**What it cannot do:** bring the machine back from a reboot while nobody is
signed in. This account has no auto sign-in and is not an administrator, so a
boot-time task was refused (S4U: access denied). Windows Update's active hours
are 3 PM-9 AM, so no update reboot can land in the 3-5 AM window.

**Evidence:** `pinflat --selftest` (16 checks), `pindesk --selftest` (30
checks), watch_bot `-Once` dry run, boot_all dry run ("all up; nothing to
do"), KalsBoot fired through the scheduler with result 0. No live restart was
performed; the bot (pid 327184) ran through the whole change.

**Revert, copy-pasteable** (puts back the old watchdog policy; the deadlock fix
and the app are harmless to leave):

```powershell
cd C:\kals-repo
git checkout 879f5b4 -- watch_bot.ps1 restart_bot.ps1
Stop-Process -Id (Get-Content results\watch_bot.pid) -Force
Unregister-ScheduledTask -TaskName KalsBoot -Confirm:$false
Start-Process powershell -ArgumentList '-ExecutionPolicy Bypass -File C:\kals-repo\watch_bot.ps1' -WindowStyle Hidden
```

---

# v-hedge60 -- 2026-09-16 ~14:10Z -- hedge trigger 0.80 -> 0.60

**Operator instruction, 2026-09-16: "Change the hedge trigger immediately".**

`restart_bot.ps1` now passes `--hedge-belief 0.60`.

**What the bot does differently.** The hedge buys the opposite side of a held
position when the model's belief in that position falls below the trigger. At
0.80 it fired on shallow dips that then recovered; at 0.60 it waits for a real
collapse.

**Evidence, all 9 hedge events on file (entry leg and hedge leg rebuilt from the
fills, not from the log's pnl field):**

| when ET | belief | entry | hedge | net |
|---|---|---|---|---|
| 09-12 BTC | 0.89 | +1.87 | -2.97 | -1.09 |
| 09-12 ETH | 0.69 | +0.37 | -5.53 | -5.16 |
| 09-12 ZEC | 0.53 | -10.61 | **+1.98** | -8.63 |
| 09-13 BNB | 0.64 | +2.31 | -3.40 | -1.09 |
| 09-14 BTC | 0.21 | -58.43 | **+24.18** | -34.26 |
| 09-14 HYPE | 0.56 | -59.20 | **+29.30** | -29.90 |
| 09-16 NEAR | 0.77 | +6.78 | -15.99 | -9.21 |
| 09-16 DOGE | 0.49 | +1.68 | -13.83 | -12.15 |

Hedge alone at 0.80: **+$13.78**. Every hedge that SAVED money fired at 0.56 or
below; four of the five that COST money fired at 0.64-0.89. At a 0.60 trigger the
same nine events give **+$41.68**, about $28 better, and BOTH disasters (0.21,
0.56) are still caught.

**The honest caveat:** 9 events, and 0.60 was chosen after seeing them. The
mechanism is the argument: a shallow dip is usually noise, a collapse usually a
real move. 2026-09-14's lesson was that a five-event recommendation got reversed
by its sixth, so this is a live change made on the operator's explicit call, not
a proven threshold.

**Revert, copy-pasteable:**

```powershell
cd C:\kals-repo
(Get-Content restart_bot.ps1) -replace '"--hedge-belief", "0.60"', '"--hedge-belief", "0.80"' | Set-Content restart_bot.ps1
powershell -ExecutionPolicy Bypass -File C:\kals-repo
estart_bot.ps1
```
(or delete the `--hedge-belief` line entirely to return to the 0.80 default)

git SHA at deploy: 50329e2

---

# Live strategy versions — what is running, and how to go back

**Every change to what trades real money is listed here with its git SHA, the
evidence, and the exact command to revert.** Newest first.

---

## HOW TO USE THIS FILE — read before adding a version

**Every change to what trades real money gets an entry here, at the moment it
is deployed, not afterwards.** The log lapsed between 2026-09-11 and
2026-09-13 while eight live changes went out; the back-fill below was written
from git on 2026-09-13 and is thinner than it should be, which is exactly the
cost of letting it lapse.

An entry needs five things and nothing else:

1. **A version tag** `v-<short name>`, and the same tag in the deploy command.
2. **The UTC time it went live** and the **git SHA** it was deployed from.
3. **What changed, in one sentence**, in terms of what the bot now does
   differently.
4. **The evidence**, or the honest absence of it, with the pre-registration
   filename if there is one.
5. **THE EXACT REVERT COMMAND.** Not a description of how to revert. The
   command, copy-pasteable.

`research/versioncheck.py` fails if `restart_bot.ps1` carries a flag that no
entry mentions, so a live change without an entry is caught rather than
remembered. Run it in any session that touches the live bot.

---

## (NOT DEPLOYED) AMENDMENT 41 — after a jump, sigma is doubled at entry AND in the hedge. FLAG IS OFF.

Shipped in code 2026-09-15 02:xxZ, **default OFF**, `--jump-widen` turns it on.
Two paper arms carry it from 02:0xZ: **WIDEN** (today's live minus the jump
gate, plus widening) and **BOTH** (today's live plus widening). Recorded so a
future `--jump-widen` in `restart_bot.ps1` has an entry to match.

**What it would change.** For 5 seconds after any one-second index move of
3 sd or more, in either direction, the model's sigma is multiplied by **2.0**
at both places a position is priced — the entry decision and the hedge's
belief. Every signal records whether it was priced widened.

**What it does that the jump gate cannot.** A40 refuses an ENTRY into a jump.
A41 also lowers the belief in a position we ALREADY HOLD when the index jumps
under it, so the hedge fires sooner. Hedging one tier sooner was measured at
~17c per rescued contract on the tape's 25 losing markets.

**The number that put it in.** Same measurement as A40 — 17,811 jumps, index
alone: the 5-second continuation after a >3 sd second has p90 +4.2 sd (calm
+2.1), p95 +6.7 (+3.2), p99 +15.4 (+7.0). The tail is about twice as wide, so
the multiplier is 2.0 and the window is the 5 s the continuation was measured
over. Neither was tuned on our fills.

**Self-tested mechanism.** On the BTC 05:30 shape — 47 prints below the
strike, then the +18.5 second, 13 s left — doubling sigma moves confidence in
NO from **0.9986 to 0.9327**: from passing the 99.5% gate to nowhere near it.
Also: the factor is exactly 1.0 with the flag off, on a missing sigma or
market, on a jump seven seconds old, and on sub-sd wobbles; both `fair()`
call sites carry it (a held position must be priced by the same model that
bought it); the signal records `widened`.

**Why this is not the dead "scale sigma by k".** That multiplied EVERY
decision and shrank the population without touching the loss rate, because
the error is shape, not width. This multiplies only in the one state where
the shape is measurably wrong. It is symmetric on purpose — a jump in our
favour also widens, which costs a few good entries; a directional drift term
is the refinement, not this version.

**Not deployed. The three-day comparison decides it** (see v-jump).

**TO DEPLOY:** add `"--jump-widen"` after `"--jump-gate"` in
`restart_bot.ps1` and run the restart script. **REVERT:** remove it; the
default is OFF.

---

## v-withdraw — 2026-09-15 04:xxZ — THE BOT TELLS A WITHDRAWAL FROM A LOSS

**Operator-directed.** His words: *"can you code it so it dynamically checks
its own price and knows if it's a withdrawal or a loss? ... once it hits cap
I'll take anything above that every day."*

**The problem it fixes.** The drawdown brake compares the balance to its
all-time high. A withdrawal was **indistinguishable from a catastrophic
loss**: taking $500 out of a $1,500 bank read as *"33% below the high -- STOP
AND LOOK"* and halted the bot. With a daily-withdrawal policy that is a halt
every single day.

**How it knows, without any price feed.** The bot already keeps a running
total of its own settled P&L. Between two balance reads:

```
expected change = realised P&L booked in that interval
actual change   = bank now - bank then
unexplained     = actual - expected
```

A trading loss is *fully explained* -- it IS the realised P&L. Money that moves
with no settlement to account for it came from outside. Negative is a
withdrawal, positive a deposit, and the high-water mark is shifted by that
amount so the brake keeps measuring **trading** and ignores the operator's cash.

**Two guards, both self-tested, both of which would have caused real damage:**

1. **Only when flat.** `autosize_tick` returns early while any position is
   open, so collateral is never mistaken for a withdrawal.
2. **The first tick of a run never classifies.** A restart zeroes the realised
   counter while the bank carries over -- without this, *every restart would
   look like a withdrawal of the entire previous run's profit* and shift the
   high-water mark down by it.

**The floor is $1.00.** Below that it is settlement timing and fees, and stays
classified as trading.

**Worked cases from the self-test:** lose $100 -> trading. Withdraw $500 with
no loss -> withdrawal $500. Lose $100 *and* withdraw $400 -> withdrawal $400,
with the $100 still charged to trading. **Win $200 and withdraw exactly $200
so the bank is flat -> withdrawal $200**, which is the operator's stated daily
policy and would otherwise read as a mysterious nothing.

**ON by default** -- the previous behaviour was a known false alarm, not a
safety feature. `--no-external-detect` restores it.

**REVERT:** add `"--no-external-detect"` to `restart_bot.ps1` and restart, or
`git revert` this commit.

---

## v-jump — 2026-09-15 02:xxZ — DO NOT BUY INTO A JUMP THAT JUST WENT AGAINST US (`6f05769`)

**Operator decision, 2026-09-14 ~21:45 ET.** His words: *"If it earns more
money, do it! But perhaps also have a paper trade version going for each and
both that check if these implementations weren't in (the version running
today) would we earn more. That's the realest check if it's good. We'll
compare all in 3 days and see who has made and lost the most."*

**What the bot now does differently.** `--jump-gate` is on: it refuses a
trade when the settlement index made a one-second move of 3 sd or more
against our side in any of the last 3 seconds.

**The three-day comparison, all auto-sized from the same bank:**

| arm | jump gate | post-jump widening | what it answers |
|---|---|---|---|
| **LIVE** | on | off | — |
| paper CONTROL | off | off | "would today's version have earned more without the gate" |
| paper WIDEN | off | on | the model version alone |
| paper BOTH | on | on | the two together |

Compare on 2026-09-17: net per contract and losses, per arm. The evidence
below is what put it live; the arms are what will keep it live or not.

**REVERT:** drop `"--jump-gate"` from `restart_bot.ps1` and run the restart
script; the default is OFF.

### The entry as it stood before deployment, unedited:

#### (was) AMENDMENT 40 — do not buy into a jump that just went against us. FLAG IS OFF.

Shipped in code 2026-09-15 01:xxZ, **default OFF**, `--jump-gate` turns it on.
A paper arm identical to live plus the flag is running from 01:28Z (pid
1646604). Recorded here so a future `--jump-gate` in `restart_bot.ps1` has an
entry to match.

**What it would change.** Refuse a trade when the settlement index made a
**one-second move of 3 sd or more against our side in any of the last 3
seconds**. Runs after AMENDMENT 38 and before the dump guard; every refusal
records the moves and sigma it saw.

**The mechanism — the first entry-side rule today with one.** Index alone,
17,811 jumps over 1,785 closes: after a >3 sd second, the NEXT five seconds
continue the same way with a tail the model does not have. Share followed by
a further >=5 sd inside 5 s: **7.9%**, vs 2.2% after a calm second and
**1.3% under the Gaussian the model assumes**. p99 of the 5-s continuation:
+15.4 sd vs +7.0 after calm. The median is ~0 — most jumps stop — but the
ones that run are the ones that settle against us.

**The live evidence.** BTC 2026-09-14 05:30 ET, second by second: the index
moved +18.5 (4.5 sd) at :46; we bought NO at :47 with spot +12 over the
strike; the model priced it as survivable, and it was, had it stopped; it ran
+22, +18, +18 more. -$58.43. Across all 359 live fills, a >=3 sd move against
us in the prior 3 s:

| move against us in last 3 s | fills | contracts | net | c/contract | losers |
|---|---|---|---|---|---|
| under +1 sd | 323 | 8,460 | +$223.78 | +2.65c | 8 (2.5%) |
| +1 to +2 sd | 26 | 742 | +$15.26 | +2.06c | 2 (7.7%) |
| +2 to +3 sd | 3 | 60 | +$5.10 | +8.50c | 0 |
| **over +3 sd** | **7** | **180** | **-$65.67** | **-36.48c** | **2 (28.6%)** |

Gate at 3 sd: blocks 7 fills over 7 closes — **5 winners worth $4.92 total,
2 losers worth $70.59**. 2.5 winners given up per loss avoided (every
previously tested entry gate cost 22–44). 2% of contracts. **Both holdout
halves positive**: first 60% +$8.94 net of blocking, last 40% +$56.73.
Bootstrap over the 7 blocked closes: mean -$9.38, 95% [-26.36, +1.11] — the
interval touches zero on 7 closes, and that is the honest limit.

**Why this is different from the four entry rules killed earlier today.**
Those had no mechanism and reversed out of sample. This one's mechanism is
measured on 17,811 independent events; the threshold (3 sd) and lookback (3 s)
were fixed in that measurement BEFORE the fill test was run, so it is not a
search; and it holds on both halves. It catches 2 of 12 live losses — but 27%
of the loss dollars — and does nothing about the no-warning kind (HYPE 16:00,
+0.3 sd, correctly passes).

**Not deployed because it changes what trades and no one has said yes.**

**TO DEPLOY:** add `"--jump-gate"` after `"--depth-ladder"` in
`restart_bot.ps1` and run the restart script. **REVERT:** remove it; the
default is OFF.

**The principled follow-up, not built:** widen the model's sigma for a few
seconds AFTER a jump, by the measured tail ratio. That would refuse the same
entries by lowering confidence, AND fire the hedge sooner on positions held
through a jump. `CURRENT_STATE`'s dead "scale sigma by k" was global; this is
conditional on the one state where the model is measurably wrong.

---

## v-nofloor — 2026-09-14 14:5xZ — NO PERCENTAGE FLOOR AT ALL, AND THE GATE READS THE LADDER

**Operator-directed and urgent.** His words, verbatim: *"I've said it a million
times and I'm tired of saying it. I need it implemented immediately if it's
not. It's number one priority. ... we buy every contract possible starting for
the best price then the next all the way til we max our size. And if we can't
max we do as much as we can. No limit on total coins only total contracts. No
thinking 'is it worth it there's no point in that it's wasted time.' That's how
it needs to function right now. No 10%."*

**What the bot now does differently. Two flags, and the FIRST is the one that
does the work.**

1. **`--min-fill-frac 0`** — the percentage floor is **gone**. `MIN_LEVEL`,
   one contract, is the only floor left at any SIZE.
2. **`--depth-ladder`** (AMENDMENT 37) — the floor, whatever is left of it,
   counts what the LADDER can fill rather than what sits at the best price.

**AND THE SECOND IS NEARLY REDUNDANT ONCE THE FIRST IS ON.** A37 only consults
the ladder when the touch fails the floor, and at a one-contract floor almost
nothing fails it. It is deployed anyway because it is the safety net if the
floor is ever raised again, and because it still catches the genuine dust case
— an ask of 0.02 contracts, which the live log does contain.

**WHY THE FLOOR HAD TO GO, and it is not only the operator's preference.** The
floor was `0.10 x SIZE`, so **it grows with the bank**: 6 contracts at SIZE 58,
**25 at SIZE 250**. It would have refused more and more of the book exactly as
we scaled into it. Five of the eight successful ladder walks on 2026-09-14 had
**fewer than 25** contracts at the best price and would have been refused
outright at SIZE 250.

**Its original justification had already expired.** `MIN_FILL_FRAC`'s own
comment gives two harms — a scrap fill "burns a scale-in slot" and "raises the
improve bar" — and AMENDMENT 17 and AMENDMENT 29 removed both. A29 in
particular lets a partial position be topped up at **any** passing price with
no improvement required, so a 6-contract fill can no longer block a
52-contract top-up. The floor has been a leftover from a replaced world since
2026-09-14 02:0xZ.

**Exposure does not change.** The worst close is still
`MAX_PER_CLOSE x SIZE x 0.98`. A smaller fill is the same bet at the same gate
on fewer contracts; `min(SIZE, offered)` can only LOWER exposure. What changes
is how often the budget actually gets spent.

**The measured counter-argument, and why it is stale.**
`results/RESULTS_levels.md` measured removing the floor as costing 30% of the
money (+15% fills, −35% mean size, −25% contracts). **That was measured before
the order walked the ladder.** In that world a thin touch really did mean a
thin fill; it no longer does. The measurement needs redoing and should not be
quoted against this change as though it still applied.

**Latency: no change.** The extra work A37 does is inside the branch that only
runs when the touch fails the floor, and at a one-contract floor that branch
is almost never entered. The operator's condition — *"if it doesn't cause us to
miss deals because we spend extra time searching all of them"* — is met by
construction.

**Coins are already unlimited.** `CLOSE_BUDGET = True` makes the per-close cap
count **contracts** (`MAX_PER_CLOSE x SIZE`), not coins and not fills. The
fill-count cap survives only behind that flag. Nothing needed changing.

**Self-tested:** at `--min-fill-frac 0` the floor is exactly `MIN_LEVEL` at
SIZE 58 **and** at SIZE 250; zero is never tighter than what it replaces; and
the guard still refuses any value above the 0.50 default, so this flag can only
ever loosen.

**REVERT:** in `restart_bot.ps1` set `"--min-fill-frac", "0.10"` and drop
`"--depth-ladder"`, then run the restart script.

---

## v-against — 2026-09-14 14:2xZ — REFUSE A THIN EDGE WHEN THE PRICE IS ALREADY RUNNING AGAINST US

**Operator-approved.** His words: *"if you mean both on the other side and
under 2c you can block it off. It's only happened 5 times so not worth too much
(it's also 2c not a huge profit) and it caused loss most times."*

**What the bot now does differently.** AMENDMENT 38 refuses a trade when BOTH
hold: the live index sits **1.0 or more one-second moves past the strike on the
side that hurts us**, AND the edge is **under 2c**. Either half alone changes
nothing.

**THE CONJUNCTION IS THE WHOLE RULE.** Both halves were measured separately on
332 live fills and both are bad gates:

| rule | fills blocked | winners given up | losses avoided | winners per loss |
|---|---|---|---|---|
| price against us alone | 15 | 13 (+$27.77) | 2 (−$70.59) | 6.5 |
| edge under 2c alone | 105 (**31% of all trading**) | 102 (+$46.30) | 3 (−$97.33) | 34.0 |
| **both together** | **5** | **4 (+$1.81)** | **1 (−$58.43)** | **4.0** |

Every entry gate previously tested in this project cost **22–44 winning trades
per loss avoided** (`PROJECT_HISTORY`). This one costs 4.

**WHY IT IS DEPLOYED ON FIVE EVENTS, against the usual bar.** The four winners
it refuses are worth **41c, 47c, 56c and 37c — $1.81 between them**, because a
sub-2c edge at 97c is pennies by construction. So the cost of being wrong is
about **$2 a week** and the cost of being right is one **$58** loss. The
argument is the asymmetry, not the significance.

**IT IS NOT EVIDENCE AND MUST NOT BE QUOTED AS ANY.** The loss that motivated
the rule is one of the five, so **+$56.62 describes the past and forecasts
nothing**. `results/PREREG_against.md` holds the bar for judging it forward.

**Note the operator's own correction to my framing**, recorded because he was
right: I called it a mirage on the strength of a bootstrap that straddles zero.
That test asks "is the effect real"; the decision actually facing us is "what
does acting cost if it is not", and the answer is $1.81. Significance was the
wrong tool for the question.

**Self-tested:** all five real fills refused by name and by their own numbers;
the same 05:30 book with a 2.5c edge NOT refused; the same 1.9c edge with spot
on our side NOT refused; a missing strike, spot or sigma never blocks.

**REVERT:** set `AGAINST_ENABLED = False` in `research/pinrun.py` and restart.

---

## v-lossreset — 2026-09-14 14:2xZ — THE LOSS COUNTER RESETS WHEN THE BANK IS WHOLE

**Operator-directed.** His words: *"the loss brakes change automatically
counter should reset when the balance hits the balance where it originally
fell from."*

**What the bot now does differently.** AMENDMENT 39 clears the losing-close
count the moment the bank gets back to the high-water mark it fell from.

**The bug this fixes.** The count only ever went up, and the only thing that
cleared it was a **restart** — so the brake's memory was tied to process
lifetime rather than to money, and restarting the bot laundered two losses
away. It now uses the same definition of "recovered" the drawdown brake uses.

**The one trap, and it is self-tested.** The mark must be read **before**
`write_hwm()` raises it. Reading after would make every tick look like a
recovery and the brake would never hold at all.

**REVERT:** `git revert` this commit, or delete the `_hwm_before` block in
`autosize_tick`.

---

## (SUPERSEDED SAME DAY) the 0.10 hedge trigger proposal — WITHDRAWN

Recorded here because a recommendation was made and reversed inside six hours,
and the reversal is the useful part. On five hedge events the hedge looked like
it had cost −$9.08 and 0.10 looked $9.13 better. The sixth hedge, 05:30 ET on
BTC, **saved $24.18** at a belief of 0.214 — which 0.10 would not have fired
on. Net over six: **0.80 is +$14.26, 0.10 is +$0.05.** The trigger stays at
0.80. Bar for revisiting it is in `results/PREREG_hedge.md`; the floor is 0.30,
never lower.

---

## v-brake2 — 2026-09-14 10:0xZ — THE LOSS BRAKE STOPS AT TWO, NOT THREE (`032c73d`)

**Operator decision, 2026-09-14 ~05:5x ET.** His words: *"Brake should be at
either 1/5 of bank lost, or after 2 losses. Which ever comes first. It should
reset once the bank hits its original size again."*

**What the bot now does differently.** `--max-losses 3` → **`--max-losses 2`**.
The other half of his sentence — 1/5 of bank, resetting at a new high — is
already `MAX_DRAWDOWN = 0.20` against `results/pinrun-hwm.json` and is
unchanged by this entry.

**Evidence: none, and none was asked for.** This is a risk preference, not a
measured threshold, and it is strictly more protective than what it replaces.
Cost is real though: of the ten losing closes in live history, no run has yet
had two losses close enough together for this to bind, so the expected cost is
small but is not zero.

**KNOWN GAP, recorded rather than fixed.** `--max-losses` counts losses **in
the current run**. A restart resets the count to zero, so "two losses" means
two since the bot last started. Every restart therefore hands the brake a
clean slate. The drawdown brake does NOT have this problem — its high-water
mark is on disk and survives restarts.

**Also note `versioncheck.py` did not catch this change.** It tracks flag
PRESENCE for the flags it knows about, and `--max-losses` is not one of them,
so changing 3 to 2 passed clean. Worth widening.

**REVERT:** in `restart_bot.ps1` change `"--max-losses", "2"` back to
`"--max-losses", "3"` and run
`powershell -ExecutionPolicy Bypass -File C:\kals-repo\restart_bot.ps1`.

---

## (not deployed) AMENDMENT 37 — the depth floor reads the ladder. FLAG IS OFF.

Shipped in code on 2026-09-14, **default OFF**, awaiting the operator's word to
turn on. Recorded here so that a future `--depth-ladder` in `restart_bot.ps1`
has an entry to match.

**What it would change.** `pinrun.py`'s depth floor refuses a market when the
contracts at the **best price** are under `MIN_FILL_FRAC x SIZE`. AMENDMENT 35
taught the ORDER to read the whole ladder but never touched this GATE, so a
market showing 3 contracts at the touch with 1,600 one tick behind — the exact
02:00 SOL shape A35 exists for — is still refused outright. A37 judges the
floor on what `book.buyable()` can actually fill up to `sweep_limit()`.

**Why it is not simply "removing the floor".** Every market it lets through
still faces `edge_floor`, the dump guard, `price_ceiling` and `ev_floor`
unchanged — the ladder check runs strictly before them and waves nothing past.
`take_n` is never reassigned, so the order still sizes through A35's own block
and the SIZE cap is untouched: **the worst close does not move.** A thin touch
in front of a thin LADDER still fails, which is the self-tested null.

**It requires `--sweep-depth` and refuses to start without it** — passing the
gate on ladder depth while the order sized from the touch would buy exactly
the scrap fill AMENDMENT 6 added the floor to prevent.

**Evidence so far:** 63 depth-floor refusals in the live gate audit, **7 of
which (11%) passed edge, EV and the ceiling**. A paper arm carrying only this
flag is running from 2026-09-14 10:0xZ.

**TO DEPLOY:** add `"--depth-ladder"` after `"--sweep-depth"` in
`restart_bot.ps1` and restart.
**REVERT:** remove it; the default is OFF. Code: `git revert` the A37 commit.

---

## v-ladder — 2026-09-14 06:1xZ — ASK FOR THE WHOLE LADDER, NOT JUST THE TOUCH (`d0c3d60`)

**Operator-directed, urgent.** His words: *"It better buy as much as it can
that we allow for the trade. That was unacceptable and has happened a lot …
you're losing me quite a bit of money with this bug."*

**What the bot now does differently.** It sizes each order from every price
level up to its own sweep limit, instead of only the contracts resting at the
single best price.

**The bug.** AMENDMENT 18 raised the LIMIT PRICE we send so a lost race takes
the next level instead of nothing — but left the QUANTITY at
`min(SIZE, touch size)`. So the bot declared itself willing to pay 98c and then
asked for only what sat at the top.

**Live evidence, the 02:00 SOL close.** Best ask 96.3c with **six** contracts;
limit sent 98c; order placed for 6; filled 6; profit **$0.21**. SIZE was 53.
Reconstructed from our own orderbook tape (05:46:24Z snapshot + 63,232 deltas)
at the second the order went out:

| price | contracts |
|---|---|
| 95.8c | 10 |
| 95.9c | 48 |
| 96.0c | 204 |
| 96.4c | 202 |
| **≤ 98c total** | **1,636** |

Replaying that exact book through the fix: **it asks for 53, not 6.**

**Why it is safe to deploy without a paper run** — and it was, deliberately,
against the usual rule. Every extra contract is at a price `sweep_limit()` had
ALREADY approved against the same confidence, edge, ceiling and expected-value
tests. Nothing new is bought; the same decision is simply filled. The order is
still capped by SIZE and by what remains of the close's contract budget, so
**the worst case per close is unchanged**.

**Not a regression.** `take_n = min(SIZE, touch size)` dates from AMENDMENT 6
(`47f399b`), long before this week. What IS new is that `--min-fill-frac 0.10`
lets six-contract fills through at all; at the old floor of 26 that close would
have been refused outright and earned nothing. So the tiny fills are new, the
sizing limitation is old, and the fix addresses the old one.

**Also live:** AMENDMENT 36 — every signal now records the eight book levels it
was looking at and their total, so this class of question is answerable from
the log instead of from a screenshot and a tape replay.

**REVERT:** drop `"--sweep-depth"` from `restart_bot.ps1` and restart; the
default is OFF. Code: `git revert --no-edit af42b1b`.

---

## v-brake20 — 2026-09-14 02:3xZ — DRAWDOWN BRAKE AT 1/5, AND THE OPEN CAP COUNTS CONTRACTS (`07b3004`)

**Operator decision.** *"make it 1/5 of bank or 3 losses whichever comes first.
Then drop the contract size to whatever the new calculated amount is and wait."*

**What the bot now does differently.**

1. **Stops when the bank is 20% below its highest-ever level.** The high-water
   mark lives in `results/pinrun-hwm.json`, so a restart cannot clear it. It
   resets itself when the balance makes a new high — which is the operator's
   own *"reset once the full balance has been restored"*, with no extra logic.
2. **Re-sizes the instant a loss settles**, instead of waiting out the rest of
   a five-minute timer while betting the size a larger bank supported.
3. **The dollar stop can tighten**, not only loosen. It used to follow the
   bank up and never come back down.
4. **The open cap counts CONTRACTS** (`max_positions x SIZE`) rather than the
   number of open trades.

**Why 4 was urgent.** `v-spend` removed the limit on the *number* of fills per
close and cut the depth floor to a tenth of SIZE, so one close can now produce
10–18 small fills. A cap of 3 *positions* would have halted the bot three fills
into every close and throttled the exact buying `v-spend` exists to enable.
Exposure is unchanged: three fills of 52 and eighteen of 8.7 are both at the
cap.

**All three brakes now run together**, answering different questions —
`--loss-abort` "too much this run", `--max-losses 3` "is the model broken", and
the new one "how far off our best". Whichever trips first, stops.

**Walked through a losing streak at $310:** size steps 52 → 47 → 41 as the bank
falls, and the brake trips at 20.5% down after **two typical losing closes**,
ahead of the 3-loss brake.

**Chosen failure modes.** A failed balance read or a missing high-water file
reads as **zero** drawdown, never as a trip. A **withdrawal looks identical to
a trading loss** and will stop the bot — the safe direction, and the halt
message says so.

**No new flags.** `MAX_DRAWDOWN = 0.20` is a constant; `--max-positions 3` is
unchanged in the command and now means 3 × SIZE contracts.

**REVERT:** `git revert --no-edit 07b3004`, then restart.

---

## v-spend — 2026-09-14 02:0xZ — SAME-COIN RE-BUY + TOP-UPS + A TENTH-SIZE DEPTH FLOOR (`6ee8409`)

**Operator decision.** His words: *"definitely allow double coin buys if it's
causing this many losses opportunities"* and *"DEFINITELY buy smaller if it
can't reach the max contract that was the entire point of opening multiple
coins so we can mix the way up to the contract threshold."*

**What the bot now does differently.** Three things, all aimed at one finding:

1. **`--max-per-market 2`** — a close may buy the same coin twice.
2. **`--min-fill-frac 0.10`** — the depth floor drops from half of SIZE to a
   tenth, so a thin book is taken instead of skipped. `MIN_LEVEL` (1 contract)
   is still the hard backstop.
3. **AMENDMENT 29, topping up** — if a market is holding LESS than a full
   SIZE, more of it is taken at any price that passes every ordinary gate,
   with no improve-by requirement. Once a full size is held, the A23 band
   (0.5c–1.0c cheaper) applies again.

**THE MEASUREMENT THAT DECIDED IT.** Over 234 live closes we bought on, the
bot spent **6,639 contracts of an allowed 11,488 — 58%**. The **median close
spent exactly 50%**: one fill, never the second. The unspent half needs a
second market to qualify, and only **6.3%** of scan seconds have one. So the
contract cap was never the binding constraint; the inability to reach it was.
Separately, of 404 closes with a tradeable moment, **170 produced no fill**.

**THE WORST CLOSE DOES NOT MOVE.** It is `MAX_PER_CLOSE x SIZE x 0.98` either
way — about a third of the bank at BANK_BRAKE 3.0. What changes is how often
the budget is actually spent, which is the risk that was already accepted and
was not being taken.

**What protects it.** `rebuy_ok()`: below a full size, a top-up needs nothing
beyond the gates every buy passes; at or above one, a second buy must be
0.5–1.0c cheaper. That band is where the measurement put it — **0.70% losses
at 0.5–1c against 26.09% at 5–10c**, over 398 markets, ordering intact in a
60/40 holdout on close time.

**Two refusals were LIFTED, not deleted** — both `--max-per-market` and
`--min-fill-frac` used to raise `SystemExit` on `--live`, and the old text
plus the reason it moved is written next to each in `pinrun.py`.

**Also in this version, and not a trading change:** paper what-ifs now
auto-size from the bank exactly as live does. They did not, so on 2026-09-14
live ran 52 contracts while all four arms ran 20 and none of their dollar
figures could be compared with live's.

**REVERT:**

```powershell
cd C:\kals-repo
# drop "--max-per-market","2","--improve-max","0.010","--min-fill-frac","0.10"
# from the Start-Process line in restart_bot.ps1, then:
powershell -ExecutionPolicy Bypass -File C:\kals-repo\restart_bot.ps1
```

The declared defaults in the source are unchanged (`MAX_PER_MARKET` 1,
`MIN_FILL_FRAC` 0.50), so removing the flags restores the old behaviour
exactly. To revert the code as well: `git revert --no-edit 6ee8409`.

---

## v-a24 — 2026-09-13 22:2xZ — AMENDMENT 24: buy the BEST market of the second, not the first one reached (`6d85371`)

**What the bot now does differently.** When two or more markets clear every
gate in the same scan second, it buys the one with the most edge instead of
whichever the loop happened to reach first. Also deployed in the same restart:
AMENDMENT 25, which makes every gate record why it refused a trade (logging
only — it decides nothing).

**Evidence.** `research/pinpick.py` over 13,984 gate-passing candidate rows on
738 closes. Two or more different markets pass in the same second on **6.3%**
of passes; when they do the first one reached is the best-edge one only
**56.3%** of the time, giving up a mean 2.10c of edge and paying 2.21c more.
Replayed one contract per close: **+2.07c → +2.76c per contract with IDENTICAL
loss counts (10 and 10)**. Holdout on close time, last 40% never fitted:
**+1.63c → +2.43c, six losses either way.** Ranking by confidence instead of
edge reaches only +2.19c, so the gain is price and not a riskier appetite.

**Why it adds no risk and loses no race.** The ordering comes from the edge
measured on the *previous* pass, 50ms earlier at 20Hz. Nothing is computed
twice and no order is deferred. The old order was dict insertion order — the
one gate in this bot that was never an EV comparison. Every gate still has to
pass; only the sequence changed.

**What is NOT deployed:** `--max-per-market` (AMENDMENT 23). It pays, but it
concentrates a close on one coin, and the operator's condition was "if it's
good and does not raise risk". Still in a paper what-if against the bar in
`results/PREREG_pin_live_AMENDMENT_23_24.md`.

**REVERT:**

```powershell
cd C:\kals-repo
git revert --no-edit 6d85371
# then remove "--pick", "best" from the Start-Process line in restart_bot.ps1
.\restart_bot.ps1
```

To revert ONLY the scan order without losing the gate instrumentation, drop
`"--pick", "best"` from `restart_bot.ps1` and run `.\restart_bot.ps1`; the
default is `"first"`, which is the old behaviour exactly.

---

## ~~NOT LIVE — AMENDMENT 23~~ — SUPERSEDED 2026-09-14 by `v-spend` above

**This entry is kept, not edited, so the reversal is visible.** A23 went LIVE
about four hours after this was written, by operator decision, once the 58%
budget-utilisation measurement showed the concentration argument below had the
wrong counterfactual: the alternative to "both fills on one coin" is not "one
fill each on two coins", it is "one fill and the rest unspent", because only
6.3% of scan seconds offer a second coin. Everything below was true when
written and is left exactly as it was.

---

**Listed here because the FLAG now exists in `pinrun.py` and a future session
must not mistake "the flag is there" for "it is running".** `MAX_PER_MARKET`
is still 1 on the live bot.

- **AMENDMENT 23 — the re-buy band.** `rebuy_ok()`: a SAME-market second buy
  must be cheaper by at least `IMPROVE_BY` (0.5c) and at most `IMPROVE_MAX`
  (1.0c, `--improve-max`). Only reachable when `--max-per-market` > 1, which is
  still refused on `--live`.
  Paper run: `--max-per-market 2 --improve-max 0.010`.

**Why it is here and not live, when AMENDMENT 24 went live the same evening.**
The operator's condition was *"if it's good and does not raise risk, implement
it."* A23 is good and it DOES raise one risk: the contract budget caps the
dollars on a close either way, but allowing a second fill on the same coin
makes the close more likely to spend that whole budget on ONE outcome instead
of splitting it across two. Same worst case, reached more often. A24 had no
such cost — identical loss counts in both halves of the sample — so it went.

*(AMENDMENT 24 was in a paper what-if alongside this one from 21:5xZ and was
deployed at 22:2xZ; see the v-a24 entry above.)*

Evidence, bars and the strike conditions:
`results/PREREG_pin_live_AMENDMENT_23_24.md`, written before either run took a
fill. Measurements: `research/pinpick.py` (first-vs-best, and the re-buy band
with a 60/40 holdout on close time) and `research/pinwarn.py` (18,653 closes
rebuilt from the index, uncensored, on whether confidence warns before a flip).

**Revert (removes both flags from anything that could use them):**

```powershell
cd C:\kals-repo
Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
  Where-Object {$_.CommandLine -like '*pinrun*' -and
                ($_.CommandLine -like '*--pick*' -or
                 $_.CommandLine -like '*--max-per-market*')} |
  ForEach-Object { Stop-Process -Id $_.ProcessId }
```

That stops the two paper runs and touches nothing else — the live bot carries
neither flag, and the filter requires one of them.

---

## v-a22 — 2026-09-13 19:3xZ — AMENDMENT 22: a second COIN at the same close is allowed on its own merits

**What changed.** `--improve-scope market`. The improve-by rule no longer
blocks a different coin.

**The operator, watching the live bot take ETH and skip HYPE while the what-if
took HYPE:** *"I would've hoped my bot would grab eth, then when hype looks
like a good buy it'd see that and scoop it up too."*

**What happened at 19:15Z.** The bot filled ETH at 98.0c. HYPE was then offered
at 97.7c with **2.14c of edge — a better trade than the one it took** — and was
refused, because 97.7c is not at least 0.5c below 98.0c.

**Why that is a bug and not a design choice.** AMENDMENT 3 wrote the improve-by
rule for SCALING INTO THE SAME MARKET: *"re-buying at the same level would
double the risk without lowering the average paid."* AMENDMENT 13 then set
`MAX_PER_MARKET = 1`, which forbids re-buying the same market at all. **Since
2026-09-12 the rule has been unable to do the job it was written for.** The
only thing it can still do is block a different coin — which it was never meant
to touch — and AMENDMENT 17, the same day, says a close is capped on CONTRACTS
with *"coins unlimited"*. The rule was silently contradicting it.

**Why this does not add risk, and why it is not the ruler.** The close's
contract budget is unchanged: `MAX_PER_CLOSE * SIZE` either way. Two coins at
47 contracts is the same 94 contracts as one coin at 94 — **identical worst
case**, only which markets get bought changes. And because coins at one close
correlate at rho ~0.8 rather than 1.0, splitting the same budget across two
markets can only reduce the chance that all of it loses together.

That is why this went live directly while the ruler went to a what-if: the
ruler was a statistical bet on a population that is not ours, with a measured
cost in volume. This is a code-reading, its exposure is provably unchanged, and
every trade it adds passes every existing gate.

**Revert:** remove `"--improve-scope","market"` from `restart_bot.ps1`.

---

## v-revert1 — 2026-09-13 18:49Z — AMENDMENTS 20, 20b and 21 REVERTED (operator call)

**What changed.** `--sigma-ruler` and `--pin` removed. Back to the 300-second
ruler and the 0.995 gate. **The sweep (v-a18) stays** — it is separately
evidenced, needs no flag, and is 3 for 3.

**Why.** The operator: *"I have barely seen any trades since I woke up and
cannot see how that's smarter... I'm having a very hard time trusting this new
idea."*

He was right and the measurement backs him, not me:

| | signals per hour |
|---|---|
| today, before the ruler change | **4.21** |
| today, after it | **1.55** |

**A 63% cut in signals.** I had measured that cost in advance — 46.6% of
signals, from re-scoring 619 real ones — and deployed anyway, then tried to
buy the volume back by loosening the gate, which is a second change to fix the
first.

**The asymmetry I should have weighted properly the first time.** The ruler's
COST is measured on our own real signals and is certain. Its BENEFIT is
measured on the index population, and CLAUDE.md rule 5 exists precisely because
that population is not ours — it differs by 31x on the one number we care
about. Certain cost, unproven benefit, no forward evidence after 7 hours. That
is a bad trade whoever proposes it.

**What is NOT concluded.** The ruler may still be right — `RESULTS_ruler.md`,
`RESULTS_calib.md` and `RESULTS_flood.md` all stand, and the model's tails
really are 8x too thin. What is concluded is that it may not be deployed on
index-population evidence alone. It needs a test that costs nothing while it
runs.

**Next step for it, if it is revisited:** score the ruler in SHADOW against
live signals — recompute what it would have said at each real decision and
compare, without touching what trades. That is `pinshadow`'s method applied to
the ruler, and it should have been built before the deploy, not after.

**Revert of the revert:** add back `"--sigma-ruler","maxdown","--pin","0.990"`
in `restart_bot.ps1`.

---

## v-a21 — 2026-09-13 17:0xZ — AMENDMENT 21: the confidence gate 0.995 → 0.990

**What changed.** `--pin 0.990`. The gate the model must clear before a trade
is considered.

**Why it is a partial REVERT, not a new bet.** v-a20b moved this gate without
touching it: a wider ruler lowers every stated confidence, so the same PIN
became a stricter gate overnight. Measured — the new ruler reads a median
**1.167x wider** (2,666 tape samples), and re-scoring **619 real live signals**
through `z -> z/1.167` shows it cost **46.6% of them**. Lowering PIN to 0.990
gives back most of that volume at the same expected money.

**Evidence.** `results/PREREG_ruler.md`, amended before this deploy. Both 0.995
and 0.990 are worth the same expected $/hour; 0.990 keeps 83% of trades against
53%, so it leans a third as hard on the one number rule 5 says cannot be
assumed to transfer — that a loss reduction measured on the index population
applies to fills someone chose to sell US.

**Also recorded:** the index population said tightening 0.995 → 0.998 costs
0.7% of decisions; on real signals it costs 51%. A 70x error. That population
may compare rulers and may NOT count trades.

**`--pin` may only LOWER the gate** — outside [0.95, 0.995] it refuses to
start. Raising it needs a code change and a version entry, not a flag.

**Revert:**

```powershell
# edit restart_bot.ps1: delete the "--pin","0.990" arguments
powershell -NoProfile -ExecutionPolicy Bypass -File C:\kals-repo
estart_bot.ps1
```

---

## v-a20b — 2026-09-13 11:57Z — AMENDMENT 20b: the ruler reads DOWN moves only (`9591ec8`)

**What changed.** The volatility estimate is now `max(downside 300s, downside
1800s)` instead of `max(two-sided 300s, two-sided 3600s)`. The model's claim is
one-sided — the settle lands on its side of the strike — and we lose only when
the index comes in the other way, so a ruler built from both directions spends
half its information on moves that cannot hurt us.

**Evidence.** 45 rulers scored over 108,000 decisions rebuilt from the index
alone (`results/RESULTS_ruler.md`). Beat the ruler deployed 47 minutes earlier
on every axis in both halves: gated loss −48.5% vs −42.3%, sd(z) 0.950 vs
0.919 (1.000 is honest), kurtosis 53.5 vs 69.1, decisions kept −0.9% vs −1.0%.
Bar and kill criterion in `results/PREREG_ruler.md`, including BAR ITEM 4
(hedge frequency) added 12:32Z before anything was scored.

**Known cost, measured 2026-09-13 on the 12:30 PM ET BNB close:** this ruler
read **40% wider** than the old one at that second (0.0271 → 0.0379). A wider
ruler pushes every belief toward 0.5 and the hedge fires below 0.80, so it
makes the hedge fire more readily. That is arithmetic, not a counterfactual —
whether that particular hedge would have fired under the old ruler could NOT be
reconstructed from the tape and is not claimed.

**Revert:**

```powershell
# edit restart_bot.ps1: delete the "--sigma-ruler","maxdown" arguments
powershell -NoProfile -ExecutionPolicy Bypass -File C:\kals-repo
estart_bot.ps1
```

---

## v-a20 — 2026-09-13 11:10Z — AMENDMENT 20: the volatility ruler lengthens (`a988c71`)

**What changed.** `--sigma-ruler max3600`: volatility measured over the larger
of 300s and 3600s instead of 300s alone. **Superseded by v-a20b 47 minutes
later; it took two fills.**

**Evidence.** `results/RESULTS_calib.md` and `results/RESULTS_flood.md`: the
calmer the last five minutes, the MORE often the model blew up (4.28% in the
calmest fifth vs 1.05% in the choppiest, 4.05x, holding out of sample) because
a quiet 300 seconds understates the next minute. Lengthening the ruler
collapsed that gradient from 4.09x to 1.15x and cut kurtosis 132 → 47.

**The deploy failed on my own guard and the bot was down ~4 minutes.** The
self-test asserted `SIGMA_RULER == "live"`, but `main()` applies the flag
BEFORE running the suite. Fixed by asserting the DECLARED default
(`_DEFAULT_SIGMA_RULER`) instead. The same latent bug was in AMENDMENT 19's
guard and was fixed at the same time.

---

## v-a18 — 2026-09-13 09:24Z — AMENDMENT 18: bid up to the gate, not to the ask (`986cc71`)

**What changed.** The IOC limit is now the highest price that still passes the
SAME gate, instead of exactly the ask we saw. When we win the race we still pay
the resting price; when we lose it we take the next level instead of buying
nothing.

**Evidence.** 28.2% of orders filled nothing and it was not latency — filled
and zero-filled orders have the same median latency, 96 ms. A crossing IOC
fills at the RESTING price: 283 of 283 live fills at or below the signalled
price, 76 strictly better, ZERO worse (RUNBOOK CONFIRMED FACTS). 43% of lost
races had a next level still inside the gate at a median +0.20c.
`results/PREREG_sweep.md` holds the bar.

**First three swept fills, all winners:** SOL 6:15 AM ET (85.0→87.0c, +$5.01),
XRP 7:00 AM (95.1→97.5c, +$0.98), BNB 12:30 PM (92.0→92.3c, +$2.30 on the bet
before the hedge). n=3 proves the mechanism, not the economics.

**Revert:** add `"--no-sweep"` to the argument list in `restart_bot.ps1`.

---

## v-brake3 — 2026-09-13 02:26Z — BANK_BRAKE 1.5 → 3.0 (`f04087d`)

Size is `bank / (BANK_BRAKE x 2 x 0.98)`. The worst single close falls from 64%
of bank to 32%. Operator's decision; the reason recorded in the commit is not
the one either of us first gave.

**Revert:** `BANK_BRAKE = 1.5` in `research/pinrun.py`, restart.

---

## v-a17 — 2026-09-13 01:49Z — AMENDMENT 17: a close is capped on CONTRACTS (`3f393ea`)

`MAX_PER_CLOSE x SIZE` contracts per close, coins unlimited, instead of a cap
on the number of fills. Same worst-case exposure under both rules.

**Revert:** set `CLOSE_BUDGET = False`; the old fill-count cap is kept behind
it for exactly this.

---

## v-a16 — 2026-09-12 23:13Z — AMENDMENT 16: SIZE follows the bank (`c0f8e33`)

Size is re-read from `/portfolio/balance` every 300 s while flat, so it grows
and shrinks with the account instead of being a fixed argument. `--size` became
a starting value only.

**Revert:** `--no-auto-size`.

---

## v-hedgefix — 2026-09-12 20:07Z — a partial hedge fill was shrinking the original position (`2ffb40d`)

**A correctness fix, not a strategy change.** A partial hedge fill silently
reduced the ORIGINAL position's settled size, which understated losses fed to
the loss-abort brake. Every loss number computed before this commit is
suspect.

---

## v-a15 — 2026-09-12 18:06Z — AMENDMENT 15: the belief-collapse hedge, threshold 0.80

When the model's belief in a held position falls below 0.80, buy the opposite
side. Recovers about one third of a loss; costs ~$1.29/day at size 20 and saves
money in bad stretches. `results/PREREG_hedge.md` holds the bar.
**On 2026-09-12 the railed holdout showed the base strategy NEGATIVE on 72
unseen hours with the hedge carrying it** (`aa257ce`), which is the single most
important caveat attached to any live version.

**Revert:** `HEDGE_ENABLED = False` in `research/pinrun.py`.

---

## BACK-FILL NOTE

v-a13 (one fill per market) and v-a14 are NOT reconstructed here — they were
deployed while the log was lapsed and the commits do not state deploy times.
`git log --grep "AMENDMENT 13"` is the starting point if either needs reverting.
This gap is the cost of letting the log lapse and is left visible rather than
guessed at.

---

## v-a12a — 2026-09-11 13:25Z — AMENDMENT 12a: scraps accumulate, exposure re-bounded (`9aa2014`)

**Found by auditing my own change rather than admiring it.** A12 said a scrap
fill spends no scale-in slot. With nothing else changed that DOUBLED the worst
case: `MAX_ATTEMPTS_PER_CLOSE` is 8, so eight scraps of 9.99 contracts would
each keep a position and none would spend a slot — **79.9 contracts, $78.32,
against an intended $39.20**, with only the run-wide $130 stake cap as a
backstop. That is a regression I introduced this morning.

**Fix:** scraps ACCUMULATE. Once they add up to a real fill (half our size)
they spend a slot exactly as one fill would. Measured in the self-test by the
only number that matters — contracts filled before the slots run out:

| scrap size | contracts before slots exhaust | intended |
|---|---|---|
| 9.99 | 39.96 | 40 |
| 5.0 | 20.00 | 40 |
| 2.0 | 20.00 | 40 |
| 0.5 | 20.00 | 40 |

and within the 8-attempt cap, 0.02 crumbs still spend **no** slot — the thing
A12 exists for.

**Two of my own test assertions were wrong before this passed**, both recorded
in place rather than quietly edited: I asserted 8 scraps of 9.99 spend 7 slots
(the code gives 4, and the code is right), and that 0.02 crumbs "never" exhaust
the slots (they do, after a thousand; the attempt cap is the real bound).
Asserting a bound that does not exist is worse than not asserting.

Restarted 13:25Z, pid 611172.

---

## v-a12 — 2026-09-11 12:40Z — AMENDMENT 12: a scrap fill is not a slot (`d3e2ef0`)

**What changed:** a fill smaller than half our size (under 10 contracts at size
20) still books its POSITION — it exists, settles and releases like any other —
but no longer spends one of the `MAX_PER_CLOSE` buys for that close and no
longer raises the improve bar. It is written as a `scrap` record. The side is
still recorded, so the both-sides guard holds. Nothing else changed.

**Why:** 2026-09-11 07:00 ET, the bot asked for 20 twice and got **2.0** (BNB)
and **0.02** (BTC) — the offer was gone by the time the order landed — and each
scrap consumed a buy for its close and raised the bar, blocking a real fill
behind it. `MIN_FILL_FRAC` gated what we ask for; nothing gated what we got.
This was already logged as open in SKIM.md ("dust fills burn a scale-in slot").

**Risk:** none to money — a scrap can only lose its own few cents. The change
can only ADD a real fill where a scrap used to block one. Self-tested
structurally (slot booked only when `filled >= _real`, scrap recorded) and on
the arithmetic (at size 20 the line is 10; 2.0 and 0.02 are scraps).

Restarted 12:40Z in the quiet window; pid 602652.

---

## v-a10c — 2026-09-11 12:45Z — the crazy-deal guard was WRONG IN BOTH DIRECTIONS; fixed (`65b0fc2`)

**A second loss (KXSOL15M 12:30Z, −$12.16) went straight through the guard**:
99.508% sure, filled at 59.1¢ — a **29.5¢ discount** — because the rule demanded
≥99.9% confidence. Scoring the guard on all 139 live fills then showed the
other half of the error.

| discount to fair at the FILLED price | fills | lost | loss rate | P&L |
|---|---|---|---|---|
| under 2¢ | 42 | 1 | 2.4% | −$2.11 |
| 2–5¢ | 64 | 2 | 3.1% | −$0.11 |
| **5–15¢** | **24** | **0** | **0.0%** | **+$32.20** |
| **15¢+** | **9** | **4** | **44.4%** | **−$12.41** |

**As deployed the guard cost −$10.49**: it refused 8 winners (+$29.22) to avoid
2 losers (−$18.73). A measurably negative rule does not stay — the operator's
own test.

**Two changes, and their evidence is NOT equal.**
* **Drop the confidence condition — NOT fitted.** The SOL loss proves the
  discount matters independent of confidence, and every trade already passes
  PIN, so "confident" carried no information.
* **5¢ → 15¢ — FITTED, and labelled so.** The 5–15¢ evidence is strong and
  one-directional (0 losses in 24 fills, +$32.20; refusing it was the guard's
  worst error). The 15¢ line itself was chosen after seeing 9 fills. It is kept
  only because no guard is also negative on that band (−$12.41) and because the
  operator decided to refuse deals this extreme. **It claims no significance.
  The pre-registered review at 40 records decides it on data it never saw.**

Restarted 12:45Z, pid 601412. Revert: `DUMP_ENABLED = False`.

---

## v-a10b — 2026-09-11 00:12Z — AMENDMENT 10 ON, BY OPERATOR DECISION; would-be outcomes recorded (`0c5f513`)

**Operator:** *"don't do the 'crazy trades', but track them with the 'would be'
outcome. Later they'll be reviewed when populated with more data. Leave the
program to continue."*

**What changed:** `DUMP_ENABLED = True`. A fill where the model is ≥ 0.999 and the
offer is more than 5¢ below fair is refused. **Every such moment writes one
`dumped` record per (close, market)** — ticker, side, price, fair, tau, discount,
depth — whether or not it is refused, so the would-be P&L resolves against the
settlement later. Everything else is v-pin995.

**The basis, stated exactly:** the EV of this class is **undeterminable** on the
six live fills (+$4.75, mean +$0.79, SE ±$4.1, t = 0.19). On an undeterminable tie
the owner chose fewer losses. **This is a recorded owner decision, not a claim
that refusing is profitable.** The 40-fill evaluation stands: refuse stays only
if the 95% CI on mean would-be P&L is not entirely above zero; if it is, the
class comes back. Cumulative P&L is never the trigger.

**To resolve would-be outcomes:** join `dumped` records to settlements on ticker
— the same join `pinrace.py` does for orders.

**Revert (buy them again):** `DUMP_ENABLED = False`, stop/start per RESTART.md.

Restarted 00:12Z; pid 439076.

---

## v-a10a — 2026-09-10 23:51Z — AMENDMENT 10 SWITCHED TO LOG-ONLY: the math does not support it (`82f2656`)

**What changed:** `DUMP_ENABLED = False`. The guard still COUNTS every fill it
would have refused (`dumped` in the close summary) and refuses none. Trading rule
is back to exactly v-pin995. Live for 13 minutes (23:38–23:51Z); no fill was
refused in that window.

**Why it came off — the operator's rule, applied:** *if it is profitable do it,
if not don't; if the math is not certain, don't use it.* The six live fills of
this class: +15.36, +3.78, +2.82, +1.52, −16.61, −2.12 = **+$4.75, mean
+$0.79/fill, standard error ±$4.1, t = 0.19. The sign is not determinable.**
Refusing is not certifiably profitable; neither is buying. The frozen baseline
(buy) therefore stands. v-a10 was deployed on a loss-frequency preference
dressed as a decision, and that was wrong.

**The metric, settled:** `CLAUDE.md`'s own kill criterion defines "consistent"
as positive expectancy. Variance matters only through ruin, and this class
cannot cause ruin at size 20 (≤ $19.60 per fill, brakes intact). So the
criterion is EV alone; EV is unknown; the class is ~3 fills/day, so the decision
is worth ~$2/day either way and does not merit a rule until it can be measured.

**PRE-REGISTERED EVALUATION, fixed now:** at **40 fills** of this class (model
≥ 0.999 and offer > 5¢ below fair), refuse only if the 95% CI on their mean P&L
lies entirely below zero; keep only if entirely above; otherwise re-evaluate at
80. **Cumulative P&L is not a trigger** — a bar moved by outcomes is not a bar.

**Revert to v-a10 (refusing):** `DUMP_ENABLED = True`, stop/start per RESTART.md.

Restarted 23:51Z in the quiet window after the 23:45 settlement; pid 445008.

---

## v-a10 — 2026-09-10 23:38Z — AMENDMENT 10: never buy a certainty at a discount (`fdd581e`)

**What changed in `pinrun.py`:** after the edge floor, a fill is refused when the
model's confidence is ≥ 0.999 (3.09 sd) AND the offer sits more than 5¢ below the
model's fair value. Counted in the close summary as `dumped`. Nothing else: size
20, gate 0.995, ceiling 98.0¢, tau 3–30, brakes unchanged.

**Why (live fills only, both gates — `fair()` is identical in both):** 14 fills at
≥4 sd. The 8 priced 94¢+ went 8–0. The 6 priced below — 8¢ to 90¢ discounts on a
"certainty" — went 4–2, and both losses were the same reconstructed event: the
book sold us the certain side cheap and the index jumped 10–18 sigma within a
second. The model puts that at ~1e−9. A trade whose EV rests on that tail is a
trade whose EV cannot be estimated, so it is removed.

**Not a fitted threshold:** any discount cut from 6.2¢ to 8.1¢ gives the same
live result; 5¢ is the conservative side and ~17× the edge floor.

**Cost on the live record:** forgoes SOL +$15.36, DOGE +$3.78, ETH +$2.82, SOL
+$1.52; avoids XRP −$16.61, DOGE −$2.12. **EV ≈ neutral (−$4.75 over 111 fills);
loss frequency down by the whole class.** The operator's stated preference, and
the definition of consistent.

**The one thing the operator asked that this answers:** *"why can't we just not
buy the crazy 'deals' that basically always end up being someone knowing what's
happening?"* We now don't.

**Revert:** set `DUMP_DISCOUNT = 9.0` (never trips) or `git checkout fdd581e --
research/pinrun.py`, then stop/start per `RESTART.md`.

Restarted 23:38Z in the quiet window after the 23:30 settlement; pid 442440.

---

## v-pin995 — 2026-09-10 08:4xZ — AMENDMENT 9: the confidence gate 0.98 → 0.995 (`184c826`)

**THE BAR MOVED. Loud, dated, and with the evidence beside it.**

**What changed in `pinrun.py`:** `PIN = 0.995` (was 0.98). The bot now needs the
model at 99.5% — a margin of **2.58 sd** instead of 2.05 — before it will buy.
Nothing else: size 20, 2 buys per close, ceiling 98.0¢, tau 3–30, brakes −$60 /
3 losing closes / 2 order errors / 8 attempts.

**Evidence (`research/pinfirst.py`, 10,796 markets walked tau 30→3, flip rate
measured AT THE SECOND THE BOT FIRES, fit/holdout over closes):**

| margin at fill | markets | flips | rate | holdout |
|---|---|---|---|---|
| 2.05–2.3 sd | 502 | 9 | 1.79% | 2.51% → 1.38% (bands pooled) |
| 2.3–2.6 sd | 195 | 6 | 3.08% | |
| 2.6–4 sd | 594 | 3 | 0.51% | 0.74% → 0% |
| 4+ sd | 7,868 | 0 | [0, 0.05%] | 0 → 0 of 2,500 |

Flips at the crossing 18 → 10 at 0.995; holdout 3 → 1; 9,151 of 9,159 markets
still reach 0.995 inside the window. On the 84 live fills: skips 3 of the 5
losses (NEAR ×2, BNB — all fired at 2.09–2.25 sd), keeps every deep win,
keeps 43 fills.

**What is NOT known:** the fill count. Deeper markets are priced higher, so
the same number of opportunities may fill less often. The next 24 h measures
that. The operator's standing want is MORE bets; tonight's want was FEWER
losses, and this trades one for the other on evidence.

**Revert:**
```powershell
# research/pinrun.py line "PIN = 0.995"  ->  "PIN = 0.98", then stop/start per RESTART.md
git checkout 184c826 -- research/pinrun.py
```

Restarted during the maintenance halt; pid 246096.

---

## v-cond — 2026-09-10 07:47Z — conditions logged on every decision (`2994b55`)

**What changed in `pinrun.py`:** every `signal` record now carries `cond_x`,
`cond_n`, `cond_own` (see `IndexWS.conditions`). Tick retention 1200s → 4000s
so the 3600s baseline is real. A per-feed, per-second cache keyed on a version
counter (a revised print busts it, an identical duplicate does not).
**Nothing about what is bought, at what price, or in what size changed.**
Price ceiling, gates, brakes, size: identical to the previous version.

**Evidence:** `research/pintail.py` — the model's loss-tail is 2.22% with no
other coin moving and 6.60% with three or more (9,159 markets). Every fixed
gate on it failed a holdout split, so it is **logged, not gated**.

**Cost on the order path:** `conditions()` runs only when a signal fires;
~0.5 ms cached, 6 ms cold once per second. Measured.

**Revert:**
```powershell
git checkout 33ead84 -- research/pinrun.py
# then stop/start per RESTART.md
```

**Restart done during the exchange's maintenance halt** (`trading_active:
false`, all shards) — trader down 07:43–07:47Z, zero opportunity cost.
pid 245640, size 20, brake at 3 losing closes.

---

## OUTAGE — 2026-09-08 14:40–15:44 UTC, ~1 hour, NO TRADING

**Cause:** three separate hardcoded rails silently refused every scale-up, and
I verified the process *started* rather than that it *survived*.

1. `pinrun` refused `--loss-abort` outside `[-5.00, 0.00)`. The −$10 (v5) and
   −$15 (v6) values were rejected and the process **exited immediately**.
2. `pinrun` refused `--max-positions > 3`. I passed 4.
3. `pintake.MAX_TAKE_COUNT` was **1 contract**, and `MAX_RUN_STAKE` was $5 —
   less than a single size-8 buy (~$7.60). So even with (1) and (2) fixed,
   **size 3 and size 8 would both have been refused at the order stage.**

**The operator noticed before I did** ("No bets have been bought since we upped
it"). The lesson is recorded, not just the fix: **check that a process is still
alive after it starts, and that its orders are accepted, before believing a
deployment.**

**Fixes:** the loss abort now **scales with size** (allowed range is roughly 2–4
ordinary losses at whatever size is trading) instead of a flat cap that was
right at size 1 and fatal at size 8. Order rails raised deliberately with the
reasoning in the source: `MAX_TAKE_COUNT` 1 → 10 (~8% of the median 125
resting at the touch), `HARD_MAX` 5 → 25, `MAX_RUN_STAKE` $5 → $60.

**`pintake`'s own self-test also had to be fixed** — it asserted "count 2 must
be refused", which was correct when the rail was 1 and became a *false alarm*
the moment it was raised. The rail tests are now written **relative to the
constants**, so they stay meaningful at any setting.

---

## v14 — CURRENT (2026-09-08 22:47 UTC) — funded, size 20, cap 3

| setting | value |
|---|---|
| **bank** | **$154.33**, all on the Crypto shard |
| size | **20 contracts** |
| buys per close | **3**, each ≥0.5¢ cheaper than the last |
| partial fills | down to 50% of size |
| price ceiling | 98.8¢ |
| worst case, one close | $60 |
| dollar brake | −$90 |
| **loss-count brake** | **3 losing trades** |
| **attempts per close** | **8**, separate from the 3-fill cap |
| max open positions | 4 |
| pid / code sha | 4074664 / `e4cdb6320807` |

The operator funded the account. The $150 landed on exchange_index 0, where it
could not have bought anything, and $113.0360 was moved to the Crypto shard.

---

## THE RUNAWAY — 2026-09-08 22:44:30Z, 160 refused orders in one second

**No money lost. Balance unchanged, zero fills, zero open positions.** Caught by
the monitor and stopped within seconds.

**Two of my own changes collided, and neither was wrong alone.**

1. **`pintake.MAX_TAKE_COUNT` was still 10**, so every order at size 20 was
   silently refused. **The FOURTH size-1 literal to break scaling in one day**,
   after the loss-abort range, the run-stake cap and the stake release.
   `take()` *returns* its violations rather than raising, so nothing noticed:
   the order records carry `status_code: null`, `parsed: false`, `error: null`.
2. **AMENDMENT 6 had just stopped a no-fill from consuming a scale-in slot.**
   That is correct — an unfilled order creates no exposure — and it earned
   +27.96¢ within five minutes of deployment. But it left **nothing bounding
   how many times we may try**, so a permanently refused order retried at 20 Hz
   forever.

**Fills and attempts needed separate budgets and only had one.**

### Three fixes

| | |
|---|---|
| `set_limits()` now raises `MAX_TAKE_COUNT` too | and `HARD_MAX` with it, announced, never silently. Still refuses to lower either. |
| a returned refusal is now an **error** | `order_errors` increments, so two in a row halt the run |
| `MAX_ATTEMPTS_PER_CLOSE = 8` | counted **before** the send, so a call that never returns still consumes one |

**Verified against the production endpoint without sending:** `check_take` at
size 20 returned `['count 20.0 exceeds MAX_TAKE_COUNT 10.0']` before the fix and
`[]` after.

### The lesson, and it is the second time today

I verified the process **started** and that its start record described the right
configuration. **I did not verify that an order at the new size would be
ACCEPTED.** That is one function call, no network, no money, and it is now part
of every deployment. *"The process is alive"* and *"the process can trade"* are
different claims.

---

## v13 — 2026-09-08 22:15 UTC — cap 2 → 3

**Withdrawn, then reinstated at the operator's instruction** (*"if you know the
idea works then do it"*). It is **not a new mechanism**: the scale-in rule has
been live since v3 and has produced second buys on real closes. Cap 3 only lets
the same proven rule repeat once more, and **the trade it adds is the cheapest
of the close** — every extra buy must clear `IMPROVE_BY`, so a third buy is at
least 1.0¢ below the first. Cheaper wins more *and* loses less, so cap 3 cannot
degrade the average price paid. Structurally, not merely empirically.

Measured with losses injected per close at the 2.31% exact upper bound:

| | typical result | ruined |
|---|---|---|
| size 20, cap 2 | $271 | 3.4% |
| **size 20, cap 3** | **$304** | **1.1%** |

**12% more money and a third of the ruin.** What it costs is exposure, not
per-contract risk.

**The self-test found the deployment bug for free.** With `--max-positions 3`,
the third buy plus a straggler still settling from the previous close would have
been silently refused. The flag is now 4.

---

## v11 — 2026-09-08 21:39 UTC — MORE BETS, same maximum exposure

| setting | value |
|---|---|
| size | 10 contracts |
| **partial fills** | **take `min(size, offered)` down to 50% of size** |
| **scale-in slot** | **consumed by a FILL, never by an attempt** |
| price ceiling | 98.8¢ |
| loss abort | −$30.00 |
| pid / code sha | 4052684 / `792ee01f2153` |

**Neither change raises the maximum exposure of a close.** That was the
constraint, because the balance cannot fund more.

### Change 1 — a no-fill no longer burns a scale-in slot: +33.3%

`fired[close_s]` was written when the SIGNAL fired, *before* the order was
sent, so an order filling **zero** contracts still burned one of the two
allowed buys and still raised the improve bar. **5 of our first 19 live orders
filled nothing**, and depth was not the cause — the misses had 562, 107, 93, 10
and 5 contracts on offer. Lost races, not thin books, so they recur.

| at the observed 26% miss rate | closes won | buys | expected |
|---|---|---|---|
| no-fill BURNS a slot (before) | 67 | 87 | $40.29 |
| **no-fill keeps the slot** | **80** | **119** | **$53.72** |

**Max exposure unchanged** — the cap always meant two *fills*; the bug made it
two *attempts*.

### Change 2 — take a partial down to half size: +1.3% at size 10, +5.4% at 25

| threshold | buys | expected |
|---|---|---|
| full size only (before) | 124 | $59.75 |
| **≥50% of size** | **125** | **$60.53** |
| ≥5% of size | 129 | $58.37 |

**Taking any scrap is worse than taking none:** a tiny early fill burns a slot
and raises the improve bar, trading a big cheap buy later for a small dear one
now. Half is the measured optimum at both sizes. Exposure can only fall.

### MEASURED AND REJECTED: `MAX_PER_CLOSE` 2 → 3

**+26.7%, larger than either change above, and NOT deployed because it cannot
be funded.** Worst close $30 against a $38.83 balance, and the rail would need
a brake at −$45 or looser. **This is the best available change the moment the
account is funded.**

### Three self-tests were inspecting themselves

`src.index("def trade_loop(")` matched this test file's OWN string literal,
because `selftest()` is defined above `trade_loop`. Every structural check
built on it was reading the test instead of the code and could have passed
vacuously. All three now anchor on a newline.

**Revert:** `MIN_FILL_FRAC = 1.0`, and move `_book_slot()` back above the order.
**Pre-registration:** `results/PREREG_pin_live_AMENDMENT_6.md`.

---

## v10 — 2026-09-08 21:14 UTC — size 10, and two silent killers removed

| setting | value |
|---|---|
| size | **10 contracts** |
| price ceiling | 98.8¢ |
| buys per close | up to 2, second only if ≥0.5¢ cheaper |
| window | tau 3–30 s |
| loss abort | **−$30.00**, and the order path now agrees |
| pid / code sha | 4056648 / `497c2f96b280` |

### First size-10 trade: +103.14¢, more than the whole day before it

```
21:30Z close   KXBTC15M  tau=7s  buy NO @0.8900  fair 0.00256  edge +10.058c
1,000 contracts on offer, we took 10
filled 10.0 @ 0.89, fee $0.0680  ->  settled NO, payout $10.00
stake $8.9000 + fee $0.0680      profit +$1.0314   = 11.59% on stake
```

**89¢ is the cheapest price we have ever paid**, and the cheapest price wins
more *and* loses less. Break-even at 89¢ is an 11% error rate; ours is 0.90%.

### Two size-1 literals were silently disarming the trader — found by audit

1. **The stake release gave back ONE contract instead of the whole fill.**
   pintake commits `filled × price`; reconcile released bare `price`. At size 5
   that stranded $3.90 per settled trade, turning the $60 run-stake cap back
   into a **cap on lifetime turnover** — every order refused after ~15 fills,
   6 at size 10. `take()` *returns* the refusal rather than raising, so nothing
   halted and nothing logged. Two give-up branches released **nothing at all**.
2. **`pintake.LOSS_ABORT` was a hard −$2.00.** One ordinary loss at size 5 is
   −$4.88, so **the first loss we ever took would have shut off all trading**,
   silently, while the −$21 brake sat untouched.

**Fixes:** a single `_release()` used on all three exit paths, releasing
`cost × contracts`; P&L booked on contracts actually filled; and
`pintake.set_limits()`, which raises the order-path rails to agree with the
run's own brake and **refuses to tighten**.

**The self-tests now sweep sizes 1, 5, 8, 10, 25**, include a positive
assertion that a one-contract release at size 5 leaks $3.90 so they cannot pass
vacuously, and scan the source to require every exit path to release.

### Depth tracking added

`close_summary` now carries min/p25/median/p75/max/total contracts offered
across every moment we could have bought, plus how many survive at each
candidate size. Early readings: **median 530 contracts** on one close, **101**
on another, with 414 moments surviving size 10.

**Revert:** `--size 5 --loss-abort -21.00`.
**Revert trigger:** any fill above 98.8¢, or a flip rate above 2.31%.

---

## v9 — CURRENT (2026-09-08 16:36 UTC) — back to a 98.8¢ ceiling

| setting | value |
|---|---|
| **price ceiling** | **98.8¢** |
| size | 5 contracts |
| buys per close | up to 2, second only if ≥0.5¢ cheaper |
| window | tau 3–30 s |
| loss abort | −$21.00 |
| pid / code sha | 3997812 / `d6826548c653` |

---

## v8 — 96¢ CEILING. IT *WAS* LIVE, IT SUPPRESSED TRADING, AND I TWICE GOT THE STORY WRONG

**This entry has been wrong twice. Both wrong versions are described here rather
than deleted, because the failure mode is the lesson.**

### Wrong version 1 (16:35 UTC): "v8 is live and it is safer AND more profitable"

Two of the three claims did not hold. Total realised profit goes DOWN when you
tighten (742.0¢ → 724.9¢); it only rises in EXPECTATION at an assumed 0.90%
flip rate (625.9¢ → 649.3¢). And "the dear trades were never paying for the
risk" was never measured — there are **zero flips in the entire eligible
sample at every ceiling**, and the 96–98.8¢ band realised **+2.087¢ per
contract** over 784 moments. I stated a model output as a measurement.

### Wrong version 2 (16:20 UTC): "the 96¢ ceiling was never live"

**Also wrong, and worse, because I acted on it.** I read the live process's own
start record, saw `"price_ceiling": 0.988`, and concluded the change had never
been applied.

**That field was DERIVED, not the constant.** The line was:

```python
price_ceiling=round(1.0 - MEASURED_FLIP - EV_FLOOR, 4)   #  = 0.988, ALWAYS
```

It reports the ceiling the EV arithmetic *implies*. It never read
`PRICE_CEILING` at all. **A process running a 96¢ ceiling truthfully logged
98.8¢.** My "verify what the process logged, not what the source says" rule was
right in principle and I applied it to a field that could not answer the
question.

### What actually gave it away — the operator noticed the symptom first

The operator said "haven't seen a trade in a while." The 16:30Z close then
showed this:

```
close 16:30Z  4,264 looks  954 tradeable  fired: FALSE
best: KXBTC15M NO @ 96.6c  edge +2.891c  tau 28s  665.71 contracts on offer
```

Every gate in the code on disk passes that moment: edge 2.891¢ ≥ 0.3¢,
EV 2.270¢ ≥ 0.3¢, price 96.6¢ ≤ 98.8¢. **The only rule that rejects 96.6¢ is a
96¢ ceiling.** Behaviour, not logs, proved it was live.

### Cost

Live signal history: **12 of our 16 real signals were above 96¢** (mean price
paid 97.61¢). The 96¢ ceiling was refusing roughly three quarters of our
trades, against a backtest that predicted it would refuse 30%.

### Two fixes, both in `pinrun.py`

1. **The start record now logs `PRICE_CEILING` itself**, with the derived value
   kept alongside as `ev_implied_ceiling`, plus a `code_sha` fingerprint of the
   running file. A log line can no longer describe code that is not running.
2. **`close_summary` now emits `over_ceiling` and `neg_ev`.** Both counters
   existed and neither was reported, so the refusal was invisible in the log
   that was written specifically to explain refusals.

### The standing rule this replaces

*"Check what the process logged at start"* is not enough. **A configuration
check must read a field that is derived from the constant it claims to
describe — and the way to prove a rule is live is to find a moment it changed
the behaviour.**

---

## v7 — 2026-09-08 16:12 UTC

| setting | value |
|---|---|
| size | **5 contracts** per buy |
| buys per close | up to 2, second only if ≥0.5¢ cheaper |
| window | tau 3–30 s |
| EV gate | ≥0.3¢ at 0.90% flip rate → ceiling 98.8¢ |
| worst case per close | **$10.00** |
| loss abort | **−$21.00** → survives 2.1 bad closes |

### First size-8 trade: WON +49.34¢

```
KXHYPE15M  tau=9s  buy NO @0.9350  fair 0.0103  edge +5.04c  size on offer 34
filled 8.0 @ 0.934, fee $0.0346  ->  settled, payout $8.00
stake $7.4720 + fee $0.0346 = $7.5066   profit +$0.4934   = 6.6% on stake
crypto shard $38.2157 -> $38.7091, reconciles exactly
```

**The rebuilt order rails work end to end at size 8.**

### The safety system caught two configuration errors in ten minutes

**1. Self-halt after the fill (correct).**
```
HALT: realised $+0.00 with $7.47 still open; one more contract
      could take this run past $-15.00
```
Size 8 with 2 buys can commit ~$16 against a −$15 brake. **The configuration
was self-contradictory** and the forward-looking loss bound refused to enter a
state where the brake could be breached. Exactly the right behaviour.

**2. The deployment rail then refused −$21 at size 5 — right call, wrong
arithmetic.** It sized the abort against **one contract** when a close can buy
**MAX_PER_CLOSE** of them. Fixed to use `size × MAX_PER_CLOSE` as the unit of
loss, because **the unit of loss is a CLOSE, not a contract**.

### The pattern, now explicit

This is the **third** time today a limit set for a size-1 proof silently
blocked scaling: the loss-abort range, `pintake`'s 1-contract order cap and $5
run stake, and now the abort's unit of measure. Every one of them was *correct
for size 1* and wrong afterwards.

**Rule going forward: any constant tied to size must be expressed in terms of
size, never as a literal.**

---

## v6 @ size 1 — CURRENT (2026-09-08 15:47 UTC)

| setting | value |
|---|---|
| window | tau 3–**30** s |
| model gate | p_flip ≤ 0.02 |
| EV gate | ≥0.3¢ expected at 0.90% flip rate → ceiling **98.8¢** |
| size | **1 contract** |
| buys per close | up to **2**, second only if ≥0.5¢ cheaper |
| max exposure/close | ~$1.90 |
| loss abort | −$3.00 |

**Deployed at size 1 deliberately.** The operator's instruction: only go one
step beyond a *proven* version, and only if each change passed its historic
test and its failure would be identifiable.

**Each change passed:**
- EV gate — 5 of 7 live trades were negative-EV; break-even price = 1−f is exact
- scale-in — 70 closes, 4.18¢ → 7.43¢/close, average price paid FELL
- tau 30 — 0 flips in 2,872 moments across 118 closes at tau 21–30

**Each failure is distinguishable:**
| symptom | cause | fix |
|---|---|---|
| flips on trades at tau > 20 | v4 | `--tau-max 20` |
| second buy at a WORSE price than the first | v3 | `MAX_PER_CLOSE = 1` |
| any fill above ~98.7¢ | EV gate not binding | check `MEASURED_FLIP` |
| flip rate > 2.31% | the whole ceiling is wrong | re-derive every threshold |

**Size stays at 1 until this version has traded and won on its own.** Scaling
is a separate, later decision — it does not accelerate learning, only exposure.

---

## v4 — 2026-09-08 15:20 UTC — SHA `45966b9`

Window **20 → 30 seconds**. Model calibration measured by horizon: 0 flips in
5,219 moments below tau 30; 3.7× overconfident at 31–45; **10.9× at 46–60**.
The overconfidence is entirely a long-horizon effect, which also explains why
the `tau<=60` backtest cell was dead. Roughly doubles qualifying moments.

**Revert:** set `TAU_MAX = 20`.
**Revert trigger:** any flip on a trade at tau > 20 → review; a second → revert.

---

## v3 — 2026-09-08 15:00 UTC — SHA `d04647d`

**Scale in as the price improves**: up to 2 buys per close, the second only at
≥0.5¢ better. Measured 4.18¢ → 8.87¢ per opportunity, average price paid FELL
95.53¢ → 94.28¢. Waiting instead is strictly worse (skipping one tick missed 7
of 70 closes).

**Revert:** `MAX_PER_CLOSE = 1`.
**Revert trigger:** average fill price across a close exceeding the first
fill's price over 50+ closes.

---

## v2 — 2026-09-08 11:35 UTC — SHA `c3aca51`

**EV gate.** Replaced "model edge ≥ floor" with `EV = (1−f)(1−p) − f·p − fee ≥
0.3¢` at the **measured** 0.90% flip rate, implying a price ceiling near 98.5¢.
Found because 5 of the first 7 live trades were negative-EV: breakeven price is
exactly `1 − f = 99.1¢`, and the model's own fair value implied 0.06% error
where reality is 0.90%.

Effect: profit per trade 1.41¢ → 3.42¢.

**Revert:** remove the `expected_value` check.

---

## v1 — 2026-09-08 08:20 UTC — SHA `2489d73`

**Edge floor 0.5¢ → 0.3¢.** Out of sample the looser floor gave 389 closes /
+2.76¢ / t=+5.6 / 1 flip in 359, against 354 / +2.51¢ / t=+4.1 / 3 flips in 333.

**Revert:** `EDGE_FLOOR = 0.005`.
**Revert trigger:** live flip rate ≥ 1.0%.

---

## v0 — 2026-09-08 07:09 UTC — first live version

tau 3–20, fair ≥0.98/≤0.02, edge ≥0.5¢, one buy per close, size 1,
loss abort −$3.00. First real trade 08:00Z (BTC YES @0.992, won +0.74¢).

---

## Running record

| | |
|---|---|
| won / **lost** | **29 / 3** |
| live flip rate | **9.4%** (3 of 32) — see the caveat below |
| bank | **$110.33** |
| day | started $38.83, funded +$113.04, now $110.33 = **−$41.54** |
| best single close | +$2.52 (three fills) |
| best single trade | +185.51¢ (SOL at 90.1¢) |
| **worst single close** | **−$52.60** (three fills, ONE market, all lost together) |

### THE FIRST LOSS — 2026-09-09 00:45Z, KXNEAR15M

Three same-side buys on **one market** at tau 22 / 21 / 17, 96.2¢ / 95.6¢ /
73.0¢, all lost together. The loss-count brake halted the run. Settlement was
reproduced independently from the raw index and agrees with the exchange, so
**the arithmetic is not broken**. The index sat flat for eight seconds, then
moved 0.0021 in a single second at tau 16 and never came back.

**A six-agent forensic investigation refuted nearly every proposed fix,
including my own.** Flatness, sigma regime and recent-jump separate losers from
winners at p = 0.14–0.99; once the model's own `z` is held fixed, nothing adds
anything. Every entry gate tested costs **22–44 winning trades per loss
avoided**. See AMENDMENT 8 and IDEAS_LOG.

**The live flip rate of 9.4% is 3 losses in one correlated close, not 3
independent events.** Clustered by close it is 1 losing close in 20, and the
sample is far too small either way. It does NOT yet exceed the 2.31% bound that
would kill the strategy, because that bound is per-trade on independent draws
and these were not independent. **This is exactly why the brake now counts
closes.**

## What to check first if it starts losing

1. **Flip rate by tau.** If flips appear above tau 20, v4 is the cause — revert
   to `TAU_MAX = 20`.
2. **Average fill price per close.** If the second buy is coming at *worse*
   prices, v3's mechanism has reversed — set `MAX_PER_CLOSE = 1`.
3. **Prices paid.** If trades are appearing above 98.5¢, the EV gate is not
   binding — check `MEASURED_FLIP` and `EV_FLOOR`.
4. **The measured flip rate itself.** Everything above is built on 0.90% from
   3 flips in 333. If the live rate exceeds 2.31% (the EXACT one-sided 95%
   Clopper-Pearson bound; the 1.80% figure quoted until 2026-09-08 was a normal
   approximation and is optimistic by 28% at only 3 events), the
   price ceiling is wrong and every threshold must be re-derived.
