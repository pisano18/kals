# PortWatch Tuesday 2026-10-06 -- read of READS_DUE `portwatch-1006` (SJ04, IDEA_LEDGER U13)

Read 2026-10-06 ~15:50Z from `results/portwatch-rec-20261006.jsonl` (recorder `research/sweep/portwatch_rec.py`,
pid 661868, 10:50:10Z..13:31:05Z; polling 11:30..13:30Z). Settlement from `GET /markets/{ticker}` (kauth), 15:45Z.
Read-only; no orders; no tape loads. Scratch scripts: session scratchpad `pw_read.py`, `pw_read2.py`.

## Verdict: DEAD -- bar 2 fails. Kill number: 1 market (needs >= 3).

| bar (pre-registered 2026-10-02, verbatim in READS_DUE) | measured | result |
|---|---|---|
| layer complete-and-stable <= first informed trade +10 s on >= 3 chokepoints | all 4 complete at 12:09:02.787Z (layer stamp 12:09:01Z); informed sweep began 12:08:54.7-12:08:55.3Z -> lag +7.5 s (Hormuz +8.1 s); stable after | PASS (4 of 4) |
| >= $20 true-side asks <= 95c resting 5 s after completion on >= 3 markets | 1 market (KXHORMUZPEAK-26OCT04-T6 NO, 1,312 contracts at 95c = $1,246.82) | **FAIL** |
| post-stamp pot (others' fills from layer-complete on) >= $300 | $28,674.98 all fills to the 13:00Z close; $20,335.96 on the true side | PASS |

## Per chokepoint

All four completed in the same layer edit (stamp `2026-10-06T12:09:01Z`), first seen by the poller at 12:09:02.787Z.

| | week (Sep 28..Oct 4) | sum | true-side $ <=95c +0 s / +5 s / +30 s | markets >= $20 +0/+5/+30 |
|---|---|---|---|---|
| Suez | 28 40 45 55 42 46 46 | 302 | $0 / $0 / $61.75 | 0 / 0 / 1 |
| Panama | 30 28 25 24 28 26 29 | 190 | $294.50 / $0 / $182.00 | 1 / 0 / 1 |
| Bab el-Mandeb | 30 37 22 28 26 30 34 | 207 | $0 / $0 / $71.49 | 0 / 0 / 2 |
| Hormuz (32 mkts incl. MAX/PEAK/MAXSHIPS/NORM) | 4 1 4 0 4 2 4 | 19 | $1,246.82 / $1,246.82 / $1,266.01 | 1 / 1 / 1 |

- +0 s: Panama T200 NO $294.50 at 95c (gone by +5 s, filled 12:09:07Z); Hormuz PEAK-T6 NO $1,246.82 at 95c (sat
  until 12:10:15Z, 72 s). Weekly-sum markets (the only ones the refuter's rider allows live) at +5 s: **0**.
- +30 s: the books refilled at 91-95c (Suez T270, Panama T200, BaB T200/T175) -- 5 markets >= $20, but the bar is +5 s.

**Stable.** One `layer_change` event, the arrival (28 new values, 0 modified). Every successful poll after completion
(2,269 to 13:30Z; 43 failed) showed 7/7/7/7 rows and the same edit stamp.

**First informed trade.** The recorder's `first_true_side_trade` field counts any true-side trade since 10:50Z, so it
marks ordinary earlier trades (Panama 11:08Z, Hormuz 10:57Z, BaB 12:07Z) -- not informed. The informed trade is the
sweep that hit all four chokepoints within 3 ms at 12:08:55.31Z (first print 12:08:54.714Z Hormuz T20 NO; Suez T300
YES bought 23c->50c, sum 302 vs 300): in the 15 s before completion $14,457 traded ($14,020 true side). It came ~6 s BEFORE
the layer's own edit stamp, so even a perfect poller of this layer is behind it. Read literally on the recorder's
field, bar 1 passes on Suez only; it does not change the verdict (bar 2 fails either way).
First true-side trades after completion: Panama +3.8 s, BaB +12.8 s, Suez +12.8 s, Hormuz +39.8 s.

**Pot detail.** First 5 s $1,233; 30 s $3,469 true side; 300 s $14,570. Most is 98-99c buys; true-side fills at <= 95c
after completion cost $2,795 and earned the takers $517.

## True side vs settlement (39 markets closing 13:00Z)

- 32 yes/no markets (11 Hormuz weekly, 5 Suez, 5 Panama, 5 BaB, 6 Hormuz PEAK): recorder side right on **32 of 32**.
- 7 HORMUZMAX settled `scalar`: the 4 tied days (Sep 28, Sep 30, Oct 2, Oct 4, all 4 ships) paid **$0.25** each; the 3
  the recorder called NO (Sep 29, Oct 1, Oct 3) paid $0.00 -- right. Ties split the dollar 4 ways (now known; the rule
  text did not say).
- Total: 35 of 35 decided calls right, 0 wrong; 4 'unknown' by design.

## What the recording missed

- **Poller rate-limited.** ArcGIS refused 413 of 3,474 polls with HTTP 429 ("6000 request units per minute" quota),
  plus 3 timeouts and 1 502 -- including 65 in a row 12:06:53-12:09:00Z; last good poll before completion 12:06:51Z
  (0 rows). The completion time is therefore the first good poll after the gap; the layer's own stamp (12:09:01Z)
  bounds the error to ~1.8 s. The 2-s cadence exceeds the quota and must be slower in any rerun.
- Nothing else: the layer completed inside the window, 47 of 47 books had snapshots, 0 sequence gaps, 423 trades.
