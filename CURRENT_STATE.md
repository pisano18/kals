# CURRENT_STATE.md -- read this FIRST, before anything else

Written so a session that has just been `/clear`ed can pick up without
re-deriving anything. **Updated 2026-09-16 ~5:35 PM ET.** If the date above is
more than a day old, verify the live numbers before quoting them.

**2026-09-16: READ THE TOP OF `HANDOFF.md` FIRST.** That session produced
mostly NEGATIVE results and, more importantly, FIVE of its own headline numbers
were artefacts that a holdout or the operator caught. They are listed there with
the corrected values. Do not re-run those analyses from scratch.

`CLAUDE.md` = the rules. `PROJECT_HISTORY.md` = why things were killed.
`HANDOFF.md` = the long running log (read the newest section, then only what you
need). **This file = what is true right now.**

## The bot, as deployed

| | |
|---|---|
| process | `research/pinrun.py --live --size 20 --minutes 4320 --loss-abort -60.00 --max-positions 3 --max-losses 2 --improve-scope market --pick best --max-per-market 2 --improve-max 0.010 --min-fill-frac 0 --sweep-depth --depth-ladder --jump-gate --hedge-belief 0.60` |
| launched | `C:\Python314\python.exe -u`, cwd `C:\kals-repo`, detached, via `restart_bot.ps1` |
| bank | **$529.98** at 2026-09-16 21:30Z (read live from `/portfolio/balance`) |
| SIZE | **auto**, from the bank -- currently **90 contracts**. `--size` is only a starting value |
| BANK_BRAKE | 3.0 -> size = bank / (3.0 x 2 x 0.98) = bank / 5.88 |
| close cap | CONTRACTS, not fills (A17): `MAX_PER_CLOSE x SIZE`, MAX_PER_CLOSE = 2 |
| hedge | on, fires at belief < **0.60** (was 0.80; lowered 2026-09-15) |
| gate | PIN 0.995, ceiling 0.98, tau 3-30s, edge >= 0.3c, EV >= 0.3c |
| per market | **2 fills** (A23 + A29, live since 2026-09-14) |
| scan order | BEST first (A24) |
| depth floor | **MIN_FILL_FRAC 0** -- a thin book is taken rather than skipped (A28) |
| sweep | on. Swept fills are 62 contracts at the median against 20 unswept, at the SAME 2.4c per contract and a LOWER loss rate |

## Live record, all time

451 closes, 430 won, **21 lost (4.66%)**, net **+$374.92**. Wins grow with size
($26 -> $175 a day gross); losses are lumpy ($0 to $118 a day) and are what
actually decides a day. Sep 13 looked like a great day because it lost only
$13, not because it won more -- Sep 14 won MORE and finished at half the money.

## THE ONE NUMBER TO WATCH: what fraction of our size the book fills

`python research/pinfill.py`. The bot asks for `size` contracts and the book
hands back what it has. That ratio is the leading indicator of the whole
compounding projection, because size grows with the bank but the offers do not.

    ET day   size   contracts per fill   % of size we got
    Sep 13     47          44.8                95%
    Sep 14     58          54.4                94%
    Sep 15     74          69.8                94%
    Sep 16     84          67.3                80%   <-- first slip

Measured over 446 signals, the offer waiting for us is p25 23 contracts, p50
67, p75 202. Half of all opportunities cannot fill an order of 67, and we are
already asking for 90. Replaying those signals at bigger caps: 2.2x the size
buys 1.68x the volume, 5.6x buys 2.44x. Volume grows like a SQUARE ROOT of
size, which is why `research/pinproject.py` exists and why the older linear
projection (\$3,476 by day 12, \$570/day) is roughly double the truth.

If that percentage keeps falling as the bank grows, the cautious column of
pinproject is the one to plan on. If it holds near 90%, the expected column is.

## What is settled and must not be re-litigated

- **The book is NOT the constraint.** Median fill is 100% of what the bot asked
  for on every single day. The BANK is the lever, with ~4x headroom before our
  share of book starts to bind. (`research/pinfill.py`)
- **Opportunities are NOT falling.** 2.0-5.7 signals per hour up, no trend.
  (`research/pinwhy.py`)
- **Extreme confidence was being picked off at the cheap end** -- big-edge
  trades lost 8.8% before 2026-09-12 and 1.4% after. The dump guard and jump
  gate fixed it. No change needed. (`research/pinadverse.py`)
- **Crypto.com / CDNA: FIX is the only order-entry route**, and an
  exchange.crypto.com API key is NOT valid on /dcm or /fcm (escalated support
  answer, matches our 40101s). Onboarding is opened through the in-app support
  chat. Blocking question: the per-contract fee -- the strategy there dies above
  about 4c. (`results/RESULTS_fcm_b2c.md`)
- **Dead ends, with evidence, in HANDOFF.md:** raising EDGE_FLOOR, a depth gate,
  hourly markets, more Kalshi series, Polymarket on-chain venues.

**To restart it -- USE THE SCRIPT, AND ONLY THE SCRIPT:**

```
powershell -ExecutionPolicy Bypass -File C:\kals-repo\restart_bot.ps1
```

That form works from bash, cmd or PowerShell. `.\restart_bot.ps1` typed into a
bash prompt silently does nothing, which wasted two attempts on 2026-09-13.
The script refuses if the bot is holding a position, proves the old one is gone
**by pid** before starting a new one, aborts rather than starting a second if
it cannot, and writes `results/restart_bot.last.log` either way.

**THE HAND-ROLLED RECIPE THAT USED TO LIVE HERE IS DELETED, NOT MOVED.** It
matched processes on `CommandLine`, which Windows returns EMPTY to a caller
that cannot open the process. That is exactly how two live bots ended up
trading the same account on 2026-09-14 -- see the incident section below. It
also killed every `pinrun`, paper what-ifs included. Do not reconstruct it.

If the script ever refuses because of a stale `results/pinrun-live.pid`, check
the pid is really dead and delete the file; the bot itself also refuses to
start a second live copy while that pid is alive.

`kauth` lives at `C:\Users\Joe\AppData\Local\Temp\kals-work` and `pinrun.py`
line ~103 puts it on `sys.path` itself, so a plain restart works.

## The numbers that matter

**Live, current version** (hedge 0.80, from 2026-09-12 2:06 PM ET) --
`python research/pinver.py` regenerates all of this:

- **35 closes, 34W 1L, net +$65.06. Close-loss rate 2.86%, CI [0.07, 14.92].**
- 48 markets, 47W 1L. Fill ratio 71.8% (we lose ~28% of races).
- Mean entry 95.6c, mean edge at signal +3.9c.

**BREAK-EVEN IS NOT 3.58%. CORRECTED 2026-09-14.** That figure assumed a win
pays 3.7c and a loss costs 96c PER CONTRACT -- no hedge, every loss total. The
belief-collapse hedge (A15) and the sweep (A18) changed both sides, and the
right way to compute it is from our own settled closes:

| window | avg winning close | avg losing close | break-even loss rate | we lose |
|---|---|---|---|---|
| all time (232 closes) | +$1.36 | -$14.55 | **8.55%** | **4.31%** |
| second half | +$1.79 | -$9.77 | 15.45% | 4.31% |
| last 100 closes | +$1.87 | -$7.92 | **19.11%** | **4.00%** |

**Our 95% range on the loss rate is [2.09%, 7.78%]** (10 losing of 232, exact
Clopper-Pearson). Even the WORST end of that range, 7.78%, sits under the
most conservative break-even, 8.55%. **So the strategy is profitable at 95%
confidence** -- which the stale 3.58% figure said it was not.

**What is still uncertain is the SIZE of a loss, not the rate.** The average
losing close rests on TEN events and the distribution is fat-tailed (the worst
was -$52.60). A few bad closes would move the 8.55% number a long way, and it
is the number the whole conclusion hangs on. Watch it, not the loss rate.

*The superseded claim, kept so the change is visible: "BREAK-EVEN IS A 3.58%
CLOSE-LOSS RATE ... All live history is 12 losing of 248 closes = 4.84%; the
current version is 2.86%. The two straddle break-even and neither has the
sample to settle it. This is the single most important open number in the
project."*

## Settled recently -- do not re-litigate

| question | answer | where |
|---|---|---|
| Is the 10x loss-rate gap calibration or selection? | **SELECTION.** Where nobody offered, the model is nearly right (off 0.028pp); where someone did, off 0.725pp -- 26x. The counterparty is informed. | `results/RESULTS_select.md` |
| Can we sell winners before settlement? | **NO.** By 15s out a loser's bid is already 23c, 6c at 10s. Every exit cell loses money. Dead on mechanism. | `results/RESULTS_exit.md` |
| Should the depth floor be lowered/removed? | **NO.** Removing it costs 30% of the money: +15% fills, -35% mean size, -25% contracts. | `results/RESULTS_levels.md` |
| Are some coins safer? | **NO.** Spread appears 53% of the time by chance; rank correlation between halves +0.35; out of sample the rule fails non-monotonically. | `results/PREREG_coinrank.md` |
| Does buying the SAME coin twice add risk? | **YES IF THE PRICE DROPPED A LOT, NO IF IT DROPPED A LITTLE -- and that is a dose-response, not a yes/no.** A second fill is the SAME bet, so the question is which closes offer a cheaper second price. Of 862 markets where none ever appeared, **0 lost**; of 398 where one did, 25 lost (6.28%), +6.28pp with a 95% CI of [+3.46, +9.82] bootstrapped over CLOSES. By size of the discount: **0.5-1c -> 0.70% lost, second leg +3.08c/contract; 1-2c -> 5.67%, -0.09c; 2-5c -> 11.49%, -4.92c; 5-10c -> 26.09%, -11.45c.** Break-even is 3.58%. Ordering survives a 60/40 holdout on close time (last 40% never fitted: 1.79 / 6.06 / 21.21 / 44.44%). AMENDMENT 23 is that band, in a paper what-if, NOT live. | `research/pinpick.py`, `results/RESULTS_pick.md` |
| "If it's really going to flip the confidence should be dropping" -- is it? | **TRUE, AND TOO SLOW TO USE.** 18,653 closes rebuilt from the index with nothing filtered (the candidate file is CENSORED -- its minimum confidence is 0.995002 because a row is only written once the model is certain, so it cannot answer this). Confidence falls below the gate on **31 of 31** closes the model gets wrong and only **0.4%** of the ones it gets right -- but late: 11 of 18 by tau 25, 12 of 19 by tau 20. On our own money later still: SOL 2026-09-12 23:00 was bought three times at tau 30/29/28 while confidence ROSE 0.9994 -> 0.9997 -> 0.9998; the flip showed around tau 12. Conditional on the gate still passing, loss odds are 0.37x at tau 20 -- real, but the PRICE is the fast signal and the confidence is not. | `research/pinwarn.py`, `results/RESULTS_warn.md` |
| Take the FIRST passing market or scan for the BEST? | **BEST, and it costs no time.** 2+ different markets pass in the same scan second on 6.3% of passes; when they do, the first seen is the best-edge one only 56.3% of the time, giving up a mean 2.10c (p90 7.43c) and paying 2.21c more. Replayed one contract per close: **+2.07c -> +2.76c per contract on IDENTICAL loss counts (10 and 10)**; holdout last 40%, never fitted, +1.63c -> +2.43c on 6 and 6. Highest-confidence reaches only +2.19c, so the gain is price, not risk appetite. The old order was dict insertion order -- the one gate in the bot that was not an EV comparison. **AMENDMENT 24 WENT LIVE 2026-09-13 8:35 PM ET**, with a paper twin running `--pick first` alongside it as the control arm. | `research/pinpick.py`, `results/RESULTS_pick.md` |
| Are there hourly series worth trading? | **15 of 71 settle on an AVERAGE** -- KXBTC/KXBTCD, KXETH/KXETHD, KXSOL*, KXXRP*, KXDOGE*, KXBNB*, KXHYPE*, KXDJI. Same mechanism as our 15-minute markets, and 4 (gold, silver, WTI, palladium hourly) are single-price and dead to us. 40 never ran a market. **2026-09-14: the books ARE quoted through the close** -- 68-94% of reads carry an ask, against 56-94% on our own markets. An earlier 'zero of 612 reads had any ask' was a bug in the probe's own strike selection (it sampled only 99c strikes, which cannot have an ask) and is withdrawn. Still untested is whether anyone sells the WINNING side at a price we would pay. **Best untested lead in the project.** | this file |
| Are there OTHER markets we could trade? | **28 fifteen-minute series exist; we trade 12.** Of the other 16: platinum, palladium, EURUSD, GBPUSD, USDJPY, S&P and Nasdaq have **never run a market**. Gold, silver, WTI, natgas and copper HAVE (200+ settled each) -- and **settle on the close of a 1-MINUTE CANDLE, not a 60-second average**, so the pin edge does not exist there. At tau=5 our uncertainty is 0.12 sigma; theirs is 2.24 -- **18x worse**, and 28x at tau=3. Source is Pyth, not CF Benchmarks. Also 71 hourly series, untested. | this file |
| Do S&P/Nasdaq 15-min series exist? | They exist, `fifteen_min`, `quadratic` -- and have **NEVER run a market**. Contradiction 3 closed, IDEAS.md B3 struck. | this file |
| Does "did anyone else take this offer" recover the population rule 5 says the tape cannot see? | **NO as a trading rule, PARTLY as a population filter.** The forward split is contaminated by outcome leakage (gap grows 3.2 -> 88.6 pp as the window widens 250 ms -> 60 s); the clean backward version has NO POWER (+1.27 pp, [-1.62, +4.57], MDE 4.05). | `results/RESULTS_contest.md` |
| Can we win more races by bidding above the ask? | **Probably, and it is nearly free** -- a crossing IOC fills at the RESTING price (283/283 live fills at or better than signalled, zero worse). 43% of lost races have a next level that still clears the SAME gate, median +0.20c. NOT DEPLOYED: needs the live bar. | `results/PREREG_sweep.md` |
| Is losing 28% of races a latency problem? | **NO.** Filled and zero-filled orders have identical latency (median 96 ms both). The competing take lands at a median 67 ms. We cannot out-run them; we can only cross a level. | this file |
| Is there anything in the 11 GB of `feed_data`? | **NO, on all three things worth trying.** (1) Our own index reconstruction does NOT lead the published one -- it LAGS (peak r 0.249 at lag -1 against 0.025 at +1; gap-regression slope -0.004, t=-6.9). (2) Exchange disagreement does not predict blow-ups (best 1.48x against an MDE of 2.58x, 3 of 4 features flip in the holdout). (3) The ORDER BOOK does not either -- 55.7M snapshots, all five features between 0.87x and 1.36x against an MDE of 2.53x, including the one I bet on (withdrawal, 0.95x). | `RESULTS_feed_BTC.md`, `RESULTS_disagree.md`, `RESULTS_book.md` |
| Trade more carefully after a loss? | **NO.** 0 of 18 closes following a loss lost (vs 2.62% baseline). Mean $ after a loss is HIGHER. A 1-close cooldown costs 6% of profit and saves nothing measurable. | this file |

## Per-function attribution — what is and is not knowable

Set up 2026-09-13 on the operator's request to see "each individual
implementation and function and algorithm and decision of the bot and see how
it alone affected what happens". Three layers, and they are not equally good:

1. **Refusals — solid.** AMENDMENT 25 instruments 18 decision points; every one
   records, once per (close, market), that it stopped a trade and what was on
   the table. `research/pinattrib.py` reads it. Gives: how often it came into
   play, over how many closes, whether it merely DELAYED a trade we made anyway
   or genuinely BLOCKED one, and whether the blocked ones would have won.
   **Binding-by-construction**: the loop stops at the first objection, so a
   recorded refusal IS the deciding one — but only in the order the gates run.
2. **Money on a refusal — an UPPER BOUND, never P&L.** A price showing is not a
   fill; rule 5. Always labelled `if filled`.
3. **True marginal value of a change — only a PAPER TWIN gives it.** Gates share
   one contract budget, so the columns never add to total P&L. The general
   pattern, and the one to reuse for any future change: run a paper bot
   identical to live except for that one flag, and difference them. That is what
   the `--pick` and `--max-per-market` what-ifs are.

**What is NOT covered:** anything that shapes a trade we DID make (the sweep's
limit, the auto-sizer, the hedge threshold) leaves no refusal record. Those need
a paper twin, layer 3.

## Open, and worth work

1. **The sweep (race harder).** `results/PREREG_sweep.md` is written and the
   bar is set; the code is not. Order **+17% more fills at the same gate**,
   ~+$4-6/day at today's size, and the one risk the tape cannot measure is
   whether swept fills are adversely selected. **Operator decision, not mine.**
2. **Quote age.** `pinselect` found every bad fill sat on a price under 0.25s
   old; prices resting 30s+ had 0 failures in 302. Now LOGGED live as
   `level_age_ms` / `level_age_exact` on every signal, and **deliberately not
   gated on** -- four self-tests assert nothing branches on it. Needs a
   pre-registered bar once there is live data. **Best lead open.**
3. **The loss rate itself.** Everything hinges on it. Keep counting.
4. `results/PREREG_hedge.md` -- n=30 live bar, 3 events so far.
5. `results/PREREG_coinrank.md` -- 147 forward clean fills for one coin.
6. `results/PREREG_coin.md` -- 30 SOL closes.

## Hedge, measured 2026-09-13

Recovers about **one third of a loss**, and it degrades with size:

| size | recovered |
|---|---|
| 20 | 34.9% |
| 39 (now) | 33.2% |
| 68 | 33.2% |
| 125 | 31.0% |
| 250 | 22.3% |

Holds to ~125, then the opposite side's depth runs out. **The hedge IS a sale**
-- buying NO at 80c is identical to selling YES at 20c, because the pair always
pays $1. Over the full 18.6-day window the hedge COSTS ~$1.29/day at size 20
and SAVES money in bad stretches. It is insurance, not edge.

## The tape got worse in the last third -- not our loss rate, the environment

`pincontest`, live-gate candidate population, split on close time: the
**first 70% of closes fail on 1.87% of rows, the last 30% on 4.61%** (11 losing
closes of 501, then 10 of 215). This is a TAPE population and is not our loss
rate (rule 5). It is the environment the bot trades in, it is getting harder,
and it is consistent with `RESULTS_levels`' note that the second half of the
window was 3x worse. Any threshold fitted on the whole window is fitted on a
gentler market than the current one.

**WHAT CHANGED -- AND MY FIRST TWO ANSWERS WERE BOTH WRONG. Read this whole
block before quoting anything about the deterioration.**

Answer 1, WITHDRAWN: "the model got more wrong." Answer 2, WITHDRAWN: "and it
got worse in the quantiles we trade." Both rested on `pincalib`'s first
version, which counted `abs(z)` -- the two-sided tail -- against a ONE-SIDED
promise, and so doubled every overconfidence figure and reversed the sign of
the early/late comparison. Corrected 2026-09-13 and re-run.

**What is TRUE, on the corrected numbers (`results/RESULTS_calib.md`, the
index feed alone, 109,122 z-scores over 1,672 closes):**

- The model is **8.0x overconfident** at the confidence the gate operates at:
  it promises to be wrong 0.15% of the time and is wrong 1.21%. At 99.99% it
  is 69.6x out. sd(z) is 1.151 -- the body is nearly right -- and kurtosis is
  **132 against a normal's 3**. The index jumps in ways a Gaussian says cannot
  happen, and every jump lands in the only region this strategy trades.
- **That has NOT changed over the window.** Early closes 1.22% realised
  failure at the 99.85% level, late closes 1.17%. Flat, if anything better.
- **The counterparty has not changed either** (contest 88.6% -> 86.8%, speed
  66 -> 70 ms, depth UP) -- though the nightly `collide` robot is right that
  this claim has never had its power stated, so treat it as unsettled.

**So WHY the candidate population's bad rate roughly doubled (1.87% -> 4.61%)
is OPEN. It is not model drift and it is not coin mix (8 of 9 coins worsened
individually). That question is now the top open item.**

**The obvious fix is dead -- do not re-try it.** Multiplying the volatility
estimate by k keeps 44% of candidates at 3.09% bad (k=1.25), 26% at 3.41%
(k=1.5), 14% at 4.62% (k=2.0), against 2.90% at k=1.0. The corrected
calibration says exactly why: the error is SHAPE, not WIDTH. sd(z) is 15% off;
kurtosis is 44x off. Scaling sigma stretches the body, where the model is
nearly right, and barely touches the tail, which is the whole problem.

**AMENDMENT 19 exists and is OFF.** `pinrun --honest` maps confidence through
the measured table instead of a Gaussian. At PIN 0.995 it demands **z >= 4.33**
where today's gate demands 2.58 -- a much stricter bar. Bar and kill criterion
in `results/PREREG_honest.md`; the trade-count impact is deliberately NOT
estimated from the replay.

**From live fills only** (270 entry fills, 9 losses, net +$81.42): below 96c,
106 fills, 6 losses, +$58.14. At 96c and above, 164 fills, 3 losses, +$23.27.
Both halves make money, so there is no support for simply lowering the price
ceiling. The one negative bucket is 94-96c (49 fills, 3 losses, -$18.32) and
it has no power.

## 2026-09-14: TWO LIVE BOTS RAN AT ONCE FOR 24 MINUTES

Read this before touching `restart_bot.ps1` or starting the bot by hand.

`restart_bot.ps1` found the running bot by matching `Win32_Process`
**CommandLine**. Run from the operator's own shell that field came back
**EMPTY** -- Windows hides it from a caller that cannot open the process -- so
the kill loop matched nothing, said nothing, and the script started a SECOND
live bot. pid 1277276 (old code) and pid 1340892 (`--pick best`) both traded
the live account 20:35-20:59 ET.

**Nothing actually traded in the overlap** (zero orders, zero settlements from
either) and both were flat when found, so no money was doubled. The risk was
real anyway: every rail in `pinrun` is per-process and counts only its own
fills -- loss abort, loss bound, stake cap, position cap, losing-trade brake --
so two processes double all of them, while both size off the same bank.

**AMENDMENT 27 fixes it in the BOT, not the script**, because the failure was
the script being unable to see. `pinrun --live` writes
`results/pinrun-live.pid` and refuses to start while that pid is alive.
`_pid_alive()` reads no command line and answers **YES when it cannot tell** --
a false "already running" costs one command to clear, a false "nothing
running" costs a second bot on the account. `restart_bot.ps1` now reads the
pid file first, proves the target is gone by pid, and **aborts rather than
falling through to a start**.

**The same fault also produced a FALSE ALARM: "collector processes alive: 0".**
Both recorders had been running since Sep 9. That check is now by file -- and
it had to learn that the two recorders write differently: `kalshi_collector`
flushes continuously, `crypto_feeds` gzips a whole hour in memory and writes
at the rotation, so its in-progress file sits at **0 bytes for up to 59
minutes**. A naive freshness test alarms on a healthy feed recorder almost
permanently. Six consecutive hours verified at 280-690 KB per feed.

## Hard-won gotchas that will bite again

- **DOWNTIME IS NOT A WEAK DAY.** Operator, 2026-09-15: "We lost 7 hours of
  trade time today. Make sure that's known for any future calculations so it
  doesn't make our daily calculations look worse." The live bot could not trade
  **7.57 h on 2026-09-15 (ET)**: 13:29Z-20:24Z (Windows Update restart -> Kalshi
  TRADING_BLOCKED pending ID verification -> API key deleted, new key 5163259c)
  plus two crashes 04:29-04:49Z and 04:59-05:19Z. Every $/day, trades/day or
  growth figure divides by hours UP, from `results/DOWNTIME.json` via
  `research/downtime.py`; pinhealth prints the per-hour-up table. **Add a window
  the moment an outage happens.** Hours up count ONLY time that has passed (24 - lost overstated it on a partial day and read $3.49/h; the operator caught it). 2026-09-15 as of 16:48 ET: +$58.83 in 9.24 h up = $6.37/h, ~$153 on a 24h basis.

- **A self-test must match a whole LINE at its real indentation**, never a
  substring. `out = pintake.take(` is a substring of `_hout = pintake.take(`;
  that alone broke a check today, and three more on 2026-09-11.
- **Every size-derived rail must move with SIZE** -- `MAX_TAKE_COUNT`,
  `MAX_RUN_STAKE`, `--loss-abort`. Four size-1 literals once refused 160
  orders silently, because `take()` RETURNS its refusal instead of raising.
- **`pintake.set_limits` refuses to TIGHTEN.** Never hand it a tightening or
  the caller rolls back.
- **Never infer a unit from magnitude.** `/portfolio/balance` gives cents AND
  `balance_dollars`; `read_bank()` requires both to agree.
- **Cluster by close TIME, not series+time.** Twelve series settle on one
  second at rho ~ 0.8. Getting this wrong inflated n from 25 to 36 today.
- **`pinlevels_rows.jsonl` holds candidates the live bot REFUSES.** 2,699 of
  the 16,683 rows are `verdict: refuse`, fired by the dump guard -- offers at
  2c on a side the model calls certain, which lose 77% of the time. Any
  re-score must filter (`pincontest.gate(rows, "live")` does). Including them
  manufactured a 10 pp gap out of a population the bot never trades, in the
  first run of `pincontest` today.
- **`pinlevels` caches candidates** in `results/pinlevels_rows.jsonl` (422
  book hours, 16,683 rows). Re-scoring is seconds; re-walking the tape is
  hours. Almost every question below is a re-score.

## Cheap commands

```bash
python research/versioncheck.py                  # live flags vs VERSIONS.md
python research/pinver.py                    # how is the current version doing
python research/pinbank.py --bank 234        # what size does the bank support
python research/pinlevels.py --minfill 39:1.0,0.5,0.25   # re-score, no tape walk
python research/pincontest.py --rescore --gate live      # contest split, 3 s
python research/<file>.py --selftest         # always before trusting a file
```
