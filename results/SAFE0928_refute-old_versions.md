# SAFE0928 -- check of the "old versions" finding (refuter)

**Verdict: the finding stands.** No older version beats today's safe bot by more than noise. One number in it is about twice too high: the safe rules skip roughly **$19 a day** of small paper winners, not $35-40.

## What I re-counted from the raw logs (my own script, not theirs)

Every headline number came out the same to the cent:

| comparison | their numbers | my count |
|---|---|---|
| 09-25 build vs today's build, insurance at 20 in 100 (paper vs paper, 42 slots since 10:48 PM ET 09-27) | +$25.43 (22 markets) vs +$7.95 (12) | same |
| same pair, no insurance | +$24.59 (22) vs +$9.85 (13) | same |
| 09-25 twin (paper) vs live (real money from Kalshi's statement), since 1:08 AM ET 09-27 | +$87.20 vs +$31.49 | same |
| twin vs live, identical settings (09-25 8:30 AM to 09-27 1:08 AM ET, restored log used) | +$66.28 vs -$3.74 | same |
| 09-20 frozen vs twin | +$13.06 | same |
| hourly-all vs twin | -$27.78 | same (ETH 2:30 AM accounts for -$24.18) |

Checked by hand:
- **Paper winners**, per contract (1 - price paid), minus the taker fee of 0.07 x price x (1 - price):
  - HYPE 1:00 AM: 91 at 98c = $1.70.
  - BTC 1:45 AM: 91 at 96.8c = $2.71.
  - ETH 12:45 AM: 91 at 97c = $2.54.
  - HYPE 11 PM: 6.66 at 98c = $0.12.
- **Live**:
  - BTC 09-27 3:15 AM: 86 at 93.1c = $5.55, matching Kalshi's statement.
  - ETH 09-27 2:30 AM: the bet won. The 88 YES cost $73.46, the 88 NO of insurance cost $44.88, and fees were $2.39, so it lost $32.73 overall. That confirms "the bet won; the insurance cost the money."
  - BTC 09-27 12:00 AM: the bet lost. It was 198 YES (two full bets), minus the insurance, for -$131.98.
- Insurance orders were left out of the entries.
- All live markets were found in Kalshi's statement.
- Nothing in the finding uses a refused market's outcome as our money. The paper money is labelled as paper.

## What is wrong or loose

1. **The cost of the safe rules is overstated about 2x.**
   - The $35-40 a day comes from a 10.5-hour overnight window stretched to a full day.
   - Over the 29 hours when all the safe rules were live (4:11 AM ET 09-27 to 9:15 AM ET 09-28), I counted the paper twin's winners on markets live refused:
     - The 97.8c price cap blocked 20 markets worth $17.21.
     - The seller check blocked 7 markets worth $6.20.
     - That is **about $19 a day**, and it is still the paper figure, so the real amount is lower.
   - So the safe rules pay for themselves if they stop **one losing 98c buy every 3-5 days**, not every 2-3 days.
2. **The breakdown of the extra markets is slightly off.**
   - The 09-25 build had 11 markets that today's build did not, plus 1 market the other way round (DOGE 12:15 AM, +$0.65). The finding said 12.
   - The "$9.18 from 9 price-cap markets" includes HYPE 9:30 AM, which falls outside the 42-slot window. Inside the window, 8 price-cap markets made $8.61.
3. **"The one-bet rule added nothing" is true in size but not literally.**
   - At BNB 11:15 PM, the 09-25 build made a second full bet at 97.1c 4 seconds after the first, worth +$0.49. Today's build did not make it, and logged a "rebuy_band" refusal.
   - The seller check would have blocked that offer anyway: 22 seconds left, a 59 ms old offer, and sellers took 51% of our side.
4. **The 09-20 frozen bot against today's settings is missing from the finding.**
   - Paper against paper, over the same 42 slots, frozen made +$28.54 and today's settings without insurance made +$9.85, a gap of +$18.70.
   - That is the same size as the 09-25 build's lead. Both are the cost side only, with zero losses on either side.

## What the sample can see

- 42 slots with zero losses cannot tell whether the safe rules stop losses. One $50-130 loss would flip every paper comparison here.
- Paper against live swings by $20-70 on a single market.
- Split into halves (09-09..09-17 / 09-18..09-28): not possible, because every bot involved started 09-25 or later.
- 11 pairs were compared and none clears noise, so no multiple-looks correction changes the verdict.

## Recommendation check

"No change to the live bot" cannot block an insurance buy. Insurance stays at 0.40. None of the five 09-28 bots has had an alarm, so the insurance-level question has no data yet. The twin had 4 alarms on 15-minute markets in 3.1 days, about 1.3 a day, as the finding says.

Collector and crypto_feeds are alive (44 MB and 26 MB). Free disk is 61.5 GB. Scripts are in `scratchpad\safe0928\refute-old_versions\`: chk.py, rate.py and hdr.py. chk.py self-tests with a planted answer, with an insurance order that must be left out, and with an empty world.
