# PRE-REGISTRATION -- BUY EARLIER: TAU_MAX 30 -> 45
## Written 2026-09-17 ~00:10 ET, BEFORE the tau-45 arm's log was opened

**Rule:** no threshold is deployed from a replay without a holdout split AND a
pre-registered live bar written before the number is seen (CLAUDE.md amendment
2026-09-10, item 4). This file states the bar first. **Nothing is deployed.**

The arm under test is the paper bot started 2026-09-17 02:01:47Z (pid 478072,
log `results/pinrun-paper-20260917T020147Z.jsonl`, live's flags plus
`--tau-max 45`). Its control is the paper bot started 2026-09-16 20:46:02Z
(pid 411820, log `results/pinrun-paper-20260916T204602Z.jsonl`, live's exact
flags, tau 30). **Neither log's settled records were read before this file was
written.** The control log was opened once, for its record LAYOUT only (a
`signal` record carries `ticker` and `tau`; a `settled` record carries `ticker`,
`result`, `pnl_c`; the two join on `ticker`).

## The change being proposed

`pinrun.py` `TAU_MAX = 30`: the bot will not buy with more than 30 seconds left.
The proposal is 45. Nothing else moves -- PIN 0.995, ceiling 98c, edge floor
0.3c, EV floor 0.3c, the dump guard, the jump gate, the hedge, the size rule.

Note the mechanics: `pinrun --live` REFUSES `--tau-max` above the constant
(line ~6376, "refusing to go live outside the pre-registered cell"). Deploying
is therefore a code edit to the constant plus a commit, not a flag in
`restart_bot.ps1`. That is deliberate and stays.

## What is known, and from where

`research/pinbefore.py`, `results/RESULTS_pinbefore.md` -- the INDEX FEED
alone, no replay: 14,261 settled closes, ~730,000 moments, at the live bar
(model >= 99.5% sure):

| seconds left | moments | model wrong | real risk |
|---|---|---|---|
| 21-30 (today) | 131,752 | 28 | 0.021% |
| **31-45** | **183,936** | **107** | **0.058%** (2.8x) |
| 46-60 | 164,994 | 153 | 0.093% (4.4x) |

Tightening the bar does not close the gap (2.9x at 99.9%, 2.3x at 99.99%).
The extra model risk is inherent to the horizon.

The old wall in the `TAU_MAX` comment ("7,302 moments, 25 flips, 3.7x
overconfident ... do NOT extend past 30") was measured on the order-book
dataset at a 2% bar. pinbefore is 25x the sample at the bar we actually use
and supersedes it. If this deploys, that comment is rewritten to cite
pinbefore; it is not silently contradicted.

**Why model error is not the question.** Live loses 4.66% of closes (21 of
451, all time). Model error at 21-30s is 0.021%. Tripling it moves the
expected loss rate from 4.66% to about 4.70%. Our losses are ADVERSE
SELECTION -- someone sold to us because they knew -- and whether that is worse
with 45 seconds left is something the index cannot see.

**The prize:** 40% more moments at the bar, and the book is deepest at 28-30s
(median 105 on offer against 29 at 23-27s), which suggests it is deeper still
further out. That matters because the ceiling on this strategy is liquidity,
not capital (`pinfill.py`, `pinproject.py`).

## THE RISK THIS ARM CANNOT MEASURE, STATED BEFORE THE BAR

A paper arm records "an offer was sitting there at a price that passed the
gate". Our live population is "someone actively sold it to us". Those differ
by 31x in loss rate on the record (tape 0.11% vs live 3.4%, 2026-09-11,
intervals not overlapping) and the difference IS the loss class that hurts
us. **So the paper arm can KILL this idea; it cannot DEPLOY it.** A paper pass
earns a live test with its own bar (stage 2), nothing more.

The specific worry: with 45 seconds left the index has 15 more seconds in
which to move, and an informed seller at 40s has more room than one at 25s.
If sellers at 31-45s are more often informed, the new population loses more
than 4.66% and the change is net negative however many extra fills it adds.
One loss costs about 9 wins at today's prices.

## STAGE 1 -- the paper arm against its CONTROL. Pass/fail, fixed now.

**Comparison is arm vs control, never arm vs live.** A paper-vs-live gap
exists on its own and the control is what measures it.

**Populations, defined by the `tau` on the arm's `signal` record, joined to
`settled` by `ticker`:**

- **NEW:** markets the arm bought where EVERY signal for that ticker had
  `tau >= 31`, and the control never signalled that ticker. These are trades
  that only exist because of the change.
- **SHIFTED:** markets both arms bought. Here the arm may have bought earlier
  at a different price. Compared per market on price paid and outcome.
- **SAME:** the arm's fills at `tau <= 30`. These should match control and
  are a sanity check that the arm is otherwise identical, not a result.

**Minimum before anything is read:** 30 settled closes in EACH arm, and at
least 20 markets in NEW. Until both hold, nobody opens the arm's numbers.

**Kill (the idea is closed, the arm is stopped):**

1. NEW has lost **3 or more of its first 30 markets** (10%), at any point.
2. NEW is net negative in dollars at 30 markets.
3. SHIFTED: the arm paid more than control on the same market by a mean of
   over 1.0c per contract. Buying earlier is then buying worse, and the extra
   fills do not pay for that.

**Proceed to stage 2 (a live test, NOT a deployment):**

1. NEW: at most 1 loss in its first 30 markets, and net positive.
2. NEW adds at least 20% to the control's close count over the same window.
   If the moments do not turn into trades, there is nothing to deploy.
3. SAME matches control's fills at tau <= 30 within noise (same tickers on at
   least 80% of shared closes). If it does not, the arm is not the control
   plus one flag and its result means nothing.

Anything between kill and proceed: keep both arms running to 60 closes and
re-read at the same bars. No threshold is moved to make it pass.

## STAGE 2 -- the LIVE bar, decided before the first tau-31-45 fill

Only after stage 1 proceeds. `TAU_MAX` edited to 45, committed, `v-tau45`
written in `results/VERSIONS.md` at the moment of restart with the exact
revert (the git SHA to check out and the restart command), and
`python research/versioncheck.py` passing.

Scored over the first **40 live CLOSES with at least one fill whose signal
`tau` is 31-45** (rule 4: closes, not fills), those fills tagged in the live
log by their signal record:

1. **Loss rate on those closes <= 8.0%.** All-time live is 4.66% and the
   most conservative break-even on our own settled closes is 8.55%
   (CURRENT_STATE.md). At 4 losses in the first 40 closes, or 3 in the first
   20, revert immediately -- do not wait for the count to finish.
2. **Net positive in dollars on those closes at 40.**
3. **Mean price paid on 31-45 fills within 1.0c of the mean on 21-30 fills
   over the same window.** If earlier means dearer, the volume is not free.
4. **Fill size on 31-45 fills at least equal to 21-30 fills** (median
   contracts per fill). The depth argument is half the case; if it is false
   the case is half as strong and this is recorded whether or not it passes.

**If bar 1 fails, the change is reverted and this file records that it
failed.** Bars 3-4 failing means the mechanism is not what this file claims;
revert and re-examine before any second attempt.

## Kill criterion for the idea itself

If after 40 live closes the 31-45 population's loss rate is indistinguishable
from the 21-30 population's AND the extra money is under $3/day at the size
then in force, the change stays but the idea is closed: no 46-60, no further
work on horizon. The handoff is explicit that 46-60 is a separate question
(4.4x model risk, not 2.8x) and is not to be skipped to.

## What is NOT being proposed

- No change to PIN, the ceiling, the edge floor, the EV floor, the dump guard,
  the jump gate, MAX_PER_CLOSE, BANK_BRAKE, the hedge, or size.
- No `--tau-max` above 45, and no removal of the live refusal at line ~6376.
- Not the tau-dependent variant (31-45 only at >= 99.9% and a depth floor).
  That is a candidate THIRD paper arm and would need its own bar; it is not
  started and this file does not cover it.

## Numbers in this file that came from somewhere other than the index feed

Live loss rate 4.66% and break-even 8.55%: our own settled closes
(`pinver.py`, CURRENT_STATE.md). The 31x paper-vs-live gap: 2026-09-11 live
fills vs tape (CLAUDE.md amendment 2026-09-10, item 5). Book depth by tau:
`pinbefore` section on the ladder, live signal records. Nothing here is from
`pinsim` or the replay.
