# C5-fresh-offer -- ARTEFACT lens verifier

Status: COMPLETE (2026-09-22). **Verdict: WEAKENED.** Own code, no investigator scripts reused:
scratchpad `map/verify2/C5-fresh-offer-artefact/{extract,a1_basic,a2_tests,a3_strata,a4_trigger}.py`.
Sources: all 124 `results/pinrun-live-*.jsonl` (1,204 signal->order pairs, 776 filled entry orders,
live logs up to 2026-09-22 ~09Z), `results/kalshi_ledger.json` via `pinledger.pnl`. No tape read.
At finish: kalshi_collector (pid 105304) and crypto_feeds (pid 105352) alive, 30 GB free disk, 1.4 GB free RAM.

## Claim under test
Early-leg (31-45 s) buys on offers <250 ms old lost 6 of 86 vs 0 of 116 older; skipping them = ~+$268.72 ledger.
03 found the same shape at <100 ms across all buys since 09-18. Is it real or a threshold chosen after looking?

## Reproduction -- the counts are real
- Early leg, level <250 ms: 86 fills = 86 markets = **73 closes, 6 lost closes**, naked entry -$221.44.
- Early leg, >=250 ms: 117 fills = 117 markets = **101 closes, 0 lost**, naked +$202.77 (claim said 116; one fill settled since).
- Ledger, markets whose every fill is early <250 ms: 83 markets, **-$268.72** -> the claim's +$268.72 reproduces exactly.
- 03's since-09-18 <100 ms, all legs: 79 closes, 7 lost, -$257.75 -- reproduces exactly.

## Artefacts listed, and what each check found
| # | artefact | checked? | result |
|---|---|---|---|
| 1 | leg attribution | yes | clean: 203/203 `leg=early` fills have tau 31-45; no tau>30 fill is labelled anything else |
| 2 | a market (or close) in two groups | yes | 0 markets in both; 24 closes in both, none of them a losing close |
| 3 | hedge legs mis-assigned / entry vs ledger outcome | **yes (test 2)** | see below -- changes the dollars, not the count |
| 4 | markets missing from the logs | yes | 80 ledger markets since the early leg began have no logged fill; ALL are WTI/GOLD/Coin-Race, none is a crypto pin market |
| 5 | clustering by close | yes | 6 losers in 6 distinct closes; n=6 losing closes, below the 30 floor |
| 6 | selection by what filled | yes | fresh signals fill 83% vs old 94%; 3 of 6 losers are price-through fills (exec 0.53/0.11/0.911 vs ask 0.978/0.976/0.955) |
| 7 | threshold / subgroup chosen after looking | **yes (test 1)** | see below -- the main weakness |

### Test 1 -- threshold and subgroup chosen after looking
- **The 250 ms line is pre-dated: CONFIRMED.** `RESULTS_select.md` 3b (tape, commit b1e6037, 09-13 03:47Z) and the logging commit
  df2c5f3 (09-13 04:06Z) both predate the first early-leg fill (09-17 13:29Z). The commit itself says the tape slice was
  "picked after seeing the tape", so 250 ms is a tape-derived hypothesis and live fills are out of sample for it.
- **The EARLY-LEG restriction was NOT pre-registered.** The pre-registered form (all legs, 250 ms) on live closes:
  fresh 9 of 188 lost vs 2 of 229, p = 0.014 -- and **in dollars it is flat: fresh -$6.93 naked vs older +$450.99.**
  On the non-early legs age does not separate (3/124 vs 2/141, p = 0.44) and skipping fresh there costs $214.52.
- **Inside "<250 ms" the losses are NOT where the mechanism says they should be.** Early-leg sub-buckets (closes, lost):

  | level age | closes | entry-lost | ledger-lost | naked $ | ledger $ |
  |---|---|---|---|---|---|
  | 0-50 ms | 36 | 1 | 1 | +64.28 | -41.94 |
  | **50-90 ms** | **22** | **5** | **5** | **-324.71** | **-260.62** |
  | 90-250 ms | 24 | 0 | 0 | +38.99 | +38.87 |
  | >=250 ms | 101 | 0 | 0 | +202.77 | +206.31 |

  The freshest offers (0-50 ms) are fine; the one entry loss there (DOGE 09-18 00:15) netted **+$4.36** on the ledger,
  and the one ledger loss there is a hedge false alarm on a winning entry. Five of six losses sit in a 40 ms band. At a
  <50 ms threshold the split is 1/36 vs 5/128, p = 0.78. Any threshold from 90 ms up gives "0 older losers", so 250 does no work;
  the robust fact is "all 6 early losers were 15-89 ms". Nothing logged (index age, book age, send latency) marks the 50-90 ms band
  as mechanically different (medians 0.32 s / 6 ms / 100 ms vs 0.26 s / 4 ms / 94 ms for 0-50 ms).
- **03's "same shape" is not a second confirmation.** Since 09-18, <100 ms, non-early legs: 1 lost of 35 closes, +$5.31.
  The 7 fresh losers 03 counted include the same 6 early-leg closes. Before 09-18, <100 ms all legs: 1 of 73, +$143.05.

### Test 2 -- hedge legs and the ledger
- Ledger-losing markets: fresh group 7 (6 closes), older group 0. The ledger does not rescue the old group -- the split holds.
- But the +$268.72 is made of: 6 entry-lost markets -$288.16 (one of them +$4.36), **2 WINNING entries whose hedges fired falsely
  (XRP and HYPE 09-19 23:45) -$108.86**, and 75 winners forgone +$128.30. **40% of the rule's value is hedge false alarms** on
  one close under the pre-v-hedge25 trigger, not fresh-offer losses. Without them: about +$160.
- 3 of the 6 entry losses ($82.60 ledger) are price-through fills (book collapsed between decision and arrival). Excluding
  price-through fills: 3 of 68 closes vs 0 of 101, p = 0.063.

### Strata (does it survive?)
Same direction everywhere, all tiny: tau 45 1/20 vs 0/52; tau 31-44 5/58 vs 0/58; BTC 3/23 vs 0/9; non-BTC 3/57 vs 0/95;
early-frac 0.333 era 2/18 vs 0/33; frac 1.0 era 4/55 vs 0/68. BTC is 27% of fresh fills vs 8% of old.

## Multiple looks
I cut the data 46 ways (a1 1, a2 17, a3 20, a4 4, since-09-18 split 4). Bonferroni bar at 0.05: **p < 0.0011**.
The claim's p (6/73 vs 0/101 closes) = **0.0048 -- does not clear it**; 10's own ~35 cuts give 0.0014, also not cleared.
Only the 90-100 ms cuts reach p ~0.0011-0.0013, and 90 ms was chosen by me from the loser ages -- that is the look-after bias itself.

## Verdict
WEAKENED. Not manufactured by leg labels, double-counting, missing markets or hedge mis-assignment of the COUNT: the
early leg really had 6 losing closes on offers <90 ms old and none on older ones. But: (a) the early-leg subgroup was chosen
after looking and the pre-registered all-legs test is worth ~$0; (b) the losses sit in a 50-90 ms band with the freshest
offers clean, the opposite of the proposed mechanism; (c) 40% of the $268.72 is two hedge false alarms on winning entries;
(d) p = 0.005 misses the multiple-looks bar; (e) 6 losing closes, under the 30 floor. It is a forward-test hypothesis,
not a result. Honest dollar claim: skipping early buys on <250 ms offers would have been +$160 to +$269 over 83 markets
(09-17 13Z .. 09-22), resting on 6 losing closes, at the cost of 75-80 winners (+$128-139).

## Validation that would settle it (live fills only)
Pre-register BEFORE reading: next 60 early-leg closes with a fill on a <250 ms exact level; also record 0-50 vs 50-250.
Bar: >= 4 lost closes and naked $ < 0 in the <250 group while >=250 stays <= 1 lost -> build a "wait and re-check" skip on
the early leg only; <= 1 lost -> drop. A gate here blocks only early-leg entries; it must never touch the hedge path.
