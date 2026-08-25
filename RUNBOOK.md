# RUNBOOK — Kalshi 15-Minute Crypto Research

**For Claude Code.** Read this fully before running anything. It contains
facts that cost many round trips to establish. Re-deriving them wastes time;
contradicting them without new measurement is an error.

Working directory: `C:\kals`

---

## HARD RULES

1. **NEVER place, amend, or cancel an order.** No `POST /portfolio/orders`,
   ever. This project is read-only research. `kalshi.pem` is present so the
   WebSocket can authenticate for market data — that is its only use here.
2. **Never claim a result you did not measure.** If a script fails, report the
   failure. Do not estimate what the output "would have been."
3. **Cluster by market, always** -- but know that this is NOT sufficient.
   Hundreds of trades share one settlement outcome, so statistics on trade
   counts are wrong by ~14x. That produced the fake "26 mispriced cells with
   21c edges". HOWEVER: clustering corrects STANDARD ERRORS, not POINT
   ESTIMATES. Occupation-time selection (how long a price path lingers near a
   level is correlated with where it ends up) biases the estimate itself and
   survives clustering untouched. See R4. Sample on an exogenous schedule
   (fixed times-to-close), not on trade arrivals.
4. **Report `n` as the number of markets, never the number of trades.**
5. Do not modify anything under `kalshi_data/` or `feed_data/` — a collector
   is actively writing there.
6. **Calibrate every estimator against ground truth before believing it.**
   Five fake-edge bugs were found in two days, none catchable by inspection,
   all caught by asking a statistic what it returns when the answer is already
   known. Every tool in `research/` refuses to touch real data until its
   self-test passes. Do not remove that gate.
7. **Never infer a price's unit from its magnitude.** On the tapered deci-cent
   grid a 0.5-cent quote is written "0.5"; any `x > 1` test reads it as 50
   cents. Decide the unit once from the whole sample. That bug alone produced
   75c/contract against a provably fair book.

---

## PROJECT STATE

Goal: determine whether a tradeable edge exists in Kalshi's 15-minute crypto
up/down markets. No money has been deployed. Current confidence that a
tradeable edge exists: **3-5%**, driven down by the efficiency result below.

A collector has been running since 2026-08-25 under `run_all.ps1` (watchdog +
`kalshi_collector.py` + `crypto_feeds.py`). Leave it running.

---

## CONFIRMED FACTS — do not re-derive

**Contract.** `KXBTC15M` and siblings (ETH, SOL, XRP, DOGE, BNB, ADA, BCH,
ZEC, HYPE, NEAR, TON). A new window opens every 15 minutes, 24/7.

**Settlement**, from `rules_primary` on the market record:
> Resolves Yes if the simple average of the sixty seconds of CF Benchmarks'
> BRTI before the close is at least the simple average of the sixty seconds
> before the open.

So **strike = opening 60s TWAP** and **settlement = closing 60s TWAP**. The two
averaging windows are 840s apart. Therefore:
```
Var(settle - strike) = 20 + 920 - 2(30) = 880 * sigma^2
```
(NOT 900, and NOT 820 — both were earlier errors.)

**CORRECTED (R1).** It was previously recorded here that every window opens at
exactly 50c fair value by construction. That is the UNCONDITIONAL mean. The
conditional fair value -- the only one tradeable -- is
`Phi((spot_at_open - strike) / (sigma*sqrt(860)))`. Strike is the TRAILING 60s
average and spot at open is not that average; their difference has sd
sqrt(20)*sigma ~ $26 against a settlement sd of ~$176. Mean |fair - 50c| is
**4.75c**, and 40% of windows open outside 45-55c. So there IS a directional
view at open, requiring no forecasting.

**Fees.** `fee_type: quadratic`, `fee_multiplier: 1` →
`ceil(0.07 * P * (1-P) * n)` per order. S&P/Nasdaq get 0.035 but have no
short-cadence markets, so that lever is unavailable.

**Tick grid.** `tapered_deci_cent`: 0.1c below $0.10, 1.0c from $0.10-$0.90,
0.1c above $0.90.

**Volatility.** BTC ~0.1765% per window (~33% annualized) as of late Aug 2026.
The June archive showed 0.2353% (~45%) — regime changed, so prefer recent data.

**Tails. CORRECTED (R3) — the 96.7c crossover is an artefact of the statistic.**
14 unrelated fat-tailed processes (Student-t nu=3..20, GARCH across a range of
persistence, normal mixtures) all cross at 96.3-99.3c regardless of kurtosis
magnitude (1.0 to 168). It sits close to a fixed point of standardizing ANY
fat-tailed distribution, so agreement across two datasets establishes only that
returns have excess kurtosis — never in doubt, and not something needing two
datasets to show. Do NOT build a threshold strategy on that number; the
informative quantities are the tail RATIOS at the price you would trade.
Per-series kurtosis 25 (BTC) to 153 (NEAR); pooling series is a mistake.
Whether the fatness is unconditional or merely vol clustering is what decides
the model — `research/volmodel.py` separates them.

**API traps.**
- WebSocket `cfbenchmarks_value` requires param **`index_ids`** (values:
  `BRTI`, `ETHUSD_RTI`, `SOLUSD_RTI`, ...). Subscribing without it returns
  `{"type":"subscribed"}` and then silently delivers nothing. **A `subscribed`
  reply is NOT success — only a data frame is.**
- `pyth_value` accepts `underlying_tickers` but sent no data in 5s. Low
  priority.
- `/historical/markets` and `/historical/trades` are **stale**, serving an
  archive ending ~2026-06-24. `/historical/trades` **ignores `series_ticker`**
  entirely and returns unfiltered global trades. Use `/markets?status=settled`
  and `/markets/trades?ticker=...` instead.
- `/markets/trades` with `limit=200` returns only each market's **last** 200
  prints. This caused a severe truncation bias. **Always paginate the full
  tape with the cursor.**
- REST `/markets/{t}/orderbook?depth=N` returns levels **ascending** and
  truncates from the bottom, hiding top-of-book.
- Reading a `.gz` the collector is writing raises `EOFError` **or**
  `zlib.error` — catch broad `Exception`, not `OSError`.
- Rate limits: Basic tier ~20 reads/sec. Sleep ~0.08s between calls.

**Measured latency.** CF→Kalshi 63ms median; Kalshi→this machine 37ms median
with only 2ms jitter. A colocated firm sees ~1-5ms, so the disadvantage is
~30ms — negligible against a 60-second settlement average.

---

## THE KEY RESULT SO FAR -- NOT YET ESTABLISHED (R4)

Full-tape calibration on **2.1M trades across 450 markets**, clustered by
market, reported mean t = -0.008 and was read as "the market is efficient".
**That compared the estimator's output to zero, and the estimator does not
return zero on an efficient market.** On a synthetic book quoting the true
model exactly, the same scheme returns mean t = -1.03 with 12 of 84 cells at
|t|>=2, from occupation-time selection. The bias depends on the trade-arrival
process, so its size on real data is unknown until measured.

`research/placebo.py` measures it, using data already on disk: keep the real
tape and redraw only the outcomes as y ~ Bernoulli(p_last), which is
martingale-consistent under the efficient-market null. Until that runs, neither
"efficient" nor "inefficient" is established.

The original table, for reference:

| | Observed | Efficient market predicts |
|---|---|---|
| Mean t across 71 cells | −0.008 | 0 |
| SD of t | 0.775 | 1 |
| Cells at abs(t) ≥ 2 | 3 | 3.2 |

The one cell at t=4.1 (180-480s @ 0.95) flips sign in the adjacent time
bucket, so it is noise. **This measured price vs outcome only.** It did not
test order flow, trade size, or the index path — which is what remains.

---

## FILES

| File | Purpose |
|---|---|
| `run_all.ps1` | Watchdog; keeps the two recorders alive. Already running. |
| `kalshi_collector.py` | Records Kalshi book/trades/index. Read-only. |
| `crypto_feeds.py` | Records Coinbase/Kraken/Bitstamp/Gemini books. |
| `kalshi_gate1.py` | Verifies we can reproduce settlement. THE gate. |
| `kalshi_brti.py` | Discovers + pulls historical index prices. |
| `kalshi_signals.py` | 8 hypotheses on flow, size, blocks, open price. |
| `kalshi_backtest.py` | Event-driven replay, look-ahead-proof. |
| `kalshi_fulltape.py` | Pulls full untruncated trade tapes. |
| `PLAN.md` | Full reasoning and kill criteria. |

Data already on disk: `fulltape/markets.json` (450 markets),
`fulltape/tapes.json` (2.1M trades).

---

## TASKS, IN ORDER

### T1 — Signal mining (instant, uses existing data)
```
python kalshi_signals.py --out ./fulltape
```
Check the first line: `with taker_side: N`. **If N is 0**, `/markets/trades`
omits the field; re-pull a sample using a different endpoint and report what
fields actually exist. Report every hypothesis result with market counts.

### T2 — Backtest (instant)
```
python kalshi_backtest.py --out ./fulltape --strategy all --entries 10
python kalshi_backtest.py --out ./fulltape --strategy all --entries 10 --pessimistic
```
The integrity check must print PASS (a cheating strategy must raise
`AttributeError`). **Only TEST-split results count.** If `random` shows a
profit outside its confidence interval, the harness is broken — stop and
report, do not proceed.

### T3 — Index history (the unlock)
```
python kalshi_brti.py --out ./fulltape --key-id <ID> --key-file kalshi.pem --discover-only
```
This probes ~25 candidate endpoint shapes for BRTI history. If none work,
**read the HTTP error bodies** — they usually name the required parameter.
That is exactly how the `index_ids` WebSocket param was found. Iterate on the
candidate list until one returns ≥10 points, then run without
`--discover-only` to bulk-pull.

Verify the built-in settlement spot-check matches `expiration_value` to
better than 1e-4 relative. **If it does not, stop.** Misaligned timestamps
invalidate everything downstream.

### T4 — Settlement gate
```
python kalshi_gate1.py --data ./kalshi_data
```
Needs markets that closed inside the recording span, so run after several
hours of collection.

### T5 — Lead-lag (build this once T3 succeeds)
The highest-value untested idea. Cross-correlate contract price changes
against BRTI changes at lags from −5s to +5s, per market, clustered.

- Peak at **positive lag** → the contract FOLLOWS the index → mechanical edge
  needing no forecasting. This is the most likely surviving edge, because it
  is a plumbing artefact rather than a pricing opinion.
- Peak at **zero lag** → the book tracks the index in real time → dead end.

Then build a fair-value model: `P(settle >= strike)` from the index path plus
trailing realized vol. **CORRECTED (R1) — both variance formulas below were
wrong.** Use `Var = sigma^2 * (tau - 39.50)` before the averaging window opens,
with tau = seconds to CLOSE (the old `(tau + 20)` was derived for time-until-
the-window-starts and overstates vol by 32% at 120s out). Inside the window use
`sigma^2 * r*(r+1)*(2r+1)/21600`, the exact form for 60 DISCRETE prices; the old
`r^3/10800` is the continuous integral and understates vol by 7.5% at r=10 and
73% at r=1, which biases toward overpricing favourites. Score it against the traded price via `kalshi_backtest.py` by
adding a strategy function.

---

## REPORTING

After each task write `RESULTS_T<n>.md` containing the command, the raw
output, and a plain-language read. State market counts, not trade counts.
Flag anything that looks too good — every large edge found in this project so
far has been a bug in the measurement, not a real opportunity.
