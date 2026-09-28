# SAFE0928 refute: floor90 (checked 2026-09-28)

**Verdict: the recommendation stands (90c floor, a third of a bet, auto-revert). But the count behind it is wrong: it left out 6 of our own fills, all winners.** Put back, the case gets slightly stronger on how often we lose and slightly weaker on how much each win pays. Two other errors: the times in section 2 are an hour off, and the offer rate is understated.

## What I re-ran myself (live logs since 09-09, the restored 09-25 12:23Z log included, hedge orders excluded, Kalshi ledger for money)

| claim | my re-run | status |
|---|---|---|
| BTC 9/19 2:00 AM: saw 94.3c, paid 94.4c, 70 contracts, 35 s left, NO side, market went YES, -$66.34 | same, from the order record and the ledger | confirmed |
| NEAR 9/21 12:45 PM: saw 95.5c, paid 91.1c, 81 contracts, lost; -$59.09 on the market after insurance | same | confirmed. A 95c floor lets it through |
| The floor checks the price SEEN | `pinrun.py` line 18943: `price < EARLY_MIN_PRICE` on the touch price, before the order is sent | confirmed |
| Only one 45-second loss ever came from a 90-95c ask | across all 375 of our 45-second fills since 09-09: every fill with a 90-95c ask won except BTC 9/19. None before 9/18 | confirmed |
| Seller gate would block BTC 9/19 | offer age 59 thousandths of a second (the bot's own log). ETH 9/19 was 54, ZEC 9/20 33, BTC 9/22 386: all under the 500 line. NEAR 9/21: 75, BTC 9/19 11:00 AM: 929 (passes) | ages confirmed. The seller shares (72 in 100 etc.) were rebuilt from the tape, and I did NOT redo that |
| 14 offers turned away at 90-95c since 9/23 10:22 PM, within the 10c cap, all won | 14. XRP comes from the ledger. The other 13 come from the paper bots' own settled records: 13 of 13 won | confirmed, with a second source |
| All 10 at 85-90c are over the 10c cap | 10 of 10 (edge 11.0 to 15.0c). 2 of the 10 are hourly-BTC 1-contract markets | confirmed |
| Paper floor bots: 0 buys under 95c, 0 lost | now 11-12 settled each, 0 lost, 0 45-second entries under 95c | confirmed. Still no answer |
| The change cannot block a hedge | a flag value only. The hedge pass sits above the entry gates. `restart_bot.ps1` line 174 holds `"--early-min-price", "0.95"` | confirmed |

## Errors found

1. **"1 loss in 11 fills" is really 1 in 17 (6 in 100; the true rate could be anywhere from 0.2 to 29 in 100).** The finding says it sorts by the price SEEN. But its table dropped every fill where the ask seen was under 95c and the price paid was 95c or more. There are 6 of those, all won, all inside the 90c-floor window. A 95c floor would have refused every one of them:
   - ETH 9/19 8:30 AM (saw 94.9, paid 95.8, +$4.28)
   - ZEC 9/20 10:30 AM (94.9 / 96.3, +$2.53)
   - XRP 9/22 2:30 AM (90.9 / 95.6, +$3.20)
   - BTC 9/22 9:00 AM (94.5 / 95.2, +$2.16)
   - ZEC 9/23 12:30 AM (93.9 / 96.4, +$4.15)
   - BTC 9/23 1:00 AM (91.1 / 97.8, +$0.56)

   (DOGE 9/18 2:30 AM, 92.0 seen, paid 97.8c, won, is from before the floor, like the ETH 9/18 fill the table already includes.)
   - **As traded: -$4.68, not -$21.56.**
   - **At a third: about +$9.5, not +$2.78.**
2. **Each win pays less than +$1.85.** These 6 paid 95.2 to 97.8c, so at a third each makes $0.65 to $1.41. Mixed in, the average win drops to about $1.6. Break-even moves from about 9 losses in 100 to about 7.5 in 100 (insured). The finding's "+$2 to +$4 a day" is still about right, because of error 3.
3. **Offer rate: 2.8 a day, not 1.7.** That is 16 fills with a 90-95c ask over the 5.8 days of the 90c floor.
4. **Every time in section 2 (the turned-away list) is 1 hour early.** This is the daylight-time bug the report says it fixed. It was not fixed there. For example, "XRP 9/24 3:30 PM" is 4:30 PM, "BTC 9/24 11:00 PM" is 9/25 12:00 AM, and the three 90-93c ones are SOL 9/26 10:45 AM, BTC 9/26 11:00 AM and BTC 9/27 3:30 AM. The counts and results are unaffected.

## Sample, halves, looks
- All the evidence is in the second half (09-18..09-28). The first half never offered the band, because there was no floor and no fill with a 90-95c ask before 9/17.
- 1 loss in 17 cannot tell 3 in 100 from 12 in 100.
- The finding compared 5 floors plus one side pattern (the "paid 3c under the seen price" split, which I confirmed at 9 fills, 3 lost). Treat that pattern as a lead, not a result.
- The "0 of 21 with the refused offers" line mixes offers we took with offers we never got. It is labelled as a floor, but it should not be read as a loss rate. Otherwise nothing tape-based is shown as our money.

Recorders not touched. Script: scratchpad `safe0928/refute-floor90/r1.py` (self-test: planted fills with a hedge order excluded, plus an empty world).
