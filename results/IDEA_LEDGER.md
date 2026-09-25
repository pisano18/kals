# IDEA_LEDGER -- every money idea ever checked, one row each, never deleted

**Read this before proposing anything new.** Every money-idea sweep
(`research/sweep/README.md`) reads it first and updates it last. A dead idea
stays here so nobody re-proposes it; it can come back only with a genuinely new
angle, stated in its new row.

Status: **live** (trading real money) · **testing** (paper arm / watcher /
1-contract test running) · **viable** (survived a check and a refutation, not
yet tested) · **needs-data** · **dead**. Money is Kalshi's books; $/day is the
realistic figure at the bank of the time, never the tape's.

Started 2026-09-25 from IDEAS_2026-09-24.md, SECOND_INCOME_SCAN_2026-09-25.md,
FAR_RUNG_2026-09-25.md and MAKER_SIM_2026-09-24.md. The 2026-09-25 multi-agent
sweep (`results/IDEA_SWEEP_2026-09-25.md`) adds its rows below when it lands.

---

## HOT AREAS -- where the next sweep should look first

- **Polymarket US BTC 15-min / 1-h** -- the same contract as our live market on a
  second book; operator funded (~$60) and eligible. Real-time recorder running
  to ~2026-09-28 (see UNRESOLVED U1). Questions: pin supply there; maker rebate +
  hedge on Kalshi; cross-book gaps.
- **Hourly crypto ladders, all seven coins** -- paper arm `arm-hourly-all` since
  2026-09-25 03:06Z; hourly BTC live at 1 contract since 2026-09-24. The only
  place more bank buys more contracts (books ~30x deeper than 15-min).
- **Sports** -- 66M contracts/day, 1,121 series, barely examined before this
  sweep; ESPN's API is blocked from this box, other league feeds are not.
- **Parlay / combination markets** -- crypto-combo pricing vs our legs
  CHECKED 2026-09-25 (D27): no gain for our strategy; sports/other combos
  still unexamined.
- **Loss hedges for the live bot** -- the operator's #1 priority is lose less;
  every hedge idea so far died on cost (rows D08, D15).

## UNRESOLVED -- decide these when the data exists

| id | item | what decides it | when |
|---|---|---|---|
| U1 | Polymarket US pin / maker / cross-book | `research/poly/poly_ws_report.py` on the 3-day recording (scratch path in OPEN_WORK A11); bar in SECOND_INCOME_SCAN section 1 row 1 | ~2026-09-28 |
| U2 | Seven-coin hourly ladders | `arm-hourly-all` vs live via armh2h2 | ~2026-10-02 |
| U3 | Hourly BTC at 1 contract (live) | ~30 fired closes; fill rate and price | ~2026-10-01 |
| U4 | Crypto one-touch monthlies (KXBTCMAXMON etc.) | replicate the trimmed-mean rule from the tape, time crosses vs trades, then a 14-day watcher | open |
| U5 | Sports final minute | a working free score feed, then books in the last 2 min of 20 games | open |
| U6 | Earthquake "biggest quake" markets | `python research/quakewatch.py --report` | ~2026-10-08 |
| U7 | Hourly temperature markets | `python research/wxwatch.py --report` (supply ~0 so far) | ~2026-09-28 |
| U8 | Fresh-offer gate / toxic-offer gate / 2c edge floor | `python research/bars.py` (or /bars on the phone) | ~2026-10-01 |

---

## LEDGER

| id | name | family | status | $/day | one-line reason | evidence |
|---|---|---|---|---|---|---|
| L01 | 15-min crypto late pin (pinrun) | crypto 15M | live | +$438 lifetime to 09-25 (all families, 1,101 markets; 09-24: +$92) | buy the near-certain side in the last 45 s off the settlement-index feed | CURRENT_STATE.md, VERSIONS.md |
| L02 | Coin race late pin | crypto coin race | live (5 contracts) | ~$1-2 | 59 won, 1 tie, 0 lost at 1 contract to 09-24 | OPEN_WORK B1 |
| L03 | Hourly BTC ladder near rungs | crypto hourly | live (1 contract) | unknown | same gates as 15-min, 30x deeper books | VERSIONS v-btcd1, OPEN_WORK A2 |
| T01 | Seven-coin hourly ladders | crypto hourly | testing (paper) | unknown | ETH SOL XRP DOGE BNB HYPE ladders on indexes we already follow | VERSIONS v-ladder7 |
| T02 | Polymarket US BTC 15-min/1-h | cross-venue | testing (recorder) | $0-15 est. | same contract, 1/10-1/50 the book, makers paid a rebate | SECOND_INCOME_SCAN s1-2 |
| T03 | Earthquake markets after USGS confirms | science | testing (watcher) | $0-10 | decided market sometimes still below 97c | OPEN_WORK A6 |
| T04 | Hourly temperature (Kalshi's own index) | weather | testing (watcher) | ~$0 | prediction perfect (240/240) but nobody sells | OPEN_WORK A5 |
| N01 | Crypto one-touch monthlies | crypto monthly | needs-data | $2-10 | $3,738 bought <=97c in last 10 min before early close, 3 events | SECOND_INCOME_SCAN s1 row 3 |
| N02 | Sports final minute | sports | needs-data | unknown | needs a score feed (ESPN 403) | SECOND_INCOME_SCAN s1 row 5 |
| D01 | Daily-high temperature brackets | weather | dead | ~$4 | locked money was the 1 F rounding-boundary case | IDEAS_2026-09-24 s3 #1 |
| D02 | KXWTI daily oil | commodities | dead | ~$3 | winner 98-99c by 30 s; wrong settlement proxy | IDEAS s3 #2 |
| D03 | AAA gas price ladders | economics | dead | negative | certainty from a private feed we lack; takers lost $9,800 | IDEAS s3 #3 |
| D04 | Equity-index / hourly-commodity / FX 15M | financials | dead | negative | one value at one instant, no partly-written average; lost real money | IDEAS s3 #4 |
| D05 | Daily-low temperature | weather | dead | ~$0.50 | whole-Celsius feed makes false locks | IDEAS s3 #5 |
| D06 | KXRAIN | weather | dead | ~0 | money gone within 15 min of first rain; radar prices it | IDEAS s3 #6 |
| D07 | Gemini Predictions pin | cross-venue | dead | 0 | winning side never <=98c inside 45 s | IDEAS s3 #7 |
| D08 | Kalshi perpetual as hedge leg | hedging | dead | negative | hedge size explodes near 50%; fees 449x a binary hedge | IDEAS s3 #8 |
| D09 | Top-of-hour 15-min YES + ladder NO package | crypto consistency | dead | 0 | 0 riskless packages in 60 reads, cheapest $1.0067 | IDEAS s3 #9 |
| D10 | Offshore crypto binaries (Deribit etc.) | cross-venue | dead | 0 | none US-accessible on a 60-s average | IDEAS s3 #11 |
| D11 | Kalshi vs Gemini cross-venue package | cross-venue | dead | negative | different strikes and indices; pays $0 on 4% of closes | IDEAS s3 #12 |
| D12 | Robinhood/Coinbase as second book | cross-venue | dead | 0 | they ARE Kalshi's book | IDEAS s3 #13 |
| D13 | Coin race favourite-longshot maker | crypto coin race | dead | -$0.62 | not significant; loses on holdout | IDEAS s3 #14 |
| D14 | Resting the hedge as a maker bid | hedging | dead | negative | a resting bid fills only when we are winning | IDEAS s3 #15 |
| D15 | Selling our winner into the 99.5c queue | exits | dead | negative | the bid vanishes 4-8 s before the flip | IDEAS s3 #16 |
| D16 | Selling lottery tickets at 1-5c | crypto 15M | dead | negative | the buyer is informed; one market cost makers $370k | IDEAS s3 #17 |
| D17 | Market making on 15-min crypto | crypto 15M | dead | -$2,800 at sim volume | every one of 12 variants loses every day, even first-in-line and instant | MAKER_SIM_2026-09-24 s9 |
| D18 | Far rungs of hourly BTC at 99c | crypto hourly | dead | ~0 | 0 safe-side buys >=97c at $150+ in 68 closes; the 99c offers were the next-to-settle rung | FAR_RUNG_2026-09-25 verdict |
| D19 | Ladder both-sides / monotonicity arbitrage | crypto hourly | dead | 0 | 0 violations in 1,496 polls | SECOND_INCOME_SCAN s1 row 4 |
| D20 | S&P / Nasdaq daily close ranges | financials | dead | 0 | one instant; strikes finer than auction noise | SECOND_INCOME_SCAN s1 row 7 |
| D21 | Crypto.com 5/15/20-min binaries | cross-venue | dead | 0 | 8-24c spreads, book dies at 42 s | SECOND_INCOME_SCAN s1 row 8 |
| D22 | ForecastEx / Rothera / PrizePicks / Sporttrade | cross-venue | dead | 0 | weekly+, Kalshi's book, sports-only, or exited US | SECOND_INCOME_SCAN s5 |
| D23 | Air quality / box office / app ranks / Trends / river levels | misc | dead (for now) | 0 | one-off or custom series, no repeatable close | SECOND_INCOME_SCAN s1 row 9 |
| D24 | Truth Social weekly post count | politics | dead | <$1 | one close a week, thin | SECOND_INCOME_SCAN s1 row 6 |
| D25 | Exchange-feed "move against us" gate | crypto 15M | dead (as a gate) | 0 | does not separate our losers | FEED_LEAD_2026-09-24 |
| D26 | Cash out AND hedge (flip to a full reversal bet at the alarm) | hedging | dead | ~0, worse tail | the other side is fairly priced at the alarm; +$59 on 10 hedges but range -$124..+$185; 09-19 -$223 -> -$275 | results/HEDGE_FLIP_2026-09-25.md |
| D27 | Buy our pin legs as a Kalshi combo | crypto 15M | dead | -$2.2..-2.6/day | combos priced 0.0-0.4c ABOVE what we paid at our moments (26 orders); same bet at equal size; needs simultaneous legs (ours are 11 s apart) and a 0.6-7 s RFQ | results/COMBOS_2026-09-25.md |
