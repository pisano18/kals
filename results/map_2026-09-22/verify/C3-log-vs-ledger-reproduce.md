# Verify C3-log-vs-ledger -- lens REPRODUCE (second pass, verify2)

Status: DONE 2026-09-22. **Verdict: CONFIRMED.** Every headline number reproduces from my own join, to the cent. There are five corrections to the cited reports, and none of them changes the conclusion.

Own code: scratchpad `map/verify2/C3-log-vs-ledger-reproduce/` (parse.py, join.py, days.py, legs.py, nocap.py, nocap2.py, nocap3.py, rebuild.py, explain07.py, rates.py). I ran none of the investigators' scripts. I only read 07's 21-line `nocap_check.py` to explain its number.
Sources:
- `results/kalshi_ledger.json`: 847 rows, 0 duplicate tickers. My own P&L formula equals `pinledger.pnl` on 847 of 847 rows.
- The 124 `pinrun-live-*.jsonl` files: 6 duplicate lines removed by whole-line dedupe, 0 lines that failed to parse.
- `research/pinday.py`, run unchanged, for the operator's own figure.

All 749 tickers with a filled pinrun order are in the ledger. I used no tape, no replay and no paper arms.

## Reproduced numbers

| number in claim | mine | n |
|---|---|---|
| 09-19 logs -$161.14 | **-161.14** (pinday.py today, and my own sum) | 71 markets with settled rows |
| 09-19 Kalshi -$223.46 | **-223.46** | 73 markets |
| 09-17 logs +$115.68 | **+115.68** | 53 |
| 09-17 Kalshi +$99.87 | **+99.87** | 55 |
| missing 09-19 02:00 ET: BTC -$66.34, ETH +$4.06 | -66.34, +4.06 | filled, no settled row; run's last record 05:59:30Z, 30 s before the close |
| missing 09-17 21:15 ET: BTC -$27.87, ZEC +$12.09 | -27.87, +12.09 | filled, no settled row; run's last record 01:14:26Z |
| v-nocap "136 markets, 8,671 ct, 96.87c, +$110.67, 1.5% losing" | **136, 8,671.71, 96.87c, +$110.67, 2 of 136**, exact | recipe below |
| v-nocap main window "515, 21,431 ct, 95.45c, +$441.53, 2.5%" | **515, 21,431.33, 95.45c, +$441.53, 13 of 515**, exact | same recipe |
| Kalshi, early leg, -$68.78 (01, 07) | **-68.78** on 140 markets / 102 closes | every market with a filled 31-45 s leg before the v-nocap commit (2026-09-20 09:48:22Z) |
| Kalshi, early leg, -$79.91 (10) | **-79.91** on 135 markets / 98 closes | same set minus 5 markets that also had a <=30 s leg (those 5: +$11.12) |
| "5 losing" | 5 markets net negative (-$311.03) on 4 closes; 4 where our side lost | both counts are right. DOGE 09-18 00:15 lost its side but netted +$4.36 |

**Leg-exact figure (new).** The like-for-like number for v-nocap's leg set is **-$76.03**. That is the 140 markets with the 5 mixed markets' <=30 s legs removed, using the log's split, which agrees with Kalshi on those 5 markets to $0.01. It sits inside the claim's "-$68.78 to -$79.91" range.

**Cross-check of the 11 markets with no settled row.** I rebuilt them from OUR OWN order and hedge fills, and all 11 match the ledger. BTC 09-17 21:15 matches once the hedge fee is included; only the ledger records that fee. So the ledger's -$66.34 and -$27.87 are not errors in the ledger.

**v-nocap's exact recipe (found).** It used the bot's `settled` rows for the ENTRY side only and dropped the hedge rows. It counted only markets that HAVE a settled row, and it split each market across its legs by contracts. The same recipe gives both of its tables exactly.

## Decomposition of the $179.45 gap (+110.67 -> -68.78)

| step | $ |
|---|---|
| v-nocap early legs, entry rows | +110.67 |
| + the <=30 s legs inside the 5 mixed markets | +7.24 |
| + hedge rows the bot DID log on those 136 markets (XRP -67.22 and HYPE -49.65 at 09-19 23:45 ET, false alarms; DOGE hedge +8.29) | -108.57 |
| = the log, all rows, 136 markets | +9.34 |
| Kalshi, same 136 markets | +9.29 (log agrees to $0.05) |
| + 4 markets with no settled row | -78.06 |
| = Kalshi, 140 markets | -68.78 |

**The larger part of the gap, about $101 net, comes from v-nocap's METHOD: it dropped hedge losses that ARE in the log. The other $78 is the log's OMISSION, from runs that died holding.** Where the log has rows, it agrees with Kalshi.

01 splits the gap into -$82.78 of hedges plus the missing rows. That differs from my split only in where BTC 09-17 21:15's +$26.32 hedge save is booked (mine: -108.57 + 26.32 = -82.25). The remaining $0.53 is unexplained and too small to matter.

## Differences from the cited reports, and which is right

1. **07's "+$124.14 with 1 loss" for the entry-leg rerun is wrong; v-nocap's +$110.67 is exactly reproducible.**
   - 07's rule is "entry = the settled row with the highest cost". On DOGE 09-18 00:15 it picks the HEDGE row (+$8.29) instead of the entry row (-$3.93), because the entry was bought at 11c and the hedge at 74c.
   - On 5 markets with two entry rows, the same rule keeps only one of them.
   - Applying 07's rule to my parse gives exactly +$124.14 with 1 loss.
   - 07's ledger figure (-$68.78, 5 losing) and its conclusion are unaffected.
   - 07 also labels -$108.86 as "hedge-leg costs". That figure is the two markets' NET result (XRP -64.95 + HYPE -43.92). The hedge legs alone were -$116.87.
2. **01 (-$68.78, 140 markets) and 10 (-$79.91, 135 markets) are both right; they use different sets.** 10 leaves out the 5 markets that had both an early leg and a <=30 s leg. The leg-exact figure is -$76.03.
3. **06's "the bot's books match Kalshi to the cent on every ET day except the two" is not quite true.**
   - There were FIVE runs that died holding, on four days:

     | run died (ET) | log missed |
     |---|---|
     | 09-08 11:59 | +$0.49 |
     | 09-11 21:59 | +$2.81 |
     | 09-11 23:29 | +$0.93 |
     | 09-17 21:14 | -$15.78 |
     | 09-19 01:59 | -$62.28 |

   - Days where the log and Kalshi differ:
     - 09-08: $2.77
     - 09-11: $3.75
     - 09-12: $0.69, from 4 per-ticker fill or fee mismatches of $0.26-$1.16 and 2 zero-fill rows.
   - 01 states this correctly ("differ by less than $4").
4. **The claim's "understate LOSSES" is right for the two days it names, but it is not a rule.**
   - The log drops whatever the held markets did, and 3 of the 5 omissions were small gains.
   - Nothing makes the omission systematically a loss. The 09-19 death was a `round(None)` crash in a log line, unrelated to the position.
   - Net across all five: -$73.83.
   - Lifetime, pinday says +$559.55 and Kalshi says +$487.21 for the same bot, so the log overstates by $72.34.
5. **Scope.** These are crypto-bot figures only. Account-wide, 09-17 was +$43.04 because the oil bot lost $56.84. On 09-19 no other bot settled anything.

## What this does to v-nocap's reasoning

- v-nocap said the early leg's loss rate was "1.5%, BETTER than the main window's 2.5%". On Kalshi's books:

  | comparison | early | main | p |
  |---|---|---|---|
  | side lost, main-only all history | 4 of 140 (2.9%) | 13 of 517 (2.5%) | 0.77 |
  | net negative, main-only all history | 5 of 140 | 18 of 517 | 1.00 |
  | same period since v-staged, main-only | | 2 of 61 | 1.00 |

  **"Better" does not survive, and neither does "worse". With 4 losses there is no power to tell them apart.**
- Dollars per close: early -$0.67 (102 closes, 4 losing) against main-only since v-staged +$0.90 (54 closes, 2 losing). I did not test this for significance. 4 and 2 losing closes are far under the 30-close floor.

## What would make this an artefact, and checks
- **Ledger P&L wrong on hedged markets (the `revenue: 0` bug).** Checked. Where the log has rows it matches Kalshi to $0.05 over 136 markets, including all 3 hedged ones, and the 11 no-row markets match our own fills.
- **Wrong leg labels.** Checked: `leg == "early"` exactly when `tau_at_send > 30`, on every filled order, by date.
- **Duplicate or missing settled rows inflating pinday.** Checked: log and ledger differ by more than $0.01 on only 4 of 738 matched tickers, less than $3 in total.
- **Cutoff choice.** At the commit time the 136 markets, 8,671 contracts and +$110.67 match exactly, so this is the set v-nocap used.

## Cuts tried / multiple looks
About 55 cuts:
- 18 ET days (one table)
- a 749-ticker join
- about 17 recipe variants for v-nocap's two tables
- 12 ledger set definitions (early-only / mixed / both / main, times 3 windows)
- 4 Fisher tests
- 3 by-close summaries
- 1 rebuild of 11 markets
- 1 re-run of 07's rule

The Bonferroni bar at 0.05 over 55 looks is p < 0.0009. The headline numbers are accounting identities, not inferences, so the bar does not apply to them. The only inferential comparison (early vs main loss rate) has p >= 0.77, nowhere near any bar.

## Verdict
**CONFIRMED.**
- Logs vs Kalshi: 09-19 -$161.14 vs -$223.46, and 09-17 +$115.68 vs +$99.87. Both are exact. The whole gap is the 4 markets held when a run died on those two days.
- v-nocap's +$110.67 on 136 markets reproduces exactly from the log. On Kalshi's books the same leg was -$68.78 (140 markets, 5 net losers), -$76.03 leg-exact, or -$79.91 early-only.

Corrections:
- About $101 of the $179 gap is v-nocap dropping hedge rows the log DID contain; the log itself was not wrong there.
- The omission is not systematically a loss: 3 of 5 were gains.
- 07's +$124.14 comes from a bug in 07's rerun.
- 06's "to the cent on every other day" misses three small died-holding gaps.

Housekeeping (read-only checks): both recorders are alive (2 python processes matching kalshi_collector / crypto_feeds). Free RAM 1,764 MB, free disk on C: 30.44 GB. No process touched.
