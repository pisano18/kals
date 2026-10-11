# External research: Kalshi 15-minute crypto binaries (as of 2026-10-08)

Scope: web-only research for the pin bot (taker, 90-98c, last 45 s; losses concentrated in
large late offers followed by an index flip). Nothing was run against the Kalshi API. Repo
read: `RUNBOOK.md` only. Each claim carries URL, date and a class:
**FACT** = primary source (exchange/vendor/regulator document or API doc), **REPORTED** =
secondary (press, blogs, data vendors, third-party summaries), **SPECULATION** = my inference.

Method notes that bear on reliability:
- The session's web-search budget was exhausted after the first wave; everything after that
  came from direct fetches of known URLs. `kalshi.com` itself rate-limited the fetcher
  (HTTP 429, "Vercel Security Checkpoint") on every attempt, so the official fee-schedule
  PDF, `kalshi.com/regulatory` and `/regulatory/notices` were NOT read. Kalshi rules text
  was taken from Robinhood's mirror of the same markets (Robinhood routes to Kalshi) and from
  Kalshi's S3 contract-terms PDF, and the rulebook from Kalshi's S3 bucket.
- Several PDFs were extracted locally with a stdlib text extractor (no PDF library on the
  box). One font in the CME CF methodology substitutes glyphs (R->n, S->o, D->5, P->m);
  the numbers and tables are unaffected and were read directly.

---

## 0. Findings that would change what the bot does (ranked)

1. **The index our loss class rides on is published at 200 ms for BTC/ETH/SOL/XRP/DOGE, and
   Kalshi now streams it at 5 Hz.** The CME CF methodology (v17.0, 21 Sep 2026) sets the
   Effective Time for BRTI, ETHUSD_RTI, SOLUSD_RTI, XRPUSD_RTI to "every 200 milliseconds"
   (changed 18 May 2026, v16.6); the CF Spot Rate methodology (v16.0, 5 Oct 2026) does the
   same for DOGEUSD_RTI. Kalshi's `cfbenchmarks_value_5hz` WebSocket channel (added
   3 Sep 2026) streams those five at up to 5 updates/s. ZEC, BNB, HYPE, NEAR stay at 1 s.
   **So what:** anyone on the 5 Hz feed sees up to 4 intermediate prints per second that our
   1 Hz subscriber never sees. A seller who dumps size at T-20 s can be reacting to a
   200 ms print we will only see at the next top-of-second. (FACT: methodology PDF +
   docs.kalshi.com changelog.) Settlement is still the 60 top-of-second prints, so the 5 Hz
   feed is an *information* edge, not a settlement edge.

2. **Kalshi now publishes its own running settlement average during the last minute**
   (`last_60s_windowed_average_15min` in every `cfbenchmarks_value` tick, present only in
   the final minute before :00/:15/:30/:45). Window is `(close - 60 s, close]`: the print at
   exactly T-60 is EXCLUDED, the print at the close second is INCLUDED, counts run
   `:01 -> 1 ... :59 -> 59, close -> 60`. **So what:** this pins down which 60 prints count
   (our `settlewin.partial()` alignment can be checked against it tick by tick), and it is a
   free, exchange-side reconciliation of `locked_sum`. The doc does not say it is the
   settlement value; it is the same arithmetic. (FACT: docs.kalshi.com/websockets/cfbenchmarks-value.)

3. **Per-coin rounding of the settlement average is in the rules and it is coarse for BTC
   and BNB:** "rounded to the nearest 2 decimal places" (BTC, BNB), 4 (XRP, HYPE, ZEC,
   NEAR), 7 (DOGE); "is at least" so ties go to Yes/Up. **So what:** for BTC a 60-print
   average within $0.005 of the strike settles Up; `fair()` should compare the ROUNDED
   average to the strike, and the tie mass is not zero. (FACT: Kalshi market rules as
   mirrored on robinhood.com, 2026-10-08, and kalshi.com/markets/kxbtc15m via proxy.)

4. **Coin Race ties are a half-payout, not a coin flip:** returns are rounded to 0.001 %, and
   if several coins tie for the highest return "each tied contract resolves to YES at $1
   divided by the number of cryptocurrencies tied ... rounded down to the nearest cent";
   the rest resolve No. **So what:** our recorded "tie loss" was a 90c+ purchase paid 50c.
   Near-flat windows (two coins within 0.001 % of each other) are a known-loss state for
   any contract bought above 50c; a tie filter on the live returns at T-45 s is cheap.
   (FACT: Kalshi KXCRYPTOLEAD15M market page via proxy, 2026-10-08.)

5. **If the index feed is missing or incomplete at close, the rules say the strike
   "resolve[s] to No"** (CRYPTO15M contract terms, dated 5 Oct 2026: "If no data is
   available or incomplete on the Expiration Date at the Expiration Time, then affected
   strikes resolve to No"). Rulebook 7.2(b) lets Kalshi instead delay expiration for
   "delayed data from a source", and 6.3(c) lets it settle at last traded price or by the
   Outcome Review Committee when the Underlying "cannot be measured". **So what:** an index
   outage is an asymmetric risk for Up/Yes holders on paper; which path Kalshi takes is at
   its discretion. (FACT for the texts; SPECULATION on which path.)

6. **ZEC and BNB indices have exactly two constituent exchanges (Coinbase, Kraken); HYPE
   has three; the retrieval-lag threshold for all four is 30 s** (10 s for the big five).
   **So what:** one stale or flagged book makes ZECUSD_RTI/BNBUSD_RTI a single-exchange
   mid, and a book can be up to 30 s stale and still count. These are the series with the
   thinnest index, and our worst adverse fills (ZEC 91.5c) are on them. (FACT: CF
   Constituent Exchanges v10.3, 5 Oct 2026; CF Spot Rate methodology v16.0.)

7. **The index is a pure order-book martingale with no averaging window** (consolidated,
   uncrossed book; utilised depth where the mid-spread curve stays within 0.5 % (BTC) or 1 %
   (ETH/SOL/XRP/DOGE/ZEC/BNB/HYPE) of mid; exponential weighting lambda = 1/(0.3 v_T); a
   dynamic order-size cap = trimmed mean + 5 sd of level sizes). **So what:** there is no
   mechanical lag term inside the index; any predictable lag versus constituent exchanges is
   feed/retrieval lag only. A single large resting order cannot move it (size cap), but a
   book-wide repricing on Coinbase/Kraken moves it on the next 200 ms calculation. (FACT:
   CME CF methodology v17.0 sections 4.1-4.2, 6.) The June 2026 "uncrossing step" (v16.8)
   removes crossed consolidated books, which previously could print through the mid.

8. **Crypto markets live on their own matching engine ("shard 2"); auto-routing "will incur
   an additional latency cost".** **So what:** pass `exchange_index` explicitly on every
   order and book subscription for KX*15M. (FACT: docs.kalshi.com/getting_started/exchange_sharding;
   changelog 24 and 27 Aug 2026.)

9. **Self-trade prevention applies across subaccounts, default `taker_at_cross` cancels the
   TAKER.** **So what:** if the ladder bot (subaccount 1) ever rests on the side pinrun
   (subaccount 0) wants to lift, pinrun's IOC is cancelled silently rather than filled;
   `maker` mode would cancel the ladder's resting order instead. (FACT: docs
   /getting_started/subaccounts and create-order-v2.)

10. **Block trades print on the public trade feed** (`is_block_trade`, added 13 Aug 2026).
    **So what:** a large late print in the tape may be an off-book block/RFQ match, not a
    book dump; the "informed seller" classifier should exclude `is_block_trade = true`.
    (FACT for the field; SPECULATION that blocks occur in 15M markets.)

11. **Polymarket's 15-minute markets now settle on a 60-second Chainlink TWAP (7 Aug 2026),
    charge the same 7 % x p(1-p) taker curve, pay makers a 20 % rebate of taker fees, and
    impose a 150 ms taker delay (4 Sep 2026, up from 50 ms).** The Stanford/SMU paper that
    triggered the TWAP switch found settlement manipulation "prevalent in five-minute
    contracts but largely absent in the fifteen-minute contracts". **So what:** the
    manipulation literature says 15-minute TWAP windows are not where the spot-pushing money
    is; our loss class (informed late sellers) is adverse selection, not manipulation, and
    Polymarket's answer to late snipers was a taker speed bump, which Kalshi does not have.
    (FACT: docs.polymarket.com changelog, docs.polymarket.com fees, arXiv 2606.31675.)

12. **Kalshi's Volume Incentive Program ends 13 Oct 2026** (it paid up to $0.005/contract on
    trades between 3c and 97c). **So what:** if the ledger has been receiving VIP credits on
    90-97c fills, that income stops next week; the cheaper-to-trade retail flow it subsidised
    may thin too. (REPORTED: PredictionMarketPulse 5 Oct 2026; program terms REPORTED via
    navnoorbawaresearch.com 14 Aug 2026.) The separate Liquidity Incentive Program (maker
    rewards, $1-$1,000 per market per day) runs to 1 Jan 2027 and since 30 Jul 2026 no
    longer excludes Market-Maker-Agreement holders or Kalshi's affiliate. (FACT: CFTC filing
    15 Jul 2026.)

13. **CFTC sent two "swap definition" rules to OMB on 28 Sep 2026: a proposed rule to include
    event contracts, and an INTERIM FINAL rule to exclude "casino-style gambling products",
    effective on publication without comment.** Texts unpublished. **So what:** the one
    regulatory event in Oct-Dec 2026 that could reclassify short-cadence crypto binaries; no
    evidence either way that 15-minute crypto is in scope. (REPORTED: PredictionMarketPulse
    5 Oct 2026; SPECULATION on scope.)

---

## 1. Fees

| Claim | Source / date | Class |
|---|---|---|
| Taker fee = `M_taker x 0.07 x C x P x (1-P)`, default multiplier 1; maker fee = `M_maker x 0.0175 x C x P x (1-P)`, default maker multiplier 0; fee schedule effective **2026-07-07**; some series charge maker fees | botforkalshi.com/blog/kalshi-fees-explained (verified 2026-09-09); polykal.net/kalshi-fees-explained (reviewed 2026-09-12) | REPORTED (official PDF `kalshi.com/docs/kalshi-fee-schedule.pdf` returned 429 on four attempts) |
| Series object `fee_type` enum: `quadratic` (general table), `quadratic_with_maker_fees` ("with maker fees (0.25 multiplier)"), `quadratic_with_combo_maker_fees` (0.5), `flat`; plus `fee_multiplier` | docs.kalshi.com/api-reference/market/get-series (read 2026-10-08) | FACT |
| Fee rounding: per-ORDER accumulator across all fills, taker or maker; direct members billed to $0.0001, non-direct to $0.01; "Net fee = trade fee + rounding fee - rebate (always >= $0.00)" | docs.kalshi.com/getting_started/fee_rounding | FACT |
| No special fee treatment for 15-minute crypto found; third-party explainers list no crypto override; RUNBOOK's `fee_type: quadratic, fee_multiplier: 1` stands unless the series object says otherwise | polykal.net; botforkalshi.com | REPORTED / nothing found |
| Combos moved to sub-cent ticks ($0.0001 below 1c / above 99c) 10 Sep 2026; crypto 15M tick grid unchanged (`tapered_deci_cent` per RUNBOOK; no change found) | docs.kalshi.com/changelog 2026-09-10 | FACT (combos) / nothing found (crypto) |
| Liquidity Incentive Program (amended 15 Jul 2026, effective 30 Jul 2026, to 1 Jan 2027): applies to "all Kalshi markets" flagged on the market page; per-market daily reward $1-$1,000; target size 100-20,000 contracts; one book snapshot per second at a random offset; score = DiscountFactor^(ticks from reference price) x size; snapshot excluded unless BOTH sides have resting size >= target; eligible = all members except IB/FCM customers (the earlier exclusion of affiliates and Market-Maker-Agreement holders was struck) | cftc.gov/filings/orgrules/rules07152610358.pdf (15 Jul 2026) | FACT |
| Volume Incentive Program: $0.005/contract cap, $1,000/market/day, trades 3c-97c, open to all except affiliate + MM-agreement holders; sealed Market Maker tier up to $50,000/series/week, selection in Confidential Appendix B; Kalshi Trading LLC (affiliate) is a documented market maker | navnoorbawaresearch.com/p/kalshi-publishes-one-liquidity-subsidy (14 Aug 2026) | REPORTED |
| VIP terminated effective **13 Oct 2026** (a year early) | predictionmarketpulse.substack.com/p/pmp-weekly-october-5-2026 | REPORTED |
| "Temporary Perpetual Fee Rebate Program" (9 Jul - 31 Dec 2026) refunds ALL maker+taker fees on perps to self-clearing members; perps only | cftc.gov/filings/orgrules/rules0625267305.pdf (24 Jun 2026) | FACT |
| Margin maker-volume incentive programs exposed via `GET /incentive_programs` (types: liquidity, volume, margin_maker_volume, margin_taker_volume) | docs.kalshi.com changelog 20 Aug 2026; api-reference/incentive-programs/get-incentives | FACT |
| **So what:** makers still pay 0 on plain `quadratic` series; whether any KX*15M series is `quadratic_with_maker_fees` is a one-call check on the series object (not run here). The LIP pays resting two-sided size, which a taker bot never earns. The turbinefi claim "Kalshi makers pay roughly one-quarter of taker fees" (19 Jun 2026) is the 0.25 multiplier of the maker-fee series generalised to all series. | | SPECULATION |

## 2. Kalshi API facts (docs.kalshi.com, read 2026-10-08)

| Claim | Source | Class |
|---|---|---|
| Order types: limit only (FIX `OrdType=2`); REST `time_in_force` in {`fill_or_kill`, `good_till_canceled` (+`expiration_time`), `immediate_or_cancel` (incompatible with expiration)}; FIX adds Day and GTD; `post_only`; `reduce_only` (IOC only, capped by position); `cancel_order_on_pause`; `self_trade_prevention_type` in {`taker_at_cross` (default), `maker`}; `client_order_id`; `subaccount`; `exchange_index` (-1 to require explicit routing); prices as fixed-point dollar strings 2-4 dp; `count` fractional to 0.01 contracts; create-order costs 10 tokens | api-reference/orders/create-order-v2; fix/order-entry | FACT |
| Batch create/cancel (V2) exist; cancel-all endpoints (27 Aug 2026); amend-expiry keeps queue priority (1 Oct 2026); "Legacy order mutation endpoints deprecated" (18 Jun 2026) | changelog; api-reference/orders/batch-create-orders-v2 | FACT |
| Rate limits (tokens/s read/write): Basic 200/100, Advanced 300/300, Expert 600/600, Premier 1,200/1,200, Paragon 2,400/2,400, Prime 4,800/4,800, Prestige 12,000/9,600 (Premier+ raised 20 % on 1 Oct 2026); default request 10 tokens, so Basic = 20 reads/s and 10 writes/s (matches RUNBOOK); write buckets above Basic hold 3 s of burst; tiers Expert+ earned from trailing 30-day volume / (previous month exchange volume x 2): Expert 0.075 %, Premier 0.125 %, Paragon 0.25 %, Prime 0.5 %, Prestige 1.0 % (requirements halved 25 Jun 2026); Advanced via the Upgrade endpoint | getting_started/rate_limits; changelog | FACT |
| CF Benchmarks REST passthrough costs 50 read tokens (vs 10); history endpoint returns tick-level values, intra-second for some indices | cfbenchmarks/rest-passthrough | FACT |
| Post-only quoters who cross "several times in short succession" may be temporarily rate limited (22 Aug 2026) | changelog | FACT |
| Subaccounts: Advanced tier and above; 63 numbered + primary; restricted API keys lock to one subaccount; STP applies across subaccounts (see finding 9); batch endpoints, WebSockets, order groups usable by restricted keys (Jul 2026) | getting_started/subaccounts; api-reference/portfolio/create-subaccount; changelog | FACT (confirms memory "subaccounts need Advanced") |
| Exchange sharding: shard 0 default, 1 combos, 2 crypto + commodities, 3 tennis/baseball/basketball; routing by `exchange_index` / FIX `ExDestination`; "Automatic routing will incur an additional latency cost"; crypto provisioned on dedicated instances 24 Aug 2026, auto-routing default 27 Aug 2026; per-shard write budgets | getting_started/exchange_sharding; changelog | FACT |
| WebSocket: `fill` (fields `is_taker`, `fee_cost`, `ts_ms`, `exchange_index`, `subaccount`, `post_position_fp`), `trade` (`taker_side`, `count_fp`, `is_block_trade`, `ts_ms`), all messages carry `sending_ts_ms` (1 Oct 2026); optional permessage-deflate; a subscription race that skipped the first event was fixed 24 Sep 2026 | websockets/user-fills; websockets/public-trades; changelog | FACT |
| `cfbenchmarks_value`: 21 coins (AAVE ADA BCH BNB BTC DOGE DOT ETH HBAR HYPE LINK LTC NEAR SHIB SOL SUI VVV WLD XLM XRP ZEC), ~1 tick/s, `index_ids` required (error 24) or `["all"]`; message has `received_at` (Kalshi receipt, unix ms), raw vendor frame in `data`, `avg_60s_data` (trailing `[ts-60000, ts)`, prior ticks only) and `last_60s_windowed_average_15min` (see finding 2); duplicate/out-of-order source timestamps ignored. `cfbenchmarks_value_5hz`: BTC ETH SOL XRP DOGE only | websockets/cfbenchmarks-value; changelog 3 Sep 2026 | FACT |
| Also new: `pyth_value` channel (23 Jul 2026); `market_lifecycle_v2` strike metadata; `settlement_sources` on events/series (18 Jun 2026); `settlement_timer_seconds` on markets; `settlement_bounds` (floor payouts) apply to scalar markets only; `result` enum `yes`/`no`/`scalar`/empty | api-reference/market/get-market; getting_started/settlement_bounds; changelog | FACT |
| FIX: FIXT.1.1/FIX50SP2 over TLS; PrivateLink from Premier, VPC peering from Prime ("Prime-tier members can contact Kalshi to discuss VPC peering", 20 Aug 2026); mass cancel 1/s; drop copy gated | fix/connectivity; changelog | FACT |
| Perps/margin exchange is live (`/margin` API; CFTC approved Kalshi's BTCPERP 28 May 2026) | docs.kalshi.com/margin; cftc.gov/PressRoom/PressReleases/9240-26 | FACT |
| Maintenance: "Every Thursday from 3:00 AM to 5:00 AM ET", trading pause; resting orders remain unless `cancel_order_on_pause`; cancels allowed in a trading pause, not in an exchange pause; CFTC notice (23 Feb 2026, effective 10 Mar 2026): "up to one maintenance period per week ... 3:00 AM ET to 5:00 AM ET on Thursdays", posted 24 h ahead | getting_started/maintenance_and_pauses; cftc.gov/.../rules02232639698.pdf; help.kalshi.com/en/articles/13823807 (updated 23 Aug 2026) | FACT (confirms memory) |
| Latency numbers: no published figures found beyond `sending_ts_ms`/`received_at` fields; Polymarket's microstructure paper reports its archive ingestion median < 50 ms (not Kalshi) | - | nothing found (Kalshi) |
| **So what:** route explicitly to shard 2; log `sending_ts_ms` and `received_at` to measure our Kalshi->box and CF->Kalshi lags directly (RUNBOOK's 63 ms / 37 ms medians can be re-measured for free); consider `cancel_order_on_pause` for anything resting into Thursday 3 AM ET; verify pinrun uses V2 order endpoints. | | SPECULATION |

## 3. CF Benchmarks real-time index methodology

Sources: CME CF Cryptocurrency Real Time Indices Methodology Guide v17.0, 21 Sep 2026
(docs.cfbenchmarks.com/CME%20CF%20Real%20Time%20Indices%20Methodology.pdf); CF Spot Rates
Methodology Guide v16.0, 5 Oct 2026 (docs.cfbenchmarks.com/CF%20Spot%20Rate%20Methodology%20Guide.pdf);
CME CF Constituent Exchanges v13.7, 24 Aug 2026 (docs.cfbenchmarks.com/CME%20CF%20Constituent%20Exchanges.pdf);
CF Constituent Exchanges (Spot Rate family) v10.3, 5 Oct 2026
(docs.cfbenchmarks.com/CF%20Constituent%20Exchanges.pdf). All FACT unless marked.

- **Two families.** BTC, ETH, SOL, XRP, NEAR are "CME CF ... Real Time Index"; DOGE, ZEC,
  BNB, HYPE are "CF ... Spot Rate" (same ticker suffix `_RTI`, separate methodology and
  constituent documents, same calculation design).
- **Calculation each tick:** (1) take each constituent's Relevant Order Book at the Effective
  Time; (2) consolidate, capping any level's size at the dynamic order-size cap
  (trimmed mean + 5 sd of the winsorised level sizes within 5 % of best, k = 1 % trimmed,
  max 50 levels per side); (2a) **uncross** the consolidated book (added 29 Jun 2026,
  v16.8 / Spot v15.4); (3) build cumulative bid/ask/mid price-volume curves at dynamic
  spacing (min of liquidity-based and KDE-based spacing, target 100 levels); (4) utilised
  depth = largest volume where the mid-spread curve deviates <= delta from mid (delta = 0.5 %
  BRTI; 1 % ETH, SOL, XRP, DOGE, ZEC, BNB, HYPE; **25 % NEAR**); (5) weight the mid
  price-volume curve by an exponential density with lambda = 1/(0.3 x utilised depth);
  (6) index = weighted sum. It is order-book only ("as opposed to trade data"), hence
  "both a Markov process and a martingale" by construction (section 4.2).
- **Frequency / lag thresholds (section 6.2):** BRTI, ETHUSD_RTI, SOLUSD_RTI, XRPUSD_RTI,
  DOGEUSD_RTI: Effective Time every 200 ms, Retrieval Lag Threshold 10 s (BRTI/ETH/SOL/XRP
  changed 18 May 2026; DOGE 18 May 2026). ZECUSD_RTI, BNBUSD_RTI, HYPEUSD_RTI,
  NEARUSD_RTI: every second, 30 s. Dissemination "Standard: approximately every second
  (top-of-second)", "Maximum: approximately every 200 milliseconds (upon request)".
- **Staleness:** a constituent whose Retrieval Time is older than the threshold is dropped
  for that calculation; if ALL are stale -> calculation failure -> no value published for
  that second (section 5.1, 5.5). Retrieval Time for a WebSocket source is "the most recent
  time as of which the Calculation Agent has a valid Order Book from an unbroken connection".
- **Erroneous data:** unparseable, one-sided or crossed books are dropped (5.2.1); a
  constituent whose own mid deviates from the median of constituent mids by more than the
  Potentially Erroneous Data parameter (5 % BTC/ETH/SOL; 10 % XRP, DOGE, ZEC, BNB, HYPE,
  NEAR) is dropped and stays dropped until back within half the threshold (5.3).
- **Precision:** BRTI 0.01; ETHUSD_RTI 0.01; SOLUSD_RTI 0.01; DOGEUSD_RTI 0.000001 (Kalshi
  rounds its average to 7 dp); ZEC 0.0001; BNB 0.001 (Kalshi rounds to 2 dp); HYPE 0.0001;
  XRP/NEAR precision rows not legible in the extract (Kalshi rounds both to 4 dp).
- **Constituents (RTI only; dates = added):** BRTI: Bitstamp, Coinbase, Kraken (2016),
  Gemini (30 Aug 2019), LMAX Digital (3 May 2021), Bullish (30 Dec 2024), Crypto.com
  (31 Mar 2025); **itBit suspended 27 Jul 2026**. ETHUSD_RTI: Bitstamp, Kraken, Gemini,
  Coinbase, LMAX, Crypto.com, Bullish (14 Jul 2025); itBit suspended 27 Jul 2026.
  SOLUSD_RTI: Coinbase, Kraken, Gemini, LMAX (24 Feb 2025), Bitstamp (14 Jul 2025),
  Bullish (14 Jul 2025 per version history). XRPUSD_RTI: Bitstamp, Kraken, Coinbase
  (18 Jul 2023), LMAX (29 Jul 2024). NEARUSD_RTI: Coinbase, Kraken. DOGEUSD_RTI: Coinbase,
  Gemini, Kraken. HYPEUSD_RTI: Bitstamp, Coinbase, Kraken (all 20 Apr 2026).
  **ZECUSD_RTI: Coinbase, Kraken (Gemini suspended 8 Jun 2026). BNBUSD_RTI: Coinbase,
  Kraken (3 Nov 2025).**
- **Disclosure:** CF Benchmarks is in the Payward (Kraken) group; Kraken is a constituent.
- **Nothing found:** no public figure for vendor->client publication latency; no statement
  that the last prints of a minute are treated differently (they are not, by the text).
- **So what (SPECULATION):** (a) the predictable-lag mechanism is stale-book carry: one
  constituent can carry a 10 s (big five) or 30 s (ZEC/BNB/HYPE/NEAR) old book into the
  index; `crypto_feeds.py` already records Coinbase/Kraken/Bitstamp/Gemini, which is the
  COMPLETE constituent set for DOGE, ZEC, BNB and HYPE, so a per-exchange "last update age"
  flag could be built from data on disk; (b) for BTC/ETH we lack Bullish, Crypto.com, LMAX,
  so a full rebuild of BRTI from our feeds is impossible, but the 5 Hz channel gives the
  next best thing; (c) NEAR's 25 % utilised-depth band means its index reaches far deeper
  into the book than the others, i.e. it reacts more to depth changes than to top-of-book.

## 4. Kalshi rules for the 15-minute crypto series

| Claim | Source | Class |
|---|---|---|
| Rules text (all nine coins, same template): "If the simple average of the sixty seconds of CF Benchmarks' <INDEX> before <close> ... is at least the simple average of the sixty seconds of CF Benchmarks' <INDEX> before <open> ..., then the market resolves to Yes"; "At the last minute before expiration, 60 RTI prices are collected. The official and final value is the average of these prices, rounded to the nearest N decimal places" with N = 2 (BTC, BNB), 4 (XRP, HYPE, ZEC, NEAR), 7 (DOGE); strike displayed to the same precision (BTC 82978.16; XRP 1.4130; DOGE 0.0879727) | robinhood.com/us/en/prediction-markets/crypto/events/{btc,xrp,doge,hype,zec,bnb,near}-15-min-...-oct-08-2026 (read 2026-10-08); kalshi.com/markets/kxbtc15m, kxxrp15m via r.jina.ai | FACT |
| Contract terms (CRYPTO15M.pdf, dated 5 Oct 2026; market pages now link assets.kalshi.com/contract_terms/CRYPTO.pdf): Underlying = "spot price ... according to a simple average of the CF <cryptocurrency> <index> for the 60 seconds prior to <time>"; Payout Criterion operators `above/below/between/exactly/at least`; "If no data is available or incomplete on the Expiration Date at the Expiration Time, then affected strikes resolve to No"; Source Agency = CF Benchmarks (no backup list); Contingencies = Kalshi may initiate Market Outcome Review under Rule 6.3(d); Position Accountability Level $25,000 per strike per Member; minimum tick $0.01 in the template | kalshi-public-docs.s3.amazonaws.com/contract_terms/CRYPTO15M.pdf | FACT |
| Coin Race (KXCRYPTOLEAD15M): BTC, ETH, SOL, XRP, HYPE; return = (end - start)/start x 100 using "the time-weighted average of the Spot Rate values published by CFBenchmarks during the 60-second intervals" at open and close; rounded to 0.001 %; tie -> each tied contract pays $1/n rounded down to the cent, others No; open 5:30, close 5:45, settlement projected 5:50 AM EDT (5-minute settlement lag) | kalshi.com/markets/kxcryptolead15m via r.jina.ai (2026-10-08) | FACT |
| By analogy, Kalshi's Bitcoin-vs-gold comparative contract (certified 12 Aug 2025) resolves No on an exact tie, rounds to 4 dp, waits up to 24 h for primary data, and falls back to "the average of the three most recent prices from Coinbase, Kraken, and Bitstamp" if BRTI is unavailable; the 15M terms contain NO such fallback | cftc.gov/.../ptc08122528435.pdf | FACT (different contract) |
| Rulebook v1.29 (17 Aug 2026): 6.3(c) Kalshi has "sole discretion to interpret a Contract's Terms"; where the Underlying cannot be measured and the terms are silent, it may settle at last traded price or refer to the Outcome Review Committee (final). 7.1: review decided within 24 h, posted on the website. 7.2(a): Kalshi may designate a new Source Agency if the source "is unavailable or undergoes significant modifications"; 7.2(b): "delayed data from a source" lets Kalshi move the Expiration Date/time. Halts: CRO/CEO may pause or halt "to prevent or reduce the potential risk of price distortions", explanation within 24 h. Prohibited: spoofing and "intentional or reckless disregard for the orderly execution of transactions during the closing period"; wash trades, money passes, front-running | kalshi-public-docs.s3.amazonaws.com/regulatory/rulebook/Kalshi%20DCM%20Rulebook%20v.1.29.pdf | FACT |
| When the strike is fixed: implicit in the rules (the opening 60 s average is only known at open + 0 s); no document states when Kalshi publishes `floor_strike` to the API; the settlement-timing study below measured ordinary Kalshi markets at mean 322.5 s determination->settlement (max 7,133 s) | arXiv 2610.00165 (15 Sep 2026) | REPORTED |
| Sept/Oct 2026 changes to the 15M series: none found (contract terms re-dated 5 Oct 2026, content is the generic template); expansions only (gold 15-min 7 Aug 2026 on Pyth; HYPE index 20 Apr 2026; ZEC, BNB, NEAR listed) | thelines.com (30 Sep 2026); cryptonomist (7 Oct 2026) | nothing found / REPORTED |
| **Contradiction with RUNBOOK:** RUNBOOK lists ADA, BCH, TON siblings; the live 15M set per Robinhood on 2026-10-08 is BTC, ETH, XRP, SOL, DOGE, ZEC, HYPE, BNB, NEAR (consistent with CLAUDE.md's "zero settled markets" note for ADA/BCH/TON). RUNBOOK's "Makers pay no fee" is true only for `quadratic` series. | | FACT |

## 5. Who trades these markets

| Claim | Source | Class |
|---|---|---|
| KXBTC15M: 3.06 M trades/day, $115.2 M/day turnover, 30-day $3.5 B, peak day 21 Sep 2026 $153.2 M; ~95 markets/day; average spread 0.54c; average best-bid/ask depth $65.6 K; buy share 48 %; last 14 days 50/50 Up/Down | cryptostruct.com/prediction-markets/kalshi-btc-15m (data vendor, read 2026-10-08) | REPORTED |
| September 2026: BTC 15-min fees est. $60.4 M, ETH 318 M contracts, gold 542 M contracts; week to 5 Oct: 15-min markets 13 % of volume, 20 % of fees; weekend records 26-27 Sep $3.03 B/day exchange-wide, combos ~2/3 | en.cryptonomist.ch (7 Oct 2026); PMP (5 Oct 2026) | REPORTED |
| 3,320 BTC windows 24 Aug-27 Sep 2026: favourites at 95-99c with ~90 s left won 97.8 %; prices calibrated within 1 point per 10c band; 8.8 % of windows decided by < $10, 23 % by < $25; independent settlement recomputation median gap 13c, 98 % within $1 | predictionmarketspicks.com/articles/is-kalshi-bitcoin-rigged (28 Sep 2026) | REPORTED |
| 1,200 BTC windows 4 Sep-5 Oct 2026: final-two-minute reversals 4 of 629 when the index was >= $50 from the strike; 19-26 % when within $25; volume ~60x normal when the price sits near 50c (the article's "1.9-2.9 million contracts per window" median is inconsistent with cryptostruct's totals and is probably mislabelled) | oddsshopper.com/.../are-kalshi-15-minute-bitcoin-markets-rigged (5 Oct 2026) | REPORTED |
| Book shape: tightest in the middle 5 minutes; "depth thins as MMs pull risk going into close"; final 60 s "a settlement auction" converging to 99c/1c | kalshibacktest.com/resources/kalshi-btc-15-minute-markets (8 Apr 2026) | REPORTED |
| Market-making guide classifies crypto 15-min as "BOTS ONLY", "High, fast" informed flow, "Extreme" resolution risk; stale quotes picked off within hundreds of ms | turbinefi.com/blog/how-to-market-make-prediction-markets-2026 (19 Jun 2026) | REPORTED |
| Open-source bots (none publish results): seanrobenalt/kalshi-bot buys YES+NO when combined ask < $1 and, inside 60 s, buys the side in the 90-97c band ("it lost me $100"); brandononchain/kalshibot: Binance-vs-Kalshi latency (claims 3-7 s Kalshi repricing lag), no entries in last 30 s; defi-ape bot: buy Polymarket UP when Kalshi YES is 93-96c and Polymarket >= 10c cheaper, 5 s polling; kapelame framework: strategy left blank; 30+ repos listed by botforkalshi | github.com (read 2026-10-08) | REPORTED |
| Kalshi affiliate Kalshi Trading LLC is a market maker; Flutter ~15 % of combo volume (sports) | navnoorbawaresearch.com (14 Aug 2026); PMP (5 Oct 2026) | REPORTED |
| Polymarket: 5/15-min/4 h crypto up/down; Chainlink 60 s TWAP at both ends since 7 Aug 2026 (5-min since 14 Aug); `source` field names pyth/massive/chainlink (29 Sep 2026); taker fee 0.07 x p(1-p) on crypto (docs) - the changelog's "1.56 % at 50 %" (12 Feb 2026) implies a lower rate at launch; makers 0 fee + 20 % rebate of fees; taker delay 250 -> 50 ms (17 Aug) -> 150 ms (4 Sep 2026); volume fell ~40 % after the TWAP switch; amended Market Maker Program effective 15 Oct 2026 | docs.polymarket.com/changelog/changelog; docs.polymarket.com/polymarket-learn/trading/fees; tradoxvps.com/polymarket-twap-settlement (31 Jul 2026); PMP | FACT (docs) / REPORTED (effects) |
| Polymarket US (QCX LLC, CFTC DCM) launched 3 Dec 2025, waitlist dropped May 2026, full KYC; NY Attorney General sued Polymarket (early Oct 2026); self-exclusion/deposit limits added 30 Sep 2026 | cryptonews.com; PMP (5 Oct 2026) | REPORTED |
| Direct evidence of "last-second dumps" or named latency-arb firms on Kalshi 15M: **nothing found** beyond the generic "BOTS ONLY" characterisation | - | nothing found |

## 6. Structural risks (Oct-Dec 2026)

| Item | Source | Class |
|---|---|---|
| CFTC sent to OIRA on 28 Sep 2026 (a) a proposed rule "Further Definition of 'Swap' to Include Event Contracts" and (b) an interim final rule "... to Exclude Casino-Style Gambling Products", effective on publication; texts unpublished | PMP (5 Oct 2026) | REPORTED |
| CFTC Enforcement advisory 25 Feb 2026: two Kalshi insider cases (candidate trading on own race; YouTube editor), "full authority to police illegal trading practices" on DCMs | cftc.gov/PressRoom/PressReleases/9185-26 | FACT |
| CFTC approved Kalshi BTCPERP 28 May 2026; CFTC sued New Mexico 12 Jun 2026; N.D. Ill. preliminary injunction for Kalshi/Coinbase/CFTC 2 Oct 2026 (sports); Michigan: Coinbase to close sports positions by 10 Oct 2026 - sports only, no crypto action found | cftc.gov press room; PMP; faruqilaw.com | FACT / REPORTED |
| Kalshi delisting or tick-size change for crypto 15M: nothing found; opposite direction (new 15-min series, gold on Pyth) | - | nothing found |
| Maintenance: Thursday 03:00-05:00 ET weekly (FACT, section 2); no other scheduled downtime found; status.kalshi.com does not resolve | docs; CFTC filing | FACT / nothing found |
| Settlement-source changes: none for CF Benchmarks indices; CF demised Ethena spot rate (24 Aug 2026), suspended itBit from BRTI/ETH (27 Jul 2026), Gemini from ZEC (8 Jun 2026) - constituent churn is routine and unannounced to Kalshi users | CF constituent docs | FACT |
| Kalshi rulebook v1.29 (17 Aug 2026) and DCO rulebook v1.4 (27 Apr 2026) current | kalshi.com/regulatory/rulebook via proxy | FACT |

## 7. Academic / practitioner results

| Paper | Usable content | Class |
|---|---|---|
| Dai, Jia, Yu, "Settlement Manipulation in Prediction Markets", arXiv 2606.31675 (30 Jun 2026) | Polymarket BTC 5-min vs 15-min: "settlement-time spot order flow spikes, causing large price reversals after settlement"; manipulation "prevalent in five-minute contracts but largely absent in the fifteen-minute contracts"; "lengthening the contract horizon removes it"; profits "mostly from retail". Secondary numbers (tradoxvps): ~16,000 contracts, 821 wallets, $8.2 M, 93 % of losses retail, final-10-s volume share 5.68 % vs 3.05 % baseline | FACT (abstract) / REPORTED (numbers) |
| Dubach, "Anatomy of a Decentralized Prediction Market", arXiv 2604.24366 (27 Apr 2026) | 30 B Polymarket book events: no residual time-to-close effect on depth once duration/price/volume are controlled; trade-direction inference from the public feed is right only ~59 % of the time (Kalshi's `taker_side` is exchange-supplied, so not our problem) | FACT (abstract) |
| Portnaya, arXiv 2606.19517 (17 Jun 2026) | Polymarket BTC threshold contracts vs Binance option-implied probabilities: 5.6-11 pp wedge, largest at low probabilities, AR(1) half-life ~4 h; not near-expiry | FACT (abstract), not usable |
| Nechepurenko, arXiv 2610.00165 / 2610.00173 (Sep 2026) | Kalshi settlement finality: 7.6 M market objects; ordinary markets mean 322.5 s determination-to-endpoint, max 7,133 s; price-at-decidability study not yet run | FACT (abstract), marginal |
| Binary options with Asian-style (averaged) settlement near expiry, adverse selection in the last minute | **nothing found** that is directly usable; the Asian-option literature only establishes that averaging reduces manipulation incentives and delta sensitivity | nothing found |

---

## Appendix: sources with dates

- docs.kalshi.com: /changelog (entries 9 Jun - 15 Oct 2026), /getting_started/rate_limits,
  /getting_started/exchange_sharding, /getting_started/maintenance_and_pauses,
  /getting_started/subaccounts, /getting_started/fee_rounding, /getting_started/settlement_bounds,
  /getting_started/market_settlement, /api-reference/orders/create-order-v2,
  /api-reference/market/get-market, /api-reference/market/get-series,
  /api-reference/portfolio/create-subaccount, /api-reference/incentive-programs/get-incentives,
  /api-reference/exchange/get-exchange-status, /websockets/cfbenchmarks-value,
  /websockets/user-fills, /websockets/public-trades, /cfbenchmarks/rest-passthrough,
  /fix/order-entry, /fix/connectivity, /margin (all read 2026-10-08).
- CF Benchmarks: CME CF Real Time Indices Methodology v17.0 (21 Sep 2026); CF Spot Rate
  Methodology Guide v16.0 (5 Oct 2026); CME CF Constituent Exchanges v13.7 (24 Aug 2026);
  CF Constituent Exchanges v10.3 (5 Oct 2026); index pages BRTI, SOLUSD_RTI, DOGEUSD_RTI,
  ZECUSD_RTI, BNBUSD_RTI, HYPEUSD_RTI (8 Oct 2026); newsletter 99 (23 Jan 2026).
- Kalshi: contract_terms/CRYPTO15M.pdf (5 Oct 2026); contract_terms/BTC.pdf; DCM Rulebook
  v1.29 (17 Aug 2026); market pages kxbtc15m, kxxrp15m, kxcryptolead15m (8 Oct 2026, via
  r.jina.ai); Robinhood mirrors of the 8 Oct 2026 05:30-05:45 ET windows for DOGE, HYPE,
  ZEC, BNB, NEAR and the 6 Mar 2026 BTC window; help.kalshi.com trading-hours article
  (23 Aug 2026). NOT read (429): kalshi.com/docs/kalshi-fee-schedule.pdf, /regulatory,
  /regulatory/notices, /markets/kxdoge15m, /markets/kxhype15m.
- CFTC: rules07152610358.pdf (LIP amendment, 15 Jul 2026); rules0625267305.pdf (perp fee
  rebate, 24 Jun 2026); rules02232639698.pdf (maintenance hours, 23 Feb 2026);
  ptc08122528435.pdf (BTC-vs-gold certification, 12 Aug 2025); press releases 9185-26
  (25 Feb 2026), 9240-26 (28 May 2026), 9251-26 (12 Jun 2026).
- Polymarket: docs.polymarket.com/changelog/changelog; docs.polymarket.com/polymarket-learn/trading/fees.
- Secondary: predictionmarketpulse.substack.com (5 Oct 2026); navnoorbawaresearch.com
  (14 Aug 2026); predictionmarketspicks.com (28 Sep 2026; 25 Sep 2026); oddsshopper.com
  (5 Oct 2026); cryptostruct.com (8 Oct 2026); kalshibacktest.com (8 Apr 2026);
  turbinefi.com (19 Jun 2026); tradoxvps.com (31 Jul 2026); en.cryptonomist.ch (7 Oct 2026);
  thelines.com (30 Sep 2026); alphascope.app (6 Oct 2026); botforkalshi.com (9 Sep 2026);
  polykal.net (12 Sep 2026); cryptonews.com (Sep 2026); github.com repos (seanrobenalt,
  brandononchain, kapelame, defi-ape); dev.to (29 Jul 2025).
- arXiv: 2606.31675, 2604.24366, 2605.02287, 2606.19517, 2610.00165, 2610.00173, 2609.17902, 2606.16852.

---

## 9. Self-trade prevention (STP) across subaccounts - follow-up to finding 9

All quotes from docs.kalshi.com, read 2026-10-08. No API calls.

**(a) Modes, what each does, and where the setting lives**

- REST (Predictions, Create Order V2): the request field `self_trade_prevention_type` is a
  **per-order field, listed in the `required` array** of `CreateOrderV2Request`; no
  account-level or API-key-level default is documented. Enum values and the verbatim
  behaviour text:
  - `taker_at_cross`: "cancels the taker order when it would trade against another order
    from the same user; execution stops and any partial fills already matched are
    executed."
  - `maker`: "cancels the resting maker order and continues matching."
  (docs.kalshi.com/api-reference/orders/create-order-v2) **FACT**
- FIX (Predictions order entry): tag `2964 SelfTradePreventionType`, Integer, optional,
  "`1`=Taker At Cross (default), `2`=Maker". Execution-report `Text(58)` values
  `SELF_CROSS_ATTEMPT`, `TAKER_CANCEL_FOR_SELF_TRADE_PREVENTION`,
  `MAKER_CANCEL_FOR_SELF_TRADE_PREVENTION` each map to `ExecType=Canceled`; the page does
  not spell out which one fires in which mode. (docs.kalshi.com/fix/order-entry) **FACT**
- WebSocket `user_orders` carries `last_update_reason` with enum values `Decrease, Amend,
  MarginCancel, SelfTradeCancel, ExpiryCancel, CloseCancel, HaltCancel, Trade,
  PostOnlyCrossCancel, ReduceOnlyCancel, SettlementBoundsCancel` - so an STP cancel is
  observable on our own order stream as `SelfTradeCancel`. (docs.kalshi.com/websockets/user-orders)
  **FACT**
- REST `GET /portfolio/orders` documents no reason field; the cancel reason is only on the
  WebSocket/FIX streams. **FACT**
- Discrepancy to note: the changelog entry of **17 Apr 2026** reads "NewOrderSingle accepts
  SelfTradePreventionType(7928) with values CancelResting(1), CancelIncoming(2), or
  CancelBoth(3)" - a different tag number and a third mode. The current Predictions FIX
  page shows tag 2964 with two modes. Either the April entry concerns the margin/perps FIX
  session or the spec was revised; not resolvable from the docs read. **FACT (both texts) /
  SPECULATION (which applies to Predictions today)**

**(b) Does it apply across subaccounts of one account? Yes - verbatim:**

> "Self-trade prevention applies across all subaccounts of an account. When an order from a
> restricted key would trade against an order resting in another subaccount, its
> `self_trade_prevention_type` decides the outcome: `taker_at_cross` cancels the restricted
> key's order, and `maker` cancels the resting order in the other subaccount."
> (docs.kalshi.com/getting_started/subaccounts, section "Restricted API keys") **FACT**

The sentence is written for restricted keys; the first clause ("applies across all
subaccounts of an account") is unconditional. The create-order text says "from the same
user", and a subaccount is the same user. The `sub_users_vs_subaccounts` page adds nothing
on matching. **FACT (quote) / the reading that an unrestricted key on subaccount 0 is
treated the same is SPECULATION, though implied by "same user".**

**(c) Is the book unified so a YES bid at 98c in subaccount 1 meets a NO buy from subaccount 0?
Yes - the book is one object with two labels:**

- "The order book shows all active bid orders for both yes and no sides of a binary market"
  and "a bid for yes at price X is equivalent to an ask for no at price (100-X). For example,
  a yes bid at 7c is the same as a no ask at 93c" (docs.kalshi.com/api-reference/market/get-market-orderbook).
- "Kalshi's orderbook only returns bids, not asks." "A NO BID at price Y is equivalent to a
  YES ASK at price ($1.00 - Y)" (docs.kalshi.com/getting_started/orderbook_responses).
- Order direction: "`bid` == yes, `ask` == no, always"; "buy no" == `outcome_side: no` +
  `book_side: ask` == "sell yes"; "An order at price `p` with `outcome_side=no` is matched by
  an order at the same price `p` with `outcome_side=yes`" (docs.kalshi.com/getting_started/order_direction).
  In V2 the `price` is the YES price and `side: ask` means "sell the YES leg ... economically
  equivalent to buying NO at `1 - price`" (create-order-v2). **FACT**

Applied to the question: a resting YES bid at 98c in subaccount 1 IS a resting NO ask at 2c.
A NO buy from subaccount 0 with a NO limit of 60-70c (= willing to sell YES down to 30-40c)
crosses every NO ask priced <= 70c, and the 2c NO ask (the 98c YES bid) is the BEST-priced
one, so it is the first order the IOC would match, at the resting price (2c NO) under the
RUNBOOK's measured "fills at the resting order's price" rule. Because both orders belong to
the same user, STP fires instead of a fill: with `taker_at_cross` the incoming NO IOC is
cancelled ("execution stops"); with `maker` the 98c YES bid in subaccount 1 is cancelled and
the IOC continues to the next NO ask. **FACT for the mechanics; SPECULATION only in that
no doc shows this exact cross-subaccount example.** Consequence for the two bots: the
pinrun hedge (buy NO at 60-70c after a flip) will be cancelled whenever the ladder still has
a stale YES bid at the top of the book, which is exactly the flip scenario; `maker` mode
would instead pull the ladder's stale bid and let the hedge proceed. **SPECULATION**

**(d) Dates**

- Oldest public changelog entry: 17 Apr 2026 (FIX STP tag/values quoted above). The REST
  `self_trade_prevention_type` field's introduction is not dated in the public changelog
  (it predates or is not listed); FIX tag 2964 as documented today carries no date. **FACT**
- V2 order endpoints with `outcome_side`/`book_side`: 14 May 2026 ("New V2 order endpoints
  POST /portfolio/events/orders and DELETE /portfolio/events/orders accept outcome_side and
  book_side"); legacy `action`/`side` supported until 28 May 2026. **FACT**
- Subaccount creation for direct members with Advanced API access: 9 Jun 2026 ("Authorized
  direct members with Advanced API access can now create subaccounts via
  POST /portfolio/subaccounts"). **FACT**
- Sub-account-restricted API keys (the context of the cross-subaccount STP sentence):
  2 Jul 2026. **FACT**
- `last_update_reason` on `user_orders` WebSocket messages: 1 Oct 2026. **FACT**
- No changelog entry between 9 Jun and 15 Oct 2026 mentions self-trade prevention, so the
  cross-subaccount behaviour has no dated announcement; it is documented as current. **FACT**
