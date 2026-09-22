# Verify C1-early-leg -- lens: ALTERNATIVE EXPLANATION (verify round 2)

**Verdict: WEAKENED.** Status: COMPLETE (2026-09-22 ~09:40Z).
Own code: `scratchpad\map\verify2\C1-early-leg-alternative\` (build.py, a1_reproduce.py,
a2_alt.py, a3_crowd.py, a4_cf.py, a5_era.py; outputs a2/a3/a4/a5_out.txt). Money = Kalshi ledger
via `pinledger.pnl`; leg timing = live `order` records (`tau_at_send`); side = `want`, else
`body.side` (bid=yes, ask=no; older records have no `want`). Tape not read. No process touched.
Window: markets whose first fill is >= 2026-09-17 13:05Z (v-staged). **E** = early-only markets
(every fill at 31-45 s, 197), **L** = late-only (every fill <= 30 s, 90), 6 mixed set aside (+$12.46).

## 1. The numbers, reconciled -- one series cut on different windows

| figure in the reports | what it is (reproduced) |
|---|---|
| -$57.38 (09) | 203 markets with ANY early fill, 150 closes |
| -$59.00 (01/02/07) | the same set one ledger refresh earlier (202 markets) |
| **-$69.84 (10)** | 197 early-ONLY markets, 145 closes -- exact |
| -$65.41 (01 text) | early legs + their hedges, leg-level; I get -$63.80 to date. 01's own day table sums to +$68.62 through 09-21, so 01 is internally off by ~$3 |
| -$96.48 (05) | only the hours with early_frac 1.0 |
| -$108.01 (07) | since full size 09-18 16:33Z |
| -$140.88 / -$144.21 (09 / mine) | 09-19..09-22 closes only |

**Counterfactual "no early leg" (ledger, drop early legs + their hedges), per ET day:**
09-17 -$20.03, 09-18 -$58.88, **09-19 +$174.62** (-$223.46 -> -$48.85, 01 reproduced exactly),
09-20 -$74.21, 09-21 +$47.12, 09-22 -$4.83. **Total +$63.80** (drop early-only markets: +$69.84 =
10 exactly; drop any-early markets: +$57.38). **01 and 10 do not disagree**: 01's -$48.85 is 09-19
alone; 10's +$69.84 is the whole window. The early leg lost $174.62 on 09-19 and MADE $110.82 on
the other five days combined (it lost only on 09-21).

Claim details checked:
- "5 of 8 losing markets since 09-19, -$373.52, 76%": the dollars are **6** early markets
  (BTC 02:00, BTC 16:00, XRP 23:45, HYPE 23:45 on 09-19; NEAR 12:45, HYPE 18:15 on 09-21).
  "5" is 5 of 7 losing CLOSES. -$373.52 of -$493.03 = 76% is right.
- Margin/loss share in 09-19..22: E 96.89c avg, 3.11c margin, 3.65% of contracts on a lost side
  (10: 3.09c / 3.61%) -> below break-even. L: 4.06c margin, 3.56%. Reproduced.
- "Does not lose more often": by market, our side lost in 5 of 197 E (2.5%) vs 2 of 90 L (2.2%). Reproduced.
- "<=30 s net positive in the same days": true over 09-19..22 (+$31.37 on 58 mk), **false on 09-19
  itself** (late -$50.63 on 23 mk).
- early_frac 1.0 since 09-18 16:33Z confirmed from `start` records (also 09-17 19:41Z..09-18 01:48Z).

## 2. Alternative explanations tested

**A. Two fixed bugs carry the net sign -- CONFIRMED as an alternative for the NET LOSS.**
- 09-19 early net = -$174.83. The two bug losses on 09-19 = -$174.29: BTC 02:00 ET (-$66.34; no
  `settled` row, no hedge record, the run ended ~06:00Z holding it = the crash) and BTC 16:00 ET
  (-$107.95; `pause` record at 19:59:15Z, the same second as the fill, "loss bound ... $107.80
  still open"; no hedge record = the pause skipped the hedge).
- Leave out ONLY BTC 16:00: the early leg goes from -$69.84 to **+$38.11** (196 mk). Leave out both
  bugs: **+$104.45**. Also leave out the two false-alarm hedges (full-size hedge policy since
  replaced by A76; both bets won): +$213.31.
- Each single early loss left out alone: -$3.50 to -$41.97 -- only BTC 16:00 flips the sign alone.

**B. The GAP to the late window survives every cut -- the alternative does NOT explain it.**
E minus L, dollars per market: base -1.67; leave-k-out k=1..9 always negative (-0.44 to -1.52);
all bug/policy losses removed -0.72 (CI [-2.22,+1.19]); same day 4 of 5 full days negative
(09-20 +0.18); same 25 closes -0.92 (E better in 7 of 25); 5 of 6 hour bands; 8 of 9 coins (BNB the
exception); all 3 volatility bands; 3 of 4 settings eras. After the fixes (09-20 04:00Z on):
**E +$30.62 on 69 mk / 54 closes (+0.70c/contract, 2 losing) vs L +$81.99 on 35 mk / 31 closes
(+3.92c/contract, 0 losing)**; bootstrap by close -1.90 $/mk, CI [-4.26,-0.09], 1.5% of draws E>=L.

**C. Market regime (calm 09-17..18 vs 09-19+) -- does not explain the gap.** On the calm days E was
positive (+$74.37, 79 mk) but still under L (+$86.90, 32 mk; -1.77 $/mk). Signal sigma relative to
the coin's median: E underperforms L in low, mid and high bands; on 09-19 E's median relative sigma
was LOWER than L's (0.81 vs 0.97).

**D. Coin mix -- partly.** BTC early: -$150.77 on 30 mk, 3 losses; but all 3 BTC losses are the two
bugs and the 53c fill before the 90c floor. Excluding BTC: E +$80.92 (167 mk, +0.48/mk) vs L +$79.14
(79 mk, +1.00/mk).

**E. Bet size -- confounded with the bugs.** E markets >= 100 contracts: -$134.76 (28 mk, 3 losses,
all 09-19: BTC 16:00, XRP, HYPE). Under 100 contracts E beats L per market (+$64.91 on 169 vs +$5.27 on 65).

**F. Cheap early buys.** E markets averaging < 95c: 16 mk, -$125.70, 4 of the 7 E losses (BTC 53c,
BTC 94.4c crash, HYPE 94.1c false alarm, NEAR 91.1c). Post hoc; overlaps 07's v-cheap bar.

**G. "It pays more" is a between-market effect, not the same market bought dearer.** Aggregate
winners' price E 97.05c vs L 96.22c. Within the SAME close (25 closes holding both): E minus L
winners' price mean +0.55c, **median -0.08c**, E dearer in 11 of 25. Late-only markets are a
different population (not buyable at 45 s); their cheap late prices cannot be assumed available
on the markets the early leg buys.

**H. Crowd-out -- not supported, not refuted.** `close_budget` refusals at <= 30 s per close with a
fill: 1.19 BEFORE the early leg existed (270 / 226 closes, 09-12..09-17 13:05Z) vs 0.66 after (133 /
202); 111 of the 133 are in 34 closes where the early leg had filled. Budget rules changed in between
(A56/A59/A64) and the gate fires before the book is read, so these refusals cannot be valued. Late
contracts per close fell 60.5 -> 35.6 while total rose 60.5 -> 99.3; in the same E markets, 124 of
197 hit `no_offer`/`price_ceiling` at <= 30 s at least once.

## 3. Corrected claim
The early leg's NET loss (-$57 to -$108 by window) is the 09-19 day, and that day's early loss equals
two since-fixed bugs (-$174.29 of -$174.83); drop the single BTC 16:00 pause loss and the leg is net
positive over the whole window. What is robust is that it earns LESS than the <= 30 s window --
after the fixes +0.70c vs +3.92c a contract, +$30.62 on 69 markets vs +$81.99 on 35 -- in every cut
tried, but that gap is not past the multiple-looks bar, rests on 2 vs 0 losing markets, and the
"pays more" part is a population difference, not a same-market price difference. Counterfactual:
01 (-$48.85 on 09-19) and 10 (+$69.84 whole window) are both right; to date the no-early-leg gain is
+$63.80 to +$69.84, all of it from 09-19.

## 4. Cuts and multiple looks
~78 looks (60 table cuts in a2, 5 bootstraps, 4 crowd-out, 3 counterfactual variants, 4 eras +
paired + cheap bucket). Bonferroni bar ~0.05/78 = 0.0006. Nothing clears it except
"excl 09-19" (0 of 4000 bootstrap draws E>=L), which was chosen after seeing 09-19, so it is not
counted as passing. Losing-market counts (7 E, 2 L) are far under the 30-close floor.

## 5. Could not measure
- What the <= 30 s window would have bought on the 197 E markets without the early leg (needs the
  book -> tape/replay = hypothesis).
- The dollar value of the 133 `close_budget` refusals (gate fires before the book read).
- What working hedges would have recovered on BTC 02:00 and 16:00. CURRENT_STATE's 57c-vs-86c per
  contract would put the two near -$103 instead of -$174 -- an estimate, not a measurement.
