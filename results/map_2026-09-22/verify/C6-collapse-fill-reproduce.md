# C6-collapse-fill -- REPRODUCE verifier

Status: **COMPLETE** (2026-09-22). Read-only. Own code only:
`scratchpad/map/verify2/C6-collapse-fill-reproduce/{extract,analyse,hedges,split,tapehedge,tradehedge}.py`.
At finish: kalshi_collector (105304) and crypto_feeds (105352) alive, disk 30.5 GB free, RAM 1.58 GB free.

## Verdict: CONFIRMED on the loss rate; the -$270.91 is WRONG (03's -$85.91 is right); an immediate hedge CANNOT be priced from what we have.

## 1. The join

- All 124 `pinrun-live-*.jsonl`: 1,201 `order`, 1,201 `signal`, **775 filled entry orders**
  (09-08 07:59Z .. 09-22 07:59Z). Every order paired to the signal before it; `ask_seen` on the order equals the
  signal's `price` in all 497 orders that carry both (0 mismatches). Every filled market has a ledger row and a
  Kalshi `market_result`. Units: exec 0.0998..0.996, ask 0.53..0.996 -- dollars throughout.
- Money = `pinledger.pnl` per ticker. For all 28 flagged markets, the exec price equals Kalshi's own
  cost/count for our side (0 contradictions).
- Cutoff for reproducing the reports: 09-22 06:30Z -> 773 fills / 747 markets / 547 closes.
  (2 fills after it; neither is under the ask.)

## 2. Every headline number, recomputed

| report | claim | mine | verdict |
|---|---|---|---|
| 03 | ">2c": 28 orders, 27 closes, 7 lost; vs 12 of 520 closes; naked -102.99; ledger -102.69 | exactly that, but it is **>=2c** (includes BNB 09-12 at exactly -2.00c, a winner). Strict >2c: 27 / 26 / 7, ledger -105.51 | right, label loose |
| 03 | since 09-14 12:54Z: 14 mkts, 13 closes, 4 lost, -$116.73 | -116.72, 14 / 13 / 4 | right |
| 10 | 7 of 28 fills vs 15 of 747, p = 4e-6; >=10c: 6 of 9 | 7/28 vs **15 of 745** other fills (747 = all markets); p 4.4e-6 fill-level; >=10c 6 of 9 | right, denominator mislabelled |
| 04 | >=3c: 7 of 23 (22 closes) vs 12 of 724; net -$113.18 | exact; -$113.18 is the NAKED entry figure; ledger -$112.87 | right, $0.31 labelling |
| 02 | >5c: 6 of 15 lost, entry -$67.33, ledger -$32.51 | floating-point edge: strict >5c = 14 / 6 lost / ledger -35.52; >=5c = 16 / 6 / -25.63. 02's 15 counts ETH 09-12 (0.89-0.84, exactly 5c) and drops BNB 09-10 (0.69-0.64, exactly 5c, +$6.88): -25.63 - 6.88 = -32.51 | lost count 6 in every version; the 15 is a float artefact |
| 08 | since 09-19 22:29Z: 6 mkts, -$270.91; other 120 mkts -$19.27 | **-$85.91** and **+$139.73** | **WRONG** |
| 03 | same window: 6 mkts, 1 lost, -$85.91 | exact | right |

### Why 08 is wrong (reconciled to the cent)
Kalshi's ledger row has `revenue: 0` whenever we held BOTH sides (a hedged market) -- `pinledger.payout()`'s
docstring documents exactly this trap. 08 used `revenue`. On the two flagged hedged markets:
- HYPE 23:45 ET 09-19: true -$43.92; revenue-based 0 - 97.864 - 47.840 - 2.213 = **-$147.92** (the gap is its $104 payout)
- NEAR 12:45 ET 09-21: true -$59.09; revenue-based **-$140.09** (gap $81)

-85.91 - 104 - 81 = **-270.91**. The same bug drives 08's "other 120 markets -$19.27": XRP 23:45 ET 09-19
(-64.95 true vs -168.95) and HYPE 18:15 ET 09-21 (-31.27 vs -86.27) -> true figure **+$139.73**.
08's p = 0.011 counts net-negative markets, so it survives the fix, but one of its two "bad" markets is a
WINNING entry that lost its money on a hedge false alarm (HYPE); only 1 of 6 entries lost.
Also: `want` (not `ask_seen`) is what first appears 09-19 22:29:15Z; `ask_seen` has been on orders since
09-13 10:14Z and before that equals the signal's `price`. 08's window was needlessly narrow.

## 3. Is the pattern real? (adversarial checks)

Per close, lost / flagged closes vs lost / closes with no flagged fill, >=2c:

| slice | flagged | others | one-sided Fisher p |
|---|---|---|---|
| all, to 09-22 06:30Z | 7 / 27 (26%) | 12 / 520 (2.3%) | 1.1e-5 |
| 09-08 .. 09-13 04:14Z (20-contract era) | 3 / 13 | 5 / 188 | 0.010 |
| 09-13 04:14Z .. 09-19 22:29Z | 3 / 8 | 6 / 255 | 0.0014 |
| 09-19 22:29Z .. 09-22 06:30Z | 1 / 6 | 1 / 77 | 0.14 |
| early leg | 3 / 6 | 3 / 143 | 0.0007 |
| full leg | 1 / 5 | 1 / 75 | 0.12 |
| fills >= 40 contracts | 3 / 12 | 6 / 276 | 0.004 |
| >=3c | 7 / 22 | 12 / 525 | 2.3e-6 |
| >=10c | 6 / 8 | 13 / 539 | 2e-8 |

- Same direction in all three disjoint periods. Control, the other direction: fills >=2c DEARER than seen
  lost 1 of 23 closes -- no elevation, so this is not "any big move between look and fill".
- Artefacts checked: exec prices = Kalshi cost/count on all 28 flagged markets; outcomes from Kalshi
  `market_result`; units decided from the whole sample; one close counted once (09-18 01:14Z BTC + ZEC).
- **Cuts tried: ~52** (7 thresholds x 4 windows, 4 close-disjoint repeats, 10 splits/controls, 10 hedge-pricing
  variants). Bonferroni bar 0.05 / 52 ~= **0.001**. The all-time, >=3c, >=10c and 09-13-onward rows clear it;
  the recent window (p = 0.14) and the full leg do not. n is under the 30-close floor in every flagged row.
- Dollars: lifetime -$102.69 ledger on 28 markets, beside +$587.67 on the other 719. Since 09-19 22:29Z:
  -$85.91 on 6, beside +$139.73 on 120. The 7 losing entries cost -$171.25 ledger; the 21 winners +$68.57.

## 4. Could an immediate hedge on this signal be priced? NO, not from anything we have.

- **Live logs: no.** Nothing records the insurance (other-side) price at the fill second. The `signal`
  ladder is our side's asks only; `close_summary`, `sweep_depth`, `dumped` carry nothing on the other side.
  The only live insurance prices are the 5 flagged markets that alarmed, 1-16 s later (BTC 09-17 21:15 ET
  72c at +4 s; DOGE 09-18 74c at +1 s; BNB 09-19 01:45 ET 51-76c at +3..5 s, 1 contract; HYPE 09-19 46c at
  +4 s; NEAR 09-21 70c/90.5c at +13/+16 s). The 23 others -- 21 of them winners, i.e. the COST side of such
  a hedge -- have no insurance price in any live record.
- **Tape (what the market did, not our loss rate): the answer flips sign with the assumptions.** 28 flagged
  markets, actual ledger -$102.69; counterfactual = entry + hedge of the whole fill at the fill response + D.

| source / assumption | total | vs actual |
|---|---|---|
| ticker top-of-book, D 100 ms, full size | +68.84 | +171.53 (**artefact**: quotes up to 1.2 s stale, pre-collapse; DOGE 09-18 "insurance 4.6c" right after we were filled at 11c) |
| ticker, D 500 ms, full / top size only | -0.41 / -81.10 | +102.28 / +21.59 |
| ticker, D 1000 ms, full / top size only | -97.39 / -152.02 | +5.30 / -49.34 |
| trade tape, insurance-side taker trades in 1 s, remainder at last price | -76.43 | +26.26 |
| same, 3 s | -68.99 | +33.70 |

  10/D1's "+$8 (tape, optimistic)" sits inside this range (close to my ticker D=1000 full-size +$5.30) but it
  is one point on a curve that runs from -$49 to +$102. All are hypotheses: n = 27 closes, our own order
  would have competed with the takers it is priced against, and the one flagged false alarm (HYPE 09-19,
  104 contracts) alone moves the total by $15-35.
- What would price it: log the other side's best ask and size at the instant each fill response returns
  (04's solution 3 -- no new reads, no gate, blocks nothing). ~30 flagged closes at the current rate of
  about 2 a day is ~2 weeks.
