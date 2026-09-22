# Verify K3-frozen-index -- CODE lens (adversarial)

Status: DONE 2026-09-22. Verdict: **CONFIRMED in code, with two corrections to the
claim; the trigger has not been seen in the live record; the proposed fix (F5) has
its trigger backwards.**

Claim under test (06_code-and-infra.md): the hedge path in research/pinrun.py never
checks the settlement index's age, so a frozen index feed while holding gives a
frozen confident belief: no alarm, no hedge, no hedge_blind record.

Own code, all under
`C:\Users\Joe\AppData\Local\Temp\claude\C--kals-repo\47b37ac1-655c-4d72-a81b-a48e9625d5bd\scratchpad\map\verify2\K3-frozen-index-code\`:
`harness.py` (imports pinrun's IndexWS/fair/hedge_should_fire; kauth stubbed, no
socket, no key, no Kalshi; peak working set 34 MB), `fixproto.py`, `logscan.py`,
`logscan2.py`. Outputs: `harness_out.txt`, `logscan_out.txt`, `logscan2_out.txt`.

## 1. Code facts (pinrun.py at HEAD 73bbb7a; file unmodified in the working tree)

- Hedge pass = lines 8961-9311. Its only index reads are `idx.sigma()` (9019),
  `fair()` (9023) and, only when HEDGE_JUMP_SIGMA is set, `idx.recent_moves()`
  (9043). Grep of 8961-9311 for `age|spot|last_rx|stale` outside comments: **zero hits**.
- `fair()` throws the age away: `_, spot, _ = idx.spot(iid)` (2729).
- `IndexWS.partial()` ends the locked window at the newest print held
  (2528 `hi = have[-1]`), so with the feed frozen at second F inside the window it
  returns the same `(sum, r = close-1-F)` every second -> belief EXACTLY constant.
- The only index-age check is on ENTRY (9617-9619, `iage > MAX_INDEX_AGE_S` = 2 s).
- `IndexWS.last_rx` is written (2272) and **never read** anywhere.
- Hedge triggers are belief < HEDGE_BELIEF (9048; live 0.25) or a jump (live start
  record `hedge_jump: null` = off). There is no trigger that reads the market price.
- `hedge_blind` (9001-9008) covers only no_hedge_meta / no_sigma / no_fair.
- Socket: `asyncio.wait_for(ws.recv(), timeout=30)` (2569). Only 30 s of silence on
  the WHOLE socket forces a reconnect. A frame from any other index resets that clock.
- Nothing else steps in: `watch_bot.ps1` restarts only after 25 min of log silence.
  The `dumped` check is an entry gate placed after the index gate, so it goes quiet too.
  The self-test (3782-3786) only checks that `spot()` reports an age.

## 2. Harness results (pinrun's own functions, live flags, synthetic index)

Every case: we hold YES, entered with a fresh index (age 0.3 s), belief 0.9918. The
"collapse" is a $9/s slide that makes YES lose. The twin is the same world with the
feed fully delivered.

| case | bot state each second | first alarm (bot / twin) | hedge_blind |
|---|---|---|---|
| CONTROL, feed fresh, collapse | quiet 7 s, ALARM 22 s | tau 22 / 22 | none |
| NULL, frozen, no collapse (YES wins) | quiet, belief 0.9918 constant | none / none | none |
| S1, one index frozen while others flow, main leg (tau 30) | quiet 29 s, belief 0.9918 constant, index age reaches 30 s | **none** / 22 | **none** |
| S1e, same, early leg (tau 45) | quiet 44 s | **none** / 35 | **none** |
| S2, whole socket silent, main leg | quiet 29 s; reconnect would come 2 s AFTER the close | **none** / 22 | **none** |
| S3, whole socket silent, early leg | quiet 31 s, then `no_fair` 13 s | **none** / 35 | **yes, at tau 13** |

All six harness assertions pass: the harness can see an alarm, the collapse really
loses, and the null stays quiet.

**Corrections to the claim.**
(a) "No hedge_blind record" is false in one case. When the whole socket goes silent
while holding an early-leg bet (tau 31-45), the 30 s timeout reconnects inside the
window. The hole this leaves fails partial()'s 95% rule, so `no_fair` IS recorded.
There is still no hedge.
(b) A related gap the claim does not name: after ANY reconnect that leaves more than 5%
of the window missing, `fair()` stays None for the rest of that close. The hedge is then
blind until settlement, even though fresh prices are arriving. That case IS recorded.
The claim's exact wording (no alarm, no hedge, no record) holds for S1, S1e and S2.

Entries cannot start from a frozen feed: the entry gate needs age <= 2 s, and every
entry is at tau <= 45 < 60. So a freeze always starts inside the averaging window,
which is the frozen-belief branch and not the `None` branch.

## 3. Has it happened live? (results/pinrun-live-*.jsonl, 124 files; n = closes)

- 776 entry fills in 550 closes (close taken from the ticker; 1 of the fills
  disagrees with `t + tau_at_send` by more than 2 s).
- `hedge_blind` records ever: **0**.
- `index_stale` looks: 11 of 1,239 closes with a close_summary. Only one of them had a
  live fill: 2026-09-21 14:45Z (10:45 AM ET). The stale looks came at 14:44:21Z,
  **before** the ZEC entry at 14:44:29Z (index age 0.14 s). The bet won +$1.14.
- Stale index while a live position was held: **0 of 545 held closes** that have a
  summary. The 95% upper bound is 3/545 = 0.55% of held closes, or 0.91% after
  correcting for 7 looks.
- This is a lower bound in one respect. A `book_stale` look (9614) comes before the
  index check, so it can hide index staleness. That happened after our entry in 28
  held closes, all on single thin-coin books, not all tickers at once. A pause or drain
  `continue` also stops the scan.
- Runs with an `end` record: 14 of 124. The index socket reconnected **0** times in any
  of them.

## 4. Worst realistic cost

A frozen index can't add exposure, because entries stop after 2 s. What it takes away
is the hedge on what is already held.
- Stake at risk in one close since 09-15: median $83.22, 90th percentile $160.64,
  max $263.12 (277 closes, up to 3 positions). All coins share one socket, so all of
  them go blind together.
- What a working hedge was worth, from the bot's own per-leg `settled` rows (18 hedged
  markets). On the 10 where our side lost, the hedge legs got back **$123.02 of
  $400.82 (31%)**. On the 7 where our side won, they cost $158.59. The lifetime net of
  all hedge legs is **-$35.57**.
- So one worst-case event, a real collapse during the freeze, costs the missed ~31%:
  about $50 at the 90th-percentile close and about $81 at the largest close. The stake
  itself is lost either way. With 0 freezes in 545 held closes, the expected cost today
  is close to $0. This is a tail-risk defect, not a current bleed.

## 5. The proposed fix (F5 in 06) has its trigger backwards

F5 says: "other side's ask below 1 - HEDGE_BELIEF -> hedge", tested with "drop the
other-side ask to 20c -> hedge fires". With HEDGE_BELIEF 0.25 that means hedging
whenever the other side is under 75c, which is every calm second of a winning bet.
`fixproto.py`, on the same worlds:
- NULL (we win): F5 fires at tau 28, buying the losing side at 4.3c. The correct rule
  does not fire.
- S1 (collapse): the correct rule fires at tau 22, other side at 89.6c, the same
  second as the fresh-feed twin.
F5's self-test would pass with the backwards rule, and its null (fresh index, calm
book) could never catch it.

**Smallest safe fix.** In the hedge pass, after `_hf`:
`_, _, _hage = idx.spot(_hiid)`. If `_hage > MAX_INDEX_AGE_S`, or if `_hf` is None:
1. Record `_hquiet("index_stale", age_s=...)` (deduped as now).
2. If the book is fresh (`age_ms <= MAX_BOOK_AGE_MS`), set
   `_belief = min(model belief or 1.0, 1 - other_side_ask)`, so it hedges when the
   other side's ask is **above** 1 - HEDGE_BELIEF.
3. With a fresh index nothing changes.

It only adds a trigger. It can't block a hedge and it can't add a bet.
Optional: a per-index watchdog on `last_rx` that resubscribes after 5 s.

Self-test, four worlds, all required:
- A. Frozen index + other-side ask 0.90 -> the hedge fires and `hedge_blind
  index_stale` is written.
- B. **Null that catches the sign:** frozen index + calm book (other-side ask 0.03)
  -> no hedge.
- C. Fresh index -> belief identical to today's code, to the bit.
- D. Reconnect hole (fair None) + ask 0.90 -> fires.

It can't be validated on live fills (0 events in 545 held closes). Validation is the
self-test plus a paper arm with a forced feed freeze.

## Cuts tried / multiple looks

Data cuts: 7 (stale overlapping a hold; close_summary stale looks in held closes;
feed-health gates after entry; end-record reconnects; hedge_blind count; stake
distribution; hedge-leg recovery). No significance claim is made. The one rate
(0 of 545) is quoted with a 7-look bound (0.91%). Harness scenarios: 6, plus 2 for the
fix prototype.
Recorders and live bot were alive after the work (pids 105304, 105352, 1985112).
Free RAM 1,862 MB, free disk 30.4 GB.
