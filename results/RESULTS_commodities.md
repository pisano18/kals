# RESULTS -- the commodities method

`2026-09-17 ~14:1xZ`. The operator: *"Most important thing right now is
figuring out the commodities method. Prioritize that."*

## THE METHOD, and it is not the one I expected

I expected to need a Pyth price feed and a distance-to-strike model, the way
the crypto bot needs the settlement index. Three findings replaced that.

### 1. The settlement rule, confirmed from Kalshi's own market metadata

Verbatim from `rules_primary` on `KXGOLD15M-26SEP170945-45`:

> "If the close price of the 1-minute candlestick for Gold on Sep 17, 2026 at
> 9:45 AM EDT is at least the close price of the 1-minute Pyth GOLD
> candlestick at 9:30 AM EDT ... then the market resolves to Yes."

So the settle is **the close of the 1-minute Pyth candle AT the close time**,
and the strike is the same thing one 15-minute window earlier. The chain
`strike(N+1) == settle(N)` held on **38 of 39** consecutive gold closes -- the
same structure as our crypto series, which also means **the strike sequence is
a free 15-minute price history**.

**The original kill was right about the mechanism.** Nothing is locked in
early: it is one price at one instant, not a 60-second average. Over 40 gold
closes the move from strike to settle was median **$4.61** on a ~$4,360 price
(10.6 basis points per 15 minutes).

### 2. We cannot see that price, and the control proves it is not our fault

- Pyth `hermes` and `benchmarks` price endpoints now answer **401** without an
  API key. (Their TLS chain also needs `certifi`, not the Windows store --
  `/v1/price_feeds/` works with certifi and fails without it. Worth knowing.)
- Kalshi's own **`pyth_value`** websocket channel accepts a subscription for
  GOLD, SILVER, COPPER, WTI and NATGAS -- and then publishes **nothing**.
  **Control: it publishes nothing for BTC and ETH either**, which Kalshi
  certainly prices. So the channel is not serving us at all; the commodity
  side is not specially excluded. 100 seconds, zero frames, both.

### 3. We do not need it -- the market's own price is the signal

Every taker buy at 90-98c within 30 s of a close, over 300 settled markets per
series, scored against the settlement. **TAPE POPULATION (rule 5): this is
what the market did, and it is NEVER our loss rate.**

| series | band | trades | bought the LOSING side | mean price | EV per contract |
|---|---|---|---|---|---|
| **GOLD** | 0-5 s | 1,547 | **0.13%** | 95.9c | **+3.72c** |
| GOLD | 6-15 s | 2,893 | 2.45% | 95.0c | +2.22c |
| GOLD | 16-30 s | 3,615 | 7.69% | 94.8c | **-2.82c** |
| **WTI** | **16-30 s** | 2,596 | **1.04%** | 94.8c | **+3.82c** |
| WTI | 6-15 s | 1,975 | 2.03% | 95.8c | +1.92c |
| WTI | 0-5 s | 1,160 | 1.64% | 96.1c | +2.00c |
| SILVER | 0-5 s | 1,089 | 2.85% | 95.7c | +1.16c |
| SILVER | 16-30 s | 1,877 | 9.16% | 95.3c | -4.77c |
| COPPER, NATGAS | every band | -- | 5.7-11.3% | -- | dead |

Break-even at 95c is about **5%** lost. Our crypto bot keeps about **3c** a
contract.

**So: WTI at 16-30 seconds is better than the business we already run, at the
horizon our machinery already trades. Gold is strong but only inside 15
seconds, and is a LOSER at 16-30 s.** The time band is not a detail; it is the
strategy.

Volume is not the constraint: gold shows ~3,200 contracts per close in the
0-5 s band at 90-98c, WTI ~1,700 per close at 16-30 s.

## What this means: no model, no feed

The rule being tested is deliberately blunt -- **buy whatever the book offers
at 90-98c inside that series' good time band**. The market's own price
identifies the near-certainty; the tape says it systematically underprices it.
No Pyth feed, no volatility model, no index. If a better model helps later it
can only add to this; it is not needed to start.

## THE ONE THING THAT COULD KILL IT, stated before any live number

**Rule 5 and the 31x.** The tape's population is "a trade happened at
90-98c". Ours would be "we took a resting offer". On the crypto markets those
two differed by **31x** -- tape 0.11%, live 3.4% -- because the offer that
reaches us is the one somebody chose to sell to us. Gold's 0.13% becoming 4%
live would put it at break-even; WTI's 1.04% becoming 5% would kill it.
Nothing measured here can rule that out, and a paper arm cannot either,
because it assumes its fills.

## What is running

`research/cmdarm.py`, started 2026-09-17 14:08Z, paper only -- the self-test
asserts `pintake`, `ordercli`, `post_only` and `/portfolio/orders` appear
nowhere in its working code, and that it loads the repo's `livebook` rather
than the scratch copy in `kals-work` that shadows it. It watches gold, silver
and WTI, applies the band and price window above, records every would-be bet
with the offer size and book age, and scores it at settlement.

Silver is included deliberately as a **losing control**: the tape says it is
marginal. If gold and WTI print well and silver does not, that is evidence the
bands are real rather than a fluke of two series.

## Next, in order

1. Let the arm run to ~40 bets per series. Read availability, price, band, and
   how often the offer is actually there.
2. If it holds, a **live penny test** (1 contract a bet, operator sign-off per
   the standing rule) is the ONLY instrument that can measure the fill
   population. That is the real decision point.
3. Only then, size.
