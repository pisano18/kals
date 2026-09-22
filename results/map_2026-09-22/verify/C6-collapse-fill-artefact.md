# C6-collapse-fill -- ARTEFACT lens verifier

Status: COMPLETE (2026-09-22). Read-only. Own code:
`scratchpad/map/verify2/C6-collapse-fill-artefact/{load,a1..a5}.py`.
Sources: all 124 `results/pinrun-live-*.jsonl` (1,204 orders, 776 filled,
775 with a settled ledger row), `results/kalshi_ledger.json` via
`pinledger.pnl`. No tape read. Units: dollars (exec 0.0998-0.996, seen
0.53-0.996, decided on all 776 fills).

## Verdict: WEAKENED

The count is real and survives every artefact check. The dollars in 08 are a
known bug. And "loses far more often" is mostly the price we paid: these fills
lost about as often as their own fill price said they would.

## Evidence

### E1. The dollar disagreement is one known bug, reconciled to the cent
08's -$270.91 minus 03's -$85.91 = exactly -$185.00 = 104 + 81 contracts of
payout. The two losing markets are hedged (both sides held):
KXHYPE15M-26SEP192345-45 (104 YES + 104 NO) and KXNEAR15M-26SEP211245-45
(81 + 81). Kalshi writes `revenue: 0` when both sides are held;
`pinledger.payout()` exists for exactly that reason. With `revenue`:
HYPE -$147.92 (08: "-$148"), NEAR -$140.09 (08: "-$140"). With the payout:
HYPE -$43.92, NEAR -$59.09. **03 is right.** Same bug on 08's other side:
"the other 120 lost $19.27" is revenue -$17.05 / payout **+$141.95** on 122
markets (2 more markets have settled since 08 ran).
Own join, window since 09-19 22:29Z, >= 2c under: 6 markets, **1 entry lost**
(NEAR), ledger -$85.91. HYPE's entry WON (+$5.74 naked); its -$43.92 is a
hedge false alarm, so 08's "2 bad of 6" counts one hedge loss as a fill loss.

### E2. Reproduced counts (fills >= 2c under the ask seen, lifetime)
28 fills / 28 markets / 27 closes, 7 lost (7 distinct closes, 6 distinct
days). Rest: 747 fills / 721 markets / 522 closes (exclusive), 12 lost closes.
One-sided Fisher on closes p = 1e-5. Matches 10 (7/28 vs 15/747), 04 (>=3c:
7/23), 02 (>=5c: 6/16; two fills sit at exactly 5.00c, so ">5c" vs ">=5c"
moves n by up to 2), 03 (7/27 closes).

### E3. ARTEFACT TEST 1 -- leg attribution / exec price / missing markets: CLEAN
- All 28 exec prices checked against Kalshi's own per-side cost: count and
  cost of OUR side match filled x exec on 28 of 28 (worst 0.9c on $75).
  E.g. BTC 09-18 YES 99 @ $52.47 = 0.53; DOGE 09-18 YES 33.63 @ $3.70 = 0.11.
- `order` records are entries only (hedges log as `hedge`); side from
  signal, order and request body agree on 776 of 776 fills.
- Signal pairing checked: where the order carries its own `ask_seen` (599
  orders), the paired signal's price agrees on 599 of 599.
- No market has fills in both groups. 12 below-ask closes share a close
  with other markets; none of those other fills lost.
- Ledger 15M rows missing from the logs: 61, all commodity (WTI/GOLD/
  NATGAS/COPPER), pre-live August, or ~$0 pin rows. No losing pin market is
  missing.

### E4. ARTEFACT TEST 2 -- the fill price itself: THIS IS THE PROBLEM
A fill at 53c is a bet the market already rates as a coin flip. Comparing its
loss rate with 97c fills compares different bets. Loss count against the
price actually PAID (Poisson-binomial, p_i = 1 - exec):

| group | fills | lost | expected at price paid | expected at ask seen | expected at model | P(>= obs) at paid |
|---|---|---|---|---|---|---|
| >= 2c under | 28 | 7 | 6.4 | 2.9 | 0.05 | 0.45 |
| >= 10c under | 9 | 6 | 4.2 | 1.5 | 0.02 | 0.14 |
| rest | 747 | 15 | 27.4 | 28.8 | 2.16 | 0.997 (far FEWER) |

- Dollars: naked -$102.99 on the 28; if each had lost at its paid-price rate,
  mean -$11.55 (fees), and P(<= -$102.99) = 0.18. Not unusual.
- Price-matched bands: 5 of the 7 losers are fills under 80c (expected 4.06,
  saw 5). At 80-95c: below-ask 2 of 20 (expected 2.27) vs rest 3 of 141.
- Only surviving residual: normal fills lose at 0.55x their price. If
  below-ask fills did the same, expect 3.49 losses; saw 7, P = 0.037 --
  does not clear the multiple-looks bar below.
- So: the market knew before our model did, and it was already in the price
  we paid. What these fills lack is the edge normal fills have, not a loss
  beyond their price.

### E5. Threshold after looking: count robust, dollars not
Same 7 losers at 1c, 2c and 3c; 6 at 5c and 10c. Ledger $ by threshold:
1c -$70.98, 2c -$102.69, 3c -$112.87, 5c -$25.63, 10c -$73.57. The 5c cut
drops both recent big losses (HYPE 3.4c, NEAR 4.4c). Loss next to its return:
at 2c, 21 winners +$68.56, 7 losers -$171.25.

### E6. Can an immediate hedge be priced from what we have? No live price; only a bound
- Logs: `signal.ladder` is our side's asks before the send; `order` has no
  book. The other side's price exists only when an alarm fired -- 5 of 28
  markets, 1-16 s after the fill. For the other 23, nothing.
- Those 5 live hedge prices vs 1 - exec at the fill: BTC 72c vs 47c
  (2 s, after cancels at 63c and 66c), BNB 76c for 1 of 76 vs 25c (gave up),
  HYPE 46c vs 5.9c, NEAR 70c/90.5c vs 8.9c (13-16 s), DOGE 74c vs 89c. A
  price 1-2 s later is not an immediate price.
- Bound from the fill: at the fill instant our side's bid < exec, so the
  hedge costs > 1 - exec. Best case on the 28 (hedge at 1 - exec, 1 tick,
  fee): +$92.16 - $10.89 fee - $7.97 tick = **<= +$73 lifetime**, on the
  realized outcomes. Expected, if the fill price is fair as E4 shows:
  **about -$19** (fee + tick). Actual hedges on these 28 already net +$0.30.
- The tape could rebuild the other side's book at the fill millisecond (what
  the market showed), but not whether our order would have filled there --
  the same race we just lost on the entry. That is a hypothesis-grade number
  (D1 got about +$8).

## Artefacts listed
1. Leg attribution (hedge counted as entry) -- tested E1/E3: present in 08
   (HYPE), absent in 03/10.
2. Market in two groups -- tested E3: none.
3. Hedge legs mis-assigned / `revenue` vs payout -- tested E1: explains all
   of 08's -$270.91 and its -$19.27.
4. Markets missing from the logs -- tested E3: none that lost.
5. Selection by what filled -- considered: an IOC fills only when the book
   falls toward us, so this group IS the "market moved against us" set. That
   defines the signal rather than faking it, and for a post-fill hedge only
   filled orders matter.
6. Clustering by close -- tested E2: 7 distinct losing closes, close-level
   p = 1e-5.
7. Threshold after looking -- tested E5: count robust, dollars swing 4x.
8. (added) Price-level composition -- tested E4: the main weakening.

## Cuts tried / multiple-looks bar
About 25 cuts: 5 thresholds x (groups, dollars), 4 slip buckets, all fills,
3 periods, the 09-19 window, 5 price bands x 2 groups, 2 Fisher tests, 1
residual test, 1 dollar null. Bonferroni bar 0.05 / 25 = **0.002**. Clears:
the raw count gap (p = 1e-5). Does not clear: any excess over the price paid
(p = 0.45; residual p = 0.037).

## Corrected claim
Fills >= 2c under the ask seen lost 7 of 27 closes vs 12 of 522 (real,
p = 1e-5), but about as often as the price actually paid implied (7 vs 6.4).
Lifetime ledger -$102.69 on 28 markets. Since 09-19 22:29Z: 6 markets, 1 lost
entry, -$85.91 (08's -$270.91 is the `revenue = 0` bug). No live price exists
for an immediate hedge; the fill bounds it at <= +$73 lifetime, about -$19
expected.
