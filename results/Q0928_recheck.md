# Q0928 recheck -- did the missing 19 hours of live log make us act on false data?

**Answer: no. No live change rested on the missing hours in a way that flips it.** The hours that were missing were the bot's best stretch of week 2. It traded 47 markets, lost none, bought no insurance and made +$92.90. Numbers that left them out made the gates look slightly better than they are, by $14-24 over 19 days. None of those gates changes sign. One tracker was badly wrong while the file was damaged: `bars.py`, the fresh-offer test. It hid the -$131.98 BTC loss and showed 0 losers and +$33. Restored, it shows 1 loser and -$29. No decision was taken on the wrong reading, because it said "too early" both times.

The damage: `results/pinrun-live-20260925T122357Z.jsonl` lost its first 9,972 lines. Those lines cover 09-25 8:23 AM ET to 09-26 3:30 AM ET. They were gone from disk from 09-26 3:31 AM ET until about 09-27 11:45 PM ET, and were restored in commit 43516ac. Scripts that read every log saw the file without its first 19 hours. `bars.py` skips any log with no start record, so for it the whole file was gone: 09-25 8:23 AM to 09-27 1:08 AM ET, 41 hours, including the BTC loss. A second file, `...20260925T093648Z` (09-25 5:36-8:23 AM ET, 5 markets, all won, +$5.01), was deleted from disk until 09-27 1:09 AM ET.

Source for everything below: Kalshi's ledger (money per market) and our own live fills. No replay was used and no tape loss rate is quoted. Script: `scratchpad\q0928\recheck\recheck.py`. Its self-test passed 11 of 11 checks, including a planted world and an empty world.

## 1. Every report and decision from the damaged window

| report / live change (written, ET) | where its log numbers came from | saw the 19 h? | re-run on the restored log | decision changes? |
|---|---|---|---|---|
| WHY_NO_MONEY (09-27 3:58 AM) | Money from the ledger. The size, 98c-band, one-full-bet, loss and calibration angles read a copy of the missing lines taken from git | yes | Its insurance and when-money angles read disk only. The 19 h had no insurance, no alarms and no losses, so they missed nothing | no |
| RULESET (09-27 2:03 AM) | read the git copy (`rs\combined\gitlogs`) | yes | nothing to redo | no |
| POSTMORTEM seller gate (v-toxic-live valuation, 09-27 1:51 AM) | disk only; the report says so | no | The gap holds 16 winning markets the gate would have refused (+$13.85 of winners given up). **+$401 over 17.7 days becomes about +$387, or $22 a day instead of $23.** The quiet first half (-$66) is unchanged, because the gap is in week 2 | no |
| v-toxic-live (staged 09-27 12:49 AM) | the 09-27 BTC loss plus arm-toxic refusing it; both in the part that was on disk | n/a | unchanged | no |
| v-ceiling978, the "98c band" figures in VERSIONS (09-27 2:57 AM): 301 markets, 5 lost, -$5.38 | Almost certainly disk only. Its 917-market count matches the damaged view, not the 970 the ledger has (an inference: the script was not saved) | no | The gap adds **28 more 98c-band markets, all won, +$24**. The band now reads **5 lost in 345 markets = 1.45 in 100** (was 1.58 in 100 on the damaged log). Break-even at 98c is 2.0 in 100. Own-leg money over 19 days is **+$30** (was +$6 on the damaged log): about $1.60 a day for a third of all contracts bought. WHY's +$77 for the ceiling already saw the 19 h | no. "About $0 of income for a third of the risk" still holds. But on a day with no loss the ceiling gives up about $22 of winners: $44 over 09-25/26, on 52 markets |
| v-onefull (09-27 4:11 AM) | WHY's size angle, which read the git copy | yes | The 19 h hold one true same-second double bet: SOL 09-25 10:14 AM ET, 178 contracts, won +$4.16. It is already in the "7 winners given up" | no |
| v-race10 / v-race20 | coin-race money from the ledger (separate bot, separate log) | n/a | Ledger: no losing race leg since 09-24 (09-24..27: 69 legs, +$12.11) | no |
| PERCAP_AND_FULLSIZE (09-27 11:37 PM) | knew about the hole; filled 19 big bets in from the ledger | filled in | The restored log shows 47 markets, all won, $0 of insurance, so its fill-in was right | no |
| LATE_PRINTS (09-27 6:45 PM) | disk only | no | 6 more entries on index prints over 1 s old, all won. That lowers the loss rate it measured, so "no rule" stands | no |
| ROUNDING_LEAD (09-27 6:45 PM) | disk only | no | The one rounding flip inside the window (BNB 09-25 3:45 PM ET) was checked: we held nothing. The log shows only confidence / no-offer refusals | no |
| PHOTOFINISH / PREREG_hedge_margin | disk only | no | The gap had no insurance buys and no alarms, so the insurance tables are unaffected. The entry table missed 47 winning markets | no |
| **bars.py fresh-offer test (arm-fresh500)** | skipped the whole file (no start record) | **no, 41 h** | On 09-27 3:48 AM it showed **31 fresh fills, 0 lost, +$32.87**. Restored: **87 fresh fills, 86 won, 1 lost (BTC 09-27 12:00 AM ET, -$131.98), net -$28.80**. The money half of DEPLOY (net at most +$25) is now met; it needs one more fresh loser by 10-01 4:08 AM ET | no action was taken on the wrong read (TOO EARLY both times) |
| bars.py arm vs live | same | no | arm-live-frozen went from 1 shared market to 114 | see section 3 |

## 2. What the invisible 19 hours held (09-25 8:23 AM to 09-26 3:30 AM ET)

- **47 markets, 60 filled entries, 0 losses, 0 insurance buys, 0 alarms, +$92.90** (ledger). Ledger by ET day: 09-25 +$107.18, 09-26 +$46.54 (15-minute crypto only).
- **42 of every 100 dollars came from two cheap late buys:** DOGE 09-25 3:29 PM ET, 135 contracts at 87c with 3 s left (+$16.48), and BTC 09-25 10:44 PM ET, 141 contracts at 83-84c with 12 and 9 s left (+$22.14). The 97.8c ceiling does not touch buys like these.
- **The first 19 hours of v-scalein-caps were never looked at.** It went live at 8:23 AM ET 09-25, the same second the gap starts. It fired once (SOL 09-25 10:14 AM ET). It worked as designed and capped the second order at 97.5c, but the position still doubled to 178 contracts. v-onefull now blocks that.
- **New, small: a position can end up above one bet without a double bet.** BTC 09-26 3:29 AM ET: the first order filled only 45 of 97. The follow-up saw 23 contracts at 97.8c, but the sweep widened it to 68 at a 98c limit, so the market held **113 contracts against a bet size of 97 (16% over)**. The same pattern shows at BNB 09-25 6:44 AM ET: **115 against 88 (31% over)**, in the other file that was deleted. v-onefull does not cover this, because the first piece was not a full bet. Both markets won. I have not checked whether today's code still allows it. The cost if one loses is about 16-31% on top of a normal loss (~$15-28 at today's size).
- Nothing else unusual: the refusals were the usual mix (no offer 723, edge 391, 98c limit 188, confidence 145), plus one 1-contract hourly BTC buy (v-btcd1).

## 3. Still wrong right now

- **bars.py's arm-vs-live lines still mix four arms.** Its 01:23 AM ET output gives arm-fresh500 and arm-lateadd-off the same numbers (326 markets, arm +$264.33 vs live +$139.44). That is TEST_AUDIT cause (2), which is still unfixed. Do not read those lines. Use the paper-against-twin method in TEST_AUDIT.
- **Nothing warns when a live log goes missing.** A daily check of ledger crypto markets against logged markets would have caught this within a day: 09-25 showed **50 markets on the ledger, 15 in the logs**, and 09-26 showed 49 and 37. After the restore every crypto day matches, except three 1-contract probes (09-12, 09-15). The cause was git rewriting tracked live logs (the rebase trap), which also wiped arm-live-frozen's first run.
- Not caused by the gap, but relevant to the 09-09..09-18 question: the ledger's 09-17 and 09-18 also hold **47 oil and gold 15-minute markets, -$84.12 together**, that no pinrun log has. They belong to the commodity bot. Any "money by day" that mixes them in is not the crypto bot's money.

## 4. A lead the restored log shows (not caused by the gap, not a result)

Refusing every entry on a fresh offer (under 0.5 s old, more than 20 s left) would have removed **9 of week 2's 10 losing markets** (-$755 of losses), against $325 of winners given up (232 winning markets). In week 1 it removed 2 of 11 losers ($38) and gave up $173 of winners, a net of -$136. This rule was written after seeing the losses, and week 1 goes the wrong way, which is the same pattern as every loser-finder so far. Also, fresh-offer buys went from 15 in 100 of week-1 winners to 45 in 100 in week 2. The honest read is the pre-registered arm-fresh500 bar on 10-01. That bar now stands at 1 loser and -$28.80.

## What the sample can and cannot say

The 19 hours hold 47 markets and 0 losses. They can move idle-cost numbers, meaning winners a gate gives up, and the counts above. They cannot say anything about loss rates: a gap that averages 1 loss per 40 markets will often show 0 in 47. Rule values are measured by removing our own trades. Insurance is shared out in proportion to contracts removed. That is an approximation, and it is why my ceiling total including insurance does not match VERSIONS' "-$76 with insurance"; the own-leg comparison above does not depend on it. Recorders were alive after the job (kalshi_collector pid 2532788, 42 MB; crypto_feeds pid 105352, 26 MB). Free disk: 63.7 GB. Nothing was written under `C:\kals`, and no orders were sent.
