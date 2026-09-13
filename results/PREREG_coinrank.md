# PREREG -- is any coin genuinely safer than the others?

Written 2026-09-13, BEFORE any coin-priority rule is deployed. The operator's
proposal: "order the coins in order of safest to most dangerous then set it up
in that order for buying... some coins really do seem much much safer."

## What was measured, and why it is NOT deployed

422 book hours, 16,683 candidate rows, budget rule at size 68, 886 fills, 18
losses (2.03% overall). Per CLAUDE.md rule 5 this is a TAPE comparison of
populations against each other -- valid for ranking coins, never quotable as
our loss rate.

**1. The spread is what chance produces.** Best-to-worst spread is 4.12 pp
(BTC 0.00%, HYPE 4.12%). Simulating 20,000 draws where every coin shares one
2.03% rate, a spread that big or bigger appears **53.0% of the time**. There
is nothing here to rank.

**2. The ranking does not persist.** Ranked on the first 13.5 days and checked
on the last 5.1, the rank correlation is **+0.35 on 9 coins** -- with n=9 that
is not distinguishable from zero. Individual reversals are total:

| coin | first 13.5 days | last 5.1 days |
|---|---|---|
| SOL | 0.00% (40) | **6.67% (30)** |
| ZEC | 3.85% (52) | **0.00% (13)** |
| XRP | 2.47% (81) | 6.82% (44) |
| NEAR | 1.37% (73) | 5.00% (20) |

**3. The rule was tested out of sample and failed non-monotonically.** Rank on
the first period, trade the second:

| holdout rule | fills | loss% | $/day@70% |
|---|---|---|---|
| all coins (today) | 281 | 2.85% | 17.65 |
| drop the 1 riskiest | 253 | 2.77% | 19.09 |
| drop the 2 riskiest | 241 | 2.90% | 14.49 |
| drop the 3 riskiest | 206 | 3.40% | 13.04 |
| only the 4 safest | 168 | 3.57% | 12.19 |
| only the 2 safest | 105 | 1.91% | 20.93 |

If safety ranking worked, dropping riskier coins would improve the result
monotonically. It goes up, down, down, down, then up. **The one coin the
ranking genuinely staked itself on -- SOL, ranked 3rd safest on zero losses in
40 fills -- became the WORST coin of the holdout at 6.67%.** "Only the 2
safest" scoring best is an endpoint of a non-monotone curve, which is how a
cherry-pick looks.

**4. Two zero-loss coins out of nine is ordinary luck.** At the 2.03% base
rate the expected number of coins showing zero losses is **1.32**; we observed
2 (BTC 0/138, BNB 0/100). P(2 or more by luck) = **38%**.

This is the same shape as the withdrawn "SOL's feed is the calmest" claim
(2026-09-12), which turned out to be a quantization artefact.

## THE BAR -- what would change this verdict

Set before the evidence exists, and it is about ONE coin, not a ranking.

A coin earns a priority only when it accumulates **147 FORWARD fills with ZERO
losses**, counted from 2026-09-13 and from live fills only. 147 is the point
at which a clean record's Clopper-Pearson upper bound falls below the 2.03%
base rate -- i.e. the first sample size at which "this coin is better than
average" is a statement the data can support rather than a streak.

- Fills before 2026-09-13 do NOT count. They are what generated the
  hypothesis and cannot also test it.
- A single loss resets that coin's counter to zero.
- Clearing the bar earns PRIORITY (first claim on the close's contract
  budget), never exclusivity -- nothing gets dropped, because point 3 shows
  dropping coins is what actually cost money.
- If no coin clears it by 2026-10-13, the idea is struck.

## What IS deployed instead

Nothing coin-specific. The contract budget (AMENDMENT 17) already captures the
useful half of the operator's instinct -- more coins per close, capped on
total exposure -- without needing to know which coin is safer.
