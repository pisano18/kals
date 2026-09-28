# SAFE0928_floor90 -- the 90c floor on the 45-second bet, with every real example

Operator, 09-28: *"for the 90c floor just do whatever makes the most and do the math on it.
Calculate for risk and check with real examples."* Read-only; nothing live changed. Times ET.
Money is Kalshi's ledger unless a row says otherwise. "A third" = 30.6 contracts (a third of
today's 92-contract bet).

## Answer, reason first

**Go to 90c, keep it at a third of a bet, and have it switch itself back to 95c after the
first loss that leaves these buys behind overall.** It is a small, positive bet: about
**+$2 to +$4 a day** if these buys lose about 3 times in 100. Each loss costs about $19 to $29.
The worst the trial can cost before it switches back is about one loss.

1. **The price the floor checks is the price we SEE, not the price we pay.** Sorted that way,
   only **1 of our 45-second losses ever came from the 90-95c band**: BTC 9/19 2:00 AM
   (-$66.34, 70 contracts). The earlier write-up also counted NEAR 9/21 12:45 PM (-$74.25).
   But the offer we saw there was **95.5c**. We paid 91.1c only because the price fell while
   our order was on its way. Today's 95c floor would have let NEAR through too.
2. **Today's seller gate would have blocked that one loss.** On BTC 9/19 the offer had been
   up 59 thousandths of a second, 72 in 100 of recent trades were sellers of our side, and
   35 s were left. All three trip the gate (it went live 09-27). It would also have skipped
   3 winners in the band (about -$6 at a third).
3. **Every 90-95c offer the 95c floor has turned away since 9/23 10:22 PM won: 14 of 14,
   by Kalshi's results.** At a third that is about **+$24 missed** in 4.5 days. These are
   offers we did NOT take, so they cannot show the bad fills (someone selling to us
   because they know better). **This is the best case, not our loss rate.**
4. **Going below 90c adds nothing.** All 10 offers at 85-90c were also over the 10c
   too-good-to-be-true cap, which stays on. None of the paper bots at 70c / 80c / 85c made
   a single 45-second buy under 95c in their first 9 hours.
5. **93c is not safer than 90c, just smaller.** The one loss was at 94.3c, which a 93c floor
   would still have allowed. Both floors break even at the same loss rate, and 90c catches
   about a fifth more offers.

## The decision math (a third of a bet, today's insurance: whole position at belief 0.40)

| | amount |
|---|---|
| win per market (average 93.5c) | **+$1.85** |
| loss per market, insured (BTC 9/19 rebuilt with today's rule: insured at 28 s for 56c) | -$16.09 |
| loss per market, insured at NEAR 9/21's real insurance price | -$22.38 |
| loss per market, no insurance at all | -$28.79 |
| **break-even** | one loss per ~11 wins: **8.8 losses in 100** insured, **6.0 in 100** uninsured |

What we have seen:

| sample | lost | loss rate | could really be |
|---|---|---|---|
| our fills with a 90-95c ask | 1 of 11 | 9 in 100 | 0.2 to 41 in 100 |
| the same, minus the 4 the seller gate would now block | 0 of 7 | 0 | 0 to 41 in 100 |
| those 7 + the 14 turned-away offers (the offers never came to us, so a floor on the truth, not an estimate) | 0 of 21 | 0 | 0 to 16 in 100 |

**What the sample can tell:** nothing better than "somewhere under about 16 to 41 in 100."
It cannot tell 3 in 100 from 12 in 100. The break-even line (9 in 100) sits inside that range.

Money per day at 90c. Offers: 1.7 a day (how often we filled under the old 90c floor) to 3.1
a day (how often the 95c floor turns them away now). At most 1 per quarter hour so far.

| true loss rate | $/day at 1.7 offers | $/day at 3.1 offers | days with 2 losses (-$38 to -$58 that day) |
|---|---|---|---|
| 0 in 100 | +$3.2 | +$5.76 | never |
| 3 in 100 | +$2.1 | +$3.8 | 4 in 1,000 |
| 6 in 100 | +$1.0 | +$1.8 | 15 in 1,000 |
| 9 in 100 (break-even) | $0 | $0 | 3 in 100 |
| 12 in 100 | -$1.2 | -$2.1 | 5 in 100 |
| 18.5 in 100 | -$3.5 | -$6.4 | 11 in 100 |

**Worst day.** No floor under 95c keeps the worst day exactly where it is. Any loss here
lands on top of whatever else that day does. With the auto-revert, the realistic extra
damage is ONE loss: -$19 typical, -$29 uninsured. Two coins crashing in the same quarter
hour would be -$58, but that has never happened in this band. For scale, one full-size
loss on today's bot is -$90 to -$132 (BTC 9/27 12:00 AM: -$131.98), and the worst recent
day was 9/26 at -$82.98.

## Recommendation, exact

- `restart_bot.ps1` line 174: `"--early-min-price", "0.95"` -> `"--early-min-price", "0.90"`.
  Leave `"--early-frac", "0.333"`, `--toxic-fresh`, `--hedge-belief 0.40` and the 10c cap
  as they are. **Never pair 0.90 with `--early-frac 1.0`:** at full size one loss is
  -$66 to -$74, which is 36 wins.
- Version entry at deploy (`v-floor90`). Revert = the same line back to `0.95`.
- **Automatic revert rule (write it before the first fill):** add up the money of every
  45-second buy whose ask was under 95c since the switch, insurance included, from the
  Kalshi ledger. If a loss pushes that total **below $0**, go back to 0.95 at once. That
  means a loss is only tolerated after at least 11 wins, which is the break-even line.
  **Scheduled read: at 30 such buys (about 10-18 days).** Keep it only if there is at most
  1 loss in the 30. The pinrun bot has no self-revert today, so this needs a watcher entry
  in `READS_DUE.json`, or a small code change, before it counts as automatic.

## 1. Our own 45-second fills while the floor was 90c (9/18 2:51 AM - 9/23 10:22 PM), with every example

Sorted by the price the bot SAW. "A third" = the same buy at 30.6 contracts with today's
insurance rule. For winners that is an upper bound: when the 30-second buy would have
bought that third anyway, the gain is only the price difference. On BTC 9/22 that is +$0.54, not +$2.52.

**Ask 90-95c: the ones the floor decides (11 markets, 1 lost)**

| close (ET) | coin | ask seen | paid | contracts | s left | result | as traded | at a third | seller gate today |
|---|---|---|---|---|---|---|---|---|---|
| 9/18 1:45 AM* | ETH | 94.0 | 93.8 | 34 | 37 | won | +$1.99 | +$1.77 | passes (offer age unknown) |
| 9/19 2:00 AM | ETH | 94.6 | 93.8 | 70 | 40 | won | +$4.05 | +$1.77 | **blocks** (sellers 96/100) |
| **9/19 2:00 AM** | **BTC** | **94.3** | **94.4** | **70** | **35** | **LOST** | **-$66.34** (no insurance: the bot's run ended 30 s before close) | **-$16.09** (rebuilt: insured at 28 s for 56c) / -$28.9 uninsured | **blocks** (offer 59 ms old, sellers 72/100) |
| 9/19 11:00 AM | BTC | 93.5 | 93.5 | 158 | 45 | won | +$9.61 | +$1.85 | passes (offer 0.9 s old) |
| 9/20 1:00 AM | XRP | 93.0 | 94.3 | 138 | 43 | won | +$7.36 | +$1.63 | passes |
| 9/20 4:30 AM | BNB | 94.8 | 95.0 | 70 | 40 | won | +$3.29 | +$1.43 | passes |
| 9/20 5:30 AM | ZEC | 92.0 | 94.7 | 71 | 37 | won | +$3.52 | +$1.52 | **blocks** (sellers 80/100) |
| 9/20 1:45 PM | NEAR | 91.3 | 91.9 | 74 | 45 | won | +$5.59 | +$2.32 | passes |
| 9/20 11:45 PM | ETH | 91.9 | 92.2 | 77 | 45 | won | +$5.61 | +$2.23 | passes |
| 9/22 6:00 PM | BTC | 91.2 | 91.2 | 27 | 32 | won | +$2.21 | +$2.52 | **blocks** (sellers 56/100) |
| 9/23 10:00 PM | ZEC | 93.6 | 93.6 | 26 | 44 | won | +$1.55 | +$1.83 | passes |
| **total** | | | | | | 1 lost | **-$21.56** | **+$2.78**; +$13.06 after the seller gate | blocks 1 loss, 3 wins |

\* bought 1:44 AM, 67 minutes before the 90c floor existed (there was no floor then).
Insurance: none of these 11 was insured live. Under today's rule only the BTC loss would
have been (rebuilt, not live).

**Ask 95c or more, but we PAID under 95c (9 markets, 1 lost).** Today's floor lets these
through, so they are not the floor's question: ZEC 9/17 9:15 PM (97.3 seen, paid 87),
HYPE 9/19 10:00 PM, HYPE 9/19 11:45 PM (won the bet, -$43.92 on the market after a false
alarm insurance at the old 0.60 trigger), BNB 9/20 7:45 AM, SOL 9/20 11:45 PM,
**NEAR 9/21 12:45 PM (95.5 seen, paid 91.1, LOST -$74.25 on the bet, -$59.09 on the
market after insurance)**, HYPE 9/23 9:00 AM, NEAR 9/25 1:15 AM (95.5 seen, paid 81),
BNB 9/27 3:00 PM. The seller gate would block 5 of the 9, NEAR 9/21 among them (sellers 53
in 100, just over the 50 line).

**Found on the way, worth its own look (identify better):** a 45-second fill that comes in
**3c or more cheaper than the price we saw** means the price was falling while our order
travelled. That happened 9 times, and **3 lost**: BTC 9/17 9:15 PM (saw 97.8, paid 53),
DOGE 9/18 12:15 AM (saw 97.6, paid 11) and NEAR 9/21 (saw 95.5, paid 91.1). Across the other 366
45-second fills, 3 lost. Small numbers, but a lopsided split. It says to check
insurance at once after such a fill, rather than to change the floor.

## 2. Offers the 95c floor turned away since 9/23 10:22 PM (4.5 days)

The market's result (Kalshi) is what the tape shows. Buys we did not make cannot show the
bad fills, so **this is a best case, never our loss rate.**

| | markets | lost | at a third | note |
|---|---|---|---|---|
| ask 93-95c | 11 | 0 | +$18.38 | XRP 9/24 3:30 PM was bought at 95c moments later anyway, so its real gain is ~$0, not +$1.45 |
| ask 90-93c | 3 | 0 | +$7.42 | BTC 9/26 10:00 AM (91.5), SOL 9/26 9:45 AM (92.0), BTC 9/27 2:30 AM (90.6) |
| ask 85-90c | 10 | 0 | $0 | every one also over the 10c cap, so still refused at any floor |

The 14 in the 90-95c band, by close: XRP 9/24 3:30 PM, BTC 9/24 6:45 PM, BTC 9/24 11:00 PM,
HYPE 9/25 7:30 AM, BNB 9/25 1:45 PM, BTC 9/25 5:00 PM, BTC 9/25 6:45 PM, XRP 9/26 5:00 AM,
SOL 9/26 9:45 AM, BTC 9/26 10:00 AM, ETH 9/26 6:30 PM, HYPE 9/27 1:00 AM, BTC 9/27 2:30 AM,
BNB 9/27 5:45 AM. All won. The records do not carry the offer's age, so we cannot say
exactly which the seller gate would stop. At most 3 (BTC 9/25 6:45 PM, BTC 9/26 10:00 AM,
BNB 9/27 5:45 AM had sellers over 50 in 100). That would be -$5.51 of the gain. Never more
than 1 of these in the same quarter hour.

## 3. Paper bots since 9/28 1:21 AM (9 hours)

| bot | settled markets | lost | 45-s buys under 95c | vs the 95c twin (arm-live-hedge20), same markets |
|---|---|---|---|---|
| arm-floor90 | 10 | 0 | **0** | +$3.07 vs +$6.84 (9 markets) |
| arm-floor85 | 10 | 0 | **0** | +$5.01 vs +$6.90 |
| arm-floor80 | 10 | 0 | **0** | +$3.09 vs +$5.33 |
| arm-floor70 | 9 | 0 | **0** | +$3.43 vs +$5.33 |
| arm-floor90-full | 10 | 0 | **0** | +$5.30 vs +$6.90 |

**No answer yet.** Not one floor bot has used its lower floor, so every gap in the table
is noise between bots that made the same choices: $2-4 in 9 hours. The twin insures at 0.20,
not 0.40, but none of these markets needed insurance. Live made +$14.03 on the same 8
markets. The paper bots bet 20 contracts until 9:16 AM against live's 92, so paper-vs-live
dollars mean nothing here.

## 4. The seller gate on the 45-second leg

It now runs on every entry with more than 20 s left, so it covers this whole leg. In the
90-95c band it would have blocked **the only loss** (BTC 9/19) and 3 winners (-$5.81 at a
third). It would also block NEAR 9/21, the other big 45-second loss, which the floor
cannot touch. For the pre-9/24 fills, the seller share is rebuilt from the recorded trade
tape: the 3 s before our own fill, which we found on the tape. Checked against the 2 fills
where the bot logged it: 0.99 vs 0.99 and 0.24 vs 0.33. The offer ages are the bot's own
logged values.

## Method, files

Scripts (stdlib, one at a time, each under 300 MB, self-tests pass, including an empty
world that must return nothing):
`scratchpad/safe0928/floor90/extract.py` streams every `pinrun-live-*` since 09-09
(including the restored 09-25 12:23Z log) and the 10 paper logs of the 09-28 manifest.
`analyze.py` builds the fills, refusals, paper arms and daily totals.
`tapeshare2.py` finds our fills on the trade tape and computes the seller share.
`post.py` re-sorts by the price seen and does the decision math. Results of refused
markets come from Kalshi's ledger, the bots' settled records, and Kalshi's public market
page (read-only GET). A bug in my own first pass read UTC times one hour off (daylight
time); it was fixed and self-tested before any number here.
Halves: every example above falls in 09-18..09-28 except ZEC 9/17 and BTC 9/17 (09-09..09-17).
Before 9/18 there was no floor.
Recorders alive after the run: crypto_feeds (105352), kalshi_collector (2532788). Free disk 61.5 GB.
