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

## 7. SECOND LOOK (operator: "double check you like your commodities ideas ... anything deeper") -- the grid BY MARKETS, and by ET session

The first grid counted TRADES. Rule 4 says cluster by close: three huge
markets can make a cell look safe. `pingrid.py` now also keeps, per cell and
per ET day-part (read from the ticker's own clock), the MARKETS touched and
how many had a buyer of the losing side. Five things changed.

**a. Gold's "0.1% at 98-99c inside 15 s" was three big markets.** By markets
it is 53 touched, 1 lost (1.9%) -- break-even at 98.5c is 1.5%. Flat, not
+1.1c. And the loss sits in one place: **the COMEX session.** 95-99c inside
15 s: night 68 markets 0 lost, late afternoon/evening 49/0, **08-14 ET
32/2**. -> the near window now SKIPS 08:00-14:00 ET.

**b. The safest cell in the whole table is gold two minutes out.** 98-99c
with 91-180 s left: **129 markets, 0 lost**, about 26 a day, +1.2c a
contract at the trade level. A gold market already at 98c+ two minutes
before the close has moved far from its strike; one that only reaches 98c in
the last 30 s is a coin that just landed. Different animals -- the 16-60 s
cells lose 3-8% of markets. -> a second, FAR window (91-180 s, 98-99c) in
the paper arm. This is "earlier bets on commodities" in the one place the
tape says it is safe.

**c. WTI holds up by markets.** 95-99c, 0-60 s: 153 markets, 3 lost (2.0%
against ~3% break-even). 90-95c: 4-6% at 2-45 s (marginal), **10% at 46-60
s** (58/6) -> the 90-95c window stops at 45 s; 95-99c runs to 60.

**d. Silver loses even in the last 5 seconds** by markets (95-99c: 74
markets, 4 lost = 5.4%). It stays in the arm as the NEGATIVE control: if
silver wins in paper, the arm is reading the world wrong.

**e. Why the arm saw "nobody selling" this morning.** The tape for the six
closes it watched (11:00 and 11:15 ET): every one of gold, silver and oil was
priced 99.7-99.9c in its last minute. Above the 99c ceiling there is nothing
to buy, and at 99.9c a win pays 0.1c -- one loss in a thousand breaks even.
Not raised. The commodity trade lives on the CONTESTED closes (90-99c),
which the by-markets counts size at roughly: gold near window outside the
US session ~11 markets/day, gold far window ~26/day, WTI ~31/day.

**Crypto, by markets, is harsher than by trades -- and it bears on 46-60 s.**
Buyers of the priced-in side, all nine crypto series (a market counts as lost
if ANY buyer in the cell took the loser, so this is an upper bound):

| seconds left | 95-98c | 98-99c |
|---|---|---|
| 0-5 | 67 mkts, 1 lost (1.5%) | 98, 1 (1.0%) |
| 6-15 | 173, 5 (2.9%) | 228, 3 (1.3%) |
| 16-30 | 389, 15 (3.9%) | 483, 7 (1.4%) |
| **31-45** | **606, 17 (2.8%)** | **751, 7 (0.9%)** |
| 46-60 | 900, 32 (3.6%) | 1101, 20 (1.8%) |
| 61-90 | 1291, 63 (4.9%) | 1446, 33 (2.3%) |

Break-even without a model: ~3.4% at 96.5c, ~1.5% at 98.5c. So 31-45 s is
at or under break-even for a buyer with NO model (the live early leg adds
the 99.5% gate on top). 46-60 s is AT break-even without a model: the gate
has to do the work, which is exactly what the early-60 paper arm measures.
Not a deployment candidate on this table; a paper question.

**Not changed:** the 99c ceiling on commodities; copper and natural gas (out);
the crypto main window.
