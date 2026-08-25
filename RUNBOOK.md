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
3. **Cluster by market, always.** Hundreds of trades share one settlement
   outcome. Statistics on trade counts are wrong by ~14x. This produced a fake
   "26 mispriced cells with 21c edges" result that was pure artefact.
4. **Report `n` as the number of markets, never the number of trades.**
5. Do not modify anything under `kalshi_data/` or `feed_data/` — a collector
   is actively writing there.

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

Consequence: every window opens at **exactly 50c fair value by construction**.

**Fees.** `fee_type: quadratic`, `fee_multiplier: 1` →
`ceil(0.07 * P * (1-P) * n)` per order. S&P/Nasdaq get 0.035 but have no
short-cadence markets, so that lever is unavailable.

**Tick grid.** `tapered_deci_cent`: 0.1c below $0.10, 1.0c from $0.10-$0.90,
0.1c above $0.90.

**Volatility.** BTC ~0.1765% per window (~33% annualized) as of late Aug 2026.
The June archive showed 0.2353% (~45%) — regime changed, so prefer recent data.

**Tails.** Winsorized, pooled: Gaussian model UNDERvalues the favourite below
~96.7c and OVERvalues above it. Crossover replicated at 96.6c on the June
archive and 96.7c on recent data — two independent datasets, so this is real.
Per-series kurtosis ranges 25 (BTC) to 153 (NEAR); pooling series is a mistake.

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

## THE KEY RESULT SO FAR

Full-tape calibration on **2.1M trades across 450 markets**, clustered by
market: the market is **efficient**.

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
trailing realized vol, using `Var = sigma^2 * (tau + 20)` before the averaging
window opens, and `sigma^2 * r^3 / 10800` with `r` seconds remaining once
inside it. Score it against the traded price via `kalshi_backtest.py` by
adding a strategy function.

---

## REPORTING

After each task write `RESULTS_T<n>.md` containing the command, the raw
output, and a plain-language read. State market counts, not trade counts.
Flag anything that looks too good — every large edge found in this project so
far has been a bug in the measurement, not a real opportunity.
