# C5-fresh-offer -- ALTERNATIVE-EXPLANATION verifier

**Verdict: WEAKENED.** The loss-rate pattern survives every other explanation
tried. The dollar headline does not: about 40% of the +$268.72 is not caused by
fresh offers. The early-leg cut was made after looking.

Sources: live logs `results/pinrun-live-*.jsonl` (1,201 signal/order pairs, all
paired; 775 filled orders) and Kalshi's ledger `results/kalshi_ledger.json` via
`pinledger.load_cache/pnl`. No tape and no replay were used. Own code:
`scratchpad/map/verify2/C5-fresh-offer-alternative/` (`build.py`, `a1.py`..`a6.py`).
Python used under 100 MB. Nothing was edited except this file.

## 1. Reproduction (exact)

Early-leg fills, 2026-09-17 13:29Z .. 2026-09-22 07:44Z:

| level age | fills = markets | closes | lost | naked $ |
|---|---|---|---|---|
| < 250 ms | 86 | 73 | 6 | -221.44 (80 winners +139.18, 6 losers -360.62) |
| >= 250 ms | 117 (claim said 116; one new fill since) | 101 | 0 | +202.77 |

- Ledger, markets where every fill would be blocked: 83 markets, **-$268.72**. The rule's claimed value is reproduced exactly.
- Fisher one-sided p = 0.0052 (fills). At close level it is 6/73 vs 0/101, p ~ 0.005.
- The 6 losers had level ages of 15, 57, 59, 75, 81 and 89 ms. The claim's "15-89 ms" is correct.
- 03's all-buys figure also reproduces: since 09-18, < 100 ms, 79 closes, 7 lost, -$257.75.

## 2. Alternative explanations tested: none removes the rate gap

Each row is a stratified exact test. Within each stratum the fresh/old split is held fixed; p = P(fresh fills carry at least 6 losses | no age effect).

| stratified by | expected fresh losses if no effect | p |
|---|---|---|
| none | 2.54 | 0.0052 |
| ET day | 2.72 | 0.0073 |
| calm 09-17/18 vs 09-19+ | 2.57 | 0.0056 |
| coin | 3.19 | 0.0107 |
| BTC vs other | 3.26 | 0.0173 |
| day x BTC | 3.45 | 0.0264 |
| price seen (4 bands) | 2.56 | 0.0048 |
| day x price (above/below 97.5c) | 2.90 | 0.0103 |
| model risk (1 - confidence) | 2.49 | 0.0047 |
| spot-to-strike distance | 2.87 | 0.0100 |
| tau (31-37 / 38-45) | 2.58 | 0.0057 |
| tau 45 (window opening) vs later | 2.86 | 0.0093 |
| tau-45 x day | 3.06 | 0.0147 |
| contracts filled | 2.40 | 0.0034 |
| ET hour block | 2.81 | 0.0099 |
| index age at the decision | 2.77 | 0.0080 |

- The fresh share was ordinary on the losing days: 40% on 09-19 and 58% on 09-21, against 35-41% on the other days.
- Medians, fresh vs old: price 97.5c vs 97.6c; risk 0.22% vs 0.28%; distance 4.7 vs 5.1 bp; size 71 vs 77; edge 2.04c vs 2.00c. Regime, coin, price, confidence, size and time of day do not explain the gap.
- **Same-close stratification is uninformative (p = 1.0).** None of the 6 losing closes held an old early fill. Two of them held another coin's fresh early fill that won (ZEC 09-17 21:15, ETH 09-19 02:00).

Where the evidence thins:
- **Leave any one loss out:** 5/85 vs 0/117, p = 0.012.
- **Drop the two 09-19 BTC markets (bug-enlarged losses):** 4/84 vs 0/117, p = 0.029.
- **Drop ET 09-19:** 4/66 vs 0/87, p = 0.033.
- **Drop both losing days (09-19 and 09-21):** 2/48 vs 0/74, **p = 0.15**.
- **Non-BTC only:** 3/63 vs 0/108, p = 0.049. BTC early fills are 72% fresh (23 of 32), against 37% for the other coins.
- **Exact ages only:** 6/86 vs 0/43, **p = 0.083**. 74 of the 117 "old" fills sat on levels already present at subscription (age is a lower bound). Those are legitimately old, so the rule itself is unaffected. But levels the bot actually watched appear, at 250 ms or older, number only 43.

## 3. The dollar headline is overstated

- **$108.86 of the $268.72 is two hedge false alarms whose ENTRIES WON:** XRP 09-19 23:45 ET (-$64.95) and HYPE 09-19 23:45 ET (-$43.92). The rule does block them, since no position means no hedge. Under today's hedge (v-hedge25), 04/10 estimate that close at about -$35 to -$70 (tape).
- **$174.29 is the two 09-19 BTC markets:**
  - 02:00 ET (-$66.34): the loop crash, since fixed, cost about $29-31.
  - 16:00 ET (-$107.95): the paused hedge, fixed by A69, cost about $16-25.
- **Re-priced on today's code:** the rule is worth about **+$139 to +$184**, not +$268.72.
- **Largest ledger losses removed cumulatively:** 1 -> +$160.77; 2 -> +$94.43; 3 -> +$29.49; **4 -> -$29.61**. The dollars rest on 3-4 markets.
- **DOGE 09-18 00:15** counts as an entry loss (a 97.6c signal filled at 11c), but it is **+$4.36 on the ledger** because the hedge won. So there are 5 losing markets on the ledger, not 6.
- **Break-even:** a fresh early winner makes $1.74 and a loser costs $60.10, so fresh early fills break even at a 2.8% loss rate.
  - Observed: 7.0% (6 of 86), 95% CI 2.6-14.6%. The lower bound sits AT break-even.
  - If fresh fills lost at the early leg's overall rate (6/203 = 3.0%), the fresh group would net about -$7.58, not -$221.44.

## 4. "Chosen after looking?" -- the number no, the leg yes

- **The 250 ms line predates the early leg.** It is a bucket edge in `RESULTS_select.md` §3b (commit b1e6037, 2026-09-12 23:47 ET), from the tape study. The first live early fill came on 09-17 at 09:29 ET, and pinrun has logged the age as "LOGGED, NEVER GATED ON" since then.
- **No pass/fail bar was ever written for it.**
- **The early-leg restriction is post hoc.** The form the line was written for, all legs, gives 10/231 vs 2/281, p = 0.0075. On the non-early legs it shows nothing:
  - fresh 4/145 vs old 2/164, p = 0.29; fresh non-early fills net positive;
  - in the early leg's own window, the full leg is fresh 2/59 (+$52.42) vs old 1/46 (+$45.40).
- **03 is NOT independent confirmation.** 6 of its 7 losing closes since 09-18 are these early-leg losses. Non-early < 100 ms since 09-18: 35 closes, 1 lost, +$5.31.
- **Within the early leg the exact threshold barely matters** (value = ledger of fully blocked markets):

| threshold | fresh lost | p | value |
|---|---|---|---|
| 25 ms | 1/12 | 0.31 | -$26.77 |
| 50 ms | 1/39 | 0.73 | +$46.97 |
| 75 ms | 3/53 | 0.18 | +$120.66 |
| 100 ms | 6/65 | 0.0009 | +$303.71 |
| 150 ms | 6/76 | 0.0024 | +$285.90 |
| 250 ms | 6/86 | 0.0052 | +$268.72 |
| 500 ms | 6/100 | 0.013 | +$239.72 |
| 1000 ms | 6/113 | 0.028 | +$204.31 |
| 5000 ms | 6/122 | 0.045 | +$194.49 |

- **The shape is non-monotonic:**

| age | fills | lost |
|---|---|---|
| 0-50 ms | 39 | 1 |
| 50-100 ms | 26 | 5 |
| 100-250 ms | 21 | 0 |

  - The age histogram of all fills peaks at 10-60 ms, consistent with the bot firing on its first 50 ms loop pass after a new offer appears. On that reading, 0-100 ms is one class ("the offer came to us"), and a 0-50 vs 50-100 gap is noise or something unexplained.

## 5. Supporting signatures (post-fill, so not usable as a gate, but they fit the mechanism)

- **All 6 hedged early-leg markets were fresh-level fills; 0 of 117 old fills were ever hedged.** That is 4 losers plus 2 false alarms.
- **All 7 early price-through fills (filled 2c or more under the ask seen) were fresh; 0 of 117 old.**
- In both, the book or the index turned against us after a fresh fill and never after an old one. That fits "someone just repriced on information" better than any regime explanation.

## 6. Cuts tried and the multiple-looks bar

- About 34 cuts (42 if each threshold counts separately): 16 stratifications, 7 exclusions/leave-outs, the age bins, the 9-threshold sweep, 4 leg splits, same-close, the hedge / price-through / tau-45 / histogram checks, and 03's 100 ms re-split.
- **Bar: 0.05/34 = about 0.0015.**
- **Nothing here clears it except the post-hoc 100 ms cut (p = 0.0009).** That cut was picked from the losers' ages, so it does not count.
- The claim's p = 0.005 counts as one look only if "early leg" had been pre-specified, and it was not.
- Every test rests on 6 losing closes, under the 30-close floor.

## 7. What would settle it (live, no code change)

- Pre-register now: on the next 60 early-leg fills on levels under 250 ms, compared with the old-level early fills over the same period.
  - **Bar:** 3 or more lost closes among the fresh fills AND 0-1 among the old, with fresh naked dollars below 0.
  - **Blocks:** nothing until the bar is met.
- A gate built from it may touch only the early leg's entry, never a hedge or a top-up.
- At about 17 fresh early fills a day, the bar takes 3-4 days.
