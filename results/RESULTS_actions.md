# RESULTS -- 2026-09-17 afternoon: what the grid, the pickoff tracker and the market-health work say to DO

The operator: *"Take that information and run with it. There MUST be something
actionable ... figure out how to make more money from it. Both the commodity
stuff and your findings on crypto market health/opportunity."* Everything here
is a TAPE population (rule 5) unless it says "live". Grid: `research/pingrid.py`,
`results/RESULTS_grid.md`, 5 days (09/12-09/17), 500 settled markets per crypto
series and 300 per commodity series, every taker buy at 20c+ inside 180 s.

## 1. CRYPTO: how early can a near-certainty be bought? The market's own record

Buyers of the priced-in side at 95-98c, share that bought the LOSER:

| seconds left | BTC | ETH | SOL | XRP | DOGE | BNB | verdict |
|---|---|---|---|---|---|---|---|
| 0-30 | 0.0-0.4% | 0.0% | 2.3-2.8% | 0.0% | 0.6-5.8% | 1.5-2.2% | our window; fine |
| 31-45 | 1.9% | 0.0% | 0.1% | 6.0% | 1.0% | 6.0% | mixed but positive on average |
| **46-60** | 3.9% | 2.0% | 1.9% | 1.2% | 0.3% | 2.1% | **the frontier: ~2%, break-even ~3.4%** |
| 61-90 | 10.0% | 7.3% | 5.7% | 2.7% | 6.1% | 1.9% | **dead** |
| 91-180 | 2-5% | 2-3% | 3-5% | 2-5% | 3% | 2-4% | dead to marginal |

These buyers had NO model -- just the price. Our bot adds a 99.5%-confidence
gate on top, which is why our live loss rate at 97-98c (2.0%) beats nothing
here. So:

- **"Trade much sooner / use the full 15 minutes": NO.** Beyond 60 s the
  market's near-certainties flip 5-10% of the time and every cell is negative.
  No model fixes a population that loses 1 in 12. The last 60 seconds are the
  whole game, for crypto.
- **46-60 s is worth one paper arm** (running: `--early-tau 60 --early-frac
  0.333`, pid 637500). If our gate turns that ~2% into ~1%, the early window
  grows from 45 to 60. Read it against the tau-45 arm, same bars as
  PREREG_staged.md.
- **The 98-99c column at 31-60 s loses 0-1% on every coin** (BTC 0.1%, DOGE
  0.0%, XRP 2.9%, others 0.0-0.7%). That is the cheapest, safest-looking cell
  in the table and we never buy it -- our ceiling is 98c. It pays ~+1c a
  contract. Parked as a paper-arm candidate (ceiling 99c INSIDE the early
  window only); not built today.

**Where the 90-98c buying happens:** 60-78% of it is at 61-180 s -- where the
grid says buyers lose. The pool we compete for in the last 45 s is 15-30% of
the volume. **Competitors moving earlier are moving into the losing part of
the table.** That is the reassurance the morning did not have.

## 2. COMMODITIES: each series has its own strategy, and the band IS the strategy

| series | window | price | evidence (loss %, EV/contract) | status |
|---|---|---|---|---|
| **GOLD** | 2-15 s | 90-99c | 0-5 s: 0.0-0.5%, +3 to +6c; 6-15 s: 98-99c **0.1%** on 2,102 trades, +1.1c; **16-30 s: 10.3% lost, dead** | paper arm |
| **WTI** | **2-60 s** | 90-99c | 95-99c: 0.0-1.5% at EVERY horizon to 60 s; 90-95c: 2-4% at 16-45 s (+2.7 to +4.8c) | paper arm |
| SILVER | 2-5 s | 90-99c | 95-98c loses at every horizon; only 0-5 s at 90-95c and 98-99c pay | paper arm, as the CONTROL |
| COPPER | -- | -- | negative in nearly every cell | not traded |
| NATGAS | -- | -- | negative in nearly every cell | not traded |

Two things are new against this morning: **gold's 98-99c band** (0.0-0.1%
lost inside 15 s, the deepest cell in the table), and **WTI's window running
to 60 s** -- the widest of anything we trade, including crypto. "Earlier bets
on commodities" is therefore YES for oil and NO for gold, and the reason is
the mechanism: a candle close is one price at one instant, so how early you
can be right depends on how calm the asset is, and oil in its last minute is
calmer than gold.

`research/cmdarm.py` carries these per-series windows (pid 637468). Its `look`
records now show, per market per close, whether the WINNING side was offered
at all inside the band and at what price -- on the first close it watched,
nobody offered gold's winner at any price, silver's was offered only at 99.9c,
and oil's at 91.8c.

## 3. THE REVERSAL IDEA ("if confidence flips, overbuy the new side"): it has a real population

Conditioned on what a trader could SEE -- the lowest price the favourite
(>=90c at 60 s) traded at inside the last 30 s -- across 1,717 crypto markets:

| the favourite fell to | markets | favourite LOST |
|---|---|---|
| stayed 90c+ | 1,511 | **0%** |
| 80-90c | 17 | 0% |
| 70-80c | 16 | 0% |
| 50-70c | 15 | 0% |
| **under 50c** | **158** | **76%** (BTC 92%, XRP 92%, ZEC 81%, ETH 59%) |

**A dip that stays above 50c recovers every time (48 of 48). A crossing below
50c is a real flip 3 times in 4.** Two consequences, both "lose less" first:

- **Our hedge fires on model belief < 0.60. The market's price is a better
  trigger.** Five of our nine live hedges were wasted, at beliefs of
  0.49-0.89; the market says a favourite that merely dips recovers. A hedge
  that waits for OUR side to trade below 50c would have skipped the wasted
  ones and kept the needed ones (which fired at 0.21-0.56). Needs a paper arm
  with `--hedge-price 0.50` (not built yet -- pinrun's hedge pass reads
  belief, not the book's last trade).
- **"Overbuy the new side" is a strategy on its own:** when a favourite
  crosses below 50c inside 30 s, the new side at ~50c wins 76% of the time.
  EV at 50c: 0.76 x 0.50 - 0.24 x 0.50 - fee = **+11c a contract**, before
  adverse selection. ~30 such crossings a day across the crypto series. It
  is the single largest per-contract number found today, and the single most
  likely to be an artefact of exactly the population trap rule 5 exists for
  (the buyer who reaches a new side at 50c is racing informed sellers). Paper
  arm first; it is a new arm, not a flag on pinrun.

## 4. Levers measured and CLOSED today

- **Per-close budget (3rd+ coin on a close):** only 0.5 markets/day would have
  passed every other gate; ~$1/day. Closed.
- **Raise the 98c ceiling (crypto, main window):** 75% of what it blocks sits
  above 99c where break-even is 1 in 107 against our measured 1.21% error.
  Closed (RESULTS_decay.md section 7). The early-window 98-99c cell is a
  separate question, above.
- **Trade beyond 60 s:** dead on the market's own record. Closed.

## 5. What is running, and what each one answers

| arm | flags | answers |
|---|---|---|
| live bot (pid 614944) | + `--early-tau 45 --early-frac 0.333` | v-staged; 2 early legs so far, both won |
| flat tau-45 paper | `--tau-max 45` | 19/30 closes to its bar, 20/20 NEW markets |
| early-60 paper (new) | `--early-tau 60 --early-frac 0.333` | does our gate rescue 46-60 s |
| one-coin paper | `--one-coin-depth` | depth at the same limit, brake-capped |
| commodities paper (re-banded) | per-series windows | gold / WTI / silver control |
| pickoff tracker | `pinpickoff.py` | pool size, our share, when bargains are taken |

## 6. Next, in order of expected money per hour of work

1. Read the early-60 and flat-45 arms at their bars (tonight).
2. Build the market-price hedge trigger as a paper flag and the "new side
   under 50c" arm. Both rest on the wobble table above.
3. Commodities: after ~40 paper bets per series, propose the 1-contract live
   test -- the only instrument that can see the fill population.
