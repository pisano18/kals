# Verify C1-early-leg -- lens ARTEFACT

**Verdict: WEAKENED.** Status: DONE 2026-09-22 ~09:45Z.
Own code: scratchpad `map/verify2/C1-early-leg-artefact/` (load.py, build.py, s1-s7.py). No investigator script reused.
Sources: `results/kalshi_ledger.json` via `pinledger.pnl` (last settlement 09-22 08:00:58Z) and the 124
`pinrun-live-*.jsonl`. Window: entry fills from 2026-09-17 13:05Z (v-staged) to the ledger's last row.
No tape, no replay. Collectors and the live bot alive at the end (read-only process list); free RAM 1.44 GB, disk 30.5 GB.

## One-paragraph answer
The dollar figures are real and every report's number reproduces to the cent under its own definition; the
reports do not disagree with each other. But "the early leg is the main bleed because it pays too much for its loss
rate" is not what the ledger shows over the whole window. The early leg's own BUYS are at break-even
(-$18.67 on 12,871 contracts, -0.15c a contract; margin 3.55c against 3.49% of contracts lost). The negative comes
from hedges on early positions (-$45.12 net), and ONE close -- 09-19 23:45 ET, two bets that WON, false-alarm hedges
cost -$116.87 -- flips the early leg from +$45 to -$64. Clustered by close, early minus late is -2.23c a contract,
95% [-5.86, +1.42], 12% chance early is actually better: not established. The "3.09c vs 3.61%" is one window (C, from
09-19 00:00 ET); in that same window the <=30 s buys are also near break-even (+0.27c a contract, 4.01c vs 3.48%).

## Reconciliation -- which numbers are right (all of them, for different things)
| figure | where | definition | my number |
|---|---|---|---|
| -$57.38, 203 mkts / 150 closes | 09 | markets whose FIRST fill was at 31-45 s | -$57.38 / 203 / 150 (exact) |
| -$59.00, 202 mkts / 149 closes | 02, 05, 07 | same, one market fewer (earlier ledger refresh) | -- |
| -$69.84, 197 mkts | 10 | markets with ONLY early fills | -$69.84 / 197 / 145 closes (exact) |
| -$65.41 | 01 | early LEGS + hedges on them (leg-level) | -$63.79 (01 includes the whole 09-17 ET day) |
| 09-19 -$223.46 -> -$48.85 | 01 | one ET day of the leg-level subtraction | -$223.46 -> -$48.85 (exact) |
| +$69.84 "saved" | 10 row 5 | same as -$69.84 above, sign flipped | same |
| -$108.01 / -$96.48 | 07 / 05 | later window starts (09-18 16:33Z / early-frac 1.0 hours) | -$110.65 early-only from 09-18 16:33Z |
- 01's -$48.85 is ONE DAY; summed over all days 01 and 10 give the same answer, ~$64-70 saved, differing only by the
  6 mixed markets (+$12.46, all won, none hedged).
- **None of them is a counterfactual.** All assume the money would have sat idle. The close budget refused 118 other
  markets in 35 of the 150 early closes (23%), but that gate runs before the offer/edge gates, so how many of those
  would have been bought, and at what result, is not in the logs.
- **"5 of 8 losing markets" is a miscount: it is 6 of 8 markets (5 of 7 closes).** The -$373.52 is right: BTC 02:00
  -66.34, BTC 16:00 -107.95, HYPE 23:45 -43.92, XRP 23:45 -64.95, NEAR 09-21 12:45 -59.09, HYPE 09-21 18:15 -31.27.
  Two of those six are WINNING bets (hedge cost only), and two more ran with no hedge because of since-fixed bugs
  (crash; loss-cap pause), -$174.29 together.

## Artefacts listed, and what was checked
| artefact | checked? | result |
|---|---|---|
| leg attribution (label vs seconds-to-close) | yes | 203/203 early labels == tau 31-45; rebuilt entry legs match the ledger within 5c on EVERY unhedged market |
| one market in two groups | yes | only 6 mixed markets, +$12.46 -> cannot move the sign |
| markets missing from the logs | yes | 0 pin-series ledger markets without a logged fill; 1 logged market (HYPE 09-22 05:15 ET) not yet in the ledger |
| **hedge legs charged to the early leg** | **TESTED (1)** | **drives the sign -- see below** |
| **clustering by close / small n** | **TESTED (2)** | **not significant -- see below** |
| window chosen after looking | yes (7 starts) | the break-even-failure mechanism holds only from 09-18 16:33Z onward |
| selection by what filled | not testable from live logs | early-only vs late-only are different market populations (late-only = not taken at 31-45 s); no fix without tape |

### Test 1 -- hedge legs attributed to the early leg
- Early legs: ENTRY **-$18.67** (-0.15c/ct, 12,871 contracts) + their hedges **-$45.12** = -$63.79.
- Late legs: ENTRY +$104.29 (+1.45c/ct, 7,192 contracts) + hedges +$20.44 = +$124.73.
- Hedges on early positions: false alarms -$116.87 (XRP, HYPE 09-19 23:45; both bets won); saves +$72.46
  (BTC 09-17 +26.32, DOGE 09-18 +8.29, NEAR 09-21 +15.15, HYPE 09-21 +22.70).
- Removing the 09-19 23:45 close alone turns the early leg to **+$45.07**.
- Is the attribution itself wrong? Not simply: those alarms fired at 30-31 s (hedges bought at 29-30 s), a wobble only
  a position bought at 31-45 s was holding through. So charging them to the early leg is defensible for "turn it off".
  But the cause is early exposure TIMES that day's hedge rule (trigger 0.6, full size); under today's rule (none above
  40% belief, half at or under 40%) HYPE (belief 0.50) would not have been hedged and XRP (0.27) only half -- a
  reading of the rule, not a measured dollar figure.

### Test 2 -- clustering by close (bootstrap, 10,000 draws, 203 closes resampled together)
- Early legs incl. hedges: 95% [-$460, +$246], P(>0) = 0.40. Entry only: [-$382, +$263], 0.48.
- Early minus late, c/contract: incl. hedges -2.23c [-5.86, +1.42], P(early better) = 0.12; entry only -1.65c [-5.36, +2.41], 0.20.
- Early margin minus lost share: +0.16c [-2.77, +2.26] -> "below break-even" NOT established.
- Early losing closes: 5 of 145 (early-only); late: 2 of 81. Below the 30-event floor on both sides.

### Window dependence
| start | early mkts/closes | early mkt net | early entry c/ct | early margin / lost | late mkts | late net | late entry c/ct | late margin / lost |
|---|---|---|---|---|---|---|---|---|
| 09-17 13:05Z | 197/145 | -69.84 | -0.15 | 3.55 / 3.49% | 91 | +118.33 | +1.45 | 3.93 / 2.23% |
| 09-17 19:41Z | 184/134 | -78.34 | -0.22 | 3.58 / 3.59% | 85 | +102.10 | +1.31 | 3.96 / 2.39% |
| 09-18 16:33Z | 141/105 | -110.65 | -0.28 | 2.96 / 3.04% | 68 | +50.44 | +0.60 | 3.91 / 3.06% |
| 09-19 00:00 ET (C) | 118/89 | -144.21 | -0.72 | **3.09 / 3.61%** | 59 | +31.42 | +0.27 | 4.01 / 3.48% |
| 09-19 05:08Z | 117/88 | -145.65 | -0.75 | 3.10 / 3.65% | 57 | +22.27 | +0.08 | 3.92 / 3.59% |
| 09-20 00:00 ET | 69/54 | +30.62 | -0.13 | 3.12 / 3.04% | 36 | +82.05 | +3.92 | 4.19 / 0% |
| 09-20 09:48Z | 62/47 | +10.06 | -0.68 | 3.04 / 3.52% | 30 | +69.50 | +3.93 | 4.21 / 0% |
- Over the whole window the entry gap (1.6c/ct) is mostly MORE contracts lost (3.49% vs 2.23%) plus 0.38c higher
  price (96.45c vs 96.07c) -- the opposite of "does not lose more often, it pays more". In C it is the other way round.
  Neither is significant.
- The early leg's ENTRY c/ct is at or below zero in every window (-0.13 to -0.75c) -- the one consistent sign here,
  and it is small.

## Cuts and the multiple-looks bar
~33 cuts: 3 market groupings, 1 first-fill grouping, 6 ET days, 2 entry/hedge splits, 5 bootstrap statistics,
1 leave-one-close-out, 7 window starts x 2 legs, 1 crowd-out count. Bar at 33 looks: p < 0.05/33 = 0.0015.
No test here reaches p < 0.05 even as a single look.

## Corrected claim
Since 09-17 13:05Z the early leg's markets are net negative on Kalshi's ledger (-$57 to -$70 depending on
definition; -$145 from 09-19) while <=30 s markets are +$118. The reports agree; 01's -$48.85 is one day of the same
~$64-70. The negative is carried by hedges and bugs on early positions, not by the early buys: early entries are
break-even over the whole window (-$18.67 on 12,871 contracts), and one close of false-alarm hedges on two winning bets
(-$116.87) decides the sign. Early vs <=30 s is not statistically different (P = 0.12). No figure measures what the
later window would have bought instead, so "turning it off saves $70" is a floor-free guess, not a measurement.

## Could not measure
- What the <=30 s window would have bought on early-leg markets (needs the book: tape/replay = hypothesis).
- Whether the 118 close-budget-refused markets would have passed the other gates.
- The dollar effect of today's proportional hedge rule on the 09-19 23:45 close (would need the book at 29-30 s).
