# SAFE0928 reopen98 -- can the 98c band come back now that we have less risk?

Read-only. Nothing live was changed. Times are ET. Money comes from our own fills
(the Kalshi ledger plus the live order records, including the 09-25 log restored on
09-28) unless a line says otherwise. "98c band" means a buy where we paid 97.85c or
more. Break-even at 98c is about 1.9 losses per 100: a win pays about 1.9c a
contract, a loss costs about 98c.

## Answer, reason first

1. **The two safety rules now live would have refused all 5 of the band's losing
   buys.** The seller gate catches all five. The one-bet rule catches none of them:
   no losing band buy was a second full bet.
2. **Without those 5, the band made money.** Raw: 345 markets, 5 lost,
   **+$30** over 19 days. With today's two rules applied: **302 markets, 0 lost,
   +$275**. The rules would also have turned away 38 winning markets worth **+$35**.
3. **Treat that 0 with care.** The seller gate was designed on 09-24 from fills
   dated 09-13 to 09-24, and 3 of these 5 losses fall inside those dates. So
   catching them is partly built in. Only 2 losses fall outside those dates (SOL 9/11
   and BTC 9/26), and the gate caught both. Outside those dates the band has 84
   markets with 0 losses. That sample can't tell a true rate of 0 losses in 100
   from 4.3 in 100. Break-even is 1.9.
4. **Reopening is worth about $10-16 a day at today's size, if nothing loses.**
   One loss costs about **$96** (98 contracts at 98c). That wipes out about 6-9
   days of the band's income. Since the 97.8c ceiling went live, it has been the
   only reason for turning away just **10 markets in 31 hours**, and all 10 won.
   That is an upper bound of about $10 a day.
5. **Recommendation: a conditional form.** Reopen 98c on the 30-second bet only,
   and keep the 45-second bet capped at 97.8c. Flags: `--price-ceiling 0.98`
   plus `--early-max-price 0.978`. It needs no code change. On the record it made
   **$10.50-16 a day**, with 177 markets and 0 losses after the two rules. It keeps
   out the leg that had the two biggest band losses. Re-opening that leg would
   add only about $3 a day, because it now bets a third. Pre-registered stop: go
   back to 0.978 on the **2nd loss in the first 100 reopened markets**, or on any
   single loss while the seller gate was switched off or had no reading.

## 1. The 5 losing band markets, one by one

"Seller gate" = the live toxic-fresh rule. It refuses when the offer appeared less
than 500 ms ago AND more than half of the last 3 seconds of trading sold our side
AND more than 20 s are left. Before 9/24 the bot did not log the selling share, so
I rebuilt it from the recorded trade feed exactly as the bot computes it. On the 60
buys where the bot did log it, the rebuild landed on the same side of the 50-in-100
line 57 times. The median difference was 0.

| market (ET) | what we bought in the band | secs left | offer age | sold share (3 s) | seller gate | 2nd full bet? | band loss |
|---|---|---|---|---|---|---|---|
| SOL 9/11 11:00 PM | 20 NO at 97.9c (first buy) | 29 | **65 ms** (rebuilt from the recorded book) | 0.75 (rebuilt) | **refuses** | no | -$19.61 |
| BNB 9/19 12:30 PM | 1.7 YES at 97.87c (a top-up; the main 83 at 97.27c were outside the band) | 23 | 9 ms (logged) | 0.70 (rebuilt) | **refuses** (the 97.27c buy too) | no | -$1.67 |
| BTC 9/19 4:00 PM | 110 NO at 98.0c, 45-second bet at full size | 45 | 81 ms (logged) | 0.64 (rebuilt) | **refuses** | no | -$107.94 |
| HYPE 9/21 6:15 PM | 55 YES at 98.0c, 45-second bet | 43 | 57 ms (logged) | 0.64 (rebuilt) | **refuses** | no | -$53.97 |
| BTC 9/27 12:00 AM | 99 YES at 97.89c (first buy) | 30 | 148 ms (logged) | 0.56 (logged) | **refuses** | no. Its second bet was at 97.0c, outside the band | -$97.05 |

- **Offer age check.** The SOL age is the only rebuilt one. On two losses where the
  bot logged the age, the same rebuild read 82 vs 57 ms (HYPE) and 122 vs 81 ms
  (BTC 9/19). Both are well under 500 ms, so SOL's 65 ms is too.
- **The one-bet rule and the band.** Across all 345 band markets it removes one buy
  (a winner, +$1.10). The band's losses were never second bets.
- **Inside or outside the gate's design dates.** The gate was designed from fills
  dated 9/13 to 9/24, and 9/19, 9/19 and 9/21 fall inside them. SOL (9/11) is
  before them and BTC (9/27) is after, so those two are true out-of-sample catches.

## 2. The band's money, raw and with today's two rules

Own-leg money of the band buys only. Insurance is left out; with a share of
insurance added, the raw band is +$63.

| | markets | lost | band money | contracts |
|---|---|---|---|---|
| raw, 9/9..9/28 | 345 | 5 (1.45 in 100) | +$30.00 | 16,609 |
| raw, 9/9..9/17 | 111 | 1 | +$65.50 | 4,488 |
| raw, 9/18..9/28 | 234 | 4 | **-$35.50** | 12,121 |
| **both rules, 9/9..9/28** | **302** | **0** | **+$274.89** | 14,507 |
| both rules, 9/9..9/17 | 107 | 0 | +$81.56 | 4,279 |
| both rules, 9/18..9/28 | 195 | 0 | +$193.33 | 10,208 |
| removed by the rules | 43 | 5 | losses -$280.24, winners +$35.35 | |

21 band buys (9/9..9/12, 9/22..9/23) have no offer age or selling share: the old logs
lack them and parts of the 9/23 trade feed are missing. I counted them as bought.
Counting them as refused changes the total by less than $12.

**What the sample can detect** (exact 95% ranges, counted in markets):
- 5 of 345 raw: 0.5 to 3.4 losses per 100. That range straddles break-even.
- 0 of 302 with the rules: 0 to 1.2 per 100. That is below break-even, but it
  flatters the rules, because 3 of the removed losses helped design the gate.
- 0 of 84 outside the gate's design dates: 0 to 4.3 per 100. It can't settle the
  question.

## 3. Reopening, valued at today's size (98 contracts; the 45-s bet at a third)

Each buy is scaled from the size it had then to today's size. A loss is scaled
the same way, so SOL's 20-contract loss counts as a full $96 loss.

| form | 9/9..9/17 | 9/18..9/28 |
|---|---|---|
| reopen, no safety rules (the old 0.98 bot) | 111 mk, 1 lost, **+$6/day** | 234 mk, 4 lost, **+$2/day** |
| **back to 0.98 with today's two rules** | 107 mk, 0 lost, +$16.40/day | 195 mk, 0 lost, +$13.73/day |
| **30-s bet only** (`--early-max-price 0.978`) | 93 mk, 0 lost, **+$15.95/day** | 84 mk, 0 lost, **+$10.50/day** |
| 45-s third-size bet only | 14 mk, 0 lost, +$0.45/day | 113 mk, 0 lost, +$3.23/day |
| only 20 s or less left (no flag exists; needs code) | 27 mk, 0 lost, +$4.68/day | 32 mk, 0 lost, +$4.01/day |

- **By seconds left, raw.** 20 s or less: 59 markets, 0 lost, +1.9c a contract,
  with no gate needed. 21-30 s: 135 markets, 3 lost. 31-45 s: 157 markets, 2 lost,
  -$36. Every raw loss came with more than 20 s left, which is exactly where the
  seller gate works. The "20 s or less" form is the safest, but it earns only about
  $4 a day and needs a code change.
- **Why leave out the 45-second bet.** Both of its band losses were the largest
  ones (-$108, -$54). At a third size it adds only about $3 a day, and one loss
  there (about $32) wipes out about 10 days of that.
- **Since the ceiling went live** (9/27 3:05 AM to 9/28 8:44 AM). This is the
  bot's own once-a-second record, and the price ceiling is the ONLY reason each
  market was turned away. It counts **10 markets**: 4 on the 30-s bet, 6 on the
  45-s bet, **all 10 won** by Kalshi's result. At the offered depth (median 150
  contracts, some only 5-43) that is about **+$13 in 31 hours**. This is the
  offer list, not our fills: it is the most we could have made and the least we
  could have lost, never our loss rate. I could not apply the seller gate to it,
  because that record has no offer age. Another 35 markets at 97.9-98c were turned
  away anyway for being under our 99.5-in-100 confidence line.

## 4. Worst case at today's size

- One lost full bet at 98c costs 98 x 98c + fee = **about $96**. One loss wipes
  out about 52 wins at 98c (about 47 at 97.8c).
- If the last-15-seconds add stacks on top (up to 147 contracts), a loss costs
  **about $144**. The same stack at 97.8c costs about $144 too. **The ceiling
  does not lower the worst single loss.** It only removes the bets that pay the
  least per win.
- Two band losses in one day would cost about $190-290. I did not check how the
  bot's daily stop rules (`--max-losses 2`, `--loss-abort -60`) cap that, and the
  ceiling does not change it.
- Money per day at 98 contracts on the 30-s form, by true loss rate: 0 in 100 ->
  about $10-16. 1 in 100 -> about $5-8. **1.9 in 100 -> $0. 3 in 100 -> about
  -$6 to -$10.**

## Recommendation

**Conditional form: `--price-ceiling 0.98` with `--early-max-price 0.978`.**
- It reopens 97.9-98c on the 30-second bet only, where the record is 177 markets,
  0 losses after the two rules, +$10.50-16 a day at today's size.
- It keeps the 45-second bet at 97.8c.
- **Pre-registered stop, written before any live number:** back to 0.978 on the 2nd
  loss in the first 100 reopened 30-s markets (2 in 100 is above break-even). Also
  back to 0.978 on any band loss the seller gate could not judge (no selling share,
  or an offer age it was not sure of).
- Watch item: every 30-s buy at 97.9-98c, its offer age and selling share, and the
  result. Add it to READS_DUE.

If you would rather take no new risk: keep 0.978. That gives up about $10 a day on
the recent record. Going fully back to 0.98 adds only about $3 a day more than the
conditional form, and brings the 45-second leg back into the band.

## Method, files

Scripts (standard library only, each self-tested on planted answers and an empty world,
one at a time, well under 300 MB) in `scratchpad/safe0928/reopen98/`:
- `extract.py`: streams every `pinrun-live-*.jsonl` (142 files).
- `analyze.py`: the band, both rules, and the loss range. It reproduces the recheck's
  345 / 5 / +$30.00 exactly.
- `tape_ss.py`: rebuilds the selling share from `C:\kals\kalshi_data\trade`.
- `levelage.py`: rebuilds the offer age from the recorded order book.
- `merge.py`, `value.py`, `scaled.py`: the band's money under each rule and form,
  at today's size.
- `refusedpop.py`: markets the ceiling turned away since 9/27 (`pintraj-live-*`
  plus Kalshi's results from the recorded market-status feed).

Some trade-feed hours on 9/23 are missing or truncated. Both recorders were running
after the work (crypto_feeds pid 105352, kalshi_collector pid 2532788), with 61.4 GB
of disk free.
