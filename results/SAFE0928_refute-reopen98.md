# SAFE0928 refute-reopen98 -- checking "the 98c band can come back"

Read-only check of `SAFE0928_reopen98.md`. Times are ET. Verdict: **the facts hold,
but the dollars-a-day figure for the recommended form is too high.**

## Reason first

1. **The 5 losses and the seller gate: confirmed.** I re-read all 5 losing band buys
   from our own order records, not the finding's scripts. Sides, prices paid,
   contracts, seconds left and losses all match. Hedge buys were left out. I rebuilt
   the sold share from the recorded trade feed myself: 0.75, 0.70, 0.64, 0.64 and 0.56
   (the bot logged 0.559 on the last one). The offer ages logged on the bot's own
   signal records were 9, 81, 57 and 148 ms. SOL's 65 ms is the finding's rebuild, and
   I did not check it. All 5 had more than 20 s left, an offer younger than 500 ms, and
   sellers above half, so the live gate would refuse all 5.
2. **The raw band money: confirmed to the cent.** My own count, which includes the
   restored 09-25 log: 345 markets, 5 lost, +$30.00. 9/9-9/17: 111 markets, 1 lost,
   +$65.50. 9/18-9/28: 234 markets, 4 lost, -$35.50.
3. **Hedges are safe: confirmed.** Raising `--price-ceiling` only lets more buys
   through. `--early-max-price` checks only 45-second-bet buys, and the code says it
   cannot block a hedge. The one hedge check that reads the ceiling (`hedge_normal_ok`)
   is loosened by a higher ceiling, never tightened.
4. **What is overstated: "+$10.50-16 a day" for reopening only the 30-second bet.**
   That figure comes from the 9/9-9/28 record, when there were about 8 of these
   markets a day. The finding's own freshest data is the 31 hours since the ceiling
   went live. In those hours the ceiling alone turned away 10 markets, and 5 of them
   (not 4) had 30 s or less left. One of those 5 (BNB 9/27 11:15 PM) still got 90
   contracts from us at 97.8c, so reopening would have added almost nothing there. The
   other 4 were worth about $4.70 at full size. So the 5 together come to about **$5
   in 31 hours, roughly $4 a day**, and that is before the seller gate removes any of
   them. It is the most we could have made (these are offers, not our buys), not a
   loss rate. Cheap offers have been drying up, so expect nearer $4-5 a day than $10-16.
5. **What that means for the risk.** The break-even of about 1.9 losses in 100 markets
   does not change. What changes is the payback: one lost full bet (about $96) takes
   **about 20-25 days** of income at $4-5 a day to earn back, not 6-9. The reopening is
   still worth a small amount if the gate holds, but it is a small amount.

## Smaller points

- The answer calls the last loss "BTC 9/26 11:59 PM", and the table calls it "BTC 9/27
  12:00 AM". Both are right: we bought at 11:59 PM on 9/26 in the market that closed
  at midnight.
- "Over 19 days" is really 20 ET days (9/9-9/28, with 9/28 only partly done). This
  does not change any total.
- **Multiple looks.** The report compared 5 forms across the 2 halves. After the rules,
  every form showed 0 losses. So choosing the 30-second form trims risk. It was not
  picked for being the best number.
- **The in-sample warning is correct.** `PREREG_toxic.md` confirms the gate was
  designed on our fills from 9/13 to 9/24. Only SOL 9/11 and BTC 9/27 are true outside
  tests, and both were caught.
- Not re-checked: the 38 winners the rules would have removed (+$35), the counts once
  the rules are applied (302 markets, and 177 for the 30-second form), and SOL's
  rebuilt offer age.

## Files

Scripts (standard library, self-tested with planted answers and an empty world) are in
`scratchpad/safe0928/refute-reopen98/`: `band_raw.py` (the raw band money) and
`ss_check.py` (the sold-share rebuild). Both recorders were alive after the run
(crypto_feeds 105352, kalshi_collector 2532788), with 61.3 GB of disk free.
