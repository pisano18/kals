# CURRENT_STATE.md -- read this FIRST, before anything else

Written so a session that has just been `/clear`ed can pick up without
re-deriving anything. **Updated 2026-09-13 ~4:20 AM ET.** If the date above is
more than a day old, verify the live numbers before quoting them.

`CLAUDE.md` = the rules. `PROJECT_HISTORY.md` = why things were killed.
`HANDOFF.md` = the long running log (66k tokens, read only when you need a
specific past result). **This file = what is true right now.**

## The bot, as deployed

| | |
|---|---|
| process | `research/pinrun.py --live --size 20 --minutes 4320 --loss-abort -60.00 --max-positions 3 --max-losses 3` |
| launched | `C:\Python314\python.exe -u`, cwd `C:\kals-repo`, detached |
| bank | ~$234 (read live from `/portfolio/balance`) |
| SIZE | **auto**, from the bank -- `--size` is only a starting value |
| BANK_BRAKE | **3.0** -> size = bank / (3.0 x 2 x 0.98) = bank / 5.88 |
| close cap | **CONTRACTS, not fills** (A17): `MAX_PER_CLOSE x SIZE`, coins unlimited |
| hedge | on, fires at belief < 0.80 |
| gate | PIN 0.995, ceiling 0.98, tau 3-30s, edge >= 0.3c, EV >= 0.3c |
| per market | 1 fill (A13) |
| depth floor | MIN_FILL_FRAC 0.50, measured against FULL size |

**To restart it** (only while FLAT -- check `settled` count >= filled `order`
count in the newest `results/pinrun-live-*.jsonl`):

```powershell
Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
  Where-Object {$_.CommandLine -like '*pinrun*'} |
  ForEach-Object { Stop-Process -Id $_.ProcessId }
Start-Process -FilePath "C:\Python314\python.exe" -ArgumentList "-u",
  "C:\kals-repo\research\pinrun.py","--live","--size","20","--minutes","4320",
  "--loss-abort","-60.00","--max-positions","3","--max-losses","3" `
  -WorkingDirectory "C:\kals-repo" -WindowStyle Hidden
```

`kauth` lives at `C:\Users\Joe\AppData\Local\Temp\kals-work` and `pinrun.py`
line ~103 puts it on `sys.path` itself, so a plain restart works.

## The numbers that matter

**Live, current version** (hedge 0.80, from 2026-09-12 2:06 PM ET) --
`python research/pinver.py` regenerates all of this:

- **35 closes, 34W 1L, net +$65.06. Close-loss rate 2.86%, CI [0.07, 14.92].**
- 48 markets, 47W 1L. Fill ratio 71.8% (we lose ~28% of races).
- Mean entry 95.6c, mean edge at signal +3.9c.

**BREAK-EVEN IS A 3.58% CLOSE-LOSS RATE.** A win pays ~3.7c, a loss costs
~96c, so one loss undoes ~26 wins. Above 3.58% the strategy loses money and
**no bank size or brake fixes that** -- the brake only sets the bleed rate.
All live history is 12 losing of 248 closes = 4.84%; the current version is
2.86%. The two straddle break-even and neither has the sample to settle it.
**This is the single most important open number in the project.**

## Settled recently -- do not re-litigate

| question | answer | where |
|---|---|---|
| Is the 10x loss-rate gap calibration or selection? | **SELECTION.** Where nobody offered, the model is nearly right (off 0.028pp); where someone did, off 0.725pp -- 26x. The counterparty is informed. | `results/RESULTS_select.md` |
| Can we sell winners before settlement? | **NO.** By 15s out a loser's bid is already 23c, 6c at 10s. Every exit cell loses money. Dead on mechanism. | `results/RESULTS_exit.md` |
| Should the depth floor be lowered/removed? | **NO.** Removing it costs 30% of the money: +15% fills, -35% mean size, -25% contracts. | `results/RESULTS_levels.md` |
| Are some coins safer? | **NO.** Spread appears 53% of the time by chance; rank correlation between halves +0.35; out of sample the rule fails non-monotonically. | `results/PREREG_coinrank.md` |
| Do S&P/Nasdaq 15-min series exist? | They exist, `fifteen_min`, `quadratic` -- and have **NEVER run a market**. Contradiction 3 closed, IDEAS.md B3 struck. | this file |
| Does "did anyone else take this offer" recover the population rule 5 says the tape cannot see? | **NO as a trading rule, PARTLY as a population filter.** The forward split is contaminated by outcome leakage (gap grows 3.2 -> 88.6 pp as the window widens 250 ms -> 60 s); the clean backward version has NO POWER (+1.27 pp, [-1.62, +4.57], MDE 4.05). | `results/RESULTS_contest.md` |
| Can we win more races by bidding above the ask? | **Probably, and it is nearly free** -- a crossing IOC fills at the RESTING price (283/283 live fills at or better than signalled, zero worse). 43% of lost races have a next level that still clears the SAME gate, median +0.20c. NOT DEPLOYED: needs the live bar. | `results/PREREG_sweep.md` |
| Is losing 28% of races a latency problem? | **NO.** Filled and zero-filled orders have identical latency (median 96 ms both). The competing take lands at a median 67 ms. We cannot out-run them; we can only cross a level. | this file |
| Trade more carefully after a loss? | **NO.** 0 of 18 closes following a loss lost (vs 2.62% baseline). Mean $ after a loss is HIGHER. A 1-close cooldown costs 6% of profit and saves nothing measurable. | this file |

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

## Hard-won gotchas that will bite again

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
python research/pinver.py                    # how is the current version doing
python research/pinbank.py --bank 234        # what size does the bank support
python research/pinlevels.py --minfill 39:1.0,0.5,0.25   # re-score, no tape walk
python research/pincontest.py --rescore --gate live      # contest split, 3 s
python research/<file>.py --selftest         # always before trusting a file
```
