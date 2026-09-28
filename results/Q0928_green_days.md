# Q0928 green_days -- what made 09-09..09-18 green, and what broke on 09-19

Written 2026-09-28 by a read-only job. All money comes from Kalshi's own books
(`results/kalshi_ledger.json`, written 09-28 03:46Z, so **nothing from today, 09-28 ET, is in it**).
The live logs supply the side, the timing, the gates and the hedges. Settings come from the bot's
own start records, not from memory. No replay and no paper numbers were used. Times are ET.
The restored 09-25 log (commit 43516ac) is used. WHY_NO_MONEY_2026-09-27 was written while those lines were missing,
but its money came from the ledger, so its day totals still stand.
"Green streak" = 09-09..09-18 (H1). "After" = 09-19..09-27 (H2).
Crypto only: the 9 fifteen-minute coins plus the 1-contract hourly BTC ladder. Coin race and oil are left out.

## The answer, reason first

**No single forgotten switch made the green streak. Three things did, and only one of them was a setting.**

1. **Losses were the same size in count but five times bigger in dollars.** Both periods lost
   about 2 markets in 100 (H1 13 of 543, H2 9 of 461). The average win was the same too:
   **$1.55 vs $1.51 a market**. The average loss was **-$14 in H1 and -$72 in H2**.
   In H1 one loss cost about 9 wins; in H2 it cost about 48.
2. **Why H1's losses were small (mostly timing, partly luck):** 8 of H1's 13 losing markets
   fell on 09-10..09-12, when every bet was a fixed 20 contracts (about $19). Those days were
   barely green: **+$0.23 and +$1.25** on 09-10 and 09-11. The six money days (09-13..09-18,
   +$549) had only **3 real losing markets out of 314**. Each one was hedged and cost $28-34.
   At H2's loss rate, 5 or fewer losing markets in 314 happens about 4 times in 10.
   So the loss COUNT was not luck. What H1 had was small positions when the losses came.
3. **Cheap offers were plentiful.** 14 in 100 H1 markets were bought under 93c, and they made
   **+$238, 37% of H1's money**. After 09-18 it was 7 in 100, and they **lost $107**. That is the
   market changing. No setting did it.
4. **The one real setting difference: nearly every H1 market held one bet or less.** Only 3 of 543
   held more than 1.6 bets. In H2, 9 markets held two stacked full bets. They lost
   **2 times in 9 (-$229)**: BTC 09-23 8:30 PM, 176 contracts, -$130, and BTC 09-27 midnight,
   198 contracts, -$132. H1 allowed one buy per market until 09-13 11:18 PM ET. The
   `--one-full-bet` rule that went live 09-27 4:11 AM ET blocks this again. It rests on 2 losses,
   so treat it as likely, not proven.

**The "return % of bank" fell for a boring reason.** In H1 one bet was about bank/4.5 to bank/6.
Since 09-20 it is about bank/12, because the third coin put a third bet into the divisor.
The dollars per ordinary day are about the same: H1 money days averaged **$91.50**, and H2's
clean days averaged **$82** (09-20 $110, 09-22 $54, 09-24 $93, 09-25 $107, 09-26 $47).
The bank doubled and the dollar bet stayed about the same, so the percentage halved.

**Was 09-19 the 45-second leg? Partly: it was the vehicle, not the whole cause.**
- On 09-19, markets first bought on the 45-second leg lost **-$172.84** (50 markets).
  Markets first bought at 30 s or less lost **-$50.63** (23 markets). The day was **-$223.46**.
- 4 of the 6 losing markets were first bought on the 45-second leg, for **$283 of the $403 lost**.
  But only 2 of those 4 bets actually lost (-$174). In both, the insurance was switched off by a
  code bug: in one the bot crashed, in the other a pause skipped the hedge. One of the two
  (94.4c) could only be bought because the 45-second leg's price floor was removed 51 minutes
  earlier. The other 2 bets **won** and lost $109 on insurance bought at 27% and 50% confidence
  (false alarms).
- **The 45-second leg over its whole life:** at a THIRD of a bet, **208 markets, 1 lost, +$168**.
  At a FULL bet, **164 markets, 5 lost, -$92**. If the two sizes really lost equally often, a split
  this lopsided would happen about 6 times in 100. The full-size days were also the days of the
  removed floor, the biggest bets and the 60c insurance rule, so the evidence points at "full
  size", but it could also be those. Today's live bot already runs it at a third.

---

## 1. The ET-day table (Kalshi's books)

"45-s leg share" = the share of contracts bought with 31-45 s left. "Bought under 96.5c" = contracts.
The bank comes from the bot's own size records. Before 09-12 the bet was a fixed 20 contracts and
the bot did not record the bank. Insurance = what the hedge side paid back minus what it cost.
Net = wins + losses + insurance - fees. Pinday's crypto line differs by cents because it counts
the hourly BTC ladder as "other".

| ET day | markets | contracts | avg paid | wins $ | losses $ (markets) | insurance $ | fees $ | NET $ | bank at start $ | bet (contracts) | return % of bank | 45-s leg share | bought under 96.5c |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 09-08 | 32 | 363 | 94.6c | +12.86 | -52.23 (1) | +0.00 | 1.22 | **-40.59** | - | 20 (fixed) | - | 0% | 200 |
| 09-09 | 40 | 719 | 92.9c | +51.17 | +0.00 (0) | +0.00 | 2.43 | **+48.74** | - | 20 (fixed) | - | 0% | 335 |
| 09-10 | 44 | 816 | 92.4c | +39.05 | -35.92 (3) | +0.00 | 2.90 | **+0.23** | - | 20 (fixed) | - | 0% | 420 |
| 09-11 | 49 | 859 | 94.9c | +35.33 | -31.40 (2) | +0.00 | 2.68 | **+1.25** | - | 20 (fixed) | - | 0% | 403 |
| 09-12 | 96 | 1722 | 95.2c | +79.29 | -29.39 (3) | -6.01 | 5.85 | **+38.04** | 194 | 66 | +19.6% | 0% | 943 |
| 09-13 | 49 | 2194 | 94.2c | +126.25 | +0.00 (0) | -3.20 | 8.27 | **+114.78** | 199 | 47 | +57.8% | 0% | 1266 |
| 09-14 | 61 | 3319 | 95.2c | +155.31 | -117.32 (2) | +55.58 | 12.46 | **+81.10** | 324 | 59 | +25.0% | 0% | 1612 |
| 09-15 | 36 | 2432 | 96.6c | +81.78 | +0.00 (0) | +0.00 | 5.47 | **+76.32** | 396 | 74 | +19.3% | 0% | 642 |
| 09-16 | 45 | 3012 | 95.9c | +123.47 | -0.98 (1) | -27.64 | 9.74 | **+85.11** | 479 | 86 | +17.8% | 0% | 1061 |
| 09-17 | 55 | 3692 | 95.0c | +136.80 | -52.47 (1) | +27.72 | 12.18 | **+99.87** | 563 | 98 | +17.7% | 47% | 1376 |
| 09-18 | 68 | 3694 | 96.6c | +93.87 | -3.70 (1) | +8.74 | 7.06 | **+91.85** | 603 | 79 | +15.2% | 65% | 362 |
| 09-19 | 73 | 6779 | 96.6c | +200.68 | -313.08 (4) | -91.42 | 19.65 | **-223.46** | 664 | 103 | -33.7% | 63% | 1649 |
| 09-20 | 53 | 3294 | 96.4c | +117.43 | +0.00 (0) | +0.00 | 7.80 | **+109.63** | 811 | 75 | +13.5% | 69% | 954 |
| 09-21 | 48 | 3006 | 96.6c | +93.63 | -127.69 (2) | +39.65 | 8.56 | **-2.97** | 931 | 78 | -0.3% | 68% | 833 |
| 09-22 | 34 | 1688 | 95.8c | +60.18 | -2.65 (1) | +0.26 | 4.09 | **+53.70** | 916 | 80 | +5.9% | 39% | 570 |
| 09-23 | 54 | 3337 | 96.5c | +94.29 | -152.36 (1) | +24.87 | 9.27 | **-42.46** | 983 | 84 | -4.3% | 20% | 851 |
| 09-24 | 63 | 2799 | 96.4c | +100.02 | +0.00 (0) | +0.00 | 6.59 | **+93.42** | 930 | 83 | +10.0% | 34% | 840 |
| 09-25 | 53 | 2890 | 96.0c | +114.69 | +0.00 (0) | +0.00 | 7.38 | **+107.31** | 1035 | 89 | +10.4% | 29% | 708 |
| 09-26 | 53 | 2595 | 95.7c | +111.60 | +0.00 (0) | -56.62 | 8.18 | **+46.80** | 1143 | 97 | +4.1% | 37% | 605 |
| 09-27 | 30 | 1788 | 95.6c | +73.98 | -192.94 (1) | +19.47 | 9.73 | **-109.21** | 1042 | 88 | -10.5% | 13% | 672 |
| 09-28 | not in the ledger yet (written 03:46Z = 11:46 PM ET 09-27) | | | | | | | | | | | | |

One bet as a share of the bank: 09-13 bank/4.5, 09-14..17 bank/5.6-6.0, 09-18 bank/7.9,
09-19 bank/6.7, **09-20..27 bank/11-12.4**.

## 2. Every setting in force each day (the bot's start records)

Columns show the setting at the start of the ET day (midnight). The last column lists changes during the day.
"45s edge cap 3c" works as a price floor near 97c on the 45-second leg; at 10c the 90c floor becomes the real floor.
The toxic gate and one-full-bet do not appear in start records, so they come from VERSIONS.md, marked (V).
The same 9 coins were traded every day; the 1-contract hourly BTC ladder was added 09-24.

| ET day | bet=bank/x | 3rd coin | ceiling | 45s leg | 45s size | 45s floor | 45s edge cap c | hedge | hedge at | hedge 60c rule | panic | late boost s | late x | late extra | 90-94c boost | sweep | ladder | edge floor | confidence | buys/market | jump gate | loss cap $ | changes during the day (ET) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 09-09 | old rule | - | 0.98 | off | - | - | - | OFF | - | - | - | - | - | - | off | - | - | 0.003 | 0.98 | - | - | - | - |
| 09-10 | old rule | - | 0.98 | off | - | - | - | OFF | - | - | - | - | - | - | off | - | - | 0.003 | 0.98 | - | - | - | 04:33 confidence 0.98->0.995 |
| 09-11 | old rule | - | 0.98 | off | - | - | - | OFF | - | - | - | - | - | - | off | - | - | 0.003 | 0.995 | - | - | - | 23:07 one buy per market |
| 09-12 | old rule | - | 0.98 | off | - | - | - | OFF | - | - | - | - | - | - | off | - | - | 0.003 | 0.995 | 1 | - | - | 04:45 hedge ON at 0.9; 14:06 hedge at 0.8; 19:13 size follows the bank |
| 09-13 | old rule | - | 0.98 | off | - | - | - | on | 0.8 | - | - | - | - | - | off | - | - | 0.003 | 0.995 | 1 | - | - | 13:51-14:49 confidence 0.99 (reverted); 23:18 buys/market 1->2 |
| 09-14 | old rule | - | 0.98 | off | - | - | - | on | 0.8 | - | - | - | - | - | off | - | - | 0.003 | 0.995 | 2 | - | - | 08:54 sweep on; 11:53 ladder on; 21:39 jump gate on |
| 09-15 | old rule | - | 0.98 | off | - | - | - | on | 0.8 | - | - | - | - | - | off | on | on | 0.003 | 0.995 | 2 | on | - | - |
| 09-16 | old rule | - | 0.98 | off | - | - | - | on | 0.8 | - | - | - | - | - | off | on | on | 0.003 | 0.995 | 2 | on | - | 09:57 hedge at 0.8->0.6 |
| 09-17 | old rule | - | 0.98 | off | - | - | - | on | 0.6 | - | - | - | - | - | off | on | on | 0.003 | 0.995 | 2 | on | - | 09:05 45s leg ON at a third; 15:41 full; 21:48 off (30 s, half); 23:02 on at a third |
| 09-18 | old rule | - | 0.98 | on | 1/3 | - | - | on | 0.6 | - | - | - | - | - | off | on | on | 0.003 | 0.995 | 2 | on | - | 02:51 bet=bank/8, 45s floor 90c, edge cap 3c; **12:33 45s FULL**; **18:46 hedge 60c rule + 1.5x at 90-94c** |
| 09-19 | 8 | - | 0.98 | on | full | 0.90 | 3 | on | 0.6 | yes | - | - | 1.0 | - | on | on | on | 0.003 | 0.995 | 2 | on | - | **00:03 bet=bank/5.88, 3rd coin, 1.5x late boost**; **01:08 45s edge cap 3->10c**, late extra; 02:06-02:20 panic 0.35->0.40; 03:30 loss cap $200 |
| 09-20 | 5.88 | 1 | 0.98 | on | full | 0.90 | 10 | on | 0.6 | yes | 0.4 | 10 | 1.5 | 1 | on | on | on | 0.003 | 0.995 | 2 | on | 200 | 01:46 bet=bank/7.84; 03:55 90-94c boost off |
| 09-21 | 7.84 | 1 | 0.98 | on | full | 0.90 | 10 | on | 0.6 | yes | 0.4 | 10 | 1.5 | 1 | off | on | on | 0.003 | 0.995 | 2 | on | 200 | 14:14 60c rule off; 16:12 hedge at 0.25 |
| 09-22 | 7.84 | 1 | 0.98 | on | full | 0.90 | 10 | on | 0.25 | - | 0.4 | 10 | 1.5 | 1 | off | on | on | 0.003 | 0.995 | 2 | on | 200 | 07:41 45s back to a third |
| 09-23 | 7.84 | 1 | 0.98 | on | 1/3 | 0.90 | 10 | on | 0.25 | - | 0.4 | 10 | 1.5 | 1 | off | on | on | 0.003 | 0.995 | 2 | on | 200 | 21:13 hedge at 0.4; 22:22 45s floor 95c |
| 09-24..26 | 7.84 | 1 | 0.98 | on | 1/3 | 0.95 | 10 | on | 0.4 | - | 0.4 | 10 | 1.5 | 1 | off | on | on | 0.003 | 0.995 | 2 | on | 200 | 09-24 hourly BTC ladder added at 1 contract |
| 09-27 | 7.84 | 1 | 0.98 | on | 1/3 | 0.95 | 10 | on | 0.4 | - | 0.4 | 10 | 1.5 | 1 | off | on | on | 0.003 | 0.995 | 2 | on | 200 | 01:08 toxic gate (V); 03:05 ceiling 97.8c; 04:11 one full bet per market (V) |

**True in H1 and not after:** no 45-second leg (until 09-17), no third coin, no late boost, one bet
= bank/4.5-6, hedge trigger 0.8-0.9 (09-12..09-16) or no hedge at all (09-09..09-12), one buy per
market (until 09-13 11:18 PM), plentiful offers under 93c.
**True after and not in H1:** the 45-second leg (full size 09-18 12:33 PM .. 09-22 7:41 AM), third
coin, 1.5x late boost, late extra, one bet = bank/12, hedge at 0.25-0.6, stacked full bets in one
market, 10c edge cap on the 45-second leg.

## 3. Each difference tested on our fills

A close = every market settling at the same quarter hour. Losses are rare, so each cell rests on
a handful of losing markets. A difference of 2 or 3 losses cannot be told apart from luck. The
sample CAN show a change in the size of a loss, and it cannot show a loss-rate change smaller
than about 2 in 100.

| difference | H1 | H2 | moves money? moves losses? |
|---|---|---|---|
| All markets | 543 mkts, lost 2.4 in 100, **+$637**, +$2.97 per $100 bet | 461 mkts, lost 2.0 in 100, **+$33**, +$0.12 per $100 | same loss count, 5x the loss size |
| H2 without 09-19 | - | 388 mkts, lost 1.3 in 100, +$256, +$1.24 per $100 | still about 40% of H1's return per dollar bet |
| Avg win / avg loss per market | +$1.55 / -$14.13 (loss = 30 contracts) | +$1.51 / -$72.11 (loss = 96 contracts) | **this is the gap** |
| Bought under 93c | 75 mkts, lost 8 in 100, **+$238** | 31 mkts, lost 13 in 100, **-$107** | the supply went away (the market, not a setting) |
| Bought 97.5-98c | 238 mkts, lost 0.8 in 100, +$164 | 278 mkts, lost 0.7 in 100, +$95 | same loss rate, thinner win |
| Position > 1.6 bets (stacked full bets) | 2 mkts, 0 lost, +$26 | **9 mkts, 2 lost (22 in 100), -$229** | moves losses; blocked since 09-27 by one-full-bet |
| Position 1.05-1.6 bets (top-up / late add) | 1 mkt, +$1 | 24 mkts, 0 lost, **+$152** | good; still allowed |
| Bought with 15 s or less left | 125 mkts, +$4.68 per $100 | 62 mkts, +$4.30 per $100 | good in both halves; not the cause |
| Coins held at the same close: 3 | 39 mkts, 1 lost, +$39 | 63 mkts, 0 lost, +$42 | third coin is not the cause |
| First buy on the 45-s leg | 83 mkts, 2 lost, +$84 | 289 mkts, 4 lost, **-$7** | see 45-s size below |
| 45-s leg at a THIRD (all days) | 208 mkts, **1 lost, +$168** | | |
| 45-s leg at FULL size (all days) | 164 mkts, **5 lost, -$92** | | moves losses; about 6 in 100 chance by luck; confounded |
| Hedge false alarms (our side won) | 5, cost -$29 (15-18c a contract) | 4, cost -$162 (46-63c a contract) | late triggers pay far more per false alarm |
| Hedged real losses | 6, net -$97 (insurance got back 42-50% on the big ones) | 5, net -$415 (got back 16-43%) + 3 with no working hedge on 09-19 | |
| One bet = bank/5.88 (09-19 00:03 -> 09-20 01:46 ET) | - | 79 mkts, 4 lost, -$209 | that is 09-19 itself |

On the hedge trigger this sample cannot settle anything; the 09-21 per-second rebuild in
VERSIONS.md (`v-hedge25`) is the better evidence. It found the 0.60 trigger worse than not
hedging at all. The 0.80 trigger was never scored there, and scoring it would take the same per-second rebuild.

## 4. 09-19 (-$223.46): the six losing markets

What changed in the 12 hours before (ET): 09-18 12:33 PM the 45-second leg went to a FULL bet.
6:46 PM brought the 60c insurance price rule and 1.5x at 90-94c. 09-19 12:03 AM brought
bet = bank/5.88 (was /8), a third coin and the 1.5x late boost. 1:08 AM the 45-second leg's
edge cap went 3c -> 10c, which removed its ~97c floor. 3:30 AM the $200 loss cap arrived.
Two code bugs rode along: a crash in the close-budget log line, and the loss-cap pause
skipping the hedge.

| close ET | coin | leg (s left) | contracts @ avg paid | net $ | insurance $ | why |
|---|---|---|---|---|---|---|
| 1:45 AM | BNB | 30 s or less (24) | 76 @ 75.0c | **-57.76** | +0.24 | Bought into a collapse: saw 85c, the sweep filled down to 75c, and confidence was 23% one second later. The hedge fired, but the **new 60c price rule held it at a 21c ask**. Then 51c, 70c, 76c, and 5 tries ran out with 1 contract hedged. Not the 45-s leg. |
| 2:00 AM | BTC | **45-s leg (35)** | 70 @ 94.4c | **-66.34** | 0 | At 94.4c the edge was 5c, so **only the 3c->10c cap change 51 minutes earlier allowed it**. The bot **crashed** 5 s later (close-budget log bug, 1:59:30 AM) and no hedge ever ran. |
| 12:30 PM | BNB | 30 s or less (23) | 85 @ 97.3c | **-61.75** | +21.70 | Signal at 91.5c with only 23 contracts there. The order was sized off the whole 98c ladder and boosted 1.5x, so it filled 83 at 97.3c. The hedge came at 15% confidence and got back a quarter. Not the 45-s leg. |
| 4:00 PM | BTC | **45-s leg (45)** | 110 @ 98.0c (full bet) | **-107.95** | 0 | The **$200 loss-cap pause skipped the hedge pass**, so there was no hedge attempt in 45 s. Largest loss that day. |
| 11:45 PM | XRP | **45-s leg (41)** | 104 @ 97.7c | **-64.95** | -65.52 | Our side **won** (+$2.44). A hedge at 27% confidence bought 104 at 63c. False alarm. |
| 11:45 PM | HYPE | **45-s leg (33)** | 104 @ 94.1c | **-43.92** | -47.84 | Our side **won** (+$6.14). A hedge at 50% confidence (0.60 trigger) bought 104 at 46c. False alarm. |

Sum of the six: -$402.67. The other 67 markets: +$179.21.

**Was it 45 seconds? Partly.** The 45-second leg carried 4 of the 6 ($283 of the $403). The
leg's own bet lost only twice, and both times the hedge was switched off by a bug (the crash,
the pause). The cheaper of those two exists only because the price floor was removed that
night. The other two were insurance false alarms on bets that won. At a third of a bet the
leg has earned +$168 on 208 markets with 1 loss. At a full bet it has lost $92 on 164 markets
with 5 losses.

## 5. How honest the green streak was

- Half luck of timing: the losses in the streak landed on the small-bet days (09-10..09-12,
  about $19 bets, days that finished +$0.23 and +$1.25).
- Half cheap supply: the plentiful offers under 93c made 37% of the streak's money, and they
  are mostly gone.
- The loss count was not luck: H1 lost 2.4 in 100 and after lost 2.0 in 100.
- What we can still copy: keep one bet per market (live since 09-27) and the 45-second leg at a
  third (live since 09-22). And never ship five changes in one night: 09-19 took six live changes
  in 15 hours plus two bugs, so no single cause can be isolated.

Scripts (self-tested: planted markets + empty world) and raw outputs:
`C:\Users\Joe\AppData\Local\Temp\claude\C--kals-repo\b2dbb5c1-92b0-452a-b1e9-86b7402d3a34\scratchpad\q0928\green_days\`
(`build.py`, `days.py`, `diffs.py`; listings `day19.py`, `losers.py`, `daysettings.py`, `settings.py`).
