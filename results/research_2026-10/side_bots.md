# Side bots -- lifetime record and whether each could scale (read 2026-10-08 ~09:40Z)

Read-only. Money = Kalshi's own settlements per subaccount (`pinledger.pnl`: payout from `value`/result + counts,
never `revenue`), cross-checked against each subaccount's balance to the cent. ET day = the market's close time in
ET (UTC-4). Scripts: scratchpad/final/sb_common.py, an_ladder.py, an_fc.py, an_race.py, an_dip.py, an_other.py,
an_paperladder.py, an_scale2.py, kfetch_sub2.py (GET only: sub 2 settlements/fills, sub 1/3 newer rows, balances).
Processes alive at the read: ladder 4047108, forecaster 3090252, coin race 3095608, dip-seller 665444, rain paper
1804636, paper ladder 132712, clean-room bettor paper 1469140, 3 fcvar papers. Disk 25.1 GB free.

Balances now: sub 1 (ladder) $77.94, sub 2 (forecaster) $78.92, sub 3 (weather) $44.81 cash + $4.92 in 5 open
positions, main $989.22. No open positions in subs 1 and 2.

---

## 1. Ladder (subaccount 1, `research/cleanroom/ladder_live.py --auto-size --market-cap-x 2`)

What it does: in the last 30 s of each quarter-hour, once the settlement average has decided a side, it rests a
post-only bid 2c under the model price (98c in practice, 97.9c when 98c would cross) for 5 contracts (pot / $14) in
every coin, and cancels at the close. It is paid 2c a contract when a seller hits the bid and the side holds.

| ET day | markets | contracts | $ net | $ bet | % on bet | lost |
|---|---|---|---|---|---|---|
| 09-29 | 8 | 10.5 | +0.21 | 10.25 | +2.07% | 0 |
| 09-30 | 20 | 121 | +2.46 | 118.54 | +2.08% | 0 |
| 10-01 | 16 | 125 | +2.53 | 122.47 | +2.07% | 0 |
| 10-02 | 8 | 40 | +0.80 | 39.20 | +2.04% | 0 |
| 10-03 | 11 | 58.8 | +1.18 | 57.62 | +2.05% | 0 |
| 10-04 | 21 | 125.2 | +2.50 | 122.69 | +2.04% | 0 |
| 10-05 | 6 | 30 | +0.60 | 29.40 | +2.04% | 0 |
| 10-06 | 10 | 61.9 | +1.24 | 60.63 | +2.04% | 0 |
| 10-07 | 13 | 70 | +1.41 | 68.58 | +2.06% | 0 |
| **total** | **113** | **642** | **+12.94** | **629.38** | **+2.06%** | **0** |

**LIFETIME (09-29 15:35Z .. 10-08 06:45Z, 9 ET days): 113 markets in 110 closes, 642 contracts, +$12.94 on
$629.38 bet = +2.06% on money bet, 0 lost; $65 put in -> $77.94 = +19.9% of the pot in 9 days ($1.44/day,
1.8%/day of the pot).** Every day +2.04..2.08% on bet: the return per contract is fixed by the price (2c on 98c);
only the volume moves. By coin: NEAR 34 markets / ZEC 23 / XRP 17 carry 70% of the money.

- Bids: 98c on 7,829 of 8,480 bids (97.9c on 87); the 95c/85c bids (281 each) are the three-rung penny period
  (09-28..29, 0 fills). Fills per order at size 5: 124 of 127 orders filled the full 5; 3 partial (0.19, 1.87, 3.8).
  Price paid 98c (102 markets) / 97.9c (11). Maker: fee $0.0001 total.
- Fill rate per bid: 1.84 per 100 bids at size 5 (126 of 6,862); 0.99 per 100 at size 1. ~880 bids a day are placed
  and ~865 cancelled unfilled; 2-18 closes a day get a fill (median 12), 5 contracts per filled close (max 20).
- How much of the passive supply it already takes (its own paper twin's `print_size` at top-rung fills, i.e. the
  seller prints that hit its price): 8,857 contracts printed at/through its price 09-29..10-07 vs 642 filled =
  **7% overall, 3-20% by day** (10-07: 2,049 printed, 70 taken). The rest went to the queue ahead of it (median 58
  contracts ahead at placement, 16% of bids first in line) and to other makers.
- Rails: `max_contracts` (10 x size) refused 43 bids, `market_cap` 7 (6 since the capfix). Peak money resting at once
  $49 (= the 50-contract rail, 09-30). Day stop (-20% of pot) never fired. Pot/14 auto-size: 5 since 09-30, needs
  $84 for 6 (rescale_wait 10-05 at $88.89 because a bid was resting; it has been 5 at every 04:00Z re-read).

**Known bugs / cap breaches:** v-ladder-settlefix (09-29: an empty settlement booked as a loss, fixed). ladder-caps
read 10-07: KXZEC15M 10-06 9:45 AM ET held 15 (3 bids of 5) over the x2 cap because a bid mid-cancel was invisible;
fixed v-ladder-capfix 10-07 12:14Z. Since the fix: 11 markets with fills, max 10 contracts, 0 over the cap, 6
market_cap refusals, 0 writer/sizer errors -> ladder-capfix bar (due 10-10) passing so far. Before the cap existed
NEAR held 20 contracts twice (09-30, 10-01) and 15 twice (10-01, 10-02) -- legal under the old 50-contract rail.

**Honest limit of the 0-of-113:** a lost market of 5 at 98c costs $4.90 = 49 winning markets. 113 wins in a row is
what a 1-in-50 loss rate produces 10 times in 100, so the record is consistent with break-even as well as with the
paper's 0 of 143. It proves the fills are not poisoned at this size; it does not yet prove the edge.

---

## 2. Forecaster (subaccount 2, `forecaster_live.py --variant race1_98_r28 --auto-scale --crash-gap 0.10`)

What it does: in the last 28 s, buys either side at a displayed ask of 75-98.5c when its model beats the price by 2c
after fees AND the offer is still there 1 s later, as an immediate-or-cancel order for pot/630 of the paper's size
(now 12.5% -> 13 per side). Skips when the index closed half its gap in 5 s (race1_98) or the ask already collapsed 10c
(crash-gap), and the first 2 s of the window (r28).

| ET day | markets | contracts | $ net | $ bet | % on bet | lost |
|---|---|---|---|---|---|---|
| 09-28 | 6 | 20 | +2.52 | 17.33 | +14.5% | 0 |
| 09-29 | 16 | 55 | +2.38 | 38.98 | +6.1% | 3 |
| 09-30 | 12 | 97 | +7.79 | 78.22 | +10.0% | 1 |
| 10-01 | 12 | 88.4 | -4.61 | 74.88 | -6.2% | 3 |
| 10-02 | 12 | 57 | -3.12 | 45.53 | -6.9% | 3 |
| 10-03 | 2 | 9 | +1.66 | 7.26 | +22.9% | 0 |
| 10-04 | 5 | 42 | +10.06 | 31.43 | +32.0% | 0 |
| 10-05 | 2 | 16 | -1.24 | 11.00 | -11.3% | 1 |
| 10-06 | 3 | 33 | +5.59 | 27.07 | +20.7% | 0 |
| 10-07 | 4 | 25 | +6.92 | 17.72 | +39.1% | 0 |
| **total** | **74** | **442** | **+27.94** | **349.42** | **+8.00%** | **11** |

**LIFETIME (09-29 00:54Z .. 10-08 03:30Z, 10 ET days): 74 markets in 62 closes, 442 contracts, +$27.94 on $349.42
bet = +8.0% on money bet; 11 lost (10 closes), money lost -$33.53; $50.98 put in net -> $78.92 = +54.8% of the pot
($2.79/day, 3.5%/day of the pot).** Before v-fc-r28 (59 markets): +$5.08 (+2.0%), 10 lost. Since v-fc-r28 10-03
06:12Z (15 markets, 15 closes): +$22.86 on $90.62 (+25%), 1 lost (BNB 10-05 -$4.29). The 5 both-sides markets
(bought YES then NO when its view flipped) are -$21.41 = 64% of all money lost; none since r28.

- Orders: 110 IOC, 515 contracts asked, 442 filled = **86 per 100**; 93 orders full, 13 empty, 4 partial. Fill share
  by order size: 1-2 asked 83%, 3-5 90%, 6-9 91%, 10-11 83% -- no sign that the current size is near the depth.
- Price: it pays a mean 4.1c LESS than the ask it was sent at (median 1.3c, 75th pct 5c, 90th 10c): the IOC lands
  while the offer is collapsing. 33 orders refused by the crash guard, 40 by in_flight. No halt, no day stop ever.
- What the SAME decisions at the paper's size did (the engine's own paper book in the same process, 100 per side,
  ~8x live, fill = what was still displayed 1 s later, paid at the displayed price): on the 74 markets live settled,
  **paper -$177.05 on $5,350 (-3.3%), 13 lost, vs live +$27.94**. All paper markets since 09-29: 106, -$663.64
  (-9.0%), 24 lost. That paper book is the UNGATED base engine; the live variant at paper size runs in the side-by-side
  papers: fcvar-paper-early 10-02 21:30Z..10-08 (5.5 days, 100/side): race1_98_crash10_r28 **+$99.09 on $1,797
  (28 markets, 4 lost, worst day -$87)** vs base -$280.96 (43 markets, 12 lost); fcvar-paper-crash (6.1 days):
  race1_98_crash15 +$100.55 (48 mk, 7 lost), race1_98_crash10 +$28.43 (45 mk, 7 lost), base -$372.43 (60 mk, 14
  lost); fcvar-paper-quiet (9.2 days): every variant -$585 to -$1,005.
- Displayed depth at the paper's triggers: median 45 contracts, 75th pct 146, 90th pct 455; the paper wants the 100
  cap on 23% of triggers. 840 of 1,064 paper triggers were "gone" before the 1-s check.

**Known bugs / events:** none open. 8 starts (4 stop-file restarts for variant/size switches), day-1 DOGE fill at 40c
on an 83c ask (F18) led to the crash guard. Bar (READS_DUE forecaster-live, due 10-13): size-up needs >= 60 markets
since r28 -- 15 so far.

---

## 3. Coin race (`research/pinracearm.py --live`, main account, KXCRYPTOLEAD15M, 20 a leg, $40 open)

Logic, from the file's docstring and live rails: (1) In the last 30 s before each quarter-hour it prices every leg of
the 5-coin race from the live index -- the leader's YES and each trailer's NO -- with the `fair` model (90c floor, 98c
ceiling, edge floor 0). (2) A leg must keep qualifying for 5 s straight before it is bought (or fire at 20 s on the
clock); the book is re-read at the send and a fresh ask more than 2c under the one seen is refused. (3) Consistency,
never a count: at most ONE yes leg, NO legs only on other coins, never a coin twice, at most 5 legs; 20 contracts a
leg, $40 open at once (the per-race cap in practice). (4) Size is what the book shows at or under the limit, not the
setting. (5) Real legs are scored from Kalshi's own result; a tie pays 50c and counts as a loss; 2 losing races in an
ET day stop it for that day (the count survives restarts since v-race-daystate).

| ET day | legs | contracts | $ net | $ bet | % on bet | lost (ties) |
|---|---|---|---|---|---|---|
| 09-21 | 32 | 32 | -1.02 | 30.95 | -3.3% | 2 |
| 09-22 | 41 | 41 | +1.03 | 39.89 | +2.6% | 0 |
| 09-23 | 54 | 53 | +0.35 | 51.57 | +0.7% | 2 (2) |
| 09-24 | 16 | 43 | +1.91 | 41.03 | +4.7% | 0 |
| 09-25 | 17 | 85 | +2.71 | 82.10 | +3.3% | 0 |
| 09-26 | 27 | 132 | +3.86 | 128.21 | +3.0% | 0 |
| 09-27 | 5 | 60 | +3.52 | 55.90 | +6.3% | 0 |
| 09-28 | 3 | 60 | +2.99 | 56.80 | +5.3% | 0 |
| 09-29 | 6 | 94 | +4.24 | 89.68 | +4.7% | 0 |
| 09-30 | 2 | 2.3 | -1.10 | 2.08 | -52.6% | 1 |
| 10-01 | 4 | 121 | +7.18 | 113.33 | +6.3% | 0 |
| 10-03 | 8 | 127 | +4.51 | 121.84 | +3.7% | 0 |
| 10-04 | 6 | 102 | +2.55 | 99.44 | +2.6% | 0 |
| 10-05 | 2 | 40 | +1.49 | 38.40 | +3.9% | 0 |
| 10-06 | 7 | 84 | +3.23 | 80.54 | +4.0% | 0 |
| 10-07 | 9 | 107 | -14.15 | 100.74 | -14.0% | 2 (2) |
| **total** | **239** | **1,183** | **+23.32** | **1,132.51** | **+2.06%** | **7 (4)** |

**LIFETIME live bot (09-21 .. 10-08 03:50Z, 16 ET days with a settled leg): 239 legs in 169 races, +$23.32 on
$1,132.51 bet = +2.06% on money bet; 5 losing races (2 of them two-way ties), money lost -$20.26; $1.46/day = 3.6%/day
of the $40 open cap (shares the $989 main account, so no pot of its own).** 4 earlier hand/penny legs (09-06..07):
-$0.03. The 10-07 4:00 PM ET race was a SOL/HYPE tie: SOL NO 20 @ 91c and HYPE YES 20 @ 90c both paid 50c, -$16.44 =
11 days of its income, and it wiped the whole 20-a-leg-with-cap period: **since v-race20cap (10-03 06:16Z, 5.1 days):
26 races, 31 legs, -$4.23 on $422.96 (-1.0%), 1 losing race.**

| period | days | races/day | $ bet / race | $/day | fill (contracts got / asked) |
|---|---|---|---|---|---|
| 1 a leg (09-21..24) | 3.3 | 25.9 | 1.58 | +0.33 | 94 per 100 |
| 5 a leg | 2.6 | 14.9 | 6.13 | +2.97 | 91 |
| 10 a leg | 0.9 | 4.6 | 13.98 | +4.06 | 58 |
| 20 a leg | 2.4 | 3.8 | 16.28 | +3.01 | 46 |
| 40 a leg | 2.7 | 2.2 | 22.24 | +2.90 | 31 |
| 20 a leg, $40 cap (10-03..) | 5.1 | 5.1 | 16.27 | -0.82 | 53 (97-98c: 67; 90-96c: 40, 10 of 24 orders empty) |

Price paid: 98c on 155 of 239 legs (median 98c); the cheap legs (90-96c) are the photo finishes.

**Known bugs / events:** the daystate file was written for the first time at the 10-07 tie loss (loss_day 10-07,
1 loss, not halted) -- v-race-daystate's first live test passed. The 10-07 12:15Z race sat 'pending' 49 min with
$17.64 held until Kalshi's row arrived (won +$0.34). Stop-on-first-loss was replaced by 2-a-day (v-race40); the
10-07 tie did not halt the day.

---

## 4. Weather dip-seller (subaccount 3, `research/sweep/dipsell_live.py`, $50) and the rain paper desk

What it does: when a daily-high temperature bracket's hourly-candle mid drops 10c+ in one hour (new mid 15-85c, 50+
contracts traded, 6-12 h to close, 18 cities), it rests a sell of 2 YES at the post-drop ask + 1c for 3 h and holds
fills to settlement. Max 5 open, one order a market ever, -25%/day stop, kill if negative after 60 fills, 14 days /
100 fills.

| ET day (market date) | markets | contracts | $ net | $ bet | % on bet | lost |
|---|---|---|---|---|---|---|
| 10-04 | 4 | 8 | +1.64 | 4.36 | +37.6% | 1 |
| 10-05 | 5 | 10 | -0.40 | 6.40 | -6.3% | 2 |
| 10-06 | 4 | 7 | -1.51 | 4.51 | -33.5% | 2 |
| **total** | **13** | **25** | **-0.27** | **15.27** | **-1.8%** | **5** |

**LIFETIME (10-04 07:57Z .. now, 4 days): 13 markets settled, 25 contracts, -$0.27 on $15.27 bet = -1.8% on money
bet, 5 of 13 lost; $50 -> $44.81 cash + $4.92 in 5 open 10-07 positions = $49.73 = -0.5% of the pot.** Its own
`--report`: 43 triggers, 25 sent, 18 filled (72 in 100 of sent; 42 in 100 of triggers), net -1.08c a contract, low
end of the range -12.2c, worst day -3.0% (10-06). Bar: fills >= 50% of triggers FAIL (42%), net > +4c FAIL, low end
> 0 FAIL, no day worse than -25% PASS; kill clause needs 60 settled fills (13 so far). The 10-07 read said +$1.58; the
four 10-06 settlements since were 2 won, 2 lost (-$1.51). Rails: `max_open` (5) refused 14 triggers (3-6 a day since
10-05), `one_per_market` 4. 3 Kalshi rejections (2 the '.'-in-ticker client-id bug, fixed 10-04 19:20Z; 1 post-only
cross). Fills come in a median 7 min; drop-hour volume at triggers median 909 contracts.

**Rain paper desk (`research/sweep/rain_paper.py`, PAPER, pid 1804636 since 10-03 14:39Z):** buys 25 NO as a taker
against a 3-10c YES bid 22 h before close on KXRAIN. 293 market-looks, 177 had no bid at all in the rung, **5 paper
fills, 2 settled (MIN 10-05, HOU 10-06), 0 lost, +3.70c a contract at the 25-lot = $1.85.** Bar (due 11-02): net
>= +1.5c at the 25-lot, no day with >= 3 losses, forecast gate removes <= 30% of eligible cities (would remove 1 of
5). Depth at the 5 fills: 1,057 / 264 / 188 / 53 / 26 contracts. The candle study behind it (rain-weekly, due 10-10):
309 markets, 7 losses (2.3 in 100), +2.79c a contract; needs 400+ markets and 15+ Oct/Nov dates before any money.

---

## 5. Other paper desks and recorders (one line each)

- **Clean-room paper ladder** (`locked_average_ladder_re_paper.py`, 100 a bid x 3 rungs, pid 132712; restarted
  10-04 13:50Z, which reset its counter): 09-27 13:47Z..10-04 13:45Z +$444.40 unkind, then 10-04..now +$254.83 =
  **+$699 unkind / +$1,650 kind over 11.8 days, 0 losing fills in 143 filled markets; top rung alone +$303 on 15,036
  contracts.** ALIVE. Paper, tape population.
- **Clean-room bettor/forecaster/contrarian paper** (`bettor_paper.py`, cleanroom-bettor.jsonl, pid 1469140, since
  09-28 03:05Z): at paper size over 10.3 days bettor_real +$23.73, contrarian_real +$41.90, forecaster_real -$121.38.
  ALIVE, all three tiny or negative.
- **cleanroom-forecaster.jsonl / cleanroom-contrarian.jsonl** (the original 09-28 clean-room paper bots): DEAD since
  09-28 18:19Z (fc_real +$171 at stop; contrarian +$2.50).
- **fcvar-paper.jsonl** (16 forecaster variants, 09-29..10-06 19:05Z, ended): base -$786, every variant negative
  except p95 +$58. DEAD (run ended).
- **fcvar-paper-crash / -early / -quiet** (alive, pids 3973524 / 2001272 / 1687992): see section 2 -- only the
  race+crash gated variants are positive at paper size (+$28..+$101 over 5.5-6.1 days); base -$281..-$931.
- **HYPE shadow** (`research/hype_shadow.py`, PAPER, loss side optimistic; due today 12:00Z): since v-skiphype 10-05,
  arm-0925b 18 HYPE markets, 18 won, +$51.07 on $821 bet (+6.2%); twin old log 6 won +$6.48 (the relaunched twin log
  is still not read by the script). No paper HYPE loser yet.
- **Polymarket US recorder** (`polypaper.py`, polypaper-20260928T034725Z.jsonl): bar read 10-01 -> STOP (sure side
  offered <= 98c in 6 of 100 windows; paper 16 entries -$1.63). DEAD by its bar.
- **PortWatch** (portwatch-rec-20261006.jsonl): bar 2 FAIL 10-06 (1 market with $20+ of true-side asks, bar 3). DEAD.
- **Coin race paper arms** (pinracearm-20261001T0742*.jsonl, 250 a leg, ended 10-04): the tau-30 / 2c-edge arm 13
  paper races, 13 won, +$265; every fill assumed. DEAD (run ended). The race-z3 earlier-entry arm failed its bar
  09-28 (2 losses in 163 races).
- **bettor-live** (subaccount 2, 09-29 00:21..00:50Z): 0 orders, replaced by the forecaster. DEAD.

---

## Scalability -- the evidence, bot by bot

**Ladder: SUPPLY-limited above ~5x, CAPITAL-limited right now; the one with a measured path to more.**
- It already takes only 7% of the contracts that print at its price (3-20% by day), so there is supply it does not
  get -- but that supply is shared with the queue ahead (median 58 contracts ahead at placement) and fills on 98c
  bids are rare (1.8 fills per 100 bids).
- The paper ladder at 100 a bid (20x) is the project's own measurement of a bigger bid (paper, tape population: a
  print at/through our price after the queue ahead = a fill). Per top-rung fill event it would get E[min(5, fill)]
  = 3.6 contracts at size 5, 10.2 at size 25, 16.0 at size 100 -- so **5x the size buys about 2.8x the contracts,
  20x buys about 4.5x per event**. By the day (same decisions, same days 09-30..10-07): paper-100 1,511 top-rung
  contracts/day unkind vs the live process's size-5 twin 108/day = 14x for 20x the size; live gets 73% of its
  twin's contracts (642 vs 878). So **20x the size would plausibly fill ~700-1,000 contracts a day (10x today's
  71) = $14-20/day at 2c, on a pot of about $1,400** (the 10 x size contract rail at 100 = $980 resting, 70%-of-pot
  rule); **5x = ~200 contracts/day = ~$4/day on a ~$350 pot.** Capital is the binding rail today: pot/14 sizing only
  reaches 6 at $84 and 10 at $140, and the live pot grows $1.44/day.
- Not supply-limited at 5 (124 of 127 filled orders got the full 5). The queue-ahead share grows with size, so these
  are upper bounds; the 73% live/twin ratio is the only live-vs-paper fill calibration and it comes from size 5.
- Risk is the unmeasured part: 0 losses in 113 markets cannot distinguish "edge" from "1 loss in 50" (10 in 100
  chance of this run at break-even). One losing close at 20x = 100 contracts x 98c = -$98 = 5 days of the 20x income.

**Forecaster: ADVERSE-SELECTION-limited beyond ~5x; the paper says its ungated engine LOSES at 8x the size.**
- Fill share is flat across order sizes 1-11 (83-91%), displayed depth median 45 / 75th pct 146 contracts at its
  triggers: 2-5x the current 13-per-side is within the usual depth; 20x (250 per side) exceeds it on 80%+ of triggers.
- The same decisions at 100 per side on the paper's 1-s rule lost -$177 on the 74 markets where live made +$28 (13 vs
  11 losers): bigger size means paying the displayed price for everything still there, which is the collapsing-offer
  population the live IOC under-pays (4c mean improvement) and the crash guard refuses. The live variant at paper
  size on the side-by-side paper: +$99 in 5.5 days (28 mk, 4 lost, worst day -$87) -- about 8x today's $2.79/day
  with a worst day equal to a month of live income. All four ungated/quiet variants at paper size: -$281..-$1,005.
- Verdict: 5x is plausible on the gated variant only (paper-backed, 28 markets, worst day -$87); 20x is not
  reachable (depth) and the engine's record at size is the losing side of this family. The +8% lifetime rests on 74
  markets with a -$4.61 and -$3.12 day and 5 both-sides losers; the +25% since r28 is 15 markets.

**Coin race: SUPPLY- and RACE-limited already at 20 a leg; capital is not the constraint.**
- Contracts got / asked fell 94 -> 91 -> 58 -> 46 -> 31 per 100 as the size went 1 -> 5 -> 10 -> 20 -> 40; at 20
  with the cap 53 (97-98c legs 67, cheap 90-96c legs 40 with 10 of 24 orders empty -- other buyers take the cheap
  offers 1-6 s first, RACE_WHY_2026-10-02). Races a day fell 26 -> 15 -> 5 as the 97-98c offers thinned market-wide.
- The paper arm at 250 a leg sees median 362 contracts "buyable" (since 10-03), but its population is "an offer was
  seen", and the live 40-a-leg test (31 per 100 filled, $2.90/day vs $3.01 at 20) already measured that doubling the
  size did not raise income. 5x (100 a leg) would plausibly fill 20-30 contracts a race, i.e. no more money, with a
  full lost leg at -$90+ (one tie at 20 cost $16.44 = 11 days). 20x is not fillable.
- Verdict: do not scale; the $/day ceiling at any size has been $3-4, and the last 5 days are -$0.82/day.

**Dip-seller: RAIL-limited (5 open, 2 contracts) and unproven; supply at 10 contracts unmeasured.**
- 11 triggers a day; 14 of 43 refused by the 5-open cap; fills 72% of sent orders in a median 7 min; the drop hour
  trades a median 909 contracts, so 10-20 contracts a trigger likely exist at ask+1c -- but the bot logs no depth, so
  that is a guess. The record itself is -$0.27 on 25 contracts with 5 of 13 lost; the bar's own kill test needs 60
  fills (another ~2 weeks). Nothing to scale until it is positive.

**Rain paper desk:** supply-limited by construction (177 of 293 looks had no bid in the 3-10c rung; depth at the 5
fills 26-1,057 contracts, so 25 lots fit, 500 would not on 4 of 5). n = 2 settled; no verdict.

**Clean-room paper ladder (20x, 3 rungs) is the largest paper number on the box (+$59/day unkind, 0 losing fills in
143 markets over 11.8 days) and is the same engine as the live ladder, which is the only side bot whose live fills
have matched its paper to the penny. It is paper: tape population, and the live/twin ratio of 73% at size 5 is the
only calibration.**

---

## Ranked by % return on money at risk (live money only; paper desks excluded)

| rank | bot | % on money bet | lifetime n | lost | % of pot / day | days | note |
|---|---|---|---|---|---|---|---|
| 1 | Forecaster (sub 2) | **+8.0%** on $349 | 74 markets / 62 closes | 11 (-$33.53) | +3.5%/day of $79 | 10 | +25% since r28 on 15 markets; two -$3..-$5 days; both-sides losers -$21 |
| 2 | Ladder (sub 1) | **+2.06%** on $629 | 113 markets / 110 closes | 0 | +1.8%/day of $78 | 9 | fixed 2c a contract; 0 of 113 is not yet proof vs 1-in-50 |
| 3 | Coin race (main) | **+2.06%** on $1,133 | 239 legs / 169 races | 5 races (2 ties) | +3.6%/day of the $40 cap | 16 | -1.0% on $423 since the $40 cap (26 races); one tie = 11 days |
| 4 | Dip-seller (sub 3) | **-1.8%** on $15 | 13 markets | 5 | -0.1%/day of $50 | 4 | bar fails 3 of 4 clauses at n=13; kill test at 60 fills |

By dollars a day: forecaster $2.79, race $1.46 (last 5 days -$0.82), ladder $1.44, dip-seller -$0.07. By how far the
evidence says it can go: ladder (paper-backed to 20x with a stated calibration) > forecaster (paper-backed to ~5-8x on
the gated variant only) > coin race (measured NOT to scale at 2x) > dip-seller (nothing to scale yet).
