# HANDOFF — read this first in a new session

Everything needed to continue is in this repo. Nothing lives only in a chat.
Read this file, then `STATUS.md`, then `PLAN_V3.md`. `RUN_WHEN_HOME.md` is the
operator's card.

- **Branch**: `claude/file-uploads-70rtjl` (this is also the remote default —
  a plain `git pull` gets it).
- **Head at handoff**: see `git log -1`. Run 2 findings are in the section below.
- **User's machine**: Windows 11, Python 3.14.6, repo `C:\kals-repo`, data
  `C:\kals` (`kalshi_data/`, `feed_data/`, `fulltape/`, `run_all.ps1`).
- **State**: 19 self-tests, all passing. One full real run completed
  2026-08-26 (203 min); its findings and its faults are below.

---

## THE MAKER QUESTION — PRICED, AND IT IS WORSE THAN IT LOOKED

Run 2 reopened market-making by replacing PLAN.md's mis-parsed "3,767
contracts resting" with a measured ~30. Makers genuinely pay no fee: all
sixteen fifteen-minute series are fee_type="quadratic" (the only
quadratic_with_maker_fees series anywhere are KXBTCMAX125/150). The tick is
1c, the liquid series quote 1c wide, ZEC 7c and NEAR 8c.

**A first pass compared the half-spread against per-second diffusion and
concluded the wings were viable (quote beyond 92.1c at 900s). That framing is
wrong and optimistic**, and `research/maker.py` now says so in its own
docstring. You are not run over by the average second; you are run over by the
seconds in which somebody chose to trade with you.

### The fee theorem
A rational taker crosses only when their estimate beats the touch by more than
the fee, so E[F | ask lifted] >= a + fee(p), and

    E[maker P&L per fill] <= a - (a + fee(p)) = -fee(p)

**and the bound is invariant to how wide you quote** — widening raises the
half-spread on both sides and it cancels. Against informed flow a maker loses
the TAKER's fee every fill: -1.75c at 50c, -0.63c at 90c, -0.33c at 95c.
Paying no maker fee is why anyone quotes at all; it is not an edge.

Independent confirmations of the same answer: a queue/diffusion argument (30
contracts ahead, a 1-tick ATM level lives ~541ms at tau=900 while only ~9.4
contracts of one-side flow arrive, so the modal outcome is the level moving
away and the fills that DO occur are informed bursts, E[drift|fill] ~ 1.55c,
net -1.05c); and the transaction-cost split (at 50c the maker captures
h/(h+fee) = 22% of what counterparties pay, Kalshi takes 78%).

### So the strategy reduces to ONE measurable number
Noise flow pays you the half-spread; informed flow costs you the fee.

    E[P&L per fill] = q*h - (1-q)*fee      break-even q = fee/(fee+h)

At 50c that is **78% of all flow must be uninformed**; at 90c, 56%. That is
not assumable — it is exactly the signed markout `maker.py` measures.

### Two fatal bugs in the first maker.py, both of which its self-test passed
1. The pre-trade mid was "last quote at or before t". Book updates share the
   trade's integer second constantly, so it read the POST-trade mid and
   attenuated a planted 1.000c to **0.000c**.
2. The headline compared |post-trade move| against |random-grid move| — a
   volatility test, not a direction test. Trades cluster in volatile seconds,
   so on a tape with provably ZERO directional information it fired at
   **t = +171**.

Both fixed; both now planted in the self-test. **The deeper lesson: the
self-test exercised the SIGNED path while main() reported the ABSOLUTE path.
Testing a different quantity than you report is indistinguishable from not
testing.**

### What a paper trade can and cannot do (measured, not argued)
At 185 close-time clusters the P&L minimum detectable effect is 2.64c at a 95c
price and **8.46c at 55c** — and making happens mid-book, so 8.46c is the
honest number. Confirming a 0.5c edge from settlement P&L needs ~6,550
clusters (68 days) at 95c and ~54,000 (564 days) at 55c. **For a maker, extra
fills buy ZERO additional power on settlement P&L**, because every fill in one
market settles on the same single outcome.

The alternative is not a longer paper trade but a different estimator: signed
post-fill markouts have per-fill sd 1.36-2.47c, cluster SE 0.028-0.094c, and
an MDE of **0.08-0.26c at 185 clusters — 30-100x more powerful** than replayed
P&L, against a target quantity of ~0.5c. That is the measurement to run.

### The 59.9% index coverage is NOT a 40% hole rate
It is ONE contiguous ~18.6-hour recorder outage (the PC crash) inside a
46.36-hour wall-clock span, plus ~2,000s of short transport interruptions.
Dedup is definitively excluded: replay's own parse counter (999,590) exactly
equals the sum of the ten per-index distinct-second counts, and the live rate
measures 1.000 Hz/index. The data that exists is dense and fine.

### implied.py's pooling bug is fixed
Five sites pooled raw sigmas across series spanning 1e6 in price. The "1.192x
variance risk premium" was 0.7839/0.0118, where 0.0118 is literally SOL's
realised sigma alone and BTC+ETH supply 97.6% of the numerator. Now pools
per-series ratios, with a self-test that plants three series priced 1,000,000x
apart carrying a common ratio and checks the price level does not leak.

---

## RUN 2 (2026-08-27 02:39, 154 min) — THE FIRST COMPLETE RUN

All 13 stages produced data. 46.4 hours recorded, 72.6M orderbook deltas
parsed (100% of them, against 0% in run 1). Findings, and what is still wrong:

- **The maker strategy's death sentence was based on a mis-parsed number.**
  PLAN.md sec.4 killed it on "best bid 0.40 with 3,767 contracts resting",
  from a REST call RUNBOOK separately records as mis-parsed. Measured from the
  websocket: **median depth at the touch is 30 contracts**, 32 at 40c, 20 at
  50c. That is 125x smaller and a joinable queue. **NOT YET CONFIRMED** — see
  the sid bug below; it was measured on 24 of 1,090 markets.
- **PLAN_V3's #1 ranked idea is refuted.** "Does the book follow the index?"
  — it does not. The book **leads** by one second: beta 0.530 at lag -1
  (t=29.4, 108 df) against -0.001 at lag +1 (p=0.37). Corroborated by feeds,
  where our own replica also lags the published index by 0-1s. There is no
  stale-quote edge available from watching the index. Most likely the CF index
  is timestamped ~1s behind the information the market already has.
- **Implied vs realised volatility, per series** (the only trustworthy cut):
  BTC 0.88, ETH 0.86, SOL 0.89, BNB 0.94, DOGE 0.94, ZEC 1.03, NEAR 1.02,
  XRP 1.10, HYPE 1.25. The liquid series price volatility BELOW realised —
  the opposite of a variance risk premium. **The report's headline "VARIANCE
  RISK PREMIUM 1.192x" and the 59x-141x "vs realised" columns in the term and
  smile tables are a POOLING ARTEFACT** — implied.py averages sigmas across
  series whose price levels differ by six orders of magnitude (BTC ~5.59
  $/sqrt(s), DOGE ~0.00002). It must pool the per-series RATIOS, not the raw
  sigmas. **Unfixed.**
- **Cross-sectional: a clean null.** All 9 series "in line", max |t| = 2.2
  (BTC absolute 0.62c). 509-533 clusters each.
- **Replay P&L: -13.20, null 95% [-657, +365], 73rd percentile.** Nothing.
- **Median spread is 1.00c** on the liquid series (ZEC 7c, NEAR 8c) —
  consistent with a flat 1-cent tick, so §8 item 1 leans that way.
- **Index coverage is 59.9% and flagged GAPPY** on every one of the ten
  indices: ~100,005 seconds present out of 166,896 in the span. Four in ten
  index prints are missing. This degrades every model-based test and is
  **undiagnosed** — is it the feed, the subscription, or the reader?

### Bugs found in run 2, fixed
- **`book.py` checked sequence continuity per TICKER.** The collector
  subscribes a LIST of market_tickers in one call, so Kalshi's `seq`
  increments per SUBSCRIPTION across every market in it. Consecutive deltas
  for one ticker jump by however many other markets spoke in between, so
  nearly every delta read as a gap: 74,343,133 deltas parsed, **24 of 1,090
  markets** rebuilt. Now keyed on `sid`, with a gap invalidating every book
  under that subscription. Self-test (8 markets interleaved on one sid)
  reproduces it: 8 of 328 states under the old logic, 328 of 328 under the
  new. **The depth figure above must be re-measured after this.**
- **`go.py`'s EMPTY flag matched bare substrings**, so `"1,090 markets"`
  matched `"0 markets"` and five stages that had each loaded ~710,000
  messages were labelled `EMPTY -- no data loaded`. A false EMPTY is worse
  than none: it buries a real result under the one label that says do not read
  this. Now boundary-anchored regexes.

### Operational note from the watchdog log
Recording is healthy (~76 MB/h kalshi, ~89 MB/h feeds). The size column looks
frozen for most of each hour and then jumps at :04 — that is Windows not
updating directory metadata until the hourly file closes, not a stall.
**But free disk swung 71.5 -> 36.5 -> 44.7 GB in five hours** while the data
directories grew ~100 MB/h. Something else on that machine is taking and
releasing tens of gigabytes. The watchdog halts below 5 GB.

---

## 0. THE ONE URGENT THING

**Both recorders are dead** and have been since 2026-08-26 (feed_data stopped
~03:59 UTC, kalshi_data ~05:41 UTC — they died when the user's PC crashed and
never came back). Recording time is the only thing in this project that cannot
be recovered later.

```powershell
powershell -ExecutionPolicy Bypass -File C:\kals\run_all.ps1
```

Restart just after the top of an hour (see §5, gzip trailers).

---

## 1. THE GOAL, VERBATIM

A bot that makes **consistent money on markets resolving every 30 minutes or
less**. The user's words: *"crypto, metal, anything as long as it's a market
that runs on 30 min intervals or less, doesn't have to be Kalshi, as long as a
strategy exists."* And: *"It doesn't have to be a Kalshi error that we try to
take advantage of… The prompt is just to make money."*

It **will run with real money**. The user has explicitly asked for wide,
aggressive idea generation, and has criticised narrow searching before:
*"Just because you can't think of something immediately doesn't mean it's not
there."*

### Hard rules (from RUNBOOK.md, non-negotiable)
1. **NEVER place, amend or cancel an order.** No `POST /portfolio/orders`,
   ever. There is no order code in this repo and none may be added.
2. **Never write, move or delete anything under `kalshi_data/` or
   `feed_data/`.** A collector is writing there and exchange feeds have no
   backfill.
3. Cluster by market/close-time, always. Report `n` as markets or clusters,
   never trades.
4. Never claim a result that was not measured.
5. Every estimator must be calibrated against a known answer before it touches
   real data.
6. Never infer a price's unit from a single observation's magnitude.

---

## 2. THE SETTLEMENT MODEL (established and verified)

Kalshi 15-min crypto binaries. Settlement = mean of the 60 discrete 1-second
CF Benchmarks index prints before close, compared to the same for the 60 prints
before open. Therefore:

- **`strike(N+1) == settle(N)` exactly.** Verified bit-for-bit in 19,471 of
  19,471 within-run consecutive pairs. (See §4 for what this does and does not
  prove.)
- `Var(settle − strike) = 880σ²` — MC-verified in `settlement_math.py`.
- Before the averaging window: `Var = σ²(τ − 39.50)`, τ = seconds to close.
  RUNBOOK's old `σ²(τ+20)` was wrong; at 120s it overstates vol by 32%.
- Inside the window: `Var = σ²·r(r+1)(2r+1)/21600`, r = ticks not yet locked.
  The continuous `σ²r³/10800` fails exactly where we would trade.
- Fair value: `Φ( ((locked_sum + r·spot)/60 − K) / sd )`. **One free
  parameter: σ.**
- `d(fair)/d(log σ) = −z·φ(z)`, maximised at **0.242**. A relative error ε in
  σ moves fair value by up to 0.242ε — this is the floor under every σ-based
  edge. A 33-second σ̂ carries 12.3% error = a **2.98¢ phantom edge**, and the
  engine built on it traded 18–28% of windows against a *provably fair* book
  and lost 3.7¢/contract.
- Fee: quadratic, `ceil(0.07·P·(1−P)·n)` — 0.33¢ at 95¢.
- **TICK SIZE IS UNRESOLVED AND MATTERS.** Code assumes a tapered grid (0.1¢
  below 10¢/above 90¢, 1¢ between). The API's `price_ranges` on market objects
  says **step = 0.01 on notional 1.0000, i.e. a flat 1-cent tick**. If the flat
  tick is right, every target edge under 1¢ is unactionable regardless of
  whether it exists. **Resolve this from the API before sizing anything.**

### The independent-unit result (the most important number in the project)
Twelve crypto series close **simultaneously** at ρ≈0.8, worth **1.22 effective
independent units**. So the independent observation is the **close time**, not
the market — **4 per hour**. 26 hours of recording = **104 clusters**, not
1,248 markets. Every earlier "n = 4,300 markets" overstated the sample ~12×.

Consequence, from `power.py`: the smallest P&L edge detectable from replayed
data is ~2.9¢ at 1 day, 1.5¢ at 7 days, 0.8¢ at 30 days. Tradeable edges here
are 0.5–2¢. **Replayed P&L cannot confirm a strategy at any recording length
you will have.** The deploy decision must rest on a per-second mechanism
(leadlag/feeds/proxy/pathstats get 3,600 obs/hour instead of 4).

---

## 3. THE FIRST REAL RUN (2026-08-26) — WHAT IT ACTUALLY SHOWED

The run completed, all six steps reported "ok", and **94% of recorded data was
never read**.

**Cause**: Kalshi emits its websocket fields with unit suffixes, as STRINGS —
`yes_bid_dollars`, `yes_ask_dollars`, `yes_bid_size_fp`, `yes_ask_size_fp` on
`ticker`; `price_dollars`, `delta_fp` on `orderbook_delta`. Loaders asked for
`yes_bid` / `price` / `delta` and got nothing.

- **68,976,084 of 68,976,084** orderbook deltas unparsed (2.0 GB).
- 7 stages loaded zero quotes (replay, leadlag, cross, openwindow, implied,
  pathstats, proxy); `book` loaded zero deltas. All exited 0.
- Fixed in `8af76b4`, with self-tests that reproduce the exact failure
  (`0 of 300 quotes`, `120 deltas unparsed`) when the fix is reverted.

**Eight independent verifiers recomputed the run from the raw cache.** The
arithmetic transcribed perfectly — ~340 printed cells all reproduce. Every
problem was in *what* was computed.

### THE ONE FINDING THAT SURVIVES

**Volatility clustering in 15-minute settlement returns.** `ac1` of `|r|` =
0.281–0.373 across the six series with adequate history (BTC 0.297, ETH 0.299,
XRP 0.373, DOGE 0.346, BNB 0.281, HYPE 0.315). It survives:
- one-day circular block bootstrap: t = 5.3–10.4
- a fully non-parametric median-indicator sign test: t = 8.3–14.2
- 99% winsorization, and dropping the single largest-|r| day
- full time-of-day de-seasonalization

It clears the corrected bar (|t| = 3.76) independently in all six. Corroborated
out-of-sample by `volmodel`: a causal EWMA σ beats an expanding-window constant
σ per-window in **BTC (63.6% win rate, t = +13.7) and ETH (57.3%, t = +7.3)**
— and *only* those two (XRP +2.6, BNB +1.3, DOGE −0.8, HYPE −1.6).

**It is not yet money.** `volmodel` states the condition itself: this is an edge
only if *the book's σ is slow*. The stage that measures that (`implied.py`)
returned zero observations. **This is the next experiment — see §7.**

### TWO CORRECTLY-MEASURED NULLS (real, not empty)
- **`pathstats`**: the contract price is a martingale on trade-print evidence.
  54 tests, max |t| = 2.5 against its own computed bar of 3.31, 405 close-time
  clusters. Strengthened by the fact its contaminated input pushes *toward*
  false positives.
- **`placebo`**: no exploitable terminal-calibration edge in 3,600 markets and
  8,024,108 prints. The run's largest |t| (4.341) sits at the **55.5th
  percentile** of what an efficient market produces on the same tape.
- **No directional edge.** Up-rate 50.4% over 5,195 markets; every series'
  deviation is smaller than its own MDE.

### THINGS THAT LOOKED REAL AND ARE NOT
- `KXSOL15M ac2 = −0.2227, t = −4.4` — **one pair** of 398 supplies 74% of the
  numerator; delete it and ac2 = −0.058. Also from a stale cache.
- **04h volatility peaks** (XRP 1.36×, DOGE 1.38×, BNB 1.30×) — a single day,
  2026-08-22, supplies 76–85% of the bucket via one ~19σ move shared across all
  three. Rotation test p = 0.59 / 0.82 / 0.94.
- **`volmodel` dLL headline** (+347.7 to +733.2) — the top 20 observations of
  946–2,548 are 44–105% of the total. Above 100% means the other ~1,000 windows
  are net negative. Block-bootstrap t = 1.2–2.4.
- **All six "MISPRICED" D-FINAL calibration cells** — killed three independent
  ways, including placebo's own null.

---

## 4. WHAT IS KNOWN TO BE WRONG WITH THE TOOLING'S OWN CLAIMS

- **GATE C is weaker than advertised.** `strike(N+1)==settle(N)` holds
  bit-exact in 19,471/19,471 *within-run* pairs but only **1 of 73** pairs that
  straddle a data gap. It verifies that Kalshi copied a field, not that
  settlement is computed correctly. The docstring's "stronger settlement gate
  than kalshi_gate1.py" should be restated.
- **`KXDOGE15M`'s GATE C `*FAIL*` is a false alarm** — `floor_strike` is
  quantized to 1e-6 while `expiration_value` carries 1e-7. The identity holds
  in 1,978/1,978 pairs under `floor(settle × 1e6)/1e6`, always one-sided
  (strike ≤ settle).
- **`chain.py` uses iid SEs (`1/√n`) on both autocorrelation tables**, while
  the same report proves the data is heteroskedastic. Should be
  block-bootstrap or HAC. **Unfixed.**
- **`KXBTC15M` was not pulled in the 2026-08-26 run** (the stage log lists 11
  series, BTC absent) — the anchor of the whole detectability table came from a
  cache ~10h stale. Other series were truncated by HTTP 429s that the report
  re-describes as "under half the history". **Unfixed.**
- ~~**`doctor.channel_stats` undercounts** wherever `mid-write > 0`~~ —
  **FIXED.** It used plain `gzip.open`, which dies inside a torn member and
  surrenders everything written after it; the proof was in the run itself
  (86,338 seconds recovered by `feeds.py` against 83,463 messages counted on
  the same channel). It now reads through `gzsalvage`, and a self-test builds
  the exact shape a crash leaves — a member torn mid-write followed by a
  complete member appended on restart — and asserts the census beats
  `gzip.open` on it: **24 lines vs 84**. The `mid-write` column now means
  "salvaged", not "discarded", and the census says so in words.

---

## 5. INFRASTRUCTURE FACTS THAT COST DATA

- **The collector cannot write a gzip trailer on Windows.**
  `loop.add_signal_handler` raises `NotImplementedError` there and was silently
  swallowed, so `c.w.close()` never ran. A restart *inside the same UTC hour*
  then appended a second gzip member behind an untrailered first, and the
  standard reader threw the **whole file** away — reproduced faithfully:
  **0 of 10 records recovered**. `research/gzsalvage.py` reads those files
  member-by-member and recovers them (0→40, 0→60 in its self-test); every
  loader now goes through it. The collector fix (signal fallback + try/finally)
  stops new files being written that way. **Restart near :00.**
- **Memory**: `replay.load_quotes` and `book.rebuild` used to hold whole
  channels as Python dicts — measured 1,330 bytes of peak RSS per message.
  Both stream now: **220 B/msg, 6×**. `orderbook_delta` at 1.9 GB still
  projects ~15 GB peak; `everything.py` preflight prints the projection.
  **A PC crash an hour into a run was this.**
- **Bitstamp is 92.6% waste.** `crypto_feeds.py` subscribes to
  `order_book_<pair>` — Bitstamp's 100-bid/100-ask FULL SNAPSHOT channel — and
  the repo only ever reads `bids[0]`/`asks[0]`. 3.1 GB of 3.2 GB feed_data.
  Switch to `diff_order_book_` or read the depth. **Unfixed.**
- Channels named `ok` and `subscribed` are being written as data channels (the
  collector routes purely on the `type` field). Harmless, tiny.

---

## 6. MARKET FACTS ESTABLISHED FROM THE API

- **There is no fee discount for equities.** `fee_multiplier` is an integer
  **0/1 waiver flag**, not a rate — only 3 series of 1,289 carry 0. All 68
  S&P/Nasdaq series and all 14 crypto 15M series carry `fee_multiplier=1`,
  `fee_type="quadratic"`. PLAN.md's 0.035-vs-0.07 premise is **refuted**.
  `fee_type` also takes `"quadratic_with_maker_fees"` on some series.
  **Open**: read Kalshi's published schedule keyed on `exchange_index`
  (0 = financials, 2 = crypto), present on both series and market objects.
- **The true ≤15-minute universe is 16 series** by the authoritative
  `frequency` field (`"fifteen_min"`): 14 crypto + **`KXINX15M` (S&P 500) and
  `KXNDQ15M` (Nasdaq 100)**. Nothing exists between `fifteen_min` and
  `hourly`; there are 44 hourly series. A ticker-substring scan is unreliable
  (it false-positives `KXUST30M`, a *30-year* Treasury, monthly).
- **`KXCRYPTOLEAD15M` ("Coin Race")** — which of BTC/ETH/SOL/XRP/HYPE has the
  highest return over a 15-min window. One market per coin per event,
  `expiration_value` holds the winning ticker. **This is computable from index
  feeds already recorded**: P(coin i has max 15-min return). Genuinely
  different shape from a binary, and unexplored.
- **`KXCRYPTOCOMP15M`** returned 0 settled markets; the query is correct, the
  series simply has no settled history yet.

---

## 7. THE NEXT EXPERIMENT (both adjudicators independently agreed)

**Get `implied.py` to produce output, and compare the book's implied σ against
the EWMA σ forecast, window by window.**

Why: after every correction, exactly one finding survives (volatility
clustering), and `volmodel` states its own condition — *"this only survives as
an edge if the book's sigma really is slow. That is the thing to measure, not
to assume."* The stage that measures it returned zero observations because of
the field rename, which is now fixed. It needs no new recording; 26 hours are
already on disk.

Order of operations:
1. Restart the recorder (§0).
2. `git pull` in `C:\kals-repo`.
3. `python research\everything.py` — one command, no arguments, 30–60 min.
   It now reads the 2 GB it ignored, and flags any stage that loads no data as
   `EMPTY` rather than `ok`.
4. Read `power.py`'s detectability table **before** `RESULTS.md`.

---

## 8. STILL OPEN / NOT YET DONE

Ranked by information unlocked per unit of work:

1. Resolve the **tick size** contradiction (tapered vs flat 1¢) from the API's
   `price_ranges`. It decides whether sub-cent edges are worth chasing at all.
2. Replace `chain.py`'s iid SEs with block-bootstrap on both autocorrelation
   tables. It is the difference between "one cell clears the bar" and "nothing
   exceeds |t| = 1.3".
3. ~~Make `doctor.channel_stats` use `gzsalvage`~~ — done; the census is no
   longer a lower bound.
4. Fix `chain.py`'s HTTP 429 handling and make it actually pull `KXBTC15M`;
   mark stale/cached series in every table, not once in a run log.
5. Restate GATE C's claim (§4).
6. Switch Bitstamp to the delta channel (§5) — recovers ~3 GB/day of disk.
7. Reopen the fee question via `exchange_index` (§6).
8. Model `KXCRYPTOLEAD15M` (§6) — unexplored, and computable from data in hand.
9. The 87-idea adversarial sweep produced 16 survivors and 6 rated worthwhile;
   **the synthesis agent never returned and that list was lost.** Worth
   regenerating if broad idea coverage is wanted again.

---

## 9. METHOD — WHY THIS PROJECT WORKS THE WAY IT DOES

Every large edge this project has produced has been a measurement bug. Roughly
thirty have been caught, every one by a self-test planting a known answer:
occupation-time selection bias, σ-noise selection, tick-quantization giving the
model a free win (t=10.6), a reflecting-barrier generator, per-observation
cents/dollars inference (a 75¢/contract phantom), pricing eleven series off
bitcoin (+6.13¢/contract at t=4.9 against two fair books), differencing across
data gaps, an `except Exception` swallowing a `NameError` as "0 rows".

So: **a statistic without a calibrated null is not evidence.** Anything
eye-catching is a bug until it survives its own null. Prefer estimators whose
correct answer is known in advance. And the corrected significance bar for one
`go.py` run (294 statistics) is **|t| = 3.76 on a normal** — but several
statistics here are *t* on ~19 degrees of freedom, where the same bar is
**4.66**. Re-measuring on fresh data beats any correction.

### The generative methods that produced the surviving ideas
1. Differentiate the pricing function; sort candidates by *which parameter they
   live in* (μ-based edges are robust, σ-based ones are capped by our own σ̂
   error). This one move re-ranked everything.
2. Hunt for what is *arithmetically determined* rather than predicted
   (`strike(N+1)=settle(N)`, the locked partial average).
3. Attack the *premises* of existing claims, not the conclusions. Killing "every
   window opens at 50¢" produced the openwindow idea.
4. Ask what nobody has ever looked at (second zero; 3 GB/day of feeds no code
   had read).
5. Invert: not "where's the edge" but "what would the market have to be doing,
   and who would be doing it?" → `proxy.py`.
6. Price the exit before the entry — this killed perp delta-hedging in one
   calculation (10.9¢ at 900s to 98¢ at 30s, against 0.5–2¢ edges).

---

## 10. FILE MAP

**Runner**: `research/everything.py` — one command, does everything, writes
`REPORT.md` + a zip. `research/go.py` — self-test gate + 13 analysis stages.

**Model & power**: `settlement_math.py` (exact model, MC-verified),
`power.py` (minimum detectable effect + multiple-testing), `tdist.py`
(Student-t), `viability.py` (edge → Sharpe/drawdown/time-to-validate),
`settlewin.py` (shared conditional-mean helper).

**Data plumbing**: `doctor.py` (schema prober — writes `schema.json`),
`gzsalvage.py` (recovers restart-damaged gzip), `replay.py` (loaders + replay),
`book.py` (order-book rebuild).

**Analysis stages**: `chain.py`, `volmodel.py`, `placebo.py`, `cross.py`,
`openwindow.py`, `implied.py`, `feeds.py`, `pathstats.py`, `proxy.py`,
`leadlag.py`, `edge.py`, `engine.py` (decision logic, **no order code**).

**Docs**: `STATUS.md`, `PLAN_V3.md` (ranked edge list), `RUNBOOK.md` (hard
rules + API traps), `RUN_WHEN_HOME.md` (operator card), `research/RESULTS_R1..R6.md`
(earlier findings, each with its method note).

**Recorders** (root): `kalshi_collector.py`, `crypto_feeds.py`, `run_all.ps1`.
