# C2-confidence-flat -- REPRODUCE verifier

Status: COMPLETE (2026-09-22). Read-only. Own code only, under scratchpad
`map/verify2/C2-confidence-flat-reproduce/` (`build.py`, `calib.py`, `cuts.py`, `more.py`).
No tape read, no replay, python < 100 MB.

Claim: on our fills the loss rate is ~2.5% and flat across model-confidence bands (99.5% to
99.9%+), 9x what the model implies; confidence does not pick losers (AUC ~0.53), the price
paid does (~0.73); raising --pin would cut trades without cutting losses.

## Verdict: WEAKENED

The headline numbers reproduce exactly. Three parts do not hold as stated:

1. **02's confidence-band table double-counts.** It sums to 757 markets / 20 losses against its
   own total of 747 / 19. A market is counted once in every band one of its fills landed in
   (10 markets span two bands). One loser, NEAR 09-08 20:45 ET (`KXNEAR15M-26SEP082045-45`), is
   counted in both 98-99% and 99.75-99.9%. Correct middle band: **3 of 154 (1.95%)**, not 4 of 160
   (2.50%). Its ledger dollars are double-counted the same way. So the neat "2.55 / 2.50 / 2.48"
   is partly an artefact. The corrected figures are 2.59 / 1.95 / 2.49: still no trend.
2. **"Flat" is a failure to find a difference, not proof of none.** Loss rate in the top band
   (>=99.9%) minus the bottom band (99.5-99.75%): 95% interval **-2.6 to +2.8 points**
   (bootstrap over closes). Model-confidence AUC 0.527, interval **0.37-0.67**. The data cannot
   tell "flat" from "the top band loses half as often". What it does show is that every band
   loses far more often than the model says.
3. **"The price paid picks losers (0.73)" relies mostly on information from after the order.**
   7 of the 19 losing markets filled 2c or more below the ask the bot saw (the book collapsed
   between the look and the order; one-sided Fisher p = 1.8e-6). Leave those 28 markets out and
   the price-paid AUC falls to **0.59**. The only price the bot knows before it sends is the ask
   it saw: AUC **0.62, interval 0.48-0.75**, which includes a coin flip. So price is at best a
   weak selector before the send. The 0.73 is mostly a signature of losing, not a forecast of it.

The "--pin" part holds in dollars, but the wording is loose. Raising the pin cuts losses in
proportion to trades: at 0.9975 it drops 8 of 17 losses. It leaves the rate unchanged
(2.33% vs 2.40%) and gives up +$302.41 of ledger profit. The top band earns the least per market
($0.25 against $0.94-1.04).

## Numbers (mine vs claimed)

Join: every `order` with filled > 0 in the 124 `pinrun-live-*.jsonl`, paired with the most recent
`signal` for the same ticker in the same file (all within 1 s; 1201 signals / 1201 orders / 426
unfilled). Confidence = `fair` for YES, 1 - `fair` for NO (pinrun `conf_of` = Phi(z), honest off).
Outcome = Kalshi `market_result` from `results/kalshi_ledger.json`; money = `pinledger.pnl`.
Prices are dollars throughout (0.0998..0.996). Unit = market (first fill), closes given.

Window 09-08 03:59 ET .. 09-22 02:29 ET (02's cut), live fills only:

| quantity | mine | 02 / 10 claimed | agree? |
|---|---|---|---|
| fills / markets / closes | 773 / 747 / 547 | 773 / 747 / 547 | yes |
| full ledger (to 09-22 04:00 ET) | 775 / 749 / 549 | 10: 775 / 749 / 549 | yes |
| losing markets (= losing closes) | 19 / 747 = 2.54% (CP95 1.54-3.94%) | 19, 2.54%, 1.5-5.4% | yes (02's upper CI end too wide) |
| losing fills | 22 / 775 = 2.84% | 10: 22 / 775, 2.8% | yes |
| model-expected losses | 2.13 (0.285%) -> 8.9x | 2.1, 0.28%, 9x | yes |
| P(>=19 if model right) | 1.2e-12 | 2e-12 | yes |
| ask-implied expected | 30.5 | 30.5 | yes |
| avg price+fee (contract-wtd) | 96.07c | 96.07c | yes |
| AUC model / ask seen / price paid (vwap) | 0.527 / 0.617 / 0.728 | 0.53 / 0.62 / 0.73 | yes |
| AUC, fill level | 0.534 / 0.618 / 0.708 | -- | -- |
| >=99.9% band | 232 mkts, 211 cl, 6 lost, 2.59%, +$57.46 | 235, 214, 6, 2.55%, +$63.81 | **no -- 02 double-counts** |
| 99.75-99.9% | 154, 148, **3 lost, 1.95%**, +$160.82 | 160, 152, **4, 2.50%**, +$119.37 | **no** |
| 99.5-99.75% | 321, 272, 8, 2.49%, +$302.41 | 322, 273, 8, 2.48%, +$303.34 | ~ |
| 98-99% / 99-99.5% | 33 (2 lost) / 7 (0) | 33 (2) / 7 (0) | yes |
| 10's z buckets (fills) | 3/42, 6/268, 6/193, 4/135, 3/137 | identical | yes |

Which is right: mine. Reproducing 02's method (a market counted in every band one of its fills
landed in) gives exactly 235/6, 160/4, 322/8, 7/0, 33/2: 757 markets, 20 losses. That count
cannot be a rate over 747 markets.

## Adversarial cuts (markets, first fill; AUC = model / ask / paid)

- conf >= 99.5% only (707 mkts, 17 lost): 0.499 / 0.606 / 0.713.
- tau <= 30 & conf >= 99.5 (505, 11 lost): 0.453 / 0.681 / 0.702. Early leg (202, 6 lost): 0.570 / 0.490 / 0.697.
- Within ask bands (confidence compared only against fills at the same price): stratified model AUC
  0.532 (4 bands) / 0.529 (1c bands). No hidden effect of confidence at a given price.
- Band x tau: >=99.9 tau<=30 2.91% (5/172); 99.5-99.75 tau>30 3.92% (4/102). Every cell has 1-5 losses. Noise.
- Loss = ledger net < 0 (hedge false alarms included): 3.88% / 1.95% / 3.43% by band. Still no trend.
- Price-through removed (719 mkts, 12 lost): paid AUC 0.590, ask 0.555, model 0.536.
- --pin raised, fills below it dropped (pin-0.995 regime, 707 mkts, +$520.68):
  0.9975 keeps 386 (9 lost, 2.33%, +$218.27); 0.999 keeps 232 (6 lost, 2.59%, +$57.46);
  0.9999 keeps 102 (3 lost, 2.94%, +$96.38).

## Cuts tried / multiple-looks bar

About 95 cells (band tables x2, 13 subsets x 3 AUCs, band x tau, 4 price strata, z buckets,
ledger-loss bands, 5 pin levels, price-through splits). Bonferroni bar ~0.0005. Clears it: the
model gap (P 1e-12) and price-through (p 1.8e-6, but known only after the fill). No confidence
cut clears it in either direction.

## Could not measure

- **Re-entry under a higher --pin.** The drop-only counterfactual assumes a refused market is
  never bought. With a higher pin, the bot might buy the same market seconds later, at higher
  confidence and a different price. The logs do not record that, so it needs the index and book
  tape per market. Not done (RAM, and the claim does not depend on it for the rate).
- Power: with 19 losers, a band difference smaller than ~2.7 points or an AUC below ~0.67
  cannot be detected.
