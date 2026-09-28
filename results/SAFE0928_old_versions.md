# SAFE0928 old_versions: would an older version be doing better right now?

Written 2026-09-28 about 10:30 AM ET by a read-only agent. Times are ET. "Paper" means a practice bot with no money in it. Live money comes from Kalshi's own statement, which runs to 9:15 AM ET today. Paper bots count every offer they see as bought, so they always look better than real money.

## Answer, reason first

**No older version is clearly ahead of today's safe bot once you take away the paper advantage. The 09-25 version (no seller check, buys up to 98c, second bets allowed) is ahead on paper by about $15-17 in 10.5 hours. That is 10 to 12 extra small wins. It comes mostly from buying at 97.9-98c, which today's bot refuses, plus 2 markets the seller check blocked. None of those skipped buys lost on paper. But paper cannot see the losing buys that the seller check and the 98c cap exist to stop, so this is the cost side only.**

1. **The fair test (paper against paper, same markets, since 10:48 PM ET last night, 42 fifteen-minute slots).** I paired bots that are the same in everything except the three new safety rules:
   - With insurance at 20 in 100: the 09-25 version made +$25.43 on 22 markets. Today's settings made +$7.95 on 12 markets. **The 09-25 version is ahead by $17.48.**
   - With no insurance: 09-25 version +$24.59 on 22 markets, today's +$9.85 on 13. **Ahead by $14.74.**
   - Neither side lost a single market, so this is all "extra winners".
2. **Why today's bot skipped them.** Of the 12 markets only the 09-25 version bought, 9 were buys at 97.9-98c that the new 97.8c price cap refuses. Together they made $9.18, about $1 each. One (ETH 12:45 AM, +$2.54) was a 97c buy. Today's bot did not get that same offer; its refusals on that market were the price cap and the confidence check. The other 2 (BTC 1:45 AM, +$2.71; XRP 3:15 AM, +$1.89) were blocked by the seller check. The one-bet rule cost nothing extra on its own: the two markets where the 09-25 bot made a second full bet (NEAR 4:00 AM, ZEC 8:00 AM) were at 97.9c, so the price cap already blocked them.
3. **What that means in dollars.** About $35-40 a day on paper at this morning's pace (my arithmetic from 10.5 hours). Real money would be less, because paper fills every offer. The trade-off is simple: one 98c buy that loses costs about $50-90. That is roughly as much as 50-90 of these winners. **The cap and the seller check pay for themselves if they stop one bad buy every 2-3 days.** This sample cannot tell whether they do. No loss has happened since they started.
4. **Paper against real, since the seller check went live (1:08 AM ET 09-27, 128 slots).** The 09-25 twin made +$87.20 on paper. Live made +$31.49 of real money. The gap is $55.72. When the two ran IDENTICAL settings (09-25 8:30 AM to 09-27 1:00 AM, 163 slots), paper still beat real money by $70.02. That works out to about $55 over 128 slots. **So all of the $56 gap is the usual paper advantage, and none of it shows the safe settings costing real money.** Without the three biggest single markets, the gap is $24.95 against about $25 expected. This measurement is noisy (one market can move it $20-70), so it does not contradict the $35-40 a day in point 3. It just cannot see a gap that size.

## Every bot since the seller check went live (1:08 AM ET 09-27), 15-minute markets

Paper numbers are paper. The paper loss counts come from offers on the book, so they are never our loss rate.

| bot | what it is | markets | won | lost | money | 09-27 | 09-28 (to ~9:15 AM) |
|---|---|---|---|---|---|---|---|
| **live (real)** | today's safe settings (price cap from 3:05 AM, one-bet from 4:11 AM) | 35 | 34 | 1 | **+$31.49** | 29 mkts +$22.76 | 6 mkts +$8.73 |
| arm-btcd (paper) | exact 09-25 live settings | 65 | 64 | 1 | +$88.26 | 45 mkts +$64.59 | 20 mkts +$23.67 |
| arm-live-frozen (paper) | the 09-20 settings | 68 | 67 | 1 | +$101.32 | 48 +$75.21 | 20 +$26.11 |
| arm-early-full (paper) | 09-25 + full-size 45-second buy | 37 | 37 | 0 | +$73.50 | 25 +$57.52 | 12 +$15.97 |
| arm-early-off (paper) | 09-25 without the 45-second buy | 41 | 41 | 0 | +$89.32 | 28 +$70.88 | 13 +$18.44 |
| arm-lateadd-off (paper) | 09-25 without the late add | 68 | 67 | 1 | +$82.44 | 48 +$57.68 | 20 +$24.76 |

The one loss was the same market for everyone: ETH 09-27 2:30 AM. It was live -$32.73, frozen -$18.11, twin -$12.28, lateadd-off -$10.99. The bet won, and the loss was the insurance. That was before the price cap and one-bet went live, and the seller check did not stop it.

## Head to head against the 09-25 twin (paper against paper, same markets)

| bot vs the 09-25 twin | since 1:08 AM 09-27 (about 128 slots) | since 10:48 PM 09-27 (42 slots) |
|---|---|---|
| 09-20 frozen | **+$13.06** | +$0.99 |
| early buy at full size | -$6.31 | -$7.11 |
| early buy off | +$2.12 | -$5.41 |
| late add off | -$5.82 | +$1.09 |
| 09-25 build relaunched last night (same settings as the twin) | -- | -$1.62 |
| hourly-all (same 15-minute settings as the twin, so a noise check) | -$27.78 | +$4.45 |

**How big a gap counts as real:** the hourly-all bot runs the same 15-minute rules as the twin, yet it trails by $27.78. All of that is one market (ETH 2:30 AM: -$36.46 against -$12.28). The two identical 09-25 bots differ by only $1.62 in 42 slots. So a gap needs to beat about $30 in a day, or survive removing its top 3 markets, before it means anything. **Nothing above passes that test.** The 09-20 frozen bot's big lead (+$107 over 2.7 days, see Q0928_frozen) came almost entirely on 09-26. Since then it is +$13 in 1.2 days. Q0928_frozen already showed that most of its lead is the 90c early floor and one lucky BNB skip.

## Insurance level: which is ahead?

**Too early. No insurance has been bought by any of the five 09-28 bots.** None of them has had an alarm in 10.5 hours. The small gaps (0.40 against 0.20 against none: +$0.51, +$1.35, +$0.85) come from bots seeing the book a split second apart, not from insurance. The 09-25 twin had 5 alarms in 3.1 days (4 on 15-minute markets), so about 1.3 a day. Comparing insurance levels needs about 10 alarms, which is around **10-06**. The pre-registered hedge-margin read (PREREG_hedge_margin) is not before **10-10**. Until then the insurance comparison is empty.

## What is too early, and when it will not be

- **The cost of the safe rules (winners skipped):** about $15-17 per 10.5 hours on paper so far. Paper against paper does not flatter either side, so by **10-01** (about 300 slots) this number will be steady.
- **Whether the safe rules are worth that cost:** it depends entirely on losses they stop, and paper cannot see those losses. It needs live evidence. The PREREG_toxic read is **10-01**, on live fills. For the 98c cap, the question is whether real 97.9-98c buys lose more than about 2 times in 100 (the break-even at 98c). That needs about 150+ real buys at 97.9-98c from the old logs, not these arms.
- **The old early-buy and late-add variations:** all within noise. arm-early-full reads 10-04. early-off and lateadd-off read about 10-01.
- **Half-split (09-09..09-17 vs 09-18..09-28):** does not apply. Every bot compared here started 09-25 or later.

## Method

- Clustered by 15-minute close. "Shared" means a close both bots were running for (their close records). Only markets settled for both bots are counted. Hourly BTC is left out of the head-to-heads because it is under $1.50 either way everywhere.
- The live money figures are Kalshi's statement (payout minus costs minus fees): 127 of 127 live markets matched, and none fell back to the log. Hedge orders are removed from live entries by their order id.
- Arms by log: btcd 20260925T122556Z, frozen 20260925T063011Z, early-full 20260927T080949Z, early-off 20260925T122541Z, lateadd-off 20260925T122549Z, hourly-all 20260925T122606Z, the five 09-28 arms 20260928T0247xxZ (in manifest order). I checked each against its arm-*.out file.
- The paper arms started before 09-27 were never updated to today's settings. They are "09-25 settings plus one change". That is why they are compared to the 09-25 twin and not to live.
- Scripts are in the scratchpad `safe0928/old_versions/` (arms.py, why.py). Each self-tests with a planted answer and an empty world, and both passed before the real run.
- Machine: the collector (pid 2532788) and crypto_feeds (pid 105352) are alive, and 61.6 GB of disk is free. I ran one process at a time, stopped nothing, placed no orders and wrote nothing under C:\kals.
